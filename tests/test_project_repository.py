import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.storage import SharedProjectRepository, ProjectRevisionConflict, write_json


def test_shared_adapter_keeps_original_paths_and_history(tmp_path):
    repo = SharedProjectRepository(tmp_path)
    project = repo.path('p_12345678')
    write_json(project / 'manifest.json', {'project_revision':1, 'prompt':'old'})
    with repo.edit('p_12345678', expected_revision=1) as manifest:
        manifest['prompt'] = 'new'
    path, manifest = repo.read('p_12345678')
    assert path == project and manifest == {'project_revision':2, 'prompt':'new'}
    assert len(list((project / 'manifests').glob('*.json'))) == 1


def test_stale_edit_preserves_bytes_and_history(tmp_path):
    repo = SharedProjectRepository(tmp_path)
    path = repo.path('p_12345678') / 'manifest.json'
    write_json(path, {'project_revision':3})
    before = path.read_bytes()
    with pytest.raises(ProjectRevisionConflict):
        with repo.edit('p_12345678', expected_revision=2):
            pytest.fail('Stale writer entered transaction')
    assert path.read_bytes() == before
    assert not (path.parent / 'manifests').exists()


def test_edit_exception_keeps_original(tmp_path):
    repo = SharedProjectRepository(tmp_path)
    path = repo.path('p_12345678') / 'manifest.json'
    write_json(path, {'project_revision':1})
    before = path.read_bytes()
    with pytest.raises(RuntimeError):
        with repo.edit('p_12345678') as data:
            data['project_revision'] = 99
            raise RuntimeError('interrupted')
    assert path.read_bytes() == before


def test_concurrent_shared_adapters_compare_inside_lock(tmp_path):
    path = tmp_path / 'p_12345678' / 'manifest.json'
    write_json(path, {'project_revision':1})
    def edit(value):
        try:
            with SharedProjectRepository(tmp_path).edit('p_12345678', expected_revision=1) as manifest:
                manifest['result'] = value
            return True
        except ProjectRevisionConflict:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit, ('A','B'))) == [False,True]
    assert json.loads(path.read_bytes())['project_revision'] == 2
