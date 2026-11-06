// Mod Studio's checks of the helper: (1.5.0) travel along a mod's road
// between the game's places (Travel.cs), over his program laid out as in
// memory: what the helper finds for it (the path search, its count of roads
// taken, its table, its read of a road shown, its loop; the walk's setup; the
// travel's read of its last road; the test of a place shown), the roads it
// numbers from a mod's folder, the memory it gives them as it would go at a
// chosen place (the table, the records, the native code passing the search's
// question on to a chosen address), the changes to the program, the roads'
// rows added to stand-ins of Route and MapRouteTable (dev/research/sidequests/
// travel.py makes them as the game's are laid out, from the game's rows), the
// tables' hook against stand-ins of the game's table and file, and the
// answers to the search's question (Ways): each place's fewest roads to where
// a search goes, and the answer to roads from where it stands. dev/
// test_side_quests.py then runs the game's own path search, walk setup and
// last road's read over the program so changed, with unicorn, the question
// answered there as Ways answers it. Part of The Ivalice Chronicles Mod
// Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --travel <program> <report.json> <route.nxd> <maproutetable.nxd> <out> <block at> <answer at>
//                       <mod id>=<folder> ...
//     dotnet Checks.dll --nxd <table> <out table> <report.json> <key>[,<key>...]=<row's bytes, hex> ...
//
// --nxd: any table given rows by the helper's Nxd.WithRows (a table of two keys of the game's, WotL Restoration's
// continuoussortieconfirm.nxd, given rows round its own), for the game's own setup and lookups to read.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.Json;
using ModStudioEventSetup;

static class TravelChecks
{
    static string Hex(byte[] bytes) => Convert.ToHexString(bytes);

    /// <summary>(1.17.0) Where the roll's native code finds what a mod's own place goes to (Travel.RollStub's slot),
    /// here: dev/test_side_quests.py maps it, holding the native code's own `.none`, or a stand-in for the helper's
    /// roll.</summary>
    public const ulong GroundSlotAt = 0x146000000;

    public static int Run(string[] args)
    {
        var image = Program.Load(args[1]);
        string reportPath = args[2], routePath = args[3], pointsPath = args[4], outFolder = args[5];
        ulong blockAt = ulong.Parse(args[6], NumberStyles.HexNumber), answerAt = ulong.Parse(args[7], NumberStyles.HexNumber);
        var report = new Dictionary<string, object?>();
        var places = Places.Find(image);
        report["found"] = new Dictionary<string, object>
        {
            ["PathSearch"] = places.PathSearch, ["RoadRecords"] = places.RoadRecords, ["VariableGet"] = places.VariableGet,
            ["WalkSetup"] = places.WalkSetup, ["LastRoad"] = places.LastRoad, ["PlaceShown"] = places.PlaceShown,
            ["SheetInit"] = places.SheetInit, ["SearchDepth"] = places.SearchDepth, ["SearchCost"] = places.SearchCost,
            ["BattleRoll"] = places.BattleRoll, ["BattleTable"] = places.BattleTable,
            ["BattleRollArriving"] = places.BattleRollArriving, ["BattleRollForced"] = places.BattleRollForced,
        };
        report["missing"] = places.MissingForJourneys;
        report["missingBattles"] = places.MissingForRoadBattles;
        var problems = new List<string>();
        var roads = new List<MapRoad>();
        for (int n = 8; n < args.Length; n++)
        {
            int split = args[n].IndexOf('=');
            string id = args[n].Substring(0, split), folder = args[n].Substring(split + 1);
            var own = PlaceFile.ReadMod(id, id, folder, problems);
            roads.AddRange(RoadFile.ReadMod(id, id, folder, own.ConvertAll(p => p.Name), problems));
        }
        var said = new List<string>();
        var travel = Travel.Plan(roads, said);
        report["problems"] = problems;
        report["said"] = said;
        report["travel"] = travel.ConvertAll(t => new object[]
        {
            t.Road.Name, t.Number, t.Cost, t.From, t.To,
            t.Road.Walk.ConvertAll(p => new[] { p.X, p.Y }), Hex(Travel.Record(t)), Hex(Travel.RouteRow(t)),
        });
        report["drawnOnly"] = roads.FindAll(r => !r.BetweenGamePlaces).ConvertAll(r => r.Name);
        if (places.Journeys)
        {
            const ulong imageBase = 0x140000000;
            var game = new ulong[Travel.GameRoads];
            for (int n = 0; n < Travel.GameRoads; n++)
                game[n] = BitConverter.ToUInt64(image, places.RoadRecords + 8 * n);
            // (1.6.0) Where each road arriving at a battle ground starts its random battles, and what the roll gets.
            var battles = new List<RoadBattle>();
            byte[]? battleRoads = null;
            ulong roll = 0;
            if (places.RoadBattles)
            {
                battles = Travel.Battles(travel, game, address => image[(int)(address - imageBase)],
                                         offset => image[places.BattleTable + offset]);
                battleRoads = Travel.BattleRoads(travel, battles);
                roll = imageBase + (ulong)places.BattleRoll;
            }
            report["battles"] = battles.ConvertAll(b => new object[] { b.Road.Number, b.Place, b.GameRoad, b.From });
            var block = Travel.Block(blockAt, game, travel, answerAt, battleRoads, roll, GroundSlotAt);
            report["block"] = new Dictionary<string, object>
            {
                ["at"] = block.At.ToString("X"), ["bytes"] = Hex(block.Bytes), ["table"] = block.Table,
                ["records"] = block.Records, ["code"] = block.Code, ["stub"] = Hex(Travel.Stub(answerAt)),
                ["battles"] = block.Battles, ["rollCode"] = block.RollCode,
                ["rollStub"] = battleRoads == null ? ""
                    : Hex(Travel.RollStub(blockAt + (ulong)block.Battles, roll, GroundSlotAt)),
                ["groundSlot"] = GroundSlotAt.ToString("X"), ["rollNone"] = Travel.RollStubNone,
                ["battleRoads"] = battleRoads == null ? "" : Hex(battleRoads),
            };
            var patches = Travel.Patches(image, places, imageBase, block, travel.Count, out string why);
            report["patchesWhy"] = why;
            report["patches"] = patches?.ConvertAll(p => new object[] { p.At, Hex(p.Old), Hex(p.New), p.What });
            // A block too far from the program: no patches, said.
            var far = Travel.Block(imageBase + 0x90000000UL, game, travel, 0);
            Travel.Patches(image, places, imageBase, far, travel.Count, out string farWhy);
            report["farWhy"] = farWhy;
            report["ways"] = WaysReport(Travel.WaysOf(game, address => image[(int)(address - imageBase)], travel));
            report["inGame"] = InGame(Travel.WaysOf(game, address => image[(int)(address - imageBase)], travel));
        }
        Directory.CreateDirectory(outFolder);
        var tables = new Dictionary<string, object?>();
        foreach (var (sheet, path, name) in new[] { (Travel.RouteSheet, routePath, "route.nxd"),
                                                     (Travel.PointsSheet, pointsPath, "maproutetable.nxd") })
        {
            var loaded = File.ReadAllBytes(path);
            string shape = Travel.ShapeProblem(sheet, loaded);
            var made = Travel.WithRows(sheet, loaded, travel, out string why);
            if (made != null)
                File.WriteAllBytes(Path.Combine(outFolder, name), made);
            tables[name] = new Dictionary<string, object?> { ["shape"] = shape, ["why"] = why, ["written"] = made != null };
            // The other sheet's shape on this table (a Route isn't two keys; a MapRouteTable isn't one key).
            int other = sheet == Travel.RouteSheet ? Travel.PointsSheet : Travel.RouteSheet;
            tables[name + " as the other"] = Travel.ShapeProblem(other, loaded);
        }
        report["tables"] = tables;
        report["giving"] = Giving(File.ReadAllBytes(routePath), File.ReadAllBytes(pointsPath), travel);
        File.WriteAllText(reportPath, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
        return 0;
    }

    /// <summary>Ways over the program's roads and the mods': which roads (by number), their places and costs; each
    /// place's (0 to 47) fewest roads to each place and their least cost, with every road shown and with every fifth
    /// of the game's (0, 5, ...) and the mods' second hidden; the answers, a character a road ("1" or "0"), from a
    /// start to an end, every 5th place to every other 5th, the search 0 roads along at no cost, 1 at 40, 2 at 80, every
    /// road shown.</summary>
    static Dictionary<string, object> WaysReport(Ways ways)
    {
        bool All(int road) => true;
        bool Some(int road) => !(road < Travel.GameRoads && road % 5 == 0) && road != Travel.GameRoads + 1;
        var report = new Dictionary<string, object>();
        var roads = new List<int[]>();
        for (int road = 0; road < ways.Count; road++)
            roads.Add(new[] { ways.From(road), ways.To(road), ways.Cost(road) });
        report["roads"] = roads;
        foreach (var (name, shown) in new (string, Func<int, bool>)[] { ("all", All), ("some", Some) })
        {
            var counted = new List<int[]>();
            for (int end = 0; end < 48; end++)
            {
                ways.Prepare(0, end, shown);
                var row = new int[96];
                for (int place = 0; place < 48; place++)
                {
                    row[place] = ways.Length(place);
                    row[48 + place] = ways.CostTo(place);
                }
                counted.Add(row);
            }
            report[name] = counted;
        }
        var answers = new Dictionary<string, string>();
        for (int start = 0; start < 47; start += 5)
            for (int end = 1; end < 47; end += 5)
            {
                ways.Prepare(start, end, All);
                for (int depth = 0; depth < 3; depth++)
                {
                    var line = new char[ways.Count];
                    for (int road = 0; road < ways.Count; road++)
                        line[road] = ways.Answer(road, start, depth, 40 * depth) ? '1' : '0';
                    answers[$"{start} {end} {depth}"] = new string(line);
                }
            }
        report["answers"] = answers;
        ways.Prepare(10, 30, All);
        report["best 10 30"] = new[] { ways.BestLength, ways.BestCost };
        ways.Prepare(0, 47, All);
        report["best 0 47"] = new[] { ways.BestLength, ways.BestCost };
        return report;
    }

    // --- WaysInGame, as the game's search asks it -------------------------------------------------------------

    /// <summary>Stand-ins for the game's variables (the variables' read: a byte each) and its test of a place shown
    /// (places under 43 by variable 512 + the place; 44 to 46, by flags these have none of, not).</summary>
    static readonly byte[] Variables = new byte[0x1000];

    [System.Runtime.InteropServices.UnmanagedCallersOnly]
    static int Variable(int number) => number >= 0 && number < Variables.Length ? Variables[number] : 0;

    [System.Runtime.InteropServices.UnmanagedCallersOnly]
    static byte PlaceShown(nint unused, int place) => (byte)(place >= 0 && place < 43 && Variables[0x200 + place] != 0 ? 1 : 0);

    /// <summary>The game's path search as read (0x2471FC; travel.py's path_model), asking WaysInGame's answer whether
    /// each road is shown as the game's asks its read (the road's variable, where it stands, where it goes), its count
    /// of roads taken and their cost kept where the answer reads them.</summary>
    sealed unsafe class Search
    {
        readonly Ways _ways;
        readonly delegate* unmanaged<int, int, int, int> _ask;
        readonly int* _depth, _cost;
        readonly int[] _path = new int[16];
        int[]? _best;
        int _bestCost, _bound, _end;
        public int Asked;

        public Search(Ways ways, nint answer, int* depth, int* cost)
        {
            _ways = ways;
            _ask = (delegate* unmanaged<int, int, int, int>)answer;
            _depth = depth;
            _cost = cost;
        }

        public string Run(int start, int end)
        {
            _best = null;
            _bestCost = _bound = 99999;
            _end = end;
            *_depth = 0;
            *_cost = 0;
            Asked = 0;
            Step(start);
            return _best == null ? "-" : string.Join(",", _best) + " " + _bestCost;
        }

        void Step(int place)
        {
            if (*_depth >= 16)
                return;
            for (int road = 0; road < _ways.Count; road++)
            {
                Asked++;
                if (_ask(Travel.ShownFirst + road, place, _end) == 0)
                    continue;
                int depth = *_depth;
                bool used = false;
                for (int n = 0; n < depth; n++)
                    used |= (_path[n] & 0xFF) == road;
                if (used)
                    continue;
                int longer = depth + 1, cost = _ways.Cost(road), a = _ways.From(road), b = _ways.To(road);
                if (longer > _bound || (longer == _bound && *_cost + cost > _bestCost))
                    continue;
                if ((place == a && _end == b) || (_end == a && place == b))
                {
                    _path[depth] = place == a ? road : road | 0x100;
                    _best = _path[..longer];
                    _bestCost = *_cost + cost;
                    _bound = longer;
                }
                else if (place == a || place == b)
                {
                    _path[depth] = place == a ? road : road | 0x100;
                    *_depth = longer;
                    *_cost += cost;
                    Step(place == a ? b : a);
                    *_depth = depth;
                    *_cost -= cost;
                }
            }
        }
    }

    /// <summary>WaysInGame set as the helper sets it in the game (its count of roads taken and their cost, the
    /// variables' read, the test of a place shown and the ready byte stood in for), the game's search run asking it,
    /// every way between the places the roads join: every place shown and every road of the game's; then before both
    /// tables have the mods' rows; then with the Tchigolith Fenlands (30) not shown; each way the roads (bit 8 the
    /// other way) and its cost, or "-"; and the most questions a way.</summary>
    internal static unsafe Dictionary<string, object> InGame(Ways ways, int hidden30 = 30)
    {
        int* counts = (int*)System.Runtime.InteropServices.NativeMemory.AllocZeroed(16);
        byte* ready = (byte*)System.Runtime.InteropServices.NativeMemory.AllocZeroed(16);
        nint answer = WaysInGame.Set(ways, (nint)counts, (nint)(counts + 1),
                                     (nint)(delegate* unmanaged<int, int>)&Variable,
                                     (nint)(delegate* unmanaged<nint, int, byte>)&PlaceShown, (nint)ready);
        var search = new Search(ways, answer, counts, counts + 1);
        var places = new SortedSet<int>();
        for (int road = 0; road < ways.Count; road++)
        {
            places.Add(ways.From(road));
            places.Add(ways.To(road));
        }
        var report = new Dictionary<string, object>();
        int most = 0;
        foreach (var (name, readyNow, hidden) in new[] { ("ours", 1, -1), ("waiting", 0, -1), ($"hidden {hidden30}", 1, hidden30) })
        {
            Array.Clear(Variables);
            for (int place = 0; place < 43; place++)
                Variables[0x200 + place] = (byte)(place == hidden ? 0 : 1);
            for (int road = 0; road < Travel.GameRoads; road++)
                Variables[Travel.ShownFirst + road] = 1;
            *ready = (byte)readyNow;
            var ways_ = new Dictionary<string, string>();
            int asked = 0;
            foreach (int a in places)
                foreach (int b in places)
                    if (a != b)
                    {
                        ways_[$"{a} {b}"] = search.Run(a, b);
                        most = Math.Max(most, search.Asked);
                        asked += search.Asked;
                    }
            report[name] = ways_;
            report[name + " asked"] = asked;
        }
        report["most asked"] = most;
        return report;
    }

    /// <summary>The tables' hook's giving (TravelTables), against stand-ins of the game's table (its number at + 8,
    /// its file at + 0x30) and file (its bytes at + 0x38, their size at + 0x40), step by step: what it said, the
    /// byte that lets the roads be shown, whether the file's bytes were swapped, and whether for the table with the
    /// roads' rows (or left as they were).</summary>
    static unsafe List<object[]> Giving(byte[] route, byte[] points, List<TravelRoad> travel)
    {
        var steps = new List<object[]>();
        var said = new List<string>();
        nint ready = (nint)System.Runtime.InteropServices.NativeMemory.AllocZeroed(16);
        var giving = new TravelTables(travel, ready, said.Add);
        nint Sheet(int number, nint file)
        {
            nint sheet = (nint)System.Runtime.InteropServices.NativeMemory.AllocZeroed(0x100);
            *(int*)(sheet + TravelTables.SheetNumber) = number;
            *(nint*)(sheet + TravelTables.SheetFile) = file;
            return sheet;
        }
        nint FileOf(byte[] bytes)
        {
            nint file = (nint)System.Runtime.InteropServices.NativeMemory.AllocZeroed(0x100);
            nint data = (nint)System.Runtime.InteropServices.NativeMemory.Alloc((nuint)Math.Max(1, bytes.Length));
            System.Runtime.InteropServices.Marshal.Copy(bytes, 0, data, bytes.Length);
            *(nint*)(file + TravelTables.FileBytes) = data;
            *(long*)(file + TravelTables.FileSize) = bytes.Length;
            return file;
        }
        void Step(string what, nint sheet, nint file, byte[]? expect)
        {
            said.Clear();
            nint before = file == 0 ? 0 : *(nint*)(file + TravelTables.FileBytes);
            giving.Give(sheet, file);
            nint after = file == 0 ? 0 : *(nint*)(file + TravelTables.FileBytes);
            long size = file == 0 ? 0 : *(long*)(file + TravelTables.FileSize);
            bool swapped = after != before;
            bool asExpected = expect == null ? !swapped
                : swapped && size == expect.Length && new ReadOnlySpan<byte>((void*)after, (int)size).SequenceEqual(expect);
            steps.Add(new object[] { what, new List<string>(said), *(byte*)ready, swapped, asExpected });
        }
        var withRoute = Travel.WithRows(Travel.RouteSheet, route, travel, out _);
        var withPoints = Travel.WithRows(Travel.PointsSheet, points, travel, out _);
        nint routeFile = FileOf(route), routeSheet = Sheet(Travel.RouteSheet, routeFile);
        Step("Route set up", routeSheet, routeFile, withRoute);
        nint other = FileOf(route);
        Step("another table set up", Sheet(0x34, other), other, null);
        nint pointsFile = FileOf(points);
        Step("MapRouteTable set up", Sheet(Travel.PointsSheet, pointsFile), pointsFile, withPoints);
        Step("Route's file given again", routeSheet, routeFile, null);
        nint wrong = FileOf(route);
        Step("MapRouteTable loaded again from a table of one key", Sheet(Travel.PointsSheet, wrong), wrong, null);
        nint again = FileOf(points);
        Step("MapRouteTable loaded again", Sheet(Travel.PointsSheet, again), again, withPoints);
        nint elsewhere = FileOf(route);
        Step("Route whose table keeps its file elsewhere", Sheet(Travel.RouteSheet, FileOf(route)), elsewhere, null);
        nint empty = FileOf(Array.Empty<byte>());
        Step("Route of no bytes", Sheet(Travel.RouteSheet, empty), empty, null);
        Step("no table", 0, FileOf(route), null);
        Step("no file", Sheet(Travel.RouteSheet, 0), 0, null);
        nint last = FileOf(route);
        Step("Route set up again", Sheet(Travel.RouteSheet, last), last, withRoute);
        return steps;
    }

    public static int RunNxd(string[] args)
    {
        var table = File.ReadAllBytes(args[1]);
        string outPath = args[2], reportPath = args[3];
        var rows = new List<NewRow>();
        for (int n = 4; n < args.Length; n++)
        {
            int split = args[n].IndexOf('=');
            var keys = Array.ConvertAll(args[n].Substring(0, split).Split(','), int.Parse);
            rows.Add(new NewRow(keys, Convert.FromHexString(args[n].Substring(split + 1))));
        }
        var made = Nxd.WithRows(table, rows, out string why);
        if (made != null)
            File.WriteAllBytes(outPath, made);
        var report = new Dictionary<string, object?> { ["keys"] = Nxd.Keys(table), ["why"] = why, ["written"] = made != null };
        File.WriteAllText(reportPath, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
        return 0;
    }
}
