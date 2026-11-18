// Mod Studio Framework: (1.7.0) a mod's own place as a destination. Part of
// The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi, 27 October, after test 27: the second half of travel, a mod's own
// place somewhere Ramza goes. 1.3.0 drew a mod's place on the world map, 1.4.0
// its road, 1.5.0 travelled a mod's road between two of the game's places;
// here the place itself becomes one of the world map's. Each gets a number
// past the game's 48 (48 on, given by the helper and kept with the side
// quests' numbers, Numbers.cs, so a save standing on it finds it again;
// never a modder's choice), and the game is given what it keeps for a place
// by its number, found by reading his program (dev/research/sidequests/):
//
// - the game's places' records (the PlayStation's location records: a
//   place's picture and its menu's kind, 4 bytes a place, 44 of them) are
//   copied into memory of the helper's with room for 256 (the game's own read
//   as far as place 47 as before, the mods' places none), and the program's
//   four reads of them read the copy;
// - the world map's dots (the PlayStation's: a place's position on its map
//   among them, 52 bytes a place, the game's 43 built as the world map is set
//   up) move to the helper's memory with room for 256, the mods' places' made
//   there (a position from where Ramza stands on the map's picture, as the
//   game's own are), and all 18 of the program's instructions that reach them
//   reach them there;
// - the world map screen (its map and its frame menu) keeps a row of 24 bytes
//   for each of its 48 places (its piece, its box, its kind, a town's byte);
//   both are made bigger as the game makes them, with a row for each mod's
//   place past their end (0xF70 on: zeroed as they are made, filled as the
//   screen sets up its places' pieces, MapPieces.cs), and each of the
//   screen's reads of a place's row that a mod's place reaches (its position,
//   the cursor put on it, its distance from the cursor, the marker arrived at
//   it, the mouse on its piece, its help, the marker put on it) goes through
//   native code of the helper's that reads the game's row for the game's
//   places, the mod's row for a mod's place, and as before for anything else;
//   each such native code changes only what the instructions it stands for
//   change (the screen's callers keep registers across these calls);
// - its Town row (where Ramza's marker stands at it, its name's number, its
//   kind) and its PlaceName row (its name) are added as the game loads those
//   tables (Travel.cs's TravelTables), so the screen walks him to it and the
//   location info names it.
//
// Every change is checked against the bytes it replaces as his program has
// them, before any is made; any one not as found, and none is made (the
// places are pictures only, their roads drawn only, said). Nothing happens at
// a mod's place yet: no menu (its record has none), no battle (the random
// battles' roll has none past 42), no event.
//
// (1.7.1) The gamepad's and the keys' cursor stops at a mod's place too: the
// screen's place nearest the cursor (its loop over the 48 rows) goes on over
// the mods' rows through native code of the helper's, a place taken as the
// game takes one (its piece there, its distance from the cursor within its
// reach and the least), and the pad's focus of that place reads its row
// through native code as the screen's other reads do.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

namespace ModStudioEventSetup
{
    /// <summary>(1.7.0) A mod's own place the game goes to: its number of the world map's (48 on), where Ramza's
    /// marker stands at it on the map's picture, its name's number (PlaceName).</summary>
    public sealed class Destination
    {
        public MapPlace Place { get; }
        public int Number { get; }
        public int MarkerX { get; }
        public int MarkerY { get; }
        public int NameId => Destinations.NameIdOf(Number);

        public Destination(MapPlace place, int number)
        {
            Place = place;
            Number = number;
            (MarkerX, MarkerY) = Destinations.MarkerOf(place);
        }
    }

    /// <summary>(1.7.0) The memory a mod's places get, as it goes: the data (the places' records copied, then the
    /// dots, read and written by the game) and the native code (each stub by its site's name), each at its
    /// address.</summary>
    public sealed class DestinationMemory
    {
        public ulong DataAt { get; }
        public byte[] Data { get; }
        public ulong CodeAt { get; }
        public byte[] Code { get; }
        public Dictionary<string, int> Stubs { get; }

        public DestinationMemory(ulong dataAt, byte[] data, ulong codeAt, byte[] code, Dictionary<string, int> stubs)
        {
            DataAt = dataAt;
            Data = data;
            CodeAt = codeAt;
            Code = code;
            Stubs = stubs;
        }
    }

    public static unsafe class Destinations
    {
        /// <summary>The numbers a mod's place can have: past the game's 0 to 47, a road's place a byte (255 kept
        /// out); kept in Numbers.json under this kind.</summary>
        public const int FirstNumber = 48, LastNumber = 254;
        public const string Kind = "Places";
        /// <summary>The screen's rows of its places: at + 0x208, 24 bytes each (its piece, its box, its kind, a town's
        /// byte), 48 of them; the mods' places' rows at + 0xF70 (past the end of both its parts), so a row read at d
        /// for place p reads at d + 0x8E8 for a mod's place (0xF70 + 24 (p - 48) = 0x208 + 24 p + 0x8E8).</summary>
        public const int RowsAt = 0x208, RowSize = 24, GameRows = 48, ScreenRows = 0xF70;
        public const int RowShift = ScreenRows - RowsAt - GameRows * RowSize;
        public const int RowPiece = 0, RowBox = 8, RowKind = 0x10, RowTown = 0x14;
        /// <summary>The rows' reads by three times a place: the first a mod's place has, as an index.</summary>
        public const int FirstIndex = 3 * FirstNumber;
        /// <summary>How many places the copied records and the moved dots have room for.</summary>
        public const int Room = 256;
        /// <summary>The tables a mod's place gets rows in: Town (its marker, its name's number, its kind) and
        /// PlaceName (its name).</summary>
        public const int TownSheet = 0x34, NameSheet = 0x55;
        public const int TownRowHead = 0x34, NameRowHead = 0x14;
        /// <summary>A place's name's number, as the game's own are given (place 0 1010, 1 1020, ...).</summary>
        public const int NameIdFirst = 1010, NameIdStep = 10;
        /// <summary>Where Ramza's marker stands at a place against its middle: a town's 11 right and 37 below, a
        /// battle ground's 3 right and 19 below (mod_studio/map_roads.py's TOWN_FOOT and FOOT).</summary>
        public static readonly (int X, int Y) Foot = (3, 19), TownFoot = (11, 37);
        /// <summary>The PlayStation's map against the map's picture (its dots' positions against the Town table's
        /// marks, the game's 43 places: x 7.0484 times and 1983.37 on, y 5.7465 times and 1199.81 on).</summary>
        public const double PsxX = 7.0484, PsxOffsetX = 1983.37, PsxY = 5.7465, PsxOffsetY = 1199.81;
        /// <summary>A dot: its kind (+ 0), its position (+ 8, x and y two bytes each), its picture's state.</summary>
        public const int DotKind = 0, DotPosition = 8, DotFieldKind = 2;

        public static int NameIdOf(int number) => NameIdFirst + NameIdStep * number;

        public static (int X, int Y) MarkerOf(MapPlace place)
            => place.Town ? (place.X + TownFoot.X, place.Y + TownFoot.Y) : (place.X + Foot.X, place.Y + Foot.Y);

        /// <summary>A place's key among the numbers kept: its mod and its name.</summary>
        public static string KeyOf(MapPlace place) => $"{place.ModId}/{place.Name}";

        /// <summary>Each mod's place given its number (the one it had, else the first never given), in Reloaded-II's
        /// order; what can't be is said.</summary>
        public static List<Destination> Plan(List<MapPlace> places, Numbers numbers, List<string> said)
        {
            var planned = new List<Destination>();
            var candidates = new List<int>();
            for (int n = FirstNumber; n <= LastNumber; n++)
                candidates.Add(n);
            foreach (var place in places)
            {
                int number = numbers.Give(Kind, KeyOf(place), candidates, _ => true, out _);
                if (number < 0)
                {
                    said.Add($"{place.Name} ({place.ModName}) isn't somewhere to go: the world map has room for "
                             + $"{LastNumber - FirstNumber + 1} places past its own, all given.");
                    continue;
                }
                planned.Add(new Destination(place, number));
            }
            return planned;
        }

        /// <summary>The rows the screen gets past its end: up to the highest number given.</summary>
        public static int RowCount(List<Destination> destinations)
        {
            int most = FirstNumber - 1;
            foreach (var d in destinations)
                most = Math.Max(most, d.Number);
            return most - FirstNumber + 1;
        }

        // --- the data ---------------------------------------------------------------------------------------------

        public const int DataRecords = 0, DataDots = Room * Places.RecordSize;
        public const int DataBytes = DataDots + Room * Places.DotSize;
        /// <summary>(1.21.0) With a mod's dungeon: past the places' data, a byte a place (1 a mod's dungeon), then two
        /// slots of the helper's (8 bytes each: what a floor chosen asks, what the Deep's list's read of a floor's row
        /// asks), each at first the native code's `zero` (no battle, the game's row) until the side quests' hooks are
        /// made.</summary>
        public const int DungeonData = DataBytes, DungeonSlots = DungeonData + Room, FloorSlot = DungeonSlots,
                         RowSlot = DungeonSlots + 8, DungeonDataBytes = DungeonSlots + 16;
        /// <summary>(1.21.0) A dungeon's record's menu (Midlight's Deep's: 2; only the entries' function reads it, and
        /// the helper's hook of it answers for a mod's dungeon first).</summary>
        public const byte MenuDungeon = 2;

        /// <summary>(1.21.0) Whether the places' memory has a dungeon's part: a mod's dungeon among them, its sites
        /// found.</summary>
        public static bool HasDungeons(Places places, List<Destination> destinations)
            => places.Dungeons && destinations.Exists(d => d.Place.Dungeon);

        /// <summary>The data the places get: the records (the program's as far as place 47, as it reads them, then
        /// none) and the dots (none: the game builds its own 43; a mod's place's kind and position).</summary>
        public static byte[] Data(ReadOnlySpan<byte> image, Places places, List<Destination> destinations)
        {
            bool dungeons = HasDungeons(places, destinations);
            var data = new byte[dungeons ? DungeonDataBytes : DataBytes];
            image.Slice(places.LocationRecords, Places.GameRecordBytes).CopyTo(data.AsSpan(DataRecords));
            foreach (var d in destinations)
            {
                // (1.18.0) A town with a menu of its own: its record's menu a town's (1), and its picture set its art
                // town's (the game's towns' 1 to 15, read as its menu opens: 0x344BB0), as the game's towns' records;
                // (1.19.0) with its own art, none (0: the opening loads none).
                if (d.Place.Town && d.Place.Menu != null)
                {
                    int record = DataRecords + d.Number * Places.RecordSize;
                    data[record + Places.RecordPicture] = d.Place.Menu.ArtPicture.Length > 0 ? (byte)0
                        : image[places.LocationRecords + d.Place.Menu.Art * Places.RecordSize + Places.RecordPicture];
                    data[record + Places.RecordMenu] = MenuTown;
                }
                // (1.21.0) A dungeon: its record's menu the Deep's, no art; its byte of the dungeons' set.
                if (dungeons && d.Place.Dungeon)
                {
                    data[DataRecords + d.Number * Places.RecordSize + Places.RecordMenu] = MenuDungeon;
                    data[DungeonData + d.Number] = 1;
                }
                int dot = DataDots + d.Number * Places.DotSize;
                BinaryPrimitives.WriteInt32LittleEndian(data.AsSpan(dot + DotKind), DotFieldKind);
                var (x, y) = DotOf(d);
                BinaryPrimitives.WriteInt16LittleEndian(data.AsSpan(dot + DotPosition), x);
                BinaryPrimitives.WriteInt16LittleEndian(data.AsSpan(dot + DotPosition + 2), y);
            }
            return data;
        }

        /// <summary>A mod's place's position on the PlayStation's map, from where Ramza stands at it.</summary>
        public static (short X, short Y) DotOf(Destination d)
            => ((short)Math.Round((d.MarkerX - PsxOffsetX) / PsxX, MidpointRounding.AwayFromZero),
                (short)Math.Round((d.MarkerY - PsxOffsetY) / PsxY, MidpointRounding.AwayFromZero));

        // --- the native code --------------------------------------------------------------------------------------

        /// <summary>Native code being written at a known address: bytes, short jumps to its own labels, near jumps to
        /// anywhere within 2 GB.</summary>
        internal sealed class Asm
        {
            readonly ulong _at;
            readonly List<byte> _bytes = new List<byte>();
            readonly Dictionary<string, int> _labels = new Dictionary<string, int>();
            readonly List<(int At, string Label)> _shorts = new List<(int At, string Label)>();
            /// <summary>(1.23.0) Near jumps to its own labels: where each distance goes, and to which.</summary>
            readonly List<(int At, string Label)> _nears = new List<(int At, string Label)>();

            public Asm(ulong at) => _at = at;
            public int Length => _bytes.Count;
            public ulong Here => _at + (ulong)_bytes.Count;

            public void Bytes(params byte[] b) => _bytes.AddRange(b);
            public void Hex(string text)
            {
                foreach (var p in text.Split(' ', StringSplitOptions.RemoveEmptyEntries))
                    _bytes.Add(Convert.ToByte(p, 16));
            }
            public void I32(long value)
            {
                var b = new byte[4];
                BinaryPrimitives.WriteInt32LittleEndian(b, checked((int)value));
                _bytes.AddRange(b);
            }
            public void Label(string name) => _labels[name] = _bytes.Count;
            /// <summary>(1.21.0) A rip-relative operand's distance to `target` (`after` bytes of the instruction
            /// following it, an immediate).</summary>
            public void Rip(ulong target, int after = 0) => I32((long)target - (long)(Here + 4 + (ulong)after));
            /// <summary>(1.7.1) A call (E8) of an address within 2 GB.</summary>
            public void Call(ulong target)
            {
                _bytes.Add(0xE8);
                I32((long)target - (long)(Here + 4));
            }
            /// <summary>A short jump's code (72 jb, 73 jae) to a label of this code.</summary>
            public void Short(byte code, string label)
            {
                _bytes.Add(code);
                _shorts.Add((_bytes.Count, label));
                _bytes.Add(0);
            }
            /// <summary>A near jump (E9) or condition (0F 8x) to an address.</summary>
            public void Near(ulong target, byte code = 0xE9)
            {
                if (code != 0xE9)
                    _bytes.Add(0x0F);
                _bytes.Add(code);
                I32((long)target - (long)(Here + 4));
            }
            /// <summary>(1.23.0) A near jump (E9) or condition (0F 8x) to a label of this code.</summary>
            public void NearTo(string label, byte code = 0xE9)
            {
                if (code != 0xE9)
                    _bytes.Add(0x0F);
                _bytes.Add(code);
                _nears.Add((_bytes.Count, label));
                _bytes.AddRange(new byte[4]);
            }
            public byte[] Done()
            {
                foreach (var (at, label) in _shorts)
                {
                    // (1.55.0) A short jump back (the game jobs' scan of the second list) is a negative byte: the
                    // distance is held to a byte's reach, then written as its byte.
                    int distance = _labels[label] - (at + 1);
                    if (distance < sbyte.MinValue || distance > sbyte.MaxValue)
                        throw new InvalidOperationException($"a short jump to {label} can't reach it ({distance} bytes)");
                    _bytes[at] = unchecked((byte)(sbyte)distance);
                }
                foreach (var (at, label) in _nears)
                {
                    int distance = _labels[label] - (at + 4);
                    for (int n = 0; n < 4; n++)
                        _bytes[at + n] = (byte)(distance >> (8 * n));
                }
                return _bytes.ToArray();
            }
        }

        const byte Jbe = 0x86, Jae = 0x83, Jb = 0x82, Jl = 0x8C, ShortJb = 0x72, ShortJae = 0x73, ShortJe = 0x74,
                   ShortJbe = 0x76, ShortJge = 0x7D, Je = 0x84, ShortJmp = 0xEB, ShortJne = 0x75, Jge = 0x8D, Jle = 0x8E;

        /// <summary>A bound of the screen's (its compare of a place with 47, then ja): for the game's places and a
        /// mod's (48 to 48 + rows - 1) on to `inside`, else to `outside` (where its ja goes). `compare` is the
        /// compare with 47 as it stands (3 or 4 bytes, an imm8), `compareMore` the same with an imm32 following.</summary>
        static void Bound(Asm a, string compare, string compareMore, int rows, ulong inside, ulong outside)
        {
            a.Hex(compare);
            a.Near(inside, Jbe);
            a.Hex(compareMore);
            a.I32(FirstNumber + rows);
            a.Near(inside, Jb);
            a.Near(outside);
        }

        /// <summary>A read of a place's row by three times its number (`index`'s compare with an imm32 as `compare`):
        /// `read` with its distance + RowShift for a mod's place, `read` as it stands for anything else; then on to
        /// `back`. `first` the index of the first mod's place (its fold of 0x16 for the marker's).</summary>
        static void RowRead(Asm a, string compare, string read, int distance, int rows, ulong back, int first = FirstIndex,
                            string tail = "")
        {
            a.Hex(compare);
            a.I32(first);
            a.Short(ShortJb, "as");
            a.Hex(compare);
            a.I32(first + 3 * rows);
            a.Short(ShortJae, "as");
            a.Hex(read);
            a.I32(distance + RowShift);
            a.Hex(tail);
            a.Near(back);
            a.Label("as");
            a.Hex(read);
            a.I32(distance);
            a.Hex(tail);
            a.Near(back);
        }

        static ulong Target(ReadOnlySpan<byte> image, ulong imageBase, int at, int length)
            => imageBase + (ulong)(at + length + BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at + length - 4, 4)));

        /// <summary>The native code, at `at`, for a program at `imageBase` with `rows` rows past the screen's end:
        /// each stub by its site's name (Sites), and the bytes.</summary>
        public static byte[] Code(ReadOnlySpan<byte> image, Places places, ulong imageBase, ulong at, int rows,
                                  out Dictionary<string, int> stubs, ulong dataAt = 0, bool dungeons = false)
        {
            ulong P(int rva) => imageBase + (ulong)rva;
            // Where each bound's ja goes, as the program has it (read before any native code is written).
            int pos = places.PlacePosition, cursor = places.CursorAtPlace + Places.CursorBound,
                cursorRead = places.CursorAtPlace + Places.CursorRead, bound = places.DistanceBound,
                read = places.DistanceRead, arrived = places.ArrivedFirst, again = places.ArrivedSecond,
                help = places.HelpBound, kind = places.HelpKind, kindAgain = places.HelpKindAgain,
                marker = places.MarkerPlace, test = places.MarkerPlace + Places.MarkerPlaceTest;
            ulong positionEnd = Target(image, imageBase, pos + 4, 6);
            ulong cursorEnd = P(cursor + Places.CursorBoundLength + (sbyte)image[cursor + 5]);
            ulong distanceEnd = Target(image, imageBase, bound + 3, 6);
            ulong helpEnd = Target(image, imageBase, help + 3, 6);
            ulong markerEnd = Target(image, imageBase, marker + 3, 6);
            ulong ctor = P(places.ScreenCtor);
            var pieceSites = new int[Places.PieceEventsReads.Length];
            for (int n = 0; n < pieceSites.Length; n++)
                pieceSites[n] = places.PieceEvents + Places.PieceEventsReads[n];

            var made = new Dictionary<string, int>();
            var all = new List<byte>();
            void Stub(string name, Action<Asm> write)
            {
                while (all.Count % 16 != 0)
                    all.Add(0xCC);
                var a = new Asm(at + (ulong)all.Count);
                write(a);
                made[name] = all.Count;
                all.AddRange(a.Done());
            }
            Stub("position", a =>
            {
                a.Hex("41 83 F8 2F");                                   // cmp r8d, 0x2f
                a.Near(P(pos + Places.PlacePositionBody), Jbe);         // jbe: the game's place, as it was
                a.Hex("41 81 F8");                                      // cmp r8d, 48 + rows
                a.I32(FirstNumber + rows);
                a.Near(positionEnd, Jae);                               // jae: none, as it was (its end)
                a.Hex("49 63 C0");                                      // movsxd rax, r8d
                a.Hex("48 83 C0");                                      // add rax, 0x16 + RowShift / 24
                a.Bytes(checked((byte)(0x16 + RowShift / RowSize)));
                a.Hex("4C 8D 04 40");                                   // lea r8, [rax + rax*2]
                a.Near(P(pos + Places.PlacePositionLoad));              // jmp: its box read, past the screen's end
            });
            Stub("cursor bound", a => Bound(a, "41 83 F9 2F", "41 81 F9", rows, P(cursor + Places.CursorBoundLength),
                                            cursorEnd));
            Stub("cursor row", a =>
            {
                a.Hex("4B 8D 04 49");                                   // lea rax, [r9 + r9*2], as it was
                RowRead(a, "48 3D", "80 BC C1", 0x21C, rows, P(cursorRead + Places.CursorReadLength), tail: "00");
            });
            Stub("distance bound", a => Bound(a, "83 FB 2F", "81 FB", rows, P(bound + Places.BoundLength), distanceEnd));
            Stub("distance row", a =>
            {
                a.Hex("48 8D 0C 5B");                                   // lea rcx, [rbx + rbx*2], as it was
                RowRead(a, "48 81 F9", "8A 84 CF", 0x21C, rows, P(read + Places.DistanceReadLength));
            });
            Stub("arrived row", a => RowRead(a, "48 81 FA", "48 8B 84 D3", RowsAt, rows, P(arrived + Places.RowReadLength)));
            Stub("arrived row again", a => RowRead(a, "48 81 F9", "48 8B 84 CB", RowsAt, rows,
                                                   P(again + Places.RowReadLength)));
            for (int n = 0; n < pieceSites.Length; n++)
            {
                int site = pieceSites[n];
                bool byRbx = n < 2;
                Stub($"piece row {n + 1}", a => RowRead(a, byRbx ? "48 81 FB" : "48 81 FE",
                                                       byRbx ? "48 8B 8C DF" : "48 8B 8C F7", RowsAt, rows,
                                                       P(site + Places.RowReadLength)));
            }
            Stub("help bound", a => Bound(a, "83 FE 2F", "81 FE", rows, P(help + Places.BoundLength), helpEnd));
            Stub("help row", a => RowRead(a, "48 81 F9", "44 8B 84 CF", 0x218, rows, P(kind + Places.RowReadLength)));
            Stub("help row again", a => RowRead(a, "48 81 F9", "8B 94 CF", 0x218, rows,
                                                P(kindAgain + Places.HelpKindAgainLength)));
            Stub("marker bound", a => Bound(a, "83 3F 2F", "81 3F", rows, P(marker + Places.BoundLength), markerEnd));
            Stub("marker row", a => RowRead(a, "48 3D", "48 83 BC C3", 0, rows,
                                            P(test + Places.MarkerPlaceTestLength), 3 * (FirstNumber + 0x16), "00"));
            Stub("rows zeroed", a =>
            {
                a.Hex("51 57");                                         // push rcx; push rdi
                a.Hex("48 8D B9");                                      // lea rdi, [rcx + 0xF70]
                a.I32(ScreenRows);
                a.Hex("31 C0");                                         // xor eax, eax
                a.Bytes(0xB9);                                          // mov ecx, the rows' quadwords
                a.I32(rows * RowSize / 8);
                a.Hex("F3 48 AB");                                      // rep stosq
                a.Hex("5F 59");                                         // pop rdi; pop rcx
                a.Near(ctor);                                           // jmp: the screen's constructor
            });
            // (1.7.1) The place nearest the cursor: after the game's 48 rows, the mods' (r15 the screen, ebx the place,
            // rbp its row, edi the nearest yet, r14 where its distance goes), each whose piece is there taken as the
            // game takes a place (its distance more than 0 and less than the nearest's yet); then its return.
            int nearest = places.Nearest;
            Stub("nearest more", a =>
            {
                a.Hex("83 FB 30");                                      // cmp ebx, 0x30, as it was
                a.Near(P(nearest + Places.NearestTop), Jl);             // jl: the game's loop, as it was
                a.Hex("49 8D AF");                                      // lea rbp, [r15 + 0xF70]: the mods' rows
                a.I32(ScreenRows);
                ulong loop = a.Here;
                a.Hex("81 FB");                                         // cmp ebx, 48 + rows
                a.I32(FirstNumber + rows);
                a.Short(ShortJge, "done");
                a.Hex("48 83 7D 00 00");                                // cmp qword [rbp], 0: no piece
                a.Short(ShortJe, "next");
                a.Hex("8B D3");                                         // mov edx, ebx
                a.Hex("49 8B CF");                                      // mov rcx, r15
                a.Call(P(places.Distance));                             // call: its distance from the cursor
                a.Hex("0F 57 C9");                                      // xorps xmm1, xmm1
                a.Hex("0F 2F C1");                                      // comiss xmm0, xmm1
                a.Short(ShortJbe, "next");                              // jbe: not within its reach
                a.Hex("83 FF FF");                                      // cmp edi, -1
                a.Short(ShortJe, "take");                               // je: none nearer yet
                a.Hex("F3 41 0F 10 0E");                                // movss xmm1, [r14]
                a.Hex("0F 2F C8");                                      // comiss xmm1, xmm0
                a.Short(ShortJbe, "next");                              // jbe: not nearer
                a.Label("take");
                a.Hex("F3 41 0F 11 06");                                // movss [r14], xmm0
                a.Hex("8B FB");                                         // mov edi, ebx
                a.Label("next");
                a.Hex("FF C3");                                         // inc ebx
                a.Hex("48 83 C5 18");                                   // add rbp, 24
                a.Near(loop);                                           // jmp: the next row
                a.Label("done");
                a.Near(P(nearest + Places.NearestReturn));              // jmp: its return, as the game's loop ends
            });
            // (1.7.1) The pad's focus of the nearest place: its three reads of the row (rdi three times the place).
            for (int n = 0; n < Places.NearestFocusReads.Length; n++)
            {
                int site = places.NearestFocus + Places.NearestFocusReads[n];
                string focusRead = n == 1 ? Places.FocusReadR8 : Places.FocusReadRax;
                Stub($"focus row {n + 1}", a => RowRead(a, "48 81 FF", focusRead, RowsAt, rows,
                                                       P(site + Places.RowReadLength)));
            }
            // (1.23.1) The PlayStation world map's name of the place arrived at (Zodi's test 52: a travel to place 69
            // stopped the game): its place plus one read as it was, a mod's place's (48 on, 49 and up) none, so its name,
            // a sprite of the game's places' only, isn't drawn; then on past it.
            Stub("arrival name", a =>
            {
                a.Hex("44 8B 1D");                                      // mov r11d, [rip + the place plus one]
                a.Rip(P(places.ArrivalNameValue));
                a.Hex("41 83 FB");                                      // cmp r11d, 48: the game's places' and none's
                a.Bytes((byte)FirstNumber);
                a.Short(ShortJbe, "game");
                a.Hex("45 31 DB");                                      // xor r11d, r11d: a mod's place's, none
                a.Label("game");
                a.Near(P(places.ArrivalName + Places.ArrivalNameLength));   // jmp: back past it
            });
            // (1.23.2) The menu's name of its place (Zodi's test 53: choosing Old Quarry, place 69, stopped the game):
            // its sprite 0x37 plus the place as it was, a mod's place's (48 on) the game's blank sprite; then the
            // instruction after it as the program has it (its record by the program's base in rdi), and on past them.
            byte[] menuKept = image.Slice(places.MenuName + Places.MenuNameKept,
                                          Places.MenuNameLength - Places.MenuNameKept).ToArray();
            Stub("menu name", a =>
            {
                a.Hex("41 8D 46");                                      // lea eax, [r14 + 0x37]: its name's sprite
                a.Bytes((byte)Places.NameSprite);
                a.Hex("41 83 FE");                                      // cmp r14d, 48: the game's places'
                a.Bytes((byte)FirstNumber);
                a.Short(ShortJb, "game");
                a.Bytes(0xB8);                                          // mov eax, 122: a mod's place's, the blank
                a.I32(Places.BlankSprite);
                a.Label("game");
                a.Bytes(menuKept);                                      // mov dword [r10 + rdi + ...], 8: as it was
                a.Near(P(places.MenuName + Places.MenuNameLength));     // jmp: back past them
            });
            if (dungeons)
                DungeonStubs(Stub, image, places, P, dataAt);
            // (1.23.0) The world map's location list: the mods' places after the game's (Zodi's test 49).
            if (places.Locations && places.ListEnd >= 0)
                Stub("list more", a => ListStub(a, places, P, rows));
            while (all.Count % 16 != 0)
                all.Add(0xCC);
            stubs = made;
            return all.ToArray();
        }

        /// <summary>(1.21.0) A mod's dungeon's native code (Zodi's list, his seventh), each place tested as a mod's
        /// dungeon by its byte of the data's set (48 to 255, 1):
        /// - "dungeon block": the settlement menu's opening's test of the Deep (r14d the place): the Deep's own on as it
        ///   was, a town's on to its path; a mod's dungeon the Deep's list's block (rbp + 0x17) of its own: its floors'
        ///   count as the Deep's is read, no floor done or new (the Deep's bytes left alone), the cursor on its first,
        ///   then on to the block's copy to the list;
        /// - "dungeon screen": its screen the Deep's (9) for the Deep and a mod's dungeon (r13d), rcx kept;
        /// - "dungeon handler": called in place of the choosing's test of the Deep, the flags as it leaves them (ZF the
        ///   Deep or a mod's dungeon), every register kept;
        /// - "floor": called in place of the floor chosen's ask of the place's chains (ecx the place): the game's
        ///   places to the chains as they were; a mod's dungeon asks the floor slot (its battle picked and kept where
        ///   the roll keeps its own, 1; else 0, the game's "nothing" said), then the random battle's setup as a battle
        ///   ground's yes, and out as the floor code goes out (its return dropped); (1.25.0) the slot's 2, a quest's
        ///   event loaded (a start waiting at the floor), the world map's start of an event in place of the setup;
        /// - "row": called in place of the Deep's list's reads of a floor's row (ecx its sheet, edx its key): at a mod's
        ///   dungeon the row slot's row (0: the game's), else the game's row as it was; rcx and rdx kept;
        /// - "zero": the slots' first answer (0).</summary>
        static void DungeonStubs(Action<string, Action<Asm>> stub, ReadOnlySpan<byte> image, Places places,
                                 Func<int, ulong> p, ulong dataAt)
        {
            ulong table = dataAt + DungeonData, floorSlot = dataAt + FloorSlot, rowSlot = dataAt + RowSlot;
            ulong place = p(places.CurrentPlace);
            var count = image.Slice(places.DungeonBlock + Places.DungeonBlockLength, Places.DungeonCountLength).ToArray();
            int first = FirstNumber;
            stub("dungeon block", a =>
            {
                a.Hex("41 83 FE 16");                                   // cmp r14d, 0x16: the Deep
                a.Near(p(places.DungeonBlock + Places.DungeonBlockLength), Je);
                a.Hex("41 81 FE");                                      // cmp r14d, 48
                a.I32(first);
                a.Near(p(places.DungeonTown), Jb);                      // jb: a town's path, as it was
                a.Hex("41 81 FE");                                      // cmp r14d, 256
                a.I32(Room);
                a.Near(p(places.DungeonTown), Jae);
                a.Hex("51 48 8D 0D");                                   // push rcx; lea rcx, [rip + the set]
                a.Rip(table);
                a.Hex("42 80 3C 31 00 59");                             // cmp byte [rcx + r14], 0; pop rcx
                a.Near(p(places.DungeonTown), Je);                      // je: not a dungeon, a town's path
                a.Bytes(count);                                         // mov r8d, [rbx + rdi + count]: its floors'
                a.Hex("44 89 45 17");                                   // mov [rbp + 0x17], r8d
                a.Hex("33 C0 48 89 45 1B 66 89 45 23");                 // the ten floors' bytes 0
                a.Hex("C6 45 25 00 C6 45 26 FF");                       // the cursor's floor 0; none new (0xFF)
                a.Near(p(places.DungeonCopy));                          // jmp: the block copied to the list
            });
            stub("dungeon screen", a =>
            {
                a.Hex("B8 09 00 00 00");                                // mov eax, 9: the Deep's screen
                a.Hex("41 83 FE 16");                                   // cmp r14d, 0x16
                a.Short(ShortJe, "deep");
                a.Hex("41 81 FE");                                      // cmp r14d, 48
                a.I32(first);
                a.Short(ShortJb, "back");
                a.Hex("41 81 FE");                                      // cmp r14d, 256
                a.I32(Room);
                a.Short(ShortJae, "back");
                a.Hex("51 48 8D 0D");                                   // push rcx; lea rcx, [rip + the set]
                a.Rip(table);
                a.Hex("42 80 3C 31 00 59");                             // cmp byte [rcx + r14], 0; pop rcx
                a.Short(ShortJe, "back");
                a.Label("deep");
                a.Hex("44 8B E8");                                      // mov r13d, eax
                a.Label("back");
                a.Near(p(places.DungeonScreen + Places.DungeonScreenLength));
            });
            stub("dungeon handler", a =>
            {
                a.Hex("50 8B 05");                                      // push rax; mov eax, [rip + the place]
                a.Rip(place);
                a.Hex("83 F8 16");                                      // cmp eax, 0x16
                a.Short(ShortJe, "done");                               // ZF: the Deep
                a.Hex("3D");                                            // cmp eax, 48
                a.I32(first);
                a.Short(ShortJb, "no");
                a.Hex("3D");                                            // cmp eax, 256
                a.I32(Room);
                a.Short(ShortJae, "no");
                a.Hex("51 48 8D 0D");                                   // push rcx; lea rcx, [rip + the set]
                a.Rip(table);
                a.Hex("80 3C 01 00 59");                                // cmp byte [rcx + rax], 0; pop rcx
                a.Short(ShortJe, "no");
                a.Hex("39 C0");                                         // cmp eax, eax: ZF, a mod's dungeon
                a.Short(ShortJmp, "done");
                a.Label("no");
                a.Hex("85 E4");                                         // test esp, esp: no ZF
                a.Label("done");
                a.Hex("58 C3");                                         // pop rax; ret
            });
            stub("floor", a =>
            {
                a.Hex("81 F9");                                         // cmp ecx, 48
                a.I32(first);
                a.Short(ShortJb, "game");
                a.Hex("81 F9");                                         // cmp ecx, 256
                a.I32(Room);
                a.Short(ShortJae, "game");
                a.Hex("48 8D 05");                                      // lea rax, [rip + the set]
                a.Rip(table);
                a.Hex("80 3C 08 00");                                   // cmp byte [rax + rcx], 0
                a.Short(ShortJne, "dungeon");
                // (1.25.0) The game's places' way first, so the short jumps to it stay near.
                a.Label("game");
                a.Near(p(places.Chains));                               // jmp: the place's chains, as they were
                a.Label("dungeon");
                a.Hex("48 83 EC 28 FF 15");                             // sub rsp, 0x28; call [rip + the floor slot]
                a.Rip(floorSlot);
                a.Hex("48 83 C4 28 85 C0");                             // add rsp, 0x28; test eax, eax
                a.Short(ShortJe, "none");
                if (places.FloorStarts)
                {
                    a.Hex("83 F8 02");                                  // cmp eax, 2: a quest's event loaded
                    a.Short(ShortJe, "event");
                }
                a.Hex("48 83 EC 28");                                   // sub rsp, 0x28
                a.Call(p(places.RandomSetup));                          // call: the random battle's setup
                if (places.InstantBattles)
                {
                    // (1.23.0) Its transition (the world map's last command, 0x23) of kind 2: it leaves the world map
                    // at once, no white flash (Zodi's test 49: "straight to black", as the Deep's). eax, the setup's
                    // answer, is kept: it is the floor code's own as it goes out.
                    a.Hex("8B 0D");                                     // mov ecx, [rip + the count]
                    a.Rip(p(places.TransitionCount));
                    a.Hex("83 E9 01");                                  // sub ecx, 1
                    a.Short(ShortJb, "flash");                          // jb: none queued
                    a.Hex("48 63 C9 48 8D 15");                         // movsxd rcx, ecx; lea rdx, [rip + the list]
                    a.Rip(p(places.TransitionCommands));
                    a.Hex("83 3C 8A");                                  // cmp dword [rdx + rcx*4], 0x23
                    a.Bytes(Places.TransitionCommand);
                    a.Short(ShortJne, "flash");                         // jne: not the transition
                    a.Hex("48 6B C9");                                  // imul rcx, rcx, 0x5C
                    a.Bytes(Places.TransitionRecord);
                    a.Hex("48 8D 15");                                  // lea rdx, [rip + the kinds]
                    a.Rip(p(places.TransitionKinds));
                    a.Hex("C7 04 0A");                                  // mov dword [rdx + rcx], 2
                    a.I32(Places.InstantTransition);
                    a.Label("flash");
                }
                a.Hex("48 83 C4 30");                                   // add rsp, 0x30: its return dropped too
                a.Near(p(places.FloorOut));                             // jmp: out as the floor code goes out
                if (places.FloorStarts)
                {
                    // (1.25.0) A quest's start waiting at the floor, its conditions holding: the event the slot loaded
                    // (and its kind, at once) started as a place starts the event its chains loaded, the first of
                    // them (ecx 0); then out as the floor code goes out, its return dropped.
                    a.Label("event");
                    a.Hex("48 83 EC 28 31 C9");                         // sub rsp, 0x28; xor ecx, ecx
                    a.Call(p(places.EventStart));                       // call: the world map's start of an event
                    a.Hex("48 83 C4 30");                               // add rsp, 0x30
                    a.Near(p(places.FloorOut));                         // jmp: out as the floor code goes out
                }
                a.Label("none");
                a.Hex("31 C0 C3");                                      // xor eax, eax; ret: nothing (the game says)
            });
            stub("row", a =>
            {
                a.Hex("51 52 48 83 EC 28 8B 05");                       // push rcx; push rdx; sub rsp, 0x28; mov eax,
                a.Rip(place);                                           // [rip + the place]
                a.Hex("3D");                                            // cmp eax, 48
                a.I32(first);
                a.Short(ShortJb, "game");
                a.Hex("3D");                                            // cmp eax, 256
                a.I32(Room);
                a.Short(ShortJae, "game");
                a.Hex("48 8D 0D");                                      // lea rcx, [rip + the set]
                a.Rip(table);
                a.Hex("80 3C 01 00");                                   // cmp byte [rcx + rax], 0
                a.Short(ShortJe, "game");
                a.Hex("8B C8 FF 15");                                   // mov ecx, eax (edx the key); call [rip + the
                a.Rip(rowSlot);                                         // row slot]
                a.Hex("48 85 C0");                                      // test rax, rax
                a.Short(ShortJe, "game");
                a.Hex("48 83 C4 28 5A 59 C3");                          // add rsp, 0x28; pop rdx; pop rcx; ret
                a.Label("game");
                a.Hex("48 83 C4 28 5A 59");                             // add rsp, 0x28; pop rdx; pop rcx
                a.Near(p(places.RowLookup));                            // jmp: the game's row, as it was
            });
            stub("zero", a => a.Hex("31 C0 C3"));                       // xor eax, eax; ret
        }

        /// <summary>(1.23.0) The world map's location list, after the game's loop over its places 0 to 47 (Zodi, test 49:
        /// "Our new modded in locations are not appearing in the location list"): each mod's place shown on the map (its
        /// piece in the main map's row, 48 on) with a Town row gets an entry as the game makes its own (0x40 bytes at
        /// rsp + 0x40: its place, its sort, the story's next place 3 or a midway one 2, the third mark 1 as a place the
        /// game marks no other way, its Poachers' Den as the game tests its own, r13b its variable's test, Ramza's place),
        /// put last in its tab's list (its Town row's kind, above 2 the first) or the list grown by the game's own; then
        /// the instruction it stands for (the UI's root read) and back. rbx (the game's loop's place) and rsi, rdi, r14
        /// are the function's own past its loop (its end restores them); r12 (3, the tabs the sort goes over), r13 and
        /// rbp are kept, rsp as the function's (16 bytes aligned: each call its own shadow space).</summary>
        static void ListStub(Asm a, Places places, Func<int, ulong> p, int rows)
        {
            a.Hex("48 8B 05");                                          // mov rax, [rip + the UI's root]
            a.Rip(p(places.UiRoot));
            a.Hex("48 85 C0");                                          // test rax, rax
            a.NearTo("done", Je);
            a.Hex("48 8B 40");                                          // mov rax, [rax + 0x10]
            a.Bytes((byte)Places.UiFirst);
            a.Hex("48 8B 80");                                          // mov rax, [rax + 0xA0]: the frame
            a.I32(Places.UiMenus);
            a.Hex("48 85 C0");                                          // test rax, rax
            a.NearTo("done", Je);
            a.Hex("48 8B 70");                                          // mov rsi, [rax + 0x40]: the main map
            a.Bytes((byte)Places.FrameMap);
            a.Hex("48 8B 78");                                          // mov rdi, [rax + 0x50]: the list
            a.Bytes((byte)Places.FrameList);
            a.Hex("48 85 F6");                                          // test rsi, rsi
            a.NearTo("done", Je);
            a.Hex("48 85 FF");                                          // test rdi, rdi
            a.NearTo("done", Je);
            a.Bytes(0xBB);                                              // mov ebx, 48: the mods' places
            a.I32(FirstNumber);
            a.Label("loop");
            a.Hex("81 FB");                                             // cmp ebx, 48 + rows
            a.I32(FirstNumber + rows);
            a.NearTo("done", Jge);
            // Shown on the map: its piece in the main map's row (the mods' rows from ScreenRows, 24 bytes each).
            a.Hex("8D 43");                                             // lea eax, [rbx - 48]
            a.Bytes(unchecked((byte)(sbyte)(-FirstNumber)));
            a.Hex("6B C0");                                             // imul eax, eax, 24
            a.Bytes((byte)RowSize);
            a.Hex("48 83 BC 06");                                       // cmp qword [rsi + rax + ScreenRows], 0
            a.I32(ScreenRows + RowPiece);
            a.Bytes(0x00);
            a.NearTo("next", Je);
            // Its Town row (sheet 0x34), as the game looks its own up.
            a.Hex("8B D3");                                             // mov edx, ebx
            a.Bytes(0xB9);                                              // mov ecx, 0x34
            a.I32(TownSheet);
            a.Call(p(places.ListRowLookup));                            // call: the row lookup
            a.Hex("48 85 C0");                                          // test rax, rax
            a.NearTo("next", Je);
            a.Hex("4C 8B F0");                                          // mov r14, rax: its row
            // The entry, at rsp + 0x40 as the game's: zeros, then its fields.
            a.Hex("0F 57 C0");                                          // xorps xmm0, xmm0
            foreach (int at in new[] { 0, 0x10, 0x20, 0x30 })
            {
                a.Hex("0F 11 44 24");                                   // movups [rsp + 0x40 + at], xmm0
                a.Bytes((byte)(Places.EntryAt + at));
            }
            a.Hex("3B 5C 24");                                          // cmp ebx, [rsp + 0x30]: the story's next place
            a.Bytes((byte)Places.NextPlaceAt);
            a.Short(ShortJne, "midway");
            a.Hex("C6 44 24");                                          // mov byte [rsp + 0x73], 3
            a.Bytes((byte)(Places.EntryAt + Places.EntryNext), 3);
            a.Short(ShortJmp, "marked");
            a.Label("midway");
            a.Hex("3B 5C 24");                                          // cmp ebx, [rsp + 0x34]: a midway place
            a.Bytes((byte)Places.MidwayPlaceAt);
            a.Short(ShortJne, "marked");
            a.Hex("C6 44 24");                                          // mov byte [rsp + 0x73], 2
            a.Bytes((byte)(Places.EntryAt + Places.EntryNext), 2);
            a.Label("marked");
            a.Hex("89 5C 24");                                          // mov [rsp + 0x74], ebx: its place
            a.Bytes((byte)(Places.EntryAt + Places.EntryPlace));
            a.Hex("41 8B 46");                                          // mov eax, [r14 + 0x20]: its sort
            a.Bytes((byte)TownSort);
            a.Hex("89 44 24");                                          // mov [rsp + 0x78], eax
            a.Bytes((byte)(Places.EntryAt + Places.EntrySort));
            a.Hex("C6 44 24");                                          // mov byte [rsp + 0x7D], 1
            a.Bytes((byte)(Places.EntryAt + Places.EntryUnmarked), 1);
            a.Hex("45 84 ED");                                          // test r13b, r13b: the Den's variable
            a.Short(ShortJe, "den");
            a.Hex("41 80 7E");                                          // cmp byte [r14 + 0x32], 0: its Den
            a.Bytes((byte)TownPoachers, 0);
            a.Short(ShortJe, "den");
            a.Hex("C6 44 24");                                          // mov byte [rsp + 0x7E], 1
            a.Bytes((byte)(Places.EntryAt + Places.EntryDen), 1);
            a.Label("den");
            a.Hex("3B 1D");                                             // cmp ebx, [rip + Ramza's place]
            a.Rip(p(places.CurrentPlace));
            a.Short(ShortJne, "here");
            a.Hex("C6 44 24");                                          // mov byte [rsp + 0x7F], 1
            a.Bytes((byte)(Places.EntryAt + Places.EntryHere), 1);
            a.Label("here");
            // (1.23.1) A town with a menu of its own (its Town row's town part, + 0x31): the kinds its shop sells, as the
            // game makes its towns' (Zodi's test 52): each of the Outfitter's five lists (1 to 4, then 7) asked of the
            // stock (the helper's, for a mod's town) into the items' list, each item's kind (+ 5 of its data) below 0x23
            // marked in the entry (+ 0x10 on). r15 (the function's own past its loop) the list; rsp + 0x38 and + 0x3C,
            // which it never uses, how many and which item.
            if (places.TownMenus && places.ListItem >= 0)
            {
                a.Hex("41 80 7E");                                      // cmp byte [r14 + 0x31], 0
                a.Bytes((byte)Places.TownPart, 0);
                a.NearTo("no kinds", Je);
                a.Hex("41 BF 01 00 00 00");                             // mov r15d, 1: the first list
                a.Label("kind list");
                a.Hex("C6 44 24 28 00");                                // mov byte [rsp + 0x28], 0: not sorted
                a.Hex("C7 44 24 20 00 00 00 00");                       // mov dword [rsp + 0x20], 0: not checked
                a.Hex("45 8B C7");                                      // mov r8d, r15d: the list
                a.Hex("41 83 FF 05");                                   // cmp r15d, 5
                a.Short(ShortJne, "kind list made");
                a.Hex("41 B8");                                         // mov r8d, 7: the fifth is 7
                a.I32(Places.FifthList);
                a.Label("kind list made");
                a.Hex("4C 8D 0D");                                      // lea r9, [rip + the items' list]
                a.Rip(p(places.ListItems));
                a.Hex("8B D3");                                         // mov edx, ebx: its place
                a.Hex("83 C9 FF");                                      // or ecx, -1: no unit
                a.Call(p(places.Stock));                                // call: the stock
                a.Hex("89 44 24 38");                                   // mov [rsp + 0x38], eax: how many
                a.Hex("C7 44 24 3C 00 00 00 00");                       // mov dword [rsp + 0x3C], 0: the first
                a.Label("kind item");
                a.Hex("8B 44 24 3C");                                   // mov eax, [rsp + 0x3C]
                a.Hex("3B 44 24 38");                                   // cmp eax, [rsp + 0x38]
                a.Short(ShortJge, "kind list done");
                a.Hex("48 8D 0D");                                      // lea rcx, [rip + the items' list]
                a.Rip(p(places.ListItems));
                a.Hex("0F B7 0C 41");                                   // movzx ecx, word [rcx + rax*2]
                a.Hex("81 E1 FF 03 00 00");                             // and ecx, 0x3FF: the item
                a.Call(p(places.ListItem));                             // call: its data
                a.Hex("48 85 C0");                                      // test rax, rax
                a.Short(ShortJe, "kind item next");
                a.Hex("0F B6 40");                                      // movzx eax, byte [rax + 5]: its kind
                a.Bytes((byte)Places.ItemKind);
                a.Hex("83 F8");                                         // cmp eax, 0x23
                a.Bytes((byte)Places.Kinds);
                a.Short(ShortJae, "kind item next");
                a.Hex("80 4C 04");                                      // or byte [rsp + rax + 0x50], 1
                a.Bytes((byte)(Places.EntryAt + Places.EntryKinds), 1);
                a.Label("kind item next");
                a.Hex("FF 44 24 3C");                                   // inc dword [rsp + 0x3C]
                a.NearTo("kind item");                                  // jmp: the next item (a short jump only goes on)
                a.Label("kind list done");
                a.Hex("41 FF C7");                                      // inc r15d
                a.Hex("41 83 FF 05");                                   // cmp r15d, 5
                a.NearTo("kind list", Jle);
                a.Label("no kinds");
            }
            // Its tab: its kind's (above 2, the first, as the game's), put last or the tab grown.
            a.Hex("41 8B 46");                                          // mov eax, [r14 + 0x24]
            a.Bytes((byte)TownKind);
            a.Hex("83 F8 02");                                          // cmp eax, 2
            a.Short(ShortJbe, "tab");
            a.Hex("31 C0");                                             // xor eax, eax
            a.Label("tab");
            a.Hex("C1 E0 05");                                          // shl eax, 5
            a.Hex("48 8D 8C 07");                                       // lea rcx, [rdi + rax + 0x6A0]
            a.I32(Places.ListTabs);
            a.Hex("48 8B 51");                                          // mov rdx, [rcx + 0x10]: its end
            a.Bytes((byte)Places.TabEnd);
            a.Hex("48 3B 51");                                          // cmp rdx, [rcx + 0x18]: its room's end
            a.Bytes((byte)Places.TabRoom);
            a.Short(ShortJe, "grow");
            foreach (int at in new[] { 0, 0x10, 0x20, 0x30 })
            {
                a.Hex("0F 10 44 24");                                   // movups xmm0, [rsp + 0x40 + at]
                a.Bytes((byte)(Places.EntryAt + at));
                a.Hex(at == 0 ? "0F 11 02" : "0F 11 42");                // movups [rdx + at], xmm0
                if (at != 0)
                    a.Bytes((byte)at);
            }
            a.Hex("48 83 41");                                          // add qword [rcx + 0x10], 0x40
            a.Bytes((byte)Places.TabEnd, (byte)Places.EntrySize);
            a.Short(ShortJmp, "next");
            a.Label("grow");
            a.Hex("4C 8D 44 24");                                       // lea r8, [rsp + 0x40]
            a.Bytes((byte)Places.EntryAt);
            a.Call(p(places.ListGrow));                                 // call: the tab grown, the entry put last
            a.Label("next");
            a.Hex("FF C3");                                             // inc ebx
            a.NearTo("loop");
            a.Label("done");
            a.Hex("48 8B 05");                                          // mov rax, [rip + the UI's root]: as it was
            a.Rip(p(places.UiRoot));
            a.Near(p(places.ListEnd + Places.ListEndLength));           // jmp: back past it
        }

        // --- the changes to the program -----------------------------------------------------------------------------

        static byte[] OldOf(ReadOnlySpan<byte> image, int at, int length) => image.Slice(at, length).ToArray();

        static byte[] I32Bytes(long value)
        {
            var b = new byte[4];
            BinaryPrimitives.WriteInt32LittleEndian(b, checked((int)value));
            return b;
        }

        /// <summary>A jump to a stub over `length` bytes (the rest int3: never reached, the stub jumping back past
        /// them).</summary>
        static byte[] JumpTo(ulong stub, ulong from, int length)
        {
            var b = new byte[length];
            b[0] = 0xE9;
            BinaryPrimitives.WriteInt32LittleEndian(b.AsSpan(1), checked((int)((long)stub - (long)(from + 5))));
            for (int n = 5; n < length; n++)
                b[n] = 0xCC;
            return b;
        }

        /// <summary>(1.21.0) A call of a stub over `length` bytes (the rest nop: the stub returns to them).</summary>
        static byte[] CallTo(ulong stub, ulong from, int length)
        {
            var b = new byte[length];
            b[0] = 0xE8;
            BinaryPrimitives.WriteInt32LittleEndian(b.AsSpan(1), checked((int)((long)stub - (long)(from + 5))));
            for (int n = 5; n < length; n++)
                b[n] = 0x90;
            return b;
        }

        /// <summary>The changes to the program (at `imageBase`): the records' four reads to the copy, the dots' 18
        /// reaches to the moved dots, the screen's sites to their stubs, its two allocations made bigger and their
        /// constructor's calls to the stub zeroing the rows; (1.7.1) the end of its loop over its places nearest the
        /// cursor and the pad's focus's three reads to their stubs; each with the bytes it replaces. Null and why
        /// when a distance can't be made (the memory too far from the program).</summary>
        public static List<CodePatch>? Patches(ReadOnlySpan<byte> image, Places places, ulong imageBase,
                                               DestinationMemory memory, int rows, out string why)
        {
            why = "";
            var patches = new List<CodePatch>();
            ulong records = memory.DataAt + DataRecords, dots = memory.DataAt + DataDots;
            ulong Stub(string name) => memory.CodeAt + (ulong)memory.Stubs[name];
            try
            {
                int lea = places.LocationRecordLea;
                patches.Add(new CodePatch(lea + 3, OldOf(image, lea + 3, 4),
                                          I32Bytes((long)(records + Places.RecordMenu) - (long)(imageBase + (ulong)lea + 7)),
                                          "the menu's entries' read of a place's record"));
                foreach (int read in places.LocationRecordReads)
                    patches.Add(new CodePatch(read + 4, OldOf(image, read + 4, 4),
                                              I32Bytes((long)(records + Places.RecordPicture) - (long)imageBase),
                                              "a read of a place's picture"));
                foreach (int at in places.DotLeas)
                {
                    long field = 7 + at + (long)BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at + 3, 4)) - places.Dots;
                    patches.Add(new CodePatch(at + 3, OldOf(image, at + 3, 4),
                                              I32Bytes((long)dots + field - (long)(imageBase + (ulong)at + 7)),
                                              "a lea of the world map's dots"));
                }
                foreach (var (at, distance) in places.DotReads)
                {
                    long field = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(distance, 4)) - (long)places.Dots;
                    patches.Add(new CodePatch(distance, OldOf(image, distance, 4), I32Bytes((long)dots + field - (long)imageBase),
                                              "a read of the world map's dots"));
                }
                foreach (var (site, length, name, what) in new[]
                         {
                             (places.PlacePosition, 10, "position", "the screen's position of a place"),
                             (places.CursorAtPlace + Places.CursorBound, Places.CursorBoundLength, "cursor bound",
                              "the screen's cursor put on a place (its bound)"),
                             (places.CursorAtPlace + Places.CursorRead, Places.CursorReadLength, "cursor row",
                              "the screen's cursor put on a place (its row)"),
                             (places.DistanceBound, Places.BoundLength, "distance bound",
                              "the screen's distance of a place (its bound)"),
                             (places.DistanceRead, Places.DistanceReadLength, "distance row",
                              "the screen's distance of a place (its row)"),
                             (places.ArrivedFirst, Places.RowReadLength, "arrived row", "the screen's marker arrived (its row)"),
                             (places.ArrivedSecond, Places.RowReadLength, "arrived row again",
                              "the screen's marker arrived (its row again)"),
                             (places.PieceEvents + Places.PieceEventsReads[0], Places.RowReadLength, "piece row 1",
                              "the screen's handler of a piece's events (the mouse on it)"),
                             (places.PieceEvents + Places.PieceEventsReads[1], Places.RowReadLength, "piece row 2",
                              "the screen's handler of a piece's events (the mouse on it, again)"),
                             (places.PieceEvents + Places.PieceEventsReads[2], Places.RowReadLength, "piece row 3",
                              "the screen's handler of a piece's events (the mouse off it)"),
                             (places.PieceEvents + Places.PieceEventsReads[3], Places.RowReadLength, "piece row 4",
                              "the screen's handler of a piece's events (the mouse off it, again)"),
                             (places.HelpBound, Places.BoundLength, "help bound", "the screen's help of a place (its bound)"),
                             (places.HelpKind, Places.RowReadLength, "help row", "the screen's help of a place (its row)"),
                             (places.HelpKindAgain, Places.HelpKindAgainLength, "help row again",
                              "the screen's help of a place (its row again)"),
                             (places.MarkerPlace, Places.BoundLength, "marker bound",
                              "the screen's marker put on its place (its bound)"),
                             (places.MarkerPlace + Places.MarkerPlaceTest, Places.MarkerPlaceTestLength, "marker row",
                              "the screen's marker put on its place (its row)"),
                         })
                    patches.Add(new CodePatch(site, OldOf(image, site, length), JumpTo(Stub(name), imageBase + (ulong)site, length),
                                              what));
                int bigger = ScreenRows + rows * RowSize;
                patches.Add(new CodePatch(places.MapAlloc + Places.MapAllocSize, OldOf(image, places.MapAlloc + Places.MapAllocSize, 4),
                                          I32Bytes(bigger), "the screen's map's size"));
                patches.Add(new CodePatch(places.FrameAlloc + Places.FrameAllocSize,
                                          OldOf(image, places.FrameAlloc + Places.FrameAllocSize, 4), I32Bytes(bigger),
                                          "the screen's frame menu's size"));
                foreach (var (alloc, what) in new[] { (places.MapAlloc, "the screen's map's constructor"),
                                                      (places.FrameAlloc, "the screen's frame menu's constructor") })
                {
                    int call = alloc + Places.AllocCtorCall;
                    patches.Add(new CodePatch(call + 1, OldOf(image, call + 1, 4),
                                              I32Bytes((long)Stub("rows zeroed") - (long)(imageBase + (ulong)call + 5)), what));
                }
                int end = places.Nearest + Places.NearestEnd;
                patches.Add(new CodePatch(end, OldOf(image, end, Places.NearestEndLength),
                                          JumpTo(Stub("nearest more"), imageBase + (ulong)end, Places.NearestEndLength),
                                          "the screen's place nearest the cursor (its loop's end)"));
                for (int n = 0; n < Places.NearestFocusReads.Length; n++)
                {
                    int site = places.NearestFocus + Places.NearestFocusReads[n];
                    patches.Add(new CodePatch(site, OldOf(image, site, Places.RowReadLength),
                                              JumpTo(Stub($"focus row {n + 1}"), imageBase + (ulong)site, Places.RowReadLength),
                                              $"the pad's focus of the nearest place (its row, read {n + 1} of 3)"));
                }
                // (1.23.1) The name of the place arrived at: its read of the place plus one to its stub.
                patches.Add(new CodePatch(places.ArrivalName, OldOf(image, places.ArrivalName, Places.ArrivalNameLength),
                                          JumpTo(Stub("arrival name"), imageBase + (ulong)places.ArrivalName,
                                                 Places.ArrivalNameLength),
                                          "the world map's name of the place arrived at"));
                // (1.23.2) The menu's name of its place: its sprite's making and the instruction after it to its stub.
                patches.Add(new CodePatch(places.MenuName, OldOf(image, places.MenuName, Places.MenuNameLength),
                                          JumpTo(Stub("menu name"), imageBase + (ulong)places.MenuName,
                                                 Places.MenuNameLength),
                                          "the menu's name of its place"));
                // (1.21.0) A mod's dungeon: the settlement menu's two tests of the Deep and its choosing's, the floor
                // chosen's ask of the chains, the Deep's list's two reads of a floor's row.
                if (memory.Stubs.ContainsKey("floor"))
                    foreach (var (site, length, name, call, what) in new[]
                             {
                                 (places.DungeonBlock, Places.DungeonBlockLength, "dungeon block", false,
                                  "the settlement menu's test of Midlight's Deep (its list)"),
                                 (places.DungeonScreen, Places.DungeonScreenLength, "dungeon screen", false,
                                  "the settlement menu's test of Midlight's Deep (its screen)"),
                                 (places.DungeonHandler, Places.DungeonHandlerLength, "dungeon handler", true,
                                  "the settlement menu's choosing's test of Midlight's Deep"),
                                 (places.FloorCall, Places.CallLength, "floor", true,
                                  "a floor chosen's ask of the place's chains"),
                                 (places.RowTitleCall, Places.CallLength, "row", true, "the Deep's list's name of a floor"),
                                 (places.RowInfoCall, Places.CallLength, "row", true, "the Deep's list's words of a floor"),
                             })
                        patches.Add(new CodePatch(site, OldOf(image, site, length),
                                                  call ? CallTo(Stub(name), imageBase + (ulong)site, length)
                                                       : JumpTo(Stub(name), imageBase + (ulong)site, length), what));
                // (1.23.0) The world map's location list: the end of its loop over the game's places to the mods'.
                if (memory.Stubs.ContainsKey("list more"))
                    patches.Add(new CodePatch(places.ListEnd, OldOf(image, places.ListEnd, Places.ListEndLength),
                                              JumpTo(Stub("list more"), imageBase + (ulong)places.ListEnd,
                                                     Places.ListEndLength),
                                              "the world map's location list (its loop's end)"));
            }
            catch (OverflowException)
            {
                why = Far;
                return null;
            }
            return patches;
        }

        public const string Far = "the memory given the places is more than 2 GB from the game's program";

        /// <summary>The memory the places get at `dataAt` and `codeAt` and the changes to the program reaching it
        /// (`patches`), or null and why: the memory too far from the program for its native code's jumps or the
        /// program's distances.</summary>
        public static DestinationMemory? Given(ReadOnlySpan<byte> image, Places places, ulong imageBase, ulong dataAt,
                                               ulong codeAt, List<Destination> destinations,
                                               out List<CodePatch>? patches, out string why)
        {
            patches = null;
            DestinationMemory memory;
            try
            {
                memory = Memory(image, places, imageBase, dataAt, codeAt, destinations);
            }
            catch (OverflowException)
            {
                why = Far;
                return null;
            }
            patches = Patches(image, places, imageBase, memory, RowCount(destinations), out why);
            return patches == null ? null : memory;
        }

        // --- the tables --------------------------------------------------------------------------------------------

        /// <summary>A row's strings are each a distance from a place of the row's own, not the same for every field:
        /// the game reads Town's Description from + 4 (its location info: 0x158D67), Town's Unknown18 from the row's
        /// start (the screen's setup: 0x1594E6), PlaceName's Title and Unknown10 from + 0xC (0xFB44C, 0xFB4DC), Route's
        /// name from the row's start (0x15B42E). So the places' rows give their empty strings a run of zeros long
        /// enough that a distance from any of those places finds one empty, and the name's distance is from + 0xC as
        /// the game reads it (from anywhere else: empty).</summary>
        public const int TownEmpty = TownRowHead, TownZeros = 0x20, NameZeros = 0x20, NameBase = 0xC;

        /// <summary>A mod's place's Town row: DLCFlags 0, (1.16.0) its description (after the row's zeros, from + 4
        /// as the location info reads it at 0x158D67; none, empty), where Ramza's marker stands (Unknown8 and
        /// UnknownC), its name's number, no piece's name (the screen's setup reads its 48 only), no picture, its kind
        /// (Unknown24: 0 a town, 1 a battle ground; (1.23.0) KindOf: 2 a dungeon or a town without a menu, and its
        /// sort in the location list, Unknown20), Unknown2C and 2E -1 as places 44 to 46's (no town of the game's
        /// has them: Unknown30, a town's background as its menu opens, is 0, a mod's place having no menu); its
        /// other strings empty (TownEmpty).</summary>
        public static byte[] TownRow(Destination d) => TownRow(d, ReadOnlySpan<byte>.Empty);

        /// <summary>(1.18.0) A town with a menu of its own also gets its art town's picture number (Unknown1C, of the
        /// game's Town table `game`: the location info's and the menu's art, the base pictures' path by number,
        /// 0xFC1C0), its town picture's number (Unknown2C and 2E: the TexChange the location info and the menu play,
        /// 0x158E30, of an Icon of the game's) and its Poachers' Den (Unknown32, read with variable 0x90 as its menu's
        /// entries are made, 0x3449B0).</summary>
        public static byte[] TownRow(Destination d, ReadOnlySpan<byte> game)
        {
            var words = Encoding.UTF8.GetBytes(d.Place.Description);
            int described = TownRowHead + TownZeros;
            var row = new byte[words.Length == 0 ? described : (described + words.Length + 1 + 3) & ~3];
            foreach (int field in new[] { 4, 0x10, 0x18 })
                BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(field), TownEmpty);
            if (words.Length > 0)
            {
                BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(4), described - 4);
                words.CopyTo(row, described);
            }
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(8), d.MarkerX);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(0xC), d.MarkerY);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(0x14), d.NameId);
            // (1.23.0) Its kind, the world map's location list's tab (Zodi's choice, "as the game sorts its own"), and its
            // sort after the game's places (theirs 10 to 510), in their numbers' order.
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(TownKind), KindOf(d.Place));
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(TownSort), SortFirst + d.Number);
            BinaryPrimitives.WriteInt16LittleEndian(row.AsSpan(0x2C), -1);
            BinaryPrimitives.WriteInt16LittleEndian(row.AsSpan(0x2E), -1);
            var menu = d.Place.Town ? d.Place.Menu : null;
            if (menu != null)
            {
                // Its art the art town's picture's number; (its own art) OwnArt plus its place's number, which the
                // base art's path gives its own files (PlaceHooks.BaseArt).
                int art = game.IsEmpty || menu.ArtPicture.Length > 0 ? -1 : Nxd.Find(game, new[] { menu.Art });
                if (menu.ArtPicture.Length > 0)
                    BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(TownArt), OwnArt + d.Number);
                else if (art >= 0 && art + TownArt + 4 <= game.Length)
                    BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(TownArt), I32(game, art + TownArt));
                if (int.TryParse(d.Place.Icon, out int icon))
                {
                    BinaryPrimitives.WriteInt16LittleEndian(row.AsSpan(0x2C), (short)icon);
                    BinaryPrimitives.WriteInt16LittleEndian(row.AsSpan(0x2E), (short)icon);
                }
                row[TownPoachers] = (byte)(menu.Poachers ? 1 : 0);
                // (1.23.1) The location panel's town part, as the game's towns' (Zodi's test 52: under Settlements, its
                // panel kept the last town's): its art and words, its errands (none: each of the game's names one of its
                // towns) and the kinds its shop sells (the list's entry's, the helper's native code).
                row[Places.TownPart] = 1;
            }
            // (1.23.0) A dungeon's art (its list's and its location info's): one of the game's places' (its Town row's
            // art), or its own (OwnArt plus its place's number, as a town's own).
            if (d.Place.Dungeon)
            {
                int art = game.IsEmpty || d.Place.DungeonArtPicture.Length > 0 ? -1
                    : Nxd.Find(game, new[] { d.Place.DungeonArt });
                if (d.Place.DungeonArtPicture.Length > 0)
                    BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(TownArt), OwnArt + d.Number);
                else if (art >= 0 && art + TownArt + 4 <= game.Length)
                    BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(TownArt), I32(game, art + TownArt));
            }
            return row;
        }

        /// <summary>(1.23.0) A Town row's kind, the world map's location list's tab, as the game's own places have
        /// theirs (Zodi's choice after test 49, "as the game sorts its own"): 0 Settlements (a town with a menu of its
        /// own), 1 Battlegrounds (a battle ground), 2 Miscellaneous (a dungeon, or a town without a menu, as Midlight's
        /// Deep, Ziekden Fortress or Orbonne Monastery).</summary>
        public static int KindOf(MapPlace place)
            => !place.Town ? KindGround : place.Dungeon || place.Menu == null ? KindOther : KindSettlement;

        public const int KindSettlement = 0, KindGround = 1, KindOther = 2;
        /// <summary>(1.23.0) A Town row's kind (+ 0x24) and its sort in the location list (+ 0x20); a mod's place's sort
        /// is this plus its number, after the game's places' (10 to 510).</summary>
        public const int TownKind = 0x24, TownSort = 0x20, SortFirst = 1000;

        /// <summary>(1.18.0) A town's record's menu (1: a town's entries) and a Town row's art picture's number
        /// (Unknown1C) and Poachers' Den (Unknown32).</summary>
        public const byte MenuTown = 1;
        public const int TownArt = 0x1C, TownPoachers = 0x32;
        /// <summary>(1.19.0) A town's own art's number in its Town row: this plus its place's number (the
        /// game's base art is numbered 1 to 26).</summary>
        public const int OwnArt = 1000;

        /// <summary>A mod's place's PlaceName row: DLCFlags 0, no comment, PlaceNameId 0 (as the game's), its name as
        /// its Title (from + 0xC, as the game reads it), no second line (Unknown10); zeros (NameZeros), then its
        /// name.</summary>
        public static byte[] NameRow(Destination d) => NameRowOf(d.Place.Name);

        /// <summary>(1.10.0) A PlaceName row for a name (a mod's place's, a quest map's Title), as NameRow lays it out.</summary>
        public static byte[] NameRowOf(string text)
        {
            var name = Encoding.UTF8.GetBytes(text);
            int zeros = NameRowHead, title = NameRowHead + NameZeros;
            var row = new byte[(title + name.Length + 1 + 3) & ~3];
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(4), zeros);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(0xC), title - NameBase);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(0x10), zeros);
            name.CopyTo(row, title);
            return row;
        }

        static int I32(ReadOnlySpan<byte> b, int at) => BinaryPrimitives.ReadInt32LittleEndian(b.Slice(at, 4));

        /// <summary>The strings of a row the game reads, each as it reads it: its field, and the place in the row its
        /// distance is from (TownEmpty's note).</summary>
        static readonly (int Field, int From)[] TownStrings = { (4, 4), (0x18, 0) }, NameStrings = { (0xC, NameBase),
                                                                                                     (0x10, NameBase) };

        /// <summary>Why a loaded Town or PlaceName isn't one the places' rows can go in, or "": one key; each row as
        /// long as the game's, the strings the game reads inside it; none of the places' keys already its.</summary>
        public static string ShapeProblem(int sheet, ReadOnlySpan<byte> table, List<Destination> destinations)
        {
            var rows = Nxd.Rows(table, out string why);
            if (rows == null)
                return why;
            if (Nxd.Keys(table) != 1)
                return $"it isn't a table of one key (byte 8: {table[8]})";
            int head = sheet == TownSheet ? TownRowHead : NameRowHead;
            var keys = new HashSet<int>();
            foreach (var d in destinations)
                keys.Add(sheet == TownSheet ? d.Number : d.NameId);
            foreach (var row in rows)
            {
                if (row.At + head > table.Length)
                    return "a row of it is cut short";
                foreach (var (field, from) in sheet == TownSheet ? TownStrings : NameStrings)
                {
                    long at = (long)row.At + from + I32(table, row.At + field);
                    if (at < 0 || at >= table.Length || table.Slice((int)at).IndexOf((byte)0) < 0)
                        return $"its row {row.Keys[0]}'s strings aren't inside it";
                }
                if (keys.Contains(row.Keys[0]))
                    return $"it already has a row {row.Keys[0]}, a mod's place's";
            }
            return "";
        }

        /// <summary>The loaded Town or PlaceName with the places' rows, or null and why.</summary>
        public static byte[]? WithRows(int sheet, ReadOnlySpan<byte> table, List<Destination> destinations, out string why)
        {
            why = ShapeProblem(sheet, table, destinations);
            if (why.Length > 0)
                return null;
            var rows = new List<NewRow>();
            foreach (var d in destinations)
                rows.Add(sheet == TownSheet ? new NewRow(new[] { d.Number }, TownRow(d, table))
                                            : new NewRow(new[] { d.NameId }, NameRow(d)));
            return Nxd.WithRows(table, rows, out why);
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
        /// <summary>How far after the program its memory may go: under 2 GB from its start (the dots' reads by a
        /// distance from the program's start reach them), and from every changed instruction.</summary>
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

        /// <summary>The memory the places get, as it goes at `dataAt` and `codeAt`.</summary>
        public static DestinationMemory Memory(ReadOnlySpan<byte> image, Places places, ulong imageBase, ulong dataAt,
                                               ulong codeAt, List<Destination> destinations)
        {
            var data = Data(image, places, destinations);
            bool dungeons = HasDungeons(places, destinations);
            var code = Code(image, places, imageBase, codeAt, RowCount(destinations), out var stubs, dataAt, dungeons);
            // (1.21.0) The dungeons' two slots: at first the code's zero.
            if (dungeons)
                foreach (int slot in new[] { FloorSlot, RowSlot })
                    BinaryPrimitives.WriteUInt64LittleEndian(data.AsSpan(slot), codeAt + (ulong)stubs["zero"]);
            return new DestinationMemory(dataAt, data, codeAt, code, stubs);
        }

        /// <summary>The places given to the program, before the game runs: the data and the native code made and
        /// written (the data read and written, the code read and run), each change checked against the bytes it
        /// replaces, then all made. Null, or why not: then nothing of the program is changed.</summary>
        public static string? Arm(byte* start, int imageSize, Places places, List<Destination> destinations)
            => Arm(start, imageSize, places, destinations, out _);

        /// <summary>(1.21.0) Arm, giving where the data went (0 if nowhere): a mod's dungeon's slots are in it.</summary>
        public static string? Arm(byte* start, int imageSize, Places places, List<Destination> destinations,
                                  out nint given)
        {
            given = 0;
            var image = new ReadOnlySpan<byte>(start, imageSize);
            ulong imageBase = (ulong)start;
            int rows = RowCount(destinations);
            bool dungeons = HasDungeons(places, destinations);
            var sizedCode = Code(image, places, imageBase, imageBase, rows, out _, imageBase, dungeons).Length;
            nint data = Near(imageBase, imageSize, dungeons ? DungeonDataBytes : DataBytes);
            if (data == 0)
                return "Windows gave no memory within 2 GB of the game's program";
            nint code = Near(imageBase, imageSize, sizedCode);
            if (code == 0)
                return "Windows gave no memory within 2 GB of the game's program";
            var memory = Given(image, places, imageBase, (ulong)data, (ulong)code, destinations, out var patches,
                               out string why);
            if (memory == null || patches == null)
                return why;
            foreach (var patch in patches)
                if (!image.Slice(patch.At, patch.Old.Length).SequenceEqual(patch.Old))
                    return $"{patch.What} isn't as it was found";
            Marshal.Copy(memory.Data, 0, data, memory.Data.Length);
            Marshal.Copy(memory.Code, 0, code, memory.Code.Length);
            if (!VirtualProtect(code, (nuint)memory.Code.Length, ExecuteRead, out _))
                return "the places' native code couldn't be made runnable";
            FlushInstructionCache(GetCurrentProcess(), code, (nuint)memory.Code.Length);
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
                return $"{patches[n].What} couldn't be changed";
            }
            foreach (var patch in patches)
                Marshal.Copy(patch.New, 0, (nint)(start + patch.At), patch.New.Length);
            for (int m = patches.Count - 1; m >= 0; m--)
            {
                nint where = (nint)(start + patches[m].At);
                VirtualProtect(where, (nuint)patches[m].New.Length, protections[m], out _);
                FlushInstructionCache(GetCurrentProcess(), where, (nuint)patches[m].New.Length);
            }
            given = data;
            return null;
        }
    }
}
