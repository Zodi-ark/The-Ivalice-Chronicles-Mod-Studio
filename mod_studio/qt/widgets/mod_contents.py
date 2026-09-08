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
                 lambda: state.edited_job_command_count() > 0),
                self._nxd_row("job_command", "job command names/descriptions"),
            ]),
            ("Abilities", [
                ("AbilityData.xml", None, False, *table("ability")),
                ("AbilityEffectNumberFilterData.xml", None, False,
                 *table("ability_effect")),
                ("AbilityTypeData.xml", None, False,
                 *table("ability_animation")),
                self._nxd_row(
                    "ability", "abilities",
                    extra_summary=lambda: (
                        "the shared override table "
                        f"({state.edited_override_count()} ability(s))"
                        if state.override_touched() else None),
                    extra_shown=lambda: state.edited_override_count() > 0),
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
                self._nxd_row("chara_name", "unit names"),
            ]),
            ("Textures", [
                ("Replaced textures",
                 ".tga is copied as-is; .tex is converted with FF16Tools.",
                 True, self._texture_summary,
                 lambda: bool(state.texture_edits)),
            ]),
            ("Sounds", [
                ("Replaced sounds",
                 "Each edited .sab is unpacked and repacked with AudioMog.",
                 True, self._sound_summary,
                 lambda: bool(state.sound_edits)),
            ]),
        ])

    def _with_every_registered_table(self, sections: list) -> list:
        """
        Adds a row for any registered `.nxd` table the curated list missed.

        `_nxd_row` was already built from the registry, so adding a table
        was supposed to be free. It was not: the HELPER was generic and the
        CALL SITES were typed out by hand, five of them for six registered
        tables. `jobcommand` was the sixth. A Job Command rename was
        counted by `_nxd_backed_edit_count`, would have been written by the
        exporter, and appeared nowhere on this pane - so the only thing the
        person could see said their edit did not exist.

        Curation still decides placement and order for every table somebody
        thought about. This decides that a table nobody thought about is
        still mentioned, under its own heading, rather than silently
        omitted. `dev/audit_table_wiring.py` checks the outcome by planting
        a real edit in each table and asking this pane whether it can see
        it.
        """
        listed = {row[0] for _section, rows in sections for row in rows}
        for key, spec in nxd_data.ALL_NXD_SPECS.items():
            if f"{spec.nxd_stem}.<lang>.nxd" in listed:
                continue
            sections.append((spec.label, [self._nxd_row(key, spec.label.lower())]))
        return sections

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
                extra=extra_summary() if extra_summary else None)

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

    def _nxd_summary(self, noun, languages, filenames, count,
                     extra=None) -> str:
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
