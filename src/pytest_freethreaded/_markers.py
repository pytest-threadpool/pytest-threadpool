"""Marker introspection for resolving effective parallel scope."""

import sys

from ._constants import (
    MARKER_NOT_PARALLELIZABLE,
    MARKER_PARALLEL_ONLY,
    MARKER_PARALLELIZABLE,
    PARALLEL_SCOPES,
    SCOPE_NOT,
)


class MarkerResolver:
    """Resolves the effective parallel scope for a test item.

    Walks the marker priority chain: own > class > module > package.
    """

    @staticmethod
    def scope_from_marks(marks) -> str | None:
        """Extract parallelizable scope from a list of pytest marks."""
        if not isinstance(marks, (list, tuple)):
            marks = [marks]
        for m in marks:
            if m.name == MARKER_PARALLELIZABLE:
                scope = m.args[0] if m.args else ParallelScope.ALL
                return scope if scope in PARALLEL_SCOPES else None
        return None

    @staticmethod
    def has_not_marker(marks) -> bool:
        """Check if marks contain not_parallelizable."""
        if not isinstance(marks, (list, tuple)):
            marks = [marks]
        return any(m.name == MARKER_NOT_PARALLELIZABLE for m in marks)

    @staticmethod
    def own_scope(item) -> str | None:
        """Parallel scope from the item's own markers (not inherited)."""
        if any(m.name == MARKER_NOT_PARALLELIZABLE for m in item.own_markers):
            return SCOPE_NOT
        for m in item.own_markers:
            if m.name == MARKER_PARALLELIZABLE:
                scope = m.args[0] if m.args else ParallelScope.ALL
                return scope if scope in PARALLEL_SCOPES else None
        return None

    @staticmethod
    def class_scope(item) -> str | None:
        """Parallel scope from the item's class."""
        if not item.cls:
            return None
        marks = getattr(item.cls, "pytestmark", [])
        if MarkerResolver.has_not_marker(marks):
            return SCOPE_NOT
        return MarkerResolver.scope_from_marks(marks)

    @staticmethod
    def module_scope(item) -> str | None:
        """Parallel scope from the item's module."""
        marks = getattr(item.module, "pytestmark", [])
        if MarkerResolver.has_not_marker(marks):
            return SCOPE_NOT
        return MarkerResolver.scope_from_marks(marks)

    @staticmethod
    def package_scope(item) -> str | None:
        """Parallel scope from the item's package hierarchy."""
        pkg_name = getattr(item.module, "__package__", None)
        if not pkg_name:
            return None
        parts = pkg_name.split(".")
        for i in range(len(parts), 0, -1):
            pkg = ".".join(parts[:i])
            mod = sys.modules.get(pkg)
            if mod is None:
                continue
            marks = getattr(mod, "pytestmark", [])
            if MarkerResolver.has_not_marker(marks):
                return SCOPE_NOT
            scope = MarkerResolver.scope_from_marks(marks)
            if scope:
                return scope
        return None

    @staticmethod
    def has_package_parallel_only(item) -> bool:
        """Check if any package in the item's hierarchy has parallel_only."""
        pkg_name = getattr(item.module, "__package__", None)
        if not pkg_name:
            return False
        parts = pkg_name.split(".")
        for i in range(len(parts), 0, -1):
            mod = sys.modules.get(".".join(parts[:i]))
            if mod is None:
                continue
            marks = getattr(mod, "pytestmark", [])
            if not isinstance(marks, (list, tuple)):
                marks = [marks]
            if any(m.name == MARKER_PARALLEL_ONLY for m in marks):
                return True
        return False

    @staticmethod
    def parametrize_argnames(item) -> set[str]:
        """Collect arg names from all @pytest.mark.parametrize markers."""
        names = set()
        for marker in item.iter_markers("parametrize"):
            argnames = marker.args[0]
            if isinstance(argnames, str):
                names.update(n.strip() for n in argnames.split(","))
            elif isinstance(argnames, (list, tuple)):
                names.update(argnames)
        return names

    @staticmethod
    def fixture_param_key(item) -> tuple:
        """Extract non-@parametrize params (fixture params with broader scope).

        These must stay in the group key to prevent merging groups whose
        class/module/session-scoped fixtures differ.
        """
        from _pytest.scope import Scope

        callspec = getattr(item, "callspec", None)
        if not callspec or not callspec.params:
            return ()
        parametrize_names = MarkerResolver.parametrize_argnames(item)
        fixture_params = {
            k: v
            for k, v in callspec.params.items()
            if k not in parametrize_names
        }
        return tuple(sorted(fixture_params.items())) if fixture_params else ()


# Import here to avoid circular; used only in scope_from_marks / own_scope
from ._constants import ParallelScope  # noqa: E402
