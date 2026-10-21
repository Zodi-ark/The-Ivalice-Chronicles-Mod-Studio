"""
The Map Editor's Light the map window (Zodi, 12 October: "generate all the
lighting textures ... with the ability to edit the position of the light
source and color of the source", the border texture and lut_chara).

A sun, the sky and lamps, set here; Preview draws the map with them, Make
puts the textures they make into the mod, with the table rows naming them
(`map_lighting.light_map`). The light is remembered for each map, beside
the textures made (`light_folder`), with the border's color since 20
October, and travels with the map: Save for editing puts it in the folder,
and Load edited brings it back (`map_editor.light_file`).
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QSpinBox, QTableWidget, QVBoxLayout, QWidget,
)

from ... import map_lighting as ml
from ... import paths
from ..workers import Worker, run_in_thread

#: Where Make keeps a map's textures and its light, in Mod Studio's own folder.
LIGHT_FOLDER = "map_lighting"
LIGHT_FILE = "light.json"
EVERY = "Every lighting"


def light_folder(number: int) -> Path:
    return paths.local_data_dir() / LIGHT_FOLDER / f"map_{number:03d}"


#: The key `light.json` keeps the border's color under, beside the light's
#: own (`map_lighting.Light.from_dict` passes over it).
BORDER_KEY = "border_colour"


def saved_light(number: int) -> ml.Light:
    """The light last made for map `number`, or the default."""
    try:
        return ml.Light.from_dict(json.loads((light_folder(number) / LIGHT_FILE).read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return ml.Light()


def saved_border(number: int):
    """The border's color last made for map `number` (`(r, g, b)`), or None."""
    try:
        colour = json.loads((light_folder(number) / LIGHT_FILE).read_text(encoding="utf-8")).get(BORDER_KEY)
        return tuple(int(c) for c in colour)[:3] if colour and len(colour) >= 3 else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def save_light(number: int, light: ml.Light, border=None) -> None:
    """Keeps map `number`'s light, and the border's color when given (`saved_border`)."""
    folder = light_folder(number)
    folder.mkdir(parents=True, exist_ok=True)
    data = light.to_dict()
    if border is not None:
        data[BORDER_KEY] = [int(c) for c in tuple(border)[:3]]
    (folder / LIGHT_FILE).write_text(json.dumps(data, indent=1), encoding="utf-8")


class LightWorker(Worker):
    """`map_lighting.light_map` off the GUI thread, its textures saved as PNG in `folder`."""

    def __init__(self, folder, **arguments):
        super().__init__()
        self.folder, self.arguments = Path(folder), arguments

    def run(self):
        made = ml.light_map(progress=lambda done, total: self.progress.emit(done, total), **self.arguments)
        return made, ml.save_made(made, self.folder)


#: The swatch's own name: its style names it, so the color reaches it alone.
SWATCH = "colorSwatch"


class ColourButton(QPushButton):
    """A color, shown as a swatch, picked with the system's color window."""

    def __init__(self, colour=(255, 255, 255), title: str = "Color", parent=None):
        super().__init__(parent)
        self.title = title
        self.setObjectName(SWATCH)
        self.setFixedWidth(64)
        self.set_colour(colour)
        self.clicked.connect(self.choose)

    def set_colour(self, colour) -> None:
        self.colour = tuple(int(c) for c in colour)[:3]
        red, green, blue = self.colour
        # Named by the swatch's object name, not every QPushButton: a style
        # set on a widget reaches the widgets inside it, and the color
        # window's buttons (Pick Screen Color, OK, Cancel) took the swatch's
        # color (Zodi's screenshot, 19 October).
        self.setStyleSheet(f"QPushButton#{SWATCH} {{ background-color: rgb({red}, {green}, {blue}); "
                           f"border: 1px solid palette(mid); border-radius: 3px; min-height: 20px; }}")
        self.setToolTip(f"{self.title}: {red}, {green}, {blue}")

    def choose(self) -> None:
        # The window the swatch is in, not the swatch, as the color window's
        # owner: nothing of the swatch's own style is passed down to it.
        picked = QColorDialog.getColor(QColor(*self.colour), self.window(), self.title)
        if picked.isValid():
            self.set_colour((picked.red(), picked.green(), picked.blue()))


def _spin(low: int, high: int, value: float, suffix: str = "") -> QSpinBox:
    box = QSpinBox()
    box.setRange(low, high)
    box.setValue(int(round(value)))
    if suffix:
        box.setSuffix(suffix)
    return box


class LightDialog(QDialog):
    """The light for the map shown on `page` (a `MapEditorPage`), and what to make with it."""

    LAMP_COLUMNS = ("X", "Z", "Height", "Color", "Strength", "Reach")

    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.number = page.number
        self.busy = False
        self.setWindowTitle(f"Light map {self.number:03d}")
        self.setModal(False)
        light = saved_light(self.number)
        layout = QVBoxLayout(self)
        intro = QLabel("Makes the map's lighting textures, its border texture and its units' lighting "
                       "from a sun, the sky and lamps. Preview draws them on the map; Make puts them "
                       "in your mod.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        sun = QGroupBox("Sun")
        form = QFormLayout(sun)
        self.sun_turn = _spin(0, 359, light.sun_turn, " degrees")
        self.sun_turn.setWrapping(True)
        self.sun_turn.setToolTip("Where the sun shines from: 0 north, 90 east, 180 south, 270 west.")
        self.sun_height = _spin(0, 90, light.sun_height, " degrees")
        self.sun_height.setToolTip("How high the sun is: 0 on the horizon, 90 straight above.")
        self.sun_colour = ColourButton(light.sun_colour, "The sun's color")
        self.sun_strength = _spin(0, 300, light.sun_strength * 100, "%")
        form.addRow("From", self.sun_turn)
        form.addRow("Height", self.sun_height)
        form.addRow("Color", self.sun_colour)
        form.addRow("Strength", self.sun_strength)

        sky = QGroupBox("Sky")
        form = QFormLayout(sky)
        self.sky_colour = ColourButton(light.sky_colour, "The sky's color")
        self.sky_strength = _spin(0, 300, light.sky_strength * 100, "%")
        self.corner_shade = _spin(0, 100, light.corner_shade * 100, "%")
        self.corner_shade.setToolTip("How much darker corners and creases are, hidden from the sky.")
        form.addRow("Color", self.sky_colour)
        form.addRow("Strength", self.sky_strength)
        form.addRow("Shade in corners", self.corner_shade)

        shadows = QGroupBox("Shadows")
        form = QFormLayout(shadows)
        self.shadows = QCheckBox("Cast shadows")
        self.shadows.setChecked(bool(light.shadows))
        self.softness = _spin(0, 100, light.softness * 100, "%")
        form.addRow(self.shadows)
        form.addRow("Softness", self.softness)

        top = QHBoxLayout()
        for box in (sun, sky, shadows):
            top.addWidget(box)
        layout.addLayout(top)

        lamps = QGroupBox("Lamps")
        lamp_layout = QVBoxLayout(lamps)
        hint = QLabel("A lamp stands over a tile (X, Z), its height in steps above the ground there; "
                      "its reach is in tiles.")
        hint.setWordWrap(True)
        hint.setProperty("role", "muted")
        lamp_layout.addWidget(hint)
        self.lamps = QTableWidget(0, len(self.LAMP_COLUMNS))
        self.lamps.setHorizontalHeaderLabels(self.LAMP_COLUMNS)
        self.lamps.verticalHeader().setVisible(False)
        self.lamps.setMinimumHeight(110)
        lamp_layout.addWidget(self.lamps)
        buttons = QHBoxLayout()
        self.add_lamp_button = QPushButton("Add lamp")
        self.add_lamp_button.clicked.connect(lambda: self.add_lamp())
        self.remove_lamp_button = QPushButton("Remove lamp")
        self.remove_lamp_button.clicked.connect(self.remove_lamp)
        buttons.addWidget(self.add_lamp_button)
        buttons.addWidget(self.remove_lamp_button)
        buttons.addStretch(1)
        lamp_layout.addLayout(buttons)
        layout.addWidget(lamps)
        for lamp in light.lamps:
            self.add_lamp(lamp)

        make = QGroupBox("Make")
        form = QFormLayout(make)
        self.make_lighting = QCheckBox("Lighting textures, for every texture group that has one")
        self.make_lighting.setChecked(True)
        border_row = QWidget()
        row = QHBoxLayout(border_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.make_border = QCheckBox("The border's texture, in")
        self.make_border.setChecked(True)
        self.border_colour = ColourButton(saved_border(self.number) or self._ground_colour(), "The border's color")
        row.addWidget(self.make_border)
        row.addWidget(self.border_colour)
        row.addStretch(1)
        self.make_units = QCheckBox("Units' lighting (lut_chara)")
        self.make_units.setChecked(True)
        self.which = QComboBox()
        self.which.addItem(EVERY, None)
        scene = getattr(page, "scene", None)
        if scene is not None and getattr(scene, "lightings", None):
            from .map_editor import lighting_words
            for index, word in enumerate(lighting_words(scene.lightings)):
                self.which.addItem(word, index)
        self.which.setToolTip("Every lighting the map has (its story and random battles) gets this light, "
                              "all its rows naming the same textures, so it is lit one way in every battle "
                              "until Put back the game's look; or one of them gets it alone.")
        form.addRow(self.make_lighting)
        form.addRow(border_row)
        form.addRow(self.make_units)
        form.addRow("For", self.which)
        layout.addWidget(make)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.note = QLabel("")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.preview_button = QPushButton("Preview")
        self.preview_button.setToolTip("Draws the map with this light, quickly, without putting it in your mod.")
        self.preview_button.clicked.connect(lambda: self.run(preview=True))
        self.make_button = QPushButton("Make")
        self.make_button.setToolTip("Makes the textures in full and puts them in your mod.")
        self.make_button.clicked.connect(lambda: self.run(preview=False))
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        for button in (self.preview_button, self.make_button, self.close_button):
            actions.addWidget(button)
        layout.addLayout(actions)

    # -- the light -----------------------------------------------------------------

    def _ground_colour(self) -> tuple:
        try:
            return self.page.border_tint(self.number)
        except Exception:                                   # noqa: BLE001
            return ml.ground_colour(None)

    def add_lamp(self, lamp=None) -> None:
        if lamp is None:
            picked = getattr(self.page, "picked", None) or []
            x, z = (picked[0][0] + 0.5, picked[0][1] + 0.5) if picked else (0.5, 0.5)
            lamp = ml.Lamp(x=x, z=z)
        row = self.lamps.rowCount()
        self.lamps.insertRow(row)
        self.lamps.setCellWidget(row, 0, _spin(-4, 40, lamp.x - 0.5))
        self.lamps.setCellWidget(row, 1, _spin(-4, 40, lamp.z - 0.5))
        self.lamps.setCellWidget(row, 2, _spin(0, 60, lamp.height))
        self.lamps.setCellWidget(row, 3, ColourButton(lamp.colour, "The lamp's color"))
        self.lamps.setCellWidget(row, 4, _spin(0, 500, lamp.strength * 100, "%"))
        self.lamps.setCellWidget(row, 5, _spin(1, 20, lamp.reach))

    def remove_lamp(self) -> None:
        row = self.lamps.currentRow()
        if row < 0:
            row = self.lamps.rowCount() - 1
        if row >= 0:
            self.lamps.removeRow(row)

    def light(self) -> ml.Light:
        lamps = []
        for row in range(self.lamps.rowCount()):
            cell = self.lamps.cellWidget
            lamps.append(ml.Lamp(x=cell(row, 0).value() + 0.5, z=cell(row, 1).value() + 0.5,
                                 height=cell(row, 2).value(), colour=cell(row, 3).colour,
                                 strength=cell(row, 4).value() / 100, reach=cell(row, 5).value()))
        return ml.Light(sun_turn=self.sun_turn.value(), sun_height=self.sun_height.value(),
                        sun_colour=self.sun_colour.colour, sun_strength=self.sun_strength.value() / 100,
                        sky_colour=self.sky_colour.colour, sky_strength=self.sky_strength.value() / 100,
                        corner_shade=self.corner_shade.value() / 100, shadows=self.shadows.isChecked(),
                        softness=self.softness.value() / 100, lamps=lamps)

    # -- making it -------------------------------------------------------------------

    def run(self, preview: bool) -> None:
        if self.busy or self.page.number != self.number:
            if self.page.number != self.number:
                self.note.setText(f"The Map Editor shows another map now: open Light the map from map "
                                  f"{self.page.number:03d}.")
            return
        if not (self.make_lighting.isChecked() or self.make_border.isChecked() or self.make_units.isChecked()):
            self.note.setText("Tick at least one thing to make.")
            return
        arguments = self.page.light_arguments(self.number)
        if arguments is None:
            self.note.setText("The map isn't read yet.")
            return
        which = self.which.currentData()
        arguments.update(light=self.light(), which=which, lighting=self.make_lighting.isChecked(),
                         border=self.make_border.isChecked(), border_tint=self.border_colour.colour,
                         units=self.make_units.isChecked(),
                         quality="preview" if preview else "full", resolution=256 if preview else 1024)
        folder = light_folder(self.number) / ("preview" if preview else "made")
        self.busy = True
        self._buttons()
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.note.setText("Lighting the map..." if not preview else "Lighting a preview...")
        self._preview = preview
        run_in_thread(LightWorker(folder, **arguments), on_finished=self._done, on_failed=self._failed,
                      on_progress=self._on_progress)

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)

    def _buttons(self) -> None:
        for button in (self.preview_button, self.make_button):
            button.setEnabled(not self.busy)

    def _done(self, result) -> None:
        made, files = result
        self.busy = False
        self._buttons()
        self.progress.setVisible(False)
        which = self.which.currentData()
        if self._preview:
            self.page.set_light_preview(self.number, files, made.rows, which)
            self.note.setText(f"Preview drawn: {len(files)} textures. Make puts them in your mod.")
        else:
            save_light(self.number, self.light(), self.border_colour.colour)
            self.page.put_light(self.number, made, files, which)
            self.note.setText(f"Made {len(files)} textures" + (f" and {sum(len(f) for f in made.rows.values())} "
                                                              f"table rows" if made.rows else "")
                              + ": they go into your mod." + "".join(f" {n[0].upper()}{n[1:]}." for n in made.notes))

    def _failed(self, message: str) -> None:
        self.busy = False
        self._buttons()
        self.progress.setVisible(False)
        self.note.setText(f"The light couldn't be made: {message}")

    def closeEvent(self, event) -> None:                              # noqa: N802
        self.page.clear_light_preview()
        super().closeEvent(event)
