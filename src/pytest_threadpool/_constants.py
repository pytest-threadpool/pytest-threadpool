"""Constants and enums for pytest-threadpool."""

from enum import StrEnum


class ParallelScope(StrEnum):
    """Parallelism strategies for test execution."""

    CHILDREN = "children"
    PARAMETERS = "parameters"
    ALL = "all"


PARALLEL_SCOPES = frozenset(s.value for s in ParallelScope)

MARKER_PARALLELIZABLE = "parallelizable"
MARKER_NOT_PARALLELIZABLE = "not_parallelizable"
MARKER_PARALLEL_ONLY = "parallel_only"


class _GroupPrefix(StrEnum):
    """Internal group key prefixes for parallel batching."""

    CLASS = "class"
    MOD_CHILDREN = "mod_children"
    PKG_CHILDREN = "pkg_children"
    PARAMS = "params"


SCOPE_NOT = "not"
