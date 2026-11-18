// Mod Studio Framework: (1.44.0) a job's own textures. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// The road's step 5, its second part, a mod's own art, next in Zodi's order of 12 November ("Colors first", then the
// sprites' textures, then the portraits), measured in dev/research/sidequests/sprites.py (claude/job-sprites-research.md
// says what it means).
//
// The Enhanced look draws a sprite from two textures in g2d.dat, its upper and its lower: the game's table of them (one
// of the longer tables of SpriteRoom.cs, "sheets") gives a sprite the number of its upper texture's entry, its lower the
// next. Three places of the game's code read an entry (the menus' figures, 0xCE204; the battle's and the screens'
// textures as they are drawn, 0x415D30 and 0x41E05C), each through the same three routines: a range of entries opened
// (0x3D2450: it reads them from the file into memory, by the file's own index), an entry unpacked into the caller's
// memory (0x3D25D8: it returns how many bytes), and the range closed (0x3D25A4). The file's index has no room for an
// entry past its own (2,450 in the game this was made for), and none of the three asks how many there are.
//
// So a job whose Look gives Textures has each of its own sprites given two entries of the framework's (Entry: far past
// the file's own, each sprite two), its upper texture's and its lower's, in the sprites' table (SpriteRoom.Fill); and
// the first two routines get a hook each: asked to open just one of those entries, the first opens nothing (there is
// nothing of the file to read) and says it did; asked to unpack it, the second copies the job's texture into the
// caller's memory and says how many bytes (SpriteTextureHooks.cs). Every other entry, and every other file read through
// them, is the game's own routine's. No change of the game's code.
//
// The two routines are found by the menus' figures' calls of them (1.44.1, his test 103: the mod loader, which reads
// g2d.dat's entries for its own tex_N.bin, has hooked both by the time the framework looks, so their own first bytes
// aren't there). Where a routine doesn't start as the game's own, it is taken where the game's program file has it
// (1.44.2, his test 104: the mod loader's hooks start with a jump of a kind 1.44.1 didn't know; ProgramFile.cs). The
// framework's hook then sits before the other mod's, which Reloaded-II's shared hooks are made for.
//
// With no job with textures of its own none of this is made.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public static class SpriteTextures
    {
        /// <summary>The g2d.dat entry a job's own sprite's upper texture is given (its lower the next): far past the
        /// file's own entries, and below a number any part of the game keeps in two bytes.</summary>
        public const int FirstEntry = 0x4000;

        /// <summary>A job's own sprite's upper texture's entry (its lower is the next).</summary>
        public static int Entry(int sprite) => FirstEntry + (sprite - SpriteRoom.GameCount) * 2;

        /// <summary>(1.44.1, his test 103: in the running game the routines' own first bytes weren't found, another mod's
        /// hooks having changed them) Where the menus' figures read an entry, found once in the game's code: its calls of
        /// the opening, the unpacking and the closing (each a call's distance open), which name the routines however
        /// their first bytes have been changed.</summary>
        internal const string ReadsPattern
            = "44 8D 47 01 45 33 C9 48 89 45 80 8B D7 49 8B CF E8 ?? ?? ?? ?? 85 C0 0F 85 ?? ?? ?? ?? 4C 8B 45 80 8B D7 49 "
              + "8B CF E8 ?? ?? ?? ?? 49 8B CF E8 ?? ?? ?? ??";
        /// <summary>Where in that pattern each call is (its distance one past), and a call's bytes.</summary>
        internal const int OpenCallAt = 16, DecodeCallAt = 38, CloseCallAt = 46, CallBytes = 5;

        /// <summary>The routines' own first instructions, as the game has them (the unpacking's security cookie's distance
        /// left open): a routine a call names starts with them, in the running game or, where another mod has hooked it,
        /// in the game's program file.</summary>
        internal const string OpenPattern
            = "48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18 57 41 56 41 57 48 83 EC 30 41 8B C0 8B F2 2B C2 48 8B D9 45 85 C9";
        internal const string DecodePattern
            = "40 53 56 57 48 81 EC 90 00 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 89 84 24 80 00 00 00 8B FA 49 8B F0 33 D2 48 "
              + "8B D9 48 8D 4C 24 20 44 8D 42 58";
        /// <summary>The menus' figures' read of the file's object (its pointer's distance at 3, from the instruction's end
        /// at 7).</summary>
        internal const string ArchivePattern = "4C 8B 3D ?? ?? ?? ?? 4D 85 FF 0F 84 ?? ?? ?? ?? 48 8B 15";
        internal const int ArchiveDistanceAt = 3, ArchiveInstructionBytes = 7;

        /// <summary>The places found: the two routines and the file's object's pointer, each from the program's start.</summary>
        public sealed class Sites
        {
            public int Open { get; internal set; } = -1;
            public int Decode { get; internal set; } = -1;
            public int Archive { get; internal set; } = -1;
            public List<string> Missing { get; } = new List<string>();
            public bool Ok => Missing.Count == 0;
        }

        /// <summary>The two routines, by the menus' figures' calls of them (found once), each starting as the game's own
        /// in `image` (the program as the game runs) or in `file` (its program file, where another mod has hooked it); and
        /// the file's object's pointer, found once by its read, inside the program.</summary>
        public static Sites Find(ReadOnlySpan<byte> image, List<Section> sections, ProgramFile? file)
        {
            var sites = new Sites();
            int reads = Once(image, sections, ReadsPattern, "the menus' read of a texture", sites.Missing);
            if (reads >= 0)
            {
                sites.Open = Routine(image, reads + OpenCallAt, OpenPattern, "the textures' opening of an entry", sites.Missing,
                                     file);
                sites.Decode = Routine(image, reads + DecodeCallAt, DecodePattern, "the textures' unpacking of an entry",
                                       sites.Missing, file);
            }
            int read = Once(image, sections, ArchivePattern, "the menus' read of the textures' file", sites.Missing);
            if (read >= 0)
            {
                long at = (long)read + ArchiveInstructionBytes
                          + BinaryPrimitives.ReadInt32LittleEndian(image.Slice(read + ArchiveDistanceAt, 4));
                if (at <= 0 || at + 8 > image.Length)
                    sites.Missing.Add("the menus' read of the textures' file (it names no place in the program)");
                else
                    sites.Archive = (int)at;
            }
            return sites;
        }

        /// <summary>The routine a call at `call` names: where it starts, if inside the program and starting with the
        /// routine's own first instructions as the game runs, or, where another mod's hook sits there (of whatever kind),
        /// in the game's program file; -1 and said where it isn't.</summary>
        internal static int Routine(ReadOnlySpan<byte> image, int call, string own, string name, List<string> missing,
                           ProgramFile? file)
        {
            long at = (long)call + CallBytes + BinaryPrimitives.ReadInt32LittleEndian(image.Slice(call + 1, 4));
            if (at <= 0 || at + 16 > image.Length)
            {
                missing.Add($"{name} (the call names no place in the program)");
                return -1;
            }
            var pattern = Places.Pattern(own);
            if (Places.At(image, (int)at, pattern))
                return (int)at;
            var kept = file?.At((int)at, pattern.Length);
            if (kept == null)
            {
                missing.Add($"{name} (the place the call names isn't the routine as the game runs, and the game's program "
                            + "file couldn't be read to see whether another mod has hooked it there)");
                return -1;
            }
            if (!Places.At(kept, 0, pattern))
            {
                missing.Add($"{name} (the place the call names isn't the routine, as the game runs or in the game's program "
                            + "file)");
                return -1;
            }
            return (int)at;
        }

        /// <summary>Where a pattern is, found once; -1 and said where it isn't.</summary>
        internal static int Once(ReadOnlySpan<byte> image, List<Section> sections, string pattern, string name, List<string> missing)
        {
            var matches = Places.Search(image, sections, Places.Pattern(pattern));
            if (matches.Count == 1)
                return matches[0];
            missing.Add($"{name} ({matches.Count} places like it, not 1)");
            return -1;
        }

        /// <summary>The entries the framework answers, each with its texture's bytes: a job's own sprite's upper and lower,
        /// for each sprite whose job's Look gives it textures (its man's, its woman's).</summary>
        public static Dictionary<int, byte[]> Entries(IList<JobRoom.Given> given)
        {
            var entries = new Dictionary<int, byte[]>();
            foreach (var g in given)
                if (g.Sprite >= 0)
                    for (int woman = 0; woman < 2; woman++)
                    {
                        var textures = g.Job.Textures[woman];
                        if (textures == null)
                            continue;
                        int entry = Entry(g.Sprite + woman);
                        entries[entry] = textures[0];
                        entries[entry + 1] = textures[1];
                    }
            return entries;
        }

        /// <summary>What the opening of a range answers for the framework's entries: true (opened, nothing to read) where
        /// the range is one of them alone in the textures' file; false to hand it to the game's own routine.</summary>
        public static bool Opens(IReadOnlyDictionary<int, byte[]> entries, nint archive, nint texturesFile, int first, int last)
            => archive != 0 && archive == texturesFile && last == first + 1 && entries.ContainsKey(first);

        /// <summary>The texture the unpacking of an entry answers with: the framework's own for one of its entries in the
        /// textures' file; null to hand it to the game's own routine.</summary>
        public static byte[]? Unpacks(IReadOnlyDictionary<int, byte[]> entries, nint archive, nint texturesFile, int entry)
            => archive != 0 && archive == texturesFile && entries.TryGetValue(entry, out var bytes) ? bytes : null;

        /// <summary>The line said when the textures can't be answered.</summary>
        public static string NotLine(string why)
            => $"the jobs' own textures can't be used: {why}. Each job with textures of its own wears its Look's.";

        /// <summary>(1.44.2) For each of the framework's entries, the line said the first time the game is given one of
        /// them (once in all: whose texture it is), so a log says whether the game asked for them at all.</summary>
        public static Dictionary<int, string> FirstLines(IList<JobRoom.Given> given)
        {
            var lines = new Dictionary<int, string>();
            string[] sex = { "man's", "woman's" }, half = { "upper", "lower" };
            foreach (var g in given)
                if (g.Sprite >= 0)
                    for (int woman = 0; woman < 2; woman++)
                        if (g.Job.Textures[woman] != null)
                            for (int lower = 0; lower < 2; lower++)
                                lines[Entry(g.Sprite + woman) + lower]
                                    = $"the game was given a job's own texture for the first time ({g.Job.Who}, the "
                                      + $"{sex[woman]} {half[lower]} texture).";
            return lines;
        }
    }
}
