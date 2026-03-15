"""Unit tests for GroupKeyBuilder internal logic."""

import types

from pytest_freethreaded._constants import (
    MARKER_NOT_PARALLELIZABLE,
    MARKER_PARALLELIZABLE,
    _GroupPrefix,
)
from pytest_freethreaded._grouping import GroupKeyBuilder


class FakeMark:
    """Minimal stand-in for a pytest Mark."""

    def __init__(self, name, args=()):
        self.name = name
        self.args = args


def _make_item(
    own_markers=None,
    cls=None,
    cls_marks=None,
    mod_marks=None,
    callspec=None,
    originalname="test_func",
):
    """Build a fake item with the fields GroupKeyBuilder reads."""
    mod = types.ModuleType("fake_mod")
    mod.__package__ = ""
    if mod_marks is not None:
        mod.pytestmark = mod_marks

    if cls is not None and cls_marks is not None:
        cls.pytestmark = cls_marks

    item = types.SimpleNamespace(
        own_markers=own_markers or [],
        cls=cls,
        module=mod,
        originalname=originalname,
        iter_markers=lambda name: [],
    )
    if callspec is not None:
        item.callspec = callspec
    return item


class TestGroupKeySequential:
    """Items without parallelizable markers return None."""

    def test_bare_function_returns_none(self):
        item = _make_item()
        assert GroupKeyBuilder.group_key(item) is None

    def test_own_not_parallelizable_returns_none(self):
        item = _make_item(own_markers=[FakeMark(MARKER_NOT_PARALLELIZABLE)])
        assert GroupKeyBuilder.group_key(item) is None

    def test_class_not_parallelizable_returns_none(self):
        cls = type("C", (), {"pytestmark": [FakeMark(MARKER_NOT_PARALLELIZABLE)]})
        item = _make_item(cls=cls, cls_marks=[FakeMark(MARKER_NOT_PARALLELIZABLE)])
        assert GroupKeyBuilder.group_key(item) is None

    def test_own_not_parallelizable_overrides_class(self):
        cls = type("C", (), {"pytestmark": [FakeMark(MARKER_PARALLELIZABLE, ("children",))]})
        item = _make_item(
            own_markers=[FakeMark(MARKER_NOT_PARALLELIZABLE)],
            cls=cls,
            cls_marks=[FakeMark(MARKER_PARALLELIZABLE, ("children",))],
        )
        assert GroupKeyBuilder.group_key(item) is None


class TestGroupKeyClassChildren:
    """Class-level 'children' scope groups by class."""

    def test_class_children_produces_class_key(self):
        cls = type("C", (), {"pytestmark": [FakeMark(MARKER_PARALLELIZABLE, ("children",))]})
        item = _make_item(cls=cls, cls_marks=[FakeMark(MARKER_PARALLELIZABLE, ("children",))])
        key = GroupKeyBuilder.group_key(item)
        assert key is not None
        assert key[0] == _GroupPrefix.CLASS
        assert key[1] is cls

    def test_class_all_also_produces_class_key(self):
        cls = type("C", (), {"pytestmark": [FakeMark(MARKER_PARALLELIZABLE, ("all",))]})
        item = _make_item(cls=cls, cls_marks=[FakeMark(MARKER_PARALLELIZABLE, ("all",))])
        key = GroupKeyBuilder.group_key(item)
        assert key is not None
        assert key[0] == _GroupPrefix.CLASS


class TestGroupKeyParameters:
    """'parameters' scope groups by test name."""

    def test_own_parameters_with_callspec(self):
        item = _make_item(
            own_markers=[FakeMark(MARKER_PARALLELIZABLE, ("parameters",))],
            callspec=types.SimpleNamespace(params={"x": 1}),
            originalname="test_foo",
        )
        key = GroupKeyBuilder.group_key(item)
        assert key is not None
        assert key[0] == _GroupPrefix.PARAMS
        assert "test_foo" in key

    def test_own_parameters_without_callspec_returns_none(self):
        item = _make_item(own_markers=[FakeMark(MARKER_PARALLELIZABLE, ("parameters",))])
        assert GroupKeyBuilder.group_key(item) is None

    def test_class_parameters_with_callspec(self):
        cls = type("C", (), {"pytestmark": [FakeMark(MARKER_PARALLELIZABLE, ("parameters",))]})
        item = _make_item(
            cls=cls,
            cls_marks=[FakeMark(MARKER_PARALLELIZABLE, ("parameters",))],
            callspec=types.SimpleNamespace(params={"x": 1}),
            originalname="test_bar",
        )
        key = GroupKeyBuilder.group_key(item)
        assert key is not None
        assert key[0] == _GroupPrefix.PARAMS


class TestGroupKeyModuleLevel:
    """Module-level markers produce module or class keys."""

    def test_module_children_bare_function(self):
        item = _make_item(mod_marks=[FakeMark(MARKER_PARALLELIZABLE, ("children",))])
        key = GroupKeyBuilder.group_key(item)
        assert key is not None
        assert key[0] == _GroupPrefix.MOD_CHILDREN

    def test_module_children_with_class(self):
        cls = type("C", (), {})
        item = _make_item(
            cls=cls,
            mod_marks=[
                FakeMark(MARKER_PARALLELIZABLE, ("children",)),
            ],
        )
        key = GroupKeyBuilder.group_key(item)
        assert key is not None
        assert key[0] == _GroupPrefix.CLASS
        assert key[1] is cls

    def test_module_not_parallelizable_skipped(self):
        """Module not_parallelizable doesn't force sequential when own/class set."""
        # module has not_parallelizable but own has parallelizable
        item = _make_item(
            own_markers=[FakeMark(MARKER_PARALLELIZABLE, ("all",))],
            mod_marks=[FakeMark(MARKER_NOT_PARALLELIZABLE)],
        )
        key = GroupKeyBuilder.group_key(item)
        # own takes priority
        assert key is not None


class TestGroupKeyOwnOverrides:
    """Own marker overrides class/module."""

    def test_own_all_overrides_class_children(self):
        cls = type("C", (), {"pytestmark": [FakeMark(MARKER_PARALLELIZABLE, ("children",))]})
        item = _make_item(
            own_markers=[FakeMark(MARKER_PARALLELIZABLE, ("all",))],
            cls=cls,
            cls_marks=[FakeMark(MARKER_PARALLELIZABLE, ("children",))],
            callspec=types.SimpleNamespace(params={"x": 1}),
            originalname="test_x",
        )
        key = GroupKeyBuilder.group_key(item)
        assert key is not None
        # "all" on own produces child_parallel=True, so CLASS key
        assert key[0] == _GroupPrefix.CLASS

    def test_own_parameters_overrides_class_children(self):
        cls = type("C", (), {"pytestmark": [FakeMark(MARKER_PARALLELIZABLE, ("children",))]})
        item = _make_item(
            own_markers=[FakeMark(MARKER_PARALLELIZABLE, ("parameters",))],
            cls=cls,
            cls_marks=[FakeMark(MARKER_PARALLELIZABLE, ("children",))],
            callspec=types.SimpleNamespace(params={"x": 1}),
            originalname="test_x",
        )
        key = GroupKeyBuilder.group_key(item)
        assert key is not None
        assert key[0] == _GroupPrefix.PARAMS


class TestBuildGroups:
    """Tests for GroupKeyBuilder.build_groups."""

    def test_empty_items(self):
        assert GroupKeyBuilder.build_groups([]) == []

    def test_all_sequential(self):
        items = [_make_item() for _ in range(3)]
        groups = GroupKeyBuilder.build_groups(items)
        # Each sequential item gets its own group (key=None, but consecutive Nones merge)
        # Actually: consecutive items with same key merge. All return None.
        assert len(groups) == 1
        assert groups[0][0] is None
        assert len(groups[0][1]) == 3

    def test_parallel_group_formed(self):
        cls = type("C", (), {"pytestmark": [FakeMark(MARKER_PARALLELIZABLE, ("children",))]})
        items = [
            _make_item(cls=cls, cls_marks=[FakeMark(MARKER_PARALLELIZABLE, ("children",))]),
            _make_item(cls=cls, cls_marks=[FakeMark(MARKER_PARALLELIZABLE, ("children",))]),
        ]
        groups = GroupKeyBuilder.build_groups(items)
        assert len(groups) == 1
        assert groups[0][0] is not None
        assert len(groups[0][1]) == 2

    def test_different_classes_split(self):
        cls_a = type("A", (), {"pytestmark": [FakeMark(MARKER_PARALLELIZABLE, ("children",))]})
        cls_b = type("B", (), {"pytestmark": [FakeMark(MARKER_PARALLELIZABLE, ("children",))]})
        items = [
            _make_item(cls=cls_a, cls_marks=[FakeMark(MARKER_PARALLELIZABLE, ("children",))]),
            _make_item(cls=cls_b, cls_marks=[FakeMark(MARKER_PARALLELIZABLE, ("children",))]),
        ]
        groups = GroupKeyBuilder.build_groups(items)
        assert len(groups) == 2

    def test_sequential_between_parallel_splits(self):
        cls = type("C", (), {"pytestmark": [FakeMark(MARKER_PARALLELIZABLE, ("children",))]})
        items = [
            _make_item(cls=cls, cls_marks=[FakeMark(MARKER_PARALLELIZABLE, ("children",))]),
            _make_item(),  # sequential
            _make_item(cls=cls, cls_marks=[FakeMark(MARKER_PARALLELIZABLE, ("children",))]),
        ]
        groups = GroupKeyBuilder.build_groups(items)
        assert len(groups) == 3


class TestIsPackageLevel:
    """Tests for GroupKeyBuilder._is_package_level."""

    def test_own_set_returns_false(self):
        assert GroupKeyBuilder._is_package_level(None, "children", None, None, "children") is False

    def test_cls_set_returns_false(self):
        item = types.SimpleNamespace(cls=type("C", (), {}))
        assert GroupKeyBuilder._is_package_level(item, None, "children", None, "children") is False

    def test_mod_set_returns_false(self):
        item = types.SimpleNamespace(cls=None)
        assert GroupKeyBuilder._is_package_level(item, None, None, "children", "children") is False

    def test_mod_not_returns_true_when_pkg_children(self):
        item = types.SimpleNamespace(cls=None)
        assert GroupKeyBuilder._is_package_level(item, None, None, "not", "children") is True

    def test_pkg_children_returns_true(self):
        item = types.SimpleNamespace(cls=None)
        assert GroupKeyBuilder._is_package_level(item, None, None, None, "children") is True

    def test_pkg_all_returns_true(self):
        item = types.SimpleNamespace(cls=None)
        assert GroupKeyBuilder._is_package_level(item, None, None, None, "all") is True

    def test_pkg_parameters_returns_false(self):
        item = types.SimpleNamespace(cls=None)
        assert GroupKeyBuilder._is_package_level(item, None, None, None, "parameters") is False

    def test_pkg_none_returns_false(self):
        item = types.SimpleNamespace(cls=None)
        assert GroupKeyBuilder._is_package_level(item, None, None, None, None) is False
