"""
One line that reports what an action just did, in room that is always there.

Reported twice in one message, about two pages: after "Export this texture
as PNG..." an "Exported to ..." line appeared ABOVE the previews and pushed
them down, so the picture shrank; and on Sounds, exporting or replacing a
track moved the waveform and everything under it - "it feels amateurish".

Both were the same construction: a result appended to a label that sits
above the thing being looked at, so every message is a layout change. The
fix is the one desktop applications use for it. The result goes in a line
that is ALWAYS laid out - empty until there is something to say - beside or
under the control that produced it, so a message appearing moves nothing:

- **One line, never wrapped.** A wrapped message is a message whose height
  depends on its length and the window's width, which is the fault again.
  A message too long for the room is elided, and the whole of it is in the
  tooltip (see `FieldNoteLabel`, which this is).
- **Its height is reserved while it is empty.** `sizeHint` answers one line
  of the current font whatever the text, so the layout gives it the same
  room before and after.
- **It takes no width of its own.** Horizontally `Ignored`, so a long path
  cannot widen the column it sits in - on Textures that column's width is
  what keeps the two previews the same size.
"""
from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QSizePolicy

from .field_rows import FieldNoteLabel

#: The roles the theme colours (`QLabel[role=...]` in `theme.py`), and
#: "plain" for the ordinary text colour.
KINDS = ("plain", "muted", "ok", "attention", "danger")


class StatusLine(FieldNoteLabel):
    """A one-line, always-reserved result message."""

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setProperty("role", "muted")
        #: The kind of the message on screen, for checks and for callers.
        self.kind = "muted"

    def sizeHint(self) -> QSize:                               # noqa: N802
        margins = self.contentsMargins()
        return QSize(0, self.fontMetrics().height()
                     + margins.top() + margins.bottom())

    def minimumSizeHint(self) -> QSize:                        # noqa: N802
        return self.sizeHint()

    def say(self, text: str, kind: str = "muted") -> None:
        """Shows `text`, coloured as `kind` - one of `KINDS`."""
        if kind not in KINDS:
            kind = "muted"
        if kind != self.kind:
            self.kind = kind
            self.setProperty("role", "" if kind == "plain" else kind)
            self.style().unpolish(self)
            self.style().polish(self)
        self.setText(text)

    def clear(self) -> None:                                   # noqa: D401
        """Back to saying nothing, in the same room."""
        self.say("", "muted")
