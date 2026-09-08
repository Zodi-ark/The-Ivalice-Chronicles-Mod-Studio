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
seam around the portrait. apply_seam_fix() ports Zodi's own fix_portrait_
seam.py algorithm directly (already proven working, unchanged here) and is
applied automatically to any replacement staged for a face texture path -
no separate script for the user to run.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

TEXTURE_EXTENSIONS = (".tga", ".tex")
FACE_TEXTURE_PATH_FRAGMENT = "ui/ffto/common/face/texture/"
# What a replacement image can be - matches FF16Tools img-conv's own
# accepted input formats (dds is recommended there for mip support; the
# rest get exported as R8G8B8A8_UNORM internally).
REPLACEMENT_IMAGE_EXTENSIONS = (".dds", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tga", ".webp")


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
    .tga loads directly; .tex is converted to .dds via FF16Tools.CLI
    tex-conv first (cached under cache_dir so repeated previews of the
    same file don't reconvert every time).
    """
    if not path.exists():
        raise ValueError(f"No texture file found at {path.name} - this id/path doesn't exist in the unpacked game.")

    ext = path.suffix.lower()
    if ext == ".tga":
        return load_any_image(path)

    if ext == ".tex":
        if cli_path is None:
            raise ValueError("FF16Tools.CLI.exe isn't set up (General Setup) - needed to preview .tex files.")
        cache_dir.mkdir(parents=True, exist_ok=True)
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
        if not dds_path.exists():
            from . import ff16tools
            shutil.copy(path, staged)
            code = ff16tools.run_tex_to_dds(cli_path, staged)
            if code != 0 or not dds_path.exists():
                raise ValueError(
                    f"FF16Tools.CLI tex-conv failed converting {path.name} for preview (exit code {code})."
                )
        return load_any_image(dds_path)

    raise ValueError(f"Unsupported texture extension for preview: {path.suffix}")


# =============================================================================
# Seam fix (ported from Zodi's fix_portrait_seam.py - algorithm unchanged)
# =============================================================================

def apply_seam_fix(img):
    """
    Returns (fixed_image, n_promoted). Input must be an RGBA `PIL.Image`.

    Stage 1 dilates visible colour into fully-transparent regions so BC7
    encoding never has to guess a colour for a "no data" pixel. Stage 2
    promotes alpha from 0 to 4 (still imperceptibly transparent) inside any
    4x4 block that also contains an opaque pixel, so the encoder doesn't
    leave a solid black seam around the portrait in-game.

    Ported from the numpy/scipy version, which used
    `scipy.ndimage.distance_transform_edt` to find each transparent pixel's
    nearest visible neighbour. That one call was the only thing scipy was
    ever imported for, and it cost 96 MB of the shipped build once numpy
    came with it.

    What is IDENTICAL to the old version:

    - the alpha channel, exactly, including the promoted count
    - every visible pixel's colour - stage 1 only ever writes into pixels
      with alpha 0
    - the colour dilated into transparent pixels within DILATE_PASSES of
      visible content, which is a true 8-neighbour nearest fill

    What DIFFERS: transparent pixels further than DILATE_PASSES from any
    visible pixel get the average visible colour rather than the nearest
    one. That is deliberate and safe, because of what the fix is for.

    BC7 encodes in 4x4 blocks. A block's colour endpoints are only pulled
    about by transparent pixels if that same block also contains visible
    ones - and any such pixel is within 3px of visible content. Beyond a
    handful of pixels out, the whole block is invisible and the colour in
    it cannot produce a seam because nothing in that block is drawn.
    DILATE_PASSES is set well past that bound, so every pixel that can
    affect a seam gets the exact nearest colour, and the fill beyond it is
    a courtesy to the encoder rather than something the image depends on.

    The old exact-everywhere fill also wasn't stable in the way it might
    look: where two visible pixels are equidistant, which one wins is an
    implementation detail of the distance transform, not a property of the
    image.
    """
    from PIL import Image, ImageChops, ImageStat

    DILATE_PASSES = 24

    w, h = img.size
    r, g, b, a = img.split()

    # "Has colour" means any alpha at all, matching the old `alpha > 0`.
    known = a.point(lambda v: 255 if v > 0 else 0).convert("L")
    if not known.getbbox():
        return img.copy(), 0

    # -- Stage 1: dilate colour outwards, one ring at a time ---------------
    #
    # Eight `ImageChops.offset` shifts per pass, each pasting whole pixels
    # through a mask. Whole pixels matter: filtering the channels
    # separately (a MaxFilter, say) would take red from one neighbour and
    # green from another and invent a colour that is in no neighbour at
    # all.
    #
    # Two things this has to get right, both of which are silent when wrong:
    #
    # `offset` WRAPS. Without blanking the wrapped edge, a pixel on the left
    # border takes its colour from the right border - the one place in the
    # image guaranteed to be unrelated to it.
    #
    # All eight directions are judged against the SAME snapshot of the
    # known-pixel mask. Updating it between directions would let a pixel
    # filled by the first direction act as a source for the seventh in the
    # same pass, so the front would advance more than one ring per pass and
    # do it faster along whichever axis happened to be listed first.
    rgb = Image.merge("RGB", (r, g, b))
    NEIGHBOURS = ((-1, 0), (1, 0), (0, -1), (0, 1),
                  (-1, -1), (-1, 1), (1, -1), (1, 1))

    def unwrapped(im, dx, dy, fill=0):
        """`offset` result with the wrapped-around edge blanked out."""
        if dx:
            box = (0, 0, dx, h) if dx > 0 else (w + dx, 0, w, h)
            im.paste(fill, box)
        if dy:
            box = (0, 0, w, dy) if dy > 0 else (0, h + dy, w, h)
            im.paste(fill, box)
        return im

    for _ in range(DILATE_PASSES):
        unknown = ImageChops.invert(known)
        if not unknown.getbbox():
            break
        newly = Image.new("L", (w, h), 0)
        for dx, dy in NEIGHBOURS:
            src_known = unwrapped(ImageChops.offset(known, dx, dy), dx, dy)
            fill = ImageChops.multiply(src_known, unknown)
            # An earlier direction in this pass already claimed these, and
            # the order is the priority: orthogonal neighbours before
            # diagonal ones, which is what keeps the fill close to a true
            # nearest rather than a square.
            fill = ImageChops.subtract(fill, newly)
            if not fill.getbbox():
                continue
            shifted = unwrapped(ImageChops.offset(rgb, dx, dy), dx, dy, (0, 0, 0))
            rgb.paste(shifted, (0, 0), fill)
            newly = ImageChops.lighter(newly, fill)
        known = ImageChops.lighter(known, newly)

    still_unknown = ImageChops.invert(known)
    if still_unknown.getbbox():
        # Everything left is far enough out to be invisible. Flat-fill it
        # with the average visible colour so the encoder still has
        # something coherent rather than black.
        visible = a.point(lambda v: 255 if v > 0 else 0).convert("L")
        mean = ImageStat.Stat(Image.merge("RGB", (r, g, b)), visible).mean
        rgb.paste(tuple(int(round(c)) for c in mean), (0, 0), still_unknown)

    # -- Stage 2: promote alpha inside blocks that contain opaque pixels ---
    #
    # Exactly the old rule: for each 4x4 block, if any pixel has alpha>128,
    # every pixel in that block with alpha==0 becomes 4.
    #
    # Done with a downscale rather than a Python loop over blocks. A BOX
    # resize averages each 4x4 group, so a block containing at least one
    # 255 averages above 0 and a block containing none averages exactly 0 -
    # which is the "any opaque in this block" test, at C speed.
    opaque = a.point(lambda v: 255 if v > 128 else 0).convert("L")

    # Pad to a whole number of blocks first. Without this the resize would
    # spread a partial edge block across the wrong pixels, and the old code
    # explicitly clamped those blocks with min(by*4+4, h).
    pw, ph = (w + 3) // 4 * 4, (h + 3) // 4 * 4
    if (pw, ph) != (w, h):
        padded = Image.new("L", (pw, ph), 0)
        padded.paste(opaque, (0, 0))
        opaque = padded

    block_any = opaque.resize((pw // 4, ph // 4), Image.BOX)
    block_any = block_any.point(lambda v: 255 if v > 0 else 0)
    block_mask = block_any.resize((pw, ph), Image.NEAREST).crop((0, 0, w, h))

    transparent = a.point(lambda v: 255 if v == 0 else 0).convert("L")
    promote = ImageChops.multiply(block_mask.convert("L"), transparent)
    promote = promote.point(lambda v: 255 if v > 0 else 0).convert("L")

    promoted = promote.histogram()[255]
    if promoted:
        a = a.copy()
        a.paste(4, (0, 0), promote)

    out_r, out_g, out_b = rgb.split()
    return Image.merge("RGBA", (out_r, out_g, out_b, a)), promoted


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
