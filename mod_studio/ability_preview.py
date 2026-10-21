"""
An ability played out on a map: who uses it, how the unit moves for it,
which tiles it reaches, which units it hits and which effect it shows.
Asked for by Zodi on 12 October: "Redesign the abilities page, so that the
map viewer displays the unit animations for the ability on map 116 and
after it completes then show the ability effect on the map, take note that
some abilities target themselves or a different unit or units at different
ranges, then make the whole thing loop", with "Being able to toggle through
all the sprites that use that ability" and, for abilities 265 to 356, the
monster that uses it, from `MonsterJobCommandData`.

- **Who uses it**: every job whose `JobCommandId` names a skillset holding
  the ability (`JobCommandData`'s 16 slots, `MonsterJobCommandData`'s 4).
  A monster job is drawn as sprite 133 plus its `MonsterGraphic`, coloured
  by its `MonsterPalette`; a generic job (74 to 93) as its man and woman
  (`unit_sprites.sprite_number`); any other job as the sprites the game's
  battles (ENTD) dress it in, the most used first (named by their number
  when there are several). Edits in the open mod count: a skillset given a
  new ability shows its jobs here.
- **How the unit moves**: `AbilityTypeData`'s `AnimationId` n is the
  sprite's animations 2n (seen from the front) and 2n + 1 (from behind),
  and its `ChargeEffectType` the pose it charges in: the Casting Start then
  Casting Mid loop (animations 42 and 43) for a spell, Charging Idle then
  Charging Loop (33 and 34) crouched, Singing (40), Dancing (41).
  `AnimationId` 0 is the attack of the weapon held, drawn as a sword's
  swing (Swing Mid, 65). Their names are TacticsEngineG's (mrgudenheim,
  MIT: `src/fftae/SeqData/animation_names.txt`), as is what the
  instructions that move a unit do (`opcodeParameters.txt`,
  `unit_animation_manager.gd`): up, down, forward and back one or two
  units, or by an amount.
- **Where it holds while the effect plays**: an animation waits at
  WaitForInput, WeaponSheatheCheck1 or 2 (`WAITS`), looping the frames just
  before it (its one argument, signed, says how many bytes of them) until
  the game goes on; the effect plays at its last wait. A spell's cast (44)
  holds the arms up there, then lowers them (Zodi, 18 October: "the units
  arms should be fully extended in the air as the effect plays out").
- **Two jobs of one name** (the game has two Bombs) are told apart in
  Shown by by their job numbers.
- **Which tiles**: its range (tiles counted along the grid, or in straight
  lines with Linear Range), its effect area round the tile aimed at (or a
  line from the caster, for Linear AoE), from the ability table and its
  override. An ability with range 0, or Force Self-Target, is aimed at its
  user's own tile; one with Weapon Range reaches as far as the weapon held,
  drawn as a sword's one tile when its own range is 0.
- **Which effect**: `AbilityEffectNumberFilterData`'s `EffectId`, the
  number of an `fftpack/effect` file (`effect_files.py`).

Pure Python: nothing here imports Qt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import nxd_data
from . import unit_sprites as us

#: Monster skillsets' ids (MonsterJobCommandData's header).
MONSTER_COMMANDS = range(176, 224)
#: Generic jobs, drawn as a man and a woman.
GENERIC_JOBS = range(74, 94)

#: Animation ids (pairs of the sprite's animations: front, back).
WALK = 3
CHARGE_IDLE, CHARGE_LOOP = 33, 34
SINGING, DANCING = 40, 41
CAST_START, CAST_MID, CAST_EXECUTE = 42, 43, 44
TAKING_DAMAGE = 25
RECEIVE_HEAL = 27
#: `AnimationId` 0 is the weapon's own attack, which the game picks by the
#: weapon held; it is drawn as a sword's swing (Swing Mid, animations 130
#: and 131), and a monster stands still for it.
WEAPON_ATTACK, SWORD_SWING = 0, 65

#: The charging poses, by the words of `ChargeEffectTypeNames.txt`.
CHARGE_POSES = {"spell": (CAST_START, CAST_MID), "summon": (CAST_START, CAST_MID),
                "crouch": (CHARGE_IDLE, CHARGE_LOOP), "kneel": (CHARGE_IDLE, CHARGE_LOOP),
                "sing": (SINGING,), "dance": (DANCING,)}

#: The SEQ instructions that move the unit: code -> (forward, up) units
#: (TacticsEngineG's `opcodeParameters.txt`: MoveUp2 0xCB ... MoveForward1 0xD2).
MOVES = {0xCB: (0, 2), 0xCC: (0, 1), 0xCD: (-2, 0), 0xCE: (-1, 0), 0xCF: (0, -2), 0xD0: (0, -1),
         0xD1: (2, 0), 0xD2: (1, 0)}
#: Moves by an amount: MoveUnitFB, MoveUnitDU (down is positive), MoveUnitRL.
MOVE_FORWARD_BY, MOVE_DOWN_BY, MOVE_RIGHT_BY, MOVE_ALL_BY = 0xEE, 0xEF, 0xF0, 0xFA
#: The instructions an animation waits at, looping the frames before them:
#: WaitForInput, WeaponSheatheCheck1 and WeaponSheatheCheck2.
WAITS = (0xC6, 0xD3, 0xD6)

#: Where a facing points on the grid: 0 south (lower Y), 1 west (lower X),
#: 2 north, 3 east, as ENTD names them (measured for the Encounters page:
#: `qt/pages/encounter_map.py`).
FACING_STEPS = {0: (0, -1), 1: (-1, 0), 2: (0, 1), 3: (1, 0)}


# =============================================================================
# Who uses it
# =============================================================================

@dataclass
class User:
    job: int
    job_name: str
    sprite: int
    palette: int
    label: str
    monster: bool = False


def _int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def ability_users(ability: int, jobs: dict, commands: dict, job_names: Optional[dict] = None,
                  job_sprites: Optional[dict] = None, sprite_names: Optional[dict] = None) -> list:
    """
    Everyone who can use `ability`: the generic jobs first, then the rest,
    each in job order.

    `jobs`: job id -> its fields (`JobCommandId`, `MonsterGraphic`,
    `MonsterPalette`, as strings or numbers). `commands`: skillset id -> its
    ability ids. `job_sprites`: job id -> {sprite: how many of the game's
    battle units wear it}, for the jobs with no generic sprite.
    """
    job_names = job_names or {}
    job_sprites = job_sprites or {}
    sprite_names = sprite_names or {}
    holding = {command for command, ids in commands.items() if ability in ids}
    users = []
    # The generic jobs first: they are who most players see using it.
    for job in sorted(jobs, key=lambda j: (j not in GENERIC_JOBS, j)):
        values = jobs[job]
        if _int(values.get("JobCommandId"), -1) not in holding:
            continue
        name = job_names.get(job) or f"Job {job}"
        command = _int(values.get("JobCommandId"), -1)
        if command in MONSTER_COMMANDS:
            graphic = _int(values.get("MonsterGraphic"))
            if graphic > 0:
                users.append(User(job, name, us.MONSTER_SPRITE_BASE + graphic,
                                  _int(values.get("MonsterPalette")), name, monster=True))
            continue
        if job in GENERIC_JOBS:
            for sprite_set, word in ((us.GENERIC_MAN, "man"), (us.GENERIC_WOMAN, "woman")):
                sprite = us.sprite_number(sprite_set, job)
                if sprite is not None:
                    users.append(User(job, name, sprite, 0, f"{name}, {word}"))
            continue
        worn = sorted((job_sprites.get(job) or {}).items(), key=lambda item: (-item[1], item[0]))
        for sprite, _count in worn:
            label = name
            if len(worn) > 1:
                label = f"{name}, {sprite_names.get(sprite) or f'sprite {sprite}'}"
            users.append(User(job, name, sprite, 0, label))
    # Two jobs can share a name (the game has two Bombs): told apart by number.
    labels = [user.label for user in users]
    for user in users:
        if labels.count(user.label) > 1:
            user.label = f"{user.label} (job {user.job})"
    return users


def entd_job_sprites(tables, jobs: dict) -> dict:
    """job -> {sprite: units}, from the game's battles (an `entd.EntdTables`)."""
    out = {}
    if tables is None:
        return out
    for units in tables.events.values():
        for unit in units:
            if not getattr(unit, "occupied", True):
                continue
            values = unit.values
            job = values.get("main_job", 0)
            graphic = _int((jobs.get(job) or {}).get("MonsterGraphic"))
            sprite = us.sprite_number(values.get("sprite_set", 0), job, graphic)
            if sprite is None:
                continue
            counts = out.setdefault(job, {})
            counts[sprite] = counts.get(sprite, 0) + 1
    return out


# =============================================================================
# How the unit moves
# =============================================================================

@dataclass
class Step:
    """One frame of a unit's animation: shown for `delay` 60ths of a second,
    the unit moved `forward` and `up` from where it stands (world units).
    `held`: one of the frames looped at the animation's last wait, where
    it holds while the effect plays."""
    frame: int
    delay: int
    forward: int
    up: int
    right: int = 0
    held: bool = False


def _signed(value: int) -> int:
    return value - 256 if value >= 128 else value


def animation_steps(animation) -> list:
    """An animation's frames with the moves its instructions make (`read_sequences` steps),
    the ones it loops at its last wait marked `held`."""
    steps = []
    forward = up = right = 0
    #: Each step read so far: its length in bytes, and its frame's place in `steps`.
    read = []
    held = ()
    for step in animation or ():
        if step[0] == "op":
            code, args = step[1], step[2]
            if code in WAITS and args:
                # The bytes before it that it loops: whole steps, back from it.
                wanted, looped = abs(_signed(args[0])), []
                for length, place in reversed(read):
                    if wanted <= 0:
                        break
                    wanted -= length
                    if place is not None:
                        looped.append(place)
                # One that loops no frame (only where an item is held, say)
                # holds the frame on screen.
                held = looped or ([len(steps) - 1] if steps else held)
            read.append((2 + len(args), None))
            if code in MOVES:
                df, du = MOVES[code]
                forward, up = forward + df, up + du
            elif code == MOVE_FORWARD_BY and args:
                forward += _signed(args[0])
            elif code == MOVE_DOWN_BY and args:
                up -= _signed(args[0])
            elif code == MOVE_RIGHT_BY and args:
                right += _signed(args[0])
            elif code == MOVE_ALL_BY and len(args) >= 3:
                right += _signed(args[0])
                up -= _signed(args[1])
                forward += _signed(args[2])
            continue
        frame, delay = step
        read.append((2, len(steps)))
        steps.append(Step(frame, max(1, delay), forward, up, right))
    for place in held:
        steps[place].held = True
    return steps


def animation(sequences, animation_id: int, back: bool = False) -> list:
    """Animation `animation_id` of a sprite's sequences, from the front or behind."""
    index = 2 * animation_id + (1 if back else 0)
    if sequences is None or not 0 <= index < len(sequences):
        return []
    return animation_steps(sequences[index])


def charge_pose(charge_name: str) -> tuple:
    """The animation ids a unit charges with, from its charge type's name."""
    words = (charge_name or "").lower()
    for word, ids in CHARGE_POSES.items():
        if word in words:
            return ids
    return (CAST_START, CAST_MID)


def cast_animation(animation_id: int, monster: bool = False) -> int:
    """The animation a unit plays for `AnimationId` `animation_id` (see `WEAPON_ATTACK`)."""
    if animation_id == WEAPON_ATTACK:
        return WALK if monster else SWORD_SWING
    return animation_id


def duration(steps: list) -> float:
    """How long an animation's frames take, in seconds."""
    return sum(step.delay for step in steps) / 60.0


# =============================================================================
# Which tiles
# =============================================================================

@dataclass
class Reach:
    range: int
    area: int
    vertical: int
    flags: set = field(default_factory=set)

    @property
    def weapon(self) -> bool:
        """Weapon Range: the weapon held decides how far it reaches."""
        return "weaponRange" in self.flags

    @property
    def reach(self) -> int:
        """How far it is drawn reaching: its range, or a sword's 1 for Weapon Range at 0."""
        return max(1, self.range) if self.weapon else self.range

    @property
    def self_only(self) -> bool:
        return self.reach <= 0 or "forceSelfTarget" in self.flags


def flags_from_bytes(flag_bytes) -> set:
    """The names of the ability flags four bytes set (`nxd_data.unpack_flag_group`,
    which reads a flag stored inverted the right way round)."""
    names = set()
    for group, value in enumerate(flag_bytes[:4]):
        for flag_id, on in nxd_data.unpack_flag_group(group, _int(value)).items():
            if on:
                names.add(flag_id)
    return names


def range_tiles(caster: tuple, reach: Reach, size: tuple) -> list:
    """The tiles it can be aimed at."""
    cx, cz = caster
    if reach.self_only:
        return [caster]
    linear = "verticalFixed" in reach.flags
    out = []
    for x in range(size[0]):
        for z in range(size[1]):
            d = abs(x - cx) + abs(z - cz)
            if d > reach.reach:
                continue
            if d == 0 and "targetSelf" not in reach.flags:
                continue
            if linear and x != cx and z != cz:
                continue
            out.append((x, z))
    return out


def aim(caster: tuple, facing: int, reach: Reach, size: tuple) -> tuple:
    """The tile it is aimed at: as far as it reaches, straight ahead."""
    if reach.self_only:
        return caster
    dx, dz = FACING_STEPS.get(facing, (1, 0))
    best = caster
    for n in range(1, reach.reach + 1):
        x, z = caster[0] + dx * n, caster[1] + dz * n
        if 0 <= x < size[0] and 0 <= z < size[1]:
            best = (x, z)
    return best


def area_tiles(caster: tuple, target: tuple, facing: int, reach: Reach, size: tuple) -> list:
    """The tiles it hits when aimed at `target`."""
    def inside(t):
        return 0 <= t[0] < size[0] and 0 <= t[1] < size[1]
    if "linearAttack" in reach.flags and target != caster:
        dx, dz = FACING_STEPS.get(facing, (1, 0))
        length = max(reach.area, reach.reach)
        return [t for t in ((caster[0] + dx * n, caster[1] + dz * n) for n in range(1, length + 1))
                if inside(t)]
    tx, tz = target
    return [(x, z) for x in range(tx - reach.area, tx + reach.area + 1)
            for z in range(tz - reach.area, tz + reach.area + 1)
            if abs(x - tx) + abs(z - tz) <= reach.area and inside((x, z))]


def stand_ins(target: tuple, area: list, caster: tuple, most: int = 3) -> list:
    """Where to stand units to be hit: the tile aimed at, then the area's nearest."""
    chosen = [] if target == caster else [target]
    for tile in sorted(area, key=lambda t: (abs(t[0] - target[0]) + abs(t[1] - target[1]), t)):
        if len(chosen) >= most:
            break
        if tile not in chosen and tile != caster:
            chosen.append(tile)
    return chosen


# =============================================================================
# A unit's pictures for an ability
# =============================================================================

@dataclass
class Moving:
    """One animation's pictures: `[(Picture, Step)]` from the front and from behind."""
    front: list
    back: list

    def seconds(self, back: bool = False) -> float:
        return sum(step.delay for _picture, step in (self.back if back else self.front)) / 60.0


def sprite_animations(sprites: us.UnitSprites, number: Optional[int], palette: int,
                      animation_ids) -> tuple:
    """
    `({animation id: Moving}, flying)` for sprite `number`, coloured by
    `palette`: what a page needs to play a unit through an ability. Empty when
    the sprite can't be drawn (`sprites.problem` says why).
    """
    out = {}
    if number is None:
        return out, False
    entry = sprites.table.get(number)
    attributes = sprites.attributes().get(number)
    if entry is None or attributes is None:
        return out, False
    sheet, colours = sprites.sheet(entry), sprites.palette(number, palette)
    shape, sequences = sprites.shape(attributes.shape), sprites.sequences(attributes.sequence)
    if sheet is None or colours is None or not shape or not sequences:
        return out, attributes.flying
    for animation_id in sorted(set(animation_ids)):
        sides = {}
        for side, back in (("front", False), ("back", True)):
            pictures = []
            for step in animation(sequences, animation_id, back):
                picture = us.draw_frame(sheet, shape[step.frame], colours) \
                    if step.frame < len(shape) else None
                if picture is not None:
                    pictures.append((picture, step))
            sides[side] = pictures
        if sides["front"] or sides["back"]:
            out[animation_id] = Moving(sides["front"] or sides["back"], sides["back"] or sides["front"])
    return out, attributes.flying
