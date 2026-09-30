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

Requires:  Python 3.10+ and PySide6, and Pillow, numpy and scipy for the
           parts that use them:
               pip install PySide6-Essentials pillow numpy scipy
           The frozen Windows build bundles all of these, so a user running
           the .exe installs none of them. The bundled FF16Tools and
           AudioMog need the .NET 9 Runtime and .NET Framework 4.7.2
           either way: README.md, Requirements.

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


#: Where a crash leaves its record, under `local_data/`.
CRASH_LOG_NAME = "crash_log.txt"


def _keep_a_crash_record() -> None:
    """
    Makes a crash leave a note behind, in `local_data/crash_log.txt`.

    Under `pythonw.exe` a crash has nowhere to print. The window simply
    goes, and the only trace is a line in Windows' Event Viewer naming a
    system file - which is exactly how the UI Layouts crash was reported:
    "Faulting module name: ucrtbase.dll, Exception code: 0xc0000409". That
    says the program stopped itself; it cannot say where.

    Two things are recorded, both only when something goes wrong:

    - **Where every thread was**, from Python's own `faulthandler`: a
      traceback per thread on a fatal signal or a Windows fault. Qt ends
      the program with `abort()` when it gives up, and `faulthandler`
      catches that too.
    - **What Qt said last.** When Qt gives up it says why first ("QThread:
      Destroyed while thread is still running") and then stops. The last
      fifty messages are kept in memory and written out only on that final
      one, so an ordinary run writes nothing.

    The file is opened at start-up - a crash cannot open a file - and on a
    clean exit it is cut back to what it held before, and deleted if that
    was nothing. So it exists after a run only if that run crashed, and it
    keeps earlier crashes until someone deletes it.

    Never stops the program starting: every step is best effort.
    """
    try:
        import atexit
        import collections
        import datetime
        import faulthandler
        import os

        from mod_studio import paths

        path = paths.local_data_dir() / CRASH_LOG_NAME
        record = open(path, "a", encoding="utf-8")
        before = record.tell()
        record.write(f"--- The Ivalice Chronicles Mod Studio, started "
                     f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} ---\n")
        record.flush()
        faulthandler.enable(file=record, all_threads=True)

        recent = collections.deque(maxlen=50)

        def qt_message(kind, _context, message):
            from PySide6.QtCore import QtMsgType

            recent.append(message)
            if kind == QtMsgType.QtFatalMsg:
                try:
                    record.write("Qt's last messages, oldest first:\n")
                    record.writelines(f"  {line}\n" for line in recent)
                    record.flush()
                except Exception:                              # noqa: BLE001
                    pass
            # Still printed, for anyone running from a terminal. Under
            # pythonw there is no stderr and this does nothing.
            if sys.stderr is not None:
                try:
                    sys.stderr.write(message + "\n")
                except Exception:                              # noqa: BLE001
                    pass

        def tidy_up():
            try:
                faulthandler.disable()
                record.truncate(before)
                record.close()
                if before == 0:
                    os.remove(path)
            except Exception:                                  # noqa: BLE001
                pass

        # Registered BEFORE PySide is first imported, because exit handlers
        # run newest first and PySide tears the application down in one of
        # its own. Registered after it, this would switch the record off
        # before that teardown - which is where a thread still running at
        # exit brings the program down.
        atexit.register(tidy_up)

        try:
            from PySide6.QtCore import qInstallMessageHandler

            qInstallMessageHandler(qt_message)
        except Exception:                                      # noqa: BLE001
            pass
    except Exception:                                          # noqa: BLE001
        pass


if __name__ == "__main__":
    # First, so a crash anywhere after this leaves a record.
    _keep_a_crash_record()
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
