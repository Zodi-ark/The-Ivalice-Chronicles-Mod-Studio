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

Requires:  Python 3.10+ and PySide6 (`pip install PySide6`). The frozen
           Windows build bundles both, so a user running the .exe installs
           nothing.

This file is also what `packaging/ModStudio.spec` hands to PyInstaller, and
PyInstaller decides what to bundle by following imports from here. That
makes the import below load-bearing in a way it does not look: for a long
time it read `mod_studio.gui.app`, and every frozen build was therefore the
legacy Tkinter interface, with no part of the Qt work in it. Both interfaces
ran fine from source, so nothing surfaced it. `dev/trace_entry_imports.py`
now walks the graph from this file and fails if the wrong one is reachable.

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

    Two mechanisms, and the ORDER between them is deliberate:

    1. `startup_error.txt` next to this file, written FIRST. This is the one
       that survives the toolkit being what broke, and it is what a user
       attaches to a bug report.
    2. A Qt message box, attempted afterwards. Best effort: PySide6 is the
       most likely thing to be missing, and a dialog drawn with the toolkit
       that just failed cannot be relied on.

    The file used to be written second, matching the Tkinter version this
    replaced. That quietly made the reliable half depend on the unreliable
    one, because the dialog is MODAL - it blocks until somebody clicks OK.
    A user who walks away, or a dialog that opens off-screen or fails to
    paint, meant the file was never written at all and the crash left no
    trace. Found by a probe that hung for 120 seconds waiting for a click
    that was never coming.

    The dialog reuses an existing QApplication if one is already up. A crash
    after `main()` has constructed its own would otherwise hit Qt's "A
    QApplication instance already exists" fatal error and replace a readable
    message with an abort.
    """
    import traceback

    detail = "".join(traceback.format_exception(type(error), error, error.__traceback__))

    try:
        from pathlib import Path

        Path(__file__).resolve().parent.joinpath("startup_error.txt").write_text(
            detail, encoding="utf-8")
    except Exception:  # noqa: BLE001 - a read-only folder isn't worth a second crash
        pass

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "The Ivalice Chronicles Mod Studio couldn't start",
            f"{type(error).__name__}: {error}\n\n"
            f"The full details have been written to startup_error.txt next to "
            f"the program.\n\nIf PySide6 is missing, install it: "
            f"pip install PySide6",
        )
        del app  # nothing further is drawn; let teardown proceed normally
    except BaseException:  # noqa: BLE001 - the dialog itself may be what's broken
        pass

    # Still print, for anyone who ran this from a terminal. With no console
    # sys.stdout is None and print() quietly does nothing, which is exactly
    # what's wanted here.
    print(detail)


if __name__ == "__main__":
    try:
        from mod_studio.qt.app import main

        # Qt's main() returns the event loop's exit code. The Tkinter one
        # returned None, so this used to be discarded - which meant a
        # non-zero exit from Qt was reported to the shell as success.
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as error:  # noqa: BLE001 - last line of defence
        _report_startup_failure(error)
        sys.exit(1)
