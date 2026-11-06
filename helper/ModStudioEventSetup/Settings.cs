// Mod Studio Framework: (1.29.0) its settings' file, Config.json in its
// Reloaded-II settings folder, read and written (Configurator.cs gives it to
// Reloaded-II's Configure). Part of The Ivalice Chronicles Mod Studio,
// GPL-3.0. No Reloaded-II code here, so the checks build it.
using System;
using System.IO;
using System.Text.Json;

namespace ModStudioEventSetup
{
    public static class Settings
    {
        public const string FileName = "Config.json", FreeNumbersField = "FreeNumbers";

        /// <summary>Whether the file at `path` asks for the numbers of mods not enabled to be freed (its FreeNumbers true);
        /// false for no file, one that can't be read, or anything else.</summary>
        public static bool ReadFreeNumbers(string path)
        {
            try
            {
                if (!File.Exists(path))
                    return false;
                using var document = JsonDocument.Parse(File.ReadAllText(path));
                return document.RootElement.ValueKind == JsonValueKind.Object
                       && document.RootElement.TryGetProperty(FreeNumbersField, out var free)
                       && free.ValueKind == JsonValueKind.True;
            }
            catch (Exception e) when (e is IOException || e is UnauthorizedAccessException || e is JsonException)
            {
                return false;
            }
        }

        /// <summary>The file's text.</summary>
        public static string Text(bool freeNumbers)
            => "{\n  \"" + FreeNumbersField + "\": " + (freeNumbers ? "true" : "false") + "\n}\n";

        /// <summary>The file written at `path` (its folder made first).</summary>
        public static void Write(string path, bool freeNumbers)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path) is { Length: > 0 } folder ? folder : ".");
            File.WriteAllText(path, Text(freeNumbers));
        }
    }
}
