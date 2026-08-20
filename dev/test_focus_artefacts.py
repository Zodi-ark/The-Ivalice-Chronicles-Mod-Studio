import sys, tempfile
from pathlib import Path
# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp())
from fft_job_editor import paths
paths.local_data_dir = lambda: TMP
import tkinter as tk
from tkinter import ttk
from fft_job_editor.gui import app as app_mod

passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {label}")
    else: failed += 1; print(f"  FAIL  {label}  ({detail})")

w = app_mod.WizardApp()
s = ttk.Style(w)
fieldbg = s.lookup("TCombobox", "fieldbackground", ["readonly"])
# The actual defect: clam fills the whole field blue for readonly+focus.
focus_fill = s.lookup("TCombobox", "fieldbackground", ["readonly", "focus"])
check("a focused readonly combobox no longer fills blue",
      focus_fill == fieldbg, (focus_fill, fieldbg))
check("and it is not clam's selection blue", focus_fill != "#4a6984", focus_fill)
check("no selection highlight either",
      s.lookup("TCombobox", "selectbackground", ["readonly"]) == fieldbg)
check("its text keeps the normal colour",
      s.lookup("TCombobox", "selectforeground", ["readonly"])
      == s.lookup("TCombobox", "foreground", ["readonly"]))

for i, title in enumerate(app_mod.ALL_PAGE_TITLES):
    w._show_step(i)
    w.update()
    focused = w.focus_get()
    check(f"{title}: focus parks on the page, not a widget",
          focused is None or isinstance(focused, (ttk.Frame, tk.Frame, app_mod.WizardApp))
          or focused is w.step_frames[i],
          type(focused).__name__)

# Sub-tab switching inside Edit Game Data must behave the same.
editor = w.step_frames[1]
nb = editor.notebook
for tab in nb.tabs()[:4]:
    nb.select(tab)
    w.update(); w.update_idletasks()
    focused = w.focus_get()
    check(f"sub-tab {nb.tab(tab,'text')}: nothing grabs focus",
          not isinstance(focused, (ttk.Combobox, ttk.Button, ttk.Entry)),
          type(focused).__name__)

# The dashed ring after a mouse click. Focus used to be parked on the
# toplevel, which leaves the window's internal focus where it was, so the
# button kept its ring - and a button disabled by its own command handler
# was skipped entirely, so the ring stayed for the whole operation.
holder = ttk.Frame(w); holder.pack()
btn = ttk.Button(holder, text="Do the thing", command=lambda: None)
btn.pack()
w.update()
btn.focus_set(); w.update()
check("a button can still take focus by keyboard", w.focus_get() is btn, w.focus_get())

btn.event_generate("<ButtonPress-1>"); btn.event_generate("<ButtonRelease-1>")
w.update(); w.update_idletasks(); w.update()
check("but a mouse click leaves it again", w.focus_get() is not btn, w.focus_get())
check("landing on a frame, which draws no ring",
      isinstance(w.focus_get(), (ttk.Frame, tk.Frame, app_mod.WizardApp)),
      type(w.focus_get()).__name__)

def disable_self():
    self_disabling.configure(state="disabled")
self_disabling = ttk.Button(holder, text="Disables itself", command=disable_self)
self_disabling.pack(); w.update()
self_disabling.focus_set(); w.update()
disable_self()
self_disabling.event_generate("<ButtonRelease-1>")
w.update(); w.update_idletasks(); w.update()
check("a button that disables itself still gives up focus",
      w.focus_get() is not self_disabling, w.focus_get())

self_disabling.configure(state="normal"); self_disabling.focus_set(); w.update()
w.park_focus(self_disabling); w.update()
check("park_focus is available to pages that disable a button themselves",
      w.focus_get() is not self_disabling, w.focus_get())

w.destroy()
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
