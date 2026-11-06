// Mod Studio's checks of the helper's numbers kept in three copies and the
// mark of the numbers a save was made with (1.13.0: Numbers.Merge,
// NumbersCopies, Framework's mark), run by dev/test_side_quests.py. Part of
// The Ivalice Chronicles Mod Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --numbers <request.json> <report.json>
//
// The request: "merges", each a list of copies ({"where", "text" or null});
// "documents", "settings" and "own" (a stand-in for the player's Documents
// and the two files: their copies read, the numbers given a flag, and kept);
// "banks", each {"bank": 1,024 bytes as hex, "id", "flag" (a flag set first,
// or 0)}. (1.29.0) "starts": each a game start over the numbers before it
// ({"text" or null, "kinds": {kind: [names enabled now, in order]},
// "first", "last"}): each name's number given as each start gives them, and
// the numbers' text after; "frees", each {"text", "enabled": [mod IDs]}: what
// freeing the mods not enabled dropped, its line, the text after and whether
// the ID changed; "configs", each {"path", "text" or null}: the settings'
// file written so (or taken away), whether it asks to free, and its text once
// written back unticked (not "settings", 1.13.0's folder of Reloaded-II's).
// (1.32.0) A bank may be loaded with whole numbers ("numbers", a file's
// text, their marks) in place of "id", the flags set after reported; and
// "stamps", each {"text", "give": [flags' names], "kinds"}: the names given,
// the mark made for flags no name had (Numbers.Stamp), a second made none.
// (1.35.0) A bank may come with its party ("roster": Framework.RosterBytes
// as hex, or fewer units): loaded with both, what is said of the mods'
// items ("items"), whether it held any before ("anyItem") and the party
// after reported; a mark's items given and freed are in "marks". (1.35.1)
// A bank may come with the places the mods give now ("given": [numbers]):
// loaded as the save hook loads one, its place (variable 49) first
// (SaveFallback.MoveOff), what is said of it ("moved") and where it stands
// after ("place") reported.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using ModStudioEventSetup;

static class NumberChecks
{
    public static int Run(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var root = request.RootElement;
        var report = new Dictionary<string, object?>
        {
            ["flagBits"] = Framework.FlagBits,
            ["markAt"] = Framework.MarkAt,
        };
        var merges = new List<object>();
        if (root.TryGetProperty("merges", out var mergeList))
            foreach (var merge in mergeList.EnumerateArray())
            {
                var copies = new List<Numbers.Copy>();
                foreach (var copy in merge.EnumerateArray())
                    copies.Add(new Numbers.Copy(copy.GetProperty("where").GetString() ?? "",
                                                copy.GetProperty("text").ValueKind == JsonValueKind.Null
                                                    ? null : copy.GetProperty("text").GetString()));
                var said = new List<string>();
                var numbers = Numbers.Merge(copies, said);
                merges.Add(new Dictionary<string, object>
                {
                    ["text"] = numbers.Text(),
                    ["said"] = said,
                    ["changed"] = numbers.Changed,
                    ["id"] = numbers.Id,
                    ["marks"] = MarksOf(numbers),
                });
            }
        report["merges"] = merges;
        if (root.TryGetProperty("documents", out var documents))
        {
            var places = NumbersCopies.Places(documents.GetString() ?? "", root.GetProperty("settings").GetString() ?? "",
                                              root.GetProperty("own").GetString() ?? "");
            report["places"] = places.ConvertAll(p => new[] { p.Where, p.File });
            var said = new List<string>();
            var numbers = NumbersCopies.Read(places, said);
            if (root.TryGetProperty("give", out var give))
                numbers.Give("Flags", give.GetString() ?? "", Bits(), b => b < Framework.FlagBits, out _);
            var kept = new List<string>();
            NumbersCopies.Keep(places, numbers, kept.Add);
            report["read"] = new Dictionary<string, object>
            {
                ["said"] = said,
                ["kept"] = kept,
                ["text"] = numbers.Text(),
                ["id"] = numbers.Id,
            };
        }
        var banks = new List<object>();
        if (root.TryGetProperty("banks", out var bankList))
            foreach (var entry in bankList.EnumerateArray())
            {
                byte[] bank = Convert.FromHexString(entry.GetProperty("bank").GetString() ?? "");
                // (1.32.0) The numbers a save is loaded with: their file's text ("numbers"), or only an ID ("id").
                var numbers = entry.TryGetProperty("numbers", out var text)
                    ? Numbers.FromText(text.GetString(), new List<string>())
                    : Numbers.FromText($"{{\"Version\": 1, \"Id\": {entry.GetProperty("id").GetUInt32()}}}",
                                       new List<string>());
                int flag = entry.TryGetProperty("flag", out var f) ? f.GetInt32() : 0;
                // (1.35.0) Its party, when the request gives one.
                byte[]? roster = entry.TryGetProperty("roster", out var r)
                    ? Convert.FromHexString(r.GetString() ?? "") : null;
                bool anyItem = Framework.AnyItem(bank, roster ?? Array.Empty<byte>());
                string? said = null, items = null, moved = null;
                // (1.35.1) The places the mods give now: the save's place looked at first, as the hook does.
                if (flag == 0 && entry.TryGetProperty("given", out var givenNow))
                {
                    var given = new HashSet<int>();
                    foreach (var place in givenNow.EnumerateArray())
                        given.Add(place.GetInt32());
                    moved = SaveFallback.MoveOff(bank, given, numbers);
                }
                if (flag != 0)
                {
                    Framework.WriteFlag(bank, flag, 1);
                    Framework.Mark(bank, numbers.Id);
                }
                else if (roster != null)
                    said = Framework.Loaded(bank, roster, numbers, out items);
                else
                    said = Framework.Loaded(bank, numbers);
                var set = new List<int>();
                for (int bit = 0; bit < Framework.FlagBits; bit++)
                    if (Framework.IsFlagByte(Framework.BankTail + (bit >> 3))
                        && Framework.ReadFlag(bank, Framework.FlagBase + bit) != 0)
                        set.Add(bit);
                banks.Add(new Dictionary<string, object?>
                {
                    ["bank"] = Convert.ToHexString(bank),
                    ["said"] = said,
                    ["items"] = items,
                    ["moved"] = moved,
                    ["place"] = BitConverter.ToInt32(bank, 4 * SaveFallback.PlaceVariable),
                    ["anyItem"] = anyItem,
                    ["roster"] = roster == null ? null : Convert.ToHexString(roster),
                    ["mark"] = Framework.ReadMark(bank),
                    ["anyFlag"] = Framework.AnyFlag(bank),
                    ["set"] = set,
                    ["isFlag"] = new[] { Framework.IsFlag(0x1000 + Framework.FlagBits - 1),
                                         Framework.IsFlag(0x1000 + Framework.FlagBits) },
                });
            }
        report["banks"] = banks;
        // (1.32.0) "stamps", each {"text", "give": [flags' names given, in order], "kinds": optional other kinds' names
        // given ({kind: [names]})}: the numbers read, the names given, a mark made when a flag no name had was given
        // (Numbers.Stamp), then a second (none); the text after, the IDs and the marks.
        var stamps = new List<object>();
        if (root.TryGetProperty("stamps", out var stampList))
            foreach (var entry in stampList.EnumerateArray())
            {
                var text = entry.GetProperty("text");
                var numbers = Numbers.FromText(text.ValueKind == JsonValueKind.Null ? null : text.GetString(),
                                               new List<string>());
                uint before = numbers.Id;
                var given = new List<int>();
                foreach (var name in entry.GetProperty("give").EnumerateArray())
                    given.Add(numbers.Give("Flags", name.GetString() ?? "", Bits(), ItemRoom.FlagFree, out _));
                if (entry.TryGetProperty("kinds", out var kinds))
                    foreach (var kind in kinds.EnumerateObject())
                        foreach (var name in kind.Value.EnumerateArray())
                            numbers.Give(kind.Name, name.GetString() ?? "", Range(1, 9999), _ => true, out _);
                bool first = numbers.Stamp();
                uint after = numbers.Id;
                bool second = numbers.Stamp();
                stamps.Add(new Dictionary<string, object>
                {
                    ["given"] = given,
                    ["stamped"] = first,
                    ["again"] = second,
                    ["before"] = before,
                    ["id"] = after,
                    ["idAgain"] = numbers.Id,
                    ["marks"] = MarksOf(numbers),
                    ["text"] = numbers.Text(),
                    ["changed"] = numbers.Changed,
                });
            }
        report["stamps"] = stamps;
        var starts = new List<object>();
        if (root.TryGetProperty("starts", out var startList))
            foreach (var start in startList.EnumerateArray())
            {
                var text = start.GetProperty("text");
                var numbers = Numbers.FromText(text.ValueKind == JsonValueKind.Null ? null : text.GetString(),
                                               new List<string>());
                int first = start.GetProperty("first").GetInt32(), last = start.GetProperty("last").GetInt32();
                var given = new Dictionary<string, object>();
                foreach (var kind in start.GetProperty("kinds").EnumerateObject())
                {
                    var names = new List<string>();
                    foreach (var name in kind.Value.EnumerateArray())
                        names.Add(name.GetString() ?? "");
                    numbers.BeginNow(kind.Name, names);
                    var numbered = new List<object>();
                    foreach (var name in names)
                        numbered.Add(new object[] { name, numbers.GiveNow(kind.Name, name, Range(first, last), out bool moved),
                                                    moved });
                    numbers.SettleNow(kind.Name);
                    given[kind.Name] = numbered;
                }
                starts.Add(new Dictionary<string, object>
                {
                    ["given"] = given,
                    ["text"] = numbers.Text(),
                    ["changed"] = numbers.Changed,
                });
            }
        report["starts"] = starts;
        var frees = new List<object>();
        if (root.TryGetProperty("frees", out var freeList))
            foreach (var free in freeList.EnumerateArray())
            {
                var numbers = Numbers.FromText(free.GetProperty("text").GetString(), new List<string>());
                uint before = numbers.Id;
                var enabled = new HashSet<string>(StringComparer.Ordinal);
                foreach (var mod in free.GetProperty("enabled").EnumerateArray())
                    enabled.Add(mod.GetString() ?? "");
                var freed = numbers.Free(enabled);
                frees.Add(new Dictionary<string, object>
                {
                    ["freed"] = freed,
                    ["line"] = Numbers.FreedLine(freed),
                    ["text"] = numbers.Text(),
                    ["idChanged"] = numbers.Id != before,
                    ["changed"] = numbers.Changed,
                    ["marks"] = MarksOf(numbers),
                });
            }
        report["frees"] = frees;
        var configs = new List<object>();
        if (root.TryGetProperty("configs", out var configList))
            foreach (var entry in configList.EnumerateArray())
            {
                string path = entry.GetProperty("path").GetString() ?? "";
                var text = entry.GetProperty("text");
                if (text.ValueKind == JsonValueKind.Null)
                {
                    if (File.Exists(path))
                        File.Delete(path);
                }
                else
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(path) ?? ".");
                    File.WriteAllText(path, text.GetString() ?? "");
                }
                bool free = Settings.ReadFreeNumbers(path);
                Settings.Write(path, false);
                configs.Add(new Dictionary<string, object> { ["free"] = free, ["after"] = File.ReadAllText(path) });
            }
        report["configs"] = configs;
        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }

    /// <summary>(1.32.0) The numbers' marks, oldest first: each its ID, flags given and freed; (1.35.0) the mods' items'
    /// numbers given and freed.</summary>
    static List<object> MarksOf(Numbers numbers)
    {
        var marks = new List<object>();
        foreach (var mark in numbers.Marks)
            marks.Add(new Dictionary<string, object>
            {
                ["id"] = mark.Id, ["flags"] = mark.Flags, ["freed"] = mark.Freed, ["items"] = mark.Items,
                ["freedItems"] = mark.FreedItems,
            });
        return marks;
    }

    static IEnumerable<int> Range(int first, int last)
    {
        for (int n = first; n <= last; n++)
            yield return n;
    }

    static IEnumerable<int> Bits()
    {
        for (int n = 0; n < Framework.FlagBits; n++)
            yield return n;
    }
}
