// Mod Studio Framework: (1.11.0) a copied scene's map animations. Part of
// The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi, 28 October, test 35: "In the original scene when the enemies break
// into the room the door opens. In the copied scene the door remains closed
// as they enter." The scene was the game's event 160 (the Bunansa residence,
// map 41) copied into a quest, played as event 1044: its script the game's,
// its 0x55 starting the door's texture animation record 0 as the game's
// does. But the remaster plays a map's doors, and some of its other moving
// parts, by the event playing: the map's command 0x83 (0x24F5A0), which
// starts a texture animation record, reads the event playing (variable 0x27,
// through the variables' read, 0x2332D8) and hands it with the record to the
// enhanced look (0xC9538 and 0xC729C), whose code opens event 160's door for
// record 0, and does nothing for an event it doesn't know; the animations'
// step (0x24FBD8) reads it again as a record ends. So a quest's event that
// says the game's event it was copied from (its From, QuestFile.cs) has those
// four reads give that event's number: each of their calls of the variables'
// read goes to a few bytes of native code made here, which call it as the
// program did and, when the event playing is one of the quests' with a From,
// give the From. Every other reader of the event playing (the event chain,
// the finish table, the helper's own hooks) still sees the quest's own
// number. Each read found by its own bytes, all four calling the one
// function; the four calls changed all or none, said.
// dev/research/sidequests/map_animations.py has what was measured;
// dev/test_side_quests.py runs the native code, and the enhanced look's own
// code for event 160's door, with unicorn.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace ModStudioEventSetup
{
    public static unsafe class MapAnimations
    {
        /// <summary>The events the table gives a From for: every number a quest's event may have (EventRoom's room).</summary>
        public const int Events = EventRoom.Events;
        /// <summary>The native code's room before the table, in the memory made for both.</summary>
        public const int CodeRoom = 0x40;
        public const int MemoryBytes = CodeRoom + 2 * Events;

        // --- what was measured (his 17 September program) -------------------------------------------------------

        /// <summary>The four reads of the event playing: each a call (E8) of the variables' read with ecx 0x27, found by
        /// its own bytes, the call this many bytes in. The map's command 0x83 as it starts a texture animation record:
        /// its UV animations' reads before its two calls of the enhanced look, and its palette animations' read; and
        /// the animations' step as a record ends.</summary>
        public static readonly (string Bytes, int Call, string What)[] Reads =
        {
            ("8D 4D 26 E8 ?? ?? ?? ?? 48 8B 0D ?? ?? ?? ?? 8B D0 45 8B C7 48 8B 89 70 42 02 00 E8", 3,
             "the map's start of a texture animation's first read of the event playing"),
            ("8D 4D 26 43 0F B6 BC A6 ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 8B 0D ?? ?? ?? ?? 44 8D 47 FB 8B D0 89 5C 24 20 "
             + "45 8B CF 48 8B 89 80 42 02 00", 12, "its second read of the event playing"),
            ("B9 27 00 00 00 E8 ?? ?? ?? ?? 8B D0 48 8B 05 ?? ?? ?? ?? 48 8B 88 80 42 02 00 83 79 18 FF", 5,
             "its palette animations' read of the event playing"),
            ("B9 27 00 00 00 E8 ?? ?? ?? ?? 48 8B 0D ?? ?? ?? ?? 48 8B 91 70 42 02 00 83 BA 0C 80 04 00 FF", 5,
             "the texture animations' step's read of the event playing"),
        };

        /// <summary>Where each call is (its E8, in Reads' order) and the variables' read they all call.</summary>
        public sealed class Sites
        {
            public List<int> Calls { get; } = new List<int>();
            public int Read { get; set; } = -1;
        }

        static int I32(ReadOnlySpan<byte> image, int at) => BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at, 4));

        /// <summary>The four reads, each found once in the program's code by its own bytes, all calling one function;
        /// null and why not.</summary>
        public static Sites? Find(ReadOnlySpan<byte> image, List<Section> sections, out string why)
        {
            var sites = new Sites();
            foreach (var (bytes, call, what) in Reads)
            {
                var found = Places.Search(image, sections, Places.Pattern(bytes));
                if (found.Count != 1)
                {
                    why = $"{what} ({found.Count} places like it, not 1)";
                    return null;
                }
                int at = found[0] + call;
                int target = at + 5 + I32(image, at + 1);
                if (sites.Read < 0)
                    sites.Read = target;
                else if (target != sites.Read)
                {
                    why = $"{what} (it calls {target:x}, not the variables' read the others call, {sites.Read:x})";
                    return null;
                }
                sites.Calls.Add(at);
            }
            why = "";
            return sites;
        }

        /// <summary>The native code the four calls go to, x64: the variables' read called at `read` as the program
        /// called it (ecx the variable, 0x27; the stack aligned with its 32 bytes of shadow space), then, when the
        /// number it gives is under Events and the table at `table` (a 16-bit word an event) holds one for it, that
        /// From instead. It changes no register the variables' read leaves as it was but rax and rdx (which the read
        /// changes too, as any function may).</summary>
        public static byte[] Stub(ulong read, ulong table)
        {
            var code = new List<byte>();
            void Add(params byte[] bytes) => code.AddRange(bytes);
            void Address(ulong value)
            {
                var bytes = new byte[8];
                BinaryPrimitives.WriteUInt64LittleEndian(bytes, value);
                code.AddRange(bytes);
            }
            Add(0x48, 0x83, 0xEC, 0x28);                       // sub rsp, 0x28
            Add(0x48, 0xB8);                                   // mov rax, read
            Address(read);
            Add(0xFF, 0xD0);                                   // call rax
            Add(0x48, 0x83, 0xC4, 0x28);                       // add rsp, 0x28
            Add(0x8B, 0xC0);                                   // mov eax, eax (its upper half 0)
            Add(0x3D);                                         // cmp eax, Events
            var events = new byte[4];
            BinaryPrimitives.WriteInt32LittleEndian(events, Events);
            Add(events);
            Add(0x73, 0x13);                                   // jae: past the table's 19 bytes, as it was
            Add(0x48, 0xBA);                                   // mov rdx, table
            Address(table);
            Add(0x0F, 0xB7, 0x14, 0x42);                       // movzx edx, word [rdx + rax*2]
            Add(0x85, 0xD2);                                   // test edx, edx
            Add(0x0F, 0x45, 0xC2);                             // cmovnz eax, edx: its From
            Add(0xC3);                                         // ret
            return code.ToArray();
        }

        /// <summary>The table's words: each quest event's From by its number, 0 for every other.</summary>
        public static byte[] Table(IEnumerable<(int Number, int From)> copied)
        {
            var table = new byte[2 * Events];
            foreach (var (number, from) in copied)
                if (number >= 0 && number < Events && from > 0 && from <= QuestFile.MostGameEvent)
                    BinaryPrimitives.WriteUInt16LittleEndian(table.AsSpan(2 * number, 2), (ushort)from);
            return table;
        }

        /// <summary>The four calls sent to the native code at `stubAt` (from the program's start): each call's distance,
        /// with the four bytes it replaces as his program has them; null and why when it is too far for one.</summary>
        public static List<CodePatch>? Patches(ReadOnlySpan<byte> image, Sites sites, long stubAt, out string why)
        {
            var patches = new List<CodePatch>();
            for (int n = 0; n < sites.Calls.Count; n++)
            {
                int at = sites.Calls[n];
                long distance = stubAt - (at + 5);
                if (distance < int.MinValue || distance > int.MaxValue)
                {
                    why = "the memory given the map's animations is more than 2 GB from the game's program";
                    return null;
                }
                var bytes = new byte[4];
                BinaryPrimitives.WriteInt32LittleEndian(bytes, (int)distance);
                patches.Add(new CodePatch(at + 1, image.Slice(at + 1, 4).ToArray(), bytes, Reads[n].What));
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

        const uint Commit = 0x1000, Reserve = 0x2000, ReadWrite = 0x04, ExecuteRead = 0x20, ExecuteReadWrite = 0x40;
        /// <summary>Under 2 GB after the program's start: the calls' distances.</summary>
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

        /// <summary>The four reads given the quests' events' From (`copied`: each event's number and its From), before
        /// the game runs: the memory made within 2 GB of the program and given the native code and the table, then each
        /// call checked against the bytes it replaces and all changed. False and why: then nothing is changed.</summary>
        public static bool Arm(byte* start, int imageSize, Sites sites, IEnumerable<(int Number, int From)> copied,
                               out string why)
        {
            var image = new ReadOnlySpan<byte>(start, imageSize);
            ulong imageBase = (ulong)start;
            nint memory = Near(imageBase, imageSize, MemoryBytes);
            if (memory == 0)
            {
                why = "Windows gave no memory within 2 GB of the game's program";
                return false;
            }
            long stubAt = (long)((ulong)memory - imageBase);
            var patches = Patches(image, sites, stubAt, out why);
            if (patches == null)
                return false;
            foreach (var patch in patches)
                if (!image.Slice(patch.At, patch.Old.Length).SequenceEqual(patch.Old))
                {
                    why = $"{patch.What} isn't as it was found";
                    return false;
                }
            var code = Stub(imageBase + (ulong)sites.Read, (ulong)memory + CodeRoom);
            Marshal.Copy(code, 0, memory, code.Length);
            var table = Table(copied);
            Marshal.Copy(table, 0, memory + CodeRoom, table.Length);
            if (!VirtualProtect(memory, (nuint)MemoryBytes, ExecuteRead, out _))
            {
                why = "the memory given the map's animations couldn't be made code";
                return false;
            }
            FlushInstructionCache(GetCurrentProcess(), memory, (nuint)MemoryBytes);
            // Every call made writable first, so that either all are changed or none.
            var protections = new uint[patches.Count];
            for (int n = 0; n < patches.Count; n++)
            {
                if (VirtualProtect((nint)(start + patches[n].At), (nuint)patches[n].New.Length, ExecuteReadWrite,
                                   out protections[n]))
                    continue;
                for (int m = n - 1; m >= 0; m--)
                    VirtualProtect((nint)(start + patches[m].At), (nuint)patches[m].New.Length, protections[m], out _);
                why = $"{patches[n].What} couldn't be changed";
                return false;
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
            return true;
        }
    }
}
