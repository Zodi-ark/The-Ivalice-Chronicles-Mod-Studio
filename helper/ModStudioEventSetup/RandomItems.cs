// Mod Studio Framework: (2.0.6) a unit's Random equipment (an entry's item byte 254, Encounters' Random) reaching the
// War of the Lions items the framework gives. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi's answer of 18 November 2026 (14:05) to the offer "I can change the framework so Random can pick them too, and add
// a Required Level to their sheet": "yes we should do that".
//
// What was measured (his program read as data, never run; dev/research/sidequests/random_items.py, which holds each
// instruction this counts on by its bytes and runs the game's own function in a machine beside this one):
//
// - The putting of an entry's equipment on its unit (0x277564, Places.UnitEquipment; the unit in rcx, the entry in
//   rdx) reads the entry's five item bytes (+ 0x12 head, + 0x13 body, + 0x14 accessory, + 0x15 right hand, + 0x16 left
//   hand) and puts each on as a word (+ 0x1A head, + 0x1C body, + 0x1E accessory, + 0x20 and + 0x22 the right hand's
//   weapon and shield, + 0x24 and + 0x26 the left's; a word of 0 made 0xFF at the end). A byte of 254 is Random: the
//   game's pick (0x277F10) is asked for an item of the slot's kind, first of the types the unit's flags prefer (+ 0x9A:
//   2 a weapon held in both hands, 1 two weapons; + 0x98: 0x20 a knight's sword, 0x10 an axe, 8 a gun, 4 a spear, 2 a
//   staff or flail, 1 a rod... as the game's own order has them, then any; a head's 0x80 a helmet, a body's 0x40 an
//   armor), the left hand nothing beside a weapon whose kind record says both hands (+ 1, bit 1) or for a unit whose
//   + 0x9A has bit 2, else a second weapon (+ 0x9A bit 1) or a shield (a unit that can equip one).
// - The pick goes through the game's items of the slot's kind only (weapons 1 to 127, shields 128 to 143, head 144 to
//   171, body 172 to 207, accessories 208 to 239) and keeps each one that isn't Rare (its record's + 3, bit 2), of the
//   type asked (+ 5), of a type the unit can equip (+ 0x52, a bit a type), with the weapon flags asked (its kind
//   record's + 1) and whose required level (+ 2) is at most the unit's (+ 0x29): the item of the highest level met
//   starts the list again, any after it of no higher level joins it; one of the list by the game's random numbers
//   (four words, a xorshift: the newest word's low 15 bits times the count, over 2 to the 15), its number as a byte
//   (254: none). So nothing past 255 can be answered, whatever its level.
//
// So, for a unit with a Random slot one of the framework's own War of the Lions items could fill (not Rare, of a type
// the unit can equip, its required level at most the unit's: Wants), the framework puts the unit's equipment on itself
// in the game's place, every step as the game's function takes it and with the game's own random numbers, its pick going
// on past the game's items of the slot's kind to the given War of the Lions items of that kind, in their numbers' order,
// each tried as the game tries its own (Equip, Pick). Every other unit's is the game's own function's. With none of
// them a unit could be given the result is the game's own, draw for draw (held in a machine by
// dev/test_wotl_items.py: the game's function and this over the same units, entries and random numbers).
//
// With WotL Restoration's items in the game (its room made) the framework gives none of its own; Random reaches its
// 40 the same way where a mod gives its own version of one (ModStudioWotLItems.json): the item WotL Restoration's,
// its Required Level and Rare as the mod's version has them (the same item at the same number whichever gives it).
using System;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public static unsafe class RandomItems
    {
        // --- what the game's function reads and writes --------------------------------------------------------------

        /// <summary>An entry's five item bytes; the byte that is Random, and the item that is none.</summary>
        public const int EntryHead = 0x12, EntryBody = 0x13, EntryAccessory = 0x14, EntryRight = 0x15, EntryLeft = 0x16;
        public const int Random = 0xFE, None = 0xFF;
        /// <summary>The unit's: a flag (+ 6, 0x20: its items put on as its entry has them, nothing random), its level,
        /// the types it can equip (a bit a type from + 0x52; shields' type 19 at + 0x54, 0x10), the types it prefers
        /// (+ 0x98) and its hands (+ 0x9A).</summary>
        public const int UnitAsGiven = 6, UnitLevel = 0x29, UnitTypes = 0x52, UnitShieldByte = 0x54, UnitPrefers = 0x98,
                         UnitHands = 0x9A;
        public const int AsGivenBit = 0x20, ShieldBit = 0x10, HelmetFirst = 0x80, ArmorFirst = 0x40, BothHands = 2,
                         TwoWeapons = 1;
        /// <summary>The unit's item words (head, body, accessory, the right hand's weapon and shield, the left's).</summary>
        public const int WordHead = 0x1A, WordBody = 0x1C, WordAccessory = 0x1E, WordRightWeapon = 0x20,
                         WordRightShield = 0x22, WordLeftWeapon = 0x24, WordLeftShield = 0x26, Words = 7;
        /// <summary>The pick's slots (its dl), each its kind's items in the game.</summary>
        public const int SlotWeapon = 0x80, SlotShield = 0x40, SlotHead = 0x20, SlotBody = 0x10, SlotAccessory = 0x08;
        /// <summary>An item's record: its required level, its type flags (Rare 2, a shield 0x40, a weapon 0x80), its
        /// type; a weapon's kind record's flags (both hands forced 1).</summary>
        public const int RecordLevel = 2, RecordFlags = 3, RecordType = 5, RareBit = 2, ShieldFlag = 0x40, WeaponFlag = 0x80;
        public const int WeaponFlags = 1, ForcedBothHands = 1;
        /// <summary>The right hand's weapon types tried by the unit's + 0x98, in the game's order: (the bit, the type).
        /// </summary>
        public static readonly (int Bit, int Type)[] RightTypes = { (0x20, 3), (0x10, 5), (0x08, 0xB), (0x04, 0xF),
                                                                    (0x02, 6), (0x01, 0xA) };
        public const int HelmetType = 0x14, ArmorType = 0x17;

        /// <summary>The game's items of a slot's kind: the first, and the one past the last.</summary>
        public static (int First, int End) Range(int slot) => slot switch
        {
            SlotAccessory => (0xD0, 0xF0),
            SlotBody => (0xAC, 0xD0),
            SlotHead => (0x90, 0xAC),
            SlotShield => (0x80, 0x90),
            SlotWeapon => (1, 0x80),
            _ => (0, 0x100),
        };

        /// <summary>The item kind of a slot's items.</summary>
        public static ItemKind KindOf(int slot) => slot switch
        {
            SlotAccessory => ItemKind.Accessory,
            SlotBody => ItemKind.Body,
            SlotHead => ItemKind.Head,
            SlotShield => ItemKind.Shield,
            _ => ItemKind.Weapon,
        };

        // --- what it asks of the game --------------------------------------------------------------------------------

        /// <summary>The game as the function asks it: an item's record's byte (its 12), a weapon's kind record's byte
        /// (its 8), and the game's next random number.</summary>
        public interface IGame
        {
            byte Record(int item, int at);
            byte Weapon(int item, int at);
            uint Next();
        }

        /// <summary>The game's random numbers: four words, as the pick draws them (a xorshift).</summary>
        public static uint Next(ref uint s0, ref uint s1, ref uint s2, ref uint s3)
        {
            uint t = s0 ^ (s0 << 11);
            s0 = s1;
            s1 = s2;
            s2 = s3;
            s3 = s3 ^ (s3 >> 19) ^ t ^ (t >> 8);
            return s3;
        }

        // --- the game's function, its pick going on past the game's items -----------------------------------------------

        /// <summary>The game's pick (0x277F10) for a slot (`slot`: its kind), a weapon's flags asked (`need`, 0 none)
        /// and a type asked (`type`, 0xFF any), over the game's items of the slot's kind and then `extras` (the given
        /// War of the Lions items of that kind, in their numbers' order): an item's number, or 254 (none).</summary>
        public static int Pick(IGame game, ReadOnlySpan<byte> unit, int slot, int need, int type,
                               IReadOnlyList<int> extras)
        {
            var (first, end) = Range(slot);
            var list = new int[(end - first) + extras.Count];
            int count = 0, best = 0;
            for (int item = first; item < end; item++)
                Consider(game, unit, item, need, type, list, ref count, ref best);
            foreach (int item in extras)
                Consider(game, unit, item, need, type, list, ref count, ref best);
            if (count == 0)
                return Random;
            uint r = game.Next() & 0x7FFF;
            return list[(int)(((uint)(byte)count * r) >> 15)];
        }

        static void Consider(IGame game, ReadOnlySpan<byte> unit, int item, int need, int type, int[] list, ref int count,
                             ref int best)
        {
            if ((game.Record(item, RecordFlags) & RareBit) != 0)
                return;
            int itemType = game.Record(item, RecordType);
            if (type != 0xFF && itemType != type)
                return;
            if ((unit[UnitTypes + (itemType >> 3)] & (0x80 >> (itemType & 7))) == 0)
                return;
            if (need != 0 && (game.Weapon(item, WeaponFlags) & need) == 0)
                return;
            int level = game.Record(item, RecordLevel);
            if (level > unit[UnitLevel])
                return;
            int index = level <= best ? count : 0;
            list[index] = item;
            count = index + 1;
            if (level > best)
                best = level;
        }

        static void Word(Span<byte> unit, int at, int value)
        {
            unit[at] = (byte)value;
            unit[at + 1] = (byte)(value >> 8);
        }

        /// <summary>The game's putting of an entry's equipment on its unit (0x277564), every step as the game's
        /// function takes it, its pick going on past the game's items (`extras`: the given War of the Lions items of a
        /// kind, by kind, in their numbers' order). A unit whose + 6 has 0x20 (its items as its entry has them) isn't
        /// asked here: the game's own function runs for it (Wants).</summary>
        public static void Equip(IGame game, Span<byte> unit, ReadOnlySpan<byte> entry,
                                 IReadOnlyDictionary<ItemKind, List<int>> extras)
        {
            // The right hand: its hands' flags first, then the types it prefers, then any weapon.
            int right = entry[EntryRight];
            int hands = unit[UnitHands];
            if (right == Random)
            {
                if ((hands & BothHands) != 0)
                    right = Ask(game, unit, extras, SlotWeapon, 4, 0xFF);
                if (right == Random && (hands & TwoWeapons) != 0)
                    right = Ask(game, unit, extras, SlotWeapon, 8, 0xFF);
            }
            int prefers = unit[UnitPrefers];
            if (right == Random)
            {
                foreach (var (bit, type) in RightTypes)
                    if ((prefers & bit) != 0 && (right = Ask(game, unit, extras, SlotWeapon, 0, type)) != Random)
                        break;
                if (right == Random)
                {
                    right = Ask(game, unit, extras, SlotWeapon, 0, 0xFF);
                    if (right == Random)
                        right = None;
                }
            }
            int rightWeapon;
            if ((game.Record(right, RecordFlags) & ShieldFlag) != 0)
            {
                Word(unit, WordRightShield, right);
                rightWeapon = None;
            }
            else
            {
                Word(unit, WordRightShield, None);
                rightWeapon = right;
            }
            Word(unit, WordRightWeapon, rightWeapon);

            // The left hand: nothing beside a weapon held in both hands; else its entry's, or at Random a second weapon
            // or a shield.
            int left = entry[EntryLeft];
            bool nothing = rightWeapon != None
                           && ((game.Weapon(rightWeapon, WeaponFlags) & ForcedBothHands) != 0
                               || (unit[UnitHands] & BothHands) != 0);
            if (nothing)
                left = None;
            else if (left == Random)
            {
                if ((unit[UnitHands] & TwoWeapons) != 0)
                    left = Ask(game, unit, extras, SlotWeapon, 8, 0xFF);
                if (left == Random)
                    left = (unit[UnitShieldByte] & ShieldBit) != 0 ? Ask(game, unit, extras, SlotShield, 0, 0xFF) : None;
            }
            if ((sbyte)game.Record(left, RecordFlags) >= 0)
            {
                Word(unit, WordLeftWeapon, None);
                Word(unit, WordLeftShield, left);
            }
            else
            {
                Word(unit, WordLeftWeapon, left);
                Word(unit, WordLeftShield, None);
            }

            // The head (a helmet first where the unit prefers one), the body (an armor first), the accessory.
            int head = entry[EntryHead];
            prefers = unit[UnitPrefers];
            if (head == Random)
            {
                if ((prefers & HelmetFirst) != 0)
                    head = Ask(game, unit, extras, SlotHead, 0, HelmetType);
                if (head == Random)
                {
                    head = Ask(game, unit, extras, SlotHead, 0, 0xFF);
                    if (head == Random)
                        head = None;
                }
            }
            Word(unit, WordHead, head);
            int body = entry[EntryBody];
            if (body == Random)
            {
                if ((prefers & ArmorFirst) != 0)
                    body = Ask(game, unit, extras, SlotBody, 0, ArmorType);
                if (body == Random)
                {
                    body = Ask(game, unit, extras, SlotBody, 0, 0xFF);
                    if (body == Random)
                        body = None;
                }
            }
            Word(unit, WordBody, body);
            int accessory = entry[EntryAccessory];
            if (accessory == Random)
            {
                accessory = Ask(game, unit, extras, SlotAccessory, 0, 0xFF);
                if (accessory == Random)
                    accessory = None;
            }
            Word(unit, WordAccessory, accessory);

            // Each word of 0 none.
            for (int k = 0; k < Words; k++)
                if (unit[WordHead + 2 * k] == 0 && unit[WordHead + 2 * k + 1] == 0)
                    Word(unit, WordHead + 2 * k, None);
        }

        static readonly List<int> Empty = new List<int>();

        /// <summary>The pick as the function asks it, the given items of the slot's kind after the game's.</summary>
        static int Ask(IGame game, ReadOnlySpan<byte> unit, IReadOnlyDictionary<ItemKind, List<int>> extras, int slot,
                       int need, int type)
            => Pick(game, unit, slot, need, type, extras.TryGetValue(KindOf(slot), out var more) ? more : Empty);

        /// <summary>Whether a unit's equipment is the framework's to put on: one of its entry's Random slots could be
        /// filled by one of `extras` (not Rare, of a type the unit can equip, its required level at most the unit's);
        /// never for a unit whose items are put on as its entry has them.</summary>
        public static bool Wants(IGame game, ReadOnlySpan<byte> unit, ReadOnlySpan<byte> entry,
                                 IReadOnlyDictionary<ItemKind, List<int>> extras)
        {
            if ((unit[UnitAsGiven] & AsGivenBit) != 0)
                return false;
            return entry[EntryHead] == Random && Could(game, unit, extras, ItemKind.Head)
                   || entry[EntryBody] == Random && Could(game, unit, extras, ItemKind.Body)
                   || entry[EntryAccessory] == Random && Could(game, unit, extras, ItemKind.Accessory)
                   || (entry[EntryRight] == Random || entry[EntryLeft] == Random)
                      && Could(game, unit, extras, ItemKind.Weapon)
                   || entry[EntryLeft] == Random && Could(game, unit, extras, ItemKind.Shield);
        }

        /// <summary>Whether one of the given items of a kind could be the unit's: not Rare, of a type it can equip, its
        /// required level at most the unit's.</summary>
        static bool Could(IGame game, ReadOnlySpan<byte> unit, IReadOnlyDictionary<ItemKind, List<int>> extras,
                          ItemKind kind)
        {
            if (!extras.TryGetValue(kind, out var items))
                return false;
            foreach (int item in items)
            {
                int type = game.Record(item, RecordType);
                if ((game.Record(item, RecordFlags) & RareBit) == 0
                    && (unit[UnitTypes + (type >> 3)] & (0x80 >> (type & 7))) != 0
                    && game.Record(item, RecordLevel) <= unit[UnitLevel])
                    return true;
            }
            return false;
        }

        // --- where it is in the game ---------------------------------------------------------------------------------

        /// <summary>The game's function, whole but its first four instructions (16 bytes, where a hook goes) to its
        /// return: every step the framework's own takes as it is (a call's distance and a rip operand's open).</summary>
        public const string EquipmentWhole =
            "48 8B D9 48 8B EA 0F B6 4A 15 BF FF 00 00 00 F6 43 06 20 74 31 66 89 4B 20 66 89 7B 22 0F B6 42 16 66 89 43 "
            + "24 66 89 7B 26 0F B6 42 12 66 89 43 1A 0F B6 42 13 66 89 43 1C 0F B6 42 14 66 89 43 1E E9 AF 02 00 00 40 8A "
            + "B3 9A 00 00 00 41 B7 FE 41 3A CF 75 35 40 F6 C6 02 74 17 44 8A CF 41 B0 04 B2 80 48 8B CB E8 ?? ?? ?? ?? 8A "
            + "C8 41 3A C7 75 18 40 F6 C6 01 74 12 44 8A CF 41 B0 08 B2 80 48 8B CB E8 ?? ?? ?? ?? 8A C8 40 8A B3 98 00 00 "
            + "00 41 3A CF 0F 85 CF 00 00 00 40 F6 C6 20 74 1B 41 B1 03 45 33 C0 B2 80 48 8B CB E8 ?? ?? ?? ?? 8A C8 41 3A "
            + "C7 0F 85 AE 00 00 00 40 F6 C6 10 74 1B 41 B1 05 45 33 C0 B2 80 48 8B CB E8 ?? ?? ?? ?? 8A C8 41 3A C7 0F 85 "
            + "8D 00 00 00 40 F6 C6 08 74 17 41 B1 0B 45 33 C0 B2 80 48 8B CB E8 ?? ?? ?? ?? 8A C8 41 3A C7 75 70 40 F6 C6 "
            + "04 74 17 41 B1 0F 45 33 C0 B2 80 48 8B CB E8 ?? ?? ?? ?? 8A C8 41 3A C7 75 53 40 F6 C6 02 74 17 41 B1 06 45 "
            + "33 C0 B2 80 48 8B CB E8 ?? ?? ?? ?? 8A C8 41 3A C7 75 36 40 F6 C6 01 74 17 41 B1 0A 45 33 C0 B2 80 48 8B CB "
            + "E8 ?? ?? ?? ?? 8A C8 41 3A C7 75 19 44 8A CF 45 33 C0 B2 80 48 8B CB E8 ?? ?? ?? ?? 41 3A C7 0F B6 C8 0F 44 "
            + "CF 44 0F B6 C1 41 0F B7 C8 E8 ?? ?? ?? ?? F6 40 03 40 74 05 0F B7 C7 EB 07 41 0F B7 C0 44 8B C7 66 44 89 43 "
            + "22 0F B6 C8 66 89 43 20 44 8A 5D 16 40 3A CF 74 19 E8 ?? ?? ?? ?? F6 40 01 01 75 09 F6 83 9A 00 00 00 02 74 "
            + "05 44 8A DF EB 21 45 3A DF 75 3F F6 83 9A 00 00 00 01 74 13 44 8A CF 41 B0 08 B2 80 48 8B CB E8 ?? ?? ?? ?? "
            + "44 8A D8 45 3A DF 75 1E F6 43 54 10 74 15 44 8A CF 45 33 C0 B2 40 48 8B CB E8 ?? ?? ?? ?? 44 8A D8 EB 03 44 "
            + "8A DF 45 0F B6 C3 41 0F B7 C8 E8 ?? ?? ?? ?? 80 78 03 00 7D 05 0F B7 C7 EB 07 41 0F B7 C0 44 8B C7 66 44 89 "
            + "43 24 66 89 43 26 8A 4D 12 44 8A B3 98 00 00 00 41 3A CF 75 35 45 84 F6 79 17 41 B1 14 45 33 C0 B2 20 48 8B "
            + "CB E8 ?? ?? ?? ?? 8A C8 41 3A C7 75 19 44 8A CF 45 33 C0 B2 20 48 8B CB E8 ?? ?? ?? ?? 41 3A C7 0F B6 C8 0F "
            + "44 CF 0F B6 C1 48 8D 73 1A 66 89 06 8A 4D 13 41 3A CF 75 36 41 F6 C6 40 74 17 41 B1 17 45 33 C0 B2 10 48 8B "
            + "CB E8 ?? ?? ?? ?? 8A C8 41 3A C7 75 19 44 8A CF 45 33 C0 B2 10 48 8B CB E8 ?? ?? ?? ?? 41 3A C7 0F B6 C8 0F "
            + "44 CF 0F B6 C1 66 89 43 1C 8A 4D 14 41 3A CF 75 19 44 8A CF 45 33 C0 B2 08 48 8B CB E8 ?? ?? ?? ?? 41 3A C7 "
            + "0F B6 C8 0F 44 CF 0F B6 C1 66 89 43 1E B8 07 00 00 00 66 83 3E 00 75 03 66 89 3E 48 83 C6 02 48 83 E8 01 75 "
            + "ED 48 8B 5C 24 40 48 8B 6C 24 48 48 8B 74 24 50 48 83 C4 20 41 5F 41 5E 5F C3";
        /// <summary>Where the pattern starts in the function, and where in the function the pick, an item's record and
        /// a weapon's kind record are called (the first of each).</summary>
        public const int EquipmentWholeAt = 0x18, PickCall = 0x7E, RecordCall = 0x189, WeaponCall = 0x1B5;

        /// <summary>The game's pick, whole from its keeping of r12 to its return (a call's distance and a rip operand's
        /// open), and where its four random words are named.</summary>
        public const string PickWhole =
            "41 54 41 56 41 57 48 81 EC A0 00 00 00 44 0F B6 D2 45 8A F1 45 8A F8 4C 8B E1 41 83 EA 08 74 4E 41 83 EA 08 "
            + "74 3D 41 83 EA 10 74 2C 41 83 EA 20 74 1B 41 83 FA 40 74 0A 33 DB 41 BB 00 01 00 00 EB 35 BB 01 00 00 00 44 "
            + "8D 5B 7F EB 2A BB 80 00 00 00 44 8D 5B 10 EB 1F BB 90 00 00 00 44 8D 5B 1C EB 14 BB AC 00 00 00 44 8D 5B 24 "
            + "EB 09 BB D0 00 00 00 44 8D 5B 20 40 32 FF 40 32 ED 0F B7 CB E8 ?? ?? ?? ?? 48 8B F0 F6 40 03 02 75 6C 41 80 "
            + "FE FF 74 06 44 38 70 05 75 60 0F B6 48 05 BA 80 00 00 00 0F B6 40 05 83 E1 07 48 C1 E8 03 D3 FA 42 84 54 20 "
            + "52 74 43 45 84 FF 74 0E 0F B7 CB E8 ?? ?? ?? ?? 44 84 78 01 74 30 0F B6 56 02 41 3A 54 24 29 77 25 33 C9 40 "
            + "0F B6 C7 40 3A D5 0F 46 C8 40 0F B6 C5 0F B6 F9 8B CA 88 5C 3C 20 40 FE C7 40 3A D5 0F 46 C8 40 8A E9 FF C3 "
            + "41 3B DB 0F 8C 78 FF FF FF 40 84 FF 75 04 B0 FE EB 5C 8B 05 ?? ?? ?? ?? 8B 15 ?? ?? ?? ?? C1 E2 0B 33 15 ?? "
            + "?? ?? ?? 89 05 ?? ?? ?? ?? 8B 05 ?? ?? ?? ?? 89 05 ?? ?? ?? ?? 8B 05 ?? ?? ?? ?? 8B C8 C1 E9 0B 33 CA 89 05 "
            + "?? ?? ?? ?? C1 E9 08 33 C8 40 0F B6 C7 33 CA 89 0D ?? ?? ?? ?? 81 E1 FF 7F 00 00 0F AF C1 48 C1 E8 0F 8A 44 "
            + "04 20 4C 8D 9C 24 A0 00 00 00 49 8B 5B 20 49 8B 6B 28 49 8B 73 30 49 8B 7B 38 49 8B E3 41 5F 41 5E 41 5C C3";
        /// <summary>Where the pattern starts in the pick, and where its four random words are read (the first's read
        /// at + 0x127, the second's at + 0x121, the third's at + 0x13C, the fourth's at + 0x148).</summary>
        public const int PickWholeAt = 0x13, FirstWordRead = 0x127, SecondWordRead = 0x121, ThirdWordRead = 0x13C,
                         FourthWordRead = 0x148;

        /// <summary>Where the game's function and its asks are, from the program's start; and what wasn't found.</summary>
        public sealed class Found
        {
            public int Equipment = -1, Pick = -1, Record = -1, Weapon = -1, Words = -1;
            public readonly List<string> Missing = new List<string>();
            public bool Ok => Missing.Count == 0;
        }

        /// <summary>The game's function and its asks, from where the function is (Places.UnitEquipment) and the item
        /// functions the items' room found (its ItemCommon and ItemWeapon), each held as measured.</summary>
        public static Found Find(ReadOnlySpan<byte> image, int equipment, int itemCommon, int itemWeapon)
        {
            var found = new Found();
            if (equipment < 0)
            {
                found.Missing.Add("the putting of an entry's equipment on its unit");
                return found;
            }
            if (!Places.At(image, equipment + EquipmentWholeAt, Places.Pattern(EquipmentWhole)))
            {
                found.Missing.Add("the putting of an entry's equipment on its unit (not whole as measured)");
                return found;
            }
            found.Equipment = equipment;
            found.Pick = CallTarget(image, equipment + PickCall);
            found.Record = CallTarget(image, equipment + RecordCall);
            found.Weapon = CallTarget(image, equipment + WeaponCall);
            if (found.Pick <= 0 || found.Pick + PickWholeAt >= image.Length
                || !Places.At(image, found.Pick + PickWholeAt, Places.Pattern(PickWhole)))
                found.Missing.Add("the game's pick of a random item (not whole as measured)");
            if (found.Record != itemCommon)
                found.Missing.Add("the function's ask of an item's record (not the items' ItemCommon)");
            if (found.Weapon != itemWeapon)
                found.Missing.Add("the function's ask of a weapon's kind record (not the items' ItemWeapon)");
            if (found.Missing.Count > 0)
                return found;
            int first = WordRead(image, found.Pick + FirstWordRead);
            if (WordRead(image, found.Pick + SecondWordRead) != first + 4
                || WordRead(image, found.Pick + ThirdWordRead) != first + 8
                || WordRead(image, found.Pick + FourthWordRead) != first + 12 || first + 16 > image.Length)
                found.Missing.Add("the game's random numbers (not four words one after another, as measured)");
            else
                found.Words = first;
            return found;
        }

        /// <summary>Where a call (E8) at `at` goes, from the program's start.</summary>
        static int CallTarget(ReadOnlySpan<byte> image, int at)
            => at >= 0 && at + 5 <= image.Length ? at + 5 + BitConverter.ToInt32(image.Slice(at + 1, 4)) : -1;

        /// <summary>The word a six byte read of a rip operand (8B 05, 8B 15) at `at` names, from the program's start.
        /// </summary>
        static int WordRead(ReadOnlySpan<byte> image, int at)
            => at >= 0 && at + 6 <= image.Length ? at + 6 + BitConverter.ToInt32(image.Slice(at + 2, 4)) : -1;

        /// <summary>The War of the Lions items by kind, in their numbers' order, that could ever be a Random item: not
        /// Rare (each as the framework plans it, a mod's own version where one gives it). Empty: none can, and nothing
        /// is made.</summary>
        public static Dictionary<ItemKind, List<int>> Extras(IReadOnlyDictionary<int, ModItem> planned)
        {
            var extras = new Dictionary<ItemKind, List<int>>();
            var numbers = new List<int>(planned.Keys);
            numbers.Sort();
            foreach (int number in numbers)
            {
                var item = planned[number];
                if ((item.Record[RecordFlags] & RareBit) != 0)
                    continue;
                if (!extras.TryGetValue(item.Kind, out var list))
                    extras[item.Kind] = list = new List<int>();
                list.Add(number);
            }
            return extras;
        }

        /// <summary>What is said once it is made.</summary>
        public static string Line(Dictionary<ItemKind, List<int>> extras)
        {
            int count = 0;
            foreach (var list in extras.Values)
                count += list.Count;
            return $"Random equipment (an entry's item 254) can give War of the Lions' {count} "
                   + (count == 1 ? "item that isn't Rare" : "items that aren't Rare")
                   + ", each to a unit of at least its Required Level that can equip it, as the game gives its own.";
        }

        /// <summary>The game in memory: its item functions called (each as the game calls it: the number in cx, the
        /// record's place answered) and its four random words; a War of the Lions item's records as the framework plans
        /// it (`planned`: the framework's own, or with WotL Restoration's items in the game the same item's record as a
        /// mod's version has it, its Required Level and Rare the mod's), the same item whichever gives it.</summary>
        public sealed class Native : IGame
        {
            readonly delegate* unmanaged<ushort, byte*> _record, _weapon;
            readonly uint* _words;
            readonly IReadOnlyDictionary<int, ModItem> _planned;

            public Native(byte* start, Found found, IReadOnlyDictionary<int, ModItem> planned)
            {
                _record = (delegate* unmanaged<ushort, byte*>)(start + found.Record);
                _weapon = (delegate* unmanaged<ushort, byte*>)(start + found.Weapon);
                _words = (uint*)(start + found.Words);
                _planned = planned;
            }

            public byte Record(int item, int at)
                => _planned.TryGetValue(item, out var planned) ? planned.Record[at] : _record((ushort)item)[at];
            public byte Weapon(int item, int at)
                => _planned.TryGetValue(item, out var planned) ? planned.KindRecord[at] : _weapon((ushort)item)[at];
            public uint Next() => RandomItems.Next(ref _words[0], ref _words[1], ref _words[2], ref _words[3]);
        }

        /// <summary>The unit's bytes the function reads and writes (from its start to past + 0x9A), and the entry's.
        /// </summary>
        public const int UnitBytes = 0x9C, EntryBytes = 0x17;
    }
}
