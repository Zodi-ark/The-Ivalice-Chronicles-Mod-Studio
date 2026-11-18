// Mod Studio Framework: the side quests' framework joined to the running
// game, through Reloaded-II's shared hooks (reloaded.sharedlib.hooks, whose
// interfaces, LGPL-3.0, ship beside this mod). Part of The Ivalice Chronicles
// Mod Studio, GPL-3.0.
//
// Made only when some mod gives a side quest. Six of the game's functions
// (Places.cs) get a hook each (the sixth, the world map's travel check, when
// it is found), a seventh when a quest fights a battle of its own, each
// handing everything that isn't the quests' to the game's own function
// unchanged:
// - the tables' setup: a table the quests add rows to is given a copy of
//   the file it loaded with their rows (Framework.WithRows), before the game
//   reads it; EventId's rows of their events are made as the game's own
//   world map events' (Framework.MakeEventRows);
// - the scripts' reader: a quest's event is read from the quest, not from a
//   file of the game's;
// - the two variable functions (the events' and the world map's): a quest
//   flag is read and written in the variables' last 340 bytes; (1.2.1) while
//   a quest's event plays, the events' never changes the story's progress
//   (variable 110);
// - (1.2.1) the game's progress: while a quest's event plays, it isn't set
//   to what a quest's script sets it to (a story scene's instruction E9,
//   copied into a quest, would set the world map's objective back);
// - (1.2.0) the battles' units, only when a quest has battles of its own: a
//   quest's battle (a number the framework gave) is handed its units;
// - (1.2.2) the world map's travel check: a quest's event waiting where you
//   stand doesn't stop travel on (the game's own events let you go back
//   only the way you came); (1.2.3) through native code that keeps every
//   register (Thunks.cs), as the game's travel step counts on, C# asked only
//   when the game would stop a travel;
// - (1.2.4) and in the world map's variable function, the framework's
//   passing-through variable (Framework.PassingThrough), which a start that
//   waits until its place is chosen tests last: 1 while a travel passes
//   through the place, from the travel's state (Places.TravelFlags,
//   TravelDone, TravelLegs), said once when it keeps an event from loading;
// - (1.2.5) the world map screen's showing of a place, when a quest has a
//   Marker: where one of its starts waits, the place shows the game's quest
//   marker in the quest's color (Marker.cs);
// - (1.15.0) the taverns' test of a rumor told, when a quest has rumors: a
//   quest's rumor is told in its towns while its When holds
//   (Framework.RumorTold), and once the taverns have shown it (the save's
//   byte for it 0) its flag is set before any quest flag is read;
// - (1.21.0) a place's settlement menu's entries, when a mod has a dungeon:
//   at a mod's dungeon its floors listed now (each waiting for a quest flag,
//   or listed from the start), as Midlight's Deep lists its own; and two
//   answers the places' native code asks (Destinations.cs): a floor chosen
//   (one of its battles picked evenly and kept where the roll keeps its own)
//   and the Deep's list's read of a floor's row (its name and words);
// - (1.24.0) in the events' variable function, the game's battle won event
//   given to play at a mod's dungeon: the won flag of the floor whose battle
//   it was, which lists the floor after it from then on; (1.25.0) a quest's
//   battle played at the floor in place of its own, its won event given,
//   the same; (1.25.1) a win given twice in one battle said once.
// Nothing here throws into the game: a fault is said once, and the game's
// own function does the work.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using Reloaded.Hooks.Definitions;
using Reloaded.Hooks.Definitions.X64;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    public sealed unsafe class Hooks
    {
        [Function(CallingConventions.Microsoft)]
        public delegate int SheetInitFunction(nint sheet, nint file);

        [Function(CallingConventions.Microsoft)]
        public delegate byte ScriptReaderFunction(uint sector, nint buffer);

        [Function(CallingConventions.Microsoft)]
        public delegate int EventVariablesFunction(int op, int variable, int operand, nint unused, byte fifth);

        [Function(CallingConventions.Microsoft)]
        public delegate int WorldVariablesFunction(int op, int variable, int operand);

        [Function(CallingConventions.Microsoft)]
        public delegate nint EncounterFunction();

        /// <summary>(1.33.0) The game's making of a battle's unit from its battle file's entry: the unit, the entry, a
        /// number it keeps, its mode, its OverrideEntryData row; -1 when it makes none.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate int UnitMadeFunction(nint unit, nint entry, int number, int mode, nint row);

        [Function(CallingConventions.Microsoft)]
        public delegate void ProgressFunction(nint progress, int track, int value);

        [Function(CallingConventions.Microsoft)]
        public delegate byte TravelCheckFunction();

        /// <summary>(1.2.3) What the travel check's stand-in asks when the game would stop a
        /// travel: 0 lets it go, 1 stops it.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate byte TravelStopFunction();

        /// <summary>(1.2.5) The world map screen's showing of a place and its marker: the screen, the
        /// place's state (16 bytes), the place.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate void MarkerStateFunction(nint screen, nint state, int place);

        /// <summary>(1.15.0) The taverns' test of a rumor told: its key, a place (less than 0: anywhere); 1 if told.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate byte RumorTestFunction(int key, int place);

        /// <summary>(1.29.0) The tavern's agent: its screen, its state, an action (0 marks the rumor of `key` read), a
        /// key.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate nint RumorAgentFunction(nint screen, nint state, int action, int key);

        /// <summary>(1.17.0) The helper's own roll of a mod's battle ground's random battles, where the roll's native
        /// code sends a mod's own place (Travel.RollStub): the place, the road arrived along, a battle forced; 1 with
        /// the battle picked kept where the game's roll keeps its own, else 0.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate int GroundRollFunction(int place, int road, byte forced);

        /// <summary>(1.18.0) The Outfitter's stock (0x288E54): a unit (whose equipment a list may check), a town (the
        /// place Ramza stands on, variable 49), a list's category, the list (items as words, -1 after the last), how
        /// it is checked against the unit (0 not, 1 marked, 2 only those it can equip), whether it is sorted; how many
        /// items.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate int StockFunction(short unit, short town, short category, nint list, int mode, byte sort);

        /// <summary>(1.21.0) A place's settlement menu's entries (0x3449B0): the place, where its entries go; how
        /// many.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate int EntriesFunction(int place, nint entries);

        /// <summary>(1.21.0) A mod's dungeon's floor chosen (the floor slot, asked by native code): the place; 1 when
        /// its battle is picked and kept where the roll keeps its own, else 0.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate int FloorFunction(int place);

        /// <summary>(1.21.0) The Deep's list's read of a floor's row at a mod's dungeon (the row slot, asked by native
        /// code): the place, the floor's place in the list; its row, or 0 (the game's).</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate nint RowFunction(int place, int key);

        /// <summary>(1.23.0) The UI's text by its number (0x3DBE88): its characters (the game's empty ones for none).</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate nint UiTextFunction(int number);

        /// <summary>(1.23.0) A row by two keys (0x3DBCE4): its sheet, its keys; the row, or 0.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate nint TwoKeyRowFunction(int sheet, int key, int key2);

        /// <summary>(1.23.0) A button guide shown (0xEB65C): -, the guide, its rows shown (a bit each).</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate void GuideShowFunction(nint unused, int guide, int rows);

        /// <summary>(1.23.0) The Deep's list's About key's guide opened (0xEE118).</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate void AboutFunction();

        /// <summary>Where, in a table, its number and its file are; where, in a file, its bytes and size.</summary>
        internal const int SheetNumber = 8, SheetFile = 0x30, FileBytes = 0x38, FileSize = 0x40;
        /// <summary>The most a table's file is taken to be (the game's largest is under 1 MB).</summary>
        internal const long MostTable = 64L << 20;

        readonly byte* _base;
        readonly Places _places;
        readonly Action<string> _say;
        readonly Framework _framework;
        readonly object _lock = new object();
        /// <summary>The copies of tables given to the game: kept for as long as it runs.</summary>
        readonly List<nint> _copies = new List<nint>();
        readonly HashSet<string> _saidOnce = new HashSet<string>();

        IHook<SheetInitFunction>? _sheetInit;
        IHook<ScriptReaderFunction>? _scriptReader;
        IHook<EventVariablesFunction>? _eventVariables;
        IHook<WorldVariablesFunction>? _worldVariables;
        IHook<EncounterFunction>? _encounter;
        /// <summary>(1.33.0) The making of a battle's unit, hooked when a quest's unit has its own name.</summary>
        IHook<UnitMadeFunction>? _unitMade;
        IHook<ProgressFunction>? _progress;
        IHook<TravelCheckFunction>? _travel;
        /// <summary>(1.2.3) The travel check's stand-in (native, Thunks.TravelCheck), the C# it asks,
        /// and where it finds the game's own check: kept as long as the game runs.</summary>
        IReverseWrapper<TravelStopFunction>? _travelStop;
        nint _travelStandIn, _travelOriginal;
        /// <summary>The quests' battles' units, where the game is handed them: kept as long as it runs.</summary>
        readonly Dictionary<int, nint> _units = new Dictionary<int, nint>();
        /// <summary>(1.2.5) The world map screen's showing of a place, hooked when a quest has a Marker.</summary>
        IHook<MarkerStateFunction>? _markerState;
        Marker? _marker;
        Marker.ShowFunction? _show;
        /// <summary>(1.8.0) The mods' own places a start with a Marker waits at (past the game's 48).</summary>
        readonly List<int> _modMarked = new List<int>();
        /// <summary>(1.15.0) Whether the quests' rumors are told (planned, and the taverns' sites found), and the
        /// taverns' test of a rumor told, hooked when they are.</summary>
        readonly bool _rumors;
        IHook<RumorTestFunction>? _rumorTest;
        IHook<RumorAgentFunction>? _rumorAgent;
        /// <summary>(1.17.0) The helper's own roll of the mods' battle grounds (called by native code: kept as long as
        /// the game runs), and its random numbers.</summary>
        IReverseWrapper<GroundRollFunction>? _groundRoll;
        readonly Random _random = new Random();
        /// <summary>(1.18.0) The mods' towns' menus: the Outfitter's stock, hooked when some mod's town has a menu and
        /// its site was found.</summary>
        IHook<StockFunction>? _stock;
        /// <summary>(1.21.0) The mods' dungeons: the settlement menu's entries hooked, the helper's own answers to a
        /// floor chosen and to a floor's row (called by native code: kept as long as the game runs), and each floor's
        /// row (Framework's floors' order, by dungeon).</summary>
        IHook<EntriesFunction>? _entries;
        IReverseWrapper<FloorFunction>? _floor;
        IReverseWrapper<RowFunction>? _row;
        readonly Dictionary<(int Place, int Floor), nint> _floorRows = new Dictionary<(int Place, int Floor), nint>();
        /// <summary>(1.25.1) The floors whose win was given in the battle being fought (Framework.FloorWins).</summary>
        readonly Framework.FloorWins _floorWins = new Framework.FloorWins();
        /// <summary>(1.23.0) A mod's dungeon's list's own looks (Zodi's test 49): the UI text's, the guide's page's, the
        /// button guide's and the About key's hooks, and what they give (DungeonLooks).</summary>
        DungeonLooks? _looks;
        IHook<UiTextFunction>? _uiText;
        IHook<TwoKeyRowFunction>? _twoKeyRow;
        IHook<GuideShowFunction>? _guideShow;
        IHook<AboutFunction>? _about;
        /// <summary>The game's own UI text by its number (the hook's original), made once: the hook is asked often.</summary>
        Func<int, nint>? _gameText;

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool VirtualProtect(void* address, nuint size, uint protect, out uint old);
        const uint ReadWrite = 0x04;

        Hooks(byte* start, Places places, Action<string> say, Framework framework)
        {
            _base = start;
            _places = places;
            _say = say;
            _framework = framework;
            // (1.18.0) A mod's town's tavern too: the quests' rumors naming it, the game's as at a town of none.
            _rumors = places.Rumors && (framework.RumorPlans.Count > 0 || framework.MenuTowns.Count > 0);
        }

        /// <summary>The hooks for the quests planned, made and active (before the game runs); the
        /// battles' units' only when a quest has a battle of its own. (1.8.0) `modRows`: the mods' own places
        /// given to the game (Destinations.cs), whose rows a marker at one of them is found in.</summary>
        public static Hooks Make(IReloadedHooks reloaded, byte* start, Places places, Action<string> say,
                                 Framework framework, int modRows = 0, nint groundSlot = 0, nint dungeonData = 0)
        {
            var hooks = new Hooks(start, places, say, framework);
            long loaded = (long)(nint)start;
            long at(int place) => loaded + place;
            foreach (var (number, units) in framework.Units)
            {
                nint copy = (nint)NativeMemory.Alloc((nuint)units.Length);
                Marshal.Copy(units, 0, copy, units.Length);
                hooks._units[number] = copy;
            }
            // Each kept before it is active, so a call the moment it is finds the game's own function.
            hooks._sheetInit = reloaded.CreateHook<SheetInitFunction>(hooks.SheetInit, at(places.SheetInit), -1);
            hooks._scriptReader = reloaded.CreateHook<ScriptReaderFunction>(hooks.ScriptReader,
                at(places.ScriptReader), -1);
            hooks._eventVariables = reloaded.CreateHook<EventVariablesFunction>(hooks.EventVariables,
                at(places.EventVariables), -1);
            hooks._worldVariables = reloaded.CreateHook<WorldVariablesFunction>(hooks.WorldVariables,
                at(places.WorldVariables), -1);
            hooks._progress = reloaded.CreateHook<ProgressFunction>(hooks.Progress, at(places.Progress), -1);
            if (places.Travel)
                hooks.HookTravel(reloaded, at(places.TravelCheck));
            if (hooks._units.Count > 0)
                hooks._encounter = reloaded.CreateHook<EncounterFunction>(hooks.Encounter, at(places.Encounter), -1);
            // (1.33.0) The quests' units' own names, each written into its unit as the game makes it from its battle file.
            if (hooks._units.Count > 0 && framework.OwnNames.Count > 0)
            {
                if (places.Names)
                    hooks._unitMade = reloaded.CreateHook<UnitMadeFunction>(hooks.UnitMade, at(places.UnitMade), -1);
                else
                    say($"the side quests' units' own names aren't shown: {string.Join(", ", places.MissingForNames)} "
                        + "wasn't found.");
            }
            if (places.Markers && framework.HasMarkers)
            {
                hooks._marker = new Marker(start, places, modRows);
                foreach (var s in framework.Starts)
                    if (s.Place >= Destinations.FirstNumber && s.Quest.Marker.Length > 0 && !hooks._modMarked.Contains(s.Place))
                        hooks._modMarked.Add(s.Place);
                // (1.25.0) A start waiting at a floor marks its dungeon.
                foreach (var f in framework.FloorStarts)
                    if (f.Quest.Marker.Length > 0 && !hooks._modMarked.Contains(f.Place))
                        hooks._modMarked.Add(f.Place);
            }
            // (1.20.0) The screen's showing of a place hooked too when a mod's town is darkened once a quest's flag is
            // set: each time the screen shows one of the game's places, the mods' towns darkened or not with them.
            if (places.Markers && (hooks._marker != null || framework.DarkPlaces.Count > 0))
                hooks._markerState = reloaded.CreateHook<MarkerStateFunction>(hooks.MarkerState, at(places.MarkerState), -1);
            if (hooks._rumors)
            {
                hooks._rumorTest = reloaded.CreateHook<RumorTestFunction>(hooks.RumorTest, at(places.RumorTest), -1);
                // (1.29.0) A quest's rumor's flag set as the tavern's agent marks it read (its key given as the game
                // starts, so the save's byte alone can't say whose it is).
                hooks._rumorAgent = reloaded.CreateHook<RumorAgentFunction>(hooks.RumorAgent, at(places.RumorAgent), -1);
            }
            // (1.18.0) The mods' towns' menus: their Outfitters' stock (the shops' masks made writable for it).
            if (framework.MenuTowns.Count > 0 && places.TownMenus)
            {
                if (VirtualProtect(start + places.ShopMasks, (nuint)(2 * Framework.ShopItems), ReadWrite, out _))
                {
                    hooks._stock = reloaded.CreateHook<StockFunction>(hooks.Stock, at(places.Stock), -1);
                    // (1.26.0) What the stock calls, for a mod's town's own items.
                    hooks.FindStockCalls(new ReadOnlySpan<byte>(start + places.Stock, StockSortAt + 5), places.Stock);
                }
                else
                    say("the mods' towns' Outfitters sell nothing: the shops' masks couldn't be made writable.");
            }
            hooks._sheetInit.Activate();
            hooks._scriptReader.Activate();
            hooks._eventVariables.Activate();
            hooks._worldVariables.Activate();
            hooks._progress.Activate();
            hooks._travel?.Activate();
            hooks._encounter?.Activate();
            hooks._unitMade?.Activate();
            hooks._markerState?.Activate();
            hooks._rumorTest?.Activate();
            hooks._rumorAgent?.Activate();
            hooks._stock?.Activate();
            // (1.21.0) The mods' dungeons: each floor's row made, the entries hooked, the two slots given the helper's
            // answers (the places' data, which held the native code's zero).
            if (framework.Dungeons.Count > 0 && dungeonData != 0 && places.Dungeons)
            {
                foreach (var (number, dungeon) in framework.Dungeons)
                    foreach (var floor in dungeon.Floors)
                    {
                        var row = Framework.FloorRow(floor);
                        nint copy = (nint)NativeMemory.Alloc((nuint)row.Length);
                        Marshal.Copy(row, 0, copy, row.Length);
                        hooks._floorRows[(number, floor.Index)] = copy;
                    }
                hooks._entries = reloaded.CreateHook<EntriesFunction>(hooks.Entries, at(places.Entries), -1);
                hooks._entries.Activate();
                hooks._floor = reloaded.CreateReverseWrapper<FloorFunction>(hooks.Floor);
                hooks._row = reloaded.CreateReverseWrapper<RowFunction>(hooks.Row);
                *(long*)(dungeonData + Destinations.FloorSlot) = (long)hooks._floor.WrapperPointer;
                *(long*)(dungeonData + Destinations.RowSlot) = (long)hooks._row.WrapperPointer;
                // (1.23.0) Its list's own title, words, art and About page (Zodi's test 49), when their sites were found.
                if (places.DungeonLooks)
                {
                    hooks._looks = new DungeonLooks(start, places, framework.Dungeons);
                    hooks._uiText = reloaded.CreateHook<UiTextFunction>(hooks.UiText, at(places.UiText), -1);
                    hooks._twoKeyRow = reloaded.CreateHook<TwoKeyRowFunction>(hooks.TwoKeyRow, at(places.TwoKeyRow), -1);
                    hooks._guideShow = reloaded.CreateHook<GuideShowFunction>(hooks.GuideShow, at(places.GuideShow), -1);
                    hooks._about = reloaded.CreateHook<AboutFunction>(hooks.About, at(places.AboutOpen), -1);
                    hooks._uiText.Activate();
                    hooks._twoKeyRow.Activate();
                    hooks._guideShow.Activate();
                    hooks._about.Activate();
                }
            }
            // (1.17.0) Last, once every battle's units are where the game is handed them: a mod's own place's roll
            // (the roll's native code's slot, which held its `.none`) to the helper's own.
            if (framework.Grounds.Count > 0 && groundSlot != 0 && places.GroundBattles)
            {
                hooks._groundRoll = reloaded.CreateReverseWrapper<GroundRollFunction>(hooks.GroundRoll);
                *(long*)groundSlot = (long)hooks._groundRoll.WrapperPointer;
            }
            return hooks;
        }

        /// <summary>(1.2.3) The travel check hooked to its stand-in (native code that keeps every
        /// register: the game's travel step keeps r9 to r11 across its call), which runs the
        /// game's check through the hook's way to it and asks TravelStopped only when it stops a
        /// travel. Not made when Windows gives no memory for the code (said: the quests' events
        /// then stop travel on as the game's do).</summary>
        void HookTravel(IReloadedHooks reloaded, long check)
        {
            _travelStop = reloaded.CreateReverseWrapper<TravelStopFunction>(TravelStopped);
            _travelOriginal = (nint)NativeMemory.AllocZeroed(8);
            _travelStandIn = Thunks.Executable(Thunks.TravelCheck((ulong)_travelOriginal,
                                                                  (ulong)_travelStop.WrapperPointer));
            if (_travelStandIn == 0)
            {
                _say("the world map's travel isn't looked after (no memory for its code): a side quest's event "
                     + "waiting where you stand stops travel on, as the game's own do.");
                return;
            }
            var hook = reloaded.CreateHook<TravelCheckFunction>((void*)_travelStandIn, check, -1);
            long original = (long)hook.OriginalFunctionAddress;
            if (original == 0)
            {
                _say("the world map's travel isn't looked after (its hook gave no way to the game's check): a side "
                     + "quest's event waiting where you stand stops travel on, as the game's own do.");
                return;
            }
            // Before the hook is active: the stand-in's first call finds the game's own check.
            *(long*)_travelOriginal = original;
            _travel = hook;
        }

        void SayOnce(string line)
        {
            lock (_lock)
                if (!_saidOnce.Add(line))
                    return;
            _say(line);
        }

        // --- the tables ----------------------------------------------------------

        int SheetInit(nint sheet, nint file)
        {
            try
            {
                Give(sheet, file);
            }
            catch (Exception e)
            {
                SayOnce($"a table's rows weren't added ({e.GetType().Name}: {e.Message}); the game's table is used.");
            }
            return _sheetInit!.OriginalFunction(sheet, file);
        }

        void Give(nint sheet, nint file)
        {
            if (sheet == 0 || file == 0)
                return;
            var framework = _framework;
            int number = *(int*)(sheet + SheetNumber);
            if (!framework.Adds(number))
                return;
            string name = Framework.SheetName(number);
            if (*(nint*)(sheet + SheetFile) != file)
            {
                SayOnce($"{name} gets no rows: the table isn't laid out as in the game this was made for.");
                return;
            }
            nint bytes = *(nint*)(file + FileBytes);
            long size = *(long*)(file + FileSize);
            lock (_lock)
                if (_copies.Contains(bytes))
                    return;
            if (bytes == 0 || size <= 0 || size > MostTable)
            {
                SayOnce($"{name} gets no rows: its file is {size} bytes.");
                return;
            }
            var said = new List<string>();
            // (1.30.0) Map 116's Map row naming its own PlaceName row, in place (its name's row: WithRows).
            if (number == Framework.MapSheet)
            {
                string unnamed = Framework.NameArena(new Span<byte>((void*)bytes, (int)size));
                if (unnamed.Length > 0)
                    SayOnce($"{name}: map {Framework.ArenaMap} isn't named {Framework.ArenaName}: {unnamed}.");
                else
                    _say($"{name}: map {Framework.ArenaMap} named {Framework.ArenaName}, for "
                         + $"{string.Join(", ", framework.ArenaUsers)}.");
                return;
            }
            if (number == Framework.EventRows)
            {
                // (1.9.0) Rows for the quests' events past 886 added first, in a copy given the game in its place.
                var grown = framework.EventRowsAdded(new ReadOnlySpan<byte>((void*)bytes, (int)size), out string whyNot,
                                                     out int grownBy);
                if (grown != null)
                {
                    nint grownCopy = (nint)NativeMemory.Alloc((nuint)grown.Length);
                    Marshal.Copy(grown, 0, grownCopy, grown.Length);
                    lock (_lock)
                        _copies.Add(grownCopy);
                    *(long*)(file + FileSize) = grown.Length;
                    *(nint*)(file + FileBytes) = grownCopy;
                    bytes = grownCopy;
                    size = grown.Length;
                    _say($"{name}: the side quests' {grownBy} row{(grownBy == 1 ? "" : "s")} past 886 added.");
                }
                else if (whyNot.Length > 0)
                    SayOnce($"{name} gets no rows past 886: {whyNot}; the side quests' events past 886 may show "
                            + "nothing before them.");
                // Rows the table has already, made in place.
                string not = framework.MakeEventRows(new Span<byte>((void*)bytes, (int)size), said, grown != null);
                foreach (var line in said)
                    SayOnce(line);
                if (not.Length > 0)
                    SayOnce($"{name}'s rows of the side quests' events aren't made as the game's: {not}.");
                else
                {
                    var made = new List<string>();
                    if (framework.Openings.Count > 0)
                        made.Add($"{framework.Openings.Count} opening{(framework.Openings.Count == 1 ? "" : "s")}");
                    if (framework.Fights.Count > 0)
                        made.Add($"{framework.Fights.Count} battle{(framework.Fights.Count == 1 ? "" : "s")}");
                    _say($"{name}: the side quests' {string.Join(" and ", made)} and their scenes made as the game's.");
                }
                return;
            }
            var table = framework.WithRows(number, new ReadOnlySpan<byte>((void*)bytes, (int)size), said, out string why,
                                           out int added);
            foreach (var line in said)
                SayOnce(line);
            if (table == null)
            {
                SayOnce($"{name} gets no rows: {why}.");
                return;
            }
            nint copy = (nint)NativeMemory.Alloc((nuint)table.Length);
            Marshal.Copy(table, 0, copy, table.Length);
            lock (_lock)
                _copies.Add(copy);
            *(long*)(file + FileSize) = table.Length;
            *(nint*)(file + FileBytes) = copy;
            // (1.12.0) "1 row", as Zodi asked (his tests' "1 rows"). (1.17.0) Whose they are: the side quests', the
            // mods' battle grounds' (their random battles' units and deploy prompts), or both; (1.21.0) or their
            // dungeons', each table's own (Framework.RowsWhose).
            if (number == Framework.NameSheet)
                _say($"{name}: map {Framework.ArenaMap}'s name, {Framework.ArenaName}, added (row {Framework.ArenaKey}).");
            else
                _say($"{name}: {framework.RowsWhose(number)} {added} row{(added == 1 ? "" : "s")} added.");
        }

        // --- the scripts ---------------------------------------------------------

        byte ScriptReader(uint sector, nint buffer)
        {
            try
            {
                var framework = _framework;
                if (buffer != 0)
                {
                    nint mode = *(nint*)(_base + _places.ScriptMode);
                    int ev = Framework.EventOfSector(sector, mode == 0 ? 1 : *(int*)(mode + 8));
                    // (1.30.0) A script naming Ramza given the party's Ramza, as he is in this chapter.
                    bool names = ev >= 0 && framework.NamesRamza(ev);
                    int ramza = names ? PartyRamza() : 0;
                    var script = ev < 0 ? null : framework.ScriptFor(ev, ramza);
                    if (script != null)
                    {
                        Marshal.Copy(script, 0, buffer, script.Length);
                        if (!names)
                            _say($"{framework.NameOf(ev)} begins (event {ev}).");
                        else if (ramza != 0)
                            _say($"{framework.NameOf(ev)} begins (event {ev}), naming Ramza as he is in "
                                 + $"{Framework.RamzaChapter(ramza)}.");
                        else
                            _say($"{framework.NameOf(ev)} begins (event {ev}); Ramza isn't found in the party, so it "
                                 + "names him as its script does.");
                        return 0;
                    }
                }
            }
            catch (Exception e)
            {
                SayOnce($"a side quest's script wasn't read ({e.GetType().Name}: {e.Message}).");
            }
            return _scriptReader!.OriginalFunction(sector, buffer);
        }

        // --- the flags -----------------------------------------------------------

        /// <summary>The variables, through the pointer the game's own function reads them by.</summary>
        Span<byte> Bank(int pointer)
        {
            nint bank = *(nint*)(_base + pointer);
            return bank == 0 ? Span<byte>.Empty : new Span<byte>((void*)bank, Framework.BankBytes);
        }

        /// <summary>A command with a quest flag in it, done (null) or made the game's own; a flag
        /// never reaches the game's function, which has no variable past 1,023.</summary>
        (int, int, int)? Flag(int pointer, int op, int variable, int operand)
        {
            try
            {
                var bank = Bank(pointer);
                if (bank.IsEmpty)
                    return null;
                bool flag = Framework.IsFlag(variable);
                int was = flag ? Framework.ReadFlag(bank, variable) : 0;
                var command = Framework.Command(bank, op, variable, operand);
                if (flag && Framework.ReadFlag(bank, variable) != was)
                {
                    _say($"{_framework.FlagNameOf(variable)} is {1 - was} (flag {variable}).");
                    // (1.13.0) The save marked with the numbers its quests' flags are set by.
                    Framework.Mark(bank, _framework.NumbersId);
                    // (1.31.0) A quest's reward as its flag is set.
                    var reward = _framework.RewardGiven(variable, was, 1 - was);
                    if (reward != null)
                        GiveReward(reward);
                }
                return command;
            }
            catch (Exception e)
            {
                SayOnce($"a side quest's flag wasn't kept ({e.GetType().Name}: {e.Message}).");
                return null;
            }
        }

        /// <summary>The event playing's number (variable 0x27), or -1 when the variables can't be read.</summary>
        int CurrentEvent()
        {
            var bank = Bank(_places.EventBank);
            return bank.IsEmpty ? -1 : Framework.ReadGame(bank, Framework.CurrentEvent);
        }

        int EventVariables(int op, int variable, int operand, nint unused, byte fifth)
        {
            // (1.24.0) The battle won event about to play (the event playing given it as a battle with no rules of its
            // own is won): at a mod's dungeon, the won flag of the floor whose battle it was, before it is set.
            if (op == Framework.AddCommand && variable == Framework.CurrentEvent && _entries != null
                && (operand == Framework.BattleWonEvent || _framework.IsFirstWon(operand)))
                FloorWon(operand);
            // A command whose variable is the story's progress writes it (the game's own reading of a
            // variable gives it as the operand, into variable 0): left out while a quest's event plays.
            if (variable == Framework.StoryProgress)
            {
                try
                {
                    string? kept = _framework.VariableKept(CurrentEvent(), variable);
                    if (kept != null)
                    {
                        SayOnce(kept);
                        return 0;
                    }
                }
                catch (Exception e)
                {
                    SayOnce($"the story's progress wasn't looked after ({e.GetType().Name}: {e.Message}).");
                }
            }
            if (Framework.IsFlag(variable) || Framework.IsFlag(operand))
            {
                // (1.15.0) A rumor read sets its flag before any flag is read; (1.29.0) as the tavern's agent marks
                // it (RumorAgent): here its save bytes made its own (SettleRumorBytes).
                if (_rumors)
                    SettleRumorBytes(_places.EventBank);
                var command = Flag(_places.EventBank, op, variable, operand);
                if (command == null)
                    return 0;
                (op, variable, operand) = command.Value;
            }
            return _eventVariables!.OriginalFunction(op, variable, operand, unused, fifth);
        }

        /// <summary>(1.2.4) Whether a travel passes through the place whose chains the world map runs:
        /// a travel under way (its flags' bit 0) with roads still to go (fewer taken than it has).
        /// False where the travel's state wasn't found: a waiting start then stops a passing travel,
        /// as the game's own events do.</summary>
        bool PassingThrough()
            => _places.Passing && Framework.Passing(*(_base + _places.TravelFlags), *(int*)(_base + _places.TravelDone),
                                                    *(int*)(_base + _places.TravelLegs));

        int WorldVariables(int op, int variable, int operand)
        {
            // (1.2.4) The framework's passing-through variable, read by a start that waits until its
            // place is chosen: never the game's function's (it has no variable past 1,023).
            if (variable == Framework.PassingThrough || operand == Framework.PassingThrough)
            {
                try
                {
                    bool through = PassingThrough();
                    var passing = Framework.PassingCommand(op, variable, operand, through);
                    if (passing == null)
                        return 0;
                    if (through && passing.Value != (op, variable, operand))    // read while passing
                        SayOnce(Framework.PassingGoesOn);
                    (op, variable, operand) = passing.Value;
                }
                catch (Exception e)
                {
                    SayOnce($"a travel passing through wasn't looked for ({e.GetType().Name}: {e.Message}).");
                    return 0;
                }
            }
            if (Framework.IsFlag(variable) || Framework.IsFlag(operand))
            {
                // (1.15.0) A rumor read sets its flag before any flag is read; (1.29.0) as the tavern's agent marks
                // it (RumorAgent): here its save bytes made its own (SettleRumorBytes).
                if (_rumors)
                    SettleRumorBytes(_places.WorldBank);
                var command = Flag(_places.WorldBank, op, variable, operand);
                if (command == null)
                    return 0;
                (op, variable, operand) = command.Value;
            }
            return _worldVariables!.OriginalFunction(op, variable, operand);
        }

        // --- (1.15.0) the quests' tavern rumors ---------------------------------------------

        /// <summary>The taverns' test of a rumor told (its key, a place): for a quest's rumor, its towns and its When
        /// (Framework.RumorTold); for any other, the game's own test.</summary>
        byte RumorTest(int key, int place)
        {
            // (1.29.0) Each of the taverns' walks over the rumors starts at key 0: the quests' rumors' save bytes made
            // theirs first (a save loaded may hold another start's keys), before the game reads any of them.
            if (key == 0)
                SettleRumorBytes(_places.WorldBank);
            try
            {
                bool? told = Framework.RumorTold(_framework.RumorAt(key), place, WorldValue, InParty);
                if (told != null)
                    return (byte)(told.Value ? 1 : 0);
            }
            catch (Exception e)
            {
                SayOnce($"a side quest's rumor wasn't told ({e.GetType().Name}: {e.Message}).");
                if (_framework.RumorAt(key) != null)
                    return 0;
            }
            // (1.18.0) The game's own rumors at a mod's town's tavern: as at a place of no town (only those told in
            // every tavern), whatever the place's number shifted as the game shifts it would say.
            if (place >= Destinations.FirstNumber)
                return _rumorTest!.OriginalFunction(key, Framework.NoTownPlace);
            return _rumorTest!.OriginalFunction(key, place);
        }

        // --- (1.18.0) the mods' towns' menus --------------------------------------------------------

        /// <summary>The Outfitter's stock: at a mod's town with a menu, its own items, listed by the game's own code
        /// as a town's (the list's category, each once the story reaches the point the game's own shops start selling
        /// it, checked against the unit as asked, sorted as asked): its items given the borrowed town's bit in the
        /// shops' masks for the call (Framework.BorrowMasks), then every byte as it was. Any other town, the game's
        /// own.</summary>
        int Stock(short unit, short town, short category, nint list, int mode, byte sort)
        {
            if (!_framework.MenuTowns.TryGetValue(town, out var menuTown))
                return _stock!.OriginalFunction(unit, town, category, list, mode, sort);
            var masks = new Span<byte>(_base + _places.ShopMasks, 2 * Framework.ShopItems);
            Span<byte> kept = stackalloc byte[Framework.ShopItems];
            bool borrowed = false;
            // (1.26.0) Its own items after the game's: the game's list made unsorted, theirs added, then sorted as asked.
            var items = Items;
            bool own = items != null && menuTown.OwnItems.Count > 0 && _stockSort != 0;
            try
            {
                Framework.BorrowMasks(masks, menuTown.Menu.Shop, kept);
                borrowed = true;
                // (1.27.0) The borrowed town's call goes past the mods' items' own hook for the game's towns
                // (ItemHooks.Stock), whichever of the two hooks wraps the other (set back in `finally` too).
                Borrowing = true;
                int listed = _stock!.OriginalFunction(unit, Framework.BorrowedTown, category, list, mode,
                                                      own ? (byte)0 : sort);
                Borrowing = false;
                if (own)
                {
                    listed += items!.Append(menuTown.OwnItems, category, list, listed, StoryPoint(),
                                            mode == 0 ? null : id => Equips(unit, id), mode);
                    if (sort != 0)
                        ((delegate* unmanaged<int, nint, void>)(_base + _stockSort))(StockSortKind, list);
                }
                return listed;
            }
            catch (Exception e)
            {
                SayOnce($"a mod's town's Outfitter sells nothing ({e.GetType().Name}: {e.Message}).");
                *(short*)list = -1;
                return 0;
            }
            finally
            {
                Borrowing = false;
                if (borrowed)
                    Framework.GiveBackMasks(masks, kept);
            }
        }

        /// <summary>(1.26.0) The mods' items, when armed (Mod.PlanItems): a mod's town's Outfitter lists its own after
        /// the game's.</summary>
        public ItemHooks? Items { get; set; }

        /// <summary>(1.27.0) Set while a mod's town's Outfitter asks the game's own stock through the borrowed town:
        /// the mods' items' hook for the game's towns (ItemHooks.Stock) then adds nothing.</summary>
        [ThreadStatic] public static bool Borrowing;

        /// <summary>(1.26.0) What the stock function calls, read from its own code (StockSort, StockEquips, StockUnits:
        /// where each is in it, checked by its bytes): the list's sort (its kind 6), the check of an item against the
        /// unit, the units' table. 0 when not found (a mod's town's own items then aren't sold, said).</summary>
        int _stockSort, _stockEquips, _stockUnits;
        public const int StockSortAt = Places.StockSortAt, StockEquipsAt = Places.StockEquipsAt,
                         StockUnitsAt = Places.StockUnitsAt, StockSortKind = 6;

        /// <summary>(1.27.0) Read as the mods' items' hook for the game's towns reads them (Places.StockCalls).</summary>
        void FindStockCalls(ReadOnlySpan<byte> code, int stock)
            => (_stockSort, _stockEquips, _stockUnits) = Places.StockCalls(code, stock);

        /// <summary>(1.26.0) The story's point the shops sell from (variable 0x6F, one of the first 128, 32 bits each, as
        /// the stock reads it through the world map's variables).</summary>
        int StoryPoint()
        {
            var bank = Bank(_places.WorldBank);
            return bank.IsEmpty ? 0 : BinaryPrimitives.ReadInt32LittleEndian(bank.Slice(StoryPointVariable * 4, 4));
        }

        public const int StoryPointVariable = 0x6F;

        /// <summary>(1.26.0) The stock's check of an item against the unit (-1: it can't), as the game's own loop asks it
        /// (0x2886D0: the item, the unit's + 0x24, the unit's + 0x73).</summary>
        int Equips(short unit, int item)
        {
            nint u = *(nint*)(_base + _stockUnits + 8 * unit);
            if (u == 0)
                return -1;
            return ((delegate* unmanaged<ushort, ushort, nint, int>)(_base + _stockEquips))((ushort)item,
                                                                                         *(ushort*)(u + 0x24), u + 0x73);
        }

        /// <summary>(1.29.0) The quests' rumors' save bytes made theirs (Framework.SettleRumors: each rumor's mark while
        /// unread, read as its flag says), their keys being given as the game starts; no flag set here (the tavern's
        /// agent sets a rumor's as it is read, RumorAgent).</summary>
        void SettleRumorBytes(int pointer)
        {
            try
            {
                var bank = Bank(pointer);
                if (bank.IsEmpty)
                    return;
                var bytes = new Span<byte>(_base + _places.RumorsRead, 2 * _places.RumorKeys);
                if (_framework.SettleRumors(bank, bytes) > 0)
                    SayOnce("the side quests' rumors are read as the save loaded says (their keys given as the game "
                            + "started).");
            }
            catch (Exception e)
            {
                SayOnce($"a side quest's rumor read wasn't kept ({e.GetType().Name}: {e.Message}).");
            }
        }

        /// <summary>(1.29.0) The tavern's agent: the game's own, then for action 0 (the rumor of `key` marked read) a
        /// quest's rumor's flag set, said, the save marked.</summary>
        nint RumorAgent(nint screen, nint state, int action, int key)
        {
            nint result = _rumorAgent!.OriginalFunction(screen, state, action, key);
            if (action != 0)
                return result;
            try
            {
                var bank = Bank(_places.WorldBank);
                if (bank.IsEmpty)
                    bank = Bank(_places.EventBank);
                if (bank.IsEmpty)
                    return result;
                string? said = _framework.RumorReadNow(bank, key);
                if (said != null)
                {
                    _say(said);
                    Framework.Mark(bank, _framework.NumbersId);
                }
            }
            catch (Exception e)
            {
                SayOnce($"a side quest's rumor read wasn't kept ({e.GetType().Name}: {e.Message}).");
            }
            return result;
        }

        // --- the game's progress ----------------------------------------------

        /// <summary>The game's progress set: left out when it is a quest's script's (instruction E9
        /// of a story scene copied into a quest) while a quest's event plays, else the game's own
        /// function sets it.</summary>
        void Progress(nint progress, int track, int value)
        {
            try
            {
                string? kept = _framework.ProgressKept(CurrentEvent(), track, value);
                if (kept != null)
                {
                    SayOnce(kept);
                    return;
                }
            }
            catch (Exception e)
            {
                SayOnce($"the game's progress wasn't looked after ({e.GetType().Name}: {e.Message}).");
            }
            _progress!.OriginalFunction(progress, track, value);
        }

        // --- the world map's travel -------------------------------------------

        /// <summary>Asked by the travel check's stand-in when the game would stop a travel from where
        /// an event waits: one of the quests' events lets it go on (the event plays when you come
        /// back), any other stops it, as the game's own check answered (1).</summary>
        byte TravelStopped()
        {
            try
            {
                string? freed = _framework.TravelFreed(*(int*)(_base + _places.PendingEvent));
                if (freed != null)
                {
                    SayOnce(freed);
                    return 0;
                }
            }
            catch (Exception e)
            {
                SayOnce($"the world map's travel wasn't looked after ({e.GetType().Name}: {e.Message}).");
            }
            return 1;
        }

        // --- the battles --------------------------------------------------------

        /// <summary>A battle's units as it loads: the game's own, but for a quest's battle (its
        /// number one the framework gave), whose units the game is handed instead. The game's
        /// function runs first, so a battle whose file is still being read waits as it did.</summary>
        /// <summary>(2.0.0) Which quest's own battle's unit a battle file's entry is (Framework.EntryOf over the units
        /// the helper hands the game), for the battles' hooks (BattleHooks.QuestEntry).</summary>
        public (int Battle, int Slot)? EntryOf(nint entry) => Framework.EntryOf(_units, entry);

        nint Encounter()
        {
            nint units = _encounter!.OriginalFunction();
            try
            {
                if (units != 0)
                {
                    int battle = *(int*)(_base + _places.EncounterNumber);
                    if (_units.TryGetValue(battle, out nint own))
                    {
                        _say($"{_framework.BattleNameOf(battle)} fights (battle {battle}).");
                        return own;
                    }
                }
            }
            catch (Exception e)
            {
                SayOnce($"a side quest's battle wasn't given its units ({e.GetType().Name}: {e.Message}).");
            }
            return units;
        }

        /// <summary>(1.33.0, Zodi's choice of 5 November: "As a renamed unit") A battle's unit made by the game from its
        /// battle file's entry; one of a quest battle's (its entry among the units the helper hands the game), not from
        /// the party, with an own name, given it where the game keeps a renamed unit's (+ 0x14C): the game shows it in
        /// place of the generic's name it gave the unit, and copies it as the unit joins the party. Said once a name.
        /// </summary>
        int UnitMade(nint unit, nint entry, int number, int mode, nint row)
        {
            int answer = _unitMade!.OriginalFunction(unit, entry, number, mode, row);
            try
            {
                if (answer != -1 && unit != 0)
                {
                    var named = Framework.NameUnit(new Span<byte>((void*)unit, Framework.UnitOwnName + Framework.OwnNameSize),
                                                   entry, _units, _framework.OwnNames);
                    if (named != null)
                        SayOnce(Framework.NamedLine(_framework.BattleNameOf(named.Value.Battle), named.Value.Slot,
                                                    named.Value.Name));
                }
            }
            catch (Exception e)
            {
                SayOnce($"a side quest's unit wasn't given its own name ({e.GetType().Name}: {e.Message}).");
            }
            return answer;
        }

        // --- (1.21.0) a mod's dungeon ------------------------------------------------------------

        /// <summary>A place's settlement menu's entries: at a mod's dungeon its floors listed now (Framework.OpenFloors,
        /// their quest flags as the world map reads them), each FloorEntry plus its place in the dungeon's floors;
        /// elsewhere the game's own.</summary>
        int Entries(int place, nint entries)
        {
            // (1.23.0) A dungeon's list's looks (the Deep's own back at the Deep, a mod's dungeon's its own).
            try
            {
                var dressed = _looks?.Dress(place);
                if (dressed != null)
                    SayOnce($"{dressed.Who}'s list shows its own name and art"
                            + (Framework.HasAbout(dressed) ? ", and its About page its description." : "; it has no About page."));
            }
            catch (Exception e)
            {
                SayOnce($"a dungeon's list wasn't given its looks ({e.GetType().Name}: {e.Message}).");
            }
            try
            {
                if (_framework.Dungeons.TryGetValue(place, out var dungeon))
                {
                    var open = OpenFloors(dungeon);
                    for (int n = 0; n < open.Count; n++)
                        *(int*)(entries + 4 * n) = Framework.FloorEntry + open[n];
                    SayOnce($"{dungeon.Who} lists {open.Count} floor{(open.Count == 1 ? "" : "s")}.");
                    return open.Count;
                }
            }
            catch (Exception e)
            {
                SayOnce($"a mod's dungeon's floors weren't listed ({e.GetType().Name}: {e.Message}).");
                return 0;
            }
            return _entries!.OriginalFunction(place, entries);
        }

        /// <summary>(1.23.0) The UI's text: at a mod's dungeon its list's title, Exit and About its own (DungeonLooks),
        /// else the game's.</summary>
        nint UiText(int number)
        {
            try
            {
                nint own = _looks!.Text(number, _gameText ??= n => _uiText!.OriginalFunction(n));
                if (own != 0)
                    return own;
            }
            catch (Exception e)
            {
                SayOnce($"a mod's dungeon's list's words weren't given ({e.GetType().Name}: {e.Message}).");
            }
            return _uiText!.OriginalFunction(number);
        }

        /// <summary>(1.23.0) A row by two keys: the guide's page of the About key at a mod's dungeon its own, else the
        /// game's.</summary>
        nint TwoKeyRow(int sheet, int key, int key2)
        {
            try
            {
                nint own = _looks!.Page(sheet, key, key2, d => SayOnce($"{d.Who}'s About page opens."));
                if (own != 0)
                    return own;
            }
            catch (Exception e)
            {
                SayOnce($"a mod's dungeon's About page wasn't given ({e.GetType().Name}: {e.Message}).");
            }
            return _twoKeyRow!.OriginalFunction(sheet, key, key2);
        }

        /// <summary>(1.23.0) A button guide shown: at a mod's dungeon without an About page, the Deep's list's About row
        /// not shown.</summary>
        void GuideShow(nint unused, int guide, int rows)
        {
            int shown = rows;
            try
            {
                shown = _looks!.Rows(guide, rows);
            }
            catch (Exception e)
            {
                SayOnce($"a mod's dungeon's list's About prompt wasn't hidden ({e.GetType().Name}: {e.Message}).");
            }
            _guideShow!.OriginalFunction(unused, guide, shown);
        }

        /// <summary>(1.23.0) The About key: at a mod's dungeon without an About page, nothing opens.</summary>
        void About()
        {
            try
            {
                if (!_looks!.AboutOpens())
                    return;
            }
            catch (Exception e)
            {
                SayOnce($"a mod's dungeon's About key wasn't looked after ({e.GetType().Name}: {e.Message}).");
            }
            _about!.OriginalFunction();
        }

        /// <summary>(1.24.0) The battle won event about to play (Zodi, 2 November: "after they defeat all enemies the
        /// next floor becomes available"; his choice "Win once"). The game's turn check gives the event playing
        /// (variable 0x27) the battle won event once every enemy is beaten in a battle with no rules of its own
        /// (0x238A29: a random battle, a floor's among them; a battle fled, or lost, never), through the events'
        /// variable function (0x233368: cleared, then 0x192 added). Where Ramza stands a mod's dungeon whose floor
        /// chosen (variable 92) has the battle fought (variable 50) and a floor waiting for it to be won
        /// (Framework.WonFloor): its won flag set (never while a scene is replayed), the save marked with the numbers
        /// as a quest's flag marks it, and said. All of it in the game's variables, so a battle saved and loaded
        /// before it is won counts too. (1.25.0) A quest's battle played at the floor in place of its own (a start
        /// waiting there), its won event given the event playing by its rules: that floor won too
        /// (Framework.FirstWonFloor). (1.25.1) Its rules give it twice in one battle (the turn check runs them to see
        /// what would play, then to play it): one win, "won again" said only in a later battle
        /// (Framework.FloorWins, a battle being from its floor chosen).</summary>
        void FloorWon(int won)
        {
            try
            {
                if (!_framework.Dungeons.TryGetValue(*(int*)(_base + _places.CurrentPlace), out var dungeon))
                    return;
                var bank = Bank(_places.EventBank);
                if (bank.IsEmpty)
                    return;
                int index = Framework.WorldValue(bank, Framework.FloorVariable);
                // (1.25.0) Or a start's battle played in place of the floor's, its won event given (his "Yes, it
                // counts"): the floor won as well.
                var floor = won == Framework.BattleWonEvent
                    ? Framework.WonFloor(dungeon, index, Framework.WorldValue(bank, Framework.CurrentBattle))
                    : Framework.FirstWonFloor(dungeon, index, won);
                if (floor == null || Framework.ReadGame(bank, Framework.ReplayVariable) != 0)
                    return;
                // (1.25.1) Its win given twice in one battle (a battle with rules of its own: the turn check runs them
                // to see what would play, then to play it) is one win: "won again" only in a later battle.
                bool first = _floorWins.First(dungeon.Number, floor.Index);
                if (Framework.ReadFlag(bank, floor.WonFlag) != 0)
                {
                    if (first)
                        SayOnce($"{dungeon.Who}'s floor {floor.Name} is won again.");
                    return;
                }
                Framework.WriteFlag(bank, floor.WonFlag, 1);
                Framework.Mark(bank, _framework.NumbersId);
                _say($"{dungeon.Who}'s floor {floor.Name} is won: {floor.WonLists} is listed from now on (flag "
                     + $"{floor.WonFlag}).");
            }
            catch (Exception e)
            {
                SayOnce($"a mod's dungeon's floor won wasn't kept ({e.GetType().Name}: {e.Message}).");
            }
        }

        /// <summary>A dungeon's floors listed now, each its place in the dungeon's floors.</summary>
        List<int> OpenFloors(Framework.DungeonPlan dungeon)
        {
            var bank = Bank(_places.WorldBank);
            var set = new Dictionary<int, int>();
            foreach (var floor in dungeon.Floors)
                if (floor.Flag >= 0)
                    set[floor.Flag] = bank.IsEmpty ? 0 : Framework.ReadFlag(bank, floor.Flag);
            return Framework.OpenFloors(dungeon, flag => set.TryGetValue(flag, out int value) ? value : 0);
        }

        /// <summary>A mod's dungeon's floor chosen (the game has set variable FloorVariable to its place in the
        /// dungeon's floors): one of its battles the story has reached picked evenly (Framework.FloorPick) and kept
        /// where the game's roll keeps its own (its squad, its battle, its map), 1; then the native code runs the random
        /// battle's setup, as a battle ground's battle answered yes. 0: none (the game says there is nothing).
        /// (1.25.0) First, a quest's start waiting at the floor whose conditions hold (Framework.FirstHolding, as the
        /// world map runs a place's): its event loaded where a place's chains load theirs, to leave at once, 2; then
        /// the native code starts it as a place starts the event its chains loaded.</summary>
        int Floor(int place)
        {
            try
            {
                if (!_framework.Dungeons.TryGetValue(place, out var dungeon))
                    return 0;
                // (1.25.1) A battle of its own begins here: its floor's win is one win in it (Framework.FloorWins).
                _floorWins.Chosen();
                int index = WorldValue(Framework.FloorVariable);
                var floor = dungeon.Floors.Find(f => f.Index == index);
                if (floor == null || !OpenFloors(dungeon).Contains(index))
                {
                    SayOnce($"{dungeon.Who}'s floor {index} isn't one of its floors listed.");
                    return 0;
                }
                if (floor.Firsts.Count > 0 && _places.FloorStarts)
                {
                    var first = Framework.FirstHolding(floor, WorldValue, InParty);
                    // The world map's start of an event hides the last command's sprite: the place's, under the menu
                    // just closed (none queued: the floor's battle instead, said).
                    if (first != null && *(int*)(_base + _places.QueueCount) <= 0)
                        SayOnce($"{dungeon.Who}'s floor {floor.Name} didn't play {first.Who}'s {first.Name}: the world "
                                + "map had no command queued.");
                    else if (first != null)
                    {
                        *(int*)(_base + _places.LoadedEvent) = first.Event;
                        *(int*)(_base + _places.LoadedKind) = Places.InstantTransition;
                        _say($"{dungeon.Who}'s floor {floor.Name} plays {first.Who}'s {first.Name} in place of its "
                             + $"battle (event {first.Event}).");
                        return 2;
                    }
                }
                Framework.GroundBattle? picked;
                lock (_lock)
                    picked = Framework.FloorPick(floor, WorldValue(Framework.StoryProgress), n => _random.Next(n));
                if (picked == null)
                {
                    SayOnce($"{dungeon.Who}'s floor {floor.Name} has no battle the story has reached.");
                    return 0;
                }
                *(int*)(_base + _places.RandomSquad) = picked.Squad;
                *(int*)(_base + _places.RandomBattle) = picked.Battle;
                *(int*)(_base + _places.RandomMap) = picked.Map;
                _say($"{dungeon.Who}'s floor {floor.Name} starts its battle {picked.Name} (battle {picked.Battle}, map "
                     + $"{picked.Map}).");
                return 1;
            }
            catch (Exception e)
            {
                SayOnce($"a mod's dungeon's floor wasn't started ({e.GetType().Name}: {e.Message}).");
                return 0;
            }
        }

        /// <summary>The Deep's list's read of a floor's row at a mod's dungeon: the row of the floor at `key` of those
        /// listed now; 0 for any other (the game's row).</summary>
        nint Row(int place, int key)
        {
            try
            {
                if (_framework.Dungeons.TryGetValue(place, out var dungeon))
                {
                    var open = OpenFloors(dungeon);
                    if (key >= 0 && key < open.Count && _floorRows.TryGetValue((place, open[key]), out nint row))
                        return row;
                }
            }
            catch (Exception e)
            {
                SayOnce($"a mod's dungeon's floor's words weren't given ({e.GetType().Name}: {e.Message}).");
            }
            return 0;
        }

        // --- (1.17.0) a mod's battle ground's own random battles --------------------------

        /// <summary>A mod's battle ground's random battle, as Ramza arrives there (`forced` 0) or as the battle ground he
        /// stands on is chosen: one of its battles the story has reached (Framework.GroundPick), kept where the game's
        /// roll keeps its choice (its squad, its battle, its map), which the game then fights as its own random battle
        /// (the encounter check, then the random battle's setup: its variables and the next map). 0, no battle.</summary>
        int GroundRoll(int place, int road, byte forced)
        {
            try
            {
                if (!_framework.Grounds.TryGetValue(place, out var ground))
                    return 0;
                int progress = WorldValue(Framework.StoryProgress);
                Framework.GroundBattle? picked;
                lock (_lock)
                    picked = Framework.GroundPick(ground, progress, forced != 0, n => _random.Next(n));
                if (picked == null)
                    return 0;
                *(int*)(_base + _places.RandomSquad) = picked.Squad;
                *(int*)(_base + _places.RandomBattle) = picked.Battle;
                *(int*)(_base + _places.RandomMap) = picked.Map;
                // Picked: the game goes on with it as with its own (its deploy prompt, which may be answered no).
                _say($"{ground.Who}'s random battle {picked.Name} is picked (battle {picked.Battle}, map {picked.Map}).");
                return 1;
            }
            catch (Exception e)
            {
                SayOnce($"a battle ground's random battle wasn't started ({e.GetType().Name}: {e.Message}).");
                return 0;
            }
        }

        // --- (1.2.5) the quests' markers -------------------------------------------

        /// <summary>A variable as the world map reads it, from the variables its own function reads.</summary>
        int WorldValue(int variable)
        {
            var bank = Bank(_places.WorldBank);
            return bank.IsEmpty ? 0 : Framework.WorldValue(bank, variable);
        }

        /// <summary>(1.31.0) A quest's reward, its flag set (never while a scene is replayed: the flag isn't set then):
        /// its gil added to the war funds by the game's own add (Places.WarFundsAdd, which stops them at 99,999,999),
        /// its items put in the bag by the game's own giving of an event's item (Places.ItemGive: 99 of an item at the
        /// most, the rest sold), a mod's own item through its room (1.26.0); said.</summary>
        void GiveReward(Framework.RewardPlan reward)
        {
            if (!_places.Rewards)
            {
                SayOnce($"{reward.Who}'s reward isn't given: {string.Join(", ", _places.MissingForRewards)} wasn't found.");
                return;
            }
            if (reward.Gil > 0)
                ((delegate* unmanaged<int, long>)(_base + _places.WarFundsAdd))(reward.Gil);
            foreach (var (number, count, _) in reward.Items)
                ((delegate* unmanaged<nint, short, nint, int, void>)(_base + _places.ItemGive))(0, (short)number, 0,
                                                                                               count);
            _say($"{reward.Who} gives its reward: {Framework.RewardWords(reward)}.");
        }

        /// <summary>(1.30.0) The identity of the Ramza in the party (Framework.RamzaOf over the party's units), or 0 when
        /// none is or the party's units weren't found.</summary>
        int PartyRamza()
        {
            if (_places.Party < 0)
                return 0;
            var units = new ReadOnlySpan<byte>(_base + _places.Party, Framework.PartyUnits * Framework.UnitBytes);
            return Framework.RamzaOf(units);
        }

        /// <summary>The world map's test of a character in the party, over the party's units.</summary>
        bool InParty(int character)
        {
            var units = new ReadOnlySpan<byte>(_base + _places.Party, Framework.PartyUnits * Framework.UnitBytes);
            nint mode = *(nint*)(_base + _places.PartyMode);
            return Framework.HasCharacter(units, character, mode == 0 || *(int*)(mode + 8) != 0);
        }

        /// <summary>The world map screen shows a place: Marker.Show, with the game's own function, the
        /// color of a quest with a Marker waiting there, and what to say; (1.8.0) then the mods' own places'
        /// markers (Marker.ShowMods), which the screen never shows itself.</summary>
        void MarkerState(nint screen, nint state, int place)
        {
            if (_marker == null)
                _markerState!.OriginalFunction(screen, state, place);
            else
            {
                _marker.Show(screen, state, place, MarkerColor,
                             _show ??= new Marker.ShowFunction(_markerState!.OriginalFunction.Invoke), SayOnce);
                if (_modMarked.Count > 0)
                    _marker.ShowMods(screen, _modMarked, MarkerColor, SayOnce);
            }
            // (1.20.0) And the mods' towns darkened once a quest's flag is set, as the game's own places are shown.
            ModDarkened(screen);
        }

        /// <summary>(1.20.0) Each place's copy darkened or not (PlaceHooks.Darken, set once the quests are planned:
        /// the screen, the place, darkened or not; whether its copy was found).</summary>
        public Func<nint, MapPlace, bool, bool>? Darken { get; set; }

        /// <summary>(1.20.0) Whether a mod's town is darkened once a quest's flag is set.</summary>
        public bool DarkensModPlaces => _framework.DarkPlaces.Count > 0;

        /// <summary>(1.34.0) Whether a mod's town is darkened now: its Darkened flag set, as the world map reads it (the
        /// mods' roads grayed with it: PlaceHooks.Darkened).</summary>
        public bool IsDarkened(MapPlace place)
        {
            var bank = Bank(_places.WorldBank);
            if (bank.IsEmpty)
                return false;
            foreach (var d in _framework.DarkPlaces)
                if (d.Place == place)
                    return Framework.ReadFlag(bank, d.Flag) != 0;
            return false;
        }

        /// <summary>(1.20.0) The mods' towns darkened once a quest's flag is set, each darkened or not on a screen by
        /// its flag as the world map reads it (at the screen's setup, and each time it shows one of the game's
        /// places); said once when one is first darkened.</summary>
        public void ModDarkened(nint screen)
        {
            if (_framework.DarkPlaces.Count == 0 || Darken == null)
                return;
            var bank = Bank(_places.WorldBank);
            if (bank.IsEmpty)
                return;
            foreach (var d in _framework.DarkPlaces)
            {
                bool dark = Framework.ReadFlag(bank, d.Flag) != 0;
                if (Darken(screen, d.Place, dark) && dark)
                    SayOnce($"{d.Who} is darkened: {_framework.FlagNameOf(d.Flag)} is 1 (flag {d.Flag}).");
            }
        }

        /// <summary>(1.8.0) Whether a quest's marker may show at one of the mods' own places.</summary>
        public bool MarksModPlaces => _marker != null && _modMarked.Count > 0;

        /// <summary>(1.8.0) The mods' own places' markers shown on a screen whose pieces were just set up (the places'
        /// hook calls this once their pieces are added: a screen set up shows them without waiting for the game to show
        /// one of its own places).</summary>
        public void ModMarkers(nint screen)
        {
            if (MarksModPlaces)
                _marker!.ShowMods(screen, _modMarked, MarkerColor, SayOnce);
        }

        /// <summary>The color (bytes R, G, B, A) of the first quest with a Marker one of whose starts
        /// waits at a place, its conditions holding as the world map tests them; null for none.</summary>
        uint? MarkerColor(int place)
        {
            // (1.15.0) A rumor read, its flag set before a start waiting for it is tested (1.29.0: by the tavern's
            // agent; here its save bytes made its own).
            if (_rumors)
                SettleRumorBytes(_places.WorldBank);
            var marked = _framework.MarkedAt(place, WorldValue, InParty);
            if (marked == null)
                return null;
            SayOnce($"{marked.Name} ({marked.ModName})'s marker shows at place {place}.");
            return QuestFile.Rgba(marked.Marker);
        }
    }
}
