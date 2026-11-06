// Mod Studio Framework: (1.14.0) a side quest's battle's own deploy areas.
// Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi's list, his second (28 October): "custom deploy areas", a quest
// battle's own squares where the player places units. A battle's setup
// record names its deploy areas by two numbers (DeployArea1 and DeployArea2,
// kept in variables 0x35 and 0x36 as the battle loads) of the program's 768
// squads of 12 bytes (ATTACK.OUT's deploy_squad_t: a 5 by 5 grid of tiles as
// 25 bits, the middle tile's x and y, its level, the grid's orientation, how
// many units, the map, its own number). Measured on his program
// (dev/research/sidequests/deploy_squads.py): the squads are read only
// through two pointers in its data (0x8ECA58, the squads, and 0x8ECA60, the
// squad in use), each reader taking a squad's number from variable 0x35 or
// 0x36 and adding 12 times it to the first pointer, with no bound; only the
// random battles' search by map stops at 768. So a quest's squads are given
// numbers past the game's (kept as "Squads" in the numbers), written into a
// copy of the squads with room for them, and both pointers given the copy
// before the game reads a squad.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace ModStudioEventSetup
{
    public static unsafe class DeploySquads
    {
        public const int SquadBytes = 12, GameSquads = 0x300;
        /// <summary>A quest's squads' numbers: past the game's 768, up to 4,095 (the copy has room up to the highest
        /// given; a setup record holds a squad's number in 16 bits).</summary>
        public const int FirstOwn = GameSquads, LastOwn = 4095;
        /// <summary>A squad's fields (deploy_squad_t): its tiles (25 bits, a 5 by 5 grid, row by row), the middle
        /// tile's x and y, its level (1 its upper), its grid's orientation (the low half how the grid lies, the high
        /// half added to it for the units' facing), how many units, its map, its own number.</summary>
        public const int Tiles = 0, X = 4, Y = 5, Level = 6, Orientation = 7, Most = 8, Map = 9, Own = 10;

        /// <summary>Where the squads were found in the program as loaded: the squads, and the two pointers to them.</summary>
        public readonly struct Found
        {
            public int Table { get; }
            public int First { get; }
            public int Second { get; }

            public Found(int table, int first, int second)
            {
                Table = table;
                First = first;
                Second = second;
            }
        }

        /// <summary>The squads (768 of 12 bytes, each ending in its own number) and the two pointers to them (each
        /// holding `baseAddress` plus the squads' place: the program as loaded, or a file's preferred base for a
        /// file laid out as loaded), one after the other; null and why when not exactly so. Both are looked for in the
        /// program's sections that aren't code, as the setup table is (Finder.Sections).</summary>
        public static Found? Find(ReadOnlySpan<byte> image, long baseAddress, out string why)
        {
            why = "";
            List<Section> sections;
            try
            {
                sections = Finder.Sections(image);
            }
            catch (InvalidOperationException e)
            {
                why = e.Message;
                return null;
            }
            int table = -1, hits = 0;
            foreach (var section in sections)
            {
                if (section.Code)
                    continue;
                int end = section.Address + section.Size;
                for (int at = section.Address; at + GameSquads * SquadBytes <= end; at += 2)
                {
                    // Squads 0x100 to 0x102 in a row, as Mod Studio finds them in the program's file.
                    int first = at + 0x100 * SquadBytes;
                    if (image[first + Own] != 0x00 || image[first + Own + 1] != 0x01
                        || image[first + SquadBytes + Own] != 0x01 || image[first + SquadBytes + Own + 1] != 0x01
                        || image[first + 2 * SquadBytes + Own] != 0x02
                        || image[first + 2 * SquadBytes + Own + 1] != 0x01)
                        continue;
                    bool all = true;
                    for (int n = 0; n < GameSquads && all; n++)
                        all = BinaryPrimitives.ReadUInt16LittleEndian(image.Slice(at + n * SquadBytes + Own, 2)) == n;
                    if (!all)
                        continue;
                    table = at;
                    hits++;
                }
            }
            if (hits != 1)
            {
                why = hits == 0 ? "the deploy squads weren't found" : "the deploy squads were found more than once";
                return null;
            }
            var pointers = new List<int>();
            long value = baseAddress + table;
            foreach (var section in sections)
            {
                if (section.Code)
                    continue;
                int end = section.Address + section.Size;
                for (int at = (section.Address + 7) & ~7; at + 8 <= end; at += 8)
                    if (BinaryPrimitives.ReadInt64LittleEndian(image.Slice(at, 8)) == value)
                        pointers.Add(at);
            }
            if (pointers.Count != 2 || pointers[1] != pointers[0] + 8)
            {
                why = $"the deploy squads' two pointers weren't found ({pointers.Count} found)";
                return null;
            }
            return new Found(table, pointers[0], pointers[1]);
        }

        /// <summary>A quest's squads given to the program: a copy of its squads with room up to the highest number
        /// given (the game's 768 first, as they are; between them and past them, nothing), each quest's squad at its
        /// number, and both pointers given the copy. Null when done, else why.</summary>
        public static string? Arm(byte* start, int imageSize, Found found, IReadOnlyList<(int Number, byte[] Bytes)> squads)
        {
            if (squads.Count == 0)
                return null;
            int most = GameSquads - 1;
            foreach (var (number, bytes) in squads)
            {
                if (number < FirstOwn || number > LastOwn || bytes.Length != SquadBytes)
                    return $"a quest's squad {number} isn't one the copy can hold";
                most = Math.Max(most, number);
            }
            if (found.Table < 0 || found.Table + GameSquads * SquadBytes > imageSize || found.Second + 8 > imageSize)
                return "the deploy squads aren't where they were found";
            long was = (long)(nint)(start + found.Table);
            if (*(long*)(start + found.First) != was || *(long*)(start + found.Second) != was)
                return "the deploy squads' pointers aren't as they were found";
            int size = (most + 1) * SquadBytes;
            byte* copy = (byte*)NativeMemory.AllocZeroed((nuint)size);
            Buffer.MemoryCopy(start + found.Table, copy, size, GameSquads * SquadBytes);
            foreach (var (number, bytes) in squads)
                Marshal.Copy(bytes, 0, (nint)(copy + number * SquadBytes), SquadBytes);
            *(long*)(start + found.First) = (long)(nint)copy;
            *(long*)(start + found.Second) = (long)(nint)copy;
            return null;
        }

        /// <summary>A unit's facing as the game's battle files hold it (0 south, 1 west, 2 north, 3 east), by its
        /// name, else -1.</summary>
        public static int FacingOf(string name) => Array.IndexOf(FacingNames, name);
        public static readonly string[] FacingNames = { "South", "West", "North", "East" };
    }

    /// <summary>(1.14.0) One of a quest battle's own deploy areas (its Battle's Deploy): the squares where the player's
    /// units may start (1 to 25, within 5 by 5 squares), whether on their upper level, how many units start there (1 to
    /// 5), and which way they face.</summary>
    public sealed class DeployArea
    {
        public List<(int X, int Y)> Squares { get; }
        public bool Upper { get; }
        public int Units { get; }
        /// <summary>0 south, 1 west, 2 north, 3 east, as a unit's facing in the game's battle files.</summary>
        public int Facing { get; }

        public const int MostSquares = 25, MostUnits = 5, MostSpan = 5;

        public DeployArea(List<(int X, int Y)> squares, bool upper, int units, int facing)
        {
            Squares = squares;
            Upper = upper;
            Units = units;
            Facing = facing;
        }

        /// <summary>The squad's 12 bytes, numbered `number`, of map `map`: its middle tile the squares' box's (each
        /// square within 2 of it), its grid laid as the game's grid of orientation 0 (row by row) turned for the
        /// facing (the game's turn: the low half less 1 plus the high half; the facing (0, 3, 2, 1) by turn, as the
        /// formation screen places the units, `event_scripts.squad_tiles`), each square's bit its place in it.</summary>
        public byte[] Squad(int number, int map)
        {
            int minX = int.MaxValue, maxX = int.MinValue, minY = int.MaxValue, maxY = int.MinValue;
            foreach (var (x, y) in Squares)
            {
                minX = Math.Min(minX, x);
                maxX = Math.Max(maxX, x);
                minY = Math.Min(minY, y);
                maxY = Math.Max(maxY, y);
            }
            int mx = (minX + maxX) / 2, my = (minY + maxY) / 2;
            int turn = Array.IndexOf(new[] { 0, 3, 2, 1 }, Facing);
            uint tiles = 0;
            foreach (var (x, y) in Squares)
            {
                var (row, column) = turn switch
                {
                    0 => (y - my + 2, mx - x + 2),
                    1 => (mx - x + 2, my - y + 2),
                    2 => (my - y + 2, x - mx + 2),
                    _ => (x - mx + 2, y - my + 2),
                };
                tiles |= 1u << (row * 5 + column);
            }
            var bytes = new byte[DeploySquads.SquadBytes];
            BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(DeploySquads.Tiles, 4), tiles);
            bytes[DeploySquads.X] = (byte)mx;
            bytes[DeploySquads.Y] = (byte)my;
            bytes[DeploySquads.Level] = (byte)(Upper ? 1 : 0);
            bytes[DeploySquads.Orientation] = (byte)(((turn + 1) % 4) << 4);
            bytes[DeploySquads.Most] = (byte)Units;
            bytes[DeploySquads.Map] = (byte)map;
            BinaryPrimitives.WriteUInt16LittleEndian(bytes.AsSpan(DeploySquads.Own, 2), (ushort)number);
            return bytes;
        }
    }
}
