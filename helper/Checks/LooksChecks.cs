// Mod Studio's checks of the helper: (1.23.0) a mod's dungeon's list in its
// own looks (DungeonLooks.cs, Zodi's test 49), run against a stand-in for the
// world map's frame and the Deep's list: the UI's root and the frame (its
// Deep list at + 0x60, its mode at + 0xE4), the Deep list's layouts (their
// pieces, the root among them), its title's pieces and text box (the UI text
// 1620), its Thumbnail; and the game's functions the helper calls (a piece's
// child by its name, a box by its name, a text made again, a row looked up,
// the base art's path, the art's setter, a place's name by its number),
// reached as the helper reaches the game's: at their places in an image,
// here code that jumps to the stand-in's own (as PlaceChecks.cs); (1.24.0)
// and the world map's prompt to enter a mod's dungeon (the UI text 1618 its
// Enter Midlight's Deep, 1626, with its name). Part of The Ivalice
// Chronicles Mod Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --looks <report.json>
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using ModStudioEventSetup;

static unsafe class LooksChecks
{
    /// <summary>The stand-in's places: a mod's dungeon described (48), one without words (49), a town (5).</summary>
    const int Described = 48, Plain = 49, Town = 5, Deep = DungeonLooks.DeepPlace;
    /// <summary>Their Town rows' art: the Deep's own 18, the described dungeon's own (OwnArt plus its number), the
    /// other a game place's (Nelveska Temple's 26).</summary>
    static readonly Dictionary<int, int> Arts = new() { [Deep] = 18, [Described] = 1048, [Plain] = 26, [Town] = 9 };
    static readonly List<string> Calls = new();
    static readonly List<string> Faults = new();
    static nint _rootPiece, _dungeon, _list, _titlePiece, _title, _deep, _thumbnail, _frame;
    static bool _french, _noTitle;
    static readonly Dictionary<string, nint> Held = new();
    /// <summary>The image's data, past its code's page: the UI's root, then Ramza's place.</summary>
    const int Data = 0x1000;

    static nint Block(int size = 0x400) => (nint)NativeMemory.AllocZeroed((nuint)size);

    static nint Utf8(string text)
    {
        if (Held.TryGetValue(text, out nint at))
            return at;
        var bytes = Encoding.UTF8.GetBytes(text + "\0");
        at = (nint)NativeMemory.AllocZeroed((nuint)bytes.Length);
        Marshal.Copy(bytes, 0, at, bytes.Length);
        Held[text] = at;
        return at;
    }

    static string Read(nint utf8)
    {
        if (utf8 == 0)
            return "";
        int length = 0;
        while (*((byte*)utf8 + length) != 0)
            length++;
        return Encoding.UTF8.GetString((byte*)utf8, length);
    }

    // --- The game's functions, as the stand-in has them ---------------------------------

    [UnmanagedCallersOnly]
    static nint ChildPiece(nint piece, nint name)
    {
        string named = Read(*(nint*)name);
        Calls.Add($"child {Who(piece)} {named}");
        if (piece == _rootPiece && named == "DeepDungeon")
            return _dungeon;
        if (piece == _dungeon && named == "DeepDungeonList")
            return _list;
        if (piece == _list && named == "Title")
            return _titlePiece;
        return 0;
    }

    [UnmanagedCallersOnly]
    static nint BoxNamed(nint tree, nint name)
    {
        string named = Read(*(nint*)name);
        Calls.Add($"box {Who(tree - Marker.PieceTree)} {named}");
        return tree == _titlePiece + Marker.PieceTree && named == "Text00" && !_noTitle ? _title : 0;
    }

    [UnmanagedCallersOnly]
    static void TextRemake(nint box)
        => Calls.Add($"remake {Who(box)} (made again: {*(byte*)(box + Places.TextRemade)}, its text "
                     + $"{*(int*)(box + Places.TextNumber)})");

    [UnmanagedCallersOnly]
    static nint RowLookup(int sheet, int key)
    {
        Calls.Add($"row {sheet:X} {key}");
        if (sheet != Destinations.TownSheet || !Arts.TryGetValue(key, out int art))
            return 0;
        nint row = Block(0x40);
        *(int*)(row + Destinations.TownArt) = art;
        return row;
    }

    [UnmanagedCallersOnly]
    static int BaseArt(nint buffer, int number, int size)
    {
        var path = Encoding.ASCII.GetBytes($"art {number}\0");
        Marshal.Copy(path, 0, buffer, Math.Min(path.Length, size));
        Calls.Add($"base art {number} ({size})");
        return path.Length - 1;
    }

    [UnmanagedCallersOnly]
    static void ArtSetter(nint ui, nint box, nint path)
        => Calls.Add($"art set {Who(ui)} {Who(box)} {Read(path)}");

    [UnmanagedCallersOnly]
    static nint PlaceNameText(int number)
    {
        Calls.Add($"place name {number}");
        return number != Places.DeepNameText ? Utf8("") : Utf8(_french ? "Donjons sans fond" : "Midlight's Deep");
    }

    static string Who(nint at)
        => at == _rootPiece ? "root" : at == _dungeon ? "DeepDungeon" : at == _list ? "DeepDungeonList"
            : at == _titlePiece ? "Title" : at == _title ? "Text00" : at == _deep ? "the Deep's list"
            : at == _thumbnail ? "Thumbnail" : at == 0 ? "none" : $"{at:X}";

    /// <summary>The game's UI text by its number, in English or French (the 1.5.2 tables' words).</summary>
    static nint GameText(int number)
    {
        Calls.Add($"game text {number}");
        return number switch
        {
            Places.TitleText => Utf8(_french ? "D<scale=0.8>ONJONS SANS FOND<scale>" : "Midlight's Deep"),
            Places.ExitText => Utf8(_french ? "Sortir des donjons sans fond" : "Exit Midlight's Deep"),
            Places.AboutText => Utf8(_french ? "Voir une explication" : "About Midlight's Deep"),
            // (1.24.0) The world map's prompts to enter a town and the Deep.
            Places.SettlementText => Utf8(_french ? "Entrer dans la ville" : "Enter Settlement"),
            Places.EnterDeepText => Utf8(_french ? "Pénétrer dans les donjons sans fond" : "Enter Midlight's Deep"),
            _ => Utf8($"text {number}"),
        };
    }

    // --- The stand-in ----------------------------------------------------------------------------

    static byte* Image(Places places)
    {
        nint libc = NativeLibrary.Load("libc.so.6");
        var map = (delegate* unmanaged<nint, nuint, int, int, int, nint, nint>)NativeLibrary.GetExport(libc, "mmap");
        var protect = (delegate* unmanaged<nint, nuint, int, int>)NativeLibrary.GetExport(libc, "mprotect");
        nint block = map(0, 8192, 3, 0x22, -1, 0);                       // its code, then its data
        if (block == -1)
            throw new InvalidOperationException("no memory for the stand-in's image");
        byte* image = (byte*)block;
        delegate* unmanaged<nint, nint, nint> child = &ChildPiece, box = &BoxNamed;
        delegate* unmanaged<nint, void> remake = &TextRemake;
        delegate* unmanaged<int, int, nint> row = &RowLookup;
        delegate* unmanaged<nint, int, int, int> art = &BaseArt;
        delegate* unmanaged<nint, nint, nint, void> setter = &ArtSetter;
        delegate* unmanaged<int, nint> name = &PlaceNameText;
        var functions = new (string Name, nint Function)[]
        {
            ("ChildPiece", (nint)child), ("BoxNamed", (nint)box), ("TextRemake", (nint)remake),
            ("RowLookup", (nint)row), ("BaseArt", (nint)art), ("ArtSetter", (nint)setter),
            ("PlaceNameText", (nint)name),
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
        Set(places, "UiRoot", Data);
        Set(places, "CurrentPlace", Data + 0x10);
        Set(places, "AboutGuide", 0xE6);
        Set(places, "DeepGuide", 0xBBD);
        // The UI's root, + 0x10, + 0xA0: the frame; its Deep list, its mode.
        nint root = Block(), menus = Block();
        _frame = Block();
        *(nint*)(image + Data) = root;
        *(nint*)(root + Places.UiFirst) = menus;
        *(nint*)(menus + Places.UiMenus) = _frame;
        _deep = Block(0x400);
        *(nint*)(_frame + Places.FrameDeep) = _deep;
        // The Deep list's layouts: two pieces, the root the second (its kind 1).
        nint layouts = Block();
        *(nint*)(_deep + Places.UiLayouts) = layouts;
        nint pieces = Block(0x20);
        nint other = Block(0x400);
        *(int*)(other + 0x218) = 3;
        _rootPiece = Block(0x400);
        *(int*)(_rootPiece + 0x218) = 1;
        *(nint*)pieces = other;
        *(nint*)(pieces + 8) = _rootPiece;
        *(nint*)(layouts + 0x68) = pieces;
        *(nint*)(layouts + 0x70) = pieces + 0x10;
        _dungeon = Block();
        _list = Block();
        _titlePiece = Block(0x200);
        _title = Block(0x200);
        *(int*)(_title + Marker.BoxKind) = Places.TextKind;
        *(int*)(_title + Places.TextNumber) = Places.TitleText;
        _thumbnail = Block(0x200);
        *(int*)(_thumbnail + Marker.BoxKind) = Marker.PictureKind;
        *(nint*)(_deep + Places.DeepThumbnail) = _thumbnail;
        if (protect(block, 4096, 5) != 0)                                   // its code read and run
            throw new InvalidOperationException("the stand-in's image can't be run");
        return image;
    }

    static void Set(Places places, string name, int value) => typeof(Places).GetProperty(name)!.SetValue(places, value);

    public static int Run(string[] args)
    {
        var places = new Places();
        byte* image = Image(places);
        int* here = (int*)(image + Data + 0x10);
        var floors = new List<Framework.DungeonFloor>();
        var described = new MapPlace("m", "Test Mod", "o", "Old Quarry", true, 0, 0, "", "07",
                                     "An old quarry, its pits deep in the hills.");
        var plain = new MapPlace("m", "Test Mod", "p", "Pit", true, 0, 0, "", "07");
        var dungeons = new SortedDictionary<int, Framework.DungeonPlan>
        {
            [Described] = new Framework.DungeonPlan(described, Described, floors),
            [Plain] = new Framework.DungeonPlan(plain, Plain, floors),
        };
        var looks = new DungeonLooks(image, places, dungeons);
        var report = new Dictionary<string, object?>();

        // The UI's texts: at each place, each language, the title, Exit, About and another text.
        var texts = new List<object?[]>();
        foreach (bool french in new[] { false, true })
            foreach (int place in new[] { Described, Plain, Deep, Town })
            {
                _french = french;
                *here = place;
                foreach (int number in new[] { Places.TitleText, Places.ExitText, Places.AboutText, 1608,
                                               Places.SettlementText, Places.EnterDeepText })
                {
                    Calls.Clear();
                    nint own = looks.Text(number, GameText);
                    texts.Add(new object?[] { french ? "fr" : "en", place, number, own == 0 ? null : Read(own),
                                              new List<string>(Calls) });
                }
            }
        _french = false;
        report["texts"] = texts;
        // The same words twice: made once (the same characters given); (1.24.0) the prompt to enter it too.
        *here = Described;
        nint first = looks.Text(Places.ExitText, GameText), again = looks.Text(Places.ExitText, GameText);
        nint enter = looks.Text(Places.SettlementText, GameText), enterAgain = looks.Text(Places.SettlementText, GameText);
        report["wordsKept"] = first == again && first != 0 && enter == enterAgain && enter != 0 && enter != first;

        // The guide's page: its sheet, the About key's guide, page 0; the frame's mode; each place.
        var pages = new List<object?[]>();
        foreach (var (place, mode, sheet, key, page) in new[]
                 {
                     (Described, 4, 0xBC, 0xE6, 0), (Described, 1, 0xBC, 0xE6, 0), (Described, 4, 0xBB, 0xE6, 0),
                     (Described, 4, 0xBC, 0xE5, 0), (Described, 4, 0xBC, 0xE6, 1), (Plain, 4, 0xBC, 0xE6, 0),
                     (Deep, 4, 0xBC, 0xE6, 0), (Town, 4, 0xBC, 0xE6, 0),
                 })
        {
            *here = place;
            *(int*)(_frame + Places.FrameMode) = mode;
            var opened = new List<string>();
            nint row = looks.Page(sheet, key, page, d => opened.Add(d.Place.Name));
            pages.Add(new object?[]
            {
                place, mode, sheet, key, page, row == 0 ? null : Hex(row, Framework.AboutPage(described.Name,
                                                                                              described.Description).Length),
                opened,
            });
        }
        report["pages"] = pages;
        report["aboutPage"] = Convert.ToHexString(Framework.AboutPage(described.Name, described.Description));

        // The button guide's rows and the About key, at each place.
        var rows = new List<object?[]>();
        foreach (int place in new[] { Described, Plain, Deep, Town })
        {
            *here = place;
            rows.Add(new object?[] { place, looks.Rows(0xBBD, -1), looks.Rows(0xBC1, -1), looks.Rows(0xBBD, 7),
                                     looks.AboutOpens() });
        }
        report["rows"] = rows;

        // A dungeon's list dressed as it opens: each place, then without a frame, without a title, a title of another
        // text.
        var dressed = new List<object?[]>();
        void Dress(string label, int place)
        {
            Calls.Clear();
            *(byte*)(_title + Places.TextRemade) = 0;
            var dungeon = looks.Dress(place);
            dressed.Add(new object?[] { label, place, dungeon?.Place.Name, new List<string>(Calls) });
        }
        foreach (int place in new[] { Described, Plain, Deep, Town })
            Dress("as made", place);
        _noTitle = true;
        Dress("no title box", Described);
        _noTitle = false;
        *(int*)(_title + Places.TextNumber) = 1611;
        Dress("its title another text", Described);
        *(int*)(_title + Places.TextNumber) = Places.TitleText;
        *(nint*)(_frame + Places.FrameDeep) = 0;
        Dress("no Deep list", Described);
        *(nint*)(_frame + Places.FrameDeep) = _deep;
        report["dressed"] = dressed;
        report["faults"] = Faults;
        File.WriteAllText(args[1], JsonSerializer.Serialize(report));
        return 0;
    }

    static string Hex(nint at, int length)
    {
        var bytes = new byte[length];
        Marshal.Copy(at, bytes, 0, length);
        return Convert.ToHexString(bytes);
    }
}
