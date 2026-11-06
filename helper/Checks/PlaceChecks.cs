// Mod Studio's checks of the helper: (1.3.0) the mods' own places
// (MapPieces.cs) run against a stand-in for the world map screen: its
// places' pieces (a town's, Base01, its picture Image01 and its markers; a
// battle ground's, Point02) in their layer under Bases as the game lays them
// out, and the game's functions the helper calls (a piece's child by its
// name, a box by its name, searching a layer's boxes by their names as they
// are; a picture's parts made ready; a box copied, moved, put in a layer;
// animations played and stopped; the game's strings made, given and let go,
// each counted by its holders), reached as the helper reaches the game's:
// at their places in an image, here code that jumps to the stand-in's own.
// (1.3.1) Each piece also has the tag the screen gives its places' pieces
// and its boxes' tree as the layout has it (layers, collision boxes, a
// picture, references naming the pieces they place), which the copy copies
// as the game's does, so the report shows a copy's tag and collision boxes.
// (1.7.0) Each piece also has its label (TextBoardMapName, its Title a text
// box showing a message's text, as the layout leaves it), copied with it; and
// the places given numbers past the game's 48 (Destinations.cs) are added to
// a screen with room for their rows past its end: their rows, labels, tags and
// collision boxes, and the screen's switch of its places' collision boxes
// mirrored for them (the game's box of a kind and its refresh stood in for).
// Part of The Ivalice Chronicles Mod Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --places <report.json>
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using ModStudioEventSetup;

static unsafe class PlaceChecks
{
    /// <summary>The game's town pictures' parts' name, as the stand-in's Base01 shows them.</summary>
    const string IconParts = "UITextureParts://ui/ffto/worldmap/textureparts/ui_wm_icon_base_uitx";
    /// <summary>What the stand-in's image holds for the strings' pool, and the screen for its layouts.</summary>
    const long Pool = 0x5EED0000, Layouts = 0x1A700000;
    /// <summary>The stand-in's places: Gariland a town (place 1), Mandalia Plains a battle ground (place 2), at
    /// their places in the game's layout.</summary>
    const int Town = 1, Battle = 2;
    static readonly string[] Markers = { "Quest", "Next", "MidwayPoint", "IconJob" };
    /// <summary>Test 22's places (dev/research/sidequests/make_test22.py): a town with its own picture, a town with
    /// a game's picture, a battle ground.</summary>
    static readonly List<MapPlace> Given = new()
    {
        new MapPlace("modstudio.test22.places", "Test 22 New Places", "1 Hidden Grove", "Hidden Grove", true, 1630,
                     720, "msq_modstudio_test22_places_1_hidden_grove_uitx", ""),
        new MapPlace("modstudio.test22.places", "Test 22 New Places", "2 Old Watchtower", "Old Watchtower", true, 1340,
                     760, "", "19"),
        new MapPlace("modstudio.test22.places", "Test 22 New Places", "3 Ambush Ridge", "Ambush Ridge", false, 1240,
                     990, "", ""),
    };

    sealed class Text
    {
        public nint Characters;
        public uint Number;
        public int Holders;
        public string Value = "";
    }

    static readonly Dictionary<string, Text> ByValue = new();
    static readonly Dictionary<uint, Text> ByNumber = new();
    /// <summary>A box's piece (a reference's), a piece's box, a piece's markers, a piece's own boxes, a layer's
    /// boxes in order.</summary>
    static readonly Dictionary<nint, nint> PieceOf = new();
    static readonly Dictionary<nint, nint> BoxOfPiece = new();
    static readonly Dictionary<(nint, string), nint> MarkerOf = new();
    static readonly Dictionary<nint, (nint Piece, string Name)> OwnerOf = new();
    static readonly Dictionary<(nint, string), nint> OwnBox = new();
    static readonly Dictionary<nint, List<nint>> Children = new();
    static readonly List<string> Calls = new();
    static readonly List<string> Faults = new();
    static nint _mapAll, _bases, _layer;
    static byte _ready = 1;
    static bool _copyFails, _noPicture;
    static int _taller;                                                    // the game's pieces' height over their width
    /// <summary>(1.3.1) Behind each reference box of the game's pieces, where a reference names the piece it
    /// places, a collision box of the piece placed: never the helper's to turn off.</summary>
    static readonly List<nint> Lures = new();
    /// <summary>(1.7.0) A label's text box's piece, and what each text box was given.</summary>
    static readonly Dictionary<nint, nint> TitleOf = new();
    static readonly Dictionary<nint, string> TextOf = new();
    const string LabelName = "TextBoardMapName";
    /// <summary>(1.7.0) The message a label's text box shows as the layout leaves it.</summary>
    const int LayoutMessage = 0x5A5;

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

    /// <summary>What a call names a piece by: its box's name as it is, a marker's after it.</summary>
    static string Label(nint piece)
    {
        if (BoxOfPiece.TryGetValue(piece, out var box))
            return NameOf(box);
        if (OwnerOf.TryGetValue(piece, out var owner))
            return $"{Label(owner.Piece)}/{owner.Name}";
        return piece == _bases ? "Bases" : $"{piece:X}";
    }

    /// <summary>A box by its name in a layer, as the game searches one (its layers' boxes too).</summary>
    static nint InLayer(nint layer, string name)
    {
        if (!Children.TryGetValue(layer, out var boxes))
            return 0;
        foreach (var box in boxes)
            if (NameOf(box) == name)
                return box;
        return 0;
    }

    // --- The game's functions, as the stand-in has them ---------------------------

    [UnmanagedCallersOnly]
    static nint ChildPiece(nint piece, nint name)
    {
        try
        {
            string named = Read(*(nint*)name);
            if (*(uint*)(name + 8) != 0)
                Faults.Add($"{named} looked for by a string's number, not its characters");
            if (piece == _mapAll)
                return named == "Bases" ? _bases : 0;
            if (piece == _bases)
            {
                nint box = InLayer(_layer, named);
                return box != 0 && PieceOf.TryGetValue(box, out var found) ? found : 0;
            }
            return MarkerOf.TryGetValue((piece, named), out var marker) ? marker : 0;
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
            return 0;
        }
    }

    [UnmanagedCallersOnly]
    static nint BoxNamed(nint tree, nint name)
    {
        try
        {
            string named = Read(*(nint*)name);
            if (tree == _bases + Marker.PieceTree)
                return InLayer(_layer, named);
            return OwnBox.TryGetValue((tree, named), out var box) ? box : 0;
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
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
        }
        return _ready;
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

    /// <summary>A box copied as the game copies one: a new box of its kind, size and place, its name's string
    /// held again, in no layer yet; a reference's piece copied with it (its picture, holding its parts' name
    /// again, and its markers).</summary>
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
            foreach (int at in new[] { Marker.BoxKind, 0x38, 0x3C, MapPieces.BoxWidth, MapPieces.BoxHeight })
                *(int*)(copy + at) = *(int*)(box + at);
            if (PieceOf.TryGetValue(box, out var piece))
            {
                nint made = Block(0x400);
                PieceOf[copy] = made;
                BoxOfPiece[made] = copy;
                if (!_noPicture && OwnBox.TryGetValue((piece + Marker.PieceTree, "Image01"), out var picture))
                    Picture(made, Read(*(nint*)(picture + Marker.PictureParts)), *(int*)(picture + Marker.PicturePart));
                foreach (var name in Markers)
                    if (MarkerOf.ContainsKey((piece, name)))
                        Mark(made, name);
                // (1.7.0) Its label, its text box as the model's (the message it shows).
                if (MarkerOf.TryGetValue((piece, LabelName), out var label)
                    && OwnBox.TryGetValue((label + Marker.PieceTree, "Title"), out var title))
                    LabelOf(made, *(int*)(title + MapPieces.TextMessage));
                // (1.3.1) As the game copies a piece: its tag (the screen's 0x1F and the place's number) and its
                // boxes, each copied, collision boxes as they are.
                *(int*)(made + MapPieces.PieceTag) = *(int*)(piece + MapPieces.PieceTag);
                *(int*)(made + MapPieces.PiecePlace) = *(int*)(piece + MapPieces.PiecePlace);
                CopyTree(piece + Marker.PieceTree, made + Marker.PieceTree, made);
            }
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
            *(int*)(box + 0x38) = x;
            *(int*)(box + 0x3C) = y;
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
        }
    }

    [UnmanagedCallersOnly]
    static void PieceAdd(nint layer, nint box, nint after)
    {
        try
        {
            Calls.Add($"add {NameOf(box)} to {(layer == _layer ? "LayerBase" : $"{layer:X}")} after "
                      + (after == 0 ? "none" : NameOf(after)));
            if (!Children.TryGetValue(layer, out var boxes))
                Children[layer] = boxes = new List<nint>();
            int at = after == 0 ? 0 : boxes.IndexOf(after) + 1;
            if (after != 0 && at == 0)
                Faults.Add($"{NameOf(box)} put after a box not in the layer");
            boxes.Insert(at, box);
            *(nint*)(box + MapPieces.BoxParent) = layer;
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
        }
    }

    [UnmanagedCallersOnly]
    static void AnimationPlay(nint piece, nint name, int frame)
    {
        try
        {
            if (*(uint*)(name + 8) != 0)
                Faults.Add($"{Read(*(nint*)name)} played by a string's number, not its characters");
            Calls.Add($"play {Label(piece)} {Read(*(nint*)name)} {frame}");
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
        }
    }

    [UnmanagedCallersOnly]
    static void AnimationsStop(nint piece)
    {
        try
        {
            Calls.Add($"stop {Label(piece)}");
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
        }
    }

    /// <summary>(1.7.0) A text box given a text (its characters, as the game's own code gives them).</summary>
    [UnmanagedCallersOnly]
    static void SetText(nint box, nint characters)
    {
        try
        {
            string text = Read(characters);
            TextOf[box] = text;
            Calls.Add($"text {(TitleOf.TryGetValue(box, out var piece) ? Label(piece) : $"{box:X}")} {text} "
                      + $"(message {*(int*)(box + MapPieces.TextMessage)}, changed {*(byte*)(box + MapPieces.TextChanged)})");
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
        }
    }

    /// <summary>(1.7.0) A tree's box of a kind, the first or the second found (through its layers, not into the
    /// pieces its references place).</summary>
    [UnmanagedCallersOnly]
    static nint BoxOfKind(nint tree, int kind, int which)
    {
        try
        {
            var found = new List<nint>();
            void Walk(nint layer)
            {
                for (nint box = *(nint*)(layer + MapPieces.LayerFirst); box != 0; box = *(nint*)(box + MapPieces.BoxNext))
                {
                    int k = *(int*)(box + Marker.BoxKind);
                    if (k == kind)
                        found.Add(box);
                    if (k == MapPieces.LayerKind)
                        Walk(box);
                }
            }
            Walk(tree);
            return which >= 0 && which < found.Count ? found[which] : 0;
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
            return 0;
        }
    }

    [UnmanagedCallersOnly]
    static void BoxRefresh(nint box, byte all)
    {
        try
        {
            Calls.Add($"refresh {box:X} {all}");
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
        }
    }

    // --- The stand-in ----------------------------------------------------------------

    /// <summary>The image: at each function's place, code that jumps to the stand-in's (jmp [rip + 0],
    /// then its address); at the strings' pool's, the pool. Its places given to `places`.</summary>
    static byte* Image(Places places)
    {
        nint libc = NativeLibrary.Load("libc.so.6");
        var map = (delegate* unmanaged<nint, nuint, int, int, int, nint, nint>)NativeLibrary.GetExport(libc, "mmap");
        var protect = (delegate* unmanaged<nint, nuint, int, int>)NativeLibrary.GetExport(libc, "mprotect");
        nint block = map(0, 4096, 3, 0x22, -1, 0);                       // read and write; private, anonymous
        if (block == -1)
            throw new InvalidOperationException("no memory for the stand-in's image");
        byte* image = (byte*)block;
        delegate* unmanaged<nint, nint, nint> child = &ChildPiece, box = &BoxNamed, make = &StringMake,
                                              assign = &StringAssign;
        delegate* unmanaged<nint, nint, byte, byte> ready = &PartsReady;
        delegate* unmanaged<nint, uint, int> release = &StringRelease;
        delegate* unmanaged<nint, nint, byte, nint> copy = &PieceCopy;
        delegate* unmanaged<nint, int, int, void> move = &PieceMove;
        delegate* unmanaged<nint, nint, nint, void> add = &PieceAdd;
        delegate* unmanaged<nint, nint, int, void> play = &AnimationPlay;
        delegate* unmanaged<nint, void> stop = &AnimationsStop;
        delegate* unmanaged<nint, nint, void> setText = &SetText;
        delegate* unmanaged<nint, int, int, nint> boxOfKind = &BoxOfKind;
        delegate* unmanaged<nint, byte, void> refresh = &BoxRefresh;
        var functions = new (string Name, nint Function)[]
        {
            ("ChildPiece", (nint)child), ("BoxNamed", (nint)box), ("PartsReady", (nint)ready),
            ("StringMake", (nint)make), ("StringAssign", (nint)assign), ("StringRelease", (nint)release),
            ("PieceCopy", (nint)copy), ("PieceMove", (nint)move), ("PieceAdd", (nint)add),
            ("AnimationPlay", (nint)play), ("AnimationsStop", (nint)stop), ("SetText", (nint)setText),
            ("BoxOfKind", (nint)boxOfKind), ("BoxRefresh", (nint)refresh),
        };
        for (int n = 0; n < functions.Length; n++)
        {
            byte* at = image + 0x10 * n;
            at[0] = 0xFF;
            at[1] = 0x25;
            at[2] = at[3] = at[4] = at[5] = 0;
            *(long*)(at + 6) = functions[n].Function;
            Set(places, functions[n].Name, 0x10 * n);
        }
        *(long*)(image + 0x100) = Pool;
        Set(places, "StringPool", 0x100);
        if (protect(block, 4096, 5) != 0)                                   // read and run
            throw new InvalidOperationException("the stand-in's image can't be run");
        return image;
    }

    static void Set(Places places, string name, int value) => typeof(Places).GetProperty(name)!.SetValue(places, value);

    static nint Block(int size = 0x200) => (nint)NativeMemory.AllocZeroed((nuint)size);

    static void Picture(nint piece, string parts, int part)
    {
        nint picture = Block();
        *(int*)(picture + Marker.BoxKind) = Marker.PictureKind;
        Hold(picture + Marker.PictureParts, parts);
        *(int*)(picture + Marker.PicturePart) = part;
        OwnBox[(piece + Marker.PieceTree, "Image01")] = picture;
    }

    static void Mark(nint piece, string name)
    {
        nint marker = Block(0x400);
        MarkerOf[(piece, name)] = marker;
        OwnerOf[marker] = (piece, name);
    }

    /// <summary>(1.7.0) A piece's label: its TextBoardMapName (a piece placed in it, as its markers are), whose
    /// Title is a text box showing `message`'s text.</summary>
    static void LabelOf(nint piece, int message)
    {
        Mark(piece, LabelName);
        nint title = NewBox(MapPieces.TextKind);
        *(int*)(title + MapPieces.TextMessage) = message;
        TitleOf[title] = piece;
        OwnBox[(MarkerOf[(piece, LabelName)] + Marker.PieceTree, "Title")] = title;
    }

    /// <summary>(1.3.1) A box of a piece's tree: its kind, seen and shown (as the layout leaves a place's). Room
    /// for every field the helper touches on one: a text box's message at + 0xF8 and whether its text changed at
    /// + 0x13C (MapPieces.TextChanged). Until the tenth session's close it was 0x100 bytes, so the helper's write
    /// of + 0x13C landed in whatever the heap held next, and once in a sweep the checks died without a word.</summary>
    static nint NewBox(int kind)
    {
        nint box = Block(0x200);
        *(int*)(box + Marker.BoxKind) = kind;
        *(byte*)(box + MapPieces.BoxVisible) = 1;
        *(byte*)(box + MapPieces.BoxShown) = 1;
        return box;
    }

    /// <summary>A box put last in a layer (a layer's first box, then each box's next).</summary>
    static nint Append(nint layer, nint box)
    {
        nint at = layer + MapPieces.LayerFirst;
        while (*(nint*)at != 0)
            at = *(nint*)at + MapPieces.BoxNext;
        *(nint*)at = box;
        return box;
    }

    /// <summary>A reference box: where the game names the piece it places (+ 0xD0), here a collision box of that
    /// piece's, which a walk of the layers mustn't take for a box of its own.</summary>
    static nint Reference()
    {
        nint box = NewBox(MapPieces.ReferenceKind);
        nint lure = NewBox(MapPieces.CollisionKind);
        Lures.Add(lure);
        *(nint*)(box + MapPieces.LayerFirst) = lure;
        return box;
    }

    /// <summary>A piece's boxes copied into another's tree as the layouts' copy copies them (a picture the copy
    /// has of its own put in its place; a reference naming what it named).</summary>
    static void CopyTree(nint from, nint to, nint made)
    {
        for (nint box = *(nint*)(from + MapPieces.LayerFirst); box != 0; box = *(nint*)(box + MapPieces.BoxNext))
        {
            int kind = *(int*)(box + Marker.BoxKind);
            nint copy;
            if (kind == Marker.PictureKind)
            {
                if (!OwnBox.TryGetValue((made + Marker.PieceTree, "Image01"), out copy))
                    continue;
            }
            else
            {
                copy = NewBox(kind);
                *(byte*)(copy + MapPieces.BoxVisible) = *(byte*)(box + MapPieces.BoxVisible);
                *(byte*)(copy + MapPieces.BoxShown) = *(byte*)(box + MapPieces.BoxShown);
                if (kind == MapPieces.ReferenceKind)
                    *(nint*)(copy + MapPieces.LayerFirst) = *(nint*)(box + MapPieces.LayerFirst);
            }
            Append(to, copy);
            if (kind == MapPieces.LayerKind)
                CopyTree(box, copy, made);
        }
    }

    /// <summary>A piece's own collision boxes (through its layers), each [seen, shown].</summary>
    static List<int[]> Collisions(nint layer)
    {
        var found = new List<int[]>();
        for (nint box = *(nint*)(layer + MapPieces.LayerFirst); box != 0; box = *(nint*)(box + MapPieces.BoxNext))
        {
            int kind = *(int*)(box + Marker.BoxKind);
            if (kind == MapPieces.CollisionKind)
                found.Add(new int[] { *(byte*)(box + MapPieces.BoxVisible), *(byte*)(box + MapPieces.BoxShown) });
            else if (kind == MapPieces.LayerKind)
                found.AddRange(Collisions(box));
        }
        return found;
    }

    /// <summary>A place's piece of the game's: its box in the layer, its piece, its picture (a town's) and
    /// markers, kept by the screen at its place.</summary>
    static void GamePiece(nint screen, int place, string name, bool town, int x, int y)
    {
        nint box = Block();
        Hold(box + MapPieces.BoxName, name);
        *(int*)(box + Marker.BoxKind) = MapPieces.ReferenceKind;
        *(int*)(box + 0x38) = x;
        *(int*)(box + 0x3C) = y;
        *(int*)(box + MapPieces.BoxWidth) = town ? 172 : 64;
        *(int*)(box + MapPieces.BoxHeight) = (town ? 172 : 64) + _taller;
        *(nint*)(box + MapPieces.BoxParent) = _layer;
        Children[_layer].Add(box);
        nint piece = Block(0x400);
        PieceOf[box] = piece;
        BoxOfPiece[piece] = box;
        if (town)
            Picture(piece, IconParts, 1);
        foreach (var marker in town ? Markers : new[] { "Quest", "Next", "MidwayPoint" })
            Mark(piece, marker);
        LabelOf(piece, LayoutMessage);
        // (1.3.1) The tag the screen's setup gives it (0x1F, its place), and its boxes as the layout has them under
        // its root layer: a town's two layers (its picture's: a collision box and the picture; its point's: a
        // collision box and a reference), a battle ground's reference and collision box.
        *(int*)(piece + MapPieces.PieceTag) = MapPieces.PlaceTag;
        *(int*)(piece + MapPieces.PiecePlace) = place;
        nint root = Append(piece + Marker.PieceTree, NewBox(MapPieces.LayerKind));
        if (town)
        {
            nint pictureLayer = Append(root, NewBox(MapPieces.LayerKind));
            Append(pictureLayer, NewBox(MapPieces.CollisionKind));
            Append(pictureLayer, OwnBox[(piece + Marker.PieceTree, "Image01")]);
            nint pointLayer = Append(root, NewBox(MapPieces.LayerKind));
            Append(pointLayer, NewBox(MapPieces.CollisionKind));
            Append(pointLayer, Reference());
        }
        else
        {
            Append(root, Reference());
            Append(root, NewBox(MapPieces.CollisionKind));
        }
        nint at = screen + Places.MarkerPieces + place * Places.MarkerPieceSize;
        *(nint*)at = piece;
        *(nint*)(at + Places.PieceBox) = box;
        *(byte*)(at + Places.PieceTown) = (byte)(town ? 1 : 0);
    }

    /// <summary>A screen as the game sets one up: its layouts, MapAll, Bases and its layer, the places' pieces
    /// it keeps (a town and a battle ground, or one of them).</summary>
    static nint Screen(bool town = true, bool battle = true)
    {
        nint screen = Block(0x2000);
        *(nint*)(screen + Marker.ScreenLayouts) = (nint)Layouts;
        _mapAll = Block(0x400);
        _bases = Block(0x400);
        _layer = Block();
        Children[_layer] = new List<nint>();
        *(nint*)(screen + MapPieces.ScreenMapAll) = _mapAll;
        if (town)
            GamePiece(screen, Town, "Base01", true, 944, 1020);
        if (battle)
            GamePiece(screen, Battle, "Point02", false, 718, 1013);
        return screen;
    }

    static int Holders(string value) => ByValue.TryGetValue(value, out var text) ? text.Holders : 0;

    /// <summary>The layer as it is: each box's name, where it is, and its picture's parts' name and part (a
    /// town's), whether that string is the name's own; (1.3.1) its piece's tag and place, and its collision
    /// boxes, each [seen, shown].</summary>
    static List<object?[]> Look()
    {
        var boxes = new List<object?[]>();
        foreach (var box in Children[_layer])
        {
            object? parts = null, part = null, own = null, tag = null, place = null, collisions = null;
            if (PieceOf.TryGetValue(box, out var piece)
                && OwnBox.TryGetValue((piece + Marker.PieceTree, "Image01"), out var picture))
            {
                string name = Read(*(nint*)(picture + Marker.PictureParts));
                parts = name;
                part = *(int*)(picture + Marker.PicturePart);
                own = ByValue.TryGetValue(name, out var text) && text.Number == *(uint*)(picture + Marker.PictureParts + 8);
            }
            if (piece != 0)
            {
                tag = *(int*)(piece + MapPieces.PieceTag);
                place = *(int*)(piece + MapPieces.PiecePlace);
                collisions = Collisions(piece + Marker.PieceTree);
            }
            uint number = *(uint*)(box + MapPieces.BoxName + 8);
            boxes.Add(new object?[]
            {
                NameOf(box), ByValue.TryGetValue(NameOf(box), out var named) && named.Number == number,
                *(int*)(box + 0x38), *(int*)(box + 0x3C), parts, part, own, tag, place, collisions,
            });
        }
        return boxes;
    }

    /// <summary>(1.7.0) A screen's rows past its end: each its piece's and box's names (the piece by its box's),
    /// its kind and town's byte, and whether the rest of it is zero.</summary>
    static List<object?[]> Rows(nint screen, int rows)
    {
        var found = new List<object?[]>();
        for (int index = 0; index < rows; index++)
        {
            nint row = screen + Destinations.ScreenRows + index * Destinations.RowSize;
            nint piece = *(nint*)(row + Destinations.RowPiece), box = *(nint*)(row + Destinations.RowBox);
            found.Add(new object?[]
            {
                piece == 0 ? null : BoxOfPiece.TryGetValue(piece, out var of) ? NameOf(of) : $"{piece:X}",
                box == 0 ? null : NameOf(box), *(int*)(row + Destinations.RowKind), *(byte*)(row + Destinations.RowTown),
                (*(uint*)(row + Destinations.RowTown) >> 8) == 0,
            });
        }
        return found;
    }

    /// <summary>(1.7.0) Each copy's label as it is: its text box's text, the message it shows, whether it is marked
    /// to be drawn again.</summary>
    static Dictionary<string, object?[]> Labels()
    {
        var labels = new Dictionary<string, object?[]>();
        foreach (var box in Children[_layer])
        {
            if (!NameOf(box).StartsWith(MapPieces.BoxPrefix) || !PieceOf.TryGetValue(box, out var piece)
                || !MarkerOf.TryGetValue((piece, LabelName), out var label)
                || !OwnBox.TryGetValue((label + Marker.PieceTree, "Title"), out var title))
                continue;
            labels[NameOf(box)] = new object?[]
            {
                TextOf.TryGetValue(title, out var text) ? text : null, *(int*)(title + MapPieces.TextMessage),
                *(byte*)(title + MapPieces.TextChanged),
            };
        }
        return labels;
    }

    public static int Run(string[] args)
    {
        var places = new Places();
        byte* image = Image(places);
        var steps = new List<Dictionary<string, object?>>();
        var said = new List<string>();

        void Step(string name, MapPieces pieces, nint screen)
        {
            Calls.Clear();
            said.Clear();
            pieces.Add(screen, said.Add);
            steps.Add(new Dictionary<string, object?>
            {
                ["step"] = name, ["said"] = new List<string>(said), ["calls"] = new List<string>(Calls),
                ["layer"] = Look(), ["names"] = new Dictionary<string, int>
                {
                    ["MsqPlace0"] = Holders("MsqPlace0"), ["MsqPlace1"] = Holders("MsqPlace1"),
                    ["MsqPlace2"] = Holders("MsqPlace2"), ["Base01"] = Holders("Base01"),
                    ["Point02"] = Holders("Point02"), ["icons"] = Holders(IconParts),
                    ["ours"] = Holders(Given[0].Parts),
                },
            });
        }

        var pieces = new MapPieces(image, places, Given);
        nint screen = Screen();
        Step("a screen set up: the three places added", pieces, screen);
        Step("the same screen set up again: nothing added", pieces, screen);
        Step("a new screen: the three added again", pieces, Screen());
        _ready = 0;
        Step("a new screen, the picture not made ready: the two others added", pieces, Screen());
        _ready = 1;
        Step("a new screen without a battle ground: the two towns added", pieces, Screen(battle: false));
        Step("a new screen without a town: the battle ground added", pieces, Screen(town: false));
        _noPicture = true;
        Step("a new screen whose town copies have no picture", pieces, Screen());
        _noPicture = false;
        _copyFails = true;
        Step("a new screen whose copies fail", pieces, Screen());
        _copyFails = false;
        _taller = 40;
        Step("a new screen whose pieces are taller than wide: each copy's middle the place's", pieces, Screen());
        _taller = 0;
        nint gone = Screen();
        *(nint*)(gone + Marker.ScreenLayouts) = 0;
        Step("a screen without its layouts: nothing", pieces, gone);
        nint noBases = Screen();
        _bases = Block(0x400);                                             // MapAll's Bases isn't this one
        nint stale = _mapAll;
        _mapAll = Block(0x400);
        *(nint*)(noBases + MapPieces.ScreenMapAll) = stale;
        Step("a screen whose MapAll has no Bases", pieces, noBases);
        Step("no screen", pieces, 0);
        // A screen whose places are pictures only has nothing past its end.
        bool unarmedRowsNone = true;
        for (int at = Destinations.ScreenRows; at < Destinations.ScreenRows + 3 * Destinations.RowSize; at++)
            unarmedRowsNone &= *(byte*)(screen + at) == 0;

        // (1.7.0) The places the game goes to, numbered as test 28's (48 to 50), then with a gap (48, 52).
        var armedSteps = new List<Dictionary<string, object?>>();
        void Armed(string name, MapPieces armed, nint room, int rows)
        {
            Calls.Clear();
            said.Clear();
            armed.Add(room, said.Add);
            armedSteps.Add(new Dictionary<string, object?>
            {
                ["step"] = name, ["said"] = new List<string>(said), ["calls"] = new List<string>(Calls),
                ["layer"] = Look(), ["rows"] = Rows(room, rows), ["labels"] = Labels(),
            });
        }
        var numbered = new List<Destination> { new(Given[0], 48), new(Given[1], 49), new(Given[2], 50) };
        var armedPieces = new MapPieces(image, places, Given, numbered);
        nint room = Screen();
        Armed("a screen set up, the places numbered 48 to 50: each added a place of the screen's, its row past the "
              + "screen's end", armedPieces, room, 3);
        // Its rows cleared first, so only rows written again read as they were.
        for (int at = Destinations.ScreenRows; at < Destinations.ScreenRows + 3 * Destinations.RowSize; at++)
            *(byte*)(room + at) = 0;
        Armed("the same screen set up again: nothing added, the rows written again", armedPieces, room, 3);
        var switched = new List<Dictionary<string, object?>>();
        foreach (int reasons in new[] { 1, 0, 2 })
        {
            *(int*)(room + MapPieces.SwitchReasons) = reasons;
            Calls.Clear();
            armedPieces.Switched(room);
            switched.Add(new Dictionary<string, object?>
            {
                ["reasons"] = reasons, ["calls"] = new List<string>(Calls), ["layer"] = Look(),
            });
        }
        Calls.Clear();
        armedPieces.Switched(0);
        bool noScreenNothing = Calls.Count == 0;
        var gap = new List<Destination> { new(Given[0], 48), new(Given[2], 52) };
        Armed("a screen set up, two places numbered 48 and 52 (the one between not given): their rows at 0 and 4",
              new MapPieces(image, places, Given, gap), Screen(), 5);
        var report = new Dictionary<string, object?>
        {
            ["steps"] = steps, ["faults"] = Faults, ["iconParts"] = IconParts,
            ["places"] = Given.ConvertAll(p => new object[] { p.Name, p.Town, p.X, p.Y, p.Parts, p.Icon }),
            ["lures"] = Lures.ConvertAll(l => new int[] { *(byte*)(l + MapPieces.BoxVisible),
                                                         *(byte*)(l + MapPieces.BoxShown) }),
            ["unarmedRowsNone"] = unarmedRowsNone, ["armed"] = armedSteps, ["switched"] = switched,
            ["switchedNoScreen"] = noScreenNothing, ["layoutMessage"] = LayoutMessage,
        };
        File.WriteAllText(args[1], JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
        return 0;
    }
}
