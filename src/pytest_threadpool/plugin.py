"""pytest plugin hooks -- wiring only, delegates to classes."""

import os
import sys
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
    parser.addini(
        "threadpool_tree_width",
        "Width (columns) of the live-view tree pane. 0 = auto.",
        type="string",
        default="0",
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
            try:
                tw_cfg = int(session.config.getini("threadpool_tree_width"))
            except (ValueError, TypeError):
                tw_cfg = 0
            view_manager._tree_width_cfg = tw_cfg
            session.config._threadpool_view_manager = view_manager  # pyright: ignore[reportPrivateUsage]

            # Show the session header on the alt screen.
            _add_session_header(session, view_manager)

    runner = ParallelRunner(session, nthreads, view_manager=view_manager)
    return runner.run_all()


def _add_session_header(session, view_manager) -> None:
    """Capture pytest's actual session header and replay it on the alt screen.

    Uses the terminal reporter's TerminalWriter to produce the exact
    same ANSI-formatted output (bold separator, platform info, etc.).
    """
    import io as _io
    import platform

    config = session.config
    tr = config.pluginmanager.get_plugin("terminalreporter")
    width = view_manager.width

    # Use pytest's own TerminalWriter to format the header identically.
    from _pytest._io.terminalwriter import TerminalWriter

    buf = _io.StringIO()
    tw = TerminalWriter(buf)
    tw.fullwidth = width
    tw.hasmarkup = True

    tw.sep("=", "test session starts", bold=True)
    tw.line(
        f"platform {sys.platform} -- Python {platform.python_version()}, "
        f"pytest-{pytest.__version__}"
    )
    tw.line(f"rootdir: {config.rootpath}")
    inipath = config.inipath
    if inipath and inipath != config.rootpath:
        tw.line(f"configfile: {inipath}")

    plugininfo = config.pluginmanager.list_plugin_distinfo()
    if plugininfo:
        plugin_str = ", ".join(f"{dist.project_name}-{dist.version}" for _, dist in plugininfo)
        tw.line(f"plugins: {plugin_str}")

    if tr and hasattr(tr, "_session"):
        nitems = len(session.items) if hasattr(session, "items") else 0
        tw.line(f"collected {nitems} items")

    # Each line from the TerminalWriter becomes a header line.
    for line in buf.getvalue().splitlines():
        view_manager.add_header(line)
    view_manager.add_header("")  # blank separator line


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
        view_manager.wait_and_leave()


def _is_free_threaded() -> bool:
    """Check if running on a free-threaded Python build (GIL disabled)."""
    from sysconfig import get_config_vars

    return bool(get_config_vars().get("Py_GIL_DISABLED"))
