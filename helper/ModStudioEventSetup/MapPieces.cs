// Mod Studio Framework: (1.3.0) the mods' own places shown on the world
// map. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi, 26 October: "real new places, built in steps". This is the first
// step, pictures only: each place a mod gives (PlaceFile.cs) is shown on the
// world map as a piece of the map's layout of its own. Every place on the
// world map is a piece of worldmap_map_all.uib (a Base for a town, its
// picture one of ui_wm_icon_base_uitx's, a Point for a battle ground) under
// MapAll's Bases, at its place on the map's picture; the world map screen
// finds the 48 of the game's as it sets itself up (Places.MapSetup) and
// keeps them. Right after it, this copies one of them for each mod's place,
// as the game's own code copies boxes it shows more than once (the layouts'
// copy of a box, Places.PieceCopy: the piece it places copied with it, its
// boxes and animations, under a name of its own), names the copy its own
// (MsqPlace and its place's number among the mods' places), moves it so its
// middle is where the place's file says, puts it in the layer beside the
// piece it was copied from, and shows it as the screen shows a place (its
// animations stopped, Show and Color_Default played to their last frame,
// its markers hidden), its picture the mod's own (made ready as the quests'
// marker's is, Marker.cs) or a game's town picture (its TexChange played).
// The copy is the screen's like the rest: it goes when the screen goes, and
// a screen set up again gets it again; the game's own code never looks at
// it (the screen's pieces are its 48). Every call into the game is one the
// game's own code makes the same way. helper/Checks runs all of it against
// a stand-in for the screen.
//
// (1.3.1) A picture only, as step 1 promises. His test 22 showed a copy
// answering the mouse as the place it was copied from (Lesalia for the towns,
// Mandalia Plain for the battle ground: its name, Travel Here, its own
// label): the copy of a piece keeps the tag the screen gives its places'
// pieces (0x1F at + 0x220, the place at + 0x224), by which the screen's
// handler of the mouse knows a place, and its collision boxes, which are
// what the mouse's hit query finds. So a copy's tag is cleared, and its
// collision boxes are turned off (they are never drawn; the query leaves out
// a box that isn't visible).
//
// (1.7.0) A place the game goes to (Destinations.cs: its number past the
// game's 48, the program given what it keeps for a place by its number) is
// a place of the screen's like its own: its copy keeps the tag, with its own
// number, and its collision boxes, so the mouse finds it, its name shows on
// the map (its label's text, TextBoardMapName's Title, set to the place's
// name) and in the location info (its Town and PlaceName rows), and choosing
// it travels there; the screen's row for it (its piece, its box, its kind, a
// town's byte) is written past the screen's end, where the screen's reads
// of a mod's place's row go. Without the program so given, as 1.3.1.
//
// (1.20.0) A town darkened once a quest's flag is set (PlaceFile's
// Darkened): its copy plays Color_Grayout (its texture drawn at 155 of 255)
// in place of Color_Default, the other stopped first, as the game's own
// two-way play does for its places whose situation holds (0xF638C, from the
// screen's showing of a place, 0x15AE14); Hooks.ModDarkened asks it at the
// screen's setup and each time the screen shows one of the game's places.
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace ModStudioEventSetup
{
    public sealed unsafe class MapPieces
    {
        /// <summary>Where the world map screen keeps MapAll's piece (which holds Bases).</summary>
        public const int ScreenMapAll = 0x1F8;
        /// <summary>The screen's places' pieces: 48 of 24 bytes (Places.MarkerPieces).</summary>
        public const int ScreenPlaces = 48;
        /// <summary>A box of the layouts, as the game keeps one: its name (a string of the game's), the layer it
        /// is in, its kind (0x0C a reference, 2 a picture), its width and height.</summary>
        public const int BoxName = 8, BoxParent = 0x18, BoxWidth = 0x40, BoxHeight = 0x44, ReferenceKind = 0x0C;
        /// <summary>The names a copy's box takes: this and its place's number among the mods' places.</summary>
        public const string BoxPrefix = "MsqPlace";
        /// <summary>A town's own picture's part in its part list.</summary>
        public const int PicturePart = 1;
        /// <summary>(1.3.1) The tag the screen gives each of its places' pieces as it sets them up (0x1F, the place's
        /// number at + 4: Places.MapSetup), by which its handler of the mouse over a piece knows the place; the
        /// layouts' copy of a piece copies it.</summary>
        public const int PieceTag = 0x220, PiecePlace = 0x224, PlaceTag = 0x1F;
        /// <summary>(1.3.1) A box's own visibility (as its layout and animations set it) and as drawn and hit (its
        /// own, its alpha's and its layer's); a layer's first box and a box's next; a layer's kind and a collision
        /// box's (GUICollisionNode), the one kind the mouse's hit query takes.</summary>
        public const int BoxVisible = 0x90, BoxShown = 0xCC, LayerFirst = 0xD0, BoxNext = 0x20, LayerKind = 1,
                         CollisionKind = 0x0D;
        const int TreeDepth = 16, TreeBoxes = 1024;
        const int StringBytes = 16, StringNumber = 8;
        /// <summary>The names looked for and played: the pieces' layer's piece, a town's picture, the animations
        /// that show a place (as the screen plays them), the markers in a place's piece.</summary>
        static readonly string[] Looked =
            { "Bases", "Image01", "Show", "Color_Default", "Hide", "Quest", "Next", "MidwayPoint", "IconJob",
              "TextBoardMapName", "Title", "Color_Grayout" };
        const int BasesName = 0, PictureName = 1, ShowName = 2, ColorName = 3, HideName = 4, FirstMarker = 5,
                  LastMarker = 8, LabelName = 9, TitleName = 10, GrayName = 11;
        /// <summary>(1.7.0) A label's text box's kind.</summary>
        public const int TextKind = 3;

        readonly byte* _base;
        readonly Places _places;
        readonly List<MapPlace> _mapPlaces;
        /// <summary>The names' strings (16 bytes each, then their characters): Looked's, then each place's box's
        /// name, its parts' name (characters only, made a string when given) and its TexChange's name.</summary>
        readonly nint _names;
        readonly nint[] _boxes, _parts, _icons;
        /// <summary>(1.7.0) Each place's number of the world map's when the game goes to it (else -1), and its name's
        /// text (UTF-8, ended), for its label.</summary>
        readonly int[] _numbers;
        readonly nint[] _titles;
        /// <summary>(1.7.0) The rows past the screen's end, when the program has room for them (0: none).</summary>
        readonly int _rows;

        public MapPieces(byte* start, Places places, List<MapPlace> mapPlaces, List<Destination>? destinations = null)
        {
            _base = start;
            _places = places;
            _mapPlaces = mapPlaces;
            _numbers = new int[mapPlaces.Count];
            _titles = new nint[mapPlaces.Count];
            Array.Fill(_numbers, -1);
            if (destinations != null && destinations.Count > 0)
            {
                _rows = Destinations.RowCount(destinations);
                foreach (var d in destinations)
                {
                    int n = mapPlaces.IndexOf(d.Place);
                    if (n < 0)
                        continue;
                    _numbers[n] = d.Number;
                    var utf8 = System.Text.Encoding.UTF8.GetBytes(d.Place.Name + "\0");
                    _titles[n] = (nint)NativeMemory.AllocZeroed((nuint)utf8.Length);
                    Marshal.Copy(utf8, 0, _titles[n], utf8.Length);
                }
            }
            var all = new List<string>(Looked);
            for (int n = 0; n < mapPlaces.Count; n++)
            {
                all.Add(BoxPrefix + n);
                all.Add(mapPlaces[n].Parts);
                all.Add(mapPlaces[n].Icon.Length > 0 ? "TexChange" + mapPlaces[n].Icon : "");
            }
            int characters = 0;
            foreach (var name in all)
                characters += name.Length + 1;
            _names = (nint)NativeMemory.AllocZeroed((nuint)(all.Count * StringBytes + characters));
            byte* text = (byte*)_names + all.Count * StringBytes;
            for (int n = 0; n < all.Count; n++)
            {
                *(nint*)(_names + n * StringBytes) = (nint)text;
                foreach (char c in all[n])
                    *text++ = (byte)c;
                *text++ = 0;
            }
            _boxes = new nint[mapPlaces.Count];
            _parts = new nint[mapPlaces.Count];
            _icons = new nint[mapPlaces.Count];
            for (int n = 0; n < mapPlaces.Count; n++)
            {
                _boxes[n] = Name(Looked.Length + 3 * n);
                _parts[n] = *(nint*)Name(Looked.Length + 3 * n + 1);
                _icons[n] = Name(Looked.Length + 3 * n + 2);
            }
        }

        nint Name(int n) => _names + n * StringBytes;

        /// <summary>A string of the game's given to a box's string (made, given, let go), as the game gives one.</summary>
        void SetString(nint into, nint characters)
        {
            var make = (delegate* unmanaged<nint, nint, nint>)(_base + _places.StringMake);
            var assign = (delegate* unmanaged<nint, nint, nint>)(_base + _places.StringAssign);
            var release = (delegate* unmanaged<nint, uint, int>)(_base + _places.StringRelease);
            byte* made = stackalloc byte[StringBytes];
            for (int n = 0; n < StringBytes; n++)
                made[n] = 0;
            make((nint)made, characters);
            assign(into, (nint)made);
            uint number = *(uint*)(made + StringNumber);
            if (number != 0)
                release(*(nint*)(_base + _places.StringPool), number);
        }

        /// <summary>The first of the screen's pieces of a town (or a battle ground) to copy: a reference shown
        /// by the screen, or 0.</summary>
        static nint Model(nint screen, bool town, out nint piece)
        {
            for (int place = 0; place < ScreenPlaces; place++)
            {
                nint at = screen + Places.MarkerPieces + place * Places.MarkerPieceSize;
                nint box = *(nint*)(at + Places.PieceBox);
                piece = *(nint*)at;
                if (box != 0 && piece != 0 && (*(byte*)(at + Places.PieceTown) != 0) == town
                    && *(int*)(box + Marker.BoxKind) == ReferenceKind && *(nint*)(box + BoxParent) != 0)
                    return box;
            }
            piece = 0;
            return 0;
        }

        /// <summary>(1.3.1) A piece's own collision boxes, in its layers (not in the pieces it places, whose
        /// reference boxes are left as they are), turned off: the mouse's hit query never finds them. How many.</summary>
        public static int Untouchable(nint root)
        {
            int turnedOff = 0, seen = 0;
            void Walk(nint layer, int depth)
            {
                if (depth > TreeDepth)
                    return;
                for (nint box = *(nint*)(layer + LayerFirst); box != 0 && seen++ < TreeBoxes;
                     box = *(nint*)(box + BoxNext))
                {
                    int kind = *(int*)(box + Marker.BoxKind);
                    if (kind == CollisionKind)
                    {
                        *(byte*)(box + BoxVisible) = 0;
                        *(byte*)(box + BoxShown) = 0;
                        turnedOff++;
                    }
                    else if (kind == LayerKind)
                        Walk(box, depth + 1);
                }
            }
            Walk(root, 0);
            return turnedOff;
        }

        /// <summary>After the world map screen has set its places' pieces up: each mod's place added to it (once:
        /// a screen that already has it is left as it is). What happens is said, each line once.</summary>
        public void Add(nint screen, Action<string> say)
        {
            if (screen == 0 || _mapPlaces.Count == 0)
                return;
            nint layouts = *(nint*)(screen + Marker.ScreenLayouts);
            nint mapAll = *(nint*)(screen + ScreenMapAll);
            if (layouts == 0 || mapAll == 0)
                return;
            var child = (delegate* unmanaged<nint, nint, nint>)(_base + _places.ChildPiece);
            var boxNamed = (delegate* unmanaged<nint, nint, nint>)(_base + _places.BoxNamed);
            nint bases = child(mapAll, Name(BasesName));
            if (bases == 0)
            {
                say("the world map has no Bases where its places are: the mods' places aren't shown.");
                return;
            }
            for (int n = 0; n < _mapPlaces.Count; n++)
            {
                var place = _mapPlaces[n];
                string who = $"{place.Name} ({place.ModName})";
                try
                {
                    if (boxNamed(bases + Marker.PieceTree, _boxes[n]) != 0)
                    {
                        Row(screen, bases, n);
                        continue;
                    }
                    string? said = AddOne(layouts, screen, bases, n, place);
                    if (said == null && _numbers[n] >= 0)
                        say($"{who} is on the world map at {place.X}, {place.Y}, place {_numbers[n]}.");
                    else
                        say(said == null ? $"{who} is on the world map at {place.X}, {place.Y}." : $"{who} {said}");
                }
                catch (Exception e)
                {
                    say($"{who} isn't shown on the world map ({e.GetType().Name}: {e.Message}).");
                }
            }
        }

        /// <summary>(1.20.0) A mod's town's copy on a screen darkened (Color_Grayout) or not (Color_Default), the
        /// other stopped first, as the game's two-way play shows its own places (0xF638C): false when the screen has
        /// no copy of it (not set up yet, or not a town's).</summary>
        public bool Darken(nint screen, MapPlace place, bool dark)
        {
            int n = _mapPlaces.IndexOf(place);
            if (screen == 0 || n < 0 || !place.Town || _places.AnimationStop < 0)
                return false;
            nint mapAll = *(nint*)(screen + ScreenMapAll);
            if (mapAll == 0)
                return false;
            var child = (delegate* unmanaged<nint, nint, nint>)(_base + _places.ChildPiece);
            var play = (delegate* unmanaged<nint, nint, int, void>)(_base + _places.AnimationPlay);
            var stopOne = (delegate* unmanaged<nint, nint, void>)(_base + _places.AnimationStop);
            nint bases = child(mapAll, Name(BasesName));
            nint piece = bases == 0 ? 0 : child(bases, _boxes[n]);
            if (piece == 0)
                return false;
            stopOne(piece, Name(dark ? ColorName : GrayName));
            play(piece, Name(dark ? GrayName : ColorName), -1);
            return true;
        }

        /// <summary>One place's piece added: null, or what went wrong (after its name).</summary>
        string? AddOne(nint layouts, nint screen, nint bases, int n, MapPlace place)
        {
            var child = (delegate* unmanaged<nint, nint, nint>)(_base + _places.ChildPiece);
            var boxNamed = (delegate* unmanaged<nint, nint, nint>)(_base + _places.BoxNamed);
            var ready = (delegate* unmanaged<nint, nint, byte, byte>)(_base + _places.PartsReady);
            var copy = (delegate* unmanaged<nint, nint, byte, nint>)(_base + _places.PieceCopy);
            var move = (delegate* unmanaged<nint, int, int, void>)(_base + _places.PieceMove);
            var add = (delegate* unmanaged<nint, nint, nint, void>)(_base + _places.PieceAdd);
            var play = (delegate* unmanaged<nint, nint, int, void>)(_base + _places.AnimationPlay);
            var stop = (delegate* unmanaged<nint, void>)(_base + _places.AnimationsStop);
            nint model = Model(screen, place.Town, out _);
            if (model == 0)
                return $"isn't shown on the world map: the map has no {(place.Town ? "town" : "battle ground")} to "
                       + "copy.";
            if (place.Picture.Length > 0 && ready(layouts, _parts[n], 0) == 0)
                return $"isn't shown on the world map: its texture ({place.Picture}) wasn't made ready.";
            nint box = copy(layouts, model, 0);
            if (box == 0)
                return "isn't shown on the world map: its piece wasn't made.";
            SetString(box + BoxName, *(nint*)_boxes[n]);
            move(box, place.X - *(int*)(model + BoxWidth) / 2, place.Y - *(int*)(model + BoxHeight) / 2);
            add(*(nint*)(model + BoxParent), box, model);
            nint piece = child(bases, _boxes[n]);
            if (piece == 0)
                return "isn't shown on the world map: its piece wasn't found once made.";
            if (_numbers[n] >= 0)
            {
                // (1.7.0) A place of the screen's: its tag, its number, its collision boxes as copied.
                *(int*)(piece + PieceTag) = PlaceTag;
                *(int*)(piece + PiecePlace) = _numbers[n];
            }
            else
            {
                *(int*)(piece + PieceTag) = 0;
                *(int*)(piece + PiecePlace) = 0;
                Untouchable(piece + Marker.PieceTree);
            }
            stop(piece);
            play(piece, Name(ShowName), -1);
            if (place.Town)
                play(piece, Name(ColorName), -1);
            for (int marker = FirstMarker; marker <= LastMarker; marker++)
            {
                nint shown = child(piece, Name(marker));
                if (shown == 0)
                    continue;
                stop(shown);
                play(shown, Name(HideName), -1);
            }
            if (place.Icon.Length > 0)
                play(piece, _icons[n], -1);
            if (place.Picture.Length > 0)
            {
                nint picture = boxNamed(piece + Marker.PieceTree, Name(PictureName));
                if (picture == 0 || *(int*)(picture + Marker.BoxKind) != Marker.PictureKind)
                    return "is on the world map without its texture: its piece has no texture where the game's has one.";
                SetString(picture + Marker.PictureParts, _parts[n]);
                *(int*)(picture + Marker.PicturePart) = PicturePart;
            }
            if (_numbers[n] >= 0)
            {
                Row(screen, bases, n);
                return Label(piece, n);
            }
            return null;
        }

        /// <summary>(1.7.0) A place's label on the map (its piece's TextBoardMapName's Title, a text box) given its
        /// name, as the location info sets its own (0x158D21: a text of a message's number it shows instead let go,
        /// the box marked to be drawn again, then its text set): null, or what went wrong (after its name).</summary>
        string? Label(nint piece, int n)
        {
            var child = (delegate* unmanaged<nint, nint, nint>)(_base + _places.ChildPiece);
            var boxNamed = (delegate* unmanaged<nint, nint, nint>)(_base + _places.BoxNamed);
            var setText = (delegate* unmanaged<nint, nint, void>)(_base + _places.SetText);
            nint label = child(piece, Name(LabelName));
            nint title = label == 0 ? 0 : boxNamed(label + Marker.PieceTree, Name(TitleName));
            if (title == 0 || *(int*)(title + Marker.BoxKind) != TextKind)
                return "is on the world map without its name: its piece has no label where the game's has one.";
            if (*(int*)(title + TextMessage) != 0)
            {
                *(int*)(title + TextMessage) = 0;
                *(byte*)(title + TextChanged) = 1;
            }
            setText(title, _titles[n]);
            return null;
        }

        /// <summary>(1.7.0) A text box's message (a number: its text a message's instead of its own) and its mark to
        /// be drawn again.</summary>
        public const int TextMessage = 0xF8, TextChanged = 0x13C;

        /// <summary>(1.7.0) A place's row in the screen past its end (where the screen's reads of a mod's place's row
        /// go: Destinations.cs), from its piece and box as found by name: its piece, its box, its kind (0 a town, 1 a
        /// battle ground), a town's byte. Only for a place the game goes to, in a screen the program made with room.</summary>
        void Row(nint screen, nint bases, int n)
        {
            if (_numbers[n] < 0 || _rows == 0)
                return;
            int index = _numbers[n] - Destinations.FirstNumber;
            if (index < 0 || index >= _rows)
                return;
            var child = (delegate* unmanaged<nint, nint, nint>)(_base + _places.ChildPiece);
            var boxNamed = (delegate* unmanaged<nint, nint, nint>)(_base + _places.BoxNamed);
            nint row = screen + Destinations.ScreenRows + index * Destinations.RowSize;
            *(nint*)(row + Destinations.RowPiece) = child(bases, _boxes[n]);
            *(nint*)(row + Destinations.RowBox) = boxNamed(bases + Marker.PieceTree, _boxes[n]);
            *(int*)(row + Destinations.RowKind) = _mapPlaces[n].Town ? 0 : 1;
            *(byte*)(row + Destinations.RowTown) = (byte)(_mapPlaces[n].Town ? 1 : 0);
        }

        /// <summary>(1.7.0) The screen's switch of its places' collision boxes, after the game's own: the same for the
        /// mods' places' pieces in its rows past its end (on while none of its two reasons to be off stands, as the
        /// game's at + 0xD1C).</summary>
        public void Switched(nint screen)
        {
            if (screen == 0 || _rows == 0)
                return;
            var boxOfKind = (delegate* unmanaged<nint, int, int, nint>)(_base + _places.BoxOfKind);
            var refresh = (delegate* unmanaged<nint, byte, void>)(_base + _places.BoxRefresh);
            byte on = (byte)(*(int*)(screen + SwitchReasons) == 0 ? 1 : 0);
            for (int index = 0; index < _rows; index++)
            {
                nint piece = *(nint*)(screen + Destinations.ScreenRows + index * Destinations.RowSize);
                if (piece == 0)
                    continue;
                for (int which = 0; which < 2; which++)
                {
                    nint box = boxOfKind(piece + Marker.PieceTree, CollisionKind, which);
                    if (box == 0)
                        continue;
                    *(byte*)(box + BoxVisible) = on;
                    refresh(box, 1);
                }
            }
        }

        /// <summary>(1.7.0) Where the screen keeps its two reasons for its places' collision boxes to be off (a bit
        /// each).</summary>
        public const int SwitchReasons = 0xD1C;
    }
}
