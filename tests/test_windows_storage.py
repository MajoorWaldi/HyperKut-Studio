import os
import threading
import time

import pytest

from backend.storage import write_json


@pytest.mark.skipif(os.name!='nt',reason='Windows replacement sharing semantics')
def test_state_write_survives_a_temporary_reader_lock(tmp_path):
    path=tmp_path/'state.json';write_json(path,{'version':1})
    opened=threading.Event()
    def reader():
        with path.open('r') as handle:
            opened.set();time.sleep(2.2)
            assert handle.read()
    thread=threading.Thread(target=reader);thread.start();assert opened.wait(2)
    try:write_json(path,{'version':2})
    finally:thread.join()
    assert '2' in path.read_text()
