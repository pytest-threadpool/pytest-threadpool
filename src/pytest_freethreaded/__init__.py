"""pytest-freethreaded: Parallel test execution for free-threaded Python."""

from typing import Literal

import pytest

from ._constants import ParallelScope

__all__ = ["ParallelScope", "not_parallelizable", "parallelizable"]


def parallelizable(
    scope: Literal["children", "parameters", "all"],
) -> pytest.MarkDecorator:
    """Mark a test/class/module for parallel execution.

    Args:
        scope: Parallelism strategy.
            ``"children"`` -- all nested tests run concurrently.
            ``"parameters"`` -- parametrized variants run concurrently.
            ``"all"`` -- children + parameters combined.
    """
    return pytest.mark.parallelizable(scope)


not_parallelizable: pytest.MarkDecorator = pytest.mark.not_parallelizable
"""Opt out of inherited parallel execution."""
