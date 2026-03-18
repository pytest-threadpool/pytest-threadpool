"""Dynamic live-view interface for terminal output.

Provides a channel-based architecture where output sources write to named
channels, and a ViewManager controls which channels are rendered to the
terminal.  Phase 1 uses a single "main" channel as a passthrough wrapper
around existing _LiveReporter output.
"""

from __future__ import annotations

import signal
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import IO


class Channel:
    """A named stream of terminal content."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._lines: list[str] = []
        self._listeners: list[Callable[[Channel, str], None]] = []

    def write(self, text: str) -> None:
        """Append content. Notifies ViewManager if this channel is visible."""
        self._lines.append(text)
        for cb in self._listeners:
            cb(self, text)

    def flush(self) -> None:
        """Flush is a no-op; the ViewManager flushes the underlying file."""

    def subscribe(self, callback: Callable[[Channel, str], None]) -> None:
        """Register a listener for new content on this channel."""
        self._listeners.append(callback)

    @property
    def lines(self) -> list[str]:
        """All content written to this channel."""
        return list(self._lines)


class ViewManager:
    """Manages channels and terminal rendering.

    In Phase 1, a single "main" channel passes all output through to
    the underlying file handle unchanged.  Future phases add per-worker
    channels, keyboard switching, and split layouts.
    """

    def __init__(self, file: IO[str], width: int) -> None:
        self._file = file
        self._width = width
        self._channels: dict[str, Channel] = {}
        self._active: list[str] = []
        self._lock = threading.Lock()

    def register(self, name: str) -> Channel:
        """Create and register a new channel."""
        ch = Channel(name)
        self._channels[name] = ch
        ch.subscribe(self._on_channel_write)
        return ch

    def activate(self, *names: str) -> None:
        """Set which channels are visible."""
        with self._lock:
            self._active = list(names)

    def _on_channel_write(self, channel: Channel, text: str) -> None:
        """Forward writes from active channels to the terminal."""
        with self._lock:
            if channel.name in self._active:
                self._file.write(text)
                self._file.flush()

    def wait_for_interrupt(self) -> None:
        """Block until Ctrl+C after tests complete.

        Keeps the terminal output visible so users can review results.
        Handles SIGINT gracefully on both the main thread and when
        signals are not available (e.g. non-main thread).
        """
        if threading.current_thread() is not threading.main_thread():
            return  # pragma: no cover -- signals only work on main thread

        stop = threading.Event()
        prev_handler = signal.getsignal(signal.SIGINT)

        def _handler(signum: int, frame: object) -> None:
            stop.set()

        # Install our handler BEFORE writing the prompt so an early
        # SIGINT (e.g. user presses Ctrl+C immediately) is caught
        # instead of raising KeyboardInterrupt through the default handler.
        signal.signal(signal.SIGINT, _handler)
        try:
            self._file.write("\n(tests complete — press Ctrl+C to exit)\n")
            self._file.flush()

            # Use a timeout loop so Python can process pending signals
            # between iterations (Event.wait() without timeout blocks
            # in C code and defers signal handler execution).
            while not stop.wait(timeout=0.5):
                pass
        finally:
            signal.signal(signal.SIGINT, prev_handler)

        # Move past the ^C that the terminal prints.
        # Wrap in try/except because restoring prev_handler above may
        # cause a deferred KeyboardInterrupt to fire here.
        try:
            self._file.write("\n")
            self._file.flush()
        except KeyboardInterrupt:
            pass

    @property
    def file(self) -> IO[str]:
        """The underlying file handle."""
        return self._file

    @property
    def width(self) -> int:
        """Terminal width."""
        return self._width

    @property
    def channels(self) -> dict[str, Channel]:
        """All registered channels."""
        return dict(self._channels)
