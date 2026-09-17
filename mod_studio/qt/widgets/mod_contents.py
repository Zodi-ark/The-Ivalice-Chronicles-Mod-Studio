"""
Mod Contents: every file the mod will write, with its actual contents.

The Export page showed a Summary and nothing else, so the only way to see
what a mod would actually contain was to build it and open the folder. The
Tkinter page has shown the real files since it shipped, and being able to
read the XML before generating is how several of this project's data bugs
were spotted at all.

Two rows of tabs. The outer row is a section, named to match an **Edit Game
Data tab one-for-one** - the two pages should call the same thing the same
name. The inner row is the real filename that section writes.

**Sections with nothing in them are hidden, not removed.** A hidden tab that
was never added would take a new slot when it reappeared, so the order would
scramble as the user edited - Textures could end up before Jobs. Every tab
is built once, up front, and visibility is all that changes. "Show every
section" reveals the empty ones.

Hiding is safe because the Summary tab lists every section including the
empty ones, so "where did Textures go?" has an answer on the first tab
rather than needing the tick box to be found first.

`.nxd` files get a summary rather than a diff: they are binary and rebuilt
through FF16Tools, so there is no text to show. Saying that on each one is
better than an empty pane that looks broken.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QPlainTextEdit, QTabWidget, QVBoxLayout,
    QWidget,
)

from ... import constants as c
from ... import nxd_data

NXD_NOTE = ("Binary .nxd - rebuilt through FF16Tools, so this is a summary "
            "of what will change rather than a diff.")

#: Heading for files a mod carries through without this tool editing them.
#:
#: Deliberately NOT named after a page. Every other section is named for an
#: Edit Game Data tab one-for-one, so "UI (carried through, not edited
#: here)" read as a page that does not exist - and produced one heading per
#: read-only table on top of that. These files are real and must stay
#: visible, so they get a region instead of a fake page.
CARRIED_THROUGH_SECTION = "Carried through"

#: What a text row is, since a .pzd is not rebuilt the way an .nxd is.
PZD_NOTE = ("Panzer text files - written as YAML and converted back by "
            "FF16Tools, so this is a summary of which lines change rather "
            "than a diff.")

#: What that section means, shown on each file under it.
CARRIED_THROUGH_NOTE = (
    "Copied from the mod you opened, unchanged. Nothing in Mod Studio edits "
    "these - they travel with the mod so that a mod shipping its own copies "
    "keeps them.")


class _SummaryView(QPlainTextEdit):
    """
    A read-only text view that also answers `text()`.

    The Summary was a `QLabel` and everything that reads it - the suites,
    and the page itself - calls `.text()`. Keeping that name working means
    the change from a label to a scrollable text view is invisible to
    callers, rather than a rename rippling through sixty assertions that
    would then be testing the rename instead of the summary.
    """

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, value: str) -> None:
        self.setPlainText(value)


class ModContentsPane(QWidget):
    """
    The right-hand pane: Summary, then a section tab per Edit Game Data tab.

    Providers are callables rather than text, because the contents change on
    every keystroke in the Mod Name field and on every edit made on another
    tab. `refresh()` re-runs them all.
    """

    def __init__(self, page, parent=None):
        super().__init__(parent)
        self.page = page
        self.state = page.state
        self.groups = []

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("Mod Contents")
        title.setStyleSheet("font-weight: 600;")
        header.addWidget(title)
        header.addStretch(1)
        self.show_all = QCheckBox("Show every section")
        self.show_all.toggled.connect(lambda _on: self.refresh_visibility())
        header.addWidget(self.show_all)
        column.addLayout(header)

        self.tabs = QTabWidget()
        column.addWidget(self.tabs, 1)

        self.summary = self._text_view(wrap=True, summary=True)
        self.tabs.addTab(self._wrap(self.summary), "Summary")

        for label, files in self._spec():
            holder = QWidget()
            inner = QVBoxLayout(holder)
            inner.setContentsMargins(2, 2, 2, 2)
            sub_tabs = QTabWidget()
            inner.addWidget(sub_tabs)
            entries = []
            for file_label, note, wrap, provider, predicate in files:
                view = self._text_view(wrap=wrap)
                entries.append({
                    "label": file_label, "view": view, "provider": provider,
                    "predicate": predicate, "index": sub_tabs.count(),
                })
                sub_tabs.addTab(self._wrap(view, note), file_label)
            # Added up front and hidden later, never added lazily.
            self.tabs.addTab(holder, label)
            self.groups.append({
                "label": label, "holder": holder, "tabs": sub_tabs,
                "files": entries,
                "index": self.tabs.count() - 1,
            })

    # -- widgets ------------------------------------------------------------

    def _text_view(self, wrap: bool, summary: bool = False) -> QPlainTextEdit:
        view = _SummaryView() if summary else QPlainTextEdit()
        view.setReadOnly(True)
        # A fixed-width font, from the system rather than a guessed name:
        # "Consolas" does not exist off Windows and Qt silently substitutes
        # something proportional, which makes XML unreadable.
        view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        view.setLineWrapMode(QPlainTextEdit.WidgetWidth if wrap
                             else QPlainTextEdit.NoWrap)
        return view

    def _wrap(self, view: QWidget, note: str | None = None) -> QWidget:
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(4, 4, 4, 4)
        column.setSpacing(4)
        if note:
            label = QLabel(note)
            label.setProperty("role", "muted")
            label.setWordWrap(True)
            column.addWidget(label)
        column.addWidget(view, 1)
        return holder

    # -- what each section writes -------------------------------------------

    def _spec(self) -> list:
        """
        (section, [(filename, note, wrap, text provider, has-content?)]).

        Section labels match the Edit Game Data tabs; file labels are the
        real filenames the mod will contain.

        The list below is curated - it decides which XML file belongs under
        which heading, and in what order - and it is then passed through
        `_with_every_registered_table`, which guarantees the one thing
        curation kept getting wrong.
        """
        page, state = self.page, self.state

        def table(key):
            return (lambda k=key: page.table_diff_xml_text(k),
                    lambda k=key: state.edited_item_table_count(k) > 0)

        return self._with_every_registered_table([
            ("Mod Config", [
                ("ModConfig.json", "Reloaded-II's manifest for your mod.",
                 False, page.config_preview_text, lambda: True),
            ]),
            ("Jobs", [
                ("JobData.xml", None, False, page.job_diff_xml_text,
                 lambda: state.edited_job_count() > 0),
                self._nxd_row("job", "job names/descriptions"),
            ]),
            # Everything made on the All Game Data tab. Two rows, because
            # the two kinds become different files by different routes -
            # .nxd through FF16Tools, .xml as a diff - and a modder
            # checking what their mod contains needs to see which.
            #
            # Listed at all because a mod could consist ENTIRELY of these
            # and Mod Contents would otherwise have shown nothing, which
            # reads as the edits having been lost.
            ("All Game Data", [
                ("Game data tables (.nxd)", NXD_NOTE, True,
                 self._browser_nxd_summary,
                 lambda: any(fields
                             for rows in (state.unmodelled_table_edits or {}).values()
                             for fields in rows.values())),
                ("Table files (.xml)", None, False,
                 self._browser_xml_summary,
                 lambda: any(fields
                             for rows in (state.derived_table_edits or {}).values()
                             for fields in rows.values())),
            ]),
            ("Job Commands", [
                ("JobCommandData.xml", None, False,
                 page.job_command_diff_xml_text,
                 lambda: self._edited_commands_of_kind(monsters=False) > 0),
                # Monster skillsets edit on the same page but write to their
                # own file - four slots and a different element name - so
                # the pane shows both, and each appears only when it has
                # something in it. One page, two files, both named.
                ("MonsterJobCommandData.xml", None, False,
                 page.monster_job_command_diff_xml_text,
                 lambda: self._edited_commands_of_kind(monsters=True) > 0),
                self._nxd_row("job_command", "job command names/descriptions"),
            ]),
            ("Abilities", [
                ("AbilityData.xml", None, False, *table("ability")),
                ("AbilityEffectNumberFilterData.xml", None, False,
                 *table("ability_effect")),
                ("AbilityTypeData.xml", None, False,
                 *table("ability_animation")),
                self._nxd_row("ability", "abilities"),
                # Its own row, not a sentence tacked onto the end of the
                # ability names file.
                #
                # It was written as "...plus the shared override table (2
                # ability(s))" on `ability.<lang>.nxd`, so the pane named
                # one file and shipped two - and the second was the one
                # carrying Range, Formula and Inflict Status. Somebody
                # checking what their mod contains had no row to look at for
                # the edits they had just made.
                #
                # `overrideentrydata.nxd` on Encounters is the same kind of
                # table and has always had its own row; this is that shape.
                (c.NXD_OVERRIDE_ACTION_FILENAME, NXD_NOTE, True,
                 self._override_summary,
                 lambda: state.edited_override_count() > 0),
            ]),
            ("Items", [
                ("ItemData.xml", None, False, *table("item")),
                ("ItemWeaponData.xml", None, False, *table("item_weapon")),
                ("ItemArmorData.xml", None, False, *table("item_armor")),
                ("ItemShieldData.xml", None, False, *table("item_shield")),
                ("ItemAccessoryData.xml", None, False,
                 *table("item_accessory")),
                ("ItemShopsData.xml", None, False, *table("item_shops")),
                self._nxd_row("item", "items"),
            ]),
            ("Equip Bonus", [
                ("ItemEquipBonusData.xml", None, False,
                 *table("item_equip_bonus")),
            ]),
            ("Poaching", [
                self._nxd_row("poach", "poaching entries"),
            ]),
            ("Treasure Hunter", [
                ("MapTrapFormationData.xml", None, False, *table("map_trap")),
            ]),
            ("Encounters", [
                ("overrideentrydata.nxd", NXD_NOTE, True,
                 self._entry_summary,
                 lambda: state.changed_entry_row_count() > 0),
                # `charaname.<lang>.nxd` is NOT listed here any more. It was,
                # and that was right while Unit Names was a sub-tab of this
                # page; it is its own page now, and the derived pass below
                # files it under `CURATED_NXD_SPECS["chara_name"].label`,
                # which already reads "Unit Names". Leaving the hand-written
                # row here would have pinned it to the wrong page and hidden
                # the fact that the derivation was already correct.
            ]),
            ("Textures", [
                ("Replaced textures",
                 ".tga is copied as-is; .tex is converted with FF16Tools.",
                 True, self._texture_summary,
                 lambda: bool(state.texture_edits)),
            ]),
            ("Sounds", [
                # Subtitles ship under Sounds because Sounds is where they
                # are edited - the pane's rule is that a section exists
                # because a page does. One row for all of them, not one per
                # file: a retranslation touches hundreds, and a section with
                # 600 tabs in it is a section nobody reads.
                ("nxd/text/*.pzd", PZD_NOTE, True,
                 self._text_summary,
                 lambda: state.edited_pzd_file_count() > 0),
                ("Replaced sounds",
                 "Each edited .sab is unpacked and repacked with AudioMog.",
                 True, self._sound_summary,
                 lambda: bool(state.sound_edits)),
            ]),
        ])

    def _with_every_registered_table(self, sections: list) -> list:
        """
        Files the tables the curated list above missed, UNDER THEIR PAGE.

        Two levels, always: the Mod Studio page you would have made the edit
        on, then the file it becomes. That is what a modder checking their
        own work is actually asking - "where did I do this, and what does it
        write" - and it is derived here rather than curated, so a page added
        next year appears without this file being edited.

        Both halves of the derivation come from things that already exist:

        - a `.nxd` table's owning page is `CURATED_NXD_SPECS[key].label`,
          and a table with no curated spec is reachable only through All
          Game Data, so that is where it goes
        - an XML table's owning page is its entry in `app`'s tab table,
          which is the same list `build_window` builds the tabs from

        Before this, every one of the 45 uncurated `.nxd` tables got its own
        TOP-LEVEL heading - "Zodiac Stone", "Novel03", "Launcher Guide" -
        so the pane read as a list of 58 pages when the tool has 14, and
        none of those headings named anywhere you could go. Worse, the
        derivation only covered `.nxd`: **Inflict Status had no row at all**,
        because it is an XML table and the XML half was hand-written. An
        edit made there appeared nowhere in Mod Contents, which reads as the
        edit having been lost - the exact fault this method was written to
        prevent, in the half it did not cover.
        """
        listed = {row[0] for _section, rows in sections for row in rows}
        by_section = {name: rows for name, rows in sections}

        def place(section: str, row) -> None:
            if row[0] in listed:
                return
            listed.add(row[0])
            if section in by_section:
                by_section[section].append(row)
            else:
                by_section[section] = [row]
                sections.append((section, by_section[section]))

        for key, spec in nxd_data.ALL_NXD_SPECS.items():
            row = self._nxd_row(key, spec.label.lower())
            if spec.nxd_stem in self._read_only_stems():
                # ONE section, and it is not named after a page.
                #
                # The rule this pane follows is that a section exists
                # because an Edit Game Data page exists. These files have no
                # page - nothing in the interface edits the UI strings; they
                # are staged because key 3737 holds the game's version
                # string, and a mod shipping its own copies has them carried
                # through untouched. Heading them "UI (carried through, not
                # edited here)" put a page-shaped thing where no page is,
                # and gave one per table on top of that.
                #
                # NOT hidden, which was tried and caught by
                # `audit_table_wiring`: opening the reference mod recovers
                # five real `ui` entries, and hiding the row makes those
                # invisible - the "my edit was lost" fault this whole method
                # exists to prevent.
                #
                # So they get a region of their own, named for what it is
                # rather than for somewhere you could go, and sorted to the
                # end where the page sections stop.
                # The note is replaced too. `NXD_NOTE` explains a rebuild
                # through FF16Tools, which is not what happens to these -
                # they are copied, not rebuilt, and saying so is the whole
                # point of the section.
                label, _note, wrap, provider, predicate = row
                place(CARRIED_THROUGH_SECTION,
                      (label, CARRIED_THROUGH_NOTE, wrap, provider,
                       predicate))
                continue
            curated = nxd_data.CURATED_NXD_SPECS.get(key)
            place(curated.label if curated else "All Game Data", row)

        for title, table_key, filename in self._xml_pages():
            place(title, (filename, None, False,
                          lambda k=table_key: self.page.table_diff_xml_text(k),
                          lambda k=table_key:
                              self.state.edited_item_table_count(k) > 0))
        return self._in_sidebar_order(sections)

    @staticmethod
    def _in_sidebar_order(sections: list) -> list:
        """
        Summary, Mod Config, the pages in SIDEBAR order, then carried
        through.

        Sorted by `EDIT_TABS.index(...)` rather than by a second list, so
        **reordering the sidebar reorders this pane** and nobody has to
        remember that two orders exist. They came out in the curated list's
        order with the derived ones appended, which put Unit Names and
        Inflict Status at the end purely because of how they were found.

        Mod Config leads because it is not a page either - it is the
        manifest every mod has - and it is the one thing here that is
        always written.

        Find Text is not in the pane and would not be even if it had files:
        it searches All Game Data rather than editing anything, which is
        why it is excluded from the sidebar order too.

        A section matching no tab sorts before the carried-through block and
        after the pages, rather than being dropped. Losing a heading here
        loses the files under it.
        """
        from ..shell import EDIT_TABS

        def rank(entry) -> tuple:
            label = entry[0]
            if label == "Mod Config":
                return (0, 0, label)
            if label == CARRIED_THROUGH_SECTION:
                return (3, 0, label)
            try:
                return (1, EDIT_TABS.index(label), label)
            except ValueError:
                return (2, 0, label)

        return sorted(sections, key=rank)

    @staticmethod
    def _read_only_stems() -> set:
        """The `.nxd` stems this tool stages but never writes."""
        return {name.split(".")[0] for name in c.NXD_ALL_UI_FILENAMES}

    @staticmethod
    def _xml_pages() -> list:
        """
        `[(page title, table key, filename)]` for every XML table with a tab.

        Read from the same list `build_window` builds the tabs from, so a
        new table page is in Mod Contents the moment it is in the sidebar.
        Imported inside the function because `app` imports the pages that
        import this widget.
        """
        from .. import app as qt_app

        return [(title, key, filename)
                for title, key, filename, *_rest in qt_app.TABLE_TABS]

    # -- .nxd summaries -----------------------------------------------------

    def _nxd_row(self, key, noun, extra_summary=None, extra_shown=None):
        """
        The (filename, note, is_nxd, preview, shown) tuple for one
        registered per-language table.

        Built from the registry so the pattern - a `<stem>.<lang>.nxd` row
        whose preview lists the languages it will write - is written once.
        Before this, each table repeated it, and a table added without its
        row here exported correctly and then went unmentioned in Mod
        Contents, which reads as "my edit was lost".
        """
        state = self.state
        spec = nxd_data.spec_for(key)
        filenames = {lang: spec.filename(lang) for lang in c.NXD_LANGUAGES}

        def preview():
            return self._nxd_summary(
                noun, state.touched_nxd_languages(key), filenames,
                state.edited_nxd_total_count(key),
                extra=extra_summary() if extra_summary else None,
                # The key, so the preview can list WHICH rows changed and
                # not merely how many files it will write.
                key=key)

        def shown():
            if state.edited_nxd_total_count(key) > 0:
                return True
            return bool(extra_shown()) if extra_shown else False

        return (f"{spec.nxd_stem}.<lang>.nxd", NXD_NOTE, True, preview, shown)

    def _browser_nxd_summary(self) -> str:
        return self._browser_summary(
            self.state.unmodelled_table_edits or {}, "table")

    def _browser_xml_summary(self) -> str:
        return self._browser_summary(
            self.state.derived_table_edits or {}, "file")

    def _browser_summary(self, store: dict, noun: str) -> str:
        """Which tables were touched and how many rows in each."""
        parts = []
        for name in sorted(store):
            rows = sum(1 for fields in store[name].values() if fields)
            if rows:
                parts.append(f"{name} ({rows} row(s))")
        if not parts:
            return f"No {noun}s edited on the All Game Data tab."
        return (f"Edited on the All Game Data tab: " + ", ".join(parts)
                + ".")

    #: How many changed rows an .nxd preview lists before it stops counting.
    #:
    #: A `.nxd` table can run to thousands of rows, so the whole file is
    #: never the useful thing to show - but "1 poaching entries edited"
    #: told a modder nothing about WHAT they had changed, which was the
    #: complaint. The changed rows are the answer, and there are almost
    #: never many: an edit is something a person typed.
    #:
    #: A cap all the same, because "almost never" is not never - a
    #: copy-to-all-languages across a big table can touch hundreds, and a
    #: preview pane is not a place to render them.
    MAX_LISTED_ROWS = 40

    def _changed_rows(self, key, language) -> list:
        """
        `[(row id, {field: new value})]` for one table in one language.

        Read from the same edit store the exporter writes from, so what this
        lists and what the file contains cannot drift apart.
        """
        store = self.state.nxd_edits_for(key) or {}
        rows = store.get(language) or {}
        return [(row_id, fields) for row_id, fields in sorted(rows.items())
                if fields]

    def _row_detail(self, key, languages) -> list:
        """
        The changed rows, as lines, for every language that has any.

        This is the half that was missing. The pane said which FILES it
        would write and said nothing about what was in them, so a modder
        checking their own work had to export and diff to find out - and
        the one thing Mod Contents exists to answer is "what is in my mod".
        """
        lines = []
        for language in languages:
            changed = self._changed_rows(key, language)
            if not changed:
                continue
            label = c.NXD_LANGUAGE_LABELS.get(language, language)
            lines.append("")
            lines.append(f"Changed rows ({label}):")
            for row_id, fields in changed[:self.MAX_LISTED_ROWS]:
                for field, value in sorted(fields.items()):
                    shown = " ".join(str(value).split())
                    if len(shown) > 60:
                        shown = shown[:57] + "..."
                    lines.append(f"  row {row_id}  {field} = {shown}")
            if len(changed) > self.MAX_LISTED_ROWS:
                lines.append(f"  ...and {len(changed) - self.MAX_LISTED_ROWS} "
                             f"more row(s)")
        return lines

    def _nxd_summary(self, noun, languages, filenames, count,
                     extra=None, key=None) -> str:
        languages = list(languages)
        if not languages and not extra:
            return f"No {noun} edited, so no .nxd file will be written."
        lines = [f"{count} {noun} edited, across "
                 f"{len(languages)} language(s).", ""]
        lines.append("Files this will write:")
        for language in languages:
            label = c.NXD_LANGUAGE_LABELS.get(language, language)
            lines.append(f"  {filenames[language]}   ({label})")
        if extra:
            lines.append(f"  ...plus {extra}")
        if key is not None:
            lines.extend(self._row_detail(key, languages))
        lines.append("")
        lines.append(
            "Each is produced by applying your edits to a copy of your "
            "converted game database and converting that copy back with "
            "FF16Tools. Your own database is never modified.")
        return "\n".join(lines)

    def _entry_summary(self) -> str:
        state = self.state
        changed = state.changed_entry_row_count()
        if not changed:
            return "No encounter rows changed."
        lines = [f"{changed} encounter row(s) changed.", ""]
        if state.entry_rekeys:
            lines.append(f"{len(state.entry_rekeys)} row(s) moved to a "
                         f"different address.")
        if state.entry_dropped:
            lines.append(f"{len(state.entry_dropped)} row(s) removed - the "
                         f"address is freed for reuse, and the game's row "
                         f"count is unchanged.")
        lines.append("")
        lines.append(f"Writes {c.NXD_OVERRIDE_ENTRY_FILENAME}.")
        return "\n".join(lines)

    def _edited_commands_of_kind(self, monsters: bool) -> int:
        """
        How many edited skillsets belong in one file or the other.

        `edited_job_command_count()` counts both together, so using it for
        either row would show `JobCommandData.xml` for a mod that edits only
        a Chocobo - naming a file the mod does not contain.
        """
        by_id = {r.command_id: r
                 for r in (self.state.job_command_records or [])}

        def is_monster(cid) -> bool:
            # An id with no record loaded counts as a JOB command.
            #
            # Dropping it instead would hide a file the mod really does
            # contain whenever the reference tables have not loaded - which
            # is the state an opened mod is in before setup completes. The
            # pane's job is to name what will be written, and being wrong
            # about WHICH file is better than claiming there is none.
            record = by_id.get(cid)
            return bool(record.is_monster) if record is not None else False

        return sum(1 for cid, fields
                   in (self.state.job_command_edits or {}).items()
                   if fields and is_monster(cid) is bool(monsters))

    def _text_summary(self) -> str:
        """Which text files change, and how many lines in each."""
        edits = {path: lines
                 for path, lines in (self.state.pzd_edits or {}).items()
                 if lines}
        if not edits:
            return "No text lines edited."
        total = sum(len(lines) for lines in edits.values())
        out = [f"{total} line(s) edited across {len(edits)} file(s).", ""]
        for path in sorted(edits):
            ids = ", ".join(str(i) for i in sorted(edits[path])[:12])
            more = ("" if len(edits[path]) <= 12
                    else f", and {len(edits[path]) - 12} more")
            out.append(f"{path}")
            out.append(f"    line(s) {ids}{more}")
        return "\n".join(out)

    def _override_summary(self) -> str:
        """
        What the ability override table will contain.

        Names the abilities and the fields changed on each, rather than
        counting them. "2 ability(s)" told somebody checking their own work
        nothing about WHICH two, which is the same complaint that made every
        other nxd row list its changed rows.
        """
        state = self.state
        edits = {key: fields
                 for key, fields in (state.override_action_edits or {}).items()
                 if fields}
        if not edits:
            return "No ability overrides set."
        lines = [f"{len(edits)} ability override(s) set.", ""]
        for key in sorted(edits):
            names = ", ".join(sorted(edits[key]))
            lines.append(f"Ability {key}: {names}")
        lines.append("")
        lines.append(f"Writes {c.NXD_OVERRIDE_ACTION_FILENAME}.")
        return "\n".join(lines)

    def _texture_summary(self) -> str:
        edits = self.state.texture_edits or {}
        if not edits:
            return "No textures replaced."
        lines = [f"{len(edits)} texture(s) replaced.", ""]
        for relative_path, info in sorted(edits.items()):
            source = info.get("source_path", "")
            if info.get("already_staged"):
                lines.append(f"{relative_path}\n    kept from the opened mod")
            else:
                lines.append(f"{relative_path}\n    from {source}")
        return "\n".join(lines)

    def _sound_summary(self) -> str:
        edits = self.state.sound_edits or {}
        if not edits:
            return "No sounds replaced."
        total = sum(len(tracks) for tracks in edits.values())
        lines = [f"{total} track(s) replaced across "
                 f"{len(edits)} archive(s).", ""]
        for archive, tracks in sorted(edits.items()):
            lines.append(archive)
            for name, info in sorted(tracks.items()):
                source = (info.get("source_path")
                          if isinstance(info, dict) else info)
                lines.append(f"    {name}  <-  {source}")
        return "\n".join(lines)

    # -- refreshing ---------------------------------------------------------

    def refresh(self, summary_text: str) -> None:
        self.summary.setPlainText(summary_text)
        for group in self.groups:
            for entry in group["files"]:
                try:
                    text = entry["provider"]()
                except Exception as exc:                      # noqa: BLE001
                    # One section that cannot render must not blank the
                    # others - and the reason belongs on screen rather than
                    # in a console the user will never look at.
                    text = (f"Couldn't build this preview: {exc}\n\n"
                            f"This is a problem with the preview, not "
                            f"necessarily with your mod.")
                entry["view"].setPlainText(text or "")
        self.refresh_visibility()

    def refresh_visibility(self) -> None:
        show_all = self.show_all.isChecked()
        for group in self.groups:
            any_content = False
            for entry in group["files"]:
                try:
                    has = bool(entry["predicate"]())
                except Exception:                             # noqa: BLE001
                    has = False
                any_content = any_content or has
                group["tabs"].setTabVisible(entry["index"], has or show_all)
            self.tabs.setTabVisible(group["index"], any_content or show_all)
