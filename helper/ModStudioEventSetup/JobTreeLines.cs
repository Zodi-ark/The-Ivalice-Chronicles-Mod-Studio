// Mod Studio Framework: (1.50.0) the mods' jobs on Job Progress, the job tree's fourth step: the lines between the new
// jobs and the small icons of the game's jobs they need (the design Zodi signed off as a sketch on 13 November:
// "Between two new jobs: a line, with the level it asks, as the game draws its own. For each of the game's jobs a new
// job needs: a small icon of that job with the level, beside the new job's box."; his screenshots of that morning:
// "green line for level requirements already met. Red lines for job levels not yet met."; and, test 113 passed, "Feel
// free to move on to the lines/arrows and small icons"). The rest of the tree is JobTree.cs. Part of The Ivalice
// Chronicles Mod Studio, GPL-3.0.
//
// What the game does, measured in his program and his layout (dev/research/sidequests/job_lines.py holds each to its
// bytes):
// - A line of the tree is a reference to a small piece (LineRight is 10 by 10: a bar and an arrow's head past its
//   right edge) that the reference's size stretches: the layout's own lines of LineRight are 100, 124 and 300 wide.
//   LineBottomRight goes down, then right into a box's side; LineTopRight up, then right. A line of LineRight starts
//   62 right of the needed job's box, 82 below it, and its bar ends 42 before the next box.
// - The game's animations size a reference at run time (39 references of the game's layouts have size keys: the
//   windows of the select and sorting screens, the job screen's window of what a job needs, a line of the battle
//   result's), by the routine the framework has sized its roads' pictures with since 1.4.0 (Places.BoxSize).
// - A line's look is one of four animations of its piece, played by one routine (0x1347DC: the piece, whether it is
//   under the cursor, whether the need is met): Lock (dark), Unlock (light), LockOnCursor (red), UnlockOnCursor
//   (green), the other three stopped. A level's label has three (0x1348B0): Hide, and under the cursor ShowLock (red)
//   or ShowUnlock (green). With the cursor on a job the tree lights the lines of what it needs and of what needs it.
// - A label is one of the four TextBoardJobLv pieces of the needed job's box (right, left, below, above). Its number
//   is the text "Title", written as the tree is set up through a text setter bound to it in turn (a setter bound to
//   a box takes the box's key: JobTree.cs), after its LvMaster is stopped and its LvNum played.
// - The name board's writer (0x29B140) puts a job's icon in the picture box it is handed first (the icon's number
//   from the record's + 0x40, the question mark's where the job isn't to be seen: 0x29B054, 0x29BC00) and writes the
//   record's level (+ 0x44) through the setter it is handed third. The job screen's icon boxes are pictures of 44 by
//   44 showing their texture's part 0.
// What the framework does (only where the boxes stand):
// - **A line between two of the mods' jobs** where one needs the other, a copy of one of the game's own lines sized
//   and placed: in one row a straight line; in different rows a branch that runs down or up a corridor 180 left of
//   the needing job's column and turns into its side, off a trunk that runs from the needed job along its row (a
//   straight line with its head hidden; one for each needed job, to its furthest branch).
// - **A small icon for each of the game's jobs a job needs**, left of its box, three a row, the second row above the
//   first: a copy of a line's bar's picture box given the job's icon by the name board's writer, and under it a copy
//   of a level's label with the level asked, written by the same call; green where the unit has the level, red where
//   it doesn't, as the game's labels are.
// - **Their looks** (Refresh, once after the mods' jobs' records came): each line Lock or Unlock by whether the unit
//   has the level, a trunk Unlock where any of its branches is; a line or an icon of a job whose box isn't shown is
//   hidden. **Under the cursor** (Lit): the lines into the job the cursor is on and out of it are played as the game
//   plays its own, and by each line into it the needed job's right label shows the level asked.
//
// (1.51.0, his test 114: "In this example with the sage, two of the lines do not fully connect back to it. In these
// three screenshots you can see only the middle one fully connects back to the sage.") What was wrong: a lit branch
// starts at its corridor; the part of its way from the needed job's box to the corridor was the trunk, which was never
// lit and stood behind the straight line along the same row (Sage to Herald), dark; and a branch into a job a straight
// line also goes into (Sage to Evoker beside Duelist to Evoker) ended on that line. What the framework does now:
// - **Each branch has its own way out of the needed job's box**: a lead (a straight line with its head hidden) along
//   the needed job's row to the branch's corridor, a branch up 18 above the straight line's height (the next one up
//   18 higher: two places), a branch down 18 below it (the next 18 lower: three places), the nearest rows' nearest the
//   straight line; any more share the last place. So no branch runs along another line, and none crosses the straight
//   line out of its own job. The trunk is no longer made. A lead's look is its branch's.
// - **Each line into a job has its own place at the job's side**: a straight line the first (where the game's own go
//   in), then the branches from above, then those from below, each 18 lower than the one before (four places; any
//   more share the fourth).
// - **Each needed job has its own corridor into a column**: the jobs with branches into a column, by their rows, take
//   the corridor 180 left of the column, then 12 right of it, then 12 left of it (any more take those again).
// - **A lit line stands in front of every other line**: each line, and each branch's lead, has a lit copy of itself,
//   made after every other line so the copies stand in front of them all (the leads' copies, then the branches', then
//   the straight lines'), not drawn (its box's own opacity 0) except while its line is lit, and then played as the
//   game plays a lit line. The lines under them keep their looks.
//
// (1.52.0, his test 115: "two the the sages lines not bending correctly two of the lines make sharp angles ... both of
// those lines do not extend into the Sage correctly", and "in vanilla, two different jobs that share the same lv
// requirement from a job will share the same line ... They only get their own line if the lv requirements are
// different") What was wrong: a lead ran 3 past its branch's upright and met it square (no bend), and it started 62
// right of the needed job's box, beside its figure, where the figure's base doesn't reach at 18 above or below the
// straight line's height. Measured on his screenshots to the pixel (the game's own lines and test 115's): a straight
// line's stroke is rows 3 to 6 of its box; the bent pieces' strokes run 1 to 4 inside their outer edges (LineTopRight's
// upright and across, LineBottomRight's upright, LineRightBottom's across) or 5 to 2 inside (LineBottomRight's across,
// LineRightBottom's upright); a figure's base is an oval about 96 by 37 whose middle is 88 below the box's top, and it
// hides what is drawn behind it; the game flips its own Monk to Geomancer line about the box's middle. What the
// framework does now:
// - **One line for each needed job and level**: the jobs that need a job at the same level share one line from it,
//   which splits at its corridor (a branch up and a branch down each turn with the game's own bend, a job between the
//   bend and the furthest one has a branch off the upright, square, as the game's Squire to Archer and Knight); a job
//   needing it at another level has a line of its own.
// - **Every line starts under the needed job's figure** (32 right of its box), so it comes out of its base or from
//   behind it. Its own line's way out: the straight line's height for the line with a job in its row (where none, the
//   line reaching nearest), then 12 above it and 24 for lines up, 12 below and 24 for lines down, the line reaching
//   further the further out; past those a free one the other side (its line crosses the straight one's way out, never
//   runs on another's pixels); more share the last.
// - **Each bend is the game's own**: a line up or down is a copy of the game's right-then-down line (LineArcherNinja,
//   its head hidden) from under the figure to its corridor and down, or flipped (its scale's height -1, about its
//   middle, as the game flips its own) to turn up, and a copy of the game's down-then-right or up-then-right line
//   into the job, the two uprights on the same pixels, each running 2 into the other's bend.
// - **A line's corridor**: each line into a column its own, the line reaching further the further left (one: 187
//   left of the column; two: 6 either side; three to five: 12 apart about it; more share them).
// - **Lit as the game lights its own**: with the cursor on a job, its lines out and every line into it whole (the
//   other jobs a shared line goes to with it).
using System;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public sealed unsafe partial class JobTree
    {
        /// <summary>One thing a job needs: a job of the mods' (`Own` its place among the jobs given) or, where that
        /// is below 0, one of the game's (`Job` its number), at a level.</summary>
        public readonly struct Need
        {
            public int Own { get; }
            public int Job { get; }
            public int Level { get; }
            /// <summary>(1.55.2) Whether the job (one of the game's) is needed mastered: its small icon's label shows the
            /// game's mark of a job mastered (LvMaster), green only where the unit has mastered it (HasMastered). (1.56.0)
            /// Or a job of the mods' needed mastered: its line met, and the right label by it lit with that mark, only
            /// where the unit has mastered it.</summary>
            public bool Mastered { get; }

            public Need(int own, int job, int level, bool mastered = false)
            {
                Own = own;
                Job = job;
                Level = level;
                Mastered = mastered;
            }
        }

        /// <summary>A line as the layout's own LineRight stands (LineThiefNinja): where it starts from the needed
        /// job's box (1.52.0: the framework's start under the figure, LineStart), how tall its box is, and how far
        /// before the needing job's box its bar ends.</summary>
        public const int LineX = 62, LineY = 82, LineTall = 10, LineBefore = 42;
        /// <summary>(1.51.0) Where a line goes into its job's box: the first place where the game's own lines go in (a
        /// stroke's rows 85 to 88 below the box's top), each place after 18 lower (a head is 20 tall), four places, any
        /// more sharing the fourth (the fifth would reach the next row's icons). Corridors are 12 apart (a stroke is 4
        /// wide; the needing job's icons start right of the third, the needed job's label of a level ends about at the
        /// first). (1.52.0: 1.50.0's corridor 180 left of the column, a branch's box 8 left of it, its ends 89 and 84
        /// below the job's top and the trunk 3 past it are no longer used.)</summary>
        public const int EntryStep = 18, Entries = 4, LaneStep = 12;
        /// <summary>(1.51.0) The ways a needed job's lines leave its box, past the straight line's height: up two, (1.52.0)
        /// down two (12 apart, the second down's stroke at the base's soft edge).</summary>
        public const int ExitsUp = 2, ExitsDown = 2;
        /// <summary>(1.52.0) Where every line out of a job starts (so far right of its box: under its figure, at its
        /// middle), a straight line's stroke (rows 3 to 6 of its box), the ways out (12 apart: at the straight line's
        /// height the stroke comes out of the figure's base, at 12 above or below it too, at 24 from behind the figure
        /// or the base's edge), the corridors (a stroke's left column so far left of the column; 12 apart, five places:
        /// the furthest left stands under the needed job's label of a level, the furthest right 2 left of the icons), a bend
        /// (16 square), how far an upright runs into the other piece's bend, the bent pieces' strokes (from the edge
        /// they hug: 1 in, or 5 in from the right or the bottom), and where a branch off an upright starts (2 into
        /// the upright's stroke).</summary>
        public const int LineStart = 32, StrokeTop = 3, ExitStep = 12, CorridorStroke = 187, Corner = 16, Overlap = 2,
                         StrokeIn = 1, StrokeOut = 5, BranchIn = 2, LanePositions = 5;
        /// <summary>A box's middle (what its scale and turn are about), as the layouts' sizing keeps it (half its
        /// size, unless fixed: 0x3EF6B4).</summary>
        public const int BoxMiddleX = 0x48, BoxMiddleY = 0x4C;
        /// <summary>The small icons: three a row, each in a cell 52 wide and 58 tall, the first row's cells ending 10
        /// left of the box and starting 12 below its top, the next row above; an icon 36 by 36 from 8 right of its
        /// cell, its label 6 right and 36 below, drawn at nine tenths of its size (a label of a job's box is drawn
        /// at 1.2: its board would be 62 wide, wider than a cell; at 0.9 it is 47 by 27 and ends 5 above a line's
        /// head). A box's scale is two numbers at + 0x50 and + 0x54, and a box changed says so at + 0x95, as the
        /// layouts' own setting of a scale writes them (0x3EF738).</summary>
        public const int IconsARow = 3, IconCellWide = 52, IconCellTall = 58, IconsBefore = 10, IconsTop = 12, IconSize = 36,
                         IconX = 8, IconLabelX = 6, IconLabelY = 36, IconPart = 0, BoxScaleX = 0x50, BoxScaleY = 0x54,
                         BoxChanged = 0x95;
        public const float IconLabelScale = 0.9f;
        /// <summary>The names of what the framework adds: a line (the needing job, then which of its needs), an icon
        /// and its label; (1.51.0) a branch's lead, and the lit copies of a line and of a lead. (A needed job's trunk,
        /// MsqTrunk and its place, was 1.50.0's.)</summary>
        public const string LinePrefix = "MsqLine", IconPrefix = "MsqIcon", LevelPrefix = "MsqLv", LeadPrefix = "MsqLead",
                            LitPrefix = "MsqLit", LitLeadPrefix = "MsqLitLead";
        /// <summary>The game's lines copied: one of LineRight, one of LineBottomRight, one of LineTopRight; (1.52.0) one
        /// of LineRightBottom, a line's lead.</summary>
        public static readonly string[] LineModels = { "LineThiefNinja", "LineThiefDragoon", "LineDragoonDancer", "LineArcherNinja" };
        /// <summary>What a piece is: a straight line, a line's bend down or up into its job, (1.52.0) a branch off a
        /// line's upright into a job (a straight line), a line's lead from the needed job (its bend down, or flipped
        /// up); none.</summary>
        public const int StraightLine = 0, DownLine = 1, UpLine = 2, BranchLine = 3, LeadLine = 4, NoLine = -1;
        /// <summary>The game's line each kind of piece is a copy of (its place in LineModels).</summary>
        static int ModelOf(int kind) => kind == BranchLine ? StraightLine : kind == LeadLine ? 3 : kind;
        const string BarName = "Image02", HeadName = "Image05", RightLabel = "TextBoardJobLvR", TopLabel = "TextBoardJobLvT",
                     LabelText = "Title", LvMaster = "LvMaster", LvNum = "LvNum", ShowLine = "Show", HideLine = "Hide";

        /// <summary>The game's own: a box sized (the box, its width, its height), a line's look played and a label's
        /// (the piece, whether it is under the cursor, whether the need is met).</summary>
        public Action<nint, int, int> Size = (_, _, _) => { };
        public Action<nint, bool, bool> LinePlay = (_, _, _) => { }, LabelPlay = (_, _, _) => { };
        /// <summary>A needed job's record for the unit the screens are of, written to 0x94 bytes (its icon's number,
        /// the unit's level in it, whether it is open, locked or not to be seen): false where it isn't known.</summary>
        public Func<int, nint, bool> Stand = (_, _) => false;
        /// <summary>(1.55.2) Whether the unit the screens are of has mastered one of the game's jobs (by its number): every
        /// place of its skillset learned, as the framework's test asks of a need of it mastered.</summary>
        public Func<int, bool> HasMastered = _ => false;

        /// <summary>One need as it is drawn: a line (a mod's job) or an icon with its label (one of the game's).</summary>
        sealed class Drawn
        {
            public Need Need;
            public nint Line, Icon, Label, Text;
            /// <summary>(1.51.0) A branch's lead (its piece); the line's lit copy and the lead's (each its piece and its
            /// box).</summary>
            public nint Lead, Lit, LitBox, LitLead, LitLeadBox;
            /// <summary>A line that is a branch; whether the need is met; an icon's box given an icon (the
            /// game's writer gives one only once its texture is ready: until then the box would show the line's
            /// picture it was copied from, so it isn't shown).</summary>
            public bool Bent, Met, Given;
            /// <summary>(1.52.0) The level its line is of (the first need of that job: a second need of the same job
            /// draws nothing).</summary>
            public int Level = -1;
        }

        /// <summary>(1.52.0) How a need's line is drawn: its place at its job's side, its needed job's way out (so many
        /// places up, below 0, or down from the straight line's height), its corridor (its lane of the lanes of its
        /// column), whether it turns into its job and draws its line's lead (the furthest of its line into its column
        /// that way) or is a branch off the line's upright, and the level its line is of.</summary>
        public readonly struct Way
        {
            public int Entry { get; }
            public int Exit { get; }
            public int Lane { get; }
            public int Lanes { get; }
            public bool Far { get; }
            public int Level { get; }

            public Way(int entry, int exit, int lane, int lanes, bool far, int level)
            {
                Entry = entry;
                Exit = exit;
                Lane = lane;
                Lanes = lanes;
                Far = far;
                Level = level;
            }
        }

        Need[][] _needs = Array.Empty<Need[]>();
        Drawn[][] _drawn = Array.Empty<Drawn[]>();
        nint[] _rightLabel = Array.Empty<nint>(), _rightText = Array.Empty<nint>();
        readonly Dictionary<string, nint> _lineNames = new Dictionary<string, nint>();
        nint _labelSetter, _stand;
        int _labelKey;
        readonly List<nint> _added = new List<nint>();
        /// <summary>(1.51.0) Each line's place at its job's side, its corridor and its way out of the needed job's box,
        /// by the needing job and the needed; (1.52.0) whether it turns into its job, and its line's level.</summary>
        readonly Dictionary<(int Job, int From), Way> _ways = new Dictionary<(int, int), Way>();
        /// <summary>(1.52.0) How a need is drawn, for the checks: by the needing job and the needed (none: a straight
        /// line's way, its first place).</summary>
        public Way WayOf(int job, int from) => _ways.TryGetValue((job, from), out var way) ? way : new Way(0, 0, 0, 1, true, -1);
        bool _lines, _stale = true;
        int _lit = None, _retries;
        /// <summary>How many frames an icon whose texture isn't ready is asked for again before it is left out.</summary>
        public const int IconRetries = 300;

        /// <summary>Whether the lines and the icons stand.</summary>
        public bool Lines => _lines;
        /// <summary>The job whose lines are lit (None: none).</summary>
        public int LitJob => _lit;

        /// <summary>`needs[k]`: what job k needs. The plan is made of the needs that are jobs of the mods'.</summary>
        public JobTree(IList<Need[]> needs, IList<string> whose) : this(OwnOf(needs), whose, GameOf(needs))
        {
            int count = _plan.Count;
            _needs = new Need[count][];
            _drawn = new Drawn[count][];
            for (int k = 0; k < count; k++)
            {
                _needs[k] = needs[k];
                _drawn[k] = new Drawn[needs[k].Length];
                for (int n = 0; n < needs[k].Length; n++)
                    _drawn[k][n] = new Drawn { Need = needs[k][n] };
            }
            _rightLabel = new nint[count];
            _rightText = new nint[count];
            var all = new List<string>(LineModels) { BarName, HeadName, RightLabel, TopLabel, LabelText, LvMaster, LvNum, ShowLine, HideLine };
            for (int k = 0; k < count; k++)
            {
                for (int n = 0; n < needs[k].Length; n++)
                {
                    all.Add($"{LinePrefix}{k}_{n}");
                    all.Add($"{IconPrefix}{k}_{n}");
                    all.Add($"{LevelPrefix}{k}_{n}");
                    all.Add($"{LeadPrefix}{k}_{n}");
                    all.Add($"{LitPrefix}{k}_{n}");
                    all.Add($"{LitLeadPrefix}{k}_{n}");
                }
            }
            Arrange();
            int characters = 0;
            foreach (string name in all)
                characters += name.Length + 1;
            nint block = (nint)System.Runtime.InteropServices.NativeMemory.AllocZeroed((nuint)(all.Count * 16 + characters));
            byte* text = (byte*)block + all.Count * 16;
            for (int n = 0; n < all.Count; n++)
            {
                *(nint*)(block + n * 16) = (nint)text;
                _lineNames[all[n]] = block + n * 16;
                foreach (char c in all[n])
                    *text++ = (byte)c;
                *text++ = 0;
            }
            _stand = (nint)System.Runtime.InteropServices.NativeMemory.AllocZeroed(RecordBytes);
        }

        static IList<int[]> OwnOf(IList<Need[]> needs)
        {
            var own = new List<int[]>();
            foreach (var list in needs)
            {
                var of = new List<int>();
                foreach (var need in list)
                    if (need.Own >= 0)
                        of.Add(need.Own);
                own.Add(of.ToArray());
            }
            return own;
        }

        /// <summary>(1.52.0) Whether each job needs any of the game's jobs (the plan puts those that do after those
        /// that need nothing).</summary>
        static IList<bool> GameOf(IList<Need[]> needs)
        {
            var game = new List<bool>();
            foreach (var list in needs)
            {
                bool any = false;
                foreach (var need in list)
                    any |= need.Own < 0;
                game.Add(any);
            }
            return game;
        }

        nint LineName(string name) => _lineNames[name];

        /// <summary>What the log says where the lines and the icons are drawn, and where they can't be.</summary>
        public const string LinesLine =
            "Job Progress draws a line between two of the mods' jobs where one needs the other, and beside a job a small icon of "
            + "each of the game's jobs it needs with the level asked: green where the unit has the level, red where it doesn't.";
        public static string LinesNotLine(string why) =>
            $"Job Progress shows the mods' jobs without their lines and small icons: {why}.";
        /// <summary>Why the lines can't be drawn at all (a place of the program they need wasn't found): null where
        /// they can.</summary>
        public string? LinesWithout { get; set; }
        public static string LinesNotFound(IEnumerable<string> missing) =>
            $"{string.Join(", ", missing)} wasn't found in the program. A game update may have changed it: look for a newer Mod "
            + "Studio Framework";
        public static string LinesFaultLine(string what) =>
            $"the lines and small icons on Job Progress couldn't be drawn ({what}); the boxes show without them.";

        /// <summary>Whether any job needs anything drawn.</summary>
        bool AnyDrawn()
        {
            foreach (var list in _needs)
                if (list.Length > 0)
                    return true;
            return false;
        }

        /// <summary>(1.51.0) Each line's place at its job's side: for each job the lines into it from jobs of its mod,
        /// the straight one first, then those from above by their rows, then those from below by theirs, each the next
        /// place (Entries at most). (1.52.0) One line for each needed job and level, going to every job that needs it
        /// at that level (a job's first need of it: a second draws nothing). Each needed job's lines' ways out: every
        /// line with a job in its row at the straight line's height; where there is none, the line reaching nearest;
        /// the others, the nearer reaching first, up or down as their furthest job is (up where as far either way),
        /// each the next place out that way (ExitsUp, ExitsDown at most; past those, a free place the other side,
        /// and only where none is free the last place again). For each column the lines with a job in it
        /// out of their row, the further reaching the further left (then by the needed job's place, then the level):
        /// each its lane. Of a line's jobs in one column up (or down) the furthest turns into its job and draws the
        /// line's lead; the others are branches off its upright.</summary>
        void Arrange()
        {
            _ways.Clear();
            int count = _plan.Count;
            var level = new Dictionary<(int Job, int From), int>();
            var entry = new Dictionary<(int Job, int From), int>();
            for (int k = 0; k < count; k++)
            {
                var from = new List<int>();
                foreach (var need in _needs[k])
                    if (need.Own >= 0 && need.Own < count && need.Own != k && !from.Contains(need.Own))
                    {
                        from.Add(need.Own);
                        level[(k, need.Own)] = need.Level;
                    }
                int row = _plan.Row[k];
                int Side(int s) => _plan.Row[s] == row ? 0 : _plan.Row[s] < row ? 1 : 2;
                from.Sort((a, b) => Side(a) != Side(b) ? Side(a).CompareTo(Side(b)) : Before(a, b));
                for (int n = 0; n < from.Count; n++)
                    entry[(k, from[n])] = Math.Min(n, Entries - 1);
            }
            // The lines: each needed job and level, and the jobs that need it so.
            var lines = new SortedDictionary<(int From, int Level), List<int>>();
            foreach (var pair in level)
            {
                var key = (pair.Key.From, pair.Value);
                if (!lines.TryGetValue(key, out var into))
                    lines[key] = into = new List<int>();
                into.Add(pair.Key.Job);
            }
            int Rise(int k, int s) => _plan.Row[k] - _plan.Row[s];
            int Reach((int From, int Level) line)
            {
                int most = 0;
                foreach (int k in lines[line])
                    most = Math.Max(most, Math.Abs(Rise(k, line.From)));
                return most;
            }
            int Nearest((int From, int Level) line)
            {
                int least = int.MaxValue;
                foreach (int k in lines[line])
                    least = Math.Min(least, Math.Abs(Rise(k, line.From)));
                return least;
            }
            // Up where its furthest job up is at least as far as its furthest down.
            bool Up((int From, int Level) line)
            {
                int up = 0, down = 0;
                foreach (int k in lines[line])
                    if (Rise(k, line.From) < 0)
                        up = Math.Max(up, -Rise(k, line.From));
                    else
                        down = Math.Max(down, Rise(k, line.From));
                return up >= down;
            }
            // The ways out of each needed job.
            var exit = new Dictionary<(int From, int Level), int>();
            var sources = new SortedSet<int>();
            foreach (var line in lines.Keys)
                sources.Add(line.From);
            foreach (int s in sources)
            {
                var rest = new List<(int From, int Level)>();
                bool zero = false;
                foreach (var line in lines.Keys)
                    if (line.From == s)
                    {
                        if (Nearest(line) == 0)
                        {
                            exit[line] = 0;
                            zero = true;
                        }
                        else
                            rest.Add(line);
                    }
                rest.Sort((a, b) => Reach(a) != Reach(b) ? Reach(a).CompareTo(Reach(b))
                                    : Nearest(a) != Nearest(b) ? Nearest(a).CompareTo(Nearest(b)) : a.Level.CompareTo(b.Level));
                // A way out the other side where its own side's are taken (its line then crosses the straight
                // line's way out, never runs on another line's pixels); where both sides' are taken, its side's last.
                int ups = 0, downs = 0;
                foreach (var line in rest)
                {
                    if (!zero)
                    {
                        exit[line] = 0;
                        zero = true;
                        continue;
                    }
                    bool up = Up(line);
                    if (up ? ups >= ExitsUp && downs < ExitsDown : downs >= ExitsDown && ups < ExitsUp)
                        up = !up;
                    exit[line] = up ? -Math.Min(++ups, ExitsUp) : Math.Min(++downs, ExitsDown);
                }
            }
            // Each column's lanes: the lines with a job in it out of their row, the further reaching the further left.
            var lanes = new SortedDictionary<int, List<(int From, int Level)>>();
            var reachIn = new Dictionary<(int Column, int From, int Level), int>();
            foreach (var pair in lines)
                foreach (int k in pair.Value)
                {
                    if (Rise(k, pair.Key.From) == 0)
                        continue;
                    int column = _plan.Column[k];
                    if (!lanes.TryGetValue(column, out var of))
                        lanes[column] = of = new List<(int, int)>();
                    if (!of.Contains(pair.Key))
                        of.Add(pair.Key);
                    var at = (column, pair.Key.From, pair.Key.Level);
                    reachIn[at] = Math.Max(reachIn.TryGetValue(at, out int had) ? had : 0, Math.Abs(Rise(k, pair.Key.From)));
                }
            foreach (var pair in lanes)
            {
                int column = pair.Key;
                pair.Value.Sort((a, b) =>
                {
                    int ra = reachIn[(column, a.From, a.Level)], rb = reachIn[(column, b.From, b.Level)];
                    return ra != rb ? rb.CompareTo(ra) : a.From != b.From ? Before(a.From, b.From) : a.Level.CompareTo(b.Level);
                });
            }
            // Each need's way: of a line's jobs in one column up (or down), the furthest turns into its job.
            foreach (var pair in lines)
            {
                var line = pair.Key;
                foreach (int k in pair.Value)
                {
                    int rise = Rise(k, line.From);
                    bool far = true;
                    int lane = 0, of = 1;
                    if (rise != 0)
                    {
                        foreach (int other in pair.Value)
                            if (other != k && _plan.Column[other] == _plan.Column[k] && Math.Sign(Rise(other, line.From)) == Math.Sign(rise)
                                && (Math.Abs(Rise(other, line.From)) > Math.Abs(rise)
                                    || (Math.Abs(Rise(other, line.From)) == Math.Abs(rise) && Before(other, k) < 0)))
                                far = false;
                        var column = lanes[_plan.Column[k]];
                        lane = column.IndexOf(line);
                        of = column.Count;
                    }
                    _ways[(k, line.From)] = new Way(entry[(k, line.From)], exit[line], lane, of, far, line.Level);
                }
            }
        }

        /// <summary>Which of two jobs comes first by where they stand: the higher row, then the column further left.</summary>
        int Before(int a, int b)
            => _plan.Row[a] != _plan.Row[b] ? _plan.Row[a].CompareTo(_plan.Row[b])
               : _plan.Column[a] != _plan.Column[b] ? _plan.Column[a].CompareTo(_plan.Column[b]) : a.CompareTo(b);

        /// <summary>(1.52.0) A lane's corridor: the left column of its upright's stroke (one lane 187 left of the
        /// column; two 6 either side of it; three to five 12 apart about it; more share those five).</summary>
        public static int Upright(int column, int lane, int lanes)
        {
            int used = Math.Min(Math.Max(lanes, 1), LanePositions);
            return column - CorridorStroke + LaneStep * (lane % used) - LaneStep * (used - 1) / 2;
        }

        /// <summary>Where a need's line stands: its kind (a straight line, its bend down or up into its job, or a branch
        /// off its line's upright), its place and its size. (1.52.0) A straight line from under the needed job's
        /// figure at the straight line's height to 42 before the job; a branch from its upright's stroke at its place
        /// at the job's side; a bend: its upright on its corridor's stroke, its across at its place at the job's side
        /// (LineTopRight's 1 below its top, LineBottomRight's 5 above its bottom), running 2 into its lead's bend.</summary>
        public (int Kind, int X, int Y, int Wide, int Tall) LineAt(int job, int from)
        {
            int xk = _plan.X(job), yk = _plan.Y(job), xs = _plan.X(from), ys = _plan.Y(from);
            var way = WayOf(job, from);
            int start = xs + LineStart, exit = ys + LineY + StrokeTop + ExitStep * way.Exit,
                place = yk + LineY + StrokeTop + EntryStep * way.Entry;
            if (yk == ys)
                return (StraightLine, start, exit - StrokeTop, xk - LineBefore - start, LineTall);
            int upright = Upright(xk, way.Lane, way.Lanes);
            if (!way.Far)
                return (BranchLine, upright + BranchIn, place - StrokeTop, xk - LineBefore - (upright + BranchIn), LineTall);
            int left = upright - StrokeIn, wide = xk - LineBefore - left;
            if (yk < ys)
                return (UpLine, left, place - StrokeIn, wide, exit + StrokeOut - Corner + Overlap - (place - StrokeIn));
            int top = exit - StrokeIn + Corner - Overlap;
            return (DownLine, left, top, wide, place + StrokeOut - top);
        }

        /// <summary>(1.52.0) Where a line's lead stands, drawn with the need that turns into its job: a copy of the
        /// game's right-then-down line from under the needed job's figure, its across at the line's way out (1 below
        /// its top), its upright on the corridor's stroke (5 left of its right), down to 2 into the bend into the job;
        /// for a line up, flipped (its across 5 above its bottom) up to 2 into that bend (3 where its height would be
        /// odd). None for a straight line or a branch.</summary>
        public (int Kind, int X, int Y, int Wide, int Tall, bool Flip) LeadAt(int job, int from)
        {
            int xk = _plan.X(job), yk = _plan.Y(job), xs = _plan.X(from), ys = _plan.Y(from);
            var way = WayOf(job, from);
            if (yk == ys || !way.Far)
                return (NoLine, 0, 0, 0, 0, false);
            int start = xs + LineStart, exit = ys + LineY + StrokeTop + ExitStep * way.Exit,
                place = yk + LineY + StrokeTop + EntryStep * way.Entry, wide = Upright(xk, way.Lane, way.Lanes) + StrokeOut - start;
            if (yk < ys)
            {
                // Its height even: its middle is kept whole (half its size), so an odd height would flip a row high.
                int top = place - StrokeIn + Corner - Overlap;
                top -= (exit + StrokeOut - top) % 2;
                return (LeadLine, start, top, wide, exit + StrokeOut - top, true);
            }
            return (LeadLine, start, exit - StrokeIn, wide, place + StrokeOut - Corner + Overlap - (exit - StrokeIn), false);
        }

        public (int X, int Y) IconCell(int job, int which)
            => (_plan.X(job) - IconsBefore - IconCellWide * (which % IconsARow + 1), _plan.Y(job) + IconsTop - IconCellTall * (which / IconsARow));

        /// <summary>The lines, the leads, their lit copies, the labels and the icons made in a tree whose boxes were
        /// just made: null, or why not. Whatever of them the layout already holds by its name is kept.</summary>
        string? BuildLines(nint tree, nint piece, nint layouts, nint boxes, nint layer, nint model)
        {
            int count = _plan.Count;
            var models = new nint[LineModels.Length];
            for (int m = 0; m < models.Length; m++)
            {
                models[m] = Named(boxes, LineName(LineModels[m]));
                if (models[m] == 0 || *(int*)(models[m] + Marker.BoxKind) != MapPieces.ReferenceKind
                    || *(nint*)(models[m] + MapPieces.BoxParent) == 0)
                    return $"the tree's layout has no line {LineModels[m]} to copy";
            }
            nint barPiece = Child(piece, LineName(LineModels[StraightLine]));
            nint bar = barPiece == 0 ? 0 : Named(barPiece + Marker.PieceTree, LineName(BarName));
            nint first = Child(piece, GameName(0));
            nint labelModel = first == 0 ? 0 : Named(first + Marker.PieceTree, LineName(TopLabel));
            if (bar == 0 || *(int*)(bar + Marker.BoxKind) != Marker.PictureKind)
                return "a line of the tree's layout has no picture to copy for an icon";
            if (labelModel == 0 || *(int*)(labelModel + Marker.BoxKind) != MapPieces.ReferenceKind)
                return "the game's first job's box has no label of a level to copy";
            if (_labelSetter == 0)
                _labelSetter = Setter();
            if (_labelSetter == 0)
                return "a label's text couldn't be made ready";

            // One of the layout's boxes by its name, or a copy of a model named so, placed and put in a layer.
            nint Made(string name, nint from, nint into, nint after, int x, int y, out bool isNew)
            {
                nint box = Named(boxes, LineName(name));
                isNew = box == 0;
                if (box != 0)
                    return box;
                box = Copy(layouts, from);
                if (box == 0)
                    return 0;
                Rename(box, Characters(LineName(name)));
                Move(box, x, y);
                Add(into, box, after);
                _added.Add(box);
                return box;
            }

            // A copy of a line placed, sized and found by its piece; a lead's head no longer drawn; a lit copy not drawn
            // until its line is lit; (1.52.0) a lead up flipped about its middle, as the game flips its own.
            nint straight = models[StraightLine], lines = *(nint*)(straight + MapPieces.BoxParent);
            string? Copied(string name, nint from, nint after, int x, int y, int wide, int tall, bool lead, bool lit, bool flip,
                           out nint box, out nint line)
            {
                line = 0;
                box = Made(name, from, lines, after, x, y, out bool isNew);
                if (box == 0)
                    return "a copy of a line wasn't made";
                if (isNew)
                {
                    Size(box, wide, tall);
                    if (flip)
                        Flip(box, wide, tall);
                }
                if (lit)
                    *(float*)(box + MapRoads.BoxOpacity) = 0f;
                line = Child(piece, LineName(name));
                if (line == 0)
                    return "a copy of a line has no piece";
                nint head = lead ? Named(line + Marker.PieceTree, LineName(HeadName)) : 0;
                if (head != 0)
                    *(float*)(head + MapRoads.BoxOpacity) = 0f;
                return null;
            }

            // (1.51.0) The leads first, so the lines made after them stand in front of them. (1.52.0) A line's lead is
            // drawn with the need that turns into its job; a job's second need of the same job draws nothing.
            for (int k = 0; k < count; k++)
            {
                var seen = new List<int>();
                for (int n = 0; n < _drawn[k].Length; n++)
                {
                    var drawn = _drawn[k][n];
                    var need = drawn.Need;
                    drawn.Line = drawn.Icon = drawn.Label = drawn.Text = drawn.Lead = drawn.Lit = drawn.LitBox = drawn.LitLead = drawn.LitLeadBox = 0;
                    drawn.Bent = false;
                    drawn.Level = -1;
                    if (need.Own < 0 || need.Own >= count || need.Own == k || seen.Contains(need.Own))
                        continue;
                    seen.Add(need.Own);
                    drawn.Level = WayOf(k, need.Own).Level;
                    drawn.Bent = LineAt(k, need.Own).Kind != StraightLine;
                    var lead = LeadAt(k, need.Own);
                    if (lead.Kind == NoLine)
                        continue;
                    string? why = Copied($"{LeadPrefix}{k}_{n}", models[ModelOf(LeadLine)], straight, lead.X, lead.Y, lead.Wide, lead.Tall,
                                         true, false, lead.Flip, out _, out drawn.Lead);
                    if (why != null)
                        return why;
                }
            }
            // The lines, and the right labels of the jobs they start from.
            _labelKey = 0;
            for (int k = 0; k < count; k++)
            {
                _rightLabel[k] = _rightText[k] = 0;
                for (int n = 0; n < _drawn[k].Length; n++)
                {
                    var drawn = _drawn[k][n];
                    var need = drawn.Need;
                    if (drawn.Level < 0)
                        continue;
                    var at = LineAt(k, need.Own);
                    nint from = models[ModelOf(at.Kind)];
                    string name = $"{LinePrefix}{k}_{n}";
                    nint box = Made(name, from, *(nint*)(from + MapPieces.BoxParent), from, at.X, at.Y, out bool isNew);
                    if (box == 0)
                        return "a copy of a line wasn't made";
                    if (isNew)
                        Size(box, at.Wide, at.Tall);
                    drawn.Line = Child(piece, LineName(name));
                    if (drawn.Line == 0)
                        return "a copy of a line has no piece";
                }
            }
            // (1.51.0) The lit copies, made after every other line so they stand in front of them all, each put right
            // after the game's straight line copied: the leads' copies, then the bent lines' and branches', then the
            // straight lines'.
            for (int pass = 0; pass < 3; pass++)
                for (int k = 0; k < count; k++)
                    for (int n = 0; n < _drawn[k].Length; n++)
                    {
                        var drawn = _drawn[k][n];
                        if (drawn.Line == 0 || (pass == 0 ? drawn.Lead == 0 : pass == 2 ? drawn.Bent : !drawn.Bent))
                            continue;
                        string? why;
                        if (pass == 0)
                        {
                            var lead = LeadAt(k, drawn.Need.Own);
                            why = Copied($"{LitLeadPrefix}{k}_{n}", models[ModelOf(LeadLine)], straight, lead.X, lead.Y, lead.Wide, lead.Tall,
                                         true, true, lead.Flip, out drawn.LitLeadBox, out drawn.LitLead);
                        }
                        else
                        {
                            var at = LineAt(k, drawn.Need.Own);
                            why = Copied($"{LitPrefix}{k}_{n}", models[ModelOf(at.Kind)], straight, at.X, at.Y, at.Wide, at.Tall, false, true,
                                         false, out drawn.LitBox, out drawn.Lit);
                        }
                        if (why != null)
                            return why;
                    }
            for (int k = 0; k < count; k++)
            {
                bool needed = false;
                for (int other = 0; other < count && !needed; other++)
                    foreach (var drawn in _drawn[other])
                        needed |= drawn.Line != 0 && drawn.Need.Own == k;
                if (!needed)
                    continue;
                nint label = Child(_piece[k], LineName(RightLabel));
                nint text = label == 0 ? 0 : Named(label + Marker.PieceTree, LineName(LabelText));
                if (label == 0 || text == 0 || *(int*)(text + Marker.BoxKind) != TextKind)
                    return "a job's box has no label of a level at its right";
                _rightLabel[k] = label;
                _rightText[k] = text;
                Ready(label, text, _piece[k]);
            }
            // The icons, each with its label.
            for (int k = 0; k < count; k++)
            {
                int which = 0;
                for (int n = 0; n < _drawn[k].Length; n++)
                {
                    var drawn = _drawn[k][n];
                    if (drawn.Need.Own >= 0)
                        continue;
                    var cell = IconCell(k, which++);
                    nint icon = Made($"{IconPrefix}{k}_{n}", bar, layer, model, cell.X + IconX, cell.Y, out bool isNew);
                    if (icon == 0)
                        return "a copy of a picture wasn't made for an icon";
                    if (*(int*)(icon + Marker.BoxKind) != Marker.PictureKind)
                        return "the box made for an icon can't show a picture";
                    if (isNew)
                    {
                        *(int*)(icon + Marker.PicturePart) = IconPart;
                        *(int*)(icon + MapRoads.BoxColorNumber) = 0;
                        *(uint*)(icon + Marker.BoxColor) = MapRoads.White;
                        *(byte*)(icon + MapPieces.BoxVisible) = 1;
                        Size(icon, IconSize, IconSize);
                    }
                    *(float*)(icon + MapRoads.BoxOpacity) = 0f;
                    drawn.Given = !isNew;
                    string name = $"{LevelPrefix}{k}_{n}";
                    nint box = Made(name, labelModel, layer, model, cell.X + IconLabelX, cell.Y + IconLabelY, out bool newLabel);
                    if (box == 0)
                        return "a copy of a level's label wasn't made";
                    if (newLabel)
                    {
                        *(float*)(box + BoxScaleX) = IconLabelScale;
                        *(float*)(box + BoxScaleY) = IconLabelScale;
                        *(byte*)(box + BoxChanged) = 1;
                    }
                    nint label = Child(piece, LineName(name));
                    nint text = label == 0 ? 0 : Named(label + Marker.PieceTree, LineName(LabelText));
                    if (label == 0 || text == 0 || *(int*)(text + Marker.BoxKind) != TextKind)
                        return "a copy of a level's label doesn't hold its number";
                    drawn.Icon = icon;
                    drawn.Label = label;
                    drawn.Text = text;
                    Ready(label, text, first);
                    // (1.55.2) A job needed mastered: the game's mark of a job mastered in place of its level.
                    if (drawn.Need.Mastered)
                        Master(label);
                }
            }
            return null;
        }

        /// <summary>(1.52.0) A copy flipped top to bottom about its middle, as the game flips its own (LineMonkGeomancer:
        /// its scale's width -1 and a half turn, which comes to the same): its middle where the layouts' sizing keeps it
        /// (half its size), its scale's height -1, and the box changed, as the layouts' own setting of a scale writes
        /// them (0x3EF738, which keeps the sign).</summary>
        static void Flip(nint box, int wide, int tall)
        {
            *(int*)(box + BoxMiddleX) = wide / 2;
            *(int*)(box + BoxMiddleY) = tall / 2;
            *(float*)(box + BoxScaleX) = 1f;
            *(float*)(box + BoxScaleY) = -1f;
            *(byte*)(box + BoxChanged) = 1;
        }

        /// <summary>A label made ready as the tree's setup makes its own: its LvMaster stopped, its LvNum played, and
        /// not shown. The key its number is written from is remembered from the first label that still has one (a
        /// label the tree's setup wrote has given its key away): this label's, the others of its box (`within`), or
        /// the key the tree's own setter holds for a level.</summary>
        void Ready(nint label, nint text, nint within)
        {
            if (_labelKey == 0)
                _labelKey = *(int*)(text + TextKey);
            foreach (string other in new[] { TopLabel, RightLabel })
            {
                if (_labelKey != 0 || within == 0)
                    break;
                nint piece = Child(within, LineName(other));
                nint title = piece == 0 ? 0 : Named(piece + Marker.PieceTree, LineName(LabelText));
                if (title != 0)
                    _labelKey = *(int*)(title + TextKey);
            }
            if (_labelKey == 0 && _tree != 0)
                _labelKey = *(int*)(_tree + TreePlaces + PlaceSetter + SetterKey);
            Stop(label, LineName(LvMaster));
            Play(label, LineName(LvNum));
            LabelPlay(label, false, false);
        }

        /// <summary>(1.55.2) A label of a job needed mastered: its LvNum stopped and its LvMaster played, which hides its "Lv."
        /// and its number and shows the game's mark of a job mastered (the piece's Image00, ui_master_uitx's part 0: the
        /// stars the job screen shows over a job mastered, its Unit's Star). The layout has it on the tree's labels and name
        /// boards, but the game's own code only ever stops it there (0x133B74; its name board plays LvNum or LvNone).</summary>
        void Master(nint label)
        {
            Stop(label, LineName(LvNum));
            Play(label, LineName(LvMaster));
        }

        /// <summary>(1.56.0) A label showing a level again ("Lv." and its number): its LvMaster stopped and its LvNum
        /// played, as Ready leaves it; a needed job's right label is lit for each line into the cursor's job in turn.</summary>
        void Leveled(nint label)
        {
            Stop(label, LineName(LvMaster));
            Play(label, LineName(LvNum));
        }

        /// <summary>A number written on a label, and an icon given where one is handed, by the name board's writer:
        /// the label's text given its key again (a setter bound takes it), the framework's one setter for labels
        /// bound to it, and the writer handed the icon's box, no title, the setter, and a record of that icon and
        /// that level.</summary>
        void WriteLabel(nint tree, nint text, int level, nint icon, int iconNumber, bool unseen)
        {
            if (_labelKey != 0 && *(int*)(text + TextKey) == 0)
                *(int*)(text + TextKey) = _labelKey;
            Bind(_labelSetter, text);
            byte* record = (byte*)_stand;
            for (int n = 0; n < RecordBytes; n++)
                record[n] = 0;
            *(int*)(record + RecordIcon) = iconNumber;
            *(int*)(record + RecordLevel) = level;
            nint* writer = (nint*)_writer;
            for (int n = 0; n < WriterPlaces; n++)
                writer[n] = 0;
            writer[WriterIcon] = icon;
            writer[WriterLevel] = _labelSetter;
            Write(tree + TreeWriter, _writer, _stand, unseen);
        }

        /// <summary>A record's icon's number; the name board's writer's first place, an icon's box.</summary>
        public const int RecordIcon = 0x40, WriterIcon = 0;

        /// <summary>Whether the unit has what a need asks: the needed job open to it, at the level or more; (1.56.0)
        /// asked mastered, mastered (HasMastered).</summary>
        bool MetOwn(Need need)
        {
            if (need.Own < 0 || need.Own >= _plan.Count || !_given[need.Own])
                return false;
            byte* record = (byte*)_records + need.Own * RecordBytes;
            return *(int*)(record + RecordClosed) == 0
                   && (need.Mastered ? HasMastered(need.Job) : *(int*)(record + RecordLevel) >= need.Level);
        }

        /// <summary>The lines' and the icons' looks after the mods' jobs' records came (or went): each line shown
        /// where both its jobs' boxes are, Unlock where the need is met and Lock where it isn't, a branch's lead with
        /// it (1.51.0), its lit copies not drawn; each icon and its label where its job's box is shown, the icon the
        /// needed job's (the question mark where it isn't to be seen), the label the level asked, green where met and
        /// red where not. Then the cursor's job's lines are lit again.</summary>
        void Refresh(nint tree)
        {
            _stale = false;
            if (!_lines)
                return;
            int count = _plan.Count;
            bool again = false;
            for (int k = 0; k < count; k++)
                foreach (var drawn in _drawn[k])
                {
                    var need = drawn.Need;
                    if (drawn.Line != 0)
                    {
                        bool shown = _given[k] && _given[need.Own];
                        drawn.Met = shown && MetOwn(need);
                        foreach (nint line in new[] { drawn.Line, drawn.Lead })
                            if (line != 0)
                            {
                                LineShown(line, shown);
                                if (shown)
                                    LinePlay(line, false, drawn.Met);
                            }
                        // (1.51.0) Its lit copies shown or hidden with it, and not drawn until it is lit.
                        foreach (var (over, box) in new[] { (drawn.Lit, drawn.LitBox), (drawn.LitLead, drawn.LitLeadBox) })
                            if (over != 0)
                            {
                                LineShown(over, shown);
                                *(float*)(box + MapRoads.BoxOpacity) = 0f;
                            }
                    }
                    else if (drawn.Icon != 0)
                    {
                        bool shown = _given[k];
                        if (!shown)
                        {
                            *(float*)(drawn.Icon + MapRoads.BoxOpacity) = 0f;
                            LabelPlay(drawn.Label, false, false);
                            continue;
                        }
                        byte* record = (byte*)_stand;
                        bool known = Stand(need.Job, _stand);
                        int closed = known ? *(int*)(record + RecordClosed) : Unseen;
                        int icon = known ? *(int*)(record + RecordIcon) : 0;
                        // (1.55.2) A job needed mastered is met only where the unit has mastered it.
                        drawn.Met = known && closed == 0
                                    && (need.Mastered ? HasMastered(need.Job) : *(int*)(record + RecordLevel) >= need.Level);
                        // The writer gives the box its icon's texture parts only where they are ready and differ from
                        // the box's: the box's name of its parts changes as it does.
                        nint was = *(nint*)(drawn.Icon + Marker.PictureParts);
                        WriteLabel(tree, drawn.Text, need.Level, drawn.Icon, icon, closed == Unseen);
                        if (*(nint*)(drawn.Icon + Marker.PictureParts) != was)
                            drawn.Given = true;
                        *(float*)(drawn.Icon + MapRoads.BoxOpacity) = drawn.Given ? 1f : 0f;
                        again |= !drawn.Given;
                        LabelPlay(drawn.Label, true, drawn.Met);
                    }
                }
            for (int k = 0; k < count; k++)
                if (_rightLabel[k] != 0)
                    LabelPlay(_rightLabel[k], false, false);
            int lit = _lit;
            _lit = None;
            Lit(tree, lit);
            // An icon not given yet is asked for again the next frame, for a while.
            if (!again)
                _retries = 0;
            else if (_retries < IconRetries)
            {
                _retries++;
                _stale = true;
            }
        }

        /// <summary>A line's piece shown or not, by the piece's own Show and Hide.</summary>
        void LineShown(nint line, bool shown)
        {
            Stop(line, LineName(shown ? HideLine : ShowLine));
            Play(line, LineName(shown ? ShowLine : HideLine));
        }

        /// <summary>The cursor's job's lines lit, as the game lights a place's: the lines into `job` and out of it
        /// played under the cursor (red or green), the job's before played back; by each line into it, the needed
        /// job's right label shows the level asked. None: no job of the mods' is under the cursor. (1.51.0) A line is
        /// lit by its lit copy, and a branch by its lead's with it, each drawn and played under the cursor in front of
        /// every other line, and no longer drawn as the cursor leaves; the lines under them keep their looks. (1.52.0)
        /// A line into the job is lit whole, as the game lights its own: the other jobs a line it shares goes to with
        /// it.</summary>
        void Lit(nint tree, int job)
        {
            if (!_lines || job == _lit)
                return;
            int count = _plan.Count;
            for (int pass = 0; pass < 2; pass++)
            {
                int of = pass == 0 ? _lit : job;
                bool on = pass == 1;
                if (of < 0 || of >= count || (on && !_given[of]))
                    continue;
                // The lines into it: each needed job and the level its line is of.
                var into = new List<(int From, int Level)>();
                foreach (var drawn in _drawn[of])
                    if (drawn.Line != 0)
                        into.Add((drawn.Need.Own, drawn.Level));
                for (int k = 0; k < count; k++)
                    foreach (var drawn in _drawn[k])
                    {
                        var need = drawn.Need;
                        if (drawn.Line == 0 || (k != of && need.Own != of && !into.Contains((need.Own, drawn.Level)))
                            || !_given[k] || !_given[need.Own])
                            continue;
                        foreach (var (lit, box) in new[] { (drawn.Lit, drawn.LitBox), (drawn.LitLead, drawn.LitLeadBox) })
                            if (lit != 0)
                            {
                                if (on)
                                    LinePlay(lit, true, drawn.Met);
                                *(float*)(box + MapRoads.BoxOpacity) = on ? 1f : 0f;
                            }
                        if (k != of || _rightLabel[need.Own] == 0)
                            continue;
                        if (on)
                        {
                            WriteLabel(tree, _rightText[need.Own], need.Level, 0, 0, false);
                            // (1.56.0) A job of the mods' needed mastered: the game's mark of a job mastered by its line.
                            if (need.Mastered)
                                Master(_rightLabel[need.Own]);
                            else
                                Leveled(_rightLabel[need.Own]);
                        }
                        LabelPlay(_rightLabel[need.Own], on, drawn.Met);
                    }
            }
            _lit = job >= 0 && job < count && _given[job] ? job : None;
        }

        /// <summary>Each frame the tree is shown, and as it comes up: the looks brought up where the records changed,
        /// and the cursor's job's lines lit. A fault turns the lines off and is said once; the boxes stay.</summary>
        void DrawLines(nint tree)
        {
            if (!_lines)
                return;
            try
            {
                if (_stale)
                    Refresh(tree);
                int job = *(int*)(tree + TreeCursor) - FirstPlace;
                Lit(tree, job >= 0 && job < _plan.Count && _given[job] ? job : None);
            }
            catch (Exception e)
            {
                _lines = false;
                Once(LinesFaultLine($"{e.GetType().Name}: {e.Message}"));
            }
        }

        /// <summary>Where the lines and the icons can't be finished, what was made of them is put away: each box added
        /// is no longer drawn (its own opacity, which no animation of its piece sets).</summary>
        void PutAway()
        {
            foreach (nint box in _added)
                *(float*)(box + MapRoads.BoxOpacity) = 0f;
        }

        /// <summary>The lines forgotten with the boxes: they went with their layout.</summary>
        void ForgetLines()
        {
            _added.Clear();
            _lines = false;
            _stale = true;
            _lit = None;
            _retries = 0;
            Array.Clear(_rightLabel, 0, _rightLabel.Length);
            Array.Clear(_rightText, 0, _rightText.Length);
            foreach (var list in _drawn)
                foreach (var drawn in list)
                    drawn.Line = drawn.Icon = drawn.Label = drawn.Text = drawn.Lead = drawn.Lit = drawn.LitBox = drawn.LitLead = drawn.LitLeadBox = 0;
        }
    }
}
