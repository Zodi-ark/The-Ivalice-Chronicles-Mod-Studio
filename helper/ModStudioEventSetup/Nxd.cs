// Mod Studio Framework: the game's tables (.nxd) as it keeps them in
// memory, and a copy of one with rows added. Part of The Ivalice Chronicles
// Mod Studio, GPL-3.0.
//
// Learned from the game's own code (its program read as data, never run) and
// its files: the program keeps a table as the file it loaded, and finds rows
// through the file's own lists (the function that sets a table up from its
// file, 0x3D3F3C in Zodi's program of 17 September 2026; the counts at
// 0x3D3A34 and 0x3D3A84; the search at 0x3D43C0). So a table with rows added
// is a new file laid out as the game's are: a header, the lists the game
// reads, the loaded file kept whole (so every row it had stays as it was,
// its words and lists where they were), and the new rows after it. Nothing
// of FF16Tools or the mod loader.
//
// (1.5.0) Tables of two keys too (MapRouteTable, a road's points): the
// game's setup (0x3D3F3C) takes their rows' heads (12 bytes: the two keys,
// where the row is from the head) from the offset at 0x2C, their count at
// 0x30 (byte 9 of 3 or 4); its count of a first key's rows (0x3D3A34, through
// 0x3D3878) searches the first keys' list (from 0x20 + the offset at 0x20,
// their count at 0x24; 12 bytes each: the key, where its rows' heads are from
// the entry, how many) in order, and its row by both keys (0x3D3B5C, through
// 0x3D4304) searches the heads in the keys' order.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    /// <summary>A row a table gets: its keys (one, or three) and its bytes, with any list or
    /// words it points at inside them, pointed at from the row's start.</summary>
    public sealed class NewRow
    {
        public int[] Keys { get; }
        public byte[] Bytes { get; }

        public NewRow(int[] keys, byte[] bytes)
        {
            Keys = keys;
            Bytes = bytes;
        }
    }

    public static class Nxd
    {
        /// <summary>The header's bytes: "NXDF", its version, its kind (byte 8: 1 one key, 3 three
        /// keys), how it is kept (9), a first row's number (10 and 12), then at 0x20 where its
        /// lists are.</summary>
        public const int Header = 0x30;
        /// <summary>A key list's entry: its key, where its own list is and how long, where its rows
        /// are and how many (the game's 0x3D38DC and 0x3D3940 read them).</summary>
        public const int SetBytes = 20;
        const int OneKeyHead = 8, ThreeKeyHead = 20;
        /// <summary>(1.5.0) Two keys: a head and a first key's entry are 12 bytes each; the header has the heads'
        /// place at 0x2C and their count at 0x30, the first keys' list after it.</summary>
        const int TwoKeyHead = 12, TwoKeySet = 12, TwoKeyHeader = 0x3C;
        /// <summary>The most a table may hold before it is taken for something else.</summary>
        const int MostRows = 1 << 20;

        static int I32(ReadOnlySpan<byte> b, int at) => BinaryPrimitives.ReadInt32LittleEndian(b.Slice(at, 4));
        static void Put(Span<byte> b, int at, int value) => BinaryPrimitives.WriteInt32LittleEndian(b.Slice(at, 4), value);

        /// <summary>How many keys a table's rows have: 1, (1.5.0) 2 or 3 for the tables read here, else 0. A table of
        /// two keys is kept as 3 or 4 (byte 9: the game's setup then counts its rows at 0x30, where its heads'
        /// count is).</summary>
        public static int Keys(ReadOnlySpan<byte> table)
        {
            if (table.Length < Header || table[0] != (byte)'N' || table[1] != (byte)'X' || table[2] != (byte)'D'
                || table[3] != (byte)'F')
                return 0;
            if (table[8] == 2)
                return table.Length >= TwoKeyHeader && (table[9] == 3 || table[9] == 4) ? 2 : 0;
            return table[8] == 1 || table[8] == 3 ? table[8] : 0;
        }

        /// <summary>Where a table's rows' heads are, how many, and how long each is.</summary>
        static (int Heads, int Count, int Size) HeadsOf(ReadOnlySpan<byte> table, int keys) => keys switch
        {
            1 => (I32(table, 0x20), I32(table, 0x24), OneKeyHead),
            2 => (I32(table, 0x2C), I32(table, 0x30), TwoKeyHead),
            _ => (I32(table, 0x28), I32(table, 0x2C), ThreeKeyHead),
        };

        /// <summary>One row of a loaded table: its keys, where its bytes start, and the head's fourth
        /// number (three keys only; 0 in every row of the game's).</summary>
        public readonly struct Row
        {
            public int[] Keys { get; }
            public int At { get; }
            public int Fourth { get; }

            public Row(int[] keys, int at, int fourth)
            {
                Keys = keys;
                At = at;
                Fourth = fourth;
            }
        }

        /// <summary>A table's rows in its own order, or null and why not.</summary>
        public static List<Row>? Rows(ReadOnlySpan<byte> table, out string why)
        {
            int keys = Keys(table);
            if (keys == 0)
            {
                why = table.Length < 4 ? "it is too short to be a table" : "it isn't a table of one, two or three keys";
                return null;
            }
            var (heads, count, size) = HeadsOf(table, keys);
            if (count < 0 || count > MostRows || heads < Header || (long)heads + (long)count * size > table.Length)
            {
                why = $"its {count} rows aren't inside its {table.Length} bytes";
                return null;
            }
            var rows = new List<Row>(count);
            for (int n = 0; n < count; n++)
            {
                int head = heads + n * size;
                var k = new int[keys];
                for (int j = 0; j < keys; j++)
                    k[j] = I32(table, head + 4 * j);
                int at = head + I32(table, head + size - 4);
                if (at < 0 || at >= table.Length)
                {
                    why = $"its row {n}'s bytes aren't inside it";
                    return null;
                }
                rows.Add(new Row(k, at, keys == 3 ? I32(table, head + 12) : 0));
            }
            why = "";
            return rows;
        }

        static int Compare(int[] a, int[] b)
        {
            for (int n = 0; n < a.Length; n++)
            {
                // The game compares keys as unsigned numbers (0x3D43C0).
                int c = ((uint)a[n]).CompareTo((uint)b[n]);
                if (c != 0)
                    return c;
            }
            return 0;
        }

        static int Align(int n) => (n + 3) & ~3;

        /// <summary>A copy of the table with `added` rows, laid out as the game's tables are: every
        /// row it had kept (its bytes where they were, in a copy of the whole file), the new ones
        /// after, each list the game reads made again in key order. Null and why when the table
        /// can't be read or a new row's keys are taken; (1.36.0) with `replace`, a row at keys taken is
        /// put in place of the one there, whose bytes stay unread in the copy of the file.</summary>
        public static byte[]? WithRows(ReadOnlySpan<byte> table, IList<NewRow> added, out string why, bool replace = false)
        {
            var rows = Rows(table, out why);
            if (rows == null)
                return null;
            int keys = Keys(table);
            // Each row: its keys, and where its bytes will be: the copy of the file (the old ones) or
            // the new rows' part (the new ones).
            var all = new List<(int[] Keys, int Fourth, int Old, int New)>(rows.Count + added.Count);
            var taken = new HashSet<string>();
            foreach (var row in rows)
            {
                all.Add((row.Keys, row.Fourth, row.At, -1));
                taken.Add(string.Join(",", row.Keys));
            }
            for (int n = 0; n < added.Count; n++)
            {
                if (added[n].Keys.Length != keys)
                {
                    why = $"a new row has {added[n].Keys.Length} keys, the table {keys}";
                    return null;
                }
                string key = string.Join(",", added[n].Keys);
                if (!taken.Add(key))
                {
                    if (!replace || all.RemoveAll(r => r.New < 0 && string.Join(",", r.Keys) == key) != 1)
                    {
                        why = $"the table already has a row {string.Join(", ", added[n].Keys)}";
                        return null;
                    }
                }
                all.Add((added[n].Keys, 0, -1, n));
            }
            all.Sort((a, b) => Compare(a.Keys, b.Keys));
            if (keys == 2)
                return TwoKeys(table, all, added);

            int count = all.Count;
            int setsAt = Header, k1 = 0, k2 = 0;
            if (keys == 3)
            {
                for (int n = 0; n < count; n++)
                {
                    if (n == 0 || all[n].Keys[0] != all[n - 1].Keys[0])
                    {
                        k1++;
                        k2++;
                    }
                    else if (all[n].Keys[1] != all[n - 1].Keys[1])
                        k2++;
                }
            }
            int k2At = setsAt + k1 * SetBytes;
            int setRowsAt = k2At + k2 * SetBytes;
            int headsAt = keys == 3 ? setRowsAt + count * ThreeKeyHead : Header;
            int headSize = keys == 3 ? ThreeKeyHead : OneKeyHead;
            int fileAt = Align(headsAt + count * headSize);
            int newAt = Align(fileAt + table.Length);
            var newPlace = new int[added.Count];
            int end = newAt;
            for (int n = 0; n < added.Count; n++)
            {
                newPlace[n] = end;
                end = Align(end + added[n].Bytes.Length);
            }
            var output = new byte[end];
            table.Slice(0, Header).CopyTo(output);
            for (int at = 0x20; at < Header; at++)
                output[at] = 0;
            table.CopyTo(output.AsSpan(fileAt));
            for (int n = 0; n < added.Count; n++)
                added[n].Bytes.CopyTo(output.AsSpan(newPlace[n]));

            int Place(int n) => all[n].Old >= 0 ? fileAt + all[n].Old : newPlace[all[n].New];

            void Head(int at, int n)
            {
                for (int j = 0; j < keys; j++)
                    Put(output, at + 4 * j, all[n].Keys[j]);
                if (keys == 3)
                    Put(output, at + 12, all[n].Fourth);
                Put(output, at + headSize - 4, Place(n) - at);
            }

            for (int n = 0; n < count; n++)
                Head(headsAt + n * headSize, n);
            if (keys == 1)
            {
                Put(output, 0x20, headsAt);
                Put(output, 0x24, count);
                // A table the game finds rows of by their place (byte 10: the key less the first
                // key is the row's place, 0x3D3AE8) is searched by key instead (0) when its keys no
                // longer follow on from one another; its old rows keep their places all the same.
                if (output[10] != 0)
                    for (int n = 1; n < count; n++)
                        if ((long)all[n].Keys[0] != (long)all[0].Keys[0] + n)
                        {
                            output[10] = 0;
                            break;
                        }
                return output;
            }
            // Three keys: the first key's list, each entry pointing at its second keys' list, each of
            // those at its rows' heads (a second copy of them, in order).
            int one = -1, two = -1, setRow = 0;
            for (int n = 0; n < count; n++)
            {
                bool newOne = n == 0 || all[n].Keys[0] != all[n - 1].Keys[0];
                bool newTwo = newOne || all[n].Keys[1] != all[n - 1].Keys[1];
                if (newOne)
                {
                    one++;
                    int entry = setsAt + one * SetBytes;
                    int list = k2At + (two + 1) * SetBytes;
                    Put(output, entry, all[n].Keys[0]);
                    Put(output, entry + 4, list - entry);
                    Put(output, entry + 8, 0);
                    Put(output, entry + 12, list - entry);
                    Put(output, entry + 16, 0);
                }
                if (newTwo)
                {
                    two++;
                    int entry = k2At + two * SetBytes;
                    int list = setRowsAt + setRow * ThreeKeyHead;
                    Put(output, entry, all[n].Keys[1]);
                    Put(output, entry + 4, list - entry);
                    Put(output, entry + 8, 0);
                    Put(output, entry + 12, list - entry);
                    Put(output, entry + 16, 0);
                    int oneEntry = setsAt + one * SetBytes;
                    Put(output, oneEntry + 8, I32(output, oneEntry + 8) + 1);
                }
                int twoEntry = k2At + two * SetBytes;
                Put(output, twoEntry + 16, I32(output, twoEntry + 16) + 1);
                Head(setRowsAt + setRow * ThreeKeyHead, n);
                setRow++;
            }
            Put(output, 0x20, setsAt - 0x20);
            Put(output, 0x24, k1);
            Put(output, 0x28, headsAt);
            Put(output, 0x2C, count);
            return output;
        }

        /// <summary>(1.5.0) A table of two keys with rows added (`all` its rows in their keys' order, each where its
        /// bytes are: the old file's or the new rows'): the header, the first keys' list, the heads in order (each
        /// first key's entry pointing at its own among them, as each is found by its first key then searched for its
        /// second), the old file whole, the new rows after it.</summary>
        static byte[] TwoKeys(ReadOnlySpan<byte> table, List<(int[] Keys, int Fourth, int Old, int New)> all,
                              IList<NewRow> added)
        {
            int count = all.Count, firsts = 0;
            for (int n = 0; n < count; n++)
                if (n == 0 || all[n].Keys[0] != all[n - 1].Keys[0])
                    firsts++;
            int setsAt = TwoKeyHeader;
            int headsAt = setsAt + firsts * TwoKeySet;
            int fileAt = Align(headsAt + count * TwoKeyHead);
            int newAt = Align(fileAt + table.Length);
            var newPlace = new int[added.Count];
            int end = newAt;
            for (int n = 0; n < added.Count; n++)
            {
                newPlace[n] = end;
                end = Align(end + added[n].Bytes.Length);
            }
            var output = new byte[end];
            table.Slice(0, Header).CopyTo(output);
            for (int at = 0x20; at < TwoKeyHeader; at++)
                output[at] = 0;
            table.CopyTo(output.AsSpan(fileAt));
            for (int n = 0; n < added.Count; n++)
                added[n].Bytes.CopyTo(output.AsSpan(newPlace[n]));
            int set = -1;
            for (int n = 0; n < count; n++)
            {
                int head = headsAt + n * TwoKeyHead;
                Put(output, head, all[n].Keys[0]);
                Put(output, head + 4, all[n].Keys[1]);
                int place = all[n].Old >= 0 ? fileAt + all[n].Old : newPlace[all[n].New];
                Put(output, head + 8, place - head);
                if (n == 0 || all[n].Keys[0] != all[n - 1].Keys[0])
                {
                    set++;
                    int entry = setsAt + set * TwoKeySet;
                    Put(output, entry, all[n].Keys[0]);
                    Put(output, entry + 4, head - entry);
                    Put(output, entry + 8, 0);
                }
                int its = setsAt + set * TwoKeySet;
                Put(output, its + 8, I32(output, its + 8) + 1);
            }
            Put(output, 0x20, setsAt - 0x20);
            Put(output, 0x24, firsts);
            Put(output, 0x28, 0);
            Put(output, 0x2C, headsAt);
            Put(output, 0x30, count);
            return output;
        }

        // -------------------------------------------------------------------
        // Reading a table as the game's lookups do, for the checks and for
        // the counts a new row's keys follow.
        // -------------------------------------------------------------------

        /// <summary>A row's bytes' start by its keys, as the game's search finds it; -1 for none.</summary>
        public static int Find(ReadOnlySpan<byte> table, int[] keys)
        {
            int k = Keys(table);
            if (k != keys.Length)
                return -1;
            var (heads, count, size) = HeadsOf(table, k);
            int lo = 0, hi = count;
            var have = new int[k];
            while (lo < hi)
            {
                int mid = (lo + hi) / 2;
                int head = heads + mid * size;
                for (int j = 0; j < k; j++)
                    have[j] = I32(table, head + 4 * j);
                int c = Compare(keys, have);
                if (c == 0)
                    return head + I32(table, head + size - 4);
                if (c < 0)
                    hi = mid;
                else
                    lo = mid + 1;
            }
            return -1;
        }

        static int Entry(ReadOnlySpan<byte> table, int list, int count, int key, int size = SetBytes)
        {
            for (int n = 0; n < count; n++)
                if (I32(table, list + n * size) == key)
                    return list + n * size;
            return -1;
        }

        /// <summary>How many second keys a first key has (the game's 0x3D3A34): (1.5.0) for two keys, how many rows.</summary>
        public static int SecondKeys(ReadOnlySpan<byte> table, int first)
        {
            int k = Keys(table);
            if (k != 3 && k != 2)
                return 0;
            int e = Entry(table, 0x20 + I32(table, 0x20), I32(table, 0x24), first, k == 2 ? TwoKeySet : SetBytes);
            return e < 0 ? 0 : I32(table, e + 8);
        }

        /// <summary>How many rows a first and second key have (the game's 0x3D3A84).</summary>
        public static int ThirdKeys(ReadOnlySpan<byte> table, int first, int second)
        {
            if (Keys(table) != 3)
                return 0;
            int e = Entry(table, 0x20 + I32(table, 0x20), I32(table, 0x24), first);
            if (e < 0)
                return 0;
            int c = Entry(table, e + I32(table, e + 4), I32(table, e + 8), second);
            return c < 0 ? 0 : I32(table, c + 16);
        }
    }
}
