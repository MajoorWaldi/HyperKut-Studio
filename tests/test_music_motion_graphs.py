import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('mode', ['text', 'music'])
def test_a_text_or_music_take_starts_where_its_motion_meets_the_music(mode):
    graph = json.loads((ROOT / f'workflows/{mode}/shot.api.json').read_text(encoding='utf-8'))
    (key, node), = [(k, n) for k, n in graph.items() if n['class_type'] == 'MajoorApplyShotMetadata']
    assert node['inputs']['align_to_music'] is True
    assert any(n['class_type'] == 'MajoorLoadProjectMusic' for n in graph.values())  # the project keeps its music, which the take is aligned to


def test_the_planner_gets_the_palette_of_the_supplied_pictures(tmp_path):
    from PIL import Image
    from backend.film_palette import palette_direction, picture_palette
    picture = Image.new('RGB', (60, 60), (40, 38, 36))
    picture.paste((20, 120, 230), (45, 45, 60, 60))  # a small blue neon
    picture.paste((226, 222, 218), (0, 0, 60, 20))
    path = tmp_path / 'ref.png'
    picture.save(path)
    found = picture_palette([path])
    assert found['accent'] and int(found['accent'][5:7], 16) > int(found['accent'][1:3], 16) + 80
    assert 'Palette of the supplied pictures' in palette_direction(found) and palette_direction(None) == ''
    assert picture_palette([tmp_path / 'missing.png']) is None


def test_a_title_that_passes_through_the_subject_asks_for_its_mask():
    from backend.unified_motion import needs_subject_mask
    assert needs_subject_mask(json.dumps([{'template': 'title_through', 'start': 0, 'end': 2, 'title': 'x'}]))
    assert needs_subject_mask(json.dumps([{'template': 'title_emerge', 'start': 0, 'end': 2, 'title': 'x'}]))
