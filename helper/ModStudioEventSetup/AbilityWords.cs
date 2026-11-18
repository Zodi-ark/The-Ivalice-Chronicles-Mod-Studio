// A mod's own action abilities: their words, and their cost to learn (the road's step 4; Zodi's answer of 10 November
// 2026: "Straight to more"). The build's sixth step. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// (1.41.0) Part of the helper since new abilities moved in for test 94 (built beside it until the whole rehearsed).
//
// Two things give an ability its words, and the first gives its cost too.
//
// - The game's Ability table (sheet 0x27: 512 rows, a row's place its number). The remaster's screens read an
//   ability's name and description there, and the game's own code reads its cost to learn there (0x2CC0AC: the word at
//   a row's + 0x40, 0xFFFF where there is no row). So a mod's ability gets a row: the row of the game's ability it is
//   like (how that one is shown: its icon, the marks of its help) with its own name, description and cost. Past the
//   game's last number the rows go on without a gap, as the Job table's do: a number between that no ability has gets
//   a row with no name. A line break in a description is written "<br>", as the game's own rows write one.
//
// - The older text routine (0x226208 and its twin 0x2DDBC8). A text code is a tag and an index of eleven bits; for an
//   ability's name (the tag 0x7000) the routine walks a file the game loads whole, counting each byte of 0xFE or more
//   until it has counted the index, and nothing bounds the walk. About forty places make that code from an ability's
//   number. So the file is made longer where the game loads it (AbilityRoom's two changes of the loader ask for
//   NamesExtra bytes more and tell the framework when the file is read): `Longer` writes an entry for every index the
//   file hasn't, to 2047, after the file's bytes. A mod's ability's entry is the bytes of the game's ability it is
//   like, any other is empty: the entry is there so that no walk leaves the file (the names a player reads are the
//   table's).
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Text;

namespace ModStudioEventSetup
{
    public static class AbilityWords
    {
        // --- the Ability table -----------------------------------------------------------------------------------------

        /// <summary>The Ability table's sheet, a row's fixed part, and its fields' places: its name, description and
        /// third word (from the row + 8), its comment (from the row), where its list of numbers is and how many, its
        /// cost to learn (a word).</summary>
        public const int Sheet = 0x27, RowBytes = 0x44, RowWordsFrom = 8, NameAt = 8, DescriptionAt = 0xC, ThirdAt = 0x10,
                         CommentAt = 0x1C, ListAt = 0x24, ListCountAt = 0x28, CostAt = 0x40;
        /// <summary>(1.55.1) Where a row's icon is (the IconId column: a word; 0 none).</summary>
        public const int IconAt = 4;
        /// <summary>The most numbers a row's list is taken to hold (the game's rows hold 0 to 3).</summary>
        public const int ListMost = 16;
        /// <summary>The game's ability whose row a number with no ability gets (the game's "none").</summary>
        public const int BlankLike = 0;

        static int I32(ReadOnlySpan<byte> b, int at) => BinaryPrimitives.ReadInt32LittleEndian(b.Slice(at, 4));

        /// <summary>How long a row of the table is with its list (the list right after the fixed part, as every row of
        /// the game's has it), or 0 where the row at `at` isn't laid out so.</summary>
        public static int RowLength(ReadOnlySpan<byte> table, int at)
        {
            if (at < 0 || at + RowBytes > table.Length)
                return 0;
            int count = I32(table, at + ListCountAt);
            if (count < 0 || count > ListMost || I32(table, at + ListAt) != RowBytes || at + RowBytes + 4 * count > table.Length)
                return 0;
            return RowBytes + 4 * count;
        }

        /// <summary>A row: the fixed part and the list of the row it is like, its own name, description and cost, the
        /// words after the list with an empty word the others point at.</summary>
        public static byte[] Row(ReadOnlySpan<byte> likeRow, string name, string description, int cost)
        {
            byte[] n = Encoding.UTF8.GetBytes(name), d = Encoding.UTF8.GetBytes(description.Replace("\n", "<br>"));
            int empty = likeRow.Length, nameAt = empty + 1, descriptionAt = nameAt + n.Length + 1;
            var row = new byte[(descriptionAt + d.Length + 1 + 3) & ~3];
            likeRow.CopyTo(row);
            void Put(int at, int value) => BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(at), value);
            Put(NameAt, nameAt - RowWordsFrom);
            Put(DescriptionAt, descriptionAt - RowWordsFrom);
            Put(ThirdAt, empty - RowWordsFrom);
            Put(CommentAt, empty);
            BinaryPrimitives.WriteUInt16LittleEndian(row.AsSpan(CostAt), (ushort)cost);
            n.CopyTo(row, nameAt);
            d.CopyTo(row, descriptionAt);
            return row;
        }

        /// <summary>A row with no name, for a number past the game's last that no ability has now: the fixed part of
        /// the game's "none", every word the empty one, no list.</summary>
        public static byte[] BlankRow(ReadOnlySpan<byte> noneRow)
        {
            int empty = RowBytes;
            var row = new byte[(empty + 1 + 3) & ~3];
            noneRow.Slice(0, RowBytes).CopyTo(row);
            void Put(int at, int value) => BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(at), value);
            Put(NameAt, empty - RowWordsFrom);
            Put(DescriptionAt, empty - RowWordsFrom);
            Put(ThirdAt, empty - RowWordsFrom);
            Put(CommentAt, empty);
            Put(ListAt, RowBytes);
            Put(ListCountAt, 0);
            return row;
        }

        /// <summary>An ability's cost to learn, as its record has it (its first two bytes).</summary>
        public static int Cost(ModAbility ability) => ability.Record[0] | ability.Record[1] << 8;

        /// <summary>The loaded Ability table (its loaded language's) with a row for each ability given and, from the
        /// game's last number to the last given, a row with no name for each number that has none (the last given too,
        /// where its own row couldn't be made: the game reads a row with no test for there being none); or null and
        /// why.</summary>
        public static byte[]? WithRows(ReadOnlySpan<byte> table, IList<AbilityFile.Given> given, List<string> said, out string why)
        {
            why = "";
            if (Nxd.Keys(table) != 1)
            {
                why = "it isn't a table of one key";
                return null;
            }
            var rows = new List<NewRow>();
            var have = new HashSet<int>();
            int last = -1;
            foreach (var g in given)
            {
                last = Math.Max(last, g.Number);
                int at = Nxd.Find(table, new[] { g.Ability.Like });
                int length = RowLength(table, at);
                if (length == 0)
                {
                    said.Add($"{g.Ability.Who} has no name and can't be learned: the table has no row as the game's for "
                             + $"ability {g.Ability.Like}.");
                    continue;
                }
                have.Add(g.Number);
                rows.Add(new NewRow(new[] { g.Number },
                                    Row(table.Slice(at, length), g.Ability.WordName, g.Ability.Description, Cost(g.Ability))));
            }
            int none = Nxd.Find(table, new[] { BlankLike });
            if (none >= 0 && none + RowBytes <= table.Length)
                for (int n = AbilityRecords.GameCount; n <= last; n++)
                    if (!have.Contains(n) && Nxd.Find(table, new[] { n }) < 0)
                        rows.Add(new NewRow(new[] { n }, BlankRow(table.Slice(none, RowBytes))));
            return Nxd.WithRows(table, rows, out why, replace: true);
        }

        /// <summary>(1.55.0) The loaded Ability table with the names of the game's own Dark Knight's abilities, where a mod
        /// gives that job (Zodi's word of 15 November: "What ever War of the Lions does we should do"): for each, the name
        /// and description its job's file gives (JobFile's Names), else War of the Lions' name and (1.55.1) description
        /// (DarkKnightAbilities.Names). A row of one the game leaves without a name is its own with them (its list and cost
        /// as they are); a row the game (or another mod) names is kept, and said where the file names it. Sanguine Sword
        /// (45, the game's copy of Chant), where `sanguine` (DarkKnightAbilities made it War of the Lions'): its row made
        /// like Infernal Strike's (no voice) with its name, description and War of the Lions' cost, where it is still the
        /// game's copy of Chant's (its words Chant's: else another mod's, kept). (1.55.1, Zodi's test 122) Each row written
        /// is given the icon of the game's ability most like it (DarkKnightAbilities.Icons): with none, the game shows no
        /// name. Null and why where the table can't be given them; `named` how many.</summary>
        public static byte[]? WithGameNames(ReadOnlySpan<byte> table, IEnumerable<JobRoom.Given> given, bool sanguine,
                                            List<string> said, out string why, out int named)
        {
            why = "";
            named = 0;
            if (Nxd.Keys(table) != 1)
            {
                why = "it isn't a table of one key";
                return null;
            }
            var rows = new List<NewRow>();
            foreach (var g in given)
            {
                if (g.Job.Game != JobFile.DarkKnight)
                    continue;
                var names = new List<AbilityName>(g.Job.AbilityNames);
                foreach (var (ability, name, description) in DarkKnightAbilities.Names)
                    if (!names.Exists(n => n.Ability == ability))
                        names.Add(new AbilityName(ability, name, description));
                foreach (var name in names)
                {
                    bool fromFile = Array.Exists(g.Job.AbilityNames, n => n.Ability == name.Ability);
                    string whose = $"{g.Job.Who}'s name for ability {name.Ability}";
                    int at = Nxd.Find(table, new[] { name.Ability });
                    int length = RowLength(table, at);
                    if (length == 0)
                    {
                        if (fromFile)
                            said.Add($"{whose} is left out: the table has no row as the game's for it.");
                        continue;
                    }
                    if (name.Ability == DarkKnightAbilities.Sanguine)
                    {
                        int chant = Nxd.Find(table, new[] { DarkKnightAbilities.Chant });
                        int like = Nxd.Find(table, new[] { DarkKnightAbilities.RowLike });
                        int likeLength = RowLength(table, like);
                        if (!sanguine)
                        {
                            if (fromFile)
                                said.Add($"{whose} is left out: ability 45 stays the game's copy of Chant.");
                        }
                        else if (RowLength(table, chant) == 0 || Words(table, at, NameAt) != Words(table, chant, NameAt)
                                 || Words(table, at, DescriptionAt) != Words(table, chant, DescriptionAt) || likeLength == 0)
                            said.Add($"{whose} is left out: another mod names that ability.");
                        else
                            rows.Add(new NewRow(new[] { name.Ability }, WithIcon(table, Row(table.Slice(like, likeLength), name.Name,
                                                                                    name.Description, DarkKnightAbilities.Cost),
                                                                         name.Ability)));
                        continue;
                    }
                    long word = (long)at + RowWordsFrom + I32(table, at + NameAt);
                    if (word < 0 || word >= table.Length || table[(int)word] != 0)
                    {
                        if (fromFile)
                            said.Add($"{whose} is left out: the game names that ability already.");
                        continue;
                    }
                    int cost = BinaryPrimitives.ReadUInt16LittleEndian(table.Slice(at + CostAt, 2));
                    rows.Add(new NewRow(new[] { name.Ability },
                                        WithIcon(table, Row(table.Slice(at, length), name.Name, name.Description, cost), name.Ability)));
                }
            }
            named = rows.Count;
            if (rows.Count == 0)
                return table.ToArray();
            return Nxd.WithRows(table, rows, out why, replace: true);
        }

        /// <summary>(1.55.1) A row made for one of the game's Dark Knight's abilities, given the icon (its word at + 4, the
        /// table's IconId) of the game's ability most like it (DarkKnightAbilities.IconLike), as the loaded table has that
        /// one's: as it was where there is none to take.</summary>
        static byte[] WithIcon(ReadOnlySpan<byte> table, byte[] row, int ability)
        {
            int like = Nxd.Find(table, new[] { DarkKnightAbilities.IconLike(ability) });
            if (DarkKnightAbilities.IconLike(ability) >= 0 && like >= 0 && like + RowBytes <= table.Length)
                BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(IconAt), I32(table, like + IconAt));
            return row;
        }

        /// <summary>(1.55.0) A row's word (its name, or its description) as text: "" where it can't be read.</summary>
        static string Words(ReadOnlySpan<byte> table, int at, int field)
        {
            if (at < 0 || at + field + 4 > table.Length)
                return "";
            long start = (long)at + RowWordsFrom + I32(table, at + field);
            if (start < 0 || start >= table.Length)
                return "";
            int end = table.Slice((int)start).IndexOf((byte)0);
            return end < 0 ? "" : Encoding.UTF8.GetString(table.Slice((int)start, end));
        }

        /// <summary>(1.55.0) The table's line, once the game's Dark Knight's abilities' names are written.</summary>
        public static string GameNamesLine(int named)
            => $"Ability: the names of {named} of the game's Dark Knight's abilities written (the job's file's, else War of "
               + "the Lions').";

        // --- the names' file of the older text -------------------------------------------------------------------------

        /// <summary>The names' file among the files the older text routine loads; how many bytes more its room is
        /// asked for with; how many indexes a text code can hold (eleven bits).</summary>
        public const int NamesFile = 8, NamesExtra = 0x10000, NamesIndexes = 2048;
        /// <summary>A byte of this or more ends an entry of the file.</summary>
        public const byte EntryEnd = 0xFE;

        /// <summary>The names' file made longer in place. `blob` is the file's room: its first `size` bytes are the
        /// file as the game read it, the rest is the framework's to write. An entry is written for every index the file
        /// hasn't, to 2047 (a last entry of the file that has no end is given one first): a mod's ability's is the
        /// bytes of the entry of the game's ability it is like, any other is empty. Where the room can't hold a name,
        /// the entry is empty and that is said; where it can't hold an end for every index, nothing is written and
        /// that is said. Gives where the last entry written ends (`size` when nothing was written).</summary>
        public static int Longer(Span<byte> blob, int size, IList<AbilityFile.Given> given, List<string> said)
        {
            if (size < 0 || size > blob.Length)
                return size;
            // Where each entry of the file starts: entry 0 at the file's start, each next one after a byte that ends one.
            var starts = new List<int> { 0 };
            for (int n = 0; n < size; n++)
                if (blob[n] >= EntryEnd)
                    starts.Add(n + 1);
            int whole = starts.Count - 1;                          // entries of the file that have their end
            bool tail = starts[whole] < size;                      // the file's last entry has none
            int first = tail ? whole + 1 : whole;                  // the first index the file has no entry for
            int ends = (tail ? 1 : 0) + Math.Max(0, NamesIndexes - first);
            if (ends > blob.Length - size)
            {
                said.Add($"the older text's names stop at {whole - 1}: its room is {blob.Length - size} bytes.");
                return size;
            }
            int at = size;
            if (tail)
                blob[at++] = EntryEnd;
            var like = new Dictionary<int, int>();
            foreach (var g in given)
                like[g.Number] = g.Ability.Like;
            int empty = 0;
            for (int index = first; index < NamesIndexes; index++)
            {
                // One byte is kept for the end of this entry and of each still to come.
                int room = blob.Length - at - (NamesIndexes - index);
                if (like.TryGetValue(index, out int from) && from < whole)
                {
                    int length = starts[from + 1] - 1 - starts[from];
                    if (length <= room)
                    {
                        blob.Slice(starts[from], length).CopyTo(blob.Slice(at));
                        at += length;
                    }
                    else
                        empty++;
                }
                blob[at++] = EntryEnd;
            }
            if (empty > 0)
                said.Add($"{empty} of the mods' abilities' names are empty in the older text: its room is {blob.Length - size} bytes.");
            return at;
        }
    }
}
