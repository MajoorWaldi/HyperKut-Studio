from fastapi.testclient import TestClient

from backend.runner import MockRunner
from backend.server import create_app
from test_backend import _settings


def test_cleaning_the_caches_keeps_takes_sources_and_exports(tmp_path):
    settings = _settings(tmp_path)
    root = settings.output_dir / 'MajoorVideoTools'
    project = root / 'p_0123456789ab'
    kept = [project / 'generated/take.mp4', project / 'sources/source.mp4', project / 'exports/final.mp4', project / 'cache/thumbnails/SHOT_001.jpg']
    rebuilt = [project / 'cache/clips/trim.mp4', project / 'cache/sfx_ab_2.0.wav', root / 'hyperframes/key/motion.mp4']
    for path in kept + rebuilt:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'x' * 10)
    with TestClient(create_app(settings, MockRunner(pace=0))) as client:
        assert client.post('/api/storage/caches/clean?dry_run=true').json() == {'freed': 30, 'in_use': 0}
        assert all(path.exists() for path in rebuilt)
        assert client.post('/api/storage/caches/clean').json() == {'freed': 30, 'in_use': 0}
    assert not any(path.exists() for path in rebuilt)
    assert all(path.exists() for path in kept)


def test_a_render_that_holds_its_lock_is_kept_and_counted(tmp_path):
    from filelock import FileLock

    settings = _settings(tmp_path)
    root = settings.output_dir / 'MajoorVideoTools' / 'hyperframes'
    busy, idle = root / 'busy', root / 'idle'
    for folder in (busy, idle):
        folder.mkdir(parents=True)
        (folder / 'motion.mp4').write_bytes(b'x' * 10)
    with TestClient(create_app(settings, MockRunner(pace=0))) as client, FileLock(str(busy) + '.lock'):
        assert client.post('/api/storage/caches/clean').json() == {'freed': 10, 'in_use': 1}
    assert (busy / 'motion.mp4').exists() and not idle.exists()
