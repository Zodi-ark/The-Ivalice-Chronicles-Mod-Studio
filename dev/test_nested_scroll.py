"""Wheel behaviour where a scrollable grid sits inside a scrolling page.

The rule: the widget under the pointer scrolls until it runs out, and only
then does the page take over. Tested on a real ScrollableFrame with a real
Treeview rather than through the Game Updates page, because the mechanism is
in ScrollableFrame and a page layout adds nothing but ways for the widget to
be unmapped.
"""
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
from fft_job_editor.gui import step_editor

passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {label}")
    else: failed += 1; print(f"  FAIL  {label}  ({detail})")

root = tk.Tk()
root.geometry("700x400")
outer = step_editor.ScrollableFrame(root)
outer.pack(fill="both", expand=True)

# Enough filler above the grid that the page itself has somewhere to scroll.
for i in range(30):
    ttk.Label(outer.inner, text=f"filler row {i}").pack(anchor="w")

tree = ttk.Treeview(outer.inner, columns=["a"], show="headings", height=8)
for i in range(200):
    tree.insert("", "end", values=[f"row {i}"])
tree.pack(fill="x")
step_editor.bind_nested_scroll(tree, outer)

for i in range(30):
    ttk.Label(outer.inner, text=f"trailing row {i}").pack(anchor="w")

root.update_idletasks(); root.update()

check("the page has room to scroll",
      outer.inner.winfo_reqheight() > outer._canvas.winfo_height(),
      (outer.inner.winfo_reqheight(), outer._canvas.winfo_height()))
check("and so does the grid", tree.yview()[1] < 1.0, tree.yview())

# Down over the grid: the grid moves, the page does not.
page_before = outer._canvas.yview()[0]
tree_before = tree.yview()[0]
for _ in range(3):
    tree.event_generate("<MouseWheel>", delta=-120)
root.update()
check("wheel down over the grid scrolls the grid", tree.yview()[0] > tree_before,
      (tree_before, tree.yview()[0]))
check("and does not move the page",
      abs(outer._canvas.yview()[0] - page_before) < 1e-9,
      (page_before, outer._canvas.yview()[0]))
check("the grid moved exactly once per notch, not twice",
      abs(tree.yview()[0] - tree_before - 3 / 200) < 1e-6,
      (tree_before, tree.yview()[0]))

# At the grid's bottom, the page takes over.
tree.yview_moveto(1.0); root.update()
page_before = outer._canvas.yview()[0]
for _ in range(3):
    tree.event_generate("<MouseWheel>", delta=-120)
root.update()
check("once the grid bottoms out the page takes over",
      outer._canvas.yview()[0] > page_before,
      (page_before, outer._canvas.yview()[0]))

# Scrolling back up: the grid regains control first.
tree_before = tree.yview()[0]
page_before = outer._canvas.yview()[0]
for _ in range(2):
    tree.event_generate("<MouseWheel>", delta=120)
root.update()
check("scrolling up moves the grid again before the page",
      tree.yview()[0] < tree_before,
      (tree_before, tree.yview()[0]))
check("with the page held still",
      abs(outer._canvas.yview()[0] - page_before) < 1e-9)

# At the grid's top, up-wheel hands control back to the page.
tree.yview_moveto(0.0); root.update()
page_before = outer._canvas.yview()[0]
for _ in range(3):
    tree.event_generate("<MouseWheel>", delta=120)
root.update()
check("at the grid's top the page scrolls up instead",
      outer._canvas.yview()[0] < page_before,
      (page_before, outer._canvas.yview()[0]))

# A grid short enough to need no scrolling must pass the wheel straight on.
short = ttk.Treeview(outer.inner, columns=["a"], show="headings", height=5)
for i in range(3):
    short.insert("", "end", values=[f"only {i}"])
short.pack(fill="x")
step_editor.bind_nested_scroll(short, outer)
root.update_idletasks(); root.update()
check("a short grid reports nothing to scroll", short.yview() == (0.0, 1.0), short.yview())
outer._canvas.yview_moveto(0.3); root.update()
page_before = outer._canvas.yview()[0]
for _ in range(2):
    short.event_generate("<MouseWheel>", delta=-120)
root.update()
check("so the wheel passes through to the page",
      outer._canvas.yview()[0] > page_before,
      (page_before, outer._canvas.yview()[0]))

class Fake:
    def __init__(self, delta=0, num=0): self.delta = delta; self.num = num
check("wheel_units: Windows down is +1", step_editor.wheel_units(Fake(delta=-120)) == 1)
check("wheel_units: Windows up is -1", step_editor.wheel_units(Fake(delta=120)) == -1)
check("wheel_units: X11 button 4 is up", step_editor.wheel_units(Fake(num=4)) == -1)
check("wheel_units: X11 button 5 is down", step_editor.wheel_units(Fake(num=5)) == 1)

root.destroy()
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
