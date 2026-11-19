// Mod Studio's checks of the helper: (1.36.0) a mod's own job (JobFile.cs,
// JobRoom.cs, JobHooks.cs) over his program as the game lays it out.
// dev/test_jobs.py reads the report and runs the native code and his program's
// own code over it with unicorn. Part of The Ivalice Chronicles Mod Studio,
// GPL-3.0. Not shipped.
//
//     dotnet Checks.dll --jobs <request.json> <report.json>
//
// The request: {"program", "numbers" (a file or ""), "mods": [{"id", "name", "folder"}], "table" (a Job table's .nxd or
// ""), "base", "at" (where the program and the native code are taken to be), "roster" (a party's bytes in hex or ""),
// "given" (the numbers the mods give now, for Settle), and (1.44.2) "programFile" (the program's file the helper would
// read where another mod has hooked a routine: its path, "" for none, the program itself when not given), "fileAt"
// ([address, length] pairs read from it)}.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using ModStudioEventSetup;

static class JobChecks
{
    static string Hex(ReadOnlySpan<byte> bytes) => Convert.ToHexString(bytes);

    static Dictionary<string, string> Keyed(Dictionary<int, string> by)
    {
        var keyed = new Dictionary<string, string>();
        foreach (var (n, name) in by)
            keyed[n.ToString()] = name;
        return keyed;
    }

    /// <summary>As the other mod keeps its list.</summary>
    sealed class TheirMod
    {
#pragma warning disable CS0414, CS0649
        ushort[] _extraJobs = { 0xA0, 0xA1 };
#pragma warning restore CS0414, CS0649
        public ushort[] List => _extraJobs;
    }

    sealed class TheirStartup
    {
#pragma warning disable CS0414, CS0649
        object _mod = new TheirMod();
#pragma warning restore CS0414, CS0649
        public TheirMod Mod => (TheirMod)_mod;
    }

    sealed class NotTheirs { }

    public static int Run(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var r = request.RootElement;
        var report = new Dictionary<string, object?>();
        var image = Program.Load(r.GetProperty("program").GetString()!);
        var sections = Finder.Sections(image);
        var found = JobRoom.Find(image, sections);
        report["missing"] = found.Missing;
        // (2.0.1, his test 126) The jobs' places found again where Mod Studio Framework's items have hooked first
        // (Mod.PlanItems makes the items' hooks before Mod.PlanJobs finds the jobs' places): every function ItemHooks
        // hooks (ItemHooks.Arm: the getters, the save, the icons' two paths, the tables' setup and the Outfitter's
        // stock) given a jump of 14 bytes at its start, as a hook writes one, and JobRoom.Find run over that. Test 126
        // found no SaveWrite so: the items' Save is the same function.
        var items = ItemRoom.Find(image, sections);
        var itemsPlaces = Places.Find(image);
        var itemsHooked = new List<int>();
        var itemsHookedBytes = new List<string>();
        var withItems = (byte[])image.Clone();
        if (items.Ok)
        {
            foreach (var name in new List<string>(ItemRoom.Getters) { "Save", "IconPath", "SmallIconPath" })
                itemsHooked.Add(items.At[name]);
            itemsHooked.Add(itemsPlaces.SheetInit);
            itemsHooked.Add(itemsPlaces.Stock);
            foreach (int at in itemsHooked)
            {
                if (at < 0)
                    continue;
                withItems[at] = 0xFF;
                withItems[at + 1] = 0x25;
                for (int k = 2; k < 14; k++)
                    withItems[at + k] = (byte)(0x10 + k);
                itemsHookedBytes.Add(Convert.ToHexString(withItems, at, 14));
            }
        }
        var again = JobRoom.Find(withItems, Finder.Sections(withItems));
        var movedWithItems = new List<string>();
        foreach (var (name, at) in found.At)
            if (again.At.TryGetValue(name, out int there) && there != at)
                movedWithItems.Add(name);
        report["itemsHooked"] = itemsHooked;
        report["itemsHookedBytes"] = itemsHookedBytes;
        report["withItemsHooked"] = new Dictionary<string, object> { ["missing"] = again.Missing,
                                                                     ["moved"] = movedWithItems };
        // (2.0.7, his report of 18 November: WotL Restoration 3.1.0) The jobs' and the abilities' places found again
        // where another mod has hooked first: each place the request names ("theirHooks") given a jump of 14 bytes, as
        // a hook writes one, and JobRoom.Find and AbilityRoom.Find run over that.
        var abilityRoutines = AbilityRoom.Find(image, sections);
        report["abilityEntries"] = abilityRoutines.At;
        report["abilityMissing"] = abilityRoutines.Missing;
        if (r.TryGetProperty("theirHooks", out var theirList))
        {
            var withTheirs = (byte[])image.Clone();
            var theirBytes = new List<string>();
            foreach (var item in theirList.EnumerateArray())
            {
                int at = item.GetInt32();
                withTheirs[at] = 0xFF;
                withTheirs[at + 1] = 0x25;
                for (int k = 2; k < 14; k++)
                    withTheirs[at + k] = (byte)(0x20 + k);
                theirBytes.Add(Convert.ToHexString(withTheirs, at, 14));
            }
            var theirSections = Finder.Sections(withTheirs);
            var jobsThere = JobRoom.Find(withTheirs, theirSections);
            var abilitiesThere = AbilityRoom.Find(withTheirs, theirSections);
            var jobsMoved = new List<string>();
            foreach (var (name, at) in found.At)
                if (jobsThere.At.TryGetValue(name, out int there) && there != at)
                    jobsMoved.Add(name);
            var abilitiesMoved = new List<string>();
            foreach (var (name, at) in abilityRoutines.At)
                if (abilitiesThere.At.TryGetValue(name, out int there) && there != at)
                    abilitiesMoved.Add(name);
            report["withTheirHooks"] = new Dictionary<string, object>
            {
                ["bytes"] = theirBytes, ["jobsMissing"] = jobsThere.Missing, ["jobsMoved"] = jobsMoved,
                ["abilitiesMissing"] = abilitiesThere.Missing, ["abilitiesMoved"] = abilitiesMoved,
            };
        }
        report["at"] = found.At;
        report["records"] = found.Records;
        report["levelOf"] = found.LevelOf;
        report["levels"] = found.Levels;
        report["startJp"] = found.StartJp;
        report["skillsets"] = found.Skillsets;
        report["battle"] = found.Battle;
        report["menus"] = found.Menus;
        report["battleRecords"] = found.BattleRecords;
        report["oneRecord"] = found.OneRecord;
        report["copyBank"] = found.CopyBank;
        report["copyBankOf"] = found.CopyBankOf;
        report["menuIndex"] = found.MenuIndex;
        report["menuTable"] = found.MenuTable;
        var open = found.Ok ? JobRoom.OpenSkillsets(image, found) : new HashSet<int>(JobRoom.FreeSkillsets);
        var openList = new List<int>(open);
        openList.Sort();
        report["openSkillsets"] = openList;
        var jobs = new List<ModJob>();
        var problems = new List<string>();
        foreach (var mod in r.GetProperty("mods").EnumerateArray())
            jobs.AddRange(JobFile.ReadMod(mod.GetProperty("id").GetString()!, mod.GetProperty("name").GetString()!,
                                          mod.GetProperty("folder").GetString()!, problems));
        report["problems"] = problems;
        string file = r.GetProperty("numbers").GetString()!;
        var numberProblems = new List<string>();
        var numbers = file.Length > 0 && File.Exists(file) ? Numbers.FromText(File.ReadAllText(file), numberProblems)
                                                           : new Numbers();
        report["numberProblems"] = numberProblems;
        var said = new List<string>();
        // (1.40.0) The longer table of job records: every reader and bound as the helper finds them; with "more" asked
        // and all found, the numbers past the game's last are given too, and the changes for a table after the cells.
        JobRecords.Sites? records = found.Ok ? JobRecords.Find(image, Finder.Sections(image), found.Records) : null;
        if (records != null)
            report["longer"] = new Dictionary<string, object>
            {
                ["missing"] = records.Missing, ["readers"] = records.ReaderAt, ["bounds"] = records.BoundAt,
                ["computed"] = records.ComputedAt,
                ["numbers"] = JobRecords.Numbers, ["empty"] = Hex(JobRecords.Empty),
            };
        bool more = r.TryGetProperty("more", out var asked) && asked.GetBoolean() && records != null && records.Ok;
        // (1.55.0) "theirs": Dark Knight & Onion Knight (Generic) on, so no mod's job is the game's Dark Knight or Onion Knight.
        bool theirs = r.TryGetProperty("theirs", out var theirsValue) && theirsValue.GetBoolean();
        var given = JobRoom.Plan(jobs, numbers, said, open, more ? JobRecords.Numbers : null, theirs ? JobRoom.TheirGameJobs : null);
        report["said"] = said;
        report["shown"] = JobRoom.Shown(given);
        // (1.55.0) The five portrait routines' second read of the job, as the helper finds them.
        var specialMissing = new List<string>();
        var special = JobRoom.FindSpecial(image, sections, specialMissing);
        report["special"] = special;
        report["specialMissing"] = specialMissing;
        report["specialNotLine"] = JobRoom.SpecialNotLine(new[] { "Special1 (0 places like it, not 1)" }, "FFT_enhanced.exe",
                                                          "Mod Studio Framework");
        // (1.55.1) Job Summary's two reads of a job's words, as the helper finds them (where the game's Onion Knight a mod
        // gives has words for its level 8, it makes its code with them), and the lines.
        var summaryMissing = new List<string>();
        var summary = JobRoom.FindSummary(image, sections, summaryMissing);
        report["summary"] = summary;
        report["summaryMissing"] = summaryMissing;
        report["summaryNotLine"] = JobRoom.SummaryNotLine(new[] { "Summary1 (0 places like it, not 1)" }, "FFT_enhanced.exe",
                                                          "Mod Studio Framework");
        // ...and the line the helper says once the jobs are given (as Mod.cs decides it; null: none said).
        JobRoom.Given? summaryOnion = given.Find(g => g.Number == JobFile.OnionKnight && g.Job.MasteredWords);
        report["summaryLine"] = summaryOnion != null && summaryMissing.Count == 0 ? JobRoom.SummaryLine(summaryOnion.Job.Who)
                                                                                    : null;
        // (1.55.2) The job screen's window's read of a job's words, as the helper finds it (where the game's Onion Knight a
        // mod gives has a description for its level 8, it makes its code with it), and the lines.
        var helpWordsMissing = new List<string>();
        var helpWords = JobRoom.FindHelpWords(image, sections, helpWordsMissing);
        report["helpWords"] = helpWords;
        report["helpWordsMissing"] = helpWordsMissing;
        report["helpWordsNotLine"] = JobRoom.HelpWordsNotLine(new[] { "HelpWords (0 places like it, not 1)" }, "FFT_enhanced.exe",
                                                              "Mod Studio Framework");
        JobRoom.Given? helpOnion = given.Find(g => g.Number == JobFile.OnionKnight && g.Job.MasteredDescription != null);
        report["helpWordsLine"] = helpOnion != null && helpWordsMissing.Count == 0 ? JobRoom.HelpWordsLine(helpOnion.Job.Who)
                                                                                    : null;
        var codeSites = new Dictionary<string, int>(special);
        foreach (var site in summary)
            codeSites[site.Key] = site.Value;
        foreach (var site in helpWords)
            codeSites[site.Key] = site.Value;
        // (1.41.0) The mods' own abilities beside their jobs, as the helper takes them: numbered over the same numbers,
        // each place of the jobs' skillsets that names one settled (as when the abilities are made in the game where a
        // place holds one, or as when they can't be with "abilitiesMade": false), and what is said.
        var abilities = new List<ModAbility>();
        var abilityProblems = new List<string>();
        foreach (var mod in r.GetProperty("mods").EnumerateArray())
            abilities.AddRange(AbilityFile.ReadMod(mod.GetProperty("id").GetString()!, mod.GetProperty("name").GetString()!,
                                                   mod.GetProperty("folder").GetString()!, abilityProblems));
        var abilitySaid = new List<string>();
        var abilitiesGiven = AbilityFile.Plan(abilities, numbers, abilitySaid);
        var plan = AbilityPlan.Make(given, abilitiesGiven, abilitySaid);
        bool abilitiesMade = plan.Places.Count > 0 && !(r.TryGetProperty("abilitiesMade", out var madeAsked) && !madeAsked.GetBoolean());
        given = plan.Jobs(abilitiesMade);
        report["abilities"] = new Dictionary<string, object>
        {
            ["problems"] = abilityProblems, ["said"] = abilitySaid, ["made"] = abilitiesMade,
            ["given"] = abilitiesGiven.ConvertAll(g => new Dictionary<string, object> { ["key"] = g.Ability.Key, ["number"] = g.Number,
                                                                                        ["like"] = g.Ability.Like,
                                                                                        ["line"] = AbilityFile.Line(g) }),
            ["places"] = plan.Places.ConvertAll(p => new[] { p.Skillset, p.Place, p.Number }),
            ["unplaced"] = plan.Unplaced.ConvertAll(g => AbilityPlan.UnplacedLine(g.Ability)),
        };
        // (1.42.0) A job's own sprites: every place as the helper finds them; with "sprites" asked and all found, the jobs'
        // sprite numbers given as the helper gives them, the changes for longer tables at "spritesAt", the tables as they
        // start, and what is brought over after others write the game's own ("spritesWritten", as "written" for the
        // job records).
        var spriteSites = SpriteRoom.Find(image, sections);
        var offsets = new List<int>();
        for (int t = 0; t <= SpriteRoom.Tables.Length; t++)
            offsets.Add(SpriteRoom.Offset(t));
        // (1.44.0) The routines that read a texture, and the textures' file's object's pointer; (1.44.2) where another
        // mod has hooked one, taken where the program's file has it.
        string programFilePath = r.TryGetProperty("programFile", out var programFileValue)
            ? programFileValue.GetString()! : r.GetProperty("program").GetString()!;
        var programFile = ProgramFile.Of(programFilePath, image);
        var textureSites = SpriteTextures.Find(image, sections, programFile);
        report["textureSites"] = new Dictionary<string, object>
        {
            ["missing"] = textureSites.Missing, ["open"] = textureSites.Open, ["decode"] = textureSites.Decode,
            ["archive"] = textureSites.Archive, ["firstEntry"] = SpriteTextures.FirstEntry,
            ["sheetsTable"] = SpriteRoom.SheetsTable,
        };
        // (1.45.0) The places a job's own portraits change, as the helper finds them.
        var portraitSites = SpritePortraits.Find(image, sections, programFile);
        report["portraitSites"] = new Dictionary<string, object>
        {
            ["missing"] = portraitSites.Missing, ["faceMap"] = portraitSites.FaceMap, ["bounds"] = portraitSites.BoundAt,
            ["answers"] = portraitSites.AnswerAt, ["faceFile"] = portraitSites.FaceFile, ["first"] = SpritePortraits.First,
            ["cards"] = portraitSites.HudBoundAt, ["faceTest"] = portraitSites.FaceTestAt,
            ["last"] = SpritePortraits.Last, ["ownPlus"] = SpritePortraits.OwnPlus,
        };
        if (r.TryGetProperty("fileAt", out var fileAt))
        {
            var read = new List<object?>();
            foreach (var ask in fileAt.EnumerateArray())
            {
                int address = ask[0].GetInt32(), length = ask[1].GetInt32();
                var bytes = programFile?.At(address, length);
                read.Add(new object?[] { programFile?.Offset(address, length), bytes == null ? null : Hex(bytes) });
            }
            report["fileAt"] = read;
        }
        report["sprites"] = new Dictionary<string, object?>
        {
            ["missing"] = spriteSites.Missing, ["game"] = spriteSites.Game, ["readers"] = spriteSites.ReaderAt,
            ["bounds"] = spriteSites.BoundAt, ["tests"] = spriteSites.TestAt, ["pairs"] = SpriteRoom.Pairs,
            ["roomBytes"] = SpriteRoom.RoomBytes, ["offsets"] = offsets,
            // (1.53.0) The load's coloring of the figures, found apart, and the log's line where it isn't.
            ["walk"] = spriteSites.Walk, ["walkMissing"] = spriteSites.WalkMissing,
            ["walkNotLine"] = SpriteRoom.WalkNotLine(spriteSites.WalkMissing ?? "", "FFT_enhanced.exe", "Mod Studio Framework"),
        };
        bool spritesAsked = r.TryGetProperty("sprites", out var spritesValue) && spritesValue.GetBoolean() && spriteSites.Ok;
        if (spritesAsked)
        {
            var spritesSaid = new List<string>();
            report["spritesOwn"] = SpriteRoom.Plan(given, numbers, spritesSaid, image, spriteSites);
            report["spritesSaid"] = spritesSaid;
            // (1.44.0) The jobs' own textures, as SpriteTextures.Arm marks them where its hooks are made ("textures" true):
            // the entries answered (each its bytes' count and SHA-256) and the answers to the opening and unpacking asks.
            if (r.TryGetProperty("textures", out var texturesValue) && texturesValue.GetBoolean())
            {
                foreach (var g in given)
                    if (g.Sprite >= 0)
                        for (int woman = 0; woman < 2; woman++)
                            g.Textures[woman] = g.Job.Textures[woman] != null;
                var entries = SpriteTextures.Entries(given);
                var listed = new Dictionary<string, object>();
                foreach (var (entry, bytes) in entries)
                    listed[entry.ToString()] = new object[] { bytes.Length,
                                                              Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(bytes)) };
                report["textureEntries"] = listed;
                var firstLines = new Dictionary<string, string>();
                foreach (var (entry, line) in SpriteTextures.FirstLines(given))
                    firstLines[entry.ToString()] = line;
                report["textureFirstLines"] = firstLines;
                if (r.TryGetProperty("textureAsks", out var asks))
                {
                    var answers = new List<object?>();
                    foreach (var ask in asks.EnumerateArray())
                    {
                        nint archive = (nint)ask[1].GetInt64(), texturesFile = (nint)ask[2].GetInt64();
                        if (ask[0].GetString() == "open")
                            answers.Add(SpriteTextures.Opens(entries, archive, texturesFile, ask[3].GetInt32(), ask[4].GetInt32()));
                        else
                        {
                            var bytes = SpriteTextures.Unpacks(entries, archive, texturesFile, ask[3].GetInt32());
                            answers.Add(bytes == null ? null : Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(bytes)));
                        }
                    }
                    report["textureAnswers"] = answers;
                }
            }
            // (1.45.0) The jobs' own portraits, as SpritePortraitHooks.Arm marks them where its hook is made ("portraits"
            // true, every place found): the part lists named by portrait number, whose each is, and the hook's answers to
            // its asks (each a portrait's number and colors: the part list's name, or null for the game's own routine).
            if (r.TryGetProperty("portraits", out var portraitsValue) && portraitsValue.GetBoolean() && portraitSites.Ok)
            {
                spriteSites.Portraits = portraitSites;
                foreach (var g in given)
                    if (g.Sprite >= 0)
                        for (int woman = 0; woman < 2; woman++)
                            g.Portraits[woman] = g.Job.Portraits[woman] != null;
                var portraitPlan = SpritePortraits.Plan(given);
                var planned = new Dictionary<string, object>();
                foreach (var (number, names) in portraitPlan)
                    planned[number.ToString()] = names;
                report["portraitPlan"] = planned;
                var whose = new Dictionary<string, string>();
                foreach (var (number, who) in SpritePortraits.Whose(given))
                    whose[number.ToString()] = who;
                report["portraitWhose"] = whose;
                if (r.TryGetProperty("portraitAsks", out var portraitAsks))
                {
                    var answers = new List<object?>();
                    foreach (var ask in portraitAsks.EnumerateArray())
                    {
                        int number = ask[0].GetInt32(), colors = ask[1].GetInt32();
                        string? name = SpritePortraits.NameFor(portraitPlan, number, colors);
                        answers.Add(name == null ? null : new object[] { name, Hex(SpritePortraits.FileName(name)),
                                                                         SpritePortraits.FirstLine(SpritePortraits.Whose(given)[number],
                                                                                                   SpritePortraits.Which(portraitPlan[number], colors)) });
                    }
                    report["portraitAnswers"] = answers;
                }
            }
            ulong spritesAt = r.GetProperty("spritesAt").GetUInt64();
            var moved = SpriteRoom.Changes(spriteSites, r.GetProperty("base").GetUInt64(), spritesAt);
            report["spriteChanges"] = moved?.ConvertAll(c => new object[] { c.At, Hex(c.Bytes) });
            var spriteRoom = new byte[SpriteRoom.RoomBytes];
            SpriteRoom.Fill(image, spriteSites, spriteRoom, given);
            report["spriteRoom"] = Hex(spriteRoom);
            // (1.42.1) A CharShape table (its .nxd, "shapes") with the jobs' own sprites' rows, as the helper gives them.
            if (r.TryGetProperty("shapes", out var shapesFile) && shapesFile.GetString()!.Length > 0)
            {
                var shapeSaid = new List<string>();
                var shaped = SpriteRoom.WithShapeRows(File.ReadAllBytes(shapesFile.GetString()!), given, shapeSaid,
                                                      out string shapeWhy, out int shapeAdded);
                report["shapes"] = shaped == null ? null : Convert.ToBase64String(shaped);
                report["shapeSaid"] = shapeSaid;
                report["shapeWhy"] = shapeWhy;
                report["shapeAdded"] = shapeAdded;
                report["shapeLine"] = SpriteRoom.ShapeLine(shapeAdded);
            }
            // (1.43.0) A CharCLUT table (its .nxd, "cluts") with the jobs' own colors' rows, as the helper gives them.
            if (r.TryGetProperty("cluts", out var clutsFile) && clutsFile.GetString()!.Length > 0)
            {
                var clutSaid = new List<string>();
                var cluts = SpriteRoom.WithClutRows(File.ReadAllBytes(clutsFile.GetString()!), given, clutSaid,
                                                    out string clutWhy, out int clutAdded);
                report["cluts"] = cluts == null ? null : Convert.ToBase64String(cluts);
                report["clutSaid"] = clutSaid;
                report["clutWhy"] = clutWhy;
                report["clutAdded"] = clutAdded;
                report["clutLine"] = SpriteRoom.ClutLine(clutAdded);
            }
            if (r.TryGetProperty("spritesWritten", out var spritesWritten))
            {
                var game = (byte[])image.Clone();
                var seen = SpriteRoom.Seen(game, spriteSites);
                var counts = new List<int>();
                foreach (var round in spritesWritten.EnumerateArray())
                {
                    foreach (var one in round.EnumerateArray())
                    {
                        byte[] bytes = Convert.FromHexString(one[2].GetString()!);
                        var into = one[0].GetString() == "room" ? spriteRoom : game;
                        bytes.CopyTo(into, one[1].GetInt32());
                    }
                    counts.Add(SpriteRoom.Sync(game, spriteSites, seen, spriteRoom, given));
                }
                report["spriteRoomAfter"] = Hex(spriteRoom);
                report["spritesBrought"] = counts;
            }
        }
        SpriteRoom.Sites? sprites = spritesAsked ? spriteSites : null;
        // (1.46.0) A job's own icons and pictures: the four routines and the box loader as the helper finds them; with "art"
        // asked and all found, each job's parts marked as JobArtHooks.Arm marks them, the plan, the answers to its asks
        // (["picture", job, man], ["icon", number], ["command", number], ["skillset", skillset]: the key the picture
        // routine answers with, its own picture's or 0 for none, or the name written; null for the game's own answer), the
        // answers left in the picture routine's row ("ownAnswers"), the first lines, and an Icon table (its .nxd, "icons")
        // with the jobs' own pictures' rows.
        var artSites = JobArt.Find(image, sections, programFile);
        report["artSites"] = new Dictionary<string, object>
        {
            ["missing"] = artSites.Missing, ["picture"] = artSites.Picture, ["icon"] = artSites.Icon, ["boxLoad"] = artSites.BoxLoad,
            ["commandName"] = artSites.CommandName, ["commandIcon"] = artSites.CommandIcon,
            ["pictureFirst"] = JobArt.PictureFirst,
        };
        if (r.TryGetProperty("art", out var artValue) && artValue.GetBoolean() && artSites.Ok)
        {
            var artPlan = JobArt.PlanOf(given);
            foreach (var g in given)
            {
                g.IconOwn = artPlan.Icons.ContainsKey(g.Number);
                g.CommandOwn = artPlan.Commands.ContainsKey(g.Number);
                for (int woman = 0; woman < 2; woman++)
                    g.Pictures[woman] = JobArt.PictureFor(artPlan, g.Number, woman == 0) > 0;
            }
            var pictures = new Dictionary<string, object>();
            foreach (var (job, keys) in artPlan.Pictures)
                pictures[job.ToString()] = keys;
            report["artPlan"] = new Dictionary<string, object>
            {
                ["icons"] = Keyed(artPlan.Icons), ["commands"] = Keyed(artPlan.Commands),
                ["commandsBySkillset"] = Keyed(artPlan.CommandsBySkillset), ["pictures"] = pictures,
            };
            if (r.TryGetProperty("artAsks", out var artAsks))
            {
                var answers = new List<object?>();
                foreach (var ask in artAsks.EnumerateArray())
                {
                    string kind = ask[0].GetString()!;
                    int n = ask[1].GetInt32();
                    if (kind == "picture")
                        answers.Add(JobArt.PictureFor(artPlan, n, ask[2].GetBoolean()));
                    else
                    {
                        var by = kind == "icon" ? artPlan.Icons : kind == "command" ? artPlan.Commands : artPlan.CommandsBySkillset;
                        answers.Add(by.TryGetValue(n, out var name)
                            ? Hex(kind == "icon" ? JobArt.IconName(name) : JobArt.CommandName(name)) : null);
                    }
                }
                report["artAnswers"] = answers;
            }
            if (r.TryGetProperty("ownAnswers", out var ownAsks))
            {
                // What the picture routine's row holds after the framework's answer: the game's answer (its key and flag),
                // the framework's key and the routine's flag kind, each then as the hook leaves it.
                var left = new List<string>();
                foreach (var ask in ownAsks.EnumerateArray())
                {
                    var answer = Convert.FromHexString(ask[0].GetString()!);
                    JobArt.Answer(answer, ask[1].GetInt32(), ask[2].GetBoolean());
                    left.Add(Hex(answer));
                }
                report["ownAnswers"] = left;
            }
            // The first lines as the hooks say them (JobArtHooks.First), for the first job given.
            var firstLines = new List<string>();
            foreach (var what in new[] { "icon", "skillset icon", "man's picture", "woman's picture" })
                firstLines.Add(JobArt.FirstLine(what, given.Count > 0 ? given[0].Job.Who : ""));
            report["artFirstLines"] = firstLines;
            report["artNotLine"] = JobArt.NotLine("a call of the picture routine (0 places like it, not 1) wasn't found in "
                                                  + "FFT_enhanced.exe. A game update may have changed it: look for a newer "
                                                  + "Mod Studio Framework");
            if (r.TryGetProperty("icons", out var iconsFile) && iconsFile.GetString()!.Length > 0)
            {
                var iconSaid = new List<string>();
                var icons = JobArt.WithPictureRows(File.ReadAllBytes(iconsFile.GetString()!), given, iconSaid, out string iconWhy,
                                                   out int iconAdded);
                report["icons"] = icons == null ? null : Convert.ToBase64String(icons);
                report["iconSaid"] = iconSaid;
                report["iconWhy"] = iconWhy;
                report["iconAdded"] = iconAdded;
                report["iconLine"] = JobArt.PictureRowsLine(iconAdded);
            }
        }
        if (more)
        {
            ulong tableAt = r.GetProperty("at").GetUInt64() + JobRoom.CellsAfter + JobRoom.CellsRoom;
            var named = JobRecords.Changes(records!, r.GetProperty("base").GetUInt64(), tableAt);
            report["tableAt"] = tableAt;
            report["recordChanges"] = named?.ConvertAll(c => new object[] { c.At, Hex(c.Bytes) });
            report["recordsLine"] = JobRecords.Line(given.FindAll(g => g.Number >= JobRecords.GameCount).Count);
            // The table as it starts, what is brought over after others write the game's own, and what stays.
            if (r.TryGetProperty("written", out var written))
            {
                int gameBytes = JobRecords.GameCount * JobRecords.RecordBytes;
                var game = new ReadOnlySpan<byte>(image, found.Records, gameBytes).ToArray();
                var table = new byte[JobRecords.Bytes];
                JobRecords.Fill(game, table);
                var seen = (byte[])game.Clone();
                var started = Hex(table);
                var counts = new List<int>();
                foreach (var round in written.EnumerateArray())
                {
                    foreach (var one in round.EnumerateArray())
                    {
                        byte[] bytes = Convert.FromHexString(one[2].GetString()!);
                        var into = one[0].GetString() == "table" ? table : game;
                        bytes.CopyTo(into, one[1].GetInt32());
                    }
                    counts.Add(JobRecords.Sync(game, seen, table));
                }
                report["tableStarted"] = started;
                report["tableAfter"] = Hex(table);
                report["brought"] = counts;
            }
        }
        report["given"] = given.ConvertAll(g => new Dictionary<string, object> { ["key"] = g.Job.Key, ["number"] = g.Number,
                                                                                 ["like"] = g.Job.Like,
                                                                                 ["skillset"] = g.Skillset,
                                                                                 ["record"] = Hex(g.Job.Record),
                                                                                 ["skillsetRecord"] = Hex(JobRoom.SkillsetRecord(g.Job)),
                                                                                 ["lookLike"] = g.Job.LookLike,
                                                                                 ["colors"] = g.Job.Colors,
                                                                                 ["textures"] = g.Textures,
                                                                                 ["portraits"] = g.Portraits,
                                                                                 ["frames"] = g.Job.Frames,
                                                                                 ["portraitNames"] = g.Job.Portraits,
                                                                                 ["textureBytes"] = Array.ConvertAll(g.Job.Textures,
                                                                                     t => t == null ? null : Array.ConvertAll(t, h => h.Length)),
                                                                                 ["art"] = new Dictionary<string, object?>
                                                                                 {
                                                                                     ["iconJob"] = g.Job.Art.IconJob, ["iconOwn"] = g.Job.Art.IconOwn,
                                                                                     ["commandSkillset"] = g.Job.Art.CommandSkillset,
                                                                                     ["commandOwn"] = g.Job.Art.CommandOwn,
                                                                                     ["pictureOwn"] = g.Job.Art.PictureOwn,
                                                                                     ["iconMarked"] = g.IconOwn, ["commandMarked"] = g.CommandOwn,
                                                                                     ["picturesMarked"] = g.Pictures,
                                                                                 },
                                                                                 ["sprite"] = g.Sprite, ["drawn"] = g.Drawn,
                                                                                 ["atlas"] = g.Atlas,
                                                                                 ["game"] = g.Job.Game,
                                                                                 ["abilityNames"] = Array.ConvertAll(g.Job.AbilityNames,
                                                                                     n => new object[] { n.Ability, n.Name, n.Description }),
                                                                                 ["skillsetWords"] = new[] { g.Job.SkillsetName, g.Job.SkillsetDescription },
                                                                                 ["line"] = JobRoom.Line(g) });
        if (file.Length > 0)
            File.WriteAllText(file, numbers.Text());
        report["kept"] = numbers.Used(Numbers.JobsKind);
        report["keptSkillsets"] = numbers.Used(Numbers.SkillsetsKind);
        report["keptAbilities"] = numbers.GivenOf(Numbers.AbilitiesKind);
        report["keptSprites"] = numbers.GivenOf(Numbers.SpritesKind);
        if (given.Count > 0 && found.Ok)
        {
            var code = JobRoom.Code(image, found, r.GetProperty("base").GetUInt64(), r.GetProperty("at").GetUInt64(), given,
                                    out var changes, sprites: sprites, special: codeSites);
            report["code"] = Hex(code);
            report["changes"] = changes.ConvertAll(c => new object[] { c.At, Hex(c.Bytes) });
        }
        // (1.41.3, his test 96) Arithmeticks's list: where it is, the log's line, and the native code with it (no screen).
        int arithmeticks = JobRoom.FindArithmeticks(image, sections, out string? noArithmeticks);
        report["arithmeticks"] = arithmeticks;
        report["arithmeticksLine"] = JobRoom.ArithmeticksLine(noArithmeticks, Path.GetFileName(r.GetProperty("program").GetString()!),
                                                              "Mod Studio Framework");
        // (1.41.4) The units' two choices: where they are, the log's line, and the native code with them too.
        var (think, random) = JobRoom.FindArithmeticksUnits(image, sections, out string? noUnits);
        report["arithmeticksUnits"] = new[] { think, random };
        report["arithmeticksUnitsLine"] = JobRoom.ArithmeticksUnitsLine(noUnits, Path.GetFileName(r.GetProperty("program").GetString()!),
                                                                        "Mod Studio Framework");
        if (given.Count > 0 && found.Ok && arithmeticks >= 0)
        {
            var code = JobRoom.Code(image, found, r.GetProperty("base").GetUInt64(), r.GetProperty("at").GetUInt64(), given,
                                    out var changes, null, arithmeticks, think, random, sprites);
            report["arithmeticksCode"] = Hex(code);
            report["arithmeticksChanges"] = changes.ConvertAll(c => new object[] { c.At, Hex(c.Bytes) });
        }
        // (1.53.0) A unit of a battle's file in a mod's job: its two places and the job's learning the loop calls, the log's
        // line, and the native code with them (no screen).
        var battleUnits = JobRoom.FindBattleUnits(image, sections, out string? noBattle);
        report["battleUnits"] = new[] { battleUnits.Own, battleUnits.Row, battleUnits.Learn };
        report["battleUnitsMissing"] = noBattle;
        report["battleUnitsLine"] = JobRoom.BattleUnitsLine(noBattle, Path.GetFileName(r.GetProperty("program").GetString()!),
                                                            "Mod Studio Framework");
        if (given.Count > 0 && found.Ok && noBattle == null)
        {
            var code = JobRoom.Code(image, found, r.GetProperty("base").GetUInt64(), r.GetProperty("at").GetUInt64(), given,
                                    out var changes, sprites: sprites, battleOwn: battleUnits.Own, battleRow: battleUnits.Row,
                                    battleLearn: battleUnits.Learn);
            report["battleCode"] = Hex(code);
            report["battleChanges"] = changes.ConvertAll(c => new object[] { c.At, Hex(c.Bytes) });
        }
        // (1.39.0) The job screen's own rows: its places in the program, and the native code with them.
        if (found.Ok)
        {
            var screen = JobRoom.FindScreen(image, sections, found);
            report["screenMissing"] = screen.Missing;
            report["screenAt"] = screen.At;
            report["screen"] = new Dictionary<string, int>
            {
                ["fill"] = screen.Fill, ["root"] = screen.Root, ["list"] = screen.ListAt, ["count"] = screen.Count,
                ["lister"] = screen.Lister, ["step"] = screen.Step, ["upDown"] = screen.UpDown, ["place"] = screen.Place,
                ["refresh"] = screen.Refresh, ["treeJob"] = screen.TreeJob,
                ["ending"] = screen.Ending, ["cycleStep"] = screen.CycleStep,
                ["window"] = screen.Window, ["secondWhole"] = screen.SecondWhole,
            };
            // (1.49.0) Job Progress's places for the mods' jobs' boxes (JobTree.Find), and the log's lines.
            var tree = JobTree.Find(image, sections, screen.TreeJob);
            report["treeMissing"] = tree.Missing;
            report["tree"] = new Dictionary<string, int>
            {
                ["update"] = tree.Update, ["shown"] = tree.Shown, ["release"] = tree.Release, ["pressed"] = tree.Pressed,
                ["focus"] = tree.Focus, ["keeper"] = tree.Keeper, ["sprites"] = tree.Sprites, ["clear"] = tree.Clear,
                ["free"] = tree.Free, ["finish"] = tree.Finish, ["figure"] = tree.Figure, ["write"] = tree.Write,
                ["setter"] = tree.Setter, ["bind"] = tree.Bind,
            };
            // (1.50.0) What the lines and the small icons need more than the boxes: the tree's play of a line's look
            // and of a label's, and the layouts' sizing of a box (Places).
            report["treeLines"] = new Dictionary<string, int>
            {
                ["linePlay"] = tree.LinePlay, ["labelPlay"] = tree.LabelPlay, ["size"] = Places.Find(image).BoxSize,
            };
            report["treeLinesMissing"] = tree.LinesMissing;
            report["treeLinesNotFound"] = JobTree.LinesNotLine(JobTree.LinesNotFound(tree.LinesMissing));
            report["treeLine"] = JobTree.Line(given.Count);
            report["treeNotLine"] = JobTree.NotFoundLine(tree.Missing, Path.GetFileName(r.GetProperty("program").GetString()!),
                                                         "Mod Studio Framework");
            if (given.Count > 0 && screen.Ok)
            {
                var code = JobRoom.Code(image, found, r.GetProperty("base").GetUInt64(), r.GetProperty("at").GetUInt64(), given,
                                        out var changes, screen, sprites: sprites);
                report["screenCode"] = Hex(code);
                report["screenChanges"] = changes.ConvertAll(c => new object[] { c.At, Hex(c.Bytes) });
                report["screenLine"] = JobScreen.Line(given.Count);
            }
        }
        string tableFile = r.GetProperty("table").GetString()!;
        if (tableFile.Length > 0)
        {
            var words = new List<string>();
            var table = JobRoom.WithJobRows(File.ReadAllBytes(tableFile), given, words, out string why);
            report["tableWords"] = words;
            report["tableWhy"] = why;
            report["table"] = table == null ? null : Convert.ToBase64String(table);
        }
        // (1.47.0) The jobs' words on Job Summary, in a job help table (UiJobAbilityHelp): the table with their rows, what
        // is said, each given job's key and words, the heading found, and the lines.
        if (r.TryGetProperty("helps", out var helpsFile) && helpsFile.GetString()!.Length > 0)
        {
            var helpSaid = new List<string>();
            byte[] loadedHelps = File.ReadAllBytes(helpsFile.GetString()!);
            var helps = JobWords.WithHelpRows(loadedHelps, given, helpSaid, out string helpWhy, out int helpAdded);
            report["helps"] = helps == null ? null : Convert.ToBase64String(helps);
            report["helpSaid"] = helpSaid;
            report["helpWhy"] = helpWhy;
            report["helpAdded"] = helpAdded;
            report["helpLine"] = JobWords.HelpRowsLine(helpAdded);
            report["helpNoRows"] = JobWords.NoRowsLine(helpWhy);
            string helpHeading = Nxd.Keys(loadedHelps) == 1 ? JobWords.Heading(loadedHelps) : "";
            report["helpHeading"] = helpHeading;
            report["helpKeys"] = given.ConvertAll(g => JobWords.HelpKey(g.Number));
            report["helpTexts"] = given.ConvertAll(g => JobWords.TextOf(g.Job, helpHeading));
            report["helpSummaries"] = given.ConvertAll(g => g.Job.Summary);
            // (1.55.1) The game's Onion Knight's words for its level 8, as its second row holds them (null: none).
            report["helpMastered"] = given.ConvertAll(g => g.Job.MasteredWords ? JobWords.MasteredTextOf(g.Job, helpHeading)
                                                                                : null);
            report["helpPlaces"] = new[] { JobWords.HelpSheet, JobWords.JobHelpAt, JobWords.HelpTextAt, JobWords.HelpFirst };
        }
        // (1.48.0) What opens a job: each given job's needs as its file has them and as the plan finds them, what is
        // said, the lines; with "general" (a GeneralJob table's file) the table with the jobs' rows, the JP a level
        // needs and what each row needs as read back; with "opens" (units: a menu's record's bytes and the unit's level
        // in each job given) whether each job is open to each unit and its mark with those units the party; with
        // "named" ([job, woman] pairs, over the Job table with the jobs' rows) each job's name and icon and a place's
        // record made of it; with "known" what each job number is known by.
        {
            var needSaid = new List<string>();
            var needsPlan = JobNeeds.Plan.Make(given, needSaid);
            report["needs"] = given.ConvertAll(g => Array.ConvertAll(g.Job.Needs, n => new object?[] { n.Job, n.Own, n.Level }));
            // (1.55.2) Which needs each file asks mastered.
            report["needsAskedMastered"] = given.ConvertAll(g => Array.ConvertAll(g.Job.Needs, n => n.Mastered));
            report["needsPlan"] = Array.ConvertAll(needsPlan.Needs, list => Array.ConvertAll(list, n => new[] { n.Known, n.Level, n.Own }));
            // (1.55.0) The game's Dark Knight and Onion Knight: which needs are of a job mastered, of a game job given, and
            // each job's slot where it is one of those.
            report["needsMastered"] = Array.ConvertAll(needsPlan.Needs, list => Array.ConvertAll(list, n => n.Mastered));
            report["needsGame"] = Array.ConvertAll(needsPlan.Needs, list => Array.ConvertAll(list, n => n.Game));
            report["needsGameSlots"] = needsPlan.GameSlots;
            // Which places of the game's jobs' skillsets hold an ability, as the helper reads them for a need of a job
            // mastered (JobNeeds.PlacesOf over the program's job records and skillsets).
            if (found.Ok)
                needsPlan.Places = JobNeeds.PlacesOf(image, found.Records, found.Skillsets);
            report["needsPlaces24"] = Array.ConvertAll(needsPlan.Places, p => p == null ? null : new List<bool>(p));
            // (1.56.0) Which places of each job given's own skillset hold an ability, for a need of it mastered.
            report["needsOwnPlaces"] = Array.ConvertAll(needsPlan.OwnPlaces, p => new List<bool>(p));
            // (1.56.0) A job's learned row out of its eight bytes as they are kept (bytes 5 to 7: 0xF0, 0x0F, 0x81).
            report["needsRowOf"] = JobProgress.RowOf(0xF0UL << 40 | 0x0FUL << 48 | 0x81UL << 56 | 0x1234_5678UL);
            report["needsNever"] = needsPlan.Never;
            report["needsAny"] = needsPlan.Any;
            report["needsSaid"] = needSaid;
            int needing = 0;
            for (int k = 0; k < given.Count; k++)
                if (needsPlan.Needs[k].Length > 0 || needsPlan.Never[k])
                    needing++;
            report["needsLine"] = JobNeeds.Line(needing, given.Count);
            report["needsNotAsked"] = JobNeeds.NotAskedLine;
            report["needsPlaces"] = new[] { JobNeeds.Sheet, JobNeeds.OwnFirst, JobNeeds.Locked, JobNeeds.Unseen, JobNeeds.RowBytes,
                                            JobFile.MostNeeds, JobFile.LeastNeedLevel, JobFile.MostNeedLevel };
            var modNumbers = new short[given.Count];
            for (int k = 0; k < given.Count; k++)
                modNumbers[k] = (short)given[k].Number;
            if (r.TryGetProperty("general", out var generalFile) && generalFile.GetString()!.Length > 0)
            {
                byte[] loadedGeneral = File.ReadAllBytes(generalFile.GetString()!);
                var generalSaid = new List<string>();
                var general = JobNeeds.WithRows(loadedGeneral, given, needsPlan, generalSaid, out string generalWhy, out int generalAdded);
                report["general"] = general == null ? null : Convert.ToBase64String(general);
                report["generalSaid"] = generalSaid;
                report["generalWhy"] = generalWhy;
                report["generalAdded"] = generalAdded;
                report["generalLine"] = JobNeeds.RowsLine(generalAdded);
                report["generalNoRows"] = JobNeeds.NoRowsLine(generalWhy);
                report["generalExp"] = Nxd.Keys(loadedGeneral) == 1 ? JobNeeds.Exp(loadedGeneral) : null;
                if (general != null)
                {
                    var read = new Dictionary<string, object?>();
                    var keys = new List<int>();
                    for (int key = 0; key < 22; key++)
                        keys.Add(key);
                    foreach (var g in given)
                        keys.Add(JobNeeds.Identity(g.Number));
                    foreach (int key in keys)
                    {
                        var rowNeeds = JobNeeds.RowNeeds(general, key);
                        read[key.ToString()] = rowNeeds == null ? null : Array.ConvertAll(rowNeeds, n => new[] { n.Known, n.Level });
                    }
                    report["generalNeeds"] = read;
                }
            }
            if (r.TryGetProperty("opens", out var opens))
            {
                // (1.56.0) "rows": the unit's learned row in each job given (its three bytes as one number, the first
                // place the highest bit), for a need of a job given mastered.
                var units = new List<(byte[] Record, int[] Levels, int[] Rows)>();
                foreach (var unit in opens.EnumerateArray())
                {
                    var levels = new List<int>();
                    foreach (var level in unit.GetProperty("levels").EnumerateArray())
                        levels.Add(level.GetInt32());
                    var learned = new List<int>();
                    if (unit.TryGetProperty("rows", out var rowsValue))
                        foreach (var value in rowsValue.EnumerateArray())
                            learned.Add(value.GetInt32());
                    units.Add((Convert.FromHexString(unit.GetProperty("record").GetString()!), levels.ToArray(), learned.ToArray()));
                }
                var opened = new List<bool[]>();
                foreach (var (unitRecord, levels, learned) in units)
                {
                    var row = new bool[given.Count];
                    for (int k = 0; k < given.Count; k++)
                        row[k] = needsPlan.Open(k, unitRecord, job => job >= 0 && job < levels.Length ? levels[job] : 0,
                                                job => job >= 0 && job < learned.Length
                                                       && JobNeeds.OwnMastered(learned[job], needsPlan.OwnPlaces[job]));
                    opened.Add(row);
                }
                report["opens"] = opened;
                report["marks"] = opened.ConvertAll(mine =>
                {
                    var marks = new int[given.Count];
                    for (int k = 0; k < given.Count; k++)
                        marks[k] = JobNeeds.Plan.Mark(mine[k], opened.Exists(o => o[k]));
                    return marks;
                });
            }
            if (r.TryGetProperty("named", out var named) && tableFile.Length > 0)
            {
                var jobTable = JobRoom.WithJobRows(File.ReadAllBytes(tableFile), given, new List<string>(), out _);
                var names = new List<object?>();
                if (jobTable != null)
                    foreach (var pair in named.EnumerateArray())
                    {
                        var one = JobNeeds.Named(jobTable, pair[0].GetInt32(), pair[1].GetBoolean());
                        if (one == null)
                        {
                            names.Add(null);
                            continue;
                        }
                        var stood = new byte[JobNeeds.PlaceBytes + 8];
                        Array.Fill(stood, (byte)0xEE);
                        JobNeeds.Stand(stood, one.Value.Name, one.Value.Icon, 5, pair[0].GetInt32(), 1);
                        names.Add(new object[] { one.Value.Name, one.Value.Icon, Hex(stood) });
                    }
                report["named"] = names;
                var longName = new byte[JobNeeds.PlaceBytes];
                JobNeeds.Stand(longName, new string('é', 40), 7, 3, 99, 2);
                report["standLong"] = Hex(longName);
            }
            if (r.TryGetProperty("known", out var knownJobs))
            {
                var knowns = new List<int[]>();
                foreach (var n in knownJobs.EnumerateArray())
                    knowns.Add(new[] { JobNeeds.Known(n.GetInt32(), modNumbers), JobNeeds.JobOf(JobNeeds.Known(n.GetInt32(), modNumbers)) });
                report["known"] = knowns;
            }
        }
        // (1.55.0) The names a job's file gives the game's own abilities of its skillset that have none, in an Ability table
        // (its .nxd, "abilityTable").
        if (r.TryGetProperty("abilityTable", out var abilityTableFile) && abilityTableFile.GetString()!.Length > 0)
        {
            var nameSaid = new List<string>();
            // (1.55.0) "sanguine": whether 45 was made War of the Lions' Sanguine Sword (its row made then); so unless said.
            bool sanguineMade = !r.TryGetProperty("sanguine", out var sanguineAsked) || sanguineAsked.GetBoolean();
            var named = AbilityWords.WithGameNames(File.ReadAllBytes(abilityTableFile.GetString()!), given, sanguineMade, nameSaid,
                                                   out string nameWhy, out int nameCount);
            report["abilityNamed"] = named == null ? null : Convert.ToBase64String(named);
            report["abilityNameSaid"] = nameSaid;
            report["abilityNameWhy"] = nameWhy;
            report["abilityNameCount"] = nameCount;
            report["abilityNameLine"] = AbilityWords.GameNamesLine(nameCount);
        }
        // (1.55.1) The window of what a job needs saying "Mastered" for a job needed mastered, in a UI table (its .nxd,
        // "uiTable"): the table with its two level texts made, what is said, the lines.
        if (r.TryGetProperty("uiTable", out var uiTableFile) && uiTableFile.GetString()!.Length > 0)
        {
            var uiSaid = new List<string>();
            var ui = JobNeeds.WithMasteredWords(File.ReadAllBytes(uiTableFile.GetString()!), uiSaid, out string uiWhy,
                                                out int uiWritten);
            report["ui"] = ui == null ? null : Convert.ToBase64String(ui);
            report["uiSaid"] = uiSaid;
            report["uiWhy"] = uiWhy;
            report["uiWritten"] = uiWritten;
            report["uiLine"] = JobNeeds.MasteredLine(uiWritten);
            report["uiNoLine"] = JobNeeds.NoMasteredLine(uiWhy);
        }
        // (1.55.0) The game's Dark Knight's first ability as War of the Lions has it (DarkKnightAbilities): its places, found
        // in the program as it is; the changes in it (with "darkPoke" bytes put in first, from the program's start: as
        // another mod, or the game's first use of the action records, would have them), what is kept, the log's lines.
        if (given.Exists(g => g.Job.Game == JobFile.DarkKnight))
        {
            var darkSites = DarkKnightAbilities.Find(image, sections, found.Skillsets);
            report["dark"] = new Dictionary<string, object?>
            {
                ["records"] = darkSites.Records, ["effects"] = darkSites.Effects, ["animations"] = darkSites.Animations,
                ["actionSource"] = darkSites.ActionSource, ["actions"] = darkSites.Actions, ["actionsMade"] = darkSites.ActionsMade,
                ["skillsets"] = darkSites.Skillsets, ["missing"] = darkSites.Missing,
            };
            var darkImage = (byte[])image.Clone();
            if (r.TryGetProperty("darkPoke", out var darkPoke))
                foreach (var poke in darkPoke.EnumerateArray())
                    Convert.FromHexString(poke[1].GetString()!).CopyTo(darkImage, poke[0].GetInt32());
            var darkKept = new List<string>();
            var darkChanges = DarkKnightAbilities.Changes(darkImage, darkSites, darkKept, out bool darkSanguine);
            report["darkChanges"] = darkChanges.ConvertAll(c => new object[] { c.At, Hex(c.Bytes) });
            report["darkKept"] = darkKept;
            report["darkSanguine"] = darkSanguine;
            report["darkLine"] = DarkKnightAbilities.Line(darkSanguine, darkKept);
            report["darkNotLine"] = DarkKnightAbilities.NotLine(darkSites.Missing.Count > 0 ? darkSites.Missing : new List<string> { "this", "that" },
                                                                Path.GetFileName(r.GetProperty("program").GetString()!), "Mod Studio Framework");
        }
        // (1.37.0) The skillsets' names, in a JobCommand table.
        if (r.TryGetProperty("commands", out var commandsFile) && commandsFile.GetString()!.Length > 0)
        {
            var words = new List<string>();
            var table = JobRoom.WithCommandRows(File.ReadAllBytes(commandsFile.GetString()!), given, words, out string why);
            report["commandWords"] = words;
            report["commandWhy"] = why;
            report["commandLine"] = JobRoom.CommandLine(given.FindAll(g => g.Skillset != 0).Count);
            report["commands"] = table == null ? null : Convert.ToBase64String(table);
        }
        string roster = r.GetProperty("roster").GetString()!;
        if (roster.Length > 0)
        {
            var bytes = Convert.FromHexString(roster);
            var kept = new List<int>();
            foreach (var n in r.GetProperty("given").EnumerateArray())
                kept.Add(n.GetInt32());
            var keptSkillsets = new List<int>();
            if (r.TryGetProperty("givenSkillsets", out var sets))
                foreach (var n in sets.EnumerateArray())
                    keptSkillsets.Add(n.GetInt32());
            // (1.55.0) "gameJobs": the game's Dark Knight and Onion Knight the framework's to settle.
            bool gameJobs = r.TryGetProperty("gameJobs", out var gameJobsValue) && gameJobsValue.GetBoolean();
            report["settled"] = JobRoom.Settle(bytes, kept, JobRoom.Gone(numbers, keptSkillsets), gameJobs);
            report["roster"] = Hex(bytes);
        }
        // The other mod's list, as it keeps it and when it isn't as this was made for.
        var startup = new TheirStartup();
        report["theirStop"] = JobRoom.OnTheirPage(startup, new[] { 142, 160 });
        report["theirList"] = Array.ConvertAll(startup.Mod.List, n => (int)n);
        report["theirOther"] = JobRoom.OnTheirPage(new NotTheirs(), new[] { 142 });
        File.WriteAllText(args[2], JsonSerializer.Serialize(report));
        return 0;
    }

    // (1.39.0) The job screen's own rows (JobScreen.cs) run over a screen made up as the game lays one out: the
    // game's interface, its unit screens' holder, a job screen of 19 places with a box each, the list the game's
    // lister fills and the menu's table of records. dev/test_jobs.py says what each step must leave.
    //
    //     dotnet Checks.dll --screen <request.json> <report.json>
    //
    // The request: {"mods": [job numbers], "steps": [...]}. A step is one of
    //   {"do": "screen", "offset": [dx, dy], "sliding": n, "ended": b}   a screen just made, where the last was
    //       and with its boxes where the last one's were: its boxes where the layout rests them, moved by the offset;
    //       with "sliding", the boxes after the first n pixels short of their place. The screen before it has ended
    //       first, as the native code tells the layouts' move ("ended": false: not told)
    //   {"do": "list", "unit": n, "job": j, "jobs": [...], "state": s, "one": b}   the game's filling for that unit
    //       (the screen in state s, 2 when not said): its lister's answer, then Listed, then what the game's filling
    //       does with the count ("one": made 1, as for a unit whose job's row hides the job tree) and the cursor;
    //       then After, as the game's call of the filling is followed by ("after": false: a filling After isn't
    //       told of)
    //   {"do": "step", "row": r, "delta": d, "fresh": b, "cursor": c, "hover": h, "min": 0, "max": 2}   the cursor's
    //       step between rows asked; the game's filling, when called, fills for the last unit again
    //   {"do": "idle", "times": n}   the cursor's step asked n times with nothing pressed (the cursor in the first
    //       row). "took": the first of the n at which the game's filling was called (0: none)
    //   {"do": "abilities"}   the game goes to the abilities' page: state 9, the piece that goes from job to job given
    //       the open places of all 19, as the game builds them
    //   {"do": "cycle", "way": 1 or 2, "fresh": b, "elsewhere": b}   Q (1) or E (2) there: Cycle asked in place of
    //       the game's step (stood in for with what it does), the cursor put where it answers. "cycle", "on": the
    //       piece's places and which it is on; "job": the job at the cursor's place in the list; "says": which way
    //   {"do": "back"}   back to the jobs: state 2
    //   {"do": "animate", "by": [dx, dy], "boxes": [[place, x, y]]}   the game's own animation of the places, through
    //       the layouts' move of a box as the native code changes it: every box put where the layout rests it (the
    //       screen's offset with it) and "by" from there, or the boxes named put where said
    //   {"do": "use", "on": b}, {"do": "gone"}   the holder in use or not, no screen
    // The game's filling as it is stood in for: in a state of 2 or less it forgets the cursor's place, and puts the
    // cursor on the place whose job is the unit's own, if the list has it (0x12EA68, 0x12EC5C). The job tree is always
    // there and is given every job listed by its number in the list, through TreePlace: "tree" is what it holds after
    // (20 places, 0 where it was never given one; a place it was given keeps what it was last given).
    // Each step's report: what it answered and the screen after it.
    /// <summary>Where the layout rests the places' boxes (ffto_jobchange_ver03.uib, UnitPosition's HomePosition and
    /// ShowUnit: Unit01 to Unit19), and a box's place in its layer: the made up screen's, for showing that the framework
    /// leaves every box where the game puts it.</summary>
    static readonly (int X, int Y)[] LayoutRest =
    {
        (254, 12), (524, 12), (794, 12), (1064, 12), (1334, 12), (1604, 12),
        (118, 214), (388, 214), (658, 214), (928, 214), (1198, 214), (1468, 214), (1738, 214),
        (254, 416), (524, 416), (794, 416), (1064, 416), (1334, 416), (1604, 416),
    };
    const int BoxX = 0x38, BoxY = 0x3C;

    public static unsafe int RunScreen(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var r = request.RootElement;
        var mods = new List<int>();
        foreach (var n in r.GetProperty("mods").EnumerateArray())
            mods.Add(n.GetInt32());
        const int ScreenBytes = 0x5000, BoxBytes = 0x100, Records = 64, RecordBytes = 0x280, ListWords = 64;
        byte* Block(int bytes) => (byte*)System.Runtime.InteropServices.NativeMemory.AllocZeroed((nuint)bytes);
        nint* root = (nint*)Block(8);
        byte* face = Block(0x100), holders = Block(0x100), holder = Block(0x100), screen = Block(ScreenBytes);
        byte* boxes = Block(JobScreen.Places * BoxBytes), records = Block(Records * RecordBytes);
        short* list = (short*)Block(2 * ListWords);
        short* index = (short*)Block(8);
        byte** table = (byte**)Block(8 * Records);
        *root = (nint)face;
        *(nint*)(face + JobScreen.RootHolders) = (nint)holders;
        *(nint*)(holders + JobScreen.HoldersUnits) = (nint)holder;
        for (int k = 0; k < Records; k++)
            table[k] = records + k * RecordBytes;
        short* gameCount = (short*)Block(8);
        int* sides = (int*)Block(16);
        int* alive = (int*)Block(8);
        // (1.49.0) The number the native code reads while the filling is run for the mods' jobs alone, and the job tree
        // the holder holds; with "harvest" the framework is told of each record so handed on (the job's place among the
        // mods' jobs, the job and whether it is closed as the record says, whether the tree is the holder's).
        int* harvesting = (int*)Block(8);
        // (2.0.5) The number the native code reads before each place is given its job: not 0 while place 0 holds another
        // job than the unit's first, which then gets palette 0 as every other place (his report of 18 November).
        int* palette = (int*)Block(8);
        byte* treeBlock = Block(16);
        var harvested = new List<int[]>();
        var rows = new JobScreen(mods, root, list, index, table, Records, gameCount, sides, alive, harvesting, palette);
        bool inUse = true;
        rows.InUse = _ => inUse;
        var calls = new List<string>();
        int[] gameJobs = Array.Empty<int>();
        int delta = 0, upDowns = 0;
        bool fresh = true;
        (int, int) handed = (0, 0);
        rows.UpDown = (out int d, out bool f, int pad, int other) =>
        {
            d = delta;
            f = fresh;
            handed = (pad, other);
            upDowns++;
            return delta != 0;
        };
        int GameLists()
        {
            for (int k = 0; k < ListWords; k++)
                list[k] = 0x7777;
            for (int k = 0; k < gameJobs.Length; k++)
                list[k] = (short)gameJobs[k];
            list[gameJobs.Length] = -1;
            return gameJobs.Length;
        }
        int filled = 0, unitJob = 0, marked = -1;
        bool one = false;
        // (1.48.0) The marks of the mods' jobs for the unit, as the framework's asker answers them.
        int[] marks = Array.Empty<int>();
        rows.Mark = k => k >= 0 && k < marks.Length ? marks[k] : 0;
        int[] tree = new int[20];
        // (1.49.1) The unit's job as each of the tree's places was last given a job: whose the place's record is.
        int[] treeFor = new int[20];
        int restX = 0, restY = 0;
        Action<nint, int, int> gameMoves = (_, _, _) => { };
        // The game's filling of the screen: its readying of the places (0x12EA68: for every unit but a monster the
        // layout's ShowUnit set at once, which puts the first place's box where it rests, by the layouts' move, and
        // makes all 19 seen), its lister, then the cursor (in a state of 2 or less) and each job listed given to the
        // tree's place the framework answers for its number.
        int GameFills()
        {
            bool there = *(nint*)(holder + JobScreen.HolderScreen) != 0 && inUse;
            // (1.49.0) While the number says so the native code leaves out the filling's readying of the screen and its
            // giving of a job to the screen's place: the lister and the tree's giving alone are left.
            bool alone = *harvesting != 0;
            if (alone)
            {
                int listed = rows.Listed(GameLists());
                if (one)
                    listed = 1;
                *gameCount = (short)listed;
                byte* made = stackalloc byte[JobScreen.RecordBytes];
                for (int k = 0; k < listed && k < JobScreen.Places && there; k++)
                {
                    new Span<byte>(made, JobScreen.RecordBytes).Clear();
                    *(int*)(made + JobScreen.RecordJobAt) = list[k] & JobScreen.JobBits;
                    *(int*)(made + JobScreen.RecordClosed) = (list[k] & 0x2000) != 0 ? 2 : (list[k] & 0x4000) != 0 ? 1 : 0;
                    int place = rows.TreePlace(k, (nint)made, (nint)treeBlock);
                    if (place >= 0 && place < tree.Length)
                    {
                        tree[place] = list[k] & JobScreen.JobBits;
                        treeFor[place] = unitJob;
                    }
                }
                return listed;
            }
            if (there)
            {
                gameMoves((nint)boxes, LayoutRest[0].X + restX, LayoutRest[0].Y + restY);
                for (int k = 0; k < JobScreen.Places; k++)
                    *(float*)(boxes + k * BoxBytes + JobScreen.BoxOpacity) = 1f;
            }
            bool cursors = there && *(int*)(screen + JobScreen.State) <= JobScreen.LastCursorState;
            if (cursors)
                *(int*)(screen + JobScreen.Cursor) = -1;
            int count = rows.Listed(GameLists());
            // The game keeps the count, and makes it 1 for a unit whose job's row hides the job tree ("one").
            if (one)
                count = 1;
            *gameCount = (short)count;
            // As it gives each place its job the filling marks the place the cursor is on then (0x132E1C).
            if (there)
                marked = *(int*)(screen + JobScreen.Cursor);
            for (int k = 0; k < count && k < JobScreen.Places; k++)
            {
                int job = list[k] & JobScreen.JobBits;
                // The place's record, as the filling writes it from the list: not to be seen (0x2000), locked
                // (0x4000) or open.
                if (there)
                {
                    *(int*)(screen + JobScreen.Records + k * JobScreen.RecordBytes + JobScreen.RecordClosed) =
                        (list[k] & 0x2000) != 0 ? 2 : (list[k] & 0x4000) != 0 ? 1 : 0;
                    // (1.48.0) And the job itself, where the window of what a job needs reads it; a byte that says
                    // which filling's record it is.
                    *(int*)(screen + JobScreen.Records + k * JobScreen.RecordBytes + JobScreen.RecordJobAt) = job;
                    *(screen + JobScreen.Records + k * JobScreen.RecordBytes) = (byte)('A' + k);
                }
                if (cursors && job == unitJob)
                    *(int*)(screen + JobScreen.Cursor) = k;
                int place = rows.TreePlace(k);
                if (place >= 0 && place < tree.Length)
                {
                    tree[place] = job;
                    treeFor[place] = unitJob;
                }
            }
            return count;
        }
        rows.Fill = () =>
        {
            calls.Add("fill");
            filled = GameFills();
        };
        rows.Place = (at, where) => calls.Add($"place {where}{(at == (nint)screen ? "" : " elsewhere")}");
        rows.Refresh = at => calls.Add($"refresh{(at == (nint)screen ? "" : " elsewhere")}");
        // The layouts' own move of a box, the game's as it is (1.39.5: the framework changes nothing of it and moves no
        // box): the box put where asked. The game's own animations go through it.
        void GameMoves(nint box, int x, int y)
        {
            *(int*)(box + BoxX) = x;
            *(int*)(box + BoxY) = y;
        }
        gameMoves = GameMoves;
        // The game's own step from one job to the next on the abilities' page (0x2A7D9C), over the piece's places: one
        // back or on, a new press going round and a held one stopping; nothing with one place or fewer.
        byte* piece = screen + JobScreen.Cycler;
        int cycleWay = 0;
        bool cycleFresh = true;
        rows.CycleStep = (at, _, _, says) =>
        {
            int count = *(int*)(at + JobScreen.CycleCount), on = *(int*)(at + JobScreen.CycleOn);
            if (count <= 1 || cycleWay == 0)
                return -1;
            int to = on + (cycleWay == JobScreen.CycleOnward ? 1 : -1);
            if (cycleFresh)
                to = to > count - 1 ? 0 : to < 0 ? count - 1 : to;
            else
                to = Math.Max(0, Math.Min(to, count - 1));
            if (to == on)
                return -1;
            *(int*)(at + JobScreen.CycleOn) = to;
            *(int*)says = cycleWay;
            calls.Add("arrow");
            return *(int*)(at + JobScreen.CyclePlaces + 4 * to);
        };
        Dictionary<string, object?> State(object? answer)
        {
            var listed = new List<int>();
            for (int k = 0; k < ListWords && list[k] != -1; k++)
                listed.Add(list[k]);
            var at = new List<int[]>();
            for (int k = 0; k < JobScreen.Places; k++)
                at.Add(new[] { *(int*)(boxes + k * BoxBytes + BoxX), *(int*)(boxes + k * BoxBytes + BoxY),
                               (int)(*(float*)(boxes + k * BoxBytes + JobScreen.BoxOpacity) * 100) });
            var state = new Dictionary<string, object?>
            {
                ["answer"] = answer, ["list"] = listed, ["boxes"] = at, ["scroll"] = rows.Scroll, ["count"] = rows.Count,
                ["own"] = rows.Own, ["pending"] = rows.Pending, ["tree"] = (int[])tree.Clone(), ["calls"] = new List<string>(calls),
                ["ends"] = new[] { *(int*)(screen + JobScreen.RowEnds), *(int*)(screen + JobScreen.RowEnds + 4),
                                   *(int*)(screen + JobScreen.RowEnds + 8) },
                ["cursor"] = *(int*)(screen + JobScreen.Cursor), ["hover"] = *(int*)(screen + JobScreen.Hover),
                ["sides"] = new[] { sides[0], sides[1], sides[2] }, ["alive"] = *alive, ["palette"] = *palette,
            };
            var through = new List<int>();
            for (int k = 0; k < *(int*)(piece + JobScreen.CycleCount) && k < JobScreen.Places; k++)
                through.Add(*(int*)(piece + JobScreen.CyclePlaces + 4 * k));
            state["cycle"] = through;
            state["on"] = *(int*)(piece + JobScreen.CycleOn);
            state["marked"] = marked;
            state["harvested"] = new List<int[]>(harvested);
            state["harvesting"] = *harvesting;
            state["treeFor"] = (int[])treeFor.Clone();
            state["gameCount"] = (int)*gameCount;
            harvested.Clear();
            var closed = new List<int>();
            for (int k = 0; k < JobScreen.Places; k++)
                closed.Add(*(int*)(screen + JobScreen.Records + k * JobScreen.RecordBytes + JobScreen.RecordClosed));
            state["closed"] = closed;
            int under = *(int*)(screen + JobScreen.Cursor);
            state["job"] = under >= 0 && under < ListWords ? list[under] & JobScreen.JobBits : -1;
            calls.Clear();
            return state;
        }
        var report = new List<Dictionary<string, object?>>();
        byte* told = Block(16);
        if (r.TryGetProperty("harvest", out var harvests) && harvests.GetBoolean())
        {
            *(nint*)(holder + JobScreen.HolderTree) = (nint)treeBlock;
            rows.Harvested = (job, record, tree) =>
                harvested.Add(new[] { job, *(int*)(record + JobScreen.RecordJobAt), *(int*)(record + JobScreen.RecordClosed),
                                      tree == (nint)treeBlock ? 1 : 0 });
            rows.HarvestBegins = () => calls.Add("harvest begins");
            rows.HarvestNone = tree => calls.Add($"harvest none{(tree == (nint)treeBlock ? "" : " without a tree")}");
        }
        foreach (var step in r.GetProperty("steps").EnumerateArray())
        {
            string what = step.GetProperty("do").GetString()!;
            if (what == "show")
            {
                // (1.49.0) Job Progress going back to the screen with one of the mods' jobs chosen: its row shown.
                report.Add(State(rows.Show(step.GetProperty("job").GetInt32())));
            }
            else if (what == "screen")
            {
                // The screen before it ended first, as the game's ending is changed to tell the framework
                // ("ended": false leaves that out, as were the ending never told).
                if (!step.TryGetProperty("ended", out var isEnded) || isEnded.GetBoolean())
                    *alive = 0;
                new Span<byte>(screen, ScreenBytes).Clear();
                int dx = 0, dy = 0, sliding = 0;
                if (step.TryGetProperty("offset", out var offset))
                {
                    dx = offset[0].GetInt32();
                    dy = offset[1].GetInt32();
                }
                if (step.TryGetProperty("sliding", out var slide))
                    sliding = slide.GetInt32();
                restX = dx;
                restY = dy;
                for (int k = 0; k < JobScreen.Places; k++)
                {
                    byte* box = boxes + k * BoxBytes;
                    *(int*)(box + BoxX) = LayoutRest[k].X + dx - (k > 0 ? sliding : 0);
                    *(int*)(box + BoxY) = LayoutRest[k].Y + dy;
                    *(float*)(box + JobScreen.BoxOpacity) = 1f;
                    *(nint*)(screen + JobScreen.Slots + k * JobScreen.SlotBytes + JobScreen.SlotBox) = (nint)box;
                }
                for (int row = 0, end = 0; row < JobScreen.Shown; row++)
                {
                    end += JobScreen.GameRows[row];
                    *(int*)(screen + JobScreen.RowEnds + 4 * row) = end;
                }
                *(int*)(screen + JobScreen.Cursor) = -1;
                *(int*)(screen + JobScreen.Hover) = -1;
                *(nint*)(holder + JobScreen.HolderScreen) = (nint)screen;
                report.Add(State(null));
            }
            else if (what == "gone")
            {
                *(nint*)(holder + JobScreen.HolderScreen) = 0;
                report.Add(State(null));
            }
            else if (what == "use")
            {
                inUse = step.GetProperty("on").GetBoolean();
                report.Add(State(null));
            }
            else if (what == "abilities")
            {
                // The game going to the abilities' page (0x12FC6C): the screen's state 9, and the piece given every
                // place whose record is open, of all 19, and which of them the cursor is on.
                *(int*)(screen + JobScreen.State) = 9;
                int n = 0;
                for (int k = 0; k < JobScreen.Places; k++)
                    if (*(int*)(screen + JobScreen.Records + k * JobScreen.RecordBytes + JobScreen.RecordClosed) == 0)
                    {
                        if (k == *(int*)(screen + JobScreen.Cursor))
                            *(int*)(piece + JobScreen.CycleOn) = n;
                        *(int*)(piece + JobScreen.CyclePlaces + 4 * n++) = k;
                    }
                *(int*)(piece + JobScreen.CycleCount) = n;
                report.Add(State(null));
            }
            else if (what == "cycle")
            {
                // Q or E on the abilities' page: the screen's step asks the framework in place of the piece's own
                // step, and puts the cursor on the place answered.
                cycleWay = step.GetProperty("way").GetInt32();
                cycleFresh = !step.TryGetProperty("fresh", out var isFresh) || isFresh.GetBoolean();
                int says = 0;
                bool elsewhere = step.TryGetProperty("elsewhere", out var other) && other.GetBoolean();
                int answer = rows.Cycle((nint)piece, 0, 0, (nint)(&says), elsewhere ? (nint)boxes : (nint)screen);
                if (answer != -1)
                    *(int*)(screen + JobScreen.Cursor) = answer;
                var state = State(answer);
                state["says"] = says;
                report.Add(state);
            }
            else if (what == "marks")
            {
                // (1.48.0) The marks the framework's asker answers for the mods' jobs from here on.
                var given = new List<int>();
                foreach (var n in step.GetProperty("marks").EnumerateArray())
                    given.Add(n.GetInt32());
                marks = given.ToArray();
                report.Add(State(null));
            }
            else if (what == "needs")
            {
                // (1.48.0) Confirm on a job that isn't open: the screen's change of state asks the framework in place
                // of the game's window of what the job needs. "needed": what the asker answers the job at the
                // cursor needs (null: not known); "stands": whether a record can be made for a job not shown. The
                // game's window, as it is called: every place's record then (its job, whether it is closed, its
                // first byte), and what its own search would find for each need (the first place whose job is known
                // as the need, by the same rule as the native code's).
                if (step.TryGetProperty("cursor", out var needsCursor))
                    *(int*)(screen + JobScreen.Cursor) = needsCursor.GetInt32();
                int[]? needed = null;
                if (step.TryGetProperty("needed", out var neededList) && neededList.ValueKind == JsonValueKind.Array)
                {
                    var all = new List<int>();
                    foreach (var n in neededList.EnumerateArray())
                        all.Add(n.GetInt32());
                    needed = all.ToArray();
                }
                bool stands = !step.TryGetProperty("stands", out var canStand) || canStand.GetBoolean();
                // (1.55.1) "mastered": which of the needs are of a job mastered (null: none); "hasMastered": the needs (as
                // known) the unit has mastered.
                bool[]? masteredList = null;
                if (step.TryGetProperty("mastered", out var masteredValue) && masteredValue.ValueKind == JsonValueKind.Array)
                {
                    var all = new List<bool>();
                    foreach (var b in masteredValue.EnumerateArray())
                        all.Add(b.GetBoolean());
                    masteredList = all.ToArray();
                }
                var hasMastered = new HashSet<int>();
                if (step.TryGetProperty("hasMastered", out var hasValue))
                    foreach (var n in hasValue.EnumerateArray())
                        hasMastered.Add(n.GetInt32());
                var askedMastered = new List<int>();
                rows.MasteredNeeds = job => masteredList;
                rows.HasMastered = known =>
                {
                    askedMastered.Add(known);
                    return hasMastered.Contains(known);
                };
                bool elsewhere = step.TryGetProperty("elsewhere", out var other) && other.GetBoolean();
                bool faults = step.TryGetProperty("faults", out var isFault) && isFault.GetBoolean();
                var modNumbers = new short[mods.Count];
                for (int k = 0; k < mods.Count; k++)
                    modNumbers[k] = (short)mods[k];
                var asked = new List<int>();
                var stood = new List<int[]>();
                rows.Needed = job =>
                {
                    asked.Add(job);
                    return needed;
                };
                rows.Stand = (job, closed, to) =>
                {
                    stood.Add(new[] { job, closed });
                    if (!stands)
                        return false;
                    new Span<byte>((void*)to, JobScreen.RecordBytes).Fill(0x5A);
                    *(int*)(to + JobScreen.RecordJobAt) = job;
                    *(int*)(to + JobScreen.RecordClosed) = closed < 0 ? 1 : closed;
                    *(byte*)to = (byte)'s';
                    return true;
                };
                var during = new List<int[]>();
                var levels = new List<int>();
                var finds = new List<int>();
                int windows = 0;
                rows.NeedsWindow = at =>
                {
                    windows++;
                    calls.Add($"window{(at == (nint)screen ? "" : " elsewhere")}");
                    for (int k = 0; k < JobScreen.Places; k++)
                    {
                        byte* record = screen + JobScreen.Records + k * JobScreen.RecordBytes;
                        during.Add(new[] { *(int*)(record + JobScreen.RecordJobAt), *(int*)(record + JobScreen.RecordClosed), *record });
                        levels.Add(*(int*)(record + JobScreen.RecordLevelAt));
                    }
                    foreach (int need in needed ?? Array.Empty<int>())
                    {
                        int found = -1;
                        for (int k = 0; k < JobScreen.Places && found < 0; k++)
                            if (JobNeeds.Known(*(ushort*)(screen + JobScreen.Records + k * JobScreen.RecordBytes + JobScreen.RecordJobAt),
                                               modNumbers) == need)
                                found = k;
                        finds.Add(found);
                    }
                    if (faults)
                        throw new InvalidOperationException("the window faults");
                };
                byte[] before = new ReadOnlySpan<byte>(screen + JobScreen.Records, JobScreen.Places * JobScreen.RecordBytes).ToArray();
                string? fault = null;
                // Elsewhere: a screen that isn't the one arranged, holding everything the arranged one holds (its
                // cursor, its records), so that only which screen it is tells the two apart.
                byte* otherScreen = null;
                if (elsewhere)
                {
                    otherScreen = Block(ScreenBytes);
                    new ReadOnlySpan<byte>(screen, ScreenBytes).CopyTo(new Span<byte>(otherScreen, ScreenBytes));
                }
                try
                {
                    rows.Needs(elsewhere ? (nint)otherScreen : (nint)screen);
                }
                catch (InvalidOperationException e)
                {
                    fault = e.Message;
                }
                var state = State(null);
                state["asked"] = asked;
                state["stood"] = stood;
                state["during"] = during;
                state["levels"] = levels;
                state["askedMastered"] = askedMastered;
                state["finds"] = finds;
                state["windows"] = windows;
                state["windowed"] = rows.Windowed;
                state["fault"] = fault;
                state["restored"] = new ReadOnlySpan<byte>(screen + JobScreen.Records, JobScreen.Places * JobScreen.RecordBytes)
                    .SequenceEqual(before);
                report.Add(state);
            }
            else if (what == "back")
            {
                // Back from the abilities' page to the jobs: the screen's state 2, the cursor where it is.
                *(int*)(screen + JobScreen.State) = 2;
                report.Add(State(null));
            }
            else if (what == "animate")
            {
                // The game's own animation of the places: each box put, by the layouts' move, where the layout rests
                // it and "by" from there (every box), or the boxes named put where said.
                if (step.TryGetProperty("by", out var by))
                    for (int k = 0; k < JobScreen.Places; k++)
                        GameMoves((nint)(boxes + k * BoxBytes), LayoutRest[k].X + restX + by[0].GetInt32(),
                                  LayoutRest[k].Y + restY + by[1].GetInt32());
                if (step.TryGetProperty("boxes", out var named))
                    foreach (var b in named.EnumerateArray())
                        GameMoves((nint)(boxes + b[0].GetInt32() * BoxBytes), b[1].GetInt32(), b[2].GetInt32());
                report.Add(State(null));
            }
            else if (what == "list")
            {
                var jobs = new List<int>();
                foreach (var n in step.GetProperty("jobs").EnumerateArray())
                    jobs.Add(n.GetInt32());
                gameJobs = jobs.ToArray();
                int unit = step.GetProperty("unit").GetInt32();
                *index = (short)unit;
                unitJob = step.GetProperty("job").GetInt32();
                one = step.TryGetProperty("one", out var hidden) && hidden.GetBoolean();
                if (unit >= 0 && unit < Records)
                    *(ushort*)(table[unit] + JobScreen.RecordJob) = (ushort)unitJob;
                *(int*)(screen + JobScreen.State) = step.TryGetProperty("state", out var state) ? state.GetInt32() : 2;
                // The game's call of its filling, and the framework told after it, as the native code has it.
                int listed = GameFills();
                if (!step.TryGetProperty("after", out var isAfter) || isAfter.GetBoolean())
                    rows.After();
                report.Add(State(listed));
            }
            else if (what == "idle")
            {
                int times = step.GetProperty("times").GetInt32();
                delta = 0;
                fresh = true;
                new Span<byte>(told, 16).Clear();
                int took = 0, answer = 0;
                for (int n = 1; n <= times; n++)
                {
                    int before = calls.FindAll(c => c == "fill").Count;
                    answer = rows.Vertical(0, 0, JobScreen.Shown - 1, 5, 9, (nint)screen, (nint)told);
                    if (took == 0 && calls.FindAll(c => c == "fill").Count > before)
                        took = n;
                }
                var state = State(answer);
                state["told"] = new[] { *(int*)told, *(int*)(told + JobScreen.OutPlace), *(told + JobScreen.OutMoved) };
                state["took"] = took;
                state["filled"] = filled;
                report.Add(state);
            }
            else if (what == "step")
            {
                delta = step.GetProperty("delta").GetInt32();
                fresh = !step.TryGetProperty("fresh", out var isNew) || isNew.GetBoolean();
                if (step.TryGetProperty("cursor", out var cursor))
                    *(int*)(screen + JobScreen.Cursor) = cursor.GetInt32();
                if (step.TryGetProperty("hover", out var hover))
                    *(int*)(screen + JobScreen.Hover) = hover.GetInt32();
                int min = step.TryGetProperty("min", out var low) ? low.GetInt32() : 0;
                int max = step.TryGetProperty("max", out var high) ? high.GetInt32() : JobScreen.Shown - 1;
                bool elsewhere = step.TryGetProperty("elsewhere", out var other) && other.GetBoolean();
                new Span<byte>(told, 16).Clear();
                upDowns = 0;
                int answer = rows.Vertical(step.GetProperty("row").GetInt32(), min, max, 5, 9,
                                           elsewhere ? (nint)told : (nint)screen, (nint)told);
                var state = State(answer);
                state["told"] = new[] { *(int*)told, *(int*)(told + JobScreen.OutPlace), *(told + JobScreen.OutMoved) };
                state["upDowns"] = upDowns;
                state["handed"] = new[] { handed.Item1, handed.Item2 };
                state["filled"] = filled;
                report.Add(state);
            }
            else
                throw new InvalidDataException($"no step called {what}");
        }
        File.WriteAllText(args[2], JsonSerializer.Serialize(new Dictionary<string, object?>
        {
            ["steps"] = report,
            ["rowSizes"] = new[] { JobScreen.RowSizes(0), JobScreen.RowSizes(1), JobScreen.RowSizes(6), JobScreen.RowSizes(7),
                                   JobScreen.RowSizes(8), JobScreen.RowSizes(22) },
            ["scrolls"] = new[] { JobScreen.Scrolls(JobScreen.RowSizes(0)), JobScreen.Scrolls(JobScreen.RowSizes(1)),
                                  JobScreen.Scrolls(JobScreen.RowSizes(6)), JobScreen.Scrolls(JobScreen.RowSizes(7)),
                                  JobScreen.Scrolls(JobScreen.RowSizes(8)), JobScreen.Scrolls(JobScreen.RowSizes(22)) },
            ["layoutRest"] = Array.ConvertAll(LayoutRest, p => new[] { p.X, p.Y }),
        }));
        return 0;
    }
}
