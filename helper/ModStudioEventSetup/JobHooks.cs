// Mod Studio Framework: (1.36.0) a mod's own job made in the game: its record
// written, the game's code stepped into where it needs to know the job
// (JobRoom.Code), its row given to the Job table as it loads, and a place on the
// job screen. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// The place: with Dark Knight & Onion Knight (Generic) on (Zodi's choice: "Its
// empty places") its job screen's second page lists what its `_extraJobs` holds,
// so the numbers given are added to that list. That mod's list is its own: read
// from it for facts only, nothing copied, its fields found by name; when they
// aren't there the job has no place, said.
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using Reloaded.Hooks.Definitions;
using Reloaded.Hooks.Definitions.X64;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    public sealed unsafe class JobHooks
    {
        readonly List<JobRoom.Given> _given;
        readonly Action<string> _say;
        readonly List<object> _kept = new List<object>();
        readonly HashSet<nint> _copies = new HashSet<nint>();
        readonly HashSet<string> _saidOnce = new HashSet<string>();
        IHook<ItemHooks.SheetInitFunction>? _sheetInit;

        // (1.38.0) A unit's progress in more than one job (JobProgress): the native code's call when another job is
        // asked for, and four hooks of the game's own: its making of a battle unit from a party's record, its writing
        // of one back, its writing of a save's state and its loading of one. (1.38.1) And the native code's call as
        // the game takes its copy of a battle or puts it back (a battle started again). (1.38.2, test 82) Three more
        // hooks of the game's own: its maker of a record of a battle unit and its copier of a battle unit's progress
        // for a view (the unit's own job loaded before the game reads it), and its putting back of the plain state as
        // a battle is started again from its start (read as a save loaded). (1.38.3, test 83) Two more: the menu's
        // update of the status card and the card made of a record handed to it, each of which copies a record of the
        // menu's before the job's slot is asked (the record's own job loaded before the game copies).
        [Function(CallingConventions.Microsoft)]
        public delegate nint FourFunction(nint a, nint b, nint c, nint d);

        static JobProgress? s_progress;
        static JobHooks? s_hooks;
        static readonly object s_lock = new object();
        int _refusedSaid;
        JobProgress? _progress;
        IHook<FourFunction>? _build, _writeBack, _saveWrite, _made, _shown, _restart, _status, _card;
        IHook<SaveFallbackHook.SaveLoadFunction>? _saveLoad;
        byte* _bank;
        byte* _copyBank;
        short* _menuIndex;
        byte** _menuTable;
        Func<int, string?>? _nameOf;

        [UnmanagedCallersOnly]
        static void SwapEntry(int job)
        {
            try
            {
                lock (s_lock)
                    s_progress?.Swap(job);
                s_hooks?.SayRefused();
            }
            catch (Exception)
            {
            }
        }

        /// <summary>(1.38.1) The game's copy of the battle. (1.38.2) About to be taken (JobRoom.RetryCopied: the mark
        /// written into the variables it takes), or put back: the party's records and the units, whose variables are
        /// still in the copy (RetryPart), then the rest, the variables with it (RetryWhole).</summary>
        [UnmanagedCallersOnly]
        static void RetryEntry(int which)
        {
            var hooks = s_hooks;
            if (hooks == null)
                return;
            try
            {
                var said = new List<string>();
                lock (s_lock)
                {
                    if (which == JobRoom.RetryCopied)
                        hooks._progress!.Copied(new Span<byte>(hooks._bank, Framework.BankBytes), said);
                    else if (which == JobRoom.RetryPart)
                        hooks._progress!.Restored(new ReadOnlySpan<byte>(hooks._copyBank, Framework.BankBytes), true,
                                                  hooks._nameOf!, said);
                    else
                        hooks._progress!.Restored(new ReadOnlySpan<byte>(hooks._bank, Framework.BankBytes), false,
                                                  hooks._nameOf!, said);
                }
                foreach (var line in said)
                    hooks.SayOnce(line);
                hooks.SayRefused();
            }
            catch (Exception)
            {
            }
        }

        // (1.39.0) The job screen's own rows (JobScreen): the native code's two calls, as the game's filling of the
        // screen has listed a unit's jobs and as its cursor's step asks its step between the rows. A fault leaves the
        // game's own answer: the count it listed, the row the cursor was in.
        JobScreen? _screen;
        /// <summary>(1.40.0) The game's own job records, the longer table the game's code reads now (null: not made)
        /// and the game's own as they were last seen.</summary>
        byte* _gameRecords, _table;
        byte[] _recordsSeen = Array.Empty<byte>();
        /// <summary>(1.42.0) The jobs' own sprites: the game's program, the places found, the longer tables (null: not
        /// made) and the game's own as they were last seen.</summary>
        byte* _start, _sprites;
        int _imageBytes;
        SpriteRoom.Sites? _spriteSites;
        byte[][] _spritesSeen = Array.Empty<byte[]>();

        /// <summary>(1.40.0) What others have written to the game's own job records since they were last seen (the mod
        /// loader, for a mod's JobData.xml) brought over to the longer table. (1.42.0) And to the game's own tables of
        /// what a sprite looks like (WotL Restoration's portraits' faces), to the longer ones.</summary>
        void BringOver()
        {
            lock (s_lock)
            {
                if (_table != null)
                    JobRecords.Sync(new ReadOnlySpan<byte>(_gameRecords, _recordsSeen.Length), _recordsSeen,
                                    new Span<byte>(_table, JobRecords.Bytes));
                if (_sprites != null && _spriteSites != null)
                    SpriteRoom.Sync(new ReadOnlySpan<byte>(_start, _imageBytes), _spriteSites, _spritesSeen,
                                    new Span<byte>(_sprites, SpriteRoom.RoomBytes), _given);
            }
        }

        [UnmanagedCallersOnly]
        static int ListEntry(int count)
        {
            try
            {
                s_hooks?.BringOver();
                var screen = s_hooks?._screen;
                return screen == null ? count : screen.Listed(count);
            }
            catch (Exception e)
            {
                s_hooks?.SayOnce($"the job screen's own rows couldn't be listed ({e.GetType().Name}: {e.Message}); the game's "
                                 + "own list is shown.");
                return count;
            }
        }

        [UnmanagedCallersOnly]
        static int VerticalEntry(int row, int min, int max, int pad, int other, nint screen, nint told)
        {
            try
            {
                var rows = s_hooks?._screen;
                return rows == null ? row : rows.Vertical(row, min, max, pad, other, screen, told);
            }
            catch (Exception e)
            {
                s_hooks?.SayOnce($"the job screen's own rows couldn't be stepped ({e.GetType().Name}: {e.Message}); the cursor "
                                 + "stays where it is.");
                return row;
            }
        }

        // (1.39.1) The filling's call for the job tree: the tree's place for the job at that number of the list. A
        // fault leaves the game's own: the number itself.
        // (1.49.0) With the job's record and the tree: in a filling run for the mods' jobs alone each record is handed to
        // Job Progress's own boxes (JobTree), and the game's places get none, after a fault too.
        [UnmanagedCallersOnly]
        static int TreeEntry(int index, nint record, nint tree)
        {
            JobScreen? rows = s_hooks?._screen;
            try
            {
                return rows == null ? index : rows.TreePlace(index, record, tree);
            }
            catch (Exception e)
            {
                if (rows != null && rows.Harvesting)
                {
                    s_hooks?.SayOnce($"one of the mods' jobs couldn't be given to its box on Job Progress ({e.GetType().Name}: "
                                     + $"{e.Message}); its box shows what it showed.");
                    return -1;
                }
                s_hooks?.SayOnce($"the job screen's own rows couldn't be matched to Job Progress ({e.GetType().Name}: {e.Message}); "
                                 + "the game's own places are used.");
                return index;
            }
        }

        // (1.49.0) The mods' jobs on Job Progress (JobTree): made where the job screen's own rows are, given the game's
        // own functions and told of the tree's update, showing and giving back by JobTreeHooks.
        JobTree? _tree;
        public JobTree? Tree => _tree;
        public JobScreen? Rows => _screen;
        /// <summary>(1.55.0) Whether ability 45 was made War of the Lions' Sanguine Sword (DarkKnightAbilities): its row of
        /// the Ability table is made then.</summary>
        public bool Sanguine { get; set; }

        /// <summary>(1.49.0) Job Progress left as the game's: no filling is run for the mods' jobs alone.</summary>
        public void TreeOff()
        {
            if (_screen != null)
            {
                _screen.Harvested = null;
                _screen.HarvestBegins = null;
                _screen.HarvestNone = null;
            }
            _tree = null;
        }

        // (1.39.3) After each of the game's two calls of its filling of the job screen: rows noted at that filling are
        // moved to. A fault leaves the rows as they are.
        [UnmanagedCallersOnly]
        static void AfterEntry()
        {
            try
            {
                s_hooks?._screen?.After();
            }
            catch (Exception e)
            {
                s_hooks?.SayOnce($"the job screen's own rows couldn't be moved to a unit's own job ({e.GetType().Name}: {e.Message}); "
                                 + "the rows stay as they are.");
            }
        }

        // (1.48.0) What opens a job (JobNeeds). The window of what the job at the cursor needs, in place of the game's
        // call of it: a fault before the game's window was shown shows it as the game would.
        JobAsker? _asker;

        [UnmanagedCallersOnly]
        static void NeedsEntry(nint screen)
        {
            JobScreen? rows = s_hooks?._screen;
            try
            {
                if (rows != null)
                    rows.Needs(screen);
            }
            catch (Exception e)
            {
                s_hooks?.SayOnce($"the window of what a job needs couldn't be given every needed job ({e.GetType().Name}: "
                                 + $"{e.Message}); it shows what the game finds.");
                try
                {
                    if (rows != null && !rows.Windowed)
                        rows.NeedsWindow(screen);
                }
                catch (Exception)
                {
                }
            }
        }

        // (1.48.0) Whether a job is open to a unit, as the lists of second skillsets and of other abilities are made. A
        // fault answers that it is, as before 1.48.0.
        [UnmanagedCallersOnly]
        static int OpenEntry(int unit, int job)
        {
            try
            {
                JobAsker? asker = s_hooks?._asker;
                return asker == null ? 1 : asker.Open(unit, job);
            }
            catch (Exception e)
            {
                s_hooks?.SayOnce($"whether a job is open to a unit couldn't be worked out ({e.GetType().Name}: {e.Message}); "
                                 + "its abilities are listed for every unit.");
                return 1;
            }
        }

        // (1.55.1) Job Summary's reads of the game's Onion Knight's words: the key read (its words for its level 8 where the
        // screen's unit's Onion Knight is level 8). A fault says so once and answers the key asked, as before 1.55.1.
        [UnmanagedCallersOnly]
        static int SummaryEntry(int key)
        {
            try
            {
                JobAsker? asker = s_hooks?._asker;
                return asker == null ? key : asker.SummaryKey(key);
            }
            catch (Exception e)
            {
                s_hooks?.SayOnce($"which words Job Summary shows for the game's Onion Knight couldn't be worked out "
                                 + $"({e.GetType().Name}: {e.Message}); it shows its words for every level.");
                return key;
            }
        }

        // (1.39.4) In the screen's step on the abilities' and the summary's pages, in place of the game's step from one
        // job to the next: the place gone to. A fault says so once and answers that nothing was pressed.
        [UnmanagedCallersOnly]
        static int CycleEntry(nint piece, int pressed, int held, nint told, nint screen)
        {
            try
            {
                JobScreen? rows = s_hooks?._screen;
                return rows != null ? rows.Cycle(piece, pressed, held, told, screen) : -1;
            }
            catch (Exception e)
            {
                s_hooks?.SayOnce($"the job screen's own rows couldn't go from one job to the next ({e.GetType().Name}: {e.Message}); "
                                 + "the job stays as it is.");
                return -1;
            }
        }

        /// <summary>(1.39.0) The job screen's own rows, each of the game's own functions called at its place in the
        /// program.</summary>
        static JobScreen MakeScreen(byte* start, JobRoom.Found found, JobRoom.Screen screen, IList<int> numbers, byte* cells)
        {
            int* sides = (int*)(cells + JobRoom.ScreenSidesCell);
            var rows = new JobScreen(numbers, (nint*)(start + screen.Root), (short*)(start + screen.ListAt),
                                     (short*)(start + found.MenuIndex), (byte**)(start + found.MenuTable),
                                     JobProgress.MenuRecords, (short*)(start + screen.Count), sides,
                                     (int*)(cells + JobRoom.ScreenAliveCell), (int*)(cells + JobRoom.ScreenHarvestCell));
            nint fill = (nint)(start + screen.Fill), place = (nint)(start + screen.Place), refresh = (nint)(start + screen.Refresh),
                 upDown = (nint)(start + screen.UpDown), cycle = (nint)(start + screen.CycleStep);
            rows.CycleStep = (piece, pressed, held, told) =>
                ((delegate* unmanaged<nint, int, int, nint, int>)cycle)(piece, pressed, held, told);
            rows.Fill = () => ((delegate* unmanaged<void>)fill)();
            rows.Place = (at, where) => ((delegate* unmanaged<nint, int, byte, void>)place)(at, where, 0);
            rows.Refresh = at => ((delegate* unmanaged<nint, void>)refresh)(at);
            rows.UpDown = (out int delta, out bool fresh, int pad, int other) =>
            {
                int step = 0;
                byte isNew = 1;
                byte any = ((delegate* unmanaged<int*, byte*, int, int, byte>)upDown)(&step, &isNew, pad, other);
                delta = step;
                fresh = isNew != 0;
                return any != 0;
            };
            rows.InUse = holder =>
                ((delegate* unmanaged<nint, byte>)(*(nint*)(*(nint*)holder + JobScreen.HolderInUse)))(holder) != 0;
            // (1.48.0) The game's own window of what a job needs.
            nint window = (nint)(start + screen.Window);
            rows.NeedsWindow = at => ((delegate* unmanaged<nint, void>)window)(at);
            return rows;
        }

        /// <summary>(1.38.1) What JobProgress wouldn't put away (a job's progress that read as less than the unit had),
        /// said once a job and place.</summary>
        void SayRefused()
        {
            string? line = null;
            lock (s_lock)
                if (_progress != null && _progress.Refused != _refusedSaid)
                {
                    _refusedSaid = _progress.Refused;
                    line = JobProgress.RefusedLine(_progress.RefusedJob, _progress.RefusedPlace);
                }
            if (line != null)
                SayOnce(line);
        }

        nint Build(nint battleUnit, nint party, nint c, nint d)
        {
            try
            {
                BringOver();
            }
            catch (Exception)
            {
                // The game's own build goes on with the records as they are.
            }
            nint answer = _build!.OriginalFunction(battleUnit, party, c, d);
            try
            {
                lock (s_lock)
                    _progress!.Built((byte*)battleUnit);
            }
            catch (Exception)
            {
            }
            return answer;
        }

        nint WriteBack(nint battleUnit, nint b, nint c, nint d)
        {
            // (1.53.0) A unit in one of the mods' jobs: that job loaded first (a guest who joins keeps its job's progress).
            try
            {
                lock (s_lock)
                    _progress!.WritingBack((byte*)battleUnit);
                SayRefused();
            }
            catch (Exception)
            {
                // The game's own writing goes on with the job loaded as it was.
            }
            nint answer = _writeBack!.OriginalFunction(battleUnit, b, c, d);
            try
            {
                lock (s_lock)
                    _progress!.WrittenBack((byte*)battleUnit, unchecked((int)(long)answer));
            }
            catch (Exception)
            {
            }
            return answer;
        }

        /// <summary>(1.38.2) The game is about to make a record of a battle unit (0x360048).</summary>
        nint Made(nint battleUnit, nint record, nint c, nint d)
        {
            try
            {
                lock (s_lock)
                    _progress!.Made((byte*)battleUnit);
                SayRefused();
            }
            catch (Exception)
            {
            }
            return _made!.OriginalFunction(battleUnit, record, c, d);
        }

        /// <summary>(1.38.2) The game is about to copy a battle unit's progress for a view (0xFCF80), by its number.</summary>
        nint Shown(nint battleUnit, nint view, nint c, nint d)
        {
            try
            {
                lock (s_lock)
                    _progress!.Shown(unchecked((int)(long)battleUnit));
                SayRefused();
            }
            catch (Exception)
            {
            }
            return _shown!.OriginalFunction(battleUnit, view, c, d);
        }

        /// <summary>(1.38.3) The menu is about to update the status card (0x2BD05C): it will copy the record its table
        /// names by the word that says which, and ask the job's slot only after. A word past the menu's records names
        /// none.</summary>
        nint Status(nint a, nint b, nint c, nint d)
        {
            try
            {
                int index = *_menuIndex;
                if ((uint)index < JobProgress.MenuRecords)
                {
                    lock (s_lock)
                        _progress!.Seen(_menuTable[index]);
                    SayRefused();
                }
            }
            catch (Exception)
            {
            }
            return _status!.OriginalFunction(a, b, c, d);
        }

        /// <summary>(1.38.3) The game is about to make the status card of a record handed to it (0x2C33D0), which it
        /// copies first.</summary>
        nint Card(nint record, nint b, nint c, nint d)
        {
            try
            {
                lock (s_lock)
                    _progress!.Seen((byte*)record);
                SayRefused();
            }
            catch (Exception)
            {
            }
            return _card!.OriginalFunction(record, b, c, d);
        }

        /// <summary>(1.38.2) The game put the plain state back as a battle is started again from its start (0x2CF768):
        /// the party's records and the variables are as they were before the battle, read as a save loaded.</summary>
        nint Restart(nint a, nint b, nint c, nint d)
        {
            nint answer = _restart!.OriginalFunction(a, b, c, d);
            try
            {
                var said = new List<string>();
                lock (s_lock)
                    _progress!.Load(new ReadOnlySpan<byte>(_bank, Framework.BankBytes), _nameOf!, said);
                foreach (var line in said)
                    SayOnce(line);
            }
            catch (Exception e)
            {
                SayOnce($"the units' progress in the mods' jobs wasn't read as the battle started again ({e.GetType().Name}: {e.Message}).");
            }
            return answer;
        }

        nint SaveWrite(nint a, nint b, nint c, nint d)
        {
            try
            {
                var said = new List<string>();
                lock (s_lock)
                    _progress!.Saving(new Span<byte>(_bank, Framework.BankBytes), said);
                foreach (var line in said)
                    SayOnce(line);
            }
            catch (Exception e)
            {
                SayOnce($"the units' progress in the mods' jobs wasn't kept as the game saved ({e.GetType().Name}: {e.Message}).");
            }
            return _saveWrite!.OriginalFunction(a, b, c, d);
        }

        int SaveLoad(int mode)
        {
            int answer = _saveLoad!.OriginalFunction(mode);
            try
            {
                BringOver();
                var said = new List<string>();
                lock (s_lock)
                    _progress!.Load(new ReadOnlySpan<byte>(_bank, Framework.BankBytes), _nameOf!, said);
                foreach (var line in said)
                    _say(line);
            }
            catch (Exception e)
            {
                _say($"the units' progress in the mods' jobs wasn't read as the save loaded ({e.GetType().Name}: {e.Message}).");
            }
            return answer;
        }

        JobHooks(List<JobRoom.Given> given, Action<string> say)
        {
            _given = given;
            _say = say;
        }

        void SayOnce(string line)
        {
            lock (_saidOnce)
                if (!_saidOnce.Add(line))
                    return;
            _say(line);
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern nint VirtualAlloc(nint address, nuint size, uint type, uint protect);

        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool VirtualProtect(nint address, nuint size, uint protect, out uint old);

        [DllImport("kernel32.dll")]
        internal static extern nint GetCurrentProcess();

        [DllImport("kernel32.dll")]
        internal static extern bool FlushInstructionCache(nint process, nint address, nuint size);

        internal const uint Commit = 0x1000, Reserve = 0x2000, ReadWrite = 0x04, ExecuteRead = 0x20;
        const long Reach = 0x7F000000;

        /// <summary>Memory of `size` bytes Windows gives after the program, near enough for four bytes of distance (0:
        /// none). (1.41.0) The abilities' room is asked for this way too (AbilityHooks).</summary>
        internal static nint Near(ulong imageBase, int imageSize, int size)
        {
            const ulong Granularity = 0x10000;
            ulong start = (imageBase + (ulong)imageSize + Granularity - 1) & ~(Granularity - 1);
            for (ulong at = start; at + (ulong)size < imageBase + (ulong)Reach; at += Granularity)
            {
                nint got = VirtualAlloc((nint)at, (nuint)size, Commit | Reserve, ReadWrite);
                if (got != 0)
                    return got;
            }
            return 0;
        }

        /// <summary>The jobs made so in the game, or null and why (nothing of the game's changed then).</summary>
        public static JobHooks? Arm(IReloadedHooks reloaded, GameMemory memory, JobRoom.Found found, List<JobRoom.Given> given,
                                    int sheetInit, Action<string> say, out string why, Places? places = null,
                                    Func<int, string?>? nameOf = null, IReadOnlyList<string>? folders = null,
                                    JobRoom.Screen? screen = null, JobRecords.Sites? records = null, int arithmeticks = -1,
                                    int arithmeticksThink = -1, int arithmeticksRandom = -1, SpriteRoom.Sites? sprites = null,
                                    (int Own, int Row, int Learn)? battle = null, IReadOnlyDictionary<string, int>? special = null)
        {
            byte* start = memory.Base;
            var image = new ReadOnlySpan<byte>(start, memory.Bytes.Length);
            ulong imageBase = (ulong)start;
            // (1.38.0) A page of code and, after it, a page the code's cells are in (JobRoom.CellsAfter).
            const int Room = JobRoom.CellsAfter;
            if (places == null || places.SaveLoad < 0 || places.SaveBank < 0 || places.Roster < 0)
            {
                why = "the game's load of a save wasn't found, so a unit's progress in the jobs couldn't be kept";
                return null;
            }
            if (found.CopyBankOf != places.SaveBank)
            {
                why = "the game's copy of a battle isn't taken from the save's variables as in the game this was made for, so "
                      + "a unit's progress in the jobs couldn't be kept";
                return null;
            }
            // (1.40.0) After the cells, where a job has a number past the game's last: the longer table of job records.
            const int TableRoom = 0x4000;
            if (records == null && given.Exists(g => g.Number >= JobRecords.GameCount))
            {
                why = "a job has a number past the game's last and the longer table of job records isn't made";
                return null;
            }
            // (1.42.0) After those, where a job has sprites of its own: the longer tables of what a sprite looks like.
            bool ownSprites = sprites != null && given.Exists(g => g.Sprite >= 0);
            if (sprites == null && given.Exists(g => g.Sprite >= 0))
            {
                why = "a job has sprites of its own and the longer tables of sprites aren't made";
                return null;
            }
            int spritesAfter = Room + JobRoom.CellsRoom + (records != null ? TableRoom : 0);
            nint code = Near(imageBase, memory.Bytes.Length, spritesAfter + (ownSprites ? SpriteRoom.RoomBytes : 0));
            if (code == 0)
            {
                why = "Windows gave no memory near the game's program for the jobs' native code";
                return null;
            }
            var bytes = JobRoom.Code(image, found, imageBase, (ulong)code, given, out var changes, screen, arithmeticks,
                                     arithmeticksThink, arithmeticksRandom, ownSprites ? sprites : null,
                                     battle?.Own ?? -1, battle?.Row ?? -1, battle?.Learn ?? -1, special);
            if (bytes.Length > Room)
            {
                why = $"the jobs' native code is {bytes.Length} bytes, past its {Room}";
                return null;
            }
            byte* table = records != null ? (byte*)code + Room + JobRoom.CellsRoom : null;
            if (records != null)
            {
                var named = JobRecords.Changes(records, imageBase, (ulong)table);
                if (named == null)
                {
                    why = "the longer table of job records is too far from the game's program";
                    return null;
                }
                changes.AddRange(named);
            }
            byte* spriteRoom = ownSprites ? (byte*)code + spritesAfter : null;
            if (ownSprites)
            {
                var moved = SpriteRoom.Changes(sprites!, imageBase, (ulong)spriteRoom);
                if (moved == null)
                {
                    why = "the longer tables of sprites are too far from the game's program";
                    return null;
                }
                changes.AddRange(moved);
            }
            Marshal.Copy(bytes, 0, code, bytes.Length);
            if (!VirtualProtect(code, (nuint)Room, ExecuteRead, out _))
            {
                why = "Windows wouldn't let the jobs' native code run";
                return null;
            }
            FlushInstructionCache(GetCurrentProcess(), code, (nuint)Room);
            var hooks = new JobHooks(given, say);
            // (1.38.0) The units' progress: the first job given is the one loaded until a save says another. (1.55.0) The
            // mods' own jobs alone (each with its place among the jobs given): the game's Dark Knight's and Onion Knight's
            // progress is the unit's own rows.
            var mods = JobRoom.Mods(given);
            hooks._progress = new JobProgress(start + places.Roster, start + found.Battle, start + found.Menus,
                                              start + found.BattleRecords, start + found.OneRecord,
                                              mods.ConvertAll(g => g.Job.Key), mods.ConvertAll(g => g.Number),
                                              folders ?? Array.Empty<string>(), (int*)(code + JobRoom.CellsAfter + JobRoom.LoadedCell),
                                              // (1.38.4) This run's copies of a battle counted from a number of its own.
                                              Random.Shared.Next(0x1000000));
            hooks._bank = start + places.SaveBank;
            hooks._copyBank = start + found.CopyBank;
            hooks._menuIndex = (short*)(start + found.MenuIndex);
            hooks._menuTable = (byte**)(start + found.MenuTable);
            hooks._nameOf = nameOf ?? (_ => null);
            lock (s_lock)
            {
                s_progress = hooks._progress;
                s_hooks = hooks;
            }
            *(nint*)(code + JobRoom.CellsAfter + JobRoom.SwapCell) = (nint)(delegate* unmanaged<int, void>)&SwapEntry;
            *(nint*)(code + JobRoom.CellsAfter + JobRoom.RetryCell) = (nint)(delegate* unmanaged<int, void>)&RetryEntry;
            // (1.55.1) Job Summary's reads of the game's Onion Knight's words (where the native code asks): set whatever
            // else is made, so the asking always has an answer.
            *(nint*)(code + JobRoom.CellsAfter + JobRoom.SummaryCell) = (nint)(delegate* unmanaged<int, int>)&SummaryEntry;
            if (screen != null)
            {
                // (1.39.2) The three numbers the window's side is read from are in the cells' page: the game's own
                // row ends until the framework arranges rows of its own (JobScreen writes them as it is made).
                // (1.39.3) So are what the layouts' move of a box is told of the 19 boxes, none until then.
                // (1.55.0) The jobs as the framework's own rows and Job Progress show them: the game's Dark Knight and Onion
                // Knight a mod gives first, then the mods' own jobs in the order given (Shown).
                int[] shown = JobRoom.Shown(given);
                hooks._screen = MakeScreen(start, found, screen, Array.ConvertAll(shown, k => given[k].Number),
                                           (byte*)code + JobRoom.CellsAfter);
                *(nint*)(code + JobRoom.CellsAfter + JobRoom.ScreenListCell) = (nint)(delegate* unmanaged<int, int>)&ListEntry;
                *(nint*)(code + JobRoom.CellsAfter + JobRoom.ScreenVerticalCell) =
                    (nint)(delegate* unmanaged<int, int, int, int, int, nint, nint, int>)&VerticalEntry;
                *(nint*)(code + JobRoom.CellsAfter + JobRoom.ScreenTreeCell) =
                    (nint)(delegate* unmanaged<int, nint, nint, int>)&TreeEntry;
                *(nint*)(code + JobRoom.CellsAfter + JobRoom.ScreenAfterCell) = (nint)(delegate* unmanaged<void>)&AfterEntry;
                *(nint*)(code + JobRoom.CellsAfter + JobRoom.ScreenCycleCell) =
                    (nint)(delegate* unmanaged<nint, int, int, nint, nint, int>)&CycleEntry;
                // (1.48.0) What opens a job: asked only where the framework's own rows show the jobs.
                var needsSaid = new List<string>();
                var needsPlan = JobNeeds.Plan.Make(given, needsSaid);
                // (1.55.0) For a need of a job mastered (the game's Dark Knight's): which places of the game's jobs'
                // skillsets hold an ability, as the program has them now.
                needsPlan.Places = JobNeeds.PlacesOf(image, found.Records, found.Skillsets);
                var asker = new JobAsker(needsPlan, hooks._progress!, hooks._menuIndex, hooks._menuTable,
                                         JobProgress.MenuRecords, s_lock);
                foreach (string line in needsSaid)
                    say(line);
                hooks._asker = asker;
                hooks._screen!.Mark = place => place >= 0 && place < shown.Length ? asker.Mark(shown[place]) : 0;
                hooks._screen.Needed = asker.Needed;
                hooks._screen.Stand = asker.Stand;
                // (1.55.1) A job needed mastered that the unit has mastered: "Mastered" in the window (JobScreen.Needs).
                hooks._screen.MasteredNeeds = asker.MasteredNeeds;
                hooks._screen.HasMastered = asker.HasMastered;
                *(nint*)(code + JobRoom.CellsAfter + JobRoom.ScreenNeedsCell) = (nint)(delegate* unmanaged<nint, void>)&NeedsEntry;
                *(nint*)(code + JobRoom.CellsAfter + JobRoom.OpenCell) = (nint)(delegate* unmanaged<int, int, int>)&OpenEntry;
                int needing = 0;
                for (int k = 0; k < given.Count; k++)
                    if (asker.Plan.Needs[k].Length > 0 || asker.Plan.Never[k])
                        needing++;
                if (needing > 0)
                    say(JobNeeds.Line(needing, given.Count));
                // (1.49.0) The mods' jobs on Job Progress: each job's box stands after the jobs of its mod it needs.
                // (1.50.0) What each needs is handed whole (JobTreeLines.cs): a line from a job of its mod it needs, a
                // small icon for one of the game's; a needed job's record for the unit on screen is the asker's.
                // (1.55.0) In the order the rows show the jobs (a need of the mods' by its place there).
                var needs = new List<JobTree.Need[]>();
                var placeOf = new int[given.Count];
                for (int place = 0; place < shown.Length; place++)
                    placeOf[shown[place]] = place;
                foreach (int k in shown)
                {
                    var list = new List<JobTree.Need>();
                    foreach (var need in asker.Plan.Needs[k])
                        list.Add(new JobTree.Need(need.Own >= 0 ? placeOf[need.Own] : -1,
                                                  need.Own >= 0 ? given[need.Own].Number : JobNeeds.JobOf(need.Known), need.Level,
                                                  need.Game < 0 && need.Mastered));
                    needs.Add(list.ToArray());
                }
                hooks._tree = new JobTree(needs, Array.ConvertAll(shown, k => given[k].Job.Name))
                {
                    Stand = (job, to) => asker.Stand(job, -1, to),
                    // (1.55.2) A job needed mastered: its small icon green only where the unit has mastered it; (1.56.0)
                    // and a line from a job of the mods' needed mastered.
                    HasMastered = asker.HasMasteredJob
                };
            }
            else if (given.Exists(g => g.Job.Needs.Length > 0))
                say(JobNeeds.NotAskedLine);
            hooks._build = reloaded.CreateHook<FourFunction>(hooks.Build, (long)(start + found.At["Build"]), -1);
            hooks._writeBack = reloaded.CreateHook<FourFunction>(hooks.WriteBack, (long)(start + found.At["WriteBack"]), -1);
            hooks._saveWrite = reloaded.CreateHook<FourFunction>(hooks.SaveWrite, (long)(start + found.At["SaveWrite"]), -1);
            hooks._saveLoad = reloaded.CreateHook<SaveFallbackHook.SaveLoadFunction>(hooks.SaveLoad, (long)(start + places.SaveLoad), -1);
            hooks._made = reloaded.CreateHook<FourFunction>(hooks.Made, (long)(start + found.At["Made"]), -1);
            hooks._shown = reloaded.CreateHook<FourFunction>(hooks.Shown, (long)(start + found.At["Shown"]), -1);
            hooks._restart = reloaded.CreateHook<FourFunction>(hooks.Restart, (long)(start + found.At["Restart"]), -1);
            hooks._status = reloaded.CreateHook<FourFunction>(hooks.Status, (long)(start + found.At["Status"]), -1);
            hooks._card = reloaded.CreateHook<FourFunction>(hooks.Card, (long)(start + found.At["Card"]), -1);
            hooks._made.Activate();
            hooks._shown.Activate();
            hooks._restart.Activate();
            hooks._status.Activate();
            hooks._card.Activate();
            hooks._build.Activate();
            hooks._writeBack.Activate();
            hooks._saveWrite.Activate();
            hooks._saveLoad.Activate();
            hooks._sheetInit = reloaded.CreateHook<ItemHooks.SheetInitFunction>(hooks.SheetInit, (long)(start + sheetInit), -1);
            hooks._sheetInit.Activate();
            int gameBytes = JobRecords.GameCount * JobRecords.RecordBytes;
            if (table != null)
                JobRecords.Fill(new ReadOnlySpan<byte>(start + found.Records, gameBytes), new Span<byte>(table, JobRecords.Bytes));
            foreach (var g in given)
            {
                // A number of the game's own table is written there, as before (others read it there); with the longer
                // table, every job's record is written into that.
                if (g.Number < JobRecords.GameCount)
                    memory.Writing(found.Records + JobRoom.RecordBytes * g.Number, JobRoom.RecordBytes,
                                   () => Marshal.Copy(g.Job.Record, 0, (nint)(start + found.Records + JobRoom.RecordBytes * g.Number),
                                                      JobRoom.RecordBytes));
                if (table != null)
                    Marshal.Copy(g.Job.Record, 0, (nint)(table + JobRoom.RecordBytes * g.Number), JobRoom.RecordBytes);
                // (1.37.0) Its own skillset's record. (1.55.0) The game's Dark Knight's skillset is the game's own (224, past
                // the 176 records), and Onion Knight has none: nothing is written for either.
                if (g.Game)
                    continue;
                byte[] skillset = JobRoom.SkillsetRecord(g.Job);
                int at = found.Skillsets + JobRoom.SkillsetBytes * g.Skillset;
                memory.Writing(at, skillset.Length, () => Marshal.Copy(skillset, 0, (nint)(start + at), skillset.Length));
            }
            if (table != null)
            {
                hooks._gameRecords = start + found.Records;
                hooks._table = table;
                hooks._recordsSeen = new ReadOnlySpan<byte>(start + found.Records, gameBytes).ToArray();
            }
            // (1.42.0) The longer tables of sprites: the game's rows, the jobs' own, and the game's as seen now.
            if (spriteRoom != null)
            {
                SpriteRoom.Fill(image, sprites!, new Span<byte>(spriteRoom, SpriteRoom.RoomBytes), given);
                lock (s_lock)
                {
                    hooks._start = start;
                    hooks._imageBytes = memory.Bytes.Length;
                    hooks._spriteSites = sprites;
                    hooks._spritesSeen = SpriteRoom.Seen(image, sprites!);
                    hooks._sprites = spriteRoom;
                }
            }
            foreach (var change in changes)
            {
                memory.Writing(change.At, change.Bytes.Length,
                               () => Marshal.Copy(change.Bytes, 0, (nint)(start + change.At), change.Bytes.Length));
                FlushInstructionCache(GetCurrentProcess(), (nint)(start + change.At), (nuint)change.Bytes.Length);
            }
            why = "";
            return hooks;
        }

        int SheetInit(nint sheet, nint file)
        {
            try
            {
                BringOver();
                Give(sheet, file);
            }
            catch (Exception e)
            {
                SayOnce($"the mods' jobs got no names ({e.GetType().Name}: {e.Message}); the game's Job table is used.");
            }
            return _sheetInit!.OriginalFunction(sheet, file);
        }

        void Give(nint sheet, nint file)
        {
            if (sheet == 0 || file == 0)
                return;
            // (1.37.0) The skillsets' names, in JobCommand. (1.42.1) A row for each job's own sprite, in CharShape. (1.43.0)
            // A row for each palette of a job's own colors, in CharCLUT. (1.46.0) A row for each picture of a job's own the
            // framework answers, in Icon. (1.47.0) A row for each job's words on Job Summary, in UiJobAbilityHelp.
            int number = *(int*)(sheet + Hooks.SheetNumber);
            bool commands = number == JobRoom.CommandSheet;
            bool shapes = number == SpriteRoom.ShapeSheet && _given.Exists(g => g.Sprite >= 0);
            bool cluts = number == SpriteRoom.ClutSheet && _given.Exists(g => g.Sprite >= 0 && g.Job.HasColors);
            bool pictures = number == JobArt.IconSheet
                            && _given.Exists(g => g.Pictures[0] && g.Job.Art.PictureOwn[0] != null
                                                  || g.Pictures[1] && g.Job.Art.PictureOwn[1] != null);
            bool helps = number == JobWords.HelpSheet && _given.Count > 0;
            // (1.55.0) The game's Dark Knight's abilities' names (its job's file's, else War of the Lions'), in Ability.
            bool names = number == AbilityWords.Sheet && _given.Exists(g => g.Job.Game == JobFile.DarkKnight);
            // (1.48.0) A row for each job's needs, in GeneralJob, where the framework's own rows show the jobs.
            JobAsker? asker = _asker;
            bool needs = number == JobNeeds.Sheet && asker != null && _given.Count > 0;
            // (1.55.1) The window's two level texts saying "Mastered" for a job needed mastered (the game's Dark Knight's
            // Knight and Black Mage), in UI, where the framework's own rows show the jobs.
            bool masteredWords = number == JobNeeds.UiSheet && asker != null
                                 && Array.Exists(asker.Plan.Needs, list => Array.Exists(list, n => n.Mastered));
            if (number != JobRoom.JobSheet && !commands && !shapes && !cluts && !pictures && !helps && !needs && !names
                && !masteredWords)
                return;
            string name = masteredWords ? "UI" : names ? "Ability" : needs ? "GeneralJob" : helps ? "UiJobAbilityHelp"
                          : pictures ? "Icon" : cluts ? "CharCLUT" : shapes ? "CharShape" : commands ? "JobCommand" : "Job";
            if (*(nint*)(sheet + Hooks.SheetFile) != file)
            {
                SayOnce($"{name} gets no rows: the table isn't laid out as in the game this was made for.");
                return;
            }
            nint bytes = *(nint*)(file + Hooks.FileBytes);
            long size = *(long*)(file + Hooks.FileSize);
            lock (_copies)
                if (_copies.Contains(bytes))
                    return;
            if (bytes == 0 || size <= 0 || size > Hooks.MostTable)
            {
                SayOnce($"{name} gets no rows: its file is {size} bytes.");
                return;
            }
            var said = new List<string>();
            var loaded = new ReadOnlySpan<byte>((void*)bytes, (int)size);
            string why;
            int shaped = 0;
            var table = masteredWords ? JobNeeds.WithMasteredWords(loaded, said, out why, out shaped)
                      : names ? AbilityWords.WithGameNames(loaded, _given, Sanguine, said, out why, out shaped)
                      : needs ? JobNeeds.WithRows(loaded, _given, asker!.Plan, said, out why, out shaped)
                      : helps ? JobWords.WithHelpRows(loaded, _given, said, out why, out shaped)
                      : pictures ? JobArt.WithPictureRows(loaded, _given, said, out why, out shaped)
                      : cluts ? SpriteRoom.WithClutRows(loaded, _given, said, out why, out shaped)
                      : shapes ? SpriteRoom.WithShapeRows(loaded, _given, said, out why, out shaped)
                      : commands ? JobRoom.WithCommandRows(loaded, _given, said, out why)
                      : JobRoom.WithJobRows(loaded, _given, said, out why);
            foreach (var line in said)
                SayOnce(line);
            if (table == null)
            {
                SayOnce(masteredWords ? JobNeeds.NoMasteredLine(why)
                        : names ? $"{name} gets no names of the game's Dark Knight's abilities: {why}."
                        : needs ? JobNeeds.NoRowsLine(why)
                               : helps ? JobWords.NoRowsLine(why)
                               : shapes ? $"{name} gets no rows: {why}. Putting a unit of a job with its own sprites on the battlefield "
                                 + "stops the game."
                               : cluts ? $"{name} gets no rows: {why}. The jobs with colors of their own wear their Look's colors instead."
                               : pictures ? $"{name} gets no rows: {why}. The jobs with pictures of their own show none."
                               : $"{name} gets no rows: {why}.");
                return;
            }
            // (1.48.0) The tables the window of what a job needs is answered from, as loaded with the mods' rows.
            if (needs)
                asker!.General = table;
            else if (number == JobRoom.JobSheet && asker != null)
                asker.Jobs = table;
            if ((pictures || helps || needs || names || masteredWords) && shaped == 0)
                return;
            nint copy = (nint)NativeMemory.Alloc((nuint)table.Length);
            Marshal.Copy(table, 0, copy, table.Length);
            lock (_copies)
                _copies.Add(copy);
            *(long*)(file + Hooks.FileSize) = table.Length;
            *(nint*)(file + Hooks.FileBytes) = copy;
            _say(masteredWords ? JobNeeds.MasteredLine(shaped)
                : names ? AbilityWords.GameNamesLine(shaped)
                : needs ? JobNeeds.RowsLine(shaped)
                : helps ? JobWords.HelpRowsLine(shaped)
                : pictures ? JobArt.PictureRowsLine(shaped)
                : cluts ? SpriteRoom.ClutLine(shaped)
                : shapes ? SpriteRoom.ShapeLine(shaped)
                : commands
                ? JobRoom.CommandLine(_given.FindAll(g => g.Skillset != 0).Count)
                : $"Job: the mods' jobs' {_given.Count} row{(_given.Count == 1 ? "" : "s")} written.");
        }
    }
}
