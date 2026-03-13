"""
pytest-threaded: Parallel test execution for free-threaded Python.

Runs test method *bodies* concurrently in a ThreadPoolExecutor while keeping
fixture setup/teardown sequential (pytest internals are not thread-safe).

Tests are grouped by class and parameterization. Within each group:
  1. Setup runs sequentially for every item (fixtures are filled per-item).
  2. The "call" phase runs in parallel across threads via item.runtest().
  3. Teardown runs sequentially for every item.

Bare functions (not in a class) run fully sequentially.

Usage:
    PYTHON_GIL=0 pytest --threaded auto
    PYTHON_GIL=0 pytest --threaded 8
    pytest                              # no flag = normal sequential run
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from _pytest.runner import (
    call_and_report,
    show_test_item,
    CallInfo,
)
from _pytest.scope import Scope


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "parallel_only: skip test when not using --threaded"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("threaded") is not None:
        return
    skip = pytest.mark.skip(reason="requires --threaded")
    for item in items:
        if "parallel_only" in item.keywords:
            item.add_marker(skip)


def pytest_addoption(parser):
    parser.addoption(
        "--threaded",
        default=None,
        metavar="N",
        help=(
            "Parallelize test calls within each class using N threads. "
            "'auto' uses os.cpu_count()."
        ),
    )


def _thread_count(config):
    val = config.getoption("threaded")
    if val is None:
        return None
    if val == "auto":
        return os.cpu_count() or 4
    return int(val)


def _group_key(item):
    """Group key that separates bare functions, different classes, and
    different parameterizations of the same class."""
    cls = item.cls
    if cls is None:
        return None
    params = getattr(item, "callspec", None)
    if params is not None and params.params:
        return (cls, tuple(sorted(params.params.items())))
    return cls


# --------------------------------------------------------------------------
# Replace the default run loop
# --------------------------------------------------------------------------

@pytest.hookimpl(tryfirst=True)
def pytest_runtestloop(session):
    nthreads = _thread_count(session.config)
    if nthreads is None:
        return  # fall through to default sequential runner

    if (
            session.testsfailed
            and not session.config.option.continue_on_collection_errors
    ):
        raise session.Interrupted(
            "%d error%s during collection"
            % (session.testsfailed, "s" if session.testsfailed != 1 else "")
        )

    if session.config.option.collectonly:
        return True

    # Group CONSECUTIVE items by class+params, preserving collection order.
    # Items with different keys are never merged even if they share a key
    # (e.g. bare functions from different files stay separate).
    groups = []          # list of (key, [items])
    prev_key = object()  # sentinel
    for item in session.items:
        key = _group_key(item)
        if key != prev_key:
            groups.append((key, []))
            prev_key = key
        groups[-1][1].append(item)

    for group_key, items in groups:
        if session.shouldfail:
            raise session.Failed(session.shouldfail)
        if session.shouldstop:
            raise session.Interrupted(session.shouldstop)

        if group_key is None or len(items) <= 1 or nthreads <= 1:
            for i, item in enumerate(items):
                nextitem = items[i + 1] if i + 1 < len(items) else None
                _run_protocol_sequential(item, nextitem)
        else:
            _run_class_parallel(session, items, nthreads)

    return True


def _run_protocol_sequential(item, nextitem):
    """Run the full default protocol for a single item."""
    ihook = item.ihook
    ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)

    if hasattr(item, "_request") and not item._request:
        item._initrequest()

    rep_setup = call_and_report(item, "setup", log=True)
    if rep_setup.passed:
        if item.config.getoption("setupshow", False):
            show_test_item(item)
        if not item.config.getoption("setuponly", False):
            call_and_report(item, "call", log=True)
    call_and_report(item, "teardown", log=True, nextitem=nextitem)

    if hasattr(item, "_request"):
        item._request = False
        item.funcargs = None

    ihook.pytest_runtest_logfinish(nodeid=item.nodeid, location=item.location)


def _save_and_clear_function_fixtures(item):
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
            # Save this fixture's finalizers (yield teardowns, etc.)
            saved.extend(fixturedef._finalizers)
            fixturedef._finalizers.clear()
            # Invalidate cache so next item re-executes the fixture
            fixturedef.cached_result = None

    return saved


def _run_class_parallel(session, items, nthreads):
    """
    Run a class group's tests with parallel call phases.

    1. Sequential: setup every item (pop Function node from _setupstate
       after each, invalidate function-scoped fixture caches).
    2. Parallel:   item.runtest() in a thread pool.
    3. Sequential: run saved per-item finalizers, then tear down class.
    """
    setup_passed = {}
    per_item_fixture_fins = {}  # item -> [callable]

    # --- Phase 1: sequential setup for ALL items ----------------------------
    for item in items:
        ihook = item.ihook
        ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)

        if hasattr(item, "_request") and not item._request:
            item._initrequest()

        rep = call_and_report(item, "setup", log=True)
        setup_passed[item] = rep.passed

        if rep.passed and session.config.getoption("setupshow", False):
            show_test_item(item)

        if rep.passed:
            # Save function-scoped fixture finalizers BEFORE popping from stack.
            # This preserves yield fixture teardowns (e.g. teardown_method)
            # while allowing the next item to get fresh fixtures.
            per_item_fixture_fins[item] = _save_and_clear_function_fixtures(item)

        # Pop this item's Function node from _setupstate WITHOUT running
        # its finalizers.  This leaves [Session, Module, Class, ...] intact
        # so the next item's setup can push its own Function node.
        if item in session._setupstate.stack:
            session._setupstate.stack.pop(item)

    if session.config.getoption("setuponly", False):
        _teardown_all(session, items, per_item_fixture_fins)
        return

    # --- Phase 2: parallel calls -------------------------------------------
    callable_items = [it for it in items if setup_passed.get(it)]
    workers = min(nthreads, len(callable_items)) if callable_items else 1

    call_results = {}  # item -> CallInfo

    def _do_call(test_item):
        call_info = CallInfo.from_call(lambda: test_item.runtest(), when="call")
        return test_item, call_info

    if workers > 1 and len(callable_items) > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_do_call, item): item
                for item in callable_items
            }
            for future in as_completed(futures):
                exc = future.exception()
                if exc is not None:
                    item = futures[future]
                    call_info = CallInfo.from_call(
                        lambda e=exc: (_ for _ in ()).throw(e),
                        when="call",
                    )
                    call_results[item] = call_info
                else:
                    item, call_info = future.result()
                    call_results[item] = call_info
    else:
        for item in callable_items:
            _, call_info = _do_call(item)
            call_results[item] = call_info

    # --- Phase 3: report call results sequentially -------------------------
    for item in callable_items:
        call_info = call_results[item]
        rep = item.ihook.pytest_runtest_makereport(item=item, call=call_info)
        item.ihook.pytest_runtest_logreport(report=rep)

    # --- Phase 4: sequential teardown --------------------------------------
    _teardown_all(session, items, per_item_fixture_fins)


def _teardown_all(session, items, per_item_fixture_fins):
    """Run per-item function-level finalizers, then tear down class collectors."""
    for item in items:
        fins = per_item_fixture_fins.get(item, [])

        def _run_fins(fns=fins):
            for fn in reversed(fns):
                fn()

        teardown_info = CallInfo.from_call(_run_fins, when="teardown")
        rep = item.ihook.pytest_runtest_makereport(item=item, call=teardown_info)
        item.ihook.pytest_runtest_logreport(report=rep)

        if hasattr(item, "_request"):
            item._request = False
            item.funcargs = None

        item.ihook.pytest_runtest_logfinish(
            nodeid=item.nodeid, location=item.location
        )

    # Tear down remaining class/module/session collectors still in the stack.
    session._setupstate.teardown_exact(nextitem=None)
