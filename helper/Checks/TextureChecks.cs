// Mod Studio's checks of the helper's own handling of a sprite's textures at a higher resolution (2.0.0, in the making;
// Zodi's second point of 16 November 2026), run by dev/test_big_textures.py. Part of The Ivalice Chronicles Mod Studio,
// GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --textures <request.json> <report.json>
//
// The request: "program" (his program: where the helper finds its places, BigTextures.Find); "mods", each {"id",
// "name", "folder"} (its ModStudioTextures.json and its sheets read, BigTextures.ReadMod); "jobs" ({"<mod id>/<Name>":
// [its man's upper texture's entry, its woman's], less than 0 where the game wasn't given that one's textures});
// "regions", each {"entry", "x", "y", "w", "h", "palette": 16 colors}: the rectangle as the helper makes its pixels
// (BigTextures.Region); "scenes" (true): what the helper's part of the four hooks does (BigTextures.Logic) over a
// stand-in for the game's own routines. (The twenty ninth session) The report's "effects" are the effects' bigger
// pictures planned (EffectTextures.ReadEffects and Make), its "effect places" where EffectTextures.Find finds its places
// in "program"; "effectScenes" ({"palette": 256 colors}) what the effects' hook does (EffectTextures.Logic) with a
// record of a page as the game hands it, over the first picture planned: the page's copies hold the mod's picture at
// the game's size where the game puts it, every other byte n * 7 + (n >> 8) of its copy. (The thirtieth session)
// "ownScenes" ({"with": an entry with a sheet of more colors, "same": 16 colors, "other": 16 colors}): a battle's slot and
// the menus' figure drawn from it in the palette it was given in and in another (BigTextures.Logic, OwnColors); the
// report's sheets and effects say each one's own colors and the palette it was given in. (2.0.4, the thirty fourth
// session) "summonScenes" ({"with": an entry with a summon's sheet of 8 bits, "same": 256 colors, "other": 256
// colors}): a battle's slot drawing that entry at 8 bits a pixel, 512 wide, as the game draws a summon's own sheet, in
// the palette given and in another, and at 4 bits (as no summon is drawn); "regions" take a palette of up to 256
// colors, and the report's sheets say their bits.
//
// **The stand-in is not the game.** `Card` does what the game's routines were read to do in his program (the noting of
// new pixels 0x3D0A80, the making of a texture 0x3D0B10, the freeing of one 0x3D0C6C, the freeing of a slot's variant
// 0x3D11DC and the battle's making of a slot's texture 0x3D0F8C: claude/texture-resolution-research.md), each written
// from its instructions, and says what it was asked. It holds the helper's part to that reading; whether the reading is
// the game's is for the game to show.
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using ModStudioEventSetup;

static unsafe class TextureChecks
{
    static int Int(nint at, int plus) => *(int*)(at + plus);
    static void Int(nint at, int plus, int value) => *(int*)(at + plus) = value;

    /// <summary>The game's texture routines as they were read, saying what they are asked.</summary>
    sealed class Card
    {
        public readonly List<string> Events = new List<string>();
        public string LastPixels = "";
        /// <summary>(The thirtieth session) The SHA-256 of the pixels last made or sent, their bytes as they lie.</summary>
        public string LastSha = "";
        int _next = 1;

        static string Hex(uint* pixels, int count)
        {
            var text = new StringBuilder(count * 8);
            for (int n = 0; n < count; n++)
                text.Append(pixels[n].ToString("x8"));
            return text.ToString();
        }

        /// <summary>0x3D0B10.</summary>
        public int Make(nint t)
        {
            nint pixels = *(nint*)(t + 0x18);
            if (Int(t, 0x4C) != 0)
            {
                int w = Int(t, 0x24), h = Int(t, 0x28);
                Events.Add($"sent {Int(t, 0x30)} {w}x{h}");
                LastPixels = pixels != 0 ? Hex((uint*)pixels, w * h) : "";
                LastSha = pixels != 0 ? Sha((uint*)pixels, w * h) : "";
                return 0;
            }
            Int(t, 0x40, 0);
            if (Int(t, 0x34) != 0x20)
            {
                Free(t);
                return -1;
            }
            int width = Int(t, 0x38), height = Int(t, 0x3C);
            int handle = _next++;
            Events.Add($"made {handle} {width}x{height}");
            LastPixels = pixels != 0 ? Hex((uint*)pixels, width * height) : "";
            LastSha = pixels != 0 ? Sha((uint*)pixels, width * height) : "";
            Int(t, 0x30, handle);
            *(float*)(t + 0x44) = width;
            *(float*)(t + 0x48) = height;
            if (pixels != 0)
            {
                if (Int(t, 0x20) != 0)
                {
                    Events.Add("the game freed the pixels");
                    Int(t, 0x20, 0);
                }
                *(nint*)(t + 0x18) = 0;
            }
            return 0;
        }

        /// <summary>0x3D0C6C.</summary>
        public void Free(nint t)
        {
            *(nint*)(t + 0x18) = 0;
            *(long*)(t + 0x34) = 0;
            Int(t, 0x3C, 0);
            Int(t, 0x4C, 0);
            *(long*)(t + 0x24) = 0;
            if (Int(t, 0x30) != 0)
            {
                Events.Add($"freed {Int(t, 0x30)}");
                Int(t, 0x30, 0);
            }
        }

        /// <summary>0x3D0A80.</summary>
        public void Note(nint t, nint pixels, int width, int height, int bits, int notedWidth, int notedHeight, byte kind)
        {
            if (Int(t, 0x30) != 0 && Int(t, 0x38) == width && Int(t, 0x3C) == height && Int(t, 0x34) == bits)
                Int(t, 0x4C, 1);
            else
                Free(t);
            Int(t, 0x24, notedWidth);
            Int(t, 0x28, notedHeight);
            *(byte*)(t + 0x50) = kind;
            Int(t, 0x38, width);
            Int(t, 0x3C, height);
            Int(t, 0x34, bits);
            Int(t, 0x2C, bits);
            *(nint*)(t + 0x18) = pixels;
        }

        /// <summary>0x3D11DC, its third argument 1.</summary>
        public void FreeVariant(nint slot, int variant)
        {
            nint t = slot + 0xA90 + (nint)variant * 0x90;
            Int(t, 0x70, -1);
            Int(t, 0x74, 0);
            Int(t, 0x84, 0);
            Int(t, 0x78, 0);
            Events.Add($"variant {variant} freed");
            Free(t);
            Int(slot, 0x5290, Int(slot, 0x5290) - 1);
        }

        /// <summary>0x3D0F8C at 4 bits a pixel: the rectangle of the slot's unpacked entry through the palette into
        /// `into`, then the variant's texture made, made anew or sent again; (2.0.4) at 8 bits, a byte a pixel
        /// (0x3D1035, 0x3D103B: palette[entry[(y + r) * stride + x + c]]).</summary>
        public nint Slot(Func<nint, int> make, nint slot, int variant, uint* palette, int hash, int x, int y, int w, int h,
                         nint into, int stride, int bits = 4)
        {
            byte* entry = *(byte**)(slot + 0xA88);
            uint* to = (uint*)into;
            for (int r = 0; r < h; r++)
                for (int c = 0; c < w; c++)
                {
                    int at = x + c;
                    if (bits == 8)
                    {
                        *to++ = palette[entry[(y + r) * stride + at]];
                        continue;
                    }
                    int b = entry[(y + r) * (stride / 2) + (at >> 1)];
                    *to++ = palette[(at & 1) == 0 ? b & 0xF : b >> 4];
                }
            nint t = slot + 0xA90 + (nint)variant * 0x90;
            if (Int(t, 0x30) == 0)
            {
                Note(t, into, w, h, 0x20, w, h, 4);
                make(t);
                Int(slot, 0x5290, Int(slot, 0x5290) + 1);
            }
            else if (Int(t, 0x38) == w && Int(t, 0x3C) == h)
                Events.Add($"sent part of {Int(t, 0x30)} {w}x{h}");
            else
            {
                Note(t, into, w, h, 0x20, w, h, 4);
                make(t);
            }
            Int(t, 0x70, hash);
            Int(t, 0x74, 1);
            Int(t, 0x78, 0x3C);
            Int(t, 0x7C, x);
            Int(t, 0x80, y);
            Int(t, 0x84, w);
            Int(t, 0x88, h);
            return Int(t, 0x30);
        }
    }

    static nint Zeroed(int bytes)
    {
        nint at = Marshal.AllocHGlobal(bytes);
        new Span<byte>((void*)at, bytes).Clear();
        return at;
    }

    static Dictionary<string, object?> Object(nint t) => new Dictionary<string, object?>
    {
        ["width"] = Int(t, 0x38), ["height"] = Int(t, 0x3C), ["widthF"] = *(float*)(t + 0x44), ["heightF"] = *(float*)(t + 0x48),
        ["notedWidth"] = Int(t, 0x24), ["notedHeight"] = Int(t, 0x28), ["handle"] = Int(t, 0x30), ["again"] = Int(t, 0x4C),
    };

    /// <summary>The scenes: `with` an entry that has a bigger sheet, `without` one that has none.</summary>
    static Dictionary<string, object?> Scenes(BigTextures.Plan plan, int with, int without)
    {
        var scenes = new Dictionary<string, object?>();
        var said = new List<string>();
        var card = new Card();
        var logic = new BigTextures.Logic(plan.Sheets, t => card.Make(t), t => card.Free(t),
                                          (slot, variant) => card.FreeVariant(slot, variant), said.Add);
        uint* palette = (uint*)Zeroed(16 * 4);
        for (int n = 0; n < 16; n++)
            palette[n] = n == 0 ? 0u : 0xFF000000u | (uint)(n * 0x101010);
        List<string> Taken()
        {
            var events = new List<string>(card.Events);
            card.Events.Clear();
            return events;
        }

        // The menus' figure: its entry unpacked 0x100000 bytes past its pixels.
        {
            nint block = Zeroed(0x200000);
            nint figure = Zeroed(0x70);
            logic.OnDecode(with, block + BigTextures.MenusApart, 0x20000);
            logic.OnPalette((nint)palette, 16);
            card.Note(figure, block, 512, 512, 0x20, 512, 512, 1);
            logic.OnMake(figure);
            var scene = new Dictionary<string, object?> { ["with"] = Taken(), ["object"] = Object(figure) };
            nint plain = Zeroed(0x70);
            logic.OnDecode(without, block + BigTextures.MenusApart, 0x20000);
            logic.OnPalette((nint)palette, 16);
            card.Note(plain, block, 512, 512, 0x20, 512, 512, 1);
            logic.OnMake(plain);
            scene["without"] = Taken();
            // A palette of 256 colors made last is no sprite's: the game's own size.
            nint other = Zeroed(0x70);
            logic.OnDecode(with, block + BigTextures.MenusApart, 0x20000);
            logic.OnPalette((nint)Zeroed(256 * 4), 256);
            card.Note(other, block, 512, 512, 0x20, 512, 512, 1);
            logic.OnMake(other);
            scene["other palette"] = Taken();
            // Pixels the game owns are left to the game.
            nint owned = Zeroed(0x70);
            logic.OnDecode(with, block + BigTextures.MenusApart, 0x20000);
            logic.OnPalette((nint)palette, 16);
            card.Note(owned, block, 512, 512, 0x20, 512, 512, 1);
            Int(owned, 0x20, 1);
            logic.OnMake(owned);
            scene["owned"] = Taken();
            scenes["menus"] = scene;
        }

        // A whole entry in the battle: its pixels right after its unpacked bytes, the object kept from one to the next.
        {
            nint scratch = Zeroed(0x200000);
            nint kind = Zeroed(0x70);
            var scene = new Dictionary<string, object?>();
            void Draw(int entry, string name)
            {
                logic.OnDecode(entry, scratch, 0x20000);
                logic.OnPalette((nint)palette, 16);
                card.Note(kind, scratch + 0x20000, 512, 512, 0x20, 512, 512, 4);
                logic.OnMake(kind);
                scene[name] = Taken();
                scene[name + " object"] = Object(kind);
            }
            Draw(with, "first");
            Draw(with, "again");
            Draw(without, "then without");
            Draw(without, "without again");
            Draw(with, "then with");
            // The game frees the texture and makes one of its own size by a way the hooks don't see: the object is
            // no longer one that holds a bigger texture, whatever the framework noted of it before.
            card.Free(kind);
            card.Note(kind, scratch + 0x20000, 512, 512, 0x20, 512, 512, 4);
            card.Make(kind);
            Taken();
            Draw(with, "after another way");
            scenes["whole"] = scene;
        }

        // The battle's slot.
        {
            nint slot = Zeroed(0x5298);
            nint entry = Zeroed(0x80000);
            for (int n = 0; n < 0x20000; n++)
                *(byte*)(entry + n) = (byte)(n * 7 + (n >> 8));
            *(nint*)(slot + 0xA88) = entry;
            nint into = Zeroed(512 * 512 * 4);
            var scene = new Dictionary<string, object?>();
            void Draw(int held, int variant, int x, int y, int w, int h, int bits, string name)
            {
                Int(slot, 0xA84, held);
                logic.OnSlot(slot, variant, (nint)palette, x, y, w, h, into, 512, bits,
                             () => card.Slot(t => logic.OnMake(t), slot, variant, palette, 77, x, y, w, h, into, 512));
                scene[name] = Taken();
                scene[name + " pixels"] = card.LastPixels;
                scene[name + " object"] = Object(slot + 0xA90 + (nint)variant * 0x90);
                scene[name + " count"] = Int(slot, 0x5290);
            }
            Draw(with, 3, 6, 2, 6, 4, 4, "first");
            Draw(with, 3, 10, 8, 6, 4, 4, "same size");
            Draw(with, 3, 0, 0, 8, 2, 4, "other size");
            Draw(without, 3, 0, 0, 8, 2, 4, "then without");
            Draw(without, 3, 4, 4, 8, 2, 4, "without again");
            Draw(with, 5, 0, 510, 4, 4, 4, "past the rows");
            Draw(with, 6, 2, 2, 4, 4, 8, "eight bits");
            scenes["slot"] = scene;
        }
        scenes["said"] = said;
        scenes["big"] = logic.BigCount;
        return scenes;
    }

    /// <summary>(The thirtieth session) A sheet of more colors drawn in the palette it was given in (`same`) and in
    /// another (`other`): a battle's slot (a rectangle of 6 by 4 at (6, 2), its pixels) and the menus' figure (512 by 512
    /// from its entry, the SHA-256 of its pixels), each made a texture by the game's routine as the stand-in has it.</summary>
    static Dictionary<string, object?> OwnScenes(BigTextures.Plan plan, int with, uint[] same, uint[] other)
    {
        var scenes = new Dictionary<string, object?>();
        var said = new List<string>();
        var card = new Card();
        var logic = new BigTextures.Logic(plan.Sheets, t => card.Make(t), t => card.Free(t),
                                          (slot, variant) => card.FreeVariant(slot, variant), said.Add);
        nint slot = Zeroed(0x5298);
        nint entry = Zeroed(0x80000);
        *(nint*)(slot + 0xA88) = entry;
        nint into = Zeroed(512 * 512 * 4);
        nint block = Zeroed(0x200000);
        int variant = 0;
        foreach (var (name, colors) in new[] { ("same", same), ("other", other) })
        {
            uint* palette = (uint*)Zeroed(16 * 4);
            for (int n = 0; n < 16; n++)
                palette[n] = colors[n];
            Int(slot, 0xA84, with);
            int v = variant++;
            logic.OnSlot(slot, v, (nint)palette, 6, 2, 6, 4, into, 512, 4,
                         () => card.Slot(t => logic.OnMake(t), slot, v, palette, 77 + v, 6, 2, 6, 4, into, 512));
            scenes[name + " slot"] = card.LastPixels;
            card.Events.Clear();
            nint figure = Zeroed(0x70);
            logic.OnDecode(with, block + BigTextures.MenusApart, 0x20000);
            logic.OnPalette((nint)palette, 16);
            card.Note(figure, block, 512, 512, 0x20, 512, 512, 1);
            logic.OnMake(figure);
            scenes[name + " menus"] = card.LastSha;
            scenes[name + " menus object"] = Object(figure);
            card.Events.Clear();
        }
        scenes["said"] = said;
        return scenes;
    }

    /// <summary>(2.0.4) A summon's own sheet (8 bits a pixel) drawn by the battle's slot as the game draws one: a
    /// rectangle (`rect`: x, y, w, h; 10 by 6 at (20, 30) where none is asked) at 8 bits, 512 wide, in the palette given
    /// (`same`) and in another (`other`), then once more in `same` at 4 bits (which no summon is drawn at: left to the
    /// game); each one's events, pixels and object.</summary>
    static Dictionary<string, object?> SummonScenes(BigTextures.Plan plan, int with, uint[] same, uint[] other, int[] rect)
    {
        int x = rect[0], y = rect[1], w = rect[2], h = rect[3];
        var scenes = new Dictionary<string, object?>();
        var said = new List<string>();
        var card = new Card();
        var logic = new BigTextures.Logic(plan.Sheets, t => card.Make(t), t => card.Free(t),
                                          (slot, variant) => card.FreeVariant(slot, variant), said.Add);
        nint slot = Zeroed(0x5298);
        nint entry = Zeroed(0x80000);
        for (int n = 0; n < 512 * 512; n++)
            *(byte*)(entry + n) = (byte)(n * 5 + (n >> 9));
        *(nint*)(slot + 0xA88) = entry;
        nint into = Zeroed(512 * 512 * 4);
        int variant = 0;
        foreach (var (name, colors, bits) in new[] { ("same", same, 8), ("other", other, 8), ("four bits", same, 4) })
        {
            uint* palette = (uint*)Zeroed(256 * 4);
            for (int n = 0; n < 256; n++)
                palette[n] = colors[n];
            Int(slot, 0xA84, with);
            int v = variant++;
            logic.OnSlot(slot, v, (nint)palette, x, y, w, h, into, 512, bits,
                         () => card.Slot(t => logic.OnMake(t), slot, v, palette, 77 + v, x, y, w, h, into, 512, bits));
            scenes[name] = new List<string>(card.Events);
            scenes[name + " pixels"] = card.LastPixels;
            scenes[name + " object"] = Object(slot + 0xA90 + (nint)v * 0x90);
            card.Events.Clear();
        }
        // The menus' figure of the same entry (which the game never draws so: a sprite's way, at 4 bits): left to the
        // game, at its own size.
        {
            nint block = Zeroed(0x200000);
            nint figure = Zeroed(0x70);
            uint* sixteen = (uint*)Zeroed(16 * 4);
            for (int n = 0; n < 16; n++)
                sixteen[n] = same[n];
            logic.OnDecode(with, block + BigTextures.MenusApart, 0x40000);
            logic.OnPalette((nint)sixteen, 16);
            card.Note(figure, block, 512, 512, 0x20, 512, 512, 1);
            logic.OnMake(figure);
            scenes["menus"] = new List<string>(card.Events);
            card.Events.Clear();
        }
        scenes["said"] = said;
        scenes["big"] = logic.BigCount;
        return scenes;
    }

    static string Sha(uint* pixels, int count)
    {
        var bytes = new ReadOnlySpan<byte>(pixels, count * 4);
        return Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(bytes)).ToLowerInvariant();
    }

    /// <summary>The effects' scenes: records of pages as the game hands them to 0x41E05C, over the first picture planned.
    /// The stand-in makes a page's pixels as 0x418F20 was read to (through 0x41DDB0: at 4 bits a byte's low four bits
    /// first, each through the record's palette; at 8 bits a byte through it), sends again as 0x3D0BF8 does, and notes,
    /// makes and frees as the sprites' Card.</summary>
    static Dictionary<string, object?> EffectScenes(EffectTextures.Plan plan, uint[] colors)
    {
        var scenes = new Dictionary<string, object?>();
        var picture = plan.Pictures[0];
        var card = new Card();
        var said = new List<string>();
        const int Count = 32;
        nint records = Zeroed(EffectTextures.RecordBytes * Count);
        nint objects = Zeroed(EffectTextures.ObjectBytes * Count);
        nint pages4 = Zeroed(EffectTextures.Page4Bytes * 32);
        nint pages8 = Zeroed(EffectTextures.Page8Bytes * 32);
        nint scratch = Zeroed(256 * 256 * 4);
        nint window = Zeroed(EffectTextures.Page8Bytes);
        string lastSha = "";
        // Every byte of the copies a pattern, then the picture where the game puts it (x 384 words, y 0).
        void Fill(nint copy, int pageBytes, int rowBytes, int page)
        {
            for (int n = 0; n < 256 * rowBytes; n++)
                *(byte*)(copy + 12 + (pageBytes == EffectTextures.Page8Bytes ? 4 : 0) + n) = (byte)(n * 7 + (n >> 8));
            int pageX = (page & 15) * EffectTextures.PageWords, covered = rowBytes / 2;
            int first = Math.Max(pageX, EffectTextures.PictureX), past = Math.Min(pageX + covered, EffectTextures.PictureX + picture.Words);
            for (int r = 0; r < picture.Rows && first < past; r++)
                for (int w = first; w < past; w++)
                    for (int b = 0; b < 2; b++)
                        *(byte*)(copy + 12 + (pageBytes == EffectTextures.Page8Bytes ? 4 : 0) + r * rowBytes + (w - pageX) * 2 + b)
                            = picture.Game[r * picture.Words * 2 + (w - EffectTextures.PictureX) * 2 + b];
        }
        nint Copy(int bits, int page) => bits == 4 ? pages4 + page * EffectTextures.Page4Bytes + 12
                                                   : pages8 + page * EffectTextures.Page8Bytes + 16;
        for (int page = 0; page < 32; page++)
        {
            // Pages 16 to 31 are rows 256 on: the picture's words there too, as a page that doesn't look at its rows would
            // take it for the picture.
            Fill(pages4 + page * EffectTextures.Page4Bytes, EffectTextures.Page4Bytes, 128, page);
            Fill(pages8 + page * EffectTextures.Page8Bytes, EffectTextures.Page8Bytes, 256, page);
        }
        nint Pixels(int index)
        {
            nint record = records + index * EffectTextures.RecordBytes;
            byte* from = *(byte**)(record + EffectTextures.RecPlace);
            uint* palette = (uint*)(record + EffectTextures.RecPalette);
            uint* to = (uint*)scratch;
            if (Int(record, EffectTextures.RecDepth) == EffectTextures.Depth4)
                for (int n = 0; n < 256 * 128; n++)
                {
                    *to++ = palette[from[n] & 0xF];
                    *to++ = palette[from[n] >> 4];
                }
            else
                for (int n = 0; n < 256 * 256; n++)
                    *to++ = palette[from[n]];
            return scratch;
        }
        void Send(nint t, nint pixels, int x, int y, int w, int h)
        {
            card.Events.Add($"sent {Int(t, 0x30)} {w}x{h}");
            lastSha = Sha((uint*)pixels, w * h);
        }
        int Make(nint t)
        {
            int w = Int(t, 0x38), h = Int(t, 0x3C);
            nint pixels = *(nint*)(t + 0x18);
            if (pixels != 0 && Int(t, 0x4C) == 0)
                lastSha = Sha((uint*)pixels, w * h);
            return card.Make(t);
        }
        // The pages' copies as the game hands them: page 0's bytes past its copy's header (0x25ED60: + 0xC at 4 bits, + 0x10 at 8).
        var logic = new EffectTextures.Logic(plan, records, objects, pages4 + 12, pages8 + 16, Pixels, Send,
                                             (t, pixels, w, h, bits, nw, nh, kind) => card.Note(t, pixels, w, h, bits, nw, nh, kind),
                                             Make, said.Add);
        nint Record(int index, int page, int bits, nint place)
        {
            nint record = records + index * EffectTextures.RecordBytes;
            Int(record, EffectTextures.RecMarked, 1);
            Int(record, EffectTextures.RecWidth, 256);
            Int(record, EffectTextures.RecHeight, 256);
            Int(record, EffectTextures.RecBits, 0x20);
            Int(record, EffectTextures.RecPage, page);
            *(nint*)(record + EffectTextures.RecPlace) = place;
            Int(record, EffectTextures.RecKind, EffectTextures.KindIndexed);
            Int(record, EffectTextures.RecDepth, bits == 4 ? EffectTextures.Depth4 : EffectTextures.Depth8);
            for (int n = 0; n < 256; n++)
                *(uint*)(record + EffectTextures.RecPalette + n * 4) = colors[n];
            // (The thirtieth session) The draw's count of colors, as 0x4188B4 copied it: 16 at 4 bits, 256 at 8.
            Int(record, EffectTextures.RecColors, bits == 4 ? 16 : 256);
            Int(record, EffectTextures.RecEntryRow, -1);
            Int(record, EffectTextures.RecMade, 0);
            return record;
        }
        void Play(string name, int index)
        {
            card.Events.Clear();
            lastSha = "";
            bool taken = logic.OnRecord(index);
            nint record = records + index * EffectTextures.RecordBytes;
            scenes[name] = new Dictionary<string, object?>
            {
                ["taken"] = taken, ["events"] = new List<string>(card.Events), ["sha"] = lastSha,
                ["marked"] = Int(record, EffectTextures.RecMarked), ["made"] = Int(record, EffectTextures.RecMade),
                ["object"] = Object(objects + index * EffectTextures.ObjectBytes),
                ["pixels kept"] = *(nint*)(objects + index * EffectTextures.ObjectBytes + 0x18) != 0,
            };
        }
        int bits = picture.Bits, other = bits == 4 ? 8 : 4;
        Record(1, 6, bits, Copy(bits, 6));
        Play("first", 1);
        Record(1, 6, bits, Copy(bits, 6));
        Play("again", 1);
        Record(2, 7, bits, Copy(bits, 7));
        Play("page 7", 2);
        Record(3, 5, bits, Copy(bits, 5));
        Play("page 5", 3);
        Record(4, 12, bits, Copy(bits, 12));
        Play("page 12", 4);
        // Page 22: x 384 as page 6, but its rows from 256 (the picture's rows are from 0).
        Record(10, 22, bits, Copy(bits, 22));
        Play("page 22", 10);
        Record(5, 6, other, Copy(other, 6));
        Play("other bits", 5);
        for (int n = 0; n < 256 * 256; n++)
            *(byte*)(window + n) = *(byte*)(Copy(bits, 6) + (bits == 4 ? n % (256 * 128) : n));
        Record(6, 6, bits, window);
        Play("window", 6);
        Record(7, 6, bits, Copy(bits, 6));
        Int(records + 7 * EffectTextures.RecordBytes, EffectTextures.RecMarked, 0);
        Play("unmarked", 7);
        Record(8, 6, bits, Copy(bits, 6));
        Int(records + 8 * EffectTextures.RecordBytes, EffectTextures.RecEntryRow, 0);
        Play("entry row", 8);
        // One byte of the picture other in the page's copy (its last row's last word): no longer the mod's picture.
        nint changed = Copy(bits, 6) + (picture.Rows - 1) * (bits == 4 ? 128 : 256) + (bits == 4 ? 127 : picture.Words * 2 - 1);
        byte was = *(byte*)changed;
        *(byte*)changed = (byte)(was ^ 0x5A);
        Record(9, 6, bits, Copy(bits, 6));
        Play("changed byte", 9);
        *(byte*)changed = was;
        // The game frees the first record's texture by another way: marked again, it is made anew, not sent.
        card.Free(objects + 1 * EffectTextures.ObjectBytes);
        Record(1, 6, bits, Copy(bits, 6));
        Play("freed another way", 1);
        // (The thirtieth session) A picture of more colors over a record handed fewer colors than it was given in: no
        // palette it was given in, so its numbers through the record's.
        if (picture.Own != null)
        {
            Record(11, 6, bits, Copy(bits, 6));
            Int(records + 11 * EffectTextures.RecordBytes, EffectTextures.RecColors, picture.Own.Tied.Length / 2);
            Play("few colors", 11);
        }
        scenes["said"] = said;
        scenes["made count"] = logic.Made;
        return scenes;
    }

    /// <summary>The SHA-256 of a sheet's own pixels, four bytes each as they lie (little endian).</summary>
    static string OwnSha(uint[] pixels)
    {
        fixed (uint* at = pixels)
            return Sha(at, pixels.Length);
    }

    public static int Run(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var r = request.RootElement;
        var report = new Dictionary<string, object?> { ["file"] = BigTextures.FileName };
        if (r.TryGetProperty("program", out var program) && program.GetString() is string path && path.Length > 0)
        {
            var image = Program.Load(path);
            var sites = BigTextures.Find(image, Finder.Sections(image), null);
            report["places"] = new Dictionary<string, object?>
            {
                ["Slot"] = sites.Slot, ["Make"] = sites.Make, ["Free"] = sites.Free, ["FreeVariant"] = sites.FreeVariant,
                ["Palette"] = sites.Palette, ["Decode"] = sites.Decode, ["Archive"] = sites.Archive, ["Missing"] = sites.Missing,
            };
            var effectSites = EffectTextures.Find(image, Finder.Sections(image), null);
            // Another mod's hook on the making of a page's texture (a jump over its first bytes): found by its one call,
            // its first instructions read from the program file; without the file, said as not found.
            var hooked = (byte[])image.Clone();
            if (effectSites.Record >= 0)
            {
                hooked[effectSites.Record] = 0xE9;
                for (int n = 1; n < 5; n++)
                    hooked[effectSites.Record + n] = 0;
            }
            var throughFile = EffectTextures.Find(hooked, Finder.Sections(hooked), ProgramFile.Of(path, hooked));
            var withoutFile = EffectTextures.Find(hooked, Finder.Sections(hooked), null);
            report["effect places hooked"] = new Dictionary<string, object?>
            {
                ["Record"] = throughFile.Record, ["Missing"] = throughFile.Missing,
                ["Without the file"] = withoutFile.Missing,
            };
            report["effect places"] = new Dictionary<string, object?>
            {
                ["Record"] = effectSites.Record, ["Pixels"] = effectSites.Pixels, ["Send"] = effectSites.Send,
                ["Note"] = effectSites.Note, ["Make"] = effectSites.Make, ["Records"] = effectSites.Records,
                ["Objects"] = effectSites.Objects, ["Scratch"] = effectSites.Scratch, ["ScratchAt"] = effectSites.ScratchAt,
                ["Pages4"] = effectSites.Pages4, ["Pages8"] = effectSites.Pages8, ["Missing"] = effectSites.Missing,
            };
        }
        var problems = new List<string>();
        var mods = new List<BigTextures.ModTextures>();
        if (r.TryGetProperty("mods", out var asked))
            foreach (var mod in asked.EnumerateArray())
            {
                var read = BigTextures.ReadMod(mod.GetProperty("id").GetString()!, mod.GetProperty("name").GetString()!,
                                               mod.GetProperty("folder").GetString()!, problems);
                if (read != null)
                    mods.Add(read);
            }
        var jobs = new Dictionary<string, int[]>();
        if (r.TryGetProperty("jobs", out var given))
            foreach (var job in given.EnumerateObject())
                jobs[job.Name] = new[] { job.Value[0].GetInt32(), job.Value[1].GetInt32() };
        var plan = BigTextures.Make(mods, (modId, name, woman)
            => jobs.TryGetValue($"{modId}/{name}", out var entries) ? entries[woman ? 1 : 0] : -1);
        report["problems"] = problems;
        report["said"] = plan.Said;
        report["line"] = plan.Any ? BigTextures.Line(plan) : null;
        var sheets = new Dictionary<string, object?>();
        foreach (var (entry, sheet) in plan.Sheets)
            sheets[entry.ToString()] = new Dictionary<string, object?>
            {
                ["Scale"] = sheet.Scale, ["Rows"] = sheet.Rows, ["Who"] = sheet.Who, ["Bytes"] = sheet.Pixels.Length,
                ["Bits"] = sheet.Bits,
                // (The thirtieth session) A sheet of more colors: the SHA-256 of its pixels as read, and its palette.
                ["Own"] = sheet.Own == null ? null : OwnSha(sheet.Own.Pixels),
                ["Tied"] = sheet.Own == null ? null : new List<int>(Array.ConvertAll(sheet.Own.Tied, w => (int)w)),
            };
        report["sheets"] = sheets;
        var regions = new List<object?>();
        if (r.TryGetProperty("regions", out var wanted))
            foreach (var region in wanted.EnumerateArray())
            {
                int entry = region.GetProperty("entry").GetInt32();
                if (!plan.Sheets.TryGetValue(entry, out var sheet))
                {
                    regions.Add(null);
                    continue;
                }
                int x = region.GetProperty("x").GetInt32(), y = region.GetProperty("y").GetInt32();
                int w = region.GetProperty("w").GetInt32(), h = region.GetProperty("h").GetInt32();
                var palette = new uint[256];
                int n = 0;
                foreach (var color in region.GetProperty("palette").EnumerateArray())
                    if (n < palette.Length)
                        palette[n++] = color.GetUInt32();
                var pixels = new uint[w * sheet.Scale * h * sheet.Scale];
                fixed (uint* colors = palette)
                fixed (uint* into = pixels)
                    BigTextures.Region(sheet, colors, x, y, w, h, into);
                var text = new StringBuilder(pixels.Length * 8);
                foreach (uint pixel in pixels)
                    text.Append(pixel.ToString("x8"));
                regions.Add(new Dictionary<string, object?>
                {
                    ["width"] = w * sheet.Scale, ["height"] = h * sheet.Scale, ["pixels"] = text.ToString(),
                });
            }
        report["regions"] = regions;
        var effects = EffectTextures.Make(mods.ConvertAll(mod => mod.Effects));
        report["effects said"] = effects.Said;
        report["effects line"] = effects.Any ? EffectTextures.Line(effects) : null;
        var planned = new List<object?>();
        foreach (var picture in effects.Pictures)
            planned.Add(new Dictionary<string, object?>
            {
                ["Effect"] = picture.Effect, ["Bits"] = picture.Bits, ["Scale"] = picture.Scale, ["Words"] = picture.Words,
                ["Rows"] = picture.Rows, ["Width"] = picture.Width, ["Height"] = picture.Height, ["Who"] = picture.Who,
                ["Game"] = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(picture.Game)).ToLowerInvariant(),
                ["Big"] = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(picture.Big)).ToLowerInvariant(),
                ["Own"] = picture.Own == null ? null : OwnSha(picture.Own.Pixels),
                ["Tied"] = picture.Own == null ? null : new List<int>(Array.ConvertAll(picture.Own.Tied, w => (int)w)),
            });
        report["effects"] = planned;
        if (r.TryGetProperty("effectScenes", out var effectScenes) && effectScenes.ValueKind == JsonValueKind.Object
            && effects.Any)
        {
            var colors = new uint[256];
            int k = 0;
            foreach (var color in effectScenes.GetProperty("palette").EnumerateArray())
                colors[k++] = color.GetUInt32();
            report["effect scenes"] = EffectScenes(effects, colors);
        }
        if (r.TryGetProperty("scenes", out var scenes) && scenes.ValueKind == JsonValueKind.Object)
            report["scenes"] = Scenes(plan, scenes.GetProperty("with").GetInt32(), scenes.GetProperty("without").GetInt32());
        if (r.TryGetProperty("ownScenes", out var ownScenes) && ownScenes.ValueKind == JsonValueKind.Object)
        {
            uint[] Colors(string name)
            {
                var colors = new uint[16];
                int n = 0;
                foreach (var color in ownScenes.GetProperty(name).EnumerateArray())
                    colors[n++] = color.GetUInt32();
                return colors;
            }
            report["own scenes"] = OwnScenes(plan, ownScenes.GetProperty("with").GetInt32(), Colors("same"), Colors("other"));
        }
        if (r.TryGetProperty("summonScenes", out var summonScenes) && summonScenes.ValueKind == JsonValueKind.Object)
        {
            uint[] Colors(string name)
            {
                var colors = new uint[256];
                int n = 0;
                foreach (var color in summonScenes.GetProperty(name).EnumerateArray())
                    if (n < colors.Length)
                        colors[n++] = color.GetUInt32();
                return colors;
            }
            var rect = new[] { 20, 30, 10, 6 };
            if (summonScenes.TryGetProperty("rect", out var asked4) && asked4.GetArrayLength() == 4)
                for (int n = 0; n < 4; n++)
                    rect[n] = asked4[n].GetInt32();
            report["summon scenes"] = SummonScenes(plan, summonScenes.GetProperty("with").GetInt32(), Colors("same"),
                                                   Colors("other"), rect);
        }
        // (2.0.2) The game's tints: for a palette given and palettes in hand, the tint OwnColors.Tint.Find finds of each
        // (none where it is the palette given, null where no tint gives it), and given own colors through each found.
        if (r.TryGetProperty("tints", out var tints) && tints.ValueKind == JsonValueKind.Object)
        {
            var tied = new List<ushort>();
            foreach (var word in tints.GetProperty("tied").EnumerateArray())
                tied.Add((ushort)word.GetInt32());
            var owns = new List<uint>();
            if (tints.TryGetProperty("own", out var ownColors))
                foreach (var color in ownColors.EnumerateArray())
                    owns.Add(color.GetUInt32());
            var found = new List<object?>();
            var watch = System.Diagnostics.Stopwatch.StartNew();
            long slowest = 0;
            var times = new List<double>();
            // The search once before the clock is read, so the times are the search's and not the code's first making.
            fixed (uint* warm = new uint[16])
                OwnColors.Tint.Find(warm, 16, tied.ToArray());
            foreach (var hand in tints.GetProperty("hands").EnumerateArray())
            {
                var colors = new uint[16];
                int n = 0;
                foreach (var color in hand.EnumerateArray())
                    colors[n++] = color.GetUInt32();
                long before = watch.ElapsedTicks;
                OwnColors.Tint? tint;
                fixed (uint* at = colors)
                    tint = OwnColors.Tint.Find(at, 16, tied.ToArray());
                slowest = Math.Max(slowest, watch.ElapsedTicks - before);
                times.Add((watch.ElapsedTicks - before) * 1000.0 / System.Diagnostics.Stopwatch.Frequency);
                if (tint == null)
                {
                    found.Add(null);
                    continue;
                }
                var applied = new List<uint>();
                foreach (uint own in owns)
                    applied.Add(tint.Apply(own) & 0xFFFFFF);
                found.Add(new Dictionary<string, object?>
                {
                    ["none"] = tint.IsNone, ["way"] = tint.Way, ["offsets"] = tint.Offsets, ["blend"] = tint.Blend,
                    ["steps"] = tint.Steps, ["of"] = tint.Of, ["toward"] = tint.Toward, ["said"] = tint.Said(),
                    ["applied"] = applied,
                });
            }
            report["tints"] = found;
            report["tints slowest ms"] = slowest * 1000.0 / System.Diagnostics.Stopwatch.Frequency;
            report["tints ms"] = times;
            // The game's own changes and blends the search tries first, as the framework has them.
            report["tints known"] = new Dictionary<string, object?>
            {
                ["changes"] = Array.ConvertAll(OwnColors.Tint.KnownChanges, k => new[] { k.Way, k.R, k.G, k.B }),
                ["blends"] = Array.ConvertAll(OwnColors.Tint.KnownBlends, k => new[] { k.R, k.G, k.B }),
                ["changeParts"] = OwnColors.Tint.KnownChangeParts, ["blendParts"] = OwnColors.Tint.KnownBlendParts,
                ["mostTried"] = OwnColors.Tint.MostTried,
            };
        }
        File.WriteAllText(args[2], JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
        return 0;
    }
}
