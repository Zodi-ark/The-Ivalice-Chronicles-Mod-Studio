"""
The "Jobs" tab within the combined Edit Jobs & Job Commands step (see
JobEditorStep at the bottom of this file), plus the field widgets it uses.

Two ideas drive the design:

1. The mod loader's diff format only writes fields the user explicitly
   *included* - not just fields that differ from vanilla (see the header
   comment in JobData.xml itself). So every field gets its own
   include/inherit checkbox, separate from its value widget. Editing a
   value auto-checks "include"; the user can also check/uncheck by hand.

2. Edits are committed to app.state_data.edits[job_id] immediately on every
   change (not just when switching jobs), so nothing is lost by navigating
   with Back/Next or by picking a different job mid-edit.
"""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk

from .. import ability_names
from .. import constants as c
from .. import ui_settings
from .. import item_xml_io
from .. import xml_io
from .app import WizardStepFrame


# -----------------------------------------------------------------------------
# Edit Game Data's two display toggles.
#
# Both have to work across every tab, and the widgets they affect are built
# by ~20 different row classes spread over a dozen modules. Rather than a
# registry each of those classes has to remember to call (and prune when
# widgets are destroyed), affected widgets are tagged with a ttk STYLE name
# that renders identically to the default. Styles are queryable at runtime,
# so hiding is a single tree walk with no bookkeeping and nothing to keep in
# sync - a row class that forgets the tag simply stays visible, which is the
# safe failure.
#
#   FieldNote.TLabel  - a field's explanatory note ("-1 = leave this
#                       equipment slot alone..."). Page intros are NOT
#                       tagged; hiding those would leave a tab unexplained.
#   UnknownRow.TFrame - a row for a field whose meaning isn't known, and
#                       the section frames that contain only such fields.
# -----------------------------------------------------------------------------
NOTE_STYLE = "FieldNote.TLabel"
UNKNOWN_ROW_STYLE = "UnknownRow.TFrame"
UNKNOWN_SECTION_STYLE = "UnknownRow.TLabelframe"


def install_field_display_styles(style: ttk.Style) -> None:
    """Makes the tag styles look exactly like the widgets they replace."""
    style.configure(NOTE_STYLE, foreground="#999999")
    style.configure(UNKNOWN_ROW_STYLE)
    style.configure(UNKNOWN_SECTION_STYLE)


def is_unknown_field(field_name: str, label: str = "") -> bool:
    """
    Whether a field's MEANING is unknown - which is not the same as its
    column being named Unknown-something.

    Judged on the label the user actually sees, falling back to the column
    name only when there's no label. Keying off the column name alone hid
    real fields: OverrideEntryData's unit name lives in a column called
    `Unknown4`, its primary job command in `EntryUnknown1D`, and its
    special-unit marker in `Unknown8E` - all confirmed, all labelled
    properly, and all wrongly hidden by a name-based test. Meanwhile
    `Unknown8F` is labelled "Unknown flag 8F" and should hide.

    The convention this relies on is deliberate: a field whose meaning
    isn't known keeps its offset as its label, because constants.py forbids
    inventing one.
    """
    text = (label or field_name or "").strip().lower()
    return text.startswith(("unknown", "unused"))


def apply_field_display(root, hide_notes: bool, hide_unknown: bool) -> None:
    """
    Shows or hides every tagged widget under `root`.

    pack_info() is captured before the first hide and stashed on the widget,
    so re-showing restores the exact position rather than appending the row
    to the end of its container.
    """
    def walk(widget):
        try:
            style_name = str(widget.cget("style"))
        except tk.TclError:
            style_name = ""
        if style_name == NOTE_STYLE:
            _set_packed(widget, not hide_notes)
        elif style_name in (UNKNOWN_ROW_STYLE, UNKNOWN_SECTION_STYLE):
            _set_packed(widget, not hide_unknown)
        for child in widget.winfo_children():
            walk(child)

    walk(root)


def _set_packed(widget, visible: bool) -> None:
    """
    Hide or restore one widget, keeping its place in the layout.

    Two things this has to get right:

    - Whether a widget is currently shown is `winfo_manager() == "pack"`,
      NOT `winfo_ismapped()`. A widget on an unselected notebook tab is
      packed but not mapped, and Edit Game Data builds all ten tabs up
      front - so keying off ismapped skipped nine tabs out of ten, and a
      toggle only appeared to work on whichever tab happened to be open.
    - pack() appends to the end of its container, so re-showing a note
      would drop it to the bottom of the section instead of back under its
      own field. The following sibling is recorded at hide time and used as
      a `before=` anchor on the way back.
    """
    if not widget.winfo_exists():
        return
    packed = widget.winfo_manager() == "pack"
    if visible:
        info = getattr(widget, "_fft_pack_info", None)
        if info is None or packed:
            return
        anchor = getattr(widget, "_fft_pack_before", None)
        try:
            if anchor is not None and anchor.winfo_exists() and anchor.winfo_manager() == "pack":
                widget.pack(**info, before=anchor)
            else:
                widget.pack(**info)
        except tk.TclError:
            pass
        return
    if not packed:
        return
    try:
        info = widget.pack_info()
        siblings = widget.master.pack_slaves()
        index = siblings.index(widget)
        widget._fft_pack_before = siblings[index + 1] if index + 1 < len(siblings) else None
        widget._fft_pack_info = {k: v for k, v in info.items() if k != "in"}
        widget.pack_forget()
    except (tk.TclError, ValueError):
        return


class ScrollableFrame(ttk.Frame):
    """
    A vertically-scrollable container. Put widgets in .inner.

    Two things here are not incidental, because getting them wrong produced
    the "empty white patches" seen all over the app:

    - A tk.Canvas defaults to a WHITE background, while every ttk widget
      around it uses the theme's grey. Any part of the canvas the inner
      frame didn't cover showed through as a white rectangle - most
      obviously under short content, like the area below Export's buttons.
      The canvas is themed, and the inner frame is stretched to at least
      the canvas height so it covers everything regardless.
    - When the scrollregion is SHORTER than the visible canvas, Tk will
      still happily slide it around, so scrolling over one of those blank
      areas dragged the content off-screen and left blank canvas above it.
      The wheel handler now refuses to scroll when everything already fits.
    """

    def __init__(self, parent):
        super().__init__(parent)
        background = ttk.Style().lookup("TFrame", "background") or None
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, background=background)
        vscroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=self.inner, anchor="nw")

        def _apply_geometry():
            self._resize_pending = False
            content = self.inner.winfo_reqheight()
            visible = canvas.winfo_height()
            # Width only. Forcing the frame's HEIGHT to fill the canvas was
            # tried and is subtly wrong: a frame pinned to a fixed height
            # stops firing <Configure> when its content grows, so the scroll
            # region froze at whatever it was and the last rows became
            # unreachable. Covering the spare canvas isn't needed anyway -
            # the canvas is themed, so bare canvas is indistinguishable from
            # the frame. Only the scroll region is stretched, which is what
            # stops Tk sliding a too-short region around inside the view.
            canvas.itemconfigure(window_id, width=canvas.winfo_width())
            canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), max(content, visible)))

        self._resize_pending = False

        def _resize(_event=None):
            # Deferred to idle rather than measured inline: a <Configure>
            # arrives while the layout is still settling, so reading
            # reqheight there left the scroll region short of the real
            # content and the last couple of rows unreachable.
            if self._resize_pending:
                return
            self._resize_pending = True
            self.after_idle(_apply_geometry)

        self.inner.bind("<Configure>", _resize)
        canvas.bind("<Configure>", _resize)
        canvas.configure(yscrollcommand=vscroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        # Only scroll-on-wheel while the pointer is actually over this
        # canvas, so multiple scrollable tabs don't fight each other.
        def _wheel(event):
            if self.inner.winfo_reqheight() <= canvas.winfo_height():
                return  # everything fits; scrolling here would just slide blank space
            delta = -1 * (event.delta // 120) if event.delta else (-1 if event.num == 4 else 1)
            canvas.yview_scroll(int(delta), "units")

        def _bind(_e):
            canvas.bind_all("<MouseWheel>", _wheel)
            canvas.bind_all("<Button-4>", _wheel)
            canvas.bind_all("<Button-5>", _wheel)

        def _unbind(_e):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind)
        canvas.bind("<Leave>", _unbind)
        self._canvas = canvas

    def scroll_by(self, units: int) -> None:
        """Scrolls the page, ignoring the request when everything fits."""
        if self.inner.winfo_reqheight() <= self._canvas.winfo_height():
            return
        self._canvas.yview_scroll(int(units), "units")


def wheel_units(event) -> int:
    """Wheel direction as scroll units, across Windows and X11 conventions."""
    if getattr(event, "delta", 0):
        return -1 * (event.delta // 120)
    return -1 if getattr(event, "num", 0) == 4 else 1


def bind_nested_scroll(widget, outer) -> None:
    """
    Makes the wheel behave the way people expect over a scrollable widget
    inside a scrolling page.

    The rule: the widget under the pointer scrolls until it reaches its
    limit, and only then does the page take over. Scrolling back up hands
    control back the same way.

    Without this the page won the wheel outright, because ScrollableFrame
    binds `<MouseWheel>` with `bind_all` - so you had to scroll the whole
    page to the bottom before an inner grid would move at all, which is
    exactly backwards from what the pointer position implies.

    Bound on the widget itself and returning "break", which is what makes
    it authoritative: Tk walks bindtags widget-class-toplevel-all, so a
    widget binding runs before the class binding that would scroll the grid
    a second time and before the `bind_all` that would scroll the page as
    well. Returning "break" stops both.
    """
    def handler(event):
        units = wheel_units(event)
        try:
            first, last = widget.yview()
        except (TypeError, ValueError, tk.TclError):
            outer.scroll_by(units)
            return "break"
        at_top = first <= 0.0
        at_bottom = last >= 1.0
        fits = at_top and at_bottom
        if fits or (units < 0 and at_top) or (units > 0 and at_bottom):
            outer.scroll_by(units)     # nothing left to give; pass it up
        else:
            widget.yview_scroll(units, "units")
        return "break"

    for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        widget.bind(sequence, handler)


def nxd_missing_data_message(state, feature: str, exc: Exception) -> str:
    """
    Plain-language explanation for "this tab's table isn't in the database
    that's loaded", with what to actually do about it.

    The raw exception ("No 'PoachItem-en' table in this database - was
    poachitem.en.nxd included when it was converted?") is accurate and
    useless to a basic user: it never says that opening a mod loads only
    the tables THAT MOD changes, so a mod which doesn't touch poaching
    simply has no poaching data to show - and that unpacking the game fixes
    it. Every tab that reads a .nxd table routes its read failures through
    here so they all say the same thing.
    """
    from_a_mod = (state.nxd_sqlite_source_detail or "").startswith("from the mod")
    lines = [f"{feature} isn't in the game data that's currently loaded."]
    if from_a_mod:
        lines.append(
            "You opened an existing mod, and a mod's own files only contain the tables it "
            "changes - so there's nothing here to edit yet."
        )
    lines.append(
        "To edit this, load the game's own data: go to General Setup, tick \u201cGame data\u201d, and "
        "press \u201cUnpack and Prepare Game Files\u201d. Anything you've already changed is kept."
    )
    lines.append(f"(Details: {exc})")
    return "\n\n".join(lines)


class CollapsibleSection(ttk.Frame):
    """
    A titled section that starts collapsed and builds its contents on first
    expand.

    Lazy building is the whole point, not an optimisation. Comparing two
    game versions produces fifty tables and thousands of rows - the real
    1.4.0-to-1.5.2 diff is 2,483 changed rows - and rendering all of that up
    front is both slow and useless, since a reader wants one table at a
    time. Collapsed sections cost a header each; expanding one pays only for
    that one.

    It also removes the inner scrollbars that made these lists unreadable.
    A fixed-height box with its own scrollbar, stacked fifty times inside a
    page that also scrolls, means two nested scroll regions fighting over
    the wheel and no way to see a long table in one go. An expanded section
    here is simply as tall as its content, and the page scrolls.

    `builder` is called once with the body frame, the first time the section
    is opened. Anything expensive belongs in there rather than in the
    caller.
    """

    ARROW_COLLAPSED = "\u25b8"      # ▸
    ARROW_EXPANDED = "\u25be"       # ▾

    def __init__(self, parent, title: str, subtitle: str = "", builder=None,
                 expanded: bool = False):
        super().__init__(parent)
        self._builder = builder
        self._built = False
        self._expanded = False

        self.header = ttk.Frame(self, padding=(6, 4))
        self.header.pack(fill="x")
        self._arrow_var = tk.StringVar(value=self.ARROW_COLLAPSED)
        self._title = title

        arrow = ttk.Label(self.header, textvariable=self._arrow_var, width=2)
        arrow.pack(side="left")
        title_label = ttk.Label(self.header, text=title, font=("Segoe UI", 10, "bold"))
        title_label.pack(side="left")
        self._subtitle_var = tk.StringVar(value=subtitle)
        subtitle_label = ttk.Label(self.header, textvariable=self._subtitle_var,
                                   foreground="#666666")
        subtitle_label.pack(side="left", padx=(10, 0))

        # The whole header row toggles, not just the arrow - a two-character
        # target is a poor thing to ask anyone to hit repeatedly.
        for widget in (self.header, arrow, title_label, subtitle_label):
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", self._toggle)

        self.body = ttk.Frame(self, padding=(20, 0, 4, 8))
        if expanded:
            self.expand()

    def set_subtitle(self, text: str) -> None:
        self._subtitle_var.set(text)

    def _toggle(self, _event=None) -> None:
        self.collapse() if self._expanded else self.expand()

    def expand(self) -> None:
        if self._expanded:
            return
        if not self._built:
            self._built = True
            if self._builder is not None:
                self._builder(self.body)
        self.body.pack(fill="x")
        self._arrow_var.set(self.ARROW_EXPANDED)
        self._expanded = True

    def collapse(self) -> None:
        if not self._expanded:
            return
        self.body.pack_forget()
        self._arrow_var.set(self.ARROW_COLLAPSED)
        self._expanded = False

    @property
    def is_expanded(self) -> bool:
        return self._expanded


class NumericFieldRow:
    """One row: [include checkbox] label [spinbox] help text."""

    def __init__(self, parent, field_name: str, on_user_edit):
        self.field_name = field_name
        self.min_v, self.max_v, self.label, self.help_text = c.NUMERIC_FIELDS[field_name]
        self._on_user_edit = on_user_edit
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)
        self.value_var = tk.StringVar(value="0")

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)

        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text=self.label, width=26, anchor="w").pack(side="left")

        vcmd = row.register(lambda p: p == "" or p.isdigit())
        spin = ttk.Spinbox(
            row, from_=self.min_v, to=self.max_v, textvariable=self.value_var,
            width=8, validate="key", validatecommand=(vcmd, "%P"),
        )
        spin.pack(side="left", padx=(4, 10))
        spin.bind("<FocusOut>", lambda e: self._clamp())
        self.value_var.trace_add("write", self._on_value_written)

        if self.help_text:
            ttk.Label(row, text=self.help_text, style=NOTE_STYLE, wraplength=340).pack(
                side="left"
            )

    def _clamp(self) -> None:
        try:
            v = int(self.value_var.get())
        except ValueError:
            v = self.min_v
        v = max(self.min_v, min(self.max_v, v))
        if str(v) != self.value_var.get():
            self._suppress = True
            self.value_var.set(str(v))
            self._suppress = False

    def _on_value_written(self, *_args) -> None:
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def load(self, value_str: str, included: bool) -> None:
        self._suppress = True
        try:
            v = max(self.min_v, min(self.max_v, int(value_str)))
        except (ValueError, TypeError):
            v = self.min_v
        self.value_var.set(str(v))
        self._suppress = False
        self.include_var.set(included)

    def get_value_str(self) -> str:
        try:
            v = int(self.value_var.get())
        except ValueError:
            v = self.min_v
        return str(max(self.min_v, min(self.max_v, v)))

    @property
    def included(self) -> bool:
        return self.include_var.get()


class XmlNumberRow:
    """
    [include] label [spinbox] help - a plain numeric item_xml_io.py field
    (string-valued, unlike NumericFieldRow above which looks bounds up from
    Job Data's own constants.NUMERIC_FIELDS by field name). Generalized to
    take bounds/label/help directly instead, so it's reusable for any
    item_xml_io.ALL_SPECS table - originally written for Items, now also
    used by Treasure Hunter, Equip Bonus, and Abilities' own Effect/Unit
    Animations sub-tabs. Lives here (not in step_items.py, where it was
    first written) specifically so step_abilities.py can import it too:
    step_items.py already imports Ability*Row widgets from step_abilities.py,
    so the reverse import would be circular - this module imports from
    neither, the same reason ScrollableFrame lives here.

    allow_negative widens the spinbox's keystroke validation to accept a
    leading "-" - off by default (every prior caller's fields are
    non-negative), needed for Ability Effect's EffectId, which is a real
    signed field (-1 is a genuine, commonly-used value, not an error case).

    name_lookup is an optional {id: name} mapping. When given, the resolved
    name is shown live beside the number ("342  -> Curaga"). It annotates
    rather than replaces: these fields legitimately hold values the name
    lists don't cover - EffectId runs past the end of the published list and
    -1 is used by 64 vanilla abilities - so a picker restricted to named ids
    would make real values unreachable.
    """

    def __init__(
        self, parent, field_name: str, min_v: int, max_v: int, label: str, help_text: str, on_user_edit,
        allow_negative: bool = False, name_lookup: dict | None = None,
    ):
        self.field_name = field_name
        self.min_v, self.max_v, self.help_text = min_v, max_v, help_text
        self._on_user_edit = on_user_edit
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)
        self.value_var = tk.StringVar(value=str(min_v))

        row = ttk.Frame(parent, style=UNKNOWN_ROW_STYLE if is_unknown_field(field_name, label) else "")
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text=label, width=24, anchor="w").pack(side="left")
        if allow_negative:
            vcmd = row.register(lambda p: re.fullmatch(r"-?\d*", p) is not None)
        else:
            vcmd = row.register(lambda p: p == "" or p.isdigit())
        spin = ttk.Spinbox(
            row, from_=min_v, to=max_v, textvariable=self.value_var,
            width=10, validate="key", validatecommand=(vcmd, "%P"),
        )
        spin.pack(side="left", padx=(4, 10))
        self._name_lookup = name_lookup
        self.name_var = tk.StringVar(value="")
        if name_lookup is not None:
            # Not tagged as a field note: this is the MEANING of the current
            # value, not an explanation of the field, so "Hide field notes"
            # leaves it alone.
            ttk.Label(row, textvariable=self.name_var, foreground="#0a4e8e").pack(side="left")
        spin.bind("<FocusOut>", lambda e: self._clamp())
        self.value_var.trace_add("write", self._on_value_written)
        if help_text:
            ttk.Label(parent, text=help_text, style=NOTE_STYLE, wraplength=600).pack(
                anchor="w", padx=(24, 0), pady=(0, 2)
            )

    def _clamp(self) -> None:
        try:
            v = int(self.value_var.get())
        except ValueError:
            v = self.min_v
        v = max(self.min_v, min(self.max_v, v))
        if str(v) != self.value_var.get():
            self._suppress = True
            self.value_var.set(str(v))
            self._suppress = False

    def _on_value_written(self, *_args) -> None:
        # The name follows the value even on a programmatic load, so it's
        # refreshed before the suppress check rather than after it.
        self._refresh_name()
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _refresh_name(self) -> None:
        if self._name_lookup is None:
            return
        from .. import reference_names
        self.name_var.set(reference_names.describe(self._name_lookup, self.value_var.get()))

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def load(self, value_str, included: bool) -> None:
        self._suppress = True
        try:
            v = max(self.min_v, min(self.max_v, int(value_str)))
        except (ValueError, TypeError):
            v = self.min_v
        self.value_var.set(str(v))
        self._suppress = False
        self.include_var.set(included)
        self._refresh_name()

    def get_value_str(self) -> str:
        try:
            v = int(self.value_var.get())
        except ValueError:
            v = self.min_v
        return str(max(self.min_v, min(self.max_v, v)))

    @property
    def included(self) -> bool:
        return self.include_var.get()


class XmlDropdownRow:
    """
    [include] label [combobox] - a single-select item_xml_io.py enum field
    (ItemCategory, ShopAvailability, AbilityData.xml's own AbilityType).

    Lives here (not step_items.py, where it was first written) for the same
    reason XmlNumberRow does above - step_abilities.py needs it too (for
    AbilityData.xml's AbilityType field), and step_items.py already imports
    Ability*Row widgets from step_abilities.py, so the reverse import would
    be circular.
    """

    def __init__(self, parent, field_name: str, choices: list, label: str, on_user_edit, width: int = 26):
        self.field_name = field_name
        self.choices = choices
        self._on_user_edit = on_user_edit
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)
        self.value_var = tk.StringVar(value=choices[0])

        row = ttk.Frame(parent, style=UNKNOWN_ROW_STYLE if is_unknown_field(field_name, label) else "")
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text=label, width=24, anchor="w").pack(side="left")
        self.combo = ttk.Combobox(
            row, textvariable=self.value_var, values=choices, state="readonly", width=width
        )
        self.combo.pack(side="left", padx=(4, 10))
        self.combo.bind("<<ComboboxSelected>>", self._on_selected)

    def _on_selected(self, _event=None) -> None:
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def load(self, value_str, included: bool) -> None:
        self._suppress = True
        value = value_str if value_str in self.choices else self.choices[0]
        self.value_var.set(value)
        self._suppress = False
        self.include_var.set(included)

    def get_value_str(self) -> str:
        return self.value_var.get()

    @property
    def included(self) -> bool:
        return self.include_var.get()


class ItemFlagFieldPanel:
    """
    Header [include] Label [All] [None], then grouped checkboxes below.

    Generalized version of FlagFieldPanel above for item_xml_io's flag
    fields (plain comma-separated [Flags] enums, same xml_io.parse_flag_value/
    format_flag_value semantics Job Data uses) - takes its label/choices/
    groups directly rather than looking them up from Job Data's own
    constants.FLAG_FIELDS. Lives here (not step_items.py, where it was first
    written) for the same reason XmlNumberRow/XmlDropdownRow do - Abilities'
    own AbilityData.xml sub-tab needs it too (Flags/AIBehaviorFlags), and the
    reverse import from step_items.py would be circular.
    """

    def __init__(self, parent, field_name: str, label: str, groups: dict, on_user_edit, columns: int = 4):
        self.field_name = field_name
        self._on_user_edit = on_user_edit
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)
        self.check_vars: dict = {}

        header = ttk.Frame(parent)
        header.pack(fill="x", pady=(10, 2))
        ttk.Checkbutton(header, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(header, text=label, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(2, 12))
        ttk.Button(header, text="All", width=4, command=self._select_all).pack(side="left")
        ttk.Button(header, text="None", width=5, command=self._select_none).pack(side="left", padx=(4, 0))

        body = ttk.Frame(parent)
        body.pack(fill="x")
        for i, (group_name, flags) in enumerate(groups.items()):
            group_frame = ttk.LabelFrame(body, text=group_name, padding=6)
            group_frame.grid(row=i // columns, column=i % columns, padx=4, pady=4, sticky="n")
            for flag_name in flags:
                var = tk.BooleanVar(value=False)
                self.check_vars[flag_name] = var
                ttk.Checkbutton(
                    group_frame, text=flag_name, variable=var, command=self._fire_checkbox_edit
                ).pack(anchor="w")

    def _fire_checkbox_edit(self) -> None:
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def _select_all(self) -> None:
        self._suppress = True
        for v in self.check_vars.values():
            v.set(True)
        self._suppress = False
        self.include_var.set(True)
        self._fire_edit()

    def _select_none(self) -> None:
        self._suppress = True
        for v in self.check_vars.values():
            v.set(False)
        self._suppress = False
        self.include_var.set(True)
        self._fire_edit()

    def load(self, value_str, included: bool) -> None:
        self._suppress = True
        flags = item_xml_io.parse_flag_value(value_str)
        for name, var in self.check_vars.items():
            var.set(name in flags)
        self._suppress = False
        self.include_var.set(included)

    def get_value_str(self) -> str:
        flags = {name for name, var in self.check_vars.items() if var.get()}
        return item_xml_io.format_flag_value(flags)

    @property
    def included(self) -> bool:
        return self.include_var.get()


class AbilityDropdownRow:
    """
    One row: [include checkbox] label [ability name dropdown].

    Only FFTPatcher's documented Innate-capable abilities (decimal 454-485)
    plus the monster/movement traits actually observed in vanilla job data
    are offered - see constants.INNATE_ABILITY_CHOICES for where that list
    comes from. Any other value already present in loaded data (shouldn't
    normally happen, but data can come from hand-edited mods) is added on
    the fly rather than silently dropped or misrepresented.
    """

    def __init__(self, parent, field_name: str, on_user_edit):
        self.field_name = field_name
        self.label = c.ABILITY_FIELD_LABELS[field_name]
        self._on_user_edit = on_user_edit
        self._suppress = False

        self._id_to_display: dict[int, str] = {}
        self._display_to_id: dict[str, int] = {}
        self._choices: list[int] = []
        for ability_id, name in c.INNATE_ABILITY_CHOICES:
            self._register_choice(ability_id, name)

        self.include_var = tk.BooleanVar(value=False)
        self.display_var = tk.StringVar(value=self._id_to_display[0])

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text=self.label, width=16, anchor="w").pack(side="left")
        self.combo = ttk.Combobox(
            row, textvariable=self.display_var, values=self._display_values(),
            state="readonly", width=34,
        )
        self.combo.pack(side="left", padx=(4, 10))
        self.combo.bind("<<ComboboxSelected>>", self._on_selected)

    def _register_choice(self, ability_id: int, name: str) -> None:
        display = name if ability_id == 0 else f"{name} ({ability_id})"
        self._id_to_display[ability_id] = display
        self._display_to_id[display] = ability_id
        self._choices.append(ability_id)

    def _display_values(self) -> list[str]:
        return [self._id_to_display[i] for i in self._choices]

    def _on_selected(self, _event=None) -> None:
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def load(self, value_str: str, included: bool) -> None:
        self._suppress = True
        try:
            ability_id = int(value_str)
        except (ValueError, TypeError):
            ability_id = 0
        if ability_id not in self._id_to_display:
            # Not one of our known choices - show it honestly instead of
            # silently renaming or discarding whatever was actually there.
            self._register_choice(ability_id, f"(Unrecognized Ability {ability_id})")
            self.combo.configure(values=self._display_values())
        self.display_var.set(self._id_to_display[ability_id])
        self._suppress = False
        self.include_var.set(included)

    def get_value_str(self) -> str:
        return str(self._display_to_id.get(self.display_var.get(), 0))

    @property
    def included(self) -> bool:
        return self.include_var.get()


class JobCommandDropdownRow:
    """
    One row: [include checkbox] "Job Command (skillset)" [dropdown], plus a
    read-only preview underneath listing the abilities that skillset
    actually grants.

    Unlike the other dropdown/flag widgets, its choices come from
    app.state_data.job_command_records - data fetched live in Step 1, not
    known yet when the editor's tabs are first built. refresh_choices()
    must be called (see EditorStep.on_show) whenever that data changes.
    """

    def __init__(self, parent, on_user_edit, on_go_to_command=None):
        self.field_name = "JobCommandId"
        self._on_user_edit = on_user_edit
        self._on_go_to_command = on_go_to_command
        self._suppress = False
        self._current_id = 0
        self._records_by_id: dict = {}
        self._ability_names_live: dict = {}

        self._id_to_display: dict[int, str] = {}
        self._display_to_id: dict[str, int] = {}
        self._choices: list[int] = []
        self._register_choice(0, "(None / Unset)")

        self.include_var = tk.BooleanVar(value=False)
        self.display_var = tk.StringVar(value=self._id_to_display[0])

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text="Job Command (skillset)", width=22, anchor="w").pack(side="left")
        self.combo = ttk.Combobox(
            row, textvariable=self.display_var, values=self._display_values(),
            state="readonly", width=40,
        )
        self.combo.pack(side="left", padx=(4, 10))
        self.combo.bind("<<ComboboxSelected>>", self._on_selected)
        self.goto_button = ttk.Button(
            row, text="Edit this Job Command \u2192", command=self._go_to_command, state="disabled"
        )
        self.goto_button.pack(side="left", padx=(4, 0))

        self.preview_var = tk.StringVar(value="")
        ttk.Label(
            parent, textvariable=self.preview_var, foreground="#555555",
            wraplength=700, justify="left",
        ).pack(anchor="w", pady=(2, 12))

    def _go_to_command(self) -> None:
        if self._on_go_to_command and self._current_id:
            self._on_go_to_command(self._current_id)

    def _register_choice(self, command_id: int, name: str) -> None:
        display = name if command_id == 0 else f"{command_id:03d} - {name}"
        self._id_to_display[command_id] = display
        self._display_to_id[display] = command_id
        self._choices.append(command_id)

    def _display_values(self) -> list[str]:
        return [self._id_to_display[i] for i in self._choices]

    def refresh_choices(self, records: list, ability_names_live: dict) -> None:
        """Call whenever app.state_data.job_command_records is replaced (Step 1 fetch)."""
        self._records_by_id = {r.command_id: r for r in records}
        self._ability_names_live = ability_names_live

        self._id_to_display = {}
        self._display_to_id = {}
        self._choices = []
        self._register_choice(0, "(None / Unset)")
        for record in records:
            self._register_choice(record.command_id, record.name or "(unnamed command)")
        if self._current_id not in self._id_to_display:
            self._register_choice(self._current_id, "(unrecognized command)")

        self.combo.configure(values=self._display_values())
        self.display_var.set(self._id_to_display[self._current_id])
        self._update_preview()

    def _on_selected(self, _event=None) -> None:
        self._current_id = self._display_to_id.get(self.display_var.get(), 0)
        if self._suppress:
            return
        self.include_var.set(True)
        self._update_preview()
        self._fire_edit()

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def _update_preview(self) -> None:
        self.goto_button.configure(state="normal" if self._current_id else "disabled")
        record = self._records_by_id.get(self._current_id)
        if record is None:
            self.preview_var.set("")
            return
        abilities = [i for i in record.ability_ids if i != 0]
        rsm = [i for i in record.rsm_ids if i != 0]
        parts = []
        if abilities:
            names = ability_names.resolve_ability_names(abilities, self._ability_names_live)
            parts.append("Menu abilities: " + ", ".join(names))
        if rsm:
            names = ability_names.resolve_ability_names(rsm, self._ability_names_live)
            parts.append("Reaction/Support/Movement unlocked: " + ", ".join(names))
        self.preview_var.set("\n".join(parts) if parts else "(This skillset has no abilities assigned.)")

    def load(self, value_str: str, included: bool) -> None:
        self._suppress = True
        try:
            command_id = int(value_str)
        except (ValueError, TypeError):
            command_id = 0
        self._current_id = command_id
        if command_id not in self._id_to_display:
            self._register_choice(command_id, "(unrecognized command)")
            self.combo.configure(values=self._display_values())
        self.display_var.set(self._id_to_display[command_id])
        self._suppress = False
        self.include_var.set(included)
        self._update_preview()

    def get_value_str(self) -> str:
        return str(self._current_id)

    @property
    def included(self) -> bool:
        return self.include_var.get()


class FlagFieldPanel:
    """Header [include] Label [All] [None], then grouped checkboxes below."""

    def __init__(self, parent, field_name: str, on_user_edit, columns: int = 4):
        self.field_name = field_name
        choices, label = c.FLAG_FIELDS[field_name]
        groups = self._groups_for(field_name, choices)
        self._on_user_edit = on_user_edit
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)
        self.check_vars: dict[str, tk.BooleanVar] = {}

        header = ttk.Frame(parent)
        header.pack(fill="x", pady=(14, 2))
        ttk.Checkbutton(header, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(header, text=label, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(2, 12))
        ttk.Button(header, text="All", width=4, command=self._select_all).pack(side="left")
        ttk.Button(header, text="None", width=5, command=self._select_none).pack(side="left", padx=(4, 0))

        body = ttk.Frame(parent)
        body.pack(fill="x")
        for i, (group_name, flags) in enumerate(groups.items()):
            group_frame = ttk.LabelFrame(body, text=group_name, padding=6)
            group_frame.grid(row=i // columns, column=i % columns, padx=4, pady=4, sticky="n")
            for flag in flags:
                var = tk.BooleanVar(value=False)
                self.check_vars[flag] = var
                ttk.Checkbutton(
                    group_frame, text=flag, variable=var, command=self._fire_checkbox_edit
                ).pack(anchor="w")

    @staticmethod
    def _groups_for(field_name: str, choices: list[str]) -> dict:
        if field_name == "EquippableItems":
            return c.EQUIP_GROUPS
        if field_name in ("InnateStatus", "ImmuneStatus", "StartingStatus"):
            return c.STATUS_GROUPS
        return {"Elements": choices}

    def _fire_checkbox_edit(self) -> None:
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def _select_all(self) -> None:
        self._suppress = True
        for v in self.check_vars.values():
            v.set(True)
        self._suppress = False
        self.include_var.set(True)
        self._fire_edit()

    def _select_none(self) -> None:
        self._suppress = True
        for v in self.check_vars.values():
            v.set(False)
        self._suppress = False
        self.include_var.set(True)
        self._fire_edit()

    def load(self, value_str: str, included: bool) -> None:
        self._suppress = True
        flags = xml_io.parse_flag_value(value_str)
        for name, var in self.check_vars.items():
            var.set(name in flags)
        self._suppress = False
        self.include_var.set(included)

    def get_value_str(self) -> str:
        flags = {name for name, var in self.check_vars.items() if var.get()}
        return xml_io.format_flag_value(flags)

    @property
    def included(self) -> bool:
        return self.include_var.get()


class JobsPanel(ttk.Frame):
    """The 'Jobs' tab within the combined Edit Jobs & Job Commands step."""

    def __init__(self, parent, app, on_go_to_job_command=None):
        super().__init__(parent)
        self.app = app
        self._on_go_to_job_command = on_go_to_job_command
        self.current_job_id: int | None = None
        self.fields: dict[str, object] = {}  # field_name -> NumericFieldRow | FlagFieldPanel
        self._loading = False  # guard against commit-while-loading
        self._applied_job_command_records: list | None = None

        self._build_layout()

    # -- layout ---------------------------------------------------------

    def _build_layout(self) -> None:
        ttk.Label(
            self,
            style="SubHeader.TLabel",
            wraplength=760,
            justify="left",
            text=(
                "Pick a job on the left, then edit it on the right. Only the fields you "
                "check the box next to will be written into your mod - everything else is "
                "left alone so it won't conflict with other mods."
            ),
        ).pack(anchor="w", pady=(4, 12))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        # --- left: job picker ---
        left = ttk.Frame(body, width=260)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        self.changes_var = tk.StringVar(value="0 of 176 jobs have pending edits")
        ttk.Label(left, textvariable=self.changes_var, foreground="#0a6e0a").pack(
            anchor="w", pady=(0, 6)
        )

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(left, textvariable=self.search_var)
        search_entry.pack(fill="x", pady=(0, 6))
        search_entry.insert(0, "")
        self.search_var.trace_add("write", lambda *_a: self._refresh_job_list())
        ttk.Label(left, text="Search by name or ID", foreground="#888888").pack(anchor="w")

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.job_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.job_tree.yview)
        self.job_tree.configure(yscrollcommand=tree_scroll.set)
        self.job_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.job_tree.tag_configure("edited", background=c.EDITED_ROW_BG, foreground=c.EDITED_ROW_FG)
        self.job_tree.tag_configure("no_ref", foreground="#999999")
        self.job_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # --- right: current job + tabs ---
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.current_job_var = tk.StringVar(value="No job selected")
        ttk.Label(right, textvariable=self.current_job_var, font=("Segoe UI", 12, "bold")).pack(
            anchor="w", pady=(0, 2)
        )
        self.no_ref_warning_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.no_ref_warning_var, foreground="#b06000").pack(anchor="w")

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True, pady=(8, 0))

        self._build_basic_stats_tab()
        self._build_equipment_tab()
        self._build_abilities_tab()
        self._build_status_tab()
        self._build_elements_tab()
        self._build_monster_tab()

    def _add_scrollable_tab(self, title: str) -> ttk.Frame:
        scroll = ScrollableFrame(self.notebook)
        self.notebook.add(scroll, text=title)
        return scroll.inner

    def _build_basic_stats_tab(self) -> None:
        tab = self._add_scrollable_tab("Basic Stats")
        self.fields["JobCommandId"] = JobCommandDropdownRow(
            tab, self._on_field_edited, on_go_to_command=self._on_go_to_job_command
        )
        basic_names = [
            "HPGrowth", "HPMultiplier", "MPGrowth", "MPMultiplier",
            "SpeedGrowth", "SpeedMultiplier", "PAGrowth", "PAMultiplier",
            "MAGrowth", "MAMultiplier", "Move", "Jump", "CharacterEvasion",
        ]
        for name in basic_names:
            self.fields[name] = NumericFieldRow(tab, name, self._on_field_edited)

    def _build_equipment_tab(self) -> None:
        tab = self._add_scrollable_tab("Equipment")
        self.fields["EquippableItems"] = FlagFieldPanel(
            tab, "EquippableItems", self._on_field_edited, columns=4
        )

    def _build_abilities_tab(self) -> None:
        tab = self._add_scrollable_tab("Abilities")
        ttk.Label(
            tab,
            wraplength=700,
            justify="left",
            foreground="#777777",
            text=(
                "Only abilities that actually function as Innate Abilities are listed "
                "(FFTPatcher's Support Abilities, decimal 454-485), plus the movement/monster "
                "traits already used by some monster jobs in the vanilla data."
            ),
        ).pack(anchor="w", pady=(0, 8))
        for name in c.ABILITY_FIELD_NAMES:
            self.fields[name] = AbilityDropdownRow(tab, name, self._on_field_edited)

    def _build_status_tab(self) -> None:
        tab = self._add_scrollable_tab("Status Effects")
        for name in ["InnateStatus", "ImmuneStatus", "StartingStatus"]:
            self.fields[name] = FlagFieldPanel(tab, name, self._on_field_edited, columns=5)

    def _build_elements_tab(self) -> None:
        tab = self._add_scrollable_tab("Elements")
        for name in ["AbsorbElements", "NullifyElements", "HalveElements", "WeakElements"]:
            self.fields[name] = FlagFieldPanel(tab, name, self._on_field_edited, columns=1)

    def _build_monster_tab(self) -> None:
        tab = self._add_scrollable_tab("Monster Graphics")
        ttk.Label(
            tab,
            wraplength=700,
            justify="left",
            style=NOTE_STYLE,
            text="Only relevant for monster-type jobs.",
        ).pack(anchor="w", pady=(0, 8))
        for name in ["MonsterPortrait", "MonsterPalette", "MonsterGraphic"]:
            self.fields[name] = NumericFieldRow(tab, name, self._on_field_edited)

    # -- job list -----------------------------------------------------------

    def _refresh_job_list(self) -> None:
        query = self.search_var.get().strip().lower()
        self.job_tree.delete(*self.job_tree.get_children())
        for record in self.app.state_data.job_records:
            if query and query not in record.display_name.lower() and query != str(record.job_id):
                continue
            tags = []
            if record.job_id in self.app.state_data.edits and self.app.state_data.edits[record.job_id]:
                tags.append("edited")
            elif not record.has_reference_data:
                tags.append("no_ref")
            self.job_tree.insert("", "end", iid=str(record.job_id), text=record.display_name, tags=tags)
        self._update_changes_label()

    def _update_changes_label(self) -> None:
        count = self.app.state_data.edited_job_count()
        total = len(self.app.state_data.job_records) or c.TOTAL_JOB_SLOTS
        self.changes_var.set(f"{count} of {total} jobs have pending edits")

    def _on_tree_select(self, _event=None) -> None:
        selection = self.job_tree.selection()
        if not selection:
            return
        self._load_job(int(selection[0]))

    # -- loading / committing -------------------------------------------------

    def _load_job(self, job_id: int) -> None:
        self._loading = True
        self.current_job_id = job_id
        record = self.app.state_data.records_by_id().get(job_id)
        if record is None:
            self._loading = False
            return

        self.current_job_var.set(f"Editing: {record.display_name}")
        self.no_ref_warning_var.set(
            "This slot has no reference data in the table - editing it defines brand "
            "new values rather than overriding known ones."
            if not record.has_reference_data
            else ""
        )

        edits_for_job = self.app.state_data.edits.get(job_id, {})
        for field_name, widget in self.fields.items():
            if field_name in edits_for_job:
                widget.load(edits_for_job[field_name], True)
            else:
                widget.load(record.values.get(field_name, ""), False)

        self._loading = False

    def _on_field_edited(self) -> None:
        if self._loading or self.current_job_id is None:
            return
        job_id = self.current_job_id
        edits = self.app.state_data.edits.setdefault(job_id, {})
        for field_name, widget in self.fields.items():
            if widget.included:
                edits[field_name] = widget.get_value_str()
            elif field_name in edits:
                del edits[field_name]
        if not edits:
            self.app.state_data.edits.pop(job_id, None)

        # Reflect the change in the job list (edited marker) without losing
        # scroll position / selection, and update the running counter.
        tags = []
        if job_id in self.app.state_data.edits and self.app.state_data.edits[job_id]:
            tags = ["edited"]
        else:
            record = self.app.state_data.records_by_id().get(job_id)
            if record and not record.has_reference_data:
                tags = ["no_ref"]
        if self.job_tree.exists(str(job_id)):
            self.job_tree.item(str(job_id), tags=tags)
        self._update_changes_label()

    # -- called by the combined step's on_show() -----------------------------

    def on_show(self) -> None:
        if self.app.state_data.job_command_records is not self._applied_job_command_records:
            self._applied_job_command_records = self.app.state_data.job_command_records
            self.fields["JobCommandId"].refresh_choices(
                self.app.state_data.job_command_records, self.app.state_data.ability_names
            )
        self._refresh_job_list()
        if self.current_job_id is None and self.app.state_data.job_records:
            first_id = str(self.app.state_data.job_records[0].job_id)
            if self.job_tree.exists(first_id):
                self.job_tree.selection_set(first_id)


class JobEditorStep(WizardStepFrame):
    """
    Combined step: Jobs, Job Commands, Abilities, Items, Equip Bonus,
    Poaching, Treasure Hunter, and Encounters as top-level tabs, mirroring
    FFTPatcher's own Jobs/Skill Sets/Abilities/Items split (Skill Sets =
    Job Command here), extended with three more tabs for the same two
    abilities' own data plus Items' own Equip Bonus system. Equip Bonus
    sits right after Items - the same "parent tab, then its own detail
    tab right beside it" relationship Job Commands already has with Jobs.
    """

    def __init__(self, parent, app):
        super().__init__(parent, app)

        # Deferred import: step_job_commands/step_abilities/step_items/
        # step_equip_bonus/step_treasure_hunter import ScrollableFrame from
        # this module, so importing them back at module load time would be
        # circular. By the time this __init__ runs, every module below is
        # already fully loaded.
        from .step_job_commands import JobCommandsPanel
        from .step_abilities import AbilitiesPanel
        from .step_items import ItemsPanel
        from .step_equip_bonus import EquipBonusPanel
        from .step_poaching import PoachingPanel
        from .step_treasure_hunter import TreasureHunterPanel
        from .step_encounters import EncountersPanel
        from .step_textures import TexturesPanel
        from .step_sounds import SoundsPanel

        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="Edit Game Data", style="Header.TLabel").pack(side="left", anchor="w")

        # Two view toggles, deliberately at step level rather than per tab:
        # they change how every tab below is displayed, so a per-tab copy
        # would just be the same switch in ten places.
        toggles = ttk.Frame(header)
        toggles.pack(side="right", anchor="e")
        saved = ui_settings.load()
        self.hide_notes_var = tk.BooleanVar(value=saved["hide_field_notes"])
        ttk.Checkbutton(
            toggles, text="Hide field notes", variable=self.hide_notes_var,
            command=self._apply_display_options,
        ).pack(side="left", padx=(0, 12))
        self.hide_unknown_var = tk.BooleanVar(value=saved["hide_unknown_fields"])
        ttk.Checkbutton(
            toggles, text="Hide unknown fields", variable=self.hide_unknown_var,
            command=self._apply_display_options,
        ).pack(side="left")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, pady=(8, 0))

        self.jobs_panel = JobsPanel(self.notebook, app, on_go_to_job_command=self._go_to_job_command)
        self.notebook.add(self.jobs_panel, text="Jobs")

        self.commands_panel = JobCommandsPanel(self.notebook, app, on_go_to_ability=self._go_to_ability)
        self.notebook.add(self.commands_panel, text="Job Commands")

        self.abilities_panel = AbilitiesPanel(self.notebook, app, on_go_to_textures=self._go_to_textures_tab)
        self.notebook.add(self.abilities_panel, text="Abilities")

        self.items_panel = ItemsPanel(
            self.notebook, app,
            on_go_to_equip_bonus=self._go_to_equip_bonus, on_go_to_textures=self._go_to_textures_tab,
        )
        self.notebook.add(self.items_panel, text="Items")

        self.equip_bonus_panel = EquipBonusPanel(self.notebook, app, on_go_to_item=self._go_to_item)
        self.notebook.add(self.equip_bonus_panel, text="Equip Bonus")

        self.poaching_panel = PoachingPanel(self.notebook, app)
        self.notebook.add(self.poaching_panel, text="Poaching")

        self.treasure_hunter_panel = TreasureHunterPanel(self.notebook, app)
        self.notebook.add(self.treasure_hunter_panel, text="Treasure Hunter")

        self.encounters_panel = EncountersPanel(self.notebook, app)
        self.notebook.add(self.encounters_panel, text="Encounters")

        self.textures_panel = TexturesPanel(self.notebook, app)
        self.notebook.add(self.textures_panel, text="Textures")

        self.sounds_panel = SoundsPanel(self.notebook, app)
        self.notebook.add(self.sounds_panel, text="Sounds")

    def _go_to_job_command(self, command_id: int) -> None:
        self.notebook.select(1)
        self.commands_panel.search_var.set("")  # clear any filter so the target is guaranteed visible
        command_id_str = str(command_id)
        if self.commands_panel.command_tree.exists(command_id_str):
            self.commands_panel.command_tree.selection_set(command_id_str)
            self.commands_panel.command_tree.see(command_id_str)

    def _go_to_equip_bonus(self, equip_bonus_id: int) -> None:
        self.notebook.select(self.equip_bonus_panel)
        self.equip_bonus_panel.search_var.set("")  # clear any filter so the target is guaranteed visible
        equip_bonus_id_str = str(equip_bonus_id)
        if self.equip_bonus_panel.bonus_tree.exists(equip_bonus_id_str):
            self.equip_bonus_panel.bonus_tree.selection_set(equip_bonus_id_str)
            self.equip_bonus_panel.bonus_tree.see(equip_bonus_id_str)

    def _go_to_item(self, item_id: int) -> None:
        """
        Equip Bonus -> Items. The mirror of _go_to_equip_bonus, which
        already goes the other way, so the two tabs link both directions.
        """
        self.notebook.select(self.items_panel)
        self.items_panel.search_var.set("")  # clear any filter so the target is guaranteed visible
        item_id_str = str(item_id)
        if self.items_panel.item_tree.exists(item_id_str):
            self.items_panel.item_tree.selection_set(item_id_str)
            self.items_panel.item_tree.see(item_id_str)

    def _go_to_ability(self, ability_id: int) -> None:
        self.notebook.select(self.abilities_panel)
        self.abilities_panel.search_var.set("")  # clear any filter so the target is guaranteed visible
        ability_id_str = str(ability_id)
        if self.abilities_panel.ability_tree.exists(ability_id_str):
            self.abilities_panel.ability_tree.selection_set(ability_id_str)
            self.abilities_panel.ability_tree.see(ability_id_str)

    def _go_to_textures_tab(self, relative_path: str) -> None:
        self.notebook.select(self.textures_panel)
        self.textures_panel.select_relative_path(relative_path)

    def _apply_display_options(self) -> None:
        hide_notes = self.hide_notes_var.get()
        hide_unknown = self.hide_unknown_var.get()
        apply_field_display(self.notebook, hide_notes=hide_notes, hide_unknown=hide_unknown)
        # Saved on every change rather than at exit: the app has no single
        # shutdown path (window close, Alt+F4, a crash), and a preference
        # that only survives a graceful quit isn't much of a preference.
        ui_settings.save(hide_field_notes=hide_notes, hide_unknown_fields=hide_unknown)

    def on_show(self) -> None:
        self.jobs_panel.on_show()
        self.commands_panel.on_show()
        self.abilities_panel.on_show()
        self.items_panel.on_show()
        self.equip_bonus_panel.on_show()
        self.poaching_panel.on_show()
        self.treasure_hunter_panel.on_show()
        self.encounters_panel.on_show()
        self.textures_panel.on_show()
        self.sounds_panel.on_show()
        # Panels rebuild rows in their own on_show, so anything hidden has
        # to be hidden again afterwards or the toggles silently lapse.
        self._apply_display_options()

