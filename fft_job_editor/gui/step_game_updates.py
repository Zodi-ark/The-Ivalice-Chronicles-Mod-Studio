"""
The Game Updates page.

Pinned to the bottom of the sidebar, below a divider, because it isn't one
of the three steps in making a mod - it's for when the game patches and a
mod built earlier needs moving across. Moving it out of the flow costs
discoverability, paid back by `WizardApp.set_sidebar_alert`, which turns the
entry amber when there's genuinely something to deal with.

Three tabs:

  Status          which saved game version the open mod was built against,
                  which one you have unpacked, and what that means.
  Review Changes  the per-field merge. Everything the mod changes, grouped
                  the way Edit Game Data is, with three values shown for
                  anything the update also touched.
  Compare         everything that changed between two saved versions,
                  including tables with no editor tab.

Compare is a tab rather than its own page because its real moment of use is
mid-review - "why is this a conflict, what else did that patch touch?" - and
losing your place in the review to go and look would be the wrong trade.

The page does not assume an update has happened. Reviewing a mod against the
same version it was built on is a perfectly reasonable thing to do: it
answers "what does my mod actually change?", which is useful on its own and
is the identical computation. Nothing breaks, and the honest result is
"nothing needs a decision".
"""
from __future__ import annotations

import platform
import threading
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path
from tkinter import messagebox, ttk

from .. import migration
from .. import paths
from .. import ui_settings
from .. import version_archive
from . import step_editor
from .app import WizardStepFrame
from .step_editor import ScrollableFrame

PAGE_TITLE = "Game Updates"

# How many grid rows to render before the grid scrolls itself. A Treeview
# sized to its full row count never scrolls internally, so Tk renders every
# row - fine at forty, unusable at UIEndCredit's 1,884. Set high enough that
# the great majority of tables still show whole.
GRID_MAX_VISIBLE_ROWS = 40

# Matches the Export page's preview font choice.
_MONO = ("Consolas", 9) if platform.system() == "Windows" else ("Monospace", 9)

OK_GREEN = "#2e7d32"
ATTENTION_AMBER = "#b06a00"
CONFLICT_RED = "#b00020"
MUTED = "#666666"

def _key_text(key) -> str:
    """
    A row key as something readable.

    compare_databases keys every row by a tuple, because a table may have
    one key column or two. Printing that straight gives "(10,)" - a Python
    tuple repr leaking into the interface. Single keys read as "10",
    composite ones as "155/1", which is how the Encounters tab already
    writes an address.
    """
    if isinstance(key, tuple):
        if len(key) == 1:
            return str(key[0])
        return "/".join(str(part) for part in key)
    return str(key)


def _fill_text(parent, lines: list, outer=None) -> None:
    """
    A read-only, full-height monospace block.

    Used wherever a list could run long. Individual Labels were the previous
    approach and don't scale - a real comparison reaches thousands of lines,
    which is thousands of widgets - and a fixed-height box with its own
    scrollbar nested inside a scrolling page is worse than either. One Text
    sized to its content builds instantly and can be selected and copied.
    """
    if not lines:
        return
    text = tk.Text(parent, wrap="none", height=len(lines), font=_MONO,
                   borderwidth=1, relief="solid")
    text.insert("1.0", "\n".join(lines))
    text.configure(state="disabled")
    text.pack(fill="x")
    if outer is not None:
        step_editor.bind_nested_scroll(text, outer)


def _subtle_note(before, after) -> str:
    """
    A parenthetical explaining a change too small to see.

    Real example from 1.4.0 to 1.5.2: a Japanese battle objective went from
    "べスラ要塞の水門を開け！" to "ベスラ要塞の水門を開け！" - Square fixed a
    single character, hiragana べ to katakana ベ. Rendered plainly that is
    two identical-looking lines with an arrow between them, which reads as
    a bug in the diff rather than as a typo fix in the game.

    So: when two strings are the same length and differ in only a few
    places, say exactly where and in which characters. Anything larger is
    a visible rewrite and needs no help.
    """
    if not (isinstance(before, str) and isinstance(after, str)) or before == after:
        return ""
    if len(before) != len(after):
        # Different lengths can still be an invisible change if the only
        # difference is padding.
        return "  (whitespace only)" if before.strip() == after.strip() else ""
    positions = [i for i, (x, y) in enumerate(zip(before, after)) if x != y]
    if not positions or len(positions) > 3:
        return ""
    parts = [f"char {i + 1}: U+{ord(before[i]):04X} \u2192 U+{ord(after[i]):04X}"
             for i in positions]
    return "  (" + "; ".join(parts) + ")"


def _short(value, limit: int = 70) -> str:
    """A value as one readable line."""
    if value is None:
        return "(not set)"
    text = str(value).replace("\n", " ").replace("\r", " ")
    if isinstance(value, str) and not text.strip():
        return "(empty)"
    return text if len(text) <= limit else text[: limit - 1] + "\u2026"


class GameUpdatesStep(WizardStepFrame):
    def __init__(self, parent, app):
        super().__init__(parent, app)

        self._plan = None
        self._baseline = None
        self._resolution_vars = {}      # id(FieldChange) -> (StringVar, change)
        self._unmodelled_vars = {}      # filename -> (StringVar, table)
        # filename -> {(row key, column)} the author still wants carried.
        # Survives a re-render so ticking boxes and then toggling a view
        # doesn't quietly undo the choices.
        self._change_selection = {}
        self._change_pickers = {}       # filename -> repaint callback
        self._merge_buttons = {}        # filename -> the "re-apply my N" radio
        self._sections_by_file = {}     # filename -> its CollapsibleSection
        self._busy = False
        self._show_clean = tk.BooleanVar(value=False)
        self._show_full_rows = tk.BooleanVar(
            value=ui_settings.load()["compare_show_full_rows"])
        self._compare_result = None      # (older, newer, deltas), for re-rendering
        self._compare_sections = []      # CollapsibleSection per differing table

        ttk.Label(self, text="Game Updates", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text=("When the game updates, a mod built against the old files can undo what "
                  "the update changed. This page re-applies your mod's changes to the game "
                  "files you have now, and shows you anything it can't carry over."),
            style="SubHeader.TLabel", wraplength=900, justify="left",
        ).pack(anchor="w", pady=(2, 12))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.status_tab = ScrollableFrame(self.notebook)
        self.review_tab = ScrollableFrame(self.notebook)
        self.compare_tab = ScrollableFrame(self.notebook)
        self.notebook.add(self.status_tab, text="Status")
        self.notebook.add(self.review_tab, text="Review Changes")
        self.notebook.add(self.compare_tab, text="Compare Versions")

        self._build_status()
        self._build_review()
        self._build_compare()

    # ======================================================================
    # Status
    # ======================================================================

    def _build_status(self) -> None:
        body = self.status_tab.inner

        box = ttk.LabelFrame(body, text="Versions", padding=12)
        box.pack(fill="x", pady=(4, 12))

        self.installed_var = tk.StringVar(value="Checking...")
        self.mod_version_var = tk.StringVar(value="None opened.")
        self.baseline_var = tk.StringVar(value="")
        self.verdict_var = tk.StringVar(value="")

        grid = ttk.Frame(box)
        grid.pack(fill="x")
        ttk.Label(grid, text="Game files you've unpacked:", width=30, anchor="w").grid(
            row=0, column=0, sticky="w", pady=2)
        ttk.Label(grid, textvariable=self.installed_var).grid(row=0, column=1, sticky="w", pady=2)
        ttk.Label(grid, text="The open mod:", width=30, anchor="w").grid(
            row=1, column=0, sticky="w", pady=2)
        ttk.Label(grid, textvariable=self.mod_version_var).grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(box, textvariable=self.baseline_var, wraplength=860, justify="left",
                  foreground=MUTED).pack(anchor="w", pady=(8, 0))
        self.verdict_label = ttk.Label(
            box, textvariable=self.verdict_var, wraplength=860, justify="left")
        self.verdict_label.pack(anchor="w", pady=(8, 0))

        archive_box = ttk.LabelFrame(body, text="Saved game versions", padding=12)
        archive_box.pack(fill="x", pady=(0, 12))
        ttk.Label(
            archive_box,
            text=("Each time you unpack, Mod Studio saves a compressed copy of that version's "
                  "game data. Once you update the game, the old files are gone from your "
                  "computer and can't be downloaded again - this copy is what makes updating "
                  "an older mod possible later."),
            wraplength=860, justify="left", foreground=MUTED,
        ).pack(anchor="w", pady=(0, 8))

        self.archive_list = ttk.Frame(archive_box)
        self.archive_list.pack(fill="x")
        self.archive_total_var = tk.StringVar(value="")
        ttk.Label(archive_box, textvariable=self.archive_total_var,
                  foreground=MUTED).pack(anchor="w", pady=(8, 0))

    def _refresh_status(self) -> None:
        state = self.app.state_data

        installed = None
        if state.nxd_sqlite_path:
            installed = migration.read_game_version(Path(state.nxd_sqlite_path))
        if installed:
            self.installed_var.set(installed)
        elif state.nxd_sqlite_path:
            self.installed_var.set("unpacked, but the version couldn't be read")
        else:
            self.installed_var.set("not unpacked yet")

        mod_open = bool(state.loaded_mod_config or state.loaded_mod_root)
        mod_sqlite = self._mod_sqlite()

        if not mod_open:
            self.mod_version_var.set("None opened.")
        elif mod_sqlite:
            name = (state.loaded_mod_config or {}).get("ModName") or (
                state.loaded_mod_root.name if state.loaded_mod_root else "opened mod")
            self.mod_version_var.set(str(name))
        else:
            self.mod_version_var.set("opened, but its game data files haven't been read yet")

        self._baseline = self._identify_baseline() if (mod_open and mod_sqlite) else None
        self.baseline_var.set(self._baseline.explain() if self._baseline else "")

        baseline = self._baseline
        fell_back = bool(baseline and baseline.fell_back)
        stale = bool(baseline and baseline.found and installed
                     and baseline.chosen.version != installed)
        if not state.nxd_sqlite_path:
            self.verdict_var.set(
                "Unpack your game files on General Setup first - that's what this page "
                "compares a mod against.")
            self.verdict_label.configure(foreground=MUTED)
        elif not mod_open:
            self.verdict_var.set(
                "Open a mod on General Setup and this page will show you everything it "
                "changes, and re-apply it to the game files you have now.")
            self.verdict_label.configure(foreground=MUTED)
        elif stale:
            self.verdict_var.set(
                f"This mod was built against {self._baseline.chosen.version}, and your game "
                f"files are {installed}. Its game data files replace the game's wholesale, so "
                f"as it stands it would undo whatever the update changed in them. Open Review "
                f"Changes to move it across.")
            self.verdict_label.configure(foreground=ATTENTION_AMBER)
        elif fell_back:
            # Not "up to date" - the baseline is a substitute. Saying
            # otherwise contradicted the line directly above it, and
            # contradicted Review Changes a moment later.
            self.verdict_var.set(
                f"This mod says it was built for {baseline.hint_version}, and there's no saved "
                f"copy of that version to compare it against. Review Changes will compare it "
                f"against {baseline.chosen.version} instead, so some of what it shows as your "
                f"mod's changes may really be things the update changed. Read the results with "
                f"that in mind.")
            self.verdict_label.configure(foreground=ATTENTION_AMBER)
        elif baseline and baseline.found:
            self.verdict_var.set(
                f"This mod was built against the game files you have ({installed}). Review "
                f"Changes will show you everything it changes; there shouldn't be anything to "
                f"decide, since there's no newer version to conflict with.")
            self.verdict_label.configure(foreground=OK_GREEN)
        else:
            self.verdict_var.set("No saved game version to compare this mod against yet.")
            self.verdict_label.configure(foreground=MUTED)

        self.app.set_sidebar_alert(PAGE_TITLE, stale)
        self._refresh_archives()

    def _mod_sqlite(self):
        """The converted database for the opened mod, if there is one."""
        state = self.app.state_data
        # Only the path recorded for *this* mod. There used to be a
        # fallback to local_data/mod_data.sqlite, which is a fixed path
        # reused by every mod - so opening a mod whose own .nxd couldn't be
        # converted silently compared the previous mod's data instead, and
        # loading the result pulled that mod's edits in. A missing path
        # means "this mod has no game data of its own", which is the truth.
        candidate = getattr(state, "mod_sqlite_path", None)
        if candidate and Path(candidate).exists():
            return Path(candidate)
        return None

    def _archive_candidates(self) -> list:
        """[(version, sqlite path)] for every saved version we can read directly."""
        candidates = []
        converter = version_archive.converter_fingerprint(
            self.app.state_data.ff16tools_cli_path)
        scratch = paths.local_data_dir() / "version_scratch"
        for entry in version_archive.list_archived():
            opened = version_archive.open_archived_database(
                entry, scratch / entry.directory.name, converter)
            if opened is not None:
                candidates.append((entry.version, opened))
        return candidates

    def _identify_baseline(self):
        state = self.app.state_data
        mod_sqlite = self._mod_sqlite()
        if mod_sqlite is None:
            return None
        hint, source = migration.detect_mod_game_version(state.loaded_mod_config, mod_sqlite)
        return migration.identify_baseline(
            mod_sqlite, self._archive_candidates(), hint or "", source if hint else "")

    def _refresh_archives(self) -> None:
        for child in self.archive_list.winfo_children():
            child.destroy()
        entries = version_archive.list_archived()
        if not entries:
            ttk.Label(
                self.archive_list,
                text="None saved yet - unpack your game files and this fills in.",
                foreground=MUTED,
            ).pack(anchor="w")
            self.archive_total_var.set("")
            return
        for entry in entries:
            ttk.Label(self.archive_list, text=entry.describe(), anchor="w").pack(
                anchor="w", pady=1)
        total = version_archive.total_size_bytes()
        self.archive_total_var.set(
            f"{len(entries)} version(s) saved, {total / 1_000_000:.1f} MB total. Older ones "
            f"are removed automatically once no installed mod needs them.")

    # ======================================================================
    # Review Changes
    # ======================================================================

    def _build_review(self) -> None:
        body = self.review_tab.inner

        # Both actions sit at the top. "Move My Changes Across" used to be
        # at the foot of the page, which meant scrolling past every conflict
        # to reach the button that acts on the decisions you just made -
        # and the longer the review, the further away the button got.
        controls = ttk.Frame(body)
        controls.pack(fill="x", pady=(4, 4))
        self.review_button = ttk.Button(
            controls, text="Check This Mod Against Your Game Files",
            command=self._start_review)
        self.review_button.pack(side="left")
        self.apply_button = ttk.Button(
            controls, text="Load Result Into Edit Game Data", command=self._apply_plan,
            state="disabled")
        self.apply_button.pack(side="left", padx=(8, 0))
        ttk.Checkbutton(
            controls, text="Also list changes that carry over cleanly",
            variable=self._show_clean, command=self._render_plan,
        ).pack(side="left", padx=(12, 0))
        ttk.Label(
            body,
            text="Your mod's changes, re-applied to the game files you have now. Review "
                 "them on the normal tabs, then use Export Mod to write the updated mod "
                 "out. The mod you opened isn't touched.",
            foreground=MUTED, wraplength=880, justify="left",
        ).pack(anchor="w", pady=(0, 6))

        self.review_summary_var = tk.StringVar(
            value="Nothing checked yet. Open a mod on General Setup, then use the button above.")
        self.review_summary_label = ttk.Label(
            body, textvariable=self.review_summary_var, wraplength=880, justify="left",
            foreground=MUTED)
        self.review_summary_label.pack(anchor="w", pady=(0, 8))

        self.review_body = ttk.Frame(body)
        self.review_body.pack(fill="both", expand=True)



    def _start_review(self) -> None:
        if self._busy:
            return
        state = self.app.state_data
        mod_sqlite = self._mod_sqlite()
        if mod_sqlite is None:
            messagebox.showinfo(
                "Nothing to check",
                "Open a mod on General Setup first. This page compares that mod's game data "
                "files against the ones you have unpacked.")
            return
        if not state.nxd_sqlite_path:
            messagebox.showinfo(
                "Game files needed",
                "Unpack your game files on General Setup first - that's what the mod gets "
                "compared against.")
            return
        baseline = self._identify_baseline()
        if baseline is None or not baseline.found:
            messagebox.showinfo(
                "No saved version to compare against",
                "Mod Studio saves a copy of your game data each time you unpack, and needs "
                "one to tell this mod's deliberate changes apart from values it simply "
                "hasn't caught up with.\n\nUnpack your game files once and this will work "
                "from then on.")
            return

        self._busy = True
        self.review_button.configure(state="disabled")
        self.apply_button.configure(state="disabled")
        self.review_summary_var.set("Comparing...")
        self.review_summary_label.configure(foreground=MUTED)

        current = Path(state.nxd_sqlite_path)
        mod_nxd_dir = self._mod_nxd_dir()
        game_nxd_dir = (Path(state.unpacked_game_dir) / "nxd"
                        if state.unpacked_game_dir else None)

        def worker():
            try:
                plan = migration.build_plan(baseline.chosen.sqlite_path, mod_sqlite, current)
                if mod_nxd_dir is not None:
                    # The baseline is what separates a value the author
                    # chose from one the mod simply hasn't caught up with.
                    plan.unmodelled = migration.assess_unmodelled(
                        mod_nxd_dir, mod_sqlite, current,
                        baseline_sqlite=baseline.chosen.sqlite_path,
                        game_nxd_dir=game_nxd_dir)
                self._dispatch(lambda: self._review_finished(plan, baseline, None))
            except Exception as exc:  # noqa: BLE001 - surface it rather than hang
                message = str(exc)
                self._dispatch(lambda: self._review_finished(None, baseline, message))

        threading.Thread(target=worker, daemon=True).start()

    def _dispatch(self, callback) -> None:
        """
        Hands a worker thread's result back to the interface thread.

        Wrapped because `after` raises if the widget has gone - the window
        closed, or the app is being driven without a mainloop - and that
        exception surfaces *inside the worker's own except block*, so the
        failure path fails too and the page is left permanently on
        "Comparing..." with its button disabled. Nothing useful can happen
        once the widget is gone, so dropping the result is the right
        answer; the alternative is a thread that dies noisily and a UI
        stuck forever.
        """
        try:
            self.after(0, callback)
        except (tk.TclError, RuntimeError):
            pass

    def _mod_nxd_dir(self):
        state = self.app.state_data
        if not state.loaded_mod_root:
            return None
        data_root = Path(state.loaded_mod_root) / "FFTIVC" / "data"
        if not data_root.is_dir():
            return None
        for child in sorted(data_root.glob("*/nxd")):
            if any(child.glob("*.nxd")):
                return child
        return None

    def _review_finished(self, plan, baseline, error) -> None:
        self._busy = False
        self.review_button.configure(state="normal")
        if error:
            self.review_summary_var.set(f"Couldn't compare: {error}")
            self.review_summary_label.configure(foreground=CONFLICT_RED)
            return
        self._plan = plan
        self._baseline = baseline
        self._change_selection = {}
        self._render_plan()

    def _render_plan(self) -> None:
        for child in self.review_body.winfo_children():
            child.destroy()
        self._resolution_vars.clear()
        self._unmodelled_vars.clear()
        self._change_pickers.clear()
        self._merge_buttons.clear()
        self._sections_by_file.clear()

        plan = self._plan
        if plan is None:
            return

        conflicts = plan.conflicts()
        orphaned = plan.by_outcome(migration.ORPHANED)
        clean = plan.by_outcome(migration.CLEAN) + plan.by_outcome(migration.REDUNDANT)

        if plan.is_noop():
            self.review_summary_var.set(
                f"{len(clean)} change(s) carry over cleanly. Nothing needs a decision - this "
                f"mod moves from {plan.from_version or 'its baseline'} to "
                f"{plan.to_version or 'your game files'} untouched.")
            self.review_summary_label.configure(foreground=OK_GREEN)
        else:
            self.review_summary_var.set(plan.summary())
            self.review_summary_label.configure(foreground=ATTENTION_AMBER)

        self.apply_button.configure(state="normal")

        if conflicts:
            self._render_conflicts(conflicts)
        if orphaned:
            self._render_orphaned(orphaned)
        if plan.structural:
            self._render_structural(plan.structural)
        if plan.advisories:
            self._render_advisories(plan.advisories)
        if plan.unmodelled:
            self._render_unmodelled(plan.unmodelled)
        if clean:
            self._render_clean(clean)

    def _section_frame(self, title: str, subtitle: str = "") -> ttk.Frame:
        box = ttk.LabelFrame(self.review_body, text=title, padding=10)
        box.pack(fill="x", pady=(0, 10))
        if subtitle:
            ttk.Label(box, text=subtitle, wraplength=850, justify="left",
                      foreground=MUTED).pack(anchor="w", pady=(0, 8))
        return box

    def _render_conflicts(self, conflicts: list) -> None:
        box = self._section_frame(
            f"Needs a decision ({len(conflicts)})",
            "The update changed the same field your mod changed. Pick which value to keep.")

        bulk = ttk.Frame(box)
        bulk.pack(anchor="w", pady=(0, 8))
        ttk.Button(bulk, text="Keep all of mine", style="Compact.TButton",
                   command=lambda: self._set_all(conflicts, migration.KEEP_MOD)).pack(side="left")
        ttk.Button(bulk, text="Take all from the update", style="Compact.TButton",
                   command=lambda: self._set_all(conflicts, migration.TAKE_UPDATE)).pack(
            side="left", padx=(6, 0))

        for section in self._ordered_sections(conflicts):
            ttk.Label(box, text=section, font=("Segoe UI", 10, "bold")).pack(
                anchor="w", pady=(6, 2))
            for change in [ch for ch in conflicts if ch.section == section]:
                self._render_conflict_row(box, change)

    def _render_conflict_row(self, parent, change) -> None:
        row = ttk.Frame(parent, padding=(8, 6))
        row.pack(fill="x", pady=2)

        label = f"{change.table} \u00b7 {_key_text(change.key)}"
        if change.label:
            label += f" \u2014 {change.label}"
        ttk.Label(row, text=f"{label}  \u00b7  {change.field_name}",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")

        # All three values, because two isn't enough to reason about: knowing
        # what the game used to have is what tells you whether the update is
        # a real rebalance or an incidental touch-up.
        values = ttk.Frame(row)
        values.pack(fill="x", pady=(3, 4))
        for i, (caption, value) in enumerate((
            (f"Was, {change.section and self._from_label() or 'old game'}", change.base_value),
            ("Your mod", change.mod_value),
            (f"Now, {self._to_label()}", change.new_value),
        )):
            ttk.Label(values, text=caption, width=16, anchor="w", foreground=MUTED).grid(
                row=i, column=0, sticky="w")
            ttk.Label(values, text=_short(value, 88), anchor="w").grid(
                row=i, column=1, sticky="w")

        var = tk.StringVar(value=change.resolution)
        self._resolution_vars[id(change)] = (var, change)
        choices = ttk.Frame(row)
        choices.pack(anchor="w")
        ttk.Radiobutton(choices, text="Keep my version", value=migration.KEEP_MOD,
                        variable=var,
                        command=lambda c=change, v=var: self._set_resolution(c, v)).pack(
            side="left")
        ttk.Radiobutton(choices, text="Take the update's", value=migration.TAKE_UPDATE,
                        variable=var,
                        command=lambda c=change, v=var: self._set_resolution(c, v)).pack(
            side="left", padx=(14, 0))

    def _from_label(self) -> str:
        return (self._plan.from_version if self._plan and self._plan.from_version
                else "old game")

    def _to_label(self) -> str:
        return self._plan.to_version if self._plan and self._plan.to_version else "new game"

    def _set_resolution(self, change, var) -> None:
        change.resolution = var.get()

    def _set_all(self, changes, resolution) -> None:
        for change in changes:
            change.resolution = resolution
            pair = self._resolution_vars.get(id(change))
            if pair:
                pair[0].set(resolution)

    def _render_orphaned(self, orphaned: list) -> None:
        rows = {}
        for change in orphaned:
            rows.setdefault((change.section, change.table, change.key), []).append(
                change.field_name)
        box = self._section_frame(
            f"Can't be carried over ({len(rows)} row(s))",
            "The update removed these rows, so there's nowhere for the changes to go. "
            "They'll be left out.")
        _fill_text(box, outer=self.review_tab, lines=[
            f"{section} \u00b7 {table} \u00b7 {_key_text(key)} \u2014 "
            f"{len(fields)} field(s): {', '.join(sorted(fields))}"
            for (section, table, key), fields in sorted(rows.items(), key=lambda kv: str(kv[0]))
        ])

    def _render_structural(self, findings: list) -> None:
        blocking = [f for f in findings if f.severity == "blocking"]
        box = self._section_frame(
            f"Encounter rows ({len(findings)})",
            "Your mod moves rows to different addresses. Here's how the update interacts "
            "with that.")
        for finding in findings:
            colour = {"blocking": CONFLICT_RED, "warning": ATTENTION_AMBER}.get(
                finding.severity, MUTED)
            ttk.Label(box, text=finding.detail, wraplength=850, justify="left",
                      foreground=colour).pack(anchor="w", pady=2)
        if blocking:
            ttk.Label(
                box,
                text=("A blocking item means two rows want the same address. That needs "
                      "sorting out on the Encounters tab before this mod will work."),
                wraplength=850, justify="left", foreground=CONFLICT_RED,
            ).pack(anchor="w", pady=(6, 0))

    def _render_advisories(self, advisories: list) -> None:
        box = self._section_frame(
            f"Worth a look ({len(advisories)})",
            "The update changed other fields on rows your mod also changes. Nothing "
            "conflicts, but the combination is something neither you nor the update "
            "designed - so it's worth an eye.")
        lines = []
        for advisory in advisories:
            label = f"{advisory.table} \u00b7 {_key_text(advisory.key)}"
            if advisory.label:
                label += f" \u2014 {advisory.label}"
            lines.append(f"{label}: you changed {', '.join(advisory.mod_fields)}; "
                         f"the update changed {', '.join(advisory.update_fields)}")
        _fill_text(box, lines, outer=self.review_tab)

    def _render_unmodelled(self, tables: list) -> None:
        merging = sum(1 for tb in tables if tb.recommendation == migration.REBASE)
        subtitle = ("Your mod ships these whole files. Because a file like this replaces the "
                    "game's copy completely, keeping one whole freezes that part of the game "
                    "at the version your mod was built on.")
        if merging:
            subtitle += (
                f"  {merging} of them can be merged instead - the game's new file with your "
                f"changes put back on top - so you keep both. Open one to pick which of your "
                f"changes carry over.")
        box = self._section_frame(
            f"Game data files with no editing tab ({len(tables)})", subtitle)

        for table in tables:
            self._render_unmodelled_row(box, table)

    def _render_unmodelled_row(self, box, table) -> None:
        row = ttk.Frame(box, padding=(6, 4))
        row.pack(fill="x", pady=1)

        # Facts only. An earlier version read "the mod is blank where the
        # game has content" as damage and said so; blanking a string is how
        # you remove a UI element, and describing that as damage told a
        # modder their deliberate work looked broken.
        detail = []
        if table.additions:
            detail.append(f"{table.additions} value(s) your mod sets")
        if table.losses:
            detail.append(f"{table.losses} value(s) your mod clears")
        if table.rows_missing:
            detail.append(f"{table.rows_missing} row(s) your mod doesn't have")
        if table.stale or table.rows_stale:
            bits = []
            if table.stale:
                bits.append(f"{table.stale} value(s)")
            if table.rows_stale:
                bits.append(f"{table.rows_stale} row(s)")
            detail.append(f"{' and '.join(bits)} the update changed that your copy predates")

        if not table.readable:
            summary = ("couldn't be read, so there's no telling what's in it - keeping it "
                       "unchanged is the safe choice")
        else:
            summary = "; ".join(detail) or "no differences from the game's copy"
        ttk.Label(row, text=f"{table.filename} \u2014 {summary}",
                  font=("Segoe UI", 9, "bold"), wraplength=840,
                  justify="left").pack(anchor="w")

        if table.purely_stale:
            ttk.Label(
                row,
                text=("Nothing in here is yours - it's the game's own file, from before the "
                      "update. Leaving it out lets the newer one through."),
                wraplength=830, justify="left", foreground=MUTED,
            ).pack(anchor="w")

        var = tk.StringVar(value=table.recommendation)
        self._unmodelled_vars[table.filename] = (var, table)
        choices = ttk.Frame(row)
        choices.pack(anchor="w", pady=(2, 0))
        if table.rebasable:
            merge_button = ttk.Radiobutton(
                choices, text="", value=migration.REBASE, variable=var)
            merge_button.pack(side="left")
            self._merge_buttons[table.filename] = merge_button
        ttk.Radiobutton(choices, text="Keep my whole copy", value=migration.KEEP_MOD,
                        variable=var).pack(side="left", padx=(14, 0) if table.rebasable else 0)
        ttk.Radiobutton(choices, text="Drop mine, use the game's", value=migration.DROP,
                        variable=var).pack(side="left", padx=(14, 0))
        if not table.rebasable and table.readable:
            ttk.Label(
                row,
                text=("The game doesn't ship a file by this name, so there's no newer copy to "
                      "merge yours onto - it can only be passed through whole or left out."),
                wraplength=830, justify="left", foreground=MUTED,
            ).pack(anchor="w")

        if table.rebasable and table.own_changes:
            # The section header is the one place that reports the count,
            # and it tracks the ticks. There were three of these before -
            # a static "6 change(s), all selected" on the header, a live
            # "5 of 6 selected" beside the buttons, and the radio label's
            # own static total - so unticking a box left two of the three
            # contradicting the thing that had just changed.
            section = step_editor.CollapsibleSection(
                row, "Choose which of your changes to carry over", "",
                builder=lambda body, tb=table, sec=None: self._build_change_picker(
                    body, tb, self._sections_by_file.get(tb.filename)),
            )
            self._sections_by_file[table.filename] = section
            section.pack(fill="x", pady=(4, 0))
            # The selection is established here, not when the picker is
            # first opened. Deferring it meant a change flagged to start
            # switched off was still switched *on* until you happened to
            # expand that section - so the count read 6 instead of 5, and
            # worse, applying without opening it carried the flagged change
            # anyway. The default has to be the default whether or not
            # anyone looks at it.
            self._change_selection.setdefault(table.filename, table.default_selection())
            self._refresh_change_counts(table)

    def _refresh_change_counts(self, table) -> None:
        """Keeps every label that mentions a count telling the same story."""
        total = table.change_count
        chosen = len(self._change_selection.get(
            table.filename, table.default_selection()))
        button = self._merge_buttons.get(table.filename)
        if button is not None:
            button.configure(
                text=f"Take the game's new file and re-apply my {chosen} change(s)")
        section = self._sections_by_file.get(table.filename)
        if section is not None:
            section.set_subtitle(
                f"{chosen} of {total} selected" if chosen != total
                else f"{total} change(s), all selected")

    def _build_change_picker(self, body, table, section=None) -> None:
        """
        Every individual change in one file, each one selectable.

        "Merge my changes" is the right default but it is all-or-nothing,
        and a mod can perfectly well contain edits its author no longer
        wants - especially after a game update has rewritten the thing they
        were working around. Showing them one at a time, with the game's
        current value beside each, turns an accept-everything button into an
        actual review.

        A Treeview rather than a stack of Checkbuttons: uibuttonguide.nxd
        carries 347 changes, and that many widgets is both slow to build and
        impossible to scan. Tk has no checkbox column, so the tick is drawn
        as text in the first column and toggled by clicking the row - which
        also makes the whole row a target rather than a ten-pixel box.
        """
        selected = self._change_selection.setdefault(
            table.filename, table.default_selection())

        # A "why not" column, present only when something is flagged, so the
        # ordinary case isn't paying for the rare one.
        flagged = bool(table.excluded_by_default)

        controls = ttk.Frame(body)
        controls.pack(fill="x", pady=(0, 4))
        ttk.Button(controls, text="Select all", style="Compact.TButton",
                   command=lambda: self._set_all_changes(table, True)).pack(side="left")
        ttk.Button(controls, text="Select none", style="Compact.TButton",
                   command=lambda: self._set_all_changes(table, False)).pack(
            side="left", padx=(6, 0))
        hint = "Click a row to include or exclude it."
        if flagged_count := len(table.excluded_by_default):
            hint += (f"  {flagged_count} row(s) start switched off, with the reason in the "
                     f"last column. Carrying the game's version number over would make it "
                     f"report the version your mod was built for rather than the one that's "
                     f"installed - but it's your mod, so turn it on if you mean to.")
        ttk.Label(body, text=hint, foreground=MUTED, wraplength=760,
                  justify="left").pack(anchor="w", pady=(0, 4))

        columns = ["tick", "row", "field", "mine", "theirs"] + (["why"] if flagged else [])
        picker_holder = ttk.Frame(body)
        picker_holder.pack(fill="x")
        picker_holder.columnconfigure(0, weight=1)
        tree = ttk.Treeview(picker_holder, columns=columns, show="headings",
                            selectmode="none")
        for column, heading, width in (
            ("tick", "", 34), ("row", "Row", 90), ("field", "Field", 150),
            ("mine", "Your value", 230), ("theirs", "The game's value", 230),
            # Measured from the reasons actually present rather than fixed:
            # a guessed width clipped the text mid-sentence, which is a poor
            # way to deliver an explanation.
            ("why", "Why it starts off", self._reason_width(table)),
        ):
            if column not in columns:
                continue
            tree.heading(column, text=heading)
            tree.column(column, width=width, minwidth=30, stretch=False, anchor="w")
        tree.tag_configure("off", foreground="#9a9a9a")

        item_keys = {}
        for key in sorted(table.own_changes, key=migration._sort_key):
            for column in sorted(table.own_changes[key]):
                mine = table.own_changes[key][column]
                theirs = (table.game_values.get(key) or {}).get(column)
                values = ["", _key_text(key), column,
                          _short(mine, 40), _short(theirs, 40)]
                if flagged:
                    # Blank rather than _short's "(empty)" placeholder: an
                    # unflagged row has no reason to give, and printing
                    # "(empty)" against five perfectly normal changes reads
                    # like something is missing from them.
                    reason = table.excluded_by_default.get((key, column))
                    values.append(_short(reason, 70) if reason else "")
                iid = tree.insert("", "end", values=values)
                item_keys[iid] = (key, column)

        def paint():
            for iid, pair in item_keys.items():
                on = pair in selected
                tree.set(iid, "tick", "\u2611" if on else "\u2610")
                tree.item(iid, tags=() if on else ("off",))
            self._refresh_change_counts(table)

        def toggle(event):
            iid = tree.identify_row(event.y)
            pair = item_keys.get(iid)
            if pair is None:
                return
            selected.discard(pair) if pair in selected else selected.add(pair)
            paint()

        tree.bind("<Button-1>", toggle)
        paint()
        holder = picker_holder
        tree.configure(height=min(len(item_keys), GRID_MAX_VISIBLE_ROWS))
        tree.grid(row=0, column=0, sticky="ew")

        if len(item_keys) > GRID_MAX_VISIBLE_ROWS:
            vbar = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vbar.set)
            vbar.grid(row=0, column=1, sticky="ns")

        # Total width can exceed the panel once a reason column is present,
        # which clipped the very explanation the column exists to give.
        total = sum(int(tree.column(column, "width")) for column in columns)
        if total > 900:
            hbar = ttk.Scrollbar(holder, orient="horizontal", command=tree.xview)
            tree.configure(xscrollcommand=hbar.set)
            hbar.grid(row=1, column=0, sticky="ew")

        step_editor.bind_nested_scroll(tree, self.review_tab)
        self._change_pickers[table.filename] = paint

    @staticmethod
    def _reason_width(table) -> int:
        """Wide enough for the longest reason actually present."""
        font = tkfont.Font(font=("Segoe UI", 9))
        widest = font.measure("Why it starts off") + 24
        for reason in table.excluded_by_default.values():
            widest = max(widest, font.measure(reason) + 24)
        return max(120, min(widest, 340))

    def _set_all_changes(self, table, on: bool) -> None:
        selected = self._change_selection.setdefault(table.filename, set())
        selected.clear()
        if on:
            selected.update((key, column)
                            for key, fields in table.own_changes.items() for column in fields)
        repaint = self._change_pickers.get(table.filename)
        if repaint:
            repaint()
        else:
            self._refresh_change_counts(table)

    def _selected_own_changes(self, table) -> dict:
        """The author's changes for one file, filtered to what they ticked."""
        # Falls back to the table's own default rather than to "everything",
        # so a flagged change is never carried just because nobody opened
        # the picker.
        selected = self._change_selection.get(table.filename)
        if selected is None:
            selected = table.default_selection()
        result = {}
        for key, fields in table.own_changes.items():
            kept = {column: value for column, value in fields.items()
                    if (key, column) in selected}
            if kept:
                result[key] = kept
        return result

    def _render_clean(self, clean: list) -> None:
        if not self._show_clean.get():
            ttk.Label(
                self.review_body,
                text=(f"{len(clean)} other change(s) carry over cleanly - the update didn't "
                      f"touch them. Tick the box above to list them."),
                foreground=MUTED, wraplength=880, justify="left",
            ).pack(anchor="w", pady=(0, 8))
            return
        box = self._section_frame(
            f"Carries over cleanly ({len(clean)})",
            "Nothing to do with these - open a section to see them all.")
        for section in self._ordered_sections(clean):
            rows = [ch for ch in clean if ch.section == section]
            step_editor.CollapsibleSection(
                box, section, f"{len(rows)} change(s)",
                builder=lambda body, r=rows: _fill_text(body, outer=self.review_tab, lines=[
                    f"{ch.table} \u00b7 {_key_text(ch.key)} \u00b7 {ch.field_name} "
                    f"\u2192 {_short(ch.mod_value, 60)}"
                    + ("   (the update makes this same change too)"
                       if ch.outcome == migration.REDUNDANT else "")
                    for ch in r
                ]),
            ).pack(fill="x", pady=(0, 2))

    @staticmethod
    def _ordered_sections(changes: list) -> list:
        order = [migration.SECTION_ABILITIES, migration.SECTION_ITEMS,
                 migration.SECTION_POACHING, migration.SECTION_ENCOUNTERS]
        present = {ch.section for ch in changes}
        return [name for name in order if name in present]

    def _apply_plan(self) -> None:
        """
        Loads the reviewed result into the editor, against the current game
        files.

        Deliberately not writing a mod folder from here. Export Mod already
        knows how to write one - icon handling, ModConfig merging, zipping,
        the Reloaded-II folder - and duplicating any of that would mean two
        code paths that have to agree forever. Handing the merged edits to
        the editor instead means the author sees them on the normal tabs
        before anything is written, which is the right last step. It also
        means the mod that was opened is untouched by construction rather
        than by care.
        """
        if self._plan is None:
            return

        # Immediate feedback, because the work that follows blocks the
        # interface for a few seconds - notify_data_loaded rebuilds every
        # tab, and Edit Game Data is a big one. Without this the button
        # looked ignored and the window looked hung.
        #
        # Nothing can go wrong during that pause: the interface thread is
        # what's busy, so clicks on the sidebar queue up and are handled
        # afterwards rather than reaching a half-loaded editor. Disabling
        # the button and saying so is about not looking broken, not about
        # preventing a race.
        # The button keeps its label. Swapping it to "Loading..." shrank the
        # widget, which reflowed the row it sits in, and the partial repaint
        # that followed drew the checkbox text twice on top of itself. The
        # status line below already carries the message and can change
        # length without moving anything.
        self.apply_button.configure(state="disabled")
        self.review_summary_var.set(
            "Loading your changes into Edit Game Data - this takes a moment while every "
            "tab reloads.")
        self.review_summary_label.configure(foreground=MUTED)
        # Focus off the button before it goes disabled: a disabled widget
        # doesn't fire the release binding that would normally take focus
        # away, so the dashed ring would sit there for the whole load.
        self.app.park_focus(self)
        self.update()

        try:
            self._apply_plan_now()
        finally:
            self.apply_button.configure(state="normal")

    def _apply_plan_now(self) -> None:
        recovered = migration.apply_plan(self._plan)
        state = self.app.state_data

        state.ability_edits = recovered.ability_edits
        state.override_action_edits = recovered.override_action_edits
        state.item_edits = recovered.item_edits
        state.chara_name_edits = recovered.chara_name_edits
        state.poach_edits = recovered.poach_edits
        state.entry_edits = recovered.entry_edits
        state.entry_rekeys = dict(recovered.entry_rekeys)
        state.entry_dropped = set(recovered.entry_dropped)

        # Dropped and rebased files both stop being carried through whole:
        # a dropped one is simply gone, and a rebased one is regenerated
        # from the game's new table instead, so passing the old file along
        # as well would have two sources writing the same output.
        dropped, rebased = [], {}
        for name, (var, table) in self._unmodelled_vars.items():
            choice = var.get()
            if choice == migration.DROP:
                dropped.append(name)
            elif choice == migration.REBASE:
                chosen = self._selected_own_changes(table)
                if chosen:
                    rebased[table.table] = chosen
                else:
                    # Merge selected but nothing ticked: the author has said
                    # they want none of their changes in this file, which is
                    # what dropping it means. Doing it explicitly beats
                    # writing a copy of the game's own file back out.
                    dropped.append(name)
        for name in list(dropped) + [t.filename for _n, (_v, t) in
                                     self._unmodelled_vars.items()
                                     if _v.get() == migration.REBASE]:
            for relative in list(state.other_file_replacements):
                if Path(relative).name.lower() == name.lower():
                    state.other_file_replacements.pop(relative, None)
        state.unmodelled_table_edits = rebased

        # Record what this now targets, so the next update starts from a
        # known baseline instead of working it out again.
        if self._plan.to_version:
            state.built_against_game_version = self._plan.to_version

        self.app.notify_data_loaded(exclude=self)
        self.app.set_sidebar_alert(PAGE_TITLE, False)

        kept = sum(1 for ch in self._plan.changes
                   if ch.outcome != migration.ORPHANED and ch.resolution != migration.DROP)
        detail = [f"{kept} change(s) loaded into the editor"]
        if rebased:
            merged = sum(len(rows) for rows in rebased.values())
            detail.append(f"{len(rebased)} file(s) merged onto the game's new copy "
                          f"({merged} row(s) of yours re-applied)")
        if dropped:
            detail.append(f"{len(dropped)} whole file(s) dropped")
        messagebox.showinfo(
            "Loaded into Edit Game Data",
            "\n".join(detail)
            + ("\n\nYour mod's changes are now sitting on top of the game files you have "
               "unpacked. Look them over on Edit Game Data, then use Export Mod to write the "
               "updated mod out. The mod you opened hasn't been changed."))

    # ======================================================================
    # Compare Versions
    # ======================================================================

    def _build_compare(self) -> None:
        body = self.compare_tab.inner

        ttk.Label(
            body,
            text=("Everything that changed between two saved game versions - including parts "
                  "of the game data this tool has no editing tab for."),
            wraplength=880, justify="left", foreground=MUTED,
        ).pack(anchor="w", pady=(4, 8))

        picker = ttk.Frame(body)
        picker.pack(fill="x", pady=(0, 8))
        ttk.Label(picker, text="From:").pack(side="left")
        self.compare_from = ttk.Combobox(picker, width=16, state="readonly")
        self.compare_from.pack(side="left", padx=(4, 12))
        ttk.Label(picker, text="To:").pack(side="left")
        self.compare_to = ttk.Combobox(picker, width=16, state="readonly")
        self.compare_to.pack(side="left", padx=(4, 12))
        self.compare_button = ttk.Button(picker, text="Compare", command=self._start_compare)
        self.compare_button.pack(side="left")
        ttk.Checkbutton(
            picker, text="Show whole rows", variable=self._show_full_rows,
            command=self._on_full_rows_toggled,
        ).pack(side="right")

        self.compare_summary_var = tk.StringVar(value="")
        self.compare_summary_label = ttk.Label(
            body, textvariable=self.compare_summary_var, wraplength=880, justify="left",
            foreground=MUTED)
        self.compare_summary_label.pack(anchor="w", pady=(0, 8))

        self._compare_bulk = ttk.Frame(body)
        ttk.Button(self._compare_bulk, text="Expand all", style="Compact.TButton",
                   command=lambda: self._set_all_compare_sections(True)).pack(side="left")
        ttk.Button(self._compare_bulk, text="Collapse all", style="Compact.TButton",
                   command=lambda: self._set_all_compare_sections(False)).pack(
            side="left", padx=(6, 0))
        ttk.Label(self._compare_bulk,
                  text="Click a table to open it. Expanding everything at once is slow "
                       "on a large update.",
                  foreground=MUTED).pack(side="left", padx=(10, 0))

        self.compare_body = ttk.Frame(body)
        self.compare_body.pack(fill="both", expand=True)

    def _refresh_compare(self) -> None:
        versions = [e.version for e in version_archive.list_archived()]
        self.compare_from.configure(values=versions)
        self.compare_to.configure(values=versions)
        if len(versions) >= 2:
            if not self.compare_from.get():
                self.compare_from.set(versions[1])   # the list is newest-first
            if not self.compare_to.get():
                self.compare_to.set(versions[0])
            self.compare_button.configure(state="normal")
        else:
            self.compare_button.configure(state="disabled")
            self.compare_summary_var.set(
                "Two saved versions are needed to compare. Mod Studio saves one each time you "
                "unpack, so this becomes available after the next game update.")
            self.compare_summary_label.configure(foreground=MUTED)

    def _start_compare(self) -> None:
        if self._busy:
            return
        older, newer = self.compare_from.get(), self.compare_to.get()
        if not older or not newer or older == newer:
            self.compare_summary_var.set("Pick two different saved versions.")
            self.compare_summary_label.configure(foreground=ATTENTION_AMBER)
            return

        converter = version_archive.converter_fingerprint(
            self.app.state_data.ff16tools_cli_path)
        scratch = paths.local_data_dir() / "version_scratch"
        opened_paths = {}
        for version in (older, newer):
            entry = version_archive.find_archived(version)
            opened = version_archive.open_archived_database(
                entry, scratch / version, converter) if entry else None
            if opened is None:
                self.compare_summary_var.set(
                    f"The saved copy of {version} can't be read directly - it needs converting "
                    f"from its game data files first, which isn't wired up here yet.")
                self.compare_summary_label.configure(foreground=ATTENTION_AMBER)
                return
            opened_paths[version] = opened

        self._busy = True
        self.compare_button.configure(state="disabled")
        self.compare_summary_var.set(f"Comparing {older} with {newer}...")
        self.compare_summary_label.configure(foreground=MUTED)

        def worker():
            try:
                deltas = migration.compare_databases(opened_paths[older], opened_paths[newer])
                self._dispatch(lambda: self._compare_finished(older, newer, deltas, None))
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                self._dispatch(lambda: self._compare_finished(older, newer, None, message))

        threading.Thread(target=worker, daemon=True).start()

    def _on_full_rows_toggled(self) -> None:
        """
        Switches between changed columns and whole rows, keeping open
        whatever was open.

        Re-rendering throws away every section and builds fresh ones, so
        without this the toggle silently collapsed the table you were
        looking at - you flipped it precisely *because* you were reading
        that table, and then had to find and reopen it.
        """
        ui_settings.save(compare_show_full_rows=self._show_full_rows.get())
        if not self._compare_result:
            return
        open_tables = {s._title for s in self._compare_sections if s.is_expanded}
        self._render_compare(*self._compare_result)
        for section in self._compare_sections:
            if section._title in open_tables:
                section.expand()

    def _compare_finished(self, older, newer, deltas, error) -> None:
        self._busy = False
        self.compare_button.configure(state="normal")
        if error:
            for child in self.compare_body.winfo_children():
                child.destroy()
            self._compare_result = None
            self.compare_summary_var.set(f"Couldn't compare: {error}")
            self.compare_summary_label.configure(foreground=CONFLICT_RED)
            return
        self._compare_result = (older, newer, deltas)
        self._render_compare(older, newer, deltas)

    def _render_compare(self, older, newer, deltas) -> None:
        for child in self.compare_body.winfo_children():
            child.destroy()
        self._compare_sections = []

        if not deltas:
            self._compare_bulk.pack_forget()
            self.compare_summary_var.set(
                f"{older} and {newer} are identical in every table saved for them - that "
                f"update changed no game data at all. More common than you'd expect.")
            self.compare_summary_label.configure(foreground=OK_GREEN)
            return

        changed = sum(len(d.rows_changed) for d in deltas.values())
        added = sum(len(d.rows_added) for d in deltas.values())
        removed = sum(len(d.rows_removed) for d in deltas.values())
        fields = sum(len(f) for d in deltas.values() for f in d.rows_changed.values())
        self.compare_summary_var.set(
            f"{len(deltas)} table(s) differ between {older} and {newer}: {changed} row(s) "
            f"changed ({fields} field(s)), {added} added, {removed} removed. Everything is "
            f"listed below - select and copy any of it.")
        self.compare_summary_label.configure(foreground=ATTENTION_AMBER)

        self._compare_bulk.pack(fill="x", pady=(0, 6), before=self.compare_body)
        for name in sorted(deltas):
            self._render_table_delta(deltas[name])

    def _set_all_compare_sections(self, expanded: bool) -> None:
        for section in self._compare_sections:
            section.expand() if expanded else section.collapse()

    def _render_table_delta(self, delta) -> None:
        """
        One table's differences, as a section you open when you want it.

        Collapsed by default and built on first expand - fifty tables and
        2,483 rows is what a real update looks like, and rendering all of
        it up front is slow and unreadable. Expanding one pays for one.
        """
        section = step_editor.CollapsibleSection(
            self.compare_body, delta.table, delta.summary(),
            builder=lambda body, d=delta: self._build_table_body(body, d),
        )
        section.pack(fill="x", pady=(0, 2))
        self._compare_sections.append(section)

    def _build_table_body(self, body, delta) -> None:
        """
        Both views are the same grid; the toggle only decides how many
        columns it has.

        Zodi asked for this after seeing the whole-row view: reading across
        a row is how you tell what a changed value belongs to, and there was
        no reason the default view should be a different shape. So the
        default shows the key columns plus the ones that actually changed,
        and "Show whole rows" adds the rest.
        """
        columns = list(delta.columns or [])
        if not columns:
            return
        if not self._show_full_rows.get():
            columns = self._changed_columns(delta) or columns
        self._build_grid(body, delta, columns)

    @staticmethod
    def _changed_columns(delta) -> list:
        """
        Key columns plus every column something actually changed in.

        Keys are always kept even when they didn't change - a grid of values
        with no way to tell which record they belong to is useless. Added
        and removed rows contribute nothing here: every one of their values
        is "new", so counting them would pull in the whole table and defeat
        the point.
        """
        changed = set()
        for fields in delta.rows_changed.values():
            changed.update(fields)
        if not changed:
            return []
        keys = migration._key_columns(delta.columns or [])
        return [c for c in (delta.columns or []) if c in changed or c in keys]

    def _build_grid(self, body, delta, columns) -> None:
        """
        A horizontal grid, in the shape a database browser uses.

        A changed row appears twice, `was` above `now`, so the two read
        against each other column by column; the `was` line is muted so a
        pair reads as one before/after unit. Added rows are green, removed
        red. A Treeview can't colour a single cell, so the marker column
        names which fields moved.

        **Height is capped and the widget scrolls itself past that point.**
        The first version sized every grid to its full row count so nothing
        needed an inner scrollbar, which is nicer to use right up until a
        table like UIEndCredit turns up with 1,884 rows: a Treeview that
        tall renders every row, because nothing is ever off its own
        viewport, and the whole page turns to treacle. Capped, Tk draws only
        the visible rows and scrolling is instant again. Most tables are
        well under the cap and still show whole with no scrollbar at all.
        """
        display = ["__what__"] + columns
        holder = ttk.Frame(body)
        holder.pack(fill="x")

        tree = ttk.Treeview(holder, columns=display, show="headings", selectmode="browse")
        tree.heading("__what__", text="")
        tree.column("__what__", width=self._label_width(delta), minwidth=80,
                    stretch=False, anchor="w")
        widths = self._column_widths(delta, columns)
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, width=widths[column], minwidth=44, stretch=False, anchor="w")

        tree.tag_configure("was", foreground="#8a8a8a")
        tree.tag_configure("added", foreground=OK_GREEN)
        tree.tag_configure("removed", foreground=CONFLICT_RED)

        rows = []
        for key in sorted(delta.rows_changed, key=migration._sort_key):
            old_row, new_row = delta.full_rows.get(key, (None, None))
            changed = delta.rows_changed[key]
            label = _key_text(key)
            rows.append(("was", [f"{label}  was"]
                         + [_short((old_row or {}).get(c), 60) for c in columns]))
            # The marker goes on the cells, not in the label. Listing the
            # changed field names in the label column read well until a row
            # changed several of them, at which point the list ran past the
            # column and was cut off mid-word - and since the cells carried
            # no marker of their own, the truncated text was the only record
            # of which fields moved. On the cell it can't be lost, and it
            # points at the value instead of describing it.
            rows.append(("", [f"{label}  now"]
                         + [(f"\u25b8 {_short((new_row or {}).get(c), 58)}" if c in changed
                             else _short((new_row or {}).get(c), 60)) for c in columns]))
        for key in delta.rows_added:
            row = (delta.full_rows.get(key) or (None, None))[1] or {}
            rows.append(("added", [f"{_key_text(key)}  added"]
                         + [_short(row.get(c), 60) for c in columns]))
        for key in delta.rows_removed:
            row = (delta.full_rows.get(key) or (None, None))[0] or {}
            rows.append(("removed", [f"{_key_text(key)}  removed"]
                         + [_short(row.get(c), 60) for c in columns]))

        for tag, values in rows:
            tree.insert("", "end", tags=(tag,) if tag else (), values=values)

        visible = min(len(rows), GRID_MAX_VISIBLE_ROWS)
        tree.configure(height=max(visible, 1))
        tree.grid(row=0, column=0, sticky="ew")
        holder.columnconfigure(0, weight=1)
        step_editor.bind_nested_scroll(tree, self.compare_tab)

        if len(rows) > GRID_MAX_VISIBLE_ROWS:
            vbar = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vbar.set)
            vbar.grid(row=0, column=1, sticky="ns")

        # A horizontal scrollbar whenever the columns don't fit. Without it
        # the rightmost columns were simply unreachable - a wide table like
        # OverrideEntryData has more columns than any window will hold, and
        # squeezing them to fit would make every value unreadable instead.
        total_width = sum(widths.values()) + self._label_width(delta)
        if total_width > 900:
            hbar = ttk.Scrollbar(holder, orient="horizontal", command=tree.xview)
            tree.configure(xscrollcommand=hbar.set)
            hbar.grid(row=1, column=0, sticky="ew")

        note = "\u25b8 marks a value the update changed."
        if len(rows) > GRID_MAX_VISIBLE_ROWS:
            note += f"  Showing {GRID_MAX_VISIBLE_ROWS} of {len(rows)} rows - scroll inside " \
                    f"the grid for the rest."
        ttk.Label(body, text=note, foreground=MUTED, wraplength=860,
                  justify="left").pack(anchor="w", pady=(2, 0))

    def _column_widths(self, delta, columns) -> dict:
        """
        Column widths measured from the text that will actually be in them.

        Measured with the font rather than guessed at characters-times-N: a
        constant leaves visible dead space on columns full of `0` and `-1`
        while still clipping bold headers, because those two errors run in
        opposite directions.

        **Sampled, not exhaustive, and that matters.** Measuring every value
        in every column was 6.3 of the 8.6 seconds it took to open the
        largest table - `font.measure` is a round trip into Tcl, and 942
        rows across 6 columns is eleven thousand of them. The Treeview's own
        1,884 inserts, by contrast, cost 0.01s. Two passes fix it: measure
        the longest *string* with Python, which is free, and only then ask
        the font about that one candidate per column.

        Longest-string is a proxy rather than a truth - a wide glyph can
        beat a longer run of narrow ones - so a little padding covers the
        difference, and the clamp bounds the damage either way.
        """
        font = tkfont.Font(font=_MONO)
        heading = tkfont.Font(font=("Segoe UI", 9, "bold"))
        widths = {}
        for column in columns:
            longest = ""
            for pair in delta.full_rows.values():
                for row in pair:
                    if row is None:
                        continue
                    value = row.get(column)
                    if value is None:
                        continue
                    text = value if isinstance(value, str) else str(value)
                    if len(text) > len(longest):
                        longest = text
            widest = heading.measure(column) + 18
            if longest:
                widest = max(widest, font.measure(_short(longest, 60)) + 20)
            widths[column] = max(44, min(widest, 460))
        return widths

    @staticmethod
    def _label_width(delta) -> int:
        """
        Width of the leading "which row, and what happened" column.

        Same sampling reason as above: the longest key is found with Python
        and only that one is measured.
        """
        font = tkfont.Font(font=("Segoe UI", 9))
        longest = ""
        for key in list(delta.rows_changed) + list(delta.rows_added) + list(delta.rows_removed):
            text = _key_text(key)
            if len(text) > len(longest):
                longest = text
        # Measures the longest label that can actually appear. These are
        # short and fixed now that the changed-field list has moved onto
        # the cells, so the column can't be surprised by its own content.
        widest = font.measure(f"{longest}  removed") + 16
        return max(90, min(widest, 260))

    # ======================================================================

    def on_show(self) -> None:
        # notify_data_loaded re-runs every page's on_show whenever General
        # Setup's background work lands, which can happen at any moment -
        # including mid-comparison. Re-identifying the baseline then would
        # duplicate work the worker is already doing and disturb the files
        # it is reading, so a busy page just leaves itself alone.
        if self._busy:
            return
        self._refresh_status()
        self._refresh_compare()
