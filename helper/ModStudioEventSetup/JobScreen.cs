// Mod Studio Framework: the mods' jobs on rows of the job screen's own
// (1.39.0; Zodi's choice of 9 November for a game without Dark Knight & Onion
// Knight (Generic), "Framework's own page", and his ask with tests 82 and 83:
// the jobs "scrolling down row by row"). Part of The Ivalice Chronicles Mod
// Studio, GPL-3.0.
//
// What the game does, measured in his program (17 September 2026, read as
// data; dev/research/sidequests/job_screen.py holds each to its bytes):
//
// The job screen has 19 places, the boxes Unit01 to Unit19 of
// ffto_jobchange_ver03.uib's UnitPosition, in rows of 6, 7 and 6, the middle
// row half a place wider each side. Its filling (0x368424) asks the game's
// lister for the unit's jobs (0x28662C into 0x3C51890: the unit's first job,
// 75 to 93 less the Bard or the Dancer, then 160 and 161), shows the first 19
// and gives each to its place by its number in that list (0x12EC5C). Before
// it lists, it puts every place's box where the layout rests it and makes
// all 19 seen (0x12EA68: the layout's ShowUnit, set at once). The screen
// keeps where each row ends (6, 13, 19 at + 0x48, set as it is made), and its
// cursor's step (0x130DF0) goes left and right inside a row and up and down
// between the three by those numbers alone (0xF6D58, 0xF6DD4), down from the
// last row going round to the first. A place's box is at + 0x18 of its 0x100
// bytes from + 0x2DC0; the cursor and the spotlight are put where that box is
// (0x131BF8). Nothing asks the mouse's wheel there.
//
// So the mods' jobs are rows after the game's three, and the screen shows
// three rows at a time. **The rows keep the game's own pattern** (Zodi's
// word on test 87: the mods' row stood under the row above it, where the
// game sets every other row half a place over; and on test 89: "Shade was
// not next to Mender ... the alternating rows goes from seven units on a
// row to six"): the first, third, fifth row of all are on the narrow
// columns and hold six, the second, fourth, sixth on the wide ones and
// hold seven, whatever rows are shown (1.39.4; up to 1.39.3 a row of the
// mods' held six wherever it stood). **Three rows are shown only where
// they fit the 19 places**: seven, six and seven are 20, so no three rows
// start from a row of seven that has a full row of seven two below it
// (Scrolls); the cursor still goes one row at a time, and the rows shown
// move as little as shows its row, by two there (Step, Showing).
//
// - **The list**: after the game's lister, in the filling, the list is made
//   the three rows shown (Listed): the game's 19 and then the mods' jobs, cut
//   to the rows from the one scrolled to. The filling then fills the places
//   as it always does, and everything that reads a place's job reads the
//   list or the place. **Listed never moves the rows itself**: it starts a
//   screen just made or another unit from the game's three, and notes where
//   the rows are to go (below).
// - **The places**: the rows shown may be 6, 7 and up to 6 (the game's own,
//   or rows that stand where the game's do), 7, 6 and up to 6, or the last
//   two alone. Each place's box is moved to its row and
//   its column (the wide columns or the narrow ones, by which row of all it
//   is), a place with no job made unseen, and the screen's three row ends
//   written, so the game's own cursor and mouse follow (Arrange). **A box
//   is never put anywhere by the framework itself** (1.39.3, his test 88:
//   the layout's own slide of the places, as the screen opens, put every
//   box back where the game's rows rest for a few frames). The layouts'
//   own move of a box (0x3EF684, which every animation of a box's place
//   goes through) is told, for each of the 19 boxes, how far its row and
//   column are from the game's: whatever the game or an animation puts the
//   box at, it stands that far from it. So the slide plays on the
//   framework's rows as it does on the game's. Every key of the layout
//   that moves one of the 19 boxes is a place itself (HomePosition, Show,
//   ShowUnit and ShowGuest, the last never played by this screen; none is a
//   step from where the box is), so the distance is added once. The boxes
//   end with their screen: at the screen's end (0x12CFA0) the move is told of none, so nothing made
//   where they were is ever moved. **Each row slides in as one** (1.39.4,
//   his test 89): the game slides its first and third rows in from the left
//   and its middle row from the right, box by box; a box of the game's
//   middle row that stands in the first row shown (the seventh, where that
//   row is one of seven) is told to come from the other side (Across).
// - **No box is moved** (1.39.5, his word on test 90: "make it consistent
//   on how many rows move no matter how many jobs are added"). The screen
//   shows from every second row only (Scrolls), so the three rows shown are
//   always six, seven and six places and stand where the game's own three
//   stand, and the rows move by two for two of the mods' jobs as for 22
//   (three rows from an odd row would be seven, six and seven: 20, and the
//   screen has 19 places). What is written above of the layouts' move, of
//   distances and of a box turned is how 1.39.3 and 1.39.4 did it, and is
//   gone: the move (0x3EF684) is the game's own again, and the screen's end
//   only makes a number 0, so a screen made where the last was starts from
//   the game's rows (Listed).
// - **The window beside the cursor** (a job's name, level and its two
//   buttons) is put to the left of a place among the last three of its row
//   and to the right of any other, by the row ends (0x12FF08). In a short
//   row every place is among the last three, so the window opened to the
//   left of the row's first places and off the screen (his test 87). That
//   test reads ends of the framework's own now (Sides): where each row
//   would end were it full, seven on the wide columns and six on the narrow
//   ones, so the window's side goes by the column a place stands in.
//   While the rows shown are the game's own three and the framework has
//   moved no box, no box is touched: the screen is the game's.
// - **The step between rows**: the game's call for its step up or down is
//   this instead (Vertical). Inside the three rows it answers as the game
//   does. Down from the last row shown, with a row below, the rows move up
//   to show it: the list is made again (the game's own filling, called),
//   and the cursor is put in that row, in its column. Up from the first row
//   shown the same way. At the very last row a
//   new press goes round to the very first, and from the first to the last,
//   as the game's does within its three.
// - A unit's own job is shown wherever the game puts the cursor on it: the
//   game's filling forgets the cursor's place and puts it on the unit's own
//   job while the screen's state is 2 or less (as it opens, and each time
//   it is filled while a job is being chosen). Where that job's row isn't
//   among the three shown, the rows are to move to it, as little as shows
//   it, **as soon as that filling is over** (After, told at the game's two
//   calls of its filling: the game's own filling called again, which then
//   puts the cursor on the job; 1.39.3, his test 88: moved at the cursor's
//   step, the game's rows showed for a few frames first). In any other
//   state the game leaves the cursor, and the rows stay.
// - **The job tree** (Job Progress) is made with the job screen and is
//   always there (0x113970 makes both: found by his test 86, where 1.39.0
//   took "the tree is there" for "the tree is open" and so never moved the
//   rows at all). The filling gives it each job by its number in the list
//   too (0x13420C), and it shows what it was last given. So: that call is
//   the framework's (TreePlace): a job of the game's goes to the tree's
//   place it has in the game's own list, whatever rows are shown, and a
//   mod's job goes to none. And a unit's first filling is always the game's
//   own three rows (above), so the tree has every job of that unit's.
//
// - **From one job to the next on the abilities' page** (Q and E; 1.39.4,
//   his test 89: with the last rows shown, Q from Dragoon went to "Mender"
//   and E from Timekeeper stopped the game). Going to that page (in
//   0x12FC6C) the game hands a piece of the screen (+ 0x1988) every one of
//   the 19 places whose record is open (+ 0x84 of its 0x94 bytes from
//   + 0x2280), whatever is listed, and the piece's step (0x2A7D9C, called
//   at 0x1313A1) goes through those and round. The filling writes the
//   records of the places it lists and no others, so with fewer than 19
//   listed the places after the last held what an earlier filling left.
//   So: the record of every place with no job is closed (Arrange); and
//   that call is the framework's (Cycle): the game's own step, and where
//   it went round the rows shown, the next open job of everything listed
//   is gone to instead, the rows moved to show it and the piece's places
//   made again from them.
//
// - **A job that isn't open to the unit** (1.48.0, the Job Tree's first
//   step; JobNeeds.cs). Each of the mods' jobs is listed with the game's own
//   mark above its number where the unit doesn't have what it needs: locked
//   (0x4000), or not to be seen (0x2000) where no unit of the party has it
//   open (Mark). The filling writes the mark into the place's record and the
//   screen does the rest as for a job of the game's: the place's look, "???",
//   and confirm opening the window of what the job needs. That window
//   (0x1321FC) looks for each needed job among the screen's 19 places, and
//   the framework's rows show three rows of more: so for the window's call
//   alone the places' records are the cursor's own and one for each needed
//   job, then as they were (Needs). Where every needed job is on a place
//   shown, nothing is touched.
//
// - **The mods' jobs on Job Progress** (1.49.0, the Job Tree's second and
//   third steps; JobTree.cs). The game makes a job's record (its name, the
//   unit's level, its figure) only for a job its filling lists, and the rows
//   shown are 19 of more. So after each of the game's own fillings the
//   filling is run again for the mods' jobs alone (Harvest): the list is the
//   unit's first job, which the filling treats apart, and then up to 18 of
//   the mods' jobs, the filling's readying of the screen and its giving of a
//   job to a place left out (a number the native code reads), and the list
//   and its count put back after. The filling's call for the job tree then
//   hands each of those records on (TreePlace, Harvested). And a job chosen
//   on Job Progress has its row shown as the tree goes back to the screen
//   (Show).
// - (2.0.5, his report of 18 November: "When going to the next job of our
//   new Jobs the very first Job in the top left changes palette this only
//   happens with ramza") The filling gives every place but place 0 palette
//   0 where the unit's row gives it colors of its own (Ramza: the game's
//   place 0 is always the unit's first job, his Gallant Knight in his own
//   colors). With the rows moved down, place 0 holds the first job of the
//   rows shown, which kept Ramza's palette number (his Dragoon green). The
//   framework writes a number the filling's test reads (Listed: not 0
//   while place 0 holds another job than the unit's first), and place 0
//   then gets palette 0 as every other place (JobRoom's stub at 0x368A09).
// - (2.0.6, his test 131: "Still green") Place 0's palette was 0 already:
//   the filling makes place 0's figure record as the unit's own (a flag of
//   the record maker, 0x2C1D40, set for place 0 alone), which gives it the
//   unit's chosen color (Ramza's, the record's + 0xA) and no palette. The
//   same number now clears that flag too (JobRoom's stub at 0x368959), so
//   place 0's record is made as every other place's.
//
// With Dark Knight & Onion Knight (Generic) on, none of this is made: the
// jobs take its second page's empty places, as before (Zodi's choice).
using System;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public sealed unsafe class JobScreen
    {
        /// <summary>The screen's places, the rows it shows, the jobs in a row on the narrow columns (the game's first
        /// and third), and in one on the wide columns (the game's second).</summary>
        public const int Places = 19, Shown = 3, ModsRow = 6, WideRow = 7;
        /// <summary>The game's own three rows.</summary>
        public static readonly int[] GameRows = { 6, 7, 6 };
        /// <summary>The screen: where each of its three rows ends, its places (0x100 bytes each, a place's box at
        /// + 0x18), its cursor's place and the place under the mouse (below 0: none).</summary>
        public const int RowEnds = 0x48, Slots = 0x2DC0, SlotBytes = 0x100, SlotBox = 0x18, Cursor = 0x4A48, Hover = 0x2148;
        /// <summary>The screen's state, and the last in which the game's filling puts the cursor on the unit's own job.</summary>
        public const int State = 0x4A40, LastCursorState = 2;
        /// <summary>A box of the layouts: how much of it shows (1 all, 0 none).</summary>
        public const int BoxOpacity = 0x6C;
        /// <summary>From the game's interface to its unit screens' holder, whether that is in use (its third own
        /// function) and the job screen it holds. (The job tree, at + 0x80, is made with the screen and always
        /// there: nothing is read from it.)</summary>
        public const int RootHolders = 0x10, HoldersUnits = 0x58, HolderInUse = 0x10, HolderScreen = 0x78;
        /// <summary>A record of the menu's: its unit's job. A job in the list: its number's bits.</summary>
        public const int RecordJob = 0x24, JobBits = 0x3FF;
        /// <summary>What the cursor's step tells its caller: the place taken, and that it moved.</summary>
        public const int OutPlace = 4, OutMoved = 8;
        /// <summary>(1.39.4) A place's record in the screen (0x94 bytes from + 0x2280): whether its job is open (0),
        /// locked (1) or not to be seen (2), as the filling writes it from the list.</summary>
        public const int Records = 0x2280, RecordBytes = 0x94, RecordClosed = 0x84, Unseen = 2;
        /// <summary>(1.39.4) A job in the list: the bits above its number that say it is locked or not to be seen.</summary>
        public const int ClosedBits = 0x6000;
        /// <summary>(1.39.4) The piece of the screen that goes from one job to the next on the abilities' and the
        /// summary's pages (Q and E): where it is in the screen, the places it goes through (19 numbers at most), how
        /// many, and which of them it is on. What its step tells its caller: 1 back, 2 on.</summary>
        public const int Cycler = 0x1988, CyclePlaces = 0x4A8, CycleCount = 0x4F4, CycleOn = 0x4F8, CycleBack = 1, CycleOnward = 2;
        /// <summary>What the log says where the mods' jobs are on rows of the screen's own.</summary>
        public static string Line(int jobs) =>
            $"the job screen lists the mods' job{(jobs == 1 ? "" : "s")} on rows of {(jobs == 1 ? "its" : "their")} own after "
            + "the game's: move down past the last row to see them.";

        // --- the rows, as numbers ---------------------------------------------------------------------------------

        /// <summary>How many jobs each row holds: the game's three, then the mods' jobs as the game's own pattern
        /// goes on (1.39.4): seven in a row on the wide columns, six in one on the narrow.</summary>
        public static List<int> RowSizes(int mods)
        {
            var sizes = new List<int>(GameRows);
            for (int left = mods; left > 0;)
            {
                int size = Math.Min(left, Wide(sizes.Count) ? WideRow : ModsRow);
                sizes.Add(size);
                left -= size;
            }
            return sizes;
        }

        /// <summary>(1.39.4) Whether the three rows from `scroll` fit the screen's 19 places (seven, six and seven
        /// don't).</summary>
        public static bool Fits(IList<int> sizes, int scroll)
        {
            if (scroll < 0 || scroll >= sizes.Count)
                return false;
            int jobs = 0;
            for (int row = scroll; row < scroll + Shown && row < sizes.Count; row++)
                jobs += sizes[row];
            return jobs <= Places;
        }

        /// <summary>(1.39.5, his word on test 90: "make it consistent on how many rows move no matter how many
        /// jobs are added") Every first row the screen can show from: every second row, as far as a row follows
        /// it. Three rows from an even row are six, seven and six places, the screen's 19, standing where the
        /// game's own rows stand; three from an odd row would be seven, six and seven, one more than the screen
        /// has. So the rows shown always move by two, for two of the mods' jobs as for 22.</summary>
        public static List<int> Scrolls(IList<int> sizes)
        {
            var scrolls = new List<int> { 0 };
            for (int scroll = 2; scroll + 1 < sizes.Count; scroll += 2)
                scrolls.Add(scroll);
            return scrolls;
        }

        /// <summary>The row a job is in, by its number in everything listed (-1: past the last).</summary>
        public static int RowOf(IList<int> sizes, int at)
        {
            if (at < 0)
                return -1;
            for (int row = 0, end = 0; row < sizes.Count; row++)
            {
                end += sizes[row];
                if (at < end)
                    return row;
            }
            return -1;
        }

        /// <summary>The first row to show so a row is among the three, of those the screen can show from
        /// (`scrolls`), nearest the one shown now. No row to show (below 0): the one shown now, or the first.</summary>
        public static int Showing(int row, int scroll, IList<int> scrolls)
        {
            if (row < 0)
                return scrolls.Contains(scroll) ? scroll : 0;
            int best = -1;
            foreach (int to in scrolls)
                if (to <= row && row < to + Shown && (best < 0 || Math.Abs(to - scroll) < Math.Abs(best - scroll)))
                    best = to;
            return best < 0 ? 0 : best;
        }

        /// <summary>The three rows from `scroll` of everything listed, written to `window` (19 at most); where each
        /// of the three ends, and how many jobs each has. How many jobs there are.</summary>
        public static int Window(ReadOnlySpan<short> whole, IList<int> sizes, int scroll, Span<short> window, Span<int> ends,
                                 Span<int> rows)
        {
            int from = 0;
            for (int row = 0; row < scroll && row < sizes.Count; row++)
                from += sizes[row];
            int count = 0;
            for (int shown = 0; shown < Shown; shown++)
            {
                int size = scroll + shown < sizes.Count ? sizes[scroll + shown] : 0;
                size = Math.Min(Math.Min(size, Places - count), whole.Length - from);
                size = Math.Max(size, 0);
                for (int k = 0; k < size; k++)
                    window[count + k] = whole[from + k];
                from += size;
                count += size;
                ends[shown] = count;
                rows[shown] = size;
            }
            return count;
        }

        /// <summary>Whether a row of all the rows (the game's first is 0) stands on the wide columns, as the game's
        /// second does: every other row.</summary>
        public static bool Wide(int row) => (row & 1) == 1;

        /// <summary>Where each of three rows would end were it full (seven on the wide columns, six on the narrow),
        /// the first of them row `scroll` of all and starting where the rows' own ends say: what the game's test of
        /// the window's side is given, so it goes by the column a place stands in.</summary>
        public static void Sides(ReadOnlySpan<int> ends, int scroll, Span<int> sides)
        {
            for (int row = 0; row < Shown; row++)
                sides[row] = (row == 0 ? 0 : ends[row - 1]) + (Wide(scroll + row) ? WideRow : ModsRow);
        }

        /// <summary>The game's own step between rows (0xF6DD4): a new press past an end goes round to the other, a
        /// held one stops at it.</summary>
        public static int Plain(int row, int min, int max, int delta, bool fresh)
        {
            if (delta == 0)
                return row;
            int to = row + delta;
            if (fresh)
                return to > max ? min : to < min ? max : to;
            return Math.Max(min, Math.Min(to, max));
        }

        /// <summary>A step up or down from one of the three rows shown, the first row shown being `scroll` of the
        /// rows there are (`rows` of them; `scrolls` the first rows the screen can show from): the row of the three
        /// the cursor takes, and the first row shown after it. The cursor goes one row of all the rows; the rows
        /// shown move as little as shows that row (by two where three rows from the next wouldn't fit). A new press
        /// past the very last row goes round to the very first, and back; a held one stops.</summary>
        public static (int Row, int Scroll) Step(int row, int delta, bool fresh, int scroll, int rows, IList<int> scrolls)
        {
            if (delta == 0)
                return (row, scroll);
            int to = scroll + row + delta;
            if (to < 0 || to >= rows)
            {
                if (!fresh)
                    return (row, scroll);
                to = to < 0 ? rows - 1 : 0;
            }
            int shown = Showing(to, scroll, scrolls);
            return (to - shown, shown);
        }

        /// <summary>The place in a row for a column: the row's last when it is shorter.</summary>
        public static int PlaceIn(ReadOnlySpan<int> ends, int row, int column)
        {
            int first = row == 0 ? 0 : ends[row - 1];
            int size = ends[row] - first;
            if (size <= 0)
                return first;
            return first + Math.Max(0, Math.Min(column, size - 1));
        }

        // --- the screen -------------------------------------------------------------------------------------------

        public delegate bool UpDownFunction(out int delta, out bool fresh, int pad, int other);

        /// <summary>The game's own, each called as the game calls it: its filling of the job screen, its putting
        /// of the cursor on a place, its drawing of the places again, its move of a box, its reading of a step up
        /// or down, and whether the unit screens' holder is in use.</summary>
        public Action Fill = () => { };
        public Action<nint, int> Place = (_, _) => { };
        public Action<nint> Refresh = _ => { };
        public UpDownFunction UpDown = (out int delta, out bool fresh, int _, int _) =>
        {
            delta = 0;
            fresh = true;
            return false;
        };
        /// <summary>(1.39.4) The game's own step from one job to the next on the abilities' page (0x2A7D9C: the piece,
        /// what is pressed, what is held, where it says which way it went): the place gone to, below 0 for none.</summary>
        public Func<nint, int, int, nint, int> CycleStep = (_, _, _, _) => -1;
        public Func<nint, bool> InUse = _ => true;
        /// <summary>(1.48.0) The mark of one of the mods' jobs (its place among them) for the unit the screen is of: 0
        /// open, JobNeeds.Locked or JobNeeds.Unseen.</summary>
        public Func<int, int> Mark = _ => 0;
        /// <summary>(1.48.0) The game's own window of what the job at the cursor needs (0x1321FC), called as the game
        /// calls it; what a job needs, each needed job as the window's search knows it (null: not known, the window
        /// is the game's); and a place's record made for a needed job on none of the places shown (the job, whether
        /// the unit's list has it open, 0, locked, 1, or not to be seen, 2, or doesn't hold it, below 0; the record to
        /// write), false where it can't be made.</summary>
        public Action<nint> NeedsWindow = _ => { };
        public Func<int, int[]?> Needed = _ => null;
        public Func<int, int, nint, bool> Stand = (_, _, _) => false;
        /// <summary>(1.55.1) Which of a job's needs are of a job mastered (JobAsker.MasteredNeeds), and whether the unit has
        /// mastered one of the game's jobs (JobAsker.HasMastered).</summary>
        public Func<int, bool[]?> MasteredNeeds = _ => null;
        public Func<int, bool> HasMastered = _ => false;
        /// <summary>(1.48.0) A place's record: where its job is, as the window reads it.</summary>
        public const int RecordJobAt = JobNeeds.PlaceJobAt;
        /// <summary>(1.55.1) A place's record's level: the unit's in its job (JobNeeds.PlaceLevelAt).</summary>
        public const int RecordLevelAt = JobNeeds.PlaceLevelAt;
        /// <summary>(1.48.0) Whether the game's window was shown in the last call of Needs (a fault before it leaves it
        /// to the caller).</summary>
        public bool Windowed { get; private set; }

        /// <summary>(1.49.0) The unit screens' holder's job tree; how many of the mods' jobs the filling is run for at
        /// a time (the list's first place is the unit's first job's).</summary>
        public const int HolderTree = 0x80, HarvestJobs = Places - 1;
        /// <summary>(1.49.0) In the filling run for the mods' jobs alone: a job's record as the game made it (the job's
        /// place among the mods' jobs, the record, the job tree); before the first of a unit's; and a unit whose list is
        /// the game's own, for which none comes (the job tree).</summary>
        public Action<int, nint, nint>? Harvested;
        public Action? HarvestBegins;
        public Action<nint>? HarvestNone;

        readonly short[] _mods;
        readonly nint* _root;
        readonly short* _list;
        readonly short* _menuIndex;
        readonly byte** _menuTable;
        readonly int _records;
        /// <summary>The count the game keeps of the unit's jobs listed (it makes it 1 after the lister for a unit whose
        /// job's row hides the job tree), and where the game's test of which side the window beside the cursor goes
        /// reads each row's end from (three numbers, the framework's to write).</summary>
        readonly short* _gameCount;
        readonly int* _sides;
        /// <summary>(1.39.5) Not 0 while the screen the framework last arranged is there: the screen's end makes it
        /// 0 (the native stand in for the deleting function's call of the ending).</summary>
        readonly int* _alive;
        /// <summary>(1.49.0) Not 0 while the filling is run for the mods' jobs alone: the native code then leaves out
        /// the filling's readying of the screen and its giving of a job to a place (null: none to tell). The first of the
        /// mods' jobs that run is for (below 0: no such run), and how many it listed.</summary>
        readonly int* _harvesting;
        /// <summary>(2.0.5) Not 0 while the screen's place 0 holds another job than the unit's first (the rows moved
        /// down): the native code then gives it palette 0 as every other place and (2.0.6) makes its figure's
        /// record as every other place's (null: none to tell).</summary>
        readonly int* _palette;
        int _harvest = -1, _harvested;
        /// <summary>(1.49.1) The filling is being run for the game's own list, so the job tree holds every one of the
        /// game's jobs for this unit whatever rows are shown.</summary>
        bool _all;
        readonly int[] _ends = new int[Shown];
        readonly int[] _rows = new int[Shown];
        /// <summary>The screen the framework last arranged (0: none, or it has ended).</summary>
        nint _arranged;
        nint _screen;
        /// <summary>The rows there are and the first rows the screen can show from; everything listed at the last
        /// filling (the game's 19 with their bits, then the mods' jobs).</summary>
        readonly List<int> _sizes, _scrolls;
        readonly short[] _whole;
        int _unit = -1, _scroll, _count, _from, _pending = -1;
        bool _own, _mine;

        /// <summary>The first row shown, how many jobs are shown, whether the rows are the framework's now, and the
        /// first row the rows are to move to at the cursor's next step (below 0: none).</summary>
        /// <summary>(1.49.0) Whether the filling now run is for the mods' jobs alone.</summary>
        public bool Harvesting => _harvest >= 0 || _all;
        public int Scroll => _scroll;
        public int Count => _count;
        public bool Own => _own;
        public int Pending => _pending;

        /// <summary>`mods`: the mods' jobs' numbers, in the order they were given. `root`: the game's interface
        /// (a pointer). `list`: the game's list of a unit's jobs for the screen. `menuIndex` and `menuTable`: which
        /// of the menu's records the screens are of, and the table of them (`records` long). `gameCount`: the
        /// game's count of the jobs listed. `sides`: three numbers the window's side is read from. `alive`: a number
        /// the screen's end makes 0.</summary>
        public JobScreen(IList<int> mods, nint* root, short* list, short* menuIndex, byte** menuTable, int records,
                         short* gameCount, int* sides, int* alive, int* harvesting = null, int* palette = null)
        {
            _gameCount = gameCount;
            _sides = sides;
            _alive = alive;
            _harvesting = harvesting;
            if (_harvesting != null)
                *_harvesting = 0;
            _palette = palette;
            if (_palette != null)
                *_palette = 0;
            *_alive = 0;
            for (int row = 0, end = 0; row < Shown; row++)
                _sides[row] = end += GameRows[row];
            _mods = new short[mods.Count];
            for (int k = 0; k < mods.Count; k++)
                _mods[k] = (short)mods[k];
            _sizes = RowSizes(mods.Count);
            _scrolls = Scrolls(_sizes);
            _whole = new short[Places + mods.Count];
            _root = root;
            _list = list;
            _menuIndex = menuIndex;
            _menuTable = menuTable;
            _records = records;
        }

        nint HolderNow()
        {
            nint root = *_root;
            if (root == 0)
                return 0;
            nint holders = *(nint*)(root + RootHolders);
            return holders == 0 ? 0 : *(nint*)(holders + HoldersUnits);
        }

        /// <summary>In the game's filling of the job screen, after its lister has listed the unit's jobs (`count` of
        /// them): the list made the three rows shown, the screen's places arranged for them. How many are listed
        /// now. A unit with fewer than 19 (a guest, a monster) keeps the game's list, and the screen is given back
        /// as the game has it.</summary>
        public int Listed(int count)
        {
            // (1.49.0) The filling run for the mods' jobs alone: its own list, nothing of the rows touched.
            // (1.49.1) The game's own list, as its lister left it.
            // (2.0.5) Place 0 holds the unit's first job in every list but the framework's rows moved down (below).
            if (_palette != null)
                *_palette = 0;
            if (_all)
                return count;
            if (_harvest >= 0)
                return HarvestListed(count);
            _own = false;
            if (_mods.Length == 0)
                return count;
            nint holder = HolderNow();
            nint screen = holder != 0 && InUse(holder) ? *(nint*)(holder + HolderScreen) : 0;
            // The screen the framework last arranged has ended (its end makes the number 0): a screen made where it
            // was is another, as the game makes it, and starts from the game's three rows.
            bool ended = _arranged != 0 && *_alive == 0;
            if (ended)
                _arranged = 0;
            if (count < Places)
            {
                // The game's own list, as it is: the screen given back as the game has it (its three row ends, each
                // place's box seen), and the unit after it starts from the game's rows.
                _pending = -1;
                _scroll = 0;
                for (int row = 0, end = 0; row < Shown; row++)
                    _sides[row] = end += GameRows[row];
                if (screen != 0 && screen == _arranged)
                {
                    for (int row = 0, end = 0; row < Shown; row++)
                    {
                        _rows[row] = GameRows[row];
                        _ends[row] = end += GameRows[row];
                    }
                    _count = Places;
                    Arrange(screen);
                }
                return count;
            }
            int unit = *_menuIndex;
            byte* record = unit >= 0 && unit < _records ? _menuTable[unit] : null;
            int job = record != null ? *(ushort*)(record + RecordJob) & JobBits : -1;

            Span<short> whole = _whole;
            for (int k = 0; k < Places; k++)
                whole[k] = _list[k];
            // (1.48.0) Each of the mods' jobs with the game's own mark above its number where it isn't open to the unit.
            for (int k = 0; k < _mods.Length; k++)
                whole[Places + k] = (short)((ushort)_mods[k] | Mark(k) & ClosedBits);
            var sizes = _sizes;

            if (!_mine)
            {
                // A screen just made or another unit starts from the game's own three rows: the job tree is given
                // every job by this filling, so its first for a unit lists all of the game's.
                if (screen == 0 || screen != _screen || unit != _unit || ended)
                    _scroll = 0;
                _pending = -1;
                // Where the game is about to put the cursor on the unit's own job and that job's row isn't among the
                // three shown, the rows are to move to it at the cursor's next step.
                if (screen != 0 && *(int*)(screen + State) <= LastCursorState)
                {
                    int at = -1;
                    for (int k = 0; k < whole.Length && at < 0; k++)
                        if ((whole[k] & JobBits) == job)
                            at = k;
                    int want = Showing(RowOf(sizes, at), _scroll, _scrolls);
                    if (want != _scroll)
                        _pending = want;
                }
            }
            if (!_scrolls.Contains(_scroll))
                _scroll = 0;
            _from = 0;
            for (int row = 0; row < _scroll; row++)
                _from += sizes[row];

            Span<short> window = stackalloc short[Places];
            int listed = Window(whole, sizes, _scroll, window, _ends, _rows);
            for (int k = 0; k < listed; k++)
                _list[k] = window[k];
            _list[listed] = -1;
            _count = listed;
            _unit = unit;
            _screen = screen;
            _own = true;
            // (2.0.5, his report of 18 November) With rows moved down, place 0 holds the first job of the rows shown,
            // not the unit's first: it is given palette 0 as every other place, not the unit's own (Ramza's colors);
            // (2.0.6, his test 131) and its figure's record is made as every other place's, not as the unit's own
            // (the record maker's flag, which gave it Ramza's chosen color: JobRoom's "OwnFigure").
            if (_palette != null)
                *_palette = _from > 0 ? 1 : 0;
            if (screen != 0)
                Arrange(screen);
            return listed;
        }

        /// <summary>In the game's filling, where it gives the job tree a job by its number in the list (`index`): the
        /// tree's place for it. A job of the game's has the place it has in the game's own list, whatever rows are
        /// shown; a mod's job has none (below 0). A list the framework left alone, or the game has since made its
        /// own, is the game's.</summary>
        public int TreePlace(int index, nint record = 0, nint tree = 0)
        {
            // (1.49.0) In the filling run for the mods' jobs alone the tree's own places get nothing: each of the mods'
            // jobs' records is handed on (the list's first is the unit's first job, given by the filling before).
            // (1.49.1, his test 112) In the filling run for the game's own list each of the game's jobs goes to its own
            // place: with the framework's rows moved down, the game's fillings list only the rows shown, and the tree
            // kept what an earlier unit, or the unit's job before a change, had left on the others.
            if (_all)
                return index >= 0 && index < Places ? index : -1;
            if (_harvest >= 0)
            {
                if (index >= 1 && index <= _harvested && record != 0)
                    Harvested?.Invoke(_harvest + index - 1, record, tree);
                return -1;
            }
            if (!_own || *_gameCount != _count)
                return index;
            int at = _from + index;
            return index >= 0 && at < Places ? at : -1;
        }

        /// <summary>The screen made to show the rows listed: its three row ends, the three numbers the window's side
        /// is read from, a place with no job unseen and (1.39.4) its record closed, so nothing that goes through the
        /// open places finds what an earlier filling left there. (1.39.5) No box is moved: every three rows the
        /// screen can show stand where the game's own three stand.</summary>
        public void Arrange(nint screen)
        {
            for (int row = 0; row < Shown; row++)
                if (*(int*)(screen + RowEnds + 4 * row) != _ends[row])
                    *(int*)(screen + RowEnds + 4 * row) = _ends[row];
            Sides(_ends, _scroll, new Span<int>(_sides, Shown));
            for (int k = _count; k < Places; k++)
                *(int*)(screen + Records + k * RecordBytes + RecordClosed) = Unseen;
            for (int k = 0; k < Places; k++)
            {
                nint box = *(nint*)(screen + Slots + k * SlotBytes + SlotBox);
                if (box == 0)
                    continue;
                float shown = k < _count ? 1f : 0f;
                if (*(float*)(box + BoxOpacity) != shown)
                    *(float*)(box + BoxOpacity) = shown;
            }
            _arranged = screen;
            *_alive = 1;
        }

        /// <summary>After each of the game's own fillings of the screen (its two calls): the rows noted at that
        /// filling for the unit's own job are moved to at once, by the game's filling again, which puts the cursor on
        /// the job. Nothing of the first is seen: no frame is drawn between the two.</summary>
        public void After()
        {
            if (_mine || _harvest >= 0 || _all)
                return;
            if (_pending >= 0)
            {
                int want = _pending;
                _pending = -1;
                if (_own && _screen != 0 && *_gameCount == _count && want != _scroll)
                    Refill(want);
            }
            Harvest();
        }

        /// <summary>(1.49.0) The game's filling run again for the mods' jobs alone, 18 at a time, so the game makes each
        /// one's record for the unit (TreePlace hands them on): the list and its count are put back as they were, and
        /// while the number says so the native code leaves out the filling's two calls that touch the screen. A unit
        /// whose list is the game's own gets none (told).</summary>
        void Harvest()
        {
            if (Harvested == null || _mods.Length == 0)
                return;
            nint holder = HolderNow();
            nint tree = holder != 0 && InUse(holder) ? *(nint*)(holder + HolderTree) : 0;
            if (!_own || _screen == 0 || *_gameCount != _count || tree == 0)
            {
                HarvestNone?.Invoke(tree);
                return;
            }
            Span<short> kept = stackalloc short[Places + 1];
            for (int k = 0; k <= Places; k++)
                kept[k] = _list[k];
            short count = *_gameCount;
            HarvestBegins?.Invoke();
            try
            {
                // (1.49.1) Where the rows shown don't start at the game's first, the game's own list first: every
                // one of the game's jobs given to the tree for this unit.
                if (_from != 0)
                {
                    _all = true;
                    if (_harvesting != null)
                        *_harvesting = 1;
                    Fill();
                    _all = false;
                }
                for (int from = 0; from < _mods.Length; from += HarvestJobs)
                {
                    _harvest = from;
                    _harvested = 0;
                    if (_harvesting != null)
                        *_harvesting = 1;
                    Fill();
                }
            }
            finally
            {
                if (_harvesting != null)
                    *_harvesting = 0;
                _all = false;
                _harvest = -1;
                _harvested = 0;
                for (int k = 0; k <= Places; k++)
                    _list[k] = kept[k];
                *_gameCount = count;
            }
        }

        /// <summary>(1.49.0) The list of a filling run for the mods' jobs alone: the unit's first job as the game's
        /// lister left it, then the mods' jobs from the one the run is for, each with its mark, 18 at most. How many
        /// are listed. A list that isn't a whole one is left as it is (no job is handed on then).</summary>
        int HarvestListed(int count)
        {
            _harvested = 0;
            if (count < Places)
                return count;
            int jobs = Math.Min(HarvestJobs, _mods.Length - _harvest);
            for (int k = 0; k < jobs; k++)
                _list[1 + k] = (short)((ushort)_mods[_harvest + k] | Mark(_harvest + k) & ClosedBits);
            _list[1 + jobs] = -1;
            _harvested = jobs;
            return 1 + jobs;
        }

        /// <summary>(1.49.0) As Job Progress goes back to the screen with one of the mods' jobs chosen (`job` its place
        /// among them): the rows made to show that job's row, by the game's filling, as little moved as shows it. Its
        /// place on the screen; below 0 where the rows aren't the framework's or the job can't be shown.</summary>
        public int Show(int job)
        {
            if (!_own || _screen == 0 || *_gameCount != _count || job < 0 || job >= _mods.Length || _harvest >= 0 || _all)
                return -1;
            int to = Places + job;
            int scroll = Showing(RowOf(_sizes, to), _scroll, _scrolls), start = 0;
            for (int row = 0; row < scroll; row++)
                start += _sizes[row];
            if (scroll != _scroll)
            {
                Refill(scroll);
                if (!_own || _scroll != scroll || _from != start)
                    return -1;
            }
            int place = to - start;
            return place >= 0 && place < _count ? place : -1;
        }

        /// <summary>In the screen's step of its cursor, where the game asks its step up or down between the three
        /// rows (`row` the cursor's, `min` and `max` the first and last, `pad` and `other` as the game hands them
        /// on; `screen` the job screen, `told` what the step tells its caller): the row the cursor takes. Each time
        /// it is asked the places are kept arranged. Where the rows move (rows noted at the last filling for the
        /// unit's own job, or a step past the first or last row shown), the list is made again and the cursor put
        /// in its new place here, and the row answered is the one it was in.</summary>
        public int Vertical(int row, int min, int max, int pad, int other, nint screen, nint told)
        {
            UpDown(out int delta, out bool fresh, pad, other);
            // (1.39.2) A count of the game's that isn't the framework's: the game has made the list its own after the
            // lister (one job, for a unit whose job's row hides the job tree), and the step is the game's.
            if (!_own || *_gameCount != _count || screen == 0 || screen != _screen || min != 0 || max != Shown - 1 || row < 0
                || row >= Shown)
                return Plain(row, min, max, delta, fresh);
            if (*(int*)(screen + Hover) >= _count)
                *(int*)(screen + Hover) = -1;
            Arrange(screen);
            if (_pending >= 0)
            {
                // Rows noted at a filling that After wasn't told of (none is known): moved to here, the same way.
                int want = _pending;
                _pending = -1;
                if (want != _scroll)
                {
                    Refill(want);
                    int on = *(int*)(screen + Cursor);
                    Put(screen, told, on >= 0 && on < _count ? on : 0);
                    return row;
                }
            }
            var (to, scroll) = Step(row, delta, fresh, _scroll, _sizes.Count, _scrolls);
            if (scroll == _scroll)
                return to;
            int column = *(int*)(screen + Cursor) - (row == 0 ? 0 : _ends[row - 1]);
            Refill(scroll);
            Put(screen, told, PlaceIn(_ends, to, column));
            return row;
        }

        /// <summary>(1.39.4) In the screen's step on the abilities' and the summary's pages, where the game asks its
        /// step from one job to the next (Q and E; `piece` the piece of the screen that keeps the open places and
        /// which it is on, `pressed`, `held` and `told` as the game hands them on, `screen` the job screen): the
        /// place gone to, below 0 for none. The game's own step goes through the open places of the rows shown and
        /// round. Where it went round, there are jobs on other rows: the next open job of everything listed is
        /// gone to (past the very last, the very first, and back), the rows moved to show it by the game's filling,
        /// the piece's places made again from the rows then shown.</summary>
        public int Cycle(nint piece, int pressed, int held, nint told, nint screen)
        {
            int before = *(int*)(piece + CycleOn);
            int from = before >= 0 && before < Places ? *(int*)(piece + CyclePlaces + 4 * before) : -1;
            int place = CycleStep(piece, pressed, held, told);
            if (place < 0 || !_own || *_gameCount != _count || screen == 0 || screen != _screen || from < 0 || from >= _count)
                return place;
            int way = *(int*)told, after = *(int*)(piece + CycleOn);
            bool round = way == CycleOnward ? after < before : way == CycleBack && after > before;
            if (!round)
                return place;
            int to = -1;
            for (int n = 1; n < _whole.Length && to < 0; n++)
            {
                int k = ((_from + from + (way == CycleOnward ? n : -n)) % _whole.Length + _whole.Length) % _whole.Length;
                if ((_whole[k] & ClosedBits) == 0)
                    to = k;
            }
            if (to < 0)
                return place;
            int scroll = Showing(RowOf(_sizes, to), _scroll, _scrolls), start = 0;
            for (int row = 0; row < scroll; row++)
                start += _sizes[row];
            if (scroll != _scroll)
            {
                // The cursor's place first, so the filling marks the right place as the one the cursor is on (in this
                // state the filling leaves the cursor where it is).
                int was = _scroll;
                *(int*)(screen + Cursor) = to - start;
                Refill(scroll);
                if (!_own || _scroll != scroll || _from != start)
                {
                    *(int*)(screen + Cursor) = from;
                    if (_own && _scroll != was)
                        Refill(was);
                    return Open(piece, screen, place) >= 0 ? place : -1;
                }
            }
            int on = Open(piece, screen, to - start);
            if (on < 0)
            {
                // The job isn't open as the screen has it: the nearest that is, the way gone.
                int count = *(int*)(piece + CycleCount);
                if (count <= 0)
                    return -1;
                on = way == CycleOnward ? 0 : count - 1;
                *(int*)(piece + CycleOn) = on;
                int found = *(int*)(piece + CyclePlaces + 4 * on);
                *(int*)(screen + Cursor) = found;
                Refresh(screen);
                return found;
            }
            return to - start;
        }

        /// <summary>(1.48.0) In the screen's change of state to the window of what the job at the cursor needs, in
        /// place of the game's call of the window (0x1321FC): the game's window, shown over records it finds every
        /// needed job in. The window looks for each needed job among the screen's 19 places' records, and the rows
        /// shown are three of more. Where a needed job is on none of the places shown, the records are, for the
        /// window's call alone: the cursor's own where it is, and from the first place on one for each needed job in
        /// the needs' order (the place's own where the job is shown, else made: Stand), every other place a record of
        /// no job that isn't to be seen; then every record as it was. Where all are on places shown, or the rows are
        /// the game's, the window is the game's and nothing is touched. (1.55.1) But a job needed mastered (the game's
        /// Dark Knight's Knight and Black Mage) that the unit has mastered is, for the call, a record of level
        /// MasteredShown, as its need is in GeneralJob: its two cells say "Mastered", neither red (JobNeeds.cs); so then
        /// the records are made even where every needed job is shown.</summary>
        public void Needs(nint screen)
        {
            Windowed = false;
            // Only the screen the rows were last arranged on is read: any other is handed on as it came.
            bool mine = _own && screen != 0 && screen == _screen && *_gameCount == _count;
            int place = mine ? *(int*)(screen + Cursor) : -1;
            int[]? needed = null;
            bool[]? mastered = null;
            if (mine && place >= 0 && place < _count)
            {
                int job = *(ushort*)(screen + Records + place * RecordBytes + RecordJobAt) & JobBits;
                needed = Needed(job);
                mastered = MasteredNeeds(job);
                if (needed == null || mastered == null || mastered.Length != needed.Length)
                    mastered = null;
            }
            if (needed == null || needed.Length == 0 || needed.Length >= Places)
            {
                Windowed = true;
                NeedsWindow(screen);
                return;
            }
            var records = new Span<byte>((byte*)screen + Records, Places * RecordBytes);
            // Where each needed job is among the places shown (below 0: on none).
            var shown = new int[needed.Length];
            bool everyShown = true;
            for (int n = 0; n < needed.Length; n++)
            {
                shown[n] = -1;
                for (int k = 0; k < _count && shown[n] < 0; k++)
                    if (k != place
                        && JobNeeds.Known(*(ushort*)(screen + Records + k * RecordBytes + RecordJobAt) & JobBits, _mods) == needed[n])
                        shown[n] = k;
                everyShown &= shown[n] >= 0;
            }
            if (everyShown && mastered == null)
            {
                Windowed = true;
                NeedsWindow(screen);
                return;
            }
            byte[] kept = records.ToArray();
            var made = new byte[kept.Length];
            // A record of no job, not to be seen: what every place the window isn't to find anything in holds.
            for (int k = 0; k < Places; k++)
                BitConverter.TryWriteBytes(made.AsSpan(k * RecordBytes + RecordClosed), Unseen);
            kept.AsSpan(place * RecordBytes, RecordBytes).CopyTo(made.AsSpan(place * RecordBytes));
            int at = 0;
            for (int n = 0; n < needed.Length; n++, at++)
            {
                if (at == place)
                    at++;
                var to = made.AsSpan(at * RecordBytes, RecordBytes);
                // (1.55.1) A job needed mastered that the unit has mastered: its record's level MasteredShown.
                bool masteredOne = mastered != null && mastered[n] && HasMastered(needed[n]);
                if (shown[n] >= 0)
                {
                    kept.AsSpan(shown[n] * RecordBytes, RecordBytes).CopyTo(to);
                    if (masteredOne)
                        BitConverter.TryWriteBytes(to.Slice(RecordLevelAt), JobNeeds.MasteredShown);
                    continue;
                }
                // The job as the unit's list has it (the game's 19 and the mods', with their marks), else by what the
                // need knows it by.
                int job = JobNeeds.JobOf(needed[n]), closed = -1;
                for (int k = 0; k < _whole.Length; k++)
                    if (JobNeeds.Known(_whole[k] & JobBits, _mods) == needed[n])
                    {
                        job = _whole[k] & JobBits;
                        closed = (_whole[k] & JobNeeds.Unseen) != 0 ? Unseen : (_whole[k] & JobNeeds.Locked) != 0 ? 1 : 0;
                        break;
                    }
                bool stood;
                fixed (byte* record = to)
                    stood = Stand(job, closed, (nint)record);
                if (!stood)
                {
                    to.Clear();
                    BitConverter.TryWriteBytes(to.Slice(RecordClosed), Unseen);
                }
                else if (masteredOne)
                    BitConverter.TryWriteBytes(to.Slice(RecordLevelAt), JobNeeds.MasteredShown);
            }
            made.CopyTo(records);
            try
            {
                Windowed = true;
                NeedsWindow(screen);
            }
            finally
            {
                kept.CopyTo(records);
            }
        }

        /// <summary>The piece's places made again from the screen as it is filled: every place with a job whose
        /// record is open, in order, and which of them `place` is (below 0: none).</summary>
        int Open(nint piece, nint screen, int place)
        {
            int count = 0, on = -1;
            for (int k = 0; k < _count && k < Places; k++)
                if (*(int*)(screen + Records + k * RecordBytes + RecordClosed) == 0)
                {
                    if (k == place)
                        on = count;
                    *(int*)(piece + CyclePlaces + 4 * count++) = k;
                }
            *(int*)(piece + CycleCount) = count;
            if (on >= 0)
                *(int*)(piece + CycleOn) = on;
            return on;
        }

        /// <summary>The rows moved to start at `scroll`: the game's own filling, which lists through Listed.</summary>
        void Refill(int scroll)
        {
            _scroll = scroll;
            _mine = true;
            try
            {
                Fill();
            }
            finally
            {
                _mine = false;
            }
        }

        /// <summary>The cursor put on a place as the game's step puts it: its place, its picture where the place's
        /// box is, the step's caller told, the places drawn again.</summary>
        void Put(nint screen, nint told, int place)
        {
            *(int*)(screen + Cursor) = place;
            Place(screen, place);
            if (told != 0)
            {
                *(int*)(told + OutPlace) = place;
                *(byte*)(told + OutMoved) = 1;
            }
            Refresh(screen);
        }
    }
}
