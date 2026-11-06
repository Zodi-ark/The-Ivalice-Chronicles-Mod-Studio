"""
The Side Quests page (Zodi, 28 October, "Side quest page": "A page in Mod
Studio to make a side quest and a new place by names: its events, battles,
starts, flags and marker, its battle on a quest map"). Built from the mock-up
he signed off ("Build it as shown except instead of saying "picture" say
"texture" unless you truly mean "picture"", with every option a battle and its
units have, and a quest map named where the battle is; its pictures made by
`dev/research/sidequests/mock_page.py`), in the Event Editor's shape:

- **Left**, Quests and Places: the mod's side quests (each its marker's
  color, its name and where its steps wait), New quest and Remove; the
  mod's own places on the world map (the page's next part makes and changes
  them; for now a mod's places are carried through as they are).
- **Middle**, what is picked: the world map for a quest and a step's start
  (the game's map, roads and places where its layout puts them, drawn from the
  unpacked game as the UI Layouts page draws the game's screens; the mod's
  places and roads; the quest's markers; click a place to put the step there),
  or a battle's map with its units (the Encounters page's own map: click a unit
  to change it, drag it to move it), or a scene's map with its units.
- **Right**, its card (`Card`, as the Event Editor's big node): the quest's
  (its name, marker and flags), a start's (its place, when it waits, passing
  through), a battle's (every field of its setup, its map, its 16 units, the
  scenes it plays), a unit's (every field the game's battle files give one,
  `entd.unit_with`), a scene's (what it is made from, its words) or a step's
  end (the flag it sets).
- **Under them**, the quest's steps (`QuestStrip`): each step's start and the
  events it plays in the order they play, wired, a dashed line to the next
  step; click one to pick it. Add a step, Add a scene and Add a battle.

What it changes is `state.quests` (`quest_edits.QuestEdits`): Export writes
each quest as `ModStudioQuests/<folder>/` with its words, and Mod Studio
Framework gives every name a number as the game starts. Whatever Mod Studio
Framework would say of a quest is said on its card and on the steps' cards,
in its own words (`quest_edits.problems`).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QMenu, QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter, QStackedWidget, QTabBar,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ... import constants as c
from ... import encounter_names
from ... import entd
from ... import event_scripts as es
from ... import event_setup as su
from ... import game_install
from ... import map_classic
from ... import map_places as mp
from ... import map_roads as mr
from ... import mod_items as mi
from ... import place_edits as pe
from ... import nxd_data
from ... import paths
from ... import quest_edits as qx
from ... import quest_map_edits as qme
from ... import reference_names
from ... import side_quests as sq
from ... import ui_settings
from ... import uib
from .. import layout_preview as lp
from .. import theme
from ..widgets.actions import page_intro
from ..widgets.field_rows import CollapsibleSection
from ..workers import Worker, run_in_thread
from . import encounters as enc
from . import event_music as emu
from . import event_words as words
from . import map_editor as me_page
from .event_nodes import CARD_H, CARD_W, GAP_X, GAP_Y, MARGIN, Card, Line, NodeBand, NodeStrip
from .encounter_map import HINT as BATTLE_MAP_HINT
from .encounter_map import TEAM_NAMES, DeployMark, EncounterMap, MapUnit, drawn_palette
from .event_music import MusicPlayer
# (Zodi, 4 November) A weapon's look chosen as the Items page's Attack chooses one; each look named by every weapon
# that shares it, as the Items page names it.
from .items import SHOP_POINT_WORDS, LookDialog, look_words, swing_palette_box

#: The page's name (Zodi, 3 November, after test 62: "change the name of the Side Quests page to something more
#: representative of what it lets users do"; his choice "New Content").
TITLE = "New Content"

# =============================================================================
# Its words (none with a dash but in a range of numbers; "texture", not
# "picture", where a texture is meant)
# =============================================================================

BLURB = ("Your mod's side quests, and places of its own on the world map for them. Pick a quest, then a step in "
         "the row below to change it.")
TABS = ("Quests", "Places", "Items")
QUEST_SEARCH = "Search quests, by name or place"
PLACE_SEARCH = "Search places and roads, by name"
NEW_QUEST, REMOVE = "New quest", "Remove"
NEW_PLACE, NEW_ROAD = "New place", "New road"
# (Zodi, 4 November: "as a continuation of making the UI clearer lets remove these notes") The lists' feet, saying
# where each quest, place, road and item goes in the mod, went: QUESTS_FOOT, PLACES_FOOT, ITEMS_FOOT; and the notes
# under an empty list (NO_QUESTS, NO_PLACES, NO_ITEMS) and after a removal (REMOVED, PLACE_REMOVED, ROAD_REMOVED,
# ITEM_REMOVED).
# (1.26.0) The Items tab (Zodi's list of 3 November, his first: "Adding new items to go into the new towns outfitter").
ITEM_SEARCH = "Search items, by name"
NEW_ITEM = "New item"
PICK_AN_ITEM = "Pick an item in the list, or make one with New item."
ITEM_LIST_LINE = {"none": "{kind}, sold at no town of yours yet", "towns": "{kind}, sold at {towns}",
                  # (1.27.0) and at the game's towns ticked on its card.
                  "game": "{kind}, sold at {count} of the game's towns", "both": "{kind}, sold at {towns} and {count} "
                  "of the game's towns"}
NEW_ITEM_TITLE = "New item"
#: (1.27.0) Zodi's fifth of 3 November: "adding new potions and the such requires a unit learning a ability to throw or
#: use that item ... remove the ability to add those kinds of items for now".
NO_ITEMS_TO_USE = ("Items to use can't be made for now: a unit uses or throws one in battle only by an ability that "
                   "knows it.")
#: (Zodi after test 62: "it would be a lot more straight forward if when creating a new item it gave you a prompt to
#: enter the Name of the item and the Category of the Item and then the Sprite and Palette option from the Items page.
#: Then after it lets you do the other edits", his to my recommendation for new users.) (4 November: "you should
#: complete remove that description") Its intro, NEW_ITEM_INTRO, went.
CATEGORY_FIELD = "Category"
#: Last in New item (Zodi, 4 November: "It should rather say "stats" rather than "numbers" and it should drop "the
#: game's" ... and the sentence should be positioned last in the menu"): the game's first item of its category, whose
#: stats a new item of it starts with, in the possessive (`possessive`).
CATEGORY_NOTE = "Its stats start as {item}."
#: A game item the tables name none: by its number.
ITEM_NUMBERED = "item {n}"
#: (Zodi, 4 November, his choice "Together, named by half") The half of its battle sprite it changes, as the Items
#: page names it.
HELD_FIELD = "Held or thrown"
# (Zodi, 4 November: "can you remove the "The sprite a unit holds up or throws in battle." line") HELD_NOTE went.
HELD_CHOOSE = "Choose an icon"
HELD_PICKED = "Sprite {sprite}, palette {palette}"
HELD_MISSING = "Choosing an icon needs the unpacked game folder (General Setup): {problem}."
ITEM_NAME_TIP = "Letters and digits of English, spaces, underscores, hyphens and apostrophes, up to 64."
ITEM_NAME_BAD = ("An item's name is letters and digits of English, spaces, underscores, hyphens and apostrophes, 1 to "
                 "64 of them, with no space at either end.")
ITEM_TAKEN = "Your mod has an item named {name} already."
NO_GAME_ITEMS = "Making an item needs the game's program, found from General Setup's folder of .pac files: {problem}."
NO_PROGRAM = "it isn't found"
ITEM_BAND = "ITEM"
ITEM_COLOR = "#c9a227"
#: Its card's band: its category (the Items page's names).
ITEM_CATEGORY_BAND = "{category}"
#: (Zodi, 4 November: "clear up the large notes clutter to improve readability and productivity on this new items
#: page") One sentence; the notes that said what a field's name and choices say already taken out.
ITEM_BLURB = "An item of your mod's own, sold at your towns' Outfitters and at the game's towns you tick."
ITEM_KIND_WORDS = "{kind} ({category})"
ITEM_WORDS = "Words"
SINGULAR, PLURAL = "Singular", "Plural"
ITEM_NUMBERS = "Numbers"
PRICE_FIELD = "Price"
SOLD_FROM = "Sold from"
#: The story's points the shops sell an item from, in words: the Items page's (Zodi, 5 November, both alike).
SOLD_FROM_POINTS = SHOP_POINT_WORDS
BONUSES_FIELD = "Equipment bonuses"
ICON_FIELD = "Icon"
#: (Zodi, 4 November: "we already have a better user interface for new users from the Items page where you can simply
#: right click the art or sprite texture and have a context menus with options and to place the users image. You should
#: still be able to cycle through the games items icons though") Its two textures as the Items page shows them, each
#: with a menu on a right click, under the game's item whose icon it uses.
ICON_HINT = "Right click a texture to use an image of your own."
#: A texture panel with nothing to show (the Items page's texture slots' words).
NO_TEXTURE = "No file here"
OWN_TEXTURES = "Your own textures"
REPLACE_TEXTURE = "Replace..."
MAKE_FROM_ART = "Make from its art"
USE_GAME_ICON = "Use the game's icon"
EXPORT_TEXTURE = "Export as PNG..."
EXPORT_TEXTURE_TITLE = "Export {texture} of {item} as PNG"
CHOOSE_ICON_TITLE = "An icon for {item}"
SOLD_AT_FIELD = "Sold at"
SOLD_AT_NONE = "No town of yours sells it yet: add it to a town's Outfitter, on its card on the Places tab."
#: On its card, the map's hint under the map saying how a town of yours comes to sell it.
SOLD_AT_NO_TOWN = "No town of yours yet."
# (1.27.0) Zodi's observations of 3 November, after test 58: what an item does, its two icons apart, the game's own
# Outfitters, its UI values set for him, and no new items to use for now.
ITEM_TO_USE_NOTE = NO_ITEMS_TO_USE + " This one is still read and sold as it is."
ATTACK_FIELD = "Attack"
FORMULA_LABEL, INFLICT_LABEL, CAST_LABEL = "Formula", "Inflict Status", "Cast Spell"
WEAPON_ELEMENTS = "Elements"
BONUS_STATUS_LABELS = ("Always has", "Immune to", "Starts a battle with")
BONUS_ELEMENT_LABELS = ("Absorbs", "Nullifies", "Halves", "Weak to", "Strengthens")
TICKED_LINE = "{label}: {names}"
TICKED_NONE = "nothing"
CHANGE = "Change"
TICKS_TITLE = "{item}: {label}"
STATUS_TICKS_INTRO = "Tick each status, as wearing {item} gives it."
ELEMENT_TICKS_INTRO = "Tick each element."
UI_FIELD = "In the menus"
UI_STATUS_WORDS = {0: "No status effect shown for what it does (UI Status Effect Id 0).",
                   1001: "Shown absorbing the hit points it deals, as the Blood Sword is (UI Status Effect Id 1001).",
                   1002: "Shown healing the one it strikes, as the Healing Staff is (UI Status Effect Id 1002)."}
UI_RANDOM_WORDS = {True: "Its damage shown as random, as the axes', flails', bags' and magic guns' is (Random Damage "
                         "on).",
                   False: "Its damage shown as fixed (Random Damage off)."}
UI_LISTED_WORDS = {"copy": "Listed with the game's item it started as, in its place among them (UI Item Category Id "
                           "{category}, Sort Order "
                           "{sort}).",
                   "own": "Listed with the game's items of its kind, after them (UI Item Category Id {category})."}
#: An item's UI category when its file gives none (the helper's `ItemRoom.UiCategories`), by kind.
UI_CATEGORY_OF_KIND = (3, 20, 21, 24, 28, 34)
#: (4 November) In the tooltip of its words now.
UI_NOTE = ("Set for you from what it does, as the game's own items have them: the Items page's UI Status Effect Id, UI "
           "Item Category Id, Sort Order and Random Damage.")
#: (1.27.0) A weapon's look in battle (his choice: "A game weapon's look"); (Zodi after test 62: "borrow the design
#: of Sprite and Palette from the Items page") its look drawn, its palette and Choose a look over the looks that swing
#: the same way; (4 November, his choice "Together, named by half") under the Attack half of its battle sprite, its
#: palettes the game's own weapons' (`mod_items.SWING_PALETTES`), the look's words in its tooltip.
PALETTE_CHOICE = "Palette {n}"
LOOK_CHOOSE = "Choose a look"
# (Zodi, 4 November: "many of them share the same design") Its look's words are the Items page's now
# (`items.look_words`: every one of the game's weapons that shares it, by name); LOOK_NOW and LOOK_OWN_NOW went.
NO_LOOKS = "Its look in battle needs the game's program, found from General Setup's folder of .pac files: {problem}."
# (after test 61) Zodi: "in Side Quests when creating a new item it should have the Texture and Sprite previews": the
# game's icon's two textures shown when it uses one, as the Items page's Art Texture and Sprite Texture, and its Battle
# Sprite (the Items page's, `unit_sprites.BattleSprites`): a weapon as it attacks, a shield as it guards, and the item
# as a unit holds it up or throws it, by its record's palette and sprite (its copy's).
ART_TEXTURE_TIP, SPRITE_TEXTURE_TIP = "Art Texture", "Sprite Texture"
GAME_ICON_MISSING = "Its textures need the unpacked game folder (General Setup): {problem}."
BATTLE_SPRITE_FIELD = "Battle sprite"
BATTLE_ATTACK, BATTLE_GUARD, BATTLE_HELD = "Attack", "Guard", "Held or thrown"
BATTLE_SPRITE_MISSING = "Its battle sprite needs the unpacked game folder (General Setup): {problem}."
BATTLE_SPRITE_UNDRAWN = "Its battle sprite can't be drawn: {problem}."
CHOOSE_SMALL_TITLE = "A small icon for {item}"
ITEM_REMOVE_ASK = "Take the item {name} out of your mod?"
ITEM_REMOVE_TOWNS = " {towns} will no longer sell it."
OWN_ITEM_LINE = "{item} (your mod's own)"
ITEMS_WORLD_TITLE = {"item": "Where {item} is sold", "none": "Your items"}
ITEMS_WORLD_HINT = {"towns": "The towns of yours that sell it are outlined.", "none": SOLD_AT_NONE}
NO_GAME = "No game files yet. Unpack your game on General Setup to make side quests."
PICK_A_QUEST = "Pick a quest in the list, or make one with New quest."
QUEST_BUTTON = "Quest"
QUEST_BUTTON_TIP = "The quest's own card: its name, marker and flags"
STEPS_TITLE = "Steps"
STEPS_NOTE = "In the order they are played. Click one to see it above and change it on the right."
ADD_STEP, ADD_SCENE, ADD_BATTLE = "Add a step", "Add a scene", "Add a battle"
# (Zodi, 4 November: "we stopped letting users copy items from the game so this applies to the new quests") Each new
# scene and battle the sample on map 116 (`quest_edits.make_sample_scene`, `make_sample_battle`).
ADD_SCENE_TIP = "A new scene, played after the card picked"
ADD_BATTLE_TIP = "A new battle, played after the card picked"
LATER = "later"
STEP = "Step {n}"
UNPLAYED = "Not played"
READY = "Ready: Mod Studio Framework reads this as it is."
READY_SHORT = "Ready."
SAYS = "Mod Studio Framework would say: {problem}."

# The strip's cards.
START_COLOUR, BATTLE_COLOUR, SCENE_COLOUR, DONE_COLOUR = "#5b9bd5", "#e8705f", "#d8b662", "#6bbf73"
QUEST_COLOUR, UNIT_COLOUR, PLACE_COLOUR = "#7d8089", "#4fb3a9", "#4fb3a9"
WAITS_AT, BATTLE_BAND, SCENE_BAND, DONE_BAND = "WAITS AT", "BATTLE", "SCENE", "DONE"
AS_IT_STARTS, ONCE_WON, ONCE_LOST = "As the battle starts", "Once the battle is won", "Once the battle is lost"
STEP_DONE = "Step {n} done"
SETS = "Sets {flag}"
SETS_NOTHING = "Sets no flag"

# The quest's card.
# (Zodi, 4 November: "clean up some of the very long notes there as well") Each card's blurb one short line, and a
# note that says how a field works its tooltip.
QUEST_BLURB = "A side quest of your mod. Its steps are in the row below."
NAME = "Name"
NAME_TIP = "Letters, digits, spaces, underscores and hyphens, up to 64."
NAME_BAD = "A name is letters, digits, spaces, underscores and hyphens, 1 to 64 of them, with no space at either end."
QUEST_TAKEN = "Your mod has a quest named {name} already."
MARKER = "Marker"
SHOW_MARKER = "Show a marker where a step waits"
CHOOSE_COLOUR = "Choose a color"
MARKER_NOTE = "Its color over each place a step waits at, as the game shows its own quest markers."
#: A new quest's marker: blue, as the mock-up's first quest (untick it for none).
DEFAULT_MARKER = "#4080E0"
FLAGS = "Flags"
ADD_FLAG = "Add a flag"
FLAG_SET_BY = "Set as {event} ends."
FLAG_NOT_SET = "No scene sets it yet."
FLAG_WAITED = "Step {n} waits for it."
FLAGS_NOTE = ("A flag is 0 until a scene sets it, and a step's conditions may test it. Each step Mod Studio makes "
              "has one, set as it ends; add your own for a scene to set.")
NAMES_KEPT = "Once your mod is out, keep the names of its quests, events, flags and rumors: saves know them by name."

# A start's card.
START_BLURB = "Where step {n} waits on the world map, and what must be so before it plays."
PLACE = "Place"
PLACE_NOTE = "Or click a place on the map. Your mod's places are listed first."
WHEN = "When"
STORY_PAST = "The story is past"
ANY_TIME = "Any point of the story"
STORY_POINT = "{place}, event {event:03d}"
STORY_EVENT = "Event {event:03d}"
STORY_LINE = "Story past {place}"
STORY_AT_LEAST = "Story at {value} or later"
AFTER_A_STEP = "Once a step before is done"
ANY_TIME_LINE = "Any time"
ONCE_ONLY = "Once only: not after step {n} is done"
AFTER_STEP = "After step {n} is done"
OTHER_CONDITIONS = "Its other conditions"
CONDITIONS_NOTE = "All of them must hold, up to {most} conditions in all."
#: A condition's rows: someone in the party, a flag of the quest set or not, one of the game's variables.
IN_PARTY = "is in the party"
FLAG_IS = {1: "is set", 0: "is not set"}
VARIABLE = "The game's variable"
TESTS_WORDS = {"Is": "is", "AtLeast": "is at least", "AtMost": "is at most"}
TAKE_OUT = "Take out"
ADD_CONDITION = "Add a condition"
CONDITION_KINDS = ("Someone in the party", "A flag of the quest", "One of the game's variables")
NO_FLAGS_YET = "The quest has no flag yet: add one on the quest's card."
ALL_FLAGS_TESTED = "Each of the quest's flags is tested here already: add another on the quest's card."
PASSING = "Passing through"
WAITS = "Waits for the player to choose the place"
STOPS = "Stops a travel passing through"
PASSING_NOTE = "A travel passing through goes on past a step that waits; the game's own events stop it."
MARKER_HERE = "The quest's marker shows here while this step waits."
#: (Mod Studio Framework 1.25.0) A step waiting at a floor of one of the mod's dungeons (Zodi, 2 November: Midlight's
#: Deep's END plays its boss battle the first time only): its Place's choice, and what it does there.
FLOOR_PLACE = "{place}, floor {floor}"
#: The separator of a floor's choice's key (the dungeon, then the floor): no place's or floor's name holds it.
FLOOR_KEY = "/"
STEP_FLOOR_NOTE = ("Each time this floor is chosen in the dungeon's list while the step's conditions hold, it plays in "
                   "place of the floor's battle. Played once only, it plays until it is done (a battle's step once its "
                   "battle is won), and winning its battle counts as winning the floor.")
REMOVE_STEP = "Remove step"
#: (1.15.0) A start waiting until one of the quest's rumors is read.
AFTER_RUMOR = "Once the rumor {rumor} is read"
AFTER_RUMOR_LINE = "Once {rumor} is read"

# (1.15.0) A tavern rumor's card (Zodi's list, his third: a rumor read in a tavern, after which the quest can start).
ADD_RUMOR = "Add a rumor"
ADD_RUMOR_TIP = "A rumor told in the taverns: once the player reads it, a step can start"
RUMORS_ROW = "Rumors"
RUMOR_BAND = "RUMOR"
RUMOR_COLOUR = "#a07cc8"
RUMOR_EVERY_TAVERN = "In every tavern"
RUMOR_ONE_TAVERN = "In {town}'s tavern"
RUMOR_TAVERNS = "In {n} towns' taverns"
RUMOR_BLURB = "Told in the taverns; once it is read, a step waiting for it can start."
RUMOR_TAKEN = "The quest has a rumor named {name} already."
RUMOR_TITLE_FIELD = "Title"
RUMOR_TITLE_TIP = "Up to 64 characters on one line: the tavern's list of rumors shows it."
RUMOR_TEXT_FIELD = "What it says"
RUMOR_TEXT_NOTE = "Up to 3000 characters. Leave an empty line between paragraphs, as the game's own rumors do."
RUMOR_TOWNS_FIELD = "Told in the taverns of"
RUMOR_TOWNS_NOTE = "Or click a town on the map. With every town ticked, every tavern tells it."
RUMOR_LAST_TOWN = "A rumor is told in one tavern at least."
RUMOR_NOT_TOWN = ("{place} has no tavern: a rumor is told in the game's 15 towns and in your towns with a menu of their "
                  "own.")
#: (1.18.0) The mod's own towns on a rumor's card, and one it names that has no menu (the helper's words: Framework's
#: rumors).
RUMOR_MOD_TOWNS = "Your towns"
RUMOR_NO_MENU = "Its rumor {rumor} isn't told at {town} ({town} has no tavern: no menu of its own)."
RUMOR_WHEN_NOTE = "It is told while all of these hold."
RUMOR_READ_FIELD = "Once it is read"
RUMOR_SETS = "It sets the flag {flag}."
RUMOR_STEP_WAITS = "Step {n} waits until it is read"
RUMOR_NO_STEPS = "The quest has no step yet: add one, then tick it here to have it wait until the rumor is read."
REMOVE_RUMOR = "Remove rumor"
FLAG_SET_BY_RUMOR = "Set once the rumor {rumor} is read."

# A battle's card.
BATTLE_BLURB = "A battle of the quest's own, fought at its step's place."
MAP = "Map"
MAP_QUEST = "{name}, made from {base:03d} {place}"
MAP_NOTE = "Your quest maps first, by the names you gave them, then the game's maps."
NEW_QUEST_MAP = "New quest map"
OPEN_MAP = "Open on the Map Editor"
QUEST_MAP_INTRO = ("A quest map is a map of your mod's own for its side quests' battles, made from map {base:03d}"
                   "{place} as your mod has it. You change it on the Map Editor apart from map {base:03d}, which stays "
                   "as it is. Mod Studio Framework gives it a map number of its own as the game starts.")
UNITS = "Units"
UNITS_OWN = "Click a unit here or on the map to change any of its fields, or drag it on the map to move it."
ADD_UNIT, ADD_UNIT_TIP = "Add a unit", "A copy of the unit picked (or the first), in the first empty place"
EMPTY_SLOT = "Empty"
FULL = "The battle's 16 places for units are all taken."
NO_UNIT_TO_COPY = "The battle has no unit to copy: change an empty place's fields on its card to make one."
HOW_WON = "How it is won"
#: (Mod Studio Framework 1.12.0, Zodi's choices of 28 October) The ways a battle is won, each as one of the game's
#: battles is won (dev/research/sidequests/battle_rules.py).
WON_WAYS = {sq.ENEMIES: "Once every enemy is beaten", sq.BEATEN: "Once one unit is beaten",
            sq.WORN_DOWN: "Once one unit is worn down", sq.ON_TILE: "Once Ramza stands on a tile"}
WON_NOTES = {sq.ENEMIES: "As most of the game's battles are won.",
             sq.BEATEN: "As the game's \"Defeat Milleuda!\" is won: that unit beaten, the other enemies or not.",
             sq.WORN_DOWN: "As the game's \"Defeat Wiegraf!\" at Windflat Mill is won: that unit's HP down to a share "
                           "of its most.",
             sq.ON_TILE: "As the game's \"Open the sluice!\" at Fort Besselat is won: Ramza on that tile, or every "
                         "enemy beaten."}
WON_UNIT, UNIT_CHOICE = "Its unit", "{n}: {unit}"
SHARE_FIELD, SHARE_SUFFIX = "Down to", " percent of its HP"
TILE_X, TILE_Y, UPPER_LEVEL = "Tile X", "Tile Y", "Its upper level"
TILE_NOTE = "X and Y count the map's tiles as a unit's own X and Y on its card do."
PROTECT = "Lost if this unit is beaten"
NO_ONE_PROTECTED = "No one"
PROTECT_NOTE = ("As the game's \"Protect Agrias!\" is lost: that unit beaten, the scene once it is lost plays, and the "
                "game starts over.")
OBJECTIVE = "Objective"
OBJECTIVE_TIP = "Up to 64 characters on one line."
OBJECTIVE_NOTE = ("Shown in the objective box as the battle starts, in your words. Without it, the box says the "
                  "game's \"Defeat all enemies!\".")
OBJECTIVE_WANTED = "Its start still says \"Defeat all enemies!\": give it an objective of its own."
AS_IT_STARTS_FIELD, ONCE_WON_FIELD, ONCE_LOST_FIELD = "As it starts", "Once it is won", "Once it is lost"
#: (1.31.0, Zodi's test 65: "there should be three events. One at start, one mid battle mostly for dialogue, and then
#: the ending event"; his choice "Either, picked on the card") A battle's scenes during it.
DURING_FIELD = "During it"
ADD_DURING = "Add a scene during it"
DURING_NOTE = ("A scene during the battle plays once a battle, as a unit's turn comes or as its HP falls: click it to "
               "change when and its words.")
DURING_NONE = "None yet."
DURING_PLAYS = "It plays"
ON_TURN, ON_HP = "As its unit's turn comes", "As its unit's HP falls"
DURING_UNIT = "Its unit"
DURING_RAMZA = "Ramza"
DURING_SHARE = "When its HP is at most (percent of its most)"
DURING_SHARE_TIP = "0 plays it as the unit is beaten."
DURING_DETAIL = {sq.TURN: "On {unit}'s turn", sq.HP: "As {unit}'s HP falls"}
LOST_NOTE = ("The scene once it is lost is the game's game over with a line of your own first: click it to change "
             "its words.")
#: (28 October, Mod Studio Framework 1.11.1) A battle without a scene of the quest's as it starts plays the game's
#: own battle start, as its random battles do (Zodi's test 37: without one, the battle was won at once).
NO_SCENE = "The game's battle start, as its random battles have"
NEW_SCENE_ENTRY = "A new scene"
#: What the new scene's entry holds (no scene is named so: a name has no control character).
NEW_SCENE_KEY = "\x00new"
WON_NOTE = ("The scene once it is won is the game's victory scene with a line of your own: click it to change its "
            "words. Add a scene after it for more.")
#: (Mod Studio Framework 1.14.0, Zodi's list, his second: "custom deploy areas") Where the player's units start.
WHERE_UNITS_START = "Where your units start"
GAME_DEPLOY, OWN_DEPLOY = "On the game's deploy areas", "On deploy areas of its own"
GAME_DEPLOY_NOTE = "Deploy areas of the game's. Pick deploy areas of its own to choose their squares on the map."
DEPLOY_AREA = "Deploy area {n}"
AREA_FIELD, DEPLOY_UNITS_FIELD, FACING_FIELD = "Area", "Units", "Facing"
DEPLOY_UNITS_TIP = "How many of your units start on the area: one to five, no more than its squares"
FACING_WORDS = ("South", "West", "North", "East")
DEPLOY_UPPER = "On its squares' upper level"
DEPLOY_SQUARES = "{n} squares of up to 25, within 5 by 5 on the map"
DEPLOY_ONE_SQUARE = "1 square of up to 25, within 5 by 5 on the map"
DEPLOY_NO_SQUARES = ("No squares yet: click tiles on the map. An area without squares is left out, and with none, "
                     "the battle starts on the game's.")
ADD_AREA, REMOVE_AREA = "Add a second area", "Remove this area"
OWN_DEPLOY_NOTE = ("Click a tile on the map to add it to this area or take it out; hold Ctrl to click a tile a unit "
                   "stands on. Mod Studio Framework gives the game each area as one of its own.")
#: The game's deploy areas a battle with its own falls back on: a short line, the whole in its tooltip.
DEPLOY_FALLBACK = "Where it starts if its own can't be given:"
DEPLOY_FALLBACK_TIP = ("If Mod Studio Framework can't give the game its own (after a game update), the battle starts on "
                       "these of the game's.")
#: The map's legend and hint for the deploy areas.
DEPLOY_LEGEND_OWN = "Deploy area {n}: {units} facing {facing}"
DEPLOY_LEGEND_GAME = "Deploy area {n}: the game's area {number}"
DEPLOY_HINT = ("Click a tile to add it to deploy area {n} or take it out, and Ctrl and click for a tile a unit stands "
               "on. Click a unit to edit it, or drag it to another tile. Drag anywhere else to turn the map, Shift and "
               "drag to move it, and use the wheel to zoom.")
REMOVE_BATTLE = "Remove battle"
PLAY_MUSIC, STOP_MUSIC = "Play", "Stop"
MAP_EDITOR = "Map Editor"
PICK_A_MAP = "Pick the battle's map first: a quest map is made from it."
QUEST_MAP_COPY_INTRO = ("A quest map is a map of your mod's own for its side quests' battles. This one is a copy of "
                        "the quest map {name} as you have changed it, which is made from map {base:03d}{place} as your "
                        "mod has it. You change it on the Map Editor apart from the maps it is made from. Mod Studio "
                        "Framework gives it a map number of its own as the game starts.")
QUEST_MAP_MADE = ("{name} is a quest map of your mod now, made from map {base:03d}, and the battle is fought on it. "
                  "Open it on the Map Editor to change it.")

# A unit's card.
UNIT_BAND = "UNIT"
UNIT_SLOT = "Slot {n} of 16"
UNIT_BLURB = "Every field the game gives a unit. It stands on the map as you change it."
BACK_TO_BATTLE = "Back to the battle"
#: (4 November) A scene's own unit's way back.
BACK_TO_SCENE = "Back to the scene"
UNIT_TAKE_OUT = "Take out"
#: (Mod Studio Framework 1.33.0, Zodi's choice of 5 November: "As a renamed unit") A quest's unit's own name: its field's
#: words when empty, its tooltip, and its Unit Name's tooltip while it has one.
OWN_NAME_NONE = "None: the name Unit Name gives"
OWN_NAME_TIP = ("The unit's own name, shown in battles and scenes as the game shows a unit you renamed, over each line "
                "it says in the quest's scenes (change a line's under Name over the box on the Event Editor), and kept "
                "if the unit joins your party. Up to 16 characters, none of < > \". Its Unit Name becomes Random, so "
                "the unit speaks with the voice of a generic unit of its gender.")
OWN_NAME_RANDOM_TIP = "Random while the unit has its own name: the game shows its own name in place of this one."
UNNAMED_NOTE = "Flags nobody has named yet, kept as the battle has them:"
#: (28 October, his test 39) Load Formation's and Save Formation's tooltip (4 November: no longer a note under them);
#: a new battle's units have both off, as a copy of the game's had (`qx.own_units`).
FORMATION_NOTE = ("Load Formation has the game take this unit from the player's own units as the battle starts, and "
                  "Save Formation writes it back to them after. With both off, it is built from its own fields; with "
                  "them on, a story character the player hasn't would be an empty place.")
SECTIONS = ("Identity", "Abilities", "Equipment", "Stats and Level", "Placement and Presence", "How It Fights",
            "Spoils", "Unknown Fields")
SECTION_TITLE = "{name}, {count} fields"
#: A unit's team: the map's own colors (`encounter_map.TEAM_NAMES`), and who each is in the game.
TEAMS = {0: "Blue team, the player's", 1: "Red team, the enemy", 2: "Green team, guests", 3: "Light blue team"}
#: A unit's birthday month (FFTPatcher's `Month`, Glain, GPL-3, read for its facts as `entd.py` was).
MONTHS = {0: "Unknown", 1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June", 7: "July",
          8: "August", 9: "September", 10: "October", 11: "November", 12: "December", 254: "Random", 255: "None"}
#: A random value, as the game's battle files hold one in a byte (`entd.RANDOM_BYTE`).
RANDOM = "Random"
#: Job Unlock's 0 (the jobs 1 to 19 are named from the job table, as the Encounters page names them).
BASE_JOB = "Base"
#: A war trophy's 0: no item.
NOTHING = "Nothing"
UNIT_LINE = "{who}, {level}, {team}"
LEVEL, RANDOM_LEVEL = "level {level}", "random level"
#: A flag nobody has named, by its byte and bit (`entd.UNNAMED_FLAGS`: "flag_35_80").
UNNAMED_LABEL = "Byte {byte}, 0x{bit}"
#: The fields a unit's title says (`_unit_words`): changing one says it again.
TITLE_FIELDS = frozenset({"unit_name", "main_job", "level", "team"})

# A scene's card.
SCENE_BLURB = {"scene": "A scene of the quest's own, played at its step's place.",
               "start": "A scene of the quest's own. It plays as the battle {battle} starts, on its map and with "
                        "its units.",
               "won": "A scene of the quest's own. It plays once {battle} is won.",
               "lost": "A scene of the quest's own. It plays once {battle} is lost, and the game starts over after "
                       "it.",
               "during": "A scene of the quest's own. It plays during the battle {battle}, once a battle, its speakers "
                         "stopping as they speak and marching again after."}
MADE_FROM = "Made from"
# (4 November) MADE_FROM_COPY went: a scene that knows no event of the game's is a new one, and says nothing.
#: (1.11.0) A scene that knows the game's event it was copied from (its `From`).
MADE_FROM_EVENT = "A copy of the game's event {event:03d}, its words your own."
MADE_FROM_WON = "The game's victory scene (event {event:03d}), with a line of your own shown first."
#: (1.12.0) A battle's scene once it is lost, and a start scene made for a battle's objective.
MADE_FROM_LOST = "The game's game over (event {event:03d}), with a line of your own shown first."
MADE_FROM_START = "The game's battle start (event {event:03d}), its objective box showing the battle's objective."
WHAT_IS_SAID = "What is said"
NOTHING_SAID = "This scene shows no words."
NO_WORDS_YET = "No words yet"
WORDS_MISSING = "Some of its lines have no words yet: write them here."
GAME_VARIABLES = ("It sets {variables}, as the game's scene does. Mod Studio Framework keeps the story's progress "
                  "as it was while it plays; the others it sets as the game's scene would.")
VARIABLES_ONE, VARIABLES_MANY = "the game's variable {variable}", "the game's variables {variables} and {last}"
WORDS_NOTE = "Changed here in {language}; its other languages keep their own words."
NODES = "Its nodes"
NODES_NOTE = ("Its camera, units, moves and words, node by node, are changed on the Event Editor as a game scene's "
              "are, and kept in the quest.")
OPEN_EVENT_EDITOR = "Open on the Event Editor"
EVENT_EDITOR = "Event Editor"
FLAGS_IT_SETS = "Flags it sets"
SETS_AS_ENDS = "{flag}, as it ends"
SETS_NONE = "None."
#: (1.31.0, Zodi's ask of 3 November: "A reward as a quest ends"; his choices "Its last step only" and "A line in the
#: scene", given silently too) The quest's reward, on its last step's last scene's card.
REWARD_FIELD = "Reward"
REWARD_NOTE = ("The quest's last step gives it as this scene ends, once: never again when the scene is replayed. "
               "Mod Studio Framework gives the gil and the items.")
REWARD_GIL = "Gil"
REWARD_ITEMS = "Items"
ADD_REWARD_ITEM = "Add item"
REMOVE_REWARD_ITEM = "Remove"
OWN_ITEM = "{name} (this mod's own)"
REWARD_UNIT = "A unit joining"
REWARD_NO_UNIT = "None"
REWARD_UNIT_CHOICE = "Unit {n}: {job}"
REWARD_UNIT_WON = "A battle's own units join as their unit cards say (Join After Event)."
#: (Zodi's test 66) A unit joins through the game's own New Party Member screen; its gil and items are said in the
#: game's narration, (his test 68, his word on test 70) for four seconds.
REWARD_UNIT_TIP = ("As the scene ends, the game's New Party Member screen asks whether this unit joins. With a full "
                   "party, the player may dismiss a unit to make room.")
REWARD_SAID = "Said in the scene"
REWARD_SAID_TIP = ("Words at the centre of the screen after the scene's last line say the gil and items the quest "
                   "gives, for four seconds; change them under What is said. Untick it to give them silently.")
SCENE_UNITS = "Its units"
REMOVE_SCENE = "Remove scene"
WON_STAYS = "It goes with its battle."
LOST_STAYS = "It goes once its battle is lost if no unit is beaten."
PLAYS_WITH_BATTLE = "It plays on its battle's map, with its units and music: change them on {battle}'s card."
SCENE_DEPLOYS = ("These place your units as a battle's do, so the game opens its formation screen before the scene. "
                 "Set both to none for a scene of its own.")
BATTLE_OF_QUEST = "{name}, the quest's own"
#: (Zodi, 4 November: a new scene is no copy of the game's, "we should not lose any functionality") A scene's doors on a
#: map whose doors the game's events open: as one of them (its From), or none.
DOORS_FIELD = "Doors"
DOORS_NONE = "As in no event of the game's"
DOORS_EVENT = "As in event {event:03d}"
DOORS_TIP = ("The remaster plays a map's doors by the event playing: a door this scene opens or shuts (on the Event "
             "Editor) plays as it does in the game's event picked.")

# A step's end.
DONE_BLURB = "What step {n} leaves behind as it ends: the flags it sets, and the steps waiting for them."
DONE_FLAGS = "Sets {flags} as {event} ends."
DONE_WAITED = "Step {n} waits for {flag}."
DONE_NOTHING = "No step waits for its flags."
DONE_MARKER = "Its marker goes from {place} once {flag} is set."

# The middle.
WORLD_TITLE = {"quest": "{quest} on the world map", "start": "Step {n} waits at {place}",
               "rumor": "The taverns telling {rumor}"}
WORLD_HINT = {"quest": "Its marker shows where each step waits. Click a step's place to pick that step. Drag to "
                       "move the map, and use the wheel to zoom.",
              "start": "Click a place to have step {n} wait there instead. Drag to move the map, and use the wheel "
                       "to zoom.",
              "rumor": "Its towns are outlined. Click a town to have its tavern tell the rumor, or no longer. Drag to "
                       "move the map, and use the wheel to zoom."}
DRAWING_WORLD = "Drawing the world map..."
NO_WORLD_FILES = ("The world map isn't in your unpacked game ({problem}). Unpack your game on General Setup with "
                  "Textures ticked: it brings the world map's textures and layouts.")
NO_WORLD = "The world map can't be drawn: {problem}."
BATTLE_TITLE = "{battle}, on {map}"
SCENE_TITLE = "{scene}, on {map}"
SCENE_HINT = "The scene's map and units, as its setup gives them."
NO_MAP_YET = "Pick its map on its card, on the right."

# Dialogs.
NEW_QUEST_TITLE = "New quest"
#: (Zodi, 4 November: "only has three things on it Name, Place, and Marker"; his choice, a story point too) New quest's
#: fields, as the start's card and the quest's card name them; its intro, NEW_QUEST_INTRO, went.
AVAILABLE = "Available"
STEP_TITLE = "Add a step"
PLAYS = "It plays"
# (Zodi, 4 November) A step's first event the sample on map 116, never a copy of the game's: STEP_INTRO,
# SCENE_TITLE_DIALOG, BATTLE_TITLE_DIALOG, SCENE_INTRO, BATTLE_INTRO and COPIED_FROM went.
A_SCENE, A_BATTLE = "A scene", "A battle"
EVENT_NAME = "Its name"
EVENT_TAKEN = "The quest has an event named {name} already."
CANT_MAKE = "It can't be made: {problem}"
REMOVE_ASK = "Take the side quest {name} out of your mod? Its steps, scenes and battles go with it."

# Places and roads (the page's second part: Zodi's "A) Places and roads made on the page", the mock-up's place).
PLACE_BAND, ROAD_BAND = "PLACE", "ROAD"
PLACE_KIND_WORDS = {True: "A town", False: "A battle ground", pe.DUNGEON: "A dungeon"}
PLACE_LINE = "{kind}, {count} road{s}"
#: (1.17.0) A battle ground's line in the list, past its roads.
PLACE_BATTLES_LINE = ", {n} random battle{s}"
#: (1.18.0) A town's line in the list, with a menu of its own (place_edits' line's words).
PLACE_MENU_LINE = ", " + pe.MENU_SHORT
#: (1.20.0) A town's line in the list, darkened once a quest's flag is set (place_edits' line's words).
PLACE_DARK_LINE = ", " + pe.DARK_SHORT
#: (1.21.0) A dungeon's line in the list, past its roads.
PLACE_FLOORS_LINE = ", {n} floor{s}"
ROAD_LIST_LINE = "A road from {start} to {end}"
PLACE_BLURB = ("A place of your mod's own on the world map. The game travels to it along its roads, and a quest's "
               "step may wait there.")
KIND = "Kind"
PLACE_NAME_TIP = "Letters, digits, spaces, apostrophes, underscores and hyphens, up to 64."
TOWN_KIND, BATTLE_KIND = "A town, shown with a texture", "A battle ground, shown as a point"
TEXTURE = "Texture"
OWN_TEXTURE, GAME_TEXTURE = "Your own texture", "One of the game's town textures"
CHOOSE = "Choose"
NO_FILE_YET = "No image chosen yet"
TOWN_TEXTURE = "Town texture {icon}"
TEXTURE_NOTE = "Made from any image file you choose, at the size of the game's town textures."
CHOOSE_TITLE = "Choose an image for {place}'s texture"
IMAGE_FILES = "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tga *.webp);;All files (*)"
CANT_READ_IMAGE = "That file can't be read as an image: {problem}"
WHERE = "Where"
WHERE_NOTE = "Drag it on the map to move it. It stands clear of the game's places."
#: (1.16.0) A place's description (Zodi's list, his fourth).
DESCRIPTION = "Description"
DESCRIPTION_NOTE = ("Shown under its name on the world map while the cursor rests on it, on two lines at the most: up "
                    "to 200 characters, one line break at the most. The game's own are 80 to 160 characters.")
#: (Mod Studio Framework 1.17.0) A battle ground's own random battles (Zodi's list, his fifth: "A battle on a mod's
#: own battle ground", his choice "Its own battles").
RANDOM_BATTLES = "Random battles"
RANDOM_BATTLE_LINE = "{battle}: {units} on {map}"
RANDOM_BATTLE_NO_MAP = "{battle}: {units}, no map yet"
ENEMIES_COUNT = {0: "no unit", 1: "1 unit"}
ENEMIES_MANY = "{n} units"
NO_RANDOM_BATTLE = "No random battle yet."
ADD_RANDOM_BATTLE = "Add a battle"
#: (Zodi, 4 November, his choice "Yes, the same sample") The quest's sample battle on map 116, never a copy.
ADD_RANDOM_BATTLE_TIP = "A random battle of the battle ground's own"
RANDOM_BATTLES_NOTE = ("Fought as the game's own battle grounds fight theirs: as Ramza arrives here, one of them picked "
                       "on as many arrivals as below, and one every time Search for Enemies is chosen standing here. "
                       "Double click a battle to change it.")
HOW_OFTEN = "How often"
HOW_OFTEN_SUFFIX = " of 100 arrivals"
HOW_OFTEN_TIP = "How many of 100 arrivals here start a battle: the game's own battle grounds start one on 31"
RANDOM_BATTLE_BAND = "RANDOM BATTLE"
RANDOM_BATTLE_AT = "At {place}"
RANDOM_BATTLE_BLURB = ("One of {place}'s random battles: its map, its units and where your units start. The game "
                       "fights it as one of its own random battles.")
RANDOM_BATTLE_MAP_NOTE = "Your quest maps first, by the names you gave them, then the game's maps."
RANDOM_BATTLE_STORY_NOTE = ("It is fought once the story is past this point; until then, only the battle ground's "
                            "other battles are.")
RANDOM_BATTLE_DEPLOY_NOTE = ("Click a tile on the map to add it to the squares or take it out; hold Ctrl to click a "
                             "tile a unit stands on. A random battle starts your units on one area, as the game's do.")
RANDOM_BATTLE_TAKEN = "The battle ground has a random battle named {name} already."
BACK_TO_PLACE = "Back to the place"
REMOVE_RANDOM_BATTLE = "Remove battle"
NOT_A_GROUND = "A town has no random battles: make it a battle ground for them."
NO_MAP_YET_CHOICE = "No map yet"
RANDOM_BATTLE_TITLE = "{battle}, at {place}, on {map}"
#: (Mod Studio Framework 1.18.0; its own art 1.19.0) A town's own menu (Zodi's list, his fifth: "a town's menu at a
#: mod's own town", his choice "Its own"; "Let the modder decide" which towns have one).
MENU_FIELD = "Enter Settlement"
MENU_TICK = "A menu of its own"
MENU_NOTE = ("As a town of the game's: an Outfitter selling the items below, a tavern telling your quests' rumors that "
             "name the town, the Warriors' Guild, and a Poachers' Den if ticked. Without one, there is no settlement "
             "to enter, as at some of the game's places.")
MENU_ART = "Its art"
MENU_ART_CHOICE = "{town}'s"
MENU_ART_NOTE = "The art its menu and its location info show: one of the game's towns', or your own."
GAME_ART, OWN_ART = "One of the game's towns' art", "Your own art"
OWN_ART_NOTE = ("Made from any image file you choose, fitted into 680 by 452 pixels, the size the game shows a "
                "town's art.")
CHOOSE_ART_TITLE = "Choose an image for {place}'s art"
OUTFITTER = "Outfitter"
OUTFITTER_EMPTY = "It sells nothing yet: add items, or copy a town's."
COPY_SHOP = "Copy {town}'s items"
COPY_SHOP_TIP = "The items {town}'s Outfitter sells, as your mod has the game's shops"
NO_SHOPS = "The game's shops aren't loaded here, so a town's items can't be copied."
NEVER_SOLD = ("Never sold, their Shop Availability past the story's last point (on the Items page): {items}.")
ADD_ITEM = "Add an item"
SELL_NOTHING = "Sell nothing"
OUTFITTER_NOTE = "Each item is sold once the story reaches the point the game's own Outfitters start selling it."
POACHERS_TICK = "A Poachers' Den"
POACHERS_NOTE = "Open once the story opens the game's own."
MENU_TAVERN = "Its tavern tells {rumors}."
MENU_NO_RUMOR = "Its tavern tells no rumor of your quests yet: tick the town on a rumor's card."
MENU_RUMOR = "{quest}'s {rumor}"
#: (Mod Studio Framework 1.20.0) A town darkened once a quest's flag is set (Zodi's list, his sixth: as the game's
#: Ziekden Fortress, Brigands' Den, Nelveska Temple, Fort Besselat, Mullonde and Golgollada Gallows).
DARK_FIELD = "Darkened"
DARK_NEVER = "Never"
DARK_CHOICE = "Once {flag} is set ({quest})"
DARK_NOTE = ("As the game darkens Ziekden Fortress or Brigands' Den once their event is done: its texture is shown "
             "darker on the world map once the flag is set. A step's flag is set once its event has played.")
DARK_NO_FLAGS = "Your quests have no flags yet: a step's flag is made with its step."
#: (Mod Studio Framework 1.21.0) A dungeon, a place like Midlight's Deep (Zodi's list, his seventh; his choices: "each
#: floor waiting for a quest flag the modder picks, or showing from the start if none is picked", and "a few random
#: battles per floor").
DUNGEON_KIND = "A dungeon, shown with a texture, listing its floors as Midlight's Deep lists its own"
FLOORS = "Floors"
FLOOR_LINE = "{floor}: {battles}, {listed}"
FLOOR_BATTLES_COUNT = {0: "no battle yet", 1: "1 battle"}
FLOOR_BATTLES_MANY = "{n} battles"
FLOOR_FROM_START = "listed from the start"
FLOOR_ONCE = "listed once {flag} is set ({quest})"
#: (Mod Studio Framework 1.24.0) A floor listed once the floor before it is won (Zodi, 2 November: "after they defeat
#: all enemies the next floor becomes available and so on"; his choice "Win once").
FLOOR_ONCE_WON = "listed once the floor before it is won"
NO_FLOOR = ("No floor yet: Add a floor makes one, listed when the dungeon is chosen on the world map, as Midlight's "
            "Deep lists its own.")
ADD_FLOOR = "Add a floor"
FLOORS_NOTE = ("Choosing the dungeon on the world map lists its floors in this order, as Midlight's Deep lists its "
               "own, and choosing a floor starts one of its battles, picked at random. Up to 10 floors. Double click "
               "a floor to change it.")
FLOOR_BAND = "FLOOR"
FLOOR_AT = "Of {place}"
FLOOR_BLURB = ("One of {place}'s floors: its name and words as the dungeon's list shows them, when it is listed, and "
               "its battles, one of which the game fights when the floor is chosen.")
FLOOR_NAME_TIP = "Letters, digits, spaces, underscores and hyphens, up to 24."
FLOOR_WORDS = "Words"
FLOOR_WORDS_NOTE = ("Shown beside the list while the floor is picked, as Midlight's Deep shows its floors' words: up to "
                    "200 characters, one line break at the most.")
FLOOR_LISTED = "Listed"
FLOOR_LISTED_START = "From the start"
FLOOR_LISTED_WON = "Once the floor before it is won"
#: The Listed choice of a floor waiting for the floor before it to be won (no quest's flag is named so).
FLOOR_WON_CHOICE = "won"
FLOOR_LISTED_NOTE = ("From the start, once the floor before it is won (winning any one of its battles once lists this "
                     "floor from then on), or once one of your quests' flags is set: a step's flag is set once its "
                     "event has played.")
FLOOR_FIRST_NOTE = ("The first floor is listed from the start, or once one of your quests' flags is set: a step's flag "
                    "is set once its event has played.")
FLOOR_BATTLES = "Battles"
NO_FLOOR_BATTLE = "No battle yet."
FLOOR_BATTLES_NOTE = ("Choosing the floor starts one of these, picked at random, with no deploy prompt, as Midlight's "
                      "Deep starts its own. Up to 8. Double click a battle to change it.")
#: (Mod Studio Framework 1.25.0) A floor's first battle: a step of one of the mod's quests waiting at it (its Place).
FIRST_BATTLE = "First battle"
FIRST_BATTLE_LINE = "{quest}'s step {n} ({event}) plays here first."
FIRST_BATTLE_NONE = ("None: a step of one of your quests plays here first, in place of the floor's battle, once its "
                     "Place is this floor (a boss battle, say).")
FIRST_BATTLE_NOTE = ("Each time the floor is chosen while the step's conditions hold, it plays in place of the floor's "
                     "battle. Played once only, it plays until it is done (a battle's step once its battle is won), "
                     "then the floor's own battles are fought. Winning its battle counts as winning the floor.")
BACK_TO_DUNGEON = "Back to the dungeon"
REMOVE_FLOOR = "Take out floor"
BACK_TO_FLOOR = "Back to the floor"
FLOOR_BATTLE_AT = "{floor}, {place}"
FLOOR_BATTLE_BLURB = ("One of the battles of {floor} at {place}: its map, its units and where your units start. "
                      "Choosing the floor starts one of its battles, picked at random.")
#: (Mod Studio Framework 1.23.0) A dungeon's art, its list's and its location info's (Zodi's choice after test 49,
#: "Its own art"), and its list's About page, its description (his "About Old Quarry").
DUNGEON_GAME_ART = "One of the game's places' art"
DUNGEON_ART_NOTE = "The art its list and its location info show: one of the game's places', or your own."
DUNGEON_OWN_ART_NOTE = ("Made from any image file you choose, fitted into 680 by 452 pixels, the size the game shows a "
                        "place's art.")
DUNGEON_ABOUT_NOTE = ("A dungeon's list shows these words on its About page, as Midlight's Deep shows its own; a dungeon "
                      "without them has no About page.")
WHERE_AT = "Its middle is at {x}, {y} on the world map."
ROADS = "Roads"
ROAD_OF_PLACE = "{road}, from {place}"
ADD_ROAD = "Add a road"
ROADS_NOTE = ("With a road picked, click the map to add a turn, drag a turn to move it, and right click one to take "
              "it out.")
NO_ROAD_YET = "No road joins it yet: the game can't travel to it until one does."
STEPS_HERE = "Steps here"
STEP_HERE = "{quest}'s step {n} waits here."
#: (Mod Studio Framework 1.25.0) A dungeon's step waiting at one of its floors.
STEP_AT_FLOOR = "{quest}'s step {n} waits at its floor {floor}."
NO_STEP_HERE = "No quest's step waits here yet. A step's Place on the Quests tab may name it."
PLACE_READY = "Ready: clear of the game's places, and joined to {places} by {roads}."
PLACE_READY_ALONE = "Ready, but no road joins it yet: the game can't travel to it until one does."
ROAD_BLURB = ("A road of your mod's own on the world map, joining two places. The game travels it as its own road, "
              "and Mod Studio draws its texture in the look of the game's trails.")
FROM, TO = "From", "To"
ENDS_NOTE = "Your mod's places first, then the game's."
TURNS = "Turns"
NO_TURNS = "None: it runs straight between its places."
TURNS_COUNT = "{n} turn{s} between its places."
ROAD_TURNS = "{n} turn{s}"
TURNS_NOTE = "Click the map to add a turn, drag a turn to move it, and right click one to take it out."
ITS_TEXTURE = "Its texture and walk"
DRAWN_NOTE = ("Drawn by Mod Studio along its places and turns in the look of the game's trails, {width} by {height}, "
              "with the {points} points Ramza walks along it.")
ROAD_READY = "Ready: it joins {start} and {end}."
#: A road's problem on its place's card, after the place's own words.
ROAD_PROBLEM_LEAD = "Its road: "
TOO_MANY_TURNS = "A road takes at most {most} turns between its places."
NEW_PLACE_TITLE, NEW_ROAD_TITLE = "New place", "New road"
NEW_PLACE_INTRO = ("A place of your mod's own on the world map, a folder of ModStudioPlaces by its name. Mod Studio "
                   "Framework gives it a number of its own as the game starts. It goes where the map is shown, "
                   "clear of the game's places: drag it from there.")
NEW_ROAD_INTRO = ("A road of your mod's own, a folder of ModStudioRoads by its name, joining two places: your mod's "
                  "or the game's. It runs straight between them until you add turns on the map.")
SAME_ENDS = "A road joins two places: pick another for its {end}."
OVERLAPS = "{place} would overlap {others} there: it stands clear of the game's places."
OFF_MAP = "{place} would run off the world map there."
PLACE_REMOVE_ASK = "Take the place {name} out of your mod?"
PLACE_REMOVE_ROADS = " Its roads go with it: {roads}."
PLACE_REMOVE_STEPS = " Its steps waiting there will need another place: {steps}."
ROAD_REMOVE_ASK = "Take the road {name} out of your mod?"
PICK_A_PLACE = "Pick a place or a road in the list, or make one with New place."
WORLD_PLACE_TITLE = {"place": "{place} and its road", "places": "{place} and its roads", "alone": "{place}",
                     "road": "{road}, from {start} to {end}", "none": "Your mod's places and roads"}
WORLD_PLACE_HINT = {
    "road": ("Drag {place} to move it. With {road} picked, click the map to add a turn, drag a turn to move it, and "
             "right click a turn to take it out."),
    "alone": "Drag {place} to move it. Drag the map to move about, and use the wheel to zoom.",
    "turns": ("Click the map to add a turn, drag a turn to move it, and right click a turn to take it out. Drag the "
              "map to move about, and use the wheel to zoom."),
    "none": "Click one of your mod's places to pick it. Drag the map to move about, and use the wheel to zoom."}

#: The map and the card's share of the page's height, the steps' rows the rest (as the Event Editor's).
TOP_SHARE = 0.7


def _label(text: str) -> str:
    """A name from Mod Studio's tables with its dashes as commas ("Chapter 1, Magick City of Gariland")."""
    return re.sub(r"\s+-\s+", ", ", str(text))


def _indent() -> QWidget:
    """Room as wide as a radio button's mark, so a control under one lines up with its words."""
    space = QWidget()
    space.setFixedWidth(22)
    return space


def _said(names: list) -> list:
    """(1.27.0) A set's names as a card says them: a status the game names Unused left out (kept as it is)."""
    return [n for n in names if not str(n).startswith("Unused")]


def _listed(names: list) -> str:
    """Names in words: "a", "a and b", "a, b and c"."""
    names = [str(n) for n in names]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


# =============================================================================
# Small parts
# =============================================================================

def muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "muted")
    label.setWordWrap(True)
    return label


def caption(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "muted")
    return label


def possessive(name: str) -> str:
    """A name in the possessive: "Dagger's", "Battle Boots'"."""
    return name + ("'" if name.endswith("s") else "'s")


def combo(choices, value=None, enabled: bool = True) -> QComboBox:
    """A dropdown of `[(data, words)]` (or of words alone), `value` picked; a value not among them added."""
    box = QComboBox()
    box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    box.setMinimumContentsLength(6)
    box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    for choice in choices:
        data, text = choice if isinstance(choice, tuple) else (choice, str(choice))
        box.addItem(str(text), data)
    if value is not None:
        index = box.findData(value)
        if index < 0:
            box.addItem(str(value), value)
            index = box.count() - 1
        box.setCurrentIndex(index)
    box.setEnabled(enabled)
    return box


def palette_combo(value: int) -> QComboBox:
    """(Zodi after test 62) One of 16 palettes, as wide as its words, as the Items page's Sprite and Palette has it."""
    box = combo([(n, PALETTE_CHOICE.format(n=n)) for n in range(16)], value)
    box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
    box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return box


def row(*widgets, stretch_first: bool = True) -> QWidget:
    holder = QWidget()
    line = QHBoxLayout(holder)
    line.setContentsMargins(0, 0, 0, 0)
    line.setSpacing(6)
    for n, w in enumerate(widgets):
        line.addWidget(w, 1 if (n == 0 and stretch_first) else 0)
    return holder


def pair(left: tuple, right: Optional[tuple] = None) -> QWidget:
    """Two fields side by side, each its caption over its control."""
    grid = QWidget()
    two = QGridLayout(grid)
    two.setContentsMargins(0, 0, 0, 0)
    two.setHorizontalSpacing(10)
    two.setVerticalSpacing(3)
    for column, entry in enumerate((left, right)):
        if entry is None:
            continue
        name, widget = entry
        two.addWidget(caption(name), 0, column)
        two.addWidget(widget, 1, column)
    two.setColumnStretch(0, 1)
    two.setColumnStretch(1, 1)
    return grid


def spin(value: int, least: int = 0, most: int = 255) -> QSpinBox:
    box = QSpinBox()
    box.setRange(least, most)
    box.setValue(int(value))
    box.setKeyboardTracking(False)
    return box


def nxd_names(state, key: str) -> dict:
    """`{row: name}` of one of the game's tables as the mod has it (`nxd_data.effective_names`), or {}."""
    try:
        return nxd_data.effective_names(state, key, "en")
    except Exception:                                                 # noqa: BLE001
        return {}


def place_name(place) -> str:
    """A start's place in words: one of the mod's own by its name, one of the game's by the game's."""
    if isinstance(place, str):
        return place
    return mr.GAME_PLACES.get(place, (f"place {place}",))[0]


def start_place(start) -> str:
    """(1.25.0) Where a start waits in words: its place, or a floor of one of the mod's dungeons."""
    floor = getattr(start, "floor", "")
    return FLOOR_PLACE.format(place=start.place, floor=floor) if floor else place_name(start.place)


def start_key(start):
    """(1.25.0) A start's Place's choice: its place, or its dungeon and floor (`FLOOR_KEY` between)."""
    floor = getattr(start, "floor", "")
    return f"{start.place}{FLOOR_KEY}{floor}" if floor else start.place


class CardPane(QFrame):
    """The right pane: a big card as the Event Editor's (its band, title, what it is, its fields, its foot)."""

    def __init__(self, band: str, right: str, colour: str, title: str, blurb: str):
        super().__init__()
        self.setObjectName("bigNode")
        self.setStyleSheet(f"#bigNode {{ border: 2px solid {colour}; border-radius: 8px; }}")
        card = QVBoxLayout(self)
        card.setContentsMargins(2, 2, 2, 2)
        card.setSpacing(0)
        self.band = NodeBand()
        self.band.set_words(band, right, colour)
        card.addWidget(self.band)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.inside = QWidget()
        self.column = QVBoxLayout(self.inside)
        self.column.setContentsMargins(12, 10, 12, 6)
        self.column.setSpacing(6)
        self.title = QLabel(title)
        self.title.setStyleSheet("font-weight: 600; font-size: 12pt;")
        self.title.setWordWrap(True)
        self.column.addWidget(self.title)
        # What it is; (Zodi, 4 November: "lets remove these notes") none said where a list has nothing to pick yet.
        self.blurb = muted(blurb)
        self.blurb.setVisible(bool(blurb))
        self.column.addWidget(self.blurb)
        self.fields = QVBoxLayout()
        self.fields.setContentsMargins(0, 4, 0, 4)
        self.fields.setSpacing(7)
        self.column.addLayout(self.fields)
        self.column.addStretch(1)
        self.scroll.setWidget(self.inside)
        card.addWidget(self.scroll, 1)
        foot = QWidget()
        self.foot = QVBoxLayout(foot)
        self.foot.setContentsMargins(12, 0, 12, 12)
        self.foot.setSpacing(6)
        self.foot.addWidget(Line())
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.foot.addWidget(self.status_label)
        card.addWidget(foot)
        self.buttons: dict = {}

    def keep_place(self, value: int) -> None:
        """(Zodi, 5 November: "clicking on an option in a drop down menu will throw you all the way back up to the top
        of the card you are on") Scrolled to `value` once its fields are laid out, as the card it was made again from
        was: as far down as it goes when it is shorter now."""
        bar = self.scroll.verticalScrollBar()
        self._place = int(value)

        def settle(_low=0, _high=0):
            if self._place is None:
                return
            bar.setValue(min(self._place, bar.maximum()))
            if bar.maximum() >= self._place:
                self._place = None

        def done():
            self._place = None

        bar.rangeChanged.connect(settle)
        settle()
        # Laid out by the time the events waiting now are done: a range that stays shorter keeps it at its foot.
        QTimer.singleShot(0, done)

    def field(self, name: str, *widgets) -> QWidget:
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(3)
        if name:
            column.addWidget(caption(name))
        for w in widgets:
            column.addWidget(w)
        self.fields.addWidget(holder)
        return holder

    def status(self, problems: list, ready: str = READY_SHORT, plain: list = ()) -> None:
        """What Mod Studio Framework would say of it (`problems`, in its words) after what Mod Studio says in its own
        (`plain`: a battle's squares where one of its units starts, Zodi's test 45), or `ready` when neither has."""
        lines = list(plain) + [SAYS.format(problem=p) for p in problems]
        if lines:
            self.status_label.setText("\n".join(lines))
            self.status_label.setStyleSheet(f"color: {theme.current()['danger']};")
        else:
            self.status_label.setText(ready)
            self.status_label.setStyleSheet(f"color: {theme.current()['ok']};")

    def add_buttons(self, *names) -> None:
        line = QWidget()
        across = QHBoxLayout(line)
        across.setContentsMargins(0, 2, 0, 0)
        across.setSpacing(6)
        for name in names:
            button = QPushButton(name)
            across.addWidget(button, 1)
            self.buttons[name] = button
        self.foot.addWidget(line)


class QuestStrip(NodeStrip):
    """The quest's steps, each on a row of its own, its name in the gutter, its cards wired in the order they play;
    a dashed line from one step's end to the next step's start (the player travels between them)."""

    GUTTER = 66.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list = []         # each card's row
        self.row_names: list = []    # each row's name in the gutter
        self.setAcceptDrops(False)

    def set_rows(self, cards: list, rows: list, row_names: list) -> None:
        self.rows, self.row_names = list(rows), list(row_names)
        self.set_cards(cards)
        # As wide as its longest row, so the scroll area round it scrolls to its last card.
        self.setMinimumWidth(self.sizeHint().width())

    def _place(self, index: int) -> tuple:
        row_ = self.rows[index] if index < len(self.rows) else 0
        column = sum(1 for r in self.rows[:index] if r == row_)
        return row_, column

    def card_rect(self, index: int, width=None) -> QRectF:
        row_, column = self._place(index)
        return QRectF(self.GUTTER + MARGIN + column * (CARD_W + GAP_X), MARGIN + row_ * (CARD_H + GAP_Y),
                      CARD_W, CARD_H)

    def heightForWidth(self, width: int) -> int:                     # noqa: N802
        rows = (max(self.rows) + 1) if self.rows else 1
        return int(2 * MARGIN + rows * CARD_H + (rows - 1) * GAP_Y)

    def sizeHint(self) -> QSize:                                      # noqa: N802
        columns = max([sum(1 for r in self.rows if r == x) for x in set(self.rows)] or [1])
        return QSize(int(self.GUTTER + 2 * MARGIN + columns * (CARD_W + GAP_X)), self.heightForWidth(self.width()))

    def mouseMoveEvent(self, event):                                  # noqa: N802
        # Cards are picked here, not dragged: a step's order is what it plays.
        return

    def _row_name(self, row_: int) -> str:
        return self.row_names[row_] if row_ < len(self.row_names) else ""

    def _paint_wires(self, p: QPainter) -> None:
        border = QColor(theme.current()["border"])
        muted_ = QColor(theme.current()["text_muted"])
        for index in range(1, len(self.cards)):
            a, b = self.card_rect(index - 1), self.card_rect(index)
            if RUMORS_ROW in (self._row_name(self.rows[index - 1]), self._row_name(self.rows[index])):
                # (1.15.0) The quest's rumors, each told on its own: nothing wired to or from them.
                continue
            if self.rows[index] == self.rows[index - 1]:
                p.setPen(QPen(border, 2.2))
                start, end = QPointF(a.right(), a.center().y()), QPointF(b.left(), b.center().y())
                p.drawLine(start, end)
                for point in (start, end):
                    p.setPen(QPen(QColor(20, 20, 20, 160), 1))
                    p.setBrush(border)
                    p.drawEllipse(point, 3.6, 3.6)
            elif self.rows[index] < len(self.row_names) and self.row_names[self.rows[index]] != UNPLAYED:
                p.setPen(QPen(muted_, 1.6, Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                mid = a.bottom() + GAP_Y / 2
                p.drawLine(QPointF(a.center().x(), a.bottom()), QPointF(a.center().x(), mid))
                p.drawLine(QPointF(a.center().x(), mid), QPointF(b.center().x(), mid))
                p.drawLine(QPointF(b.center().x(), mid), QPointF(b.center().x(), b.top()))
                font = QFont(self.font())
                font.setPixelSize(11)
                p.setFont(font)
                spot = QRectF((a.center().x() + b.center().x()) / 2 - 26, mid - 8, 52, 16)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(theme.current()["window_bg"]))
                p.drawRoundedRect(spot, 4, 4)
                p.setPen(muted_)
                p.drawText(spot, int(Qt.AlignCenter), LATER)

    def paintEvent(self, event):                                      # noqa: N802
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        font = QFont(self.font())
        font.setPixelSize(12)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(theme.current()["text_muted"]))
        for row_, name in enumerate(self.row_names):
            top = MARGIN + row_ * (CARD_H + GAP_Y)
            p.drawText(QRectF(4, top, self.GUTTER, CARD_H), int(Qt.AlignVCenter | Qt.AlignLeft), name)
        p.end()


# =============================================================================
# The world map
# =============================================================================

#: Where the world map's files are in the unpacked game (its layout, as the UI Layouts page reads layouts).
WORLD_LAYOUT = "ui/ffto/worldmap/worldmap_map_all.uib"
TEXTURE_FOLDER = "ui/ffto/worldmap/texture"
PARTS_FOLDER = "ui/ffto/worldmap/textureparts"
#: The world map's own textures, by how their part lists' names end: the map and the game's roads.
MAP_TEXTURE, ROUTES_TEXTURE = "ui_wm_map_uitx", "ui_wm_route_all_uitx"
#: The parts the places are drawn with: the towns' textures (each its town's part by name) and a battle
#: ground's point (its part named Default).
ICONS_PARTS = "UITextureParts://ui/ffto/worldmap/textureparts/ui_wm_icon_base_uitx"
POINT_PARTS = "UITextureParts://ui/ffto/worldmap/textureparts/ffto_wm_pos_point_uitx"
POINT_PART = "Default"
#: Where a place's picture is drawn about its middle: a town's 172 by 172; a battle ground's point 100 by 100,
#: 18 and 17 left of and above its 64 by 64 piece (the layout's PointTex in each Point).
TOWN_HALF, POINT_LEFT, POINT_UP, POINT_SIZE = 86, 50, 49, 100
#: The quest marker's texture (Mod Studio Framework's own, in the helper's folder), drawn in the quest's color.
MARKER_TEXTURE = "helper/marker/msq_quest_marker_uitx.png"


def _walk(box, at=(0, 0)):
    """A layout's box and every box in it, each with where it is on the layout (its parents' places added)."""
    here = (at[0] + box.origin[0], at[1] + box.origin[1])
    yield box, here
    for inner in box.children:
        yield from _walk(inner, here)


def _placed(layout, component: str) -> list:
    found = layout.components.get(component)
    return [pair for top in (found.boxes if found is not None else []) for pair in _walk(top)]


class WorldWorker(Worker):
    """Draws the world map off the interface thread: the game's map and roads, as one QImage (3840 by 2288, the
    map's own size), with the game's places' pieces where its layout puts them and the textures the mod's places
    are shown with (the game's 23 town textures and its battle grounds' point) beside it, for the view to draw over
    the mod's roads as the game draws its places over its roads. Finishes with `(image, words, pieces)`: image None
    and what to say when it can't be drawn (no pieces then); pieces `{"places": [(QImage, QRectF)], "icons": {name:
    QImage}, "point": QImage or None}`."""

    def __init__(self, game_dir: Path, texture_edits: dict, decode, decode_replacement):
        super().__init__()
        self.game_dir = Path(game_dir)
        self.texture_edits = {r: dict(v) for r, v in (texture_edits or {}).items()}
        self.decode, self.decode_replacement = decode, decode_replacement

    def run(self):
        path = self.game_dir / WORLD_LAYOUT
        if not path.is_file():
            return None, NO_WORLD_FILES.format(problem=f"no {WORLD_LAYOUT}"), {}
        try:
            layout = uib.read_layout(path)
        except (OSError, uib.UibError) as exc:
            return None, NO_WORLD.format(problem=exc), {}
        pictures = lp.Pictures(self.game_dir, self.texture_edits, self.decode, self.decode_replacement)
        map_box = next((box for box, _ in _placed(layout, "MapAll")
                        if box.kind == "Image" and box.textures and box.textures[0].uri.endswith(MAP_TEXTURE)), None)
        if map_box is None:
            return None, NO_WORLD.format(problem="its layout has no map"), {}
        ground = pictures.piece(map_box.textures[0])
        if ground is None:
            said = "; ".join(f"{k}: {v}" for k, v in pictures.missing.items()) or "its map can't be read"
            gone = not (self.game_dir / TEXTURE_FOLDER / f"{MAP_TEXTURE}.tex").is_file()
            return None, (NO_WORLD_FILES if gone else NO_WORLD).format(problem=said), {}
        width, height = map_box.size
        image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        p = QPainter(image)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(QRectF(0, 0, width, height), ground)
        for box, (x, y) in _placed(layout, "Route"):
            if box.kind == "Image" and box.textures and box.textures[0].uri.endswith(ROUTES_TEXTURE):
                piece = pictures.piece(box.textures[0])
                if piece is not None:
                    p.drawImage(QRectF(x, y, box.size[0], box.size[1]), piece)
        p.end()
        icon_parts = pictures.part_list(ICONS_PARTS.split("://", 1)[1] + ".utexpt")
        icon_index = {part.name: n for n, part in enumerate(icon_parts.parts)} if icon_parts is not None else {}
        icons = {}
        for name in mp.ICONS:
            piece = pictures.piece(uib.TextureRef(ICONS_PARTS, icon_index[name])) if icon_index.get(name) else None
            if piece is not None:
                icons[name] = piece
        point_parts = pictures.part_list(POINT_PARTS.split("://", 1)[1] + ".utexpt")
        point_index = next((n for n, part in enumerate(point_parts.parts) if part.name == POINT_PART), None) \
            if point_parts is not None else None
        point = pictures.piece(uib.TextureRef(POINT_PARTS, point_index)) if point_index else None
        places = []
        for box, (x, y) in _placed(layout, "Bases"):
            if box.kind != "Reference":
                continue
            if box.name.startswith("Base"):
                # (3 November) Nelveska Temple's and Midlight's Deep's pieces too: each by the picture the game gives
                # it (`map_places.base_icon`), not its name.
                piece = icons.get(mp.base_icon(box.name[4:]))
                if piece is not None:
                    places.append((piece, QRectF(x, y, box.size[0], box.size[1])))
            elif box.name.startswith("Point") and point is not None:
                places.append((point, QRectF(x + box.size[0] / 2 - POINT_LEFT, y + box.size[1] / 2 - POINT_UP,
                                             POINT_SIZE, POINT_SIZE)))
        return image, "", {"places": places, "icons": icons, "point": point}


class WorldMapView(QWidget):
    """The world map drawn, a part of it at a time: drag to move it, the wheel to zoom; each place's name on a label
    of Mod Studio's, the quest's markers in its color, the place picked in gold; a click on a place says which.

    Drawn as the game draws it: its map and roads (`image`, `WorldWorker`), the mod's roads (`mod_roads`), the
    game's places' pieces (`pieces`), the mod's places (`mod_places`), then the labels and markers. With the Places
    tab (`edit_place`, `edit_road`): the mod's place picked is dragged to move it, and the road picked shows its
    turns, which a click on the map adds to, a drag moves and a right click takes out."""

    place_clicked = Signal(object)
    #: (Places) the place `edit_place` dropped at a new middle; a turn of `edit_road` added (its place among the
    #: road's turns, x, y), moved (which, x, y) or taken out (which).
    place_dropped = Signal(str, int, int)
    turn_added = Signal(int, int, int)
    turn_moved = Signal(int, int, int)
    turn_removed = Signal(int)

    #: How near a turn the pointer must be to take it (the view's pixels), and a turn's dot's radius.
    TURN_REACH, TURN_DOT = 10.0, 6.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image: Optional[QImage] = None
        self.message = DRAWING_WORLD
        # (Zodi, 3 November: "can the map start zoomed out and centered") It opens on the whole map, centered, fitted to
        # the view whatever its size (`across` None); a pick brings it to what is picked as before (`PICKED_ACROSS`).
        self.centre = QPointF(mp.MAP_WIDTH / 2, mp.MAP_HEIGHT / 2)
        self.across: Optional[float] = None
        self.places: dict = {}          # {place: (x, y, town)}: every place a step may wait at
        self.markers: list = []         # [(place, words, gold)]
        self.marker_colour = QColor("#4080E0")
        self.picked = None
        #: (1.15.0) The places outlined as the one picked is: a rumor's towns.
        self.outlined: set = set()
        self.marker_image: Optional[QImage] = None
        #: The game's places' pieces, drawn over the mod's roads ([(QImage, QRectF)]), and the textures the mod's
        #: places are shown with (`WorldWorker`'s pieces).
        self.pieces: list = []
        self.icons: dict = {}
        self.point: Optional[QImage] = None
        #: The mod's places: {name: (x, y, town, its own texture or None, the game's town texture's name)}.
        self.mod_places: dict = {}
        #: The mod's roads: [(name, QImage, (x, y))], each its texture where its top left corner is.
        self.mod_roads: list = []
        #: (Places) the mod's place that can be dragged, and the road whose turns are shown: (name, [points from
        #: its From's middle through its turns to its To's]).
        self.edit_place: Optional[str] = None
        self.edit_road: Optional[tuple] = None
        self._press = None
        self._moved = False
        self._dragging = None           # ("place", (x, y)) or ("turn", which, (x, y))
        self.setMouseTracking(True)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_image(self, image: Optional[QImage], message: str = "") -> None:
        self.image, self.message = image, message
        self.update()

    def set_pieces(self, pieces: dict) -> None:
        self.pieces = list((pieces or {}).get("places") or [])
        self.icons = dict((pieces or {}).get("icons") or {})
        self.point = (pieces or {}).get("point")
        self.update()

    # -- the Places tab's editing ----------------------------------------------------------------------

    def turn_at(self, point: QPointF) -> Optional[int]:
        """The turn of `edit_road` under a point of the view (its place among the road's turns), or None."""
        if not self.edit_road:
            return None
        points = self.edit_road[1]
        best, best_distance = None, None
        for n, (x, y) in enumerate(points[1:-1]):
            at = self.to_view(x, y)
            distance = (at.x() - point.x()) ** 2 + (at.y() - point.y()) ** 2
            if distance <= self.TURN_REACH ** 2 and (best_distance is None or distance < best_distance):
                best, best_distance = n, distance
        return best

    def on_edit_place(self, point: QPointF) -> bool:
        """Whether a point of the view is on the piece of the place that can be dragged."""
        if self.edit_place is None or self.edit_place not in self.mod_places:
            return False
        x, y, town = self.mod_places[self.edit_place][:3]
        half = TOWN_HALF if town else 32
        where = self.to_map(point)
        return abs(where.x() - x) <= half and abs(where.y() - y) <= half

    def insert_at(self, x: float, y: float) -> int:
        """Where a turn at (x, y) goes among `edit_road`'s turns: between the two points of the road whose stretch
        passes nearest it."""
        points = self.edit_road[1]
        best, best_distance = 0, None
        for n, (a, b) in enumerate(zip(points, points[1:])):
            dx, dy = b[0] - a[0], b[1] - a[1]
            span = dx * dx + dy * dy
            u = 0.0 if span == 0 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / span))
            distance = (a[0] + u * dx - x) ** 2 + (a[1] + u * dy - y) ** 2
            if best_distance is None or distance < best_distance:
                best, best_distance = n, distance
        return best

    #: How much of the map's width a pick shows (what the map opened on before it opened on the whole map).
    PICKED_ACROSS = 1180.0
    #: How near the wheel zooms in (the map's pixels across the view).
    NEAREST_ACROSS = 300.0

    def show_place(self, x: float, y: float, across: Optional[float] = None) -> None:
        """The map brought to (x, y): `across` of its pixels across the view when given, else as now (from the whole
        map, `PICKED_ACROSS`)."""
        self.centre = QPointF(x, y)
        if across:
            self.across = float(across)
        elif self.across is None:
            self.across = self.PICKED_ACROSS
        self.update()

    def show_whole(self) -> None:
        """The whole map, centered, fitted to the view."""
        self.centre = QPointF(mp.MAP_WIDTH / 2, mp.MAP_HEIGHT / 2)
        self.across = None
        self.update()

    def fitted_across(self) -> float:
        """The map's pixels across the view that show all of it: its width, or more where the view is wider than the
        map is (its height then fitted)."""
        return max(float(mp.MAP_WIDTH), mp.MAP_HEIGHT * self.width() / max(1.0, float(self.height())))

    def scale(self) -> float:
        return self.width() / max(1.0, self.across if self.across is not None else self.fitted_across())

    def to_view(self, x: float, y: float) -> QPointF:
        s = self.scale()
        return QPointF((x - self.centre.x()) * s + self.width() / 2, (y - self.centre.y()) * s + self.height() / 2)

    def to_map(self, point: QPointF) -> QPointF:
        s = self.scale()
        return QPointF((point.x() - self.width() / 2) / s + self.centre.x(),
                       (point.y() - self.height() / 2) / s + self.centre.y())

    def place_at(self, point: QPointF):
        """The place under a point of the view, the nearest within its picture's reach, or None."""
        best, best_distance = None, None
        where = self.to_map(point)
        for place, (x, y, town) in self.places.items():
            reach = 80 if town else 34
            distance = (x - where.x()) ** 2 + (y - where.y()) ** 2
            if distance <= reach * reach and (best_distance is None or distance < best_distance):
                best, best_distance = place, distance
        return best

    def mousePressEvent(self, event):                                 # noqa: N802
        if event.button() == Qt.RightButton:
            turn = self.turn_at(event.position())
            if turn is not None:
                self.turn_removed.emit(turn)
            self._press = None
            return
        self._press = (event.position(), QPointF(self.centre))
        self._moved = False
        turn = self.turn_at(event.position())
        if turn is not None:
            self._dragging = ("turn", turn, tuple(self.edit_road[1][turn + 1]))
        elif self.on_edit_place(event.position()):
            x, y = self.mod_places[self.edit_place][:2]
            self._dragging = ("place", (x, y))
        else:
            self._dragging = None

    def mouseMoveEvent(self, event):                                  # noqa: N802
        if self._press is None:
            return
        start, centre = self._press
        delta = event.position() - start
        if abs(delta.x()) + abs(delta.y()) > 4:
            self._moved = True
        if not self._moved:
            return
        s = self.scale()
        if self._dragging is not None:
            origin = self._dragging[-1]
            x, y = round(origin[0] + delta.x() / s), round(origin[1] + delta.y() / s)
            if self._dragging[0] == "turn":
                points = list(self.edit_road[1])
                points[self._dragging[1] + 1] = (x, y)
                self.edit_road = (self.edit_road[0], points)
            else:
                name = self.edit_place
                self.mod_places[name] = (x, y) + tuple(self.mod_places[name][2:])
            self.update()
            return
        self.centre = QPointF(centre.x() - delta.x() / s, centre.y() - delta.y() / s)
        self.update()

    def mouseReleaseEvent(self, event):                               # noqa: N802
        if self._press is None:
            return
        dragging, self._dragging = self._dragging, None
        if self._moved and dragging is not None:
            if dragging[0] == "turn":
                x, y = self.edit_road[1][dragging[1] + 1]
                self.turn_moved.emit(dragging[1], int(x), int(y))
            else:
                x, y = self.mod_places[self.edit_place][:2]
                self.place_dropped.emit(self.edit_place, int(x), int(y))
        elif not self._moved and dragging is None:
            # A click: on a place, that place; elsewhere, with a road's turns shown, a turn there (where only the
            # mod's own places are picked: a turn may go near one of the game's).
            place = self.place_at(event.position())
            if self.edit_road is not None and place not in self.mod_places:
                place = None
            if place is not None:
                self.place_clicked.emit(place)
            elif self.edit_road is not None:
                where = self.to_map(event.position())
                self.turn_added.emit(self.insert_at(where.x(), where.y()), round(where.x()), round(where.y()))
        self._press = None

    def wheelEvent(self, event):                                      # noqa: N802
        steps = event.angleDelta().y() / 120.0
        most = self.fitted_across()
        across = max(self.NEAREST_ACROSS, min(most, (self.across or most) * (0.85 ** steps)))
        # Zoomed all the way out: the whole map, centered, fitted to the view as it changes size.
        if across >= most:
            self.show_whole()
            return
        self.across = across
        self.update()

    def _where(self, place) -> tuple:
        """(x, y, a town) of a place: one of the mod's where it is drawn now (dragged or not), else as `places` has
        it."""
        if place in self.mod_places:
            return tuple(self.mod_places[place][:3])
        return self.places[place]

    def paintEvent(self, event):                                      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(theme.current()["surface_alt"]))
        if self.image is None:
            p.setPen(QColor(theme.current()["text_muted"]))
            p.drawText(self.rect().adjusted(20, 20, -20, -20), int(Qt.AlignCenter | Qt.TextWordWrap), self.message)
            p.end()
            return
        s = self.scale()
        top_left = self.to_map(QPointF(0, 0))
        source = QRectF(top_left.x(), top_left.y(), self.width() / s, self.height() / s)
        p.drawImage(QRectF(0, 0, self.width(), self.height()), self.image, source)
        dragging_turn = self._dragging is not None and self._dragging[0] == "turn" and self._moved
        # The mod's roads under every place, as the game draws its own (the one whose turn is dragged as a line).
        for name, picture, (x, y) in self.mod_roads:
            if picture is None or (dragging_turn and self.edit_road and name == self.edit_road[0]):
                continue
            p.drawImage(QRectF(self.to_view(x, y), self.to_view(x + picture.width(), y + picture.height())), picture)
        for picture, rect in self.pieces:
            p.drawImage(QRectF(self.to_view(rect.left(), rect.top()), self.to_view(rect.right(), rect.bottom())),
                        picture)
        for name, (x, y, town, own, icon) in self.mod_places.items():
            if town:
                picture = own if own is not None else self.icons.get(icon)
                rect = QRectF(self.to_view(x - TOWN_HALF, y - TOWN_HALF), self.to_view(x + TOWN_HALF, y + TOWN_HALF))
            else:
                picture = self.point
                rect = QRectF(self.to_view(x - POINT_LEFT, y - POINT_UP),
                              self.to_view(x - POINT_LEFT + POINT_SIZE, y - POINT_UP + POINT_SIZE))
            if picture is not None:
                p.drawImage(rect, picture)
            else:
                p.setPen(QPen(QColor(40, 30, 20, 220), 2))
                p.setBrush(QColor(214, 190, 140, 200))
                p.drawEllipse(rect.center(), 10 * s * (3 if town else 1), 10 * s * (3 if town else 1))
        font = QFont(self.font())
        font.setPixelSize(11)
        p.setFont(font)
        gold = QColor(theme.current()["accent"])
        for place in [self.picked] + sorted(self.outlined, key=str):
            if place not in self.places:
                continue
            # The place picked (and (1.15.0) a rumor's towns), outlined as the mock-up outlines it: its piece's
            # square, dashed in gold.
            x, y, town = self._where(place)
            half = TOWN_HALF if town else 32
            p.setPen(QPen(gold, 2, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(self.to_view(x - half, y - half), self.to_view(x + half, y + half)))
        for place in self.places:
            x, y, town = self._where(place)
            spot = self.to_view(x, y + (66 if town else 32))
            if not self.rect().adjusted(-200, -40, 200, 40).contains(spot.toPoint()):
                continue
            name = place_name(place)
            width = p.fontMetrics().horizontalAdvance(name) + 14
            box = QRectF(spot.x() - width / 2, spot.y() - 9, width, 18)
            picked = place == self.picked or place in self.outlined
            p.setPen(QPen(gold if picked else QColor(96, 100, 108, 210), 2 if picked else 1))
            p.setBrush(QColor(20, 21, 24, 210))
            p.drawRoundedRect(box, 6, 6)
            p.setPen(QColor(250, 240, 214) if picked else QColor(226, 228, 232))
            p.drawText(box, int(Qt.AlignCenter), name)
        for place, words_, gold_label in self.markers:
            if place not in self.places:
                continue
            x, y, town = self._where(place)
            mx, my = (x - 86 + 67 - 18, y - 86 - 25 - 24) if town else (x - 32 + 12 - 18, y - 32 - 45 - 24)
            at = self.to_view(mx, my)
            size = QSize(round(78 * s * 0.9), round(98 * s * 0.9))
            if self.marker_image is not None:
                p.drawImage(QRectF(at.x(), at.y(), size.width(), size.height()), self.marker_image)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(self.marker_colour)
                p.drawEllipse(QRectF(at.x(), at.y(), size.width(), size.width()))
            width = p.fontMetrics().horizontalAdvance(words_) + 14
            box = QRectF(at.x() + size.width() + 4, at.y() + size.height() * 0.38 - 9, width, 18)
            p.setPen(QPen(gold if gold_label else QColor(96, 100, 108, 210), 2 if gold_label else 1))
            p.setBrush(QColor(20, 21, 24, 210))
            p.drawRoundedRect(box, 6, 6)
            p.setPen(QColor(250, 240, 214) if gold_label else QColor(226, 228, 232))
            p.drawText(box, int(Qt.AlignCenter), words_)
        if self.edit_road:
            # The road picked: its turns as dots, as the mock-up drew them; a line through them while one is dragged.
            points = [self.to_view(x, y) for x, y in self.edit_road[1]]
            if dragging_turn:
                p.setPen(QPen(QColor(250, 240, 214), 2.4, Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                for a, b in zip(points, points[1:]):
                    p.drawLine(a, b)
            p.setPen(QPen(QColor(30, 30, 34), 2))
            p.setBrush(QColor(250, 246, 236))
            for at in points[1:-1]:
                p.drawEllipse(at, self.TURN_DOT, self.TURN_DOT)
        p.end()


def tinted_marker(colour: QColor) -> Optional[QImage]:
    """The helper's quest marker in a color, multiplied in as the world map colors it (`make_marker_picture`)."""
    source = paths.bundled_root() / MARKER_TEXTURE
    image = QImage(str(source))
    if image.isNull():
        return None
    image = image.convertToFormat(QImage.Format_ARGB32).copy(1, 1, 78, 98)
    out = QImage(image.size(), QImage.Format_ARGB32)
    for y in range(image.height()):
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            out.setPixelColor(x, y, QColor(pixel.red() * colour.red() // 255, pixel.green() * colour.green() // 255,
                                           pixel.blue() * colour.blue() // 255, pixel.alpha()))
    return out


# =============================================================================
# Dialogs
# =============================================================================

class NewQuestDialog(QDialog):
    """(Zodi, 4 November: "So when the user clicks on New Quest it will bring up a menu that only has three things on it
    Name, Place, and Marker so that user can input the quest name and select the place where the quest starts using that
    drop down we already have and toggle if they want a quest marker over the place they chose and if so what color";
    his choice, a story point too) A new quest's name (letters, digits, spaces, underscores and hyphens, not one
    taken), the place it starts at (`places`, a step's Place's choices), when it is available (`points`, the story
    points a step's When lists) and its marker, ticked, in a color. `answer`: (its name, its place, its story point or
    None, its marker's color or "")."""

    def __init__(self, parent, name: str, taken, places: list, points: list, colour: str = ""):
        super().__init__(parent)
        self.setWindowTitle(NEW_QUEST_TITLE)
        self.taken = {t.lower() for t in taken}
        self.colour = colour or DEFAULT_MARKER
        column = QVBoxLayout(self)
        form = QFormLayout()
        self.name_box = QLineEdit(name)
        self.name_box.setMaxLength(64)
        self.name_box.setToolTip(NAME_TIP)
        form.addRow(NAME, self.name_box)
        # (Zodi, 5 November: "for the Place drop down only can you make it Alphabetical order") By name, the mod's and
        # the game's together.
        self.place_box = combo(sorted(places, key=lambda choice: str(choice[1]).lower()))
        form.addRow(PLACE, self.place_box)
        self.story_box = combo([(None, ANY_TIME)] + list(points))
        form.addRow(AVAILABLE, self.story_box)
        # Its marker as the quest's card shows it: the tick, its color's swatch and Choose a color.
        self.marker_box = QCheckBox(SHOW_MARKER)
        self.marker_box.setChecked(True)
        self.marker_box.setToolTip(MARKER_NOTE)
        self.swatch = QPushButton("")
        self.swatch.setFixedSize(46, 24)
        self.swatch.clicked.connect(self.choose_colour)
        self.colour_button = QPushButton(CHOOSE_COLOUR)
        self.colour_button.clicked.connect(self.choose_colour)
        self.marker_box.toggled.connect(self.colour_button.setEnabled)
        self.marker_box.toggled.connect(self.swatch.setEnabled)
        form.addRow(MARKER, self.marker_box)
        form.addRow("", row(self.swatch, self.colour_button, stretch_first=False))
        column.addLayout(form)
        self.note = QLabel("")
        self.note.setProperty("role", "danger")
        self.note.setWordWrap(True)
        column.addWidget(self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        column.addWidget(buttons)
        self.setMinimumWidth(460)
        self._show_colour()

    def _show_colour(self) -> None:
        self.swatch.setStyleSheet(f"background: {self.colour}; border: 1px solid #00000080; border-radius: 4px;")

    def choose_colour(self) -> None:
        chosen = QColorDialog.getColor(QColor(self.colour), self, CHOOSE_COLOUR)
        if chosen.isValid():
            self.colour = chosen.name().upper()
            self._show_colour()

    def answer(self) -> tuple:
        return (self.name_box.text(), self.place_box.currentData(), self.story_box.currentData(),
                self.colour if self.marker_box.isChecked() else "")

    def problem(self) -> str:
        name = self.name_box.text()
        if not sq.good_name(name):
            return NAME_BAD
        if name.lower() in self.taken:
            return QUEST_TAKEN.format(name=name)
        return ""

    def _accept(self) -> None:
        said = self.problem()
        if said:
            self.note.setText(said)
            return
        self.accept()


def _kind_words(place: pe.PlaceEdit) -> str:
    """A place's kind in words: a town, a battle ground, (1.21.0) a dungeon."""
    return PLACE_KIND_WORDS[pe.DUNGEON if place.dungeon else place.town]


class PlaceDialog(QDialog):
    """A new place of the mod's (its name and kind), or a new road (its name and the two places it joins)."""

    def __init__(self, parent, title: str, intro: str, name: str, problem, ends=None, start=None, end=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.problem_of = problem
        column = QVBoxLayout(self)
        text = QLabel(intro)
        text.setWordWrap(True)
        column.addWidget(text)
        form = QFormLayout()
        self.name_box = QLineEdit(name)
        self.name_box.setMaxLength(64)
        self.name_box.setToolTip(PLACE_NAME_TIP)
        form.addRow(NAME, self.name_box)
        self.town_radio = self.battle_radio = self.dungeon_radio = self.start_box = self.end_box = None
        if ends is None:
            self.town_radio, self.battle_radio = QRadioButton(TOWN_KIND), QRadioButton(BATTLE_KIND)
            # (1.21.0) Or a dungeon.
            self.dungeon_radio = QRadioButton(DUNGEON_KIND)
            group = QButtonGroup(self)
            for button in (self.town_radio, self.battle_radio, self.dungeon_radio):
                group.addButton(button)
            self.town_radio.setChecked(True)
            form.addRow(KIND, self.town_radio)
            form.addRow("", self.battle_radio)
            form.addRow("", self.dungeon_radio)
        else:
            self.start_box, self.end_box = combo(ends, start), combo(ends, end)
            form.addRow(FROM, self.start_box)
            form.addRow(TO, self.end_box)
            form.addRow("", muted(ENDS_NOTE))
        column.addLayout(form)
        self.note = QLabel("")
        self.note.setProperty("role", "danger")
        self.note.setWordWrap(True)
        column.addWidget(self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        column.addWidget(buttons)
        self.setMinimumWidth(500)

    def answer(self) -> tuple:
        if self.start_box is not None:
            return self.name_box.text(), self.start_box.currentData(), self.end_box.currentData()
        if self.dungeon_radio is not None and self.dungeon_radio.isChecked():
            return self.name_box.text(), pe.DUNGEON
        return self.name_box.text(), self.town_radio.isChecked()

    def _accept(self) -> None:
        said = self.problem_of(*self.answer())
        if said:
            self.note.setText(said)
            return
        self.accept()


class ItemDialog(QDialog):
    """(1.26.0) A new item of the mod's; (Zodi after test 62, his to my recommendation for new users) its name, its
    category (each with the game's first item of it, whose numbers it starts with: `categories`, `[(category, its
    words, that item's number, its name, (its palette, its sprite))]`) and its Sprite and Palette, picked as the Items
    page picks them (`items.HeldSpriteDialog`, over `sprites`). `answer`: (its name, that item's number, its palette,
    its sprite)."""

    def __init__(self, parent, name: str, categories: list, sprites, problem):
        super().__init__(parent)
        self.setWindowTitle(NEW_ITEM_TITLE)
        self.problem_of = problem
        self._categories = {cat: (words, base, base_name, held) for cat, words, base, base_name, held in categories}
        self._sprites = sprites
        self._held_picked = False
        # (Zodi, 4 November) No intro: its name, its category, its Held or thrown, then whose stats it starts with.
        column = QVBoxLayout(self)
        form = QFormLayout()
        self.name_box = QLineEdit(name)
        self.name_box.setMaxLength(64)
        self.name_box.setToolTip(ITEM_NAME_TIP)
        form.addRow(NAME, self.name_box)
        self.category_box = combo([(cat, words) for cat, words, *_rest in categories],
                                  categories[0][0] if categories else None)
        self.category_box.currentIndexChanged.connect(self._category_chosen)
        form.addRow(CATEGORY_FIELD, self.category_box)
        self.held_icon = QLabel()
        self.held_icon.setFixedSize(32, 32)
        self.held_icon.setAlignment(Qt.AlignCenter)
        self.palette_box = palette_combo(0)
        self.palette_box.currentIndexChanged.connect(self._palette_chosen)
        self.choose = QPushButton(HELD_CHOOSE)
        self.choose.clicked.connect(self.choose_icon)
        form.addRow(HELD_FIELD, row(self.held_icon, self.palette_box, self.choose, QWidget(), stretch_first=False))
        # (Zodi, 4 November: "can you remove the "The sprite a unit holds up or throws in battle." line") Shown only
        # to say what choosing an icon needs, when the item texture can't be read.
        self.held_note = muted("")
        self.held_note.setVisible(False)
        form.addRow("", self.held_note)
        column.addLayout(form)
        self.category_note = muted("")
        column.addWidget(self.category_note)
        self.note = QLabel("")
        self.note.setProperty("role", "danger")
        self.note.setWordWrap(True)
        column.addWidget(self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        column.addWidget(buttons)
        self.setMinimumWidth(520)
        self.palette, self.sprite = 0, 0
        self._category_chosen()

    def base(self) -> int:
        entry = self._categories.get(self.category_box.currentData())
        return entry[1] if entry else 0

    def answer(self) -> tuple:
        return self.name_box.text(), self.base(), self.palette, self.sprite

    def _category_chosen(self, _index=None) -> None:
        entry = self._categories.get(self.category_box.currentData())
        if entry is None:
            return
        _words, _base, base_name, (palette, sprite) = entry
        self.category_note.setText(CATEGORY_NOTE.format(item=possessive(base_name)))
        # Its icon follows the category's first item until one is picked.
        if not self._held_picked:
            self._set_held(palette, sprite, picked=False)

    def _palette_chosen(self, _index) -> None:
        if self.palette_box.currentData() is not None and self.palette_box.currentData() != self.palette:
            self._set_held(self.palette_box.currentData(), self.sprite)

    def _set_held(self, palette: int, sprite: int, picked: bool = True) -> None:
        from .items import _picture_pixmap
        self.palette, self.sprite = int(palette), int(sprite)
        self._held_picked = self._held_picked or picked
        self.palette_box.blockSignals(True)
        index = self.palette_box.findData(self.palette)
        if index < 0:
            self.palette_box.addItem(PALETTE_CHOICE.format(n=self.palette), self.palette)
            index = self.palette_box.count() - 1
        self.palette_box.setCurrentIndex(index)
        self.palette_box.blockSignals(False)
        picture = self._sprites.held(self.palette, self.sprite) if self._sprites is not None else None
        drawn = _picture_pixmap(picture)
        if drawn is None:
            self.held_icon.clear()
        else:
            self.held_icon.setPixmap(drawn)
        self.held_icon.setToolTip(HELD_PICKED.format(sprite=self.sprite, palette=self.palette))
        readable = self._sprites is not None and self._sprites.items_drawable
        self.choose.setEnabled(readable)
        problem = "it isn't set" if self._sprites is None else self._sprites.item_problem
        self.held_note.setText("" if readable else HELD_MISSING.format(problem=problem))
        self.held_note.setVisible(not readable)

    def choose_icon(self) -> None:
        from .items import HeldSpriteDialog
        dialog = HeldSpriteDialog(self._sprites, self.palette, self.sprite, self.name_box.text() or NEW_ITEM, self)
        if dialog.exec():
            self._set_held(*dialog.choice())

    def _accept(self) -> None:
        said = self.problem_of(*self.answer()[:2])
        if said:
            self.note.setText(said)
            return
        self.accept()


class TicksDialog(QDialog):
    """(1.27.0) Names ticked: one of an item's sets of statuses or elements, `columns` across in their order."""

    def __init__(self, parent, title: str, intro: str, names: list, ticked, columns: int):
        super().__init__(parent)
        self.setWindowTitle(title)
        column = QVBoxLayout(self)
        text = QLabel(intro)
        text.setWordWrap(True)
        column.addWidget(text)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        self.boxes = {}
        down = -(-len(names) // columns)
        for n, name in enumerate(names):
            box = QCheckBox(name)
            box.setChecked(name in ticked)
            self.boxes[name] = box
            grid.addWidget(box, n % down, n // down)
        column.addLayout(grid)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        column.addWidget(buttons)

    def answer(self) -> list:
        return [name for name, box in self.boxes.items() if box.isChecked()]


class MakeDialog(QDialog):
    """A new step: where it waits (`places`) and whether it plays a scene or a battle first, and its name. (Zodi, 4
    November: "we stopped letting users copy items from the game so this applies to the new quests") Neither is a copy
    of the game's now: each starts as the sample on map 116 (`quest_edits.make_sample_scene`, `make_sample_battle`)."""

    def __init__(self, parent, title: str, places=None, kind: str = "scene", names: Optional[dict] = None, taken=(),
                 taken_words: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.taken = {t.lower() for t in taken}
        self.taken_words = taken_words or EVENT_TAKEN
        #: Its name for each kind (`{"scene": ..., "battle": ...}`): the name box follows the kind picked until the
        #: name is changed.
        self.names = dict(names or {})
        column = QVBoxLayout(self)
        form = QFormLayout()
        self.place_box = None
        if places is not None:
            self.place_box = combo(places)
            form.addRow(PLACE, self.place_box)
        self.kind_group = QButtonGroup(self)
        self.scene_radio, self.battle_radio = QRadioButton(A_SCENE), QRadioButton(A_BATTLE)
        for radio in (self.scene_radio, self.battle_radio):
            self.kind_group.addButton(radio)
        (self.scene_radio if kind == "scene" else self.battle_radio).setChecked(True)
        form.addRow(PLAYS, self.scene_radio)
        form.addRow("", self.battle_radio)
        self.name_box = QLineEdit(self.names.get(kind, ""))
        self.name_box.setMaxLength(64)
        self.name_box.setToolTip(NAME_TIP)
        form.addRow(EVENT_NAME, self.name_box)
        self.scene_radio.toggled.connect(self._kind_changed)
        column.addLayout(form)
        self.note = QLabel("")
        self.note.setProperty("role", "danger")
        self.note.setWordWrap(True)
        column.addWidget(self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        column.addWidget(buttons)
        self.setMinimumWidth(460)

    def kind(self) -> str:
        return "scene" if self.scene_radio.isChecked() else "battle"

    def _kind_changed(self, _on: bool) -> None:
        """The kind picked: its name in the name box, when the box still holds the other kind's."""
        if self.name_box.text() in self.names.values():
            self.name_box.setText(self.names.get(self.kind(), self.name_box.text()))

    def place(self):
        return self.place_box.currentData() if self.place_box is not None else None

    def problem(self) -> str:
        name = self.name_box.text()
        if not sq.good_name(name):
            return NAME_BAD
        if name.lower() in self.taken:
            return self.taken_words.format(name=name)
        return ""

    def _accept(self) -> None:
        said = self.problem()
        if said:
            self.note.setText(said)
            return
        self.accept()


# =============================================================================
# The page
# =============================================================================

class SideQuestsPage(QWidget):
    """The Side Quests page (see the module's notes)."""

    #: Something changed in the mod: Export's summary follows (`app.build_window`).
    edits_changed = Signal()
    #: A jump to another page: its tab and what to show there (a quest map on the Map Editor).
    navigate_requested = Signal(str, object)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        if getattr(self.state, "quests", None) is None:
            self.state.quests = {}
        #: The quest shown (its folder) and what of it is picked: ("quest",), ("start", index), ("event", name),
        #: ("done", index) or ("unit", battle, slot).
        self.folder: Optional[str] = None
        self.picked: tuple = ("quest",)
        #: Set by the suites: what a dialog would have answered (`_ask`).
        self.answers: list = []
        #: How the world map's textures are decoded (`layout_preview.default_decoder`); the suites give their own.
        self.decode = None
        self.decode_replacement = None
        self._game = None
        self._game_key = None
        self._story = None
        self._story_places: dict = {}
        self._world_key = None
        self._world_job = None
        self._world_thread = None
        self._building = False
        self._shown_event: Optional[str] = None
        self._shown_scene = False
        #: (1.14.0) The battle's own deploy area a tile clicked changes, `(battle, index)`; and each battle's own
        #: deploy areas while it starts on the game's, `{(quest, battle): [DeployArea]}`, to start on again.
        self._deploy_area = ("", 0)
        self._kept_deploy: dict = {}
        self._battles = None
        #: The unit card's sections opened or closed, kept from one unit to the next.
        self._open_sections: dict = {}
        self.field_widgets: dict = {}
        self.music = MusicPlayer(state, self)
        self.music.said.connect(self._say)
        self.music.changed.connect(self._music_changed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(8)
        outer.addLayout(page_intro(BLURB))
        self.split = QSplitter(Qt.Vertical)
        self.split.setChildrenCollapsible(False)
        outer.addWidget(self.split, 1)
        top = QWidget()
        top_row = QHBoxLayout(top)
        top_row.setContentsMargins(0, 0, 0, 0)
        self.panes = QSplitter(Qt.Horizontal)
        self.panes.setChildrenCollapsible(False)
        self.panes.setHandleWidth(14)
        top_row.addWidget(self.panes)
        self.split.addWidget(top)

        # -- the left: Quests and Places ---------------------------------------------------------
        left = QWidget()
        left.setMinimumWidth(200)
        column = QVBoxLayout(left)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        self.tabs = QTabBar()
        self.tabs.setExpanding(True)
        self.tabs.setUsesScrollButtons(False)
        for name in TABS:
            self.tabs.addTab(name)
        column.addWidget(self.tabs)
        self.left_stack = QStackedWidget()
        quests = QWidget()
        quests_column = QVBoxLayout(quests)
        quests_column.setContentsMargins(0, 0, 0, 0)
        quests_column.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText(QUEST_SEARCH)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        quests_column.addWidget(self.search)
        self.quest_list = QListWidget()
        self.quest_list.setAlternatingRowColors(True)
        self.quest_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.quest_list.currentItemChanged.connect(self._quest_picked)
        quests_column.addWidget(self.quest_list, 1)
        self.list_note = muted("")
        quests_column.addWidget(self.list_note)
        self.new_button = QPushButton(NEW_QUEST)
        self.new_button.clicked.connect(self.new_quest)
        self.remove_button = QPushButton(REMOVE)
        self.remove_button.clicked.connect(self.remove_quest)
        quests_column.addWidget(row(self.new_button, self.remove_button, stretch_first=False))
        self.left_stack.addWidget(quests)
        places = QWidget()
        places_column = QVBoxLayout(places)
        places_column.setContentsMargins(0, 0, 0, 0)
        places_column.setSpacing(6)
        self.place_search = QLineEdit()
        self.place_search.setPlaceholderText(PLACE_SEARCH)
        self.place_search.setClearButtonEnabled(True)
        self.place_search.textChanged.connect(self._filter_places)
        places_column.addWidget(self.place_search)
        self.place_list = QListWidget()
        self.place_list.setAlternatingRowColors(True)
        self.place_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.place_list.currentItemChanged.connect(self._place_list_picked)
        places_column.addWidget(self.place_list, 1)
        self.place_message = muted("")
        self.place_message.setVisible(False)
        places_column.addWidget(self.place_message)
        self.new_place_button = QPushButton(NEW_PLACE)
        self.new_place_button.clicked.connect(self.new_place)
        self.new_road_button = QPushButton(NEW_ROAD)
        self.new_road_button.clicked.connect(lambda: self.new_road())
        self.remove_place_button = QPushButton(REMOVE)
        self.remove_place_button.clicked.connect(self.remove_place_or_road)
        places_column.addWidget(row(self.new_place_button, self.new_road_button, self.remove_place_button,
                                    stretch_first=False))
        self.left_stack.addWidget(places)
        # (1.26.0) The Items tab: the mod's own items.
        items = QWidget()
        items_column = QVBoxLayout(items)
        items_column.setContentsMargins(0, 0, 0, 0)
        items_column.setSpacing(6)
        self.item_search = QLineEdit()
        self.item_search.setPlaceholderText(ITEM_SEARCH)
        self.item_search.setClearButtonEnabled(True)
        self.item_search.textChanged.connect(self._filter_items)
        items_column.addWidget(self.item_search)
        self.item_list = QListWidget()
        self.item_list.setAlternatingRowColors(True)
        self.item_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.item_list.currentItemChanged.connect(self._item_list_picked)
        items_column.addWidget(self.item_list, 1)
        self.item_message = muted("")
        self.item_message.setVisible(False)
        items_column.addWidget(self.item_message)
        self.new_item_button = QPushButton(NEW_ITEM)
        self.new_item_button.clicked.connect(self.new_item)
        self.remove_item_button = QPushButton(REMOVE)
        self.remove_item_button.clicked.connect(self.remove_item)
        items_column.addWidget(row(self.new_item_button, self.remove_item_button, stretch_first=False))
        self.left_stack.addWidget(items)
        #: (1.26.0) The Items tab's item picked (its folder), or None.
        self.item_pick: Optional[str] = None
        column.addWidget(self.left_stack, 1)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.panes.addWidget(left)

        # -- the middle: the world map, or a battle's or scene's map --------------------------
        self.middle = QStackedWidget()
        world = QWidget()
        world_column = QVBoxLayout(world)
        world_column.setContentsMargins(0, 0, 0, 0)
        world_column.setSpacing(6)
        self.world_title = QLabel("")
        self.world_title.setStyleSheet("font-weight: 600; font-size: 12pt;")
        world_column.addWidget(self.world_title)
        self.world = WorldMapView()
        self.world.place_clicked.connect(self._place_clicked)
        self.world.place_dropped.connect(self._place_dropped)
        self.world.turn_added.connect(self._turn_added)
        self.world.turn_moved.connect(self._turn_moved)
        self.world.turn_removed.connect(self._turn_removed)
        world_column.addWidget(self.world, 1)
        self.world_hint = muted("")
        world_column.addWidget(self.world_hint)
        self.middle.addWidget(world)
        self.battle_map = EncounterMap(state, self._map_units, self._map_title)
        self.battle_map.map_label.setVisible(False)
        self.battle_map.map_box.setVisible(False)
        self.battle_map.unit_picked.connect(self._unit_picked_on_map)
        self.battle_map.unit_moved.connect(self._unit_moved)
        self.battle_map.tile_clicked.connect(self._deploy_tile)
        self.middle.addWidget(self.battle_map)
        self.panes.addWidget(self.middle)

        # -- the right: the card ------------------------------------------------------------------
        self.card_holder = QStackedWidget()
        self.card_holder.setMinimumWidth(300)
        self.card: Optional[CardPane] = None
        self.panes.addWidget(self.card_holder)
        self.panes.setSizes([280, 900, 380])
        self.panes.setStretchFactor(1, 1)

        # -- under them: the steps (not with Places: the map takes the height, as the mock-up drew it) --------
        bottom = QWidget()
        self.bottom = bottom
        bottom_column = QVBoxLayout(bottom)
        bottom_column.setContentsMargins(0, 0, 0, 0)
        bottom_column.setSpacing(4)
        head = QHBoxLayout()
        self.quest_button = QPushButton(QUEST_BUTTON)
        self.quest_button.setToolTip(QUEST_BUTTON_TIP)
        self.quest_button.clicked.connect(lambda: self.pick(("quest",)))
        head.addWidget(self.quest_button)
        steps_title = QLabel(STEPS_TITLE)
        steps_title.setStyleSheet("font-weight: 600;")
        head.addWidget(steps_title)
        note = muted(STEPS_NOTE)
        note.setWordWrap(False)
        note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        head.addWidget(note, 1)
        self.add_step_button = QPushButton(ADD_STEP)
        self.add_step_button.clicked.connect(self.add_step)
        self.add_scene_button = QPushButton(ADD_SCENE)
        self.add_scene_button.setToolTip(ADD_SCENE_TIP)
        self.add_scene_button.clicked.connect(lambda: self.add_after("scene"))
        self.add_battle_button = QPushButton(ADD_BATTLE)
        self.add_battle_button.setToolTip(ADD_BATTLE_TIP)
        self.add_battle_button.clicked.connect(lambda: self.add_after("battle"))
        self.add_rumor_button = QPushButton(ADD_RUMOR)
        self.add_rumor_button.setToolTip(ADD_RUMOR_TIP)
        self.add_rumor_button.clicked.connect(self.add_rumor)
        for button in (self.add_step_button, self.add_scene_button, self.add_battle_button, self.add_rumor_button):
            head.addWidget(button)
        bottom_column.addLayout(head)
        self.strip = QuestStrip()
        self.strip.picked.connect(self._card_picked)
        self.strip_scroll = QScrollArea()
        self.strip_scroll.setWidgetResizable(True)
        self.strip_scroll.setWidget(self.strip)
        self.strip_scroll.setMinimumHeight(140)
        bottom_column.addWidget(self.strip_scroll, 1)
        self.message = muted("")
        self.message.setVisible(False)
        bottom_column.addWidget(self.message)
        self.split.addWidget(bottom)
        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 1)
        # The mock-up's share of the height, kept as the window changes until the divider is dragged: the map and
        # the card over about two steps' rows (`_share_height`, as the Event Editor's).
        self._height_dragged = False
        self.split.splitterMoved.connect(self._height_moved)
        #: What each card of the strip is: ("start", index), ("event", name) or ("done", index).
        self.strip_keys: list = []
        #: The Places tab's: what is picked, ("place", folder) or ("road", folder) or None; the road a place's card
        #: has picked (its turns on the map), by its folder; each road's texture drawn for the map, kept while its
        #: places and turns stay (`_road_drawn`).
        self.place_pick: Optional[tuple] = None
        self.place_road: Optional[str] = None
        self._road_drawings: dict = {}
        self._own_textures: dict = {}
        self.refresh_from_store()

    # =========================================================================
    # The game and the mod
    # =========================================================================

    def game_dir(self) -> Optional[Path]:
        root = getattr(self.state, "nxd_unpack_dir", None)
        return Path(root) if root and Path(root).is_dir() else None

    def find_program(self) -> Optional[Path]:
        """The game's program, from the folder of .pac files General Setup has (as the Event Editor finds it)."""
        return game_install.find_program(ui_settings.load().get("game_data_folder") or None)

    def program(self):
        """The game's program read as data (`event_setup.read_program`: its events' setups and the deploy areas),
        read once; None without it."""
        path = self.find_program()
        if path != getattr(self, "_program_path", "unread"):
            self._program_path = path
            try:
                self._program = su.read_program(path) if path is not None else None
            except (OSError, su.SetupError):
                self._program = None
        return self._program

    def game(self) -> Optional[qx.Game]:
        """The game's things a quest is made from (`quest_edits.Game`), or None without the unpacked game."""
        folder = self.game_dir()
        if folder is None:
            return None
        program = self.program()
        key = (str(folder), id(program), str(getattr(self.state, "nxd_sqlite_path", None)))
        if key != self._game_key:
            try:
                self._game = qx.Game(folder, program.records if program is not None else {},
                                     getattr(self.state, "nxd_sqlite_path", None))
            except es.ScriptError:
                self._game = None
            self._game_key = key
            self._story = None
            self._battles = None
        return self._game

    def lengths(self) -> Optional[es.Lengths]:
        game = self.game()
        return game.lengths if game is not None else None

    def quests(self) -> dict:
        quests = getattr(self.state, "quests", None)
        if quests is None:
            quests = self.state.quests = {}
        return quests

    def edits(self) -> Optional[qx.QuestEdits]:
        return self.quests().get(self.folder) if self.folder is not None else None

    def places_store(self) -> dict:
        """The mod's own places as the Places tab has them (`state.places`: `{folder: place_edits.PlaceEdit}`)."""
        places = getattr(self.state, "places", None)
        if places is None:
            places = self.state.places = {}
        return places

    def roads_store(self) -> dict:
        """The mod's own roads (`state.roads`: `{folder: place_edits.RoadEdit}`)."""
        roads = getattr(self.state, "roads", None)
        if roads is None:
            roads = self.state.roads = {}
        return roads

    def mod_places(self) -> dict:
        """`{name: map_places.Place}`: the mod's own places (the Places tab's), which a step may wait at."""
        return {place.name: place.place() for place in self.places_store().values()}

    def quest_map_names(self) -> list:
        return list(getattr(self.state, "quest_maps", None) or {})

    def problems(self, edits: Optional[qx.QuestEdits] = None) -> list:
        edits = edits or self.edits()
        if edits is None:
            return []
        return qx.problems(edits, self.lengths(), set(self.mod_places()), set(self.quest_map_names()))

    def all_places(self) -> list:
        """`[(place, words)]`: the mod's places by name first, then the game's by number."""
        out = [(name, name) for name in sorted(self.mod_places(), key=str.lower)]
        out += [(number, name) for number, (name, _town, _x, _y) in sorted(mr.GAME_PLACES.items())]
        return out

    def step_places(self) -> list:
        """(1.25.0) `[(place, words)]` a step's Place offers: the mod's places by name first, each of its dungeons'
        floors after it, then the game's by number."""
        floors = {p.name: [f.name for f in p.floors] for p in self.places_store().values() if p.dungeon}
        out = []
        for place, words in self.all_places():
            out.append((place, words))
            for floor in floors.get(place, []) if isinstance(place, str) else []:
                out.append((f"{place}{FLOOR_KEY}{floor}", FLOOR_PLACE.format(place=place, floor=floor)))
        return out

    def place_where(self) -> dict:
        """`{place: (x, y, town)}` for every place a step may wait at."""
        out = {number: (x, y, town) for number, (_name, town, x, y) in mr.GAME_PLACES.items()}
        out.update({name: (place.x, place.y, place.town) for name, place in self.mod_places().items()})
        return out

    def story_points(self) -> list:
        """`[(value, words)]`: the story's progress values the game's scenes set, each named by the scene that sets
        it (its map and number), read once from the game's scripts."""
        game = self.game()
        if game is None:
            return []
        if self._story is None:
            names = me_page.map_names(self.state)
            found = {}
            for number in es.game_script_numbers(game.folder, "enhanced"):
                try:
                    script = es.read_script(game.script(number), game.lengths, "enhanced")
                except (OSError, es.ScriptError):
                    continue
                for ins in script.instructions:
                    if ins.opcode == qx.ADD_OP and es.operand(ins, "variable") == qx.STORY:
                        value = es.operand(ins, "value")
                        found.setdefault(value, number)
            points, self._story_places = [], {}
            for value in sorted(found):
                event = found[value]
                place = names.get(game.setup(event).get("Map")) if game.setup(event) else None
                place = _label(place) if place else None
                self._story_places[value] = (place, event)
                points.append((value, STORY_POINT.format(place=place, event=event) if place
                               else STORY_EVENT.format(event=event)))
            self._story = points
        return self._story

    def music_titles(self) -> dict:
        """The music's names (`event_scripts.music_titles`), read once from the database."""
        path = getattr(self.state, "nxd_sqlite_path", None)
        if getattr(self, "_titles_key", None) != str(path):
            self._titles_key = str(path)
            self._titles = es.music_titles(path) if path else {}
            self.music.titles = self._titles
        return self._titles

    def game_battles(self) -> list:
        """`[(battle, words)]`: the game's battles to copy, by Mod Studio's names for them, read once a game."""
        game = self.game()
        if getattr(self, "_battles", None) is None:
            names = encounter_names.EncounterNames.load()
            count = 512 + (es.fifth_battle_count(game.folder) if game is not None else 0)
            self._battles = [(b, _label(names.label_for(b))) for b in range(1, count)]
        return self._battles

    # =========================================================================
    # The list
    # =========================================================================

    def refresh_from_store(self) -> None:
        """The lists and what is shown again, from `state.quests`, `state.places` and `state.roads` (an opened
        mod, a new mod)."""
        quests = self.quests()
        if self.folder not in quests:
            self.folder = next(iter(quests), None)
            self.picked = ("quest",)
        if self.place_pick is None or not self._pick_exists(self.place_pick):
            self.place_pick = self._first_place_pick()
            self.place_road = self._first_road_of(self.place_pick)
        elif self.place_road is not None and self.place_road not in self.roads_store():
            self.place_road = self._first_road_of(self.place_pick)
        self._fill_list()
        self._fill_places()
        self._fill_items()
        self.show_quest()

    def view_toggles_used(self) -> tuple:
        """`(notes, unknown, comments)`: none of the three. The page has no field notes, unknown fields or comment
        rows for them to hide."""
        return (False, False, False)

    def refresh_records(self) -> None:
        """After General Setup (a game unpacked, a mod opened) or Start a new mod: everything read again."""
        self._game_key = None
        self._world_key = None
        self.refresh_from_store()

    def showEvent(self, event):                                       # noqa: N802
        super().showEvent(event)
        self._share_height()
        # Back from another page: a quest map made, renamed or taken out on the Map Editor, the mod's maps' names.
        self.refresh_from_store()

    def resizeEvent(self, event):                                     # noqa: N802
        super().resizeEvent(event)
        self._share_height()

    def _height_moved(self, *_args) -> None:
        self._height_dragged = True

    def _share_height(self) -> None:
        """The map and the card TOP_SHARE of the height, the steps the rest, until the divider is dragged."""
        if self._height_dragged:
            return
        total = sum(self.split.sizes())
        if total <= 0:
            return
        top = max(self.split.widget(0).minimumSizeHint().height(), round(total * TOP_SHARE))
        top = min(top, total - self.split.widget(1).minimumSizeHint().height())
        self.split.blockSignals(True)
        self.split.setSizes([top, total - top])
        self.split.blockSignals(False)

    def hideEvent(self, event):                                       # noqa: N802
        # Another page opened: a piece playing stops.
        self.music.stop()
        super().hideEvent(event)

    def _fill_list(self) -> None:
        self.quest_list.blockSignals(True)
        self.quest_list.clear()
        for folder, edits in self.quests().items():
            places = [start_place(edits.quest.starts[s.start]) for s in qx.steps(edits.quest)]
            line = (f"{len(places)} step{'s' if len(places) != 1 else ''}: {', then '.join(places)}"
                    if places else "No steps yet")
            item = QListWidgetItem(f"{folder}\n{line}")
            item.setData(Qt.UserRole, folder)
            if edits.quest.marker:
                pix = QPixmap(12, 12)
                pix.fill(QColor(edits.quest.marker))
                item.setIcon(pix)
            item.setToolTip(line)
            self.quest_list.addItem(item)
            if folder == self.folder:
                self.quest_list.setCurrentItem(item)
        self.quest_list.blockSignals(False)
        self.list_note.setText(NO_GAME if self.game_dir() is None else "")
        self.list_note.setVisible(bool(self.list_note.text()))
        self.remove_button.setEnabled(self.folder is not None)
        self._filter(self.search.text())

    def _fill_places(self) -> None:
        """The Places tab's list: the mod's places, then its roads, each its name over a line saying it."""
        places, roads = self.places_store(), self.roads_store()
        if self.place_pick is not None and not self._pick_exists(self.place_pick):
            self.place_pick = self._first_place_pick()
        self.place_list.blockSignals(True)
        self.place_list.clear()
        for folder, place in places.items():
            count = len(pe.roads_at(roads, place.name))
            line = PLACE_LINE.format(kind=_kind_words(place), count=count, s="s" if count != 1 else "")
            ground = [b for b in place.battles if not b.floor]
            if not place.town and ground:
                many = len(ground)
                line += PLACE_BATTLES_LINE.format(n=many, s="s" if many != 1 else "")
            if place.dungeon:
                many = len(place.floors)
                line += PLACE_FLOORS_LINE.format(n=many, s="s" if many != 1 else "")
            if place.town and not place.dungeon and place.menu is not None:
                line += PLACE_MENU_LINE
            if place.town and not place.dungeon and place.darkened is not None:
                line += PLACE_DARK_LINE.format(flag=place.darkened.flag, quest=place.darkened.quest)
            item = QListWidgetItem(f"{place.name}\n" + line)
            item.setData(Qt.UserRole, ("place", folder))
            self.place_list.addItem(item)
        for folder, road in roads.items():
            item = QListWidgetItem(f"{road.name}\n" + ROAD_LIST_LINE.format(start=pe.place_words(road.start),
                                                                            end=pe.place_words(road.end)))
            item.setData(Qt.UserRole, ("road", folder))
            self.place_list.addItem(item)
        listed = self._listed_pick(self.place_pick)
        for n in range(self.place_list.count()):
            if self.place_list.item(n).data(Qt.UserRole) == listed:
                self.place_list.setCurrentRow(n)
        self.place_list.blockSignals(False)
        self.remove_place_button.setEnabled(self.place_pick is not None)
        self._filter_places(self.place_search.text())

    def _filter(self, text: str) -> None:
        wanted = text.strip().lower()
        for n in range(self.quest_list.count()):
            item = self.quest_list.item(n)
            item.setHidden(bool(wanted) and wanted not in item.text().lower())

    def _quest_picked(self, item, _previous=None) -> None:
        if item is None:
            return
        self.folder = item.data(Qt.UserRole)
        self.picked = ("quest",)
        self.remove_button.setEnabled(True)
        self.show_quest()

    def pick_quest(self, folder: str) -> None:
        for n in range(self.quest_list.count()):
            if self.quest_list.item(n).data(Qt.UserRole) == folder:
                self.quest_list.setCurrentRow(n)
                return

    # =========================================================================
    # What is shown
    # =========================================================================

    def show_quest(self) -> None:
        """The strip of the quest shown, and what is picked of it on the card and in the middle."""
        edits = self.edits()
        enabled = edits is not None and self.game() is not None
        for button in (self.add_step_button, self.add_scene_button, self.add_battle_button, self.quest_button,
                       self.add_rumor_button):
            # A rumor is the quest's own words: it needs no game files.
            button.setEnabled(enabled if button not in (self.quest_button, self.add_rumor_button)
                              else edits is not None)
        self._fill_strip()
        self._show_card()
        self._show_middle()

    def _fill_strip(self) -> None:
        edits = self.edits()
        cards, rows, names, keys = [], [], [], []
        if edits is not None:
            quest = edits.quest
            all_problems = self.problems(edits)
            if quest.rumors:
                # (1.15.0) Its tavern rumors first, each read before the steps waiting for it start.
                names.append(RUMORS_ROW)
                for rumor in quest.rumors:
                    cards.append(self._rumor_strip_card(rumor, all_problems))
                    rows.append(len(names) - 1)
                    keys.append(("rumor", rumor.name))
            for n, step in enumerate(qx.steps(quest)):
                start = quest.starts[step.start]
                names.append(STEP.format(n=n + 1))
                row_ = len(names) - 1
                cards.append(Card("other", start_place(start), self._start_line(quest, step),
                                  band=WAITS_AT, colour=START_COLOUR))
                rows.append(row_)
                keys.append(("start", step.start))
                for name in step.events:
                    cards.append(self._event_card(quest, name, all_problems))
                    rows.append(row_)
                    keys.append(("event", name))
                cards.append(Card("other", STEP_DONE.format(n=n + 1),
                                  SETS.format(flag=", ".join(step.sets)) if step.sets else SETS_NOTHING,
                                  band=DONE_BAND, colour=DONE_COLOUR))
                rows.append(row_)
                keys.append(("done", step.start))
            left = qx.unplayed(quest)
            if left:
                names.append(UNPLAYED)
                for name in left:
                    cards.append(self._event_card(quest, name, all_problems))
                    rows.append(len(names) - 1)
                    keys.append(("event", name))
        self.strip_keys = keys
        self.strip.set_rows(cards, rows, names)
        chosen = keys.index(self._strip_key()) if self._strip_key() in keys else -1
        self.strip.set_chosen(chosen)

    def _strip_key(self):
        if self.picked and self.picked[0] == "unit":
            return ("event", self.picked[1])
        return self.picked

    def _rumor_strip_card(self, rumor: sq.Rumor, all_problems: list) -> Card:
        """(1.15.0) A rumor's card in the strip: its name, the taverns telling it, what the helper would say of it."""
        problem = next((p for p in all_problems if self._of_rumor(p, rumor.name)), "")
        return Card("other", rumor.name, self._towns_words(rumor), problem=problem, band=RUMOR_BAND,
                    colour=RUMOR_COLOUR)

    @staticmethod
    def _of_rumor(problem: str, name: str) -> bool:
        """Whether something Mod Studio Framework would say is about the rumor `name` (its words: "the rumor
        <name>'s Title is ...", "the rumor <name> has more than ...")."""
        return problem.startswith(f"the rumor {name}'s ") or problem.startswith(f"the rumor {name} ")

    @staticmethod
    def _towns_words(rumor: sq.Rumor) -> str:
        if not rumor.towns:
            return RUMOR_EVERY_TAVERN
        if len(rumor.towns) == 1:
            return RUMOR_ONE_TAVERN.format(town=place_name(rumor.towns[0]))
        return RUMOR_TAVERNS.format(n=len(rumor.towns))

    def _start_line(self, quest: sq.Quest, step: qx.Step) -> str:
        start = quest.starts[step.start]
        rumor = next((r for r in quest.rumors if qx.waits_for_rumor(start, r)), None)
        if rumor is not None:
            # (1.15.0) The rumor it waits for, which the player acts on (the rumor itself waits for the story).
            return AFTER_RUMOR_LINE.format(rumor=rumor.name)
        past = qx.story_past(start)
        if past is not None:
            self.story_points()
            place, event = self._story_places.get(past, (None, None))
            if event is None:
                return STORY_AT_LEAST.format(value=past)
            return STORY_LINE.format(place=place or STORY_EVENT.format(event=event).lower())
        after = [cond.flag for cond in start.when if cond.kind == "Flag" and cond.value == 1]
        return AFTER_A_STEP if after else ANY_TIME_LINE

    def _event_card(self, quest: sq.Quest, name: str, all_problems: list) -> Card:
        ev = quest.event_named(name)
        what = qx.role(quest, name)
        problem = next((p for p in all_problems if f" {name}" in p or f"{name}'s" in p), "")
        if what == "battle":
            enemies = 0
            try:
                block = next(self.edits().files[b.units] for b in quest.battles if b.name == ev.battle.units)
                enemies = sum(1 for u in entd.battle_units(block) if u.occupied and u.values["team"] == 1)
            except (StopIteration, KeyError, ValueError):
                pass
            return Card("other", name, f"On {self._map_words(ev.setup.get('Map'))}, {enemies} enemies",
                        problem=problem, band=BATTLE_BAND, colour=BATTLE_COLOUR)
        fight = quest.fight_of(name)
        during = next((d for d in fight.battle.during if d.event == name), None) if fight is not None else None
        detail = AS_IT_STARTS if what == "start" else ONCE_WON if what == "won" else ONCE_LOST if what == "lost" else (
            self._during_words(self.edits(), fight, during) if during is not None else
            f"On {self._map_words(ev.setup.get('Map'))}" if ev.setup.get("Map") is not None else "")
        return Card("other", name, detail, problem=problem, band=SCENE_BAND, colour=SCENE_COLOUR)

    def _map_words(self, value) -> str:
        if isinstance(value, str):
            return value
        if value is None:
            return "no map yet"
        return _label(me_page.map_names(self.state).get(value) or f"map {value:03d}")

    def _card_picked(self, index: int) -> None:
        if 0 <= index < len(self.strip_keys):
            self.pick(self.strip_keys[index])

    def pick(self, key: tuple) -> None:
        """Picks something of the quest: the quest, a start, an event, a step's end or a unit."""
        self.picked = key
        chosen = self.strip_keys.index(self._strip_key()) if self._strip_key() in self.strip_keys else -1
        self.strip.set_chosen(chosen)
        self._show_card()
        self._show_middle()

    def _changed(self, refill: bool = True) -> None:
        """After a change: the list's line, the strip; Export's summary."""
        if refill:
            self._fill_list()
            self._fill_strip()
        self.edits_changed.emit()

    def quests_changed_elsewhere(self) -> None:
        """(C) A quest's scene changed on the Event Editor: the list, the steps' row and the card shown again, as
        it now is (nothing said back to the Event Editor, whose change it was)."""
        if self.in_places() or self.in_items():
            return
        self._fill_list()
        self._fill_strip()
        self._show_card()

    # -- the middle ---------------------------------------------------------------------------------

    def _show_middle(self) -> None:
        edits = self.edits()
        kind = self.picked[0] if self.picked else "quest"
        if self.in_items():
            self.middle.setCurrentIndex(0)
            self._show_items_world()
            return
        if self.in_places():
            place, battle = self._picked_battle()
            if battle is not None:
                self._show_place_battle_map(place, battle)
                return
            self.middle.setCurrentIndex(0)
            self._show_places_world()
            return
        if edits is not None and kind in ("event", "unit"):
            name = self.picked[1]
            ev = edits.quest.event_named(name)
            if ev is not None:
                battle = ev if ev.battle is not None else edits.quest.fight_of(name)
                if battle is not None or ev.setup.get("Map") is not None:
                    self._show_battle_map(ev if battle is None else battle, scene=battle is None)
                    return
        self.middle.setCurrentIndex(0)
        self._show_world(kind)

    def _show_world(self, kind: str) -> None:
        edits = self.edits()
        self._want_world()
        self._show_mod_world()
        self.world.edit_place = self.world.edit_road = None
        self.world.places = self.place_where()
        self.world.outlined = set()
        markers = []
        if edits is not None:
            colour = QColor(edits.quest.marker or "#4080E0")
            if colour != self.world.marker_colour or self.world.marker_image is None:
                self.world.marker_colour = colour
                self.world.marker_image = tinted_marker(colour)
            picked_start = self.picked[1] if self.picked and self.picked[0] in ("start", "done") else None
            rumor = (qx.rumor_named(edits.quest, self.picked[1]) if self.picked and self.picked[0] == "rumor"
                     else None)
            for n, step in enumerate(qx.steps(edits.quest)):
                place = edits.quest.starts[step.start].place
                markers.append((place, STEP.format(n=n + 1), step.start == picked_start))
            if rumor is not None:
                # (1.15.0) A rumor: its towns outlined, each click a town's tavern telling it or no longer.
                self.world.picked = None
                self.world.outlined = set(qx.told_in(rumor, pe.menu_towns(self.places_store())))
                self.world_title.setText(WORLD_TITLE["rumor"].format(rumor=rumor.name))
                self.world_hint.setText(WORLD_HINT["rumor"])
            elif picked_start is not None and picked_start < len(edits.quest.starts):
                place = edits.quest.starts[picked_start].place
                n = next(i for i, s in enumerate(qx.steps(edits.quest)) if s.start == picked_start)
                self.world.picked = place
                x, y, _town = self.world.places.get(place, (1300, 930, True))
                self.world.show_place(x, y)
                self.world_title.setText(WORLD_TITLE["start"].format(
                    n=n + 1, place=start_place(edits.quest.starts[picked_start])))
                self.world_hint.setText(WORLD_HINT["start"].format(n=n + 1))
            else:
                self.world.picked = None
                self.world_title.setText(WORLD_TITLE["quest"].format(quest=edits.quest.name))
                self.world_hint.setText(WORLD_HINT["quest"])
        else:
            self.world.picked = None
            self.world_title.setText("")
            self.world_hint.setText(PICK_A_QUEST)
        self.world.markers = markers if (edits is None or edits.quest.marker) else []
        self.world.update()

    def _want_world(self) -> None:
        """The world map drawn for the unpacked game, once the page is shown: decoding its textures takes a while,
        and nobody waits for a page not open. The mod's places and roads are drawn over it by the view, as they
        change (`_show_mod_world`)."""
        if not self.isVisible():
            return
        game = self.game_dir()
        key = (str(game), tuple(sorted((str(k), str((v or {}).get("source_path"))) for k, v in
                                       (getattr(self.state, "texture_edits", None) or {}).items()
                                       if "worldmap" in str(k).lower())))
        if key == self._world_key:
            return
        if self._world_job is not None:
            self._world_again = True
            return
        self._world_key = key
        self._world_again = False
        if game is None:
            self.world.set_image(None, NO_GAME)
            return
        cli = getattr(self.state, "ff16tools_cli_path", None)
        cache = paths.local_data_dir() / "texture_preview_cache"
        decode = self.decode or lp.default_decoder(cli, cache)
        replacement = self.decode_replacement or self.decode or lp.default_replacement_decoder(cli, cache)
        self.world.set_image(None, DRAWING_WORLD)
        worker = WorldWorker(game, getattr(self.state, "texture_edits", {}), decode, replacement)
        self._world_job = worker
        self._world_thread = run_in_thread(worker, on_finished=self._world_ready, on_failed=self._world_failed)

    def redraw_world(self) -> None:
        """The world map drawn again (its textures replaced, another decoder given)."""
        self._world_key = None
        self._want_world()

    def _world_ready(self, result) -> None:
        self._world_job = None
        image, said = result[0], result[1]
        self.world.set_pieces(result[2] if len(result) > 2 else {})
        self.world.set_image(image, said)
        if self.in_places():
            # A town's card shows the game's town texture it uses, which the world map's drawing brought.
            self._show_card()
        if getattr(self, "_world_again", False):
            self._want_world()

    def _world_failed(self, message: str) -> None:
        self._world_job = None
        self.world.set_image(None, NO_WORLD.format(problem=message))

    def _place_clicked(self, place) -> None:
        if self.in_items():
            # (1.26.0) The Items tab's map only shows where the item is sold.
            return
        if self.in_places():
            found = pe.place_named(self.places_store(), place) if isinstance(place, str) else None
            if found is not None:
                self.pick_place(("place", found.folder))
            return
        edits = self.edits()
        if edits is None:
            return
        if self.picked and self.picked[0] == "start":
            qx.set_start_place(edits.quest.starts[self.picked[1]], place)
            self._changed()
            self._show_card()
            self._show_middle()
            return
        if self.picked and self.picked[0] == "rumor":
            self.toggle_rumor_town(self.picked[1], place)
            return
        for step in qx.steps(edits.quest):
            if edits.quest.starts[step.start].place == place:
                self.pick(("start", step.start))
                return

    def _battle_key(self, name: str) -> int:
        """The Encounters map's key for one of the quest's battles: past every battle of the game's."""
        edits = self.edits()
        names = [e.name for e in edits.quest.events] if edits is not None else []
        return 100000 + (names.index(name) if name in names else 0)

    def _show_battle_map(self, ev: sq.QuestEvent, scene: bool) -> None:
        self.middle.setCurrentIndex(1)
        self._shown_event = ev.name
        self._shown_scene = scene
        value = ev.setup.get("Map")
        state = self.state
        if isinstance(value, str):
            quest_map = (getattr(self.state, "quest_maps", None) or {}).get(value)
            number = quest_map.base if quest_map is not None else None
            if quest_map is not None:
                state = qme.EditView(self.state, quest_map)
        else:
            number = value
        self.battle_map.state = state
        key = self._battle_key(ev.name)
        if number is not None:
            self.battle_map.chosen[key] = int(number)
        else:
            self.battle_map.chosen.pop(key, None)
        if self.picked and self.picked[0] == "unit":
            self.battle_map.selected = (key, self.picked[2])
        else:
            self.battle_map.selected = None
        self.battle_map.show_battle(key)
        self.battle_map.map_label.setVisible(False)
        self.battle_map.map_box.setVisible(False)
        self.battle_map.hint.setVisible(not scene)
        self._show_deploy()
        if number is None:
            self.battle_map._no_map(NO_MAP_YET)

    def _units_block(self, name: str) -> Optional[bytes]:
        """The 640 bytes of units an event shows: a battle's own, or a scene's setup's EnemyBattle (the quest's or
        the game's)."""
        edits = self.edits()
        if edits is None:
            return None
        ev = edits.quest.event_named(name)
        if ev is None:
            return None
        if ev.battle is not None:
            units = ev.battle.units
        else:
            units = ev.setup.get("EnemyBattle") or ev.setup.get("SceneUnits")
        if isinstance(units, str):
            battle = next((b for b in edits.quest.battles if b.name == units), None)
            return edits.files.get(battle.units) if battle is not None else None
        if isinstance(units, int) and units > 0 and self.game() is not None:
            return self.game().battle(units)
        return None

    def _map_units(self, key) -> list:
        if self.in_places():
            # (1.17.0) A random battle's units.
            _place, battle = self._picked_battle()
            block = battle.units if battle is not None and battle.units else None
        else:
            edits = self.edits()
            name = getattr(self, "_shown_event", None)
            if edits is None or name is None:
                return []
            block = self._units_block(name)
        if block is None:
            return []
        out = []
        for unit in entd.battle_units(block):
            v = unit.values
            if not unit.occupied:
                continue
            sprite = enc.unit_sprites.sprite_number(v["sprite_set"], v["main_job"], 0)
            out.append(MapUnit(address=(key, unit.slot), editable=self._units_editable(), x=v["x"], y=v["y"],
                               upper=v["upper_level"], facing=v["facing"], sprite=sprite,
                               palette=drawn_palette(sprite, v["sprite_set"], v["palette"]), team=v["team"],
                               randomly_present=v["randomly_present"], disabled=False,
                               label=self._unit_words(v)))
        return out

    def _map_title(self, key) -> str:
        if self.in_places():
            place, battle = self._picked_battle()
            return RANDOM_BATTLE_TITLE.format(battle=battle.name, place=place.name,
                                              map=self._map_words(battle.map)) if battle is not None else ""
        edits = self.edits()
        name = getattr(self, "_shown_event", None)
        ev = edits.quest.event_named(name) if edits is not None and name else None
        if ev is None:
            return ""
        fight = ev if ev.battle is not None else edits.quest.fight_of(name)
        shown = fight if fight is not None else ev
        template = BATTLE_TITLE if fight is not None else SCENE_TITLE
        return template.format(battle=shown.name, scene=shown.name, map=self._map_words(shown.setup.get("Map")))

    def _units_editable(self) -> bool:
        """Whether the units shown on the map are the quest's own to change: a battle's, or (4 November) a scene's own
        (`own_units`)."""
        if not self._shown_scene:
            return True
        edits = self.edits()
        name = getattr(self, "_shown_event", None)
        return edits is not None and name is not None and self.own_units(edits.quest.event_named(name)) is not None

    def _unit_picked_on_map(self, address) -> None:
        if self.in_places():
            place, battle = self._picked_battle()
            if battle is not None:
                self.pick_place(("place_unit", place.folder, battle.name, address[1]))
            return
        name = getattr(self, "_shown_event", None)
        edits = self.edits()
        if edits is None or name is None or not self._units_editable():
            return
        ev = edits.quest.event_named(name)
        battle = ev if ev.battle is not None or self._shown_scene else edits.quest.fight_of(name)
        if battle is not None:
            self.pick(("unit", battle.name, address[1]))

    def _unit_moved(self, address, x: int, y: int, level: int) -> None:
        if self.in_places():
            place, battle = self._picked_battle()
            if battle is None:
                return
            pe.set_battle_unit(place, battle.name, address[1], x=x, y=y, upper_level=bool(level))
            self.place_pick = ("place_unit", place.folder, battle.name, address[1])
            self.edits_changed.emit()
            self._show_card()
            self.battle_map.refresh_units()
            return
        if not self._units_editable():
            return
        edits = self.edits()
        name = getattr(self, "_shown_event", None)
        ev = edits.quest.event_named(name) if edits is not None and name else None
        battle = ev if ev is not None and (ev.battle is not None or self._shown_scene) else (
            edits.quest.fight_of(name) if ev else None)
        units = self.own_units(battle)
        if battle is None or units is None:
            return
        qx.set_unit(edits, units, address[1], x=x, y=y, upper_level=bool(level))
        self.picked = ("unit", battle.name, address[1])
        self._changed(refill=False)
        self._show_card()
        self.battle_map.refresh_units()

    def _unit_words(self, v: dict) -> str:
        """A unit in a line: its name when it has one of its own (or its job's), its level, its team."""
        names = self._choices("Unknown4")
        name = names.get(v["unit_name"]) if v["unit_name"] not in c.ENTRY_SPECIAL_VALUES["Unknown4"] else None
        if not name or name == "(unnamed)":
            name = self._choices("MainJob").get(v["main_job"]) or f"Job {v['main_job']}"
        return UNIT_LINE.format(who=name, level=self._level_words(v["level"]),
                                team=TEAM_NAMES.get(v["team"], "").lower())

    def _choices(self, column: str) -> dict:
        """`{value: name}` of one of a unit's fields (`encounters.base_choices_for`), read once a card."""
        cache = self.__dict__.setdefault("_choice_cache", {})
        if column not in cache:
            cache[column] = enc.base_choices_for(self.state, column)
        return cache[column]

    @staticmethod
    def _level_words(level: int) -> str:
        """A unit's level in its line: "level 4", "party level + 3", "random level"."""
        if level == entd.RANDOM_BYTE:
            return RANDOM_LEVEL
        if level >= c.ENTRY_LEVEL_PARTY and level in c.entry_level_choices():
            return c.entry_level_choices()[level].lower()
        return LEVEL.format(level=level)

    # =========================================================================
    # The cards
    # =========================================================================

    def _card_shown(self) -> tuple:
        """What the card shows: its tab and what is picked there (the item, the place or road, or the quest and its
        step, scene, battle, unit or rumor)."""
        if self.in_items():
            return ("items", self.item_pick)
        if self.in_places():
            return ("places", self.place_pick)
        edits = self.edits()
        return ("quests", edits.folder if edits is not None else None, self.picked)

    def _show_card(self) -> None:
        self._building = True
        self._choice_cache = {}
        self.field_widgets = {}
        try:
            old = self.card
            # (Zodi, 5 November) A card made again for what it showed (a drop down's choice, any change that makes it
            # anew) keeps its place, not scrolled back to its top; another thing picked opens at its top.
            shown = self._card_shown()
            place = (old.scroll.verticalScrollBar().value() if old is not None and isinstance(old, CardPane)
                     and getattr(self, "_card_was", None) == shown else 0)
            self._card_was = shown
            edits = self.edits()
            if self.in_items():
                card = self._item_card()
            elif self.in_places():
                card = self._places_card()
            elif edits is None:
                card = CardPane("QUEST", "", QUEST_COLOUR, "", PICK_A_QUEST if self.quests() else "")
                card.status([], "")
            else:
                kind = self.picked[0] if self.picked else "quest"
                if kind == "start" and self.picked[1] < len(edits.quest.starts):
                    card = self._start_card(edits, self.picked[1])
                elif kind == "done" and self.picked[1] < len(edits.quest.starts):
                    card = self._done_card(edits, self.picked[1])
                elif kind == "event" and edits.quest.event_named(self.picked[1]) is not None:
                    ev = edits.quest.event_named(self.picked[1])
                    card = self._battle_card(edits, ev) if ev.battle is not None else self._scene_card(edits, ev)
                elif kind == "unit" and edits.quest.event_named(self.picked[1]) is not None:
                    card = self._unit_card(edits, edits.quest.event_named(self.picked[1]), self.picked[2])
                elif kind == "rumor" and qx.rumor_named(edits.quest, self.picked[1]) is not None:
                    card = self._rumor_card(edits, qx.rumor_named(edits.quest, self.picked[1]))
                else:
                    self.picked = ("quest",)
                    card = self._quest_card(edits)
            self.card = card
            self.card_holder.addWidget(card)
            self.card_holder.setCurrentWidget(card)
            if old is not None:
                self.card_holder.removeWidget(old)
                old.deleteLater()
            if place and isinstance(card, CardPane):
                card.keep_place(place)
        finally:
            self._building = False

    def _step_number(self, edits: qx.QuestEdits, start: int) -> int:
        return next((n + 1 for n, s in enumerate(qx.steps(edits.quest)) if s.start == start), 0)

    # -- the quest ----------------------------------------------------------------------------------

    def _quest_card(self, edits: qx.QuestEdits) -> CardPane:
        quest = edits.quest
        steps = qx.steps(quest)
        card = CardPane("QUEST", f"{len(steps)} step{'s' if len(steps) != 1 else ''}", QUEST_COLOUR, quest.name,
                        QUEST_BLURB)
        name = QLineEdit(edits.folder)
        name.setMaxLength(64)
        name.setToolTip(NAME_TIP)
        name.editingFinished.connect(lambda box=name: self.rename_quest(box.text()))
        self.field_widgets["quest_name"] = name
        card.field(NAME, name)
        shown = QCheckBox(SHOW_MARKER)
        shown.setChecked(bool(quest.marker))
        shown.toggled.connect(self._marker_shown)
        swatch = QPushButton("")
        swatch.setFixedSize(46, 24)
        colour = quest.marker or "#4080E0"
        swatch.setStyleSheet(f"background: {colour}; border: 1px solid #00000080; border-radius: 4px;")
        swatch.setEnabled(bool(quest.marker))
        choose = QPushButton(CHOOSE_COLOUR)
        choose.setEnabled(bool(quest.marker))
        choose.clicked.connect(self.choose_marker)
        swatch.clicked.connect(self.choose_marker)
        shown.setToolTip(MARKER_NOTE)
        self.field_widgets.update(marker_shown=shown, marker_swatch=swatch, marker_choose=choose)
        card.field(MARKER, shown, row(swatch, choose, stretch_first=False))
        flags = QWidget()
        lines = QVBoxLayout(flags)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(3)
        for flag in quest.flags:
            box = QLineEdit(flag)
            box.setMaxLength(64)
            box.editingFinished.connect(lambda b=box, old=flag: self.rename_flag(old, b.text()))
            self.field_widgets[f"flag_{flag}"] = box
            lines.addWidget(box)
            setters = [e.name for e in quest.events if any(f == flag for _, f in e.flags_in_script)]
            readers = [r.name for r in quest.rumors if r.read == flag]
            said = (FLAG_SET_BY.format(event=", ".join(setters)) if setters
                    else FLAG_SET_BY_RUMOR.format(rumor=readers[0]) if readers else FLAG_NOT_SET)
            waiting = [n + 1 for n, s in enumerate(steps)
                       if any(cond.kind == "Flag" and cond.flag == flag and cond.value == 1
                              for cond in quest.starts[s.start].when)]
            if waiting:
                said += " " + " ".join(FLAG_WAITED.format(n=n) for n in waiting)
            lines.addWidget(muted(said))
        add = QPushButton(ADD_FLAG)
        add.setToolTip(FLAGS_NOTE)
        add.clicked.connect(self.add_flag)
        self.field_widgets["add_flag"] = add
        card.field(FLAGS, flags, row(add, stretch_first=False))
        card.fields.addWidget(muted(NAMES_KEPT))
        card.status(self.problems(edits), READY)
        return card

    def rename_quest(self, name: str) -> None:
        edits = self.edits()
        if edits is None or self._building or name == edits.folder:
            return
        taken = {f.lower() for f in self.quests() if f != edits.folder}
        if not sq.good_name(name) or name.lower() in taken:
            self._say(NAME_BAD if not sq.good_name(name) else QUEST_TAKEN.format(name=name))
            self._show_card()
            return
        quests = self.quests()
        renamed = {}
        # (1.20.0) The towns darkened by its flags name it so.
        pe.follow_quest(self.places_store(), edits.folder, name)
        for folder, other in quests.items():
            if folder == edits.folder:
                other.folder = name
                other.quest.name = name
                renamed[name] = other
            else:
                renamed[folder] = other
        self.state.quests = renamed
        self.folder = name
        self._changed()
        self._show_card()

    def _marker_shown(self, on: bool) -> None:
        edits = self.edits()
        if edits is None or self._building:
            return
        edits.quest.marker = (edits.quest.marker or "#4080E0") if on else ""
        self._changed()
        self._show_card()
        self._show_middle()

    def choose_marker(self) -> None:
        edits = self.edits()
        if edits is None:
            return
        colour = self._ask("colour", lambda: QColorDialog.getColor(QColor(edits.quest.marker or "#4080E0"), self))
        if colour is None or not colour.isValid():
            return
        edits.quest.marker = colour.name().upper()
        self._changed()
        self._show_card()
        self._show_middle()

    def add_flag(self) -> None:
        edits = self.edits()
        if edits is None:
            return
        qx.add_flag(edits, "flag")
        self._changed()
        self._show_card()

    def rename_flag(self, old: str, new: str) -> None:
        edits = self.edits()
        if edits is None or self._building or new == old:
            return
        before = list(edits.quest.flags)
        try:
            qx.rename_flag(edits, old, new)
        except ValueError:
            self._say(NAME_BAD)
            self._show_card()
            return
        # (1.20.0) The towns darkened by it name it so.
        pe.follow_flags(self.places_store(), edits.folder, before, edits.quest.flags)
        self._changed()
        self._show_card()

    # -- a start -------------------------------------------------------------------------------------

    def _start_card(self, edits: qx.QuestEdits, index: int) -> CardPane:
        quest = edits.quest
        start = quest.starts[index]
        n = self._step_number(edits, index)
        card = CardPane(WAITS_AT, STEP.format(n=n), START_COLOUR, start_place(start),
                        START_BLURB.format(n=n))
        places = combo(self.step_places(), start_key(start))
        places.currentIndexChanged.connect(lambda _i, b=places: self._set_place(index, b.currentData()))
        self.field_widgets["place"] = places
        # (1.25.0) A step waiting at a floor of one of the mod's dungeons: what it does there, in its tooltip (4
        # November) as how a place is picked is.
        places.setToolTip(PLACE_NOTE + ("\n\n" + STEP_FLOOR_NOTE if start.floor else ""))
        card.field(PLACE, places)
        story = combo([(None, ANY_TIME)] + self.story_points(), qx.story_past(start))
        story.currentIndexChanged.connect(lambda _i, b=story: self._set_story(index, b.currentData()))
        self.field_widgets["story"] = story
        steps = qx.steps(quest)
        step = next(s for s in steps if s.start == index)
        conditions = [caption(STORY_PAST), story]
        # The conditions a tick stands for: this step's own flag 0 (once only), another step's flag 1 (after it).
        ticked = set()
        own = step.once or (step.sets[-1] if step.sets else "")
        if own:
            once = QCheckBox(ONCE_ONLY.format(n=n))
            once.setChecked(qx.flag_condition(start, own) == 0)
            once.toggled.connect(lambda on, f=own: self._set_flag_condition(index, f, 0 if on else None))
            self.field_widgets["once"] = once
            conditions.append(once)
            ticked.add((own, 0))
        for m, other in enumerate(steps):
            flag = other.once or (other.sets[-1] if other.sets else "")
            if other.start == index or not flag or flag == own or any(f == flag for f, _ in ticked):
                continue
            after = QCheckBox(AFTER_STEP.format(n=m + 1))
            after.setChecked(qx.flag_condition(start, flag) == 1)
            after.toggled.connect(lambda on, f=flag: self._set_flag_condition(index, f, 1 if on else None))
            self.field_widgets[f"after_{m + 1}"] = after
            conditions.append(after)
            ticked.add((flag, 1))
        for rumor in quest.rumors:
            # (1.15.0) Waiting until one of the quest's rumors is read (its flag set).
            if any(f == rumor.read for f, _ in ticked):
                continue
            after = QCheckBox(AFTER_RUMOR.format(rumor=rumor.name))
            after.setChecked(qx.waits_for_rumor(start, rumor))
            after.toggled.connect(lambda on, r=rumor.name: self._set_waits_for_rumor(index, r, on))
            self.field_widgets[f"rumor_{rumor.name}"] = after
            conditions.append(after)
            ticked.add((rumor.read, 1))
        card.field(WHEN, *conditions)
        others = [cond for cond in start.when
                  if not (cond.kind == "Variable" and cond.variable == qx.STORY and cond.test == "AtLeast")
                  and not (cond.kind == "Flag" and (cond.flag, cond.value) in ticked)]
        rows_ = [self._condition_row(index, number, cond) for number, cond in enumerate(others)]
        kinds = combo([(None, ADD_CONDITION)] + [(k, k) for k in CONDITION_KINDS])
        kinds.currentIndexChanged.connect(lambda _i, b=kinds: self._add_condition(index, b.currentData()))
        kinds.setEnabled(len(start.when) < sq.MOST_CONDITIONS)
        kinds.setToolTip(CONDITIONS_NOTE.format(most=sq.MOST_CONDITIONS))
        self.field_widgets["add_condition"] = kinds
        card.field(OTHER_CONDITIONS, *rows_, kinds)
        if not start.floor:
            # A travel never passes through a floor: a step there plays as the floor is chosen.
            waits, stops = QRadioButton(WAITS), QRadioButton(STOPS)
            group = QButtonGroup(card)
            group.addButton(waits)
            group.addButton(stops)
            (stops if start.stops_passing else waits).setChecked(True)
            stops.toggled.connect(lambda on: self._set_passing(index, on))
            waits.setToolTip(PASSING_NOTE)
            stops.setToolTip(PASSING_NOTE)
            self.field_widgets.update(waits=waits, stops=stops)
            card.field(PASSING, waits, stops)
        if quest.marker:
            card.fields.addWidget(muted(MARKER_HERE))
        said = self._problems_of(edits, "start")
        unplayed = pe.floor_start_problem(self.places_store(), start)
        if not said and unplayed:
            self._warn(card, [unplayed])
        else:
            card.status(said)
        card.add_buttons(REMOVE_STEP)
        card.buttons[REMOVE_STEP].clicked.connect(lambda: self.remove_step(index))
        return card

    def _condition_row(self, key, number: int, cond: sq.Condition) -> QWidget:
        """One of a start's (or (1.15.0) a rumor's) other conditions, each part of it changed in place: someone in
        the party, a flag of the quest set or not, one of the game's variables tested against a number."""
        take = QPushButton(TAKE_OUT)
        take.clicked.connect(lambda _c=False, cd=cond: self._take_condition(key, cd))
        self.field_widgets[f"condition_{number}_take"] = take
        if cond.kind == "Character":
            names = reference_names.sprite_set_names()
            who = combo([(k, names.get(k) or f"Character {k}") for k in range(1, 256)], cond.value)
            who.currentIndexChanged.connect(lambda _i, b=who, cd=cond: self._set_condition(cd, value=b.currentData()))
            self.field_widgets[f"condition_{number}_character"] = who
            return row(who, QLabel(IN_PARTY), take)
        if cond.kind == "Flag":
            flags = combo([(f, f) for f in self.edits().quest.flags], cond.flag)
            flags.currentIndexChanged.connect(lambda _i, b=flags, cd=cond: self._set_condition(cd, flag=b.currentData()))
            value = combo(list(FLAG_IS.items()), cond.value)
            value.currentIndexChanged.connect(lambda _i, b=value, cd=cond: self._set_condition(cd, value=b.currentData()))
            self.field_widgets.update({f"condition_{number}_flag": flags, f"condition_{number}_is": value})
            return row(flags, value, take)
        variable = spin(cond.variable, 1, 1023)
        variable.valueChanged.connect(lambda v, cd=cond: self._set_condition(cd, variable=v))
        test = combo(list(TESTS_WORDS.items()), cond.test)
        test.currentIndexChanged.connect(lambda _i, b=test, cd=cond: self._set_condition(cd, test=b.currentData()))
        value = spin(cond.value, 0, 0xFFFF)
        value.valueChanged.connect(lambda v, cd=cond: self._set_condition(cd, value=v))
        self.field_widgets.update({f"condition_{number}_variable": variable, f"condition_{number}_test": test,
                                   f"condition_{number}_value": value})
        holder = QWidget()
        lines = QVBoxLayout(holder)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(3)
        lines.addWidget(row(QLabel(VARIABLE), variable, stretch_first=False))
        lines.addWidget(row(test, value, take))
        return holder

    def _set_condition(self, cond: sq.Condition, **changes) -> None:
        if self._building:
            return
        for name, value in changes.items():
            if value is not None:
                setattr(cond, name, value)
        self._changed()

    def _problems_of(self, edits: qx.QuestEdits, what: str) -> list:
        said = self.problems(edits)
        if what == "start":
            return [p for p in said if p.startswith("a start")]
        return [p for p in said if f" {what}" in p or f"{what}'s" in p]

    def _set_place(self, index: int, place) -> None:
        if self._building or place is None:
            return
        floor = ""
        if isinstance(place, str) and FLOOR_KEY in place:
            # (1.25.0) A floor of one of the mod's dungeons.
            place, floor = place.split(FLOOR_KEY, 1)
        qx.set_start_place(self.edits().quest.starts[index], place, floor)
        self._changed()
        self._show_card()
        self._show_middle()

    def _holder(self, key):
        """What a condition is of: a start (`key` its place among the quest's starts) or (1.15.0) a rumor (`key` its
        name), each with its When."""
        quest = self.edits().quest
        return qx.rumor_named(quest, key) if isinstance(key, str) else quest.starts[key]

    def _set_story(self, key, value) -> None:
        if self._building:
            return
        qx.set_story_past(self._holder(key), value)
        self._changed()

    def _set_flag_condition(self, key, flag: str, value) -> None:
        if self._building:
            return
        qx.set_flag_condition(self._holder(key), flag, value)
        self._changed()

    def _take_condition(self, key, condition: sq.Condition) -> None:
        start = self._holder(key)
        start.when = [cond for cond in start.when if cond is not condition]
        self._changed()
        self._show_card()

    def _add_condition(self, key, kind) -> None:
        if self._building or kind is None:
            return
        start = self._holder(key)
        if kind == CONDITION_KINDS[0]:
            start.when.append(sq.Condition("Character", 0, "", "Is", 1))
        elif kind == CONDITION_KINDS[1]:
            flags = self.edits().quest.flags
            tested = {cond.flag for cond in start.when if cond.kind == "Flag"}
            free = [f for f in flags if f not in tested]
            if not free:
                self._say(NO_FLAGS_YET if not flags else ALL_FLAGS_TESTED)
                self._show_card()
                return
            start.when.append(sq.Condition("Flag", 0, free[0], "Is", 1))
        else:
            start.when.append(sq.Condition("Variable", 1, "", "AtLeast", 0))
        self._changed()
        self._show_card()

    def _set_passing(self, index: int, stops: bool) -> None:
        if self._building:
            return
        self.edits().quest.starts[index].stops_passing = bool(stops)
        self._changed()

    def remove_step(self, index: int) -> None:
        edits = self.edits()
        lengths = self.lengths()
        if edits is None or lengths is None:
            return
        qx.remove_step(edits, index, lengths)
        self.picked = ("quest",)
        self._changed()
        self.show_quest()

    def _set_waits_for_rumor(self, index: int, rumor: str, on: bool) -> None:
        """(1.15.0) A step waiting until one of the quest's rumors is read, or no longer."""
        edits = self.edits()
        if self._building or edits is None:
            return
        found = qx.rumor_named(edits.quest, rumor)
        if found is None or not 0 <= index < len(edits.quest.starts):
            return
        qx.set_waits_for_rumor(edits.quest.starts[index], found, bool(on))
        self._changed()

    # -- (1.15.0) a tavern rumor ----------------------------------------------------------------------

    def _rumor_card(self, edits: qx.QuestEdits, rumor: sq.Rumor) -> CardPane:
        """A rumor's card: its name, title and words, the towns whose taverns tell it (ticked here or clicked on the
        map), when it is told (as a step's conditions), and the steps waiting until it is read."""
        quest = edits.quest
        name = rumor.name
        card = CardPane(RUMOR_BAND, self._towns_words(rumor), RUMOR_COLOUR, name, RUMOR_BLURB)
        box = QLineEdit(name)
        box.setMaxLength(64)
        box.setToolTip(NAME_TIP)
        box.editingFinished.connect(lambda b=box: self.rename_rumor(name, b.text()))
        self.field_widgets["rumor_name"] = box
        card.field(NAME, box)
        title = QLineEdit(rumor.title)
        title.setMaxLength(sq.MOST_RUMOR_TITLE)
        title.setToolTip(RUMOR_TITLE_TIP)
        title.textChanged.connect(lambda text: self._set_rumor_words(name, title=text))
        self.field_widgets["rumor_title"] = title
        card.field(RUMOR_TITLE_FIELD, title)
        text = QPlainTextEdit(rumor.text)
        text.setTabChangesFocus(True)
        text.setMinimumHeight(120)
        text.textChanged.connect(lambda b=text: self._set_rumor_words(name, text=b.toPlainText()))
        text.setToolTip(RUMOR_TEXT_NOTE)
        self.field_widgets["rumor_text"] = text
        card.field(RUMOR_TEXT_FIELD, text)
        towns = QWidget()
        grid = QGridLayout(towns)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(2)
        mine = pe.menu_towns(self.places_store())
        told = qx.told_in(rumor, mine)
        for town in range(sq.TOWNS):
            tick = QCheckBox(place_name(town))
            tick.setChecked(town in told)
            tick.toggled.connect(lambda _on, t=town: self.toggle_rumor_town(name, t))
            self.field_widgets[f"town_{town}"] = tick
            grid.addWidget(tick, town // 2, town % 2)
        # (1.18.0) The mod's own towns with a menu of their own.
        own = []
        if mine:
            own.append(caption(RUMOR_MOD_TOWNS))
            for town in mine:
                tick = QCheckBox(town)
                tick.setChecked(town in told)
                tick.toggled.connect(lambda _on, t=town: self.toggle_rumor_town(name, t))
                self.field_widgets[f"town_{town}"] = tick
                own.append(tick)
        untold = [RUMOR_NO_MENU.format(rumor=name, town=t) for t in rumor.towns if isinstance(t, str) and t not in mine]
        towns.setToolTip(RUMOR_TOWNS_NOTE)
        card.field(RUMOR_TOWNS_FIELD, towns, *own)
        story = combo([(None, ANY_TIME)] + self.story_points(), qx.story_past(rumor))
        story.currentIndexChanged.connect(lambda _i, b=story: self._set_story(name, b.currentData()))
        self.field_widgets["story"] = story
        conditions = [caption(STORY_PAST), story]
        # The conditions a tick stands for: a step's own flag 1 (after it is done).
        ticked = set()
        steps = qx.steps(quest)
        for m, other in enumerate(steps):
            flag = other.once or (other.sets[-1] if other.sets else "")
            if not flag or any(f == flag for f, _ in ticked):
                continue
            after = QCheckBox(AFTER_STEP.format(n=m + 1))
            after.setChecked(qx.flag_condition(rumor, flag) == 1)
            after.toggled.connect(lambda on, f=flag: self._set_flag_condition(name, f, 1 if on else None))
            self.field_widgets[f"after_{m + 1}"] = after
            conditions.append(after)
            ticked.add((flag, 1))
        story.setToolTip(RUMOR_WHEN_NOTE)
        card.field(WHEN, *conditions)
        others = [cond for cond in rumor.when
                  if not (cond.kind == "Variable" and cond.variable == qx.STORY and cond.test == "AtLeast")
                  and not (cond.kind == "Flag" and (cond.flag, cond.value) in ticked)]
        rows_ = [self._condition_row(name, number, cond) for number, cond in enumerate(others)]
        kinds = combo([(None, ADD_CONDITION)] + [(k, k) for k in CONDITION_KINDS])
        kinds.currentIndexChanged.connect(lambda _i, b=kinds: self._add_condition(name, b.currentData()))
        kinds.setEnabled(len(rumor.when) < sq.MOST_CONDITIONS)
        kinds.setToolTip(CONDITIONS_NOTE.format(most=sq.MOST_CONDITIONS))
        self.field_widgets["add_condition"] = kinds
        card.field(OTHER_CONDITIONS, *rows_, kinds)
        reads = [muted(RUMOR_SETS.format(flag=rumor.read))]
        for m, step in enumerate(steps):
            wait = QCheckBox(RUMOR_STEP_WAITS.format(n=m + 1))
            wait.setChecked(qx.waits_for_rumor(quest.starts[step.start], rumor))
            wait.toggled.connect(lambda on, i=step.start: self._set_waits_for_rumor(i, name, on))
            self.field_widgets[f"step_{m + 1}_waits"] = wait
            reads.append(wait)
        if not steps:
            reads.append(muted(RUMOR_NO_STEPS))
        card.field(RUMOR_READ_FIELD, *reads)
        problems = self._rumor_problems(edits, name)
        if problems or not untold:
            card.status(problems)
        else:
            self._warn(card, untold)
        card.add_buttons(REMOVE_RUMOR)
        card.buttons[REMOVE_RUMOR].clicked.connect(lambda: self.remove_rumor(name))
        return card

    def _rumor_problems(self, edits: qx.QuestEdits, name: str) -> list:
        return [p for p in self.problems(edits) if self._of_rumor(p, name)]

    def add_rumor(self) -> None:
        """A new rumor of the quest, its card shown to write it (`quest_edits.add_rumor`: its flag made with it)."""
        edits = self.edits()
        if edits is None:
            return
        name = qx.add_rumor(edits)
        self._changed()
        self.pick(("rumor", name))

    def rename_rumor(self, old: str, new: str) -> None:
        edits = self.edits()
        if edits is None or self._building or new == old:
            return
        before = list(edits.quest.flags)
        try:
            qx.rename_rumor(edits, old, new)
        except ValueError:
            self._say(NAME_BAD if not sq.good_name(new) else RUMOR_TAKEN.format(name=new))
            self._show_card()
            return
        # (1.20.0) Its flag renamed with it: the towns darkened by it name it so.
        pe.follow_flags(self.places_store(), edits.folder, before, edits.quest.flags)
        self.picked = ("rumor", new)
        self._changed()
        self._show_card()
        self._show_middle()

    def _set_rumor_words(self, name: str, title=None, text=None) -> None:
        """A rumor's title or words as they are typed: kept, and what Mod Studio Framework would say of them shown
        on its card and in the steps' row (the card stays as it is, its box still being typed in)."""
        edits = self.edits()
        if self._building or edits is None or qx.rumor_named(edits.quest, name) is None:
            return
        qx.set_rumor_words(edits, name, title=title, text=text)
        self._changed()
        if self.picked == ("rumor", name) and self.card is not None:
            self.card.status(self._rumor_problems(edits, name))

    def toggle_rumor_town(self, name: str, town) -> None:
        """A town's tavern telling the rumor or no longer (ticked on its card, or clicked on the map); never none."""
        edits = self.edits()
        rumor = qx.rumor_named(edits.quest, name) if edits is not None else None
        if self._building or rumor is None:
            return
        mine = pe.menu_towns(self.places_store())
        game_town = isinstance(town, int) and not isinstance(town, bool) and 0 <= town < sq.TOWNS
        if not game_town and not (isinstance(town, str) and town in mine):
            self._say(RUMOR_NOT_TOWN.format(place=place_name(town)))
        elif not qx.toggle_rumor_town(edits, name, town, mine):
            self._say(RUMOR_LAST_TOWN)
        else:
            self._say("")
            self._changed()
        # Its card's ticks and words, and the map's outlines, as the rumor now has them (the card kept, where it
        # was scrolled to).
        if self.picked == ("rumor", name) and self.card is not None:
            told = qx.told_in(rumor, mine)
            for t in list(range(sq.TOWNS)) + mine:
                tick = self.field_widgets.get(f"town_{t}")
                if tick is not None:
                    tick.blockSignals(True)
                    tick.setChecked(t in told)
                    tick.blockSignals(False)
            self.card.band.set_words(RUMOR_BAND, self._towns_words(rumor), RUMOR_COLOUR)
        self._show_middle()

    def remove_rumor(self, name: str) -> None:
        edits = self.edits()
        if edits is None:
            return
        qx.remove_rumor(edits, name, self.lengths())
        self.picked = ("quest",)
        self._changed()
        self.show_quest()

    # -- a step's end ---------------------------------------------------------------------------------

    def _done_card(self, edits: qx.QuestEdits, index: int) -> CardPane:
        quest = edits.quest
        n = self._step_number(edits, index)
        step = next(s for s in qx.steps(quest) if s.start == index)
        card = CardPane(DONE_BAND, STEP.format(n=n), DONE_COLOUR, STEP_DONE.format(n=n), DONE_BLURB.format(n=n))
        end = qx.last_scene(quest, step)
        if step.sets:
            card.fields.addWidget(QLabel(DONE_FLAGS.format(flags=", ".join(step.sets), event=end or "")))
        else:
            card.fields.addWidget(QLabel(SETS_NOTHING + "."))
        waiting = []
        for m, other in enumerate(qx.steps(quest)):
            for cond in quest.starts[other.start].when:
                if cond.kind == "Flag" and cond.value == 1 and cond.flag in step.sets:
                    waiting.append(DONE_WAITED.format(n=m + 1, flag=cond.flag))
        for line in waiting or [DONE_NOTHING]:
            card.fields.addWidget(muted(line))
        if quest.marker and step.once:
            card.fields.addWidget(muted(DONE_MARKER.format(place=place_name(quest.starts[index].place),
                                                           flag=step.once)))
        card.status([])
        return card

    # -- a battle ---------------------------------------------------------------------------------------

    def _map_choices(self) -> list:
        names = me_page.map_names(self.state)
        out = []
        for name, quest_map in (getattr(self.state, "quest_maps", None) or {}).items():
            out.append((name, MAP_QUEST.format(name=name, base=quest_map.base,
                                               place=_label(names.get(quest_map.base, "")))))
        out += [(n, me_page.map_label(n, _label(names.get(n, "")))) for n in sorted(names)]
        return out

    def _squads(self) -> list:
        """The deploy areas, as the Event Editor's setup card offers them: none, or each of the program's."""
        game = self.game()
        program = self.program()
        names = me_page.map_names(self.state)
        out = [(0, words.SETUP_NO_SQUAD)]
        if program is None or game is None:
            return out
        for number in range(su.SQUAD_MOST):
            squad = su.squad(program.squads, number)
            if squad is not None and squad.tiles:
                out.append((number, words.SETUP_SQUAD.format(number=number, place=_label(names.get(squad.map) or
                                                                                          f"map {squad.map}"),
                                                             most=squad.most)))
        return out

    def _music_choices(self) -> list:
        titles = self.music_titles()
        pieces = sorted(set(range(1, 128)) | set(titles))
        return [(0, emu.music_words(0, titles))] + [(n, emu.music_words(n, titles)) for n in pieces]

    def _music_row(self, ev: sq.QuestEvent, key: str) -> QWidget:
        """A piece of music's dropdown and its Play (Stop while it plays alone), as the Event Editor's setup."""
        box = self._setup_combo(ev, key, self._music_choices())
        play = QPushButton(STOP_MUSIC if self.music.now == (ev.setup.get(key), None) and ev.setup.get(key)
                           else PLAY_MUSIC)
        play.setEnabled(bool(ev.setup.get(key)))
        play.clicked.connect(lambda _c=False, b=box: self._play_music(b.currentData()))
        box.currentIndexChanged.connect(lambda _i, b=box, button=play: button.setEnabled(bool(b.currentData())))
        self.field_widgets[f"setup_{key}_play"] = play
        return row(box, play)

    def _play_music(self, music_id) -> None:
        """Play: the piece alone, or Stop when it is playing."""
        if not music_id:
            return
        if self.music.now == (music_id, None):
            self.music.stop()
            return
        self.music.play_piece(music_id)

    def _music_changed(self, music_id: int) -> None:
        """The piece heard changed: each Play says Stop while its own piece plays alone."""
        for key in ("Music1", "Music2"):
            play, box = self.field_widgets.get(f"setup_{key}_play"), self.field_widgets.get(f"setup_{key}")
            if play is None or box is None:
                continue
            mine = self.music.now is not None and self.music.now[1] is None and self.music.now[0] == box.currentData()
            try:
                play.setText(STOP_MUSIC if mine else PLAY_MUSIC)
            except RuntimeError:
                pass                                    # the card was built again since

    def _setup_combo(self, ev: sq.QuestEvent, key: str, choices: list, default=0) -> QComboBox:
        box = combo(choices, ev.setup.get(key, default))
        box.currentIndexChanged.connect(lambda _i, b=box, k=key, name=ev.name: self._set_setup(name, k, b.currentData()))
        self.field_widgets[f"setup_{key}"] = box
        return box

    def _setup_spin(self, ev: sq.QuestEvent, key: str, most: int) -> QSpinBox:
        box = spin(ev.setup.get(key, 0), 0, most)
        box.valueChanged.connect(lambda value, k=key, name=ev.name: self._set_setup(name, k, value))
        self.field_widgets[f"setup_{key}"] = box
        return box

    def _set_setup(self, event: str, key: str, value) -> None:
        if self._building:
            return
        ev = self.edits().quest.event_named(event)
        if value is None:
            ev.setup.pop(key, None)
        else:
            ev.setup[key] = value
        self._changed()
        if key == "Map":
            self._show_middle()
            # (4 November) The card again: a scene's doors follow its map, and Open on the Map Editor a quest map.
            self._show_card()
        elif key in qx.DEPLOYS:
            self._show_deploy()

    def _battle_card(self, edits: qx.QuestEdits, ev: sq.QuestEvent) -> CardPane:
        quest = edits.quest
        step = qx.step_of(quest, ev.name)
        n = self._step_number(edits, step.start) if step is not None else 0
        card = CardPane(BATTLE_BAND, STEP.format(n=n) if n else UNPLAYED, BATTLE_COLOUR, ev.name, BATTLE_BLURB)
        name = QLineEdit(ev.name)
        name.setMaxLength(64)
        name.setToolTip(NAME_TIP)
        name.editingFinished.connect(lambda box=name, old=ev.name: self.rename_event(old, box.text()))
        self.field_widgets["event_name"] = name
        card.field(NAME, name)
        maps = self._setup_combo(ev, "Map", self._map_choices(), None)
        new_map = QPushButton(NEW_QUEST_MAP)
        new_map.clicked.connect(lambda: self.new_quest_map(ev.name))
        open_map = QPushButton(OPEN_MAP)
        open_map.setEnabled(isinstance(ev.setup.get("Map"), str))
        open_map.clicked.connect(lambda: self.open_map(ev.name))
        self.field_widgets.update(new_quest_map=new_map, open_map=open_map)
        maps.setToolTip(MAP_NOTE)
        card.field(MAP, maps, row(new_map, open_map))
        battle_units = self._units_field(card, edits, ev, ev.battle.units)
        self._won_fields(card, ev, battle_units)
        free = [e.name for e in quest.events if e.battle is None and qx.role(quest, e.name) == "scene"
                and not any(e.name in s.events for s in qx.steps(quest))]
        choices = [("", NO_SCENE)] + ([(ev.battle.start, ev.battle.start)] if ev.battle.start else [])
        choices += [(scene, scene) for scene in free if scene != ev.battle.start]
        choices.append((NEW_SCENE_KEY, NEW_SCENE_ENTRY))
        starts = combo(choices, ev.battle.start or "")
        starts.currentIndexChanged.connect(lambda _i, b=starts: self._set_start_scene(ev.name, b.currentData()))
        won = QPushButton(ev.battle.won)
        won.setToolTip(WON_NOTE)
        won.clicked.connect(lambda: self.pick(("event", ev.battle.won)))
        self.field_widgets.update(as_it_starts=starts, once_won=won)
        card.fields.addWidget(pair((AS_IT_STARTS_FIELD, starts), (ONCE_WON_FIELD, won)))
        # (1.31.0) Its scenes during it, each a button to its card, and one more to add.
        mids = []
        for n, d in enumerate(ev.battle.during):
            button = QPushButton(f"{d.event}: {self._during_words(edits, ev, d)}")
            button.setToolTip(DURING_NOTE)
            button.clicked.connect(lambda _c=False, name=d.event: self.pick(("event", name)))
            self.field_widgets[f"during_{n}"] = button
            mids.append(button)
        add_during = QPushButton(ADD_DURING)
        add_during.setEnabled(len(ev.battle.during) < sq.MOST_DURING)
        add_during.clicked.connect(lambda: self.add_during(ev.name))
        self.field_widgets["add_during"] = add_during
        card.field(DURING_FIELD, *(mids or [muted(DURING_NONE)]), row(add_during, stretch_first=False))
        if ev.battle.lost:
            lost = QPushButton(ev.battle.lost)
            lost.setToolTip(LOST_NOTE)
            lost.clicked.connect(lambda: self.pick(("event", ev.battle.lost)))
            self.field_widgets["once_lost"] = lost
            card.fields.addWidget(pair((ONCE_LOST_FIELD, lost)))
        self._deploy_fields(card, ev)
        ramza = QCheckBox(words.SETUP_LABELS["RamzaRequired"])
        ramza.setChecked(bool(ev.setup.get("RamzaRequired")))
        ramza.toggled.connect(lambda on, event=ev.name: self._set_setup(event, "RamzaRequired", int(on)))
        self.field_widgets["setup_RamzaRequired"] = ramza
        card.fields.addWidget(ramza)
        self._setup_fields(card, ev)
        card.status(self._problems_of(edits, ev.name), plain=qx.deploy_squares_taken(edits, ev.name))
        card.add_buttons(REMOVE_BATTLE)
        card.buttons[REMOVE_BATTLE].clicked.connect(lambda: self.remove_event(ev.name))
        return card

    def _units_field(self, card: CardPane, edits: qx.QuestEdits, ev: sq.QuestEvent, units_name: str) -> list:
        """Its units' 16 places, each its number and its unit in words (or empty), a click picking it, and Add a unit:
        a battle's units, or (Zodi, 4 November: a new scene has two of its own) a scene's (`own_units`). Returns the
        units (`entd.battle_units`)."""
        units = QTreeWidget()
        units.setColumnCount(2)
        units.setHeaderHidden(True)
        units.setRootIsDecorated(False)
        units.setAlternatingRowColors(True)
        units.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        units.header().setStretchLastSection(True)
        units.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        units.setToolTip(UNITS_OWN)
        battle_units = entd.battle_units(qx.battle_block(edits, units_name))
        for unit in battle_units:
            item = QTreeWidgetItem([str(unit.slot + 1),
                                    self._unit_words(unit.values) if unit.occupied else EMPTY_SLOT])
            item.setData(0, Qt.UserRole, unit.slot)
            item.setTextAlignment(0, int(Qt.AlignRight | Qt.AlignVCenter))
            if not unit.occupied:
                item.setForeground(1, QColor(theme.current()["text_muted"]))
            units.addTopLevelItem(item)
        units.setFixedHeight(8 * 22 + 6)
        units.itemClicked.connect(lambda item, _column, b=ev.name: self.pick(("unit", b, item.data(0, Qt.UserRole))))
        add = QPushButton(ADD_UNIT)
        add.setToolTip(ADD_UNIT_TIP)
        add.setEnabled(any(not u.occupied for u in battle_units))
        add.clicked.connect(lambda: self.add_unit(ev.name))
        self.field_widgets.update(units=units, add_unit=add)
        card.field(UNITS, units, row(add, stretch_first=False))
        return battle_units

    def _deploy_fields(self, card: CardPane, ev: sq.QuestEvent) -> None:
        """(Mod Studio Framework 1.14.0) Where the player's units start: on the game's deploy areas its setup names,
        or on its own, one or two, each its squares clicked on the map, how many units start there, which way they
        face and on which level; the game's then where it starts when the helper can't give it its own."""
        fight = ev.battle
        own = bool(fight.deploy)
        which = combo([(0, GAME_DEPLOY), (1, OWN_DEPLOY)], int(own))
        which.currentIndexChanged.connect(lambda _i, b=which: self._set_own_deploy(ev.name, bool(b.currentData())))
        self.field_widgets["deploy_which"] = which
        squads = self._squads()
        game_areas = pair((words.SETUP_LABELS["DeployArea1"], self._setup_combo(ev, "DeployArea1", squads)),
                          (words.SETUP_LABELS["DeployArea2"], self._setup_combo(ev, "DeployArea2", squads)))
        if not own:
            which.setToolTip(GAME_DEPLOY_NOTE)
            card.field(WHERE_UNITS_START, which, game_areas)
            return
        which.setToolTip(OWN_DEPLOY_NOTE)
        n = self._area_shown(ev)
        area = fight.deploy[n]
        widgets = [which]
        if len(fight.deploy) > 1:
            areas = combo([(i, DEPLOY_AREA.format(n=i + 1)) for i in range(len(fight.deploy))], n)
            areas.currentIndexChanged.connect(lambda _i, b=areas: self._pick_deploy_area(ev.name, b.currentData()))
            self.field_widgets["deploy_area"] = areas
            widgets.append(pair((AREA_FIELD, areas)))
        units = spin(area.units, 1, sq.MOST_DEPLOY_UNITS)
        units.setToolTip(DEPLOY_UNITS_TIP)
        units.valueChanged.connect(lambda value: self._set_deploy(ev.name, units=value))
        facing = combo(list(enumerate(FACING_WORDS)), area.facing)
        facing.currentIndexChanged.connect(lambda _i, b=facing: self._set_deploy(ev.name, facing=b.currentData()))
        upper = QCheckBox(DEPLOY_UPPER)
        upper.setChecked(area.upper)
        upper.toggled.connect(lambda on: self._set_deploy(ev.name, upper=on))
        squares = muted(self._squares_words(area))
        self.field_widgets.update(deploy_units=units, deploy_facing=facing, deploy_upper=upper,
                                  deploy_squares=squares)
        widgets += [pair((DEPLOY_UNITS_FIELD, units), (FACING_FIELD, facing)), upper, squares]
        if len(fight.deploy) < sq.MOST_DEPLOY_AREAS:
            more = QPushButton(ADD_AREA)
            more.clicked.connect(lambda: self._add_deploy_area(ev.name))
            self.field_widgets["deploy_add"] = more
            widgets.append(row(more, stretch_first=False))
        else:
            less = QPushButton(REMOVE_AREA)
            less.clicked.connect(lambda: self._remove_deploy_area(ev.name))
            self.field_widgets["deploy_remove"] = less
            widgets.append(row(less, stretch_first=False))
        fallback = muted(DEPLOY_FALLBACK)
        fallback.setToolTip(DEPLOY_FALLBACK_TIP)
        game_areas.setToolTip(DEPLOY_FALLBACK_TIP)
        widgets += [fallback, game_areas]
        card.field(WHERE_UNITS_START, *widgets)

    @staticmethod
    def _squares_words(area: sq.DeployArea) -> str:
        count = len(area.squares)
        return (DEPLOY_NO_SQUARES if not count else DEPLOY_ONE_SQUARE if count == 1
                else DEPLOY_SQUARES.format(n=count))

    def _area_shown(self, ev: sq.QuestEvent) -> int:
        """Which of the battle's own deploy areas a tile clicked changes: the one picked, while it has it."""
        areas = ev.battle.deploy if ev.battle is not None else []
        if self._deploy_area[0] != ev.name or not 0 <= self._deploy_area[1] < len(areas):
            self._deploy_area = (ev.name, 0)
        return self._deploy_area[1]

    def _set_own_deploy(self, battle: str, on: bool) -> None:
        """The battle's units start on deploy areas of its own (first as the game's it names, or as they were when
        last its own) or on the game's."""
        if self._building:
            return
        edits = self.edits()
        fight = edits.quest.event_named(battle).battle
        key = (edits.uid, battle)
        if not on and fight.deploy:
            self._kept_deploy[key] = [sq.DeployArea(list(a.squares), a.units, a.facing, a.upper)
                                      for a in fight.deploy]
        program = self.program()
        qx.set_own_deploy(edits, battle, on, program.squads if program is not None else b"",
                          self._kept_deploy.get(key))
        self._deploy_area = (battle, 0)
        self._changed()
        self._show_card()
        self._show_deploy()

    def _pick_deploy_area(self, battle: str, area) -> None:
        if self._building or area is None:
            return
        self._deploy_area = (battle, int(area))
        self._show_card()
        self._show_deploy()

    def _set_deploy(self, battle: str, units=None, facing=None, upper=None) -> None:
        """One of the fields of the deploy area picked: how many units start there, their facing, its level."""
        if self._building:
            return
        edits = self.edits()
        ev = edits.quest.event_named(battle)
        qx.set_deploy(edits, battle, self._area_shown(ev), units=units, facing=facing, upper=upper)
        self._changed()
        self._deploy_changed(ev)

    def _add_deploy_area(self, battle: str) -> None:
        edits = self.edits()
        self._deploy_area = (battle, qx.add_deploy_area(edits, battle))
        self._changed()
        self._show_card()
        self._show_deploy()

    def _remove_deploy_area(self, battle: str) -> None:
        edits = self.edits()
        qx.remove_deploy_area(edits, battle, self._area_shown(edits.quest.event_named(battle)))
        self._deploy_area = (battle, 0)
        self._changed()
        self._show_card()
        self._show_deploy()

    def _deploy_tile(self, x: int, y: int, level: int) -> None:
        """A tile clicked on the battle's map while its card shows its own deploy areas: added to the area picked,
        or taken out of it; why not, under the steps. (1.17.0) A random battle's, while its card is shown."""
        if self.in_places():
            place, battle = self._picked_battle()
            if battle is None or self.place_pick[0] != "battle":
                return
            try:
                pe.toggle_battle_square(place, battle.name, x, y, bool(level))
            except ValueError as problem:
                self._say(str(problem))
                return
            self._say("")
            self.edits_changed.emit()
            self._place_deploy_changed(battle)
            return
        edits = self.edits()
        if edits is None or not self.picked or self.picked[0] != "event" or self._shown_scene:
            return
        ev = edits.quest.event_named(self.picked[1])
        if ev is None or ev.battle is None or not ev.battle.deploy:
            return
        try:
            qx.toggle_deploy_square(edits, ev.name, self._area_shown(ev), x, y, bool(level))
        except ValueError as problem:
            self._say(str(problem))
            return
        self._say("")
        self._changed()
        self._deploy_changed(ev)

    def _deploy_changed(self, ev: sq.QuestEvent) -> None:
        """After a square, the units or facing or level of an area changed: the card's fields that show them and its
        problems, as they now are (the card stays, keeping its place and focus), and the map."""
        area = ev.battle.deploy[self._area_shown(ev)] if ev.battle is not None and ev.battle.deploy else None
        if area is not None and self.card is not None:
            self._building = True
            try:
                for key, value in (("deploy_units", area.units), ("deploy_facing", area.facing),
                                   ("deploy_upper", area.upper)):
                    box = self.field_widgets.get(key)
                    if box is None:
                        continue
                    if isinstance(box, QCheckBox):
                        box.setChecked(bool(value))
                    elif isinstance(box, QComboBox):
                        box.setCurrentIndex(max(0, box.findData(value)))
                    else:
                        box.setValue(int(value))
                said = self.field_widgets.get("deploy_squares")
                if said is not None:
                    said.setText(self._squares_words(area))
                self.card.status(self._problems_of(self.edits(), ev.name),
                                 plain=qx.deploy_squares_taken(self.edits(), ev.name))
            finally:
                self._building = False
        self._show_deploy()

    def _show_deploy(self) -> None:
        """The deploy areas of the battle the map shows, drawn under its units: its own (the one a tile clicked
        changes the stronger, while its card is shown), else the game's its setup names; the hint and the compass for
        clicking squares. (1.17.0) A random battle's one area."""
        if self.in_places():
            _place, battle = self._picked_battle()
            marks, clicking = [], False
            if battle is not None and battle.deploy:
                area = battle.deploy[0]
                clicking = self.place_pick[0] == "battle"
                units = f"{area.units} unit" + ("s" if area.units != 1 else "")
                marks.append(DeployMark(1, list(area.squares), area.upper, area.facing, clicking, True,
                                        DEPLOY_LEGEND_OWN.format(n=1, units=units,
                                                                 facing=FACING_WORDS[area.facing].lower())))
            self.battle_map.hint.setText(DEPLOY_HINT.format(n=1) if clicking else BATTLE_MAP_HINT)
            self.battle_map.view.show_compass = clicking
            self.battle_map.set_deploy(marks)
            return
        edits = self.edits()
        name = getattr(self, "_shown_event", None)
        ev = edits.quest.event_named(name) if edits is not None and name else None
        marks = []
        clicking = False
        if ev is not None and ev.battle is not None and not self._shown_scene:
            on_card = bool(self.picked) and self.picked[0] == "event" and self.picked[1] == ev.name
            if ev.battle.deploy:
                picked = self._area_shown(ev)
                clicking = on_card
                for n, area in enumerate(ev.battle.deploy):
                    units = f"{area.units} unit" + ("s" if area.units != 1 else "")
                    marks.append(DeployMark(n + 1, list(area.squares), area.upper, area.facing,
                                            clicking and n == picked, True,
                                            DEPLOY_LEGEND_OWN.format(n=n + 1, units=units,
                                                                     facing=FACING_WORDS[area.facing].lower())))
                hint = DEPLOY_HINT.format(n=picked + 1) if clicking else None
            else:
                program = self.program()
                for n, key in enumerate(qx.DEPLOYS):
                    number = ev.setup.get(key) or 0
                    squad = su.squad(program.squads, number) if program is not None and isinstance(number, int) \
                        and number else None
                    tiles = es.squad_tiles(squad) if squad is not None else []
                    if tiles:
                        marks.append(DeployMark(n + 1, [(t[0], t[1]) for t in tiles], bool(tiles[0][2]),
                                                tiles[0][3] & 3, False, False,
                                                DEPLOY_LEGEND_GAME.format(n=n + 1, number=number)))
                hint = None
            self.battle_map.hint.setText(hint or BATTLE_MAP_HINT)
        self.battle_map.view.show_compass = clicking
        self.battle_map.set_deploy(marks)

    def _won_fields(self, card: CardPane, ev: sq.QuestEvent, battle_units: list) -> None:
        """(Mod Studio Framework 1.12.0) How the battle is won (its way, and its unit, share or tile), the unit it
        is lost without, and its objective in the quest's own words."""
        fight = ev.battle
        ways = combo([(way, WON_WAYS[way]) for way in qx.WAYS], fight.won_by)
        ways.currentIndexChanged.connect(lambda _i, b=ways: self._set_won_when(ev.name, way=b.currentData()))
        self.field_widgets["won_way"] = ways
        widgets = [ways]
        units = [(u.slot + 1, UNIT_CHOICE.format(n=u.slot + 1, unit=self._unit_words(u.values)))
                 for u in battle_units if u.occupied]
        if fight.won_by in (sq.BEATEN, sq.WORN_DOWN):
            unit = combo(units, fight.won_unit or None)
            unit.currentIndexChanged.connect(lambda _i, b=unit: self._set_won_when(ev.name, unit=b.currentData()))
            self.field_widgets["won_unit"] = unit
            if fight.won_by == sq.WORN_DOWN:
                share = spin(fight.share or qx.SHARE, 1, sq.MOST_SHARE)
                share.setSuffix(SHARE_SUFFIX)
                share.valueChanged.connect(lambda value: self._set_won_when(ev.name, share=value))
                self.field_widgets["won_share"] = share
                widgets.append(pair((WON_UNIT, unit), (SHARE_FIELD, share)))
            else:
                widgets.append(pair((WON_UNIT, unit)))
        if fight.won_by == sq.ON_TILE:
            x, y, upper = tuple(fight.tile) if len(fight.tile) == 3 else (0, 0, 0)
            tile_x, tile_y = spin(x, 0, sq.MOST_TILE), spin(y, 0, sq.MOST_TILE)
            tile_x.valueChanged.connect(lambda value: self._set_won_when(ev.name, tile_x=value))
            tile_y.valueChanged.connect(lambda value: self._set_won_when(ev.name, tile_y=value))
            level = QCheckBox(UPPER_LEVEL)
            level.setChecked(bool(upper))
            level.toggled.connect(lambda on: self._set_won_when(ev.name, upper=int(on)))
            tile_x.setToolTip(TILE_NOTE)
            tile_y.setToolTip(TILE_NOTE)
            self.field_widgets.update(tile_x=tile_x, tile_y=tile_y, tile_upper=level)
            widgets += [pair((TILE_X, tile_x), (TILE_Y, tile_y)), level]
        # (4 November) Which of the game's battles is won so, in the way's tooltip.
        ways.setToolTip(WON_NOTES[fight.won_by])
        card.field(HOW_WON, *widgets)
        protect = combo([(0, NO_ONE_PROTECTED)] + units, fight.protect)
        protect.currentIndexChanged.connect(lambda _i, b=protect: self._set_protect(ev.name, b.currentData()))
        protect.setToolTip(PROTECT_NOTE)
        self.field_widgets["protect"] = protect
        card.field(PROTECT, protect)
        objective = QLineEdit(fight.objective)
        objective.setMaxLength(sq.MOST_OBJECTIVE)
        objective.setToolTip(OBJECTIVE_TIP + " " + OBJECTIVE_NOTE)
        objective.editingFinished.connect(lambda box=objective: self._set_objective(ev.name, box.text()))
        self.field_widgets["objective"] = objective
        notes = []
        if not fight.objective and (fight.won_by != sq.ENEMIES or fight.protect):
            notes.append(muted(OBJECTIVE_WANTED))
        card.field(OBJECTIVE, objective, *notes)

    def _set_won_when(self, battle: str, way=None, unit=None, share=None, tile_x=None, tile_y=None,
                      upper=None) -> None:
        """How the battle is won, one of its fields changed: a way taken up starts with its first enemy that is
        always on the field (else its first unit), a share of 25 percent, the tile 0, 0."""
        if self._building:
            return
        edits = self.edits()
        ev = edits.quest.event_named(battle)
        fight = ev.battle
        way = way or fight.won_by
        units = [u for u in entd.battle_units(qx.battle_block(edits, fight.units)) if u.occupied]
        if unit is None:
            unit = fight.won_unit or next(
                (u.slot + 1 for u in units if u.values["team"] == 1 and u.values["always_present"]
                 and not u.values["randomly_present"]), units[0].slot + 1 if units else 1)
        tile = list(fight.tile) if len(fight.tile) == 3 else [0, 0, 0]
        for n, value in enumerate((tile_x, tile_y, upper)):
            if value is not None:
                tile[n] = int(value)
        qx.set_won_when(edits, battle, way, unit, share if share is not None else (fight.share or qx.SHARE), tile)
        self._changed()
        # A share or a tile changes nothing else the card shows (each is one the helper reads): its spin box keeps
        # its focus as the card stays.
        if share is None and tile_x is None and tile_y is None and upper is None:
            self._show_card()

    def _set_protect(self, battle: str, unit) -> None:
        """The unit the battle is lost without (its scene once it is lost made from the game's), or none."""
        if self._building:
            return
        try:
            qx.set_protect(self.edits(), self.game(), battle, int(unit or 0))
        except ValueError:
            self._say(NO_GAME)
        self._changed()
        self._show_card()

    def _set_objective(self, battle: str, words: str) -> None:
        """The battle's objective in the quest's own words, its start scene showing it (one made from the game's
        battle start when it has none)."""
        edits, lengths = self.edits(), self.lengths()
        if self._building or edits is None or lengths is None:
            return
        fight = edits.quest.event_named(battle).battle
        words = words.strip()
        if words == fight.objective:
            return
        if words and not sq.good_objective(words):
            self._say(OBJECTIVE_TIP)
            self._show_card()
            return
        try:
            qx.set_objective(edits, self.game(), battle, words, lengths)
        except ValueError:
            self._say(NO_GAME)
        self._changed()
        self._show_card()

    def _setup_fields(self, card: CardPane, ev: sq.QuestEvent) -> None:
        """The rest of an event's setup, as the Event Editor's setup card gives them: its music (each with its
        Play), weather, time of day, the map's arrangement, the portrait and its unit."""
        card.field(words.SETUP_LABELS["Music1"], self._music_row(ev, "Music1"))
        card.field(words.SETUP_LABELS["Music2"], self._music_row(ev, "Music2"))
        card.fields.addWidget(pair(
            (words.SETUP_LABELS["Weather"], self._setup_combo(ev, "Weather", list(enumerate(map_classic.WEATHERS)))),
            (words.SETUP_LABELS["Night"], self._setup_combo(ev, "Night", list(words.TIMES_OF_DAY.items())))))
        card.fields.addWidget(pair(
            (words.SETUP_LABELS["Arrangement"], self._setup_combo(
                ev, "Arrangement", [(n, me_page.arrangement_word(n)) for n in range(8)])),
            (words.SETUP_LABELS["Portrait"], self._setup_spin(ev, "Portrait", su.field_of("Portrait").most))))
        card.fields.addWidget(pair((words.SETUP_LABELS["PortraitUnit"],
                                    self._setup_spin(ev, "PortraitUnit", su.field_of("PortraitUnit").most))))

    def _set_start_scene(self, battle: str, scene) -> None:
        """The scene a battle plays as it starts: one of the quest's scenes no step plays, none, or (Zodi, 4
        November) a new one, two of its units speaking (`quest_edits.make_sample_start`)."""
        if self._building:
            return
        edits = self.edits()
        if scene == NEW_SCENE_KEY:
            # (Zodi, 4 November) A new one, two of the battle's units speaking; no copy of the game's.
            game = self.game()
            if game is None:
                self._show_card()
                return
            try:
                scene = qx.make_sample_start(edits, game, battle)
            except (OSError, ValueError, es.ScriptError) as exc:
                self._say(CANT_MAKE.format(problem=exc))
                self._show_card()
                return
        qx.set_start_scene(edits, battle, scene or "", self.lengths())
        self._keep_objective(battle)
        self._changed()
        self._show_card()

    def _keep_objective(self, battle: str) -> None:
        """(1.12.0) A battle with an objective keeps a start scene showing it: a copy of the game's battle start once
        it has none, the objective box in one that shows none."""
        edits = self.edits()
        ev = edits.quest.event_named(battle) if edits is not None else None
        if ev is None or ev.battle is None or not ev.battle.objective or self.lengths() is None:
            return
        try:
            qx.set_objective(edits, self.game(), battle, ev.battle.objective, self.lengths())
        except ValueError:
            self._say(NO_GAME)

    def rename_event(self, old: str, new: str) -> None:
        edits = self.edits()
        if edits is None or self._building or new == old:
            return
        try:
            qx.rename_event(edits, old, new)
        except ValueError:
            self._say(NAME_BAD if not sq.good_name(new) else EVENT_TAKEN.format(name=new))
            self._show_card()
            return
        if self.picked and len(self.picked) > 1 and self.picked[1] == old:
            self.picked = (self.picked[0], new) + tuple(self.picked[2:])
        self._changed()
        self._show_card()

    def open_map(self, battle: str) -> None:
        """Open on the Map Editor: the battle's quest map shown there."""
        ev = self.edits().quest.event_named(battle) if self.edits() is not None else None
        value = ev.setup.get("Map") if ev is not None else None
        if isinstance(value, str):
            self.navigate_requested.emit(MAP_EDITOR, value)

    def _has_grid(self, number: int) -> bool:
        game = self.game_dir()
        try:
            return game is not None and bool(map_classic.map_grids(game / map_classic.MAP_FOLDER, number))
        except (OSError, map_classic.MapError):
            return False

    def new_quest_map(self, battle: str) -> None:
        """A quest map made from the map the battle is on (as the mod has it, or a copy of the quest map it is on),
        named and titled in the Map Editor's own dialog, and the battle fought on it."""
        edits = self.edits()
        ev = edits.quest.event_named(battle) if edits is not None else None
        if ev is None:
            return
        value = ev.setup.get("Map")
        maps = getattr(self.state, "quest_maps", None)
        if maps is None:
            maps = self.state.quest_maps = {}
        shown = maps.get(value) if isinstance(value, str) else None
        base = shown.base if shown is not None else value
        if not isinstance(base, int):
            self._say(PICK_A_MAP)
            return
        if not self._has_grid(base):
            self._say(me_page.QUEST_NO_GRID.format(base=base))
            return
        place = me_page.map_names(self.state).get(base, "")
        where = f", {_label(place)}," if place else ""
        intro = (QUEST_MAP_COPY_INTRO.format(name=value, base=base, place=where) if shown is not None
                 else QUEST_MAP_INTRO.format(base=base, place=where))
        taken = set(maps)
        dialog = me_page.QuestMapDialog(self, me_page.QUEST_NEW_DIALOG, intro, me_page.quest_name_for(place, taken),
                                        "", place, taken)
        answer = self._ask("quest_map", lambda: dialog.values() if dialog.exec() == QDialog.Accepted else None)
        if not answer:
            return
        name, title = answer
        said = me_page.quest_name_problem(name, title, taken)
        if said:
            self._say(said)
            return
        maps[name] = qme.copy_of(shown, title) if shown is not None else qme.from_state(self.state, base, title)
        ev.setup["Map"] = name
        self._say(QUEST_MAP_MADE.format(name=name, base=base))
        self._changed()
        self._show_card()
        self._show_middle()

    def own_units(self, ev: Optional[sq.QuestEvent]) -> Optional[str]:
        """The quest's own units an event shows, by their name among its battles: a battle's, or (Zodi, 4 November: a
        new scene has two units of its own) a scene's, those the map shows (`_units_block`: its setup's EnemyBattle,
        else its SceneUnits) when they are one of the quest's; None when they are the game's, or none."""
        edits = self.edits()
        if ev is None or edits is None:
            return None
        if ev.battle is not None:
            return ev.battle.units if isinstance(ev.battle.units, str) else None
        units = ev.setup.get("EnemyBattle") or ev.setup.get("SceneUnits")
        return units if isinstance(units, str) and any(b.name == units for b in edits.quest.battles) else None

    def add_unit(self, battle: str) -> None:
        """A copy of the unit picked (or the first) in the battle's (or the scene's) first empty place, and it
        picked."""
        edits = self.edits()
        ev = edits.quest.event_named(battle)
        units = self.own_units(ev)
        if units is None:
            return
        picked = self.picked[2] if self.picked and self.picked[0] == "unit" else None
        slot = qx.add_unit(edits, units, picked)
        if slot is None:
            occupied = [u.occupied for u in entd.battle_units(qx.battle_block(edits, units))]
            self._say(FULL if all(occupied) else NO_UNIT_TO_COPY)
            return
        self.picked = ("unit", battle, slot)
        self._changed()
        self._show_card()
        self._show_middle()

    def _unit_card(self, edits: qx.QuestEdits, ev: sq.QuestEvent, slot: int) -> CardPane:
        """A quest battle's unit's card (`_unit_card_of`); (4 November) a scene's own units' too, its way back the
        scene's."""
        units = self.own_units(ev)
        return self._unit_card_of(qx.battle_block(edits, units), slot,
                                  lambda field, value: self._set_unit(ev.name, slot, field, value),
                                  lambda: self.pick(("event", ev.name)), lambda: self.take_out_unit(ev.name, slot),
                                  BACK_TO_BATTLE if ev.battle is not None else BACK_TO_SCENE,
                                  qx.own_name(edits, units, slot),
                                  lambda text: self._set_own_name(ev.name, slot, text))

    def _unit_card_of(self, block: bytes, slot: int, set_field, back, take_out,
                      back_words: Optional[str] = None, own: str = "", set_own=None) -> CardPane:
        """One of a battle's 16 units (`block`), every field the game's battle files give it: `set_field(field,
        value)` changes one, `back` goes back to its battle's card (`back_words` its button, Back to the battle when
        not given), `take_out` empties its place. (1.17.0) A quest's battle's or a battle ground's random battle's;
        (4 November) a quest's scene's own. (1.33.0) A quest's unit's own name too (`own`, `set_own(text)`), its Unit
        Name then Random."""
        back_words = back_words or BACK_TO_BATTLE
        unit = entd.battle_units(block)[slot]
        v = unit.values
        card = CardPane(UNIT_BAND, UNIT_SLOT.format(n=slot + 1), UNIT_COLOUR,
                        self._unit_words(v) if unit.occupied else EMPTY_SLOT, UNIT_BLURB)

        def chosen(field: str, choices: list) -> QComboBox:
            box = combo(choices, v[field])
            box.currentIndexChanged.connect(lambda _i, b=box, f=field: set_field(f, b.currentData()))
            self.field_widgets[f"unit_{field}"] = box
            return box

        def number(field: str, most: int = 255) -> QSpinBox:
            box = spin(min(v[field], most), 0, most)
            box.valueChanged.connect(lambda value, f=field: set_field(f, value))
            self.field_widgets[f"unit_{field}"] = box
            return box

        def ticks(*pairs, columns: int = 2) -> QWidget:
            grid = QWidget()
            layout = QGridLayout(grid)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setHorizontalSpacing(10)
            layout.setVerticalSpacing(3)
            for n, (field, label) in enumerate(pairs):
                box = QCheckBox(label)
                box.setChecked(bool(v[field]))
                box.toggled.connect(lambda on, f=field: set_field(f, bool(on)))
                self.field_widgets[f"unit_{field}"] = box
                layout.addWidget(box, n // columns, n % columns)
            return grid

        def section(name: str, count: int, *widgets) -> None:
            body = QWidget()
            fields = QVBoxLayout(body)
            fields.setContentsMargins(4, 2, 0, 6)
            fields.setSpacing(5)
            for w in widgets:
                fields.addWidget(w)
            opened = self._open_sections.get(name, name in SECTIONS[:3])
            box = CollapsibleSection(SECTION_TITLE.format(name=name, count=count), body, expanded=opened)
            box.header.toggled.connect(lambda on, n=name: self._open_sections.__setitem__(n, on))
            self.field_widgets[f"section_{name}"] = box
            card.fields.addWidget(box)

        def table(column: str, specials: dict, most: int = 255) -> list:
            """A field's choices: its special values first, then the game's names for the rest it can hold."""
            names = self._choices(column)
            return list(specials.items()) + [(k, names[k]) for k in sorted(names) if k <= most and k not in specials]

        def numbers(least: int, most: int, specials: dict, words_: Optional[dict] = None) -> list:
            words_ = words_ or {}
            return list(specials.items()) + [(n, words_.get(n, str(n))) for n in range(least, most + 1)
                                             if n not in specials]

        specials = c.ENTRY_SPECIAL_VALUES
        random_byte = {entd.RANDOM_BYTE: RANDOM}
        items = nxd_names(self.state, "item")
        name_box = chosen("unit_name", table("Unknown4", specials["Unknown4"]))
        # (1.33.0) A quest's unit's own name, beside its Unit Name, which it makes Random.
        own_rows = []
        if set_own is not None and unit.occupied:
            own_edit = QLineEdit(own)
            own_edit.setMaxLength(sq.MOST_OWN_NAME)
            own_edit.setPlaceholderText(OWN_NAME_NONE)
            own_edit.setToolTip(OWN_NAME_TIP)
            own_edit.editingFinished.connect(lambda e=own_edit: set_own(e.text().strip()))
            self.field_widgets["own_name"] = own_edit
            name_box.setEnabled(not own)
            if own:
                name_box.setToolTip(OWN_NAME_RANDOM_TIP)
            own_rows.append(pair(("Own Name", own_edit)))
        section(SECTIONS[0], 12 + len(own_rows),
                pair(("Spriteset", chosen("sprite_set", table("Spriteset", {}))),
                     ("Unit Name", name_box)),
                *own_rows,
                pair(("Main Job", chosen("main_job", table("MainJob", specials["MainJob"]))),
                     ("Unit ID", number("unit_id"))),
                pair(("Job Unlock", chosen("prereq_job", table("JobUnlock", {0: BASE_JOB}))),
                     ("Job Level", number("prereq_job_level", c.ENTRY_JOB_LEVEL_MAX))),
                ticks(("male", "Male"), ("female", "Female"), ("monster", "Monster"),
                      ("zodiac_monster", "Zodiac Monster")),
                pair(("Palette", number("palette")),
                     ("Birthday", row(chosen("month", list(MONTHS.items())),
                                      chosen("day", numbers(0, 31, random_byte))))))
        section(SECTIONS[1], 5,
                pair(("Primary Job Command", chosen("primary_command", table("EntryUnknown1D",
                                                                             specials["EntryUnknown1D"]))),
                     ("Secondary Job Command", chosen("secondary_command",
                                                      table("SecondarySkillset", specials["SecondarySkillset"])))),
                pair(("Reaction", chosen("reaction", table("Reaction", specials["Reaction"], 0x1FF))),
                     ("Support", chosen("support", table("Support", specials["Support"], 0x1FF)))),
                pair(("Movement", chosen("movement", table("Movement", specials["Movement"], 0x1FF)))))
        section(SECTIONS[2], 5,
                pair(("Right Hand", chosen("right_hand", table("RightHand", specials["RightHand"]))),
                     ("Left Hand", chosen("left_hand", table("LeftHand", specials["LeftHand"])))),
                pair(("Head", chosen("head", table("Head", specials["Head"]))),
                     ("Body", chosen("body", table("Body", specials["Body"])))),
                pair(("Accessory", chosen("accessory", table("Accessory", specials["Accessory"])))))
        section(SECTIONS[3], 4,
                pair(("Level", chosen("level", numbers(0, 255, random_byte, c.entry_level_choices()))),
                     ("Experience", number("experience"))),
                pair(("Bravery", chosen("bravery", numbers(0, c.ENTRY_TRAIT_MAX, random_byte))),
                     ("Faith", chosen("faith", numbers(0, c.ENTRY_TRAIT_MAX, random_byte)))))
        section(SECTIONS[4], 13,
                pair(("Position X", number("x")), ("Position Y", number("y"))),
                pair(("Initial Direction", chosen("facing", list(entd.FACING_NAMES.items()))),
                     ("Team", chosen("team", list(TEAMS.items())))),
                ticks(("upper_level", "Higher Elevation"), ("always_present", "Always Present"),
                      ("randomly_present", "Randomly Present"), ("control", "Control"), ("immortal", "Immortal"),
                      ("join_after_event", "Join After Event"), ("load_formation", "Load Formation"),
                      ("save_formation", "Save Formation"), ("save_ct", "Save CT")))
        # (Zodi, 4 November: "clean up some of the very long notes") What Load Formation and Save Formation do, on them.
        for field in qx.FORMATION_FLAGS:
            self.field_widgets[f"unit_{field}"].setToolTip(FORMATION_NOTE)
        section(SECTIONS[5], 7,
                ticks(("focus_unit", "Focus Unit"), ("stay_near_xy", "Stay Near X and Y"),
                      ("aggressive", "Aggressive"), ("defensive", "Defensive")),
                pair(("Target", number("target"))),
                pair(("Target X", number("target_x")), ("Target Y", number("target_y"))))
        section(SECTIONS[6], 2,
                pair(("War Trophy", chosen("war_trophy", [(0, NOTHING)] + [(k, items[k]) for k in sorted(items)
                                                                          if 0 < k <= 255])),
                     ("Bonus Money", number("bonus_money"))))
        section(SECTIONS[7], 16,
                pair(("Unknown10", number("unknown10")), ("Unknown12", number("unknown12"))),
                muted(UNNAMED_NOTE),
                ticks(*[(name, UNNAMED_LABEL.format(byte=name.split("_")[1], bit=name.split("_")[2]))
                        for name in entd.UNNAMED_FLAGS], columns=3))
        card.status([])
        card.add_buttons(back_words, UNIT_TAKE_OUT)
        card.buttons[back_words].clicked.connect(lambda: back())
        card.buttons[UNIT_TAKE_OUT].clicked.connect(lambda: take_out())
        card.buttons[UNIT_TAKE_OUT].setEnabled(unit.occupied)
        return card

    def _set_unit(self, event: str, slot: int, field: str, value) -> None:
        if self._building or value is None:
            return
        edits = self.edits()
        ev = edits.quest.event_named(event)
        units = self.own_units(ev)
        if units is None:
            return
        try:
            qx.set_unit(edits, units, slot, **{field: value})
        except ValueError as exc:
            self._say(str(exc))
            return
        self._changed()
        self.battle_map.refresh_units()
        if field in TITLE_FIELDS and self.card is not None:
            unit = entd.battle_units(qx.battle_block(edits, units))[slot]
            self.card.title.setText(self._unit_words(unit.values) if unit.occupied else EMPTY_SLOT)

    def _set_own_name(self, event: str, slot: int, text: str) -> None:
        """(1.33.0) A quest's unit's own name set ("" none): said when it isn't one; its card shown again (its Unit
        Name then Random, and grayed out while it has one); (his test 69) the lines it says marked with it."""
        if self._building:
            return
        edits = self.edits()
        ev = edits.quest.event_named(event)
        units = self.own_units(ev)
        if units is None or text == qx.own_name(edits, units, slot):
            return
        try:
            qx.set_own_name(edits, units, slot, text, self.lengths())
        except ValueError as exc:
            self._say(str(exc))
            return
        self._changed()
        self._show_card()

    def take_out_unit(self, event: str, slot: int) -> None:
        edits = self.edits()
        ev = edits.quest.event_named(event)
        units = self.own_units(ev)
        if units is None:
            return
        qx.take_out_unit(edits, units, slot, self.lengths())
        self.picked = ("event", event)
        self._changed()
        self._show_card()
        self._show_middle()

    def _scene_card(self, edits: qx.QuestEdits, ev: sq.QuestEvent) -> CardPane:
        quest = edits.quest
        what = qx.role(quest, ev.name)
        step = qx.step_of(quest, ev.name)
        n = self._step_number(edits, step.start) if step is not None else 0
        fight = quest.fight_of(ev.name)
        card = CardPane(SCENE_BAND, STEP.format(n=n) if n else UNPLAYED, SCENE_COLOUR, ev.name,
                        SCENE_BLURB[what].format(battle=fight.name if fight is not None else ""))
        name = QLineEdit(ev.name)
        name.setMaxLength(64)
        name.setToolTip(NAME_TIP)
        name.editingFinished.connect(lambda box=name, old=ev.name: self.rename_event(old, box.text()))
        self.field_widgets["event_name"] = name
        card.field(NAME, name)
        # (Zodi, 4 November) A new scene is no copy of the game's: a scene says what it was made from only when it
        # plays with a battle (made from the game's victory, game over or battle start, or a copy made before); a
        # scene of a step's own says no more than its doors (`_doors_box`), as its From is theirs to change now.
        made = (MADE_FROM_WON.format(event=qx.VICTORY_SCENE) if what == "won"
                else MADE_FROM_LOST.format(event=qx.GAME_OVER_SCENE) if what == "lost"
                else MADE_FROM_START.format(event=ev.copied_from) if ev.copied_from == qx.BATTLE_START_SCENE
                else MADE_FROM_EVENT.format(event=ev.copied_from) if ev.copied_from and what == "start"
                else "")
        if made:
            card.field(MADE_FROM, muted(made))
        # Every line its script shows, its words where it has them (a sample's, or copied from the game's), else to
        # be written.
        have = {line.line_id: line for line in qx.lines_of(edits, ev.name)}
        shown, variables = self._script_facts(ev)
        boxes = []
        # In the order the scene shows them; any line of its words it doesn't show after them. (Zodi's choice of 5
        # November, "Words without the mark") A line's mark naming its box isn't shown, as the Event Editor shows it:
        # the words typed keep it (`quest_edits.set_scene_words`).
        for line_id in list(shown) + sorted(set(have) - set(shown)):
            box = QLineEdit(qx.without_mark(have[line_id].line) if line_id in have else "")
            box.setPlaceholderText(NO_WORDS_YET)
            # (4 November) A long line shows from its start, as it is read.
            box.setCursorPosition(0)
            box.editingFinished.connect(lambda b=box, n=line_id: self._set_line(ev.name, n, b.text()))
            self.field_widgets[f"line_{line_id}"] = box
            boxes.append(box)
        card.field(WHAT_IS_SAID, *(boxes or [muted(NOTHING_SAID)]))
        # (4 November) Its other languages follow English where they said the same (a sample's); a copy's keep the
        # game's words, and say so.
        if boxes and qx.words_apart(edits, ev.name):
            card.fields.addWidget(muted(WORDS_NOTE.format(language="English")))
        if any(line_id not in have for line_id in shown):
            card.fields.addWidget(muted(WORDS_MISSING))
        nodes = QPushButton(OPEN_EVENT_EDITOR)
        nodes.setToolTip(NODES_NOTE)
        nodes.clicked.connect(lambda: self.navigate_requested.emit(EVENT_EDITOR, ("quest", self.folder, ev.name)))
        self.field_widgets["open_event_editor"] = nodes
        card.field(NODES, row(nodes, stretch_first=False))
        sets = [SETS_AS_ENDS.format(flag=f) for f in dict.fromkeys(f for _, f in ev.flags_in_script)]
        card.field(FLAGS_IT_SETS, muted("\n".join(sets) if sets else SETS_NONE))
        if variables:
            named = (VARIABLES_ONE.format(variable=variables[0]) if len(variables) == 1 else VARIABLES_MANY.format(
                variables=", ".join(str(v) for v in variables[:-1]), last=variables[-1]))
            card.fields.addWidget(muted(GAME_VARIABLES.format(variables=named)))
        # (1.31.0) The quest's reward, on its last step's last scene.
        if qx.reward_scene(quest) == ev.name:
            self._reward_fields(card, edits, ev)
        if what == "during":
            self._during_fields(card, edits, ev, fight)
        if what == "scene":
            maps = self._setup_combo(ev, "Map", self._map_choices(), None)
            maps.setToolTip(MAP_NOTE)
            card.field(MAP, maps)
            # (Zodi, 4 November: nothing lost with the copies) On a map whose doors the game's events open, which of
            # them it opens them as (its From).
            doors = self._doors_box(ev)
            if doors is not None:
                card.field(DOORS_FIELD, doors)
            own = self.own_units(ev)
            if own is not None:
                self._units_field(card, edits, ev, own)
            battles = self._units_choices()
            card.fields.addWidget(pair(
                (words.SETUP_LABELS["EnemyBattle"], self._setup_combo(ev, "EnemyBattle", battles)),
                (words.SETUP_LABELS["SceneUnits"], self._setup_combo(ev, "SceneUnits", battles))))
            # (28 October) A scene copied before Mod Studio cleared a battle's deploy areas from it (or written by
            # hand) shows them, so they can be set to none (`quest_edits.DEPLOYS`).
            if any(ev.setup.get(key) for key in qx.DEPLOYS):
                squads = self._squads()
                card.fields.addWidget(pair(
                    (words.SETUP_LABELS["DeployArea1"], self._setup_combo(ev, "DeployArea1", squads)),
                    (words.SETUP_LABELS["DeployArea2"], self._setup_combo(ev, "DeployArea2", squads))))
                card.fields.addWidget(muted(SCENE_DEPLOYS))
            self._setup_fields(card, ev)
        else:
            card.fields.addWidget(muted(PLAYS_WITH_BATTLE.format(battle=fight.name if fight is not None else "")))
        card.status(self._problems_of(edits, ev.name))
        if qx.can_remove(quest, ev.name):
            card.add_buttons(REMOVE_SCENE)
            card.buttons[REMOVE_SCENE].clicked.connect(lambda: self.remove_event(ev.name))
        else:
            card.fields.addWidget(muted(LOST_STAYS if what == "lost" else WON_STAYS))
        return card

    def _during_words(self, edits: qx.QuestEdits, battle: sq.QuestEvent, d) -> str:
        """(1.31.0) When a scene during a battle plays, in words: "On Ramza's turn", "As Knight 2's HP falls"."""
        return DURING_DETAIL[d.when].format(unit=self._during_unit_name(edits, battle, d.unit))

    def _during_unit_name(self, edits: qx.QuestEdits, battle: sq.QuestEvent, slot: int) -> str:
        """Ramza (0), or a battle's unit (1 to 16) by its job and place."""
        if slot == 0:
            return DURING_RAMZA
        jobs = self._choices("MainJob")
        try:
            unit = entd.battle_units(qx.battle_block(edits, battle.battle.units))[slot - 1]
        except (StopIteration, KeyError, IndexError, ValueError):
            return f"unit {slot}"
        return REWARD_UNIT_CHOICE.format(n=slot, job=jobs.get(unit.values["main_job"], str(unit.values["main_job"])))

    def _during_fields(self, card: CardPane, edits: qx.QuestEdits, ev: sq.QuestEvent, fight) -> None:
        """(1.31.0, his choice "Either, picked on the card") When a scene during a battle plays: as its unit's turn
        comes or as its HP falls (to a share of its most, 0 beaten), its unit Ramza or one of the battle's."""
        d = next((x for x in fight.battle.during if x.event == ev.name), None) if fight is not None else None
        if d is None:
            return
        plays = combo([(sq.TURN, ON_TURN), (sq.HP, ON_HP)], d.when)
        plays.currentIndexChanged.connect(lambda _i, b=plays: self._set_during(ev.name, when=b.currentData()))
        units = [(0, DURING_RAMZA)] + [
            (u.slot + 1, self._during_unit_name(edits, fight, u.slot + 1))
            for u in entd.battle_units(qx.battle_block(edits, fight.battle.units)) if u.occupied] \
            if isinstance(fight.battle.units, str) else [(0, DURING_RAMZA)]
        unit = combo(units, d.unit)
        unit.currentIndexChanged.connect(lambda _i, b=unit: self._set_during(ev.name, unit=b.currentData()))
        self.field_widgets.update(during_plays=plays, during_unit=unit)
        card.fields.addWidget(pair((DURING_PLAYS, plays), (DURING_UNIT, unit)))
        if d.when == sq.HP:
            share = spin(d.share, 0, sq.MOST_SHARE_DURING)
            share.setToolTip(DURING_SHARE_TIP)
            share.valueChanged.connect(lambda value: self._set_during(ev.name, share=int(value), keep=True))
            self.field_widgets["during_share"] = share
            card.field(DURING_SHARE, share)

    def _set_during(self, scene: str, when=None, unit=None, share=None, keep: bool = False) -> None:
        """When a scene during a battle plays changed (`quest_edits.set_during`): the card again, but for its share."""
        if self._building:
            return
        qx.set_during(self.edits(), scene, when, unit, share)
        self._changed()
        if not keep:
            self._show_card()

    def add_during(self, battle: str) -> None:
        """(1.31.0) A new scene during a battle, as the sample's on Ramza's turn (`quest_edits.make_sample_during`),
        picked."""
        edits, game = self.edits(), self.game()
        if edits is None or game is None:
            self._say(NO_GAME)
            return
        try:
            name = qx.make_sample_during(edits, game, battle)
        except (OSError, ValueError, es.ScriptError) as exc:
            self._say(CANT_MAKE.format(problem=exc))
            return
        self.picked = ("event", name)
        self._changed()
        self._show_card()
        self._show_middle()

    def _reward_fields(self, card: CardPane, edits: qx.QuestEdits, ev: sq.QuestEvent) -> None:
        """(1.31.0, Zodi's ask of 3 November: "A reward as a quest ends"; his choices "Its last step only" and "A line
        in the scene", given silently too) The quest's reward on its last step's last scene: its gil, its items (the
        mod's own or the game's, each with a count), one of the scene's own units joining, and whether the scene says
        it (`quest_edits.set_reward`)."""
        lengths = self.lengths()
        reward = qx.reward_of(edits, lengths) if lengths is not None else None
        if reward is None:
            return
        card.field(REWARD_FIELD, muted(REWARD_NOTE))
        gil = spin(reward.gil, 0, sq.MOST_GIL)
        gil.setSingleStep(100)
        gil.setGroupSeparatorShown(True)
        gil.valueChanged.connect(lambda value: self._set_reward(gil=int(value)))
        self.field_widgets["reward_gil"] = gil
        card.field(REWARD_GIL, gil)
        choices = self._reward_item_choices()
        rows = []
        for n, (item, count) in enumerate(reward.items):
            pick = combo(choices, item)
            pick.currentIndexChanged.connect(lambda _i, b=pick, k=n: self._set_reward_item(k, item=b.currentData()))
            many = spin(count, 1, sq.MOST_OF_AN_ITEM)
            many.valueChanged.connect(lambda value, k=n: self._set_reward_item(k, count=int(value)))
            out = QPushButton(REMOVE_REWARD_ITEM)
            out.clicked.connect(lambda _c=False, k=n: self._set_reward_item(k, remove=True))
            self.field_widgets.update({f"reward_item_{n}": pick, f"reward_count_{n}": many,
                                       f"reward_remove_{n}": out})
            rows.append(row(pick, many, out))
        add = QPushButton(ADD_REWARD_ITEM)
        add.setEnabled(len(reward.items) < sq.MOST_REWARD_ITEMS and bool(choices))
        add.clicked.connect(lambda: self._set_reward_item(None))
        self.field_widgets["reward_add_item"] = add
        card.field(REWARD_ITEMS, *rows, row(add, stretch_first=False))
        units = qx.scene_units(edits.quest, ev.name)
        if units is not None:
            jobs = self._choices("MainJob")
            joining = combo([(-1, REWARD_NO_UNIT)] + [
                (u.slot, REWARD_UNIT_CHOICE.format(n=u.slot + 1, job=jobs.get(u.values["main_job"],
                                                                             str(u.values["main_job"]))))
                for u in entd.battle_units(qx.battle_block(edits, units)) if u.occupied],
                -1 if reward.unit is None else reward.unit)
            joining.currentIndexChanged.connect(
                lambda _i, b=joining: self._set_reward(unit=None if b.currentData() == -1 else b.currentData()))
            joining.setToolTip(REWARD_UNIT_TIP)
            self.field_widgets["reward_unit"] = joining
            card.field(REWARD_UNIT, joining)
        else:
            card.field(REWARD_UNIT, muted(REWARD_UNIT_WON))
        said = QCheckBox(REWARD_SAID)
        said.setChecked(reward.said)
        said.setToolTip(REWARD_SAID_TIP)
        # (His test 66) It says the gil and items: the New Party Member screen says a unit joining.
        said.setEnabled(bool(reward.gil or reward.items))
        said.toggled.connect(lambda on: self._set_reward(said=bool(on)))
        self.field_widgets["reward_said"] = said
        card.fields.addWidget(said)

    def _reward_item_choices(self) -> list:
        """A reward's items: the mod's own (by their names) but an item to use (one made before 1.27.0: Zodi, test 66,
        "I told you to never make consumable items because units need to learn an ability to use them"), then the
        game's (by their numbers, as the mod names them)."""
        own = [(e.item.name, OWN_ITEM.format(name=e.item.name)) for e in self.items_store().values()
               if e.item.kind != mi.ITEM]
        names = nxd_names(self.state, "item")
        return own + [(n, names.get(n, str(n))) for n in mi.GAME_ITEMS]

    def _reward_item_words(self) -> dict:
        """Each item's singular and plural, as a reward's line says them: the game's (its Item table as the mod has
        it), the mod's own (its item's words)."""
        out = {}
        try:
            records = self.state.nxd_records_for("item").get("en") or []
            edits = self.state.nxd_edits_for("item").get("en", {})
        except Exception:                                             # noqa: BLE001
            records, edits = [], {}
        for record in records:
            values = dict(record.values)
            values.update(edits.get(record.key, {}))
            out[record.key] = (str(values.get("NameSingular") or values.get("Name") or ""),
                               str(values.get("NamePlural") or ""))
        for e in self.items_store().values():
            out[e.item.name] = (e.item.singular or e.item.name, e.item.plural or "")
        return out

    _SAME = object()

    def _set_reward(self, gil=None, items=None, unit=_SAME, said=None, keep: bool = False) -> None:
        """The quest's reward, one of its parts changed (`quest_edits.set_reward`): the card again, but for its gil
        or an item's count (`keep`), whose spin box keeps its focus."""
        if self._building:
            return
        edits, lengths = self.edits(), self.lengths()
        reward = qx.reward_of(edits, lengths) if edits is not None and lengths is not None else None
        if reward is None:
            return
        qx.set_reward(edits, lengths, reward.gil if gil is None else gil, reward.items if items is None else items,
                      reward.unit if unit is self._SAME else unit, reward.said if said is None else said,
                      self._reward_item_words(), self._choices("MainJob"))
        self._changed()
        if gil is None and not keep:
            self._show_card()
            return
        # The card stays (its spin box keeping its focus): the line saying the reward shows its words as they are now.
        now = qx.reward_of(edits, lengths)
        box = self.field_widgets.get(f"line_{now.line}") if now is not None and now.line is not None else None
        if box is not None:
            words = next((x.line for x in qx.lines_of(edits, qx.reward_scene(edits.quest)) if x.line_id == now.line),
                         "")
            box.blockSignals(True)
            box.setText(words)
            box.setCursorPosition(0)
            box.blockSignals(False)

    def _set_reward_item(self, index: Optional[int], item=None, count=None, remove: bool = False) -> None:
        """One of the reward's items changed (`item`, `count`) or taken out; `index` None adds the first item not
        listed yet, one of it."""
        if self._building:
            return
        edits, lengths = self.edits(), self.lengths()
        reward = qx.reward_of(edits, lengths) if edits is not None and lengths is not None else None
        if reward is None:
            return
        items = list(reward.items)
        listed = [i for i, _ in items]
        if index is None:
            free = next((data for data, _ in self._reward_item_choices() if data not in listed), None)
            if free is None:
                return
            items.append((free, 1))
        elif remove:
            items.pop(index)
        else:
            was, many = items[index]
            if item is not None and item != was and item in listed:
                self._show_card()
                return
            items[index] = (was if item is None else item, many if count is None else count)
        self._set_reward(items=items, keep=count is not None)

    def _script_facts(self, ev: sq.QuestEvent) -> tuple:
        """`(the lines its script shows, in the order it shows them; the game's variables it sets)`: the variable
        instructions' first variables but the quest's own flags (its FlagsInScript), as Mod Studio Framework
        leaves them to the game; empty when the script can't be read."""
        edits, lengths = self.edits(), self.lengths()
        data = edits.files.get(ev.script) if edits is not None else None
        if data is None or lengths is None:
            return [], []
        try:
            script = es.read_script(data, lengths, "enhanced")
            shown = qx.lines_in_order(data, lengths)
        except es.ScriptError:
            return [], []
        own = {at for at, _ in ev.flags_in_script}
        found, at = set(), 0
        for ins in script.instructions:
            if qx.ADD_OP <= ins.opcode <= qx.CLEAR_OP and at + 1 not in own:
                variable = es.operand(ins, "variable")
                if variable is not None:
                    found.add(variable)
            at += ins.size
        return shown, sorted(found)

    def _units_choices(self) -> list:
        """A scene's units: none, one of the quest's battles by its name, or one of the game's by its number."""
        edits = self.edits()
        own = [(b.name, BATTLE_OF_QUEST.format(name=b.name)) for b in edits.quest.battles] if edits is not None else []
        return [(0, words.SETUP_NO_BATTLE)] + own + [(b, label) for b, label in self.game_battles()]

    def _scene_map_number(self, ev: sq.QuestEvent) -> Optional[int]:
        """The game's map a scene plays on: its setup's Map, or the one its quest map is made from; None when it has
        none."""
        value = ev.setup.get("Map")
        if isinstance(value, str):
            quest_map = (getattr(self.state, "quest_maps", None) or {}).get(value)
            return quest_map.base if quest_map is not None else None
        return value if isinstance(value, int) else None

    def _doors_named(self, ev: sq.QuestEvent) -> bool:
        """Whether a scene's From is one of the game's events that open its map's doors (said by Its doors play as
        in, not Made from)."""
        game = self.game()
        number = self._scene_map_number(ev)
        return bool(ev.copied_from) and game is not None and number is not None and \
            ev.copied_from in game.door_events(number)

    def _doors_box(self, ev: sq.QuestEvent) -> Optional[QComboBox]:
        """(Zodi, 4 November: "we should not lose any functionality") Its doors play as in: none, or one of the game's
        events on its map that opens the map's doors or moves its parts (`quest_edits.Game.door_events`), its From;
        a copy of the game's had its own (Mod Studio Framework 1.11.0, his test 36). None when its map has none, and
        its From names none of them."""
        game = self.game()
        number = self._scene_map_number(ev)
        events = game.door_events(number) if game is not None and number is not None else []
        if not events and not self._doors_named(ev):
            return None
        choices = [(0, DOORS_NONE)] + [(n, DOORS_EVENT.format(event=n)) for n in events]
        if ev.copied_from and ev.copied_from not in events:
            choices.append((ev.copied_from, DOORS_EVENT.format(event=ev.copied_from)))
        box = combo(choices, ev.copied_from)
        box.setToolTip(DOORS_TIP)
        box.currentIndexChanged.connect(lambda _i, b=box, name=ev.name: self._set_doors(name, b.currentData()))
        self.field_widgets["doors"] = box
        return box

    def _set_doors(self, event: str, number: int) -> None:
        if self._building:
            return
        ev = self.edits().quest.event_named(event)
        ev.copied_from = int(number or 0)
        self._changed(refill=False)

    def _set_line(self, event: str, line_id: int, text: str) -> None:
        """A line's words in English; (4 November) in each other language that said the same, those too
        (`quest_edits.set_scene_words`: a sample's words, in every language, follow)."""
        if self._building:
            return
        qx.set_scene_words(self.edits(), event, line_id, text, qx.LANGUAGE)
        self._changed(refill=False)

    def remove_event(self, name: str) -> None:
        edits = self.edits()
        lengths = self.lengths()
        if edits is None or lengths is None:
            return
        fight = edits.quest.fight_of(name)
        qx.remove_event(edits, name, lengths)
        if fight is not None and edits.quest.event_named(fight.name) is not None:
            self._keep_objective(fight.name)
        self.picked = ("quest",)
        self._changed()
        self.show_quest()

    # =========================================================================
    # (1.26.0) Items (the Items tab: Zodi's list of 3 November, his first)
    # =========================================================================

    def items_store(self) -> dict:
        """The mod's own items as the Items tab has them (`state.items`: `{folder: mod_items.ItemEdit}`)."""
        items = getattr(self.state, "items", None)
        if items is None:
            items = self.state.items = {}
        return items

    def in_items(self) -> bool:
        """Whether the Items tab is shown."""
        return self.tabs.currentIndex() == 2

    def show_items(self, folder: Optional[str] = None) -> None:
        """The Items tab shown, the item in `folder` picked when given."""
        if folder is not None:
            self.item_pick = folder
        if not self.in_items():
            self.tabs.setCurrentIndex(2)
        else:
            self._tab_changed(2)

    def _picked_item(self) -> Optional[mi.ItemEdit]:
        return self.items_store().get(self.item_pick) if self.item_pick else None

    def _fill_items(self) -> None:
        """The Items tab's list: the mod's items, each its name over its kind and the towns of the mod's that sell
        it."""
        items, places = self.items_store(), self.places_store()
        if self.item_pick not in items:
            self.item_pick = next(iter(items), None)
        self.item_list.blockSignals(True)
        self.item_list.clear()
        for folder, edit in items.items():
            towns = pe.towns_selling_item(places, edit.item.name)
            kind = mi.KIND_WORDS[edit.item.kind]
            kind = kind[:1].upper() + kind[1:]
            # (1.27.0) And the game's towns ticked on its card.
            count = len(edit.item.shops)
            line = (ITEM_LIST_LINE["both"].format(kind=kind, towns=_listed(towns), count=count) if towns and count
                    else ITEM_LIST_LINE["towns"].format(kind=kind, towns=_listed(towns)) if towns
                    else ITEM_LIST_LINE["game"].format(kind=kind, count=count) if count
                    else ITEM_LIST_LINE["none"].format(kind=kind))
            entry = QListWidgetItem(f"{edit.item.name}\n{line}")
            entry.setData(Qt.UserRole, folder)
            self.item_list.addItem(entry)
            if folder == self.item_pick:
                self.item_list.setCurrentItem(entry)
        self.item_list.blockSignals(False)
        self.remove_item_button.setEnabled(self.item_pick is not None)
        self._filter_items(self.item_search.text())

    def _filter_items(self, text: str) -> None:
        wanted = text.strip().lower()
        for n in range(self.item_list.count()):
            entry = self.item_list.item(n)
            entry.setHidden(bool(wanted) and wanted not in entry.text().lower())

    def _item_list_picked(self, entry, _previous=None) -> None:
        if entry is None:
            return
        self.item_pick = entry.data(Qt.UserRole)
        self.remove_item_button.setEnabled(True)
        self._say("")
        self._show_card()
        self._show_middle()

    def _items_changed(self, refill: bool = True) -> None:
        """After an item changed: the list, the card, the world map; Export's summary."""
        if refill:
            self._fill_items()
        self._show_card()
        self._show_middle()
        self.edits_changed.emit()

    def game_items(self) -> tuple:
        """(the game's items read from its program, `mod_items.GameItems`, or None; why not, in words)."""
        path = self.find_program()
        if path is None:
            return None, NO_PROGRAM
        try:
            return mi.game_items(path), ""
        except (OSError, mi.ItemsError) as exc:
            return None, str(exc)

    def _game_item_choices(self) -> list:
        """`[(number, words)]`: the game's items an item may start as a copy of (1 to 253, 256 to 260), by name."""
        names = nxd_names(self.state, "item")
        return [(n, f"{names.get(n) or n} ({n})") for n in mi.GAME_ITEMS]

    def _game_words(self, number: int) -> dict:
        """The game item's row of the Item table (as Mod Studio has the game's, in English): its words, its UI
        category and sort, or {}."""
        path = getattr(self.state, "nxd_sqlite_path", None)
        if not path:
            return {}
        try:
            rows = nxd_data.read_item_table(Path(path), "en")
        except Exception:                                             # noqa: BLE001
            return {}
        row_ = next((r for r in rows if r.key == number), None)
        return dict(row_.values) if row_ is not None else {}

    def new_item_categories(self, game) -> list:
        """(Zodi after test 62) The categories a new item may be: `[(category, its words, the game's first item of it,
        that item's name, (its palette, its sprite))]`, in the categories' order (`mod_items.first_of_categories`: no
        items to use for now, 1.27.0)."""
        from ..widgets.field_rows import split_words
        names = nxd_names(self.state, "item")
        out = []
        for category, number in mi.first_of_categories(game):
            words = split_words(c.ITEM_CATEGORIES[category]) if 0 <= category < len(c.ITEM_CATEGORIES) else str(category)
            out.append((category, words, number, names.get(number) or ITEM_NUMBERED.format(n=number),
                        mi.held(game.item(number))))
        return out

    def new_item(self) -> None:
        """New item: (Zodi after test 62) its name, its category and its Sprite and Palette asked; it starts as the
        game's first item of its category, its icon in battle the one picked."""
        items = self.items_store()
        game, why = self.game_items()
        if game is None:
            self._say(NO_GAME_ITEMS.format(problem=why))
            return
        name = mi.free_name("New Item", [e.item.name for e in items.values()])

        def problem(n, _base) -> str:
            return self._item_name_problem(n)
        dialog = ItemDialog(self, name, self.new_item_categories(game), self.battle_sprites(), problem)
        answer = self._ask("new_item", lambda: dialog.answer() if dialog.exec() == QDialog.Accepted else None)
        if not answer:
            return
        # Its name and the game's item it starts as; its Sprite and Palette when picked (else that item's).
        name, number = answer[0], answer[1]
        picked_held = tuple(answer[2:4]) if len(answer) >= 4 else None
        said = self._item_name_problem(name)
        if said:
            self._say(said)
            return
        try:
            made = game.item(int(number))
        except (ValueError, TypeError, mi.ItemsError) as exc:
            self._say(NO_GAME_ITEMS.format(problem=exc))
            return
        if made.kind == mi.ITEM:
            self._say(NO_ITEMS_TO_USE)
            return
        words = self._game_words(int(number))
        category = words.get("UiItemCategoryId")
        sort = words.get("SortOrder")
        item = mi.copy_of(made, name, words, category if isinstance(category, int) else -1,
                          sort if isinstance(sort, int) else -1)
        if picked_held is not None:
            mi.set_held(item, *picked_held)
        folder = mi.folder_for(name)
        items[folder] = mi.ItemEdit(folder, item, made.number)
        self.item_pick = folder
        self._say("")
        self.show_items(folder)
        self._items_changed()

    @staticmethod
    def _copyable(game, number: int) -> bool:
        """(1.27.0) Whether a new item may start as a copy of the game's item `number`: any but an item to use."""
        try:
            return game.item(number).kind != mi.ITEM
        except mi.ItemsError:
            return False

    def _item_name_problem(self, name: str, own: Optional[mi.ItemEdit] = None) -> str:
        if not mi.good_name(name):
            return ITEM_NAME_BAD
        folder = mi.folder_for(name).lower()
        if any(e is not own and (e.item.name == name or mi.folder_for(e.item.name).lower() == folder)
               for e in self.items_store().values()):
            return ITEM_TAKEN.format(name=name)
        return ""

    def remove_item(self) -> None:
        """Remove: the item picked, asked first; no Outfitter of the mod's sells it after."""
        edit = self._picked_item()
        if edit is None:
            return
        towns = pe.towns_selling_item(self.places_store(), edit.item.name)
        question = ITEM_REMOVE_ASK.format(name=edit.item.name)
        if towns:
            question += ITEM_REMOVE_TOWNS.format(towns=_listed(towns))
        sure = self._ask("remove_item", lambda: QMessageBox.question(self, TITLE, question) == QMessageBox.Yes)
        if not sure:
            return
        pe.item_removed(self.places_store(), edit.item.name)
        self.items_store().pop(edit.folder, None)
        self.item_pick = next(iter(self.items_store()), None)
        self._say("")
        self._items_changed()

    def _item_problems(self, edit: mi.ItemEdit) -> list:
        """What Mod Studio Framework would say of the item as Export writes it (its own icon's files written with it)."""
        written = mi.written_item(edit, "x")
        _item, problems = mi.read_item_text(mi.item_text(written), lambda _path: True)
        return problems

    def _item_card(self) -> CardPane:
        """An item's card: its name, kind, words, numbers, price, the story point it is sold from, (1.27.0) what a
        weapon does, its equipment bonuses with their statuses and elements, its UI values, its two icons and the towns
        that sell it (the mod's and the game's ticked)."""
        edit = self._picked_item()
        if edit is None:
            card = CardPane(ITEM_BAND, "", ITEM_COLOR, "", PICK_AN_ITEM if self.items_store() else "")
            card.status([], "")
            return card
        item = edit.item
        category_words = self._category_words(item)
        card = CardPane(ITEM_BAND, ITEM_CATEGORY_BAND.format(category=category_words), ITEM_COLOR, item.name,
                        ITEM_BLURB)
        name = QLineEdit(item.name)
        name.setMaxLength(64)
        name.setToolTip(ITEM_NAME_TIP)
        name.editingFinished.connect(lambda box=name: self.rename_item(box.text()))
        kind = mi.KIND_WORDS[item.kind]
        card.field(NAME, name)
        kind_words = ITEM_KIND_WORDS.format(kind=kind[:1].upper() + kind[1:], category=category_words)
        if item.kind == mi.ITEM:
            # (1.27.0) Kept, as Zodi chose: read and sold, its card saying why no new one is made.
            card.field(KIND, muted(kind_words), muted(ITEM_TO_USE_NOTE))
        else:
            card.field(KIND, muted(kind_words))
        singular, plural = QLineEdit(item.singular), QLineEdit(item.plural)
        for box, key in ((singular, "singular"), (plural, "plural")):
            box.setMaxLength(mi.WORD_MOST)
            box.editingFinished.connect(lambda b=box, k=key: self.set_item_word(k, b.text()))
        description = QPlainTextEdit(item.description)
        description.setFixedHeight(90)
        description.textChanged.connect(lambda box=description: self.set_item_word("description",
                                                                                     box.toPlainText(), False))
        card.field(ITEM_WORDS, pair((SINGULAR, singular), (PLURAL, plural)), caption(DESCRIPTION), description)
        numbers = []
        for label, where, at, width, most in mi.NUMBERS[item.kind]:
            box = spin(mi.number(item, where, at, width), 0, most)
            box.valueChanged.connect(lambda v, w=where, a=at, n=width: self.set_item_number(w, a, n, v))
            self.field_widgets[f"item_{label}"] = box
            numbers.append((label, box))
        rows_ = [pair(numbers[n], numbers[n + 1] if n + 1 < len(numbers) else None)
                 for n in range(0, len(numbers), 2)]
        card.field(ITEM_NUMBERS, *rows_)
        if item.kind == mi.WEAPON:
            self._attack_field(card, item)
        # (Zodi, 4 November) Its battle sprite, each half with what changes it under it: Attack and Held or thrown.
        self._battle_sprite_field(card, item)
        _label, where, at, width, most = mi.PRICE
        price = spin(mi.number(item, where, at, width), 0, most)
        price.valueChanged.connect(lambda v, w=where, a=at, n=width: self.set_item_number(w, a, n, v))
        card.field(PRICE_FIELD, row(price, QWidget(), stretch_first=False))
        points = [(n, SOLD_FROM_POINTS.get(n, str(n))) for n in range(1, mi.MOST_SHOP_POINT + 1)]
        sold_from = combo(points, mi.shop_point(item))
        sold_from.currentIndexChanged.connect(lambda _i, b=sold_from: self.set_item_shop_point(b.currentData()))
        if item.kind != mi.ITEM:
            bonuses = []
            for label, where, at, width, most in mi.BONUSES:
                box = spin(mi.number(item, where, at, width), 0, most)
                box.valueChanged.connect(lambda v, a=at: self.set_item_number("bonus", a, 1, v))
                self.field_widgets[f"item_{label}"] = box
                bonuses.append((label, box))
            # (1.27.0) Its statuses and elements too, each set's names in words, ticked in a dialog.
            ticked = []
            for which, label in enumerate(BONUS_STATUS_LABELS):
                ticked.append(self._ticked_row("status", which, label, mi.bonus_statuses(item, which)))
            for which, label in enumerate(BONUS_ELEMENT_LABELS):
                ticked.append(self._ticked_row("element", which, label, mi.bonus_elements(item, which)))
            card.field(BONUSES_FIELD, *[pair(bonuses[n], bonuses[n + 1] if n + 1 < len(bonuses) else None)
                                        for n in range(0, len(bonuses), 2)], *ticked)
        # (1.27.0) Its UI values, set from what it does (Zodi's choice: automatically, shown); why, in their tooltip.
        ui_words = muted("")
        ui_words.setToolTip(UI_NOTE)
        self.field_widgets["item_ui_words"] = ui_words
        self._show_ui_words(item)
        card.field(UI_FIELD, ui_words)
        self._icon_field(card, edit)
        towns = pe.towns_selling_item(self.places_store(), item.name)
        # (1.27.0) The game's towns' Outfitters ticked (Zodi's choice: none ticked to start).
        game_towns = QWidget()
        towns_column = QVBoxLayout(game_towns)
        towns_column.setContentsMargins(0, 0, 0, 0)
        towns_column.setSpacing(2)
        town_boxes = []
        for town, town_name in enumerate(mi.GAME_TOWNS):
            box = QCheckBox(town_name)
            box.setChecked(town in item.shops)
            box.toggled.connect(lambda on, t=town: self.set_item_town(t, on))
            towns_column.addWidget(box)
            town_boxes.append(box)
        # (Zodi after test 62) The point of the story it is sold from, beside where it is sold; (4 November) the towns
        # of yours, then the game's ticked, then the point, without the notes their names and choices say already.
        card.field(SOLD_AT_FIELD, muted(_listed(towns) + "." if towns else SOLD_AT_NO_TOWN), game_towns,
                   caption(SOLD_FROM), sold_from)
        self.field_widgets.update(item_name=name, item_singular=singular, item_plural=plural,
                                  item_description=description, item_price=price, item_sold_from=sold_from,
                                  item_game_towns=town_boxes)
        card.status(self._item_problems(edit))
        return card

    def _attack_field(self, card: CardPane, item: mi.ModItem) -> None:
        """(1.27.0) A weapon's formula, its Inflict Status (or the spell it casts) and its elements."""
        formulas = reference_names.formula_names()
        formula = combo([(n, f"{formulas[n]} ({n})") for n in sorted(formulas) if 0 <= n <= 255], mi.formula(item))
        formula.currentIndexChanged.connect(lambda _i, b=formula: self.set_item_formula(b.currentData()))
        inflict_caption = caption("")
        inflict = combo([])
        self.field_widgets.update(item_formula=formula, item_inflict=inflict, item_inflict_caption=inflict_caption)
        self._fill_inflict(item)
        inflict.currentIndexChanged.connect(lambda _i, b=inflict: self.set_item_inflict(b.currentData()))
        elements = QWidget()
        grid = QGridLayout(elements)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(2)
        boxes = []
        ticked = mi.weapon_elements(item)
        for n, element in enumerate(c.ELEMENT_FLAGS):
            box = QCheckBox(element)
            box.setChecked(element in ticked)
            box.toggled.connect(lambda _on: self.set_item_elements([b.text() for b in boxes if b.isChecked()]))
            grid.addWidget(box, n // 4, n % 4)
            boxes.append(box)
        self.field_widgets["item_elements"] = boxes
        card.field(ATTACK_FIELD, caption(FORMULA_LABEL), formula, inflict_caption, inflict, caption(WEAPON_ELEMENTS),
                   elements)

    def _category_words(self, item: mi.ModItem) -> str:
        """(Zodi after test 62) Its category as the Items page names it."""
        from ..widgets.field_rows import split_words
        category = item.record[mi.CATEGORY_AT]
        return split_words(c.ITEM_CATEGORIES[category]) if 0 <= category < len(c.ITEM_CATEGORIES) else str(category)

    def _item_looks(self, item: mi.ModItem):
        """The looks a weapon may swing (`mod_items.looks_of`: the game's weapons whose swings share its frames), or
        (5 November) a shield guard with (the game's shields'), or None and why not."""
        game, why = self.game_items()
        if game is None:
            return None, why
        try:
            return mi.looks_of(game, item.record[mi.CATEGORY_AT]), ""
        except mi.ItemsError as exc:
            return None, str(exc)

    @staticmethod
    def _show_picture(label, picture, width: int, height: int, tip: str) -> None:
        """A battle sprite drawn into `label` (a whole number of times its size, or a
        whole number of times smaller), named by its tooltip; hidden when there is none."""
        if label is None:
            return
        if picture is None:
            label.clear()
            label.setVisible(False)
            return
        image = QImage(picture.rgba, picture.width, picture.height, picture.width * 4, QImage.Format_RGBA8888).copy()
        across, down = max(1, picture.width), max(1, picture.height)
        if across <= width and down <= height:
            times = min(width // across, height // down)
            size = (across * times, down * times)
        else:
            parts = max(-(-across // width), -(-down // height))
            size = (max(1, across // parts), max(1, down // parts))
        label.setPixmap(QPixmap.fromImage(image.scaled(size[0], size[1], Qt.IgnoreAspectRatio,
                                                       Qt.FastTransformation)))
        label.setToolTip(tip)
        label.setVisible(True)

    def _refresh_item_pictures(self, item: mi.ModItem) -> None:
        """(Zodi after test 62: "changing a new items palette ... does not update its appearance in the preview") Its
        battle sprite's two halves drawn again as the item has them now, each named in its tooltip (the look's game
        weapon and palette, the icon's sprite and palette), and the palettes beside them following."""
        from ... import unit_sprites as us
        sprites = self.battle_sprites()
        category = item.record[mi.CATEGORY_AT]
        flags = {mi.WEAPON: {"Weapon"}, mi.SHIELD: {"Shield"}}.get(item.kind, set())
        kind = us.sprite_kind(flags, category)
        look = None
        if sprites is not None and kind in ("attack", "guard") and len(item.sprite_pair) == mi.PAIR_BYTES:
            look = sprites.attack(us.frames_type(kind, category), bytes(item.sprite_pair))
        palette, sprite = mi.held(item)
        held = sprites.held(palette, sprite) if sprites is not None else None
        name = BATTLE_ATTACK if kind == "attack" else BATTLE_GUARD
        if item.kind in (mi.WEAPON, mi.SHIELD):
            looks, _why = self._item_looks(item)
            names = nxd_names(self.state, "item")
            # (Zodi, 4 November: "many of them share the same design") Every one of the game's weapons that shares
            # its look, by name.
            name = look_words(mi.look_group(looks or [], bytes(item.sprite_pair)),
                              lambda n: names.get(n) or ITEM_NUMBERED.format(n=n), mi.battle_palette(item))
        self._show_picture(self.field_widgets.get("item_battle_look"), look, 144, 96, name)
        self._show_picture(self.field_widgets.get("item_battle_held"), held, 64, 64,
                           HELD_PICKED.format(sprite=sprite, palette=palette))
        for key, value in (("item_palette", mi.battle_palette(item)), ("item_held_palette", palette)):
            box = self.field_widgets.get(key)
            if box is None or value < 0 or box.currentData() == value:
                continue
            box.blockSignals(True)
            index = box.findData(value)
            if index < 0:
                box.addItem(PALETTE_CHOICE.format(n=value), value)
                index = box.count() - 1
            box.setCurrentIndex(index)
            box.blockSignals(False)
        choose = self.field_widgets.get("item_choose_held")
        if choose is not None:
            choose.setEnabled(sprites is not None and sprites.items_drawable)

    def choose_item_look(self) -> None:
        """(Zodi after test 62) Choose a look: the looks that swing the same way, drawn in the palette chosen
        (`LookDialog`); the look and palette taken."""
        from ... import unit_sprites as us
        edit = self._picked_item()
        if edit is None:
            return
        looks, _why = self._item_looks(edit.item)
        if not looks:
            return
        names = nxd_names(self.state, "item")
        category = edit.item.record[mi.CATEGORY_AT]
        # (Zodi, 4 November) Each look once, under the weapon type it is drawn for.
        game, _why = self.game_items()
        categories = {n: game.item(n).record[mi.CATEGORY_AT] for n, _pair in looks} if game is not None else None
        # (Zodi, 5 November: "Make sure you can also change the look in the New Items card") A shield's as it guards.
        guard = edit.item.kind == mi.SHIELD
        dialog = LookDialog(self, self.battle_sprites(), us.frames_type("guard" if guard else "attack", category),
                            looks, names, mi.look_now(looks, edit.item.sprite_pair), mi.battle_palette(edit.item),
                            edit.item.name, categories=categories, pair=bytes(edit.item.sprite_pair), guard=guard)
        answer = self._ask("item_look", lambda: dialog.choice() if dialog.exec() == QDialog.Accepted else None)
        if not answer:
            return
        number, palette = answer
        self.set_item_look(number)
        if palette is not None:
            self.set_item_palette(palette)

    def choose_item_held(self) -> None:
        """(Zodi after test 62) Choose an icon: the enhanced item texture's icons in the palette chosen, as the Items
        page's (`items.HeldSpriteDialog`)."""
        from .items import HeldSpriteDialog
        edit = self._picked_item()
        if edit is None:
            return
        palette, sprite = mi.held(edit.item)
        dialog = HeldSpriteDialog(self.battle_sprites(), palette, sprite, edit.item.name, self)
        answer = self._ask("item_held", lambda: dialog.choice() if dialog.exec() else None)
        if not answer:
            return
        self.set_item_held(*answer)

    def set_item_held(self, palette, sprite) -> None:
        """(Zodi after test 62) The icon a unit holds up or throws in battle: its palette and its sprite."""
        edit = self._picked_item()
        if edit is None or self._building or palette is None or sprite is None:
            return
        mi.set_held(edit.item, int(palette), int(sprite))
        self._refresh_item_pictures(edit.item)
        self.edits_changed.emit()

    def set_item_held_palette(self, palette) -> None:
        edit = self._picked_item()
        if edit is None or self._building or palette is None:
            return
        self.set_item_held(palette, mi.held(edit.item)[1])

    def _fill_inflict(self, item: mi.ModItem) -> None:
        """The row under a weapon's formula: its Inflict Status, or with the formula that casts a spell, the spell (the
        Items page's choices: the Inflict Status rows as that page names them, the abilities by their names)."""
        box, label = self.field_widgets.get("item_inflict"), self.field_widgets.get("item_inflict_caption")
        if box is None or label is None:
            return
        value = mi.inflict(item)
        if mi.casts_spell(item):
            from ..app import ability_choices
            named = ability_choices(self.state)
            choices = [(n, f"{named[n]} ({n})") for n in sorted(named) if 0 <= n <= 255]
            label.setText(CAST_LABEL)
        else:
            from .table_editor import inflict_status_descriptor
            records = (getattr(self.state, "item_table_records", None) or {}).get("item_options", [])
            edits = (getattr(self.state, "item_table_edits", None) or {}).get("item_options", {})
            choices = [(r.item_id, f"{inflict_status_descriptor({**r.values, **edits.get(r.item_id, {})})} "
                                   f"({r.item_id})") for r in records if 0 <= r.item_id <= 255]
            if not choices:
                choices = [(n, str(n)) for n in range(256)]
            label.setText(INFLICT_LABEL)
        box.blockSignals(True)
        box.clear()
        for data, words in choices:
            box.addItem(words, data)
        index = box.findData(value)
        if index < 0:
            box.addItem(str(value), value)
            index = box.count() - 1
        box.setCurrentIndex(index)
        box.blockSignals(False)

    def _ticked_row(self, kind: str, which: int, label: str, names: list) -> QWidget:
        """(1.27.0) One of its bonus row's sets in words (a status the game names Unused kept but not said), and
        Change, which ticks them in a dialog."""
        words = muted(TICKED_LINE.format(label=label, names=_listed(_said(names)) or TICKED_NONE))
        change = QPushButton(CHANGE)
        change.clicked.connect(lambda _c=False, k=kind, w=which: self.change_item_ticks(k, w))
        self.field_widgets[f"item_{kind}_{which}"] = words
        self.field_widgets[f"item_{kind}_{which}_change"] = change
        return row(words, change)

    def _show_ui_words(self, item: mi.ModItem) -> None:
        """(1.27.0) Its UI values in words, as Export writes them (`mod_items.ui_values`)."""
        label = self.field_widgets.get("item_ui_words")
        if label is None:
            return
        ui_status, random_damage = mi.ui_values(item)
        if item.ui_category >= 0 and item.sort >= 0:
            listed = UI_LISTED_WORDS["copy"].format(category=item.ui_category, sort=item.sort)
        else:
            category = item.ui_category if item.ui_category >= 0 else UI_CATEGORY_OF_KIND[item.kind]
            listed = UI_LISTED_WORDS["own"].format(category=category)
        lines = [listed]
        if item.kind == mi.WEAPON:
            lines = [UI_STATUS_WORDS.get(ui_status, UI_STATUS_WORDS[0]), UI_RANDOM_WORDS[random_damage], listed]
        label.setText("\n".join(lines))

    def _icon_field(self, card: CardPane, edit: mi.ItemEdit) -> None:
        """Its icon: (Zodi, 4 November: "we already have a better user interface for new users from the Items page where
        you can simply right click the art or sprite texture and have a context menus with options and to place the
        users image. You should still be able to cycle through the games items icons though that's a good feature")
        the game's item whose icon it uses, picked in a list, and its two textures as the Items page shows them, each
        with its menu on a right click (`texture_menu`): an image of your own in its place (its art fitted to 100 by
        100, its small icon to 48 by 48, made from its art until one of its own is chosen), its small icon made from
        its art again, the game's icon again, either saved as a PNG."""
        own = bool(edit.icon_png)
        choices = self._game_item_choices()
        if own:
            choices = [(-1, OWN_TEXTURES)] + choices
        shown = combo(choices, -1 if own else self._game_icon_number(edit), enabled=not own)
        shown.currentIndexChanged.connect(lambda _i, b=shown: self.set_game_icon(b.currentData()))
        panels, problems = [], []
        for which, title, size in (("art", ART_TEXTURE_TIP, 96), ("small", SPRITE_TEXTURE_TIP, 48)):
            image, why = self._item_texture_image(edit, which)
            if why:
                problems.append(why)
            box, view = self._texture_panel(title, image, size, which)
            panels.append(box)
            self.field_widgets[f"item_{which}_texture"] = view
        icon_said = muted(GAME_ICON_MISSING.format(problem="; ".join(dict.fromkeys(problems)))
                          if problems and not own else "")
        icon_said.setVisible(bool(problems) and not own)
        card.field(ICON_FIELD, shown, row(*panels, QWidget(), stretch_first=False), icon_said, muted(ICON_HINT))
        self.field_widgets.update(item_icon=shown, item_icon_said=icon_said)

    def _game_icon_number(self, edit: mi.ItemEdit) -> int:
        """The game's item whose icon it uses (or would, once its own textures are put aside)."""
        return edit.item.icon if edit.item.icon in mi.GAME_ITEMS else edit.copied_from or 1

    def _item_texture_image(self, edit: mi.ItemEdit, which: str) -> tuple:
        """(4 November) Its art (`which` "art") or its small icon ("small") as it has it now, a QImage: its own (the
        small one made from its art until one of its own is chosen), else the game's item's texture; (None, why) when
        the game's can't be read."""
        from ... import texture_data as td
        if edit.icon_png:
            png = edit.icon_png if which == "art" else (edit.small_png or self._small_made(edit))
            image = QImage.fromData(png)
            return (image, "") if not image.isNull() else (None, "")
        number = self._game_icon_number(edit)
        relative = td.item_art_texture_path(number) if which == "art" else td.item_sprite_texture_path(number)
        return self._game_texture(relative)

    def _texture_panel(self, title: str, image, size: int, which: str) -> tuple:
        """A texture as the Items page's slots show one: framed, its name over it, shrunk to `size` (never magnified),
        its menu on a right click. (Zodi, 4 November: "the Art Texture and Sprite Texture are not centered ... also
        right clicking anywhere in it's preview box should bring up the context menu not just directly on the image")
        The texture in the middle of the room under its name, and the menu on a right click anywhere in its panel.
        (The panel, its picture.)"""
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        inner = QVBoxLayout(box)
        inner.setContentsMargins(6, 4, 6, 4)
        inner.setSpacing(2)
        inner.addWidget(caption(title))
        view = QLabel()
        view.setAlignment(Qt.AlignCenter)
        view.setFixedSize(max(size, 64), size)
        view.setToolTip(title)
        if image is not None and not image.isNull():
            shown = image if image.width() <= size and image.height() <= size else image.scaled(
                size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            view.setPixmap(QPixmap.fromImage(shown))
        else:
            view.setText(NO_TEXTURE)
        for source in (box, view):
            source.setContextMenuPolicy(Qt.CustomContextMenu)
            source.customContextMenuRequested.connect(
                lambda point, s=source, w=which: self.texture_menu(w).exec(s.mapToGlobal(point)))
        inner.addStretch(1)
        inner.addWidget(view, 0, Qt.AlignHCenter)
        inner.addStretch(1)
        return box, view

    def texture_menu(self, which: str) -> QMenu:
        """(4 November) Its texture's menu (`which` "art" or "small"), as the Items page's: Replace..., Make from its
        art (its own small icon only), Use the game's icon (its own textures only), Export as PNG... (what it shows)."""
        edit = self._picked_item()
        menu = QMenu(self)
        replace = menu.addAction(REPLACE_TEXTURE)
        replace.triggered.connect(lambda _c=False: self.choose_icon() if which == "art" else self.choose_small_icon())
        if which == "small":
            made = menu.addAction(MAKE_FROM_ART)
            made.setEnabled(edit is not None and bool(edit.small_png))
            made.triggered.connect(lambda _c=False: self.small_from_art())
        back = menu.addAction(USE_GAME_ICON)
        back.setEnabled(edit is not None and bool(edit.icon_png))
        back.triggered.connect(lambda _c=False: self.use_game_icon())
        menu.addSeparator()
        export = menu.addAction(EXPORT_TEXTURE)
        export.setEnabled(edit is not None and self._item_texture_image(edit, which)[0] is not None)
        export.triggered.connect(lambda _c=False: self.export_item_texture(which))
        return menu

    def _game_texture(self, relative: str):
        """One of the unpacked game's textures as a QImage, decoded once for each file's size and time (as the Items
        page's texture slots decode theirs), or (None, why)."""
        from ... import texture_data as td
        root = getattr(self.state, "nxd_unpack_dir", None)
        if not root or not Path(root).is_dir():
            return None, "it isn't set"
        path = Path(root) / relative
        try:
            stat = path.stat()
        except OSError:
            return None, f"{path.name} isn't there"
        key = (str(path), stat.st_size, stat.st_mtime_ns)
        cache = self.__dict__.setdefault("_game_textures", {})
        if key not in cache:
            try:
                image = td.load_game_texture_preview(path, getattr(self.state, "ff16tools_cli_path", None),
                                                     paths.local_data_dir() / "texture_preview_cache")
                image = image.convert("RGBA")
                cache[key] = (QImage(image.tobytes(), image.width, image.height, image.width * 4,
                                     QImage.Format_RGBA8888).copy(), "")
            except Exception as exc:                          # noqa: BLE001
                cache[key] = (None, f"{path.name} couldn't be read ({exc})")
        return cache[key]

    def battle_sprites(self):
        """The unpacked game's battle sprites (`unit_sprites.BattleSprites`, as the Items page's), read again when
        its files change."""
        from ... import unit_sprites as us
        root = getattr(self.state, "nxd_unpack_dir", None)
        game = Path(root) if root and Path(root).is_dir() else None
        if game is None:
            return None

        def stamp(path):
            try:
                return path.stat().st_mtime_ns
            except OSError:
                return None
        key = (str(game), stamp(game / us.WEAPON_SPR_FILE), stamp(game / us.ITEM_BIN_FILES[0]),
               stamp(game / us.G2D_FILE))
        if key != self.__dict__.get("_battle_sprites_key"):
            self._battle_sprites, self._battle_sprites_key = us.BattleSprites(game), key
        return self._battle_sprites

    def _battle_sprite_field(self, card: CardPane, item: mi.ModItem) -> None:
        """(after test 61) Its Battle Sprite: as it attacks or guards (its sprite pair, by its type's frames), and as
        a unit holds it up or throws it (its record's palette and sprite: the enhanced item texture's icon). (Zodi, 4
        November: "Together, named by half. Both side by side with the Battle Sprite, one named Attack and one Held or
        thrown, each changing only its half. Also make sure the field options to change them appear next to each
        other") Each half named under it, and under that what changes it: a weapon's palette (one the game's own
        weapons swing in) and Choose a look; any item's palette and Choose an icon. (5 November) A shield's look as it
        guards chosen the same way, from the game's shields'."""
        from ... import unit_sprites as us
        sprites = self.battle_sprites()
        category = item.record[mi.CATEGORY_AT]
        flags = {mi.WEAPON: {"Weapon"}, mi.SHIELD: {"Shield"}}.get(item.kind, set())
        kind = us.sprite_kind(flags, category)
        problems, undrawn = [], []
        if sprites is None:
            problems.append("it isn't set")
        else:
            if kind in ("attack", "guard") and len(item.sprite_pair) == mi.PAIR_BYTES:
                if sprites.attack(us.frames_type(kind, category), bytes(item.sprite_pair)) is None:
                    (undrawn if sprites.weapons_drawable else problems).append(sprites.problem)
            if sprites.held(*mi.held(item)) is None:
                (undrawn if sprites.items_drawable else problems).append(sprites.item_problem)
        halves = QWidget()
        grid = QGridLayout(halves)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)
        column = 0
        if kind in ("attack", "guard"):
            look = QLabel()
            look.setFixedSize(144, 96)
            look.setAlignment(Qt.AlignCenter)
            grid.addWidget(look, 0, column, Qt.AlignLeft | Qt.AlignBottom)
            grid.addWidget(caption(BATTLE_ATTACK if kind == "attack" else BATTLE_GUARD), 1, column)
            self.field_widgets["item_battle_look"] = look
            # (Zodi, 5 November) A shield's look as it guards, chosen as a weapon's is.
            if item.kind in (mi.WEAPON, mi.SHIELD):
                looks, why = self._item_looks(item)
                if looks is None:
                    grid.addWidget(muted(NO_LOOKS.format(problem=why)), 2, column, 2, 1)
                else:
                    palette = swing_palette_box(max(0, mi.battle_palette(item)))
                    palette.currentIndexChanged.connect(lambda _i, b=palette: self.set_item_palette(b.currentData()))
                    choose = QPushButton(LOOK_CHOOSE)
                    choose.clicked.connect(lambda _c=False: self.choose_item_look())
                    grid.addWidget(palette, 2, column, Qt.AlignLeft)
                    grid.addWidget(choose, 3, column, Qt.AlignLeft)
                    self.field_widgets.update(item_palette=palette, item_choose_look=choose)
            column += 1
        held = QLabel()
        held.setFixedSize(64, 64)
        held.setAlignment(Qt.AlignCenter)
        grid.addWidget(held, 0, column, Qt.AlignLeft | Qt.AlignBottom)
        grid.addWidget(caption(BATTLE_HELD), 1, column)
        self.field_widgets["item_battle_held"] = held
        if item.kind != mi.ITEM:
            palette_now, _sprite = mi.held(item)
            palette = palette_combo(palette_now)
            palette.currentIndexChanged.connect(lambda _i, b=palette: self.set_item_held_palette(b.currentData()))
            choose = QPushButton(HELD_CHOOSE)
            choose.clicked.connect(lambda _c=False: self.choose_item_held())
            grid.addWidget(palette, 2, column, Qt.AlignLeft)
            grid.addWidget(choose, 3, column, Qt.AlignLeft)
            self.field_widgets.update(item_held_palette=palette, item_choose_held=choose)
        grid.setColumnStretch(column + 1, 1)
        said = muted(" ".join([BATTLE_SPRITE_MISSING.format(problem=p) for p in dict.fromkeys(q for q in problems if q)]
                              + [BATTLE_SPRITE_UNDRAWN.format(problem=p) for p in dict.fromkeys(q for q in undrawn if q)]))
        said.setVisible(bool(said.text()))
        card.field(BATTLE_SPRITE_FIELD, halves, said)
        self.field_widgets["item_battle_said"] = said
        self._refresh_item_pictures(item)

    @staticmethod
    def _small_made(edit: mi.ItemEdit) -> bytes:
        """The small icon Export makes from its art (`mod_items.small_of`), as a PNG, or nothing without its art."""
        if not edit.icon_png:
            return b""
        import io

        from PIL import Image
        return mi.icon_png(mi.small_of(Image.open(io.BytesIO(edit.icon_png))), mi.SMALL_ICON_SIZE)

    def rename_item(self, name: str) -> None:
        edit = self._picked_item()
        if edit is None or self._building or name == edit.item.name:
            return
        said = self._item_name_problem(name, edit)
        if said:
            self._say(said)
            self._show_card()
            return
        old = edit.item.name
        mi.rename(edit, name)
        pe.item_renamed(self.places_store(), old, name)
        # Its folder is its name's.
        items = self.items_store()
        folder = mi.folder_for(name)
        if folder != edit.folder:
            self.state.items = {(folder if f == edit.folder else f): e for f, e in items.items()}
            edit.folder = folder
            self.item_pick = folder
        self._say("")
        self._items_changed()

    def set_item_word(self, key: str, text: str, show: bool = True) -> None:
        """One of the item's words (its singular, plural or description); none given its name's."""
        edit = self._picked_item()
        if edit is None or self._building:
            return
        if key == "description":
            edit.item.description = text
        else:
            setattr(edit.item, key, text or edit.item.name)
        if show:
            self._items_changed(refill=False)
        else:
            if self.card is not None:
                self.card.status(self._item_problems(edit))
            self.edits_changed.emit()

    def set_item_number(self, where: str, at: int, width: int, value: int) -> None:
        edit = self._picked_item()
        if edit is None or self._building:
            return
        mi.set_number(edit.item, where, at, width, int(value))
        if self.card is not None:
            self.card.status(self._item_problems(edit))
        self.edits_changed.emit()

    def set_item_formula(self, value) -> None:
        """(1.27.0) A weapon's formula: the row under it its Inflict Status or the spell it casts as the formula has
        it, its UI values with it."""
        edit = self._picked_item()
        if edit is None or self._building or value is None:
            return
        mi.set_formula(edit.item, int(value))
        self._fill_inflict(edit.item)
        self._show_ui_words(edit.item)
        if self.card is not None:
            self.card.status(self._item_problems(edit))
        self.edits_changed.emit()

    def set_item_look(self, number) -> None:
        """(1.27.0) A weapon's look in battle that of the game's weapon `number` (its picture and palettes), its
        palette's choice following it; (5 November) a shield's that of the game's shield `number`."""
        edit = self._picked_item()
        if edit is None or self._building or not number:
            return
        game, _why = self.game_items()
        if game is None:
            return
        looks = dict(mi.looks_of(game, edit.item.record[mi.CATEGORY_AT]))
        if int(number) not in looks:
            return
        mi.set_battle_look(edit.item, looks[int(number)])
        # (Zodi after test 62) Its battle sprite, its look and their words drawn again.
        self._refresh_item_pictures(edit.item)
        self.edits_changed.emit()

    def set_item_palette(self, palette) -> None:
        """(1.27.0) A weapon's (or, 5 November, a shield's) palette in battle (0 to 15), its picture as it was."""
        edit = self._picked_item()
        if edit is None or self._building or palette is None:
            return
        mi.set_battle_palette(edit.item, int(palette))
        # (Zodi after test 62: "changing a new items palette ... does not update its appearance in the preview")
        self._refresh_item_pictures(edit.item)
        self.edits_changed.emit()

    def set_item_inflict(self, value) -> None:
        edit = self._picked_item()
        if edit is None or self._building or value is None:
            return
        mi.set_inflict(edit.item, int(value))
        self.edits_changed.emit()

    def set_item_elements(self, names: list) -> None:
        """(1.27.0) A weapon's elements."""
        edit = self._picked_item()
        if edit is None or self._building:
            return
        mi.set_weapon_elements(edit.item, names)
        self.edits_changed.emit()

    def change_item_ticks(self, kind: str, which: int) -> None:
        """(1.27.0) One of its bonus row's sets ticked in a dialog (`kind` "status": the three sets of statuses,
        "element": the five of elements); a status the game names Unused kept as it was."""
        edit = self._picked_item()
        if edit is None:
            return
        statuses = kind == "status"
        label = (BONUS_STATUS_LABELS if statuses else BONUS_ELEMENT_LABELS)[which]
        now = mi.bonus_statuses(edit.item, which) if statuses else mi.bonus_elements(edit.item, which)
        names = [n for n in c.STATUS_FLAGS if not n.startswith("Unused")] if statuses else list(c.ELEMENT_FLAGS)
        dialog = TicksDialog(self, TICKS_TITLE.format(item=edit.item.name, label=label),
                             (STATUS_TICKS_INTRO if statuses else ELEMENT_TICKS_INTRO).format(item=edit.item.name),
                             names, now, 5 if statuses else 4)
        answer = self._ask("ticks", lambda: dialog.answer() if dialog.exec() == QDialog.Accepted else None)
        if answer is None:
            return
        if statuses:
            mi.set_bonus_statuses(edit.item, which, set(answer) | {n for n in now if n.startswith("Unused")})
        else:
            mi.set_bonus_elements(edit.item, which, answer)
        words = self.field_widgets.get(f"item_{kind}_{which}")
        if words is not None:
            ticked = mi.bonus_statuses(edit.item, which) if statuses else mi.bonus_elements(edit.item, which)
            words.setText(TICKED_LINE.format(label=label, names=_listed(_said(ticked)) or TICKED_NONE))
        if self.card is not None:
            self.card.status(self._item_problems(edit))
        self.edits_changed.emit()

    def set_item_town(self, town: int, sold: bool) -> None:
        """(1.27.0) One of the game's towns' Outfitters selling the item, or not."""
        edit = self._picked_item()
        if edit is None or self._building:
            return
        towns = set(edit.item.shops)
        (towns.add if sold else towns.discard)(int(town))
        mi.set_shops(edit.item, towns)
        self._fill_items()
        self.edits_changed.emit()

    def set_item_shop_point(self, point) -> None:
        edit = self._picked_item()
        if edit is None or self._building or point is None:
            return
        mi.set_shop_point(edit.item, int(point))
        self.edits_changed.emit()

    def set_game_icon(self, number) -> None:
        """Its icon one of the game's items' (its own, if it had one, put aside)."""
        edit = self._picked_item()
        if edit is None or self._building or number not in mi.GAME_ITEMS:
            return
        edit.item.icon = int(number)
        edit.icon_png, edit.icon_from = b"", ""
        edit.small_png, edit.small_from = b"", ""
        self._items_changed(refill=False)

    def use_game_icon(self) -> None:
        """(4 November) Use the game's icon: the game's item's icon picked in its list again, its own textures put
        aside."""
        edit = self._picked_item()
        if edit is None or self._building or not edit.icon_png:
            return
        self.set_game_icon(self._game_icon_number(edit))

    def export_item_texture(self, which: str) -> None:
        """(4 November) Export as PNG...: its art or its small icon as it shows it, saved where asked."""
        from PySide6.QtWidgets import QFileDialog
        edit = self._picked_item()
        if edit is None:
            return
        image, _why = self._item_texture_image(edit, which)
        if image is None:
            return
        title = ART_TEXTURE_TIP if which == "art" else SPRITE_TEXTURE_TIP
        path = self._ask("export_texture", lambda: QFileDialog.getSaveFileName(
            self, EXPORT_TEXTURE_TITLE.format(texture=title, item=edit.item.name),
            f"{edit.item.name} {title}.png", "PNG image (*.png)")[0])
        if path:
            image.save(str(path), "PNG")

    def choose_icon(self) -> None:
        """Choose: an item's own icon made from any image file, fitted to the game's icon sizes."""
        from PySide6.QtWidgets import QFileDialog
        from PIL import Image
        edit = self._picked_item()
        if edit is None:
            return
        path = self._ask("icon", lambda: QFileDialog.getOpenFileName(
            self, CHOOSE_ICON_TITLE.format(item=edit.item.name), "", IMAGE_FILES)[0])
        if not path:
            return
        try:
            with Image.open(path) as image:
                edit.icon_png = mi.icon_png(image)
        except Exception as exc:                                      # noqa: BLE001
            self._say(CANT_READ_IMAGE.format(problem=exc))
            return
        edit.icon_from = Path(path).name
        self._say("")
        self._items_changed(refill=False)

    def choose_small_icon(self) -> None:
        """(1.27.0) Choose: its own small icon (the lists' 48 by 48) made from any image file, apart from its art.
        (4 November) While it uses the game's icon, the image is its art too (an item's own icon is its art and its
        small icon together), each fitted to its size."""
        from PySide6.QtWidgets import QFileDialog
        from PIL import Image
        edit = self._picked_item()
        if edit is None:
            return
        path = self._ask("small_icon", lambda: QFileDialog.getOpenFileName(
            self, CHOOSE_SMALL_TITLE.format(item=edit.item.name), "", IMAGE_FILES)[0])
        if not path:
            return
        try:
            with Image.open(path) as image:
                small = mi.icon_png(image, mi.SMALL_ICON_SIZE)
                art = mi.icon_png(image) if not edit.icon_png else edit.icon_png
        except Exception as exc:                                      # noqa: BLE001
            self._say(CANT_READ_IMAGE.format(problem=exc))
            return
        if not edit.icon_png:
            edit.icon_from = Path(path).name
        edit.icon_png, edit.small_png = art, small
        edit.small_from = Path(path).name
        self._say("")
        self._items_changed(refill=False)

    def small_from_art(self) -> None:
        """(1.27.0) Use its art: its small icon made from its art again."""
        edit = self._picked_item()
        if edit is None or not edit.small_png:
            return
        edit.small_png, edit.small_from = b"", ""
        self._items_changed(refill=False)

    def _show_items_world(self) -> None:
        """The world map with the Items tab: the towns of the mod's that sell the item picked outlined."""
        self._want_world()
        self._show_mod_world()
        self.world.places = self.place_where()
        self.world.markers = []
        self.world.edit_place = self.world.edit_road = self.world.picked = None
        edit = self._picked_item()
        towns = pe.towns_selling_item(self.places_store(), edit.item.name) if edit is not None else []
        self.world.outlined = set(towns)
        if edit is None:
            self.world_title.setText(ITEMS_WORLD_TITLE["none"])
            self.world_hint.setText(PICK_AN_ITEM if self.items_store() else "")
        else:
            self.world_title.setText(ITEMS_WORLD_TITLE["item"].format(item=edit.item.name))
            self.world_hint.setText(ITEMS_WORLD_HINT["towns" if towns else "none"])
        self.world.update()

    # =========================================================================
    # Places and roads (the Places tab: the page's second part)
    # =========================================================================

    def in_places(self) -> bool:
        """Whether the Places tab is shown (its list, its cards and the world map's editing)."""
        return self.tabs.currentIndex() == 1

    def _tab_changed(self, index: int) -> None:
        self.left_stack.setCurrentIndex(index)
        # With Places (and (1.26.0) Items) the map takes the height, as the mock-up drew it: no steps' row under it.
        self.bottom.setVisible(index == 0)
        self._say("")
        self._centred_on = None
        self._fill_places()
        self._fill_items()
        self._show_card()
        self._show_middle()

    def show_places(self, pick: Optional[tuple] = None) -> None:
        """The Places tab shown, `pick` picked (("place", folder) or ("road", folder)) when given."""
        if pick is not None:
            self.place_pick = pick
            self.place_road = self._first_road_of(pick)
        if not self.in_places():
            self.tabs.setCurrentIndex(1)
        else:
            self._tab_changed(1)

    def _pick_exists(self, pick: tuple) -> bool:
        if pick[0] in ("battle", "place_unit"):
            # (1.17.0) A battle ground's random battle, or one of its units; (1.21.0) or a dungeon's floor's.
            place = self.places_store().get(pick[1])
            battle = pe.battle_named(place, pick[2]) if place is not None else None
            return battle is not None and (place.dungeon if battle.floor else not place.town)
        if pick[0] == "floor":
            # (1.21.0) A dungeon's floor.
            place = self.places_store().get(pick[1])
            return place is not None and place.dungeon and pe.floor_named(place, pick[2]) is not None
        store = self.places_store() if pick[0] == "place" else self.roads_store()
        return pick[1] in store

    @staticmethod
    def _listed_pick(pick: Optional[tuple]) -> Optional[tuple]:
        """What the list shows picked: a place or a road; (1.17.0) for a random battle or its unit, its place; (1.21.0)
        for a dungeon's floor, its dungeon."""
        if pick and pick[0] in ("battle", "place_unit", "floor"):
            return ("place", pick[1])
        return pick

    def _first_place_pick(self) -> Optional[tuple]:
        if self.places_store():
            return ("place", next(iter(self.places_store())))
        if self.roads_store():
            return ("road", next(iter(self.roads_store())))
        return None

    def _first_road_of(self, pick: Optional[tuple]) -> Optional[str]:
        """The road a place's card picks first: its first road (its turns shown on the map)."""
        if not pick or pick[0] != "place" or pick[1] not in self.places_store():
            return None
        roads = pe.roads_at(self.roads_store(), self.places_store()[pick[1]].name)
        return roads[0].folder if roads else None

    def _filter_places(self, text: str) -> None:
        wanted = text.strip().lower()
        for n in range(self.place_list.count()):
            item = self.place_list.item(n)
            item.setHidden(bool(wanted) and wanted not in item.text().lower())

    def _place_list_picked(self, item, _previous=None) -> None:
        if item is None or item.data(Qt.UserRole) is None:
            return
        self.pick_place(item.data(Qt.UserRole))

    def pick_place(self, pick: tuple) -> None:
        """Picks a place or a road of the mod's: its card, and the world map showing it."""
        if pick != self.place_pick and self._listed_pick(pick) != self._listed_pick(self.place_pick):
            self.place_road = self._first_road_of(pick)
        self.place_pick = pick
        listed = self._listed_pick(pick)
        for n in range(self.place_list.count()):
            if self.place_list.item(n).data(Qt.UserRole) == listed:
                self.place_list.blockSignals(True)
                self.place_list.setCurrentRow(n)
                self.place_list.blockSignals(False)
        self.remove_place_button.setEnabled(True)
        self._show_card()
        self._show_middle()

    def _places_changed(self, refill: bool = True) -> None:
        """After a place or road changed: the list, the card, the world map; Export's summary."""
        if refill:
            self._fill_places()
            self._fill_list()
        self._show_card()
        self._show_middle()
        self.edits_changed.emit()

    # -- what the world map draws of the mod's -------------------------------------------------------

    def _own_texture(self, place: pe.PlaceEdit) -> Optional[QImage]:
        """A town's own texture as the map draws it, kept while its bytes stay."""
        if not place.texture:
            return None
        kept = self._own_textures.get(place.folder)
        if kept is None or kept[0] is not place.texture:
            image = QImage.fromData(place.texture)
            kept = (place.texture, None if image.isNull() else image)
            self._own_textures[place.folder] = kept
        return kept[1]

    def _road_drawn(self, road: pe.RoadEdit):
        """The road drawn between its places (`place_edits.draw`): (the road as written, its QImage), or the words
        saying why it can't be. Kept while its places and turns stay."""
        places = self.places_store()
        key = (road.start, road.end, tuple(tuple(p) for p in road.via), pe.where(road.start, places),
               pe.where(road.end, places))
        kept = self._road_drawings.get(road.folder)
        if kept is not None and kept[0] == key:
            return kept[1]
        try:
            made, picture = pe.draw(road, places)
            found = (made, lp.pil_to_qimage(picture), picture.size)
        except ValueError as exc:
            found = str(exc)
        self._road_drawings[road.folder] = (key, found)
        return found

    def _trail_points(self, road: pe.RoadEdit) -> list:
        """The road's points on the map's picture: its From's middle, its turns, its To's middle."""
        places = self.places_store()
        start, end = pe.where(road.start, places), pe.where(road.end, places)
        points = [tuple(p) for p in road.via]
        if start is not None:
            points = [(start[1], start[2])] + points
        if end is not None:
            points = points + [(end[1], end[2])]
        return points

    def _show_mod_world(self) -> None:
        """The mod's places and roads over the world map, as they are now."""
        places = {}
        for place in self.places_store().values():
            places[place.name] = (place.x, place.y, place.town, self._own_texture(place),
                                  place.icon or pe.DEFAULT_ICON)
        self.world.mod_places = places
        roads = []
        for folder, road in self.roads_store().items():
            drawn = self._road_drawn(road)
            if not isinstance(drawn, str):
                roads.append((folder, drawn[1], drawn[0].at))
        self.world.mod_roads = roads

    def _edited_road(self) -> Optional[pe.RoadEdit]:
        """The road whose turns the map shows: the road picked, or the one a place's card has picked."""
        pick = self.place_pick
        if pick and pick[0] == "road":
            return self.roads_store().get(pick[1])
        if pick and pick[0] == "place" and self.place_road:
            return self.roads_store().get(self.place_road)
        return None

    def _show_places_world(self) -> None:
        self._want_world()
        self._show_mod_world()
        self.world.places = self.place_where()
        self.world.markers = []
        self.world.outlined = set()
        self.world.edit_place = self.world.edit_road = self.world.picked = None
        pick, places = self.place_pick, self.places_store()
        road = self._edited_road()
        if road is not None:
            self.world.edit_road = (road.folder, self._trail_points(road))
        centre = None
        if pick and pick[0] == "place" and pick[1] in places:
            place = places[pick[1]]
            self.world.picked = self.world.edit_place = place.name
            count = len(pe.roads_at(self.roads_store(), place.name))
            self.world_title.setText(WORLD_PLACE_TITLE["alone" if not count else "place" if count == 1 else "places"]
                                     .format(place=place.name))
            self.world_hint.setText(WORLD_PLACE_HINT["road"].format(place=place.name, road=road.name) if road
                                    else WORLD_PLACE_HINT["alone"].format(place=place.name))
            centre = (place.x, place.y)
        elif pick and pick[0] == "road" and road is not None:
            self.world_title.setText(WORLD_PLACE_TITLE["road"].format(road=road.name, start=pe.place_words(road.start),
                                                                      end=pe.place_words(road.end)))
            self.world_hint.setText(WORLD_PLACE_HINT["turns"])
            points = self._trail_points(road)
            if points:
                centre = (sum(x for x, _ in points) / len(points), sum(y for _, y in points) / len(points))
        else:
            self.world_title.setText(WORLD_PLACE_TITLE["none"])
            self.world_hint.setText(WORLD_PLACE_HINT["none"] if places else PICK_A_PLACE)
        # The map goes to what is picked when the pick changes, and stays where it was moved to otherwise.
        if centre is not None and getattr(self, "_centred_on", None) != pick:
            self._centred_on = pick
            self.world.show_place(*centre)
        self.world.update()

    # -- what the map's editing does ------------------------------------------------------------------

    def _place_dropped(self, name: str, x: int, y: int) -> None:
        place = pe.place_named(self.places_store(), name)
        if place is None:
            return
        over = pe.overlapping(place, self.places_store(), x, y)
        if not pe.on_map(place.town, x, y):
            self._say(OFF_MAP.format(place=name))
        elif over:
            self._say(OVERLAPS.format(place=name, others=", ".join(over)))
        else:
            place.x, place.y = int(x), int(y)
            self._say("")
        self._places_changed(refill=False)

    def _turn_added(self, index: int, x: int, y: int) -> None:
        road = self._edited_road()
        if road is None:
            return
        if len(road.via) >= mr.MOST_VIA:
            self._say(TOO_MANY_TURNS.format(most=mr.MOST_VIA))
            return
        road.via.insert(max(0, min(index, len(road.via))), (int(x), int(y)))
        self._say("")
        self._places_changed(refill=False)

    def _turn_moved(self, index: int, x: int, y: int) -> None:
        road = self._edited_road()
        if road is None or not 0 <= index < len(road.via):
            return
        road.via[index] = (int(x), int(y))
        self._places_changed(refill=False)

    def _turn_removed(self, index: int) -> None:
        road = self._edited_road()
        if road is None or not 0 <= index < len(road.via):
            return
        road.via.pop(index)
        self._places_changed(refill=False)

    # -- the cards ------------------------------------------------------------------------------------

    def _places_card(self) -> CardPane:
        pick = self.place_pick
        if pick and pick[0] in ("battle", "place_unit") and self._pick_exists(pick):
            # (1.17.0) A battle ground's random battle, or one of its units.
            place = self.places_store()[pick[1]]
            battle = pe.battle_named(place, pick[2])
            if pick[0] == "place_unit":
                return self._unit_card_of(battle.units, pick[3],
                                          lambda field, value: self._set_place_unit(pick[3], field, value),
                                          lambda: self.pick_place(("battle", place.folder, battle.name)),
                                          lambda: self.take_out_place_unit(pick[3]))
            return self._place_battle_card(place, battle)
        if pick and pick[0] == "floor" and self._pick_exists(pick):
            # (1.21.0) A dungeon's floor.
            place = self.places_store()[pick[1]]
            return self._floor_card(place, pe.floor_named(place, pick[2]))
        if pick and pick[0] == "place" and pick[1] in self.places_store():
            return self._place_card(self.places_store()[pick[1]])
        if pick and pick[0] == "road" and pick[1] in self.roads_store():
            return self._road_card(self.roads_store()[pick[1]])
        card = CardPane(PLACE_BAND, "", PLACE_COLOUR, "", PICK_A_PLACE if self.places_store() else "")
        card.status([], "")
        return card

    def _place_card(self, place: pe.PlaceEdit) -> CardPane:
        roads = self.roads_store()
        card = CardPane(PLACE_BAND, _kind_words(place), PLACE_COLOUR, place.name, PLACE_BLURB)
        name = QLineEdit(place.name)
        name.setMaxLength(64)
        name.setToolTip(PLACE_NAME_TIP)
        name.editingFinished.connect(lambda box=name: self.rename_place(box.text()))
        self.field_widgets["place_name"] = name
        card.field(NAME, name)
        described = QPlainTextEdit(place.description)
        described.setTabChangesFocus(True)
        described.setFixedHeight(70)
        described.textChanged.connect(lambda b=described: self._set_place_description(b.toPlainText()))
        self.field_widgets["place_description"] = described
        card.field(DESCRIPTION, described, muted(DESCRIPTION_NOTE),
                   *([muted(DUNGEON_ABOUT_NOTE)] if place.dungeon else []))
        town, battle, dungeon = QRadioButton(TOWN_KIND), QRadioButton(BATTLE_KIND), QRadioButton(DUNGEON_KIND)
        kinds = QButtonGroup(card)
        for button, kind in ((town, pe.TOWN), (battle, pe.GROUND), (dungeon, pe.DUNGEON)):
            kinds.addButton(button)
            button.setChecked(pe.kind_of(place) == kind)
            button.toggled.connect(lambda on, k=kind: self._set_place_kind(k) if on else None)
        self.field_widgets.update(place_town=town, place_battle=battle, place_dungeon=dungeon)
        card.field(KIND, town, battle, dungeon)
        if place.town:
            own, games = QRadioButton(OWN_TEXTURE), QRadioButton(GAME_TEXTURE)
            textures = QButtonGroup(card)
            textures.addButton(own)
            textures.addButton(games)
            (own if place.texture else games).setChecked(True)
            own.toggled.connect(self._use_own_texture)
            chosen = muted(place.texture_from or NO_FILE_YET)
            chosen.setWordWrap(False)
            choose = QPushButton(CHOOSE)
            choose.clicked.connect(self.choose_texture)
            icons = combo([(icon, TOWN_TEXTURE.format(icon=icon)) for icon in mp.ICONS],
                          place.icon or pe.DEFAULT_ICON, enabled=not place.texture)
            icons.setMinimumContentsLength(len(TOWN_TEXTURE.format(icon="14_34")))
            icons.currentIndexChanged.connect(lambda _i, b=icons: self._set_place_icon(b.currentData()))
            preview = QLabel()
            preview.setFixedSize(80, 80)
            preview.setAlignment(Qt.AlignCenter)
            shown = self._own_texture(place) if place.texture else self.world.icons.get(place.icon or pe.DEFAULT_ICON)
            if shown is not None:
                preview.setPixmap(QPixmap.fromImage(shown.scaled(76, 76, Qt.KeepAspectRatio,
                                                                 Qt.SmoothTransformation)))
            self.field_widgets.update(texture_own=own, texture_game=games, texture_choose=choose,
                                      texture_icon=icons, texture_preview=preview, texture_file=chosen)
            card.field(TEXTURE, row(own, chosen, choose), games, row(_indent(), icons), preview, muted(TEXTURE_NOTE))
        card.field(WHERE, muted(WHERE_AT.format(x=place.x, y=place.y)), muted(WHERE_NOTE))
        joined = pe.roads_at(roads, place.name)
        listed = QListWidget()
        listed.setAlternatingRowColors(True)
        listed.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for road in joined:
            item = QListWidgetItem(ROAD_OF_PLACE.format(road=road.name,
                                                       place=pe.place_words(pe.other_end(road, place.name))))
            item.setData(Qt.UserRole, road.folder)
            listed.addItem(item)
            if road.folder == self.place_road:
                listed.setCurrentItem(item)
        listed.setFixedHeight(max(1, len(joined)) * 24 + 8)
        listed.currentItemChanged.connect(lambda item, _p=None: self._place_road_picked(item))
        listed.itemDoubleClicked.connect(lambda item: self.pick_place(("road", item.data(Qt.UserRole))))
        add = QPushButton(ADD_ROAD)
        add.clicked.connect(lambda: self.new_road(place.name))
        take = QPushButton(TAKE_OUT)
        take.setEnabled(self.place_road is not None)
        take.clicked.connect(lambda: self.remove_road(self.place_road))
        self.field_widgets.update(place_roads=listed, add_road=add, take_road=take)
        if joined:
            card.field(ROADS, listed, row(add, take, stretch_first=False), muted(ROADS_NOTE))
        else:
            listed.setVisible(False)
            card.field(ROADS, muted(NO_ROAD_YET), row(add, take, stretch_first=False))
        if not place.town:
            self._random_battles_field(card, place)
        elif place.dungeon:
            # (1.21.0) A dungeon's floors; (1.23.0) its art.
            self._floors_field(card, place)
            self._dungeon_art_field(card, place)
        else:
            self._town_menu_field(card, place)
            self._town_dark_field(card, place)
        waiting = [muted(STEP_HERE.format(quest=q, n=n)) for q, n in pe.waiting_at(self.quests(), place.name, False)]
        for floor in place.floors if place.dungeon else []:
            # (1.25.0) Each step waiting at one of its floors.
            waiting += [muted(STEP_AT_FLOOR.format(quest=q, n=n, floor=floor.name))
                        for q, n, _e in pe.waiting_at_floor(self.quests(), place.name, floor.name)]
        card.field(STEPS_HERE, *(waiting or [muted(NO_STEP_HERE)]))
        self._place_status(card, place)
        card.add_buttons(REMOVE)
        card.buttons[REMOVE].clicked.connect(self.remove_place_or_road)
        return card

    def _place_status(self, card: CardPane, place: pe.PlaceEdit) -> None:
        """A place's card's foot: what Mod Studio Framework would say of it, else where it stands and its roads'
        problems in Mod Studio's words, else ready."""
        joined = pe.roads_at(self.roads_store(), place.name)
        said = pe.place_problems(place, self.quest_map_names())
        where = pe.place_warnings(place, self.places_store())
        # (1.20.0) A town darkened by a flag the mod's quests don't have.
        dark = pe.dark_problem(place, self.quests()) if not place.dungeon else ""
        if dark:
            where.append(dark)
        # (1.21.0) A dungeon's floor waiting for a flag the mod's quests don't have.
        where += pe.floor_problems(place, self.quests())
        drawn_problems = [problem for road in joined for found in self._road_problems(road) for problem in found]
        if said:
            card.status(said)
        elif where or drawn_problems:
            self._warn(card, where + [f"{ROAD_PROBLEM_LEAD}{p}" for p in drawn_problems])
        else:
            ends = []
            for road in joined:
                words = pe.place_words(pe.other_end(road, place.name))
                if words not in ends:
                    ends.append(words)
            card.status([], PLACE_READY.format(places=_listed(ends), roads=_listed([r.name for r in joined]))
                        if joined else PLACE_READY_ALONE)

    # -- (1.17.0) a battle ground's own random battles -------------------------------------------------

    def _random_battle_line(self, battle: pe.BattleEdit) -> str:
        """A random battle in a line: its name, how many units it has, its map."""
        count = sum(1 for u in entd.battle_units(battle.units) if u.occupied) if battle.units else 0
        units = ENEMIES_COUNT.get(count) or ENEMIES_MANY.format(n=count)
        if battle.map is None:
            return RANDOM_BATTLE_NO_MAP.format(battle=battle.name, units=units)
        return RANDOM_BATTLE_LINE.format(battle=battle.name, units=units, map=self._map_words(battle.map))

    def _random_battles_field(self, card: CardPane, place: pe.PlaceEdit) -> None:
        """A battle ground's card's random battles: each a line (double click it to change it), Add a battle and Take
        out, and how many of 100 arrivals start one."""
        listed = QListWidget()
        listed.setAlternatingRowColors(True)
        listed.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        ground = [b for b in place.battles if not b.floor]
        for battle in ground:
            item = QListWidgetItem(self._random_battle_line(battle))
            item.setData(Qt.UserRole, battle.name)
            listed.addItem(item)
        listed.setFixedHeight(max(1, len(ground)) * 24 + 8)
        listed.itemDoubleClicked.connect(
            lambda item, f=place.folder: self.pick_place(("battle", f, item.data(Qt.UserRole))))
        add = QPushButton(ADD_RANDOM_BATTLE)
        add.setToolTip(ADD_RANDOM_BATTLE_TIP)
        add.setEnabled(len(ground) < mp.MOST_BATTLES and self.game() is not None)
        add.clicked.connect(self.add_place_battle)
        take = QPushButton(TAKE_OUT)
        take.setEnabled(False)
        listed.currentItemChanged.connect(lambda item, _p=None, b=take: b.setEnabled(item is not None))
        take.clicked.connect(lambda: self.remove_place_battle(
            listed.currentItem().data(Qt.UserRole) if listed.currentItem() is not None else None))
        often = spin(place.chance, 0, mp.MOST_CHANCE)
        often.setSuffix(HOW_OFTEN_SUFFIX)
        often.setToolTip(HOW_OFTEN_TIP)
        often.valueChanged.connect(self._set_place_chance)
        self.field_widgets.update(place_battles=listed, add_place_battle=add, take_place_battle=take,
                                  place_chance=often)
        if ground:
            card.field(RANDOM_BATTLES, listed, row(add, take, stretch_first=False), pair((HOW_OFTEN, often)),
                       muted(RANDOM_BATTLES_NOTE))
        else:
            listed.setVisible(False)
            often.setVisible(False)
            card.field(RANDOM_BATTLES, muted(NO_RANDOM_BATTLE), row(add, take, stretch_first=False))

    # -- (1.21.0) a dungeon's floors -----------------------------------------------------------------

    def _floor_line(self, place: pe.PlaceEdit, floor: pe.FloorEdit) -> str:
        """A floor in a line: its name, how many battles it has, when it is listed."""
        many = len(pe.floor_battles(place, floor.name))
        battles = FLOOR_BATTLES_COUNT.get(many) or FLOOR_BATTLES_MANY.format(n=many)
        listed = (FLOOR_ONCE_WON if floor.won
                  else FLOOR_ONCE.format(flag=floor.flag, quest=floor.quest) if floor.quest and floor.flag
                  else FLOOR_FROM_START)
        return FLOOR_LINE.format(floor=floor.name, battles=battles, listed=listed)

    def _floors_field(self, card: CardPane, place: pe.PlaceEdit) -> None:
        """A dungeon's card's floors: each a line in the list's order (double click it to change it), Add a floor and
        Take out."""
        listed = QListWidget()
        listed.setAlternatingRowColors(True)
        listed.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for floor in place.floors:
            item = QListWidgetItem(self._floor_line(place, floor))
            item.setData(Qt.UserRole, floor.name)
            listed.addItem(item)
        listed.setFixedHeight(max(1, len(place.floors)) * 24 + 8)
        listed.itemDoubleClicked.connect(
            lambda item, f=place.folder: self.pick_place(("floor", f, item.data(Qt.UserRole))))
        add = QPushButton(ADD_FLOOR)
        add.setEnabled(len(place.floors) < mp.MOST_FLOORS)
        add.clicked.connect(self.add_floor)
        take = QPushButton(TAKE_OUT)
        take.setEnabled(False)
        listed.currentItemChanged.connect(lambda item, _p=None, b=take: b.setEnabled(item is not None))
        take.clicked.connect(lambda: self.remove_floor(
            listed.currentItem().data(Qt.UserRole) if listed.currentItem() is not None else None))
        self.field_widgets.update(floors=listed, add_floor=add, take_floor=take)
        if place.floors:
            card.field(FLOORS, listed, row(add, take, stretch_first=False), muted(FLOORS_NOTE))
        else:
            listed.setVisible(False)
            card.field(FLOORS, muted(NO_FLOOR), row(add, take, stretch_first=False))

    def _dungeon_art_field(self, card: CardPane, place: pe.PlaceEdit) -> None:
        """(1.23.0) A dungeon's card's art, its list's and its location info's: one of the game's places' (Midlight's
        Deep's until another is picked), or its own made from an image file, as a town's menu's own art is."""
        places = [(n, MENU_ART_CHOICE.format(town=place_name(n))) for n in pe.ART_PLACES]
        art = combo(places, place.dungeon_art, enabled=not place.dungeon_own_art)
        art.currentIndexChanged.connect(lambda _i, b=art: self._set_dungeon_art(b.currentData()))
        game_art, own_art = QRadioButton(DUNGEON_GAME_ART), QRadioButton(OWN_ART)
        arts = QButtonGroup(self)
        arts.addButton(game_art)
        arts.addButton(own_art)
        (own_art if place.dungeon_own_art else game_art).setChecked(True)
        own_art.toggled.connect(self._use_dungeon_own_art)
        art_file = muted(place.dungeon_own_art_from or NO_FILE_YET)
        art_file.setWordWrap(False)
        choose_art = QPushButton(CHOOSE)
        choose_art.clicked.connect(self.choose_dungeon_art)
        art_preview = QLabel()
        art_preview.setFixedSize(170, 113)
        art_preview.setAlignment(Qt.AlignCenter)
        if place.dungeon_own_art:
            shown = QImage.fromData(place.dungeon_own_art)
            if not shown.isNull():
                art_preview.setPixmap(QPixmap.fromImage(shown.scaled(170, 113, Qt.KeepAspectRatio,
                                                                     Qt.SmoothTransformation)))
        else:
            art_preview.setVisible(False)
        self.field_widgets.update(dungeon_art=art, dungeon_game_art=game_art, dungeon_own_art=own_art,
                                  dungeon_art_file=art_file, dungeon_choose_art=choose_art,
                                  dungeon_art_preview=art_preview)
        card.field(MENU_ART, game_art, row(_indent(), art), own_art, row(_indent(), art_file, choose_art), art_preview,
                   muted(DUNGEON_OWN_ART_NOTE), muted(DUNGEON_ART_NOTE))

    def _set_dungeon_art(self, number) -> None:
        place = self._dungeon()
        if place is None or self._building or number is None:
            return
        pe.set_dungeon_art(place, number)
        self._places_changed()

    def _use_dungeon_own_art(self, own: bool) -> None:
        """Your own art ticked: its image chosen (nothing changed until one is); a game place's ticked: that place's
        art again."""
        place = self._dungeon()
        if place is None or self._building:
            return
        if own and not place.dungeon_own_art:
            self.choose_dungeon_art()
            if not place.dungeon_own_art:
                self._show_card()
            return
        if not own and place.dungeon_own_art:
            pe.set_dungeon_art(place, place.dungeon_art)
            self._places_changed()

    def choose_dungeon_art(self) -> None:
        """Choose: a dungeon's own art made from any image file, fitted into 680 x 452."""
        from PySide6.QtWidgets import QFileDialog
        place = self._dungeon()
        if place is None:
            return
        path = self._ask("art", lambda: QFileDialog.getOpenFileName(
            self, CHOOSE_ART_TITLE.format(place=place.name), "", IMAGE_FILES)[0])
        if not path:
            return
        try:
            art = pe.art_from_file(path)
        except Exception as exc:                                      # noqa: BLE001
            self._say(CANT_READ_IMAGE.format(problem=exc))
            return
        pe.set_dungeon_own_art(place, art, Path(path).name)
        self._say("")
        self._places_changed()

    def _floor_card(self, place: pe.PlaceEdit, floor: pe.FloorEdit) -> CardPane:
        """A dungeon's floor's card: its name, its words, when it is listed (from the start, (1.24.0) once the floor
        before it is won, a floor but the first, or once one of the mod's quests' flags is set), and its battles (each
        a line, Add a battle and Take out)."""
        card = CardPane(FLOOR_BAND, FLOOR_AT.format(place=place.name), PLACE_COLOUR, floor.name,
                        FLOOR_BLURB.format(place=place.name))
        name = QLineEdit(floor.name)
        name.setMaxLength(mp.MOST_FLOOR_NAME)
        name.setToolTip(FLOOR_NAME_TIP)
        name.editingFinished.connect(lambda box=name, old=floor.name: self.rename_floor(old, box.text()))
        self.field_widgets["floor_name"] = name
        card.field(NAME, name)
        words = QPlainTextEdit(floor.description)
        words.setTabChangesFocus(True)
        words.setFixedHeight(70)
        words.textChanged.connect(lambda b=words, f=floor.name: self._set_floor_words(f, b.toPlainText()))
        self.field_widgets["floor_words"] = words
        card.field(FLOOR_WORDS, words, muted(FLOOR_WORDS_NOTE))
        flags = pe.flag_choices(self.quests())
        first = bool(place.floors) and place.floors[0] is floor
        choices = ([(None, FLOOR_LISTED_START)] + ([] if first else [(FLOOR_WON_CHOICE, FLOOR_LISTED_WON)])
                   + [(f"{q}/{f}", DARK_CHOICE.format(flag=f, quest=q)) for q, f in flags])
        current = (FLOOR_WON_CHOICE if floor.won and not first
                   else f"{floor.quest}/{floor.flag}" if floor.quest and floor.flag else None)
        if current is not None and current not in [c for c, _w in choices]:
            choices.append((current, DARK_CHOICE.format(flag=floor.flag, quest=floor.quest)))
        opens = combo(choices, current)
        opens.currentIndexChanged.connect(lambda _i, b=opens, f=floor.name: self._set_floor_opens(f, b.currentData()))
        self.field_widgets["floor_opens"] = opens
        note = muted(FLOOR_FIRST_NOTE if first else FLOOR_LISTED_NOTE)
        notes = [note] if flags else [muted(DARK_NO_FLAGS), note]
        card.field(FLOOR_LISTED, opens, *notes)
        battles = pe.floor_battles(place, floor.name)
        listed = QListWidget()
        listed.setAlternatingRowColors(True)
        listed.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for battle in battles:
            item = QListWidgetItem(self._random_battle_line(battle))
            item.setData(Qt.UserRole, battle.name)
            listed.addItem(item)
        listed.setFixedHeight(max(1, len(battles)) * 24 + 8)
        listed.itemDoubleClicked.connect(
            lambda item, f=place.folder: self.pick_place(("battle", f, item.data(Qt.UserRole))))
        add = QPushButton(ADD_RANDOM_BATTLE)
        add.setEnabled(len(battles) < mp.MOST_BATTLES and self.game() is not None)
        add.clicked.connect(lambda: self.add_place_battle(floor.name))
        take = QPushButton(TAKE_OUT)
        take.setEnabled(False)
        listed.currentItemChanged.connect(lambda item, _p=None, b=take: b.setEnabled(item is not None))
        take.clicked.connect(lambda: self.remove_place_battle(
            listed.currentItem().data(Qt.UserRole) if listed.currentItem() is not None else None))
        self.field_widgets.update(floor_battles=listed, add_floor_battle=add, take_floor_battle=take)
        if battles:
            card.field(FLOOR_BATTLES, listed, row(add, take, stretch_first=False), muted(FLOOR_BATTLES_NOTE))
        else:
            listed.setVisible(False)
            card.field(FLOOR_BATTLES, muted(NO_FLOOR_BATTLE), row(add, take, stretch_first=False))
        # (1.25.0) The steps of the mod's quests waiting at it, the first whose conditions hold played first.
        firsts = pe.waiting_at_floor(self.quests(), place.name, floor.name)
        if firsts:
            card.field(FIRST_BATTLE, *[muted(FIRST_BATTLE_LINE.format(quest=q, n=n, event=e)) for q, n, e in firsts],
                       muted(FIRST_BATTLE_NOTE))
        else:
            card.field(FIRST_BATTLE, muted(FIRST_BATTLE_NONE))
        # What Mod Studio Framework would say of the floor and its battles, then of its flag.
        named = [b.name for b in battles]
        said = [line for line in pe.place_problems(place, self.quest_map_names())
                if f"floor {floor.name}'s" in line or any(f"random battle {n}'s" in line or f"random battle {n} " in line
                                                          for n in named)]
        missing = [line for line in pe.floor_problems(place, self.quests()) if f"floor {floor.name} " in line]
        if said:
            card.status(said)
        elif missing:
            self._warn(card, missing)
        else:
            card.status([])
        card.add_buttons(BACK_TO_DUNGEON, REMOVE_FLOOR)
        card.buttons[BACK_TO_DUNGEON].clicked.connect(lambda: self.pick_place(("place", place.folder)))
        card.buttons[REMOVE_FLOOR].clicked.connect(lambda: self.remove_floor(floor.name))
        return card

    def _dungeon(self) -> Optional[pe.PlaceEdit]:
        """The dungeon a place's card or a floor's shows."""
        pick = self.place_pick
        if not pick or pick[0] not in ("place", "floor"):
            return None
        place = self.places_store().get(pick[1])
        return place if place is not None and place.dungeon else None

    def add_floor(self) -> None:
        """Add a floor: the dungeon's next, listed from the start, its card shown."""
        place = self._dungeon()
        if place is None:
            return
        try:
            made = pe.add_floor(place)
        except ValueError as exc:
            self._say(str(exc))
            return
        self._say("")
        self.place_pick = ("floor", place.folder, made)
        self._places_changed()

    def remove_floor(self, name: Optional[str]) -> None:
        """A floor taken out, with its battles; the dungeon's card again."""
        place = self._dungeon()
        if place is None or not name or pe.floor_named(place, name) is None:
            return
        pe.remove_floor(place, name)
        self.place_pick = ("place", place.folder)
        self._places_changed()

    def rename_floor(self, old: str, new: str) -> None:
        place = self._dungeon()
        if place is None or self._building or new == old:
            return
        try:
            pe.rename_floor(place, old, new, self.quests())
        except ValueError as exc:
            self._say(str(exc))
            self._show_card()
            return
        self._say("")
        self.place_pick = ("floor", place.folder, new)
        self._places_changed()

    def _set_floor_words(self, floor: str, words: str) -> None:
        place = self._dungeon()
        if place is None or self._building:
            return
        pe.set_floor_description(place, floor, words)
        self.edits_changed.emit()

    def _set_floor_opens(self, floor: str, choice) -> None:
        place = self._dungeon()
        if place is None or self._building:
            return
        if not choice:
            pe.set_floor_opens(place, floor)
        elif choice == FLOOR_WON_CHOICE:
            # (1.24.0) Listed once the floor before it is won (the first floor isn't offered it).
            try:
                pe.set_floor_opens(place, floor, won=True)
            except ValueError as exc:
                self._say(str(exc))
                return
        else:
            quest, flag = str(choice).split("/", 1)
            pe.set_floor_opens(place, floor, quest, flag)
        self._places_changed()

    # -- (1.18.0) a town's own menu -------------------------------------------------------------------

    def _town_menu_field(self, card: CardPane, place: pe.PlaceEdit) -> None:
        """A town's card's menu: ticked, its art (one of the game's towns'), its Outfitter's items (each a line, Take
        out; Add an item; a game town's copied; Sell nothing), its Poachers' Den, and the rumors its tavern tells."""
        tick = QCheckBox(MENU_TICK)
        tick.setChecked(place.menu is not None)
        tick.toggled.connect(self._set_town_menu)
        self.field_widgets["town_menu"] = tick
        if place.menu is None:
            card.field(MENU_FIELD, tick, muted(MENU_NOTE))
            return
        menu = place.menu
        towns = [(t, MENU_ART_CHOICE.format(town=place_name(t))) for t in range(mp.MOST_ART_TOWN + 1)]
        art = combo(towns, menu.art, enabled=not place.art)
        art.currentIndexChanged.connect(lambda _i, b=art: self._set_menu_art(b.currentData()))
        # (Its own art) One of the game's towns' art, or the modder's own made from an image.
        game_art, own_art = QRadioButton(GAME_ART), QRadioButton(OWN_ART)
        arts = QButtonGroup(self)
        arts.addButton(game_art)
        arts.addButton(own_art)
        (own_art if place.art else game_art).setChecked(True)
        own_art.toggled.connect(self._use_own_art)
        art_file = muted(place.art_from or NO_FILE_YET)
        art_file.setWordWrap(False)
        choose_art = QPushButton(CHOOSE)
        choose_art.clicked.connect(self.choose_art)
        art_preview = QLabel()
        art_preview.setFixedSize(170, 113)
        art_preview.setAlignment(Qt.AlignCenter)
        if place.art:
            shown = QImage.fromData(place.art)
            if not shown.isNull():
                art_preview.setPixmap(QPixmap.fromImage(shown.scaled(170, 113, Qt.KeepAspectRatio,
                                                                     Qt.SmoothTransformation)))
        else:
            art_preview.setVisible(False)
        self.field_widgets.update(menu_game_art=game_art, menu_own_art=own_art, menu_art_file=art_file,
                                  menu_choose_art=choose_art, menu_art_preview=art_preview)
        poachers = QCheckBox(POACHERS_TICK)
        poachers.setChecked(menu.poachers)
        poachers.toggled.connect(self._set_poachers)
        told = pe.told_at(self.quests(), place.name)
        tavern = (MENU_TAVERN.format(rumors=_listed([MENU_RUMOR.format(quest=q, rumor=r) for q, r in told]))
                  if told else MENU_NO_RUMOR)
        self.field_widgets.update(menu_art=art, menu_poachers=poachers)
        card.field(MENU_FIELD, tick, muted(MENU_NOTE), caption(MENU_ART), game_art, row(_indent(), art), own_art,
                   row(_indent(), art_file, choose_art), art_preview, muted(OWN_ART_NOTE), muted(MENU_ART_NOTE),
                   poachers, muted(POACHERS_NOTE), muted(tavern))
        names = nxd_names(self.state, "item")
        listed = QListWidget()
        listed.setAlternatingRowColors(True)
        listed.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for item in menu.shop:
            line = QListWidgetItem(names.get(item) or str(item))
            line.setData(Qt.UserRole, item)
            listed.addItem(line)
        # (1.26.0) Then the mod's own items, by their names.
        for item in menu.own:
            line = QListWidgetItem(OWN_ITEM_LINE.format(item=item))
            line.setData(Qt.UserRole, item)
            listed.addItem(line)
        sold = len(menu.shop) + len(menu.own)
        listed.setFixedHeight(min(10, max(1, sold)) * 22 + 8)
        take = QPushButton(TAKE_OUT)
        take.setEnabled(False)
        listed.currentItemChanged.connect(lambda item, _p=None, b=take: b.setEnabled(item is not None))
        take.clicked.connect(lambda: self.remove_shop_item(
            listed.currentItem().data(Qt.UserRole) if listed.currentItem() is not None else None))
        own_items = [(e.item.name, OWN_ITEM_LINE.format(item=e.item.name)) for e in self.items_store().values()
                     if e.item.name not in menu.own]
        add = combo([(None, ADD_ITEM)] + own_items + [(n, names.get(n) or str(n)) for n in range(1, mp.MOST_ITEM + 1)
                                                      if n not in menu.shop])
        add.currentIndexChanged.connect(lambda _i, b=add: self.add_shop_item(b.currentData()))
        records, edits = self._item_tables()
        copy_ = QPushButton(COPY_SHOP.format(town=place_name(menu.art)))
        copy_.setToolTip(COPY_SHOP_TIP.format(town=place_name(menu.art)))
        copy_.setEnabled(bool(records.get("item_shops")))
        copy_.clicked.connect(self.copy_shop)
        nothing = QPushButton(SELL_NOTHING)
        nothing.setEnabled(bool(menu.shop) or bool(menu.own))
        nothing.clicked.connect(self.clear_shop)
        self.field_widgets.update(shop=listed, take_shop_item=take, add_shop_item=add, copy_shop=copy_,
                                  sell_nothing=nothing)
        notes = [muted(OUTFITTER_NOTE)] + ([] if records.get("item_shops") else [muted(NO_SHOPS)])
        never = pe.never_sold(records, edits, menu.shop)
        if never:
            notes.append(muted(NEVER_SOLD.format(items=_listed([names.get(n) or str(n) for n in never]))))
        if sold:
            card.field(OUTFITTER, listed, row(add, take, stretch_first=True), row(copy_, nothing, stretch_first=False),
                       *notes)
        else:
            listed.setVisible(False)
            card.field(OUTFITTER, muted(OUTFITTER_EMPTY), row(add, take, stretch_first=True),
                       row(copy_, nothing, stretch_first=False), *notes)

    def _item_tables(self) -> tuple:
        """The item tables' records by id (ItemData and ItemShopsData, as Mod Studio has the game's) and the mod's
        edits of them."""
        state = self.state
        records = {table: state.item_table_records_by_id(table) for table in ("item", "item_shops")}
        return records, getattr(state, "item_table_edits", {}) or {}

    def _town(self) -> Optional[pe.PlaceEdit]:
        place = self._picked_place()
        return place if place is not None and place.town else None

    # -- (1.20.0) a town darkened once a quest's flag is set ------------------------------------------

    def _town_dark_field(self, card: CardPane, place: pe.PlaceEdit) -> None:
        """A town's card's darkening: Never, or once one of the mod's quests' flags is set ("Once <flag> is set
        (<quest>)", each flag of each quest); a flag its quests no longer have kept as it is, said on the card's
        foot."""
        choices = [(None, DARK_NEVER)] + [(f"{q}/{f}", DARK_CHOICE.format(flag=f, quest=q))
                                         for q, f in pe.flag_choices(self.quests())]
        current = f"{place.darkened.quest}/{place.darkened.flag}" if place.darkened is not None else None
        if current is not None and current not in [c for c, _w in choices]:
            choices.append((current, DARK_CHOICE.format(flag=place.darkened.flag, quest=place.darkened.quest)))
        darkened = combo(choices, current)
        darkened.currentIndexChanged.connect(lambda _i, b=darkened: self._set_darkened(b.currentData()))
        self.field_widgets["darkened"] = darkened
        notes = [muted(DARK_NOTE)] if len(choices) > 1 else [muted(DARK_NO_FLAGS), muted(DARK_NOTE)]
        card.field(DARK_FIELD, darkened, *notes)

    def _set_darkened(self, choice) -> None:
        place = self._town()
        if place is None or self._building:
            return
        if not choice:
            pe.set_darkened(place)
        else:
            quest, flag = str(choice).split("/", 1)
            pe.set_darkened(place, quest, flag)
        self._places_changed()

    def _set_town_menu(self, on: bool) -> None:
        place = self._town()
        if place is None or self._building:
            return
        pe.set_menu(place, bool(on))
        self._places_changed()

    def _set_menu_art(self, town) -> None:
        place = self._town()
        if place is None or self._building or town is None:
            return
        pe.set_menu_art(place, town)
        self._places_changed()

    def _use_own_art(self, own: bool) -> None:
        """Your own art ticked: its image chosen (nothing changed until one is); a game town's ticked: that town's art
        again."""
        place = self._town()
        if place is None or self._building or place.menu is None:
            return
        if own and not place.art:
            self.choose_art()
            if not place.art:
                self._show_card()
            return
        if not own and place.art:
            pe.set_menu_art(place, place.menu.art)
            self._places_changed()

    def choose_art(self) -> None:
        """Choose: a town's menu's own art made from any image file, fitted into 680 x 452."""
        from PySide6.QtWidgets import QFileDialog
        place = self._town()
        if place is None or place.menu is None:
            return
        path = self._ask("art", lambda: QFileDialog.getOpenFileName(
            self, CHOOSE_ART_TITLE.format(place=place.name), "", IMAGE_FILES)[0])
        if not path:
            return
        try:
            art = pe.art_from_file(path)
        except Exception as exc:                                      # noqa: BLE001
            self._say(CANT_READ_IMAGE.format(problem=exc))
            return
        pe.set_own_art(place, art, Path(path).name)
        self._say("")
        self._places_changed()

    def _set_poachers(self, on: bool) -> None:
        place = self._town()
        if place is None or self._building:
            return
        pe.set_poachers(place, bool(on))
        self._places_changed(refill=False)

    def add_shop_item(self, item) -> None:
        place = self._town()
        if place is None or self._building or item is None:
            return
        pe.add_shop_item(place, item)
        self._places_changed()

    def remove_shop_item(self, item) -> None:
        place = self._town()
        if place is None or item is None:
            return
        pe.remove_shop_item(place, item)
        self._places_changed()

    def copy_shop(self) -> None:
        """The Outfitter's items made a copy of its art town's, as the mod has the game's shops."""
        place = self._town()
        if place is None:
            return
        pe.copy_shop(place, *self._item_tables())
        self._places_changed()

    def clear_shop(self) -> None:
        place = self._town()
        if place is None:
            return
        pe.clear_shop(place)
        self._places_changed()

    def _place_battle_card(self, place: pe.PlaceEdit, battle: pe.BattleEdit) -> CardPane:
        """A random battle's card: its name, its map, its units (click one to change it), where your units start
        (its squares clicked on the map, how many, their facing and level) and the story's point it waits for."""
        if battle.floor:
            # (1.21.0) One of a dungeon's floor's battles.
            card = CardPane(RANDOM_BATTLE_BAND, FLOOR_BATTLE_AT.format(floor=battle.floor, place=place.name),
                            BATTLE_COLOUR, battle.name, FLOOR_BATTLE_BLURB.format(floor=battle.floor, place=place.name))
        else:
            card = CardPane(RANDOM_BATTLE_BAND, RANDOM_BATTLE_AT.format(place=place.name), BATTLE_COLOUR, battle.name,
                            RANDOM_BATTLE_BLURB.format(place=place.name))
        name = QLineEdit(battle.name)
        name.setMaxLength(64)
        name.setToolTip(NAME_TIP)
        name.editingFinished.connect(lambda box=name, old=battle.name: self.rename_place_battle(old, box.text()))
        self.field_widgets["battle_name"] = name
        card.field(NAME, name)
        choices = self._map_choices()
        if battle.map is None:
            choices = [(0, NO_MAP_YET_CHOICE)] + choices
        maps = combo(choices, battle.map if battle.map is not None else 0)
        maps.currentIndexChanged.connect(lambda _i, b=maps: self._set_place_battle_map(b.currentData()))
        self.field_widgets["battle_map"] = maps
        card.field(MAP, maps, muted(RANDOM_BATTLE_MAP_NOTE))
        units = QTreeWidget()
        units.setColumnCount(2)
        units.setHeaderHidden(True)
        units.setRootIsDecorated(False)
        units.setAlternatingRowColors(True)
        units.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        units.header().setStretchLastSection(True)
        units.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        battle_units = entd.battle_units(battle.units) if battle.units else []
        for unit in battle_units:
            item = QTreeWidgetItem([str(unit.slot + 1),
                                    self._unit_words(unit.values) if unit.occupied else EMPTY_SLOT])
            item.setData(0, Qt.UserRole, unit.slot)
            item.setTextAlignment(0, int(Qt.AlignRight | Qt.AlignVCenter))
            if not unit.occupied:
                item.setForeground(1, QColor(theme.current()["text_muted"]))
            units.addTopLevelItem(item)
        units.setFixedHeight(8 * 22 + 6)
        units.itemClicked.connect(lambda item, _column, f=place.folder, b=battle.name:
                                  self.pick_place(("place_unit", f, b, item.data(0, Qt.UserRole))))
        add = QPushButton(ADD_UNIT)
        add.setToolTip(ADD_UNIT_TIP)
        add.setEnabled(any(not u.occupied for u in battle_units))
        add.clicked.connect(self.add_place_unit)
        self.field_widgets.update(units=units, add_unit=add)
        card.field(UNITS, units, row(add, stretch_first=False), muted(UNITS_OWN))
        area = battle.deploy[0] if battle.deploy else sq.DeployArea([])
        count = spin(area.units, 1, sq.MOST_DEPLOY_UNITS)
        count.setToolTip(DEPLOY_UNITS_TIP)
        count.valueChanged.connect(lambda value: self._set_place_deploy(units=value))
        facing = combo(list(enumerate(FACING_WORDS)), area.facing)
        facing.currentIndexChanged.connect(lambda _i, b=facing: self._set_place_deploy(facing=b.currentData()))
        upper = QCheckBox(DEPLOY_UPPER)
        upper.setChecked(area.upper)
        upper.toggled.connect(lambda on: self._set_place_deploy(upper=on))
        squares = muted(self._squares_words(area))
        self.field_widgets.update(deploy_units=count, deploy_facing=facing, deploy_upper=upper, deploy_squares=squares)
        card.field(WHERE_UNITS_START, pair((DEPLOY_UNITS_FIELD, count), (FACING_FIELD, facing)), upper, squares,
                   muted(RANDOM_BATTLE_DEPLOY_NOTE))
        story = combo([(None, ANY_TIME)] + self.story_points(), battle.story)
        story.currentIndexChanged.connect(lambda _i, b=story: self._set_place_battle_story(b.currentData()))
        self.field_widgets["battle_story"] = story
        card.field(STORY_PAST, story, muted(RANDOM_BATTLE_STORY_NOTE))
        card.status(pe.battle_problems(place, battle.name, self.quest_map_names()),
                    plain=pe.battle_squares_taken(place, battle.name))
        if battle.floor:
            card.add_buttons(BACK_TO_FLOOR, REMOVE_RANDOM_BATTLE)
            card.buttons[BACK_TO_FLOOR].clicked.connect(
                lambda: self.pick_place(("floor", place.folder, battle.floor)))
        else:
            card.add_buttons(BACK_TO_PLACE, REMOVE_RANDOM_BATTLE)
            card.buttons[BACK_TO_PLACE].clicked.connect(lambda: self.pick_place(("place", place.folder)))
        card.buttons[REMOVE_RANDOM_BATTLE].clicked.connect(lambda: self.remove_place_battle(battle.name))
        return card

    def _picked_battle(self) -> tuple:
        """(the battle ground, its random battle) a battle's or its unit's pick names, else (None, None)."""
        pick = self.place_pick
        if not pick or pick[0] not in ("battle", "place_unit") or not self._pick_exists(pick):
            return None, None
        place = self.places_store()[pick[1]]
        return place, pe.battle_named(place, pick[2])

    def _ground(self) -> Optional[pe.PlaceEdit]:
        """The battle ground a place's card, a random battle's or one of its units' shows; (1.21.0) or the dungeon a
        floor's card, its battle's or one of its units' shows."""
        pick = self.place_pick
        if not pick or pick[0] not in ("place", "battle", "place_unit", "floor"):
            return None
        place = self.places_store().get(pick[1])
        return place if place is not None and (not place.town or place.dungeon) else None

    def add_place_battle(self, floor: str = "") -> None:
        """Add a battle: (Zodi, 4 November, his choice "Yes, the same sample") the battle ground's own random battle as
        the quest's sample battle on map 116 (`place_edits.add_sample_battle`), named as the next and its card shown,
        its name changed there; (1.21.0) a dungeon's, one of its floor `floor`'s."""
        place = self._ground()
        if place is None or bool(floor) != place.dungeon:
            return
        try:
            made = pe.add_sample_battle(place, "", floor)
        except ValueError as exc:
            self._say(CANT_MAKE.format(problem=exc))
            return
        self._say("")
        self.place_pick = ("battle", place.folder, made)
        self._places_changed()

    def remove_place_battle(self, name: Optional[str]) -> None:
        place = self._ground()
        battle = pe.battle_named(place, name) if place is not None and name else None
        if battle is None:
            return
        pe.remove_battle(place, name)
        # (1.21.0) A dungeon's battle: back to its floor.
        self.place_pick = ("floor", place.folder, battle.floor) if battle.floor else ("place", place.folder)
        self._places_changed()

    def rename_place_battle(self, old: str, new: str) -> None:
        place, battle = self._picked_battle()
        if place is None or self._building or new == old:
            return
        try:
            pe.rename_battle(place, old, new)
        except ValueError as exc:
            self._say(str(exc))
            self._show_card()
            return
        self._say("")
        self.place_pick = ("battle", place.folder, new)
        self._places_changed()

    def _set_place_chance(self, value: int) -> None:
        place = self._ground()
        if place is None or self._building:
            return
        pe.set_chance(place, value)
        self.edits_changed.emit()

    def _set_place_battle_map(self, value) -> None:
        place, battle = self._picked_battle()
        if place is None or self._building or value is None:
            return
        pe.set_battle_map(place, battle.name, None if value == 0 else value)
        self._places_changed(refill=False)

    def _set_place_battle_story(self, value) -> None:
        place, battle = self._picked_battle()
        if place is None or self._building:
            return
        pe.set_battle_story(place, battle.name, value)
        self.edits_changed.emit()

    def _set_place_unit(self, slot: int, field: str, value) -> None:
        place, battle = self._picked_battle()
        if place is None or self._building or value is None:
            return
        try:
            pe.set_battle_unit(place, battle.name, slot, **{field: value})
        except ValueError as exc:
            self._say(str(exc))
            return
        self.edits_changed.emit()
        self.battle_map.refresh_units()
        if field in TITLE_FIELDS and self.card is not None:
            unit = entd.battle_units(battle.units)[slot]
            self.card.title.setText(self._unit_words(unit.values) if unit.occupied else EMPTY_SLOT)

    def add_place_unit(self) -> None:
        """A copy of the unit picked (or the first) in the random battle's first empty place, and it picked."""
        place, battle = self._picked_battle()
        if place is None:
            return
        picked = self.place_pick[3] if self.place_pick[0] == "place_unit" else None
        slot = pe.add_battle_unit(place, battle.name, picked)
        if slot is None:
            occupied = [u.occupied for u in entd.battle_units(battle.units)]
            self._say(FULL if all(occupied) else NO_UNIT_TO_COPY)
            return
        self.place_pick = ("place_unit", place.folder, battle.name, slot)
        self._places_changed()

    def take_out_place_unit(self, slot: int) -> None:
        place, battle = self._picked_battle()
        if place is None:
            return
        pe.take_out_battle_unit(place, battle.name, slot)
        self.place_pick = ("battle", place.folder, battle.name)
        self._places_changed()

    def _set_place_deploy(self, units=None, facing=None, upper=None) -> None:
        place, battle = self._picked_battle()
        if place is None or self._building:
            return
        pe.set_battle_deploy(place, battle.name, units=units, facing=facing, upper=upper)
        self.edits_changed.emit()
        self._place_deploy_changed(battle)

    def _place_deploy_changed(self, battle: pe.BattleEdit) -> None:
        """After a square, or the units, facing or level of a random battle's area changed: its card's fields that show
        them and its problems as they now are (the card stays), and the map."""
        area = battle.deploy[0] if battle.deploy else None
        if area is not None and self.card is not None:
            self._building = True
            try:
                for key, value in (("deploy_units", area.units), ("deploy_facing", area.facing),
                                   ("deploy_upper", area.upper)):
                    box = self.field_widgets.get(key)
                    if box is None:
                        continue
                    if isinstance(box, QCheckBox):
                        box.setChecked(bool(value))
                    elif isinstance(box, QComboBox):
                        box.setCurrentIndex(max(0, box.findData(value)))
                    else:
                        box.setValue(int(value))
                said = self.field_widgets.get("deploy_squares")
                if said is not None:
                    said.setText(self._squares_words(area))
            finally:
                self._building = False
            place, _battle = self._picked_battle()
            if place is not None:
                self.card.status(pe.battle_problems(place, battle.name, self.quest_map_names()),
                                 plain=pe.battle_squares_taken(place, battle.name))
        self._show_deploy()

    def _show_place_battle_map(self, place: pe.PlaceEdit, battle: pe.BattleEdit) -> None:
        """A random battle's map in the middle: its units (click one to change it, drag it to move it) and its squares
        (click a tile to add it or take it out while its card is shown)."""
        self.middle.setCurrentIndex(1)
        self._shown_event = None
        self._shown_scene = False
        value = battle.map
        state = self.state
        if isinstance(value, str):
            quest_map = (getattr(self.state, "quest_maps", None) or {}).get(value)
            number = quest_map.base if quest_map is not None else None
            if quest_map is not None:
                state = qme.EditView(self.state, quest_map)
        else:
            number = value
        self.battle_map.state = state
        key = self._place_battle_key(place, battle)
        if number is not None:
            self.battle_map.chosen[key] = int(number)
        else:
            self.battle_map.chosen.pop(key, None)
        pick = self.place_pick
        self.battle_map.selected = (key, pick[3]) if pick and pick[0] == "place_unit" else None
        self.battle_map.show_battle(key)
        self.battle_map.map_label.setVisible(False)
        self.battle_map.map_box.setVisible(False)
        self.battle_map.hint.setVisible(True)
        self._show_deploy()
        if number is None:
            self.battle_map._no_map(NO_MAP_YET)

    def _place_battle_key(self, place: pe.PlaceEdit, battle: pe.BattleEdit) -> int:
        """The Encounters map's key for a random battle: past every battle of the game's and the quests' own."""
        folders = list(self.places_store())
        at = folders.index(place.folder) if place.folder in folders else 0
        names = [b.name for b in place.battles]
        return 200000 + 16 * at + (names.index(battle.name) if battle.name in names else 0)

    def _set_place_description(self, words: str) -> None:
        """(1.16.0) A place's description as it is typed: kept, its card's foot said again (the card kept as it is,
        its box still being typed in)."""
        place = self._picked_place()
        if place is None or self._building:
            return
        pe.set_description(place, words)
        self.edits_changed.emit()
        if self.card is not None:
            self._place_status(self.card, place)

    def _road_problems(self, road: pe.RoadEdit) -> tuple:
        """(why the road can't be drawn, in Mod Studio's words; what Mod Studio Framework would say of it)."""
        drawn = self._road_drawn(road)
        if isinstance(drawn, str):
            return [drawn], []
        made, _image, size = drawn
        return [], pe.road_problems(road, self.places_store(), (made, size))

    @staticmethod
    def _warn(card: CardPane, lines: list) -> None:
        """A card's foot saying what is wrong in Mod Studio's own words (not Mod Studio Framework's)."""
        card.status_label.setText("\n".join(lines))
        card.status_label.setStyleSheet(f"color: {theme.current()['danger']};")

    def _road_card(self, road: pe.RoadEdit) -> CardPane:
        turns = len(road.via)
        card = CardPane(ROAD_BAND, ROAD_TURNS.format(n=turns, s="s" if turns != 1 else "") if turns else "",
                        PLACE_COLOUR, road.name, ROAD_BLURB)
        name = QLineEdit(road.name)
        name.setMaxLength(64)
        name.setToolTip(PLACE_NAME_TIP)
        name.editingFinished.connect(lambda box=name: self.rename_road(box.text()))
        self.field_widgets["road_name"] = name
        card.field(NAME, name)
        ends = self._road_ends()
        start, end = combo(ends, road.start), combo(ends, road.end)
        start.currentIndexChanged.connect(lambda _i, b=start: self._set_road_end("start", b.currentData()))
        end.currentIndexChanged.connect(lambda _i, b=end: self._set_road_end("end", b.currentData()))
        self.field_widgets.update(road_start=start, road_end=end)
        card.field(FROM, start)
        card.field(TO, end, muted(ENDS_NOTE))
        card.field(TURNS, muted(TURNS_COUNT.format(n=turns, s="s" if turns != 1 else "") if turns else NO_TURNS),
                   muted(TURNS_NOTE))
        drawn = self._road_drawn(road)
        if not isinstance(drawn, str):
            made, _image, (width, height) = drawn
            card.field(ITS_TEXTURE, muted(DRAWN_NOTE.format(width=width, height=height, points=len(made.walk))))
        plain, said = self._road_problems(road)
        if plain:
            self._warn(card, plain)
        else:
            card.status(said, ROAD_READY.format(start=pe.place_words(road.start), end=pe.place_words(road.end)))
        card.add_buttons(REMOVE)
        card.buttons[REMOVE].clicked.connect(self.remove_place_or_road)
        return card

    def _road_ends(self) -> list:
        """`[(place, words)]`: the places a road may join, the mod's by name first, then the game's by number."""
        out = [(p.name, p.name) for p in self.places_store().values()]
        out += [(number, name) for number, (name, _town, _x, _y) in sorted(mr.GAME_PLACES.items())]
        return out

    def _place_road_picked(self, item) -> None:
        if self._building or item is None:
            return
        self.place_road = item.data(Qt.UserRole)
        self._show_card()
        self._show_middle()

    # -- what the cards change ------------------------------------------------------------------------

    def _picked_place(self) -> Optional[pe.PlaceEdit]:
        pick = self.place_pick
        return self.places_store().get(pick[1]) if pick and pick[0] == "place" else None

    def rename_place(self, name: str) -> None:
        place = self._picked_place()
        if place is None or self._building or name == place.name:
            return
        try:
            folder = pe.rename_place(self.places_store(), self.roads_store(), self.quests(), place.folder, name)
        except ValueError as exc:
            self._say(str(exc))
            self._show_card()
            return
        self._own_textures.pop(self.place_pick[1], None)
        self.place_pick = ("place", folder)
        self._centred_on = self.place_pick
        self._say("")
        self._places_changed()

    def rename_road(self, name: str) -> None:
        pick = self.place_pick
        road = self.roads_store().get(pick[1]) if pick and pick[0] == "road" else None
        if road is None or self._building or name == road.name:
            return
        try:
            folder = pe.rename_road(self.roads_store(), road.folder, name)
        except ValueError as exc:
            self._say(str(exc))
            self._show_card()
            return
        self._road_drawings.pop(pick[1], None)
        self.place_pick = ("road", folder)
        self._centred_on = self.place_pick
        self._say("")
        self._places_changed()

    def _set_place_kind(self, kind) -> None:
        """A place made a town, a battle ground or (1.21.0) a dungeon (`place_edits`' kinds; True a town, False a
        battle ground)."""
        if isinstance(kind, bool):
            kind = pe.TOWN if kind else pe.GROUND
        place = self._picked_place()
        if place is None or self._building or pe.kind_of(place) == kind:
            return
        pe.set_kind(place, kind)
        self._places_changed()

    def _set_place_icon(self, icon) -> None:
        place = self._picked_place()
        if place is None or self._building or icon is None:
            return
        place.icon = icon
        self._places_changed(refill=False)

    def _use_own_texture(self, own: bool) -> None:
        place = self._picked_place()
        if place is None or self._building:
            return
        if own and not place.texture:
            self.choose_texture()
            if not place.texture:
                self._show_card()
            return
        if not own and place.texture:
            place.texture, place.texture_from = b"", ""
            place.icon = place.icon or pe.DEFAULT_ICON
            self._places_changed(refill=False)

    def choose_texture(self) -> None:
        """Choose: a town's own texture made from any image file, fitted into the game's town textures' size."""
        from PySide6.QtWidgets import QFileDialog
        place = self._picked_place()
        if place is None:
            return
        path = self._ask("texture", lambda: QFileDialog.getOpenFileName(
            self, CHOOSE_TITLE.format(place=place.name), "", IMAGE_FILES)[0])
        if not path:
            return
        try:
            texture = pe.texture_from_file(path)
        except Exception as exc:                                      # noqa: BLE001
            self._say(CANT_READ_IMAGE.format(problem=exc))
            return
        place.texture, place.texture_from = texture, Path(path).name
        self._say("")
        self._places_changed(refill=False)

    def _set_road_end(self, which: str, value) -> None:
        pick = self.place_pick
        road = self.roads_store().get(pick[1]) if pick and pick[0] == "road" else None
        if road is None or self._building or value is None:
            return
        other = road.end if which == "start" else road.start
        if value == other:
            self._say(SAME_ENDS.format(end=FROM if which == "start" else TO))
            self._show_card()
            return
        setattr(road, which, value)
        self._say("")
        self._places_changed()

    # -- making and taking out ------------------------------------------------------------------------

    def new_place(self) -> None:
        """New place: its name and kind asked; it goes where the map is shown, clear of the game's places."""
        places = self.places_store()
        name = pe.free_name("New Place", [p.name for p in places.values()])
        dialog = PlaceDialog(self, NEW_PLACE_TITLE, NEW_PLACE_INTRO, name,
                             lambda n, _town: pe.name_problem(n, places))
        answer = self._ask("new_place", lambda: dialog.answer() if dialog.exec() == QDialog.Accepted else None)
        if not answer:
            return
        name, town = answer
        problem = pe.name_problem(name, places)
        if problem:
            self._say(problem)
            return
        # (1.21.0) Or a dungeon, drawn as a town is.
        dungeon = town == pe.DUNGEON
        town = True if dungeon else bool(town)
        x, y = pe.free_spot(town, round(self.world.centre.x()), round(self.world.centre.y()), places)
        place = pe.new_place(name, town, x, y, dungeon=dungeon)
        places[place.folder] = place
        self._say("")
        self.show_places(("place", place.folder))
        self._places_changed()

    def new_road(self, start=None) -> None:
        """New road: its name and the two places it joins asked (the place picked first)."""
        places, roads = self.places_store(), self.roads_store()
        if start is None:
            picked = self._picked_place()
            start = picked.name if picked is not None else (next(iter(places.values())).name if places else 6)
        end = self._nearest_game_place(start)
        name = pe.free_name(f"Road to {pe.place_words(start)}" if isinstance(start, str) else "New Road",
                            [r.name for r in roads.values()])

        def problem(n, a, b) -> str:
            return pe.name_problem(n, roads, kind="road") or (SAME_ENDS.format(end=TO) if a == b else "")
        dialog = PlaceDialog(self, NEW_ROAD_TITLE, NEW_ROAD_INTRO, name, problem, self._road_ends(), start, end)
        answer = self._ask("new_road", lambda: dialog.answer() if dialog.exec() == QDialog.Accepted else None)
        if not answer:
            return
        name, a, b = answer
        said = problem(name, a, b)
        if said:
            self._say(said)
            return
        road = pe.new_road(name, a, b)
        roads[road.folder] = road
        self._say("")
        picked = self._picked_place()
        if picked is not None and picked.name in (a, b):
            # Made from a place's card: it stays the place's card, the new road picked on it.
            self.place_road = road.folder
        else:
            self.place_pick, self.place_road = ("road", road.folder), None
        if not self.in_places():
            self.tabs.setCurrentIndex(1)
        self._places_changed()

    def _nearest_game_place(self, start):
        """The game's place nearest a road's start (a new road's To until another is picked)."""
        at = pe.where(start, self.places_store())
        if at is None:
            return 9 if start != 9 else 6
        _town, x, y = at
        return min((n for n in mr.GAME_PLACES if n != start),
                   key=lambda n: (mr.GAME_PLACES[n][2] - x) ** 2 + (mr.GAME_PLACES[n][3] - y) ** 2)

    def remove_place_or_road(self) -> None:
        """Remove: the place picked (with its roads) or the road picked, asked first."""
        pick = self.place_pick
        if not pick:
            return
        if pick[0] == "road":
            self.remove_road(pick[1])
            return
        place = self.places_store().get(pick[1])
        if place is None:
            return
        roads = [r.name for r in pe.roads_at(self.roads_store(), place.name)]
        steps = [STEP_HERE.format(quest=q, n=n)[:-len(" waits here.")] for q, n in
                 pe.waiting_at(self.quests(), place.name)]
        question = PLACE_REMOVE_ASK.format(name=place.name)
        if roads:
            question += PLACE_REMOVE_ROADS.format(roads=_listed(roads))
        if steps:
            question += PLACE_REMOVE_STEPS.format(steps=_listed(steps))
        sure = self._ask("remove_place", lambda: QMessageBox.question(self, TITLE, question) == QMessageBox.Yes)
        if not sure:
            return
        pe.remove_place(self.places_store(), self.roads_store(), place.folder)
        self.place_pick = self._first_place_pick()
        self.place_road = self._first_road_of(self.place_pick)
        self._say("")
        self._places_changed()

    def remove_road(self, folder: Optional[str]) -> None:
        road = self.roads_store().get(folder) if folder else None
        if road is None:
            return
        sure = self._ask("remove_road", lambda: QMessageBox.question(
            self, TITLE, ROAD_REMOVE_ASK.format(name=road.name)) == QMessageBox.Yes)
        if not sure:
            return
        self.roads_store().pop(folder)
        self._road_drawings.pop(folder, None)
        if self.place_pick == ("road", folder):
            self.place_pick = self._first_place_pick()
            self.place_road = self._first_road_of(self.place_pick)
        elif self.place_road == folder:
            self.place_road = self._first_road_of(self.place_pick)
        self._say("")
        self._places_changed()

    # =========================================================================
    # Making things
    # =========================================================================

    def new_quest(self) -> None:
        """(Zodi, 4 November: "So when the user clicks on New Quest it will bring up a menu that only has three things
        on it Name, Place, and Marker"; his choice, a story point too) New quest: its name, the place it starts at, when
        it is available and its marker asked; the quest made whole, its Blender cube (`quest_edits.starting_quest`):
        a rumor, a scene there, a battle at the nearest battle ground, a scene back there, all on map 116; (Zodi, 5
        November) made as test 70's quest was (`quest_edits.sample_quest`: its reward, its units' own names, the
        knight's first line said by no one, Ramza's lines naming him)."""
        game = self.game()
        if game is None:
            self._say(NO_GAME)
            return
        taken = set(self.quests())
        name = qx.free_name("New Quest", taken)
        dialog = NewQuestDialog(self, name, taken, self.all_places(), self.story_points())
        answer = self._ask("new_quest", lambda: dialog.answer() if dialog.exec() == QDialog.Accepted else None)
        if not answer:
            return
        name, place, story, marker = answer
        if not sq.good_name(name) or name.lower() in {t.lower() for t in taken}:
            self._say(NAME_BAD if not sq.good_name(name) else QUEST_TAKEN.format(name=name))
            return
        if place is None:
            return
        program = self.program()
        try:
            # (Zodi, 5 November) The sample as test 70's quest was: its reward, own names and speakers too.
            made = qx.sample_quest(name, game, place, self.place_where(), marker, story,
                                   program.squads if program is not None else b"", self._reward_item_words())
        except (OSError, ValueError, es.ScriptError) as exc:
            self._say(CANT_MAKE.format(problem=exc))
            return
        self.quests()[name] = made
        self.folder = name
        self.picked = ("quest",)
        self._say("")
        self._changed()
        self.show_quest()

    def remove_quest(self) -> None:
        edits = self.edits()
        if edits is None:
            return
        sure = self._ask("remove", lambda: QMessageBox.question(self, TITLE, REMOVE_ASK.format(name=edits.folder))
                         == QMessageBox.Yes)
        if not sure:
            return
        self.quests().pop(edits.folder, None)
        self.folder = next(iter(self.quests()), None)
        self.picked = ("quest",)
        self._say("")
        self._changed()
        self.show_quest()

    def add_step(self, kind: Optional[str] = None) -> None:
        """Add a step: where it waits, and whether it plays a scene or a battle first (Zodi, 4 November: no copy of the
        game's; each starts as the sample on map 116), and its name."""
        edits = self.edits()
        game = self.game()
        if edits is None or game is None:
            return
        kind = kind or "scene"
        taken = qx.event_names(edits) + [b.name for b in edits.quest.battles]
        dialog = MakeDialog(self, STEP_TITLE, places=self.all_places(), kind=kind,
                            names={"scene": qx.free_name(qx.SCENE_NAME, taken),
                                   "battle": qx.free_name(qx.BATTLE_NAME, taken)}, taken=taken)
        answer = self._ask("step", lambda: (dialog.place(), dialog.kind(), dialog.name_box.text())
                           if dialog.exec() == QDialog.Accepted else None)
        if not answer:
            return
        place, kind, name = answer
        first = self._sample(kind, name)
        if first is None:
            return
        index = qx.add_step(edits, place, first, game.lengths)
        self.picked = ("start", index)
        self._changed()
        self.show_quest()

    def _sample(self, kind: str, name: str = "") -> Optional[str]:
        """(Zodi, 4 November) A scene or a battle of the quest's own, the sample on map 116 (`quest_edits.
        make_sample_scene`, `make_sample_battle`), named `name` or numbered past the quest's names. Its name, or
        None."""
        edits, game = self.edits(), self.game()
        if edits is None or game is None:
            return None
        program = self.program()
        try:
            if kind == "scene":
                return qx.make_sample_scene(edits, game, name or qx.SCENE_NAME)
            return qx.make_sample_battle(edits, game, name or qx.BATTLE_NAME,
                                         program.squads if program is not None else b"")
        except (OSError, ValueError, es.ScriptError) as exc:
            self._say(CANT_MAKE.format(problem=exc))
            return None

    def _after(self) -> Optional[str]:
        """The event a new scene or battle plays after: the card picked (a unit: its battle); a step's start or end:
        its last event; the quest's own card: the last step's last."""
        quest = self.edits().quest
        kind = self.picked[0] if self.picked else "quest"
        if kind in ("event", "unit") and quest.event_named(self.picked[1]) is not None:
            return self.picked[1]
        steps = qx.steps(quest)
        if kind in ("start", "done"):
            step = next((s for s in steps if s.start == self.picked[1]), None)
        else:
            step = steps[-1] if steps else None
        return step.events[-1] if step is not None and step.events else None

    def add_after(self, kind: str) -> None:
        """Add a scene, Add a battle: (Zodi, 4 November) the sample on map 116, played after the card picked on the same
        visit (see `_after`), named as the next of its kind and picked, its name changed on its card; a quest with no
        step yet gets its first step instead."""
        edits = self.edits()
        if edits is None or self.game() is None:
            return
        after = self._after()
        if after is None:
            self.add_step(kind)
            return
        made = self._sample(kind)
        if made is None:
            return
        qx.insert_after(edits, after, made, self.lengths())
        self.picked = ("event", made)
        self._changed()
        self.show_quest()

    # =========================================================================
    # Asking and saying
    # =========================================================================

    def _ask(self, what: str, ask):
        """A dialog's answer: the suites' (`answers`, first in first out) when they gave one."""
        if self.answers:
            return self.answers.pop(0)
        return ask()

    def _say(self, text: str) -> None:
        """Says something under the steps, or under the places' list with the Places tab (no steps' row then)."""
        self.message.setText(text)
        self.message.setVisible(bool(text))
        self.place_message.setText(text)
        self.place_message.setVisible(bool(text))
        self.item_message.setText(text)
        self.item_message.setVisible(bool(text))

