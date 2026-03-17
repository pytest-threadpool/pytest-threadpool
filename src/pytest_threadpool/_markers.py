"""Marker introspection for resolving effective parallel scope."""

import sys
from collections.abc import Iterator

from pytest_threadpool._constants import (
    MARKER_NOT_PARALLELIZABLE,
    MARKER_PARALLEL_ONLY,
    MARKER_PARALLELIZABLE,
    PARALLEL_SCOPES,
    SCOPE_NOT,
    ParallelScope,
)


def _walk_package_marks(item) -> Iterator[tuple[str, list]]:
    """Yield (package_name, marks) for each package in the item's hierarchy.

    Walks from most specific to least specific package.
    Normalizes marks to a list before yielding.
    """
    pkg_name = getattr(item.module, "__package__", None)
    if not pkg_name:
        return
    parts = pkg_name.split(".")
    for i in range(len(parts), 0, -1):
        pkg = ".".join(parts[:i])
        mod = sys.modules.get(pkg)
        if mod is None:
            continue
        marks = getattr(mod, "pytestmark", [])
        if not isinstance(marks, list):
            marks = [marks] if not isinstance(marks, tuple) else list(marks)
        yield pkg, marks


class MarkerResolver:
    """Resolves the effective parallel scope for a test item.

    Walks the marker priority chain: own > class > module > package.
    """

    @staticmethod
    def scope_from_marks(marks) -> str | None:
        """Extract a parallelizable scope from a list of pytest marks."""
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
        for _pkg, marks in _walk_package_marks(item):
            if MarkerResolver.has_not_marker(marks):
                return SCOPE_NOT
            scope = MarkerResolver.scope_from_marks(marks)
            if scope:
                return scope
        return None

    @staticmethod
    def marker_source_package(item) -> str | None:
        """Return the package name where the parallelizable marker was found.

        Walks the package hierarchy from most specific to least specific,
        returning the name of the first package that has a parallelizable marker.
        Returns None if no package has the marker.
        """
        for pkg, marks in _walk_package_marks(item):
            scope = MarkerResolver.scope_from_marks(marks)
            if scope:
                return pkg
        return None

    @staticmethod
    def has_package_parallel_only(item) -> bool:
        """Check if any package in the item's hierarchy has parallel_only."""
        for _pkg, marks in _walk_package_marks(item):
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
        # noinspection PyProtectedMember
        # callspec._arg2scope: no public API; needed to identify
        # function-scoped params from pytest_generate_tests (which
        # don't produce parametrize markers visible to iter_markers).
        arg2scope = getattr(callspec, "_arg2scope", {})
        fixture_params = {
            k: v
            for k, v in callspec.params.items()
            if k not in parametrize_names
            and arg2scope.get(k, Scope.Function) is not Scope.Function
        }
        return tuple(sorted(fixture_params.items())) if fixture_params else ()
