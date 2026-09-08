"""
How wide a text field should be, decided from what the game actually stores.

A field's size is a signifier whether or not anyone intended it to be one:
a 600px box tells the person to type a paragraph, and if it holds a job name
the box has lied to them. `TextFieldRow` used one full-width `QLineEdit` for
every string column, so a twelve-character name and a 261-character
description got the same control - one of them far too wide, the other far
too small in the only direction that mattered.

### The measurements

Every string column of the bundled 1.5.2 database, in characters:

    column                            rows   median   p95   max
    Job-en.Name                        134        9    13    18
    Job-en.Description                 126      161   217   261
    Item-en.Name                       259       11    16    19
    Item-en.NameSingular               259       12    21    24
    Item-en.NamePlural                 259       13    22    25
    Item-en.Name2                      259       11    16    19
    Item-en.Description                258       93   168   230
    Ability-en.Name                    491        9    16    49
    Ability-en.Description             505       80   154   211
    JobCommand-en.Name                  83       10    15    16
    JobCommand-en.Description           83      112   151   177
    CharaName-en.Name                  844        7     9    12
    SystemBonusItem-en.Title             2       18    22    22
    SystemBonusItem-en.Description       2      301   329   329
    SystemBonusSpecialItem-en.Caption    6       23    25    25
    PoachItem-en.Unknown18              96       75    87    93

Two clearly separate populations, and nothing in between: names top out at
25 characters except one 49-character ability, while descriptions run from
80 to 329. `SHORT_TEXT_CHARS = 28` covers the p95 of every name column and
the outright maximum of all but one of them.

### Descriptions are not merely long, they have line breaks

**142 of 258 item descriptions contain a real newline**, and the game uses
it - "...robs its victim of sight.\\nWhen attacking, has a chance of
inflicting Blindness." A `QLineEdit` stores such a value without damaging
it (checked: the round trip through `load()` and `get_value_str()` is
lossless) but it cannot draw it and **it cannot be typed**, because Return
in a line edit does not insert a character. So a modder could open an item,
see a description missing its break, and had no way to write a new one in
the shape the game's own text uses.

That makes the multi-line box a correctness fix as well as a sizing one,
which is why descriptions get a real text area rather than a wider line.

### Why the classification is by name

A per-column measured table would be exact and would also be a fourth place
that has to learn about every new table. The two populations are far enough
apart that the name is a reliable signal, and the one measured exception
that the name would get wrong - `PoachItem-en.Unknown18`, 75 characters
median under a column name that says nothing - is listed explicitly rather
than left to be discovered by someone typing into a box a third the size of
its contents.
"""
from __future__ import annotations

#: Characters a short text field is sized to hold. See the table above.
SHORT_TEXT_CHARS = 28

#: Visible lines for a long text field. A 161-character job description at
#: roughly 55 characters a line is three lines; four would make a row of
#: five text fields taller than the twelve stat rows under it, which this
#: project has already done once.
LONG_TEXT_ROWS = 3

#: Name fragments that mean "this column holds prose". Lower-cased
#: substring match, so `Description2` and `ShortComment` are both caught.
_LONG_MARKERS = ("description", "comment")

#: Columns the name test gets wrong, from the measurements above. A column
#: belongs here only when its real contents have been counted.
_LONG_EXCEPTIONS = frozenset({
    "Unknown18",        # PoachItem-en: median 75 characters, max 93
})


def is_long_text(field_name: str) -> bool:
    """Whether a string column holds prose rather than a name."""
    name = (field_name or "").strip()
    if name in _LONG_EXCEPTIONS:
        return True
    lowered = name.lower()
    return any(marker in lowered for marker in _LONG_MARKERS)


def short_text_width(font_metrics, characters: int = SHORT_TEXT_CHARS) -> int:
    """
    Pixels for `characters` characters of the given font, plus the frame.

    Measured against the widget's own metrics rather than a fixed pixel
    count, because the tool ships two themes and a person may be at any
    system font scale - a number that is 28 characters at 100% is fourteen
    at 200%. The padding covers the line edit's frame and text margin,
    which `horizontalAdvance` knows nothing about.
    """
    sample = "n" * max(1, int(characters))
    return font_metrics.horizontalAdvance(sample) + 18


def long_text_height(font_metrics, rows: int = LONG_TEXT_ROWS) -> int:
    """Pixels for `rows` lines of text, plus the frame."""
    return font_metrics.lineSpacing() * max(1, int(rows)) + 12
