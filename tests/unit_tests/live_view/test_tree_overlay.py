"""Unit tests for the tree overlay (ItemTree + TreeOverlay)."""

from __future__ import annotations

from pytest_threadpool._live_view._tree_overlay import ItemTree, TreeOverlay

SAMPLE_NODEIDS = [
    "tests/test_foo.py::TestAlpha::test_one",
    "tests/test_foo.py::TestAlpha::test_two",
    "tests/test_foo.py::TestBeta::test_three",
    "tests/test_bar.py::test_standalone",
    "tests/sub/test_deep.py::TestDeep::test_a[param0]",
    "tests/sub/test_deep.py::TestDeep::test_a[param1]",
]


class TestItemTree:
    """ItemTree builds a hierarchy from pytest nodeids."""

    def test_root_has_children(self):
        tree = ItemTree(SAMPLE_NODEIDS)
        assert tree.root.label == "session"
        assert len(tree.root.children) > 0

    def test_top_level_is_package(self):
        tree = ItemTree(SAMPLE_NODEIDS)
        labels = [c.label for c in tree.root.children]
        assert "tests" in labels

    def test_files_are_grouped(self):
        tree = ItemTree(SAMPLE_NODEIDS)
        tests_node = tree.root.children[0]  # "tests"
        child_labels = [c.label for c in tests_node.children]
        assert "test_foo.py" in child_labels
        assert "test_bar.py" in child_labels

    def test_classes_appear_under_file(self):
        tree = ItemTree(SAMPLE_NODEIDS)
        # tests > test_foo.py
        tests_node = tree.root.children[0]
        foo_node = next(c for c in tests_node.children if c.label == "test_foo.py")
        class_labels = [c.label for c in foo_node.children]
        assert "TestAlpha" in class_labels
        assert "TestBeta" in class_labels

    def test_methods_are_leaves(self):
        tree = ItemTree(SAMPLE_NODEIDS)
        tests_node = tree.root.children[0]
        foo_node = next(c for c in tests_node.children if c.label == "test_foo.py")
        alpha = next(c for c in foo_node.children if c.label == "TestAlpha")
        assert len(alpha.children) == 2
        assert all(c.is_leaf for c in alpha.children)

    def test_leaf_has_nodeid(self):
        tree = ItemTree(SAMPLE_NODEIDS)
        flat = tree.flat_visible()
        leaves = [n for n in flat if n.is_leaf]
        assert any(n.nodeid == "tests/test_foo.py::TestAlpha::test_one" for n in leaves)

    def test_flat_visible_includes_all_when_expanded(self):
        tree = ItemTree(SAMPLE_NODEIDS)
        flat = tree.flat_visible()
        # Should include: tests, test_foo.py, TestAlpha, test_one, test_two,
        # TestBeta, test_three, test_bar.py, test_standalone,
        # sub, test_deep.py, TestDeep, test_a[param0], test_a[param1]
        labels = [n.label for n in flat]
        assert "test_one" in labels
        assert "test_standalone" in labels
        assert "test_a[param0]" in labels

    def test_collapse_hides_children(self):
        tree = ItemTree(SAMPLE_NODEIDS)
        tests_node = tree.root.children[0]
        tests_node.expanded = False
        flat = tree.flat_visible()
        # Only "tests" should be visible, everything else hidden.
        assert len(flat) == 1
        assert flat[0].label == "tests"

    def test_parametrized_items_grouped(self):
        tree = ItemTree(SAMPLE_NODEIDS)
        flat = tree.flat_visible()
        param_labels = [n.label for n in flat if "param" in n.label]
        assert "test_a[param0]" in param_labels
        assert "test_a[param1]" in param_labels


class ItemTreeOverlay:
    """TreeOverlay handles navigation and rendering."""

    def _make_overlay(self, height: int = 20, width: int = 80) -> TreeOverlay:
        tree = ItemTree(SAMPLE_NODEIDS)
        return TreeOverlay(tree, width, height)

    def test_initial_cursor_at_zero(self):
        ov = self._make_overlay()
        assert ov._cursor == 0

    def test_escape_returns_close(self):
        ov = self._make_overlay()
        assert ov.handle_key("Escape") == "close"

    def test_tab_returns_close(self):
        ov = self._make_overlay()
        assert ov.handle_key("Tab") == "close"

    def test_down_moves_cursor(self):
        ov = self._make_overlay()
        ov.handle_key("Down")
        assert ov._cursor == 1

    def test_up_at_zero_stays(self):
        ov = self._make_overlay()
        ov.handle_key("Up")
        assert ov._cursor == 0

    def test_enter_on_summary_returns_close(self):
        ov = self._make_overlay()
        # First node (index 0) is the Summary node.
        assert ov._visible[0].label == "Summary"
        assert ov.handle_key("Enter") == "close"

    def test_enter_on_branch_toggles(self):
        ov = self._make_overlay()
        # Index 1 is "tests" (a branch).
        ov.handle_key("Down")
        node = ov._visible[ov._cursor]
        assert not node.is_leaf
        was_expanded = node.expanded
        ov.handle_key("Enter")
        assert node.expanded != was_expanded

    def test_enter_on_leaf_returns_jump(self):
        ov = self._make_overlay()
        # Navigate to a leaf node.
        for _i in range(20):
            if ov._cursor < len(ov._visible) and ov._visible[ov._cursor].is_leaf:
                break
            ov.handle_key("Down")
        result = ov.handle_key("Enter")
        assert result is not None
        assert result.startswith("jump:")

    def test_right_expands_collapsed(self):
        ov = self._make_overlay()
        # Move to branch node (index 1).
        ov.handle_key("Down")
        node = ov._visible[ov._cursor]
        node.expanded = False
        ov._rebuild()
        ov._cursor = 1
        ov.handle_key("Right")
        assert node.expanded

    def test_left_collapses_expanded(self):
        ov = self._make_overlay()
        # Move to branch node (index 1).
        ov.handle_key("Down")
        node = ov._visible[ov._cursor]
        assert node.expanded
        ov.handle_key("Left")
        assert not node.expanded

    def test_left_on_leaf_collapses_parent(self):
        ov = self._make_overlay()
        # Navigate to a leaf.
        for _i in range(20):
            if ov._cursor < len(ov._visible) and ov._visible[ov._cursor].is_leaf:
                break
            ov.handle_key("Down")
        leaf_depth = ov._visible[ov._cursor].depth
        ov.handle_key("Left")
        # Cursor should move to the parent (lower depth).
        assert ov._visible[ov._cursor].depth < leaf_depth

    def test_render_returns_correct_height(self):
        ov = self._make_overlay(height=10)
        lines = ov.render()
        assert len(lines) == 10

    def test_render_first_line_is_title(self):
        ov = self._make_overlay()
        lines = ov.render()
        assert "Test Tree" in lines[0]

    def test_page_down_moves_by_page(self):
        ov = self._make_overlay(height=5)
        ov.handle_key("PageDown")
        # Should move by height - 2 = 3.
        assert ov._cursor == 3

    def test_home_goes_to_top(self):
        ov = self._make_overlay()
        ov.handle_key("End")
        ov.handle_key("Home")
        assert ov._cursor == 0

    def test_end_goes_to_bottom(self):
        ov = self._make_overlay()
        ov.handle_key("End")
        assert ov._cursor == len(ov._visible) - 1
