// Mod Studio Framework: (1.26.0) room for a mod's own items in the game.
// Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi's list of 3 November, his first: "Adding new items to go into the new
// towns outfitter". What was measured (his program read as data, never run;
// WotL Restoration 2.0.7's DLL's strings and metadata read for facts, its code
// never copied; dev/research/sidequests/items.py): the game's items are 1 to
// 253 and 256 to 260, each found through nine small functions (its segment, its
// 12 byte record, its kind's record, its sprite pair, whether it is an item at
// all); the bag of counts (261 bytes), the owned copy, the 85 equipment bonus
// rows and the menus' lists are arrays the game's code reaches in 63 places,
// and 44 walks over the bag stop at 0x105. WotL Restoration gives its own 40
// items (numbered 261 to 315) room as it loads: a page of memory within 2 GB of
// the program holding the arrays with room, the 63 reaches pointed at it, the 44
// bounds raised to 0x13C, the nine functions hooked, 14 list pointers pointed at
// its page's lists, two calls of the item test sent to the game's own test, and
// a thread keeping the game's own arrays and its page's alike.
//
// The framework numbers a mod's items from 316 (past WotL's) to 381 (the walks
// the game bounds with a byte reach no further in place), the same number every
// time (Numbers.json's Items). With WotL Restoration's page already made (all
// the reaches elsewhere), it adopts it: raises the bounds again and hooks the
// nine functions for its own numbers first (native code, only rax and a pushed
// rdx touched). Without, it makes the same room itself, its own page. Either
// way its items' counts are kept in the event variables' last bytes (one a
// number, from the bank's mark down), synced as the game saves and as a save
// loads, as WotL keeps its own.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

namespace ModStudioEventSetup
{
    public static unsafe class ItemRoom
    {
        // --- the numbers -----------------------------------------------------------------------------------------

        /// <summary>The mods' items' numbers: past the game's (to 260) and WotL Restoration's (261 to 315), to 381
        /// (the bounds the game makes as 0xFF plus a byte, and the number less 0x100 compared with a byte, reach no
        /// further where they are).</summary>
        public const int FirstItem = 316, LastItem = 381, Count = LastItem - FirstItem + 1;
        public const int GameLast = 260, WotLFirst = 261, WotLLast = 315;
        /// <summary>The Item table (its loaded language's): sheet 0x2D (read by 0x1EDC50 with 0x3D325C, its row by
        /// 0x3D3AE8); 0x30 bytes a row.</summary>
        public const int ItemSheet = 0x2D, ItemRowBytes = 0x30;
        /// <summary>The most an item's count in the bag is (the game's, as WotL's MaxCount).</summary>
        public const int MostCount = 99;

        // --- the counts in the save: the event variables' tail ----------------------------------------------------

        /// <summary>WotL Restoration's items' counts in the event variables (its SyncNewCounts: from its pointer of
        /// them, + 0x2FC: a mark of 4 bytes, then a count each of its 55 numbers; its TailOffset, TailHeader 4 and
        /// TailLength 59, the length read as past the mark, the farther of its two readings): bytes the framework's
        /// flags never take (flags 4736 to 5239 would be there).</summary>
        public const int WotLTail = 0x2FC, WotLTailEnd = 0x2FC + 4 + 59;
        /// <summary>The byte of the event variables an item's count is kept in: from the bank's mark down, one a
        /// number (0x3FB for 316 to 0x3BA for 381).</summary>
        public static int CountAt(int item) => Framework.MarkAt - 1 - (item - FirstItem);
        public const int CountsFirst = Framework.MarkAt - Count;
        /// <summary>(1.38.0) The eight bytes below the items' counts: the mods' jobs' mark in a save (JobProgress: the
        /// key of the file kept beside the save, the job loaded). No flag was ever given there.</summary>
        public const int JobsMarkBytes = 8, JobsMark = CountsFirst - JobsMarkBytes;

        /// <summary>Whether a quest flag's bit may be given: its byte not WotL Restoration's counts' and not the
        /// items' (1.26.0; no flag given before was ever there).</summary>
        public static bool FlagFree(int bit)
        {
            if (bit < 0 || bit >= Framework.FlagBits)
                return false;
            int at = Framework.BankTail + (bit >> 3);
            return (at < WotLTail || at >= WotLTailEnd) && at < JobsMark;
        }

        // --- the page (made by the framework when no other mod made one) -----------------------------------------

        public const int PageBytes = 0x10000, PageBag = 0, PageOwned = 0x800, PageAttribute = 0x1000,
                         PageAllItems = 0x3000, PageCharts = 0x4000;
        public const int ChartWords = 512, AllItemsWords = 1024, Rows = 255, RowBytes = 26;
        /// <summary>The game's arrays: the bag's and the owned copy's 261 bytes, the 85 bonus rows, the all-items
        /// list's 263 words; the lists' end (0xFF) and the words after it (0xFFFF, as WotL's page holds them).</summary>
        public const int GameBag = 261, GameRows = 85, GameAllItems = 263, ListEnd = 0xFF, ListWall = 0xFFFF;
        /// <summary>The 14 list pointers' lists (each the game's list and its words): the five the menus take by
        /// kind, twice, and the four of the all-items block.</summary>
        public static readonly (int Slot, int List, int Words)[] Slots =
        {
            (0, 0, 141), (1, 1, 30), (2, 2, 38), (3, 3, 34), (4, 4, 21),
            (5, 0, 141), (6, 1, 30), (7, 2, 38), (8, 3, 34), (9, 4, 21),
            (10, 5, 141), (11, 6, 30), (12, 7, 38), (13, 8, 34),
        };

        /// <summary>The value each kind of bound gets for items to LastItem (Count: an id's bound; Last; LastLess; Lea6:
        /// 0xFF plus it; Ax4: the number less 0x100; Row: an equipment bonus row's, every row of 255; Blocks and Stride:
        /// the owned copy's rebuild, eight blocks of 0x80, as WotL's), and the game's own.</summary>
        public static int Value(string kind, bool game)
            => kind switch
            {
                "count" => game ? 0x105 : LastItem + 1,
                "last" => game ? 0x104 : LastItem,
                "lastless" => game ? 0x103 : LastItem - 1,
                "lea6" => game ? 6 : LastItem + 1 - 0xFF,
                "ax4" => game ? 4 : LastItem - 0x100,
                "row" => game ? 0x55 : 0xFF,
                "blocks" => game ? 2 : 8,
                "stride" => game ? 0x7E : 0x78,
                _ => throw new ArgumentException(kind),
            };

        // --- the sites, found by their own bytes ------------------------------------------------------------------

        /// <summary>A place the framework changes or hooks: its pattern (dev/research/sidequests/items.py made each
        /// from his program, every rip distance and 32-bit displacement and every byte another mod changes left out),
        /// where its instruction is in the pattern (Lead; a function's start may be before it, another mod's hook
        /// covering its first bytes), its operand's place and width, the instruction's size, the value his program
        /// holds (a bound's), and for a reach its array and the offset into it.</summary>
        public sealed class Site
        {
            public string Name { get; }
            public string Kind { get; }
            public int[] Pattern { get; }
            public int Lead { get; }
            public int Operand { get; }
            public int Width { get; }
            public int Size { get; }
            public int Old { get; }
            public string Array { get; }
            public int Offset { get; }

            public Site(string name, string kind, string pattern, int lead)
                : this(name, kind, pattern, lead, 0, 0, 0, "", 0) { }

            public Site(string name, string kind, string pattern, int lead, int operand, int width, int old)
                : this(name, kind, pattern, lead, operand, width, 0, "", 0)
            {
                Old = old;
            }

            public Site(string name, string kind, string pattern, int lead, int operand, int size, string array,
                        int offset)
                : this(name, kind, pattern, lead, operand, 4, size, array, offset) { }

            Site(string name, string kind, string pattern, int lead, int operand, int width, int size, string array,
                 int offset)
            {
                Name = name;
                Kind = kind;
                Pattern = Places.Pattern(pattern);
                Lead = lead;
                Operand = operand;
                Width = width;
                Size = size;
                Array = array;
                Offset = offset;
            }

            public bool Reach => Kind == "rip" || Kind == "abs";
            public bool Bound => !Reach && Kind != "call" && Kind != "function";
        }

        public static readonly Site[] Sites =
        {
            // Made by dev/research/sidequests/items.py from his program (17 September, 12,158,720 bytes).
            new Site("reach0", "rip", "48 8D 0D ?? ?? ?? ?? 48 03 F9", 0, 3, 7, "attribute", 0),
            new Site("reach1", "rip", "48 8D 0D ?? ?? ?? ?? 80 3C 0B 00", 0, 3, 7, "bag", 0),
            new Site("reach2", "rip", "4C 8D 05 ?? ?? ?? ?? 42 02 34 07", 0, 3, 7, "bag", 0),
            new Site("reach3", "rip", "48 8D 0D ?? ?? ?? ?? 0F B6 3C 0E", 0, 3, 7, "bag", 0),
            new Site("reach4", "rip", "4C 8D 05 ?? ?? ?? ?? 42 88 0C 00", 0, 3, 7, "bag", 0),
            new Site("reach5", "rip", "49 8B C7 48 8D 15 ?? ?? ?? ??", 3, 3, 7, "bag", 0),
            new Site("reach6", "rip", "41 8B C2 48 8D 15 ?? ?? ?? ??", 3, 3, 7, "bag", 0),
            new Site("reach7", "rip", "48 8D 15 ?? ?? ?? ?? 48 8B C5 49 8D 8B ?? ?? ?? ??", 0, 3, 7, "bag", 0),
            new Site("reach8", "abs", "0F B7 01 0F B6 84 10 ?? ?? ?? ??", 3, 4, 8, "bag", 0),
            new Site("reach9", "abs", "46 00 AC 07 ?? ?? ?? ?? 33 C9", 0, 4, 8, "bag", 0),
            new Site("reach10", "abs", "8A 84 39 ?? ?? ?? ?? 3C 63 73 0A", 0, 3, 7, "bag", 0),
            new Site("reach11", "abs", "88 84 39 ?? ?? ?? ?? 48 03 D6", 0, 3, 7, "bag", 0),
            new Site("reach12", "rip", "48 8D 05 ?? ?? ?? ?? 48 03 D0 EB 02", 0, 3, 7, "attribute", 0),
            new Site("reach13", "abs", "41 0F B6 94 1B ?? ?? ?? ?? 41 83 F8 36", 0, 5, 9, "bag", 0),
            new Site("reach14", "rip", "48 8D 0D ?? ?? ?? ?? 48 8B C6 0F 10 07", 0, 3, 7, "bag", 0),
            new Site("reach15", "rip", "48 8D 0D ?? ?? ?? ?? 48 8B C6 0F 10 01", 0, 3, 7, "bag", 0),
            new Site("reach16", "abs", "43 8A 84 05 ?? ?? ?? ?? 0F 85 D4 00 00 00", 0, 4, 8, "bag", 0),
            new Site("reach17", "abs", "43 88 8C 05 ?? ?? ?? ?? 3A C1", 0, 4, 8, "bag", 0),
            new Site("reach18", "abs", "43 8A 84 04 ?? ?? ?? ?? 84 C0", 0, 4, 8, "bag", 0),
            new Site("reach19", "abs", "43 88 84 04 ?? ?? ?? ?? 88 9E ?? ?? ?? ??", 0, 4, 8, "bag", 0),
            new Site("reach20", "abs", "43 8A 84 08 ?? ?? ?? ?? 84 C0", 0, 4, 8, "bag", 0),
            new Site("reach21", "abs", "43 88 84 08 ?? ?? ?? ?? B8 6F 01 00 00", 0, 4, 8, "bag", 0),
            new Site("reach22", "abs", "46 38 BC 02 ?? ?? ?? ?? 75 11", 0, 4, 8, "bag", 0),
            new Site("reach23", "rip", "C7 05 ?? ?? ?? ?? 05 02 01 01", 0, 2, 10, "bag", 240),
            new Site("reach24", "rip", "C7 05 ?? ?? ?? ?? 01 01 01 02", 0, 2, 10, "bag", 244),
            new Site("reach25", "rip", "C7 05 ?? ?? ?? ?? 01 01 01 01", 0, 2, 10, "bag", 248),
            new Site("reach26", "rip", "66 C7 05 ?? ?? ?? ?? 01 02 C6 05 ?? ?? ?? ?? 01", 0, 3, 9, "bag", 252),
            new Site("reach27", "rip", "C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01", 0, 2, 7, "bag", 77),
            new Site("reach28", "rip", "C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01 C3", 0, 2, 7, "bag", 128),
            new Site("reach29", "rip", "C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01 C3", 0, 2, 7, "bag", 144),
            new Site("reach30", "rip", "C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01 C3", 0, 2, 7, "bag", 172),
            new Site("reach31", "rip", "C6 05 ?? ?? ?? ?? 01 C6 05 ?? ?? ?? ?? 01 C3", 0, 2, 7, "bag", 51),
            new Site("reach32", "rip", "C6 05 ?? ?? ?? ?? 01 C3 CC CC", 0, 2, 7, "bag", 59),
            new Site("reach33", "abs", "42 C6 84 00 ?? ?? ?? ?? 00 48 FF C0", 0, 4, 9, "bag", 0),
            new Site("reach34", "abs", "42 0F B6 8C 30 ?? ?? ?? ?? 3B CF", 0, 5, 9, "bag", 0),
            new Site("reach35", "abs", "42 C6 84 30 ?? ?? ?? ?? 00 0F B6 05 ?? ?? ?? ??", 0, 4, 9, "bag", 0),
            new Site("reach36", "abs", "42 88 8C 30 ?? ?? ?? ?? 40 B7 01", 0, 4, 8, "bag", 0),
            new Site("reach37", "rip", "4C 8D 0D ?? ?? ?? ?? 33 C0 43 0F B6 0C 08", 0, 3, 7, "bag", 0),
            new Site("reach38", "rip", "48 8D 35 ?? ?? ?? ?? BB 01 00 00 00", 0, 3, 7, "allitems", -486),
            new Site("reach39", "rip", "48 8D 0D ?? ?? ?? ?? 66 39 29", 0, 3, 7, "allitems", 0),
            new Site("reach40", "rip", "66 89 1D ?? ?? ?? ?? EB 0E 48 8D 15 ?? ?? ?? ??", 0, 3, 7, "allitems", 0),
            new Site("reach41", "rip", "48 8D 15 ?? ?? ?? ?? 8B CB E8 CF FC FF FF", 0, 3, 7, "allitems", 0),
            new Site("reach42", "rip", "48 8D 0D ?? ?? ?? ?? E8 19 FB FF FF", 0, 3, 7, "allitems", 0),
            new Site("reach43", "rip", "E8 35 20 03 00 48 85 C0 74 11 0F B6 08 66 41 89 4B 18 0F B6 40 01 66 41 89 43 22 40 80 FE ?? 73 0E 48 6B DE 1A 48 8D 05 ?? ?? ?? ??", 37, 3, 7, "attribute", 0),
            new Site("reach44", "rip", "48 8D 05 ?? ?? ?? ?? 48 03 D8 EB 02", 0, 3, 7, "attribute", 0),
            new Site("reach45", "abs", "42 FE 84 23 ?? ?? ?? ?? 48 83 C7 02", 0, 4, 8, "bag", 0),
            new Site("reach46", "abs", "42 FE 84 38 ?? ?? ?? ?? EB 26", 0, 4, 8, "bag", 0),
            new Site("reach47", "rip", "E8 67 AB 2F 00 48 8D 0D ?? ?? ?? ?? 48 8B C3 48 8D 15 ?? ?? ?? ??", 15, 3, 7, "bag", 0),
            new Site("reach48", "rip", "E8 79 A2 2F 00 48 8D 0D ?? ?? ?? ??", 5, 3, 7, "bag", 0),
            new Site("reach49", "rip", "48 8D 4C 24 20 48 8D 15 ?? ?? ?? ?? 44 8D 40 7E", 5, 3, 7, "bag", 0),
            new Site("reach50", "abs", "0F B7 01 0F B6 84 10 ?? ?? ?? ??", 3, 4, 8, "bag", 0),
            new Site("reach51", "rip", "48 8D 0D ?? ?? ?? ?? FE 04 0B", 0, 3, 7, "bag", 0),
            new Site("reach52", "abs", "42 38 9C 28 ?? ?? ?? ?? 74 08", 0, 4, 8, "bag", 0),
            new Site("reach53", "rip", "66 89 3D ?? ?? ?? ?? 48 81 C4 20 04 00 00", 0, 3, 7, "allitems", 0),
            new Site("reach54", "rip", "4C 8D 2D ?? ?? ?? ?? 41 BB 7F 01 00 00", 0, 3, 7, "bag", 0),
            new Site("reach55", "rip", "48 8D 0D ?? ?? ?? ?? 80 3C 08 00", 0, 3, 7, "bag", 0),
            new Site("reach56", "abs", "0F B6 8C 08 ?? ?? ?? ?? B8 00 40 00 00", 0, 4, 8, "owned", 0),
            new Site("reach57", "abs", "41 0F B6 8C 1A ?? ?? ?? ?? 2B C8", 0, 5, 9, "owned", 0),
            new Site("reach58", "rip", "48 8D 3D ?? ?? ?? ?? 48 8B CF 48 8D 15 ?? ?? ?? ??", 0, 3, 7, "owned", 0),
            new Site("reach59", "rip", "48 8B CF 48 8D 15 ?? ?? ?? ?? 44 8D 40 ??", 3, 3, 7, "bag", 0),
            new Site("reach60", "abs", "42 80 BC 20 ?? ?? ?? ?? 00 74 4A", 0, 4, 9, "owned", 0),
            new Site("reach61", "rip", "E8 47 23 F2 FF 48 85 C0 74 11 0F B6 08 66 41 89 4B 18 0F B6 40 01 66 41 89 43 22 40 80 FE ?? 73 0E 48 6B DE 1A 48 8D 05 ?? ?? ?? ??", 37, 3, 7, "attribute", 0),
            new Site("reach62", "abs", "42 80 BC 18 ?? ?? ?? ?? 00 0F 84 CE 00 00 00", 0, 4, 9, "owned", 0),
            new Site("bound0", "lastless", "41 B8 ?? ?? ?? ?? 66 23 C8 8D 41 FF", 0, 2, 4, 259),
            new Site("bound1", "count", "B8 ?? ?? ?? ?? 66 3B C8 72 03", 0, 1, 4, 261),
            new Site("bound2", "count", "81 FE ?? ?? ?? ?? 73 0B 48 8D 0D ?? ?? ?? ??", 0, 2, 4, 261),
            new Site("bound3", "last", "B8 ?? ?? ?? ?? 66 3B D8 0F 87 B9 00 00 00", 0, 1, 4, 260),
            new Site("bound4", "last", "B8 ?? ?? ?? ?? 41 8B F1 49 8B D8", 0, 1, 4, 260),
            new Site("bound5", "count", "B8 ?? ?? ?? ?? 66 3B 02 76 1F", 0, 1, 4, 261),
            new Site("bound6", "count", "48 3D ?? ?? ?? ?? 0F 83 C3 00 00 00", 0, 2, 4, 261),
            new Site("bound7", "count", "81 FB ?? ?? ?? ?? 0F 8C 15 FF FF FF", 0, 2, 4, 261),
            new Site("bound8", "count", "81 FF ?? ?? ?? ?? 0F 8C E6 FE FF FF", 0, 2, 4, 261),
            new Site("bound9", "count", "81 FB ?? ?? ?? ?? 7C 83 4C 8B AC 24 ?? ?? ?? ??", 0, 2, 4, 261),
            new Site("bound10", "count", "81 FF ?? ?? ?? ?? 0F 8C 0A FF FF FF", 0, 2, 4, 261),
            new Site("bound11", "count", "B8 ?? ?? ?? ?? 66 3B 04 51 76 05", 0, 1, 4, 261),
            new Site("bound12", "count", "B8 ?? ?? ?? ?? 66 41 3B 00 0F 86 C7 00 00 00", 0, 1, 4, 261),
            new Site("bound13", "count", "B8 ?? ?? ?? ?? 66 41 3B 04 4B", 0, 1, 4, 261),
            new Site("bound14", "lea6", "45 8D 53 ?? 44 3B C1", 0, 3, 1, 6),
            new Site("bound15", "lea6", "45 8D 77 ?? 0F B7 CB E8 FE 2E 03 00", 0, 3, 1, 6),
            new Site("bound16", "lea6", "45 8D 77 ?? 0F B7 CB E8 05 2E 03 00", 0, 3, 1, 6),
            new Site("bound17", "lea6", "45 8D 77 ?? 0F B7 CB 0F B7 FB", 0, 3, 1, 6),
            new Site("bound18", "lea6", "8D 7D ?? 0F B7 CB E8 2C 2D 03 00", 0, 2, 1, 6),
            new Site("bound19", "count", "B9 ?? ?? ?? ?? 66 3B 08 77 04", 0, 1, 4, 261),
            new Site("bound20", "count", "B8 ?? ?? ?? ?? 66 41 3B C3 0F 86 16 01 00 00", 0, 1, 4, 261),
            new Site("bound21", "row", "80 7F 07 ?? 73 14 0F B6 47 07", 0, 3, 1, 85),
            new Site("bound22", "row", "80 78 07 ?? 73 14 0F B6 48 07", 0, 3, 1, 85),
            new Site("bound23", "row", "80 78 07 ?? 73 14 0F B6 40 07", 0, 3, 1, 85),
            new Site("bound24", "row", "40 80 FE ?? 73 0E 48 6B DE 1A 48 8D 05 ?? ?? ?? ?? 48 03 D8 0F B6 43 03 66 41 89 03 0F B6 43 02 66 41 89 43 02 0F B6 43 04 66 41 89 43 04 0F B6 03 66 41 89 43 12 0F B6 43 01 66 41 89 43 1C 48 8B 5C 24 30 48 8B 6C 24 38 48 8B 74 24 40 48 8B 7C 24 48 48 83 C4 20 41 5E C3 CC 4C 8B DC", 0, 3, 1, 85),
            new Site("bound25", "row", "40 80 FE ?? 73 0E 48 6B DE 1A 48 8D 05 ?? ?? ?? ?? 48 03 D8 0F B6 43 03 66 41 89 03 0F B6 43 02 66 41 89 43 02 0F B6 43 04 66 41 89 43 04 0F B6 03 66 41 89 43 12 0F B6 43 01 66 41 89 43 1C 48 8B 5C 24 30 48 8B 6C 24 38 48 8B 74 24 40 48 8B 7C 24 48 48 83 C4 20 41 5E C3 CC CC", 0, 3, 1, 85),
            new Site("bound26", "lea6", "8D 4A ?? 66 3B C2 74 05 66 3B C8 77 04 0F B7 43 22 66 89 05 ?? ?? ?? ?? 0F B7 43 24 66 3B C2 74 05 66 3B C8 77 04 0F B7 43 26 66 89 05 ?? ?? ?? ?? 0F B7 43 1A 66 89 05 ?? ?? ?? ?? 0F B7 43 1C 66 89 05 ?? ?? ?? ?? 0F B7 43 1E 66 89 05 ?? ?? ?? ?? 41 83 CC FF 48 8D 35 ?? ?? ?? ?? 41 0F B7 09 E8 79 1E 09 00", 0, 2, 1, 6),
            new Site("bound27", "lea6", "8D 4A ?? 66 3B C2 74 05 66 3B C8 77 04 0F B7 43 22 66 89 05 ?? ?? ?? ?? 0F B7 43 24 66 3B C2 74 05 66 3B C8 77 04 0F B7 43 26 66 89 05 ?? ?? ?? ?? 0F B7 43 1A 66 89 05 ?? ?? ?? ?? 0F B7 43 1C 66 89 05 ?? ?? ?? ?? 0F B7 43 1E 66 89 05 ?? ?? ?? ?? 41 83 CC FF 48 8D 35 ?? ?? ?? ?? 41 0F B7 09 E8 A1 3F FF FF", 0, 2, 1, 6),
            new Site("bound28", "lea6", "8D 4A ?? 66 3B C2 74 05 66 3B C8 77 04 0F B7 43 22 66 89 05 ?? ?? ?? ?? 0F B7 43 24 66 3B C2 74 05 66 3B C8 77 04 0F B7 43 26 66 89 05 ?? ?? ?? ?? 0F B7 43 1A 66 89 05 ?? ?? ?? ?? 0F B7 43 1C 66 89 05 ?? ?? ?? ?? 0F B7 43 1E 66 89 05 ?? ?? ?? ?? 41 83 CC FF 48 8D 35 ?? ?? ?? ?? 41 0F B7 09 E8 59 A7 FD FF", 0, 2, 1, 6),
            new Site("bound29", "lea6", "8D 4A ?? 66 3B C2 74 05 66 3B C8 77 07 0F B7 05 ?? ?? ?? ?? 66 89 05 ?? ?? ?? ?? 48 8B 05 ?? ?? ?? ??", 0, 2, 1, 6),
            new Site("bound30", "lea6", "8D 4A ?? 66 3B C2 74 05 66 3B C8 77 04 0F B7 43 22 66 89 05 ?? ?? ?? ?? 0F B7 43 24 66 3B C2 74 05 66 3B C8 77 04 0F B7 43 26 66 89 05 ?? ?? ?? ?? 0F B7 43 1A 66 89 05 ?? ?? ?? ?? 0F B7 43 1C 66 89 05 ?? ?? ?? ?? 0F B7 43 1E 66 89 05 ?? ?? ?? ?? 41 83 CC FF 48 8D 35 ?? ?? ?? ?? 41 0F B7 09 E8 9D D8 F7 FF", 0, 2, 1, 6),
            new Site("bound31", "lea6", "8D 4A ?? 66 3B C2 74 05 66 3B C8 77 07 0F B7 05 ?? ?? ?? ?? 66 89 05 ?? ?? ?? ?? 0F B7 05 ?? ?? ?? ??", 0, 2, 1, 6),
            new Site("bound32", "lea6", "8D 4A ?? 66 3B C2 74 05 66 3B C8 77 12", 0, 2, 1, 6),
            new Site("bound33", "lea6", "44 8D 75 ?? 0F B7 43 20", 0, 3, 1, 6),
            new Site("bound34", "lea6", "8D 4A ?? 66 3B C2 74 05 66 3B C8 77 04 0F B7 47 16", 0, 2, 1, 6),
            new Site("bound35", "count", "B9 ?? ?? ?? ?? 66 3B C6 74 05", 0, 1, 4, 261),
            new Site("bound36", "lea6", "45 8D 41 ?? 0F B6 43 2B", 0, 3, 1, 6),
            new Site("bound37", "lea6", "8D 77 ?? 66 44 3B CF", 0, 2, 1, 6),
            new Site("bound38", "count", "BA ?? ?? ?? ?? 66 44 39 68 20", 0, 1, 4, 261),
            new Site("bound39", "count", "41 B8 ?? ?? ?? ?? 66 3B CE 74 08", 0, 2, 4, 261),
            new Site("bound40", "ax4", "66 83 F8 ?? 77 0B E8 ED 02 00 00", 0, 3, 1, 4),
            new Site("bound41", "ax4", "66 83 F8 ?? 77 07 E8 C6 02 00 00", 0, 3, 1, 4),
            new Site("bound42", "blocks", "B8 ?? ?? ?? ?? 48 8D 3D ?? ?? ?? ?? 48 8B CF", 0, 1, 4, 2),
            new Site("bound43", "stride", "44 8D 40 ?? 0F 10 02 0F 10 4A 10 0F 11 01 0F 10 42 20 0F 11 49 10 0F 10 4A 30 0F 11 41 20 0F 10 42 40 0F 11 49 30 0F 10 4A 50 0F 11 41 40 0F 10 42 60 0F 11 49 50 0F 10 4A 70 49 03 D0 0F 11 41 60 49 03 C8 0F 11 49 F0 48 83 E8 01 75 B6 8B 02 48 8D 35 ?? ?? ?? ??", 0, 3, 1, 126),
            new Site("low0", "call", "E8 ?? ?? ?? ?? 85 C0 74 07 0F B7 C6", 0, 1, 4, 2854588),
            new Site("low1", "call", "E8 ?? ?? ?? ?? 85 C0 74 07 0F B7 03", 0, 1, 4, 2854588),
            new Site("SecondaryItemType", "function", "B7 C1 66 2B C2 66 83 F8 04", -14),
            new Site("ItemCommon", "function", "AA 73 D4 FF 48 8D", -14),
            new Site("ItemWeapon", "function", "0F B7 D1 41 0F B7 C9 66 44 2B D0 E8 3A FF FF FF", -14),
            new Site("ItemShield", "function", "0F B7 D1 41 0F B7 C9 66 44 2B D0 E8 DA FE FF FF", -14),
            new Site("ItemArmor", "function", "0F B7 D1 41 0F B7 C9 66 44 2B D0 E8 72 FE FF FF", -14),
            new Site("ItemAccessory", "function", "0F B7 D1 41 0F B7 C9 66 44 2B D0 E8 0E FE FF FF", -14),
            new Site("ItemChemist", "function", "0F B7 D1 41 0F B7 C9 66 44 2B D0 E8 AA FD FF FF", -14),
            new Site("ItemSpritePair", "function", "48 63 D0 4C 8D 0D ?? ?? ?? ??", -14),
            new Site("IsValidItem", "function", "FC 00 00 00 66 3B", -14),
            new Site("Save", "function", "41 56 41 57 48 83 EC 40 48 8B 05 ?? ?? ?? ?? 44 8B E1", -14),
            new Site("Stock", "function", "41 54 41 55 41 56 41 57 48 83 EC 28 33 C0", -14),
            // (1.26.0) The Icon table's two paths of an item's icon (0xFC0D8, 0xFC14C: the base art's path's shape,
            // its row 0x0C and 0x0D), their first 18 bytes not looked at.
            new Site("IconPath", "function", "?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? 48 33 C4 48 89 84 24 30 01 00 00 49 63 F8 8B DA 48 8B F1 48 8D 54 24 20 41 B0 01 B9 0C 00 00 00 41 B9 04 01 00 00 E8", 0),
            new Site("SmallIconPath", "function", "?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? 48 33 C4 48 89 84 24 30 01 00 00 49 63 F8 8B DA 48 8B F1 48 8D 54 24 20 41 B0 01 B9 0D 00 00 00 41 B9 04 01 00 00 E8", 0),
        };

        /// <summary>The two walks over the Poachers' Den's stock (0x11A7700: a count an item, the den's buy list's; the
        /// stock function's second loop, 0x289072, through 0x287564, 0x28756F), which no reach moves: kept as found, so
        /// the den never reads past its 261 for the mods' items (WotL Restoration raises them to its 0x13C).</summary>
        public static readonly HashSet<string> KeptBounds = new HashSet<string>(StringComparer.Ordinal) { "bound1", "bound9" };

        public static readonly string[] Arrays = { "bag", "owned", "attribute", "allitems" };
        public static readonly string[] Getters = { "SecondaryItemType", "ItemCommon", "ItemWeapon", "ItemShield",
                                                    "ItemArmor", "ItemAccessory", "ItemChemist", "ItemSpritePair",
                                                    "IsValidItem" };

        /// <summary>What was found in a program: each site's address (its instruction, or a function's start), each
        /// array's place (from where its reaches lead: the game's, or another mod's page), whether another mod moved
        /// them (WotL Restoration's page), and what wasn't found.</summary>
        public sealed class Found
        {
            public Dictionary<string, int> At { get; } = new Dictionary<string, int>(StringComparer.Ordinal);
            /// <summary>Each reach, by its instruction's address: its site.</summary>
            public SortedDictionary<int, Site> Reaches { get; } = new SortedDictionary<int, Site>();
            /// <summary>Each array's place, counted from the program's start (another mod's page may be past it).</summary>
            public Dictionary<string, long> Array { get; } = new Dictionary<string, long>(StringComparer.Ordinal);
            /// <summary>Each bound's value as found.</summary>
            public Dictionary<string, int> Values { get; } = new Dictionary<string, int>(StringComparer.Ordinal);
            public List<string> Missing { get; } = new List<string>();
            public bool Moved { get; set; }
            /// <summary>The 14 list pointers' place (the first five, the second five, the last four).</summary>
            public int[] SlotsAt { get; } = new int[3];
            public bool Ok => Missing.Count == 0;
        }

        static long TargetOf(ReadOnlySpan<byte> image, int at, Site s)
        {
            int disp = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at + s.Operand, 4));
            return s.Kind == "rip" ? (long)at + s.Size + disp : disp;
        }

        static int ValueAt(ReadOnlySpan<byte> image, int at, Site s)
            => s.Width == 1 ? image[at + s.Operand] : BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at + s.Operand, 4));

        /// <summary>Every site found in a program laid out as it lies in memory. A reach whose pattern the program has
        /// twice (the same code over another table) is the one reaching its array where the others say it is.</summary>
        public static Found Find(ReadOnlySpan<byte> image, List<Section> sections)
        {
            var found = new Found();
            var twins = new List<(Site, List<int>)>();
            foreach (var s in Sites)
            {
                var matches = Places.Search(image, sections, s.Pattern);
                if (s.Reach && matches.Count > 1)
                {
                    twins.Add((s, matches));
                    continue;
                }
                if (matches.Count != 1)
                {
                    found.Missing.Add($"{Name(s)} ({matches.Count} places like it, not 1)");
                    continue;
                }
                int at = matches[0] + s.Lead;
                found.At[s.Name] = at;
                if (s.Reach)
                {
                    found.Reaches[at] = s;
                    long array = TargetOf(image, at, s) - s.Offset;
                    if (found.Array.TryGetValue(s.Array, out long had) && had != array)
                        found.Missing.Add($"{Name(s)} (it reaches another {s.Array} than the others do)");
                    found.Array[s.Array] = array;
                }
                else if (s.Bound)
                    found.Values[s.Name] = ValueAt(image, at, s);
            }
            foreach (var (s, matches) in twins)
            {
                var reached = new List<int>();
                foreach (int m in matches)
                {
                    int at = m + s.Lead;
                    if (found.Array.TryGetValue(s.Array, out long array) && TargetOf(image, at, s) - s.Offset == array)
                        reached.Add(at);
                }
                // Each twin reaching the array is a reach of it: another site of the table has its own place.
                int own = reached.Find(at => !found.Reaches.ContainsKey(at));
                if (reached.Count == 0 || !reached.Exists(at => !found.Reaches.ContainsKey(at)))
                {
                    found.Missing.Add($"{Name(s)} ({matches.Count} places like it, none reaching the {s.Array})");
                    continue;
                }
                found.At[s.Name] = own;
                found.Reaches[own] = s;
            }
            foreach (var array in Arrays)
                if (!found.Array.ContainsKey(array))
                    found.Missing.Add($"the items' {array} (no reach of it found)");
            if (!found.Ok)
                return found;
            // The game's arrays are in the program; another mod's page past it (WotL Restoration's is above it).
            int end = 0;
            foreach (var section in sections)
                end = Math.Max(end, section.Address + section.Size);
            int outside = 0;
            foreach (var array in Arrays)
                if (found.Array[array] < 0 || found.Array[array] >= end)
                    outside++;
            if (outside != 0 && outside != Arrays.Length)
            {
                found.Missing.Add("the items' arrays (some are moved out of the program, some not)");
                return found;
            }
            found.Moved = outside == Arrays.Length;
            // Each bound as the game has it, or, its arrays moved, as raised by another mod (to no further than ours).
            // The 14 list pointers' three places: each the lea a housekeeper takes them by, just before its walk's bound
            // (the Items tab's, the third copy's, the equip picker's).
            var leas = new (string Bound, int Back, string Bytes)[]
            {
                ("bound15", 7, "4C 8D 25"), ("bound13", 0x19, "4C 8D 1D"), ("bound16", 0xC, "4C 8D 25"),
            };
            for (int k = 0; k < leas.Length; k++)
            {
                int lea = found.At[leas[k].Bound] - leas[k].Back;
                if (!Places.At(image, lea, Places.Pattern(leas[k].Bytes)))
                {
                    found.Missing.Add("the menus' lists' pointers (their lea isn't before their walk)");
                    return found;
                }
                found.SlotsAt[k] = lea + 7 + BinaryPrimitives.ReadInt32LittleEndian(image.Slice(lea + 3, 4));
                if (found.SlotsAt[k] < 0 || found.SlotsAt[k] + 40 > image.Length)
                {
                    found.Missing.Add("the menus' lists' pointers (outside the program)");
                    return found;
                }
            }
            foreach (var s in Sites)
            {
                if (!s.Bound || !found.Values.TryGetValue(s.Name, out int value))
                    continue;
                int game = Value(s.Kind, true), ours = Value(s.Kind, false);
                bool good = found.Moved ? (s.Kind == "row" ? value == 0x55 || value == 0xFF
                                           : s.Kind == "blocks" ? value == 2 || value == 8
                                           : s.Kind == "stride" ? value == 0x7E || value == 0x78
                                           : value >= game && value <= ours)
                                        : value == game;
                if (!good)
                    found.Missing.Add($"{Name(s)} (its bound is {value}, not {(found.Moved ? $"{game} to {ours}" : game)})");
            }
            return found;
        }

        static string Name(Site s) => s.Kind switch
        {
            "function" => $"the item's {s.Name} function",
            "call" => "a call of the item test",
            "rip" or "abs" => $"a reach of the items' {s.Array}",
            _ => "a walk over the items",
        };

        // --- the plan: numbers, bonus rows -------------------------------------------------------------------------

        /// <summary>A mod's item given its number and (with bonuses) its bonus row.</summary>
        public sealed class Given
        {
            public ModItem Item { get; }
            public int Number { get; }
            public int Row { get; }
            public string Who => $"{Item.Name} ({Item.ModName})";

            public Given(ModItem item, int number, int row)
            {
                Item = item;
                Number = number;
                Row = row;
            }
        }

        /// <summary>Each mod's item numbered (Numbers.json's Items, from FirstItem; a number given never goes to another
        /// name) and its bonuses given a row from `firstRow` (past every row an item of the game's, or another mod's,
        /// names), in the mods' order. What can't be given is said, and the item left out.</summary>
        public static List<Given> Plan(IList<ModItem> items, Numbers numbers, int firstRow, List<string> said)
        {
            var given = new List<Given>();
            int row = firstRow;
            foreach (var item in items)
            {
                int n = numbers.Give("Items", item.Key, Range(FirstItem, LastItem), _ => true, out bool moved);
                if (n < 0)
                {
                    said.Add($"{item.Name} ({item.ModName}) is left out: no item number is left (the mods' items are "
                             + $"{FirstItem} to {LastItem}).");
                    continue;
                }
                int r = 0;
                if (item.Bonus != null)
                {
                    if (row >= Rows)
                    {
                        said.Add($"{item.Name} ({item.ModName}) is left out: no equipment bonus row is left for it "
                                 + $"(the game has {Rows}).");
                        continue;
                    }
                    r = row++;
                }
                given.Add(new Given(item, n, r));
            }
            return given;
        }

        /// <summary>What is said of an item as it is given its number.</summary>
        public static string Line(Given g)
            => $"{g.Who} is item {g.Number}, {ItemFile.KindWords[(int)g.Item.Kind]}"
               + (g.Item.Bonus != null ? $", its equipment bonuses in row {g.Row}" : "")
               + (g.Item.Icon > 0 ? $", its icon the game's item {g.Item.Icon}'s." : ", its icon its own.");

        static IEnumerable<int> Range(int first, int last)
        {
            for (int n = first; n <= last; n++)
                yield return n;
        }

        /// <summary>(1.27.0) The game's 15 towns by their places (0 to 14), as the game's English PlaceName rows name
        /// them: the Outfitters a mod's item may be sold at besides its mod's own towns.</summary>
        public static readonly string[] TownNames =
        {
            "Royal City of Lesalia", "Riovanes Castle", "Eagrose Castle", "Lionel Castle", "Limberry Castle",
            "Zeltennia Castle", "Magick City of Gariland", "Walled City of Yardrow", "Mining Town of Gollund",
            "Merchant City of Dorter", "Castled City of Zaland", "Clockwork City of Goug", "Port City of Warjilis",
            "Free City of Bervenia", "Trade City of Sal Ghidos",
        };

        /// <summary>(1.27.0) Each of the game's towns that sells a mod's item, and the items it sells, in the plan's
        /// order.</summary>
        public static Dictionary<int, List<int>> TownItems(IEnumerable<Given> given)
        {
            var towns = new Dictionary<int, List<int>>();
            foreach (var g in given)
                foreach (int town in g.Item.Shops)
                {
                    if (!towns.TryGetValue(town, out var list))
                        towns[town] = list = new List<int>();
                    list.Add(g.Number);
                }
            return towns;
        }

        /// <summary>(1.27.0) What is said of an item sold at the game's own Outfitters.</summary>
        public static string ShopsLine(Given g)
        {
            var names = new List<string>();
            foreach (int town in g.Item.Shops)
                names.Add(TownNames[town]);
            string them = names.Count == 1 ? names[0]
                          : string.Join(", ", names.GetRange(0, names.Count - 1)) + " and " + names[^1];
            return $"{g.Who} is sold at the Outfitter{(names.Count == 1 ? "" : "s")} of {them}.";
        }

        /// <summary>An item's 12 byte record as the game is given it: the mod's, its kind's type flag set, its kind's
        /// record's number 0 (its records are found by its number), its bonus row the framework's.</summary>
        public static byte[] Record(Given g)
        {
            var record = (byte[])g.Item.Record.Clone();
            record[ItemFile.FlagsAt] = (byte)((record[ItemFile.FlagsAt] & ~ItemFile.KindMask)
                                              | ItemFile.KindFlags[(int)g.Item.Kind]);
            record[ItemFile.KindAt] = 0;
            record[ItemFile.BonusAt] = (byte)g.Row;
            return record;
        }

        /// <summary>The segment an item of a kind is in (SecondaryItemType's answer: the remaster's own, as its 256 to
        /// 260 are; 0x67FB78 gives each its kind, 5 to 9, which ItemWeapon to ItemChemist look for).</summary>
        public static readonly sbyte[] Segments = { 7, 9, 10, 11, 12, 13 };
        /// <summary>Each getter's kind's segment's kind (0x67FB78 of the segments above).</summary>
        public static readonly int[] KindOfSegment = { 5, 6, 7, 7, 8, 9 };

        // --- the items' own data and the nine functions' native code ---------------------------------------------

        /// <summary>The items' data (a RW block): seven tables of Count pointers (common, weapon, shield, armor,
        /// accessory, chemist, sprite pair; 0 where an item has none), the valid and segment bytes, the records, the
        /// zero record unused numbers' common record is, and a slot for each function's way to the game's (or another
        /// mod's) own.</summary>
        public const int TablePointers = 0, Tables = 7, ValidAt = Tables * Count * 8, SegmentAt = ValidAt + Count,
                         CommonsAt = (SegmentAt + Count + 15) & ~15, KindsAt = CommonsAt + Count * 12,
                         PairsAt = KindsAt + Count * 8, ZeroAt = PairsAt + Count * 2, SlotsAt = (ZeroAt + 16 + 7) & ~7,
                         DataBytes = SlotsAt + 9 * 8;

        /// <summary>The items' data at `at`: given items' records, pointers and bytes; unused numbers invalid, their
        /// segment -1, their common record zeros. (2.0.0) `first`: the number the block's first place is (the mods'
        /// own items' by default; War of the Lions' items have a block of their own, from WotLFirst, laid out alike:
        /// their 55 numbers fit the mods' 66 places).</summary>
        public static byte[] Data(List<Given> given, ulong at, int first = FirstItem)
        {
            var data = new byte[DataBytes];
            for (int i = 0; i < Count; i++)
            {
                data[SegmentAt + i] = 0xFF;
                Pointer(data, 0, i, at + ZeroAt);
            }
            foreach (var g in given)
            {
                int i = g.Number - first;
                if (i < 0 || i >= Count)
                    throw new ArgumentException($"item {g.Number} isn't one of the block's ({first} on)");
                int kind = (int)g.Item.Kind;
                data[ValidAt + i] = 1;
                data[SegmentAt + i] = (byte)Segments[kind];
                Record(g).CopyTo(data, CommonsAt + i * 12);
                g.Item.KindRecord.CopyTo(data, KindsAt + i * 8);
                Pointer(data, 0, i, at + (ulong)(CommonsAt + i * 12));
                // ItemWeapon 1, ItemShield 2, ItemArmor 3 (a head's and a body's), ItemAccessory 4, ItemChemist 5.
                int table = kind switch
                {
                    (int)ItemKind.Weapon => 1, (int)ItemKind.Shield => 2, (int)ItemKind.Head => 3,
                    (int)ItemKind.Body => 3, (int)ItemKind.Accessory => 4, _ => 5,
                };
                Pointer(data, table, i, at + (ulong)(KindsAt + i * 8));
                if (g.Item.SpritePair.Length == ItemFile.PairBytes)
                {
                    g.Item.SpritePair.CopyTo(data, PairsAt + i * 2);
                    Pointer(data, 6, i, at + (ulong)(PairsAt + i * 2));
                }
            }
            return data;
        }

        static void Pointer(byte[] data, int table, int i, ulong value)
            => BinaryPrimitives.WriteUInt64LittleEndian(data.AsSpan(TablePointers + (table * Count + i) * 8), value);

        /// <summary>The nine functions' native code, each: the number (cx) less FirstItem below Count, its answer from
        /// the items' data (rdx pushed and popped: rax and the flags are all it changes, as the game's own leave rax
        /// theirs); else on to the game's (or another mod's hook) by its slot. Offsets of each in the code. (2.0.0)
        /// `first` and `count`: the block's numbers (the mods' own by default; War of the Lions' 261 on, 55 of them,
        /// whose way on is the mods' own items' code).</summary>
        public static byte[] Code(ulong data, out int[] starts, int first = FirstItem, int count = Count)
        {
            if (count < 1 || count > Count)
                throw new ArgumentException($"a block holds 1 to {Count} numbers, not {count}");
            var code = new List<byte>();
            starts = new int[Getters.Length];
            for (int g = 0; g < Getters.Length; g++)
            {
                starts[g] = code.Count;
                code.AddRange(new byte[] { 0x0F, 0xB7, 0xC1 });                       // movzx eax, cx
                code.Add(0x2D);                                                        // sub eax, first
                code.AddRange(BitConverter.GetBytes(first));
                code.AddRange(new byte[] { 0x83, 0xF8, (byte)count });                 // cmp eax, count
                code.AddRange(new byte[] { 0x73, 17 });                                // jae next
                code.Add(0x52);                                                        // push rdx
                code.AddRange(new byte[] { 0x48, 0xBA });                              // mov rdx, table
                ulong table = Getters[g] switch
                {
                    "IsValidItem" => data + ValidAt,
                    "SecondaryItemType" => data + SegmentAt,
                    "ItemCommon" => data + (ulong)(TablePointers + 0 * Count * 8),
                    "ItemWeapon" => data + (ulong)(TablePointers + 1 * Count * 8),
                    "ItemShield" => data + (ulong)(TablePointers + 2 * Count * 8),
                    "ItemArmor" => data + (ulong)(TablePointers + 3 * Count * 8),
                    "ItemAccessory" => data + (ulong)(TablePointers + 4 * Count * 8),
                    "ItemChemist" => data + (ulong)(TablePointers + 5 * Count * 8),
                    _ => data + (ulong)(TablePointers + 6 * Count * 8),
                };
                code.AddRange(BitConverter.GetBytes(table));
                code.AddRange(Getters[g] switch
                {
                    "IsValidItem" => new byte[] { 0x0F, 0xB6, 0x04, 0x02 },              // movzx eax, byte [rdx + rax]
                    "SecondaryItemType" => new byte[] { 0x0F, 0xBE, 0x04, 0x02 },        // movsx eax, byte [rdx + rax]
                    _ => new byte[] { 0x48, 0x8B, 0x04, 0xC2 },                          // mov rax, [rdx + rax*8]
                });
                code.Add(0x5A);                                                        // pop rdx
                code.Add(0xC3);                                                        // ret
                code.AddRange(new byte[] { 0x48, 0xA1 });                              // next: mov rax, [slot]
                code.AddRange(BitConverter.GetBytes(data + (ulong)(SlotsAt + 8 * g)));
                code.AddRange(new byte[] { 0xFF, 0xE0 });                              // jmp rax
            }
            return code.ToArray();
        }

        // --- the page's changes (made only when no other mod made one) --------------------------------------------

        /// <summary>One change of the program's bytes: where, what it held, what it gets, and what it is in words.</summary>
        public sealed class Patch
        {
            public int At { get; }
            public byte[] Old { get; }
            public byte[] New { get; }
            public string What { get; }

            public Patch(int at, byte[] old, byte[] made, string what)
            {
                At = at;
                Old = old;
                New = made;
                What = what;
            }
        }

        static readonly Dictionary<string, int> PageOf = new Dictionary<string, int>(StringComparer.Ordinal)
        {
            ["bag"] = PageBag, ["owned"] = PageOwned, ["attribute"] = PageAttribute, ["allitems"] = PageAllItems,
        };

        /// <summary>The program's changes: each bound raised for items to LastItem; and, the arrays not moved by another
        /// mod, each reach pointed at the page (`page`, from the program's start), the two calls of the item test at
        /// `lowTest` (native code reaching the game's own test, from the program's start). Null and why when one can't
        /// be made (a distance past 2 GB).</summary>
        public static List<Patch>? Patches(ReadOnlySpan<byte> image, Found found, long page, long lowTest, out string why)
        {
            why = "";
            var patches = new List<Patch>();
            foreach (var s in Sites)
            {
                if (!found.At.TryGetValue(s.Name, out int at))
                    continue;
                if (s.Bound && !KeptBounds.Contains(s.Name))
                {
                    int value = Value(s.Kind, false);
                    var made = s.Width == 1 ? new[] { (byte)value } : BitConverter.GetBytes(value);
                    var old = image.Slice(at + s.Operand, s.Width).ToArray();
                    if (!old.AsSpan().SequenceEqual(made))
                        patches.Add(new Patch(at + s.Operand, old, made, Name(s)));
                }
            }
            foreach (var (at, s) in found.Reaches)
            {
                if (found.Moved)
                    break;
                long to = page + PageOf[s.Array] + s.Offset;
                long disp = s.Kind == "rip" ? to - (at + s.Size) : to;
                if (disp < int.MinValue || disp > int.MaxValue)
                {
                    why = "the items' page is more than 2 GB from the game's program";
                    return null;
                }
                patches.Add(new Patch(at + s.Operand, image.Slice(at + s.Operand, 4).ToArray(),
                                      BitConverter.GetBytes((int)disp), Name(s)));
            }
            if (!found.Moved)
                foreach (var s in Sites)
                {
                    if (s.Kind != "call" || !found.At.TryGetValue(s.Name, out int at))
                        continue;
                    long disp = lowTest - (at + 5);
                    if (disp < int.MinValue || disp > int.MaxValue)
                    {
                        why = "the item test's native code is more than 2 GB from the game's program";
                        return null;
                    }
                    patches.Add(new Patch(at + 1, image.Slice(at + 1, 4).ToArray(), BitConverter.GetBytes((int)disp),
                                          Name(s)));
                }
            return patches;
        }

        /// <summary>The page as it is first made (no other mod made one): the game's bag, owned copy and bonus rows
        /// copied in, its lists adopted (each the game's entries up to its end, then the end, then the wall), and the
        /// mods' items' bonus rows written.</summary>
        public static byte[] Page(ReadOnlySpan<byte> image, Found found, int[] lists, List<Given> given)
        {
            var page = new byte[PageBytes];
            image.Slice((int)found.Array["bag"], GameBag).CopyTo(page.AsSpan(PageBag));
            image.Slice((int)found.Array["owned"], GameBag).CopyTo(page.AsSpan(PageOwned));
            image.Slice((int)found.Array["attribute"], GameRows * RowBytes).CopyTo(page.AsSpan(PageAttribute));
            Adopt(image.Slice((int)found.Array["allitems"], GameAllItems * 2), page.AsSpan(PageAllItems, AllItemsWords * 2));
            for (int n = 0; n < lists.Length; n++)
                Adopt(image.Slice(lists[n], Slots[Array.FindIndex(Slots, s => s.List == n)].Words * 2),
                      page.AsSpan(PageCharts + n * ChartWords * 2, ChartWords * 2));
            foreach (var g in given)
                if (g.Item.Bonus != null)
                    g.Item.Bonus.CopyTo(page, PageAttribute + g.Row * RowBytes);
            return page;
        }

        /// <summary>The 14 list pointers' places (each 8 bytes on: the first five from the menus' own first, the second
        /// five from the third copy's, the last four from the all-items block's).</summary>
        public static int SlotAt(Found found, int slot)
            => slot < 5 ? found.SlotsAt[0] + 8 * slot : slot < 10 ? found.SlotsAt[1] + 8 * (slot - 5)
                                                                   : found.SlotsAt[2] + 8 * (slot - 10);

        /// <summary>Each of the nine lists the 14 pointers point at, by its number (Slots' List), from the program's
        /// start (`imageBase`: where it is loaded, its pointers' addresses counted from there); -1 for one not in the
        /// program (another mod's page's), or for two pointers of one list that differ.</summary>
        public static int[] Lists(ReadOnlySpan<byte> image, Found found, ulong imageBase)
        {
            var lists = new int[9];
            for (int n = 0; n < lists.Length; n++)
                lists[n] = -2;
            foreach (var (slot, list, words) in Slots)
            {
                long at = BinaryPrimitives.ReadInt64LittleEndian(image.Slice(SlotAt(found, slot), 8)) - (long)imageBase;
                int place = at < 0 || at + 2 * words > image.Length ? -1 : (int)at;
                lists[list] = lists[list] == -2 || lists[list] == place ? place : -1;
            }
            return lists;
        }

        /// <summary>A list taken into a bigger one: its entries up to its end (0xFF), then the end, then the wall to
        /// the bigger list's end.</summary>
        public static void Adopt(ReadOnlySpan<byte> game, Span<byte> into)
        {
            int words = game.Length / 2, n = 0;
            for (; n < words; n++)
            {
                ushort entry = BinaryPrimitives.ReadUInt16LittleEndian(game.Slice(2 * n, 2));
                if (entry == ListEnd)
                    break;
                BinaryPrimitives.WriteUInt16LittleEndian(into.Slice(2 * n, 2), entry);
            }
            BinaryPrimitives.WriteUInt16LittleEndian(into.Slice(2 * n, 2), ListEnd);
            for (n++; 2 * n + 2 <= into.Length; n++)
                BinaryPrimitives.WriteUInt16LittleEndian(into.Slice(2 * n, 2), ListWall);
        }

        /// <summary>A bigger list given back to the game's: its entries of the game's own numbers (to GameLast), as
        /// many as the game's list holds less its end, then the end. (Another mod's numbers and ours aren't the game's
        /// lists'; the game's walks put an owned item back in its lists as they rebuild them.)</summary>
        public static void GiveBack(ReadOnlySpan<byte> big, Span<byte> game)
        {
            int words = game.Length / 2, n = 0;
            for (int k = 0; 2 * k + 2 <= big.Length && n < words - 1; k++)
            {
                ushort entry = BinaryPrimitives.ReadUInt16LittleEndian(big.Slice(2 * k, 2));
                if (entry == ListEnd || entry == ListWall)
                    break;
                if (entry <= GameLast)
                    BinaryPrimitives.WriteUInt16LittleEndian(game.Slice(2 * n++, 2), entry);
            }
            BinaryPrimitives.WriteUInt16LittleEndian(game.Slice(2 * n, 2), ListEnd);
        }

        // --- the counts kept in the save ----------------------------------------------------------------------------

        /// <summary>The items' counts and the event variables' tail kept alike (as WotL keeps its own): the tail changed
        /// since last seen (a save loaded, a new game, a battle tried again) and seen so twice, the counts taken from it
        /// (at most 99); else the counts changed, written to it; at a save always written. Returns what was done: 0
        /// nothing, 1 taken from the tail, 2 written to it.</summary>
        public sealed class Counts
        {
            readonly byte[] _lastTail = new byte[Count], _lastBag = new byte[Count], _settling = new byte[Count];
            bool _waiting;

            public int Sync(Span<byte> bag, Span<byte> bank, bool atSave)
            {
                Span<byte> tail = stackalloc byte[Count];
                for (int i = 0; i < Count; i++)
                    tail[i] = bank[CountAt(FirstItem + i)];
                Span<byte> counts = bag.Slice(FirstItem, Count);
                int done = 0;
                if (!atSave && !tail.SequenceEqual(_lastTail))
                {
                    if (!_waiting || !tail.SequenceEqual(_settling))
                    {
                        tail.CopyTo(_settling);
                        _waiting = true;
                        return 0;
                    }
                    for (int i = 0; i < Count; i++)
                        counts[i] = Math.Min(tail[i], (byte)MostCount);
                    done = 1;
                }
                else if (atSave || !counts.SequenceEqual(_lastBag))
                {
                    for (int i = 0; i < Count; i++)
                        bank[CountAt(FirstItem + i)] = Math.Min(counts[i], (byte)MostCount);
                    done = atSave || !counts.SequenceEqual(_lastBag) ? 2 : 0;
                }
                _waiting = false;
                for (int i = 0; i < Count; i++)
                    _lastTail[i] = bank[CountAt(FirstItem + i)];
                counts.CopyTo(_lastBag);
                return done;
            }
        }

        // --- the Item table's rows ------------------------------------------------------------------------------------

        /// <summary>An item's Item row: DLCFlags 0, its Name, NameSingular, NamePlural, Description and Name2 (its name),
        /// each a distance from + 4 (the layout's own: its strings relative to Name's field), Unknown19 1 as the game's
        /// rows, its Comment empty, UiItemCategoryId and SortOrder as the game item it was copied from has them (else
        /// its kind's own and a sort past the game's), the other bytes 0. Empty strings a run of zeros from anywhere.</summary>
        public static byte[] ItemRow(ModItem item, int number)
        {
            var texts = new[] { item.WordName, item.Singular, item.Plural, item.Description, item.WordName };
            var encoded = Array.ConvertAll(texts, t => Encoding.UTF8.GetBytes(t));
            int zeros = ItemRowBytes;
            int at = zeros + 8;
            int size = at;
            foreach (var e in encoded)
                size += e.Length + 1;
            var row = new byte[(size + 3) & ~3];
            for (int n = 0; n < encoded.Length; n++)
            {
                int field = 4 + 4 * n;
                if (encoded[n].Length == 0)
                    BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(field), zeros - 4);
                else
                {
                    BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(field), at - 4);
                    encoded[n].CopyTo(row, at);
                    at += encoded[n].Length + 1;
                }
            }
            row[0x19] = 1;
            // (1.27.0) Its UI status effect and random damage, as its file gives them (Mod Studio's from what it does).
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(UiStatusAt), item.UiStatus);
            row[RandomDamageAt] = (byte)(item.RandomDamage ? 1 : 0);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(0x20), zeros - 0x20);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(0x24), item.UiCategory >= 0 ? item.UiCategory
                                                                       : UiCategories[(int)item.Kind]);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(0x28), item.Sort >= 0 ? item.Sort : SortPast + number);
            return row;
        }

        /// <summary>An item's UI category when its file gives none, by kind (the game's own most often: a sword's 3, a
        /// shield's 20, a hat's 21, clothes' 24, an accessory's 28, a potion's 34), and a sort past every game item's.</summary>
        public static readonly int[] UiCategories = { 3, 20, 21, 24, 28, 34 };
        public const int SortPast = 900000;
        /// <summary>(1.27.0) An Item row's UI status effect (UiStatusEffectId, 32 bits) and random damage
        /// (IsRandomDamage, a byte), as the game's own rows have them (the Blood Sword's 1001 at + 0x1C, the Battle
        /// Axe's 1 at + 0x2D).</summary>
        public const int UiStatusAt = 0x1C, RandomDamageAt = 0x2D;

        /// <summary>The loaded Item table (its loaded language's) with the mods' items' rows, or null and why: a row
        /// another mod has at an item's number is left out, said.</summary>
        public static byte[]? WithItemRows(ReadOnlySpan<byte> table, IEnumerable<Given> given, List<string> said,
                                          out string why)
        {
            var rows = Nxd.Rows(table, out why);
            if (rows == null)
                return null;
            if (Nxd.Keys(table) != 1)
            {
                why = $"it isn't a table of one key (byte 8: {table[8]})";
                return null;
            }
            var added = new List<NewRow>();
            foreach (var g in given)
            {
                if (Nxd.Find(table, new[] { g.Number }) >= 0)
                {
                    said.Add($"{g.Who} has no name in the game: Item {g.Number} is another mod's already.");
                    continue;
                }
                added.Add(new NewRow(new[] { g.Number }, ItemRow(g.Item, g.Number)));
            }
            return Nxd.WithRows(table, added, out why);
        }

        // --- the Outfitter --------------------------------------------------------------------------------------------

        /// <summary>The Outfitter's tab an item of a kind is listed under (0x2890C0's answer: 0 weapons, 1 shields, 2
        /// heads, 3 bodies, 4 accessories, 5 the rest), and the tabs a list's category asks for (0x288E54's first
        /// lines: up to 1 the weapons and shields, 2, 3 and 4 their own, 5 the weapons, 6 the shields, any other the
        /// rest's).</summary>
        public static int TabOf(ItemKind kind) => kind switch
        {
            ItemKind.Weapon => 0, ItemKind.Shield => 1, ItemKind.Head => 2, ItemKind.Body => 3, ItemKind.Accessory => 4,
            _ => 5,
        };

        /// <summary>The stock's mark of an item the unit can't use (the list's word's 0x4000).</summary>
        public const int CantUse = 0x4000;

        /// <summary>The words an Outfitter's list gets for the mods' items it sells (`items`, by number) after the
        /// `listed` it has: those of the tabs the list's category asks for, the story at their point (`storyPoint`),
        /// each marked as the stock marks one the unit can't use (`equips`' -1: in mode 1 marked, in mode 2 left out),
        /// up to the list's 255.</summary>
        public static List<int> Appended(IReadOnlyList<int> items, Func<int, Given?> byNumber, short category,
                                         int listed, int storyPoint, Func<int, int>? equips, int mode)
        {
            var (first, second) = TabsOf(category);
            var entries = new List<int>();
            foreach (int number in items)
            {
                if (listed + entries.Count >= 255)
                    break;
                var g = byNumber(number);
                if (g == null)
                    continue;
                int tab = TabOf(g.Item.Kind);
                if (tab != first && tab != second)
                    continue;
                if (g.Item.Record[ItemFile.ShopAt] > storyPoint)
                    continue;
                int entry = number;
                if (equips != null && equips(number) == -1)
                {
                    if (mode == 2)
                        continue;
                    if (mode == 1)
                        entry |= CantUse;
                }
                entries.Add(entry);
            }
            return entries;
        }

        public static (int, int) TabsOf(short category) => category switch
        {
            <= 1 => (0, 1), 2 => (2, 2), 3 => (3, 3), 4 => (4, 4), 5 => (0, 0), 6 => (1, 1), _ => (5, 5),
        };
    }
}
