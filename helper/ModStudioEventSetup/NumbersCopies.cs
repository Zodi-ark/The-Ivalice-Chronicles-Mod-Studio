// Mod Studio Framework: (1.13.0) where the numbers' copies are kept, and
// reading and writing them. Part of The Ivalice Chronicles Mod Studio,
// GPL-3.0.
//
// Zodi's first of his list (28 October): "a second copy of the helper's
// numbers file, so a lost file never renumbers anyone's quests or reads a
// save's flags as another quest's"; his choice: kept beside the game's saves,
// in Reloaded-II's settings folder for the helper (as before) and in the
// helper's own folder. The game keeps every save slot in one file,
// fftsave.bin, in its folder of the player's Documents: "My Games", its
// name, "Steam", the player's Steam ID (his program builds it from
// SHGetSpecialFolderLocation's 5, the Documents, at 0x6E5DC and 0x6B144, and
// deletes only files it names). A Reloaded-II update keeps the helper's own
// folder's .json files when its release was made with Reloaded-II's
// publisher (its ModConfig.json's IgnoreRegexes), and its settings folder
// always.
using System;
using System.Collections.Generic;
using System.IO;

namespace ModStudioEventSetup
{
    public static class NumbersCopies
    {
        /// <summary>The game's folder in the player's Documents, as his program names it (0x6E5DC: "/My Games/",
        /// then its title, then "Steam/" and the Steam ID, 0x6B144).</summary>
        public const string MyGames = "My Games", GameFolder = "FINAL FANTASY TACTICS - The Ivalice Chronicles",
                            SteamFolder = "Steam";
        /// <summary>The copy's name beside the saves: the helper's mod ID's, so a new name of the helper keeps it.</summary>
        public const string SaveCopyName = "fftivc.utility.modstudio.eventsetup.Numbers.json";
        /// <summary>Where each copy is, in words, for what is said.</summary>
        public const string BesideSaves = "beside the game's saves", InSettings = "in Reloaded-II's settings folder",
                            InOwnFolder = "in its own folder";

        /// <summary>One copy: where it is in words, and its file.</summary>
        public readonly struct Place
        {
            public string Where { get; }
            public string File { get; }

            public Place(string where, string file)
            {
                Where = where;
                File = file;
            }
        }

        /// <summary>Each of the game's save folders under `documents` (one for each Steam ID that played it): the
        /// folders of digits under My Games, the game's folder, Steam.</summary>
        public static List<string> SaveFolders(string documents)
        {
            var found = new List<string>();
            if (string.IsNullOrEmpty(documents))
                return found;
            string steam = Path.Combine(documents, MyGames, GameFolder, SteamFolder);
            try
            {
                if (!Directory.Exists(steam))
                    return found;
                foreach (var folder in Directory.GetDirectories(steam))
                {
                    string name = Path.GetFileName(folder);
                    if (name.Length > 0 && name.TrimStart('0', '1', '2', '3', '4', '5', '6', '7', '8', '9').Length == 0)
                        found.Add(folder);
                }
            }
            catch (Exception e) when (e is IOException || e is UnauthorizedAccessException)
            {
                return found;
            }
            found.Sort(StringComparer.Ordinal);
            return found;
        }

        /// <summary>The copies in the order they are trusted: beside each of the game's saves first (the saves were
        /// made with them), then Reloaded-II's settings folder, then the helper's own folder; each file once.</summary>
        public static List<Place> Places(string documents, string settingsFile, string ownFile)
        {
            var places = new List<Place>();
            var saves = SaveFolders(documents);
            foreach (var folder in saves)
                places.Add(new Place(saves.Count == 1 ? BesideSaves : $"{BesideSaves} of {Path.GetFileName(folder)}",
                                     Path.Combine(folder, SaveCopyName)));
            if (settingsFile.Length > 0)
                places.Add(new Place(InSettings, settingsFile));
            if (ownFile.Length > 0)
                places.Add(new Place(InOwnFolder, ownFile));
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            places.RemoveAll(p => !seen.Add(Path.GetFullPath(p.File)));
            return places;
        }

        /// <summary>The numbers from every copy (Numbers.Merge), what reading them said in `said`.</summary>
        public static Numbers Read(List<Place> places, List<string> said)
        {
            var copies = new List<Numbers.Copy>();
            foreach (var place in places)
            {
                string? text = null;
                try
                {
                    if (File.Exists(place.File))
                        text = File.ReadAllText(place.File);
                }
                catch (Exception e) when (e is IOException || e is UnauthorizedAccessException)
                {
                    said.Add($"its numbers' copy {place.Where} can't be read ({e.Message}).");
                }
                copies.Add(new Numbers.Copy(place.Where, text));
            }
            return Numbers.Merge(copies, said);
        }

        /// <summary>The numbers written into every copy, when they changed (or a copy was missing or said other);
        /// a copy that can't be written is said.</summary>
        public static void Keep(List<Place> places, Numbers numbers, Action<string> say)
        {
            if (!numbers.Changed)
                return;
            string text = numbers.Text();
            var failed = new List<string>();
            foreach (var place in places)
            {
                try
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(place.File)!);
                    File.WriteAllText(place.File, text);
                }
                catch (Exception e) when (e is IOException || e is UnauthorizedAccessException)
                {
                    failed.Add($"{place.Where} ({e.Message})");
                }
            }
            if (failed.Count > 0 && failed.Count == places.Count)
                say($"the numbers given can't be kept anywhere ({string.Join("; ", failed)}): next time they may "
                    + "differ.");
            else
                foreach (var why in failed)
                    say($"the numbers given can't be kept {why}: the other copies keep them.");
        }
    }
}
