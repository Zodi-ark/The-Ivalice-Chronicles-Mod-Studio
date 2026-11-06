// Mod Studio's checks of the helper: (1.7.0) a mod's own place as a
// destination (Destinations.cs), over his program laid out as in memory:
// what the helper finds for it (the places' records and their reads, the
// world map's dots and every instruction reaching them, the screen's reads of
// a place's row, its allocations and constructor, its switch of its places'
// boxes, the setting of a text), the places it numbers from mods' folders
// (with the numbers kept, Numbers.json's text in and out), the roads to them
// it travels, the memory it gives them as it would go at chosen places (the
// records copied, the dots, the native code), the changes to the program, and
// the places' rows added to stand-ins of Town and PlaceName (dev/research/
// sidequests/destinations.py makes them as the game's are laid out, from the
// game's rows); and the roads to them as travel takes them (TravelChecks'
// memory, changes and answer to the path search, with the places numbered:
// a mod's place shown). dev/test_side_quests.py then runs the program's own
// code so changed with unicorn. Part of The Ivalice Chronicles Mod Studio,
// GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --destinations <program> <report.json> <town.nxd> <placename.nxd> <out> <data at> <code at>
//                       <numbers.json or -> <mod id>=<folder> ...
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;
using ModStudioEventSetup;

static unsafe class DestinationChecks
{
    static string Hex(byte[] bytes) => Convert.ToHexString(bytes);
    /// <summary>Where the travel's memory goes here, and the helper's answer it jumps to (TravelChecks' are 0x144000000
    /// and 0x150000000; the places' data and code go where asked).</summary>
    const ulong TravelAt = 0x146000000, AnswerAt = 0x150000000;

    public static int Run(string[] args)
    {
        var image = Program.Load(args[1]);
        string reportPath = args[2], townPath = args[3], namePath = args[4], outFolder = args[5];
        ulong dataAt = ulong.Parse(args[6], NumberStyles.HexNumber), codeAt = ulong.Parse(args[7], NumberStyles.HexNumber);
        string numbersPath = args[8];
        var report = new Dictionary<string, object?>();
        var places = Places.Find(image);
        report["found"] = new Dictionary<string, object>
        {
            ["LocationRecords"] = places.LocationRecords, ["LocationRecordLea"] = places.LocationRecordLea,
            ["LocationRecordReads"] = places.LocationRecordReads, ["Dots"] = places.Dots, ["DotLeas"] = places.DotLeas,
            ["DotReads"] = places.DotReads.ConvertAll(r => new[] { r.At, r.Distance }),
            ["PlacePosition"] = places.PlacePosition, ["CursorAtPlace"] = places.CursorAtPlace,
            ["DistanceBound"] = places.DistanceBound, ["DistanceRead"] = places.DistanceRead,
            ["ArrivedFirst"] = places.ArrivedFirst, ["ArrivedSecond"] = places.ArrivedSecond,
            ["PieceEvents"] = places.PieceEvents, ["HelpBound"] = places.HelpBound, ["HelpKind"] = places.HelpKind,
            ["HelpKindAgain"] = places.HelpKindAgain, ["MarkerPlace"] = places.MarkerPlace, ["MapAlloc"] = places.MapAlloc,
            ["FrameAlloc"] = places.FrameAlloc, ["ScreenCtor"] = places.ScreenCtor,
            ["CollisionSwitch"] = places.CollisionSwitch, ["BoxOfKind"] = places.BoxOfKind,
            ["BoxRefresh"] = places.BoxRefresh, ["SetText"] = places.SetText,
            ["Distance"] = places.Distance, ["Nearest"] = places.Nearest, ["NearestFocus"] = places.NearestFocus,
            // (1.23.1) The name of the place arrived at (its read of the place plus one, and that).
            ["ArrivalName"] = places.ArrivalName, ["ArrivalNameValue"] = places.ArrivalNameValue,
            // (1.23.2) The menu's name of its place.
            ["MenuName"] = places.MenuName,
            ["SaveLoad"] = places.SaveLoad, ["SaveBank"] = places.SaveBank,
            // (1.19.0) A town's own art and picture in its menu.
            ["BaseArt"] = places.BaseArt, ["MenuIcon"] = places.MenuIcon, ["UiRoot"] = places.UiRoot,
            ["MissingForMenuArt"] = places.MissingForMenuArt,
            // (1.21.0) A mod's dungeon (its native code given with the places').
            ["Entries"] = places.Entries, ["DungeonBlock"] = places.DungeonBlock, ["DungeonTown"] = places.DungeonTown,
            ["DungeonCopy"] = places.DungeonCopy, ["DungeonScreen"] = places.DungeonScreen,
            ["DungeonHandler"] = places.DungeonHandler, ["CurrentPlace"] = places.CurrentPlace,
            ["FloorCall"] = places.FloorCall, ["Chains"] = places.Chains, ["FloorOut"] = places.FloorOut,
            ["RandomSetup"] = places.RandomSetup, ["RowTitleCall"] = places.RowTitleCall,
            ["RowInfoCall"] = places.RowInfoCall, ["RowLookup"] = places.RowLookup,
            ["MissingForDungeons"] = places.MissingForDungeons, ["Dungeons"] = places.Dungeons,
            // (1.23.0) Test 49's findings: the transition's queue (a dungeon's battle at once), the location list, the
            // Deep's list's looks.
            ["TransitionCount"] = places.TransitionCount, ["TransitionCommands"] = places.TransitionCommands,
            ["TransitionKinds"] = places.TransitionKinds, ["MissingForInstantBattles"] = places.MissingForInstantBattles,
            ["InstantBattles"] = places.InstantBattles, ["ListEnd"] = places.ListEnd, ["ListGrow"] = places.ListGrow,
            ["ListRowLookup"] = places.ListRowLookup, ["MissingForLocations"] = places.MissingForLocations,
            // (1.23.1) The location list's kinds of a town's shop: the items' list, the item's data, the stock.
            ["ListItems"] = places.ListItems, ["ListItem"] = places.ListItem, ["Stock"] = places.Stock,
            ["TownMenus"] = places.TownMenus,
            ["Locations"] = places.Locations, ["UiText"] = places.UiText, ["TwoKeyRow"] = places.TwoKeyRow,
            ["GuideShow"] = places.GuideShow, ["DeepGuide"] = places.DeepGuide, ["AboutOpen"] = places.AboutOpen,
            ["AboutGuide"] = places.AboutGuide, ["PlaceNameText"] = places.PlaceNameText,
            ["ArtSetter"] = places.ArtSetter, ["TextRemake"] = places.TextRemake,
            ["MissingForDungeonLooks"] = places.MissingForDungeonLooks, ["DungeonLooks"] = places.DungeonLooks,
        };
        report["missing"] = places.MissingForDestinations;
        report["missingForSaveFallback"] = places.MissingForSaveFallback;
        var problems = new List<string>();
        var mapPlaces = new List<MapPlace>();
        var roads = new List<MapRoad>();
        for (int n = 9; n < args.Length; n++)
        {
            int split = args[n].IndexOf('=');
            string id = args[n].Substring(0, split), folder = args[n].Substring(split + 1);
            var own = PlaceFile.ReadMod(id, id, folder, problems);
            mapPlaces.AddRange(own);
            roads.AddRange(RoadFile.ReadMod(id, id, folder, own.ConvertAll(p => p.Name), problems));
        }
        var read = new List<string>();
        var numbers = Numbers.FromText(numbersPath == "-" ? "" : File.ReadAllText(numbersPath), read);
        var said = new List<string>();
        var destinations = Destinations.Plan(mapPlaces, numbers, said);
        report["problems"] = problems;
        report["said"] = said;
        report["numbersRead"] = read;
        report["destinations"] = destinations.ConvertAll(d => new object[]
        {
            d.Place.Name, d.Place.ModId, d.Number, d.MarkerX, d.MarkerY, d.NameId, d.Place.Town,
            new[] { (int)Destinations.DotOf(d).X, (int)Destinations.DotOf(d).Y },
            Hex(Destinations.TownRow(d)), Hex(Destinations.NameRow(d)),
        });
        report["rows"] = Destinations.RowCount(destinations);
        // (1.19.0) Each place's own art's path as the base art's hook gives it (its number OwnArt plus the place's), or
        // null (the game's own path); and whether a town's own picture is given its menu's picture box.
        var menuArt = new MenuArt(null, places, destinations);
        report["arts"] = destinations.ConvertAll(d => new object?[]
        {
            d.Number, menuArt.PathOf(Destinations.OwnArt + d.Number) is byte[] path
                ? System.Text.Encoding.ASCII.GetString(path) : null,
        });
        report["artNumbers"] = new object?[]
        {
            menuArt.PathOf(Destinations.OwnArt - 1) == null, menuArt.PathOf(0) == null, menuArt.PathOf(26) == null,
            menuArt.HasArts, menuArt.HasIcons,
        };
        var travelSaid = new List<string>();
        var travel = Travel.Plan(roads, travelSaid, destinations);
        // (1.7.1) Each place's home kept with its number (the plan's, Mod.cs), the numbers' text with them.
        var homes = SaveFallback.Homes(destinations, travel);
        foreach (var (place, home) in homes)
            numbers.Home(place, home);
        report["homes"] = homes.ToDictionary(h => h.Key.ToString(CultureInfo.InvariantCulture), h => h.Value);
        report["numbers"] = numbers.Text();
        // (1.7.1) A save standing on each place loaded with only some of them given (the second's mod gone): where
        // it goes on from, and what is said; Numbers.json's text read back keeping the homes.
        var given = destinations.Count > 1 ? new List<int> { destinations[0].Number } : new List<int>();
        var fallbacks = new List<object?[]>();
        foreach (int place in new[] { 0, 6, 46, 47, 48, 49, 50, 51, 99, 254 })
        {
            int now = SaveFallback.Fallback(place, given, numbers, out string? fell);
            fallbacks.Add(new object?[] { place, now, fell });
        }
        report["fallbacks"] = fallbacks;
        report["fallbackConstants"] = new[] { SaveFallback.PlaceVariable, SaveFallback.Gariland };
        var back = Numbers.FromText(numbers.Text(), new List<string>());
        report["homesBack"] = new[] { back.HomeOf(48), back.HomeOf(49), back.HomeOf(50), back.HomeOf(51) };
        report["travelSaid"] = travelSaid;
        report["travel"] = travel.ConvertAll(t => new object[]
        {
            t.Road.Name, t.Number, t.Cost, t.From, t.To, Hex(Travel.Record(t)), Hex(Travel.RouteRow(t)),
        });
        // Without the places numbered, the roads to them drawn only, as 1.6.0.
        report["travelWithout"] = Travel.Plan(roads, new List<string>()).ConvertAll(t => t.Road.Name);
        // The roads to them travelled (Travel.cs, 1.5.0 and 1.6.0, with the places numbered): their random battles,
        // the memory travel gets (at TravelAt, its answer at AnswerAt) and its changes, and the helper's answer to the
        // path search's question as the game asks it (WaysInGame, its place shown counting the mods' places).
        if (places.Journeys)
        {
            const ulong travelBase = 0x140000000;
            var game = new ulong[Travel.GameRoads];
            for (int n = 0; n < Travel.GameRoads; n++)
                game[n] = BitConverter.ToUInt64(image, places.RoadRecords + 8 * n);
            var battles = new List<RoadBattle>();
            byte[]? battleRoads = null;
            ulong roll = 0;
            if (places.RoadBattles)
            {
                battles = Travel.Battles(travel, game, address => image[(int)(address - travelBase)],
                                         offset => image[places.BattleTable + offset]);
                battleRoads = Travel.BattleRoads(travel, battles);
                roll = travelBase + (ulong)places.BattleRoll;
            }
            report["battles"] = battles.ConvertAll(b => new object[] { b.Road.Number, b.Place, b.GameRoad, b.From });
            var block = Travel.Block(TravelAt, game, travel, AnswerAt, battleRoads, roll);
            report["travelBlock"] = new Dictionary<string, object> { ["at"] = block.At.ToString("X"),
                                                                     ["bytes"] = Hex(block.Bytes) };
            var travelPatches = Travel.Patches(image, places, travelBase, block, travel.Count, out string travelWhy);
            report["travelPatchesWhy"] = travelWhy;
            report["travelPatches"] = travelPatches?.ConvertAll(p => new object[] { p.At, Hex(p.Old), Hex(p.New), p.What });
            report["inGame"] = TravelChecks.InGame(Travel.WaysOf(game, address => image[(int)(address - travelBase)],
                                                                 travel), 28);
        }
        if (places.Destinations && destinations.Count > 0)
        {
            const ulong imageBase = 0x140000000;
            var memory = Destinations.Given(image, places, imageBase, dataAt, codeAt, destinations, out var patches,
                                            out string why);
            if (memory != null)
                report["memory"] = new Dictionary<string, object>
                {
                    ["data"] = Hex(memory.Data), ["code"] = Hex(memory.Code), ["stubs"] = memory.Stubs,
                    ["records"] = Destinations.DataRecords, ["dots"] = Destinations.DataDots,
                };
            report["patchesWhy"] = why;
            report["patches"] = patches?.ConvertAll(p => new object[] { p.At, Hex(p.Old), Hex(p.New), p.What });
            // Memory too far from the program, its data, then its native code: no changes, said.
            var farWhy = new List<string>();
            foreach (var (farData, farCode) in new[] { (imageBase + 0x90000000UL, codeAt),
                                                       (dataAt, imageBase + 0x90100000UL) })
            {
                var far = Destinations.Given(image, places, imageBase, farData, farCode, destinations, out var farPatches,
                                             out string whyFar);
                farWhy.Add(far == null && farPatches == null ? whyFar : "given");
            }
            report["farWhy"] = farWhy;
        }
        // The tables' hook giving the places' rows with the roads' (TravelTables, 1.7.0): Route's and MapRouteTable's
        // stand-ins beside Town's, when the suite has made them (TravelChecks' run before this one).
        string here = Path.GetDirectoryName(Path.GetFullPath(townPath)) ?? ".";
        string routePath = Path.Combine(here, "route.nxd"), pointsPath = Path.Combine(here, "maproutetable.nxd");
        if (File.Exists(routePath) && File.Exists(pointsPath) && destinations.Count > 0 && travel.Count > 0)
            report["giving"] = Giving(File.ReadAllBytes(routePath), File.ReadAllBytes(pointsPath),
                                      File.ReadAllBytes(townPath), File.ReadAllBytes(namePath), travel, destinations);
        Directory.CreateDirectory(outFolder);
        var tables = new Dictionary<string, object?>();
        foreach (var (sheet, path, name) in new[] { (Destinations.TownSheet, townPath, "town.nxd"),
                                                     (Destinations.NameSheet, namePath, "placename.nxd") })
        {
            var loaded = File.ReadAllBytes(path);
            string shape = Destinations.ShapeProblem(sheet, loaded, destinations);
            var made = Destinations.WithRows(sheet, loaded, destinations, out string why);
            if (made != null)
            {
                File.WriteAllBytes(Path.Combine(outFolder, name), made);
                // Given twice (a table loaded again is a fresh file; given its own copy, it refuses).
                var again = Destinations.WithRows(sheet, made, destinations, out string againWhy);
                tables[name + " again"] = again == null ? againWhy : "given";
            }
            tables[name] = new Dictionary<string, object?> { ["shape"] = shape, ["why"] = why, ["written"] = made != null };
        }
        report["tables"] = tables;
        File.WriteAllText(reportPath, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
        return 0;
    }

    /// <summary>(1.7.0) The tables' hook (TravelTables) with roads to the mods' places and the places: Route's,
    /// MapRouteTable's, PlaceName's and Town's stand-ins set up in the game's order and again, each step what was said,
    /// the byte the path search reads (the roads offered only once Route, MapRouteTable and Town have their rows),
    /// whether the table was given a new file and whether that file is the rows' as made apart.</summary>
    static unsafe List<object[]> Giving(byte[] route, byte[] points, byte[] town, byte[] names, List<TravelRoad> travel,
                                        List<Destination> destinations)
    {
        var steps = new List<object[]>();
        var said = new List<string>();
        nint ready = (nint)System.Runtime.InteropServices.NativeMemory.AllocZeroed(16);
        var giving = new TravelTables(travel, ready, said.Add, destinations);
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
        void Step(string what, int number, nint file, byte[]? expect)
        {
            said.Clear();
            nint before = *(nint*)(file + TravelTables.FileBytes);
            giving.Give(Sheet(number, file), file);
            nint after = *(nint*)(file + TravelTables.FileBytes);
            long size = *(long*)(file + TravelTables.FileSize);
            bool swapped = after != before;
            bool asExpected = expect == null ? !swapped
                : swapped && size == expect.Length && new ReadOnlySpan<byte>((void*)after, (int)size).SequenceEqual(expect);
            steps.Add(new object[] { what, new List<string>(said), *(byte*)ready, swapped, asExpected });
        }
        var withRoute = Travel.WithRows(Travel.RouteSheet, route, travel, out _);
        var withPoints = Travel.WithRows(Travel.PointsSheet, points, travel, out _);
        var withTown = Destinations.WithRows(Destinations.TownSheet, town, destinations, out _);
        var withNames = Destinations.WithRows(Destinations.NameSheet, names, destinations, out _);
        Step("Route set up", Travel.RouteSheet, FileOf(route), withRoute);
        Step("MapRouteTable set up", Travel.PointsSheet, FileOf(points), withPoints);
        Step("PlaceName set up", Destinations.NameSheet, FileOf(names), withNames);
        nint townFile = FileOf(town);
        Step("Town set up", Destinations.TownSheet, townFile, withTown);
        // Given again: the table's own copy (the helper's, already with the rows) is left alone.
        Step("Town's own copy given again", Destinations.TownSheet, townFile, null);
        Step("Town loaded again from a file with the places' rows already", Destinations.TownSheet,
             FileOf(withTown ?? town), null);
        Step("Town loaded again", Destinations.TownSheet, FileOf(town), withTown);
        return steps;
    }
}
