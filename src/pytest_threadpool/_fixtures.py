"""Fixture finalizer save/restore helpers for parallel execution."""

from collections.abc import Iterable

from _pytest.fixtures import FixtureDef
from _pytest.scope import Scope


class FixtureManager:
    """Helpers for saving/restoring fixture finalizers during parallel execution.

    Uses protected members of pytest internals (FixtureDef, TopRequest,
    SetupState) because there is no public API for direct finalizer
    manipulation.  These are the same internals that pytest's own
    runner.py and fixtures.py use.
    """

    @staticmethod
    def clone_function_fixturedefs(item) -> None:
        """Clone function-scoped FixtureDefs so this item has its own copies.

        Shared (module/class/session) FixtureDefs are kept as-is — their
        cached values are read-only after the first item's setup.
        Function-scoped FixtureDefs get independent copies with fresh
        cached_result and _finalizers, allowing concurrent fixture setup
        across items without racing on shared singleton state.
        """
        # noinspection PyProtectedMember
        # request._arg2fixturedefs, fixturedef._scope: no public API;
        # mirrors pytest's own TopRequest/FixtureDef internals.
        request = getattr(item, "_request", None)
        if not request or not hasattr(request, "_arg2fixturedefs"):
            return  # pragma: no cover -- defensive guard; request is always initialized by pytest

        new_arg2fds = {}
        for argname, fds in request._arg2fixturedefs.items():  # pyright: ignore[reportPrivateUsage]
            new_fds = []
            for fd in fds:
                if fd._scope is Scope.Function:  # pyright: ignore[reportPrivateUsage]
                    clone = FixtureDef.__new__(FixtureDef)
                    clone.__dict__.update(fd.__dict__)
                    clone.cached_result = None
                    clone._finalizers = []  # pyright: ignore[reportPrivateUsage, reportAttributeAccessIssue]
                    new_fds.append(clone)
                else:
                    new_fds.append(fd)
            new_arg2fds[argname] = new_fds

        # _arg2fixturedefs is typed Final but not enforced at runtime
        object.__setattr__(request, "_arg2fixturedefs", new_arg2fds)

    @staticmethod
    def save_and_clear_function_fixtures(item) -> list:
        """After an item's setup, save its function-scoped fixture finalizers
        and invalidate FixtureDef caches so the next item gets fresh fixtures.

        Returns a list of saved finalizer callables for this item.
        """
        saved = []
        request = getattr(item, "_request", None)
        if not request or not hasattr(request, "_fixture_defs"):
            return saved

        # noinspection PyProtectedMember
        # request._fixture_defs, fixturedef._scope, fixturedef._finalizers:
        # No public API for direct finalizer access; mirrors pytest's own
        # FixtureDef/TopRequest internals.
        for fixturedef in request._fixture_defs.values():  # pyright: ignore[reportPrivateUsage]
            if fixturedef._scope is Scope.Function:  # pyright: ignore[reportPrivateUsage]
                saved.extend(fixturedef._finalizers)  # pyright: ignore[reportPrivateUsage]
                fixturedef._finalizers.clear()  # pyright: ignore[reportPrivateUsage]
                fixturedef.cached_result = None

        return saved

    @staticmethod
    def clear_function_fixture_caches(item) -> None:
        """Invalidate function-scoped fixture caches after a failed setup.

        When setup fails, the fixture def's execute() raises before
        registering in request._fixture_defs.  We use _arg2fixturedefs
        (populated during collection) to find all candidate fixture defs.
        """
        request = getattr(item, "_request", None)
        if not request:
            return

        # noinspection PyProtectedMember
        # request._arg2fixturedefs: populated during collection, maps
        # argname -> list[FixtureDef].  Unlike _fixture_defs, this is
        # available even when setup fails mid-execution.
        arg2fds = getattr(request, "_arg2fixturedefs", {})
        for fixturedefs in arg2fds.values():  # pyright: ignore[reportPrivateUsage]
            for fixturedef in fixturedefs:
                if fixturedef._scope is Scope.Function and fixturedef.cached_result is not None:  # pyright: ignore[reportPrivateUsage]
                    fixturedef.cached_result = None

    @staticmethod
    def populate_shared_fixtures(item) -> None:
        """Resolve only non-function-scoped fixtures for the item.

        Populates shared fixture caches (module/class/session scope) by
        calling getfixturevalue for each non-function-scoped fixture.
        Function-scoped fixtures are skipped — they will be created later
        from cloned FixtureDefs in parallel workers.

        Must be called inside a setup hook context (item in setupstate)
        so that addfinalizer works for the resolved fixtures.
        """
        # noinspection PyProtectedMember
        # request._arg2fixturedefs, fixturedef._scope: no public API;
        # mirrors pytest's own TopRequest/FixtureDef internals.
        request = getattr(item, "_request", None)
        if not request or not hasattr(request, "_arg2fixturedefs"):
            return  # pragma: no cover -- defensive guard; request is always initialized by pytest

        for argname in item.fixturenames:
            if argname in item.funcargs:
                continue  # pragma: no cover -- funcargs is empty when called from parallel prep
            fds = request._arg2fixturedefs.get(argname, [])  # pyright: ignore[reportPrivateUsage]
            if fds and fds[-1]._scope is not Scope.Function:  # pyright: ignore[reportPrivateUsage]
                value = request.getfixturevalue(argname)
                item.funcargs[argname] = value
                # Eagerly initialize lazy state on shared fixture values.
                # TmpPathFactory.getbasetemp() lazily creates the basetemp
                # directory; without this, parallel workers would race on
                # the first tmp_path_factory.mktemp() call.
                if hasattr(value, "getbasetemp"):
                    value.getbasetemp()

    @staticmethod
    def run_finalizers(finalizers: Iterable, msg: str = "errors during fixture teardown") -> None:
        """Run finalizers in reverse order, collecting all exceptions.

        Raises the single exception directly if only one occurs, or a
        BaseExceptionGroup if multiple finalizers fail.
        """
        exceptions = []
        for fn in reversed(list(finalizers)):
            try:
                fn()
            except BaseException as e:
                exceptions.append(e)
        if len(exceptions) == 1:
            raise exceptions[0]
        if exceptions:
            raise BaseExceptionGroup(msg, exceptions)

    @staticmethod
    def save_collector_finalizers(session, next_item) -> list:
        """Save finalizers from stack nodes that would be torn down when
        transitioning to next_item.  Clears them from the stack so
        teardown_exact() pops the nodes without side effects.

        Returns a list of (node, [finalizers]) tuples.
        """
        needed = set(next_item.listchain())
        saved = []
        # noinspection PyProtectedMember
        # session._setupstate: no public API for setup state management;
        # mirrors pytest's own runner.py (SetupState).
        for node in list(session._setupstate.stack):  # pyright: ignore[reportPrivateUsage]
            if node not in needed:
                fins_list, _exc_info = session._setupstate.stack[node]  # pyright: ignore[reportPrivateUsage]
                saved.append((node, list(fins_list)))
                fins_list.clear()
        return saved
