"""Fixture finalizer save/restore helpers for parallel execution."""

from _pytest.scope import Scope


class FixtureManager:
    """Helpers for saving/restoring fixture finalizers during parallel execution.

    Uses protected members of pytest internals (FixtureDef, TopRequest,
    SetupState) because there is no public API for direct finalizer
    manipulation.  These are the same internals that pytest's own
    runner.py and fixtures.py use.
    """

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
                fins_list, exc_info = session._setupstate.stack[node]  # pyright: ignore[reportPrivateUsage]
                saved.append((node, list(fins_list)))
                fins_list.clear()
        return saved
