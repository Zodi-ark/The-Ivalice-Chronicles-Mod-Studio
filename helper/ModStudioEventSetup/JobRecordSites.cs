// Written by dev/research/sidequests/make_record_sites.py from Zodi's program (FFT_enhanced.exe, 17 September 2026,
// read as data) and jobs.py's RECORD_SITES, RECORD_BOUNDS and RECORD_COMPUTED. Not edited by hand: change those and
// run it again.
//
// Every place of the game's code that names the job records (174 of 0x31 bytes), and every bound of a job's number
// by their count, each as a pattern found once in the program's code (whole instructions; ?? where four bytes are
// a distance to somewhere else). JobRecords holds each found to what its distance names, or to the number 174.
namespace ModStudioEventSetup
{
    public static partial class JobRecords
    {
        /// <summary>A reader: its pattern, where in it the four bytes of the distance are, whether the distance is
        /// from the instruction's end (true) or from the image's base (false), and what it names, counted from the
        /// first record.</summary>
        internal static readonly (string Pattern, int At, bool Relative, int Names)[] Readers =
        {
            ("40 88 7B D0 48 8B 05 ?? ?? ?? ?? 38 43 D5", 7, true, 0x31),   // 0x21E043
            ("74 18 48 8B 15 ?? ?? ?? ?? 38 53 D5", 5, true, 0x62),   // 0x21E04F
            ("74 0C 48 8B 15 ?? ?? ?? ?? 38 53 D5", 5, true, 0x93),   // 0x21E05B
            ("45 32 E4 48 8D 05 ?? ?? ?? ?? 45 32 ED", 6, true, 0x0),   // 0x21E071
            ("33 FF 48 8D 05 ?? ?? ?? ?? 0F B6 34 01", 5, true, 0x0),   // 0x21E136
            ("45 8B F0 0F B6 B4 01 ?? ?? ?? ?? 41 8B EE", 7, false, 0x0),   // 0x27213C
            ("4C 6B C0 31 48 8D 05 ?? ?? ?? ?? 44 8B CA", 7, true, 0xE),   // 0x275DE3
            ("41 88 43 02 3A 0D ?? ?? ?? ?? 74 10", 6, true, 0x31),   // 0x2761F7
            ("74 10 3A 0D ?? ?? ?? ?? 74 08 3A 0D ?? ?? ?? ??", 4, true, 0x62),   // 0x2761FF
            ("74 08 3A 0D ?? ?? ?? ?? 75 13 0F B6 03", 4, true, 0x93),   // 0x276207
            ("42 8A 84 01 ?? ?? ?? ?? 41 88 43 07", 4, false, 0x0),   // 0x276216
            ("45 22 FD 46 0F B6 AC 01 ?? ?? ?? ??", 8, false, 0x0),   // 0x276240
            ("33 F6 44 0F B6 AC 11 ?? ?? ?? ?? 8B D6", 7, false, 0x0),   // 0x2762FA
            ("48 6B C8 31 42 8A 84 29 ?? ?? ?? ??", 8, false, 0x0),   // 0x276B43
            ("48 8B EA 48 8D 15 ?? ?? ?? ?? 48 8B D9", 6, true, 0x0),   // 0x276C7E
            ("8A 52 1D 4C 8D 1D ?? ?? ?? ?? 8D 42 FF", 6, true, 0x0),   // 0x277219
            ("4C 8D 1D ?? ?? ?? ?? 4C 6B 54 24 48 31", 3, true, 0x0),   // 0x2774A7
            ("41 F6 43 06 20 48 8D 0D ?? ?? ?? ??", 8, true, 0x1A),   // 0x27790E
            ("48 6B C8 31 48 8D 05 ?? ?? ?? ?? 8A 04 01", 7, true, 0x0),   // 0x278265
            ("48 6B C8 31 48 8D 05 ?? ?? ?? ?? 40 8A 2C 01", 7, true, 0x0),   // 0x278448
            ("4C 6B C0 31 4C 8D 15 ?? ?? ?? ?? 49 8D 52 09", 7, true, 0x0),   // 0x278713
            ("4C 6B C0 31 4C 8D 15 ?? ?? ?? ?? 33 DB", 7, true, 0x0),   // 0x278958
            ("48 6B D8 31 48 8D 05 ?? ?? ?? ?? 48 03 D8", 7, true, 0xE),   // 0x278B61
            ("48 0F BF C0 48 6B C8 31 48 8D 05 ?? ?? ?? ?? 48 03 C8 EB 02", 11, true, 0x0),   // 0x28676B
            ("41 BB AE 00 00 00 4C 8D 35 ?? ?? ?? ??", 9, true, 0x0),   // 0x286809
            ("48 6B CD 31 48 8D 05 ?? ?? ?? ?? 48 03 C8", 7, true, 0x0),   // 0x2893AF
            ("BB AE 00 00 00 48 8D 3D ?? ?? ?? ??", 8, true, 0x0),   // 0x28A40B
            ("48 8D 05 ?? ?? ?? ?? 48 03 C8 EB 03 49 8B CA", 3, true, 0x0),   // 0x28A84E
            ("73 10 48 6B C8 31 48 8D 05 ?? ?? ?? ??", 9, true, 0x0),   // 0x28AC98
            ("4C 8B E0 48 8D 35 ?? ?? ?? ?? B3 4A", 6, true, 0xE2A),   // 0x29FEAF
            ("48 6B F8 31 48 8D 05 ?? ?? ?? ?? 48 03 F8", 7, true, 0x1),   // 0x2A7777
            ("4D 6B D1 31 48 8D 05 ?? ?? ?? ?? 4C 03 D0", 7, true, 0x0),   // 0x2B56C9
            ("48 6B CE 31 48 8D 05 ?? ?? ?? ?? 48 03 C8", 7, true, 0x0),   // 0x2BA300
            ("49 6B D8 31 48 8D 05 ?? ?? ?? ?? 48 03 D8", 7, true, 0x0),   // 0x2DB402
            ("48 8D 05 ?? ?? ?? ?? 48 03 C8 EB 03 49 8B CD 48 89 0D ?? ?? ?? ??", 3, true, 0x0),   // 0x300959
            ("48 8D 05 ?? ?? ?? ?? 48 03 C8 EB 03 49 8B CE", 3, true, 0x0),   // 0x300F0D
            ("4C 6B D2 31 48 8D 05 ?? ?? ?? ?? 4C 03 D0", 7, true, 0x0),   // 0x32ABC4
            ("48 63 06 48 6B C8 31 48 8D 05 ?? ?? ?? ??", 10, true, 0x0),   // 0x348796
            ("48 63 C3 48 6B C8 31 48 8D 05 ?? ?? ?? ??", 10, true, 0x0),   // 0x34887B
            ("41 B9 AE 00 00 00 4C 8D 15 ?? ?? ?? ??", 9, true, 0x0),   // 0x39265A
        };

        /// <summary>A bound: its pattern, where in it the number 174 is, and how many bytes the number is.</summary>
        internal static readonly (string Pattern, int At, int Bytes)[] Bounds =
        {
            ("B9 AE 00 00 00 66 3B C1", 1, 4),   // 0x286759
            ("41 BB AE 00 00 00 4C 8D 35 ?? ?? ?? ??", 2, 4),   // 0x286803
            ("B8 AE 00 00 00 48 0F BF EA", 1, 4),   // 0x289399
            ("BB AE 00 00 00 48 8D 3D ?? ?? ?? ??", 1, 4),   // 0x28A406
            ("B9 AE 00 00 00 66 89 02", 1, 4),   // 0x28A839
            ("4A 0F BF 44 44 20 B9 AE 00 00 00", 7, 4),   // 0x28AC88
            ("41 81 7E 48 AE 00 00 00 73 14", 4, 4),   // 0x2A7765
            ("45 0F B6 4B 02 41 80 F9 AE", 8, 1),   // 0x2B56BF
            ("45 0F B6 41 02 41 80 F8 AE 73 0E", 8, 1),   // 0x2DB3F8
            ("74 6B 45 0F B6 41 02 41 80 F8 AE", 10, 1),   // 0x30094F
            ("0F 84 ?? ?? ?? ?? 45 0F B6 41 02 41 80 F8 AE", 14, 1),   // 0x300F03
            ("0F B6 53 02 80 FA AE 73 0E", 6, 1),   // 0x32ABBB
            ("81 3E AE 00 00 00 73 11", 2, 4),   // 0x348787
            ("81 FB AE 00 00 00 73 13", 2, 4),   // 0x34886C
            ("41 B9 AE 00 00 00 4C 8D 15 ?? ?? ?? ??", 2, 4),   // 0x392654
        };

        /// <summary>(1.40.1) A bound by 174 the game works out in a register (0x40 + 0x6E): its pattern, where in it the
        /// instruction that works it out is, its bytes, and what they become.</summary>
        internal static readonly (string Pattern, int At, string Bytes, string Becomes)[] Computed =
        {
            ("BB 40 00 00 00 66 45 85 F6 0F 8F ?? ?? ?? ?? 44 8B C3 48 8D 4C 24 70 33 D2 E8 ?? ?? ?? ?? 44 8B C3 4C 89 6D B0 33 D2 44 88 6D B8 48 8D 4D C0 E8 ?? ?? ?? ?? 66 0F 6F 05 ?? ?? ?? ?? 8D 43 6E 66 0F 7F 45 00 44 89 65 10 44 89 65 14 4C 89 6D 1C C6 44 24 32 01 66 3B F0 73 10", 60, "8D436E", "6BC304"),   // 0x2BA2DE
        };
    }
}
