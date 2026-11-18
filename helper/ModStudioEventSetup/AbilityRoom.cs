// A mod's own action abilities: the framework's own code in the game's central routines (the road's step 4; Zodi's
// answer of 10 November 2026: "Straight to more"). The build's fourth step, first part. Part of The Ivalice Chronicles
// Mod Studio, GPL-3.0.
//
// (1.41.0) Part of the helper since new abilities moved in for test 94 (built beside it until the whole rehearsed).
//
// The game reads an ability through a few routines that everything else calls. Three of them are taken here at their
// first instructions: a jump to a piece of the framework's own code, which answers for a mod's ability and otherwise
// does the instructions the jump replaced and goes back, so the game's own numbers go the game's own way.
//
// - The reader (a skillset in ecx, a place in it in edx: the ability there, in eax). A skillset's record holds an
//   ability in nine bits, so a mod's ability at a place is kept in a list of the framework's own, a word for each
//   place of each skillset (0: none, the game's record is read). 89 calls reach an ability through this and the
//   others; 14 call it.
// - The action record's getter (an ability in ecx: where its record of 20 bytes is, in rax; for the game, nothing for
//   a number past 367). For a number from 549 to 1023: its record in the framework's own table. 39 calls.
// - The effect's chooser (the ability in edx). For a mod's ability: the game's ability it is like, so its effect is
//   that one's. 3 calls.
//
// The framework's room for abilities, from its start: the code, with two cells at its room's end (the first the
// framework's own function that is told the names' file is read: AbilityWords.Longer); the abilities the mods' are
// like (a word each, from 549); (1.41.2) the turn order's table of the units' readied words (a word for each of the 21
// units, kept by the turn order's writer as it writes); their action records (20 bytes each); the list of places (256
// skillsets of 32 places, a word each); then the longer table of the abilities' records (AbilityRecords); then the
// longer table of their effects (AbilityEffects); then the longer table of how their users move (AbilityAnimations).
//
// (1.41.2, his test 95) And the battle's places the first measure missed: the menu's confirm, which cut the chosen
// word to nine bits (550, Mending Light, became 38, Float); six compares more (the menu's MP and charge of each action,
// the MP a charged ability costs, the action's formula, two lists more); and the turn order's writer, whose word for
// each unit the places that make an entry's ability again read, where 1.41.0 read the unit's own word after the menu
// had put it back.
//
// (The build's sixth step.) The loader of the older text's files is changed in two places, so that the names' file
// can be made longer (AbilityWords): where the file's room is asked for, the names' file's is asked for with
// NamesExtra bytes more; and where the file has been read, the framework's function in the first cell is called for
// the names' file (its room in rcx, the file's size in edx), as one function of the game calls another (the place is
// between two calls of the loader's own, the stack as they have it).
using System;
using System.Buffers.Binary;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public static partial class AbilityRoom
    {
        /// <summary>The room, from its start: where each part is, and its size in all.</summary>
        public const int CodeRoom = 0x1000, LikesAt = 0x1000, ActionsAt = 0x1400, PlacesAt = 0x4000, RecordsAt = 0x8000,
                         EffectsAt = RecordsAt + AbilityRecords.Bytes, AnimationsAt = EffectsAt + AbilityEffects.Bytes,
                         Room = AnimationsAt + AbilityAnimations.Bytes;
        /// <summary>The cells, at the end of the code's room: the framework's function told the names' file is read
        /// (a room in rcx, the file's size in edx); the second is kept.</summary>
        public const int CellsAt = CodeRoom - 0x10, NamesCell = CellsAt;
        /// <summary>(1.41.2) The turn order's table of the units' readied words: a word for each of the 21 units, after
        /// the likes (which end at LikesAt + 2 * 475) and before the action records.</summary>
        public const int TurnOrderAt = 0x13C0;
        /// <summary>The loader's store of a file's pointer (`mov [r15 + rbp*8 + the pointers], rax`): where the four
        /// bytes of the pointers' place are from the first of the loader's two places.</summary>
        const int PointersAfter = 18;
        /// <summary>The list of places: how many skillsets, and places in each.</summary>
        public const int Skillsets = 256, PlacesEach = 32;
        const int First = AbilityRecords.First, Last = AbilityRecords.Count - 1, ActionBytes = AbilityFile.ActionRecordBytes;

        /// <summary>The central routines found: where each starts (from the program's start). And each compare that is
        /// to take a mod's ability for a plain action: where it is.</summary>
        public sealed class Found
        {
            public Dictionary<string, int> At { get; } = new Dictionary<string, int>();
            public int[] CompareAt { get; } = new int[Compares.Length];
            public int[] CutAt { get; } = new int[Cuts.Length];
            public int[] LoaderAt { get; } = new int[Loader.Length];
            public int[] ChargingAt { get; } = new int[Charging.Length];
            /// <summary>(1.41.1) Where each tab's filter of a skillset's abilities is.</summary>
            public int[] FilterAt { get; } = new int[Filters.Length];
            /// <summary>Where the turn order's writer's `lea` of the units' records is.</summary>
            public int UnitsAt { get; set; } = -1;
            /// <summary>(1.41.2, his test 95) Where the battle menu's confirm's cut is, the turn order writer's load of a
            /// unit's readied word, and each of the two places that make an entry's ability again as a text code.</summary>
            public int MenuCutAt { get; set; } = -1;
            public int WriterAt { get; set; } = -1;
            public int[] TextAt { get; } = new int[Texts.Length];
            public List<string> Missing { get; } = new List<string>();
            public bool Ok => Missing.Count == 0;
        }

        /// <summary>Each routine found once by its first bytes.</summary>
        public static Found Find(ReadOnlySpan<byte> image, List<Section> sections)
        {
            var found = new Found();
            foreach (var (name, pattern, _) in Entries)
            {
                var matches = Places.Search(image, sections, Places.Pattern(pattern));
                if (matches.Count != 1)
                    found.Missing.Add($"the abilities' {name} ({matches.Count} places like it, not 1)");
                else
                    found.At[name] = matches[0];
            }
            // Each compare, found as many times as measured (twice where its function has a twin, and then the one of
            // the two measured, by their order in the program). Its pattern is the compare whole and the instruction
            // after it but for a jump's distance, so one found is the compare measured.
            for (int n = 0; n < Compares.Length; n++)
            {
                var (pattern, of, which, _, _, _, _, _, _) = Compares[n];
                var matches = Places.Search(image, sections, Places.Pattern(pattern));
                if (matches.Count != of)
                {
                    found.Missing.Add($"the abilities' compare {n + 1} ({matches.Count} places like it, not {of})");
                    continue;
                }
                matches.Sort();
                found.CompareAt[n] = matches[which];
            }
            // Each cut, the same way.
            for (int n = 0; n < Cuts.Length; n++)
            {
                var (pattern, of, which, _, _, _) = Cuts[n];
                var matches = Places.Search(image, sections, Places.Pattern(pattern));
                if (matches.Count != of)
                {
                    found.Missing.Add($"the abilities' cut {n + 1} ({matches.Count} places like it, not {of})");
                    continue;
                }
                matches.Sort();
                found.CutAt[n] = matches[which];
            }
            // (11 November) The two places that make a readied ability again from the turn order, and the turn order's
            // writer (where the units' records are, and the readied ability's field), each found once.
            for (int n = 0; n < Charging.Length; n++)
            {
                var matches = Places.Search(image, sections, Places.Pattern(Charging[n].Pattern));
                if (matches.Count != 1)
                    found.Missing.Add($"the abilities' turn order {n + 1} ({matches.Count} places like it, not 1)");
                else
                    found.ChargingAt[n] = matches[0];
            }
            {
                var matches = Places.Search(image, sections, Places.Pattern(Units));
                if (matches.Count != 1)
                    found.Missing.Add($"the turn order's units ({matches.Count} places like it, not 1)");
                else
                    found.UnitsAt = matches[0];
            }
            // (1.41.1, his test 94) The tabs' filters of a skillset's abilities, each found once.
            for (int n = 0; n < Filters.Length; n++)
            {
                var matches = Places.Search(image, sections, Places.Pattern(Filters[n].Pattern));
                if (matches.Count != 1)
                    found.Missing.Add($"the abilities' tab {n + 1} ({matches.Count} places like it, not 1)");
                else
                    found.FilterAt[n] = matches[0];
            }
            // (1.41.2, his test 95) The menu's confirm's cut and the turn order writer's load, each found once; the two
            // places that make an entry's ability again as a text code, each found as measured.
            {
                var matches = Places.Search(image, sections, Places.Pattern(MenuCut));
                if (matches.Count != 1)
                    found.Missing.Add($"the abilities' menu cut ({matches.Count} places like it, not 1)");
                else
                    found.MenuCutAt = matches[0];
                matches = Places.Search(image, sections, Places.Pattern(Writer));
                if (matches.Count != 1)
                    found.Missing.Add($"the turn order's writer ({matches.Count} places like it, not 1)");
                else
                    found.WriterAt = matches[0];
            }
            for (int n = 0; n < Texts.Length; n++)
            {
                var (pattern, of, which, _) = Texts[n];
                var matches = Places.Search(image, sections, Places.Pattern(pattern));
                if (matches.Count != of)
                {
                    found.Missing.Add($"the turn order's text {n + 1} ({matches.Count} places like it, not {of})");
                    continue;
                }
                matches.Sort();
                found.TextAt[n] = matches[which];
            }
            // The loader's two places, each found once. (The first's pattern holds the store of a file's pointer after
            // it, but for the pointers' place: the list's maker stops where it doesn't.)
            for (int n = 0; n < Loader.Length; n++)
            {
                var (_, pattern, _) = Loader[n];
                var matches = Places.Search(image, sections, Places.Pattern(pattern));
                if (matches.Count != 1)
                    found.Missing.Add($"the older text's loader {n + 1} ({matches.Count} places like it, not 1)");
                else
                    found.LoaderAt[n] = matches[0];
            }
            return found;
        }

        static int Length(string name)
        {
            foreach (var (entry, _, length) in Entries)
                if (entry == name)
                    return length;
            throw new ArgumentException(name);
        }

        /// <summary>The framework's code for a room at `at` (an address, as `imageBase` is), and the changes of the
        /// game's code that send each routine to it: a jump over the routine's first instructions, which the code does
        /// itself before going back.</summary>
        public static byte[] Code(ReadOnlySpan<byte> image, Found found, ulong imageBase, ulong at, out List<JobRoom.Change> changes)
        {
            var a = new Destinations.Asm(at);
            var made = new List<JobRoom.Change>();
            const byte ShortJl = 0x7C, ShortJg = 0x7F, ShortJa = 0x77, ShortJe = 0x74, ShortJne = 0x75, ShortJle = 0x7E;

            // Each routine's first instructions as they stand in the program.
            var first = new Dictionary<string, byte[]>();
            foreach (var (name, _, length) in Entries)
                first[name] = image.Slice(found.At[name], length).ToArray();

            // A routine's first instructions done here, then back to the one after them.
            void Back(string name)
            {
                int site = found.At[name];
                a.Bytes(first[name]);
                a.Near(imageBase + (ulong)(site + first[name].Length));
            }

            // The jump from a routine's start to the code here.
            void Take(string name, ulong to)
            {
                int site = found.At[name], length = Length(name);
                var bytes = new byte[length];
                for (int n = 5; n < length; n++)
                    bytes[n] = 0x90;
                bytes[0] = 0xE9;
                BinaryPrimitives.WriteInt32LittleEndian(bytes.AsSpan(1), checked((int)((long)to - (long)(imageBase + (ulong)site + 5))));
                made.Add(new JobRoom.Change(site, bytes));
            }

            // The reader. A place of the framework's list: the skillset (to 255) times 32 and the place (to 31); a word
            // there that isn't 0 is the ability. r8 is the routine's own to spoil (its first instruction sets it).
            ulong reader = a.Here;
            a.Hex("81 F9 FF 00 00 00");                            // cmp ecx, 255
            a.Short(ShortJa, "reader's own");
            a.Hex("83 FA 1F");                                     // cmp edx, 31
            a.Short(ShortJa, "reader's own");
            a.Hex("8B C1 C1 E0 05 03 C2");                         // mov eax, ecx; shl eax, 5; add eax, edx
            a.Hex("4C 8D 05");                                     // lea r8, [rip + the list of places]
            a.Rip(at + PlacesAt);
            a.Hex("41 0F B7 04 40");                               // movzx eax, word ptr [r8 + rax*2]
            a.Hex("85 C0");                                        // test eax, eax
            a.Short(ShortJe, "reader's own");
            a.Bytes(0xC3);                                         // ret
            a.Label("reader's own");
            Back("reader");
            Take("reader", reader);

            // The action record's getter. For a number from 549 to 1023: its record in the framework's table, in rax,
            // nothing else changed.
            ulong getter = a.Here;
            a.Hex("81 F9");                                        // cmp ecx, 549
            a.I32(First);
            a.Short(ShortJl, "getter's own");
            a.Hex("81 F9");                                        // cmp ecx, 1023
            a.I32(Last);
            a.Short(ShortJg, "getter's own");
            a.Hex("52 48 63 C1 48 2D");                            // push rdx; movsxd rax, ecx; sub rax, 549
            a.I32(First);
            a.Hex("48 8D 04 80 48 C1 E0 02");                      // lea rax, [rax + rax*4]; shl rax, 2
            a.Hex("48 8D 15");                                     // lea rdx, [rip + the action records]
            a.Rip(at + ActionsAt);
            a.Hex("48 03 C2 5A C3");                               // add rax, rdx; pop rdx; ret
            a.Label("getter's own");
            Back("action record");
            Take("action record", getter);

            // The effect's chooser. For a number from 549 to 1023 that a mod's ability has: the game's ability it is
            // like in its place (edx), then on as the game's own.
            ulong effect = a.Here;
            a.Hex("81 FA");                                        // cmp edx, 549
            a.I32(First);
            a.Short(ShortJl, "effect's own");
            a.Hex("81 FA");                                        // cmp edx, 1023
            a.I32(Last);
            a.Short(ShortJg, "effect's own");
            a.Hex("50 51 8B CA");                                  // push rax; push rcx; mov ecx, edx
            a.Hex("48 8D 05");                                     // lea rax, [rip + the likes]
            a.Rip(at + LikesAt);
            a.Hex("0F B7 84 48");                                  // movzx eax, word ptr [rax + rcx*2 - 549 * 2]
            a.I32(-First * 2);
            a.Hex("59 85 C0");                                     // pop rcx; test eax, eax
            a.Short(ShortJe, "effect's as it came");
            a.Hex("8B D0");                                        // mov edx, eax
            a.Label("effect's as it came");
            a.Bytes(0x58);                                         // pop rax
            a.Label("effect's own");
            Back("effect");
            Take("effect", effect);

            // Each compare that is to take a mod's ability for a plain action. The compare is done with 549 and with 1023
            // (each less Less: 548 and 1022 where the compare is of the ability less 1, 1.41.2) in the number's place to
            // tell a mod's ability (where a register holds the number, the register is kept on
            // the stack meanwhile: no compare here reads by the stack). For a mod's: the compare once more with 0x7FFF,
            // which leaves the flags as a plain action's (below, less, not equal). For any other: the game's own
            // compare. Then the instruction after, on those flags: a jump (to where it went, or on to what followed it)
            // or the sbb, and back.
            const byte ShortJb = 0x72;
            for (int n = 0; n < Compares.Length; n++)
            {
                var (_, _, _, length, register, numberAt, _, next, less) = Compares[n];
                int site = found.CompareAt[n];
                byte[] compare = image.Slice(site, length).ToArray(), after = image.Slice(site + length, next).ToArray();
                ulong back = imageBase + (ulong)(site + length + next);
                ulong here = a.Here;

                void With(int number)
                {
                    if (register >= 0)
                    {
                        a.Bytes((byte)(0xB8 + register));          // mov eax/ecx/edx, number
                        a.I32(number);
                        a.Bytes(compare);
                    }
                    else
                    {
                        var changed = (byte[])compare.Clone();
                        BinaryPrimitives.WriteInt32LittleEndian(changed.AsSpan(numberAt), number);
                        a.Bytes(changed);
                    }
                }

                if (register >= 0)
                    a.Bytes((byte)(0x50 + register));              // push rax/rcx/rdx
                With(First - less);
                a.Short(ShortJb, $"compare {n}: the game's");
                With(Last - less);
                a.Short(ShortJa, $"compare {n}: the game's");
                With(0x7FFF);
                if (register >= 0)
                    a.Bytes((byte)(0x58 + register));              // pop
                a.Short(0xEB, $"compare {n}: after");
                a.Label($"compare {n}: the game's");
                if (register >= 0)
                    a.Bytes((byte)(0x58 + register));              // pop
                a.Bytes(compare);
                a.Label($"compare {n}: after");
                if (next == 2 && (after[0] & 0xF0) == 0x70)        // a short jump: 7x and a distance of one byte
                {
                    a.Near(back + (ulong)(long)(sbyte)after[1], (byte)(0x80 | (after[0] & 0x0F)));
                    a.Near(back);
                }
                else if (next == 6 && after[0] == 0x0F)            // a near jump: 0F 8x and a distance of four
                {
                    a.Near(back + (ulong)(long)BinaryPrimitives.ReadInt32LittleEndian(after.AsSpan(2)), after[1]);
                    a.Near(back);
                }
                else                                               // the sbb
                {
                    a.Bytes(after);
                    a.Near(back);
                }
                var bytes = new byte[length + next];
                for (int k = 5; k < bytes.Length; k++)
                    bytes[k] = 0x90;
                bytes[0] = 0xE9;
                BinaryPrimitives.WriteInt32LittleEndian(bytes.AsSpan(1), checked((int)((long)here - (long)(imageBase + (ulong)site + 5))));
                made.Add(new JobRoom.Change(site, bytes));
            }

            // Each cut of an ability's number to nine bits: a number from 549 to 1023 is kept, any other is cut by the
            // game's own instruction. What else the jump replaced is done here as it stood (a call and a store of the
            // program's given their distances anew), then back.
            for (int n = 0; n < Cuts.Length; n++)
            {
                var (_, _, _, kind, register, length) = Cuts[n];
                int site = found.CutAt[n];
                byte[] span = image.Slice(site, length).ToArray();
                ulong back = imageBase + (ulong)(site + length);
                ulong here = a.Here;
                string cut = $"cut {n}: cut", after = $"cut {n}: after";

                // Whether the register holds a mod's ability: on to `cut` where it doesn't.
                void Tell(int r)
                {
                    a.Bytes(0x81, (byte)(0xF8 + r));               // cmp r32, 549
                    a.I32(First);
                    a.Short(ShortJb, cut);
                    a.Bytes(0x81, (byte)(0xF8 + r));               // cmp r32, 1023
                    a.I32(Last);
                    a.Short(ShortJa, cut);
                }

                switch (kind)
                {
                    case 0:                                        // and ecx, 0x1FF
                        Tell(register);
                        a.Near(back);
                        a.Label(cut);
                        a.Bytes(span);
                        break;
                    case 1:                                        // and ecx, esi; call the info
                        Tell(register);
                        a.Short(0xEB, after);
                        a.Label(cut);
                        a.Bytes(span.AsSpan(0, 2).ToArray());
                        a.Label(after);
                        a.Call(back + (ulong)(long)BinaryPrimitives.ReadInt32LittleEndian(span.AsSpan(3)));
                        break;
                    case 2:                                        // and eax, esi; mov [a dword of the program], eax
                        Tell(register);
                        a.Short(0xEB, after);
                        a.Label(cut);
                        a.Bytes(span.AsSpan(0, 2).ToArray());
                        a.Label(after);
                        a.Bytes(span[2], span[3]);
                        a.Rip(back + (ulong)(long)BinaryPrimitives.ReadInt32LittleEndian(span.AsSpan(4)));
                        break;
                    case 3:                                        // and si, [rdi + 2]; mov eax, 0x1B4
                        a.Hex("50 0F B7 47 02");                   // push rax; movzx eax, word ptr [rdi + 2]
                        Tell(0);
                        a.Hex("66 8B F0 58");                      // mov si, ax; pop rax
                        a.Short(0xEB, after);
                        a.Label(cut);
                        a.Bytes(0x58);                             // pop rax
                        a.Bytes(span.AsSpan(0, 4).ToArray());
                        a.Label(after);
                        a.Bytes(span.AsSpan(4).ToArray());
                        break;
                    default:                                       // mov eax, 0x1FF; and edx, eax
                        a.Bytes(span.AsSpan(0, 5).ToArray());
                        Tell(register);
                        a.Near(back);
                        a.Label(cut);
                        a.Bytes(span.AsSpan(5).ToArray());
                        break;
                }
                a.Near(back);
                var bytes = new byte[length];
                for (int k = 5; k < bytes.Length; k++)
                    bytes[k] = 0x90;
                bytes[0] = 0xE9;
                BinaryPrimitives.WriteInt32LittleEndian(bytes.AsSpan(1), checked((int)((long)here - (long)(imageBase + (ulong)site + 5))));
                made.Add(new JobRoom.Change(site, bytes));
            }

            // The loader of the older text's files. Its first place (`movsxd rbx, esi`, `mov rcx, rbx`, before the call
            // that gets the file's room): the same, and for the names' file (ebp, the file's number) NamesExtra more in
            // rcx; rbx, the file's size, is as the game has it.
            {
                int roomAt = found.LoaderAt[0], loadedAt = found.LoaderAt[1];
                int roomLength = Loader[0].Length, loadedLength = Loader[1].Length;
                ulong here = a.Here;
                a.Bytes(image.Slice(roomAt, roomLength).ToArray());
                a.Bytes(0x83, 0xFD, (byte)AbilityWords.NamesFile);  // cmp ebp, 8
                a.Short(ShortJne, "names: the room as asked");
                a.Hex("48 81 C1");                                  // add rcx, NamesExtra
                a.I32(AbilityWords.NamesExtra);
                a.Label("names: the room as asked");
                a.Near(imageBase + (ulong)(roomAt + roomLength));
                Jump(roomAt, roomLength, here);

                // Its second place (`mov eax, esi`, then the store of the file's size, rbx): the store, then for the
                // names' file the framework's function is called with the file's room (read from the game's pointers,
                // whose place the game's own store of it names) and its size; then the `mov eax, esi`, after the call
                // so that the loader gives what it gave.
                here = a.Here;
                a.Bytes(image.Slice(loadedAt + 2, loadedLength - 2).ToArray());
                a.Bytes(0x83, 0xFD, (byte)AbilityWords.NamesFile);  // cmp ebp, 8
                a.Short(ShortJne, "names: not the names' file");
                a.Hex("49 8B 8C EF");                               // mov rcx, [r15 + rbp*8 + the pointers]
                a.Bytes(image.Slice(roomAt + PointersAfter, 4).ToArray());
                a.Hex("8B D6 FF 15");                               // mov edx, esi; call [rip + the names' cell]
                a.Rip(at + NamesCell);
                a.Label("names: not the names' file");
                a.Bytes(image.Slice(loadedAt, 2).ToArray());
                a.Near(imageBase + (ulong)(loadedAt + loadedLength));
                Jump(loadedAt, loadedLength, here);
            }

            // (11 November) The two places that make a readied ability again from the turn order's entry: the game's
            // twenty bytes done as they stood (eax the entry's low byte from the stack, ecx it and 0x100 where the flag
            // is set); then, where the flag is set, the unit's word (its place in the entry's flags' low five bits)
            // given in ecx when it is a mod's ability with that low byte; eax made again as the game left it.
            // (1.41.2, his test 95) The unit's word is the one the turn order's writer kept for it as it wrote the
            // entry (the framework's table at TurnOrderAt), not the unit's own: while the menu is open the turn order is
            // worked out with the chosen action put in the unit and the unit's own put back after.
            {
                for (int n = 0; n < Charging.Length; n++)
                {
                    var (_, flags, length) = Charging[n];
                    int site = found.ChargingAt[n];
                    byte[] span = image.Slice(site, length).ToArray();
                    ulong here = a.Here;
                    string back = $"turn order {n}: back", pop = $"turn order {n}: pop";
                    a.Bytes(span);
                    a.Hex(flags == 0 ? "41 F6 C4 80" : "40 F6 C7 80");     // test r12b / dil, 0x80
                    a.Short(ShortJe, back);
                    a.Bytes(0x52);                                        // push rdx
                    a.Hex(flags == 0 ? "41 0F B6 D4" : "40 0F B6 D7");     // movzx edx, r12b / dil
                    a.Hex("83 E2 1F");                                    // and edx, 0x1F
                    a.Hex("83 FA");                                       // cmp edx, the last unit
                    a.Bytes((byte)(UnitCount - 1));
                    a.Short(ShortJa, pop);
                    a.Hex("48 8D 05");                                    // lea rax, [rip + the writer's table]
                    a.Rip(at + TurnOrderAt);
                    a.Hex("0F B7 04 50");                                 // movzx eax, word ptr [rax + rdx*2]
                    a.Bytes(0x5A);                                        // pop rdx
                    a.Bytes(0x3D);                                        // cmp eax, 549
                    a.I32(First);
                    a.Short(ShortJb, back);
                    a.Bytes(0x3D);                                        // cmp eax, 1023
                    a.I32(Last);
                    a.Short(ShortJa, back);
                    a.Hex("38 C8");                                       // cmp al, cl
                    a.Short(ShortJne, back);
                    a.Hex("8B C8");                                       // mov ecx, eax
                    a.Short(0xEB, back);
                    a.Label(pop);
                    a.Bytes(0x5A);                                        // pop rdx
                    a.Label(back);
                    a.Bytes(span.AsSpan(0, 7).ToArray());                 // mov eax, [rsp + 0x1B0], as the game left it
                    a.Near(imageBase + (ulong)(site + length));
                    Jump(site, length, here);
                }
            }

            // (1.41.2, his test 95) The turn order's writer: its load of the unit's readied word and the `mov edx, 0xFF`
            // after it, done as they stood, and between them the word kept for the unit (rsi is the unit's place times
            // 0x200) in the framework's table, which the four places that make an entry's ability again read.
            {
                int site = found.WriterAt;
                byte[] span = image.Slice(site, WriterLength).ToArray();
                ulong here = a.Here;
                a.Bytes(span.AsSpan(0, 8).ToArray());                     // movzx ecx, word ptr [rsi + rcx + 0x1A2]
                a.Hex("50 48 8B C6 48 C1 E8 09");                         // push rax; mov rax, rsi; shr rax, 9
                a.Hex("48 83 F8");                                        // cmp rax, the last unit
                a.Bytes((byte)(UnitCount - 1));
                a.Short(ShortJa, "writer: past the units");
                a.Hex("52 48 8D 15");                                     // push rdx; lea rdx, [rip + the table]
                a.Rip(at + TurnOrderAt);
                a.Hex("66 89 0C 42 5A");                                  // mov word ptr [rdx + rax*2], cx; pop rdx
                a.Label("writer: past the units");
                a.Bytes(0x58);                                            // pop rax
                a.Bytes(span.AsSpan(8).ToArray());                        // mov edx, 0xFF
                a.Near(imageBase + (ulong)(site + WriterLength));
                Jump(site, WriterLength, here);
            }

            // (1.41.2) The two places that make each turn order entry's ability again as a text code for the timeline's
            // list (0x7000 is added after): the game's 22 bytes done as they stood (eax the entry's low byte, cx it, and
            // 0x100 more where the entry's first byte is below 0); then, where it is, the writer's word for the entry's
            // unit given in ecx when it is a mod's ability with that low byte. rax and rdx as the game left them.
            for (int n = 0; n < Texts.Length; n++)
            {
                int site = found.TextAt[n], length = Texts[n].Length;
                byte[] span = image.Slice(site, length).ToArray();
                ulong here = a.Here;
                string back = $"text {n}: back", pop = $"text {n}: pop";
                a.Bytes(span);
                a.Hex("43 80 7C 8D 00 00");                               // cmp byte ptr [r13 + r9*4], 0
                a.Short(0x7D, back);                                      // jge: not past 255
                a.Hex("52 50");                                           // push rdx; push rax
                a.Hex("43 0F B6 54 8D 00");                               // movzx edx, byte ptr [r13 + r9*4]
                a.Hex("83 E2 1F 83 FA");                                  // and edx, 0x1F; cmp edx, the last unit
                a.Bytes((byte)(UnitCount - 1));
                a.Short(ShortJa, pop);
                a.Hex("48 8D 05");                                        // lea rax, [rip + the writer's table]
                a.Rip(at + TurnOrderAt);
                a.Hex("0F B7 04 50");                                     // movzx eax, word ptr [rax + rdx*2]
                a.Bytes(0x3D);                                            // cmp eax, 549
                a.I32(First);
                a.Short(ShortJb, pop);
                a.Bytes(0x3D);                                            // cmp eax, 1023
                a.I32(Last);
                a.Short(ShortJa, pop);
                a.Hex("3A 04 24");                                        // cmp al, byte ptr [rsp] (the entry's low byte)
                a.Short(ShortJne, pop);
                a.Hex("8B C8");                                           // mov ecx, eax
                a.Label(pop);
                a.Hex("58 5A");                                           // pop rax; pop rdx
                a.Label(back);
                a.Near(imageBase + (ulong)(site + length));
                Jump(site, length, here);
            }

            // (1.41.2, his test 95) The battle menu's confirm: a chosen word with the text code 0x7000 and a mod's number
            // in its eleven bits gives that number; any other word is cut to nine bits as the game cuts it. Only r8
            // changes (and the flags, which nothing after reads before setting them again).
            {
                int site = found.MenuCutAt;
                byte[] span = image.Slice(site, MenuCutLength).ToArray();
                ulong here = a.Here;
                a.Hex("50 44 89 C0");                                     // push rax; mov eax, r8d
                a.Hex("25 00 F8 00 00 3D 00 70 00 00");                   // and eax, 0xF800; cmp eax, 0x7000
                a.Short(ShortJne, "menu: the game's");
                a.Hex("44 89 C0 25 FF 07 00 00");                         // mov eax, r8d; and eax, 0x7FF
                a.Bytes(0x3D);                                            // cmp eax, 549
                a.I32(First);
                a.Short(ShortJb, "menu: the game's");
                a.Bytes(0x3D);                                            // cmp eax, 1023
                a.I32(Last);
                a.Short(ShortJa, "menu: the game's");
                a.Hex("41 89 C0 58");                                     // mov r8d, eax; pop rax
                a.Near(imageBase + (ulong)(site + MenuCutLength));
                a.Label("menu: the game's");
                a.Bytes(0x58);                                            // pop rax
                a.Bytes(span);                                            // and r8d, 0x1FF
                a.Near(imageBase + (ulong)(site + MenuCutLength));
                Jump(site, MenuCutLength, here);
            }

            // (1.41.1, his test 94) The tabs' filters of a skillset's abilities: the word (read through its register,
            // or a copy of the register holding it) in r9, kept on the stack; a number from 549 to 1023 compared as 1,
            // inside the action tab's range and below every other tab's; then the game's two compares and jumps on it,
            // to the store of 0 or the step to the next word. The word stays as it is.
            for (int n = 0; n < Filters.Length; n++)
            {
                var (_, word, register, width, low, high, drop, keep) = Filters[n];
                int site = found.FilterAt[n];
                ulong here = a.Here;
                string game = $"tab {n}: the game's", dropped = $"tab {n}: drop", kept = $"tab {n}: keep";
                a.Hex("41 51");                                           // push r9
                if (word == 0)
                    a.Bytes(0x44, 0x0F, 0xBF, (byte)(0x08 | register));   // movsx r9d, word ptr [register]
                else
                    a.Bytes(0x45, 0x8B, (byte)(0xC8 | (register & 7)));   // mov r9d, r8d
                a.Hex("41 81 F9");                                        // cmp r9d, 549
                a.I32(First);
                a.Short(ShortJl, game);
                a.Hex("41 81 F9");                                        // cmp r9d, 1023
                a.I32(Last);
                a.Short(ShortJg, game);
                a.Hex("41 B9 01 00 00 00");                               // mov r9d, 1
                a.Label(game);
                foreach (var (edge, jump, to) in new[] { (low, ShortJl, dropped), (high, ShortJle, kept) })
                {
                    if (width == 16)
                        a.Bytes(0x66, 0x41, 0x39, (byte)(0xC1 | (edge << 3)));  // cmp r9w, edge
                    else
                        a.Bytes(0x44, 0x3B, (byte)(0xC8 | edge));               // cmp r9d, edge
                    a.Short(jump, to);
                }
                a.Label(dropped);
                a.Hex("41 59");                                           // pop r9
                a.Near(imageBase + (ulong)(site + drop));
                a.Label(kept);
                a.Hex("41 59");                                           // pop r9
                a.Near(imageBase + (ulong)(site + keep));
                Jump(site, 10, here);
            }

            // The jump from a place to the code here, the rest of what it replaces filled.
            void Jump(int site, int length, ulong to)
            {
                var bytes = new byte[length];
                for (int k = 5; k < length; k++)
                    bytes[k] = 0x90;
                bytes[0] = 0xE9;
                BinaryPrimitives.WriteInt32LittleEndian(bytes.AsSpan(1), checked((int)((long)to - (long)(imageBase + (ulong)site + 5))));
                made.Add(new JobRoom.Change(site, bytes));
            }

            if (a.Length > CellsAt)
                throw new InvalidOperationException($"the abilities' code is {a.Length} bytes, more than the {CellsAt} before its cells");
            changes = made;
            return a.Done();
        }

        /// <summary>Each ability's common record of 8 bytes written to its place in the longer table of the abilities'
        /// records (the table as `AbilityRecords.Fill` starts it).</summary>
        public static void Records(Span<byte> table, IList<AbilityFile.Given> given)
        {
            foreach (var g in given)
                g.Ability.Record.CopyTo(table.Slice(AbilityRecords.RecordBytes * g.Number, AbilityRecords.RecordBytes));
        }

        /// <summary>(1.41.0) The room as the framework starts it, all but its code (AbilityHooks runs this): its lists
        /// (Tables), then the longer table of the abilities' records (the game's 512 as they are, the mods' at their
        /// numbers), of their effects and of how their users move (each the program's own bytes from the game's table's
        /// start, each mod's as the game's ability it is like). An empty `gameEffects` or `gameAnimations` leaves that
        /// table as it is.</summary>
        public static void Start(Span<byte> room, ReadOnlySpan<byte> gameRecords, ReadOnlySpan<byte> gameEffects,
                                 ReadOnlySpan<byte> gameAnimations, IList<AbilityFile.Given> given,
                                 IList<(int Skillset, int Place, int Number)> places)
        {
            Tables(room, given, places);
            var records = room.Slice(RecordsAt, AbilityRecords.Bytes);
            AbilityRecords.Fill(gameRecords, records);
            Records(records, given);
            if (!gameEffects.IsEmpty)
            {
                var effects = room.Slice(EffectsAt, AbilityEffects.Bytes);
                AbilityEffects.Fill(gameEffects, effects);
                AbilityEffects.Likes(effects, given);
            }
            if (!gameAnimations.IsEmpty)
            {
                var animations = room.Slice(AnimationsAt, AbilityAnimations.Bytes);
                AbilityAnimations.Fill(gameAnimations, animations);
                AbilityAnimations.Likes(animations, given);
            }
        }

        /// <summary>The room's lists written: for each ability given, the game's ability it is like and its action
        /// record; and each place of a skillset that holds a mod's ability (a skillset, a place in it, the ability's
        /// number). The rest is left empty.</summary>
        public static void Tables(Span<byte> room, IList<AbilityFile.Given> given, IList<(int Skillset, int Place, int Number)> places)
        {
            room.Slice(LikesAt, RecordsAt - LikesAt).Clear();
            foreach (var g in given)
            {
                int n = g.Number - First;
                BinaryPrimitives.WriteUInt16LittleEndian(room.Slice(LikesAt + 2 * n, 2), (ushort)g.Ability.Like);
                g.Ability.ActionRecord().CopyTo(room.Slice(ActionsAt + ActionBytes * n, ActionBytes));
            }
            foreach (var (skillset, place, number) in places)
                if (skillset >= 0 && skillset < Skillsets && place >= 0 && place < PlacesEach)
                    BinaryPrimitives.WriteUInt16LittleEndian(room.Slice(PlacesAt + 2 * (skillset * PlacesEach + place), 2), (ushort)number);
        }
    }
}
