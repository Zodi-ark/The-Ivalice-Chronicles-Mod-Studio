// Mod Studio's checks of the helper (dev/test_event_setup.py and
// dev/test_side_quests.py run them): the helper's own code finds the table in
// a program's file laid out as the game lays it out in memory, and applies
// mods' EventSetup.json files to a copy, saying what it found, read and
// changed; and (1.1.0) plans mods' side quests over the program and tables as
// the game loads them, saying what it gave, wrote and added. Part of The
// Ivalice Chronicles Mod Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll <program> <report.json> [<mod name>=<EventSetup.json> ...]
//     dotnet Checks.dll --quests <program> <report.json> <tables> <numbers.json> <out> [<mod id>=<folder> ...]
//     dotnet Checks.dll --flags <commands.json> <report.json>
//     dotnet Checks.dll --marker <report.json>       (1.2.5, MarkerChecks.cs)
//     dotnet Checks.dll --places <report.json>       (1.3.0, PlaceChecks.cs)
//     dotnet Checks.dll --looks <report.json>        (1.23.0, LooksChecks.cs)
//     dotnet Checks.dll --roads <report.json> <mod id>=<folder>   (1.4.0, RoadChecks.cs)
//     dotnet Checks.dll --travel <program> <report.json> <route.nxd> <maproutetable.nxd> <out> <block at> <answer at>
//                       <mod id>=<folder> ...                         (1.5.0, TravelChecks.cs)
//     dotnet Checks.dll --nxd <table> <out table> <report.json> <keys>=<hex> ...   (1.5.0, TravelChecks.cs)
//     dotnet Checks.dll --destinations <program> <report.json> <town.nxd> <placename.nxd> <out> <data at> <code at>
//                       <numbers.json or -> <mod id>=<folder> ...   (1.7.0, DestinationChecks.cs)
//     dotnet Checks.dll --event-room <program> <report.json> <at>   (1.9.0, EventRoomChecks.cs)
//     dotnet Checks.dll --quest-maps <program> <report.json> <out> <data at> <code at> <numbers.json or -> ...
//                       [table:<sheet>=<file> ...] <mod id>=<folder> ...   (1.10.0, MapChecks.cs)
//     dotnet Checks.dll --map-file <map.json> <report.json>   (1.10.0, MapChecks.cs)
//     dotnet Checks.dll --numbers <request.json> <report.json>   (1.13.0, NumberChecks.cs)
//     dotnet Checks.dll --squads <request.json> <report.json>   (1.14.0, a deploy area's squad)
//     dotnet Checks.dll --rumors <request.json> <report.json>   (1.15.0, RumorChecks.cs)
//     dotnet Checks.dll --floors <request.json> <report.json>   (1.21.0, a dungeon's floors and battles)
//     dotnet Checks.dll --items <request.json> <report.json>    (1.26.0, ItemChecks.cs)
//     dotnet Checks.dll --ramza <request.json> <report.json>    (1.30.0, the party's Ramza and map 116's name)
//     dotnet Checks.dll --names <request.json> <report.json>    (1.33.0, NameChecks.cs: a unit's own name)
//     dotnet Checks.dll --rewards <request.json> <report.json>  (1.31.0, quests' rewards planned over given records)
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using ModStudioEventSetup;

static class Program
{
    /// <summary>The program's file laid out as in memory: its headers, then each section's
    /// stored bytes at its own address (the rest zero).</summary>
    static byte[] Image(byte[] file)
    {
        int pe = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(0x3C, 4));
        int count = BinaryPrimitives.ReadUInt16LittleEndian(file.AsSpan(pe + 6, 2));
        int optionalSize = BinaryPrimitives.ReadUInt16LittleEndian(file.AsSpan(pe + 20, 2));
        int optional = pe + 24;
        int imageSize = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(optional + 56, 4));
        int headers = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(optional + 60, 4));
        var image = new byte[imageSize];
        file.AsSpan(0, Math.Min(headers, file.Length)).CopyTo(image);
        for (int n = 0; n < count; n++)
        {
            int at = optional + optionalSize + 40 * n;
            int size = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(at + 8, 4));
            int address = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(at + 12, 4));
            int stored = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(at + 16, 4));
            int raw = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(at + 20, 4));
            int length = Math.Min(stored, size == 0 ? stored : size);
            length = Math.Min(length, Math.Min(file.Length - raw, image.Length - address));
            if (length > 0)
                file.AsSpan(raw, length).CopyTo(image.AsSpan(address));
        }
        return image;
    }

    /// <summary>(1.14.0) The quests' squads given a copy of the program laid out as loaded, as the game's loader would
    /// have it (its two pointers relocated to where the copy is), then read back: why not (null when given), whether
    /// both pointers moved to one new place, the game's 768 squads kept there as they are, each quest's squad at its
    /// number, and the copy's squads themselves untouched.</summary>
    static unsafe Dictionary<string, object?> ArmSquads(byte[] image, DeploySquads.Found found,
                                                       List<(int Number, byte[] Bytes)> squads)
    {
        var copy = (byte[])image.Clone();
        var result = new Dictionary<string, object?>();
        fixed (byte* start = copy)
        {
            *(long*)(start + found.First) = (long)(nint)(start + found.Table);
            *(long*)(start + found.Second) = (long)(nint)(start + found.Table);
            result["why"] = DeploySquads.Arm(start, copy.Length, found, squads);
            long first = *(long*)(start + found.First), second = *(long*)(start + found.Second);
            byte* moved = (byte*)first;
            result["moved"] = first == second && first != (long)(nint)(start + found.Table);
            bool kept = true;
            for (int n = 0; n < DeploySquads.GameSquads * DeploySquads.SquadBytes; n++)
                kept &= moved[n] == image[found.Table + n];
            result["gameKept"] = kept;
            bool own = true;
            foreach (var (number, bytes) in squads)
                for (int n = 0; n < DeploySquads.SquadBytes; n++)
                    own &= moved[number * DeploySquads.SquadBytes + n] == bytes[n];
            result["ownAt"] = own;
            bool untouched = true;
            for (int n = 0; n < DeploySquads.GameSquads * DeploySquads.SquadBytes; n++)
                untouched &= copy[found.Table + n] == image[found.Table + n];
            result["untouched"] = untouched;
        }
        return result;
    }

    /// <summary>(1.14.0) Deploy areas' squads as the helper makes them (DeployArea.Squad): the request a list of
    /// {"squares": [[x, y], ...], "upper", "units", "facing" (0 to 3), "number", "map"}, the report each squad's 12
    /// bytes as hex.</summary>
    static int Squads(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var made = new List<string>();
        foreach (var area in request.RootElement.EnumerateArray())
        {
            var squares = new List<(int X, int Y)>();
            foreach (var square in area.GetProperty("squares").EnumerateArray())
                squares.Add((square[0].GetInt32(), square[1].GetInt32()));
            var deploy = new DeployArea(squares, area.GetProperty("upper").GetBoolean(),
                                        area.GetProperty("units").GetInt32(), area.GetProperty("facing").GetInt32());
            made.Add(Convert.ToHexString(deploy.Squad(area.GetProperty("number").GetInt32(),
                                                      area.GetProperty("map").GetInt32())));
        }
        File.WriteAllText(args[2], JsonSerializer.Serialize(made));
        return 0;
    }

    /// <summary>(1.17.0) A mod's battle ground's random battle picked (Framework.GroundPick) for each case given: the
    /// request {"ground": [chance, [[name, battle, map, squad, from], ...]], "cases": [[progress, forced, [random numbers
    /// given in turn]], ...]}; for each, the battle picked (its name, or null) and what each random number was asked
    /// to be under.</summary>
    static int GroundPicks(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var top = request.RootElement;
        var given = top.GetProperty("ground");
        var battles = new List<Framework.GroundBattle>();
        foreach (var b in given[1].EnumerateArray())
            battles.Add(new Framework.GroundBattle(b[0].GetString()!, b[1].GetInt32(), b[2].GetInt32(), b[3].GetInt32(),
                                                   b[4].GetInt32()));
        var place = new MapPlace("m", "M", "f", "Ground", false, 0, 0, "", "");
        var ground = new Framework.GroundPlan(place, 48, given[0].GetInt32(), battles);
        var out_ = new List<object?>();
        foreach (var c in top.GetProperty("cases").EnumerateArray())
        {
            var numbers = new List<int>();
            foreach (var n in c[2].EnumerateArray())
                numbers.Add(n.GetInt32());
            var asked = new List<int>();
            int at = 0;
            // Each number below the bound asked (its remainder), as a random number below it is.
            var picked = Framework.GroundPick(ground, c[0].GetInt32(), c[1].GetBoolean(), n =>
            {
                asked.Add(n);
                return at < numbers.Count ? numbers[at++] % n : 0;
            });
            out_.Add(new object?[] { picked?.Name, asked });
        }
        File.WriteAllText(args[2], JsonSerializer.Serialize(out_));
        return 0;
    }

    /// <summary>(1.21.0) A mod's dungeon's floors listed and a floor's battle picked (Framework.OpenFloors, FloorPick,
    /// Framework.FloorRow) for each case given: the request {"floors": [[name, description, flag, [[name, battle, map,
    /// squad, from], ...]], ...], "cases": [[{flag: value, ...}, progress, floor, [random numbers given in turn]], ...]};
    /// for each, the floors listed (their places), the battle the floor at its place picks (its name, or null) and
    /// what each random number was asked to be under; and each floor's row as hex.</summary>
    static int FloorPicks(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var top = request.RootElement;
        var floors = new List<Framework.DungeonFloor>();
        foreach (var f in top.GetProperty("floors").EnumerateArray())
        {
            var battles = new List<Framework.GroundBattle>();
            foreach (var b in f[3].EnumerateArray())
                battles.Add(new Framework.GroundBattle(b[0].GetString()!, b[1].GetInt32(), b[2].GetInt32(),
                                                       b[3].GetInt32(), b[4].GetInt32()));
            floors.Add(new Framework.DungeonFloor(f[0].GetString()!, f[1].GetString()!, f[2].GetInt32(), battles,
                                                  floors.Count));
        }
        var place = new MapPlace("m", "M", "f", "Dungeon", true, 0, 0, "", "");
        var dungeon = new Framework.DungeonPlan(place, 48, floors);
        var out_ = new List<object?>();
        foreach (var c in top.GetProperty("cases").EnumerateArray())
        {
            var flags = new Dictionary<int, int>();
            foreach (var p in c[0].EnumerateObject())
                flags[int.Parse(p.Name)] = p.Value.GetInt32();
            var listed = Framework.OpenFloors(dungeon, flag => flags.TryGetValue(flag, out int v) ? v : 0);
            var numbers = new List<int>();
            foreach (var n in c[3].EnumerateArray())
                numbers.Add(n.GetInt32());
            var asked = new List<int>();
            int at = 0;
            int index = c[2].GetInt32();
            var picked = index >= 0 && index < floors.Count
                ? Framework.FloorPick(floors[index], c[1].GetInt32(), n =>
                {
                    asked.Add(n);
                    return at < numbers.Count ? numbers[at++] % n : 0;
                })
                : null;
            out_.Add(new object?[] { listed, picked?.Name, asked });
        }
        var report = new Dictionary<string, object?>
        {
            ["cases"] = out_, ["rows"] = floors.ConvertAll(f => Hex(Framework.FloorRow(f))),
            ["entry"] = Framework.FloorEntry, ["variable"] = Framework.FloorVariable,
        };
        // (1.23.0) A mod's dungeon's list's words (the game's, the Deep's name, the dungeon's: Framework.DungeonWords),
        // its About page (its name and words: AboutPage), whether it has one; each place's kind of the location list.
        if (top.TryGetProperty("words", out var words))
        {
            var made = new List<string>();
            foreach (var w in words.EnumerateArray())
                made.Add(Framework.DungeonWords(w[0].GetString()!, w[1].GetString()!, w[2].GetString()!));
            report["words"] = made;
        }
        if (top.TryGetProperty("about", out var about))
        {
            report["about"] = Hex(Framework.AboutPage(about[0].GetString()!, about[1].GetString()!));
            var described = new MapPlace("m", "M", "f", "Dungeon", true, 0, 0, "", "", about[1].GetString()!);
            report["hasAbout"] = new[] { Framework.HasAbout(new Framework.DungeonPlan(described, 48, floors)),
                                         Framework.HasAbout(dungeon) };
        }
        report["pageHead"] = new[] { Framework.PageHead, Framework.PageZeros, Framework.PageBase };
        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }

    /// <summary>(1.18.0) The shops' masks as the helper finds them in the program given (Places.Find: its ShopMasks),
    /// and, for each list of items in the request ([[items], ...]), the masks as the helper borrows them for a mod's
    /// town selling those items (Framework.BorrowMasks) and as it gives them back (GiveBackMasks): {"stock", "masks",
    /// "borrowed": [hex, ...], "back": [hex, ...]}.</summary>
    static int ShopMasks(string[] args)
    {
        var image = Load(args[1]);
        var places = Places.Find(image);
        var report = new Dictionary<string, object?>
        {
            ["stock"] = places.Stock, ["shopMasks"] = places.ShopMasks,
            ["missing"] = places.MissingForTownMenus,
        };
        if (places.TownMenus)
        {
            var masks = image.AsSpan(places.ShopMasks, 2 * Framework.ShopItems);
            report["masks"] = Hex(masks.ToArray());
            var borrowed = new List<string>();
            var back = new List<string>();
            using var request = JsonDocument.Parse(File.ReadAllText(args[2]));
            foreach (var list in request.RootElement.EnumerateArray())
            {
                var items = new List<int>();
                foreach (var item in list.EnumerateArray())
                    items.Add(item.GetInt32());
                var copy = masks.ToArray();
                var kept = new byte[Framework.ShopItems];
                Framework.BorrowMasks(copy, items, kept);
                borrowed.Add(Hex(copy));
                Framework.GiveBackMasks(copy, kept);
                back.Add(Hex(copy));
            }
            report["borrowed"] = borrowed;
            report["back"] = back;
        }
        File.WriteAllText(args[3], JsonSerializer.Serialize(report));
        return 0;
    }

    /// <summary>(1.30.0) The Ramza in each party given (Framework.RamzaOf): the request {"parties": [the party's units
    /// as hex, ...]}, the report {"ramza": [his identity or 0, ...], "chapters": [RamzaChapter of 0 to 4]}; and Map 116's
    /// name as the hook gives it to a map table given ("map": hex): {"named": hex, "why": why not}.</summary>
    static int Ramza(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var found = new List<int>();
        foreach (var party in request.RootElement.GetProperty("parties").EnumerateArray())
            found.Add(Framework.RamzaOf(Convert.FromHexString(party.GetString()!)));
        var report = new Dictionary<string, object?>
        {
            ["ramza"] = found, ["chapters"] = new[] { 0, 1, 2, 3, 4 }.Select(Framework.RamzaChapter).ToList(),
        };
        if (request.RootElement.TryGetProperty("map", out var map))
        {
            var table = Convert.FromHexString(map.GetString()!);
            report["why"] = Framework.NameArena(table);
            report["named"] = Hex(table);
        }
        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }

    /// <summary>(1.31.0) Quests' rewards planned (Framework.Plan) over the event records given ("records": the game's
    /// taken numbers, "free": its slots left), the mods given ("mods": [id, name, folder]) and their items' numbers
    /// ("items": {key: number}): each quest event's number, the events whose scripts have units join, the rewards
    /// (as the --quests report has them) and what is said.</summary>
    static int Rewards(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var root = request.RootElement;
        var records = root.GetProperty("records").EnumerateArray().Select(r => r.GetInt32()).ToList();
        var items = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (var p in root.GetProperty("items").EnumerateObject())
            items[p.Name] = p.Value.GetInt32();
        var quests = new List<Quest>();
        var problems = new List<string>();
        foreach (var mod in root.GetProperty("mods").EnumerateArray())
            quests.AddRange(QuestFile.ReadMod(mod[0].GetString()!, mod[1].GetString()!, mod[2].GetString()!, problems));
        var numbers = Numbers.FromText("", new List<string>());
        var plan = Framework.Plan(records, root.GetProperty("free").GetInt32(), new HashSet<int>(), quests, numbers,
                                  items: items);
        var events = new Dictionary<string, int>();
        foreach (var e in plan.Events)
            events[e.Event.Name] = e.Number;
        var rewards = new Dictionary<string, object>();
        foreach (var (flag, reward) in plan.Rewards)
            rewards[flag.ToString()] = new Dictionary<string, object>
            {
                ["who"] = reward.Who, ["flag"] = reward.Flag, ["gil"] = reward.Gil,
                ["items"] = reward.Items.ConvertAll(i => new object[] { i.Number, i.Count, i.Named }),
                ["words"] = Framework.RewardWords(reward),
            };
        var report = new Dictionary<string, object?>
        {
            ["problems"] = problems, ["events"] = events, ["rewards"] = rewards, ["said"] = plan.Said,
            ["joins"] = plan.Events.FindAll(e => e.Event.Battle == null && Framework.JoinsUnits(e.Event.Script))
                                   .ConvertAll(e => e.Number),
            ["joinsFrom"] = Framework.JoinsFrom,
        };
        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }

    internal static byte[] Load(string path)
    {
        var file = File.ReadAllBytes(path);
        try
        {
            return Image(file);
        }
        catch (Exception e) when (e is ArgumentException || e is IndexOutOfRangeException)
        {
            return file;
        }
    }

    static int Main(string[] args)
    {
        if (args.Length > 0 && args[0] == "--quests")
            return Quests(args);
        if (args.Length > 0 && args[0] == "--flags")
            return Flags(args);
        if (args.Length > 0 && (args[0] == "--marker" || args[0] == "--marker-mods"))
            return MarkerChecks.Run(args);
        if (args.Length > 0 && args[0] == "--places")
            return PlaceChecks.Run(args);
        if (args.Length > 0 && args[0] == "--roads")
            return RoadChecks.Run(args);
        if (args.Length > 0 && args[0] == "--travel")
            return TravelChecks.Run(args);
        if (args.Length > 0 && args[0] == "--destinations")
            return DestinationChecks.Run(args);
        if (args.Length > 0 && args[0] == "--nxd")
            return TravelChecks.RunNxd(args);
        if (args.Length > 0 && args[0] == "--event-room")
            return EventRoomChecks.Run(args);
        if (args.Length > 0 && args[0] == "--quest-maps")
            return MapChecks.Run(args);
        if (args.Length > 0 && args[0] == "--map-file")
            return MapChecks.RunFile(args);
        if (args.Length > 0 && args[0] == "--animations")
            return MapAnimationChecks.Run(args);
        if (args.Length > 0 && args[0] == "--numbers")
            return NumberChecks.Run(args);
        if (args.Length > 0 && args[0] == "--squads")
            return Squads(args);
        if (args.Length > 0 && args[0] == "--rumors")
            return RumorChecks.Run(args);
        if (args.Length > 0 && args[0] == "--ground-picks")
            return GroundPicks(args);
        if (args.Length > 0 && args[0] == "--shop-masks")
            return ShopMasks(args);
        if (args.Length > 0 && args[0] == "--floors")
            return FloorPicks(args);
        if (args.Length > 0 && args[0] == "--looks")
            return LooksChecks.Run(args);
        if (args.Length > 0 && args[0] == "--rewards")
            return Rewards(args);
        if (args.Length > 0 && args[0] == "--ramza")
            return Ramza(args);
        if (args.Length > 0 && args[0] == "--items")
            return ItemChecks.Run(args);
        if (args.Length > 0 && args[0] == "--names")
            return NameChecks.Run(args);
        var image = Load(args[0]);
        var report = new Dictionary<string, object?>();
        var table = Finder.Find(image, out string why);
        report["why"] = why;
        report["found"] = table == null ? null : new Dictionary<string, object>
        {
            ["address"] = table.Address,
            ["how"] = table.How,
            ["events"] = table.SlotOf.Count,
            ["slots"] = table.Slots,
        };
        var copy = (byte[])image.Clone();
        var applier = new Applier();
        var mods = new List<object>();
        for (int n = 2; n < args.Length; n++)
        {
            int split = args[n].IndexOf('=');
            string name = args[n].Substring(0, split);
            var problems = new List<string>();
            var changes = SetupFile.Read(File.ReadAllText(args[n].Substring(split + 1)), problems);
            var said = table == null
                ? new List<string>()
                : applier.Apply(copy.AsSpan(table.Address, table.Bytes), table, name, changes);
            var asked = new List<object>();
            foreach (var change in changes)
                asked.Add(new object[] { change.Event, change.Field.Key, change.Value });
            mods.Add(new Dictionary<string, object> { ["name"] = name, ["changes"] = asked, ["problems"] = problems, ["said"] = said });
        }
        report["mods"] = mods;
        var changed = new List<int[]>();
        for (int at = 0; at < image.Length; at++)
            if (image[at] != copy[at])
                changed.Add(new[] { at, image[at], copy[at] });
        report["changed"] = changed;
        var fields = new List<object>();
        foreach (var field in Fields.All)
            fields.Add(new object[] { field.Key, field.At, field.Size, field.Mask, field.Most });
        report["fields"] = fields;
        File.WriteAllText(args[1], JsonSerializer.Serialize(report));
        return 0;
    }

    static string Hex(byte[] bytes) => Convert.ToHexString(bytes);

    /// <summary>The tables the side quests add rows to, by their file names as the game keeps them.</summary>
    static readonly (int Sheet, string File)[] Tables =
    {
        (Framework.WorldStarts, "enhancedworldevent.nxd"), (Framework.Rules, "enhancedbattleevent.nxd"),
        (Framework.Scenes, "scenarioid.nxd"), (Framework.Texts, "scionfiles.nxd"),
        (Framework.EntryRows, "entryno.nxd"), (Framework.Prompts, "sortieconfirm.nxd"),
        (Framework.Objectives, "battleobjective.en.nxd"), (Framework.Rumors, "gossip.en.nxd"),
        // (1.30.0) Map 116's name's row.
        (Framework.NameSheet, "placename.en.nxd"),
    };

    /// <summary>The side quests of the mods given (in their order) planned over the program, the
    /// numbers file read and written as the helper keeps it, the records written into a copy
    /// of the setup table, and the tables in the tables folder given their rows (written to
    /// the out folder under the same names).</summary>
    static int Quests(string[] args)
    {
        var image = Load(args[1]);
        string reportPath = args[2], tables = args[3], numbersPath = args[4], output = args[5];
        Directory.CreateDirectory(output);
        var report = new Dictionary<string, object?>();
        var places = Places.Find(image);
        report["places"] = new Dictionary<string, object>
        {
            ["SheetInit"] = places.SheetInit, ["ScriptReader"] = places.ScriptReader, ["ScriptMode"] = places.ScriptMode,
            ["EventVariables"] = places.EventVariables, ["WorldVariables"] = places.WorldVariables,
            ["EventBank"] = places.EventBank, ["WorldBank"] = places.WorldBank, ["Missing"] = places.Missing,
            ["Encounter"] = places.Encounter, ["EncounterNumber"] = places.EncounterNumber,
            ["MissingForBattles"] = places.MissingForBattles, ["Progress"] = places.Progress,
            ["TravelCheck"] = places.TravelCheck, ["PendingEvent"] = places.PendingEvent,
            ["MissingForTravel"] = places.MissingForTravel, ["TravelFlags"] = places.TravelFlags,
            ["TravelDone"] = places.TravelDone, ["TravelLegs"] = places.TravelLegs,
            ["MissingForPassing"] = places.MissingForPassing, ["PartyTest"] = places.PartyTest,
            ["Party"] = places.Party, ["PartyMode"] = places.PartyMode, ["MarkerState"] = places.MarkerState,
            ["ChildPiece"] = places.ChildPiece, ["BoxNamed"] = places.BoxNamed, ["PartsReady"] = places.PartsReady,
            ["StringMake"] = places.StringMake, ["StringAssign"] = places.StringAssign,
            ["StringRelease"] = places.StringRelease, ["StringPool"] = places.StringPool,
            ["MissingForMarkers"] = places.MissingForMarkers, ["MapSetup"] = places.MapSetup,
            ["PieceCopy"] = places.PieceCopy, ["PieceMove"] = places.PieceMove, ["PieceAdd"] = places.PieceAdd,
            ["AnimationPlay"] = places.AnimationPlay, ["AnimationsStop"] = places.AnimationsStop,
            // (1.20.0) One animation stopped by its name (a darkened town's other colour first).
            ["AnimationStop"] = places.AnimationStop,
            ["MissingForPlaces"] = places.MissingForPlaces, ["BoxSize"] = places.BoxSize,
            ["MissingForRoads"] = places.MissingForRoads,
            // (1.15.0) The taverns' rumors' sites.
            ["RumorTest"] = places.RumorTest, ["RumorsRead"] = places.RumorsRead, ["RumorKeys"] = places.RumorKeys,
            ["RumorAgent"] = places.RumorAgent,
            ["MissingForRumors"] = places.MissingForRumors,
            // (1.18.0) The mods' towns' menus' sites: the Outfitter's stock and the shops' masks.
            ["Stock"] = places.Stock, ["ShopMasks"] = places.ShopMasks,
            ["MissingForTownMenus"] = places.MissingForTownMenus, ["TownMenus"] = places.TownMenus,
            // (1.19.0) A town's own art and picture in its menu: the base art's path, the menu's town
            // picture, the UI's root.
            ["BaseArt"] = places.BaseArt, ["MenuIcon"] = places.MenuIcon, ["UiRoot"] = places.UiRoot,
            ["MissingForMenuArt"] = places.MissingForMenuArt, ["MenuArt"] = places.MenuArt,
            // (1.21.0) A mod's dungeon: the entries' function, the menu's three tests of the Deep and its list's copy,
            // the floor chosen's ask of the chains and way out, the random battle's setup, the list's two reads of a
            // floor's row and the row lookup, the place the menu is opened at.
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
            // (1.23.1) The location list's kinds of a town's shop: the items' list and the item's data.
            ["ListItems"] = places.ListItems, ["ListItem"] = places.ListItem,
            ["Locations"] = places.Locations, ["UiText"] = places.UiText, ["TwoKeyRow"] = places.TwoKeyRow,
            ["GuideShow"] = places.GuideShow, ["DeepGuide"] = places.DeepGuide, ["AboutOpen"] = places.AboutOpen,
            ["AboutGuide"] = places.AboutGuide, ["PlaceNameText"] = places.PlaceNameText,
            ["ArtSetter"] = places.ArtSetter, ["TextRemake"] = places.TextRemake,
            ["MissingForDungeonLooks"] = places.MissingForDungeonLooks, ["DungeonLooks"] = places.DungeonLooks,
            // (1.25.0) A quest's start waiting at a dungeon's floor: the world map's start of an event loaded, the event
            // it loads and its kind, the queue's count it reads.
            ["EventStart"] = places.EventStart, ["LoadedEvent"] = places.LoadedEvent, ["LoadedKind"] = places.LoadedKind,
            ["QueueCount"] = places.QueueCount, ["MissingForFloorStarts"] = places.MissingForFloorStarts,
            ["FloorStarts"] = places.FloorStarts,
            // (1.31.0) A quest's reward: the game's giving of an event's item and its add to the war funds.
            ["ItemGive"] = places.ItemGive, ["WarFundsAdd"] = places.WarFundsAdd,
            ["MissingForRewards"] = places.MissingForRewards, ["Rewards"] = places.Rewards,
            // (1.33.0) A quest's unit's own name: the game's making of a battle's unit from its battle file's entry.
            ["UnitMade"] = places.UnitMade, ["MissingForNames"] = places.MissingForNames, ["Names"] = places.Names,
            // (1.34.0) A mod's road shown and grayed with its places: the game's test of a place shown, the Town row's
            // lookup and the situation's test the screen grays a place by.
            ["PlaceTest"] = places.PlaceTest, ["TownRow"] = places.TownRow, ["Situation"] = places.Situation,
            ["MissingForRoadLooks"] = places.MissingForRoadLooks, ["RoadLooks"] = places.RoadLooks,
            // (1.35.0) A save's old items: the game's load of a save, the variables and the party it fills.
            ["SaveLoad"] = places.SaveLoad, ["SaveBank"] = places.SaveBank, ["Roster"] = places.Roster,
            ["MissingForRoster"] = places.MissingForRoster,
        };
        // What the helper goes by: every quest's places, a battle's, the travel check's, (1.2.4) the travel's
        // state's, (1.2.5) the markers', (1.3.0) the mods' own places', (1.4.0) their roads'.
        report["placesFound"] = new[] { places.All, places.Battles, places.Travel, places.Passing, places.Markers,
                                        places.NewPlaces, places.NewRoads };
        // (1.17.0) Where the random battles' roll keeps its choice, which a mod's battle ground's own battles set.
        report["groundPlaces"] = new Dictionary<string, object>
        {
            ["RandomSquad"] = places.RandomSquad, ["RandomBattle"] = places.RandomBattle,
            ["RandomMap"] = places.RandomMap, ["MissingForGroundBattles"] = places.MissingForGroundBattles,
            ["GroundBattles"] = places.GroundBattles, ["RoadBattles"] = places.RoadBattles,
        };
        // (1.2.3) The travel check's stand-in as the helper makes it, for an address of the game's
        // check kept at 0x10000000 and C# asked at 0x10002000 (dev/test_side_quests.py runs it).
        report["travelStandIn"] = Hex(Thunks.TravelCheck(0x10000000, 0x10002000));
        report["registersKept"] = Thunks.Kept;
        var table = Finder.Find(image, out string why);
        report["why"] = why;
        var problems = new List<string>();
        var quests = new List<Quest>();
        var otherScripts = new HashSet<int>();
        var placeProblems = new List<string>();
        var mapPlaces = new List<MapPlace>();
        var roadProblems = new List<string>();
        var mapRoads = new List<MapRoad>();
        // (1.10.0) The mods' quest maps, which an event's setup may name.
        var questMaps = new List<QuestMap>();
        var mapProblems = new List<string>();
        // (1.26.0) The mods' own items, which a town's Outfitter may sell.
        var modItems = new List<ModItem>();
        var itemProblems = new List<string>();
        // (1.22.0) A mod given as "id|name=folder" has that name, else its id; each named in the log as the helper
        // names it (Framework.LogName: with its id beside it when another mod given has its name).
        var modsGiven = new List<(string Id, string Name, string Folder)>();
        for (int n = 6; n < args.Length; n++)
        {
            int split = args[n].IndexOf('=');
            string modId = args[n].Substring(0, split), modFolder = args[n].Substring(split + 1), modName = modId;
            int bar = modId.IndexOf('|');
            if (bar >= 0)
            {
                modName = modId.Substring(bar + 1);
                modId = modId.Substring(0, bar);
            }
            modsGiven.Add((modId, modName, modFolder));
        }
        var modsLoaded = modsGiven.ConvertAll(g => (g.Id, g.Name));
        foreach (var modGiven in modsGiven)
        {
            string id = modGiven.Id, folder = modGiven.Folder;
            string name = Framework.LogName(id, modGiven.Name, modsLoaded);
            var own = PlaceFile.ReadMod(id, name, folder, placeProblems);
            questMaps.AddRange(MapFile.ReadMod(id, name, folder, mapProblems));
            // (1.8.0) A start may name one of its mod's own places; (1.10.0) a setup one of its quest maps.
            quests.AddRange(QuestFile.ReadMod(id, name, folder, problems, own.ConvertAll(p => p.Name),
                                              MapFile.NamesIn(folder)));
            QuestFile.ScriptNumbers(folder, otherScripts);
            mapPlaces.AddRange(own);
            mapRoads.AddRange(RoadFile.ReadMod(id, name, folder, own.ConvertAll(p => p.Name), roadProblems));
            modItems.AddRange(ItemFile.ReadMod(id, name, folder, itemProblems));
        }
        report["otherScripts"] = otherScripts;
        report["problems"] = problems;
        // (1.8.0) Each start as the reader gives it: its place (-1 for one of its mod's own, by name) and that name.
        report["readStarts"] = quests.ConvertAll(q => q.Starts.ConvertAll(s => new object[] { s.Place, s.PlaceName }));
        // (1.3.0) The mods' own places as the helper reads them; (1.16.0) each one's description.
        report["mapPlaces"] = mapPlaces.ConvertAll(p => new object[]
        {
            p.ModId, p.Folder, p.Name, p.Town, p.X, p.Y, p.Picture, p.Icon, p.Parts, p.Description,
        });
        // (1.18.0) Each town's menu of its own as the helper reads it: its folder, the game's town whose art it shows,
        // its Outfitter's items, its Poachers' Den.
        report["placeMenus"] = mapPlaces.FindAll(p => p.Menu != null).ConvertAll(p => new object[]
        {
            p.Folder, p.Menu!.ArtPicture.Length > 0 ? p.Menu.ArtPicture : p.Menu.Art, p.Menu.Shop, p.Menu.Poachers,
            // (1.26.0) Its own items, by their names.
            p.Menu.OwnItems,
        });
        // (1.20.0) Each town's Darkened as the helper reads it: its folder, the quest and its flag.
        report["placeDarkened"] = mapPlaces.FindAll(p => p.Darkened != null).ConvertAll(p => new object[]
        {
            p.Folder, p.Darkened!.Quest, p.Darkened.Flag,
        });
        report["placeProblems"] = placeProblems;
        // (1.21.0) Each dungeon's floors as the helper reads them: its folder, and each floor (its name, its words, the
        // quest and flag it waits for, its battles' names; 1.24.0, whether it waits for the floor before it won).
        report["placeFloors"] = mapPlaces.FindAll(p => p.Dungeon).ConvertAll(p => new object[]
        {
            p.Folder, p.Floors.ConvertAll(f => new object?[]
            {
                f.Name, f.Description, f.Opens?.Quest, f.Opens?.Flag, f.Battles.ConvertAll(b => b.Name), f.AfterWin,
            }),
        });
        // (1.23.0) Each dungeon's art as the helper reads it: its folder, the game's place or its own art's files' name;
        // and each place's kind of the world map's location list (its folder, Destinations.KindOf).
        report["placeArt"] = mapPlaces.FindAll(p => p.Dungeon).ConvertAll(p => new object[]
        {
            p.Folder, p.DungeonArtPicture.Length > 0 ? p.DungeonArtPicture : p.DungeonArt,
        });
        report["placeKinds"] = mapPlaces.ConvertAll(p => new object[] { p.Folder, Destinations.KindOf(p) });
        // (1.17.0) Each battle ground's own random battles as the helper reads them: its folder, how many of 100
        // arrivals start one, and each battle (its name, its units in hex or the game's battle, its map or quest map,
        // its deploy area's squares, units, facing and level, the story's progress it waits for).
        report["placeBattles"] = mapPlaces.FindAll(p => p.Battles.Count > 0).ConvertAll(p => new object[]
        {
            p.Folder, p.Chance, p.Battles.ConvertAll(b => new object[]
            {
                b.Name, b.Units == null ? "" : Hex(b.Units), b.GameUnits, b.Map, b.MapName,
                b.Deploy.ConvertAll(a => new object[]
                {
                    a.Squares.ConvertAll(q => new[] { q.X, q.Y }), a.Units, a.Facing, a.Upper,
                }),
                b.From,
            }),
        });
        // (1.4.0) The mods' own roads as the helper reads them; (1.5.0) each one's walk, and whether it joins two of
        // the game's places with one (travelled).
        report["mapRoads"] = mapRoads.ConvertAll(r => new object[]
        {
            r.ModId, r.Folder, r.Name, r.FromPlace, r.FromName, r.ToPlace, r.ToName,
            r.Via.ConvertAll(v => new[] { v.X, v.Y }), r.Picture, r.X, r.Y, r.Width, r.Height, r.Parts,
            r.Walk.ConvertAll(v => new[] { v.X, v.Y }), r.BetweenGamePlaces,
        });
        report["roadProblems"] = roadProblems;
        var read = new List<string>();
        var numbers = Numbers.FromText(File.Exists(numbersPath) ? File.ReadAllText(numbersPath) : "", read);
        report["numbersRead"] = read;
        // (1.26.0) The mods' items planned as the helper plans them first (Mod.PlanItems), its lines in its order: each
        // problem, the plan's, the room made (his program's, no other mod's: the game's 85 bonus rows the last given),
        // each item's; their numbers given the towns' menus.
        var itemNumbers = new Dictionary<string, int>(StringComparer.Ordinal);
        var itemsSaid = new List<string>();
        foreach (var problem in itemProblems)
            itemsSaid.Add($"{problem}; the item is left out.");
        var itemsGiven = new List<ItemRoom.Given>();
        if (modItems.Count > 0)
        {
            var itemsFound = ItemRoom.Find(image, Finder.Sections(image));
            report["itemsMissing"] = itemsFound.Missing;
            if (itemsFound.Ok)
            {
                itemsGiven = ItemRoom.Plan(modItems, numbers, ItemRoom.GameRows, itemsSaid);
                // (1.27.0) The game's towns' Outfitters, as ItemHooks.Arm finds the stock's calls for them (said as it
                // arms, before the room's line): each item's towns said after its own line (Mod.PlanItems), or that
                // none is sold there.
                bool atGameTowns = ItemRoom.TownItems(itemsGiven).Count > 0;
                if (atGameTowns)
                {
                    var calls = places.Stock >= 0
                        ? Places.StockCalls(new ReadOnlySpan<byte>(image, places.Stock, Places.StockSortAt + 5),
                                            places.Stock)
                        : (0, 0, 0);
                    report["stockCalls"] = new[] { calls.Item1, calls.Item2, calls.Item3 };
                    if (calls.Item1 == 0)
                    {
                        itemsSaid.Add("the mods' items aren't sold at the game's own Outfitters: "
                                      + (places.Stock < 0 ? "the Outfitter's stock wasn't found"
                                                          : "the stock's calls aren't where they were")
                                      + ". A game update may have changed it: look for a newer Mod Studio Framework.");
                        atGameTowns = false;
                    }
                }
                if (itemsGiven.Count > 0)
                    itemsSaid.Add(itemsFound.Moved
                        ? $"the game's items have room for the mods' items, past WotL Restoration's: {ItemRoom.FirstItem} "
                          + $"to {ItemRoom.LastItem}."
                        : $"the game's items have room for the mods' items: {ItemRoom.FirstItem} to {ItemRoom.LastItem}.");
                foreach (var g in itemsGiven)
                {
                    itemNumbers[g.Item.Key] = g.Number;
                    itemsSaid.Add(ItemRoom.Line(g));
                    if (atGameTowns && g.Item.Shops.Length > 0)
                        itemsSaid.Add(ItemRoom.ShopsLine(g));
                }
                report["townItems"] = ItemRoom.TownItems(itemsGiven);
            }
        }
        report["itemsSaid"] = itemsSaid;
        report["itemNumbers"] = itemNumbers;
        report["itemProblems"] = itemProblems;
        // Each item's Item row added to the loaded Item table (the tables' item.en.nxd), as the helper adds them.
        string itemTable = Path.Combine(tables, "item.en.nxd");
        if (itemsGiven.Count > 0 && File.Exists(itemTable))
        {
            var rowsSaid = new List<string>();
            var withRows = ItemRoom.WithItemRows(File.ReadAllBytes(itemTable), itemsGiven, rowsSaid, out string rowsWhy);
            if (withRows != null)
                rowsSaid.Add($"Item: the mods' items' {itemsGiven.Count} row{(itemsGiven.Count == 1 ? "" : "s")} added.");
            else
                rowsSaid.Add($"Item gets no rows: {rowsWhy}.");
            report["itemRowsSaid"] = rowsSaid;
        }
        if (table == null)
        {
            File.WriteAllText(reportPath, JsonSerializer.Serialize(report));
            return 0;
        }
        // (1.9.0) With MOD_STUDIO_EVENT_ROOM set, as the helper plans once the tables are moved (EventRoom.cs): the
        // setup table a copy with room for 8192 events, its game's slots as his program has them, numbers to 8191.
        bool room = Environment.GetEnvironmentVariable("MOD_STUDIO_EVENT_ROOM") == "1";
        var moved = new byte[EventRoom.SetupBytes];
        image.AsSpan(table.Address, table.Bytes).CopyTo(moved);
        var setup = room ? moved.AsSpan() : image.AsSpan(table.Address, table.Bytes);
        int first = Framework.FirstEmpty(setup, room ? EventRoom.Events : table.Slots, out int free,
                                         room ? EventRoom.Events : Framework.SearchedSlots);
        report["room"] = room;
        report["firstEmpty"] = first;
        report["free"] = free;
        // (1.8.0) When a start names one of its mod's places: the places numbered as the helper numbers them
        // (Destinations.Plan, kept in the numbers file), each taken as given to the game, before the quests.
        var placeNumbers = new Dictionary<string, int>(StringComparer.Ordinal);
        // (1.17.0) And when a battle ground has random battles of its own: each numbered first, as the game gives them;
        // (1.18.0) and when a town has a menu of its own (a rumor may name it).
        var grounds = new List<(MapPlace Place, int Number)>();
        var towns = new List<(MapPlace Place, int Number)>();
        // (1.21.0) And when a mod has a dungeon.
        var dungeons = new List<(MapPlace Place, int Number)>();
        if ((quests.Exists(q => q.Starts.Exists(s => s.PlaceName.Length > 0))
             || mapPlaces.Exists(p => !p.Town && p.Battles.Count > 0)
             || mapPlaces.Exists(p => p.Town && p.Menu != null) || mapPlaces.Exists(p => p.Dungeon))
            && places.Destinations)
        {
            var placesSaid = new List<string>();
            foreach (var d in Destinations.Plan(mapPlaces, numbers, placesSaid))
            {
                placeNumbers[$"{d.Place.ModId}/{d.Place.Name}"] = d.Number;
                if (!d.Place.Town && d.Place.Battles.Count > 0)
                    grounds.Add((d.Place, d.Number));
                if (d.Place.Town && d.Place.Menu != null)
                    towns.Add((d.Place, d.Number));
                if (d.Place.Dungeon)
                    dungeons.Add((d.Place, d.Number));
            }
            report["placesSaid"] = placesSaid;
        }
        report["placeNumbers"] = placeNumbers;
        // (1.10.0) The quest maps numbered as the helper numbers them (MapRoom.Plan), before the quests.
        var mapNumbers = new Dictionary<string, int>(StringComparer.Ordinal);
        var mapBases = new Dictionary<int, int>();
        if (questMaps.Count > 0)
        {
            var mapsSaid = new List<string>();
            var mapSites = MapRoom.Find(image, Finder.Sections(image), out _);
            foreach (var g in MapRoom.Plan(questMaps, numbers, image, mapSites, mapsSaid))
            {
                mapNumbers[g.Map.Key] = g.Number;
                mapBases[g.Number] = g.Map.Base;
            }
            report["mapsSaid"] = mapsSaid;
        }
        report["mapProblems"] = mapProblems;
        report["mapNumbers"] = mapNumbers;
        // (1.14.0) The quests' own deploy areas: the program's squads and their two pointers found as the helper finds
        // them (the file's pointers hold its preferred base plus the squads' place), the plan's squads given them.
        long preferred = BinaryPrimitives.ReadInt64LittleEndian(
            image.AsSpan(BinaryPrimitives.ReadInt32LittleEndian(image.AsSpan(0x3C, 4)) + 24 + 24, 8));
        var squadsFound = DeploySquads.Find(image, preferred, out string squadsWhy);
        report["squadsFound"] = squadsFound == null ? null
            : new[] { squadsFound.Value.Table, squadsFound.Value.First, squadsFound.Value.Second };
        report["squadsWhy"] = squadsWhy;
        // (1.20.0) The mods' towns darkened once a quest's flag is set (each shown, as the helper's places' hook
        // shows them).
        var darkPlaces = mapPlaces.FindAll(p => p.Town && p.Darkened != null);
        var plan = Framework.Plan(table.SlotOf.Keys, free, otherScripts, quests, numbers, placeNumbers,
                                  room ? EventRoom.LastEvent : Framework.LastEvent, mapNumbers, mapBases,
                                  squadsFound != null, places.Rumors, squadsFound != null ? grounds : null,
                                  places.Battles, towns, darkPlaces, squadsFound != null ? dungeons : null,
                                  places.FloorStarts, itemNumbers);
        report["squads"] = plan.Squads.ConvertAll(s => new object[] { s.Number, Convert.ToHexString(s.Bytes) });
        // (1.17.0) The battle grounds as planned: each its place's number, how many of 100 arrivals start one, and its
        // battles (its name, its battle's number, its map's, its deploy area's squad, the story's progress it waits
        // for); and the battles' numbers kept by GroundKey.
        var groundsPlanned = new List<object>();
        foreach (var (number, ground) in plan.Grounds)
            groundsPlanned.Add(new object[]
            {
                number, ground.Chance, ground.Battles.ConvertAll(b => new object[] { b.Name, b.Battle, b.Map, b.Squad, b.From }),
            });
        report["grounds"] = groundsPlanned;
        // (1.21.0) The dungeons as planned: each its place's number and its floors (each its name, its place in the
        // list, the flag it waits for, its battles as a battle ground's, its row as the Deep's list reads it; 1.24.0,
        // the floor whose win it waits for, its own won flag and the floor that lists).
        var dungeonsPlanned = new List<object>();
        // (1.24.0) The floor won as the battle won event starts (Framework.WonFloor): at each floor chosen (its place in
        // the list, then one past them), each battle of the dungeon's and one of none: [floor, battle, the floor won].
        var dungeonWins = new List<object>();
        foreach (var (number, dungeon) in plan.Dungeons)
        {
            dungeonsPlanned.Add(new object[]
            {
                number, dungeon.Floors.ConvertAll(f => new object[]
                {
                    f.Name, f.Index, f.Flag,
                    f.Battles.ConvertAll(b => new object[] { b.Name, b.Battle, b.Map, b.Squad, b.From }),
                    Hex(Framework.FloorRow(f)), f.After, f.WonFlag, f.WonLists,
                }),
            });
            var fought = new List<int>();
            foreach (var f in dungeon.Floors)
                fought.AddRange(f.Battles.ConvertAll(b => b.Battle));
            fought.Add(-1);
            for (int index = 0; index <= dungeon.Floors.Count; index++)
                foreach (int battle in fought)
                    dungeonWins.Add(new object?[] { number, index, battle, Framework.WonFloor(dungeon, index, battle)?.Name });
        }
        report["dungeons"] = dungeonsPlanned;
        report["dungeonWins"] = dungeonWins;
        // (1.25.0) The quests' starts waiting at the dungeons' floors as planned: each its quest, the dungeon's number,
        // the floor's name and place, the event it loads, the event's name, its battle's won event, and its steps; and
        // the floor won as each of the plan's won events starts (Framework.FirstWonFloor), at each floor chosen (its
        // place in the list, then one past them), and one of no start's: [dungeon, floor, won event, the floor won,
        // whether it is a first's won event].
        report["floorStarts"] = plan.FloorStarts.ConvertAll(f => new object[]
        {
            f.Quest.Name, f.Place, f.Floor, f.Index, f.Event, f.Name, f.Won, f.Steps.ConvertAll(Hex),
        });
        var firstWins = new List<object>();
        foreach (var (number, dungeon) in plan.Dungeons)
        {
            var wonEvents = plan.FloorStarts.ConvertAll(f => f.Won);
            wonEvents.Add(Framework.BattleWonEvent);
            for (int index = 0; index <= dungeon.Floors.Count; index++)
                foreach (int won in wonEvents)
                    firstWins.Add(new object?[]
                    {
                        number, index, won, Framework.FirstWonFloor(dungeon, index, won)?.Name, plan.IsFirstWon(won),
                    });
        }
        report["firstWins"] = firstWins;
        // (1.25.0) At each floor with starts waiting there, the first whose conditions hold (Framework.FirstHolding) and
        // the quest whose marker the dungeon shows (Framework.MarkedAt), every variable 0 (a step not done yet), then
        // every variable 1 (done): [dungeon, floor, the start held, then not, the marker's quest, then not].
        var firstHolding = new List<object>();
        foreach (var (number, dungeon) in plan.Dungeons)
            foreach (var f in dungeon.Floors)
                if (f.Firsts.Count > 0)
                    firstHolding.Add(new object?[]
                    {
                        number, f.Index, Framework.FirstHolding(f, _ => 0, _ => false)?.Name,
                        Framework.FirstHolding(f, _ => 1, _ => false)?.Name,
                        plan.MarkedAt(number, _ => 0, _ => false)?.Name, plan.MarkedAt(number, _ => 1, _ => false)?.Name,
                    });
        report["firstHolding"] = firstHolding;
        // (1.25.1) A floor's win given in one battle (Framework.FloorWins): twice at one floor, then at another floor of
        // the dungeon, at a floor of another dungeon; a floor chosen; then twice at the first again: whether each is the
        // first in its battle.
        var wins = new Framework.FloorWins();
        var floorWins = new List<bool> { wins.First(69, 2), wins.First(69, 2), wins.First(69, 3), wins.First(70, 2) };
        wins.Chosen();
        floorWins.Add(wins.First(69, 2));
        floorWins.Add(wins.First(69, 2));
        report["floorWins"] = floorWins;
        report["battleWon"] = new[] { Framework.BattleWonEvent, Framework.CurrentBattle, Framework.FloorVariable,
                                     Framework.AddCommand, Framework.CurrentEvent };
        // (1.17.0) Their deploy prompts: each its key, its battle's map and whose; and the key each battle's EntryNo
        // row names, by its battle's number.
        report["groundPrompts"] = plan.GroundPrompts.ConvertAll(g => new object[] { g.Key, g.Map, g.Who });
        report["entryPrompts"] = plan.EntryPrompts;
        // (1.15.0) The quests' rumors as planned: each its key, towns' mask, read flag and When's steps (as the hooks
        // tell them: RumorChecks.cs).
        report["rumors"] = plan.RumorPlans.ConvertAll(r => new object[]
        {
            r.Key, r.Mask, r.Flag, r.Steps.ConvertAll(Hex), new SortedSet<int>(r.ModTowns),
        });
        // (1.18.0) The mods' towns with a menu of their own as planned: each its place's number, the game's town whose
        // art it shows, its Outfitter's items, its Poachers' Den.
        var menuTowns = new List<object>();
        foreach (var t in plan.MenuTowns.Values)
            menuTowns.Add(new object[]
            {
                t.Number, t.Menu.ArtPicture.Length > 0 ? t.Menu.ArtPicture : t.Menu.Art, t.Menu.Shop, t.Menu.Poachers,
                // (1.26.0) Its own items' numbers, as numbered.
                t.OwnItems,
            });
        report["menuTowns"] = menuTowns;
        // (1.20.0) The mods' towns darkened once a quest's flag is set as planned: each its name and the flag's number.
        report["darkPlaces"] = plan.DarkPlaces.ConvertAll(d => new object[] { d.Place.Name, d.Flag });
        if (squadsFound != null && plan.Squads.Count > 0)
            report["squadsArmed"] = ArmSquads(image, squadsFound.Value, plan.Squads);
        int written = plan.WriteRecords(setup, first);
        report["written"] = written;
        var records = new List<object>();
        for (int slot = first; slot < first + written; slot++)
            records.Add(new object[] { slot, Hex(setup.Slice(slot * Table.RecordBytes, Table.RecordBytes).ToArray()) });
        report["records"] = records;
        report["said"] = plan.Said;
        var events = new List<object>();
        foreach (var p in plan.Events)
            events.Add(new Dictionary<string, object>
            {
                ["quest"] = p.Quest.Key, ["name"] = p.Event.Name, ["number"] = p.Number, ["scene"] = p.Scene,
                ["text"] = p.Text, ["script"] = Hex(p.Script), ["from"] = p.Event.From,
            });
        report["events"] = events;
        report["flags"] = plan.Flags;
        // (1.9.0) What the log calls each event and each flag given, kept apart: an event's number may now be a
        // flag's (both from 4096).
        var eventNames = new Dictionary<string, string>();
        foreach (var p in plan.Events)
            eventNames[p.Number.ToString()] = plan.NameOf(p.Number);
        foreach (var (opening, _) in plan.Openings)
            eventNames[opening.ToString()] = plan.NameOf(opening);
        report["eventNames"] = eventNames;
        var flagNames = new Dictionary<string, string>();
        foreach (int flag in plan.Flags.Values)
            flagNames[flag.ToString()] = plan.FlagNameOf(flag);
        report["flagNames"] = flagNames;
        var scripts = new Dictionary<string, string>();
        foreach (var ev in plan.Scripts.Keys)
            scripts[ev.ToString()] = Hex(plan.ScriptFor(ev)!);
        report["scripts"] = scripts;
        // (1.30.0) Where each script names Ramza, and each such script as handed over with each of his identities
        // (1 to 3, and 0 and 4, which aren't his: the script as written).
        var ramzaPlaces = new Dictionary<string, int[]>();
        var ramzaScripts = new Dictionary<string, List<string>>();
        foreach (var (ev, ramzaAt) in plan.RamzaPlaces)
        {
            ramzaPlaces[ev.ToString()] = ramzaAt;
            ramzaScripts[ev.ToString()] = new List<string>();
            for (int ramza = 0; ramza <= 4; ramza++)
                ramzaScripts[ev.ToString()].Add(Hex(plan.ScriptFor(ev, ramza)!));
        }
        report["ramzaPlaces"] = ramzaPlaces;
        report["ramzaScripts"] = ramzaScripts;
        report["namesRamza"] = plan.Events.ConvertAll(e => new object[] { e.Number, plan.NamesRamza(e.Number) });
        // (1.30.0) Who plays or fights on map 116, which the helper then names.
        report["arenaUsers"] = plan.ArenaUsers;
        report["namesArena"] = plan.NamesArena;
        // (1.31.0) Each quest's reward by its flag's number: whose, its flag, gil, items (number, count, named), its
        // words, and whether it is given as its flag goes from 0 to 1, stays 1, goes from 1 to 0, stays 0.
        var rewards = new Dictionary<string, object>();
        foreach (var (flag, reward) in plan.Rewards)
            rewards[flag.ToString()] = new Dictionary<string, object>
            {
                ["who"] = reward.Who, ["flag"] = reward.Flag, ["gil"] = reward.Gil,
                ["items"] = reward.Items.ConvertAll(i => new object[] { i.Number, i.Count, i.Named }),
                ["words"] = Framework.RewardWords(reward),
                ["given"] = new[] { plan.RewardGiven(flag, 0, 1) != null, plan.RewardGiven(flag, 1, 1) != null,
                                    plan.RewardGiven(flag, 1, 0) != null, plan.RewardGiven(flag, 0, 0) != null },
            };
        report["rewards"] = rewards;
        // (1.31.0) The quests' events whose scripts have units join the party (numbered from Framework.JoinsFrom).
        report["joins"] = plan.Events.FindAll(e => e.Event.Battle == null && Framework.JoinsUnits(e.Event.Script))
                                     .ConvertAll(e => e.Number);
        // (1.33.0) The quests' battles' units' own names, by the battle's number and the unit's place (1 to 16).
        var ownNames = new Dictionary<string, object>();
        foreach (var (number, names) in plan.OwnNames)
        {
            var named = new Dictionary<string, string>();
            foreach (var (slot, name) in names)
                named[(slot + 1).ToString()] = name;
            ownNames[number.ToString()] = named;
        }
        report["ownNames"] = ownNames;
        var rules = new Dictionary<string, object>();
        foreach (var (key, (quest, chains)) in plan.RuleSets)
            rules[key.ToString()] = chains.ConvertAll(steps => steps.ConvertAll(Hex));
        report["rules"] = rules;
        var units = new Dictionary<string, object>();
        foreach (var (number, bytes) in plan.Units)
            units[number.ToString()] = new Dictionary<string, object>
            {
                ["name"] = plan.BattleNameOf(number), ["units"] = Hex(bytes),
            };
        report["units"] = units;
        report["fights"] = plan.Fights.ConvertAll(f => new[] { f.Battle, f.Prompt });
        report["fightScenes"] = plan.FightScenes.ConvertAll(f => new[] { f.Scene, f.First });
        report["prompts"] = plan.PromptRowsNeeded.ConvertAll(p => new object[] { p.Key, p.Map, p.Who });
        // (1.12.0) The battles' objectives: each one's key, words, whether it protects a unit, whose.
        report["objectives"] = plan.ObjectiveRows.ConvertAll(o => new object[] { o.Key, o.Words, o.Protects, o.Who });
        var starts = new List<object>();
        foreach (var start in plan.Starts)
            starts.Add(new Dictionary<string, object>
            {
                ["quest"] = start.Quest.Key, ["place"] = start.Place, ["steps"] = start.Steps.ConvertAll(Hex),
            });
        report["starts"] = starts;
        // (1.2.5) The quests' markers for each case given (MOD_STUDIO_MARKER_CASES names a JSON list of
        // [the variables' 1,024 bytes, the party's units, strict], each in hex): each place's color.
        string? markerCases = Environment.GetEnvironmentVariable("MOD_STUDIO_MARKER_CASES");
        if (markerCases != null)
        {
            using var document = JsonDocument.Parse(File.ReadAllText(markerCases));
            var markers = new List<object>();
            foreach (var c in document.RootElement.EnumerateArray())
            {
                var bank = Convert.FromHexString(c[0].GetString()!);
                var party = Convert.FromHexString(c[1].GetString()!);
                bool strict = c[2].GetBoolean();
                var shown = new List<long[]>();
                var looked = new List<int>();
                for (int place = 0; place < 48; place++)
                    looked.Add(place);
                foreach (int place in new SortedSet<int>(placeNumbers.Values))
                    looked.Add(place);
                foreach (int place in looked)
                {
                    var color = plan.MarkerAt(place, v => Framework.WorldValue(bank, v),
                                              who => Framework.HasCharacter(party, who, strict));
                    if (color != null)
                        shown.Add(new long[] { place, color.Value });
                }
                markers.Add(shown);
            }
            report["markers"] = markers;
        }
        report["hasMarkers"] = plan.HasMarkers;
        // (1.2.1) What the hooks say while each event plays (the quests' and three of the game's;
        // -1 none, 0 the world map's, 4096 a flag's number, never an event's): the game's progress
        // set (track 0 to 80, to 50, track 1 to 5), the story's progress changed, another variable;
        // (1.2.2) and when the world map would stop a travel for it, waiting where you stand.
        var kept = new List<object?>();
        var playing = new List<int> { -1, 0, 9, 10, 14, 4096 };
        foreach (var p in plan.Events)
            playing.Add(p.Number);
        foreach (var (opening, _) in plan.Openings)
            playing.Add(opening);
        foreach (int ev in playing)
            kept.Add(new object?[]
            {
                ev, plan.IsQuestEvent(ev), plan.ProgressKept(ev, 0, 80), plan.ProgressKept(ev, 0, 50),
                plan.ProgressKept(ev, 1, 5), plan.VariableKept(ev, Framework.StoryProgress),
                plan.VariableKept(ev, Framework.StoryProgress + 1), plan.TravelFreed(ev),
            });
        report["kept"] = kept;
        var given = new Dictionary<string, object>();
        foreach (var (sheet, name) in Tables)
        {
            string path = Path.Combine(tables, name);
            if (!File.Exists(path))
                continue;
            var said = new List<string>();
            var merged = plan.WithRows(sheet, File.ReadAllBytes(path), said, out string whyNot, out int added);
            if (merged != null)
                File.WriteAllBytes(Path.Combine(output, name), merged);
            given[name] = new Dictionary<string, object>
            {
                ["adds"] = plan.Adds(sheet), ["added"] = added, ["why"] = whyNot, ["said"] = said,
                ["shape"] = Framework.TableShape(sheet, File.ReadAllBytes(path)), ["whose"] = plan.RowsWhose(sheet),
            };
        }
        string eventRows = Path.Combine(tables, "eventid.nxd");
        if (File.Exists(eventRows))
        {
            var rows = File.ReadAllBytes(eventRows);
            var said = new List<string>();
            // (1.9.0) Rows for the quests' events past 886 added first.
            var grown = plan.EventRowsAdded(rows, out string whyGrown, out int grownBy);
            if (grown != null)
                rows = grown;
            string whyNot = plan.MakeEventRows(rows, said, grown != null);
            File.WriteAllBytes(Path.Combine(output, "eventid.nxd"), rows);
            given["eventid.nxd"] = new Dictionary<string, object>
            {
                ["adds"] = plan.Adds(Framework.EventRows), ["why"] = whyNot, ["said"] = said,
                ["pastAdded"] = grownBy, ["pastWhy"] = whyGrown, ["past"] = plan.EventsPastGame(),
            };
        }
        // (1.30.0) Map 116's Map row named, in place (as the hook names it), when the plan names it.
        string mapTable = Path.Combine(tables, "map.nxd");
        if (File.Exists(mapTable))
        {
            var rows = File.ReadAllBytes(mapTable);
            string whyNot = plan.Adds(Framework.MapSheet) ? Framework.NameArena(rows) : "it gets no change";
            File.WriteAllBytes(Path.Combine(output, "map.nxd"), rows);
            given["map.nxd"] = new Dictionary<string, object>
            {
                ["adds"] = plan.Adds(Framework.MapSheet), ["added"] = 0, ["why"] = whyNot, ["said"] = new List<string>(),
                ["shape"] = Framework.TableShape(Framework.MapSheet, File.ReadAllBytes(mapTable)),
                ["whose"] = plan.RowsWhose(Framework.MapSheet),
            };
        }
        report["tables"] = given;
        // (1.15.0) The rumors whose Gossip rows were another mod's as the table was given its rows: left to the game.
        report["rumorsTaken"] = plan.RumorPlans.FindAll(r => r.Taken).ConvertAll(r => r.Key);
        if (numbers.Changed)
            File.WriteAllText(numbersPath, numbers.Text());
        report["numbersChanged"] = numbers.Changed;
        File.WriteAllText(reportPath, JsonSerializer.Serialize(report));
        return 0;
    }

    /// <summary>Commands given to the variable functions run over a bank as the hooks run them:
    /// for each, what the game's own function would be given (or null), and the bank after.</summary>
    static int Flags(string[] args)
    {
        using var document = JsonDocument.Parse(File.ReadAllText(args[1]));
        var top = document.RootElement;
        var bank = new byte[Framework.BankBytes];
        if (top.TryGetProperty("bank", out var start))
            Convert.FromHexString(start.GetString()!).CopyTo(bank, 0);
        var results = new List<object?>();
        foreach (var command in top.GetProperty("commands").EnumerateArray())
        {
            int op = command[0].GetInt32(), variable = command[1].GetInt32(), operand = command[2].GetInt32();
            var result = Framework.Command(bank, op, variable, operand);
            results.Add(result == null ? null : new[] { result.Value.Op, result.Value.Dest, result.Value.Src });
        }
        // (1.2.4) The passing-through variable in the world map's commands: read into variable 0 (B1)
        // while passing and not; written (B0 on it); a number that looks like it (B0 5, 4095); cleared (BE).
        var passing = new List<object?>();
        foreach (var (op, dest, src, through) in new[]
                 {
                     (0xB1, 0, Framework.PassingThrough, true), (0xB1, 0, Framework.PassingThrough, false),
                     (0xB0, Framework.PassingThrough, 1, true), (0xB0, 5, Framework.PassingThrough, true),
                     (0xBE, Framework.PassingThrough, 0, false),
                 })
        {
            var result = Framework.PassingCommand(op, dest, src, through);
            passing.Add(result == null ? null : new[] { result.Value.Op, result.Value.Dest, result.Value.Src });
        }
        // ...and the travel's state read so (its flags, roads taken, roads it has): on the way, at
        // its last stop, none under way, another bit of the flags, at its start, past its end.
        var travels = new List<bool>();
        foreach (var (flags, taken, roads) in new[] { (1, 1, 2), (1, 2, 2), (0, 1, 2), (2, 1, 2), (3, 0, 1), (1, 3, 2) })
            travels.Add(Framework.Passing(flags, taken, roads));
        // (1.2.5) The world map's test of a character over the units given ([units, character, strict]),
        // variables as the world map reads them from the bank as the commands left it, and Markers' colors.
        var party = new List<bool>();
        if (top.TryGetProperty("party", out var partyCases))
            foreach (var c in partyCases.EnumerateArray())
                party.Add(Framework.HasCharacter(Convert.FromHexString(c[0].GetString()!), c[1].GetInt32(), c[2].GetBoolean()));
        var world = new List<int>();
        if (top.TryGetProperty("world", out var worldCases))
            foreach (var v in worldCases.EnumerateArray())
                world.Add(Framework.WorldValue(bank, v.GetInt32()));
        var colors = new List<long?>();
        if (top.TryGetProperty("colors", out var colorCases))
            foreach (var c in colorCases.EnumerateArray())
            {
                string text = c.GetString()!;
                colors.Add(QuestFile.IsColor(text) ? QuestFile.Rgba(text) : (long?)null);
            }
        // ...and whether a start's steps hold for a marker: each case its steps ([type, variable, [numbers]],
        // made into the world map's rows as the framework makes them), the variables, the party, strict.
        var holds = new List<bool>();
        if (top.TryGetProperty("holds", out var holdCases))
            foreach (var c in holdCases.EnumerateArray())
            {
                var steps = new List<byte[]>();
                foreach (var s in c.GetProperty("steps").EnumerateArray())
                {
                    var numbers = new List<short>();
                    foreach (var n in s[2].EnumerateArray())
                        numbers.Add(unchecked((short)n.GetInt32()));
                    steps.Add(Framework.WorldRow((short)s[0].GetInt32(), s[1].GetInt32(), numbers.ToArray()));
                }
                var caseBank = Convert.FromHexString(c.GetProperty("bank").GetString()!);
                var units = Convert.FromHexString(c.GetProperty("units").GetString()!);
                bool strict = c.GetProperty("strict").GetBoolean();
                holds.Add(Framework.Holds(steps, v => Framework.WorldValue(caseBank, v),
                                          who => Framework.HasCharacter(units, who, strict)));
            }
        var report = new Dictionary<string, object?>
        {
            ["party"] = party, ["world"] = world, ["colors"] = colors, ["holds"] = holds,
            ["results"] = results, ["bank"] = Hex(bank), ["passingThrough"] = Framework.PassingThrough,
            ["passing"] = passing, ["travels"] = travels, ["passingGoesOn"] = Framework.PassingGoesOn,
            ["sectors"] = new[]
            {
                Framework.EventOfSector(744 * 5, 1), Framework.EventOfSector(744 * 3, 0), Framework.EventOfSector(3721, 1),
                Framework.EventOfSector(887 * 5, 1), Framework.EventOfSector(8191 * 5, 1),
                Framework.EventOfSector(8192 * 5, 1),
            },
        };
        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }
}
