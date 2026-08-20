"""
Cross-checks how Mod Studio classifies every nxd column against the column
type Nenkai's .layout files actually declare.

This exists because of a real bug: OverrideEntryData's Unknown04 was listed
as an array when the layout declares it a `string`, so every entry edit
silently rewrote NULL to "[]" in a column the user never touched. Same
shape of mistake is possible in any table, so this checks all of them.

Usage: python3 audit_layouts.py [path-to-layouts-dir]
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
STUDIO = ROOT
sys.path.insert(0, str(STUDIO))

from fft_job_editor import constants as c

LAYOUTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "nex_layouts"

findings = []


def note(severity, table, column, message):
    findings.append((severity, table, column, message))


def parse_layout(path: Path):
    """-> (table_name, [(column_name, type_string, comment)])"""
    table = path.stem
    columns = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("table_name|"):
            table = line.split("|", 1)[1].strip()
        if not line.startswith("add_column|"):
            continue
        body, _, comment = line.partition("//")
        parts = [p.strip() for p in body.strip().split("|")]
        # add_column|Name|type|modifier|offset
        name = parts[1]
        type_str = parts[2] if len(parts) > 2 else ""
        columns.append((name, type_str, comment.strip()))
    return table, columns


def kind_of(type_str: str) -> str:
    if type_str.endswith("[]"):
        return "array"
    if type_str == "string":
        return "string"
    if type_str == "union":
        return "union"
    if type_str in ("byte", "short", "ushort", "int", "uint", "long", "ulong", "float", "double"):
        return "number"
    return "other"


BYTE_MAX = {"byte": 255, "short": 32767, "ushort": 65535, "int": 2147483647, "uint": 4294967295}


def studio_kind(table_key, name):
    """How Mod Studio treats a column: 'array' | 'text' | 'bool' | 'number' | None."""
    spec = STUDIO_TABLES[table_key]
    if name in spec.get("array", []):
        return "array"
    if name in spec.get("text", []):
        return "text"
    if name in spec.get("bool", {}):
        return "bool"
    if name in spec.get("numeric", {}):
        return "number"
    return None


STUDIO_TABLES = {
    "Ability": {
        "text": c.ABILITY_TEXT_FIELDS,
        "numeric": c.ABILITY_NUMERIC_FIELDS,
        "array": c.ABILITY_ARRAY_FIELDS,
        "bool": {},
        "extra_handled": ["JpCost1", "JpCost2"],   # edited together as one JP Cost
    },
    "Item": {
        "text": c.ITEM_TEXT_FIELDS,
        "numeric": c.ITEM_NUMERIC_FIELDS,
        "array": [],
        "bool": c.ITEM_BOOL_FIELDS,
        "extra_handled": [],
    },
    "CharaName": {
        "text": c.CHARANAME_TEXT_FIELDS,
        "numeric": c.CHARANAME_NUMERIC_FIELDS,
        "array": [],
        "bool": c.CHARANAME_BOOL_FIELDS,
        "extra_handled": [],
    },
    "PoachItem": {
        "text": c.POACH_TEXT_FIELDS,
        "numeric": c.POACH_NUMERIC_FIELDS,
        "array": [],
        "bool": c.POACH_BOOL_FIELDS,
        "extra_handled": ["ProducedItemId"],   # Mod Studio's name for Unknown2C
    },
    "OverrideEntryData": {
        "text": c.ENTRY_STRING_FIELDS,
        "numeric": c.ENTRY_NUMERIC_FIELDS,
        "array": c.ENTRY_ARRAY_FIELDS,
        "bool": c.ENTRY_BOOL_FIELDS,
        "extra_handled": [
            "Unknown4", "MainJob", "EntryUnknown1D", "SecondarySkillset",
            "Reaction", "Support", "Movement",
            "Head", "Body", "Accessory", "RightHand", "LeftHand",
        ],   # dropdown-backed, not in ENTRY_NUMERIC_FIELDS
    },
}

# Mod Studio renames a couple of columns for the UI. layout name -> studio name.
RENAMES = {
    ("PoachItem", "Unknown2C"): "ProducedItemId",
    # This layouts repo leaves PoachItem's five rel-strings unnamed, while
    # the layout FF16Tools itself ships (the one that produced the .sqlite
    # this tool reads) names them. Mapped by POSITION against Item.layout's
    # identical string block - inferred, not confirmed.
    ("PoachItem", "Unknown8"): "Name",
    ("PoachItem", "UnknownC"): "NameSingular",
    ("PoachItem", "Unknown10"): "NamePlural",
    ("PoachItem", "Unknown14"): "Description",
    ("PoachItem", "Unknown18"): "Name2",
}

print(f"Reading layouts from {LAYOUTS}")
print(f"{len(list(LAYOUTS.glob('*.layout')))} layout files available\n")

for table_key, spec in STUDIO_TABLES.items():
    path = LAYOUTS / f"{table_key}.layout"
    if not path.exists():
        note("INFO", table_key, "-", "no .layout file in the repo")
        continue
    table_name, columns = parse_layout(path)
    layout_names = {name for name, _t, _c in columns}
    handled = (
        set(spec.get("text", [])) | set(spec.get("numeric", {}))
        | set(spec.get("array", [])) | set(spec.get("bool", {}))
        | set(spec.get("extra_handled", []))
    )

    for name, type_str, comment in columns:
        declared = kind_of(type_str)
        studio_name = RENAMES.get((table_key, name), name)
        if studio_name is None:
            continue
        treated = studio_kind(table_key, studio_name)

        if treated is None:
            if studio_name in handled:
                continue
            note("INFO", table_key, name, f"declared {type_str or '?'} - not exposed for editing")
            continue

        # --- the Unknown04 bug class: type category mismatch
        if declared == "array" and treated != "array":
            note("BUG", table_key, name,
                 f"layout declares {type_str} (an ARRAY) but Mod Studio edits it as {treated}")
        elif declared == "string" and treated not in ("text",):
            note("BUG", table_key, name,
                 f"layout declares `string` but Mod Studio edits it as {treated}")
        elif declared == "number" and treated in ("array", "text"):
            note("BUG", table_key, name,
                 f"layout declares {type_str} (a number) but Mod Studio edits it as {treated}")
        elif declared == "union" and treated is not None:
            note("WARN", table_key, name,
                 f"layout declares `union` (a variant type) but Mod Studio edits it as {treated}")

        # --- range mismatches on numeric columns
        if declared == "number" and treated in ("number", "bool"):
            ceiling = BYTE_MAX.get(type_str)
            entry = spec.get("numeric", {}).get(studio_name)
            if ceiling and entry:
                lo, hi = entry[0], entry[1]
                if hi > ceiling:
                    note("BUG", table_key, name,
                         f"declared {type_str} (max {ceiling}) but the editor allows up to {hi}")
                if lo < 0 and (type_str.startswith("u") or type_str == "byte"):
                    note("WARN", table_key, name,
                         f"declared unsigned {type_str} but the editor allows negatives (min {lo})")

    for studio_name in sorted(handled):
        if studio_name in layout_names:
            continue
        if studio_name in {v for v in RENAMES.values() if v}:
            continue
        note("WARN", table_key, studio_name, "Mod Studio edits this column but the layout has no such column")

# ---------------------------------------------------------------------------
# Cross-check the declared types against real data where we have it.
# ---------------------------------------------------------------------------
REAL = ROOT / "_audit_sample.sqlite"
if REAL.exists():
    con = sqlite3.connect(str(REAL))
    con.row_factory = sqlite3.Row
    for sql_table, layout_key in (("Ability-en", "Ability"), ("Item-en", "Item"),
                                  ("OverrideAbilityActionData", "OverrideAbilityActionData"),
                                  ("OverrideEntryData", "OverrideEntryData")):
        try:
            rows = [dict(r) for r in con.execute(f'SELECT * FROM "{sql_table}" LIMIT 400')]
        except sqlite3.Error:
            continue
        path = LAYOUTS / f"{layout_key}.layout"
        if not path.exists():
            continue
        _t, columns = parse_layout(path)
        for name, type_str, _c in columns:
            if not rows or name not in rows[0]:
                continue
            declared = kind_of(type_str)
            values = [r[name] for r in rows if r[name] is not None]
            if not values:
                continue
            looks_array = all(isinstance(v, str) and v.startswith("[") for v in values)
            looks_text = all(isinstance(v, str) for v in values) and not looks_array
            if declared == "array" and not looks_array:
                note("WARN", sql_table, name, "layout says array, real column doesn't hold JSON arrays")
            if declared == "number" and looks_text:
                note("WARN", sql_table, name, "layout says a number, real column holds text")
            if declared == "string" and not looks_text:
                note("WARN", sql_table, name, "layout says string, real column doesn't hold text")
    con.close()

print("=" * 78)
order = {"BUG": 0, "WARN": 1, "INFO": 2}
for severity, table, column, message in sorted(findings, key=lambda f: (order[f[0]], f[1], f[2])):
    if severity == "INFO":
        continue
    print(f"{severity:5s} {table:22s} {column:26s} {message}")
print("=" * 78)
counts = {}
for severity, *_ in findings:
    counts[severity] = counts.get(severity, 0) + 1
print("summary:", ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
print("\n(INFO = column exists in the layout but isn't exposed for editing; not shown above)")
for severity, table, column, message in sorted(findings):
    if severity == "INFO":
        print(f"      {table:22s} {column:26s} {message}")
