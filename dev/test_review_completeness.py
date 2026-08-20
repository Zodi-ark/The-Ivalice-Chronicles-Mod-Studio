"""Nothing differing is ever left out of the review.

Written in response to "if this isn't working correctly I'm wondering what
else isn't working correctly". The answer to that question isn't an
argument, it's a property: every row that differs between a mod's file and
the game's must appear in the review, whatever the tool then decides about
it. A change can start switched off, but it cannot be invisible.

Driven by comparing the databases directly, independently of the code under
test - so the expected set comes from the data rather than from the same
logic being checked.
"""
import sqlite3, sys
from pathlib import Path

# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fft_job_editor import migration

CMP = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "cmp"
MOD = CMP / "texture pack mod/fft_data.sqlite"
GAME = CMP / "UnpackedGame folder/fft_data.sqlite"

passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {label}")
    else: failed += 1; print(f"  FAIL  {label}  ({detail})")

if not MOD.exists():
    print(f"SKIP - no comparison data at {CMP}")
    sys.exit(0)


def differing_rows(table, key_column="Key"):
    """The truth, read straight from both databases."""
    mod = {r[0]: r[1:] for r in sqlite3.connect(MOD).execute(f'SELECT * FROM "{table}"')}
    game = {r[0]: r[1:] for r in sqlite3.connect(GAME).execute(f'SELECT * FROM "{table}"')}
    return sorted(k for k in mod if k in game and mod[k] != game[k]), mod, game


rows, mod_rows, game_rows = differing_rows("UI-en")
check("the mod really does differ from the game in six rows", len(rows) == 6, rows)

# The substitute-baseline case, which is what a user hits when the version
# they built against isn't among their saved ones.
assessment = migration.assess_unmodelled_table(
    MOD, GAME, "ui.en.nxd", "UI-en", baseline_sqlite=GAME)

listed = {(key[0] if isinstance(key, tuple) else key)
          for key in assessment.own_changes}
check("every differing row is listed in the review", listed == set(rows),
      sorted(set(rows) - listed))
check("and nothing is listed that doesn't differ", listed <= set(rows),
      sorted(listed - set(rows)))
check("the count matches the number of differences",
      assessment.change_count == len(rows), (assessment.change_count, len(rows)))

ticked = {(key[0] if isinstance(key, tuple) else key)
          for key, _column in assessment.default_selection()}
check("the five HUD labels start ticked",
      ticked == {2801, 2802, 2803, 2804, 2806}, sorted(ticked))
check("the version row starts unticked", migration.VERSION_UI_KEY not in ticked)
check("every unticked row says why",
      all((key, column) in assessment.excluded_by_default
          for key, fields in assessment.own_changes.items() for column in fields
          if (key, column) not in assessment.default_selection()))

# Both sides of every change must be available, or the review is one-sided.
for key, fields in assessment.own_changes.items():
    for column in fields:
        if key not in assessment.game_values or column not in assessment.game_values[key]:
            check("every change carries the game's value too", False, (key, column))
            break
else:
    check("every change carries the game's value too", True)

check("the mod's values shown are the mod's actual values",
      all(assessment.own_changes[(k,)]["Text"] == mod_rows[k][1] for k in rows))
check("and the game's values shown are the game's actual values",
      all(assessment.game_values[(k,)]["Text"] == game_rows[k][1] for k in rows))

# The counters must add up to what is really there.
check("clears, sets and flagged rows account for every difference",
      assessment.additions + assessment.losses + len(assessment.excluded_by_default)
      == len(rows),
      (assessment.additions, assessment.losses, len(assessment.excluded_by_default)))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
