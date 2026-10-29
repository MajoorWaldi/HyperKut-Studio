import json
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.models import JobRequest,Settings
from backend.direction import brief_context,resolved_brief,use_prepared_brief,validate_prepared,normalize_media_roles
from backend.runner import ComfyRunner
from backend.jobs import Job
from backend.server import create_app
from test_backend import _settings


def test_automatic_choices_do_not_impose_a_visual_style():
    settings=Settings(prompt='A quiet portrait')
    assert settings.style=='none' and resolved_brief(settings)=='A quiet portrait'
    assert Settings(art_direction={'look':'auto'}).art_direction=={}
    with pytest.raises(ValidationError):Settings(art_direction={'look':'invented-option'})


def test_absent_picture_batch_does_not_announce_a_phantom_reference():
    graph={'missing':{'class_type':'MajoorEditSkills','inputs':{'n_pictures':1}},'present':{'class_type':'MajoorEditSkills','inputs':{'n_pictures':1,'images':['loader',0]}}}
    normalize_media_roles(graph)
    assert graph['missing']['inputs']['n_pictures']==0
    assert graph['present']['inputs']['n_pictures']==1


def test_same_direction_reaches_idea_and_music_context(tmp_path):
    request=JobRequest(mode='text',settings={'prompt':'A portrait','art_direction':{'look':'collage','light':'night'}})
    values=ComfyRunner(_settings(tmp_path),{})._values(Job(request))
    assert values['brief']==values['idea']==values['idea_creative']
    assert 'paper collage' in values['brief'] and 'nighttime' in values['brief']
    assert json.loads(values['music_context'])['creative_brief']==values['brief']


def test_an_accepted_edited_brief_is_reused_verbatim():
    settings=Settings(prompt='Original phrase',art_direction={'look':'collage'},approved_brief='My edited final direction')
    assert resolved_brief(settings)=='My edited final direction'


def test_prepared_brief_is_invalidated_by_creative_changes_but_not_random_seed():
    request=JobRequest(mode='text',settings={'prompt':'A portrait'})
    request.settings.approved_brief_context=brief_context(request);request.settings.approved_brief='Approved portrait'
    validate_prepared(request)
    request.settings.seed=93;validate_prepared(request)
    request.refs=['another-photo']
    with pytest.raises(ValueError,match='outdated'):validate_prepared(request)


def test_approved_text_bypasses_only_the_enrichment_node():
    graph={'s':{'class_type':'MajoorEditSkills','inputs':{'skill':'prompt_enhancer'}},'e':{'class_type':'TextGenerate','inputs':{'system_prompt':['s',0]}},'m':{'class_type':'TextGenerate','inputs':{'system_prompt':'music director'}}}
    use_prepared_brief(graph,'My edited direction')
    assert graph['e']=={'class_type':'PrimitiveStringMultiline','inputs':{'value':'My edited direction'}}
    assert graph['m']['class_type']=='TextGenerate'


def test_catalog_preview_and_stale_rejection_do_not_start_a_video(tmp_path):
    app=create_app(_settings(tmp_path))
    with TestClient(app) as client:
        assert len(client.get('/api/art-direction').json()['fields'])==4
        request={'mode':'text','settings':{'prompt':'A short portrait','art_direction':{'look':'collage'}}}
        response=client.post('/api/brief-preview',json=request)
        assert response.status_code==200,response.text
        prepared=response.json();assert 'paper collage' in prepared['brief']
        assert client.get('/api/jobs').json()==[]
        request['settings'].update(approved_brief=prepared['brief'],approved_brief_context=prepared['context'],duration=30)
        assert client.post('/api/jobs',json=request).status_code==422
        assert client.get('/api/jobs').json()==[]
        request['settings']['art_direction']={'look':'bad'}
        assert client.post('/api/brief-preview',json=request).status_code==422
