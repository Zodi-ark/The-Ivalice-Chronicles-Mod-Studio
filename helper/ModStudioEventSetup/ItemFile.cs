// Mod Studio Framework: (1.26.0) reading a mod's own item. Part of The
// Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi's list of 3 November, his first: "Adding new items to go into the new
// towns outfitter". His choices: new items now, made on the Side Quests page's
// Items tab, an icon of the game's or a texture of the modder's own, an item
// started as a copy of one of the game's. An item is a folder of its own in a
// mod, `ModStudioItems/<item>/`, holding `item.json`: its name, its kind, its
// records as the game keeps an item's (its 12 bytes, its kind's record, a
// weapon's or a shield's sprite pair, its equipment bonuses if it has any),
// its words (the Item table's name, singular, plural and description) and its
// icon (one of the game's items' by number, or its own texture's files). Mod
// Studio writes it (`mod_studio/mod_items.py` reads and writes the same file
// and says the same problems); what can't be used is left out and said. A
// modder never chooses a number: the framework numbers each item past the
// game's and WotL Restoration's (ItemRoom.cs).
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Json;

namespace ModStudioEventSetup
{
    /// <summary>An item's kind, as the game tells an item's records apart (its segment, the segment's kind).</summary>
    public enum ItemKind { Weapon, Shield, Head, Body, Accessory, Item }

    /// <summary>A mod's own item, as its mod gives it.</summary>
    public sealed class ModItem
    {
        public string ModId { get; }
        public string ModName { get; }
        public string Folder { get; }
        public string Name { get; }
        public ItemKind Kind { get; }
        /// <summary>Its 12 byte record (ItemCommon's): palette, graphic, level, type flags, its kind's record's number,
        /// its category, a byte, its equipment bonus row, its price (two bytes), the story point the shops sell it from,
        /// a byte. The type flag of its kind is set and its kind's record's number and bonus row are the framework's
        /// (ItemRoom.Record).</summary>
        public byte[] Record { get; }
        /// <summary>Its kind's record: a weapon's 8 bytes, a shield's, a head's, a body's or an accessory's 2, an
        /// item's 3.</summary>
        public byte[] KindRecord { get; }
        /// <summary>A weapon's or a shield's sprite pair (2 bytes), or empty.</summary>
        public byte[] SpritePair { get; }
        /// <summary>Its equipment bonuses (a row of 26 bytes: attack, magick, speed, move, jump, statuses always, never
        /// and at the start, elements absorbed, cancelled, halved, weak to and strengthened, a byte), or null for
        /// none.</summary>
        public byte[]? Bonus { get; }
        public string WordName { get; }
        public string Singular { get; }
        public string Plural { get; }
        public string Description { get; }
        /// <summary>Its icon: one of the game's items' by its number (1 to 260), or -1 for its own (IconPicture).</summary>
        public int Icon { get; }
        public string IconPicture { get; }
        /// <summary>Its Item row's UI category (UiItemCategoryId) and sort (SortOrder), as the game item it was copied
        /// from has them (the menus' tabs and order); -1 when its file gives none.</summary>
        public int UiCategory { get; }
        public int Sort { get; }
        /// <summary>(1.27.0) The game's towns whose Outfitters sell it (by their places, 0 to 14), as its file names
        /// them.</summary>
        public int[] Shops { get; }
        /// <summary>(1.27.0) Its Item row's UI status effect (UiStatusEffectId: 1001 an HP drain's, 1002 a heal's) and
        /// random damage (IsRandomDamage), as Mod Studio sets them from what it does (the game's own items' way).</summary>
        public int UiStatus { get; }
        public bool RandomDamage { get; }

        public ModItem(string modId, string modName, string folder, string name, ItemKind kind, byte[] record,
                       byte[] kindRecord, byte[] spritePair, byte[]? bonus, string wordName, string singular,
                       string plural, string description, int icon, string iconPicture, int uiCategory = -1,
                       int sort = -1, int[]? shops = null, int uiStatus = 0, bool randomDamage = false)
        {
            UiCategory = uiCategory;
            Sort = sort;
            Shops = shops ?? Array.Empty<int>();
            UiStatus = uiStatus;
            RandomDamage = randomDamage;
            ModId = modId;
            ModName = modName;
            Folder = folder;
            Name = name;
            Kind = kind;
            Record = record;
            KindRecord = kindRecord;
            SpritePair = spritePair;
            Bonus = bonus;
            WordName = wordName;
            Singular = singular;
            Plural = plural;
            Description = description;
            IconPicture = iconPicture;
            Icon = iconPicture.Length > 0 ? -1 : icon;
        }

        /// <summary>The key Numbers.json keeps its number under.</summary>
        public string Key => $"{ModId}/{Name}";
    }

    public static class ItemFile
    {
        /// <summary>The folder of a mod that holds its own items, one folder each.</summary>
        public const string Folder = "ModStudioItems";
        public const string Name = "item.json";
        public const string Format = "Mod Studio item";
        public const int Version = 1;
        /// <summary>An item's name and its words: as a quest's names (letters, digits, spaces, underscores, hyphens and
        /// apostrophes, 1 to 64), its words up to the game's own longest kinds.</summary>
        public const int NameMost = 64, WordMost = 64, DescriptionMost = 400;
        /// <summary>The game's items an icon may be one of: 1 to 253 and 256 to 260 (IsValidItem's).</summary>
        public const int MostGameItem = 260;
        public static readonly string[] Kinds = { "Weapon", "Shield", "Head", "Body", "Accessory", "Item" };
        /// <summary>Each kind in words, as a sentence says it.</summary>
        public static readonly string[] KindWords = { "a weapon", "a shield", "an item worn on the head",
                                                      "an item worn on the body", "an accessory", "an item to use" };
        /// <summary>Each kind's record's bytes, as the game's kind tables hold them (ItemWeapon 8, ItemShield 2,
        /// ItemArmor 2 for a head and a body, ItemAccessory 2, ItemChemist 3).</summary>
        public static readonly int[] KindBytes = { 8, 2, 2, 2, 2, 3 };
        /// <summary>Each kind's type flag in its record's + 3 (the game's: a weapon 0x80, a shield 0x40, a head 0x20, a
        /// body 0x10, an accessory 0x08; an item none).</summary>
        public static readonly byte[] KindFlags = { 0x80, 0x40, 0x20, 0x10, 0x08, 0 };
        public const int RecordBytes = 12, BonusBytes = 26, PairBytes = 2;
        /// <summary>The kinds' five flags and the two the record's + 3 may hold beside them (Rare 0x02; 0x04 and 0x01
        /// unused by the game's items): a record's flags past its own kind's are refused.</summary>
        public const byte KindMask = 0xF8;
        /// <summary>The story point (its + 10) shops sell an item from: 1 to 16, as the game's scenes go (the shops'
        /// points, event 457 the last).</summary>
        public const int MostShopPoint = 16;
        public const int PriceAt = 8, ShopAt = 10, FlagsAt = 3, KindAt = 4, BonusAt = 7;
        /// <summary>(1.27.0) The game's towns a file's Shops may name: their places, 0 to 14 (the shops' masks'
        /// fifteen).</summary>
        public const int LastTown = 14;
        public const int MostUiStatus = 65535;

        public static bool GoodName(string name)
        {
            if (name.Length == 0 || name.Length > NameMost || name.Trim() != name)
                return false;
            foreach (char ch in name)
                if (!(char.IsAsciiLetterOrDigit(ch) || ch == ' ' || ch == '_' || ch == '-' || ch == '\''))
                    return false;
            return true;
        }

        /// <summary>An own icon's files' name: small letters, digits and _, 1 to 64 of them (as a place's own
        /// texture's).</summary>
        public static bool GoodPicture(string name)
        {
            if (name.Length == 0 || name.Length > 64)
                return false;
            foreach (char ch in name)
                if (!(ch >= 'a' && ch <= 'z' || ch >= '0' && ch <= '9' || ch == '_'))
                    return false;
            return true;
        }

        /// <summary>Where an item's own icon's texture and part list are in its mod, from the mod's folder (each of the
        /// Icon table's two: the menus' and the small one's).</summary>
        public static string[] IconFiles(string picture) => new[]
        {
            $"FFTIVC/data/enhanced/ui/ffto/icon/equip_item/texture/{picture}.tex",
            $"FFTIVC/data/enhanced/ui/ffto/icon/equip_item/textureparts/{picture}.utexpt",
            $"FFTIVC/data/enhanced/ui/ffto/icon/equip_item_s/texture/{picture}_s.tex",
            $"FFTIVC/data/enhanced/ui/ffto/icon/equip_item_s/textureparts/{picture}_s.utexpt",
        };

        public static List<ModItem> ReadMod(string modId, string modName, string modFolder, List<string> problems)
        {
            var items = new List<ModItem>();
            string root = Path.Combine(modFolder, Folder);
            if (!Directory.Exists(root))
                return items;
            var folders = new List<string>(Directory.GetDirectories(root));
            folders.Sort(StringComparer.Ordinal);
            foreach (var folder in folders)
            {
                string file = Path.Combine(folder, Name);
                if (!File.Exists(file))
                    continue;
                string folderName = Path.GetFileName(folder);
                var said = new List<string>();
                ModItem? item = null;
                try
                {
                    item = Read(modId, modName, folderName, File.ReadAllText(file),
                                path => File.Exists(Path.Combine(modFolder, path)), said);
                }
                catch (Exception e) when (e is not OutOfMemoryException)
                {
                    said.Add($"it can't be read ({e.Message})");
                }
                if (item != null && items.Exists(i => i.Name == item.Name))
                {
                    said.Add($"another of the mod's items is named {item.Name}");
                    item = null;
                }
                foreach (var s in said)
                    problems.Add($"{modName}'s item {folderName}: {s}");
                if (item != null)
                    items.Add(item);
            }
            return items;
        }

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

        /// <summary>A list of whole numbers 0 to 255, `count` of them, or null.</summary>
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

        /// <summary>Text that isn't Unicode text (half of a surrogate pair alone) anywhere in the file: GetString
        /// would throw on it, so such a file is refused first (as Mod Studio refuses it).</summary>
        static bool HalfPair(JsonElement e)
        {
            switch (e.ValueKind)
            {
                case JsonValueKind.Object:
                    foreach (var p in e.EnumerateObject())
                        if (HalfPair(p.Value) || !WholeText(p.Name))
                            return true;
                    return false;
                case JsonValueKind.Array:
                    foreach (var v in e.EnumerateArray())
                        if (HalfPair(v))
                            return true;
                    return false;
                case JsonValueKind.String:
                    try
                    {
                        e.GetString();
                        return false;
                    }
                    catch (InvalidOperationException)
                    {
                        return true;
                    }
                default:
                    return false;
            }
        }

        static bool WholeText(string text)
        {
            for (int n = 0; n < text.Length; n++)
            {
                if (char.IsHighSurrogate(text[n]))
                {
                    if (n + 1 >= text.Length || !char.IsLowSurrogate(text[n + 1]))
                        return false;
                    n++;
                }
                else if (char.IsLowSurrogate(text[n]))
                    return false;
            }
            return true;
        }

        /// <summary>A word of the item's (Words' Name, Singular, Plural, Description): text of 1 to `most`
        /// characters, a description up to two line breaks; "" and false when wrong.</summary>
        static bool Word(JsonElement words, string name, int most, bool required, out string text)
        {
            text = "";
            if (!Has(words, name, out var value))
                return !required;
            if (value.ValueKind != JsonValueKind.String)
                return false;
            text = value.GetString() ?? "";
            int breaks = 0;
            foreach (char ch in text)
                if (ch == '\n')
                    breaks++;
                else if (char.IsControl(ch))
                    return false;
            return text.Length > 0 && text.Length <= most && breaks <= (most == DescriptionMost ? 2 : 0)
                   && Encoding.UTF8.GetByteCount(text) < 1024;
        }

        /// <summary>An item from its file's text; null when it can't be used, why in problems. `hasFile` says whether
        /// the mod has a file (its path from the mod's folder).</summary>
        public static ModItem? Read(string modId, string modName, string folder, string text, Func<string, bool> hasFile,
                                    List<string> problems)
        {
            JsonDocument document;
            try
            {
                document = JsonDocument.Parse(text);
            }
            catch (JsonException e)
            {
                problems.Add($"its {Name} isn't JSON ({e.Message})");
                return null;
            }
            using (document)
            {
                var root = document.RootElement;
                if (root.ValueKind != JsonValueKind.Object)
                {
                    problems.Add($"its {Name} isn't a list of fields");
                    return null;
                }
                if (HalfPair(root))
                {
                    problems.Add($"its {Name} has a text that isn't Unicode text (half of a surrogate pair alone)");
                    return null;
                }
                if (!Has(root, "Format", out var format) || format.ValueKind != JsonValueKind.String
                    || format.GetString() != Format)
                {
                    problems.Add($"its Format isn't \"{Format}\"");
                    return null;
                }
                if (!Has(root, "Version", out var version) || version.ValueKind != JsonValueKind.Number
                    || !version.TryGetInt32(out int v) || v != Version)
                {
                    problems.Add($"its Version is {Raw(root, "Version")}, not {Version}");
                    return null;
                }
                string name = Has(root, "Name", out var n) && n.ValueKind == JsonValueKind.String ? n.GetString() ?? "" : "";
                if (!GoodName(name))
                {
                    problems.Add($"its Name is 1 to {NameMost} letters, digits, spaces, underscores, hyphens and "
                                 + $"apostrophes, with no space at either end, not {Raw(root, "Name")}");
                    return null;
                }
                string kindText = Has(root, "Kind", out var k) && k.ValueKind == JsonValueKind.String ? k.GetString() ?? "" : "";
                int kind = Array.IndexOf(Kinds, kindText);
                if (kind < 0)
                {
                    problems.Add($"its Kind is Weapon, Shield, Head, Body, Accessory or Item, not {Raw(root, "Kind")}");
                    return null;
                }
                var record = Bytes(root, "Record", RecordBytes);
                if (record == null)
                {
                    problems.Add($"its Record is its {RecordBytes} bytes as the game keeps an item's (each 0 to 255), not "
                                 + Raw(root, "Record"));
                    return null;
                }
                if ((record[FlagsAt] & KindMask) != KindFlags[kind])
                {
                    problems.Add($"its Record's type flags (byte 3: {record[FlagsAt]}) aren't those of {KindWords[kind]} "
                                 + $"({KindFlags[kind]}, with Rare 2 if it is rare)");
                    return null;
                }
                if (record[ShopAt] < 1 || record[ShopAt] > MostShopPoint)
                {
                    problems.Add($"its Record's story point the shops sell it from (byte 10) is 1 to {MostShopPoint}, "
                                 + $"not {record[ShopAt]}");
                    return null;
                }
                var kindRecord = Bytes(root, "KindRecord", KindBytes[kind]);
                if (kindRecord == null)
                {
                    problems.Add($"its KindRecord is the record of {KindWords[kind]}, {KindBytes[kind]} bytes "
                                 + $"(each 0 to 255), not {Raw(root, "KindRecord")}");
                    return null;
                }
                byte[] pair = Array.Empty<byte>();
                bool paired = kind == (int)ItemKind.Weapon || kind == (int)ItemKind.Shield;
                if (paired)
                {
                    pair = Bytes(root, "SpritePair", PairBytes) ?? Array.Empty<byte>();
                    if (pair.Length != PairBytes)
                    {
                        problems.Add($"its SpritePair is a weapon's or a shield's two bytes (each 0 to 255), not "
                                     + Raw(root, "SpritePair"));
                        return null;
                    }
                }
                else if (Has(root, "SpritePair", out _))
                {
                    problems.Add("only a weapon or a shield has a SpritePair");
                    return null;
                }
                byte[]? bonus = null;
                if (Has(root, "Bonus", out var given) && given.ValueKind != JsonValueKind.Null)
                {
                    bonus = Bytes(root, "Bonus", BonusBytes);
                    if (bonus == null)
                    {
                        problems.Add($"its Bonus is its equipment bonuses' {BonusBytes} bytes (each 0 to 255), or none, "
                                     + $"not {Raw(root, "Bonus")}");
                        return null;
                    }
                }
                if (!Has(root, "Words", out var words) || words.ValueKind != JsonValueKind.Object)
                {
                    problems.Add("it has no Words (its Name, Singular, Plural and Description)");
                    return null;
                }
                if (!Word(words, "Name", WordMost, true, out string wordName)
                    || !Word(words, "Singular", WordMost, false, out string singular)
                    || !Word(words, "Plural", WordMost, false, out string plural)
                    || !Word(words, "Description", DescriptionMost, false, out string description))
                {
                    problems.Add($"its Words are its Name (1 to {WordMost} characters), and if it has them its Singular "
                                 + $"and Plural (1 to {WordMost}) and Description (1 to {DescriptionMost}, at most two line "
                                 + "breaks), each text");
                    return null;
                }
                int icon = -1;
                string own = "";
                bool hasIcon = Has(root, "Icon", out var iconValue);
                if (hasIcon && iconValue.ValueKind == JsonValueKind.String && GoodPicture(iconValue.GetString() ?? ""))
                    own = iconValue.GetString() ?? "";
                else if (!hasIcon || iconValue.ValueKind != JsonValueKind.Number || !iconValue.TryGetInt32(out icon)
                         || icon < 1 || icon > MostGameItem || icon == 254 || icon == 255)
                {
                    problems.Add($"its Icon is one of the game's items' icons (by its number: 1 to 253, or 256 to "
                                 + $"{MostGameItem}), or its own texture's files' name (small letters, digits and _, 1 to "
                                 + $"64 of them), not {Raw(root, "Icon")}");
                    return null;
                }
                if (own.Length > 0)
                {
                    var missing = new List<string>();
                    foreach (var path in IconFiles(own))
                        if (!hasFile(path))
                            missing.Add(path);
                    if (missing.Count > 0)
                    {
                        problems.Add($"its icon's texture files aren't in the mod ({string.Join(", ", missing)})");
                        return null;
                    }
                }
                // Its Item row's UI category and sort, as the game item it was copied from has them (else none).
                int uiCategory = -1, sort = -1;
                if (Has(root, "UiCategory", out var ui) && (ui.ValueKind != JsonValueKind.Number
                                                            || !ui.TryGetInt32(out uiCategory) || uiCategory < 0
                                                            || uiCategory > 255))
                {
                    problems.Add($"its UiCategory is the Item table's UI category of the game item it was copied from "
                                 + $"(0 to 255), not {Raw(root, "UiCategory")}");
                    return null;
                }
                if (Has(root, "Sort", out var so) && (so.ValueKind != JsonValueKind.Number || !so.TryGetInt32(out sort)
                                                      || sort < 0 || sort > 999999))
                {
                    problems.Add($"its Sort is the Item table's sort of the game item it was copied from (0 to 999999), "
                                 + $"not {Raw(root, "Sort")}");
                    return null;
                }
                // (1.27.0) The game's towns whose Outfitters sell it (each by its place, 0 to 14, once), and its Item
                // row's UI status effect and random damage, as Mod Studio sets them from what it does.
                var shops = new List<int>();
                if (Has(root, "Shops", out var listed))
                {
                    bool good = listed.ValueKind == JsonValueKind.Array;
                    if (good)
                    {
                        foreach (var t in listed.EnumerateArray())
                        {
                            if (t.ValueKind != JsonValueKind.Number || !t.TryGetInt32(out int town) || town < 0
                                || town > LastTown || shops.Contains(town))
                            {
                                good = false;
                                break;
                            }
                            shops.Add(town);
                        }
                    }
                    if (!good)
                    {
                        problems.Add($"its Shops are the game's towns whose Outfitters sell it, each by its number (0 to "
                                     + $"{LastTown}) and once, not {Raw(root, "Shops")}");
                        return null;
                    }
                }
                int uiStatus = 0;
                if (Has(root, "UiStatus", out var us) && (us.ValueKind != JsonValueKind.Number
                                                          || !us.TryGetInt32(out uiStatus) || uiStatus < 0
                                                          || uiStatus > MostUiStatus))
                {
                    problems.Add($"its UiStatus is the Item table's UI status effect for what it does (0 to "
                                 + $"{MostUiStatus}), not {Raw(root, "UiStatus")}");
                    return null;
                }
                bool random = false;
                if (Has(root, "RandomDamage", out var rd))
                {
                    if (rd.ValueKind == JsonValueKind.True)
                        random = true;
                    else if (rd.ValueKind != JsonValueKind.False)
                    {
                        problems.Add($"its RandomDamage is true or false (the Item table's random damage), not "
                                     + Raw(root, "RandomDamage"));
                        return null;
                    }
                }
                return new ModItem(modId, modName, folder, name, (ItemKind)kind, record, kindRecord, pair, bonus,
                                   wordName, singular.Length > 0 ? singular : wordName,
                                   plural.Length > 0 ? plural : wordName, description, icon, own, uiCategory, sort,
                                   shops.ToArray(), uiStatus, random);
            }
        }
    }
}
