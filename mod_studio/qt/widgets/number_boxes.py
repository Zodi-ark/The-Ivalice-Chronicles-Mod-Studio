"""
Number boxes as wide as the numbers they hold.

Zodi, 6 October: "on the items page if the price field is five digits it
gets cut off ... in this screenshot the price is 16000 you can see a bit of
the last zero before it is cut off. I'm sure this is a problem exists
everywhere else in mod studio for fields that can be five digits or more."

It did. Every field row's box was 84 pixels whatever its range. The theme
keeps 20 pixels of padding and 16 for the arrows on the right, so the line
edit inside had 40, and draws its text 2 pixels in with a pixel to spare
after it: "16000" is 41 pixels in the test machine's font, so it needs 44,
and was cut as in Zodi's screenshot. Measured in the window before this,
the same on seven more pages: Job Commands, Abilities (Effect, -32768 to
32767; icon and UI ids; a 32-bit DLC flags; "Inherits 6", what an
override shows at -1), Poaching (Cost, Sell Price), Encounters
(positions, unit ids), All Game Data (every number, 32-bit), UI Layouts
(positions and sizes, -10000 to 10000; frames and corners, to 100000)
and Sounds (loop points, to 2,000,000,000).

So a box here is as wide as the widest number it accepts, and never
narrower than the width it was given (84 in the forms, so a box whose
numbers fit keeps the look it had). The room around the number (border,
padding, arrows) is asked of the style in use, not written down: the
stylesheet goes on the application after the pages are built, and a width
worked out when a box is made would be the plain style's.

- `FittedSpinBox`, a whole number: as wide as its range's widest, so the
  box doesn't change width while somebody types.
- `FittedDoubleSpinBox`, a decimal: as wide as its range's ends or the
  number in it, whichever is wider. A 32-bit float shown exactly can run
  to fourteen characters (UI Layouts' opacity 0.000010000001), so these
  widen for the number they hold.
"""
from __future__ import annotations

import re

from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import (
    QDoubleSpinBox, QSizePolicy, QSpinBox, QStyle, QStyleOptionSpinBox,
)

#: The space a `QLineEdit` keeps on each side of its text (Qt's own
#: `horizontalMargin`, fixed at 2), and the room after the last digit: Qt
#: scrolls a line edit whose text and one pixel for the cursor don't fit
#: inside those margins, and its own size hint keeps two.
LINE_EDIT_MARGIN, CURSOR_ROOM = 2, 2


class _FitsItsNumbers:
    """What both boxes share: a width worked out from the texts they show."""

    def _setup_fit(self, at_least: int) -> None:
        #: The narrowest the box is, the width it had before.
        self.at_least = int(at_least)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def fit_texts(self) -> list:
        """The texts the box must show whole."""
        raise NotImplementedError

    def chrome_width(self) -> int:
        """The box's width less its number's room, as the style in use draws it."""
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        option.rect = QRect(0, 0, 400, max(1, self.height()))
        edit = self.style().subControlRect(QStyle.CC_SpinBox, option,
                                           QStyle.SC_SpinBoxEditField, self)
        return 400 - edit.width()

    def fitted_width(self) -> int:
        """The narrowest this box can be and show each of `fit_texts` whole."""
        self.ensurePolished()
        edit = self.lineEdit()
        edit.ensurePolished()
        metrics = edit.fontMetrics()
        margins = edit.textMargins()
        widest = max((metrics.horizontalAdvance(text) for text in self.fit_texts()), default=0)
        needed = (self.chrome_width() + widest + 2 * LINE_EDIT_MARGIN + CURSOR_ROOM
                  + margins.left() + margins.right())
        return max(self.at_least, needed)

    def sizeHint(self) -> QSize:                                        # noqa: N802
        return QSize(self.fitted_width(), super().sizeHint().height())

    def minimumSizeHint(self) -> QSize:                                 # noqa: N802
        return QSize(self.fitted_width(), super().minimumSizeHint().height())


    def setSpecialValueText(self, text: str) -> None:                  # noqa: N802
        super().setSpecialValueText(text)
        # Qt doesn't tell the layout this one, as it does a new range: an
        # override set to "Inherits 6" stayed 84 pixels wide (measured).
        self.updateGeometry()


def widest_digits(box, lowest, highest) -> str:
    """
    The widest text a whole number from `lowest` to `highest` can be, in
    the box's font: as many of its widest digit as the end's number has, a
    minus before the low end's where it is below 0. (-1 to 9999 is at most
    four digits wide, not a minus and four.)
    """
    metrics = box.lineEdit().fontMetrics()
    digit = max("0123456789", key=metrics.horizontalAdvance)
    texts = [digit * len(str(abs(int(end)))) for end in (lowest, highest) if end >= 0]
    texts += ["-" + digit * len(str(abs(int(end)))) for end in (lowest, highest) if end < 0]
    return max(texts, key=metrics.horizontalAdvance)


class FittedSpinBox(_FitsItsNumbers, QSpinBox):
    """A whole-number box as wide as the widest number its range allows."""

    def __init__(self, at_least: int = 84, parent=None):
        super().__init__(parent)
        self._setup_fit(at_least)

    def fit_texts(self) -> list:
        widest = widest_digits(self, self.minimum(), self.maximum())
        texts = [self.textFromValue(self.minimum()), self.textFromValue(self.maximum()), widest]
        texts = [self.prefix() + text + self.suffix() for text in texts]
        special = self.specialValueText()
        if special:
            # What the box shows at its lowest instead of the number, with
            # any number in it as wide as the range's: Abilities' "Inherits
            # 6" is "Inherits 255" on another ability, and the box keeps
            # one width from one to the next.
            texts.append(re.sub(r"\d+", widest.lstrip("-"), special))
        return texts


class FittedDoubleSpinBox(_FitsItsNumbers, QDoubleSpinBox):
    """A decimal box as wide as its range's ends or its number, whichever is wider."""

    def __init__(self, at_least: int = 84, parent=None):
        super().__init__(parent)
        self._setup_fit(at_least)
        # The box's own signal: its line edit's is held back while the box
        # writes a value into it, so a value loaded or stepped to went unseen.
        self.textChanged.connect(lambda _text: self.updateGeometry())

    def fit_texts(self) -> list:
        texts = [self.textFromValue(self.minimum()), self.textFromValue(self.maximum())]
        texts = [self.prefix() + text + self.suffix() for text in texts]
        texts.append(self.lineEdit().text())
        if self.specialValueText():
            texts.append(self.specialValueText())
        return texts
