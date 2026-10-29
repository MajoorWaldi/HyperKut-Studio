import json
from pathlib import Path

ROOT=Path(__file__).parents[1]


def _graph():
    return json.loads((ROOT/'workflows/remix/shot.api.json').read_text(encoding='utf-8'))


def _nodes(graph,class_type,title=''):
    return {k:n for k,n in graph.items() if n['class_type']==class_type and n.get('_meta',{}).get('title','').startswith(title)}


def test_remix_short_reference_is_padded_only_when_needed():
    graph=_graph()
    (keep_id,keep),=_nodes(graph,'ComfyMathExpression','KEEP THE SHOT?').items()
    assert keep['inputs']['expression']=='a > 0' and list(keep['inputs'])==['expression','values.a']
    (_,reference),=_nodes(graph,'ComfySwitchNode','SOURCE FRAMES as the H3 reference video').items()
    switch=graph[reference['inputs']['on_true'][0]]
    assert switch['class_type']=='ComfySwitchNode'
    short=graph[switch['inputs']['switch'][0]]
    assert switch['inputs']['switch'][1]==2 and short['class_type']=='ComfyMathExpression' and short['inputs']['expression']=='a < 5'
    source=switch['inputs']['on_false']
    padded=graph[switch['inputs']['on_true'][0]]
    assert padded['class_type']=='ImageFromBatch' and padded['inputs']['length']==5
    joined=graph[padded['inputs']['image'][0]]
    assert joined['class_type']=='ImageBatch' and joined['inputs']['image1']==source
    repeated=graph[joined['inputs']['image2'][0]]
    last=graph[repeated['inputs']['image'][0]]
    assert repeated['inputs']['amount']==4
    assert last['inputs']=={'image':source,'batch_index':-1,'length':1}
    # Duration still comes from the actual source, independently of padded refs.
    assert any(n['class_type']=='ComfyMathExpression' and n['inputs'].get('expression')=='a / b' for n in graph.values())


def test_no_subject_and_pose_only_decisions_still_bypass_reference_padding():
    graph=_graph()
    (keep_id,_),=_nodes(graph,'ComfyMathExpression','KEEP THE SHOT?').items()
    (_,reference),=_nodes(graph,'ComfySwitchNode','SOURCE FRAMES as the H3 reference video').items()
    decision=graph[reference['inputs']['switch'][0]]
    assert reference['inputs']['switch'][1]==2 and decision['class_type']=='ComfyMathExpression'  # the pose-only and no-subject decisions drive the reference
    kept=[n for key,n in graph.items() if not key.endswith('_generation_prompt') and n['class_type']=='ComfySwitchNode' and n['inputs'].get('switch')==[keep_id,2]]
    assert kept and all(isinstance(n['inputs'].get('on_true'),list) for n in kept)
