// Mod Studio Framework: (1.19.0) a mod's town's own art and own picture in
// its menu (Zodi's list, his fifth: "a town's menu at a mod's own town"; its
// art "Just like the map place icon the modder should be able to chose
// between using their own or a game town's"); (1.23.0) a mod's dungeon's own
// art in its list and its location info alike (his answer after test 49).
// Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// A town's menu (Enter Settlement) and its location info show its art from
// its Town row's + 0x1C (the base art's path by that number: 0xFC1C0, the
// thumbnail's, made ready and given its box by the game's own setter) and,
// in the menu, its town picture by playing TexChange of the row's + 0x2C
// (0x158E30). A town with its own art is numbered OwnArt plus its place's
// number (Destinations.TownRow), whose path the base art's hook writes: its
// own files' (PlaceFile.PartsName and its art's name). A town with its own
// picture has no TexChange of the game's (+ 0x2C -1): the menu's town
// picture's hook gives the menu's picture box its own picture's parts, part 1,
// made ready with the menu's layouts as the game makes the thumbnail's, and
// gives the box back its own parts and part before a game town's TexChange
// plays. Nothing here throws into the game (PlaceHooks).
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

namespace ModStudioEventSetup
{
    public sealed unsafe class MenuArt
    {
        const int StringBytes = 16, StringNumber = 8;
        /// <summary>The menu's town picture's own box (worldmap_base_menu.uib's IconBase/Icon).</summary>
        public const string IconBox = "Icon";
        /// <summary>A town's own picture's part (its part list's part 1, as on the map).</summary>
        public const int PicturePart = 1;

        readonly byte* _base;
        readonly Places _places;
        /// <summary>Each town's own art's path by its place's number (its Town row's art less OwnArt), as ASCII.</summary>
        readonly Dictionary<int, byte[]> _arts = new Dictionary<int, byte[]>();
        /// <summary>Each town's own picture's parts' name by its place's number (characters, NUL ended).</summary>
        readonly Dictionary<int, nint> _icons = new Dictionary<int, nint>();
        /// <summary>The box's name looked for (a string of the game's: its characters' address first).</summary>
        readonly nint _iconName;
        /// <summary>The menu's picture box the helper gave a town's own picture, and what it had before (its parts'
        /// name, NUL ended, and its part), given back before a game town's TexChange plays.</summary>
        nint _changed, _keptParts;
        int _keptPart;

        public MenuArt(byte* start, Places places, List<Destination> destinations)
        {
            _base = start;
            _places = places;
            foreach (var d in destinations)
            {
                // (1.23.0) A dungeon's own art: its list's and its location info's, by its number as a town's own.
                if (d.Place.Dungeon && d.Place.DungeonArtPicture.Length > 0)
                    _arts[d.Number] = Encoding.ASCII.GetBytes(d.Place.DungeonArtParts);
                var menu = d.Place.Town ? d.Place.Menu : null;
                if (menu == null)
                    continue;
                if (menu.ArtPicture.Length > 0)
                    _arts[d.Number] = Encoding.ASCII.GetBytes(menu.ArtParts);
                if (d.Place.Picture.Length > 0)
                    _icons[d.Number] = Chars(d.Place.Parts);
            }
            _iconName = (nint)NativeMemory.AllocZeroed(StringBytes);
            *(nint*)_iconName = Chars(IconBox);
        }

        public bool HasArts => _arts.Count > 0;
        public bool HasIcons => _icons.Count > 0;

        static nint Chars(string text)
        {
            var bytes = Encoding.ASCII.GetBytes(text + "\0");
            nint at = (nint)NativeMemory.AllocZeroed((nuint)bytes.Length);
            Marshal.Copy(bytes, 0, at, bytes.Length);
            return at;
        }

        /// <summary>The path a base art's number names when it is a town's own (OwnArt plus its place's number), as
        /// ASCII; null for any other (the game's own path).</summary>
        public byte[]? PathOf(int number)
            => number >= Destinations.OwnArt && _arts.TryGetValue(number - Destinations.OwnArt, out var path) ? path
               : null;

        /// <summary>A town's own art's path written into the base art's buffer (`size` bytes, NUL ended), as the
        /// game's own writes its: its length, or -1 for a number not a town's own (the game's own then).</summary>
        public int WriteArt(nint buffer, int number, int size)
        {
            var path = PathOf(number);
            if (path == null || buffer == 0 || size <= 0)
                return -1;
            int length = Math.Min(path.Length, size - 1);
            Marshal.Copy(path, 0, buffer, length);
            *(byte*)(buffer + length) = 0;
            return length;
        }

        /// <summary>The menu's UI object (from the UI's root), or 0.</summary>
        nint MenuUi()
        {
            nint at = *(nint*)(_base + _places.UiRoot);
            foreach (int step in new[] { Places.UiFirst, Places.UiMenus, Places.UiMenu })
            {
                if (at == 0)
                    return 0;
                at = *(nint*)(at + step);
            }
            return at;
        }

        /// <summary>The menu's town picture for a mod's town with its own picture: the menu's picture box given its
        /// parts (made ready with the menu's layouts) and part 1, what it had kept; true when given (the game's own
        /// TexChange then not played). False for any other place or piece (the game's own).</summary>
        public bool GiveIcon(nint piece, int place)
        {
            if (!_icons.TryGetValue(place, out nint parts))
                return false;
            nint ui = MenuUi();
            if (ui == 0 || *(nint*)(ui + Places.UiMenuIcon) != piece)
                return false;
            nint box = Box(piece);
            nint layouts = *(nint*)(ui + Places.UiLayouts);
            var ready = (delegate* unmanaged<nint, nint, byte, byte>)(_base + _places.PartsReady);
            if (box == 0 || layouts == 0 || ready(layouts, parts, 0) == 0)
                return false;
            if (_changed != box)
            {
                Keep(box);
                _changed = box;
            }
            SetString(box + Marker.PictureParts, parts);
            *(int*)(box + Marker.PicturePart) = PicturePart;
            return true;
        }

        /// <summary>Before a game town's TexChange plays on the menu's picture box: its own parts and part given back
        /// when the helper gave it a town's own picture.</summary>
        public void GiveBack(nint piece)
        {
            if (_changed == 0)
                return;
            nint ui = MenuUi();
            if (ui == 0 || *(nint*)(ui + Places.UiMenuIcon) != piece)
                return;
            nint box = Box(piece);
            if (box != _changed)
            {
                // Another box (the menu made again): its own as it was made.
                _changed = 0;
                return;
            }
            nint layouts = *(nint*)(ui + Places.UiLayouts);
            var ready = (delegate* unmanaged<nint, nint, byte, byte>)(_base + _places.PartsReady);
            if (_keptParts != 0 && layouts != 0 && ready(layouts, _keptParts, 0) != 0)
                SetString(box + Marker.PictureParts, _keptParts);
            *(int*)(box + Marker.PicturePart) = _keptPart;
            _changed = 0;
        }

        /// <summary>A piece's picture box (IconBox, a picture), or 0.</summary>
        nint Box(nint piece)
        {
            var boxNamed = (delegate* unmanaged<nint, nint, nint>)(_base + _places.BoxNamed);
            nint box = boxNamed(piece + Marker.PieceTree, _iconName);
            return box != 0 && *(int*)(box + Marker.BoxKind) == Marker.PictureKind ? box : 0;
        }

        /// <summary>What a box shows kept: its parts' name (copied) and part.</summary>
        void Keep(nint box)
        {
            if (_keptParts != 0)
                NativeMemory.Free((void*)_keptParts);
            _keptParts = 0;
            byte* name = *(byte**)(box + Marker.PictureParts);
            if (name != null)
            {
                int length = 0;
                while (length < 512 && name[length] != 0)
                    length++;
                if (length < 512)
                {
                    _keptParts = (nint)NativeMemory.AllocZeroed((nuint)(length + 1));
                    Buffer.MemoryCopy(name, (void*)_keptParts, length + 1, length);
                }
            }
            _keptPart = *(int*)(box + Marker.PicturePart);
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
    }
}
