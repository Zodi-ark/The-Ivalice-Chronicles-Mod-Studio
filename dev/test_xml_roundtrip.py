"""Opening a mod and exporting it unchanged must not alter its XML.

Written after a working mod stopped loading. Mod Studio dropped
`ExtendAbilityIdFlagBits` and `ExtendReactionSupportMovementIdFlagBits` from
every JobCommandData entry - on the strength of the table's own comment
saying the loader fills them in - and the loader then refused to read the
file at all:

    YAXPropertyCannotBeAssignedTo: Could not assign to the property
    'AbilityId1'

Whether the loader ought to cope is beside the point. A round trip that
changes a mod nobody edited is wrong on its own terms, and the same hole
existed in every XML table this tool rewrites.

Driven by the real files from the report where they're available.
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fft_job_editor import item_xml_io, xml_io

XMLERR = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "xmlerr"
ORIGINAL = XMLERR / "Original Mod" / "JobCommandData.xml"
BROKEN = XMLERR / "Mod Studio After Opening Mod - No Edits Done" / "JobCommandData.xml"

passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {label}")
    else: failed += 1; print(f"  FAIL  {label}  ({detail})")


def entries_of(source, is_text=False):
    root = ET.fromstring(source) if is_text else ET.parse(source).getroot()
    return [[(child.tag, (child.text or "").strip()) for child in entry]
            for entry in root.find("Entries")]


class FakeCommand:
    def __init__(self, command_id): self.command_id = command_id; self.name = None


if ORIGINAL.exists():
    # What went wrong, recorded so the shape of the bug stays legible.
    before = entries_of(ORIGINAL)
    after = entries_of(BROKEN)
    lost = [tag for entry_before, entry_after in zip(before, after)
            for tag, _v in entry_before if tag not in dict(entry_after)]
    check("the reported output really had dropped elements", bool(lost), lost)
    check("and they were the two flag fields",
          set(lost) == {"ExtendAbilityIdFlagBits", "ExtendReactionSupportMovementIdFlagBits"},
          sorted(set(lost)))

    edits, version, preserved = xml_io.parse_job_command_diff_xml(ORIGINAL)
    check("reading keeps the unmodelled elements", bool(preserved), preserved)
    check("one preserved record per entry", len(preserved) == len(edits))

    rebuilt = xml_io.build_job_command_diff_xml_text(
        version, [(FakeCommand(i), edits[i], None) for i in sorted(edits)], preserved)
    check("a no-op round trip is identical, element for element and in order",
          entries_of(rebuilt, is_text=True) == before)

    # Editing must still work in both directions.
    changed = {i: dict(fields) for i, fields in edits.items()}
    first = sorted(changed)[0]
    changed[first]["AbilityId2"] = "999"
    edited = entries_of(xml_io.build_job_command_diff_xml_text(
        version, [(FakeCommand(i), changed[i], None) for i in sorted(changed)],
        preserved), is_text=True)
    check("an edited value is written", ("AbilityId2", "999") in edited[0])
    check("while the unmodelled elements stay put",
          ("ExtendAbilityIdFlagBits", "0") in edited[0])

    trimmed = {i: {f: v for f, v in fields.items() if f != "AbilityId2"}
               for i, fields in edits.items()}
    untick = entries_of(xml_io.build_job_command_diff_xml_text(
        version, [(FakeCommand(i), trimmed[i], None) for i in sorted(trimmed)],
        preserved), is_text=True)
    check("unticking a modelled field really removes it",
          not any(tag == "AbilityId2" for entry in untick for tag, _v in entry))
    check("but never removes an unmodelled one - this tool can't know it's unwanted",
          all(any(tag == "ExtendAbilityIdFlagBits" for tag, _v in entry) for entry in untick))
else:
    print(f"  (no reference files at {XMLERR}; skipping the real-file checks)")

# --- The same property, for the other two readers -------------------------
TMP = ROOT.parent / "_xmlrt_tmp"
TMP.mkdir(exist_ok=True)

job_xml = TMP / "JobData.xml"
job_xml.write_text(
    '<?xml version="1.0" encoding="utf-8"?>\n<JobTable>\n  <Version>1</Version>\n'
    "  <Entries>\n    <Job>\n      <Id>3</Id>\n"
    "      <SomethingUnmodelled>keep me</SomethingUnmodelled>\n"
    "      <JobCommandId>40</JobCommandId>\n    </Job>\n  </Entries>\n</JobTable>\n",
    encoding="utf-8")
job_edits, job_version, job_preserved = xml_io.parse_diff_xml(job_xml)
check("JobData keeps an unmodelled element", "SomethingUnmodelled" in job_preserved.get(3, {}))

class FakeJob:
    def __init__(self, job_id): self.job_id = job_id; self.name = None
job_out = entries_of(xml_io.build_diff_xml_text(
    job_version, [(FakeJob(3), job_edits[3], None)], job_preserved), is_text=True)
check("and writes it back", ("SomethingUnmodelled", "keep me") in job_out[0])
check("in its original position, before the modelled field",
      [tag for tag, _v in job_out[0]] == ["Id", "SomethingUnmodelled", "JobCommandId"],
      [tag for tag, _v in job_out[0]])

spec = item_xml_io.ALL_SPECS["item"]
item_xml = TMP / "ItemData.xml"
item_xml.write_text(
    f'<?xml version="1.0" encoding="utf-8"?>\n<{spec.root_tag}>\n  <Version>1</Version>\n'
    f"  <Entries>\n    <{spec.entry_tag}>\n      <Id>5</Id>\n"
    f"      <FutureField>hello</FutureField>\n"
    f"      <{spec.field_order[0]}>7</{spec.field_order[0]}>\n"
    f"    </{spec.entry_tag}>\n  </Entries>\n</{spec.root_tag}>\n",
    encoding="utf-8")
item_edits, item_version, item_preserved = item_xml_io.parse_diff_xml(item_xml, spec)
check("the generic table engine keeps one too",
      "FutureField" in item_preserved.get(5, {}), item_preserved)

class FakeItem:
    def __init__(self, item_id): self.item_id = item_id; self.name = None
item_out = entries_of(item_xml_io.build_diff_xml_text(
    spec, item_version, [(FakeItem(5), item_edits[5], None)], item_preserved), is_text=True)
check("and writes it back in place",
      [tag for tag, _v in item_out[0]] == ["Id", "FutureField", spec.field_order[0]],
      [tag for tag, _v in item_out[0]])

# An entry the mod never had must not gain anything.
fresh = entries_of(item_xml_io.build_diff_xml_text(
    spec, "1", [(FakeItem(99), {spec.field_order[0]: "1"}, None)], item_preserved),
    is_text=True)
check("a newly added entry gets only what was asked for",
      [tag for tag, _v in fresh[0]] == ["Id", spec.field_order[0]], fresh[0])

import shutil
shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
