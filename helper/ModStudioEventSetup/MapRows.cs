// Mod Studio Framework: (1.10.0) a quest map's rows in the six tables the
// game keys by a map, read from its map.json and laid out as the game's
// tables hold them. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Each table by the number the program asks for it (nxd/root.nxl's), found by
// the code that reads it in his program of 17 September and held to the
// tables' layouts and WotL Restoration's whole copies of them
// (dev/research/sidequests/README.md, A quest's own maps): Map 0x3C (one key:
// the map), RefinedBgTexture 0x47 (the map, a group, a variant),
// RefinedBgSystemTexture 0x8D (the map, 0, a slot), RefinedBgMeshNode 0x99
// (the map, a block, a slot), RefinedBgAnim 0x31 (the map, a track) and
// RefinedBgMeshPolygon 0xE8 (the map, a row). A row's fixed bytes, then its
// lists (each pointed at from the row's start, its count after), then its
// words: a list of words' entries each a distance from the list's start (the
// game's reads at 0xCA5F0 and 0xCAC33), a lone text (a Comment) a distance
// from the row's start, to an empty one when there is none.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Text;
using System.Text.Json;

namespace ModStudioEventSetup
{
    public static class MapRows
    {
        /// <summary>A column's kind: a 32-bit number, a float, 16 bits, a byte, a text (or none), a list of 32-bit
        /// numbers, a list of texts, Map's list of variants (24 numbers each, 0x48 bytes).</summary>
        public enum Kind { Int, Float, Short, Byte, Text, Ints, Texts, Variants }

        public sealed class Table
        {
            public string Name { get; }
            public int Sheet { get; }
            /// <summary>The keys after the map's: none (Map), "Key2", or "Key2" and "Key3".</summary>
            public string[] Keys { get; }
            /// <summary>Its fixed bytes, and each column's kind and place in them.</summary>
            public int Head { get; }
            public (string Name, Kind Kind, int At)[] Columns { get; }

            public Table(string name, int sheet, string[] keys, int head, (string, Kind, int)[] columns)
            {
                Name = name;
                Sheet = sheet;
                Keys = keys;
                Head = head;
                Columns = columns;
            }
        }

        public const int MapSheet = 0x3C, TextureSheet = 0x47, SystemSheet = 0x8D, NodeSheet = 0x99, AnimSheet = 0x31,
                         PolygonSheet = 0xE8;

        public static readonly Table[] Tables =
        {
            new Table("Map", MapSheet, new string[0], 0x20, new[]
            {
                ("DLCFlags", Kind.Int, 0), ("Comment", Kind.Text, 4), ("Unknown8", Kind.Int, 8),
                ("UnknownC", Kind.Int, 0xC), ("Unknown10", Kind.Int, 0x10), ("Unknown14", Kind.Variants, 0x14),
                ("Unknown1C", Kind.Int, 0x1C),
            }),
            new Table("RefinedBgTexture", TextureSheet, new[] { "Key2", "Key3" }, 0x28, new[]
            {
                ("DLCFlags", Kind.Int, 0), ("Comment", Kind.Text, 4), ("Unknown8", Kind.Texts, 8),
                ("Unknown10", Kind.Ints, 0x10), ("Unknown18", Kind.Texts, 0x18), ("Unknown20", Kind.Ints, 0x20),
            }),
            new Table("RefinedBgSystemTexture", SystemSheet, new[] { "Key2", "Key3" }, 0x18, new[]
            {
                ("DLCFlags", Kind.Int, 0), ("Comment", Kind.Text, 4), ("Unknown8", Kind.Texts, 8),
                ("Unknown10", Kind.Texts, 0x10),
            }),
            new Table("RefinedBgMeshNode", NodeSheet, new[] { "Key2", "Key3" }, 0x1C, new[]
            {
                ("DLCFlags", Kind.Int, 0), ("Comment", Kind.Text, 4), ("Unknown8", Kind.Int, 8),
                ("UnknownC", Kind.Int, 0xC), ("Unknown10", Kind.Int, 0x10), ("Unknown14", Kind.Byte, 0x14),
                ("Unknown15", Kind.Byte, 0x15), ("Unknown16", Kind.Byte, 0x16), ("Unknown17", Kind.Byte, 0x17),
                ("Unknown18", Kind.Byte, 0x18),
            }),
            new Table("RefinedBgAnim", AnimSheet, new[] { "Key2" }, 0xC, new[]
            {
                ("Unknown0", Kind.Int, 0), ("Unknown4", Kind.Int, 4), ("Unknown8", Kind.Int, 8),
            }),
            new Table("RefinedBgMeshPolygon", PolygonSheet, new[] { "Key2" }, 0x18, new[]
            {
                ("DLCFlags", Kind.Int, 0), ("Unknown4", Kind.Int, 4), ("Unknown8", Kind.Int, 8),
                ("UnknownC", Kind.Int, 0xC), ("RefinedBgMeshPolygonCondId", Kind.Int, 0x10), ("Unknown14", Kind.Int, 0x14),
            }),
        };

        /// <summary>A Map variant's 24 numbers, as its 0x48 bytes hold them (the layout's UnknownMapStruct): eight
        /// 32-bit numbers, a float, three, two floats, six of 16 bits, four bytes.</summary>
        public static readonly Kind[] VariantKinds =
        {
            Kind.Int, Kind.Int, Kind.Int, Kind.Int, Kind.Int, Kind.Int, Kind.Int, Kind.Int, Kind.Float, Kind.Int,
            Kind.Int, Kind.Int, Kind.Float, Kind.Float, Kind.Short, Kind.Short, Kind.Short, Kind.Short, Kind.Short,
            Kind.Short, Kind.Byte, Kind.Byte, Kind.Byte, Kind.Byte,
        };
        public const int VariantBytes = 0x48;
        /// <summary>The most a list holds, and a text's most bytes.</summary>
        public const int MostList = 256, MostText = 255;

        public static Table? TableNamed(string name) => Array.Find(Tables, t => t.Name == name);
        public static Table? TableOf(int sheet) => Array.Find(Tables, t => t.Sheet == sheet);

        static string What(Kind kind) => kind switch
        {
            Kind.Int => "a 32-bit number",
            Kind.Float => "a number",
            Kind.Short => "a 16-bit number",
            Kind.Byte => "a byte",
            Kind.Text => "a text or null",
            Kind.Ints => $"a list of up to {MostList} 32-bit numbers",
            Kind.Texts => $"a list of up to {MostList} texts",
            _ => "a list of variants of 24 numbers",
        };

        static bool Whole(JsonElement e, long low, long high, out long value)
        {
            value = 0;
            if (e.ValueKind != JsonValueKind.Number || !e.TryGetInt64(out value))
                return false;
            return value >= low && value <= high;
        }

        static bool Number(JsonElement e, Kind kind, out object? value)
        {
            value = null;
            switch (kind)
            {
                case Kind.Int:
                    if (!Whole(e, int.MinValue, uint.MaxValue, out long i))
                        return false;
                    value = i;
                    return true;
                case Kind.Short:
                    if (!Whole(e, short.MinValue, ushort.MaxValue, out long s))
                        return false;
                    value = s;
                    return true;
                case Kind.Byte:
                    if (!Whole(e, sbyte.MinValue, byte.MaxValue, out long b))
                        return false;
                    value = b;
                    return true;
                case Kind.Float:
                    if (e.ValueKind != JsonValueKind.Number || !e.TryGetDouble(out double d) || double.IsInfinity(d)
                        || double.IsNaN(d))
                        return false;
                    value = d;
                    return true;
            }
            return false;
        }

        static bool TextOf(JsonElement e, out string text)
        {
            text = e.ValueKind == JsonValueKind.String ? e.GetString() ?? "" : "";
            return e.ValueKind == JsonValueKind.String && Encoding.UTF8.GetByteCount(text) <= MostText;
        }

        /// <summary>A column's value as read, or false.</summary>
        static bool Value(JsonElement e, Kind kind, out object? value)
        {
            value = null;
            switch (kind)
            {
                case Kind.Text:
                    if (e.ValueKind == JsonValueKind.Null)
                        return true;
                    if (!TextOf(e, out string text))
                        return false;
                    value = text;
                    return true;
                case Kind.Ints:
                case Kind.Texts:
                {
                    if (e.ValueKind != JsonValueKind.Array || e.GetArrayLength() > MostList)
                        return false;
                    var list = new List<object?>();
                    foreach (var item in e.EnumerateArray())
                    {
                        object? one;
                        if (kind == Kind.Texts)
                        {
                            if (!TextOf(item, out string t))
                                return false;
                            one = t;
                        }
                        else if (!Number(item, Kind.Int, out one))
                            return false;
                        list.Add(one);
                    }
                    value = list;
                    return true;
                }
                case Kind.Variants:
                {
                    if (e.ValueKind != JsonValueKind.Array || e.GetArrayLength() > MostList)
                        return false;
                    var variants = new List<object?>();
                    foreach (var item in e.EnumerateArray())
                    {
                        if (item.ValueKind != JsonValueKind.Array || item.GetArrayLength() != VariantKinds.Length)
                            return false;
                        var numbers = new List<object?>();
                        int n = 0;
                        foreach (var x in item.EnumerateArray())
                        {
                            if (!Number(x, VariantKinds[n++], out object? one))
                                return false;
                            numbers.Add(one);
                        }
                        variants.Add(numbers);
                    }
                    value = variants;
                    return true;
                }
                default:
                    return Number(e, kind, out value);
            }
        }

        /// <summary>One row's keys after the map's and its columns, or null and why in problems (`where` names it).</summary>
        static MapRow? Row(Table table, JsonElement e, string where, List<string> problems)
        {
            if (e.ValueKind != JsonValueKind.Object)
            {
                problems.Add($"{where} isn't a list of fields");
                return null;
            }
            int before = problems.Count;
            var keys = new int[table.Keys.Length];
            var values = new Dictionary<string, object?>(StringComparer.Ordinal);
            var given = new HashSet<string>(StringComparer.Ordinal);
            foreach (var p in e.EnumerateObject())
            {
                if (!given.Add(p.Name))
                {
                    problems.Add($"{where} gives {p.Name} twice");
                    continue;
                }
                if (p.Name == "Key")
                {
                    problems.Add($"{where} gives Key: the map's number is the helper's to give");
                    continue;
                }
                int key = Array.IndexOf(table.Keys, p.Name);
                if (key >= 0)
                {
                    if (!Whole(p.Value, 0, int.MaxValue, out long k))
                        problems.Add($"{where}'s {p.Name} isn't 0 to {int.MaxValue}");
                    else
                        keys[key] = (int)k;
                    continue;
                }
                int column = Array.FindIndex(table.Columns, c => c.Name == p.Name);
                if (column < 0)
                {
                    problems.Add($"{where} has no column {p.Name}");
                    continue;
                }
                var kind = table.Columns[column].Kind;
                if (!Value(p.Value, kind, out object? value))
                    problems.Add($"{where}'s {p.Name} isn't {What(kind)}");
                else
                    values[p.Name] = value;
            }
            foreach (var name in table.Keys)
                if (!given.Contains(name))
                    problems.Add($"{where} gives no {name}");
            return problems.Count > before ? null : new MapRow(keys, values);
        }

        /// <summary>A map.json's Rows into `rows` (by table), what is wrong in problems: Map one row, the others each
        /// a list of rows, none two at the same keys.</summary>
        public static void Read(JsonElement r, Dictionary<string, List<MapRow>> rows, List<string> problems)
        {
            foreach (var p in r.EnumerateObject())
            {
                var table = TableNamed(p.Name);
                if (table == null)
                {
                    problems.Add($"its Rows have no table {p.Name}");
                    continue;
                }
                if (rows.ContainsKey(table.Name))
                {
                    problems.Add($"its Rows give {table.Name} twice");
                    continue;
                }
                var list = new List<MapRow>();
                rows[table.Name] = list;
                if (table.Keys.Length == 0)
                {
                    var row = Row(table, p.Value, $"its Rows' {table.Name}", problems);
                    if (row != null)
                        list.Add(row);
                    continue;
                }
                if (p.Value.ValueKind != JsonValueKind.Array)
                {
                    problems.Add($"its Rows' {table.Name} isn't a list of rows");
                    continue;
                }
                var seen = new HashSet<string>(StringComparer.Ordinal);
                int n = 0;
                foreach (var e in p.Value.EnumerateArray())
                {
                    n++;
                    var row = Row(table, e, $"its Rows' {table.Name} row {n}", problems);
                    if (row == null)
                        continue;
                    string keys = string.Join(", ", row.Keys);
                    if (!seen.Add(keys))
                        problems.Add($"its Rows' {table.Name} has two rows at {keys}");
                    else
                        list.Add(row);
                }
            }
            if (!rows.TryGetValue("Map", out var map) || map.Count == 0)
                problems.Add("its Rows have no Map row");
        }

        // --- laid out as the game's -----------------------------------------------------------------------------------

        static void Put(List<byte> bytes, int at, Kind kind, object? value)
        {
            Span<byte> b = stackalloc byte[4];
            switch (kind)
            {
                case Kind.Int:
                    BinaryPrimitives.WriteUInt32LittleEndian(b, unchecked((uint)(long)(value ?? 0L)));
                    for (int k = 0; k < 4; k++)
                        bytes[at + k] = b[k];
                    break;
                case Kind.Float:
                    BinaryPrimitives.WriteSingleLittleEndian(b, (float)(double)(value ?? 0.0));
                    for (int k = 0; k < 4; k++)
                        bytes[at + k] = b[k];
                    break;
                case Kind.Short:
                {
                    ushort s = unchecked((ushort)(long)(value ?? 0L));
                    bytes[at] = (byte)s;
                    bytes[at + 1] = (byte)(s >> 8);
                    break;
                }
                case Kind.Byte:
                    bytes[at] = unchecked((byte)(long)(value ?? 0L));
                    break;
            }
        }

        static void PutInt(List<byte> bytes, int at, int value) => Put(bytes, at, Kind.Int, (long)value);

        static int VariantAt(int n)
        {
            int at = 0;
            for (int k = 0; k < n; k++)
                at += VariantKinds[k] switch { Kind.Short => 2, Kind.Byte => 1, _ => 4 };
            return at;
        }

        /// <summary>A row's bytes as the game's tables hold them: its fixed bytes; then each list in its columns'
        /// order (pointed at from the row's start, its count after); then the texts, each ending in a zero: a list's
        /// entries each a distance from the list's start, a lone text a distance from the row's start; an empty text
        /// (a Comment not given) pointing at the zeros the row ends with.</summary>
        public static byte[] Bytes(Table table, MapRow row)
        {
            var bytes = new List<byte>(new byte[table.Head]);
            var texts = new List<(int At, int From, string Text)>();
            var empty = new List<(int At, int From)>();
            foreach (var (name, kind, at) in table.Columns)
            {
                row.Values.TryGetValue(name, out object? value);
                switch (kind)
                {
                    case Kind.Text:
                        if (value is string text && text.Length > 0)
                            texts.Add((at, 0, text));
                        else
                            empty.Add((at, 0));
                        break;
                    case Kind.Ints:
                    case Kind.Texts:
                    case Kind.Variants:
                    {
                        var list = value as List<object?> ?? new List<object?>();
                        int start = bytes.Count;
                        PutInt(bytes, at, start);
                        PutInt(bytes, at + 4, list.Count);
                        int size = kind == Kind.Variants ? VariantBytes : 4;
                        bytes.AddRange(new byte[size * list.Count]);
                        for (int n = 0; n < list.Count; n++)
                        {
                            int entry = start + size * n;
                            if (kind == Kind.Ints)
                                Put(bytes, entry, Kind.Int, list[n]);
                            else if (kind == Kind.Texts)
                            {
                                string t = list[n] as string ?? "";
                                if (t.Length > 0)
                                    texts.Add((entry, start, t));
                                else
                                    empty.Add((entry, start));
                            }
                            else
                            {
                                var numbers = (List<object?>)list[n]!;
                                for (int k = 0; k < VariantKinds.Length; k++)
                                    Put(bytes, entry + VariantAt(k), VariantKinds[k], numbers[k]);
                            }
                        }
                        break;
                    }
                    default:
                        Put(bytes, at, kind, value);
                        break;
                }
            }
            foreach (var (at, from, text) in texts)
            {
                PutInt(bytes, at, bytes.Count - from);
                bytes.AddRange(Encoding.UTF8.GetBytes(text));
                bytes.Add(0);
            }
            while (bytes.Count % 4 != 0)
                bytes.Add(0);
            int zero = bytes.Count;
            bytes.AddRange(new byte[4]);
            foreach (var (at, from) in empty)
                PutInt(bytes, at, zero - from);
            return bytes.ToArray();
        }

        /// <summary>The rows a table gets for the quest maps given numbers (each map's at its number, then its keys).</summary>
        public static List<NewRow> RowsFor(Table table, IEnumerable<(int Number, QuestMap Map)> maps)
        {
            var rows = new List<NewRow>();
            foreach (var (number, map) in maps)
            {
                if (!map.Rows.TryGetValue(table.Name, out var list))
                    continue;
                foreach (var row in list)
                {
                    var keys = new int[1 + row.Keys.Length];
                    keys[0] = number;
                    row.Keys.CopyTo(keys, 1);
                    rows.Add(new NewRow(keys, Bytes(table, row)));
                }
            }
            return rows;
        }
    }
}
