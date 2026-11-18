// Mod Studio's checks of the helper's own handling of a mod's units of any battle, the items past 255 its units wear
// and its buried treasures (2.0.0, Zodi's points of 16 November 2026), run by dev/test_battle_units.py. Part of The
// Ivalice Chronicles Mod Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --battles <request.json> <report.json>
//
// The request: "program" (his program: where the helper finds its three sites, Places.FindBattleUnits); "mods", each
// {"id", "name", "folder"} (its ModStudioBattles.json read, BattleFile.ReadMod); "items" ({"<mod>/<Name>": number}),
// "kinds" ({"<number>": 0 to 5}: what each item given this time is worn as) and "jobs" ({"<mod>/<Name>": number}): what
// the game has this time; "quests", each {"mod", "who", "battle", "units": {"<place 1 to 16>": {"Head": ...}}} (a
// quest's battle's Items, BattleFile.ReadItems); "blocks" ({"<battle>": 640 bytes in hex}), "units" (each {"battle",
// "slot", "unit": a battle unit's first bytes in hex}) and "maps" ({"<map>": 24 bytes in hex}): each as the hooks
// change it (BattleFile.Apply, Wear, Bury).
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using ModStudioEventSetup;

static class BattleChecks
{
    public static int Run(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var r = request.RootElement;
        var report = new Dictionary<string, object?>
        {
            ["file"] = BattleFile.FileName, ["format"] = BattleFile.Format, ["version"] = BattleFile.Version,
            ["lastBattle"] = BattleFile.LastBattle,
        };
        if (r.TryGetProperty("program", out var program) && program.GetString() is string path && path.Length > 0)
        {
            var places = Places.Find(Program.Load(path));
            report["places"] = new Dictionary<string, object?>
            {
                ["UnitOverrides"] = places.UnitOverrides, ["UnitEquipment"] = places.UnitEquipment,
                ["MapTreasures"] = places.MapTreasures, ["TreasureTable"] = places.TreasureTable,
                ["TreasuresNow"] = places.TreasuresNow, ["UnitMade"] = places.UnitMade,
                ["EncounterNumber"] = places.EncounterNumber,
                ["MissingForUnits"] = places.MissingForUnits, ["MissingForWideItems"] = places.MissingForWideItems,
                ["MissingForTreasures"] = places.MissingForTreasures,
            };
        }
        var problems = new List<string>();
        var mods = new List<BattleFile.ModBattles>();
        var read = new List<object?>();
        if (r.TryGetProperty("mods", out var modList))
            foreach (var m in modList.EnumerateArray())
            {
                var mod = BattleFile.ReadMod(m.GetProperty("id").GetString()!, m.GetProperty("name").GetString()!,
                                             m.GetProperty("folder").GetString()!, problems);
                read.Add(mod == null ? null : new[] { mod.Units.Count, mod.Treasures.Count });
                if (mod != null)
                    mods.Add(mod);
            }
        report["read"] = read;
        var items = new Dictionary<string, int>(StringComparer.Ordinal);
        if (r.TryGetProperty("items", out var itemList))
            foreach (var p in itemList.EnumerateObject())
                items[p.Name] = p.Value.GetInt32();
        var kinds = new Dictionary<int, ItemKind>();
        if (r.TryGetProperty("kinds", out var kindList))
            foreach (var p in kindList.EnumerateObject())
                kinds[int.Parse(p.Name)] = (ItemKind)p.Value.GetInt32();
        var jobs = new Dictionary<string, int>(StringComparer.Ordinal);
        if (r.TryGetProperty("jobs", out var jobList))
            foreach (var p in jobList.EnumerateObject())
                jobs[p.Name] = p.Value.GetInt32();
        var quests = new List<BattleFile.QuestItems>();
        if (r.TryGetProperty("quests", out var questList))
            foreach (var q in questList.EnumerateArray())
            {
                var worn = new SortedDictionary<int, BattleFile.ItemRef?[]>();
                foreach (var unit in q.GetProperty("units").EnumerateObject())
                {
                    var found = BattleFile.ReadItems(unit.Value, $"{q.GetProperty("who").GetString()}'s unit {unit.Name}",
                                                     problems);
                    if (found != null)
                        worn[int.Parse(unit.Name) - 1] = found;
                }
                quests.Add(new BattleFile.QuestItems(q.GetProperty("mod").GetString()!, q.GetProperty("who").GetString()!,
                                                     q.GetProperty("battle").GetInt32(), worn));
            }
        report["problems"] = problems;
        var plan = BattleFile.Make(mods, quests, items, n => kinds.TryGetValue(n, out var kind) ? kind : BattleFile.GameKind(n),
                                   jobs);
        report["said"] = plan.Said;
        report["any"] = plan.Any;
        report["line"] = plan.Any ? BattleFile.Line(plan) : "";
        report["counts"] = new[] { plan.UnitsChanged, plan.UnitsWearing, plan.TreasuresChanged };
        var planned = new Dictionary<string, object?>();
        foreach (var (battle, units) in plan.Battles)
        {
            var slots = new Dictionary<string, object?>();
            for (int s = 0; s < units.Length; s++)
                if (units[s] != null)
                    slots[(s + 1).ToString()] = new Dictionary<string, object?>
                    {
                        ["mask"] = Convert.ToHexString(units[s]!.Mask), ["values"] = Convert.ToHexString(units[s]!.Values),
                        ["items"] = units[s]!.Items, ["kinds"] = Array.ConvertAll(units[s]!.Kinds, k => (int)k),
                        ["names"] = units[s]!.ItemNames, ["changes"] = units[s]!.Changes, ["wears"] = units[s]!.Wears,
                        ["wearsLine"] = units[s]!.Wears ? BattleFile.WearsLine($"battle {battle}", s, units[s]!) : "",
                    };
            planned[battle.ToString()] = slots;
        }
        report["battles"] = planned;
        var maps = new Dictionary<string, object?>();
        foreach (var (map, tiles) in plan.Maps)
            maps[map.ToString()] = new Dictionary<string, object?> { ["rare"] = tiles.Rare, ["common"] = tiles.Common };
        report["maps"] = maps;
        // What the hooks do, each time.
        var blocks = new Dictionary<string, object?>();
        if (r.TryGetProperty("blocks", out var blockList))
            foreach (var p in blockList.EnumerateObject())
            {
                byte[] block = Convert.FromHexString(p.Value.GetString() ?? "");
                int changed = plan.Battles.TryGetValue(int.Parse(p.Name), out var units) ? BattleFile.Apply(block, units) : -1;
                int count = 0;
                if (units != null)
                    foreach (var unit in units)
                        if (unit != null && unit.Changes)
                            count++;
                blocks[p.Name] = new Dictionary<string, object?>
                {
                    ["changed"] = changed, ["after"] = Convert.ToHexString(block),
                    ["line"] = count > 0 ? BattleFile.UnitsLine($"battle {p.Name}", count) : "",
                };
            }
        report["blocks"] = blocks;
        var worns = new List<object?>();
        if (r.TryGetProperty("units", out var unitList))
            foreach (var u in unitList.EnumerateArray())
            {
                byte[] unit = Convert.FromHexString(u.GetProperty("unit").GetString() ?? "");
                int battle = u.GetProperty("battle").GetInt32(), slot = u.GetProperty("slot").GetInt32();
                int worn = plan.Battles.TryGetValue(battle, out var units) && units[slot] != null
                    ? BattleFile.Wear(unit, units[slot]!) : -1;
                worns.Add(new Dictionary<string, object?> { ["worn"] = worn, ["after"] = Convert.ToHexString(unit) });
            }
        report["units"] = worns;
        var buried = new Dictionary<string, object?>();
        if (r.TryGetProperty("mapsNow", out var mapList))
            foreach (var p in mapList.EnumerateObject())
            {
                byte[] now = Convert.FromHexString(p.Value.GetString() ?? "");
                int changed = plan.Maps.TryGetValue(int.Parse(p.Name), out var tiles) ? BattleFile.Bury(now, tiles) : -1;
                buried[p.Name] = new Dictionary<string, object?>
                {
                    ["changed"] = changed, ["after"] = Convert.ToHexString(now),
                    ["line"] = BattleFile.TreasuresLine(int.Parse(p.Name)),
                };
            }
        report["mapsNow"] = buried;
        var slots_ = new List<int>();
        if (r.TryGetProperty("entries", out var entryList))
            foreach (var e in entryList.EnumerateArray())
                slots_.Add(BattleFile.SlotOf((nint)e[0].GetInt64(), (nint)e[1].GetInt64()));
        report["entries"] = slots_;
        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }
}
