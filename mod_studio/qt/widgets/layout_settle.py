"""
Finishing a layout NOW, rather than leaving half of it until later.

### The fault

Reported as a flash: for a moment after a click, text appears out of
position and then settles. The reporter's description was "the contents have
no where to go and mess up the layout, then the page extends and they drop
into it", which is close to what happens.

Showing or hiding a widget lays IT out immediately and at the right place -
measured, the rows are already where they end up. What is not immediate is
the PAGE. Forms sit in a `QScrollArea` with `setWidgetResizable(True)`, and
that resizes its widget when a LayoutRequest is DELIVERED to it. That event
is POSTED, so between the click and the next trip round the event loop the
content is its new size inside a page that is still its old one - measured
on Job Commands, a holder 847px tall holding 942px of form. Anything painted
in that window is painted against the old page.

### Why it lives here rather than in one caller

Two different actions change how much a form contains, and both had the
fault:

- opening or closing a `CollapsibleSection`
- the **Hide unknown fields** and **Hide comments** toggles, which hide rows
  right down a page

The first was fixed on `CollapsibleSection` alone and the second went on
flashing, which is the same mistake as fixing a scrollbar on one page while
eight siblings keep it. One function, called by both, so a third kind of
show/hide gets it by calling one line rather than by rediscovering the
cause.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QWidget


def settle_layout(widget: QWidget) -> None:
    """
    Re-lays `widget` and every ancestor at once, before the caller returns.

    Walking UP is the point. Activating the widget's own layout re-lays it
    out inside the size it already HAS; it is the ancestor - ultimately the
    scroll area - that owns the decision about how big the widget should be.
    A version that called `activate()` without the event below left 184
    widgets on Jobs still moving after the click.
    """
    while widget is not None:
        layout = widget.layout()
        if layout is not None:
            layout.activate()
        # Sent, not posted. Posting it is what the caller was already doing
        # by accident, and posting is the fault.
        QApplication.sendEvent(widget, QEvent(QEvent.LayoutRequest))
        widget = widget.parentWidget()
