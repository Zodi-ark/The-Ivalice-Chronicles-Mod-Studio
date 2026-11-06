// Mod Studio Framework: (1.23.0) a mod's dungeon's list in its own looks.
// Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi, test 49 (2 November): "After selecting the Old Quarry the dungeon UI
// still said "Midlight's Deep", "About Midlight's Deep", and "Exit
// Midlight's Deep"". His answers: "Exit Old Quarry" (the dungeon's name
// where the game's words name the Deep, in each language), "About Old
// Quarry" (a guide page of the dungeon's own, showing its place's
// description) and "Its own art" (one of the game's places' art or the
// modder's own; the location list shows it too).
//
// A mod's dungeon shows the Deep's own list (Destinations.DungeonStubs), so
// its looks are the Deep's list's, measured in his program (Places.cs,
// MissingForDungeonLooks): its title the UI text 1620, its art its
// Thumbnail's texture, its prompts the button guide 0xBBD's rows ("Exit
// Midlight's Deep", 1607; "Enter"; "About Midlight's Deep", 1614, the T
// key, opening the guide 0xE6's page). Here, while Ramza stands at a mod's
// dungeon (the place the menu is for, Places.CurrentPlace):
// - the UI text 1620 is the dungeon's name, 1607 and 1614 the game's words
//   with the dungeon's name where they name the Deep (Framework.DungeonWords:
//   the Deep's name in the language shown, any capitals);
// - (1.24.0) the world map's prompt to enter it, Enter Settlement (1618:
//   the guide a town gets with the cursor on Ramza's place), the game's words
//   for Enter Midlight's Deep (1626, the Deep's guide's) with the dungeon's
//   name (Zodi's test 54, his answer "Enter Old Quarry");
// - the guide's page of the About key, while its list is up (the frame's
//   mode 4), is the dungeon's own (Framework.AboutPage: its name and its
//   description); a dungeon without a description has no About prompt and
//   its T key opens nothing;
// - as a dungeon's list is about to open (the entries' hook), its title is
//   made again from its text and its Thumbnail given the place's Town row's
//   art (the Deep's own 18 at the Deep; a mod's dungeon's its own:
//   Destinations.TownRow), by the game's own setter.
// Nothing here throws into the game (Hooks.cs says a fault once).
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

namespace ModStudioEventSetup
{
    public sealed unsafe class DungeonLooks
    {
        /// <summary>The Deep's list's title's boxes, from the layout's root (worldmap_deep_dungeon_ver02.uib).</summary>
        static readonly string[] TitlePath = { "DeepDungeon", "DeepDungeonList", "Title", "Text00" };
        const int StringBytes = 16;
        /// <summary>A layout's pieces (its list from + 0x68 to + 0x70) and its root's kind (+ 0x218, 1), as 0x3F9DA0
        /// finds the root.</summary>
        const int LayoutPieces = 0x68, LayoutPiecesEnd = 0x70, PieceKind = 0x218, RootKind = 1;
        /// <summary>A base art's path's room (0x158CB0's).</summary>
        const int ArtPathBytes = 0x104;
        public const int DeepPlace = 22;

        readonly byte* _base;
        readonly Places _places;
        readonly IReadOnlyDictionary<int, Framework.DungeonPlan> _dungeons;
        readonly nint _names;
        /// <summary>Each mod's dungeon's name (UTF-8, NUL ended) and About page (Framework.AboutPage), by its place.</summary>
        readonly Dictionary<int, nint> _titles = new Dictionary<int, nint>();
        readonly Dictionary<int, nint> _pages = new Dictionary<int, nint>();
        /// <summary>The words made for a dungeon: by its place, the text's number, the game's words and the Deep's name.</summary>
        readonly Dictionary<(int Place, int Text, string Game, string Deep), nint> _words =
            new Dictionary<(int, int, string, string), nint>();

        public DungeonLooks(byte* start, Places places, IReadOnlyDictionary<int, Framework.DungeonPlan> dungeons)
        {
            _base = start;
            _places = places;
            _dungeons = dungeons;
            int characters = 0;
            foreach (var name in TitlePath)
                characters += name.Length + 1;
            _names = (nint)NativeMemory.AllocZeroed((nuint)(TitlePath.Length * StringBytes + characters));
            byte* text = (byte*)_names + TitlePath.Length * StringBytes;
            for (int n = 0; n < TitlePath.Length; n++)
            {
                *(nint*)(_names + n * StringBytes) = (nint)text;
                foreach (char c in TitlePath[n])
                    *text++ = (byte)c;
                *text++ = 0;
            }
            foreach (var (number, dungeon) in dungeons)
            {
                _titles[number] = Copy(Encoding.UTF8.GetBytes(dungeon.Place.Name));
                if (Framework.HasAbout(dungeon))
                {
                    var page = Framework.AboutPage(dungeon.Place.Name, dungeon.Place.Description);
                    nint copy = (nint)NativeMemory.Alloc((nuint)page.Length);
                    Marshal.Copy(page, 0, copy, page.Length);
                    _pages[number] = copy;
                }
            }
        }

        static nint Copy(byte[] utf8)
        {
            nint at = (nint)NativeMemory.AllocZeroed((nuint)(utf8.Length + 1));
            Marshal.Copy(utf8, 0, at, utf8.Length);
            return at;
        }

        static string Read(nint utf8)
        {
            if (utf8 == 0)
                return "";
            int length = 0;
            while (length < 4096 && *((byte*)utf8 + length) != 0)
                length++;
            return Encoding.UTF8.GetString((byte*)utf8, length);
        }

        /// <summary>The mod's dungeon Ramza stands at (the menu's place), or null.</summary>
        Framework.DungeonPlan? Here()
            => _dungeons.TryGetValue(*(int*)(_base + _places.CurrentPlace), out var dungeon) ? dungeon : null;

        /// <summary>The world map's frame (the UI's root, + 0x10, + 0xA0), or 0.</summary>
        nint Frame()
        {
            nint at = *(nint*)(_base + _places.UiRoot);
            if (at == 0)
                return 0;
            at = *(nint*)(at + Places.UiFirst);
            return at == 0 ? 0 : *(nint*)(at + Places.UiMenus);
        }

        /// <summary>The UI text `number` at a mod's dungeon (its title its name; Exit and About the game's words,
        /// `game`, with its name; 1.24.0, the world map's Enter Settlement the game's Enter Midlight's Deep with its
        /// name), or 0: the game's own.</summary>
        public nint Text(int number, Func<int, nint> game)
        {
            if (number != Places.TitleText && number != Places.ExitText && number != Places.AboutText
                && number != Places.SettlementText)
                return 0;
            var dungeon = Here();
            if (dungeon == null)
                return 0;
            if (number == Places.TitleText)
                return _titles.TryGetValue(dungeon.Number, out nint title) ? title : 0;
            string words = Read(game(number == Places.SettlementText ? Places.EnterDeepText : number));
            string deep = Read(((delegate* unmanaged<int, nint>)(_base + _places.PlaceNameText))(Places.DeepNameText));
            var key = (dungeon.Number, number, words, deep);
            if (!_words.TryGetValue(key, out nint made))
            {
                made = Copy(Encoding.UTF8.GetBytes(Framework.DungeonWords(words, deep, dungeon.Place.Name)));
                _words[key] = made;
            }
            return made;
        }

        /// <summary>The guide's page (sheet, guide, page) at a mod's dungeon while its list is up: its About page, or 0
        /// (the game's own). `opened` is told the dungeon whose page it was.</summary>
        public nint Page(int sheet, int key, int key2, Action<Framework.DungeonPlan>? opened = null)
        {
            if (sheet != Places.PageSheet || key != _places.AboutGuide || key2 != 0)
                return 0;
            var dungeon = Here();
            nint frame = Frame();
            if (dungeon == null || frame == 0 || *(int*)(frame + Places.FrameMode) != Places.DeepListMode)
                return 0;
            if (!_pages.TryGetValue(dungeon.Number, out nint page))
                return 0;
            opened?.Invoke(dungeon);
            return page;
        }

        /// <summary>The button guide's rows shown: the Deep's list's About row not at a mod's dungeon without an About
        /// page.</summary>
        public int Rows(int guide, int rows)
            => guide == _places.DeepGuide && Here() is { } dungeon && !Framework.HasAbout(dungeon)
                ? rows & ~(1 << Places.AboutRow) : rows;

        /// <summary>Whether the About key opens its guide: not at a mod's dungeon without an About page.</summary>
        public bool AboutOpens() => !(Here() is { } dungeon && !Framework.HasAbout(dungeon));

        /// <summary>A dungeon's list about to open (the Deep's or a mod's dungeon's): its title made again from its text,
        /// its Thumbnail given the place's art (its Town row's); the dungeon, or null for a place of neither.</summary>
        public Framework.DungeonPlan? Dress(int place)
        {
            if (place != DeepPlace && !_dungeons.ContainsKey(place))
                return null;
            _dungeons.TryGetValue(place, out var dungeon);
            nint frame = Frame();
            nint deep = frame == 0 ? 0 : *(nint*)(frame + Places.FrameDeep);
            if (deep == 0)
                return dungeon;
            nint title = Title(deep);
            if (title != 0 && *(int*)(title + Marker.BoxKind) == Places.TextKind
                && *(int*)(title + Places.TextNumber) == Places.TitleText)
            {
                *(byte*)(title + Places.TextRemade) = 1;
                ((delegate* unmanaged<nint, void>)(_base + _places.TextRemake))(title);
            }
            nint thumbnail = *(nint*)(deep + Places.DeepThumbnail);
            nint row = ((delegate* unmanaged<int, int, nint>)(_base + _places.RowLookup))(Destinations.TownSheet, place);
            if (thumbnail != 0 && *(int*)(thumbnail + Marker.BoxKind) == Marker.PictureKind && row != 0)
            {
                byte* path = stackalloc byte[ArtPathBytes];
                path[0] = 0;
                ((delegate* unmanaged<nint, int, int, int>)(_base + _places.BaseArt))((nint)path,
                                                                                     *(int*)(row + Destinations.TownArt),
                                                                                     ArtPathBytes);
                if (path[0] != 0)
                    ((delegate* unmanaged<nint, nint, nint, void>)(_base + _places.ArtSetter))(deep, thumbnail, (nint)path);
            }
            return dungeon;
        }

        /// <summary>The Deep's list's title's text box, or 0: from its layout's root, its pieces and the box by
        /// name.</summary>
        nint Title(nint deep)
        {
            nint layouts = *(nint*)(deep + Places.UiLayouts);
            if (layouts == 0)
                return 0;
            nint at = 0;
            for (nint* piece = *(nint**)(layouts + LayoutPieces); piece != null
                 && piece != *(nint**)(layouts + LayoutPiecesEnd); piece++)
                if (*piece != 0 && *(int*)(*piece + PieceKind) == RootKind)
                {
                    at = *piece;
                    break;
                }
            var child = (delegate* unmanaged<nint, nint, nint>)(_base + _places.ChildPiece);
            var boxNamed = (delegate* unmanaged<nint, nint, nint>)(_base + _places.BoxNamed);
            for (int n = 0; n < TitlePath.Length - 1 && at != 0; n++)
                at = child(at, _names + n * StringBytes);
            return at == 0 ? 0 : boxNamed(at + Marker.PieceTree, _names + (TitlePath.Length - 1) * StringBytes);
        }
    }
}
