"""Test all fixture scopes and styles with the threaded runner."""

import threading
import time

import pytest

# ── tracking state shared across the module ──────────────────────────────
_session_setup_count = 0
_session_lock = threading.Lock()

_module_setup_count = 0
_module_lock = threading.Lock()


# ── session-scoped fixture ───────────────────────────────────────────────
@pytest.fixture(scope="session")
def session_resource():
    global _session_setup_count
    with _session_lock:
        _session_setup_count += 1
    return {"created_by": "session_resource", "call_count": _session_setup_count}


# ── module-scoped fixture ───────────────────────────────────────────────
@pytest.fixture(scope="module")
def module_resource():
    global _module_setup_count
    with _module_lock:
        _module_setup_count += 1
    return {"created_by": "module_resource", "call_count": _module_setup_count}


# ── class-scoped yield fixture ───────────────────────────────────────────
@pytest.mark.parallelizable("children")
class TestClassScopedYieldFixture:
    """Class-scoped yield fixture: setup once, teardown after all methods."""

    setup_teardown_log = []
    log_lock = threading.Lock()

    @pytest.fixture(autouse=True, scope="class")
    def db_connection(self):
        with self.log_lock:
            self.setup_teardown_log.append("setup")
        yield "fake_db_conn"
        with self.log_lock:
            self.setup_teardown_log.append("teardown")

    def test_a(self):
        time.sleep(0.1)
        assert any(x == "setup" for x in self.setup_teardown_log)

    def test_b(self):
        time.sleep(0.1)
        assert any(x == "setup" for x in self.setup_teardown_log)

    def test_c(self):
        time.sleep(0.1)
        assert any(x == "setup" for x in self.setup_teardown_log)


@pytest.mark.parallel_only
@pytest.mark.parallelizable("children")
class TestClassScopedYieldFixtureVerify:
    """Verify class-scoped fixture is set up exactly once (parallel only)."""

    setup_count = []
    log_lock = threading.Lock()
    barrier = threading.Barrier(3, timeout=10)

    @pytest.fixture(autouse=True, scope="class")
    def db_connection(self):
        with self.log_lock:
            self.setup_count.append(1)
        yield

    def test_a(self):
        self.barrier.wait()
        assert len(self.setup_count) == 1

    def test_b(self):
        self.barrier.wait()

    def test_c(self):
        self.barrier.wait()


# ── autouse fixture at class scope with state ────────────────────────────
@pytest.mark.parallelizable("children")
class TestAutouseClassFixtureState:
    """Autouse class fixture that provides shared state to all methods."""

    shared_list = []
    list_lock = threading.Lock()

    @pytest.fixture(autouse=True, scope="class")
    def init_shared(self):
        self.shared_list.clear()
        self.shared_list.append("initialized")
        yield
        self.shared_list.append("finalized")

    def test_write_1(self):
        with self.list_lock:
            self.shared_list.append("w1")
        assert "initialized" in self.shared_list

    def test_write_2(self):
        with self.list_lock:
            self.shared_list.append("w2")
        assert "initialized" in self.shared_list


# ── parameterized fixture ────────────────────────────────────────────────
@pytest.mark.parallelizable("children")
class TestParameterizedFixture:
    """Parameterized class-scoped fixture expands into multiple test runs."""

    @pytest.fixture(params=["alpha", "beta", "gamma"], scope="class", autouse=True)
    def variant(self, request):
        return request.param

    def test_param_is_str(self, variant):
        assert isinstance(variant, str)

    def test_param_in_set(self, variant):
        assert variant in {"alpha", "beta", "gamma"}


# ── multiple fixtures composed ───────────────────────────────────────────
@pytest.mark.parallelizable("children")
class TestMultipleFixtures:
    """Combine session, module, and class fixtures in one test class."""

    @pytest.fixture(autouse=True, scope="class")
    def class_tag(self):
        return "class_level"

    def test_session_fixture(self, session_resource):
        assert session_resource["created_by"] == "session_resource"

    def test_module_fixture(self, module_resource):
        assert module_resource["created_by"] == "module_resource"

    def test_both(self, session_resource, module_resource):
        assert session_resource["call_count"] >= 1
        assert module_resource["call_count"] >= 1


# ── yield fixture with cleanup verification ──────────────────────────────
@pytest.mark.parallelizable("children")
class TestYieldFixtureCleanup:
    """Verify that yield fixture teardown actually runs."""

    cleanup_flag = {"cleaned": False}

    @pytest.fixture(autouse=True, scope="class")
    def resource_with_cleanup(self):
        self.cleanup_flag["cleaned"] = False
        yield "resource"
        self.cleanup_flag["cleaned"] = True

    def test_use_resource_a(self):
        assert not self.cleanup_flag["cleaned"]

    def test_use_resource_b(self):
        assert not self.cleanup_flag["cleaned"]


# ── function-scoped fixture (per-test) ───────────────────────────────────
@pytest.mark.parallelizable("children")
class TestFunctionScopedFixture:
    """Function-scoped fixtures get fresh values per test."""

    call_log = []
    log_lock = threading.Lock()

    @pytest.fixture(autouse=True)
    def per_test_counter(self):
        with self.log_lock:
            idx = len(self.call_log)
            self.call_log.append(f"setup_{idx}")
        yield idx
        with self.log_lock:
            self.call_log.append(f"teardown_{idx}")

    def test_a(self, per_test_counter):
        assert isinstance(per_test_counter, int)

    def test_b(self, per_test_counter):
        assert isinstance(per_test_counter, int)

    def test_c(self, per_test_counter):
        assert isinstance(per_test_counter, int)


def test_function_scoped_setups_all_ran():
    """Verify all 3 function-scoped fixtures were set up (runs after class)."""
    setups = [x for x in TestFunctionScopedFixture.call_log if x.startswith("setup_")]
    assert len(setups) == 3, f"expected 3 setups, got {setups}"
