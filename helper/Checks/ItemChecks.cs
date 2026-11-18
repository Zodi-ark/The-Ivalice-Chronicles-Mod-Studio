// Mod Studio's checks of the helper: (1.26.0) a mod's own items (ItemFile.cs,
// ItemRoom.cs) over his program laid out as the game lays it out, as the game
// has it or as WotL Restoration's page leaves it (`moved`: its bounds and its
// reaches as its strings say it changes them, its page at an address of the
// request's). dev/test_side_quests.py reads the report and runs the native
// code and his program's own code over it with unicorn. Part of The Ivalice
// Chronicles Mod Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --items <request.json> <report.json>
//
// The request: {"program", "moved": a page's address or 0, "data", "page", "lowTest" (addresses from the program's
// start), "firstRow", "numbers" (a file or ""), "mods": [{"id", "name", "folder"}], "table" (an Item table's .nxd or
// ""), "counts": [[bag 66 bytes hex, bank 1024 bytes hex, atSave] ...] (a sequence run through one Counts), (2.0.0,
// optional) "lions": true (War of the Lions' items planned as Mod.PlanItems plans them: each mod's
// ModStudioWotLItems.json read, the 40 given their rows before the mods' own items', their block at "lionsData",
// "lionsCounts" a sequence run through one WotLItems.Counts, each [bag 55 bytes hex, bank 1024 bytes hex, atSave]), and
// (1.27.0, optional) "stock": [{"items", "category", "listed", "storyPoint", "mode", "cantUse"} ...] (the words a game
// town's Outfitter's list gets for each, ItemRoom.Appended: "cantUse" the items the unit can't use)}.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using ModStudioEventSetup;

static class ItemChecks
{
    public const ulong PreferredBase = 0x140000000;

    static string Hex(ReadOnlySpan<byte> bytes) => Convert.ToHexString(bytes);

    public static int Run(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var r = request.RootElement;
        var image = Program.Load(r.GetProperty("program").GetString()!);
        long moved = r.GetProperty("moved").GetInt64();
        var report = new Dictionary<string, object?>();
        if (moved != 0)
            report["wotl"] = Wotl(image, moved);
        var sections = Finder.Sections(image);
        var found = ItemRoom.Find(image, sections);
        report["missing"] = found.Missing;
        report["moved"] = found.Moved;
        report["at"] = found.At;
        report["arrays"] = found.Array;
        report["values"] = found.Values;
        report["slotsAt"] = found.SlotsAt;
        report["reaches"] = found.Reaches.Count;
        var items = new List<ModItem>();
        var problems = new List<string>();
        foreach (var mod in r.GetProperty("mods").EnumerateArray())
            items.AddRange(ItemFile.ReadMod(mod.GetProperty("id").GetString()!, mod.GetProperty("name").GetString()!,
                                            mod.GetProperty("folder").GetString()!, problems));
        report["problems"] = problems;
        // (1.28.0) The mods' looks for the game's weapons, read and planned as the helper reads and plans them.
        var lookProblems = new List<string>();
        var allLooks = new List<ItemLook>();
        foreach (var mod in r.GetProperty("mods").EnumerateArray())
            allLooks.AddRange(ItemLooks.ReadMod(mod.GetProperty("id").GetString()!, mod.GetProperty("name").GetString()!,
                                                mod.GetProperty("folder").GetString()!, lookProblems));
        var looksSaid = new List<string>();
        var plannedLooks = ItemLooks.Plan(allLooks, looksSaid);
        report["lookProblems"] = lookProblems;
        report["looksSaid"] = looksSaid;
        report["looks"] = plannedLooks.ConvertAll(l => (object)new object[] { l.Item, Hex(l.Pair), l.ModName });
        report["lookLines"] = plannedLooks.ConvertAll(l => ItemLooks.Line(l, new byte[] { 0x70, 0x02 }));
        string numbersPath = r.GetProperty("numbers").GetString() ?? "";
        var numbers = numbersPath.Length > 0 && File.Exists(numbersPath)
            ? Numbers.FromText(File.ReadAllText(numbersPath), problems) : new Numbers();
        var said = new List<string>();
        // (2.0.0) War of the Lions' items, as Mod.PlanItems plans them: asked for by a mod's file, WotL Restoration's
        // where its page is made, their rows before the mods' own items'.
        int firstRow = r.GetProperty("firstRow").GetInt32();
        var lions = new List<ItemRoom.Given>();
        if (r.TryGetProperty("lions", out var lionsAsked) && lionsAsked.ValueKind == JsonValueKind.True)
        {
            bool asked = false;
            var changed = new Dictionary<int, ModItem>();
            var theirProblems = new List<string>();
            foreach (var mod in r.GetProperty("mods").EnumerateArray())
            {
                var theirs = WotLItems.ReadMod(mod.GetProperty("id").GetString()!, mod.GetProperty("name").GetString()!,
                                               mod.GetProperty("folder").GetString()!, theirProblems);
                if (theirs == null)
                    continue;
                asked = true;
                foreach (var (number, item) in theirs)
                    changed[number] = item;
            }
            var lionsSaid = new List<string>();
            string lionsLine = "";
            if (asked && found.Moved)
                lionsLine = WotLItems.TheirsLine;
            else if (asked)
            {
                lions = WotLItems.Plan(firstRow, changed, lionsSaid, out firstRow);
                int theirs = 0;
                foreach (var g in lions)
                    if (g.Item.ModId != WotLItems.ModId)
                        theirs++;
                if (lions.Count > 0)
                    lionsLine = WotLItems.Line(lions, theirs);
            }
            var lionsOut = new List<object>();
            foreach (var g in lions)
                lionsOut.Add(new Dictionary<string, object>
                {
                    ["key"] = g.Item.Key, ["mod"] = g.Item.ModId, ["name"] = g.Item.Name, ["number"] = g.Number,
                    ["row"] = g.Row, ["kind"] = (int)g.Item.Kind, ["record"] = Hex(ItemRoom.Record(g)),
                    ["kindRecord"] = Hex(g.Item.KindRecord), ["pair"] = Hex(g.Item.SpritePair),
                    ["bonus"] = g.Item.Bonus == null ? "" : Hex(g.Item.Bonus), ["icon"] = g.Item.Icon,
                    ["iconPicture"] = g.Item.IconPicture, ["row40"] = Hex(ItemRoom.ItemRow(g.Item, g.Number)),
                    ["uiCategory"] = g.Item.UiCategory, ["sort"] = g.Item.Sort, ["uiStatus"] = g.Item.UiStatus,
                    ["randomDamage"] = g.Item.RandomDamage, ["description"] = g.Item.Description,
                });
            ulong lionsAt = r.TryGetProperty("lionsData", out var at) ? (ulong)at.GetInt64() : 0;
            var lionsCounts = new WotLItems.Counts();
            var lionsSteps = new List<object>();
            if (r.TryGetProperty("lionsCounts", out var theirSteps))
                foreach (var step in theirSteps.EnumerateArray())
                {
                    var bag = new byte[ItemRoom.LastItem + 1];
                    Convert.FromHexString(step[0].GetString()!).CopyTo(bag, WotLItems.First);
                    var bank = Convert.FromHexString(step[1].GetString()!);
                    int done = lionsCounts.Sync(bag, bank, step[2].GetBoolean());
                    lionsSteps.Add(new Dictionary<string, object>
                    {
                        ["done"] = done, ["bag"] = Hex(bag.AsSpan(WotLItems.First, WotLItems.Count)), ["bank"] = Hex(bank),
                    });
                }
            report["lions"] = new Dictionary<string, object>
            {
                ["asked"] = asked, ["problems"] = theirProblems, ["said"] = lionsSaid, ["line"] = lionsLine,
                ["given"] = lionsOut, ["nextRow"] = firstRow,
                ["data"] = lions.Count == 0 ? "" : Hex(ItemRoom.Data(lions, lionsAt, WotLItems.First)),
                ["code"] = lions.Count == 0 ? "" : Hex(ItemRoom.Code(lionsAt, out _, WotLItems.First, WotLItems.Count)),
                ["counts"] = lionsSteps, ["first"] = WotLItems.First, ["count"] = WotLItems.Count,
                ["tail"] = WotLItems.Tail, ["magic"] = Hex(WotLItems.TailMagic),
            };
        }
        var given = ItemRoom.Plan(items, numbers, firstRow, said);
        report["said"] = said;
        var all = new List<ItemRoom.Given>(lions);
        all.AddRange(given);
        // (1.35.0, optional "stamp") The numbers stamped as the helper keeps them once its items are given (Mod.PlanItems):
        // a mark for the items' numbers no name had.
        if (r.TryGetProperty("stamp", out var stamp) && stamp.ValueKind == JsonValueKind.True)
        {
            report["stamped"] = numbers.Stamp();
            report["numbersId"] = numbers.Id;
        }
        var lines = new List<string>();
        foreach (var g in given)
            lines.Add(ItemRoom.Line(g));
        report["lines"] = lines;
        var givenOut = new List<object>();
        foreach (var g in given)
            givenOut.Add(new Dictionary<string, object>
            {
                ["key"] = g.Item.Key, ["number"] = g.Number, ["row"] = g.Row, ["kind"] = (int)g.Item.Kind,
                ["record"] = Hex(ItemRoom.Record(g)), ["kindRecord"] = Hex(g.Item.KindRecord),
                ["pair"] = Hex(g.Item.SpritePair), ["bonus"] = g.Item.Bonus == null ? "" : Hex(g.Item.Bonus),
                ["icon"] = g.Item.Icon, ["iconPath"] = g.Item.IconPicture.Length > 0
                    ? new[] { ItemIconPath(g.Item.IconPicture, false), ItemIconPath(g.Item.IconPicture, true) }
                    : Array.Empty<string>(),
                ["row40"] = Hex(ItemRoom.ItemRow(g.Item, g.Number)),
                ["shops"] = g.Item.Shops, ["uiStatus"] = g.Item.UiStatus, ["randomDamage"] = g.Item.RandomDamage,
            });
        report["given"] = givenOut;
        // (1.27.0) The game's towns' Outfitters: the towns selling each item and what is said of it, then the words a
        // list gets for each case asked.
        var townItems = new Dictionary<string, List<int>>();
        foreach (var (town, sold) in ItemRoom.TownItems(given))
            townItems[town.ToString()] = sold;
        report["townItems"] = townItems;
        // (Test 126) The game's towns' Outfitters as the running framework stocks them: War of the Lions' 40 and the
        // mods' own items together (ItemHooks' _all), so one of the 40 a mod's version sells is held too.
        var townItemsAll = new Dictionary<string, List<int>>();
        foreach (var (town, sold) in ItemRoom.TownItems(all))
            townItemsAll[town.ToString()] = sold;
        report["townItemsAll"] = townItemsAll;
        var shopsLines = new List<string>();
        foreach (var g in given)
            if (g.Item.Shops.Length > 0)
                shopsLines.Add(ItemRoom.ShopsLine(g));
        report["shopsLines"] = shopsLines;
        if (r.TryGetProperty("stock", out var stock))
        {
            var byNumber = new Dictionary<int, ItemRoom.Given>();
            foreach (var g in given)
                byNumber[g.Number] = g;
            var appended = new List<object>();
            foreach (var c in stock.EnumerateArray())
            {
                var asked = new List<int>();
                foreach (var n in c.GetProperty("items").EnumerateArray())
                    asked.Add(n.GetInt32());
                var cantUse = new HashSet<int>();
                foreach (var n in c.GetProperty("cantUse").EnumerateArray())
                    cantUse.Add(n.GetInt32());
                int mode = c.GetProperty("mode").GetInt32();
                appended.Add(ItemRoom.Appended(asked, n => byNumber.TryGetValue(n, out var g) ? g : null,
                                               (short)c.GetProperty("category").GetInt32(),
                                               c.GetProperty("listed").GetInt32(), c.GetProperty("storyPoint").GetInt32(),
                                               mode == 0 ? null : n => cantUse.Contains(n) ? -1 : 0, mode));
            }
            report["appended"] = appended;
        }
        report["numbersText"] = numbers.Text();
        ulong dataAt = (ulong)r.GetProperty("data").GetInt64();
        report["data"] = Hex(ItemRoom.Data(given, dataAt));
        report["code"] = Hex(ItemRoom.Code(dataAt, out int[] starts));
        report["starts"] = starts;
        report["layout"] = new Dictionary<string, int>
        {
            ["valid"] = ItemRoom.ValidAt, ["segment"] = ItemRoom.SegmentAt, ["commons"] = ItemRoom.CommonsAt,
            ["kinds"] = ItemRoom.KindsAt, ["pairs"] = ItemRoom.PairsAt, ["zero"] = ItemRoom.ZeroAt,
            ["slots"] = ItemRoom.SlotsAt, ["bytes"] = ItemRoom.DataBytes,
        };
        if (found.Ok)
        {
            long page = r.GetProperty("page").GetInt64(), lowTest = r.GetProperty("lowTest").GetInt64();
            var patches = ItemRoom.Patches(image, found, found.Moved ? 0 : page, found.Moved ? 0 : lowTest,
                                           out string why);
            report["patchesWhy"] = why;
            var patchesOut = new List<object>();
            foreach (var p in patches ?? new List<ItemRoom.Patch>())
                patchesOut.Add(new Dictionary<string, object>
                {
                    ["at"] = p.At, ["old"] = Hex(p.Old), ["new"] = Hex(p.New), ["what"] = p.What,
                });
            report["patches"] = patchesOut;
            var lists = ItemRoom.Lists(image, found, PreferredBase);
            report["lists"] = lists;
            if (!found.Moved && !Array.Exists(lists, l => l < 0))
                report["page"] = Hex(ItemRoom.Page(image, found, lists, all));
        }
        string tablePath = r.GetProperty("table").GetString() ?? "";
        if (tablePath.Length > 0 && File.Exists(tablePath))
        {
            var rowsSaid = new List<string>();
            var table = ItemRoom.WithItemRows(File.ReadAllBytes(tablePath), all, rowsSaid, out string tableWhy);
            report["table"] = table == null ? null : Hex(table);
            report["tableWhy"] = tableWhy;
            report["tableSaid"] = rowsSaid;
        }
        // The counts kept in the save: one Counts run through each step given.
        var counts = new ItemRoom.Counts();
        var steps = new List<object>();
        foreach (var step in r.GetProperty("counts").EnumerateArray())
        {
            var bag = new byte[ItemRoom.LastItem + 1];
            Convert.FromHexString(step[0].GetString()!).CopyTo(bag, ItemRoom.FirstItem);
            var bank = Convert.FromHexString(step[1].GetString()!);
            int done = counts.Sync(bag, bank, step[2].GetBoolean());
            steps.Add(new Dictionary<string, object>
            {
                ["done"] = done, ["bag"] = Hex(bag.AsSpan(ItemRoom.FirstItem, ItemRoom.Count)), ["bank"] = Hex(bank),
            });
        }
        report["counts"] = steps;
        var flagsFree = new List<int>();
        for (int bit = 0; bit < Framework.FlagBits; bit++)
            if (!ItemRoom.FlagFree(bit))
                flagsFree.Add(bit);
        report["flagsNotFree"] = flagsFree;
        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }

    /// <summary>An item's own icon's path (ItemHooks.ItemIconPath's words, ItemHooks being the game's side).</summary>
    static string ItemIconPath(string picture, bool small)
        => small ? $"UITextureParts://ui/ffto/icon/equip_item_s/textureparts/{picture}_s"
                 : $"UITextureParts://ui/ffto/icon/equip_item/textureparts/{picture}";

    /// <summary>His program as WotL Restoration's item expansion leaves it (its strings' facts, dev/research/sidequests/
    /// items.py): each bound at its value, each of its 63 reaches pointed at its page (`page`, from the program's start:
    /// its bag at + 0, its owned copy at + 0x800, its bonus rows at + 0x1000, its all-items list at + 0x3000), its two
    /// calls of the item test elsewhere. Changed in place; what was changed said.</summary>
    static Dictionary<string, object> Wotl(byte[] image, long page)
    {
        var sections = Finder.Sections(image);
        var found = ItemRoom.Find(image, sections);
        var wotl = new Dictionary<string, int>
        {
            ["count"] = 0x13C, ["last"] = 0x13B, ["lastless"] = 0x13A, ["lea6"] = 0x3D, ["ax4"] = 0x3B, ["row"] = 0xFF,
            ["blocks"] = 8, ["stride"] = 0x78,
        };
        var pageOf = new Dictionary<string, int> { ["bag"] = 0, ["owned"] = 0x800, ["attribute"] = 0x1000, ["allitems"] = 0x3000 };
        int bounds = 0, reaches = 0, calls = 0;
        foreach (var s in ItemRoom.Sites)
        {
            if (!found.At.TryGetValue(s.Name, out int at))
                continue;
            if (s.Bound)
            {
                int v = wotl[s.Kind];
                if (s.Width == 1)
                    image[at + s.Operand] = (byte)v;
                else
                    BinaryPrimitives.WriteInt32LittleEndian(image.AsSpan(at + s.Operand), v);
                bounds++;
            }
            else if (s.Kind == "call")
            {
                BinaryPrimitives.WriteInt32LittleEndian(image.AsSpan(at + 1), (int)(page + 0xE400 - (at + 5)));
                calls++;
            }
        }
        foreach (var (at, s) in found.Reaches)
        {
            long to = page + pageOf[s.Array] + s.Offset;
            long disp = s.Kind == "rip" ? to - (at + s.Size) : to;
            BinaryPrimitives.WriteInt32LittleEndian(image.AsSpan(at + s.Operand), (int)disp);
            reaches++;
        }
        return new Dictionary<string, object> { ["bounds"] = bounds, ["reaches"] = reaches, ["calls"] = calls,
                                                ["missing"] = found.Missing };
    }
}
