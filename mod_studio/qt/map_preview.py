"""
A map package's enhanced look drawn from the game's four camera corners, in
one picture: for a person or an AI coworker checking an edit without Mod
Studio's window. Here rather than in `map_package` because it draws with Qt
and OpenGL, and the engine imports neither (`dev/test_engine_boundary.py`).

    python -m mod_studio.qt.map_preview <package folder> --game <unpacked game> --out preview.png

`python -m mod_studio.map_package preview` runs this. Needs PySide6 and a
graphics driver with OpenGL 3.3, as the Map Editor does.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QImage, QPainter

from .. import map_package as mpk
from . import map_render as mr
from . import map_scene as ms


def preview(folder, game_dir, out, size=(640, 480)) -> Path:
    """Draws the package's map from the four corners into `out` (a PNG), two by two."""
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    built = mpk.build(folder)
    mesh_file = mpk.write_built(folder, built)
    scene = ms.build_enhanced(Path(game_dir), built.number, mesh_file=mesh_file,
                              picture_files=built.pictures)
    renderer = mr.MapRenderer()
    if not renderer.ensure_context():
        raise mpk.PackageError(f"can't draw here: {renderer.error}")
    renderer.set_scene(scene)
    w, h = size
    sheet = QImage(2 * w, 2 * h, QImage.Format_RGB32)
    painter = QPainter(sheet)
    for i, (yaw, _bit) in enumerate(ms.CORNERS):
        painter.drawImage((i % 2) * w, (i // 2) * h, renderer.render(mr.Camera(yaw=yaw), w, h))
    painter.end()
    renderer.close()
    sheet.save(str(out))
    del app
    return Path(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mod_studio.qt.map_preview",
                                     description="Draw a map package's map from the four camera corners.")
    parser.add_argument("folder")
    parser.add_argument("--game", required=True, help="the unpacked game folder")
    parser.add_argument("--out", required=True, help="the picture to write (.png)")
    args = parser.parse_args(argv)
    try:
        print(f"Wrote {preview(args.folder, args.game, args.out)}")
    except mpk.PackageError as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
