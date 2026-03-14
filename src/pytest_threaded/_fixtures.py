"""Fixture finalizer save/restore helpers for parallel execution."""

from _pytest.scope import Scope


class FixtureManager:
    """Helpers for saving/restoring fixture finalizers during parallel execution."""

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

        for fixturedef in request._fixture_defs.values():
            if fixturedef._scope is Scope.Function:
                saved.extend(fixturedef._finalizers)
                fixturedef._finalizers.clear()
                fixturedef.cached_result = None

        return saved

    @staticmethod
    def save_collector_finalizers(session, next_item) -> list:
        """Save finalizers from stack nodes that would be torn down when
        transitioning to next_item.  Clears them from the stack so
        teardown_exact() pops the nodes without side effects.

        Returns a list of (node, [finalizers]) tuples.
        """
        needed = set(next_item.listchain())
        saved = []
        for node in list(session._setupstate.stack):
            if node not in needed:
                fins_list, exc_info = session._setupstate.stack[node]
                saved.append((node, list(fins_list)))
                fins_list.clear()
        return saved
