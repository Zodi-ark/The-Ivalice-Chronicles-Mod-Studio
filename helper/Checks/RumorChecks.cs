// Mod Studio's checks of a side quest's tavern rumors as the helper's hooks tell them (1.15.0: Framework's RumorTold,
// and Holds over a rumor's When; 1.29.0: RumorReadNow, as the tavern's agent marks a rumor read, and SettleRumors, its
// save bytes made its own), run by dev/test_side_quests.py. Part of The Ivalice Chronicles Mod Studio, GPL-3.0. Not
// shipped.
//
//     dotnet Checks.dll --rumors <request.json> <report.json>
//
// The request: "mod" (<mod id>=<folder>, its quests read and planned as the helper plans them, from no numbers),
// "tests" (the taverns' tests of a rumor told, each [key, place]), and "banks", each {"bank": 1,024 bytes as hex,
// "read": the keys of the rumors the taverns have shown, "party": the characters in the party}. The report: what the
// plan said and its rumors (key, mask, flag); for each bank, each rumor told anywhere, each test as the hook answers
// it (null: the game's own test), what the read rumors said and the rumors' flags after. (1.18.0) With "places": true,
// the mod's own places read and numbered as the helper numbers them (from no numbers), so a rumor may name its towns
// with a menu of their own: the report then has "placeNumbers", "menuTowns" and each rumor's mod towns ("rumorTowns").
// (1.29.0) "settles", each {"bank", "bytes": the rumors' 128 save bytes as hex}: the bytes after SettleRumors, how many
// keys it settled, and each rumor's mark ("tags").
//
// (1.29.0, Zodi's test 62) "starts" in place of "mod": the game started again and again over one numbers file and one
// save, as test 62 plays it. Each start {"mods": ["<mod id>=<folder>", ...] (enabled, in Reloaded-II's order), "read":
// [the names of the rumors read in its taverns], "free": whether his setting is ticked}: the numbers of every mod not
// enabled freed first when it is (Numbers.Free, as Mod.FreeNumbersIfAsked), the quests planned from the numbers kept
// (the rumors numbered afresh), the save's rumor bytes settled (a new game's at the first start: every pair 1, 1), each
// rumor named marked read as the game and the tavern's agent mark it (its first byte 0, then RumorReadNow), the numbers
// kept for the next start as the file keeps them. The report's "starts": each start's freeing line (null unticked),
// problems, rumors (name, key, mark, flag after its reads), how many keys it settled, each rumor's two bytes after the
// settle and after its reads, what the reads said, what the plan said, and the numbers' text after it.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using ModStudioEventSetup;

static class RumorChecks
{
    public static int Run(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var root = request.RootElement;
        if (root.TryGetProperty("starts", out var startList))
            return Starts(startList, args[2]);
        string mod = root.GetProperty("mod").GetString() ?? "";
        int split = mod.IndexOf('=');
        string id = mod.Substring(0, split), folder = mod.Substring(split + 1);
        var problems = new List<string>();
        var numbers = Numbers.FromText("", new List<string>());
        bool withPlaces = root.TryGetProperty("places", out var asked) && asked.ValueKind == JsonValueKind.True;
        var own = withPlaces ? PlaceFile.ReadMod(id, id, folder, problems) : new List<MapPlace>();
        var placeNumbers = new Dictionary<string, int>(StringComparer.Ordinal);
        var towns = new List<(MapPlace Place, int Number)>();
        foreach (var d in Destinations.Plan(own, numbers, new List<string>()))
        {
            placeNumbers[$"{d.Place.ModId}/{d.Place.Name}"] = d.Number;
            if (d.Place.Town && d.Place.Menu != null)
                towns.Add((d.Place, d.Number));
        }
        var quests = QuestFile.ReadMod(id, id, folder, problems, own.ConvertAll(p => p.Name), MapFile.NamesIn(folder));
        var plan = Framework.Plan(new[] { 1, 2, 3 }, 600, new HashSet<int>(), quests, numbers, placeNumbers,
                                  menuTowns: towns);
        var report = new Dictionary<string, object?>
        {
            ["problems"] = problems,
            ["said"] = plan.Said,
            ["rumors"] = plan.RumorPlans.ConvertAll(r => new object[] { r.Key, r.Mask, r.Flag }),
        };
        if (withPlaces)
        {
            report["placeNumbers"] = placeNumbers;
            report["menuTowns"] = new List<int>(plan.MenuTowns.Keys);
            report["rumorTowns"] = plan.RumorPlans.ConvertAll(r => new SortedSet<int>(r.ModTowns));
        }
        var banks = new List<object>();
        foreach (var entry in root.GetProperty("banks").EnumerateArray())
        {
            byte[] bank = Convert.FromHexString(entry.GetProperty("bank").GetString() ?? "");
            var read = new HashSet<int>();
            foreach (var k in entry.GetProperty("read").EnumerateArray())
                read.Add(k.GetInt32());
            var party = new HashSet<int>();
            foreach (var c in entry.GetProperty("party").EnumerateArray())
                party.Add(c.GetInt32());
            int Value(int v) => Framework.WorldValue(bank, v);
            bool InParty(int c) => party.Contains(c);
            var told = plan.RumorPlans.ConvertAll(r => Framework.RumorTold(r, -1, Value, InParty));
            var tests = new List<bool?>();
            foreach (var test in root.GetProperty("tests").EnumerateArray())
                tests.Add(Framework.RumorTold(plan.RumorAt(test[0].GetInt32()), test[1].GetInt32(), Value, InParty));
            var said = new List<string>();
            foreach (int key in read)
            {
                string? line = plan.RumorReadNow(bank, key);
                if (line != null)
                    said.Add(line);
            }
            banks.Add(new Dictionary<string, object?>
            {
                ["told"] = told,
                ["tests"] = tests,
                ["said"] = said,
                ["flags"] = plan.RumorPlans.ConvertAll(r => Framework.ReadFlag(bank, r.Flag)),
            });
        }
        report["banks"] = banks;
        report["tags"] = plan.RumorPlans.ConvertAll(r => (int)r.Tag);
        var settles = new List<object>();
        if (root.TryGetProperty("settles", out var settleList))
            foreach (var entry in settleList.EnumerateArray())
            {
                byte[] bank = Convert.FromHexString(entry.GetProperty("bank").GetString() ?? "");
                byte[] bytes = Convert.FromHexString(entry.GetProperty("bytes").GetString() ?? "");
                int settled = plan.SettleRumors(bank, bytes);
                settles.Add(new Dictionary<string, object>
                {
                    ["bytes"] = Convert.ToHexString(bytes),
                    ["settled"] = settled,
                    ["flags"] = plan.RumorPlans.ConvertAll(r => Framework.ReadFlag(bank, r.Flag)),
                });
            }
        report["settles"] = settles;
        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }

    /// <summary>(1.29.0, test 62) The game started again and again over one numbers file and one save (the header
    /// says what a start asks and what the report has).</summary>
    static int Starts(JsonElement startList, string reportPath)
    {
        string kept = "";
        var bank = new byte[1024];
        var bytes = new byte[128];
        Array.Fill(bytes, (byte)1);
        var starts = new List<object>();
        foreach (var start in startList.EnumerateArray())
        {
            var problems = new List<string>();
            var numbers = Numbers.FromText(kept, problems);
            var quests = new List<Quest>();
            var enabled = new HashSet<string>(StringComparer.Ordinal);
            foreach (var entry in start.GetProperty("mods").EnumerateArray())
            {
                string mod = entry.GetString() ?? "";
                int split = mod.IndexOf('=');
                string id = mod.Substring(0, split), folder = mod.Substring(split + 1);
                enabled.Add(id);
                quests.AddRange(QuestFile.ReadMod(id, id, folder, problems, new List<string>(), MapFile.NamesIn(folder)));
            }
            string? freedLine = null;
            if (start.TryGetProperty("free", out var free) && free.ValueKind == JsonValueKind.True)
                freedLine = Numbers.FreedLine(numbers.Free(enabled));
            var records = new List<int>();
            for (int n = 1; n <= 40; n++)
                records.Add(n);
            var plan = Framework.Plan(records, 600, new HashSet<int>(), quests, numbers);
            int settled = plan.SettleRumors(bank, bytes);
            List<object> Pairs() => plan.RumorPlans.ConvertAll(r => (object)new[] { (int)bytes[2 * r.Key],
                                                                                      (int)bytes[2 * r.Key + 1] });
            var afterSettle = Pairs();
            var said = new List<string>();
            foreach (var name in start.GetProperty("read").EnumerateArray())
            {
                var rumor = plan.RumorPlans.Find(r => r.Rumor.Name == name.GetString());
                if (rumor == null)
                {
                    said.Add($"no rumor {name.GetString()} at this start");
                    continue;
                }
                // The game's own mark of a rumor read (the tavern's agent, action 0), then the helper's hook after it.
                bytes[2 * rumor.Key] = 0;
                string? line = plan.RumorReadNow(bank, rumor.Key);
                if (line != null)
                    said.Add(line);
            }
            starts.Add(new Dictionary<string, object?>
            {
                ["freed"] = freedLine,
                ["problems"] = problems,
                ["rumors"] = plan.RumorPlans.ConvertAll(r => (object)new object[] { r.Rumor.Name, r.Key, (int)r.Tag,
                                                                                    Framework.ReadFlag(bank, r.Flag) }),
                ["settled"] = settled,
                ["afterSettle"] = afterSettle,
                ["afterReads"] = Pairs(),
                ["said"] = said,
                ["planSaid"] = plan.Said,
                ["numbers"] = numbers.Text(),
            });
            kept = numbers.Text();
        }
        File.WriteAllText(reportPath, JsonSerializer.Serialize(new Dictionary<string, object> { ["starts"] = starts }));
        return 0;
    }
}
