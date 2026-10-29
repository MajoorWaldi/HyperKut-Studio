import json
from types import SimpleNamespace
from PIL import Image
from backend.motion_presets import subject_accent
from backend.unified_motion import finishing_layers


def test_pack_is_optional_and_preserves_protected_actions_and_manual_layers():
    shots=[SimpleNamespace(id='A',duration=2),SimpleNamespace(id='B',duration=2)]
    manifest={'shots':[{'shot_id':'A','plan':{'story':{'protect_action':True}}}]}
    assert json.loads(finishing_layers(manifest,shots,'[]'))==[]
    rows=json.loads(finishing_layers(manifest,shots,'{"pack":"tech","layers":[]}'))
    assert rows and all(row['shot_id']=='B' for row in rows)
    assert all(row['type']=='vector' for row in rows)
    manual='{"pack":"pop","layers":[{"type":"box","shot_id":"B","start":0,"end":1}]}'
    assert len(json.loads(finishing_layers(manifest,shots,manual)))==1
    assert json.loads(finishing_layers(manifest,shots,'{"pack":"tech"}',motion_on=False))==[]


def test_subject_color_ignores_white_background_and_returns_none_when_uncertain(tmp_path):
    image=Image.new('RGB',(100,100),'white')
    image.paste((180,35,45),(20,20,80,80))
    path=tmp_path/'subject.png';image.save(path)
    assert subject_accent(path).startswith('#')
    assert int(subject_accent(path)[1:3],16)>int(subject_accent(path)[3:5],16)
    Image.new('RGB',(100,100),'white').save(path)
    assert subject_accent(path) is None


def test_subject_accent_preserves_the_complete_direction():
    from backend.motion_presets import with_motion_accent
    assert with_motion_accent('sobre et discret','#123456')=='sobre et discret #123456'
    spec=json.loads(with_motion_accent('{"preset":"minimal","reactive":false,"intensity":0.12}','#123456'))
    assert spec=={'preset':'minimal','reactive':False,'intensity':.12,'accent':'#123456'}
