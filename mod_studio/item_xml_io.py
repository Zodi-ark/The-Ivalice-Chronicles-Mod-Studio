"""
Reading/writing the six Item*Data.xml reference/diff tables (ItemData,
ItemWeaponData, ItemArmorData, ItemShieldData, ItemAccessoryData,
ItemEquipBonusData, ItemShopsData) plus three more tables that happen to
share the exact same shape: MapTrapFormationData.xml (Treasure Hunter's
buried-treasure map tiles), AbilityEffectNumberFilterData.xml (Ability
Effect), and AbilityTypeData.xml (Unit Animations) - none conceptually
related to Items, but "generic reference/diff XML table" doesn't care about
that, so each is just one more TableSpec/ALL_SPECS entry rather than a
near-duplicate engine. Ability Effect and Unit Animations in particular
live as their own sub-tabs inside the Abilities tab itself (see
step_abilities.py), not a separate top-level tab like Treasure Hunter.

All ten share the exact same "reference table + trimmed diff" shape as
JobData.xml/JobCommandData.xml (see xml_io.py's module docstring for the
rules - only touched entries are written, only included fields within a
touched entry are written) - just different tag names and field lists. So
rather than ten near-duplicate copies of xml_io.py's Job-specific
functions, this module has ONE generic engine (TableSpec + load_table/
parse_diff_xml/build_diff_xml_text/write_diff_xml) and a TableSpec constant
per table describing what's different about it.

Per-language item text (Name/Description/etc.) is NOT here - that lives in
a separate nxd table, see nxd_data.py's read_item_table/write_item_edits.
ItemData.xml's TypeFlags determines which of the other five tables
AdditionalDataId links into - see constants.ITEM_TYPE_TO_ADDITIONAL_TABLE.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import constants as c
from .xml_io import format_flag_value, parse_flag_value  # noqa: F401 - re-exported for callers


@dataclass
class ItemTableRecord:
    """One row of any Item*Data table, plus a human-readable name if a name comment exists."""
    item_id: int
    name: Optional[str]
    values: dict = field(default_factory=dict)  # field name -> str value from XML

    def display_name(self, digits: int = 3) -> str:
        if self.name:
            return f"{self.item_id:0{digits}d} - {self.name}"
        return f"{self.item_id:0{digits}d} - (unnamed)"


@dataclass
class TableSpec:
    """Everything that differs between the ten tables this engine handles (six Item*Data tables +
    MapTrapFormationData, AbilityEffectNumberFilterData, and AbilityTypeData)."""
    root_tag: str
    entry_tag: str
    field_order: list
    max_id: int
    header_comment: str
    flag_fields: tuple = ()   # fields using parse_flag_value/format_flag_value ("None"-default) semantics
    bool_fields: tuple = ()   # fields using "true"/"false" ("false"-default)


def derive_spec(xml_path: Path) -> "TableSpec | None":
    """
    Builds a TableSpec by reading a table's own XML, instead of declaring one.

    28 of the mod loader's 29 XML tables have the identical shape -
    `<XTable><Entries><X><Id>n</Id>...</X></Entries></XTable>`, keyed by
    `Id`, between 2 and 30 fields. Checked, not assumed: only
    `AbilityActionData.xml` differs, and only because it ships empty.

    So the five things a spec needs are all in the file:

      root_tag       the document element
      entry_tag      the repeating child
      field_order    every child tag, in the order the file uses, unioned
                     across entries so a field some rows omit is not lost
      max_id         the largest Id present
      header_comment the file's own leading comment, which is where the
                     mod loader explains that table's rules

    `flag_fields` and `bool_fields` are left EMPTY on purpose. Which fields
    are flags is knowledge about a table, and the eleven declared specs have
    it because someone worked it out. Guessing here - "it is called Flags so
    it must be flags" - would write `None` into a numeric field on a table
    nobody has characterised. The same rule the All Game Data page follows
    for `.nxd`: show it raw, do not invent meaning.

    Returns None for a file with no entries, rather than a spec that
    describes nothing.
    """
    try:
        raw = xml_path.read_text(encoding="utf-8", errors="replace")
        root = ET.fromstring(raw)
    except Exception:                                         # noqa: BLE001
        return None

    container = None
    for child in root:
        if len(list(child)) > 0:
            container = child
            break
    if container is None:
        return None
    entries = list(container)
    if not entries:
        return None

    entry_tag = entries[0].tag
    entries = [e for e in entries if e.tag == entry_tag]

    field_order = []
    for entry in entries:
        for field in entry:
            if field.tag not in field_order:
                field_order.append(field.tag)
    if "Id" not in field_order:
        # Every table this engine can diff is keyed by Id. One that is not
        # needs a real spec, not a derived one.
        return None
    field_order = [name for name in field_order if name != "Id"]

    max_id = 0
    for entry in entries:
        found = entry.find("Id")
        if found is not None and (found.text or "").strip().isdigit():
            max_id = max(max_id, int(found.text.strip()))

    header = ""
    for node in root.iter():
        break
    comment_start = raw.find("<!--")
    if 0 <= comment_start < raw.find("<" + root.tag):
        comment_end = raw.find("-->", comment_start)
        if comment_end > comment_start:
            header = raw[comment_start + 4:comment_end].strip()

    # The mod loader's own Model for this table, if one is bundled. It is
    # the SCHEMA where everything above is an INSTANCE, and it states three
    # things a sample file cannot:
    #
    #   * every field the loader will diff, including any the shipped rows
    #     all happen to omit. Measured: today the samples are complete, all
    #     189 fields across 28 tables - so this buys nothing YET. It buys
    #     not silently losing a field the day a sample goes stale or a new
    #     table ships a partial one, which is the failure this whole
    #     architecture exists to remove.
    #   * which fields are FLAGS - 31 of the 189. `derive_spec` refused to
    #     guess these from names, correctly, so they were plain boxes; the
    #     loader declares them as `[Flags]` enums and now they are known.
    #   * which are numbers - 149 of the 189, previously all free text.
    #
    # Merged rather than substituted: the instance still contributes
    # `max_id` and the header comment, which are properties of the data and
    # not of the schema. Field order follows the MODEL where there is one,
    # with any instance-only field appended rather than dropped - a sample
    # containing a field the model does not know about is a discrepancy to
    # surface, not to silently discard.
    from . import xml_models
    model = xml_models.model_for(entry_tag)
    flag_fields: tuple = ()
    bool_fields: tuple = ()
    if model is not None:
        modelled = [name for name in model.field_names() if name != "Id"]
        field_order = modelled + [name for name in field_order
                                  if name not in modelled]
        flag_fields = model.flag_fields()
        bool_fields = model.bool_fields()

    return TableSpec(
        root_tag=root.tag,
        entry_tag=entry_tag,
        field_order=field_order,
        max_id=max_id,
        header_comment=header or (
            f"Only the {entry_tag} entries you edited are listed here. "
            f"Everything else keeps the game's own value."),
        flag_fields=flag_fields,
        bool_fields=bool_fields,
    )


def discover_specs(tables_dir: Path) -> dict:
    """
    A spec for every XML table in a folder, keyed by filename.

    This is what makes an XML table's arrival free: drop the file in and it
    is loadable, diffable and exportable without a declaration. The eleven
    hand-written specs in ALL_SPECS stay authoritative for the tables they
    cover - they know which fields are flags and which are booleans, which
    a derived spec cannot - so callers should prefer those and fall back
    here.
    """
    found = {}
    if not tables_dir or not Path(tables_dir).is_dir():
        return found
    for path in sorted(Path(tables_dir).glob("*.xml")):
        spec = derive_spec(path)
        if spec is not None:
            found[path.name] = spec
    return found


def _extract_name_from_comment(raw_comment: str) -> Optional[str]:
    """'Dagger / たかー / dague / dolch' -> 'Dagger' (English/first segment only)."""
    text = raw_comment.strip()
    if not text:
        return None
    first_segment = text.split("/")[0].strip()
    return first_segment or None


def _find_name_comment_for_id(raw_text: str, entry_id: int) -> Optional[str]:
    """Looks for '<Id>{entry_id}</Id> <!-- Name / ... -->' in the raw XML text."""
    pattern = re.compile(r"<Id>\s*" + str(entry_id) + r"\s*</Id>\s*<!--(.*?)-->", re.DOTALL)
    match = pattern.search(raw_text)
    if not match:
        return None
    return _extract_name_from_comment(match.group(1))


def _default_for(spec: TableSpec, field_name: str) -> str:
    if field_name in spec.flag_fields:
        return "None"
    if field_name in spec.bool_fields:
        return "false"
    return "0"


# ---------------------------------------------------------------------------
# Generic read/write engine
# ---------------------------------------------------------------------------

def load_table(xml_path: Path, spec: TableSpec) -> tuple[list[ItemTableRecord], str]:
    """
    Parses a full reference Item*Data.xml into a list of ItemTableRecord, in
    <Id> order. Returns (records, version_string).
    """
    raw_text = xml_path.read_text(encoding="utf-8-sig")
    root = ET.fromstring(raw_text)

    version_el = root.find("Version")
    version = version_el.text.strip() if version_el is not None and version_el.text else "1"

    entries = root.find("Entries")
    if entries is None:
        raise ValueError(f"No <Entries> element found - this doesn't look like a {spec.root_tag}")

    records: list[ItemTableRecord] = []
    for entry_el in entries.findall(spec.entry_tag):
        id_el = entry_el.find("Id")
        if id_el is None or id_el.text is None:
            continue
        entry_id = int(id_el.text.strip())
        name = _find_name_comment_for_id(raw_text, entry_id)

        values = {}
        for field_name in spec.field_order:
            el = entry_el.find(field_name)
            values[field_name] = el.text.strip() if el is not None and el.text else _default_for(spec, field_name)

        records.append(ItemTableRecord(item_id=entry_id, name=name, values=values))

    # All seven tables are fully contiguous 0..max_id in the shipped
    # reference data (verified against the real files, MapTrapFormationData.xml
    # included), but gap-fill defensively
    # anyway in case a future game update's reference table falls behind,
    # same defensive approach as xml_io.load_job_table.
    seen_ids = {r.item_id for r in records}
    for missing_id in range(0, spec.max_id + 1):
        if missing_id not in seen_ids:
            blank_values = {f: _default_for(spec, f) for f in spec.field_order}
            records.append(ItemTableRecord(item_id=missing_id, name=None, values=blank_values))

    records.sort(key=lambda r: r.item_id)
    return records, version


def parse_diff_xml(xml_path: Path, spec: TableSpec) -> tuple[dict, str, dict]:
    """
    Parses a MOD's own trimmed Item*Data.xml (as generated by write_diff_xml,
    or hand-edited following the same convention) into {id: {field: value}}.
    Used by "open an existing mod to continue editing".
    """
    raw_text = xml_path.read_text(encoding="utf-8-sig")
    root = ET.fromstring(raw_text)
    version_el = root.find("Version")
    version = version_el.text.strip() if version_el is not None and version_el.text else "1"

    edits: dict = {}
    # Each entry exactly as it was, in its original order, so rewriting the
    # mod gives back elements this tool doesn't model. See
    # xml_io.parse_job_command_diff_xml for the incident that prompted it.
    preserved: dict = {}
    entries = root.find("Entries")
    if entries is None:
        return edits, version, preserved

    for entry_el in entries.findall(spec.entry_tag):
        id_el = entry_el.find("Id")
        if id_el is None or id_el.text is None:
            continue
        try:
            entry_id = int(id_el.text.strip())
        except ValueError:
            continue
        if not (0 <= entry_id <= spec.max_id):
            continue

        fields = {}
        for field_name in spec.field_order:
            el = entry_el.find(field_name)
            if el is not None and el.text is not None:
                fields[field_name] = el.text.strip()

        original = {}
        for child in entry_el:
            if child.tag == "Id":
                continue
            original[child.tag] = (child.text or "").strip()

        if fields:
            edits[entry_id] = fields
        if original:
            preserved[entry_id] = original

    return edits, version, preserved


def build_diff_xml_text(spec: TableSpec, version: str, edited_entries: list,
                        preserved: Optional[dict] = None) -> str:
    """
    edited_entries: list of (record, {field_name: new_string_value, ...}, name_comment)
                     where the dict only contains fields the user chose to include.
                     An entry with an empty dict is skipped entirely.
    """
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "", "<!--"]
    lines.append(spec.header_comment.rstrip())
    lines.append("-->")
    lines.append("")
    lines.append(f"<{spec.root_tag}>")
    lines.append(f"  <Version>{version}</Version>")
    lines.append("  <Entries>")

    for record, included_fields, name_comment in edited_entries:
        if not included_fields:
            continue
        id_comment = f" <!-- {name_comment} -->" if name_comment else ""
        lines.append(f"    <{spec.entry_tag}>")
        lines.append(f"      <Id>{record.item_id}</Id>{id_comment}")
        # Original order first, then anything newly included. A modelled
        # field appears only if still included, so unticking removes it; an
        # unmodelled element is always written back.
        original = (preserved or {}).get(record.item_id, {})
        emitted = set()
        for tag, original_text in original.items():
            if tag in spec.field_order:
                if tag in included_fields:
                    lines.append(f"      <{tag}>{included_fields[tag]}</{tag}>")
                    emitted.add(tag)
            else:
                lines.append(f"      <{tag}>{original_text}</{tag}>")
        for field_name in spec.field_order:
            if field_name in included_fields and field_name not in emitted:
                lines.append(f"      <{field_name}>{included_fields[field_name]}</{field_name}>")
        lines.append(f"    </{spec.entry_tag}>")

    lines.append("  </Entries>")
    lines.append(f"</{spec.root_tag}>")
    lines.append("")
    return "\n".join(lines)


def write_diff_xml(output_path: Path, spec: TableSpec, version: str, edited_entries: list,
                   preserved: Optional[dict] = None) -> None:
    output_path.write_text(
        build_diff_xml_text(spec, version, edited_entries, preserved), encoding="utf-8")


# ---------------------------------------------------------------------------
# Per-table specs - header comments copied verbatim from the real shipped
# XML files (fftivc.utility.modloader 1.7.x) so generated diffs carry the
# exact same documentation/links a hand-edited file would.
# ---------------------------------------------------------------------------

_ITEM_HEADER = """This table file is used to overwrite the game's hardcoded item table.

Refer to: https://ffhacktics.com/wiki/Item_Data
This table links to nex table 'Item'. Some properties edited here may be overriden by the nex table.

You can use this file as a base to edit Item data in your mod.
Simply copy this file to your mod's folder under FFTIVC/tables/<enhanced/classic/combined>/ItemData.xml.

IMPORTANT: You are free to remove everything and **SHOULD ONLY LEAVE ELEMENTS THAT YOU HAVE EDITED** to avoid conflicts between mods.
Only properties that are actually included in this file will be tracked as edited. Properties not edited will inherit their
value from the original table or, from other mods making changes depending on mod order.

IMPORTANT 2: The Id property must NOT be removed for nodes that you're leaving here!

IMPORTANT 3: Id cannot be more than 260 (hardcoded table size is 261 across two tables - 256 + 5 (extended)).

For available flags, refer to https://github.com/Nenkai/fftivc.utility.modloader/blob/master/fftivc.utility.modloader.Interfaces/Tables/Structures/ITEM_COMMON_DATA.cs
"""

_ITEM_WEAPON_HEADER = """This table file is used to overwrite the game's hardcoded item weapon table.

Refer to: https://ffhacktics.com/wiki/Weapon_Secondary_Data
It is referenced from the ItemData table, with category ranges defined by ItemCategoryRanges.

You can use this file as a base to edit Weapon data in your mod.
Simply copy this file to your mod's folder under FFTIVC/tables/<enhanced/classic/combined>/ItemWeaponData.xml.

IMPORTANT: You are free to remove everything and **SHOULD ONLY LEAVE ELEMENTS THAT YOU HAVE EDITED** to avoid conflicts between mods.
Only properties that are actually included in this file will be tracked as edited. Properties not edited will inherit their
value from the original table or, from other mods making changes depending on mod order.

IMPORTANT 2: The Id property must NOT be removed for nodes that you're leaving here!

IMPORTANT 3: Id cannot be more than 127 (hardcoded table size is 128).

IMPORTANT 4: If using Formula 02, <OptionsAbilityId> should be set to an ability id; otherwise, <OptionsAbilityId> should be set to an "item options" id or 0.

For available flags, refer to https://github.com/Nenkai/fftivc.utility.modloader/blob/master/fftivc.utility.modloader.Interfaces/Tables/Structures/ITEM_WEAPON_DATA.cs
"""

_ITEM_ARMOR_HEADER = """This table file is used to overwrite the game's hardcoded item armor table.

Refer to: https://ffhacktics.com/wiki/Helm/Armor_Secondary_Data
It is referenced from the ItemData table, with category ranges defined by ItemCategoryRanges.

You can use this file as a base to edit Armor data in your mod.
Simply copy this file to your mod's folder under FFTIVC/tables/<enhanced/classic/combined>/ItemArmorData.xml.

IMPORTANT: You are free to remove everything and **SHOULD ONLY LEAVE ELEMENTS THAT YOU HAVE EDITED** to avoid conflicts between mods.
Only properties that are actually included in this file will be tracked as edited. Properties not edited will inherit their
value from the original table or, from other mods making changes depending on mod order.

IMPORTANT 2: The Id property must NOT be removed for nodes that you're leaving here!

IMPORTANT 3: Id cannot be more than 63 (hardcoded table size is 64).

For available flags, refer to https://github.com/Nenkai/fftivc.utility.modloader/blob/master/fftivc.utility.modloader.Interfaces/Tables/Structures/ITEM_ARMOR_DATA.cs
"""

_ITEM_SHIELD_HEADER = """This table file is used to overwrite the game's hardcoded item shield table.

Refer to: https://ffhacktics.com/wiki/Shield_Secondary_Data
It is referenced from the ItemData table, with category ranges defined by ItemCategoryRanges.

You can use this file as a base to edit Shield data in your mod.
Simply copy this file to your mod's folder under FFTIVC/tables/<enhanced/classic/combined>/ItemShieldData.xml.

IMPORTANT: You are free to remove everything and **SHOULD ONLY LEAVE ELEMENTS THAT YOU HAVE EDITED** to avoid conflicts between mods.
Only properties that are actually included in this file will be tracked as edited. Properties not edited will inherit their
value from the original table or, from other mods making changes depending on mod order.

IMPORTANT 2: The Id property must NOT be removed for nodes that you're leaving here!

IMPORTANT 3: Id cannot be more than 15 (hardcoded table size is 16).

For available flags, refer to https://github.com/Nenkai/fftivc.utility.modloader/blob/master/fftivc.utility.modloader.Interfaces/Tables/Structures/ITEM_SHIELD_DATA.cs
"""

_ITEM_ACCESSORY_HEADER = """This table file is used to overwrite the game's hardcoded item accessory table.

Refer to: https://ffhacktics.com/wiki/Accessory_Secondary_Data
It is referenced from the ItemData table, with category ranges defined by ItemCategoryRanges.

You can use this file as a base to edit Accessory data in your mod.
Simply copy this file to your mod's folder under FFTIVC/tables/<enhanced/classic/combined>/ItemAccessoryData.xml.

IMPORTANT: You are free to remove everything and **SHOULD ONLY LEAVE ELEMENTS THAT YOU HAVE EDITED** to avoid conflicts between mods.
Only properties that are actually included in this file will be tracked as edited. Properties not edited will inherit their
value from the original table or, from other mods making changes depending on mod order.

IMPORTANT 2: The Id property must NOT be removed for nodes that you're leaving here!

IMPORTANT 3: Id cannot be more than 31 (hardcoded table size is 32).

For available flags, refer to https://github.com/Nenkai/fftivc.utility.modloader/blob/master/fftivc.utility.modloader.Interfaces/Tables/Structures/ITEM_ACCESSORY_DATA.cs
"""

_ITEM_EQUIP_BONUS_HEADER = """This table file is used to overwrite the game's hardcoded item equip bonus table.
It is referenced from the ItemData table, EquipBonusId.

Refer to: https://ffhacktics.com/wiki/Item_Attribute

You can use this file as a base to edit Equip Bonus data in your mod.
Simply copy this file to your mod's folder under FFTIVC/tables/<enhanced/classic/combined>/ItemEquipBonusData.xml.

IMPORTANT: You are free to remove everything and **SHOULD ONLY LEAVE ELEMENTS THAT YOU HAVE EDITED** to avoid conflicts between mods.
Only properties that are actually included in this file will be tracked as edited. Properties not edited will inherit their
value from the original table or, from other mods making changes depending on mod order.

IMPORTANT 2: The Id property must NOT be removed for nodes that you're leaving here!

IMPORTANT 3: Id cannot be more than 84 (hardcoded table size is 85).

For available flags, refer to https://github.com/Nenkai/fftivc.utility.modloader/blob/master/fftivc.utility.modloader.Interfaces/Tables/Structures/ITEM_EQUIP_BONUS_DATA.cs
"""

_ITEM_SHOPS_HEADER = """This table file is used to overwrite the game's hardcoded Item -> Shops table.

Refer to: https://ffhacktics.com/wiki/Shop_Selling_Lists

You can use this file as a base to edit Item Shops data in your mod.
Simply copy this file to your mod's folder under FFTIVC/tables/<enhanced/classic/combined>/ItemShopsData.xml.

IMPORTANT: You are free to remove everything and **SHOULD ONLY LEAVE ELEMENTS THAT YOU HAVE EDITED** to avoid conflicts between mods.
Only properties that are actually included in this file will be tracked as edited. Properties not edited will inherit their
value from the original table or, from other mods making changes depending on mod order.

IMPORTANT 2: The Id property must NOT be removed for nodes that you're leaving here!

IMPORTANT 3: Id cannot be more than 255 (hardcoded table size is 256).

For available flags, refer to https://github.com/Nenkai/fftivc.utility.modloader/blob/master/fftivc.utility.modloader.Interfaces/Tables/Structures/ITEM_SHOPS_DATA.cs
"""

ITEM_SPEC = TableSpec(
    root_tag="ItemTable", entry_tag="Item", field_order=c.ITEM_FIELD_ORDER, max_id=c.MAX_ITEM_ID,
    header_comment=_ITEM_HEADER, flag_fields=("TypeFlags",),
)
ITEM_WEAPON_SPEC = TableSpec(
    root_tag="ItemWeaponTable", entry_tag="ItemWeapon", field_order=c.ITEM_WEAPON_FIELD_ORDER,
    max_id=c.MAX_ITEM_WEAPON_ID, header_comment=_ITEM_WEAPON_HEADER, flag_fields=("AttackFlags", "Elements"),
)
ITEM_ARMOR_SPEC = TableSpec(
    root_tag="ItemArmorTable", entry_tag="ItemArmor", field_order=c.ITEM_ARMOR_FIELD_ORDER,
    max_id=c.MAX_ITEM_ARMOR_ID, header_comment=_ITEM_ARMOR_HEADER,
)
ITEM_SHIELD_SPEC = TableSpec(
    root_tag="ItemShieldTable", entry_tag="ItemShield", field_order=c.ITEM_SHIELD_FIELD_ORDER,
    max_id=c.MAX_ITEM_SHIELD_ID, header_comment=_ITEM_SHIELD_HEADER,
)
ITEM_ACCESSORY_SPEC = TableSpec(
    root_tag="ItemAccessoryTable", entry_tag="ItemAccessory", field_order=c.ITEM_ACCESSORY_FIELD_ORDER,
    max_id=c.MAX_ITEM_ACCESSORY_ID, header_comment=_ITEM_ACCESSORY_HEADER,
)
ITEM_EQUIP_BONUS_SPEC = TableSpec(
    root_tag="ItemEquipBonusTable", entry_tag="ItemEquipBonus", field_order=c.ITEM_EQUIP_BONUS_FIELD_ORDER,
    max_id=c.MAX_ITEM_EQUIP_BONUS_ID, header_comment=_ITEM_EQUIP_BONUS_HEADER,
    flag_fields=(
        "InnateStatus", "ImmuneStatus", "StartingStatus",
        "AbsorbElements", "NullifyElements", "HalveElements", "WeakElements", "StrongElements",
    ),
    bool_fields=("BoostJP",),
)
ITEM_SHOPS_SPEC = TableSpec(
    root_tag="ItemShopsTable", entry_tag="ItemShops", field_order=c.ITEM_SHOPS_FIELD_ORDER,
    max_id=c.MAX_ITEM_SHOPS_ID, header_comment=_ITEM_SHOPS_HEADER, flag_fields=("Shops",),
)

_MAP_TRAP_HEADER = """This table file is used to overwrite the game's hardcoded map items table.

You can use this file as a base to edit Map Items data in your mod.
Simply copy this file to your mod's folder under FFTIVC/tables/<enhanced/classic/combined>/MapTrapFormationData.xml.

IMPORTANT: You are free to remove everything and **SHOULD ONLY LEAVE ELEMENTS THAT YOU HAVE EDITED** to avoid conflicts between mods.
Only properties that are actually included in this file will be tracked as edited. Properties not edited will inherit their
value from the original table or, from other mods making changes depending on mod order.

IMPORTANT 2: The Id property must NOT be removed for nodes that you're leaving here!

IMPORTANT 3: Id cannot be more than 127 (hardcoded table size is 128).

For available flags, refer to https://github.com/Nenkai/fftivc.utility.modloader/blob/master/fftivc.utility.modloader.Interfaces/Tables/Structures/MAP_ITEM_DATA.cs
"""

MAP_TRAP_SPEC = TableSpec(
    root_tag="MapTrapFormationTable", entry_tag="MapTrapFormation", field_order=c.MAPTRAP_FIELD_ORDER,
    max_id=c.MAX_MAPTRAP_ID, header_comment=_MAP_TRAP_HEADER,
    flag_fields=tuple(f"TrapFlags{slot}" for slot in c.MAPTRAP_SLOTS),
)

# Header comment copied verbatim from the real shipped AbilityEffectNumberFilterData.xml.
# Note its own text below points modders at "AbilityEffectData.xml" as the destination
# filename - a stale name; the real required filename (confirmed via Zodi's actual
# FFTOAbilityEffectNumberFilterDataManager.cs - TableFileName => "AbilityEffectNumberFilterData")
# is AbilityEffectNumberFilterData.xml, which is what constants.TABLE_FILENAMES actually
# uses. Kept verbatim here anyway, same reasoning as MapTrapFormationData's own stale
# header text above - a generated diff should still read like a hand-edited copy of the
# real file, stale mentions and all.
_ABILITY_EFFECT_HEADER = """This table file is used to overwrite the game's hardcoded ability effect table.

Refer to: https://ffhacktics.com/wiki/Effects and https://ffhacktics.com/smf/index.php?topic=4830.0
This table is only used to determine which effect is used when an ability is executed.

You can use this file as a base to edit Ability Effects data in your mod.
Simply copy this file to your mod's folder under FFTIVC/tables/<enhanced/classic/combined>/AbilityEffectData.xml.

IMPORTANT: You are free to remove everything and **SHOULD ONLY LEAVE ELEMENTS THAT YOU HAVE EDITED** to avoid conflicts between mods.
Only properties that are actually included in this file will be tracked as edited. Properties not edited will inherit their
value from the original table or, from other mods making changes depending on mod order.

IMPORTANT 2: The Id property must NOT be removed for nodes that you're leaving here!

IMPORTANT 3: Id cannot be more than 453 (hardcoded table size is 454).
"""

_ABILITY_TYPE_HEADER = """This table file is used to overwrite the game's hardcoded ability animation table.

This table is used to determine which animation(s) are used when an ability is executed.
Refer to: https://ffhacktics.com/wiki/Animations_(Tab)

You can use this file as a base to edit Ability Animation data in your mod.
Simply copy this file to your mod's folder under FFTIVC/tables/<enhanced/classic/combined>/AbilityTypeData.xml.

IMPORTANT: You are free to remove everything and **SHOULD ONLY LEAVE ELEMENTS THAT YOU HAVE EDITED** to avoid conflicts between mods.
Only properties that are actually included in this file will be tracked as edited. Properties not edited will inherit their
value from the original table or, from other mods making changes depending on mod order.

IMPORTANT 2: The Id property must NOT be removed for nodes that you're leaving here!

IMPORTANT 3: Same ids as AbilityData. Id cannot be more than 453 (hardcoded table size is 454).
"""

# Root/entry tags confirmed directly from the real shipped XML files - note
# AbilityEffectNumberFilterData.xml's root tag is the table name itself
# (no "...Table" suffix), unlike every other table here.
ABILITY_EFFECT_SPEC = TableSpec(
    root_tag="AbilityEffectNumberFilterData", entry_tag="AbilityEffectNumberFilter",
    field_order=c.ABILITY_EFFECT_FIELD_ORDER, max_id=c.MAX_ABILITY_EFFECT_ID,
    header_comment=_ABILITY_EFFECT_HEADER,
)
ABILITY_TYPE_SPEC = TableSpec(
    root_tag="AbilityTypeTable", entry_tag="AbilityType", field_order=c.ABILITY_ANIMATION_FIELD_ORDER,
    max_id=c.MAX_ABILITY_ANIMATION_ID, header_comment=_ABILITY_TYPE_HEADER,
)

# Header comment copied verbatim from the real shipped AbilityData.xml - no
# staleness here (unlike Ability Effect/MapTrapFormationData above), its own
# text correctly names itself throughout.
_ABILITY_DATA_HEADER = """This table file is used to overwrite the game's hardcoded ability table.

Refer to: https://ffhacktics.com/wiki/Ability_Data
This table links to nex table 'Ability'. Some properties edited here may be overriden by the nex table.

You can use this file as a base to edit Ability data in your mod.
Simply copy this file to your mod's folder under FFTIVC/tables/<enhanced/classic/combined>/AbilityData.xml.

IMPORTANT: You are free to remove everything and **SHOULD ONLY LEAVE ELEMENTS THAT YOU HAVE EDITED** to avoid conflicts between mods.
Only properties that are actually included in this file will be tracked as edited. Properties not edited will inherit their
value from the original table or, from other mods making changes depending on mod order.

IMPORTANT 2: The Id property must NOT be removed for nodes that you're leaving here!

IMPORTANT 3: Id cannot be more than 511 (hardcoded table size is 512).

For available flags, refer to https://github.com/Nenkai/fftivc.utility.modloader/blob/master/fftivc.utility.modloader.Interfaces/Tables/Structures/ABILITY_COMMON_DATA.cs
"""

# Note JPCost is deliberately absent from ABILITY_XML_FIELD_ORDER (see
# constants.py's own section comment) - not a flags/bool field either, so it
# needs no entry in flag_fields/bool_fields.
#
# Keyed "ability" in ALL_SPECS below (matching TABLE_FILENAMES["ability"],
# same "key mirrors the filename" convention "item"/"map_trap"/etc. already
# use) - NOT to be confused with the unrelated state.ability_edits/
# ability_records attributes, which are the separate nxd-backed Ability-xx
# data (Name/Description/JpCost/etc., see nxd_data.py). This table's own
# edits live in state.item_table_edits["ability"], same storage mechanism
# as every other item_xml_io-backed table.
ABILITY_DATA_SPEC = TableSpec(
    root_tag="AbilityTable", entry_tag="Ability", field_order=c.ABILITY_XML_FIELD_ORDER,
    max_id=c.MAX_ABILITY_ID, header_comment=_ABILITY_DATA_HEADER,
    flag_fields=("Flags", "AIBehaviorFlags"),
)

ALL_SPECS = {
    "item": ITEM_SPEC,
    "item_weapon": ITEM_WEAPON_SPEC,
    "item_armor": ITEM_ARMOR_SPEC,
    "item_shield": ITEM_SHIELD_SPEC,
    "item_accessory": ITEM_ACCESSORY_SPEC,
    "item_equip_bonus": ITEM_EQUIP_BONUS_SPEC,
    "item_shops": ITEM_SHOPS_SPEC,
    "map_trap": MAP_TRAP_SPEC,
    "ability_effect": ABILITY_EFFECT_SPEC,
    "ability_animation": ABILITY_TYPE_SPEC,
    "ability": ABILITY_DATA_SPEC,
}
