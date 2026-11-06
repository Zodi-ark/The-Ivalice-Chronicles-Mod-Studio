// Mod Studio Framework: (1.3.0) the mods' own places joined to the running
// game, through Reloaded-II's shared hooks. Part of The Ivalice Chronicles
// Mod Studio, GPL-3.0.
//
// Made only when some mod gives a place of its own (PlaceFile.cs) or, since
// 1.4.0, a road (RoadFile.cs), apart from the side quests' hooks (Hooks.cs):
// one hook, of the world map screen's setup of its places' pieces
// (Places.MapSetup), which runs the game's own setup first, whole, then adds
// the mods' places' pieces to the screen (MapPieces.Add) and their roads'
// pictures (MapRoads.Add), each apart. Nothing here throws into the game: a
// fault is said once.
//
// (1.5.0) And, when some mod's road joins two of the game's places
// (Travel.cs), the tables' setup (Places.SheetInit), as the side quests'
// hooks have it: Route and MapRouteTable are given a copy of the file they
// loaded with the roads' rows before the game reads them (TravelTables);
// while both have, the ready byte the path search's answer reads (Travel.cs's
// WaysInGame) is set, and the search may take the mods' roads.
//
// (1.7.0) With the mods' places the game goes to (Destinations.cs), the same
// hook of the tables' setup gives Town and PlaceName their rows, and one more
// hook, of the screen's switch of its places' collision boxes
// (Places.CollisionSwitch), does the same for the mods' places' pieces after
// the game's own (MapPieces.Switched).
//
// (1.19.0) With a mod's town with a menu of its own and its own art or its own
// picture (MenuArt.cs): the base art's path, for its own art's number, and the
// menu's town picture, for its own picture.
//
// (1.20.0) A mod's town darkened once a quest's flag is set: Darken, which
// the side quests' hooks ask (Hooks.ModDarkened) once the quests are planned.
//
// (1.34.0) A mod's road shown once both its places show and grayed while
// either is (Zodi's choices of 5 November): LookRoads, as the screen sets its
// pieces up and each time it shows a place (Places.MarkerState, hooked here
// too: the story draws a place while the world map is up by it); a game
// place by the game's own tests (MapRoads.GamePlaceLook), a mod's town by its
// Darkened flag (Darkened, from the side quests' hooks).
using System;
using System.Collections.Generic;
using Reloaded.Hooks.Definitions;
using Reloaded.Hooks.Definitions.X64;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    public sealed unsafe class PlaceHooks
    {
        /// <summary>The world map screen's setup of its places' pieces: the screen.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate void MapSetupFunction(nint screen);

        /// <summary>(1.5.0) The tables' setup (the table, its file).</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate int SheetInitFunction(nint sheet, nint file);

        /// <summary>(1.7.0) The screen's switch of its places' collision boxes (the screen, on or off, which of its two
        /// reasons).</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate void CollisionSwitchFunction(nint screen, byte off, int reason);

        /// <summary>(1.19.0) The base art's path (its buffer, the art's number, the buffer's size).</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate int BaseArtFunction(nint buffer, int number, int size);

        /// <summary>(1.19.0) The menu's town picture (-, the piece, the place, its Town row).</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate void MenuIconFunction(nint unused, nint piece, int place, nint row);

        /// <summary>(1.34.0) The world map screen's showing of a place (the screen, the place's state, the place), which
        /// the side quests' markers hook too (Hooks.MarkerState).</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate void PlaceShowFunction(nint screen, nint state, int place);

        readonly MapPieces? _pieces;
        readonly MapRoads? _roads;
        readonly Action<string> _say;
        /// <summary>(1.34.0) The program, where its places are, the mods' places, and whether the roads' looks can be
        /// given (Places.RoadLooks).</summary>
        readonly byte* _start;
        readonly Places _places;
        readonly List<MapPlace> _mapPlaces;
        readonly bool _looks;
        /// <summary>(1.34.0) Whether a mod's town is darkened now (its Darkened flag set), from the side quests' hooks once
        /// the quests are planned; null: none is.</summary>
        public Func<MapPlace, bool>? Darkened { get; set; }
        readonly object _lock = new object();
        readonly HashSet<string> _saidOnce = new HashSet<string>();
        IHook<MapSetupFunction>? _setup;
        /// <summary>(1.5.0) The tables' hook, and what it gives Route and MapRouteTable (Travel.cs's TravelTables).</summary>
        IHook<SheetInitFunction>? _sheetInit;
        TravelTables? _tables;
        /// <summary>(1.7.0) The switch's hook, with the mods' places the game goes to.</summary>
        IHook<CollisionSwitchFunction>? _switch;
        /// <summary>(1.19.0) A town's own art and own picture in its menu, and their hooks.</summary>
        MenuArt? _menuArt;
        IHook<BaseArtFunction>? _baseArt;
        IHook<MenuIconFunction>? _menuIcon;
        /// <summary>(1.34.0) The screen's showing of a place, hooked when the mods' roads are given their looks.</summary>
        IHook<PlaceShowFunction>? _placeShow;
        /// <summary>(1.8.0) What follows the mods' places' pieces added to a screen: the side quests' markers at
        /// those places shown (Hooks.ModMarkers), set once the quests are planned.</summary>
        public Action<nint>? PiecesAdded { get; set; }

        PlaceHooks(MapPieces? pieces, MapRoads? roads, Action<string> say, byte* start, Places places,
                   List<MapPlace> mapPlaces)
        {
            _pieces = pieces;
            _roads = roads;
            _say = say;
            _start = start;
            _places = places;
            _mapPlaces = mapPlaces;
            _looks = places.RoadLooks;
        }

        /// <summary>The places' and roads' hook, made and active (before the game runs); (1.5.0) with roads the game
        /// travels, the tables' hook too, `ready` the byte it sets once Route and MapRouteTable have their rows; (1.7.0)
        /// with places the game goes to (the program given them: Destinations.Arm), the tables' hook for their rows and
        /// the switch's hook.</summary>
        public static PlaceHooks Make(IReloadedHooks reloaded, byte* start, Places places, Action<string> say,
                                      List<MapPlace> mapPlaces, List<MapRoad> mapRoads, List<TravelRoad>? travel = null,
                                      nint ready = 0, List<Destination>? destinations = null)
        {
            destinations ??= new List<Destination>();
            var hooks = new PlaceHooks(mapPlaces.Count > 0 ? new MapPieces(start, places, mapPlaces, destinations) : null,
                                       mapRoads.Count > 0 ? new MapRoads(start, places, mapRoads) : null, say, start,
                                       places, mapPlaces);
            // (1.34.0) The mods' roads shown and grayed with their places, once the game's tests of a place are found.
            if (mapRoads.Count > 0 && !places.RoadLooks)
                say("the mods' roads are shown whatever their places do: "
                    + $"{string.Join(", ", places.MissingForRoadLooks)} wasn't found. A game update may have changed it: "
                    + "look for a newer Mod Studio Framework.");
            if (mapPlaces.Count > 0 || mapRoads.Count > 0)
            {
                hooks._setup = reloaded.CreateHook<MapSetupFunction>(hooks.MapSetup, (long)(nint)start + places.MapSetup, -1);
                hooks._setup.Activate();
            }
            // (1.34.0) And each time the screen shows a place (one the story draws while the world map is up too).
            if (hooks._setup != null && hooks._roads != null && places.RoadLooks)
            {
                hooks._placeShow = reloaded.CreateHook<PlaceShowFunction>(hooks.PlaceShow,
                                                                         (long)(nint)start + places.MarkerState, -1);
                hooks._placeShow.Activate();
            }
            bool roads = travel != null && travel.Count > 0 && ready != 0;
            if (roads || destinations.Count > 0)
            {
                hooks._tables = new TravelTables(roads ? travel! : new List<TravelRoad>(), roads ? ready : 0,
                                                 hooks.SayOnce, destinations);
                hooks._sheetInit = reloaded.CreateHook<SheetInitFunction>(hooks.SheetInit,
                                                                          (long)(nint)start + places.SheetInit, -1);
                hooks._sheetInit.Activate();
            }
            if (destinations.Count > 0 && hooks._pieces != null)
            {
                hooks._switch = reloaded.CreateHook<CollisionSwitchFunction>(hooks.CollisionSwitch,
                                                                             (long)(nint)start + places.CollisionSwitch, -1);
                hooks._switch.Activate();
            }
            // (1.19.0) A town's own art and own picture in its menu.
            var art = new MenuArt(start, places, destinations);
            if (art.HasArts || art.HasIcons)
            {
                if (!places.MenuArt || !places.NewPlaces)
                    say("the mods' towns' own art and textures aren't shown in their menus: "
                        + $"{string.Join(", ", places.MenuArt ? places.MissingForPlaces : places.MissingForMenuArt)} "
                        + "wasn't found. A game update may have changed it: look for a newer Mod Studio Framework.");
                else
                {
                    hooks._menuArt = art;
                    if (art.HasArts)
                    {
                        hooks._baseArt = reloaded.CreateHook<BaseArtFunction>(hooks.BaseArt,
                                                                             (long)(nint)start + places.BaseArt, -1);
                        hooks._baseArt.Activate();
                    }
                    if (art.HasIcons)
                    {
                        hooks._menuIcon = reloaded.CreateHook<MenuIconFunction>(hooks.MenuIcon,
                                                                               (long)(nint)start + places.MenuIcon, -1);
                        hooks._menuIcon.Activate();
                    }
                }
            }
            return hooks;
        }

        /// <summary>(1.19.0) The base art's path: a town's own art's (its number OwnArt plus its place's), else the
        /// game's own.</summary>
        int BaseArt(nint buffer, int number, int size)
        {
            try
            {
                int written = _menuArt!.WriteArt(buffer, number, size);
                if (written >= 0)
                    return written;
            }
            catch (Exception e)
            {
                SayOnce($"a town's own art wasn't given its path ({e.GetType().Name}: {e.Message}).");
            }
            return _baseArt!.OriginalFunction(buffer, number, size);
        }

        /// <summary>(1.19.0) The menu's town picture: a town's own picture given the menu's picture box, else (its box
        /// given back first, if a town's own was given it) the game's own TexChange.</summary>
        void MenuIcon(nint unused, nint piece, int place, nint row)
        {
            try
            {
                if (_menuArt!.GiveIcon(piece, place))
                    return;
                _menuArt.GiveBack(piece);
            }
            catch (Exception e)
            {
                SayOnce($"a town's own texture wasn't shown in its menu ({e.GetType().Name}: {e.Message}).");
            }
            _menuIcon!.OriginalFunction(unused, piece, place, row);
        }

        /// <summary>(1.7.0) The screen's switch of its places' collision boxes: the game's own, then the same for the
        /// mods' places' pieces.</summary>
        void CollisionSwitch(nint screen, byte off, int reason)
        {
            _switch!.OriginalFunction(screen, off, reason);
            try
            {
                _pieces?.Switched(screen);
            }
            catch (Exception e)
            {
                SayOnce($"the mods' places' boxes weren't switched with the game's ({e.GetType().Name}: {e.Message}).");
            }
        }

        /// <summary>(1.5.0) A table set up: Route and MapRouteTable given the roads' rows first.</summary>
        int SheetInit(nint sheet, nint file)
        {
            _tables?.Give(sheet, file);
            return _sheetInit!.OriginalFunction(sheet, file);
        }

        void SayOnce(string line)
        {
            lock (_lock)
                if (!_saidOnce.Add(line))
                    return;
            _say(line);
        }

        /// <summary>(1.20.0) A mod's town darkened or not on a screen (MapPieces.Darken), a fault said once, never
        /// thrown: whether its copy was found.</summary>
        public bool Darken(nint screen, MapPlace place, bool dark)
        {
            try
            {
                return _pieces != null && _pieces.Darken(screen, place, dark);
            }
            catch (Exception e)
            {
                SayOnce($"{place.Name} ({place.ModName}) wasn't darkened ({e.GetType().Name}: {e.Message}).");
                return false;
            }
        }

        /// <summary>The world map screen sets its places' pieces up: the game's own setup, whole, then the mods'
        /// places' pieces added, then (1.4.0) their roads' pictures.</summary>
        void MapSetup(nint screen)
        {
            if (_setup == null)
                return;
            _setup!.OriginalFunction(screen);
            if (_pieces != null)
                try
                {
                    _pieces.Add(screen, SayOnce);
                    PiecesAdded?.Invoke(screen);
                }
                catch (Exception e)
                {
                    SayOnce($"the mods' places weren't added to the world map ({e.GetType().Name}: {e.Message}).");
                }
            if (_roads != null)
                try
                {
                    _roads.Add(screen, SayOnce);
                }
                catch (Exception e)
                {
                    SayOnce($"the mods' roads weren't added to the world map ({e.GetType().Name}: {e.Message}).");
                }
            // (1.34.0) And shown and grayed with their places.
            LookRoads(screen);
        }

        /// <summary>(1.34.0) The screen shows a place: the game's own showing (the side quests' markers' with it, when
        /// they hook it too), then the mods' roads given their looks.</summary>
        void PlaceShow(nint screen, nint state, int place)
        {
            _placeShow!.OriginalFunction(screen, state, place);
            LookRoads(screen);
        }

        /// <summary>(1.34.0) Each mod's road on a screen shown once both its places show and grayed while either is
        /// (MapRoads.Look); nothing when the game's tests of a place weren't found. A fault said once.</summary>
        public void LookRoads(nint screen)
        {
            if (_roads == null || !_looks || screen == 0)
                return;
            try
            {
                _roads.Look(screen, road => MapRoads.RoadLook(_start, _places, _mapPlaces, Darkened, road));
            }
            catch (Exception e)
            {
                SayOnce($"the mods' roads weren't shown with their places ({e.GetType().Name}: {e.Message}).");
            }
        }

    }
}
