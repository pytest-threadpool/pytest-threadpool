"""Pure-stdlib DI providers — no C extensions, no GIL re-enablement.

Four scopes built on threading and contextvars primitives:

- ``Singleton``:        one instance for the process lifetime (thread-safe).
- ``ThreadLocal``:      one instance per OS thread.
- ``ContextLocal``:     one instance per execution context (survives await).
- ``Factory``:          fresh instance on every call.
"""

import contextlib
import contextvars
import threading
from typing import Any


class Singleton:
    """Thread-safe singleton — one instance for the entire process."""

    def __init__(self, cls: type, **kwargs: Any):
        self._cls = cls
        self._kwargs = kwargs
        self._instance: Any = None
        self._lock = threading.Lock()

    def __call__(self) -> Any:
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    self._instance = self._cls(**self._resolve_kwargs())
        return self._instance

    def reset(self) -> None:
        with self._lock:
            self._instance = None

    def _resolve_kwargs(self) -> dict:
        return {k: v() if callable(v) else v for k, v in self._kwargs.items()}


class ThreadLocal:
    """Thread-local singleton — one instance per OS thread."""

    def __init__(self, cls: type, **kwargs: Any):
        self._cls = cls
        self._kwargs = kwargs
        self._local = threading.local()

    def __call__(self) -> Any:
        try:
            return self._local.instance
        except AttributeError:
            self._local.instance = self._cls(**self._resolve_kwargs())
            return self._local.instance

    def reset(self) -> None:
        with contextlib.suppress(AttributeError):
            del self._local.instance

    def _resolve_kwargs(self) -> dict:
        return {k: v() if callable(v) else v for k, v in self._kwargs.items()}


class ContextLocal:
    """Context-local singleton — one instance per execution context.

    Uses ``contextvars.ContextVar``, so the instance follows the async
    execution flow across ``await`` boundaries, even if the coroutine
    resumes on a different OS thread.
    """

    _SENTINEL = object()

    def __init__(self, cls: type, **kwargs: Any):
        self._cls = cls
        self._kwargs = kwargs
        self._var: contextvars.ContextVar = contextvars.ContextVar(f"_di_{cls.__name__}")

    def __call__(self) -> Any:
        instance = self._var.get(self._SENTINEL)
        if instance is self._SENTINEL:
            instance = self._cls(**self._resolve_kwargs())
            self._var.set(instance)
        return instance

    def reset(self) -> None:
        self._var.set(self._SENTINEL)  # type: ignore[arg-type]

    def _resolve_kwargs(self) -> dict:
        return {k: v() if callable(v) else v for k, v in self._kwargs.items()}


class Factory:
    """Factory — fresh instance on every call."""

    def __init__(self, cls: type, **kwargs: Any):
        self._cls = cls
        self._kwargs = kwargs

    def __call__(self) -> Any:
        return self._cls(**self._resolve_kwargs())

    def _resolve_kwargs(self) -> dict:
        return {k: v() if callable(v) else v for k, v in self._kwargs.items()}
