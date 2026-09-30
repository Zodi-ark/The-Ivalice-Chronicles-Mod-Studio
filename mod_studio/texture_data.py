"""
Browsing, previewing, and staging texture replacements for the unpacked
game's .tga/.tex files.

Two texture formats live side by side in an unpacked game folder:
  - .tga - a standard, directly-viewable/editable image format. No
    conversion needed either direction.
  - .tex - a proprietary Luminous-engine format. FF16Tools.CLI converts it
    to/from .dds (tex-conv/img-conv) - there's no way to view or produce a
    .tex file without going through that conversion (see ff16tools.py).

Face portrait textures (ui/ffto/common/face/texture/) need one more step:
FF16Tools' BC7 encoder leaves fully-transparent pixels black instead of
inheriting a neighboring colour, which shows up in-game as a visible black
seam around the portrait. apply_seam_fix() is the Portrait Seam Fixer's own
algorithm (`fix_portrait_seam.py`'s `_fix_array`, numpy and scipy), applied
automatically to any replacement staged for a face texture path - no
separate script for the user to run.
"""

from __future__ import annotations

import hashlib
import shutil
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

TEXTURE_EXTENSIONS = (".tga", ".tex")
FACE_TEXTURE_PATH_FRAGMENT = "ui/ffto/common/face/texture/"
# What a replacement image can be - matches FF16Tools img-conv's own
# accepted input formats (dds is recommended there for mip support; the
# rest get exported as R8G8B8A8_UNORM internally).
REPLACEMENT_IMAGE_EXTENSIONS = (".dds", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tga", ".webp")

#: What each kind of game texture may be replaced WITH.
#:
#: The two are not interchangeable and the game does not treat them alike.
#: A `.tga` slot is raw and is swapped for another `.tga`; a `.tex` is
#: re-encoded through FF16Tools, which takes `.png` or `.dds`. Offering
#: every readable image format for both let somebody pick a `.png` for a
#: `.tga` slot, which produces a mod that builds and a texture that does
#: not appear.
REPLACEMENT_EXTENSIONS_BY_TARGET = {
    # A `.tga` slot is raw. It is swapped for another `.tga` and nothing
    # else re-encodes into one.
    ".tga": (".tga",),
    # A `.tex` is re-encoded by FF16Tools, so it accepts everything that
    # tool's own `img-conv` accepts - quoted from its help text: "Converts
    # image files to .tex. Supported: .dds (recommended), .png, .jpg, .gif,
    # .bmp, .tga, .webp".
    #
    # This listed only `.png` and `.dds` at first, which was a guess dressed
    # as a rule: it refused six formats the converter handles, and `.dds`
    # being the recommended one is not the same as the others being
    # unsupported. Taken from the tool that does the work, not from what
    # seemed likely.
    ".tex": (".dds", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tga",
             ".webp"),
}


def allowed_replacements(relative_path) -> tuple:
    """
    The extensions this target accepts, or everything readable if it is
    neither kind.

    The fallback is deliberate rather than defensive: the tree is built from
    whatever the unpacked game holds, and refusing to offer a replacement
    for a file type nobody has catalogued yet would be worse than offering
    too much.
    """
    suffix = str(relative_path).lower()
    for target, allowed in REPLACEMENT_EXTENSIONS_BY_TARGET.items():
        if suffix.endswith(target):
            return allowed
    return REPLACEMENT_IMAGE_EXTENSIONS


def is_face_texture(relative_path: str) -> bool:
    return FACE_TEXTURE_PATH_FRAGMENT in relative_path.replace("\\", "/").lower()


# =============================================================================
# Item icon textures - the "art" (equip_item) and "sprite" (equip_item_s)
# icons shown for a given ItemData id. Confirmed directly against Zodi's own
# real unpacked game folder listing: both ui/ffto/icon/equip_item/texture/
# and ui/ffto/icon/equip_item_s/texture/ contain exactly one ei_<id>_uitx.tex
# / ei_s_<id>_uitx.tex per id, zero-padded to 3 digits, ids 0-260 with no
# gaps on either side - i.e. one icon pair per ItemData row, 1:1 with
# constants.MAX_ITEM_ID (260). Lets the Items tab offer these two textures
# as an inline quality-of-life shortcut without the user needing to hunt
# for the matching file in the main Textures tab's full game-wide browser.
# =============================================================================

ITEM_ART_TEXTURE_DIR = "ui/ffto/icon/equip_item/texture"
ITEM_SPRITE_TEXTURE_DIR = "ui/ffto/icon/equip_item_s/texture"


def item_art_texture_path(item_id: int) -> str:
    """The item's larger 'art' icon (e.g. shown in menus/shops) - ei_NNN_uitx.tex."""
    return f"{ITEM_ART_TEXTURE_DIR}/ei_{item_id:03d}_uitx.tex"


def item_sprite_texture_path(item_id: int) -> str:
    """The item's small inventory/battle 'sprite' icon - ei_s_NNN_uitx.tex."""
    return f"{ITEM_SPRITE_TEXTURE_DIR}/ei_s_{item_id:03d}_uitx.tex"


# =============================================================================
# Ability icon textures - Abilities' own IconId (constants.ABILITY_NUMERIC_
# FIELDS) references a SHARED icon sheet, unlike items' own 1:1 art/sprite
# icons above: confirmed against Zodi's real unpacked game folder listing
# that ui/ffto/icon/ability/texture/ only contains 55 real files
# (a_000_uitx.tex through a_054_uitx.tex, no gaps), even though the IconId
# field itself is a much wider ushort (0-65535) - i.e. only ids 0-54
# currently have a real icon on disk; anything else is a valid field value
# with no matching texture (load_game_texture_preview's own not-found
# check above surfaces that honestly rather than erroring obscurely).
# Because it's shared, replacing this file affects every ability (or
# anything else) whose IconId points at it, not just whichever ability
# happens to be selected when the replacement is staged.
# =============================================================================

ABILITY_ICON_TEXTURE_DIR = "ui/ffto/icon/ability/texture"


def ability_icon_texture_path(icon_id: int) -> str:
    return f"{ABILITY_ICON_TEXTURE_DIR}/a_{icon_id:03d}_uitx.tex"


# =============================================================================
# Browsing
# =============================================================================

@dataclass
class TextureTreeNode:
    """One folder or file in the pruned texture tree."""
    name: str
    relative_path: str        # "" for the root; always forward-slashed
    is_file: bool
    children: list = field(default_factory=list)   # list[TextureTreeNode], folders only


def scan_texture_tree(root: Path) -> TextureTreeNode:
    """
    Recursively scans root for .tga/.tex files, returning a tree pruned of
    any branch that contains none. The game's full unpacked folder has
    tens of thousands of non-texture files (.sab/.pzd/.bin/.mes/etc.) that
    would make a browser unusable if shown alongside - see HANDOFF.md for
    the real counts this was tested against.
    """
    def scan_dir(path: Path, rel: str) -> Optional[TextureTreeNode]:
        children = []
        try:
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return None
        for entry in entries:
            entry_rel = f"{rel}/{entry.name}" if rel else entry.name
            if entry.is_dir():
                sub = scan_dir(entry, entry_rel)
                if sub is not None:
                    children.append(sub)
            elif entry.is_file() and entry.suffix.lower() in TEXTURE_EXTENSIONS:
                children.append(TextureTreeNode(name=entry.name, relative_path=entry_rel, is_file=True))
        if not children:
            return None
        return TextureTreeNode(name=path.name or str(path), relative_path=rel, is_file=False, children=children)

    result = scan_dir(root, "")
    return result if result is not None else TextureTreeNode(name=root.name, relative_path="", is_file=False)


def count_textures(node: TextureTreeNode) -> int:
    if node.is_file:
        return 1
    return sum(count_textures(c) for c in node.children)


# =============================================================================
# Loading / preview
# =============================================================================

def load_any_image(path: Path):
    """
    Loads any common image format (png/jpg/bmp/webp/tga/gif, or dds) as an
    RGBA `PIL.Image`. For a REPLACEMENT image the user provides, not for
    existing game .tex files - those need load_game_texture_preview below
    (tex-conv first).

    This used to return a numpy array and go through imageio for .dds.
    Neither was earning its place. Every caller immediately did
    `Image.fromarray(arr, "RGBA")` to get back to the image it started as,
    so the array was a round trip to nowhere; and Pillow decodes DDS
    directly, including BC1-BC7, so imageio was only ever forwarding to it.

    The old version also hand-rolled greyscale and RGB promotion with
    np.stack/np.concatenate. `convert("RGBA")` does exactly that, and was
    checked against the old code on greyscale, RGB, RGBA and a real BC7
    .dds - identical pixels in every case.

    Between them imageio, numpy and scipy were 96 MB of a 154 MB build.
    """
    from PIL import Image

    return Image.open(str(path)).convert("RGBA")


def save_image_as_png(img, dest_path: Path) -> None:
    """
    Saves a full-resolution RGBA image (as returned by
    load_game_texture_preview) out to a standalone .png file, for the
    Textures tab's "Export as PNG..." button - lets a user pull the
    game's current texture out to edit in an external tool (Photoshop,
    GIMP, whatever), then bring the edited version back in via Replace.
    PNG's own compression is always lossless, so this is a straight,
    quality-preserving dump of exactly the pixels shown in the "Current"
    preview - no extra downscaling or recompression happens here (that
    only ever applies to the on-screen thumbnail, never to this array).
    """
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(dest_path), "PNG")


def load_game_texture_preview(path: Path, cli_path: Optional[Path], cache_dir: Path):
    """
    Loads an EXISTING unpacked-game texture (.tga or .tex) for preview.

    .tga loads directly. A .tex is converted to a .dds and cached under
    `cache_dir`, so a texture looked at again is not converted again. The
    conversion is done here, in Python, for a .tex this module reads and
    that is small enough to be quicker that way (`tex_as_dds`); anything
    else goes to FF16Tools.CLI tex-conv, as every .tex did before. Both ways
    give the same pixels, and both leave the same kind of .dds in the cache.
    """
    if not path.exists():
        raise ValueError(f"No texture file found at {path.name} - this id/path doesn't exist in the unpacked game.")

    ext = path.suffix.lower()
    if ext == ".tga":
        return load_any_image(path)

    if ext == ".tex":
        # Keyed on which file this is, not just what it's called.
        #
        # The key used to be the bare filename, so the game's `foo.tex` and
        # a mod's replacement `foo.tex` shared one cache entry - and since
        # the current texture is converted first, the replacement preview
        # showed the game's image back at you. `.tga` never had the problem
        # because it isn't cached at all, which is exactly the shape of the
        # report: .tga fine, .tex showing the wrong picture.
        #
        # Size and mtime are in the key too, so editing a file and
        # previewing it again shows the edit rather than the old copy.
        try:
            stat = path.stat()
            fingerprint = f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}"
        except OSError:
            fingerprint = str(path)
        digest = hashlib.sha256(fingerprint.encode("utf-8", "replace")).hexdigest()[:16]
        staged = cache_dir / f"{digest}_{path.name}"
        dds_path = staged.with_suffix(".dds")
        if dds_path.exists():
            return load_any_image(dds_path)

        # Read here if it can be. Anything that cannot - a format this does
        # not handle, a texture too big to be quicker here, a damaged file -
        # goes the way every .tex went before, so what the preview shows is
        # never worse than it was.
        image = None
        try:
            dds = tex_as_dds(path.read_bytes(), IN_PROCESS_MAX_PACKED_BYTES)
            image = _image_from_dds(dds)
        except Exception:                                     # noqa: BLE001
            image = None
        if image is not None:
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                _write_whole(dds_path, dds)
                prune_preview_cache(cache_dir)
            except OSError:
                pass            # a preview that could not be cached is still a preview
            return image

        if cli_path is None:
            raise ValueError("FF16Tools.CLI.exe isn't set up (General Setup) - needed to preview .tex files.")
        cache_dir.mkdir(parents=True, exist_ok=True)
        from . import ff16tools
        shutil.copy(path, staged)
        code = ff16tools.run_tex_to_dds(cli_path, staged)
        if code != 0 or not dds_path.exists():
            raise ValueError(
                f"FF16Tools.CLI tex-conv failed converting {path.name} for preview (exit code {code})."
            )
        # Bounded AFTER writing, so the entry just made is counted and
        # the oldest go first. Nothing pruned this before, and a preview
        # of a .tex leaves TWO files behind - a copy of the .tex and its
        # .dds - so browsing the texture tree grew this folder without
        # limit. The game ships 10,011 textures; at a few megabytes a
        # pair that is tens of gigabytes for someone who scrolls
        # through looking for something.
        prune_preview_cache(cache_dir)
        return load_any_image(dds_path)


def _image_from_dds(dds: bytes):
    """A DDS held in memory as an RGBA `PIL.Image` - `load_any_image`'s read."""
    import io

    from PIL import Image

    return Image.open(io.BytesIO(dds)).convert("RGBA")


def _write_whole(path: Path, data: bytes) -> None:
    """
    Writes a file so that nobody ever reads half of it: to a name of its
    own first, then renamed into place. Both pages preview textures on
    threads of their own, so one can be reading the cache while the other
    writes the same entry.
    """
    import os
    import uuid

    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.part")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


#: How much converted-preview data to keep on disk.
#:
#: A cache, not an archive: its only job is to stop the SAME texture being
#: re-converted while someone clicks back and forth between a few of them.
#: 512MB holds hundreds of pairs, which is far more than that needs, and is
#: small enough that nobody finds it by wondering where their disk went.
PREVIEW_CACHE_BYTES = 512 * 1024 * 1024


def prune_preview_cache(cache_dir: Path,
                        limit: int = PREVIEW_CACHE_BYTES) -> list:
    """
    Deletes the least recently used entries until the cache fits `limit`.

    Returns what it removed, for the log and for checking.

    **Never raises.** This runs as a side effect of showing a picture, so a
    locked file or a folder someone deleted underneath it must cost the
    cleanup and nothing else - failing to prune is a disk that fills slowly,
    while raising here is a preview that does not appear at all.

    Least-recently-USED rather than oldest-created, by mtime touched on
    read, so the textures someone is actually working with survive a sweep
    that clears the ones they passed through once.
    """
    removed = []
    try:
        entries = [(f.stat().st_mtime, f.stat().st_size, f)
                   for f in cache_dir.iterdir() if f.is_file()]
    except OSError:
        return removed
    total = sum(size for _mtime, size, _f in entries)
    if total <= limit:
        return removed
    for _mtime, size, path in sorted(entries):
        if total <= limit:
            break
        try:
            path.unlink()
        except OSError:
            continue
        total -= size
        removed.append(path.name)
    return removed

    raise ValueError(f"Unsupported texture extension for preview: {path.suffix}")


# =============================================================================
# Reading a .tex without FF16Tools
# =============================================================================
#
# A preview used to cost one FF16Tools run per .tex: copy the file into the
# cache, start the program, wait for it to write a .dds, read that back. For
# an icon the program's start-up is nearly all of it, and the UI Layouts page
# asks for dozens of sheets per screen.
#
# The format is small. A .tex holds one picture as chunks (FF16Tools'
# `TextureFile.GetTextureData`): each chunk stored as it is when its packed
# and unpacked sizes match, otherwise packed with GDeflate - DirectStorage's
# version of DEFLATE, the same codes spread over 32 interleaved bit streams.
# Unpacked, the pixels are BC1-BC7 blocks or plain RGBA, with each row padded
# to 256 bytes. `TextureFile.GetAsDds` takes the padding out and puts a DDS
# header in front, which Pillow reads. This does the same in memory, for the
# first mip - the one Pillow shows - and hands Pillow the same bytes.
#
# **Checked, not assumed:** the nine bar textures Zodi exported to PNG through
# the Textures page (so through the real FF16Tools, on his machine) come out
# pixel for pixel identical, and the GDeflate step alone gives byte for byte
# what NVIDIA's own decoder gives on every real .tex available here (sixteen:
# BC7 and RGBA, one with stored blocks). `dev/test_tex_decode.py` holds both.
#
# The decoder is a port of the GDeflate reference decompressor in NVIDIA's
# fork of libdeflate (github.com/NVIDIA/libdeflate, branch `gdeflate`, file
# lib/gdeflate_decompress_template.h): Copyright 2016 Eric Biggers (MIT) and
# Copyright (c) 2020-2022 NVIDIA CORPORATION & AFFILIATES (Apache-2.0). This
# is a translation into Python with changes; see NOTICE.md.

#: The largest .tex (by packed size) read here rather than by FF16Tools.
#:
#: Python unpacks GDeflate at about 0.35 seconds per packed megabyte on the
#: machine this was built on - whatever the picture, because the time goes
#: per code read and there is about one per packed byte. FF16Tools unpacks
#: natively but costs a program start per texture, which on Windows is a
#: .NET start-up: not measured, but not less than a few tenths of a second.
#: A megabyte keeps this path to about that, so it is never much slower and
#: usually far quicker (an icon: a few milliseconds). Bigger textures go to
#: FF16Tools as before. Either way the pixels are the same, so this number
#: decides speed only.
IN_PROCESS_MAX_PACKED_BYTES = 1024 * 1024

#: DXGI numbers for the pixel formats read here: the ones Pillow's DDS reader
#: handles, keyed by the .tex's own format number (FF16Tools'
#: `TexturePixelFormat`). Anything else goes to FF16Tools, exactly as before.
_TEX_BC_FORMATS = {
    0x107420: (71, 8),     # BC1_UNORM
    0x117430: (74, 16),    # BC2_UNORM
    0x127430: (77, 16),    # BC3_UNORM
    0x137120: (80, 8),     # BC4_UNORM
    0x147230: (83, 16),    # BC5_UNORM
    0x147231: (84, 16),    # BC5_SNORM
    0x157330: (95, 16),    # BC6H_UF16
    0x157331: (96, 16),    # BC6H_SF16
    0x167430: (98, 16),    # BC7_UNORM
    0x168430: (99, 16),    # BC7_UNORM_SRGB
}
_TEX_RGBA_FORMATS = {
    0xA0450: 27,           # R8G8B8A8_TYPELESS
    0xA1450: 28,           # R8G8B8A8_UNORM
    0xA2450: 29,           # R8G8B8A8_UNORM_SRGB
}


class TexNotReadHere(ValueError):
    """A .tex this module leaves to FF16Tools; the message says why."""


# -- GDeflate ------------------------------------------------------------------

_GD_STREAMS = 32
_GD_TILE = 64 * 1024
# DEFLATE's length and distance codes, as GDeflate uses them: the Deflate64
# variant, where length codes 285-287 are 3 plus sixteen more bits.
_GD_LENGTH_BASE = (3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
                   35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 3, 3, 3)
_GD_LENGTH_EXTRA = (0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
                    3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 16, 16, 16)
_GD_DIST_BASE = (1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193,
                 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145,
                 8193, 12289, 16385, 24577, 32769, 49153)
_GD_DIST_EXTRA = (0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6,
                  7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14)
_GD_PRECODE_ORDER = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2,
                     14, 1, 15)
#: A table slot no code reaches. Its symbol is past the end of every list
#: above, so reading one fails at once instead of looping on zero bits.
_GD_NO_CODE = 400 << 4
_gd_static = None


def _gd_table(lengths, bits: int = 15) -> list:
    """
    A full lookup for canonical DEFLATE codes: indexed by the next `bits`
    bits of a stream (lowest first), each slot holds `(symbol << 4) |
    code length`.
    """
    size = 1 << bits
    table = [_GD_NO_CODE] * size
    count = [0] * 16
    for length in lengths:
        count[length] += 1
    count[0] = 0
    code, first = 0, [0] * 16
    for length in range(1, 16):
        code = (code + count[length - 1]) << 1
        first[length] = code
    for symbol, length in enumerate(lengths):
        if not length:
            continue
        code = first[length]
        first[length] += 1
        if code >= 1 << length:
            raise ValueError("over-subscribed code lengths")
        reversed_code = int(format(code, f"0{length}b")[::-1], 2)
        table[reversed_code::1 << length] = [(symbol << 4) | length] * (size >> length)
    return table


def _gd_static_tables():
    global _gd_static
    if _gd_static is None:
        _gd_static = (_gd_table([8] * 144 + [9] * 112 + [7] * 24 + [8] * 8),
                      _gd_table([5] * 32))
    return _gd_static


def _gdeflate_tile(data: bytes, out_size: int) -> bytes:
    """
    One 64 KB page of a GDeflate stream. The reference decoder's structure,
    step for step: 32 bit buffers, each topped up with the stream's next
    32 bits whenever it holds fewer than 32 after its turn; a match's length
    is read in one round and its distance, from the same buffer, in the
    next.
    """
    padded = bytes(data) + bytes(-len(data) % 4 + 256)
    words = struct.unpack_from(f"<{len(padded) // 4}I", padded)
    wi = _GD_STREAMS
    buf = list(words[:_GD_STREAMS])
    left = [32] * _GD_STREAMS
    out = bytearray()
    pending = [None] * _GD_STREAMS
    while True:
        # Block header, always on stream 0.
        b = buf[0]
        final, kind = b & 1, (b >> 1) & 3
        buf[0] = b >> 3
        left[0] -= 3
        if left[0] < 32:
            buf[0] |= words[wi] << left[0]
            wi += 1
            left[0] += 32
        if kind == 0:
            # Stored: a 16-bit count on stream 0, then one byte per stream
            # in turn, starting at stream 0.
            count = buf[0] & 0xFFFF
            buf[0] >>= 16
            left[0] -= 16
            if len(out) + count > out_size:
                raise ValueError("a stored block runs past the page")
            idx = 0
            for _ in range(count):
                out.append(buf[idx] & 0xFF)
                buf[idx] >>= 8
                left[idx] -= 8
                if left[idx] < 32:
                    buf[idx] |= words[wi] << left[idx]
                    wi += 1
                    left[idx] += 32
                idx = (idx + 1) & 31
            if final:
                break
            continue
        if kind == 1:
            lit_table, dist_table = _gd_static_tables()
        elif kind == 2:
            b = buf[0]
            n_lit = (b & 31) + 257
            n_dist = ((b >> 5) & 31) + 1
            n_pre = ((b >> 10) & 15) + 4
            buf[0] = b >> 14
            left[0] -= 14
            if left[0] < 32:
                buf[0] |= words[wi] << left[0]
                wi += 1
                left[0] += 32
            pre = [0] * 19
            idx = 0
            for i in range(n_pre):
                pre[_GD_PRECODE_ORDER[i]] = buf[idx] & 7
                buf[idx] >>= 3
                left[idx] -= 3
                if left[idx] < 32:
                    buf[idx] |= words[wi] << left[idx]
                    wi += 1
                    left[idx] += 32
                idx = (idx + 1) & 31
            pre_table = _gd_table(pre, 7)
            lengths = []
            idx = 0
            while len(lengths) < n_lit + n_dist:
                e = pre_table[buf[idx] & 127]
                size, symbol = e & 15, e >> 4
                if not size:
                    raise ValueError("a code length code that is not in the table")
                buf[idx] >>= size
                left[idx] -= size
                if symbol < 16:
                    lengths.append(symbol)
                elif symbol == 16:
                    if not lengths:
                        raise ValueError("a repeat with nothing before it")
                    lengths.extend([lengths[-1]] * (3 + (buf[idx] & 3)))
                    buf[idx] >>= 2
                    left[idx] -= 2
                elif symbol == 17:
                    lengths.extend([0] * (3 + (buf[idx] & 7)))
                    buf[idx] >>= 3
                    left[idx] -= 3
                else:
                    lengths.extend([0] * (11 + (buf[idx] & 127)))
                    buf[idx] >>= 7
                    left[idx] -= 7
                if left[idx] < 32:
                    buf[idx] |= words[wi] << left[idx]
                    wi += 1
                    left[idx] += 32
                idx = (idx + 1) & 31
            if len(lengths) != n_lit + n_dist:
                raise ValueError("code lengths run past their count")
            lit_table = _gd_table(lengths[:n_lit])
            dist_table = _gd_table(lengths[n_lit:])
        else:
            raise ValueError("block type 3 does not exist")

        idx = 0
        waiting = 0                     # bit n set: stream n reads a distance next
        while True:
            if (waiting >> idx) & 1:
                length, at = pending[idx]
                b = buf[idx]
                e = dist_table[b & 32767]
                size, symbol = e & 15, e >> 4
                b >>= size
                extra = _GD_DIST_EXTRA[symbol]
                distance = _GD_DIST_BASE[symbol] + (b & ((1 << extra) - 1))
                buf[idx] = b >> extra
                left[idx] -= size + extra
                if distance > at:
                    raise ValueError("a match reaches back before the start")
                start = at - distance
                if distance >= length:
                    out[at:at + length] = out[start:start + length]
                else:
                    for k in range(length):
                        out[at + k] = out[start + k]
                waiting &= ~(1 << idx)
            else:
                b = buf[idx]
                e = lit_table[b & 32767]
                size, symbol = e & 15, e >> 4
                if symbol < 256:
                    out.append(symbol)
                    buf[idx] = b >> size
                    left[idx] -= size
                elif symbol == 256:
                    buf[idx] = b >> size
                    left[idx] -= size
                    break
                else:
                    code = symbol - 257
                    extra = _GD_LENGTH_EXTRA[code]
                    b >>= size
                    length = _GD_LENGTH_BASE[code] + (b & ((1 << extra) - 1))
                    buf[idx] = b >> extra
                    left[idx] -= size + extra
                    if len(out) + length > out_size:
                        raise ValueError("a match runs past the page")
                    pending[idx] = (length, len(out))
                    out.extend(bytes(length))
                    waiting |= 1 << idx
            if left[idx] < 32:
                buf[idx] |= words[wi] << left[idx]
                wi += 1
                left[idx] += 32
            idx = (idx + 1) & 31
            if len(out) > out_size:
                raise ValueError("the page decodes to more than it holds")
        # The block has ended. One more lap, from the stream that read the
        # end, finishes the matches still waiting for their distances.
        for _ in range(_GD_STREAMS):
            if (waiting >> idx) & 1:
                length, at = pending[idx]
                b = buf[idx]
                e = dist_table[b & 32767]
                size, symbol = e & 15, e >> 4
                b >>= size
                extra = _GD_DIST_EXTRA[symbol]
                distance = _GD_DIST_BASE[symbol] + (b & ((1 << extra) - 1))
                buf[idx] = b >> extra
                left[idx] -= size + extra
                if distance > at:
                    raise ValueError("a match reaches back before the start")
                start = at - distance
                for k in range(length):
                    out[at + k] = out[start + k]
                waiting &= ~(1 << idx)
            if left[idx] < 32:
                buf[idx] |= words[wi] << left[idx]
                wi += 1
                left[idx] += 32
            idx = (idx + 1) & 31
        if final:
            break
    if len(out) != out_size:
        raise ValueError(f"a page unpacked to {len(out)} bytes, not {out_size}")
    return bytes(out)


def gdeflate_decompress(data: bytes, out_size: int) -> bytes:
    """
    Unpacks a GDeflate stream (DirectStorage's tile stream: an 8-byte header,
    a table of page offsets, then the pages, each 64 KB unpacked).

    Raises ValueError for anything that is not a stream of that shape or
    does not unpack to exactly `out_size` bytes. Python's own errors from a
    damaged stream (an index past the end) are left to the caller, which
    treats every failure the same way.
    """
    if len(data) < 8:
        raise ValueError("too short to be a GDeflate stream")
    ident, check, pages, bits = struct.unpack_from("<BBHI", data, 0)
    if ident != 4 or check != ident ^ 0xFF or bits & 3 != 1:
        raise ValueError("not a GDeflate stream")
    last = (bits >> 2) & 0x3FFFF
    offsets = struct.unpack_from(f"<{pages}I", data, 8)
    base = 8 + 4 * pages
    out = []
    for page in range(pages):
        start = offsets[page] if page else 0
        end = offsets[page + 1] if page < pages - 1 else start + offsets[0]
        size = _GD_TILE if (page < pages - 1 or last == 0) else last
        out.append(_gdeflate_tile(data[base + start: base + end], size))
    result = b"".join(out)
    if len(result) != out_size:
        raise ValueError(f"unpacked to {len(result)} bytes, not {out_size}")
    return result


# -- .tex ------------------------------------------------------------------------

def tex_as_dds(tex: bytes, max_packed: Optional[int] = None) -> bytes:
    """
    A .tex's first picture as a DDS in memory - its first mip, laid out the
    way FF16Tools' `TextureFile.GetAsDds` lays it out, which is what Pillow
    reads.

    Two of GetAsDds' habits are kept on purpose, because the pixels have to
    match what FF16Tools gives:

    - rows are un-padded only when the picture is stored in chunks (the
      256-byte padding comes from DirectStorage);
    - of a block-compressed picture it copies `height // 4` rows of blocks,
      so a height that is not a multiple of 4 leaves the last row of blocks
      empty. It is left empty here too.

    Raises `TexNotReadHere` for a file this does not read (more than one
    picture, not a flat 2D picture, a pixel format Pillow cannot show, or
    packed data over `max_packed`), and ValueError for a damaged one.
    """
    if tex[:4] != b"TEX ":
        raise TexNotReadHere("not a .tex file")
    pictures = tex[8]
    chunk_count_total = struct.unpack_from("<H", tex, 10)[0]
    if pictures != 1:
        # FF16Tools writes these to a folder of their own, not one .dds.
        raise TexNotReadHere(f"{pictures} pictures in one file")
    (flags, fmt, _mips, width, height, _depth, data_offset, data_size,
     _colour, chunk_index, chunk_count) = struct.unpack_from("<IIHHHHIIIHH", tex, 0x28)
    if flags & 3 != 1:
        raise TexNotReadHere("not a flat 2D picture")
    if fmt in _TEX_BC_FORMATS:
        dxgi, block_bytes = _TEX_BC_FORMATS[fmt]
        pitch = max(1, (width + 3) // 4) * block_bytes
        rows = height // 4
        slice_rows = max(1, (height + 3) // 4)
    elif fmt in _TEX_RGBA_FORMATS:
        dxgi = _TEX_RGBA_FORMATS[fmt]
        pitch = width * 4
        rows = slice_rows = height
    else:
        raise TexNotReadHere(f"pixel format 0x{fmt:X}")
    if not width or not height:
        raise TexNotReadHere("an empty picture")

    if (flags >> 3) & 1:
        # Stored whole, not in chunks.
        if max_packed is not None and data_size > max_packed:
            raise TexNotReadHere("larger than is quicker to read here")
        data = tex[data_offset:data_offset + data_size]
    else:
        if chunk_index + chunk_count > chunk_count_total:
            raise ValueError("the picture names chunks the file does not list")
        table = 0x28 + pictures * 0x20
        chunks = [struct.unpack_from("<III", tex, table + i * 0x10)
                  for i in range(chunk_index, chunk_index + chunk_count)]
        packed = sum(bits >> 2 for _off, bits, _size in chunks)
        if max_packed is not None and packed > max_packed:
            raise TexNotReadHere("larger than is quicker to read here")
        parts = []
        for offset, bits, size in chunks:
            blob = tex[offset:offset + (bits >> 2)]
            if len(blob) != bits >> 2:
                raise ValueError("a chunk runs past the end of the file")
            # "This is how the game checks" (FF16Tools): same size, not packed.
            parts.append(blob if (bits >> 2) == size else gdeflate_decompress(blob, size))
        data = b"".join(parts)

    stride = (pitch + 255) & ~255 if chunk_count else pitch
    if rows and (rows - 1) * stride + pitch > len(data):
        raise ValueError("the picture's data is shorter than its size says")
    if stride == pitch:
        first_mip = bytearray(data[:rows * pitch])
    else:
        first_mip = bytearray()
        for row in range(rows):
            first_mip += data[row * stride: row * stride + pitch]
    first_mip += bytes(slice_rows * pitch - len(first_mip))

    header = bytearray(4 + 124 + 20)
    header[0:4] = b"DDS "
    # size, flags (caps, height, width, pixel format, linear size), height,
    # width, linear size, depth, mips
    struct.pack_into("<7I", header, 4, 124, 0x81007, height, width, pitch, 0, 1)
    struct.pack_into("<2I4s", header, 4 + 72, 32, 0x4, b"DX10")     # pixel format: FourCC DX10
    struct.pack_into("<I", header, 4 + 104, 0x1000)                 # caps: texture
    struct.pack_into("<5I", header, 128, dxgi, 3, 0, 1, 0)          # DXGI format, 2D, array of 1
    return bytes(header) + bytes(first_mip)


def decode_tex_in_process(path: Path, max_packed: Optional[int] = IN_PROCESS_MAX_PACKED_BYTES):
    """
    A .tex as an RGBA `PIL.Image`, read in Python - the same pixels
    `load_game_texture_preview` gets from FF16Tools. Raises `TexNotReadHere`
    for what it leaves to FF16Tools, and other exceptions for a damaged
    file; the caller falls back to FF16Tools on either.
    """
    return _image_from_dds(tex_as_dds(Path(path).read_bytes(), max_packed))


# =============================================================================
# Seam fix (the Portrait Seam Fixer's `_fix_array`, as it is)
# =============================================================================

#: Said when the seam fix can't run: running from source without the two
#: libraries it needs. A packaged build has them.
SEAM_FIX_NEEDS = ("The face seam fix needs numpy and scipy, which aren't installed here. "
                  "Install them with: pip install numpy scipy")


def apply_seam_fix(img):
    """
    Returns (fixed_image, n_promoted). Input must be an RGBA `PIL.Image`.

    The "IVC Portrait Seam Fixer" (`fix_portrait_seam.py`, Zodi's) exactly:
    its `_fix_array`, the same numpy and scipy calls in the same order, on
    the picture as an RGBA array.

    Stage 1 gives every fully transparent pixel the colour of its nearest
    visible one (`scipy.ndimage.distance_transform_edt`), so BC7 encoding
    never guesses a colour for a pixel with no data. Stage 2 raises alpha
    from 0 to 4 (still transparent to the eye) in any 4x4 block that also
    holds an opaque pixel, so the encoder doesn't leave a dark line round
    the portrait in the game.

    **Back to this from a Pillow rewrite** (Zodi: "There was an older fix
    that worked better. Let go back to using that fix"). The rewrite
    dropped numpy and scipy, 96 MB of the build then, and matched this
    one's alpha exactly, but filled about 40% of the transparent pixels
    that share a block with visible ones from a different neighbour - an
    8-way ring fill, not the nearest by distance - and in the game it drew
    the seam this is for. `dev/test_seam_fix.py` holds this function to
    the script's own, byte for byte.

    Raises RuntimeError (`SEAM_FIX_NEEDS`) without numpy and scipy: a face
    exported without its fix would show the seam, so it is not written
    another way.
    """
    try:
        import numpy as np
        from scipy import ndimage
    except ImportError as exc:
        raise RuntimeError(SEAM_FIX_NEEDS) from exc
    from PIL import Image

    arr = np.array(img.convert("RGBA"), dtype=np.uint8)

    # -- fix_portrait_seam.py's _fix_array, unchanged ---------------------
    h, w = arr.shape[:2]
    result = arr.copy()
    alpha = arr[:, :, 3].astype(np.int32)

    has_color = alpha > 0
    if not has_color.any():
        return Image.fromarray(result, "RGBA"), 0

    # Stage 1 - colour dilation
    _, nearest = ndimage.distance_transform_edt(~has_color, return_indices=True)
    for ch in range(3):
        result[:, :, ch] = arr[:, :, ch][nearest[0], nearest[1]]

    # Stage 2 - BC7 block alpha promotion
    opaque = alpha > 128
    bh, bw = (h + 3) // 4, (w + 3) // 4
    promoted = 0
    for by in range(bh):
        for bx in range(bw):
            r0, r1 = by * 4, min(by * 4 + 4, h)
            c0, c1 = bx * 4, min(bx * 4 + 4, w)
            if opaque[r0:r1, c0:c1].any():
                blk = result[r0:r1, c0:c1, 3]
                mask = blk == 0
                if mask.any():
                    result[r0:r1, c0:c1, 3][mask] = 4
                    promoted += int(mask.sum())
    # -----------------------------------------------------------------------

    return Image.fromarray(result.astype(np.uint8), "RGBA"), promoted


# =============================================================================
# Staging a replacement for export
# =============================================================================

def stage_texture_replacement(
    target_relative_path: str, source_image_path: Path, staging_dir: Path, cli_path: Optional[Path]
) -> Path:
    """
    Prepares a replacement image for the given target relative path
    (target_relative_path's own extension, .tga or .tex, determines the
    output format), applying the portrait seam fix automatically if the
    target is a face texture. Returns the path to the finished file, named
    to match the target exactly, ready to copy into the mod at that same
    relative path.
    """
    from PIL import Image

    staging_dir.mkdir(parents=True, exist_ok=True)
    target_name = Path(target_relative_path).name
    target_ext = Path(target_relative_path).suffix.lower()
    face = is_face_texture(target_relative_path)

    img = load_any_image(source_image_path)
    if face:
        img, _ = apply_seam_fix(img)

    if target_ext == ".tga":
        out_path = staging_dir / target_name
        # Run-length encoded, which is what the game's own files are.
        #
        # Pillow writes TGA uncompressed by default, and for a large
        # texture that is enormous: `ffto_screen_filter_0.tga` is 2048x2048
        # and ships at 0.49 MB, where an uncompressed 32-bit write of the
        # same image is 16.00 MB - thirty-two times bigger, for one file,
        # in a mod people download.
        #
        # Safe because the game demonstrably reads RLE: a working texture
        # pack built outside this tool contains both RLE and uncompressed
        # TGAs and the game accepts both. The header says which, and TGA
        # readers are required to handle image type 10.
        #
        # Falls back to an uncompressed write rather than failing, because
        # a mod that is large is better than a mod that did not build.
        try:
            img.save(str(out_path), compression="tga_rle")
        except Exception:                                     # noqa: BLE001
            img.save(str(out_path))
        return out_path

    if target_ext == ".tex":
        if cli_path is None:
            raise ValueError("FF16Tools.CLI.exe isn't set up (General Setup) - needed to produce .tex files.")
        from . import ff16tools
        stem = Path(target_name).stem
        staged_png = staging_dir / f"{stem}.png"
        img.save(str(staged_png))
        code = ff16tools.run_img_to_tex(cli_path, staged_png)
        out_path = staging_dir / f"{stem}.tex"
        if code != 0 or not out_path.exists():
            raise ValueError(f"FF16Tools.CLI img-conv failed converting {staged_png.name} (exit code {code}).")
        return out_path

    raise ValueError(f"Unsupported target extension: {target_ext}")


def graft_extra_paths(tree: TextureTreeNode, relative_paths) -> TextureTreeNode:
    """
    Adds texture paths to a scanned tree that aren't in the unpacked game.

    A mod can ship a texture at a path the game has no file for - the Dark
    Knight Expansion adds ui/ffto/icon/job/texture/j_160_uitx.tex for a job
    slot the base game never had an icon for. The tree is built by scanning
    the unpacked game, so those files simply weren't in it: the Textures tab
    reported "2 of 4503 textures have a staged replacement" while showing
    neither of the two anywhere in the browser.

    Grafting them in makes them selectable like any other texture. They have
    no vanilla original to preview against, which the tab handles the same
    way it handles any missing source file.

    Returns the same tree object, modified in place.
    """
    for relative_path in sorted(set(relative_paths)):
        parts = [p for p in relative_path.replace("\\", "/").split("/") if p]
        if not parts:
            continue
        node = tree
        walked = []
        for part in parts[:-1]:
            walked.append(part)
            existing = next(
                (c for c in node.children if not c.is_file and c.name == part), None
            )
            if existing is None:
                existing = TextureTreeNode(
                    name=part, relative_path="/".join(walked), is_file=False
                )
                node.children.append(existing)
                node.children.sort(key=lambda n: (n.is_file, n.name.lower()))
            node = existing

        filename = parts[-1]
        if any(c.is_file and c.name == filename for c in node.children):
            continue  # the game already has this one; nothing to graft
        node.children.append(
            TextureTreeNode(name=filename, relative_path=relative_path, is_file=True)
        )
        node.children.sort(key=lambda n: (n.is_file, n.name.lower()))
    return tree


def load_replacement_preview(path: Path, cli_path: Optional[Path], cache_dir: Path):
    """
    Decodes a staged replacement for preview.

    A staged replacement is usually a plain image the user picked (.png,
    .tga, ...), but it can also be a game-format .tex - that's what comes
    back when a mod is opened, since the mod ships finished game files. Only
    load_game_texture_preview can read those (it shells out to FF16Tools),
    so dispatching on extension is what makes a recovered mod's textures
    actually previewable instead of showing a decode error.
    """
    if Path(path).suffix.lower() == ".tex":
        return load_game_texture_preview(Path(path), cli_path, cache_dir)
    return load_any_image(path)
