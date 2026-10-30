import pytest

from backend.remote_connection import RemoteConnection, CapabilityError, require_capabilities


@pytest.mark.parametrize('endpoint', ['http://remote.example','https://user:pass@host','https://host?token=secret',
                                     'https://host#secret','file:///tmp/out','not-a-url'])
def test_remote_rejects_unsafe_endpoints(endpoint):
    with pytest.raises(ValueError):
        RemoteConnection(endpoint,'private-key')


def test_remote_secret_not_in_repr_and_environment_is_child_only():
    connection = RemoteConnection('https://api.example/private','private-key')
    parent = {'COMFY_BASE_URL':'http://127.0.0.1:8189'}
    child = connection.child_environment(parent)
    assert parent['COMFY_BASE_URL'] == 'http://127.0.0.1:8189'
    assert child['COMFY_API_KEY'] == 'private-key'
    assert 'private-key' not in repr(connection)


def test_capabilities_fail_before_gpu_submission():
    capabilities = {'protocol':1,'outputs':'file','operations':['verify','set_prompt'],
                    'isolated_workspace':True,'generation':False}
    assert require_capabilities(capabilities) == capabilities
    with pytest.raises(CapabilityError,match='H3'):
        require_capabilities(capabilities,generation=True)
    with pytest.raises(CapabilityError):
        require_capabilities({**capabilities,'isolated_workspace':False})
    with pytest.raises(CapabilityError):
        require_capabilities({**capabilities,'protocol':True})
