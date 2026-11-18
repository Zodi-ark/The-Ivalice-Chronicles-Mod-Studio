// A mod's own action abilities: the longer table of how an ability's user moves (the road's step 4; Zodi's answer of
// 10 November 2026: "Straight to more"). The build's seventh step. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// (1.41.0) Part of the helper since new abilities moved in for test 94 (built beside it until the whole rehearsed).
//
// How an ability's user moves while it is readied and while it is done (and a third byte) is a row of three bytes for
// each ability in one table of 454 rows. Eight places of the game's code read a row by the ability's number times
// three, with no bound: for a mod's ability (549 to 1023) they would read past the table, into other tables.
//
// So, as for the abilities' effects: a longer table of the framework's own, 1,024 rows. It starts as the program's own
// bytes from the table's start (the game's 454 rows, and what follows them, which the game reads today for a number
// past 453 and reads still), and each mod's ability's row is the row of the game's ability it is like. Each of the
// eight instructions that name the game's table is given the same place in the longer one. Others may write the game's
// own table, so what is written to its 454 rows is brought over, and the mods' rows made again from the ones they are
// like.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public static partial class AbilityAnimations
    {
        /// <summary>The game's table: how many rows, and a row's bytes. The longer one: how many rows, and its bytes.</summary>
        public const int GameRows = 454, RowBytes = 3, Rows = 1024, Bytes = Rows * RowBytes;

        /// <summary>The places found: where each reader's four bytes of distance are.</summary>
        public sealed class Sites
        {
            public int Animations { get; set; }
            public int[] ReaderAt { get; } = new int[Readers.Length];
            public List<string> Missing { get; } = new List<string>();
            public bool Ok => Missing.Count == 0;
        }

        /// <summary>Where the game's table is, read from the first reader that names its first byte by a distance from
        /// the image's base: -1 where that reader isn't found once.</summary>
        public static int Locate(ReadOnlySpan<byte> image, List<Section> sections)
        {
            for (int n = 0; n < Readers.Length; n++)
            {
                var (pattern, at, relative, names) = Readers[n];
                if (relative || names != 0)
                    continue;
                var matches = Places.Search(image, sections, Places.Pattern(pattern));
                return matches.Count == 1 ? BinaryPrimitives.ReadInt32LittleEndian(image.Slice(matches[0] + at, 4)) : -1;
            }
            return -1;
        }

        /// <summary>Every reader, each found once by its bytes and held to naming the byte of the table measured.</summary>
        public static Sites Find(ReadOnlySpan<byte> image, List<Section> sections, int animations)
        {
            var sites = new Sites { Animations = animations };
            AbilityRecords.FindReaders(image, sections, animations, Readers, "the abilities' animations' reader", sites.ReaderAt,
                                       sites.Missing);
            return sites;
        }

        /// <summary>The changes of the game's code for a longer table at `table`.</summary>
        public static List<JobRoom.Change>? Changes(Sites sites, ulong imageBase, ulong table)
            => AbilityRecords.ReaderChanges(Readers, sites.ReaderAt, imageBase, table);

        /// <summary>The longer table as it starts: the program's own bytes from the game's table's start (`game`, the
        /// longer table's length of them).</summary>
        public static void Fill(ReadOnlySpan<byte> game, Span<byte> table) => game.Slice(0, Bytes).CopyTo(table);

        /// <summary>Each mod's ability's row: the row the longer table has for the game's ability it is like.</summary>
        public static void Likes(Span<byte> table, IList<AbilityFile.Given> given)
        {
            foreach (var g in given)
                table.Slice(RowBytes * g.Ability.Like, RowBytes).CopyTo(table.Slice(RowBytes * g.Number, RowBytes));
        }

        /// <summary>What has been written to the game's own 454 rows since they were last seen (`kept`) brought over to
        /// the longer table, row by row, and kept. How many rows were. (The mods' rows are to be made again after:
        /// `Likes`.)</summary>
        public static int Sync(ReadOnlySpan<byte> game, Span<byte> kept, Span<byte> table)
        {
            int brought = 0;
            for (int n = 0; n < GameRows; n++)
            {
                var now = game.Slice(RowBytes * n, RowBytes);
                var was = kept.Slice(RowBytes * n, RowBytes);
                if (now.SequenceEqual(was))
                    continue;
                now.CopyTo(table.Slice(RowBytes * n, RowBytes));
                now.CopyTo(was);
                brought++;
            }
            return brought;
        }
    }
}
