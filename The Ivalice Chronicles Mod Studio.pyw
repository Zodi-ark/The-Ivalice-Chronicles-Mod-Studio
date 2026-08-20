#!/usr/bin/env python3
"""
Entry point for The Ivalice Chronicles Mod Studio.

This is the file that starts the program - double-click it on Windows, or
run it from a terminal.

The extension is `.pyw`, not `.py`, and that is the whole reason no black
console window appears alongside the app on Windows: the `.py` association
runs `python.exe`, which always allocates a console, while `.pyw` runs
`pythonw.exe`, which doesn't. Nothing else about how it starts is different.

To see console output anyway - handy if something misbehaves - invoke the
interpreter explicitly, which ignores the extension:

    python "The Ivalice Chronicles Mod Studio.pyw"

On Linux and macOS the extension means nothing; run it as before:

    python3 "The Ivalice Chronicles Mod Studio.pyw"

Requires:  Python 3.10+ with tkinter (python3-tk on Linux; bundled with the
           official python.org installer on Windows).

See README.md for what it does and HANDOFF.md for the research/decisions
record behind how it's built.
"""
import sys


def _report_startup_failure(error: BaseException) -> None:
    """
    Shows a crash during startup, rather than letting it vanish.

    Under `pythonw.exe` there is no console, so an exception before the
    window exists would print to nowhere and the program would simply fail
    to appear - the one real cost of dropping the console, and worth paying
    only because it can be bought back like this.

    Tkinter is what's most likely to be missing, so the dialog is attempted
    defensively and falls back to writing a file next to this script.
    """
    import traceback

    detail = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "The Ivalice Chronicles Mod Studio couldn't start",
            f"{type(error).__name__}: {error}\n\n"
            f"The full details have been written to startup_error.txt next to "
            f"the program.\n\nIf tkinter is missing, install it: python3-tk on "
            f"Linux, or use the official python.org installer on Windows.",
        )
        root.destroy()
    except Exception:  # noqa: BLE001 - the dialog itself may be what's broken
        pass

    try:
        from pathlib import Path

        Path(__file__).resolve().parent.joinpath("startup_error.txt").write_text(
            detail, encoding="utf-8")
    except Exception:  # noqa: BLE001 - a read-only folder isn't worth a second crash
        pass

    # Still print, for anyone who ran this from a terminal. With no console
    # sys.stdout is None and print() quietly does nothing, which is exactly
    # what's wanted here.
    print(detail)


if __name__ == "__main__":
    try:
        from fft_job_editor.gui.app import main

        main()
    except BaseException as error:  # noqa: BLE001 - last line of defence
        _report_startup_failure(error)
        sys.exit(1)
