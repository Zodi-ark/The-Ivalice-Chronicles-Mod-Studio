// Mod Studio Framework: (1.10.0) reading a quest map's file. Part of The
// Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi, 27 October, after his test 32: a quest's own maps ("Yes, start with
// test 33"). A quest map is a folder of its own in a mod,
// `ModStudioMaps/<map>/`, holding `map.json` and its own PlayStation files.
// It is made from one of the game's maps (its Base, 0 to 127): what the mod
// doesn't give is that map's. The helper gives it a number past the game's
// (129 to 255, MapRoom.cs) as the game starts, so a quest's battle names it
// by its name (a modder never chooses a number). What it gives:
// - its rows in the six tables the game keys by a map (Map, RefinedBgTexture,
//   RefinedBgSystemTexture, RefinedBgMeshNode, RefinedBgAnim,
//   RefinedBgMeshPolygon), whole, as Mod Studio's database holds them; the
//   textures they name are found in its Base's folder of pictures
//   (bg/textures/NNN/), the game's own there and the mod's under names of its
//   own;
// - its enhanced mesh and anims (paths of the mod's own under bg/meshes/ and
//   bg/anims/), else its Base's;
// - its own PlayStation files (its battle grid's) by their place among its
//   Base's numbered files (the GNS's records name a file by that place);
// - its Title, shown where the game shows a map's name.
// mod_studio/side_quests.py reads the same file and says the same problems,
// word for word.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.Json;

namespace ModStudioEventSetup
{
    /// <summary>One row a quest map gives a table: its keys after the map's (none for Map, one or two), and its
    /// columns' values as read (a number, a string, or a list).</summary>
    public sealed class MapRow
    {
        public int[] Keys { get; }
        public Dictionary<string, object?> Values { get; }

        public MapRow(int[] keys, Dictionary<string, object?> values)
        {
            Keys = keys;
            Values = values;
        }
    }

    /// <summary>A quest map, as its mod gives it.</summary>
    public sealed class QuestMap
    {
        public string ModId { get; }
        public string ModName { get; }
        /// <summary>Its folder's name in its mod: with the mod's id, what names it for good, and the name a quest's
        /// setup gives its Map.</summary>
        public string Folder { get; }
        /// <summary>The game's map it is made from (0 to 127).</summary>
        public int Base { get; }
        /// <summary>Its name shown in the game, or "" for its Base's (its Map row's).</summary>
        public string Title { get; }
        /// <summary>Its enhanced mesh's and anims' paths (under bg/meshes/ and bg/anims/), or "" for its Base's.</summary>
        public string Mesh { get; }
        public string Anims { get; }
        /// <summary>Its own PlayStation files by their place among its Base's numbered files.</summary>
        public SortedDictionary<int, byte[]> Grid { get; }
        /// <summary>Its rows by table (MapRows.Tables' names).</summary>
        public Dictionary<string, List<MapRow>> Rows { get; }

        public QuestMap(string modId, string modName, string folder, int @base, string title, string mesh,
                        string anims, SortedDictionary<int, byte[]> grid, Dictionary<string, List<MapRow>> rows)
        {
            ModId = modId;
            ModName = modName;
            Folder = folder;
            Base = @base;
            Title = title;
            Mesh = mesh;
            Anims = anims;
            Grid = grid;
            Rows = rows;
        }

        /// <summary>What names it in the helper's file of numbers: its mod and its folder.</summary>
        public string Key => $"{ModId}/{Folder}";
    }

    public static class MapFile
    {
        /// <summary>The folder of a mod that holds its quest maps, one folder each.</summary>
        public const string Folder = "ModStudioMaps";
        public const string Name = "map.json";
        public const string Format = "Mod Studio quest map";
        public const int Version = 1;
        /// <summary>The game's maps a quest map may be made from.</summary>
        public const int GameMaps = 128;
        /// <summary>A file's place among its Base's numbered files: the game's maps have at most 40.</summary>
        public const int Places = 64;
        /// <summary>The most a PlayStation file of a quest map may be (a map's largest, a texture, is 131,072).</summary>
        public const int MostFile = 1 << 20;
        /// <summary>The longest path of a mesh or anims (the game makes its paths in 0x110 bytes).</summary>
        public const int MostPath = 200;
        public const int MostTitle = 64;

        /// <summary>Every quest map of a mod, in its folders' order; what can't be used goes in problems.</summary>
        public static List<QuestMap> ReadMod(string modId, string modName, string modFolder, List<string> problems)
        {
            var maps = new List<QuestMap>();
            string root = Path.Combine(modFolder, Folder);
            if (!Directory.Exists(root))
                return maps;
            var folders = new List<string>(Directory.GetDirectories(root));
            folders.Sort(StringComparer.Ordinal);
            foreach (var folder in folders)
            {
                string file = Path.Combine(folder, Name);
                if (!File.Exists(file))
                    continue;
                string folderName = Path.GetFileName(folder);
                var said = new List<string>();
                QuestMap? map = null;
                if (!QuestFile.GoodName(folderName))
                    said.Add("its folder's name isn't a name (letters, digits, spaces, _ and -, 1 to 64 of them)");
                else
                    try
                    {
                        map = Read(modId, modName, folderName, File.ReadAllText(file),
                                   name => File.ReadAllBytes(Path.Combine(folder, name)), said);
                    }
                    catch (Exception e) when (e is not OutOfMemoryException)
                    {
                        said.Add($"it can't be read ({e.Message})");
                    }
                foreach (var s in said)
                    problems.Add($"{modName}'s quest map {folderName}: {s}");
                if (map != null)
                    maps.Add(map);
            }
            return maps;
        }

        /// <summary>The names of a mod's quest maps (their folders with a map.json), whatever their files hold: what
        /// a quest's setup may name.</summary>
        public static List<string> NamesIn(string modFolder)
        {
            var names = new List<string>();
            string root = Path.Combine(modFolder, Folder);
            if (!Directory.Exists(root))
                return names;
            foreach (var folder in Directory.GetDirectories(root))
                if (File.Exists(Path.Combine(folder, Name)))
                    names.Add(Path.GetFileName(folder));
            names.Sort(StringComparer.Ordinal);
            return names;
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
            => Has(e, name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() ?? "" : "";

        /// <summary>A path of the mod's own under `folder` (bg/meshes/ or bg/anims/): lowercase letters, digits, _, -
        /// and /, then .bin; no more than MostPath.</summary>
        public static bool GoodPath(string path, string folder)
        {
            if (!path.StartsWith(folder, StringComparison.Ordinal) || !path.EndsWith(".bin", StringComparison.Ordinal)
                || path.Length > MostPath || path.Length <= folder.Length + 4 || path.Contains("//"))
                return false;
            foreach (char c in path)
                if (!(c >= 'a' && c <= 'z' || c >= '0' && c <= '9' || c == '_' || c == '-' || c == '/' || c == '.'))
                    return false;
            return !path.Contains("..");
        }

        /// <summary>A title: 1 to MostTitle characters, none a control character, not starting or ending with a
        /// space.</summary>
        public static bool GoodTitle(string title)
        {
            if (title.Length == 0 || title.Length > MostTitle || title.Trim() != title)
                return false;
            foreach (char c in title)
                if (char.IsControl(c))
                    return false;
            return true;
        }

        /// <summary>A quest map from its file's text; null when it can't be used, why in problems. `read` reads one of
        /// its folder's files by name.</summary>
        public static QuestMap? Read(string modId, string modName, string folder, string text, Func<string, byte[]> read,
                                     List<string> problems)
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
                if (Text(top, "Format") != Format || !Has(top, "Version", out var version)
                    || version.ValueKind != JsonValueKind.Number || !version.TryGetInt32(out int v) || v != Version)
                {
                    problems.Add($"its {Name} isn't a \"{Format}\" file of version {Version}");
                    return null;
                }
                int before = problems.Count;
                int @base = -1;
                if (!Has(top, "Base", out var b) || b.ValueKind != JsonValueKind.Number || !b.TryGetInt32(out @base)
                    || @base < 0 || @base >= GameMaps)
                    problems.Add($"its Base isn't one of the game's maps 0 to {GameMaps - 1}");
                string title = "";
                if (Has(top, "Title", out var t))
                {
                    title = t.ValueKind == JsonValueKind.String ? t.GetString() ?? "" : "";
                    if (!GoodTitle(title))
                        problems.Add($"its Title isn't 1 to {MostTitle} characters, none of them a control "
                                     + "character, without a space at either end");
                }
                string mesh = "", anims = "";
                foreach (var (field, under) in new[] { ("Mesh", "bg/meshes/"), ("Anims", "bg/anims/") })
                {
                    if (!Has(top, field, out var p))
                        continue;
                    string path = p.ValueKind == JsonValueKind.String ? p.GetString() ?? "" : "";
                    if (!GoodPath(path, under))
                        problems.Add($"its {field} isn't a path under {under} of lowercase letters, digits, _ and -, "
                                     + $"ending .bin, {MostPath} characters at most");
                    else if (field == "Mesh")
                        mesh = path;
                    else
                        anims = path;
                }
                var grid = new SortedDictionary<int, byte[]>();
                if (Has(top, "Grid", out var g))
                {
                    if (g.ValueKind != JsonValueKind.Object)
                        problems.Add("its Grid isn't a list of files by their places");
                    else
                        foreach (var p in g.EnumerateObject())
                        {
                            if (!int.TryParse(p.Name, NumberStyles.None, CultureInfo.InvariantCulture, out int place)
                                || place < 0 || place >= Places || place.ToString(CultureInfo.InvariantCulture) != p.Name)
                            {
                                problems.Add($"its Grid's place {p.Name} isn't 0 to {Places - 1}");
                                continue;
                            }
                            string file = p.Value.ValueKind == JsonValueKind.String ? p.Value.GetString() ?? "" : "";
                            if (file.Length == 0 || file.Contains("..") || file.Contains('/') || file.Contains('\\')
                                || file.Contains(':'))
                            {
                                problems.Add($"its Grid's place {place} names no file in its folder");
                                continue;
                            }
                            byte[] bytes;
                            try
                            {
                                bytes = read(file);
                            }
                            catch (Exception ex) when (ex is IOException || ex is UnauthorizedAccessException)
                            {
                                problems.Add($"its Grid's file {file} can't be read ({ex.Message})");
                                continue;
                            }
                            if (bytes.Length == 0 || bytes.Length > MostFile)
                                problems.Add($"its Grid's file {file} is {bytes.Length} bytes; a map's file is 1 to "
                                             + $"{MostFile}");
                            else
                                grid[place] = bytes;
                        }
                }
                var rows = new Dictionary<string, List<MapRow>>(StringComparer.Ordinal);
                if (!Has(top, "Rows", out var r) || r.ValueKind != JsonValueKind.Object)
                    problems.Add("it has no Rows");
                else
                    MapRows.Read(r, rows, problems);
                if (problems.Count > before)
                    return null;
                return new QuestMap(modId, modName, folder, @base, title, mesh, anims, grid, rows);
            }
        }
    }
}
