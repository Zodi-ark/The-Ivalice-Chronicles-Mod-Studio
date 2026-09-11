"""
The two packed-byte panels on Abilities' override layer.

Both edit ONE byte presented as a set of checkboxes, which is why neither
can be a `FlagFieldPanel`: that panel's value is a comma-joined name list
written straight into XML, and these pack to an integer through
`nxd_data`'s own bit layout. Using the wrong one would write `"Reflect,
Silence"` into a column the game reads as a number.

**Three things here are counter-intuitive and all three are correct.**

- **Some flags are stored inverted.** Ticking the box CLEARS the underlying
  bit. `nxd_data.pack_flag_group` owns that mapping and this file never
  reproduces it - the panels show effective state and let the engine do the
  packing, exactly as FFTPatcher and Zodi's `flag_codex.html` present it.
- **"Not set" is not byte 0.** An unset group inherits vanilla behaviour and
  has no byte to decode. Showing a fabricated 0 would be actively wrong,
  because all-unchecked packs to 209 for Flagset II rather than 0 - so
  decoding 0 would draw every inverted flag as ticked while nothing is
  overridden at all.
- **Each of the four groups is written separately.** Two share a physical
  column (`Flags12`, `Flags34`) and `write_override_action_edits` does a
  targeted read-modify-write per `FlagsGroup<n>`, so editing one never
  clobbers its sibling.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)

from ... import constants as c
from ... import nxd_data


def baseline_note(raw_value) -> str:
    """The same sentence the Tkinter panels show under each group."""
    if raw_value is None or raw_value == c.OVERRIDE_NOT_SET:
        return "Vanilla: not overridden (inherits hardcoded behaviour)."
    return (f"Vanilla: already overridden in the base data "
            f"(value {int(raw_value)}).")


class _PackedBytePanel(QWidget):
    """Shared behaviour: an include box, All/Clear, checkboxes, a note."""

    edited = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.is_unknown = False
        self._loading = False
        self.boxes: dict = {}

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(2)

        self.box = QGroupBox(title.replace("&", "&&"))
        inner = QVBoxLayout(self.box)
        inner.setContentsMargins(8, 4, 8, 6)
        inner.setSpacing(2)

        header = QHBoxLayout()
        self.include = QCheckBox()
        self.include.setToolTip(
            "Tick to write this over the ability's vanilla behaviour. "
            "Unticked leaves it inheriting.")
        self.include.toggled.connect(self._on_include)
        header.addWidget(self.include)
        header.addWidget(QLabel("Override"))
        header.addSpacing(8)
        # All is kept here, unlike FlagFieldPanel.
        #
        # That button was removed from the flag panel because no vanilla
        # map-trap row sets more than two of five flags, so "all" was not a
        # state the game had. These are different data: a flag byte is a set
        # of independent behaviours and vanilla rows do set many at once, so
        # both bulk actions are meaningful here.
        all_button = QPushButton("All")
        all_button.clicked.connect(lambda: self._set_all(True))
        header.addWidget(all_button)
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(lambda: self._set_all(False))
        header.addWidget(clear_button)
        header.addStretch(1)
        inner.addLayout(header)

        self.grid = QGridLayout()
        self.grid.setSpacing(2)
        inner.addLayout(self.grid)

        self.note = QLabel("")
        self.note.setProperty("role", "muted")
        self.note.setWordWrap(True)
        inner.addWidget(self.note)
        column.addWidget(self.box)

    @property
    def included(self) -> bool:
        return self.include.isChecked()

    def _on_flag(self, _on) -> None:
        if self._loading:
            return
        if not self.include.isChecked():
            self.include.setChecked(True)
            return
        self.edited.emit()

    def _on_include(self, _on) -> None:
        if self._loading:
            return
        self.edited.emit()

    def _set_all(self, on: bool) -> None:
        self._loading = True
        try:
            for box in self.boxes.values():
                box.setChecked(on)
        finally:
            self._loading = False
        if not self.include.isChecked():
            self.include.setChecked(True)
        else:
            self.edited.emit()

    def apply_display(self, hide_notes: bool, hide_unknown: bool,
                      hide_comments: bool) -> None:
        return


class AbilityFlagGroupPanel(_PackedBytePanel):
    """One Flagset (I-IV): a single override byte, shown as its flags."""

    def __init__(self, group_index: int, parent=None):
        super().__init__(c.ABILITY_FLAG_GROUP_LABELS[group_index],
                         parent=parent)
        self.group_index = group_index
        self.field_name = f"FlagsGroup{group_index}"
        items = [f for f in c.ABILITY_FLAG_DEFS if f[2] == group_index]

        row = 0
        for flag_id, label, _group, inverted, blank in items:
            if blank:
                spacer = QLabel("(unused)")
                spacer.setProperty("role", "muted")
                self.grid.addWidget(spacer, row, 0)
                row += 1
                continue
            # The dagger marks a flag stored as the opposite bit, the same
            # marker FFTPatcher uses. Its meaning is in the panel's tooltip
            # rather than only in a blurb somebody may have scrolled past.
            check = QCheckBox(label + (" \u2020" if inverted else ""))
            if inverted:
                check.setToolTip(
                    "Stored as the opposite bit - ticking this box clears "
                    "the underlying flag.")
            check.toggled.connect(self._on_flag)
            self.boxes[flag_id] = check
            self.grid.addWidget(check, row, 0)
            row += 1

    def load(self, raw_value, included: bool) -> None:
        self._loading = True
        try:
            if raw_value in (None, c.OVERRIDE_NOT_SET):
                # No byte to decode - see the module docstring. Byte 0 is
                # not the same thing as "not set" for an inverted flag.
                for box in self.boxes.values():
                    box.setChecked(False)
            else:
                states = nxd_data.unpack_flag_group(self.group_index,
                                                    int(raw_value))
                for flag_id, box in self.boxes.items():
                    box.setChecked(bool(states.get(flag_id, False)))
            self.include.setChecked(bool(included))
            self.note.setText(baseline_note(raw_value))
        finally:
            self._loading = False

    def get_value(self) -> int:
        return nxd_data.pack_flag_group(
            self.group_index,
            {flag_id: box.isChecked() for flag_id, box in self.boxes.items()})

    def get_value_str(self) -> str:
        return str(self.get_value())


class ElementFlagPanel(_PackedBytePanel):
    """The Element column: eight element bits in one byte."""

    def __init__(self, parent=None):
        super().__init__("Element", parent=parent)
        self.field_name = "Element"
        for index, (name, _value) in enumerate(c.ABILITY_ELEMENT_VALUES):
            check = QCheckBox(name)
            check.toggled.connect(self._on_flag)
            self.boxes[name] = check
            self.grid.addWidget(check, index // 4, index % 4)

    def load(self, raw_value, included: bool) -> None:
        self._loading = True
        try:
            byte = (0 if raw_value in (None, c.OVERRIDE_NOT_SET)
                    else int(raw_value))
            states = nxd_data.unpack_element_value(byte)
            for name, box in self.boxes.items():
                box.setChecked(bool(states.get(name, False)))
            self.include.setChecked(bool(included))
            self.note.setText(baseline_note(raw_value))
        finally:
            self._loading = False

    def get_value(self) -> int:
        return nxd_data.pack_element_value(
            {name: box.isChecked() for name, box in self.boxes.items()})

    def get_value_str(self) -> str:
        return str(self.get_value())
