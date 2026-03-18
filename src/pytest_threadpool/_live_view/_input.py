"""Terminal input reader: parses keys and mouse events from raw bytes."""

from __future__ import annotations

import contextlib
import dataclasses
import os
import queue
import re
import select
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import IO


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
        elif b == 0x0D:
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
    """

    def __init__(self, fd: int, *, notify: threading.Event | None = None) -> None:
        self._fd = fd
        self._queue: queue.Queue[InputEvent] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        # Self-pipe for clean shutdown of blocking select().
        self._wake_r, self._wake_w = os.pipe()
        # Optional event to signal when new input arrives.
        self._notify = notify
        # Debug log (set externally to enable).
        self.debug_log: IO[str] | None = None
        # Heartbeat: incremented every loop iteration.
        self.loop_count: int = 0

    def start(self) -> None:
        """Start the background reader thread."""
        self._stop.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=1)

    def stop(self) -> None:
        """Signal the reader to stop and wait for the thread."""
        self._stop.set()
        # Wake up select() via the self-pipe.
        with contextlib.suppress(OSError):
            os.write(self._wake_w, b"\x00")
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        # Close the self-pipe fds.
        for fd in (self._wake_r, self._wake_w):
            with contextlib.suppress(OSError):
                os.close(fd)

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
        fd = self._fd
        os.set_blocking(fd, False)
        self._ready.set()
        try:
            self._read_loop(fd)
        finally:
            with contextlib.suppress(OSError):
                os.set_blocking(fd, True)

    def _read_loop(self, fd: int) -> None:
        """Non-blocking reads with adaptive wait strategy.

        Uses ``select()`` to wait for data efficiently.  If select()
        exhibits starvation (common on free-threaded Python 3.14t),
        automatically falls back to a tight polling loop with short
        sleeps.
        """
        wake_r = self._wake_r
        # Start with select() — switch to polling if starvation detected.
        use_select = True
        starvation_count = 0

        while not self._stop.is_set():
            if use_select:
                t_sel = time.monotonic()
                try:
                    ready, _, _ = select.select([fd, wake_r], [], [], 0.01)
                except (OSError, ValueError):
                    break
                elapsed = time.monotonic() - t_sel
                # Detect starvation: select(timeout=10ms) took >100ms.
                if not ready and elapsed > 0.1:
                    starvation_count += 1
                    if starvation_count >= 3:
                        use_select = False
                        _dbg = self.debug_log
                        if _dbg is not None:
                            _dbg.write(
                                f"  IR select starvation detected "
                                f"({elapsed:.3f}s), switching to poll\n"
                            )
                            _dbg.flush()
                else:
                    starvation_count = 0
                self.loop_count += 1
                if not ready:
                    continue
                if wake_r in ready:
                    break
            else:
                # Tight polling fallback — 0.5 ms sleep.
                time.sleep(0.0005)
                self.loop_count += 1

            try:
                data = os.read(fd, 4096)
            except BlockingIOError:
                continue
            except OSError:
                break
            if not data:
                break
            t_read = time.monotonic()
            events = parse_events(data)
            for event in events:
                self._queue.put(event)
            if self._notify is not None:
                self._notify.set()
            _dbg = self.debug_log
            if _dbg is not None:
                _dbg.write(
                    f"  IR {t_read:.4f} fd={fd} "
                    f"bytes={len(data)} events={len(events)} "
                    f"raw={data!r}\n"
                )
                _dbg.flush()
