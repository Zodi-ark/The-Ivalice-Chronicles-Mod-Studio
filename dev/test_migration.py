"""
Migration engine tests.

Run against the real files wherever possible: the three real converted
vanilla databases (1.5.0/1.5.1/1.5.2) and the real published Dark Knight
Expansion. Conflicts get synthetic fixtures because none of the three real
updates changed anything a mod could conflict with - 1.5.0 to 1.5.2
changed exactly one row in the whole database, three times over - so the
conflict path has no real-world example to test against yet.

Usage:  python3 test_migration.py [path-to-References-folder]
"""
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fft_job_editor import migration as m
from fft_job_editor import modconfig
from fft_job_editor import nxd_data

REFS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "refs"
V150 = REFS / "v150" / "Version 1.5.0 nxd files to sqlite" / "fft_data.sqlite"
V151 = REFS / "Version 1.5.1 nxd files to sqlite" / "fft_data.sqlite"
V152 = REFS / "Version 1.5.2 nxd files to sqlite" / "fft_data.sqlite"
MOD_ROOT = REFS / "Stale Mod" / "fftivc.gameplay.darkknightexpansion"
MOD_NXD = MOD_ROOT / "FFTIVC" / "data" / "enhanced" / "nxd"
MOD_DB = MOD_NXD / "fft_data.sqlite"

passed = failed = 0
_tmp = Path(tempfile.mkdtemp(prefix="migration_tests_"))


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}" + (f"  ({detail})" if detail else ""))


def section(title):
    print(f"\n--- {title} ---")


def patched(source: Path, name: str, statements) -> Path:
    """A copy of `source` with some SQL applied - a synthetic game update."""
    dest = _tmp / name
    shutil.copy(source, dest)
    con = sqlite3.connect(dest)
    for sql, params in statements:
        con.execute(sql, params)
    con.commit()
    con.close()
    return dest


# ---------------------------------------------------------------------------
section("Version detection")
# ---------------------------------------------------------------------------
check("1.5.0 database reports v1.5.0", m.read_game_version(V150) == "v1.5.0",
      m.read_game_version(V150))
check("1.5.1 database reports v1.5.1", m.read_game_version(V151) == "v1.5.1",
      m.read_game_version(V151))
check("1.5.2 database reports v1.5.2", m.read_game_version(V152) == "v1.5.2",
      m.read_game_version(V152))
check("the real mod dates itself to v1.5.1 from its own ui.*.nxd",
      m.read_game_version(MOD_DB) == "v1.5.1", m.read_game_version(MOD_DB))

# A mod shipping only one language must still be datable.
one_lang = _tmp / "one_language.sqlite"
shutil.copy(MOD_DB, one_lang)
con = sqlite3.connect(one_lang)
for lang in ("en", "ja", "cs", "ct", "ko", "fr"):
    con.execute(f'DROP TABLE IF EXISTS "UI-{lang}"')
con.commit()
con.close()
check("a mod shipping only ui.de.nxd is still datable",
      m.read_game_version(one_lang) == "v1.5.1")

no_ui = _tmp / "no_ui.sqlite"
shutil.copy(MOD_DB, no_ui)
con = sqlite3.connect(no_ui)
for lang in ("en", "ja", "de", "fr", "cs", "ct", "ko"):
    con.execute(f'DROP TABLE IF EXISTS "UI-{lang}"')
con.commit()
con.close()
check("a mod with no UI table returns None rather than raising",
      m.read_game_version(no_ui) is None)

version, source = m.detect_mod_game_version(None, MOD_DB)
check("detection falls back to the mod's own UI table", version == "v1.5.1")
check("and says where the answer came from", "UI table" in source, source)

# ---------------------------------------------------------------------------
section("The ModConfig.json stamp")
# ---------------------------------------------------------------------------
real_config = modconfig.read_mod_config(MOD_ROOT) if hasattr(modconfig, "read_mod_config") else None
if real_config is None:
    import json
    real_config = json.loads((MOD_ROOT / "ModConfig.json").read_text(encoding="utf-8-sig"))

check("the real mod carries no stamp yet", m.read_stamp(real_config).is_empty())

config = dict(real_config)
config["PluginData"] = dict(config.get("PluginData") or {})
before = set(config["PluginData"])
m.apply_stamp(config, m.ModStamp(game_version="v1.5.2", clean_unpack=True,
                                 table_versions={"job": "3"}, studio_version="1.0"))
check("stamping leaves every other PluginData key alone",
      before <= set(config["PluginData"]), sorted(config["PluginData"]))
check("GitHubRelease survives stamping",
      "GitHubRelease" in config["PluginData"])
back = m.read_stamp(config)
check("the stamp round-trips its game version", back.game_version == "v1.5.2")
check("the stamp round-trips clean_unpack", back.clean_unpack is True)
check("the stamp round-trips table versions", back.table_versions == {"job": "3"})

version, source = m.detect_mod_game_version(config, MOD_DB)
check("an explicit stamp beats reading the UI table", version == "v1.5.2")
check("and says so", "ModConfig" in source, source)

cleared = dict(config)
m.apply_stamp(cleared, m.ModStamp())
check("an empty stamp removes the block rather than writing junk",
      m.PLUGIN_DATA_KEY not in cleared["PluginData"])
check("clearing still leaves other keys alone",
      "GitHubRelease" in cleared["PluginData"])

# ---------------------------------------------------------------------------
section("Comparing two real game versions")
# ---------------------------------------------------------------------------
deltas = m.compare_databases(V151, V152)
check("1.5.1 -> 1.5.2 differs in exactly 7 tables", len(deltas) == 7, sorted(deltas))
check("and all seven are UI language tables",
      all(t.startswith("UI-") for t in deltas), sorted(deltas))
check("each with exactly one changed row",
      all(len(d.rows_changed) == 1 for d in deltas.values()))
check("no rows added or removed anywhere",
      all(not d.rows_added and not d.rows_removed for d in deltas.values()))
check("no schema changes anywhere",
      all(not d.columns_added and not d.columns_removed for d in deltas.values()))
en = deltas["UI-en"]
check("the one changed row is the version string",
      en.rows_changed[(m.VERSION_UI_KEY,)]["Text"] == ("v1.5.1", "v1.5.2"),
      en.rows_changed)

deltas_150 = m.compare_databases(V150, V151)
check("1.5.0 -> 1.5.1 is the same shape", len(deltas_150) == 7, sorted(deltas_150))
check("1.5.0 -> 1.5.2 too", len(m.compare_databases(V150, V152)) == 7)

check("a database compared against itself yields nothing",
      m.compare_databases(V151, V151) == {})

# This is the assertion that justifies the generic differ existing at all.
modelled = nxd_data.recover_edits_from_sqlite(V151, V152)
check("the typed readers see nothing between 1.5.1 and 1.5.2", modelled.is_empty())
check("but the generic comparison does - which is why it isn't built on them",
      len(deltas) > 0)

# ---------------------------------------------------------------------------
section("The real mod's intent, recovered against 1.5.1")
# ---------------------------------------------------------------------------
intent = nxd_data.recover_edits_from_sqlite(V151, MOD_DB)
check("three abilities edited in English",
      len(intent.ability_edits.get("en", {})) == 3, sorted(intent.ability_edits.get("en", {})))
check("three ability stat overrides", len(intent.override_action_edits) == 3)
check("one item edited", len(intent.item_edits.get("en", {})) == 1)
check("ten rows rekeyed", len(intent.entry_rekeys) == 10, intent.entry_rekeys)
check("all ten land on Key 95",
      all(dest[0] == 95 for dest in intent.entry_rekeys.values()))
check("nothing dropped outright", intent.entry_dropped == [])

# ---------------------------------------------------------------------------
section("Migrating the real mod 1.5.1 -> 1.5.2 (the no-op case)")
# ---------------------------------------------------------------------------
plan = m.build_plan(V151, MOD_DB, V152, mod_intent=intent)
check("the plan knows both versions",
      (plan.from_version, plan.to_version) == ("v1.5.1", "v1.5.2"),
      (plan.from_version, plan.to_version))
check("no conflicts", plan.conflicts() == [])
check("nothing orphaned", plan.by_outcome(m.ORPHANED) == [])
check("no structural findings", plan.structural == [])
check("every change carries cleanly",
      all(ch.outcome == m.CLEAN for ch in plan.changes),
      {ch.outcome for ch in plan.changes})
check("the plan reports itself a no-op", plan.is_noop())
check("the rekeys are carried through untouched", plan.rekeys == intent.entry_rekeys)
check("something was actually classified (not an empty plan)", len(plan.changes) > 30,
      len(plan.changes))

replayed = m.apply_plan(plan)
check("applying a no-op plan reproduces the mod's ability edits exactly",
      replayed.ability_edits == intent.ability_edits)
check("...its item edits", replayed.item_edits == intent.item_edits)
check("...its stat overrides", replayed.override_action_edits == intent.override_action_edits)
check("...its entry edits", replayed.entry_edits == intent.entry_edits)
check("...and its rekeys", replayed.entry_rekeys == intent.entry_rekeys)

# Migrating from 1.5.0 straight to 1.5.2 skips a version and must behave the same.
plan_skip = m.build_plan(V150, MOD_DB, V152)
check("migrating across two versions at once is also a no-op", plan_skip.is_noop())

# ---------------------------------------------------------------------------
section("Conflicts (synthetic update, since no real one exists yet)")
# ---------------------------------------------------------------------------
fake = patched(V151, "fake_conflicts.sqlite", [
    # same row AND same field as the mod, different value -> conflict
    ('UPDATE "Ability-en" SET Description = ? WHERE Key = 359',
     ("An officially rebalanced description.",)),
    # same row, a field the mod did NOT touch -> advisory, not conflict
    ('UPDATE "Ability-en" SET Name = ? WHERE Key = 166', ("Renamed By Patch",)),
    # a row the mod never touched -> irrelevant
    ('UPDATE "Ability-en" SET Description = ? WHERE Key = 10', ("unrelated",)),
    # the update makes the same change the mod does -> redundant
    ('UPDATE "Item-en" SET Name = ? WHERE Key = 255', ("Deathbringer",)),
    ('UPDATE "UI-en" SET Text = ? WHERE Key = ?', ("v1.5.3", m.VERSION_UI_KEY)),
])
plan = m.build_plan(V151, MOD_DB, fake)
check("the synthetic update reports as v1.5.3", plan.to_version == "v1.5.3", plan.to_version)

conflicts = plan.conflicts()
check("exactly one conflict", len(conflicts) == 1,
      [(ch.table, ch.key, ch.field_name) for ch in conflicts])
conflict = conflicts[0]
check("on the right row and field",
      (conflict.key, conflict.field_name) == (359, "Description"),
      (conflict.key, conflict.field_name))
check("it carries all three values for display",
      conflict.base_value is not None and conflict.mod_value and conflict.new_value)
check("the mod's value is what the mod wrote",
      "dark energy" in str(conflict.mod_value).lower(), conflict.mod_value)
check("the update's value is what the update wrote",
      conflict.new_value == "An officially rebalanced description.")
check("base differs from both", conflict.base_value != conflict.mod_value)
check("a conflict is flagged as needing a decision", conflict.needs_decision)
check("and defaults to keeping the mod's version",
      conflict.resolution == m.KEEP_MOD and conflict.resolved_value() == conflict.mod_value)

redundant = plan.by_outcome(m.REDUNDANT)
check("the same-change case is REDUNDANT, not CONFLICT",
      any(ch.key == 255 and ch.field_name == "Name" for ch in redundant),
      [(ch.table, ch.key, ch.field_name) for ch in redundant])
check("a redundant change needs no decision",
      all(not ch.needs_decision for ch in redundant))

advisories = [a for a in plan.advisories if a.key == 166]
check("a same-row/different-field update produces an advisory", len(advisories) == 1)
check("the advisory names the update's fields",
      advisories and "Name" in advisories[0].update_fields, advisories)
check("and does not become a conflict",
      not any(ch.key == 166 and ch.field_name == "Name" for ch in plan.conflicts()))
check("the unrelated row 10 produces nothing at all",
      not any(ch.key == 10 for ch in plan.changes)
      and not any(a.key == 10 for a in plan.advisories))
check("a plan with a conflict is not a no-op", not plan.is_noop())
check("the summary counts the conflict", "1 conflict" in plan.summary(), plan.summary())

# Resolution actually changes what gets written.
applied_keep = m.apply_plan(plan)
check("keeping the mod's version writes the mod's value",
      applied_keep.ability_edits["en"][359]["Description"] == conflict.mod_value)
conflict.resolution = m.TAKE_UPDATE
applied_take = m.apply_plan(plan)
check("taking the update's version writes the update's value",
      applied_take.ability_edits["en"][359]["Description"] == conflict.new_value)
conflict.resolution = m.DROP
applied_drop = m.apply_plan(plan)
check("dropping omits the field entirely",
      "Description" not in applied_drop.ability_edits["en"].get(359, {}))
check("...without disturbing the row's other fields",
      "Name" in applied_drop.ability_edits["en"][359])
conflict.resolution = m.KEEP_MOD

# ---------------------------------------------------------------------------
section("Orphaned rows")
# ---------------------------------------------------------------------------
orphan_db = patched(V151, "fake_orphan.sqlite", [
    ('DELETE FROM "Item-en" WHERE Key = 255', ()),
])
plan = m.build_plan(V151, MOD_DB, orphan_db)
orphaned = plan.by_outcome(m.ORPHANED)
check("deleting a row the mod edited orphans its edits", len(orphaned) == 7,
      len(orphaned))
check("all on the deleted row", all(ch.key == 255 for ch in orphaned))
check("an orphan needs no decision - there's nothing to choose between",
      all(not ch.needs_decision for ch in orphaned))
applied = m.apply_plan(plan)
check("orphaned edits are not written", 255 not in applied.item_edits.get("en", {}))
check("but the rest of the mod still is", applied.ability_edits.get("en"))

# ---------------------------------------------------------------------------
section("OverrideEntryData: rekeys versus a changing game")
# ---------------------------------------------------------------------------
# The trap: _diff_entries reads a patch's added row as a mod-style rekey.
# The trap needs a patch that both removes and adds - zip() pairs the two
# lists, so an addition alone can't be mistaken for a move. A patch that
# retires one encounter slot and introduces another is exactly that shape.
reshuffled = patched(V151, "fake_reshuffle.sqlite", [
    ("DELETE FROM OverrideEntryData WHERE Key = 83 AND Key2 = 10", ()),
    ("INSERT INTO OverrideEntryData (Key, Key2) VALUES (200, 0)", ()),
])
via_mod_lens = nxd_data.recover_edits_from_sqlite(V151, reshuffled)
check("nxd_data._diff_entries reads a patch's remove+add as a rekey "
      "(the trap this module avoids)",
      via_mod_lens.entry_rekeys == {(83, 10): (200, 0)}, via_mod_lens.entry_rekeys)
vanilla_delta = m.diff_vanilla_entries(V151, reshuffled)
check("diff_vanilla_entries reports an addition instead",
      vanilla_delta["added"] == [(200, 0)], vanilla_delta["added"])
check("and a removal, separately",
      vanilla_delta["removed"] == [(83, 10)], vanilla_delta["removed"])
check("inferring no rekeys at all", "rekeys" not in vanilla_delta)

added_only = patched(V151, "fake_added_entry.sqlite", [
    ("INSERT INTO OverrideEntryData (Key, Key2) VALUES (200, 0)", ()),
])
check("an addition with no matching removal is not mistaken for a move",
      m.diff_vanilla_entries(V151, added_only)["added"] == [(200, 0)])

# The update takes an address the mod moves a row to.
collision = patched(V151, "fake_collision.sqlite", [
    ("INSERT INTO OverrideEntryData (Key, Key2) VALUES (95, 0)", ()),
])
plan = m.build_plan(V151, MOD_DB, collision)
taken = [f for f in plan.structural if f.kind == m.DESTINATION_TAKEN]
check("a collision at a rekey destination is reported", len(taken) == 1, plan.structural)
check("as blocking", taken and taken[0].severity == "blocking")
check("naming the address", taken and taken[0].address == (95, 0))
check("a collision means the plan is not a no-op", not plan.is_noop())

# The update removes the row a move started from.
origin_gone = patched(V151, "fake_origin_removed.sqlite", [
    ("DELETE FROM OverrideEntryData WHERE Key = 155 AND Key2 = 1", ()),
])
plan = m.build_plan(V151, MOD_DB, origin_gone)
removed = [f for f in plan.structural if f.kind == m.ORIGIN_REMOVED]
check("a removed rekey origin is reported", len(removed) == 1, plan.structural)
check("as a warning rather than blocking", removed and removed[0].severity == "warning")
check("the row count change is also noted",
      any(f.kind == m.ROW_COUNT_CHANGED for f in plan.structural))

# The update edits a row the mod moved away from: informational only.
origin_changed = patched(V151, "fake_origin_changed.sqlite", [
    ("UPDATE OverrideEntryData SET Level = 42 WHERE Key = 155 AND Key2 = 1", ()),
])
plan = m.build_plan(V151, MOD_DB, origin_changed)
changed_findings = [f for f in plan.structural if f.kind == m.ORIGIN_CHANGED]
check("a patch touching a vacated origin is reported", len(changed_findings) == 1)
check("as information, not a conflict", changed_findings[0].severity == "info")
check("and it does not become a blocking conflict",
      not any(f.severity == "blocking" for f in plan.structural))

# ---------------------------------------------------------------------------
section("Unmodelled .nxd files the mod ships")
# ---------------------------------------------------------------------------
unmodelled = m.find_unmodelled_nxd(MOD_NXD)
check("the real mod ships 9 nxd files with no editor tab",
      len(unmodelled) == 9, unmodelled)
check("all seven ui languages among them",
      sum(1 for f in unmodelled if f.startswith("ui.")) == 7, unmodelled)
check("uibuttonguide.nxd is one of them", "uibuttonguide.nxd" in unmodelled)
check("modelled files are excluded", "ability.en.nxd" not in unmodelled)

check("ui.en.nxd resolves to the UI-en table",
      m.resolve_table_name(MOD_DB, "ui.en.nxd") == "UI-en",
      m.resolve_table_name(MOD_DB, "ui.en.nxd"))
check("uibuttonguide.nxd resolves to UIButtonGuide despite the case difference",
      m.resolve_table_name(MOD_DB, "uibuttonguide.nxd") == "UIButtonGuide",
      m.resolve_table_name(MOD_DB, "uibuttonguide.nxd"))
check("uiannounce.nxd resolves to UIAnnounce",
      m.resolve_table_name(MOD_DB, "uiannounce.nxd") == "UIAnnounce",
      m.resolve_table_name(MOD_DB, "uiannounce.nxd"))
check("an unknown .nxd resolves to None rather than a guess",
      m.resolve_table_name(MOD_DB, "notatable.nxd") is None)

assessed = {a.filename: a for a in m.assess_unmodelled(MOD_NXD, MOD_DB, V151)}
check("every unmodelled file is accounted for", len(assessed) == 9, sorted(assessed))
check("each resolved to a real table",
      all(a.table for a in assessed.values()),
      {f: a.table for f, a in assessed.items() if not a.table})

ui_en = assessed.get("ui.en.nxd")
check("the mod's UI-en shows losses against vanilla", ui_en and ui_en.losses == 5,
      ui_en and ui_en.losses)
check("and no additions", ui_en and ui_en.additions == 0, ui_en and ui_en.additions)
# Clearing values is an edit, not damage. A real mod exists whose purpose is
# tidying the HUD by blanking UI strings, and calling that "damaged" told its
# author their deliberate work looked broken.
check("clearing values counts as the author's own work", ui_en and ui_en.has_own_work)
check("it is not treated as an empty, purely stale file", ui_en and not ui_en.purely_stale)
check("and merging is recommended where possible, since that keeps both",
      ui_en and (m.REBASE if ui_en.rebasable else m.KEEP_MOD) == ui_en.recommendation,
      ui_en and ui_en.recommendation)

empty = m.UnmodelledTable(filename="x.nxd", table="X", stale=3, rebasable=True)
check("a file with nothing of the author's is still recommended for dropping",
      empty.purely_stale and empty.recommendation == m.DROP)

guide = assessed.get("uibuttonguide.nxd")
check("UIButtonGuide is missing 36 rows against vanilla",
      guide and guide.rows_missing == 36, guide and guide.rows_missing)
check("with hundreds of blanked fields", guide and guide.losses > 300,
      guide and guide.losses)

# A table with genuine additions must NOT be recommended for dropping.
with_additions = _tmp / "mod_with_ui_additions.sqlite"
shutil.copy(MOD_DB, with_additions)
con = sqlite3.connect(with_additions)
con.execute('UPDATE "UI-en" SET Text = ? WHERE Key = 2800', ("Dark Knight",))
con.commit()
con.close()
added_assessment = m.assess_unmodelled_table(with_additions, V151, "ui.en.nxd", "UI-en")
check("a real addition is counted as an addition",
      added_assessment.additions == 1, added_assessment.additions)
check("and is recommended for keeping when it can't be merged",
      added_assessment.recommendation == m.KEEP_MOD)
added_assessment.rebasable = True
check("or for merging when it can",
      added_assessment.recommendation == m.REBASE)

# ---------------------------------------------------------------------------
section("No false positives")
# ---------------------------------------------------------------------------
# A mod identical to vanilla must migrate to nothing at all.
plan = m.build_plan(V151, V151, V152)
check("a mod identical to vanilla produces no changes", plan.changes == [])
check("no advisories", plan.advisories == [])
check("no structural findings", plan.structural == [])
check("and is a no-op", plan.is_noop())
check("applying it invents nothing", m.apply_plan(plan).is_empty())

# ---------------------------------------------------------------------------
section("Robustness")
# ---------------------------------------------------------------------------
partial = _tmp / "partial_mod.sqlite"
shutil.copy(MOD_DB, partial)
con = sqlite3.connect(partial)
con.execute("DROP TABLE OverrideEntryData")
con.commit()
con.close()
try:
    plan = m.build_plan(V151, partial, V152)
    check("a mod with no OverrideEntryData still plans", True)
    check("and still carries its ability edits",
          any(ch.section == m.SECTION_ABILITIES for ch in plan.changes))
except Exception as exc:  # noqa: BLE001
    check("a mod with no OverrideEntryData still plans", False, repr(exc))

check("read_game_version on a missing file returns None rather than raising",
      m.read_game_version(_tmp / "does_not_exist.sqlite") is None)

not_a_db = _tmp / "garbage.sqlite"
not_a_db.write_bytes(b"this is not a database")
check("read_game_version on a corrupt file returns None",
      m.read_game_version(not_a_db) is None)

# ---------------------------------------------------------------------------
print(f"\n{'=' * 60}")
print(f"{passed} passed, {failed} failed")
print("=" * 60)
shutil.rmtree(_tmp, ignore_errors=True)
sys.exit(1 if failed else 0)
