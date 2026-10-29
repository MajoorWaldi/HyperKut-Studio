import json
from pathlib import Path
from types import SimpleNamespace

from backend.unified_motion import finishing_layers, needs_subject_mask
from backend.templates import load_templates


def test_planned_motion_follows_shot_ids_and_respects_text_and_decoration_switches():
    manifest={'shots':[{'shot_id':'A','plan':{'motion':[{'type':'brackets','start':0,'end':'90%','sync':'onset'}, {'type':'text','content':'BASS'}]}}]}
    shots=[SimpleNamespace(id='A',start=3,duration=2)]
    rows=json.loads(finishing_layers(manifest,shots,'[]'))
    assert len(rows)==2 and rows[0]['shot_id']=='A' and rows[0]['sync']=='onset'
    assert len(json.loads(finishing_layers(manifest,shots,'[]',False)))==1
    assert json.loads(finishing_layers(manifest,shots,'[]',True,False))==[]
    manual='[{"type":"box","shot_id":"A","start":0,"end":1}]'
    assert len(json.loads(finishing_layers(manifest,shots,manual)))==1


def test_text_disabled_keeps_dependent_scene_timing_without_rendering_words():
    configured=json.dumps([{'type':'text','id':'title','scene':'demo','content':'HIDE','start':0,'end':1,'sfx':'click'},
                           {'type':'vector','scene':'demo','after':'title','duration':.5}])
    rows=json.loads(finishing_layers({'shots':[]},[],configured,False))
    assert rows[0]['id']=='title' and rows[0]['opacity']==0
    assert all(row['type']=='vector' for row in rows)
    assert 'content' not in rows[0] and 'sfx' not in rows[0]


def test_planned_text_is_transferred_once_with_its_style_and_timing():
    manifest={'shots':[{'shot_id':'A','plan':{'fx':{'text':{'content':'Reveal','start':.5,'end':1.5,'position':'bottom','font':'serif','rotate':12,'repeat':2}}}}]}
    shots=[SimpleNamespace(id='A',start=3,duration=2)]
    configured='[{"type":"box","color":"red"}]'
    rows=json.loads(finishing_layers(manifest,shots,configured))
    assert len(rows)==2 and rows[1]['content']=='REVEAL'
    assert rows[1]['shot_id']=='A'
    assert (rows[1]['start'],rows[1]['end'])==(.5,1.5)
    assert rows[1]['font']=='serif' and rows[1]['repeat']==2 and rows[1]['rotate']==12
    assert json.loads(configured)==[{'type':'box','color':'red'}]  # original edit input is unchanged
    assert len(json.loads(finishing_layers(manifest,shots,configured)))==2  # no append on repeated renders
    assert len(json.loads(finishing_layers(manifest,shots,configured,False)))==1


def test_masks_are_required_only_for_subject_dependent_layers():
    for row in ({'type':'outline'},{'type':'effect','target':'background'},{'type':'track','anchor':'subject_top'}):
        assert needs_subject_mask(json.dumps([row]))
    assert not needs_subject_mask('[{"type":"text","content":"A"},{"type":"effect","target":"frame"},{"type":"track","at":[0.5,0.5]}]')


def test_all_modes_have_one_compositor_and_direct_lazy_mask_inputs():
    folder=Path(__file__).resolve().parents[1]/'workflows'
    for mode in ('text','music','remix'):
        template=load_templates(folder,mode)['final'];graph=template.prompt
        assert not any(node['class_type']=='MajoorMotionGraphics' for node in graph.values())
        hf=graph['hyperframes']['inputs']
        assert graph[hf['video'][0]]['class_type']=='MajoorShotAssemble'
        assert graph[hf['mask'][0]]['class_type']=='RemoveBackground'
        assert ('hyperframes','layers') in template.slots['unified_layers']
        assembly_slot=next(slot for slot in template.slots['unified_layers'] if slot[1]=='motion_layers')
        assert graph[assembly_slot[0]]['class_type']=='MajoorShotAssemble'
    remix=load_templates(folder,'remix')['final'].prompt
    assert remix[remix['hyperframes']['inputs']['source_layers'][0]]['class_type']=='TextGenerate'


def test_disabling_decoration_does_not_discard_manual_or_restored_layers():
    folder=Path(__file__).resolve().parents[1]/'workflows'
    template=load_templates(folder,'remix')['final']
    assert 'hyperframes' not in template.fill({'motion_design':False,'redraw_text':False,'unified_layers':'[]'})
    assert 'hyperframes' in template.fill({'motion_design':False,'redraw_text':True,'unified_layers':'[]'})
    assert 'hyperframes' in template.fill({'motion_design':False,'redraw_text':False,'unified_layers':'[{"type":"box"}]'})
