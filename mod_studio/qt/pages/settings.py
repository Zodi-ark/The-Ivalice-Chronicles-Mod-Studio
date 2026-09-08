"""
Settings.

Pinned below Game Updates, under the same divider: neither is a step in
making a mod.

Every choice here is written to `ui_settings.json` the moment it is made,
the same store the field-note toggles already use. A preference that has to
be set again every launch is not a preference, it is a chore - and the
project already decided where these live, so this adds keys to
`ui_settings.DEFAULTS` rather than inventing a second store.

Two things are deliberately honest rather than tidy:

- The backdrop options say when they are unavailable. Mica and Acrylic need
  Windows 11 22H2 or newer; on anything else the radio button is disabled
  and says why, instead of offering a tick that silently does nothing.
- "Plain" is a first-class option, not a fallback. Mica and Acrylic are
  composited by the desktop manager and cost real frames on weak hardware,
  which is exactly the machine a lot of modders are on.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup, QGroupBox, QLabel, QRadioButton, QVBoxLayout, QWidget,
)

from ... import ui_settings
from .. import win_native

APPEARANCES = [
    ("system", "Follow Windows", "Match the light or dark setting Windows is using, and change with it."),
    ("light", "Light", "This is a basic light theme."),
    ("dark", "Dark", "This is a basic dark theme."),
    ("phthalo", "Phthalo Green", "A deep blue-green theme."),
]

BACKDROPS = [
    ("mica", "Mica", "A subtle tint of your desktop wallpaper behind the window."),
    ("acrylic", "Acrylic", "A stronger frosted blur. Heavier than Mica."),
    ("none", "Plain", "No transparency. The lightest option, and the one to pick on older hardware."),
]


class SettingsPage(QWidget):
    """Emits when a choice changes; the shell applies it."""

    appearance_changed = Signal(str)
    backdrop_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        saved = ui_settings.load()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(10)

        heading = QLabel("Settings")
        heading.setProperty("role", "heading")
        outer.addWidget(heading)

        blurb = QLabel("Your choices here are saved and used next time.")
        blurb.setProperty("role", "muted")
        outer.addWidget(blurb)

        outer.addWidget(self._appearance_box(saved.get("appearance", "system")))
        outer.addWidget(self._backdrop_box(saved.get("window_backdrop", "mica")))
        outer.addStretch(1)

    # -- appearance ----------------------------------------------------------

    def _appearance_box(self, current: str) -> QGroupBox:
        box = QGroupBox("Appearance")
        column = QVBoxLayout(box)
        self.appearance_group = QButtonGroup(self)
        self.appearance_buttons = {}
        for value, label, note in APPEARANCES:
            button = QRadioButton(label)
            button.setChecked(value == current)
            button.toggled.connect(
                lambda on, v=value: self._on_appearance(v) if on else None)
            self.appearance_group.addButton(button)
            self.appearance_buttons[value] = button
            column.addWidget(button)
            hint = QLabel("   " + note)
            hint.setProperty("role", "muted")
            hint.setWordWrap(True)
            column.addWidget(hint)
        return box

    def _on_appearance(self, value: str) -> None:
        ui_settings.save(appearance=value)
        self.appearance_changed.emit(value)

    # -- backdrop ------------------------------------------------------------

    def _backdrop_box(self, current: str) -> QGroupBox:
        box = QGroupBox("Window material")
        column = QVBoxLayout(box)
        supported = win_native.is_supported()

        if not supported:
            unavailable = QLabel(
                "Mica and Acrylic need Windows 11 (22H2 or newer). "
                "This machine will use a plain window.")
            unavailable.setProperty("role", "attention")
            unavailable.setWordWrap(True)
            column.addWidget(unavailable)

        self.backdrop_group = QButtonGroup(self)
        self.backdrop_buttons = {}
        for value, label, note in BACKDROPS:
            button = QRadioButton(label)
            usable = supported or value == "none"
            button.setEnabled(usable)
            # With no support, "Plain" is what is actually in effect, so it
            # is what should be shown selected - a ticked option the machine
            # is ignoring would be a small lie.
            #
            # The STORED preference is left alone though, deliberately. The
            # same settings file follows a user to a newer machine, and
            # silently rewriting their choice to "none" because today's
            # hardware cannot honour it would lose a preference they never
            # changed. Shown: what is in effect. Stored: what was asked for.
            button.setChecked(value == (current if supported else "none"))
            button.toggled.connect(
                lambda on, v=value: self._on_backdrop(v) if on else None)
            self.backdrop_group.addButton(button)
            self.backdrop_buttons[value] = button
            column.addWidget(button)
            hint = QLabel("   " + note)
            hint.setProperty("role", "muted")
            hint.setWordWrap(True)
            column.addWidget(hint)
        return box

    def _on_backdrop(self, value: str) -> None:
        ui_settings.save(window_backdrop=value)
        self.backdrop_changed.emit(value)
