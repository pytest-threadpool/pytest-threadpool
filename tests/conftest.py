"""
pytest-threaded: Parallel test execution for free-threaded Python.

Runs test *bodies* concurrently in a ThreadPoolExecutor while keeping
fixture setup/teardown sequential (pytest internals are not thread-safe).

Mark tests for parallel execution (import from tests.markers for IDE hints):

    @parallelizable("children")    # methods/functions run in parallel
    @parallelizable("parameters")  # parametrized variants run in parallel
    @parallelizable("all")         # children + parameters

    @not_parallelizable            # opt out of inherited parallelism

The marker can be applied at function, class, module (pytestmark), or
package (__init__.py pytestmark) level.

Scopes:
  children   – direct children of the marked node run concurrently.
               On a class: methods run in parallel.
               On a module (pytestmark): each class's methods run in parallel,
               and bare functions run in parallel with each other.
               On a package (__init__.py): ALL tests within the package run
               in parallel across modules and classes.
  parameters – parametrized variants of the marked test run concurrently.
               test_foo[0], test_foo[1], … share a parallel batch.
  all        – combines children + parameters.  @parametrize variants
               are merged into the class batch (class-scoped fixture
               params still separate groups for correctness).

Marker priority (most specific wins):
  not_parallelizable > own marker > class > module > package

Usage:
    PYTHON_GIL=0 pytest --threaded auto
    PYTHON_GIL=0 pytest --threaded 8
    pytest                              # no flag = normal sequential run
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from _pytest.runner import (
    call_and_report,
    show_test_item,
    CallInfo,
)
from _pytest.scope import Scope

_PARALLEL_SCOPES = frozenset(("children", "parameters", "all"))
_MARKER = "parallelizable"
_NOT_MARKER = "not_parallelizable"


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "parallel_only: skip test when not using --threaded"
    )
    config.addinivalue_line(
        "markers",
        f"{_MARKER}(scope): mark for parallel execution. "
        "scope: 'children' | 'parameters' | 'all'",
    )
    config.addinivalue_line(
        "markers",
        f"{_NOT_MARKER}: opt out of inherited parallel execution",
    )


def _has_package_parallel_only(item):
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
        if any(m.name == "parallel_only" for m in marks):
            return True
    return False


def pytest_collection_modifyitems(config, items):
    if config.getoption("threaded") is not None:
        return
    skip = pytest.mark.skip(reason="requires --threaded")
    for item in items:
        if "parallel_only" in item.keywords or _has_package_parallel_only(item):
            item.add_marker(skip)


def pytest_addoption(parser):
    parser.addoption(
        "--threaded",
        default=None,
        metavar="N",
        help=(
            "Parallelize marked test calls using N threads. "
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


# --------------------------------------------------------------------------
# Marker introspection
# --------------------------------------------------------------------------

def _scope_from_marks(marks):
    """Extract parallelizable scope from a list of pytest marks."""
    if not isinstance(marks, (list, tuple)):
        marks = [marks]
    for m in marks:
        if m.name == _MARKER:
            scope = m.args[0] if m.args else "all"
            return scope if scope in _PARALLEL_SCOPES else None
    return None


def _has_not_marker(marks):
    """Check if marks contain not_parallelizable."""
    if not isinstance(marks, (list, tuple)):
        marks = [marks]
    return any(m.name == _NOT_MARKER for m in marks)


def _own_scope(item):
    """Parallel scope from the item's own markers (not inherited)."""
    if any(m.name == _NOT_MARKER for m in item.own_markers):
        return "not"
    for m in item.own_markers:
        if m.name == _MARKER:
            scope = m.args[0] if m.args else "all"
            return scope if scope in _PARALLEL_SCOPES else None
    return None


def _class_scope(item):
    """Parallel scope from the item's class."""
    if not item.cls:
        return None
    marks = getattr(item.cls, "pytestmark", [])
    if _has_not_marker(marks):
        return "not"
    return _scope_from_marks(marks)


def _module_scope(item):
    """Parallel scope from the item's module."""
    marks = getattr(item.module, "pytestmark", [])
    if _has_not_marker(marks):
        return "not"
    return _scope_from_marks(marks)


def _package_scope(item):
    """Parallel scope from the item's package hierarchy (__init__.py pytestmark)."""
    pkg_name = getattr(item.module, "__package__", None)
    if not pkg_name:
        return None
    parts = pkg_name.split(".")
    # Walk from innermost package outward
    for i in range(len(parts), 0, -1):
        pkg = ".".join(parts[:i])
        mod = sys.modules.get(pkg)
        if mod is None:
            continue
        marks = getattr(mod, "pytestmark", [])
        if _has_not_marker(marks):
            return "not"
        scope = _scope_from_marks(marks)
        if scope:
            return scope
    return None


def _parametrize_argnames(item):
    """Collect arg names from all @pytest.mark.parametrize markers."""
    names = set()
    for marker in item.iter_markers("parametrize"):
        argnames = marker.args[0]
        if isinstance(argnames, str):
            names.update(n.strip() for n in argnames.split(","))
        elif isinstance(argnames, (list, tuple)):
            names.update(argnames)
    return names


def _fixture_param_key(item):
    """Extract non-@parametrize params (i.e. fixture params with broader scope).

    These must stay in the group key to prevent merging groups whose
    class/module/session-scoped fixtures differ.
    """
    callspec = getattr(item, "callspec", None)
    if not callspec or not callspec.params:
        return ()
    parametrize_names = _parametrize_argnames(item)
    fixture_params = {
        k: v for k, v in callspec.params.items()
        if k not in parametrize_names
    }
    return tuple(sorted(fixture_params.items())) if fixture_params else ()


# --------------------------------------------------------------------------
# Grouping
# --------------------------------------------------------------------------

def _parallel_group_key(item):
    """Compute a group key for parallel batching.

    Returns a hashable key if the item should be part of a parallel batch,
    or None for sequential execution.
    Consecutive items with the same non-None key form a parallel batch.

    Marker priority: not_parallelizable > own > class > module > package.
    """
    own = _own_scope(item)
    cls = _class_scope(item)
    mod = _module_scope(item)
    pkg = _package_scope(item)

    # --- not_parallelizable at any level forces sequential ---
    if own == "not":
        return None
    if item.cls and cls == "not":
        return None

    # --- Resolve effective scope (most specific wins) ---
    # For "children" semantics: can this item run in parallel with siblings?
    child_parallel = False
    # For "parameters" semantics: can parametrized variants run together?
    param_parallel = False

    # Check levels from most to least specific.
    # The first level that has an explicit marker determines behavior.

    if own is not None:
        # Item has its own marker
        if own == "all":
            child_parallel = True
            param_parallel = True
        elif own == "parameters":
            param_parallel = True
        # own == "children" on a leaf test doesn't enable anything for itself
    elif item.cls and cls is not None:
        # Class has a marker (and module/package didn't override via not_)
        if cls in ("children", "all"):
            child_parallel = True
        if cls in ("parameters", "all"):
            param_parallel = True
    elif mod is not None and mod != "not":
        # Module has a marker
        if mod in ("children", "all"):
            child_parallel = True
        if mod in ("parameters", "all"):
            param_parallel = True
    elif pkg is not None and pkg != "not":
        # Package has a marker
        if pkg in ("children", "all"):
            child_parallel = True
        if pkg in ("parameters", "all"):
            param_parallel = True

    # --- Compute group key ---

    if child_parallel:
        # Determine the grouping level based on where the marker was defined
        if _is_package_level(item, own, cls, mod, pkg):
            # Package-level children: ALL items in the package batch together
            return ("pkg_children", item.module.__package__)

        if item.cls:
            fp_key = _fixture_param_key(item)
            if fp_key:
                return ("class", item.cls, fp_key)
            return ("class", item.cls)
        else:
            return ("mod_children", id(item.module))

    if param_parallel:
        callspec = getattr(item, "callspec", None)
        if callspec:
            fp_key = _fixture_param_key(item)
            if fp_key:
                return ("params", item.cls, item.originalname, fp_key)
            return ("params", item.cls, item.originalname)

    return None


def _is_package_level(item, own, cls, mod, pkg):
    """True when the effective children marker comes from the package level."""
    if own is not None:
        return False
    if item.cls and cls is not None:
        return False
    if mod is not None and mod != "not":
        return False
    return pkg is not None and pkg in ("children", "all")


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

    # Group CONSECUTIVE items by parallel group key.
    groups = []          # list of (key, [items])
    prev_key = object()  # sentinel
    for item in session.items:
        key = _parallel_group_key(item)
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
            _run_group_parallel(session, items, nthreads)

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
            saved.extend(fixturedef._finalizers)
            fixturedef._finalizers.clear()
            fixturedef.cached_result = None

    return saved


def _save_collector_finalizers(session, next_item):
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


def _run_group_parallel(session, items, nthreads):
    """
    Run a group's tests with parallel call phases.

    Handles cross-module/class transitions within a batch by saving
    broader-scope finalizers before teardown_exact() and deferring them
    to after the parallel call phase.

    1. Sequential: setup every item (no reporting yet).
    2. Parallel:   item.runtest() in a thread pool.
    3. Sequential: report setup + call results per item (logstart before each
       item so the terminal reporter attributes dots to the correct file).
    4. Sequential: per-item finalizers, saved collector finalizers,
       then tear down remaining collectors.
    """
    setup_passed = {}
    setup_reports = {}                 # item -> report
    per_item_fixture_fins = {}         # item -> [callable]
    saved_collector_fins = []          # [(node, [finalizers])]

    # --- Phase 1: sequential setup for ALL items (silent) -------------------
    for item in items:
        if hasattr(item, "_request") and not item._request:
            item._initrequest()

        # Handle cross-module/class transitions: save finalizers from nodes
        # that would be torn down, then let teardown_exact pop them cleanly
        # so that setup() finds only matching nodes on the stack.
        needed = set(item.listchain())
        if any(node not in needed for node in session._setupstate.stack):
            saved_collector_fins.extend(
                _save_collector_finalizers(session, item)
            )
            session._setupstate.teardown_exact(nextitem=item)

        rep = call_and_report(item, "setup", log=False)
        setup_reports[item] = rep
        setup_passed[item] = rep.passed

        if rep.passed:
            per_item_fixture_fins[item] = _save_and_clear_function_fixtures(item)

        if item in session._setupstate.stack:
            session._setupstate.stack.pop(item)

    if session.config.getoption("setuponly", False):
        # Report setups before teardown
        for item in items:
            ihook = item.ihook
            ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)
            ihook.pytest_runtest_logreport(report=setup_reports[item])
            if setup_passed[item] and session.config.getoption("setupshow", False):
                show_test_item(item)
        _teardown_all(session, items, per_item_fixture_fins, saved_collector_fins)
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

    # --- Phase 3: report setup + call results per item --------------------
    # logstart is emitted here (not during Phase 1) so the terminal reporter
    # attributes each dot/F to the correct file in non-verbose mode.
    for item in items:
        ihook = item.ihook
        ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)
        ihook.pytest_runtest_logreport(report=setup_reports[item])

        if setup_passed[item]:
            if session.config.getoption("setupshow", False):
                show_test_item(item)
            if item in call_results:
                call_info = call_results[item]
                rep = ihook.pytest_runtest_makereport(item=item, call=call_info)
                ihook.pytest_runtest_logreport(report=rep)

    # --- Phase 4: sequential teardown --------------------------------------
    _teardown_all(session, items, per_item_fixture_fins, saved_collector_fins)


def _teardown_all(session, items, per_item_fixture_fins, saved_collector_fins):
    """Run per-item function-level finalizers, saved collector finalizers,
    then tear down remaining collectors."""
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

    # Tear down whatever is still on the stack (last module/class).
    session._setupstate.teardown_exact(nextitem=None)

    # Run saved collector finalizers from cross-module/class transitions
    # in reverse order (LIFO: innermost scope first).
    exceptions = []
    for node, fins in reversed(saved_collector_fins):
        for fin in reversed(fins):
            try:
                fin()
            except BaseException as e:
                exceptions.append(e)
    if len(exceptions) == 1:
        raise exceptions[0]
    elif exceptions:
        raise BaseExceptionGroup(
            "errors during deferred collector teardown", exceptions
        )
