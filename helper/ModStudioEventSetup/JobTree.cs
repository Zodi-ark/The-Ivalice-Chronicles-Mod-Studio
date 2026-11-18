// Mod Studio Framework: (1.49.0) the mods' jobs on Job Progress, the job tree: its second and third steps, the new
// jobs' boxes, the cursor and the view (Zodi's words of 13 November: "All jobs new and vanilla jobs together on the Job
// Progress (the tree). Ideally nothing about the original Job Progress but in addendum to it our framework adds boxes
// and lines for the new jobs around the original job progress."; his choice of the sketch, "Slide to the side"; and of
// that morning, a separate page allowed "if you are have trouble developing the view sliding over": the slide is what
// is built). Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// What the game does, measured in his program (17 September 2026, read as data;
// dev/research/sidequests/job_boxes.py holds each to its bytes):
//
// Job Progress is one drawing (ffto_job_tree.uib): the piece JobTree holds a layer, LayerRoot, with 20 boxes named for
// the jobs, each a reference to the piece UnitJob (the unit's figure, the ring under the cursor, the mark of the job
// worn, a name board, four labels of a level), and the lines; the stone background is another box of JobTree, not in
// that layer. The tree's memory (0x2FD8 bytes, made with the job screen) keeps 20 places of 0x1C8 bytes from + 0x48
// (a place's piece at + 0, its figure's picture box at + 8, its name board at + 0x10, the board's title at + 0x18, a
// text setter of 0x68 bytes for its level at + 0x20), each place's eight directions from + 0x1F0 (two boxes a
// direction, each a place and whether the move goes round the board; 20 for none), 20 job records of 0x94 bytes from
// + 0x23E8, its JobTree piece at + 0x2F78, the place the cursor is on at + 0x2FC8.
//
// - The filling of the job screen (0x368424) builds each listed job's record in line (its name, icon, the unit's
//   level, whether it is open, the figure the unit would have in it) and hands it to the job screen's place
//   (0x12EC5C) and to the tree's (0x13420C), both by its number in the list. The tree's giving copies the record,
//   numbers the figure 0x50 plus the place (the figures' 256 numbered slots: the job screen's are 0x3D to 0x4F),
//   finishes the figure's record (0xFB328) and gives it to the figures' keeper with the place's picture box
//   (0xED9F8), writes the name and the level on the board (0x29B140), plays the board's LvNum or LvNone, the piece's
//   Unlock, LockReleased or LockUnreleased by the record's + 0x84, and its ShowUse or HideUse by + 0x8D.
// - A box tagged 0x12 (+ 0x220, its place at + 0x224) that is focused is, to the tree's handler (0x133DDC), the place
//   the cursor is on; the handler lights that place's lines only for a place up to 19. The ring, the larger figure and
//   the name board are the piece's own CursorOver, which the layouts play for whatever piece is focused.
// - The update (0x133FA4, called by the unit screens' holder each frame the tree is shown, the holder going straight
//   to its end after): confirm (the action 0x1A asked of 0xFC598, or a click noted at + 0x2FD1) tells the tree's
//   receiver (+ 0x10, its function at + 0x30) 0x80 with the place and makes the menu's mode 0x578, the job screen's,
//   which puts its cursor on that place (0x12F7F4); cancel makes the mode 0x578; a direction focuses the piece of the
//   place the cursor's place's directions name (0x1D2240). Right from the board's rightmost boxes goes round to its
//   leftmost.
// - As the menu's mode becomes 0x581 the tree's showing (0x133F30) focuses the place of the job the unit is in.
//
// What the framework does:
//
// - **The records.** The game makes a record only for a job it lists, and it lists 19. After each of the game's own
//   fillings (JobScreen.After) the framework has the game's filling run again for the mods' jobs alone, 18 at a time
//   after the unit's first job (the list's first is treated apart), with the two calls that touch the job screen left
//   out (its readying and its giving of a job to a place: a number the native code reads) and the list put back after:
//   the filling's call for the tree hands each record here (Harvested). Nothing of the screen changes.
// - **The boxes** (Build): as the first record comes, a copy of the game's first job's box for each of the mods' jobs,
//   made by the layouts' own copy of a box as the world map's places are since 1.3.0 (MapPieces.cs), named MsqJob and
//   its number, put in the same layer right of the board in columns of five (a job after the jobs of its mod it
//   needs: Plan), tagged 0x12 with a place from 20 on and telling the tree as the game's boxes do. A text setter of
//   the framework's own is bound to each one's level.
// - **A job given to its box** (Give): what the tree's giving does, with a figure's slot of the framework's own, taken
//   from numbers no screen was found to use and only while the keeper has it free (Slots), kept while it is still the
//   box's.
// - **The cursor** (Update, in place of the game's update): confirm on one of the mods' jobs shows its row on the job
//   screen (JobScreen.Show) and tells the receiver its place there, as the game does for its own. Anything else is
//   the game's own update, run over a copy of the tree in which the cursor's place's directions name the boxes
//   beside it: on one of the mods' jobs, its neighbours in the columns; on one of the game's rightmost boxes, right
//   goes to the first column in place of going round the board. The game's update reads the keys, skips nothing of
//   its own and focuses the piece; the tree's own handler then takes the box as the place the cursor is on.
// - **The view** (Slide): LayerRoot is moved left so the columns the cursor is in stand on the board, four at a time,
//   a part of the way each frame; back as the cursor comes back. No animation of the layout sets that layer's place.
// - **As the tree is shown** (Shown, after the game's): where the job the unit is in is a mod's, its box is focused,
//   and the view is put where the cursor is at once.
//
// The lines between the new jobs and the small icons of the game's jobs they need: JobTreeLines.cs (1.50.0).
using System;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public sealed unsafe partial class JobTree
    {
        // --- the plan: where each job's box stands, and where the cursor goes from it ------------------------------

        /// <summary>The boxes in a column, the columns in a view; where the first column and row stand in the layer
        /// that holds the game's boxes (which is 1,920 wide, its last column of boxes at 1,628), and how far apart
        /// columns and rows are: the sketch he signed off (dev/research/sidequests/tree_mock.py: columns from 1,960
        /// every 340, rows from 120 every 175). How far the layer moves for the first view of the mods' jobs and for
        /// each after: the sketch moved it 1,160, which would stand the fourth column at 1,820, and the game's own
        /// name board stands right of a box (100 from it, 96 wide), so it would go past the screen's edge; moved
        /// 1,400 the four columns stand at 560, 900, 1,240 and 1,580, none further right than the game's own last
        /// (1,628), with Black Mage, Time Mage and Summoner still seen at 228.</summary>
        public const int Rows = 5, ViewColumns = 4, FirstColumn = 1960, ColumnStep = 340, FirstRow = 120, RowStep = 175,
                         FirstSlide = 1400, NextSlide = ColumnStep * ViewColumns;
        /// <summary>The game's places, and the place of the first of the mods' jobs' boxes.</summary>
        public const int GamePlaces = 20, FirstPlace = 20;
        /// <summary>The cursor's eight directions as the game numbers them, from right round by down.</summary>
        public const int Right = 0, DownRight = 1, Down = 2, DownLeft = 3, Left = 4, UpLeft = 5, Up = 6, UpRight = 7, Directions = 8;
        /// <summary>What a direction leads to besides a job: nothing, and the game's board.</summary>
        public const int None = -1, Board = -2;

        /// <summary>Where each of the mods' jobs' boxes stands: its column and row, in the order the jobs were given.</summary>
        public sealed class Plan
        {
            public int Count { get; }
            public int[] Column { get; }
            public int[] Row { get; }
            public int Columns { get; }
            readonly int[,] _at;

            Plan(int[] column, int[] row)
            {
                Count = column.Length;
                Column = column;
                Row = row;
                foreach (int c in column)
                    Columns = Math.Max(Columns, c + 1);
                _at = new int[Math.Max(Columns, 1), Rows];
                for (int c = 0; c < _at.GetLength(0); c++)
                    for (int r = 0; r < Rows; r++)
                        _at[c, r] = None;
                for (int k = 0; k < Count; k++)
                    _at[column[k], row[k]] = k;
            }

            /// <summary>The plan of the jobs: `own[k]` the jobs of its mod job k needs (their places among the jobs).
            /// As the sketch he signed off has them: a job that needs a job of its mod stands in the column right after
            /// it, in its row (the nearest free row where that is taken, the next column where the column is full), so
            /// the line between them runs straight along the row. (1.51.0, his word on test 114: "new Jobs that do not
            /// have any requirements be order on the left most columns. That way if the user adds more jobs with more
            /// requirements for their existing new jobs they can continue towards the right hand side") First the jobs
            /// that neither need a job of their mod nor are needed by one, five to a column from the first column's
            /// top; then, from the next column on, the jobs others need that need none themselves, from that column's
            /// top; then each job that needs one, after the job it needs. However many columns that makes, the view
            /// slides over four at a time. (1.52.0, his word on test 115: "Jobs that have no New Job requirements but
            /// have Vanilla job requirements should appear after the Jobs that have no requirements at all", and "There
            /// is room for three jobs under the Timekeeper in this example") Of the jobs no line joins, those that need
            /// nothing at all come first, then those that need only the game's jobs (`game[k]`: job k needs one of the
            /// game's); the jobs others need follow in the same run of places, under them, not from a column of their
            /// own.</summary>
            public static Plan Make(IList<int[]> own, IList<bool>? game = null)
            {
                int count = own.Count;
                var depth = new int[count];
                var needed = new bool[count];
                var needs = new bool[count];
                for (int k = 0; k < count; k++)
                {
                    depth[k] = Depth(own, k, 0);
                    foreach (int need in own[k])
                        if (need >= 0 && need < count && need != k)
                        {
                            needed[need] = true;
                            needs[k] = true;
                        }
                }
                var column = new int[count];
                var row = new int[count];
                var taken = new HashSet<(int, int)>();
                var placed = new bool[count];
                // One run of places, five a column from the first column's top: the jobs no line joins that need
                // nothing, then those that need only the game's jobs, then the jobs others need that need none.
                var run = new List<int>();
                for (int pass = 0; pass < 2; pass++)
                    for (int k = 0; k < count; k++)
                        if (!needs[k] && !needed[k] && (game != null && k < game.Count && game[k]) == (pass == 1))
                            run.Add(k);
                for (int k = 0; k < count; k++)
                    if (depth[k] == 0 && needed[k] && !needs[k])
                        run.Add(k);
                foreach (int k in run)
                {
                    column[k] = taken.Count / Rows;
                    row[k] = taken.Count % Rows;
                    taken.Add((column[k], row[k]));
                    placed[k] = true;
                }
                int first = (run.Count + Rows - 1) / Rows;
                // Then each job that needs one of its mod, the nearer the first, right of the job it needs.
                var order = new List<int>();
                for (int k = 0; k < count; k++)
                    if (!placed[k])
                        order.Add(k);
                order.Sort((a, b) => depth[a] != depth[b] ? depth[a].CompareTo(depth[b]) : a.CompareTo(b));
                foreach (int k in order)
                {
                    int c = first, r = 0;
                    bool has = false;
                    foreach (int need in own[k])
                        if (need >= 0 && need < count && need != k && placed[need] && (!has || column[need] + 1 > c))
                        {
                            c = column[need] + 1;
                            r = row[need];
                            has = true;
                        }
                    for (bool found = false; !found; c++)
                        for (int far = 0; far < Rows && !found; far++)
                            foreach (int to in has ? new[] { r + far, r - far } : new[] { far })
                                if (!found && to >= 0 && to < Rows && taken.Add((c, to)))
                                {
                                    column[k] = c;
                                    row[k] = to;
                                    found = true;
                                }
                    placed[k] = true;
                }
                return new Plan(column, row);
            }

            /// <summary>How many jobs of its mod stand before a job, the longest way (a ring, which a job's file can't
            /// give, ends at the jobs' count).</summary>
            static int Depth(IList<int[]> own, int k, int seen)
            {
                if (seen > own.Count)
                    return 0;
                int most = 0;
                foreach (int need in own[k])
                    if (need >= 0 && need < own.Count && need != k)
                        most = Math.Max(most, 1 + Depth(own, need, seen + 1));
                return most;
            }

            /// <summary>The job at a column and row (None: none, or no such place).</summary>
            public int At(int column, int row)
                => column < 0 || column >= Columns || row < 0 || row >= Rows ? None : _at[column, row];

            /// <summary>Where a job's box stands in the layer.</summary>
            public int X(int k) => FirstColumn + ColumnStep * Column[k];
            public int Y(int k) => FirstRow + RowStep * Row[k];

            /// <summary>The view a job is in: 1 the first four columns, 2 the next.</summary>
            public int View(int k) => 1 + Column[k] / ViewColumns;

            /// <summary>The job of a column nearest a row (the row itself, else the nearest above or below, above
            /// first), None where the column has none.</summary>
            public int Nearest(int column, int row)
            {
                for (int far = 0; far < Rows; far++)
                {
                    int above = At(column, row - far), below = At(column, row + far);
                    if (above != None)
                        return above;
                    if (below != None)
                        return below;
                }
                return None;
            }

            /// <summary>Where the cursor goes from a job's box: up and down inside its column, right and left to the
            /// column beside it (the same row, else the nearest), a slanted direction to exactly that box; left from
            /// the first column the game's board (Board); None where nothing is.</summary>
            public int Neighbour(int k, int direction)
            {
                int c = Column[k], r = Row[k];
                switch (direction)
                {
                    case Up:
                        for (int to = r - 1; to >= 0; to--)
                            if (At(c, to) != None)
                                return At(c, to);
                        return None;
                    case Down:
                        for (int to = r + 1; to < Rows; to++)
                            if (At(c, to) != None)
                                return At(c, to);
                        return None;
                    case Right:
                        return Nearest(c + 1, r);
                    case Left:
                        return c == 0 ? Board : Nearest(c - 1, r);
                    case UpRight:
                        return At(c + 1, r - 1);
                    case DownRight:
                        return At(c + 1, r + 1);
                    case DownLeft:
                        return At(c - 1, r + 1);
                    case UpLeft:
                        return At(c - 1, r - 1);
                    default:
                        return None;
                }
            }

            /// <summary>The row whose boxes stand nearest a height in the layer.</summary>
            public static int RowNear(int y)
            {
                int best = 0;
                for (int r = 1; r < Rows; r++)
                    if (Math.Abs(FirstRow + RowStep * r - y) < Math.Abs(FirstRow + RowStep * best - y))
                        best = r;
                return best;
            }
        }

        /// <summary>How far the layer is moved left for a view: 0 the game's board.</summary>
        public static int SlideOf(int view) => view <= 0 ? 0 : FirstSlide + NextSlide * (view - 1);

        /// <summary>The view's next place on its way to where it is going: a part of what is left each frame, the
        /// rest once it is small.</summary>
        public static float Slid(float now, float to)
        {
            float left = to - now;
            return Math.Abs(left) <= SlideEnd ? to : now + left * SlidePart;
        }

        public const float SlidePart = 0.3f, SlideEnd = 1.5f;

        // --- the figures' slots ------------------------------------------------------------------------------------

        /// <summary>The figures' numbered slots (0 to 255) the framework takes its own from, in this order: numbers no
        /// place of the program's code that numbers a figure was seen to write (0x3B to 0x4F, the tree's 0x50 to 0x63,
        /// 0x6B, 0x6C, 0x7D on, 0x88, 0xAE, 0xB4 to 0xB7 on and 0xC8 on were). Not every such place was read: each
        /// slot is taken only while the keeper has it free.</summary>
        public static readonly (int First, int Last)[] SlotRanges = { (0x89, 0xAD), (0xB8, 0xC7), (0x6D, 0x7C), (0x64, 0x6A) };

        /// <summary>The slots in the order they are tried.</summary>
        public static IEnumerable<int> Slots()
        {
            foreach (var (first, last) in SlotRanges)
                for (int slot = first; slot <= last; slot++)
                    yield return slot;
        }

        // --- the game's memory, as measured ------------------------------------------------------------------------

        /// <summary>The tree: its bytes, the number it tells its boxes' pieces, its receiver (whose function at
        /// ReceiverTell hears what was chosen), its layouts, what the name board's writer is handed, its places, their
        /// directions, its JobTree piece, the place the cursor is on, the unit's own job's, which of the Bard's and the
        /// Dancer's boxes is hidden and whether a click chose the box under the mouse.</summary>
        public const int TreeBytes = 0x2FD8, TreeActor = 8, TreeReceiver = 0x10, ReceiverTell = 0x30, TreeLayouts = 0x18,
                         TreeWriter = 0x40, TreePlaces = 0x48, PlaceBytes = 0x1C8, TreeDirections = 0x1F0, TreePiece = 0x2F78,
                         TreeCursor = 0x2FC8, TreeOwn = 0x2FCC, TreeHidden = 0x2FD0, TreeClicked = 0x2FD1;
        /// <summary>A place's direction: two boxes, each its place and whether the move goes round the board.</summary>
        public const int DirectionBytes = 4, CandidateBytes = 2, NoPlace = 20, HiddenFirst = 0x11, HiddenSecond = 0x12;
        /// <summary>A job's record: its bytes, the unit's level in it, the job, its figure's record (its slot first),
        /// whether it is open (0), locked (1) or not to be seen (2), and whether the unit is in it.</summary>
        public const int RecordBytes = 0x94, RecordLevel = 0x44, RecordJob = 0x48, RecordFigure = 0x5C, RecordClosed = 0x84,
                         RecordWorn = 0x8D, Unseen = 2;
        /// <summary>A box's piece: the tag of a job's box and its place, the four numbers it tells, a byte the tree's
        /// setup clears. A box of the layouts: its kind, where it stands, its layer.</summary>
        public const int PieceTag = 0x220, PiecePlace = 0x224, PieceTells = 0x248, Tells = 4, PieceByte = 0x22D, JobTag = 0x12,
                         BoxX = 0x38, BoxY = 0x3C, TextKind = 3;
        /// <summary>What the update is asked and tells: confirm and cancel, "this job was chosen", the job screen's
        /// mode and the tree's.</summary>
        public const int Confirm = 0x1A, Cancel = 0x1B, Chosen = 0x80, ScreenMode = 0x578, TreeMode = 0x581;
        /// <summary>The figures: the keeper's slots (0x70 bytes each from + 0x3A48: the picture box at + 0, the slot's
        /// number at + 0x38) and the sprites' (0x5C bytes each, at the pointer at the sprites' keeper's + 0x242B0:
        /// whether it is in use at + 0x10).</summary>
        public const int KeeperSlots = 0x3A48, KeeperSlotBytes = 0x70, KeeperSlotBox = 0, KeeperSlotNumber = 0x38,
                         SpriteSlots = 0x242B0, SpriteSlotBytes = 0x5C, SpriteInUse = 0x10, LastSlot = 0xFF;
        /// <summary>A text setter's bytes, and what the name board's writer is handed: six places (an icon's box, the
        /// title, the level's setter, three the tree leaves empty).</summary>
        public const int SetterBytes = 0x68, WriterPlaces = 6, WriterTitle = 1, WriterLevel = 2;
        /// <summary>(1.49.1, his test 112) A text's key (the words it is written from, the level's number among them):
        /// a text box's at + 0xF8, a setter's at + 0x60. A setter bound to a box takes the box's key and clears it
        /// (0x28F5E4), and writes through its own (0x28F754: with no key and no words of its own it writes nothing).
        /// A place's level's setter is at the place's + 0x20.</summary>
        public const int TextKey = 0xF8, SetterKey = 0x60, PlaceSetter = 0x20;

        /// <summary>The names looked for and played. The game's boxes in the order of their places.</summary>
        public static readonly string[] GameBoxes =
        {
            "Squire", "Chemist", "Knight", "Archer", "Monk", "White", "Black", "Time", "Summoner", "Thief", "Orator", "Mystic",
            "Geomancer", "Dragoon", "Samurai", "Ninja", "Arithmetician", "Bard", "Dancer", "Mime",
        };
        public const string BoxPrefix = "MsqJob";
        static readonly string[] Fixed =
        {
            "Unit", "TextBoardJobName", "Title", "TextLvNum", "Show", "Hide", "Unlock", "LockReleased", "LockUnreleased", "LvNum",
            "LvNone", "ShowUse", "HideUse", "CursorOut",
        };
        const int UnitName = 0, BoardName = 1, TitleName = 2, LevelName = 3, ShowName = 4, HideName = 5, UnlockName = 6,
                  LvNumName = 9, LvNoneName = 10, ShowUseName = 11, HideUseName = 12, CursorOutName = 13;

        // --- the game's own, each called as the game calls it ------------------------------------------------------

        /// <summary>The layouts: a piece's piece by its name, a box by its name in a piece's boxes, a copy of a box, a
        /// box moved, a box put in a layer after another, a box named, a piece's animation played from its start and
        /// stopped, every animation of a piece stopped, a piece focused.</summary>
        public Func<nint, nint, nint> Child = (_, _) => 0, Named = (_, _) => 0, Copy = (_, _) => 0;
        public Action<nint, int, int> Move = (_, _, _) => { };
        public Action<nint, nint, nint> Add = (_, _, _) => { };
        public Action<nint, nint> Rename = (_, _) => { }, Play = (_, _) => { }, Stop = (_, _) => { };
        public Action<nint> StopAll = _ => { }, Focus = _ => { };
        /// <summary>The figures: a figure's record finished as the tree finishes it, the figure given to the keeper
        /// with its picture box, a slot given back, and where a slot's two records are (0: the keeper isn't there).</summary>
        public Action<nint> Finish = _ => { };
        public Action<nint, nint> Figure = (_, _) => { };
        public Action<int> Free = _ => { };
        public Func<int, nint> KeeperSlot = _ => 0, SpriteSlot = _ => 0;
        /// <summary>The name board's writer (what the tree hands it, the six places, the record, whether the job isn't
        /// to be seen); a new text setter; a setter bound to a text box.</summary>
        public Action<nint, nint, nint, bool> Write = (_, _, _, _) => { };
        public Func<nint> Setter = () => 0;
        public Action<nint, nint> Bind = (_, _) => { };
        /// <summary>The update: whether an action is pressed, the game's own update (the tree, the menu's mode), and
        /// the receiver told (the receiver, the tree, what, which).</summary>
        public Func<int, bool> Pressed = _ => false;
        public Action<nint, nint> GameUpdate = (_, _) => { };
        public Action<nint, nint, int, int> Tell = (_, _, _, _) => { };
        /// <summary>The job screen's rows made to show a job of the mods' (its place among them): its place on the
        /// screen, below 0 where it can't be shown.</summary>
        public Func<int, int> ShowJob = _ => -1;
        /// <summary>What is said, each line once.</summary>
        public Action<string> Say = _ => { };

        // --- what the framework keeps ------------------------------------------------------------------------------

        readonly Plan _plan;
        readonly string[] _whose;
        /// <summary>The names' strings (16 bytes each: where its characters are, then 0), then their characters:
        /// Fixed's, the game's boxes', then each of the mods' jobs' box's.</summary>
        readonly nint _names;
        readonly int _nameCount;
        /// <summary>Each job's box, its piece, its figure's picture box, its name board and the board's title; its text
        /// setter (made once, bound anew to each tree's box); its figure's slot (below 0: none); its record as last
        /// given (0x94 bytes each) and whether one was.</summary>
        readonly nint[] _box, _piece, _figure, _board, _title, _setter;
        readonly int[] _slot;
        readonly nint _records, _scratch, _writer;
        readonly bool[] _given;
        readonly HashSet<string> _said = new HashSet<string>();
        /// <summary>The tree the boxes were made in and its JobTree piece, the layer and where the game rests it; the
        /// game's rightmost boxes (their places) and each one's box of the first column; the box of the job the unit
        /// is in (below 0: none of the mods'); how far the layer is moved now.</summary>
        nint _tree, _treePiece, _layer;
        int _layerX, _layerY, _worn = -1;
        readonly int[] _enter = new int[GamePlaces];
        readonly int[] _back = new int[Rows];
        float _slide;

        public Plan Placed => _plan;
        public int Worn => _worn;
        public float Slide => _slide;
        public bool Built => _tree != 0;

        /// <summary>`own[k]`: the jobs of its mod job k needs (their places among the jobs given). `whose[k]`: the
        /// job's name, for what is said. (1.52.0) `game[k]`: whether job k needs any of the game's jobs.</summary>
        public JobTree(IList<int[]> own, IList<string> whose, IList<bool>? game = null)
        {
            _plan = Plan.Make(own, game);
            int count = _plan.Count;
            _whose = new string[count];
            for (int k = 0; k < count; k++)
                _whose[k] = whose[k];
            _box = new nint[count];
            _piece = new nint[count];
            _figure = new nint[count];
            _board = new nint[count];
            _title = new nint[count];
            _setter = new nint[count];
            _slot = new int[count];
            _given = new bool[count];
            Array.Fill(_slot, -1);
            Array.Fill(_enter, None);
            Array.Fill(_back, None);
            var all = new List<string>(Fixed);
            all.AddRange(GameBoxes);
            for (int k = 0; k < count; k++)
                all.Add(BoxPrefix + k);
            _nameCount = all.Count;
            int characters = 0;
            foreach (string name in all)
                characters += name.Length + 1;
            _names = (nint)System.Runtime.InteropServices.NativeMemory.AllocZeroed((nuint)(all.Count * 16 + characters));
            byte* text = (byte*)_names + all.Count * 16;
            for (int n = 0; n < all.Count; n++)
            {
                *(nint*)(_names + n * 16) = (nint)text;
                foreach (char c in all[n])
                    *text++ = (byte)c;
                *text++ = 0;
            }
            _records = (nint)System.Runtime.InteropServices.NativeMemory.AllocZeroed((nuint)(Math.Max(count, 1) * RecordBytes));
            _scratch = (nint)System.Runtime.InteropServices.NativeMemory.AllocZeroed(TreeBytes);
            _writer = (nint)System.Runtime.InteropServices.NativeMemory.AllocZeroed((nuint)(WriterPlaces * sizeof(nint)));
        }

        nint Name(int n) => _names + n * 16;
        nint GameName(int place) => Name(Fixed.Length + place);
        nint BoxName(int k) => Name(Fixed.Length + GameBoxes.Length + k);
        nint Characters(nint name) => *(nint*)name;

        void Once(string line)
        {
            if (_said.Add(line))
                Say(line);
        }

        /// <summary>What the log says where the boxes are made, and where they can't be.</summary>
        public static string Line(int jobs) =>
            $"Job Progress shows the mods' job{(jobs == 1 ? "" : "s")} in columns to the right of the game's tree: move right "
            + "past Black Mage, Time Mage or Summoner and the view slides over to them.";
        public static string NotLine(string why) =>
            $"Job Progress doesn't show the mods' jobs: {why}. The job screen's own rows show them as before.";
        /// <summary>...where the tree's places aren't found in the program.</summary>
        public static string NotFoundLine(IEnumerable<string> missing, string program, string name) =>
            NotLine($"{string.Join(", ", missing)} wasn't found in {program}. A game update may have changed it: look for a newer "
                    + name);

        // --- the boxes ---------------------------------------------------------------------------------------------

        /// <summary>Whether the boxes made are still this tree's: the same tree and JobTree piece, the first box still
        /// found there by its name.</summary>
        bool Stands(nint tree)
        {
            if (tree == 0 || _tree != tree || _plan.Count == 0)
                return false;
            nint piece = *(nint*)(tree + TreePiece);
            return piece != 0 && piece == _treePiece && _box[0] != 0 && Named(piece + Marker.PieceTree, BoxName(0)) == _box[0];
        }

        /// <summary>The boxes made in a tree that has none of them (a tree set up again has its layout anew): true
        /// where they stand. A tree not set up yet has no JobTree piece: nothing is made, nothing said.</summary>
        public bool Build(nint tree)
        {
            if (_plan.Count == 0 || tree == 0)
                return false;
            if (Stands(tree))
                return true;
            nint piece = *(nint*)(tree + TreePiece), layouts = *(nint*)(tree + TreeLayouts);
            if (piece == 0 || layouts == 0)
                return false;
            // Whatever was made before went with its layout: its slots are given back, nothing of it is touched.
            Forget();
            nint boxes = piece + Marker.PieceTree;
            nint model = Named(boxes, GameName(0));
            if (model == 0 || *(int*)(model + Marker.BoxKind) != MapPieces.ReferenceKind || *(nint*)(model + MapPieces.BoxParent) == 0)
            {
                Once(NotLine("the tree has no box of the game's first job to copy"));
                return false;
            }
            nint layer = *(nint*)(model + MapPieces.BoxParent);
            for (int k = 0; k < _plan.Count; k++)
            {
                nint box = Named(boxes, BoxName(k));
                if (box == 0)
                {
                    box = Copy(layouts, model);
                    if (box == 0)
                    {
                        Once(NotLine("a copy of a job's box wasn't made"));
                        return false;
                    }
                    Rename(box, Characters(BoxName(k)));
                    Move(box, _plan.X(k), _plan.Y(k));
                    Add(layer, box, model);
                }
                nint made = Child(piece, BoxName(k));
                nint unit = made == 0 ? 0 : Child(made, Name(UnitName));
                nint figure = unit == 0 ? 0 : Named(unit + Marker.PieceTree, Name(UnitName));
                nint board = made == 0 ? 0 : Child(made, Name(BoardName));
                nint title = board == 0 ? 0 : Named(board + Marker.PieceTree, Name(TitleName));
                nint level = board == 0 ? 0 : Named(board + Marker.PieceTree, Name(LevelName));
                if (made == 0 || figure == 0 || *(int*)(figure + Marker.BoxKind) != Marker.PictureKind || title == 0
                    || *(int*)(title + Marker.BoxKind) != TextKind || level == 0 || *(int*)(level + Marker.BoxKind) != TextKind)
                {
                    // The copy made stays in the layout, right of everything seen: not shown.
                    if (made != 0)
                    {
                        StopAll(made);
                        Play(made, Name(HideName));
                    }
                    Once(NotLine("a copy of a job's box doesn't hold what the game's holds"));
                    return false;
                }
                // The tag and the place, the tree told, the byte cleared: as the tree's setup does for its own.
                *(int*)(made + PieceTag) = JobTag;
                *(int*)(made + PiecePlace) = FirstPlace + k;
                int actor = *(int*)(tree + TreeActor);
                for (int n = 0; n < Tells; n++)
                {
                    int* tells = (int*)(made + PieceTells + 4 * n);
                    if (*tells == actor)
                        break;
                    if (*tells == 0)
                    {
                        *tells = actor;
                        break;
                    }
                }
                *(byte*)(made + PieceByte) = 0;
                if (_setter[k] == 0)
                    _setter[k] = Setter();
                if (_setter[k] == 0)
                {
                    StopAll(made);
                    Play(made, Name(HideName));
                    Once(NotLine("a level's text couldn't be made ready"));
                    return false;
                }
                // (1.49.1, his test 112: "the Lv. number was missing") The box copied gave its level's text's key to
                // the tree's own setter as the tree was set up, so the copy's level has none and the framework's
                // setter would write nothing: the copy's is given the key the tree's first place's setter holds, and
                // the framework's setter takes it as it is bound.
                int key = *(int*)(tree + TreePlaces + PlaceSetter + SetterKey);
                if (key != 0 && *(int*)(level + TextKey) == 0)
                    *(int*)(level + TextKey) = key;
                Bind(_setter[k], level);
                _box[k] = box;
                _piece[k] = made;
                _figure[k] = figure;
                _board[k] = board;
                _title[k] = title;
                _given[k] = false;
                // Not seen until its job is given: a copy shows the copied box's job. (1.49.1, his test 112: every
                // copy had the ring and the name board of a box under the cursor until the cursor had been on it and
                // left) A copy is as the box copied was, ring and name board showing: it is played the piece's own
                // CursorOut, as the layouts play it for a box the cursor leaves.
                StopAll(made);
                Play(made, Name(CursorOutName));
                Play(made, Name(HideName));
            }
            _tree = tree;
            _treePiece = piece;
            _layer = layer;
            _layerX = *(int*)(layer + BoxX);
            _layerY = *(int*)(layer + BoxY);
            _slide = 0;
            Ways(tree, boxes);
            Once(Line(_plan.Count));
            // (1.50.0) The lines between the jobs and the small icons of the game's jobs they need (JobTreeLines.cs):
            // where they can't be made the boxes stand without them, and what was made of them is put away.
            if (AnyDrawn())
            {
                string? why = LinesWithout ?? BuildLines(tree, piece, layouts, boxes, layer, model);
                _lines = why == null;
                _stale = true;
                if (why != null)
                    PutAway();
                Once(why == null ? LinesLine : LinesNotLine(why));
            }
            return true;
        }

        /// <summary>The game's rightmost boxes (those standing furthest right) each lead right to the box of the first
        /// column nearest its height, and each row of the first column leads left to the rightmost box nearest it.</summary>
        void Ways(nint tree, nint boxes)
        {
            Array.Fill(_enter, None);
            Array.Fill(_back, None);
            var x = new int[GamePlaces];
            var y = new int[GamePlaces];
            int most = int.MinValue;
            for (int place = 0; place < GamePlaces; place++)
            {
                nint box = Named(boxes, GameName(place));
                x[place] = box == 0 ? int.MinValue : *(int*)(box + BoxX);
                y[place] = box == 0 ? 0 : *(int*)(box + BoxY);
                most = Math.Max(most, x[place]);
            }
            for (int place = 0; place < GamePlaces; place++)
                if (x[place] == most && most != int.MinValue)
                    _enter[place] = _plan.Nearest(0, Plan.RowNear(y[place]));
            for (int row = 0; row < Rows; row++)
            {
                int best = None;
                for (int place = 0; place < GamePlaces; place++)
                    if (_enter[place] != None
                        && (best == None || Math.Abs(y[place] - (FirstRow + RowStep * row)) < Math.Abs(y[best] - (FirstRow + RowStep * row))))
                        best = place;
                _back[row] = best;
            }
        }

        /// <summary>The game's box a row of the first column leads back to, and the first column's box a game's box
        /// leads to (None: none).</summary>
        public int Back(int row) => row < 0 || row >= Rows ? None : _back[row];
        public int Enter(int place) => place < 0 || place >= GamePlaces ? None : _enter[place];

        /// <summary>Every slot given back and the boxes forgotten: they went with their layout, or are to be made
        /// anew. Nothing of a box is touched.</summary>
        public void Forget()
        {
            for (int k = 0; k < _plan.Count; k++)
            {
                if (_slot[k] >= 0 && Mine(k))
                    Free(_slot[k]);
                _slot[k] = -1;
                _box[k] = _piece[k] = _figure[k] = _board[k] = _title[k] = 0;
                _given[k] = false;
            }
            _tree = _treePiece = _layer = 0;
            _worn = -1;
            _slide = 0;
            ForgetLines();
        }

        /// <summary>The game's own giving back of the tree's figures (0x133EB8), where it is ever asked: the
        /// framework's are given back with them, the boxes kept.</summary>
        public void Released()
        {
            for (int k = 0; k < _plan.Count; k++)
            {
                if (_slot[k] >= 0 && Mine(k))
                    Free(_slot[k]);
                _slot[k] = -1;
            }
        }

        /// <summary>Whether a job's slot is still its box's: the keeper's record of that slot names the box's picture.</summary>
        bool Mine(int k)
        {
            if (_slot[k] < 0 || _figure[k] == 0)
                return false;
            nint keeper = KeeperSlot(_slot[k]);
            return keeper != 0 && *(nint*)(keeper + KeeperSlotBox) == _figure[k] && *(int*)(keeper + KeeperSlotNumber) == _slot[k];
        }

        /// <summary>A slot for a job's figure: the one it has while that is still its box's, else the first of the
        /// framework's numbers that no other of its boxes has and the keeper has free (no sprite in use there, no
        /// picture box). Below 0: none.</summary>
        int Slot(int k)
        {
            if (Mine(k))
                return _slot[k];
            _slot[k] = -1;
            foreach (int slot in Slots())
            {
                bool taken = false;
                for (int other = 0; other < _plan.Count && !taken; other++)
                    taken = other != k && _slot[other] == slot;
                if (taken)
                    continue;
                nint keeper = KeeperSlot(slot), sprite = SpriteSlot(slot);
                if (keeper == 0 || sprite == 0)
                    return -1;
                if (*(byte*)(sprite + SpriteInUse) != 0 || *(nint*)(keeper + KeeperSlotBox) != 0)
                    continue;
                return _slot[k] = slot;
            }
            return -1;
        }

        // --- a job given to its box --------------------------------------------------------------------------------

        /// <summary>In the game's filling run for the mods' jobs alone, a job's record as the game made it (`job` its
        /// place among the mods' jobs): the boxes made where they aren't, and the job given to its box as the tree's
        /// own giving gives one.</summary>
        public void Harvested(int job, nint record, nint tree)
        {
            if (job < 0 || job >= _plan.Count || record == 0 || !Build(tree))
                return;
            Give(job, record, tree);
        }

        /// <summary>Before the mods' jobs' records come for a unit: none is the unit's own until one says so.</summary>
        public void Begin()
        {
            _worn = -1;
            _stale = true;
        }

        /// <summary>A unit whose list is the game's own (a guest, a monster): no job of the mods' is shown for it.</summary>
        public void Empty(nint tree)
        {
            _worn = -1;
            _stale = true;
            if (!Stands(tree))
                return;
            for (int k = 0; k < _plan.Count; k++)
                if (_given[k])
                {
                    Stop(_piece[k], Name(ShowName));
                    Play(_piece[k], Name(HideName));
                    _given[k] = false;
                }
        }

        void Give(int k, nint record, nint tree)
        {
            byte* kept = (byte*)_records + k * RecordBytes;
            Buffer.MemoryCopy((void*)record, kept, RecordBytes, RecordBytes);
            int closed = *(int*)(kept + RecordClosed);
            bool worn = kept[RecordWorn] != 0;
            // The figure: a slot of the framework's own where the tree numbers its place's, then as the tree does.
            int slot = Slot(k);
            if (slot >= 0)
            {
                *(int*)(kept + RecordFigure) = slot;
                Finish((nint)(kept + RecordFigure));
                Figure((nint)(kept + RecordFigure), _figure[k]);
            }
            else
                Once($"{_whose[k]} has no figure on Job Progress: none of the figures' places the framework takes its own from "
                     + "was free.");
            // The name and the level on the board.
            nint* writer = (nint*)_writer;
            for (int n = 0; n < WriterPlaces; n++)
                writer[n] = 0;
            writer[WriterTitle] = _title[k];
            writer[WriterLevel] = _setter[k];
            Write(tree + TreeWriter, _writer, (nint)kept, closed == Unseen);
            Either(_board[k], closed == 0, LvNumName, LvNoneName);
            for (int state = 0; state < 3; state++)
                if (state == closed)
                    Play(_piece[k], Name(UnlockName + state));
                else
                    Stop(_piece[k], Name(UnlockName + state));
            Either(_piece[k], worn, ShowUseName, HideUseName);
            Stop(_piece[k], Name(HideName));
            Play(_piece[k], Name(ShowName));
            _given[k] = true;
            _stale = true;
            if (worn)
                _worn = k;
        }

        /// <summary>One of two animations played, the other stopped first.</summary>
        void Either(nint piece, bool first, int one, int other)
        {
            Stop(piece, Name(first ? other : one));
            Play(piece, Name(first ? one : other));
        }

        /// <summary>A job's record as last given (null: none yet).</summary>
        public byte* Record(int k) => k < 0 || k >= _plan.Count || !_given[k] ? null : (byte*)_records + k * RecordBytes;

        // --- the cursor and the view -------------------------------------------------------------------------------

        /// <summary>In place of the game's update of the tree (`mode`: where the menu's mode is). A tree without the
        /// framework's boxes is the game's own.</summary>
        public void Update(nint tree, nint mode)
        {
            Handled = false;
            if (!Stands(tree))
            {
                Game(tree, mode);
                return;
            }
            int cursor = *(int*)(tree + TreeCursor), job = cursor - FirstPlace;
            // A box that isn't shown (this unit was given no record of its job) is no place of the framework's: the
            // game's own update takes a place past its 19 as the unit's own job's, and moves from there.
            bool mine = job >= 0 && job < _plan.Count && _given[job];
            // Confirm, as the game's update asks it first: the key, or a click noted by the tree's handler.
            bool chosen = Pressed(Confirm) || *(byte*)(tree + TreeClicked) != 0;
            bool leads = !mine && cursor >= 0 && cursor < GamePlaces && _enter[cursor] != None && _given[_enter[cursor]];
            if (mine && chosen)
            {
                // One of the mods' jobs chosen: its row shown on the job screen, the receiver told its place there.
                Handled = true;
                int place = ShowJob(job);
                if (place >= 0)
                {
                    nint receiver = *(nint*)(tree + TreeReceiver);
                    if (receiver != 0)
                        Tell(receiver, tree, Chosen, place);
                }
                *(int*)mode = ScreenMode;
            }
            else if (!chosen && (mine || leads))
                // (A game's job chosen is the game's own update over the tree itself: the receiver is told by the tree.)
                Stepped(tree, mode, cursor, mine ? job : None);
            else
                Game(tree, mode);
            Moved(tree);
            DrawLines(tree);
        }

        /// <summary>The game's own update over a copy of the tree in which the cursor's place's directions name the
        /// framework's boxes. On one of the mods' jobs the copy's cursor is on its first place, whose eight directions
        /// name places 1 to 8, each given the piece of the box that way; on one of the game's rightmost boxes its own
        /// place's way right names a place none of its directions names, given the piece of its box of the first
        /// column, and is no longer a move round the board.</summary>
        void Stepped(nint tree, nint mode, int cursor, int job)
        {
            Buffer.MemoryCopy((void*)tree, (void*)_scratch, TreeBytes, TreeBytes);
            byte* copy = (byte*)_scratch;
            if (job != None)
            {
                *(int*)(copy + TreeCursor) = 0;
                copy[TreeClicked] = 0;
                for (int direction = 0; direction < Directions; direction++)
                {
                    byte* way = copy + TreeDirections + direction * DirectionBytes;
                    int to = _plan.Neighbour(job, direction);
                    nint piece = to == Board ? GamePiece(tree, Back(_plan.Row[job])) : to >= 0 && _given[to] ? _piece[to] : 0;
                    way[0] = (byte)(piece != 0 ? 1 + direction : NoPlace);
                    way[1] = 0;
                    way[CandidateBytes] = NoPlace;
                    way[CandidateBytes + 1] = 0;
                    if (piece != 0)
                        *(nint*)(copy + TreePlaces + (1 + direction) * PlaceBytes) = piece;
                }
            }
            else
            {
                byte* ways = copy + TreeDirections + cursor * PlaceBytes;
                int free = -1;
                for (int place = 0; place < HiddenFirst && free < 0; place++)
                {
                    bool named = place == cursor;
                    for (int n = 0; n < Directions * 2 && !named; n++)
                        named = ways[n * CandidateBytes] == place;
                    if (!named)
                        free = place;
                }
                nint piece = _enter[cursor] >= 0 ? _piece[_enter[cursor]] : 0;
                if (free >= 0 && piece != 0)
                {
                    ways[Right * DirectionBytes] = (byte)free;
                    ways[Right * DirectionBytes + 1] = 0;
                    *(nint*)(copy + TreePlaces + free * PlaceBytes) = piece;
                }
            }
            Game(_scratch, mode);
        }

        /// <summary>Whether the last update's keys were answered: the game's own update ran, or one of the mods' jobs was
        /// chosen. (Where a fault came before, the caller runs the game's own once.)</summary>
        public bool Handled { get; private set; }

        void Game(nint tree, nint mode)
        {
            Handled = true;
            GameUpdate(tree, mode);
        }

        /// <summary>A game's place's piece (0: none).</summary>
        static nint GamePiece(nint tree, int place)
            => place < 0 || place >= GamePlaces ? 0 : *(nint*)(tree + TreePlaces + place * PlaceBytes);

        /// <summary>The view the cursor is in: 0 the game's board.</summary>
        int ViewOf(nint tree)
        {
            int job = *(int*)(tree + TreeCursor) - FirstPlace;
            return job >= 0 && job < _plan.Count && _given[job] ? _plan.View(job) : 0;
        }

        /// <summary>The layer moved a part of the way to the view the cursor is in.</summary>
        void Moved(nint tree)
        {
            float to = SlideOf(ViewOf(tree));
            if (_slide != to)
                _slide = Slid(_slide, to);
            // (1.49.1) Moved wherever it isn't where it should stand: the layout may have rested it meanwhile.
            int x = _layerX - (int)Math.Round(_slide);
            if (*(int*)(_layer + BoxX) != x)
                Move(_layer, x, _layerY);
        }

        /// <summary>After the game's showing of the tree as the menu's mode changes (`mode` the new one): as the tree
        /// comes up, the box of the job the unit is in is focused where that job is a mod's, and the layer is put
        /// where that box, or the game's board, is seen, at once.</summary>
        public void Shown(nint tree, int mode)
        {
            if (mode != TreeMode || !Stands(tree))
                return;
            bool own = _worn >= 0 && _given[_worn];
            // (1.49.1) The layer is put there whatever the framework last moved it by: it is the layout's to rest.
            _slide = SlideOf(own ? _plan.View(_worn) : 0);
            Move(_layer, _layerX - (int)Math.Round(_slide), _layerY);
            if (own)
                Focus(_piece[_worn]);
            DrawLines(tree);
        }

        // --- the places in the game's program, each found by its own bytes ------------------------------------------

        /// <summary>The tree's update (0x133FA4) from its start: the action 0x1A asked (its call), and the answer tested.</summary>
        public const string UpdateBytes = "48 89 5C 24 08 57 48 83 EC 30 45 33 C9 48 8B FA 48 8B D9 33 D2 33 C9 45 8D 41 1A E8 ?? "
                                          + "?? ?? ?? 84 C0 0F 85";
        public const int UpdatePressedAt = 0x1B;
        /// <summary>Its one call, by the unit screens' holder (the tree from + 0x80, the menu's mode handed on), after
        /// which the holder goes to its end.</summary>
        public const string UpdateCallBytes = "48 8B 8F 80 00 00 00 48 8B D6 E8 ?? ?? ?? ?? EB 7B";
        public const int UpdateCallAt = 10;
        /// <summary>In the update: the piece of the place a direction names focused (its call).</summary>
        public const string FocusBytes = "48 69 C8 C8 01 00 00 48 8B 4C 19 48 E8 ?? ?? ?? ?? EB 30";
        public const int FocusCallAt = 12;
        /// <summary>The tree's showing as the menu's mode changes (0x133F30), from its start.</summary>
        public const string ShownBytes = "48 89 5C 24 08 57 48 83 EC 30 8B FA 48 8B D9 41 81 F8 81 05 00 00 75 20 33 D2 E8";
        /// <summary>The tree's giving back of its figures (0x133EB8), from its start: 19 slots from 0x50, each the
        /// keeper's slot cleared (the keeper named, its call) and the sprite's given back (the sprites' keeper named,
        /// its call).</summary>
        public const string ReleaseBytes = "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 BB 50 00 00 00 BF 00 23 00 00 8D 73 C3 81 FB "
                                           + "FF 00 00 00 77 35 48 8B 0D ?? ?? ?? ?? 48 81 C1 48 3A 00 00";
        public const int ReleaseKeeperAt = 0x24, ReleaseClearAt = 0x35, ReleaseSpritesAt = 0x3A, ReleaseFreeAt = 0x54;
        /// <summary>In the tree's giving of a job to its place (0x13420C, found by the filling's call of it): the
        /// figure numbered 0x50 plus the place, finished (its call), the keeper named, the figure given with the place's
        /// picture box (its call); and, further on, the name board's writer (its call).</summary>
        public const string GiveBytes = "41 8D 46 50 33 D2 48 8D 8B 44 24 00 00 89 83 44 24 00 00 45 8D 41 04 E8 ?? ?? ?? ?? 48 8B 0D "
                                        + "?? ?? ?? ?? 48 8D 93 44 24 00 00 4D 8B 44 3F 50 E8";
        public const int GiveAt = 0xE5, GiveFinishAt = 0xFC, GiveKeeperAt = 0x101, GiveFigureAt = 0x114;
        public const string WriteBytes = "02 F3 0F 7F 45 C8 41 0F 94 C1 48 89 45 C0 E8";
        public const int WriteAt = 0x153, WriteCallAt = 0x161;
        /// <summary>In the tree's setup: a text setter made (its call), and a place's level's setter bound to its text
        /// box (its call).</summary>
        public const string SetterBytes0 = "48 8D 8D 00 01 00 00 E8 ?? ?? ?? ?? 45 8B F4 48 8D 5E 48";
        public const int SetterCallAt = 7;
        public const string BindBytes = "48 8B D0 49 8B CF E8 ?? ?? ?? ?? 8B 55 88";
        public const int BindCallAt = 6;
        /// <summary>(1.50.0) The play of a line's look (0x1347DC) and of a label's (0x1348B0), each from its start.</summary>
        public const string LinePlayBytes = "48 85 D2 0F 84 C9 00 00 00 4C 8B DC 49 89 5B 08 49 89 73 10 57 48 83 EC 60 48 8D 05 ?? ?? "
                                            + "?? ?? 41 0F B6 C9";
        public const string LabelPlayBytes = "48 85 D2 0F 84 C6 00 00 00 4C 8B DC 49 89 5B 08 49 89 73 10 57 48 83 EC 60 48 8D 05 ?? ?? "
                                             + "?? ?? 33 FF";

        /// <summary>What was found of the tree.</summary>
        public sealed class Sites
        {
            /// <summary>The update, the showing and the giving back; whether an action is pressed; a piece focused.</summary>
            public int Update { get; internal set; } = -1;
            public int Shown { get; internal set; } = -1;
            public int Release { get; internal set; } = -1;
            public int Pressed { get; internal set; } = -1;
            public int Focus { get; internal set; } = -1;
            /// <summary>The figures' keeper and the sprites' keeper (a pointer each); a keeper's slot cleared and a
            /// sprite's slot given back; a figure's record finished and the figure given.</summary>
            public int Keeper { get; internal set; } = -1;
            public int Sprites { get; internal set; } = -1;
            public int Clear { get; internal set; } = -1;
            public int Free { get; internal set; } = -1;
            public int Finish { get; internal set; } = -1;
            public int Figure { get; internal set; } = -1;
            /// <summary>The name board's writer; a text setter made and bound.</summary>
            public int Write { get; internal set; } = -1;
            public int Setter { get; internal set; } = -1;
            public int Bind { get; internal set; } = -1;
            public List<string> Missing { get; } = new List<string>();
            public bool Ok => Missing.Count == 0;
            /// <summary>(1.50.0) The play of a line's look and of a label's: what the lines and the small icons need
            /// more than the boxes. Without them the boxes stand without lines.</summary>
            public int LinePlay { get; internal set; } = -1;
            public int LabelPlay { get; internal set; } = -1;
            public List<string> LinesMissing { get; } = new List<string>();
        }

        /// <summary>The places, each found once by its bytes; `give` the tree's giving of a job to its place, as the
        /// filling's call of it names it (JobRoom.Screen.TreeJob).</summary>
        public static Sites Find(ReadOnlySpan<byte> image, List<Section> sections, int give)
        {
            var sites = new Sites();
            sites.Update = SpriteTextures.Once(image, sections, UpdateBytes, "the job tree's update", sites.Missing);
            if (sites.Update >= 0)
            {
                sites.Pressed = CallAt(image, sites.Update + UpdatePressedAt, "the job tree's asking of a key", sites.Missing);
                int call = SpriteTextures.Once(image, sections, UpdateCallBytes, "the call of the job tree's update", sites.Missing);
                if (call >= 0 && CallAt(image, call + UpdateCallAt, "the call of the job tree's update", sites.Missing) != sites.Update)
                    sites.Missing.Add("the call of the job tree's update (it isn't of the update found)");
            }
            int focus = SpriteTextures.Once(image, sections, FocusBytes, "the job tree's focusing of a box", sites.Missing);
            if (focus >= 0)
                sites.Focus = CallAt(image, focus + FocusCallAt, "the job tree's focusing of a box", sites.Missing);
            sites.Shown = SpriteTextures.Once(image, sections, ShownBytes, "the job tree's showing", sites.Missing);
            sites.Release = SpriteTextures.Once(image, sections, ReleaseBytes, "the job tree's giving back of its figures",
                                                sites.Missing);
            if (sites.Release >= 0)
            {
                sites.Keeper = NamedAt(image, sites.Release + ReleaseKeeperAt, "the figures' keeper", sites.Missing);
                sites.Clear = CallAt(image, sites.Release + ReleaseClearAt, "the clearing of a figure's slot", sites.Missing);
                sites.Sprites = NamedAt(image, sites.Release + ReleaseSpritesAt, "the sprites' keeper", sites.Missing);
                sites.Free = CallAt(image, sites.Release + ReleaseFreeAt, "the giving back of a sprite's slot", sites.Missing);
            }
            if (give <= 0 || give + WriteCallAt + 5 > image.Length || !Places.At(image, give + GiveAt, Places.Pattern(GiveBytes))
                || !Places.At(image, give + WriteAt, Places.Pattern(WriteBytes)))
                sites.Missing.Add("the job tree's giving of a job to its place (it isn't as it was measured)");
            else
            {
                sites.Finish = CallAt(image, give + GiveFinishAt, "the finishing of a figure's record", sites.Missing);
                sites.Figure = CallAt(image, give + GiveFigureAt, "the giving of a figure", sites.Missing);
                sites.Write = CallAt(image, give + WriteCallAt, "the name board's writer", sites.Missing);
                if (sites.Keeper >= 0 && NamedAt(image, give + GiveKeeperAt, "the figures' keeper", sites.Missing) != sites.Keeper)
                    sites.Missing.Add("the figures' keeper (the tree's giving and its giving back name two)");
            }
            int setter = SpriteTextures.Once(image, sections, SetterBytes0, "the making of a text setter", sites.Missing);
            if (setter >= 0)
                sites.Setter = CallAt(image, setter + SetterCallAt, "the making of a text setter", sites.Missing);
            int bind = SpriteTextures.Once(image, sections, BindBytes, "the binding of a text setter", sites.Missing);
            if (bind >= 0)
                sites.Bind = CallAt(image, bind + BindCallAt, "the binding of a text setter", sites.Missing);
            sites.LinePlay = SpriteTextures.Once(image, sections, LinePlayBytes, "the job tree's play of a line", sites.LinesMissing);
            sites.LabelPlay = SpriteTextures.Once(image, sections, LabelPlayBytes, "the job tree's play of a level's label",
                                                  sites.LinesMissing);
            return sites;
        }

        /// <summary>The routine a call at `at` names (below 0 and said: no call there, or it names no place of the
        /// program).</summary>
        static int CallAt(ReadOnlySpan<byte> image, int at, string what, List<string> missing)
        {
            if (at < 0 || at + 5 > image.Length || image[at] != 0xE8)
            {
                missing.Add($"{what} (no call where it should be)");
                return -1;
            }
            long to = (long)at + 5 + System.Buffers.Binary.BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at + 1, 4));
            if (to <= 0 || to >= image.Length)
            {
                missing.Add($"{what} (its call names no place in the program)");
                return -1;
            }
            return (int)to;
        }

        /// <summary>The place a `mov rcx, [rip + x]` at `at` names, a pointer (below 0 and said: it isn't there, or it
        /// names no place of the program).</summary>
        static int NamedAt(ReadOnlySpan<byte> image, int at, string what, List<string> missing)
        {
            if (at < 0 || at + 7 > image.Length || image[at] != 0x48 || image[at + 1] != 0x8B || image[at + 2] != 0x0D)
            {
                missing.Add($"{what} (not named where it should be)");
                return -1;
            }
            long to = (long)at + 7 + System.Buffers.Binary.BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at + 3, 4));
            if (to <= 0 || to + 8 > image.Length)
            {
                missing.Add($"{what} (it names no place in the program)");
                return -1;
            }
            return (int)to;
        }
    }
}
