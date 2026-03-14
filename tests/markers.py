"""Re-export typed marker wrappers from the package."""

from pytest_threaded import not_parallelizable, parallelizable

__all__ = ["not_parallelizable", "parallelizable"]
