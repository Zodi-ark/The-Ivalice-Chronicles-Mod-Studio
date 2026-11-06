// Mod Studio's checks of the helper: (1.11.0) a copied scene's map animations (MapAnimations.cs) over a program's
// file laid out as in memory: the four reads of the event playing as the helper finds them, the changes it would make
// for its memory at `at` (counted from the program's start, as the calls' distances are), the native code for a
// program loaded at 0x140000000, and the table it would give the copied events. Part of The Ivalice Chronicles Mod
// Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --animations <program> <report.json> <at, hex> [variants.json] [copied.json]
//
// With variants.json (a list of programs, each a list of [address, bytes in hex] written over a copy of his): what
// Find says of each. With copied.json (a list of [event, its From]): the table's words that aren't 0.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.Json;
using ModStudioEventSetup;

static class MapAnimationChecks
{
    /// <summary>Where the program is taken to be loaded, for the native code's addresses.</summary>
    const ulong ImageBase = 0x140000000;

    public static int Run(string[] args)
    {
        var image = Program.Load(args[1]);
        var report = new Dictionary<string, object?>();
        var sites = MapAnimations.Find(image, Finder.Sections(image), out string why);
        report["why"] = why;
        if (sites != null)
        {
            report["calls"] = sites.Calls;
            report["read"] = sites.Read;
            long at = long.Parse(args[3], NumberStyles.HexNumber, CultureInfo.InvariantCulture);
            var patches = MapAnimations.Patches(image, sites, at, out why);
            report["patchesWhy"] = why;
            report["patches"] = patches?.ConvertAll(p => new object[]
            {
                p.At, Convert.ToHexString(p.Old).ToLowerInvariant(), Convert.ToHexString(p.New).ToLowerInvariant(), p.What,
            });
            report["stub"] = Convert.ToHexString(MapAnimations.Stub(ImageBase + (ulong)sites.Read,
                                                                     ImageBase + (ulong)at + MapAnimations.CodeRoom))
                                    .ToLowerInvariant();
        }
        report["constants"] = new Dictionary<string, long>
        {
            ["events"] = MapAnimations.Events, ["codeRoom"] = MapAnimations.CodeRoom,
            ["memoryBytes"] = MapAnimations.MemoryBytes, ["imageBase"] = (long)ImageBase,
            ["mostFrom"] = QuestFile.MostGameEvent,
        };
        if (args.Length > 4 && args[4] != "-")
        {
            using var document = JsonDocument.Parse(File.ReadAllText(args[4]));
            var seen = new List<object>();
            foreach (var variant in document.RootElement.EnumerateArray())
            {
                var undo = new List<(int At, byte[] Was)>();
                foreach (var change in variant.EnumerateArray())
                {
                    var bytes = Convert.FromHexString(change[1].GetString()!);
                    int where = change[0].GetInt32();
                    undo.Add((where, image.AsSpan(where, bytes.Length).ToArray()));
                    bytes.CopyTo(image, where);
                }
                var found = MapAnimations.Find(image, Finder.Sections(image), out string said);
                seen.Add(new object[] { said, found?.Calls.Count ?? 0 });
                for (int n = undo.Count - 1; n >= 0; n--)
                    undo[n].Was.CopyTo(image, undo[n].At);
            }
            report["variants"] = seen;
        }
        if (args.Length > 5)
        {
            using var document = JsonDocument.Parse(File.ReadAllText(args[5]));
            var copied = new List<(int, int)>();
            foreach (var pair in document.RootElement.EnumerateArray())
                copied.Add((pair[0].GetInt32(), pair[1].GetInt32()));
            var table = MapAnimations.Table(copied);
            var words = new List<int[]>();
            for (int n = 0; n < MapAnimations.Events; n++)
            {
                int word = BinaryPrimitives.ReadUInt16LittleEndian(table.AsSpan(2 * n, 2));
                if (word != 0)
                    words.Add(new[] { n, word });
            }
            report["table"] = words;
            report["tableBytes"] = table.Length;
        }
        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }
}
