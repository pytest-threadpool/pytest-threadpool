"""pytest plugin hooks -- wiring only, delegates to classes."""

import os
import sys

import pytest

from ._constants import (
    MARKER_NOT_PARALLELIZABLE,
    MARKER_PARALLEL_ONLY,
    MARKER_PARALLELIZABLE,
)
from ._markers import MarkerResolver
from ._runner import ParallelRunner


def pytest_addoption(parser):
    parser.addoption(
        "--freethreaded",
        default=None,
        metavar="N",
        help=(
            "Parallelize marked test calls using N threads. "
            "'auto' uses os.cpu_count()."
        ),
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        f"{MARKER_PARALLEL_ONLY}: skip test when not using --freethreaded",
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
    if config.getoption("freethreaded") is not None:
        return
    skip = pytest.mark.skip(reason="requires --freethreaded")
    for item in items:
        if (
            MARKER_PARALLEL_ONLY in item.keywords
            or MarkerResolver.has_package_parallel_only(item)
        ):
            item.add_marker(skip)


@pytest.hookimpl(tryfirst=True)
def pytest_runtestloop(session):
    nthreads = _thread_count(session.config)
    if nthreads is None:
        return None
    if not _is_free_threaded():
        raise pytest.UsageError(
            "--freethreaded requires a free-threaded Python build "
            "(e.g. python3.13t or python3.14t)"
        )
    runner = ParallelRunner(session, nthreads)
    return runner.run_all()


def _thread_count(config) -> int | None:
    val = config.getoption("freethreaded")
    if val is None:
        return None
    if val == "auto":
        return os.cpu_count() or 4
    return int(val)


def _is_free_threaded() -> bool:
    """Check if running on a free-threaded Python build (GIL disabled)."""
    from sysconfig import get_config_vars

    return bool(get_config_vars().get("Py_GIL_DISABLED"))
