"""pytest-freethreaded: Parallel test execution for free-threaded Python."""

from pytest_freethreaded._api import not_parallelizable, parallelizable
from pytest_freethreaded._constants import ParallelScope

__all__ = ["ParallelScope", "not_parallelizable", "parallelizable"]
