"""
The mod loader's `Tables/Models/*.cs`, read as the schema for its XML tables.

    https://github.com/Nenkai/fftivc.utility.modloader
    bundled from b7d8d50, MIT, in `data/loader_models`

### Why this exists

`item_xml_io.derive_spec` builds a table's spec by reading **an instance** -
the sample XML bundled in `data/`. That works, and it was the right first
move, but an instance can only ever show what the shipped rows happen to
use. It cannot state:

  * a field every sample row omits, which is then invisible and uneditable;
  * a field's TYPE, so everything is a string and a numeric column gets a
    free-text box;
  * which fields are flags, which `derive_spec` deliberately leaves empty
    rather than guess from the name;
  * what a field MEANS, which the tool has been hand-writing in
    `constants.py` one table at a time.

The Models are the loader's own declaration of all four. `PropertyMap` in
each model is an ordered, typed list of exactly the properties the loader
will diff - which is exactly the field list a mod's XML may contain - and
each property carries an XML doc comment written by the person who
implemented the table.

This is the XML counterpart to `nxd_layouts.py`. Same principle: read the
schema, do not restate it.

### Matching a model to a table

By ENTRY tag, not by root tag. 27 of the 29 bundled tables agree on both,
but `AbilityEffectNumberFilterData.xml` has root `AbilityEffectNumberFilterData`
where its model declares `AbilityEffectNumberFilterTable` - the sample and
the loader have drifted apart on the root element, and the entry tag is the
thing both agree on and the thing a mod's rows actually use.

`AbilityActionData.xml` has no model at all and ships empty; it stays on
the instance-derived path, which is what it always used.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

#: `public class JobCommandTable : TableBase<JobCommand>`
_TABLE_CLASS = re.compile(
    r"public\s+(?:sealed\s+)?class\s+(\w+)\s*:\s*TableBase<\s*(\w+)\s*>")

#: One `PropertyMap` line:
#: `[nameof(AbilityId1)] = new DiffablePropertyItem<JobCommand, ushort?>(...`
#: The second generic argument is the property's CLR type, which is where
#: numeric-vs-string-vs-flags comes from.
#: The type may itself be generic (`List<StatusEffectType>`), so the closing
#: bracket cannot simply be the first one - matching to `[^>]+` truncated
#: `List<StatusEffectType>` to `List<StatusEffectType` and left it
#: unclassified. One optional nested level covers everything the loader
#: declares.
_PROPERTY_ITEM = re.compile(
    r"\[nameof\((\w+)\)\]\s*=\s*new\s+DiffablePropertyItem<\s*\w+\s*,\s*"
    r"((?:[^<>]|<[^<>]*>)+?)\s*>\s*\(")

#: A property declaration with the doc comment above it, so a field can
#: carry the loader author's own description instead of a hand-written one.
_DOCUMENTED_PROPERTY = re.compile(
    r"((?:^[ \t]*///.*\n)+)[ \t]*public\s+[\w<>?\[\], ]+?\s+(\w+)\s*\{",
    re.M)

_SUMMARY_LINE = re.compile(r"^\s*///\s?(.*)$")
_TAG = re.compile(r"<[^>]+>")

#: C# types that are whole numbers. Anything not here and not a known enum
#: is treated as text, which is the safe direction: a number typed into a
#: text box round-trips, a string forced into a spin box does not.
_INTEGER_TYPES = frozenset({
    "byte", "sbyte", "short", "ushort", "int", "uint", "long", "ulong",
})
_BOOL_TYPES = frozenset({"bool"})
_TEXT_TYPES = frozenset({"string"})


def models_dir() -> Path:
    from . import paths
    return Path(paths.bundled_data_dir()) / "loader_models"


def structures_dir() -> Path:
    from . import paths
    return Path(paths.bundled_data_dir()) / "loader_structures"


def _clean_doc(block: str) -> str:
    """The prose out of a `///` comment block, tags and all stripped."""
    lines = []
    for raw in block.splitlines():
        match = _SUMMARY_LINE.match(raw)
        if not match:
            continue
        text = _TAG.sub(" ", match.group(1))
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&amp;", "&")
        text = " ".join(text.split())
        if text:
            lines.append(text)
    return " ".join(lines)


@lru_cache(maxsize=1)
def flag_enums() -> dict:
    """
    `{enum name: (member, ...)}` for every `[Flags]` enum in Structures.

    Only `[Flags]` ones. A plain enum is a choice from a list and belongs
    in a dropdown; a flags enum is a set of independent bits and belongs in
    a checkbox panel. Treating the second as the first silently drops every
    bit but one.
    """
    found = {}
    pattern = re.compile(
        r"\[Flags\][^;{]*?\benum\s+(\w+)[^{]*\{(.*?)\}", re.S)
    member = re.compile(r"^\s*(\w+)\s*=", re.M)
    # BOTH folders. Scanning only Structures missed eleven `[Flags]` enums -
    # `JobEquippableItems`, `ItemInnateStartImmuneStatus` and the rest are
    # declared beside the model that uses them, not with the binary
    # structs, so sixteen fields came back unclassified and would have been
    # given plain boxes instead of checkbox panels.
    from . import upstream
    sources = list(upstream.resolve("loader_structures", ".cs").values())
    sources += list(upstream.resolve("loader_models", ".cs").values())
    for path in sources:
        source = path.read_text(encoding="utf-8", errors="replace")
        for name, body in pattern.findall(source):
            members = tuple(m for m in member.findall(body)
                            if m.lower() not in ("none",))
            if members:
                found[name] = members
    return found


class ModelField:
    """One property of an XML table entry, as the loader declares it."""

    def __init__(self, name: str, csharp_type: str, doc: str = ""):
        self.name = name
        # `ushort?` and `ushort` are the same shape to us - nullable means
        # "may be omitted from the XML", which every field already may be.
        # Namespace-qualified in a few places (`Structures.AbilityType`),
        # which made the type not match the enum of that name and left the
        # field unclassified.
        raw = (csharp_type or "").strip().rstrip("?").strip()
        self.csharp_type = raw.rsplit(".", 1)[-1] if "." in raw else raw
        self.doc = doc

    @property
    def is_flags(self) -> bool:
        return self.csharp_type in flag_enums()

    @property
    def flag_members(self) -> tuple:
        return flag_enums().get(self.csharp_type, ())

    @property
    def is_number(self) -> bool:
        return self.csharp_type in _INTEGER_TYPES

    @property
    def is_bool(self) -> bool:
        return self.csharp_type in _BOOL_TYPES

    @property
    def is_text(self) -> bool:
        return self.csharp_type in _TEXT_TYPES

    def __repr__(self) -> str:
        return f"<ModelField {self.name}:{self.csharp_type}>"


class TableModel:
    """One parsed `Models/*.cs`."""

    def __init__(self, path: Path):
        self.path = Path(path)
        source = self.path.read_text(encoding="utf-8", errors="replace")
        match = _TABLE_CLASS.search(source)
        self.table_tag = match.group(1) if match else ""
        self.entry_tag = match.group(2) if match else ""
        docs = {name: _clean_doc(block)
                for block, name in _DOCUMENTED_PROPERTY.findall(source)}
        # PropertyMap is the authority on WHICH properties and in what
        # order. Reading `public X Y { get; set; }` declarations instead
        # would also pick up helpers, computed properties and the Id, none
        # of which the loader diffs.
        self.fields = [ModelField(name, kind, docs.get(name, ""))
                       for name, kind in _PROPERTY_ITEM.findall(source)]
        self.field_docs = docs

    @property
    def usable(self) -> bool:
        return bool(self.entry_tag and self.fields)

    def field_names(self) -> tuple:
        return tuple(f.name for f in self.fields)

    def flag_fields(self) -> tuple:
        return tuple(f.name for f in self.fields if f.is_flags)

    def bool_fields(self) -> tuple:
        return tuple(f.name for f in self.fields if f.is_bool)

    def __repr__(self) -> str:
        return (f"<TableModel {self.entry_tag} {len(self.fields)} fields, "
                f"{len(self.flag_fields())} flag>")


@lru_cache(maxsize=1)
def all_models() -> dict:
    """
    Every model, keyed by ENTRY tag - see the module note.

    A fetched copy beats the bundled one, per file, so "Check for updates"
    pulling one changed model replaces exactly that model.
    """
    from . import upstream
    found = {}
    for _name, path in sorted(upstream.resolve("loader_models", ".cs").items()):
        try:
            model = TableModel(path)
        except Exception:                                     # noqa: BLE001
            continue
        if model.usable:
            found[model.entry_tag] = model
    return found


def model_for(entry_tag: str):
    """One model by the tag its rows use, or None if it is not bundled."""
    return all_models().get(entry_tag)
