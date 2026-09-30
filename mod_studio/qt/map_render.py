"""
Drawing a battle map with the graphics card, off screen.

An OpenGL context on an offscreen surface draws into a framebuffer, and the
picture is read back as a QImage for an ordinary widget to paint. No
`QOpenGLWidget`: once a window holds one, Qt composites the whole window
through OpenGL, which changes how every other page draws and how the
window's backdrop shows through. Reading back costs a few milliseconds a
frame, which turning a map with the mouse doesn't notice.

Needs OpenGL 3.3. Where the machine's driver can't give it,
`MapRenderer.error` says why and the page shows that instead of a map.
(Whether Qt on Windows turns to the software renderer the build ships,
`opengl32sw.dll`, for a driver too old for 3.3 is not known here.)

**Walls in the way fade** (`map_scene.corner_weights`): a polygon the game
leaves out from some corners is drawn solid where it shows fully, not at
all where it is left out, and blended in a pass of its own while the
camera turns between corners (`FADING`).

**Each draw turns off the vertex arrays it turned on** (`_draw`). The first
build left them on: the classic look's fourth and fifth arrays stayed on
after its map was gone, pointing at a buffer that no longer existed, and
drawing the next map in the enhanced look read through them. Mesa ignores
an array the shader doesn't use; Zodi's Windows driver crashed on it
("access violation" in `glDrawArrays`, switching from Classic to Enhanced
and between enhanced maps).
"""
from __future__ import annotations

import atexit
import math
import weakref
from typing import Optional

from PySide6.QtGui import (QImage, QMatrix4x4, QOffscreenSurface, QOpenGLContext, QSurfaceFormat,
                           QVector2D, QVector3D, QVector4D)

from . import map_scene as ms

GL_TRIANGLES, GL_LINES = 0x0004, 0x0001
GL_FLOAT = 0x1406
GL_DEPTH_TEST, GL_BLEND = 0x0B71, 0x0BE2
GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT = 0x4000, 0x0100
GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ZERO, GL_ONE = 0x0302, 0x0303, 0, 1
GL_LEQUAL = 0x0203

#: How many texture animations a classic map can have: its 32 records.
UV_ANIMATIONS = 32

#: The passes a scene is drawn in: its solid polygons where they show fully,
#: its see-through ones, and its solid ones fading in or out.
SOLID, SEE_THROUGH, FADING = 0, 1, 2

# How much of a polygon shows from the camera's corner (`map_scene.shown`),
# and whether this pass draws it: SOLID the whole, SEE_THROUGH anything
# showing, FADING the part-shown, blended by how much.
_SHOWN = """
uniform vec4 cornerWeight; uniform int drawPass;
float shownBy(float render) {
  int r = int(render + 0.5);
  vec4 hidden = vec4((r >> 13) & 1, (r >> 12) & 1, (r >> 11) & 1, (r >> 10) & 1);
  return 1.0 - dot(cornerWeight, hidden);
}
bool drawnIn(float s) {
  if (drawPass == 0) return s > 0.999;
  if (drawPass == 1) return s > 0.001;
  return s > 0.001 && s <= 0.999;
}"""

ENHANCED_VS = """#version 330 core
layout(location=0) in vec3 pos; layout(location=1) in vec2 uv; layout(location=2) in float render;
uniform mat4 mvp; out vec2 vuv; flat out float vrender;
void main() { vuv = uv; vrender = render; gl_Position = mvp * vec4(pos, 1.0); }"""
ENHANCED_FS = """#version 330 core
in vec2 vuv; flat in float vrender;
uniform sampler2D colourMap; uniform sampler2D lightMap; uniform int hasLight;
uniform float gain; out vec4 frag;""" + _SHOWN + """
void main() {
  float s = shownBy(vrender);
  if (!drawnIn(s)) discard;
  vec4 c = texture(colourMap, vuv);
  if (c.a < 0.02) discard;
  vec3 l = hasLight == 1 ? texture(lightMap, vuv).rgb * gain : vec3(1.0);
  frag = vec4(min(c.rgb * l, vec3(1.0)), c.a * s);
}"""
CLASSIC_VS = """#version 330 core
layout(location=0) in vec3 pos; layout(location=1) in vec2 uv; layout(location=2) in vec3 nrm;
layout(location=3) in float pal; layout(location=4) in float render;
uniform mat4 mvp; out vec2 vuv; out vec3 vn; flat out float vpal; flat out float vrender;
void main() { vuv = uv; vn = nrm; vpal = pal; vrender = render; gl_Position = mvp * vec4(pos, 1.0); }"""
CLASSIC_FS = """#version 330 core
in vec2 vuv; in vec3 vn; flat in float vpal; flat in float vrender;
uniform sampler2D indexMap; uniform sampler2D paletteMap;
uniform vec3 ambient; uniform vec3 lightDir[3]; uniform vec3 lightCol[3];
uniform int uvCount; uniform vec4 uvCanvas[32]; uniform vec2 uvShift[32];
uniform int paletteRow[16];
out vec4 frag;""" + _SHOWN + """
void main() {
  float s = shownBy(vrender);
  if (!drawnIn(s)) discard;
  vec2 t = vuv;
  for (int i = 0; i < uvCount; i++) {
    vec4 r = uvCanvas[i];
    if (t.x >= r.x && t.x < r.z && t.y >= r.y && t.y < r.w) { t += uvShift[i]; break; }
  }
  float index = texture(indexMap, t).r * 255.0;
  vec4 c = texelFetch(paletteMap, ivec2(int(index + 0.5), paletteRow[int(vpal + 0.5)]), 0);
  if (c.a < 0.5) discard;
  vec3 light = vec3(1.0);
  if (((int(vrender + 0.5) >> 15) & 1) == 0) {
    vec3 n = normalize(vn);
    light = ambient;
    for (int i = 0; i < 3; i++) light += lightCol[i] * max(dot(n, lightDir[i]), 0.0);
  }
  frag = vec4(min(c.rgb * light, vec3(1.0)), s);
}"""
FLAT_VS = """#version 330 core
layout(location=0) in vec3 pos; layout(location=1) in vec4 col; layout(location=2) in float render;
uniform mat4 mvp; out vec4 vcol; flat out float vrender;
void main() { vcol = col; vrender = render; gl_Position = mvp * vec4(pos, 1.0); }"""
FLAT_FS = """#version 330 core
in vec4 vcol; flat in float vrender; out vec4 frag;""" + _SHOWN + """
void main() {
  float s = shownBy(vrender);
  if (!drawnIn(s)) discard;
  frag = vec4(vcol.rgb, vcol.a * s); }"""


class Camera:
    """
    Where the map is seen from: `yaw`, the camera's place around the map in
    the files' ground plane (225 is the south-west corner), `pitch` above
    the ground, `zoom`, and `pan` in screen units.
    """

    def __init__(self, yaw=225.0, pitch=ms.LOW_PITCH, zoom=1.0, pan=(0.0, 0.0)):
        self.yaw, self.pitch, self.zoom, self.pan = yaw, pitch, zoom, pan

    def copy(self) -> "Camera":
        return Camera(self.yaw, self.pitch, self.zoom, self.pan)


class _Upload:
    """A batch on the graphics card: its buffer, its colour picture's frames, its lighting."""

    def __init__(self, batch, vbo, colours, light):
        self.batch, self.vbo, self.colours, self.light = batch, vbo, colours, light


#: Every renderer made, so what they hold on the graphics card is freed while
#: their contexts still exist, whichever way the program ends.
_LIVE = weakref.WeakSet()


@atexit.register
def _close_all() -> None:
    for renderer in list(_LIVE):
        try:
            renderer.close()
        except RuntimeError:
            pass                        # Qt's side is already gone


class MapRenderer:
    def __init__(self):
        _LIVE.add(self)
        self.error: Optional[str] = None
        self.ctx = None
        self.surface = None
        self.gl = None
        self.fbo = None
        self.fbo_size = (0, 0)
        self.scene: Optional[ms.Scene] = None
        self._uploaded = []          # _Upload per batch
        self._grid = {}
        self.index_tex = self.palette_tex = None

    # -- the context ------------------------------------------------------
    def ensure_context(self) -> bool:
        if self.ctx is not None:
            return True
        if self.error:
            return False
        try:
            from PySide6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram, QOpenGLVertexArrayObject
        except ImportError as exc:
            self.error = f"this copy of Mod Studio has no OpenGL module ({exc})"
            return False
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        fmt.setDepthBufferSize(24)
        ctx = QOpenGLContext()
        ctx.setFormat(fmt)
        if not ctx.create():
            self.error = "the graphics driver could not start OpenGL 3.3"
            return False
        got = ctx.format().version()
        if got < (3, 3):
            self.error = f"the graphics driver offers OpenGL {got[0]}.{got[1]}, and maps need 3.3"
            return False
        surface = QOffscreenSurface()
        surface.setFormat(ctx.format())
        surface.create()
        if not ctx.makeCurrent(surface):
            self.error = "the graphics driver would not draw off screen"
            return False
        self.ctx, self.surface, self.gl = ctx, surface, ctx.functions()
        self.programs = {}
        for name, (vs, fs) in {"enhanced": (ENHANCED_VS, ENHANCED_FS),
                               "classic": (CLASSIC_VS, CLASSIC_FS),
                               "flat": (FLAT_VS, FLAT_FS)}.items():
            program = QOpenGLShaderProgram()
            ok = (program.addShaderFromSourceCode(QOpenGLShader.Vertex, vs)
                  and program.addShaderFromSourceCode(QOpenGLShader.Fragment, fs)
                  and program.link())
            if not ok:
                self.error = f"a shader would not build: {program.log()[:300]}"
                self.ctx = None
                return False
            self.programs[name] = program
        self.vao = QOpenGLVertexArrayObject()
        self.vao.create()
        self.vao.bind()
        return True

    def make_current(self) -> bool:
        return self.ensure_context() and self.ctx.makeCurrent(self.surface)

    # -- the scene ------------------------------------------------------------
    def set_scene(self, scene: Optional[ms.Scene]) -> None:
        if not self.make_current():
            return
        self._release()
        self.scene = scene
        if scene is None:
            return
        for batch in scene.batches:
            vbo = self._buffer(batch.floats)
            colours, light = [], None
            if batch.kind == ms.ENHANCED:
                colours = [self._texture(image, mipmaps=True)
                           for image in (batch.frames or [batch.colour])]
                light = self._texture(batch.light, mipmaps=True) if batch.light else None
            self._uploaded.append(_Upload(batch, vbo, colours, light))
        if scene.look == ms.CLASSIC:
            from PySide6.QtOpenGL import QOpenGLTexture
            image = QImage(scene.classic_indices, 256, 1024, 256, QImage.Format_Grayscale8).copy()
            self.index_tex = QOpenGLTexture(image, QOpenGLTexture.DontGenerateMipMaps)
            self.index_tex.setMinificationFilter(QOpenGLTexture.Nearest)
            self.index_tex.setMagnificationFilter(QOpenGLTexture.Nearest)
            self.palette_tex = self._texture(scene.classic_palette, mipmaps=False, nearest=True)

    def _buffer(self, floats):
        from PySide6.QtOpenGL import QOpenGLBuffer
        vbo = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        vbo.create()
        vbo.bind()
        raw = floats.tobytes()
        vbo.allocate(raw, len(raw))
        vbo.release()
        return vbo

    def _texture(self, image, mipmaps=True, nearest=False):
        from PySide6.QtOpenGL import QOpenGLTexture
        rgba = image.convert("RGBA")
        q = QImage(rgba.tobytes(), rgba.width, rgba.height, 4 * rgba.width,
                   QImage.Format_RGBA8888).copy()
        texture = QOpenGLTexture(q, QOpenGLTexture.GenerateMipMaps if mipmaps
                                 else QOpenGLTexture.DontGenerateMipMaps)
        if nearest:
            texture.setMinificationFilter(QOpenGLTexture.Nearest)
            texture.setMagnificationFilter(QOpenGLTexture.Nearest)
        else:
            texture.setMinificationFilter(QOpenGLTexture.LinearMipMapLinear if mipmaps
                                          else QOpenGLTexture.Linear)
            texture.setMagnificationFilter(QOpenGLTexture.Linear)
        texture.setWrapMode(QOpenGLTexture.ClampToEdge)
        return texture

    def _release(self) -> None:
        for up in self._uploaded:
            up.vbo.destroy()
            for t in up.colours + ([up.light] if up.light is not None else []):
                t.destroy()
        self._uploaded = []
        for name in ("index_tex", "palette_tex"):
            t = getattr(self, name, None)
            if t is not None:
                t.destroy()
                setattr(self, name, None)
        for vbo, _count, _mode in self._grid.values():
            vbo.destroy()
        self._grid = {}

    def set_grid(self, geometry: dict) -> None:
        """
        Replaces the named parts of the grid (`map_scene.grid_geometry`'s
        "fill" and "lines", `highlight_geometry`'s "hover" and "selected"),
        leaving the others: the pointer moving redraws one tile, not 512.
        """
        if not self.make_current():
            return
        for name, floats in geometry.items():
            old = self._grid.pop(name, None)
            if old is not None:
                old[0].destroy()
            if len(floats):
                mode = GL_LINES if name == "lines" else GL_TRIANGLES
                self._grid[name] = (self._buffer(floats), len(floats) // ms.GRID_STRIDE, mode)

    def close(self) -> None:
        """Frees what the graphics card holds. The renderer draws nothing after."""
        if self.ctx is not None and self.ctx.makeCurrent(self.surface):
            self._release()
            self.fbo = None
            self.scene = None
            self.ctx.doneCurrent()

    # -- what moves -------------------------------------------------------------
    def animates(self) -> bool:
        """Whether anything in the scene moves: a picture with frames, or a classic animation."""
        if self.scene is None:
            return False
        return (any(len(up.colours) > 1 for up in self._uploaded)
                or bool(self.scene.uv_animations or self.scene.palette_animations))

    def frames_at(self, seconds: float) -> tuple:
        """The frame each moving thing shows at `seconds`: a picture needs drawing again when it changes."""
        if self.scene is None:
            return ()
        out = [ms.enhanced_frame(len(up.colours), seconds) for up in self._uploaded
               if len(up.colours) > 1]
        out += [ms.frame_at(len(a.frames), a.duration, seconds, a.back_and_forth)
                for a in self.scene.uv_animations]
        out += [ms.frame_at(a.count, a.duration, seconds, a.back_and_forth)
                for a in self.scene.palette_animations]
        return tuple(out)

    # -- the camera -------------------------------------------------------------
    #: Room left round the map at zoom 1, as a share of what it needs.
    FRAME_MARGIN = 1.02

    def _view(self, camera: Camera) -> tuple:
        """The view matrix for a camera, and how far the drawing reaches from its middle."""
        frame = self.scene.frame if self.scene else ((0, 0, 0), (1, 1, 1))
        bounds = self.scene.bounds if self.scene else frame
        (x0, y0, z0), (x1, y1, z1) = frame
        centre = QVector3D((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
        # Far enough out that nothing drawn is behind the camera: the frame
        # is the map, but the enhanced border and shadow reach past it.
        reach = max(math.dist((centre.x(), centre.y(), centre.z()), (x, y, z))
                    for x in (bounds[0][0], bounds[1][0]) for y in (bounds[0][1], bounds[1][1])
                    for z in (bounds[0][2], bounds[1][2])) + 1.0
        az, el = math.radians(camera.yaw), math.radians(camera.pitch)
        # The camera's place in the files' ground plane, turned into world
        # space (x is the files' -x).
        direction = QVector3D(-math.cos(az) * math.cos(el), math.sin(el), math.sin(az) * math.cos(el))
        eye = centre + direction * (reach * 2)
        up = QVector3D(0, 1, 0) if camera.pitch < 89 else QVector3D(math.cos(az), 0, -math.sin(az))
        view = QMatrix4x4()
        view.lookAt(eye, centre, up)
        return view, reach

    def half_height(self, camera: Camera, aspect: float = 1.0) -> float:
        """
        Half the picture's height, in world units, at the camera's zoom.

        At zoom 1 the whole map fits a picture `aspect` (width over height)
        in shape from ANY side and height, so turning or tilting it never
        changes its size - only the zoom does. The box round the map, seen
        from anywhere, is at most its diagonal across the ground wide and
        its full diagonal tall.
        """
        (x0, y0, z0), (x1, y1, z1) = self.scene.frame if self.scene else ((0, 0, 0), (1, 1, 1))
        ground = math.hypot(x1 - x0, z1 - z0)
        whole = math.hypot(ground, y1 - y0)
        fit = max(whole / 2, ground / 2 / max(aspect, 0.05), 1.0) * self.FRAME_MARGIN
        return fit / max(camera.zoom, 0.05)

    def matrices(self, camera: Camera, width: int, height: int) -> tuple:
        view, reach = self._view(camera)
        aspect = width / max(height, 1)
        half = self.half_height(camera, aspect)
        px, py = camera.pan
        proj = QMatrix4x4()
        proj.ortho(-half * aspect - px, half * aspect - px, -half + py, half + py,
                   reach * 0.5, reach * 3.5)
        return proj, view

    # -- drawing ----------------------------------------------------------------
    def render(self, camera: Camera, width: int, height: int, show_grid=True,
               background=(0.10, 0.105, 0.12), seconds: float = 0.0) -> Optional[QImage]:
        """The map from `camera`, `seconds` into its animations."""
        if not self.make_current():
            return None
        from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat
        width, height = max(1, int(width)), max(1, int(height))
        if self.fbo is None or self.fbo_size != (width, height):
            fmt = QOpenGLFramebufferObjectFormat()
            fmt.setAttachment(QOpenGLFramebufferObject.CombinedDepthStencil)
            fmt.setSamples(4)
            self.fbo = QOpenGLFramebufferObject(width, height, fmt)
            self.fbo_size = (width, height)
        gl = self.gl
        self.fbo.bind()
        gl.glViewport(0, 0, width, height)
        gl.glClearColor(background[0], background[1], background[2], 1.0)
        gl.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        gl.glEnable(GL_DEPTH_TEST)
        gl.glDepthFunc(GL_LEQUAL)
        gl.glEnable(GL_BLEND)
        gl.glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ZERO, GL_ONE)
        if self.scene is not None:
            proj, view = self.matrices(camera, width, height)
            mvp = proj * view
            weights = ms.corner_weights(camera.yaw)
            solid = [u for u in self._uploaded if not u.batch.see_through]
            clear = [u for u in self._uploaded if u.batch.see_through]
            for up in solid:
                self._draw_batch(up, mvp, seconds, weights, SOLID)
            # Blended, over what is behind them and under what is in front.
            gl.glDepthMask(False)
            for up in clear:
                self._draw_batch(up, mvp, seconds, weights, SEE_THROUGH)
            if any(0.0 < w < 1.0 for w in weights):
                for up in solid:
                    self._draw_batch(up, mvp, seconds, weights, FADING)
            gl.glDepthMask(True)
            if show_grid and self._grid:
                flat = self.programs["flat"]
                flat.bind()
                flat.setUniformValue("mvp", mvp)
                # The grid is never left out.
                flat.setUniformValue("cornerWeight", QVector4D(0, 0, 0, 0))
                flat.setUniformValue1i("drawPass", SOLID)
                gl.glDepthMask(False)
                for name in ("fill", "lines"):
                    if name in self._grid:
                        self._draw(self._grid[name], flat, (3, 4))
                gl.glDisable(GL_DEPTH_TEST)
                for name in ("selected", "hover"):
                    if name in self._grid:
                        self._draw(self._grid[name], flat, (3, 4))
                gl.glEnable(GL_DEPTH_TEST)
                gl.glDepthMask(True)
        self.fbo.release()
        return self.fbo.toImage()

    def _draw_batch(self, up: _Upload, mvp, seconds: float, weights: tuple, pass_: int) -> None:
        batch = up.batch
        if batch.kind == ms.ENHANCED:
            p = self.programs["enhanced"]
            p.bind()
            p.setUniformValue("mvp", mvp)
            p.setUniformValue1f("gain", 2.0)
            p.setUniformValue1i("colourMap", 0)
            p.setUniformValue1i("lightMap", 1)
            up.colours[ms.enhanced_frame(len(up.colours), seconds)].bind(0)
            # Unit 1 always holds a picture of this map: without a lighting
            # picture, the colour one, which the shader then doesn't read.
            (up.light if up.light is not None else up.colours[0]).bind(1)
            p.setUniformValue1i("hasLight", 1 if up.light is not None else 0)
        elif batch.kind == ms.CLASSIC:
            p = self.programs["classic"]
            p.bind()
            p.setUniformValue("mvp", mvp)
            p.setUniformValue1i("indexMap", 0)
            p.setUniformValue1i("paletteMap", 1)
            self.index_tex.bind(0)
            self.palette_tex.bind(1)
            self._classic_animations(p, seconds)
            lights = self.scene.lights
            if lights is not None:
                a = lights.ambient
                p.setUniformValue("ambient", QVector3D(a[0] / 128, a[1] / 128, a[2] / 128))
                for i in range(3):
                    d = lights.directions[i]
                    v = QVector3D(-d[0], -d[1], d[2])
                    if v.length() > 0:
                        v.normalize()
                    r, g, b = lights.colours[i]
                    p.setUniformValue(f"lightDir[{i}]", v)
                    p.setUniformValue(f"lightCol[{i}]", QVector3D(r / 4096, g / 4096, b / 4096))
        else:
            p = self.programs["flat"]
            p.bind()
            p.setUniformValue("mvp", mvp)
        p.setUniformValue("cornerWeight", QVector4D(*weights))
        p.setUniformValue1i("drawPass", pass_)
        self._draw((up.vbo, batch.count, GL_TRIANGLES), p, batch.layout)

    def _classic_animations(self, p, seconds: float) -> None:
        """The texture's moving rectangles and the palettes' frames, `seconds` in."""
        uvs = self.scene.uv_animations[:UV_ANIMATIONS]
        p.setUniformValue1i("uvCount", len(uvs))
        for i, a in enumerate(uvs):
            x, y, w, h = a.canvas
            fx, fy = a.frames[ms.frame_at(len(a.frames), a.duration, seconds, a.back_and_forth)]
            p.setUniformValue(f"uvCanvas[{i}]", QVector4D(x / 256, y / 1024, (x + w) / 256, (y + h) / 1024))
            p.setUniformValue(f"uvShift[{i}]", QVector2D((fx - x) / 256, (fy - y) / 1024))
        rows = list(range(16))
        for a in self.scene.palette_animations:
            rows[a.palette] = 16 + a.start + ms.frame_at(a.count, a.duration, seconds, a.back_and_forth)
        for i, row in enumerate(rows):
            p.setUniformValue1i(f"paletteRow[{i}]", row)

    def _draw(self, item, program, layout) -> None:
        """
        One draw of a buffer whose vertices are `layout` floats per
        attribute. The arrays it turns on are off again after it (see the
        module's notes): none is ever left on for the next draw to read.
        """
        vbo, count, mode = item
        vbo.bind()
        stride = sum(layout) * 4
        offset = 0
        for location, n in enumerate(layout):
            program.enableAttributeArray(location)
            program.setAttributeBuffer(location, GL_FLOAT, offset, n, stride)
            offset += n * 4
        self.gl.glDrawArrays(mode, 0, count)
        for location in range(len(layout)):
            program.disableAttributeArray(location)
        vbo.release()

    # -- picking ----------------------------------------------------------------
    def project(self, point, camera: Camera, width: int, height: int) -> tuple:
        proj, view = self.matrices(camera, width, height)
        v = (proj * view).map(QVector3D(*point))
        return ((v.x() + 1) / 2 * width, (1 - v.y()) / 2 * height)

    def _ray(self, x: float, y: float, camera: Camera, width: int, height: int):
        """The ray from the camera through a point of the picture: (origin, direction)."""
        proj, view = self.matrices(camera, width, height)
        inverse, ok = (proj * view).inverted()
        if not ok:
            return None
        nx, ny = x / width * 2 - 1, 1 - y / height * 2
        a = inverse.map(QVector3D(nx, ny, -1))
        b = inverse.map(QVector3D(nx, ny, 1))
        return (a.x(), a.y(), a.z()), (b.x() - a.x(), b.y() - a.y(), b.z() - a.z())

    def pick(self, x: float, y: float, camera: Camera, width: int, height: int, tiles) -> Optional[tuple]:
        """
        The tile under a point of the picture: the nearest the ray from the
        camera crosses, as `(x, z, level)`. `tiles` are the tiles as edited.
        """
        if self.scene is None:
            return None
        ray = self._ray(x, y, camera, width, height)
        if ray is None:
            return None
        origin, direction = ray
        best = None
        for tile in tiles:
            if not ms.shows(tile):
                continue
            c = ms.tile_corners(tile)
            for tri in ((0, 1, 2), (0, 2, 3)):
                hit = ray_triangle(origin, direction, c[tri[0]], c[tri[1]], c[tri[2]])
                if hit is not None and (best is None or hit < best[0]):
                    best = (hit, (tile.x, tile.z, tile.level))
        return best[1] if best else None

    def pick_batch(self, x: float, y: float, camera: Camera, width: int, height: int):
        """
        The batch drawn at a point of the picture: the nearest polygon the
        ray crosses among those showing more than half from where the
        camera is, or None. An enhanced batch's `group` says which pictures
        it is drawn with.
        """
        if self.scene is None:
            return None
        ray = self._ray(x, y, camera, width, height)
        if ray is None:
            return None
        origin, direction = ray
        weights = ms.corner_weights(camera.yaw)
        best = None
        for batch in self.scene.batches:
            stride = sum(batch.layout)
            f = batch.floats
            for start in range(0, len(f) - 3 * stride + 1, 3 * stride):
                if ms.shown(f[start + stride - 1] + 0.5, weights) < 0.5:
                    continue
                a = (f[start], f[start + 1], f[start + 2])
                b = (f[start + stride], f[start + stride + 1], f[start + stride + 2])
                c = (f[start + 2 * stride], f[start + 2 * stride + 1], f[start + 2 * stride + 2])
                hit = ray_triangle(origin, direction, a, b, c)
                if hit is not None and (best is None or hit < best[0]):
                    best = (hit, batch)
        return best[1] if best else None


def ray_triangle(o, d, a, b, c) -> Optional[float]:
    """Möller-Trumbore: how far along the ray it meets the triangle, or None."""
    e1 = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    e2 = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    p = (d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0])
    det = e1[0] * p[0] + e1[1] * p[1] + e1[2] * p[2]
    if abs(det) < 1e-9:
        return None
    inv = 1.0 / det
    s = (o[0] - a[0], o[1] - a[1], o[2] - a[2])
    u = (s[0] * p[0] + s[1] * p[1] + s[2] * p[2]) * inv
    if u < 0 or u > 1:
        return None
    q = (s[1] * e1[2] - s[2] * e1[1], s[2] * e1[0] - s[0] * e1[2], s[0] * e1[1] - s[1] * e1[0])
    v = (d[0] * q[0] + d[1] * q[1] + d[2] * q[2]) * inv
    if v < 0 or u + v > 1:
        return None
    t = (e2[0] * q[0] + e2[1] * q[1] + e2[2] * q[2]) * inv
    return t if t >= 0 else None
