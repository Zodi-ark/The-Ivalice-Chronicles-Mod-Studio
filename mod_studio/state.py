"""
The application's shared state.

Everything the interface's pages need to pass between them, in one place.
This is a plain dataclass with no interface framework anywhere in it - it
knows what a mod contains and how to count what has been edited, and
nothing about how any of that is displayed.

It lived in `gui/app.py` until the Qt rewrite made the distinction matter.
Two reasons it moved:

- It is not interface code. It imports no interface framework, and should
  not gain one. A page reads and writes this; it does not own it.
  (Deliberately not naming the frameworks here: a plain `grep` for them
  across the engine is a check people actually run, and prose that
  mentions them makes this file a false positive.)
- `gui/` is being replaced wholesale. Anything genuinely portable that sits
  inside the folder being replaced is at risk of being rewritten by
  accident, and this is 440 lines of accumulated rules about what counts as
  an edit - `edited_item_table_total_count` excluding "map_trap",
  `clear_opened_mod_content` knowing exactly which state belongs to a mod
  and which belongs to the machine - that would be expensive to rediscover.

Moved verbatim: the class body is byte-identical to the version that was in
`gui/app.py`, apart from four deferred `constants` imports changing `..` to
`.` now that this module is one level up. `gui.app` re-exports the name, so
existing imports keep working and both spellings are the same object.

The imports stay deferred rather than being hoisted to the top. That is not
tidiness lost: `constants` is a large module and these are the only four
places the state needs it, but more importantly hoisting would be a second
change riding along with a move, and the point of doing this on its own is
that anything which breaks afterwards has exactly one possible cause.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


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
        from . import constants as c
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
        # Every registered per-language nxd table, rather than a list that
        # has to be remembered when one is added. A table missed here keeps
        # the previous mod's edits alive in the next one.
        from . import nxd_data
        for _key in nxd_data.ALL_NXD_SPECS:
            self.set_nxd_edits_for(_key, {})
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
        # Jobs, Job Commands and the XML tables, which this method's own
        # docstring has always promised and never delivered.
        #
        # Two call sites compensated by clearing them straight afterwards,
        # and a third - the setup page - happened to assign over them, so
        # the gap only showed when someone added a fourth caller. A method
        # named "forgets everything that came from a previously opened mod"
        # that forgets most of it is a trap, not an API.
        self.edits = {}
        self.job_command_edits = {}
        self.item_table_edits = {}
        self.derived_table_edits = {}
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

    # ---- XML tables with no hand-written spec -----------------------------
    # Keyed by XML FILENAME ("StatusEffectData.xml"), not by a short table
    # key, because there is no key to use: these tables have no entry in
    # ALL_SPECS or TABLE_FILENAMES. The filename is the only identifier
    # they have, and it is also exactly what the export has to write, so
    # using it removes a lookup that could go wrong.
    #
    # Deliberately a SEPARATE store from item_table_edits rather than more
    # keys in it. The two are not the same thing: a curated table has a
    # spec that knows which fields are flags and which are booleans, and a
    # derived one has no such knowledge and must not pretend to. Mixing
    # them would make "which kind is this" a runtime guess at every use.
    derived_table_records: dict = field(default_factory=dict)   # filename -> list[ItemTableRecord]
    derived_table_versions: dict = field(default_factory=dict)  # filename -> version str
    derived_table_edits: dict = field(default_factory=dict)     # filename -> {id: {field: value}}

    def edited_derived_table_count(self, filename: str) -> int:
        return sum(1 for fields
                   in self.derived_table_edits.get(filename, {}).values()
                   if fields)

    def edited_derived_table_total(self) -> int:
        return sum(self.edited_derived_table_count(name)
                   for name in self.derived_table_edits)

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
        from . import constants as c
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
        from . import constants as c
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
        from . import constants as c
        return [
            lang for lang in c.NXD_LANGUAGES
            if any(fields for fields in self.poach_edits.get(lang, {}).values())
        ]

    def has_any_poach_edits(self) -> bool:
        return self.edited_poach_total_count() > 0

    # -- Jobs, the per-language half (Job-xx, nxd) --------------------------
    # The job's NAME and DESCRIPTION, which is a different table from
    # JobData.xml's stats even though both are called Job. The XML half
    # lives in `edits` above; these two are the text the player reads.
    # NOT `job_records`/`job_edits` - both names were already taken by
    # JobData.xml's reference rows and per-field edits above. As dataclass
    # fields, redeclaring them does not raise; the second declaration wins
    # and the XML half of the Jobs tab silently starts reading a dict.
    job_text_records: dict = field(default_factory=dict)  # language -> list[nxd_data.JobTextRecord]
    job_text_edits: dict = field(default_factory=dict)    # language -> {job_id: {field: value}}

    # Same pairing for JobCommand-xx. NOT `job_command_records`/`_edits`,
    # which are JobCommandData.xml's above.
    #: Stores for the tables derived from bundled layouts.
    #:
    #: `{attr_name: {language: ...}}`, one entry per derived table, created
    #: on demand. A declared field per table would be 106 of them for the
    #: 53 localized layouts, and a redeclared dataclass field does not
    #: raise - the second silently wins.
    nxd_stores: dict = field(default_factory=dict)

    job_command_text_records: dict = field(default_factory=dict)
    job_command_text_edits: dict = field(default_factory=dict)

    # -- Every per-language nxd table, by registry key ----------------------
    # The five methods below replace what used to be five near-identical
    # methods per table (twenty-five in total, of which twenty were copies).
    # A table added to nxd_data.ALL_NXD_SPECS is counted, reported and
    # exported without anything here being edited.
    #
    # Everything resolves through `getattr`/`setattr` at CALL time. Caching
    # the dicts in a lookup built once would leave every holder watching an
    # orphaned dict the moment `clear_opened_mod_content` reassigned one -
    # which is a bug this project has already paid for.

    def nxd_records_for(self, key: str) -> dict:
        """
        {language: [record]} for one registered table.

        Derived tables - the ones built from a bundled layout rather than
        written by hand - keep their stores in `nxd_stores` instead of a
        declared field, because 53 localized layouts would otherwise mean
        106 dataclass fields. A redeclared dataclass field does not raise;
        the second one silently wins, which is how `job_records` once
        turned from a list into a dict.
        """
        from . import nxd_data
        spec = nxd_data.spec_for(key)
        if spec.derived:
            return self.nxd_stores.setdefault(spec.records_attr, {})
        return getattr(self, spec.records_attr) or {}

    def set_nxd_records_for(self, key: str, value: dict) -> None:
        from . import nxd_data
        spec = nxd_data.spec_for(key)
        if spec.derived:
            self.nxd_stores[spec.records_attr] = value
            return
        setattr(self, spec.records_attr, value)

    def nxd_edits_for(self, key: str) -> dict:
        """{language: {row_key: {field: value}}} for one registered table."""
        from . import nxd_data
        spec = nxd_data.spec_for(key)
        if spec.derived:
            return self.nxd_stores.setdefault(spec.edits_attr, {})
        return getattr(self, spec.edits_attr) or {}

    def set_nxd_edits_for(self, key: str, value: dict) -> None:
        from . import nxd_data
        spec = nxd_data.spec_for(key)
        if spec.derived:
            self.nxd_stores[spec.edits_attr] = value
            return
        setattr(self, spec.edits_attr, value)

    def edited_nxd_count(self, key: str, language: str) -> int:
        return sum(1 for fields in self.nxd_edits_for(key).get(language, {}).values() if fields)

    def edited_nxd_total_count(self, key: str) -> int:
        return sum(self.edited_nxd_count(key, lang) for lang in self.nxd_edits_for(key))

    def touched_nxd_languages(self, key: str) -> list:
        from . import constants as c
        edits = self.nxd_edits_for(key)
        return [
            lang for lang in c.NXD_LANGUAGES
            if any(fields for fields in edits.get(lang, {}).values())
        ]

    def has_any_nxd_edits(self, key: str) -> bool:
        return self.edited_nxd_total_count(key) > 0

    def any_nxd_table_edited(self) -> bool:
        """True if any registered per-language table has an edit anywhere."""
        from . import nxd_data
        return any(self.has_any_nxd_edits(key) for key in nxd_data.ALL_NXD_SPECS)

    # -- Jobs' per-language accessors, named for readability ---------------
    def edited_job_text_count(self, language: str) -> int:
        return self.edited_nxd_count("job", language)

    def edited_job_text_total_count(self) -> int:
        return self.edited_nxd_total_count("job")

    def touched_job_languages(self) -> list:
        return self.touched_nxd_languages("job")

    def has_any_job_text_edits(self) -> bool:
        return self.has_any_nxd_edits("job")

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



