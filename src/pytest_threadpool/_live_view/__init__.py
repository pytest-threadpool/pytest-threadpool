"""Live-view terminal UI package.

Re-exports public API for backward compatibility with existing imports
like ``from pytest_threadpool._live_view import ViewManager``.
"""

from pytest_threadpool._live_view._ansi import visible_len as _visible_len
from pytest_threadpool._live_view._buffer import ScreenBuffer
from pytest_threadpool._live_view._cursor import Cursor, CursorMode
from pytest_threadpool._live_view._display import Display
from pytest_threadpool._live_view._field import Field, SplitDirection
from pytest_threadpool._live_view._input import InputReader, KeyEvent, MouseEvent, parse_events
from pytest_threadpool._live_view._layout import LayoutManager, Rect
from pytest_threadpool._live_view._scroll_column import ScrollColumn
from pytest_threadpool._live_view._status_line import Position, StatusLine
from pytest_threadpool._live_view._tree_overlay import ItemTree, TreeOverlay
from pytest_threadpool._live_view._view_manager import Region, ViewManager

__all__ = [
    "Cursor",
    "CursorMode",
    "Display",
    "Field",
    "InputReader",
    "ItemTree",
    "KeyEvent",
    "LayoutManager",
    "MouseEvent",
    "Position",
    "Rect",
    "Region",
    "ScreenBuffer",
    "ScrollColumn",
    "SplitDirection",
    "StatusLine",
    "TreeOverlay",
    "ViewManager",
    "_visible_len",
    "parse_events",
]
