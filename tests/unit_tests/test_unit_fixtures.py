"""Unit tests for FixtureManager internal logic."""

import types

from _pytest.scope import Scope

from pytest_freethreaded._fixtures import FixtureManager


class FakeFixtureDef:
    """Minimal stand-in for _pytest.fixtures.FixtureDef."""

    def __init__(self, scope, finalizers=None, cached_result=None):
        self._scope = scope
        self._finalizers = list(finalizers or [])
        self.cached_result = cached_result


class TestSaveAndClearFunctionFixtures:
    """Tests for FixtureManager.save_and_clear_function_fixtures."""

    def test_no_request_returns_empty(self):
        item = types.SimpleNamespace()
        assert FixtureManager.save_and_clear_function_fixtures(item) == []

    def test_no_fixture_defs_returns_empty(self):
        item = types.SimpleNamespace(_request=types.SimpleNamespace())
        assert FixtureManager.save_and_clear_function_fixtures(item) == []

    def test_saves_function_scoped_finalizers(self):
        def fin1():
            return None

        def fin2():
            return None

        fd = FakeFixtureDef(Scope.Function, finalizers=[fin1, fin2], cached_result=("val",))
        request = types.SimpleNamespace(_fixture_defs={"fix": fd})
        item = types.SimpleNamespace(_request=request)

        saved = FixtureManager.save_and_clear_function_fixtures(item)
        assert saved == [fin1, fin2]
        assert fd._finalizers == []
        assert fd.cached_result is None

    def test_ignores_class_scoped_fixtures(self):
        fd = FakeFixtureDef(Scope.Class, finalizers=[lambda: None], cached_result=("val",))
        request = types.SimpleNamespace(_fixture_defs={"fix": fd})
        item = types.SimpleNamespace(_request=request)

        saved = FixtureManager.save_and_clear_function_fixtures(item)
        assert saved == []
        assert len(fd._finalizers) == 1
        assert fd.cached_result is not None

    def test_ignores_session_scoped_fixtures(self):
        fd = FakeFixtureDef(Scope.Session, finalizers=[lambda: None])
        request = types.SimpleNamespace(_fixture_defs={"fix": fd})
        item = types.SimpleNamespace(_request=request)

        saved = FixtureManager.save_and_clear_function_fixtures(item)
        assert saved == []

    def test_multiple_fixtures_mixed_scopes(self):
        def fin_func():
            return None

        fd_func = FakeFixtureDef(Scope.Function, finalizers=[fin_func], cached_result=("a",))
        fd_cls = FakeFixtureDef(Scope.Class, finalizers=[lambda: None], cached_result=("b",))
        fd_mod = FakeFixtureDef(Scope.Module, finalizers=[lambda: None])

        request = types.SimpleNamespace(_fixture_defs={"f": fd_func, "c": fd_cls, "m": fd_mod})
        item = types.SimpleNamespace(_request=request)

        saved = FixtureManager.save_and_clear_function_fixtures(item)
        assert saved == [fin_func]
        assert fd_func.cached_result is None
        assert fd_cls.cached_result is not None


class TestClearFunctionFixtureCaches:
    """Tests for FixtureManager.clear_function_fixture_caches."""

    def test_no_request_does_nothing(self):
        item = types.SimpleNamespace()
        FixtureManager.clear_function_fixture_caches(item)  # no error

    def test_clears_function_scoped_cached_results(self):
        fd = FakeFixtureDef(Scope.Function, cached_result=("val",))
        request = types.SimpleNamespace(_arg2fixturedefs={"fix": [fd]})
        item = types.SimpleNamespace(_request=request)

        FixtureManager.clear_function_fixture_caches(item)
        assert fd.cached_result is None

    def test_preserves_class_scoped_cached_results(self):
        fd = FakeFixtureDef(Scope.Class, cached_result=("val",))
        request = types.SimpleNamespace(_arg2fixturedefs={"fix": [fd]})
        item = types.SimpleNamespace(_request=request)

        FixtureManager.clear_function_fixture_caches(item)
        assert fd.cached_result == ("val",)

    def test_skips_already_none_caches(self):
        fd = FakeFixtureDef(Scope.Function, cached_result=None)
        request = types.SimpleNamespace(_arg2fixturedefs={"fix": [fd]})
        item = types.SimpleNamespace(_request=request)

        FixtureManager.clear_function_fixture_caches(item)
        assert fd.cached_result is None

    def test_multiple_fixturedefs_per_arg(self):
        fd1 = FakeFixtureDef(Scope.Function, cached_result=("a",))
        fd2 = FakeFixtureDef(Scope.Function, cached_result=("b",))
        request = types.SimpleNamespace(_arg2fixturedefs={"fix": [fd1, fd2]})
        item = types.SimpleNamespace(_request=request)

        FixtureManager.clear_function_fixture_caches(item)
        assert fd1.cached_result is None
        assert fd2.cached_result is None


class _Node:
    """Hashable fake node for setup state stack."""

    def __init__(self, name):
        self.name = name


class TestSaveCollectorFinalizers:
    """Tests for FixtureManager.save_collector_finalizers."""

    def test_saves_finalizers_for_unneeded_nodes(self):
        node_a = _Node("a")
        node_b = _Node("b")
        node_c = _Node("c")

        fin_a = [lambda: None]
        fin_b = [lambda: None, lambda: None]

        # Ordered dict to preserve insertion order
        stack = {
            node_a: (list(fin_a), None),
            node_b: (list(fin_b), None),
            node_c: ([], None),
        }

        session = types.SimpleNamespace(_setupstate=types.SimpleNamespace(stack=stack))

        # next_item needs node_c but not node_a or node_b
        class FakeItem:
            def listchain(self):
                return [node_c]

        next_item = FakeItem()

        saved = FixtureManager.save_collector_finalizers(session, next_item)
        assert len(saved) == 2
        assert saved[0][0] is node_a
        assert len(saved[0][1]) == 1
        assert saved[1][0] is node_b
        assert len(saved[1][1]) == 2
        # Original lists should be cleared
        assert stack[node_a][0] == []
        assert stack[node_b][0] == []

    def test_needed_nodes_not_saved(self):
        node_a = _Node("a")

        stack = {node_a: ([lambda: None], None)}
        session = types.SimpleNamespace(_setupstate=types.SimpleNamespace(stack=stack))

        class FakeItem:
            def listchain(self):
                return [node_a]

        next_item = FakeItem()

        saved = FixtureManager.save_collector_finalizers(session, next_item)
        assert saved == []
        assert len(stack[node_a][0]) == 1  # not cleared
