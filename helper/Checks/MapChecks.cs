// Mod Studio's checks of the helper: (1.10.0) a quest's own maps (MapFile.cs, MapRows.cs, MapRoom.cs, MapTables.cs)
// over a program's file laid out as in memory: the mods' quest maps read and numbered as the helper reads and numbers
// them, the sites MapRoom finds, the memory it makes for its data at `data at` and its code at `code at` (written to
// the out folder: data.bin, code.bin) and the changes it would make for them, and the tables given (each by its sheet)
// with the quest maps' rows (written to the out folder). The program's pointers in its file are from its own base
// (its header's), which the memory is made from. Part of The Ivalice Chronicles Mod Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --quest-maps <program> <report.json> <out> <data at, hex> <code at, hex> <numbers.json or ->
//                       [table:<sheet, hex>=<file> ...] <mod id>=<folder> ...
//     dotnet Checks.dll --map-file <map.json> <report.json>    (its files beside it)
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.Json;
using ModStudioEventSetup;

static class MapChecks
{
    static string Hex(byte[] bytes) => Convert.ToHexString(bytes);

    /// <summary>The base the program's file's pointers are from: its PE header's.</summary>
    static ulong ImageBase(byte[] file)
    {
        int pe = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(0x3C, 4));
        return BinaryPrimitives.ReadUInt64LittleEndian(file.AsSpan(pe + 24 + 24, 8));
    }

    static object Summary(QuestMap m)
    {
        var grid = new List<object>();
        foreach (var (place, bytes) in m.Grid)
            grid.Add(new object[] { place, bytes.Length, Hex(System.Security.Cryptography.SHA256.HashData(bytes)) });
        var rows = new Dictionary<string, object>();
        foreach (var (table, list) in m.Rows)
            rows[table] = list.Count;
        return new Dictionary<string, object>
        {
            ["key"] = m.Key, ["folder"] = m.Folder, ["base"] = m.Base, ["title"] = m.Title, ["mesh"] = m.Mesh,
            ["anims"] = m.Anims, ["grid"] = grid, ["rows"] = rows,
        };
    }

    public static int Run(string[] args)
    {
        var file = File.ReadAllBytes(args[1]);
        var image = Program.Load(args[1]);
        string reportPath = args[2], output = args[3];
        ulong dataAt = ulong.Parse(args[4], NumberStyles.HexNumber, CultureInfo.InvariantCulture);
        ulong codeAt = ulong.Parse(args[5], NumberStyles.HexNumber, CultureInfo.InvariantCulture);
        string numbersPath = args[6];
        Directory.CreateDirectory(output);
        var report = new Dictionary<string, object?>();
        var tables = new List<(int Sheet, string File)>();
        var maps = new List<QuestMap>();
        var problems = new List<string>();
        var names = new Dictionary<string, List<string>>();
        for (int n = 7; n < args.Length; n++)
        {
            int split = args[n].IndexOf('=');
            string left = args[n].Substring(0, split), right = args[n].Substring(split + 1);
            if (left.StartsWith("table:", StringComparison.Ordinal))
            {
                tables.Add((int.Parse(left.Substring(6), NumberStyles.HexNumber, CultureInfo.InvariantCulture), right));
                continue;
            }
            maps.AddRange(MapFile.ReadMod(left, left, right, problems));
            names[left] = MapFile.NamesIn(right);
        }
        report["problems"] = problems;
        report["names"] = names;
        report["maps"] = maps.ConvertAll(Summary);
        var read = new List<string>();
        var numbers = Numbers.FromText(numbersPath != "-" && File.Exists(numbersPath) ? File.ReadAllText(numbersPath) : "",
                                       read);
        report["numbersRead"] = read;
        var sites = MapRoom.Find(image, Finder.Sections(image), out string why);
        report["why"] = why;
        report["sites"] = sites == null ? null : new Dictionary<string, object>
        {
            ["GnsLoad"] = sites.GnsLoad, ["MoveFindLea"] = sites.MoveFindLea, ["GnsLeaJa"] = sites.GnsLeaJa,
            ["GnsLeaEn"] = sites.GnsLeaEn, ["ListsCall"] = sites.ListsCall, ["ListsTarget"] = sites.ListsTarget,
            ["ListLeaJa"] = sites.ListLeaJa, ["ListLeaEn"] = sites.ListLeaEn, ["FileRead"] = sites.FileRead,
            ["ReadDoneWord"] = sites.ReadDoneWord, ["Sprintf"] = sites.Sprintf, ["FormatCalls"] = sites.FormatCalls,
            ["MeshCheck"] = sites.MeshCheck, ["AnimCheck"] = sites.AnimCheck, ["Limit"] = sites.Limit,
            ["MoveFind"] = sites.MoveFind, ["GnsJa"] = sites.GnsJa, ["GnsEn"] = sites.GnsEn, ["ListsJa"] = sites.ListsJa,
            ["ListsEn"] = sites.ListsEn,
        };
        var said = new List<string>();
        var given = MapRoom.Plan(maps, numbers, image, sites, said);
        report["said"] = said;
        report["given"] = given.ConvertAll(g => new object[] { g.Number, g.Map.Key, g.Map.Base });
        report["numbers"] = numbers.Text();
        ulong imageBase = ImageBase(file);
        report["imageBase"] = imageBase;
        if (sites != null)
        {
            var block = MapRoom.Memory(image, sites, imageBase, dataAt, codeAt, given);
            File.WriteAllBytes(Path.Combine(output, "data.bin"), block.Data);
            File.WriteAllBytes(Path.Combine(output, "code.bin"), block.Code);
            report["block"] = new Dictionary<string, object>
            {
                ["refresh"] = block.Refresh, ["reader"] = block.Reader, ["lists"] = block.ListsThunk,
                ["stubs"] = block.Stubs, ["files"] = block.Files.ConvertAll(f => new[] { f.Number, f.Place }),
                ["data"] = block.Data.Length, ["code"] = block.Code.Length,
                ["codeLength"] = MapRoom.CodeLength(sites, block.Files.Count),
            };
            var patches = MapRoom.Patches(image, sites, block, imageBase, out string patchesWhy);
            report["patchesWhy"] = patchesWhy;
            report["patches"] = patches?.ConvertAll(p => new object[]
            {
                p.At, Convert.ToHexString(p.Old).ToLowerInvariant(), Convert.ToHexString(p.New).ToLowerInvariant(), p.What,
            });
        }
        report["layout"] = new Dictionary<string, int>
        {
            ["GnsJaAt"] = MapRoom.GnsJaAt, ["GnsEnAt"] = MapRoom.GnsEnAt, ["ListsJaAt"] = MapRoom.ListsJaAt,
            ["ListsEnAt"] = MapRoom.ListsEnAt, ["MoveFindAt"] = MapRoom.MoveFindAt, ["BasesAt"] = MapRoom.BasesAt,
            ["MeshPathsAt"] = MapRoom.MeshPathsAt, ["AnimPathsAt"] = MapRoom.AnimPathsAt,
            ["RefreshSlot"] = MapRoom.RefreshSlot, ["ReaderSlot"] = MapRoom.ReaderSlot, ["FilesAt"] = MapRoom.FilesAt,
            ["FakeFile"] = (int)MapRoom.FakeFile, ["ListPairs"] = MapRoom.ListPairs, ["FirstMap"] = MapRoom.FirstMap,
            ["LastMap"] = MapRoom.LastMap, ["TitleKeyFirst"] = MapRoom.TitleKeyFirst,
        };
        var mapTables = new MapTables(given);
        var tableReport = new Dictionary<string, object?>();
        foreach (var (sheet, path) in tables)
        {
            var bytes = File.ReadAllBytes(path);
            bool adds = mapTables.Adds(sheet);
            string twhy = "";
            int added = 0;
            var tableSaid = new List<string>();
            var withRows = adds ? mapTables.WithRows(sheet, bytes, tableSaid, out twhy, out added) : null;
            string outFile = Path.Combine(output, $"table_{sheet:x}.nxd");
            if (withRows != null)
                File.WriteAllBytes(outFile, withRows);
            tableReport[sheet.ToString("x")] = new Dictionary<string, object?>
            {
                ["name"] = MapTables.NameOf(sheet), ["adds"] = adds, ["why"] = twhy, ["added"] = added, ["said"] = tableSaid,
                ["file"] = withRows != null ? outFile : null,
            };
        }
        report["tables"] = tableReport;
        var rows = new Dictionary<string, object>();
        foreach (var t in MapRows.Tables)
            rows[t.Name] = mapTables.RowsFor(t.Sheet).ConvertAll(r => new object[] { r.Keys, Hex(r.Bytes) });
        rows["PlaceName"] = mapTables.RowsFor(Destinations.NameSheet).ConvertAll(r => new object[] { r.Keys, Hex(r.Bytes) });
        report["rows"] = rows;
        report["sheets"] = Array.ConvertAll(MapRows.Tables, t => new object[] { t.Name, t.Sheet, t.Keys, t.Head });
        File.WriteAllText(reportPath, JsonSerializer.Serialize(report));
        return 0;
    }

    /// <summary>One map.json read as the helper reads it (its folder's files beside it): its problems and, when it can
    /// be used, what it gives.</summary>
    public static int RunFile(string[] args)
    {
        string path = Path.GetFullPath(args[1]);
        string folder = Path.GetDirectoryName(path)!;
        var problems = new List<string>();
        var map = MapFile.Read("mod", "mod", Path.GetFileName(folder), File.ReadAllText(path),
                               name => File.ReadAllBytes(Path.Combine(folder, name)), problems);
        var report = new Dictionary<string, object?>
        {
            ["problems"] = problems, ["map"] = map == null ? null : Summary(map),
        };
        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }
}
