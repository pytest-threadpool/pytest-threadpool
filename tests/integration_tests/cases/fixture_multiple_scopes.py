"""Session + module + class fixtures compose correctly."""

import pytest

from pytest_threadpool import parallelizable


@pytest.fixture(scope="session")
def session_res():
    return {"from": "session"}


@pytest.fixture(scope="module")
def module_res():
    return {"from": "module"}


@parallelizable("children")
class TestCompose:
    def test_session(self, session_res):
        assert session_res["from"] == "session"

    def test_module(self, module_res):
        assert module_res["from"] == "module"

    def test_both(self, session_res, module_res):
        assert session_res
        assert module_res
