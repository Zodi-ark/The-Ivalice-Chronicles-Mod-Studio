// Written by dev/research/sidequests/make_portrait_sites.py from Zodi's program (FFT_enhanced.exe, 17 September
// 2026, read as data) and portraits.py's measure. Not edited by hand: change that and run it again.
//
// The places of the game's code a job's own portraits change (each a pattern found once in the program's code:
// whole instructions, ?? where four bytes are a distance to somewhere else): the face to portrait routine's first
// two instructions, the bounds at 205 on the way to the Enhanced look and the switch's answers three of them hold,
// the face's file's routine, by a call of it, and (1.45.1) the HUD's cards' two bounds and the roster's face
// test. SpritePortraits holds each found to what it must be.
namespace ModStudioEventSetup
{
    public static partial class SpritePortraits
    {
        /// <summary>The face to portrait routine's first two instructions, a call to the framework's own in their place:
        /// its pattern, where in it they start, and their bytes.</summary>
        internal static readonly (string Pattern, int At, string Bytes) FaceMap = ("83 C9 FF 81 FA 9F 00 00 00", 0, "83C9FF81FA9F000000");   // 0x274028

        /// <summary>The bounds at 205, each widened to the last of the framework's portraits: its pattern and where in
        /// it the bound's four bytes are (the game's 205).</summary>
        internal static readonly (string Pattern, int At)[] Bounds =
        {
            ("81 FB CD 00 00 00 B9 FF 01 00 00", 2),   // 0x1F3A03
            ("81 FB CD 00 00 00 0F 47 DE", 2),   // 0x2C0816
            ("3D CD 00 00 00 0F 47 C6", 1),   // 0x2C086C
            ("41 B9 CD 00 00 00 3B CB", 2),   // 0x214178
            ("41 B8 CD 00 00 00 41 3B CE", 2),   // 0x2150A2
            ("41 B8 CD 00 00 00 41 3B CF", 2),   // 0x21568B
        };

        /// <summary>The switch's answers for face 0xCD the three bounds held in a register give (the register's own
        /// value), each made from eax (0xC3 there) so that it stays 205: its pattern, where in it the answer is, its
        /// bytes and what they become.</summary>
        internal static readonly (string Pattern, int At, string Bytes, string Becomes)[] Answers =
        {
            ("83 F9 04 75 31 41 8B D1", 5, "418BD1", "8D500A"),   // 0x214241
            ("83 F9 04 75 31 41 8B F8", 5, "418BF8", "8D780A"),   // 0x21516C
            ("83 F9 04 75 31 41 8B D8", 5, "418BD8", "8D580A"),   // 0x215755
        };

        /// <summary>A call of the face's file's routine (in the face widget, 0x28FF34): its pattern and where in it the
        /// call is.</summary>
        internal static readonly (string Pattern, int At) FaceFileCall = ("48 8D 4C 24 30 44 8B C6 E8 ?? ?? ?? ??", 8);   // 0x28FF8F

        /// <summary>The face's file's routine's own first instructions (its security cookie's distance open).</summary>
        internal const string FaceFileOwn = "40 53 56 57 48 81 EC 50 01 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 89 84 24 40 01 00 00 41 8B F8 8B DA 48 8B F1 48 8D 54 24 30 41 B8 04 01 00 00 B9 04 00 00 00";

        /// <summary>(1.45.1) The HUD's cards' two bounds at 205 (`cmp r11d, 0xCD; jbe; mov r11d, edi; mov edx, esi`, in
        /// the two routines that fill the cards' records): their bytes, the same at both, found by them that many
        /// times; a call of the framework's code in their place.</summary>
        internal static readonly (string Pattern, int Count) HudBound = ("41 81 FB CD 00 00 00 76 05 44 8B DF 8B D6", 2);   // 0x229A50, 0x2E065A

        /// <summary>(1.45.1) The roster's face test (the portrait routine 0x32AB3C's `test edx, 0x300`, which takes a
        /// face word with bit 8 or 9 set as no face), a call of the framework's code in its place: its pattern, where
        /// in it the test starts, and its bytes.</summary>
        internal static readonly (string Pattern, int At, string Bytes) FaceTest = ("F7 C2 00 03 00 00 75 0D", 0, "F7C200030000");   // 0x32AC46
    }
}
