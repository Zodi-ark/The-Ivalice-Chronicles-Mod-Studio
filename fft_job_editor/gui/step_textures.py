"""
The "Textures" tab within the combined Edit Game Data step - browses the
unpacked game's .tga/.tex files directly (no nxd/sqlite involved, just a
real unpacked game folder set in General Setup) and lets the user stage a
replacement image for any of them. See texture_data.py for the actual
scanning/preview/staging logic - this module is purely the UI.

Unlike every other tab, there's no "reference data" or "database" to load -
the tree is built by directly scanning the folder General Setup points at,
and a staged replacement is just a path to a file on the user's computer
until Export actually converts and copies it.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import constants as c

from .. import paths
from .. import texture_data as td

PREVIEW_MAX_SIZE = (320, 320)


class TexturesPanel(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.current_relative_path: str | None = None
        self._current_photo = None
        self._pending_photo = None
        self._current_full_arr = None   # full-res RGBA array behind the (possibly downscaled) "Current" preview, for Export
        self._preview_token = 0   # bumped on every selection, so a slow background load can't clobber a newer one
        self._applied_game_dir = None
        self._queue: queue.Queue = queue.Queue()

        self._build_layout()
        self.after(150, self._poll_queue)

    # -- layout ---------------------------------------------------------

    def _build_layout(self) -> None:
        ttk.Label(
            self, style="SubHeader.TLabel", wraplength=760, justify="left",
            text=(
                "Browse the unpacked game's texture files (set the folder in General Setup) and "
                "stage replacements - .tga works directly; .tex needs FF16Tools.CLI (also General "
                "Setup) to preview and replace, since it's a proprietary format. Portrait faces "
                "(ui/ffto/common/face/texture) get Zodi's seam-fix applied automatically to any "
                "replacement, so there's nothing extra to run by hand. Use Export as PNG... to pull "
                "the current texture out losslessly and edit it in Photoshop, GIMP, or whatever you "
                "already use, then bring it back in with Replace..."
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

        self.current_path_var = tk.StringVar(value="No texture selected")
        ttk.Label(right, textvariable=self.current_path_var, font=("Segoe UI", 11, "bold"), wraplength=700).pack(
            anchor="w", pady=(0, 4)
        )
        self.status_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.status_var, foreground="#666666", wraplength=700).pack(
            anchor="w", pady=(0, 8)
        )

        preview_row = ttk.Frame(right)
        preview_row.pack(fill="x", pady=(0, 8))

        current_box = ttk.LabelFrame(preview_row, text="Current", padding=8)
        current_box.pack(side="left", padx=(0, 12))
        current_inner = tk.Frame(current_box, width=PREVIEW_MAX_SIZE[0], height=PREVIEW_MAX_SIZE[1])
        current_inner.pack()
        current_inner.pack_propagate(False)
        self.current_preview_label = tk.Label(current_inner, text="(no preview)")
        self.current_preview_label.pack(expand=True)

        pending_box = ttk.LabelFrame(preview_row, text="Replacement (pending)", padding=8)
        pending_box.pack(side="left")
        pending_inner = tk.Frame(pending_box, width=PREVIEW_MAX_SIZE[0], height=PREVIEW_MAX_SIZE[1])
        pending_inner.pack()
        pending_inner.pack_propagate(False)
        self.pending_preview_label = tk.Label(pending_inner, text="(none staged)")
        self.pending_preview_label.pack(expand=True)

        action_row = ttk.Frame(right)
        action_row.pack(fill="x", pady=(0, 8))
        self.replace_button = ttk.Button(
            action_row, text="Replace...", command=self._on_replace_clicked, state="disabled"
        )
        self.replace_button.pack(side="left")
        self.clear_button = ttk.Button(
            action_row, text="Clear Replacement", command=self._on_clear_clicked, state="disabled"
        )
        self.clear_button.pack(side="left", padx=(6, 0))

        export_row = ttk.Frame(right)
        export_row.pack(fill="x", pady=(0, 8))
        self.export_button = ttk.Button(
            export_row, text="Export as PNG...", command=self._on_export_clicked, state="disabled"
        )
        self.export_button.pack(side="left")

        self.face_note_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.face_note_var, foreground="#0a6e0a", wraplength=700, justify="left").pack(
            anchor="w"
        )

    # -- tree -------------------------------------------------------------

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        tree_data = self.app.state_data.texture_tree
        if tree_data is None:
            return
        query = self.search_var.get().strip().lower()

        if query:
            matches = []
            self._collect_matches(tree_data, query, matches)
            for node in matches[:500]:
                tags = ["edited"] if node.relative_path in self.app.state_data.texture_edits else []
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
                tags = ["edited"] if child.relative_path in self.app.state_data.texture_edits else []
                self.tree.insert(parent_iid, "end", iid=child.relative_path, text=child.name, tags=tags)
            else:
                edited_count = self._count_edited_under(child)
                label = f"{child.name} ({edited_count} edited)" if edited_count else child.name
                node_id = self.tree.insert(
                    parent_iid, "end", iid=f"dir:{child.relative_path}", text=label, tags=["folder"], open=False
                )
                self._insert_node(node_id, child)

    def _count_edited_under(self, node) -> int:
        edits = self.app.state_data.texture_edits
        if node.is_file:
            return 1 if node.relative_path in edits else 0
        return sum(self._count_edited_under(c) for c in node.children)

    def _update_changes_label(self) -> None:
        state = self.app.state_data
        total = td.count_textures(state.texture_tree) if state.texture_tree else 0
        count = state.edited_texture_count()
        self.changes_var.set(f"{count} of {total} textures have a staged replacement.")

    def _on_tree_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        iid = selection[0]
        if iid.startswith("dir:"):
            return
        self._load_texture(iid)

    # -- selection / preview ------------------------------------------------

    def _load_texture(self, relative_path: str) -> None:
        self.current_relative_path = relative_path
        self.current_path_var.set(relative_path)
        self.status_var.set("Loading preview...")
        self.replace_button.configure(state="normal")
        self.export_button.configure(state="disabled")
        self._current_full_arr = None
        is_face = td.is_face_texture(relative_path)
        self.face_note_var.set(
            "This is a portrait face texture - the seam-fix is applied automatically to any replacement."
            if is_face else ""
        )

        pending = self.app.state_data.texture_edits.get(relative_path)
        self.clear_button.configure(state="normal" if pending else "disabled")

        self._preview_token += 1
        token = self._preview_token
        game_dir = self.app.state_data.unpacked_game_dir
        cli_path = self.app.state_data.ff16tools_cli_path
        cache_dir = paths.local_data_dir() / "texture_preview_cache"
        pending_source = pending["source_path"] if pending else None
        # The tree can now contain textures a mod added with no game files
        # unpacked at all, so there may be no game folder to build a path
        # from - there's simply no "current" version to show.
        full_path = (game_dir / relative_path) if game_dir is not None else None
        # A texture the mod added has no vanilla original, so "not found" is
        # the expected state rather than a problem to report as one.
        added_by_mod = bool(pending and pending.get("already_staged")) and (
            full_path is None or not full_path.exists()
        )

        def worker() -> None:
            current_arr = None
            current_error = None
            if full_path is None:
                current_error = "No unpacked game folder - nothing to compare against."
            else:
                try:
                    current_arr = td.load_game_texture_preview(full_path, cli_path, cache_dir)
                except Exception as exc:  # noqa: BLE001
                    current_error = str(exc)

            pending_arr = None
            pending_error = None
            if pending_source is not None:
                try:
                    pending_arr = td.load_replacement_preview(pending_source, cli_path, cache_dir)
                    if is_face:
                        pending_arr, _ = td.apply_seam_fix(pending_arr)
                except Exception as exc:  # noqa: BLE001
                    pending_error = str(exc)

            if added_by_mod:
                current_error = "This texture is added by the mod - the game has no original."

            self._queue.put(("preview_ready", (token, current_arr, current_error, pending_arr, pending_error)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "preview_ready":
                    token, current_arr, current_error, pending_arr, pending_error = payload
                    if token == self._preview_token:
                        self._apply_preview(current_arr, current_error, pending_arr, pending_error)
        except queue.Empty:
            pass
        self.after(150, self._poll_queue)

    def _apply_preview(self, current_arr, current_error, pending_arr, pending_error) -> None:
        from PIL import Image, ImageTk

        self._current_full_arr = current_arr

        if current_arr is not None:
            img = Image.fromarray(current_arr, "RGBA")
            self.status_var.set(f"{img.width} \u00d7 {img.height} px")
            img.thumbnail(PREVIEW_MAX_SIZE)
            self._current_photo = ImageTk.PhotoImage(img)
            self.current_preview_label.configure(image=self._current_photo, text="")
            self.export_button.configure(state="normal")
        else:
            self.status_var.set(current_error or "Couldn't load preview.")
            self.current_preview_label.configure(image="", text="(preview unavailable)")
            self.export_button.configure(state="disabled")

        if pending_arr is not None:
            img2 = Image.fromarray(pending_arr, "RGBA")
            img2.thumbnail(PREVIEW_MAX_SIZE)
            self._pending_photo = ImageTk.PhotoImage(img2)
            self.pending_preview_label.configure(image=self._pending_photo, text="")
        elif pending_error:
            self.pending_preview_label.configure(image="", text=f"(error: {pending_error})")
        else:
            self.pending_preview_label.configure(image="", text="(none staged)")

    # -- replace / clear ----------------------------------------------------

    def _on_replace_clicked(self) -> None:
        if self.current_relative_path is None:
            return
        chosen = filedialog.askopenfilename(
            title="Select a replacement image",
            filetypes=[
                ("Image files", " ".join(f"*{ext}" for ext in td.REPLACEMENT_IMAGE_EXTENSIONS)),
                ("All files", "*.*"),
            ],
        )
        if not chosen:
            return
        self.app.state_data.texture_edits[self.current_relative_path] = {
            "source_path": Path(chosen),
            "is_face_texture": td.is_face_texture(self.current_relative_path),
        }
        self._refresh_tree_tag(self.current_relative_path)
        self._update_changes_label()
        self._load_texture(self.current_relative_path)

    def _on_clear_clicked(self) -> None:
        if self.current_relative_path is None:
            return
        self.app.state_data.texture_edits.pop(self.current_relative_path, None)
        self._refresh_tree_tag(self.current_relative_path)
        self._update_changes_label()
        self._load_texture(self.current_relative_path)

    def _refresh_tree_tag(self, relative_path: str) -> None:
        edited = relative_path in self.app.state_data.texture_edits
        if self.tree.exists(relative_path):
            self.tree.item(relative_path, tags=["edited"] if edited else [])
        self.clear_button.configure(state="normal" if edited else "disabled")

    # -- export -----------------------------------------------------------

    def _on_export_clicked(self) -> None:
        if self.current_relative_path is None or self._current_full_arr is None:
            return
        default_name = Path(self.current_relative_path).stem + ".png"
        chosen = filedialog.asksaveasfilename(
            title="Export texture as PNG",
            initialfile=default_name,
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("All files", "*.*")],
        )
        if not chosen:
            return
        try:
            td.save_array_as_png(self._current_full_arr, Path(chosen))
            self.status_var.set(f"Exported to {chosen}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Export Failed", f"Couldn't export texture: {exc}")

    # -- cross-tab jump target (e.g. Items' own icon shortcuts) --------------

    def select_relative_path(self, relative_path: str) -> None:
        """Clears any active search filter and selects/reveals one file, if its tree node exists yet."""
        self.search_var.set("")
        if self.tree.exists(relative_path):
            self.tree.selection_set(relative_path)
            self.tree.see(relative_path)

    # -- called by the combined step's on_show() -----------------------------

    def on_show(self) -> None:
        state = self.app.state_data
        if state.unpacked_game_dir is None:
            # Without game files there's nothing to browse - but a mod that
            # was just opened brings its own textures, and refusing to show
            # those is refusing to let someone edit a mod they already have.
            # Show exactly what the mod carries, and say what's missing.
            if state.texture_edits:
                self._applied_game_dir = None
                state.texture_tree = td.graft_extra_paths(
                    td.TextureTreeNode(name="(mod)", relative_path="", is_file=False),
                    state.texture_edits.keys(),
                )
                self.no_data_var.set(
                    "Showing only the textures this mod replaces. Unpack your game files in "
                    "General Setup to browse and replace the rest."
                )
                self._refresh_tree()
                return

            self.no_data_var.set(
                "No unpacked game folder set yet - go to General Setup, tick \u201cTextures\u201d, and "
                "press \u201cUnpack and Prepare Game Files\u201d."
            )
            self.tree.delete(*self.tree.get_children())
            self.changes_var.set("")
            return

        if state.unpacked_game_dir != self._applied_game_dir or state.texture_tree is None:
            self._applied_game_dir = state.unpacked_game_dir
            self.no_data_var.set(f"Scanning {state.unpacked_game_dir} for textures...")
            self.update_idletasks()
            try:
                state.texture_tree = td.scan_texture_tree(state.unpacked_game_dir)
            except Exception as exc:  # noqa: BLE001
                self.no_data_var.set(f"Couldn't scan {state.unpacked_game_dir}: {exc}")
                return

            # A mod can add a texture at a path the base game has no file
            # for (a new job's icon, say). The scan only sees the unpacked
            # game, so those would be counted as staged replacements while
            # being impossible to find in the browser.
            if state.texture_edits:
                td.graft_extra_paths(state.texture_tree, state.texture_edits.keys())

        total = td.count_textures(state.texture_tree)
        if total == 0:
            self.no_data_var.set(
                f"No .tga/.tex files found under {state.unpacked_game_dir} - double check this is "
                "the unpacked game's root folder."
            )
        else:
            self.no_data_var.set("")
        self._refresh_tree()


# =============================================================================
# InlineTextureSlot - a compact current/pending preview + Replace/Clear for
# ONE fixed relative path, for embedding in other tabs (currently: Items'
# own Art/Sprite icon shortcuts - see step_items.py) rather than browsing
# the full game tree. Reads/writes the exact same app.state_data.texture_
# edits dict the main Textures tab above uses (same key: forward-slashed
# relative path), so Export's existing texture pipeline needs zero changes
# to pick up edits made from here - it has no idea, or need to know, which
# tab staged them.
# =============================================================================

INLINE_PREVIEW_SIZE = (100, 100)


class InlineTextureSlot(ttk.Frame):
    def __init__(self, parent, app, title: str, on_view_in_textures=None, on_edit_changed=None):
        super().__init__(parent)
        self.app = app
        self.title = title
        self._on_view_in_textures = on_view_in_textures
        self._on_edit_changed = on_edit_changed
        self.relative_path: str | None = None
        self._current_photo = None
        self._pending_photo = None
        self._current_full_arr = None
        self._preview_token = 0
        self._queue: queue.Queue = queue.Queue()

        self._build_layout()
        self.after(150, self._poll_queue)

    # -- layout ---------------------------------------------------------

    def _build_layout(self) -> None:
        box = ttk.LabelFrame(self, text=self.title, padding=8)
        box.pack(fill="both", expand=True)

        self.path_var = tk.StringVar(value="")
        ttk.Label(box, textvariable=self.path_var, foreground="#888888", wraplength=620, justify="left").pack(
            anchor="w", pady=(0, 6)
        )

        previews = ttk.Frame(box)
        previews.pack(anchor="w")

        current_box = ttk.LabelFrame(previews, text="Current", padding=4)
        current_box.pack(side="left", padx=(0, 8))
        current_inner = tk.Frame(current_box, width=INLINE_PREVIEW_SIZE[0], height=INLINE_PREVIEW_SIZE[1])
        current_inner.pack()
        current_inner.pack_propagate(False)
        self.current_preview_label = tk.Label(current_inner, text="(no preview)")
        self.current_preview_label.pack(expand=True)

        pending_box = ttk.LabelFrame(previews, text="Replacement", padding=4)
        pending_box.pack(side="left")
        pending_inner = tk.Frame(pending_box, width=INLINE_PREVIEW_SIZE[0], height=INLINE_PREVIEW_SIZE[1])
        pending_inner.pack()
        pending_inner.pack_propagate(False)
        self.pending_preview_label = tk.Label(pending_inner, text="(none staged)")
        self.pending_preview_label.pack(expand=True)

        self.status_var = tk.StringVar(value="")
        ttk.Label(box, textvariable=self.status_var, foreground="#666666", wraplength=620, justify="left").pack(
            anchor="w", pady=(4, 6)
        )

        btn_row = ttk.Frame(box)
        btn_row.pack(anchor="w")
        self.replace_button = ttk.Button(btn_row, text="Replace...", command=self._on_replace_clicked)
        self.replace_button.pack(side="left")
        self.clear_button = ttk.Button(
            btn_row, text="Clear", command=self._on_clear_clicked, state="disabled"
        )
        self.clear_button.pack(side="left", padx=(6, 0))

        btn_row2 = ttk.Frame(box)
        btn_row2.pack(anchor="w", pady=(4, 0))
        self.export_button = ttk.Button(
            btn_row2, text="Export as PNG...", command=self._on_export_clicked, state="disabled"
        )
        self.export_button.pack(side="left")
        if self._on_view_in_textures is not None:
            ttk.Button(
                btn_row2, text="View in Textures tab \u2192", command=self._go_to_textures
            ).pack(side="left", padx=(6, 0))

    def _go_to_textures(self) -> None:
        if self._on_view_in_textures and self.relative_path:
            self._on_view_in_textures(self.relative_path)

    # -- public API ---------------------------------------------------------

    def set_relative_path(self, relative_path: str) -> None:
        """Points this slot at a (possibly new) fixed relative path and reloads its preview/pending state."""
        self.relative_path = relative_path
        self.path_var.set(relative_path)
        self.refresh()

    def refresh(self) -> None:
        """Re-reads app.state_data.texture_edits and reloads previews - call after any edit that might affect this path."""
        if self.relative_path is None:
            return
        state = self.app.state_data
        pending = state.texture_edits.get(self.relative_path)
        self.clear_button.configure(state="normal" if pending else "disabled")

        self._preview_token += 1
        token = self._preview_token
        self._current_full_arr = None
        game_dir = state.unpacked_game_dir
        cli_path = state.ff16tools_cli_path
        cache_dir = paths.local_data_dir() / "texture_preview_cache"
        pending_source = pending["source_path"] if pending else None
        relative_path = self.relative_path

        if game_dir is None:
            self.status_var.set(
                "No unpacked game folder set (General Setup) - can't preview the current texture, "
                "but Replace still works."
            )
            self.current_preview_label.configure(image="", text="(no game folder)")
            self.export_button.configure(state="disabled")
            self._load_pending_only(pending_source, token)
            return

        self.status_var.set("Loading preview...")
        full_path = game_dir / relative_path

        def worker() -> None:
            try:
                current_arr = td.load_game_texture_preview(full_path, cli_path, cache_dir)
                current_error = None
            except Exception as exc:  # noqa: BLE001
                current_arr = None
                current_error = str(exc)

            pending_arr = None
            pending_error = None
            if pending_source is not None:
                try:
                    pending_arr = td.load_replacement_preview(pending_source, cli_path, cache_dir)
                except Exception as exc:  # noqa: BLE001
                    pending_error = str(exc)

            self._queue.put(("preview_ready", (token, current_arr, current_error, pending_arr, pending_error)))

        threading.Thread(target=worker, daemon=True).start()

    def _load_pending_only(self, pending_source, token: int) -> None:
        # Reached when there's no unpacked game folder, so these have to be
        # looked up here rather than inherited from the caller's scope. The
        # CLI is still needed: a replacement recovered from an opened mod is
        # a .tex, and nothing else can decode one.
        cli_path = self.app.state_data.ff16tools_cli_path
        cache_dir = paths.local_data_dir() / "texture_preview_cache"
        pending_arr = None
        pending_error = None
        if pending_source is not None:
            try:
                pending_arr = td.load_replacement_preview(pending_source, cli_path, cache_dir)
            except Exception as exc:  # noqa: BLE001
                pending_error = str(exc)
        self._queue.put(("preview_ready", (token, None, None, pending_arr, pending_error)))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "preview_ready":
                    token, current_arr, current_error, pending_arr, pending_error = payload
                    if token == self._preview_token:
                        self._apply_preview(current_arr, current_error, pending_arr, pending_error)
        except queue.Empty:
            pass
        self.after(150, self._poll_queue)

    def _apply_preview(self, current_arr, current_error, pending_arr, pending_error) -> None:
        from PIL import Image, ImageTk

        self._current_full_arr = current_arr

        if current_arr is not None:
            img = Image.fromarray(current_arr, "RGBA")
            self.status_var.set(f"{img.width} \u00d7 {img.height} px")
            img.thumbnail(INLINE_PREVIEW_SIZE)
            self._current_photo = ImageTk.PhotoImage(img)
            self.current_preview_label.configure(image=self._current_photo, text="")
            self.export_button.configure(state="normal")
        elif current_error:
            self.status_var.set(current_error)
            self.current_preview_label.configure(image="", text="(unavailable)")
            self.export_button.configure(state="disabled")

        if pending_arr is not None:
            img2 = Image.fromarray(pending_arr, "RGBA")
            img2.thumbnail(INLINE_PREVIEW_SIZE)
            self._pending_photo = ImageTk.PhotoImage(img2)
            self.pending_preview_label.configure(image=self._pending_photo, text="")
        elif pending_error:
            self.pending_preview_label.configure(image="", text=f"(error: {pending_error})")
        else:
            self.pending_preview_label.configure(image="", text="(none staged)")

    # -- replace / clear ----------------------------------------------------

    def _on_replace_clicked(self) -> None:
        if self.relative_path is None:
            return
        chosen = filedialog.askopenfilename(
            title=f"Select a replacement image for {self.title}",
            filetypes=[
                ("Image files", " ".join(f"*{ext}" for ext in td.REPLACEMENT_IMAGE_EXTENSIONS)),
                ("All files", "*.*"),
            ],
        )
        if not chosen:
            return
        self.app.state_data.texture_edits[self.relative_path] = {
            "source_path": Path(chosen),
            "is_face_texture": td.is_face_texture(self.relative_path),
        }
        self.refresh()
        if self._on_edit_changed:
            self._on_edit_changed()

    def _on_clear_clicked(self) -> None:
        if self.relative_path is None:
            return
        self.app.state_data.texture_edits.pop(self.relative_path, None)
        self.refresh()
        if self._on_edit_changed:
            self._on_edit_changed()

    # -- export -----------------------------------------------------------

    def _on_export_clicked(self) -> None:
        if self.relative_path is None or self._current_full_arr is None:
            return
        default_name = Path(self.relative_path).stem + ".png"
        chosen = filedialog.asksaveasfilename(
            title="Export texture as PNG",
            initialfile=default_name,
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("All files", "*.*")],
        )
        if not chosen:
            return
        try:
            td.save_array_as_png(self._current_full_arr, Path(chosen))
            self.status_var.set(f"Exported to {chosen}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Export Failed", f"Couldn't export texture: {exc}")
