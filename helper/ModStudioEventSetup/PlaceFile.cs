// Mod Studio Framework: (1.3.0) reading a mod's own place on the world
// map. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi, 26 October, of new places: "we should do "real new places, built in
// steps" because the pay off would be a tremendous achievement and one of
// the best possible practices for the longevity of the Ivalice Chronicles
// modding scene." Its first step: a mod's place shown on the world map, a
// piece of the map's layout added as the game sets the map up (MapPieces.cs),
// pictures only (no roads to it yet, no travel, no quests at it). A place is
// a folder of its own in a mod, `ModStudioPlaces/<place>/`, holding
// `place.json`: its name, its kind (a town, its picture of 172 x 172 the
// mod's own or one of the game's; or a battle ground, the game's point), and
// where its middle is on the world map. A town's own picture is a texture
// and its part list at the game's paths in the mod, which the mod loader
// serves (`FFTIVC/data/enhanced/ui/ffto/worldmap/texture/<Picture>.tex` and
// `.../textureparts/<Picture>.utexpt`, its part 1). Mod Studio writes it
// (`mod_studio/map_places.py` reads and writes the same file and says the
// same problems); what can't be used is left out and said. A modder never
// chooses a number: places have names.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace ModStudioEventSetup
{
    /// <summary>A mod's own place on the world map, as its mod gives it.</summary>
    public sealed class MapPlace
    {
        public string ModId { get; }
        public string ModName { get; }
        public string Folder { get; }
        public string Name { get; }
        /// <summary>A town (a Base piece, its picture) or a battle ground (a Point piece, the game's point).</summary>
        public bool Town { get; }
        /// <summary>Where its middle is on the world map, in the map's pixels (3840 x 2288).</summary>
        public int X { get; }
        public int Y { get; }
        /// <summary>A town's own picture: its files' name (its part list's name, part 1), or "".</summary>
        public string Picture { get; }
        /// <summary>A town's picture of the game's: one of its town pictures by name ("07"), or "".</summary>
        public string Icon { get; }
        /// <summary>(1.16.0) Its description, as the world map's location info shows a place's under its name (its
        /// Town row's Description), or "".</summary>
        public string Description { get; }
        /// <summary>(1.17.0) A battle ground's own random battles (none: no random battle there), and how many of 100
        /// arrivals start one (choosing to fight where you stand always does).</summary>
        public List<PlaceBattle> Battles { get; }
        public int Chance { get; }
        /// <summary>(1.18.0) A town's own menu (Enter Settlement), or null: none, as the game's places that have no
        /// settlement to enter.</summary>
        public TownMenu? Menu { get; }
        /// <summary>(1.20.0) What darkens a town on the world map once set (one of its mod's quests' flags), or null:
        /// never darkened.</summary>
        public PlaceDarkened? Darkened { get; }
        /// <summary>(1.21.0) A dungeon's floors (Zodi's list, his seventh: a place like Midlight's Deep, choosing it
        /// listing its floors, choosing one starting one of its random battles), each in the list's order; none, not a
        /// dungeon. A dungeon is drawn as a town is (its picture), and has no Menu: its floors are its list.</summary>
        public List<PlaceFloor> Floors { get; }
        public bool Dungeon => Floors.Count > 0;
        /// <summary>(1.23.0) A dungeon's art (Zodi's answer after test 49: "Its own art", the modder picking one of the
        /// game's places' art or their own texture, as a town's menu art; the location list shows it too): the game's
        /// place whose art its list shows (one of those with art: 0 to 19, or 21 to 23; Midlight's Deep's, 22, when its
        /// file names none), or -1 for its own (DungeonArtPicture: its two files' name).</summary>
        public int DungeonArt { get; }
        public string DungeonArtPicture { get; }
        /// <summary>The part list's name the game makes a dungeon's own art's parts ready by, or "".</summary>
        public string DungeonArtParts => PlaceFile.PartsOf(DungeonArtPicture);

        public MapPlace(string modId, string modName, string folder, string name, bool town, int x, int y,
                        string picture, string icon, string description = "", int chance = 0,
                        List<PlaceBattle>? battles = null, TownMenu? menu = null, PlaceDarkened? darkened = null,
                        List<PlaceFloor>? floors = null, int dungeonArt = PlaceFile.DeepPlace, string dungeonArtPicture = "")
        {
            ModId = modId;
            ModName = modName;
            Folder = folder;
            Name = name;
            Town = town;
            X = x;
            Y = y;
            Picture = picture;
            Icon = icon;
            Description = description;
            Chance = chance;
            Battles = battles ?? new List<PlaceBattle>();
            Menu = menu;
            Darkened = darkened;
            Floors = floors ?? new List<PlaceFloor>();
            DungeonArtPicture = dungeonArtPicture;
            DungeonArt = dungeonArtPicture.Length > 0 ? -1 : dungeonArt;
        }

        /// <summary>The part list's name the game makes a picture's parts ready by.</summary>
        public string Parts => PlaceFile.PartsOf(Picture);
    }

    /// <summary>(1.21.0) One of a dungeon's floors, as its place's file gives it (Zodi's choices: "each floor waiting
    /// for a quest flag the modder picks, or showing from the start if none is picked", and "a few random battles per
    /// floor"): its name and description (shown in the dungeon's list, as Midlight's Deep shows its floors'), the quest
    /// flag it waits for (Opens: one of its mod's quests, by its folder's name, and that quest's flag; null, listed
    /// from the start) and its random battles (1 to 8, one picked evenly each time the floor is chosen). (1.24.0) Or,
    /// AfterWin, listed once the floor before it is won (Zodi, 2 November: "after they defeat all enemies the next
    /// floor becomes available and so on"; his choice "Win once": any one of its battles won once lists it from then
    /// on): its Opens "FloorBeforeWon", never the first floor's.</summary>
    public sealed class PlaceFloor
    {
        public string Name { get; }
        public string Description { get; }
        public PlaceDarkened? Opens { get; }
        public List<PlaceBattle> Battles { get; }
        public bool AfterWin { get; }

        public PlaceFloor(string name, string description, PlaceDarkened? opens, List<PlaceBattle> battles,
                          bool afterWin = false)
        {
            Name = name;
            Description = description;
            Opens = afterWin ? null : opens;
            Battles = battles;
            AfterWin = afterWin;
        }
    }

    /// <summary>(1.20.0) What darkens a mod's town on the world map, as the game darkens its own places once their
    /// event is done (Zodi's list, his sixth: Ziekden Fortress, Brigands' Den, Nelveska Temple, Fort Besselat,
    /// Mullonde, Golgollada Gallows): one of its mod's quests (by its folder's name) and that quest's flag. Once the
    /// flag is set, its texture is drawn darkened (its piece's Color_Grayout, as the game's: 155 of 255).</summary>
    public sealed class PlaceDarkened
    {
        public string Quest { get; }
        public string Flag { get; }

        public PlaceDarkened(string quest, string flag)
        {
            Quest = quest;
            Flag = flag;
        }
    }

    /// <summary>(1.17.0) One of a battle ground's own random battles, as its place's file gives it (Zodi's list, his
    /// fifth: "A battle on a mod's own battle ground", his choice "Its own battles").</summary>
    public sealed class PlaceBattle
    {
        public string Name { get; }
        /// <summary>Its own units (640 bytes, its file in the place's folder), or null for one of the game's battles
        /// (GameUnits).</summary>
        public byte[]? Units { get; }
        public int GameUnits { get; }
        /// <summary>One of the game's maps by its number (Map), or one of the mod's quest maps by its name (MapName,
        /// else "").</summary>
        public int Map { get; }
        public string MapName { get; }
        /// <summary>Where the player's units start: one deploy area of its own (the game's random battles start
        /// them on one squad).</summary>
        public List<DeployArea> Deploy { get; }
        /// <summary>The story's progress it waits for (variable 110 at least it), or -1 from the start.</summary>
        public int From { get; }

        public PlaceBattle(string name, byte[]? units, int gameUnits, int map, string mapName, List<DeployArea> deploy,
                           int from)
        {
            Name = name;
            Units = units;
            GameUnits = gameUnits;
            Map = map;
            MapName = mapName;
            Deploy = deploy;
            From = from;
        }
    }

    /// <summary>(1.18.0) A town's own menu (Enter Settlement), as its place's file gives it (Zodi's list, his fifth:
    /// "a town's menu at a mod's own town", his choice "Its own"): the game's town (by its place, 0 to 14) whose art
    /// the menu shows, its Outfitter's items (the game's, by number: each sold once the story reaches the point the
    /// game's own shops start selling it), and whether it has a Poachers' Den (open once the story opens the game's
    /// own). Its tavern tells the side quests' rumors that name the town and the game's told in every tavern, and has
    /// no errands (each of the game's names one of its towns); its Warriors' Guild is the game's.</summary>
    public sealed class TownMenu
    {
        /// <summary>The game's town (0 to 14) whose art it shows, or -1 for its own (ArtPicture).</summary>
        public int Art { get; }
        public List<int> Shop { get; }
        public bool Poachers { get; }
        /// <summary>(1.19.0) Its own art's files' name (its part list's name, part 0 the art), or "".</summary>
        public string ArtPicture { get; }

        /// <summary>(1.26.0) Its Outfitter's own items: the mod's items (ItemFile) by their names, sold after the game's
        /// items it sells.</summary>
        public List<string> OwnItems { get; }

        public TownMenu(int art, List<int> shop, bool poachers, string artPicture = "", List<string>? ownItems = null)
        {
            Art = artPicture.Length > 0 ? -1 : art;
            Shop = shop;
            Poachers = poachers;
            ArtPicture = artPicture;
            OwnItems = ownItems ?? new List<string>();
        }

        /// <summary>The part list's name the game makes its own art's parts ready by, or "".</summary>
        public string ArtParts => PlaceFile.PartsOf(ArtPicture);
    }

    public static class PlaceFile
    {
        /// <summary>The folder of a mod that holds its own places, one folder each.</summary>
        public const string Folder = "ModStudioPlaces";
        public const string Name = "place.json";
        public const string Format = "Mod Studio place";
        public const int Version = 1;
        /// <summary>The world map's picture (MapAll's Map, ui_wm_map_uitx): where a place's middle may be.</summary>
        public const int MapWidth = 3840, MapHeight = 2288;
        /// <summary>The game's town pictures, by their names in ui_wm_icon_base_uitx (each a TexChange of the
        /// map's Base piece).</summary>
        public static readonly string[] Icons =
        {
            "01", "03", "05", "07", "10", "11", "14_34", "15", "17", "19", "20", "22", "23", "24", "26", "28", "30",
            "32", "35", "38", "40", "41", "42",
        };
        /// <summary>(1.16.0) A place's description at the most: the location info's two lines (its detail box,
        /// `wm_location_info.uib`'s text_detail: 1750 by 106 at 28 points, a line 44 high), the game's own 80 to 160
        /// characters, one line break among them at the most.</summary>
        public const int MostDescription = 200;
        /// <summary>(1.17.0) A battle ground's random battles: one to eight (as many formations as each entrance of
        /// the game's battle grounds has), started on up to 100 of 100 arrivals (the game's own: 31 of 100, a roll of
        /// 0 to 99 at most 30); the story's progress a battle may wait for (variable 110, as the world map's own tests
        /// compare it: up to 65535).</summary>
        public const int MostBattles = 8, MostChance = 100, MostFrom = 65535;
        /// <summary>(1.18.0) A town's menu: its art one of the game's 15 towns' (places 0 to 14, each its own art and
        /// Outfitter); its Outfitter's items numbered as the game's shops list them (1 to 255: the stock's loop counts
        /// 256, 0 none).</summary>
        public const int MostArtTown = 14, MostItem = 255;
        /// <summary>(1.21.0) A dungeon's floors: one to ten (as many as Midlight's Deep lists: a settlement menu holds
        /// ten entries, 0x5C bytes from + 0x34, and the Deep's list marks ten), each named in 1 to 24 characters (the
        /// Deep's own names are 3 to 11).</summary>
        public const int MostFloors = 10, MostFloorName = 24;
        /// <summary>(1.24.0) A floor's Opens when it is listed once the floor before it is won (PlaceFloor.AfterWin).</summary>
        public const string FloorBeforeWon = "FloorBeforeWon";
        /// <summary>(1.23.0) The game's places a dungeon's art may be (their Town rows' art, + 0x1C: the towns 0 to 14
        /// and the other places with a settlement picture, 15 to 19 and 21 to 23; 20 has none), and the one a dungeon
        /// shows when its file names none: Midlight's Deep's.</summary>
        public const int MostArtPlace = 23, NoArtPlace = 20, DeepPlace = 22;

        /// <summary>(1.23.0) Whether a game's place's art may be a dungeon's.</summary>
        public static bool GoodArtPlace(int place) => place >= 0 && place <= MostArtPlace && place != NoArtPlace;
        /// <summary>Where a town's own picture's files are in its mod (the game's paths, which the mod loader
        /// serves), and the part list's name the game knows it by.</summary>
        public const string TextureFolder = "FFTIVC/data/enhanced/ui/ffto/worldmap/texture";
        public const string PartsFolder = "FFTIVC/data/enhanced/ui/ffto/worldmap/textureparts";
        public const string PartsName = "UITextureParts://ui/ffto/worldmap/textureparts/";

        public static string PartsOf(string picture) => picture.Length == 0 ? "" : PartsName + picture;

        /// <summary>A picture's files' name: small letters, digits and _, 1 to 64 of them.</summary>
        public static bool GoodPicture(string name)
        {
            if (name.Length == 0 || name.Length > 64)
                return false;
            foreach (char c in name)
                if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_'))
                    return false;
            return true;
        }

        /// <summary>Every place of a mod, in its folders' order; what can't be used goes in problems.</summary>
        public static List<MapPlace> ReadMod(string modId, string modName, string modFolder, List<string> problems)
        {
            var places = new List<MapPlace>();
            string root = Path.Combine(modFolder, Folder);
            if (!Directory.Exists(root))
                return places;
            var folders = new List<string>(Directory.GetDirectories(root));
            folders.Sort(StringComparer.Ordinal);
            var mapNames = MapFile.NamesIn(modFolder);
            foreach (var folder in folders)
            {
                string file = Path.Combine(folder, Name);
                if (!File.Exists(file))
                    continue;
                string folderName = Path.GetFileName(folder);
                var said = new List<string>();
                MapPlace? place = null;
                string own = folder;
                try
                {
                    place = Read(modId, modName, folderName, File.ReadAllText(file),
                                 path => File.Exists(Path.Combine(modFolder, path)), said,
                                 n => File.ReadAllBytes(Path.Combine(own, n)), mapNames);
                }
                catch (Exception e) when (e is not OutOfMemoryException)
                {
                    said.Add($"it can't be read ({e.Message})");
                }
                if (place != null && places.Exists(p => p.Name == place.Name))
                {
                    said.Add($"another of the mod's places is named {place.Name}");
                    place = null;
                }
                foreach (var s in said)
                    problems.Add($"{modName}'s place {folderName}: {s}");
                if (place != null)
                    places.Add(place);
            }
            return places;
        }

        static bool Has(JsonElement e, string name, out JsonElement value)
        {
            foreach (var p in e.EnumerateObject())
                if (string.Equals(p.Name, name, StringComparison.OrdinalIgnoreCase))
                {
                    value = p.Value;
                    return true;
                }
            value = default;
            return false;
        }

        static string Text(JsonElement e, string name)
            => Has(e, name, out var value) && value.ValueKind == JsonValueKind.String ? value.GetString() ?? "" : "";

        /// <summary>A place from its file's text; null when it can't be used, why in problems. `hasFile`
        /// says whether the mod has a file (its path from the mod's folder); (1.17.0) `readOwn` reads a file of the
        /// place's folder by name, `mapNames` the mod's quest maps' names, which a random battle may name.</summary>
        public static MapPlace? Read(string modId, string modName, string folder, string text, Func<string, bool> hasFile,
                                     List<string> problems, Func<string, byte[]>? readOwn = null,
                                     ICollection<string>? mapNames = null)
        {
            JsonDocument document;
            try
            {
                document = JsonDocument.Parse(text);
            }
            catch (JsonException e)
            {
                problems.Add($"its {Name} isn't JSON ({e.Message})");
                return null;
            }
            using (document)
            {
                var top = document.RootElement;
                if (top.ValueKind != JsonValueKind.Object)
                {
                    problems.Add($"its {Name} isn't a list of fields");
                    return null;
                }
                if (QuestFile.BrokenText(top))
                {
                    problems.Add($"its {Name} {QuestFile.BrokenTextSaid}");
                    return null;
                }
                if (Text(top, "Format") != Format || !Has(top, "Version", out var v) || v.ValueKind != JsonValueKind.Number
                    || !v.TryGetInt32(out int version) || version != Version)
                {
                    problems.Add($"its {Name} isn't a \"{Format}\" file of version {Version}");
                    return null;
                }
                int before = problems.Count;
                string name = Text(top, "Name");
                if (name.Length == 0)
                    name = folder;
                bool town = true, dungeon = false;
                if (!Has(top, "Kind", out var kind))
                    problems.Add("it has no Kind (Town, Battle or Dungeon)");
                else if (kind.ValueKind == JsonValueKind.String && kind.GetString() == "Town")
                    town = true;
                else if (kind.ValueKind == JsonValueKind.String && kind.GetString() == "Battle")
                    town = false;
                // (1.21.0) A dungeon: drawn as a town is, its floors its list.
                else if (kind.ValueKind == JsonValueKind.String && kind.GetString() == "Dungeon")
                    dungeon = true;
                else
                    problems.Add($"its Kind is Town, Battle or Dungeon, not {kind.GetRawText()}");
                int x = 0, y = 0;
                if (!Has(top, "At", out var at))
                    problems.Add("it has no At (where its middle is on the world map)");
                else if (!Point(at, out x, out y))
                    problems.Add($"its At is where its middle is on the world map, two whole numbers from 0 to "
                                 + $"{MapWidth} and 0 to {MapHeight}, not {at.GetRawText()}");
                string picture = "", icon = "";
                bool hasPicture = Has(top, "Picture", out var pictureValue);
                bool hasIcon = Has(top, "Icon", out var iconValue);
                if (hasPicture)
                {
                    string given = pictureValue.ValueKind == JsonValueKind.String ? pictureValue.GetString() ?? "" : "";
                    if (GoodPicture(given))
                        picture = given;
                    else
                        problems.Add("its Picture is its texture's files' name (small letters, digits and _, 1 to 64 of "
                                     + $"them), not {pictureValue.GetRawText()}");
                }
                if (hasIcon)
                {
                    string given = iconValue.ValueKind == JsonValueKind.String ? iconValue.GetString() ?? "" : "";
                    if (Array.IndexOf(Icons, given) >= 0)
                        icon = given;
                    else
                        problems.Add($"its Icon is one of the game's town textures ({string.Join(", ", Icons)}), not "
                                     + iconValue.GetRawText());
                }
                // (1.16.0) Its description, if it has one.
                string description = "";
                if (Has(top, "Description", out var descriptionValue))
                {
                    string given = descriptionValue.ValueKind == JsonValueKind.String
                        ? descriptionValue.GetString() ?? "" : "";
                    if (descriptionValue.ValueKind == JsonValueKind.String && GoodDescription(given))
                        description = given;
                    else
                        problems.Add($"its Description is words of 1 to {MostDescription} characters, at most one line "
                                     + $"break among them, not {descriptionValue.GetRawText()}");
                }
                // (1.17.0) A battle ground's own random battles, if it has them.
                int chance = 0;
                var battles = new List<PlaceBattle>();
                bool hasBattles = Has(top, "RandomBattles", out var randomBattles);
                if (hasBattles)
                    chance = ReadRandomBattles(randomBattles, readOwn, mapNames ?? Array.Empty<string>(), battles,
                                               problems);
                // (1.18.0) A town's own menu, if it has one.
                TownMenu? menu = null;
                bool hasMenu = Has(top, "Menu", out var menuValue);
                if (hasMenu)
                    menu = ReadMenu(menuValue, problems);
                // (1.20.0) What darkens a town, if anything does.
                PlaceDarkened? darkened = null;
                bool hasDarkened = Has(top, "Darkened", out var darkenedValue);
                if (hasDarkened)
                    darkened = ReadDarkened(darkenedValue, problems);
                // (1.21.0) A dungeon's floors.
                var floors = new List<PlaceFloor>();
                bool hasFloors = Has(top, "Floors", out var floorsValue);
                if (hasFloors && dungeon)
                    ReadFloors(floorsValue, readOwn, mapNames ?? Array.Empty<string>(), floors, problems);
                // (1.23.0) A dungeon's art: one of the game's places' (by its number), or its own art's files' name.
                int dungeonArt = DeepPlace;
                string dungeonOwn = "";
                bool hasArt = Has(top, "Art", out var artValue);
                if (hasArt && dungeon)
                {
                    if (artValue.ValueKind == JsonValueKind.String && GoodPicture(artValue.GetString() ?? ""))
                        dungeonOwn = artValue.GetString() ?? "";
                    else if (artValue.ValueKind != JsonValueKind.Number || !artValue.TryGetInt32(out dungeonArt)
                             || !GoodArtPlace(dungeonArt))
                        problems.Add($"its Art is the game's place whose art its list shows (by its number: 0 to "
                                     + $"{NoArtPlace - 1}, or {NoArtPlace + 1} to {MostArtPlace}), or its own art's files' "
                                     + $"name (small letters, digits and _, 1 to 64 of them), not {artValue.GetRawText()}");
                }
                if (problems.Count == before)
                {
                    if (dungeon && !hasFloors)
                        problems.Add($"a dungeon has Floors (1 to {MostFloors}): the list choosing it shows");
                    else if (!dungeon && hasFloors)
                        problems.Add("only a dungeon has Floors");
                    else if (dungeon && hasBattles)
                        problems.Add("a dungeon has no RandomBattles: its floors' battles are its own");
                    else if (dungeon && hasMenu)
                        problems.Add("a dungeon has no Menu: its floors are the list choosing it shows");
                    else if (!dungeon && hasArt)
                        problems.Add("only a dungeon has Art: a town's is its Menu's");
                    else if (town && hasBattles)
                        problems.Add("a town has no random battles: RandomBattles is a battle ground's");
                    else if (!town && hasMenu)
                        problems.Add("a battle ground has no Menu: Enter Settlement is a town's");
                    else if (!town && hasDarkened)
                        problems.Add("a battle ground isn't darkened: Darkened is a town's");
                    else if (!town && (hasPicture || hasIcon))
                        problems.Add("a battle ground shows the game's point: it has no Picture or Icon");
                    else if (town && hasPicture && hasIcon)
                        problems.Add("a town shows its own Picture or an Icon of the game's, not both");
                    else if (town && !hasPicture && !hasIcon)
                        problems.Add("a town shows its own Picture or an Icon of the game's");
                    else if (picture.Length > 0 && !(hasFile($"{TextureFolder}/{picture}.tex")
                                                     && hasFile($"{PartsFolder}/{picture}.utexpt")))
                        problems.Add($"its texture's files aren't in the mod ({TextureFolder}/{picture}.tex and "
                                     + $"{PartsFolder}/{picture}.utexpt)");
                    // (1.19.0) A menu's own art: its two files beside a town's picture's.
                    else if (menu != null && menu.ArtPicture.Length > 0
                             && !(hasFile($"{TextureFolder}/{menu.ArtPicture}.tex")
                                  && hasFile($"{PartsFolder}/{menu.ArtPicture}.utexpt")))
                        problems.Add($"its Menu's art's files aren't in the mod ({TextureFolder}/{menu.ArtPicture}.tex "
                                     + $"and {PartsFolder}/{menu.ArtPicture}.utexpt)");
                    // (1.23.0) A dungeon's own art: its two files as a menu's own art's.
                    else if (dungeonOwn.Length > 0 && !(hasFile($"{TextureFolder}/{dungeonOwn}.tex")
                                                        && hasFile($"{PartsFolder}/{dungeonOwn}.utexpt")))
                        problems.Add($"its art's files aren't in the mod ({TextureFolder}/{dungeonOwn}.tex and "
                                     + $"{PartsFolder}/{dungeonOwn}.utexpt)");
                }
                if (problems.Count > before)
                    return null;
                return new MapPlace(modId, modName, folder, name, town, x, y, picture, icon, description, chance,
                                    battles, menu, darkened, floors, dungeonArt, dungeonOwn);
            }
        }

        static string Raw(JsonElement e, string name) => Has(e, name, out var value) ? value.GetRawText() : "none";

        /// <summary>(1.20.0) A town's Darkened: its Quest (one of its mod's quests, by its folder's name) and that
        /// quest's Flag, each a name as a quest's are; null and why in problems.</summary>
        static PlaceDarkened? ReadDarkened(JsonElement given, List<string> problems)
        {
            if (given.ValueKind != JsonValueKind.Object)
            {
                problems.Add("its Darkened isn't a list of fields");
                return null;
            }
            string quest = Text(given, "Quest"), flag = Text(given, "Flag");
            if (QuestFile.GoodName(quest) && QuestFile.GoodName(flag))
                return new PlaceDarkened(quest, flag);
            problems.Add("its Darkened is the quest and its flag that darken it once set, each by its name (Quest and "
                         + "Flag: letters, digits, spaces, underscores and hyphens, 1 to 64 of them), not Quest "
                         + $"{Raw(given, "Quest")} and Flag {Raw(given, "Flag")}");
            return null;
        }

        /// <summary>(1.18.0) A town's Menu: its Art (the game's town whose art it shows, 0 to 14, or (1.19.0) its own
        /// art's files' name), its Shop (the
        /// Outfitter's items, each one of the game's by number, 1 to 255, once; none an empty Outfitter) and, if it
        /// has one, Poachers (true or false); null and why in problems.</summary>
        static TownMenu? ReadMenu(JsonElement given, List<string> problems)
        {
            if (given.ValueKind != JsonValueKind.Object)
            {
                problems.Add("its Menu isn't a list of fields");
                return null;
            }
            // The game's town whose art it shows, by its place; or (its own art) its art's files' name.
            int town = -1;
            string ownArt = "";
            bool hasArt = Has(given, "Art", out var art);
            if (hasArt && art.ValueKind == JsonValueKind.String && GoodPicture(art.GetString() ?? ""))
                ownArt = art.GetString() ?? "";
            else if (!hasArt || art.ValueKind != JsonValueKind.Number || !art.TryGetInt32(out town) || town < 0
                     || town > MostArtTown)
            {
                problems.Add($"its Menu's Art is the game's town (by its place, 0 to {MostArtTown}) whose art its menu "
                             + "shows, or its own art's files' name (small letters, digits and _, 1 to 64 of them), "
                             + $"not {Raw(given, "Art")}");
                return null;
            }
            var shop = new List<int>();
            var own = new List<string>();
            bool good = Has(given, "Shop", out var listed) && listed.ValueKind == JsonValueKind.Array;
            if (good)
                foreach (var item in listed.EnumerateArray())
                {
                    // (1.26.0) Or one of the mod's own items, by its name (ItemFile's).
                    if (item.ValueKind == JsonValueKind.String && ItemFile.GoodName(item.GetString() ?? "")
                        && !own.Contains(item.GetString() ?? ""))
                    {
                        own.Add(item.GetString() ?? "");
                        continue;
                    }
                    if (item.ValueKind != JsonValueKind.Number || !item.TryGetInt32(out int n) || n < 1
                        || n > MostItem || shop.Contains(n))
                    {
                        good = false;
                        break;
                    }
                    shop.Add(n);
                }
            if (!good)
            {
                problems.Add($"its Menu's Shop is the Outfitter's items, each one of the game's by its number (1 to "
                             + $"{MostItem}) or one of the mod's own items by its name, and once, not {Raw(given, "Shop")}");
                return null;
            }
            bool poachers = false;
            if (Has(given, "Poachers", out var den))
            {
                if (den.ValueKind != JsonValueKind.True && den.ValueKind != JsonValueKind.False)
                {
                    problems.Add($"its Menu's Poachers is true or false, not {den.GetRawText()}");
                    return null;
                }
                poachers = den.GetBoolean();
            }
            return new TownMenu(town, shop, poachers, ownArt, own);
        }

        /// <summary>(1.21.0) A dungeon's Floors: 1 to 10, each its Name (1 to 24 characters, as a quest's names are), if
        /// it has one its Description (as a place's), if it waits for one Opens (a quest's flag, as Darkened; 1.24.0, or
        /// "FloorBeforeWon": the floor before it won, never the first floor's) and its Battles (1 to 8,
        /// ReadPlaceBattle), every battle named once in the whole dungeon (each its own file's).</summary>
        static void ReadFloors(JsonElement given, Func<string, byte[]>? readOwn, ICollection<string> mapNames,
                               List<PlaceFloor> floors, List<string> problems)
        {
            if (given.ValueKind != JsonValueKind.Array || given.GetArrayLength() < 1
                || given.GetArrayLength() > MostFloors)
            {
                problems.Add($"its Floors are 1 to {MostFloors} floors, not {given.GetRawText()}");
                return;
            }
            var named = new HashSet<string>(StringComparer.Ordinal);
            foreach (var f in given.EnumerateArray())
            {
                string name = f.ValueKind == JsonValueKind.Object ? Text(f, "Name") : "";
                if (!QuestFile.GoodName(name) || name.Length > MostFloorName)
                {
                    problems.Add($"a floor's Name is 1 to {MostFloorName} letters, digits, spaces, underscores and "
                                 + $"hyphens, not {(f.ValueKind == JsonValueKind.Object ? Raw(f, "Name") : f.GetRawText())}");
                    return;
                }
                if (floors.Exists(other => string.Equals(other.Name, name, StringComparison.OrdinalIgnoreCase)))
                {
                    problems.Add($"the floor {name} is named twice");
                    return;
                }
                string description = "";
                if (Has(f, "Description", out var words))
                {
                    string text = words.ValueKind == JsonValueKind.String ? words.GetString() ?? "" : "";
                    if (words.ValueKind != JsonValueKind.String || !GoodDescription(text))
                    {
                        problems.Add($"the floor {name}'s Description is words of 1 to {MostDescription} characters, at "
                                     + $"most one line break among them, not {words.GetRawText()}");
                        return;
                    }
                    description = text;
                }
                PlaceDarkened? opens = null;
                bool afterWin = false;
                if (Has(f, "Opens", out var opensValue))
                {
                    // (1.24.0) Listed once the floor before it is won: never the first floor, which has none.
                    if (opensValue.ValueKind == JsonValueKind.String && opensValue.GetString() == FloorBeforeWon)
                    {
                        if (floors.Count == 0)
                        {
                            problems.Add($"the floor {name} is the dungeon's first: it has no floor before it to be won, "
                                         + $"so its Opens can't be \"{FloorBeforeWon}\"");
                            return;
                        }
                        afterWin = true;
                    }
                    else
                    {
                        var said = new List<string>();
                        opens = ReadDarkened(opensValue, said);
                        if (opens == null)
                        {
                            problems.Add($"the floor {name}'s Opens is the quest and its flag that list it once set, "
                                         + "each by its name (Quest and Flag: letters, digits, spaces, underscores and "
                                         + $"hyphens, 1 to 64 of them), or \"{FloorBeforeWon}\" (listed once the floor "
                                         + $"before it is won), not {opensValue.GetRawText()}");
                            return;
                        }
                    }
                }
                if (!Has(f, "Battles", out var listed) || listed.ValueKind != JsonValueKind.Array
                    || listed.GetArrayLength() < 1 || listed.GetArrayLength() > MostBattles)
                {
                    problems.Add($"the floor {name}'s Battles are 1 to {MostBattles} battles, not {Raw(f, "Battles")}");
                    return;
                }
                var battles = new List<PlaceBattle>();
                foreach (var b in listed.EnumerateArray())
                {
                    var battle = ReadPlaceBattle(b, readOwn, mapNames, problems);
                    if (battle == null)
                        return;
                    if (!named.Add(battle.Name))
                    {
                        problems.Add($"the random battle {battle.Name} is named twice");
                        return;
                    }
                    battles.Add(battle);
                }
                floors.Add(new PlaceFloor(name, description, opens, battles, afterWin));
            }
        }

        /// <summary>(1.17.0) A battle ground's RandomBattles: its Chance (how many of 100 arrivals start a battle, 0 to
        /// 100) and its Battles (1 to 8, ReadPlaceBattle), into `battles`; returns the chance (problems said).</summary>
        static int ReadRandomBattles(JsonElement given, Func<string, byte[]>? readOwn, ICollection<string> mapNames,
                                     List<PlaceBattle> battles, List<string> problems)
        {
            if (given.ValueKind != JsonValueKind.Object)
            {
                problems.Add("its RandomBattles isn't a list of fields");
                return 0;
            }
            if (!Has(given, "Chance", out var c) || c.ValueKind != JsonValueKind.Number || !c.TryGetInt32(out int chance)
                || chance < 0 || chance > MostChance)
            {
                problems.Add($"its RandomBattles' Chance is how many of 100 arrivals start a battle, 0 to {MostChance}, "
                             + $"not {Raw(given, "Chance")}");
                return 0;
            }
            if (!Has(given, "Battles", out var listed) || listed.ValueKind != JsonValueKind.Array
                || listed.GetArrayLength() < 1 || listed.GetArrayLength() > MostBattles)
            {
                problems.Add($"its RandomBattles' Battles are 1 to {MostBattles} battles, not {Raw(given, "Battles")}");
                return 0;
            }
            foreach (var b in listed.EnumerateArray())
            {
                var battle = ReadPlaceBattle(b, readOwn, mapNames, problems);
                if (battle == null)
                    return 0;
                if (battles.Exists(other => other.Name == battle.Name))
                {
                    problems.Add($"the random battle {battle.Name} is named twice");
                    return 0;
                }
                battles.Add(battle);
            }
            return chance;
        }

        /// <summary>(1.17.0) One random battle: its Name, its Units (its file in the place's folder, 640 bytes, or one
        /// of the game's battles by number), its Map (one of the game's by number, or one of the mod's quest maps by
        /// name), its Deploy (one deploy area, QuestFile.ReadDeploy) and, if it waits for the story, From
        /// (variable 110 at least it); null and why in problems.</summary>
        static PlaceBattle? ReadPlaceBattle(JsonElement b, Func<string, byte[]>? readOwn, ICollection<string> mapNames,
                                            List<string> problems)
        {
            string name = b.ValueKind == JsonValueKind.Object ? Text(b, "Name") : "";
            if (!QuestFile.GoodName(name))
            {
                problems.Add($"a random battle's name isn't one: {b.GetRawText()}");
                return null;
            }
            string who = $"the random battle {name}";
            byte[]? units = null;
            int gameUnits = 0;
            Has(b, "Units", out var unitsValue);
            if (unitsValue.ValueKind == JsonValueKind.String)
            {
                string file = unitsValue.GetString() ?? "";
                if (file.Length == 0 || file.Contains("..") || file.StartsWith("/") || file.StartsWith("\\")
                    || Path.IsPathRooted(file) || (file.Length >= 2 && char.IsLetter(file[0]) && file[1] == ':'))
                {
                    problems.Add($"{who} names no file in its folder");
                    return null;
                }
                try
                {
                    if (readOwn == null)
                        throw new IOException("its folder isn't read here");
                    units = readOwn(file);
                }
                catch (Exception ex) when (ex is IOException || ex is UnauthorizedAccessException)
                {
                    problems.Add($"{who}'s file {file} can't be read ({ex.Message})");
                    return null;
                }
                if (units.Length != QuestFile.BattleBytes)
                {
                    problems.Add($"{who}'s units are {units.Length} bytes, not {QuestFile.BattleBytes} (16 units as the "
                                 + "game's battles hold them)");
                    return null;
                }
            }
            else if (unitsValue.ValueKind != JsonValueKind.Number || !unitsValue.TryGetInt32(out gameUnits)
                     || gameUnits < 1 || gameUnits > QuestFile.MostGameBattle)
            {
                problems.Add($"{who}'s Units are its units' file in the place's folder, or one of the game's battles by "
                             + $"its number (1 to {QuestFile.MostGameBattle}), not {Raw(b, "Units")}");
                return null;
            }
            int map = 0;
            string mapName = "";
            Has(b, "Map", out var mapValue);
            bool goodMap = (mapValue.ValueKind == JsonValueKind.Number && mapValue.TryGetInt32(out map) && map >= 1
                            && map <= QuestFile.MostGameMap)
                           || (mapValue.ValueKind == JsonValueKind.String && mapNames.Contains(mapValue.GetString() ?? ""));
            if (!goodMap)
            {
                problems.Add($"{who}'s Map is one of the game's maps by its number (1 to {QuestFile.MostGameMap}) or one "
                             + $"of the mod's quest maps by its name, not {Raw(b, "Map")}");
                return null;
            }
            if (mapValue.ValueKind == JsonValueKind.String)
            {
                mapName = mapValue.GetString() ?? "";
                map = 0;
            }
            if (!Has(b, "Deploy", out var areas))
            {
                problems.Add($"{who} gives no Deploy (where the player's units start: one deploy area)");
                return null;
            }
            if (areas.ValueKind != JsonValueKind.Array || areas.GetArrayLength() != 1)
            {
                problems.Add($"{who}'s Deploy is one deploy area: a random battle starts the player's units on one, as "
                             + "the game's own do");
                return null;
            }
            var deploy = new List<DeployArea>();
            if (!QuestFile.ReadDeploy(who, areas, deploy, problems))
                return null;
            int from = -1;
            if (Has(b, "From", out var fromValue))
            {
                if (fromValue.ValueKind != JsonValueKind.Number || !fromValue.TryGetInt32(out from) || from < 1
                    || from > MostFrom)
                {
                    problems.Add($"{who}'s From is the story's progress it waits for, 1 to {MostFrom}, not "
                                 + Raw(b, "From"));
                    return null;
                }
            }
            return new PlaceBattle(name, units, gameUnits, map, mapName, deploy, from);
        }

        /// <summary>(1.16.0) Words a place's description may be: 1 to 200 characters, a line break the only control
        /// character among them and once at the most, no space at either end.</summary>
        public static bool GoodDescription(string words)
        {
            if (words.Length < 1 || words.Length > MostDescription || char.IsWhiteSpace(words[0])
                || char.IsWhiteSpace(words[^1]))
                return false;
            int breaks = 0;
            foreach (char c in words)
            {
                if (c == '\n')
                    breaks++;
                else if (char.IsControl(c))
                    return false;
            }
            return breaks <= 1;
        }

        /// <summary>[x, y]: two whole numbers on the world map's picture.</summary>
        static bool Point(JsonElement at, out int x, out int y)
        {
            x = y = 0;
            if (at.ValueKind != JsonValueKind.Array || at.GetArrayLength() != 2)
                return false;
            var first = at[0];
            var second = at[1];
            return first.ValueKind == JsonValueKind.Number && second.ValueKind == JsonValueKind.Number
                   && first.TryGetInt32(out x) && second.TryGetInt32(out y)
                   && x >= 0 && x <= MapWidth && y >= 0 && y <= MapHeight;
        }
    }
}
