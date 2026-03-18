"""ANSI escape sequence utilities."""

from __future__ import annotations

import re

# Matches a single ANSI CSI sequence (e.g. \033[32m, \033[K, \033[2A).
CSI_RE = re.compile(r"\033\[[^a-zA-Z]*[a-zA-Z]")


def visible_len(text: str) -> int:
    """Count visible characters in *text*, ignoring ANSI CSI sequences."""
    return len(CSI_RE.sub("", text))


def move_to(row: int, col: int) -> str:
    """Return CSI sequence to move cursor to *row*, *col* (1-based)."""
    return f"\033[{row};{col}H"


def hide_cursor() -> str:
    return "\033[?25l"


def show_cursor() -> str:
    return "\033[?25h"


def enter_alt_screen() -> str:
    return "\033[?1049h"


def exit_alt_screen() -> str:
    return "\033[?1049l"


def clear_screen() -> str:
    return "\033[H\033[2J"


def reset_sgr() -> str:
    return "\033[0m"


def enable_mouse_tracking() -> str:
    """Enable SGR extended mouse mode (button events + scroll)."""
    return "\033[?1000h\033[?1006h"


def disable_mouse_tracking() -> str:
    return "\033[?1000l\033[?1006l"


def pad_line(content: str, width: int) -> str:
    """Truncate or pad *content* to exactly *width* visible characters.

    ANSI sequences pass through without counting toward width.
    A trailing reset is appended to prevent color bleed.
    """
    if width <= 0:
        return ""

    out: list[str] = []
    col = 0
    i = 0
    n = len(content)

    while i < n:
        ch = content[i]

        if ch == "\033" and i + 1 < n and content[i + 1] == "[":
            m = CSI_RE.match(content, i)
            if m:
                out.append(m.group())
                i += len(m.group())
                continue

        if col < width:
            out.append(ch)
            col += 1
        i += 1

    out.append("\033[0m")
    if col < width:
        out.append(" " * (width - col))

    return "".join(out)
