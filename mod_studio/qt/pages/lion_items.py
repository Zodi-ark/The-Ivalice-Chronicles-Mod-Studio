"""
(The twenty fifth session, 16 November 2026) War of the Lions' 40 items on the Items page.

Zodi's first point of 16 November: "Like we made Dark Knight and Onion Onion In Mod Studio Framework we should do the
same for WotLs items from WotL Restoration to be able to be used by the framework so they can be edited on the Items
page". His choices: "Always listed (Recommended)" (every mod sees them after the game's items; only a mod that changes
or uses one is written as needing the framework), and, asked which of two designs edits one, "I go with your
recommendations": **the New Content page's item sheet, shown inside the Items page for these 40** (said to him before
it was built; the other way was the Items page's own fields mapped onto rows the game's tables don't have).

Why the sheet: nothing of the 40 is in the game (`claude/wotl-items-research.md`), so each is a whole item Mod Studio
Framework gives it, in `item.json`'s format (`mod_items.ModItem`), which is what the sheet edits and what his tests 58
to 64 passed with. The Items page's own form edits one item through seven of the game's tables, a row each; the 40
have no row in any of them.

`LionItemPane` is the sheet's page here (`side_quests.ItemSheet`'s notes say what a page gives it). It holds the item
shown as a `mod_items.ItemEdit` (`wotl_items.edit_of`) and, after every change, keeps what the mod has of it
(`wotl_items.kept` into `state.wotl_items`, a picture of the mod's own into `state.wotl_art`), or nothing where the
item is the framework's own again. Export and General Setup write and read both (`wotl_items.write`, `read`,
`read_art`).

(The thirty second session, his ask of 17 November: "can you make the layout of for the WotL items closer to that of
the original items for the vanilla items page") The sheet's parts are laid out here as the page lays out one of the
game's items (`sheet_as_items_page`, `side_quests.ItemSheet._items_page_layout`): its Sprite Texture and Art Texture
in a narrow column beside its words, then Battle Sprite, Base Item Data, Additional Data, Equip Bonus and Shop
Availability, one under another. The New Content page keeps the sheet's own layout.

What differs from a mod's own item on this sheet, each by one of the sheet's answers:
- its icon is the framework's own for its number (Zodi's art of 16 November) until another is chosen: the list under
  its textures starts with it, and the textures' menu puts a picture of the mod's own aside for it;
- no town of the mod's can sell it (a town's Outfitter lists its mod's own items by name), so the sheet says nothing
  of the mod's towns; the game's towns are ticked as for any item;
- it may be sold from no point of the story at all (War of the Lions' own are: `mod_items.NEVER_SOLD`), the list's
  last choice;
- its name is its words' name: nothing else names it (units and treasures name the 40 by number).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ... import game_install
from ... import mod_items as mi
from ... import ui_settings
from ... import wotl_items as wl
from ..widgets.layout_settle import retire
from . import job_tabs as jt
from . import side_quests as sq
from .items import SHOP_POINT_NEVER

#: Over the sheet: what these items are, and what changing or using one asks of the mod.
LION_NOTE = ("One of War of the Lions' items, which Mod Studio Framework gives the game. A mod that changes it or "
             "uses it needs Mod Studio Framework.")
#: The button that takes the mod's changes off the item shown, and its tip (the Encounters page's "As the game has
#: it" and its tip, for an item the framework has).
AS_FRAMEWORK = "As the framework has it"
AS_FRAMEWORK_TIP = "Takes the mod's changes off this item"
#: The first choice of the list under its textures, and the textures' menu's line that puts a picture of the mod's
#: own aside for it.
OWN_ICON = "Its own icon"
USE_OWN_ICON = "Use its own icon"
#: How the Items page's list and title say one of the 40 (the game's items' own way: its number, then its name).
LISTED = "{number:03d} - {name}"


class _Kept:
    """The sheet's `edits_changed`: what the mod has of the item is kept first, then the pane says it changed."""

    def __init__(self, pane: "LionItemPane"):
        self.pane = pane

    def emit(self) -> None:
        self.pane.keep()
        self.pane.changed.emit()


class LionItemPane(sq.ItemSheet, QWidget):
    """The Items page's right side while one of War of the Lions' 40 is picked: the item sheet over that item."""

    #: Something of the item shown changed (kept already).
    changed = Signal()
    #: Its name in the page's list is to be said again.
    named = Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.number: Optional[int] = None
        self.edit: Optional[mi.ItemEdit] = None
        self.field_widgets: dict = {}
        self.item_sheet_widgets: dict = {}
        self.item_foot = None
        self.item_sheet: Optional[QWidget] = None
        self._building = False
        #: The suites' answers to the dialogs (`_ask`), first in first out.
        self.answers: list = []
        self.edits_changed = _Kept(self)

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self.note = sq.muted(LION_NOTE)
        top.addWidget(self.note, 1)
        self.reset_button = QPushButton(AS_FRAMEWORK)
        self.reset_button.setToolTip(AS_FRAMEWORK_TIP)
        self.reset_button.clicked.connect(lambda _c=False: self.as_framework())
        top.addWidget(self.reset_button)
        column.addLayout(top)
        self.message = QLabel("")
        self.message.setProperty("role", "warn")
        self.message.setWordWrap(True)
        self.message.setVisible(False)
        column.addWidget(self.message)
        self.holder, self._sheet_column = jt._box()
        column.addWidget(self.holder, 1)

    # -- the item shown ------------------------------------------------------------------------------------------

    def show_item(self, number: int, again: bool = False) -> None:
        """The sheet over one of the 40 as the mod has it now (`again`: the same item's sheet made again, its place
        kept). Made with the window's painting held and laid out before it is let go, as the New Content page's
        (`SideQuestsPage._show_item_middle`)."""
        old, place = self.item_sheet, 0
        if again and old is not None and number == self.number:
            scroll = old.findChild(QScrollArea)
            place = scroll.verticalScrollBar().value() if scroll is not None else 0
        else:
            self.edit = wl.edit_of(number, getattr(self.state, "wotl_items", None),
                                   getattr(self.state, "wotl_art", None))
            self._say("")
        self.number = number
        window = self.window()
        window.setUpdatesEnabled(False)
        was = self._building
        try:
            self._building = True
            try:
                self.field_widgets = {}
                self.item_sheet_widgets = {}
                self.item_foot = None
                self.item_sheet = self._item_sheet(self.edit) if self.edit is not None else QWidget()
            finally:
                self._building = was
            # The page's own line over the pane names the item ("Editing: 262 - Onion Sword"): the sheet's title
            # would say it twice.
            title = self.item_sheet_widgets.get("title")
            if title is not None:
                title.setVisible(False)
            self._sheet_column.addWidget(self.item_sheet)
            if old is not None:
                self._sheet_column.removeWidget(old)
                retire(old)
            if self.isVisible():
                jt.settle_sheet(self.item_sheet)
            scroll = self.item_sheet.findChild(QScrollArea)
            if place and scroll is not None:
                bar = scroll.verticalScrollBar()
                bar.setValue(min(place, bar.maximum()))
                if bar.value() != place:
                    QTimer.singleShot(0, lambda b=bar, v=place: b.setValue(v))
        finally:
            window.setUpdatesEnabled(True)
        self._show_reset()

    def showEvent(self, event):                                              # noqa: N802
        """A sheet made while the pane was hidden is laid out as it shows."""
        super().showEvent(event)
        if self.item_sheet is not None and self.item_sheet.findChild(jt.SheetScroll) is not None:
            jt.settle_sheet(self.item_sheet)

    def is_changed(self, number=None) -> bool:
        """Whether the mod has its own version of an item (the one shown, with no number)."""
        number = self.number if number is None else number
        return number in (getattr(self.state, "wotl_items", None) or {})

    def _show_reset(self) -> None:
        self.reset_button.setEnabled(self.number is not None and self.is_changed())

    def keep(self) -> None:
        """What the mod has of the item shown, kept: its own version where it differs from the framework's
        (`wotl_items.kept`, `is_changed`), with its picture of its own; nothing where it is the framework's again."""
        if self.edit is None or self.number is None:
            return
        if getattr(self.state, "wotl_items", None) is None:
            self.state.wotl_items = {}
        if getattr(self.state, "wotl_art", None) is None:
            self.state.wotl_art = {}
        made = wl.kept(self.number, self.edit)
        if self.edit.icon_png or wl.is_changed(self.number, made):
            self.state.wotl_items[self.number] = made
            if self.edit.icon_png:
                self.state.wotl_art[self.number] = wl.Art(bytes(self.edit.icon_png), bytes(self.edit.small_png))
            else:
                self.state.wotl_art.pop(self.number, None)
        else:
            self.state.wotl_items.pop(self.number, None)
            self.state.wotl_art.pop(self.number, None)
        self._show_reset()

    def as_framework(self) -> None:
        """As the framework has it: the mod's own version of the item shown let go."""
        if self.number is None or not self.is_changed():
            return
        (getattr(self.state, "wotl_items", None) or {}).pop(self.number, None)
        (getattr(self.state, "wotl_art", None) or {}).pop(self.number, None)
        self.show_item(self.number)
        self.named.emit()
        self.changed.emit()

    def name_of(self, number: int) -> str:
        """One of the 40's name as the mod has it (its words' name), for the page's list."""
        if number == self.number and self.edit is not None:
            return self.edit.item.word_name or self.edit.item.name
        made = wl.item(number, getattr(self.state, "wotl_items", None))
        return (made.word_name or made.name) if made is not None else str(number)

    # -- what the sheet asks of its page (`side_quests.ItemSheet`'s notes) -----------------------------------------

    def _picked_item(self) -> Optional[mi.ItemEdit]:
        return self.edit

    def in_items(self) -> bool:
        return True

    def _ask(self, what: str, ask):
        if self.answers:
            return self.answers.pop(0)
        return ask()

    def _say(self, text: str) -> None:
        self.message.setText(text)
        self.message.setVisible(bool(text))

    def _fill_items(self) -> None:
        self.named.emit()

    def _items_changed(self, refill: bool = True) -> None:
        """After a change the sheet is made again for (its textures): kept, made again in its place, said."""
        self.keep()
        if self.number is not None:
            self.show_item(self.number, again=True)
        if refill:
            self.named.emit()
        self.changed.emit()

    def find_program(self) -> Optional[Path]:
        return game_install.find_program(ui_settings.load().get("game_data_folder") or None)

    def places_store(self) -> dict:
        return {}

    def rename_item(self, name: str) -> None:
        """Its name (its words' name with it): an item's name as any item's (`mod_items.good_name`)."""
        edit = self.edit
        if edit is None or self._building or name == edit.item.name:
            return
        if not mi.good_name(name):
            self._say(sq.ITEM_NAME_BAD)
            box = self.field_widgets.get("item_name")
            if box is not None:
                box.setText(edit.item.name)
            return
        old = edit.item.name
        mi.rename(edit, name)
        if edit.item.plural == old:
            # Its plural was its name (as the framework gives the 40): it follows, as its singular does.
            edit.item.plural = name
        for key, text in (("item_singular", edit.item.singular), ("item_plural", edit.item.plural)):
            box = self.field_widgets.get(key)
            if box is not None and box.text() != text:
                box.setText(text)
        self._say("")
        self._item_sheet_words(edit.item)
        self._item_status()
        self.edits_changed.emit()
        self.named.emit()

    # -- the sheet's answers that differ for these items -----------------------------------------------------------

    def sheet_never_sold(self) -> bool:
        return True

    def sheet_your_towns(self, item: mi.ModItem):
        return None

    def sheet_shop_points(self) -> list:
        return sq.ItemSheet.sheet_shop_points(self) + [(mi.NEVER_SOLD, SHOP_POINT_NEVER.format(n=mi.NEVER_SOLD))]

    def sheet_icon_choices(self, edit: mi.ItemEdit) -> list:
        return [(0, OWN_ICON)] + self._game_item_choices()

    def sheet_icon_now(self, edit: mi.ItemEdit) -> int:
        return 0 if wl.uses_own_icon(self.number, edit.item) else self._game_icon_number(edit)

    def sheet_back_words(self) -> str:
        return USE_OWN_ICON

    def sheet_as_items_page(self) -> bool:
        """(The thirty second session, his ask of 17 November: "the layout ... for the WotL items closer to that of the
        original items for the vanilla items page") Laid out as the Items page lays out one of the game's items."""
        return True

    def sheet_own_art(self, edit: mi.ItemEdit, which: str):
        """The framework's own icon for the item, from the framework as Mod Studio carries it."""
        if self.number is None or not wl.uses_own_icon(self.number, edit.item):
            return None
        from ... import texture_data as td
        path = wl.own_icon_file(self.number, small=(which == "small"))
        cache = self.__dict__.setdefault("_own_art", {})
        if path not in cache:
            try:
                image = td.decode_tex_in_process(path).convert("RGBA")
                cache[path] = (QImage(image.tobytes(), image.width, image.height, image.width * 4,
                                      QImage.Format_RGBA8888).copy(), "")
            except Exception as exc:                                     # noqa: BLE001
                cache[path] = (None, f"{path.name} couldn't be read ({exc})")
        return cache[path]

    def set_game_icon(self, number) -> None:
        """Its icon: the framework's own (0) or one of the game's items'; a picture of the mod's own put aside."""
        edit = self.edit
        if edit is None or self._building:
            return
        if number == 0:
            edit.item.icon, edit.item.icon_picture = 0, wl.icon_name(self.number)
            edit.icon_png, edit.icon_from = b"", ""
            edit.small_png, edit.small_from = b"", ""
            self._items_changed(refill=False)
            return
        if number not in mi.GAME_ITEMS:
            return
        edit.item.icon_picture = ""
        sq.ItemSheet.set_game_icon(self, number)

    def use_game_icon(self) -> None:
        """The textures' menu's Use its own icon: a picture of the mod's own put aside for the framework's."""
        if self.edit is None or self._building or not self.edit.icon_png:
            return
        self.set_game_icon(0)
