// Mod Studio's checks of the helper (dev/test_event_setup.py runs them): the
// helper's own code finds the table in a program's file laid out as the
// game lays it out in memory, and applies mods' EventSetup.json files to a
// copy, saying what it found, read and changed. Part of The Ivalice
// Chronicles Mod Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll <program> <report.json> [<mod name>=<EventSetup.json> ...]
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using ModStudioEventSetup;

static class Program
{
    /// <summary>The program's file laid out as in memory: its headers, then each section's
    /// stored bytes at its own address (the rest zero).</summary>
    static byte[] Image(byte[] file)
    {
        int pe = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(0x3C, 4));
        int count = BinaryPrimitives.ReadUInt16LittleEndian(file.AsSpan(pe + 6, 2));
        int optionalSize = BinaryPrimitives.ReadUInt16LittleEndian(file.AsSpan(pe + 20, 2));
        int optional = pe + 24;
        int imageSize = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(optional + 56, 4));
        int headers = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(optional + 60, 4));
        var image = new byte[imageSize];
        file.AsSpan(0, Math.Min(headers, file.Length)).CopyTo(image);
        for (int n = 0; n < count; n++)
        {
            int at = optional + optionalSize + 40 * n;
            int size = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(at + 8, 4));
            int address = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(at + 12, 4));
            int stored = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(at + 16, 4));
            int raw = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(at + 20, 4));
            int length = Math.Min(stored, size == 0 ? stored : size);
            length = Math.Min(length, Math.Min(file.Length - raw, image.Length - address));
            if (length > 0)
                file.AsSpan(raw, length).CopyTo(image.AsSpan(address));
        }
        return image;
    }

    static int Main(string[] args)
    {
        var file = File.ReadAllBytes(args[0]);
        byte[] image;
        try
        {
            image = Image(file);
        }
        catch (Exception e) when (e is ArgumentException || e is IndexOutOfRangeException)
        {
            image = file;
        }
        var report = new Dictionary<string, object?>();
        var table = Finder.Find(image, out string why);
        report["why"] = why;
        report["found"] = table == null ? null : new Dictionary<string, object>
        {
            ["address"] = table.Address,
            ["how"] = table.How,
            ["events"] = table.SlotOf.Count,
            ["slots"] = table.Slots,
        };
        var copy = (byte[])image.Clone();
        var applier = new Applier();
        var mods = new List<object>();
        for (int n = 2; n < args.Length; n++)
        {
            int split = args[n].IndexOf('=');
            string name = args[n].Substring(0, split);
            var problems = new List<string>();
            var changes = SetupFile.Read(File.ReadAllText(args[n].Substring(split + 1)), problems);
            var said = table == null
                ? new List<string>()
                : applier.Apply(copy.AsSpan(table.Address, table.Bytes), table, name, changes);
            var asked = new List<object>();
            foreach (var change in changes)
                asked.Add(new object[] { change.Event, change.Field.Key, change.Value });
            mods.Add(new Dictionary<string, object> { ["name"] = name, ["changes"] = asked, ["problems"] = problems, ["said"] = said });
        }
        report["mods"] = mods;
        var changed = new List<int[]>();
        for (int at = 0; at < image.Length; at++)
            if (image[at] != copy[at])
                changed.Add(new[] { at, image[at], copy[at] });
        report["changed"] = changed;
        var fields = new List<object>();
        foreach (var field in Fields.All)
            fields.Add(new object[] { field.Key, field.At, field.Size, field.Mask, field.Most });
        report["fields"] = fields;
        File.WriteAllText(args[1], JsonSerializer.Serialize(report));
        return 0;
    }
}
