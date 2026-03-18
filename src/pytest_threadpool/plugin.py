"""pytest plugin hooks -- wiring only, delegates to classes."""

import os
import warnings

import pytest

from pytest_threadpool import hooks as threadpool_hooks
from pytest_threadpool._constants import (
    MARKER_NOT_PARALLELIZABLE,
    MARKER_PARALLEL_ONLY,
    MARKER_PARALLELIZABLE,
)
from pytest_threadpool._markers import MarkerResolver
from pytest_threadpool._runner import ParallelRunner


def pytest_addhooks(pluginmanager):
    pluginmanager.add_hookspecs(threadpool_hooks)


def pytest_addoption(parser):
    parser.addoption(
        "--threadpool",
        default=None,
        metavar="N",
        help=("Parallelize marked test calls using N threads. 'auto' uses os.cpu_count()."),
    )
    parser.addoption(
        "--threadpool-output",
        choices=["classic", "live"],
        default="classic",
        help="Output mode: 'classic' (current) or 'live' (interactive viewer)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        f"{MARKER_PARALLEL_ONLY}: skip test when not using --threadpool",
    )
    config.addinivalue_line(
        "markers",
        f"{MARKER_PARALLELIZABLE}(scope): mark for parallel execution. "
        "scope: 'children' | 'parameters' | 'all'",
    )
    config.addinivalue_line(
        "markers",
        f"{MARKER_NOT_PARALLELIZABLE}: opt out of inherited parallel execution",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("threadpool") is not None:
        return
    skip = pytest.mark.skip(reason="requires --threadpool")
    for item in items:
        if MARKER_PARALLEL_ONLY in item.keywords or MarkerResolver.has_package_parallel_only(item):
            item.add_marker(skip)


@pytest.hookimpl(tryfirst=True)
def pytest_runtestloop(session):
    nthreads = _thread_count(session.config)
    if nthreads is None:
        return None
    if not _is_free_threaded():
        warnings.warn(
            "--threadpool works best with free-threaded Python (e.g. python3.14t). "
            "The GIL limits parallel speedup for CPU-bound tests.",
            stacklevel=1,
        )

    output_mode = session.config.getoption("threadpool_output", "classic")
    view_manager = None
    if output_mode == "live":
        from pytest_threadpool._live_view import ViewManager

        tr = session.config.pluginmanager.get_plugin("terminalreporter")
        tw = tr._tw if tr and hasattr(tr, "_tw") else None  # pyright: ignore[reportPrivateUsage]
        file = getattr(tw, "_file", None) if tw else None  # pyright: ignore[reportPrivateUsage]
        is_tty = file is not None and hasattr(file, "isatty") and file.isatty()
        if is_tty and file is not None:
            width = getattr(tw, "fullwidth", 80) if tw else 80
            view_manager = ViewManager(file, width)
            view_manager.register("main")
            view_manager.activate("main")
            session.config._threadpool_view_manager = view_manager  # pyright: ignore[reportPrivateUsage]

    runner = ParallelRunner(session, nthreads, view_manager=view_manager)
    return runner.run_all()


def _thread_count(config) -> int | None:
    val = config.getoption("threadpool")
    if val is None:
        return None
    if val == "auto":
        return os.cpu_count() or 4
    try:
        return int(val)
    except ValueError:
        raise pytest.UsageError(f"--threadpool: expected integer or 'auto', got {val!r}") from None


def pytest_unconfigure(config):
    view_manager = getattr(config, "_threadpool_view_manager", None)
    if view_manager is not None:
        view_manager.wait_for_interrupt()


def _is_free_threaded() -> bool:
    """Check if running on a free-threaded Python build (GIL disabled)."""
    from sysconfig import get_config_vars

    return bool(get_config_vars().get("Py_GIL_DISABLED"))
