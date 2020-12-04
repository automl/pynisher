import pytest
from unittest.mock import Mock
import psutil


class PickableMock(Mock):
    def __reduce__(self):
        return (Mock, ())


@pytest.fixture
def logger_mock():
    return PickableMock()


def pytest_sessionfinish(session, exitstatus):
    proc = psutil.Process()
    for child in proc.children(recursive=True):
        print(child, child.cmdline())
