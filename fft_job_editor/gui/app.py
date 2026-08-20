"""
Main wizard window. Three pages, with a clickable sidebar for jumping
directly to any page, plus Back/Next for a guided sequential flow - because
the target user is someone who wants to make a mod without needing to
already understand modding tools.
"""

from __future__ import annotations

import platform
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import ttk

from typing import Optional

from .. import paths, xml_io

APP_TITLE = "The Ivalice Chronicles Mod Studio"
# Width matters more than height here: the Export page splits into a
# fixed-width form column and a preview, and at 1100 the preview was
# narrow enough to squeeze its tab labels into stubs. Height is left
# at 720 because 1366x768 laptops are still common.
WINDOW_SIZE = "1280x720"

# The three workflow steps, in the order a mod actually gets made. This
# short list is doing real work for a first-time user: it says what making
# a mod consists of.
STEP_TITLES = [
    "General Setup",
    "Edit Game Data",
    "Export Mod",
]

# Pages that aren't steps in that sequence, pinned to the bottom of the
# sidebar and separated from it.
#
# Game Updates is occasional and conditional - most sessions have nothing to
# migrate, because a game patch often changes no table data at all. Sitting
# it between General Setup and Edit Game Data would interrupt the basic
# workflow with a page that usually says "nothing to do", and would imply
# that checking for game updates is a step in making a mod. Bottom-anchored
# secondary navigation is the established convention for exactly this, and
# it keeps the three-step spine intact.
#
# The cost of moving it out of the flow is discoverability, which is paid
# back by SIDEBAR_ATTENTION below: the entry raises its hand when there is
# genuinely something to deal with.
UTILITY_TITLES = [
    "Game Updates",
]

ALL_PAGE_TITLES = STEP_TITLES + UTILITY_TITLES


@dataclass
class WizardState:
    """Everything the steps need to share, kept in one place."""
    ff16tools_cli_path: Optional[Path] = None
    reloaded_ii_path: Optional[Path] = None
    job_table_path: Optional[Path] = None
    job_records: list = field(default_factory=list)   # list[xml_io.JobRecord]
    table_version: str = "1"
    table_source_detail: str = ""
    job_command_records: list = field(default_factory=list)   # list[xml_io.JobCommandRecord]
    job_command_version: str = "1"
    ability_names: dict = field(default_factory=dict)          # live names from AbilityData.xml
    ability_types: dict = field(default_factory=dict)           # live AbilityType from AbilityData.xml
    # job_id -> {field_name: new_string_value}, only fields explicitly included
    edits: dict = field(default_factory=dict)
    # command_id -> {field_name: new_string_value}, same idea for Job Commands
    job_command_edits: dict = field(default_factory=dict)
    # command_id -> {tag: text}: elements an opened mod's JobCommandData.xml
    # carried that this tool has no model for. Written back out verbatim, so
    # a round trip can't quietly change somebody's working mod.
    job_command_preserved: dict = field(default_factory=dict)
    # job_id -> {tag: text} and {table key: {entry id: {tag: text}}}: the
    # same idea for JobData.xml and every Item*Data-style table.
    job_preserved: dict = field(default_factory=dict)
    table_preserved: dict = field(default_factory=dict)

    # Set when "Open Existing Mod" is used, so the Export step knows to update that
    # mod in place (preserving fields it doesn't manage) rather than create
    # a new one elsewhere.
    loaded_mod_root: Optional[Path] = None
    loaded_mod_config: Optional[dict] = None
    loaded_game_mode: Optional[str] = None

    # -- Abilities (.nxd), see nxd_data.py -----------------------------------
    # Where the unpacked game's nxd/ folder lives (source for conversion).
    nxd_unpack_dir: Optional[Path] = None
    # The converted, directly-editable SQLite database (never mutated in
    # place - Export makes a fresh staged copy each time, see step_export.py).
    nxd_sqlite_path: Optional[Path] = None
    nxd_sqlite_source_detail: str = ""
    # language -> list[nxd_data.AbilityRecord], loaded lazily per language
    # (visiting the Abilities tab loads the current language on demand;
    # switching languages loads that one too, rather than all 7 upfront).
    ability_records: dict = field(default_factory=dict)
    # list[nxd_data.OverrideActionRecord] - language-independent, loaded once
    # alongside the first language.
    override_action_records: list = field(default_factory=list)
    # language -> {ability_key: {field_name: new_raw_value}} - mirrors
    # edits/job_command_edits, but values are raw typed Python values (int/
    # str/list) ready for nxd_data.write_ability_edits, not XML text.
    ability_edits: dict = field(default_factory=dict)
    # ability_key -> {field_name: new_raw_value} for OverrideAbilityActionData
    # (Flags12/Flags34/Element/scalars) - shared across every language.
    override_action_edits: dict = field(default_factory=dict)

    def records_by_id(self) -> dict:
        return {r.job_id: r for r in self.job_records}

    def job_commands_by_id(self) -> dict:
        return {r.command_id: r for r in self.job_command_records}

    def edited_job_count(self) -> int:
        return sum(1 for fields in self.edits.values() if fields)

    def edited_job_command_count(self) -> int:
        return sum(1 for fields in self.job_command_edits.values() if fields)

    def override_records_by_key(self) -> dict:
        return {r.key: r for r in self.override_action_records}

    def edited_ability_count(self, language: str) -> int:
        return sum(1 for fields in self.ability_edits.get(language, {}).values() if fields)

    def touched_ability_languages(self) -> list:
        """Languages with at least one ability carrying a real edit, in NXD_LANGUAGES order."""
        from .. import constants as c
        return [
            lang for lang in c.NXD_LANGUAGES
            if any(fields for fields in self.ability_edits.get(lang, {}).values())
        ]

    def edited_ability_total_count(self) -> int:
        """Total ability-in-a-language edits across every language (an ability edited in 2 languages counts twice)."""
        return sum(self.edited_ability_count(lang) for lang in self.ability_edits)

    def edited_override_count(self) -> int:
        return sum(1 for fields in self.override_action_edits.values() if fields)

    def override_touched(self) -> bool:
        return self.edited_override_count() > 0

    def clear_opened_mod_content(self) -> None:
        """
        Forgets everything that came from a previously opened mod.

        Opening a second mod used to leave the first one's game data edits
        in place. `_apply_recovered_nxd` merges rather than replaces, with
        existing state winning - which is right for the sequence it was
        written for (open a mod with no game files, edit, then unpack, and
        the diff that arrives late must not wipe what you typed) and exactly
        wrong across two different mods, where the first one's values won
        every conflict and reappeared inside the second.

        The distinction is *whose* edits they are, not when they arrived, so
        the fix belongs here at the point a different mod is opened rather
        than in the merge. Everything below is derived from a mod folder,
        and none of it is meaningful once that folder is no longer the one
        being edited.

        Deliberately NOT cleared: the unpacked game files, the reference
        tables, and the view preferences. Those belong to the machine and
        the session, not to any one mod.
        """
        self.ability_edits = {}
        self.item_edits = {}
        self.chara_name_edits = {}
        self.poach_edits = {}
        self.override_action_edits = {}
        self.entry_edits = {}
        self.entry_rekeys = {}
        self.entry_dropped = set()
        self.unmodelled_table_edits = {}
        self.job_command_preserved = {}
        self.job_preserved = {}
        self.table_preserved = {}
        self.texture_edits = {}
        self.sound_file_replacements = {}
        self.other_file_replacements = {}
        self.mod_sqlite_path = None
        # Force the Textures and Sounds tabs to rescan rather than show the
        # previous mod's staged entries.
        self.texture_tree = None
        self.sound_tree = None

    def has_any_ability_edits(self) -> bool:
        return self.edited_ability_total_count() > 0 or self.override_touched()

    # -- Items (ItemData.xml + 5 "Additional Data" tables + ItemShopsData.xml,
    # all via item_xml_io.py) -------------------------------------------------
    item_table_paths: dict = field(default_factory=dict)     # table_key -> Path (source XML)
    item_table_records: dict = field(default_factory=dict)    # table_key -> list[item_xml_io.ItemTableRecord]
    item_table_versions: dict = field(default_factory=dict)   # table_key -> version str
    # table_key -> {item_id: {field_name: new_string_value}}
    item_table_edits: dict = field(default_factory=dict)

    # Item-xx (nxd, per-language name/description) - lives in the SAME
    # nxd_sqlite_path as Abilities; a single converted database can hold both
    # Ability-xx and Item-xx tables side by side (see nxd_data.py).
    item_records: dict = field(default_factory=dict)   # language -> list[nxd_data.ItemRecord]
    item_edits: dict = field(default_factory=dict)      # language -> {item_id: {field: value}}

    def item_table_records_by_id(self, table_key: str) -> dict:
        return {r.item_id: r for r in self.item_table_records.get(table_key, [])}

    def edited_item_table_count(self, table_key: str) -> int:
        return sum(1 for fields in self.item_table_edits.get(table_key, {}).values() if fields)

    # table_keys that live in item_table_edits (so Export's generic
    # item_xml_io.ALL_SPECS loop picks them up for free) but aren't one of
    # the six real Item*Data tables - each has its own tab/counters instead
    # (see edited_maptrap_count(), edited_ability_effect_count(),
    # edited_ability_animation_count() below) and is kept out of Items' own
    # displayed total. Public (not underscore-prefixed) since step_export.py
    # also needs it to keep its own Items preview in sync with this list.
    NON_ITEM_TABLE_KEYS = ("map_trap", "ability_effect", "ability_animation", "ability")

    def edited_item_table_total_count(self) -> int:
        return sum(
            self.edited_item_table_count(k) for k in self.item_table_edits
            if k not in self.NON_ITEM_TABLE_KEYS
        )

    def edited_item_text_count(self, language: str) -> int:
        return sum(1 for fields in self.item_edits.get(language, {}).values() if fields)

    def edited_item_text_total_count(self) -> int:
        return sum(self.edited_item_text_count(lang) for lang in self.item_edits)

    def touched_item_languages(self) -> list:
        from .. import constants as c
        return [
            lang for lang in c.NXD_LANGUAGES
            if any(fields for fields in self.item_edits.get(lang, {}).values())
        ]

    def has_any_item_edits(self) -> bool:
        return self.edited_item_table_total_count() > 0 or self.edited_item_text_total_count() > 0

    # -- Encounters (OverrideEntryData + CharaName-xx, both via nxd_data.py) --
    # CharaName-xx (per-language unit names) - lives in the SAME
    # nxd_sqlite_path as Abilities/Items.
    chara_name_records: dict = field(default_factory=dict)   # language -> list[nxd_data.CharaNameRecord]
    chara_name_edits: dict = field(default_factory=dict)      # language -> {key: {field: value}}

    # OverrideEntryData - shared across languages, keyed by (key, key2) - a
    # unit slot within an encounter. No dense reference table backs this
    # one (see nxd_data.EntryRecord's docstring), so entry_records is
    # whatever's currently in the database (existing overrides only);
    # brand new (key, key2) combos are created on first edit.
    entry_records: list = field(default_factory=list)   # list[nxd_data.EntryRecord]
    entry_edits: dict = field(default_factory=dict)       # {(key, key2): {field: value}}

    # Rows the mod moves to a different address, and rows it removes.
    #
    # New rows can't be added in a way the game picks up (Zodi's own
    # in-game testing), so *moving* an existing row is how a mod gets a
    # unit slot the game doesn't otherwise have - and because a move
    # vacates one address as it fills another, the row count stays put by
    # construction, which is the property that made her Dark Knight
    # Expansion work. Both dicts are keyed by a row's ORIGIN address (where
    # it sits in the working database), so a row that gets moved twice, or
    # moved and moved back, keeps one stable identity and one set of edits.
    entry_rekeys: dict = field(default_factory=dict)      # {(key, key2): (new_key, new_key2)}
    entry_dropped: set = field(default_factory=set)       # {(key, key2)}

    def entry_records_by_key(self) -> dict:
        return {(r.key, r.key2): r for r in self.entry_records}

    def entry_address(self, origin: tuple) -> tuple:
        """Where a row currently lives, following any move applied to it."""
        return self.entry_rekeys.get(origin, origin)

    def entry_origins_by_address(self) -> dict:
        """{address: origin} for every row that hasn't been removed - the map the tab and its collision check both read."""
        result = {}
        for record in self.entry_records:
            origin = (record.key, record.key2)
            if origin in self.entry_dropped:
                continue
            result[self.entry_address(origin)] = origin
        return result

    def entry_address_conflict(self, origin: tuple, address: tuple):
        """The origin of whichever *other* row already occupies an address, or None."""
        occupant = self.entry_origins_by_address().get(address)
        return occupant if occupant is not None and occupant != origin else None

    def entry_row_count(self) -> int:
        """How many rows the exported table will have."""
        return len(self.entry_origins_by_address())

    def entry_baseline_row_count(self) -> int:
        return len(self.entry_records)

    def edited_entry_count(self) -> int:
        return sum(1 for fields in self.entry_edits.values() if fields)

    def changed_entry_row_count(self) -> int:
        """
        How many rows this mod changes, counting each row ONCE.

        A repurposed row is normally both moved and edited, so adding the
        three collections together double-counts it - the Dark Knight
        Expansion's ten repurposed rows reported as twenty.
        """
        return len(set(self.entry_edits) | set(self.entry_rekeys) | set(self.entry_dropped))

    def entry_structure_changed(self) -> bool:
        return bool(self.entry_rekeys or self.entry_dropped)

    def has_entry_changes(self) -> bool:
        return self.edited_entry_count() > 0 or self.entry_structure_changed()

    def edited_chara_name_count(self, language: str) -> int:
        return sum(1 for fields in self.chara_name_edits.get(language, {}).values() if fields)

    def edited_chara_name_total_count(self) -> int:
        return sum(self.edited_chara_name_count(lang) for lang in self.chara_name_edits)

    def touched_chara_name_languages(self) -> list:
        from .. import constants as c
        return [
            lang for lang in c.NXD_LANGUAGES
            if any(fields for fields in self.chara_name_edits.get(lang, {}).values())
        ]

    def has_any_encounter_edits(self) -> bool:
        return self.has_entry_changes() or self.edited_chara_name_total_count() > 0

    # -- Poaching (PoachItem-xx, nxd, per-language) - see nxd_data.py -------
    # Lives in the SAME nxd_sqlite_path as Ability/Item/CharaName.
    poach_records: dict = field(default_factory=dict)   # language -> list[nxd_data.PoachItemRecord]
    poach_edits: dict = field(default_factory=dict)      # language -> {key: {field: value}}

    def edited_poach_count(self, language: str) -> int:
        return sum(1 for fields in self.poach_edits.get(language, {}).values() if fields)

    def edited_poach_total_count(self) -> int:
        return sum(self.edited_poach_count(lang) for lang in self.poach_edits)

    def touched_poach_languages(self) -> list:
        from .. import constants as c
        return [
            lang for lang in c.NXD_LANGUAGES
            if any(fields for fields in self.poach_edits.get(lang, {}).values())
        ]

    def has_any_poach_edits(self) -> bool:
        return self.edited_poach_total_count() > 0

    # -- Treasure Hunter (MapTrapFormationData.xml, via item_xml_io.py) -----
    # "map_trap" is just one more key in item_xml_io.ALL_SPECS, so General
    # Setup's fetch loop (reference data) AND Export's diff-gathering loop
    # (edited entries) already handle it generically for free by reusing
    # item_table_paths/item_table_records/item_table_versions/
    # item_table_edits["map_trap"] - no Treasure-Hunter-specific storage
    # needed at all, just its own accessor methods so it reads as its own
    # tab (not folded into Items' own counts - see edited_item_table_total_
    # count's "map_trap" exclusion above).
    def maptrap_records_by_id(self) -> dict:
        return {r.item_id: r for r in self.item_table_records.get("map_trap", [])}

    def edited_maptrap_count(self) -> int:
        return self.edited_item_table_count("map_trap")

    def has_any_maptrap_edits(self) -> bool:
        return self.edited_maptrap_count() > 0

    # -- Ability Effect (AbilityEffectNumberFilterData.xml) and Unit
    # Animations (AbilityTypeData.xml), both via item_xml_io.py -------------
    # Same "just one more item_xml_io.ALL_SPECS key" story as Treasure
    # Hunter directly above - but unlike Treasure Hunter, both live as their
    # own sub-tabs INSIDE the Abilities tab itself (see step_abilities.py),
    # keyed by the same ability id as Ability Info/Flags/Element/Overrides.
    # Deliberately NOT folded into has_any_ability_edits() below - that
    # method specifically gates whether the nxd binary re-export pipeline
    # needs to run (ability_edits/override_action_edits), and these two are
    # pure XML diffs that pipeline never touches; folding them in would
    # spuriously trigger a "converting to .nxd" export step for edits that
    # don't need one. They do still need their own place in Export's
    # "nothing edited yet" validation - see step_export.py's _validate_form.
    def ability_effect_records_by_id(self) -> dict:
        return {r.item_id: r for r in self.item_table_records.get("ability_effect", [])}

    def edited_ability_effect_count(self) -> int:
        return self.edited_item_table_count("ability_effect")

    def has_any_ability_effect_edits(self) -> bool:
        return self.edited_ability_effect_count() > 0

    def ability_animation_records_by_id(self) -> dict:
        return {r.item_id: r for r in self.item_table_records.get("ability_animation", [])}

    def edited_ability_animation_count(self) -> int:
        return self.edited_item_table_count("ability_animation")

    def has_any_ability_animation_edits(self) -> bool:
        return self.edited_ability_animation_count() > 0

    # -- Ability's own base stats - AbilityData.xml itself (ChanceToLearn/
    # Flags/AbilityType/AIBehaviorFlags - JPCost deliberately excluded, see
    # constants.py), via item_xml_io.py -----------------------------------
    # Same "just one more item_xml_io.ALL_SPECS key" story as Ability Effect/
    # Unit Animations directly above, also its own Abilities sub-tab, keyed
    # "ability" (matching TABLE_FILENAMES["ability"]) - NOT to be confused
    # with ability_edits/ability_records above, which are the separate,
    # unrelated nxd-backed Ability-xx data (Name/Description/JpCost/etc.).
    # Deliberately NOT folded into has_any_ability_edits() for the same
    # reason Ability Effect/Unit Animations aren't - pure XML diff, the nxd
    # re-export pipeline never touches it.
    def ability_data_records_by_id(self) -> dict:
        return {r.item_id: r for r in self.item_table_records.get("ability", [])}

    def edited_ability_data_count(self) -> int:
        return self.edited_item_table_count("ability")

    def has_any_ability_data_edits(self) -> bool:
        return self.edited_ability_data_count() > 0

    # -- Textures (.tga/.tex, direct file replacement - no nxd/sqlite
    # involved, just a real unpacked game folder) -----------------------
    unpacked_game_dir: Optional[Path] = None
    texture_tree: object = None   # texture_data.TextureTreeNode, cached after first scan
    # relative_path (forward-slashed, e.g. "ui/ffto/common/face/texture/blkface_05_04_uitx.tex")
    # -> {"source_path": Path, "is_face_texture": bool}
    texture_edits: dict = field(default_factory=dict)

    def rebased_table_count(self) -> int:
        """Tables merged onto the game's newer copy by the Game Updates page."""
        return sum(1 for rows in self.unmodelled_table_edits.values() if rows)

    def carried_through_file_count(self) -> int:
        """
        Files from an opened mod that this tool has no tab for and passes
        through unchanged.

        Counted so the Export summary can say they exist. They were
        invisible there - the only mention was a log line *after* the export
        had already run - which meant a mod whose only content was carried
        through files read as "nothing has been edited yet".
        """
        return len(self.other_file_replacements) + len(self.sound_file_replacements)

    def edited_texture_count(self) -> int:
        return len(self.texture_edits)

    def has_any_texture_edits(self) -> bool:
        return bool(self.texture_edits)

    # -- Sounds (.sab, via AudioMog - see sound_data.py) --------------------
    # Same unpacked_game_dir as Textures above - sound archives are real
    # files in that same folder (under sound/), not a separate database.
    audiomog_exe_path: Optional[Path] = None
    sound_tree: object = None   # sound_data.SoundTreeNode, cached after first scan
    # relative_path (forward-slashed, e.g. "sound/music/music_00067.sab") ->
    # {track_index: {"source_path": Path, "loop_start": Optional[int], "loop_end": Optional[int]}}
    sound_edits: dict = field(default_factory=dict)

    def edited_sound_track_count(self) -> int:
        return sum(len(tracks) for tracks in self.sound_edits.values())

    def edited_sound_file_count(self) -> int:
        return sum(1 for tracks in self.sound_edits.values() if tracks)

    def has_any_sound_edits(self) -> bool:
        return self.edited_sound_track_count() > 0 or bool(self.sound_file_replacements)

    # A .sab recovered whole from an opened mod: relative_path -> Path to
    # the mod's own copy. Kept separate from sound_edits because that dict
    # describes *track* replacements (source .wav, loop points), and none of
    # that survives inside a repacked archive - all that can honestly be
    # said is "this mod replaces this file", so it's copied through as-is
    # on export rather than rebuilt from tracks that can't be recovered.
    sound_file_replacements: dict = field(default_factory=dict)

    def replaced_sound_file_count(self) -> int:
        return len(self.sound_file_replacements)

    # Files a mod replaces that this tool has no tab for (anything under
    # FFTIVC/data/<mode>/ that isn't nxd, a texture or a sound). Carried
    # through untouched so opening and re-exporting can't quietly drop
    # parts of someone's mod.
    other_file_replacements: dict = field(default_factory=dict)
    # {table name: {key tuple: {column: value}}} - changes to .nxd tables
    # that have no editor tab, carried over by the Game Updates page's
    # Rebase option and written back out at export. Distinct from
    # other_file_replacements, which passes a mod's file through whole; this
    # regenerates the table from the game's current one with these on top.
    unmodelled_table_edits: dict = field(default_factory=dict)
    # The opened mod's own .nxd converted to SQLite, once that has happened.
    # Read by the Game Updates page; None until a mod has been opened and
    # converted, and cleared the moment a different mod is opened.
    mod_sqlite_path: object = None



class WizardApp(tk.Tk):
    def __init__(self):
        # Before the first window exists - see _claim_taskbar_identity.
        self._claim_taskbar_identity()
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(WINDOW_SIZE)
        self.minsize(900, 600)

        self.state_data = WizardState()
        self.current_step = 0
        self.step_frames: list[ttk.Frame] = []
        # Sidebar indices currently asking for attention. See
        # set_sidebar_alert - Game Updates uses this so that moving it out
        # of the main flow doesn't make it undiscoverable.
        self._sidebar_alerts: set = set()

        self._set_icon()
        self._build_chrome()
        self._build_steps()
        self._show_step(0)

    @staticmethod
    def _claim_taskbar_identity() -> None:
        """
        Tells Windows this is its own application, not "some Python".

        The window icon was always right, but the *taskbar* button showed
        the Python snake, because Windows groups taskbar buttons by
        AppUserModelID and a script inherits the host interpreter's. Setting
        an explicit one makes the taskbar use this window's own icon, and
        stops Mod Studio being grouped with any other Python program that
        happens to be running.

        Must happen before the first window exists, which is why it's called
        at the top of __init__ rather than alongside the icon itself.

        Windows-only and entirely cosmetic, so every failure is swallowed -
        an old Windows without the call, or a locked-down environment, isn't
        a reason not to start.
        """
        if platform.system() != "Windows":
            return
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Zodi.IvaliceChroniclesModStudio")
        except Exception:  # noqa: BLE001 - cosmetic, never fatal
            pass

    def _set_icon(self) -> None:
        """Best-effort - the icon is cosmetic, so any failure here is silently ignored."""
        assets_dir = paths.project_root() / "assets"
        try:
            if platform.system() == "Windows":
                ico_path = assets_dir / "icon.ico"
                if ico_path.exists():
                    # `default=` rather than a bare path: it sets the icon
                    # for this window *and* every dialog opened later, so
                    # file pickers and message boxes stop falling back to
                    # the interpreter's icon.
                    self.iconbitmap(default=str(ico_path))
                    return
            png_path = assets_dir / "icon_256.png"
            if png_path.exists():
                self._icon_image = tk.PhotoImage(file=str(png_path))  # keep a reference alive
                self.iconphoto(True, self._icon_image)
        except (tk.TclError, OSError):
            pass

    # -- chrome (sidebar + nav buttons) ------------------------------------


    def notify_data_loaded(self, exclude=None) -> None:
        """
        Re-runs on_show for every step except `exclude`, the step that is
        announcing the change.

        General Setup loads its reference tables and adopts the previous
        session's unpacked folder on a background thread, so the data lands
        some seconds after launch. Nothing told the other steps, and the
        only refresh they got was their own on_show - so opening Edit Game
        Data quickly after launch showed empty job/ability/item lists, and
        the only cure was going back to General Setup and waiting. Now the
        data announces itself.

        `exclude` is the CALLER, not the visible step. Skipping the visible
        step was the obvious first guess and is exactly backwards: the
        visible step is the one the user is staring at, so it's the one that
        most needs redrawing. Only the caller has to be skipped, because
        General Setup announces this from inside its own queue handler and
        re-entering its on_show there would restart the fetch that just
        finished.
        """
        for frame in self.step_frames:
            if frame is exclude:
                continue
            try:
                frame.on_show()
            except Exception:  # noqa: BLE001 - a refresh must never break the loader
                pass

    def _tame_spinboxes(self) -> None:
        """
        Stops ttk.Spinbox leaving its value highlighted after the arrows are
        clicked.

        Tk selects the whole entry when a spin arrow fires, so nudging a
        stat left it sitting in selection blue - and because nothing clears
        it, the highlight followed you to the next record you picked, making
        an untouched field look like it was mid-edit.

        Done with bind_class rather than per widget, so it covers every
        spinbox in the app including any added later. after_idle because the
        selection is applied by Tk's own handler after this one returns.
        """
        def clear(event):
            widget = event.widget

            def do_clear():
                try:
                    widget.selection_clear()
                except tk.TclError:
                    pass  # widget went away between the click and the idle pass

            # Synchronously FIRST. Tk has already applied the selection by
            # the time <<Increment>> fires, so clearing here happens before
            # the redraw and nothing is ever painted blue. Doing this only
            # at idle meant select -> paint -> clear -> paint, which read as
            # a flash on one click and a strobe on several.
            do_clear()
            # And again at idle, for any path that re-selects after this
            # handler returns. On the common path the selection is already
            # gone, so this is a no-op and costs no second repaint.
            widget.after_idle(do_clear)

        for sequence in ("<<Increment>>", "<<Decrement>>", "<ButtonRelease-1>"):
            self.bind_class("TSpinbox", sequence, clear, add="+")

        # Switching a notebook tab focuses a child of the new tab, with the
        # same two visible side effects as switching pages. Bound on the
        # class so every notebook in the app is covered - Edit Game Data's
        # ten tabs, each tab's own sub-tabs, Export's previews, Game
        # Updates' three - with nothing for a future tab to forget.
        def park(event):
            widget = event.widget
            try:
                current = widget.nametowidget(widget.select())
            except (tk.TclError, KeyError):
                return
            widget.after_idle(lambda: self._park_focus(current))

        self.bind_class("TNotebook", "<<NotebookTabChanged>>", park, add="+")

        # A clicked button keeps focus, and so keeps its dashed ring, long
        # after the click that put it there - which reads as "this button is
        # somehow still active" rather than as a focus cue. Focus is handed
        # back to the surrounding page on mouse release.
        #
        # Only for the mouse. Tab navigation still moves focus normally and
        # still shows the ring, which is the one context where it earns its
        # place: it's the only cue for which button Enter would fire.
        def release(event):
            # No state check: a button disabled by its own command handler
            # still gets this event, and skipping it left the dashed ring
            # drawn for as long as the button stayed disabled.
            widget = event.widget
            widget.after_idle(lambda: self._park_focus(widget))

        self.bind_class("TButton", "<ButtonRelease-1>", release, add="+")

    def _build_chrome(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        # Drop the dashed focus ring ttk draws inside a clicked notebook tab.
        # It's the "Notebook.focus" element in clam's default tab layout, and
        # it made every sub-tab in Export's Mod Contents look like it had a
        # dotted box around its text the moment you selected it. Removing the
        # element loses nothing: which tab is current is already obvious from
        # the raised, lighter tab itself, so the ring only ever duplicated
        # that in an uglier way.
        style.layout("TNotebook.Tab", [
            ("Notebook.tab", {"sticky": "nswe", "children": [
                ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
                    ("Notebook.label", {"side": "top", "sticky": ""}),
                ]}),
            ]}),
        ])

        # Same ring, same reasoning, on checkbuttons and radiobuttons. This
        # one is everywhere rather than just on tabs: every field in Edit
        # Game Data has an "include this field" checkbox, so ticking one
        # left a dotted box around its label, and so did the view toggles
        # and Export's "Show every section". A checkbox's own tick already
        # says what a focus ring would.
        #
        # TButton is deliberately left alone - a focus ring on a push button
        # is conventional, and it's the only cue for which button Enter
        # would fire.
        style.layout("TCheckbutton", [
            ("Checkbutton.padding", {"sticky": "nswe", "children": [
                ("Checkbutton.indicator", {"side": "left", "sticky": ""}),
                ("Checkbutton.label", {"side": "left", "sticky": "w"}),
            ]}),
        ])
        # A readonly combobox turns solid blue the moment it holds focus, so
        # arriving on a tab that happened to focus one showed a highlighted
        # value nobody had touched - Language on the Abilities tab was the
        # usual culprit. It isn't a text selection, which is what made it
        # confusing to chase: clam maps the *field background* itself to
        # "#4a6984" for the readonly+focus state, so the whole box fills in.
        #
        # Restored to the ordinary readonly colour. Nothing is lost - a
        # readonly combobox has no text you could cut, copy or type over, so
        # painting a selection over it says nothing true. The dropdown arrow
        # and the list still behave exactly as before.
        readonly_field = style.lookup("TCombobox", "fieldbackground", ["readonly"]) or "#dcdad5"
        text_colour = style.lookup("TCombobox", "foreground", ["readonly"]) or "black"
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "focus", readonly_field),
                             ("readonly", readonly_field)],
            selectbackground=[("readonly", readonly_field)],
            selectforeground=[("readonly", text_colour)],
        )

        style.layout("TRadiobutton", [
            ("Radiobutton.padding", {"sticky": "nswe", "children": [
                ("Radiobutton.indicator", {"side": "left", "sticky": ""}),
                ("Radiobutton.label", {"side": "left", "sticky": "w"}),
            ]}),
        ])
        # The tag styles Edit Game Data's view toggles key off. Registered
        # here so they exist before any panel is built.
        from .step_editor import install_field_display_styles
        install_field_display_styles(style)

        self._tame_spinboxes()

        style.configure("Sidebar.TFrame", background="#1f2430")
        style.configure("SidebarLogo.TLabel", background="#1f2430")
        style.configure(
            "SidebarStep.TLabel",
            background="#1f2430", foreground="#8b93a7",
            font=("Segoe UI", 11), padding=(16, 10),
        )
        style.configure(
            "SidebarStepActive.TLabel",
            background="#1f2430", foreground="#ffffff",
            font=("Segoe UI", 11, "bold"), padding=(16, 10),
        )
        # A hairline between the workflow steps and the utility pages below.
        # Slightly lighter than the sidebar rather than a hard line: it needs
        # to group, not to divide the sidebar into two competing halves.
        style.configure("SidebarRule.TFrame", background="#2f3646")
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("SubHeader.TLabel", font=("Segoe UI", 10), foreground="#555555")
        # A plain ttk.Button renders noticeably taller than a Combobox/Checkbutton in the
        # "clam" theme (33px vs 23px, confirmed by measuring both) - fine for a one-off button
        # on its own row, but stacked 16/6 times per SearchableAbilityRow (Job Commands'
        # Abilities/Reaction-Support-Movement sub-tabs) that extra height per row visibly
        # loosens up what used to be a tight list. This style trims the button's own internal
        # padding back down to match the row's other widgets exactly (23px), so adding the
        # "Edit \u2192" jump button there didn't change the row spacing at all.
        style.configure("Compact.TButton", padding=(6, 0))

        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)

        self.sidebar = ttk.Frame(outer, style="Sidebar.TFrame", width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self._build_sidebar_logo()

        self.sidebar_labels: list[ttk.Label] = []
        for index, title in enumerate(STEP_TITLES):
            lbl = ttk.Label(self.sidebar, text=title, style="SidebarStep.TLabel", anchor="w")
            lbl.pack(fill="x")
            lbl.configure(cursor="hand2")
            lbl.bind("<Button-1>", lambda _e, i=index: self._show_step(i))
            self.sidebar_labels.append(lbl)

        # Utility pages go to the bottom, packed in reverse so they read
        # top-to-bottom, with a hairline above them. `side="bottom"` rather
        # than a spacer frame so they stay pinned however tall the window
        # gets.
        #
        # The bottom spacer is packed first so it ends up furthest down:
        # without it the last entry sits flush against the window edge,
        # which reads as clipped rather than anchored. Caught by screenshot.
        ttk.Frame(self.sidebar, style="Sidebar.TFrame", height=14).pack(side="bottom", fill="x")
        # Packed in reverse so they read top-to-bottom, but stored **by page
        # index**, not in the order they were created.
        #
        # They used to be appended as they were packed, so with two utility
        # pages the list order stopped matching the page order and the
        # sidebar highlighted the wrong entry - Settings was open while Game
        # Updates looked selected. With one utility page the two orders
        # happened to agree, which is why it went unnoticed.
        self.sidebar_labels.extend([None] * len(UTILITY_TITLES))
        for offset, title in reversed(list(enumerate(UTILITY_TITLES))):
            index = len(STEP_TITLES) + offset
            lbl = ttk.Label(self.sidebar, text=title, style="SidebarStep.TLabel", anchor="w")
            lbl.pack(side="bottom", fill="x")
            lbl.configure(cursor="hand2")
            lbl.bind("<Button-1>", lambda _e, i=index: self._show_step(i))
            self.sidebar_labels[index] = lbl
        ttk.Frame(self.sidebar, style="SidebarRule.TFrame", height=1).pack(
            side="bottom", fill="x", padx=16, pady=(10, 6)
        )

        right = ttk.Frame(outer)
        right.pack(side="left", fill="both", expand=True)

        self.content_container = ttk.Frame(right, padding=20)
        self.content_container.pack(fill="both", expand=True)

        # No Back/Next/Finish bar. It predates the clickable sidebar, which
        # does the same navigation better (any step, one click, in either
        # direction). "Finish" in particular was a trap: it was a pure
        # duplicate of the Export page's own "Generate / Overwrite Mod"
        # button - same validation, same call - sitting where "Next" used
        # to be, so it read like a step you had to complete rather than a
        # second copy of the button right above it.

    def _build_sidebar_logo(self) -> None:
        assets_dir = paths.project_root() / "assets"
        png_path = assets_dir / "icon_64.png"
        if not png_path.exists():
            return
        try:
            self._sidebar_logo_image = tk.PhotoImage(file=str(png_path))
        except (tk.TclError, OSError):
            return
        logo_frame = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
        logo_frame.pack(fill="x", pady=(20, 12))
        ttk.Label(logo_frame, image=self._sidebar_logo_image, style="SidebarLogo.TLabel").pack()

    def _build_steps(self) -> None:
        # Imported here to avoid circular imports at module load time.
        from .step_setup import SetupStep
        from .step_editor import JobEditorStep
        from .step_export import ExportStep
        from .step_game_updates import GameUpdatesStep

        # Order here must match STEP_TITLES + UTILITY_TITLES, since the
        # sidebar indexes into step_frames by position.
        step_classes = [SetupStep, JobEditorStep, ExportStep, GameUpdatesStep]
        for step_cls in step_classes:
            frame = step_cls(self.content_container, self)
            frame.place(x=0, y=0, relwidth=1, relheight=1)
            self.step_frames.append(frame)

    # -- navigation ---------------------------------------------------------

    def _show_step(self, index: int) -> None:
        self.current_step = index
        self._restyle_sidebar()
        frame = self.step_frames[index]
        frame.tkraise()
        frame.on_show()
        self._park_focus(frame)

    def park_focus(self, widget) -> None:
        """Public wrapper, for pages that need to drop focus themselves."""
        self._park_focus(widget)

    @staticmethod
    def _park_focus(widget) -> None:
        """
        Puts keyboard focus on the container rather than on whatever child
        Tk would pick.

        Arriving on a page, Tk hands focus to the first widget that will
        take it - which then draws itself as focused. That produced two
        complaints that look unrelated and aren't: a dashed ring around a
        button nobody clicked, and a dropdown showing its value highlighted
        as though it were mid-edit.

        Parking focus on the frame fixes both without removing focus
        indication, which would be the wrong trade - the ring is the only
        cue for which button Enter fires, and someone navigating by keyboard
        needs it. Tabbing still works and still shows where you are; it just
        starts from nowhere instead of from an arbitrary widget.
        """
        # Focus goes to the nearest enclosing frame, not to the toplevel.
        # Focusing a toplevel leaves the window's internal focus where it
        # was, so the widget kept its ring and the whole thing looked like
        # it hadn't worked - which for a while it hadn't.
        try:
            target = widget
            while target is not None and not isinstance(target, (ttk.Frame, tk.Frame)):
                target = getattr(target, "master", None)
            (target or widget).focus_set()
        except (tk.TclError, AttributeError):
            pass

    def _restyle_sidebar(self) -> None:
        """
        Applies the active styling to every sidebar entry.

        Every entry is styled identically - grey when idle, white when
        current - including Game Updates. An earlier version turned it
        amber when a mod needed attention, which stood out precisely
        because none of the other three ever change colour; the
        inconsistency read as a glitch rather than as a signal. The page
        itself says loudly what needs doing once it's open, which is where
        the detail belongs anyway.
        """
        for i, lbl in enumerate(self.sidebar_labels):
            active = i == self.current_step
            lbl.configure(style="SidebarStepActive.TLabel" if active
                          else "SidebarStep.TLabel")

    def set_sidebar_alert(self, title: str, active: bool) -> None:
        """
        Records that a page wants attention, by page title.

        Currently draws nothing - the sidebar deliberately styles every
        entry the same way (see _restyle_sidebar). Kept because the state
        itself is meaningful and the pages already report it honestly, so a
        future non-colour cue has somewhere to hook in without every caller
        changing.

        By title rather than index so callers don't have to know the page
        order - which is exactly the sort of coupling that breaks silently
        the next time a page is added or moved.
        """
        try:
            index = ALL_PAGE_TITLES.index(title)
        except ValueError:
            return
        if active:
            self._sidebar_alerts.add(index)
        else:
            self._sidebar_alerts.discard(index)
        self._restyle_sidebar()


class WizardStepFrame(ttk.Frame):
    """Base class every step inherits from."""

    def __init__(self, parent, app: WizardApp):
        super().__init__(parent)
        self.app = app

    def on_show(self) -> None:
        """Called every time the user navigates to this step."""



def main() -> None:
    app = WizardApp()
    app.mainloop()


if __name__ == "__main__":
    main()
