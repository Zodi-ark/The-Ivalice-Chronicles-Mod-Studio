// Mod Studio Framework: (2.0.0, in the making) a sprite's textures at a higher resolution. Part of The Ivalice Chronicles
// Mod Studio, GPL-3.0.
//
// Zodi's second point of 16 November 2026: "replace the effect sprites (this can apply to all sprites as well) files with
// those of higher resolution ... In game the texture upscaled will be the same size on the screen as before but higher
// resolution. New Jobs sprites should be able to have this as well." His choice of 16 November: the modder gives the
// bigger picture on Mod Studio's Textures page, and Mod Studio works out which texture it stands for. This file and
// BigTextureHooks.cs are the sprites' part; the effects' pictures take another way to the card and are not built
// (claude/texture-resolution-research.md says which).
//
// What was measured in his program (12,158,720 bytes; dev/research/sidequests/big_textures.py holds each instruction this
// rests on by its bytes, and the note says what each means):
//
// - A sprite's sheet is an entry of g2d.dat, 512 pixels wide at 4 bits a pixel, unpacked by one routine (0x3D25D8: the
//   file's object, the entry, where to; it answers how many bytes). Nothing draws from it: the game makes 32 bit pixels
//   on the CPU from the sheet and a palette of 32 bit colors (0x41DC34 makes one from 15 bit colors: each part's five
//   bits shifted up three, the top byte 0xFF, the first color 0 where asked), and hands those to the card through one
//   routine, 0x3D0B10 (a texture object: + 0x18 its pixels, + 0x38 and + 0x3C its width and height, + 0x44 and + 0x48
//   the same as floats, + 0x30 its handle once made, + 0x4C set where it is only to be sent again at the size noted at
//   + 0x24 and + 0x28, + 0x20 set where the game owns the pixels and frees them).
// - Three places make such pixels from a sheet. **The battle's slots** (0x3D0F8C; a slot is 0x5298 bytes, + 0xA84 the
//   entry it holds, + 0xA88 the entry unpacked, + 0xA90 its 0x80 variants of 0x90 bytes, each a texture object): a
//   rectangle x, y, w, h of the sheet through the palette it is handed, into the caller's memory, then made a texture
//   of w by h (made anew where the variant has no texture or one of another size; sent again where the size is the
//   same). **The menus' figures** (0xCE204): the whole sheet, 512 by 512, the entry unpacked 0x100000 bytes past the
//   pixels in one block of memory. **A whole entry in the battle** (0x415D30, its kinds 5 to 7): 512 by 512, the pixels
//   right after the unpacked entry.
// - **No draw asks the card's texture for its size.** A slot's draw divides its texture coordinates by the rectangle's
//   own width and height (0x41AE44: the rectangle from 0x41AC00, its + 8 and + 0xC made floats); the menus' figures
//   divide by constants (0xCD458: 1/256); the battle's other textured primitives by the game's own record of the
//   texture (0x417690). So a texture with more pixels in it, under the same numbers, covers the same place on the
//   screen.
//
// What the framework does with it: a mod's ModStudioTextures.json names sheets of the same colour numbers at 2 to 8
// times the size (BigTextures.Read), each for an entry of g2d.dat or for a job of the mod's own (its man's or woman's
// upper or lower texture, which the framework answers at entries of its own: SpriteTextures.cs). Where the game makes a
// texture from such an entry, the framework makes the same rectangle from the bigger sheet through the same palette,
// lets the game's own routine make the texture from those pixels at their size, and puts the object's width and height
// back to the game's (Logic.OnMake). **The palette is the game's own of that moment**, so every palette a unit wears and
// every change the game makes to one colors the bigger sheet as it colors the game's. Nothing of the game's code is
// changed; four routines are hooked (BigTextureHooks.cs) and two of the game's own are called (a texture freed, 0x3D0C6C;
// a slot's variant freed, 0x3D11DC), and with no bigger sheet none of this is made.
//
// (The thirtieth session) A sheet may also be **of more colors** (its file's version 2, OwnColors.cs: each pixel its
// color number and its own color, and the palette it was given in), at the game's size or up to 4 times it: drawn the
// same way, but where the palette of that moment is the one it was given in each pixel is its own color (Region).
//
// (2.0.4, the thirty fourth session; his Lich test of 17 November) A sheet may also be **of 8 bits a pixel**: the 16
// summons' own sheets. Measured in his program (dev/research/sidequests/summon_sheets.py holds each instruction by its
// bytes and runs 0xD2C74, 0x41AAAC and 0x3D0F8C in a machine; claude/texture-resolution-research-continued.md, "The
// summons' remastered sheets, measured", says what each means): in the enhanced look a summon (the game's table
// RefinedVFXTexture's + 0x18 set: 0xD2AB8) is drawn from g2d.dat's entry 1426 plus two times its effect's number,
// 512 by 512 at 8 bits, through the battle's slots 15 to 17 (0x415D30: the entry unpacked by 0x3D25D8; 256 colors
// read from the emulated video memory at the draw's color table, made by 0x41DC34 with the first cleared; the sheet
// 512 wide where + 0x19 is set), 0x3D0F8C making a rectangle twice the draw's own texture coordinates (0x41AAAC),
// each pixel palette[sheet[(y + r) * 512 + x + c]]. So the slots' part draws a sheet of 8 bits as it draws one of 4
// (OnSlot, Region): the rectangle from the bigger sheet's bytes through the 256 colors in hand.
using System;
using System.Buffers;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace ModStudioEventSetup
{
    public static class BigTextures
    {
        public const string FileName = "ModStudioTextures.json";
        /// <summary>A sheet's width in the game's pixels, the most rows of one, and the sizes a bigger one may have.</summary>
        public const int SheetWidth = 512, SheetRows = 512, MinScale = 2, MaxScale = 8;
        /// <summary>A bigger sheet's file: "MSBT", its version (1), its bits a pixel (4), its scale (two bytes), its
        /// width and its height in pixels (four bytes each), then its rows, the left pixel in a byte's low four bits.</summary>
        public const int HeaderBytes = 16;
        static readonly byte[] Magic = { (byte)'M', (byte)'S', (byte)'B', (byte)'T' };
        /// <summary>(2.0.4) g2d.dat's entries of the effects' own sheets: two for each of the 512 effects from 1426
        /// (0xD2C74: 1426 plus two times the effect's number), the summons' drawn at 8 bits a pixel; every other entry
        /// the framework is asked for is a sprite's, at 4.</summary>
        public const int EffectEntries = 1426, EffectEntriesEnd = 1426 + 2 * 512;

        /// <summary>(2.0.4) The bits a pixel the game draws an entry's sheet at: a summon's own sheet 8, a sprite's 4.</summary>
        public static int BitsOf(int entry) => entry >= EffectEntries && entry < EffectEntriesEnd ? 8 : 4;

        /// <summary>A sheet at `Scale` times the game's size: `Rows` of the game's rows, each row `Scale * 256` bytes;
        /// (the thirtieth session) or a sheet of more colors (`Own`, its pixels and the palette it was given in; its
        /// `Pixels` then empty); (2.0.4) its color numbers 4 bits or 8 (`Bits`: a summon's own sheet, each row then
        /// `Scale * 512` bytes).</summary>
        public sealed class Sheet
        {
            public int Scale { get; }
            public int Rows { get; }
            public byte[] Pixels { get; }
            public string Who { get; }
            public OwnColors.Own? Own { get; }
            public int Bits { get; }
            public int Width => SheetWidth * Scale;
            public int Height => Rows * Scale;
            /// <summary>How many colors its palette has.</summary>
            public int Colors => 1 << Bits;
            public Sheet(int scale, int rows, byte[] pixels, string who, OwnColors.Own? own = null, int bits = 4)
            {
                Scale = scale;
                Rows = rows;
                Pixels = pixels;
                Who = who;
                Own = own;
                Bits = bits;
            }

            /// <summary>The same sheet said as a picture of more colors (where it is one): "...'s picture of the game's
            /// texture N in more colors", or "...'s bigger picture of ... in more colors".</summary>
            public Sheet Named()
                => Own == null ? this
                   : new Sheet(Scale, Rows, Pixels, (Scale > 1 ? Who : Who.Replace("'s bigger picture of ", "'s picture of "))
                                                     + " in more colors", Own, Bits);
        }

        /// <summary>What a mod asks: a sheet for an entry of g2d.dat (`Entry` 0 or more), or for a job of its own (`Job`
        /// its Name, its woman's or its man's, its lower or its upper texture).</summary>
        public sealed class Ask
        {
            public int Entry { get; internal set; } = -1;
            public string Job { get; internal set; } = "";
            public bool Woman { get; internal set; }
            public bool Lower { get; internal set; }
            public Sheet Sheet { get; internal set; } = null!;
        }

        public sealed class ModTextures
        {
            public string ModId { get; internal set; } = "";
            public string ModName { get; internal set; } = "";
            public List<Ask> Asks { get; } = new List<Ask>();
            /// <summary>(The twenty ninth session) Its effects' bigger pictures (EffectTextures.cs).</summary>
            public List<EffectTextures.Picture> Effects { get; } = new List<EffectTextures.Picture>();
        }

        /// <summary>The sheets the framework shows, by the entry each stands for, and what was said.</summary>
        public sealed class Plan
        {
            public Dictionary<int, Sheet> Sheets { get; } = new Dictionary<int, Sheet>();
            public List<string> Said { get; } = new List<string>();
            public bool Any => Sheets.Count > 0;
        }

        static bool Has(JsonElement e, string name, out JsonElement value)
        {
            value = default;
            return e.ValueKind == JsonValueKind.Object && e.TryGetProperty(name, out value);
        }

        /// <summary>A mod's ModStudioTextures.json with its sheets' files; null where the mod has none. What can't be
        /// used is said in `problems` and left out.</summary>
        public static ModTextures? ReadMod(string modId, string modName, string modFolder, List<string> problems)
        {
            string path = Path.Combine(modFolder, FileName);
            if (!File.Exists(path))
                return null;
            var mod = new ModTextures { ModId = modId, ModName = modName };
            string text;
            try
            {
                text = File.ReadAllText(path);
            }
            catch (Exception e) when (e is IOException || e is UnauthorizedAccessException)
            {
                problems.Add($"{modName}'s {FileName} can't be read ({e.Message})");
                return mod;
            }
            JsonDocument document;
            try
            {
                document = JsonDocument.Parse(text, new JsonDocumentOptions { AllowTrailingCommas = true,
                                                                              CommentHandling = JsonCommentHandling.Skip });
            }
            catch (JsonException e)
            {
                problems.Add($"{modName}'s {FileName} isn't JSON ({e.Message})");
                return mod;
            }
            using (document)
            {
                // A list of Sprites, of Effects (the twenty ninth session: EffectTextures.ReadEffects), or both.
                bool hasSprites = Has(document.RootElement, "Sprites", out var sprites) && sprites.ValueKind == JsonValueKind.Array;
                bool hasEffects = Has(document.RootElement, "Effects", out var effects) && effects.ValueKind == JsonValueKind.Array;
                if (!hasSprites && !hasEffects)
                {
                    problems.Add($"{modName}'s {FileName} has no list of Sprites or of Effects");
                    return mod;
                }
                if (hasEffects)
                    mod.Effects.AddRange(EffectTextures.ReadEffects(effects, modName, modFolder, problems));
                if (!hasSprites)
                    return mod;
                int n = 0;
                foreach (var entry in sprites.EnumerateArray())
                {
                    n++;
                    string what = $"{modName}'s {FileName}, sprite {n}";
                    var ask = new Ask();
                    bool byEntry = Has(entry, "Entry", out var number);
                    bool byJob = Has(entry, "Job", out var job);
                    if (byEntry == byJob)
                    {
                        problems.Add($"{what} names an Entry of the game's textures or a Job of its mod's own, one of the two");
                        continue;
                    }
                    if (byEntry)
                    {
                        if (number.ValueKind != JsonValueKind.Number || !number.TryGetInt32(out int at) || at < 0
                            || at >= SpriteTextures.FirstEntry)
                        {
                            problems.Add($"{what}'s Entry is a texture of the game's (0 to {SpriteTextures.FirstEntry - 1}), "
                                         + $"not {number.GetRawText()}");
                            continue;
                        }
                        ask.Entry = at;
                        // (2.0.4) A summon's own sheet is named by its effect, where the mod says which.
                        what = Has(entry, "Effect", out var effect) && effect.ValueKind == JsonValueKind.Number
                               && effect.TryGetInt32(out int effectNumber) && effectNumber >= 0
                            ? $"{modName}'s bigger picture of effect {effectNumber}'s own sheet (the game's texture {at})"
                            : $"{modName}'s bigger picture of the game's texture {at}";
                    }
                    else
                    {
                        string? name = job.ValueKind == JsonValueKind.String ? job.GetString() : null;
                        string? who = Has(entry, "Who", out var w) && w.ValueKind == JsonValueKind.String ? w.GetString() : null;
                        string? half = Has(entry, "Half", out var h) && h.ValueKind == JsonValueKind.String ? h.GetString() : null;
                        if (string.IsNullOrEmpty(name) || (who != "Man" && who != "Woman") || (half != "Upper" && half != "Lower"))
                        {
                            problems.Add($"{what} names a Job with Who (\"Man\" or \"Woman\") and Half (\"Upper\" or \"Lower\")");
                            continue;
                        }
                        ask.Job = name!;
                        ask.Woman = who == "Woman";
                        ask.Lower = half == "Lower";
                        what = $"{modName}'s bigger picture of {name}'s {who!.ToLowerInvariant()}'s {half!.ToLowerInvariant()} texture";
                    }
                    string? file = Has(entry, "File", out var f) && f.ValueKind == JsonValueKind.String ? f.GetString() : null;
                    if (string.IsNullOrEmpty(file) || Path.IsPathRooted(file) || file!.Replace('\\', '/').Split('/').Length == 0
                        || Array.IndexOf(file.Replace('\\', '/').Split('/'), "..") >= 0)
                    {
                        problems.Add($"{what} names no File inside its mod's folder");
                        continue;
                    }
                    byte[] bytes;
                    try
                    {
                        bytes = File.ReadAllBytes(Path.Combine(modFolder, file));
                    }
                    catch (Exception e) when (e is IOException || e is UnauthorizedAccessException)
                    {
                        problems.Add($"{what} can't be read ({e.Message})");
                        continue;
                    }
                    var sheet = ReadSheet(bytes, what, problems, byEntry ? BitsOf(ask.Entry) : 4);
                    if (sheet == null)
                        continue;
                    ask.Sheet = sheet.Named();
                    mod.Asks.Add(ask);
                }
            }
            return mod;
        }

        /// <summary>A bigger sheet's file read; null and why where it isn't one. (The thirtieth session) Its version 2 is
        /// a sheet of more colors (OwnColors.Read), at 1 to 4 times the game's size. (2.0.4) Its color numbers have the
        /// bits its entry's are drawn at (`bits`: BitsOf, a summon's 8, a sprite's 4).</summary>
        public static Sheet? ReadSheet(byte[] bytes, string what, List<string> problems, int bits = 4)
        {
            if (bytes.Length < HeaderBytes || !bytes.AsSpan(0, 4).SequenceEqual(Magic)
                || (bytes[4] != 1 && bytes[4] != OwnColors.Version))
            {
                problems.Add($"{what} isn't a bigger sheet as Mod Studio writes one");
                return null;
            }
            int fileBits = bytes[5];
            int scale = BinaryPrimitives.ReadUInt16LittleEndian(bytes.AsSpan(6, 2));
            long width = BinaryPrimitives.ReadUInt32LittleEndian(bytes.AsSpan(8, 4));
            long height = BinaryPrimitives.ReadUInt32LittleEndian(bytes.AsSpan(12, 4));
            if (bytes[4] == OwnColors.Version)
                return ReadOwn(bytes, fileBits, scale, width, height, what, problems, bits);
            if (fileBits != bits)
            {
                problems.Add($"{what} has {fileBits} bits a pixel, and {(bits == 8 ? "a summon's sheet has 8" : "a sheet has 4")}");
                return null;
            }
            if (scale < MinScale || scale > MaxScale)
            {
                problems.Add($"{what} is {scale} times the game's size, and a bigger sheet is {MinScale} to {MaxScale} times");
                return null;
            }
            if (width != (long)SheetWidth * scale || height < scale || height > (long)SheetRows * scale || height % scale != 0)
            {
                problems.Add($"{what} is {width} by {height} pixels, and a sheet at {scale} times the game's size is "
                             + $"{SheetWidth * scale} wide and {scale} to {SheetRows * scale} tall, by whole rows of the game's");
                return null;
            }
            long wanted = HeaderBytes + height * (bits == 8 ? width : width / 2);
            if (bytes.Length != wanted)
            {
                problems.Add($"{what} holds {bytes.Length} bytes, and its size asks for {wanted}");
                return null;
            }
            var pixels = new byte[bytes.Length - HeaderBytes];
            Buffer.BlockCopy(bytes, HeaderBytes, pixels, 0, pixels.Length);
            return new Sheet(scale, (int)(height / scale), pixels, what, null, bits);
        }

        /// <summary>(The thirtieth session) A sheet of more colors' file, its header read: 32 bits a pixel, 1 to 4 times
        /// the game's size, its color numbers 4 bits, given in a palette of 16 colors; (2.0.4) or a summon's, 8 bits in a
        /// palette of 256.</summary>
        static Sheet? ReadOwn(byte[] bytes, int bits, int scale, long width, long height, string what, List<string> problems,
                              int numberBits)
        {
            if (bits != OwnColors.Bits)
            {
                problems.Add($"{what} has {bits} bits a pixel, and a sheet of more colors has {OwnColors.Bits}");
                return null;
            }
            if (scale < OwnColors.MinScale || scale > OwnColors.MaxScale)
            {
                problems.Add($"{what} is {scale} times the game's size, and a sheet of more colors is {OwnColors.MinScale} "
                             + $"to {OwnColors.MaxScale} times");
                return null;
            }
            if (width != (long)SheetWidth * scale || height < scale || height > (long)SheetRows * scale || height % scale != 0)
            {
                problems.Add($"{what} is {width} by {height} pixels, and a sheet at {scale} times the game's size is "
                             + $"{SheetWidth * scale} wide and {scale} to {SheetRows * scale} tall, by whole rows of the game's");
                return null;
            }
            var own = OwnColors.Read(bytes, (int)width, (int)height, numberBits, what, problems);
            return own == null ? null : new Sheet(scale, (int)(height / scale), Array.Empty<byte>(), what, own, numberBits);
        }

        /// <summary>The sheets shown, by entry: the mods in Reloaded-II's order, a later mod's sheet for an entry in an
        /// earlier one's place (said). `jobEntry` answers a job's own sprite's upper texture's entry by its mod, its
        /// Name and whether its woman's, or less than 0 where the framework doesn't answer that job's textures.</summary>
        public static Plan Make(IList<ModTextures> mods, Func<string, string, bool, int> jobEntry)
        {
            var plan = new Plan();
            var owner = new Dictionary<int, string>();
            foreach (var mod in mods)
                foreach (var ask in mod.Asks)
                {
                    int entry = ask.Entry;
                    if (entry < 0)
                    {
                        int upper = jobEntry(mod.ModId, ask.Job, ask.Woman);
                        if (upper < 0)
                        {
                            plan.Said.Add($"{ask.Sheet.Who} is left out: {ask.Job} isn't a job of {mod.ModName}'s with "
                                          + $"textures of its own for its {(ask.Woman ? "woman" : "man")} that the game was given");
                            continue;
                        }
                        entry = upper + (ask.Lower ? 1 : 0);
                    }
                    if (owner.TryGetValue(entry, out string? earlier))
                        plan.Said.Add($"{ask.Sheet.Who} is shown in the place of {earlier}");
                    owner[entry] = ask.Sheet.Who;
                    plan.Sheets[entry] = ask.Sheet;
                }
            return plan;
        }

        /// <summary>The line said once the sheets are joined to the game; (the thirtieth session) with how many of them
        /// are of more colors, where any is.</summary>
        public static string Line(Plan plan)
        {
            int n = plan.Sheets.Count, m = 0, summons = 0;
            foreach (var sheet in plan.Sheets.Values)
            {
                if (sheet.Own != null)
                    m++;
                if (sheet.Bits == 8)
                    summons++;
            }
            // (2.0.4) A summon's own sheet (8 bits) is said as one.
            string of = summons == 0 ? "sprites" : summons == n ? "summons' sheets" : "sprites and summons' sheets";
            string where = $"shown where the game draws {(n == 1 ? "its texture" : "their textures")}, at the same size on the screen";
            if (m == 0)
                return $"{n} bigger picture{(n == 1 ? "" : "s")} of {of} {(n == 1 ? "is" : "are")} {where}.";
            return $"{n} picture{(n == 1 ? "" : "s")} of {of} {(n == 1 ? "is" : "are")} {where}, "
                   + (n == 1 ? "of more colors where the game draws it in the palette it was given in."
                      : $"{m} of them of more colors where the game draws {(m == 1 ? "it" : "them")} in the palette "
                        + $"{(m == 1 ? "it was" : "each was")} given in.");
        }

        /// <summary>The line said when they can't be shown.</summary>
        public static string NotLine(string why)
            => $"the sprites' bigger pictures can't be shown: {why}. Each sprite is drawn at the game's size.";

        // --- the places of the game's code ---------------------------------------------------------------------------

        /// <summary>The routines' own first instructions and the instructions that say how the game lays its textures
        /// out, each found once in his program (the distances a call or a read names left open).</summary>
        internal const string SlotPattern
            = "48 89 5C 24 08 48 89 74 24 10 44 89 4C 24 20 57 41 54 41 55 41 56 41 57 48 83 EC 50 4C 8B 99 88 0A 00 00 48 8D "
              + "99 90 0A 00 00";
        internal const string MakePattern = "48 89 5C 24 08 57 48 83 EC 30 83 79 4C 00 48 8B D9 74 22 8B 41 28 45 33";
        internal const string FreePattern
            = "48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18 57 48 83 EC 20 48 8B D9 33 ED 48 8B 49 18";
        internal const string FreeVariantPattern = "40 53 48 83 EC 20 48 63 C2 48 8B D9 48 81 C1 90 0A 00 00 48 8D 14 C0 33";
        internal const string PalettePattern
            = "48 8B C4 48 89 58 08 48 89 68 10 48 89 70 18 48 89 78 20 41 56 4C 63 5C 24 30";
        /// <summary>The battle's read of the entry a slot holds (+ 0xA84), the menus' figures' unpacking 0x100000 bytes
        /// past their pixels, and a whole entry's pixels right after its unpacked bytes.</summary>
        internal const string SlotEntryPattern = "44 89 20 83 FE FF 0F 84 ?? ?? ?? ?? 39 B0 84 0A 00 00";
        internal const string MenusPattern = "48 05 00 00 10 00 44 8D 47 01 45 33 C9 48 89 45";
        internal const string WholePattern = "4D 63 F4 48 8D 05 ?? ?? ?? ?? 4C 03 F3";

        /// <summary>The slot's and a texture object's own places, as measured.</summary>
        public const int SlotEntry = 0xA84, SlotVariants = 0xA90, VariantBytes = 0x90;
        public const int TexPixels = 0x18, TexOwned = 0x20, TexNotedWidth = 0x24, TexNotedHeight = 0x28, TexNotedBits = 0x2C,
                         TexHandle = 0x30, TexBits = 0x34, TexWidth = 0x38, TexHeight = 0x3C, TexWidthF = 0x44,
                         TexHeightF = 0x48, TexAgain = 0x4C, TexKind = 0x50;
        /// <summary>How far past the menus' figures' pixels their entry is unpacked.</summary>
        public const int MenusApart = 0x100000;

        public sealed class Sites
        {
            public int Slot { get; internal set; } = -1;
            public int Make { get; internal set; } = -1;
            public int Free { get; internal set; } = -1;
            public int FreeVariant { get; internal set; } = -1;
            public int Palette { get; internal set; } = -1;
            public int Decode { get; internal set; } = -1;
            public int Archive { get; internal set; } = -1;
            public List<string> Missing { get; } = new List<string>();
            public bool Ok => Missing.Count == 0;
        }

        /// <summary>Every place the bigger pictures need, each found once; the unpacking of an entry and the textures'
        /// file as the jobs' own textures find them (SpriteTextures.Find: where another mod has hooked the routine, by
        /// the game's program file).</summary>
        public static Sites Find(ReadOnlySpan<byte> image, List<Section> sections, ProgramFile? file)
        {
            var sites = new Sites();
            sites.Slot = SpriteTextures.Once(image, sections, SlotPattern, "the battle's making of a sprite's texture", sites.Missing);
            sites.Make = SpriteTextures.Once(image, sections, MakePattern, "the making of a texture on the card", sites.Missing);
            sites.Free = SpriteTextures.Once(image, sections, FreePattern, "the freeing of a texture", sites.Missing);
            sites.FreeVariant = SpriteTextures.Once(image, sections, FreeVariantPattern, "the freeing of a sprite's texture",
                                                    sites.Missing);
            sites.Palette = SpriteTextures.Once(image, sections, PalettePattern, "the making of a palette's colors", sites.Missing);
            SpriteTextures.Once(image, sections, SlotEntryPattern, "the battle's read of the texture a sprite holds", sites.Missing);
            SpriteTextures.Once(image, sections, MenusPattern, "the menus' unpacking of a figure's texture", sites.Missing);
            SpriteTextures.Once(image, sections, WholePattern, "the battle's unpacking of a whole texture", sites.Missing);
            var reads = SpriteTextures.Find(image, sections, file);
            sites.Missing.AddRange(reads.Missing);
            sites.Decode = reads.Decode;
            sites.Archive = reads.Archive;
            return sites;
        }

        // --- the pixels ----------------------------------------------------------------------------------------------

        /// <summary>The rectangle x, y, w, h of the game's sheet as the bigger sheet has it, through a palette of 32 bit
        /// colors: `Scale * w` by `Scale * h` pixels written to `into`, row after row. A place past the sheet's rows or
        /// its width takes the palette's first color (the game's sheet has nothing there either). (The thirtieth
        /// session) A sheet of more colors: where the palette is the one it was given in, each pixel its own color
        /// (OwnColors.Pixel); (2.0.2) where it is that palette through one of the game's tints (a status, the darkness, a
        /// highlight: OwnColors.TintOf), each pixel its own color through that tint; in any other, its color number
        /// through the palette. `tinted`, where given, is told the tint each time one is used.</summary>
        public static unsafe void Region(Sheet sheet, uint* palette, int x, int y, int w, int h, uint* into,
                                         Action<OwnColors.Tint>? tinted = null)
        {
            // (2.0.4) A summon's sheet of 8 bits: a byte a pixel, through 256 colors.
            bool eight = sheet.Bits == 8;
            int scale = sheet.Scale, width = sheet.Width, height = sheet.Height, rowBytes = eight ? width : width / 2;
            int outWidth = w * scale, outHeight = h * scale, left = x * scale, top = y * scale;
            uint first = palette[0];
            if (sheet.Own != null)
            {
                var tint = OwnColors.TintOf(palette, sheet.Colors, sheet.Own);
                if (tint != null && !tint.IsNone)
                    tinted?.Invoke(tint);
                OwnRegion(sheet.Own, width, height, palette, tint, left, top, outWidth, outHeight, into);
                return;
            }
            fixed (byte* pixels = sheet.Pixels)
            {
                for (int r = 0; r < outHeight; r++)
                {
                    uint* row = into + (long)r * outWidth;
                    int from = top + r;
                    if (from < 0 || from >= height)
                    {
                        for (int c = 0; c < outWidth; c++)
                            row[c] = first;
                        continue;
                    }
                    byte* line = pixels + (long)from * rowBytes;
                    for (int c = 0; c < outWidth; c++)
                    {
                        int at = left + c;
                        if (at < 0 || at >= width)
                            row[c] = first;
                        else if (eight)
                            row[c] = palette[line[at]];
                        else
                        {
                            int b = line[at >> 1];
                            row[c] = palette[(at & 1) == 0 ? b & 0xF : b >> 4];
                        }
                    }
                }
            }
        }

        /// <summary>(The thirtieth session) Region's rectangle of a sheet of more colors, `outWidth` by `outHeight` from
        /// `left`, `top` of the sheet's own pixels: each its own color where the palette is the one given (`tint` None),
        /// its own color through the tint where it is that palette tinted (2.0.2), else its number through the palette;
        /// past the sheet, the palette's first color.</summary>
        static unsafe void OwnRegion(OwnColors.Own own, int width, int height, uint* palette, OwnColors.Tint? tint,
                                     int left, int top, int outWidth, int outHeight, uint* into)
        {
            bool same = tint != null && tint.IsNone;
            uint first = palette[0];
            fixed (uint* pixels = own.Pixels)
                for (int r = 0; r < outHeight; r++)
                {
                    uint* row = into + (long)r * outWidth;
                    int from = top + r;
                    if (from < 0 || from >= height)
                    {
                        for (int c = 0; c < outWidth; c++)
                            row[c] = first;
                        continue;
                    }
                    uint* line = pixels + (long)from * width;
                    for (int c = 0; c < outWidth; c++)
                    {
                        int at = left + c;
                        if (at < 0 || at >= width)
                            row[c] = first;
                        else
                        {
                            uint pixel = line[at];
                            uint hand = palette[pixel >> 24];
                            row[c] = same ? OwnColors.Pixel(hand, pixel)
                                     : tint != null ? OwnColors.Pixel(hand, tint.Apply(pixel)) : hand;
                        }
                    }
                }
        }

        // --- what the hooks do, apart from the hooks themselves (so the checks program can run it) --------------------

        /// <summary>What the four hooks do with what the game hands them. `make` is the game's own making of a texture
        /// (0x3D0B10), `free` its freeing of one (0x3D0C6C), `freeVariant` its freeing of a slot's variant (0x3D11DC,
        /// its third argument 1). What the game did last on a thread (the entry unpacked, the palette made, the slot's
        /// rectangle in hand) is kept by thread.</summary>
        public sealed unsafe class Logic
        {
            readonly Dictionary<int, Sheet> _sheets;
            readonly Func<nint, int> _make;
            readonly Action<nint> _free;
            readonly Action<nint, int> _freeVariant;
            readonly Action<string> _say;
            /// <summary>The texture objects whose texture on the card is a bigger one, with its size there and its
            /// handle (an object the game freed by itself, or another made where it was, has another handle or none:
            /// then it is no longer one of these).</summary>
            readonly Dictionary<nint, (int Width, int Height, int Handle)> _big = new Dictionary<nint, (int, int, int)>();
            int _saidFirst, _saidTint;

            [ThreadStatic] static int t_entry;
            [ThreadStatic] static nint t_into;
            [ThreadStatic] static int t_length;
            [ThreadStatic] static uint[]? t_palette;
            [ThreadStatic] static int t_colors;
            [ThreadStatic] static Sheet? t_slotSheet;
            [ThreadStatic] static nint t_slotPalette, t_slotInto;
            [ThreadStatic] static int t_x, t_y, t_w, t_h;

            public Logic(Dictionary<int, Sheet> sheets, Func<nint, int> make, Action<nint> free, Action<nint, int> freeVariant,
                         Action<string> say)
            {
                _sheets = sheets;
                _make = make;
                _free = free;
                _freeVariant = freeVariant;
                _say = say;
            }

            static int Int(nint at, int plus) => *(int*)(at + plus);
            static void Int(nint at, int plus, int value) => *(int*)(at + plus) = value;

            /// <summary>How many texture objects hold a bigger texture now (for the checks).</summary>
            public int BigCount
            {
                get
                {
                    lock (_big)
                        return _big.Count;
                }
            }

            bool IsBig(nint texture, out (int Width, int Height, int Handle) size)
            {
                lock (_big)
                {
                    if (!_big.TryGetValue(texture, out size))
                        return false;
                    if (size.Handle == Int(texture, TexHandle))
                        return true;
                    _big.Remove(texture);
                    return false;
                }
            }

            void Forget(nint texture)
            {
                lock (_big)
                    _big.Remove(texture);
            }

            /// <summary>The game unpacked an entry of the textures' file: which, where to, how many bytes.</summary>
            public void OnDecode(int entry, nint into, int length)
            {
                t_entry = entry;
                t_into = into;
                t_length = length;
            }

            /// <summary>The game made a palette's 32 bit colors: kept, for the texture made from them next.</summary>
            public void OnPalette(nint into, int count)
            {
                if (into == 0 || count <= 0 || count > 256)
                {
                    t_colors = 0;
                    return;
                }
                var kept = t_palette ??= new uint[256];
                new ReadOnlySpan<uint>((void*)into, count).CopyTo(kept);
                t_colors = count;
            }

            /// <summary>The battle makes a slot's variant's texture: where the slot's entry has a bigger sheet, the
            /// variant's texture is freed first (so the game makes it anew, which OnMake answers) and the rectangle is
            /// kept for it; where the variant holds a bigger texture and the entry has none, it is freed too, so the
            /// game makes one of its own size. Then the game's own routine (`original`). (2.0.4) A sheet is drawn at
            /// the bits it has: 4 (a sprite's), or 8 (a summon's own sheet, slots 15 to 17).</summary>
            public nint OnSlot(nint slot, int variant, nint palette, int x, int y, int w, int h, nint into, int stride, int bits,
                               Func<nint> original)
            {
                nint texture = slot + SlotVariants + (nint)variant * VariantBytes;
                Sheet? sheet = null;
                if ((bits == 4 || bits == 8) && stride == SheetWidth && palette != 0 && into != 0 && w > 0 && h > 0
                    && _sheets.TryGetValue(Int(slot, SlotEntry), out var found) && found.Bits == bits)
                    sheet = found;
                if ((sheet != null || IsBig(texture, out _)) && Int(texture, TexHandle) != 0)
                {
                    _freeVariant(slot, variant);
                    Forget(texture);
                }
                if (sheet == null)
                    return original();
                t_slotSheet = sheet;
                t_slotPalette = palette;
                t_slotInto = into;
                t_x = x;
                t_y = y;
                t_w = w;
                t_h = h;
                try
                {
                    return original();
                }
                finally
                {
                    t_slotSheet = null;
                }
            }

            /// <summary>The bigger sheet and the rectangle the texture now made stands for, where it stands for one: a
            /// slot's (its pixels where the slot's routine wrote them, its size the rectangle's), the menus' figure's or
            /// a whole entry's (512 by 512, its pixels where those two keep them by the entry last unpacked, the
            /// palette last made one of 16 colors).</summary>
            Sheet? Stands(nint pixels, int width, int height, out uint* palette, out int x, out int y)
            {
                palette = null;
                x = y = 0;
                if (t_slotSheet != null)
                {
                    if (pixels != t_slotInto || width != t_w || height != t_h)
                        return null;
                    palette = (uint*)t_slotPalette;
                    x = t_x;
                    y = t_y;
                    return t_slotSheet;
                }
                if (width != SheetWidth || height != SheetRows || t_into == 0 || t_colors != 16 || t_palette == null)
                    return null;
                if (pixels != t_into - MenusApart && !(t_length > 0 && pixels == t_into + t_length))
                    return null;
                // (2.0.4) The menus' figure and a whole entry are sprites' sheets of 4 bits: a summon's isn't drawn so.
                return _sheets.TryGetValue(t_entry, out var sheet) && sheet.Bits == 4 ? sheet : null;
            }

            /// <summary>The game makes a texture on the card from an object's pixels (or sends them again). Where they
            /// stand for a bigger sheet's rectangle, the game's routine is handed that rectangle's pixels at their size
            /// and the object's width and height are put back to the game's; a texture that is bigger on the card and
            /// is now given pixels of the game's size (or the other way) is freed first and made anew.</summary>
            public int OnMake(nint texture)
            {
                nint pixels = *(nint*)(texture + TexPixels);
                int width = Int(texture, TexWidth), height = Int(texture, TexHeight);
                bool again = Int(texture, TexAgain) != 0;
                bool wasBig = IsBig(texture, out var size);
                Sheet? sheet = null;
                uint* palette = null;
                int x = 0, y = 0;
                if (pixels != 0 && Int(texture, TexBits) == 0x20 && Int(texture, TexOwned) == 0 && width > 0 && height > 0)
                    sheet = Stands(pixels, width, height, out palette, out x, out y);
                if (sheet == null)
                {
                    if (wasBig)
                    {
                        // Pixels of the game's size for a texture that is bigger on the card: made anew at the game's.
                        if (again)
                            Anew(texture, pixels, width, height);
                        Forget(texture);
                    }
                    return _make(texture);
                }
                int bigWidth = width * sheet.Scale, bigHeight = height * sheet.Scale;
                uint[] rented = ArrayPool<uint>.Shared.Rent(bigWidth * bigHeight);
                try
                {
                    fixed (uint* big = rented)
                    {
                        // (2.0.2) The first time a picture of more colors is drawn through one of the game's tints, said once.
                        void Tinted(OwnColors.Tint tint)
                        {
                            if (System.Threading.Interlocked.Exchange(ref _saidTint, 1) == 0)
                                _say($"the game tinted a picture of more colors for the first time, and its own colors were "
                                     + $"kept through the tint ({sheet.Who}: {tint.Said()}).");
                        }
                        if (palette == null)
                            fixed (uint* kept = t_palette)
                                Region(sheet, kept, x, y, width, height, big, Tinted);
                        else
                            Region(sheet, palette, x, y, width, height, big, Tinted);
                        int result;
                        if (again && wasBig && size.Width == bigWidth && size.Height == bigHeight)
                        {
                            // Sent again, whole, at the size its texture has on the card.
                            *(nint*)(texture + TexPixels) = (nint)big;
                            Int(texture, TexNotedWidth, bigWidth);
                            Int(texture, TexNotedHeight, bigHeight);
                            result = _make(texture);
                            Int(texture, TexNotedWidth, width);
                            Int(texture, TexNotedHeight, height);
                            *(nint*)(texture + TexPixels) = pixels;
                            return result;
                        }
                        if (again)
                            Anew(texture, pixels, width, height);
                        *(nint*)(texture + TexPixels) = (nint)big;
                        Int(texture, TexWidth, bigWidth);
                        Int(texture, TexHeight, bigHeight);
                        result = _make(texture);
                        Int(texture, TexWidth, width);
                        Int(texture, TexHeight, height);
                        *(float*)(texture + TexWidthF) = width;
                        *(float*)(texture + TexHeightF) = height;
                        if (Int(texture, TexHandle) != 0)
                        {
                            lock (_big)
                                _big[texture] = (bigWidth, bigHeight, Int(texture, TexHandle));
                            if (System.Threading.Interlocked.Exchange(ref _saidFirst, 1) == 0)
                                _say($"the game was given {OwnColors.Kind(sheet.Scale, sheet.Own != null)} for the first "
                                     + $"time ({sheet.Who}, {bigWidth} by {bigHeight} pixels where the game's are {width} by "
                                     + $"{height}).");
                        }
                        else
                            Forget(texture);
                        return result;
                    }
                }
                finally
                {
                    ArrayPool<uint>.Shared.Return(rented);
                }
            }

            /// <summary>A texture that has one on the card freed, and its object set as the game's own noting of new
            /// pixels sets it (0x3D0A80), so the game's routine makes it anew.</summary>
            void Anew(nint texture, nint pixels, int width, int height)
            {
                _free(texture);
                *(nint*)(texture + TexPixels) = pixels;
                Int(texture, TexNotedWidth, width);
                Int(texture, TexNotedHeight, height);
                Int(texture, TexNotedBits, 0x20);
                Int(texture, TexBits, 0x20);
                Int(texture, TexWidth, width);
                Int(texture, TexHeight, height);
            }
        }
    }
}
