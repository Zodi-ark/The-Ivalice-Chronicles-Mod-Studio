// Written by dev/research/sidequests/make_sprite_sites.py from Zodi's program (FFT_enhanced.exe, 17 September 2026,
// read as data) and sprites.py's measure. Not edited by hand: change that and run it again.
//
// The longer tables a job's own sprites need, every place of the game's code that names a table keyed by a sprite
// (each a pattern found once in the program's code: whole instructions, ?? where four bytes are a distance to
// somewhere else), every bound of a sprite by those tables' count, the three tests that sort a sprite or a job
// the build takes, and the two writes of a graphics slot's sprite (its portrait in the battle's panels). SpriteRoom
// holds each found to what it must be.
namespace ModStudioEventSetup
{
    public static partial class SpriteRoom
    {
        /// <summary>The longer tables: each its name, the bytes of an entry, how many entries the game's table has, and
        /// whose rows a job's own sprites take (true: its Look's; false: its Like's).</summary>
        internal static readonly (string Name, int Entry, int GameEntries, bool Look)[] Tables =
        {
            ("attributes", 4, 170, false),
            ("classic files", 8, 170, true),
            ("classic files other", 8, 170, true),
            ("palette files", 8, 170, true),
            ("palette files other", 8, 170, true),
            ("second files", 8, 170, false),
            ("second files other", 8, 170, false),
            ("sheets", 4, 170, true),
            ("second sheets", 4, 170, true),
            ("face words 1", 2, 211, true),
            ("face words 2", 2, 211, true),
            ("face words 3", 2, 211, true),
            ("face words 4", 2, 211, true),
            ("face words 5", 2, 211, true),
        };

        /// <summary>A reader: its pattern, where in it the four bytes of the distance are, whether the distance is
        /// from the instruction's end (true) or from the image's base (false), the longer table it is given, and
        /// what it names, counted from the table's first byte.</summary>
        internal static readonly (string Pattern, int At, bool Relative, int Table, int Names)[] Readers =
        {
            ("48 8B EA 48 8D 15 ?? ?? ?? ?? 45 33 FF", 6, true, 0, 1),   // 0xCC6D4
            ("41 0F B7 84 36 40 B8 00 00 0F B6 8C 81 ?? ?? ?? ??", 13, false, 0, 0),   // 0xCD8EB
            ("41 0F B7 42 1C 48 8D 0D ?? ?? ?? ??", 8, true, 0, 2),   // 0xEDBAB
            ("49 03 CA 48 8D 1D ?? ?? ?? ?? 48 89 0D ?? ?? ?? ??", 6, true, 0, 0),   // 0x1D4D17
            ("4C 8D 35 ?? ?? ?? ?? 48 8D 1D ?? ?? ?? ?? 49 8B 03", 10, true, 0, 0),   // 0x1D4EDD
            ("48 8D 2D ?? ?? ?? ?? 4C 8D 3D ?? ?? ?? ?? 45 39 62 54", 10, true, 0, 0),   // 0x1D5148
            ("48 8D 0D ?? ?? ?? ?? 41 0F BF 53 7C", 3, true, 0, 2),   // 0x1F4FB5
            ("48 8D 0D ?? ?? ?? ?? 0F B6 4C 81 03", 3, true, 0, 0),   // 0x201BEA
            ("48 8D 0D ?? ?? ?? ?? 0F B6 7C 81 03", 3, true, 0, 0),   // 0x201D3C
            ("74 24 0F B6 40 0A 48 8D 0D ?? ?? ?? ??", 9, true, 0, 3),   // 0x202159
            ("41 88 93 71 03 00 00 0F B6 8C 85 ?? ?? ?? ??", 11, false, 0, 0),   // 0x266353
            ("48 8D 0D ?? ?? ?? ?? 80 3C 81 05 73 16 0F B6 04 81 48 8D 0D ?? ?? ?? ?? 48 69 C0 08 0D 00 00", 3, true, 0, 0),   // 0x268E83
            ("C3 CC CC 0F B7 C1 48 8D 0D ?? ?? ?? ??", 9, true, 0, 1),   // 0x268EB3
            ("48 8D 15 ?? ?? ?? ?? 0F B6 8C 82 ?? ?? ?? ?? 83 E9 05", 11, false, 0, 1),   // 0x2699A8
            ("8B 8B 5C 01 00 00 4C 8D 05 ?? ?? ?? ??", 9, true, 0, 0),   // 0x269C66
            ("0F B6 43 0A 48 8D 0D ?? ?? ?? ?? 8A 0C 81", 7, true, 0, 1),   // 0x269E5E
            ("41 0F B6 40 0A 48 8D 15 ?? ?? ?? ??", 8, true, 0, 0),   // 0x26A45C
            ("45 84 FB 48 8D 0D ?? ?? ?? ?? 45 0F B7 CF", 6, true, 0, 0),   // 0x26BA94
            ("0F B6 48 0A 0F B6 84 8F ?? ?? ?? ??", 8, false, 0, 0),   // 0x26CDE9
            ("0F B6 84 AF ?? ?? ?? ?? 48 69 C8 40 18 00 00", 4, false, 0, 0),   // 0x26F452
            ("41 0F B6 8C 82 ?? ?? ?? ?? 83 F9 05 0F 82 ?? ?? ?? ??", 5, false, 0, 1),   // 0x26FDA7
            ("41 0F B6 8C 82 ?? ?? ?? ?? 83 F9 05 72 71", 5, false, 0, 0),   // 0x26FE09
            ("48 8D 0D ?? ?? ?? ?? 0F B6 0C 81 8B C1 48 83 C4 28 C3 48 83 EC 28", 3, true, 0, 3),   // 0x2736BE
            ("48 8D 0D ?? ?? ?? ?? 0F B6 0C 81 8B C1 48 83 C4 28 C3 48 8B C4", 3, true, 0, 3),   // 0x2736F6
            ("48 8D 0D ?? ?? ?? ?? 4C 8D 35 ?? ?? ?? ?? 4C 0F 44 F1", 10, true, 3, 0),   // 0x26E792
            ("48 0F BF F2 85 C0 48 8D 3D ?? ?? ?? ??", 9, true, 1, 0),   // 0x26FD69
            ("85 C0 48 8D 0D ?? ?? ?? ?? 4C 8D 35 ?? ?? ?? ??", 5, true, 4, 0),   // 0x26E78B
            ("8B 40 08 48 8D 0D ?? ?? ?? ?? 48 0F BF F2", 6, true, 2, 0),   // 0x26FD5C
            ("48 8D 0D ?? ?? ?? ?? 4C 8D 05 ?? ?? ?? ?? 4C 0F 44 C1 41 8B 0C F8", 3, true, 5, 0),   // 0x2128D9
            ("4C 8D 05 ?? ?? ?? ?? 4C 0F 44 C1 41 8B 0C F8", 3, true, 6, 0),   // 0x2128E0
            ("05 43 27 00 00 E9 ?? ?? ?? ?? 80 7E 0A AA 0F 83 ?? ?? ?? ?? 0F B6 46 0A 8B 8C 82 ?? ?? ?? ??", 27, false, 7, 0),   // 0x261722
            ("05 53 27 00 00 E9 ?? ?? ?? ?? 80 7E 0A AA 0F 83 ?? ?? ?? ?? 0F B6 46 0A 8B 8C 82 ?? ?? ?? ??", 27, false, 7, 0),   // 0x2617B2
            ("41 BD 0D 00 00 00 41 8B 8C 83 ?? ?? ?? ??", 10, false, 7, 0),   // 0x2618FC
            ("0F B6 41 0A 41 8B 84 87 ?? ?? ?? ??", 8, false, 7, 0),   // 0x26C33F
            ("77 3E 48 0F BF C5 8B 8C 87 ?? ?? ?? ??", 9, false, 7, 0),   // 0x26F014
            ("77 17 48 0F BF C5 8B 8C 87 ?? ?? ?? ??", 9, false, 7, 0),   // 0x26F03B
            ("77 11 48 8D 0D ?? ?? ?? ?? 42 8B 3C B1", 5, true, 7, 0),   // 0xCE26C
            ("41 8B 84 BA ?? ?? ?? ?? 41 83 C8 FF", 4, false, 8, 0),   // 0x212953
            ("44 0F B7 8C 46 ?? ?? ?? ?? 41 8A C0", 5, false, 9, 0),   // 0x2B56EA
            ("48 63 C2 48 8D 0D ?? ?? ?? ?? 0F B7 3C 41", 6, true, 10, 0),   // 0x2C0853
            ("48 63 C1 41 0F B7 8C 43 ?? ?? ?? ??", 8, false, 11, 0),   // 0x2DB41E
            ("48 63 C1 45 0F B7 84 44 ?? ?? ?? ??", 8, false, 12, 0),   // 0x300985
            ("48 63 C1 45 0F B7 84 42 ?? ?? ?? ??", 8, false, 12, 0),   // 0x300F39
            ("45 0F B7 9C 47 ?? ?? ?? ?? 41 8A C0", 5, false, 13, 0),   // 0x32AC23
        };

        /// <summary>A bound: its pattern, where in it the number is (one byte of it; the others are 0), the number
        /// as the game has it, and what it becomes.</summary>
        internal static readonly (string Pattern, int At, int Was, int Becomes)[] Bounds =
        {
            ("05 43 27 00 00 E9 ?? ?? ?? ?? 80 7E 0A AA", 13, 0xAA, 0xFF),   // 0x261714
            ("05 53 27 00 00 E9 ?? ?? ?? ?? 80 7E 0A AA", 13, 0xAA, 0xFF),   // 0x2617A4
            ("EB 67 80 7E 0A AA 73 5B", 5, 0xAA, 0xFF),   // 0x2618EC
            ("74 31 80 79 0A AA 73 2B", 5, 0xAA, 0xFF),   // 0x26C335
            ("74 24 40 80 FF AA 73 1E", 5, 0xAA, 0xFF),   // 0x21294D
            ("41 81 FE A9 00 00 00 77 11", 3, 0xA9, 0xFE),   // 0xCE263
            ("75 22 B8 A9 00 00 00 66 3B E8", 3, 0xA9, 0xFE),   // 0x26F006
            ("77 21 B8 A9 00 00 00 66 3B E8", 3, 0xA9, 0xFE),   // 0x26F02D
            ("B9 AA 00 00 00 66 3B C1", 1, 0xAA, 0xFF),   // 0x304207
            ("B9 AA 00 00 00 42 0F B7 94 10 ?? ?? ?? ??", 1, 0xAA, 0xFE),   // 0x26FD05
            ("83 E9 02 81 F9 D3 00 00 00 0F 82 ?? ?? ?? ??", 5, 0xD3, 0xFF),   // 0x2B5778
            ("81 FA D3 00 00 00 73 0E", 2, 0xD3, 0xFF),   // 0x2C0848
            ("81 F9 D3 00 00 00 72 92", 2, 0xD3, 0xFF),   // 0x2DB481
            ("81 F9 D3 00 00 00 72 89", 2, 0xD3, 0xFF),   // 0x3009F1
            ("2B CE 81 F9 D3 00 00 00", 4, 0xD3, 0xFF),   // 0x300FD6
            ("81 F9 D3 00 00 00 73 0C", 2, 0xD3, 0xFF),   // 0x32AC18
        };

        /// <summary>The three tests the build takes and the two writes of a graphics slot's sprite, a call to the
        /// framework's own in their place: each its pattern, where in it the test or the write starts, and its bytes
        /// (what the call and its fill take the place of).</summary>
        internal static readonly (string Pattern, int At, string Bytes)[] Tests =
        {
            ("8D 45 A0 66 83 F8 25 0F 86 ?? ?? ?? ??", 0, "8D45A06683F825"),   // 0x26EE23, the figure
            ("42 8A 44 02 01 2C 60 3C 3A", 0, "428A4402012C603C3A"),   // 0x2690BD, the palette
            ("8D 41 B6 3C 13 45 0F 46 CA", 0, "8D41B63C13"),   // 0x368995, the cell
            ("89 8C 82 ?? ?? ?? ?? 41 0F B6 40 09", 0, "898C82E0597A03"),   // 0x26E88B, the first slot's sprite
            ("41 0F B6 4E 0A 89 8C 82 ?? ?? ?? ??", 5, "898C82E0597A03"),   // 0x26E9BB, the second slot's sprite
        };
    }
}
