// Mod Studio Framework: (1.4.0) reading a mod's own road on the world map.
// Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi, 26 October, after his test 23: "Roads to new places", step 2 of his
// "real new places, built in steps". Its first part: a mod's road drawn on
// the world map, a picture of the map's layout added as the game sets the map
// up (MapRoads.cs), pictures only (the game doesn't travel it yet). A road is
// a folder of its own in a mod, `ModStudioRoads/<road>/`, holding
// `road.json`: its name, the two places it joins (From and To: one of the
// world map's places by its number, 0 to 46, as a quest's start names one,
// or one of the mod's own places by its name), the turns it takes between
// them (Via: points on the map's picture), and its picture: a texture and its
// part list at the game's paths in the mod, which the mod loader serves
// (`FFTIVC/data/enhanced/ui/ffto/worldmap/texture/<Picture>.tex` and
// `.../textureparts/<Picture>.utexpt`, its part 1 the picture, drawn at its
// size), with where its top left corner is on the map's picture (PictureAt).
// Mod Studio writes it (`mod_studio/map_roads.py` reads and writes the same
// file and says the same problems, and draws the picture in the game's look);
// what can't be used is left out and said. A modder never chooses a number
// for anything a road adds.
//
// (1.5.0) Walk: the points Ramza's marker walks along the road, From to To
// (Mod Studio's map_roads.walk_points: the drawn trail every 60 pixels or so,
// where his marker stands with his feet on it; its first and last where he
// stands at the road's places). A road between two of the game's places with
// a Walk is travelled as the game's own (Travel.cs); without one it is drawn
// only.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace ModStudioEventSetup
{
    /// <summary>A mod's own road on the world map, as its mod gives it.</summary>
    public sealed class MapRoad
    {
        public string ModId { get; }
        public string ModName { get; }
        public string Folder { get; }
        public string Name { get; }
        /// <summary>Its places: one of the world map's by its number (the name ""), or one of the mod's own by its
        /// name (the number -1).</summary>
        public int FromPlace { get; }
        public string FromName { get; }
        public int ToPlace { get; }
        public string ToName { get; }
        /// <summary>The turns it takes between its places, on the map's picture (3840 x 2288).</summary>
        public List<(int X, int Y)> Via { get; }
        /// <summary>Its picture: its files' name (its part list's name, part 1), where its top left corner is on
        /// the map's picture, and its size (its part 1's).</summary>
        public string Picture { get; }
        public int X { get; }
        public int Y { get; }
        public int Width { get; }
        public int Height { get; }
        /// <summary>(1.5.0) Where Ramza's marker walks along it, From to To (none: drawn only).</summary>
        public List<(int X, int Y)> Walk { get; }

        public MapRoad(string modId, string modName, string folder, string name, int fromPlace, string fromName,
                       int toPlace, string toName, List<(int X, int Y)> via, string picture, int x, int y, int width,
                       int height, List<(int X, int Y)>? walk = null)
        {
            ModId = modId;
            ModName = modName;
            Folder = folder;
            Name = name;
            FromPlace = fromPlace;
            FromName = fromName;
            ToPlace = toPlace;
            ToName = toName;
            Via = via;
            Picture = picture;
            X = x;
            Y = y;
            Width = width;
            Height = height;
            Walk = walk ?? new List<(int X, int Y)>();
        }

        /// <summary>(1.5.0) Whether the game can travel it: both its places the game's, and a walk.</summary>
        public bool BetweenGamePlaces => FromName.Length == 0 && ToName.Length == 0 && Walk.Count >= 2;

        /// <summary>The part list's name the game makes its picture's parts ready by.</summary>
        public string Parts => PlaceFile.PartsOf(Picture);
    }

    public static class RoadFile
    {
        /// <summary>The folder of a mod that holds its own roads, one folder each.</summary>
        public const string Folder = "ModStudioRoads";
        public const string Name = "road.json";
        public const string Format = "Mod Studio road";
        public const int Version = 1;
        /// <summary>The world map's places a road may join by number (a quest's start names them so: 0 to 46); 20
        /// and 43 have none.</summary>
        public const int Places = 47;
        static readonly int[] NoPlace = { 20, 43 };
        /// <summary>The most turns a road takes between its places (with its two places, 64 points).</summary>
        public const int MostVia = 62;
        /// <summary>The largest picture a road has (its part 1's width and height).</summary>
        public const int MostPicture = 4096;
        /// <summary>(1.5.0) The most points a road's walk has.</summary>
        public const int MostWalk = 64;

        public static bool GamePlace(int place) => place >= 0 && place < Places && Array.IndexOf(NoPlace, place) < 0;

        /// <summary>Every road of a mod, in its folders' order (its places named by `placeNames`, the mod's own as
        /// read); what can't be used goes in problems.</summary>
        public static List<MapRoad> ReadMod(string modId, string modName, string modFolder, ICollection<string> placeNames,
                                            List<string> problems)
        {
            var roads = new List<MapRoad>();
            string root = Path.Combine(modFolder, Folder);
            if (!Directory.Exists(root))
                return roads;
            var folders = new List<string>(Directory.GetDirectories(root));
            folders.Sort(StringComparer.Ordinal);
            foreach (var folder in folders)
            {
                string file = Path.Combine(folder, Name);
                if (!File.Exists(file))
                    continue;
                string folderName = Path.GetFileName(folder);
                var said = new List<string>();
                MapRoad? road = null;
                try
                {
                    road = Read(modId, modName, folderName, File.ReadAllText(file), path =>
                    {
                        string full = Path.Combine(modFolder, path);
                        return File.Exists(full) ? File.ReadAllBytes(full) : null;
                    }, placeNames, said);
                }
                catch (Exception e) when (e is not OutOfMemoryException)
                {
                    said.Add($"it can't be read ({e.Message})");
                }
                if (road != null && roads.Exists(r => r.Name == road.Name))
                {
                    said.Clear();
                    said.Add($"another of the mod's roads is named {road.Name}");
                    road = null;
                }
                foreach (var s in said)
                    problems.Add($"{modName}'s road {folderName}: {s}");
                if (road != null)
                    roads.Add(road);
            }
            return roads;
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

        /// <summary>A part list's part 1's width and height, or (0, 0) when it has none (not a part list, no part
        /// 1, or one of no size or over MostPicture).</summary>
        public static (int Width, int Height) PartSize(byte[]? data)
        {
            if (data == null || data.Length < 12)
                return (0, 0);
            uint table = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(4, 4));
            uint count = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(8, 4));
            long at = (long)table + 20;
            if (count < 2 || table < 12 || at + 20 > data.Length)
                return (0, 0);
            int x1 = BinaryPrimitives.ReadInt32LittleEndian(data.AsSpan((int)at + 4, 4));
            int y1 = BinaryPrimitives.ReadInt32LittleEndian(data.AsSpan((int)at + 8, 4));
            int x2 = BinaryPrimitives.ReadInt32LittleEndian(data.AsSpan((int)at + 12, 4));
            int y2 = BinaryPrimitives.ReadInt32LittleEndian(data.AsSpan((int)at + 16, 4));
            long width = (long)x2 - x1, height = (long)y2 - y1;
            if (width <= 0 || width > MostPicture || height <= 0 || height > MostPicture)
                return (0, 0);
            return ((int)width, (int)height);
        }

        /// <summary>A road's From or To: one of the world map's places by its number, or one of the mod's own by
        /// its name; false when it can't be used, why in problems.</summary>
        static bool End(JsonElement top, string key, ICollection<string> placeNames, List<string> problems, out int place,
                        out string name)
        {
            place = -1;
            name = "";
            if (!Has(top, key, out var value))
            {
                problems.Add($"it has no {key} (the place it {(key == "From" ? "starts at" : "goes to")})");
                return false;
            }
            if (value.ValueKind == JsonValueKind.Number && value.TryGetInt32(out int number) && GamePlace(number)
                && !value.GetRawText().Contains('.') && !value.GetRawText().Contains('e')
                && !value.GetRawText().Contains('E'))
            {
                place = number;
                return true;
            }
            if (value.ValueKind == JsonValueKind.String && (value.GetString() ?? "").Length > 0)
            {
                string given = value.GetString()!;
                if (placeNames.Contains(given))
                {
                    name = given;
                    return true;
                }
                problems.Add($"its {key} names no place of the mod's ({given})");
                return false;
            }
            problems.Add($"its {key} is one of the world map's places by its number (0 to {Places - 1}, but not 20 or 43: "
                         + $"they have none) or one of the mod's own places by its name, not {value.GetRawText()}");
            return false;
        }

        /// <summary>[x, y]: two whole numbers on the world map's picture.</summary>
        static bool Point(JsonElement at, out int x, out int y)
        {
            x = y = 0;
            if (at.ValueKind != JsonValueKind.Array || at.GetArrayLength() != 2)
                return false;
            var first = at[0];
            var second = at[1];
            return Whole(first, out x) && Whole(second, out y) && x >= 0 && x <= PlaceFile.MapWidth && y >= 0
                   && y <= PlaceFile.MapHeight;
        }

        static bool Whole(JsonElement e, out int value)
        {
            value = 0;
            if (e.ValueKind != JsonValueKind.Number || !e.TryGetInt32(out value))
                return false;
            string raw = e.GetRawText();
            return !raw.Contains('.') && !raw.Contains('e') && !raw.Contains('E');
        }

        /// <summary>A road from its file's text; null when it can't be used, why in problems. `readFile` gives a
        /// file of the mod's (its path from the mod's folder), or null.</summary>
        public static MapRoad? Read(string modId, string modName, string folder, string text, Func<string, byte[]?> readFile,
                                    ICollection<string> placeNames, List<string> problems)
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
                if (Text(top, "Format") != Format || !Has(top, "Version", out var v) || !Whole(v, out int version)
                    || version != Version)
                {
                    problems.Add($"its {Name} isn't a \"{Format}\" file of version {Version}");
                    return null;
                }
                int before = problems.Count;
                string name = Text(top, "Name");
                if (name.Length == 0)
                    name = folder;
                bool hasFrom = End(top, "From", placeNames, problems, out int fromPlace, out string fromName);
                bool hasTo = End(top, "To", placeNames, problems, out int toPlace, out string toName);
                var via = new List<(int X, int Y)>();
                if (Has(top, "Via", out var viaValue))
                {
                    bool good = viaValue.ValueKind == JsonValueKind.Array && viaValue.GetArrayLength() <= MostVia;
                    if (good)
                        foreach (var point in viaValue.EnumerateArray())
                        {
                            if (!Point(point, out int px, out int py))
                            {
                                good = false;
                                break;
                            }
                            via.Add((px, py));
                        }
                    if (!good)
                        problems.Add("its Via is the points it passes between its places on the world map, each two "
                                     + $"whole numbers from 0 to {PlaceFile.MapWidth} and 0 to {PlaceFile.MapHeight}, at "
                                     + $"most {MostVia} of them, not {viaValue.GetRawText()}");
                }
                string picture = "";
                if (!Has(top, "Picture", out var pictureValue))
                    problems.Add("it has no Picture (its texture's files' name)");
                else
                {
                    string given = pictureValue.ValueKind == JsonValueKind.String ? pictureValue.GetString() ?? "" : "";
                    if (pictureValue.ValueKind == JsonValueKind.String && PlaceFile.GoodPicture(given))
                        picture = given;
                    else
                        problems.Add("its Picture is its texture's files' name (small letters, digits and _, 1 to 64 of "
                                     + $"them), not {pictureValue.GetRawText()}");
                }
                int x = 0, y = 0;
                if (!Has(top, "PictureAt", out var at))
                    problems.Add("it has no PictureAt (where its texture's top left corner is on the world map)");
                else if (!Point(at, out x, out y))
                    problems.Add("its PictureAt is where its texture's top left corner is on the world map, two whole "
                                 + $"numbers from 0 to {PlaceFile.MapWidth} and 0 to {PlaceFile.MapHeight}, not "
                                 + at.GetRawText());
                var walk = new List<(int X, int Y)>();
                if (Has(top, "Walk", out var walkValue))
                {
                    bool good = walkValue.ValueKind == JsonValueKind.Array && walkValue.GetArrayLength() >= 2
                                && walkValue.GetArrayLength() <= MostWalk;
                    if (good)
                        foreach (var point in walkValue.EnumerateArray())
                        {
                            if (!Point(point, out int px, out int py))
                            {
                                good = false;
                                break;
                            }
                            walk.Add((px, py));
                        }
                    if (!good)
                        problems.Add("its Walk is the points Ramza walks from its From to its To on the world map, each "
                                     + $"two whole numbers from 0 to {PlaceFile.MapWidth} and 0 to {PlaceFile.MapHeight}, "
                                     + $"2 to {MostWalk} of them, not {walkValue.GetRawText()}");
                }
                int width = 0, height = 0;
                if (problems.Count == before && hasFrom && hasTo)
                {
                    if (fromPlace == toPlace && fromName == toName)
                        problems.Add("its From and To are the same place");
                    else
                    {
                        byte[]? texture = readFile($"{PlaceFile.TextureFolder}/{picture}.tex");
                        byte[]? parts = readFile($"{PlaceFile.PartsFolder}/{picture}.utexpt");
                        if (texture == null || parts == null)
                            problems.Add($"its texture's files aren't in the mod ({PlaceFile.TextureFolder}/{picture}.tex "
                                         + $"and {PlaceFile.PartsFolder}/{picture}.utexpt)");
                        else
                        {
                            (width, height) = PartSize(parts);
                            if (width == 0)
                                problems.Add($"its texture's part list ({PlaceFile.PartsFolder}/{picture}.utexpt) has no "
                                             + $"part 1 (1 to {MostPicture} pixels wide and high)");
                        }
                    }
                }
                if (problems.Count > before)
                    return null;
                return new MapRoad(modId, modName, folder, name, fromPlace, fromName, toPlace, toName, via, picture, x, y,
                                   width, height, walk);
            }
        }
    }
}
