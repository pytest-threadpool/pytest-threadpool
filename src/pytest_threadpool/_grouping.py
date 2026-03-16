"""Group key computation for parallel test batching."""

from pytest_threadpool._constants import (
    SCOPE_NOT,
    ParallelScope,
    _GroupPrefix,
)
from pytest_threadpool._markers import MarkerResolver


class GroupKeyBuilder:
    """Computes parallel batch group keys for test items."""

    @staticmethod
    def group_key(item) -> tuple | None:
        """Compute a group key for parallel batching.

        Returns a hashable key if the item should be part of a parallel batch,
        or None for sequential execution.
        Consecutive items with the same non-None key form a parallel batch.

        Marker priority: not_parallelizable > own > class > module > package.
        """
        own = MarkerResolver.own_scope(item)
        cls = MarkerResolver.class_scope(item)
        mod = MarkerResolver.module_scope(item)
        pkg = MarkerResolver.package_scope(item)

        # not_parallelizable at any level forces sequential
        if own == SCOPE_NOT:
            return None
        if item.cls and cls == SCOPE_NOT:
            return None

        child_parallel = False
        param_parallel = False

        # The most specific level with an explicit marker determines behavior
        if own is not None:
            if own == ParallelScope.ALL:
                child_parallel = True
                param_parallel = True
            elif own == ParallelScope.PARAMETERS:
                param_parallel = True
        elif item.cls and cls is not None:
            if cls in (ParallelScope.CHILDREN, ParallelScope.ALL):
                child_parallel = True
            if cls in (ParallelScope.PARAMETERS, ParallelScope.ALL):
                param_parallel = True
        elif mod is not None and mod != SCOPE_NOT:
            if mod in (ParallelScope.CHILDREN, ParallelScope.ALL):
                child_parallel = True
            if mod in (ParallelScope.PARAMETERS, ParallelScope.ALL):
                param_parallel = True
        elif pkg is not None and pkg != SCOPE_NOT:
            if pkg in (ParallelScope.CHILDREN, ParallelScope.ALL):
                child_parallel = True
            if pkg in (ParallelScope.PARAMETERS, ParallelScope.ALL):
                param_parallel = True

        if child_parallel:
            if GroupKeyBuilder._is_package_level(item, own, cls, mod, pkg):
                source = MarkerResolver.marker_source_package(item)
                return (_GroupPrefix.PKG_CHILDREN, source or item.module.__package__)
            if item.cls:
                fp_key = MarkerResolver.fixture_param_key(item)
                if fp_key:
                    return (_GroupPrefix.CLASS, item.cls, fp_key)
                return (_GroupPrefix.CLASS, item.cls)
            return (_GroupPrefix.MOD_CHILDREN, id(item.module))

        if param_parallel:
            callspec = getattr(item, "callspec", None)
            if callspec:
                fp_key = MarkerResolver.fixture_param_key(item)
                if fp_key:
                    return (_GroupPrefix.PARAMS, item.cls, item.originalname, fp_key)
                return (_GroupPrefix.PARAMS, item.cls, item.originalname)

        return None

    @staticmethod
    def _is_package_level(item, own, cls, mod, pkg) -> bool:
        """True when the effective children marker comes from the package level."""
        if own is not None:
            return False
        if item.cls and cls is not None:
            return False
        if mod is not None and mod != SCOPE_NOT:
            return False
        return pkg is not None and pkg in (ParallelScope.CHILDREN, ParallelScope.ALL)

    @staticmethod
    def build_groups(items) -> list[tuple[object, list]]:
        """Group consecutive items by parallel group key.

        Returns a list of (key, [items]) tuples.
        Package-level groups that are split by sequential items
        (e.g. @not_parallelizable functions) are merged back together,
        with the sequential items deferred to after the parallel batch.
        """
        groups: list[tuple[object, list]] = []
        prev_key = object()
        for item in items:
            key = GroupKeyBuilder.group_key(item)
            if key != prev_key:
                groups.append((key, []))
                prev_key = key
            groups[-1][1].append(item)
        return GroupKeyBuilder._merge_package_groups(groups)

    @staticmethod
    def _merge_package_groups(
        groups: list[tuple[object, list]],
    ) -> list[tuple[object, list]]:
        """Merge non-consecutive groups sharing the same PKG_CHILDREN key.

        Sequential (None-key) items between fragments are deferred to after
        the merged parallel group, preserving their relative order.
        """
        pkg_indices: dict[object, list[int]] = {}
        for i, (key, _) in enumerate(groups):
            if isinstance(key, tuple) and key[0] == _GroupPrefix.PKG_CHILDREN:
                pkg_indices.setdefault(key, []).append(i)

        fragmented = {k for k, v in pkg_indices.items() if len(v) > 1}
        if not fragmented:
            return groups

        merged: list[tuple[object, list]] = []
        consumed: set[int] = set()
        for i, (key, items) in enumerate(groups):
            if i in consumed:
                continue
            if key not in fragmented:
                merged.append((key, items))
                continue

            # Merge all fragments of this package key
            indices = pkg_indices[key]
            parallel_items: list = []
            deferred: list[tuple[object, list]] = []
            for j in range(indices[0], indices[-1] + 1):
                consumed.add(j)
                gkey, gitems = groups[j]
                if gkey == key:
                    parallel_items.extend(gitems)
                else:
                    deferred.append((gkey, gitems))

            merged.append((key, parallel_items))
            merged.extend(deferred)

        return merged
