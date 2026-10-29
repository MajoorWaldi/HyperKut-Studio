import importlib.util
from pathlib import Path

import pytest


def module():
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'planner_eval.py'
    spec = importlib.util.spec_from_file_location('bounded_planner_eval', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Response:
    def __init__(self, data): self.data = data
    def raise_for_status(self): pass
    def json(self): return self.data


def test_incomplete_history_does_not_count_as_completed(monkeypatch):
    mod = module()
    monkeypatch.setattr(mod.time, 'sleep', lambda _: None)
    data = iter([{'own': {'status': {'completed': False}}},
                 {'own': {'status': {'completed': True}, 'outputs': {'raw': {'text': ['{"shots":[]}']}}}}])
    class Client:
        def get(self, url): return Response(next(data))
    assert mod.wait_plan(Client(), 'http://local', 'own', 10) == '{"shots":[]}'


def test_timeout_interrupts_only_owned_prompt():
    mod = module()
    calls = []
    class Client:
        def post(self, url, json):
            calls.append((url, json)); return Response({})
    with pytest.raises(TimeoutError): mod.wait_plan(Client(), 'http://local', 'own', 0)
    assert calls == [('http://local/queue', {'delete': ['own']}), ('http://local/interrupt', {'prompt_id': 'own'})]


def test_failed_planner_is_not_parsed_as_success():
    mod = module()
    class Client:
        def get(self, url): return Response({'own': {'status': {'completed': False, 'status_str': 'error'}}})
        def post(self, url, json): return Response({})
    with pytest.raises(RuntimeError, match='Planner failed'):
        mod.wait_plan(Client(), 'http://local', 'own', 10)
