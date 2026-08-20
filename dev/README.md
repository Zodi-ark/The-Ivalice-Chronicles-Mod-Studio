# dev/

Development tooling. Nothing in here is needed to *run* Mod Studio - it's
here so the main folder holds only what a user is looking for, which is
`The Ivalice Chronicles Mod Studio.py`.

Run everything from the project root, not from inside this folder:

```
python3 dev/audit_nxd_layouts.py
python3 dev/test_migration.py
```

Each script works out the project root itself (`__file__` two levels up), so
the working directory doesn't matter - but the reference data paths below
are resolved relative to the root's *parent*.

## audit_nxd_layouts.py

Cross-checks `constants.py`'s field definitions against the real FF16Tools
`.layout` files, and against a real converted database when one is present.
Run it at the start of a session for a clean baseline: 0 BUG, 0 WARN, 11
INFO is the expected result. The 11 INFO lines are columns that exist in the
layouts but aren't exposed for editing.

Drop a real converted database at `_audit_sample.sqlite` in the project root
to exercise the real-data checks as well.

## The suites

Engine tests, no display needed:

| suite | covers |
|---|---|
| `test_migration.py` | the three-way merge, baseline identification, version detection |
| `test_version_archive.py` | archiving each game version, pruning, the converter cache |
| `test_rebase.py` | merging a mod's own changes onto the game's newer table |
| `test_full_conversion.py` | converting every `.nxd`, and table-to-filename mapping |
| `test_review_completeness.py` | every differing row reaches the review |
| `test_xml_roundtrip.py` | a no-op round trip never alters a mod's XML |
| `test_texture_preview_cache.py` | preview cache keys identify the file, not the name |
| `test_unpack_pack_claiming.py` | a pack isn't retired by an incidental filter match |

Interface tests, which need a display (`xvfb-run -a python3 dev/<name>` on a
headless machine):

| suite | covers |
|---|---|
| `test_game_updates_nav.py` | sidebar structure, page indexing, Status tab |
| `test_game_updates_page.py` | the review, the comparison grid, collapsible sections |
| `test_change_picker.py` | per-change selection and the counts that report it |
| `test_mod_switching.py` | opening a second mod doesn't inherit the first's edits |
| `test_real_migration_flow.py` | the whole flow, end to end, on real data |
| `test_unpack_archive_wiring.py` | unpacking archives the version it just read |
| `test_export_summary.py` | the Export summary reflects Game Updates decisions |
| `test_nested_scroll.py` | the wheel scrolls the thing under the pointer |
| `test_focus_artefacts.py` | no stray focus rings or highlighted dropdowns |

## Reference data

Several suites read real game data, expected beside the project folder:

```
<parent>/refs2/Version 1.4.0 nxd files to sqlite/fft_data.sqlite
<parent>/refs2/Version 1.5.2 nxd files to sqlite/fft_data.sqlite
<parent>/refs/Version 1.5.1 nxd files to sqlite/fft_data.sqlite
<parent>/refs2/fftivc.gameplay.darkknightexpansion/
<parent>/zpack/fftivc.asset.zoditexturepack/
<parent>/xmlerr/, <parent>/cmp/
```

Most take an override as the first argument. A suite whose data is missing
says so and skips rather than failing, so a partial checkout still runs the
rest.

## verify_package.py

Lives beside the project folder rather than inside it, since it inspects a
shipped zip against the working copy. Anything other than `IDENTICAL` means
don't ship:

```
python3 verify_package.py <zip> "<project folder>"
```
