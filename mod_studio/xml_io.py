"""
Reading the reference JobData.xml into plain Python data, and writing back a
trimmed diff file that follows the mod loader's rules:

  - Only <Job> elements the user actually touched are written.
  - Within a touched <Job>, only the specific fields the user marked as
    "included" are written (plus <Id>, which must always be present).
  - Everything else is simply left out so it inherits from the vanilla
    table / other mods, per the loader's own documentation.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import constants as c

# Matches the "<!-- English / Japanese / French / German -->" comment FF16
# modding convention leaves after some (not all) <Id> elements.
_NAME_COMMENT_RE = re.compile(r"^\s*(.*?)\s*(?:/.*)?$")


@dataclass
class JobRecord:
    """One row of the Job table, plus a human-readable name if one exists."""
    job_id: int
    name: Optional[str]  # None for unnamed/reserved slots
    values: dict = field(default_factory=dict)  # field name -> str value from XML
    has_reference_data: bool = True  # False for slots missing from the source file

    @property
    def display_name(self) -> str:
        if self.name:
            return f"{self.job_id:03d} - {self.name}"
        if not self.has_reference_data:
            return f"{self.job_id:03d} - (no reference data)"
        return f"{self.job_id:03d} - (unnamed slot)"


def _extract_name_from_comment(raw_comment: str) -> Optional[str]:
    """
    Reference comments look like ' Squire / 見習い戦士 / Écuyer / Knappe ',
    we only want the English (first) segment.
    """
    text = raw_comment.strip()
    if not text:
        return None
    first_segment = text.split("/")[0].strip()
    return first_segment or None


def load_job_table(xml_path: Path) -> tuple[list[JobRecord], str]:
    """
    Parses a full JobData.xml (either the bundled fallback or a freshly
    downloaded copy) into a list of JobRecord, in <Id> order.

    Returns (records, version_string) - version_string is whatever the file's
    <Version> element says, so we can echo it back unchanged on export.
    """
    raw_text = xml_path.read_text(encoding="utf-8-sig")
    root = ET.fromstring(raw_text)

    version_el = root.find("Version")
    version = version_el.text.strip() if version_el is not None and version_el.text else "1"

    records: list[JobRecord] = []
    entries = root.find("Entries")
    if entries is None:
        raise ValueError("No <Entries> element found - this doesn't look like a JobData.xml")

    for job_el in entries.findall("Job"):
        id_el = job_el.find("Id")
        if id_el is None or id_el.text is None:
            continue
        job_id = int(id_el.text.strip())

        # ElementTree doesn't expose comments by default; we re-scan the raw
        # text around this Id to pull out the "<!-- Name / ... -->" comment
        # FF16's tooling leaves in place, since that's the only source of
        # human-readable job names.
        name = _find_name_comment_for_id(raw_text, job_id)

        values = {}
        for name_key in c.FIELD_ORDER:
            el = job_el.find(name_key)
            values[name_key] = el.text.strip() if el is not None and el.text else _default_for(name_key)

        records.append(JobRecord(job_id=job_id, name=name, values=values))

    # The shipped reference file is not guaranteed to cover every legal Id
    # (e.g. as of this writing it stops at 173, even though 175 is allowed).
    # Fill any gaps with blank placeholders so the editor can still offer
    # them, with a clear "no reference data" marker.
    seen_ids = {r.job_id for r in records}
    for missing_id in range(0, c.MAX_JOB_ID + 1):
        if missing_id not in seen_ids:
            blank_values = {name_key: _default_for(name_key) for name_key in c.FIELD_ORDER}
            records.append(
                JobRecord(job_id=missing_id, name=None, values=blank_values, has_reference_data=False)
            )

    records.sort(key=lambda r: r.job_id)
    return records, version


def _default_for(field_name: str) -> str:
    return "None" if field_name in c.FLAG_FIELDS else "0"


def _find_name_comment_for_id(raw_text: str, job_id: int) -> Optional[str]:
    """
    Looks for '<Id>{job_id}</Id> <!-- Name / ... -->' in the raw XML text.
    """
    pattern = re.compile(
        r"<Id>\s*" + str(job_id) + r"\s*</Id>\s*<!--(.*?)-->", re.DOTALL
    )
    match = pattern.search(raw_text)
    if not match:
        return None
    return _extract_name_from_comment(match.group(1))


def parse_flag_value(raw_value: str) -> set[str]:
    """'Perfume, Cloak, Sword' -> {'Perfume', 'Cloak', 'Sword'}. 'None' -> set()."""
    raw_value = (raw_value or "").strip()
    if not raw_value or raw_value == "None":
        return set()
    return {v.strip() for v in raw_value.split(",") if v.strip()}


def format_flag_value(flags: set[str]) -> str:
    if not flags:
        return "None"
    # Keep a stable, readable ordering rather than dumping set() order.
    ordered = []
    for known_list in (
        c.EQUIP_ITEMS, c.STATUS_FLAGS, c.ELEMENT_FLAGS, c.ITEM_TYPE_FLAGS, c.ITEM_ATTACK_FLAGS,
        c.ITEM_SHOPS, c.MAPTRAP_TRAP_FLAGS,
    ):
        for item in known_list:
            if item in flags and item not in ordered:
                ordered.append(item)
    # anything unrecognized (shouldn't happen) goes at the end
    for f in flags:
        if f not in ordered:
            ordered.append(f)
    return ", ".join(ordered)


def parse_diff_xml(
    xml_path: Path,
) -> tuple[dict[int, dict[str, str]], str, dict[int, dict[str, str]]]:
    """
    Parses a MOD's own trimmed JobData.xml (as generated by write_diff_xml,
    or hand-edited by someone following the same convention) - NOT the full
    reference table. Returns only the jobs and fields actually present, with
    no gap-filling or default-filling, since a diff file being sparse is the
    entire point.

    Used by "open an existing mod to continue editing": the result maps
    directly onto app.state_data.edits.
    """
    raw_text = xml_path.read_text(encoding="utf-8-sig")
    root = ET.fromstring(raw_text)

    version_el = root.find("Version")
    version = version_el.text.strip() if version_el is not None and version_el.text else "1"

    edits: dict[int, dict[str, str]] = {}
    # Each entry exactly as it was, in its original order - see
    # parse_job_command_diff_xml for why this matters.
    preserved: dict[int, dict[str, str]] = {}
    entries = root.find("Entries")
    if entries is None:
        return edits, version, preserved

    for job_el in entries.findall("Job"):
        id_el = job_el.find("Id")
        if id_el is None or id_el.text is None:
            continue
        try:
            job_id = int(id_el.text.strip())
        except ValueError:
            continue
        if not (0 <= job_id <= c.MAX_JOB_ID):
            continue

        fields: dict[str, str] = {}
        for field_name in c.FIELD_ORDER:
            el = job_el.find(field_name)
            if el is not None and el.text is not None:
                fields[field_name] = el.text.strip()

        original: dict[str, str] = {}
        for child in job_el:
            if child.tag == "Id":
                continue
            original[child.tag] = (child.text or "").strip()

        if fields:
            edits[job_id] = fields
        if original:
            preserved[job_id] = original

    return edits, version, preserved


def load_ability_names(xml_path: Path) -> dict[int, str]:
    """
    Parses AbilityData.xml (or any table using the same '<Id>N</Id>
    <!-- Name / ... -->' convention) into a plain {id: name} dict. Ids with
    no comment are simply absent from the result - callers decide how to
    handle gaps (fallback lookup, "(unnamed)", etc.).
    """
    raw_text = xml_path.read_text(encoding="utf-8-sig")
    names: dict[int, str] = {}
    for match in re.finditer(r"<Id>\s*(\d+)\s*</Id>\s*<!--(.*?)-->", raw_text, re.DOTALL):
        name = _extract_name_from_comment(match.group(2))
        if name:
            names[int(match.group(1))] = name
    return names


def load_ability_types(xml_path: Path) -> dict[int, str]:
    """
    Parses AbilityData.xml's <AbilityType> field for each ability into
    {id: type_name} (e.g. "Normal", "Item", "Reaction", "Support",
    "Movement", "None", ...).

    This is the authoritative source for which abilities are actually
    Reaction/Support/Movement-type versus regular action abilities - it's
    parsed straight from the table rather than guessed at via an id range,
    since the boundaries turned out not to be as clean as they first looked.
    """
    raw_text = xml_path.read_text(encoding="utf-8-sig")
    types: dict[int, str] = {}
    for block in re.finditer(r"<Ability>(.*?)</Ability>", raw_text, re.DOTALL):
        body = block.group(1)
        id_match = re.search(r"<Id>\s*(\d+)\s*</Id>", body)
        type_match = re.search(r"<AbilityType>([^<]*)</AbilityType>", body)
        if id_match and type_match:
            types[int(id_match.group(1))] = type_match.group(1).strip()
    return types


@dataclass
class JobCommandRecord:
    """One row of the Job Command (skillset) table."""
    command_id: int
    name: Optional[str]
    ability_ids: list = field(default_factory=list)   # 16 ints, action-menu abilities
    rsm_ids: list = field(default_factory=list)       # 6 ints, Reaction/Support/Movement

    @property
    def display_name(self) -> str:
        if self.name:
            return f"{self.command_id:03d} - {self.name}"
        return f"{self.command_id:03d} - (unnamed command)"


_ABILITY_SLOT_NAMES = [f"AbilityId{i}" for i in range(1, 17)]
_RSM_SLOT_NAMES = [f"ReactionSupportMovementId{i}" for i in range(1, 7)]


def load_job_command_table(xml_path: Path) -> tuple[list[JobCommandRecord], str]:
    """
    Parses JobCommandData.xml. Unlike JobData.xml, this file's Id range is
    genuinely non-contiguous (0-175 plus the War of the Lions-exclusive
    224-226 - see the file's own header comment), so there's no gap-filling
    here: whatever Ids are actually present are exactly what's returned.
    """
    raw_text = xml_path.read_text(encoding="utf-8-sig")
    root = ET.fromstring(raw_text)

    version_el = root.find("Version")
    version = version_el.text.strip() if version_el is not None and version_el.text else "1"

    entries = root.find("Entries")
    if entries is None:
        raise ValueError("No <Entries> element found - this doesn't look like a JobCommandData.xml")

    records: list[JobCommandRecord] = []
    for cmd_el in entries.findall("JobCommand"):
        id_el = cmd_el.find("Id")
        if id_el is None or id_el.text is None:
            continue
        command_id = int(id_el.text.strip())
        name = _find_name_comment_for_id(raw_text, command_id)

        def _read(slot_name: str) -> int:
            el = cmd_el.find(slot_name)
            try:
                return int(el.text.strip()) if el is not None and el.text else 0
            except ValueError:
                return 0

        records.append(
            JobCommandRecord(
                command_id=command_id,
                name=name,
                ability_ids=[_read(s) for s in _ABILITY_SLOT_NAMES],
                rsm_ids=[_read(s) for s in _RSM_SLOT_NAMES],
            )
        )

    records.sort(key=lambda r: r.command_id)
    return records, version


# ---------------------------------------------------------------------------
# Writing the trimmed diff file
# ---------------------------------------------------------------------------

_HEADER_COMMENT = """This table file is used to overwrite the game's hardcoded job table.

Refer to: https://ffhacktics.com/wiki/Job_Data
This table links to nex table 'Job'. Some properties edited here may be overriden by the nex table.

You can use this file as a base to edit Job data in your mod.
Simply copy this file to your mod's folder under FFTIVC/tables/<enhanced/classic/combined>/JobData.xml.

IMPORTANT: You are free to remove everything and **SHOULD ONLY LEAVE ELEMENTS THAT YOU HAVE EDITED** to avoid conflicts between mods.
Only properties that are actually included in this file will be tracked as edited. Properties not edited will inherit their
value from the original table or, from other mods making changes depending on mod order.

IMPORTANT 2: The Id property must NOT be removed for nodes that you're leaving here!

IMPORTANT 3: Id cannot be more than 175 (hardcoded table size is 176).

For available flags, refer to https://github.com/Nenkai/fftivc.utility.modloader/blob/master/fftivc.utility.modloader.Interfaces/Tables/Structures/JOB_DATA.cs
"""


def build_diff_xml_text(
    version: str,
    edited_jobs: list[tuple[JobRecord, dict[str, str], Optional[str]]],
    preserved: Optional[dict] = None,
) -> str:
    """
    edited_jobs: list of (job_record, {field_name: new_string_value, ...}, name_comment)
                 where the dict only contains fields the user chose to include.
                 A job with an empty dict is skipped entirely (nothing to write).
    """
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "", "<!--"]
    lines.append(_HEADER_COMMENT.rstrip())
    lines.append("-->")
    lines.append("")
    lines.append("<JobTable>")
    lines.append(f"  <Version>{version}</Version>")
    lines.append("  <Entries>")

    for record, included_fields, name_comment in edited_jobs:
        if not included_fields:
            continue
        id_comment = f" <!-- {name_comment} -->" if name_comment else ""
        lines.append("    <Job>")
        lines.append(f"      <Id>{record.job_id}</Id>{id_comment}")
        # Original order first, then anything newly included. A modelled
        # field appears only if still included, so unticking removes it; an
        # unmodelled element is always written back, because this tool has
        # no basis for deciding it isn't wanted.
        original = (preserved or {}).get(record.job_id, {})
        emitted = set()
        for tag, original_text in original.items():
            if tag in c.FIELD_ORDER:
                if tag in included_fields:
                    lines.append(f"      <{tag}>{included_fields[tag]}</{tag}>")
                    emitted.add(tag)
            else:
                lines.append(f"      <{tag}>{original_text}</{tag}>")
        for field_name in c.FIELD_ORDER:
            if field_name in included_fields and field_name not in emitted:
                lines.append(f"      <{field_name}>{included_fields[field_name]}</{field_name}>")
        lines.append("    </Job>")

    lines.append("  </Entries>")
    lines.append("</JobTable>")
    lines.append("")

    return "\n".join(lines)


def write_diff_xml(
    output_path: Path,
    version: str,
    edited_jobs: list[tuple[JobRecord, dict[str, str], Optional[str]]],
    preserved: Optional[dict] = None,
) -> None:
    output_path.write_text(
        build_diff_xml_text(version, edited_jobs, preserved), encoding="utf-8")


# ---------------------------------------------------------------------------
# Job Command (skillset) diff read/write - same idea as above, but for
# JobCommandData.xml's AbilityId1-16 / ReactionSupportMovementId1-6 fields.
# ExtendAbilityIdFlagBits / ExtendReactionSupportMovementIdFlagBits are
# deliberately never read or written - the loader computes those from the
# ids itself (see the table's own header comment).
# ---------------------------------------------------------------------------

JOB_COMMAND_FIELD_ORDER = _ABILITY_SLOT_NAMES + _RSM_SLOT_NAMES

_JOB_COMMAND_HEADER_COMMENT = """This table file is used to overwrite the game's hardcoded job command table.

Refer to: https://ffhacktics.com/wiki/Skillsets
This table links to nex table 'JobCommand'. Some properties edited here may be overriden by the nex table.

You can use this file as a base to edit Job Command data in your mod.
Simply copy this file to your mod's folder under FFTIVC/tables/<enhanced/classic/combined>/JobCommandData.xml.

IMPORTANT: You are free to remove everything and **SHOULD ONLY LEAVE ELEMENTS THAT YOU HAVE EDITED** to avoid conflicts between mods.
Only properties that are actually included in this file will be tracked as edited. Properties not edited will inherit their
value from the original table or, from other mods making changes depending on mod order.

IMPORTANT 2: The Id property must NOT be removed for nodes that you're leaving here!

IMPORTANT 3: Id must be 0-175 (main table, hardcoded size 176), OR 224-226 (Darkness/Piracy/
Huntcraft - Dark Knight/Sky Pirate/Game Hunter's War of the Lions-exclusive skillsets). 176-223
belong to MonsterJobCommandData, not this file.

IMPORTANT 4: You do not need to worry about setting ExtendAbilityIdFlagBits or ExtendReactionSupportMovementIdFlagBits.
The loader will fill these according to ids. You're free to use ids 0-512 directly.

For available flags, refer to https://github.com/Nenkai/fftivc.utility.modloader/blob/master/fftivc.utility.modloader.Interfaces/Tables/Structures/JOB_COMMAND_DATA.cs
"""


def parse_job_command_diff_xml(
    xml_path: Path,
) -> tuple[dict[int, dict[str, str]], str, dict[int, dict[str, str]]]:
    """
    Parses a MOD's JobCommandData.xml (a sparse diff file) into
    {command_id: {field: value}}. Same shape/purpose as parse_diff_xml,
    just for JobCommand's AbilityId/ReactionSupportMovementId fields.
    """
    raw_text = xml_path.read_text(encoding="utf-8-sig")
    root = ET.fromstring(raw_text)
    version_el = root.find("Version")
    version = version_el.text.strip() if version_el is not None and version_el.text else "1"

    result: dict[int, dict[str, str]] = {}
    preserved: dict[int, dict[str, str]] = {}
    entries = root.find("Entries")
    if entries is None:
        return result, version, preserved

    for cmd_el in entries.findall("JobCommand"):
        id_el = cmd_el.find("Id")
        if id_el is None or id_el.text is None:
            continue
        try:
            command_id = int(id_el.text.strip())
        except ValueError:
            continue

        fields: dict[str, str] = {}
        for field_name in JOB_COMMAND_FIELD_ORDER:
            el = cmd_el.find(field_name)
            if el is not None and el.text is not None:
                fields[field_name] = el.text.strip()

        # The entry exactly as it was, in its original order, so rewriting
        # this mod gives back what it came with.
        #
        # Opening a working mod and exporting it without touching anything
        # used to drop `ExtendAbilityIdFlagBits` and
        # `ExtendReactionSupportMovementIdFlagBits` - on the strength of the
        # table's own comment saying the loader fills them in - and the
        # loader then refused to read the result at all.
        #
        # Whether the loader ought to cope is beside the point. A round trip
        # that changes a mod nobody edited is wrong on its own terms, and
        # "give back what you can't model" costs nothing and covers the next
        # field nobody has thought about yet.
        #
        # Order is kept as well as content. Python dicts preserve insertion
        # order, so this doubles as the original element order, and the
        # writer follows it rather than reordering somebody's file.
        original: dict[str, str] = {}
        for child in cmd_el:
            if child.tag == "Id":
                continue
            original[child.tag] = (child.text or "").strip()

        if fields:
            result[command_id] = fields
        if original:
            preserved[command_id] = original

    return result, version, preserved


def build_job_command_diff_xml_text(
    version: str,
    edited_commands: list[tuple[JobCommandRecord, dict[str, str], Optional[str]]],
    preserved: Optional[dict] = None,
) -> str:
    """
    edited_commands: list of (command_record, {field_name: new_string_value, ...}, name_comment)
                      - same shape as build_diff_xml_text's edited_jobs.
    preserved: {command_id: {tag: text}} read out of the mod's own file for
               elements this tool doesn't model. Written back after the
               modelled fields so the canonical order still holds, because
               dropping them broke mods that had been working.
    """
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "", "<!--"]
    lines.append(_JOB_COMMAND_HEADER_COMMENT.rstrip())
    lines.append("-->")
    lines.append("")
    lines.append("<JobCommandTable>")
    lines.append(f"  <Version>{version}</Version>")
    lines.append("  <Entries>")

    for record, included_fields, name_comment in edited_commands:
        if not included_fields:
            continue
        id_comment = f" <!-- {name_comment} -->" if name_comment else ""
        lines.append("    <JobCommand>")
        lines.append(f"      <Id>{record.command_id}</Id>{id_comment}")
        # Original order first, then anything newly included.
        #
        # A modelled field is written only if it's still included - so
        # unticking one really removes it - while an unmodelled element is
        # always written back, because this tool has no basis for deciding
        # it isn't wanted.
        original = (preserved or {}).get(record.command_id, {})
        emitted = set()
        for tag, original_text in original.items():
            if tag in JOB_COMMAND_FIELD_ORDER:
                if tag in included_fields:
                    lines.append(f"      <{tag}>{included_fields[tag]}</{tag}>")
                    emitted.add(tag)
            else:
                lines.append(f"      <{tag}>{original_text}</{tag}>")
        for field_name in JOB_COMMAND_FIELD_ORDER:
            if field_name in included_fields and field_name not in emitted:
                lines.append(f"      <{field_name}>{included_fields[field_name]}</{field_name}>")
        lines.append("    </JobCommand>")

    lines.append("  </Entries>")
    lines.append("</JobCommandTable>")
    lines.append("")

    return "\n".join(lines)


def write_job_command_diff_xml(
    output_path: Path,
    version: str,
    edited_commands: list[tuple[JobCommandRecord, dict[str, str], Optional[str]]],
    preserved: Optional[dict] = None,
) -> None:
    output_path.write_text(
        build_job_command_diff_xml_text(version, edited_commands, preserved),
        encoding="utf-8")
