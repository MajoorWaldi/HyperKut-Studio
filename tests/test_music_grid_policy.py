from backend.direction import apply_plan_contract
from backend.models import Settings
from backend.templates import load_templates
from backend.config import ROOT


def test_music_grid_guides_without_discarding_additional_planner_shots():
    graph=load_templates(ROOT/'workflows','music')['stage1'].fill({'planning_instructions':''})
    apply_plan_contract(graph,Settings(duration=15,cut_density='high'))
    music={key for key,node in graph.items() if node['class_type']=='MajoorCreateTimeline' and node['inputs'].get('source')=='music'}
    assert music and all(graph[key]['inputs']['rhythm_reference_only'] for key in music)
    finals=[node for node in graph.values() if node['class_type']=='MajoorCreateTimeline' and node['inputs'].get('source')=='json']
    assert finals and all('skeleton_json' not in node['inputs'] for node in finals)
    assert all(node['inputs']['source.duration']==15 for node in finals)
    assert any(node['class_type']=='MajoorEnsureBurst' and node['inputs']['density']=='high' for node in graph.values())
    count=len(graph);apply_plan_contract(graph,Settings(duration=15,cut_density='high'));assert len(graph)==count


def test_text_and_manual_fixed_skeletons_are_not_rewired():
    graph={'fixed':{'class_type':'MajoorCreateTimeline','inputs':{'source':'json','skeleton_json':['manual',1]}}}
    apply_plan_contract(graph,Settings())
    assert graph['fixed']['inputs']['skeleton_json']==['manual',1]
