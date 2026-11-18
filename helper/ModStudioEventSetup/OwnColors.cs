// Mod Studio Framework: (2.0.0, in the making) pictures of more colors than a sheet's, tied to one palette. Part of The
// Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi's second point of 16 November 2026: "replace the effect sprites (this can apply to all sprites as well) files
// with those of higher resolution and deeper color depths. For instance using PPSSPP texture packs". His choices of 17
// November: a picture of more colors is **tied to one palette**, PPSSPP's way (the close's recommended answer, taken by
// "Continue with your recommendations"): shown where the game draws the sprite or effect in the palette it was given
// in, and in every other palette its version in the sheet's colors, so a team's colors and a status's still work; and,
// once the measure below was put to him with its cost, "Up to 4 times (Recommended)" and "Keep its colors
// (Recommended)".
//
// What was measured in his program (12,158,720 bytes; dev/research/sidequests/deep_colors.py holds each instruction this
// rests on by its bytes and runs both of the game's rules over every 15 bit color; claude/texture-resolution-
// research.md, "Measured in the thirtieth session", says what each means):
//
// - Where the framework makes a sprite's pixels (BigTextures.Logic) the palette in hand is 16 colors the game made by
//   0x41DC34 (each part's five bits shifted up three, the top byte 0xFF, the first color 0 where cleared), from the
//   emulated video memory's color table in the battle (0x416786, 0x416A31) and from the sprite's own colors in the
//   menus (0xCE796), each first changed by the unit's status there (0xCE5D9 to 0xCE765). Where it makes an effect's
//   page's pixels (EffectTextures.Logic) the palette in hand is the record's 16 or 256 colors (+ 0x40, their count at
//   + 0x440), which 0x25EB10 made of the same memory's color table through a table of its own (each part over 31 times
//   255, cut to a whole number; a word of 0 never drawn, 0).
// - So a palette is known there by its colors: under both rules each part's five bits come back as the 32 bit color's
//   part shifted down three, and a color the game made never drawn is 0. A team's colors are another palette; a
//   status's, a flash in an effect's play and an effect's colors as they change are colors changed before they are
//   made: none of them is the palette a picture was given in.
//
// What the framework does with it: a sheet of more colors (the bigger sheet's file, "MSBT", version 2: each pixel its
// color number and its own color, and the palette it was given in; `Read`) is drawn where the game makes its texture as
// before, but where the palette in hand is that palette (`Same`) each pixel is its own color, kept as see through or
// blended as the game made its number's color (`Pixel`); in any other palette the sheet's color numbers go through
// the palette in hand, as a sheet of 16 or 256 colors always does. Nothing is hooked here: BigTextures.Region and
// EffectTextures.Bigger call it.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;

namespace ModStudioEventSetup
{
    public static class OwnColors
    {
        /// <summary>The bigger sheet's file's version for a sheet of more colors, and its bits a pixel.</summary>
        public const int Version = 2, Bits = 32;
        /// <summary>How many times the game's size a picture of more colors may be (his choice of 17 November: "Up to
        /// 4 times"; at the game's size too).</summary>
        public const int MinScale = 1, MaxScale = 4;
        /// <summary>After the 16 bytes every bigger sheet's file starts with: the color numbers' bits (a byte), 0 (a
        /// byte), how many colors the palette it was given in has (two bytes), then those colors' 15 bit words.</summary>
        public const int Head = 4;

        /// <summary>A sheet's own colors: each pixel its color number in the top byte and its own red, green and blue
        /// below (red lowest, as the game keeps a 32 bit color); `Tied` the palette it was given in, as 15 bit words.</summary>
        public sealed class Own
        {
            public uint[] Pixels { get; }
            public ushort[] Tied { get; }
            public int NumberBits { get; }
            /// <summary>(2.0.2) The tints found of the palettes this sheet met, by their colors (`TintOf`).</summary>
            public Dictionary<string, Tint?> Tints { get; } = new Dictionary<string, Tint?>();
            public Own(uint[] pixels, ushort[] tied, int numberBits)
            {
                Pixels = pixels;
                Tied = tied;
                NumberBits = numberBits;
            }
        }

        /// <summary>A sheet of more colors' body (its file past the 16 bytes all bigger sheets start with), for a sheet
        /// `width` by `height` whose color numbers have `bits` bits (4 or 8); null and why in `problems` where it isn't
        /// one. Its rows are compressed (zlib): `width * height` pixels of four bytes, nothing after them.</summary>
        public static Own? Read(byte[] bytes, int width, int height, int bits, string what, List<string> problems)
        {
            const int start = BigTextures.HeaderBytes;
            if (bytes.Length < start + Head)
            {
                problems.Add($"{what} isn't a sheet of more colors as Mod Studio writes one");
                return null;
            }
            int numberBits = bytes[start], count = BinaryPrimitives.ReadUInt16LittleEndian(bytes.AsSpan(start + 2, 2));
            if (numberBits != bits || bytes[start + 1] != 0)
            {
                problems.Add($"{what} has color numbers of {numberBits} bits, and its sheet's have {bits}");
                return null;
            }
            if (count != 1 << bits || bytes.Length < start + Head + 2 * count)
            {
                problems.Add($"{what}'s palette has {count} colors, and a sheet of {bits} bit color numbers is given in "
                             + $"one of {1 << bits}");
                return null;
            }
            var tied = new ushort[count];
            for (int n = 0; n < count; n++)
                tied[n] = BinaryPrimitives.ReadUInt16LittleEndian(bytes.AsSpan(start + Head + 2 * n, 2));
            long pixelCount = (long)width * height;
            if (pixelCount <= 0 || pixelCount > int.MaxValue / 4)
            {
                problems.Add($"{what} is {width} by {height} pixels, which a sheet of more colors can't be");
                return null;
            }
            var pixels = new uint[pixelCount];
            int body = start + Head + 2 * count;
            try
            {
                using var packed = new MemoryStream(bytes, body, bytes.Length - body, false);
                using var rows = new ZLibStream(packed, CompressionMode.Decompress);
                var into = System.Runtime.InteropServices.MemoryMarshal.AsBytes(pixels.AsSpan());
                int got = 0;
                while (got < into.Length)
                {
                    int read = rows.Read(into.Slice(got));
                    if (read == 0)
                        break;
                    got += read;
                }
                Span<byte> more = stackalloc byte[1];
                if (got != into.Length || rows.Read(more) != 0)
                {
                    problems.Add($"{what}'s rows aren't {width} by {height} pixels of four bytes");
                    return null;
                }
            }
            catch (Exception e) when (e is InvalidDataException || e is IOException)
            {
                problems.Add($"{what}'s rows can't be read ({e.Message})");
                return null;
            }
            if (!BitConverter.IsLittleEndian)
                for (int n = 0; n < pixels.Length; n++)
                    pixels[n] = BinaryPrimitives.ReverseEndianness(pixels[n]);
            uint most = (1u << bits) - 1;
            foreach (uint pixel in pixels)
                if (pixel >> 24 > most)
                {
                    problems.Add($"{what} has a color number past {most}");
                    return null;
                }
            return new Own(pixels, tied, bits);
        }

        /// <summary>Whether the palette in hand (`count` 32 bit colors) is the one a picture was given in: each of its
        /// colors has the same five bits a part as the given palette's word (the 32 bit color's part shifted down
        /// three, under both of the game's rules), or is 0 (a color the game made never drawn).</summary>
        public static unsafe bool Same(uint* hand, int count, ushort[] tied)
        {
            if (hand == null || count < tied.Length)
                return false;
            for (int n = 0; n < tied.Length; n++)
            {
                uint color = hand[n];
                if (color == 0)
                    continue;
                int word = tied[n];
                if (((color >> 3) & 0x1F) != (word & 0x1F) || ((color >> 11) & 0x1F) != ((word >> 5) & 0x1F)
                    || ((color >> 19) & 0x1F) != ((word >> 10) & 0x1F))
                    return false;
            }
            return true;
        }

        /// <summary>A pixel of more colors where the palette in hand is the one it was given in: its own red, green and
        /// blue, see through or blended as the game made its number's color (`hand`, that color: never drawn stays
        /// never drawn).</summary>
        public static uint Pixel(uint hand, uint own) => (hand >> 24) == 0 ? hand : (hand & 0xFF000000u) | (own & 0x00FFFFFFu);

        /// <summary>What a picture is, for the framework's lines: bigger, of more colors, or both.</summary>
        public static string Kind(int scale, bool own)
            => own ? (scale > 1 ? "a bigger picture of more colors" : "a picture of more colors") : "a bigger picture";

        // --- (2.0.2, the thirty second session) the game's tints of a palette ------------------------------------------
        //
        // Zodi's answer of 17 November, 14:59 (his test 127: the selected Squire man's colors changed while the game's
        // selection highlight faded in and out): "The full colors should stay through the highlight with what ever
        // appropriate tints applied to them"; and of 16:42, to the question put to him with a recommendation: a status's
        // tints keep them too, one rule for both.
        //
        // Measured in his program (dev/research/sidequests/tints.py holds each instruction by its bytes, runs the units'
        // and the menus' changes in a machine against its own working out, and finds the two step tables the rule's;
        // claude/texture-resolution-research.md, "Measured in the thirty second session", says what each means): every
        // tint the game gives a unit's palette is one of two kinds, or the second on the first.
        //
        // - **A change** (0x2F7628 in the battle: a status's tint, 0x269330, and the map's darkness, 0x269074; and the
        //   menus' figure's loop, 0xCE5E2 to 0xCE765, for a status there): each color's five bit parts as they are,
        //   halved, made grey from (2 red + 3 green + blue) / 6, or that grey halved, then each part plus its offset,
        //   kept to 0 and 31; a color made black that wasn't given blue 1; a word of 0 left as it is.
        // - **A blend** (0x2F4944 and each frame's step in 0x2F5F78: the selection highlights, 0x1EABF8 and 0x1EAC44, a
        //   flash, a fade): each part moves from its color toward that color plus three offsets (kept to 0 and 31; a black
        //   target given blue 1), or back from there, by the step table's change for its own distance, one step of 32 or of
        //   8 at a time; a black color left alone; a color blended to black given blue 1. Its "color" is the palette as the
        //   change last left it.
        //
        // So where the palette in hand isn't the one a picture was given in, `Find` looks for such a tint that gives every
        // color in hand from the given one (the simplest first; tints.py's `tint_found` is the same search, and the checks
        // hold the two together), and `Apply` puts each own color through it as the palette's colors go (tints.py's
        // `through`): a pixel of a palette's color comes out exactly as the game made that color. Where none gives them all
        // (a team's palette, an effect's flash of another kind), the sheet's numbers go through the palette in hand, as
        // before.

        /// <summary>A tint of a palette as the game gives one: a change (`Way`: 0 the parts as they are, 1 halved, 2 grey,
        /// 3 grey halved; `Offsets` red, green, blue) then, where `Of` isn't 0, a blend (`Blend` offsets, `Steps` of
        /// `Of` steps taken, `Toward` the offsets or back from them). `None` is no tint: the palette given.</summary>
        public sealed class Tint
        {
            public int Way { get; }
            public int[] Offsets { get; }
            public int[] Blend { get; }
            public int Steps { get; }
            public int Of { get; }
            public bool Toward { get; }
            public static readonly Tint None = new Tint(0, new int[3], new int[3], 0, 0, true);
            public bool IsNone => ReferenceEquals(this, None);

            public Tint(int way, int[] offsets, int[] blend, int steps, int of, bool toward)
            {
                Way = way;
                Offsets = offsets;
                Blend = blend;
                Steps = steps;
                Of = of;
                Toward = toward;
            }

            /// <summary>What the tint is, for the framework's line: a change, a blend, or a blend on a change.</summary>
            public string Said()
            {
                string Parts(int[] o) => $"red {o[0]}, green {o[1]} and blue {o[2]}";
                string[] ways = { "its parts as they are", "halved", "made grey", "made grey and halved" };
                bool change = Way != 0 || Offsets[0] != 0 || Offsets[1] != 0 || Offsets[2] != 0;
                string blend = $"a blend {(Toward ? "toward" : "back from")} {Parts(Blend)}, step {Steps} of {Of}";
                string changed = $"a change ({ways[Way]}, {Parts(Offsets)})";
                return Of == 0 ? changed : change ? $"{blend} on {changed}" : blend;
            }

            // --- the game's arithmetic of one color (tints.py: changed, blended, pos) ---

            /// <summary>How far a part moving by `d` has moved after `s` of `n` steps (the step tables' rule).</summary>
            public static int Pos(int d, int s, int n)
            {
                if (s <= 0)
                    return 0;
                if (s >= n)
                    return d;
                int p = d * s, q = p / n;              // C#'s division cuts toward zero, as the PlayStation's did
                return p < 0 ? q - 1 : q;
            }

            static void WayOf(int r, int g, int b, int way, Span<int> into)
            {
                if (way == 1)
                {
                    into[0] = r >> 1;
                    into[1] = g >> 1;
                    into[2] = b >> 1;
                }
                else if (way == 2 || way == 3)
                {
                    int grey = (2 * r + 3 * g + b) / (way == 2 ? 6 : 12);
                    into[0] = into[1] = into[2] = grey;
                }
                else
                {
                    into[0] = r;
                    into[1] = g;
                    into[2] = b;
                }
            }

            static int Clamp(int v, int low, int high) => v < low ? low : v > high ? high : v;

            /// <summary>A 16 bit color through the change.</summary>
            public static int Changed(int word, int way, int[] offsets)
            {
                if (word == 0)
                    return 0;
                Span<int> p = stackalloc int[3];
                WayOf(word & 0x1F, (word >> 5) & 0x1F, (word >> 10) & 0x1F, way, p);
                int r = Clamp(p[0] + offsets[0], 0, 31), g = Clamp(p[1] + offsets[1], 0, 31), b = Clamp(p[2] + offsets[2], 0, 31);
                if ((r | g | b) == 0 && (word & 0x7FFF) != 0)
                    b = 1;
                return (word & 0x8000) | (b << 10) | (g << 5) | r;
            }

            /// <summary>A 16 bit color of a palette whose blend is on, `s` of `n` steps along.</summary>
            public static int Blended(int word, int[] offsets, int s, int n, bool toward)
            {
                if (word == 0)
                    return 0;
                int xr = word & 0x1F, xg = (word >> 5) & 0x1F, xb = (word >> 10) & 0x1F;
                if (xr + xg + xb == 0)
                    return word;
                int tr = Clamp(xr + offsets[0], 0, 31), tg = Clamp(xg + offsets[1], 0, 31), tb = Clamp(xb + offsets[2], 0, 31);
                if ((tr | tg | tb) == 0)
                    tb = 1;
                int Step(int x, int target)
                {
                    int a = toward ? x : target, e = toward ? target : x;
                    return a + Pos(e - a, s, n);
                }
                int r = Step(xr, tr), g = Step(xg, tg), b = Step(xb, tb);
                if ((r | g | b) == 0)
                    b = 1;
                return (word & 0x8000) | (b << 10) | (g << 5) | r;
            }

            /// <summary>A palette's 16 bit color through this tint, as the game makes it.</summary>
            public int Word(int word)
            {
                int changed = Changed(word, Way, Offsets);
                return Of == 0 ? changed : Blended(changed, Blend, Steps, Of, Toward);
            }

            // --- the search (tints.py: tint_found) ---

            /// <summary>The order offsets are tried in: nearest 0 first, the rising one before the falling.</summary>
            static readonly int[] Order = BuildOrder();
            /// <summary>The blends tried: 32 steps before 8, toward before back, the steps in order (toward's last step the
            /// offsets reached; back's last is the palette itself).</summary>
            static readonly (int N, bool Toward, int S)[] Blends = BuildBlends();
            /// <summary>A unit faded to black: every color toward black, its target blue 1.</summary>
            static readonly int[] ToBlack = { -31, -31, -31 };
            /// <summary>How many whole tints one way of the search holds to every color at most.</summary>
            public const int MostTried = 4096;
            /// <summary>The game's own changes (its statuses' tints in the battle, 0x269330, as the framework's ways, and
            /// its darkness, 0x269074) and blends (its highlights, 0x1EABF8, 0x1EAC44 and 0x1EABB0, a flash and a fade):
            /// where a part's offset isn't pinned by the palette one of these is tried first, and where a change and a
            /// blend alone both give the palette the game's own of the two is taken (the change where both or neither
            /// are). tints.py's KNOWN_CHANGES and KNOWN_BLENDS; the checks hold the two together.</summary>
            public static readonly (int Way, int R, int G, int B)[] KnownChanges =
            {
                (2, 0, 0, 0), (2, 3, -1, 8), (0, 8, 0, 0), (1, 0, 8, 0), (0, 0, 0, 8), (1, -4, -4, -4), (1, -8, -8, -8),
                (1, 4, 0, 5), (0, -4, -4, -4), (0, -8, -8, -8), (0, -12, -12, -12), (0, -4, -5, -2), (0, -8, -9, -6),
                (0, -12, -14, -8),
            };
            public static readonly (int R, int G, int B)[] KnownBlends =
                { (0, 0, 24), (16, 0, 0), (16, 8, 0), (31, 31, 31), (-31, -31, -31) };
            /// <summary>For each part, the offsets the game's own changes and blends give it, in the order tried (each
            /// once; tints.py's KNOWN_CHANGE_PARTS and KNOWN_BLEND_PARTS).</summary>
            public static readonly int[][] KnownChangeParts =
            {
                new[] { -12, -8, -4, 0, 3, 4, 8 }, new[] { -14, -12, -9, -8, -5, -4, 0, 8, -1 },
                new[] { -8, -12, -6, -2, -4, 0, 8, 5 },
            };
            public static readonly int[][] KnownBlendParts =
                { new[] { -31, 0, 16, 31 }, new[] { -31, 0, 8, 31 }, new[] { -31, 24, 0, 31 } };

            static bool IsKnownChange(Tint t)
            {
                foreach (var k in KnownChanges)
                    if (k.Way == t.Way && k.R == t.Offsets[0] && k.G == t.Offsets[1] && k.B == t.Offsets[2])
                        return true;
                return false;
            }

            static bool IsKnownBlend(Tint t)
            {
                foreach (var k in KnownBlends)
                    if (k.R == t.Blend[0] && k.G == t.Blend[1] && k.B == t.Blend[2])
                        return true;
                return false;
            }
            static readonly Dictionary<(int, bool, int), (int Lo, int Hi)?[,]> s_ranges = new Dictionary<(int, bool, int), (int, int)?[,]>();

            static int[] BuildOrder()
            {
                var order = new List<int> { 0 };
                for (int k = 1; k <= 31; k++)
                {
                    order.Add(k);
                    order.Add(-k);
                }
                return order.ToArray();
            }

            static (int, bool, int)[] BuildBlends()
            {
                var blends = new List<(int, bool, int)>();
                foreach (int n in new[] { 32, 8 })
                    foreach (bool toward in new[] { true, false })
                        for (int s = 1; s < n + (toward ? 1 : 0); s++)
                            blends.Add((n, toward, s));
                return blends.ToArray();
            }

            static int BlendValue(int x, int b, int s, int n, bool toward)
            {
                int target = Clamp(x + b, 0, 31);
                int a = toward ? x : target, e = toward ? target : x;
                return a + Pos(e - a, s, n);
            }

            /// <summary>For each x (0 to 31) and out (0 to 31), the offsets giving out from x at this step (an interval).</summary>
            static (int Lo, int Hi)?[,] Ranges(int n, bool toward, int s)
            {
                lock (s_ranges)
                {
                    if (s_ranges.TryGetValue((n, toward, s), out var known))
                        return known;
                    var table = new (int, int)?[32, 32];
                    for (int x = 0; x < 32; x++)
                        for (int b = -31; b <= 31; b++)
                        {
                            int v = BlendValue(x, b, s, n, toward);
                            if (v < 0 || v > 31)
                                continue;
                            var was = table[x, v];
                            table[x, v] = was == null ? (b, b) : (Math.Min(was.Value.Item1, b), Math.Max(was.Value.Item2, b));
                        }
                    s_ranges[(n, toward, s)] = table;
                    return table;
                }
            }

            static (int, int)? Meet((int, int)? a, (int, int)? b)
            {
                if (a == null || b == null)
                    return null;
                int lo = Math.Max(a.Value.Item1, b.Value.Item1), hi = Math.Min(a.Value.Item2, b.Value.Item2);
                return lo <= hi ? (lo, hi) : null;
            }

            static (int, int)? ChangeRange(int v, int out_)
            {
                if (out_ <= 0)
                    return (-31, -v);
                if (out_ >= 31)
                    return (31 - v, 31);
                return (out_ - v, out_ - v);
            }

            /// <summary>An interval's offsets to try: the game's own for this part (`known`), then the two nearest 0, then
            /// its two ends.</summary>
            static List<int> InOrder((int Lo, int Hi)? interval, int[] known)
            {
                var out_ = new List<int>();
                if (interval == null)
                    return out_;
                int lo = interval.Value.Lo, hi = interval.Value.Hi;
                foreach (int o in known)
                    if (o >= lo && o <= hi && !out_.Contains(o))
                        out_.Add(o);
                int near = 0;
                foreach (int o in Order)
                    if (o >= lo && o <= hi)
                    {
                        if (!out_.Contains(o))
                            out_.Add(o);
                        if (++near == 2)
                            break;
                    }
                foreach (int o in new[] { hi, lo })
                    if (!out_.Contains(o))
                        out_.Add(o);
                return out_;
            }

            static int Hand(uint color, int c) => (int)((color >> (3 + 8 * c)) & 0x1F);

            static unsafe bool Fits(Tint t, uint* hand, ushort[] tied)
            {
                for (int n = 0; n < tied.Length; n++)
                {
                    int w = tied[n];
                    uint h = hand[n];
                    if (w == 0 || h == 0)
                        continue;
                    int made = t.Word(w);
                    if ((made & 0x1F) != Hand(h, 0) || ((made >> 5) & 0x1F) != Hand(h, 1) || ((made >> 10) & 0x1F) != Hand(h, 2))
                        return false;
                }
                return true;
            }

            static bool Monotone(List<(int In, int Out)> pairs)
            {
                pairs.Sort((a, b) => a.In != b.In ? a.In.CompareTo(b.In) : a.Out.CompareTo(b.Out));
                for (int k = 1; k < pairs.Count; k++)
                {
                    var a = pairs[k - 1];
                    var b = pairs[k];
                    if (a.In < b.In ? a.Out > b.Out : a.Out != b.Out)
                        return false;
                }
                return true;
            }

            /// <summary>The tint that gives every color in hand (`count` 32 bit colors, the sprites' rule; 0 never drawn)
            /// from the palette a picture was given in: `None` where it is that palette, null where no tint gives them all
            /// (or where red or green falls as the color given rises, which no tint does: a team's palette).</summary>
            public static unsafe Tint? Find(uint* hand, int count, ushort[] tied)
            {
                if (hand == null || count < tied.Length)
                    return null;
                var plain = new List<(int[] P, int[] Q)>();
                bool same = true;
                for (int n = 0; n < tied.Length; n++)
                {
                    int w = tied[n];
                    uint h = hand[n];
                    if (w == 0 || h == 0)
                        continue;
                    int[] p = { w & 0x1F, (w >> 5) & 0x1F, (w >> 10) & 0x1F };
                    int[] q = { Hand(h, 0), Hand(h, 1), Hand(h, 2) };
                    if (p[0] != q[0] || p[1] != q[1] || p[2] != q[2])
                        same = false;
                    // Colors near black are held only by the whole check (blue 1 and black left alone tie the parts).
                    if (p[0] + p[1] + p[2] > 0 && q[0] + q[1] + q[2] > 1)
                        plain.Add((p, q));
                }
                if (same)
                    return None;
                if (plain.Count == 0)
                    return null;
                // Red's and green's order only: blue is where the game's blue 1 goes, which a later blend can lift.
                bool OrderKept(Func<int[], int, int> key)
                {
                    for (int c = 0; c < 2; c++)
                    {
                        var pairs = new List<(int, int)>();
                        foreach (var (p, q) in plain)
                            pairs.Add((key(p, c), q[c]));
                        if (!Monotone(pairs))
                            return false;
                    }
                    return true;
                }
                var ways = new List<int>();
                if (OrderKept((p, c) => p[c]))
                    ways.AddRange(new[] { 0, 1 });
                if (OrderKept((p, c) => 2 * p[0] + 3 * p[1] + p[2]))
                    ways.AddRange(new[] { 2, 3 });
                if (ways.Count == 0)
                    return null;

                Tint? FirstFit<T>(List<T>[] lists, Func<T, T, T, Tint> make)
                {
                    int tried = 0;
                    foreach (var a in lists[0])
                        foreach (var b in lists[1])
                            foreach (var c in lists[2])
                            {
                                var t = make(a, b, c);
                                if (Fits(t, hand, tied))
                                    return t;
                                if (++tried >= MostTried)
                                    return null;
                            }
                    return null;
                }

                // Each plain color's parts by each way, made once.
                var byWay = new int[4][][];
                for (int way = 0; way < 4; way++)
                {
                    byWay[way] = new int[plain.Count][];
                    Span<int> v = stackalloc int[3];
                    for (int k = 0; k < plain.Count; k++)
                    {
                        var p = plain[k].P;
                        WayOf(p[0], p[1], p[2], way, v);
                        byWay[way][k] = new[] { v[0], v[1], v[2] };
                    }
                }

                // A change alone.
                Tint? change = null;
                foreach (int way in ways)
                {
                    var lists = new List<int>[3];
                    for (int c = 0; c < 3; c++)
                    {
                        (int, int)? interval = (-31, 31);
                        for (int k = 0; k < plain.Count; k++)
                            interval = Meet(interval, ChangeRange(byWay[way][k][c], plain[k].Q[c]));
                        lists[c] = InOrder(interval, KnownChangeParts[c]);
                    }
                    change = FirstFit(lists, (a, b, c) => new Tint(way, new[] { a, b, c }, new int[3], 0, 0, true));
                    if (change != null)
                        break;
                }
                // A blend alone (and a unit faded to black).
                Tint? blend = null;
                foreach (var (n, toward, s) in Blends)
                {
                    var table = Ranges(n, toward, s);
                    var lists = new List<int>[3];
                    for (int c = 0; c < 3; c++)
                    {
                        (int, int)? interval = (-31, 31);
                        foreach (var (p, q) in plain)
                            interval = Meet(interval, table[p[c], q[c]]);
                        lists[c] = InOrder(interval, KnownBlendParts[c]);
                    }
                    blend = FirstFit(lists, (a, b, c) => new Tint(0, new int[3], new[] { a, b, c }, s, n, toward));
                    if (blend != null)
                        break;
                    var black = new Tint(0, new int[3], ToBlack, s, n, toward);
                    if (Fits(black, hand, tied))
                    {
                        blend = black;
                        break;
                    }
                }
                if (change != null && blend != null)
                    return IsKnownBlend(blend) && !IsKnownChange(change) ? blend : change;
                if (change != null || blend != null)
                    return change ?? blend;
                // A blend on a change.
                foreach (int way in ways)
                    foreach (var (n, toward, s) in Blends)
                    {
                        var table = Ranges(n, toward, s);
                        var lists = new List<(int O, int B)>[3];
                        for (int c = 0; c < 3; c++)
                        {
                            var pairs = new List<(int, int)>();
                            var offsets = new List<int>(KnownChangeParts[c]);
                            foreach (int o in Order)
                                if (!offsets.Contains(o))
                                    offsets.Add(o);
                            foreach (int o in offsets)
                            {
                                (int, int)? interval = (-31, 31);
                                for (int k = 0; k < plain.Count; k++)
                                {
                                    int want = plain[k].Q[c];
                                    int x = Clamp(byWay[way][k][c] + o, 0, 31);
                                    var allowed = table[x, want];
                                    if (x == 0 && c == 2)
                                    {
                                        // A color the change made black was given blue 1: its blue may be 0 or 1 here.
                                        var other = table[1, want];
                                        allowed = allowed == null ? other : other == null ? allowed
                                                  : (Math.Min(allowed.Value.Item1, other.Value.Item1),
                                                     Math.Max(allowed.Value.Item2, other.Value.Item2));
                                    }
                                    interval = Meet(interval, allowed);
                                    if (interval == null)
                                        break;
                                }
                                foreach (int b in InOrder(interval, KnownBlendParts[c]))
                                    pairs.Add((o, b));
                            }
                            lists[c] = pairs;
                        }
                        var found = FirstFit(lists, (a, b, c) => new Tint(way, new[] { a.O, b.O, c.O },
                                                                          new[] { a.B, b.B, c.B }, s, n, toward));
                        if (found != null)
                            return found;
                    }
                return null;
            }

            // --- an own color through the tint (tints.py: part_table, along, through) ---

            int ChangePart(int v, int c, int top) => Clamp(v + Offsets[c], 0, top);

            int BlendPart(int x, int c, int top, bool black)
            {
                if (Of == 0)
                    return x;
                int target = black ? 1 : Clamp(x + Blend[c], 0, top);
                int a = Toward ? x : target, e = Toward ? target : x;
                return a + Pos(e - a, Steps, Of);
            }

            int[] PartTable(int c, int stage)
            {
                var out_ = new int[33];
                for (int v = 0; v < 33; v++)
                {
                    int top = Math.Max(31, v);
                    out_[v] = stage == 0 ? ChangePart(v, c, top) : BlendPart(v, c, top, stage == 2);
                }
                return out_;
            }

            static byte Along(int[] table, int five, double share)
            {
                int lo = table[Math.Min(five, 32)], hi = table[Math.Min(five + 1, 32)];
                return (byte)Clamp((int)Math.Round(lo * 8 + (hi - lo) * share), 0, 255);
            }

            byte[][]? _change, _blend;
            byte[]? _blendBlack;

            void Build()
            {
                var change = new byte[3][];
                var blend = new byte[3][];
                for (int c = 0; c < 3; c++)
                {
                    int[] table = PartTable(c, 0);
                    if (Way == 2 || Way == 3)
                    {
                        // By (2 red + 3 green + blue) of the five bit parts, and the same of the finer three bits.
                        int div = Way == 2 ? 6 : 12;
                        change[c] = new byte[187 * 43];
                        for (int weight = 0; weight < 187; weight++)
                            for (int fine = 0; fine < 43; fine++)
                                change[c][weight * 43 + fine] = Along(table, weight / div, (double)fine / div);
                    }
                    else
                    {
                        change[c] = new byte[256];
                        for (int v = 0; v < 256; v++)
                            change[c][v] = Way == 1 ? Along(table, (v >> 3) >> 1, (v & 7) / 2.0)
                                                    : Along(table, v >> 3, v & 7);
                    }
                    int[] blendTable = PartTable(c, 1);
                    blend[c] = new byte[256];
                    for (int v = 0; v < 256; v++)
                        blend[c][v] = Along(blendTable, v >> 3, v & 7);
                }
                int[] black = PartTable(2, 2);
                var blendBlack = new byte[256];
                for (int v = 0; v < 256; v++)
                    blendBlack[v] = Along(black, v >> 3, v & 7);
                _change = change;
                _blend = blend;
                _blendBlack = blendBlack;
            }

            /// <summary>An own color (red lowest, as the game keeps a 32 bit color; its top byte left as it is) through the
            /// tint: each part at its five bits as the palette's colors go and its finer bits along the tint's slope there;
            /// a color the change leaves black given blue 8 where it wasn't black, and left out of the blend while black.</summary>
            public uint Apply(uint own)
            {
                if (IsNone)
                    return own;
                if (_change == null)
                    lock (this)
                        if (_change == null)
                            Build();
                int r8 = (int)(own & 0xFF), g8 = (int)((own >> 8) & 0xFF), b8 = (int)((own >> 16) & 0xFF);
                int mr, mg, mb;
                if (Way == 2 || Way == 3)
                {
                    int at = (2 * (r8 >> 3) + 3 * (g8 >> 3) + (b8 >> 3)) * 43 + (2 * (r8 & 7) + 3 * (g8 & 7) + (b8 & 7));
                    mr = _change![0][at];
                    mg = _change[1][at];
                    mb = _change[2][at];
                }
                else
                {
                    mr = _change![0][r8];
                    mg = _change[1][g8];
                    mb = _change[2][b8];
                }
                bool dark = mr < 8 && mg < 8 && mb < 8;
                if (dark && ((r8 | g8 | b8) >> 3) != 0)
                {
                    mb = Math.Max(mb, 8);
                    dark = false;
                }
                int or, og, ob;
                if (dark || Of == 0)
                {
                    or = mr;
                    og = mg;
                    ob = mb;
                }
                else
                {
                    bool black = (mr >> 3) + Blend[0] <= 0 && (mg >> 3) + Blend[1] <= 0 && (mb >> 3) + Blend[2] <= 0;
                    or = _blend![0][mr];
                    og = _blend[1][mg];
                    ob = (black ? _blendBlack! : _blend[2])[mb];
                    if (or < 8 && og < 8 && ob < 8)
                        ob = Math.Max(ob, 8);
                }
                return (own & 0xFF000000u) | ((uint)ob << 16) | ((uint)og << 8) | (uint)or;
            }
        }

        /// <summary>(2.0.2) The tint of the palette in hand for a sheet of more colors (`Tint.Find`), kept by the palette's
        /// colors so a palette met again isn't looked for again: `None` where it is the palette given, null where no tint
        /// gives it.</summary>
        public static unsafe Tint? TintOf(uint* hand, int count, Own own)
        {
            if (hand == null || count < own.Tied.Length)
                return null;
            var key = new uint[own.Tied.Length];
            for (int n = 0; n < key.Length; n++)
                key[n] = hand[n];
            string text = Convert.ToBase64String(System.Runtime.InteropServices.MemoryMarshal.AsBytes(key.AsSpan()));
            lock (own.Tints)
                if (own.Tints.TryGetValue(text, out var known))
                    return known;
            var found = Tint.Find(hand, count, own.Tied);
            lock (own.Tints)
            {
                if (own.Tints.Count >= TintsKept)
                    own.Tints.Clear();
                own.Tints[text] = found;
            }
            return found;
        }

        /// <summary>How many palettes' tints a sheet keeps (a highlight's blend is 64 palettes, back and forth).</summary>
        public const int TintsKept = 512;
    }
}
