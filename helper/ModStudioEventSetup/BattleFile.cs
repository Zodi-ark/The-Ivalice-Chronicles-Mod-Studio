// Mod Studio Framework: (2.0.0) a mod's units for any battle, and its buried
// treasures. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi's points of 16 November 2026. His third: "The ENTD only supports a
// limited amount of override slots, can we overcome this and allow users to
// override every single 16 unit slot for every battle." His first, of War of
// the Lions' items and a mod's own: "can be used in Encounters page and
// modders new Battles and for Treasure Hunter".
//
// What was measured in his program (read as data, never run;
// dev/research/sidequests/battle_units.py):
//
// - A battle's 16 units are 40 bytes each in its battle file. As a battle
//   loads (0x30428C) the game takes the battle's block (0x28416C), then,
//   in the mode it applies its own changes in (the dword at 0x7D453C),
//   looks its OverrideEntryData row up for each of the 16 places by the
//   battle and the place (0x1EA574: no count of rows anywhere) and writes
//   the row's columns into the entry (0x1EA638), then makes the units
//   (0x27128C). A row has no column for an entry's name, birthday, palette,
//   team, war trophy, gil or AI, so a row alone can't make a unit where the
//   battle file has none.
// - A unit's equipment is five BYTES in its entry (+ 0x12 head, body,
//   accessory, right hand, left hand), read as bytes by the one function
//   that puts them on (0x277564, called once, from the unit's making, before
//   its stats are worked out), and five bytes too in a row's columns as the
//   game reads them. The unit itself keeps WORDS (+ 0x1A head, + 0x1C body,
//   + 0x1E accessory, + 0x20 and + 0x22 the right hand's weapon and shield,
//   + 0x24 and + 0x26 the left's).
// - A map's buried treasures are four records of 6 bytes in the program's
//   own table (0x783840, 128 maps): the tile, its flags, and the rare and
//   the common item as WORDS, copied as the map loads (0x251584) to where
//   the battle reads them (0xD8DC90), as words.
//
// So this file, `ModStudioBattles.json` at a mod's root, read here:
//
//   { "Format": "Mod Studio battles", "Version": 1,
//     "Units": [ { "Battle": 387, "Unit": 5,
//                  "Mask": "<40 bytes in hex>", "Values": "<40 bytes in hex>",
//                  "Job": "Battlemage",
//                  "Head": 293, "RightHand": "Moon Sword" } ],
//     "Treasures": [ { "Map": 74, "Tile": 2, "Rare": 262,
//                      "Common": "Moon Sword" } ] }
//
// A unit: one of a game's battle's 16 (Battle: its number in the game's
// battle files; Unit: 1 to 16). `Mask` and `Values` are its 40 bytes as the
// mod has them: where a bit of Mask is set, the entry's bit is Values'. The
// framework writes them after the game's own changes (its hook of 0x1EA574,
// the game's function first), so they are made exactly where the game makes
// its own, and a place the battle file leaves empty is a unit like any
// other. `Job`: one of its mod's own jobs by its Name, the number it was
// given written as the unit's job. `Head`, `Body`, `Accessory`, `RightHand`
// and `LeftHand`: an item past the 255 a byte holds, by its number (the
// game's own five, 256 to 260, and War of the Lions', 261 to 315) or by the
// Name of one of its mod's own items, put on the unit as words right after
// the game put its entry's bytes on (the framework's hook of 0x277564).
//
// A treasure: one of a map's four (Map: 0 to 127; Tile: 1 to 4). `Rare` and
// `Common`: an item past 255, by its number or its mod's item's Name, written
// over the battle's copy as the map loads (the framework's hook of 0x251584,
// the game's function first), whatever a table of another mod's put there.
//
// A quest's own battle names its units' items past 255 the same way
// (QuestFile.cs: its battle's `Items`).
//
// What can't be used is left out and said, in words. A later mod's bits,
// job and items stand over an earlier's for the same unit, and its item for
// the same tile.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.Json;

namespace ModStudioEventSetup
{
    public static class BattleFile
    {
        public const string FileName = "ModStudioBattles.json";
        public const string Format = "Mod Studio battles";
        public const int Version = 1;
        /// <summary>A battle's units and an entry's bytes; the last battle a mod may name (the quests' own are numbered
        /// from Framework.FirstBattle); the maps and a map's treasures.</summary>
        public const int Units = 16, EntryBytes = 40, LastBattle = Framework.FirstBattle - 1, Maps = 128, Tiles = 4;
        /// <summary>The five places a unit wears an item, as the file names them, and each one's byte in an entry.</summary>
        public static readonly string[] Places = { "Head", "Body", "Accessory", "RightHand", "LeftHand" };
        public static readonly string[] PlaceWords = { "head", "body", "accessory", "right hand", "left hand" };
        public const int EntryItemsAt = 0x12, EntryJobAt = 10;
        /// <summary>The first item a byte can't hold, the game's own last (Ring of Aptitude) and the last of the mods'.
        /// </summary>
        public const int FirstWide = 256, LastGame = 260;
        /// <summary>A battle unit's equipment, as the game keeps it: words (0xFF: none).</summary>
        public const int UnitHead = 0x1A, UnitBody = 0x1C, UnitAccessory = 0x1E, UnitRightWeapon = 0x20,
                         UnitRightShield = 0x22, UnitLeftWeapon = 0x24, UnitLeftShield = 0x26, UnitBytes = 0x28, None = 0xFF;
        /// <summary>A map's treasures as the battle reads them: 6 bytes each, its rare item a word at + 2, its common
        /// one at + 4.</summary>
        public const int TreasureBytes = 6, RareAt = 2, CommonAt = 4;
        /// <summary>The game's own five items past 255, by what each is worn as (his program's item boundaries: 256 and
        /// 257 weapons, 258 a head's, 259 a body's, 260 an accessory).</summary>
        public static ItemKind? GameKind(int number) => number switch
        {
            256 or 257 => ItemKind.Weapon,
            258 => ItemKind.Head,
            259 => ItemKind.Body,
            260 => ItemKind.Accessory,
            _ => null,
        };

        /// <summary>An item as a file names it: its number, or its mod's own item's Name.</summary>
        public readonly struct ItemRef
        {
            public int Number { get; }
            public string Name { get; }
            public ItemRef(int number, string name)
            {
                Number = number;
                Name = name;
            }
            public bool Named => Name.Length > 0;
            public override string ToString() => Named ? Name : Number.ToString(CultureInfo.InvariantCulture);
        }

        /// <summary>A unit as a mod has it.</summary>
        public sealed class UnitEdit
        {
            public string ModId { get; }
            public string ModName { get; }
            public int Battle { get; }
            public int Slot { get; }
            public byte[] Mask { get; }
            public byte[] Values { get; }
            public string Job { get; }
            public ItemRef?[] Items { get; }

            public UnitEdit(string modId, string modName, int battle, int slot, byte[] mask, byte[] values, string job,
                            ItemRef?[] items)
            {
                ModId = modId;
                ModName = modName;
                Battle = battle;
                Slot = slot;
                Mask = mask;
                Values = values;
                Job = job;
                Items = items;
            }
        }

        /// <summary>A buried treasure as a mod has it.</summary>
        public sealed class Treasure
        {
            public string ModId { get; }
            public string ModName { get; }
            public int Map { get; }
            public int Tile { get; }
            public ItemRef? Rare { get; }
            public ItemRef? Common { get; }

            public Treasure(string modId, string modName, int map, int tile, ItemRef? rare, ItemRef? common)
            {
                ModId = modId;
                ModName = modName;
                Map = map;
                Tile = tile;
                Rare = rare;
                Common = common;
            }
        }

        /// <summary>A quest's own battle's units' items past 255 (QuestFile's battle's Items), by the number its battle
        /// was given.</summary>
        public sealed class QuestItems
        {
            public string ModId { get; }
            public string Who { get; }
            public int Battle { get; }
            public SortedDictionary<int, ItemRef?[]> Items { get; }

            public QuestItems(string modId, string who, int battle, SortedDictionary<int, ItemRef?[]> items)
            {
                ModId = modId;
                Who = who;
                Battle = battle;
                Items = items;
            }
        }

        public sealed class ModBattles
        {
            public List<UnitEdit> Units { get; } = new List<UnitEdit>();
            public List<Treasure> Treasures { get; } = new List<Treasure>();
        }

        static bool Has(JsonElement e, string name, out JsonElement value)
        {
            value = default;
            return e.ValueKind == JsonValueKind.Object && e.TryGetProperty(name, out value);
        }

        static bool Whole(JsonElement e, string name, out int value)
        {
            value = 0;
            return Has(e, name, out var v) && v.ValueKind == JsonValueKind.Number && v.TryGetInt32(out value);
        }

        /// <summary>A mod's file, or null for a mod that has none.</summary>
        public static ModBattles? ReadMod(string modId, string modName, string modFolder, List<string> problems)
        {
            string path = Path.Combine(modFolder, FileName);
            if (!File.Exists(path))
                return null;
            string text;
            try
            {
                text = File.ReadAllText(path);
            }
            catch (Exception e) when (e is IOException || e is UnauthorizedAccessException)
            {
                problems.Add($"{modName}'s {FileName} can't be read ({e.Message})");
                return new ModBattles();
            }
            return Read(modId, modName, text, problems);
        }

        /// <summary>An item a unit wears or a tile holds, as an entry names it under `key`: a number past 255 (the game's
        /// own five and War of the Lions' numbers) or an item's Name. `found`: null where the entry has no such key.
        /// False, and why, for one that is neither.</summary>
        public static bool ReadItem(JsonElement entry, string key, string what, List<string> problems, out ItemRef? found)
        {
            found = null;
            if (!Has(entry, key, out var value) || value.ValueKind == JsonValueKind.Null)
                return true;
            if (value.ValueKind == JsonValueKind.Number && value.TryGetInt32(out int number))
            {
                if (number < FirstWide || number > WotLItems.Last)
                {
                    problems.Add($"{what}'s {key} is an item past the 255 a byte holds by its number ({FirstWide} to "
                                 + $"{WotLItems.Last}) or the Name of one of its mod's own items, not {number}");
                    return false;
                }
                found = new ItemRef(number, "");
                return true;
            }
            string? name = value.ValueKind == JsonValueKind.String ? value.GetString() : null;
            if (name == null || !ItemFile.GoodName(name))
            {
                problems.Add($"{what}'s {key} is an item past the 255 a byte holds by its number ({FirstWide} to "
                             + $"{WotLItems.Last}) or the Name of one of its mod's own items, not {value.GetRawText()}");
                return false;
            }
            found = new ItemRef(0, name);
            return true;
        }

        /// <summary>The five places' items of a unit's entry (`what`: the unit in words); null, and why, when one can't
        /// be used.</summary>
        public static ItemRef?[]? ReadItems(JsonElement entry, string what, List<string> problems)
        {
            var items = new ItemRef?[Places.Length];
            for (int p = 0; p < Places.Length; p++)
                if (!ReadItem(entry, Places[p], what, problems, out items[p]))
                    return null;
            return items;
        }

        static byte[]? Hex(JsonElement entry, string key)
        {
            if (!Has(entry, key, out var value) || value.ValueKind != JsonValueKind.String)
                return null;
            string text = value.GetString() ?? "";
            if (text.Length != 2 * EntryBytes)
                return null;
            var bytes = new byte[EntryBytes];
            for (int i = 0; i < EntryBytes; i++)
                if (!byte.TryParse(text.AsSpan(2 * i, 2), NumberStyles.AllowHexSpecifier, CultureInfo.InvariantCulture,
                                   out bytes[i]))
                    return null;
            return bytes;
        }

        public static ModBattles Read(string modId, string modName, string text, List<string> problems)
        {
            var read = new ModBattles();
            JsonDocument document;
            try
            {
                document = JsonDocument.Parse(text);
            }
            catch (JsonException e)
            {
                problems.Add($"{modName}'s {FileName} isn't JSON ({e.Message})");
                return read;
            }
            using (document)
            {
                var root = document.RootElement;
                if (!Has(root, "Format", out var format) || format.ValueKind != JsonValueKind.String
                    || format.GetString() != Format)
                {
                    problems.Add($"{modName}'s {FileName}: its Format isn't \"{Format}\"");
                    return read;
                }
                if (!Whole(root, "Version", out int version) || version != Version)
                {
                    problems.Add($"{modName}'s {FileName}: its Version isn't {Version}");
                    return read;
                }
                if (Has(root, "Units", out var units))
                {
                    if (units.ValueKind != JsonValueKind.Array)
                        problems.Add($"{modName}'s {FileName}: its Units isn't a list");
                    else
                    {
                        int place = 0;
                        var seen = new HashSet<(int, int)>();
                        foreach (var entry in units.EnumerateArray())
                        {
                            place++;
                            var unit = ReadUnit(modId, modName, entry, place, problems);
                            if (unit == null)
                                continue;
                            if (!seen.Add((unit.Battle, unit.Slot)))
                            {
                                problems.Add($"{modName}'s {FileName} gives unit {unit.Slot + 1} of battle {unit.Battle} "
                                             + "twice");
                                continue;
                            }
                            read.Units.Add(unit);
                        }
                    }
                }
                if (Has(root, "Treasures", out var treasures))
                {
                    if (treasures.ValueKind != JsonValueKind.Array)
                        problems.Add($"{modName}'s {FileName}: its Treasures isn't a list");
                    else
                    {
                        int place = 0;
                        var seen = new HashSet<(int, int)>();
                        foreach (var entry in treasures.EnumerateArray())
                        {
                            place++;
                            var treasure = ReadTreasure(modId, modName, entry, place, problems);
                            if (treasure == null)
                                continue;
                            if (!seen.Add((treasure.Map, treasure.Tile)))
                            {
                                problems.Add($"{modName}'s {FileName} gives treasure {treasure.Tile + 1} of map "
                                             + $"{treasure.Map} twice");
                                continue;
                            }
                            read.Treasures.Add(treasure);
                        }
                    }
                }
            }
            return read;
        }

        static UnitEdit? ReadUnit(string modId, string modName, JsonElement entry, int place, List<string> problems)
        {
            if (!Whole(entry, "Battle", out int battle) || battle < 0 || battle > LastBattle
                || !Whole(entry, "Unit", out int unit) || unit < 1 || unit > Units)
            {
                problems.Add($"{modName}'s {FileName}: its unit {place} names no unit of a battle (Battle: 0 to "
                             + $"{LastBattle}; Unit: 1 to {Units})");
                return null;
            }
            string what = $"{modName}'s unit {unit} of battle {battle}";
            byte[] mask = new byte[EntryBytes], values = new byte[EntryBytes];
            bool hasMask = Has(entry, "Mask", out _), hasValues = Has(entry, "Values", out _);
            if (hasMask || hasValues)
            {
                var m = Hex(entry, "Mask");
                var v = Hex(entry, "Values");
                if (m == null || v == null)
                {
                    problems.Add($"{what}: its Mask and Values are each an entry's {EntryBytes} bytes in hex "
                                 + $"({2 * EntryBytes} digits)");
                    return null;
                }
                for (int i = 0; i < EntryBytes; i++)
                    if ((v[i] & ~m[i]) != 0)
                    {
                        problems.Add($"{what}: its Values has a bit its Mask doesn't (byte {i})");
                        return null;
                    }
                mask = m;
                values = v;
            }
            string job = "";
            if (Has(entry, "Job", out var named) && named.ValueKind != JsonValueKind.Null)
            {
                string? text = named.ValueKind == JsonValueKind.String ? named.GetString() : null;
                if (text == null || !JobFile.GoodJobName(text))
                {
                    problems.Add($"{what}: its Job isn't a job's Name: 1 to {JobFile.NameMost} characters, none a control "
                                 + "character");
                    return null;
                }
                job = text;
            }
            var items = ReadItems(entry, what, problems);
            if (items == null)
                return null;
            bool any = job.Length > 0;
            foreach (byte b in mask)
                any |= b != 0;
            foreach (var item in items)
                any |= item != null;
            if (!any)
            {
                problems.Add($"{what} changes nothing (no bit of Mask, no Job, no item)");
                return null;
            }
            return new UnitEdit(modId, modName, battle, unit - 1, mask, values, job, items);
        }

        static Treasure? ReadTreasure(string modId, string modName, JsonElement entry, int place, List<string> problems)
        {
            if (!Whole(entry, "Map", out int map) || map < 0 || map >= Maps
                || !Whole(entry, "Tile", out int tile) || tile < 1 || tile > Tiles)
            {
                problems.Add($"{modName}'s {FileName}: its treasure {place} names no treasure of a map (Map: 0 to "
                             + $"{Maps - 1}; Tile: 1 to {Tiles})");
                return null;
            }
            string what = $"{modName}'s treasure {tile} of map {map}";
            if (!ReadItem(entry, "Rare", what, problems, out var rare)
                || !ReadItem(entry, "Common", what, problems, out var common))
                return null;
            if (rare == null && common == null)
            {
                problems.Add($"{what} names no item (Rare, Common)");
                return null;
            }
            return new Treasure(modId, modName, map, tile - 1, rare, common);
        }

        // --- what the mods' files come to ----------------------------------------------------------------------------

        /// <summary>A unit as the game is given it: its entry's bits, and the words put on it (0: the place is left as
        /// the game put it on).</summary>
        public sealed class UnitPlan
        {
            public byte[] Mask { get; } = new byte[EntryBytes];
            public byte[] Values { get; } = new byte[EntryBytes];
            public int[] Items { get; } = new int[5];
            public ItemKind[] Kinds { get; } = new ItemKind[5];
            public string[] ItemNames { get; } = { "", "", "", "", "" };
            public bool Changes
            {
                get
                {
                    foreach (byte b in Mask)
                        if (b != 0)
                            return true;
                    return false;
                }
            }
            public bool Wears
            {
                get
                {
                    foreach (int i in Items)
                        if (i != 0)
                            return true;
                    return false;
                }
            }
        }

        /// <summary>A map's four treasures as the battle is given them: each one's rare and common item (0: left as the
        /// game has it).</summary>
        public sealed class TreasurePlan
        {
            public int[] Rare { get; } = new int[Tiles];
            public int[] Common { get; } = new int[Tiles];
        }

        public sealed class Plan
        {
            public Dictionary<int, UnitPlan?[]> Battles { get; } = new Dictionary<int, UnitPlan?[]>();
            public Dictionary<int, TreasurePlan> Maps { get; } = new Dictionary<int, TreasurePlan>();
            public List<string> Said { get; } = new List<string>();
            public int UnitsChanged, UnitsWearing, TreasuresChanged;
            public bool Any => Battles.Count > 0 || Maps.Count > 0;

            public UnitPlan Unit(int battle, int slot)
            {
                if (!Battles.TryGetValue(battle, out var units))
                    Battles[battle] = units = new UnitPlan?[Units];
                return units[slot] ??= new UnitPlan();
            }
        }

        /// <summary>An item a file names, as a number the game knows now and what it is worn as; 0, and why (`said`),
        /// for one no mod gives the game this time. `itemNumbers`: every item given, by its mod and Name; `kindOf`:
        /// what a number is worn as, null for a number that is no item now.</summary>
        static int Resolve(ItemRef item, string modId, string what, IReadOnlyDictionary<string, int> itemNumbers,
                           Func<int, ItemKind?> kindOf, List<string> said, out ItemKind kind, out string name)
        {
            kind = ItemKind.Item;
            name = item.ToString();
            int number = item.Number;
            if (item.Named && !itemNumbers.TryGetValue($"{modId}/{item.Name}", out number))
            {
                said.Add($"{what} isn't {item.Name}: its mod gives the game no item of that Name this time");
                return 0;
            }
            var found = kindOf(number);
            if (found == null)
            {
                said.Add(WotLItems.Of(number) != null
                    ? $"{what} isn't item {number} ({WotLItems.Of(number)!.Name}): War of the Lions' items aren't given "
                      + "this time"
                    : $"{what} isn't item {number}: the game has no such item");
                return 0;
            }
            kind = found.Value;
            return number;
        }

        static bool Fits(int place, ItemKind kind) => place switch
        {
            0 => kind == ItemKind.Head,
            1 => kind == ItemKind.Body,
            2 => kind == ItemKind.Accessory,
            _ => kind == ItemKind.Weapon || kind == ItemKind.Shield,
        };

        static void Wear(UnitPlan unit, ItemRef?[] items, string modId, string who, IReadOnlyDictionary<string, int> numbers,
                         Func<int, ItemKind?> kindOf, List<string> said)
        {
            for (int p = 0; p < Places.Length; p++)
            {
                if (items[p] == null)
                    continue;
                string what = $"{who}'s {PlaceWords[p]}";
                int number = Resolve(items[p]!.Value, modId, what, numbers, kindOf, said, out var kind, out string name);
                if (number == 0)
                    continue;
                if (!Fits(p, kind))
                {
                    said.Add($"{what} isn't {(items[p]!.Value.Named ? name : $"item {number}")}: "
                             + $"{ItemFile.KindWords[(int)kind]} isn't worn there");
                    continue;
                }
                unit.Items[p] = number;
                unit.Kinds[p] = kind;
                unit.ItemNames[p] = name;
            }
        }

        /// <summary>What the mods' files come to, in Reloaded-II's order (a later mod's bits, job and items over an
        /// earlier's): each battle's units, each map's treasures, and what couldn't be used (`Said`). `jobs`: every job
        /// given, by its mod and Name. `quests`: the quests' own battles' units' items.</summary>
        public static Plan Make(IEnumerable<ModBattles> mods, IEnumerable<QuestItems> quests,
                                IReadOnlyDictionary<string, int> itemNumbers, Func<int, ItemKind?> kindOf,
                                IReadOnlyDictionary<string, int> jobs)
        {
            var plan = new Plan();
            foreach (var mod in mods)
            {
                foreach (var edit in mod.Units)
                {
                    string who = $"{edit.ModName}'s unit {edit.Slot + 1} of battle {edit.Battle}";
                    var unit = plan.Unit(edit.Battle, edit.Slot);
                    for (int i = 0; i < EntryBytes; i++)
                    {
                        unit.Mask[i] |= edit.Mask[i];
                        unit.Values[i] = (byte)((unit.Values[i] & ~edit.Mask[i]) | edit.Values[i]);
                    }
                    if (edit.Job.Length > 0)
                    {
                        if (jobs.TryGetValue($"{edit.ModId}/{edit.Job}", out int job))
                        {
                            unit.Mask[EntryJobAt] = 0xFF;
                            unit.Values[EntryJobAt] = (byte)job;
                        }
                        else
                            plan.Said.Add($"{who} isn't put in {edit.Job}: its mod gives the game no job of that Name "
                                          + "this time");
                    }
                    Wear(unit, edit.Items, edit.ModId, who, itemNumbers, kindOf, plan.Said);
                }
                foreach (var treasure in mod.Treasures)
                {
                    string who = $"{treasure.ModName}'s treasure {treasure.Tile + 1} of map {treasure.Map}";
                    if (!plan.Maps.TryGetValue(treasure.Map, out var map))
                        map = new TreasurePlan();
                    bool any = false;
                    if (treasure.Rare != null)
                    {
                        int n = Resolve(treasure.Rare.Value, treasure.ModId, $"{who}'s rare item", itemNumbers, kindOf,
                                        plan.Said, out _, out _);
                        if (n != 0)
                        {
                            map.Rare[treasure.Tile] = n;
                            any = true;
                        }
                    }
                    if (treasure.Common != null)
                    {
                        int n = Resolve(treasure.Common.Value, treasure.ModId, $"{who}'s common item", itemNumbers, kindOf,
                                        plan.Said, out _, out _);
                        if (n != 0)
                        {
                            map.Common[treasure.Tile] = n;
                            any = true;
                        }
                    }
                    if (any)
                        plan.Maps[treasure.Map] = map;
                }
            }
            foreach (var quest in quests)
                foreach (var (slot, items) in quest.Items)
                    Wear(plan.Unit(quest.Battle, slot), items, quest.ModId, $"{quest.Who}'s unit {slot + 1}", itemNumbers,
                         kindOf, plan.Said);
            // A unit that came to nothing (its job and items all left out) is no unit of the plan.
            var empty = new List<int>();
            foreach (var (battle, units) in plan.Battles)
            {
                bool any = false;
                for (int s = 0; s < Units; s++)
                {
                    var unit = units[s];
                    if (unit == null)
                        continue;
                    if (!unit.Changes && !unit.Wears)
                    {
                        units[s] = null;
                        continue;
                    }
                    any = true;
                    if (unit.Changes)
                        plan.UnitsChanged++;
                    if (unit.Wears)
                        plan.UnitsWearing++;
                }
                if (!any)
                    empty.Add(battle);
            }
            foreach (int battle in empty)
                plan.Battles.Remove(battle);
            foreach (var (_, map) in plan.Maps)
                for (int t = 0; t < Tiles; t++)
                    if (map.Rare[t] != 0 || map.Common[t] != 0)
                        plan.TreasuresChanged++;
            return plan;
        }

        static string Count(int n, string one, string many) => n == 1 ? $"1 {one}" : $"{n} {many}";

        /// <summary>What is said of the plan, once: "The mods' battles: 12 units changed in 3 battles, 2 units wearing
        /// items past 255, 3 buried treasures on 2 maps."</summary>
        public static string Line(Plan plan)
        {
            var parts = new List<string>();
            int battles = 0;
            foreach (var (_, units) in plan.Battles)
                foreach (var unit in units)
                    if (unit != null && unit.Changes)
                    {
                        battles++;
                        break;
                    }
            if (plan.UnitsChanged > 0)
                parts.Add($"{Count(plan.UnitsChanged, "unit", "units")} changed in {Count(battles, "battle", "battles")}");
            if (plan.UnitsWearing > 0)
                parts.Add($"{Count(plan.UnitsWearing, "unit", "units")} wearing items past 255");
            if (plan.TreasuresChanged > 0)
                parts.Add($"{Count(plan.TreasuresChanged, "buried treasure", "buried treasures")} on "
                          + $"{Count(plan.Maps.Count, "map", "maps")}");
            return $"The mods' battles: {string.Join(", ", parts)}.";
        }

        // --- what is said as each is done, once ----------------------------------------------------------------------

        /// <summary>"battle 387: 3 of its units are as the mods have them."</summary>
        public static string UnitsLine(string battle, int units)
            => $"{battle}: {units} of its units {(units == 1 ? "is" : "are")} as the mods have them.";

        /// <summary>"battle 387: unit 5 wears Onion Sword (right hand) and item 293 (head)."</summary>
        public static string WearsLine(string battle, int slot, UnitPlan unit)
        {
            var parts = new List<string>();
            for (int p = 0; p < Places.Length; p++)
                if (unit.Items[p] != 0)
                    parts.Add($"{(int.TryParse(unit.ItemNames[p], out _) ? "item " : "")}{unit.ItemNames[p]} "
                              + $"({PlaceWords[p]})");
            string listed = parts.Count <= 1 ? string.Join("", parts)
                : $"{string.Join(", ", parts.GetRange(0, parts.Count - 1))} and {parts[parts.Count - 1]}";
            return $"{battle}: unit {slot + 1} wears {listed}.";
        }

        /// <summary>"map 74: its buried treasure is as the mods have it."</summary>
        public static string TreasuresLine(int map) => $"map {map}: its buried treasure is as the mods have it.";

        // --- what is done to the game's memory, each time ------------------------------------------------------------

        /// <summary>A battle's block (its 16 entries) with the mods' units' bits written: how many entries changed.
        /// </summary>
        public static int Apply(Span<byte> block, UnitPlan?[] units)
        {
            int changed = 0;
            for (int s = 0; s < Units && (s + 1) * EntryBytes <= block.Length; s++)
            {
                var unit = units[s];
                if (unit == null || !unit.Changes)
                    continue;
                var entry = block.Slice(s * EntryBytes, EntryBytes);
                bool any = false;
                for (int i = 0; i < EntryBytes; i++)
                {
                    byte now = (byte)((entry[i] & ~unit.Mask[i]) | unit.Values[i]);
                    any |= now != entry[i];
                    entry[i] = now;
                }
                if (any)
                    changed++;
            }
            return changed;
        }

        static void Word(Span<byte> unit, int at, int value)
        {
            unit[at] = (byte)value;
            unit[at + 1] = (byte)(value >> 8);
        }

        /// <summary>A battle unit the game just put its entry's equipment on (its first 0x28 bytes), with the mods' items
        /// past 255 put on as the game puts a byte's item on (0x277564): a head's, a body's and an accessory's word; a
        /// hand's weapon in its weapon's word and its shield's none, a hand's shield in its shield's word and its
        /// weapon's none. How many were put on.</summary>
        public static int Wear(Span<byte> unit, UnitPlan plan)
        {
            if (unit.Length < UnitBytes)
                return 0;
            int worn = 0;
            int[] at = { UnitHead, UnitBody, UnitAccessory };
            for (int p = 0; p < 3; p++)
                if (plan.Items[p] != 0)
                {
                    Word(unit, at[p], plan.Items[p]);
                    worn++;
                }
            for (int hand = 0; hand < 2; hand++)
            {
                int item = plan.Items[3 + hand];
                if (item == 0)
                    continue;
                int weapon = hand == 0 ? UnitRightWeapon : UnitLeftWeapon;
                int shield = hand == 0 ? UnitRightShield : UnitLeftShield;
                bool isShield = plan.Kinds[3 + hand] == ItemKind.Shield;
                Word(unit, isShield ? shield : weapon, item);
                Word(unit, isShield ? weapon : shield, None);
                worn++;
            }
            return worn;
        }

        /// <summary>A map's treasures as the battle reads them (24 bytes) with the mods' items written: how many words
        /// changed.</summary>
        public static int Bury(Span<byte> now, TreasurePlan map)
        {
            int changed = 0;
            for (int t = 0; t < Tiles && (t + 1) * TreasureBytes <= now.Length; t++)
            {
                if (map.Rare[t] != 0)
                {
                    Word(now, t * TreasureBytes + RareAt, map.Rare[t]);
                    changed++;
                }
                if (map.Common[t] != 0)
                {
                    Word(now, t * TreasureBytes + CommonAt, map.Common[t]);
                    changed++;
                }
            }
            return changed;
        }

        /// <summary>Which of a block's 16 entries one is: its place, or -1 for an address that is none of them.</summary>
        public static int SlotOf(nint block, nint entry)
        {
            long distance = (long)entry - (long)block;
            return block != 0 && distance >= 0 && distance < Units * EntryBytes && distance % EntryBytes == 0
                ? (int)(distance / EntryBytes) : -1;
        }
    }
}
