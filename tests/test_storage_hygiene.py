import asyncio
import functools
import json
import os
import time

from fastapi.testclient import TestClient
from filelock import FileLock

from backend import capacity, server
from backend.runner import MockRunner
from backend.server import create_app
from test_backend import _settings


def _upload(client, name, data=b'fake', kind='video/mp4'):
    return client.post('/api/uploads', files={'file': (name, data, kind)}).json()


def _age(settings, upload_id, seconds=7200):
    path = next((settings.workspace / 'uploads').glob(f'{upload_id}.*'))
    old = time.time() - seconds
    os.utime(path, (old, old))
    return path


def test_a_busy_storage_lock_is_waited_for_without_blocking_and_answers_503(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'capacity_held', functools.partial(capacity.capacity_held, timeout=.3))
    settings = _settings(tmp_path)
    with TestClient(create_app(settings, MockRunner(pace=0))) as client:
        with FileLock(str(settings.workspace / '.capacity.lock')):  # an upload, an import or an export writes
            response = client.post('/api/jobs', json={'mode': 'text', 'settings': {'prompt': 'x'}})
        assert response.status_code == 503 and 'busy' in response.json()['detail']
        assert client.post('/api/jobs', json={'mode': 'text', 'settings': {'prompt': 'x'}}).status_code == 200


def test_the_wait_for_the_storage_lock_lets_the_holder_finish():
    async def scenario(path):
        holder = FileLock(path, thread_local=False)
        holder.acquire()
        async def release_soon():
            await asyncio.sleep(.2)  # the holder is a coroutine of the same loop: it must get to run
            holder.release()
        releasing = asyncio.create_task(release_soon())
        waiter = FileLock(path, thread_local=False)
        await capacity.acquire_async(waiter, timeout=5)
        waiter.release()
        await releasing
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        started = time.monotonic()
        asyncio.run(scenario(os.path.join(directory, '.capacity.lock')))
        assert time.monotonic() - started < 2


def test_cleaning_removes_unused_uploads_and_studio_pictures_but_keeps_what_is_used(tmp_path):
    settings = _settings(tmp_path)
    thumbs, reviews = settings.workspace / 'thumbs', settings.workspace / 'reviews' / 'abc'
    for path in (thumbs / 'cover_abc_1.jpg', thumbs / 'p_0123456789ab_SHOT_001_k.jpg', reviews / '000001.jpg'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'x' * 10)
    with TestClient(create_app(settings, MockRunner(pace=0))) as client:
        used, placed, unused, recent = (_upload(client, f'{name}.mp4') for name in ('used', 'placed', 'unused', 'recent'))
        for item in (used, placed, unused):
            _age(settings, item['id'])
        client.post('/api/jobs', json={'mode': 'remix', 'source': used['id'], 'settings': {'duration': 14}})
        for _ in range(100):
            if all(job['status'] not in ('queued', 'running') for job in client.get('/api/jobs').json()):
                break
            time.sleep(.02)
        dry = client.post('/api/storage/caches/clean?dry_run=true', json={'keep_uploads': [placed['id']]}).json()
        assert dry == {'freed': 34, 'in_use': 0, 'uploads': 1}
        assert client.get(unused['url']).status_code == 200
        assert client.post('/api/storage/caches/clean', json={'keep_uploads': [placed['id']]}).json() == dry
        assert client.get(unused['url']).status_code == 404
        assert all(client.get(item['url']).status_code == 200 for item in (used, placed, recent))
    assert not any(thumbs.iterdir()) and not reviews.exists()
    assert unused['id'] not in json.loads((settings.workspace / 'uploads.json').read_text(encoding='utf-8'))


def test_deleting_a_job_removes_its_covers_and_review_frames(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings, MockRunner(pace=0))) as client:
        job = client.post('/api/jobs', json={'mode': 'text', 'settings': {'prompt': 'x'}}).json()
        for _ in range(100):
            if client.get(f"/api/jobs/{job['id']}").json()['status'] not in ('queued', 'running'):
                break
            time.sleep(.02)
        thumbs = settings.workspace / 'thumbs'
        thumbs.mkdir(parents=True)
        other = thumbs / 'cover_someone_else_1.jpg'
        for path in (thumbs / f"cover_{job['id']}_1.jpg", thumbs / f"cover_{job['id']}_2.jpg", other,
                     settings.workspace / 'reviews' / job['id'] / '000001.jpg'):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'x')
        assert client.delete(f"/api/jobs/{job['id']}").status_code == 200
    assert [path.name for path in thumbs.iterdir()] == [other.name]
    assert not (settings.workspace / 'reviews' / job['id']).exists()
