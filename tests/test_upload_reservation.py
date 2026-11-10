"""An upload reserves its room under the storage lock and is written after: the lock is not held for the copy, and the room is counted meanwhile."""
import os
import time

from fastapi.testclient import TestClient

from backend.capacity import _active_reservations, release_upload_reservation, write_upload_reservation
from backend.jobs import JobStore
from backend.runner import MockRunner
from backend.server import create_app
from test_backend import _settings


def test_an_upload_leaves_no_reservation_and_never_takes_the_name_of_the_client(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings, MockRunner(pace=0))) as client:
        response = client.post('/api/uploads', files={'file': ('clip.wav:hidden', b'1234', 'audio/wav')})
        assert response.status_code == 200
    names = [p.name for p in (settings.workspace / 'uploads').iterdir()]
    assert names and all(':' not in n and 'hidden' not in n and not n.endswith('.part') for n in names)
    assert not list((settings.workspace / '.upload-reservations').glob('*.json'))


def test_the_room_of_an_upload_being_written_is_counted_until_it_is_released(tmp_path):
    settings = _settings(tmp_path)
    store = JobStore(settings.workspace / 'state')
    write_upload_reservation(settings, 'abc', 5000)
    assert _active_reservations(settings, store) == 5000
    (settings.workspace / 'uploads').mkdir(parents=True, exist_ok=True)
    (settings.workspace / 'uploads' / 'abc.part').write_bytes(b'x' * 1000)
    assert _active_reservations(settings, store) == 4000  # the part on disk is counted by the walk of the storage
    release_upload_reservation(settings, 'abc')
    assert _active_reservations(settings, store) == 0


def test_a_reservation_left_by_a_dead_request_frees_its_room(tmp_path):
    settings = _settings(tmp_path)
    write_upload_reservation(settings, 'old', 5000)
    path = settings.workspace / '.upload-reservations' / 'old.json'
    stale = time.time() - 7 * 3600
    os.utime(path, (stale, stale))
    assert _active_reservations(settings, JobStore(settings.workspace / 'state')) == 0 and not path.exists()


def test_the_server_cleans_what_a_stop_left_in_the_uploads(tmp_path):
    settings = _settings(tmp_path)
    (settings.workspace / 'uploads').mkdir(parents=True)
    (settings.workspace / 'uploads' / 'cut.part').write_bytes(b'x')
    write_upload_reservation(settings, 'cut', 10)
    create_app(settings, MockRunner(pace=0))
    assert not (settings.workspace / 'uploads' / 'cut.part').exists() and not list((settings.workspace / '.upload-reservations').glob('*'))
