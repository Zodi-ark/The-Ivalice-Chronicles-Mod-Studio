// Mod Studio Framework: (2.0.0) War of the Lions' items. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi's first point of 16 November: "Like we made Dark Knight and Onion Onion In Mod Studio Framework we should do
// the same for WotLs items from WotL Restoration to be able to be used by the framework so they can be edited on the
// Items page and can be used in Encounters page and modders new Battles and for Treasure Hunter."
//
// What was measured (dev/research/sidequests/wotl_items.py; wotl-items-research.md beside it): nothing of War of the
// Lions' 40 new items is in the game. Its program holds item records for 0 to 255 and its own five (256 to 260), and
// its Item table stops at 260; only its code still knows of them (Onion Knight's own equipment by its numbers, the
// fell swords' item type). So the framework carries each item whole: its records and equipment bonuses as War of the
// Lions has them (FFTPatcher's PSP files, Glain's, GPL-3, commit 26d45cc, read for facts only: NewItems.bin,
// NewItemAttributes.bin and Items.xml's names), at WotL Restoration's numbers (its Item table's rows, read for facts:
// War of the Lions' own numbers but for the five fell swords, at 278 to 282 since the game's own five took 256 to
// 260), so a mod that names one means the same item with either. WotL Restoration's art is its author's and isn't
// copied: each item shows an icon Zodi gave for it (his own pictures of 16 November 2026, carried beside the helper:
// IconName) and has War of the Lions' description as he gave it. (2.0.3) Its looks in battle are matched to his icon
// (dev/research/sidequests/wotl_looks.py, over his game's files of 17 November): the icon it is held up or thrown as
// (its record's first two bytes) War of the Lions' own where the game has it, else the nearest of the game's 16
// palettes (War of the Lions' 16 to 22 aren't in it); a weapon's or shield's look as it attacks or guards (its sprite
// pair) the look of the game's weapons that have its icon, in the palette nearest his icon's colors. Until 2.0.3 it
// swung the look in battle of the game's nearest item (the last of the game's items of its type; a fell sword's a
// knight's sword's, Tynar Rouge's a perfume's), still kept as each fact's Icon.
//
// They are given only where WotL Restoration hasn't given them (its page made: its items stay its own) and only once
// an enabled mod asks for them (Mod.PlanItems). Their counts are kept in a save where WotL Restoration keeps its own
// (the event variables' 0x2FC: its four bytes 57 43 01 00, then a count for each of the 55 numbers; its DLL's
// constants, read for facts), so a save goes from one to the other.
//
// The table is written by dev/research/sidequests/wotl_items.py --csharp from those files and his program, and held
// to them by dev/test_wotl_items.py where they are on hand.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace ModStudioEventSetup
{
    public static class WotLItems
    {
        // --- a mod's asking for them, and its changes of them ---------------------------------------------------------

        /// <summary>The file at a mod's root that asks for War of the Lions' items (a mod that names one anywhere has
        /// it: Mod Studio writes it), with the mod's own version of any it changed on the Items page:
        /// {"Format": "Mod Studio War of the Lions items", "Version": 1, "Items": [...]}, each of Items an item as an
        /// item.json gives one (ItemFile.cs: its Format, Version, Name, Kind, Record and the rest) with "Item", its
        /// number.</summary>
        public const string FileName = "ModStudioWotLItems.json";
        public const string Format = "Mod Studio War of the Lions items";
        public const int Version = 1;

        /// <summary>A mod's changed items by their numbers, or null where the mod has no such file (it doesn't ask
        /// for them). A file that can't be read still asks; what can't be used of it is said, and the framework's own
        /// item stands.</summary>
        public static Dictionary<int, ModItem>? ReadMod(string modId, string modName, string modFolder,
                                                        List<string> problems)
        {
            string file = Path.Combine(modFolder, FileName);
            if (!File.Exists(file))
                return null;
            try
            {
                return Read(modId, modName, File.ReadAllText(file), path => File.Exists(Path.Combine(modFolder, path)),
                            problems);
            }
            catch (Exception e) when (e is not OutOfMemoryException)
            {
                problems.Add($"{modName}'s {FileName} can't be read ({e.Message})");
                return new Dictionary<int, ModItem>();
            }
        }

        public static Dictionary<int, ModItem> Read(string modId, string modName, string text, Func<string, bool> hasFile,
                                                    List<string> problems)
        {
            var changed = new Dictionary<int, ModItem>();
            JsonDocument document;
            try
            {
                document = JsonDocument.Parse(text);
            }
            catch (JsonException e)
            {
                problems.Add($"{modName}'s {FileName} isn't JSON ({e.Message})");
                return changed;
            }
            using (document)
            {
                var root = document.RootElement;
                if (root.ValueKind != JsonValueKind.Object || !Has(root, "Format", out var format)
                    || format.ValueKind != JsonValueKind.String || format.GetString() != Format)
                {
                    problems.Add($"{modName}'s {FileName}: its Format isn't \"{Format}\"");
                    return changed;
                }
                if (!Has(root, "Version", out var version) || version.ValueKind != JsonValueKind.Number
                    || !version.TryGetInt32(out int v) || v != Version)
                {
                    problems.Add($"{modName}'s {FileName}: its Version isn't {Version}");
                    return changed;
                }
                if (!Has(root, "Items", out var items))
                    return changed;
                if (items.ValueKind != JsonValueKind.Array)
                {
                    problems.Add($"{modName}'s {FileName}: its Items isn't a list");
                    return changed;
                }
                int place = 0;
                foreach (var entry in items.EnumerateArray())
                {
                    place++;
                    if (entry.ValueKind != JsonValueKind.Object || !Has(entry, "Item", out var number)
                        || number.ValueKind != JsonValueKind.Number || !number.TryGetInt32(out int n) || Of(n) == null)
                    {
                        problems.Add($"{modName}'s {FileName}: its item {place} doesn't say which of War of the Lions' "
                                     + $"items it is (Item: one of their numbers, {First} to {Last})");
                        continue;
                    }
                    var fact = Of(n)!;
                    var said = new List<string>();
                    // Its Icon may be the framework's own for that item (IconName: the files are the framework's, not
                    // the mod's), one of the game's items', or a picture of the mod's own.
                    string[] own = ItemFile.IconFiles(IconName(n));
                    var item = ItemFile.Read(modId, modName, n.ToString(), entry.GetRawText(),
                                             path => Array.IndexOf(own, path) >= 0 || hasFile(path), said, true);
                    if (item != null && item.Kind != fact.Kind)
                    {
                        said.Add($"its Kind isn't {fact.Name}'s ({ItemFile.Kinds[(int)fact.Kind]})");
                        item = null;
                    }
                    if (item != null && changed.ContainsKey(n))
                    {
                        said.Add("the file gives it twice");
                        item = null;
                    }
                    foreach (var s in said)
                        problems.Add($"{modName}'s {ModName} item {n} ({fact.Name}): {s}");
                    if (item != null)
                        changed[n] = item;
                }
            }
            return changed;
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

        /// <summary>Whose they are in the framework's words, and the key their mod's place has in a ModItem.</summary>
        public const string ModId = "mod.studio.war.of.the.lions", ModName = "War of the Lions";
        /// <summary>WotL Restoration's numbers (its FirstNewId and MaxItemId).</summary>
        public const int First = ItemRoom.WotLFirst, Last = ItemRoom.WotLLast, Count = Last - First + 1;
        /// <summary>Where a save keeps their counts (WotL Restoration's TailOffset, its TailMagic and a count each).</summary>
        public const int Tail = ItemRoom.WotLTail, TailHeader = 4;
        public static readonly byte[] TailMagic = { 0x57, 0x43, 0x01, 0x00 };
        /// <summary>The byte of the event variables an item's count is kept in.</summary>
        public static int CountAt(int item) => Tail + TailHeader + (item - First);
        /// <summary>The story point of an item no shop sells (War of the Lions' own for all 40: past the game's 16).</summary>
        public const int NeverSold = 20;

        /// <summary>One item as the framework carries it: its number, War of the Lions' name, its kind, its 12 byte
        /// record and its kind's record (the PSP's), its equipment bonuses (26 bytes) or none, the game's nearest
        /// item, whose icon it shows and whose sprite pair it swings, and its Item row's UI category and sort.</summary>
        public sealed class Fact
        {
            public int Number { get; }
            public string Name { get; }
            public ItemKind Kind { get; }
            public byte[] Record { get; }
            public byte[] KindRecord { get; }
            public byte[]? Bonus { get; }
            public int Icon { get; }
            public byte[] Pair { get; }
            public int UiCategory { get; }
            public int Sort { get; }
            /// <summary>War of the Lions' words for it, as Zodi gave them (16 November 2026).</summary>
            public string Description { get; }

            public Fact(int number, string name, ItemKind kind, string record, string kindRecord, string? bonus,
                        int icon, string pair, int uiCategory, int sort, string description)
            {
                Number = number;
                Name = name;
                Kind = kind;
                Record = Convert.FromHexString(record);
                KindRecord = Convert.FromHexString(kindRecord);
                Bonus = bonus == null ? null : Convert.FromHexString(bonus);
                Icon = icon;
                Pair = Convert.FromHexString(pair);
                UiCategory = uiCategory;
                Sort = sort;
                Description = description;
            }
        }

        /// <summary>The name of an item's own icon's files, which the framework carries beside itself at the game's
        /// paths (ItemFile.IconFiles; helper/wotl_items/, made by dev/research/sidequests/make_wotl_icons.py from
        /// Zodi's own pictures of 16 November 2026).</summary>
        public static string IconName(int number) => $"msf_wotl_{number}";

        public static readonly Fact[] Facts =
        {
            new Fact(261, "Moonblade", ItemKind.Weapon, "080F0082000300500A001400", "018E01FF140F0000", "0000000000000000080000000000000000000000000000000000", 32, "D006", 3, 217,
                     "A sword that glitters cruelly like a crescent moon."),
            new Fact(262, "Onion Sword", ItemKind.Weapon, "0E0F0082000300000A001400", "018201FF320F0000", null, 32, "D006", 3, 218,
                     "A blade forged for swordsmen who have mastered every technique and achieved knighthood's most exalted rank."),
            new Fact(263, "Ras Algethi", ItemKind.Weapon, "082C0082000A0000606D1400", "082003FF0C050000", null, 76, "0102", 10, 807,
                     "A firearm named for Ras Algethi, the star that forms the Kneeler's head."),
            new Fact(264, "Fomalhaut", ItemKind.Weapon, "0E2C0082000A00000A001400", "082003FF12050000", null, 76, "0102", 10, 808,
                     "A firearm named for the brightest star in the Whale's Maw."),
            new Fact(265, "Francisca", ItemKind.Weapon, "0C200082000600000A001400", "018701FF18000000", null, 50, "4000", 6, 1104,
                     "This axe's small size belies its incredible destructive power."),
            new Fact(266, "Golden Axe", ItemKind.Weapon, "0B2000820006000050C31400", "018701FF1E000000", null, 50, "8000", 6, 1105,
                     "An axe said to have been a gift from spirits inhabiting a spring. Only the righteous may wield it."),
            new Fact(267, "Orochi", ItemKind.Weapon, "04070082000200000A001400", "018E06FF14050100", null, 18, "D008", 2, 1409,
                     "A katana that strikes like a savage serpent."),
            new Fact(268, "Moonsilk Blade", ItemKind.Weapon, "06070082000200000A001400", "018E01FF1A050000", null, 18, "4008", 2, 1410,
                     "The creator of this masterpiece learned the art of swordcraft in a faraway land."),
            new Fact(269, "Nirvana", ItemKind.Weapon, "022A0082000800510A001400", "018C01FF050F0200", "0003000000000000000000000000000000000000000000000000", 66, "F01C", 8, 609,
                     "A staff that can only be mastered by the enlightened."),
            new Fact(270, "Dreamwaker", ItemKind.Weapon, "062A0082000800520A001400", "018C01FF050F0000", "0004000000000000000000000000000000000000000000000000", 66, "B01C", 8, 610,
                     "A powerful staff said to give life to its owner's dreams."),
            new Fact(271, "Stardust Rod", ItemKind.Weapon, "02260082000700530A001400", "038C02FF0514002A", "0003000000000000000000000000000000000000000000000000", 58, "0018", 7, 709,
                     "A rod tipped with a meteorite fragment."),
            new Fact(272, "Crown Scepter", ItemKind.Weapon, "01260082000700540A001400", "018C01FF05140000", "0004000000000000000000000000000000000000000000000000", 58, "7018", 7, 710,
                     "A magicked rod wielded by members of the royal guard."),
            new Fact(273, "Vesper", ItemKind.Weapon, "022B0082000900000A001400", "018E01FF24000000", null, 70, "F003", 9, 1505,
                     "A weapon named after the evenstar."),
            new Fact(274, "Sagittarius Bow", ItemKind.Weapon, "07340082000C00000A001400", "051501FF18000000", null, 91, "C003", 12, 410,
                     "An enormous bow that fires meteor-like arrows."),
            new Fact(275, "Durandal", ItemKind.Weapon, "02180082000400550A001400", "018E01FF1A280200", "0000000000000000300000000000000000000000000000000000", 37, "F00E", 4, 306,
                     "A holy knight's sword said to have been forged by spirits."),
            new Fact(276, "Gae Bolg", ItemKind.Weapon, "0A3A0082000F00000A001400", "024601FF180F0000", null, 106, "F000", 15, 1209,
                     "A spear said to have been wielded by a child of the gods. Merely lifting it requires great strength."),
            new Fact(277, "Gungnir", ItemKind.Weapon, "09380082000F00000A001400", "024601FF1D0F4000", null, 106, "4000", 15, 1210,
                     "A spear with the power to pierce anything."),
            new Fact(278, "Chaosbringer", ItemKind.Weapon, "0C0E008200230000983A1400", "018501FF10000109", null, 37, "D004", 4, 307,
                     "The wielder of this sword bears the sins of his previous lives, robbing him or her of all hope."),
            new Fact(279, "Deathbringer", ItemKind.Weapon, "060E0082002300000A001400", "018501FF1400010B", null, 37, "5004", 4, 308,
                     "This sword brings death to all those who kill in the name of truth and justice."),
            new Fact(280, "Arondight", ItemKind.Weapon, "050E0082002300000A001400", "018501FF18000112", null, 37, "7004", 4, 309,
                     "It is said that a witch bestowed this sword to a knight who died an unnatural death."),
            new Fact(281, "Balmung", ItemKind.Weapon, "01100082002300000A001400", "018501FF2000012C", null, 37, "D002", 4, 310,
                     "A sword said to have been wielded by a hero from the north. A blue jewel is embedded in its broad handle."),
            new Fact(282, "Valhalla", ItemKind.Weapon, "06190082002300000A001400", "018501FF28000129", null, 37, "400E", 4, 311,
                     "A tainted blade spoken of in legends about the end of the world, said to feed upon the souls of its victims."),
            new Fact(288, "Onion Shield", ItemKind.Shield, "0C480042001300000A001400", "504B", null, 143, "6000", 19, 2017,
                     "A shield forged for swordsmen who have mastered every technique and achieved knighthood's most exalted rank."),
            new Fact(289, "Reverie Shield", ItemKind.Shield, "004800420013005660EA1400", "3219", "00000000000000000000000000000000000000000000FF000000", 143, "B000", 19, 2018,
                     "A shield imbued with resistance to various attacks."),
            new Fact(292, "Vanguard Helm", ItemKind.Head, "03550022001400000A001400", "9614", null, 156, "", 20, 3114,
                     "A helm passed down from one veteran warrior to the next. Every pit and scratch recalls a pitched battle."),
            new Fact(293, "Onion Helm", ItemKind.Head, "0F530022001400000A001400", "C800", null, 156, "", 20, 3115,
                     "A helm forged for swordsmen who have mastered every technique and achieved knighthood's most exalted rank."),
            new Fact(294, "Acacia Hat", ItemKind.Head, "03610022001500570A001400", "7814", "0000020000000000000000100800200000000000000000000000", 168, "", 21, 3014,
                     "A hat that increases agility and protects against certain status effects."),
            new Fact(295, "Brass Coronet", ItemKind.Head, "08650022001500580A001400", "3C64", "0003000000000000000000080000000000000000000000000000", 168, "", 21, 3015,
                     "A crown that boosts the potency of the wearer's magicks."),
            new Fact(300, "Grand Armor", ItemKind.Body, "0C700012001700590A001400", "AA00", "0000000000000020400000000000000000000000000000000000", 185, "", 23, 4115,
                     "Legendary armor given by the gods to a knight in honor of his service. Confers divine protection to the wearer."),
            new Fact(301, "Onion Armor", ItemKind.Body, "0D6900120017005A0A001400", "FA00", "0000000000000020700000000000000000000000000000000000", 185, "", 23, 4116,
                     "Armor forged for swordsmen who have mastered every technique and achieved knighthood's most exalted rank."),
            new Fact(302, "Minerva Bustier", ItemKind.Body, "047600120018005B0A001400", "7800", "000000000000000000000000000000000000000000D12E000000", 199, "", 24, 4016,
                     "Clothing blessed by a goddess. It provides protection against various elemental magicks."),
            new Fact(303, "Mirage Vest", ItemKind.Body, "007C00120018005C0A001400", "7800", "0000010000000000000000800080100000000000000000000000", 199, "", 24, 4017,
                     "A vest designed to increase the user's mobility. Prevents several status ailments."),
            new Fact(304, "Brave Suit", ItemKind.Body, "047C00120018005D0A001400", "A028", "0000000000000020400000000000000000000000000000000000", 199, "", 24, 4018,
                     "This battle garb is rumored to prevent its wearer from defeat as long as he or she has the will to fight."),
            new Fact(305, "Sage's Robe", ItemKind.Body, "0B8300120019005E0A001400", "7864", "00000000000000000000000000000000000000000000FF000000", 207, "", 25, 4209,
                     "A robe woven from threads that shimmer in all colors of the rainbow. Halves damage taken from elemental magick."),
            new Fact(308, "Gaius Caligae", ItemKind.Accessory, "0286000A001A005F0A001400", "0000", "0000000200000000000000000000000000000000000000000000", 214, "", 26, 5008,
                     "Military sandals bearing the name of an ancient emperor."),
            new Fact(309, "Brigand's Gloves", ItemKind.Accessory, "0E8E000A001B006030751400", "0000", "0000010000000000080000000000000000000000000000000000", 218, "", 27, 5205,
                     "Gloves that increase the wearer's mobility."),
            new Fact(310, "Onion Gloves", ItemKind.Accessory, "0F8E000A001B00610A001400", "0000", "0000000000000000000030FC0A863D0000000000000000000000", 218, "", 27, 5206,
                     "Gloves forged for swordsmen who have mastered every technique and achieved knighthood's most exalted rank."),
            new Fact(311, "Empyreal Armband", ItemKind.Accessory, "0292000A001D00620A001400", "0000", "0000010000000000000000000006080000000000000000000000", 228, "", 29, 5306,
                     "An armband that contains the power of the stars."),
            new Fact(312, "Tynar Rouge", ItemKind.Accessory, "069E000A002400630A001400", "0000", "0303000000000000380000000000000000000000000000000200", 239, "", 31, 5505,
                     "Magickal lip rouge from the popular Feyforge brand. It is a limited-edition product, making it difficult for even the richest noblewomen to obtain."),
            new Fact(313, "Sage's Ring", ItemKind.Accessory, "0690000A001C00640A001400", "0000", "0000000000000000000000000000000000000000FF000000FF00", 223, "", 28, 5407,
                     "A ring bearing a magickal jewel."),
        };

        /// <summary>The Item row's UI status effect and random damage for what a weapon does, the game's own rows' way
        /// (ItemFile's UiStatus: a formula taking the hit points it deals 1001, healing by them 1002; random damage
        /// for the axes, flails and bags, and a formula casting by its element).</summary>
        public static (int UiStatus, bool RandomDamage) Shown(Fact fact)
        {
            if (fact.Kind != ItemKind.Weapon)
                return (0, false);
            int formula = fact.KindRecord[2], type = fact.Record[5];
            return (formula == 6 ? 1001 : formula == 7 ? 1002 : 0, type == 6 || type == 9 || type == 0x11 || formula == 4);
        }

        /// <summary>An item as the framework gives it with nothing of a mod's: its name (its singular and plural the
        /// same words), its description and its own icon (Zodi's words and pictures of 16 November 2026).</summary>
        public static ModItem Item(Fact fact)
        {
            var (uiStatus, randomDamage) = Shown(fact);
            return new ModItem(ModId, ModName, fact.Number.ToString(), fact.Name, fact.Kind, (byte[])fact.Record.Clone(),
                               (byte[])fact.KindRecord.Clone(), (byte[])fact.Pair.Clone(),
                               fact.Bonus == null ? null : (byte[])fact.Bonus.Clone(), fact.Name, fact.Name, fact.Name,
                               fact.Description, fact.Icon, IconName(fact.Number), fact.UiCategory, fact.Sort, null,
                               uiStatus, randomDamage);
        }

        /// <summary>The fact of a number, or null (a number of the 55 that holds no item).</summary>
        public static Fact? Of(int number)
        {
            foreach (var fact in Facts)
                if (fact.Number == number)
                    return fact;
            return null;
        }

        /// <summary>The 40 given their numbers and, with bonuses, a row each from `firstRow` (past every row an item
        /// of the game's names); `changed` a mod's own version of an item, by its number (the last mod's to give one),
        /// in place of the framework's. `nextRow`: the first row left for the mods' own items. An item with no row
        /// left is left out and said.</summary>
        public static List<ItemRoom.Given> Plan(int firstRow, IReadOnlyDictionary<int, ModItem>? changed,
                                                List<string> said, out int nextRow)
        {
            var given = new List<ItemRoom.Given>();
            int row = firstRow;
            foreach (var fact in Facts)
            {
                ModItem item = changed != null && changed.TryGetValue(fact.Number, out var theirs) ? theirs : Item(fact);
                int r = 0;
                if (item.Bonus != null)
                {
                    if (row >= ItemRoom.Rows)
                    {
                        said.Add($"{ModName}' {fact.Name} is left out: no equipment bonus row is left for it (the game "
                                 + $"has {ItemRoom.Rows}).");
                        continue;
                    }
                    r = row++;
                }
                given.Add(new ItemRoom.Given(item, fact.Number, r));
            }
            nextRow = row;
            return given;
        }

        /// <summary>What is said once they are given.</summary>
        public static string Line(IReadOnlyList<ItemRoom.Given> given, int changed)
            => $"{ModName}' {given.Count} items are given ({given[0].Number} to {given[^1].Number}), each with its own "
               + "icon and a look in battle matched to its icon"
               + (changed == 0 ? "." : $"; {changed} as the mods changed {(changed == 1 ? "it" : "them")}.");

        /// <summary>What is said where WotL Restoration has given them.</summary>
        public const string TheirsLine = "War of the Lions' items are WotL Restoration's here: Mod Studio Framework "
                                         + "gives none of its own.";

        // --- the counts in a save ---------------------------------------------------------------------------------------

        /// <summary>Whether a save's event variables hold the counts' mark.</summary>
        public static bool Marked(ReadOnlySpan<byte> bank) => bank.Slice(Tail, TailHeader).SequenceEqual(TailMagic);

        /// <summary>The 55 counts a save's event variables hold (zeros without the mark).</summary>
        public static void Read(ReadOnlySpan<byte> bank, Span<byte> counts)
        {
            if (Marked(bank))
                bank.Slice(Tail + TailHeader, Count).CopyTo(counts);
            else
                counts.Clear();
        }

        /// <summary>The 55 counts written to the event variables (each at most the bag's most), with the mark; nothing
        /// is written where there is no mark and every count is 0 (a save that never held one stays as it was).</summary>
        public static void Write(Span<byte> bank, ReadOnlySpan<byte> counts)
        {
            bool any = false;
            foreach (byte count in counts)
                any |= count != 0;
            if (!any && !Marked(bank))
                return;
            TailMagic.CopyTo(bank.Slice(Tail, TailHeader));
            for (int i = 0; i < Count; i++)
                bank[Tail + TailHeader + i] = Math.Min(counts[i], (byte)ItemRoom.MostCount);
        }

        /// <summary>Their counts and a save's kept alike, as ItemRoom.Counts keeps the mods' items': the save's changed
        /// since last seen (a save loaded, a new game, a battle tried again) and seen so twice, the bag's counts taken
        /// from it; else the bag's changed, written to it; at a save always written. 0 nothing, 1 taken, 2 written.</summary>
        public sealed class Counts
        {
            readonly byte[] _lastTail = new byte[Count], _lastBag = new byte[Count], _settling = new byte[Count];
            bool _waiting;

            public int Sync(Span<byte> bag, Span<byte> bank, bool atSave)
            {
                Span<byte> tail = stackalloc byte[Count];
                Read(bank, tail);
                Span<byte> counts = bag.Slice(First, Count);
                int done = 0;
                if (!atSave && !tail.SequenceEqual(_lastTail))
                {
                    if (!_waiting || !tail.SequenceEqual(_settling))
                    {
                        tail.CopyTo(_settling);
                        _waiting = true;
                        return 0;
                    }
                    for (int i = 0; i < Count; i++)
                        counts[i] = Math.Min(tail[i], (byte)ItemRoom.MostCount);
                    done = 1;
                }
                else if (atSave || !counts.SequenceEqual(_lastBag))
                {
                    bool changed = !counts.SequenceEqual(_lastBag);
                    Write(bank, counts);
                    done = atSave || changed ? 2 : 0;
                }
                _waiting = false;
                Read(bank, _lastTail);
                counts.CopyTo(_lastBag);
                return done;
            }
        }
    }
}
