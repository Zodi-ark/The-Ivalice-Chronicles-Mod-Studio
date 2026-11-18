"""
A unit sprite's sheet as a mod replaces it, at the game's size and at a
bigger one (Zodi's second point of 16 November 2026: "On the Textures page of
Mod Studio, not only should we be able to view Sprite textures there and
replace them like in the new Jobs page (we currently can not), but also be
able to replace the ... files with those of higher resolution ... In game the
texture upscaled will be the same size on the screen as before but higher
resolution"; his two choices of that day, each the recommended one: the bigger
picture is given on the Textures page, and the page lists the units' sprites
in a group of their own, each by its name).

What a sprite is, as the game keeps it (`unit_sprites.py`'s note): two
entries of `system/ffto/g2d.dat`, its upper texture (512 by 512 pixels at 4
bits a pixel, the left pixel in a byte's low four bits) and its lower (512
wide, the game's own 464 rows), drawn in the 16 palettes of its classic
sprite file. `data/UnitSprites.txt` says which two entries each sprite number
has.

What a mod's own picture of one becomes at Export (`write`):

- **At the game's size**, the two entries as the mod loader replaces one:
  `FFTIVC/data/enhanced/system/ffto/g2d/tex_<entry>.bin`, each 131,072 bytes
  (the lower texture's rows past its own left see through), as other mods'
  are (Dark Knight & Onion Knight (Generic)'s files are that size). No Mod
  Studio Framework is needed for these.
- **Bigger** (2 to 8 times the size, the same color numbers): besides the two
  files above (the bigger picture made the game's size, every `scale`th pixel
  of every `scale`th row, so the sprite is the mod's wherever the framework
  doesn't reach), the mod's `ModStudioTextures.json` names a sheet for each of
  the two entries, `ModStudioTextures/sprite_<entry>.bin`, as Mod Studio
  Framework reads them (`helper/ModStudioEventSetup/BigTextures.cs`: "MSBT",
  version 1, 4 bits, the scale, the width and height in pixels, then the
  rows). The framework draws them through the game's own palette of the
  moment, so every palette a unit wears colors the bigger sheet. The mod then
  needs Mod Studio Framework.

A picture's colors: one whose colors are numbered (a PNG of 16 colors or
fewer, as Export as PNG writes one) keeps its numbers; in any other each
pixel is the nearest of the 15 shown colors of the palette it is given under,
see through where it is more than half see through (`numbers_of`).

Opening a mod reads its pictures back (`read`): a sprite whose two entries
the mod replaces is the page's again, with its bigger sheets where
`ModStudioTextures.json` names both.

**A job's own figure given bigger** (the New Content page's Jobs tab; his
words: "New Jobs sprites should be able to have this as well") is named in
the same file, by the job (`{"Job": name, "Who": "Man", "Half": "Upper",
"File": ...}`: `job_looks.big_sheets` makes the list, `files` and `write`
take it as `jobs`, and `read_jobs` reads it back), so the mod has one
`ModStudioTextures.json` whichever page gave a bigger picture.

**A picture of more colors** (the thirtieth session; his choices of 17
November: tied to one palette, up to 4 times the game's size, and Replace...
keeps an image's own colors): an image whose drawn pixels aren't all the shown
palette's colors (five bits a part, `own_colors.own_of`), at the game's size or
up to 4 times it, keeps its own colors for that palette (`SpriteArt.own_upper`,
`own_lower`, `tied`) besides its numbers, which are as before (the nearest
colors). Export writes the two entries at the game's size as before and, named
in the same file, a sheet of more colors for each (`own_colors.sheet_file`:
"MSBT", version 2), which Mod Studio Framework draws in its own colors where the
game draws the sprite in that palette. An image 5 to 8 times the size keeps the
palette's colors only, as before.

Nothing here imports Qt; Pillow is imported where a picture is read.
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import own_colors as oc
from . import unit_sprites as us

#: Where the mod loader takes a replaced entry of g2d.dat from, and how it names one.
G2D_FOLDER = "FFTIVC/data/enhanced/system/ffto/g2d"
TEXTURE_BYTES = us.SHEET_WIDTH * us.SHEET_WIDTH // 2
ROW_BYTES = us.SHEET_WIDTH // 2
#: The rows of a sprite's sheet: its upper texture's, and the most both have.
UPPER_ROWS = us.SHEET_WIDTH
MOST_ROWS = 2 * us.SHEET_WIDTH
#: The file Mod Studio Framework reads a mod's bigger sheets from, and the folder they are written to.
FILE = "ModStudioTextures.json"
FOLDER = "ModStudioTextures"
MAGIC = b"MSBT"
HEADER_BYTES = 16
#: How many times the game's size a bigger sheet may be (the framework's `MinScale` and `MaxScale`).
SCALES = tuple(range(2, 9))

SIZE_BAD = ("A sprite's sheet is an image 512 pixels wide and 513 to 1,024 tall (the game's are 976), or one 2 to 8 "
            "times that size for a bigger picture, not {w} by {h}.")
SHEET_BAD = "its bigger sheet {file} can't be read here ({why})"
#: (The thirtieth session) Two sheets of one sprite that aren't one picture (one of more colors and one not, or of two
#: sizes or two palettes).
SHEETS_APART = "its two bigger sheets aren't one picture"


class SpriteTextureError(ValueError):
    """A picture that can't be a sprite's sheet; its message is for the reader."""


@dataclass
class SpriteArt:
    """A mod's own picture of one of the game's sprites: its two textures at the game's size (as g2d.dat keeps a
    sprite's), and, where the picture given was bigger, its two textures at `scale` times the size; (the thirtieth
    session) where it was of more colors, its own colors at `scale` times the size (1 to 4: `own_upper` and
    `own_lower`, red, green and blue a pixel) and the palette they were given in (`tied`, 16 words). `own_count` and
    `own_dropped` say what Replace... did with an image's colors (how many pixels had their own; whether they were
    kept to the palette's because the image was more than 4 times the size)."""
    upper: bytes
    lower: bytes
    scale: int = 1
    big_upper: Optional[bytes] = None
    big_lower: Optional[bytes] = None
    own_upper: Optional[bytes] = None
    own_lower: Optional[bytes] = None
    tied: Optional[list] = None
    own_count: int = field(default=0, compare=False)
    own_dropped: bool = field(default=False, compare=False)

    @property
    def is_big(self) -> bool:
        return self.scale > 1 and self.big_upper is not None and self.big_lower is not None

    @property
    def has_own(self) -> bool:
        """(The thirtieth session) Whether it has colors of its own, tied to a palette."""
        return self.own_upper is not None and self.own_lower is not None and self.tied is not None

    @property
    def needs_sheets(self) -> bool:
        """Whether Export names sheets for it that Mod Studio Framework draws (bigger, or of more colors)."""
        return self.is_big or self.has_own

    def numbers_at_scale(self) -> tuple:
        """Its two textures' color numbers (packed) at the size its sheets have: the bigger ones, else the game's."""
        return (self.big_upper, self.big_lower) if self.is_big else (self.upper, self.lower)

    def own_rgba(self, seen: list) -> bytes:
        """(The thirtieth session) Its own colors as the page draws them in the palette they were given in, red,
        green, blue and opacity a pixel at its sheet's size, upper rows first (`seen`: each number's opacity)."""
        upper, lower = self.numbers_at_scale()
        numbers = us.colour_numbers(bytes(upper)) + us.colour_numbers(bytes(lower))
        return oc.drawn(numbers, bytes(self.own_upper) + bytes(self.own_lower), seen)

    def sheet(self) -> Optional[us.Sheet]:
        """The sheet at the game's size, a color number a pixel."""
        return us.join_sheets([self.upper, self.lower])

    def big_sheet(self) -> Optional[us.Sheet]:
        """The bigger sheet, a color number a pixel; None where the picture is the game's size."""
        if not self.is_big:
            return None
        rows = us.colour_numbers(self.big_upper) + us.colour_numbers(self.big_lower)
        width = us.SHEET_WIDTH * self.scale
        return us.Sheet(width, len(rows) // width, rows)


def packed(numbers: bytes) -> bytes:
    """A color number a byte to 4 bits a pixel, the left pixel in a byte's low four bits."""
    low = int.from_bytes(numbers[0::2], "little")
    high = int.from_bytes(numbers[1::2], "little")
    return (low | (high << 4)).to_bytes(len(numbers) // 2, "little")


def scale_of(width: int, height: int) -> int:
    """How many times the game's size an image of a sheet is: 1, or one of `SCALES`. Raises where it is neither."""
    scale = width // us.SHEET_WIDTH if width % us.SHEET_WIDTH == 0 else 0
    if (scale != 1 and scale not in SCALES) or height % scale or not UPPER_ROWS < height // scale <= MOST_ROWS:
        raise SpriteTextureError(SIZE_BAD.format(w=width, h=height))
    return scale


def numbers_of(image, colors16: list) -> tuple:
    """
    An image's pixels as color numbers, and how many of its pixels weren't
    one of the palette's colors. An image whose colors are numbered (16 or
    fewer) keeps its numbers; in any other each pixel is the nearest of the
    palette's 15 shown colors (`colors16`: 16 bit values, the first see
    through), see through where it is more than half see through.
    """
    from PIL import Image, ImageChops
    if image.mode == "P":
        data = image.tobytes()
        if max(data) < 16:
            return data, 0
    shown = [us.rgba(value | 0x8000)[:3] for value in list(colors16)[1:16]]
    shown += [shown[-1] if shown else (0, 0, 0)] * (15 - len(shown))
    palette = Image.new("P", (1, 1))
    flat = [part for color in shown for part in color]
    palette.putpalette(flat + flat[-3:] * (256 - len(shown)))
    rgba = image.convert("RGBA")
    rgb = rgba.convert("RGB")
    nearest = rgb.quantize(palette=palette, dither=Image.Dither.NONE)
    clear = rgba.getchannel("A").point(lambda a: 255 if a < 128 else 0)
    numbers = nearest.point(lambda n: min(n, 14) + 1)
    numbers.paste(0, mask=clear)
    apart = ImageChops.difference(rgb, nearest.convert("RGB")).convert("L").point(lambda d: 255 if d else 0)
    apart.paste(0, mask=clear)
    return numbers.tobytes(), apart.histogram()[255]


def from_image(image, colors16: list) -> tuple:
    """
    A sprite's art from an image (Pillow) of its sheet, at the game's size or
    at 2 to 8 times it (`scale_of`), with how many of its pixels weren't one
    of the palette's colors. A bigger picture is also made the game's size:
    every `scale`th pixel of every `scale`th row, from the middle of each
    block. (The thirtieth session) An image that isn't numbered and whose
    drawn pixels aren't all the palette's colors, five bits a part
    (`own_colors.own_of`), keeps its own colors for that palette where it is
    1 to 4 times the game's size (`own_count` says how many pixels had their
    own; past 4 times they take the palette's colors, `own_dropped`).
    """
    width, height = image.size
    scale = scale_of(width, height)
    numbers, off = numbers_of(image, colors16)
    own, count = None, 0
    if off:                                       # (an image whose colors are numbered has none off: `numbers_of`)
        import numpy as np
        words = (list(colors16) + [0] * 16)[:16]
        own, count = oc.own_of(np.asarray(image.convert("RGBA")), numbers, words)
    if scale == 1:
        split = UPPER_ROWS * us.SHEET_WIDTH
        art = SpriteArt(packed(numbers[:split]), packed(numbers[split:]))
    else:
        split = UPPER_ROWS * scale * width
        middle = scale // 2
        small = b"".join(numbers[row * width + middle:(row + 1) * width:scale]
                         for row in range(middle, height, scale))
        small_split = UPPER_ROWS * us.SHEET_WIDTH
        art = SpriteArt(packed(small[:small_split]), packed(small[small_split:]), scale,
                        packed(numbers[:split]), packed(numbers[split:]))
    art.own_count = count
    if own is not None and scale in oc.SCALES:
        cut = UPPER_ROWS * scale * width * 3
        art.own_upper, art.own_lower = own[:cut], own[cut:]
        art.tied = (list(colors16) + [0] * 16)[:16]
    elif own is not None:
        art.own_dropped = True
    return art, off


def from_textures(upper: bytes, lower: bytes) -> SpriteArt:
    """A sprite's art from its two textures at the game's size (a classic sprite doubled, or a mod's files)."""
    return SpriteArt(bytes(upper), bytes(lower))


def padded(texture: bytes) -> bytes:
    """A texture as the mod loader's file holds one: 512 rows, the rows past its own see through."""
    return bytes(texture[:TEXTURE_BYTES]) + bytes(max(0, TEXTURE_BYTES - len(texture)))


def sheet_file(scale: int, pixels: bytes) -> bytes:
    """A bigger sheet's file as Mod Studio Framework reads one: its header, then its rows."""
    width = us.SHEET_WIDTH * scale
    height = len(pixels) // (width // 2)
    return MAGIC + bytes((1, 4)) + struct.pack("<HII", scale, width, height) + bytes(pixels)


def own_sheet_file(scale: int, pixels: bytes, own: bytes, tied: list) -> bytes:
    """(The thirtieth session) A sheet of more colors' file (`own_colors.sheet_file`) for one of a sprite's two
    textures: its color numbers (`pixels`, packed) and its own colors at `scale` times the size."""
    width = us.SHEET_WIDTH * scale
    height = len(pixels) // (width // 2)
    return oc.sheet_file(scale, width, height, bytes(us.colour_numbers(bytes(pixels))), own, tied, 4)


@dataclass
class SheetFile:
    """(The thirtieth session) A bigger sheet's file as read: its scale and its color numbers (packed); for a sheet of
    more colors, its own colors and the palette they were given in."""
    scale: int
    pixels: bytes
    own: Optional[bytes] = None
    tied: Optional[list] = None


def read_sheet(data: bytes) -> SheetFile:
    """A bigger sheet's file read, of 16 colors or (the thirtieth session) of more; raises `SpriteTextureError` saying
    why where it isn't one."""
    if oc.is_own_file(data):
        try:
            sheet = oc.read_sheet_file(data)
        except oc.OwnColorsError as exc:
            raise SpriteTextureError(str(exc)) from None
        if sheet.number_bits != 4 or sheet.width != us.SHEET_WIDTH * sheet.scale or sheet.height % sheet.scale \
                or not sheet.scale <= sheet.height <= UPPER_ROWS * sheet.scale:
            raise SpriteTextureError("its size isn't one a bigger sheet has")
        return SheetFile(sheet.scale, packed(sheet.numbers), sheet.own, sheet.tied)
    return SheetFile(*read_sheet_file(data))


def read_sheet_file(data: bytes) -> tuple:
    """(scale, pixels) of a bigger sheet's file of 16 colors; raises `SpriteTextureError` saying why where it isn't
    one."""
    if len(data) < HEADER_BYTES or data[:4] != MAGIC or data[4] != 1:
        raise SpriteTextureError("it isn't a bigger sheet as Mod Studio writes one")
    scale, width, height = struct.unpack_from("<HII", data, 6)
    if data[5] != 4 or scale not in SCALES or width != us.SHEET_WIDTH * scale or height % scale \
            or not scale <= height <= UPPER_ROWS * scale or len(data) != HEADER_BYTES + height * (width // 2):
        raise SpriteTextureError("its size isn't one a bigger sheet has")
    return scale, data[HEADER_BYTES:]


def entry_file(entry: int) -> str:
    """The mod loader's file for an entry of g2d.dat, from the mod's folder."""
    return f"{G2D_FOLDER}/tex_{entry}.bin"


def big_file(entry: int) -> str:
    """A bigger sheet's file for an entry, from the mod's folder."""
    return f"{FOLDER}/sprite_{entry}.bin"


def has_big(art: Optional[dict]) -> bool:
    """Whether any of a mod's sprites has a bigger picture or (the thirtieth session) one of more colors (the mod then
    needs Mod Studio Framework)."""
    return any(own is not None and own.needs_sheets for own in (art or {}).values())


def files(art: dict, table: dict, jobs=(), effects=(), summons=()) -> dict:
    """`{a file from the mod's folder: its bytes}` for a mod's sprites: each one's two entries at the game's size,
    and, where any is bigger, the bigger sheets and the file that names them. A sprite the table doesn't know (or
    one with other than two entries) is left out. `jobs` are the mod's jobs' figures given bigger
    (`job_looks.big_sheets`: each what the file names and its sheet's file), named in the same file after the
    game's sprites'; (the twenty ninth session) `effects` the mod's effects' bigger pictures
    (`effect_pictures.big_sheets`, the same way), named in the file's list of Effects; (the thirty fourth session)
    `summons` the mod's summons' own sheets bigger or of more colors (`effect_pictures.summon_sheets`), named in its
    list of Sprites by their entries, after the jobs'."""
    out: dict = {}
    named = []
    for number in sorted(art or {}):
        own, entry = art[number], (table or {}).get(number)
        if own is None or entry is None or len(entry.sheets) != 2:
            continue
        upper, lower = entry.sheets
        out[entry_file(upper)] = padded(own.upper)
        out[entry_file(lower)] = padded(own.lower)
        if own.has_own:
            for at, pixels, colors in zip((upper, lower), own.numbers_at_scale(), (own.own_upper, own.own_lower)):
                out[big_file(at)] = own_sheet_file(own.scale, pixels, colors, own.tied)
                named.append({"Entry": at, "File": big_file(at)})
        elif own.is_big:
            for at, pixels in ((upper, own.big_upper), (lower, own.big_lower)):
                out[big_file(at)] = sheet_file(own.scale, pixels)
                named.append({"Entry": at, "File": big_file(at)})
    for ask, data in list(jobs or ()) + list(summons or ()):
        out[ask["File"]] = bytes(data)
        named.append(dict(ask))
    effects_named = []
    for ask, data in effects or ():
        out[ask["File"]] = bytes(data)
        effects_named.append(dict(ask))
    if named or effects_named:
        lists = {"Sprites": named} if named else {}
        if effects_named:
            lists["Effects"] = effects_named
        out[FILE] = (json.dumps(lists, indent=2) + "\n").encode("utf-8")
    return out


def written_before(mod_root) -> list:
    """The files an earlier export wrote for the mod's bigger sheets (the ones its `ModStudioTextures.json` names
    inside `ModStudioTextures/`, in its list of Sprites and (the twenty ninth session) of Effects, and the file
    itself): Export takes away those it doesn't write now."""
    root = Path(mod_root)
    try:
        lists = json.loads((root / FILE).read_text(encoding="utf-8"))
        named = list(lists.get("Sprites", []) or []) + list(lists.get("Effects", []) or [])
    except (OSError, ValueError, AttributeError, TypeError):
        return []
    found = [FILE]
    for one in named:
        name = one.get("File") if isinstance(one, dict) else None
        if isinstance(name, str) and name.replace("\\", "/").startswith(FOLDER + "/") and ".." not in name:
            found.append(name.replace("\\", "/"))
    return found


def write(mod_root, art: dict, table: dict, carried=(), jobs=(), effects=(), summons=()) -> list:
    """Writes a mod's sprites' files (`files`, with its jobs' bigger figures: `jobs`, (the twenty ninth session) its
    effects' bigger pictures: `effects`, and (the thirty fourth session) its summons' own sheets for Mod Studio
    Framework: `summons`) under its folder and takes away what an earlier export wrote of them that isn't written
    now: the bigger sheets (`written_before`) and the two entries' files of any sprite of the table. A file the mod
    carries as its own (`carried`: one Mod Studio didn't read as a sprite's, kept as it is) is left alone. The files
    written, sorted."""
    root = Path(mod_root)
    made = files(art, table, jobs, effects, summons)
    kept = {str(rel).replace("\\", "/").lower() for rel in carried or ()}
    stale = list(written_before(root))
    for entry in (table or {}).values():
        if len(entry.sheets) == 2:
            stale += [entry_file(at) for at in entry.sheets]
    for rel in stale:
        if rel not in made and rel.lower() not in kept:
            try:
                (root / rel).unlink()
            except OSError:
                pass
    for rel, data in made.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    folder = root / FOLDER
    try:
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    except OSError:
        pass
    return sorted(made)


def read(mod_root, table: dict) -> tuple:
    """
    A mod's sprites read back from its folder: `({sprite number: SpriteArt},
    [what couldn't be read], [the files that are the sprites' now])`. A
    sprite is the mod's where the mod replaces both of its entries with a
    whole texture each; its bigger sheets where `ModStudioTextures.json`
    names both entries with sheets of one scale. Each texture is kept as
    its file has it (a lower texture of 512 rows stays 512 rows), so a mod
    opened and exported again has the same files byte for byte.
    """
    root = Path(mod_root)
    art, problems, taken = {}, [], []
    big: dict = {}
    for rel in written_before(root)[1:]:
        stem = Path(rel).stem
        if not (stem.startswith("sprite_") and stem[7:].isdigit()):
            continue                      # a job's own bigger sheet, or another's: not one of the game's sprites'
        try:
            big[int(stem[7:])] = (rel, read_sheet((root / rel).read_bytes()))
        except (OSError, ValueError) as exc:
            problems.append(SHEET_BAD.format(file=rel, why=exc))
    for number in sorted(table or {}):
        entry = table[number]
        if len(entry.sheets) != 2:
            continue
        paths = [root / entry_file(at) for at in entry.sheets]
        if not all(path.is_file() for path in paths):
            continue
        try:
            upper, lower = (path.read_bytes() for path in paths)
        except OSError:
            continue
        if len(upper) != TEXTURE_BYTES or not ROW_BYTES <= len(lower) <= TEXTURE_BYTES or len(lower) % ROW_BYTES:
            continue
        own = SpriteArt(upper, lower)
        taken += [entry_file(at) for at in entry.sheets]
        both = [big.get(at) for at in entry.sheets]
        if all(both):
            first, second = both[0][1], both[1][1]
            if first.scale != second.scale or first.tied != second.tied:
                problems.append(SHEET_BAD.format(file=both[0][0], why=SHEETS_APART))
            else:
                own.scale = first.scale
                if first.scale > 1:
                    own.big_upper, own.big_lower = first.pixels, second.pixels
                if first.own is not None:
                    own.own_upper, own.own_lower, own.tied = first.own, second.own, list(first.tied)
                taken += [both[0][0], both[1][0]]
        art[number] = own
    if any(rel.startswith(FOLDER + "/") for rel in taken):
        taken.append(FILE)
    return art, problems, taken


def read_jobs(mod_root) -> tuple:
    """
    What a mod's `ModStudioTextures.json` names of its jobs' own figures:
    `({(the job's name, "Man" or "Woman"): {"Upper" or "Lower": (the sheet's
    file from the mod's folder, the sheet as read: `SheetFile`)}}, [what
    couldn't be read])`. Only sheets inside `ModStudioTextures/` are read, as `read`
    reads the game's sprites'; which job each is for, and whether its two
    sheets fit that job's textures, is `job_looks.take_big`'s to say.
    """
    root = Path(mod_root)
    try:
        named = json.loads((root / FILE).read_text(encoding="utf-8")).get("Sprites", [])
    except (OSError, ValueError, AttributeError):
        return {}, []
    found, problems = {}, []
    for one in named if isinstance(named, list) else []:
        if not isinstance(one, dict) or not isinstance(one.get("Job"), str) or "Entry" in one:
            continue
        who, half, rel = one.get("Who"), one.get("Half"), one.get("File")
        if who not in ("Man", "Woman") or half not in ("Upper", "Lower") or not isinstance(rel, str):
            continue
        rel = rel.replace("\\", "/")
        if not rel.startswith(FOLDER + "/") or ".." in rel:
            continue
        try:
            sheet = read_sheet((root / rel).read_bytes())
        except (OSError, ValueError) as exc:
            problems.append(SHEET_BAD.format(file=rel, why=exc))
            continue
        found.setdefault((one["Job"], who), {})[half] = (rel, sheet)
    return found, problems


def sprite_names(table: dict, set_names: Optional[dict] = None) -> list:
    """`[(sprite number, the name the page lists it by)]`, by number: the sprite set's name where Mod Studio has one
    (`data/SpriteSetNames.txt`), with the classic sprite file's own name; else that name alone."""
    out = []
    for number in sorted(table or {}):
        entry = table[number]
        if len(entry.sheets) != 2:
            continue
        known = (set_names or {}).get(number)
        out.append((number, f"{number:03d}  {known} ({entry.name})" if known else f"{number:03d}  {entry.name}"))
    return out
