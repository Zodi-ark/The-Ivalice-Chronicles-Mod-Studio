"""
Entry point for the Qt interface.

    python3 -m mod_studio.qt.app

Runs alongside the Tkinter one rather than replacing it. Both front ends sit
over the same `WizardState` and the same engine, which is what promoting
WizardState out of `gui/` bought - running both during the migration costs a
launcher flag, not a fork.

The Tkinter launcher (`The Ivalice Chronicles Mod Studio.pyw`) is still the
one to use for real work. This one shows the tabs that have been rebuilt and
says so for the ones that have not.
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from .. import constants as c
from .. import item_xml_io, paths, xml_io
from ..state import WizardState
from .pages.data_browser import DataBrowserPage
from .pages.compare import ComparePage
from .pages.job_commands import JobCommandsPage
from .pages.jobs import JobsPage
from .pages.table_editor import TableEditorPage
from .pages.export import ExportPage
from .pages.abilities import AbilitiesPage
from .pages.items import ItemsPage
from .pages.encounters import EncountersPage
from .pages.poaching import PoachingPage
from .pages.review import ReviewPage
from .pages.setup import SetupPage
from .pages.sounds import SoundsPage
from .pages.textures import TexturesPage
from .shell import MainWindow, application_icon


def load_reference_tables(state: WizardState) -> list:
    """
    Fills the state from the bundled reference XML.

    Returns a list of complaints rather than raising. A missing table means
    one tab has nothing to show, which is worth saying out loud - it is not
    worth refusing to start over.
    """
    problems = []
    data_dir = paths.bundled_data_dir()

    try:
        state.job_records, _ = xml_io.load_job_table(data_dir / "JobData.xml")
    except Exception as exc:                                  # noqa: BLE001
        problems.append(f"Jobs: {exc}")

    try:
        state.job_command_records, state.job_command_version = (
            xml_io.load_job_command_table(data_dir / "JobCommandData.xml"))
    except Exception as exc:                                  # noqa: BLE001
        problems.append(f"Job Commands: {exc}")

    # Ability names AND types, from the same file, and neither was being
    # loaded here at all - the Tkinter interface has read both since the
    # beginning (gui/step_setup.py).
    #
    # `ability_types` is the one with teeth. It is what separates action
    # abilities from Reaction/Support/Movement ones, so with it empty the
    # Job Commands tab cannot scope its two groups of slots and falls back
    # to offering every ability in both - which means the six R/S/M slots
    # offer Fire. The fallback is deliberate and is still wrong to rely on.
    try:
        state.ability_names = xml_io.load_ability_names(
            data_dir / "AbilityData.xml")
        state.ability_types = xml_io.load_ability_types(
            data_dir / "AbilityData.xml")
    except Exception as exc:                                  # noqa: BLE001
        problems.append(f"Abilities: {exc}")

    problems.extend(load_table_tabs(state))
    return problems


# The generic-table tabs: which spec, which bundled file, and the wording.
# Adding a table here is the whole job - the page itself is driven by the
# spec, so nothing else needs writing.
TABLE_TABS = [
    ("Items", "item", "ItemData.xml",
     "Every item in the game. Pick one on the left, then edit it. Only the "
     "fields you tick are written into your mod."),
    ("Equip Bonus", "item_equip_bonus", "ItemEquipBonusData.xml",
     "The stat bonuses and statuses a piece of equipment grants while worn."),
    ("Treasure Hunter", "map_trap", "MapTrapFormationData.xml",
     "Traps and buried treasure on each map, and what Treasure Hunter turns "
     "them into."),
]


def load_table_tabs(state: WizardState) -> list:
    """
    Loads **every** table in `ALL_SPECS` into the state, reporting failures.

    Not just the three with their own tab. A table needs loading because
    some page reads it, and "has a tab" and "is read by a page" are
    different questions: Items alone reaches seven of these - ItemData plus
    the weapon, armor, shield and accessory tables it links into, plus
    shops - and Abilities reaches three more for its Effect, Unit Animations
    and Base Stats sub-tabs. None of those seven has a tab of its own.

    This used to loop over `TABLE_TABS`, so eight of the eleven bundled XML
    files were never opened. The Items page could not have shown a weapon's
    Power even if it asked, because the records were not in the state to
    ask for - and the failure looked like a thin page rather than a missing
    load, which is why it survived the whole rewrite. The Tkinter interface
    has always looped over `ALL_SPECS` here (`gui/step_setup.py`).

    Keyed by spec rather than by tab, the tab list goes back to being about
    presentation only.
    """
    problems = []
    data_dir = paths.bundled_data_dir()
    if state.item_table_records is None:
        state.item_table_records = {}
    # Titles for the error message, so "item_shops: ..." reads as
    # "Shop Availability: ..." to somebody who has never seen a table key.
    titles = {key: title for title, key, _f, _b in TABLE_TABS}
    for key in item_xml_io.ALL_SPECS:
        filename = c.TABLE_FILENAMES.get(key)
        if filename is None:
            # Raised rather than guessed, the same rule Export follows: a
            # made-up "item_weapon.xml" would load nothing and report
            # success.
            problems.append(
                f"{key}: no filename in constants.TABLE_FILENAMES")
            continue
        try:
            records, version = item_xml_io.load_table(
                data_dir / filename, item_xml_io.ALL_SPECS[key])
            state.item_table_records[key] = records
            state.item_table_versions[key] = version
        except Exception as exc:                              # noqa: BLE001
            problems.append(f"{titles.get(key, key)}: {exc}")

    # Every OTHER XML table in the same folder, through a derived spec.
    #
    # This is what makes an XML table's arrival free: a file that appears in
    # a future patch is loaded, editable and exportable without anyone
    # adding it to ALL_SPECS or TABLE_FILENAMES. The eleven declared specs
    # above stay authoritative for the tables they cover, because they know
    # which fields are flags; these are read raw.
    declared_shapes = {(spec.root_tag, spec.entry_tag)
                       for spec in item_xml_io.ALL_SPECS.values()}
    for filename, spec in item_xml_io.discover_specs(data_dir).items():
        if (spec.root_tag, spec.entry_tag) in declared_shapes:
            continue                    # a curated tab already owns it
        if filename in c.XML_HANDLED_ELSEWHERE:
            # JobData and JobCommandData have curated tabs too, but they go
            # through `xml_io` rather than `ALL_SPECS`, so the shape check
            # above does not see them. Without this they would be offered
            # twice - once with real controls, once as a raw grid - and the
            # raw one would write a competing diff for the same file.
            continue
        try:
            records, version = item_xml_io.load_table(data_dir / filename, spec)
            state.derived_table_records[filename] = records
            state.derived_table_versions[filename] = version
        except Exception as exc:                              # noqa: BLE001
            # A note, not a failure: one unreadable extra table must not
            # stop the ten curated tabs from opening.
            problems.append(f"{filename}: {exc}")
    return problems


def ability_choices(state=None, language: str = "en") -> dict:
    """
    Ability id -> name, for the Job Commands dropdowns.

    Passes the modder's OWN names through as the live-name layer. This used
    to call `resolve_ability_name(ability_id, {})` - an empty dict - so the
    22 ability slots on every job command showed the name the game shipped
    even after the ability had been renamed on the Abilities tab. Renaming
    "Cure" to "Mend" left Job Commands offering "Cure", which reads as the
    rename not having taken.

    `effective_names` supplies both halves of the answer: the loaded
    `Ability-<lang>` table, and any rename typed but not yet exported.

    Falls back to an empty list rather than failing: a dropdown showing
    only "(None / Unset)" is honest about not knowing the names, whereas a
    page that refuses to open is not more correct, just less useful.
    """
    try:
        from .. import ability_names
        live = {}
        if state is not None:
            from .. import nxd_data
            live = nxd_data.effective_names(state, "ability", language)
        found = {0: "(None / Unset)"}
        for ability_id in range(512):
            name = ability_names.resolve_ability_name(ability_id, live)
            if name:
                found[ability_id] = name
        return found
    except Exception:                                         # noqa: BLE001
        return {0: "(None / Unset)"}


def command_choices(state) -> dict:
    """
    Job command id -> name, for the Jobs page's skillset dropdown.

    Reads the same `job_command_records` the Job Commands tab lists, so the
    two cannot disagree about what a skillset is called. Empty until setup
    has loaded that table, which is why the page takes it through a setter
    rather than reading it once at construction.
    """
    found = {0: "(None / Unset)"}
    for record in getattr(state, "job_command_records", None) or []:
        found[record.command_id] = record.name or "(unnamed command)"
    return found


def discover_versions(state: WizardState | None = None) -> dict:
    """
    Saved game versions that can actually be opened, label -> database path.

    A version whose archive cannot be read is left out rather than listed
    and failing on click. The page then says two versions are needed, which
    is true, instead of offering something that does not work.

    This used to read `entry.sqlite_path`, through `getattr(..., None)`.
    **`ArchivedVersion` has no such attribute** - it holds `nxd_zip` and
    `data_zip` - so the lookup returned None every time and the dict came
    back empty however many versions were archived. Compare Versions could
    therefore never offer anything, on any machine, and the `getattr`
    default meant it failed silently rather than raising.

    An archive is a zip of `.nxd` files, so each one has to be opened.
    `open_archived_database` returns the cached database when the cache was
    written by the same FF16Tools build and None otherwise - a version
    converted by a different build is not trusted, because a converter that
    reads a column differently would turn its own change into "the game
    changed this". That is the same call `ReviewPage.identify_baseline`
    makes, and doing it the same way here is what keeps the two pages
    agreeing about which versions exist.
    """
    found = {}
    try:
        from .. import paths, version_archive
        converter = version_archive.converter_fingerprint(
            getattr(state, "ff16tools_cli_path", None) if state else None)
        scratch = paths.local_data_dir() / "version_scratch"
        for entry in version_archive.list_archived():
            opened = version_archive.open_archived_database(
                entry, scratch / Path(entry.directory).name, converter)
            if opened is not None and Path(opened).exists():
                found[entry.version] = Path(opened)
    except Exception:                                         # noqa: BLE001
        pass
    return found


def build_window(state: WizardState, versions: dict | None = None) -> MainWindow:
    jobs = JobsPage(state)
    commands = JobCommandsPage(state)
    commands.set_ability_choices(ability_choices(state),
                                 getattr(state, "ability_types", None))
    jobs.set_command_choices(command_choices(state))

    pages = {"Jobs": jobs, "Job Commands": commands}
    # Textures is ALWAYS built, even with no game files yet.
    #
    # It used to be created only when a texture tree already existed - which
    # at startup it never does, because Setup has not run. So the tab was a
    # placeholder forever, and the refresh wiring below looked up a page
    # that had never been built and quietly did nothing. Twice now a page
    # has passed its own tests while being unreachable; the lesson is that
    # "built when the data is ready" and "built, and says when the data is
    # not ready" look identical from inside the page.
    pages["Textures"] = TexturesPage(state)
    pages["Sounds"] = SoundsPage(state)
    pages["All Game Data"] = DataBrowserPage(state)
    pages["Poaching"] = PoachingPage(state)
    pages["Abilities"] = AbilitiesPage(state)
    pages["Encounters"] = EncountersPage(state)
    # Items gets its own page; the other two stay generic.
    #
    # `TableEditorPage` drives one spec over records with an id and a name,
    # which is right for ten of the eleven tables and wrong for Items: one
    # item spans ItemData, one of the four type-specific tables, its shop
    # row, its equip bonus, its per-language text and two textures. Driving
    # that through a one-spec page is what made the Qt Items tab show
    # ItemData and stop.
    #
    # Built unconditionally, like Textures. It used to appear only when its
    # records were already loaded, and this project has twice shipped a page
    # that was never built because the data arrives after the window does.
    pages["Items"] = ItemsPage(state)
    for title, key, _filename, blurb in TABLE_TABS:
        if title == "Items":
            continue
        # Built unconditionally, like Items, Textures and Sounds above.
        #
        # This used to be guarded by `if state.item_table_records.get(key)`,
        # so Equip Bonus and Treasure Hunter appeared only when their
        # bundled XML had already parsed. `load_table_tabs` catches each
        # table's exception into `problems` and carries on, so one
        # unreadable file took its whole tab out of the sidebar with nothing
        # on screen to say why - the tool simply had eight tabs instead of
        # ten, and a missing tab looks like a tool that does not have the
        # feature.
        #
        # That is the third time this project has shipped a page that was
        # never built; the comment above records the first two. The page now
        # carries its own "reference data hasn't loaded" message, which is
        # what the Tkinter tab has always done (`step_equip_bonus.py`'s
        # `no_reference_var`).
        pages[title] = TableEditorPage(state, key, title, blurb)

    setup = SetupPage(state)
    export = ExportPage(state)
    found_versions = (versions if versions is not None
                      else discover_versions(state))
    review = ReviewPage(state, found_versions)
    compare = ComparePage(found_versions)
    window = MainWindow(
        compare,
        tab_pages=pages,
        step_pages={"General Setup": setup, "Export Mod": export},
        review_page=review,
    )
    # Setup is what produces the texture tree, and Textures is built before
    # it exists. Rather than leave a page showing an empty tree forever, the
    # tab rebuilds itself when setup reports a change.
    def _on_setup_changed():
        # Jobs and Job Commands were missing from this list, and both of
        # them read tables that only exist AFTER setup has run.
        #
        # The result was two dropdowns permanently stuck on their startup
        # contents: the Jobs skillset picker offered "(None / Unset)" and
        # nothing else, and the 22 ability slots on Job Commands offered the
        # bundled name list rather than the loaded one. Neither page looked
        # broken - a dropdown with one entry looks like a dropdown - which
        # is why it survived. Restarting the tool after setup "fixed" it,
        # which is the shape of a refresh that never happens.
        # The two pages that need something BESIDES a refresh. The refresh
        # itself is left to the loop below, so these two are not refreshed
        # twice and cannot drift out of step with the rest.
        jobs_page = pages.get("Jobs")
        if jobs_page is not None:
            jobs_page.set_command_choices(command_choices(state))
        commands_page = pages.get("Job Commands")
        if commands_page is not None:
            commands_page.set_ability_choices(
                ability_choices(state), getattr(state, "ability_types", None))
        # Same rule for the file-tree pages. Two of them have `refresh_tree`
        # today and naming them worked; naming things is what failed twice
        # above, so it is asked of every page here too.
        for page in pages.values():
            refresh_tree = getattr(page, "refresh_tree", None)
            if callable(refresh_tree):
                refresh_tree()
        # EVERY page that can be refreshed, not a list of names.
        #
        # This was a hand-written list, and All Game Data was not on it -
        # so after unpacking the game that tab went on saying "No game data
        # yet" until the tool was restarted, which is the same shape as the
        # Jobs and Job Commands fault recorded above. The list had already
        # been wrong twice; the third time it was a page rather than a
        # dropdown, and the page's own empty state made it look like the
        # unpack had failed.
        #
        # A page knows whether it needs refreshing - it either has the
        # method or it does not - so asking every page removes the standing
        # requirement that somebody remember this line exists.
        # `dev/audit_table_wiring.py` checks the outcome.
        for page in pages.values():
            refresh = getattr(page, "refresh_records", None)
            if callable(refresh):
                refresh()
        # Both Game Updates pages re-read the archive.
        #
        # Unpacking the game is what SAVES a version, so the two pages that
        # choose between saved versions are stale the moment setup finishes
        # - and on a fresh install they were built with none at all. Compare
        # Versions filled its From and To boxes once in `__init__` and had
        # no way of ever being told about a new one, so it could not be used
        # for the whole session; restarting "fixed" it. `versions` is only
        # passed in by tests, which supply their own fixed archive, so
        # rediscovery is skipped in that case.
        if versions is None:
            fresh = discover_versions(state)
            compare.set_versions(fresh)
            review.set_versions(fresh)

        export.refresh_summary()
    setup.setup_changed.connect(_on_setup_changed)

    # Every editing page tells Export that its totals moved. Without this the
    # summary would show whatever was true when the page was built, which for
    # a page opened before any editing means "nothing edited yet" forever.
    for page in pages.values():
        signal = getattr(page, "edits_changed", None)
        if signal is not None:
            signal.connect(export.refresh_summary)

    # Cross-tab jumps. Connected after the window exists because the pages
    # ask the SHELL to navigate - they do not know what tabs there are, and
    # a page reaching into its siblings is how two pages end up disagreeing
    # about which record is selected.
    for page in pages.values():
        signal = getattr(page, "navigate_requested", None)
        if signal is not None:
            signal.connect(window.open_tab)

    # Items' two jumps go through the same shell call. They are separate
    # signals rather than one `navigate_requested` because their payloads
    # differ - an equip bonus is a row id, a texture is a path - and a
    # single signal carrying "either an int or a string, depending" is the
    # kind of thing that works until somebody passes the wrong one.
    # Repointing an item's EquipBonusId changes which rows Equip Bonus shows
    # as used, and by what. Without this the counts on its 85 list rows and
    # its "Used by:" line go stale the moment an item is edited - showing a
    # row as worn by an item that no longer wears it, which is worse than
    # showing no count at all.
    equip_bonus_page = pages.get("Equip Bonus")
    if equip_bonus_page is not None and pages.get("Items") is not None:
        pages["Items"].edits_changed.connect(equip_bonus_page.refresh_usage)

    # Renaming an ability has to reach the 22 dropdowns on Job Commands.
    #
    # The choices are built once and refilled only on a Setup refresh, so
    # without this a rename showed on the Abilities tab and nowhere else
    # until the tool was restarted - the same shape of fault as the
    # skillset picker that offered "(None / Unset)" forever. Same for the
    # Jobs page's Name, which is what its own skillset preview reads.
    abilities_page = pages.get("Abilities")
    commands_page = pages.get("Job Commands")
    if abilities_page is not None and commands_page is not None:
        def _refresh_ability_names():
            language = getattr(abilities_page, "language", "en")
            commands_page.set_ability_choices(
                ability_choices(state, language),
                getattr(state, "ability_types", None))
        abilities_page.edits_changed.connect(_refresh_ability_names)

    items_page = pages.get("Items")
    if items_page is not None:
        items_page.jump_to_equip_bonus.connect(
            lambda row_id: window.open_tab("Equip Bonus", int(row_id)))
        items_page.jump_to_texture.connect(
            lambda path: window.open_tab("Textures", str(path)))

    # Abilities has the same icon slot and emits the same signal, and
    # nothing was listening. "View in Textures" and the slot's right-click
    # "View in the Textures tab" both fired into nowhere, so the button
    # simply did nothing - the same shape as `set_item_choices`, which was
    # called by the test suite and by no part of the application.
    abilities_page = pages.get("Abilities")
    if abilities_page is not None:
        abilities_page.jump_to_texture.connect(
            lambda path: window.open_tab("Textures", str(path)))

    window.setup_page = setup
    window.export_page = export
    window.review_page = review
    return window


def _claim_taskbar_identity() -> None:
    """
    Tells Windows this is its own application, not "some Python".

    Windows-only and entirely cosmetic, so every failure is swallowed - an
    old Windows without the call, or a locked-down environment, is not a
    reason to refuse to start. The id matches the Tkinter interface's, so
    the two do not appear as separate applications.
    """
    if platform.system() != "Windows":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Zodi.IvaliceChroniclesModStudio")
    except Exception:                                         # noqa: BLE001
        pass


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("The Ivalice Chronicles Mod Studio")

    # The taskbar button, which is a separate problem from the window icon.
    #
    # Windows groups taskbar buttons by AppUserModelID, and a script
    # inherits the host interpreter's - so the button showed the Python
    # snake however correct the window icon was. The Tkinter interface has
    # claimed its own since that was noticed; this one never did.
    #
    # Must happen before the first window exists.
    _claim_taskbar_identity()

    # Set on the QApplication as well as the window: dialogs and message
    # boxes take the application icon, not the parent window's, so without
    # this a file picker still opens wearing the default.
    app.setWindowIcon(application_icon())

    state = WizardState()
    problems = load_reference_tables(state)

    # Closing the window while an unpack or a preview is running would
    # otherwise leave Python to destroy a live QThread during teardown,
    # which aborts.
    from .workers import running_threads
    app.aboutToQuit.connect(lambda: running_threads().stop_all())

    window = build_window(state)

    # Before showing, so the tabs come up populated rather than flashing
    # empty. Everything this needs is already on disk from the last run.
    setup_page = window.stack.widget(0)
    if hasattr(setup_page, "reuse_previous_session"):
        for line in setup_page.reuse_previous_session():
            setup_page._log(line)
        setup_page._refresh_readiness()
        setup_page.setup_changed.emit()

    window.show()

    if problems:
        QMessageBox.warning(
            window, "Some reference tables couldn't be read",
            "These tabs will be empty:\n\n" + "\n".join(problems)
            + "\n\nEverything else works normally.")

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
