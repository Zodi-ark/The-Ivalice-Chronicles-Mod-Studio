// Mod Studio's checks of the helper: (1.4.0) the mods' own roads
// (MapRoads.cs) run against a stand-in for the world map screen: its Route
// piece, its layer LayerRoute and the game's road pictures in it as the game
// lays them out (the first faded out, as his layout's R_24_24_2 is, and
// greyed, its colour by number), linked as the game links a layer's boxes,
// and the game's functions the helper calls (a box by its name, searching a
// piece's layers as they are; a picture's parts made ready; a picture box
// copied, moved, sized, put in a layer; the game's strings made, given and let
// go, each counted by its holders), reached as the helper reaches the game's:
// at their places in an image, here code that jumps to the stand-in's own.
// The roads are a mod's own, as the helper reads them from its folder.
// (1.4.1) A screen keeps MapAll as its setup gets to its pieces, and a
// screen whose setup has kept nothing yet (its first call, before its
// layouts are read, as his test 24 showed) is passed by in silence.
// (1.34.0) Each road's copy given its look as its places give it (Zodi's
// choices of 5 November, "Once both its places show" and "Gray with its
// places": MapRoads.RoadLook, MapRoads.Look), the game's test of a place
// shown, its Town rows and their situations' test stood in for too, each
// step's places shown, grayed and darkened as it says.
// Part of The Ivalice Chronicles Mod Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --roads <report.json> <mod id>=<mod folder>
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using ModStudioEventSetup;

static unsafe class RoadChecks
{
    /// <summary>The game's roads' pictures' parts' name, as the stand-in's road pictures show them.</summary>
    const string RouteParts = "UITextureParts://ui/ffto/worldmap/textureparts/ui_wm_route_all_uitx";
    /// <summary>What the stand-in's image holds for the strings' pool, and the screen for its layouts.</summary>
    const long Pool = 0x5EED0000, Layouts = 0x1A700000;
    const int Next = 0x20, Before = 0x28, X = 0x38, Y = 0x3C, Width = 0x40, Height = 0x44, PartsAt = 0xE8;

    sealed class Text
    {
        public nint Characters;
        public uint Number;
        public int Holders;
        public string Value = "";
    }

    static readonly Dictionary<string, Text> ByValue = new();
    static readonly Dictionary<uint, Text> ByNumber = new();
    static readonly List<string> Calls = new();
    static readonly List<string> Faults = new();
    static readonly HashSet<nint> Layers = new();
    static nint _layerRoute;
    static string _notReady = "";
    static bool _copyFails, _copyNotPicture;
    /// <summary>(1.34.0) The stand-in's game places shown, its Town rows' situations (a place without one has no row),
    /// the situations holding, and the asks of each.</summary>
    static readonly HashSet<int> ShownPlaces = new();
    static readonly Dictionary<int, int> TownSituations = new();
    static readonly HashSet<int> Holding = new();
    static readonly List<string> Asked = new();
    static readonly Dictionary<int, nint> TownRows = new();

    static string Read(nint characters) => characters == 0 ? "" : Marshal.PtrToStringUTF8(characters) ?? "";

    static Text Intern(string value)
    {
        if (!ByValue.TryGetValue(value, out var text))
        {
            var bytes = Encoding.UTF8.GetBytes(value + "\0");
            nint characters = (nint)NativeMemory.AllocZeroed((nuint)bytes.Length);
            Marshal.Copy(bytes, 0, characters, bytes.Length);
            text = new Text { Characters = characters, Number = (uint)(0x100 + ByValue.Count), Value = value };
            ByValue[value] = text;
            ByNumber[text.Number] = text;
        }
        return text;
    }

    static void Hold(nint into, string value)
    {
        var text = Intern(value);
        text.Holders++;
        *(nint*)into = text.Characters;
        *(uint*)(into + 8) = text.Number;
    }

    static void LetGo(uint number)
    {
        if (!ByNumber.TryGetValue(number, out var text))
            Faults.Add($"a string numbered {number} let go, which was never made");
        else if (--text.Holders < 0)
            Faults.Add($"{text.Value} let go more often than it was held");
    }

    static string NameOf(nint box) => Read(*(nint*)(box + MapPieces.BoxName));

    static int Holders(string value) => ByValue.TryGetValue(value, out var text) ? text.Holders : 0;

    /// <summary>A box by its name in a layer as the game searches one: each box in turn, a layer's boxes too.</summary>
    static nint Search(nint layer, string name)
    {
        for (nint box = *(nint*)(layer + MapPieces.LayerFirst); box != 0; box = *(nint*)(box + Next))
        {
            if (NameOf(box) == name)
                return box;
            if (*(int*)(box + Marker.BoxKind) == MapPieces.LayerKind)
            {
                nint found = Search(box, name);
                if (found != 0)
                    return found;
            }
        }
        return 0;
    }

    // --- The game's functions, as the stand-in has them ---------------------------

    [UnmanagedCallersOnly]
    static nint BoxNamed(nint tree, nint name)
    {
        try
        {
            if (*(uint*)(name + 8) != 0)
                Faults.Add($"{Read(*(nint*)name)} looked for by a string's number, not its characters");
            return Search(tree, Read(*(nint*)name));
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
            return 0;
        }
    }

    [UnmanagedCallersOnly]
    static byte PartsReady(nint layouts, nint url, byte flags)
    {
        try
        {
            Calls.Add($"ready {(layouts == (nint)Layouts ? "the screen's layouts" : $"{layouts:X}")} {Read(url)} {flags}");
            return (byte)(Read(url) == _notReady ? 0 : 1);
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
            return 0;
        }
    }

    [UnmanagedCallersOnly]
    static nint StringMake(nint into, nint characters)
    {
        try
        {
            Hold(into, Read(characters));
            Calls.Add($"make {Read(characters)}");
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
        }
        return into;
    }

    [UnmanagedCallersOnly]
    static nint StringAssign(nint into, nint from)
    {
        try
        {
            uint number = *(uint*)(from + 8), old = *(uint*)(into + 8);
            if (number != 0)
                ByNumber[number].Holders++;
            if (old != 0)
                LetGo(old);
            *(nint*)into = *(nint*)from;
            *(uint*)(into + 8) = number;
            Calls.Add($"give {Read(*(nint*)from)}");
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
        }
        return into;
    }

    [UnmanagedCallersOnly]
    static int StringRelease(nint pool, uint number)
    {
        try
        {
            if (pool != (nint)Pool)
                Faults.Add($"a string let go into {pool:X}, not the strings' pool");
            LetGo(number);
            Calls.Add($"let go {(ByNumber.TryGetValue(number, out var text) ? text.Value : number.ToString())}");
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
        }
        return 0;
    }

    /// <summary>A box copied as the game copies a picture box: a new box of its kind, its fields copied (its name's
    /// and its parts' strings held again), in no layer yet.</summary>
    [UnmanagedCallersOnly]
    static nint PieceCopy(nint layouts, nint box, byte tracks)
    {
        try
        {
            Calls.Add($"copy {NameOf(box)} {tracks}");
            if (layouts != (nint)Layouts)
                Faults.Add($"a box copied into {layouts:X}, not the screen's layouts");
            if (_copyFails)
                return 0;
            nint copy = Block();
            Hold(copy + MapPieces.BoxName, NameOf(box));
            *(int*)(copy + Marker.BoxKind) = _copyNotPicture ? MapPieces.LayerKind : *(int*)(box + Marker.BoxKind);
            foreach (int at in new[] { X, Y, Width, Height, MapRoads.BoxColorNumber, Marker.BoxColor,
                                       MapRoads.BoxOpacity, Marker.PicturePart })
                *(int*)(copy + at) = *(int*)(box + at);
            *(byte*)(copy + MapPieces.BoxVisible) = *(byte*)(box + MapPieces.BoxVisible);
            Hold(copy + PartsAt, Read(*(nint*)(box + PartsAt)));
            return copy;
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
            return 0;
        }
    }

    [UnmanagedCallersOnly]
    static void PieceMove(nint box, int x, int y)
    {
        try
        {
            Calls.Add($"move {NameOf(box)} {x} {y}");
            *(int*)(box + X) = x;
            *(int*)(box + Y) = y;
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
        }
    }

    [UnmanagedCallersOnly]
    static void BoxSize(nint box, int width, int height)
    {
        try
        {
            Calls.Add($"size {NameOf(box)} {width} {height}");
            *(int*)(box + Width) = width;
            *(int*)(box + Height) = height;
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
        }
    }

    /// <summary>A box put in a layer as the game puts one: after the box given, or first.</summary>
    [UnmanagedCallersOnly]
    static void PieceAdd(nint layer, nint box, nint after)
    {
        try
        {
            Calls.Add($"add {NameOf(box)} to {NameOf(layer)} after {(after == 0 ? "none" : NameOf(after))}");
            if (!Layers.Contains(layer))
                Faults.Add($"{NameOf(box)} put in {NameOf(layer)}, which isn't a layer");
            if (after != 0 && *(nint*)(after + MapPieces.BoxParent) != layer)
                Faults.Add($"{NameOf(box)} put after a box not in the layer");
            *(nint*)(box + MapPieces.BoxParent) = layer;
            if (after != 0)
            {
                nint next = *(nint*)(after + Next);
                *(nint*)(box + Next) = next;
                if (next != 0)
                    *(nint*)(next + Before) = box;
                *(nint*)(box + Before) = after;
                *(nint*)(after + Next) = box;
            }
            else
            {
                nint first = *(nint*)(layer + MapPieces.LayerFirst);
                *(nint*)(box + Next) = first;
                if (first != 0)
                    *(nint*)(first + Before) = box;
                *(nint*)(layer + MapPieces.LayerFirst) = box;
            }
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
        }
    }

    /// <summary>(1.34.0) The game's test of a place shown: the stand-in's places shown.</summary>
    [UnmanagedCallersOnly]
    static byte PlaceShownStandIn(nint unused, int place)
    {
        Asked.Add($"shown {place}");
        return (byte)(ShownPlaces.Contains(place) ? 1 : 0);
    }

    /// <summary>(1.34.0) A row by its table and key, as the game's: the Town table's row of a place with a situation
    /// (+ 0x28), none for another place or table.</summary>
    [UnmanagedCallersOnly]
    static nint TownRowStandIn(int sheet, int key)
    {
        Asked.Add($"row {sheet:X} {key}");
        if (sheet != MapRoads.TownSheet)
        {
            Faults.Add($"a row of table {sheet:X} asked for, not the Town table's");
            return 0;
        }
        if (!TownSituations.TryGetValue(key, out int situation))
            return 0;
        if (!TownRows.TryGetValue(key, out nint row))
            TownRows[key] = row = Block(0x40);
        *(int*)(row + MapRoads.TownSituation) = situation;
        return row;
    }

    /// <summary>(1.34.0) Whether a situation holds: the stand-in's holding ones; never asked of none (0).</summary>
    [UnmanagedCallersOnly]
    static byte SituationStandIn(nint unused, int situation)
    {
        Asked.Add($"holds {situation}");
        if (situation == 0)
            Faults.Add("situation 0 asked of, which the game never asks");
        return (byte)(Holding.Contains(situation) ? 1 : 0);
    }

    // --- The stand-in ----------------------------------------------------------------

    static byte* Image(Places places)
    {
        nint libc = NativeLibrary.Load("libc.so.6");
        var map = (delegate* unmanaged<nint, nuint, int, int, int, nint, nint>)NativeLibrary.GetExport(libc, "mmap");
        var protect = (delegate* unmanaged<nint, nuint, int, int>)NativeLibrary.GetExport(libc, "mprotect");
        nint block = map(0, 4096, 3, 0x22, -1, 0);
        if (block == -1)
            throw new InvalidOperationException("no memory for the stand-in's image");
        byte* image = (byte*)block;
        delegate* unmanaged<nint, nint, nint> box = &BoxNamed, make = &StringMake, assign = &StringAssign;
        delegate* unmanaged<nint, nint, byte, byte> ready = &PartsReady;
        delegate* unmanaged<nint, uint, int> release = &StringRelease;
        delegate* unmanaged<nint, nint, byte, nint> copy = &PieceCopy;
        delegate* unmanaged<nint, int, int, void> move = &PieceMove, size = &BoxSize;
        delegate* unmanaged<nint, nint, nint, void> add = &PieceAdd;
        delegate* unmanaged<nint, int, byte> placeShown = &PlaceShownStandIn, situation = &SituationStandIn;
        delegate* unmanaged<int, int, nint> townRow = &TownRowStandIn;
        var functions = new (string Name, nint Function)[]
        {
            ("BoxNamed", (nint)box), ("PartsReady", (nint)ready), ("StringMake", (nint)make),
            ("StringAssign", (nint)assign), ("StringRelease", (nint)release), ("PieceCopy", (nint)copy),
            ("PieceMove", (nint)move), ("BoxSize", (nint)size), ("PieceAdd", (nint)add),
            ("PlaceTest", (nint)placeShown), ("TownRow", (nint)townRow), ("Situation", (nint)situation),
        };
        for (int n = 0; n < functions.Length; n++)
        {
            byte* at = image + 0x10 * n;
            at[0] = 0xFF;
            at[1] = 0x25;
            at[2] = at[3] = at[4] = at[5] = 0;
            *(long*)(at + 6) = functions[n].Function;
            typeof(Places).GetProperty(functions[n].Name)!.SetValue(places, 0x10 * n);
        }
        *(long*)(image + 0x100) = Pool;
        typeof(Places).GetProperty("StringPool")!.SetValue(places, 0x100);
        if (protect(block, 4096, 5) != 0)
            throw new InvalidOperationException("the stand-in's image can't be run");
        return image;
    }

    static nint Block(int size = 0x200) => (nint)NativeMemory.AllocZeroed((nuint)size);

    static nint Layer(nint into, string name)
    {
        nint layer = Block();
        Hold(layer + MapPieces.BoxName, name);
        *(int*)(layer + Marker.BoxKind) = MapPieces.LayerKind;
        *(byte*)(layer + MapPieces.BoxVisible) = 1;
        Layers.Add(layer);
        Append(into, layer);
        return layer;
    }

    static void Append(nint layer, nint box)
    {
        *(nint*)(box + MapPieces.BoxParent) = layer;
        nint at = layer + MapPieces.LayerFirst;
        nint before = 0;
        while (*(nint*)at != 0)
        {
            before = *(nint*)at;
            at = before + Next;
        }
        *(nint*)at = box;
        *(nint*)(box + Before) = before;
    }

    /// <summary>A road picture of the game's: its name, a part of the roads' texture, where it is, its size; faded
    /// out and greyed (by number) as a road not yet shown is, or white and shown.</summary>
    static void GameRoad(nint layer, string name, int part, int x, int y, int width, int height, bool faded)
    {
        nint box = Block();
        Hold(box + MapPieces.BoxName, name);
        *(int*)(box + Marker.BoxKind) = Marker.PictureKind;
        *(int*)(box + X) = x;
        *(int*)(box + Y) = y;
        *(int*)(box + Width) = width;
        *(int*)(box + Height) = height;
        Hold(box + PartsAt, RouteParts);
        *(int*)(box + Marker.PicturePart) = part;
        *(int*)(box + MapRoads.BoxColorNumber) = faded ? 7 : 0;
        *(uint*)(box + Marker.BoxColor) = faded ? 0xFF5A5A5Au : MapRoads.White;
        *(float*)(box + MapRoads.BoxOpacity) = faded ? 0f : 1f;
        *(byte*)(box + MapPieces.BoxVisible) = (byte)(faded ? 0 : 1);
        Append(layer, box);
    }

    /// <summary>A screen as the game sets one up: its layouts, MapAll, its Route piece (its root layer, LayerRoute,
    /// and in it two road pictures of the game's, the first faded out), or a Route deeper, or with no picture, or
    /// no Route; or (1.4.1) a screen whose setup has kept nothing yet (its first call, before its layouts are read,
    /// as his test 24 showed): its layouts alone.</summary>
    static nint Screen(bool route = true, bool deeper = false, bool pictures = true, bool kept = true)
    {
        nint screen = Block(0x2000);
        *(nint*)(screen + Marker.ScreenLayouts) = (nint)Layouts;
        if (!kept)
            return screen;
        *(nint*)(screen + MapPieces.ScreenMapAll) = Block(0x400);
        if (!route)
            return screen;
        nint piece = Block(0x400);
        *(nint*)(screen + MapRoads.ScreenRoute) = piece;
        nint root = piece + Marker.PieceTree;
        Layers.Add(root);
        Hold(root + MapPieces.BoxName, "Route");
        _layerRoute = Layer(root, "LayerRoute");
        if (deeper)
            _layerRoute = Layer(_layerRoute, "LayerInner");
        if (pictures)
        {
            GameRoad(_layerRoute, "R_24_24_2", 52, 1933, 687, 100, 66, true);
            GameRoad(_layerRoute, "R_01_02", 1, 750, 1036, 220, 90, false);
        }
        return screen;
    }

    /// <summary>The layer as it is: each box's name (whether its string is the name's own), where it is, its size,
    /// its parts' name and part (whether that string is its own), its colour by number, its colour, opacity and
    /// whether it is seen.</summary>
    static List<object?[]> Look()
    {
        var boxes = new List<object?[]>();
        for (nint box = *(nint*)(_layerRoute + MapPieces.LayerFirst); box != 0; box = *(nint*)(box + Next))
        {
            string name = NameOf(box), parts = Read(*(nint*)(box + PartsAt));
            boxes.Add(new object?[]
            {
                name, ByValue.TryGetValue(name, out var named) && named.Number == *(uint*)(box + MapPieces.BoxName + 8),
                *(int*)(box + X), *(int*)(box + Y), *(int*)(box + Width), *(int*)(box + Height), parts,
                ByValue.TryGetValue(parts, out var own) && own.Number == *(uint*)(box + PartsAt + 8),
                *(int*)(box + Marker.PicturePart), *(int*)(box + MapRoads.BoxColorNumber),
                $"{*(uint*)(box + Marker.BoxColor):X8}", *(float*)(box + MapRoads.BoxOpacity),
                *(byte*)(box + MapPieces.BoxVisible), *(nint*)(box + MapPieces.BoxParent) == _layerRoute,
            });
        }
        return boxes;
    }

    public static int Run(string[] args)
    {
        int split = args[2].IndexOf('=');
        string id = args[2].Substring(0, split), folder = args[2].Substring(split + 1);
        var problems = new List<string>();
        var own = PlaceFile.ReadMod(id, id, folder, problems);
        var roads = RoadFile.ReadMod(id, id, folder, own.ConvertAll(p => p.Name), problems);
        var places = new Places();
        byte* image = Image(places);
        var steps = new List<Dictionary<string, object?>>();
        var said = new List<string>();
        var names = new List<string>();
        for (int n = 0; n < roads.Count; n++)
            names.Add(MapRoads.BoxPrefix + n);

        void Step(string name, MapRoads drawn, nint screen)
        {
            Calls.Clear();
            said.Clear();
            drawn.Add(screen, said.Add);
            var held = new Dictionary<string, int> { ["R_24_24_2"] = Holders("R_24_24_2"),
                                                     ["R_01_02"] = Holders("R_01_02"), ["route"] = Holders(RouteParts) };
            foreach (var road in names)
                held[road] = Holders(road);
            foreach (var road in roads)
                held[road.Picture] = Holders(road.Parts);
            steps.Add(new Dictionary<string, object?>
            {
                ["step"] = name, ["said"] = new List<string>(said), ["calls"] = new List<string>(Calls),
                ["layer"] = screen != 0 && *(nint*)(screen + MapRoads.ScreenRoute) != 0 ? Look() : null,
                ["held"] = held,
            });
        }

        var drawn = new MapRoads(image, places, roads);
        nint screen = Screen();
        Step("a screen set up: the roads added", drawn, screen);
        Step("the same screen set up again: nothing added", drawn, screen);
        Step("a new screen: the roads added again", drawn, Screen());
        _notReady = roads.Count > 0 ? roads[0].Parts : "";
        Step("a new screen, the first road's picture not made ready: the others added", drawn, Screen());
        _notReady = "";
        _copyFails = true;
        Step("a new screen whose copies fail", drawn, Screen());
        _copyFails = false;
        _copyNotPicture = true;
        Step("a new screen whose copies aren't pictures", drawn, Screen());
        _copyNotPicture = false;
        Step("a new screen whose road pictures are a layer deeper", drawn, Screen(deeper: true));
        Step("a new screen whose Route has no picture", drawn, Screen(pictures: false));
        Step("a new screen without its Route", drawn, Screen(route: false));
        Step("a new screen its setup has kept nothing of yet: nothing said, nothing added", drawn,
             Screen(kept: false));
        nint gone = Screen();
        *(nint*)(gone + Marker.ScreenLayouts) = 0;
        Step("a screen without its layouts: nothing", drawn, gone);
        Step("no screen", drawn, 0);

        // (1.34.0) The roads' looks: a screen with the roads added, each step's places shown, grayed and darkened as
        // it says (the game's places 0 to 46 but 20 and 43 shown, each with a situation of its own, none holding,
        // unless it says otherwise), the roads looked at as the place hooks look at them.
        var looks = new List<Dictionary<string, object?>>();
        nint lookScreen = Screen();
        drawn.Add(lookScreen, _ => { });
        int firstGame = roads.Count > 0 ? (roads[0].FromName.Length == 0 ? roads[0].FromPlace : roads[0].ToPlace) : -1;
        int secondGame = roads.Count > 1 ? (roads[1].FromName.Length == 0 ? roads[1].FromPlace : roads[1].ToPlace) : -1;
        string firstMod = roads.Count > 2 ? (roads[2].FromName.Length > 0 ? roads[2].FromName : roads[2].ToName) : "";

        void Places(bool everyRow = true)
        {
            ShownPlaces.Clear();
            TownSituations.Clear();
            Holding.Clear();
            for (int n = 0; n <= 46; n++)
                if (n != 20 && n != 43)
                {
                    ShownPlaces.Add(n);
                    if (everyRow || n != firstGame)
                        TownSituations[n] = 1000 + n;
                }
        }

        void LookStep(string name, nint screen, Func<MapPlace, bool>? darkened)
        {
            Asked.Clear();
            int found = drawn.Look(screen, road => MapRoads.RoadLook(image, places, own, darkened, road));
            looks.Add(new Dictionary<string, object?>
            {
                ["step"] = name, ["found"] = found,
                ["roads"] = roads.ConvertAll(r =>
                {
                    var (shown, gray) = MapRoads.RoadLook(image, places, own, darkened, r);
                    return new object[] { shown, gray };
                }),
                ["layer"] = screen != 0 && *(nint*)(screen + MapRoads.ScreenRoute) != 0 ? Look() : null,
                ["asked"] = new List<string>(Asked),
            });
        }
        Places();
        LookStep("every place shown, none grayed or darkened", lookScreen, null);
        Places();
        ShownPlaces.Remove(firstGame);
        LookStep("the first road's game place not shown: it hides", lookScreen, null);
        Places();
        Holding.Add(1000 + secondGame);
        LookStep("the second road's game place grayed (its Town row's situation holds): it grays", lookScreen, null);
        Places();
        LookStep("the third road's place of the mod's darkened: it grays", lookScreen, p => p.Name == firstMod);
        Places(everyRow: false);
        ShownPlaces.Remove(secondGame);
        Holding.Add(1000 + firstGame);
        LookStep("the first road's game place without a Town row (its situation not asked), the second's hidden: the "
                 + "first shown white, the second hidden", lookScreen, null);
        Places();
        LookStep("every place shown again: every road shown white again", lookScreen, null);
        LookStep("a screen the roads weren't added to: none found", Screen(), null);
        LookStep("no screen: none found", 0, null);
        var lookOf = new List<object[]>();
        foreach (bool fromShown in new[] { false, true })
            foreach (bool fromGray in new[] { false, true })
                foreach (bool toShown in new[] { false, true })
                    foreach (bool toGray in new[] { false, true })
                    {
                        var (shown, gray) = MapRoads.LookOf((fromShown, fromGray), (toShown, toGray));
                        lookOf.Add(new object[] { fromShown, fromGray, toShown, toGray, shown, gray });
                    }
        var report = new Dictionary<string, object?>
        {
            ["steps"] = steps, ["faults"] = Faults, ["problems"] = problems, ["routeParts"] = RouteParts,
            ["roads"] = roads.ConvertAll(r => new object[] { r.Name, r.Picture, r.Parts, r.X, r.Y, r.Width, r.Height }),
            ["roadPlaces"] = roads.ConvertAll(r => new object[] { r.FromPlace, r.FromName, r.ToPlace, r.ToName }),
            ["looks"] = looks, ["lookOf"] = lookOf, ["gray"] = $"{MapRoads.Gray:X8}",
        };
        File.WriteAllText(args[1], JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
        return 0;
    }
}
