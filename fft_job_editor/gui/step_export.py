"""
Step 3: fill in mod details, preview exactly what will be written, generate
the mod folder.

Output matches the real schema verified against Zodi's own published mod
(github.com/Zodi-ark/Dark-Knight-Expansion) - see modconfig.py.
"""

from __future__ import annotations

import os
import platform
import queue
import shutil
import subprocess
import threading
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Optional

from .. import constants as c
from .. import migration
from .. import ui_settings
from .. import audiomog, ff16tools, item_xml_io, modconfig, nxd_data, paths, reloaded, sound_data as sd, texture_data as td, xml_io
from .app import WizardStepFrame
from .step_editor import ScrollableFrame
from .step_setup import CollapsiblePane


def _entry_rowset_note(rekeys: dict, dropped: list) -> str:
    """
    Plain-language line for the export log when the encounter table's row
    set changes.

    Worth saying out loud because the previous behaviour was the opposite
    and silent: rows an author had removed came back from vanilla, so an
    opened 516-row mod exported as 526 and only turned up by byte-comparing
    the files.
    """
    bits = []
    if rekeys:
        bits.append(f"moved {len(rekeys)} encounter row(s) to a different Key/Key2")
    if dropped:
        bits.append(f"removed {len(dropped)} row(s) the mod doesn't have")
    return (
        "OverrideEntryData: " + ", ".join(bits)
        + ". The exported table keeps your row set rather than topping it back up from the game's."
    )

CATEGORY_SUGGESTIONS = ["gameplay", "graphics", "audio", "characters", "balance", "other"]


class ExportStep(WizardStepFrame):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._mod_id_manually_edited = False
        self._last_output_root: Optional[Path] = None
        self._applied_loaded_mod_root: Optional[Path] = None
        self._queue: queue.Queue = queue.Queue()
        self._pending_export_ops = 0   # nxd/texture/sound export can all run concurrently - zip waits for all
        self._build_layout()
        self._poll_queue()

    # -- layout ---------------------------------------------------------

    def _build_layout(self) -> None:
        ttk.Label(self, text="Export Mod", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            style="SubHeader.TLabel",
            wraplength=760,
            justify="left",
            text=(
                "Fill in your mod's details, check the contents look right, then generate it "
                "straight into your Reloaded-II Mods folder."
            ),
        ).pack(anchor="w", pady=(4, 12))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        # The form column is a fixed width but an unbounded height - the
        # Publishing section expands, and the destination note can run to
        # several lines - so it has to scroll. Without this, expanding
        # Publishing pushed Generate off the bottom of the window with no
        # way to reach it.
        left_holder = ttk.Frame(body, width=370)
        left_holder.pack(side="left", fill="y", padx=(0, 12))
        left_holder.pack_propagate(False)

        # One scroll region for the whole column. Pinning the generate area
        # to the bottom was tried and is worse: after an export it carries a
        # destination path, a result path and two buttons, so it grew to
        # most of the column's height and left the form itself showing two
        # fields. Keeping the column short is what actually solves this -
        # see the three status sections removed from _build_generate_area.
        left_scroll = ScrollableFrame(left_holder)
        left_scroll.pack(fill="both", expand=True)
        left = left_scroll.inner

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self._build_loaded_mod_banner(left)
        self._build_form(left)
        self._build_summary(left)
        self._build_generate_area(left)
        self._build_preview(right)

    def _build_loaded_mod_banner(self, parent) -> None:
        """
        The "you're editing an existing mod" banner.

        Two things it got wrong, both only visible once a mod was actually
        loaded (which is why an empty-state screenshot missed them):

        - It re-packed itself with a bare pack() after pack_forget(), and
          pack() appends. So the banner reappeared at the BOTTOM of the
          column, under the export buttons, instead of at the top where it
          was built. It now lives inside a holder frame that is always
          packed, so showing and hiding the banner can't move it.
        - Its label and "Start New Mod Instead" button were side by side in
          a fixed 370px column, so the button rendered as "Start Ne".
          Stacked now.
        """
        self.loaded_mod_banner_var = tk.StringVar(value="")
        self._banner_holder = ttk.Frame(parent)
        self._banner_holder.pack(fill="x")
        self.loaded_mod_banner_frame = ttk.Frame(self._banner_holder)
        self.loaded_mod_banner_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(
            self.loaded_mod_banner_frame, textvariable=self.loaded_mod_banner_var,
            foreground="#0a4e8e", wraplength=350, justify="left",
        ).pack(anchor="w", fill="x")
        ttk.Button(
            self.loaded_mod_banner_frame, text="Start New Mod Instead", command=self._start_new_mod
        ).pack(anchor="w", pady=(4, 0))
        self.loaded_mod_banner_frame.pack_forget()  # hidden until a mod is actually loaded

    def _build_form(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Mod Details", padding=12)
        box.pack(fill="x")

        self.mod_name_var = tk.StringVar()
        self.author_var = tk.StringVar()
        self.version_var = tk.StringVar(value="1.0.0")
        self.category_var = tk.StringVar(value="gameplay")
        self.mod_id_var = tk.StringVar()
        self.game_mode_var = tk.StringVar(value="enhanced")

        self._labeled_entry(box, "Mod Name", self.mod_name_var)
        self._labeled_entry(box, "Author", self.author_var)
        self._labeled_entry(box, "Version", self.version_var)

        cat_row = ttk.Frame(box)
        cat_row.pack(fill="x", pady=3)
        ttk.Label(cat_row, text="Category", width=12, anchor="w").pack(side="left")
        ttk.Combobox(
            cat_row, textvariable=self.category_var, values=CATEGORY_SUGGESTIONS, width=20
        ).pack(side="left", fill="x", expand=True)

        mode_row = ttk.Frame(box)
        mode_row.pack(fill="x", pady=3)
        ttk.Label(mode_row, text="Game Mode", width=12, anchor="w").pack(side="left")
        ttk.Combobox(
            mode_row, textvariable=self.game_mode_var, values=c.GAME_MODES,
            state="readonly", width=20,
        ).pack(side="left", fill="x", expand=True)

        id_row = ttk.Frame(box)
        id_row.pack(fill="x", pady=3)
        ttk.Label(id_row, text="Mod ID", width=12, anchor="w").pack(side="left")
        self.mod_id_entry = ttk.Entry(id_row, textvariable=self.mod_id_var)
        self.mod_id_entry.pack(side="left", fill="x", expand=True)
        self.mod_id_entry.bind("<Key>", lambda e: setattr(self, "_mod_id_manually_edited", True))

        self.mod_id_status_var = tk.StringVar(value="")
        ttk.Label(box, textvariable=self.mod_id_status_var, wraplength=340).pack(
            anchor="w", pady=(0, 6)
        )

        ttk.Label(box, text="Description", anchor="w").pack(anchor="w")
        # Mod descriptions are a paragraph or two - three lines meant
        # scrolling to read back what you just typed. The space came
        # free from collapsing the three export-status sections below.
        self.description_text = tk.Text(box, height=6, wrap="word")
        self.description_text.pack(fill="x", pady=(2, 0))

        # Live mod-id suggestion + validation + preview refresh
        self.mod_name_var.trace_add("write", self._on_form_changed)
        self.author_var.trace_add("write", self._on_form_changed)
        self.version_var.trace_add("write", self._on_form_changed)
        self.category_var.trace_add("write", self._on_form_changed)
        self.mod_id_var.trace_add("write", self._on_form_changed)
        self.game_mode_var.trace_add("write", self._on_game_mode_changed)
        self.description_text.bind("<KeyRelease>", lambda e: self._refresh_preview())

        self._build_publishing_form(parent)

    def _build_publishing_form(self, parent) -> None:
        """
        The Reloaded-II mod properties that aren't strictly needed to make a
        working mod, but are needed to *publish* one - the same things its
        own Edit Mod dialog exposes. Kept in its own collapsed section so
        someone testing a change locally never has to look at it.
        """
        # No subtitle: this sits next to a wide toggle button in a 395px
        # column, so "Icon, dependencies, auto-update" was rendering as
        # "Icon, depende". The section's own title already says enough.
        pane = CollapsiblePane(parent, "Publishing and Reloaded-II options")
        pane.pack(fill="x", pady=(10, 0))
        box = pane.inner

        # -- preview image ---------------------------------------------------
        ttk.Label(box, text="Preview image", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Label(
            box, wraplength=330, justify="left", foreground="#555555",
            text="Shown next to your mod in Reloaded-II. Copied into the mod folder as "
                 f"{modconfig.ICON_FILENAME}.",
        ).pack(anchor="w", pady=(0, 4))
        icon_row = ttk.Frame(box)
        icon_row.pack(fill="x")
        ttk.Button(
            icon_row, text="Choose image...", style="Compact.TButton", command=self._choose_icon
        ).pack(side="left")
        ttk.Button(
            icon_row, text="Remove", style="Compact.TButton", command=self._clear_icon
        ).pack(side="left", padx=(6, 0))
        self.icon_status_var = tk.StringVar(value="No image chosen.")
        ttk.Label(box, textvariable=self.icon_status_var, wraplength=330, justify="left").pack(
            anchor="w", pady=(4, 10)
        )

        # -- supported applications -------------------------------------------
        ttk.Label(box, text="Show this mod under", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Label(
            box, wraplength=330, justify="left", foreground="#555555",
            text="Which game executables the mod appears under in Reloaded-II. Follows Game Mode "
                 "above unless you change it.",
        ).pack(anchor="w", pady=(0, 4))
        self.app_id_vars: dict = {}
        for exe in ("fft_enhanced.exe", "fft_classic.exe"):
            var = tk.BooleanVar(value=exe in c.SUPPORTED_APP_IDS[self.game_mode_var.get()])
            self.app_id_vars[exe] = var
            var.trace_add("write", lambda *_a: self._refresh_preview())
            ttk.Checkbutton(box, text=exe, variable=var).pack(anchor="w")
        self._app_ids_manually_edited = False
        for var in self.app_id_vars.values():
            var.trace_add("write", self._mark_app_ids_edited)

        # -- dependencies ------------------------------------------------------
        ttk.Label(box, text="Requires these mods", font=("Segoe UI", 9, "bold")).pack(
            anchor="w", pady=(10, 0)
        )
        ttk.Label(
            box, wraplength=330, justify="left", foreground="#555555",
            text=f"{modconfig.MOD_LOADER_ID} is always required and is added for you. Anything else "
                 f"you tick is listed so Reloaded-II can warn people who don't have it.",
        ).pack(anchor="w", pady=(0, 4))
        self.dependency_vars: dict = {}
        self.dependency_box = ttk.Frame(box)
        self.dependency_box.pack(fill="x")
        self._refresh_dependency_list()

        # -- auto-update -------------------------------------------------------
        ttk.Label(box, text="Auto-update from GitHub", font=("Segoe UI", 9, "bold")).pack(
            anchor="w", pady=(10, 0)
        )
        ttk.Label(
            box, wraplength=330, justify="left", foreground="#555555",
            text="If you publish releases on GitHub, fill these in and Reloaded-II will offer "
                 "updates to anyone who installs the mod. Leave blank to skip.",
        ).pack(anchor="w", pady=(0, 4))

        self.gh_user_var = tk.StringVar()
        self.gh_repo_var = tk.StringVar()
        self.gh_use_tag_var = tk.BooleanVar(value=True)
        self.gh_asset_var = tk.StringVar(value=modconfig.DEFAULT_UPDATE_ASSET_NAME)
        self.project_url_var = tk.StringVar()

        self._labeled_entry(box, "GitHub user", self.gh_user_var, width=14)
        self._labeled_entry(box, "Repository", self.gh_repo_var, width=14)
        ttk.Checkbutton(
            box, text="Version comes from the release tag", variable=self.gh_use_tag_var
        ).pack(anchor="w", pady=(2, 0))
        self._labeled_entry(box, "Asset name", self.gh_asset_var, width=14)
        self._labeled_entry(box, "Project URL", self.project_url_var, width=14)

        for var in (self.gh_user_var, self.gh_repo_var, self.gh_asset_var,
                    self.project_url_var):
            var.trace_add("write", lambda *_a: self._refresh_preview())
        self.gh_use_tag_var.trace_add("write", lambda *_a: self._refresh_preview())

        self._icon_source: Optional[Path] = None

    def _mark_app_ids_edited(self, *_args) -> None:
        self._app_ids_manually_edited = True

    def _on_game_mode_changed(self, *_args) -> None:
        """Keep the app-id tick boxes in step with Game Mode until touched."""
        if not getattr(self, "_app_ids_manually_edited", False):
            defaults = c.SUPPORTED_APP_IDS.get(self.game_mode_var.get(), [])
            for exe, var in getattr(self, "app_id_vars", {}).items():
                if var.get() != (exe in defaults):
                    var.set(exe in defaults)
            self._app_ids_manually_edited = False
        self._on_form_changed()

    def _refresh_dependency_list(self) -> None:
        """
        Rebuilds the dependency tick list from whatever is installed in
        Reloaded-II right now, preserving anything already ticked (including
        ids from an opened mod that aren't installed on this machine - those
        would otherwise silently vanish from the config on regenerate).
        """
        already_on = {mod_id for mod_id, var in self.dependency_vars.items() if var.get()}
        for child in self.dependency_box.winfo_children():
            child.destroy()

        installed = reloaded.installed_mod_ids(self.app.state_data.reloaded_ii_path)
        # Parenthesised deliberately: `-` binds tighter than `|`, so without
        # these the mod loader would only be filtered out of already_on and
        # would still show up as a tick box from the installed list - which
        # is confusing, since it's always added automatically.
        candidates = sorted((set(installed) | already_on) - {modconfig.MOD_LOADER_ID})

        if not candidates:
            ttk.Label(
                self.dependency_box, foreground="#555555", wraplength=330, justify="left",
                text="No other mods found in your Reloaded-II Mods folder.",
            ).pack(anchor="w")
            self.dependency_vars = {}
            return

        new_vars: dict = {}
        for mod_id in candidates:
            var = tk.BooleanVar(value=mod_id in already_on)
            var.trace_add("write", lambda *_a: self._refresh_preview())
            new_vars[mod_id] = var
            ttk.Checkbutton(self.dependency_box, text=mod_id, variable=var).pack(anchor="w")
        self.dependency_vars = new_vars

    def _choose_icon(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Choose a preview image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All files", "*.*")],
        )
        if not chosen:
            return
        self._icon_source = Path(chosen)
        self.icon_status_var.set(f"Using: {self._icon_source.name}")
        self._refresh_preview()

    def _clear_icon(self) -> None:
        self._icon_source = None
        self.icon_status_var.set("No image chosen.")
        self._refresh_preview()

    @staticmethod
    def _labeled_entry(parent, label: str, var: tk.StringVar, width: int = 12) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=width, anchor="w").pack(side="left")
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)

    def _build_summary(self, parent) -> None:
        # Nothing here any more. This was a green one-line count ("2 job
        # command(s), 14 ability edit(s), ... will be included in this
        # mod"), which is exactly what the Summary tab on the right already
        # says - with the file list and the untouched categories alongside
        # it. Two copies of the same figure in one screen is one too many,
        # and this was the less useful copy.
        #
        # summary_count_var is kept because _refresh_preview still writes to
        # it and it costs nothing; if a future layout wants the line back,
        # it just needs a Label bound to it.
        self.summary_count_var = tk.StringVar(value="")

    def _build_generate_area(self, parent) -> None:
        box = ttk.Frame(parent)
        box.pack(fill="x", pady=(12, 0))

        ttk.Separator(box, orient="horizontal").pack(fill="x", pady=(0, 8))

        self.destination_var = tk.StringVar(value="")
        ttk.Label(
            box, textvariable=self.destination_var, wraplength=350, justify="left",
            foreground="#555555",
        ).pack(anchor="w", pady=(0, 6))

        self.generate_button = ttk.Button(
            box, text="Generate / Overwrite Mod", command=self._on_generate_clicked
        )
        self.generate_button.pack(anchor="w", fill="x")
        ttk.Button(
            box, text="Choose a Different Folder...", command=self._on_choose_different_folder_clicked
        ).pack(anchor="w", pady=(4, 0))

        self.generate_status_var = tk.StringVar(value="")
        self.generate_status_label = ttk.Label(
            box, textvariable=self.generate_status_var, wraplength=350, justify="left"
        )
        self.generate_status_label.pack(anchor="w", pady=(6, 0))

        # Side by side: two stacked full-width buttons cost a row of height
        # in a column that is pinned to the bottom, so every row here comes
        # out of the form's scroll space above.
        after_row = ttk.Frame(box)
        after_row.pack(anchor="w", fill="x", pady=(4, 0))
        self.open_folder_button = ttk.Button(
            after_row, text="Open Mod Folder", command=self._open_last_output, state="disabled"
        )
        self.open_folder_button.pack(side="left")
        self.zip_button = ttk.Button(
            after_row, text="Zip Mod...", command=self._on_zip_clicked, state="disabled"
        )
        self.zip_button.pack(side="left", padx=(6, 0))

        # One compact progress/results area, not three labelled sections.
        #
        # There used to be a separator + bold heading + status line for
        # each of .nxd, textures and sounds, and each result repeated the
        # full mod path - which is already stated once above, in "Mod
        # created/updated at". On a real export that was three headings and
        # three copies of "F:\The Ivalice Chronicles\Reloaded II\Mods\..."
        # filling most of the column.
        #
        # The three StringVars are kept because they carry live progress
        # ("Converting 12 texture(s)...") and, more importantly, partial
        # failures ("...but FF16Tools.CLI.exe isn't set up"). Those still
        # need somewhere to appear - they just don't each need a heading.
        self.nxd_export_status_var = tk.StringVar(value="")
        self.texture_export_status_var = tk.StringVar(value="")
        self.sound_export_status_var = tk.StringVar(value="")
        self._detail_status_labels = []
        for var in (self.nxd_export_status_var, self.texture_export_status_var,
                    self.sound_export_status_var):
            label = ttk.Label(box, textvariable=var, wraplength=350, justify="left",
                              foreground="#555555")
            label.pack(anchor="w", pady=(4, 0))
            self._detail_status_labels.append(label)
        self.nxd_export_status_label = self._detail_status_labels[0]
        self.texture_export_status_label = self._detail_status_labels[1]
        self.sound_export_status_label = self._detail_status_labels[2]

    def _build_preview(self, parent) -> None:
        header = ttk.Frame(parent)
        header.pack(fill="x", pady=(0, 6))
        ttk.Label(header, text="Mod Contents", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.show_all_sections_var = tk.BooleanVar(
            value=ui_settings.load()["export_show_all_sections"]
        )
        ttk.Checkbutton(
            header, text="Show every section", variable=self.show_all_sections_var,
            command=self._on_show_all_toggled,
        ).pack(side="right")

        self.preview_notebook = ttk.Notebook(parent)
        self.preview_notebook.pack(fill="both", expand=True)

        mono = ("Consolas", 9) if platform.system() == "Windows" else ("Monospace", 9)
        self._preview_groups = []

        # Summary first: the "what am I about to ship" answer, in plain
        # language, and the only tab a basic user needs to read.
        summary_tab = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(summary_tab, text="Summary")
        self.contents_preview = tk.Text(summary_tab, wrap="word", state="disabled", font=mono)
        self._add_scrollbars(summary_tab, self.contents_preview)
        self._summary_tab = summary_tab

        for group_label, files in self._preview_group_spec(mono):
            group_frame = ttk.Frame(self.preview_notebook)
            # Added up front, like the sub-tabs: a hidden ttk tab keeps its
            # slot in the tab order, so hiding and re-showing can never
            # scramble it. Adding lazily did - the first section to appear
            # landed at index 0 and stayed ahead of everything declared
            # before it.
            self.preview_notebook.add(group_frame, text=group_label)
            sub = ttk.Notebook(group_frame)
            sub.pack(fill="both", expand=True, padx=2, pady=2)
            entries = []
            for file_label, note, wrap, provider, predicate in files:
                file_tab = ttk.Frame(sub)
                sub.add(file_tab, text=file_label)
                if note:
                    ttk.Label(
                        file_tab, wraplength=350, justify="left", foreground="#666666", text=note,
                    ).pack(anchor="w", padx=8, pady=(8, 4))
                text_frame = ttk.Frame(file_tab)
                text_frame.pack(fill="both", expand=True)
                widget = tk.Text(text_frame, wrap=wrap, state="disabled", font=mono)
                self._add_scrollbars(text_frame, widget)
                entries.append({
                    "label": file_label, "tab": file_tab, "widget": widget,
                    "provider": provider, "predicate": predicate, "visible": True,
                })
            self._preview_groups.append({
                "label": group_label, "frame": group_frame, "notebook": sub,
                "files": entries, "visible": True,
            })

    def _preview_group_spec(self, mono):
        """
        (group label, [(file label, note, wrap mode, text provider, "has content?")]).

        Group labels match the Edit Game Data tabs one-for-one, on purpose -
        the two pages should name the same thing the same way. File labels
        are the real filenames the mod will contain.
        """
        state = self.app.state_data
        n = c.NXD_LANGUAGES

        def table(key):
            return (lambda: self._table_diff_xml_text(key),
                    lambda: state.edited_item_table_count(key) > 0)

        # Repeated on every .nxd sub-tab, so it has to be short.
        nxd_note = "Binary .nxd - rebuilt via FF16Tools, so there's a summary here rather than a diff."

        return [
            ("Mod Config", [
                ("ModConfig.json", "Reloaded-II's manifest for your mod.", "none",
                 lambda: self._config_preview_text(), lambda: True),
            ]),
            ("Jobs", [
                ("JobData.xml", None, "none",
                 lambda: xml_io.build_diff_xml_text(
                     state.table_version, self._gather_edited_jobs(), state.job_preserved),
                 lambda: state.edited_job_count() > 0),
            ]),
            ("Job Commands", [
                ("JobCommandData.xml", None, "none",
                 lambda: xml_io.build_job_command_diff_xml_text(
                     state.job_command_version, self._gather_edited_job_commands(),
                     state.job_command_preserved),
                 lambda: state.edited_job_command_count() > 0),
            ]),
            ("Abilities", [
                ("AbilityData.xml", None, "none", *table("ability")),
                ("AbilityEffectNumberFilterData.xml", None, "none", *table("ability_effect")),
                ("AbilityTypeData.xml", None, "none", *table("ability_animation")),
                (f"ability.<lang>.nxd", nxd_note, "word",
                 lambda: self._ability_nxd_summary_text(),
                 lambda: state.edited_ability_total_count() > 0 or state.edited_override_count() > 0),
            ]),
            ("Items", [
                ("ItemData.xml", None, "none", *table("item")),
                ("ItemWeaponData.xml", None, "none", *table("item_weapon")),
                ("ItemArmorData.xml", None, "none", *table("item_armor")),
                ("ItemShieldData.xml", None, "none", *table("item_shield")),
                ("ItemAccessoryData.xml", None, "none", *table("item_accessory")),
                ("ItemShopsData.xml", None, "none", *table("item_shops")),
                ("item.<lang>.nxd", nxd_note, "word",
                 lambda: self._item_nxd_summary_text(),
                 lambda: state.edited_item_text_total_count() > 0),
            ]),
            ("Equip Bonus", [
                ("ItemEquipBonusData.xml", None, "none", *table("item_equip_bonus")),
            ]),
            ("Poaching", [
                ("poachitem.<lang>.nxd", nxd_note, "word",
                 lambda: self._poach_summary_text(), lambda: state.has_any_poach_edits()),
            ]),
            ("Treasure Hunter", [
                ("MapTrapFormationData.xml", None, "none", *table("map_trap")),
            ]),
            ("Encounters", [
                ("overrideentrydata.nxd", nxd_note, "word",
                 lambda: self._entry_nxd_summary_text(), lambda: state.has_entry_changes()),
                ("charaname.<lang>.nxd", nxd_note, "word",
                 lambda: self._chara_name_summary_text(),
                 lambda: state.edited_chara_name_total_count() > 0),
            ]),
            ("Textures", [
                ("Replaced textures",
                 ".tga is copied as-is; .tex is converted with FF16Tools.CLI.", "word",
                 lambda: self._texture_summary_text(), lambda: state.has_any_texture_edits()),
            ]),
            ("Sounds", [
                ("Replaced sounds",
                 "Each edited .sab is unpacked and repacked with AudioMog.", "word",
                 lambda: self._sound_summary_text(), lambda: state.has_any_sound_edits()),
            ]),
        ]

    def _on_show_all_toggled(self) -> None:
        self._refresh_preview_visibility()
        ui_settings.save(export_show_all_sections=self.show_all_sections_var.get())

    def _refresh_preview_visibility(self) -> None:
        """
        Shows a group only when it has something in it (or "Show every
        section" is ticked), and the same for each file within a group.

        Uses insert/hide rather than rebuilding: _refresh_preview runs on
        every keystroke in the Mod Name field, so tearing down and
        recreating a dozen Text widgets each time would be visible.

        Visibility is tracked in Python rather than read back from Tk,
        because ttk raises on hide() for a tab that was never added, and
        the group frames start out unadded.
        """
        show_all = self.show_all_sections_var.get()
        for group in self._preview_groups:
            visible_files = 0
            for entry in group["files"]:
                if show_all or entry["predicate"]():
                    self._set_tab_visible(group["notebook"], entry)
                    visible_files += 1
                else:
                    self._set_tab_hidden(group["notebook"], entry)
            if visible_files:
                self._set_tab_visible(self.preview_notebook, group)
                self._select_first_visible(group["notebook"])
            else:
                self._set_tab_hidden(self.preview_notebook, group)

    @staticmethod
    def _set_tab_visible(notebook, holder) -> None:
        """
        Un-hides a tab. Every tab is added once at build time and only ever
        hidden or shown after that, so it keeps its declared slot - Jobs
        stays before Items no matter which of them was hidden a moment ago.
        """
        if holder.get("visible"):
            return
        child = holder.get("frame") or holder["tab"]
        try:
            notebook.add(child, text=holder["label"])
        except tk.TclError:
            pass
        holder["visible"] = True

    @staticmethod
    def _select_first_visible(notebook) -> None:
        """
        Makes sure a sub-notebook is actually showing one of its tabs.

        Hiding the selected tab leaves ttk with NO selection, so the pane
        went blank: opening Job Commands showed the JobCommandData.xml tab
        header with nothing underneath until you clicked the header. Which
        tabs are hidden changes on every refresh, so the selection has to be
        re-checked on every refresh too, not just set once at build time.
        """
        current = notebook.select()
        if current and str(notebook.tab(current, "state")) != "hidden":
            return
        for tab in notebook.tabs():
            if str(notebook.tab(tab, "state")) != "hidden":
                notebook.select(tab)
                return

    @staticmethod
    def _set_tab_hidden(notebook, holder) -> None:
        if not holder.get("visible"):
            return
        child = holder.get("frame") or holder["tab"]
        try:
            notebook.hide(child)
        except tk.TclError:
            pass
        holder["visible"] = False

    @staticmethod
    def _add_scrollbars(parent, text_widget: tk.Text) -> None:
        vscroll = ttk.Scrollbar(parent, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=vscroll.set)
        text_widget.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        # Only the XML/JSON panes scroll sideways. A wrap="word" pane never
        # overflows horizontally, so a horizontal bar there is dead chrome
        # eating a row of height in an already-short pane.
        if str(text_widget.cget("wrap")) == "none":
            hscroll = ttk.Scrollbar(parent, orient="horizontal", command=text_widget.xview)
            text_widget.configure(xscrollcommand=hscroll.set)
            hscroll.grid(row=1, column=0, sticky="ew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

    # -- data gathering ---------------------------------------------------

    def _gather_edited_jobs(self) -> list[tuple]:
        records_by_id = self.app.state_data.records_by_id()
        edited_jobs = []
        for job_id, fields in self.app.state_data.edits.items():
            if not fields:
                continue
            record = records_by_id.get(job_id)
            if record is None:
                continue
            edited_jobs.append((record, fields, record.name))
        edited_jobs.sort(key=lambda t: t[0].job_id)
        return edited_jobs

    def _gather_edited_job_commands(self) -> list[tuple]:
        commands_by_id = self.app.state_data.job_commands_by_id()
        edited_commands = []
        for command_id, fields in self.app.state_data.job_command_edits.items():
            if not fields:
                continue
            record = commands_by_id.get(command_id)
            if record is None:
                continue
            edited_commands.append((record, fields, record.name))
        edited_commands.sort(key=lambda t: t[0].command_id)
        return edited_commands

    def _gather_item_table_diffs(self) -> dict:
        """{filename: xml_text} for every Item*Data table with at least one edit - including
        "map_trap" (MapTrapFormationData.xml/Treasure Hunter), which lives in this same
        item_xml_io.ALL_SPECS-driven dict so it's picked up here for free."""
        state = self.app.state_data
        diffs = {}
        for table_key, spec in item_xml_io.ALL_SPECS.items():
            edits = state.item_table_edits.get(table_key, {})
            if not edits:
                continue
            records_by_id = state.item_table_records_by_id(table_key)
            edited_entries = []
            for item_id, fields in edits.items():
                if not fields:
                    continue
                record = records_by_id.get(item_id)
                if record is None:
                    continue
                edited_entries.append((record, fields, record.name))
            edited_entries.sort(key=lambda t: t[0].item_id)
            if not edited_entries:
                continue
            version = state.item_table_versions.get(table_key, "1")
            diffs[c.TABLE_FILENAMES[table_key]] = item_xml_io.build_diff_xml_text(
                spec, version, edited_entries, state.table_preserved.get(table_key))
        return diffs

    def _gather_meta(self) -> modconfig.ModMetadata:
        category = self.category_var.get().strip()
        chosen_apps = [exe for exe, var in self.app_id_vars.items() if var.get()]
        return modconfig.ModMetadata(
            mod_id=self.mod_id_var.get().strip(),
            mod_name=self.mod_name_var.get().strip(),
            author=self.author_var.get().strip(),
            version=self.version_var.get().strip() or "1.0.0",
            description=self.description_text.get("1.0", "end-1c").strip(),
            game_mode=self.game_mode_var.get(),
            tags=[category] if category else [],
            dependencies=[m for m, var in self.dependency_vars.items() if var.get()],
            # Empty means "nothing ticked" - fall back to the Game Mode
            # default rather than writing an empty SupportedAppId, which
            # would hide the mod from every application in the launcher.
            supported_app_ids=chosen_apps or None,
            project_url=self.project_url_var.get().strip(),
            icon_source=self._icon_source,
            # Preserve the name a mod already uses; only a newly chosen
            # image gets normalised to ICON_FILENAME.
            icon_filename=getattr(self, "_existing_icon_name", "") if self._icon_source is not None
            and getattr(self, "_existing_icon_name", "") and self._icon_source.name
            == getattr(self, "_existing_icon_name", "") else "",
            github_user=self.gh_user_var.get().strip(),
            github_repo=self.gh_repo_var.get().strip(),
            github_use_release_tag=bool(self.gh_use_tag_var.get()),
            github_asset_filename=self.gh_asset_var.get().strip(),
        )

    # -- loaded-mod handling -------------------------------------------------

    def _apply_loaded_mod_to_form(self) -> None:
        mod_root = self.app.state_data.loaded_mod_root
        config = self.app.state_data.loaded_mod_config

        if mod_root is None or config is None:
            self.mod_id_entry.configure(state="normal")
            self.loaded_mod_banner_var.set("")
            self.loaded_mod_banner_frame.pack_forget()
            return

        self._mod_id_manually_edited = True  # keep auto-suggest from clobbering it
        self.mod_name_var.set(config.get("ModName", ""))
        self.author_var.set(config.get("ModAuthor", ""))
        self.version_var.set(config.get("ModVersion", "") or "1.0.0")
        self.mod_id_var.set(config.get("ModId", mod_root.name))
        self.description_text.delete("1.0", "end")
        self.description_text.insert("1.0", config.get("ModDescription", ""))
        if self.app.state_data.loaded_game_mode:
            self.game_mode_var.set(self.app.state_data.loaded_game_mode)

        # Publishing fields - loaded back so a plain regenerate round-trips
        # them instead of clearing settings the user never touched here.
        self.project_url_var.set(config.get("ProjectUrl", "") or "")

        existing_apps = config.get("SupportedAppId") or []
        if existing_apps:
            self._app_ids_manually_edited = True
            for exe, var in self.app_id_vars.items():
                var.set(exe in existing_apps)

        existing_icon = (config.get("ModIcon") or "").strip()
        self._icon_source = None
        self._existing_icon_name = existing_icon
        if existing_icon:
            # Point at the mod's own copy so regenerating carries the image
            # across. Without this, ModConfig.json kept saying ModIcon:
            # preview.png while the file itself was left behind - the mod
            # showed a broken icon in Reloaded-II, and exporting to a new
            # folder lost it entirely.
            existing_path = mod_root / existing_icon
            if existing_path.is_file():
                self._icon_source = existing_path
                self.icon_status_var.set(f"Keeping the mod's existing image ({existing_icon}).")
            else:
                self.icon_status_var.set(
                    f"This mod's ModConfig.json points at {existing_icon}, but that file is "
                    f"missing - choose an image to fix it."
                )
        else:
            self.icon_status_var.set("No image chosen.")

        update = modconfig.read_update_settings(config)
        self.gh_user_var.set(update["user"])
        self.gh_repo_var.set(update["repo"])
        self.gh_use_tag_var.set(update["use_release_tag"])
        self.gh_asset_var.set(update["asset_filename"])

        existing_deps = [
            d for d in (config.get("ModDependencies") or [])
            if d and d != modconfig.MOD_LOADER_ID
        ]
        for mod_id in existing_deps:
            if mod_id not in self.dependency_vars:
                self.dependency_vars[mod_id] = tk.BooleanVar(value=True)
        self._refresh_dependency_list()
        for mod_id in existing_deps:
            if mod_id in self.dependency_vars:
                self.dependency_vars[mod_id].set(True)

        # Left editable on purpose. Locking it meant an opened mod could
        # only ever be written back over itself - there was no way to save a
        # variant, or to try a change without risking your working copy.
        # Changing the id makes this a new mod folder, which is exactly what
        # someone renaming it intends.
        self.mod_id_entry.configure(state="normal")
        self._mod_id_manually_edited = True   # don't re-derive it from the name
        # Deliberately no full path here - it's shown below, twice, in the
        # destination line and the result line. Four wrapped lines of blue
        # at the top of the column bought nothing.
        self.loaded_mod_banner_var.set(
            f"Editing existing mod: {config.get('ModName', mod_root.name)}. "
            f"Change the Mod ID below to save it as a separate mod instead of overwriting."
        )
        self.loaded_mod_banner_frame.pack(fill="x", pady=(0, 8))
        self._validate_mod_id()
        self._refresh_preview()

    def _start_new_mod(self) -> None:
        self.app.state_data.loaded_mod_root = None
        self.app.state_data.loaded_mod_config = None
        self.app.state_data.loaded_game_mode = None
        self._applied_loaded_mod_root = None
        self._mod_id_manually_edited = False
        self._apply_loaded_mod_to_form()
        self._on_form_changed()

    def _resolve_output_root(self) -> Optional[Path]:
        """Where to write without prompting, if it can be figured out automatically."""
        if self.app.state_data.loaded_mod_root is not None:
            return self.app.state_data.loaded_mod_root.parent
        if self.app.state_data.reloaded_ii_path is not None:
            return reloaded.effective_mods_folder(self.app.state_data.reloaded_ii_path)
        return None

    def _refresh_destination_label(self) -> None:
        mod_id = self.mod_id_var.get().strip() or "<mod-id>"
        loaded_root = self.app.state_data.loaded_mod_root
        if loaded_root is not None:
            mod_id = self.mod_id_var.get().strip()
            if mod_id and mod_id != loaded_root.name:
                # Renamed: this becomes a new folder beside the original,
                # which stays untouched.
                self.destination_var.set(
                    f"Will be created as a NEW mod at:\n{loaded_root.parent / mod_id}\n"
                    f"(the mod you opened is left as it is)"
                )
            else:
                self.destination_var.set(f"Will overwrite the mod already at:\n{loaded_root}")
        elif self.app.state_data.reloaded_ii_path is not None:
            mods_folder = reloaded.effective_mods_folder(self.app.state_data.reloaded_ii_path)
            target = mods_folder / mod_id
            note = ""
            # effective_mods_folder follows Reloaded-II's own config, which
            # for a non-portable install can be nowhere near the install
            # folder - worth saying so rather than looking like a bug.
            conventional = self.app.state_data.reloaded_ii_path / "Mods"
            try:
                if mods_folder.resolve() != conventional.resolve():
                    note = "\n(This is where Reloaded-II's own settings say it loads mods from.)"
            except OSError:
                pass
            self.destination_var.set(
                f"Will be placed in your Reloaded-II Mods folder:\n{target}{note}"
            )
        else:
            self.destination_var.set(
                "No Reloaded-II folder set (Step 1) - you'll be asked where to save."
            )

    # -- form change handlers -------------------------------------------------

    def _on_form_changed(self, *_args) -> None:
        if not self._mod_id_manually_edited:
            suggested = modconfig.suggest_mod_id(
                self.category_var.get() or "gameplay", self.mod_name_var.get() or "mymod"
            )
            if suggested != self.mod_id_var.get():
                self.mod_id_var.set(suggested)
                return  # the set() above re-triggers this trace; let that call finish the work
        self._validate_mod_id()
        self._refresh_preview()

    def _validate_mod_id(self) -> Optional[str]:
        mod_id = self.mod_id_var.get().strip()
        error = modconfig.validate_mod_id(mod_id) if mod_id else "Mod ID is required."
        if error:
            self.mod_id_status_var.set(error)
        else:
            self.mod_id_status_var.set(f"Will be created as: {mod_id}/")
        return error

    def _config_preview_text(self) -> str:
        """
        ModConfig.json as it will be written - merged into the existing
        file's config when editing a loaded mod, so fields this tool doesn't
        manage (icon, GitHub auto-update settings, custom tags) survive.
        """
        import json
        existing = self.app.state_data.loaded_mod_config
        meta = self._gather_meta()
        config = (
            modconfig.merge_mod_config(existing, meta) if existing is not None
            else modconfig.build_mod_config(meta)
        )
        return json.dumps(config, indent=2, ensure_ascii=False)

    def _ability_nxd_summary_text(self) -> str:
        state = self.app.state_data
        lines = []
        for lang in state.touched_ability_languages():
            count = state.edited_ability_count(lang)
            lines.append(
                f"{c.NXD_LANGUAGE_LABELS[lang]} (Ability-{lang}): {count} "
                f"abilit{'y' if count == 1 else 'ies'} edited."
            )
        if state.override_touched():
            count = state.edited_override_count()
            lines.append(
                f"Flags / Element / Overrides (overrideabilityactiondata.nxd, shared across every "
                f"language): {count} abilit{'y' if count == 1 else 'ies'} edited."
            )
        if not lines:
            return "(No ability text or flag/element/override edits yet.)"
        return "\n".join(lines) + self._nxd_pipeline_note()

    def _item_nxd_summary_text(self) -> str:
        state = self.app.state_data
        lines = []
        for lang in state.touched_item_languages():
            count = state.edited_item_text_count(lang)
            lines.append(
                f"{c.NXD_LANGUAGE_LABELS[lang]} (Item-{lang}): {count} "
                f"item{'s' if count != 1 else ''} edited."
            )
        if not lines:
            return "(No item name/description edits yet.)"
        return "\n".join(lines) + self._nxd_pipeline_note()

    def _entry_nxd_summary_text(self) -> str:
        """
        OverrideEntryData only - unit names moved to their own
        charaname.<lang>.nxd sub-tab, since they're a separate file.
        """
        state = self.app.state_data
        entry_count = state.edited_entry_count()
        if not entry_count and not state.entry_structure_changed():
            return "(No encounter unit edits yet.)"

        lines = []
        if entry_count:
            lines.append(f"{entry_count} unit slot(s) edited.")
        if state.entry_rekeys:
            lines.append(f"{len(state.entry_rekeys)} row(s) moved to a different encounter/unit slot:")
            for origin, destination in sorted(state.entry_rekeys.items()):
                lines.append(f"    {origin[0]}/{origin[1]}  \u2192  {destination[0]}/{destination[1]}")
        if state.entry_dropped:
            lines.append(f"{len(state.entry_dropped)} row(s) removed: " + ", ".join(
                f"{k}/{k2}" for k, k2 in sorted(state.entry_dropped)
            ))
        if state.entry_structure_changed():
            lines.append(
                f"The exported table will have {state.entry_row_count()} row(s) "
                f"(the database it was loaded from has {state.entry_baseline_row_count()})."
            )
        return "\n".join(lines) + self._nxd_pipeline_note()

    def _chara_name_summary_text(self) -> str:
        state = self.app.state_data
        lines = []
        for lang in state.touched_chara_name_languages():
            count = state.edited_chara_name_count(lang)
            lines.append(
                f"{c.NXD_LANGUAGE_LABELS[lang]} (CharaName-{lang}): {count} "
                f"unit name{'s' if count != 1 else ''} edited."
            )
        if not lines:
            return "(No unit name edits yet.)"
        return "\n".join(lines) + self._nxd_pipeline_note()

    def _nxd_pipeline_note(self) -> str:
        """The two things that stop a .nxd rebuild, said once, where it's relevant."""
        state = self.app.state_data
        if state.nxd_sqlite_path is None:
            return (
                "\n\nNo Ability, Item & Encounter Data database is loaded (General Setup) - "
                "these edits won't be exported until one is."
            )
        if state.ff16tools_cli_path is None:
            return (
                "\n\nFF16Tools.CLI.exe isn't set up (General Setup) - these edits won't be "
                "exported until it is."
            )
        return ""

    def _contents_summary_text(self) -> str:
        """
        The Summary tab: every category, in Edit Game Data's own order, with
        what it contributes - including the ones contributing nothing.

        That last part is why hiding empty preview tabs is safe. A category
        with no edits still appears here saying so, so "where did Textures
        go?" has an answer on the first tab rather than requiring the user
        to find the "Show every section" checkbox.
        """
        state = self.app.state_data
        edited_jobs = self._gather_edited_jobs()
        edited_commands = self._gather_edited_job_commands()

        rows = [
            ("Jobs", len(edited_jobs), "job"),
            ("Job Commands", len(edited_commands), "job command"),
            ("Abilities", (state.edited_ability_total_count() + state.edited_override_count()
                           + state.edited_ability_effect_count() + state.edited_ability_animation_count()
                           + state.edited_ability_data_count()), "edit"),
            ("Items", state.edited_item_text_total_count() + state.edited_item_table_total_count(), "edit"),
            ("Equip Bonus", state.edited_item_table_count("item_equip_bonus"), "edit"),
            ("Poaching", state.edited_poach_total_count(), "edit"),
            ("Treasure Hunter", state.edited_maptrap_count(), "map edit"),
            ("Encounters", state.changed_entry_row_count() + state.edited_chara_name_total_count(), "edit"),
            ("Textures", state.edited_texture_count(), "replacement"),
            ("Sounds", state.edited_sound_track_count(), "replacement"),
            # Decisions made on the Game Updates page. Without these two a
            # migration whose whole result was "merge these tables and drop
            # those files" reported "Nothing has been edited yet", which is
            # both wrong and alarming right after you have just reviewed and
            # accepted a set of changes.
            ("Game data (no tab)", state.rebased_table_count(), "merged table"),
            ("Carried through", state.carried_through_file_count(), "file"),
        ]

        lines = []
        touched = [(label, count, noun) for label, count, noun in rows if count]
        if not touched:
            lines.append("Nothing has been edited yet, so this mod would contain only its")
            lines.append("ModConfig.json. Go back to Edit Game Data to make changes.")
            lines.append("")
        else:
            lines.append("This mod will contain:")
            lines.append("")
            for label, count, noun in touched:
                lines.append(f"  {label:<18} {count} {noun}{'' if count == 1 else 's'}")
            lines.append("")
            files = self._files_to_be_written()
            lines.append(f"Files it will write ({len(files)}):")
            lines.append("")
            for name in files:
                lines.append(f"  {name}")
            lines.append("")

        untouched = [label for label, count, _n in rows if not count]
        if untouched:
            lines.append("Nothing edited in: " + ", ".join(untouched) + ".")
            lines.append("(Those sections are hidden above - tick \u201cShow every section\u201d to see them.)")
        return "\n".join(lines)

    def _files_to_be_written(self) -> list:
        """Every file the generated mod folder will contain, in preview order."""
        names = ["ModConfig.json"]
        for group in self._preview_groups:
            for entry in group["files"]:
                if entry["label"] == "ModConfig.json":
                    continue
                if entry["predicate"]():
                    names.append(entry["label"])
        return names

    def _refresh_preview(self) -> None:
        edited_jobs = self._gather_edited_jobs()
        edited_commands = self._gather_edited_job_commands()

        # Fill every preview pane, then decide which of them to show.
        for group in self._preview_groups:
            for entry in group["files"]:
                try:
                    text = entry["provider"]()
                except Exception as exc:  # noqa: BLE001 - a preview must never break Export
                    text = f"(Couldn't build this preview: {exc})"
                self._set_readonly_text(entry["widget"], text)
        self._set_readonly_text(self.contents_preview, self._contents_summary_text())
        self._refresh_preview_visibility()

        # Left-hand Changes Summary - the at-a-glance count next to the form.
        state = self.app.state_data
        counts = {
            "job(s)": len(edited_jobs),
            "job command(s)": len(edited_commands),
            "ability edit(s)": (state.edited_ability_total_count() + state.edited_override_count()
                                + state.edited_ability_effect_count()
                                + state.edited_ability_animation_count()
                                + state.edited_ability_data_count()),
            "item edit(s)": state.edited_item_text_total_count() + state.edited_item_table_total_count(),
            "encounter edit(s)": state.changed_entry_row_count() + state.edited_chara_name_total_count(),
            "poach item edit(s)": state.edited_poach_total_count(),
            "Treasure Hunter map edit(s)": state.edited_maptrap_count(),
            "texture replacement(s)": state.edited_texture_count(),
            "sound track replacement(s)": state.edited_sound_track_count(),
        }
        # Only non-zero categories, so the line stays short enough to read -
        # it used to list every category including the empty ones and ran to
        # four wrapped lines in a 340px column.
        bits = [f"{count} {noun}" for noun, count in counts.items() if count]
        if bits:
            summary_text = (
                ", ".join(bits[:-1]) + f", and {bits[-1]}" if len(bits) > 1 else bits[0]
            )
            self.summary_count_var.set(summary_text + " will be included in this mod.")
        else:
            self.summary_count_var.set("Nothing has been edited yet.")

        self._refresh_destination_label()

    @staticmethod
    def _set_readonly_text(widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _poach_summary_text(self) -> str:
        state = self.app.state_data
        touched_langs = state.touched_poach_languages()
        if not touched_langs:
            return "(No poaching edits yet.)"

        lines = []
        for lang in touched_langs:
            count = state.edited_poach_count(lang)
            lines.append(
                f"{c.NXD_LANGUAGE_LABELS[lang]} (PoachItem-{lang}): {count} "
                f"poach item{'s' if count != 1 else ''} edited."
            )

        lines.append("")
        tables = nxd_data.tables_to_reexport_poach(touched_langs)
        lines.append(f"Tables to re-export as .nxd: {', '.join(tables)}")
        if state.nxd_sqlite_path is None:
            lines.append(
                "No Ability, Item, Encounter & Poaching Data database is loaded (General Setup) - "
                "these edits won't be exported until one is."
            )
        elif state.ff16tools_cli_path is None:
            lines.append(
                "FF16Tools.CLI.exe isn't set up (General Setup) - these edits won't be exported "
                "until it is."
            )
        return "\n".join(lines)

    def _table_diff_xml_text(self, table_key: str) -> str:
        """Full diff XML text for one item_xml_io.ALL_SPECS table - the same per-table logic
        _gather_item_table_diffs uses internally, factored out so a table that gets its own
        dedicated preview section (shown in full, not folded into the generic Items loop -
        Treasure Hunter, and now Ability Effect/Unit Animations) can reuse it without
        re-deriving edited_entries by hand."""
        state = self.app.state_data
        spec = item_xml_io.ALL_SPECS[table_key]
        records_by_id = state.item_table_records_by_id(table_key)
        edited_entries = []
        for entry_id, fields in state.item_table_edits.get(table_key, {}).items():
            if not fields:
                continue
            record = records_by_id.get(entry_id)
            if record is None:
                continue
            edited_entries.append((record, fields, record.name))
        edited_entries.sort(key=lambda t: t[0].item_id)
        version = state.item_table_versions.get(table_key, "1")
        return item_xml_io.build_diff_xml_text(
            spec, version, edited_entries,
            self.app.state_data.table_preserved.get(table_key))

    def _texture_summary_text(self) -> str:
        state = self.app.state_data
        if not state.texture_edits:
            return "(No texture replacements staged yet.)"

        lines = [f"{len(state.texture_edits)} texture(s) staged for replacement:"]
        tex_needing_cli = 0
        face_count = 0
        for relative_path, info in sorted(state.texture_edits.items()):
            marker = " (face - seam-fix applied automatically)" if info.get("is_face_texture") else ""
            if info.get("is_face_texture"):
                face_count += 1
            lines.append(f"  {relative_path}{marker}")
            lines.append(f"    <- {info['source_path']}")
            if relative_path.lower().endswith(".tex"):
                tex_needing_cli += 1

        lines.append("")
        if tex_needing_cli and state.ff16tools_cli_path is None:
            lines.append(
                f"{tex_needing_cli} of these are .tex files - FF16Tools.CLI.exe isn't set up "
                "(General Setup), so these won't be exported until it is."
            )
        if state.unpacked_game_dir is None:
            lines.append(
                "No unpacked game folder is set (General Setup) - textures won't be exported until "
                "one is, since that's also where the mod's own destination path structure is mirrored from."
            )
        return "\n".join(lines)

    def _sound_summary_text(self) -> str:
        state = self.app.state_data
        if not state.sound_edits:
            return "(No sound replacements staged yet.)"

        track_total = state.edited_sound_track_count()
        lines = [f"{state.edited_sound_file_count()} sound file(s), {track_total} track(s) staged for replacement:"]
        for relative_path, tracks in sorted(state.sound_edits.items()):
            if not tracks:
                continue
            lines.append(f"  {relative_path}")
            for track_index, edit in sorted(tracks.items()):
                loop_note = (
                    f" (loop {edit['loop_start']:,}\u2013{edit['loop_end']:,})"
                    if edit.get("loop_start") is not None and edit.get("loop_end") is not None
                    else ""
                )
                lines.append(f"    track {track_index}{loop_note} <- {edit['source_path']}")

        lines.append("")
        if state.audiomog_exe_path is None:
            lines.append("AudioMog.exe isn't set up (General Setup) - these won't be exported until it is.")
        if state.unpacked_game_dir is None:
            lines.append(
                "No unpacked game folder is set (General Setup) - sound replacements won't be exported "
                "until one is, since that's also where the vanilla .sab files to unpack come from and "
                "where the mod's own destination path is mirrored from."
            )
        return "\n".join(lines)

    # -- generation ---------------------------------------------------------

    def _validate_form(self) -> tuple[bool, str]:
        if not self.mod_name_var.get().strip():
            return False, "Enter a mod name."
        if not self.author_var.get().strip():
            return False, "Enter an author name."
        mod_id_error = self._validate_mod_id()
        if mod_id_error:
            return False, mod_id_error
        state = self.app.state_data
        if (
            not state.edited_job_count() and not state.edited_job_command_count()
            and not state.has_any_ability_edits() and not state.has_any_item_edits()
            # has_any_ability_edits()/has_any_item_edits() deliberately don't cover these four -
            # see their own docstrings in app.py (has_any_maptrap_edits/has_any_poach_edits were
            # already excluded from has_any_item_edits() on purpose; has_any_ability_effect_edits/
            # has_any_ability_animation_edits are deliberately excluded from has_any_ability_edits()
            # since that one specifically gates the nxd re-export pipeline, which these don't need).
            # Omitting them here would have meant editing ONLY Treasure Hunter, Poaching, Ability
            # Effect, or Unit Animations - with nothing else touched - incorrectly reported
            # "Nothing has been edited yet" and blocked Export entirely.
            and not state.has_any_maptrap_edits() and not state.has_any_poach_edits()
            and not state.has_any_ability_effect_edits() and not state.has_any_ability_animation_edits()
            and not state.has_any_ability_data_edits()
            and not state.has_any_encounter_edits() and not state.has_any_texture_edits()
            and not state.has_any_sound_edits()
        ):
            return False, (
                "Nothing has been edited yet. Go back to Step 2 to make changes."
            )
        return True, ""

    def _on_generate_clicked(self) -> None:
        ok, message = self._validate_form()
        if not ok:
            self.generate_status_var.set(message)
            self.generate_status_label.configure(foreground="#b00020")
            return

        output_root = self._resolve_output_root()
        if output_root is None:
            chosen = filedialog.askdirectory(
                title="Choose a folder to create your mod in (e.g. your Reloaded-II Mods folder)",
                initialdir=str(self._last_output_root) if self._last_output_root else None,
            )
            if not chosen:
                return
            output_root = Path(chosen)

        self._generate_mod(output_root)

    def _on_choose_different_folder_clicked(self) -> None:
        ok, message = self._validate_form()
        if not ok:
            self.generate_status_var.set(message)
            self.generate_status_label.configure(foreground="#b00020")
            return

        chosen = filedialog.askdirectory(
            title="Choose a folder to create your mod in",
            initialdir=str(self._last_output_root) if self._last_output_root else None,
        )
        if chosen:
            self._generate_mod(Path(chosen))

    def _generate_mod(self, output_root: Path) -> None:
        meta = self._gather_meta()
        edited_jobs = self._gather_edited_jobs()
        xml_text = xml_io.build_diff_xml_text(
            self.app.state_data.table_version, edited_jobs, self.app.state_data.job_preserved)

        edited_commands = self._gather_edited_job_commands()
        job_command_xml_text = xml_io.build_job_command_diff_xml_text(
            self.app.state_data.job_command_version, edited_commands,
            self.app.state_data.job_command_preserved,
        ) if edited_commands else None

        item_table_diffs = self._gather_item_table_diffs()

        existing_config = self.app.state_data.loaded_mod_config
        config = (
            modconfig.merge_mod_config(existing_config, meta)
            if existing_config is not None
            else modconfig.build_mod_config(meta)
        )

        try:
            mod_root = modconfig.scaffold_mod_folder(
                output_root, meta, xml_text, config=config,
                job_command_xml_text=job_command_xml_text,
                extra_table_files=item_table_diffs,
            )
        except OSError as exc:
            self.generate_status_var.set(f"Couldn't write the mod folder: {exc}")
            self.generate_status_label.configure(foreground="#b00020")
            return

        self._last_output_root = output_root
        self.generate_status_var.set(f"Mod created/updated at:\n{mod_root}")
        self.generate_status_label.configure(foreground="#0a6e0a")
        self.open_folder_button.configure(state="normal")
        self._last_mod_root = mod_root

        # Adopt what we just wrote as the new "loaded mod" baseline, so a
        # second click of Generate/Overwrite updates this same mod in place
        # instead of prompting for a folder again or risking a duplicate.
        self.app.state_data.loaded_mod_root = mod_root
        self.app.state_data.loaded_mod_config = config
        self.app.state_data.loaded_game_mode = meta.game_mode
        self._applied_loaded_mod_root = mod_root
        self._apply_loaded_mod_to_form()

        # Zipping before ability/item/encounter, texture, or sound edits land
        # would silently ship an incomplete mod, so the button stays disabled
        # until every async export operation kicked off below finishes (all
        # three can run concurrently and are independent of each other).
        self._pending_export_ops = 0
        self._maybe_export_nxd(mod_root, meta.game_mode)
        self._maybe_export_textures(mod_root, meta.game_mode)
        self._maybe_export_sounds(mod_root, meta.game_mode)
        self.zip_button.configure(state="disabled" if self._pending_export_ops else "normal")

    def _begin_export_op(self) -> None:
        self._pending_export_ops += 1
        self.zip_button.configure(state="disabled")

    def _end_export_op(self) -> None:
        self._pending_export_ops = max(0, self._pending_export_ops - 1)
        if self._pending_export_ops == 0:
            self.zip_button.configure(state="normal")

    def _maybe_export_nxd(self, mod_root: Path, mode: str) -> None:
        state = self.app.state_data
        touched_item_langs = state.touched_item_languages()
        touched_chara_langs = state.touched_chara_name_languages()
        # Moving or removing a row changes the exported table just as much
        # as editing a field does, so the .nxd has to be rebuilt for those
        # too - a mod whose ONLY change is repurposing ten rows is a real
        # case (that's most of what Dark Knight Expansion does).
        entry_touched = state.has_entry_changes()
        touched_poach_langs = state.touched_poach_languages()
        # Tables with no editor tab, merged by the Game Updates page's
        # Rebase option. They can be the only reason to run this whole
        # path - a migration whose sole change is putting a mod's UI
        # strings back on top of the game's newer table is a real case.
        unmodelled_edits = {
            table: {key: dict(fields) for key, fields in rows.items()}
            for table, rows in (state.unmodelled_table_edits or {}).items() if rows
        }
        if (
            not state.has_any_ability_edits() and not touched_item_langs
            and not touched_chara_langs and not entry_touched and not touched_poach_langs
            and not unmodelled_edits
        ):
            self.nxd_export_status_var.set("")
            return

        if state.nxd_sqlite_path is None or state.ff16tools_cli_path is None:
            missing = []
            if state.nxd_sqlite_path is None:
                missing.append("an Ability, Item, Encounter & Poaching Data database")
            if state.ff16tools_cli_path is None:
                missing.append("FF16Tools.CLI.exe")
            self.nxd_export_status_var.set(
                "Ability/Item/Encounter/Poaching text edits exist but weren't exported - missing "
                + " and ".join(missing) + " (set up in General Setup, then Generate again)."
            )
            self.nxd_export_status_label.configure(foreground="#b00020")
            return

        touched_ability_langs = state.touched_ability_languages()
        override_touched = state.override_touched()
        ability_edits_snapshot = {lang: dict(edits) for lang, edits in state.ability_edits.items()}
        override_edits_snapshot = dict(state.override_action_edits)
        item_edits_snapshot = {lang: dict(edits) for lang, edits in state.item_edits.items()}
        chara_edits_snapshot = {lang: dict(edits) for lang, edits in state.chara_name_edits.items()}
        entry_edits_snapshot = dict(state.entry_edits)
        entry_rekeys_snapshot = dict(state.entry_rekeys)
        entry_dropped_snapshot = list(state.entry_dropped)
        poach_edits_snapshot = {lang: dict(edits) for lang, edits in state.poach_edits.items()}
        sqlite_source = state.nxd_sqlite_path
        cli_path = state.ff16tools_cli_path

        self._begin_export_op()
        self.nxd_export_status_var.set("Applying ability/item/encounter/poaching text edits and converting to .nxd...")
        self.nxd_export_status_label.configure(foreground="#666666")

        def worker() -> None:
            try:
                staging_dir = paths.local_data_dir() / "nxd_export_staging"
                staged_sqlite = nxd_data.stage_sqlite_copy(sqlite_source, staging_dir)
                for lang in touched_ability_langs:
                    nxd_data.write_ability_edits(staged_sqlite, lang, ability_edits_snapshot.get(lang, {}))
                if override_touched:
                    nxd_data.write_override_action_edits(staged_sqlite, override_edits_snapshot)
                for lang in touched_item_langs:
                    nxd_data.write_item_edits(staged_sqlite, lang, item_edits_snapshot.get(lang, {}))
                for lang in touched_chara_langs:
                    nxd_data.write_charaname_edits(staged_sqlite, lang, chara_edits_snapshot.get(lang, {}))
                if entry_touched:
                    # Order matters: move rows to their final addresses
                    # first, drop any the author removed, then apply field
                    # edits (translated to follow the rows that moved).
                    #
                    # Rows the author removed are NOT topped back up from
                    # vanilla. That used to happen implicitly - export
                    # rebuilt from the game's own database, so an opened
                    # mod's 516 rows came back out as 526 - and it was
                    # wrong: since a .nxd replaces the game's file
                    # wholesale, and rows can't be added in a way the game
                    # picks up, dropping a row is how an author frees an
                    # address to repurpose. Restoring it silently undid
                    # half of that.
                    nxd_data.apply_override_entry_rekeys(staged_sqlite, entry_rekeys_snapshot)
                    nxd_data.delete_override_entry_rows(staged_sqlite, entry_dropped_snapshot)
                    nxd_data.write_override_entry_edits(
                        staged_sqlite,
                        nxd_data.translate_entry_edits(entry_edits_snapshot, entry_rekeys_snapshot),
                    )
                    if entry_rekeys_snapshot or entry_dropped_snapshot:
                        self._queue.put(("nxd_status", _entry_rowset_note(
                            entry_rekeys_snapshot, entry_dropped_snapshot
                        )))
                for lang in touched_poach_langs:
                    nxd_data.write_poach_edits(staged_sqlite, lang, poach_edits_snapshot.get(lang, {}))

                # Tables being merged that the working database doesn't
                # hold - uibuttonguide and friends. The game's copy is
                # fetched from its own .nxd on demand and imported, so a
                # merge isn't limited to the tables that happen to have an
                # editor tab. Only the files actually needed are converted,
                # so this costs nothing on an export that merges nothing.
                # Normally empty: unpacking converts every .nxd the game
                # ships, so the staged database already has the table. This
                # is the fallback for the handful FF16Tools can't convert -
                # configitemclassictextlanguage.nxd and
                # configitemdifficultylevel.nxd produce no table at all -
                # and for a database made by an older build of this tool,
                # back when only 37 files were converted.
                missing = nxd_data.tables_missing_from(staged_sqlite, list(unmodelled_edits))
                if missing:
                    fetched = self._fetch_game_tables(
                        staging_dir, missing, cli_path,
                        lambda line: self._queue.put(("nxd_status", line)))
                    if fetched:
                        nxd_data.import_tables_from(staged_sqlite, fetched, missing)
                    still_missing = nxd_data.tables_missing_from(
                        staged_sqlite, list(unmodelled_edits))
                    for table_name in still_missing:
                        unmodelled_edits.pop(table_name, None)
                        self._queue.put(("nxd_error", (
                            f"Couldn't fetch the game's copy of {table_name}, so your changes "
                            f"to it were left out. Your original file is unchanged."
                        )))

                for table_name, rows in unmodelled_edits.items():
                    applied = nxd_data.write_unmodelled_table_edits(
                        staged_sqlite, table_name, rows)
                    if applied < len(rows):
                        # The update removed rows this mod had changed, so
                        # some edits have nowhere to land. Said out loud
                        # rather than silently dropped.
                        self._queue.put(("nxd_status", (
                            f"{table_name}: {len(rows) - applied} row(s) your mod changed no "
                            f"longer exist in this version of the game and were left out."
                        )))

                tables = nxd_data.tables_to_reexport(touched_ability_langs, override_touched)
                tables += nxd_data.tables_to_reexport_items(touched_item_langs)
                tables += nxd_data.tables_to_reexport_encounters(touched_chara_langs, entry_touched)
                tables += nxd_data.tables_to_reexport_poach(touched_poach_langs)
                tables += sorted(unmodelled_edits)
                # Emptied before the converter runs. This is a fixed path
                # reused by every export, and copy_nxd_files takes whatever
                # it finds under each expected name - so a file FF16Tools
                # failed to regenerate this time would be silently copied
                # from a previous export, and the "didn't produce" check
                # below would see it present and say nothing. Same shape as
                # the mod staging bug that shipped one mod's abilities
                # inside another; see prepare_staging_folder.
                output_nxd_dir = staging_dir / "nxd_out"
                output_nxd_dir.mkdir(parents=True, exist_ok=True)
                for stale in output_nxd_dir.glob("*.nxd"):
                    try:
                        stale.unlink()
                    except OSError:
                        pass
                self._queue.put(("nxd_status", f"Running FF16Tools.CLI sqlite-to-nxd for: {', '.join(tables)}"))
                code = ff16tools.run_sqlite_to_nxd(
                    cli_path, staged_sqlite, output_nxd_dir, tables=tables,
                    line_cb=lambda line: self._queue.put(("nxd_status", line)),
                )
                if code != 0:
                    self._queue.put(("nxd_error", f"FF16Tools.CLI sqlite-to-nxd failed (exit code {code})."))
                    return

                filenames = [c.NXD_ABILITY_FILENAMES[lang] for lang in touched_ability_langs]
                if override_touched:
                    filenames.append(c.NXD_OVERRIDE_ACTION_FILENAME)
                filenames += [c.NXD_ITEM_FILENAMES[lang] for lang in touched_item_langs]
                filenames += [c.NXD_CHARANAME_FILENAMES[lang] for lang in touched_chara_langs]
                if entry_touched:
                    filenames.append(c.NXD_OVERRIDE_ENTRY_FILENAME)
                filenames += [c.NXD_POACH_FILENAMES[lang] for lang in touched_poach_langs]
                # Which file each merged table becomes, looked up in the
                # game's own nxd folder rather than in a fixed list. The
                # list only had 37 names in it, so anything merged outside
                # it was converted and then silently not copied - which is
                # how uibuttonguide.nxd and uiannounce.nxd went missing from
                # an export that reported them merged.
                game_nxd = (Path(state.unpacked_game_dir) / "nxd"
                            if state.unpacked_game_dir else None)
                lower_to_name = {name.lower(): name for name in c.NXD_ALL_STAGED_FILENAMES}
                for table_name in sorted(unmodelled_edits):
                    found = migration.nxd_filename_for_table(game_nxd, table_name)
                    if found is None:
                        # No game folder to ask, or the game has no such
                        # file. Fall back to the old list, then to the
                        # obvious construction, so a missing game folder
                        # degrades rather than dropping the file.
                        candidate = table_name.replace("-", ".").lower() + ".nxd"
                        found = lower_to_name.get(candidate, candidate)
                    filenames.append(found)
                copied = modconfig.copy_nxd_files(output_nxd_dir, filenames, mod_root, mode)
                missing_files = [f for f in filenames if f not in copied]
                if missing_files:
                    self._queue.put((
                        "nxd_error",
                        f"FF16Tools.CLI ran but didn't produce: {', '.join(missing_files)}.",
                    ))
                    return
                dest = modconfig.nxd_output_dir(mod_root, mode)
                self._queue.put(("nxd_done", f"Wrote {len(copied)} .nxd file(s)."))
            except Exception as exc:  # noqa: BLE001 - surface any failure honestly rather than hang
                self._queue.put(("nxd_error", str(exc)))
            finally:
                self._queue.put(("nxd_finished", None))

        threading.Thread(target=worker, daemon=True).start()

    def _maybe_export_textures(self, mod_root: Path, mode: str) -> None:
        state = self.app.state_data
        if not state.texture_edits:
            self.texture_export_status_var.set("")
            return

        needs_cli = any(
            rel.lower().endswith(".tex") and not info.get("already_staged")
            for rel, info in state.texture_edits.items()
        )
        if needs_cli and state.ff16tools_cli_path is None:
            self.texture_export_status_var.set(
                "Some staged textures are .tex files, but FF16Tools.CLI.exe isn't set up "
                "(General Setup) - only the .tga replacements below will be exported until it is."
            )
            self.texture_export_status_label.configure(foreground="#b00020")

        edits_snapshot = dict(state.texture_edits)
        cli_path = state.ff16tools_cli_path

        self._begin_export_op()
        if not (needs_cli and cli_path is None):
            self.texture_export_status_var.set(f"Converting and copying {len(edits_snapshot)} texture(s)...")
            self.texture_export_status_label.configure(foreground="#666666")

        def worker() -> None:
            staged_count = 0
            skipped = []
            errors = []
            try:
                staging_dir = paths.local_data_dir() / "texture_export_staging"
                dest_root = modconfig.data_output_dir(mod_root, mode)
                for relative_path, info in edits_snapshot.items():
                    ext = Path(relative_path).suffix.lower()
                    if ext == ".tex" and cli_path is None and not info.get("already_staged"):
                        skipped.append(relative_path)
                        continue
                    self._queue.put(("texture_export_status", f"Staging {relative_path}..."))
                    try:
                        if info.get("already_staged"):
                            # Recovered from an opened mod: this file is
                            # already in the exact target format, so decoding
                            # and re-encoding it would only lose quality on
                            # every open/export cycle.
                            staged = Path(info["source_path"])
                        else:
                            staged = td.stage_texture_replacement(
                                relative_path, info["source_path"], staging_dir, cli_path
                            )
                        dest = dest_root / relative_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        import shutil
                        shutil.copy(staged, dest)
                        staged_count += 1
                    except Exception as exc:  # noqa: BLE001 - one bad texture shouldn't abort the rest
                        errors.append(f"{relative_path}: {exc}")

                summary = (f"Exported {staged_count} texture(s)." if staged_count == len(edits_snapshot)
                           else f"Exported {staged_count} of {len(edits_snapshot)} texture(s).")
                if skipped:
                    summary += f"\n{len(skipped)} .tex file(s) skipped (FF16Tools.CLI.exe not set up)."
                if errors:
                    summary += "\nErrors:\n" + "\n".join(f"  {e}" for e in errors[:10])
                    self._queue.put(("texture_export_error", summary))
                else:
                    self._queue.put(("texture_export_done", summary))
            except Exception as exc:  # noqa: BLE001 - surface any failure honestly rather than hang
                self._queue.put(("texture_export_error", str(exc)))
            finally:
                self._queue.put(("texture_export_finished", None))

        threading.Thread(target=worker, daemon=True).start()

    def _fetch_game_tables(self, staging_dir: Path, tables: list, cli_path,
                           log) -> Optional[Path]:
        """
        Converts just the game .nxd files behind a set of tables, so they can
        be merged even though the working database never held them.

        Runs on the export worker thread and returns the database it made,
        or None if anything went wrong - the caller then drops those merges
        and says so rather than writing a table it couldn't build from.

        Deliberately narrow. The alternative was converting all 564 game
        .nxd at unpack time, which would make every unpack pay for a feature
        most sessions never use; this pays only for the tables actually
        being merged, and only when merging.
        """
        state = self.app.state_data
        game_nxd = Path(state.unpacked_game_dir) / "nxd" if state.unpacked_game_dir else None
        if not game_nxd or not game_nxd.is_dir():
            return None

        wanted = {}
        for name in game_nxd.glob("*.nxd"):
            table = migration.resolve_table_name(self.app.state_data.nxd_sqlite_path, name.name)
            candidate = table or migration._candidate_table_name(name.name)
            for table_name in tables:
                if candidate and candidate.lower() == table_name.lower():
                    wanted[table_name] = name
        if not wanted:
            return None

        scratch = staging_dir / "game_tables"
        target = scratch / "nxd"
        target.mkdir(parents=True, exist_ok=True)
        for stale in target.glob("*.nxd"):
            stale.unlink(missing_ok=True)
        for path in wanted.values():
            shutil.copy(path, target / path.name)

        out = scratch / "game_tables.sqlite"
        out.unlink(missing_ok=True)
        log(f"Fetching the game's copy of: {', '.join(sorted(wanted))}")
        code = ff16tools.run_nxd_to_sqlite(cli_path, target, out, line_cb=log)
        if code != 0 or not out.exists():
            return None
        return out

    def _copy_through_replacements(self, mod_root: Path, mode: str) -> int:
        """
        Re-writes whole-file replacements recovered from an opened mod
        (sound archives, and anything this tool has no tab for) back into
        the generated mod.

        Needed because Generate writes into the same folder it read from,
        and a user can legitimately point it somewhere else - "Choose a
        Different Folder", a new Mod ID, exporting to a fresh copy. Without
        this, opening a mod and regenerating it elsewhere would silently
        drop every sound and every unrecognised file it contained.
        """
        state = self.app.state_data
        replacements = {**state.sound_file_replacements, **state.other_file_replacements}
        if not replacements:
            return 0

        import shutil
        dest_root = modconfig.data_output_dir(mod_root, mode)
        copied = 0
        for relative_path, source in replacements.items():
            source = Path(source)
            dest = dest_root / relative_path
            try:
                if not source.exists():
                    continue
                if dest.resolve() == source.resolve():
                    copied += 1  # regenerating in place; already where it needs to be
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(source, dest)
                copied += 1
            except OSError:
                continue  # one unreadable file shouldn't abort the export
        return copied

    def _maybe_export_sounds(self, mod_root: Path, mode: str) -> None:
        state = self.app.state_data
        carried = self._copy_through_replacements(mod_root, mode)
        if not state.sound_edits:
            if carried:
                self.sound_export_status_var.set(
                    f"{carried} replaced file(s) from the opened mod carried through unchanged."
                )
            else:
                self.sound_export_status_var.set("")
            return

        missing = []
        if state.audiomog_exe_path is None:
            missing.append("AudioMog.exe")
        if state.unpacked_game_dir is None:
            missing.append("an unpacked game folder")
        if missing:
            self.sound_export_status_var.set(
                "Sound replacements exist but weren't exported - missing " + " and ".join(missing)
                + " (set up in General Setup, then Generate again)."
            )
            self.sound_export_status_label.configure(foreground="#b00020")
            return

        edits_snapshot = {rel: dict(tracks) for rel, tracks in state.sound_edits.items() if tracks}
        exe_path = state.audiomog_exe_path
        game_dir = state.unpacked_game_dir

        self._begin_export_op()
        self.sound_export_status_var.set(f"Unpacking, replacing, and repacking {len(edits_snapshot)} sound file(s)...")
        self.sound_export_status_label.configure(foreground="#666666")

        def sound_worker() -> None:
            staged_count = 0
            errors = []
            try:
                staging_dir = paths.local_data_dir() / "sound_export_staging"
                dest_root = modconfig.data_output_dir(mod_root, mode)
                for relative_path, track_edits in edits_snapshot.items():
                    vanilla_path = game_dir / relative_path
                    if not vanilla_path.exists():
                        errors.append(f"{relative_path}: vanilla file not found at {vanilla_path}")
                        continue
                    self._queue.put(("sound_export_status", f"Processing {relative_path}..."))
                    try:
                        repacked = sd.stage_sound_export(
                            exe_path, vanilla_path, relative_path, track_edits, staging_dir,
                            line_cb=lambda line: self._queue.put(("sound_export_status", line)),
                        )
                        dest = dest_root / relative_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        import shutil
                        shutil.copy(repacked, dest)
                        staged_count += 1
                    except Exception as exc:  # noqa: BLE001 - one bad sound file shouldn't abort the rest
                        errors.append(f"{relative_path}: {exc}")

                summary = (f"Exported {staged_count} sound file(s)." if staged_count == len(edits_snapshot)
                           else f"Exported {staged_count} of {len(edits_snapshot)} sound file(s).")
                if errors:
                    summary += "\nErrors:\n" + "\n".join(f"  {e}" for e in errors[:10])
                    self._queue.put(("sound_export_error", summary))
                else:
                    self._queue.put(("sound_export_done", summary))
            except Exception as exc:  # noqa: BLE001 - surface any failure honestly rather than hang
                self._queue.put(("sound_export_error", str(exc)))
            finally:
                self._queue.put(("sound_export_finished", None))

        threading.Thread(target=sound_worker, daemon=True).start()

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "nxd_status":
                    self.nxd_export_status_var.set(payload)
                elif kind == "nxd_error":
                    self.nxd_export_status_var.set(payload)
                    self.nxd_export_status_label.configure(foreground="#b00020")
                elif kind == "nxd_done":
                    self.nxd_export_status_var.set(payload)
                    self.nxd_export_status_label.configure(foreground="#0a6e0a")
                elif kind == "nxd_finished":
                    self._end_export_op()
                elif kind == "texture_export_status":
                    self.texture_export_status_var.set(payload)
                elif kind == "texture_export_error":
                    self.texture_export_status_var.set(payload)
                    self.texture_export_status_label.configure(foreground="#b00020")
                elif kind == "texture_export_done":
                    self.texture_export_status_var.set(payload)
                    self.texture_export_status_label.configure(foreground="#0a6e0a")
                elif kind == "texture_export_finished":
                    self._end_export_op()
                elif kind == "sound_export_status":
                    self.sound_export_status_var.set(payload)
                elif kind == "sound_export_error":
                    self.sound_export_status_var.set(payload)
                    self.sound_export_status_label.configure(foreground="#b00020")
                elif kind == "sound_export_done":
                    self.sound_export_status_var.set(payload)
                    self.sound_export_status_label.configure(foreground="#0a6e0a")
                elif kind == "sound_export_finished":
                    self._end_export_op()
        except queue.Empty:
            pass
        self.after(150, self._poll_queue)

    def _open_last_output(self) -> None:
        mod_root = getattr(self, "_last_mod_root", None)
        if not mod_root:
            return
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(str(mod_root))  # type: ignore[attr-defined]
            elif system == "Darwin":
                subprocess.run(["open", str(mod_root)], check=False)
            else:
                subprocess.run(["xdg-open", str(mod_root)], check=False)
        except Exception:
            pass  # best-effort convenience only

    def _on_zip_clicked(self) -> None:
        mod_root = getattr(self, "_last_mod_root", None)
        if not mod_root or not mod_root.exists():
            self.generate_status_var.set("Generate the mod first before zipping it.")
            self.generate_status_label.configure(foreground="#b00020")
            return

        default_name = f"{mod_root.name}.zip"
        chosen = filedialog.asksaveasfilename(
            title="Save mod as .zip (ready to upload to Nexus Mods)",
            initialdir=str(mod_root.parent),
            initialfile=default_name,
            defaultextension=".zip",
            filetypes=[("Zip archive", "*.zip")],
        )
        if not chosen:
            return

        try:
            zip_path = Path(chosen)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in mod_root.rglob("*"):
                    if file_path.is_file():
                        # Keep the ModId folder itself as the zip's top-level
                        # entry, so extracting straight into a Mods folder
                        # (Reloaded-II's own manual-install convention) works.
                        arcname = Path(mod_root.name) / file_path.relative_to(mod_root)
                        zf.write(file_path, arcname)
        except OSError as exc:
            self.generate_status_var.set(f"Couldn't create the zip: {exc}")
            self.generate_status_label.configure(foreground="#b00020")
            return

        self.generate_status_var.set(f"Zipped to:\n{zip_path}")
        self.generate_status_label.configure(foreground="#0a6e0a")

    # -- WizardStepFrame overrides -----------------------------------------

    def on_show(self) -> None:
        # Reloaded-II may only have been located (or new mods installed)
        # after this page was first built, so re-scan its Mods folder here
        # rather than only at construction time.
        self._refresh_dependency_list()
        if self.app.state_data.loaded_mod_root != self._applied_loaded_mod_root:
            self._applied_loaded_mod_root = self.app.state_data.loaded_mod_root
            self._apply_loaded_mod_to_form()
        elif not self.mod_id_var.get():
            self._on_form_changed()
        self._refresh_preview()

