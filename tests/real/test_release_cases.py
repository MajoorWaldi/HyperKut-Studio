"""Opt-in tests against an isolated Studio; no network downloads or paid generation."""
import hashlib
import io
import json
import os
import subprocess
import time
import zipfile
from pathlib import Path
from fractions import Fraction

import httpx
import pytest

pytestmark=pytest.mark.real
CASES=json.loads((Path(__file__).parents[1]/'fixtures/release-cases.json').read_text())


@pytest.mark.parametrize('case',CASES,ids=[c['id'] for c in CASES])
def test_release_case(case,tmp_path):
    root=os.environ.get('SECATOR_TEST_MEDIA_DIR')
    if not root:pytest.skip('Set SECATOR_TEST_MEDIA_DIR to authorized local benchmark media')
    root=Path(root)
    paths=[case[k] for k in ('source','music','voice') if k in case]+case.get('refs',[])
    if any(not (root/p).is_file() for p in paths):pytest.skip('Required authorized media missing for '+case['id'])
    url=os.environ.get('SECATOR_TEST_STUDIO','http://127.0.0.1:8098')
    proof={'case':case,'media':{},'manual_identity_review':'pending','manual_voice_review':'pending'}
    with httpx.Client(base_url=url,timeout=120) as client:
        ids={}
        for name in paths:
            path=root/name
            proof['media'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
            with path.open('rb') as stream:
                response=client.post('/api/uploads',files={'file':(path.name,stream)})
                response.raise_for_status();ids[name]=response.json()['id']
        settings={k:case[k] for k in ('prompt','duration','ratio')}
        settings.update(quality='draft',places=False,effects=False,text=False,sound_effects=False,retry_bad_takes=False,quality_check=False,seed=2042)
        if 'voice' in case:settings.update(audio='voice',dialogue=case['dialogue'])
        body={'mode':case['mode'],'settings':settings,'refs':[ids[p] for p in case.get('refs',[])]}
        body.update({k:ids[case[k]] for k in ('source','music','voice') if k in case})
        response=client.post('/api/jobs',json=body);response.raise_for_status();job=response.json()['id']
        proof['job']=job
        output=Path(os.environ.get('SECATOR_TEST_REPORTS',str(tmp_path)))
        output.mkdir(parents=True,exist_ok=True)
        deadline=time.monotonic()+float(os.environ.get('SECATOR_TEST_TIMEOUT',3600))
        try:
            while time.monotonic()<deadline:
                state=client.get(f'/api/jobs/{job}').json()
                if state['status'] not in ('queued','running'):break
                time.sleep(2)
            else:raise AssertionError('Real job timed out')
            proof['state']=state
            assert state['status']=='succeeded',state.get('error')
            video=client.get(f'/api/jobs/{job}/video');video.raise_for_status()
            path=output/f'{case["id"]}.mp4';path.write_bytes(video.content)
            metadata=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],capture_output=True,check=True).stdout)
            stream=next(s for s in metadata['streams'] if s['codec_type']=='video')
            assert abs(float(metadata['format']['duration'])-case['duration'])<=1/24+.001
            w,h=map(int,case['ratio'].split(':'))
            if case['mode']!='remix':assert abs(stream['width']/stream['height']-w/h)<.06
            if 'voice' in case:assert any(s['codec_type']=='audio' for s in metadata['streams'])
            output_fps=float(Fraction(stream['avg_frame_rate']))
            assert int(stream['nb_frames'])==round(case['duration']*output_fps)
            archive=client.get(f'/api/jobs/{job}/export');archive.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
                assert bundle.testzip() is None and bundle.namelist()
            proof['export_zip_valid']=True
            review=client.get(f'/api/jobs/{job}/review');review.raise_for_status()
            proof['review_frames']=len(review.json()['frames'])
            proof['metadata']=metadata
        finally:
            (output/f'{case["id"]}.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
