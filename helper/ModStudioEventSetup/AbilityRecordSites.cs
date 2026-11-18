// Written by dev/research/sidequests/make_ability_sites.py from Zodi's program (FFT_enhanced.exe, 17 September 2026,
// read as data) and abilities.py's RECORD_SITES. Not edited by hand: change that and run it again.
//
// Every place of the game's code that names the abilities' records (512 of 8 bytes), each as a pattern found once
// in the program's code (whole instructions; ?? where four bytes are a distance to somewhere else). AbilityRecords
// holds each found to what its distance names.
namespace ModStudioEventSetup
{
    public static partial class AbilityRecords
    {
        /// <summary>A reader: its pattern, where in it the four bytes of the distance are, whether the distance is
        /// from the instruction's end (true) or from the image's base (false), and which byte of the first record
        /// it names. (A distance from the instruction's end is the instruction's last four bytes in each.)</summary>
        internal static readonly (string Pattern, int At, bool Relative, int Names)[] Readers =
        {
            ("42 0F B6 94 FF ?? ?? ?? ?? B9 64 00 00 00", 5, false, 2),   // 0x2721B7
            ("48 8D 0D ?? ?? ?? ?? 48 8D 81 ?? ?? ?? ?? 4A 8D 04 C8", 10, false, 0),   // 0x275A91
            ("48 8D 0D ?? ?? ?? ?? 42 0F B6 14 D9", 3, true, 2),   // 0x2780DD
            ("75 2D 45 38 8C DA ?? ?? ?? ?? 7C 57", 6, false, 3),   // 0x2869D6
            ("B8 00 40 00 00 45 38 8C DA ?? ?? ?? ??", 9, false, 3),   // 0x286A1B
            ("75 24 47 38 8C C2 ?? ?? ?? ?? 7C 77", 6, false, 3),   // 0x28A5F7
            ("75 C9 47 38 8C C2 ?? ?? ?? ?? 7C 30", 6, false, 3),   // 0x28A652
            ("75 16 47 38 8C C2 ?? ?? ?? ?? 7C 06", 6, false, 3),   // 0x28A668
            ("48 0F BF C7 41 8A 8C C4 ?? ?? ?? ??", 8, false, 4),   // 0x309C5E
            ("88 4A 1A 41 84 9C C4 ?? ?? ?? ?? 74 06", 7, false, 7),   // 0x309C6C
            ("0F 84 ?? ?? ?? ?? 48 8D 05 ?? ?? ?? ?? 4C 8B EE", 9, true, 0),   // 0x30CD40
            ("48 8D 05 ?? ?? ?? ?? B9 64 00 00 00", 3, true, 0),   // 0x30CE28
            ("4D 03 F0 41 80 BC E8 ?? ?? ?? ?? 00", 7, false, 7),   // 0x316F1D
            ("40 FE CD 41 8B 84 C4 ?? ?? ?? ?? 89 05 ?? ?? ?? ??", 7, false, 4),   // 0x320805
            ("0F B6 0D ?? ?? ?? ?? 41 8B 84 CC ?? ?? ?? ?? 89 05 ?? ?? ?? ??", 11, false, 4),   // 0x389017
            ("41 F6 84 F4 ?? ?? ?? ?? 08 44 8B F8", 4, false, 4),   // 0x38AC0C
            ("4C 8D 15 ?? ?? ?? ?? 45 38 8C F2 ?? ?? ?? ?? 7C 4C", 11, false, 5),   // 0x38AC87
            ("B8 01 00 00 00 41 84 84 F2 ?? ?? ?? ??", 9, false, 4),   // 0x38ACC5
            ("4C 8D 15 ?? ?? ?? ?? 41 8A 8C F2 ?? ?? ?? ?? 8A D1", 11, false, 4),   // 0x38ACFD
            ("0F 84 ?? ?? ?? ?? 41 80 BC F4 ?? ?? ?? ?? 00 0F 8D ?? ?? ?? ??", 10, false, 7),   // 0x38C068
            ("75 34 48 8D 15 ?? ?? ?? ?? 41 03 FD", 5, true, 3),   // 0x392776
        };
    }

    public static partial class AbilityEffects
    {
        /// <summary>A reader of the effects' table: its pattern, where in it the four bytes of the distance are,
        /// whether the distance is from the instruction's end (true) or from the image's base (false), and which
        /// byte of the table it names.</summary>
        internal static readonly (string Pattern, int At, bool Relative, int Names)[] Readers =
        {
            ("76 2F 42 0F BF 8C 4F ?? ?? ?? ?? 66 85 C9", 7, false, 0),   // 0x212CE9
            ("EB 19 42 0F BF 8C 4F ?? ?? ?? ?? 66 85 C9", 7, false, 0),   // 0x212D18
            ("48 63 C8 0F B7 84 4F ?? ?? ?? ?? EB 18", 7, false, 0),   // 0x319BF1
            ("8D 81 6B FE FF FF 83 F8 08 76 1F 81 F9 92 00 00 00 74 17 48 63 C1 48 8D 0D ?? ?? ?? ??", 25, true, 0),   // 0x319D8A
        };
    }

    public static partial class AbilityAnimations
    {
        /// <summary>A reader of the table of how an ability's user moves (three bytes an ability): its pattern,
        /// where in it the four bytes of the distance are, whether the distance is from the instruction's end
        /// (true) or from the image's base (false), and which byte of the table it names.</summary>
        internal static readonly (string Pattern, int At, bool Relative, int Names)[] Readers =
        {
            ("48 8D 14 49 42 0F B6 8C 12 ?? ?? ?? ??", 9, false, 0),   // 0x206C4D
            ("46 0F B6 8C 10 ?? ?? ?? ?? 48 8B 05 ?? ?? ?? ??", 5, false, 1),   // 0x2127F6
            ("0F B6 84 0A ?? ?? ?? ?? 0F B6 BC 41 ?? ?? ?? ??", 4, false, 0),   // 0x26993F
            ("48 8D 0C 40 0F B6 84 11 ?? ?? ?? ??", 8, false, 1),   // 0x2699D6
            ("48 8D 0C 40 48 8D 05 ?? ?? ?? ?? 0F B6 1C 01", 7, true, 2),   // 0x205C80
            ("48 8D 05 ?? ?? ?? ?? 44 0F B6 1C 01", 3, true, 0),   // 0x2062CB
            ("48 8D 14 40 48 8D 05 ?? ?? ?? ?? 80 3C 02 00", 7, true, 0),   // 0x206F18
            ("48 8D 0C 52 48 8D 05 ?? ?? ?? ?? 44 38 34 01", 7, true, 1),   // 0x20CE39
        };
    }

    public static partial class AbilityRoom
    {
        /// <summary>A central routine taken at its first instructions: its name, its pattern from its first byte,
        /// and how many bytes its first whole instructions are (done in the framework's own code before going
        /// back).</summary>
        internal static readonly (string Name, string Pattern, int Length)[] Entries =
        {
            ("reader", "41 B8 B0 00 00 00 4C 63 CA", 6),   // 0x275860
            ("action record", "40 53 48 83 EC 20 48 63 D9 81 FB 6F 01 00 00", 6),   // 0x2BB060
            ("effect", "48 8B C4 48 89 58 08 48 89 68 10 48 89 70 18 48 89 78 20 41 56 48 83 EC 20 33 ED 48 8D 3D ?? ?? ?? ??", 7),   // 0x319B50
        };

        /// <summary>A compare that is to take a mod's ability for a plain action: its pattern from the compare's
        /// first byte, how many places of the program are like it (1, or 2 where a function has a twin) and which
        /// of them it is, the compare's length, the register that holds the number it compares with (0 rax, 1 rcx,
        /// 2 rdx; -1 where the number is written in the compare), where the number's four bytes start in the
        /// compare (-1 where a register holds it), the number, the length of the instruction after (a jump of
        /// two or six bytes, or an sbb of two or three), and (1.41.2) how much less than the ability the number
        /// compared is (1 where the compare is of the ability less 1 against 366).</summary>
        internal static readonly (string Pattern, int Of, int Which, int Length, int Register, int NumberAt, int Number, int Next, int Less)[] Compares =
        {
            ("81 FE 70 01 00 00 7D 10", 1, 0, 6, -1, 2, 368, 2, 0),   // 0x2062F6
            ("66 39 46 02 7C 0A B9 03 00 00 00 38 4E 01 75 30 48 8B 05 ?? ?? ?? ?? 48 89 2D ?? ?? ?? ?? 40 88 2D ?? ?? ?? ??", 2, 0, 4, 0, -1, 368, 2, 0),   // 0x229EBA
            ("66 39 47 02 0F 8D ?? ?? ?? ?? 48 8B 44 24 50", 1, 0, 4, 0, -1, 368, 6, 0),   // 0x23863F
            ("66 44 3B D8 73 10 8B CB", 1, 0, 4, 0, -1, 422, 2, 0),   // 0x2759C6
            ("41 81 F9 70 01 00 00 73 12", 1, 0, 7, -1, 3, 368, 2, 0),   // 0x275A9F
            ("66 3B F8 73 A4 0F B7 CF", 1, 0, 3, 0, -1, 368, 2, 0),   // 0x27FF83
            ("66 44 3B C0 73 24 48 8D 4C 24 20", 1, 0, 4, 0, -1, 368, 2, 0),   // 0x28012E
            ("66 39 45 DA 0F 8D ?? ?? ?? ?? 0F BF 4D DA", 1, 0, 4, 0, -1, 368, 6, 0),   // 0x280200
            ("66 39 45 E2 0F 87 ?? ?? ?? ?? 4D 8B CD", 1, 0, 4, 0, -1, 367, 6, 0),   // 0x2815E7
            ("66 44 3B E0 0F 87 ?? ?? ?? ?? 4D 8B CD", 1, 0, 4, 0, -1, 367, 6, 0),   // 0x2817D8
            ("66 39 47 02 7D 1A 0F BF 4F 02", 1, 0, 4, 0, -1, 368, 2, 0),   // 0x281C67
            ("66 3B C2 73 0A 8B C8 E8 ?? ?? ?? ??", 1, 0, 3, 2, -1, 368, 2, 0),   // 0x282C94
            ("66 39 46 02 7C 0A B9 03 00 00 00 38 4E 01 75 30 48 8B 05 ?? ?? ?? ?? 48 89 2D ?? ?? ?? ?? 40 88 2D ?? ?? ?? ??", 2, 1, 4, 0, -1, 368, 2, 0),   // 0x2E0AC2
            ("66 39 46 02 7D DA 0F BF 4E 02", 1, 0, 4, 0, -1, 368, 2, 0),   // 0x309967
            ("66 3B F8 66 1B C9 66 23 CF", 1, 0, 3, 0, -1, 368, 3, 0),   // 0x309B89
            ("66 3B D0 7D 65 0F B6 0D ?? ?? ?? ??", 1, 0, 3, 0, -1, 368, 2, 0),   // 0x316955
            ("81 FD 70 01 00 00 0F 83 ?? ?? ?? ??", 1, 0, 6, -1, 2, 368, 6, 0),   // 0x316F2C
            ("41 81 FB 70 01 00 00 7D 7E", 1, 0, 7, -1, 3, 368, 2, 0),   // 0x320829
            ("66 3B C1 7D 18 8B C8 E8 ?? ?? ?? ??", 1, 0, 3, 1, -1, 368, 2, 0),   // 0x38B3E2
            ("66 3B C1 1B DB 23 D8 89 5C 24 38 0F 84 ?? ?? ?? ?? 8D 8B 00 70 00 00 E8 ?? ?? ?? ?? 4C 8B C0 48 89 45 E0", 2, 0, 3, 1, -1, 512, 2, 0),   // 0x2289CE
            ("66 3B C1 1B DB 23 D8 89 5C 24 38 0F 84 ?? ?? ?? ?? 8D 8B 00 70 00 00 E8 ?? ?? ?? ?? 4C 8B C0 48 89 45 E0", 2, 1, 3, 1, -1, 512, 2, 0),   // 0x2DF5CA
            ("66 3B F8 77 66 8B CF E8 ?? ?? ?? ??", 1, 0, 3, 0, -1, 367, 2, 0),   // 0x282977
            ("66 44 3B D0 77 4B 41 8B CA", 1, 0, 4, 0, -1, 367, 2, 0),   // 0x30B21A
            ("66 3B F8 0F 8D ?? ?? ?? ?? F6 42 63 02", 1, 0, 3, 0, -1, 368, 6, 0),   // 0x309CFF
            ("66 3B C1 0F 87 ?? ?? ?? ?? 8B CE E8 ?? ?? ?? ??", 1, 0, 3, 1, -1, 366, 6, 1),   // 0x30DEAE
            ("66 3B C1 0F 87 ?? ?? ?? ?? 8B CF E8 ?? ?? ?? ??", 1, 0, 3, 1, -1, 366, 6, 1),   // 0x30E4C6
            ("66 3B C8 77 29 8B CF E8 ?? ?? ?? ??", 1, 0, 3, 0, -1, 366, 2, 1),   // 0x30ED09
        };

        /// <summary>A cut of an ability's number to nine bits: its pattern from the first byte the framework
        /// replaces, how many places of the program are like it and which of them it is, its kind (0 the mask
        /// written in the instruction; 1 the mask in a register, then a call; 2 then a store; 3 the mask's
        /// register taking the word; 4 the mask loaded first), the register cut (0 eax, 1 ecx, 2 edx; -1 si), and
        /// how many bytes are replaced.</summary>
        internal static readonly (string Pattern, int Of, int Which, int Kind, int Register, int Length)[] Cuts =
        {
            ("81 E1 FF 01 00 00 48 8D 54 24 38", 1, 0, 0, 1, 6),   // 0x2071AB
            ("81 E1 FF 01 00 00 4C 8D 44 24 50 E8 ?? ?? ?? ?? 48 8B 05 ?? ?? ?? ?? 48 8B 0D ?? ?? ?? ?? 66 89 A9 90 94 0A 00", 2, 0, 0, 1, 6),   // 0x229E4D
            ("23 CE E8 ?? ?? ?? ?? 83 FD 14 0F 87 ?? ?? ?? ??", 1, 0, 1, 1, 7),   // 0x238475
            ("23 C6 89 05 ?? ?? ?? ?? E9 ?? ?? ?? ?? 8B 05 ?? ?? ?? ?? 0F B6 57 01", 1, 0, 2, 0, 8),   // 0x2386D2
            ("66 23 77 02 B8 B4 01 00 00", 1, 0, 3, -1, 9),   // 0x238733
            ("B8 FF 01 00 00 23 D0 89 15 ?? ?? ?? ??", 1, 0, 4, 2, 7),   // 0x238BDD
            ("B8 FF 01 00 00 23 D0 8D 42 C4", 1, 0, 4, 2, 7),   // 0x238CE5
            ("81 E1 FF 01 00 00 49 8B D8", 1, 0, 0, 1, 6),   // 0x275A7E
            ("81 E1 FF 01 00 00 4C 8D 44 24 50 E8 ?? ?? ?? ?? 48 8B 05 ?? ?? ?? ?? 48 8B 0D ?? ?? ?? ?? 66 89 A9 90 94 0A 00", 2, 1, 0, 1, 6),   // 0x2E0A55
        };

        /// <summary>The two places of the older text's loader the framework takes: its name, its pattern from the
        /// first byte replaced, and how many bytes are replaced. (The first's pattern runs on over the loader's
        /// store of the file's pointer.)</summary>
        internal static readonly (string Name, string Pattern, int Length)[] Loader =
        {
            ("room", "48 63 DE 48 8B CB E8 ?? ?? ?? ?? 44 8B CE 49 89 84 EF ?? ?? ?? ??", 6),   // 0x2BAD6C
            ("loaded", "8B C6 49 89 9C EF ?? ?? ?? ?? 48 8B 5C 24 50", 10),   // 0x2BADA3
        };

        /// <summary>(11 November) The two places that make a readied ability again from the turn order's entry
        /// (its low byte and a past 255 flag): each one's pattern from the first byte replaced, the register
        /// holding the entry's flags (0 r12b, 1 dil), and how many bytes are replaced.</summary>
        internal static readonly (string Pattern, int Flags, int Length)[] Charging =
        {
            ("8B 84 24 B0 01 00 00 41 F6 C4 80 8D 88 00 01 00 00 0F 44 C8", 0, 20),   // 0x2151D1
            ("8B 84 24 B0 01 00 00 40 F6 C7 80 8D 88 00 01 00 00 0F 44 C8", 1, 20),   // 0x2157B4
        };

        /// <summary>(1.41.1, his test 94) The tabs' filters of a skillset's abilities: each one's pattern from its
        /// first compare, the word (0 the word a register points at, 1 a register holding it), that register (0
        /// rax, 2 rdx, 8 r8), its width (16 or 32), the registers holding the tab's low and high edge (0 ax, 1
        /// cx, 2 dx), and where the store of 0 (drop) and the step to the next word (keep) are from the place.
        /// The ten bytes from the first compare to the second jump are replaced.</summary>
        internal static readonly (string Pattern, int Word, int Register, int Width, int Low, int High, int Drop, int Keep)[] Filters =
        {
            ("66 39 0A 7C 05 66 39 02 7E 03", 0, 2, 16, 1, 0, 10, 13),   // 0x2868E2
            ("44 3B C1 7C 05 44 3B C0 7E 04", 1, 8, 32, 1, 0, 10, 14),   // 0x28A3DD
            ("66 39 10 7C 05 66 39 08 7E 03", 0, 0, 16, 2, 1, 10, 13),   // 0x3926E5
        };

        /// <summary>(1.41.2, his test 95) The battle menu's confirm: its cut of the chosen word to nine bits
        /// (`and r8d, 0x1FF`), the pattern from it, and how many bytes are replaced.</summary>
        internal const string MenuCut = "41 81 E0 FF 01 00 00 44 88 0D ?? ?? ?? ??";
        internal const int MenuCutLength = 7;

        /// <summary>(1.41.2) The turn order writer's load of a unit's readied word and the `mov edx, 0xFF` after
        /// it: the pattern from the load, and how many bytes are replaced.</summary>
        internal const string Writer = "0F B7 8C 0E A2 01 00 00 BA FF 00 00 00";
        internal const int WriterLength = 13;

        /// <summary>(1.41.2) The two places that make each turn order entry's ability again as a text code for
        /// the timeline's list (on the entry's sign): each one's pattern from the entry's low byte read, how many
        /// places are like it and which it is, and how many bytes are replaced.</summary>
        internal static readonly (string Pattern, int Of, int Which, int Length)[] Texts =
        {
            ("43 0F B6 44 8D 01 B9 00 01 00 00 03 C8 43 38 6C 8D 00 66 0F 4D C8 B8 00 70 00 00 66 03 C8 66 43 89 8C 4F 30 3B 87 01", 1, 0, 22),   // 0x3244F9
            ("43 0F B6 44 8D 01 B9 00 01 00 00 03 C8 43 38 6C 8D 00 66 0F 4D C8 B8 00 70 00 00 66 03 C8 66 43 89 8C 4F 10 A9 D3 01", 1, 0, 22),   // 0x364BCD
        };

        /// <summary>The turn order's writer, from its `lea` of the units' records (the distance at 3, from the
        /// instruction's end at 7) to its load of the readied ability (the field's four bytes at FieldAt).</summary>
        internal const string Units = "48 8D 0D ?? ?? ?? ?? 80 BC 0E A1 01 00 00 12 75 06 41 80 C2 20 EB 1B 0F B7 8C 0E A2 01 00 00";
        internal const int UnitsFieldAt = 27, UnitBytes = 0x200, UnitCount = 21;
    }
}
