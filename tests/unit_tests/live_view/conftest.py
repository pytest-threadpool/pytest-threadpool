"""Shared helpers for live-view unit tests."""

import re


def strip_ansi(text):
    """Remove all ANSI CSI sequences from text."""
    return re.sub(r"\033\[[^a-zA-Z]*[a-zA-Z]", "", text)
