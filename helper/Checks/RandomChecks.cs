// Mod Studio's checks of the helper: (2.0.6) a unit's Random equipment reaching War of the Lions' items
// (RandomItems.cs), and WotL Restoration's 40 shown with the framework's own pictures (WotLIcons.cs). Part of The
// Ivalice Chronicles Mod Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --random <request.json> <report.json>
//
// The request: "program" (his program: where the helper finds the game's function and its asks, RandomItems.Find,
// from the places Places.Find and ItemRoom.Find give); "records" (each item's 12 bytes by its number, the game's as his
// program has them and the 40's as the framework plans them), "weapons" (each weapon's kind record, 8 bytes, by its
// number); "extras" (the War of the Lions items Random may give, by kind's name); "cases" (each a unit's first 0x9C
// bytes, an entry's first 0x17 and the four random words): each put on by the framework's own Equip, as the
// machine runs the game's function beside it (dev/test_wotl_items.py); "planned" (items as the framework plans them,
// each its number, kind and record): which could be Random equipment (RandomItems.Extras) and the line said.
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text.Json;
using ModStudioEventSetup;

static unsafe class RandomChecks
{
    sealed class Game : RandomItems.IGame
    {
        public Dictionary<int, byte[]> Records = new(), Weapons = new();
        public uint S0, S1, S2, S3;
        public int Draws;
        public readonly List<int> Asked = new();

        public byte Record(int item, int at)
        {
            Asked.Add(item);
            return Records.TryGetValue(item, out var r) ? r[at] : (byte)0;
        }

        public byte Weapon(int item, int at) => Weapons.TryGetValue(item, out var w) ? w[at] : (byte)0;

        public uint Next()
        {
            Draws++;
            return RandomItems.Next(ref S0, ref S1, ref S2, ref S3);
        }
    }

    static byte[] Hex(string text) => Convert.FromHexString(text);

    public static int Run(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var r = request.RootElement;
        var report = new Dictionary<string, object?>();

        // Where the helper finds the game's function and its asks in his program.
        if (r.TryGetProperty("program", out var programPath))
        {
            var image = Program.Load(programPath.GetString()!);
            var places = Places.Find(image);
            var items = ItemRoom.Find(image, Finder.Sections(image));
            int common = items.At.TryGetValue("ItemCommon", out int c) ? c : -1;
            int weapon = items.At.TryGetValue("ItemWeapon", out int w) ? w : -1;
            var found = RandomItems.Find(image, places.UnitEquipment, common, weapon);
            report["found"] = new Dictionary<string, object?>
            {
                ["equipment"] = found.Equipment, ["pick"] = found.Pick, ["record"] = found.Record,
                ["weapon"] = found.Weapon, ["words"] = found.Words, ["missing"] = found.Missing,
                ["common"] = common, ["weaponFunction"] = weapon, ["unitEquipment"] = places.UnitEquipment,
                ["iconPath"] = items.At.TryGetValue("IconPath", out int ip) ? ip : -1,
                ["smallIconPath"] = items.At.TryGetValue("SmallIconPath", out int sp) ? sp : -1,
            };
            // A function changed by one byte is not found (the pattern held whole).
            if (found.Ok)
            {
                var changed = (byte[])image.Clone();
                changed[found.Equipment + 0x200] ^= 0x01;
                var broken = RandomItems.Find(changed, places.UnitEquipment, common, weapon);
                var pickChanged = (byte[])image.Clone();
                pickChanged[found.Pick + 0x80] ^= 0x01;
                var pickBroken = RandomItems.Find(pickChanged, places.UnitEquipment, common, weapon);
                report["brokenFound"] = new[] { broken.Missing, pickBroken.Missing };
                report["otherRecord"] = RandomItems.Find(image, places.UnitEquipment, common + 1, weapon).Missing;
            }
        }

        var game = new Game();
        if (r.TryGetProperty("records", out var records))
            foreach (var p in records.EnumerateObject())
                game.Records[int.Parse(p.Name)] = Hex(p.Value.GetString()!);
        if (r.TryGetProperty("weapons", out var weapons))
            foreach (var p in weapons.EnumerateObject())
                game.Weapons[int.Parse(p.Name)] = Hex(p.Value.GetString()!);
        var extras = new Dictionary<ItemKind, List<int>>();
        if (r.TryGetProperty("extras", out var given))
            foreach (var p in given.EnumerateObject())
            {
                var list = new List<int>();
                foreach (var n in p.Value.EnumerateArray())
                    list.Add(n.GetInt32());
                extras[Enum.Parse<ItemKind>(p.Name)] = list;
            }

        // Each case put on by the framework's own function, its words and random numbers after.
        var cases = new List<object?>();
        if (r.TryGetProperty("cases", out var all))
            foreach (var one in all.EnumerateArray())
            {
                var unit = Hex(one.GetProperty("unit").GetString()!);
                var entry = Hex(one.GetProperty("entry").GetString()!);
                var words = one.GetProperty("words");
                game.S0 = words[0].GetUInt32();
                game.S1 = words[1].GetUInt32();
                game.S2 = words[2].GetUInt32();
                game.S3 = words[3].GetUInt32();
                game.Draws = 0;
                bool wants = RandomItems.Wants(game, unit, entry, extras);
                string? fault = null;
                try
                {
                    RandomItems.Equip(game, unit, entry, extras);
                }
                catch (Exception e)
                {
                    fault = $"{e.GetType().Name}: {e.Message}";
                }
                var put = new List<int>();
                for (int k = 0; k < RandomItems.Words; k++)
                    put.Add(unit[RandomItems.WordHead + 2 * k] | unit[RandomItems.WordHead + 2 * k + 1] << 8);
                cases.Add(new Dictionary<string, object?>
                {
                    ["words"] = put, ["rng"] = new[] { game.S0, game.S1, game.S2, game.S3 }, ["draws"] = game.Draws,
                    ["wants"] = wants, ["fault"] = fault, ["unitAfter"] = Convert.ToHexString(unit),
                });
            }
        report["cases"] = cases;

        // Which planned items could be Random equipment, and the line said.
        if (r.TryGetProperty("planned", out var plannedItems))
        {
            var planned = new Dictionary<int, ModItem>();
            foreach (var item in plannedItems.EnumerateArray())
            {
                int number = item.GetProperty("number").GetInt32();
                var kind = Enum.Parse<ItemKind>(item.GetProperty("kind").GetString()!);
                var record = Hex(item.GetProperty("record").GetString()!);
                var fact = WotLItems.Of(number);
                var made = fact != null ? WotLItems.Item(fact) : null;
                planned[number] = new ModItem("test", "Test", number.ToString(), $"Item {number}", kind, record,
                                              made?.KindRecord ?? new byte[ItemFile.KindBytes[(int)kind]],
                                              made?.SpritePair ?? Array.Empty<byte>(), null, $"Item {number}",
                                              $"Item {number}", $"Item {number}", "", 0, "", 0, 0, null, 0, false);
            }
            var made40 = RandomItems.Extras(planned);
            var byKind = new Dictionary<string, List<int>>();
            foreach (var (kind, list) in made40)
                byKind[kind.ToString()] = list;
            report["extrasMade"] = byKind;
            report["line"] = made40.Count > 0 ? RandomItems.Line(made40) : "";
        }

        // The 40's pictures with WotL Restoration's items: each one's two paths, written as the game's icon path writes
        // one, and a buffer too small for one left to the game.
        var icons = new Dictionary<string, object?>();
        var buffer = NativeMemory.AllocZeroed(0x200);
        try
        {
            foreach (var fact in WotLItems.Facts)
            {
                int big = WotLItems.WritePicturePath((nint)buffer, fact.Number, 0x104, false);
                string bigText = Marshal.PtrToStringUTF8((nint)buffer) ?? "";
                int small = WotLItems.WritePicturePath((nint)buffer, fact.Number, 0x104, true);
                string smallText = Marshal.PtrToStringUTF8((nint)buffer) ?? "";
                icons[fact.Number.ToString()] = new object[] { big, bigText, small, smallText };
            }
            icons["tooSmall"] = WotLItems.WritePicturePath((nint)buffer, 261, 20, false);
        }
        finally
        {
            NativeMemory.Free(buffer);
        }
        report["icons"] = icons;
        report["iconsLine"] = WotLItems.PicturesLine;

        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }
}
