import json
from fastapi.testclient import TestClient
from backend.server import create_app
from backend.runner import MockRunner
from backend.take_trim import trim_bounds
from test_backend import _settings, _project_on_disk, _finished_job


def test_speed_and_explicit_subcuts_preserve_the_consumed_source_span():
    shot={'target_duration_seconds':2,'plan':{'fx':{'speed':2}}}
    revision={'actual_duration_seconds':6}
    assert trim_bounds(shot,revision,{},24)['max_start']==2
    shot['plan']['fx']={'sub_cuts':[{'frames':24,'start':0},{'frames':24,'start':3,'speed':2}]}
    bounds=trim_bounds(shot,revision,{},24)
    assert bounds['window']==5 and bounds['max_start']==1
    assert trim_bounds(shot,revision,{'effects':False},24)['max_start']==4


def test_slip_is_persisted_per_active_take_and_invalid_changes_leave_manifest_untouched(tmp_path):
    settings=_settings(tmp_path)
    folder=_project_on_disk(settings)
    manifest=json.loads((folder/'manifest.json').read_text())
    manifest['source']={'fps_num':24,'fps_den':1}
    manifest['shots'][0]['target_duration_seconds']=2
    for revision in manifest['shots'][0]['revisions']:
        revision['actual_duration_seconds']=5
    (folder/'manifest.json').write_text(json.dumps(manifest))
    runner=MockRunner(pace=.01)
    run=runner.run
    async def with_project(job):
        await run(job)
        job.update(project_id='p_0123456789ab')
    runner.run=with_project
    with TestClient(create_app(settings,runner)) as client:
        job=_finished_job(client)
        url=f'/api/jobs/{job}/shots/SHOT_001/trim'
        response=client.post(url,json={'take':'take_002','start':1.5})
        assert response.status_code==200,response.text
        assert response.json()[1]['start']==1.5
        before=(folder/'manifest.json').read_bytes()
        for body,status in [({'take':'take_001','start':1},409),({'take':'take_002','start':4},422),({'take':'take_002','start':-1},422)]:
            assert client.post(url,json=body).status_code==status
            assert (folder/'manifest.json').read_bytes()==before
        assert client.get(f'/api/jobs/{job}/shots/SHOT_001/takes/take_002/video').content==b'two'
        client.post(f'/api/jobs/{job}/shots/SHOT_001/active',json={'take':'take_001'})
        listed=client.get(f'/api/jobs/{job}/shots/SHOT_001/takes').json()
        assert listed[0]['start']==0 and listed[1]['start']==1.5
        client.patch(f'/api/jobs/{job}/shots/SHOT_001',json={'locked':True})
        assert client.post(url,json={'take':'take_001','start':1}).status_code==409
