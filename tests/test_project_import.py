import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.jobs import Job
from backend.manual_timeline import editor_payload, save_document
from backend.models import JobRequest, JobState
from backend.project_import import extract_project_archive
from backend.server import create_app
from backend.storage import write_json

pytest_plugins = ('test_manual_timeline',)


def test_project_zip_roundtrip_restores_timeline_and_remaps_uploads(editorial_project, tmp_path):
    settings = Settings(
        'http://127.0.0.1:1',
        'http://127.0.0.1:1',
        tmp_path / 'out',
        tmp_path / 'workspace',
        tmp_path / 'workflows',
        True,
    )
    upload_id = 'abcdef123456'
    upload_path = settings.workspace / 'uploads' / f'{upload_id}.wav'
    upload_path.parent.mkdir(parents=True)
    upload_path.write_bytes(b'portable music input')
    write_json(settings.workspace / 'uploads.json', {
        upload_id: {'name': 'music.wav', 'kind': 'audio'},
    })
    request = JobRequest(mode='music', music=upload_id)
    job = Job(request, JobState(
        id='originaljob1',
        mode='music',
        status='succeeded',
        stage='done',
        project_id=editorial_project.name,
    ))
    write_json(settings.workspace / 'state' / f'{job.id}.json', {
        'request': request.model_dump(),
        'state': job.state.model_dump(),
        'edits': 0,
    })
    document = editor_payload(editorial_project, 3600)['document']
    save_document(editorial_project, document, None)

    with TestClient(create_app(settings)) as client:
        exported = client.get(f'/api/jobs/{job.id}/export')
        assert exported.status_code == 200
        with zipfile.ZipFile(io.BytesIO(exported.content)) as bundle:
            assert 'editor/timeline.json' in bundle.namelist()
        imported = client.post(
            '/api/projects/import',
            files={'file': ('project.zip', exported.content, 'application/zip')},
        )

        assert imported.status_code == 200, imported.text
        state = imported.json()
        assert state['id'] != job.id
        assert state['project_id'] != editorial_project.name
        assert state['status'] == 'succeeded'
        assert len(state['shots']) == 2 and all(shot['done'] for shot in state['shots'])
        inputs = client.get(f"/api/jobs/{state['id']}/inputs").json()
        assert inputs['music']['id'] != upload_id
        new_music = settings.workspace / 'uploads' / f"{inputs['music']['id']}.wav"
        assert new_music.read_bytes() == b'portable music input'
        imported_project = settings.output_dir / 'MajoorVideoTools' / state['project_id']
        record = json.loads((imported_project / 'editor/timeline.json').read_text())
        assert record['sources']['project_id'] == state['project_id']
        assert record['document']['project_id'] == state['project_id']
        assert record['document']['source_signature'] != document['source_signature']
        assert record['document']['clips'] == document['clips']
        assert editor_payload(imported_project, 3600)['stale'] is False


def test_project_archive_rejects_traversal_before_extracting(tmp_path):
    archive_path = tmp_path / 'unsafe.zip'
    destination = tmp_path / 'extract'
    with zipfile.ZipFile(archive_path, 'w') as archive:
        archive.writestr('../outside.txt', 'unsafe')

    with pytest.raises(ValueError, match='unsafe path'):
        extract_project_archive(archive_path, destination, 1024)
    assert not destination.exists()
