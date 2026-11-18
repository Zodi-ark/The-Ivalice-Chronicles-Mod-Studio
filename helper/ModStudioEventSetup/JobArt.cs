// Mod Studio Framework: (1.46.0) a job's own icons and pictures. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// The road's step 5, its third part (Zodi's pick of 11 November: "Job screen picture and icons"), measured in
// dev/research/sidequests/job_art.py (claude/job-sprites-research.md says what it means).
//
// A job's art is four pictures the game names from its tables: its icon (the small job symbol: the Job row's
// TexturePartsIndex, a number printed into `j_%03d_uitx` by one routine, 0x29B054), its skillset's icon (the JobCommand
// row's IconId, printed into `jc_%03d_uitx` by one routine, 0xFBF30, through 0xFBF9C, which lets only the game's 1 to 24
// through, or through the records 0xFB8E4 fills), and its two job screen pictures, a man's and a woman's (the Job row's
// jobtype+Id names a JobType row whose two keys name rows of the Icon table: the part lists under ui/ffto/icon/; read by
// one routine, 0xFBEB8, which also says whether to show the picture: on the job screen only for the game's 20 generic
// jobs).
//
// Zodi's word of 12 November: "What ever the modder selects for the jobs icon, skillset icon, or it's job screen
// pictures, male and female, selected from the game if they do not want to make their own for each icon or pictures";
// then, his change of mind the same evening: "The modder can pick either their own files or one of the game's for the
// job icon and skillset icon but not for the man art or woman art. The modder should be able to choose their own art for
// male and or female or no art for the male and or female."; and asked where a job has no art of its own: "No picture
// there either" (no art is no picture anywhere: the job screen, the equipment screen, Combat Sets).
//
// So a job's file may give its icon (`Icon`) and its skillset's icon (`Skillset`'s `Icon`) as either one of the game's
// (the game's generic job whose icon it shows, 74 to 93; the game's skillset whose icon its skillset shows, 5 to 24) or
// its own (the name of a part list in its mod, laid out as the game's and naming its texture); an icon it doesn't give
// is its Like's, as before. Its two pictures (`Pictures`' `Man` and `Woman`) are each its own part list or none; a job
// shows no picture for a sex it gives no art for, the job screen's and every other. None of it needs sprites of its
// own. Only the Enhanced look is supported (his word, 12 November).
//
// The game's icons a job picks are rows only: its Job row's TexturePartsIndex and its skillset's JobCommand row's IconId
// are the picked one's (JobRoom.JobRow, JobRoom.CommandRow). Its own icon and its skillset's own icon are numbered as the
// job (TexturePartsIndex and IconId the job's own number, past the game's numbers; the other mod numbers Dark Knight's
// the same way, 160), and the framework names their part lists for those numbers (JobArtHooks: the icon routine, the
// skillset icon's name routine, and the skillset icon routine, whose bound would turn the number into the empty icon).
// Every job's pictures are answered at the picture routine (JobArtHooks), its jobtype+Id left as its Like's (the game
// also takes two jobs as one, clears the units' "new" marks and tells a Chemist by it): its own with a row of the Icon
// table of the framework's (WithPictureRows: keyed PictureFirst plus twice the job, the woman's the next), shown on the
// job screen as the game shows its generic jobs' pictures; none with the key 0, which the game shows nowhere.
//
// Each routine is found by a call of it, and where it doesn't start as the game's own (another mod's hook), taken where
// the game's program file has it (as SpriteTextures.cs finds its routines). The picture routine's hook is made wherever a
// mod gives a job; the icons' only where a job gives an icon of its own.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Text;

namespace ModStudioEventSetup
{
    /// <summary>(1.46.0) A job's picks of its icon and its skillset's icon (each the game's, a job's or a skillset's
    /// number, or its own, a part list's name, or neither: its Like's) and of its two job screen pictures (each its own
    /// part list's name, or none: no picture).</summary>
    public sealed class JobArtPicks
    {
        /// <summary>The game's generic job whose icon it shows (74 to 93), or 0.</summary>
        public int IconJob { get; }
        /// <summary>Its own icon's part list's name, or null.</summary>
        public string? IconOwn { get; }
        /// <summary>The game's skillset whose icon its skillset shows (5 to 24), or 0.</summary>
        public int CommandSkillset { get; }
        /// <summary>Its skillset's own icon's part list's name, or null.</summary>
        public string? CommandOwn { get; }
        /// <summary>Its own pictures' part lists' names, [0] the man's, [1] the woman's, or null for no picture.</summary>
        public string?[] PictureOwn { get; }

        public static readonly JobArtPicks None = new JobArtPicks(0, null, 0, null, new string?[2]);

        public JobArtPicks(int iconJob, string? iconOwn, int commandSkillset, string? commandOwn, string?[] pictureOwn)
        {
            IconJob = iconJob;
            IconOwn = iconOwn;
            CommandSkillset = commandSkillset;
            CommandOwn = commandOwn;
            PictureOwn = pictureOwn;
        }
    }

    public static partial class JobArt
    {
        /// <summary>The game tables: the Icon table (its sheet number, a row's bytes, where its path is from the row's
        /// start and its part), the Job row's TexturePartsIndex and the JobCommand row's IconId.</summary>
        public const int IconSheet = 0x76, IconRowBytes = 0x10, IconComment = 4, IconPathAt = 8, IconPartAt = 0xC;
        public const int JobIconAt = 0x2C, CommandIconAt = 4;
        /// <summary>A job's own picture's key in the Icon table: PictureFirst plus twice the job, the woman's the next.</summary>
        public const int PictureFirst = 0x10000;
        /// <summary>The game's jobs and skillsets a job may pick the icons of.</summary>
        public const int FirstJob = 74, LastJob = 93, FirstSkillset = 5, LastSkillset = 24;
        /// <summary>Where a job's own art's part lists are in its mod, and the names the framework hands the game.</summary>
        public const string IconFolder = "FFTIVC/data/enhanced/ui/ffto/icon/job/textureparts";
        public const string CommandFolder = "FFTIVC/data/enhanced/ui/ffto/icon/job_comm/textureparts";
        public const string PictureFolder = "FFTIVC/data/enhanced/ui/ffto/icon/job_visual/textureparts";
        public const string IconNamePrefix = "UITextureParts://ui/ffto/icon/job/textureparts/";
        public const string CommandNamePrefix = "UITextureParts://ui/ffto/icon/job_comm/textureparts/";
        public const string PicturePathPrefix = "job_visual/textureparts/";
        /// <summary>The most bytes the callers' buffers hold: the icon routine's own (0x104) and the skillset icon
        /// routine's callers' (0x100).</summary>
        public const int IconBytes = 0x104, CommandBytes = 0x100;

        public static int PictureKey(int job, int woman) => PictureFirst + job * 2 + woman;

        /// <summary>The names the framework hands the game, each ended by a 0: a job's own icon's and its skillset's own
        /// icon's (as their routines write the game's, without the part list's ending), and a picture's path in the Icon
        /// table (under ui/ffto/icon/, with its ending, as the game's rows).</summary>
        public static byte[] IconName(string name) => Encoding.ASCII.GetBytes(IconNamePrefix + name + "\0");
        public static byte[] CommandName(string name) => Encoding.ASCII.GetBytes(CommandNamePrefix + name + "\0");
        public static string PicturePath(string name) => PicturePathPrefix + name + ".utexpt";

        /// <summary>The places found, each from the program's start: the four routines and the box loader.</summary>
        public sealed class Sites
        {
            public int Picture { get; internal set; } = -1;
            public int Icon { get; internal set; } = -1;
            public int BoxLoad { get; internal set; } = -1;
            public int CommandName { get; internal set; } = -1;
            public int CommandIcon { get; internal set; } = -1;
            public List<string> Missing { get; } = new List<string>();
            public bool Ok => Missing.Count == 0;
        }

        /// <summary>Each routine by a call of it (found once), starting as the game's own in `image` or in `file` (its
        /// program file, where another mod has hooked it); the box loader by the icon routine's call of it.</summary>
        public static Sites Find(ReadOnlySpan<byte> image, List<Section> sections, ProgramFile? file)
        {
            var sites = new Sites();
            sites.Picture = RoutineOf(image, sections, file, PictureCall, PictureOwn, "the picture routine", sites.Missing);
            sites.Icon = RoutineOf(image, sections, file, IconCall, IconOwn, "the icon routine", sites.Missing);
            sites.CommandName = RoutineOf(image, sections, file, CommandNameCall, CommandNameOwn, "the skillset icon's name routine",
                                          sites.Missing);
            sites.CommandIcon = RoutineOf(image, sections, file, CommandIconCall, CommandIconOwn, "the skillset icon routine",
                                          sites.Missing);
            if (sites.Icon >= 0)
            {
                int call = sites.Icon + BoxLoadCallAt;
                if (call + 5 > image.Length || image[call] != 0xE8)
                    sites.Missing.Add("the box loader (the icon routine doesn't call it where it should)");
                else
                    sites.BoxLoad = SpriteTextures.Routine(image, call, BoxLoadOwn, "the box loader", sites.Missing, file);
            }
            return sites;
        }

        static int RoutineOf(ReadOnlySpan<byte> image, List<Section> sections, ProgramFile? file, (string Pattern, int At) call,
                             string own, string what, List<string> missing)
        {
            int at = SpriteTextures.Once(image, sections, call.Pattern, $"a call of {what}", missing);
            return at < 0 ? -1 : SpriteTextures.Routine(image, at + call.At, own, what, missing, file);
        }

        /// <summary>What the framework answers, from the jobs given: the part lists of the jobs' own icons by number (the
        /// job's), of their skillsets' own icons by number (the job's) and by skillset, and every job's pictures (by job:
        /// [0] the man's, [1] the woman's, each its own key in the Icon table, or 0 for none).</summary>
        public sealed class Plan
        {
            public Dictionary<int, string> Icons { get; } = new Dictionary<int, string>();
            public Dictionary<int, string> Commands { get; } = new Dictionary<int, string>();
            public Dictionary<int, string> CommandsBySkillset { get; } = new Dictionary<int, string>();
            public Dictionary<int, int[]> Pictures { get; } = new Dictionary<int, int[]>();
            public Dictionary<int, string> Whose { get; } = new Dictionary<int, string>();
            public Dictionary<int, int> SkillsetJob { get; } = new Dictionary<int, int>();
            public bool Empty => Icons.Count == 0 && Commands.Count == 0 && Pictures.Count == 0;
        }

        public static Plan PlanOf(IList<JobRoom.Given> given)
        {
            var plan = new Plan();
            foreach (var g in given)
            {
                var art = g.Job.Art;
                if (art.IconOwn != null)
                    plan.Icons[g.Number] = art.IconOwn;
                if (art.CommandOwn != null)
                {
                    plan.Commands[g.Number] = art.CommandOwn;
                    plan.CommandsBySkillset[g.Skillset] = art.CommandOwn;
                }
                var keys = new int[2];
                for (int woman = 0; woman < 2; woman++)
                    keys[woman] = art.PictureOwn[woman] != null ? PictureKey(g.Number, woman) : 0;
                plan.Pictures[g.Number] = keys;
                plan.Whose[g.Number] = g.Job.Who;
                if (g.Skillset != 0)                           // (1.55.0) the game's Onion Knight has no skillset
                    plan.SkillsetJob[g.Skillset] = g.Number;
            }
            return plan;
        }

        /// <summary>The key the picture routine answers a job's record with (`man`: the record's sex byte's top bit): the
        /// job's own picture's, or 0 for none; null where the job isn't one of the plan's (the game's own answer).</summary>
        public static int? PictureFor(Plan plan, int job, bool man)
            => plan.Pictures.TryGetValue(job, out var keys) ? keys[man ? 0 : 1] : null;

        /// <summary>A job's row as the picture routine leaves it: the framework's key (its own picture's, or 0, shown
        /// nowhere), and for its own picture on the job screen (`asked`: the routine's flag kind set) the flag cleared so it
        /// is shown; any other flag as the game made it.</summary>
        public static void Answer(Span<byte> answer, int key, bool asked)
        {
            BinaryPrimitives.WriteInt32LittleEndian(answer, key);
            if (asked && key > 0)
                answer[4] = 0;
        }

        // --- the Icon table -----------------------------------------------------------------------------------------

        /// <summary>A row of the Icon table naming a job's own picture: no DLC flags, an empty comment, its path (from the
        /// row's start) and the first part, its words after the row's fixed part.</summary>
        public static byte[] PictureRow(string name)
        {
            byte[] path = Encoding.ASCII.GetBytes(PicturePath(name));
            int empty = IconRowBytes, pathAt = empty + 1;
            var row = new byte[(pathAt + path.Length + 1 + 3) & ~3];
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(IconComment), empty);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(IconPathAt), pathAt);
            path.CopyTo(row, pathAt);
            return row;
        }

        /// <summary>The loaded Icon table with a row for each own picture the framework answers (Given.Pictures), or null
        /// and why; `rows` how many. A row another mod has at a key is kept, said.</summary>
        public static byte[]? WithPictureRows(ReadOnlySpan<byte> table, IEnumerable<JobRoom.Given> given, List<string> said,
                                              out string why, out int rows)
        {
            rows = 0;
            if (Nxd.Keys(table) != 1)
            {
                why = "it isn't a table of one key";
                return null;
            }
            var added = new List<NewRow>();
            foreach (var g in given)
                for (int woman = 0; woman < 2; woman++)
                {
                    string? name = g.Job.Art.PictureOwn[woman];
                    if (name == null || !g.Pictures[woman])
                        continue;
                    int key = PictureKey(g.Number, woman);
                    if (Nxd.Find(table, new[] { key }) >= 0)
                    {
                        said.Add($"{g.Job.Who}'s {(woman == 0 ? "man's" : "woman's")} picture keeps the Icon row another mod gives "
                                 + $"it ({key}).");
                        continue;
                    }
                    added.Add(new NewRow(new[] { key }, PictureRow(name)));
                }
            if (added.Count == 0)
            {
                why = "";
                return table.ToArray();
            }
            var made = Nxd.WithRows(table, added, out why);
            if (made != null)
                rows = added.Count;
            return made;
        }

        /// <summary>The Icon table's line, once its rows are written.</summary>
        public static string PictureRowsLine(int rows)
            => $"Icon: the mods' jobs' own pictures' {rows} row{(rows == 1 ? "" : "s")} written.";

        // --- the log ------------------------------------------------------------------------------------------------

        /// <summary>What of a job's art its line says (nothing where it gives none).</summary>
        public static string ArtOf(JobRoom.Given g)
        {
            var art = g.Job.Art;
            var parts = new List<string>();
            if (g.IconOwn)
                parts.Add("its own icon");
            else if (art.IconJob > 0)
                parts.Add($"the game's job {art.IconJob}'s icon");
            if (g.CommandOwn)
                parts.Add("its skillset's own icon");
            else if (art.CommandSkillset > 0)
                parts.Add($"the game's skillset {art.CommandSkillset}'s icon");
            if (g.Pictures[0] && g.Pictures[1])
                parts.Add("pictures of its own");
            else if (g.Pictures[0])
                parts.Add("the man's picture of its own");
            else if (g.Pictures[1])
                parts.Add("the woman's picture of its own");
            if (parts.Count == 0)
                return "";
            string last = parts[^1];
            parts.RemoveAt(parts.Count - 1);
            return parts.Count == 0 ? $" It shows {last}." : $" It shows {string.Join(", ", parts)} and {last}.";
        }

        /// <summary>What the log says the first time the game is given a job's own icon, skillset icon or picture.</summary>
        public static string FirstLine(string what, string whose)
            => $"the game was given a job's own {what} for the first time ({whose}).";

        /// <summary>What the log says where the hooks can't be made: a job's own icon and its skillset's own icon not
        /// marked, their rows name their Likes'; no picture answered; the game's icons a job picks are its rows.</summary>
        public static string NotLine(string why)
            => $"the jobs' own icons and pictures can't be given: {why}. A job with an icon of its own shows its Like's and a "
               + "skillset with an icon of its own its Like's; the game's icons a job picks are still shown. Each job's "
               + "pictures are as they were before: none on the job screen, its Like's elsewhere.";
    }
}
