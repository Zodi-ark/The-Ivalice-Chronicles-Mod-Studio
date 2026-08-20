"""
The "Sounds" tab within the combined Edit Game Data step - browses the
unpacked game's .sab sound archives (music, voice lines, common SFX/UI
banks) and lets the user listen to and stage replacements for individual
tracks inside them, via AudioMog (see audiomog.py/sound_data.py).

Closest in spirit to Textures (real files in the unpacked game folder, no
database), but with one extra layer: a .sab has to be unpacked with
AudioMog before its track(s) - usually one, sometimes many for a shared
SFX bank - are even known, so there's a tree of .sab files on the left and
a "Tracks" sub-list on the right that only populates once a file's been
unpacked.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import constants as c

from .. import paths
from .. import sound_data as sd
from .step_editor import ScrollableFrame

CLASSIFICATION_LABELS = {
    "music": "Music track",
    "voice": "Voice line",
    "other": "Sound file",
}
CLASSIFICATION_NOTES = {
    "music": "",
    "voice": " Voice lines typically don't loop.",
    "other": "",
}


class SoundsPanel(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.current_relative_path: str | None = None
        self.current_project_dir: Path | None = None
        self.current_tracks: list = []
        self.current_track_index: int | None = None
        self._vanilla_track = None  # sound_data.TrackInfo for the currently loaded track
        self._preview_token = 0     # bumped per .sab selection, guards against stale unpack results
        self._applied_game_dir = None
        self._suppress_loop_trace = False
        self._queue: queue.Queue = queue.Queue()
        self._player = sd.SoundPlayer()

        self._build_layout()
        self.after(150, self._poll_queue)

    # -- layout ---------------------------------------------------------

    def _build_layout(self) -> None:
        ttk.Label(
            self, style="SubHeader.TLabel", wraplength=760, justify="left",
            text=(
                "Browse the unpacked game's sound archives (.sab - set the folder in General Setup, "
                "the same one Textures uses) and stage replacements. Loop points, so replaced music "
                "keeps looping seamlessly, are read from and written back into each track's own "
                "loop data automatically - voice lines typically don't carry any. Needs AudioMog.exe "
                "(General Setup) to unpack, preview, or replace anything here, since .sab is a "
                "proprietary archive format. Use Export as WAV... to pull the selected track out "
                "losslessly and edit it in your DAW of choice, then bring it back in with Replace..."
            ),
        ).pack(anchor="w", pady=(4, 8))

        self.no_data_var = tk.StringVar(value="")
        ttk.Label(
            self, textvariable=self.no_data_var, foreground="#b06000", wraplength=760, justify="left"
        ).pack(anchor="w", pady=(0, 8))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, width=320)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        self.changes_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.changes_var, foreground="#0a6e0a", wraplength=300, justify="left").pack(
            anchor="w", pady=(0, 6)
        )

        self.search_var = tk.StringVar()
        ttk.Entry(left, textvariable=self.search_var).pack(fill="x", pady=(0, 6))
        self.search_var.trace_add("write", lambda *_a: self._refresh_tree())
        ttk.Label(left, text="Search by filename (shows a flat matching list)", foreground="#888888").pack(anchor="w")

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.tree.tag_configure("edited", background=c.EDITED_ROW_BG, foreground=c.EDITED_ROW_FG)
        self.tree.tag_configure("folder", foreground="#333333")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        right_scroll = ScrollableFrame(right)
        right_scroll.pack(fill="both", expand=True)
        right = right_scroll.inner

        self.current_path_var = tk.StringVar(value="No sound file selected")
        ttk.Label(right, textvariable=self.current_path_var, font=("Segoe UI", 11, "bold"), wraplength=440).pack(
            anchor="w", pady=(0, 4)
        )
        self.status_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.status_var, foreground="#666666", wraplength=440).pack(
            anchor="w", pady=(0, 8)
        )

        self._build_track_list(right)
        self._build_track_detail(right)

    def _build_track_list(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Tracks", padding=8)
        box.pack(fill="x", pady=(0, 8))
        frame = ttk.Frame(box)
        frame.pack(fill="x")
        self.track_tree = ttk.Treeview(
            frame, columns=("users", "loop"), show="headings", height=4, selectmode="browse"
        )
        self.track_tree.heading("users", text="Track / in-game use")
        self.track_tree.heading("loop", text="Loops")
        self.track_tree.column("users", width=260, anchor="w")
        self.track_tree.column("loop", width=120, anchor="w")
        track_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.track_tree.yview)
        self.track_tree.configure(yscrollcommand=track_scroll.set)
        self.track_tree.pack(side="left", fill="x", expand=True)
        track_scroll.pack(side="right", fill="y")
        self.track_tree.tag_configure("edited", background=c.EDITED_ROW_BG, foreground=c.EDITED_ROW_FG)
        self.track_tree.bind("<<TreeviewSelect>>", self._on_track_select)

    def _build_track_detail(self, parent) -> None:
        self.detail_frame = ttk.Frame(parent)
        self.detail_frame.pack(fill="both", expand=True)

        self.track_info_var = tk.StringVar(value="")
        ttk.Label(
            self.detail_frame, textvariable=self.track_info_var, wraplength=440, justify="left",
            foreground="#444444",
        ).pack(anchor="w", pady=(0, 8))

        current_row = ttk.Frame(self.detail_frame)
        current_row.pack(fill="x", pady=(0, 4))
        ttk.Label(current_row, text="Current (vanilla):", width=20, anchor="w").pack(side="left")
        self.play_current_button = ttk.Button(
            current_row, text="Play", command=self._play_current, state="disabled"
        )
        self.play_current_button.pack(side="left", padx=(0, 4))
        ttk.Button(current_row, text="Stop", command=self._stop_playback).pack(side="left")

        pending_row = ttk.Frame(self.detail_frame)
        pending_row.pack(fill="x", pady=(0, 4))
        ttk.Label(pending_row, text="Replacement (pending):", width=20, anchor="w").pack(side="left")
        self.play_pending_button = ttk.Button(
            pending_row, text="Play", command=self._play_pending, state="disabled"
        )
        self.play_pending_button.pack(side="left", padx=(0, 4))
        ttk.Button(pending_row, text="Stop", command=self._stop_playback).pack(side="left")

        self.pending_status_var = tk.StringVar(value="(none staged)")
        ttk.Label(
            self.detail_frame, textvariable=self.pending_status_var, foreground="#666666",
            wraplength=440, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        action_row = ttk.Frame(self.detail_frame)
        action_row.pack(fill="x", pady=(0, 8))
        self.replace_button = ttk.Button(
            action_row, text="Replace...", command=self._on_replace_clicked, state="disabled"
        )
        self.replace_button.pack(side="left")
        self.clear_button = ttk.Button(
            action_row, text="Clear Replacement", command=self._on_clear_clicked, state="disabled"
        )
        self.clear_button.pack(side="left", padx=(6, 0))

        export_row = ttk.Frame(self.detail_frame)
        export_row.pack(fill="x", pady=(0, 8))
        self.export_button = ttk.Button(
            export_row, text="Export as WAV...", command=self._on_export_clicked, state="disabled"
        )
        self.export_button.pack(side="left")

        self.loop_frame = ttk.LabelFrame(self.detail_frame, text="Loop Points (samples)", padding=8)
        loop_row = ttk.Frame(self.loop_frame)
        loop_row.pack(fill="x")
        vcmd = self.register(lambda p: p == "" or p.isdigit())
        self.loop_start_var = tk.StringVar(value="0")
        self.loop_end_var = tk.StringVar(value="0")
        ttk.Label(loop_row, text="Start:", width=8, anchor="w").pack(side="left")
        self.loop_start_entry = ttk.Entry(
            loop_row, textvariable=self.loop_start_var, width=12, validate="key", validatecommand=(vcmd, "%P")
        )
        self.loop_start_entry.pack(side="left", padx=(0, 12))
        ttk.Label(loop_row, text="End:", width=6, anchor="w").pack(side="left")
        self.loop_end_entry = ttk.Entry(
            loop_row, textvariable=self.loop_end_var, width=12, validate="key", validatecommand=(vcmd, "%P")
        )
        self.loop_end_entry.pack(side="left")
        self.loop_time_var = tk.StringVar(value="")
        ttk.Label(self.loop_frame, textvariable=self.loop_time_var, foreground="#777777").pack(
            anchor="w", pady=(4, 0)
        )
        ttk.Button(
            self.loop_frame, text="Reset to vanilla loop points", command=self._reset_loop_points
        ).pack(anchor="w", pady=(6, 0))
        self.loop_start_var.trace_add("write", self._on_loop_points_edited)
        self.loop_end_var.trace_add("write", self._on_loop_points_edited)
        self.loop_frame.pack_forget()  # only shown once a track with real loop data is loaded

    # -- tree (mirrors step_textures.TexturesPanel's tree, same shape) --------

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        tree_data = self.app.state_data.sound_tree
        if tree_data is None:
            return
        query = self.search_var.get().strip().lower()

        if query:
            matches = []
            self._collect_matches(tree_data, query, matches)
            for node in matches[:500]:
                tags = ["edited"] if self._is_edited(node.relative_path) else []
                self.tree.insert("", "end", iid=node.relative_path, text=node.relative_path, tags=tags)
        else:
            self._insert_node("", tree_data)

        self._update_changes_label()

    def _collect_matches(self, node, query: str, out: list) -> None:
        if node.is_file:
            if query in node.name.lower():
                out.append(node)
            return
        for child in node.children:
            self._collect_matches(child, query, out)

    def _insert_node(self, parent_iid: str, node) -> None:
        for child in node.children:
            if child.is_file:
                tags = ["edited"] if self._is_edited(child.relative_path) else []
                self.tree.insert(parent_iid, "end", iid=child.relative_path, text=child.name, tags=tags)
            else:
                edited_count = self._count_edited_under(child)
                label = f"{child.name} ({edited_count} edited)" if edited_count else child.name
                node_id = self.tree.insert(
                    parent_iid, "end", iid=f"dir:{child.relative_path}", text=label, tags=["folder"], open=False
                )
                self._insert_node(node_id, child)

    def _is_edited(self, relative_path: str) -> bool:
        state = self.app.state_data
        # A file recovered from an opened mod counts as edited even though
        # there are no per-track edits behind it - the mod really does
        # replace it, and showing it as untouched would be misleading.
        return bool(state.sound_edits.get(relative_path)) or (
            relative_path in state.sound_file_replacements
        )

    def _count_edited_under(self, node) -> int:
        if node.is_file:
            return 1 if self._is_edited(node.relative_path) else 0
        return sum(self._count_edited_under(c) for c in node.children)

    def _update_changes_label(self) -> None:
        state = self.app.state_data
        total = sd.count_sounds(state.sound_tree) if state.sound_tree else 0
        files_count = state.edited_sound_file_count()
        tracks_count = state.edited_sound_track_count()
        message = (
            f"{files_count} of {total} sound file(s) have a staged replacement "
            f"({tracks_count} track{'s' if tracks_count != 1 else ''} total)."
        )
        carried = state.replaced_sound_file_count()
        if carried:
            # These came from an opened mod as finished .sab archives, so
            # there are no tracks to show or edit - say so plainly rather
            # than leaving them looking like ordinary staged edits.
            message += (
                f" {carried} more come from the mod you opened and are kept exactly as they are;"
                f" replace one here to change it."
            )
        self.changes_var.set(message)

    def _refresh_tree_tag(self, relative_path: str) -> None:
        edited = self._is_edited(relative_path)
        if self.tree.exists(relative_path):
            self.tree.item(relative_path, tags=["edited"] if edited else [])

    def _on_tree_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        iid = selection[0]
        if iid.startswith("dir:"):
            return
        if iid == self.current_relative_path:
            return  # already loaded/loading this exact file - re-selecting it is a no-op, not a reload
        self._load_sab(iid)

    # -- loading a .sab (unpack with AudioMog, threaded) -----------------------

    def _load_sab(self, relative_path: str) -> None:
        self.current_relative_path = relative_path
        self.current_path_var.set(relative_path)
        self.current_tracks = []
        self.current_project_dir = None
        self.current_track_index = None
        self.track_tree.delete(*self.track_tree.get_children())
        self._clear_track_detail()

        classification = sd.classify_sab_path(relative_path)
        kind_label = CLASSIFICATION_LABELS[classification]

        audiomog_exe = self.app.state_data.audiomog_exe_path
        if audiomog_exe is None:
            self.status_var.set(
                f"{kind_label} - AudioMog.exe isn't set up (General Setup) - needed to unpack/preview/replace."
            )
            return

        game_dir = self.app.state_data.unpacked_game_dir
        full_path = game_dir / relative_path
        cache_dir = paths.local_data_dir() / "sound_preview_cache"

        self.status_var.set(f"{kind_label} - unpacking with AudioMog (can take a moment for large sound banks)...")
        self._preview_token += 1
        token = self._preview_token

        def worker() -> None:
            try:
                project_dir = sd.unpack_sab_cached(audiomog_exe, full_path, relative_path, cache_dir)
                tracks = sd.list_tracks(project_dir)
                error = None
            except Exception as exc:  # noqa: BLE001
                project_dir = None
                tracks = []
                error = str(exc)
            self._queue.put(("sab_loaded", (token, relative_path, project_dir, tracks, error)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "sab_loaded":
                    token, relative_path, project_dir, tracks, error = payload
                    if token == self._preview_token and relative_path == self.current_relative_path:
                        self._apply_sab_loaded(project_dir, tracks, error)
        except queue.Empty:
            pass
        self.after(150, self._poll_queue)

    def _apply_sab_loaded(self, project_dir, tracks, error) -> None:
        if error:
            self.status_var.set(f"Couldn't unpack: {error}")
            return
        self.current_project_dir = project_dir
        self.current_tracks = tracks
        self._populate_track_tree(tracks)
        if tracks:
            classification = sd.classify_sab_path(self.current_relative_path)
            self.status_var.set(f"{CLASSIFICATION_LABELS[classification]} - {len(tracks)} track(s) found.")
            first_iid = str(tracks[0].index)
            if self.track_tree.exists(first_iid):
                self.track_tree.selection_set(first_iid)
        else:
            self.status_var.set("AudioMog unpacked this file but no readable .wav tracks were found inside.")

    def _populate_track_tree(self, tracks: list) -> None:
        self.track_tree.delete(*self.track_tree.get_children())
        edits_for_sab = self.app.state_data.sound_edits.get(self.current_relative_path, {})
        for t in tracks:
            loop_label = f"{t.info.duration_sec:.1f}s, loops" if t.info.has_loop else f"{t.info.duration_sec:.1f}s, no loop"
            users_label = t.users or t.stem
            tags = ["edited"] if t.index in edits_for_sab else []
            self.track_tree.insert("", "end", iid=str(t.index), values=(users_label, loop_label), tags=tags)

    # -- track selection / detail ----------------------------------------------

    def _clear_track_detail(self) -> None:
        self.track_info_var.set("")
        self.play_current_button.configure(state="disabled")
        self.play_pending_button.configure(state="disabled")
        self.replace_button.configure(state="disabled")
        self.clear_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.pending_status_var.set("(none staged)")
        self.loop_frame.pack_forget()
        self._vanilla_track = None

    def _on_track_select(self, _event=None) -> None:
        selection = self.track_tree.selection()
        if not selection:
            return
        self._load_track(int(selection[0]))

    def _load_track(self, idx: int) -> None:
        self.current_track_index = idx
        track = next((t for t in self.current_tracks if t.index == idx), None)
        if track is None:
            return
        self._vanilla_track = track
        info = track.info

        classification = sd.classify_sab_path(self.current_relative_path)
        note = CLASSIFICATION_NOTES[classification]
        if info.has_loop:
            loop_desc = (
                f"Loops: samples {info.loop_start:,} \u2192 {info.loop_end:,} "
                f"({self._fmt_time(info.loop_start, info.sample_rate)} \u2192 "
                f"{self._fmt_time(info.loop_end, info.sample_rate)})"
            )
        else:
            loop_desc = "Loops: no (plays once)"
        header = track.stem + (f" \u2014 {track.users}" if track.users else "")
        self.track_info_var.set(
            f"{header}\n{info.sample_rate} Hz, {info.channels} ch, {info.duration_sec:.2f}s. {loop_desc}.{note}"
        )

        self.play_current_button.configure(state="normal")
        self.replace_button.configure(state="normal")
        self.export_button.configure(state="normal")

        edit = self.app.state_data.sound_edits.get(self.current_relative_path, {}).get(idx)
        self.clear_button.configure(state="normal" if edit else "disabled")
        self.play_pending_button.configure(state="normal" if edit else "disabled")
        self.pending_status_var.set(str(edit["source_path"]) if edit else "(none staged)")

        if info.has_loop:
            self.loop_frame.pack(fill="x", pady=(0, 8))
            if edit is not None:
                start = edit.get("loop_start") if edit.get("loop_start") is not None else info.loop_start
                end = edit.get("loop_end") if edit.get("loop_end") is not None else info.loop_end
                entry_state = "normal"
            else:
                start, end = info.loop_start, info.loop_end
                entry_state = "disabled"  # informational only until a replacement exists to attach these to
            self._set_loop_fields(start, end, info.sample_rate)
            self.loop_start_entry.configure(state=entry_state)
            self.loop_end_entry.configure(state=entry_state)
        else:
            self.loop_frame.pack_forget()

    @staticmethod
    def _fmt_time(samples: int, rate: int) -> str:
        if not rate:
            return "0:00.0"
        total = samples / rate
        minutes = int(total // 60)
        seconds = total - minutes * 60
        return f"{minutes}:{seconds:04.1f}"

    def _set_loop_fields(self, start: int, end: int, sample_rate: int) -> None:
        self._suppress_loop_trace = True
        self.loop_start_var.set(str(start))
        self.loop_end_var.set(str(end))
        self._suppress_loop_trace = False
        self.loop_time_var.set(f"{self._fmt_time(start, sample_rate)} \u2192 {self._fmt_time(end, sample_rate)}")

    def _on_loop_points_edited(self, *_args) -> None:
        if self._suppress_loop_trace or self.current_relative_path is None or self.current_track_index is None:
            return
        edits_for_sab = self.app.state_data.sound_edits.get(self.current_relative_path, {})
        edit = edits_for_sab.get(self.current_track_index)
        if edit is None:
            return
        try:
            start = int(self.loop_start_var.get())
        except ValueError:
            start = edit.get("loop_start") or 0
        try:
            end = int(self.loop_end_var.get())
        except ValueError:
            end = edit.get("loop_end") or 0
        edit["loop_start"] = start
        edit["loop_end"] = end
        rate = self._vanilla_track.info.sample_rate if self._vanilla_track else 0
        self.loop_time_var.set(f"{self._fmt_time(start, rate)} \u2192 {self._fmt_time(end, rate)}")

    def _reset_loop_points(self) -> None:
        if self._vanilla_track is None or not self._vanilla_track.info.has_loop:
            return
        info = self._vanilla_track.info
        edit = self.app.state_data.sound_edits.get(self.current_relative_path, {}).get(self.current_track_index)

        replacement_samples = None
        if edit is not None:
            try:
                replacement_samples = sd.read_wav_info(edit["source_path"]).num_samples
            except (ValueError, OSError):
                replacement_samples = None

        if replacement_samples is not None:
            start, end = sd.clamp_loop_points(info.loop_start, info.loop_end, replacement_samples)
            start, end = start or 0, end or 0
        else:
            start, end = info.loop_start, info.loop_end

        if edit is not None:
            edit["loop_start"] = start
            edit["loop_end"] = end
        self._set_loop_fields(start, end, info.sample_rate)

    # -- replace / clear ----------------------------------------------------

    def _on_replace_clicked(self) -> None:
        if self.current_relative_path is None or self.current_track_index is None or self._vanilla_track is None:
            return
        chosen = filedialog.askopenfilename(
            title="Select a replacement WAV file", filetypes=[("WAV audio", "*.wav"), ("All files", "*.*")],
        )
        if not chosen:
            return
        chosen_path = Path(chosen)
        try:
            replacement_info = sd.read_wav_info(chosen_path)
        except ValueError as exc:
            messagebox.showerror(
                "Invalid WAV File",
                f"{exc}\n\nAudioMog's own rebuild step only accepts .wav (or .hca) files - export your "
                "replacement as a standard PCM .wav.",
            )
            return

        vanilla_info = self._vanilla_track.info
        if vanilla_info.has_loop:
            start, end = sd.clamp_loop_points(vanilla_info.loop_start, vanilla_info.loop_end, replacement_info.num_samples)
        else:
            start, end = None, None

        edits_for_sab = self.app.state_data.sound_edits.setdefault(self.current_relative_path, {})
        edits_for_sab[self.current_track_index] = {
            "source_path": chosen_path, "loop_start": start, "loop_end": end,
        }
        self._refresh_tree_tag(self.current_relative_path)
        self._populate_track_tree(self.current_tracks)
        self._reselect_track(self.current_track_index)
        self._update_changes_label()

    def _on_clear_clicked(self) -> None:
        if self.current_relative_path is None or self.current_track_index is None:
            return
        edits_for_sab = self.app.state_data.sound_edits.get(self.current_relative_path)
        if edits_for_sab:
            edits_for_sab.pop(self.current_track_index, None)
            if not edits_for_sab:
                self.app.state_data.sound_edits.pop(self.current_relative_path, None)
        self._refresh_tree_tag(self.current_relative_path)
        self._populate_track_tree(self.current_tracks)
        self._reselect_track(self.current_track_index)
        self._update_changes_label()

    def _on_export_clicked(self) -> None:
        if self._vanilla_track is None:
            return
        default_name = f"{self._vanilla_track.stem}.wav"
        chosen = filedialog.asksaveasfilename(
            title="Export track as WAV",
            initialfile=default_name,
            defaultextension=".wav",
            filetypes=[("WAV audio", "*.wav"), ("All files", "*.*")],
        )
        if not chosen:
            return
        try:
            sd.export_track_wav(self._vanilla_track.wav_path, Path(chosen))
            self.status_var.set(f"Exported {self._vanilla_track.stem} to {chosen}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Export Failed", f"Couldn't export track: {exc}")

    def _reselect_track(self, idx: int) -> None:
        iid = str(idx)
        if self.track_tree.exists(iid):
            self.track_tree.selection_set(iid)
        else:
            self._load_track(idx)

    # -- playback -------------------------------------------------------------

    def _play_current(self) -> None:
        if self._vanilla_track is None:
            return
        track = self._vanilla_track
        preview_dir = paths.local_data_dir() / "sound_playback_scratch"
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = preview_dir / "current_preview.wav"
        try:
            sd.build_preview_wav(track.wav_path, preview_path, track.info.loop_start, track.info.loop_end)
            self._player.play(preview_path)
            self.status_var.set("Playing current (vanilla) track...")
        except Exception as exc:  # noqa: BLE001
            self.status_var.set(f"Couldn't play: {exc}")

    def _play_pending(self) -> None:
        if self.current_relative_path is None or self.current_track_index is None:
            return
        edit = self.app.state_data.sound_edits.get(self.current_relative_path, {}).get(self.current_track_index)
        if edit is None:
            return
        preview_dir = paths.local_data_dir() / "sound_playback_scratch"
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = preview_dir / "pending_preview.wav"
        try:
            sd.build_preview_wav(edit["source_path"], preview_path, edit.get("loop_start"), edit.get("loop_end"))
            self._player.play(preview_path)
            self.status_var.set("Playing replacement (pending) track...")
        except Exception as exc:  # noqa: BLE001
            self.status_var.set(f"Couldn't play: {exc}")

    def _stop_playback(self) -> None:
        try:
            self._player.stop()
            self.status_var.set("Stopped.")
        except Exception as exc:  # noqa: BLE001
            self.status_var.set(f"Couldn't stop: {exc}")

    # -- called by the combined step's on_show() -----------------------------

    def on_show(self) -> None:
        state = self.app.state_data
        if state.unpacked_game_dir is None:
            extra = ""
            if state.sound_file_replacements:
                # Replacing a track needs the vanilla archive to repack
                # against, so unlike Textures these can't be edited without
                # game files - but the user should still be told the mod has
                # them rather than seeing a bare "nothing here".
                extra = (
                    f" This mod replaces {len(state.sound_file_replacements)} sound file(s); they "
                    f"are kept as they are, and unpacking is only needed to change them."
                )
            self.no_data_var.set(
                "No unpacked game folder set yet - go to General Setup, tick \u201cSounds and music\u201d, "
                "and press \u201cUnpack and Prepare Game Files\u201d." + extra
            )
            self.tree.delete(*self.tree.get_children())
            self.changes_var.set("")
            return

        if state.unpacked_game_dir != self._applied_game_dir or state.sound_tree is None:
            self._applied_game_dir = state.unpacked_game_dir
            self.no_data_var.set(f"Scanning {state.unpacked_game_dir}/sound for sound archives...")
            self.update_idletasks()
            try:
                state.sound_tree = sd.scan_sound_tree(state.unpacked_game_dir)
            except Exception as exc:  # noqa: BLE001
                self.no_data_var.set(f"Couldn't scan {state.unpacked_game_dir}: {exc}")
                return

        total = sd.count_sounds(state.sound_tree)
        if total == 0:
            self.no_data_var.set(
                f"No sound archives found under {state.unpacked_game_dir}/sound - double check this is "
                "the unpacked game's root folder."
            )
        elif state.audiomog_exe_path is None:
            self.no_data_var.set(
                "AudioMog.exe isn't set up yet (General Setup) - the tree below still browses fine, but "
                "unpacking/previewing/replacing needs it."
            )
        else:
            self.no_data_var.set("")
        self._refresh_tree()
