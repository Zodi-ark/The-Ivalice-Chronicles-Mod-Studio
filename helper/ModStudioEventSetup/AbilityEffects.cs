// A mod's own action abilities: the longer table of the abilities' effects (the road's step 4; Zodi's answer of 10
// November 2026: "Straight to more"). Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// (1.41.0) Part of the helper since new abilities moved in for test 94 (built beside it until the whole rehearsed).
//
// What plays when an ability is used is a word for each ability in one table of 454 words. Three places of the game's
// code read that word by the ability's number with no bound: a routine that says whether an ability has no effect
// (its word below 0), and two reads in the battle's own long function. For a mod's ability (549 to 1023) they would
// read past the table.
//
// So, as for the abilities' records: a longer table of the framework's own, 1,024 words. It starts as the program's
// own bytes from the table's start (the game's 454 words, and what follows them, which the game reads today for a
// number past 453 and reads still), and each mod's ability's word is the word of the game's ability it is like. Each
// of the four instructions that name the game's table is given the same place in the longer one. Others may write the
// game's own table, so what is written to its 454 words is brought over, and the mods' words made again from the
// ones they are like.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public static partial class AbilityEffects
    {
        /// <summary>The game's table: how many words. The longer one: how many words, and its bytes.</summary>
        public const int GameWords = 454, Words = 1024, Bytes = Words * 2;

        /// <summary>The places found: where each reader's four bytes of distance are.</summary>
        public sealed class Sites
        {
            public int Effects { get; set; }
            public int[] ReaderAt { get; } = new int[Readers.Length];
            public List<string> Missing { get; } = new List<string>();
            public bool Ok => Missing.Count == 0;
        }

        /// <summary>Where the game's table of effects is, read from the first reader that names it by a distance from
        /// the image's base: -1 where that reader isn't found once.</summary>
        public static int Locate(ReadOnlySpan<byte> image, List<Section> sections)
        {
            for (int n = 0; n < Readers.Length; n++)
            {
                var (pattern, at, relative, _) = Readers[n];
                if (relative)
                    continue;
                var matches = Places.Search(image, sections, Places.Pattern(pattern));
                return matches.Count == 1 ? BinaryPrimitives.ReadInt32LittleEndian(image.Slice(matches[0] + at, 4)) : -1;
            }
            return -1;
        }

        /// <summary>Every reader, each found once by its bytes and held to naming the table's first byte.</summary>
        public static Sites Find(ReadOnlySpan<byte> image, List<Section> sections, int effects)
        {
            var sites = new Sites { Effects = effects };
            AbilityRecords.FindReaders(image, sections, effects, Readers, "the abilities' effects' reader", sites.ReaderAt, sites.Missing);
            return sites;
        }

        /// <summary>The changes of the game's code for a longer table at `table`.</summary>
        public static List<JobRoom.Change>? Changes(Sites sites, ulong imageBase, ulong table)
            => AbilityRecords.ReaderChanges(Readers, sites.ReaderAt, imageBase, table);

        /// <summary>The longer table as it starts: the program's own bytes from the game's table's start (`game`, the
        /// longer table's length of them).</summary>
        public static void Fill(ReadOnlySpan<byte> game, Span<byte> table) => game.Slice(0, Bytes).CopyTo(table);

        /// <summary>Each mod's ability's word: the word the longer table has for the game's ability it is like.</summary>
        public static void Likes(Span<byte> table, IList<AbilityFile.Given> given)
        {
            foreach (var g in given)
                table.Slice(2 * g.Ability.Like, 2).CopyTo(table.Slice(2 * g.Number, 2));
        }

        /// <summary>What has been written to the game's own 454 words since they were last seen (`kept`) brought over
        /// to the longer table, word by word, and kept. How many words were. (The mods' words are to be made again
        /// after: `Likes`.)</summary>
        public static int Sync(ReadOnlySpan<byte> game, Span<byte> kept, Span<byte> table)
        {
            int brought = 0;
            for (int n = 0; n < GameWords; n++)
            {
                var now = game.Slice(2 * n, 2);
                var was = kept.Slice(2 * n, 2);
                if (now.SequenceEqual(was))
                    continue;
                now.CopyTo(table.Slice(2 * n, 2));
                now.CopyTo(was);
                brought++;
            }
            return brought;
        }
    }
}
