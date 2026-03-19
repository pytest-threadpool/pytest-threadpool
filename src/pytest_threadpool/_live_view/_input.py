"""Terminal input reader: parses keys and mouse events from raw bytes."""

from __future__ import annotations

import contextlib
import dataclasses
import os
import queue
import re
import select
import threading
from typing import ClassVar


@dataclasses.dataclass(frozen=True)
class KeyEvent:
    """A parsed keyboard event."""

    key: str  # e.g., "q", "Tab", "Up", "Down", "Escape", "Ctrl+C"


@dataclasses.dataclass(frozen=True)
class MouseEvent:
    """A parsed SGR mouse event."""

    button: int  # 0=left, 1=middle, 2=right, 64=scroll-up, 65=scroll-down
    row: int  # 0-based
    col: int  # 0-based
    pressed: bool  # True for press, False for release


InputEvent = KeyEvent | MouseEvent

# SGR mouse: \033[<button;col;row[Mm]
_SGR_MOUSE_RE = re.compile(rb"\033\[<(\d+);(\d+);(\d+)([Mm])")

# CSI sequences for arrow keys, etc.
_CSI_KEY_MAP: dict[bytes, str] = {
    b"\033[A": "Up",
    b"\033[B": "Down",
    b"\033[C": "Right",
    b"\033[D": "Left",
    b"\033[H": "Home",
    b"\033[F": "End",
    b"\033[5~": "PageUp",
    b"\033[6~": "PageDown",
    b"\033[1;5C": "Ctrl+Right",
    b"\033[1;5D": "Ctrl+Left",
}


def parse_events(data: bytes) -> list[InputEvent]:
    """Parse raw terminal bytes into a list of input events."""
    events: list[InputEvent] = []
    i = 0
    n = len(data)

    while i < n:
        # ESC sequence.
        if data[i : i + 1] == b"\033":
            # SGR mouse.
            m = _SGR_MOUSE_RE.match(data, i)
            if m:
                btn = int(m.group(1))
                col = int(m.group(2)) - 1  # 1-based → 0-based
                row = int(m.group(3)) - 1
                pressed = m.group(4) == b"M"
                events.append(MouseEvent(button=btn, row=row, col=col, pressed=pressed))
                i += len(m.group(0))
                continue

            # CSI key sequences.
            matched = False
            for seq, name in _CSI_KEY_MAP.items():
                if data[i : i + len(seq)] == seq:
                    events.append(KeyEvent(key=name))
                    i += len(seq)
                    matched = True
                    break
            if matched:
                continue

            # Bare ESC.
            if i + 1 >= n or data[i + 1 : i + 2] != b"[":
                events.append(KeyEvent(key="Escape"))
                i += 1
                continue

            # Unknown CSI — skip to end of sequence.
            j = i + 2
            while j < n and not (0x40 <= data[j] <= 0x7E):
                j += 1
            if j < n:
                j += 1  # include the final byte
            i = j
            continue

        # Control characters.
        b = data[i]
        if b == 0x09:
            events.append(KeyEvent(key="Tab"))
        elif b in (0x0D, 0x0A):
            events.append(KeyEvent(key="Enter"))
        elif b == 0x03:
            events.append(KeyEvent(key="Ctrl+C"))
        elif b == 0x7F:
            events.append(KeyEvent(key="Backspace"))
        elif 0x01 <= b <= 0x1A:
            events.append(KeyEvent(key=f"Ctrl+{chr(b + 0x60)}"))
        elif 0x20 <= b <= 0x7E:
            events.append(KeyEvent(key=chr(b)))
        i += 1

    return events


class InputReader:
    """Reads terminal input in a background thread, queues events.

    Uses ``select()`` with a short timeout so the thread can be
    stopped promptly without blocking in ``os.read()``.

    Only one active reader per process is allowed — starting a new
    reader automatically stops any previously active one to prevent
    competing reads on the shared terminal input buffer.
    """

    # Registry of active readers keyed by terminal device number.
    # When a new reader starts on the same device, old ones are stopped
    # to prevent competing reads on the shared kernel input buffer.
    _active_lock = threading.Lock()
    _active_by_dev: ClassVar[dict[int, InputReader]] = {}

    def __init__(self, fd: int, *, notify: threading.Event | None = None) -> None:
        # Dup the fd so that external dup2() redirections (e.g. pytest
        # capture redirecting fd 1 to a pipe) don't affect our reads.
        # The duped fd shares the same underlying terminal device.
        self._fd = os.dup(fd)
        self._dev: int = 0
        if os.isatty(self._fd):
            with contextlib.suppress(OSError):
                self._dev = os.fstat(self._fd).st_rdev
        self._owns_fd = True
        self._queue: queue.Queue[InputEvent] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._wake_r, self._wake_w = os.pipe()
        self._notify = notify

    def start(self) -> None:
        """Start the background reader thread.

        For tty fds, signals any previously active InputReader on the
        same device to stop (without blocking) to prevent competing
        reads on the shared kernel input buffer.  Pipe/pty fds used
        in unit tests are unaffected.
        """
        if self._dev:
            with InputReader._active_lock:
                prev = InputReader._active_by_dev.get(self._dev)
                if prev is not None and prev is not self:
                    prev._stop.set()
                    with contextlib.suppress(OSError):
                        os.write(prev._wake_w, b"\x00")
                InputReader._active_by_dev[self._dev] = self
        self._stop.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=1)

    def stop(self) -> None:
        """Signal the reader to stop and wait for the thread."""
        if self._dev:
            with InputReader._active_lock:
                if InputReader._active_by_dev.get(self._dev) is self:
                    del InputReader._active_by_dev[self._dev]
        self._stop.set()
        # Wake up select() via the self-pipe.
        with contextlib.suppress(OSError):
            os.write(self._wake_w, b"\x00")
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        # Close the self-pipe fds and our duped input fd.
        for fd in (self._wake_r, self._wake_w):
            with contextlib.suppress(OSError):
                os.close(fd)
        if self._owns_fd:
            with contextlib.suppress(OSError):
                os.close(self._fd)
            self._owns_fd = False

    def poll(self) -> InputEvent | None:
        """Return the next event, or None if the queue is empty."""
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def drain(self) -> list[InputEvent]:
        """Return all queued events."""
        events: list[InputEvent] = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events

    def _run(self) -> None:
        self._ready.set()
        self._read_loop(self._fd)

    def _read_loop(self, fd: int) -> None:
        """Blocking select() + blocking read() with self-pipe shutdown.

        Never changes the fd's blocking mode — the fd may be shared
        (e.g. stdout) so setting ``O_NONBLOCK`` would break other
        writers.  ``select()`` tells us data is available, then the
        blocking ``read()`` returns immediately.
        """
        wake_r = self._wake_r
        while not self._stop.is_set():
            try:
                ready, _, _ = select.select([fd, wake_r], [], [], 0.01)
            except (OSError, ValueError):
                break
            if not ready:
                continue
            if wake_r in ready:
                break
            try:
                data = os.read(fd, 4096)
            except OSError:
                break
            if not data:
                break
            events = parse_events(data)
            for event in events:
                self._queue.put(event)
            if self._notify is not None:
                self._notify.set()
