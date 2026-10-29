import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def pytest_addoption(parser):
    parser.addoption('--real',action='store_true',default=False,help='Allow local real GPU jobs')


def pytest_collection_modifyitems(config,items):
    import pytest
    if not config.getoption('--real'):
        skip=pytest.mark.skip(reason='Real GPU tests require --real')
        for item in items:
            if 'real' in item.keywords:item.add_marker(skip)
