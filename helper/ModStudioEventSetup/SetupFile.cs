// Mod Studio Event Setup: reading a mod's EventSetup.json. Part of The
// Ivalice Chronicles Mod Studio, GPL-3.0.
//
// The file Mod Studio writes (mod_studio/event_setup.py's file_text), read
// as event_setup.read_file_text reads it: the Events list's entries, each an
// Event number and fields named as the fields are (without case), each a
// whole number the field holds. What can't be applied is left out and said.
using System;
using System.Collections.Generic;
using System.Text.Json;

namespace ModStudioEventSetup
{
    public static class SetupFile
    {
        public const string Name = "EventSetup.json";

        static bool Whole(JsonElement value, out long number)
        {
            number = 0;
            return value.ValueKind == JsonValueKind.Number && value.TryGetInt64(out number);
        }

        /// <summary>The changes a file asks for, in its order; what is left out goes in problems.</summary>
        public static List<Change> Read(string text, List<string> problems)
        {
            var changes = new List<Change>();
            JsonDocument document;
            try
            {
                document = JsonDocument.Parse(text);
            }
            catch (JsonException e)
            {
                problems.Add($"it isn't JSON ({e.Message})");
                return changes;
            }
            using (document)
            {
                var top = document.RootElement;
                if (top.ValueKind != JsonValueKind.Object || !top.TryGetProperty("Events", out var events)
                    || events.ValueKind != JsonValueKind.Array)
                {
                    problems.Add("it has no Events list");
                    return changes;
                }
                int n = 0;
                foreach (var entry in events.EnumerateArray())
                {
                    n++;
                    if (entry.ValueKind != JsonValueKind.Object)
                    {
                        problems.Add($"entry {n} isn't a list of fields");
                        continue;
                    }
                    long ev = -1;
                    foreach (var property in entry.EnumerateObject())
                    {
                        if (string.Equals(property.Name, "event", StringComparison.OrdinalIgnoreCase))
                        {
                            if (!Whole(property.Value, out ev))
                                ev = -1;
                            break;
                        }
                    }
                    if (ev < 1 || ev > 0xFFFF)
                    {
                        problems.Add($"entry {n} has no event number");
                        continue;
                    }
                    foreach (var property in entry.EnumerateObject())
                    {
                        if (string.Equals(property.Name, "event", StringComparison.OrdinalIgnoreCase))
                            continue;
                        var field = Fields.Find(property.Name);
                        if (field == null)
                            problems.Add($"event {ev}: no field is named {property.Name}");
                        else if (!Whole(property.Value, out long value) || value < 0 || value > field.Most)
                            problems.Add($"event {ev}: {field.Key} holds 0 to {field.Most}, not {property.Value.GetRawText()}");
                        else
                            changes.Add(new Change((int)ev, field, (int)value));
                    }
                }
            }
            return changes;
        }
    }
}
