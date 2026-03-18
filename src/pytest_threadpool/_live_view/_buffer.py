"""Thread-safe growable line buffer."""

from __future__ import annotations

import threading


class ScreenBuffer:
    """Growable in-memory line buffer.  Thread-safe, no terminal I/O.

    Lines are appended via ``add_lines()`` (returns starting index).
    Workers update individual rows via ``set_line()``.
    Consumers read via ``snapshot()``.
    """

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._lock = threading.Lock()

    def add_lines(self, n: int) -> int:
        """Append *n* empty lines and return the starting index."""
        with self._lock:
            start = len(self._lines)
            self._lines.extend([""] * n)
            return start

    def set_line(self, row: int, content: str) -> None:
        """Update content for *row*.  Thread-safe."""
        with self._lock:
            self._lines[row] = content

    def snapshot(self) -> list[str]:
        """Return a copy of all lines."""
        with self._lock:
            return list(self._lines)

    @property
    def nlines(self) -> int:
        with self._lock:
            return len(self._lines)
