// Mod Studio's checks of the helper's own names for a quest's units (1.33.0, Zodi's choice of 5 November: "As a
// renamed unit"), run by dev/test_side_quests.py. Part of The Ivalice Chronicles Mod Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --names <request.json> <report.json>
//
// The request: "goods", names each told a unit's own name or not (QuestFile.GoodOwnName, as Mod Studio's
// side_quests.good_own_name tells it); "entries", each {"blocks": {battle: where its 16 entries start}, "entry"}: which
// quest battle's unit the entry is (Framework.EntryOf), or none; "writes", names each written where the game keeps a
// renamed unit's (Framework.WriteOwnName over 64 bytes of 0xEE: the bytes after); "units", each {"unit": a battle
// unit's first bytes as hex, "entry", "blocks", "names": {battle: {place 1 to 16: name}}}: the unit given its own name
// as the hook gives it (Framework.NameUnit), what was named and its bytes after.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using ModStudioEventSetup;

static class NameChecks
{
    public static int Run(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var root = request.RootElement;
        var report = new Dictionary<string, object?>
        {
            ["most"] = QuestFile.MostOwnName, ["bytes"] = QuestFile.OwnNameBytes,
            ["at"] = new[] { Framework.UnitPartyAt, Framework.NotFromParty, Framework.UnitOwnName, Framework.OwnNameSize },
        };
        var goods = new List<bool>();
        if (root.TryGetProperty("goods", out var goodList))
            foreach (var name in goodList.EnumerateArray())
                goods.Add(QuestFile.GoodOwnName(name.GetString() ?? ""));
        report["goods"] = goods;
        var entries = new List<object?>();
        if (root.TryGetProperty("entries", out var entryList))
            foreach (var e in entryList.EnumerateArray())
            {
                var found = Framework.EntryOf(Blocks(e.GetProperty("blocks")), (nint)e.GetProperty("entry").GetInt64());
                entries.Add(found == null ? null : new[] { found.Value.Battle, found.Value.Slot });
            }
        report["entries"] = entries;
        var writes = new List<string>();
        if (root.TryGetProperty("writes", out var writeList))
            foreach (var name in writeList.EnumerateArray())
            {
                var text = new byte[Framework.OwnNameSize];
                Array.Fill(text, (byte)0xEE);
                Framework.WriteOwnName(text, name.GetString() ?? "");
                writes.Add(Convert.ToHexString(text));
            }
        report["writes"] = writes;
        var units = new List<object?>();
        if (root.TryGetProperty("units", out var unitList))
            foreach (var u in unitList.EnumerateArray())
            {
                byte[] unit = Convert.FromHexString(u.GetProperty("unit").GetString() ?? "");
                var names = new Dictionary<int, SortedDictionary<int, string>>();
                foreach (var battle in u.GetProperty("names").EnumerateObject())
                {
                    var named = new SortedDictionary<int, string>();
                    foreach (var slot in battle.Value.EnumerateObject())
                        named[int.Parse(slot.Name) - 1] = slot.Value.GetString() ?? "";
                    names[int.Parse(battle.Name)] = named;
                }
                var done = Framework.NameUnit(unit, (nint)u.GetProperty("entry").GetInt64(), Blocks(u.GetProperty("blocks")),
                                              names);
                units.Add(new Dictionary<string, object?>
                {
                    ["named"] = done == null ? null : new object[] { done.Value.Battle, done.Value.Slot + 1, done.Value.Name },
                    ["said"] = done == null ? null : Framework.NamedLine("Test 69 Quest's Opening units", done.Value.Slot,
                                                                          done.Value.Name),
                    ["unit"] = Convert.ToHexString(unit),
                });
            }
        report["units"] = units;
        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }

    static Dictionary<int, nint> Blocks(JsonElement blocks)
    {
        var out_ = new Dictionary<int, nint>();
        foreach (var p in blocks.EnumerateObject())
            out_[int.Parse(p.Name)] = (nint)p.Value.GetInt64();
        return out_;
    }
}
