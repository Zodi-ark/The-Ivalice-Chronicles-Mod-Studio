// Mod Studio Event Setup: finding the game's event setup table and changing
// its records. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Everything here works on the game's program as it lies in memory (each
// section at its own address from where the program is loaded), so the
// same code runs in the game and, over a copy laid out the same way, in
// Mod Studio's checks. Written from the game's own data (the records, as
// mod_studio/event_setup.py describes them) and WotL Restoration's pattern;
// nothing of the mod loader's.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    /// <summary>One field of a record: its name in a mod's file, its byte, how
    /// many bytes (little endian), and for part of a byte, its bits.</summary>
    public sealed class Field
    {
        public string Key { get; }
        public int At { get; }
        public int Size { get; }
        public int Mask { get; }

        public Field(string key, int at, int size = 1, int mask = 0)
        {
            Key = key;
            At = at;
            Size = size;
            Mask = mask;
        }

        public int Shift => Mask == 0 ? 0 : System.Numerics.BitOperations.TrailingZeroCount(Mask);

        /// <summary>The highest value it holds.</summary>
        public int Most => Mask != 0 ? Mask >> Shift : (1 << (8 * Size)) - 1;

        public int Read(ReadOnlySpan<byte> record)
        {
            int whole = Size == 2 ? BinaryPrimitives.ReadUInt16LittleEndian(record.Slice(At, 2)) : record[At];
            return Mask != 0 ? (whole & Mask) >> Shift : whole;
        }

        public void Write(Span<byte> record, int value)
        {
            if (value < 0 || value > Most)
                throw new ArgumentOutOfRangeException(nameof(value), $"{Key} holds 0 to {Most}, not {value}");
            if (Mask != 0)
                record[At] = (byte)((record[At] & ~Mask & 0xFF) | (value << Shift));
            else if (Size == 2)
                BinaryPrimitives.WriteUInt16LittleEndian(record.Slice(At, 2), (ushort)value);
            else
                record[At] = (byte)value;
        }
    }

    public static class Fields
    {
        /// <summary>The fields, as Mod Studio's event_setup.FIELDS names them.</summary>
        public static readonly Field[] All =
        {
            new Field("Map", 2),
            new Field("Weather", 3, mask: 0x0F),
            new Field("Arrangement", 3, mask: 0xF0),
            new Field("Night", 4),
            new Field("Music1", 5),
            new Field("Music2", 6),
            new Field("EnemyBattle", 7, 2),
            new Field("DeployArea1", 9, 2),
            new Field("DeployArea2", 11, 2),
            new Field("Portrait", 13),
            new Field("PortraitUnit", 14),
            new Field("SceneUnits", 15, 2),
            new Field("RamzaRequired", 17),
            new Field("NextEvent", 18, 2),
            new Field("AfterEvent", 20),
            new Field("BattleRules", 22),
        };

        /// <summary>A field by its name, without case; null for none.</summary>
        public static Field? Find(string key)
        {
            foreach (var field in All)
                if (string.Equals(field.Key, key, StringComparison.OrdinalIgnoreCase))
                    return field;
            return null;
        }
    }

    /// <summary>A section of the program as loaded: its address from where the
    /// program is loaded, its size there, and whether it is code.</summary>
    public readonly struct Section
    {
        public string Name { get; }
        public int Address { get; }
        public int Size { get; }
        public bool Code { get; }

        public Section(string name, int address, int size, bool code)
        {
            Name = name;
            Address = address;
            Size = size;
            Code = code;
        }
    }

    /// <summary>The table as found: where it is from where the program is
    /// loaded, how it was found, how many slots it has, and each event's slot.</summary>
    public sealed class Table
    {
        public const int RecordBytes = 24;
        /// <summary>The slots the game's table has (as many as its EventId table has rows); read
        /// as far as its records go rather than assumed, up to MostSlots, should an update give
        /// it more or fewer.</summary>
        public const int GameSlots = 887;
        public const int MostSlots = 2048;

        public int Address { get; }
        public string How { get; }
        public int Slots { get; }
        public Dictionary<int, int> SlotOf { get; }

        public int Bytes => Slots * RecordBytes;

        public Table(int address, string how, int slots, Dictionary<int, int> slotOf)
        {
            Address = address;
            How = how;
            Slots = slots;
            SlotOf = slotOf;
        }
    }

    public static class Finder
    {
        /// <summary>The least a table holds: the PlayStation's scenarios.</summary>
        public const int LeastRecords = 480;
        /// <summary>The lea's length: the table is at its end plus the four bytes it holds.</summary>
        const int LeaBytes = 7;
        /// <summary>WotL Restoration's pattern: lea rbx, [rip + x]; mov edx, r12d; mov ebp, 0x27
        /// (-1: any byte, the x).</summary>
        static readonly int[] Pattern = { 0x48, 0x8D, 0x1D, -1, -1, -1, -1, 0x41, 0x8B, 0xD4, 0xBD, 0x27, 0x00, 0x00, 0x00 };

        /// <summary>The program's sections, from its headers at the image's start.</summary>
        public static List<Section> Sections(ReadOnlySpan<byte> image)
        {
            if (image.Length < 0x40 || image[0] != (byte)'M' || image[1] != (byte)'Z')
                throw new InvalidOperationException("it isn't a Windows program");
            int pe = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(0x3C, 4));
            if (pe < 0 || pe + 24 > image.Length || image[pe] != (byte)'P' || image[pe + 1] != (byte)'E'
                || image[pe + 2] != 0 || image[pe + 3] != 0)
                throw new InvalidOperationException("it isn't a Windows program");
            int count = BinaryPrimitives.ReadUInt16LittleEndian(image.Slice(pe + 6, 2));
            int optionalSize = BinaryPrimitives.ReadUInt16LittleEndian(image.Slice(pe + 20, 2));
            int first = pe + 24 + optionalSize;
            var sections = new List<Section>();
            for (int n = 0; n < count; n++)
            {
                int at = first + 40 * n;
                if (at + 40 > image.Length)
                    throw new InvalidOperationException("its section table is cut short");
                var name = System.Text.Encoding.ASCII.GetString(image.Slice(at, 8)).TrimEnd('\0');
                int size = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at + 8, 4));
                int address = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at + 12, 4));
                uint characteristics = BinaryPrimitives.ReadUInt32LittleEndian(image.Slice(at + 36, 4));
                bool code = (characteristics & 0x20000000) != 0;
                int within = Math.Max(0, Math.Min(size, image.Length - address));
                sections.Add(new Section(name, address, within, code));
            }
            return sections;
        }

        /// <summary>Why a slot's 24 bytes aren't laid out as the game's setup records are, or ""
        /// when they are: bytes 21 and 23 zero, what follows (20) one of 0, 0x80, 0x81 and 0x82,
        /// night (4) and Ramza required (17) 0 or 1, as in every one of the game's 713
        /// (event_setup.record_problem). A game update that laid them out otherwise fails it, so
        /// no mod's change goes into the wrong byte.</summary>
        public static string RecordProblem(ReadOnlySpan<byte> record)
        {
            if (record[21] != 0)
                return $"byte 21 is {record[21]}, not 0";
            if (record[23] != 0)
                return $"byte 23 is {record[23]}, not 0";
            if (record[20] != 0 && (record[20] < 0x80 || record[20] > 0x82))
                return $"byte 20, what follows, is {record[20]}";
            if (record[4] > 1)
                return $"byte 4, night, is {record[4]}";
            if (record[17] > 1)
                return $"byte 17, Ramza required, is {record[17]}";
            return "";
        }

        /// <summary>Why the slots from `at` don't look like the setup table, or "" when they do,
        /// and how many slots it has: read until a slot that is neither empty (all zero) nor a
        /// record laid out as the game's with a higher event than the one before (MostSlots at
        /// the most); events 1 and 2 first, at least the PlayStation's 480 records
        /// (event_setup.scan_table).</summary>
        public static string Scan(ReadOnlySpan<byte> image, int at, out int slots)
        {
            int previous = 0, records = 0;
            string stop = "";
            slots = 0;
            while (slots < Table.MostSlots && at + (slots + 1) * Table.RecordBytes <= image.Length)
            {
                var record = image.Slice(at + slots * Table.RecordBytes, Table.RecordBytes);
                if (record.IndexOfAnyExcept((byte)0) >= 0)
                {
                    int ev = BinaryPrimitives.ReadUInt16LittleEndian(record);
                    if (slots < 2 && ev != slots + 1)
                        return $"its slot {slots} holds event {ev}, not {slots + 1}";
                    string wrong = RecordProblem(record);
                    if (wrong.Length > 0 || ev <= previous)
                    {
                        stop = wrong.Length > 0 ? $"slot {slots}, whose {wrong}"
                            : $"slot {slots}, whose event {ev} comes after event {previous}";
                        break;
                    }
                    previous = ev;
                    records++;
                }
                else if (slots < 2)
                    return $"its slot {slots} is empty";
                slots++;
            }
            if (records < LeastRecords)
                return $"it has {records} records" + (stop.Length > 0 ? $" before {stop}" : "")
                    + $", fewer than the PlayStation's {LeastRecords}";
            return "";
        }

        static bool PatternAt(ReadOnlySpan<byte> bytes, int at)
        {
            for (int k = 0; k < Pattern.Length; k++)
                if (Pattern[k] >= 0 && bytes[at + k] != Pattern[k])
                    return false;
            return true;
        }

        /// <summary>Where WotL Restoration's pattern points, if it is in the code once and points
        /// at slots that look like the table; -1 and why not otherwise.</summary>
        public static int ByPattern(ReadOnlySpan<byte> image, List<Section> sections, out string why)
        {
            int hits = 0, target = -1;
            foreach (var section in sections)
            {
                if (!section.Code)
                    continue;
                var code = image.Slice(section.Address, section.Size);
                for (int at = code.IndexOf((byte)0x48); at >= 0 && at + Pattern.Length <= code.Length;)
                {
                    if (PatternAt(code, at))
                    {
                        hits++;
                        int x = BinaryPrimitives.ReadInt32LittleEndian(code.Slice(at + 3, 4));
                        target = section.Address + at + LeaBytes + x;
                    }
                    int next = code.Slice(at + 1).IndexOf((byte)0x48);
                    at = next < 0 ? -1 : at + 1 + next;
                }
            }
            if (hits != 1)
            {
                why = $"WotL Restoration's pattern is in it {hits} times, not once";
                return -1;
            }
            if (target < 0 || target + 2 * Table.RecordBytes > image.Length)
            {
                why = "WotL Restoration's pattern points outside the program";
                return -1;
            }
            string problem = Scan(image, target, out _);
            if (problem.Length > 0)
            {
                why = $"where WotL Restoration's pattern points, {problem}";
                return -1;
            }
            why = "";
            return target;
        }

        /// <summary>The one run of events 1, 2 and 3 outside the code that looks like the table;
        /// -1 and why not otherwise.</summary>
        public static int ByRecords(ReadOnlySpan<byte> image, List<Section> sections, out string why)
        {
            int good = 0, found = -1;
            foreach (var section in sections)
            {
                if (section.Code)
                    continue;
                int end = section.Address + section.Size;
                for (int at = section.Address; at + 2 * Table.RecordBytes + 2 <= end; at++)
                {
                    if (image[at] != 1 || image[at + 1] != 0 || image[at + 24] != 2 || image[at + 25] != 0
                        || image[at + 48] != 3 || image[at + 49] != 0)
                        continue;
                    if (Scan(image, at, out _).Length == 0)
                    {
                        good++;
                        found = at;
                    }
                }
            }
            if (good != 1)
            {
                why = $"the records' own bytes are in it {good} times, not once";
                return -1;
            }
            why = "";
            return found;
        }

        /// <summary>The table, by the pattern, else by the records' own bytes; null and why not.</summary>
        public static Table? Find(ReadOnlySpan<byte> image, out string why)
        {
            List<Section> sections;
            try
            {
                sections = Sections(image);
            }
            catch (InvalidOperationException e)
            {
                why = e.Message;
                return null;
            }
            string how = "WotL Restoration's pattern";
            int at = ByPattern(image, sections, out string whyPattern);
            if (at < 0)
            {
                how = "the records' own bytes";
                at = ByRecords(image, sections, out string whyRecords);
                if (at < 0)
                {
                    why = $"{whyPattern}, and {whyRecords}";
                    return null;
                }
            }
            Scan(image, at, out int slots);
            var slotOf = new Dictionary<int, int>();
            for (int slot = 0; slot < slots; slot++)
            {
                var record = image.Slice(at + slot * Table.RecordBytes, Table.RecordBytes);
                if (record.IndexOfAnyExcept((byte)0) >= 0)
                    slotOf[BinaryPrimitives.ReadUInt16LittleEndian(record)] = slot;
            }
            why = "";
            return new Table(at, how, slots, slotOf);
        }
    }

    /// <summary>Applies mods' changes to the table, the later mod winning a field two mods
    /// change, and says what it did.</summary>
    public sealed class Applier
    {
        readonly Dictionary<(int, string), string> _setBy = new Dictionary<(int, string), string>();

        /// <summary>One mod's changes, in order, onto the table's bytes; returns a line for each
        /// change made or skipped.</summary>
        public List<string> Apply(Span<byte> table, Table found, string mod, IEnumerable<Change> changes)
        {
            var said = new List<string>();
            foreach (var change in changes)
            {
                if (!found.SlotOf.TryGetValue(change.Event, out int slot))
                {
                    said.Add($"{mod}: event {change.Event} has no setup record in the game, so its {change.Field.Key} is left out");
                    continue;
                }
                var record = table.Slice(slot * Table.RecordBytes, Table.RecordBytes);
                int was = change.Field.Read(record);
                change.Field.Write(record, change.Value);
                var key = (change.Event, change.Field.Key);
                string over = _setBy.TryGetValue(key, out string? earlier) && earlier != mod
                    ? $" (over {earlier}'s)" : "";
                _setBy[key] = mod;
                said.Add($"{mod}: event {change.Event}'s {change.Field.Key} {was} to {change.Value}{over}");
            }
            return said;
        }
    }

    /// <summary>One field of one event, as a mod changes it.</summary>
    public readonly struct Change
    {
        public int Event { get; }
        public Field Field { get; }
        public int Value { get; }

        public Change(int ev, Field field, int value)
        {
            Event = ev;
            Field = field;
            Value = value;
        }
    }
}
