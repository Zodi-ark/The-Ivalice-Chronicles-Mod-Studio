// Mod Studio Framework: (1.2.5) the quests' markers on the world map. Part
// of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi, 26 October: "there should be a quest marker for every quest if the
// modders choses to have it, the marker should be a different hue that they
// can pick". Every place on the world map (a piece of its layout, Base or
// Point, worldmap_map_all.uib) holds the game's three markers: Quest (a pin,
// ui_wm_01_uitx's part PinQuest, blue, and two glows, cyan), Next and
// MidwayPoint. Hooks.MarkerState hands the screen's showing of a place to
// Show: where a quest with a Marker waits, the screen shows the place's Quest
// marker, and this gives it the quest's color. The game colors a box by
// multiplying its picture (its own color, times its parents'), so the blue
// pin can only get darker: the pin is given a light picture of its own
// (helper/marker, shipped at the game's paths), as the screen changes the
// walking Ramza's picture (its parts' name made a string of the game's and
// given to the picture, its part set), and the pin and its two glows the
// quest's color. None of the marker's animations (Show, Hide, Loop, Out,
// OpenQuest) sets a color. A place no quest's marker is shown at is given
// back the game's picture and colors, as learned from the first pin met.
// Every call into the game is one the game's own code makes the same way.
// (1.8.0) A mod's own place (Destinations.cs: its row past the screen's 48)
// is never shown by the screen's function, which stops at 47 and keeps a
// state in an array of 48: ShowMods shows or hides its piece's Quest marker
// itself, as that function does a place's (the marker's Show and Loop
// played, or its Hide), when the screen shows any place, and paints it.
// helper/Checks runs all of it against a stand-in for the game's screen.
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

namespace ModStudioEventSetup
{
    public sealed unsafe class Marker
    {
        /// <summary>The world map screen's showing of a place and its marker, the game's own function
        /// (Places.MarkerState): the screen, the place's state (16 bytes), the place.</summary>
        public delegate void ShowFunction(nint screen, nint state, int place);

        /// <summary>A place's state, as the world map screen keeps it: its marker (0 none, 1 Quest,
        /// 2 MidwayPoint, 3 Next), whether the place is shown, whether its marker plays Loop.</summary>
        public const int Kind = 0, Shown = 8, Loop = 9;
        public const byte QuestMarker = 1;
        /// <summary>The quests' marker's picture: its parts' name and its part
        /// (dev/research/sidequests/make_marker_picture.py; helper/build.py ships the files at the game's
        /// paths, which the mod loader serves).</summary>
        public const string Parts = "UITextureParts://ui/ffto/worldmap/textureparts/msq_quest_marker_uitx";
        public const int PinPart = 1;
        /// <summary>A box of the layouts, as the game keeps one: its kind (2 a picture), its color (bytes
        /// R, G, B, A), a picture's parts' name (a string of the game's: its characters, then its
        /// number) and its part; a piece's tree, in it.</summary>
        public const int BoxKind = 0x34, BoxColor = 0x64, PictureParts = 0xE8, PicturePart = 0xF8, PieceTree = 0x110;
        public const int PictureKind = 2;
        /// <summary>Where the world map screen keeps its layouts (what it makes a picture's parts ready in).</summary>
        public const int ScreenLayouts = 0x18;
        /// <summary>A string of the game's: its characters, its number (0: looked for by its characters).</summary>
        const int StringBytes = 16, StringNumber = 8;
        /// <summary>The longest parts' name learned from the game.</summary>
        const int MostName = 256;
        /// <summary>The names looked for: a place's quest marker; its pin and its two glows; (1.8.0) the marker's
        /// animations, as the screen plays them.</summary>
        static readonly string[] Looked = { "Quest", "Image00", "GlowCircle", "GlowCircle00", "Show", "Loop", "Hide" };
        const int QuestName = 0, PinName = 1, GlowName = 2, Glow00Name = 3, ShowName = 4, LoopName = 5, HideName = 6;

        readonly byte* _base;
        readonly Places _places;
        /// <summary>(1.8.0) The mods' places' rows past the screen's 48 (Destinations.cs), and what each mod's
        /// place's marker was last given: its piece then and its color (null: hidden).</summary>
        readonly int _modRows;
        readonly Dictionary<int, (nint Piece, uint? Color)> _modShown = new Dictionary<int, (nint, uint?)>();
        /// <summary>The names' strings (16 bytes each, then their characters), and our parts' name's characters.</summary>
        readonly nint _names, _parts;
        /// <summary>The game's look, learned from the first pin met: its parts' name (characters), part, and the
        /// pin's and the glows' colors.</summary>
        nint _gameParts;
        int _gamePart;
        uint _gamePin, _gameGlow, _gameGlow00;
        bool _learned;

        public Marker(byte* start, Places places, int modRows = 0)
        {
            _base = start;
            _places = places;
            _modRows = modRows;
            int characters = 0;
            foreach (var name in Looked)
                characters += name.Length + 1;
            _names = (nint)NativeMemory.AllocZeroed((nuint)(Looked.Length * StringBytes + characters));
            byte* text = (byte*)_names + Looked.Length * StringBytes;
            for (int n = 0; n < Looked.Length; n++)
            {
                *(nint*)(_names + n * StringBytes) = (nint)text;
                text = Write(text, Looked[n]);
            }
            _parts = (nint)NativeMemory.AllocZeroed((nuint)(Parts.Length + 1));
            Write((byte*)_parts, Parts);
        }

        static byte* Write(byte* into, string text)
        {
            foreach (char c in text)
                *into++ = (byte)c;
            *into++ = 0;
            return into;
        }

        nint Name(int n) => _names + n * StringBytes;

        /// <summary>Whether a picture shows our parts (its parts' name's characters ours).</summary>
        bool IsOurs(nint pin)
        {
            byte* name = *(byte**)(pin + PictureParts);
            if (name == null)
                return false;
            for (int n = 0; n <= Parts.Length; n++)
                if (name[n] != (n < Parts.Length ? (byte)Parts[n] : 0))
                    return false;
            return true;
        }

        /// <summary>A place's piece on the screen: the game's in its 48 rows, (1.8.0) a mod's in its row past them;
        /// 0 for none.</summary>
        nint PieceOf(nint screen, int place)
        {
            if (place >= 0 && place < QuestFile.Places)
                return *(nint*)(screen + Places.MarkerPieces + place * Places.MarkerPieceSize);
            int row = place - Destinations.FirstNumber;
            if (row < 0 || row >= _modRows)
                return 0;
            return *(nint*)(screen + Destinations.ScreenRows + row * Destinations.RowSize);
        }

        /// <summary>A place's quest marker's pin and glows (0 for any not there).</summary>
        (nint Pin, nint Glow, nint Glow00) Boxes(nint screen, int place)
        {
            nint piece = PieceOf(screen, place);
            if (piece == 0)
                return (0, 0, 0);
            var child = (delegate* unmanaged<nint, nint, nint>)(_base + _places.ChildPiece);
            var box = (delegate* unmanaged<nint, nint, nint>)(_base + _places.BoxNamed);
            nint quest = child(piece, Name(QuestName));
            if (quest == 0)
                return (0, 0, 0);
            nint pin = box(quest + PieceTree, Name(PinName));
            if (pin != 0 && *(int*)(pin + BoxKind) != PictureKind)
                pin = 0;
            return (pin, box(quest + PieceTree, Name(GlowName)), box(quest + PieceTree, Name(Glow00Name)));
        }

        /// <summary>The game's look, from a pin not yet ours: its parts' name, part and colors.</summary>
        void Learn(nint pin, nint glow, nint glow00)
        {
            if (_learned || IsOurs(pin))
                return;
            byte* name = *(byte**)(pin + PictureParts);
            int length = 0;
            while (name != null && length < MostName && name[length] != 0)
                length++;
            if (name == null || length == 0 || length == MostName)
                return;
            _gameParts = (nint)NativeMemory.AllocZeroed((nuint)(length + 1));
            Buffer.MemoryCopy(name, (void*)_gameParts, length + 1, length);
            _gamePart = *(int*)(pin + PicturePart);
            _gamePin = *(uint*)(pin + BoxColor);
            _gameGlow = glow == 0 ? 0 : *(uint*)(glow + BoxColor);
            _gameGlow00 = glow00 == 0 ? 0 : *(uint*)(glow00 + BoxColor);
            _learned = true;
        }

        /// <summary>A picture given another parts' name, as the game gives one (made a string of the
        /// game's, given, let go).</summary>
        void SetParts(nint pin, nint characters)
        {
            var make = (delegate* unmanaged<nint, nint, nint>)(_base + _places.StringMake);
            var assign = (delegate* unmanaged<nint, nint, nint>)(_base + _places.StringAssign);
            var release = (delegate* unmanaged<nint, uint, int>)(_base + _places.StringRelease);
            byte* made = stackalloc byte[StringBytes];
            for (int n = 0; n < StringBytes; n++)
                made[n] = 0;
            make((nint)made, characters);
            assign(pin + PictureParts, (nint)made);
            uint number = *(uint*)(made + StringNumber);
            if (number != 0)
                release(*(nint*)(_base + _places.StringPool), number);
        }

        /// <summary>The screen shows a place, `show` the game's own function, called once whatever
        /// happens here. Where the game shows the place and no marker of its own, and `colorAt` gives
        /// the color of a quest with a Marker waiting there: the game's quest marker shown (a copy of
        /// the place's state given, its marker 1, its Loop), the state the screen keeps set back to the
        /// game's, the marker painted the color. Elsewhere: the game's own, and the place given back
        /// the game's look where it was painted. A fault is said, never thrown.</summary>
        public void Show(nint screen, nint state, int place, Func<int, uint?> colorAt, ShowFunction show,
                         Action<string> say)
        {
            uint? color = null;
            try
            {
                if (screen != 0 && state != 0 && place >= 0 && place < QuestFile.Places
                    && *(byte*)(state + Shown) != 0 && *(byte*)(state + Kind) == 0)
                    color = colorAt(place);
            }
            catch (Exception e)
            {
                say($"a side quest's marker wasn't looked for ({e.GetType().Name}: {e.Message}).");
            }
            if (color == null)
            {
                show(screen, state, place);
                try
                {
                    if (screen != 0 && place >= 0 && place < QuestFile.Places)
                        Unpaint(screen, place);
                }
                catch (Exception e)
                {
                    say($"a place's marker wasn't given back the game's look ({e.GetType().Name}: {e.Message}).");
                }
                return;
            }
            byte* kept = stackalloc byte[Places.MarkerStateSize];
            byte* given = stackalloc byte[Places.MarkerStateSize];
            for (int n = 0; n < Places.MarkerStateSize; n++)
                kept[n] = given[n] = *(byte*)(state + n);
            given[Kind] = QuestMarker;
            given[Loop] = 1;
            show(screen, (nint)given, place);
            try
            {
                byte* stored = (byte*)screen + Places.MarkerStates + place * Places.MarkerStateSize;
                for (int n = 0; n < Places.MarkerStateSize; n++)
                    stored[n] = kept[n];
                string? said = Paint(screen, place, color.Value);
                if (said != null)
                    say(said);
            }
            catch (Exception e)
            {
                say($"a side quest's marker wasn't colored ({e.GetType().Name}: {e.Message}).");
            }
        }

        /// <summary>A place's quest marker in a quest's color (bytes R, G, B, A): its pin given the
        /// quests' marker's picture (made ready first, as the game makes a picture's parts ready),
        /// its pin and glows the color. What to say once, or null.</summary>
        public string? Paint(nint screen, int place, uint color)
        {
            var (pin, glow, glow00) = Boxes(screen, place);
            if (pin == 0)
                return $"place {place}'s quest marker has no texture where the game's has one: a side quest's marker "
                       + "there isn't colored.";
            Learn(pin, glow, glow00);
            if (!_learned)
                return $"place {place}'s quest marker's texture has no name the helper can keep: a side quest's "
                       + "marker there isn't colored.";
            string? said = null;
            if (!IsOurs(pin))
            {
                nint layouts = *(nint*)(screen + ScreenLayouts);
                var ready = (delegate* unmanaged<nint, nint, byte, byte>)(_base + _places.PartsReady);
                if (layouts == 0 || ready(layouts, _parts, 0) == 0)
                    said = "the side quests' marker's texture wasn't made ready: their markers show the game's pin in "
                           + "their colors.";
                else
                {
                    SetParts(pin, _parts);
                    *(int*)(pin + PicturePart) = PinPart;
                }
            }
            *(uint*)(pin + BoxColor) = color;
            if (glow != 0)
                *(uint*)(glow + BoxColor) = color;
            if (glow00 != 0)
                *(uint*)(glow00 + BoxColor) = color;
            return said;
        }

        /// <summary>(1.8.0) The mods' places a quest's marker may show at (`places`, past the game's 48): each
        /// one's Quest marker shown (its Show and Loop played from their start, as the screen plays a place's)
        /// and painted where `colorAt` gives a color, hidden (its Hide played to its end, the game's look given
        /// back) where it gives none; only where its piece or color changed since. A fault is said, never
        /// thrown.</summary>
        public void ShowMods(nint screen, IReadOnlyList<int> places, Func<int, uint?> colorAt, Action<string> say)
        {
            if (screen == 0)
                return;
            foreach (int place in places)
            {
                try
                {
                    nint piece = PieceOf(screen, place);
                    if (piece == 0)
                    {
                        _modShown.Remove(place);
                        continue;
                    }
                    uint? color = colorAt(place);
                    if (_modShown.TryGetValue(place, out var shown) && shown.Piece == piece && shown.Color == color)
                        continue;
                    _modShown[place] = (piece, color);
                    var child = (delegate* unmanaged<nint, nint, nint>)(_base + _places.ChildPiece);
                    var play = (delegate* unmanaged<nint, nint, int, void>)(_base + _places.AnimationPlay);
                    var stop = (delegate* unmanaged<nint, void>)(_base + _places.AnimationsStop);
                    nint quest = child(piece, Name(QuestName));
                    if (quest == 0)
                    {
                        say($"place {place}'s piece has no quest marker where the game's has one: a side quest's "
                            + "marker isn't shown there.");
                        continue;
                    }
                    stop(quest);
                    if (color == null)
                    {
                        play(quest, Name(HideName), -1);
                        Unpaint(screen, place);
                        continue;
                    }
                    play(quest, Name(ShowName), 0);
                    play(quest, Name(LoopName), 0);
                    string? said = Paint(screen, place, color.Value);
                    if (said != null)
                        say(said);
                }
                catch (Exception e)
                {
                    say($"a side quest's marker at place {place} wasn't shown ({e.GetType().Name}: {e.Message}).");
                }
            }
        }

        /// <summary>A place's quest marker given back the game's look, where it was given a quest's.</summary>
        public void Unpaint(nint screen, int place)
        {
            if (!_learned)
                return;
            var (pin, glow, glow00) = Boxes(screen, place);
            if (pin == 0)
                return;
            bool ours = IsOurs(pin);
            if (!ours && *(uint*)(pin + BoxColor) == _gamePin)
                return;
            if (ours)
            {
                SetParts(pin, _gameParts);
                *(int*)(pin + PicturePart) = _gamePart;
            }
            *(uint*)(pin + BoxColor) = _gamePin;
            if (glow != 0)
                *(uint*)(glow + BoxColor) = _gameGlow;
            if (glow00 != 0)
                *(uint*)(glow00 + BoxColor) = _gameGlow00;
        }
    }
}
