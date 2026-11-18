"""
Builds Mod Studio Framework, the helper mod (Zodi, 21 October: "One
shared helper mod", called "Mod Studio Event Setup", "Its own release, and
in Mod Studio"; renamed 2 November, his eighth, its mod id and its files'
names kept), into `tools/ModStudioEventSetup/`: the copy Mod Studio
ships and puts in Reloaded-II for an author's own testing, and what its own
release is made from.

    python3 helper/build.py <Reloaded.Mod.Interfaces.dll> \
        <Reloaded.Hooks.Definitions.dll> <Reloaded.Hooks.ReloadedII.Interfaces.dll>

Needs the .NET 8 SDK. The first DLL is Reloaded-II's interfaces (GPL-3.0):
the one in `reloaded.mod.interfaces.2.5.0.nupkg`, a zip, under
`lib/netcoreapp3.1/` (or 2.4.0's). The other two (1.1.0, for the side
quests' hooks) are Reloaded-II's shared hooks' interfaces (LGPL-3.0), which
ship beside the helper as WotL Restoration carries them:
`reloaded.hooks.definitions.1.11.0.nupkg`'s `lib/net6.0/` and
`reloaded.sharedlib.hooks.1.9.0.nupkg`'s `lib/netstandard2.0/`, with their
license (LGPL-3.0's text, in the helper's `NOTICE.md`) and the helper's own
(`LICENSE`, Mod Studio's GPL-3.0) beside them. Built in a copy of the source
in a scratch folder, so no `bin/` or `obj/` lands in the project.
Deterministic: the same source makes the same DLL byte for byte wherever it
is built (`dev/test_event_setup.py` checks that the shipped one is this
source's).

The helper asks Reloaded-II for its interfaces at 2.4.0 or newer
(`REFERENCE_VERSION`): what Reloaded-II shipped from April 2023 until 1.30
(January 2026), and what WotL Restoration is built against. A DLL built
against 2.5.0 as it is asks for 2.5.0, which .NET refuses to give it in a
Reloaded-II from before 1.30, so the build compiles against a copy of the
interfaces whose own version reads 2.4.0 (`interfaces_reference`). The
helper uses nothing 2.5.0 added (2.5.0 added to mods' configuration
settings): its mod entry, the loader's GetLogger, GetActiveMods,
ModLoaded, OnModLoaderInitialized, GetController and
GetDirectoryForModId, the mod configuration's ModId and ModName, and the
logger's WriteLine and PrintMessage, all there since Reloaded-II's
interfaces 2.0; and, where the loader has it, GetModConfigDirectory (the
side quests' numbers' folder, 1.1.0), else its own folder. The copy is
made in the scratch folder and never ships.
"""
from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: What the build puts in Mod Studio's copy.
SHIPPED = ("ModConfig.json", "ModStudioEventSetup.dll", "ModStudioEventSetup.deps.json", "Preview.png",
           "Reloaded.Hooks.Definitions.dll", "Reloaded.Hooks.ReloadedII.Interfaces.dll")
#: The licenses it carries (1.2.0): each one's name beside it and its file in Mod Studio's folder. The
#: hooks' interfaces are LGPL-3.0, whose text goes with them, and the GPL's with it.
LICENSES = {"LICENSE": "LICENSE", "NOTICE.md": "helper/NOTICE.md"}
#: (1.2.5) What it gives the game besides its program, at the game's paths (the mod loader serves a mod's
#: FFTIVC folder): the side quests' marker's picture and its part list
#: (dev/research/sidequests/make_marker_picture.py).
DATA = {
    "FFTIVC/data/enhanced/ui/ffto/worldmap/texture/msq_quest_marker_uitx.tex": "helper/marker/msq_quest_marker_uitx.tex",
    "FFTIVC/data/enhanced/ui/ffto/worldmap/textureparts/msq_quest_marker_uitx.utexpt":
        "helper/marker/msq_quest_marker_uitx.utexpt",
}
#: (The twenty third session, toward 2.0.0) War of the Lions' 40 items' own icons (helper/wotl_items/, made by
#: dev/research/sidequests/make_wotl_icons.py from Zodi's own pictures): each one's menus' texture and part list and
#: its small one's, at the paths the game's own item icons have.
_ICONS = "FFTIVC/data/enhanced/ui/ffto/icon"
for _file in sorted((ROOT / "helper" / "wotl_items").glob("msf_wotl_*.*")):
    _small = _file.stem.endswith("_s")
    _kind = "texture" if _file.suffix == ".tex" else "textureparts"
    DATA[f"{_ICONS}/equip_item{'_s' if _small else ''}/{_kind}/{_file.name}"] = f"helper/wotl_items/{_file.name}"
INTERFACES_NAME = "Reloaded.Mod.Interfaces"
#: The shared hooks' interfaces the helper carries (1.1.0): each DLL's name and version.
HOOKS = {"Reloaded.Hooks.Definitions": (1, 11, 0, 0), "Reloaded.Hooks.ReloadedII.Interfaces": (1, 9, 0, 0)}
#: The interfaces version the helper asks Reloaded-II for (see above).
REFERENCE_VERSION = (2, 4, 0, 0)


# ---------------------------------------------------------------------------
# A .NET assembly's name, version and references, from its metadata tables
# (ECMA-335, partition II, 22 and 24): only as far as the AssemblyRef table.
# ---------------------------------------------------------------------------
U2, U4, STR, GUID, BLOB = "u2", "u4", "str", "guid", "blob"
#: Coded indexes: how many tag bits, and which tables they point into.
CODED = {
    "TypeDefOrRef": (2, (0x02, 0x01, 0x1B)),
    "HasConstant": (2, (0x04, 0x08, 0x17)),
    "HasCustomAttribute": (5, (0x06, 0x04, 0x01, 0x02, 0x08, 0x09, 0x0A, 0x00, 0x0E, 0x17, 0x14, 0x11,
                               0x1A, 0x1B, 0x20, 0x23, 0x26, 0x27, 0x28, 0x2A, 0x2C, 0x2B)),
    "HasFieldMarshal": (1, (0x04, 0x08)),
    "HasDeclSecurity": (2, (0x02, 0x06, 0x20)),
    "MemberRefParent": (3, (0x02, 0x01, 0x1A, 0x06, 0x1B)),
    "HasSemantics": (1, (0x14, 0x17)),
    "MethodDefOrRef": (1, (0x06, 0x0A)),
    "MemberForwarded": (1, (0x04, 0x06)),
    "CustomAttributeType": (3, (0x06, 0x0A)),
    "ResolutionScope": (2, (0x00, 0x1A, 0x23, 0x01)),
}
#: Each table's columns, up to AssemblyRef (0x23).
COLUMNS = {
    0x00: (U2, STR, GUID, GUID, GUID),                                  # Module
    0x01: (("c", "ResolutionScope"), STR, STR),                         # TypeRef
    0x02: (U4, STR, STR, ("c", "TypeDefOrRef"), ("i", 0x04), ("i", 0x06)),  # TypeDef
    0x03: (("i", 0x04),),                                               # FieldPtr
    0x04: (U2, STR, BLOB),                                              # Field
    0x05: (("i", 0x06),),                                               # MethodPtr
    0x06: (U4, U2, U2, STR, BLOB, ("i", 0x08)),                         # MethodDef
    0x07: (("i", 0x08),),                                               # ParamPtr
    0x08: (U2, U2, STR),                                                # Param
    0x09: (("i", 0x02), ("c", "TypeDefOrRef")),                         # InterfaceImpl
    0x0A: (("c", "MemberRefParent"), STR, BLOB),                        # MemberRef
    0x0B: (U2, ("c", "HasConstant"), BLOB),                             # Constant
    0x0C: (("c", "HasCustomAttribute"), ("c", "CustomAttributeType"), BLOB),  # CustomAttribute
    0x0D: (("c", "HasFieldMarshal"), BLOB),                             # FieldMarshal
    0x0E: (U2, ("c", "HasDeclSecurity"), BLOB),                         # DeclSecurity
    0x0F: (U2, U4, ("i", 0x02)),                                        # ClassLayout
    0x10: (U4, ("i", 0x04)),                                            # FieldLayout
    0x11: (BLOB,),                                                      # StandAloneSig
    0x12: (("i", 0x02), ("i", 0x14)),                                   # EventMap
    0x13: (("i", 0x14),),                                               # EventPtr
    0x14: (U2, STR, ("c", "TypeDefOrRef")),                             # Event
    0x15: (("i", 0x02), ("i", 0x17)),                                   # PropertyMap
    0x16: (("i", 0x17),),                                               # PropertyPtr
    0x17: (U2, STR, BLOB),                                              # Property
    0x18: (U2, ("i", 0x06), ("c", "HasSemantics")),                     # MethodSemantics
    0x19: (("i", 0x02), ("c", "MethodDefOrRef"), ("c", "MethodDefOrRef")),  # MethodImpl
    0x1A: (STR,),                                                       # ModuleRef
    0x1B: (BLOB,),                                                      # TypeSpec
    0x1C: (U2, ("c", "MemberForwarded"), STR, ("i", 0x1A)),             # ImplMap
    0x1D: (U4, ("i", 0x04)),                                            # FieldRVA
    0x1E: (U4, U4),                                                     # EncLog
    0x1F: (U4,),                                                        # EncMap
    0x20: (U4, U2, U2, U2, U2, U4, BLOB, STR, STR),                     # Assembly
    0x21: (U4,),                                                        # AssemblyProcessor
    0x22: (U4, U4, U4),                                                 # AssemblyOS
    0x23: (U2, U2, U2, U2, U4, BLOB, STR, STR, BLOB),                   # AssemblyRef
}
ASSEMBLY, ASSEMBLY_REF = 0x20, 0x23


class Metadata:
    """Where a .NET assembly's Assembly and AssemblyRef rows are in its file."""

    def __init__(self, data: bytes):
        self.data = data
        if data[:2] != b"MZ":
            raise ValueError("not a program file")
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        if data[pe:pe + 4] != b"PE\0\0":
            raise ValueError("not a program file")
        count, optional = struct.unpack_from("<H", data, pe + 6)[0], struct.unpack_from("<H", data, pe + 20)[0]
        magic = struct.unpack_from("<H", data, pe + 24)[0]
        directories = pe + 24 + (96 if magic == 0x10B else 112)
        cli_rva = struct.unpack_from("<I", data, directories + 14 * 8)[0]
        if not cli_rva:
            raise ValueError("not a .NET assembly")
        table = pe + 24 + optional
        self.sections = [struct.unpack_from("<IIII", data, table + 40 * i + 8) for i in range(count)]
        cli = self.offset(cli_rva)
        root = self.offset(struct.unpack_from("<I", data, cli + 8)[0])
        if struct.unpack_from("<I", data, root)[0] != 0x424A5342:
            raise ValueError("no metadata")
        at = root + 16 + struct.unpack_from("<I", data, root + 12)[0]
        streams = {}
        at, count = at + 4, struct.unpack_from("<H", data, at + 2)[0]
        for _ in range(count):
            where, size = struct.unpack_from("<II", data, at)
            end = data.index(b"\0", at + 8)
            streams[data[at + 8:end].decode("ascii")] = root + where
            at += 8 + ((end - (at + 8) + 1 + 3) & ~3)
        if "#~" not in streams or "#Strings" not in streams:
            raise ValueError("no compressed metadata tables")
        self.strings = streams["#Strings"]
        tables = streams["#~"]
        heaps = data[tables + 6]
        valid = struct.unpack_from("<Q", data, tables + 8)[0]
        at = tables + 24
        self.rows = [0] * 64
        for t in range(64):
            if valid >> t & 1:
                self.rows[t] = struct.unpack_from("<I", data, at)[0]
                at += 4
        if heaps & 0x40:
            at += 4
        if any(self.rows[t] for t in range(ASSEMBLY_REF + 1) if t not in COLUMNS):
            raise ValueError("a metadata table this reader doesn't know")
        self.sizes = {STR: 4 if heaps & 1 else 2, GUID: 4 if heaps & 2 else 2, BLOB: 4 if heaps & 4 else 2,
                      U2: 2, U4: 4}
        self.at = {}
        for t in range(ASSEMBLY_REF + 1):
            self.at[t] = at
            at += self.rows[t] * sum(self.size(c) for c in COLUMNS[t])

    def offset(self, rva: int) -> int:
        for size, address, raw_size, raw in self.sections:
            if address <= rva < address + max(size, raw_size):
                return raw + rva - address
        raise ValueError(f"RVA {rva:#x} is in no section")

    def size(self, column) -> int:
        if isinstance(column, str):
            return self.sizes[column]
        kind, what = column
        if kind == "i":
            return 2 if self.rows[what] < 1 << 16 else 4
        bits, tables = CODED[what]
        return 2 if max(self.rows[t] for t in tables) < 1 << (16 - bits) else 4

    def fields(self, table: int, row: int) -> list:
        """One row's columns, each as (file offset, value)."""
        at = self.at[table] + row * sum(self.size(c) for c in COLUMNS[table])
        out = []
        for column in COLUMNS[table]:
            size = self.size(column)
            out.append((at, int.from_bytes(self.data[at:at + size], "little")))
            at += size
        return out

    def string(self, index: int) -> str:
        start = self.strings + index
        return self.data[start:self.data.index(b"\0", start)].decode("utf-8")


def assembly(data: bytes) -> tuple:
    """An assembly's own name and version: ("Reloaded.Mod.Interfaces", (2, 5, 0, 0))."""
    meta = Metadata(data)
    if meta.rows[ASSEMBLY] != 1:
        raise ValueError("not an assembly")
    row = meta.fields(ASSEMBLY, 0)
    return meta.string(row[7][1]), tuple(value for _, value in row[1:5])


def references(data: bytes) -> dict:
    """The assemblies an assembly asks for, by name, with the versions it asks for."""
    meta = Metadata(data)
    out = {}
    for n in range(meta.rows[ASSEMBLY_REF]):
        row = meta.fields(ASSEMBLY_REF, n)
        out[meta.string(row[6][1])] = tuple(value for _, value in row[0:4])
    return out


def with_version(data: bytes, version: tuple) -> bytes:
    """A copy of an assembly whose own version reads `version`; nothing else changed."""
    meta = Metadata(data)
    if meta.rows[ASSEMBLY] != 1:
        raise ValueError("not an assembly")
    out = bytearray(data)
    for (at, _), value in zip(meta.fields(ASSEMBLY, 0)[1:5], version):
        struct.pack_into("<H", out, at, value)
    return bytes(out)


def interfaces_reference(interfaces: Path, folder: Path) -> Path:
    """
    What to compile against: `interfaces` itself when its version is
    `REFERENCE_VERSION` or older, else a copy in `folder` whose version reads
    `REFERENCE_VERSION`, so the helper asks Reloaded-II for no newer
    interfaces than that.
    """
    data = interfaces.read_bytes()
    name, version = assembly(data)
    if name != INTERFACES_NAME:
        raise ValueError(f"{interfaces} is {name}, not {INTERFACES_NAME}")
    if version <= REFERENCE_VERSION:
        return interfaces
    copy = folder / "reference" / interfaces.name
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(with_version(data, REFERENCE_VERSION))
    return copy


def hooks_folder(hooks: list, folder: Path) -> Path:
    """
    A folder in `folder` holding the shared hooks' two interface DLLs, each
    checked to be the one `HOOKS` names at its version.
    """
    found = {}
    for path in hooks:
        name, version = assembly(Path(path).read_bytes())
        if HOOKS.get(name) != version:
            raise ValueError(f"{path} is {name} {'.'.join(map(str, version))}, not one of the shared hooks' "
                             f"interfaces the helper carries")
        found[name] = Path(path)
    if set(found) != set(HOOKS):
        raise ValueError(f"the shared hooks' interfaces given are {sorted(found)}, not {sorted(HOOKS)}")
    target = folder / "hooks"
    target.mkdir(parents=True, exist_ok=True)
    for name, path in found.items():
        shutil.copy2(path, target / f"{name}.dll")
    return target


def build(root: Path, interfaces: Path, out: Path, project: str = "ModStudioEventSetup",
          hooks: list | None = None) -> subprocess.CompletedProcess:
    """
    Builds `helper/<project>` of the project at `root` into `out`, in a
    scratch copy laid out as the project is (the helper beside `assets/`).
    `hooks`: the shared hooks' two interface DLLs (the helper's project needs
    them; the checks' don't). Paths are taken from where this runs: `dotnet`
    runs in the scratch copy, so `out` and `interfaces` are made absolute
    first (a relative `out` would build into the copy, deleted after).
    """
    out, interfaces = Path(out).resolve(), Path(interfaces).resolve()
    with tempfile.TemporaryDirectory(prefix="helper_build_") as scratch:
        copy = Path(scratch) / "project"
        shutil.copytree(root / "helper", copy / "helper",
                        ignore=shutil.ignore_patterns("bin", "obj", "__pycache__"))
        (copy / "assets").mkdir()
        shutil.copy2(root / "assets" / "icon_256.png", copy / "assets" / "icon_256.png")
        reference = interfaces_reference(interfaces, Path(scratch)) if interfaces.is_file() else interfaces
        command = ["dotnet", "build", "-c", "Release", "-nologo", "-o", str(out),
                   f"-p:ReloadedInterfaces={reference}"]
        if hooks:
            command.append(f"-p:ReloadedHooks={hooks_folder(hooks, Path(scratch))}")
        return subprocess.run(command, cwd=str(copy / "helper" / project), capture_output=True, text=True,
                              timeout=600)


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    interfaces = Path(sys.argv[1]).resolve()
    hooks = [Path(p).resolve() for p in sys.argv[2:4]]
    with tempfile.TemporaryDirectory(prefix="helper_out_") as out:
        done = build(ROOT, interfaces, Path(out), hooks=hooks)
        if done.returncode != 0:
            print(done.stdout + done.stderr)
            return 1
        target = ROOT / "tools" / "ModStudioEventSetup"
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        for name in SHIPPED:
            shutil.copy2(Path(out) / name, target / name)
        for name, source in LICENSES.items():
            shutil.copy2(ROOT / source, target / name)
        for name, source in DATA.items():
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / source, target / name)
    print(f"Built into {target}: {', '.join(SHIPPED + tuple(LICENSES) + tuple(DATA))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
