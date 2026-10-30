import json
import pytest

from backend.artifact_contract import ArtifactRef, ProjectSnapshot, SnapshotAsset, portable_relative_path


def ref():
    return ArtifactRef('a' * 64, 42, 'video/mp4')


def test_roundtrip_is_json_and_contains_no_host_paths():
    snapshot = ProjectSnapshot('p_12345678', 3, ArtifactRef('b' * 64, 700, 'application/json'),
                               (SnapshotAsset('generated/take 01.mp4', ref()),))
    encoded = json.dumps(snapshot.to_dict())
    assert ProjectSnapshot.from_dict(json.loads(encoded)) == snapshot
    assert ref().storage_key == 'sha256/' + 'a' * 64


@pytest.mark.parametrize('path', ['/tmp/x', '../x', 'a/../x', 'a/./x', 'a//x',
    'C:/x', 'C:\\x', '\\\\server\\x', 'a\\b', '', 'a/', 'a\x00b', 'x\nx',
    'NUL', 'con.txt', 'COM1.mp4', 'a/LPT9.wav', 'file.', 'file ', 'a:b', 'x?y'])
def test_reject_nonportable_and_escaping_paths(path):
    with pytest.raises(ValueError):
        portable_relative_path(path)


def test_unicode_relative_filename_is_supported():
    assert portable_relative_path('sources/référence image.png') == 'sources/référence image.png'


@pytest.mark.parametrize('size', [True, -1, 1.0, '42', None])
def test_reject_invalid_size(size):
    with pytest.raises(ValueError):
        ArtifactRef('a' * 64, size)


@pytest.mark.parametrize('digest', ['a' * 63, 'A' * 64, 'g' * 64, '', None])
def test_reject_invalid_hash(digest):
    with pytest.raises(ValueError):
        ArtifactRef(digest, 1)


def test_reject_mime_header_injection():
    with pytest.raises(ValueError):
        ArtifactRef('a' * 64, 1, 'video/mp4\r\nX-Test: value')


@pytest.mark.parametrize('version', [True, 2, '1'])
def test_reject_unknown_or_invalid_schema(version):
    data = ProjectSnapshot('p_12345678', 1, ref()).to_dict()
    data['schema_version'] = version
    with pytest.raises(ValueError):
        ProjectSnapshot.from_dict(data)


@pytest.mark.parametrize('project', ['../project', 'p_12', 'p_' + 'a' * 33, None])
def test_reject_invalid_project(project):
    with pytest.raises(ValueError):
        ProjectSnapshot(project, 1, ref())


@pytest.mark.parametrize('revision', [True, 0, -1, '2'])
def test_reject_invalid_revision(revision):
    with pytest.raises(ValueError):
        ProjectSnapshot('p_12345678', revision, ref())


@pytest.mark.parametrize('paths', [('generated/a.mp4', 'generated/A.mp4'), ('generated', 'generated/a.mp4')])
def test_reject_cross_platform_file_collisions(paths):
    with pytest.raises(ValueError):
        ProjectSnapshot('p_12345678', 1, ref(), tuple(SnapshotAsset(p, ref()) for p in paths))


def test_manifest_cannot_be_overridden_by_asset():
    with pytest.raises(ValueError):
        SnapshotAsset('manifest.json', ref())


def test_unknown_fields_not_silently_dropped():
    data = ref().to_dict()
    data['url'] = 'https://example.com/private-signed-url'
    with pytest.raises(ValueError):
        ArtifactRef.from_dict(data)


def test_empty_asset_list_is_valid_for_metadata_only_snapshot():
    snapshot = ProjectSnapshot('p_12345678', 1, ref())
    assert ProjectSnapshot.from_dict(snapshot.to_dict()) == snapshot


def test_non_list_json_assets_rejected():
    data = ProjectSnapshot('p_12345678', 1, ref()).to_dict()
    data['assets'] = {'relative_path': 'take.mp4'}
    with pytest.raises(ValueError):
        ProjectSnapshot.from_dict(data)
