// Mod Studio Framework: (1.9.0) room for hundreds of quests. Part of The
// Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi, 27 October, after his test 30: "Room for hundreds of quests". The
// game's event numbers stop at 886: its finish table (887 words, one an event
// by its number: the next event and what follows, written from every setup
// record as a scenario loads) has the scenario's own flags and offsets right
// after it, and its setup table has 887 slots, 713 of them the game's. So 97
// numbers were free, shared by every mod's quests, a quest taking 2 or more.
//
// The helper gives both tables, and the battle retry's copy of the finish
// table, room for 8192 events in memory of its own within 2 GB of the program,
// once every mod has loaded (WotL Restoration's changes to the records, made
// as it loads, are then in the copy; a change found later through the table's
// lea reaches the copy). 35 changes, each a distance or a number of the same
// size, none of them native code: the setup table's four leas and three
// bounds (887), the finish table's sixteen reaches, the retry's two leas and
// two sizes, the next event's two decodes widened from 10 bits to 13 (a next
// event up to 8191: its high byte times 0x400 below what follows' 0x8000),
// what follows' four tests made 0x8300 from 0xF300 (what follows is 0x80 to
// 0x82 times 0x100, so 0x8300 reads every record of the game's as 0xF300 did,
// its next events under 887; a next event past 1023 sets bits 0xF300 would
// take for something following), and (1.9.1) its kind, decided as an event
// ends, read by 0x83 and 0x8300 from 0xF3 and 0xF300 (his test 31: a scene
// whose next event was 1025 went back to the world map, its kind read as
// none of the three). Each found by its own bytes and checked against them as
// the helper makes it; all made or none, said.
// dev/research/sidequests/event_room.py runs the game's own code over the
// moved tables; helper/Checks has the helper find and plan them in his
// program.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace ModStudioEventSetup
{
    public sealed unsafe class EventRoom
    {
        /// <summary>The events the moved tables have room for, the last a next event's 13 bits can name.</summary>
        public const int Events = 8192, LastEvent = Events - 1;
        public const int GameEvents = Table.GameSlots, RecordBytes = Table.RecordBytes;
        /// <summary>The finish table's bytes as the game has them (887 words: 0x6EE).</summary>
        public const int FinishBytes = 2 * GameEvents;
        /// <summary>The moved tables, one after another in the helper's memory: the setup table, the finish table,
        /// the retry's copy.</summary>
        public const int SetupBytes = Events * RecordBytes, FinishRoom = 2 * Events, MemoryBytes =
            SetupBytes + 2 * FinishRoom;
        public const int WideDecode = 0x1F00, FollowsTest = 0x8300;

        // --- what was measured (his 17 September program) -------------------------------------------------------

        /// <summary>The scenario setup's write of the finish table from every record: mov word [r15 + rax*2 + x],
        /// r8w (x the table, from the program's start); cmp r11d, esi; jb.</summary>
        public const string FinishWriteBytes = "66 45 89 84 47 ?? ?? ?? ?? 44 3B DE 72";
        /// <summary>The finish table's reaches by a distance from the program's start (r15, r12 or rdi holding it):
        /// the bytes before the distance.</summary>
        public static readonly string[] FinishBasedBytes =
            { "66 45 89 84 47", "41 0F B7 84 4F", "41 0F B7 84 5C", "66 85 8C 47" };
        /// <summary>The scenario setup's six writes of events 400 to 404's own after its write of every record's:
        /// where each starts past the write, its bytes before the distance, its length, the word it writes (a
        /// `mov dword [rip + x], 0x80000000` writes 401 and 402).</summary>
        public static readonly (int At, string Bytes, int Length, int Word)[] FixedWrites =
        {
            (0x13, "C7 05", 10, 401), (0x22, "66 44 89 25", 8, 403), (0x33, "66 89 1D", 7, 400),
            (0x3A, "66 89 1D", 7, 404), (0x48, "66 89 05", 7, 400), (0x4F, "66 89 05", 7, 404),
        };
        public const int FinishLeas = 6, FinishBased = 4;
        /// <summary>The setup table's leas (4) and bounds: mov esi, 887 (2) and cmp r8d, 887 (1), each within this
        /// many bytes after a lea of the table.</summary>
        public const int SetupLeas = 4, BoundReach = 0x40;
        public const string BoundEsiBytes = "BE 77 03 00 00", BoundR8Bytes = "41 81 F8 77 03 00 00";
        /// <summary>The battle retry's copies of the finish table: mov r8d, 0x6EE, twice; the first after a lea of
        /// its copy (lea rcx), the second before one (lea rdx, after the finish table's lea rcx).</summary>
        public const string RetrySizeBytes = "41 B8 EE 06 00 00";
        /// <summary>The next event's two decodes (and ecx/edx, 0x300) within this many bytes after a reach of the
        /// finish table, and what follows' four tests (0xF300 into edx, r9d, ecx; test eax) within these of one.</summary>
        public static readonly string[] DecodeBytes = { "81 E1 00 03 00 00", "81 E2 00 03 00 00" };
        public static readonly (string Bytes, int Imm)[] TestBytes =
        {
            ("41 B9 00 F3 00 00", 2), ("BA 00 F3 00 00", 1), ("B9 00 F3 00 00", 1), ("A9 00 F3 00 00", 1),
        };
        public const int DecodeReach = 0x80, TestBefore = 0x10, TestAfter = 0x50, Decodes = 2, Tests = 4;
        /// <summary>(1.9.1) What follows an event, decided as it ends (the event chain, `0x23987C`): its kind read from
        /// the word's high byte through `and eax, 0xF3` (then 0x80 the world map, 0x81 the next event, 0x82 a reset),
        /// and 0x83's through `and ebx, 0xF300` (then `cmp ebx, 0x8300`); each within this many bytes after a reach
        /// of the finish table, its immediate where it is and what it becomes (0x83, 0x8300: the next event's bits
        /// left out, as the tests').</summary>
        public static readonly (string Bytes, int Imm, int New)[] KindBytes =
        {
            ("25 F3 00 00 00", 1, 0x83), ("81 E3 00 F3 00 00", 2, FollowsTest),
        };
        public const int KindReach = 0xC0, Kinds = 2;

        /// <summary>Where each change goes, as found: the setup table's leas (and where each points past the table's
        /// start) and bounds; the finish table, its leas, its reaches by a distance, its six writes; the retry's
        /// copy, its leas and sizes; the decodes and the tests.</summary>
        public sealed class Sites
        {
            public int SetupTable { get; set; } = -1;
            public List<(int At, int Past)> SetupLeas { get; } = new List<(int, int)>();
            public List<(int At, int Imm)> Bounds { get; } = new List<(int, int)>();
            public int FinishTable { get; set; } = -1;
            public List<int> FinishLeas { get; } = new List<int>();
            public List<(int At, int Distance)> FinishBased { get; } = new List<(int, int)>();
            public List<(int At, int Distance, int Length, int Word)> FixedWrites { get; } =
                new List<(int, int, int, int)>();
            public int RetryCopy { get; set; } = -1;
            public List<int> RetryLeas { get; } = new List<int>();
            public List<int> RetrySizes { get; } = new List<int>();
            public List<int> Decodes { get; } = new List<int>();
            public List<(int At, int Imm)> Tests { get; } = new List<(int, int)>();
            /// <summary>(1.9.1) What follows' kind's two masks: where each is, its immediate, what it becomes.</summary>
            public List<(int At, int Imm, int New)> Kinds { get; } = new List<(int, int, int)>();
            public int Count => SetupLeas.Count + Bounds.Count + FinishLeas.Count + FinishBased.Count
                                + FixedWrites.Count + RetryLeas.Count + RetrySizes.Count + Decodes.Count + Tests.Count
                                + Kinds.Count;
        }

        static int I32(ReadOnlySpan<byte> image, int at) => BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at, 4));

        /// <summary>Whether each lea reaches `target` exactly.</summary>
        static bool AllReach(ReadOnlySpan<byte> image, List<int> leas, int target)
        {
            foreach (int at in leas)
                if (at + 7 + I32(image, at + 3) != target)
                    return false;
            return true;
        }

        /// <summary>The bytes of an immediate after a rip-relative operand's distance (at `at`, the operand's byte
        /// before it), for the instructions a compiler gives a variable with one: mov (C6, C7), arithmetic and
        /// compares (80, 81, 83), test (F6, F7 /0 and /1), shifts (C0, C1), imul (6B, 69), bt and its kin (0F BA); an
        /// immediate of 4 is 2 after a 66 (without REX.W). Else none.</summary>
        static int ImmediateAfter(ReadOnlySpan<byte> image, int at)
        {
            if (at < 3)
                return 0;
            byte op = image[at - 2];
            int reg = (image[at - 1] >> 3) & 7, before = at - 3;
            bool rexW = false;
            if (image[before] >= 0x40 && image[before] <= 0x4F)
            {
                rexW = (image[before] & 8) != 0;
                before--;
            }
            int wide = !rexW && before >= 0 && image[before] == 0x66 ? 2 : 4;
            switch (op)
            {
                case 0xC6: case 0x80: case 0x83: case 0xC0: case 0xC1: case 0x6B:
                    return 1;
                case 0xC7: case 0x81: case 0x69:
                    return wide;
                case 0xF6:
                    return reg <= 1 ? 1 : 0;
                case 0xF7:
                    return reg <= 1 ? wide : 0;
                case 0xBA:
                    return image[at - 3] == 0x0F ? 1 : 0;
                default:
                    return 0;
            }
        }

        /// <summary>Every rip-relative operand in the program's code reaching [low, high) (an operand's byte before a
        /// distance), counting an immediate after the distance: the leas' starts (48 or 4C, 8D; 7 bytes) and the
        /// others' distances. (Places.RipLeas doesn't count an immediate: it takes the scenario's flag right after
        /// the finish table, cleared by a mov byte, for the table's last word, and would miss a write of the table's
        /// first word with one.)</summary>
        internal static List<int> Reaching(ReadOnlySpan<byte> image, List<Section> sections, long low, long high,
                                  List<int> others)
        {
            var leas = new List<int>();
            foreach (var section in sections)
            {
                if (!section.Code)
                    continue;
                int end = Math.Min(section.Address + section.Size, image.Length) - 4;
                for (int at = section.Address + 1; at <= end; at++)
                {
                    if ((image[at - 1] & 0xC7) != 0x05)
                        continue;
                    long target = at + 4L + I32(image, at);
                    if (target < low - 4 || target >= high)
                        continue;
                    bool lea = at >= 3 && (image[at - 3] == 0x48 || image[at - 3] == 0x4C) && image[at - 2] == 0x8D;
                    if (!lea)
                        target += ImmediateAfter(image, at);
                    if (target < low || target >= high)
                        continue;
                    if (lea)
                        leas.Add(at - 3);
                    else
                        others.Add(at);
                }
            }
            return leas;
        }

        /// <summary>Every place in [from, to) where the pattern is.</summary>
        internal static List<int> Within(ReadOnlySpan<byte> image, int from, int to, string bytes)
        {
            var pattern = Places.Pattern(bytes);
            var found = new List<int>();
            for (int at = Math.Max(0, from); at < to && at + pattern.Length <= image.Length; at++)
                if (Places.At(image, at, pattern))
                    found.Add(at);
            return found;
        }

        /// <summary>The sites, each found by its own bytes where it was measured to be, given the setup table (as the
        /// helper finds it); null and why not.</summary>
        public static Sites? Find(ReadOnlySpan<byte> image, List<Section> sections, int setupTable, out string why)
        {
            var sites = new Sites { SetupTable = setupTable };
            // The setup table: four leas reaching it and nothing else; three bounds of 887, each after a lea.
            var others = new List<int>();
            var leas = Reaching(image, sections, setupTable, setupTable + (long)GameEvents * RecordBytes, others);
            if (leas.Count != SetupLeas || others.Count != 0)
            {
                why = $"the setup table's reaches ({leas.Count} leas and {others.Count} others, not {SetupLeas} and 0)";
                return null;
            }
            foreach (int at in leas)
                sites.SetupLeas.Add((at, at + 7 + I32(image, at + 3) - setupTable));
            var bounds = new SortedSet<(int, int)>();
            foreach (var (bytes, imm) in new[] { (BoundEsiBytes, 1), (BoundR8Bytes, 3) })
                foreach (int lea in leas)
                    foreach (int at in Within(image, lea + 7, lea + 7 + BoundReach, bytes))
                        bounds.Add((at, imm));
            int esi = Places.Search(image, sections, Places.Pattern(BoundEsiBytes)).Count;
            int r8 = Places.Search(image, sections, Places.Pattern(BoundR8Bytes)).Count;
            if (bounds.Count != 3 || esi != 2 || r8 != 1)
            {
                why = $"the setup table's bounds ({bounds.Count} after its leas, {esi + r8} in all, not 3)";
                return null;
            }
            sites.Bounds.AddRange(bounds);
            // The finish table: from its write; its leas, its reaches by a distance, its six writes.
            var writes = Places.Search(image, sections, Places.Pattern(FinishWriteBytes));
            if (writes.Count != 1)
            {
                why = $"the finish table's write ({writes.Count} places like it, not 1)";
                return null;
            }
            int write = writes[0];
            int finish = I32(image, write + 5);
            sites.FinishTable = finish;
            foreach (var (past, bytes, length, word) in FixedWrites)
            {
                int at = write + past;
                int distance = at + Places.Pattern(bytes).Length;
                if (!Places.At(image, at, Places.Pattern(bytes)) || at + length + I32(image, distance) != finish + 2 * word)
                {
                    why = $"the scenario setup's write of event {word}'s own (at + {past:x})";
                    return null;
                }
                sites.FixedWrites.Add((at, distance - at, length, word));
            }
            // Its rip-relative reaches: six leas, and the six writes (nothing else).
            var finishOthers = new List<int>();
            var finishLeas = Reaching(image, sections, finish, finish + (long)FinishBytes, finishOthers);
            var writesAt = new SortedSet<int>(sites.FixedWrites.ConvertAll(w => w.At + w.Distance));
            if (finishLeas.Count != FinishLeas || !AllReach(image, finishLeas, finish)
                || !writesAt.SetEquals(finishOthers))
            {
                why = $"the finish table's reaches ({finishLeas.Count} leas and {finishOthers.Count} others, not "
                      + $"{FinishLeas} and its {FixedWrites.Length} writes of events 400 to 404)";
                return null;
            }
            sites.FinishLeas.AddRange(finishLeas);
            var based = Places.Distances(image, sections, finish, finish + 1, FinishBasedBytes);
            if (based.Count != FinishBased || !based.Exists(b => b.At == write))
            {
                why = $"the finish table's reaches from the program's start ({based.Count}, not {FinishBased})";
                return null;
            }
            sites.FinishBased.AddRange(based);
            // The retry's copy: its two sizes, the lea of it before the first and after the second.
            var sizes = Places.Search(image, sections, Places.Pattern(RetrySizeBytes));
            if (sizes.Count != 2 || !sites.FinishLeas.Contains(sizes[0] + 6) || !sites.FinishLeas.Contains(sizes[1] - 7))
            {
                why = $"the battle retry's copies of the finish table ({sizes.Count} of 0x6EE bytes, not 2 beside it)";
                return null;
            }
            int retry = sizes[0] - 7 + 7 + I32(image, sizes[0] - 7 + 3);
            var retryOthers = new List<int>();
            var retryLeas = Reaching(image, sections, retry, retry + (long)FinishBytes, retryOthers);
            if (retryLeas.Count != 2 || retryOthers.Count != 0 || !retryLeas.Contains(sizes[0] - 7)
                || !retryLeas.Contains(sizes[1] + 6) || !AllReach(image, retryLeas, retry))
            {
                why = $"the battle retry's copy ({retryLeas.Count} leas and {retryOthers.Count} others, not 2 and 0)";
                return null;
            }
            sites.RetryCopy = retry;
            sites.RetryLeas.AddRange(retryLeas);
            sites.RetrySizes.AddRange(sizes);
            // The decodes and the tests, near the finish table's reaches.
            var reaches = new List<int>(sites.FinishLeas);
            foreach (var (at, _) in sites.FinishBased)
                reaches.Add(at);
            var decodes = new SortedSet<int>();
            var tests = new SortedDictionary<int, int>();
            foreach (int reach in reaches)
            {
                foreach (var bytes in DecodeBytes)
                    foreach (int at in Within(image, reach, reach + DecodeReach, bytes))
                        decodes.Add(at);
                foreach (var (bytes, imm) in TestBytes)
                    foreach (int at in Within(image, reach - TestBefore, reach + TestAfter, bytes))
                        tests[at] = imm;
            }
            // A test into r9d (41 B9) holds a test into ecx's bytes (B9) one after its start: that one is the same.
            foreach (var (at, imm) in new List<KeyValuePair<int, int>>(tests).ConvertAll(kv => (kv.Key, kv.Value)))
                if (imm == 2)
                    tests.Remove(at + 1);
            if (decodes.Count != Decodes || tests.Count != Tests)
            {
                why = $"the next event's decodes and what follows' tests ({decodes.Count} and {tests.Count}, not "
                      + $"{Decodes} and {Tests})";
                return null;
            }
            sites.Decodes.AddRange(decodes);
            foreach (var (at, imm) in tests)
                sites.Tests.Add((at, imm));
            // (1.9.1) What follows' kind as an event ends, near the finish table's reaches too.
            var kinds = new SortedDictionary<int, (int Imm, int New)>();
            foreach (int reach in reaches)
                foreach (var (bytes, imm, value) in KindBytes)
                    foreach (int at in Within(image, reach, reach + KindReach, bytes))
                        kinds[at] = (imm, value);
            if (kinds.Count != Kinds)
            {
                why = $"what follows' kinds as an event ends ({kinds.Count}, not {Kinds})";
                return null;
            }
            foreach (var (at, (imm, value)) in kinds)
                sites.Kinds.Add((at, imm, value));
            why = "";
            return sites;
        }

        static byte[] Bytes32(long value)
        {
            var b = new byte[4];
            BinaryPrimitives.WriteInt32LittleEndian(b, checked((int)value));
            return b;
        }

        static CodePatch Change(ReadOnlySpan<byte> image, int at, long value, string what)
            => new CodePatch(at, image.Slice(at, 4).ToArray(), Bytes32(value), what);

        /// <summary>The changes for the tables moved to `setupAt`, `finishAt` and `retryAt` (from the program's start,
        /// as its distances count): each the four bytes it replaces as his program has them; null and why when the
        /// memory is too far for a distance.</summary>
        public static List<CodePatch>? Patches(ReadOnlySpan<byte> image, Sites sites, long setupAt, long finishAt,
                                               long retryAt, out string why)
        {
            var patches = new List<CodePatch>();
            try
            {
                foreach (var (at, past) in sites.SetupLeas)
                    patches.Add(Change(image, at + 3, setupAt + past - (at + 7), $"the setup table's lea at {at:x}"));
                foreach (var (at, imm) in sites.Bounds)
                    patches.Add(Change(image, at + imm, Events, $"the setup table's bound at {at:x}"));
                foreach (int at in sites.FinishLeas)
                    patches.Add(Change(image, at + 3, finishAt - (at + 7), $"the finish table's lea at {at:x}"));
                foreach (var (at, distance) in sites.FinishBased)
                    patches.Add(Change(image, distance, finishAt, $"the finish table's reach at {at:x}"));
                foreach (var (at, distance, length, word) in sites.FixedWrites)
                    patches.Add(Change(image, at + distance, finishAt + 2 * word - (at + length),
                                       $"the scenario setup's write of event {word}'s own at {at:x}"));
                foreach (int at in sites.RetryLeas)
                    patches.Add(Change(image, at + 3, retryAt - (at + 7), $"the retry's copy's lea at {at:x}"));
                foreach (int at in sites.RetrySizes)
                    patches.Add(Change(image, at + 2, FinishRoom, $"the retry's copy's size at {at:x}"));
                foreach (int at in sites.Decodes)
                    patches.Add(Change(image, at + 2, WideDecode, $"the next event's decode at {at:x}"));
                foreach (var (at, imm) in sites.Tests)
                    patches.Add(Change(image, at + imm, FollowsTest, $"what follows' test at {at:x}"));
                foreach (var (at, imm, value) in sites.Kinds)
                    patches.Add(Change(image, at + imm, value, $"what follows' kind at {at:x}"));
            }
            catch (OverflowException)
            {
                why = "the memory given the events is more than 2 GB from the game's program";
                return null;
            }
            why = "";
            return patches;
        }

        // --- in the game ---------------------------------------------------------------------------------------------

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern nint VirtualAlloc(nint address, nuint size, uint type, uint protect);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool VirtualProtect(nint address, nuint size, uint protect, out uint old);

        [DllImport("kernel32.dll")]
        static extern nint GetCurrentProcess();

        [DllImport("kernel32.dll")]
        static extern bool FlushInstructionCache(nint process, nint address, nuint size);

        const uint Commit = 0x1000, Reserve = 0x2000, ReadWrite = 0x04, ExecuteReadWrite = 0x40;
        /// <summary>Under 2 GB after the program's start: the finish table's reaches by a distance from it.</summary>
        const long Reach = 0x7F000000;

        static nint Near(ulong imageBase, int imageSize, int size)
        {
            const ulong Granularity = 0x10000;
            ulong start = (imageBase + (ulong)imageSize + Granularity - 1) & ~(Granularity - 1);
            for (ulong at = start; at + (ulong)size < imageBase + (ulong)Reach; at += Granularity)
            {
                nint got = VirtualAlloc((nint)at, (nuint)size, Commit | Reserve, ReadWrite);
                if (got != 0)
                    return got;
            }
            return 0;
        }

        /// <summary>The tables moved, before the game runs (every mod loaded): the memory made and given the setup
        /// table's slots, the finish table and the retry's copy as they are, then each change checked against the
        /// bytes it replaces and all made. The moved setup table (its slots, as the helper reads them from there on),
        /// or null and why: then nothing of the program is changed.</summary>
        public static Table? Arm(byte* start, int imageSize, Sites sites, Table table, out string why)
        {
            var image = new ReadOnlySpan<byte>(start, imageSize);
            ulong imageBase = (ulong)start;
            nint memory = Near(imageBase, imageSize, MemoryBytes);
            if (memory == 0)
            {
                why = "Windows gave no memory within 2 GB of the game's program";
                return null;
            }
            long setupAt = (long)((ulong)memory - imageBase), finishAt = setupAt + SetupBytes,
                 retryAt = finishAt + FinishRoom;
            var patches = Patches(image, sites, setupAt, finishAt, retryAt, out why);
            if (patches == null)
                return null;
            foreach (var patch in patches)
                if (!image.Slice(patch.At, patch.Old.Length).SequenceEqual(patch.Old))
                {
                    why = $"{patch.What} isn't as it was found";
                    return null;
                }
            Buffer.MemoryCopy(start + sites.SetupTable, (void*)memory, SetupBytes,
                              (long)table.Slots * RecordBytes);
            Buffer.MemoryCopy(start + sites.FinishTable, start + finishAt, FinishRoom, FinishBytes);
            Buffer.MemoryCopy(start + sites.RetryCopy, start + retryAt, FinishRoom, FinishBytes);
            // Every change made writable first, so that either all are made or none (each page's protection put back
            // as it was, last first: a page two changes share was made writable by the first).
            var protections = new uint[patches.Count];
            for (int n = 0; n < patches.Count; n++)
            {
                if (VirtualProtect((nint)(start + patches[n].At), (nuint)patches[n].New.Length, ExecuteReadWrite,
                                   out protections[n]))
                    continue;
                for (int m = n - 1; m >= 0; m--)
                    VirtualProtect((nint)(start + patches[m].At), (nuint)patches[m].New.Length, protections[m], out _);
                why = $"{patches[n].What} couldn't be changed";
                return null;
            }
            foreach (var patch in patches)
                Marshal.Copy(patch.New, 0, (nint)(start + patch.At), patch.New.Length);
            for (int m = patches.Count - 1; m >= 0; m--)
            {
                nint where = (nint)(start + patches[m].At);
                VirtualProtect(where, (nuint)patches[m].New.Length, protections[m], out _);
                FlushInstructionCache(GetCurrentProcess(), where, (nuint)patches[m].New.Length);
            }
            why = "";
            return new Table(checked((int)setupAt), $"moved past the program, room for {Events}", Events,
                             new Dictionary<int, int>(table.SlotOf));
        }
    }
}
