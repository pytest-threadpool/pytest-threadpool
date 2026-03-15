"""Unit tests for MarkerResolver internal logic."""

import sys
import types

from pytest_freethreaded._constants import (
    MARKER_NOT_PARALLELIZABLE,
    MARKER_PARALLELIZABLE,
    SCOPE_NOT,
    ParallelScope,
)
from pytest_freethreaded._markers import MarkerResolver


class FakeMark:
    """Minimal stand-in for a pytest Mark."""

    def __init__(self, name, args=()):
        self.name = name
        self.args = args


class FakeItem:
    """Minimal stand-in for a pytest Item used by MarkerResolver."""

    def __init__(self, own_markers=None, cls=None, module=None):
        self.own_markers = own_markers or []
        self.cls = cls
        self.module = module or types.ModuleType("fake_module")


class TestScopeFromMarks:
    """Tests for MarkerResolver.scope_from_marks."""

    def test_returns_scope_from_parallelizable_mark(self):
        marks = [FakeMark(MARKER_PARALLELIZABLE, ("children",))]
        assert MarkerResolver.scope_from_marks(marks) == "children"

    def test_returns_none_for_empty_marks(self):
        assert MarkerResolver.scope_from_marks([]) is None

    def test_returns_none_for_unrelated_marks(self):
        marks = [FakeMark("skip")]
        assert MarkerResolver.scope_from_marks(marks) is None

    def test_returns_none_for_invalid_scope(self):
        marks = [FakeMark(MARKER_PARALLELIZABLE, ("bogus",))]
        assert MarkerResolver.scope_from_marks(marks) is None

    def test_defaults_to_all_when_no_args(self):
        marks = [FakeMark(MARKER_PARALLELIZABLE)]
        assert MarkerResolver.scope_from_marks(marks) == ParallelScope.ALL

    def test_accepts_single_mark_not_in_list(self):
        mark = FakeMark(MARKER_PARALLELIZABLE, ("parameters",))
        assert MarkerResolver.scope_from_marks(mark) == "parameters"

    def test_first_parallelizable_mark_wins(self):
        marks = [
            FakeMark(MARKER_PARALLELIZABLE, ("children",)),
            FakeMark(MARKER_PARALLELIZABLE, ("parameters",)),
        ]
        assert MarkerResolver.scope_from_marks(marks) == "children"

    def test_all_three_scopes_accepted(self):
        for scope in ("children", "parameters", "all"):
            marks = [FakeMark(MARKER_PARALLELIZABLE, (scope,))]
            assert MarkerResolver.scope_from_marks(marks) == scope


class TestHasNotMarker:
    """Tests for MarkerResolver.has_not_marker."""

    def test_true_when_present(self):
        marks = [FakeMark(MARKER_NOT_PARALLELIZABLE)]
        assert MarkerResolver.has_not_marker(marks) is True

    def test_false_when_absent(self):
        marks = [FakeMark("skip")]
        assert MarkerResolver.has_not_marker(marks) is False

    def test_false_for_empty(self):
        assert MarkerResolver.has_not_marker([]) is False

    def test_accepts_single_mark(self):
        assert MarkerResolver.has_not_marker(FakeMark(MARKER_NOT_PARALLELIZABLE)) is True


class TestOwnScope:
    """Tests for MarkerResolver.own_scope."""

    def test_not_parallelizable_returns_scope_not(self):
        item = FakeItem(own_markers=[FakeMark(MARKER_NOT_PARALLELIZABLE)])
        assert MarkerResolver.own_scope(item) == SCOPE_NOT

    def test_parallelizable_returns_scope(self):
        item = FakeItem(own_markers=[FakeMark(MARKER_PARALLELIZABLE, ("children",))])
        assert MarkerResolver.own_scope(item) == "children"

    def test_no_markers_returns_none(self):
        item = FakeItem(own_markers=[])
        assert MarkerResolver.own_scope(item) is None

    def test_not_parallelizable_takes_priority(self):
        item = FakeItem(
            own_markers=[
                FakeMark(MARKER_NOT_PARALLELIZABLE),
                FakeMark(MARKER_PARALLELIZABLE, ("children",)),
            ]
        )
        assert MarkerResolver.own_scope(item) == SCOPE_NOT

    def test_invalid_scope_returns_none(self):
        item = FakeItem(own_markers=[FakeMark(MARKER_PARALLELIZABLE, ("invalid",))])
        assert MarkerResolver.own_scope(item) is None

    def test_no_args_defaults_to_all(self):
        item = FakeItem(own_markers=[FakeMark(MARKER_PARALLELIZABLE)])
        assert MarkerResolver.own_scope(item) == ParallelScope.ALL


class TestClassScope:
    """Tests for MarkerResolver.class_scope."""

    def test_returns_none_when_no_cls(self):
        item = FakeItem(cls=None)
        assert MarkerResolver.class_scope(item) is None

    def test_reads_scope_from_cls_pytestmark(self):
        cls = type("MyClass", (), {"pytestmark": [FakeMark(MARKER_PARALLELIZABLE, ("children",))]})
        item = FakeItem(cls=cls)
        assert MarkerResolver.class_scope(item) == "children"

    def test_not_parallelizable_on_cls(self):
        cls = type("MyClass", (), {"pytestmark": [FakeMark(MARKER_NOT_PARALLELIZABLE)]})
        item = FakeItem(cls=cls)
        assert MarkerResolver.class_scope(item) == SCOPE_NOT

    def test_no_pytestmark_returns_none(self):
        cls = type("MyClass", (), {})
        item = FakeItem(cls=cls)
        assert MarkerResolver.class_scope(item) is None


class TestModuleScope:
    """Tests for MarkerResolver.module_scope."""

    def test_reads_scope_from_module_pytestmark(self):
        mod = types.ModuleType("test_mod")
        mod.pytestmark = [FakeMark(MARKER_PARALLELIZABLE, ("all",))]
        item = FakeItem(module=mod)
        assert MarkerResolver.module_scope(item) == "all"

    def test_not_parallelizable_on_module(self):
        mod = types.ModuleType("test_mod")
        mod.pytestmark = [FakeMark(MARKER_NOT_PARALLELIZABLE)]
        item = FakeItem(module=mod)
        assert MarkerResolver.module_scope(item) == SCOPE_NOT

    def test_no_pytestmark_returns_none(self):
        mod = types.ModuleType("test_mod")
        item = FakeItem(module=mod)
        assert MarkerResolver.module_scope(item) is None


class TestPackageScope:
    """Tests for MarkerResolver.package_scope."""

    def test_returns_none_when_no_package(self):
        mod = types.ModuleType("test_mod")
        mod.__package__ = None
        item = FakeItem(module=mod)
        assert MarkerResolver.package_scope(item) is None

    def test_returns_none_when_empty_package(self):
        mod = types.ModuleType("test_mod")
        mod.__package__ = ""
        item = FakeItem(module=mod)
        assert MarkerResolver.package_scope(item) is None

    def test_finds_scope_in_package_module(self):
        pkg_mod = types.ModuleType("mypkg")
        pkg_mod.pytestmark = [FakeMark(MARKER_PARALLELIZABLE, ("children",))]
        sys.modules["mypkg"] = pkg_mod
        try:
            mod = types.ModuleType("mypkg.test_mod")
            mod.__package__ = "mypkg"
            item = FakeItem(module=mod)
            assert MarkerResolver.package_scope(item) == "children"
        finally:
            del sys.modules["mypkg"]

    def test_walks_parent_packages(self):
        parent = types.ModuleType("a")
        parent.pytestmark = [FakeMark(MARKER_PARALLELIZABLE, ("all",))]
        child = types.ModuleType("a.b")
        # child has no pytestmark
        sys.modules["a"] = parent
        sys.modules["a.b"] = child
        try:
            mod = types.ModuleType("a.b.test_mod")
            mod.__package__ = "a.b"
            item = FakeItem(module=mod)
            assert MarkerResolver.package_scope(item) == "all"
        finally:
            del sys.modules["a"]
            del sys.modules["a.b"]

    def test_nearest_package_wins(self):
        parent = types.ModuleType("a")
        parent.pytestmark = [FakeMark(MARKER_PARALLELIZABLE, ("all",))]
        child = types.ModuleType("a.b")
        child.pytestmark = [FakeMark(MARKER_PARALLELIZABLE, ("children",))]
        sys.modules["a"] = parent
        sys.modules["a.b"] = child
        try:
            mod = types.ModuleType("a.b.test_mod")
            mod.__package__ = "a.b"
            item = FakeItem(module=mod)
            assert MarkerResolver.package_scope(item) == "children"
        finally:
            del sys.modules["a"]
            del sys.modules["a.b"]

    def test_not_parallelizable_in_package(self):
        pkg_mod = types.ModuleType("pkg")
        pkg_mod.pytestmark = [FakeMark(MARKER_NOT_PARALLELIZABLE)]
        sys.modules["pkg"] = pkg_mod
        try:
            mod = types.ModuleType("pkg.test_mod")
            mod.__package__ = "pkg"
            item = FakeItem(module=mod)
            assert MarkerResolver.package_scope(item) == SCOPE_NOT
        finally:
            del sys.modules["pkg"]

    def test_skips_missing_modules(self):
        """When a package part isn't in sys.modules, it's skipped."""
        parent = types.ModuleType("x")
        parent.pytestmark = [FakeMark(MARKER_PARALLELIZABLE, ("parameters",))]
        sys.modules["x"] = parent
        # "x.y" deliberately not in sys.modules
        try:
            mod = types.ModuleType("x.y.test_mod")
            mod.__package__ = "x.y"
            item = FakeItem(module=mod)
            assert MarkerResolver.package_scope(item) == "parameters"
        finally:
            del sys.modules["x"]


class TestHasPackageParallelOnly:
    """Tests for MarkerResolver.has_package_parallel_only."""

    def test_returns_false_when_no_package(self):
        mod = types.ModuleType("test_mod")
        mod.__package__ = ""
        item = FakeItem(module=mod)
        assert MarkerResolver.has_package_parallel_only(item) is False

    def test_returns_true_when_marker_present(self):
        pkg_mod = types.ModuleType("mypkg")
        pkg_mod.pytestmark = [FakeMark("parallel_only")]
        sys.modules["mypkg"] = pkg_mod
        try:
            mod = types.ModuleType("mypkg.test_mod")
            mod.__package__ = "mypkg"
            item = FakeItem(module=mod)
            assert MarkerResolver.has_package_parallel_only(item) is True
        finally:
            del sys.modules["mypkg"]

    def test_returns_false_when_marker_absent(self):
        pkg_mod = types.ModuleType("mypkg2")
        pkg_mod.pytestmark = [FakeMark(MARKER_PARALLELIZABLE, ("children",))]
        sys.modules["mypkg2"] = pkg_mod
        try:
            mod = types.ModuleType("mypkg2.test_mod")
            mod.__package__ = "mypkg2"
            item = FakeItem(module=mod)
            assert MarkerResolver.has_package_parallel_only(item) is False
        finally:
            del sys.modules["mypkg2"]

    def test_handles_single_mark_not_in_list(self):
        pkg_mod = types.ModuleType("mypkg3")
        pkg_mod.pytestmark = FakeMark("parallel_only")  # not wrapped in list
        sys.modules["mypkg3"] = pkg_mod
        try:
            mod = types.ModuleType("mypkg3.test_mod")
            mod.__package__ = "mypkg3"
            item = FakeItem(module=mod)
            assert MarkerResolver.has_package_parallel_only(item) is True
        finally:
            del sys.modules["mypkg3"]


class TestParametrizeArgnames:
    """Tests for MarkerResolver.parametrize_argnames."""

    def test_single_string_arg(self):
        marker = FakeMark("parametrize", ("x",))
        item = FakeItem()
        item.iter_markers = lambda name: [marker] if name == "parametrize" else []
        assert MarkerResolver.parametrize_argnames(item) == {"x"}

    def test_comma_separated_args(self):
        marker = FakeMark("parametrize", ("a, b, c",))
        item = FakeItem()
        item.iter_markers = lambda name: [marker] if name == "parametrize" else []
        assert MarkerResolver.parametrize_argnames(item) == {"a", "b", "c"}

    def test_list_args(self):
        marker = FakeMark("parametrize", (["x", "y"],))
        item = FakeItem()
        item.iter_markers = lambda name: [marker] if name == "parametrize" else []
        assert MarkerResolver.parametrize_argnames(item) == {"x", "y"}

    def test_tuple_args(self):
        marker = FakeMark("parametrize", (("p", "q"),))
        item = FakeItem()
        item.iter_markers = lambda name: [marker] if name == "parametrize" else []
        assert MarkerResolver.parametrize_argnames(item) == {"p", "q"}

    def test_multiple_parametrize_markers(self):
        m1 = FakeMark("parametrize", ("a",))
        m2 = FakeMark("parametrize", ("b",))
        item = FakeItem()
        item.iter_markers = lambda name: [m1, m2] if name == "parametrize" else []
        assert MarkerResolver.parametrize_argnames(item) == {"a", "b"}

    def test_no_parametrize_markers(self):
        item = FakeItem()
        item.iter_markers = lambda name: []
        assert MarkerResolver.parametrize_argnames(item) == set()


class TestFixtureParamKey:
    """Tests for MarkerResolver.fixture_param_key."""

    def test_no_callspec_returns_empty(self):
        item = FakeItem()
        item.iter_markers = lambda name: []
        assert MarkerResolver.fixture_param_key(item) == ()

    def test_empty_params_returns_empty(self):
        item = FakeItem()
        item.iter_markers = lambda name: []
        item.callspec = types.SimpleNamespace(params={})
        assert MarkerResolver.fixture_param_key(item) == ()

    def test_excludes_parametrize_params(self):
        from _pytest.scope import Scope

        marker = FakeMark("parametrize", ("x",))
        item = FakeItem()
        item.iter_markers = lambda name: [marker] if name == "parametrize" else []
        item.callspec = types.SimpleNamespace(
            params={"x": 1, "fix": "val"},
            _arg2scope={"x": Scope.Function, "fix": Scope.Class},
        )
        assert MarkerResolver.fixture_param_key(item) == (("fix", "val"),)

    def test_excludes_function_scoped_non_parametrize_params(self):
        from _pytest.scope import Scope

        item = FakeItem()
        item.iter_markers = lambda name: []
        item.callspec = types.SimpleNamespace(
            params={"a": 1},
            _arg2scope={"a": Scope.Function},
        )
        assert MarkerResolver.fixture_param_key(item) == ()

    def test_includes_class_scoped_params(self):
        from _pytest.scope import Scope

        item = FakeItem()
        item.iter_markers = lambda name: []
        item.callspec = types.SimpleNamespace(
            params={"fix": "v1"},
            _arg2scope={"fix": Scope.Class},
        )
        assert MarkerResolver.fixture_param_key(item) == (("fix", "v1"),)

    def test_includes_session_scoped_params(self):
        from _pytest.scope import Scope

        item = FakeItem()
        item.iter_markers = lambda name: []
        item.callspec = types.SimpleNamespace(
            params={"s": 42},
            _arg2scope={"s": Scope.Session},
        )
        assert MarkerResolver.fixture_param_key(item) == (("s", 42),)

    def test_missing_arg2scope_defaults_to_function(self):
        """When _arg2scope is missing, params default to Function scope (excluded)."""
        item = FakeItem()
        item.iter_markers = lambda name: []
        item.callspec = types.SimpleNamespace(params={"a": 1})
        # no _arg2scope attribute
        assert MarkerResolver.fixture_param_key(item) == ()
