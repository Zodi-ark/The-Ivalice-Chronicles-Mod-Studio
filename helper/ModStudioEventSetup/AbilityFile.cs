// Reading a mod's own action ability, and giving it a number (the road's step 4; Zodi's answer of 10 November 2026:
// "Straight to more"). The build's second step. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// (1.41.0) Part of the helper since new abilities moved in for test 94 (built beside it until the whole rehearsed).
//
// An ability is a folder of its own in a mod, `ModStudioAbilities/<ability>/`, holding `ability.json`:
//
//     { "Format": "Mod Studio ability", "Version": 1,
//       "Name": "Meteor Strike",
//       "Like": 16,
//       "Record": [8 numbers], "Action": [14 numbers],
//       "Words": { "Name": "Meteor Strike", "Description": "..." } }
//
// `Name` is what the mod's jobs call it by. `Like` is the game's action ability it looks like (1 to 367): its effect,
// and whatever else the game keeps by an ability's number that a mod can't give yet. `Record` is its common record as
// the game keeps an ability's (8 bytes: its cost to learn in two, its chance to be known, its kind and flags, four of
// flags for the units the game moves). `Action` is its action record's fourteen bytes as the game's table of action
// data has them, in the game's order: Range, EffectArea, Vertical, the four of Flags, Element, Formula, X, Y,
// InflictStatus, CT, MPCost (the six bytes after are the same for every ability of the game and are the framework's
// to write). `Words` are its name and description as the game shows them. What can't be used is left out and said.
//
// Only action abilities: what a reaction, support or movement ability does is the game's code, so a mod's data can
// give a new one nothing to do. A mod's job lists the game's own of those.
//
// A modder never chooses a number. The framework gives each ability one from 549 to 1023 (512 to 548 are the game's
// own) and keeps it, as it keeps a job's.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace ModStudioEventSetup
{
    /// <summary>A mod's own action ability, as its mod gives it.</summary>
    public sealed class ModAbility
    {
        public string ModId { get; }
        public string ModName { get; }
        public string Name { get; }
        /// <summary>The game's action ability it looks like (1 to 367).</summary>
        public int Like { get; }
        /// <summary>Its common record as the game keeps an ability's (8 bytes).</summary>
        public byte[] Record { get; }
        /// <summary>Its action record's first fourteen bytes.</summary>
        public byte[] Action { get; }
        public string WordName { get; }
        public string Description { get; }

        public ModAbility(string modId, string modName, string name, int like, byte[] record, byte[] action, string wordName,
                          string description)
        {
            ModId = modId;
            ModName = modName;
            Name = name;
            Like = like;
            Record = record;
            Action = action;
            WordName = wordName;
            Description = description;
        }

        /// <summary>The name its number is kept under.</summary>
        public string Key => $"{ModId}/{Name}";
        public string Who => $"{ModName}'s {Name}";

        /// <summary>Its action record whole, as the game keeps one: the fourteen bytes and the six every ability of
        /// the game has after them.</summary>
        public byte[] ActionRecord()
        {
            var record = new byte[AbilityFile.ActionRecordBytes];
            Action.CopyTo(record, 0);
            AbilityFile.ActionTail.CopyTo(record, AbilityFile.ActionBytes);
            return record;
        }
    }

    public static class AbilityFile
    {
        public const string Folder = "ModStudioAbilities", Name = "ability.json", Format = "Mod Studio ability";
        public const int Version = 1, RecordBytes = 8, ActionBytes = 14, ActionRecordBytes = 20, FirstLike = 1, LastLike = 367,
                         NameMost = 40, DescriptionMost = 300;
        /// <summary>The six bytes every action record of the game has after its fourteen.</summary>
        public static readonly byte[] ActionTail = { 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF };

        /// <summary>The abilities of a mod, each folder of `ModStudioAbilities` that has an `ability.json`, in the
        /// folders' order by name; what can't be used said in `problems`.</summary>
        public static List<ModAbility> ReadMod(string modId, string modName, string modFolder, List<string> problems)
        {
            var abilities = new List<ModAbility>();
            string root = Path.Combine(modFolder, Folder);
            if (!Directory.Exists(root))
                return abilities;
            var folders = new List<string>(Directory.GetDirectories(root));
            folders.Sort(StringComparer.Ordinal);
            foreach (var folder in folders)
            {
                string file = Path.Combine(folder, Name);
                if (!File.Exists(file))
                    continue;
                string folderName = Path.GetFileName(folder);
                var said = new List<string>();
                ModAbility? ability = null;
                try
                {
                    ability = Read(modId, modName, File.ReadAllText(file), said);
                }
                catch (Exception e) when (e is not OutOfMemoryException)
                {
                    said.Add($"it can't be read ({e.Message})");
                }
                if (ability != null && abilities.Exists(a => a.Name == ability.Name))
                {
                    said.Add($"another of the mod's abilities is named {ability.Name}");
                    ability = null;
                }
                foreach (var s in said)
                    problems.Add($"{modName}'s ability {folderName}: {s}");
                if (ability != null)
                    abilities.Add(ability);
            }
            return abilities;
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

        static string Raw(JsonElement e, string name)
        {
            if (!Has(e, name, out var value))
                return "nothing";
            string raw = value.GetRawText();
            return raw.Length > 80 ? raw.Substring(0, 77) + "..." : raw;
        }

        static string? Word(JsonElement words, string name, int most)
        {
            if (!Has(words, name, out var value) || value.ValueKind != JsonValueKind.String)
                return null;
            string text = value.GetString() ?? "";
            int breaks = 0;
            foreach (char ch in text)
                if (ch == '\n')
                    breaks++;
                else if (char.IsControl(ch))
                    return null;
            return text.Length > 0 && text.Length <= most && breaks <= (most == DescriptionMost ? 2 : 0) ? text : null;
        }

        static byte[]? Bytes(JsonElement root, string name, int count)
        {
            if (!Has(root, name, out var values) || values.ValueKind != JsonValueKind.Array || values.GetArrayLength() != count)
                return null;
            var bytes = new byte[count];
            int n = 0;
            foreach (var b in values.EnumerateArray())
            {
                if (b.ValueKind != JsonValueKind.Number || !b.TryGetInt32(out int value) || value < 0 || value > 255)
                    return null;
                bytes[n++] = (byte)value;
            }
            return bytes;
        }

        /// <summary>An ability from its file's text, or null with why in `problems`.</summary>
        public static ModAbility? Read(string modId, string modName, string text, List<string> problems)
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
                var root = document.RootElement;
                if (root.ValueKind != JsonValueKind.Object)
                {
                    problems.Add($"its {Name} isn't a list of fields");
                    return null;
                }
                if (!Has(root, "Format", out var format) || format.ValueKind != JsonValueKind.String
                    || format.GetString() != Format)
                {
                    problems.Add($"its Format isn't \"{Format}\"");
                    return null;
                }
                if (!Has(root, "Version", out var version) || version.ValueKind != JsonValueKind.Number
                    || !version.TryGetInt32(out int v) || v != Version)
                {
                    problems.Add($"its Version is {Raw(root, "Version")}, not {Version}");
                    return null;
                }
                string? name = Word(root, "Name", NameMost);
                if (name == null)
                {
                    problems.Add($"its Name is {Raw(root, "Name")}, not text of 1 to {NameMost} characters");
                    return null;
                }
                if (!Has(root, "Like", out var likeValue) || likeValue.ValueKind != JsonValueKind.Number
                    || !likeValue.TryGetInt32(out int like) || like < FirstLike || like > LastLike)
                {
                    problems.Add($"its Like is {Raw(root, "Like")}, not one of the game's action abilities ({FirstLike} to {LastLike})");
                    return null;
                }
                byte[]? record = Bytes(root, "Record", RecordBytes);
                if (record == null)
                {
                    problems.Add($"its Record isn't a list of {RecordBytes} whole numbers from 0 to 255");
                    return null;
                }
                byte[]? action = Bytes(root, "Action", ActionBytes);
                if (action == null)
                {
                    problems.Add($"its Action isn't a list of {ActionBytes} whole numbers from 0 to 255");
                    return null;
                }
                if (!Has(root, "Words", out var words) || words.ValueKind != JsonValueKind.Object)
                {
                    problems.Add("it has no Words");
                    return null;
                }
                string? wordName = Word(words, "Name", NameMost);
                if (wordName == null)
                {
                    problems.Add($"its Words' Name is {Raw(words, "Name")}, not text of 1 to {NameMost} characters");
                    return null;
                }
                string? description = Word(words, "Description", DescriptionMost);
                if (description == null)
                {
                    problems.Add($"its Words' Description is {Raw(words, "Description")}, not text of 1 to {DescriptionMost} "
                                 + "characters with up to two line breaks");
                    return null;
                }
                return new ModAbility(modId, modName, name, like, record, action, wordName, description);
            }
        }

        /// <summary>An ability and the number it is given.</summary>
        public readonly struct Given
        {
            public ModAbility Ability { get; }
            public int Number { get; }

            public Given(ModAbility ability, int number)
            {
                Ability = ability;
                Number = number;
            }
        }

        /// <summary>Each ability given its number (Numbers.json's Abilities, the same number every time): the one kept
        /// under its key where there is one (and it is one a mod's ability may have, and no other ability here has it),
        /// else the lowest from 549 to 1023 that no key has had. An ability there is no number left for is left out and
        /// said.</summary>
        public static List<Given> Plan(IList<ModAbility> abilities, Numbers numbers, List<string> said)
        {
            var given = new List<Given>();
            var taken = new HashSet<int>();
            var candidates = new List<int>();
            for (int n = AbilityRecords.First; n < AbilityRecords.Count; n++)
                candidates.Add(n);
            // The numbers kept first, so that an ability given a new number never takes one another here keeps.
            var waiting = new List<ModAbility>();
            foreach (var ability in abilities)
            {
                if (numbers.Has(Numbers.AbilitiesKind, ability.Key, out int had) && had >= AbilityRecords.First
                    && had < AbilityRecords.Count && taken.Add(had))
                    given.Add(new Given(ability, had));
                else
                    waiting.Add(ability);
            }
            foreach (var ability in waiting)
            {
                int number = numbers.Give(Numbers.AbilitiesKind, ability.Key, candidates,
                                          n => n >= AbilityRecords.First && n < AbilityRecords.Count && !taken.Contains(n), out _);
                if (number < 0)
                {
                    said.Add($"{ability.Who} is left out: every number a mod's ability can have "
                             + $"({AbilityRecords.First} to {AbilityRecords.Count - 1}) is taken");
                    continue;
                }
                taken.Add(number);
                given.Add(new Given(ability, number));
            }
            given.Sort((a, b) => a.Number.CompareTo(b.Number));
            return given;
        }

        /// <summary>(1.41.0) The log's line for an ability given.</summary>
        public static string Line(Given g)
            => $"{g.Ability.Who} is ability {g.Number}, looking like the game's ability {g.Ability.Like}.";
    }
}
