from backend.creative_controls import level
from backend.models import JobRequest,JobState
from backend.jobs import Job
from backend.runner import ComfyRunner
from backend.templates import load_templates
from backend.direction import brief_context,validate_prepared
from backend.brief_preview import branch
from backend.config import ROOT
from test_backend import _settings
from fastapi.testclient import TestClient
from backend.server import create_app
from backend.runner import MockRunner


def test_named_levels_reach_enrichment_and_planner_and_keep_pose_compatibility(tmp_path):
    runner=ComfyRunner(_settings(tmp_path),{})
    graphs=[]
    for value in (0,50,85):
        request=JobRequest(mode='text',settings={'structure':value,'creativity':value,'prompt':'A product film'})
        values=runner._values(Job(request,JobState(id='fixed',mode='text')))
        template=load_templates(ROOT/'workflows','text')['stage1']
        graph=template.fill({k:v for k,v in values.items() if k in template.slots})
        target=next(k for k,n in graph.items() if n['class_type']=='TextGenerate' and isinstance(n['inputs'].get('system_prompt'),list) and graph[str(n['inputs']['system_prompt'][0])]['inputs'].get('skill')=='prompt_enhancer')
        graphs.append(branch(graph,target))
        assert 'Creative choices for this new video' in values['planning_instructions']
        assert graph['82']['inputs']['creative_freedom']==level(value,('faithful','balanced','free'))
        assert values['pose_strength']==round(.4+.6*value/100,2)
    assert graphs[0]!=graphs[1] and graphs[1]!=graphs[2]


def test_effective_context_is_stable_within_levels_and_legacy_approvals_survive():
    request=JobRequest(mode='text',settings={'prompt':'Film','structure':85,'creativity':50})
    same=request.model_copy(deep=True);same.settings.structure=86;same.settings.creativity=66
    assert brief_context(request)==brief_context(same)
    changed=request.model_copy(deep=True);changed.settings.creativity=85
    assert brief_context(request)!=brief_context(changed)
    request.settings.approved_brief='Retained manual brief'
    request.settings.approved_brief_context=brief_context(request,legacy=True)
    validate_prepared(request)


def test_retained_brief_can_be_approved_without_starting_a_job(tmp_path):
    with TestClient(create_app(_settings(tmp_path),MockRunner(pace=.01))) as client:
        body={'mode':'text','settings':{'prompt':'Film','approved_brief':'My edited brief','approved_brief_context':'old','creativity':85}}
        response=client.post('/api/brief-approve',json=body)
        assert response.status_code==200
        req=JobRequest.model_validate(body)
        assert response.json()['context']==brief_context(req)
        assert client.get('/api/jobs').json()==[]
        assert client.post('/api/brief-approve',json={'mode':'text','settings':{'approved_brief':''}}).status_code==422
