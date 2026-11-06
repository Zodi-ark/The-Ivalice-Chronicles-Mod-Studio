// Mod Studio Framework: (1.10.0) a quest's own maps, numbered past the
// game's. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi, 27 October, after his test 32: a quest's own maps, built in steps
// ("Yes, start with test 33"). The game's maps are 0 to 127; a setup record's
// map is a byte. A quest map (MapFile.cs) is given a number from 129 to 255
// as the game starts (kept in Numbers.json, the same every time, never given
// twice), and his program, read as data (dev/research/sidequests/README.md, A
// quest's own maps), is changed so that a map past 127 loads as one of its
// own, made from its Base:
// - the PlayStation side (the battle grid, the classic look): the five tables
//   of 128 its map loader reads (`0x251584`, `0x251640`: the GNS's file index
//   in the Japanese and English packs, each map's list of its numbered files
//   in each, the move-find data), each reached by one lea and nothing else,
//   moved to copies of 256 in memory of the helper's, the game's 128 copied
//   again each time a map loads (so what the mod loader writes into them, as
//   mods' Treasure Hunter tiles, stays the game's); a quest map's entries are
//   its Base's GNS, its Base's list of files with its own files in their
//   places (handed to the game under file indices from 0x10000, read at the
//   PlayStation's file reader `0x2F40C4`), and no hidden items; the lists of
//   polygons a map has (`0x249CB8`) its Base's;
// - the enhanced look: the five places that make a map's file names
//   (sprintf, `0xD5A50`) given its mesh and anims (the mod's, else its
//   Base's), and its Base's number for its pictures' folder (its rows name
//   them: the game's own there, the mod's under names of its own) and the
//   classic look's pictures; the mesh's and anims' check of their own number
//   against the map's (byte 8) taken out, and the textures' limit of 127
//   raised;
// - its rows in the six tables keyed by a map, and its Title in PlaceName,
//   as they load (MapHooks.cs).
// Each found by its own bytes, checked against them as the helper makes it;
// all made or none, said. dev/research/sidequests/quest_maps.py runs the
// game's own code over what this makes; helper/Checks has the helper find
// and make it in his program.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

namespace ModStudioEventSetup
{
    public sealed unsafe class MapRoom
    {
        /// <summary>The numbers a quest map is given: past the game's 128 and the one more its Map table has a row for
        /// (128, nothing but a variant), up to what a setup record's byte holds.</summary>
        public const int FirstMap = 129, LastMap = 255, GameMaps = 128, Room = 256;
        /// <summary>The PlayStation file indices a quest map's own files are handed to the game under (the packs have
        /// 3,931 at most).</summary>
        public const uint FakeFile = 0x10000;
        /// <summary>How many of its Base's numbered files a quest map's list holds (the game's maps have at most 40).</summary>
        public const int ListPairs = MapFile.Places;
        /// <summary>A quest map's Title's key in PlaceName: past the game's and the mods' places'.</summary>
        public const int TitleKeyFirst = 950000;
        public static int TitleKey(int number) => TitleKeyFirst + number;

        // --- what was measured (his 17 September program) ------------------------------------------------------------

        /// <summary>The map's GNS's loader (0x251584: the map as 16 bits): its lea of the move-find data, 0xF from its
        /// start (the bytes before it not looked at: a hook's jump may be there); its two leas of the GNS's file
        /// indices (each pack's; 0x59 from its start); its call of the polygon lists' setter (0x249CB8, at 0x83).</summary>
        public const string GnsBodyBytes =
            "48 8D 0D ?? ?? ?? ?? 41 B8 B8 0B 00 00 48 8D 04 5B 0F 10 04 C1 F2 0F 10 4C C1 10 48 8D 0D ?? ?? ?? ?? 0F 29 05";
        public const int GnsBody = 0xF;
        public const string GnsLeasBytes = "85 C9 48 8D 15 ?? ?? ?? ?? 48 8D 05 ?? ?? ?? ?? 48 0F 44 C2 8B 3C 98";
        public const int GnsLeas = 0x59;
        public const string ListsCallBytes = "83 3D ?? ?? ?? ?? 00 75 07 8B CB E8 ?? ?? ?? ??";
        public const int ListsCall = 0x78, ListsCallAt = 0xB;
        /// <summary>A map's resource's loader (0x251640): after its test of 0xFEEDBACC, its two leas of each pack's lists
        /// of the maps' files (at + 0x21 and + 0x2E).</summary>
        public const string ResourceBytes =
            "41 81 FA CC BA ED FE 75 ?? 48 8B 05 ?? ?? ?? ?? 48 85 C0 75 07 B8 01 00 00 00 EB 03 8B 40 08 85 C0 48 8D 15 "
            + "?? ?? ?? ?? 8B 05 ?? ?? ?? ?? 48 8D 0D ?? ?? ?? ?? 48 0F 44 CA 48 8B 14 C1";
        public const int ResourceListJa = 0x21, ResourceListEn = 0x2E;
        /// <summary>The PlayStation's file reader (0x2F40C4: the file, a sector, a size, the buffer), 0x14 from its start;
        /// and, after a read, its clearing of a word (0x1856AB4: and dword [rip + x], 0), 0xB9 from its start.</summary>
        public const string ReaderBytes =
            "80 3D ?? ?? ?? ?? 00 49 8B F1 41 8B E8 8B D9 8B FA 75 16 8B CB E8 ?? ?? ?? ?? 85 C0 0F 85 ?? ?? ?? ?? C6 05 "
            + "?? ?? ?? ?? 01 83 FB 11 75 0C";
        public const int ReaderBody = 0x14;
        public const string ReadDoneBytes = "83 25 ?? ?? ?? ?? 00 44 8B C3 E8";
        public const int ReadDone = 0xB9;
        /// <summary>The paths made from a map's number, each the format a `lea rdx, [rip + x]` gives a sprintf called
        /// within FormatReach bytes after it: the mesh's, the anims', the units' lighting's (.tga), the pictures' by
        /// name and the classic look's pictures'.</summary>
        public static readonly string[] Formats =
        {
            "bg/meshes/map_%03d_mesh.bin", "bg/anims/map_%03d_anim.bin", "bg/textures/%03d/%s.tga",
            "bg/textures/%03d/%s", "bg/classic/textures/%03d/map_%03d_%d.tex",
        };
        public const int MeshFormat = 0, AnimFormat = 1, LightingFormat = 2, TexturesFormat = 3, ClassicFormat = 4;
        public const int FormatReach = 0x40;
        /// <summary>The mesh's check of its byte 8 against the map (cmp [rbp - 0x60], r12d at + 5), and the anims' (mov
        /// eax, [rdx + 8]; cmp eax, [rsp + 0x58] at + 0x11); the textures by name's limit (cmp [rcx + 0xC6E8], 0x7F,
        /// its immediate at + 6).</summary>
        public const string MeshCheckBytes = "E8 ?? ?? ?? ?? 44 39 65 A0 8B C6 0F 95 C0 81 7D 98 46 46 54 4F";
        public const int MeshCheck = 5;
        public const string AnimCheckBytes = "81 3A 46 46 54 4F 75 ?? 81 7A 04 41 4E 49 4D 75 ?? 8B 42 08 3B 44 24 58 75";
        public const int AnimCheck = 0x11;
        public const string LimitBytes = "83 B9 E8 C6 00 00 7F 48 8B D9";
        public const int Limit = 6;
        public static readonly byte[] MeshCheckNew = { 0x45, 0x39, 0xE4, 0x90 };
        public static readonly byte[] AnimCheckNew = { 0x8B, 0x44, 0x24, 0x58, 0x39, 0xC0, 0x90 };
        /// <summary>The textures' limit made -2: only a map of -1 (none yet) is above it.</summary>
        public const byte LimitNew = 0xFE;

        /// <summary>The five tables (their entries' sizes), each reached by one lea.</summary>
        public const int GnsEntry = 4, ListEntry = 8, MoveFindEntry = 24;

        /// <summary>Where everything is, as found.</summary>
        public sealed class Sites
        {
            public int GnsLoad { get; set; } = -1;
            public int MoveFindLea { get; set; } = -1;
            public int GnsLeaJa { get; set; } = -1;
            public int GnsLeaEn { get; set; } = -1;
            public int ListsCall { get; set; } = -1;
            public int ListsTarget { get; set; } = -1;
            public int ListLeaJa { get; set; } = -1;
            public int ListLeaEn { get; set; } = -1;
            public int FileRead { get; set; } = -1;
            public int ReadDoneWord { get; set; } = -1;
            public int Sprintf { get; set; } = -1;
            /// <summary>The sprintf call of each format (Formats' order).</summary>
            public int[] FormatCalls { get; } = { -1, -1, -1, -1, -1 };
            public int MeshCheck { get; set; } = -1;
            public int AnimCheck { get; set; } = -1;
            public int Limit { get; set; } = -1;
            /// <summary>The tables, from the program's start.</summary>
            public int MoveFind { get; set; } = -1;
            public int GnsJa { get; set; } = -1;
            public int GnsEn { get; set; } = -1;
            public int ListsJa { get; set; } = -1;
            public int ListsEn { get; set; } = -1;
        }

        static int I32(ReadOnlySpan<byte> image, int at) => BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at, 4));
        static int Rip(ReadOnlySpan<byte> image, int at, int length) => at + length + I32(image, at + length - 4);

        static int One(ReadOnlySpan<byte> image, List<Section> sections, string bytes, string what, out string why)
        {
            var found = Places.Search(image, sections, Places.Pattern(bytes));
            why = found.Count == 1 ? "" : $"{what} ({found.Count} places like it, not 1)";
            return found.Count == 1 ? found[0] : -1;
        }

        /// <summary>Where a format's text is in the program: its bytes and a zero after them, once.</summary>
        static int TextAt(ReadOnlySpan<byte> image, string text)
        {
            var bytes = Encoding.ASCII.GetBytes(text + "\0");
            int at = -1, from = 0;
            while (true)
            {
                int next = image.Slice(from).IndexOf(bytes);
                if (next < 0)
                    return at;
                if (at >= 0)
                    return -2;
                at = from + next;
                from = at + 1;
            }
        }

        /// <summary>Whether the four bytes at `at`, after a byte that would make them a distance from the instruction's
        /// end (a ModRM of mod 0, r/m 5), follow an opcode that takes such an operand: one of the one-byte opcodes
        /// that do (arithmetic, mov, lea, movsxd, imul, the shifts, test, inc and the rest), or any after 0F. Four
        /// bytes inside another instruction (in his program, two inside a call's distance near the move-find data)
        /// aren't one.</summary>
        static bool Operand(ReadOnlySpan<byte> image, int at)
        {
            if (at < 3)
                return false;
            if (image[at - 3] == 0x0F)
                return true;
            byte op = image[at - 2];
            return op <= 0x3B && (op & 7) <= 3 || op == 0x63 || op == 0x69 || op == 0x6B || op >= 0x80 && op <= 0x8B
                   || op == 0x8D || op == 0x8F || op == 0xC0 || op == 0xC1 || op == 0xC6 || op == 0xC7
                   || op >= 0xD0 && op <= 0xD3 || op == 0xF6 || op == 0xF7 || op == 0xFE || op == 0xFF;
        }

        /// <summary>The sites, each found by its own bytes where it was measured to be; null and why not.</summary>
        public static Sites? Find(ReadOnlySpan<byte> image, List<Section> sections, out string why)
        {
            var s = new Sites();
            int body = One(image, sections, GnsBodyBytes, "the map's GNS's loader", out why);
            if (body < 0)
                return null;
            s.GnsLoad = body - GnsBody;
            s.MoveFindLea = body;
            if (!Places.At(image, s.GnsLoad + GnsLeas, Places.Pattern(GnsLeasBytes)))
            {
                why = "the map's GNS's loader's leas of its file indices";
                return null;
            }
            s.GnsLeaJa = s.GnsLoad + GnsLeas + 2;
            s.GnsLeaEn = s.GnsLoad + GnsLeas + 9;
            if (!Places.At(image, s.GnsLoad + ListsCall, Places.Pattern(ListsCallBytes)))
            {
                why = "the map's GNS's loader's call of its polygon lists";
                return null;
            }
            s.ListsCall = s.GnsLoad + ListsCall + ListsCallAt;
            s.ListsTarget = Rip(image, s.ListsCall, 5);
            int resource = One(image, sections, ResourceBytes, "the map's resources' loader", out why);
            if (resource < 0)
                return null;
            s.ListLeaJa = resource + ResourceListJa;
            s.ListLeaEn = resource + ResourceListEn;
            int reader = One(image, sections, ReaderBytes, "the PlayStation's file reader", out why);
            if (reader < 0)
                return null;
            s.FileRead = reader - ReaderBody;
            if (!Places.At(image, s.FileRead + ReadDone, Places.Pattern(ReadDoneBytes)))
            {
                why = "the PlayStation's file reader's clearing after a read";
                return null;
            }
            s.ReadDoneWord = s.FileRead + ReadDone + 7 + I32(image, s.FileRead + ReadDone + 2);
            // The tables: each reached by its one lea and nothing else.
            s.MoveFind = Rip(image, s.MoveFindLea, 7);
            s.GnsJa = Rip(image, s.GnsLeaJa, 7);
            s.GnsEn = Rip(image, s.GnsLeaEn, 7);
            s.ListsJa = Rip(image, s.ListLeaJa, 7);
            s.ListsEn = Rip(image, s.ListLeaEn, 7);
            foreach (var (lea, table, size, what) in new[]
                     {
                         (s.MoveFindLea, s.MoveFind, MoveFindEntry, "the move-find data"),
                         (s.GnsLeaJa, s.GnsJa, GnsEntry, "the Japanese pack's GNS indices"),
                         (s.GnsLeaEn, s.GnsEn, GnsEntry, "the English pack's GNS indices"),
                         (s.ListLeaJa, s.ListsJa, ListEntry, "the Japanese pack's lists of the maps' files"),
                         (s.ListLeaEn, s.ListsEn, ListEntry, "the English pack's lists of the maps' files"),
                     })
            {
                var found = new List<int>();
                var leas = EventRoom.Reaching(image, sections, table, table + (long)GameMaps * size, found);
                var others = new List<int>();
                foreach (int at in found)
                    if (Operand(image, at))
                        others.Add(at);
                if (leas.Count != 1 || leas[0] != lea || others.Count != 0)
                {
                    why = $"{what}'s reaches ({leas.Count} leas and {others.Count} others, not its one lea)";
                    return null;
                }
            }
            // The paths: each format's lea, and the sprintf the five call after them.
            var candidates = new List<List<(int At, int Target)>>();
            for (int f = 0; f < Formats.Length; f++)
            {
                int text = TextAt(image, Formats[f]);
                if (text < 0)
                {
                    why = $"the path {Formats[f]} ({(text == -1 ? "not in the program" : "twice in it")})";
                    return null;
                }
                var others = new List<int>();
                var reaching = EventRoom.Reaching(image, sections, text, text + 1, others);
                var leas = new List<int>();
                foreach (int at in reaching)
                    if (image[at + 2] == 0x15)
                        leas.Add(at);
                if (leas.Count != 1)
                {
                    why = $"the path {Formats[f]}'s lea into rdx ({leas.Count}, not 1)";
                    return null;
                }
                var calls = new List<(int, int)>();
                for (int at = leas[0] + 7; at < leas[0] + 7 + FormatReach; at++)
                    if (image[at] == 0xE8)
                        calls.Add((at, Rip(image, at, 5)));
                candidates.Add(calls);
            }
            var common = new List<int>();
            foreach (var (_, target) in candidates[0])
                if (!common.Contains(target) && candidates.TrueForAll(c => c.Exists(x => x.Target == target)))
                    common.Add(target);
            if (common.Count != 1)
            {
                why = $"the sprintf the map's paths are made by ({common.Count} called after every one, not 1)";
                return null;
            }
            s.Sprintf = common[0];
            for (int f = 0; f < Formats.Length; f++)
                s.FormatCalls[f] = candidates[f].Find(x => x.Target == s.Sprintf).At;
            int mesh = One(image, sections, MeshCheckBytes, "the mesh's check of its number", out why);
            int anim = mesh < 0 ? -1 : One(image, sections, AnimCheckBytes, "the anims' check of their number", out why);
            int limit = anim < 0 ? -1 : One(image, sections, LimitBytes, "the textures' limit of 127", out why);
            if (limit < 0)
                return null;
            s.MeshCheck = mesh + MeshCheck;
            s.AnimCheck = anim + AnimCheck;
            s.Limit = limit + Limit;
            why = "";
            return s;
        }

        // --- the memory given the maps -------------------------------------------------------------------------------

        /// <summary>The data's layout: the five tables' copies (room for 256 maps), then the quest maps' Bases (-1 none),
        /// their meshes' and anims' paths (pointers), the two hooks' ways to the game's functions, the table of the
        /// files handed over (each its bytes' address and length, 16 bytes), then the quest maps' lists, the files and
        /// the paths' texts.</summary>
        public const int GnsJaAt = 0, GnsEnAt = 0x400, ListsJaAt = 0x800, ListsEnAt = 0x1000, MoveFindAt = 0x1800,
                         BasesAt = 0x3000, MeshPathsAt = 0x3200, AnimPathsAt = 0x3600, RefreshSlot = 0x3A00,
                         ReaderSlot = 0x3A08, FilesAt = 0x3A10, FileEntry = 16;
        /// <summary>The PlayStation's sector: the reader's unit, and every size in the game's lists a whole number of
        /// them.</summary>
        public const int Sector = 2048;

        /// <summary>A quest map given its number.</summary>
        public sealed class Given
        {
            public int Number { get; }
            public QuestMap Map { get; }

            public Given(int number, QuestMap map)
            {
                Number = number;
                Map = map;
            }
        }

        /// <summary>The memory as it goes at DataAt and CodeAt, and where in the code each piece is.</summary>
        public sealed class Block
        {
            public ulong DataAt { get; }
            public byte[] Data { get; }
            public ulong CodeAt { get; }
            public byte[] Code { get; }
            public int Refresh { get; set; }
            public int Reader { get; set; }
            public int ListsThunk { get; set; }
            /// <summary>Each format's stand-in (Formats' order).</summary>
            public int[] Stubs { get; } = new int[5];
            /// <summary>What each file handed over is: its map's number and place.</summary>
            public List<(int Number, int Place)> Files { get; } = new List<(int, int)>();

            public Block(ulong dataAt, byte[] data, ulong codeAt, byte[] code)
            {
                DataAt = dataAt;
                Data = data;
                CodeAt = codeAt;
                Code = code;
            }
        }

        /// <summary>The bytes the data will hold, from the program as `image` holds it (the tables' 128 entries copied,
        /// each quest map's lists from its Base's, read through the program's pointers less `imageBase`).</summary>
        static byte[] Data(ReadOnlySpan<byte> image, Sites s, ulong imageBase, ulong dataAt, IList<Given> maps,
                           List<(int Number, int Place)> files)
        {
            var data = new List<byte>(new byte[FilesAt]);
            void Put32(int at, uint v)
            {
                for (int k = 0; k < 4; k++)
                    data[at + k] = (byte)(v >> (8 * k));
            }
            void Put64(int at, ulong v)
            {
                for (int k = 0; k < 8; k++)
                    data[at + k] = (byte)(v >> (8 * k));
            }
            foreach (var (at, from, length) in new[]
                     {
                         (GnsJaAt, s.GnsJa, GameMaps * GnsEntry), (GnsEnAt, s.GnsEn, GameMaps * GnsEntry),
                         (ListsJaAt, s.ListsJa, GameMaps * ListEntry), (ListsEnAt, s.ListsEn, GameMaps * ListEntry),
                         (MoveFindAt, s.MoveFind, GameMaps * MoveFindEntry),
                     })
                for (int k = 0; k < length; k++)
                    data[at + k] = image[from + k];
            for (int n = 0; n < LastMap - FirstMap + 1; n++)
                Put32(BasesAt + 4 * n, 0xFFFFFFFF);
            // The files handed over, numbered in the maps' order and their places'.
            foreach (var g in maps)
                foreach (var place in g.Map.Grid.Keys)
                    files.Add((g.Number, place));
            int filesEnd = FilesAt + files.Count * FileEntry;
            data.AddRange(new byte[filesEnd - FilesAt]);
            var texts = new List<(int At, string Text)>();
            var blobs = new List<(int At, byte[] Bytes)>();
            foreach (var g in maps)
            {
                int n = g.Number, b = g.Map.Base, slot = n - FirstMap;
                Put32(BasesAt + 4 * slot, (uint)b);
                Put32(GnsJaAt + 4 * n, BinaryPrimitives.ReadUInt32LittleEndian(image.Slice(s.GnsJa + 4 * b, 4)));
                Put32(GnsEnAt + 4 * n, BinaryPrimitives.ReadUInt32LittleEndian(image.Slice(s.GnsEn + 4 * b, 4)));
                // Its lists: its Base's first ListPairs pairs in each pack, its own files in their places.
                foreach (var (tableAt, game) in new[] { (ListsJaAt, s.ListsJa), (ListsEnAt, s.ListsEn) })
                {
                    ulong pointer = BinaryPrimitives.ReadUInt64LittleEndian(image.Slice(game + 8 * b, 8));
                    if (pointer == 0)
                        continue;
                    int from = checked((int)(pointer - imageBase));
                    int list = data.Count;
                    data.AddRange(new byte[ListPairs * 8]);
                    int length = Math.Min(ListPairs * 8, image.Length - from);
                    for (int k = 0; k < length; k++)
                        data[list + k] = image[from + k];
                    // Its own files' sizes in whole sectors, as the game's lists give every file's (the reader hands
                    // over zeros past a file's end).
                    foreach (var (place, bytes) in g.Map.Grid)
                    {
                        int file = files.FindIndex(f => f.Number == n && f.Place == place);
                        Put32(list + 8 * place, FakeFile + (uint)file);
                        Put32(list + 8 * place + 4, (uint)((bytes.Length + Sector - 1) / Sector * Sector));
                    }
                    Put64(tableAt + 8 * n, dataAt + (ulong)list);
                }
                string mesh = g.Map.Mesh.Length > 0 ? g.Map.Mesh : $"bg/meshes/map_{b:D3}_mesh.bin";
                string anims = g.Map.Anims.Length > 0 ? g.Map.Anims : $"bg/anims/map_{b:D3}_anim.bin";
                texts.Add((MeshPathsAt + 8 * slot, mesh));
                texts.Add((AnimPathsAt + 8 * slot, anims));
            }
            foreach (var (at, text) in texts)
            {
                Put64(at, dataAt + (ulong)data.Count);
                data.AddRange(Encoding.ASCII.GetBytes(text));
                data.Add(0);
                while (data.Count % 8 != 0)
                    data.Add(0);
            }
            for (int f = 0; f < files.Count; f++)
            {
                var (number, place) = files[f];
                var bytes = maps[IndexOf(maps, number)].Map.Grid[place];
                Put64(FilesAt + FileEntry * f, dataAt + (ulong)data.Count);
                Put32(FilesAt + FileEntry * f + 8, (uint)bytes.Length);
                data.AddRange(bytes);
                while (data.Count % 16 != 0)
                    data.Add(0);
            }
            return data.ToArray();
        }

        static int IndexOf(IList<Given> maps, int number)
        {
            for (int n = 0; n < maps.Count; n++)
                if (maps[n].Number == number)
                    return n;
            return -1;
        }

        /// <summary>x64 code, written by hand: each piece's bytes.</summary>
        sealed class Code
        {
            readonly List<byte> _bytes = new List<byte>();
            public int Here => _bytes.Count;
            public byte[] Bytes => _bytes.ToArray();
            public void Add(params byte[] b) => _bytes.AddRange(b);
            public void U32(uint v)
            {
                for (int k = 0; k < 4; k++)
                    _bytes.Add((byte)(v >> (8 * k)));
            }
            public void U64(ulong v)
            {
                for (int k = 0; k < 8; k++)
                    _bytes.Add((byte)(v >> (8 * k)));
            }
            /// <summary>A short jump's distance, once its target is known.</summary>
            public void Land(int jump) => _bytes[jump] = checked((byte)(sbyte)(Here - (jump + 1)));
            public void Align()
            {
                while (_bytes.Count % 16 != 0)
                    _bytes.Add(0xCC);
            }
        }

        /// <summary>A map number past the game's in r8d (`r8`) or ecx: on to `go` below 128 or above 255. Returns the two
        /// jumps' distance bytes.</summary>
        static (int, int) Range(Code c, bool r8)
        {
            if (r8)
                c.Add(0x41, 0x81, 0xF8);                                     // cmp r8d, 0x80
            else
                c.Add(0x81, 0xF9);                                           // cmp ecx, 0x80
            c.U32(FirstMap);
            c.Add(0x72, 0);                                                  // jb go
            int below = c.Here - 1;
            if (r8)
                c.Add(0x41, 0x81, 0xF8);                                     // cmp r8d, 0xFF
            else
                c.Add(0x81, 0xF9);                                           // cmp ecx, 0xFF
            c.U32(LastMap);
            c.Add(0x77, 0);                                                  // ja go
            return (below, c.Here - 1);
        }

        /// <summary>The native code: the four stand-ins for the paths' sprintf calls (a mesh's or anims' path given;
        /// a Base's number for the pictures, once or twice), the polygon lists' setter given a Base, the copy of the
        /// game's 128 entries made as a map loads, and the file reader's handing over of the quest maps' files.</summary>
        static byte[] CodeBytes(Sites s, ulong imageBase, ulong dataAt, int files, Block? into)
        {
            var c = new Code();
            ulong sprintf = imageBase + (ulong)s.Sprintf;
            int[] stubs = new int[5];
            // The mesh's and the anims': r8d the map; a quest map's path is the format, which sprintf copies.
            foreach (var (format, paths) in new[] { (MeshFormat, MeshPathsAt), (AnimFormat, AnimPathsAt) })
            {
                c.Align();
                stubs[format] = c.Here;
                c.Add(0x45, 0x8B, 0xC0);                                     // mov r8d, r8d
                var (below, above) = Range(c, true);
                c.Add(0x48, 0xB8);                                           // mov rax, paths - 0x400
                c.U64(dataAt + (ulong)paths - 8UL * FirstMap);
                c.Add(0x4A, 0x8B, 0x04, 0xC0);                               // mov rax, [rax + r8*8]
                c.Add(0x48, 0x85, 0xC0);                                     // test rax, rax
                c.Add(0x74, 0x03);                                           // jz go
                c.Add(0x48, 0x8B, 0xD0);                                     // mov rdx, rax
                c.Land(below);
                c.Land(above);
                c.Add(0x48, 0xB8);                                           // go: mov rax, sprintf
                c.U64(sprintf);
                c.Add(0xFF, 0xE0);                                           // jmp rax
            }
            // The pictures': r8d the map (and r9d, the classic look's), given the quest map's Base.
            foreach (var (format, both) in new[] { (LightingFormat, false), (TexturesFormat, false), (ClassicFormat, true) })
            {
                if (format == TexturesFormat)
                {
                    stubs[format] = stubs[LightingFormat];
                    continue;
                }
                c.Align();
                stubs[format] = c.Here;
                c.Add(0x45, 0x8B, 0xC0);                                     // mov r8d, r8d
                var (below, above) = Range(c, true);
                c.Add(0x48, 0xB8);                                           // mov rax, bases - 0x200
                c.U64(dataAt + BasesAt - 4UL * FirstMap);
                c.Add(0x42, 0x8B, 0x04, 0x80);                               // mov eax, [rax + r8*4]
                c.Add(0x85, 0xC0);                                           // test eax, eax
                c.Add(0x78, (byte)(both ? 6 : 3));                           // js go
                c.Add(0x44, 0x8B, 0xC0);                                     // mov r8d, eax
                if (both)
                    c.Add(0x44, 0x8B, 0xC8);                                 // mov r9d, eax
                c.Land(below);
                c.Land(above);
                c.Add(0x48, 0xB8);                                           // go: mov rax, sprintf
                c.U64(sprintf);
                c.Add(0xFF, 0xE0);                                           // jmp rax
            }
            // The polygon lists' setter (ecx the map), given the quest map's Base.
            c.Align();
            int lists = c.Here;
            {
                c.Add(0x8B, 0xC9);                                           // mov ecx, ecx
                var (below, above) = Range(c, false);
                c.Add(0x48, 0xB8);                                           // mov rax, bases - 0x200
                c.U64(dataAt + BasesAt - 4UL * FirstMap);
                c.Add(0x8B, 0x04, 0x88);                                     // mov eax, [rax + rcx*4]
                c.Add(0x85, 0xC0);                                           // test eax, eax
                c.Add(0x78, 0x02);                                           // js go
                c.Add(0x8B, 0xC8);                                           // mov ecx, eax
                c.Land(below);
                c.Land(above);
                c.Add(0x48, 0xB8);                                           // go: mov rax, the setter
                c.U64(imageBase + (ulong)s.ListsTarget);
                c.Add(0xFF, 0xE0);                                           // jmp rax
            }
            // As a map loads (the GNS's loader's start): the game's 128 entries of the five tables copied into the
            // copies, rcx (the map) and every other argument kept; then the game's function.
            c.Align();
            int refresh = c.Here;
            c.Add(0x56, 0x57, 0x51);                                         // push rsi; push rdi; push rcx
            foreach (var (game, copy, size) in new[]
                     {
                         (s.GnsJa, GnsJaAt, GnsEntry), (s.GnsEn, GnsEnAt, GnsEntry), (s.ListsJa, ListsJaAt, ListEntry),
                         (s.ListsEn, ListsEnAt, ListEntry), (s.MoveFind, MoveFindAt, MoveFindEntry),
                     })
            {
                c.Add(0x48, 0xBE);                                           // mov rsi, the game's
                c.U64(imageBase + (ulong)game);
                c.Add(0x48, 0xBF);                                           // mov rdi, the copy
                c.U64(dataAt + (ulong)copy);
                c.Add(0xB9);                                                 // mov ecx, its 128 entries' bytes
                c.U32((uint)(GameMaps * size));
                c.Add(0xF3, 0xA4);                                           // rep movsb
            }
            c.Add(0x59, 0x5F, 0x5E);                                         // pop rcx; pop rdi; pop rsi
            c.Add(0x48, 0xB8);                                               // mov rax, the way to the game's
            c.U64(dataAt + RefreshSlot);
            c.Add(0xFF, 0x20);                                               // jmp [rax]
            // The PlayStation's file reader (ecx the file, edx a sector, r8d a size, r9 the buffer): a file from
            // FakeFile is one of the quest maps', copied from the helper's memory (a sector 2,048 bytes; what the file
            // hasn't, zeros), the reader's word cleared and 0 given back, as the game's own read; any other file the
            // game's.
            c.Align();
            int reader = c.Here;
            c.Add(0x81, 0xF9);                                               // cmp ecx, FakeFile
            c.U32(FakeFile);
            c.Add(0x73, 0x0C);                                               // jae ours
            c.Add(0x48, 0xB8);                                               // mov rax, the way to the game's
            c.U64(dataAt + ReaderSlot);
            c.Add(0xFF, 0x20);                                               // jmp [rax]
            c.Add(0x56, 0x57);                                               // ours: push rsi; push rdi
            c.Add(0x8B, 0xC1);                                               // mov eax, ecx
            c.Add(0x2D);                                                     // sub eax, FakeFile
            c.U32(FakeFile);
            c.Add(0x3D);                                                     // cmp eax, files
            c.U32((uint)files);
            c.Add(0x73, 0);                                                  // jae done
            int unknown = c.Here - 1;
            c.Add(0x4D, 0x85, 0xC9);                                         // test r9, r9
            c.Add(0x74, 0);                                                  // jz done
            int nowhere = c.Here - 1;
            c.Add(0x49, 0xBA);                                               // mov r10, the files' table
            c.U64(dataAt + FilesAt);
            c.Add(0x48, 0xC1, 0xE0, 0x04);                                   // shl rax, 4
            c.Add(0x4C, 0x01, 0xD0);                                         // add rax, r10
            c.Add(0x48, 0x8B, 0x30);                                         // mov rsi, [rax]
            c.Add(0x44, 0x8B, 0x58, 0x08);                                   // mov r11d, [rax + 8]
            c.Add(0x4C, 0x89, 0xCF);                                         // mov rdi, r9
            c.Add(0x8B, 0xC2);                                               // mov eax, edx
            c.Add(0x48, 0xC1, 0xE0, 0x0B);                                   // shl rax, 11
            c.Add(0x4D, 0x89, 0xDA);                                         // mov r10, r11
            c.Add(0x49, 0x29, 0xC2);                                         // sub r10, rax
            c.Add(0x73, 0x03);                                               // jae has
            c.Add(0x4D, 0x31, 0xD2);                                         // xor r10, r10
            c.Add(0x48, 0x01, 0xC6);                                         // has: add rsi, rax
            c.Add(0x44, 0x89, 0xC1);                                         // mov ecx, r8d
            c.Add(0x4C, 0x39, 0xD1);                                         // cmp rcx, r10
            c.Add(0x76, 0x03);                                               // jbe fits
            c.Add(0x4C, 0x89, 0xD1);                                         // mov rcx, r10
            c.Add(0x44, 0x89, 0xC0);                                         // fits: mov eax, r8d
            c.Add(0x48, 0x29, 0xC8);                                         // sub rax, rcx
            c.Add(0xF3, 0xA4);                                               // rep movsb
            c.Add(0x48, 0x89, 0xC1);                                         // mov rcx, rax
            c.Add(0x31, 0xC0);                                               // xor eax, eax
            c.Add(0xF3, 0xAA);                                               // rep stosb
            c.Land(unknown);
            c.Land(nowhere);
            c.Add(0x48, 0xB8);                                               // done: mov rax, the reader's word
            c.U64(imageBase + (ulong)s.ReadDoneWord);
            c.Add(0xC7, 0x00);                                               // mov dword [rax], 0
            c.U32(0);
            c.Add(0x31, 0xC0);                                               // xor eax, eax
            c.Add(0x5F, 0x5E, 0xC3);                                         // pop rdi; pop rsi; ret
            c.Align();
            if (into != null)
            {
                into.Refresh = refresh;
                into.Reader = reader;
                into.ListsThunk = lists;
                stubs.CopyTo(into.Stubs, 0);
            }
            return c.Bytes;
        }

        /// <summary>The memory the quest maps get at `dataAt` and `codeAt` (the program at `imageBase`), from the program
        /// as `image` holds it.</summary>
        public static Block Memory(ReadOnlySpan<byte> image, Sites s, ulong imageBase, ulong dataAt, ulong codeAt,
                                   IList<Given> maps)
        {
            var files = new List<(int, int)>();
            var data = Data(image, s, imageBase, dataAt, maps, files);
            var block = new Block(dataAt, data, codeAt, Array.Empty<byte>());
            var code = CodeBytes(s, imageBase, dataAt, files.Count, block);
            var made = new Block(dataAt, data, codeAt, code)
            {
                Refresh = block.Refresh, Reader = block.Reader, ListsThunk = block.ListsThunk,
            };
            block.Stubs.CopyTo(made.Stubs, 0);
            made.Files.AddRange(files);
            return made;
        }

        /// <summary>How long the code is, for a number of files (its length doesn't change with the addresses).</summary>
        public static int CodeLength(Sites s, int files) => CodeBytes(s, 0, 0, files, null).Length;

        static byte[] Bytes32(long value)
        {
            var b = new byte[4];
            BinaryPrimitives.WriteInt32LittleEndian(b, checked((int)value));
            return b;
        }

        /// <summary>The changes to the program for the memory in `block`: each the bytes it replaces as `image` has them;
        /// null and why when the memory is too far for a distance.</summary>
        public static List<CodePatch>? Patches(ReadOnlySpan<byte> image, Sites s, Block block, ulong imageBase, out string why)
        {
            var patches = new List<CodePatch>();
            long data = (long)(block.DataAt - imageBase), code = (long)(block.CodeAt - imageBase);
            var image_ = image.ToArray();
            CodePatch Distance(int at, int length, long target, string what)
                => new CodePatch(at + length - 4, image_.AsSpan(at + length - 4, 4).ToArray(),
                                 Bytes32(target - (at + length)), what);
            try
            {
                patches.Add(Distance(s.MoveFindLea, 7, data + MoveFindAt, $"the move-find data's lea at {s.MoveFindLea:x}"));
                patches.Add(Distance(s.GnsLeaJa, 7, data + GnsJaAt, $"the GNS indices' lea at {s.GnsLeaJa:x}"));
                patches.Add(Distance(s.GnsLeaEn, 7, data + GnsEnAt, $"the GNS indices' lea at {s.GnsLeaEn:x}"));
                patches.Add(Distance(s.ListLeaJa, 7, data + ListsJaAt, $"the files' lists' lea at {s.ListLeaJa:x}"));
                patches.Add(Distance(s.ListLeaEn, 7, data + ListsEnAt, $"the files' lists' lea at {s.ListLeaEn:x}"));
                patches.Add(Distance(s.ListsCall, 5, code + block.ListsThunk,
                                     $"the polygon lists' call at {s.ListsCall:x}"));
                for (int f = 0; f < Formats.Length; f++)
                    patches.Add(Distance(s.FormatCalls[f], 5, code + block.Stubs[f],
                                         $"the path {Formats[f]}'s sprintf at {s.FormatCalls[f]:x}"));
            }
            catch (OverflowException)
            {
                why = "the memory given the quest maps is more than 2 GB from the game's program";
                return null;
            }
            patches.Add(new CodePatch(s.MeshCheck, image.Slice(s.MeshCheck, 4).ToArray(), MeshCheckNew,
                                      $"the mesh's check of its number at {s.MeshCheck:x}"));
            patches.Add(new CodePatch(s.AnimCheck, image.Slice(s.AnimCheck, 7).ToArray(), AnimCheckNew,
                                      $"the anims' check of their number at {s.AnimCheck:x}"));
            patches.Add(new CodePatch(s.Limit, image.Slice(s.Limit, 1).ToArray(), new[] { LimitNew },
                                      $"the textures' limit at {s.Limit:x}"));
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
        /// <summary>Under 2 GB after the program's start: the leas' and calls' distances.</summary>
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

        /// <summary>The memory made and filled (its code made runnable), not yet joined to the program; null and why not.</summary>
        public static Block? Make(byte* start, int imageSize, Sites s, IList<Given> maps, out string why)
        {
            var image = new ReadOnlySpan<byte>(start, imageSize);
            ulong imageBase = (ulong)start;
            int files = 0;
            foreach (var g in maps)
                files += g.Map.Grid.Count;
            var sized = Memory(image, s, imageBase, imageBase, imageBase, maps);
            nint data = Near(imageBase, imageSize, sized.Data.Length);
            nint code = data == 0 ? 0 : Near(imageBase, imageSize, sized.Code.Length);
            if (data == 0 || code == 0)
            {
                why = "Windows gave no memory within 2 GB of the game's program";
                return null;
            }
            var block = Memory(image, s, imageBase, (ulong)data, (ulong)code, maps);
            Marshal.Copy(block.Data, 0, data, block.Data.Length);
            Marshal.Copy(block.Code, 0, code, block.Code.Length);
            if (!VirtualProtect(code, (nuint)block.Code.Length, ExecuteRead, out _))
            {
                why = "the quest maps' native code couldn't be made runnable";
                return null;
            }
            FlushInstructionCache(GetCurrentProcess(), code, (nuint)block.Code.Length);
            why = "";
            return block;
        }

        /// <summary>The program changed for the memory made (its two ways to the game's functions written first, by the
        /// hooks' maker): each change checked against the bytes it replaces, then all made. Null, or why not: then
        /// nothing of the program is changed.</summary>
        public static string? Join(byte* start, int imageSize, Sites s, Block block)
        {
            var image = new ReadOnlySpan<byte>(start, imageSize);
            var patches = Patches(image, s, block, (ulong)start, out string why);
            if (patches == null)
                return why;
            foreach (var patch in patches)
                if (!image.Slice(patch.At, patch.Old.Length).SequenceEqual(patch.Old))
                    return $"{patch.What} isn't as it was found";
            // Every change made writable first, so that either all are made or none.
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
            return null;
        }

        // --- the plan ---------------------------------------------------------------------------------------------------

        /// <summary>Each quest map given its number (Numbers.json's Maps, by its mod and folder), what can't be numbered
        /// or used said: a Base the game has no battle grid for (its GNS index 0 in either pack, read from `image` at the
        /// sites' tables). (1.29.0, Zodi's sixth of 3 November) Numbered afresh as each game starts: a map keeps the
        /// number it had while no other map enabled now has it, and the numbers of maps no longer enabled are free, so
        /// the room (129 to 255) is the maps enabled at once.</summary>
        public static List<Given> Plan(IList<QuestMap> maps, Numbers numbers, ReadOnlySpan<byte> image, Sites? s,
                                       List<string> said)
        {
            var given = new List<Given>();
            var present = new List<string>();
            foreach (var map in maps)
                present.Add(map.Key);
            numbers.BeginNow(Kind, present);
            foreach (var map in maps)
            {
                string who = $"{map.Folder} ({map.ModName})";
                if (s != null && (I32(image, s.GnsJa + 4 * map.Base) == 0 || I32(image, s.GnsEn + 4 * map.Base) == 0))
                {
                    said.Add($"the quest map {who} is left out: its Base, map {map.Base}, has no battle grid in the game.");
                    continue;
                }
                int n = numbers.GiveNow(Kind, map.Key, Range(FirstMap, LastMap), out _);
                if (n < 0)
                {
                    said.Add($"the quest map {who} is left out: no map number from {FirstMap} to {LastMap} is left "
                             + "(they are the quest maps enabled at once).");
                    continue;
                }
                given.Add(new Given(n, map));
            }
            numbers.SettleNow(Kind);
            return given;
        }

        /// <summary>The numbers' kind of the quest maps.</summary>
        public const string Kind = "Maps";

        static IEnumerable<int> Range(int first, int last)
        {
            for (int n = first; n <= last; n++)
                yield return n;
        }
    }
}
