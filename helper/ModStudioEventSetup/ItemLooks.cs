// Mod Studio Framework (1.28.0): the game's own weapons' looks in battle (Zodi, 3 November, after test 60: "We
// should probably also apply our item's sprite pair findings to the Items page on the Mod Studio so that users can
// also change the vanilla items look and palette"). A weapon's swing is drawn from its sprite pair (ItemSpritePair,
// 0x2B8E60, read only by the swing's palette load and its animation), which the game keeps in its program, not in a
// table the mod loader changes: a mod's ModStudioItemLooks.json names the game's items whose sprite pair it changes,
// and this helper writes each where the game's own ItemSpritePair finds that item's, as the game starts. Mod Studio
// reads and writes the file (mod_studio/mod_items.py: read_looks_text, the same problems word for word). Part of The
// Ivalice Chronicles Mod Studio, GPL-3.0.
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text.Json;

namespace ModStudioEventSetup
{
    /// <summary>One look: the game's item, its new sprite pair, the mod giving it.</summary>
    public sealed class ItemLook
    {
        public ItemLook(string modId, string modName, int item, byte[] pair)
        {
            ModId = modId;
            ModName = modName;
            Item = item;
            Pair = pair;
        }

        public string ModId { get; }
        public string ModName { get; }
        public int Item { get; }
        public byte[] Pair { get; }
    }

    public static class ItemLooks
    {
        public const string FileName = "ModStudioItemLooks.json";
        public const string Format = "Mod Studio item looks";
        public const int Version = 1;

        /// <summary>A mod's looks from its file's text: the whole file refused for a problem of its own, a look with a
        /// problem of its own left out, each said (`problems`, without the mod's name).</summary>
        public static List<ItemLook> Read(string modId, string modName, string text, List<string> problems)
        {
            var looks = new List<ItemLook>();
            JsonDocument document;
            try
            {
                document = JsonDocument.Parse(text);
            }
            catch (JsonException e)
            {
                problems.Add($"it isn't JSON ({e.Message})");
                return looks;
            }
            using (document)
            {
                var root = document.RootElement;
                if (root.ValueKind != JsonValueKind.Object)
                {
                    problems.Add("it isn't a list of fields");
                    return looks;
                }
                if (!Has(root, "Format", out var format) || format.ValueKind != JsonValueKind.String
                    || format.GetString() != Format)
                {
                    problems.Add($"its Format isn't \"{Format}\"");
                    return looks;
                }
                if (!Has(root, "Version", out var version) || version.ValueKind != JsonValueKind.Number
                    || !version.TryGetInt32(out int v) || v != Version)
                {
                    problems.Add($"its Version is {Raw(root, "Version")}, not {Version}");
                    return looks;
                }
                if (!Has(root, "Looks", out var listed) || listed.ValueKind != JsonValueKind.Array)
                {
                    problems.Add($"its Looks is a list of the game's items' looks, not {Raw(root, "Looks")}");
                    return looks;
                }
                int n = 0;
                foreach (var entry in listed.EnumerateArray())
                {
                    n++;
                    if (entry.ValueKind != JsonValueKind.Object)
                    {
                        problems.Add($"its look {n} isn't a list of fields (its Item and its SpritePair)");
                        continue;
                    }
                    if (!Has(entry, "Item", out var it) || it.ValueKind != JsonValueKind.Number
                        || !it.TryGetInt32(out int item) || !GameItem(item))
                    {
                        problems.Add($"its look {n}'s Item is one of the game's items (1 to 253, or 256 to "
                                     + $"{MostGameItem}), not {Raw(entry, "Item")}");
                        continue;
                    }
                    var pair = Bytes(entry, "SpritePair", 2);
                    if (pair == null)
                    {
                        problems.Add($"its look {n}'s SpritePair is a sprite pair's two bytes (each 0 to 255), not "
                                     + Raw(entry, "SpritePair"));
                        continue;
                    }
                    if (looks.Exists(l => l.Item == item))
                    {
                        problems.Add($"its look {n} is for item {item} again");
                        continue;
                    }
                    looks.Add(new ItemLook(modId, modName, item, pair));
                }
            }
            return looks;
        }

        /// <summary>A mod's looks (its FileName at its folder's root), each problem said with the mod's name.</summary>
        public static List<ItemLook> ReadMod(string modId, string modName, string modFolder, List<string> problems)
        {
            string file = Path.Combine(modFolder, FileName);
            if (!File.Exists(file))
                return new List<ItemLook>();
            var said = new List<string>();
            List<ItemLook> looks;
            try
            {
                looks = Read(modId, modName, File.ReadAllText(file), said);
            }
            catch (Exception e) when (e is not OutOfMemoryException)
            {
                said.Add($"it can't be read ({e.Message})");
                looks = new List<ItemLook>();
            }
            foreach (var s in said)
                problems.Add($"{modName}'s {FileName}: {s}");
            return looks;
        }

        /// <summary>The looks given, in Reloaded-II's order, one a game item: a later mod's in place of an earlier's,
        /// said.</summary>
        public static List<ItemLook> Plan(IEnumerable<ItemLook> looks, List<string> said)
        {
            var planned = new List<ItemLook>();
            foreach (var look in looks)
            {
                int had = planned.FindIndex(l => l.Item == look.Item);
                if (had >= 0)
                {
                    said.Add($"the game's item {look.Item}'s look in battle is {look.ModName}'s, not "
                             + $"{planned[had].ModName}'s (later in the load order).");
                    planned[had] = look;
                }
                else
                    planned.Add(look);
            }
            return planned;
        }

        /// <summary>What is said of a look given. (1.35.0, Zodi of 5 November: a shield's look as it guards changed
        /// too) A weapon's or a shield's alike: "has another look in battle" (1.28.0 to 1.34.0: "swings").</summary>
        public static string Line(ItemLook look, byte[] old)
            => $"the game's item {look.Item} has another look in battle ({look.ModName}): its sprite pair "
               + $"{old[0]} {old[1]} made {look.Pair[0]} {look.Pair[1]}.";

        /// <summary>The looks given to the game (`start`, the program's image; `pairAt`, its ItemSpritePair): each
        /// written where the game's own function finds that item's sprite pair, its page made writable for the two
        /// bytes and given back; an item without one (not a weapon or a shield) said, left as it is.</summary>
        public static unsafe void Give(byte* start, int pairAt, List<ItemLook> looks, Action<string> say)
        {
            var pairOf = (delegate* unmanaged<int, nint>)(start + pairAt);
            foreach (var look in looks)
            {
                nint at = pairOf(look.Item);
                if (at == 0)
                {
                    say($"the game's item {look.Item} has no look in battle ({look.ModName}): its look is left out.");
                    continue;
                }
                var old = new[] { *(byte*)at, *(byte*)(at + 1) };
                if (!VirtualProtect(at, 2, ExecuteReadWrite, out uint was))
                {
                    say($"the game's item {look.Item}'s look in battle couldn't be changed ({look.ModName}).");
                    continue;
                }
                *(byte*)at = look.Pair[0];
                *(byte*)(at + 1) = look.Pair[1];
                VirtualProtect(at, 2, was, out _);
                say(Line(look, old));
            }
        }

        const uint ExecuteReadWrite = 0x40;

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool VirtualProtect(nint address, nuint size, uint protect, out uint old);

        public const int MostGameItem = 260;

        /// <summary>One of the game's items (IsValidItem's 1 to 253 and 256 to 260).</summary>
        public static bool GameItem(int item) => (item >= 1 && item <= 253) || (item >= 256 && item <= MostGameItem);

        static bool Has(JsonElement e, string name, out JsonElement value)
        {
            foreach (var p in e.EnumerateObject())
                if (string.Equals(p.Name, name, StringComparison.OrdinalIgnoreCase))
                {
                    value = p.Value;
                    return true;
                }
            value = default;
            return false;
        }

        static string Raw(JsonElement e, string name)
        {
            if (!Has(e, name, out var value))
                return "nothing";
            string raw = value.GetRawText();
            return raw.Length > 80 ? raw.Substring(0, 77) + "..." : raw;
        }

        static byte[]? Bytes(JsonElement e, string name, int count)
        {
            if (!Has(e, name, out var value) || value.ValueKind != JsonValueKind.Array || value.GetArrayLength() != count)
                return null;
            var bytes = new byte[count];
            int n = 0;
            foreach (var b in value.EnumerateArray())
            {
                if (b.ValueKind != JsonValueKind.Number || !b.TryGetInt32(out int v) || v < 0 || v > 255)
                    return null;
                bytes[n++] = (byte)v;
            }
            return bytes;
        }
    }
}
