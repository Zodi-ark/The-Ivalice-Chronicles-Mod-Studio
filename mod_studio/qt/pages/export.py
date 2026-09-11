"""
Export Mod.

The other end of the workflow. A mod you cannot export is a mod you cannot
play, which makes this the second of the two steps that had to exist before
the Qt interface was usable for anything real - General Setup was the first.

What it writes is a Reloaded-II mod folder: `ModConfig.json` plus the diff
XML for every table with edits in it. All of that is pure Python, so the
export genuinely runs here and its output can be read back and checked.

What it does NOT do is repack `.nxd` files or convert textures and sounds -
those need FF16Tools and AudioMog, Windows binaries. The page says which
parts of a mod that leaves out rather than writing a partial mod and calling
it done, because a mod that silently exports without its textures is worse
than one that refuses.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea,
    QSplitter, QTabWidget,
    QTextEdit, QVBoxLayout, QWidget,
)

from ... import item_xml_io as ix
from ... import constants as c
from ... import modconfig, paths, reloaded, xml_io
from ... import sound_data as sd, texture_data as td
from ..widgets.hairline_splitter import HairlineSplitter
from ..widgets.field_rows import CollapsibleSection
from ..nxd_export import NxdExportWorker
from ..widgets.flow_layout import FlowLayout
from ..widgets.mod_contents import ModContentsPane
from ..workers import Worker, run_in_thread
from ..widgets.actions import reveal_in_file_manager, zip_folder


# Suggestions only - the field is editable, so an author whose mod is none of
# these can type their own. This list was duplicated from the Tkinter export
# page and pinned to it by a test, because importing that module would have
# pulled tkinter into the Qt interface. That page is gone; this is now the
# only copy, and there is nothing left for it to drift from.
CATEGORY_SUGGESTIONS = ["gameplay", "graphics", "audio", "characters",
                        "balance", "other"]


class AssetExportWorker(Worker):
    """
    Converts replaced textures and repacks edited sound archives into a
    built mod folder.

    Both were listed on the page as "not included by this interface yet"
    while the engine had done them all along -
    `texture_data.stage_texture_replacement` and
    `sound_data.stage_sound_export` are complete, and the Tkinter export has
    called them since each feature shipped. The Qt page wrote ModConfig.json
    and the diff XML and stopped, so a texture pack exported from it was an
    empty mod that reported success.

    On a worker thread because the sound path shells out to AudioMog per
    archive, which takes seconds each.

    **One bad file must not abort the rest.** A single texture that fails to
    convert should cost that texture, not the other forty - so every item is
    tried, failures are collected, and the result says how many of how many
    landed. Reporting "exported 39 of 40" plus the reason is honest;
    stopping at the first error and leaving a half-written mod is not.

    **Not verified.** FF16Tools and AudioMog are Windows binaries. The
    staging calls, the destination paths and the error handling are
    exercised here against `.tga` (which is pure Pillow and needs neither
    tool); `.tex` and `.sab` have never run.
    """

    def __init__(self, mod_root, mode, texture_edits, sound_edits,
                 cli_path, audiomog_path, game_dir):
        super().__init__()
        self.mod_root = Path(mod_root)
        self.mode = mode
        self.texture_edits = dict(texture_edits or {})
        # A nested copy: the per-track dicts are the page's own state and
        # must not be handed to a background thread by reference.
        self.sound_edits = {rel: dict(tracks)
                            for rel, tracks in (sound_edits or {}).items()
                            if tracks}
        self.cli_path = Path(cli_path) if cli_path else None
        self.audiomog_path = Path(audiomog_path) if audiomog_path else None
        self.game_dir = Path(game_dir) if game_dir else None

    def run(self):
        import shutil

        dest_root = modconfig.data_output_dir(self.mod_root, self.mode)
        result = {"textures": 0, "texture_total": len(self.texture_edits),
                  "sounds": 0, "sound_total": len(self.sound_edits),
                  "skipped": [], "errors": []}

        if self.texture_edits:
            staging = paths.local_data_dir() / "texture_export_staging"
            for relative_path, info in sorted(self.texture_edits.items()):
                already = bool(info.get("already_staged"))
                if (Path(relative_path).suffix.lower() == ".tex"
                        and self.cli_path is None and not already):
                    result["skipped"].append(relative_path)
                    continue
                self.log.emit(f"Staging {relative_path}...")
                try:
                    if already:
                        # Recovered from an opened mod: already in the exact
                        # target format, so decoding and re-encoding it would
                        # lose quality on every open/export cycle.
                        staged = Path(info["source_path"])
                    else:
                        staged = td.stage_texture_replacement(
                            relative_path, info["source_path"], staging,
                            self.cli_path)
                    destination = dest_root / relative_path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(staged, destination)
                    result["textures"] += 1
                except Exception as exc:                      # noqa: BLE001
                    result["errors"].append(f"{relative_path}: {exc}")

        if self.sound_edits:
            if self.audiomog_path is None:
                result["errors"].append(
                    "AudioMog isn't set up, so no sound archive could be "
                    "repacked. Set it under General Setup, Advanced options.")
            elif self.game_dir is None:
                result["errors"].append(
                    "The unpacked game folder isn't set, and repacking a "
                    "sound archive needs the vanilla file to start from.")
            else:
                staging = paths.local_data_dir() / "sound_export_staging"
                for relative_path, tracks in sorted(self.sound_edits.items()):
                    vanilla = self.game_dir / relative_path
                    if not vanilla.exists():
                        result["errors"].append(
                            f"{relative_path}: the vanilla file isn't at "
                            f"{vanilla}")
                        continue
                    self.log.emit(f"Repacking {relative_path}...")
                    try:
                        repacked = sd.stage_sound_export(
                            self.audiomog_path, vanilla, relative_path,
                            tracks, staging, line_cb=self.log.emit)
                        destination = dest_root / relative_path
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy(repacked, destination)
                        result["sounds"] += 1
                    except Exception as exc:                  # noqa: BLE001
                        result["errors"].append(f"{relative_path}: {exc}")

        return result


class ExportPage(QWidget):
    exported = Signal(Path)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.last_built = None
        self._thread = None
        # Which opened mod's details are currently in the fields, so a
        # refresh does not keep overwriting a Mod ID the user has changed
        # on purpose to fork the mod.
        self._adopted_mod_id = None
        self._loading_opened = False
        self._carried_tags = None
        self._carried_icon = None
        # Carried between the export stages, which are now three deep:
        # tables, then assets, then .nxd.
        self._last_mode = None
        self._asset_detail = None
        self._said_trouble = False

        # The whole page scrolls.
        #
        # It did not, because it used to be short enough not to need it.
        # Adding a collapsible Publishing panel changed that: with no scroll
        # area there is nowhere for the expanded panel to go, so Qt squeezes
        # it into whatever is left - a screenshot showed all four groups
        # crushed into about 110px, drawn on top of each other.
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        page_layout.addWidget(self.scroll)

        inner = QWidget()
        self.scroll.setWidget(inner)
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(10)

        heading = QLabel("Export Mod")
        heading.setProperty("role", "heading")
        outer.addWidget(heading)

        blurb = QLabel(
            "Turn your edits into a Reloaded-II mod. Only the fields you ticked "
            "are written, so your mod stays compatible with others.")
        blurb.setProperty("role", "intro")
        blurb.setWordWrap(True)
        outer.addWidget(blurb)

        # A real vertical split: everything you fill in on the left, what
        # you are about to ship on the right.
        #
        # This was an HBox holding Mod Details and Mod Contents, with
        # Publishing, Where it goes, the status line and the log stacked
        # underneath it at full width. So the halves only lined up for the
        # first section and then stopped: Mod Contents ended level with the
        # bottom of Mod Details while the three things that decide what goes
        # into the mod ran along beneath both columns. Reading it meant
        # crossing the page and coming back.
        #
        # A `QSplitter` rather than two fixed columns, because the two sides
        # want different widths depending on what is being done - a mod with
        # forty changed files needs room to list them, and one being filled
        # in for the first time does not.
        split = HairlineSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)

        # The banner sits above the details it is talking about, which is
        # where Tkinter puts it - a warning under the fields it applies to
        # is read after they have already been filled in.
        #
        # Split into two parts, which is what makes the two halves of the
        # page share a bottom edge:
        #
        #   the FORM scrolls inside the left pane
        #   the status line and the log are pinned under it
        #
        # Before this, everything was one column inside the page's own
        # scroll area, so expanding "Publishing and Reloaded-II options"
        # made the left column taller, made the splitter taller, and pushed
        # the whole page's floor down - Mod Contents grew with it and the
        # log ended up somewhere below the fold. The floor moved because
        # the collapsible section was driving the height.
        #
        # Now the pane's height is authoritative and the form takes what is
        # left, so expanding a section scrolls the form instead of resizing
        # the page. Status and log stay on the floor because they are the
        # two things a person looks at WHILE exporting, and a log that
        # scrolls out of view during the job it is reporting is the one
        # arrangement worse than no log.
        form_column = QVBoxLayout()
        form_column.setContentsMargins(0, 0, 0, 0)
        form_column.addWidget(self._build_opened_mod_banner())
        form_column.addWidget(self._details_box())
        form_column.addWidget(self._build_publishing_section())
        form_column.addWidget(self._destination_box())
        form_column.addStretch(1)
        form_holder = QWidget()
        form_holder.setLayout(form_column)

        # No visible scrollbar, and still scrollable.
        #
        # `ScrollBarAlwaysOff` hides the bar without removing the scroll
        # RANGE, so the wheel and the keyboard still move it - which is the
        # requirement. A bar here would be a second vertical scrollbar a few
        # hundred pixels from the page's own, and two scrollbars side by
        # side is how a reader stops trusting either.
        self.left_scroll = QScrollArea()
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setFrameShape(QScrollArea.NoFrame)
        self.left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.left_scroll.setWidget(form_holder)

        left_column = QVBoxLayout()
        left_column.setContentsMargins(0, 0, 0, 0)
        left_column.addWidget(self.left_scroll, 1)

        self.status = QLabel("")
        self.status.setProperty("role", "muted")
        self.status.setWordWrap(True)
        left_column.addWidget(self.status)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        left_column.addWidget(self.log)

        left_holder = QWidget()
        left_holder.setLayout(left_column)
        split.addWidget(left_holder)

        # Mod Contents replaces the lone Summary box. The summary is still
        # there - it is the pane's first tab - so nothing that read
        # `self.summary` had to change.
        right_column = QVBoxLayout()
        right_column.setContentsMargins(0, 0, 0, 0)
        self.contents = ModContentsPane(self)
        self.summary = self.contents.summary
        right_column.addWidget(self.contents, 1)
        # Kept beneath the contents rather than inside the Summary tab: it
        # warns about things that will not be written, and a warning on a
        # tab the reader may not be looking at is a warning they will miss.
        self.missing_note = QLabel("")
        self.missing_note.setProperty("role", "attention")
        self.missing_note.setWordWrap(True)
        # Hidden while it has nothing to say.
        #
        # An empty QLabel is not a zero-height widget: it keeps a line of
        # height and the layout's spacing above it. Reported from a
        # screenshot - Mod Contents stopped 26px short of the floor the log
        # and the splitter shared, and the culprit was this label holding
        # a line open for a warning that was not there. `_say_missing`
        # shows it again the moment there is one.
        self.missing_note.setVisible(False)
        right_column.addWidget(self.missing_note)
        right_holder = QWidget()
        right_holder.setLayout(right_column)
        split.addWidget(right_holder)

        # Even by default. Stretch factors alone were not enough: a
        # `QSplitter` sizes its panes from their size hints first and only
        # distributes what is left over by stretch, and the left pane's hint
        # is the width of the widest field row - so it opened at roughly
        # two-thirds and Mod Contents got the remainder. Two equal sizes are
        # normalised against the real width, which gives a genuine half
        # each, and the divider still drags.
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        split.setSizes([10_000, 10_000])
        outer.addWidget(split, 1)

        self.refresh_summary()

    # -- sections ----------------------------------------------------------------

    def _details_box(self) -> QGroupBox:
        box = QGroupBox("Mod details")
        form = QFormLayout(box)

        self.name_field = QLineEdit("My FFT Mod")
        self.name_field.textChanged.connect(self._suggest_id)
        form.addRow("Name:", self.name_field)

        self.author_field = QLineEdit("")
        form.addRow("Author:", self.author_field)

        self.version_field = QLineEdit("1.0.0")
        form.addRow("Version:", self.version_field)

        # Category, which this page did not have at all.
        #
        # It feeds two things: the mod's `Tags`, and the middle segment of
        # the suggested Mod ID (`fftivc.<category>.<name>`). Without it
        # every mod built here was tagged `gameplay` whatever it actually
        # was, and an opened asset mod lost its tag on re-export.
        #
        # Editable, because Reloaded-II does not restrict the vocabulary -
        # the list is a set of suggestions, and a real mod in the wild uses
        # "Character", which is not in it.
        self.category_box = QComboBox()
        self.category_box.setEditable(True)
        self.category_box.addItems(CATEGORY_SUGGESTIONS)
        self.category_box.currentTextChanged.connect(
            lambda _text: self._suggest_id(self.name_field.text()))
        form.addRow("Category:", self.category_box)

        self.id_field = QLineEdit()
        self.id_field.textChanged.connect(self._check_id)
        form.addRow("Mod ID:", self.id_field)

        self.id_hint = QLabel("")
        self.id_hint.setProperty("role", "muted")
        self.id_hint.setWordWrap(True)
        form.addRow("", self.id_hint)

        icon_row = QHBoxLayout()
        self.icon_field = QLineEdit()
        self.icon_field.setPlaceholderText("Optional")
        icon_row.addWidget(self.icon_field, 1)
        icon_browse = QPushButton("Choose image...")
        icon_browse.setMinimumWidth(icon_browse.sizeHint().width() + 8)
        icon_browse.clicked.connect(self.choose_icon)
        icon_row.addWidget(icon_browse)
        icon_holder = QWidget()
        icon_holder.setLayout(icon_row)
        form.addRow("Icon:", icon_holder)

        self.description_field = QTextEdit()
        self.description_field.setMaximumHeight(70)
        form.addRow("Description:", self.description_field)

        self._suggest_id(self.name_field.text())
        return box

    def _build_opened_mod_banner(self) -> QWidget:
        """
        The "you are editing an existing mod" strip, with a way out of it.

        Without this, opening a mod and pressing Generate writes it under
        "My FFT Mod" at a freshly suggested id - so the author gets a second
        copy of their own mod beside the first instead of an updated one,
        and only finds out by looking in the Mods folder. Tkinter has said
        so on this page for a long time.
        """
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 6)
        column.setSpacing(4)
        self.opened_mod_label = QLabel("")
        self.opened_mod_label.setProperty("role", "ok")
        self.opened_mod_label.setWordWrap(True)
        column.addWidget(self.opened_mod_label)
        # No "Start New Mod Instead" button here.
        #
        # Tkinter has one because its banner is the only place that says so.
        # This page already carries a Start New Mod button further down, so
        # a second one three inches above it is two controls doing one job -
        # and the reader has to work out whether they differ. The banner
        # warns; the existing button acts.
        holder.setVisible(False)
        self.opened_mod_banner = holder
        return holder

    def adopt_opened_mod(self) -> bool:
        """
        Fills the details in from the mod that was opened, if there was one.

        Returns whether anything was adopted. `ReviewPage` has stored
        `loaded_mod_config` since mods could be opened at all; this page
        simply never read it.

        **Only fields the user has not already typed into.** Re-adopting on
        every refresh would otherwise fight somebody who has deliberately
        changed the Mod ID to fork the mod - which is exactly what the
        banner tells them to do.
        """
        config = getattr(self.state, "loaded_mod_config", None)
        if not config:
            return False
        if self._adopted_mod_id == config.get("ModId"):
            return True

        self._adopted_mod_id = config.get("ModId") or ""
        self._loading_opened = True
        try:
            for key, widget in (("ModName", self.name_field),
                                ("ModAuthor", self.author_field),
                                ("ModVersion", self.version_field),
                                ("ModId", self.id_field),
                                # Under "Publishing and Reloaded-II
                                # options", and it was the one publishable
                                # field this loop did not name - so an
                                # author who opened their own mod and
                                # re-exported it shipped a ModConfig with
                                # the project link REMOVED. Same shape as
                                # the auto-update block below, which was
                                # fixed for the same reason; this one was
                                # missed because nothing enumerates the
                                # fields. `test_qt_export.py` now round-
                                # trips every publishable field rather
                                # than trusting this list to be complete.
                                ("ProjectUrl", self.project_url_field)):
                value = (config.get(key) or "").strip()
                if value:
                    widget.setText(value)
            description = (config.get("ModDescription") or "").strip()
            if description:
                self.description_field.setPlainText(description)
            # Category has no widget on this page yet - Tkinter has a
            # dropdown and `_suggest_id` here passes a hard-coded
            # "gameplay". The opened mod's tags are carried through
            # untouched rather than dropped, so re-exporting does not
            # silently retag somebody's asset mod as gameplay.
            tags = config.get("Tags") or []
            if tags:
                self._carried_tags = list(tags)
                # Shown in the box as well, so the category is visible and
                # editable rather than merely carried invisibly.
                self.category_box.setCurrentText(str(tags[0]))

            # The GitHub auto-update block, from the mod's own PluginData.
            #
            # Under "Publishing and Reloaded-II options", and it was not
            # carried across - so an author who opened their published mod
            # and re-exported it shipped a ModConfig with the auto-update
            # block **removed**, because `_apply_update_settings` clears its
            # key when the fields are blank. Everybody already running the
            # mod silently stopped receiving updates.
            update = (config.get("PluginData")
                      or {}).get(modconfig.GITHUB_UPDATE_PLUGIN_KEY) or {}
            if update:
                self.github_user_field.setText(
                    str(update.get("UserName") or ""))
                self.github_repo_field.setText(
                    str(update.get("RepositoryName") or ""))
                self.github_tag_check.setChecked(
                    bool(update.get("UseReleaseTag", True)))
                asset = str(update.get("AssetFileName") or "").strip()
                if asset:
                    self.github_asset_field.setText(asset)

            # And the icon.
            #
            # `icon_source` is a path to an image to COPY IN, which is not
            # what an opened mod has - its icon is already inside the mod
            # folder. So the filename is carried instead and
            # `write_mod_config`'s "keep the existing icon" path handles it;
            # pointing icon_source at the mod's own preview.png would make
            # export copy the file over itself.
            icon_name = str(config.get("ModIcon") or "").strip()
            self._carried_icon = icon_name or None
            root = getattr(self.state, "loaded_mod_root", None)
            if icon_name and root:
                existing = Path(root) / icon_name
                if existing.is_file():
                    self.icon_field.setText(str(existing))
            app_ids = config.get("SupportedAppId") or []
            if app_ids:
                self._apply_app_ids(app_ids)
        finally:
            self._loading_opened = False

        name = config.get("ModName") or self._adopted_mod_id
        folder = Path(self.output_field.text().strip() or ".") / \
            (self._adopted_mod_id or "")
        self.opened_mod_label.setText(
            f"Editing existing mod: {name}. Change the Mod ID below to save "
            f"it as a separate mod instead of overwriting.\n"
            f"Will overwrite the mod already at: {folder}")
        self.opened_mod_banner.setVisible(True)
        return True

    def _chosen_tags(self) -> list:
        """
        The mod's tags: the category, plus anything else an opened mod had.

        An opened mod may carry tags this page has no control for, and
        dropping them on re-export would quietly rewrite somebody's
        metadata. The category leads because that is the one being edited.
        """
        category = self.category_box.currentText().strip()
        tags = [category] if category else []
        for tag in (self._carried_tags or []):
            if tag and tag not in tags:
                tags.append(tag)
        return tags

    def _icon_source(self, destination: str, mod_id: str):
        """
        The image to copy in, or None to keep the icon already in the mod.

        An opened mod's icon lives INSIDE the mod folder, so carrying it
        across as an `icon_source` would ask export to copy the file over
        itself - `shutil.copy2` raises `SameFileError` on that, which would
        turn "re-export my published mod" into a failed export.

        Passing None with the filename kept is `write_mod_config`'s
        "keep the existing icon" path: `ModIcon` stays pointing at the same
        name and the file is left where it already is. Picking a genuinely
        new image still copies normally, including over an old one.
        """
        text = self.icon_field.text().strip()
        if not text:
            return None
        chosen = Path(text)
        try:
            target = Path(destination) / mod_id / chosen.name
            if chosen.resolve() == target.resolve():
                return None
        except OSError:
            # An unresolvable path is not worth failing an export over;
            # let the copy attempt report it properly.
            pass
        return chosen

    def _apply_app_ids(self, app_ids) -> None:
        """Ticks the executables a loaded mod declares, if the panel has them."""
        boxes = getattr(self, "app_id_boxes", None)
        if not boxes:
            return
        wanted = {str(a) for a in app_ids}
        for app_id, box in boxes.items():
            box.setChecked(str(app_id) in wanted)

    def _destination_box(self) -> QGroupBox:
        return self._build_output_section()

    def _build_publishing_section(self):
        """
        The Reloaded-II side of a mod: what it shows under, what it needs,
        and how it updates itself.

        None of this existed on the Qt page - `game_mode` was hard-coded to
        "enhanced" and `supported_app_ids`, `dependencies`, `project_url`
        and all four GitHub fields were passed empty. So every mod built
        here claimed to support only the enhanced executable, declared no
        dependencies, and could never offer an update. Those are not
        cosmetic: a mod with the wrong app id does not appear under the
        game the author meant, and a missing dependency means Reloaded-II
        cannot warn somebody who is missing the mod this one needs.

        Collapsed by default. Everything here has a working default, and a
        first-time modder should not have to scroll past four panels of
        publishing metadata to reach the button.
        """
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 4, 0, 0)
        column.setSpacing(6)

        # -- which executables ------------------------------------------------
        column.addWidget(self._bold("Show this mod under"))
        app_note = QLabel(
            "Which game executables the mod appears under in Reloaded-II. "
            "Follows the game mode unless you change it.")
        app_note.setProperty("role", "muted")
        app_note.setWordWrap(True)
        column.addWidget(app_note)

        self.app_id_boxes = {}
        for app_id in ("fft_enhanced.exe", "fft_classic.exe"):
            check = QCheckBox(app_id)
            check.setChecked(app_id == "fft_enhanced.exe")
            self.app_id_boxes[app_id] = check
            column.addWidget(check)

        # -- dependencies -------------------------------------------------------
        column.addSpacing(6)
        column.addWidget(self._bold("Requires these mods"))
        dep_note = QLabel(
            f"{c.MODLOADER_REPO} is always required and is added for you. "
            "Anything else you tick is listed so Reloaded-II can warn people "
            "who don't have it.")
        dep_note.setProperty("role", "muted")
        dep_note.setWordWrap(True)
        column.addWidget(dep_note)

        self.dependency_boxes = {}
        self.dependency_holder = QWidget()
        self.dependency_column = QVBoxLayout(self.dependency_holder)
        self.dependency_column.setContentsMargins(8, 2, 0, 2)
        self.dependency_column.setSpacing(1)
        column.addWidget(self.dependency_holder)
        self.refresh_dependencies()

        # -- GitHub auto-update -------------------------------------------------
        column.addSpacing(6)
        column.addWidget(self._bold("Auto-update from GitHub"))
        github_note = QLabel(
            "If you publish releases on GitHub, fill these in and Reloaded-II "
            "will offer updates to anyone who installs the mod. Leave blank "
            "to skip.")
        github_note.setProperty("role", "muted")
        github_note.setWordWrap(True)
        column.addWidget(github_note)

        self.github_user_field = QLineEdit()
        column.addLayout(self._labelled("GitHub user:", self.github_user_field))
        self.github_repo_field = QLineEdit()
        column.addLayout(self._labelled("Repository:", self.github_repo_field))

        self.github_tag_check = QCheckBox("Version comes from the release tag")
        self.github_tag_check.setChecked(True)
        column.addWidget(self.github_tag_check)

        self.github_asset_field = QLineEdit("Mod.zip")
        column.addLayout(self._labelled("Asset name:", self.github_asset_field))
        self.project_url_field = QLineEdit()
        column.addLayout(self._labelled("Project URL:", self.project_url_field))

        return CollapsibleSection("Publishing and Reloaded-II options", body,
                                  expanded=False)

    @staticmethod
    def _bold(text: str) -> QLabel:
        label = QLabel(text)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        return label

    @staticmethod
    def _labelled(text: str, widget) -> QHBoxLayout:
        row = QHBoxLayout()
        label = QLabel(text)
        label.setFixedWidth(110)
        row.addWidget(label)
        row.addWidget(widget, 1)
        return row

    def refresh_dependencies(self) -> None:
        """
        Lists the mods installed in Reloaded-II, so a dependency is picked
        rather than typed.

        A mod id has to be exact, and typing one from memory is how a
        dependency silently never matches. Ticks already made are kept when
        the list is rebuilt.
        """
        if not hasattr(self, "dependency_boxes"):
            return
        previous = {mod_id: box.isChecked()
                    for mod_id, box in self.dependency_boxes.items()}
        while self.dependency_column.count():
            item = self.dependency_column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.dependency_boxes = {}

        try:
            installed = reloaded.installed_mod_ids(
                getattr(self.state, "reloaded_ii_path", None))
        except Exception:                                     # noqa: BLE001
            installed = []
        # The mod loader is added by the engine, so offering it here would
        # let somebody untick a dependency that is not optional.
        installed = [m for m in installed if m != c.MODLOADER_REPO]
        if not installed:
            note = QLabel("No other mods installed, or Reloaded-II wasn't found.")
            note.setProperty("role", "muted")
            self.dependency_column.addWidget(note)
            return
        for mod_id in installed:
            check = QCheckBox(mod_id)
            check.setChecked(previous.get(mod_id, False))
            self.dependency_boxes[mod_id] = check
            self.dependency_column.addWidget(check)

    @staticmethod
    def _game_mode_for(app_ids: list) -> str:
        """
        The game mode the ticked executables imply.

        `constants.SUPPORTED_APP_IDS` maps the mode to the executables;
        this is that map read backwards, because the panel asks the
        question the way an author thinks about it - which game does my mod
        show under - rather than as a mode they then have to translate.

        Nothing ticked falls back to enhanced rather than writing a mod that
        appears under no executable at all.
        """
        chosen = set(app_ids)
        for mode, ids in c.SUPPORTED_APP_IDS.items():
            if set(ids) == chosen:
                return mode
        return "enhanced"

    def chosen_app_ids(self) -> list:
        return [app_id for app_id, box in self.app_id_boxes.items()
                if box.isChecked()]

    def chosen_dependencies(self) -> list:
        return [mod_id for mod_id, box in self.dependency_boxes.items()
                if box.isChecked()]

    def _build_output_section(self):
        box = QGroupBox("Where it goes")
        column = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("Folder:"))
        self.output_field = QLineEdit()
        row.addWidget(self.output_field, 1)
        browse = QPushButton("Browse...")
        browse.setMinimumWidth(browse.sizeHint().width() + 8)
        browse.clicked.connect(self.browse_output)
        row.addWidget(browse)
        column.addLayout(row)

        self.output_hint = QLabel("")
        self.output_hint.setProperty("role", "muted")
        self.output_hint.setWordWrap(True)
        column.addWidget(self.output_hint)

        # A wrapping row, not a fixed one.
        #
        # As a `QHBoxLayout` these four buttons could not wrap, so the box's
        # minimum width was the sum of all four - 715px. That box is in the
        # left half of the page's splitter, so at the documented 1100px
        # minimum the split came out 715/259 and Mod Contents clipped its
        # own text. At 1500 nothing changes: all four still sit on one line.
        actions = FlowLayout(spacing=6)
        # "Generate / Overwrite Mod", as the Tkinter page has it. Exporting
        # into a folder that already holds a mod of the same ID replaces it,
        # and "Build my mod" gives no hint of that - which is how somebody
        # loses work by not changing the Mod ID first.
        self.export_button = QPushButton("Generate / Overwrite Mod")
        self.export_button.setMinimumWidth(
            self.export_button.sizeHint().width() + 8)
        self.export_button.clicked.connect(self.export)
        actions.addWidget(self.export_button)

        # Both disabled until there is a mod to act on. A button that does
        # nothing when pressed teaches people not to press buttons.
        self.open_folder_button = QPushButton("Open mod folder")
        self.open_folder_button.setMinimumWidth(
            self.open_folder_button.sizeHint().width() + 8)
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.clicked.connect(self.open_mod_folder)
        actions.addWidget(self.open_folder_button)

        self.zip_button = QPushButton("Zip it for uploading...")
        self.zip_button.setMinimumWidth(self.zip_button.sizeHint().width() + 8)
        self.zip_button.setEnabled(False)
        self.zip_button.clicked.connect(self.zip_mod)
        actions.addWidget(self.zip_button)

        self.new_mod_button = QPushButton("Start a new mod")
        self.new_mod_button.setMinimumWidth(
            self.new_mod_button.sizeHint().width() + 8)
        self.new_mod_button.clicked.connect(self.start_new_mod)
        actions.addWidget(self.new_mod_button)
        # No trailing stretch: a FlowLayout already packs to the left, and
        # a spacer item in one would be measured as another thing to wrap.
        column.addLayout(actions)

        self._default_destination()
        return box

    def _default_destination(self) -> None:
        """
        Defaults to the Reloaded-II mods folder when one can be found, so
        the common case is one button rather than a folder hunt.
        """
        try:
            root = reloaded.find_installed_reloaded()
            if root is not None:
                mods = reloaded.effective_mods_folder(root)
                self.output_field.setText(str(mods))
                self.output_hint.setText(
                    "This is your Reloaded-II mods folder, so the mod will be "
                    "ready to enable as soon as it's built.")
                return
        except Exception:                                     # noqa: BLE001
            pass
        self.output_hint.setText(
            "Reloaded-II wasn't found, so pick where you'd like the mod folder "
            "written.")

    # -- mod id -------------------------------------------------------------------

    def _suggest_id(self, name: str) -> None:
        """
        Rebuilds the suggested Mod ID from the name and category.

        Not while an opened mod's details are being filled in: that would
        overwrite the mod's real id with a guess derived from its name, and
        re-exporting would then write a second copy of somebody's mod beside
        the first.
        """
        if self._loading_opened:
            return
        try:
            category = (self.category_box.currentText().strip()
                        if hasattr(self, "category_box") else "") or "gameplay"
            self.id_field.setText(modconfig.suggest_mod_id(category, name))
        except Exception:                                     # noqa: BLE001
            pass

    def _check_id(self, value: str) -> None:
        try:
            complaint = modconfig.validate_mod_id(value)
        except Exception:                                     # noqa: BLE001
            complaint = None
        self.id_hint.setText(complaint or "")
        self.id_hint.setProperty("role", "danger" if complaint else "muted")
        self.id_hint.style().unpolish(self.id_hint)
        self.id_hint.style().polish(self.id_hint)

    # -- summary --------------------------------------------------------------------

    def _sections(self) -> list:
        """
        Every section of the tool and how much of it is in this mod.

        The same list the Tkinter page reports, drawn from the same engine
        counters, so the two cannot disagree about what a mod contains.

        The last two matter more than they look. A migration whose whole
        result is "merge these tables and carry those files through" edits
        nothing on any tab, and without them the page said "nothing edited
        yet" immediately after somebody had reviewed and accepted a set of
        changes - both wrong and alarming.
        """
        state = self.state
        return [
            ("Jobs", len(self._edited_jobs())
             + state.edited_job_text_total_count(), "job"),
            ("Job Commands", len(self._edited_commands()), "job command"),
            ("Abilities",
             state.edited_ability_total_count() + state.edited_override_count()
             + state.edited_ability_effect_count()
             + state.edited_ability_animation_count()
             + state.edited_ability_data_count(), "edit"),
            ("Items", state.edited_item_text_total_count()
             + state.edited_item_table_total_count(), "edit"),
            ("Equip Bonus", state.edited_item_table_count("item_equip_bonus"),
             "edit"),
            ("Poaching", state.edited_poach_total_count(), "edit"),
            ("Treasure Hunter", state.edited_maptrap_count(), "map edit"),
            ("Encounters", state.changed_entry_row_count()
             + state.edited_chara_name_total_count(), "edit"),
            ("Textures", state.edited_texture_count(), "replacement"),
            ("Sounds", state.edited_sound_track_count(), "replacement"),
            ("Game data (no tab)", state.rebased_table_count(), "merged table"),
            ("Carried through", state.carried_through_file_count(), "file"),
        ]

    def _summary_text(self) -> str:
        """
        What this mod will contain, and - just as usefully - what it will
        not.

        The Qt page listed only the sections with something in them, so a
        texture pack read as a bare "5 textures" with no way to tell whether
        the tool had noticed everything else was deliberately empty. Naming
        the untouched sections turns "did it miss my edits?" into an answer
        on the page.
        """
        rows = self._sections()
        touched = [(label, count, noun) for label, count, noun in rows if count]

        lines = []
        # "Will contain" has to mean will contain.
        #
        # A section whose whole count is .nxd-backed - an item edited only
        # by name, say - is reported under its own heading like any other,
        # and then the mod is written without it. So the heading changes
        # when that is the only thing there is, rather than the page
        # promising something the export cannot deliver.
        # A mod made only of name and description edits is a real mod now,
        # so it no longer gets a special heading - only the case where the
        # tools to write it are missing does.
        nxd_only = (self._nxd_backed_edit_count()
                    and (getattr(self.state, "nxd_sqlite_path", None) is None
                         or getattr(self.state, "ff16tools_cli_path", None)
                         is None)
                    and not (self._edited_jobs() or self._edited_commands()
                             or self._extra_table_files()
                             or self.state.texture_edits
                             or self.state.sound_edits
                             or self.state.other_file_replacements))
        if not touched:
            lines.append("Nothing has been edited yet, so this mod would "
                         "contain only its")
            lines.append("ModConfig.json. Go to Edit Game Data to make "
                         "changes.")
            lines.append("")
        else:
            if nxd_only:
                lines.append("Everything edited so far lives in .nxd files, "
                             "and the tools to")
                lines.append("write those aren't set up - so this mod would "
                             "contain only its")
                lines.append("ModConfig.json. What you have edited:")
            else:
                lines.append("This mod will contain:")
            lines.append("")
            # The section list is printed either way. It is the answer to
            # "did the tool notice my work", and withholding it in the one
            # case where the export cannot carry that work would be the
            # least helpful moment to withhold it.
            for label, count, noun in touched:
                plural = "" if count == 1 else "s"
                lines.append(f"  {label:<18} {count} {noun}{plural}")
            lines.append("")
            files = self._files_to_write()
            lines.append(f"Files it will write ({len(files)}):")
            lines.append("")
            for name in files:
                lines.append(f"  {name}")
            lines.append("")

        untouched = [label for label, count, _noun in rows if not count]
        if untouched:
            lines.append("Nothing edited in: " + ", ".join(untouched) + ".")
        return "\n".join(lines)

    def _files_to_write(self) -> list:
        """Every file the generated mod folder will contain."""
        names = ["ModConfig.json"]
        if self._edited_jobs():
            names.append("JobData.xml")
        if self._edited_commands():
            names.append("JobCommandData.xml")
        names.extend(sorted(self._extra_table_files()))
        if self.state.texture_edits:
            names.append("Replaced textures")
        if self.state.sound_edits:
            names.append("Repacked sound archives")
        if self.state.other_file_replacements:
            names.append("Carried-through files")
        return names

    def _nxd_backed_edit_count(self) -> int:
        """
        Edits that live in `.nxd` and therefore need FF16Tools to be written.

        Every per-language text layer plus the two shared binary tables:
        ability and item names and descriptions, unit names, poaching, the
        ability override layer, and encounter rows. **This interface cannot
        write any of them yet** - repacking `.nxd` needs FF16Tools, a
        Windows binary.

        Counted so the page can say so. Before this, `_sections()` reported
        an item name change under "Items" while `_files_to_write()` listed
        only `ModConfig.json` and `export()` refused outright with "there's
        nothing to export yet" - three statements on one page, no two of
        them agreeing. It was unreachable until the Items tab grew its text
        editor, which is why it survived.
        """
        state = self.state
        # Every registered per-language nxd table, plus the two shared ones.
        # This decides whether "Export" is allowed to run at all, so a table
        # left out of the sum makes the button refuse work that exists.
        from ... import nxd_data as _nxd
        per_language = sum(state.edited_nxd_total_count(key)
                           for key in _nxd.ALL_NXD_SPECS)
        # Plus everything made on the All Game Data tab.
        #
        # Without these, a mod whose ONLY edits were made there had this
        # total come out zero, so Export refused to run - while the export
        # worker's own `has_work()` counted them and would have written
        # them happily. Two answers to "is there anything to export", and
        # the one that ran first said no.
        browser = sum(
            1 for rows in (state.unmodelled_table_edits or {}).values()
            for fields in rows.values() if fields)
        browser += sum(
            1 for rows in (state.derived_table_edits or {}).values()
            for fields in rows.values() if fields)
        return (per_language + browser
                + state.edited_override_count()
                + state.changed_entry_row_count())

    def showEvent(self, event):                             # noqa: N802
        """
        Rebuilds the previews whenever the tab is opened.

        Everything on this page is a view of shared state that other tabs
        change, and it was refreshed only when one of them said so. Any
        edit that reached `item_table_edits` without a matching
        `edits_changed` therefore sat invisible until something else
        happened to trigger a refresh - which is why toggling "Show every
        section" appeared to fix it. That toggle calls `refresh_visibility`,
        which reads the predicates live, so hidden sections reappeared even
        though nothing had rebuilt them.

        Refreshing on show makes arriving at the tab the trigger, which is
        the moment the reader is actually looking. It does not remove the
        need for the signals - they keep the page current while it is
        already open - it removes the page's dependence on them being
        complete.
        """
        super().showEvent(event)
        self.refresh_summary()

    def refresh_summary(self) -> None:
        """
        Counts what will be written, from the shared state.

        Anything the interface cannot yet export is listed separately rather
        than folded into the total, so the number is what you will actually
        get and not what you have edited.
        """
        state = self.state
        # An opened mod's details land here rather than in a one-shot call,
        # because a mod is opened from a different page and this one may not
        # exist yet when that happens. `adopt_opened_mod` is idempotent.
        self.adopt_opened_mod()
        # Fills the summary tab and every file preview in one pass.
        self.contents.refresh(self._summary_text())

        # Two different kinds of "this won't be in your mod", kept apart.
        #
        # A missing tool is something the reader can go and fix, so it gets
        # the pointer to where. A part of the interface that does not exist
        # yet is not, and telling somebody to "set it up in General Setup"
        # would send them looking for a setting that cannot help.
        tool_warnings = []
        needs_tex = any(Path(rel).suffix.lower() == ".tex"
                        and not info.get("already_staged")
                        for rel, info in (state.texture_edits or {}).items())
        if needs_tex and getattr(state, "ff16tools_cli_path", None) is None:
            tool_warnings.append(
                "FF16Tools isn't set up, so .tex textures will be skipped")
        if state.sound_edits and getattr(state, "audiomog_exe_path", None) is None:
            tool_warnings.append(
                "AudioMog isn't set up, so sound archives can't be repacked")

        parts = []
        if tool_warnings:
            parts.append(". ".join(tool_warnings)
                         + ". Set them under General Setup, Advanced options.")
        nxd_edits = self._nxd_backed_edit_count()
        if nxd_edits:
            # These ARE written now. What can still stop them is a missing
            # database or a missing FF16Tools, which is a setup problem the
            # reader can fix - so it reads like the other tool warnings
            # rather than like a feature that does not exist.
            missing = []
            if getattr(state, "nxd_sqlite_path", None) is None:
                missing.append("a converted game database")
            if getattr(state, "ff16tools_cli_path", None) is None:
                missing.append("FF16Tools")
            if missing:
                parts.append(
                    f"{nxd_edits} name/description and override edit(s) need "
                    f"{' and '.join(missing)} to be written into the mod. "
                    f"Set that up under General Setup.")
        text = " ".join(parts)
        self.missing_note.setText(text)
        # Shown only when it says something - see where it is built.
        self.missing_note.setVisible(bool(text))

    # -- exporting -----------------------------------------------------------------

    def browse_output(self, _checked=False, path: str | None = None) -> None:
        if path is None:
            path = QFileDialog.getExistingDirectory(
                self, "Where should the mod folder go?")
        if path:
            self.output_field.setText(path)
            self.output_hint.setText("")

    def _edited_jobs(self) -> list:
        by_id = {r.job_id: r for r in (self.state.job_records or [])}
        return [(by_id[job_id], fields, None)
                for job_id, fields in sorted(self.state.edits.items())
                if fields and job_id in by_id]

    def _edited_commands(self) -> list:
        by_id = {r.command_id: r for r in (self.state.job_command_records or [])}
        return [(by_id[cid], fields, None)
                for cid, fields in sorted(self.state.job_command_edits.items())
                if fields and cid in by_id]

    # -- text the Mod Contents pane shows ------------------------------------
    #
    # Public, and built through the SAME engine calls the export itself
    # uses. A preview generated any other way is a second implementation
    # that can disagree with the file actually written, which would make it
    # worse than no preview at all.

    def job_diff_xml_text(self) -> str:
        return xml_io.build_diff_xml_text(
            self.state.table_version, self._edited_jobs(),
            self.state.job_preserved)

    def job_command_diff_xml_text(self) -> str:
        return xml_io.build_job_command_diff_xml_text(
            self.state.job_command_version, self._edited_commands(),
            self.state.job_command_preserved)

    def table_diff_xml_text(self, key: str) -> str:
        spec = ix.ALL_SPECS.get(key)
        if spec is None:
            return f"No table spec for '{key}'."
        records = {r.item_id: r for r
                   in (self.state.item_table_records or {}).get(key, [])}
        edits = (self.state.item_table_edits or {}).get(key, {})
        entries = [(records[rid], fields, None)
                   for rid, fields in sorted(edits.items())
                   if fields and rid in records]
        if not entries:
            return "Nothing edited in this table, so it won't be written."
        version = (self.state.item_table_versions or {}).get(key, "1")
        return ix.build_diff_xml_text(spec, version, entries)

    def config_preview_text(self) -> str:
        """
        The ModConfig.json this page would write, right now.

        Built through `modconfig.build_config` with the metadata the fields
        currently hold, so what is previewed is what lands - including the
        GitHub auto-update block and the tags, both of which have been
        silently wrong on this page before.
        """
        import json
        try:
            meta = self._metadata_from_fields()
            existing = getattr(self.state, "loaded_mod_config", None)
            # An opened mod is MERGED, not rebuilt - the same call the
            # export makes. `build_mod_config` alone would drop the keys
            # Reloaded-II owns (GitHubDependencies, IgnoreRegexes and the
            # rest), so a preview built that way would show an author a
            # manifest far smaller than the one they are about to write.
            config = (modconfig.merge_mod_config(existing, meta) if existing
                      else modconfig.build_mod_config(meta))
            return json.dumps(config, indent=2)
        except Exception as exc:                              # noqa: BLE001
            return f"Couldn't build the manifest yet: {exc}"

    def _metadata_from_fields(self, destination: str = "",
                              mod_id: str = "") -> "modconfig.ModMetadata":
        """
        One place the mod's metadata is assembled from the form.

        Both the export and the ModConfig.json preview go through this, so
        the preview cannot drift from the file. It had no preview when the
        GitHub block and the tags were being dropped; a preview built
        separately would have shown them correct while the export wrote them
        empty.
        """
        mod_id = mod_id or self.id_field.text().strip()
        return modconfig.ModMetadata(
            mod_id=mod_id,
            mod_name=self.name_field.text().strip() or mod_id,
            author=self.author_field.text().strip(),
            version=self.version_field.text().strip() or "1.0.0",
            description=self.description_field.toPlainText().strip(),
            # From the panel, not hard-coded. `game_mode` follows the
            # executables ticked: enhanced only, classic only, or both.
            game_mode=self._game_mode_for(self.chosen_app_ids()),
            # The Category box, plus any other tags an opened mod carried.
            # This used to be a hard-coded empty list, so re-exporting an
            # asset mod silently stripped its "asset" tag.
            tags=self._chosen_tags(),
            dependencies=self.chosen_dependencies(),
            supported_app_ids=self.chosen_app_ids(),
            project_url=self.project_url_field.text().strip(),
            icon_source=self._icon_source(destination, mod_id),
            icon_filename=(Path(self.icon_field.text().strip()).name
                           if self.icon_field.text().strip()
                           else (self._carried_icon or "")),
            github_user=self.github_user_field.text().strip(),
            github_repo=self.github_repo_field.text().strip(),
            github_use_release_tag=self.github_tag_check.isChecked(),
            github_asset_filename=self.github_asset_field.text().strip(),
            built_against_game_version=getattr(
                self.state, "unpacked_game_version", "") or "",
            # The reference-table versions this mod was actually built
            # against. This was an empty dict, so every mod Mod Studio made
            # recorded nothing on the XML side - and `ModStamp.table_versions`
            # exists precisely because "the game version alone doesn't date
            # the XML side of a mod". `modconfig` falls back to the opened
            # mod's own stamp when this is empty, so re-exports kept working
            # and a NEW mod recorded nothing at all, which is why it went
            # unnoticed.
            built_against_table_versions={
                **{key: version for key, version
                   in (self.state.item_table_versions or {}).items() if version},
                **{name: version for name, version
                   in (self.state.derived_table_versions or {}).items() if version},
            },
            built_against_clean_unpack=bool(
                getattr(self.state, "clean_unpack", False)),
        )

    def _extra_table_files(self) -> dict:
        """Diff XML for every generic table that has edits in it."""
        files = {}
        for key, edits in (self.state.item_table_edits or {}).items():
            spec = ix.ALL_SPECS.get(key)
            if spec is None:
                continue
            records = {r.item_id: r for r
                       in (self.state.item_table_records or {}).get(key, [])}
            entries = [(records[rid], fields, None)
                       for rid, fields in sorted(edits.items())
                       if fields and rid in records]
            if not entries:
                continue
            version = (self.state.item_table_versions or {}).get(key, "1")
            # constants.TABLE_FILENAMES is the authority. A missing key is
            # RAISED, not defaulted to f"{key}.xml" - that fallback would
            # have written "item.xml" where the loader expects
            # "ItemData.xml", producing a mod that silently does nothing.
            # This project has already paid once for a lookup that skipped
            # what it did not recognise: 520 tables were generated and never
            # copied because a stale 37-name list did not mention them.
            filename = c.TABLE_FILENAMES.get(key)
            if filename is None:
                raise KeyError(
                    f"No filename known for table {key!r}. Add it to "
                    f"constants.TABLE_FILENAMES rather than guessing one.")
            files[filename] = ix.build_diff_xml_text(spec, version, entries)

        # XML tables with no hand-written spec, keyed by their filename.
        #
        # No TABLE_FILENAMES lookup here, and no risk of one going wrong:
        # the key IS the filename the loader expects, which is why the
        # store is keyed that way.
        derived = ix.discover_specs(paths.bundled_data_dir())
        for filename, edits in (self.state.derived_table_edits or {}).items():
            spec = derived.get(filename)
            if spec is None:
                # Raised, not skipped. A silently dropped table is how 520
                # generated tables once went uncopied; if the file the
                # edits came from has gone, the person needs telling.
                raise KeyError(
                    f"{filename} has edits but is no longer in the bundled "
                    f"tables, so no spec can be derived for it.")
            records = {r.item_id: r for r
                       in (self.state.derived_table_records or {}).get(filename, [])}
            entries = [(records[rid], fields, None)
                       for rid, fields in sorted(edits.items())
                       if fields and rid in records]
            if not entries:
                continue
            version = (self.state.derived_table_versions or {}).get(filename, "1")
            files[filename] = ix.build_diff_xml_text(spec, version, entries)
        return files

    def export(self) -> None:
        mod_id = self.id_field.text().strip()
        complaint = modconfig.validate_mod_id(mod_id) if mod_id else "Give the mod an ID."
        if complaint:
            self._say(complaint, "danger")
            return

        destination = self.output_field.text().strip()
        if not destination:
            self._say("Choose where the mod folder should go.", "attention")
            return

        jobs = self._edited_jobs()
        commands = self._edited_commands()
        extras = self._extra_table_files()
        assets = bool(self.state.texture_edits or self.state.sound_edits)
        # A texture pack has no table edits at all, and this used to refuse
        # to export one - "there's nothing to export yet" for a mod whose
        # entire content is textures.
        if not (jobs or commands or extras or assets):
            # Never write an empty mod and report success - but a mod whose
            # whole content is name and description edits is NOT empty.
            #
            # Those write no XML and stage no asset, so every check above
            # this line misses them, and the export used to refuse with
            # "make some changes in Edit Game Data first" at somebody who
            # had just spent an hour renaming items. The only case that
            # genuinely cannot proceed is the tools being absent.
            if self._nxd_backed_edit_count():
                if (getattr(self.state, "nxd_sqlite_path", None) is None
                        or getattr(self.state, "ff16tools_cli_path", None)
                        is None):
                    self._say(
                        "Your edits are all name/description or override "
                        "edits, which are written into .nxd files - and that "
                        "needs a converted game database and FF16Tools, set "
                        "up under General Setup. Your edits are safe.",
                        "attention")
                    return
                # There IS work; it is all .nxd. Fall through and build.
            else:
                self._say(
                    "There's nothing to export yet - make some changes in "
                    "Edit Game Data first.", "attention")
                return

        meta = self._metadata_from_fields(destination, mod_id)

        try:
            # Built even when there are no job edits, which is what the
            # Tkinter export does.
            #
            # Passing "" wrote a **zero-byte JobData.xml**, and
            # `scaffold_mod_folder` writes that file unconditionally - so
            # every mod with no job edits shipped an unparseable XML file.
            # Nobody had hit it because the Qt page refused to export a mod
            # with no table edits at all; enabling texture-only exports made
            # it reachable. An empty `<JobTable>` with no entries is a valid
            # document that says "this mod changes no jobs", which is true.
            job_xml = xml_io.build_diff_xml_text(
                self.state.table_version or "1", jobs)
            command_xml = (xml_io.build_job_command_diff_xml_text(
                self.state.job_command_version or "1", commands)
                if commands else None)
            root = modconfig.scaffold_mod_folder(
                Path(destination), meta, job_xml,
                job_command_xml_text=command_xml,
                extra_table_files=extras or None)
        except Exception as exc:                              # noqa: BLE001
            self._say(f"The mod couldn't be built: {exc}", "danger")
            self._log(repr(exc))
            return

        written = [name for name in ("JobData.xml",) if jobs]
        if command_xml:
            written.append("JobCommandData.xml")
        written.extend(sorted(extras))
        self._log(f"Wrote {root}")
        for name in written:
            self._log(f"   {name}")
        self.last_built = root
        # Which FFTIVC/tables/<mode>/ subfolder everything goes under. The
        # .nxd stage needs it too and runs after the asset stage, so it is
        # kept rather than re-derived - re-deriving it would read the
        # executable tick boxes again, which the user may have changed
        # while the export was running.
        self._last_mode = meta.game_mode
        self._asset_detail = None
        self._said_trouble = False
        self.open_folder_button.setEnabled(True)
        self.zip_button.setEnabled(True)

        if self.state.texture_edits or self.state.sound_edits:
            self._say(
                "Tables written. Converting textures and repacking sound "
                "archives...", "muted")
            self.export_button.setEnabled(False)
            worker = AssetExportWorker(
                root, meta.game_mode, self.state.texture_edits,
                self.state.sound_edits,
                getattr(self.state, "ff16tools_cli_path", None),
                getattr(self.state, "audiomog_exe_path", None),
                getattr(self.state, "nxd_unpack_dir", None))
            self._thread = run_in_thread(
                worker, on_finished=self._assets_done,
                on_failed=self._assets_failed, on_log=self._log)
            return

        self._asset_detail = None
        self._start_nxd_stage()

    def _start_nxd_stage(self) -> None:
        """
        Writes the `.nxd`-backed edits into the mod that has just been built.

        Last, because it is the slowest step and because it needs the mod
        folder to already exist to copy into. A mod with no name,
        description or override edits skips it entirely and costs nothing.

        This interface used to stop before this and TELL the author their
        name and description edits would not be in the mod. That was honest
        but wrong: the Tkinter interface has always written them, and Game
        Updates' Review My Changes hands back edits that live entirely in
        .nxd - so without this the whole feature dead-ended at export.
        """
        worker = NxdExportWorker(self.state, self.last_built,
                                 self._last_mode or "enhanced")
        if not worker.has_work():
            self._finish_export()
            return
        self._say("Tables written. Applying name, description and override "
                  "edits and converting to .nxd...", "muted")
        self.export_button.setEnabled(False)
        self._thread = run_in_thread(
            worker, on_finished=self._nxd_done,
            on_failed=self._nxd_failed, on_log=self._log)

    def _nxd_done(self, result: dict) -> None:
        self.export_button.setEnabled(True)
        written = result.get("written", 0)
        if written:
            self._log(f"   wrote {written} .nxd file(s)")
        for name in result.get("skipped", []):
            self._log(f"   left out (not in this database): {name}")
        self._finish_export(
            f"{written} .nxd file(s)" if written else None)

    def _nxd_failed(self, message: str) -> None:
        self.export_button.setEnabled(True)
        # The rest of the mod is real and on disk, so this is a partial mod
        # rather than a failed export - the same rule the asset stage
        # follows. Saying "export failed" sends someone looking for a folder
        # that exists and is most of the way there.
        self._say(
            f"The mod at {self.last_built} was built, but your name, "
            f"description and override edits were NOT written into it: "
            f"{message}", "danger")
        self.exported.emit(self.last_built)

    def _finish_export(self, nxd_detail: str | None = None) -> None:
        parts = [p for p in (getattr(self, "_asset_detail", None), nxd_detail)
                 if p]
        suffix = f" - {' and '.join(parts)}." if parts else ""
        if not self._said_trouble:
            self._say(f"Built your mod at {self.last_built}{suffix}", "ok")
        self.exported.emit(self.last_built)

    def _assets_done(self, result: dict) -> None:
        """
        Reports how much of the mod's art and audio actually landed.

        Counts of how many of how many, not "done". A mod missing three of
        its forty textures is a broken mod, and the person building it needs
        to know that at export time rather than in a bug report.
        """
        self.export_button.setEnabled(True)
        parts = []
        if result["texture_total"]:
            parts.append(f"{result['textures']} of {result['texture_total']} "
                         f"texture(s)")
        if result["sound_total"]:
            parts.append(f"{result['sounds']} of {result['sound_total']} "
                         f"sound archive(s)")
        detail = " and ".join(parts)

        for line in result["errors"]:
            self._log(f"   ! {line}")
        for line in result["skipped"]:
            self._log(f"   skipped (needs FF16Tools): {line}")

        self._said_trouble = not (
            not result["errors"] and not result["skipped"]
            and result["textures"] == result["texture_total"]
            and result["sounds"] == result["sound_total"])
        clean = (not result["errors"] and not result["skipped"]
                 and result["textures"] == result["texture_total"]
                 and result["sounds"] == result["sound_total"])
        if clean:
            self._say(f"Built your mod at {self.last_built} - {detail}.", "ok")
        else:
            trouble = []
            if result["skipped"]:
                trouble.append(f"{len(result['skipped'])} skipped")
            if result["errors"]:
                trouble.append(f"{len(result['errors'])} failed")
            self._say(
                f"Built your mod at {self.last_built}, but only {detail} "
                f"({', '.join(trouble)} - see the log).", "attention")
        self._asset_detail = detail if clean else None
        self._start_nxd_stage()

    def _assets_failed(self, message: str) -> None:
        self.export_button.setEnabled(True)
        # The tables are on disk and are real, so this is a partial mod
        # rather than a failed export. Saying "export failed" would send
        # someone looking for a folder that exists and is half right.
        self._say(
            f"The tables were written to {self.last_built}, but the textures "
            f"and sounds couldn't be: {message}", "danger")
        self.exported.emit(self.last_built)

    # -- after building --------------------------------------------------------

    def open_mod_folder(self) -> None:
        if self.last_built is None:
            return
        if not reveal_in_file_manager(self.last_built):
            self._say(f"Couldn't open {self.last_built}.", "attention")

    def zip_mod(self, _checked=False, path: str | None = None) -> None:
        """
        Zips the built mod for uploading, with the mod folder inside it.

        A zip that unpacks loose is how somebody's Reloaded-II mods folder
        ends up full of stray XML, so the folder stays the archive's top
        level.
        """
        if self.last_built is None:
            self._say("Build the mod first.", "attention")
            return
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save the mod zip",
                str(self.last_built.parent / f"{self.last_built.name}.zip"),
                "Zip archives (*.zip)")
        if not path:
            return
        try:
            written = zip_folder(self.last_built, Path(path))
        except Exception as exc:                              # noqa: BLE001
            self._say(f"Couldn't build the zip: {exc}", "danger")
            return
        self._log(f"Zipped to {written}")
        self._say(f"Zipped your mod to {written}", "ok")

    def choose_icon(self, _checked=False, path: str | None = None) -> None:
        """
        Picks the image Reloaded-II shows for the mod in its list.

        Optional, and left blank rather than defaulted to something of this
        tool's - a mod wearing the editor's logo would misrepresent who made
        it.
        """
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Choose a mod icon", "",
                "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.icon_field.setText(path)

    def start_new_mod(self) -> None:
        """
        Forgets the mod currently open so the next export is a fresh one.

        It clears the mod, NOT the machine: the unpacked game, the converted
        database and the tool paths all survive, because they belong to the
        computer rather than to whatever mod you were making. That split is
        `clear_opened_mod_content`'s, not this page's.

        **The three XML edit stores are cleared here as well**, because
        `clear_opened_mod_content` does not clear them: `edits` (jobs),
        `job_command_edits` and `item_table_edits` are all absent from it,
        while every database-derived store is present. Its docstring says it
        "forgets everything that came from a previously opened mod", so
        either the omission is deliberate for a reason not written down, or
        it is a gap - and opening a second mod would carry the first one's
        job edits into it, which is the exact bug that method was written to
        fix, for a different set of stores.

        Changed in the engine since, so this page no longer compensates.
        For "start a new mod" the intent was unambiguous either way:
        nothing of the old mod should survive.
        """
        # The three that used to be cleared here are cleared by
        # `clear_opened_mod_content` itself now, which is what its docstring
        # always said it did.
        self.state.clear_opened_mod_content()
        self.last_built = None
        self.icon_field.setText("")

        # And the details the page now carries across from an opened mod.
        #
        # Without this the fields kept the old mod's name, author, version
        # and id after "Start New Mod Instead", so the next export would go
        # straight back over the mod the button exists to stop overwriting.
        self.state.loaded_mod_config = None
        self._adopted_mod_id = None
        self._carried_tags = None
        self._carried_icon = None
        self.category_box.setCurrentText("gameplay")
        self.opened_mod_banner.setVisible(False)
        self.name_field.setText("My FFT Mod")
        self.author_field.setText("")
        self.version_field.setText("1.0.0")
        self.description_field.setPlainText("")
        self._suggest_id(self.name_field.text())
        self.open_folder_button.setEnabled(False)
        self.zip_button.setEnabled(False)
        self.refresh_summary()
        self._say("Started a new mod - your previous edits have been cleared.",
                  "muted")
        self.exported.emit(Path())

    # -- helpers --------------------------------------------------------------------

    def _say(self, text: str, role: str) -> None:
        self.status.setText(text)
        self.status.setProperty("role", role)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _log(self, line: str) -> None:
        self.log.appendPlainText(line)
