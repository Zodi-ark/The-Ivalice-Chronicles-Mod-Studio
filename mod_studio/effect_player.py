"""
Plays an effect file (`effect_files.py`) frame by frame: where each
particle is and which picture it shows, where the camera is, how the
screen and the units and map are coloured, and when sounds start. Asked
for by Zodi on 12 October: "Do it completly now the emitters, timing,
camera, and sound as well as everything else that is possible".

The rules are the ExMateria effects addon's, ported line by line
(timbermania, MIT, Copyright (c) 2026 timbermania -
github.com/timbermania/TacticsTemplateG, branch `pr-upstream-wip`,
`addons/exmateria_effects`: `cast/EffectTimeline.gd`, `cast/EffectPhase.gd`,
`subsystem/PhaseBlock.gd`, `subsystem/ParticleSubsystem.gd`,
`particles/ActiveEmitter.gd`, `particles/ParticlePhysics.gd`,
`particles/ParticleAnimator.gd`, `subsystem/CameraSubsystem.gd`,
`subsystem/ScreenSubsystem.gd`, `subsystem/PaletteSubsystem.gd`, and from
its `exmateria_schema` the colour model `ColorStack.gd` and
`ColorRecipe.gd`, and from `exmateria_platform` the sound walker
`EffectSoundController.gd` and `EffectSoundResolver.gd`). Its authors
measured them against the PlayStation game.

- **Time**: 30 frames a second. An effect has three parts: before the
  targets ("phase 1"), one for each target, started `target_gap` frames
  apart, and after them ("phase 2"), which starts `after_delay` frames
  after the last target's. Slow motion stretches a frame (the time scale).
- **Particles**: each part's five lanes of keyframes say which emitter
  makes particles on each frame; an emitter's curves are read at how many
  frames its lane has been making them. Particles fly, slow, fall and
  home in as `ParticlePhysics.gd` has it, play their animation, and leave
  other emitters' particles behind when they die or while they live.
- **Camera**: angle, position and zoom move towards the caster, target,
  map centre or fixed values, jumping, easing or shaking.
- **Colour**: the screen's backdrop and the map's, caster's and target's
  colours are layers faded in and out over the keyframes' times.
- **Sound**: the moments each sound lane starts a sound, and which sound,
  after the effect's containers have had their say.

Positions are in tiles, x and z along the map's grid and y up, measured
from where the effect is played (the caster); camera positions are
PlayStation units (28 a tile, y down) as the game keeps them.

Not here: the special drawings some effects make in code ("callbacks":
rings, tubes, grids), which ExMateria draws for a few of them; a callback
moment is reported instead.

Pure Python: nothing here imports Qt.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional

from . import effect_files as ef

#: Frames a second.
FPS = 30
#: Particles at once (ExMateria's EffectInstance pool).
POOL = 512
#: The longest effect played: two minutes, as ExMateria's end model.
FRAME_CAP = 3600
#: The part names, in ExMateria's order.
BEFORE, EACH, AFTER = "before", "each", "after"
PARTS = (BEFORE, EACH, AFTER)
#: The camera's pose before an effect moves it: (pitch, yaw, roll), 4096 a turn.
DEFAULT_ANGLES = (302.0, 3584.0, 0.0)
DEFAULT_ZOOM = 4096.0
#: Slow motion: the usual pace.
BASE_PACING = 2
EPSILON = 0.00001


# =============================================================================
# Small vectors
# =============================================================================

def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _length(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _axis_rotation(axis, angle):
    """Godot's `Basis(axis, angle)`: a right-handed rotation, as three rows."""
    x, y, z = axis
    c, s = math.cos(angle), math.sin(angle)
    t = 1.0 - c
    return ((t * x * x + c, t * x * y - s * z, t * x * z + s * y),
            (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
            (t * x * z - s * y, t * y * z + s * x, t * z * z + c))


def _matmul(a, b):
    return tuple(tuple(sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)) for r in range(3))


def _apply(m, v):
    return (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2])


RIGHT, UP, FORWARD, DOWN = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0), (0.0, -1.0, 0.0)


def angle_to_direction(ax: float, ay: float, az: float) -> tuple:
    """Where a launch at these angles goes: straight down rotated about the
    forward axis, then up, then right (`ParticlePhysics.angle_to_direction`)."""
    basis = _matmul(_axis_rotation(RIGHT, ax),
                    _matmul(_axis_rotation(UP, ay), _axis_rotation(FORWARD, az)))
    d = _apply(basis, DOWN)
    length = _length(d)
    return _mul(d, 1.0 / length) if length * length > 0.001 else DOWN


def rotate_y(v, angle: float):
    if abs(angle) < 0.001:
        return v
    c, s = math.cos(angle), math.sin(angle)
    return (v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c)


# =============================================================================
# Particles
# =============================================================================

class Particle:
    __slots__ = ("position", "velocity", "acceleration", "drag", "inertia", "weight",
                 "homing_strength", "homing_target", "homing_curve", "homing_arrival",
                 "age", "lifetime", "complete", "held", "active", "emitter", "child_death",
                 "child_mid", "anim_index", "anim_time", "offset", "group_offset", "frameset",
                 "depth", "anchors", "target")

    def __init__(self, position, velocity, lifetime, emitter, child_death, child_mid):
        self.position, self.velocity, self.lifetime = position, velocity, lifetime
        self.emitter, self.child_death, self.child_mid = emitter, child_death, child_mid
        self.acceleration = self.drag = (0.0, 0.0, 0.0)
        self.inertia, self.weight = 1.0, 0.0
        self.homing_strength, self.homing_target = 0.0, (0.0, 0.0, 0.0)
        self.homing_curve, self.homing_arrival = -1, 0.0
        self.age = 0
        self.complete = self.held = False
        self.active = True
        self.anim_index = self.anim_time = 0
        self.offset = (0, 0)
        self.group_offset = self.frameset = self.depth = 0
        self.anchors = None
        self.target = 0

    def dead(self) -> bool:
        if self.lifetime == -1:
            return self.complete
        return self.age >= self.lifetime


@dataclass
class Anchors:
    """Where an emitter's particles can start from, as offsets from the
    effect's place (tiles, y up)."""
    world: tuple = (0.0, 0.0, 0.0)
    cursor: tuple = (0.0, 0.0, 0.0)
    origin: tuple = (0.0, 0.0, 0.0)
    target: tuple = (0.0, 0.0, 0.0)
    camera: tuple = (0.0, 0.0, 0.0)

    def start(self, mode: str):
        """ActiveEmitter._get_anchor_offset: a parent anchor is the effect's own place."""
        return {"cursor": self.cursor, "origin": self.origin, "target": self.target,
                "parent": (0.0, 0.0, 0.0), "camera": self.camera}.get(mode, self.world)

    def homing(self, mode: str, child: bool = False):
        """ActiveEmitter._get_target_anchor (a child homes on the target for "parent")."""
        if mode == "parent":
            return self.target if child else (0.0, 0.0, 0.0)
        return {"cursor": self.cursor, "origin": self.origin, "target": self.target,
                "camera": self.camera}.get(mode, self.world)


class Curves:
    def __init__(self, effect: ef.EffectFile):
        self.values = [[v / 255.0 for v in curve] for curve in effect.curves]

    def get(self, index: int):
        return self.values[index] if 0 <= index < len(self.values) else None

    @staticmethod
    def sample(curve, frame: int) -> float:
        return curve[frame % len(curve)] if curve else 0.0


def _simple(start, end, curve, frame):
    if curve is None:
        return start
    t = Curves.sample(curve, frame)
    return start + (end - start) * t


def _vec(pair, curve, frame):
    if curve is None:
        return pair[0]
    return _lerp(pair[0], pair[1], Curves.sample(curve, frame))


def _range(four, curve, frame, rng):
    min_s, max_s, min_e, max_e = four
    if curve is None:
        return rng.uniform(min_s, max_s)
    t = Curves.sample(curve, frame)
    lo, hi = min_s + (min_e - min_s) * t, max_s + (max_e - max_s) * t
    return rng.uniform(lo, hi)


def _vec_range(four, curve, frame, rng):
    min_s, max_s, min_e, max_e = four
    if curve is None:
        return tuple(rng.uniform(min_s[i], max_s[i]) for i in range(3))
    t = Curves.sample(curve, frame)
    lo, hi = _lerp(min_s, min_e, t), _lerp(max_s, max_e, t)
    return tuple(rng.uniform(lo[i], hi[i]) for i in range(3))


def _round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5)) if value >= 0 else -int(math.floor(-value + 0.5))


class _Animator:
    """ParticleAnimator: each animation unrolled into one entry a frame."""

    def __init__(self, effect: ef.EffectFile):
        self.baked = []
        for steps in effect.animations:
            frames, offset = [], (0, 0)
            for step in steps:
                if step[0] == "offset":
                    offset = (step[1], step[2])
                elif step[0] == "move":
                    offset = (offset[0] + step[1], offset[1] + step[2])
                elif step[0] == "frame":
                    _kind, frameset, duration, depth = step
                    shown = max(1, (duration + 1) >> 1)
                    for i in range(shown):
                        frames.append((frameset, depth, offset, duration == 0 and i == shown - 1))
            self.baked.append(frames)

    def tick(self, p: Particle) -> None:
        if p.held:
            return
        if p.anim_index < 0 or p.anim_index >= len(self.baked):
            return
        frames = self.baked[p.anim_index]
        if not frames:
            return
        frameset, depth, offset, terminal = frames[p.anim_time]
        p.offset = offset
        p.frameset = frameset + p.group_offset
        p.depth = depth
        if terminal:
            if p.lifetime == -1:
                p.complete = True
            else:
                p.held = True
            return
        p.anim_time += 1
        if p.anim_time >= len(frames):
            p.anim_time = 0


class _Lane:
    __slots__ = ("lane", "key", "remaining", "counter", "finished")


class _Block:
    """PhaseBlock: one part's particle lanes, keyframe 0 skipped."""

    def __init__(self, lanes: list, events: list, part: str, target: int, start: int):
        self.states = []
        self.events, self.part, self.target, self.start = events, part, target, start
        self.frame = 0
        self.last_active = 0
        self.pending_start = []
        for lane in sorted(lanes, key=lambda item: item.index):
            state = _Lane()
            state.lane, state.key, state.counter = lane, 1, 0
            if lane.last < 1:
                state.finished, state.remaining = True, 0
            else:
                state.finished = False
                state.remaining = lane.keys[1][0]
                if lane.keys[1][2]:
                    self.pending_start.append(lane.keys[1][2])
            self.states.append(state)
        for lane in lanes:
            for i in range(min(lane.last, len(lane.keys) - 1), 0, -1):
                if lane.keys[i][1] != 0:
                    self.last_active = max(self.last_active, lane.keys[i][0])
                    break

    def advance(self) -> list:
        requests = []
        for state in self.states:
            if state.finished:
                continue
            time, emitter_id, action = state.lane.keys[state.key]
            if emitter_id != 0:
                requests.append((emitter_id - 1, state.counter, state.lane.index, action,
                                 state.remaining))
                state.counter += 1
            state.remaining -= 1
            if state.remaining <= 0:
                state.key += 1
                if state.key > state.lane.last or state.key >= len(state.lane.keys):
                    state.finished = True
                    continue
                now, before = state.lane.keys[state.key], state.lane.keys[state.key - 1]
                state.remaining = now[0] - before[0]
                state.counter = 0
                if now[2]:
                    self.events.append(("action", now[2], self.part, self.target, state.lane.index,
                                        self.start + self.frame))
        self.frame += 1
        return requests

    def finished(self) -> bool:
        return all(state.finished for state in self.states)


# =============================================================================
# Colour (ColorRecipe / ColorStack)
# =============================================================================

class Recipe:
    """One colour step: `c * scale + bias` (affine), or a mix to grey and an
    added amount (luma); from the colour so far or from the base colour."""
    __slots__ = ("scale", "bias", "from_base", "luma_div", "luma_delta", "luma_from_base",
                 "param_max")

    def __init__(self, scale=(1.0, 1.0, 1.0), bias=(0.0, 0.0, 0.0), from_base=False,
                 luma_div=0, luma_delta=(0, 0, 0), luma_from_base=True, param_max=31):
        self.scale, self.bias, self.from_base = scale, bias, from_base
        self.luma_div, self.luma_delta, self.luma_from_base = luma_div, luma_delta, luma_from_base
        self.param_max = param_max

    def reads_base(self) -> bool:
        return self.from_base if self.luma_div == 0 else self.luma_from_base

    def apply(self, base, current):
        if self.luma_div == 0:
            source = base if self.from_base else current
            return tuple(source[i] * self.scale[i] + self.bias[i] for i in range(3))
        source = base if self.luma_from_base else current
        m = float(self.param_max)
        r, g, b = (_round_half_up(min(1.0, max(0.0, channel)) * m) for channel in source)
        luma = (2 * r + 3 * g + b) // self.luma_div
        return tuple(min(self.param_max, max(0, luma + self.luma_delta[i])) / m for i in range(3))


def _signed_byte(value: int) -> int:
    value &= 0xFF
    return value - 256 if value >= 128 else value


def recipe_for_mode(mode: int, r: int, g: int, b: int, param_max: int = 31,
                    double: bool = False) -> Recipe:
    """ColorRecipe.from_mode: the game's 11 colour modes as recipes."""
    param_max = max(1, param_max)
    delta = [_signed_byte(r), _signed_byte(g), _signed_byte(b)]
    if double:
        delta = [d * 2 for d in delta]
    normal = tuple(d / float(param_max) for d in delta)
    if mode == 0:
        return Recipe(bias=normal)
    if mode in (4, 9):
        return Recipe(bias=normal, from_base=True)
    if mode == 1:
        return Recipe(scale=(0.5, 0.5, 0.5), bias=normal)
    if mode == 5:
        return Recipe(scale=(0.5, 0.5, 0.5), bias=normal, from_base=True)
    if mode in (8, 10):
        return Recipe()
    if mode == 7:
        return Recipe(luma_div=12, luma_delta=tuple(delta), luma_from_base=True, param_max=param_max)
    if mode == 6:
        return Recipe(luma_div=6, luma_delta=tuple(delta), luma_from_base=True, param_max=param_max)
    if mode == 3:
        return Recipe(luma_div=12, luma_delta=tuple(delta), luma_from_base=False, param_max=param_max)
    if mode == 2:
        return Recipe(luma_div=6, luma_delta=tuple(delta), luma_from_base=False, param_max=param_max)
    return Recipe()


def ramp_frames(time: int) -> int:
    """How many frames a colour step of this `Time` fades over (the two DDA tables)."""
    if time <= 0:
        return 0
    if time < 4:
        return 8
    return 32 * (time >> 2)


def _progress(elapsed: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return min(1.0, max(0.0, elapsed / float(total)))


class _Layer:
    __slots__ = ("recipe", "start", "duration", "restoring", "restore_start", "restore_dur",
                 "restore_from", "shadowed")

    def __init__(self, recipe, start, duration):
        self.recipe, self.start, self.duration = recipe, start, duration
        self.restoring, self.restore_start, self.restore_dur = False, 0, 0
        self.restore_from, self.shadowed = 1.0, False

    def progress(self, now: int) -> float:
        if now < self.start:
            return 0.0
        if self.restoring and now >= self.restore_start:
            return self.restore_from * (1.0 - _progress(now - self.restore_start, self.restore_dur))
        return _progress(now - self.start, self.duration)

    def expired(self, now: int) -> bool:
        return self.restoring and now >= self.restore_start + self.restore_dur

    def dormant(self, now: int) -> bool:
        return self.shadowed and now >= self.restore_start


class ColourStack:
    """ColorStack: colour layers over time, folded over a base colour."""

    def __init__(self, quantize: bool = False, param_max: int = 31):
        self.quantize, self.param_max = quantize, param_max
        self.layers = []

    def push_layer(self, recipe: Recipe, start: int, duration: int) -> None:
        self.layers.append(_Layer(recipe, start, duration))

    def push_op(self, mode, r, g, b, time, now, duration=-1, double=False) -> None:
        if duration < 0:
            duration = ramp_frames(time)
        if mode in (8, 10):
            self._restore(now, duration)
            return
        self.push_layer(recipe_for_mode(mode, r, g, b, self.param_max, double), now, duration)

    def _restore(self, now: int, duration: int) -> None:
        for i, layer in enumerate(self.layers):
            if layer.expired(now):
                continue
            layer.shadowed = self._shadowed(i, now)
            layer.restore_from = layer.progress(now)
            layer.restoring, layer.restore_start, layer.restore_dur = True, now, duration

    def _shadowed(self, index: int, now: int) -> bool:
        for upper in self.layers[index + 1:]:
            if upper.expired(now) or not upper.recipe.reads_base():
                continue
            if upper.progress(now) < 1.0:
                continue
            return True
        return False

    def fold(self, base, now: int) -> tuple:
        colour = tuple(base)
        for layer in self.layers:
            if layer.expired(now) or layer.dormant(now):
                continue
            p = layer.progress(now)
            if p <= 0.0:
                continue
            target = layer.recipe.apply(base, colour)
            colour = _lerp(colour, target, p)
        if self.quantize:
            q = float(max(1, self.param_max))
            colour = tuple(_round_half_up(min(1.0, max(0.0, c)) * q) / q for c in colour)
        return colour

    def busy_until(self) -> int:
        """The last frame any layer is still changing."""
        last = 0
        for layer in self.layers:
            last = max(last, layer.start + layer.duration)
            if layer.restoring:
                last = max(last, layer.restore_start + layer.restore_dur)
        return last


def _lane_window(lane) -> int:
    """How many of a colour lane's keyframes are played (index < last - 1)."""
    return min(len(lane.keys), max(0, lane.last - 1))


def screen_stack(effect: ef.EffectFile, starts: dict, bottom: bool = False) -> ColourStack:
    """ScreenSubsystem.build_stream: the backdrop's top (or bottom) colour."""
    stack = ColourStack(quantize=False, param_max=255)
    if effect.timeline is None:
        return stack
    for part in (BEFORE, EACH, AFTER):
        if part not in starts:
            continue
        lane = effect.timeline.screen.get(part)
        if lane is None:
            continue
        at = 0
        for key in lane.keys[:_lane_window(lane)]:
            duration = max(1, key.frames)
            now = starts[part] + at
            if key.blends:
                stack.push_op(key.mode, key.start[0], key.start[1], key.start[2], key.time, now,
                              duration, True)
            else:
                colour = key.end if bottom else key.start
                stack.push_layer(Recipe(scale=(0.0, 0.0, 0.0),
                                        bias=tuple(c / 255.0 for c in colour)), now, duration)
            at += duration
    return stack


def palette_stack(effect: ef.EffectFile, starts: dict, surface: str) -> ColourStack:
    """PaletteSubsystem.build_stream: "affected" (the map), "caster" or "target"."""
    stack = ColourStack(quantize=True, param_max=31)
    if effect.timeline is None:
        return stack
    for part in (BEFORE, EACH, AFTER):
        if part not in starts:
            continue
        lane = effect.timeline.palette.get(part, {}).get(surface)
        if lane is None:
            continue
        at = 0
        for key in lane.keys[:_lane_window(lane)]:
            if key.on:
                stack.push_op(key.mode, key.rgb[0], key.rgb[1], key.rgb[2], key.time,
                              starts[part] + at)
            at += max(1, key.frames)
    return stack


# =============================================================================
# Camera (CameraSubsystem)
# =============================================================================

SHAKES = ("shake fading", "shake")


class _Channel:
    """One of the camera's three channels: angle (3 numbers), position (3) or zoom (1)."""

    def __init__(self, value):
        self.state = ""
        self.value = value
        self.start = self.end = value
        self.frame = self.total = 0
        self.additive = self.amplitude = value


class Camera:
    """Where the effect puts the camera, frame by frame."""

    def __init__(self, effect: ef.EffectFile, before: int, gap: int, after: int,
                 targets: int, continuous: bool, rng: random.Random,
                 angles=DEFAULT_ANGLES, position=(0.0, 0.0, 0.0), zoom=DEFAULT_ZOOM):
        self.tables = effect.timeline.camera if effect.timeline else {}
        self.before, self.gap, self.after = before, gap, after
        self.targets = max(1, targets)
        self.continuous, self.rng = continuous, rng
        self.active = any(table.last > 0 for table in self.tables.values())
        self.saved_angles, self.saved_position, self.saved_zoom = tuple(angles), tuple(position), zoom
        self.angle = _Channel(tuple(angles))
        self.position = _Channel(tuple(position))
        self.zoom = _Channel(float(zoom))
        self.map_centre = (0.0, 0.0, 0.0)
        self.caster = tuple(position)
        self.target_positions = [tuple(position)]
        self.cursor = tuple(position)
        self.current_target = 0
        self.busy_until = 0

    def pose(self) -> tuple:
        return self.angle.value, self.position.value, self.zoom.value

    def last_keyframe_end(self) -> int:
        """The frame the effect's last camera keyframe ends on (the game waits for it)."""
        last = 0
        for part, table in self.tables.items():
            ends = [key.end_frame for key in table.keys[:table.last + 1]]
            if not ends or table.last <= 0:
                continue
            start = {BEFORE: 0, EACH: self.before + (self.targets - 1) * self.gap,
                     AFTER: self.after}[part]
            last = max(last, start + max(ends))
        return last

    def target_position(self):
        index = min(self.current_target, len(self.target_positions) - 1)
        return self.target_positions[index]

    def all_targets(self):
        points = self.target_positions
        return tuple(sum(p[i] for p in points) / len(points) for i in range(3))

    def advance(self, frame: int) -> None:
        if not self.active:
            return
        for channel, bit in ((self.angle, 1), (self.position, 2), (self.zoom, 4)):
            if channel.state == "":
                self._find_and_run(frame, bit)
        for channel, kind in ((self.angle, "angle"), (self.position, "position"), (self.zoom, "zoom")):
            if channel.state != "":
                self._step(channel, kind)
                self.busy_until = frame + 1

    def _find(self, frame: int, bit: int):
        table = self.tables.get(BEFORE)
        if frame < self.before and table is not None:
            for i in range(table.last + 1):
                key = table.keys[i]
                if key.command & bit and frame < key.end_frame:
                    return key, key.end_frame
        table = self.tables.get(EACH)
        if frame >= self.before and table is not None:
            if self.continuous:
                local = frame - self.before
                for i in range(table.last + 1):
                    key = table.keys[i]
                    if key.command & bit and local < key.end_frame:
                        return key, key.end_frame + self.before
            elif self.gap > 0:
                if frame < self.before + self.gap * self.targets:
                    elapsed = frame - self.before
                    index, local = elapsed // self.gap, elapsed % self.gap
                    self.current_target = index
                    for i in range(table.last + 1):
                        key = table.keys[i]
                        if key.command & bit and local < key.end_frame:
                            return key, key.end_frame + self.before + index * self.gap
        table = self.tables.get(AFTER)
        if frame >= self.after and table is not None:
            local = frame - self.after
            for i in range(table.last + 1):
                key = table.keys[i]
                if key.command & bit and local < key.end_frame:
                    return key, key.end_frame + self.after
        return None, 0

    def _find_and_run(self, frame: int, bit: int) -> None:
        key, end = self._find(frame, bit)
        if key is None or key.move == "none":
            return
        remaining = end - frame
        if remaining <= 1 and key.move != "jump":
            return
        remaining = max(1, remaining)
        if bit == 1:
            self._angle(key, remaining)
        elif bit == 2:
            self._position(key, remaining)
        else:
            self._zoom(key, remaining)

    def _facing_yaw(self) -> float:
        return math.floor(self.angle.value[1] / 512.0) * 512.0

    @staticmethod
    def _wrap(start, end):
        delta = math.fmod(end - start + 2048.0, 4096.0)
        if delta < 0:
            delta += 4096.0
        return start + delta - 2048.0

    def _angle(self, key, remaining) -> None:
        kf = tuple(float(v) for v in key.angle)
        now = self.angle.value
        saved = self.saved_angles
        source = key.source
        if source in ("target", "caster", "cursor", "effect centre", "all targets"):
            end = (now[0] + kf[0], self._facing_yaw() + kf[1], now[2] + kf[2])
        elif source == "offset":
            end = (kf[0], now[1] + kf[1], now[2] + kf[2])
        elif source == "direct":
            end = (kf[0], self._wrap(now[1], kf[1]), kf[2])
        elif source == "map":
            end = _add(now, kf)
        elif source == "saved":
            end = (saved[0] + kf[0], self._wrap(now[1], saved[1] + kf[1]), saved[2] + kf[2])
        elif source == "origin":
            end = (saved[0] + kf[0], now[1] + kf[1], now[2] + kf[2])
        else:
            end = kf
        if key.move in SHAKES:
            end = now
        self._begin(self.angle, key.move, remaining, kf, end)

    def _position(self, key, remaining) -> None:
        kf = tuple(float(v) for v in key.position)
        now = self.position.value
        source = key.source
        if source == "target":
            end = _add(self.target_position(), kf)
        elif source == "caster":
            end = _add(self.caster, kf)
        elif source == "direct":
            end = kf
        elif source == "map":
            end = _add(now, kf)
        elif source in ("saved", "origin"):
            end = _add(self.saved_position, kf)
        elif source == "effect centre":
            end = _add((self.map_centre[0], 0.0, self.map_centre[2]), kf)
        elif source == "all targets":
            end = _add(self.all_targets(), kf)
        elif source == "cursor":
            end = _add(self.cursor, kf)
        else:
            end = kf
        if key.move in SHAKES:
            end = now
        self._begin(self.position, key.move, remaining, kf, end)

    def _zoom(self, key, remaining) -> None:
        kf = float(key.zoom[0])
        now = self.zoom.value
        source = key.source
        if source == "map":
            end = now + kf
        elif source == "saved":
            end = self.saved_zoom + kf
        elif source in ("offset", "cursor"):
            return
        else:
            end = kf
        if key.move in SHAKES:
            end = now
        self._begin(self.zoom, key.move, remaining, kf, end)

    @staticmethod
    def _begin(channel, move, remaining, kf, end) -> None:
        channel.state, channel.frame, channel.total = move, 0, remaining
        channel.start, channel.end = channel.value, end
        if move == "add":
            channel.additive = kf
        elif move in SHAKES:
            channel.amplitude = kf

    def _step(self, channel, kind) -> None:
        channel.frame += 1
        t = channel.frame / float(max(1, channel.total))
        tuple_kind = kind != "zoom"

        def mix(a, b, k):
            return _lerp(a, b, k) if tuple_kind else a + (b - a) * k

        state = channel.state
        done = channel.frame >= channel.total
        if state == "jump":
            channel.value, channel.state = channel.end, ""
        elif state == "straight":
            channel.value = channel.end if done else mix(channel.start, channel.end, t)
        elif state == "ease":
            k = 0.5 - 0.5 * math.cos(math.pi * t)
            channel.value = channel.end if done else mix(channel.start, channel.end, k)
        elif state == "add":
            channel.value = _add(channel.value, channel.additive) if tuple_kind \
                else channel.value + channel.additive
        elif state in SHAKES:
            decay = 1.0 - t if state == "shake fading" else 1.0
            if tuple_kind:
                channel.value = tuple(channel.end[i] + self.rng.uniform(-channel.amplitude[i],
                                                                         channel.amplitude[i]) * decay
                                      for i in range(3))
            else:
                channel.value = channel.end + self.rng.uniform(-channel.amplitude, channel.amplitude) * decay
            if done:
                channel.value = channel.end
        else:
            channel.value, channel.state = channel.end, ""
        if done:
            channel.state = ""


# =============================================================================
# Sound (EffectSoundController / EffectSoundResolver)
# =============================================================================

class _SoundLane:
    def __init__(self, lane: ef.SoundLane, part: str, enforce_last: bool):
        self.keys, self.index, self.part = lane.keys, lane.index, part
        self.last, self.enforce_last = lane.last, enforce_last
        self.key = 0
        self.done = not self.keys
        self.left = self.keys[0][0] if not self.done else 0

    def advance(self) -> bool:
        self.key += 1
        if (self.enforce_last and self.key > self.last) or self.key >= len(self.keys):
            self.done = True
            return False
        self.left = self.keys[self.key][0]
        return True

    def sound(self) -> int:
        if self.done or not 0 <= self.key < len(self.keys):
            return 0
        return self.keys[self.key][1]


class SoundWalker:
    """When each sound starts: `(frame, part, lane, sound)`, the sound being
    the container's choice (`lookup_sound_effect`), not the keyframe's number."""

    def __init__(self, effect: ef.EffectFile, targets: int = 1):
        timeline = effect.timeline
        self.containers = list(effect.containers)
        self.counters = [0, 0, 0, 0]
        self.before = timeline.before_frames if timeline else 0
        self.gap = timeline.target_gap if timeline else 0
        self.delay = timeline.after_delay if timeline else 0
        self.targets = max(1, targets)
        lanes = timeline.sound if timeline else {}
        # ExMateria's reader always gives the before part its three lanes, so its
        # walker always takes an effect as having three parts (the PlayStation
        # captures it was matched against agree).
        self.three_part = bool(lanes.get(BEFORE))
        self.before_lanes = [_SoundLane(lane, BEFORE, True) for lane in lanes.get(BEFORE, [])]
        self.after_lanes = [_SoundLane(lane, AFTER, True) for lane in lanes.get(AFTER, [])]
        self.each_template = lanes.get(EACH, [])
        self.each = []
        self.next_target = 0
        self.started = False
        self.events = []
        self.finished_at = None

    def has_schedule(self) -> bool:
        return any(lane.keys for part in (self.before_lanes, self.after_lanes) for lane in part) or \
            any(lane.keys for lane in self.each_template)

    def _resolve(self, container: int, sound: int) -> int:
        if sound < 2 or container < 0 or container >= len(self.containers):
            return -1
        mode, a, b, c = self.containers[container]
        count = self.counters[container]
        self.counters[container] = (count + 1) & 0xFF
        if mode == 0:
            return a
        if mode == 1:
            return a if count & 1 == 0 else b
        if mode == 2:
            return b if count > 0 else a
        if mode == 3:
            if count > 0:
                return b if count & 1 == 0 else c
            return a
        if mode == 4:
            return (a, b, c)[count % 3]
        return sound

    def _fire(self, lane, frame) -> None:
        sound = lane.sound()
        if sound < 2:
            return
        resolved = self._resolve(sound - 2, sound)
        if resolved > 0:
            self.events.append((frame, lane.part, lane.index, resolved))

    @staticmethod
    def _tick(lane) -> bool:
        if lane.done:
            return False
        if lane.left > 0:
            lane.left -= 1
            if lane.left <= 0:
                return lane.advance()
        return False

    def after_start(self) -> int:
        if not self.three_part:
            return 0
        return self.before + max(0, self.targets - 1) * self.gap + self.delay

    def _spawn_each(self, frame) -> None:
        while self.next_target < self.targets:
            at = self.before + self.next_target * self.gap
            if frame < at:
                return
            lanes = [_SoundLane(lane, EACH, False) for lane in self.each_template]
            self.each.append(lanes)
            self.next_target += 1
            for lane in lanes:
                self._fire(lane, frame)

    def update(self, frame: int) -> None:
        if not self.started:
            self.started = True
            if not self.three_part or self.before <= 0:
                self._spawn_each(frame)
            if self.three_part:
                for lane in self.before_lanes:
                    self._fire(lane, frame)
        if self.three_part and frame < self.before:
            for lane in self.before_lanes:
                if self._tick(lane):
                    self._fire(lane, frame)
        for lanes in self.each:
            for lane in lanes:
                if self._tick(lane):
                    self._fire(lane, frame)
        if self.three_part and frame >= self.after_start():
            for lane in self.after_lanes:
                if self._tick(lane):
                    self._fire(lane, frame)
        if self.three_part and frame >= self.before:
            self._spawn_each(frame)
        if self.finished_at is None and self._finished():
            self.finished_at = frame

    def _finished(self) -> bool:
        if self.three_part and any(not lane.done for lane in self.before_lanes + self.after_lanes):
            return False
        if self.next_target < self.targets:
            return False
        return all(lane.done for lanes in self.each for lane in lanes)

    def idle(self, frame: int) -> bool:
        """True when no lane can start a sound after `frame`: each is done, or
        waits on a keyframe of no length (which never ends), or its part is over."""
        def stuck(lane):
            return lane.done or lane.left <= 0
        if self.next_target < self.targets:
            return False
        if self.three_part and frame < self.before and not all(stuck(l) for l in self.before_lanes):
            return False
        if self.three_part and not all(stuck(l) for l in self.after_lanes):
            return False
        return all(stuck(lane) for lanes in self.each for lane in lanes)


def sound_schedule(effect: ef.EffectFile, targets: int = 1, cap: int = FRAME_CAP) -> list:
    """Every sound the effect starts: `[(frame, part, lane, sound)]`."""
    walker = SoundWalker(effect, targets)
    if effect.timeline is None:
        return []
    for frame in range(cap):
        walker.update(frame)
        if frame >= walker.after_start() and walker.idle(frame):
            break
    return list(walker.events)


# =============================================================================
# The whole effect
# =============================================================================

@dataclass
class Frame:
    """Everything shown on one frame."""
    number: int
    seconds: float                  # how long it lasts on screen (slow motion stretches it)
    particles: list                 # [(emitter, (x, y, z), (vx, vy, vz), frameset, (ox, oy), depth, age, target)]
    angles: Optional[tuple]         # the camera: (pitch, yaw, roll) 4096 a turn, or None when the effect leaves it
    position: Optional[tuple]       # PlayStation units, y down
    zoom: Optional[float]           # 4096 = usual
    events: list = field(default_factory=list)


@dataclass
class Playback:
    effect: ef.EffectFile
    frames: list
    sounds: list                    # [(frame, part, lane, sound)]
    starts: dict                    # part -> the frame it first leads the colours
    target_starts: list             # the frame each target's part starts
    after_start: int
    callbacks: list                 # [(frame, slot, emitter)] moments a special drawing is made
    screen_top: ColourStack
    screen_bottom: ColourStack
    palettes: dict                  # "affected" | "caster" | "target" -> ColourStack

    @property
    def length(self) -> int:
        return len(self.frames)

    @property
    def seconds(self) -> float:
        return sum(frame.seconds for frame in self.frames)

    def screen(self, frame: int, top, bottom) -> tuple:
        """The backdrop's two colours (0-1 floats) on a frame, from the map's own."""
        return (tuple(min(1.0, max(0.0, c)) for c in self.screen_top.fold(top, frame)),
                tuple(min(1.0, max(0.0, c)) for c in self.screen_bottom.fold(bottom, frame)))

    def tint(self, surface: str, frame: int, colour) -> tuple:
        """A colour (0-1 floats) of the map ("affected"), caster or target on a frame."""
        return self.palettes[surface].fold(colour, frame)


class EffectPlayer:
    """
    Plays one effect for a caster and its targets. `targets` are the
    targets' places as offsets from the caster (tiles, y up); `camera_*`
    the camera's place before the effect, in PlayStation units, and
    `map_size` the map's (width, depth) in tiles, for anchors at its centre.
    """

    def __init__(self, effect: ef.EffectFile, targets=((0.0, 0.0, 0.0),), seed: int = 1,
                 caster_place=(0.0, 0.0, 0.0), map_size=(0, 0), camera_angles=DEFAULT_ANGLES,
                 camera_position=None, camera_zoom=DEFAULT_ZOOM):
        self.effect = effect
        self.targets = [tuple(t) for t in targets] or [(0.0, 0.0, 0.0)]
        self.rng = random.Random(seed)
        self.curves = Curves(effect)
        self.animator = _Animator(effect)
        timeline = effect.timeline
        self.before = timeline.before_frames if timeline else 0
        self.gap = timeline.target_gap if timeline else 0
        self.delay = timeline.after_delay if timeline else 0
        count = len(self.targets)
        self.target_starts = [self.before + i * self.gap for i in range(count)]
        self.after_start = self.before + (count - 1) * self.gap + self.delay
        self.events = []
        lanes = timeline.particles if timeline else {}
        self.blocks = []
        caster_place = tuple(caster_place)
        centre = (map_size[0] / 2.0 - caster_place[0], -caster_place[1],
                  map_size[1] / 2.0 - caster_place[2])
        anchors = []
        for target in self.targets:
            anchors.append(Anchors(world=target, cursor=target, origin=(0.0, 0.0, 0.0),
                                   target=target, camera=centre))
        self.anchors = anchors
        first = anchors[0]
        if lanes.get(BEFORE):
            self.blocks.append((BEFORE, 0, _Block(lanes[BEFORE], self.events, BEFORE, 0, 0),
                                first, 0))
        if lanes.get(EACH):
            for i, start in enumerate(self.target_starts):
                self.blocks.append((EACH, start, _Block(lanes[EACH], self.events, EACH, i, start),
                                    anchors[i], i))
        if lanes.get(AFTER):
            self.blocks.append((AFTER, self.after_start,
                                _Block(lanes[AFTER], self.events, AFTER, 0, self.after_start),
                                first, 0))
        for part, start, block, _anchors, target in self.blocks:
            for action in block.pending_start:
                self.events.append(("action", action, part, target, -1, start))
        direction = self.targets[0]
        if direction[0] * direction[0] + direction[2] * direction[2] > 0.001:
            self.facing = math.atan2(direction[0], direction[2]) - math.pi / 2.0
        else:
            self.facing = 0.0
        self.particles = []
        caster_psx = (caster_place[0] * 28.0, -caster_place[1] * 28.0, caster_place[2] * 28.0)
        self.camera = Camera(effect, self.before, self.gap, self.after_start, count,
                             effect.runs_for_each_target, self.rng, camera_angles,
                             caster_psx if camera_position is None else camera_position, camera_zoom)
        self.camera.map_centre = (map_size[0] * 14.0, 0.0, map_size[1] * 14.0)
        self.camera.caster = caster_psx
        self.camera.target_positions = [
            ((caster_place[0] + t[0]) * 28.0, -(caster_place[1] + t[1]) * 28.0,
             (caster_place[2] + t[2]) * 28.0) for t in self.targets]
        self.camera.cursor = self.camera.target_positions[0]
        self.callbacks = []
        self.colour_starts = {}
        self.dominant = ""
        self.factor = 1.0
        self.pacing = BASE_PACING
        self.before_local = self.each_local = 0
        self.was_past_before = False

    # --- particles -----------------------------------------------------------

    def _open(self, part: str, start: int, frame: int) -> bool:
        if part == BEFORE:
            return frame < self.before
        return frame >= start and frame >= self.before

    def _spawn(self, emitter_index: int, counter: int, anchors: Anchors, target: int) -> None:
        emitters = self.effect.emitters
        if not 0 <= emitter_index < len(emitters):
            return
        e = emitters[emitter_index]
        interval = _round_half_up(_simple(float(e.interval[0]), float(e.interval[1]),
                                          self.curves.get(e.curves["interval"]), counter))
        if interval <= 0 or counter % interval != 0:
            return
        count = max(1, int(_simple(float(e.count[0]), float(e.count[1]),
                                   self.curves.get(e.curves["count"]), counter)))
        for _ in range(count):
            if len(self.particles) >= POOL:
                break
            self._make(e, counter, anchors.start(e.anchor), (0.0, 0.0, 0.0), anchors, target,
                       child=False)

    def _make(self, e: ef.Emitter, frame: int, anchor, parent, anchors: Anchors, target: int,
              child: bool) -> None:
        curve = self.curves.get
        rng = self.rng
        unit_oriented = e.inward and e.align_to_facing
        offset = _vec(e.position, curve(e.curves["position"]), frame)
        spread = _vec(e.spread, curve(e.curves["spread"]), frame)
        if unit_oriented:
            offset = rotate_y(offset, self.facing)
            spread = rotate_y(spread, self.facing)
        base = _add(_add(parent, offset), anchor)
        if e.box_spread:
            jitter = (rng.uniform(-spread[0], spread[0]), rng.uniform(-spread[1], spread[1]),
                      rng.uniform(-spread[2], spread[2]))
        else:
            theta = rng.random() * math.tau
            phi = math.acos(2.0 * rng.random() - 1.0)
            r = rng.random() ** (1.0 / 3.0)
            jitter = (r * spread[0] * math.sin(phi) * math.cos(theta), r * spread[1] * math.cos(phi),
                      r * spread[2] * math.sin(phi) * math.sin(theta))
        final = _add(base, jitter)
        radial = _range(e.radial, curve(e.curves["radial"]), frame, rng)
        if unit_oriented or not (e.inward or e.align_to_facing):
            angle = _vec(e.angle, curve(e.curves["angle"]), frame)
            cone = _vec(e.angle_spread, curve(e.curves["angle_spread"]), frame)
            direction = angle_to_direction(*angle)
            ox, oy = rng.uniform(-cone[0], cone[0]), rng.uniform(-cone[1], cone[1])
            direction = _apply(_matmul(_axis_rotation(UP, oy), _axis_rotation(RIGHT, ox)), direction)
            velocity = _mul(direction, radial)
            if unit_oriented:
                velocity = rotate_y(velocity, self.facing)
        elif e.inward:
            towards = _sub(base, final)
            length = _length(towards)
            if length * length < 0.0001:
                velocity = (0.0, -radial, 0.0)
            else:
                velocity = _mul(towards, radial / length)
        else:
            velocity = (0.0, 0.0, 0.0)
        lifetime = int(_range(tuple(float(v) for v in e.lifetime), curve(e.curves["lifetime"]),
                              frame, rng))
        if lifetime >= 0:
            lifetime = max(1, lifetime)
        p = Particle(final, velocity, lifetime, e.index, e.child_on_death, e.child_mid_life)
        p.inertia = _range(tuple(float(v) for v in e.inertia), curve(e.curves["inertia"]), frame, rng)
        p.weight = _range(tuple(float(v) for v in e.weight), curve(e.curves["weight"]), frame, rng)
        p.acceleration = _vec_range(e.acceleration, curve(e.curves["acceleration"]), frame, rng)
        p.drag = _vec_range(e.drag, curve(e.curves["drag"]), frame, rng)
        p.homing_strength = _range(e.homing, curve(e.curves["homing"]), frame, rng)
        p.homing_curve = e.curves["homing_blend"]
        p.homing_arrival = e.homing_arrival * 16.0 / 28.0 if e.homing_arrival > 0 else 0.0
        if abs(p.homing_strength) > EPSILON:
            aim = _vec(e.target_offset, curve(e.curves["target_offset"]), frame)
            p.homing_target = _add(anchors.homing(e.homing_anchor, child), aim)
        p.anim_index = e.anim_index
        p.group_offset = self.effect.group_offset(e.anim_param)
        p.anchors, p.target = anchors, target
        self.particles.append(p)

    def _child(self, index: int, position, frame: int, anchors: Anchors, target: int) -> None:
        emitters = self.effect.emitters
        if not 0 <= index < len(emitters):
            return
        e = emitters[index]
        interval = e.interval[0]
        if interval > 0 and frame % interval != 0:
            return
        for _ in range(e.count[0]):
            if len(self.particles) >= POOL:
                break
            self._make(e, frame, (0.0, 0.0, 0.0), position, anchors, target, child=True)

    def _physics(self, p: Particle) -> None:
        old = p.velocity
        inertia = p.inertia
        factor = max(0.0, inertia - self.effect.inertia_threshold)
        a = p.acceleration
        if inertia > 0.0:
            new = ((factor * old[0] + a[0] * 4096.0) / inertia,
                   (factor * old[1] + a[1] * 4096.0) / inertia,
                   (factor * old[2] + a[2] * 4096.0) / inertia)
        else:
            new = (a[0] * 4096.0, a[1] * 4096.0, a[2] * 4096.0)
        g = self.effect.gravity
        k = p.weight / 4096.0
        p.velocity = (new[0] + g[0] * k, new[1] + g[1] * k, new[2] + g[2] * k)
        p.position = _add(p.position, old)
        if abs(p.homing_strength) <= EPSILON:
            p.acceleration = _add(a, p.drag)
            return
        value = -128.0
        if p.homing_curve > 0:
            curve = self.curves.get(p.homing_curve - 1)
            if curve:
                value = Curves.sample(curve, p.age) * 255.0 - 128.0
        towards = _sub(p.homing_target, p.position)
        distance = _length(towards)
        if distance < 0.001:
            p.acceleration = _add(a, p.drag)
            return
        pull = _mul(towards, p.homing_strength / distance)
        blend = value / 127.0
        p.acceleration = _add(a, _add(_mul(_sub(p.drag, pull), blend), pull))

    def _arrival(self, p: Particle) -> None:
        if p.homing_arrival <= 0.0 or p.lifetime == -1:
            return
        d = _sub(p.position, p.homing_target)
        if abs(d[0]) < p.homing_arrival and abs(d[1]) < p.homing_arrival and \
                abs(d[2]) < p.homing_arrival:
            p.held = False
            p.lifetime = -1

    def _particles(self, frame: int) -> None:
        requests = []
        for part, start, block, anchors, target in self.blocks:
            if self._open(part, start, frame):
                requests.extend((r, anchors, target) for r in block.advance())
        for (emitter, counter, lane, action, remaining), anchors, target in requests:
            slot = action & ef.ACTION_CALLBACK
            if slot:
                self.callbacks.append((frame, slot - 1, emitter))
                continue
            self._spawn(emitter, counter, anchors, target)
        after = frame + 1
        emitters = self.effect.emitters
        for p in list(self.particles):
            if p.dead() or not p.active:
                parent = emitters[p.emitter] if 0 <= p.emitter < len(emitters) else None
                if parent is not None and parent.child_death_on and p.child_death >= 0:
                    self._child(p.child_death, p.position, after, p.anchors, p.target)
        self.particles = [p for p in self.particles if not (p.dead() or not p.active)]
        alive = self.particles
        for p in alive:
            self._arrival(p)
        moving = list(alive)
        for p in moving:
            self._physics(p)
        for p in moving:
            if p.child_mid < 0:
                continue
            parent = emitters[p.emitter] if 0 <= p.emitter < len(emitters) else None
            if parent is not None and parent.child_mid_life_on:
                self._child(p.child_mid, p.position, after, p.anchors, p.target)
        for p in self.particles:
            p.age += 1
        for p in self.particles:
            self.animator.tick(p)

    def last_spawn_frame(self) -> int:
        last = 0
        for part, start, block, _anchors, _target in self.blocks:
            last = max(last, block.last_active + start)
        return last

    # --- time scale and colour parts -------------------------------------------

    def _open_parts(self, frame: int) -> list:
        if frame < self.before:
            return [BEFORE]
        parts = [EACH]
        if frame >= self.after_start:
            parts.append(AFTER)
        return parts

    def _time_scale(self, parts: list) -> None:
        scale = self.effect.time_scale
        if scale is None:
            return
        past_before = BEFORE not in parts
        pacing = 0
        if self.effect.flags & ef.FLAG_TIME_SCALE_BEFORE and not past_before:
            if 0 <= self.before_local < len(scale[0]):
                pacing = scale[0][self.before_local]
        if self.effect.flags & ef.FLAG_TIME_SCALE_EACH and past_before:
            if 0 <= self.each_local < len(scale[1]):
                pacing = scale[1][self.each_local]
        if past_before and not self.was_past_before:
            pacing = BASE_PACING
        self.was_past_before = past_before
        if 1 <= pacing <= 9 and pacing > BASE_PACING:
            self.pacing = pacing
            self.factor = BASE_PACING / float(pacing)
        elif 1 <= pacing <= BASE_PACING:
            self.pacing, self.factor = BASE_PACING, 1.0

    # --- the whole run ---------------------------------------------------------------

    def run(self, cap: int = FRAME_CAP) -> Playback:
        """
        Plays the effect to its end: past its last particle keyframe with
        no particle left, past its last camera keyframe, and with its
        colours settled (ExMateria's `EffectEndModel`, which stops at the
        particles, plus what the cinematic waits for). Sounds after that
        are not played: the lanes for each target don't stop at their last
        keyframe, and some hold leftovers far later (effect 8: a sound at
        frame 1206 of a 95-frame effect).
        """
        frames = []
        last_spawn = self.last_spawn_frame()
        sounds = sound_schedule(self.effect, len(self.targets), cap)
        camera_end = self.camera.last_keyframe_end() if self.camera.active else 0
        stacks = None
        for frame in range(cap):
            parts = self._open_parts(frame)
            dominant = AFTER if AFTER in parts else (EACH if EACH in parts else BEFORE)
            if dominant != self.dominant:
                self.dominant = dominant
                if dominant not in self.colour_starts:
                    self.colour_starts[dominant] = frame
                    stacks = None
            if stacks is None:
                stacks = self._colour_stacks()
            seconds = 1.0 / (FPS * self.factor)
            self._particles(frame)
            self.camera.advance(frame)
            if BEFORE in parts:
                self.before_local += 1
            if EACH in parts:
                self.each_local += 1
            self._time_scale(parts)
            angles = position = zoom = None
            if self.camera.active:
                angles, position, zoom = self.camera.pose()
            snapshot = [(p.emitter, p.position, p.velocity, p.frameset, p.offset, p.depth, p.age,
                         p.target) for p in self.particles]
            frames.append(Frame(frame, seconds, snapshot, angles, position, zoom, []))
            settled = max(stack.busy_until() for stack in stacks.values())
            if frame > last_spawn and not self.particles and \
                    frame >= camera_end and frame >= settled and \
                    (frame >= self.after_start or not self._waits_for_after()):
                break
        for event in self.events:
            if 0 <= event[-1] < len(frames):
                frames[event[-1]].events.append(event)
        sounds = [event for event in sounds if event[0] < len(frames)]
        for event in sounds:
            frames[event[0]].events.append(("sound",) + tuple(event[1:]))
        stacks = self._colour_stacks()
        return Playback(self.effect, frames, sounds, dict(self.colour_starts), self.target_starts,
                        self.after_start, self.callbacks, stacks["top"], stacks["bottom"],
                        {name: stacks[name] for name in ("affected", "caster", "target")})

    def _colour_stacks(self) -> dict:
        starts = self.colour_starts
        stacks = {"top": screen_stack(self.effect, starts),
                  "bottom": screen_stack(self.effect, starts, bottom=True)}
        for name in ("affected", "caster", "target"):
            stacks[name] = palette_stack(self.effect, starts, name)
        return stacks

    def _waits_for_after(self) -> bool:
        """Whether the after part has anything to show: particles, colour or camera."""
        timeline = self.effect.timeline
        if timeline is None:
            return False
        if any(lane.last >= 1 for lane in timeline.particles.get(AFTER, [])):
            return True
        if timeline.camera.get(AFTER) is not None and timeline.camera[AFTER].last > 0:
            return True
        screen = timeline.screen.get(AFTER)
        if screen is not None and _lane_window(screen) > 0:
            return True
        return any(_lane_window(lane) > 0 and any(key.on for key in lane.keys[:_lane_window(lane)])
                   for lane in timeline.palette.get(AFTER, {}).values())


def play(effect: ef.EffectFile, **kwargs) -> Playback:
    return EffectPlayer(effect, **kwargs).run()
