from backend.config import _studio_env
from backend.brand import NAME, EXPORT_PREFIX

def test_hyperkut_environment_keeps_legacy_and_prefers_new_names(monkeypatch):
    monkeypatch.delenv('HYPERKUT_OUTPUT_DIR', raising=False)
    monkeypatch.setenv('SECATOR_OUTPUT_DIR', '/previous/output')
    assert _studio_env('OUTPUT_DIR') == '/previous/output'
    monkeypatch.setenv('HYPERKUT_OUTPUT_DIR', '/new/output')
    assert _studio_env('OUTPUT_DIR') == '/new/output'
    assert NAME == 'HyperKut' and EXPORT_PREFIX == 'hyperkut'
