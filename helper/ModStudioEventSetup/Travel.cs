// Mod Studio Framework: (1.5.0) travel along a mod's own roads between
// the game's places. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi, 26 October, after his test 24: step 2 of his "real new places, built
// in steps", its second part: travel along a mod's road. Its first half: a
// road between two of the game's places (RoadFile.cs; its Walk the points
// Ramza walks), travelled as the game's own. Read from his program (dev/
// research/sidequests/roads.py) and the game's tables, the game keeps every
// road twice:
// - the program's own (the PlayStation's): a table of 51 records (a point
//   count, its two places, its length, its points), which the path search
//   (Places.PathSearch: the fewest roads, then the shortest, over the roads
//   shown, variable 556 + the road) loops over to 51, and which the walk's
//   setup of a road (Places.WalkSetup) and the travel's read of its last
//   road (Places.LastRoad) index by a road's number, a byte of the travel's
//   path (its 0xFF; the other way its 0x100). The remaster's own three roads
//   (48 to 50) have two or five points at 0, 0: while the world map screen
//   is there, the travel waits for the screen's walk, not the points;
// - the remaster's, in two tables: Route (sheet 0x61: a road's name, its
//   two places at + 8 and + 0xC), which the screen reads for where a road
//   leads, and MapRouteTable (sheet 0x62: its points by road and number,
//   x at + 4, y at + 8), along which it walks Ramza's marker, from the
//   point after his place to the place he goes to (its Town middle).
// So a mod's road gets a number past the game's, from 51 (Plan: in Reloaded-
// II's order, never a modder's choice; 254 the last, 255 kept out), and:
// - a record of the remaster's kind (Record: two points at 0, 0, its length
//   the path search's cost, as the game's: its walk's length on the
//   PlayStation's map, x 7.05 and y 5.75 times smaller, over 1.07);
// - the program's table copied with the mods' records after the game's 51,
//   in memory the helper owns within 2 GB of the program (Arm), and the
//   three readers given it; the path search's loop to the mods' last road
//   (cmp bl, n; jb, as the road's number is a byte); its read of whether a
//   road is shown through native code (Stub) that passes the question, with
//   where the search stands and where it goes, to the helper (WaysInGame):
//   a game's road shown as the game's own read says, a mod's when both its
//   places are, by the game's own test (Places.PlaceShown), and only once
//   both tables have the roads' rows (the ready byte, set by TravelTables
//   when the second gets them: until then no mod's road is on any path);
//   and the search kept to the ways it would end with (Ways: its work grows
//   very fast with roads between places), so it ends with the same way;
// - a Route row and its MapRouteTable rows (RouteRow, PointRows: its Walk),
//   added to the tables as the game reads them (TravelTables, through
//   PlaceHooks' hook of the tables' setup).
// The patches are made before the game runs, each checked against the bytes
// it replaces; a game that isn't laid out so gets none, said, and the roads
// are drawn only. The game's own travel stays as it was: the table's first
// 51 are the game's, the loop goes over them as before, and the search ends
// with the way the game's rules end it with. helper/Checks runs the game's
// own path search, walk setup and last road's read over the patched program
// (dev/test_side_quests.py, with unicorn).
//
// (1.6.0) Zodi, 27 October, after his test 26 ("arriving by a new road never
// starts a random battle ... that should be a feature we should implement as
// well"): the game picks a random battle by the road Ramza arrived along. Its
// roll (Places.BattleRoll: the place, the road's low byte, whether a battle
// is forced) looks for the road among the three entrances its battle ground
// has in a table of the program's (19 grounds, 24 to 42; each entrance where
// the party deploys, four tiers of the chance by the story's progress, eight
// enemy formations, the map: as the PlayStation's), and finds a mod's road
// in none. It is called as Ramza arrives (the travel step) and as the battle
// ground he stands on is chosen (a battle forced). So each mod's road
// arriving at a battle ground uses the entrance of the game's road arriving
// there from the nearest heading (Battles: over the last 100 pixels of each,
// the game's roads by their records' points), said in the log; both calls go
// to native code (RollStub) that turns a mod's road arriving at one of its
// places into that road (BattleRoads), the game's roads as they are, and on
// to the roll. Without the roll found, the roads are travelled and start no
// random battle, said.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

namespace ModStudioEventSetup
{
    /// <summary>A mod's road the game travels: the road, its number, its cost (its length as the path search
    /// counts it).</summary>
    public sealed class TravelRoad
    {
        public MapRoad Road { get; }
        public int Number { get; }
        public int Cost { get; }
        /// <summary>(1.7.0) Its places' numbers of the world map's: one of the game's as the road names it, one of the
        /// mod's own by the number it was given (Destinations.cs).</summary>
        public int From { get; }
        public int To { get; }

        public TravelRoad(MapRoad road, int number, int cost, int from = -1, int to = -1)
        {
            Road = road;
            Number = number;
            Cost = cost;
            From = from >= 0 ? from : road.FromPlace;
            To = to >= 0 ? to : road.ToPlace;
        }
    }

    /// <summary>One change to the program's code: where, the bytes it has, the bytes it gets.</summary>
    public sealed class CodePatch
    {
        public int At { get; }
        public byte[] Old { get; }
        public byte[] New { get; }
        public string What { get; }

        public CodePatch(int at, byte[] old, byte[] @new, string what)
        {
            At = at;
            Old = old;
            New = @new;
            What = what;
        }
    }

    /// <summary>The memory the helper gives the roads: its bytes as they go at `At`, and where in them the table,
    /// the records and the native code are; (1.6.0) and, when the mods' roads start random battles, the roads each
    /// arrives as at a battle ground and the native code turning one into the other for the roll (else -1).</summary>
    public sealed class TravelBlock
    {
        public ulong At { get; }
        public byte[] Bytes { get; }
        public int Table { get; }
        public int Records { get; }
        public int Code { get; }
        public int Battles { get; }
        public int RollCode { get; }

        public TravelBlock(ulong at, byte[] bytes, int table, int records, int code, int battles = -1, int rollCode = -1)
        {
            At = at;
            Bytes = bytes;
            Table = table;
            Records = records;
            Code = code;
            Battles = battles;
            RollCode = rollCode;
        }
    }

    /// <summary>(1.6.0) A mod's road arriving at a battle ground: the place, the game's road whose entrance it uses
    /// there (its random battles: where the party deploys, the enemies, how often), and that road's other place.</summary>
    public sealed class RoadBattle
    {
        public TravelRoad Road { get; }
        public int Place { get; }
        public int GameRoad { get; }
        public int From { get; }

        public RoadBattle(TravelRoad road, int place, int gameRoad, int from)
        {
            Road = road;
            Place = place;
            GameRoad = gameRoad;
            From = from;
        }
    }

    /// <summary>(1.5.0) The path search kept to the ways it would end with. The game's search (Places.PathSearch, as
    /// the PlayStation's) tries every road from where it stands, then every road from there, 16 deep, keeping the
    /// fewest roads, then the least cost, an equal one found later taken: every road between its places a mod adds
    /// makes it longer (measured over every way between the world map's places: with 10 more roads 7 times as many
    /// tries, with 20 37 times, 32 million on the worst way; dev/research/sidequests/travel.py). So its read of whether
    /// a road is shown is answered here (WaysInGame): as the game would (each road of its own by its variable, a mod's
    /// by both its places, once the tables have its rows), and, from where the search stands, only onto a way of the
    /// fewest roads and, of those, the least cost (each place's fewest roads to where the search goes, and their least
    /// cost, counted when it begins; the search's own count of roads taken and their cost so far). The way the search
    /// ends with is one of those, and every one of them is still tried in the game's order, so it ends with the same
    /// way; it only stops trying the others (travel.py: the same way, every way between the places, with the game's
    /// own search over his program; a few hundred questions a way, with 200 more roads too).</summary>
    public sealed class Ways
    {
        /// <summary>A road's places are a byte each.</summary>
        public const int PlaceCount = 256;
        readonly byte[] _from, _to, _cost;
        readonly bool[] _shown;
        readonly int[] _length = new int[PlaceCount], _costTo = new int[PlaceCount];
        readonly bool[] _done = new bool[PlaceCount];
        int _bestLength = -1, _bestCost = -1;

        /// <summary>The roads by number (the game's first, then the mods'), each its two places and its cost.</summary>
        public Ways(byte[] from, byte[] to, byte[] cost)
        {
            _from = from;
            _to = to;
            _cost = cost;
            _shown = new bool[from.Length];
            Array.Fill(_length, -1);
        }

        public int Count => _from.Length;
        public int From(int road) => _from[road];
        public int To(int road) => _to[road];
        public int Cost(int road) => _cost[road];
        /// <summary>The fewest roads from the search's start to where it goes (-1: none), and their least cost.</summary>
        public int BestLength => _bestLength;
        public int BestCost => _bestCost;
        /// <summary>A place's fewest roads to where the search goes (-1: none), and their least cost.</summary>
        public int Length(int place) => place >= 0 && place < PlaceCount ? _length[place] : -1;
        public int CostTo(int place) => place >= 0 && place < PlaceCount && _length[place] >= 0 ? _costTo[place] : -1;
        public bool Shown(int road) => road >= 0 && road < _shown.Length && _shown[road];

        /// <summary>A search begins, from `start` to `end`: the roads it may take (`shown`), each place's fewest of
        /// them to `end` and, of those, the least cost, from `end` out, the fewest and least from `start`.</summary>
        public void Prepare(int start, int end, Func<int, bool> shown)
        {
            for (int road = 0; road < _from.Length; road++)
                _shown[road] = shown(road);
            Array.Fill(_length, -1);
            Array.Fill(_costTo, 0);
            Array.Fill(_done, false);
            _bestLength = _bestCost = -1;
            if (end < 0 || end >= PlaceCount)
                return;
            _length[end] = 0;
            while (true)
            {
                int place = -1;
                for (int p = 0; p < PlaceCount; p++)
                    if (!_done[p] && _length[p] >= 0
                        && (place < 0 || _length[p] < _length[place]
                            || (_length[p] == _length[place] && _costTo[p] < _costTo[place])))
                        place = p;
                if (place < 0)
                    break;
                _done[place] = true;
                for (int road = 0; road < _from.Length; road++)
                {
                    if (!_shown[road])
                        continue;
                    int other = _from[road] == place ? _to[road] : _to[road] == place ? _from[road] : -1;
                    if (other < 0 || _done[other])
                        continue;
                    int length = _length[place] + 1, cost = _costTo[place] + _cost[road];
                    if (_length[other] < 0 || length < _length[other] || (length == _length[other] && cost < _costTo[other]))
                    {
                        _length[other] = length;
                        _costTo[other] = cost;
                    }
                }
            }
            if (start >= 0 && start < PlaceCount && _length[start] >= 0)
            {
                _bestLength = _length[start];
                _bestCost = _costTo[start];
            }
        }

        /// <summary>Whether the search may take `road` from `place`, `depth` roads along its way at `cost` so far: a
        /// road shown and, from where it stands, only onto a way of the fewest roads and the least cost; a road not
        /// from there as it is (the search passes it by itself).</summary>
        public bool Answer(int road, int place, int depth, int cost)
        {
            if (!Shown(road))
                return false;
            int other = _from[road] == place ? _to[road] : _to[road] == place ? _from[road] : -1;
            if (other < 0)
                return true;
            return _bestLength >= 0 && _length[other] >= 0 && depth + 1 + _length[other] <= _bestLength
                   && cost + _cost[road] + _costTo[other] <= _bestCost;
        }
    }

    /// <summary>(1.5.0) Ways in the running game: the path search's question answered (the block's native code jumps
    /// here with the road's variable, where the search stands, where it goes); the roads' Ways prepared as each
    /// search begins (its first question: road 0, none taken yet), the game's roads shown by the game's variables'
    /// read (556 + the road), a mod's by the game's test of its two places, once both tables have its rows (the ready
    /// byte); the search's count of roads taken and their cost read where it keeps them. Never throws into the game: a
    /// fault answers as the game would, without keeping to the ways it ends with.</summary>
    public static unsafe class WaysInGame
    {
        static Ways? _ways;
        static int* _depth, _cost;
        static byte* _ready;
        static delegate* unmanaged<int, int> _variable;
        static delegate* unmanaged<nint, int, byte> _placeShown;
        static readonly Func<int, bool> ShownNow = Shown;

        /// <summary>The roads, the search's count of roads taken and their cost, the variables' read, the test of a
        /// place shown and the ready byte; the answer's address for the native code.</summary>
        public static nint Set(Ways ways, nint depth, nint cost, nint variable, nint placeShown, nint ready)
        {
            _ways = ways;
            _depth = (int*)depth;
            _cost = (int*)cost;
            _variable = (delegate* unmanaged<int, int>)variable;
            _placeShown = (delegate* unmanaged<nint, int, byte>)placeShown;
            _ready = (byte*)ready;
            return (nint)(delegate* unmanaged<int, int, int, int>)&RoadShown;
        }

        /// <summary>A place shown: one of the game's by the game's own test, (1.7.0) a mod's place the game goes to
        /// always (the only places past 47 a mod's road has).</summary>
        static bool PlaceShown(int place) => place >= Destinations.FirstNumber || _placeShown(0, place) != 0;

        static bool Shown(int road)
        {
            if (road < Travel.GameRoads)
                return _variable(Travel.ShownFirst + road) != 0;
            return *_ready != 0 && PlaceShown(_ways!.From(road)) && PlaceShown(_ways.To(road));
        }

        [UnmanagedCallersOnly]
        static int RoadShown(int variable, int place, int end)
        {
            int road = variable - Travel.ShownFirst;
            try
            {
                if (_ways == null || road < 0 || road >= _ways.Count)
                    return 0;
                int depth = *_depth;
                if (depth == 0 && road == 0)
                    _ways.Prepare(place, end, ShownNow);
                return _ways.Answer(road, place, depth, *_cost) ? 1 : 0;
            }
            catch (Exception)
            {
                try
                {
                    return _ways != null && road >= 0 && road < _ways.Count && Shown(road) ? 1 : 0;
                }
                catch (Exception)
                {
                    return 0;
                }
            }
        }
    }

    /// <summary>(1.5.0) Route and MapRouteTable given the mods' roads' rows as the game sets each up from its file
    /// (PlaceHooks' hook of the tables' setup, Places.SheetInit: the table, its file): the file's bytes swapped for a
    /// copy with the rows (Travel.WithRows), as the side quests' tables are (Hooks.cs); the ready byte WaysInGame
    /// reads 1 only while both tables' last loads have them, so the path search never takes a road the screen has no
    /// points or place for. (1.7.0) And Town and PlaceName the mods' places' rows (Destinations.WithRows): where
    /// Ramza stands at each and its name; while a road to one of them is travelled, Town's last load having them is
    /// needed too (the screen walks him to where its row says). Never throws into the game: what it can't do is
    /// said.</summary>
    public sealed unsafe class TravelTables
    {
        /// <summary>A table's number (+ 8) and its file (+ 0x30), as the setup reads them; the file's bytes (+ 0x38)
        /// and their size (+ 0x40).</summary>
        public const int SheetNumber = 8, SheetFile = 0x30, FileBytes = 0x38, FileSize = 0x40;
        /// <summary>The largest file taken for a table.</summary>
        public const long MostTable = 64L << 20;

        readonly List<TravelRoad> _travel;
        readonly List<Destination> _destinations;
        readonly nint _ready;
        /// <summary>(1.7.0) Whether a road travelled goes to a mod's place (then Town's rows are needed).</summary>
        readonly bool _needTown;
        readonly Action<string> _say;
        readonly object _lock = new object();
        readonly HashSet<nint> _copies = new HashSet<nint>();
        readonly Dictionary<int, bool> _given = new Dictionary<int, bool>();

        public TravelTables(List<TravelRoad> travel, nint ready, Action<string> say, List<Destination>? destinations = null)
        {
            _travel = new List<TravelRoad>(travel);
            _destinations = new List<Destination>(destinations ?? new List<Destination>());
            _ready = ready;
            _say = say;
            _needTown = _travel.Exists(t => t.From >= Destinations.FirstNumber || t.To >= Destinations.FirstNumber);
        }

        static string NameOf(int number) => number switch
        {
            Travel.RouteSheet => "Route",
            Travel.PointsSheet => "MapRouteTable",
            Destinations.TownSheet => "Town",
            _ => "PlaceName",
        };

        bool Roads(int number) => number == Travel.RouteSheet || number == Travel.PointsSheet;

        /// <summary>The tables given rows: Route's and MapRouteTable's with roads to travel, (1.7.0) Town's and
        /// PlaceName's with places to go to.</summary>
        bool Wanted(int number) => Roads(number) ? _travel.Count > 0
                                   : (number == Destinations.TownSheet || number == Destinations.NameSheet)
                                     && _destinations.Count > 0;

        /// <summary>What isn't done without a table's rows.</summary>
        string Without(int number) => Roads(number) ? "the mods' roads aren't travelled"
                                      : number == Destinations.TownSheet ? "the mods' places aren't travelled to"
                                      : "the mods' places show no names";

        /// <summary>A table about to be set up from its file: Route's and MapRouteTable's given the roads' rows,
        /// (1.7.0) Town's and PlaceName's the places'; any other left as it is.</summary>
        public void Give(nint sheet, nint file)
        {
            int number = -1;
            try
            {
                if (sheet != 0)
                    number = *(int*)(sheet + SheetNumber);
                GiveRows(sheet, file, number);
            }
            catch (Exception e)
            {
                if (Wanted(number))
                {
                    _say($"{NameOf(number)}'s rows weren't added ({e.GetType().Name}: {e.Message}); {Without(number)}.");
                    Given(number, false);
                }
            }
        }

        void GiveRows(nint sheet, nint file, int number)
        {
            if (sheet == 0 || file == 0 || !Wanted(number))
                return;
            string name = NameOf(number);
            string rows = Roads(number) ? "roads' rows" : "places' rows";
            if (*(nint*)(sheet + SheetFile) != file)
            {
                _say($"{name} gets no {rows}: the table isn't laid out as in the game this was made for; "
                     + $"{Without(number)}.");
                Given(number, false);
                return;
            }
            nint bytes = *(nint*)(file + FileBytes);
            long size = *(long*)(file + FileSize);
            lock (_lock)
                if (_copies.Contains(bytes))
                    return;
            if (bytes == 0 || size <= 0 || size > MostTable)
            {
                _say($"{name} gets no {rows}: its file is {size} bytes; {Without(number)}.");
                Given(number, false);
                return;
            }
            var loaded = new ReadOnlySpan<byte>((void*)bytes, (int)size);
            string why;
            var table = Roads(number) ? Travel.WithRows(number, loaded, _travel, out why)
                                      : Destinations.WithRows(number, loaded, _destinations, out why);
            if (table == null)
            {
                _say($"{name} gets no {rows}: {why}; {Without(number)}.");
                Given(number, false);
                return;
            }
            nint copy = (nint)NativeMemory.Alloc((nuint)table.Length);
            Marshal.Copy(table, 0, copy, table.Length);
            lock (_lock)
                _copies.Add(copy);
            *(long*)(file + FileSize) = table.Length;
            *(nint*)(file + FileBytes) = copy;
            int points = 0;
            foreach (var road in _travel)
                points += road.Road.Walk.Count;
            bool one = _destinations.Count == 1;
            _say(number switch
            {
                Travel.RouteSheet => $"Route: the mods' {_travel.Count} road{(_travel.Count == 1 ? "" : "s")} added.",
                Travel.PointsSheet => $"MapRouteTable: the mods' roads' {points} points added.",
                Destinations.TownSheet => $"Town: the mods' {_destinations.Count} place{(one ? "" : "s")} added.",
                _ => $"PlaceName: the mods' {_destinations.Count} {(one ? "place's name" : "places' names")} added.",
            });
            Given(number, true);
        }

        /// <summary>A table's load, with the rows or not: the mods' roads shown to the path search only while both
        /// tables' last loads have them (a table loaded again without them takes them off every path, as the screen
        /// would walk a road it has no points of), (1.7.0) and Town's when a road goes to a mod's place.</summary>
        void Given(int number, bool with)
        {
            if (_ready == 0)
                return;
            bool both, was;
            lock (_lock)
            {
                _given[number] = with;
                both = _given.TryGetValue(Travel.RouteSheet, out bool route) && route
                       && _given.TryGetValue(Travel.PointsSheet, out bool points) && points
                       && (!_needTown || (_given.TryGetValue(Destinations.TownSheet, out bool town) && town));
                was = *(byte*)_ready != 0;
                *(byte*)_ready = (byte)(both ? 1 : 0);
            }
            string which = _needTown ? "the mods' roads" : "the mods' roads between the game's places";
            if (both && !was)
                _say($"{which} are travelled from now.");
            else if (!both && was)
                _say($"{which} aren't travelled from now: a table of theirs was loaded again without their rows.");
        }
    }

    public static unsafe class Travel
    {
        /// <summary>The game's roads (0 to 50); the last number a mod's road can have (a byte of the travel's path,
        /// 255 kept out).</summary>
        public const int GameRoads = 51, LastNumber = 254;
        /// <summary>Variable 556 + a road: the game's road shown.</summary>
        public const int ShownFirst = 0x22C;
        /// <summary>The tables' numbers: Route (a road's name and places), MapRouteTable (its points).</summary>
        public const int RouteSheet = 0x61, PointsSheet = 0x62;
        /// <summary>A record: its point count, two places, its cost (4 bytes), then its points (12 bytes each: x and
        /// y on the PlayStation's map, 0, a facing, the frames to the next).</summary>
        public const int RecordHead = 4, RecordPoint = 12, RecordPoints = 2;
        /// <summary>The PlayStation's map against the world map's picture (the game's MapRouteTable points are its
        /// roads' points so: x 7.05 times and y 5.75 times as far apart), and its roads' cost against their length
        /// there (1.07: their middle).</summary>
        public const double PsxX = 7.05, PsxY = 5.75, CostPerPsx = 1.07;
        /// <summary>A Route row: its DLCFlags, its name (from the row), its two places, three more words (from the
        /// row), then the words.</summary>
        public const int RouteRowHead = 0x1C;

        /// <summary>The mods' roads the game travels: each between two of the game's places, or (1.7.0) to one of its
        /// mod's own places the game goes to (`destinations`), with a walk, a number from 51 in their order; what
        /// can't be is said.</summary>
        public static List<TravelRoad> Plan(List<MapRoad> roads, List<string> said, List<Destination>? destinations = null)
        {
            var planned = new List<TravelRoad>();
            int next = GameRoads;
            int NumberOf(MapRoad road, string name, int place)
            {
                if (name.Length == 0)
                    return place;
                var found = destinations?.Find(d => d.Place.ModId == road.ModId && d.Place.Name == name);
                return found?.Number ?? -1;
            }
            foreach (var road in roads)
            {
                if (road.Walk.Count < 2)
                    continue;
                int from = NumberOf(road, road.FromName, road.FromPlace), to = NumberOf(road, road.ToName, road.ToPlace);
                if (from < 0 || to < 0)
                    continue;
                if (next > LastNumber)
                {
                    said.Add($"{road.Name} ({road.ModName}) isn't travelled: the world map has room for "
                             + $"{LastNumber - GameRoads + 1} roads past its own, all given.");
                    continue;
                }
                planned.Add(new TravelRoad(road, next++, Cost(road.Walk), from, to));
            }
            return planned;
        }

        /// <summary>A road's cost as the path search counts it: its walk's length on the PlayStation's map over
        /// 1.07, 1 to 255.</summary>
        public static int Cost(List<(int X, int Y)> walk)
        {
            double length = 0;
            for (int n = 1; n < walk.Count; n++)
            {
                double dx = (walk[n].X - walk[n - 1].X) / PsxX, dy = (walk[n].Y - walk[n - 1].Y) / PsxY;
                length += Math.Sqrt(dx * dx + dy * dy);
            }
            return Math.Clamp((int)Math.Round(length / CostPerPsx, MidpointRounding.AwayFromZero), 1, 255);
        }

        /// <summary>A road's record, as the remaster's own three are: two points at 0, 0 (facing 0, a frame).</summary>
        public static byte[] Record(TravelRoad road)
        {
            var record = new byte[RecordHead + RecordPoints * RecordPoint];
            record[0] = RecordPoints;
            record[1] = (byte)road.From;
            record[2] = (byte)road.To;
            record[3] = (byte)road.Cost;
            for (int n = 0; n < RecordPoints; n++)
                BinaryPrimitives.WriteInt32LittleEndian(record.AsSpan(RecordHead + n * RecordPoint + 8), 1);
            return record;
        }

        /// <summary>The name a road's Route row gives it (the game finds its own roads' pictures and animations by
        /// theirs, R_ and the name: none of the game's is this).</summary>
        public static string RouteName(int number) => $"MsqRoad{number}";

        /// <summary>A road's Route row: DLCFlags 0, its name, its two places, three empty words.</summary>
        public static byte[] RouteRow(TravelRoad road)
        {
            var name = Encoding.ASCII.GetBytes(RouteName(road.Number));
            var row = new byte[(RouteRowHead + name.Length + 2 + 3) & ~3];
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(4), RouteRowHead);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(8), road.From);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(0xC), road.To);
            int empty = RouteRowHead + name.Length + 1;
            for (int at = 0x10; at <= 0x18; at += 4)
                BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(at), empty);
            name.CopyTo(row, RouteRowHead);
            return row;
        }

        /// <summary>A road's MapRouteTable rows: its walk's points by its number and theirs (DLCFlags 0, x, y).</summary>
        public static List<NewRow> PointRows(TravelRoad road)
        {
            var rows = new List<NewRow>();
            for (int n = 0; n < road.Road.Walk.Count; n++)
            {
                var row = new byte[12];
                BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(4), road.Road.Walk[n].X);
                BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(8), road.Road.Walk[n].Y);
                rows.Add(new NewRow(new[] { road.Number, n }, row));
            }
            return rows;
        }

        // --- the tables ------------------------------------------------------------

        static int I32(ReadOnlySpan<byte> b, int at) => BinaryPrimitives.ReadInt32LittleEndian(b.Slice(at, 4));

        /// <summary>Why a loaded Route or MapRouteTable isn't one the roads' rows can go in, or "": its keys (one,
        /// two) and each row's shape as the game's (a Route row's name inside the file and its places the game's; a
        /// point on the map's picture).</summary>
        public static string ShapeProblem(int sheet, ReadOnlySpan<byte> table)
        {
            var rows = Nxd.Rows(table, out string why);
            if (rows == null)
                return why;
            int keys = sheet == RouteSheet ? 1 : 2;
            if (Nxd.Keys(table) != keys)
                return $"it isn't a table of {(keys == 1 ? "one key" : "two keys")} (byte 8: {table[8]})";
            foreach (var row in rows)
            {
                int at = row.At;
                if (sheet == RouteSheet)
                {
                    if (at + RouteRowHead > table.Length)
                        return "a row of it is cut short";
                    int name = at + I32(table, at + 4);
                    int from = I32(table, at + 8), to = I32(table, at + 0xC);
                    if (name < 0 || name >= table.Length || table.Slice(name).IndexOf((byte)0) < 0)
                        return $"its row {row.Keys[0]}'s name isn't inside it";
                    if (from < 0 || from > 47 || to < 0 || to > 47)
                        return $"its row {row.Keys[0]} doesn't join two of the world map's places ({from}, {to})";
                }
                else
                {
                    if (at + 12 > table.Length)
                        return "a row of it is cut short";
                    int x = I32(table, at + 4), y = I32(table, at + 8);
                    if (x < 0 || x > PlaceFile.MapWidth || y < 0 || y > PlaceFile.MapHeight)
                        return $"its row {row.Keys[0]}, {row.Keys[1]} isn't a point on the map's texture ({x}, {y})";
                }
            }
            return "";
        }

        /// <summary>The loaded Route or MapRouteTable with the roads' rows, or null and why.</summary>
        public static byte[]? WithRows(int sheet, ReadOnlySpan<byte> table, List<TravelRoad> roads, out string why)
        {
            why = ShapeProblem(sheet, table);
            if (why.Length > 0)
                return null;
            var rows = new List<NewRow>();
            foreach (var road in roads)
            {
                if (sheet == RouteSheet)
                    rows.Add(new NewRow(new[] { road.Number }, RouteRow(road)));
                else
                    rows.AddRange(PointRows(road));
            }
            return Nxd.WithRows(table, rows, out why);
        }

        // --- (1.6.0) random battles ------------------------------------------------------

        /// <summary>How far back along a road its heading as it arrives is taken, in pixels of the map's picture.</summary>
        public const double ArrivalReach = 100;

        /// <summary>A road's heading as it arrives: from the point ArrivalReach back along it to where it arrives (its
        /// points in order toward there, the last there; from the first when it is shorter).</summary>
        public static (double X, double Y) Heading(IReadOnlyList<(double X, double Y)> points)
        {
            var (ax, ay) = points[points.Count - 1];
            double gone = 0;
            for (int n = points.Count - 1; n > 0; n--)
            {
                double dx = points[n - 1].X - points[n].X, dy = points[n - 1].Y - points[n].Y;
                double step = Math.Sqrt(dx * dx + dy * dy);
                if (step > 0 && gone + step >= ArrivalReach)
                {
                    double part = (ArrivalReach - gone) / step;
                    return (ax - (points[n].X + dx * part), ay - (points[n].Y + dy * part));
                }
                gone += step;
            }
            return (ax - points[0].X, ay - points[0].Y);
        }

        /// <summary>Of a battle ground's entrances (each the game's road it belongs to and that road's heading as it
        /// arrives there), the road whose heading is nearest `heading` (the greatest cosine; the first of equals); -1
        /// when no heading has a length.</summary>
        public static int Entrance((double X, double Y) heading, IReadOnlyList<(int Road, (double X, double Y) Heading)> entrances)
        {
            double length = Math.Sqrt(heading.X * heading.X + heading.Y * heading.Y);
            int best = -1;
            double bestCosine = 0;
            if (length == 0)
                return -1;
            foreach (var (road, (x, y)) in entrances)
            {
                double other = Math.Sqrt(x * x + y * y);
                if (other == 0)
                    continue;
                double cosine = (heading.X * x + heading.Y * y) / (length * other);
                if (best < 0 || cosine > bestCosine)
                {
                    best = road;
                    bestCosine = cosine;
                }
            }
            return best;
        }

        /// <summary>A record's points (x and y, two bytes each, at + 4 and 12 bytes apart; `at` reads a byte) as the
        /// map's picture has them apart (x 7.05 and y 5.75 times), from its first place to its second.</summary>
        public static List<(double X, double Y)> PointsOf(ulong record, Func<ulong, byte> at)
        {
            int count = at(record);
            var points = new List<(double X, double Y)>(count);
            for (int n = 0; n < count; n++)
            {
                ulong point = record + RecordHead + (ulong)(n * RecordPoint);
                short x = (short)(at(point) | (at(point + 1) << 8)), y = (short)(at(point + 2) | (at(point + 3) << 8));
                points.Add((x * PsxX, y * PsxY));
            }
            return points;
        }

        /// <summary>Where each mod's road arriving at a battle ground (24 to 42) starts its random battles, its first
        /// place then its second: the entrance of the game's road arriving there from the nearest heading, of the
        /// ground's three in the roll's table (`table` reads its byte) whose road arrives there (the others the game
        /// never rolls: road 0, its chances 0). `records`: the game's roads' records (`at` reads a record's byte).</summary>
        public static List<RoadBattle> Battles(List<TravelRoad> roads, ulong[] records, Func<ulong, byte> at,
                                               Func<int, byte> table)
        {
            var battles = new List<RoadBattle>();
            foreach (var road in roads)
            {
                var walk = new List<(double X, double Y)>();
                foreach (var (x, y) in road.Road.Walk)
                    walk.Add((x, y));
                foreach (int place in new[] { road.From, road.To })
                {
                    int ground = place - Places.BattleGroundFirst;
                    if (ground < 0 || ground >= Places.BattleGrounds || walk.Count < 2)
                        continue;
                    var toward = new List<(double X, double Y)>(walk);
                    if (place == road.From)
                        toward.Reverse();
                    var entrances = new List<(int Road, (double X, double Y) Heading)>();
                    var others = new Dictionary<int, int>();
                    for (int k = 0; k < Places.BattleEntrances; k++)
                    {
                        int game = table(ground * Places.BattleGroundBytes + k * Places.BattleEntranceBytes);
                        if (game >= records.Length || others.ContainsKey(game))
                            continue;
                        int from = at(records[game] + 1), to = at(records[game] + 2);
                        if (from != place && to != place)
                            continue;
                        var points = PointsOf(records[game], at);
                        if (points.Count < 2)
                            continue;
                        if (from == place)
                            points.Reverse();
                        entrances.Add((game, Heading(points)));
                        others[game] = from == place ? to : from;
                    }
                    int chosen = Entrance(Heading(toward), entrances);
                    if (chosen >= 0)
                        battles.Add(new RoadBattle(road, place, chosen, others[chosen]));
                }
            }
            return battles;
        }

        /// <summary>The roads as the roll sees them, four bytes a road by its number (256): a mod's road's two
        /// places, then the road it arrives as at its first and at its second (the game's road whose entrance it
        /// uses at a battle ground, else itself, which no entrance has).</summary>
        public static byte[] BattleRoads(List<TravelRoad> roads, List<RoadBattle> battles)
        {
            var table = new byte[256 * 4];
            foreach (var road in roads)
            {
                int at = road.Number * 4;
                table[at] = (byte)road.From;
                table[at + 1] = (byte)road.To;
                table[at + 2] = table[at + 3] = (byte)road.Number;
            }
            foreach (var battle in battles)
                table[battle.Road.Number * 4 + (battle.Place == battle.Road.From ? 2 : 3)] = (byte)battle.GameRoad;
            return table;
        }

        /// <summary>The native code both calls of the roll go to (ecx the place, edx the road arrived along, r8b a
        /// battle forced): a mod's road (51 on) arriving at one of its places turned into the road it arrives as there
        /// (`battles`: BattleRoads), the game's roads as they are; then on to the roll (`roll`), which returns to the
        /// call itself. Only rax, r10 and r11 changed besides, which neither call keeps across it. (1.17.0) A mod's own
        /// place (48 on) goes instead to what `groundSlot` holds (8 bytes of the helper's: at first `.none` here, no
        /// battle; the helper's own roll of the mods' battle grounds once the side quests' hooks are made), which
        /// returns to the call itself as the roll does.</summary>
        public static byte[] RollStub(ulong battles, ulong roll, ulong groundSlot = 0)
        {
            var code = new byte[]
            {
                0x83, 0xF9, (byte)Destinations.FirstNumber,       // cmp ecx, 48
                0x73, 0x42,                                       // jae .mods: a mod's own place
                0x83, 0xFA, (byte)GameRoads,                      // cmp edx, 51
                0x72, 0x30,                                       // jb .roll: a road of the game's as it is
                0x0F, 0xB6, 0xC2,                                 // movzx eax, dl
                0x49, 0xBA, 0, 0, 0, 0, 0, 0, 0, 0,               // mov r10, the roads (at 10)
                0x4D, 0x8D, 0x14, 0x82,                           // lea r10, [r10 + rax*4]
                0x45, 0x0F, 0xB6, 0x1A,                           // movzx r11d, byte [r10]: its first place
                0x44, 0x39, 0xD9,                                 // cmp ecx, r11d
                0x75, 0x07,                                       // jne .second
                0x41, 0x0F, 0xB6, 0x52, 0x02,                     // movzx edx, byte [r10 + 2]
                0xEB, 0x0F,                                       // jmp .roll
                0x45, 0x0F, 0xB6, 0x5A, 0x01,                     // .second: movzx r11d, byte [r10 + 1]
                0x44, 0x39, 0xD9,                                 // cmp ecx, r11d
                0x75, 0x05,                                       // jne .roll: neither place, as it is
                0x41, 0x0F, 0xB6, 0x52, 0x03,                     // movzx edx, byte [r10 + 3]
                0x48, 0xB8, 0, 0, 0, 0, 0, 0, 0, 0,               // .roll: mov rax, the roll (at 60)
                0xFF, 0xE0,                                       // jmp rax
                0xCC,
                0x48, 0xB8, 0, 0, 0, 0, 0, 0, 0, 0,               // .mods (71): mov rax, the slot (at 73)
                0xFF, 0x20,                                       // jmp qword [rax]
                0x33, 0xC0,                                       // .none (83): xor eax, eax: no battle
                0xC3,                                             // ret
                0xCC,
            };
            BinaryPrimitives.WriteUInt64LittleEndian(code.AsSpan(15), battles);
            BinaryPrimitives.WriteUInt64LittleEndian(code.AsSpan(60), roll);
            BinaryPrimitives.WriteUInt64LittleEndian(code.AsSpan(73), groundSlot);
            return code;
        }

        /// <summary>(1.17.0) Where in RollStub its `.none` is (no battle), which a mod's own place goes to until the
        /// helper's own roll of the mods' battle grounds is made.</summary>
        public const int RollStubNone = 83;

        // --- the program -------------------------------------------------------------

        /// <summary>The native code standing in for the path search's read of whether a road is shown (called with
        /// ecx = 556 + the road; eax the answer, 0 not shown): where the search stands (esi) and where it goes (ebp),
        /// both kept by the search across the call, passed on with it to the helper's answer (`ways`:
        /// WaysInGame.RoadShown: ecx, edx, r8d), which it jumps to, so that returns to the search itself.</summary>
        public static byte[] Stub(ulong ways)
        {
            var code = new byte[18];
            code[0] = 0x89; code[1] = 0xF2;                      // mov edx, esi (where the search stands)
            code[2] = 0x41; code[3] = 0x89; code[4] = 0xE8;      // mov r8d, ebp (where it goes)
            code[5] = 0x48; code[6] = 0xB8;                      // mov rax, the helper's answer
            BinaryPrimitives.WriteUInt64LittleEndian(code.AsSpan(7), ways);
            code[15] = 0xFF; code[16] = 0xE0;                    // jmp rax
            code[17] = 0xCC;
            return code;
        }

        /// <summary>The memory the roads get, as it goes at `at`: the program's table (`gameRecords`, its 51
        /// pointers) followed by the mods' roads' records' places, the records, and the native code passing the path
        /// search's question to `ways` (Stub), each 16-aligned; (1.6.0) with `battleRoads` (BattleRoads), them and
        /// the native code turning a mod's road into the road it arrives as for the roll at `roll` (RollStub).</summary>
        public static TravelBlock Block(ulong at, ulong[] gameRecords, List<TravelRoad> roads, ulong ways,
                                        byte[]? battleRoads = null, ulong roll = 0, ulong groundSlot = 0)
        {
            static int Up(int n) => (n + 15) & ~15;
            int table = 0;
            int records = Up(table + 8 * (gameRecords.Length + roads.Count));
            int recordSize = Up(RecordHead + RecordPoints * RecordPoint);
            int code = Up(records + recordSize * roads.Count);
            var stub = Stub(ways);
            int battles = -1, rollCode = -1, end = Up(code + stub.Length);
            if (battleRoads != null)
            {
                battles = end;
                rollCode = Up(battles + battleRoads.Length);
                end = Up(rollCode + RollStub(0, 0, 0).Length);
            }
            var bytes = new byte[end];
            for (int n = 0; n < gameRecords.Length; n++)
                BinaryPrimitives.WriteUInt64LittleEndian(bytes.AsSpan(table + 8 * n), gameRecords[n]);
            for (int n = 0; n < roads.Count; n++)
            {
                int record = records + recordSize * n;
                BinaryPrimitives.WriteUInt64LittleEndian(bytes.AsSpan(table + 8 * (gameRecords.Length + n)),
                                                         at + (ulong)record);
                Record(roads[n]).CopyTo(bytes, record);
            }
            stub.CopyTo(bytes, code);
            if (battleRoads != null)
            {
                battleRoads.CopyTo(bytes, battles);
                RollStub(at + (ulong)battles, roll, groundSlot).CopyTo(bytes, rollCode);
            }
            return new TravelBlock(at, bytes, table, records, code, battles, rollCode);
        }

        static byte[] Rel32(long value)
        {
            var b = new byte[4];
            BinaryPrimitives.WriteInt32LittleEndian(b, checked((int)value));
            return b;
        }

        /// <summary>The changes to the program (loaded at `imageBase`) that give its three readers the block's table,
        /// its path search the block's native code and its loop the mods' roads, (1.6.0) and, with the block's
        /// native code for the roll, both calls of the roll that; each with the bytes it replaces. Null and why when a
        /// distance can't be made (the block too far from the program).</summary>
        public static List<CodePatch>? Patches(ReadOnlySpan<byte> image, Places places, ulong imageBase,
                                               TravelBlock block, int roads, out string why)
        {
            why = "";
            long table = (long)(block.At + (ulong)block.Table), code = (long)(block.At + (ulong)block.Code);
            long Distance(long target, int from) => target - ((long)imageBase + from);
            var patches = new List<CodePatch>();
            var rollCalls = new List<CodePatch>();
            try
            {
                int lea = places.PathSearch + Places.PathSearchTable;
                patches.Add(new CodePatch(lea + 3, image.Slice(lea + 3, 4).ToArray(), Rel32(Distance(table, lea + 7)),
                                          "the path search's table"));
                int walk = places.WalkSetup + Places.WalkSetupTable;
                patches.Add(new CodePatch(walk + 3, image.Slice(walk + 3, 4).ToArray(), Rel32(Distance(table, walk + 7)),
                                          "the walk's setup's table"));
                int read = places.LastRoad + Places.LastRoadTable;
                patches.Add(new CodePatch(read + 4, image.Slice(read + 4, 4).ToArray(), Rel32(table - (long)imageBase),
                                          "the travel's read of its last road's table"));
                int call = places.PathSearch + Places.PathSearchCall;
                patches.Add(new CodePatch(call + 1, image.Slice(call + 1, 4).ToArray(), Rel32(Distance(code, call + 5)),
                                          "the path search's read of a road shown"));
                // (1.6.0) Both calls of the random battles' roll to the native code that turns a mod's road into the
                // road it arrives as, last: either alone only turns roads the game's own never are.
                if (block.RollCode >= 0)
                {
                    long rollCode = (long)(block.At + (ulong)block.RollCode);
                    foreach (var (roll, what) in new[]
                             {
                                 (places.BattleRollArriving, "the travel's roll of a random battle as it arrives"),
                                 (places.BattleRollForced, "the world map's battle on the ground it stands on"),
                             })
                        rollCalls.Add(new CodePatch(roll + 1, image.Slice(roll + 1, 4).ToArray(),
                                                    Rel32(Distance(rollCode, roll + 5)), what));
                }
            }
            catch (OverflowException)
            {
                why = "the memory given the roads is more than 2 GB from the game's program";
                return null;
            }
            int loop = places.PathSearch + Places.PathSearchLoop;
            // cmp ebx, 0x33 (83 FB 33) to cmp bl, n (80 FB n); jl (0F 8C) to jb (0F 82): the road a byte, to 255.
            patches.Add(new CodePatch(loop, image.Slice(loop, 5).ToArray(),
                                      new byte[] { 0x80, 0xFB, (byte)(GameRoads + roads), 0x0F, 0x82 },
                                      "the path search's loop over the roads"));
            patches.AddRange(rollCalls);
            return patches;
        }

        // --- in the game ------------------------------------------------------------------

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern nint VirtualAlloc(nint address, nuint size, uint type, uint protect);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool VirtualProtect(nint address, nuint size, uint protect, out uint old);

        [DllImport("kernel32.dll")]
        static extern nint GetCurrentProcess();

        [DllImport("kernel32.dll")]
        static extern bool FlushInstructionCache(nint process, nint address, nuint size);

        const uint Commit = 0x1000, Reserve = 0x2000, ReadWrite = 0x04, ExecuteRead = 0x20, ExecuteReadWrite = 0x40;
        /// <summary>How far after the program the block may go: under 2 GB from its start, so the travel's read of
        /// its last road (a distance from the program's start) reaches it, and from every patched instruction.</summary>
        const long Reach = 0x7F000000;

        /// <summary>Memory of `size` bytes after the program (`imageBase`, `imageSize` long), within 2 GB of its start,
        /// writable; 0 when Windows gives none there.</summary>
        static nint Near(ulong imageBase, int imageSize, int size)
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

        /// <summary>The roads by number with their places and costs, for Ways: the game's 51 as its records have them
        /// (each record's places and cost, bytes 1 to 3; `records` its table's 51 pointers, `at` reading a record's
        /// byte), then the mods'.</summary>
        public static Ways WaysOf(ulong[] records, Func<ulong, byte> at, List<TravelRoad> roads)
        {
            var from = new byte[records.Length + roads.Count];
            var to = new byte[from.Length];
            var cost = new byte[from.Length];
            for (int n = 0; n < records.Length; n++)
            {
                from[n] = at(records[n] + 1);
                to[n] = at(records[n] + 2);
                cost[n] = at(records[n] + 3);
            }
            for (int n = 0; n < roads.Count; n++)
            {
                from[records.Length + n] = (byte)roads[n].From;
                to[records.Length + n] = (byte)roads[n].To;
                cost[records.Length + n] = (byte)roads[n].Cost;
            }
            return new Ways(from, to, cost);
        }

        /// <summary>The roads given to the program, before the game runs: the block made and written (read-only and
        /// runnable once written), each patch checked against the bytes it replaces and made; the path search's
        /// question answered by WaysInGame (the roads' Ways; `ready` the byte, the helper's, 0, that lets the mods'
        /// roads be shown once set); (1.6.0) with what random battles need found, each road arriving at a battle
        /// ground given the entrance it uses there (`battles`), both calls of the roll turning it into that road.
        /// Null, or why not: then nothing of the program is changed, unless Windows refuses a patch partway, after
        /// letting the ones before it on the same two pages be made. Those stay, and keep the game's travel as it
        /// was: the roads are then drawn only (Mod.cs), so `ready` is never set, no mod's road is shown, and the
        /// table's first 51 are the game's.</summary>
        public static string? Arm(byte* start, int imageSize, Places places, List<TravelRoad> roads, nint ready,
                                  out List<RoadBattle> battles, out nint groundSlot)
        {
            var image = new ReadOnlySpan<byte>(start, imageSize);
            var game = new ulong[GameRoads];
            for (int n = 0; n < GameRoads; n++)
                game[n] = BinaryPrimitives.ReadUInt64LittleEndian(image.Slice(places.RoadRecords + 8 * n, 8));
            ulong imageBase = (ulong)start;
            battles = new List<RoadBattle>();
            groundSlot = 0;
            byte[]? battleRoads = null;
            ulong roll = 0;
            if (places.RoadBattles && places.BattleRoll >= 0)
            {
                nint entrances = (nint)(start + places.BattleTable);
                battles = Battles(roads, game, address => *(byte*)address, offset => *(byte*)(entrances + offset));
                battleRoads = BattleRoads(roads, battles);
                roll = imageBase + (ulong)places.BattleRoll;
                // (1.17.0) Where a mod's own place's roll goes: no battle until the helper's own roll is made.
                groundSlot = (nint)NativeMemory.AllocZeroed(16);
            }
            var sized = Block(0, game, roads, 0, battleRoads, roll, (ulong)groundSlot);
            nint at = Near(imageBase, imageSize, sized.Bytes.Length);
            if (at == 0)
                return "Windows gave no memory within 2 GB of the game's program";
            var ways = WaysOf(game, address => *(byte*)address, roads);
            nint answer = WaysInGame.Set(ways, (nint)(start + places.SearchDepth), (nint)(start + places.SearchCost),
                                         (nint)(start + places.VariableGet), (nint)(start + places.PlaceShown), ready);
            var block = Block((ulong)at, game, roads, (ulong)answer, battleRoads, roll, (ulong)groundSlot);
            if (groundSlot != 0)
                *(ulong*)groundSlot = (ulong)at + (ulong)block.RollCode + RollStubNone;
            var patches = Patches(image, places, imageBase, block, roads.Count, out string why);
            if (patches == null)
                return why;
            foreach (var patch in patches)
                if (!image.Slice(patch.At, patch.Old.Length).SequenceEqual(patch.Old))
                    return $"{patch.What} isn't as it was found";
            Marshal.Copy(block.Bytes, 0, at, block.Bytes.Length);
            if (!VirtualProtect(at, (nuint)block.Bytes.Length, ExecuteRead, out _))
                return "the roads' memory couldn't be made runnable";
            FlushInstructionCache(GetCurrentProcess(), at, (nuint)block.Bytes.Length);
            foreach (var patch in patches)
            {
                nint where = (nint)(start + patch.At);
                if (!VirtualProtect(where, (nuint)patch.New.Length, ExecuteReadWrite, out uint old))
                    return $"{patch.What} couldn't be changed";
                Marshal.Copy(patch.New, 0, where, patch.New.Length);
                VirtualProtect(where, (nuint)patch.New.Length, old, out _);
                FlushInstructionCache(GetCurrentProcess(), where, (nuint)patch.New.Length);
            }
            return null;
        }
    }
}
