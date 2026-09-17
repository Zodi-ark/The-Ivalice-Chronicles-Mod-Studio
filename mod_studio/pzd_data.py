"""
Panzer (`.pzd`) text files - the game's dialogue, voice lines and subtitles.

The unpacked game holds 4,417 of these under `nxd/text/`:

    scenario 2422   battlevoice 553   unitlines 462   unitvoice 336
    battlelines 280 facilitylines 259 movie 63        facilityvoice 42

631 distinct stems in seven languages (cs, ct, de, en, fr, ja, ko), the same
language set every other table uses.

**Read here, written by FF16Tools.** This module parses `.pzd` natively and
emits the YAML that FF16Tools' `pzd-conv` turns back into a `.pzd`. The split
is deliberate and each half has a reason:

- Reading natively because the alternative is 4,417 x 7 subprocess calls to
  put text in front of somebody, which no amount of patience survives. Find
  Text has to walk all of them. Reading is also the safe half: the worst a
  wrong read can do is show the wrong string.
- Writing through `pzd-conv` because that is the half that can corrupt a
  game file, and FF16Tools is what the community already trusts with it.
  Hand-rolling a binary writer - pointer tables, string tables, padding -
  to save one subprocess on the handful of files somebody actually edits
  would be trading the tool's whole credibility for nothing.

That is the same division the `.nxd` path uses: the tool reads a converted
database and hands the writing back to FF16Tools.

The format is transcribed from FF16Tools' own source
(`FF16Tools.Files/Panzer/PzdFile.cs` and `PzdTextContent.cs`), not inferred
from sample files - there were none to infer from.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

#: `PZDF`, little-endian, at offset 0.
PZD_MAGIC = b"PZDF"

#: The only version FF16Tools supports: "Only Panzer files version 2 (FF16)".
PZD_VERSION = 2

#: Where the header keeps the line array's offset and count.
PZD_ARRAY_HEADER_OFFSET = 0x20

#: Size of one `PzdTextContent`, from its own `GetSize()`.
PZD_ENTRY_SIZE = 0x20

#: `LineShowType`, by value, from the enum in `PzdTextContent.cs`.
SHOW_TYPES = {
    0: "Normal",
    1: "AlwaysShow",
    2: "HearingImpairedSubtitle",
}

#: The folders under `nxd/text/` that hold these files.
TEXT_FOLDER = "text"

#: The languages these files come in - the same set as every other table.
PZD_LANGUAGES = ("en", "cs", "ct", "de", "fr", "ja", "ko")


@dataclass
class PzdLine:
    """
    One line of text, matching `PzdTextContent` field for field.

    Every field is carried, not just `line`, because the file is rewritten
    whole: a field this tool drops is a field the mod loses. `speaker_type`
    and `speaker_value` are the two halves of the `NexUnionKey` - a 16-bit
    type, two bytes of padding, then a 32-bit value.
    """
    line_id: int
    line: str = ""
    speaker_type: int = 0
    speaker_value: int = 0
    voice_sound_path: str = ""
    show_type: int = 0
    short_voice_sound_path: str = ""
    is_shortened: bool = False

    @property
    def show_type_name(self) -> str:
        return SHOW_TYPES.get(self.show_type, str(self.show_type))


@dataclass
class PzdTextFile:
    """One `.pzd`: where it came from, and the lines in it."""
    relative_path: str
    stem: str
    folder: str
    language: str
    lines: list = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return f"{self.folder}/{self.stem}"


def _read_c_string(data: bytes, offset: int) -> str:
    """
    A zero-terminated UTF-8 string at `offset`.

    Decoded with `replace` rather than strictly. A single bad byte in one
    line of one of 4,417 files should cost that line's accuracy, not the
    whole page - and a decode error here would otherwise take down a Find
    Text search across every file.
    """
    if offset <= 0 or offset >= len(data):
        return ""
    end = data.find(b"\0", offset)
    if end < 0:
        end = len(data)
    return data[offset:end].decode("utf-8", "replace")


def read_pzd_bytes(data: bytes) -> list:
    """
    Parses a `.pzd` into `PzdLine`s.

    Layout, from `PzdFile.Read` and `PzdTextContent.Read`:

        0x00  magic "PZDF"
        0x04  version (u16), must be 2
        0x20  int32 offset to the array, then uint32 count

    and each 0x20-byte entry, with string offsets relative to the ENTRY's
    own start rather than the file's:

        +0x00  u32   Id
        +0x04  i32   -> Line
        +0x08  i16   Speaker.Type,  +0x0A two bytes padding
        +0x0C  i32   Speaker.Value
        +0x10  i32   -> VoiceSoundPath
        +0x14  i32   ShowType
        +0x18  i32   -> ShortVoiceSoundPath
        +0x1C  u8    IsShortened, then three bytes padding

    The relative string offsets are the part worth stating out loud: they
    are what makes an entry movable, and reading them against the file start
    instead would give plausible-looking strings from the wrong lines.
    """
    if len(data) < PZD_ARRAY_HEADER_OFFSET + 8:
        raise ValueError("Too short to be a Panzer (.pzd) file.")
    if data[:4] != PZD_MAGIC:
        raise ValueError("Not a Panzer (.pzd) file - magic did not match "
                         "PZDF.")
    version = struct.unpack_from("<H", data, 4)[0]
    if version != PZD_VERSION:
        raise ValueError(f"Panzer file version {version} is not supported "
                         f"(FF16Tools reads version {PZD_VERSION} only).")

    array_offset, count = struct.unpack_from("<iI", data,
                                             PZD_ARRAY_HEADER_OFFSET)
    lines = []
    for index in range(count):
        base = array_offset + index * PZD_ENTRY_SIZE
        if base + PZD_ENTRY_SIZE > len(data):
            raise ValueError(f"Entry {index} runs past the end of the file.")
        (line_id, line_off, speaker_type, speaker_value, voice_off,
         show_type, short_off, shortened) = struct.unpack_from(
            "<IihxxiiiiB", data, base)
        lines.append(PzdLine(
            line_id=line_id,
            line=_read_c_string(data, base + line_off) if line_off else "",
            speaker_type=speaker_type,
            speaker_value=speaker_value,
            voice_sound_path=(_read_c_string(data, base + voice_off)
                              if voice_off else ""),
            show_type=show_type,
            short_voice_sound_path=(_read_c_string(data, base + short_off)
                                    if short_off else ""),
            is_shortened=bool(shortened)))
    return lines


def read_pzd(path: Path) -> list:
    return read_pzd_bytes(Path(path).read_bytes())


def _yaml_scalar(value) -> str:
    """
    One YAML scalar, always double-quoted for strings.

    Hand-written rather than through PyYAML on purpose: `yaml` is in the
    frozen build's exclusion list, with a comment saying the exclusion is
    there so that re-importing it fails loudly. Re-adding a library that was
    deliberately removed, to write seven fields, is not a trade worth
    making.

    Double quotes always, so nothing in a line of game dialogue can change
    the shape of the document - a leading `-`, a `: `, a `#`, a lone `*`,
    something that looks like a number or like `yes`. Escaping follows
    YAML's double-quoted rules, which are the same as JSON's for everything
    that appears here.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = "" if value is None else str(value)
    out = []
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20:
            out.append(f"\\x{ord(ch):02x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def build_pzd_yaml(lines: list) -> str:
    """
    The YAML `pzd-conv` reads back, matching `PzdFile.ReadFromYaml`.

    A LIST of entries with PascalCase keys, because that is what the
    deserializer is built with:

        new DeserializerBuilder()
            .WithNamingConvention(PascalCaseNamingConvention.Instance)

    `ShowType` is written by NAME rather than number - YamlDotNet maps enum
    members by name, and "Normal" survives a reader's eye where 0 does not.

    Every field is written, including the ones this tool does not edit. The
    conversion rebuilds the file from this document alone, so a field left
    out is a field the mod drops.
    """
    out = []
    for entry in lines:
        out.append(f"- Id: {entry.line_id}")
        out.append(f"  Line: {_yaml_scalar(entry.line)}")
        out.append("  Speaker:")
        out.append(f"    Type: {entry.speaker_type}")
        out.append(f"    Value: {entry.speaker_value}")
        # `TypeName` is the third member of `NexUnionKey` and `pzd-conv`
        # writes it, so it is written here - confirmed against a real
        # conversion rather than assumed from the struct.
        #
        # Always null, and that is correct: `NexUnionKey.FromStream` reads
        # only Type and Value out of the binary, so nothing in a `.pzd` can
        # ever populate it. Emitting the key keeps a document this tool
        # writes the same shape as one the converter writes, which is what
        # makes the two diffable.
        out.append("    TypeName:")
        out.append(f"  VoiceSoundPath: {_yaml_scalar(entry.voice_sound_path)}")
        out.append(f"  ShowType: {entry.show_type_name}")
        out.append("  ShortVoiceSoundPath: "
                   + _yaml_scalar(entry.short_voice_sound_path))
        out.append(f"  IsShortened: {_yaml_scalar(entry.is_shortened)}")
    return "\n".join(out) + "\n"


def split_pzd_name(relative_path: str) -> tuple:
    """
    `(folder, stem, language)` from a path like
    `nxd/text/scenario/scenario0001.en.pzd`.

    The language is the second-to-last dot part, which is how every other
    per-language file in this game is named.
    """
    posix = str(relative_path).replace("\\", "/")
    name = posix.rsplit("/", 1)[-1]
    folder = posix.rsplit("/", 2)[-2] if "/" in posix else ""
    parts = name.split(".")
    if len(parts) >= 3 and parts[-1].lower() == "pzd":
        return folder, ".".join(parts[:-2]), parts[-2]
    return folder, parts[0], ""


def scan_text_tree(unpack_dir: Optional[Path]) -> dict:
    """
    `{(folder, stem): {language: relative_path}}` for every `.pzd` found.

    Grouped by stem so one editable thing is one row with seven languages
    behind it, rather than seven rows that happen to share a prefix - the
    same shape the nxd language files already use.

    Returns empty when the game is not unpacked, rather than raising. A
    missing folder is the normal state before setup, not a fault.
    """
    found: dict = {}
    if not unpack_dir:
        return found
    root = Path(unpack_dir) / "nxd" / TEXT_FOLDER
    if not root.is_dir():
        return found
    for path in sorted(root.rglob("*.pzd")):
        relative = path.relative_to(Path(unpack_dir)).as_posix()
        folder, stem, language = split_pzd_name(relative)
        if not language:
            continue
        found.setdefault((folder, stem), {})[language] = relative
    return found


def search_text(unpack_dir, needle: str, languages=None,
                limit: int = 0) -> list:
    """
    Every `.pzd` line containing `needle`, as `nxd_data.TextHit`s.

    Returned in the SAME shape the database search returns so Find Text can
    show both kinds of result in one list. That matters more than it looks:
    a person searching for a line of dialogue does not know or care whether
    the game keeps it in a table or in a Panzer file, and two result lists
    would make them ask.

    `table` is named the way a database table is: the stem, then the
    language - "battlelinesgc008-en", beside "UI-en". It carried the folder
    too ("battlelines/battlelinesgc008") until that was reported as reading
    unlike everything else in the list, and the folder turns out to be
    doubly redundant: the 631 stems are unique across all eight folders,
    and every stem already begins with its own folder's name.

    Reads every file, which is why `pzd_data` parses natively: 4,417 files
    times seven languages is not something to do through a subprocess.
    Files that fail to parse are SKIPPED rather than raising - one bad file
    out of thousands must not empty the results.
    """
    from .nxd_data import TextHit

    lowered = needle.lower()
    hits: list = []
    wanted = set(languages) if languages else None
    for (folder, stem), by_language in scan_text_tree(unpack_dir).items():
        for language, relative in sorted(by_language.items()):
            if wanted and language not in wanted:
                continue
            try:
                lines = read_pzd(Path(unpack_dir) / relative)
            except (OSError, ValueError):
                continue
            for entry in lines:
                if lowered not in (entry.line or "").lower():
                    continue
                hits.append(TextHit(
                    table=f"{stem}-{language}" if language else stem,
                    base_table=stem,
                    language=language,
                    key=entry.line_id,
                    column="Line",
                    value=entry.line))
                if limit and len(hits) >= limit:
                    return hits
    return hits


def stage_pzd_export(relative_path: str, lines: list, staging_dir: Path,
                     cli_path) -> Path:
    """
    Writes the edited lines out as a `.pzd`, ready to copy into a mod.

    YAML first, then `pzd-conv`, because FF16Tools owns the binary writing.
    Confirmed working in both directions on real hardware:

        [Info] Converted yaml file 'battlelinesbs001.en.yaml' to panzer (.pzd)

    Raises rather than returning something wrong. A text file that silently
    failed to convert would leave the mod shipping nothing for a line
    somebody had edited, and they would find out from the game.
    """
    from . import ff16tools

    if cli_path is None:
        raise ValueError(
            "FF16Tools is needed to write text files and isn't set up. "
            "Set it under General Setup.")
    staging_dir = Path(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    # Flattened into one name, so two stems from different folders cannot
    # land on each other in the staging directory.
    stem = str(relative_path).replace("\\", "/").replace("/", "_")
    yaml_path = staging_dir / f"{stem}.yaml"
    yaml_path.write_text(build_pzd_yaml(lines), encoding="utf-8")
    pzd_path = yaml_path.with_suffix(".pzd")
    if pzd_path.exists():
        pzd_path.unlink()
    code = ff16tools.run_pzd_conv(cli_path, yaml_path)
    if code != 0 or not pzd_path.exists():
        raise ValueError(
            f"FF16Tools pzd-conv failed converting {yaml_path.name} "
            f"(exit code {code}).")
    return pzd_path


#: Every field of a line that can be edited, and how to coerce it back.
#:
#: Named from `PzdTextContent.cs` rather than chosen: `Id` is the key and is
#: not here, and everything else the struct carries is. A field this tool
#: reads but will not let anybody change is a field they have to leave
#: FF16Tools and hand-edit YAML for.
EDITABLE_FIELDS = {
    "line": str,
    "speaker_type": int,
    "speaker_value": int,
    "voice_sound_path": str,
    "show_type": int,
    "short_voice_sound_path": str,
    "is_shortened": bool,
}


def apply_line_edits(lines: list, edits: dict) -> list:
    """
    `lines` with `{line_id: {field: value}}` applied.

    Returns a new list; the originals are the file on disk and stay that
    way. Ids the file does not have are ignored rather than added - this
    tool edits the game's lines, and inventing one would write a row the
    game never asks for.

    Only the FIELDS named in an edit change. Somebody rewriting a subtitle
    is not also asking to reset its speaker.
    """
    out = []
    for entry in lines:
        fields = edits.get(entry.line_id)
        if not fields:
            out.append(entry)
            continue
        values = {name: getattr(entry, name) for name in EDITABLE_FIELDS}
        for name, raw in fields.items():
            if name not in EDITABLE_FIELDS:
                continue
            try:
                values[name] = EDITABLE_FIELDS[name](raw)
            except (TypeError, ValueError):
                # Left as the original rather than written as something the
                # game cannot read. The form validates first; this is the
                # backstop for an edit recovered from a file.
                continue
        out.append(PzdLine(line_id=entry.line_id, **values))
    return out


def voice_key(sab_path) -> tuple:
    """
    `(language-neutral voice path, language)` for a sound archive.

    **The game's `.sab` files carry a language and a `.pzd`'s
    `VoiceSoundPath` does not.** The real tree holds

        sound/voice/battlelines/battlelinesbs001/vo_..._001_001.en.sab
        sound/voice/battlelines/battlelinesbs001/vo_..._001_001.ja.sab

    while the line that subtitles them both points at

        sound/voice/battlelines/battlelinesbs001/vo_..._001_001.sab

    which is right: one line per recording, per language, and the path names
    the recording rather than one language's copy of it. Keying the index on
    the literal string therefore matched nothing at all - the Subtitle box
    disappeared on exactly the files that have subtitles.

    The language falls out of the same split, which is the useful half: pick
    the Japanese recording and the Japanese subtitle is the one to show.
    """
    text = str(sab_path).replace("\\", "/")
    if not text.endswith(".sab"):
        return text, ""
    stem = text[:-len(".sab")]
    head, _, maybe = stem.rpartition(".")
    if head and maybe in PZD_LANGUAGES:
        return f"{head}.sab", maybe
    return text, ""


def voice_path_for_language(neutral_path: str, language: str) -> str:
    """
    The archive a line's voice path means, in one language.

    The inverse of `voice_key`: a line points at `vo_x_001.sab` and the
    game ships `vo_x_001.en.sab`. Going one way was enough to SHOW a
    subtitle beside its recording; going back is what a jump from Find Text
    needs to select the recording in the first place.
    """
    text = str(neutral_path).replace("\\", "/")
    if not language or not text.endswith(".sab"):
        return text
    return f"{text[:-len('.sab')]}.{language}.sab"


def build_voice_index(unpack_dir) -> dict:
    """
    `{voice path: (relative path, line id)}` for every line in the game.

    **The join that puts subtitles on the Sounds page.** Measured across the
    real files: 14,208 lines, 14,208 distinct voice paths, 100% of lines
    carrying one, every one a `.sab` under `sound/voice/`. The relationship
    is not incidental - it is total and one-to-one, because these lines ARE
    the subtitles for those recordings.

    Reading every file to build it costs about 3 seconds for the full
    4,417; 0.4s for the 629 in a typical text mod. Worth doing once, on a
    worker, rather than per selection.
    """
    index: dict = {}
    for (folder, stem), by_language in scan_text_tree(unpack_dir).items():
        for language, relative in by_language.items():
            try:
                lines = read_pzd(Path(unpack_dir) / relative)
            except (OSError, ValueError):
                continue
            for entry in lines:
                if entry.voice_sound_path:
                    index[entry.voice_sound_path] = (relative, entry.line_id)
    return index
