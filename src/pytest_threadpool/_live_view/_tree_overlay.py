"""Modal tree-view overlay for browsing test items.

Displays the test session hierarchy as a collapsible tree:
session > packages > modules > classes > tests > parameters.

Triggered by Tab, dismissed by Escape/Tab, navigate with arrows,
toggle expand/collapse with Enter or Right/Left.
"""

from __future__ import annotations

import dataclasses

from pytest_threadpool._live_view._ansi import pad_line

# ANSI style codes
_DIM = "\033[2m"
_BOLD = "\033[1m"
_CYAN = "\033[36m"
_YELLOW = "\033[33m"
_REVERSE = "\033[7m"
_RESET = "\033[0m"
_UNDERLINE = "\033[4m"
_GREEN = "\033[32m"
_RED_BOLD = "\033[31;1m"

# Outcome markers shown next to leaf nodes in the tree.
_OUTCOME_MARKER: dict[str, str] = {
    "passed": f" {_GREEN}\u2713{_RESET}",
    "failed": f" {_RED_BOLD}\u2717{_RESET}",
    "error": f" {_RED_BOLD}E{_RESET}",
    "skipped": f" {_YELLOW}s{_RESET}",
    "xfail": f" {_YELLOW}x{_RESET}",
    "xpass": f" {_RED_BOLD}X{_RESET}",
}

# Tree drawing characters
_BRANCH = "\u251c\u2500 "  # ├─
_LAST = "\u2514\u2500 "  # └─
_PIPE = "\u2502  "  # │
_SPACE = "   "
_EXPANDED = "\u25bc "  # ▼
_COLLAPSED = "\u25b6 "  # ▶


@dataclasses.dataclass
class TreeNode:
    """A node in the test item tree."""

    label: str
    children: list[TreeNode] = dataclasses.field(default_factory=list)
    expanded: bool = True
    depth: int = 0
    nodeid: str = ""
    # Row in the ScreenBuffer that this node's output starts at.
    buffer_row: int = -1

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0


def _fuzzy_match(query: str, text: str) -> bool:
    """fzf-style subsequence match: each query char appears in order."""
    qi = 0
    for ch in text:
        if qi < len(query) and ch == query[qi]:
            qi += 1
    return qi == len(query)


def _has_matching_descendant(node: TreeNode, query: str) -> bool:
    """Check if any descendant's label fuzzy-matches the query."""
    for child in node.children:
        if _fuzzy_match(query, child.label.lower()):
            return True
        if not child.is_leaf and _has_matching_descendant(child, query):
            return True
    return False


class ItemTree:
    """Builds a tree from pytest item nodeids.

    The hierarchy is derived by splitting nodeids on ``::`` and
    grouping common prefixes.  File paths are further split on ``/``
    to create package nodes.
    """

    def __init__(self, nodeids: list[str]) -> None:
        self.root = TreeNode(label="session", depth=0)
        self._build(nodeids)

    def _build(self, nodeids: list[str]) -> None:
        for nid in nodeids:
            # Split "tests/pkg/test_foo.py::TestClass::test_method[param]"
            # into path part and test parts.
            parts: list[str]
            if "::" in nid:
                file_part, rest = nid.split("::", 1)
                parts = file_part.split("/") + rest.split("::")
            else:
                parts = nid.split("/")
            self._insert(self.root, parts, nid)

    def _insert(self, parent: TreeNode, parts: list[str], nodeid: str) -> None:
        if not parts:
            return
        label = parts[0]
        remaining = parts[1:]
        # Find existing child with this label.
        child = None
        for c in parent.children:
            if c.label == label:
                child = c
                break
        if child is None:
            child = TreeNode(
                label=label,
                depth=parent.depth + 1,
                nodeid=nodeid if not remaining else "",
            )
            parent.children.append(child)
        if remaining:
            self._insert(child, remaining, nodeid)
        elif not child.nodeid:
            child.nodeid = nodeid

    def flat_visible(self) -> list[TreeNode]:
        """Return a flattened list of visible nodes (respecting expanded)."""
        result: list[TreeNode] = []
        # Skip the root "session" node itself — show its children.
        for child in self.root.children:
            self._flatten(child, result)
        return result

    def _flatten(self, node: TreeNode, out: list[TreeNode]) -> None:
        out.append(node)
        if node.expanded:
            for child in node.children:
                self._flatten(child, out)


class TreeOverlay:
    """Modal overlay showing the test tree with cursor navigation."""

    def __init__(
        self,
        tree: ItemTree,
        width: int,
        height: int,
        *,
        pane_width: int | None = None,
        outcomes: dict[str, str] | None = None,
    ) -> None:
        self._tree = tree
        self._width = pane_width if pane_width is not None else width
        self._height = height
        self._cursor = 0
        self._scroll = 0
        self._outcomes = outcomes or {}
        # "Summary" is a virtual top-level node that returns the user
        # to the default content view when activated.
        self._summary_node = TreeNode(label="Summary", depth=0, nodeid="")
        self._query = ""
        self._show_passed = True
        self._show_failed = True
        self._visible = self._build_visible()

    def scroll(self, delta: int) -> None:
        """Scroll the tree cursor by *delta* lines (positive = down)."""
        max_idx = len(self._visible) - 1
        self._cursor = max(0, min(self._cursor + delta, max_idx))
        self._ensure_visible()

    def handle_key(self, key: str) -> str | None:
        """Process a key press.

        Returns:
            ``"close"`` — dismiss the overlay.
            ``"jump:<nodeid>"`` — dismiss and jump to the given nodeid.
            ``None`` — stay in the overlay (handled internally).
        """
        if key == "Tab":
            return "close"
        if key == "Escape":
            if self._query:
                self._query = ""
                self._rebuild()
            else:
                return "close"
        elif key == "Backspace":
            if self._query:
                self._query = self._query[:-1]
                self._rebuild()
        elif key == "Up":
            self._cursor = max(0, self._cursor - 1)
            self._ensure_visible()
        elif key == "Down":
            self._cursor = min(len(self._visible) - 1, self._cursor + 1)
            self._ensure_visible()
        elif key == "PageUp":
            self._cursor = max(0, self._cursor - (self._height - 3))
            self._ensure_visible()
        elif key == "PageDown":
            self._cursor = min(len(self._visible) - 1, self._cursor + (self._height - 3))
            self._ensure_visible()
        elif key == "Home":
            self._cursor = 0
            self._ensure_visible()
        elif key == "End":
            self._cursor = max(0, len(self._visible) - 1)
            self._ensure_visible()
        elif key == "Right":
            self._expand_current()
        elif key == "Left":
            self._collapse_current()
        elif key == "Enter":
            return self._activate_current()
        elif key == "Ctrl+p":
            self._show_passed = not self._show_passed
            self._rebuild()
        elif key == "Ctrl+x":
            self._show_failed = not self._show_failed
            self._rebuild()
        elif len(key) == 1 and key.isprintable():
            self._query += key
            self._rebuild()
        return None

    def _expand_current(self) -> None:
        """Expand the node under the cursor."""
        if self._cursor < len(self._visible):
            node = self._visible[self._cursor]
            if not node.is_leaf and not node.expanded:
                node.expanded = True
                self._rebuild()

    def _collapse_current(self) -> None:
        """Collapse the node under the cursor."""
        if self._cursor < len(self._visible):
            node = self._visible[self._cursor]
            if not node.is_leaf and node.expanded:
                node.expanded = False
                self._rebuild()
            elif node.is_leaf:
                # Collapse parent instead.
                self._collapse_parent(node)

    def _collapse_parent(self, node: TreeNode) -> None:
        """Walk backwards from cursor to find and collapse nearest ancestor."""
        for i in range(self._cursor - 1, -1, -1):
            n = self._visible[i]
            if not n.is_leaf and n.expanded and n.depth < node.depth:
                n.expanded = False
                self._cursor = i
                self._rebuild()
                return

    def _activate_current(self) -> str | None:
        """Select current node — show its output in the content pane.

        Leaves jump to a single test.  Branches jump to a group
        (all descendant tests).  Summary returns to the main view.
        Expand/collapse is handled by Left/Right, not Enter.
        """
        if self._cursor >= len(self._visible):
            return None
        node = self._visible[self._cursor]
        if node is self._summary_node:
            return "close"
        if node.is_leaf:
            if node.nodeid:
                return f"jump:{node.nodeid}"
            return "close"
        # Branch — collect all descendant leaf nodeids.
        nodeids = self._collect_leaves(node)
        if nodeids:
            return "jumpgroup:" + "\t".join(nodeids)
        return None

    _FAIL_OUTCOMES = frozenset({"failed", "error", "xpass"})

    def _group_outcome(self, node: TreeNode) -> str:
        """Aggregate outcome for a branch: failed if any fail, passed if all done."""
        leaves = self._collect_leaves(node)
        if not leaves:
            return ""
        outcomes = [self._outcomes.get(nid, "") for nid in leaves]
        if any(o in self._FAIL_OUTCOMES for o in outcomes):
            return "failed"
        if all(o for o in outcomes):
            # All have an outcome (none still running).
            return "passed"
        return ""

    @staticmethod
    def _collect_leaves(node: TreeNode) -> list[str]:
        """Recursively collect all leaf nodeids under a branch."""
        result: list[str] = []
        for child in node.children:
            if child.is_leaf and child.nodeid:
                result.append(child.nodeid)
            else:
                result.extend(TreeOverlay._collect_leaves(child))
        return result

    def _is_hidden(self, node: TreeNode) -> bool:
        """Check if a leaf node should be hidden by outcome filters."""
        if not node.is_leaf or not node.nodeid:
            return False
        outcome = self._outcomes.get(node.nodeid, "")
        if not outcome:
            return False  # still running — always show
        if not self._show_passed and outcome in ("passed", "xfail"):
            return True
        return not self._show_failed and outcome in ("failed", "error", "xpass")

    def _has_visible_leaf(self, node: TreeNode, query: str) -> bool:
        """Check if a branch has any visible descendant after all filters."""
        for child in node.children:
            if child.is_leaf:
                if self._is_hidden(child):
                    continue
                if query and not _fuzzy_match(query, child.label.lower()):
                    continue
                return True
            if self._has_visible_leaf(child, query):
                return True
        return False

    def _build_visible(self) -> list[TreeNode]:
        """Summary node + flattened tree, filtered by query and toggles."""
        all_nodes = self._tree.flat_visible()
        q = self._query.lower() if self._query else ""
        filtered: list[TreeNode] = []
        for node in all_nodes:
            if self._is_hidden(node):
                continue
            if not node.is_leaf and not self._has_visible_leaf(node, q):
                continue
            if q and not (
                _fuzzy_match(q, node.label.lower())
                or (not node.is_leaf and _has_matching_descendant(node, q))
            ):
                continue
            filtered.append(node)
        return [self._summary_node, *filtered]

    def _rebuild(self) -> None:
        """Rebuild the flat visible list after expand/collapse or query change."""
        self._visible = self._build_visible()
        if self._cursor >= len(self._visible):
            self._cursor = max(0, len(self._visible) - 1)
        self._ensure_visible()

    def _ensure_visible(self) -> None:
        """Scroll so the cursor is within the visible viewport."""
        view_h = self._height - 2  # title bar + search bar
        if view_h < 1:
            view_h = 1
        if self._cursor < self._scroll:
            self._scroll = self._cursor
        elif self._cursor >= self._scroll + view_h:
            self._scroll = self._cursor - view_h + 1

    def render(self) -> list[str]:
        """Render the overlay as a list of terminal lines."""
        lines: list[str] = []
        # Title bar with filter toggles.
        p_tag = f"{_GREEN}\u2713pass{_RESET}" if self._show_passed else f"{_DIM}pass{_RESET}"
        f_tag = f"{_RED_BOLD}\u2717fail{_RESET}" if self._show_failed else f"{_DIM}fail{_RESET}"
        title = f" {_BOLD}Test Tree{_RESET} {p_tag} {f_tag}"
        lines.append(title)

        # Tree nodes.
        view_h = self._height - 2  # title + search bar
        if view_h < 1:
            view_h = 1
        end = min(self._scroll + view_h, len(self._visible))
        for i in range(self._scroll, end):
            lines.append(self._render_node(self._visible[i], i))

        # Pad to push search bar to the bottom.
        while len(lines) < self._height - 1:
            lines.append("")

        # Search bar at the bottom (reverse-video background).
        w = self._width
        if self._query:
            inner = f" {_CYAN}/{_RESET}{_REVERSE} {self._query}\u2588"
        else:
            inner = f" {_DIM}{_REVERSE} type to search"
        lines.append(f"{_REVERSE}{pad_line(inner, w)}{_RESET}")

        return lines

    def _render_node(self, node: TreeNode, idx: int) -> str:
        """Render a single tree node with indentation and connector."""
        indent = "  " * (node.depth - 1) if node.depth > 0 else ""

        if node.is_leaf:
            icon = "  "  # align with text after ▼/▶ on branches
        elif node.expanded:
            icon = _EXPANDED
        else:
            icon = _COLLAPSED

        # Outcome marker.
        marker = ""
        if node.is_leaf and node.nodeid:
            outcome = self._outcomes.get(node.nodeid, "")
            marker = _OUTCOME_MARKER.get(outcome, "")
        elif not node.is_leaf and node is not self._summary_node:
            group_outcome = self._group_outcome(node)
            marker = _OUTCOME_MARKER.get(group_outcome, "")

        # Style based on node type.
        if node is self._summary_node:
            styled_label = f"{_BOLD}{node.label}{_RESET}"
        elif node.depth <= 1:
            styled_label = f"{_CYAN}{node.label}{_RESET}"
        elif node.is_leaf:
            styled_label = node.label
        else:
            styled_label = f"{_YELLOW}{node.label}{_RESET}"

        text = f" {indent}{icon}{styled_label}{marker}"

        # Highlight cursor line.
        if idx == self._cursor:
            # Reverse video for cursor.
            text = f"{_REVERSE}{pad_line(text, self._width - 1)}{_RESET}"

        return text
