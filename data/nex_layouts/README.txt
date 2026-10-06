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

Mod Studio also reads them while it runs (mod_studio/nxd_layouts.py):
which tables have a file per language, and which of their columns are
text. The copies FF16Tools converts the game's tables with are its own,
in tools/FF16Tools/win-x64/Nex/Layouts/ffto/, and are kept the same.

Updated 6 October 2026
----------------------

From the copy of Nenkai's repository Zodi supplied that day, which
differed from the one bundled before in one file: RefinedBgTexture's
Unknown20 is an int[], where it was read as a string[]. Read as text,
its numbers came out as empty or one-character strings ("", "\x08",
"\x01"). FF16Tools' copy was updated with it, so a database converted
before then still holds the old reading: convert the game data again
before exporting a mod with RefinedBgTexture rows in it (General Setup,
Advanced options, the unpacked game's nxd folder, Convert to editable
database; unpacking again doesn't, while a database is loaded).
