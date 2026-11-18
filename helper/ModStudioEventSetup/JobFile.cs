// Mod Studio Framework: (1.36.0, 1.37.0) reading a mod's own job. Part of The Ivalice
// Chronicles Mod Studio, GPL-3.0.
//
// Zodi's ask of 9 November: "The final touch would be adding new Jobs and
// Abilities for those jobs." His choice for the first step: one job, start to
// finish, looking like one of the game's, its own name and stats, its abilities
// one of the game's skillsets for now. A job is a folder of its own in a mod,
// `ModStudioJobs/<job>/`, holding `job.json`: its name, the game's job it looks
// like (that job's sprites, portrait, icons and JP table), its record as the
// game keeps a job's (49 bytes) and its words (the Job table's name and
// description). What can't be used is left out and said. A modder never chooses
// a number: the framework numbers each job (JobRoom.cs).
//
// (1.37.0, his word on test 77: "Go on and complete this") A job has a skillset
// of its own: `Skillset` names the game's skillset it looks like (its icon), its
// action abilities (1 to 16 of the game's) and its reaction, support and
// movement abilities (up to 6), and its own name and description. The framework
// numbers the skillset too, so the first number of `Record` is whatever the file
// has: it is replaced. A file of version 1 (a job with one of the game's
// skillsets) isn't read any more.
//
// (1.42.0, the road's step 5; his word on test 98: "I believe Sprites are next on our list for new Jobs") A job can
// have a look of its own: `Look` names the game's generic job whose look it wears (the Enhanced look's sheets and the
// palettes they are drawn with, and its portraits' faces), on two sprite numbers of the job's own (SpriteRoom.cs). The
// classic look's sheets, the job screen's figure and the icons stay its Like's for now. Without a Look a job looks like
// its Like, as before.
//
// (1.43.0, the road's step 5's second part; his choice of 12 November: "Colors first") A Look can hold its own Colors:
// its man's and its woman's palettes (`Man`, `Woman`, either or both), each a list of 1 to 5 palettes in the order the
// game keeps a figure's (the first its player's team's), each 16 colors written "#RRGGBB", the first see through
// ("#000000"). The game colors a figure from a table (CharCLUT), as it colors Ramza's looks; the framework gives the job's
// own sprites rows of it (SpriteRoom.cs). A palette not given keeps its Look's colors.
//
// (1.44.0, step 5's second part, next in his order: the sprites' textures) A Look can hold its own Textures: its man's
// and its woman's (`Man`, `Woman`, either or both), each a list of two file names in the job's folder, its upper
// texture's and its lower texture's, as the game keeps a sprite's two textures in g2d.dat (4 bits a pixel, 512 pixels
// wide, the left pixel in a byte's low four bits; the upper 512 rows, 131,072 bytes; the lower 1 to 512 rows, the
// game's own 464, 118,784 bytes), drawn for its Like's frames and colored by its colors (its own or its Look's). The
// framework gives the game those textures for the job's own sprites (SpriteTextures.cs).
//
// (1.45.0, step 5's second part, the last in his order: the portraits) A Look can hold its own Portraits: its man's and
// its woman's (`Man`, `Woman`, either or both), each a list of 1 to 5 names, one a team's colors in the game's order (the
// first its player's team's; a team past the list's end takes the first), each the name of a part list in the job's mod,
// at FFTIVC/data/enhanced/ui/ffto/common/face/textureparts/<name>.utexpt, laid out as the game's own faces (the whole
// face, three eyes and four mouths) and naming its texture. The game reads those files itself, through the mod loader;
// the framework sends the job's own sprites' portraits to them (SpritePortraits.cs).
//
// (1.46.0, step 5's third part; Zodi's word of 12 November: "The modder can pick either their own files or one of the
// game's for the job icon and skillset icon but not for the man art or woman art. The modder should be able to choose
// their own art for male and or female or no art for the male and or female.") A job can pick its `Icon` (the small job
// symbol) and its `Skillset`'s `Icon`, each one of the game's (the game's generic job whose icon it shows, 74 to 93; the
// game's skillset whose icon its skillset shows, 5 to 24) or its own (the name of a part list in its mod, at
// FFTIVC/data/enhanced/ui/ffto/icon/job/textureparts/<name>.utexpt or .../job_comm/..., laid out as the game's and naming
// its texture); an icon it doesn't pick is its Like's. Its `Pictures` (the job screen's big drawings, its `Man`'s and its
// `Woman`'s) are each its own part list (.../job_visual/...) or none, and none is no picture anywhere ("No picture there
// either", his word). None of it needs a Look (JobArt.cs).
//
// (1.48.0, the Job Tree's first step, his order of 13 November: what opens a new job) A job can say what it needs:
// `Needs`, a list of up to 6 (the most the game's own window of what a job needs lists, and the most any of the game's
// jobs has), each `{"Job": ..., "Level": ...}`: the job one of the game's generic jobs (74 to 93) or the Name of another
// job of the same mod, the level 1 to 8. Left out, null or empty: the job is open to every unit, as before. A job needed
// can't be the job itself or be given twice, a name has to be one of the mod's jobs, and the mod's jobs can't need each
// other in a ring: such a job is left out and said (JobNeeds.cs has what the framework does with them).
//
// (1.55.2, Zodi's word of 15 November on test 123: "can new jobs could also get the Mastered jobs requirement like Dark
// Knight does, we should support that if modders want it. Like if the user wanted Ninja master as a requirement for its
// job.") A need of one of the game's generic jobs may ask it mastered: `{"Job": 89, "Level": "Mastered"}` (the word in
// any case), every place of the job's skillset learned, as the game's Dark Knight asks of the Knight and the Black Mage
// (JobNeeds.cs). (1.56.0, Zodi's answer of 16 November: "yes a job also be able to need one of your own mod's jobs
// mastered") A job of the same mod may be asked mastered too: `{"Job": "Mender", "Level": "Mastered"}`, every place of
// its own skillset learned (JobNeeds.cs).
//
// (1.54.0, Zodi's 8th note of 14 November: "Sprites for humans have two kinds that the community refers to as Type1 and
// Type2. When replacing the squires sprites for the users modded sprite we should account for this.", and his pick
// "Framework sets its frames") A Look can say the frames its own textures are drawn for: `Frames`, its man's and its
// woman's (`Man`, `Woman`, either or both), each 1 or 2, the game's two kinds of human frames (Type 1: the Squire's,
// Knight's, Archer's, Monk's, Thief's, Dragoon's, Samurai's and Ninja's; Type 2: the other twelve generic jobs'). Only a
// man or a woman with textures of its own can say it: one wearing its Look's textures is drawn in their frames. Not
// said, its own textures are drawn in its Like's frames, as before (SpriteRoom.Source).
//
// (1.55.0, his three answers of 14 November: "a mod gives them") A job's file can be the game's own Dark Knight or Onion
// Knight: `Game`, 160 or 161. Such a job keeps the game's number, its progress in the unit's own rows and what the game
// does with it (dev/research/sidequests/dark_onion.py); its file gives its Like (its look where it has no Look of its
// own, the row of the Job table its own is made from, its JP table), its Record (the first number replaced by the
// game's: Dark Knight's skillset 224, Onion Knight's none), its Words, its Look and its art as any job's. What opens it
// is the game's own rule less the kills (his second answer), so it gives no Needs. Dark Knight's abilities are the game's
// own skillset 224 (his third answer): its Skillset gives that skillset's words and icon and no Actions or Others, and
// may give `Names`, a name and description for each of the skillset's abilities the game leaves without one (each
// `{"Ability": ..., "Name": ..., "Description": ...}`). Onion Knight learns no abilities: no Skillset.
//
// (1.55.1, Zodi's words of 15 November: "after every base game job is mastered making Onion Knight lvl 8 the description
// changes") Onion Knight's Words may give `MasteredDescription`, its words for a unit whose Onion Knight is level 8, as
// the Description's rules: Job Summary shows them there (JobWords.cs, JobRoom's SummarySites). (Zodi's word of 05:49:
// "make sure the Job Summary for the two jobs matches the format of the vanilla jobs") And `MasteredSummary`, its whole
// Job Summary there, as the Summary's rules (the game's own rows' sections: Job Overview, Usable Equipment, Select
// Abilities): Job Summary shows it at level 8, before the MasteredDescription under the heading.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Json;

namespace ModStudioEventSetup
{
    /// <summary>(1.48.0) One of the jobs a job needs: one of the game's generic jobs (`Job`, 74 to 93) or another of its
    /// own mod's by its Name (`Own`; `Job` is 0 then), at a level of 1 to 8. (1.55.2) Or one of the game's generic jobs
    /// mastered (`Mastered`: every place of its skillset learned; `Level` is then 8, the most a level can be); (1.56.0,
    /// Zodi's answer of 16 November: "yes a job also be able to need one of your own mod's jobs mastered") or a job of
    /// its own mod's mastered.</summary>
    public readonly struct JobNeed
    {
        public int Job { get; }
        public string? Own { get; }
        public int Level { get; }
        public bool Mastered { get; }

        public JobNeed(int job, string? own, int level, bool mastered = false)
        {
            Job = job;
            Own = own;
            Level = level;
            Mastered = mastered;
        }
    }

    /// <summary>(1.55.0) A name and description a job's file gives one of the game's own abilities its skillset holds,
    /// where the game leaves it without one.</summary>
    public readonly struct AbilityName
    {
        public int Ability { get; }
        public string Name { get; }
        public string Description { get; }

        public AbilityName(int ability, string name, string description)
        {
            Ability = ability;
            Name = name;
            Description = description;
        }
    }

    /// <summary>A mod's own job, as its mod gives it.</summary>
    public sealed class ModJob
    {
        public string ModId { get; }
        public string ModName { get; }
        public string Name { get; }
        /// <summary>The game's generic job it looks like (74 to 93): its sprites, portrait and icons, and its JP table.</summary>
        public int Like { get; }
        /// <summary>Its record as the game keeps a job's: its skillset, innate abilities, equipment, growths, Move, Jump,
        /// evade, statuses, elements and look.</summary>
        public byte[] Record { get; }
        public string WordName { get; }
        public string Description { get; }
        /// <summary>Its own skillset: the game's skillset it looks like (5 to 23: its icon), its action abilities (1 to
        /// 16), its reaction, support and movement abilities (up to 6), its name and description.</summary>
        public int SkillsetLike { get; }
        public int[] Actions { get; }
        /// <summary>(1.41.0) Where a place of Actions names one of the mod's own abilities: its Name (that place of
        /// Actions is 0 until the ability is given its number: AbilityPlan); else null.</summary>
        public string?[] ActionNames { get; }
        public int[] Others { get; }
        public string SkillsetName { get; }
        public string SkillsetDescription { get; }
        /// <summary>(1.42.0) The game's generic job whose look it wears (74 to 93: the Enhanced look's sheets and palettes,
        /// its portraits' faces), on sprite numbers of its own; 0 when it has no Look (it looks like its Like).</summary>
        public int LookLike { get; }
        /// <summary>(1.43.0) Its own colors, if its Look gives any: [0] its man's palettes, [1] its woman's (null where
        /// that one keeps its Look's colors), each palette 16 colors as 0xRRGGBB, the first palettes of the figure's in
        /// the game's order.</summary>
        public int[][]?[] Colors { get; }
        public bool HasColors => Colors[0] != null || Colors[1] != null;
        /// <summary>(1.44.0) Its own textures, if its Look gives any: [0] its man's, [1] its woman's (null where that one
        /// keeps its Look's), each its upper texture's bytes and its lower texture's, as g2d.dat keeps a sprite's.</summary>
        public byte[][]?[] Textures { get; }
        public bool HasTextures => Textures[0] != null || Textures[1] != null;
        /// <summary>(1.45.0) Its own portraits, if its Look gives any: [0] its man's, [1] its woman's (null where that one
        /// keeps its Look's), each 1 to 5 names of part lists in its mod, one a team's colors (the first its player's
        /// team's).</summary>
        public string[]?[] Portraits { get; }
        public bool HasPortraits => Portraits[0] != null || Portraits[1] != null;
        /// <summary>(1.54.0) The frames its own textures are drawn for, if its Look says: [0] its man's, [1] its woman's,
        /// each 1 (Type 1) or 2 (Type 2), 0 where it doesn't say (its Like's frames). Said only with textures of its
        /// own.</summary>
        public int[] Frames { get; }
        /// <summary>(1.46.0) Its picks of its icon and its skillset's icon (each the game's or its own, or neither) and its
        /// two job screen pictures (each its own or none) (JobArt.cs).</summary>
        public JobArtPicks Art { get; }
        /// <summary>(1.47.0) Its own words on Job Summary, as the game shows them (its Words' Summary), or null where its
        /// file gives none: Job Summary then shows its Description under the game's own heading (JobWords.cs).</summary>
        public string? Summary { get; }
        /// <summary>(1.48.0) What it needs before a unit can take it (its file's Needs): none, and it is open to every
        /// unit (JobNeeds.cs).</summary>
        public JobNeed[] Needs { get; }
        /// <summary>(1.55.0) The game's own job it is (JobFile.DarkKnight or JobFile.OnionKnight), or 0: a job of its
        /// mod's own.</summary>
        public int Game { get; }
        /// <summary>(1.55.0) The names it gives the game's abilities of its skillset that have none (Dark Knight's).</summary>
        public AbilityName[] AbilityNames { get; }
        /// <summary>(1.55.1) The game's Onion Knight's words for a unit whose Onion Knight is level 8 (its Words'
        /// MasteredDescription), or null: Job Summary shows them under the game's heading there (JobWords.cs).</summary>
        public string? MasteredDescription { get; }
        /// <summary>(1.55.1, Zodi's word of 05:49) The game's Onion Knight's whole Job Summary for a unit whose Onion Knight
        /// is level 8 (its Words' MasteredSummary), or null: Job Summary shows its MasteredDescription there.</summary>
        public string? MasteredSummary { get; }
        /// <summary>(1.55.1) Whether it has words for its level 8 (a MasteredDescription or a MasteredSummary).</summary>
        public bool MasteredWords => MasteredDescription != null || MasteredSummary != null;

        public ModJob(string modId, string modName, string name, int like, byte[] record, string wordName, string description,
                      int skillsetLike, int[] actions, int[] others, string skillsetName, string skillsetDescription,
                      string?[]? actionNames = null, int lookLike = 0, int[][]?[]? colors = null,
                      byte[][]?[]? textures = null, string[]?[]? portraits = null, JobArtPicks? art = null,
                      string? summary = null, JobNeed[]? needs = null, int[]? frames = null, int game = 0,
                      AbilityName[]? abilityNames = null, string? masteredDescription = null, string? masteredSummary = null)
        {
            MasteredDescription = masteredDescription;
            MasteredSummary = masteredSummary;
            Game = game;
            AbilityNames = abilityNames ?? Array.Empty<AbilityName>();
            Frames = frames ?? new int[2];
            Needs = needs ?? Array.Empty<JobNeed>();
            Summary = summary;
            Art = art ?? JobArtPicks.None;
            LookLike = lookLike;
            Colors = colors ?? new int[][]?[2];
            Textures = textures ?? new byte[][]?[2];
            Portraits = portraits ?? new string[]?[2];
            ActionNames = actionNames ?? new string?[actions.Length];
            ModId = modId;
            ModName = modName;
            Name = name;
            Like = like;
            Record = record;
            WordName = wordName;
            Description = description;
            SkillsetLike = skillsetLike;
            Actions = actions;
            Others = others;
            SkillsetName = skillsetName;
            SkillsetDescription = skillsetDescription;
        }

        /// <summary>The name its number is kept under (Numbers.json's Jobs).</summary>
        public string Key => $"{ModId}/{Name}";
        public string Who => $"{ModName}'s {Name}";

        /// <summary>(1.41.0) The same job with other numbers in its skillset's Actions (AbilityPlan: the ability a mod's
        /// own is like, where Actions names it).</summary>
        public ModJob WithActions(int[] actions)
            => new ModJob(ModId, ModName, Name, Like, Record, WordName, Description, SkillsetLike, actions, Others, SkillsetName,
                          SkillsetDescription, ActionNames, LookLike, Colors, Textures, Portraits, Art, Summary, Needs, Frames,
                          Game, AbilityNames, MasteredDescription, MasteredSummary);
    }

    /// <summary>(1.55.0) A job's Look as its file gives it (JobFile.GameLook).</summary>
    public readonly struct ParsedLook
    {
        public int Like { get; }
        public int[][]?[] Colors { get; }
        public byte[][]?[] Textures { get; }
        public string[]?[] Portraits { get; }
        public int[] Frames { get; }

        public ParsedLook(int like, int[][]?[] colors, byte[][]?[] textures, string[]?[] portraits, int[] frames)
        {
            Like = like;
            Colors = colors;
            Textures = textures;
            Portraits = portraits;
            Frames = frames;
        }
    }

    public static class JobFile
    {
        public const string Folder = "ModStudioJobs", Name = "job.json", Format = "Mod Studio job";
        /// <summary>(1.47.0) The most characters of a job's Summary (the game's longest, in any language, is 3,081) and the
        /// most bytes it may take as the game keeps it.</summary>
        public const int SummaryMost = 4000, SummaryBytesMost = 16000;
        public const int Version = 2, RecordBytes = 0x31, FirstLike = 74, LastLike = 93, NameMost = 40, DescriptionMost = 300,
                         FirstSkillset = 5, LastSkillset = 23;
        /// <summary>A skillset's abilities: how many actions and others it holds, and the game's numbers (an action is 1
        /// to 421, a reaction, support or movement ability 422 to 511).</summary>
        public const int MostActions = 16, MostOthers = 6, FirstOther = 0x1A6, LastAbility = 0x1FF;
        /// <summary>(1.43.0) A Look's Colors: up to 5 palettes for a man and for a woman (a figure's: the game keeps 5, one
        /// a team), each 16 colors.</summary>
        public const int MostPalettes = 5, PaletteColors = 16;
        /// <summary>(1.44.0) A Look's Textures: a row of a texture (512 pixels at 4 bits a pixel), the upper texture's
        /// rows, the most a lower texture has, and the game's own lower textures' bytes (464 rows).</summary>
        public const int TextureRowBytes = 256, TextureRows = 512, UpperTextureBytes = TextureRowBytes * TextureRows,
                         GameLowerTextureBytes = TextureRowBytes * 464;
        /// <summary>(1.45.0) A Look's Portraits: up to 5 for a man and for a woman (one a team's colors), each a name of up
        /// to 64 letters, digits and _, of a part list in the job's mod's PortraitsFolder.</summary>
        public const int MostPortraits = 5, PortraitNameMost = 64;
        /// <summary>(1.54.0) A Look's Frames: the game's two kinds of human frames, Type 1 and Type 2.</summary>
        public const int Type1Frames = 1, Type2Frames = 2;
        /// <summary>(1.48.0) A job's Needs: how many at most (the rows of the game's window of what a job needs, and the
        /// most a job of the game's has), and the levels a need can ask (the game's jobs have eight).</summary>
        public const int MostNeeds = 6, LeastNeedLevel = 1, MostNeedLevel = 8;
        /// <summary>(1.55.2) The word a need's Level is to ask its job mastered (in any case).</summary>
        public const string MasteredWord = "Mastered";
        public const string PortraitsFolder = "FFTIVC/data/enhanced/ui/ffto/common/face/textureparts";
        /// <summary>(1.55.0) The game's own jobs a job's file can be (its Game), Dark Knight's skillset (the game's own,
        /// its record's first number) and the abilities it holds as the game has it (dark_onion.py's SKILLSET_224).</summary>
        public const int DarkKnight = 160, OnionKnight = 161, DarkSkillset = 224;
        public static readonly int[] DarkAbilities = { 45, 184, 219, 220, 357, 484, 485, 488, 491 };
        /// <summary>(1.55.1) The job the game takes a level 8 Onion Knight's record and words from (dark_onion.py's
        /// MASTERED_ONION): its key of the job help table holds the game's Onion Knight's words for its level 8.</summary>
        public const int MasteredOnion = 164;

        /// <summary>(1.55.0) The game's own job's name, for what is said.</summary>
        public static string GameJobName(int game) => game == DarkKnight ? "Dark Knight" : "Onion Knight";

        /// <summary>(1.53.0) Whether a text can be a job's Name as a job's file gives it (1 to NameMost characters, none a
        /// control character): what a quest's battle names one of its mod's jobs by (QuestFile's Jobs).</summary>
        public static bool GoodJobName(string text)
        {
            foreach (char ch in text)
                if (char.IsControl(ch))
                    return false;
            return text.Length > 0 && text.Length <= NameMost && Encoding.UTF8.GetByteCount(text) < 1024;
        }

        public static List<ModJob> ReadMod(string modId, string modName, string modFolder, List<string> problems)
        {
            var jobs = new List<ModJob>();
            string root = Path.Combine(modFolder, Folder);
            if (!Directory.Exists(root))
                return jobs;
            var folders = new List<string>(Directory.GetDirectories(root));
            folders.Sort(StringComparer.Ordinal);
            foreach (var folder in folders)
            {
                string file = Path.Combine(folder, Name);
                if (!File.Exists(file))
                    continue;
                string folderName = Path.GetFileName(folder);
                var said = new List<string>();
                ModJob? job = null;
                try
                {
                    job = Read(modId, modName, File.ReadAllText(file), said, folder);
                }
                catch (Exception e) when (e is not OutOfMemoryException)
                {
                    said.Add($"it can't be read ({e.Message})");
                }
                if (job != null && jobs.Exists(j => j.Name == job.Name))
                {
                    said.Add($"another of the mod's jobs is named {job.Name}");
                    job = null;
                }
                foreach (var s in said)
                    problems.Add($"{modName}'s job {folderName}: {s}");
                if (job != null)
                    jobs.Add(job);
            }
            // (1.48.0) What the mod's jobs need of each other: a job that names one the mod doesn't give, or that is in
            // a ring of jobs each needing the next, is left out and said.
            foreach (string s in NeedsBetween(jobs))
                problems.Add($"{modName}'s job {s}");
            return jobs;
        }

        /// <summary>(1.48.0) A mod's jobs' needs of each other held to the mod's jobs: a job that needs one by a name none
        /// of the mod's jobs has is taken out, until every name is one of those left; then every job in a ring (each
        /// needing the next, the last the first) is taken out. What is said of each, the job's name first.</summary>
        public static List<string> NeedsBetween(List<ModJob> jobs)
        {
            var said = new List<string>();
            for (bool again = true; again;)
            {
                again = false;
                for (int k = jobs.Count - 1; k >= 0; k--)
                    foreach (var need in jobs[k].Needs)
                        if (need.Own != null && !jobs.Exists(j => j.Name == need.Own))
                        {
                            said.Add($"{jobs[k].Name}: its Needs name {need.Own}, which isn't a job this mod gives");
                            jobs.RemoveAt(k);
                            again = true;
                            break;
                        }
            }
            // A job is in a ring when following the needs between the mod's jobs from it comes back to it.
            bool Reaches(ModJob from, ModJob to, HashSet<string> seen)
            {
                foreach (var need in from.Needs)
                {
                    if (need.Own == null)
                        continue;
                    if (need.Own == to.Name)
                        return true;
                    if (!seen.Add(need.Own))
                        continue;
                    var next = jobs.Find(j => j.Name == need.Own);
                    if (next != null && Reaches(next, to, seen))
                        return true;
                }
                return false;
            }
            var ringed = jobs.FindAll(j => Reaches(j, j, new HashSet<string>()));
            foreach (var job in ringed)
            {
                said.Add($"{job.Name}: its Needs go round in a ring (a job it needs needs it in turn)");
                jobs.Remove(job);
            }
            // A job that needed one of the ring's has lost it: taken out the same way.
            if (ringed.Count > 0)
                said.AddRange(NeedsBetween(jobs));
            return said;
        }

        /// <summary>(1.48.0) A job's Needs: a list of up to MostNeeds, each a list of fields with a Job (a whole number
        /// FirstLike to LastLike, or the Name of another of the mod's jobs) and a Level (LeastNeedLevel to
        /// MostNeedLevel), no job twice and not the job itself (`name`); null when it isn't, why in `why`.</summary>
        static JobNeed[]? NeedsOf(JsonElement value, string name, out string why)
        {
            why = "";
            string Bad(string what) => $"its Needs {what}: a list of up to {MostNeeds}, each with a Job (one of the game's generic "
                                       + $"jobs, {FirstLike} to {LastLike}, or the Name of another job of this mod) and a Level "
                                       + $"({LeastNeedLevel} to {MostNeedLevel}, or {MasteredWord})";
            if (value.ValueKind != JsonValueKind.Array)
            {
                why = Bad("aren't a list");
                return null;
            }
            if (value.GetArrayLength() > MostNeeds)
            {
                why = Bad($"are {value.GetArrayLength()}");
                return null;
            }
            var needs = new List<JobNeed>();
            foreach (var item in value.EnumerateArray())
            {
                if (item.ValueKind != JsonValueKind.Object || !Has(item, "Job", out var job) || !Has(item, "Level", out var level))
                {
                    why = Bad("hold something that isn't a Job with a Level");
                    return null;
                }
                // (1.55.2) The word Mastered (in any case) asks the job mastered: every place of its skillset learned.
                bool mastered = level.ValueKind == JsonValueKind.String
                                && string.Equals(level.GetString(), MasteredWord, StringComparison.OrdinalIgnoreCase);
                int asked = MostNeedLevel;
                if (!mastered && (level.ValueKind != JsonValueKind.Number || !level.TryGetInt32(out asked) || asked < LeastNeedLevel
                    || asked > MostNeedLevel))
                {
                    why = Bad($"ask the level {Raw(item, "Level")}");
                    return null;
                }
                int number = 0;
                string? own = null;
                bool game = job.ValueKind == JsonValueKind.Number && job.TryGetInt32(out number) && number >= FirstLike
                            && number <= LastLike;
                if (!game)
                {
                    number = 0;
                    own = job.ValueKind == JsonValueKind.String ? Word(item, "Job", NameMost) : null;
                    if (own == null)
                    {
                        why = Bad($"name the job {Raw(item, "Job")}");
                        return null;
                    }
                }
                if (own == name)
                {
                    why = Bad("name the job itself");
                    return null;
                }
                if (needs.Exists(n => own != null ? n.Own == own : n.Own == null && n.Job == number))
                {
                    why = Bad($"name {Raw(item, "Job")} twice");
                    return null;
                }
                // (1.56.0) A job of its own mod's may be asked mastered as one of the game's generic jobs may.
                needs.Add(new JobNeed(number, own, asked, mastered));
            }
            return needs.ToArray();
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

        /// <summary>A word of the job's: text of 1 to `most` characters, no control characters but, in a description, up
        /// to two line breaks; null when wrong.</summary>
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
            return text.Length > 0 && text.Length <= most && breaks <= (most == DescriptionMost ? 2 : 0)
                   && Encoding.UTF8.GetByteCount(text) < 1024 ? text : null;
        }

        /// <summary>(1.47.0) A job's words on Job Summary: text of 1 to SummaryMost characters, no control characters but
        /// line breaks; null when wrong.</summary>
        static string? SummaryWords(JsonElement value)
        {
            if (value.ValueKind != JsonValueKind.String)
                return null;
            string text = value.GetString() ?? "";
            foreach (char ch in text)
                if (ch != '\n' && char.IsControl(ch))
                    return null;
            return text.Length > 0 && text.Length <= SummaryMost && Encoding.UTF8.GetByteCount(text) <= SummaryBytesMost
                   ? text : null;
        }

        /// <summary>A list of `least` to `most` different whole numbers from `first` to `last`; null when it isn't.</summary>
        static int[]? Abilities(JsonElement skillset, string name, int least, int most, int first, int last)
        {
            if (!Has(skillset, name, out var values) || values.ValueKind != JsonValueKind.Array
                || values.GetArrayLength() < least || values.GetArrayLength() > most)
                return null;
            var list = new List<int>();
            foreach (var v in values.EnumerateArray())
            {
                if (v.ValueKind != JsonValueKind.Number || !v.TryGetInt32(out int n) || n < first || n > last || list.Contains(n))
                    return null;
                list.Add(n);
            }
            return list.ToArray();
        }

        /// <summary>(1.41.0) A skillset's Actions: 1 to 16 places, each the game's action ability (a whole number from 1
        /// to 421) or one of the mod's own abilities by its Name (text of 1 to 40 characters), no two alike. Null when it
        /// isn't; `names` holds each place's Name, null where the place is a number (whose place is a number (a named
        /// place's number is 0).</summary>
        static int[]? ActionList(JsonElement skillset, out string?[] names)
        {
            names = Array.Empty<string?>();
            if (!Has(skillset, "Actions", out var values) || values.ValueKind != JsonValueKind.Array
                || values.GetArrayLength() < 1 || values.GetArrayLength() > MostActions)
                return null;
            var numbers = new List<int>();
            var named = new List<string?>();
            foreach (var v in values.EnumerateArray())
            {
                if (v.ValueKind == JsonValueKind.Number && v.TryGetInt32(out int n) && n >= 1 && n < FirstOther
                    && !numbers.Contains(n))
                {
                    numbers.Add(n);
                    named.Add(null);
                    continue;
                }
                if (v.ValueKind == JsonValueKind.String)
                {
                    string text = v.GetString() ?? "";
                    bool control = false;
                    foreach (char ch in text)
                        control |= char.IsControl(ch);
                    if (text.Length >= 1 && text.Length <= AbilityFile.NameMost && !control && !named.Contains(text))
                    {
                        numbers.Add(0);
                        named.Add(text);
                        continue;
                    }
                }
                return null;
            }
            names = named.ToArray();
            return numbers.ToArray();
        }

        /// <summary>(1.43.0) One "#RRGGBB" color as 0xRRGGBB; -1 when it isn't one.</summary>
        static int Color(JsonElement value)
        {
            if (value.ValueKind != JsonValueKind.String)
                return -1;
            string text = value.GetString() ?? "";
            if (text.Length != 7 || text[0] != '#')
                return -1;
            int color = 0;
            for (int n = 1; n < 7; n++)
            {
                int digit = Uri.IsHexDigit(text[n]) ? Convert.ToInt32(text[n].ToString(), 16) : -1;
                if (digit < 0)
                    return -1;
                color = color * 16 + digit;
            }
            return color;
        }

        /// <summary>(1.44.0) A Look's Textures for a man or a woman: a list of two names of files in the job's folder, its
        /// upper texture's (131,072 bytes: 512 by 512 pixels at 4 bits a pixel) and its lower texture's (512 pixels wide at
        /// 4 bits a pixel, 1 to 512 rows), each read. Null and why when it isn't.</summary>
        static byte[][]? TexturesOf(JsonElement textures, string who, string? folder, out string why)
        {
            why = "";
            if (!Has(textures, who, out var list) || list.ValueKind != JsonValueKind.Array || list.GetArrayLength() != 2)
            {
                why = $"its Look's Textures' {who} isn't a list of two file names (its upper texture's and its lower texture's)";
                return null;
            }
            string[] halves = { "upper", "lower" };
            var read = new byte[2][];
            int n = 0;
            foreach (var value in list.EnumerateArray())
            {
                string which = $"its Look's Textures' {who}'s {halves[n]} texture";
                string? fileName = value.ValueKind == JsonValueKind.String ? value.GetString() : null;
                if (string.IsNullOrWhiteSpace(fileName) || fileName == "." || fileName == ".." || fileName.IndexOfAny(NotInAName) >= 0
                    || fileName.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
                {
                    why = $"{which} is {value.GetRawText()}, not the name of a file in the job's folder";
                    return null;
                }
                string? path = folder == null ? null : Path.Combine(folder, fileName);
                if (path == null || !File.Exists(path))
                {
                    why = $"{which}, {fileName}, isn't in the job's folder";
                    return null;
                }
                long size = new FileInfo(path).Length;
                bool fits = n == 0 ? size == UpperTextureBytes
                                   : size >= TextureRowBytes && size <= UpperTextureBytes && size % TextureRowBytes == 0;
                if (!fits)
                {
                    why = n == 0
                        ? $"{which}, {fileName}, is {Bytes(size)} bytes, not {Bytes(UpperTextureBytes)} (512 by 512 pixels at 4 "
                          + "bits a pixel)"
                        : $"{which}, {fileName}, is {Bytes(size)} bytes, not 512 pixels wide at 4 bits a pixel with 1 to 512 "
                          + $"rows (the game's own are {Bytes(GameLowerTextureBytes)} bytes)";
                    return null;
                }
                read[n++] = File.ReadAllBytes(path);
            }
            return read;
        }

        /// <summary>(1.45.0) A Look's Portraits for a man or a woman: a list of 1 to 5 names, each of a part list in the job's
        /// mod (`folder`, the job's own, is two folders inside it: ModStudioJobs, then the job's). Null and why when it
        /// isn't.</summary>
        static string[]? PortraitsOf(JsonElement portraits, string who, string? folder, out string why)
        {
            why = "";
            if (!Has(portraits, who, out var list) || list.ValueKind != JsonValueKind.Array || list.GetArrayLength() < 1
                || list.GetArrayLength() > MostPortraits)
            {
                why = $"its Look's Portraits' {who} isn't a list of 1 to {MostPortraits} names (one a team's colors, the first "
                      + "its player's team's)";
                return null;
            }
            string? mod = folder == null ? null : Path.GetDirectoryName(Path.GetDirectoryName(Path.GetFullPath(folder)));
            var names = new string[list.GetArrayLength()];
            int n = 0;
            foreach (var value in list.EnumerateArray())
            {
                string which = $"its Look's Portraits' {who}'s {PaletteOrdinals[n]} portrait";
                string? name = value.ValueKind == JsonValueKind.String ? value.GetString() : null;
                if (!IsPortraitName(name))
                {
                    why = $"{which} is {value.GetRawText()}, not a name of 1 to {PortraitNameMost} letters, digits and _";
                    return null;
                }
                string? path = mod == null ? null : Path.Combine(mod, PortraitsFolder.Replace('/', Path.DirectorySeparatorChar),
                                                                 name + ".utexpt");
                if (path == null || !File.Exists(path))
                {
                    why = $"{which}, {name}, isn't in its mod's folder ({PortraitsFolder}/{name}.utexpt)";
                    return null;
                }
                names[n++] = name!;
            }
            return names;
        }

        /// <summary>(1.45.0) Whether a portrait's name is 1 to 64 of the letters a to z (either case), the digits and _.</summary>
        public static bool IsPortraitName(string? name)
        {
            if (string.IsNullOrEmpty(name) || name.Length > PortraitNameMost)
                return false;
            foreach (char c in name)
                if (!(c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' || c == '_'))
                    return false;
            return true;
        }

        /// <summary>(1.44.0) What a file's name in a job's folder can't hold, on any computer: a folder's mark or a drive's.</summary>
        static readonly char[] NotInAName = { '/', '\\', ':' };

        static string Bytes(long n) => n.ToString("N0", System.Globalization.CultureInfo.InvariantCulture);

        /// <summary>(1.43.0) A palette's place in a Look's Colors, in words.</summary>
        public static readonly string[] PaletteOrdinals = { "first", "second", "third", "fourth", "fifth" };

        /// <summary>(1.43.0) A Look's Colors' palettes for a man or a woman: a list of 1 to 5 palettes, each a list of 16
        /// "#RRGGBB" colors, the first "#000000" (see through). Null and why when it isn't.</summary>
        static int[][]? Palettes(JsonElement colors, string who, out string why)
        {
            why = "";
            if (!Has(colors, who, out var list) || list.ValueKind != JsonValueKind.Array || list.GetArrayLength() < 1
                || list.GetArrayLength() > MostPalettes)
            {
                why = $"its Look's Colors' {who} isn't a list of 1 to {MostPalettes} palettes";
                return null;
            }
            var palettes = new List<int[]>();
            foreach (var palette in list.EnumerateArray())
            {
                string which = $"its Look's Colors' {who}'s {PaletteOrdinals[palettes.Count]} palette";
                if (palette.ValueKind != JsonValueKind.Array || palette.GetArrayLength() != PaletteColors)
                {
                    why = $"{which} isn't a list of {PaletteColors} colors";
                    return null;
                }
                var colorsOf = new int[PaletteColors];
                int n = 0;
                foreach (var value in palette.EnumerateArray())
                {
                    int color = Color(value);
                    if (color < 0)
                    {
                        why = $"{which} has {value.GetRawText()}, not a color written \"#RRGGBB\"";
                        return null;
                    }
                    colorsOf[n++] = color;
                }
                if (colorsOf[0] != 0)
                {
                    why = $"{which} starts with a color that isn't \"#000000\" (the first color is see through)";
                    return null;
                }
                palettes.Add(colorsOf);
            }
            return palettes.ToArray();
        }

        /// <summary>(1.46.0) One of a job's art picks, `field` of `holder` (`which` its words): absent or null (0 and null),
        /// one of the game's (`first` to `last`, where `game` names them; a picture has none), or the name of a part list of
        /// its own in its mod's `artFolder` (`folder`, the job's own, is two folders inside the mod). False and why when it
        /// is neither.</summary>
        static bool ArtPick(JsonElement holder, string field, string which, string? game, int first, int last, string own,
                            string artFolder, string? folder, out int number, out string? name, out string why)
        {
            number = 0;
            name = null;
            why = "";
            if (!Has(holder, field, out var value) || value.ValueKind == JsonValueKind.Null)
                return true;
            if (game != null && value.ValueKind == JsonValueKind.Number && value.TryGetInt32(out int n) && n >= first
                && n <= last)
            {
                number = n;
                return true;
            }
            string? text = value.ValueKind == JsonValueKind.String ? value.GetString() : null;
            if (!IsPortraitName(text))
            {
                why = game == null
                    ? $"{which} is {value.GetRawText()}, not the name of {own} part list (1 to {PortraitNameMost} letters, "
                      + "digits and _)"
                    : $"{which} is {value.GetRawText()}, not {game} ({first} to {last}) or the name of {own} part list (1 to "
                      + $"{PortraitNameMost} letters, digits and _)";
                return false;
            }
            string? mod = folder == null ? null : Path.GetDirectoryName(Path.GetDirectoryName(Path.GetFullPath(folder)));
            string? path = mod == null ? null : Path.Combine(mod, artFolder.Replace('/', Path.DirectorySeparatorChar), text + ".utexpt");
            if (path == null || !File.Exists(path))
            {
                why = $"{which}, {text}, isn't in its mod's folder ({artFolder}/{text}.utexpt)";
                return false;
            }
            name = text;
            return true;
        }

        /// <summary>(1.55.0, from Read) A job's Look, if it has one: the game's generic job whose look it wears (0: none),
        /// its own colors, textures, frames and portraits. False and why in `problems` when it can't be used.</summary>
        static bool GameLook(JsonElement root, string? folder, List<string> problems, out ParsedLook parsed)
        {
            parsed = default;
            // (1.42.0) Its own look, if it has one.
            int lookLike = 0;
            var ownColors = new int[][]?[2];
            var ownTextures = new byte[][]?[2];
            var ownPortraits = new string[]?[2];
            var ownFrames = new int[2];
            string[] whose = { "Man", "Woman" };
            if (Has(root, "Look", out var look))
            {
                if (look.ValueKind != JsonValueKind.Object)
                {
                    problems.Add("its Look isn't a list of fields");
                    return false;
                }
                if (!Has(look, "Like", out var lookValue) || lookValue.ValueKind != JsonValueKind.Number
                    || !lookValue.TryGetInt32(out lookLike) || lookLike < FirstLike || lookLike > LastLike)
                {
                    problems.Add($"its Look's Like is {Raw(look, "Like")}, not one of the game's generic jobs ({FirstLike} to "
                                 + $"{LastLike})");
                    return false;
                }
                // (1.43.0) Its own colors, if it has any.
                if (Has(look, "Colors", out var colors))
                {
                    if (colors.ValueKind != JsonValueKind.Object || (!Has(colors, "Man", out _) && !Has(colors, "Woman", out _)))
                    {
                        problems.Add("its Look's Colors isn't a list of fields with a Man's or a Woman's palettes");
                        return false;
                    }
                    for (int woman = 0; woman < 2; woman++)
                    {
                        if (!Has(colors, whose[woman], out _))
                            continue;
                        ownColors[woman] = Palettes(colors, whose[woman], out string why);
                        if (ownColors[woman] == null)
                        {
                            problems.Add(why);
                            return false;
                        }
                    }
                }
                // (1.44.0) Its own textures, if it has any.
                if (Has(look, "Textures", out var textures))
                {
                    if (textures.ValueKind != JsonValueKind.Object
                        || (!Has(textures, "Man", out _) && !Has(textures, "Woman", out _)))
                    {
                        problems.Add("its Look's Textures isn't a list of fields with a Man's or a Woman's textures");
                        return false;
                    }
                    for (int woman = 0; woman < 2; woman++)
                    {
                        if (!Has(textures, whose[woman], out _))
                            continue;
                        ownTextures[woman] = TexturesOf(textures, whose[woman], folder, out string why);
                        if (ownTextures[woman] == null)
                        {
                            problems.Add(why);
                            return false;
                        }
                    }
                }
                // (1.54.0) The frames its own textures are drawn for, if it says.
                if (Has(look, "Frames", out var frames))
                {
                    if (frames.ValueKind != JsonValueKind.Object || (!Has(frames, "Man", out _) && !Has(frames, "Woman", out _)))
                    {
                        problems.Add("its Look's Frames isn't a list of fields with a Man's or a Woman's frames");
                        return false;
                    }
                    for (int woman = 0; woman < 2; woman++)
                    {
                        if (!Has(frames, whose[woman], out var kind))
                            continue;
                        if (kind.ValueKind != JsonValueKind.Number || !kind.TryGetInt32(out int frameKind)
                            || frameKind < Type1Frames || frameKind > Type2Frames)
                        {
                            problems.Add($"its Look's Frames' {whose[woman]} is {Raw(frames, whose[woman])}, not "
                                         + $"{Type1Frames} or {Type2Frames} (Type 1 or Type 2 frames)");
                            return false;
                        }
                        if (ownTextures[woman] == null)
                        {
                            string who = whose[woman].ToLowerInvariant();
                            problems.Add($"its Look's Frames give the {who}'s frames, but its Look's Textures give the {who} "
                                         + "no textures of its own to draw in them");
                            return false;
                        }
                        ownFrames[woman] = frameKind;
                    }
                }
                // (1.45.0) Its own portraits, if it has any.
                if (Has(look, "Portraits", out var portraits))
                {
                    if (portraits.ValueKind != JsonValueKind.Object
                        || (!Has(portraits, "Man", out _) && !Has(portraits, "Woman", out _)))
                    {
                        problems.Add("its Look's Portraits isn't a list of fields with a Man's or a Woman's portraits");
                        return false;
                    }
                    for (int woman = 0; woman < 2; woman++)
                    {
                        if (!Has(portraits, whose[woman], out _))
                            continue;
                        ownPortraits[woman] = PortraitsOf(portraits, whose[woman], folder, out string why);
                        if (ownPortraits[woman] == null)
                        {
                            problems.Add(why);
                            return false;
                        }
                    }
                }
            }
            parsed = new ParsedLook(lookLike, ownColors, ownTextures, ownPortraits, ownFrames);
            return true;
        }

        /// <summary>(1.55.0, from Read) A job's picks of its icon and its skillset's icon (the game's or its own; none for a
        /// skillset where `skillset` is null) and its pictures (its own or none). False and why in `problems` when one
        /// can't be used.</summary>
        static bool GameArt(JsonElement root, JsonElement? skillset, string? folder, List<string> problems, out JobArtPicks art)
        {
            art = JobArtPicks.None;
            string[] whose = { "Man", "Woman" };
            int commandSkillset = 0;
            string? commandOwn = null;
            if (!ArtPick(root, "Icon", "its Icon", "one of the game's generic jobs whose icon it shows", JobArt.FirstJob,
                         JobArt.LastJob, "its own icon's", JobArt.IconFolder, folder, out int iconJob, out string? iconOwn,
                         out string pickWhy)
                || skillset != null
                   && !ArtPick(skillset.Value, "Icon", "its Skillset's Icon", "one of the game's skillsets whose icon it shows",
                               JobArt.FirstSkillset, JobArt.LastSkillset, "its own icon's", JobArt.CommandFolder, folder,
                               out commandSkillset, out commandOwn, out pickWhy))
            {
                problems.Add(pickWhy);
                return false;
            }
            var pictureOwn = new string?[2];
            if (Has(root, "Pictures", out var pictures))
            {
                if (pictures.ValueKind != JsonValueKind.Object || (!Has(pictures, "Man", out _) && !Has(pictures, "Woman", out _)))
                {
                    problems.Add("its Pictures isn't a list of fields with a Man's or a Woman's picture");
                    return false;
                }
                for (int woman = 0; woman < 2; woman++)
                    if (!ArtPick(pictures, whose[woman], $"its Pictures' {whose[woman]}", null, 0, 0, "its own picture's",
                                 JobArt.PictureFolder, folder, out _, out pictureOwn[woman], out pickWhy))
                    {
                        problems.Add(pickWhy);
                        return false;
                    }
            }
            art = new JobArtPicks(iconJob, iconOwn, commandSkillset, commandOwn, pictureOwn);
            return true;
        }

        /// <summary>(1.55.0, from Read) A skillset's Words: its name and description. False and why in `problems` when
        /// they can't be used.</summary>
        static bool SkillsetWords(JsonElement skillset, List<string> problems, out string name, out string description)
        {
            name = description = "";
            if (!Has(skillset, "Words", out var setWords) || setWords.ValueKind != JsonValueKind.Object)
            {
                problems.Add("its Skillset has no Words");
                return false;
            }
            string? setName = Word(setWords, "Name", NameMost);
            if (setName == null)
            {
                problems.Add($"its Skillset's Words' Name is {Raw(setWords, "Name")}, not text of 1 to {NameMost} characters");
                return false;
            }
            string? setDescription = Word(setWords, "Description", DescriptionMost);
            if (setDescription == null)
            {
                problems.Add($"its Skillset's Words' Description is {Raw(setWords, "Description")}, not text of 1 to "
                             + $"{DescriptionMost} characters with up to two line breaks");
                return false;
            }
            name = setName;
            description = setDescription;
            return true;
        }

        /// <summary>(1.55.0) The game's Dark Knight's Skillset's Names: left out, null or empty, none; else a list, each
        /// with an Ability (one of the game's skillset 224's, DarkAbilities), a Name and a Description as a job's Words
        /// have them, no ability twice. Null and why in `problems` when it isn't.</summary>
        static AbilityName[]? NamesOf(JsonElement skillset, List<string> problems)
        {
            if (!Has(skillset, "Names", out var value) || value.ValueKind == JsonValueKind.Null)
                return Array.Empty<AbilityName>();
            string Bad(string what) => $"its Skillset's Names {what}: a list, each with an Ability (one of the game's skillset "
                                       + $"{DarkSkillset}'s: {string.Join(", ", DarkAbilities)}), a Name (1 to {NameMost} characters) "
                                       + $"and a Description (1 to {DescriptionMost} characters with up to two line breaks)";
            if (value.ValueKind != JsonValueKind.Array || value.GetArrayLength() > DarkAbilities.Length)
            {
                problems.Add(Bad(value.ValueKind != JsonValueKind.Array ? "aren't a list" : $"are {value.GetArrayLength()}"));
                return null;
            }
            var names = new List<AbilityName>();
            foreach (var item in value.EnumerateArray())
            {
                if (item.ValueKind != JsonValueKind.Object || !Has(item, "Ability", out var ability)
                    || ability.ValueKind != JsonValueKind.Number || !ability.TryGetInt32(out int number)
                    || Array.IndexOf(DarkAbilities, number) < 0)
                {
                    problems.Add(Bad(item.ValueKind != JsonValueKind.Object ? "hold something that isn't a list of fields"
                                     : $"name the ability {Raw(item, "Ability")}"));
                    return null;
                }
                if (names.Exists(n => n.Ability == number))
                {
                    problems.Add(Bad($"name the ability {number} twice"));
                    return null;
                }
                string? name = Word(item, "Name", NameMost), description = Word(item, "Description", DescriptionMost);
                if (name == null || description == null)
                {
                    problems.Add(Bad($"give the ability {number} {(name == null ? "a Name" : "a Description")} that can't be used"));
                    return null;
                }
                names.Add(new AbilityName(number, name, description));
            }
            return names.ToArray();
        }
        /// <summary>A job from its file's text; null when it can't be used, why in problems.</summary>
        public static ModJob? Read(string modId, string modName, string text, List<string> problems, string? folder = null)
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
                string? name = Has(root, "Name", out _) ? Word(root, "Name", NameMost) : null;
                if (name == null)
                {
                    problems.Add($"its Name is {Raw(root, "Name")}, not text of 1 to {NameMost} characters");
                    return null;
                }
                if (!Has(root, "Like", out var likeValue) || likeValue.ValueKind != JsonValueKind.Number
                    || !likeValue.TryGetInt32(out int like) || like < FirstLike || like > LastLike)
                {
                    problems.Add($"its Like is {Raw(root, "Like")}, not one of the game's generic jobs ({FirstLike} to {LastLike})");
                    return null;
                }
                byte[]? record = null;
                if (Has(root, "Record", out var values) && values.ValueKind == JsonValueKind.Array
                    && values.GetArrayLength() == RecordBytes)
                {
                    record = new byte[RecordBytes];
                    int n = 0;
                    foreach (var b in values.EnumerateArray())
                    {
                        if (b.ValueKind != JsonValueKind.Number || !b.TryGetInt32(out int value) || value < 0 || value > 255)
                        {
                            record = null;
                            break;
                        }
                        record[n++] = (byte)value;
                    }
                }
                if (record == null)
                {
                    problems.Add($"its Record isn't a list of {RecordBytes} whole numbers from 0 to 255");
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
                // (1.47.0) Its own words on Job Summary: left out, or null, and Job Summary shows its Description.
                string? summary = null;
                if (Has(words, "Summary", out var summaryValue) && summaryValue.ValueKind != JsonValueKind.Null)
                {
                    summary = SummaryWords(summaryValue);
                    if (summary == null)
                    {
                        problems.Add($"its Words' Summary is {Raw(words, "Summary")}, not text of 1 to {SummaryMost} characters");
                        return null;
                    }
                }
                // (1.55.0) The game's own job it is, if it is one.
                int game = 0;
                if (Has(root, "Game", out var gameValue) && gameValue.ValueKind != JsonValueKind.Null
                    && (gameValue.ValueKind != JsonValueKind.Number || !gameValue.TryGetInt32(out game)
                        || game != DarkKnight && game != OnionKnight))
                {
                    problems.Add($"its Game is {Raw(root, "Game")}, not {DarkKnight} (the game's Dark Knight) or {OnionKnight} "
                                 + "(the game's Onion Knight)");
                    return null;
                }
                // (1.55.1, Zodi's words of 15 November) The game's Onion Knight's words for a unit whose Onion Knight is level
                // 8 (every job mastered): its Words' MasteredDescription, left out or null, and Job Summary shows its
                // Description at every level. Only the game's Onion Knight has a level 8 the game gives so.
                string? masteredDescription = null;
                if (Has(words, "MasteredDescription", out var masteredValue) && masteredValue.ValueKind != JsonValueKind.Null)
                {
                    if (game != OnionKnight)
                    {
                        problems.Add("its Words' MasteredDescription can't be given: only the game's Onion Knight (Game "
                                     + $"{OnionKnight}) has words for its level 8");
                        return null;
                    }
                    masteredDescription = Word(words, "MasteredDescription", DescriptionMost);
                    if (masteredDescription == null)
                    {
                        problems.Add($"its Words' MasteredDescription is {Raw(words, "MasteredDescription")}, not text of 1 to "
                                     + $"{DescriptionMost} characters with up to two line breaks");
                        return null;
                    }
                }
                // (1.55.1, Zodi's word of 05:49) Its whole Job Summary for its level 8: left out or null, and Job Summary
                // shows its MasteredDescription there (or its Summary, at every level, where it has none).
                string? masteredSummary = null;
                if (Has(words, "MasteredSummary", out var masteredSummaryValue)
                    && masteredSummaryValue.ValueKind != JsonValueKind.Null)
                {
                    if (game != OnionKnight)
                    {
                        problems.Add("its Words' MasteredSummary can't be given: only the game's Onion Knight (Game "
                                     + $"{OnionKnight}) has words for its level 8");
                        return null;
                    }
                    masteredSummary = SummaryWords(masteredSummaryValue);
                    if (masteredSummary == null)
                    {
                        problems.Add($"its Words' MasteredSummary is {Raw(words, "MasteredSummary")}, not text of 1 to "
                                     + $"{SummaryMost} characters");
                        return null;
                    }
                }
                // (1.48.0) What it needs: left out, null or empty, and it is open to every unit.
                JobNeed[]? needs = null;
                if (Has(root, "Needs", out var needsValue) && needsValue.ValueKind != JsonValueKind.Null)
                {
                    if (game != 0 && (needsValue.ValueKind != JsonValueKind.Array || needsValue.GetArrayLength() > 0))
                    {
                        problems.Add($"its Needs can't be given: the game's own rule opens the game's {GameJobName(game)}");
                        return null;
                    }
                    needs = NeedsOf(needsValue, name, out string needsWhy);
                    if (needs == null)
                    {
                        problems.Add(needsWhy);
                        return null;
                    }
                }
                // (1.55.0) The game's Onion Knight learns no abilities: no Skillset, its record's skillset none.
                if (game == OnionKnight)
                {
                    if (Has(root, "Skillset", out var noSkillset) && noSkillset.ValueKind != JsonValueKind.Null)
                    {
                        problems.Add("its Skillset can't be given: the game's Onion Knight learns no abilities");
                        return null;
                    }
                    if (!GameLook(root, folder, problems, out var onionLook) || !GameArt(root, null, folder, problems, out var onionArt))
                        return null;
                    record[0] = 0;
                    return new ModJob(modId, modName, name, like, record, wordName, description, 0, Array.Empty<int>(),
                                      Array.Empty<int>(), "", "", null, onionLook.Like, onionLook.Colors, onionLook.Textures,
                                      onionLook.Portraits, onionArt, summary, needs, onionLook.Frames, game,
                                      masteredDescription: masteredDescription, masteredSummary: masteredSummary);
                }
                if (!Has(root, "Skillset", out var skillset) || skillset.ValueKind != JsonValueKind.Object)
                {
                    problems.Add("it has no Skillset");
                    return null;
                }
                // (1.55.0) The game's Dark Knight's skillset is the game's own 224: its words, its icon and the names of its
                // abilities that have none.
                if (game == DarkKnight)
                {
                    if (Has(skillset, "Actions", out _) || Has(skillset, "Others", out _))
                    {
                        problems.Add($"its Skillset's Actions and Others can't be given: the game's Dark Knight's abilities are "
                                     + $"the game's own skillset {DarkSkillset}");
                        return null;
                    }
                    if (!Has(skillset, "Like", out var darkLike) || darkLike.ValueKind != JsonValueKind.Number
                        || !darkLike.TryGetInt32(out int darkSkillsetLike) || darkSkillsetLike < FirstSkillset
                        || darkSkillsetLike > LastSkillset)
                    {
                        problems.Add($"its Skillset's Like is {Raw(skillset, "Like")}, not one of the generic jobs' skillsets "
                                     + $"({FirstSkillset} to {LastSkillset})");
                        return null;
                    }
                    if (!SkillsetWords(skillset, problems, out string darkName, out string darkDescription))
                        return null;
                    var abilityNames = NamesOf(skillset, problems);
                    if (abilityNames == null)
                        return null;
                    if (!GameLook(root, folder, problems, out var darkLook) || !GameArt(root, skillset, folder, problems, out var darkArt))
                        return null;
                    record[0] = DarkSkillset;
                    return new ModJob(modId, modName, name, like, record, wordName, description, darkSkillsetLike,
                                      Array.Empty<int>(), Array.Empty<int>(), darkName, darkDescription, null, darkLook.Like,
                                      darkLook.Colors, darkLook.Textures, darkLook.Portraits, darkArt, summary, needs,
                                      darkLook.Frames, game, abilityNames);
                }
                if (!Has(skillset, "Like", out var setLike) || setLike.ValueKind != JsonValueKind.Number
                    || !setLike.TryGetInt32(out int skillsetLike) || skillsetLike < FirstSkillset || skillsetLike > LastSkillset)
                {
                    problems.Add($"its Skillset's Like is {Raw(skillset, "Like")}, not one of the generic jobs' skillsets "
                                 + $"({FirstSkillset} to {LastSkillset})");
                    return null;
                }
                int[]? actions = ActionList(skillset, out var actionNames);
                if (actions == null)
                {
                    problems.Add($"its Skillset's Actions aren't a list of 1 to {MostActions} different action abilities (whole "
                                 + $"numbers from 1 to {FirstOther - 1}, or the names of the mod's own abilities)");
                    return null;
                }
                int[]? others = Abilities(skillset, "Others", 0, MostOthers, FirstOther, LastAbility);
                if (others == null)
                {
                    problems.Add($"its Skillset's Others aren't a list of up to {MostOthers} different reaction, support or "
                                 + $"movement abilities (whole numbers from {FirstOther} to {LastAbility})");
                    return null;
                }
                if (!SkillsetWords(skillset, problems, out string setName, out string setDescription))
                    return null;
                if (!GameLook(root, folder, problems, out var parsed) || !GameArt(root, skillset, folder, problems, out var art))
                    return null;
                return new ModJob(modId, modName, name, like, record, wordName, description, skillsetLike, actions, others,
                                  setName, setDescription, actionNames, parsed.Like, parsed.Colors, parsed.Textures,
                                  parsed.Portraits, art, summary, needs, parsed.Frames);
            }
        }
    }
}
