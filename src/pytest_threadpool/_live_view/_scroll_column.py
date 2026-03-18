"""Scroll indicator column rendered on the right edge of a field."""

from __future__ import annotations


class ScrollColumn:
    """Renders a 1-character-wide scroll indicator.

    Shows a thumb (visible portion) on a track, like a scrollbar.
    Returns empty strings when all content fits in the viewport.
    """

    THUMB = "\u2588"  # █ Full block
    TRACK = "\u2502"  # │ Box drawing light vertical

    def render(
        self,
        viewport_height: int,
        content_height: int,
        scroll_offset: int,
    ) -> list[str]:
        """Return a list of single-character strings, one per viewport row.

        If content fits in the viewport, returns empty strings (no bar).
        """
        if content_height <= viewport_height:
            return [""] * viewport_height

        # Thumb size: proportional to viewport/content ratio, minimum 1 row.
        thumb_size = max(1, round(viewport_height * viewport_height / content_height))

        # Thumb position: proportional to scroll offset.
        max_offset = content_height - viewport_height
        if max_offset > 0:
            thumb_top = round(scroll_offset / max_offset * (viewport_height - thumb_size))
        else:
            thumb_top = 0
        thumb_top = max(0, min(thumb_top, viewport_height - thumb_size))

        result: list[str] = []
        for row in range(viewport_height):
            if thumb_top <= row < thumb_top + thumb_size:
                result.append(self.THUMB)
            else:
                result.append(self.TRACK)
        return result
