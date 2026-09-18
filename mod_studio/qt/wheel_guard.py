"""
Stops the scroll wheel editing a control it is merely passing over.

Reported by the community:

    "When using the scroll wheel to scroll up and down entries, if the
     mouse touches a drop-down menu for even a frame, it will also modify
     the drop-down entry while continuing to scroll past."

Qt's default: a `QComboBox` or a spin box under the pointer takes the wheel
whether or not anybody clicked it. On a form that scrolls, that makes
scrolling destructive - the page moves AND every control the pointer crossed
changes value on the way. Worse, the damage is silent: the person is looking
at where they are scrolling to, not at the rows going past, and the edits
are real edits that ship in the mod.

**The rule here is focus.** A control changes on the wheel only when it has
been clicked into. Otherwise the wheel belongs to whatever is scrolling, and
the event is handed to the nearest scroll area so the page moves normally.

The reporter suggested a hover delay instead - only edit after the pointer
has rested for a few frames. Focus was chosen over that for three reasons:
it is what the surrounding desktop already does, it has no timer to tune and
no state to get wrong, and a delay still edits the control eventually, which
means scrolling slowly through a long form is still destructive. Focus makes
the destructive case impossible rather than unlikely.

**Focus alone did not work on real hardware.** Qt gives focus to a
`WheelFocus` control under the pointer BEFORE the wheel event is delivered -
`QApplication::notify` calls `giveFocusAccordingToFocusPolicy` for every real
wheel event - and spin boxes and dropdowns both default to `WheelFocus`. So
by the time this filter saw the event the control already had focus, and the
guard stood aside. Reported again from real use, and then reproduced with
real X11 wheel events (xdotool, under Xvfb): one tick changed a spin box and
a dropdown and moved focus into it. The synthetic events the first tests
sent are never "spontaneous", so Qt skipped that step for them, which is why
they passed. The wheel is now taken out of these controls' focus policy as
each one is polished: a click or Tab still focuses them, and once focused
the wheel changes them - which is exactly the behaviour asked for.

Installed once on the application rather than on each widget, because there
are hundreds of these across fifteen pages and "remember to use the
non-scrolling variant" is exactly the instruction that gets followed most of
the time.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox, QAbstractScrollArea, QApplication, QComboBox,
)

#: The controls that edit their own value on a wheel tick.
#:
#: Sliders and scroll bars are deliberately absent: dragging is not their
#: only interaction and a wheel over one is a reasonable way to move it.
#: These two are the ones that hold a value somebody has to notice changing.
GUARDED = (QComboBox, QAbstractSpinBox)


class WheelGuard(QObject):
    """Application event filter implementing the rule above."""

    def eventFilter(self, watched, event):                    # noqa: N802
        if event.type() == QEvent.Polish:
            if isinstance(watched, GUARDED):
                no_wheel_focus(watched)
            return False
        if event.type() != QEvent.Wheel:
            return False
        if not isinstance(watched, GUARDED):
            return False
        if watched.hasFocus():
            # Clicked into, so the wheel is meant for it.
            return False
        # Handed to whatever is scrolling, so the page still moves. Without
        # this the wheel would simply be swallowed and the form would feel
        # stuck wherever a dropdown happened to be.
        area = self._scroll_area(watched)
        if area is not None:
            QApplication.sendEvent(area.viewport(), event)
        return True

    @staticmethod
    def _scroll_area(widget):
        """The nearest scrolling ancestor, or None if nothing scrolls."""
        parent = widget.parentWidget()
        while parent is not None:
            if isinstance(parent, QAbstractScrollArea):
                return parent
            parent = parent.parentWidget()
        return None


def no_wheel_focus(widget) -> None:
    """Keeps click and Tab focus, drops wheel focus - see the module docstring."""
    if widget.focusPolicy() == Qt.WheelFocus:
        widget.setFocusPolicy(Qt.StrongFocus)


def install(app) -> WheelGuard:
    """
    Installs the guard and returns it.

    The instance is returned so the caller keeps a reference: an event
    filter whose only reference is the install call is collected, and the
    filter silently stops working - which would look exactly like the bug
    coming back.
    """
    guard = WheelGuard(app)
    app.installEventFilter(guard)
    return guard
