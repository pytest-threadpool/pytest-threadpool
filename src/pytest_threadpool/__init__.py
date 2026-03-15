"""pytest-threadpool: Parallel test execution for free-threaded Python."""

from pytest_threadpool._api import not_parallelizable, parallelizable
from pytest_threadpool._constants import ParallelScope

__all__ = ["ParallelScope", "not_parallelizable", "parallelizable"]
