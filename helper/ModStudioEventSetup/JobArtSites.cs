// Written by dev/research/sidequests/make_art_sites.py from Zodi's program (FFT_enhanced.exe, 17 September
// 2026, read as data) and job_art.py's measure. Not edited by hand: change that and run it again.
//
// The four routines a job's own icons and pictures are answered at (each found by a call of it, a pattern found
// once in the program's code: whole instructions, ?? where four bytes are a distance to somewhere else; and taken
// where it starts as its own first instructions, as the game runs or in the game's program file), and the box
// loader the icon routine calls. JobArt holds each found to what it must be.
namespace ModStudioEventSetup
{
    public static partial class JobArt
    {
        /// <summary>A call of the picture routine (0xFBEB8): its pattern and where in it the call is.</summary>
        internal static readonly (string Pattern, int At) PictureCall = ("48 8D 4D 1C E8 ?? ?? ?? ?? 0F B7 4D E8", 4);   // 0x3687FA
        /// <summary>The picture routine's own first instructions.</summary>
        internal const string PictureOwn = "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 48 8B F9 41 8A F0 8B 0A 48 8B DA E8";

        /// <summary>A call of the icon routine (0x29B054): its pattern and where in it the call is.</summary>
        internal static readonly (string Pattern, int At) IconCall = ("48 83 64 24 20 00 E8 ?? ?? ?? ?? 48 8B 5C 24 40", 6);   // 0x117ED8
        /// <summary>The icon routine's own first instructions.</summary>
        internal const string IconOwn = "40 55 56 57 41 56 41 57 48 81 EC 60 02 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 89 84 24 50 02 00 00 4C 8B BC 24 B0 02 00 00 49 8B F1 41 8B F8 4C 8B F2 48 8B E9 48 8D 94 24 40 01 00 00 41 B9 04 01 00 00 41 B0 01 B9 0F 00 00 00 E8";

        /// <summary>A call of the skillset icon's name routine (0xFBF30): its pattern and where in it the call is.</summary>
        internal static readonly (string Pattern, int At) CommandNameCall = ("49 8B D9 E8 ?? ?? ?? ?? 80 BC 24 B8 01 00 00 00", 3);   // 0x29AFA7
        /// <summary>The skillset icon's name routine's own first instructions.</summary>
        internal const string CommandNameOwn = "40 53 56 57 48 81 EC 40 01 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 89 84 24 30 01 00 00 49 63 F8 8B DA 48 8B F1 48 8D 54 24 20 41 B0 01 B9 10 00 00 00";

        /// <summary>A call of the skillset icon routine (0xFBF9C): its pattern and where in it the call is.</summary>
        internal static readonly (string Pattern, int At) CommandIconCall = ("8B D3 48 8D 4D C0 E8 ?? ?? ?? ?? 48 8B 4E 18", 6);   // 0x1099F4
        /// <summary>The skillset icon routine's own first instructions.</summary>
        internal const string CommandIconOwn = "40 53 48 83 EC 20 48 8B D9 8B CA E8";

        /// <summary>Where the icon routine calls the box loader as it loads a number's icon (its second call, the one
        /// without the question mark), from the routine's start, and the box loader's own first instructions.</summary>
        internal const int BoxLoadCallAt = 0xC5;
        internal const string BoxLoadOwn = "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 30 49 8B F8 48 8B DA 48 8B F1";
    }
}
