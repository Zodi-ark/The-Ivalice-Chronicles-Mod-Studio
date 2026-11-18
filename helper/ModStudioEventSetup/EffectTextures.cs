// Mod Studio Framework: (2.0.0, in the making) an effect's picture at a higher resolution. Part of The Ivalice
// Chronicles Mod Studio, GPL-3.0.
//
// Zodi's second point of 16 November 2026: "replace the effect sprites ... files with those of higher resolution ... In
// game the texture upscaled will be the same size on the screen as before but higher resolution". His choices of 17
// November: both sizes, the game's size first (built in Mod Studio alone: the effect's own file written again); how big,
// "Continue on", up to 4 times; and, once the measure below was put to him with its cost, "Yes, up to 4 times
// (Recommended)": an effect's picture made bigger where the game makes its texture, with no shared texture made bigger.
//
// What was measured in his program (12,158,720 bytes; dev/research/sidequests/effect_textures.py holds each instruction
// this rests on by its bytes and runs 0x41E05C in a machine of its own; claude/texture-resolution-research.md, "Measured
// in the twenty ninth session", says what each means):
//
// - An effect's picture is put in the game's emulated PlayStation video memory at x 384 words, y 0 (0x2741E0), 64 words
//   wide (128 where the byte at its texture section's + 0x403 is set), its rows from the three bytes of its size.
//   A draw takes a page of that memory: page n is x (n mod 16) times 64 words, y (n / 16) times 256, its number kept at
//   0x11A374A (0x25CDCC). At 4 bits a pixel the page's bytes are copied to 0x30F9F9C + n * 0x800C (64 words a row, 256
//   rows), at 8 bits to 0x325A1B0 + n * 0x10010 (128 words a row): 0x25ED60.
// - A page with a palette is a record of 0x3C7C960 (0x468 bytes: + 0 marked to be made, + 4 and + 8 its width and
//   height, 256 by 256 for a page, + 0xC its bits, 0x20, + 0x10 its page's number, + 0x18 the page's bytes, + 0x20 3
//   for indexed pixels, + 0x24 4 at 4 bits a pixel and 5 at 8, + 0x40 its palette as 32 bit colors, + 0x450 a row of the
//   seven pages the game replaces itself or - 1, + 0x460 made): 0x418A48. **0x41E05C makes a marked record's texture.**
//   Only pages 12 to 15 are ever given a cell of the shared texture there (with its switch on and the mode 1); **every
//   other page's record is a texture of its own**: the texture object of the record's own number at 0x2E94390 (0x70
//   bytes each), its pixels made by 0x418F20 into the scratch memory (`[0x2C819C0] + ([0x2C819C8] << 10) - 0x280000`),
//   then sent again by 0x3D0BF8 where the object already has the record's width, height and bits, else noted by
//   0x3D0A80 and made by 0x3D0B10 at that size; the record unmarked and + 0x460 set; 0 returned. An effect's picture
//   lies on pages 6 and 7: always textures of their own.
// - The draw of such a record takes its texture's handle and texture coordinates over the record's own width and height
//   (0x416C7B, 0x417690), and the game itself makes seven of its pages' textures 512 by 512 for records of 256 by 256
//   (from entries of g2d.dat), so **a bigger texture under the same record covers the same place**.
//
// What the framework does with it: a mod's ModStudioTextures.json names, besides its sprites, its effects' bigger
// pictures: {"Effect": its number, "File": the bigger sheet (MSBT, 4 or 8 bits, 2 to 4 times the size, the same color
// numbers), "Picture": the mod's own file of the effect at the game's size}. One hook, on 0x41E05C: for a marked record
// whose page holds part of a mod's effect picture (its page's plain copy, at the bits the bigger picture was given at,
// its bytes there the mod's picture at the game's size, so another effect, or an effect that drew into that memory
// itself, is never taken for it), the framework lets the game make the page's pixels (0x418F20), makes them `scale`
// times bigger (the picture's part from the bigger sheet's color numbers **through the record's own palette**, so every
// palette and every change of color the game makes is kept; the rest of the page the game's pixels repeated), and hands
// them to the game's own routines as the game does at that place (0x3D0BF8, or 0x3D0A80 and 0x3D0B10). Every other
// record goes to the game's own routine, and with no bigger picture the hook isn't made.
//
// (The thirtieth session) A picture may also be **of more colors** (its sheet's file's version 2, OwnColors.cs: each
// pixel its color number and its own color, and the view's palette it was given in), at the game's size or up to 4
// times it: made the same way, but where the record's palette is the one it was given in each pixel of the picture is
// its own color (Bigger); in any other palette (another line of colors, a flash, colors changing as the effect plays)
// its color numbers through the record's palette, as before.
using System;
using System.Buffers;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace ModStudioEventSetup
{
    public static class EffectTextures
    {
        /// <summary>How many times the game's size an effect's bigger picture may be (his choice of 17 November).</summary>
        public const int MinScale = 2, MaxScale = 4;
        /// <summary>Where an effect's picture is in the video memory, in its words (x) and rows (y 0), and how wide a
        /// sheet may be in words.</summary>
        public const int PictureX = 384, NarrowWords = 64, WideWords = 128;
        /// <summary>A page of the video memory: 64 words across, 256 rows; at 4 bits a pixel 4 pixels a word, at 8 bits 2.</summary>
        public const int PageWords = 64, PageRows = 256, PageSide = 256;
        /// <summary>A record's places (0x418A48, 0x41E05C), as measured.</summary>
        public const int RecordBytes = 0x468, RecMarked = 0, RecWidth = 4, RecHeight = 8, RecBits = 0xC, RecPage = 0x10,
                         RecPlace = 0x18, RecKind = 0x20, RecDepth = 0x24, RecPalette = 0x40, RecColors = 0x440,
                         RecEntryRow = 0x450, RecMade = 0x460;
        /// <summary>A record's + 0x20 for indexed pixels, its + 0x24 at 4 and at 8 bits a pixel, its + 0xC (32 bit
        /// pixels), and a texture object's size.</summary>
        public const int KindIndexed = 3, Depth4 = 4, Depth8 = 5, Bits32 = 0x20, ObjectBytes = 0x70;
        /// <summary>A page's copy at 4 and at 8 bits a pixel (0x25ED60), one after another by the page's number.</summary>
        public const int Page4Bytes = 0x800C, Page8Bytes = 0x10010;
        /// <summary>An effect's file: its texture section's place in its header (its tenth offset), and in that section
        /// the size's three bytes, the byte that makes the sheet 128 words wide, and the pixels.</summary>
        public const int TextureOffsetAt = 0x24, SizeAt = 0x400, WideAt = 0x403, PixelsAt = 0x404;

        /// <summary>A mod's bigger picture of an effect: the sheet as the game puts it in the video memory (`Words` words
        /// wide, `Rows` rows, its bytes `Game` from the mod's own file of the effect) and the bigger sheet's color
        /// numbers, a byte a pixel (`Width` by `Height`), at the bits its frames draw it at that it was given in; (the
        /// thirtieth session) or a picture of more colors (`Own`: its pixels, whose numbers are `Big`, and the palette it
        /// was given in), at 1 to 4 times the size.</summary>
        public sealed class Picture
        {
            public int Effect { get; }
            public int Bits { get; }
            public int Scale { get; }
            public int Words { get; }
            public int Rows { get; }
            public byte[] Game { get; }
            public byte[] Big { get; }
            public string Who { get; }
            public OwnColors.Own? Own { get; }
            public int PixelsAWord => Bits == 4 ? 4 : 2;
            public int Width => Words * PixelsAWord * Scale;
            public int Height => Rows * Scale;
            public Picture(int effect, int bits, int scale, int words, int rows, byte[] game, byte[] big, string who,
                           OwnColors.Own? own = null)
            {
                Effect = effect;
                Bits = bits;
                Scale = scale;
                Words = words;
                Rows = rows;
                Game = game;
                Big = big;
                Who = who;
                Own = own;
            }
        }

        /// <summary>The pictures the framework shows: the mods in Reloaded-II's order, a later mod's tried before an
        /// earlier one's (`Tried`), and what was said.</summary>
        public sealed class Plan
        {
            public List<Picture> Pictures { get; } = new List<Picture>();
            public List<string> Said { get; } = new List<string>();
            public bool Any => Pictures.Count > 0;
            public List<Picture> Tried
            {
                get
                {
                    var tried = new List<Picture>(Pictures);
                    tried.Reverse();
                    return tried;
                }
            }
        }

        static bool Has(JsonElement e, string name, out JsonElement value)
        {
            value = default;
            return e.ValueKind == JsonValueKind.Object && e.TryGetProperty(name, out value);
        }

        static string? InsideFile(JsonElement entry, string name)
        {
            string? file = Has(entry, name, out var f) && f.ValueKind == JsonValueKind.String ? f.GetString() : null;
            if (string.IsNullOrEmpty(file) || Path.IsPathRooted(file)
                || Array.IndexOf(file!.Replace('\\', '/').Split('/'), "..") >= 0)
                return null;
            return file;
        }

        /// <summary>A mod's ModStudioTextures.json's list of Effects, each read with its two files (BigTextures.ReadMod
        /// reads the file); what can't be used is said in `problems` and left out.</summary>
        public static List<Picture> ReadEffects(JsonElement effects, string modName, string modFolder, List<string> problems)
        {
            var pictures = new List<Picture>();
            int n = 0;
            foreach (var entry in effects.EnumerateArray())
            {
                n++;
                string what = $"{modName}'s {BigTextures.FileName}, effect {n}";
                if (!Has(entry, "Effect", out var number) || number.ValueKind != JsonValueKind.Number
                    || !number.TryGetInt32(out int effect) || effect < 0 || effect > 511)
                {
                    problems.Add($"{what} names no Effect of the game's (0 to 511)");
                    continue;
                }
                what = $"{modName}'s bigger picture of the effect {effect}";
                string? file = InsideFile(entry, "File"), own = InsideFile(entry, "Picture");
                if (file == null || own == null)
                {
                    problems.Add($"{what} names no File or no Picture inside its mod's folder");
                    continue;
                }
                byte[] sheet, picture;
                try
                {
                    sheet = File.ReadAllBytes(Path.Combine(modFolder, file));
                    picture = File.ReadAllBytes(Path.Combine(modFolder, own));
                }
                catch (Exception e) when (e is IOException || e is UnauthorizedAccessException)
                {
                    problems.Add($"{what} can't be read ({e.Message})");
                    continue;
                }
                var read = Read(effect, sheet, picture, what, problems);
                if (read != null)
                    pictures.Add(read);
            }
            return pictures;
        }

        /// <summary>The sheet an effect's file puts in the video memory, as the game reads it (0x2741E0): `(words wide,
        /// rows, its bytes)`, or null and why where the file has no such sheet.</summary>
        public static (int Words, int Rows, byte[] Bytes)? SheetOf(byte[] file, out string why)
        {
            why = "";
            if (file.Length < TextureOffsetAt + 4)
            {
                why = "it is no effect's file";
                return null;
            }
            long start = BinaryPrimitives.ReadUInt32LittleEndian(file.AsSpan(TextureOffsetAt, 4));
            if (start < TextureOffsetAt + 4 || start + PixelsAt > file.Length)
            {
                why = "its file has no picture";
                return null;
            }
            int size = file[start + SizeAt] | (file[start + SizeAt + 1] << 8) | (file[start + SizeAt + 2] << 16);
            bool wide = file[start + WideAt] != 0;
            int words = wide ? WideWords : NarrowWords, rows = wide ? size >> 8 : size >> 7;
            long bytes = (long)rows * words * 2;
            if (rows <= 0 || rows > PageRows || start + PixelsAt + bytes > file.Length)
            {
                why = $"its picture's size ({size} bytes) isn't one its file holds";
                return null;
            }
            var pixels = new byte[bytes];
            Buffer.BlockCopy(file, (int)(start + PixelsAt), pixels, 0, pixels.Length);
            return (words, rows, pixels);
        }

        /// <summary>A bigger picture from its sheet's file ("MSBT", version 1, 4 or 8 bits a pixel, its scale, its width
        /// and height, then its rows: at 4 bits the left pixel in a byte's low four bits) and the mod's file of the effect;
        /// null and why where the two don't make one.</summary>
        public static Picture? Read(int effect, byte[] sheet, byte[] picture, string what, List<string> problems)
        {
            var game = SheetOf(picture, out string why);
            if (game == null)
            {
                problems.Add($"{what}: its Picture can't be read as the effect's ({why})");
                return null;
            }
            if (sheet.Length < BigTextures.HeaderBytes || sheet[0] != 'M' || sheet[1] != 'S' || sheet[2] != 'B'
                || sheet[3] != 'T' || (sheet[4] != 1 && sheet[4] != OwnColors.Version))
            {
                problems.Add($"{what} isn't a bigger sheet as Mod Studio writes one");
                return null;
            }
            int bits = sheet[5];
            int scale = BinaryPrimitives.ReadUInt16LittleEndian(sheet.AsSpan(6, 2));
            long width = BinaryPrimitives.ReadUInt32LittleEndian(sheet.AsSpan(8, 4));
            long height = BinaryPrimitives.ReadUInt32LittleEndian(sheet.AsSpan(12, 4));
            if (sheet[4] == OwnColors.Version)
                return ReadOwn(effect, sheet, game.Value, bits, scale, width, height, what, problems);
            if (bits != 4 && bits != 8)
            {
                problems.Add($"{what} has {bits} bits a pixel, and an effect's sheet is drawn at 4 or 8");
                return null;
            }
            if (scale < MinScale || scale > MaxScale)
            {
                problems.Add($"{what} is {scale} times the game's size, and a bigger picture of an effect is {MinScale} to "
                             + $"{MaxScale} times");
                return null;
            }
            var (words, rows, bytes) = game.Value;
            long wantWidth = (long)words * (bits == 4 ? 4 : 2) * scale, wantHeight = (long)rows * scale;
            if (width != wantWidth || height != wantHeight)
            {
                problems.Add($"{what} is {width} by {height} pixels, and the effect's sheet at {bits} bits a pixel and "
                             + $"{scale} times the game's size is {wantWidth} by {wantHeight}");
                return null;
            }
            long rowBytes = bits == 4 ? width / 2 : width;
            if (sheet.Length != BigTextures.HeaderBytes + height * rowBytes)
            {
                problems.Add($"{what} holds {sheet.Length} bytes, and its size asks for {BigTextures.HeaderBytes + height * rowBytes}");
                return null;
            }
            var big = new byte[width * height];
            if (bits == 8)
                Buffer.BlockCopy(sheet, BigTextures.HeaderBytes, big, 0, big.Length);
            else
                for (long at = 0; at < big.Length; at++)
                {
                    int b = sheet[BigTextures.HeaderBytes + (at >> 1)];
                    big[at] = (byte)((at & 1) == 0 ? b & 0xF : b >> 4);
                }
            return new Picture(effect, bits, scale, words, rows, bytes, big, what);
        }

        /// <summary>(The thirtieth session) A picture of more colors from its sheet's file, its header read: 32 bits a
        /// pixel, 1 to 4 times the size, its color numbers at the bits a frame draws it at (4 or 8, the file's 17th
        /// byte), its size the effect's sheet's at those bits.</summary>
        static Picture? ReadOwn(int effect, byte[] sheet, (int Words, int Rows, byte[] Bytes) game, int bits, int scale,
                                long width, long height, string what, List<string> problems)
        {
            if (bits != OwnColors.Bits)
            {
                problems.Add($"{what} has {bits} bits a pixel, and a picture of more colors has {OwnColors.Bits}");
                return null;
            }
            if (scale < OwnColors.MinScale || scale > OwnColors.MaxScale)
            {
                problems.Add($"{what} is {scale} times the game's size, and a picture of more colors of an effect is "
                             + $"{OwnColors.MinScale} to {OwnColors.MaxScale} times");
                return null;
            }
            int numbers = sheet.Length > BigTextures.HeaderBytes ? sheet[BigTextures.HeaderBytes] : 0;
            if (numbers != 4 && numbers != 8)
            {
                problems.Add($"{what} has color numbers of {numbers} bits, and an effect's sheet is drawn at 4 or 8");
                return null;
            }
            var (words, rows, bytes) = game;
            long wantWidth = (long)words * (numbers == 4 ? 4 : 2) * scale, wantHeight = (long)rows * scale;
            if (width != wantWidth || height != wantHeight)
            {
                problems.Add($"{what} is {width} by {height} pixels, and the effect's sheet at {numbers} bits a pixel and "
                             + $"{scale} times the game's size is {wantWidth} by {wantHeight}");
                return null;
            }
            var own = OwnColors.Read(sheet, (int)width, (int)height, numbers, what, problems);
            if (own == null)
                return null;
            var big = new byte[own.Pixels.Length];
            for (int n = 0; n < big.Length; n++)
                big[n] = (byte)(own.Pixels[n] >> 24);
            string who = (scale > 1 ? what : what.Replace("'s bigger picture of ", "'s picture of ")) + " in more colors";
            return new Picture(effect, numbers, scale, words, rows, bytes, big, who, own);
        }

        /// <summary>The pictures shown: every mod's in Reloaded-II's order; a later mod's picture of an effect an earlier
        /// one gave too is tried first (said).</summary>
        public static Plan Make(IList<List<Picture>> mods)
        {
            var plan = new Plan();
            var owner = new Dictionary<int, string>();
            foreach (var pictures in mods)
                foreach (var picture in pictures)
                {
                    if (owner.TryGetValue(picture.Effect, out string? earlier))
                        plan.Said.Add($"{picture.Who} is tried before {earlier}, where the game has both mods' effect");
                    owner[picture.Effect] = picture.Who;
                    plan.Pictures.Add(picture);
                }
            return plan;
        }

        /// <summary>The line said once the pictures are joined to the game; (the thirtieth session) with how many of them
        /// are of more colors, where any is.</summary>
        public static string Line(Plan plan)
        {
            int n = plan.Pictures.Count, m = 0;
            foreach (var picture in plan.Pictures)
                if (picture.Own != null)
                    m++;
            string where = $"shown where the game makes {(n == 1 ? "its texture" : "their textures")}, at the same size on the screen";
            if (m == 0)
                return $"{n} bigger picture{(n == 1 ? "" : "s")} of effects {(n == 1 ? "is" : "are")} {where}.";
            return $"{n} picture{(n == 1 ? "" : "s")} of effects {(n == 1 ? "is" : "are")} {where}, "
                   + (n == 1 ? "of more colors where the game makes it in the palette it was given in."
                      : $"{m} of them of more colors where the game makes {(m == 1 ? "it" : "them")} in the palette "
                        + $"{(m == 1 ? "it was" : "each was")} given in.");
        }

        /// <summary>The line said when they can't be shown.</summary>
        public static string NotLine(string why)
            => $"the effects' bigger pictures can't be shown: {why}. Each effect is drawn at the game's size.";

        // --- the places of the game's code ---------------------------------------------------------------------------

        /// <summary>The playback's call of 0x41E05C for each record a draw marked (0x416032, in 0x415D30), found once; the
        /// routine's own first instructions, as the game runs or in its program file where another mod's hook sits there
        /// (SpriteTextures.Routine); and its instructions past them, found once right after them: the scratch memory's
        /// two numbers, the records' place and a record's size (the distances left open).</summary>
        internal const string CallPattern = "8B CB 83 C7 1C E8 ?? ?? ?? ?? 44 0B E0 45 33 C9 EB 03";
        internal const int CallAt = 5;
        internal const string RecordStart
            = "48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18 57 41 54 41 55 41 56 41 57 48 83 EC 60";
        internal const string RecordBody
            = "44 8B 25 ?? ?? ?? ?? 48 8D 05 ?? ?? ?? ?? 4C 8B 2D ?? ?? ?? ?? 41 C1 E4 0A 48 63 E9 41 81 EC 00 00 28 00 48 69 "
              + "FD 68 04 00 00";
        internal const int BodyAt = 0x1C;
        /// <summary>Its way for a record with a texture of its own (0x41E324 to 0x41E3B8): the page's pixels, the texture
        /// object of the record's number, sent again or noted and made, the record unmarked and made.</summary>
        internal const string OwnPattern
            = "8B CD E8 ?? ?? ?? ?? 44 8B 47 04 48 6B C3 70 48 8D 1D ?? ?? ?? ?? 48 8D AB ?? ?? ?? ?? 48 03 E8 44 3B 84 18 ?? "
              + "?? ?? ?? 75 34 8B 4F 08 3B 8C 18 ?? ?? ?? ?? 75 28 8B 84 18 ?? ?? ?? ?? 39 47 0C 75 1C 89 4C 24 28 45 33 C9 "
              + "44 89 44 24 20 49 8B D4 45 33 C0 48 8B CD E8 ?? ?? ?? ?? EB 2D 44 8B 4F 08 49 8B D4 8B 47 0C 48 8B CD 40 88 "
              + "74 24 38 44 89 4C 24 30 44 89 44 24 28 89 44 24 20 E8 ?? ?? ?? ?? 48 8B CD E8 ?? ?? ?? ?? 83 27 00 89 B7 60 04 "
              + "00 00";
        /// <summary>0x25ED60's 8 bit page's copy (its place from the image's start) and its 4 bit one (from the next
        /// instruction).</summary>
        internal const string Pages8Pattern = "48 69 C8 10 00 01 00 89 BC 19 ?? ?? ?? ?? 48 8D 83 ?? ?? ?? ??";
        internal const string Pages4Pattern = "48 0F BF C2 48 69 C8 0C 80 00 00 48 8D 05 ?? ?? ?? ?? 89 3E";

        public sealed class Sites
        {
            public int Record { get; internal set; } = -1;
            public int Pixels { get; internal set; } = -1;
            public int Send { get; internal set; } = -1;
            public int Note { get; internal set; } = -1;
            public int Make { get; internal set; } = -1;
            public int Records { get; internal set; } = -1;
            public int Objects { get; internal set; } = -1;
            public int Scratch { get; internal set; } = -1;
            public int ScratchAt { get; internal set; } = -1;
            public int Pages4 { get; internal set; } = -1;
            public int Pages8 { get; internal set; } = -1;
            public List<string> Missing { get; } = new List<string>();
            public bool Ok => Missing.Count == 0;
        }

        static int I32(ReadOnlySpan<byte> image, int at) => BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at, 4));
        /// <summary>Where an instruction of `length` bytes that ends in a distance from its own end reaches.</summary>
        static int Reach(ReadOnlySpan<byte> image, int at, int length) => at + length + I32(image, at + length - 4);

        /// <summary>Every place the effects' bigger pictures need, each found once in the program as it runs (the making
        /// of a page's texture by its one call, its first instructions in the program file where another mod has hooked
        /// it there).</summary>
        public static Sites Find(ReadOnlySpan<byte> image, List<Section> sections, ProgramFile? file)
        {
            var sites = new Sites();
            int call = SpriteTextures.Once(image, sections, CallPattern, "the playback's making of a page's texture",
                                           sites.Missing);
            int record = call < 0 ? -1 : SpriteTextures.Routine(image, call + CallAt, RecordStart,
                                                                 "the making of a page's texture", sites.Missing, file);
            int body = SpriteTextures.Once(image, sections, RecordBody, "the making of a page's texture's first reads",
                                           sites.Missing);
            int own = SpriteTextures.Once(image, sections, OwnPattern, "the making of a page's own texture", sites.Missing);
            int pages8 = SpriteTextures.Once(image, sections, Pages8Pattern, "the 8 bit pages' copies", sites.Missing);
            int pages4 = SpriteTextures.Once(image, sections, Pages4Pattern, "the 4 bit pages' copies", sites.Missing);
            if (record >= 0 && body >= 0 && body != record + BodyAt)
                sites.Missing.Add("the making of a page's texture's first reads (not where the routine's first instructions "
                                  + "end)");
            else if (record >= 0 && body >= 0)
            {
                sites.Record = record;
                sites.ScratchAt = Reach(image, body, 7);
                sites.Records = Reach(image, body + 7, 7);
                sites.Scratch = Reach(image, body + 14, 7);
            }
            if (own >= 0)
            {
                sites.Pixels = Reach(image, own + 2, 5);
                sites.Objects = I32(image, own + 0x19);
                sites.Send = Reach(image, own + 0x57, 5);
                sites.Note = Reach(image, own + 0x7E, 5);
                sites.Make = Reach(image, own + 0x86, 5);
                if (record >= 0 && (own < record || own > record + 0x400))
                    sites.Missing.Add("the making of a page's own texture (not inside the making of a page's texture)");
            }
            if (pages8 >= 0)
                sites.Pages8 = I32(image, pages8 + 0x11);
            if (pages4 >= 0)
                sites.Pages4 = Reach(image, pages4 + 0xB, 7);
            return sites;
        }

        // --- what the hook does, apart from the hook itself (so the checks program can run it) ------------------------

        /// <summary>Whether a record's page holds part of a picture: the words of the video memory both cover, as
        /// `(first, past)`, and the page's place in words; false where they share none.</summary>
        public static bool Shares(int page, int bits, Picture picture, out int first, out int past, out int pageX)
        {
            pageX = (page & 15) * PageWords;
            int covered = bits == 4 ? PageWords : 2 * PageWords;
            first = Math.Max(pageX, PictureX);
            past = Math.Min(pageX + covered, PictureX + picture.Words);
            return page >= 0 && page < 16 && first < past;
        }

        /// <summary>Whether a page's bytes (`rowBytes` a row from `place`) are the picture at the game's size over the words
        /// both cover.</summary>
        public static unsafe bool Holds(byte* place, int rowBytes, Picture picture, int first, int past, int pageX)
        {
            int count = (past - first) * 2, rows = Math.Min(picture.Rows, PageRows);
            fixed (byte* game = picture.Game)
                for (int r = 0; r < rows; r++)
                {
                    var page = new ReadOnlySpan<byte>(place + (long)r * rowBytes + (first - pageX) * 2, count);
                    var mine = new ReadOnlySpan<byte>(game + (long)r * picture.Words * 2 + (first - PictureX) * 2, count);
                    if (!page.SequenceEqual(mine))
                        return false;
                }
            return true;
        }

        /// <summary>The page's pixels `Scale` times bigger: where the picture lies, its bigger sheet's color numbers
        /// through the record's palette; elsewhere each of the game's pixels (`game`, `side` by `side`) repeated. (The
        /// thirtieth session) A picture of more colors: where the record's palette (`colors` of them) is the one it was
        /// given in (OwnColors.Same), each of its pixels its own color (OwnColors.Pixel).</summary>
        public static unsafe void Bigger(Picture picture, uint* palette, int colors, uint* game, int side, int first, int past,
                                         int pageX, uint* into)
        {
            int n = picture.Scale, big = side * n, ppw = picture.PixelsAWord;
            int fromX = (first - pageX) * ppw, toX = (past - pageX) * ppw, rows = Math.Min(picture.Rows, side);
            int shift = ((first - PictureX) * ppw - fromX) * n, width = picture.Width;
            var own = picture.Own;
            bool same = own != null && OwnColors.Same(palette, colors, own.Tied);
            fixed (byte* numbers = picture.Big)
            fixed (uint* mine = own != null ? own.Pixels : null)
                for (int y = 0; y < big; y++)
                {
                    uint* row = into + (long)y * big;
                    uint* gameRow = game + (long)(y / n) * side;
                    bool inRows = y / n < rows;
                    byte* sheetRow = numbers + (long)y * width;
                    uint* ownRow = mine + (long)y * width;
                    for (int x = 0; x < big; x++)
                    {
                        int px = x / n;
                        if (!inRows || px < fromX || px >= toX)
                            row[x] = gameRow[px];
                        else if (same)
                            row[x] = OwnColors.Pixel(palette[sheetRow[x + shift]], ownRow[x + shift]);
                        else
                            row[x] = palette[sheetRow[x + shift]];
                    }
                }
        }

        /// <summary>What the hook does with a record the game is about to make a texture of. `pixels` is the game's own
        /// making of the page's pixels (0x418F20, the record's number) answering where they were made; `send` the sending
        /// of pixels again (0x3D0BF8: the object, the pixels, x, y, width, height); `note` the noting of new pixels
        /// (0x3D0A80: the object, the pixels, width, height, bits, the width and height kept, a byte); `make` the making
        /// on the card (0x3D0B10).</summary>
        public sealed unsafe class Logic
        {
            readonly List<Picture> _tried;
            readonly nint _records, _objects, _pages4, _pages8;
            readonly Func<int, nint> _pixels;
            readonly Action<nint, nint, int, int, int, int> _send;
            readonly Action<nint, nint, int, int, int, int, int, byte> _note;
            readonly Func<nint, int> _make;
            readonly Action<string> _say;
            int _saidFirst, _made;

            public Logic(Plan plan, nint records, nint objects, nint pages4, nint pages8, Func<int, nint> pixels,
                         Action<nint, nint, int, int, int, int> send, Action<nint, nint, int, int, int, int, int, byte> note,
                         Func<nint, int> make, Action<string> say)
            {
                _tried = plan.Tried;
                _records = records;
                _objects = objects;
                _pages4 = pages4;
                _pages8 = pages8;
                _pixels = pixels;
                _send = send;
                _note = note;
                _make = make;
                _say = say;
            }

            static int Int(nint at, int plus) => *(int*)(at + plus);
            static void Int(nint at, int plus, int value) => *(int*)(at + plus) = value;

            /// <summary>How many bigger textures were made (for the checks).</summary>
            public int Made => _made;

            /// <summary>The picture a record's page holds, the words both cover and the page's place, where the record is
            /// one this answers: marked, no page the game replaces itself, a page of 256 by 256 indexed pixels at 4 or 8
            /// bits, its bytes its page's plain copy (a draw with a texture window has another), holding part of a
            /// picture given at its bits whose bytes there are the mod's at the game's size. Null for any other.</summary>
            public Picture? Holding(int index, out int first, out int past, out int pageX)
            {
                first = past = pageX = 0;
                nint record = _records + (nint)index * RecordBytes;
                if (index < 0 || Int(record, RecMarked) == 0 || Int(record, RecEntryRow) != -1
                    || Int(record, RecKind) != KindIndexed || Int(record, RecWidth) != PageSide
                    || Int(record, RecHeight) != PageSide || Int(record, RecBits) != Bits32)
                    return null;
                int depth = Int(record, RecDepth), page = Int(record, RecPage);
                int bits = depth == Depth4 ? 4 : depth == Depth8 ? 8 : 0;
                if (bits == 0 || page < 0 || page > 31)
                    return null;
                nint plain = bits == 4 ? _pages4 + (nint)page * Page4Bytes : _pages8 + (nint)page * Page8Bytes;
                nint place = *(nint*)(record + RecPlace);
                if (place != plain)
                    return null;
                int rowBytes = bits == 4 ? PageSide / 2 : PageSide;
                foreach (var picture in _tried)
                    if (picture.Bits == bits && Shares(page, bits, picture, out first, out past, out pageX)
                        && Holds((byte*)place, rowBytes, picture, first, past, pageX))
                        return picture;
                return null;
            }

            /// <summary>The game is to make record `index`'s texture (0x41E05C). True where this made it bigger, as the
            /// game's own routine would have made it at the game's size (the record unmarked, + 0x460 set); false to hand
            /// the record to the game's own routine.</summary>
            public bool OnRecord(int index)
            {
                var picture = Holding(index, out int first, out int past, out int pageX);
                if (picture == null)
                    return false;
                nint record = _records + (nint)index * RecordBytes;
                nint game = _pixels(index);
                if (game == 0)
                    return false;
                int n = picture.Scale, side = PageSide * n;
                nint texture = _objects + (nint)index * ObjectBytes;
                uint[] rented = ArrayPool<uint>.Shared.Rent(side * side);
                try
                {
                    fixed (uint* big = rented)
                    {
                        Bigger(picture, (uint*)(record + RecPalette), Int(record, RecColors), (uint*)game, PageSide, first,
                               past, pageX, big);
                        if (Int(texture, BigTextures.TexNotedWidth) == side && Int(texture, BigTextures.TexNotedHeight) == side
                            && Int(texture, BigTextures.TexNotedBits) == Bits32 && Int(texture, BigTextures.TexHandle) != 0)
                            _send(texture, (nint)big, 0, 0, side, side);
                        else
                        {
                            // Noted at a size the object hasn't (the game notes the size it keeps with its own), so the
                            // game's making makes it anew and lets go of the pixels, which are the framework's, lent for
                            // the call (0x3D0B10 clears the object's + 0x18 once the texture is made).
                            _note(texture, (nint)big, side, side, Bits32, side, side, 1);
                            _make(texture);
                        }
                    }
                }
                finally
                {
                    ArrayPool<uint>.Shared.Return(rented);
                }
                Int(record, RecMarked, 0);
                Int(record, RecMade, 1);
                System.Threading.Interlocked.Increment(ref _made);
                if (System.Threading.Interlocked.Exchange(ref _saidFirst, 1) == 0)
                    _say($"the game was given {OwnColors.Kind(picture.Scale, picture.Own != null)} of an effect for the first "
                         + $"time ({picture.Who}, {side} by {side} pixels for a page of the game's {PageSide} by {PageSide}).");
                return true;
            }
        }
    }
}
