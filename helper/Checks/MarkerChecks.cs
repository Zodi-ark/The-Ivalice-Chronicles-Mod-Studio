// Mod Studio's checks of the helper: (1.2.5) the quests' markers (Marker.cs)
// run against a stand-in for the world map screen: places' pieces, their
// Quest markers' pins and glows laid out as the game lays its boxes out, and
// the game's functions the helper calls (a piece's child by its name, a box by
// its name, a picture's parts made ready, the game's strings made, given and
// let go, each counted by its holders as the game counts them), reached as
// the helper reaches the game's: at their places in an image, here code that
// jumps to the stand-in's own. (1.8.0) And a mod's own places' markers
// (Marker.ShowMods): their pieces in the rows past the screen's 48, the
// layouts' playing and stopping of a piece's animations recorded. Part of The
// Ivalice Chronicles Mod Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --marker <report.json>
//     dotnet Checks.dll --marker-mods <report.json>     (1.8.0: the mods' places' markers)
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using ModStudioEventSetup;

static unsafe class MarkerChecks
{
    /// <summary>The game's pin's parts' name and part (ui_wm_01_uitx's PinQuest), its color and its
    /// glows' (65, 237, 255, 255; the second glow's here a little see-through, so the two are told
    /// apart), as bytes R, G, B, A.</summary>
    const string GameParts = "UITextureParts://ui/ffto/worldmap/textureparts/ui_wm_01_uitx";
    const int GamePart = 8;
    const uint White = 0xFFFFFFFF, Cyan = 0xFFFFED41, Cyan00 = 0xC0FFED41;
    /// <summary>What the stand-in's image holds for the strings' pool, and the screen for its layouts.</summary>
    const long Pool = 0x5EED0000, Layouts = 0x1A700000;
    /// <summary>The stand-in's places: whole (a pin and two glows), a pin alone, no piece, no Quest
    /// marker, no pin, a pin that isn't a picture, a pin whose picture has no name.</summary>
    static readonly int[] Whole = { 6, 9, 12, 32 };
    const int PinAlone = 33, NoPiece = 20, NoQuest = 21, NoPin = 22, NotPicture = 23, Nameless = 40;
    /// <summary>Place 47, no place (a quest's are 0 to 46): a piece there is never to be looked at.</summary>
    const int Past = QuestFile.Places;
    /// <summary>(1.8.0) The mods' places given (rows past the screen's 48): 48 whole, 49 without a Quest marker;
    /// 50 has a row past the two given, never to be looked at.</summary>
    const int ModWhole = Destinations.FirstNumber, ModNoQuest = Destinations.FirstNumber + 1, ModRows = 2,
              ModPast = Destinations.FirstNumber + ModRows;
    static nint _modPast;

    sealed class Text
    {
        public nint Characters;
        public uint Number;
        public int Holders;
        public string Value = "";
    }

    static readonly Dictionary<string, Text> ByValue = new();
    static readonly Dictionary<uint, Text> ByNumber = new();
    static readonly Dictionary<nint, nint> QuestOf = new();
    static readonly Dictionary<(nint, string), nint> BoxOf = new();
    static readonly Dictionary<int, (nint Pin, nint Glow, nint Glow00)> Pins = new();
    static readonly List<string> Calls = new();
    static readonly List<string> Faults = new();
    static nint _past;
    static byte _ready = 1;

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

    static void LetGo(uint number)
    {
        if (!ByNumber.TryGetValue(number, out var text))
            Faults.Add($"a string numbered {number} let go, which was never made");
        else if (--text.Holders < 0)
            Faults.Add($"{text.Value} let go more often than it was held");
    }

    // --- The game's functions, as the stand-in has them ---------------------------

    [UnmanagedCallersOnly]
    static nint ChildPiece(nint piece, nint name)
    {
        try
        {
            if (piece == _past)
                Faults.Add($"place {Past}'s piece looked at, no place a quest can be at");
            if (piece == _modPast)
                Faults.Add($"place {ModPast}'s piece looked at, past the mods' places given");
            return Read(*(nint*)name) == "Quest" && QuestOf.TryGetValue(piece, out var quest) ? quest : 0;
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
            return 0;
        }
    }

    /// <summary>(1.8.0) The layouts' playing of a piece's animation by its name (frame -1: its last), and the
    /// stopping of all a piece's animations: recorded, by the piece's name.</summary>
    static readonly Dictionary<nint, string> PieceNames = new();

    static string PieceName(nint piece) => PieceNames.TryGetValue(piece, out var name) ? name : $"{piece:X}";

    [UnmanagedCallersOnly]
    static void AnimationPlay(nint piece, nint name, int frame)
    {
        try
        {
            Calls.Add($"play {PieceName(piece)} {Read(*(nint*)name)} {frame}");
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
            Calls.Add($"stop {PieceName(piece)}");
        }
        catch (Exception e)
        {
            Faults.Add(e.Message);
        }
    }

    [UnmanagedCallersOnly]
    static nint BoxNamed(nint tree, nint name)
    {
        try
        {
            return BoxOf.TryGetValue((tree, Read(*(nint*)name)), out var box) ? box : 0;
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
            var text = Intern(Read(characters));
            text.Holders++;
            *(nint*)into = text.Characters;
            *(uint*)(into + 8) = text.Number;
            Calls.Add($"make {text.Value}");
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
        delegate* unmanaged<nint, nint, int, void> play = &AnimationPlay;
        delegate* unmanaged<nint, void> stop = &AnimationsStop;
        var functions = new (string Name, nint Function)[]
        {
            ("ChildPiece", (nint)child), ("BoxNamed", (nint)box), ("PartsReady", (nint)ready),
            ("StringMake", (nint)make), ("StringAssign", (nint)assign), ("StringRelease", (nint)release),
            ("AnimationPlay", (nint)play), ("AnimationsStop", (nint)stop),
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

    static nint Box(nint tree, string name, int kind, uint color, string? parts)
    {
        nint box = Block();
        *(int*)(box + Marker.BoxKind) = kind;
        *(uint*)(box + Marker.BoxColor) = color;
        if (parts != null)
        {
            var text = Intern(parts);
            text.Holders++;
            *(nint*)(box + Marker.PictureParts) = text.Characters;
            *(uint*)(box + Marker.PictureParts + 8) = text.Number;
            *(int*)(box + Marker.PicturePart) = GamePart;
        }
        BoxOf[(tree, name)] = box;
        return box;
    }

    /// <summary>The screen: its layouts, its places' pieces, each piece's Quest marker and its boxes; (1.8.0) with
    /// `mods`, the mods' places' rows past its 48.</summary>
    static nint Screen(bool mods)
    {
        nint screen = Block(0x2000);
        *(nint*)(screen + Marker.ScreenLayouts) = (nint)Layouts;
        Intern(GameParts).Holders++;                                       // held elsewhere in the game too
        void Piece(int place, bool quest, Func<nint, nint>? pin, bool glows)
        {
            nint piece = Block();
            if (place < Destinations.FirstNumber)
                *(nint*)(screen + Places.MarkerPieces + place * Places.MarkerPieceSize) = piece;
            else
                *(nint*)(screen + Destinations.ScreenRows + (place - Destinations.FirstNumber) * Destinations.RowSize)
                    = piece;
            PieceNames[piece] = $"place {place}";
            if (!quest)
                return;
            nint instance = Block();
            QuestOf[piece] = instance;
            PieceNames[instance] = $"place {place}'s Quest";
            nint tree = instance + Marker.PieceTree;
            nint image = pin == null ? 0 : pin(tree);
            nint glow = glows ? Box(tree, "GlowCircle", 0xC, Cyan, null) : 0;
            nint glow00 = glows ? Box(tree, "GlowCircle00", 0xC, Cyan00, null) : 0;
            Pins[place] = (image, glow, glow00);
        }
        foreach (int place in Whole)
            Piece(place, true, tree => Box(tree, "Image00", Marker.PictureKind, White, GameParts), true);
        Piece(PinAlone, true, tree => Box(tree, "Image00", Marker.PictureKind, White, GameParts), false);
        Piece(NoQuest, false, null, false);
        Piece(NoPin, true, null, true);
        Piece(NotPicture, true, tree => Box(tree, "Image00", 1, White, null), true);
        Piece(Nameless, true, tree => Box(tree, "Image00", Marker.PictureKind, White, null), true);
        _past = Block();
        *(nint*)(screen + Places.MarkerPieces + Past * Places.MarkerPieceSize) = _past;
        if (mods)
        {
            // (1.8.0) The mods' places: 48 whole, 49 without a Quest marker, and a row past the two given.
            Piece(ModWhole, true, tree => Box(tree, "Image00", Marker.PictureKind, White, GameParts), true);
            Piece(ModNoQuest, false, null, false);
            _modPast = Block();
            *(nint*)(screen + Destinations.ScreenRows + ModRows * Destinations.RowSize) = _modPast;
        }
        return screen;
    }

    static string Hex(nint at, int count)
    {
        var bytes = new byte[count];
        Marshal.Copy(at, bytes, 0, count);
        return Convert.ToHexString(bytes);
    }

    /// <summary>Each place's pin as it is: its parts' name, whether its string is that name's, its
    /// part, its color, its glows' (null where it has none).</summary>
    static Dictionary<string, object?> Look()
    {
        var pins = new Dictionary<string, object?>();
        foreach (var (place, (pin, glow, glow00)) in Pins)
        {
            if (pin == 0)
            {
                pins[place.ToString()] = null;
                continue;
            }
            string parts = Read(*(nint*)(pin + Marker.PictureParts));
            uint number = *(uint*)(pin + Marker.PictureParts + 8);
            pins[place.ToString()] = new object?[]
            {
                parts, parts.Length == 0 ? number == 0 : ByValue.TryGetValue(parts, out var text) && text.Number == number,
                *(int*)(pin + Marker.PicturePart), *(uint*)(pin + Marker.BoxColor),
                glow == 0 ? null : *(uint*)(glow + Marker.BoxColor), glow00 == 0 ? null : *(uint*)(glow00 + Marker.BoxColor),
            };
        }
        return pins;
    }

    static int Holders(string value) => ByValue.TryGetValue(value, out var text) ? text.Holders : 0;

    public static int Run(string[] args)
    {
        bool mods = args[0] == "--marker-mods";
        var places = new Places();
        byte* image = Image(places);
        var marker = new Marker(image, places, mods ? ModRows : 0);
        nint screen = Screen(mods);
        uint red = QuestFile.Rgba("#E03030"), purple = QuestFile.Rgba("#A050E0"), green = QuestFile.Rgba("#30C040");
        var steps = new List<Dictionary<string, object?>>();
        var said = new List<string>();
        var shows = new List<object>();
        var asked = new List<int>();

        void Step(string name, Action action)
        {
            Calls.Clear();
            said.Clear();
            shows.Clear();
            asked.Clear();
            action();
            steps.Add(new Dictionary<string, object?>
            {
                ["step"] = name, ["said"] = new List<string>(said), ["calls"] = new List<string>(Calls),
                ["shows"] = new List<object>(shows), ["asked"] = new List<int>(asked), ["pins"] = Look(),
                ["game"] = Holders(GameParts), ["ours"] = Holders(Marker.Parts),
                ["stored"] = Hex(screen + Places.MarkerStates + 9 * Places.MarkerStateSize, Places.MarkerStateSize),
            });
        }

        void Paint(int place, uint color)
        {
            string? words = marker.Paint(screen, place, color);
            if (words != null)
                said.Add(words);
        }

        // The game's own showing of a place, as the stand-in has it: it keeps the state it is given.
        void GameShow(nint at, nint state, int place)
        {
            shows.Add(new object[] { place, Hex(state, Places.MarkerStateSize) });
            if (place >= 0 && place < QuestFile.Places)
                Buffer.MemoryCopy((void*)state, (byte*)at + Places.MarkerStates + place * Places.MarkerStateSize,
                                  Places.MarkerStateSize, Places.MarkerStateSize);
        }

        // A place's state as the game gives it: its marker, the job icon, shown, Loop.
        nint state = Block(Places.MarkerStateSize);
        void Show(int place, byte kind, byte shown, Func<int, uint?> colorAt)
        {
            *(byte*)(state + Marker.Kind) = kind;
            *(int*)(state + 4) = 0x1234;
            *(byte*)(state + Marker.Shown) = shown;
            *(byte*)(state + Marker.Loop) = 0;
            marker.Show(screen, state, place, p => { asked.Add(p); return colorAt(p); }, GameShow, said.Add);
        }

        if (!mods)
        {
            Step("9 given back before any marker is painted", () => marker.Unpaint(screen, 9));
            Step("9 painted red", () => Paint(9, red));
            Step("9 painted purple, already ours", () => Paint(9, purple));
            Step("32 painted green", () => Paint(32, green));
            Step("33, a pin without glows, painted red", () => Paint(PinAlone, red));
            Step("9 given back", () => marker.Unpaint(screen, 9));
            Step("9 given back again", () => marker.Unpaint(screen, 9));
            Step("6, never painted, given back", () => marker.Unpaint(screen, 6));
            Step("20 (no piece), 21 (no Quest marker), 22 (no pin), 23 (a pin not a picture) painted", () =>
            {
                foreach (int place in new[] { NoPiece, NoQuest, NoPin, NotPicture })
                    Paint(place, red);
            });
            Step("20 to 23 given back", () =>
            {
                foreach (int place in new[] { NoPiece, NoQuest, NoPin, NotPicture })
                    marker.Unpaint(screen, place);
            });
            Step("12 painted red, its parts not made ready", () =>
            {
                _ready = 0;
                Paint(12, red);
                _ready = 1;
            });
            Step("12 given back", () => marker.Unpaint(screen, 12));
            Step("6 painted green, the screen's layouts gone", () =>
            {
                *(nint*)(screen + Marker.ScreenLayouts) = 0;
                Paint(6, green);
                *(nint*)(screen + Marker.ScreenLayouts) = (nint)Layouts;
            });
            Step("6 painted green", () => Paint(6, green));
            Step("6, 32 and 33 given back", () =>
            {
                foreach (int place in new[] { 6, 32, PinAlone })
                    marker.Unpaint(screen, place);
            });
            // The screen's showing of a place, as the hook hands it over.
            Step("9 shown, no marker of the game's, red waiting", () => Show(9, 0, 1, _ => red));
            Step("9 shown, nothing waiting", () => Show(9, 0, 1, _ => null));
            Step("9 shown with the game's MidwayPoint marker, red waiting", () => Show(9, 2, 1, _ => red));
            Step("9 hidden, red waiting", () => Show(9, 0, 0, _ => red));
            Step("9 shown, red waiting, then its looking-for failing", () =>
            {
                Show(9, 0, 1, _ => red);
                Show(9, 0, 1, _ => throw new InvalidOperationException("the quests' plan is gone"));
            });
            Step("place 47 (no place), red waiting", () => Show(Past, 0, 1, _ => red));
            Step("22, no pin, shown, red waiting", () => Show(NoPin, 0, 1, _ => red));
            // A helper whose first pin met has a picture with no name: it has nothing to give back, so it paints nothing.
            var fresh = new Marker(image, places);
            Step("40, the first pin a new helper meets, its picture nameless, painted red", () =>
            {
                string? words = fresh.Paint(screen, Nameless, red);
                if (words != null)
                    said.Add(words);
            });
        }
        else
        {
            // (1.8.0) The mods' own places' markers, shown by the helper itself as the screen shows any place.
            var modPlaces = new List<int> { ModWhole, ModNoQuest, ModPast };
            void ShowMods(Func<int, uint?> colorAt)
                => marker.ShowMods(screen, modPlaces, p => { asked.Add(p); return colorAt(p); }, said.Add);
            Step("the mods' places, red waiting at 48", () => ShowMods(p => p == ModWhole ? red : null));
            Step("the mods' places again, nothing changed", () => ShowMods(p => p == ModWhole ? red : null));
            Step("the mods' places, green at 48", () => ShowMods(p => p == ModWhole ? green : null));
            Step("the mods' places, nothing waiting", () => ShowMods(_ => null));
            Step("the mods' places, red at 48 and 49", () => ShowMods(_ => red));
            Step("48's piece made again (the screen set up again), red waiting", () =>
            {
                nint row = screen + Destinations.ScreenRows;
                nint old = *(nint*)row;
                nint again = Block();
                PieceNames[again] = $"place {ModWhole} made again";
                QuestOf[again] = QuestOf[old];
                *(nint*)row = again;
                ShowMods(p => p == ModWhole ? red : null);
            });
            Step("48's row emptied, red waiting", () =>
            {
                nint row = screen + Destinations.ScreenRows;
                nint kept = *(nint*)row;
                *(nint*)row = 0;
                ShowMods(p => p == ModWhole ? red : null);
                *(nint*)row = kept;
            });
            Step("48's piece back in its row, red waiting", () => ShowMods(p => p == ModWhole ? red : null));
            Step("49's row a Quest marker without its pin, red waiting", () =>
            {
                nint row = screen + Destinations.ScreenRows + Destinations.RowSize;
                nint kept = *(nint*)row;
                nint piece = Block(), quest = Block();
                PieceNames[piece] = $"place {ModNoQuest} without its pin";
                QuestOf[piece] = quest;
                PieceNames[quest] = $"place {ModNoQuest}'s Quest without its pin";
                *(nint*)row = piece;
                ShowMods(p => p == ModNoQuest ? red : null);
                *(nint*)row = kept;
            });
            Step("the mods' places, the looking-for failing", () =>
                ShowMods(_ => throw new InvalidOperationException("the quests' plan is gone")));
        }
        var report = new Dictionary<string, object?>
        {
            ["steps"] = steps, ["faults"] = Faults, ["gameParts"] = GameParts, ["ourParts"] = Marker.Parts,
            ["pinPart"] = Marker.PinPart, ["red"] = red, ["purple"] = purple, ["green"] = green,
            ["white"] = White, ["cyan"] = Cyan, ["cyan00"] = Cyan00,
        };
        File.WriteAllText(args[1], JsonSerializer.Serialize(report));
        return 0;
    }
}
