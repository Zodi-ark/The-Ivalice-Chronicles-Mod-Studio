// More than the game's eleven free job numbers (the road's step 3; 1.40.0, Zodi's ask of 9 and 10 November: "22
// completlely new jobs or more"; measured in dev/research/sidequests/jobs.py: RECORD_SITES, RECORD_BOUNDS).
//
// The game keeps a job's record (0x31 bytes: its skillset, innate abilities, equipment, growths, Move, Jump and so on)
// in a table of 174, and the abilities' table starts right after it. Eleven of the 174 are empty and free; a twelfth
// job of the mods' needs a number past 173, and so a record past the table's end.
//
// So, only when a job is given such a number: a longer table of the framework's own, 255 records (a unit's job is one
// byte; 255 is left out), in memory near the program. The game's 174 records are copied into it and the rest are the
// empty record the game's own unused numbers have. Then every instruction of the game's code that names the game's
// table is given the same place in the longer one (40 of them, in 30 functions: 35 by a distance from the
// instruction's end, 5 by a distance from the image's base), and every bound of a job's number by 174 is made 255 (15,
// in 15 of those functions). Each is found once by its bytes (JobRecordSites.cs, written from the program by
// dev/research/sidequests/make_record_sites.py), a reader held to what its distance names (a bound's 174 is among its
// bytes): one not
// found, and nothing is changed and no number past 173 is given.
//
// (1.40.1, his test 92: for the five jobs past 173, Job Abilities (T) on the job screen showed no Job Command until the
// unit wore the job.) One bound more, that no instruction writes as a number: the window's maker (0x2BA1FC) makes its 174
// as 0x40 + 0x6E in a register (`lea eax, [rbx + 0x6E]`, ebx kept at 0x40) and compares the job with it. It becomes
// `imul eax, ebx, 4`, 256, in the same three bytes (Computed): the nearest to 255 that room allows; a job of 255 is never
// given, and its record would be read in the table's own room. Found by following every register through each function
// of the program for 173 or 174 however made; no other bound of a job was found that way.
//
// The game's own table stays where it is, and others write it: the mod loader finds it by its bytes and writes a mod's
// JobData.xml there, and another mod's code may too. So the framework keeps a copy of it as it last saw it, and
// whatever is different since is brought over to the longer table (Sync), at the tables' load, a save's load, a
// battle's build and the job screen's filling. What the game itself writes goes through the changed instructions to
// the longer table and stays there.
//
// With eleven jobs or fewer none of this is made: the game's table and its code are as they were.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public static partial class JobRecords
    {
        /// <summary>The game's table: how many records, and a record's bytes.</summary>
        public const int GameCount = 174, RecordBytes = 0x31;
        /// <summary>The longer table: how many records (a unit's job is one byte, and 255 is left out, so every bound
        /// is one number an instruction of one byte can hold), and its bytes.</summary>
        public const int Count = 255, Bytes = Count * RecordBytes;

        /// <summary>The record every unused number of the game's has (ten bytes of defaults in its growths).</summary>
        public static readonly byte[] Empty = MakeEmpty();

        static byte[] MakeEmpty()
        {
            var record = new byte[RecordBytes];
            new byte[] { 0x0B, 0x64, 0x0B, 0x64, 0x64, 0x64, 0x32, 0x64, 0x32, 0x64 }.CopyTo(record, 14);
            return record;
        }

        /// <summary>The job numbers the mods' jobs are given where the longer table can be made: the game's eleven
        /// free ones first, then 174 to 254.</summary>
        public static readonly int[] Numbers = MakeNumbers();

        static int[] MakeNumbers()
        {
            var numbers = new List<int>(JobRoom.FreeNumbers);
            for (int n = GameCount; n < Count; n++)
                numbers.Add(n);
            return numbers.ToArray();
        }

        /// <summary>Whether a number is one the mods' jobs are given: one of the game's eleven free, or past its
        /// last.</summary>
        public static bool Given(int number) =>
            Array.IndexOf(JobRoom.FreeNumbers, number) >= 0 || (number >= GameCount && number < Count);

        /// <summary>What the log says where the longer table is made, and where jobs are left out because the other mod's
        /// page has no more places.</summary>
        public static string Line(int past) =>
            $"the game's job records are in a longer table now: {past} of the mods' jobs {(past == 1 ? "has a number" : "have numbers")} "
            + $"past the game's last ({GameCount - 1}). A save with a unit in one of them needs Mod Studio Framework.";

        public const string TheirsLine = "with Dark Knight & Onion Knight (Generic) enabled the mods' jobs take its second "
            + "page's eleven empty places, and no more can be added. Disable it to have more than eleven.";

        /// <summary>The places found: where each reader's four bytes of distance are, and each bound's number.</summary>
        public sealed class Sites
        {
            public int Records { get; set; }
            public int[] ReaderAt { get; } = new int[Readers.Length];
            public int[] BoundAt { get; } = new int[Bounds.Length];
            public int[] ComputedAt { get; } = new int[Computed.Length];
            public List<string> Missing { get; } = new List<string>();
            public bool Ok => Missing.Count == 0;
        }

        /// <summary>Every reader and every bound, each found once by its bytes and held to what it must be: a reader's
        /// distance names the game's records (at `records`) where measured; a bound's number, 174, is in its pattern.</summary>
        public static Sites Find(ReadOnlySpan<byte> image, List<Section> sections, int records)
        {
            var sites = new Sites { Records = records };
            for (int n = 0; n < Readers.Length; n++)
            {
                var (pattern, at, relative, names) = Readers[n];
                var matches = Places.Search(image, sections, Places.Pattern(pattern));
                if (matches.Count != 1)
                {
                    sites.Missing.Add($"the job records' reader {n + 1} ({matches.Count} places like it, not 1)");
                    continue;
                }
                int where = matches[0] + at;
                int distance = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(where, 4));
                long named = relative ? (long)where + 4 + distance : distance;
                if (named != records + names)
                {
                    sites.Missing.Add($"the job records' reader {n + 1} (it names another place than the records)");
                    continue;
                }
                sites.ReaderAt[n] = where;
            }
            for (int n = 0; n < Bounds.Length; n++)
            {
                var (pattern, at, _) = Bounds[n];
                var matches = Places.Search(image, sections, Places.Pattern(pattern));
                if (matches.Count != 1)
                {
                    sites.Missing.Add($"the job records' bound {n + 1} ({matches.Count} places like it, not 1)");
                    continue;
                }
                // (Its number, 174, is among the pattern's own bytes.)
                sites.BoundAt[n] = matches[0] + at;
            }
            for (int n = 0; n < Computed.Length; n++)
            {
                // (1.40.1) Its register's setting to 0x40, the bound's instruction and the compare are among the
                // pattern's own bytes.
                var (pattern, at, _, _) = Computed[n];
                var matches = Places.Search(image, sections, Places.Pattern(pattern));
                if (matches.Count != 1)
                {
                    sites.Missing.Add($"the job records' worked out bound {n + 1} ({matches.Count} places like it, not 1)");
                    continue;
                }
                sites.ComputedAt[n] = matches[0] + at;
            }
            return sites;
        }

        /// <summary>The changes of the game's code for a longer table at `table` (an address, as `imageBase` is): each
        /// reader's distance to the same place in it, each bound's number the longer count, (1.40.1) each worked out
        /// bound's instruction what it becomes. Null where a distance
        /// doesn't fit its four bytes (the table too far from the program).</summary>
        public static List<JobRoom.Change>? Changes(Sites sites, ulong imageBase, ulong table)
        {
            var changes = new List<JobRoom.Change>();
            for (int n = 0; n < Readers.Length; n++)
            {
                var (_, _, relative, names) = Readers[n];
                int where = sites.ReaderAt[n];
                long distance = relative
                    ? (long)table + names - ((long)imageBase + where + 4)
                    : (long)table + names - (long)imageBase;
                if (distance < int.MinValue || distance > int.MaxValue)
                    return null;
                var bytes = new byte[4];
                BinaryPrimitives.WriteInt32LittleEndian(bytes, (int)distance);
                changes.Add(new JobRoom.Change(where, bytes));
            }
            for (int n = 0; n < Bounds.Length; n++)
            {
                var bytes = new byte[Bounds[n].Bytes];
                bytes[0] = Count;
                changes.Add(new JobRoom.Change(sites.BoundAt[n], bytes));
            }
            for (int n = 0; n < Computed.Length; n++)
                changes.Add(new JobRoom.Change(sites.ComputedAt[n], Convert.FromHexString(Computed[n].Becomes)));
            return changes;
        }

        /// <summary>The longer table as it starts: the game's records as they are, then empty ones.</summary>
        public static void Fill(ReadOnlySpan<byte> game, Span<byte> table)
        {
            game.Slice(0, GameCount * RecordBytes).CopyTo(table);
            for (int n = GameCount; n < Count; n++)
                Empty.CopyTo(table.Slice(n * RecordBytes, RecordBytes));
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
