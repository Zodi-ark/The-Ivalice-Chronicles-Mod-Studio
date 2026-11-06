// Mod Studio Framework: (1.4.0) the mods' own roads drawn on the world map.
// Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi, 26 October, after his test 23: "Roads to new places", step 2 of his
// "real new places, built in steps". Its first part, pictures only: each
// road a mod gives (RoadFile.cs) is drawn on the world map as a picture of
// the map's layout of its own. Every road the game draws is a picture box of
// worldmap_map_all.uib's Route (its layer LayerRoute: R_ and the road's name,
// a part of ui_wm_route_all_uitx at its top left on the map's picture, the
// part's size), shown and hidden by its opacity, coloured white or grey; the
// world map screen keeps its Route piece as it sets itself up
// (Places.MapSetup) and shows the game's 51 roads by their names. Right
// after it, this copies one of those pictures for each mod's road, as the
// game's own code copies boxes it shows more than once (the layouts' copy of
// a box, Places.PieceCopy: a picture box made, its fields copied), names the
// copy its own (MsqRoad and its number among the mods' roads: the game never
// finds it by a name, so never shows, hides or greys it), moves it to where
// the road's file says, sizes it to its picture (Places.BoxSize), puts it in
// the layer beside the picture it was copied from (under every place, as the
// game's roads are), and gives it its picture (the mod's own, made ready as
// the places' and the quests' marker's are), its opacity 1, its colour white
// and seen. A picture box has no collision box and no tag, so the mouse never
// finds it (trap 245). The copy is the screen's like the rest: it goes when
// the screen goes, and a screen set up again gets it again. Every call into
// the game is one the game's own code makes the same way. helper/Checks runs
// all of it against a stand-in for the screen.
//
// (1.4.1) His test 24 drew the three roads, and its console said first "the
// world map has no Route where its roads are": the screen's setup runs once
// before its layouts are read, and keeps nothing then (its layouts' root not
// there, it returns before keeping MapAll or Route). As the places wait for
// MapAll (MapPieces.Add), so do the roads: until the screen keeps MapAll, its
// setup hasn't got to its Route; once it has, it keeps its Route right
// after, whatever MapAll holds, so a Route missing then is missing.
//
// (1.34.0) Zodi's choices of 5 November, once measured: a mod's road shown
// "Once both its places show" and "Gray with its places". The game shows each
// of its roads by its own variable (556 + the road) and grays one (Color_
// Grayout: 90, 90, 90 of 255) while it lies ahead on the way to the story's
// objective (WorldMapProgressInfo's roads), not with its places; a game place
// shows by its variable (0x1DF4F0) and grays while its Town row's situation
// holds (the screen's own test, 0x15AEF5); a mod's place always shows, and a
// mod's town grays once its Darkened flag is set (1.20.0). Each road's copy
// is given its look as the screen sets its pieces up and each time it shows a
// place: its opacity 1 once both its places show (0 before, as Hide_R_
// leaves a game road), its color the gray game roads take while either place
// is grayed (Look; a game's animation track writes a box's color and opacity
// as this does, and the box is drawn from them).
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace ModStudioEventSetup
{
    public sealed unsafe class MapRoads
    {
        /// <summary>Where the world map screen keeps its Route piece (which holds the roads' pictures).</summary>
        public const int ScreenRoute = 0x200;
        /// <summary>A box's colour by number (0: its own colour, + 0x64, R, G, B, A), its opacity (a float, which the
        /// game's Show_R_ and Hide_R_ set to 1 and 0); the colour a road is drawn in (white, as Color_Default).</summary>
        public const int BoxColorNumber = 0x60, BoxOpacity = 0x6C;
        public const uint White = 0xFFFFFFFF;
        /// <summary>(1.34.0) The color the game's roads are grayed to (Color_Grayout: 90, 90, 90 of 255, opaque).</summary>
        public const uint Gray = 0xFF5A5A5A;
        /// <summary>(1.34.0) The Town table's number and its rows' situation (Places.TownRow's rows).</summary>
        public const int TownSheet = 0x34, TownSituation = 0x28;
        /// <summary>The names a copy's box takes: this and its road's number among the mods' roads.</summary>
        public const string BoxPrefix = "MsqRoad";
        /// <summary>A road's picture's part in its part list.</summary>
        public const int PicturePart = 1;
        const int TreeDepth = 16, TreeBoxes = 1024;
        const int StringBytes = 16, StringNumber = 8;

        readonly byte* _base;
        readonly Places _places;
        readonly List<MapRoad> _roads;
        /// <summary>The names' strings (16 bytes each, then their characters): each road's box's name and its parts'
        /// name (characters only, made a string when given).</summary>
        readonly nint _names;
        readonly nint[] _boxes, _parts;

        public MapRoads(byte* start, Places places, List<MapRoad> roads)
        {
            _base = start;
            _places = places;
            _roads = roads;
            var all = new List<string>();
            for (int n = 0; n < roads.Count; n++)
            {
                all.Add(BoxPrefix + n);
                all.Add(roads[n].Parts);
            }
            int characters = 0;
            foreach (var name in all)
                characters += name.Length + 1;
            _names = (nint)NativeMemory.AllocZeroed((nuint)(all.Count * StringBytes + characters + 1));
            byte* text = (byte*)_names + all.Count * StringBytes;
            for (int n = 0; n < all.Count; n++)
            {
                *(nint*)(_names + n * StringBytes) = (nint)text;
                foreach (char c in all[n])
                    *text++ = (byte)c;
                *text++ = 0;
            }
            _boxes = new nint[roads.Count];
            _parts = new nint[roads.Count];
            for (int n = 0; n < roads.Count; n++)
            {
                _boxes[n] = _names + 2 * n * StringBytes;
                _parts[n] = *(nint*)(_names + (2 * n + 1) * StringBytes);
            }
        }

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

        /// <summary>The first of the Route piece's road pictures (a picture box in its layers), or 0.</summary>
        public static nint Model(nint tree)
        {
            int seen = 0;
            nint Walk(nint layer, int depth)
            {
                if (depth > TreeDepth)
                    return 0;
                for (nint box = *(nint*)(layer + MapPieces.LayerFirst); box != 0 && seen++ < TreeBoxes;
                     box = *(nint*)(box + MapPieces.BoxNext))
                {
                    int kind = *(int*)(box + Marker.BoxKind);
                    if (kind == Marker.PictureKind && *(nint*)(box + MapPieces.BoxParent) != 0)
                        return box;
                    if (kind == MapPieces.LayerKind)
                    {
                        nint found = Walk(box, depth + 1);
                        if (found != 0)
                            return found;
                    }
                }
                return 0;
            }
            return Walk(tree, 0);
        }

        /// <summary>After the world map screen has set itself up: each mod's road added to it (once: a screen that
        /// already has it is left as it is). Nothing before the screen keeps MapAll (1.4.1: its setup hasn't got
        /// to its Route yet). What happens is said, each line once.</summary>
        public void Add(nint screen, Action<string> say)
        {
            if (screen == 0 || _roads.Count == 0)
                return;
            nint layouts = *(nint*)(screen + Marker.ScreenLayouts);
            nint mapAll = *(nint*)(screen + MapPieces.ScreenMapAll);
            nint route = *(nint*)(screen + ScreenRoute);
            if (layouts == 0 || mapAll == 0)
                return;
            if (route == 0)
            {
                say("the world map has no Route where its roads are: the mods' roads aren't shown.");
                return;
            }
            var boxNamed = (delegate* unmanaged<nint, nint, nint>)(_base + _places.BoxNamed);
            nint model = Model(route + Marker.PieceTree);
            if (model == 0)
            {
                say("the world map has no road piece to copy: the mods' roads aren't shown.");
                return;
            }
            for (int n = 0; n < _roads.Count; n++)
            {
                var road = _roads[n];
                string who = $"{road.Name} ({road.ModName})";
                try
                {
                    if (boxNamed(route + Marker.PieceTree, _boxes[n]) != 0)
                        continue;
                    string? said = AddOne(layouts, model, n, road);
                    say(said == null ? $"{who} is on the world map, its texture at {road.X}, {road.Y}." : $"{who} {said}");
                }
                catch (Exception e)
                {
                    say($"{who} isn't shown on the world map ({e.GetType().Name}: {e.Message}).");
                }
            }
        }

        /// <summary>(1.34.0) A road's look from its places': shown once both show, gray while either is grayed.</summary>
        public static (bool Shown, bool Gray) LookOf((bool Shown, bool Gray) from, (bool Shown, bool Gray) to)
            => (from.Shown && to.Shown, from.Gray || to.Gray);

        /// <summary>(1.34.0) A road's look from its two places' (MapRoads.LookOf).</summary>
        public static (bool Shown, bool Gray) RoadLook(byte* start, Places places, List<MapPlace> mapPlaces,
                                                       Func<MapPlace, bool>? darkened, MapRoad road)
            => LookOf(PlaceLook(start, places, mapPlaces, darkened, road, true),
                               PlaceLook(start, places, mapPlaces, darkened, road, false));

        /// <summary>(1.34.0) One of a road's places, shown and grayed: a game place as the game shows it
        /// (GamePlaceLook); a mod's place always shown, grayed once its Darkened flag is set (`darkened`; none
        /// without it).</summary>
        public static (bool Shown, bool Gray) PlaceLook(byte* start, Places places, List<MapPlace> mapPlaces,
                                                        Func<MapPlace, bool>? darkened, MapRoad road, bool from)
        {
            string name = from ? road.FromName : road.ToName;
            if (name.Length > 0)
            {
                var place = mapPlaces.Find(p => p.ModId == road.ModId && p.Name == name);
                return (true, place != null && darkened != null && darkened(place));
            }
            return GamePlaceLook(start, places, from ? road.FromPlace : road.ToPlace);
        }

        /// <summary>(1.34.0) A game place, shown and grayed: shown by the game's test of a place shown (Places.PlaceTest);
        /// grayed while its Town row's situation holds, as the screen grays it (the row by Places.TownRow, its + 0x28
        /// tested by Places.Situation; none for a row without one).</summary>
        public static (bool Shown, bool Gray) GamePlaceLook(byte* start, Places places, int number)
        {
            var shown = (delegate* unmanaged<nint, int, byte>)(start + places.PlaceTest);
            var row = (delegate* unmanaged<int, int, nint>)(start + places.TownRow);
            var holds = (delegate* unmanaged<nint, int, byte>)(start + places.Situation);
            nint town = row(TownSheet, number);
            int situation = town == 0 ? 0 : *(int*)(town + TownSituation);
            return (shown(0, number) != 0, situation != 0 && holds(0, situation) != 0);
        }

        /// <summary>(1.34.0) Each road's copy on a screen given its look (`look(road)`: shown, gray): its opacity 1 or
        /// 0, its color white or the game's roads' gray. How many copies were found (none before they are added).
        /// </summary>
        public int Look(nint screen, Func<MapRoad, (bool Shown, bool Gray)> look)
        {
            if (screen == 0 || _roads.Count == 0)
                return 0;
            nint route = *(nint*)(screen + ScreenRoute);
            if (route == 0 || *(nint*)(screen + MapPieces.ScreenMapAll) == 0)
                return 0;
            var boxNamed = (delegate* unmanaged<nint, nint, nint>)(_base + _places.BoxNamed);
            int found = 0;
            for (int n = 0; n < _roads.Count; n++)
            {
                nint box = boxNamed(route + Marker.PieceTree, _boxes[n]);
                if (box == 0)
                    continue;
                var (shown, gray) = look(_roads[n]);
                *(float*)(box + BoxOpacity) = shown ? 1f : 0f;
                *(uint*)(box + Marker.BoxColor) = gray ? Gray : White;
                found++;
            }
            return found;
        }

        /// <summary>One road's picture added: null, or what went wrong (after its name).</summary>
        string? AddOne(nint layouts, nint model, int n, MapRoad road)
        {
            var ready = (delegate* unmanaged<nint, nint, byte, byte>)(_base + _places.PartsReady);
            var copy = (delegate* unmanaged<nint, nint, byte, nint>)(_base + _places.PieceCopy);
            var move = (delegate* unmanaged<nint, int, int, void>)(_base + _places.PieceMove);
            var size = (delegate* unmanaged<nint, int, int, void>)(_base + _places.BoxSize);
            var add = (delegate* unmanaged<nint, nint, nint, void>)(_base + _places.PieceAdd);
            if (ready(layouts, _parts[n], 0) == 0)
                return $"isn't shown on the world map: its texture ({road.Picture}) wasn't made ready.";
            nint box = copy(layouts, model, 0);
            if (box == 0)
                return "isn't shown on the world map: its texture's box wasn't made.";
            if (*(int*)(box + Marker.BoxKind) != Marker.PictureKind)
                return "isn't shown on the world map: the box made for it can't show a texture.";
            SetString(box + MapPieces.BoxName, *(nint*)_boxes[n]);
            SetString(box + Marker.PictureParts, _parts[n]);
            *(int*)(box + Marker.PicturePart) = PicturePart;
            *(int*)(box + BoxColorNumber) = 0;
            *(uint*)(box + Marker.BoxColor) = White;
            *(float*)(box + BoxOpacity) = 1f;
            *(byte*)(box + MapPieces.BoxVisible) = 1;
            move(box, road.X, road.Y);
            size(box, road.Width, road.Height);
            add(*(nint*)(model + MapPieces.BoxParent), box, model);
            return null;
        }
    }
}
