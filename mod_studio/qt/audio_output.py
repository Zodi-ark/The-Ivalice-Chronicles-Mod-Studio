"""
Sound for the loop editor: plays a track from any frame, jumping back at the
loop's end when asked, and says which frame is SOUNDING - from the sound
device, not from a clock.

Reported from real use: "when I click play there is a delay before the audio
comes through yet on the ui I can see the play head moving ... So when the
playhead hits the end of the track and stops my delayed audio also stops".
The cause: the page followed the playhead by a clock started when
`winsound.PlaySound` returned - and PlaySound returns BEFORE the sound
starts, having only begun loading a file that held minutes of looped audio.
The playhead ran ahead of the sound by that delay, and stopping at the
playhead's end cut the sound's end off by the same amount.

So nothing here trusts a clock while there is a device to ask. On Windows
the audio goes to the waveOut API (winmm.dll, always present - the layer
PlaySound itself sits on) in small buffers, and `waveOutGetPosition` says
how many samples have actually been played. The playhead is that position,
mapped back through what was written; playback ends when the device has
played the last sample, not when a timer thinks it should have.

Streaming also means the loop is never baked into a file. Each buffer is cut
from the track as it is needed, wrapping at the loop's end, so moving a flag
while it plays is heard a moment later with no rebuild and no gap.

Off Windows, `ClockDevice` plays nothing and consumes audio at the real rate
by the clock - for developing off Windows, and for the suite, which drives
its clock by hand. Qt's own audio output would do this too, but it lives in
the PySide6 Addons wheel, which the build leaves out.
"""
from __future__ import annotations

import ctypes
import sys
import time
from collections import deque

from PySide6.QtCore import QObject, QTimer, Signal

#: Each buffer's length: short enough that a moved flag is heard quickly,
#: long enough that refilling on a timer never falls behind.
CHUNK_SECONDS = 0.05
#: Buffers queued at once - 0.4 s of audio between the page and silence.
SLOTS = 8
#: How long the last buffer may take to be reported played, before the
#: device is taken at its word that it has finished.
FINISH_GRACE_SECONDS = 0.5


class LoopStream:
    """
    A track cut into the order it should be heard: from `start_frame`, and -
    looping - back to `loop_start` each time it reaches `loop_end`.

    Remembers where each piece came from, so a device position can be turned
    back into a frame of the track.

    The loop only catches a reader that reaches its end from before it: a
    reader already past the end plays straight on, as audio editors do.
    """

    def __init__(self, pcm, start_frame, loop_start=None, loop_end=None,
                 looping=False):
        self.pcm = pcm
        self.total = pcm.frames
        self.frame = max(0, min(int(start_frame), self.total))
        self.out_frames = 0
        self._segments = deque()           # (out_start, src_start, length)
        self.loop = None
        self.set_loop(loop_start, loop_end, looping)

    def set_loop(self, loop_start, loop_end, looping) -> None:
        """Changes the loop for everything not yet cut."""
        if (looping and loop_start is not None and loop_end is not None
                and 0 <= int(loop_start) < int(loop_end) <= self.total):
            self.loop = (int(loop_start), int(loop_end))
        else:
            self.loop = None

    def next_chunk(self, frames: int):
        """Up to `frames` frames of audio, or None once nothing is left."""
        frame_bytes = 2 * self.pcm.channels
        parts = []
        wanted = frames
        while wanted > 0:
            looping_here = self.loop is not None and self.frame < self.loop[1]
            stop = self.loop[1] if looping_here else self.total
            if self.frame >= stop:
                break
            take = min(wanted, stop - self.frame)
            parts.append(self.pcm.data[self.frame * frame_bytes:
                                       (self.frame + take) * frame_bytes])
            self._segments.append((self.out_frames, self.frame, take))
            self.out_frames += take
            self.frame += take
            wanted -= take
            if looping_here and self.frame >= self.loop[1]:
                self.frame = self.loop[0]
        return b"".join(parts) if parts else None

    def frame_at(self, out_position: int):
        """The track frame sounding `out_position` frames in, or None past all of it."""
        segments = self._segments
        while len(segments) > 1 and segments[0][0] + segments[0][2] <= out_position:
            segments.popleft()
        for out_start, src_start, length in segments:
            if out_start <= out_position < out_start + length:
                return src_start + (out_position - out_start)
        return None


class ClockDevice:
    """
    Plays nothing, at the real rate: its position is how much of what was
    written the clock says has gone by. Off Windows, and in the suite, which
    passes its own `clock`.
    """
    slots = SLOTS

    def __init__(self, rate, channels, chunk_bytes, clock=time.monotonic):
        self._rate = rate
        self._frame_bytes = 2 * channels
        self._clock = clock
        self._start = None
        self._written = 0
        self._ends = [0] * SLOTS
        #: Everything written, and the position when closed - for the suite.
        self.data = bytearray()
        self.closed_at = None

    def write(self, slot, data) -> None:
        if self._start is None:
            self._start = self._clock()
        self._written += len(data) // self._frame_bytes
        self._ends[slot] = self._written
        self.data += data

    def idle(self, slot) -> bool:
        return self._ends[slot] <= self.position()

    def position(self) -> int:
        if self._start is None:
            return 0
        return min(self._written, int((self._clock() - self._start) * self._rate))

    def close(self) -> None:
        self.closed_at = self.position()


# -- the waveOut API ---------------------------------------------------------------
#
# Laid out with fixed-width types so the layouts can be checked on any
# machine (`dev/test_audio_output.py`): on 64-bit Windows WAVEHDR is 48 bytes
# and MMTIME 12, and WAVEFORMATEX is byte-packed at 18, as mmeapi.h declares.

class WAVEFORMATEX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("wFormatTag", ctypes.c_uint16), ("nChannels", ctypes.c_uint16),
                ("nSamplesPerSec", ctypes.c_uint32),
                ("nAvgBytesPerSec", ctypes.c_uint32),
                ("nBlockAlign", ctypes.c_uint16), ("wBitsPerSample", ctypes.c_uint16),
                ("cbSize", ctypes.c_uint16)]


class WAVEHDR(ctypes.Structure):
    _fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", ctypes.c_uint32),
                ("dwBytesRecorded", ctypes.c_uint32), ("dwUser", ctypes.c_size_t),
                ("dwFlags", ctypes.c_uint32), ("dwLoops", ctypes.c_uint32),
                ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]


class _MMTimeValue(ctypes.Union):
    _fields_ = [("ms", ctypes.c_uint32), ("sample", ctypes.c_uint32),
                ("cb", ctypes.c_uint32), ("ticks", ctypes.c_uint32),
                ("smpte", ctypes.c_uint8 * 8), ("songptrpos", ctypes.c_uint32)]


class MMTIME(ctypes.Structure):
    _fields_ = [("wType", ctypes.c_uint32), ("u", _MMTimeValue)]


WAVE_MAPPER = 0xFFFFFFFF
WAVE_FORMAT_PCM = 1
CALLBACK_NULL = 0
WHDR_DONE = 0x1
TIME_MS, TIME_SAMPLES, TIME_BYTES = 0x1, 0x2, 0x4

#: What the codes worth saying in words mean.
_MM_ERRORS = {2: "no sound output device was found",
              4: "the sound device is in use by something else",
              6: "no sound driver is installed",
              32: "the sound device can't play this format"}


def _check(result: int, call: str) -> None:
    if result:
        why = _MM_ERRORS.get(result, f"{call} failed with code {result}")
        raise OSError(f"Couldn't use the sound device: {why}.")


def _winmm():
    api = ctypes.WinDLL("winmm")
    handle = ctypes.c_void_p
    api.waveOutOpen.argtypes = [ctypes.POINTER(handle), ctypes.c_uint,
                                ctypes.POINTER(WAVEFORMATEX), ctypes.c_size_t,
                                ctypes.c_size_t, ctypes.c_uint32]
    for name in ("waveOutPrepareHeader", "waveOutUnprepareHeader", "waveOutWrite"):
        getattr(api, name).argtypes = [handle, ctypes.POINTER(WAVEHDR), ctypes.c_uint]
    api.waveOutGetPosition.argtypes = [handle, ctypes.POINTER(MMTIME), ctypes.c_uint]
    api.waveOutReset.argtypes = [handle]
    api.waveOutClose.argtypes = [handle]
    for name in ("waveOutOpen", "waveOutPrepareHeader", "waveOutUnprepareHeader",
                 "waveOutWrite", "waveOutGetPosition", "waveOutReset",
                 "waveOutClose"):
        getattr(api, name).restype = ctypes.c_uint
    return api


class WinMMDevice:
    """
    The waveOut API: buffers played in the order written, and the device's
    own count of samples played. Polled from the page's timer - no callback
    runs on a system thread. Every buffer and header is held here until the
    device has handed it back, because the device reads them after the call
    that queued them has returned.
    """
    slots = SLOTS

    def __init__(self, rate, channels, chunk_bytes):
        self._api = _winmm()
        self._frame_bytes = 2 * channels
        self._rate = rate
        fmt = WAVEFORMATEX(WAVE_FORMAT_PCM, channels, rate,
                           rate * self._frame_bytes, self._frame_bytes, 16, 0)
        self._handle = ctypes.c_void_p()
        _check(self._api.waveOutOpen(ctypes.byref(self._handle), WAVE_MAPPER,
                                     ctypes.byref(fmt), 0, 0, CALLBACK_NULL),
               "waveOutOpen")
        self._buffers = [ctypes.create_string_buffer(chunk_bytes) for _ in range(SLOTS)]
        self._headers = [WAVEHDR() for _ in range(SLOTS)]
        self._queued = [False] * SLOTS

    def write(self, slot, data) -> None:
        buffer = self._buffers[slot]
        ctypes.memmove(buffer, data, len(data))
        header = self._headers[slot]
        header.lpData = ctypes.cast(buffer, ctypes.c_void_p)
        header.dwBufferLength = len(data)
        header.dwBytesRecorded = header.dwUser = header.dwFlags = 0
        header.dwLoops = header.reserved = 0
        header.lpNext = None
        _check(self._api.waveOutPrepareHeader(self._handle, ctypes.byref(header),
                                              ctypes.sizeof(WAVEHDR)),
               "waveOutPrepareHeader")
        self._queued[slot] = True
        _check(self._api.waveOutWrite(self._handle, ctypes.byref(header),
                                      ctypes.sizeof(WAVEHDR)), "waveOutWrite")

    def idle(self, slot) -> bool:
        if not self._queued[slot]:
            return True
        header = self._headers[slot]
        if not header.dwFlags & WHDR_DONE:
            return False
        self._api.waveOutUnprepareHeader(self._handle, ctypes.byref(header),
                                         ctypes.sizeof(WAVEHDR))
        self._queued[slot] = False
        return True

    def position(self) -> int:
        when = MMTIME()
        when.wType = TIME_SAMPLES
        _check(self._api.waveOutGetPosition(self._handle, ctypes.byref(when),
                                            ctypes.sizeof(MMTIME)),
               "waveOutGetPosition")
        if when.wType == TIME_SAMPLES:
            return when.u.sample
        if when.wType == TIME_BYTES:
            return when.u.cb // self._frame_bytes
        if when.wType == TIME_MS:
            return when.u.ms * self._rate // 1000
        return 0

    def close(self) -> None:
        # Reset hands every queued buffer back marked done; only then may they
        # be unprepared, and only then closed.
        self._api.waveOutReset(self._handle)
        for slot, header in enumerate(self._headers):
            if self._queued[slot]:
                self._api.waveOutUnprepareHeader(self._handle, ctypes.byref(header),
                                                 ctypes.sizeof(WAVEHDR))
                self._queued[slot] = False
        self._api.waveOutClose(self._handle)


def default_device(rate, channels, chunk_bytes):
    if sys.platform == "win32":
        return WinMMDevice(rate, channels, chunk_bytes)
    return ClockDevice(rate, channels, chunk_bytes)


class LoopPlayer(QObject):
    """Plays a `sound_data.Pcm16` through a device, and says where it is."""

    #: The device has played the last of it - not before.
    finished = Signal()

    def __init__(self, parent=None, device_factory=None):
        super().__init__(parent)
        self.device_factory = device_factory or default_device
        self._device = None
        self._stream = None
        self._exhausted = False
        self._drained_at = None
        self._chunk_frames = 1
        self._pump_timer = QTimer(self)
        self._pump_timer.setInterval(15)
        self._pump_timer.timeout.connect(self.pump)

    @property
    def playing(self) -> bool:
        return self._device is not None

    def play(self, pcm, start_frame, loop_start=None, loop_end=None,
             looping=False) -> None:
        self.stop()
        self._stream = LoopStream(pcm, start_frame, loop_start, loop_end, looping)
        self._chunk_frames = max(1, int(pcm.sample_rate * CHUNK_SECONDS))
        self._device = self.device_factory(
            pcm.sample_rate, pcm.channels, self._chunk_frames * 2 * pcm.channels)
        self._exhausted = False
        self._drained_at = None
        self.pump()
        self._pump_timer.start()

    def update_loop(self, loop_start, loop_end, looping) -> None:
        """A loop change for what isn't queued yet - no restart, no gap."""
        if self._stream is not None:
            self._stream.set_loop(loop_start, loop_end, looping)

    def pump(self) -> None:
        """Refills whatever the device has finished with; notices the end."""
        device = self._device
        if device is None:
            return
        if not self._exhausted:
            for slot in range(device.slots):
                if not device.idle(slot):
                    continue
                data = self._stream.next_chunk(self._chunk_frames)
                if data is None:
                    self._exhausted = True
                    break
                device.write(slot, data)
        if self._exhausted and all(device.idle(s) for s in range(device.slots)):
            # Every buffer is back. Wait for the device to say the last
            # sample has been PLAYED, with a grace period for a driver that
            # never quite counts to the end.
            if self._drained_at is None:
                self._drained_at = time.monotonic()
            if (device.position() >= self._stream.out_frames
                    or time.monotonic() - self._drained_at > FINISH_GRACE_SECONDS):
                self.stop()
                self.finished.emit()

    def current_frame(self):
        """The frame of the track being heard now, or None when not playing."""
        if self._device is None or self._stream is None:
            return None
        frame = self._stream.frame_at(self._device.position())
        return frame if frame is not None else self._stream.frame

    def stop(self) -> None:
        self._pump_timer.stop()
        device, self._device = self._device, None
        if device is not None:
            try:
                device.close()
            except Exception:                                 # noqa: BLE001
                pass
