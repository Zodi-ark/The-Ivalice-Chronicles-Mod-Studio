// Mod Studio Framework: (1.42.0) a job's own sprites. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// The road's step 5 (Zodi's words of 10 November, "new generic Male and Female sprites for those jobs", and on test 98,
// 11 November: "Continue on. I believe Sprites are next on our list for new Jobs"), its first part: two sprite numbers
// a job, measured in dev/research/sidequests/sprites.py (claude/job-sprites-research.md says what it means).
//
// A unit's look is chosen by its sprite, a number the game makes from its job: as a battle's units are made, as a
// portrait or a face is drawn, as the job screen shows a job's cell (a generic man's (job + 0x26) * 2 + 0x80 in a byte,
// a woman's the next; the Squire's 96 and 97). The game's sprites are 0 to 169, and each table of what a sprite looks
// like has 170 rows (its attributes, its classic file, the big monsters' second classic file, the Enhanced look's
// sheets and the big monsters' second sheets) or 211 (its face, in the five tables the portraits are read through).
//
// A job with a Look of its own (its job.json's "Look": {"Like": a generic job}) is given two sprite numbers past the
// game's (Numbers.json's Sprites), a man's and the woman's after it, and the game's own routines that make a sprite from
// a job are handed a job number of the framework's that makes them make those two (Virtual). Every table keyed by a
// sprite is made longer, 255 rows in memory near the program (a sprite is one byte; 255 is left out): the game's rows as
// they are, the Squire's for every number past them no job has (in the face words, past the game's 211, none), and each
// job's own two rows: its Like's in its attributes (the same frames as its Look's) and the big monsters' second files
// (none for a generic), its Look's everywhere else (its sheets, the palettes they are drawn with, its faces and, from
// 1.42.2, its classic files). A Look must be drawn for the same frames as its Like (the attributes' first two bytes),
// or the job keeps its Like's look. Every instruction of the game's code that names one of those tables then names the same place in the
// longer one (44), every bound of a sprite by their count is widened (16), the two tests that sort a sprite as a
// generic's or a story unit's take 170 to 254 as a generic's, and the job screen's cell, which draws only a generic job
// by its job, draws a job with sprites of its own by its job too. Each place is found once by its bytes
// (SpriteRoomSites.cs, written from the program by dev/research/sidequests/make_sprite_sites.py), held to what it must
// be; one not found, and no job has a look of its own (each looks like its Like, as before).
//
// The game's own tables stay where they are, and others write them (WotL Restoration writes its portraits' faces into
// the face words): what is written there since is brought over to the longer ones (Sync), as the job records' are, with
// every job's own row taken from a row so written.
//
// (1.54.0, Zodi's 8th note of 14 November and his pick "Framework sets its frames") A man or a woman whose own textures
// are drawn for the other kind of human frames (a Look's Frames: Type 1 or Type 2, JobFile.cs) takes, in the attributes,
// the row of the game's generic job drawn for them (the Squire's for Type 1, the Chemist's for Type 2): its first two
// bytes pick the frames and animations the game draws the sprite with, as they pick the Black Mage's. Every other row,
// and every row of one without its own textures, is as before.
//
// (1.42.1, Zodi's test 99 of 12 November: putting the Battlemage on a tile in the battle's formation stopped the game, at
// 0x217172 of his program) One table more is keyed by a sprite: the game table CharShape (its sheet 0xAE), a unit's
// height above the ground, its shadow, its colors and its light, a row for each of the game's sprites (0 to 158; WotL
// Restoration's 0 to 169). The code that shows a unit on the battlefield reads its row with no test for none (at
// 0x217172, 0x221AB9, 0x26456E, 0x2648C6 and 0x264CE9), so each job's own sprite is given a row as the table loads
// (WithShapeRows): its Look's sprite's, a woman's the woman's.
//
// (1.42.2, his test 100: placed, the figures' colors and their portraits on the battlefield weren't the Look's) The
// battle draws a unit's figure with the palettes of the classic file its figure's loader reads, in the Enhanced look too
// (0x26E838 copies the file's first 512 bytes into the figure's graphics slot): the classic files' rows are a job's
// Look's now, as the palettes' copy the menus read always was. And the same function keeps each graphics slot's sprite
// in a table of ten, which the battle's panels read as the unit's portrait (a generic's numbered as its sprite): at its
// two writes a job's own sprite is written as its Look's (the fourth and fifth of the places taken). Only the Enhanced
// look is supported (his word, 12 November).
//
// (1.43.0, step 5's second part, his choice of 12 November: "Colors first") A job's own colors. Both routes that color a
// figure, the menus' (0x26E750) and the battle's (0x26E838), copy its 16 palettes from its classic file and then hand
// its sprite to one routine (0x26C7AC), which looks up the sprite's CharShape row and, where its CharCLUT number (+ 0xC)
// isn't 0, writes that table's rows over the palettes (0x26C530: sheet 0xD2, two keys, the number and a palette's; each
// row 16 colors of three bytes, switched on by its + 0x14): the game colors Ramza's three looks so. So a job whose Look
// gives Colors has its own sprites' CharShape rows name a CharCLUT number of their own (the sprite's own number, past the
// game's 1 to 3 and short of its 254 and 255), and CharCLUT gets a row for each palette given, as it loads
// (WithClutRows). Palettes 0 to 4 are a figure's (the game's generics wear one a team); 8 to 12, the battle's portraits'
// colors, stay the Look's, as its portraits are. No change of the game's code. One thing more the game does with a
// CharCLUT number: as a save loads or a battle is started again (0x1009E8) a figure whose sprite names one wears the
// palette its first row's color skin gives (0x1E3A10: 0 for no skin), which for the party's units is the palette they
// wear.
//
// (1.44.0, step 5's second part, next in his order: the sprites' textures) A job's own textures. Where a job's Look gives
// Textures and the framework answers them (SpriteTextures.cs), its own sprites' rows in the textures' table ("sheets": a
// sprite's upper texture's g2d.dat entry, its lower the next) name entries of the framework's (SpriteTextures.Entry) in
// place of its Look's, kept so as others write the game's table (Sync).
//
// With no job with a look of its own none of this is made.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public static partial class SpriteRoom
    {
        /// <summary>The game's sprites (0 to 169), and the longer tables' rows (a sprite is one byte; 255 is left out, so
        /// every bound is one number an instruction holds).</summary>
        public const int GameCount = 170, Count = 255;
        /// <summary>The Squire's sprites (a man's; a woman's the next): every number past the game's no job has looks so.</summary>
        public const int Squire = 96;

        /// <summary>The numbers a job's own sprites are given, each a man's (the woman's is the next): past the game's
        /// 169, below 255, and not 202 to 209 (the game keeps faces for 203 to 209).</summary>
        public static readonly int[] Pairs = MakePairs();

        static int[] MakePairs()
        {
            var pairs = new List<int>();
            for (int n = GameCount; n <= 200; n += 2)
                pairs.Add(n);
            for (int n = 210; n + 1 < Count; n += 2)
                pairs.Add(n);
            return pairs.ToArray();
        }

        /// <summary>The job number the game's routines are handed for a job's own sprites: from it they make its man's
        /// sprite and its woman's (111 to 126 and 131 to 152, none of the jobs those routines ask apart).</summary>
        public static int Virtual(int sprite) => (sprite + 0x34) / 2;

        /// <summary>A generic job's sprite as the game makes it (jobs 92 and 93 count as 91 and 92).</summary>
        public static int GenericSprite(int job, bool woman)
        {
            if (job == 92 || job == 93)
                job--;
            return ((job + 0x26) * 2 + (woman ? 0x81 : 0x80)) & 0xFF;
        }

        /// <summary>The places found: where each longer table's game table is, where each reader's four bytes of distance
        /// are, each bound's number, each test.</summary>
        public sealed class Sites
        {
            public int[] Game { get; } = new int[Tables.Length];
            public int[] ReaderAt { get; } = new int[Readers.Length];
            public int[] BoundAt { get; } = new int[Bounds.Length];
            public int[] TestAt { get; } = new int[Tests.Length];
            /// <summary>(1.45.0) The places a job's own portraits change, where they are found and their hook is made (null
            /// otherwise): the jobs' code takes them then (SpritePortraits.Code).</summary>
            public SpritePortraits.Sites? Portraits { get; set; }
            /// <summary>(1.53.0) The load's walk's write of a figure's palette (WalkPattern), or -1 and why: found apart, so
            /// a job's own sprites are its own whether or not it is.</summary>
            public int Walk { get; set; } = -1;
            public string? WalkMissing { get; set; }
            public List<string> Missing { get; } = new List<string>();
            public bool Ok => Missing.Count == 0;
        }

        /// <summary>Every reader, bound and test, each found once by its bytes and held to what it must be: every reader of
        /// a longer table names one place (its game table, less what it names in it), inside the program; a bound's number
        /// and a test's bytes are in their patterns.</summary>
        public static Sites Find(ReadOnlySpan<byte> image, List<Section> sections)
        {
            var sites = new Sites();
            for (int n = 0; n < Readers.Length; n++)
            {
                var (pattern, at, relative, table, names) = Readers[n];
                var matches = Places.Search(image, sections, Places.Pattern(pattern));
                if (matches.Count != 1)
                {
                    sites.Missing.Add($"the sprites' reader {n + 1} ({matches.Count} places like it, not 1)");
                    continue;
                }
                int where = matches[0] + at;
                int distance = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(where, 4));
                long game = (relative ? (long)where + 4 + distance : distance) - names;
                if (game <= 0 || game + (long)Tables[table].Entry * Tables[table].GameEntries > image.Length)
                {
                    sites.Missing.Add($"the sprites' reader {n + 1} (it names no place in the program)");
                    continue;
                }
                if (sites.Game[table] != 0 && sites.Game[table] != game)
                {
                    sites.Missing.Add($"the sprites' reader {n + 1} (it names another place than the others of its table)");
                    continue;
                }
                sites.Game[table] = (int)game;
                sites.ReaderAt[n] = where;
            }
            for (int n = 0; n < Bounds.Length; n++)
            {
                var matches = Places.Search(image, sections, Places.Pattern(Bounds[n].Pattern));
                if (matches.Count != 1)
                {
                    sites.Missing.Add($"the sprites' bound {n + 1} ({matches.Count} places like it, not 1)");
                    continue;
                }
                // (Its number is among the pattern's own bytes.)
                sites.BoundAt[n] = matches[0] + Bounds[n].At;
            }
            for (int n = 0; n < Tests.Length; n++)
            {
                var matches = Places.Search(image, sections, Places.Pattern(Tests[n].Pattern));
                if (matches.Count != 1)
                {
                    sites.Missing.Add($"the sprites' test {n + 1} ({matches.Count} places like it, not 1)");
                    continue;
                }
                // Its bytes as measured: among the pattern's own for the tests; (1.42.2) a slot's sprite's write names the
                // slots' table from the image's base, four bytes the pattern leaves open, held here.
                int place = matches[0] + Tests[n].At;
                byte[] bytes = Convert.FromHexString(Tests[n].Bytes);
                if (place + bytes.Length > image.Length || !image.Slice(place, bytes.Length).SequenceEqual(bytes))
                {
                    sites.Missing.Add($"the sprites' test {n + 1} (its bytes aren't as measured)");
                    continue;
                }
                sites.TestAt[n] = place;
            }
            for (int t = 0; t < Tables.Length; t++)
                if (sites.Game[t] == 0 && sites.Ok)
                    sites.Missing.Add($"the sprites' table {Tables[t].Name} (no reader names it)");
            // (1.53.0) The load's walk over the figures, apart.
            var walk = Places.Search(image, sections, Places.Pattern(WalkPattern));
            if (walk.Count == 1)
                sites.Walk = walk[0] + WalkAt;
            else
                sites.WalkMissing = $"the load's coloring of the figures ({walk.Count} places like it, not 1)";
            return sites;
        }

        /// <summary>(1.53.0, Zodi's order of 13 November: "jobs in a quest's battle") As a save loads or a battle is taken
        /// up again (0x1009E8, dev/research/sidequests/quest_jobs.py), every figure whose sprite's CharShape row names a
        /// CharCLUT number is given the palette that number's first row's color skin gives (0x1E3A10: Ramza's chosen one
        /// for a skin of 1, else 0) and colored again: a job's own sprites in colors of their own have no skin, so a unit
        /// of another team in such a job would wear the player's colors after a load, where the figure's own making gave
        /// it its unit's (its first sort takes 170 to 254 as a generic's: Tests[0]). The color skin's call, then edx made 0
        /// and the palette's write (WalkLength bytes at WalkAt), then the figure handed to its coloring.</summary>
        public const string WalkPattern = "8B 50 0C E8 ?? ?? ?? ?? 33 D2 88 43 0B 48 8B CB 44 8D 42 01 E8";
        public const int WalkAt = 8, WalkLength = 5, FigureSprite = 0xA, FigurePalette = 0xB;

        /// <summary>(1.53.0) The log's line for the walk where it isn't found and a job has colors of its own.</summary>
        public static string WalkNotLine(string missing, string program, string name)
            => $"after a load, a unit of another team in a mod's job with colors of its own wears the player's colors: "
               + $"{missing} wasn't found in {program}. A game update may have changed it: look for a newer {name}.";

        /// <summary>Each longer table's place in the room, from its start (16 bytes apart at least), and the room's bytes.</summary>
        public static int Offset(int table)
        {
            int at = 0;
            for (int t = 0; t < table; t++)
                at += (Tables[t].Entry * Count + 15) & ~15;
            return at;
        }

        public static int RoomBytes => Offset(Tables.Length);

        /// <summary>Whether two generic jobs' sprites are drawn for the same frames (the attributes' first two bytes, a
        /// man's and a woman's), so one's sheets can be drawn as the other.</summary>
        public static bool SameFrames(ReadOnlySpan<byte> image, Sites sites, int like, int look)
        {
            for (int woman = 0; woman < 2; woman++)
            {
                var a = image.Slice(sites.Game[0] + 4 * GenericSprite(like, woman == 1), 2);
                var b = image.Slice(sites.Game[0] + 4 * GenericSprite(look, woman == 1), 2);
                if (!a.SequenceEqual(b))
                    return false;
            }
            return true;
        }

        /// <summary>Each job with a Look of its own given its two sprite numbers, the same every time (Numbers.json's
        /// Sprites), where its Look is drawn for its Like's frames; what can't be is said, and that job keeps its Like's
        /// look. How many have their own.</summary>
        public static int Plan(IList<JobRoom.Given> given, Numbers numbers, List<string> said, ReadOnlySpan<byte> image, Sites sites)
        {
            int made = 0;
            foreach (var g in given)
            {
                g.Sprite = -1;
                if (g.Job.LookLike <= 0)
                    continue;
                if (!SameFrames(image, sites, g.Job.Like, g.Job.LookLike))
                {
                    said.Add($"{g.Job.Who} keeps the look of the game's job {g.Job.Like}: the game's job {g.Job.LookLike}'s "
                             + "sprites have other frames, so its look can't be used.");
                    continue;
                }
                int sprite = numbers.Give(Numbers.SpritesKind, g.Job.Key, Pairs, n => Array.IndexOf(Pairs, n) >= 0, out _);
                if (sprite < 0)
                {
                    said.Add($"{g.Job.Who} keeps the look of the game's job {g.Job.Like}: all {Pairs.Length} pairs of sprite "
                             + "numbers are given.");
                    continue;
                }
                g.Sprite = sprite;
                made++;
            }
            return made;
        }

        /// <summary>The changes of the game's code for longer tables in a room at `room` (an address, as `imageBase` is):
        /// each reader's distance to the same place in its longer table, each bound's number the longer count. Null where
        /// a distance doesn't fit its four bytes (the room too far from the program).</summary>
        public static List<JobRoom.Change>? Changes(Sites sites, ulong imageBase, ulong room)
        {
            var changes = new List<JobRoom.Change>();
            for (int n = 0; n < Readers.Length; n++)
            {
                var (_, _, relative, table, names) = Readers[n];
                int where = sites.ReaderAt[n];
                long target = (long)room + Offset(table) + names;
                long distance = relative ? target - ((long)imageBase + where + 4) : target - (long)imageBase;
                if (distance < int.MinValue || distance > int.MaxValue)
                    return null;
                var bytes = new byte[4];
                BinaryPrimitives.WriteInt32LittleEndian(bytes, (int)distance);
                changes.Add(new JobRoom.Change(where, bytes));
            }
            for (int n = 0; n < Bounds.Length; n++)
                changes.Add(new JobRoom.Change(sites.BoundAt[n], new[] { (byte)Bounds[n].Becomes }));
            return changes;
        }

        /// <summary>A call (E8) of `to` in place of `length` bytes at `site`, the rest filled with nop.</summary>
        internal static byte[] CallFrom(ulong imageBase, int site, ulong to, int length)
        {
            var bytes = new byte[length];
            bytes[0] = 0xE8;
            BinaryPrimitives.WriteInt32LittleEndian(bytes.AsSpan(1), checked((int)((long)to - (long)(imageBase + (ulong)site + 5))));
            for (int n = 5; n < length; n++)
                bytes[n] = 0x90;
            return bytes;
        }

        /// <summary>The framework's own three tests, written in `a` (the jobs' native code), and the changes of the game's
        /// code that call them in place of the game's: the two sorts take every number past the game's (170 to 254) as a
        /// generic's; the job screen's cell takes the job number the routines are handed for a job's own sprites as a
        /// generic job's. Each leaves the flags the game's jump after it reads as the game's test would for any other
        /// number, and every register but eax (its test's own) as it was. (1.42.2) And the write of a graphics slot's
        /// sprite, called at both its places: a job's own sprite written as its Look's, every register but ecx (the
        /// sprite, read by nothing after) as it was.</summary>
        internal static void Code(Destinations.Asm a, Sites sites, ulong imageBase, IList<JobRoom.Given> given,
                                  List<JobRoom.Change> made)
        {
            // A unit's figure's colors (0x26EB74): a generic's for 96 to 133 (the game's test, the sprite in bp), and
            // for 170 to 254.
            ulong figure = a.Here;
            a.Bytes(Convert.FromHexString(Tests[0].Bytes));    // lea eax, [rbp - 0x60]; cmp ax, 0x25
            a.Short(0x76, "spriteFigureDone");                  // jbe
            a.Hex("66 81 FD AA 00");                            // cmp bp, 0xAA
            a.Short(0x72, "spriteFigureNot");                   // jb
            a.Hex("66 81 FD FE 00");                            // cmp bp, 0xFE
            a.Short(0x77, "spriteFigureNot");                   // ja
            a.Hex("39 C0");                                     // cmp eax, eax (below or equal)
            a.Label("spriteFigureDone");
            a.Bytes(0xC3);
            a.Label("spriteFigureNot");
            a.Hex("66 83 F8 25 C3");                            // cmp ax, 0x25; ret
            made.Add(new JobRoom.Change(sites.TestAt[0], CallFrom(imageBase, sites.TestAt[0], figure, Tests[0].Bytes.Length / 2)));

            // The palette a unit's figure wears (0x269074): its own for 96 to 154 (the game's test, the sprite less 0x60
            // in al), and for 170 to 254.
            ulong palette = a.Here;
            a.Bytes(Convert.FromHexString(Tests[1].Bytes));    // mov al, [rdx + r8 + 1]; sub al, 0x60; cmp al, 0x3A
            a.Short(0x76, "spritePaletteDone");                 // jbe
            a.Hex("3C 4A");                                     // cmp al, 0x4A (170 less 0x60)
            a.Short(0x72, "spritePaletteNot");                  // jb
            a.Hex("3C 9E");                                     // cmp al, 0x9E (254 less 0x60)
            a.Short(0x77, "spritePaletteNot");                  // ja
            a.Hex("39 C0");                                     // cmp eax, eax
            a.Label("spritePaletteDone");
            a.Bytes(0xC3);
            a.Label("spritePaletteNot");
            a.Hex("3C 3A C3");                                  // cmp al, 0x3A; ret
            made.Add(new JobRoom.Change(sites.TestAt[1], CallFrom(imageBase, sites.TestAt[1], palette, Tests[1].Bytes.Length / 2)));

            // A job's cell on the job screen (0x368424): drawn by its job for a generic job (the game's test, the job in
            // cl), and for the job number a job's own sprites are made from.
            ulong cell = a.Here;
            a.Bytes(Convert.FromHexString(Tests[2].Bytes));    // lea eax, [rcx - 0x4A]; cmp al, 0x13
            a.NearTo("spriteCellDone", 0x86);                   // jbe
            foreach (var g in given)
            {
                if (g.Sprite < 0)
                    continue;
                a.Hex("80 F9");                                 // cmp cl, its number
                a.Bytes((byte)Virtual(g.Sprite));
                a.NearTo("spriteCellYes", 0x84);                // je
            }
            a.Hex("3C 13");                                     // cmp al, 0x13
            a.Label("spriteCellDone");
            a.Bytes(0xC3);
            a.Label("spriteCellYes");
            a.Hex("39 C0 C3");                                  // cmp eax, eax; ret
            made.Add(new JobRoom.Change(sites.TestAt[2], CallFrom(imageBase, sites.TestAt[2], cell, Tests[2].Bytes.Length / 2)));

            // (1.42.2, his test 100) A graphics slot's sprite as the figure's palettes are loaded (0x26E838, two writes of
            // ecx, the figure's sprite, at [rdx + rax * 4 + the slots' table], rdx the image's base): the battle's panels
            // read it as the unit's portrait, a generic's numbered as its sprite. A job's own sprite is written as its
            // Look's, a woman's the woman's (each below 170, so no later compare takes it again); any other as it is.
            // (1.45.0) One with portraits of its own is written as its own portrait's number (SpritePortraits.Number:
            // past 255, so no later compare takes it again either).
            ulong slot = a.Here;
            foreach (var g in given)
            {
                if (g.Sprite < 0)
                    continue;
                for (int woman = 0; woman < 2; woman++)
                {
                    a.Hex("81 F9");                             // cmp ecx, its sprite
                    a.Bytes(BitConverter.GetBytes(g.Sprite + woman));
                    a.Hex("75 05 B9");                          // jne past; mov ecx, its Look's sprite or its own portrait
                    a.Bytes(BitConverter.GetBytes(g.Portraits[woman] ? SpritePortraits.Number(g.Sprite + woman)
                                                                     : GenericSprite(g.Job.LookLike, woman == 1)));
                }
            }
            a.Bytes(Convert.FromHexString(Tests[3].Bytes));    // mov [rdx + rax * 4 + the slots' table], ecx
            a.Bytes(0xC3);
            for (int n = 3; n <= 4; n++)
                made.Add(new JobRoom.Change(sites.TestAt[n], CallFrom(imageBase, sites.TestAt[n], slot, Tests[n].Bytes.Length / 2)));

            // (1.53.0) The load's walk over the figures (where found), where a job has colors of its own: a figure of one of
            // the framework's sprites (170 to 254, as the figure's own making sorts them: a generic's) keeps the palette its
            // making gave it; any other gets the palette the skin gives, as the game writes it. edx is made 0 either way;
            // every other register as it was; the flags are set again before they are read.
            bool colors = false;
            foreach (var g in given)
                colors |= g.Sprite >= 0 && g.Job.HasColors;
            if (sites.Walk >= 0 && colors)
            {
                ulong walk = a.Here;
                a.Hex("33 D2");                                 // xor edx, edx
                a.Hex("80 7B");                                 // cmp byte ptr [rbx + the figure's sprite], 0xAA
                a.Bytes((byte)FigureSprite, 0xAA);
                a.Short(0x72, "spriteWalkWrite");               // jb
                a.Hex("80 7B");                                 // cmp byte ptr [rbx + the figure's sprite], 0xFE
                a.Bytes((byte)FigureSprite, 0xFE);
                a.Short(0x77, "spriteWalkWrite");               // ja
                a.Bytes(0xC3);
                a.Label("spriteWalkWrite");
                a.Hex("88 43");                                 // mov [rbx + the figure's palette], al
                a.Bytes((byte)FigurePalette, 0xC3);
                made.Add(new JobRoom.Change(sites.Walk, CallFrom(imageBase, sites.Walk, walk, WalkLength)));
            }
        }

        /// <summary>The row a job's own sprite takes in a table: its Look's or its Like's, a man's or a woman's. (1.54.0) In
        /// the attributes, a man or a woman whose own textures are drawn for frames its Look names (ModJob.Frames) takes
        /// the row of the game's generic job drawn for them (FramesJob), where those textures are given to the game.</summary>
        static int Source(int table, JobRoom.Given g, bool woman)
        {
            int who = woman ? 1 : 0;
            if (table == AttributesTable && g.Job.Frames[who] > 0 && g.Textures[who])
                return GenericSprite(FramesJob(g.Job.Frames[who]), woman);
            return GenericSprite(Tables[table].Look ? g.Job.LookLike : g.Job.Like, woman);
        }

        /// <summary>(1.54.0) The sprites' attributes' table (its first two bytes a sprite's frames and animations).</summary>
        public static int AttributesTable => Array.FindIndex(Tables, table => table.Name == "attributes");

        /// <summary>(1.54.0) The game's generic jobs whose sprites' attributes are each kind of human frames': the Squire's
        /// (0, 0, 0, 36: Type 1's frames and animations, not flying, 36 high) and the Chemist's (1, 1, 0, 36: Type 2's).
        /// Every one of the game's 38 generic sprites has one of the two rows, a man's and a woman's alike (BATTLE.BIN's
        /// table; dev/test_jobs.py holds both to his program).</summary>
        public const int Type1Job = 74, Type2Job = 75;

        /// <summary>(1.54.0) The game's generic job drawn for a kind of frames (JobFile.Type1Frames or Type2Frames).</summary>
        public static int FramesJob(int frames) => frames == JobFile.Type2Frames ? Type2Job : Type1Job;

        /// <summary>(1.44.0) The sprites' textures' table (the Enhanced look's: a sprite's upper texture's g2d.dat entry).</summary>
        public static int SheetsTable => Array.FindIndex(Tables, table => table.Name == "sheets");

        /// <summary>(1.45.0) Whether a longer table is one of the face words' (a sprite's face, its portrait through the face
        /// to portrait routine).</summary>
        public static bool IsFaceWords(int table) => Tables[table].Name.StartsWith("face words", StringComparison.Ordinal);

        /// <summary>(1.44.0) Whether a job's own sprite's row in a table is its own texture's entry (the sprites' textures'
        /// table, where its textures are its own) rather than a row it takes from another sprite; and that row. (1.45.0)
        /// Or, in the face words, its own portrait's number as its face, where its portraits are its own (the face to
        /// portrait routine answers it with itself: SpritePortraits.Code).</summary>
        static bool OwnRow(int table, JobRoom.Given g, int woman, Span<byte> row)
        {
            if (table == SheetsTable && g.Textures[woman])
            {
                BinaryPrimitives.WriteInt32LittleEndian(row, SpriteTextures.Entry(g.Sprite + woman));
                return true;
            }
            if (IsFaceWords(table) && g.Portraits[woman])
            {
                BinaryPrimitives.WriteUInt16LittleEndian(row, (ushort)SpritePortraits.Number(g.Sprite + woman));
                return true;
            }
            return false;
        }

        /// <summary>(1.45.0) Whether a job's own sprite's row in a table is its own (OwnRow), not taken from another's.</summary>
        static bool IsOwnRow(int table, JobRoom.Given g, int woman)
            => table == SheetsTable && g.Textures[woman] || IsFaceWords(table) && g.Portraits[woman];

        /// <summary>The longer tables as they start: the game's rows as they are, the Squire's for every number past them no
        /// job has (none in the face words past the game's), each job's own two rows its Like's or its Look's.</summary>
        public static void Fill(ReadOnlySpan<byte> image, Sites sites, Span<byte> room, IList<JobRoom.Given> given)
        {
            for (int t = 0; t < Tables.Length; t++)
            {
                var (_, entry, gameEntries, _) = Tables[t];
                var table = room.Slice(Offset(t), entry * Count);
                image.Slice(sites.Game[t], entry * gameEntries).CopyTo(table);
                for (int n = gameEntries; n < Count; n++)
                {
                    var row = table.Slice(n * entry, entry);
                    if (gameEntries == GameCount)
                        table.Slice((Squire + (n & 1)) * entry, entry).CopyTo(row);
                    else
                        row.Clear();
                }
                foreach (var g in given)
                    if (g.Sprite >= 0)
                        for (int woman = 0; woman < 2; woman++)
                        {
                            var own = table.Slice((g.Sprite + woman) * entry, entry);
                            if (!OwnRow(t, g, woman, own))
                                table.Slice(Source(t, g, woman == 1) * entry, entry).CopyTo(own);
                        }
            }
        }

        /// <summary>Copies of the game's own tables as they are now (for Sync).</summary>
        public static byte[][] Seen(ReadOnlySpan<byte> image, Sites sites)
        {
            var seen = new byte[Tables.Length][];
            for (int t = 0; t < Tables.Length; t++)
                seen[t] = image.Slice(sites.Game[t], Tables[t].Entry * Tables[t].GameEntries).ToArray();
            return seen;
        }

        /// <summary>What has been written to the game's own tables since they were last seen (`kept`, copies of them as they
        /// were then) brought over to the longer ones, row by row, and kept: a job's own rows stay its own, and take a row
        /// so written that they are taken from. How many rows were.</summary>
        public static int Sync(ReadOnlySpan<byte> image, Sites sites, byte[][] kept, Span<byte> room, IList<JobRoom.Given> given)
        {
            int brought = 0;
            for (int t = 0; t < Tables.Length; t++)
            {
                var (_, entry, gameEntries, _) = Tables[t];
                var table = room.Slice(Offset(t), entry * Count);
                for (int n = 0; n < gameEntries; n++)
                {
                    var now = image.Slice(sites.Game[t] + n * entry, entry);
                    var was = kept[t].AsSpan(n * entry, entry);
                    if (now.SequenceEqual(was))
                        continue;
                    bool own = false;
                    foreach (var g in given)
                        if (g.Sprite >= 0)
                        {
                            own |= n == g.Sprite || n == g.Sprite + 1;
                            for (int woman = 0; woman < 2; woman++)
                                if (Source(t, g, woman == 1) == n && !IsOwnRow(t, g, woman))
                                    now.CopyTo(table.Slice((g.Sprite + woman) * entry, entry));
                        }
                    if (!own)
                        now.CopyTo(table.Slice(n * entry, entry));
                    now.CopyTo(was);
                    brought++;
                }
            }
            return brought;
        }

        /// <summary>(1.42.1) The game table CharShape (sheet 0xAE): a row by a sprite's number, 0x30 bytes, its Comment's
        /// words pointed at from the row's start (+ 4).</summary>
        public const int ShapeSheet = 0xAE, ShapeRowBytes = 0x30, ShapeComment = 4;

        /// <summary>(1.42.1) The loaded CharShape with a row for each job's own sprite: its Look's sprite's row, a woman's the
        /// woman's, its Comment empty. A row another mod has at one of those numbers is kept, said. Null and why when the
        /// table can't be read or has no row for a Look's sprite; `added`, how many rows it gets.</summary>
        public static byte[]? WithShapeRows(ReadOnlySpan<byte> table, IList<JobRoom.Given> given, List<string> said,
                                            out string why, out int added)
        {
            added = 0;
            if (Nxd.Rows(table, out why) == null)
                return null;
            if (Nxd.Keys(table) != 1)
            {
                why = $"it isn't a table of one key (byte 8: {table[8]})";
                return null;
            }
            var rows = new List<NewRow>();
            foreach (var g in given)
            {
                if (g.Sprite < 0)
                    continue;
                for (int woman = 0; woman < 2; woman++)
                {
                    int sprite = g.Sprite + woman, source = GenericSprite(g.Job.LookLike, woman == 1);
                    if (Nxd.Find(table, new[] { sprite }) >= 0)
                    {
                        said.Add($"{g.Job.Who}'s sprite {sprite} keeps the CharShape row another mod gives it.");
                        continue;
                    }
                    int at = Nxd.Find(table, new[] { source });
                    if (at < 0 || at > table.Length - ShapeRowBytes)
                    {
                        why = $"it has no row for the game's sprite {source}, which {g.Job.Who} looks like";
                        return null;
                    }
                    // The row's bytes, then four zeros: its Comment's words, empty.
                    var row = new byte[ShapeRowBytes + 4];
                    table.Slice(at, ShapeRowBytes).CopyTo(row);
                    BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(ShapeComment), ShapeRowBytes);
                    // (1.43.0) Its own colors: its CharCLUT number, the sprite's own.
                    if (g.Job.Colors[woman] != null)
                        BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(ShapeClut), sprite);
                    rows.Add(new NewRow(new[] { sprite }, row));
                }
            }
            added = rows.Count;
            return Nxd.WithRows(table, rows, out why);
        }

        /// <summary>(1.42.1) The log's line once CharShape has the jobs' own sprites' rows.</summary>
        public static string ShapeLine(int added)
            => $"CharShape: the mods' jobs' own sprites' {added} row{(added == 1 ? "" : "s")} written.";

        /// <summary>(1.43.0) A CharShape row's CharCLUT number (0 for none); the game table CharCLUT (sheet 0xD2, two keys:
        /// that number and a palette's), a row of 0x18 bytes: its Comment's words (+ 4) and its colors (+ 8, a list of
        /// bytes: where from the row's start, and + 0xC how many, 0x30: 16 colors of red, green and blue), a color skin
        /// (+ 0x10, 0 for none) and whether it is used (+ 0x14).</summary>
        public const int ShapeClut = 0xC, ClutSheet = 0xD2, ClutRowBytes = 0x18, ClutComment = 4, ClutData = 8,
                         ClutDataCount = 0xC, ClutSkin = 0x10, ClutUsed = 0x14, ClutColors = 0x30;

        /// <summary>(1.43.0) A CharCLUT row: its bytes, its 16 colors' red, green and blue after them, then eight zeros (its
        /// Comment's words, empty from the row's start or from its field).</summary>
        public static byte[] ClutRow(int[] colors)
        {
            var row = new byte[ClutRowBytes + ClutColors + 8];
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(ClutComment), ClutRowBytes + ClutColors);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(ClutData), ClutRowBytes);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(ClutDataCount), ClutColors);
            row[ClutUsed] = 1;
            for (int n = 0; n < JobFile.PaletteColors; n++)
            {
                row[ClutRowBytes + 3 * n] = (byte)(colors[n] >> 16);
                row[ClutRowBytes + 3 * n + 1] = (byte)(colors[n] >> 8);
                row[ClutRowBytes + 3 * n + 2] = (byte)colors[n];
            }
            return row;
        }

        /// <summary>(1.43.0) The loaded CharCLUT with a row for each palette each job's own sprite has colors for: its key the
        /// sprite's own number (its CharShape row's CharCLUT number) and the palette's. A row another mod has at those
        /// keys is kept, said. Null and why when the table can't be read or isn't one of two keys; `added`, how many rows
        /// it gets.</summary>
        public static byte[]? WithClutRows(ReadOnlySpan<byte> table, IList<JobRoom.Given> given, List<string> said,
                                           out string why, out int added)
        {
            added = 0;
            if (Nxd.Rows(table, out why) == null)
                return null;
            if (Nxd.Keys(table) != 2)
            {
                why = $"it isn't a table of two keys (byte 8: {table[8]})";
                return null;
            }
            var rows = new List<NewRow>();
            foreach (var g in given)
            {
                if (g.Sprite < 0)
                    continue;
                for (int woman = 0; woman < 2; woman++)
                {
                    var palettes = g.Job.Colors[woman];
                    if (palettes == null)
                        continue;
                    int sprite = g.Sprite + woman;
                    for (int p = 0; p < palettes.Length; p++)
                    {
                        if (Nxd.Find(table, new[] { sprite, p }) >= 0)
                        {
                            said.Add($"{g.Job.Who}'s sprite {sprite} keeps the CharCLUT row another mod gives its "
                                     + $"{JobFile.PaletteOrdinals[p]} palette.");
                            continue;
                        }
                        rows.Add(new NewRow(new[] { sprite, p }, ClutRow(palettes[p])));
                    }
                }
            }
            added = rows.Count;
            return Nxd.WithRows(table, rows, out why);
        }

        /// <summary>(1.43.0) The log's line once CharCLUT has the jobs' own colors' rows.</summary>
        public static string ClutLine(int added)
            => $"CharCLUT: the mods' jobs' own colors' {added} row{(added == 1 ? "" : "s")} written.";
    }
}
