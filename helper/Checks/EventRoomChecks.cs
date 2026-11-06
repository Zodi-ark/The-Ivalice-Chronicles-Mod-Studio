// Mod Studio's checks of the helper: (1.9.0) room for hundreds of quests (EventRoom.cs) over a program's file laid
// out as in memory: the setup table as the helper finds it, the sites EventRoom finds, and the changes it would make
// for its memory at `at` (counted from the program's start, as its distances are). Part of The Ivalice Chronicles
// Mod Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --event-room <program> <report.json> <at, hex> [variants.json]
//
// With variants.json (a list of programs, each a list of [address, bytes in hex] written over a copy of his):
// what Find says of each.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.Json;
using ModStudioEventSetup;

static class EventRoomChecks
{
    public static int Run(string[] args)
    {
        var image = Program.Load(args[1]);
        var report = new Dictionary<string, object?>();
        var table = Finder.Find(image, out string why);
        report["table"] = table == null ? null : new object[] { table.Address, table.Slots, table.SlotOf.Count };
        if (table == null)
        {
            report["why"] = why;
            File.WriteAllText(args[2], JsonSerializer.Serialize(report));
            return 0;
        }
        var sites = EventRoom.Find(image, Finder.Sections(image), table.Address, out why);
        report["why"] = why;
        if (sites != null)
        {
            report["sites"] = new Dictionary<string, object>
            {
                ["setupTable"] = sites.SetupTable,
                ["setupLeas"] = sites.SetupLeas.ConvertAll(s => new[] { s.At, s.Past }),
                ["bounds"] = sites.Bounds.ConvertAll(s => new[] { s.At, s.Imm }),
                ["finishTable"] = sites.FinishTable,
                ["finishLeas"] = sites.FinishLeas,
                ["finishBased"] = sites.FinishBased.ConvertAll(s => new[] { s.At, s.Distance }),
                ["fixedWrites"] = sites.FixedWrites.ConvertAll(s => new[] { s.At, s.Distance, s.Length, s.Word }),
                ["retryCopy"] = sites.RetryCopy,
                ["retryLeas"] = sites.RetryLeas,
                ["retrySizes"] = sites.RetrySizes,
                ["decodes"] = sites.Decodes,
                ["tests"] = sites.Tests.ConvertAll(s => new[] { s.At, s.Imm }),
                ["kinds"] = sites.Kinds.ConvertAll(s => new[] { s.At, s.Imm, s.New }),
                ["count"] = sites.Count,
            };
            long at = long.Parse(args[3], NumberStyles.HexNumber, CultureInfo.InvariantCulture);
            var patches = EventRoom.Patches(image, sites, at, at + EventRoom.SetupBytes,
                                            at + EventRoom.SetupBytes + EventRoom.FinishRoom, out why);
            report["patchesWhy"] = why;
            report["patches"] = patches?.ConvertAll(p => new object[]
            {
                p.At, Convert.ToHexString(p.Old).ToLowerInvariant(), Convert.ToHexString(p.New).ToLowerInvariant(), p.What,
            });
        }
        report["constants"] = new Dictionary<string, int>
        {
            ["events"] = EventRoom.Events, ["lastEvent"] = EventRoom.LastEvent, ["setupBytes"] = EventRoom.SetupBytes,
            ["finishRoom"] = EventRoom.FinishRoom, ["memoryBytes"] = EventRoom.MemoryBytes,
            ["wideDecode"] = EventRoom.WideDecode, ["followsTest"] = EventRoom.FollowsTest,
        };
        // Variants of the program (a JSON list, each a list of [address, bytes in hex] written over a copy of it):
        // what EventRoom.Find says of each ("" when it finds the sites), and how many it finds.
        if (args.Length > 4)
        {
            using var document = JsonDocument.Parse(File.ReadAllText(args[4]));
            var seen = new List<object>();
            foreach (var variant in document.RootElement.EnumerateArray())
            {
                // Each change made over the program, then put back as it was once Find has looked.
                var undo = new List<(int At, byte[] Was)>();
                foreach (var change in variant.EnumerateArray())
                {
                    var bytes = Convert.FromHexString(change[1].GetString()!);
                    int at = change[0].GetInt32();
                    undo.Add((at, image.AsSpan(at, bytes.Length).ToArray()));
                    bytes.CopyTo(image, at);
                }
                var found = EventRoom.Find(image, Finder.Sections(image), table.Address, out string said);
                seen.Add(new object[] { said, found?.Count ?? 0 });
                for (int n = undo.Count - 1; n >= 0; n--)
                    undo[n].Was.CopyTo(image, undo[n].At);
            }
            report["variants"] = seen;
        }
        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }
}
