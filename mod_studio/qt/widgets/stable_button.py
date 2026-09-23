"""
A push button whose width does not change when its text does.

Three buttons on the Sounds page say their state in their text - "Play" and
"Pause", "Loop: on" and "Loop: off", "Undo this track's replacement" and
"Undo this track's loop change". A button is as wide as its text, so every
one of those changes pushed the buttons after it sideways: pressing Play
moved Stop, Loop and both Set buttons 11px to the right while the music
played. Part of "it moves elements of the page ... it feels amateurish".

The button is sized for the WIDEST of the texts it can show, measured from
the button's own font at layout time - so it is right after the stylesheet
arrives and after a theme or font change, which a width fixed in
`__init__` would not be (see `setup.py`'s reset button for that trap).
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QPushButton, QStyle, QStyleOptionButton


class StableButton(QPushButton):
    """A QPushButton as wide as the widest of `texts`, whichever it shows."""

    def __init__(self, text: str, alternates=(), parent=None):
        super().__init__(text, parent)
        self._texts = [text, *alternates]

    def sizeHint(self) -> QSize:                               # noqa: N802
        """
        The size QPushButton would ask for with each text, whichever is
        largest - computed the way QPushButton computes its own, through
        the style, because the style adds padding and may impose a minimum
        width (a subtraction of text widths from the current hint gets the
        second one wrong: "Play" and "Pause" both come out at the style's
        80px floor, and the arithmetic said 90 and 80).
        """
        best = super().sizeHint()
        option = QStyleOptionButton()
        self.initStyleOption(option)
        metrics = self.fontMetrics()
        for text in self._texts:
            option.text = text
            content = metrics.size(Qt.TextShowMnemonic, text)
            best = best.expandedTo(self.style().sizeFromContents(
                QStyle.CT_PushButton, option, content, self))
        return best

    def minimumSizeHint(self) -> QSize:                        # noqa: N802
        return self.sizeHint()
