Nex data-format layouts for Final Fantasy Tactics: The Ivalice Chronicles
========================================================================

Source:  https://github.com/Nenkai/fftivc-nex-layouts
Author:  Nenkai
License: MIT - the full text is in LICENSE in this folder.

These are Nenkai's reverse-engineered column definitions for the game's
.nxd tables. They are the authoritative answer to "what type is this
column, and when does the game actually apply it?", and Mod Studio treats
them as such: OverrideEntryData's per-column patch conditions (documented
in constants.py) come straight from OverrideEntryData.layout.

They are bundled for two reasons:

1. So the field documentation in constants.py can be checked against its
   source without going and finding the repo again.
2. So audit_nxd_layouts.py (in the project root) can run offline. That
   script cross-checks how Mod Studio classifies every column against the
   type the layout declares, which is the check that would have caught a
   real bug: OverrideEntryData's Unknown04 was treated as an array when the
   layout declares it a string, so every entry edit silently rewrote a
   column nobody had touched.

Run the audit after touching any nxd field definition, and whenever a new
table is added:

    python3 audit_nxd_layouts.py

Nothing in this folder is read at runtime - Mod Studio does not parse
.layout files. They are reference material and audit input only.
