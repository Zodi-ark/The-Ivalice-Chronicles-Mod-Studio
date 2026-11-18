"""
A job's look and its art, as the New Content page's Jobs tab edits them: the
Jobs page's second part (Zodi's choices of 14 November: "Build it as shown",
whose pictures had the middle's "Its look" and the card's Look section; the
job screen art none by default, his word of 12 November). His goal since 9
November: "let's add everything to Mod Studio so users can create their new
jobs".

What a job's file gives of its look and art, as Mod Studio Framework reads it
(`helper/ModStudioEventSetup/JobFile.cs`, `JobArt.cs`, `SpriteRoom.cs`), each
file's shape measured on the test makers that made one
(`dev/research/sidequests/make_test102.py` to `make_test109.py`) and on the
framework's readers:

- **Look.Like**: the game's generic job whose look it wears (74 to 93), drawn
  in the same frames as the job it is based on (its sprites' attributes' first
  two bytes, a man's and a woman's alike; measured on the game's BATTLE.BIN:
  the Squire, Knight, Archer, Monk, Thief, Dragoon, Samurai and Ninja one kind,
  the other twelve the other; `FRAMES`). A job with a Look takes one of the 38
  pairs of sprite numbers the mods' jobs share; one that wears its own Like's
  look with nothing of its own needs none (`tidy_look`).
- **Look.Colors**: a man's and a woman's palettes, each 1 to 5 of 16 colors
  "#RRGGBB" (the first "#000000", see through), the first the player's
  team's; a palette not given keeps the look's. The game makes each color one
  of its own 15 bits (each part's top five bits, every color but the first
  shown), so a color picked is kept as the game shows it (`snapped`).
- **Look.Textures**: a man's and a woman's two files in the job's folder, its
  upper texture (512 by 512 pixels at 4 bits a pixel, the left pixel in a
  byte's low four bits: 131,072 bytes) and its lower (512 wide, 1 to 512
  rows; the game's own 464), drawn for its frames and colored by its colors.
  Written as test 103 named them (`TEXTURE_FILES`).
- **Look.Frames** (Mod Studio Framework 1.54.0, his 8th note of 14 November): the frames a man's or a woman's own
  textures are drawn for, 1 (Type 1) or 2 (Type 2), where they differ from the frames of the job it is based on
  (`written_job`); told from the textures when they are given (`classic_sprites.told_frames`, his pick "Tell it,
  modder can change") and kept in its art (`mod_jobs.JobArt.frames`). A classic sprite (.spr, or a .bmp of 256 by
  488) is doubled to the game's size (`classic_sprites.textures`, his pick "Smooth, plain if asked") and its palettes
  made the sex's colors as the game wants them (`set_classic_colors`).
- **What Export writes of the textures** (his answer of 16 November to test 124: "Mod Studio should fix it
  automatically"): the textures as held, with the lines the game would draw past a frame's pieces cleared for the
  frames they are drawn with (`cleared`, `classic_sprites.cleared_edges`), where the unpacked game's frames can be read.
- **A figure given bigger** (17 November 2026; his second point of 16 November: "New Jobs sprites should be able to
  have this as well"): an image 2 to 8 times the game's size is kept at that size (`mod_jobs.JobArt.big`) and also
  made the game's size, which is the job's Look.Textures as before (`figure_from_image`,
  `sprite_textures.from_image`). Export names the bigger sheets by the job in the mod's `ModStudioTextures.json`
  (`big_sheets`: `{"Job": name, "Who": "Man", "Half": "Upper", "File": ...}`, beside the game's unit sprites'), where
  Mod Studio Framework reads them and shows them in the game's place at the same size on the screen; they are written
  with the same lines cleared, each of the game's pixels as its block (`cleared_big`,
  `classic_sprites.cleared_bigger`). Opening the mod reads them back (`take_big`).
- **A figure of more colors** (the thirtieth session; his choices of 17 November: tied to one palette, up to 4 times,
  and Replace... keeps an image's own colors): an image that isn't numbered and whose drawn pixels aren't all the
  figure's first palette's colors, five bits a part, keeps its own colors for that palette (`mod_jobs.JobArt.own`), at
  the game's size or up to 4 times it, besides its numbers as before (`figure_from_image`). Export names a sheet of
  more colors for each of its two textures in the same file (`big_sheets`, `sprite_textures.own_sheet_file`), its
  palette the job's first as Export writes it, so Mod Studio Framework draws its own colors where the game draws the
  job in the player's team's colors; the tab still draws the figure in its palette's colors.
- **Look.Portraits**: a man's and a woman's 1 to 5 part lists (one a team's
  colors, the first the player's team's; a team past the list's end takes the
  first) at `FFTIVC/data/enhanced/ui/ffto/common/face/textureparts/`, each laid
  out as the game's faces (a sheet of 520 by 388: three eyes for blinking,
  four mouths for talking, the whole face; `FACE_PARTS`) and naming its
  texture. An image of the sheet's size is taken as a sheet; any other is one
  face, laid into every part (it doesn't blink or talk). Either way the face
  is made as test 108's were: the eyes' parts one row past where the mouths'
  begin, then Mod Studio's own seam fix.
- **Icon** and **Skillset.Icon**: the game's (74 to 93; 5 to 24) or its own
  part list (`.../icon/job/`, 60 by 60; `.../icon/job_comm/`, 96 by 96: one
  part, the whole sheet, as test 109's and other mods' are); **Pictures**: a
  man's and a woman's job screen art, each its own part list
  (`.../icon/job_visual/`, 400 by 652) or none, and a job without shows no
  picture anywhere.

A job's own art is the page's (`mod_jobs.JobArt`), as an item's own icon is:
read back from the mod's files when the mod is opened (`read_art`), written
afresh by Export (`written_job`, `art_files`) with names of the mod and the
job (`art_base`), so no two mods' or jobs' art meet in the game's folders.

Nothing here imports Qt; Pillow is imported where a picture is made.
"""
from __future__ import annotations

import copy
import io
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import classic_sprites as cs
from . import helper_json as hj
from . import mod_jobs as mj
from . import own_colors as oc
from . import sprite_textures as st
from . import unit_sprites as us

WHO = ("Man", "Woman")
#: The generic jobs drawn in the same frames, a kind each (BATTLE.BIN's sprite attributes' first two bytes, a man's
#: and a woman's alike for every generic job; `dev/test_job_looks.py` holds them to the game's file).
FRAMES = ((74, 76, 77, 78, 83, 87, 88, 89), (75, 79, 80, 81, 82, 84, 85, 86, 90, 91, 92, 93))

#: A figure's textures: the sheet's width, the upper texture's rows, the game's lower texture's, the most both hold.
SHEET_WIDTH, UPPER_ROWS, GAME_LOWER_ROWS, MOST_ROWS = 512, 512, 464, 1024
ROW_BYTES = SHEET_WIDTH // 2
#: The files of a job's own textures in its folder (test 103's names), each sex's upper texture's and lower's.
TEXTURE_FILES = {who: (f"{who.lower()}_upper.bin", f"{who.lower()}_lower.bin") for who in WHO}
#: (His answer of 16 November to test 124) What Export's log says of a figure's textures it cleared lines of (`cleared`),
#: and what the Jobs tab says when a figure is given. Words a user sees (HANDOFF's "Words to sign off" lists them).
EDGES_LOG = ("The job {job}'s {who} textures: {n} pixels the game would show as a thin line under or beside a pose are "
             "cleared{trimmed}.")
EDGES_LOG_TRIMMED = " ({m} of them also the edge of a piece in other poses, which lose them)"
EDGES_SAID = ("Export clears {n} of its pixels that the game would show as a thin line under or beside a pose (they lie "
              "just past the edge of a frame's piece on the sheet).")
EDGES_SAID_TRIMMED = " {m} of them are also the edge of a piece in other poses, which lose them."

#: A face sheet as the game's: its size, its parts in the game's order (each its name and x1, y1, x2, y2), a face's
#: cell, where in it the mouths' parts begin and how many rows past that the eyes' parts go (the game's own: one).
FACE_SIZE = (520, 388)
FACE_PARTS = (("TexturePart", (0, 0, 520, 388)), ("Eye00", (1, 1, 129, 193)), ("Eye01", (131, 1, 259, 193)),
              ("Eye02", (261, 1, 389, 193)), ("Mouth00", (1, 195, 129, 387)), ("Mouth01", (131, 195, 259, 387)),
              ("Mouth02", (261, 195, 389, 387)), ("Mouth03", (391, 195, 519, 387)), ("All", (391, 1, 519, 193)))
FACE_CELL, FACE_SPLIT, FACE_OVERLAP = (128, 192), 118, 1
#: The colors of a job's first portrait, as the game numbers its faces' (the player's team's; the teams' 8 to 12).
FIRST_TEAM = 8
#: The sizes of a job icon, a skillset icon and job screen art (the game's own and test 109's).
ICON_SIZE, COMMAND_SIZE, PICTURE_SIZE = (60, 60), (96, 96), (400, 652)

DATA = "FFTIVC/data/enhanced/"
FACE_TEXTURES = "ui/ffto/common/face/texture"
ICON_TEXTURES = "ui/ffto/icon/job/texture"
COMMAND_TEXTURES = "ui/ffto/icon/job_comm/texture"
PICTURE_TEXTURES = "ui/ffto/icon/job_visual/texture"

# Words a user sees (HANDOFF's "Words to sign off" lists them).
FIGURE_SIZE_BAD = ("A figure's texture is an image 512 pixels wide and 513 to 1,024 tall (the game's are 976), an image "
                   "2 to 8 times that size for a bigger texture, or a classic sprite (a .spr file, or a sheet of 256 by "
                   "488): this one is {w} by {h}. Export as PNG gives one to start from.")
#: (The thirtieth session) What Replace... did with a figure image's own colors (`figure_from_image`): `own` its own
#: colors kept, `(scale, upper's, lower's, the palette's 16 words)`, or None; `count` how many of its pixels had their
#: own; `dropped` whether they took the palette's colors because the image was more than 4 times the game's size.
@dataclass
class FigureOwn:
    own: Optional[tuple] = None
    count: int = 0
    dropped: bool = False


#: (17 November 2026) Why a mod's bigger sheets of a job's figure aren't the page's when the mod is opened (`take_big`).
BIG_NO_JOB = "{job} isn't a job of this mod's with a {who} figure of its own"
BIG_HALF = "{job}'s {who} figure has a bigger sheet for one of its two textures only"
BIG_SIZES = "the two bigger sheets of {job}'s {who} figure don't match its two textures at one size"
ART_UNREAD = "its art can't be read here ({problem})"


class LookError(ValueError):
    """An image that can't be made into a job's art; the message says why, in words."""


# =============================================================================
# Which look, and its frames
# =============================================================================

def generic_sprite(job: int, woman: int) -> int:
    """A generic job's sprite for a man (`woman` 0) or a woman (1), as the framework makes it
    (`SpriteRoom.GenericSprite`: the Bard and the Dancer share 130 and 131, the Mime has 132 and 133)."""
    if job in (92, 93):
        job -= 1
    return ((job + 0x26) * 2 + (0x81 if woman else 0x80)) & 0xFF


def frames_alike(like: int) -> list:
    """The game's generic jobs drawn in the same frames as `like`, in the game's order: the looks a job based on it can
    wear."""
    return next((list(kind) for kind in FRAMES if like in kind), [like])


def frames_of_job(job: int) -> int:
    """(1.54.0) The frames the game draws one of its generic jobs' sprites in: Type 1 (`FRAMES`' first kind) or Type 2."""
    return cs.TYPE1 if job in FRAMES[0] else cs.TYPE2


def frames_shown(job, art, who: str) -> int:
    """(1.54.0) The frames a man or a woman of the job is drawn in: those of its own textures where told or picked,
    else those of the job it is based on (the framework's, as before)."""
    told = art.frames.get(who) if who in art.textures else None
    return told if told in (cs.TYPE1, cs.TYPE2) else frames_of_job(job.like)


def frames_job(job, art, who: str) -> int:
    """(1.54.0) The game's job whose frames a man or a woman of the job is drawn in: the job it is based on, or where
    its own textures are drawn for the other kind, the game's job drawn for them (the framework's FramesJob)."""
    shown = frames_shown(job, art, who)
    return job.like if shown == frames_of_job(job.like) else cs.FRAMES_JOBS[shown]


def frames_reader(sprites):
    """(His answer of 16 November) What reads the game's frames of each kind (`classic_sprites.TYPE1` or `TYPE2`) for
    `cleared`, from the unpacked game's units (`unit_sprites.UnitSprites`); None without them."""
    if sprites is None:
        return None
    return lambda kind: sprites.shape(cs.SHAPES[kind]) if kind in cs.SHAPES else None


def cleared(edit, who: str, frames_of) -> tuple:
    """(His answer of 16 November to test 124: "Mod Studio should fix it automatically") A man's or a woman's own
    textures as Export writes them: `(upper, lower, Edges)`, with the lines the game would draw past a frame's pieces
    cleared for the frames they are drawn with (`frames_shown`; `classic_sprites.cleared_edges`); as held, and None,
    where those frames can't be read (`frames_of` None, or it gives none)."""
    upper, lower = edit.art.textures[who]
    frames = frames_of(frames_shown(edit.job, edit.art, who)) if frames_of is not None else None
    if not frames:
        return upper, lower, None
    return cs.cleared_edges(upper, lower, frames)


def _look(job) -> dict:
    return job.look if isinstance(job.look, dict) else {}


def look_like(job) -> int:
    """The game's job whose look the job wears: its Look's Like, else the job it is based on."""
    value = hj.get(_look(job), "Like")
    return value if mj._whole(value) and mj.FIRST_LIKE <= value <= mj.LAST_LIKE else job.like


def own_colors(job, who: str) -> Optional[list]:
    """The job's own palettes for a man or a woman (lists of 16 "#RRGGBB"), None where it keeps its look's."""
    colors = hj.get(_look(job), "Colors")
    listed = hj.get(colors, who) if isinstance(colors, dict) else None
    return [list(palette) for palette in listed] if isinstance(listed, list) and listed else None


def tidy_look(job, art) -> None:
    """The job's Look as the framework can wear it: in the same frames as the job it is based on (else its Like's look
    again), its Like and its own colors only (its own textures and portraits are the page's art, named as Export writes
    them), and no Look at all where it wears its Like's look with nothing of its own."""
    worn = look_like(job)
    if worn not in frames_alike(job.like):
        worn = job.like
    colors = {who: own for who in WHO if (own := own_colors(job, who))}
    if worn == job.like and not colors and not art.textures and not art.portraits:
        job.look = None
        return
    job.look = {"Like": worn, **({"Colors": colors} if colors else {})}


def set_look_like(job, worn: int, art) -> None:
    """Wears the look of: the game's job `worn` (one drawn in the same frames as the job it is based on)."""
    colors = {who: own for who in WHO if (own := own_colors(job, who))}
    job.look = {"Like": int(worn), **({"Colors": colors} if colors else {})}
    tidy_look(job, art)


# =============================================================================
# Colors
# =============================================================================

def game_color(value: int) -> str:
    """One of the game's 16 bit colors as "#RRGGBB", as the game shows it."""
    r, g, b = value & 31, (value >> 5) & 31, (value >> 10) & 31
    return "#%02X%02X%02X" % ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))


def snapped(rgb) -> str:
    """A color picked (red, green, blue, 0 to 255) as "#RRGGBB", as the game shows it: each part's top five bits."""
    r, g, b = (max(0, min(255, int(v))) >> 3 for v in tuple(rgb)[:3])
    return "#%02X%02X%02X" % ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))


def palette16(colors: list) -> list:
    """A palette of "#RRGGBB" colors as the game's 16 bit values: the first see through (0), every other shown (its
    top bit set, as the game sets it)."""
    out = [0]
    for text in list(colors)[1:16]:
        n = int(text[1:], 16)
        out.append(0x8000 | (((n >> 3) & 31) << 10) | (((n >> 11) & 31) << 5) | ((n >> 19) & 31))
    return out


def as_colors(palette: list) -> list:
    """One of the game's palettes (16 bit values) as 16 "#RRGGBB", the first "#000000"."""
    return ["#000000"] + [game_color(v) for v in list(palette)[1:16]]


def shown_colors(job, who: str, game: list) -> list:
    """The five palettes a man or a woman of the job wears, as "#RRGGBB" lists: its own where it gives them, else its
    look's (`game`: the look's five palettes, 16 bit values; None or a short list where the game's can't be read)."""
    own = own_colors(job, who) or []
    out = []
    for n in range(mj.MOST_PALETTES):
        if n < len(own):
            out.append(list(own[n]))
        elif game and n < len(game) and game[n]:
            out.append(as_colors(game[n]))
        else:
            out.append(None)
    return out


def palettes(job, who: str, game: list) -> list:
    """The five palettes a man or a woman of the job is drawn in, as the game's 16 bit values (None where neither its
    own nor its look's is known)."""
    own = own_colors(job, who) or []
    out = []
    for n in range(mj.MOST_PALETTES):
        if n < len(own):
            out.append(palette16(own[n]))
        elif game and n < len(game) and game[n]:
            out.append(list(game[n]))
        else:
            out.append(None)
    return out


def _set_own(job, who: str, wanted: list, game: list, art) -> None:
    """A sex's five palettes as wanted ("#RRGGBB" lists): its own as far as the last that isn't its look's, none where
    every one is its look's."""
    look = [as_colors(p) if p else None for p in (list(game or []) + [None] * mj.MOST_PALETTES)[:mj.MOST_PALETTES]]
    last = max((n for n in range(mj.MOST_PALETTES) if wanted[n] is not None and wanted[n] != look[n]), default=-1)
    colors = {w: own for w in WHO if w != who and (own := own_colors(job, w))}
    if last >= 0:
        colors[who] = [list(wanted[n] or look[n] or ["#000000"] * mj.PALETTE_COLORS) for n in range(last + 1)]
    job.look = {"Like": look_like(job), **({"Colors": {w: colors[w] for w in WHO if w in colors}} if colors else {})}
    tidy_look(job, art)


def set_color(job, who: str, palette: int, index: int, color: str, game: list, art) -> None:
    """Color `index` (1 to 15: the first is see through) of the man's or the woman's palette `palette` (0 to 4) made
    `color` ("#RRGGBB")."""
    if not 1 <= index < mj.PALETTE_COLORS or not 0 <= palette < mj.MOST_PALETTES:
        return
    wanted = shown_colors(job, who, game)
    if wanted[palette] is None:
        return
    wanted[palette] = list(wanted[palette])
    wanted[palette][index] = snapped((int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)))
    _set_own(job, who, wanted, game, art)


def use_look_palette(job, who: str, palette: int, game: list, art) -> None:
    """The man's or the woman's palette `palette` its look's again."""
    wanted = shown_colors(job, who, game)
    if game and palette < len(game) and game[palette]:
        wanted[palette] = as_colors(game[palette])
    _set_own(job, who, wanted, game, art)


def set_classic_colors(job, who: str, colors: list, art) -> None:
    """(1.54.0) A man's or a woman's five palettes made those of a classic sprite (`classic_sprites.team_colors`: as the
    game wants them)."""
    own = {w: c for w in WHO if w != who and (c := own_colors(job, w))}
    own[who] = [list(p) for p in colors[:mj.MOST_PALETTES]]
    job.look = {"Like": look_like(job), "Colors": {w: own[w] for w in WHO if w in own}}
    tidy_look(job, art)


def use_look_figure(job, who: str, art) -> None:
    """(1.54.0) A man's or a woman's figure its look's again: its own textures, the frames they were drawn for, the
    classic sprite they were made from, its bigger picture and its own colors put aside (they were made for its own
    textures)."""
    for kept in (art.textures, art.frames, art.classic, art.big, art.own):
        kept.pop(who, None)
    own = {w: c for w in WHO if w != who and (c := own_colors(job, w))}
    job.look = {"Like": look_like(job), **({"Colors": own} if own else {})}
    tidy_look(job, art)


def textures_frames(textures, kinds) -> Optional[int]:
    """(1.54.0) The frames a figure's own two textures (the game's size) are drawn for, told from them halved
    (`classic_sprites.told_frames`); None where they can't be told."""
    sheet = sheet_of(textures)
    if sheet is None:
        return None
    return cs.told_frames(cs.halved(bytes(sheet.pixels), sheet.width), kinds)


def palette_is_own(job, who: str, palette: int, game: list) -> bool:
    """Whether the man's or the woman's palette `palette` is its own (not its look's)."""
    own = own_colors(job, who) or []
    if palette >= len(own):
        return False
    return not (game and palette < len(game) and game[palette] and own[palette] == as_colors(game[palette]))


# =============================================================================
# A figure's textures
# =============================================================================

def sheet_of(textures) -> Optional[us.Sheet]:
    """A figure's two textures (upper, lower) as one sheet, a color number a pixel."""
    return us.join_sheets(list(textures))


def _pack(numbers: bytes) -> bytes:
    """A color number a byte to 4 bits a pixel, the left pixel in a byte's low four bits."""
    return bytes(a | (b << 4) for a, b in zip(numbers[0::2], numbers[1::2]))


def _rgb(value: int) -> tuple:
    return us.rgba(value | 0x8000)[:3]


def textures_from_image(image, colors16: list) -> tuple:
    """
    A figure's two textures from an image (Pillow) of its sheet: 512 pixels
    wide and 513 to 1,024 tall (the game's 976), its upper texture the first
    512 rows and its lower the rest. An image whose colors are numbered (a PNG
    of 16 colors or fewer, as Export as PNG writes one) keeps its numbers; in
    any other each pixel is the nearest of the palette's colors (`colors16`,
    16 bit values: the palette it was exported in), see through where it is
    more than half see through. (upper, lower, how many pixels weren't one of
    the palette's colors.)
    """
    width, height = image.size
    if width != SHEET_WIDTH or not UPPER_ROWS < height <= MOST_ROWS:
        raise LookError(FIGURE_SIZE_BAD.format(w=width, h=height))
    numbers, off = None, 0
    if image.mode == "P":
        data = image.tobytes()
        if max(data) < mj.PALETTE_COLORS:
            numbers = data
    if numbers is None:
        shown = [(k, _rgb(v)) for k, v in enumerate(list(colors16)[:mj.PALETTE_COLORS]) if k > 0]
        rgba = image.convert("RGBA").tobytes()
        made = bytearray(width * height)
        nearest: dict = {}
        for n in range(width * height):
            pixel = rgba[4 * n:4 * n + 4]
            found = nearest.get(pixel)
            if found is None:
                if pixel[3] < 128:
                    found = (0, False)
                else:
                    r, g, b = pixel[0], pixel[1], pixel[2]
                    k, (cr, cg, cb) = min(shown, key=lambda kc: (kc[1][0] - r) ** 2 + (kc[1][1] - g) ** 2
                                          + (kc[1][2] - b) ** 2)
                    found = (k, (cr, cg, cb) != (r, g, b))
                nearest[pixel] = found
            made[n] = found[0]
            off += found[1]
        numbers = bytes(made)
    packed = _pack(numbers)
    split = UPPER_ROWS * ROW_BYTES
    return packed[:split], packed[split:], off


def figure_from_image(image, colors16: list) -> tuple:
    """
    (17 November 2026) A figure from an image (Pillow) of its sheet at the
    game's size or at 2 to 8 times it: `(upper, lower, how many pixels
    weren't one of the palette's colors, bigger, own)`. At the game's size it
    is `textures_from_image` and `bigger` is None. A bigger image is kept at
    its size, `bigger` its `(scale, upper, lower)`, and is also made the
    game's size (`sprite_textures.from_image`: every `scale`th pixel of every
    `scale`th row, from the middle of each block), which is what the figure's
    two textures are. Its colors are taken the same way: numbered colors
    kept, any other the nearest of the palette's. (The thirtieth session)
    `own` says what became of its own colors (`FigureOwn`): kept for the
    palette where the image isn't numbered, its drawn pixels aren't all the
    palette's colors (five bits a part) and it is up to 4 times the size.
    """
    width, height = image.size
    if width == SHEET_WIDTH:
        upper, lower, off = textures_from_image(image, colors16)
        return upper, lower, off, None, _own_at_size(image, upper, lower, colors16, off)
    try:
        made, off = st.from_image(image, colors16)
    except st.SpriteTextureError:
        raise LookError(FIGURE_SIZE_BAD.format(w=width, h=height)) from None
    kept = FigureOwn(count=made.own_count, dropped=made.own_dropped)
    if made.has_own:
        kept.own = (made.scale, made.own_upper, made.own_lower, list(made.tied))
    return made.upper, made.lower, off, (made.scale, made.big_upper, made.big_lower), kept


def _own_at_size(image, upper: bytes, lower: bytes, colors16: list, off: int) -> FigureOwn:
    """(The thirtieth session) An image of the game's size's own colors for the palette it was given in
    (`own_colors.own_of`), where it isn't numbered and some pixel isn't the palette's colors."""
    if not off:                                   # (an image whose colors are numbered has none off)
        return FigureOwn()
    import numpy as np
    words = (list(colors16) + [0] * 16)[:16]
    numbers = us.colour_numbers(bytes(upper)) + us.colour_numbers(bytes(lower))
    rgba = np.asarray(image.convert("RGBA"))
    own, count = oc.own_of(rgba, bytes(numbers[:rgba.shape[0] * rgba.shape[1]]), words)
    if own is None:
        return FigureOwn()
    cut = UPPER_ROWS * SHEET_WIDTH * 3
    return FigureOwn((1, own[:cut], own[cut:], words), count)


def big_sheet(art, who: str) -> Optional[us.Sheet]:
    """A figure's bigger picture as one sheet, a color number a pixel; None where it has none."""
    if who not in art.big or who not in art.textures:
        return None
    scale, upper, lower = art.big[who]
    rows = us.colour_numbers(bytes(upper)) + us.colour_numbers(bytes(lower))
    width = SHEET_WIDTH * scale
    return us.Sheet(width, len(rows) // width, rows)


def cleared_big(edit, who: str, frames_of) -> tuple:
    """(17 November 2026) A man's or a woman's bigger picture as Export writes it: `(scale, upper, lower)`, with the
    lines the game would draw past a frame's pieces cleared as `cleared` clears them at the game's size, each of the
    game's pixels as its block (`classic_sprites.cleared_bigger`); as held where the game's frames can't be read."""
    scale, upper, lower = edit.art.big[who]
    frames = frames_of(frames_shown(edit.job, edit.art, who)) if frames_of is not None else None
    if not frames:
        return scale, upper, lower
    return (scale,) + cs.cleared_bigger(upper, lower, scale, frames)[:2]


def big_file(folder: str, who: str, half: str) -> str:
    """A job's figure's bigger sheet's file, from the mod's folder: beside the game's unit sprites' sheets, named of
    the job's folder."""
    return f"{st.FOLDER}/job_{folder}_{who.lower()}_{half.lower()}.bin"


def has_own(art, who: str) -> bool:
    """(The thirtieth session) Whether a man's or a woman's figure has colors of its own (kept at the size its bigger
    sheet has, or the game's where it has none, and only with its own textures: Replace..., a classic sprite, Use its
    look's and `take_big` keep them together)."""
    return who in art.own


def own_png(art, who: str) -> bytes:
    """(The thirtieth session) A man's or a woman's figure of more colors as a PNG of its own colors at its size (its
    bigger sheet's, or the game's), the first number see through: what Export as PNG writes and Replace... reads back
    the same."""
    from PIL import Image
    scale, own_upper, own_lower, _tied = art.own[who]
    sheet = big_sheet(art, who) if scale > 1 else sheet_of(art.textures[who])
    rgba = oc.drawn(bytes(sheet.pixels), bytes(own_upper) + bytes(own_lower), [0] + [255] * 15)
    out = io.BytesIO()
    Image.frombytes("RGBA", (sheet.width, sheet.height), rgba).save(out, "PNG")
    return out.getvalue()


def tied_colors(edit, who: str) -> list:
    """(The thirtieth session) The palette a figure's own colors are drawn in by Mod Studio Framework: its first (the
    player's team's) as Export writes the job, its own colors where it gives them, else the look's as they were when
    the colors were given."""
    own = own_colors(edit.job, who)
    return palette16(own[0]) if own else list(edit.art.own[who][3])


def big_sheets(edits: dict, frames_of=None) -> list:
    """(17 November 2026) What the mod's `ModStudioTextures.json` names of its jobs' figures given bigger, as Mod Studio
    Framework reads it (`helper/ModStudioEventSetup/BigTextures.cs`): `[({"Job": the job's name, "Who": "Man" or
    "Woman", "Half": "Upper" or "Lower", "File": its path from the mod's folder}, the sheet's file)]`, a man's before a
    woman's and an upper before a lower, in the jobs' order. `sprite_textures.files` writes them into the one file with
    the game's unit sprites'. (The thirtieth session) A figure of more colors is named the same way, each sheet one of
    more colors (`sprite_textures.own_sheet_file`) of its numbers as Export writes them (cleared) and its own colors,
    in its first palette (`tied_colors`)."""
    out = []
    for edit in (edits or {}).values():
        for who in WHO:
            if has_own(edit.art, who):
                if who in edit.art.big:
                    scale, upper, lower = cleared_big(edit, who, frames_of)
                else:
                    scale, (upper, lower) = 1, cleared(edit, who, frames_of)[:2]
                _scale, own_upper, own_lower, _tied = edit.art.own[who]
                tied = tied_colors(edit, who)
                for half, pixels, own in (("Upper", upper, own_upper), ("Lower", lower, own_lower)):
                    rel = big_file(edit.folder, who, half)
                    out.append(({"Job": edit.job.name, "Who": who, "Half": half, "File": rel},
                                st.own_sheet_file(scale, pixels, own, tied)))
                continue
            if who not in edit.art.big or who not in edit.art.textures:
                continue
            scale, upper, lower = cleared_big(edit, who, frames_of)
            for half, pixels in (("Upper", upper), ("Lower", lower)):
                rel = big_file(edit.folder, who, half)
                out.append(({"Job": edit.job.name, "Who": who, "Half": half, "File": rel}, st.sheet_file(scale, pixels)))
    return out


def has_big(edits: Optional[dict]) -> bool:
    """Whether any of the mod's jobs has a figure given bigger or (the thirtieth session) of more colors (the mod's
    `ModStudioTextures.json` is then written)."""
    return any((who in edit.art.big and who in edit.art.textures) or has_own(edit.art, who)
               for edit in (edits or {}).values() for who in WHO)


def take_big(mod_root, edits: dict) -> tuple:
    """
    (17 November 2026) The jobs' bigger figures read back from the mod's
    `ModStudioTextures.json` (`sprite_textures.read_jobs`) into the jobs'
    art: `(how many figures, [what couldn't be taken], [the files that are
    the jobs' now])`. A figure is taken where the file names both of its
    textures for a job of the mod's that has that figure of its own, with
    sheets of one scale that are the size of its two textures (the upper 512
    of the game's rows, the lower as many as its lower texture's file has).
    Anything else is said and left out.
    """
    found, problems = st.read_jobs(mod_root)
    by_name = {edit.job.name: edit for edit in (edits or {}).values()}
    count, taken = 0, []
    for (name, who), halves in found.items():
        edit = by_name.get(name)
        whose = who.lower() + "'s"
        if edit is None or who not in edit.art.textures:
            problems.append(BIG_NO_JOB.format(job=name, who=whose))
            continue
        if set(halves) != {"Upper", "Lower"}:
            problems.append(BIG_HALF.format(job=name, who=whose))
            continue
        first, second = halves["Upper"][1], halves["Lower"][1]
        scale = first.scale
        upper, lower = first.pixels, second.pixels
        game_upper, game_lower = edit.art.textures[who]
        # (Each sheet's length is its scale's: a lower sheet at another scale than the upper's fails here too.)
        if len(upper) != len(game_upper) * scale * scale or len(lower) != len(game_lower) * scale * scale \
                or (first.own is None) != (second.own is None) or first.tied != second.tied:
            problems.append(BIG_SIZES.format(job=name, who=whose))
            continue
        if scale > 1:
            edit.art.big[who] = (scale, upper, lower)
        if first.own is not None:
            edit.art.own[who] = (scale, first.own, second.own, list(first.tied))
        taken += [halves["Upper"][0], halves["Lower"][0]]
        count += 1
    return count, problems, taken


def sheet_png(sheet: us.Sheet, colors16: list) -> bytes:
    """A figure's sheet as a PNG of numbered colors (16, the first see through), in a palette's colors: what Export as
    PNG writes, and what Replace... reads back number for number."""
    from PIL import Image
    image = Image.frombytes("P", (sheet.width, sheet.height), bytes(sheet.pixels))
    flat = []
    for k in range(mj.PALETTE_COLORS):
        value = list(colors16)[k] if colors16 and k < len(colors16) else 0
        flat += list(_rgb(value)) if k else [0, 0, 0]
    image.putpalette(flat + [0] * (768 - len(flat)))
    out = io.BytesIO()
    image.save(out, "PNG", transparency=0)
    return out.getvalue()


def standing(sprites: us.UnitSprites, like: int, worn: int, woman: int, palette: Optional[list],
             sheet: Optional[us.Sheet] = None) -> Optional[us.Picture]:
    """A man or a woman of a job standing as a battle draws it waiting (`idle`'s first picture from the front), None
    where it can't be drawn here."""
    frames_of = sprites.attributes().get(generic_sprite(like, woman))
    if frames_of is None or palette is None:
        return None
    if sheet is None:
        sheet = look_sheet(sprites, worn, woman)
    shape, animations = sprites.shape(frames_of.shape), sprites.sequences(frames_of.sequence)
    if sheet is None or not shape or not animations or us.WALK_FRONT >= len(animations):
        return None
    for frame, _delay in us.frames_of(animations[us.WALK_FRONT]):
        picture = us.draw_frame(sheet, shape[frame], palette) if frame < len(shape) else None
        if picture is not None:
            return picture
    return None


def idle(sprites: us.UnitSprites, like: int, worn: int, woman: int, palette: Optional[list],
         sheet: Optional[us.Sheet] = None) -> Optional[us.Idle]:
    """A man or a woman of a job waiting on the battlefield, as the game draws it: the frames of the job it is based on
    (`like`), the sheet of the look it wears (`worn`) or its own (`sheet`), in `palette` (16 bit values). None where it
    can't be drawn here."""
    frames_of = sprites.attributes().get(generic_sprite(like, woman))
    entry = sprites.table.get(generic_sprite(worn, woman))
    if frames_of is None or palette is None:
        return None
    if sheet is None:
        sheet = sprites.sheet(entry) if entry is not None else None
    shape, animations = sprites.shape(frames_of.shape), sprites.sequences(frames_of.sequence)
    if sheet is None or not shape or not animations:
        return None
    sides = {}
    for side, which in (("front", us.WALK_FRONT), ("back", us.WALK_BACK)):
        pictures = []
        for frame, delay in us.frames_of(animations[which] if which < len(animations) else []):
            picture = us.draw_frame(sheet, shape[frame], palette) if frame < len(shape) else None
            if picture is not None:
                pictures.append((picture, max(1, delay)))
        sides[side] = pictures
    if not sides["front"] and not sides["back"]:
        return None
    return us.Idle(sides["front"], sides["back"], frames_of.flying, frames_of.height)


def look_sheet(sprites: us.UnitSprites, worn: int, woman: int) -> Optional[us.Sheet]:
    """The sheet of the game's look a man or a woman wears (g2d.dat's two textures), None where it can't be read."""
    entry = sprites.table.get(generic_sprite(worn, woman))
    return sprites.sheet(entry) if entry is not None else None


def look_palettes(sprites: us.UnitSprites, worn: int, woman: int) -> list:
    """The five palettes of the game's look a man or a woman wears (16 bit values; None where they can't be read)."""
    number = generic_sprite(worn, woman)
    out = []
    for n in range(mj.MOST_PALETTES):
        try:
            out.append(sprites.palette(number, n))
        except Exception:                                             # noqa: BLE001
            out.append(None)
    return out


# =============================================================================
# Pictures: portraits, icons, job screen art
# =============================================================================

def fitted(image, size: tuple):
    """An image (Pillow) fitted into `size`, its shape kept, in the middle, see through round it."""
    from PIL import Image
    image = image.convert("RGBA")
    if image.size == tuple(size):
        return image
    scale = min(size[0] / image.width, size[1] / image.height)
    shrunk = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.LANCZOS)
    out = Image.new("RGBA", tuple(size), (0, 0, 0, 0))
    out.paste(shrunk, ((size[0] - shrunk.width) // 2, (size[1] - shrunk.height) // 2))
    return out


def png(image) -> bytes:
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def face_sheet(image):
    """A face sheet (Pillow, RGBA, 520 by 388) from an image: one of the sheet's size taken as a sheet laid out as the
    game's, any other a face fitted into a face's cell (128 by 192) and laid into every part (it doesn't blink or
    talk); the eyes' parts one row past where the mouths' begin; then Mod Studio's seam fix (the Portrait Seam
    Fixer's, as the Textures page runs it over a face it writes)."""
    from PIL import Image
    from . import texture_data as td
    image = image.convert("RGBA")
    if image.size == FACE_SIZE:
        sheet = image
    else:
        face = fitted(image, FACE_CELL)
        sheet = Image.new("RGBA", FACE_SIZE, (0, 0, 0, 0))
        rects = dict(FACE_PARTS)
        width, height = FACE_CELL
        upper = face.crop((0, 0, width, FACE_SPLIT + FACE_OVERLAP))
        lower = face.crop((0, FACE_SPLIT, width, height))
        for n in range(3):
            sheet.paste(upper, rects[f"Eye0{n}"][:2])
        for n in range(4):
            x, y = rects[f"Mouth0{n}"][:2]
            sheet.paste(lower, (x, y + FACE_SPLIT))
        sheet.paste(face, rects["All"][:2])
    fixed, _promoted = td.apply_seam_fix(sheet)
    return fixed


def face_of(sheet, parts=FACE_PARTS):
    """The whole face of a face sheet (Pillow): its part "All", as the game shows a portrait."""
    rect = dict((name, tuple(r)) for name, r in parts).get("All", FACE_PARTS[-1][1])
    return sheet.crop(rect)


def portrait_from(image) -> tuple:
    """A portrait from an image (`face_sheet`): (its sheet as a PNG, its parts)."""
    return png(face_sheet(image)), FACE_PARTS


# =============================================================================
# Names, and the files Export writes
# =============================================================================

def _slug(text: str) -> str:
    kept = "".join(ch.lower() if ch.isascii() and ch.isalnum() else "_" for ch in text)
    return "_".join(part for part in kept.split("_") if part)


def art_base(mod_id: str, folder: str) -> str:
    """The start of the names of a job's own art's files: its mod's and its folder's letters and digits, then a number
    made of the whole of both (two mods or folders whose names differ only past what is kept, or in what a part list's
    name can't hold): at most 44 characters, so every name is within the framework's 64."""
    whole = f"{mod_id}/{folder}".lower().encode("utf-8")
    return f"{_slug(mod_id)[:20] or 'mod'}_{_slug(folder)[:14] or 'job'}_{zlib.crc32(whole) & 0xFFFFFFFF:08x}"


def portrait_name(base: str, who: str, n: int) -> str:
    return f"{base}_face_{'m' if who == 'Man' else 'f'}_{FIRST_TEAM + n:02d}_uitx"


def icon_name(base: str) -> str:
    return f"{base}_j_uitx"


def command_name(base: str) -> str:
    return f"{base}_jc_uitx"


def picture_name(base: str, who: str) -> str:
    return f"{base}_jv_{'m' if who == 'Man' else 'f'}_uitx"


def written_job(edit, mod_id: str):
    """The job as Export writes it (a copy): its Look as the framework can wear it, with its own textures and portraits
    named, and its own icon, skillset icon and pictures named, of the mod and the job."""
    job = copy.deepcopy(edit.job)
    art, base = edit.art, art_base(mod_id, edit.folder)
    tidy_look(job, art)
    if job.look is not None:
        look = dict(job.look)
        if art.textures:
            look["Textures"] = {who: list(TEXTURE_FILES[who]) for who in WHO if who in art.textures}
            # (1.54.0) The frames its own textures are drawn for, where they aren't the job's it is based on.
            frames = {who: frames_shown(job, art, who) for who in WHO if who in art.textures
                      and frames_shown(job, art, who) != frames_of_job(job.like)}
            if frames:
                look["Frames"] = frames
        if art.portraits:
            look["Portraits"] = {who: [portrait_name(base, who, n) for n in range(len(art.portraits[who]))]
                                 for who in WHO if art.portraits.get(who)}
        job.look = look
    if art.icon:
        job.icon = icon_name(base)
    elif isinstance(job.icon, str):
        job.icon = None
    if art.command:
        job.skillset_icon = command_name(base)
    elif isinstance(job.skillset_icon, str):
        job.skillset_icon = None
    job.pictures = {who: picture_name(base, who) for who in WHO if art.pictures.get(who)} or None
    return job


def _art_items(edit, mod_id: str, frames_of=None) -> list:
    """Each file of a job's own art: (its path from the mod's folder, what it is, its data and its parts); its own
    textures as Export writes them where `frames_of` reads the game's frames (`cleared`)."""
    art, base = edit.art, art_base(mod_id, edit.folder)
    out = []
    for who in WHO:
        if who in art.textures:
            for name, data in zip(TEXTURE_FILES[who], cleared(edit, who, frames_of)[:2]):
                out.append((f"{mj.FOLDER}/{edit.folder}/{name}", "texture", data, None))
        for n, (picture, parts) in enumerate(art.portraits.get(who, [])):
            out.append((portrait_name(base, who, n), "face", picture, parts))
        if art.pictures.get(who):
            out.append((picture_name(base, who), "picture", art.pictures[who], None))
    if art.icon:
        out.append((icon_name(base), "icon", art.icon, None))
    if art.command:
        out.append((command_name(base), "command", art.command, None))
    return out


_FOLDERS = {"face": (FACE_TEXTURES, mj.PORTRAITS_FOLDER), "icon": (ICON_TEXTURES, mj.ICON_FOLDER),
            "command": (COMMAND_TEXTURES, mj.COMMAND_FOLDER), "picture": (PICTURE_TEXTURES, mj.PICTURE_FOLDER)}


def art_paths(edit, mod_id: str) -> dict:
    """The paths of a job's own art's files from the mod's folder, each with its size where it is a texture of its folder
    (else `mod_jobs.ANY_SIZE`): what the page checks a job against before its files are written."""
    out = {}
    for name, kind, data, _parts in _art_items(edit, mod_id):
        if kind == "texture":
            out[name] = len(data)
            continue
        textures, part_lists = _FOLDERS[kind]
        out[f"{DATA}{textures}/{name}.tex"] = mj.ANY_SIZE
        out[f"{part_lists}/{name}.utexpt"] = mj.ANY_SIZE
    return out


def art_files(edit, mod_id: str, frames_of=None) -> dict:
    """The files of a job's own art, by their paths from the mod's folder: its textures in its folder (with the lines
    the game would draw past a frame's pieces cleared where `frames_of` reads the game's frames: `cleared`), and each
    portrait's, icon's and picture's texture (Mod Studio's own writer) and part list naming it at the game's path (a
    portrait's its parts, the others one part, the whole sheet)."""
    from PIL import Image
    from . import texture_data as td
    from . import uib
    out = {}
    for name, kind, data, parts in _art_items(edit, mod_id, frames_of):
        if kind == "texture":
            out[name] = bytes(data)
            continue
        textures, part_lists = _FOLDERS[kind]
        image = Image.open(io.BytesIO(data)).convert("RGBA")
        texture = f"{textures}/{name}.tex"
        out[f"{DATA}{texture}"] = td.rgba_tex(image)
        out[f"{part_lists}/{name}.utexpt"] = uib.part_list_file(
            texture, [(n, tuple(r)) for n, r in parts] if parts else [("TexturePart", (0, 0) + image.size)])
    return out


# =============================================================================
# A job's own art, read back from its mod
# =============================================================================

def _named(job, folder: str) -> dict:
    """What a job's file names of its own art: `{"textures": {who: [two paths]}, "portraits": {who: [part lists]},
    "icon": part list, "command": part list, "pictures": {who: part list}}`, each path from the mod's folder."""
    look = _look(job)
    out = {"textures": {}, "portraits": {}, "icon": None, "command": None, "pictures": {}}
    for who in WHO:
        textures = hj.get(hj.get(look, "Textures") or {}, who)
        if isinstance(textures, list) and len(textures) == 2 and all(isinstance(t, str) for t in textures):
            out["textures"][who] = [f"{mj.FOLDER}/{folder}/{t}" for t in textures]
        portraits = hj.get(hj.get(look, "Portraits") or {}, who)
        if isinstance(portraits, list) and portraits:
            out["portraits"][who] = [f"{mj.PORTRAITS_FOLDER}/{p}.utexpt" for p in portraits if isinstance(p, str)]
        picture = hj.get(job.pictures or {}, who) if isinstance(job.pictures, dict) else None
        if isinstance(picture, str):
            out["pictures"][who] = f"{mj.PICTURE_FOLDER}/{picture}.utexpt"
    if isinstance(job.icon, str):
        out["icon"] = f"{mj.ICON_FOLDER}/{job.icon}.utexpt"
    if isinstance(job.skillset_icon, str):
        out["command"] = f"{mj.COMMAND_FOLDER}/{job.skillset_icon}.utexpt"
    return out


def _part_list_texture(mod_root: Path, part_list: str) -> tuple:
    """A part list of the mod's (by its path from the mod's folder): (its texture's path from the mod's folder, its
    parts)."""
    from . import uib
    read = uib.read_part_list((mod_root / part_list).read_bytes())
    return f"{DATA}{read.texture_path}", tuple((p.name, tuple(p.rect)) for p in read.parts)


def files_named(mod_root, job, folder: str) -> list:
    """Every file of the mod a job's file names of its own art, by its path from the mod's folder: its textures in its
    folder, its part lists, and the textures those name (where they can be read)."""
    root = Path(mod_root)
    named = _named(job, folder)
    out = [p for who in WHO for p in named["textures"].get(who, [])]
    lists = [p for who in WHO for p in named["portraits"].get(who, [])]
    lists += [named["pictures"][who] for who in WHO if who in named["pictures"]]
    lists += [p for p in (named["icon"], named["command"]) if p]
    for part_list in lists:
        out.append(part_list)
        try:
            out.append(_part_list_texture(root, part_list)[0])
        except Exception:                                             # noqa: BLE001
            pass
    return out


def read_art(mod_root, folder: str, job) -> tuple:
    """
    A job's own art read back from its mod's files (what its file's Look's
    Textures and Portraits, its Icon, its Skillset's Icon and its Pictures
    name of its own), and the job without those names (the page names them
    again as Export writes them): (art, job, problems). Where a file can't be
    read here the job is left as it is, and the problem said: the page then
    carries it through as it is.
    """
    from . import texture_data as td
    root = Path(mod_root)
    named = _named(job, folder)
    art = mj.JobArt()
    try:
        for who in WHO:
            if who in named["textures"]:
                art.textures[who] = tuple((root / p).read_bytes() for p in named["textures"][who])
                # (1.54.0) The frames they are drawn for, where its file says.
                kind = hj.get(hj.get(_look(job), "Frames") or {}, who)
                if mj._whole(kind) and kind in (cs.TYPE1, cs.TYPE2):
                    art.frames[who] = kind
            faces = []
            for part_list in named["portraits"].get(who, []):
                texture, parts = _part_list_texture(root, part_list)
                faces.append((png(td.decode_tex_in_process(root / texture, None).convert("RGBA")), parts))
            if faces:
                art.portraits[who] = faces
            if who in named["pictures"]:
                texture, _parts = _part_list_texture(root, named["pictures"][who])
                art.pictures[who] = png(td.decode_tex_in_process(root / texture, None).convert("RGBA"))
        for key in ("icon", "command"):
            if named[key]:
                texture, _parts = _part_list_texture(root, named[key])
                setattr(art, key, png(td.decode_tex_in_process(root / texture, None).convert("RGBA")))
    except Exception as exc:                                          # noqa: BLE001
        return mj.JobArt(), job, [ART_UNREAD.format(problem=exc)]
    job = copy.deepcopy(job)
    if isinstance(job.icon, str):
        job.icon = None
    if isinstance(job.skillset_icon, str):
        job.skillset_icon = None
    job.pictures = None
    tidy_look(job, art)
    return art, job, []


# =============================================================================
# The game's own art, as the middle shows it
# =============================================================================

def game_icon_path(number: int) -> str:
    """A job icon of the game's (a Job row's TexturePartsIndex), by its texture's path in the unpacked game."""
    return f"{ICON_TEXTURES}/j_{number:03d}_uitx.tex"


def game_command_path(number: int) -> str:
    """A skillset icon of the game's (a JobCommand row's IconId), by its texture's path in the unpacked game."""
    return f"{COMMAND_TEXTURES}/jc_{number:03d}_uitx.tex"


def game_face_path(worn: int, woman: int) -> str:
    """The player's team's face of the game's look a man or a woman wears, by its texture's path in the unpacked game
    (a generic's face is numbered as its sprite)."""
    return f"{FACE_TEXTURES}/wldface_{generic_sprite(worn, woman):03d}_{FIRST_TEAM:02d}_uitx.tex"
