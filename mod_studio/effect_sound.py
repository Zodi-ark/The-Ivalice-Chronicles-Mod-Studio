"""
The sound of an effect, as the PlayStation version plays it and as The
Ivalice Chronicles does. Asked for by Zodi on 12 October: "Do it completly
now the emitters, timing, camera, and sound as well as everything else that
is possible".

An effect file's sound section ("feds") is a little sequence in the
language of the game's music files: pairs of channels of notes, rests and
settings, one pair for each sound the effect's timeline starts
(`effect_player.SoundWalker` says when, and which: pair = sound - 1). The
instruments are the PlayStation's own samples, `SOUND/WAVESET.WD`, which
The Ivalice Chronicles still carries in `system/ffto/fftpack.en.bin`
(entry 775, `sound/waveset.wd` in the mod loader's list).

**The remaster's own sounds** (`mix_recordings`) are recordings in
`sound/common/sound.sab`, named `FID_SOUND_VFX_<resource><sound less one>_WAV`
in hexadecimal (`vfx_name`): the resource is the sound section's word at
0x0A (`vfx_resource`), which 386 of the 400 effects' name one of the
archive's 494 VFX names by (only one of them is its effect's own number:
Fire, effect 16, is resource 0x1A, `FID_SOUND_VFX_001A0000_WAV`, track 668,
"Yes, that's Fire": Zodi, 20 October; Holy, 15, is 0xF9, track 809, which
he knew for "holy/ dark holy"), and the second half is the sound less one,
as the PlayStation's pair is (385 of the 386 effects' names are under their
pairs). A name may play several recordings at once (Holy's third sound,
660 with 683, five seconds of silence).

Read and played as ExMateria-Sound reads and plays them (timbermania,
GPL-3.0 - github.com/timbermania/exmateria-sound), which its authors
matched against the PlayStation running in an emulator:

- **The bank** (`waveset_parser.gd`): "dwds", the samples' start at 0x10,
  then 16 bytes an instrument from 0x20: where its sample is, its size,
  its tuning (s16) and its envelope; samples are PlayStation ADPCM.
- **The sequence** (`feds_bank.gd`, `smd_opcodes.gd`, `shared/opcodes`):
  a note is a byte under 0x80 then one whose value / 19 is the key (0-11,
  12 hold, 13 rest) and % 19 its length from a table; the bytes from 0x80
  are instructions (instrument, octave, tempo, volume, envelope, pitch
  bend, repeats, end). A sound's own volume is the byte at its number past
  the section's data offset.
- **The voice** (`compute_pitch.gd`, `compute_vol_lr.gd`, `pitch_table.gd`,
  and from `src/shared` the envelope `fft_adsr_envelope.cpp`, the
  four-point Gaussian interpolation `fft_spu_voice_tools.cpp` with its
  table, and the noise generator `fft_spu_mix_tools.cpp`, all PCSX-Redux's
  SPU): pitch from the note, the instrument's tuning and the bend; volume
  from the dynamics, the sound's own volume and the pan.

Not here: the music driver's vibrato, tremolo and pan wobbles (LFOs),
portamento and reverb. Rendered at 44,100 samples a second, 16-bit stereo.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

#: Samples a second.
RATE = 44100
#: Where the bank is.
PACK_FILE = "system/ffto/fftpack.en.bin"
WAVESET_INDEX = 775
#: The longest a sound is let ring.
MOST_SECONDS = 8.0
#: An effect's sounds keep time at tempo byte 0x66 (the sound entity's
#: 0x6600 budget: 102 x 0x100), 48 ticks a beat.
EFFECT_TEMPO = 0x66
TICKS_A_BEAT = 48
#: A note's length, by its second byte % 19; 0 = the next byte (`DELTA_TIME_TABLE`).
LENGTHS = (0, 192, 144, 96, 72, 64, 48, 36, 32, 24, 18, 16, 12, 9, 8, 6, 4, 3, 2)
#: Bytes each instruction takes after itself (`OPCODE_INFO` and `_EXTRA_OPCODES`).
ARGUMENTS = {
    0x80: 1, 0x81: 1, 0x82: 0, 0x8A: 0, 0x8D: 1, 0x8E: 3, 0x8F: 0, 0x90: 0, 0x91: 0, 0x94: 1,
    0x95: 0, 0x96: 0, 0x97: 2, 0x98: 1, 0x99: 0, 0x9A: 0, 0x9B: 0, 0x9C: 3, 0x9D: 3, 0x9E: 3,
    0xA0: 1, 0xA1: 1, 0xA2: 2, 0xA3: 2, 0xA4: 1, 0xA5: 1, 0xA6: 1, 0xA7: 2, 0xA9: 1, 0xAA: 1,
    0xAC: 1, 0xAD: 1, 0xAE: 0, 0xAF: 0, 0xB0: 0, 0xB1: 0, 0xB2: 0, 0xB3: 0, 0xB4: 1, 0xB5: 1,
    0xB6: 0, 0xB7: 0, 0xB8: 3, 0xB9: 1, 0xBA: 0, 0xBB: 0, 0xC0: 0, 0xC1: 3, 0xC2: 1, 0xC3: 1,
    0xC4: 1, 0xC5: 1, 0xC6: 1, 0xC7: 2, 0xC8: 1, 0xC9: 1, 0xCA: 1, 0xCF: 0, 0xD0: 1, 0xD1: 1,
    0xD2: 1, 0xD3: 2, 0xD4: 2, 0xD5: 0, 0xD6: 1, 0xD7: 1, 0xD8: 3, 0xD9: 3, 0xDA: 0, 0xDB: 0,
    0xDC: 0, 0xE0: 1, 0xE1: 1, 0xE2: 2, 0xE3: 1, 0xE4: 3, 0xE5: 3, 0xE6: 0, 0xE7: 0, 0xE8: 1,
    0xE9: 1, 0xEA: 2, 0xEB: 1, 0xEC: 3, 0xED: 3, 0xEE: 0, 0xEF: 0, 0xF0: 3, 0xF1: 3, 0xF2: 2,
    0xF4: 1, 0xF5: 1, 0xF6: 1, 0xF7: 1, 0xF8: 3, 0xF9: 2, 0xFB: 1, 0xFC: 2, 0xFD: 1, 0xFE: 1,
    0xFF: 0}
END, REST, FERMATA, OCTAVE, OCTAVE_UP, OCTAVE_DOWN = 0x90, 0x80, 0x81, 0x94, 0x95, 0x96
REPEAT, CODA, TEMPO, GATE, INSTRUMENT, SLUR_ON, SLUR_OFF = 0x98, 0x99, 0xA0, 0xA9, 0xAC, 0xB0, 0xB1
NOISE_ON, NOISE_CLOCK_ADD, NOISE_ON_KEEP, NOISE_OFF = 0xB4, 0xB5, 0xB6, 0xB7
ADSR_RESET, ATTACK, DECAY_RATE, SUSTAIN_RATE, RELEASE = 0xC0, 0xC2, 0xC3, 0xC4, 0xC5
DECAY_SUSTAIN, ATTACK_MODE, SUSTAIN_MODE, RELEASE_MODE = 0xC7, 0xC8, 0xC9, 0xCA
BEND_SET, BEND_ADD, BEND_STEP, BEND_ADD16 = 0xD0, 0xD1, 0xD2, 0xD3
DYNAMICS, DYNAMICS_ADD, DYNAMICS_RAMP, PAN = 0xE0, 0xE1, 0xE2, 0xE8

#: ADPCM's prediction filters.
FILTERS = ((0, 0), (60, 0), (115, -52), (98, -55), (122, -60))

#: The PlayStation's pitch table: 0x2000 x 2^(k / 3072), rounded (it is the
#: game's table to the last entry; `pitch_table.gd`).
_PITCHES = [int(round(0x2000 * 2 ** (k / 3072))) for k in range(12 * 256)]


def note_pitch(adjusted: int) -> int:
    """The voice's pitch register (4096 = the sample's own rate) for a note,
    as `(note x 256) + tuning + bend` (`PitchTable.note_to_pitch`)."""
    index = (adjusted >> 8) & 0x7F
    fine = adjusted & 0xFF
    semitone, octave = index % 12, min(index // 12, 9)
    base = _PITCHES[min(semitone * 256 + fine, len(_PITCHES) - 1)]
    shift = 6 - octave
    value = base >> shift if shift >= 0 else base << -shift
    return value & 0x3FFF


#: The SPU's interpolation weights, 256 places between two samples by four
#: weights (the oldest of the last four samples first), summing to about 2048:
#: PCSX-Redux's table as ExMateria-Sound lays it out (`detail/fft_gauss_table.inc`).
_GAUSS_WEIGHTS = (
    370, 1305, 374, 0, 366, 1305, 378, 0, 362, 1304, 381, 0, 358, 1304, 385, 0,
    354, 1304, 389, 0, 351, 1304, 393, 0, 347, 1304, 397, 0, 343, 1303, 401, 0,
    339, 1303, 405, 0, 336, 1303, 410, 0, 332, 1302, 414, 0, 328, 1302, 418, 0,
    325, 1301, 422, 0, 321, 1300, 426, 0, 318, 1300, 430, 0, 314, 1299, 434, 0,
    311, 1298, 439, 1, 307, 1297, 443, 1, 304, 1297, 447, 1, 300, 1296, 451, 1,
    297, 1295, 456, 1, 293, 1294, 460, 1, 290, 1293, 464, 1, 286, 1292, 469, 1,
    283, 1291, 473, 1, 280, 1290, 477, 1, 276, 1288, 482, 1, 273, 1287, 486, 2,
    270, 1286, 491, 2, 267, 1284, 495, 2, 263, 1283, 499, 2, 260, 1282, 504, 2,
    257, 1280, 508, 2, 254, 1279, 513, 2, 251, 1277, 517, 3, 248, 1275, 522, 3,
    245, 1274, 527, 3, 242, 1272, 531, 3, 239, 1270, 536, 3, 236, 1269, 540, 4,
    233, 1267, 545, 4, 230, 1265, 550, 4, 227, 1263, 554, 4, 224, 1261, 559, 4,
    221, 1259, 563, 5, 218, 1257, 568, 5, 215, 1255, 573, 5, 212, 1253, 577, 5,
    210, 1251, 582, 6, 207, 1248, 587, 6, 204, 1246, 592, 6, 201, 1244, 596, 6,
    199, 1241, 601, 7, 196, 1239, 606, 7, 193, 1237, 611, 7, 191, 1234, 615, 8,
    188, 1232, 620, 8, 186, 1229, 625, 8, 183, 1227, 630, 9, 180, 1224, 635, 9,
    178, 1221, 640, 9, 175, 1219, 644, 10, 173, 1216, 649, 10, 171, 1213, 654, 10,
    168, 1210, 659, 11, 166, 1207, 664, 11, 163, 1205, 669, 11, 161, 1202, 674, 12,
    159, 1199, 678, 12, 156, 1196, 683, 13, 154, 1193, 688, 13, 152, 1190, 693, 14,
    150, 1186, 698, 14, 147, 1183, 703, 15, 145, 1180, 708, 15, 143, 1177, 713, 15,
    141, 1174, 718, 16, 139, 1170, 723, 16, 137, 1167, 728, 17, 134, 1164, 732, 17,
    132, 1160, 737, 18, 130, 1157, 742, 19, 128, 1153, 747, 19, 126, 1150, 752, 20,
    124, 1146, 757, 20, 122, 1143, 762, 21, 120, 1139, 767, 21, 118, 1136, 772, 22,
    117, 1132, 777, 23, 115, 1128, 782, 23, 113, 1125, 787, 24, 111, 1121, 792, 24,
    109, 1117, 797, 25, 107, 1113, 802, 26, 106, 1109, 806, 27, 104, 1106, 811, 27,
    102, 1102, 816, 28, 100, 1098, 821, 29, 99, 1094, 826, 29, 97, 1090, 831, 30,
    95, 1086, 836, 31, 94, 1082, 841, 32, 92, 1078, 846, 32, 90, 1074, 851, 33,
    89, 1070, 855, 34, 87, 1066, 860, 35, 86, 1061, 865, 36, 84, 1057, 870, 36,
    83, 1053, 875, 37, 81, 1049, 880, 38, 80, 1045, 884, 39, 78, 1040, 889, 40,
    77, 1036, 894, 41, 76, 1032, 899, 42, 74, 1027, 904, 43, 73, 1023, 908, 44,
    71, 1019, 913, 45, 70, 1014, 918, 46, 69, 1010, 923, 47, 67, 1005, 927, 48,
    66, 1001, 932, 49, 65, 997, 937, 50, 64, 992, 941, 51, 62, 988, 946, 52,
    61, 983, 951, 53, 60, 978, 955, 54, 59, 974, 960, 55, 58, 969, 965, 56,
    56, 965, 969, 58, 55, 960, 974, 59, 54, 955, 978, 60, 53, 951, 983, 61,
    52, 946, 988, 62, 51, 941, 992, 64, 50, 937, 997, 65, 49, 932, 1001, 66,
    48, 927, 1005, 67, 47, 923, 1010, 69, 46, 918, 1014, 70, 45, 913, 1019, 71,
    44, 908, 1023, 73, 43, 904, 1027, 74, 42, 899, 1032, 76, 41, 894, 1036, 77,
    40, 889, 1040, 78, 39, 884, 1045, 80, 38, 880, 1049, 81, 37, 875, 1053, 83,
    36, 870, 1057, 84, 36, 865, 1061, 86, 35, 860, 1066, 87, 34, 855, 1070, 89,
    33, 851, 1074, 90, 32, 846, 1078, 92, 32, 841, 1082, 94, 31, 836, 1086, 95,
    30, 831, 1090, 97, 29, 826, 1094, 99, 29, 821, 1098, 100, 28, 816, 1102, 102,
    27, 811, 1106, 104, 27, 806, 1109, 106, 26, 802, 1113, 107, 25, 797, 1117, 109,
    24, 792, 1121, 111, 24, 787, 1125, 113, 23, 782, 1128, 115, 23, 777, 1132, 117,
    22, 772, 1136, 118, 21, 767, 1139, 120, 21, 762, 1143, 122, 20, 757, 1146, 124,
    20, 752, 1150, 126, 19, 747, 1153, 128, 19, 742, 1157, 130, 18, 737, 1160, 132,
    17, 732, 1164, 134, 17, 728, 1167, 137, 16, 723, 1170, 139, 16, 718, 1174, 141,
    15, 713, 1177, 143, 15, 708, 1180, 145, 15, 703, 1183, 147, 14, 698, 1186, 150,
    14, 693, 1190, 152, 13, 688, 1193, 154, 13, 683, 1196, 156, 12, 678, 1199, 159,
    12, 674, 1202, 161, 11, 669, 1205, 163, 11, 664, 1207, 166, 11, 659, 1210, 168,
    10, 654, 1213, 171, 10, 649, 1216, 173, 10, 644, 1219, 175, 9, 640, 1221, 178,
    9, 635, 1224, 180, 9, 630, 1227, 183, 8, 625, 1229, 186, 8, 620, 1232, 188,
    8, 615, 1234, 191, 7, 611, 1237, 193, 7, 606, 1239, 196, 7, 601, 1241, 199,
    6, 596, 1244, 201, 6, 592, 1246, 204, 6, 587, 1248, 207, 6, 582, 1251, 210,
    5, 577, 1253, 212, 5, 573, 1255, 215, 5, 568, 1257, 218, 5, 563, 1259, 221,
    4, 559, 1261, 224, 4, 554, 1263, 227, 4, 550, 1265, 230, 4, 545, 1267, 233,
    4, 540, 1269, 236, 3, 536, 1270, 239, 3, 531, 1272, 242, 3, 527, 1274, 245,
    3, 522, 1275, 248, 3, 517, 1277, 251, 2, 513, 1279, 254, 2, 508, 1280, 257,
    2, 504, 1282, 260, 2, 499, 1283, 263, 2, 495, 1284, 267, 2, 491, 1286, 270,
    2, 486, 1287, 273, 1, 482, 1288, 276, 1, 477, 1290, 280, 1, 473, 1291, 283,
    1, 469, 1292, 286, 1, 464, 1293, 290, 1, 460, 1294, 293, 1, 456, 1295, 297,
    1, 451, 1296, 300, 1, 447, 1297, 304, 1, 443, 1297, 307, 1, 439, 1298, 311,
    0, 434, 1299, 314, 0, 430, 1300, 318, 0, 426, 1300, 321, 0, 422, 1301, 325,
    0, 418, 1302, 328, 0, 414, 1302, 332, 0, 410, 1303, 336, 0, 405, 1303, 339,
    0, 401, 1303, 343, 0, 397, 1304, 347, 0, 393, 1304, 351, 0, 389, 1304, 354,
    0, 385, 1304, 358, 0, 381, 1304, 362, 0, 378, 1305, 366, 0, 374, 1305, 370,
)
_GAUSS = None


def _gauss() -> np.ndarray:
    global _GAUSS
    if _GAUSS is None:
        _GAUSS = np.array(_GAUSS_WEIGHTS, dtype=np.int64).reshape(256, 4)
    return _GAUSS


class SoundError(ValueError):
    """A file that isn't the shape this module reads."""


# =============================================================================
# The bank
# =============================================================================

def read_pack_entry(path, index: int) -> bytes:
    """One file of an `fftpack.bin`: a u32 count, then where the offsets and
    the sizes tables are (u32 each); a file's place and size by its index."""
    with Path(path).open("rb") as handle:
        head = handle.read(12)
        if len(head) < 12:
            raise SoundError(f"{Path(path).name} is too short to be a pack")
        count, offsets_at, sizes_at = struct.unpack("<3I", head)
        if not 0 <= index < count:
            raise SoundError(f"{Path(path).name} has no file {index}")
        handle.seek(offsets_at + 4 * index)
        offset = struct.unpack("<I", handle.read(4))[0]
        handle.seek(sizes_at + 4 * index)
        size = struct.unpack("<I", handle.read(4))[0]
        handle.seek(offset)
        data = handle.read(size)
    if len(data) < size:
        raise SoundError(f"{Path(path).name}'s file {index} runs past its end")
    return data


def waveset_bytes(game_dir) -> bytes:
    """`SOUND/WAVESET.WD`, out of the unpacked game's `fftpack.en.bin`."""
    data = read_pack_entry(Path(game_dir) / PACK_FILE, WAVESET_INDEX)
    if data[:4] != b"dwds":
        raise SoundError("fftpack.en.bin's entry 775 isn't the sample bank")
    return data


def decode_adpcm(data: bytes) -> tuple:
    """`(samples, loop start or -1)`: PlayStation ADPCM, 16 bytes to 28 samples,
    up to the block that ends it."""
    out = []
    s1 = s2 = 0
    loop = -1
    for at in range(0, len(data) - 15, 16):
        head, flags = data[at], data[at + 1]
        shift, f0, f1 = head & 0x0F, *FILTERS[min((head >> 4) & 0x0F, 4)]
        if flags & 0x04:
            loop = len(out)
        for byte in data[at + 2:at + 16]:
            for nibble in (byte & 0x0F, byte >> 4):
                s = (nibble << 12) & 0xFFFF
                if s & 0x8000:
                    s -= 0x10000
                value = (s >> shift) + ((s1 * f0) >> 6) + ((s2 * f1) >> 6)
                s2, s1 = s1, value
                out.append(max(-32768, min(32767, value)))
        if flags & 0x01:
            if not (flags & 0x02):
                loop = -1
            elif loop < 0:
                loop = 0
            break
    return np.array(out, dtype=np.int64), loop


@dataclass
class Instrument:
    index: int
    offset: int
    size: int
    tuning: int
    adsr1: int
    adsr2: int
    raw: bytes = b""
    _pcm: object = None
    _loop: int = -1

    def samples(self) -> tuple:
        if self._pcm is None:
            data = self.raw
            if len(data) >= 16 and not any(data[:16]):
                data = data[16:]
            self._pcm, self._loop = decode_adpcm(data)
        return self._pcm, self._loop


def read_waveset(data: bytes) -> list:
    if len(data) < 0x20 or data[:4] != b"dwds":
        raise SoundError("it doesn't begin the way the sample bank does")
    start = struct.unpack_from("<I", data, 0x10)[0]
    instruments = []
    for i in range((start - 0x20) // 16):
        at = 0x20 + 16 * i
        offset, size, tuning = struct.unpack_from("<IHh", data, at)
        b = data[at + 8:at + 16]
        attack, decay, sustain_rate, release, sustain_level = (b[0] & 0x7F, b[1] & 0x0F, b[2] & 0x7F,
                                                               b[3] & 0x1F, b[4] & 0x0F)
        sustain_exp, release_exp = (b[6] >> 2) & 1, (b[7] >> 2) & 1
        adsr1 = (attack << 8) | (decay << 4) | sustain_level
        adsr2 = (sustain_exp << 15) | (1 << 14) | (sustain_rate << 6) | (release_exp << 5) | release
        raw = data[start + offset:start + offset + size] if offset or size else b""
        instruments.append(Instrument(i, offset, size, tuning, adsr1, adsr2, raw))
    return instruments


# =============================================================================
# The effect's sequence
# =============================================================================

@dataclass
class Feds:
    data_size: int
    pairs: int
    data_offset: int
    channels: list         # offsets
    raw: bytes
    #: The remaster's recordings it names (`vfx_resource`).
    resource: int = 0

    def volume(self, sound: int) -> int:
        """A sound's own volume (`chan_92`): 0x6000 x its byte >> 7, at most 0x7FFF."""
        at = self.data_offset + sound
        byte = self.raw[at] if 0 <= at < len(self.raw) else 0
        return min((0x6000 * byte) >> 7, 0x7FFF)

    def events(self, channel: int) -> list:
        """A channel's notes and instructions, to its end (it runs on into the
        next channel when it has none, as the game's reader does)."""
        if not 0 <= channel < len(self.channels):
            return []
        return decode_events(self.raw, self.channels[channel], min(self.data_size, len(self.raw)))


def read_feds(blob: bytes) -> Feds:
    if len(blob) < 0x18 or blob[:4] != b"feds":
        raise SoundError("it doesn't begin the way an effect's sound does")
    data_size, pairs_plus_one, resource, data_offset = struct.unpack_from("<IHHI", blob, 4)
    pairs = max(0, pairs_plus_one - 1)
    channels = [struct.unpack_from("<H", blob, 0x18 + 2 * i)[0] for i in range(2 * pairs)
                if 0x1A + 2 * i <= len(blob)]
    return Feds(data_size, pairs, data_offset, channels, bytes(blob), resource)


def decode_events(data: bytes, start: int, end: int) -> list:
    """`[("note", key, ticks)]` and `[("op", code, args)]`, to the first end (0x90)."""
    events = []
    at = start
    while at < end:
        byte = data[at]
        at += 1
        if byte < 0x80:
            if at >= end:
                break
            second = data[at]
            at += 1
            ticks = LENGTHS[second % 19]
            if ticks == 0 and at < end:
                ticks = data[at]
                at += 1
            events.append(("note", second // 19, ticks))
            continue
        count = ARGUMENTS.get(byte, 0)
        events.append(("op", byte, tuple(data[at:at + count])))
        at += count
        if byte == END:
            break
    return events


# =============================================================================
# Playing a channel
# =============================================================================

def _signed(value: int) -> int:
    value &= 0xFF
    return value - 256 if value >= 128 else value


@dataclass
class Note:
    """A note on a voice: from `start` (samples), let go at `off`."""
    start: int
    off: int
    instrument: int
    key: int               # octave x 12 + key
    tuning: int
    bend: int
    adsr1: int
    adsr2: int
    left: int              # 0 to 0x3FFF
    right: int
    noise: Optional[int] = None
    #: Later changes of pitch while it sounds, a slurred note's or a bend:
    #: [(samples after `start`, key, bend)].
    bends: list = field(default_factory=list)

    def adjusted(self, key: Optional[int] = None, bend: Optional[int] = None) -> int:
        """`(note x 256) + tuning + bend`, what its pitch is read from."""
        return ((self.key if key is None else key) * 256 + self.tuning
                + (self.bend if bend is None else bend))


def _volumes(dynamics: int, sound_volume: int, pan: int) -> tuple:
    """`compute_vol_lr`: the voice's left and right volume."""
    env = max(0, min(0x7FFF, dynamics << 8))
    gated = (sound_volume * env) >> 15
    base = (0x7F00 * gated) >> 16
    pan_base = max(0, min(0x7F00, 0x4000 + pan))
    if pan_base < 0x4000:
        split, right_first = pan_base, False
    else:
        split, right_first = 0x8000 - pan_base, True
    poly1 = ((45 * split) << 9) >> 14
    poly2 = 0x7F00 - (((37 * split) << 8) >> 14)
    left_weight, right_weight = (poly1, poly2) if right_first else (poly2, poly1)
    return (max(0, min(0x3FFF, (left_weight * base) >> 15)),
            max(0, min(0x3FFF, (right_weight * base) >> 15)))


def channel_notes(events: list, instruments: list, sound_volume: int,
                  most_seconds: float = MOST_SECONDS) -> list:
    """The notes a channel plays, in samples from its start. A note sounds
    until the channel's next note starts (the voice is keyed again)."""
    tempo = EFFECT_TEMPO
    # An effect's channel starts at middle C (`play_sound.gd`'s bind: "baseline
    # byte 60"), with its first instrument already loaded, even when notes come
    # before the instruction that names it.
    octave, base = 5, 60
    instrument, tuning, adsr1, adsr2 = -1, 0, 0, 0
    first = next((event[2][0] for event in events
                  if event[0] == "op" and event[1] == INSTRUMENT and event[2]), None)
    if first is not None and 0 <= first + 1 < len(instruments):
        instrument = first + 1
        inst = instruments[instrument]
        tuning, adsr1, adsr2 = inst.tuning, inst.adsr1, inst.adsr2
    dynamics, pan, bend, gate = 0x7F, 0, 0, 15
    noise = None
    slur = False
    repeats = []
    notes = []
    current = None
    now = 0.0
    limit = most_seconds * RATE
    index = 0
    steps = 0

    def tick():
        bpm = tempo * 256.0 / 218.0 if tempo else 120.0
        return RATE * 60.0 / (bpm * TICKS_A_BEAT)

    def held(ticks):
        if gate == 15:
            count = ticks - 1
        elif gate == 16:
            count = ticks
        else:
            count = (ticks * gate) >> 4
        return max(1, count) * tick()

    def let_go(at):
        if current is not None:
            current.off = min(current.off, int(at))

    while index < len(events) and now < limit and steps < 20000:
        steps += 1
        event = events[index]
        index += 1
        if event[0] == "note":
            _kind, key, ticks = event
            if key < 12:
                if current is not None and slur:
                    current.bends.append((int(now) - current.start, base + key, bend))
                    current.off = int(now + held(ticks))
                elif instrument >= 0 or noise is not None:
                    left, right = _volumes(dynamics, sound_volume, pan)
                    current = Note(int(now), int(now + held(ticks)), instrument, base + key, tuning,
                                   bend, adsr1, adsr2, left, right, noise)
                    notes.append(current)
            elif key == 12:
                if current is not None:
                    current.off = max(current.off, int(now + held(ticks)))
            else:
                let_go(now)
            now += ticks * tick()
            continue
        _kind, code, args = event
        a = args[0] if args else 0
        if code == END:
            break
        if code == REST:
            let_go(now)
            now += a * tick()
        elif code == FERMATA:
            if current is not None:
                current.off = max(current.off, int(now + a * tick()))
            now += a * tick()
        elif code == OCTAVE:
            octave, base = a, (a * 12) & 0xFF
        elif code == OCTAVE_UP:
            octave, base = min(7, octave + 1), (base + 12) & 0xFF
        elif code == OCTAVE_DOWN:
            octave, base = max(0, octave - 1), (base - 12) & 0xFF
        elif code == REPEAT:
            repeats.append([index, a - 1, octave, base])
        elif code == CODA:
            if repeats:
                top = repeats[-1]
                if top[1] > 0:
                    top[1] -= 1
                    index, octave, base = top[0], top[2], top[3]
                else:
                    repeats.pop()
        elif code == TEMPO:
            tempo = a
        elif code == GATE:
            gate = a
        elif code == INSTRUMENT:
            instrument = a + 1
            if 0 <= instrument < len(instruments):
                inst = instruments[instrument]
                tuning, adsr1, adsr2 = inst.tuning, inst.adsr1, inst.adsr2
        elif code == SLUR_ON:
            slur = True
        elif code == SLUR_OFF:
            slur = False
        elif code == NOISE_ON:
            noise = a & 0x3F
        elif code == NOISE_CLOCK_ADD and noise is not None:
            noise = (noise + a) & 0x3F
        elif code == NOISE_ON_KEEP:
            noise = 0x3F if noise is None else noise
        elif code == NOISE_OFF:
            noise = None
        elif code == ADSR_RESET:
            if 0 <= instrument < len(instruments):
                adsr1, adsr2 = instruments[instrument].adsr1, instruments[instrument].adsr2
        elif code == ATTACK:
            adsr1 = (adsr1 & 0x80FF) | ((a & 0x7F) << 8)
        elif code == DECAY_RATE:
            adsr1 = (adsr1 & 0xFF0F) | ((a & 0x0F) << 4)
        elif code == SUSTAIN_RATE:
            adsr2 = (adsr2 & 0x803F) | 0x4000 | ((a & 0x7F) << 6)
        elif code == RELEASE:
            adsr2 = (adsr2 & 0xFFC0) | (a & 0x3F)
        elif code == DECAY_SUSTAIN and len(args) >= 2:
            adsr1 = (adsr1 & 0xFF00) | ((args[0] & 0x0F) << 4) | (args[1] & 0x0F)
        elif code == ATTACK_MODE:
            adsr1 = (adsr1 & 0x7FFF) | (((a >> 2) & 1) << 15)
        elif code == SUSTAIN_MODE:
            adsr2 = (adsr2 & 0x7FFF) | (((a >> 2) & 1) << 15)
        elif code == RELEASE_MODE:
            adsr2 = (adsr2 & 0xFFDF) | (((a >> 2) & 1) << 5)
        elif code in (BEND_SET, BEND_ADD, BEND_STEP, BEND_ADD16):
            if code == BEND_SET:
                bend = _signed(a) * 32
            elif code == BEND_ADD:
                bend += _signed(a) * 32
            elif code == BEND_STEP:
                bend += _signed(a) * 8
            elif len(args) >= 2:
                value = (args[1] << 8) | args[0]
                bend += value - 0x10000 if value >= 0x8000 else value
            if current is not None:
                key = current.bends[-1][1] if current.bends else current.key
                current.bends.append((int(now) - current.start, key, bend))
        elif code == DYNAMICS:
            dynamics = a & 0xFF
        elif code == DYNAMICS_ADD:
            dynamics = max(0, min(0x7F, dynamics + _signed(a)))
        elif code == DYNAMICS_RAMP and len(args) >= 2:
            dynamics = max(0, min(0x7F, _signed(args[1])))
        elif code == PAN:
            pan = a
    return [note for note in notes if note.start < limit]


# =============================================================================
# The voice
# =============================================================================

_DEN = [1 if r < 48 else 1 << ((r >> 2) - 11) for r in range(128)]
_INC = [((7 - (r & 3)) << (11 - (r >> 2))) if r < 48 else 7 - (r & 3) for r in range(128)]
_DEC = [((-8 + (r & 3)) * (1 << (11 - (r >> 2)))) if r < 48 else -8 + (r & 3) for r in range(128)]


def envelope(adsr1: int, adsr2: int, off: int, length: int) -> np.ndarray:
    """The ADSR envelope (0-1023) for `length` samples, let go at `off`
    (PCSX-Redux's, as `fft_adsr_envelope.cpp`). Shorter when it ends."""
    sustain_level = adsr1 & 0x0F
    decay_rate = (adsr1 >> 4) & 0x0F
    attack_rate = (adsr1 >> 8) & 0x7F
    attack_exp = (adsr1 >> 15) & 1
    release_rate = adsr2 & 0x1F
    release_exp = (adsr2 >> 5) & 1
    sustain_rate = (adsr2 >> 6) & 0x7F
    sustain_exp = (adsr2 >> 15) & 1
    sustain_up = 1 - ((adsr2 >> 14) & 1)
    levels, counts = [], []
    level = 0
    t = 0
    state = "attack"

    def emit(value, count):
        if count > 0:
            levels.append(value)
            counts.append(count)

    while t < length:
        if state != "release" and t >= off:
            state = "release"
        if state == "attack":
            rate = attack_rate
            if attack_exp and level >= 0x6000:
                rate = min(rate + 8, 127)
            den, inc = _DEN[rate], _INC[rate]
            stop = min(off, length)
            limit = 0x6000 if attack_exp and level < 0x6000 else 32767
            steps = max(1, -(-(limit - level) // max(1, inc)))
            span = min(stop - t, steps * den)
            done = span // den
            # The level after each whole step, held for `den` samples.
            for k in range(done):
                emit(level, den)
                level += inc
            rest = span - done * den
            emit(level, rest)
            t += span
            if level >= 32767:
                level, state = 32767, "decay"
            continue
        if state == "decay":
            rate = min(decay_rate * 4, 127)
            den, dec = _DEN[rate], _DEC[rate]
            while t < min(off, length) and ((level >> 11) & 0x0F) > sustain_level:
                span = min(den, min(off, length) - t)
                emit(level, span)
                t += span
                level += (dec * level) >> 15 if release_exp else dec
                level = max(level, 0)
            if t < min(off, length):
                state = "sustain"
            continue
        if state == "sustain":
            rate = sustain_rate
            stop = min(off, length)
            while t < stop:
                if sustain_up:
                    r = min(rate + 8, 127) if sustain_exp and level >= 0x6000 else rate
                    step = _INC[r]
                    den = _DEN[r]
                else:
                    den = _DEN[rate]
                    step = (_DEC[rate] * level) >> 15 if sustain_exp else _DEC[rate]
                span = min(den, stop - t)
                if (sustain_up and level >= 32767) or (not sustain_up and level <= 0) or step == 0:
                    emit(level, stop - t)
                    t = stop
                    break
                emit(level, span)
                t += span
                level = max(0, min(32767, level + step))
            continue
        # release
        rate = min(release_rate * 4, 127)
        den, dec = _DEN[rate], _DEC[rate]
        while t < length and level > 0:
            span = min(den, length - t)
            emit(level, span)
            t += span
            level += (dec * level) >> 15 if release_exp else dec
        break
    if not counts:
        return np.zeros(0, dtype=np.int64)
    out = np.repeat(np.array(levels, dtype=np.int64), np.array(counts, dtype=np.int64))
    return out >> 5


_NOISE_CACHE = {}
_NOISE_ADD = (1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0,
              1, 1, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1,
              1, 0, 1, 0, 0, 1)
_NOISE_FREQ = (0, 84, 140, 180, 210)


def noise(clock: int, length: int) -> np.ndarray:
    """The SPU's noise at a clock (PCSX-Redux's `NoiseClock`), `length` samples."""
    cached = _NOISE_CACHE.get(clock)
    if cached is None or len(cached) < length:
        value, count = 0x8000, 0
        level = (0x8000 >> (clock >> 2)) << 16
        out = np.empty(max(length, RATE), dtype=np.int64)
        for i in range(len(out)):
            count += 0x10000 + _NOISE_FREQ[clock & 3]
            if (count & 0xFFFF) >= _NOISE_FREQ[4]:
                count += 0x10000 - _NOISE_FREQ[clock & 3]
            if count >= level:
                while count >= level:
                    count -= level
                value = ((value << 1) | _NOISE_ADD[(value >> 10) & 63]) & 0xFFFF
            out[i] = value - 0x10000 if value >= 0x8000 else value
        cached = _NOISE_CACHE[clock] = out
    return cached[:length]


def render_note(note: Note, instruments: list, length: int) -> np.ndarray:
    """A note's voice, `(n, 2)` samples, n up to `length` (its cut)."""
    env = envelope(note.adsr1, note.adsr2, note.off - note.start, length)
    n = len(env)
    if n == 0:
        return np.zeros((0, 2), dtype=np.int64)
    if note.noise is not None:
        source = noise(note.noise, n)
    else:
        if not 0 <= note.instrument < len(instruments):
            return np.zeros((0, 2), dtype=np.int64)
        pcm, loop = instruments[note.instrument].samples()
        if len(pcm) == 0:
            return np.zeros((0, 2), dtype=np.int64)
        steps = np.full(n, note_pitch(note.adjusted()) << 4, dtype=np.int64)
        for after, key, bend in note.bends:
            if 0 <= after < n:
                steps[after:] = note_pitch(note.adjusted(key, bend)) << 4
        total = np.cumsum(steps) - steps
        decoded = total >> 16
        place = total & 0xFFFF
        rows = _gauss()[(place >> 8) & 0xFF]
        taps = np.stack([decoded - 4, decoded - 3, decoded - 2, decoded - 1], axis=1)
        valid = taps >= 0
        size = len(pcm)
        if loop >= 0 and size > loop:
            span = size - loop
            wrapped = np.where(taps >= size, loop + (taps - loop) % span, taps)
        else:
            wrapped = taps
            ended = np.nonzero(decoded - 1 >= size)[0]
            if len(ended):
                n = int(ended[0])
                env, wrapped, valid, rows = env[:n], wrapped[:n], valid[:n], rows[:n]
        values = np.where(valid, pcm[np.clip(wrapped, 0, size - 1)], 0)
        mixed = np.sum((rows * values) & ~2047, axis=1) >> 11
        source = np.clip(mixed, -32768, 32767)
    sample = (source * env) // 1023
    left = (sample * note.left) >> 14
    right = (sample * note.right) >> 14
    return np.stack([left, right], axis=1)


# =============================================================================
# A sound, and an effect's sounds
# =============================================================================

def render_sound(feds: Feds, instruments: list, sound: int,
                 most_seconds: float = MOST_SECONDS) -> np.ndarray:
    """Sound `sound` of an effect (its pair `sound - 1`), `(n, 2)` int64 samples."""
    pair = sound - 1
    if not 0 <= pair < feds.pairs:
        return np.zeros((0, 2), dtype=np.int64)
    volume = feds.volume(sound)
    limit = int(most_seconds * RATE)
    voices = []
    end = 0
    for channel in (2 * pair, 2 * pair + 1):
        notes = channel_notes(feds.events(channel), instruments, volume, most_seconds)
        for k, note in enumerate(notes):
            cut = notes[k + 1].start if k + 1 < len(notes) else limit
            audio = render_note(note, instruments, max(1, min(limit, cut) - note.start))
            voices.append((note.start, audio))
            end = max(end, note.start + len(audio))
    out = np.zeros((min(limit, end), 2), dtype=np.int64)
    for start, audio in voices:
        if start >= len(out):
            continue
        take = min(len(audio), len(out) - start)
        out[start:start + take] += audio[:take]
    return out


#: An instrument this many bytes long or shorter has no sample to speak of:
#: The Ivalice Chronicles' copy of the bank leaves 36 of them like that.
EMPTY_BYTES = 32


def is_empty(instrument: Instrument) -> bool:
    return instrument.size <= EMPTY_BYTES


def empty_instruments(feds: Feds, instruments: list, sounds) -> list:
    """The instruments `sounds` play notes on that the bank has no sample for
    (empty, or past its end), in order."""
    out = set()
    for sound in set(sounds):
        pair = sound - 1
        if not 0 <= pair < feds.pairs:
            continue
        for channel in (2 * pair, 2 * pair + 1):
            for note in channel_notes(feds.events(channel), instruments, feds.volume(sound)):
                if note.noise is not None:
                    continue
                if not 0 <= note.instrument < len(instruments) or is_empty(instruments[note.instrument]):
                    out.add(note.instrument)
    return sorted(out)


@dataclass
class EffectSounds:
    """An effect's sounds, ready to play: 16-bit stereo, `rate` a second."""
    pcm: bytes
    frames: int            # sample frames
    starts: list           # [(seconds, sound)]
    #: the instruments its notes ask for that the bank has no sample for, or
    #: (the remaster's) the names it plays that have no recording
    missing: list = field(default_factory=list)
    rate: int = RATE

    @property
    def seconds(self) -> float:
        return self.frames / self.rate


def render_effect(feds_blob: Optional[bytes], instruments: list, events: list,
                  frame_seconds: list) -> EffectSounds:
    """
    Every sound an effect starts, mixed. `events` are the player's sounds,
    `(frame, part, lane, sound)`; `frame_seconds` how long each effect frame
    lasts (slow motion stretches them).
    """
    if not feds_blob or not events:
        return EffectSounds(b"", 0, [])
    feds = read_feds(feds_blob)
    times = [0.0]
    for seconds in frame_seconds:
        times.append(times[-1] + seconds)
    rendered = {}
    placed = []
    for frame, _part, _lane, sound in events:
        at = times[min(frame, len(times) - 1)]
        if sound not in rendered:
            rendered[sound] = render_sound(feds, instruments, sound)
        placed.append((int(at * RATE), rendered[sound], sound, at))
    length = max([start + len(audio) for start, audio, _s, _a in placed] + [int(times[-1] * RATE)])
    mix = np.zeros((length, 2), dtype=np.int64)
    for start, audio, _sound, _at in placed:
        mix[start:start + len(audio)] += audio
    pcm = np.clip(mix, -32768, 32767).astype("<i2").tobytes()
    return EffectSounds(pcm, length, [(at, sound) for _start, _audio, sound, at in placed],
                        empty_instruments(feds, instruments, rendered))


# =============================================================================
# The remaster's recordings
# =============================================================================

#: Where The Ivalice Chronicles keeps its effects' sounds, under the unpacked game.
SOUND_ARCHIVE = "sound/common/sound.sab"
#: A sound's recording: the resource, then the sound less one, four hexadecimal digits each.
VFX_NAME = "FID_SOUND_VFX_{:04X}{:04X}_WAV"


def vfx_resource(feds_blob: Optional[bytes]) -> Optional[int]:
    """The resource an effect's sound section names the remaster's recordings by (its word at
    0x0A), or None without a sound section."""
    if not feds_blob or len(feds_blob) < 0x18 or bytes(feds_blob[:4]) != b"feds":
        return None
    return struct.unpack_from("<H", feds_blob, 0x0A)[0]


def vfx_name(resource: int, sound: int) -> str:
    """The name of the recording an effect's sound `sound` (1 up) plays, for its `resource`."""
    return VFX_NAME.format(int(resource) & 0xFFFF, (int(sound) - 1) & 0xFFFF)


def tracks_by_name(users: dict) -> dict:
    """
    `{name: [track numbers]}` from an unpacked archive's list of who plays
    each track (`sound_data.parse_track_users`: `{"sound_683": "A, B"}`), the
    tracks in order: a name with several plays them together.
    """
    out = {}
    for stem, names in users.items():
        _head, _, number = str(stem).rpartition("_")
        if not number.isdigit():
            continue
        for name in str(names or "").split(","):
            name = name.strip()
            if name:
                out.setdefault(name, []).append(int(number))
    for tracks in out.values():
        tracks.sort()
    return out


def names_played(resource: Optional[int], events: list) -> list:
    """The names of the recordings an effect's sounds play (`events`, the player's `(frame,
    part, lane, sound)`), in the order first played, each once."""
    if resource is None:
        return []
    out = []
    for _frame, _part, _lane, sound in events:
        name = vfx_name(resource, sound)
        if name not in out:
            out.append(name)
    return out


def _stereo(samples: np.ndarray, channels: int) -> np.ndarray:
    """16-bit samples as `(frames, 2)`: one channel doubled, more than two cut to the first two."""
    frames = samples.reshape(-1, max(1, channels))
    if frames.shape[1] == 1:
        return np.repeat(frames, 2, axis=1)
    return frames[:, :2]


def _at_rate(frames: np.ndarray, rate: int, wanted: int) -> np.ndarray:
    """`(frames, 2)` at `rate` a second made `wanted` a second, read between samples."""
    if rate == wanted or not len(frames):
        return frames
    count = max(1, int(round(len(frames) * wanted / rate)))
    where = np.linspace(0.0, len(frames) - 1, count)
    return np.stack([np.interp(where, np.arange(len(frames)), frames[:, c]) for c in range(2)], axis=1)


def mix_recordings(events: list, frame_seconds: list, resource: Optional[int], recordings: dict,
                   rate: int = 48000) -> EffectSounds:
    """
    Every sound an effect starts, as the remaster plays them: each sound's
    recordings (`recordings[name]`: `[(rate, channels, 16-bit samples)]`,
    played together) from when the effect's timeline starts it (`events`,
    the player's `(frame, part, lane, sound)`; `frame_seconds`, how long each
    effect frame lasts), mixed at `rate`. A name without a recording is
    silent and listed in `missing`.
    """
    if resource is None or not events:
        return EffectSounds(b"", 0, [], [], rate)
    times = [0.0]
    for seconds in frame_seconds:
        times.append(times[-1] + seconds)
    ready = {}
    missing = []
    placed = []
    for frame, _part, _lane, sound in events:
        name = vfx_name(resource, sound)
        if name not in ready:
            layers = [_at_rate(_stereo(np.frombuffer(data, dtype="<i2"), channels).astype(np.int64),
                               layer_rate, rate)
                      for layer_rate, channels, data in recordings.get(name) or []]
            if not layers and name not in missing:
                missing.append(name)
            longest = max((len(layer) for layer in layers), default=0)
            audio = np.zeros((longest, 2), dtype=np.int64)
            for layer in layers:
                audio[:len(layer)] += layer.astype(np.int64)
            ready[name] = audio
        at = times[min(frame, len(times) - 1)]
        placed.append((int(round(at * rate)), ready[name], sound, at))
    length = max([start + len(audio) for start, audio, _s, _a in placed] + [int(times[-1] * rate)])
    mix = np.zeros((length, 2), dtype=np.int64)
    for start, audio, _sound, _at in placed:
        mix[start:start + len(audio)] += audio
    pcm = np.clip(mix, -32768, 32767).astype("<i2").tobytes()
    return EffectSounds(pcm, length, [(at, sound) for _start, _audio, sound, at in placed], missing, rate)
