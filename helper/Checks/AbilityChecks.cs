// Mod Studio's checks of the framework's longer table of the abilities' records (the road's step 4, new abilities, built
// straight to more by Zodi's answer of 10 November 2026; part of the helper since 1.41.0), run by dev/test_jobs.py.
// Part of The Ivalice Chronicles Mod Studio, GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --abilities <request.json> <report.json>
//
// The request: "program", his FFT_enhanced.exe. The report: "records", where the game's table is as the framework
// finds it; "missing", each reader not found once or naming another place; "readers", where each reader's four bytes
// of distance are; "counts", the game's count, a record's bytes, the longer count and the first number given. With
// "base" and "table" (addresses): "changes", each reader's place and its four new bytes. With "written", rounds of
// writes each ["game" or "table", a place in it, bytes as hex]: the longer table as it starts ("tableStarted"), how
// many records each round brought over ("brought") and the table after ("tableAfter"). With "mods" (each "id", "name",
// "folder") and "kept" (the numbers kept, by key): "problems", "said", "kept" after, and "given": each ability read
// with its number, its records and its words.
// (The build's sixth step, its words.) With "abilityTable" (a file of the game's Ability table as loaded) and
// "abilityTableOut": the table with the abilities' rows written there, "rowsSaid" and "rowsWhy". With "names" (a file
// standing in for the older text's names' file), "namesOut" and, where wanted, "namesRoom" (the bytes after the file,
// AbilityWords.NamesExtra where not given): the file's room after AbilityWords.Longer written there (the room filled
// with 0xEE first), "namesEnd" and "namesSaid". And of the room: "loader" (the loader's two places), "cells" (the
// cells' place and the names' cell) and "namesNumbers" (the file's number, the bytes more, the indexes).
// (The build's seventh step, how a user moves.) "animations", "animationsMissing", "animationReaders" and, for a table
// at "animationsTable", "animationChanges"; of the room, "animationsAt", "roomAnimations" and, with "animationsWritten",
// "animationsBrought" and "animationsAfter" (as the effects' are).
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using ModStudioEventSetup;

static class AbilityChecks
{
    public static int Run(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var r = request.RootElement;
        var report = new Dictionary<string, object?>();
        var image = Program.Load(r.GetProperty("program").GetString()!);
        var sections = Finder.Sections(image);
        int records = AbilityRecords.Locate(image, sections);
        report["records"] = records;
        report["counts"] = new[] { AbilityRecords.GameCount, AbilityRecords.RecordBytes, AbilityRecords.Count, AbilityRecords.First };
        var sites = AbilityRecords.Find(image, sections, records);
        report["missing"] = sites.Missing;
        report["readers"] = sites.ReaderAt;
        if (sites.Ok && r.TryGetProperty("table", out var tableAt))
        {
            var changes = AbilityRecords.Changes(sites, r.GetProperty("base").GetUInt64(), tableAt.GetUInt64());
            report["changes"] = changes?.ConvertAll(c => new object[] { c.At, Convert.ToHexString(c.Bytes) });
        }
        if (sites.Ok && r.TryGetProperty("written", out var written))
        {
            int gameBytes = AbilityRecords.GameCount * AbilityRecords.RecordBytes;
            var game = new ReadOnlySpan<byte>(image, records, gameBytes).ToArray();
            // (The room the table is given isn't empty to start with: what was there must not stay.)
            var table = new byte[AbilityRecords.Bytes];
            Array.Fill(table, (byte)0xEE);
            AbilityRecords.Fill(game, table);
            var seen = (byte[])game.Clone();
            report["tableStarted"] = Convert.ToHexString(table);
            var counts = new List<int>();
            foreach (var round in written.EnumerateArray())
            {
                foreach (var one in round.EnumerateArray())
                {
                    byte[] bytes = Convert.FromHexString(one[2].GetString()!);
                    var into = one[0].GetString() == "table" ? table : game;
                    bytes.CopyTo(into, one[1].GetInt32());
                }
                counts.Add(AbilityRecords.Sync(game, seen, table));
            }
            report["tableAfter"] = Convert.ToHexString(table);
            report["brought"] = counts;
        }
        // The longer table of the abilities' effects: where the game's is, each reader, and for a table at "effectsTable"
        // each reader's four new bytes.
        int effects = AbilityEffects.Locate(image, sections);
        report["effects"] = effects;
        var effectSites = AbilityEffects.Find(image, sections, effects);
        report["effectsMissing"] = effectSites.Missing;
        report["effectReaders"] = effectSites.ReaderAt;
        if (effectSites.Ok && r.TryGetProperty("effectsTable", out var effectsAt))
        {
            var changes = AbilityEffects.Changes(effectSites, r.GetProperty("base").GetUInt64(), effectsAt.GetUInt64());
            report["effectChanges"] = changes?.ConvertAll(c => new object[] { c.At, Convert.ToHexString(c.Bytes) });
        }
        // (The build's seventh step.) The longer table of how an ability's user moves: the same, by "animationsTable".
        int animations = AbilityAnimations.Locate(image, sections);
        report["animations"] = animations;
        var animationSites = AbilityAnimations.Find(image, sections, animations);
        report["animationsMissing"] = animationSites.Missing;
        report["animationReaders"] = animationSites.ReaderAt;
        if (animationSites.Ok && r.TryGetProperty("animationsTable", out var animationsAt))
        {
            var changes = AbilityAnimations.Changes(animationSites, r.GetProperty("base").GetUInt64(), animationsAt.GetUInt64());
            report["animationChanges"] = changes?.ConvertAll(c => new object[] { c.At, Convert.ToHexString(c.Bytes) });
        }
        // (The build's second step.) A mod's abilities as read, what is said of the ones that can't be used, and the
        // number each is given over the numbers kept.
        if (r.TryGetProperty("mods", out var mods))
        {
            var abilities = new List<ModAbility>();
            var problems = new List<string>();
            foreach (var mod in mods.EnumerateArray())
                abilities.AddRange(AbilityFile.ReadMod(mod.GetProperty("id").GetString()!, mod.GetProperty("name").GetString()!,
                                                       mod.GetProperty("folder").GetString()!, problems));
            report["problems"] = problems;
            // (1.41.0) The numbers kept as Numbers.json keeps them, under Abilities.
            var kept = new Dictionary<string, int>();
            if (r.TryGetProperty("kept", out var keptList))
                foreach (var one in keptList.EnumerateObject())
                    kept[one.Name] = one.Value.GetInt32();
            var numbers = Numbers.FromText(JsonSerializer.Serialize(new Dictionary<string, object> { [Numbers.AbilitiesKind] = kept }),
                                           problems);
            var said = new List<string>();
            var given = AbilityFile.Plan(abilities, numbers, said);
            report["said"] = said;
            report["kept"] = new SortedDictionary<string, int>(new Dictionary<string, int>(numbers.GivenOf(Numbers.AbilitiesKind)),
                                                               StringComparer.Ordinal);
            // (The build's fourth step.) The framework's code in the game's central routines for a room at "room",
            // the changes that send them to it, and the room's lists for the abilities given and the "places" asked
            // (each a skillset, a place in it, an ability's key).
            if (r.TryGetProperty("room", out var roomAt))
            {
                var entries = AbilityRoom.Find(image, sections);
                report["entries"] = entries.At;
                report["entriesMissing"] = entries.Missing;
                report["compares"] = entries.CompareAt;
                report["cuts"] = entries.CutAt;
                report["loader"] = entries.LoaderAt;
                report["charging"] = entries.ChargingAt;
                report["units"] = entries.UnitsAt;
                report["filters"] = entries.FilterAt;
                // (1.41.2, his test 95) The menu's confirm's cut, the turn order writer's load, the two text places, and
                // where the writer's table of readied words is in the room.
                report["menuCut"] = entries.MenuCutAt;
                report["writer"] = entries.WriterAt;
                report["texts"] = entries.TextAt;
                report["turnOrderAt"] = AbilityRoom.TurnOrderAt;
                report["cells"] = new[] { AbilityRoom.CellsAt, AbilityRoom.NamesCell };
                report["namesNumbers"] = new[] { AbilityWords.NamesFile, AbilityWords.NamesExtra, AbilityWords.NamesIndexes };
                report["layout"] = new[] { AbilityRoom.CodeRoom, AbilityRoom.LikesAt, AbilityRoom.ActionsAt, AbilityRoom.PlacesAt,
                                           AbilityRoom.RecordsAt, AbilityRoom.Room, AbilityRoom.Skillsets, AbilityRoom.PlacesEach };
                report["effectsAt"] = AbilityRoom.EffectsAt;
                report["animationsAt"] = AbilityRoom.AnimationsAt;
                if (entries.Ok)
                {
                    var code = AbilityRoom.Code(image, entries, r.GetProperty("base").GetUInt64(), roomAt.GetUInt64(), out var codeChanges);
                    report["code"] = Convert.ToHexString(code);
                    report["codeChanges"] = codeChanges.ConvertAll(c => new object[] { c.At, Convert.ToHexString(c.Bytes) });
                    var places = new List<(int, int, int)>();
                    if (r.TryGetProperty("places", out var placeList))
                        foreach (var one in placeList.EnumerateArray())
                        {
                            var g = given.Find(x => x.Ability.Key == one[2].GetString());
                            if (g.Ability != null)
                                places.Add((one[0].GetInt32(), one[1].GetInt32(), g.Number));
                        }
                    var room = new byte[AbilityRoom.Room];
                    Array.Fill(room, (byte)0xEE);
                    AbilityRoom.Tables(room, given, places);
                    report["lists"] = Convert.ToHexString(room.AsSpan(AbilityRoom.LikesAt, AbilityRoom.RecordsAt - AbilityRoom.LikesAt));
                    report["roomRest"] = new int[] { room[0], room[AbilityRoom.LikesAt - 1], room[AbilityRoom.RecordsAt], room[AbilityRoom.Room - 1] };
                    // (1.41.0) The room as the helper starts it (AbilityRoom.Start, which AbilityHooks runs), over a
                    // room that isn't empty to start with: its lists, its code's part (left as it was), and the three
                    // longer tables.
                    var gameEffects = effectSites.Ok ? new ReadOnlySpan<byte>(image, effects, AbilityEffects.Bytes).ToArray()
                                                     : Array.Empty<byte>();
                    var gameAnimations = animationSites.Ok
                        ? new ReadOnlySpan<byte>(image, animations, AbilityAnimations.Bytes).ToArray() : Array.Empty<byte>();
                    var started = new byte[AbilityRoom.Room];
                    Array.Fill(started, (byte)0xEE);
                    AbilityRoom.Start(started, new ReadOnlySpan<byte>(image, records, AbilityRecords.GameCount * AbilityRecords.RecordBytes),
                                      gameEffects, gameAnimations, given, places);
                    report["startedLists"] = Convert.ToHexString(started.AsSpan(AbilityRoom.LikesAt, AbilityRoom.RecordsAt - AbilityRoom.LikesAt));
                    report["startedCode"] = Convert.ToHexString(started.AsSpan(0, AbilityRoom.CodeRoom));
                    // The longer table as the room has it: the game's records, then the mods' at their numbers.
                    var longer = started.AsSpan(AbilityRoom.RecordsAt, AbilityRecords.Bytes);
                    report["roomRecords"] = Convert.ToHexString(longer);
                    // The longer table of effects as the room has it: the program's own bytes, then each mod's word. And
                    // with "effectsWritten" (rounds of writes to the game's own words, each a place and bytes as hex):
                    // how many words each round brought over, and the table after, the mods' words made again.
                    if (effectSites.Ok)
                    {
                        var longerEffects = started.AsSpan(AbilityRoom.EffectsAt, AbilityEffects.Bytes);
                        report["roomEffects"] = Convert.ToHexString(longerEffects);
                        if (r.TryGetProperty("effectsWritten", out var effectRounds))
                        {
                            var seenEffects = (byte[])gameEffects.Clone();
                            var broughtEffects = new List<int>();
                            foreach (var round in effectRounds.EnumerateArray())
                            {
                                foreach (var one in round.EnumerateArray())
                                    Convert.FromHexString(one[1].GetString()!).CopyTo(gameEffects, one[0].GetInt32());
                                broughtEffects.Add(AbilityEffects.Sync(gameEffects, seenEffects, longerEffects));
                                AbilityEffects.Likes(longerEffects, given);
                            }
                            report["effectsBrought"] = broughtEffects;
                            report["effectsAfter"] = Convert.ToHexString(longerEffects);
                        }
                    }
                    // The longer table of how a user moves, the same way, with "animationsWritten".
                    if (animationSites.Ok)
                    {
                        var longerAnimations = started.AsSpan(AbilityRoom.AnimationsAt, AbilityAnimations.Bytes);
                        report["roomAnimations"] = Convert.ToHexString(longerAnimations);
                        if (r.TryGetProperty("animationsWritten", out var animationRounds))
                        {
                            var seenAnimations = (byte[])gameAnimations.Clone();
                            var broughtAnimations = new List<int>();
                            foreach (var round in animationRounds.EnumerateArray())
                            {
                                foreach (var one in round.EnumerateArray())
                                    Convert.FromHexString(one[1].GetString()!).CopyTo(gameAnimations, one[0].GetInt32());
                                broughtAnimations.Add(AbilityAnimations.Sync(gameAnimations, seenAnimations, longerAnimations));
                                AbilityAnimations.Likes(longerAnimations, given);
                            }
                            report["animationsBrought"] = broughtAnimations;
                            report["animationsAfter"] = Convert.ToHexString(longerAnimations);
                        }
                    }

                }
            }
            // (The build's sixth step.) The Ability table with the abilities' rows, and the names' file made longer.
            if (r.TryGetProperty("abilityTable", out var abilityTable))
            {
                var rowsSaid = new List<string>();
                byte[]? with = AbilityWords.WithRows(File.ReadAllBytes(abilityTable.GetString()!), given, rowsSaid, out string rowsWhy);
                report["rowsSaid"] = rowsSaid;
                report["rowsWhy"] = rowsWhy;
                report["rows"] = with != null;
                if (with != null)
                    File.WriteAllBytes(r.GetProperty("abilityTableOut").GetString()!, with);
            }
            if (r.TryGetProperty("names", out var names))
            {
                byte[] file = File.ReadAllBytes(names.GetString()!);
                int more = r.TryGetProperty("namesRoom", out var namesRoom) ? namesRoom.GetInt32() : AbilityWords.NamesExtra;
                var blob = new byte[file.Length + more];
                Array.Fill(blob, (byte)0xEE);
                file.AsSpan(0, Math.Min(file.Length, blob.Length)).CopyTo(blob);
                var namesSaid = new List<string>();
                report["namesEnd"] = AbilityWords.Longer(blob, file.Length, given, namesSaid);
                report["namesSaid"] = namesSaid;
                File.WriteAllBytes(r.GetProperty("namesOut").GetString()!, blob);
            }
            report["given"] = given.ConvertAll(g => new Dictionary<string, object>
            {
                ["key"] = g.Ability.Key, ["who"] = g.Ability.Who, ["number"] = g.Number, ["like"] = g.Ability.Like,
                ["record"] = Convert.ToHexString(g.Ability.Record), ["action"] = Convert.ToHexString(g.Ability.ActionRecord()),
                ["name"] = g.Ability.WordName, ["description"] = g.Ability.Description,
            });
        }
        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }
}
