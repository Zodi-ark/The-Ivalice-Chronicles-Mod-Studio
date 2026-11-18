// A mod's own action abilities past the game's ten open numbers (the road's step 4; Zodi's answer of 10 November 2026:
// "Straight to more"; measured in dev/research/sidequests/abilities.py: RECORD_SITES). The build's third step.
//
// (1.41.0) Part of the helper since new abilities moved in for test 94. Until the whole rehearsed, the abilities' files
// were built beside it (helper/Abilities), into the checks program only, so the helper's source stayed what 1.40.1 was
// built from.
//
// The game keeps an ability's common record (8 bytes: its cost to learn, its chance to be known, its kind's flags) in
// a table of 512, and another table starts right after it. A mod's action ability is given a number from 549 to 1023
// (512 to 548 are the game's own), and so a record past the table's end.
//
// So: a longer table of the framework's own, 1,024 records, in memory near the program. The game's 512 records are
// copied into it and the rest are empty. Then every instruction of the game's code that names a record of the game's
// table is given the same place in the longer one (21 of them, in 13 functions: 17 by a distance from the image's
// base, 4 by a distance from the instruction's end). Each is found once by its bytes (AbilityRecordSites.cs, written
// from the program by dev/research/sidequests/make_ability_sites.py) and held to what its distance names: one not
// found, and nothing is changed and no mod's ability is given a number.
//
// Eight more instructions name other kinds' small tables through the same stretch of memory (a start set back by the
// kind's first number: the jumps', the charging's, the reactions', supports' and movements'). An action's number
// never reaches them and they stay as they are.
//
// The game's own table stays where it is, and others write it (the mod loader writes a mod's ability data there). So
// the framework keeps a copy of it as it last saw it, and whatever is different since is brought over to the longer
// table (Sync), as the job records' longer table does.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public static partial class AbilityRecords
    {
        /// <summary>The game's table: how many records, and a record's bytes.</summary>
        public const int GameCount = 512, RecordBytes = 8;
        /// <summary>The longer table: how many records (ten bits: two of the game's calls cut an ability's number to
        /// ten), and its bytes.</summary>
        public const int Count = 1024, Bytes = Count * RecordBytes;
        /// <summary>The first number a mod's action ability is given: 512 to 548 are the game's own.</summary>
        public const int First = 549;

        /// <summary>The places found: where each reader's four bytes of distance are.</summary>
        public sealed class Sites
        {
            public int Records { get; set; }
            public int[] ReaderAt { get; } = new int[Readers.Length];
            public List<string> Missing { get; } = new List<string>();
            public bool Ok => Missing.Count == 0;
        }

        /// <summary>Where the game's table of the abilities' records is, read from the first reader that names its
        /// first byte by a distance from the image's base (the info's own, `lea rax, [rcx + records]`): -1 where that
        /// reader isn't found once.</summary>
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

        /// <summary>Every reader, each found once by its bytes and held to what it must be: its distance names the
        /// game's records (at `records`) where measured.</summary>
        public static Sites Find(ReadOnlySpan<byte> image, List<Section> sections, int records)
        {
            var sites = new Sites { Records = records };
            FindReaders(image, sections, records, Readers, "the abilities' records' reader", sites.ReaderAt, sites.Missing);
            return sites;
        }

        /// <summary>Each reader of a table (a pattern, where its four bytes of distance are in it, whether the distance
        /// is from the instruction's end, which byte of the table it names) found once by its bytes and held to what
        /// it names: where its distance is, into `readerAt`; one not found or naming another place said in `missing`.
        /// (The abilities' records and the effects' table are both moved to a longer one this way.)</summary>
        internal static void FindReaders(ReadOnlySpan<byte> image, List<Section> sections, int start,
                                         (string Pattern, int At, bool Relative, int Names)[] readers, string what,
                                         int[] readerAt, List<string> missing)
        {
            for (int n = 0; n < readers.Length; n++)
            {
                var (pattern, at, relative, names) = readers[n];
                var matches = Places.Search(image, sections, Places.Pattern(pattern));
                if (matches.Count != 1)
                {
                    missing.Add($"{what} {n + 1} ({matches.Count} places like it, not 1)");
                    continue;
                }
                int where = matches[0] + at;
                int distance = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(where, 4));
                long named = relative ? (long)where + 4 + distance : distance;
                if (named != start + names)
                {
                    missing.Add($"{what} {n + 1} (it names another place than the table)");
                    continue;
                }
                readerAt[n] = where;
            }
        }

        /// <summary>The changes of the game's code for a longer table at `table` (an address, as `imageBase` is): each
        /// reader's distance to the same place in it. Null where a distance doesn't fit its four bytes (the table too
        /// far from the program).</summary>
        public static List<JobRoom.Change>? Changes(Sites sites, ulong imageBase, ulong table)
            => ReaderChanges(Readers, sites.ReaderAt, imageBase, table);

        /// <summary>The changes for a table's readers found at `readerAt`: each one's distance to the same byte of a
        /// longer table at `table`. Null where a distance doesn't fit its four bytes.</summary>
        internal static List<JobRoom.Change>? ReaderChanges((string Pattern, int At, bool Relative, int Names)[] readers,
                                                           int[] readerAt, ulong imageBase, ulong table)
        {
            var changes = new List<JobRoom.Change>();
            for (int n = 0; n < readers.Length; n++)
            {
                var (_, _, relative, names) = readers[n];
                int where = readerAt[n];
                long distance = relative
                    ? (long)table + names - ((long)imageBase + where + 4)
                    : (long)table + names - (long)imageBase;
                if (distance < int.MinValue || distance > int.MaxValue)
                    return null;
                var bytes = new byte[4];
                BinaryPrimitives.WriteInt32LittleEndian(bytes, (int)distance);
                changes.Add(new JobRoom.Change(where, bytes));
            }
            return changes;
        }

        /// <summary>The longer table as it starts: the game's records as they are, then empty ones.</summary>
        public static void Fill(ReadOnlySpan<byte> game, Span<byte> table)
        {
            game.Slice(0, GameCount * RecordBytes).CopyTo(table);
            table.Slice(GameCount * RecordBytes, (Count - GameCount) * RecordBytes).Clear();
        }

        /// <summary>What has been written to the game's own table since it was last seen (`kept`, a copy of it as it
        /// was then) brought over to the longer one, record by record, and kept. How many records were.</summary>
        public static int Sync(ReadOnlySpan<byte> game, Span<byte> kept, Span<byte> table)
        {
            int brought = 0;
            for (int n = 0; n < GameCount; n++)
            {
                var now = game.Slice(n * RecordBytes, RecordBytes);
                var was = kept.Slice(n * RecordBytes, RecordBytes);
                if (now.SequenceEqual(was))
                    continue;
                now.CopyTo(table.Slice(n * RecordBytes, RecordBytes));
                now.CopyTo(was);
                brought++;
            }
            return brought;
        }
    }
}
