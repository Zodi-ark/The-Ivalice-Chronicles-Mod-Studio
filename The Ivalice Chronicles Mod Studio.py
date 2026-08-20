#!/usr/bin/env python3
"""
Entry point for The Ivalice Chronicles Mod Studio.

This is the file that starts the program - run it (or on most Windows
setups, double-click it) to launch the app.

Run with:  python3 "The Ivalice Chronicles Mod Studio.py"
Requires:  Python 3.10+ with tkinter (python3-tk on Linux; bundled with the
           official python.org installer on Windows).

See README.md for what it does and HANDOFF.md for the research/decisions
record behind how it's built.
"""
from fft_job_editor.gui.app import main

if __name__ == "__main__":
    main()
