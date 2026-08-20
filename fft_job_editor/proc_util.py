"""
Small shared helpers for driving external Windows .exe tools (FF16Tools.CLI,
AudioMog) via subprocess, factored out of ff16tools.py so audiomog.py can
reuse the exact same Wine-wrapping/streaming behavior instead of copying it.
"""

from __future__ import annotations

import platform
import subprocess
import threading
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Callable, Optional


def for_platform(exe_path: Path, raw_command: list[str]) -> list[str]:
    """Wraps a command in Wine on non-Windows platforms, since these are Windows executables."""
    if platform.system() != "Windows" and exe_path.suffix.lower() == ".exe":
        return ["wine", str(exe_path)] + raw_command[1:]
    return raw_command


def _no_window_flags() -> dict:
    """
    Keyword arguments that stop a console window flashing up on Windows.

    Every FF16Tools and AudioMog call is a console program, and Windows
    gives each one its own window unless told otherwise. Under the old
    `.py` entry point that went unnoticed - the app already had a console
    of its own, so the children just reused it. Launching without one makes
    each call flash a black box on screen instead, which would have turned
    one visible console into dozens of brief ones.

    `CREATE_NO_WINDOW` only exists on Windows, so this is empty everywhere
    else and the calls are unchanged there.
    """
    if platform.system() != "Windows":
        return {}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {"creationflags": flags, "startupinfo": startupinfo}


def run_streaming(command: list[str], line_cb: Optional[Callable[[str], None]] = None, cwd: Optional[Path] = None) -> int:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(cwd) if cwd else None,
        **_no_window_flags(),
    )
    assert process.stdout is not None
    for line in process.stdout:
        if line_cb:
            line_cb(line.rstrip("\n"))
    process.wait()
    return process.returncode


def run_streaming_with_artifact(
    command: list[str],
    artifact_check: Callable[[], bool],
    cwd: Optional[Path] = None,
    line_cb: Optional[Callable[[str], None]] = None,
    poll_interval: float = 0.3,
    timeout: float = 120.0,
) -> tuple[bool, Optional[int]]:
    """
    Like run_streaming, but doesn't block waiting for the process to exit -
    only for artifact_check() to become True (or `timeout` seconds to
    elapse), polling both alongside each other. Some tools (AudioMog, at
    least with its default shipped settings) can finish their real work
    and write real output to disk without their own process actually
    exiting - a plain blocking wait on the process would hang forever even
    though the thing we actually care about (the output existing) already
    happened. Output lines are still streamed to line_cb as they arrive,
    read on a background thread so a stuck process can't block that either.

    Returns (artifact_found, returncode_or_None) - returncode is None if
    the process hadn't exited yet by the time this returned (either
    because the artifact appeared first, or the timeout was hit). The
    process is left running in the background in that case - not killed,
    since it may just be sitting at a harmless prompt, and killing a
    Windows GUI/console process by pid isn't always clean cross-platform.
    """
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(cwd) if cwd else None,
        **_no_window_flags(),
    )
    assert process.stdout is not None

    line_queue: Queue = Queue()

    def reader() -> None:
        try:
            for line in process.stdout:
                line_queue.put(line.rstrip("\n"))
        except (ValueError, OSError):
            pass  # pipe closed out from under us - nothing more to read

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()

    def drain_lines() -> None:
        try:
            while True:
                line = line_queue.get_nowait()
                if line_cb:
                    line_cb(line)
        except Empty:
            pass

    start = time.monotonic()
    while True:
        drain_lines()

        if artifact_check():
            return True, process.poll()

        exit_code = process.poll()
        if exit_code is not None:
            time.sleep(0.1)  # give the reader thread a moment to catch any final buffered lines
            drain_lines()
            return artifact_check(), exit_code

        if time.monotonic() - start > timeout:
            drain_lines()
            return artifact_check(), None

        time.sleep(poll_interval)
