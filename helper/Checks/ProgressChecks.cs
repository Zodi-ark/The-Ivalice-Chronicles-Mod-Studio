// Mod Studio's checks of the helper: (1.38.0) a unit's progress in more than
// one of the mods' jobs (JobProgress.cs), over a party, battle units and menu
// copies made up here as the game lays them out. dev/test_jobs.py writes the
// steps and reads what each left. Part of The Ivalice Chronicles Mod Studio,
// GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --progress <request.json> <report.json>
//
// The request: {"jobs": [{"name", "number"}], "folders": [..], "names": {"<number>": "<name>"}, "steps": [..]}. A step is
// one of: {"do": "poke", "in": "party" | "battle" | "menu" | "records" | "one" | "bank", "at", "hex"} ((1.38.1) "records"
// the battle's own records of its units, "one" the one record on its own); {"do": "peek", "in", "at", "bytes"};
// {"do": "copied"} (the game is about to take its copy of the battle: the mark is written) and {"do": "restored", "party",
// "from"} (it put the copy back: "party" false when the party's records didn't come with it, "from" the variables that
// came, "copybank" or "bank"; the memory is the steps' own to copy); {"do": "refused"} (how often a job's progress read
// as less than was brought in, the last such job and place, and the line said of it);
// {"do": "swap", "job"}; {"do": "built", "battle"}; (1.53.0) {"do": "writing", "battle"} (the game is about to write that
// battle unit back: the job loaded after); {"do": "back", "battle", "place"} (the place the game wrote the unit
// to; the place the unit names when left out); {"do": "made", "battle"} or {"do": "made", "temp": true} (the game is about
// to make a record of that battle unit, or of the unit made for the moment in "temp"); {"do": "shown", "index"};
// {"do": "saving"}; {"do": "load"}; {"do": "again", "jobs": [..]} (the framework started again with these jobs, the
// memory kept); {"do": "kept", "job", "place"} (the party's side); {"do": "there", "job", "battle"} (the battle's side:
// null when the battle unit has none of its own). The report: one entry a step. (1.38.2) "in" is also "copybank" (the
// game's copy of the variables) or "temp" (a unit made for the moment, outside the battle's units). {"do": "take"}: the
// game takes a state (everything here kept aside, the variables into "copybank" too); {"do": "give", "what"}: it puts
// one back as its own functions do: "plain" (0x2CF768, 0x21B0E8: the party's records and the variables), "part"
// (0x2CE5C8: the party's records and the battle's units) or "whole" (0x2CE7A8: the variables, the battle's units and
// every record). (1.38.3) "in" is also "copy" (a copy the game took of a battle unit, outside the battle's units);
// {"do": "built", "temp": true} (the game made the unit in "temp" from a party's record); {"do": "made", "copy": true};
// {"do": "seen", "in", "at"} (the game is about to copy the record there for the status card; nowhere when "in" is left
// out). (1.38.4) The request's "copiesBefore", and an "again" step's own: the number the copies of a battle are counted
// from (0 when left out).
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text.Json;
using ModStudioEventSetup;

static unsafe class ProgressChecks
{
    public static int Run(string[] args)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(args[1]));
        var r = doc.RootElement;
        int party = JobProgress.Places * JobProgress.UnitBytes, battle = JobProgress.BattleUnits * JobProgress.BattleBytes,
            menu = JobProgress.MenuRecords * JobProgress.MenuBytes, own = (JobProgress.BattleUnits + 1) * JobProgress.MenuBytes;
        byte* memory = (byte*)NativeMemory.AllocZeroed((nuint)(party + battle + menu + own + 2 * Framework.BankBytes + 16
                                                               + 2 * JobProgress.BattleBytes));
        byte* roster = memory, units = memory + party, copies = units + battle, records = copies + menu,
              one = records + JobProgress.BattleUnits * JobProgress.MenuBytes, bank = records + own;
        int* cell = (int*)(bank + Framework.BankBytes);
        byte* copyBank = bank + Framework.BankBytes + 16, temp = copyBank + Framework.BankBytes, copy = temp + JobProgress.BattleBytes;
        int all = party + battle + menu + own + Framework.BankBytes;
        byte* aside = (byte*)NativeMemory.AllocZeroed((nuint)all);
        void Give(byte* what, int bytes) => Buffer.MemoryCopy(aside + (what - memory), what, bytes, bytes);
        for (int place = 0; place < JobProgress.Places; place++)
            roster[place * JobProgress.UnitBytes + JobProgress.PlaceAt] = JobProgress.NoPlace;
        // A record of nobody names no unit; the game's own are cleared as they are made (0x360048, 0x284A08).
        for (int m = 0; m < JobProgress.MenuRecords + JobProgress.BattleUnits + 1; m++)
            *(ushort*)(copies + m * JobProgress.MenuBytes + JobProgress.MenuPlaceAt) = 0xFFFF;
        var folders = new List<string>();
        foreach (var f in r.GetProperty("folders").EnumerateArray())
            folders.Add(f.GetString()!);
        var names = new Dictionary<int, string>();
        if (r.TryGetProperty("names", out var known))
            foreach (var n in known.EnumerateObject())
                names[int.Parse(n.Name)] = n.Value.GetString()!;

        JobProgress Make(JsonElement jobs, JsonElement from)
        {
            int before = from.TryGetProperty("copiesBefore", out var counted) ? counted.GetInt32() : 0;
            var jobNames = new List<string>();
            var numbers = new List<int>();
            foreach (var j in jobs.EnumerateArray())
            {
                jobNames.Add(j.GetProperty("name").GetString()!);
                numbers.Add(j.GetProperty("number").GetInt32());
            }
            return new JobProgress(roster, units, copies, records, one, jobNames, numbers, folders, cell, before);
        }

        byte* In(string where) => where switch
        {
            "party" => roster, "battle" => units, "menu" => copies, "records" => records, "one" => one,
            "copybank" => copyBank, "temp" => temp, "copy" => copy, _ => bank,
        };
        Func<int, string?> nameOf = n => names.TryGetValue(n, out var name) ? name : null;
        var progress = Make(r.GetProperty("jobs"), r);
        var report = new List<object?>();
        foreach (var step in r.GetProperty("steps").EnumerateArray())
        {
            string what = step.GetProperty("do").GetString()!;
            var said = new List<string>();
            switch (what)
            {
                case "poke":
                    byte[] bytes = Convert.FromHexString(step.GetProperty("hex").GetString()!);
                    Marshal.Copy(bytes, 0, (nint)(In(step.GetProperty("in").GetString()!) + step.GetProperty("at").GetInt32()), bytes.Length);
                    report.Add(null);
                    break;
                case "peek":
                    report.Add(Convert.ToHexString(new ReadOnlySpan<byte>(In(step.GetProperty("in").GetString()!) + step.GetProperty("at").GetInt32(),
                                                                          step.GetProperty("bytes").GetInt32())));
                    break;
                case "swap":
                    progress.Swap(step.GetProperty("job").GetInt32());
                    report.Add(new Dictionary<string, object?> { ["loaded"] = progress.Loaded, ["cell"] = *cell });
                    break;
                case "take":
                    Buffer.MemoryCopy(memory, aside, all, all);
                    Buffer.MemoryCopy(bank, copyBank, Framework.BankBytes, Framework.BankBytes);
                    report.Add(null);
                    break;
                case "give":
                    string kind = step.GetProperty("what").GetString()!;
                    if (kind != "whole")
                        Give(roster, party);
                    if (kind != "part")
                        Give(bank, Framework.BankBytes);
                    if (kind != "plain")
                        Give(units, battle);
                    if (kind == "whole")
                        Give(copies, menu + own);
                    report.Add(null);
                    break;
                case "built":
                    progress.Built(step.TryGetProperty("temp", out _) ? temp
                                   : units + step.GetProperty("battle").GetInt32() * JobProgress.BattleBytes);
                    report.Add(null);
                    break;
                case "writing":
                    // (1.53.0) The game is about to write that battle unit back to a place of the party's.
                    progress.WritingBack(units + step.GetProperty("battle").GetInt32() * JobProgress.BattleBytes);
                    report.Add(new Dictionary<string, object?> { ["loaded"] = progress.Loaded, ["cell"] = *cell });
                    break;
                case "back":
                    byte* written = units + step.GetProperty("battle").GetInt32() * JobProgress.BattleBytes;
                    progress.WrittenBack(written, step.TryGetProperty("place", out var to) ? to.GetInt32()
                                                                                          : written[JobProgress.BattlePlaceAt]);
                    report.Add(null);
                    break;
                case "made":
                    progress.Made(step.TryGetProperty("temp", out _) ? temp : step.TryGetProperty("copy", out _) ? copy
                                  : units + step.GetProperty("battle").GetInt32() * JobProgress.BattleBytes);
                    report.Add(new Dictionary<string, object?> { ["loaded"] = progress.Loaded, ["cell"] = *cell });
                    break;
                case "seen":
                    progress.Seen(step.TryGetProperty("in", out var seenIn) ? In(seenIn.GetString()!) + step.GetProperty("at").GetInt32()
                                                                            : null);
                    report.Add(new Dictionary<string, object?> { ["loaded"] = progress.Loaded, ["cell"] = *cell });
                    break;
                case "shown":
                    progress.Shown(step.GetProperty("index").GetInt32());
                    report.Add(new Dictionary<string, object?> { ["loaded"] = progress.Loaded, ["cell"] = *cell });
                    break;
                case "copied":
                    progress.Copied(new Span<byte>(bank, Framework.BankBytes), said);
                    report.Add(new Dictionary<string, object?>
                    {
                        ["said"] = said,
                        ["mark"] = Convert.ToHexString(new ReadOnlySpan<byte>(bank + JobProgress.MarkAt, JobProgress.MarkBytes)),
                    });
                    break;
                case "restored":
                    bool partyToo = !step.TryGetProperty("party", out var came) || came.GetBoolean();
                    byte* with = In(step.TryGetProperty("from", out var which) ? which.GetString()! : partyToo ? "copybank" : "bank");
                    progress.Restored(new ReadOnlySpan<byte>(with, Framework.BankBytes), partyToo, nameOf, said);
                    report.Add(new Dictionary<string, object?> { ["said"] = said, ["loaded"] = progress.Loaded, ["cell"] = *cell });
                    break;
                case "there":
                    report.Add(progress.There(step.GetProperty("job").GetInt32(), step.GetProperty("battle").GetInt32())?.ToString("X16"));
                    break;
                case "refused":
                    report.Add(new Dictionary<string, object?>
                    {
                        ["count"] = progress.Refused, ["job"] = progress.RefusedJob, ["place"] = progress.RefusedPlace,
                        ["line"] = JobProgress.RefusedLine(progress.RefusedJob, progress.RefusedPlace),
                    });
                    break;
                case "saving":
                    progress.Saving(new Span<byte>(bank, Framework.BankBytes), said);
                    report.Add(new Dictionary<string, object?>
                    {
                        ["said"] = said,
                        ["mark"] = Convert.ToHexString(new ReadOnlySpan<byte>(bank + JobProgress.MarkAt, JobProgress.MarkBytes)),
                    });
                    break;
                case "load":
                    progress.Load(new ReadOnlySpan<byte>(bank, Framework.BankBytes), nameOf, said);
                    report.Add(new Dictionary<string, object?> { ["said"] = said, ["loaded"] = progress.Loaded, ["cell"] = *cell });
                    break;
                case "again":
                    progress = Make(step.GetProperty("jobs"), step);
                    report.Add(new Dictionary<string, object?> { ["loaded"] = progress.Loaded, ["cell"] = *cell });
                    break;
                case "kept":
                    report.Add(progress.Kept(step.GetProperty("job").GetInt32(), step.GetProperty("place").GetInt32()).ToString("X16"));
                    break;
                case "level":
                    // (1.48.0) A unit's level in one of the jobs, by one of the records there are (looked at first).
                    progress.Looked();
                    report.Add(new Dictionary<string, object?>
                    {
                        ["level"] = progress.Level(step.GetProperty("job").GetInt32(), step.GetProperty("record").GetInt32()),
                        ["owned"] = progress.Owned(step.GetProperty("record").GetInt32()),
                        ["index"] = progress.IndexOf(In(step.TryGetProperty("in", out var levelIn) ? levelIn.GetString()! : "menu")
                                                     + step.GetProperty("record").GetInt32() * JobProgress.MenuBytes),
                    });
                    break;
                case "ask":
                {
                    // (1.48.0) The asker of the jobs' needs over the menu's records as they are: "needs" each job's
                    // ([known, level, own] each), "never" which can't be opened, "index" which record the screens are
                    // of; then what it answers: each job's mark, whether each of "open" ([unit, number] pairs) is
                    // open, and with "general" and "jobs" (tables, base64) what "needed" jobs need and the records
                    // made for "stand" ([job, closed] pairs).
                    var numbers = new List<int>();
                    foreach (var j in r.GetProperty("jobs").EnumerateArray())
                        numbers.Add(j.GetProperty("number").GetInt32());
                    var needs = new List<JobNeeds.Need[]>();
                    foreach (var list in step.GetProperty("needs").EnumerateArray())
                    {
                        var each = new List<JobNeeds.Need>();
                        // (1.55.1) A fourth: whether the job is needed mastered.
                        foreach (var n in list.EnumerateArray())
                            each.Add(new JobNeeds.Need(n[0].GetInt32(), n[1].GetInt32(), n[2].GetInt32(),
                                                       n.GetArrayLength() > 3 && n[3].GetBoolean()));
                        needs.Add(each.ToArray());
                    }
                    var never = new bool[numbers.Count];
                    if (step.TryGetProperty("never", out var nevers))
                        for (int k = 0; k < never.Length; k++)
                            never[k] = nevers[k].GetBoolean();
                    short* index = (short*)NativeMemory.AllocZeroed(8);
                    byte** table = (byte**)NativeMemory.AllocZeroed((nuint)(8 * JobProgress.MenuRecords));
                    for (int k = 0; k < JobProgress.MenuRecords; k++)
                        table[k] = copies + k * JobProgress.MenuBytes;
                    *index = (short)step.GetProperty("index").GetInt32();
                    var asker = new JobAsker(new JobNeeds.Plan(numbers.ToArray(), needs.ToArray(), never), progress, index, table,
                                             JobProgress.MenuRecords, new object());
                    if (step.TryGetProperty("general", out var generalTable))
                        asker.General = Convert.FromBase64String(generalTable.GetString()!);
                    if (step.TryGetProperty("jobTable", out var jobTable))
                        asker.Jobs = Convert.FromBase64String(jobTable.GetString()!);
                    // (1.55.1) "places": [slot, 24 bools] pairs, which places of the game's jobs' skillsets hold an ability.
                    if (step.TryGetProperty("places", out var askPlaces))
                        foreach (var pair in askPlaces.EnumerateArray())
                        {
                            var held = new List<bool>();
                            foreach (var b in pair[1].EnumerateArray())
                                held.Add(b.GetBoolean());
                            asker.Plan.Places[pair[0].GetInt32()] = held;
                        }
                    var answer = new Dictionary<string, object?>();
                    // (1.55.1) Which needs of each "masteredNeeds" job are of a job mastered; whether the unit has mastered
                    // each "hasMastered" slot; the key Job Summary reads for each "summaryKeys" key.
                    if (step.TryGetProperty("masteredNeeds", out var askMastered))
                    {
                        var each = new List<bool[]?>();
                        foreach (var job in askMastered.EnumerateArray())
                            each.Add(asker.MasteredNeeds(job.GetInt32()));
                        answer["masteredNeeds"] = each;
                    }
                    if (step.TryGetProperty("hasMastered", out var askHas))
                    {
                        var each = new List<bool>();
                        foreach (var slot in askHas.EnumerateArray())
                            each.Add(asker.HasMastered(slot.GetInt32()));
                        answer["hasMastered"] = each;
                    }
                    if (step.TryGetProperty("summaryKeys", out var askKeys))
                    {
                        var each = new List<int>();
                        foreach (var key in askKeys.EnumerateArray())
                            each.Add(asker.SummaryKey(key.GetInt32()));
                        answer["summaryKeys"] = each;
                    }
                    var marks = new List<int>();
                    for (int k = 0; k < numbers.Count; k++)
                        marks.Add(asker.Mark(k));
                    answer["marks"] = marks;
                    if (step.TryGetProperty("open", out var askOpen))
                    {
                        var opened = new List<int>();
                        foreach (var pair in askOpen.EnumerateArray())
                            opened.Add(asker.Open(pair[0].GetInt32(), pair[1].GetInt32()));
                        answer["open"] = opened;
                    }
                    if (step.TryGetProperty("needed", out var askNeeded))
                    {
                        var needed = new List<int[]?>();
                        foreach (var job in askNeeded.EnumerateArray())
                            needed.Add(asker.Needed(job.GetInt32()));
                        answer["needed"] = needed;
                    }
                    if (step.TryGetProperty("stand", out var askStand))
                    {
                        var stood = new List<object?>();
                        byte* place = (byte*)NativeMemory.AllocZeroed((nuint)JobNeeds.PlaceBytes);
                        foreach (var pair in askStand.EnumerateArray())
                        {
                            new Span<byte>(place, JobNeeds.PlaceBytes).Fill(0xEE);
                            bool made = asker.Stand(pair[0].GetInt32(), pair[1].GetInt32(), (nint)place);
                            stood.Add(made ? Convert.ToHexString(new ReadOnlySpan<byte>(place, JobNeeds.PlaceBytes)) : null);
                        }
                        NativeMemory.Free(place);
                        answer["stand"] = stood;
                    }
                    NativeMemory.Free(index);
                    NativeMemory.Free(table);
                    report.Add(answer);
                    break;
                }
                default:
                    report.Add("?");
                    break;
            }
        }
        var whole = new Dictionary<string, object?>
        {
            ["steps"] = report,
            ["markAt"] = JobProgress.MarkAt,
            ["flagFreeAtMark"] = ItemRoom.FlagFree((JobProgress.MarkAt - Framework.BankTail) * 8),
            ["flagFreeBefore"] = ItemRoom.FlagFree((JobProgress.MarkAt - Framework.BankTail) * 8 - 1),
            ["flagByteAtMark"] = Framework.IsFlagByte(JobProgress.MarkAt),
        };
        File.WriteAllText(args[2], JsonSerializer.Serialize(whole));
        NativeMemory.Free(memory);
        NativeMemory.Free(aside);
        return 0;
    }
}
