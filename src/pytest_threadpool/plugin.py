"""pytest plugin hooks -- wiring only, delegates to classes."""

import os
import warnings

import pytest

from pytest_threadpool._constants import (
    MARKER_NOT_PARALLELIZABLE,
    MARKER_PARALLEL_ONLY,
    MARKER_PARALLELIZABLE,
)
from pytest_threadpool._markers import MarkerResolver
from pytest_threadpool._runner import ParallelRunner


def pytest_addoption(parser):
    parser.addoption(
        "--threadpool",
        default=None,
        metavar="N",
        help=("Parallelize marked test calls using N threads. 'auto' uses os.cpu_count()."),
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
    runner = ParallelRunner(session, nthreads)
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


def _is_free_threaded() -> bool:
    """Check if running on a free-threaded Python build (GIL disabled)."""
    from sysconfig import get_config_vars

    return bool(get_config_vars().get("Py_GIL_DISABLED"))
