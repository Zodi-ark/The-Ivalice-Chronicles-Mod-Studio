// Mod Studio Framework: what opens a mod's job (1.48.0; the Job Tree's first
// step, Zodi's order of 13 November: "the Job Tree and Job Summary for our new
// jobs", its design signed off the same night: a job's file says what it
// needs, the framework tests it). Part of The Ivalice Chronicles Mod Studio,
// GPL-3.0.
//
// What the game does, measured in his program (17 September 2026, read as
// data; dev/research/sidequests/job_tree.py and job_needs.py hold each place
// to its bytes):
//
// - What opens one of the game's jobs is a table inside the program (19 rows,
//   0x67F390, read by 0x348684 into three bytes of bits a unit: the menu's
//   record of a unit keeps them at + 0x78, the first bit its first job's, then
//   one for each job after). A mod's job is in no row and has no bit.
// - The lister (0x2864AC) marks a job that isn't open 0x4000 above its number
//   (locked), or 0x2000 (not to be seen) where no unit of the party has it
//   open; the job screen's filling (0x368424) writes that into the place's
//   record (+ 0x84: 0 open, 1 locked, 2 not to be seen), and everything the
//   screen does with a job that isn't open goes by that record: its place's
//   look (0x131E4C), "???" for its name (0x12EC5C), and confirm on it opening
//   the window of what it needs (the screen's state 6) where an open job's
//   opens its two buttons (0x13100E, and 0x12F7F4 coming back from Job
//   Progress).
// - That window (0x1321FC) reads the game table GeneralJob (sheet 0xBD) by the
//   slot of the job at the cursor (0x2B8F18, then the generic getter
//   0x3DBC74): up to six needed jobs by their slots (+ 0x10) with their levels
//   (+ 0x18). For each it looks through the screen's 19 places for the job
//   with that slot (0x2B8F18 again) and shows that place's record: its icon,
//   its name ("???" and a question mark where it isn't to be seen), the unit's
//   level in it, or "Locked" where it isn't open. A needed job that is on none
//   of the 19 places gets a row with a level and nothing else. The game's own
//   screen always shows all of a unit's jobs, so it never meets that; the
//   framework's rows show three rows of more.
//
// So, what the framework does:
//
// - **The test is the framework's own** (Plan.Open): a job is open to a unit
//   that has every job it needs open, at the level asked or more. One of the
//   game's jobs is open by the unit's own bits and its level is the unit's
//   (the menu's record, + 0xBD: a nibble a slot); one of the mod's own is open
//   by this same test and its level is what the framework keeps of it
//   (JobProgress.Level). The job a unit is in is open to it. Nothing is asked
//   of a unit's sex: a job that needs the Bard is a man's and one that needs
//   the Dancer a woman's, since only they have those open.
// - **Where the framework lists a job** (JobScreen.Listed) it marks it as the
//   game marks its own: locked, or not to be seen where no unit of the party
//   has it open (Mark). The filling and the screen then treat it as one of the
//   game's.
// - **The lists of second skillsets and of other abilities** (JobRoom's
//   SecondList and OthersList) take a job's only while it is open to the unit
//   (the native code asks, through JobHooks).
// - **The window of what a job needs**: GeneralJob is given a row for each of
//   the mods' jobs as it loads (WithRows: key OwnFirst plus the job's number,
//   its needs by what the window's own search finds them by). In the window
//   the two askings of a job's slot are the framework's (JobRoom's Same): a
//   mod's job answers OwnFirst plus its number, any other job its slot as
//   before. And around the window's call the screen's 19 records are, for
//   that call alone, the cursor's own and one for each needed job (the
//   place's own where the job is on one of the places shown, else made from
//   the Job table's row, the unit's level and the mark; JobScreen.Needs), so
//   every need is found whatever rows are shown.
//
// (1.55.0, his second answer of 14 November: "the game's own rule, less the kills") The game's own Dark Knight and Onion
// Knight a mod gives are opened by the framework's test as a mod's job is, with what the program's own rows of them ask
// (dark_onion.py's REQUIRED_MORE, which the game's routine never reads): Onion Knight the Squire and the Chemist at level
// 6; Dark Knight the Geomancer, the Dragoon, the Samurai and the Ninja at level 8, and the Knight and the Black Mage
// mastered (every place of the job's skillset learned, as the game's routine asks of the two: JOBS_MASTERED). Job Progress
// shows a mastered job's need as level 8, the most the game's window shows. A mod's job that needs the game's Dark Knight
// or Onion Knight of its mod (by its Name) needs it open by that test, at the level the unit has in it (the unit's own
// rows).
//
// (1.55.1, Zodi's test 122: "on the Level requirements menu ... it should say Mastered for Knight and Black Mages Required
// Level column") The window's Required Level cell is a text of the UI table's (1012, "Lv. <num=lnum0>" in English: its
// layout's own, ffto_jobchange_ver03's JobcConditionRow, no other box uses it) handed the need's level from GeneralJob's
// row (0x132569: one at least, no most); its Current Level cell is 1004 handed the record's level, shown red where it is
// less than the need's. So a mastered need's level in GeneralJob is MasteredShown (9, a level no job has); the window's
// record of that job, for the window's call alone, has 9 where the unit has mastered it (JobScreen.Needs), so the cell
// isn't red; and both texts, as the UI table loads, show the language's own "Mastered" (UI 1077) for 9 and themselves
// otherwise (WithMasteredWords), in the game's own way of choosing words by a number (<if([lnum0==9],...,...)>, as the
// game's job levels' text 3883 does for 8). 1004 is the job change screen's job level too: no level there is 9.
//
// (1.55.2, Zodi's words on test 123: "our job tree (Job Progress) still says level 8 for Knight and Black Mage" and "can
// new jobs could also get the Mastered jobs requirement like Dark Knight does") A mod's job's file may ask one of the
// game's generic jobs mastered (JobFile's Needs, "Level": "Mastered"): the same test, window and GeneralJob row as the
// game's Dark Knight's two. On Job Progress the small icon of a job needed mastered shows the game's own mark of a job
// mastered under it in place of "Lv. 8" (the label's LvMaster: the stars the job screen shows over a job mastered,
// JobTreeLines.cs), green only where the unit has mastered the job.
//
// (1.56.0, Zodi's answer of 16 November: "yes a job also be able to need one of your own mod's jobs mastered") A job of
// the same mod may be asked mastered: every place of its own skillset learned (its Actions the first places, its Others
// from MostActions on; a place it leaves empty counts as learned, as the game counts its own: Plan.OwnPlaces), read from
// the unit's learned row in that job (JobProgress.Row: the record's own row where it is the loaded job, else what is
// kept for the unit). The window's two cells say "Mastered" for it and Job Progress's label of its line shows the stars,
// as for one of the game's jobs. The game's Dark Knight or Onion Knight a mod gives, asked mastered, is asked at level 8
// (the Onion Knight learns no abilities; the game's own Dark Knight rule asks levels of the jobs it needs), said.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Text;

namespace ModStudioEventSetup
{
    public static class JobNeeds
    {
        /// <summary>The game table of what a job needs (GeneralJob): its sheet, a row's fixed part and its fields: its
        /// comment, the JP each level needs, the needed jobs, their levels, where each level's label stands on Job
        /// Progress (each a distance from the row's start, then how many), the cursor's 16 directions (four bytes
        /// each, then 16 of one byte) and whether the job starts not to be seen.</summary>
        public const int Sheet = 0xBD, RowBytes = 0x7C, CommentAt = 4, ExpAt = 8, NeedsAt = 0x10, LevelsAt = 0x18,
                         LabelsAt = 0x20, DirectionsAt = 0x28, DirectionBytesAt = 0x68, Directions = 16, StartsUnseenAt = 0x78;
        /// <summary>A direction that leads nowhere, as the game's own rows have it; the JP table's levels.</summary>
        public const int NoDirection = 20, ExpLevels = 9;
        /// <summary>(1.55.1) The level a mastered need is given in GeneralJob, and the window's record of a job the unit has
        /// mastered for the window's call: a level no job has, which the window's two texts show as "Mastered".</summary>
        public const int MasteredShown = 9;
        /// <summary>(1.55.1) The UI table (its sheet; a row's fixed part: a word, then its text's distance counted from that
        /// field), the window's Required Level text, its Current Level text, and the language's "Mastered".</summary>
        public const int UiSheet = 0x13, UiRowBytes = 8, UiTextAt = 4, RequiredText = 1012, CurrentText = 1004,
                         MasteredText = 1077;
        /// <summary>The game's 20 generic jobs: the first, and how many (a job's slot is its number less the first).</summary>
        public const int FirstGeneric = JobRoom.FirstGeneric, GameJobs = 20;
        /// <summary>What a mod's job is known by in GeneralJob and in the window's search: this plus its number. The
        /// game's own are known by their slots, 0 to 21.</summary>
        public const int OwnFirst = 0x100;
        /// <summary>The marks above a job's number in the screen's list: locked, and not to be seen.</summary>
        public const int Locked = 0x4000, Unseen = 0x2000;
        /// <summary>The menu's record of a unit: its job (a word), its sex's bits, its opened jobs (three bytes of bits,
        /// the first its first job's) and its levels (a nibble a slot, the even slot the high one).</summary>
        public const int RecordJobAt = 0x24, RecordSexAt = 0x70, RecordOpenAt = 0x78, RecordLevelsAt = 0xBD, JobBits = 0x3FF;
        /// <summary>A place's record on the job screen (0x94 bytes): its name (0x40 bytes with its end), its icon's
        /// number, the unit's level in it, its job and whether it is open (0), locked (1) or not to be seen (2).</summary>
        public const int PlaceBytes = 0x94, PlaceName = 0x40, PlaceIconAt = 0x40, PlaceLevelAt = 0x44, PlaceJobAt = 0x48,
                         PlaceClosedAt = 0x84;

        /// <summary>What a mod's job is known by.</summary>
        public static int Identity(int number) => OwnFirst + number;

        /// <summary>What a job is known by in the window's search (JobRoom's Same answers the same in the game): a mod's
        /// job (`mods`: their numbers) by Identity, any other by its slot as the game's own function has it (0x2B8F18:
        /// 74 to 93 are 0 to 19, 160 and 161 are 20 and 21, anything else 0).</summary>
        public static int Known(int job, ReadOnlySpan<short> mods)
        {
            foreach (short mod in mods)
                if (mod == job)
                    return Identity(job);
            return job >= FirstGeneric && job < FirstGeneric + GameJobs ? job - FirstGeneric
                   : job == 160 ? 20 : job == 161 ? 21 : 0;
        }

        /// <summary>The job a need is of, where the unit's list doesn't hold it: a mod's by its number, one of the
        /// game's generic jobs by its slot.</summary>
        public static int JobOf(int known) => known >= OwnFirst ? known - OwnFirst : known == 20 ? 160 : known == 21 ? 161
                                                                                    : FirstGeneric + known;

        /// <summary>One need of a job given: what the needed job is known by (a slot of the game's, or Identity of a
        /// mod's), the level asked, and for a mod's job its place among the jobs given (below 0: one of the game's).</summary>
        public readonly struct Need
        {
            public int Known { get; }
            public int Level { get; }
            public int Own { get; }
            /// <summary>(1.55.0) Whether the job (one of the game's, by its slot) is needed mastered: every place of its
            /// skillset learned (Level is then the most a window shows, 8). The game's Dark Knight's Knight and Black Mage;
            /// (1.55.2) and a mod's job's need of one of the game's generic jobs its file asks mastered; (1.56.0) and of a
            /// job of its own mod's (`Own` its place among the jobs given).</summary>
            public bool Mastered { get; }
            /// <summary>(1.55.0) Where the job is the game's Dark Knight or Onion Knight a mod gives: its place among the jobs
            /// given (open by the framework's test, its level the unit's own); else below 0.</summary>
            public int Game { get; }

            public Need(int known, int level, int own, bool mastered = false, int game = -1)
            {
                Known = known;
                Level = level;
                Own = own;
                Mastered = mastered;
                Game = game;
            }
        }

        /// <summary>(1.55.0) The game's own rule for its Dark Knight and Onion Knight (the program's rows of them, its
        /// routine's two mastered jobs; dev/research/sidequests/dark_onion.py), less the kills: each needed job's slot, the
        /// level asked, whether mastered.</summary>
        public static readonly (int Slot, int Level, bool Mastered)[] DarkRule =
            { (12, 8, false), (13, 8, false), (14, 8, false), (15, 8, false), (2, 8, true), (6, 8, true) };
        public static readonly (int Slot, int Level, bool Mastered)[] OnionRule = { (0, 6, false), (1, 6, false) };
        /// <summary>(1.55.0) The menu's record of a unit: its learned rows (three bytes a slot, the first place the highest
        /// bit), and how many places a row has.</summary>
        public const int RecordLearnedAt = 0x7B, RowPlaces = 24;

        /// <summary>(1.55.0) Which of the 24 places of each of the game's generic jobs' skillsets hold an ability (by slot,
        /// 0 to 19; null for the rest), from the program's job records (`records`: the job's skillset its record's first
        /// byte) and skillset records (`skillsets`: 25 bytes each, 176 of them; an ability a place's byte and a ninth bit,
        /// as the game's reader takes it), as the game's routine finds a job mastered.</summary>
        public static IReadOnlyList<bool>?[] PlacesOf(ReadOnlySpan<byte> image, int records, int skillsets)
        {
            var places = new IReadOnlyList<bool>?[22];
            for (int slot = 0; slot < GameJobs; slot++)
            {
                int skillset = image[records + JobRoom.RecordBytes * (FirstGeneric + slot)];
                if (skillset >= JobRoom.SkillsetCount)
                    continue;
                var record = image.Slice(skillsets + JobRoom.SkillsetBytes * skillset, JobRoom.SkillsetBytes);
                var holds = new bool[RowPlaces];
                for (int place = 0; place < JobFile.MostActions + JobFile.MostOthers; place++)
                {
                    int at = place < JobFile.MostActions ? JobRoom.SkillsetActionsAt + place
                                                         : JobRoom.SkillsetOthersAt + place - JobFile.MostActions;
                    holds[place] = record[at] != 0 || (record[place / 8] & 0x80 >> place % 8) != 0;
                }
                places[slot] = holds;
            }
            return places;
        }

        /// <summary>(1.55.0) Whether a unit has learned every place of a job's skillset (`places`: which of its 24 places
        /// hold an ability), by its menu's record and the job's slot: a place that holds none counts as learned, as the
        /// game's own routine counts it.</summary>
        public static bool Mastered(ReadOnlySpan<byte> record, int slot, IReadOnlyList<bool>? places)
        {
            if (places == null || slot < 0 || slot >= 22)
                return false;
            for (int place = 0; place < RowPlaces && place < places.Count; place++)
                if (places[place] && (record[RecordLearnedAt + 3 * slot + place / 8] & 0x80 >> place % 8) == 0)
                    return false;
            return true;
        }

        /// <summary>Whether a unit has one of the game's jobs open, by its menu's record and the job's slot.</summary>
        public static bool GameOpen(ReadOnlySpan<byte> record, int slot)
            => slot >= 0 && slot < 24 && (record[RecordOpenAt + slot / 8] & 0x80 >> slot % 8) != 0;

        /// <summary>A unit's level in one of the game's jobs, by its menu's record and the job's slot.</summary>
        public static int GameLevel(ReadOnlySpan<byte> record, int slot)
            => slot < 0 || slot >= 24 ? 0 : record[RecordLevelsAt + slot / 2] >> (slot % 2 == 0 ? 4 : 0) & 0xF;

        /// <summary>The needs of the jobs given, each need's job found among them.</summary>
        public sealed class Plan
        {
            /// <summary>The jobs' numbers, in the order given; each job's needs; and whether a job can never be opened
            /// (it needs a job of its mod's that has no number here).</summary>
            public int[] Numbers { get; }
            public Need[][] Needs { get; }
            public bool[] Never { get; }
            /// <summary>(1.55.0) Each job's slot where it is the game's Dark Knight or Onion Knight (20, 21), else -1; and
            /// which places of the game's jobs' skillsets hold an ability (by slot, null where not known), for a need of a
            /// job mastered.</summary>
            public int[] GameSlots { get; }
            public IReadOnlyList<bool>?[] Places { get; set; } = new IReadOnlyList<bool>?[22];
            /// <summary>(1.56.0) Which of the 24 places of each job given's own skillset hold an ability (by its place
            /// among the jobs given), for a need of it mastered: its Actions the first places, its Others from
            /// JobFile.MostActions on.</summary>
            public bool[][] OwnPlaces { get; }
            /// <summary>Whether any job given needs anything.</summary>
            public bool Any { get; }

            /// <summary>A plan of these jobs' numbers, each one's needs, and which can never be opened.</summary>
            public Plan(int[] numbers, Need[][] needs, bool[] never, int[]? gameSlots = null, bool[][]? ownPlaces = null)
            {
                Numbers = numbers;
                Needs = needs;
                Never = never;
                GameSlots = gameSlots ?? Array.ConvertAll(numbers, _ => -1);
                OwnPlaces = ownPlaces ?? Array.ConvertAll(numbers, _ => new bool[RowPlaces]);
                foreach (var list in needs)
                    Any |= list.Length > 0;
                foreach (bool no in never)
                    Any |= no;
            }

            /// <summary>The plan of the jobs given. A need by name is the job of the same mod with that Name; where that
            /// job has no number (it was left out), the job that needs it can't be opened, said.</summary>
            public static Plan Make(IList<JobRoom.Given> given, List<string> said)
            {
                var numbers = new int[given.Count];
                var needs = new Need[given.Count][];
                var never = new bool[given.Count];
                var gameSlots = new int[given.Count];
                var ownPlaces = new bool[given.Count][];
                for (int k = 0; k < given.Count; k++)
                    ownPlaces[k] = PlacesOfOwn(given[k].Job);
                for (int k = 0; k < given.Count; k++)
                {
                    numbers[k] = given[k].Number;
                    gameSlots[k] = -1;
                    var list = new List<Need>();
                    // (1.55.0) The game's own Dark Knight or Onion Knight: the game's own rule, less the kills.
                    if (given[k].Game)
                    {
                        bool darkKnight = given[k].Number == JobFile.DarkKnight;
                        gameSlots[k] = darkKnight ? JobRoom.DarkSlot : JobRoom.DarkSlot + 1;
                        foreach (var (slot, level, mastered) in darkKnight ? DarkRule : OnionRule)
                            list.Add(new Need(slot, level, -1, mastered));
                        needs[k] = list.ToArray();
                        continue;
                    }
                    foreach (var need in given[k].Job.Needs)
                    {
                        if (need.Own == null)
                        {
                            // (1.55.2) One of the game's generic jobs, at a level or (Zodi's word on test 123) mastered.
                            list.Add(new Need(need.Job - FirstGeneric, need.Level, -1, need.Mastered));
                            continue;
                        }
                        int own = -1;
                        for (int j = 0; j < given.Count && own < 0; j++)
                            if (given[j].Job.ModId == given[k].Job.ModId && given[j].Job.Name == need.Own)
                                own = j;
                        if (own < 0)
                        {
                            never[k] = true;
                            said.Add(NeverLine(given[k].Job.Who, need.Own));
                            continue;
                        }
                        // (1.55.0) The game's Dark Knight or Onion Knight of its mod: by its slot, open by its own test;
                        // (1.56.0) asked mastered, asked at level 8, said.
                        if (given[own].Game)
                        {
                            if (need.Mastered)
                                said.Add(GameMasteredLine(given[k].Job.Who, JobFile.GameJobName(given[own].Number)));
                            list.Add(new Need(given[own].Number == JobFile.DarkKnight ? JobRoom.DarkSlot : JobRoom.DarkSlot + 1,
                                              need.Mastered ? JobFile.MostNeedLevel : need.Level, -1, false, own));
                        }
                        else
                            list.Add(new Need(Identity(given[own].Number), need.Level, own, need.Mastered));
                    }
                    needs[k] = list.ToArray();
                }
                return new Plan(numbers, needs, never, gameSlots, ownPlaces);
            }

            /// <summary>A job's place among the jobs given, by its number (below 0: not one of them).</summary>
            public int IndexOf(int number) => Array.IndexOf(Numbers, number);

            /// <summary>Whether a job given (its place among them) is open to a unit, by the menu's record of the unit
            /// and its level in each of the jobs given (`ownLevel`, by place): the job it is in is; else it has every
            /// job needed open, at the level asked or more. (1.56.0) `ownMastered` (by place): whether the unit has
            /// mastered a job given, for a need of it mastered (none: never).</summary>
            public bool Open(int index, ReadOnlySpan<byte> record, Func<int, int> ownLevel, Func<int, bool>? ownMastered = null)
                => Open(index, record, ownLevel, ownMastered ?? (_ => false), 0);

            bool Open(int index, ReadOnlySpan<byte> record, Func<int, int> ownLevel, Func<int, bool> ownMastered, int depth)
            {
                if (index < 0 || index >= Numbers.Length)
                    return false;
                if ((BinaryPrimitives.ReadUInt16LittleEndian(record.Slice(RecordJobAt)) & JobBits) == Numbers[index])
                    return true;
                // The files' reading leaves no ring of needs; a plan made another way stops here all the same.
                if (Never[index] || depth > Numbers.Length)
                    return false;
                foreach (var need in Needs[index])
                {
                    if (need.Own >= 0)
                    {
                        // (1.56.0) A job of its mod's asked mastered: every place of its own skillset learned.
                        if ((need.Mastered ? !ownMastered(need.Own) : ownLevel(need.Own) < need.Level)
                            || !Open(need.Own, record, ownLevel, ownMastered, depth + 1))
                            return false;
                    }
                    else if (need.Game >= 0)
                    {
                        // (1.55.0) The game's Dark Knight or Onion Knight a mod gives: its own test, the unit's level in it.
                        if (GameLevel(record, need.Known) < need.Level || !Open(need.Game, record, ownLevel, ownMastered, depth + 1))
                            return false;
                    }
                    else if (!GameOpen(record, need.Known)
                             || (need.Mastered ? !Mastered(record, need.Known, Places[need.Known]) : GameLevel(record, need.Known) < need.Level))
                        return false;
                }
                return true;
            }

            /// <summary>The mark of a job given for a unit: none where it is open to the unit (`mine`), locked where it
            /// is open to some unit of the party (`anyone`), else not to be seen.</summary>
            public static int Mark(bool mine, bool anyone) => mine ? 0 : anyone ? Locked : Unseen;
        }

        /// <summary>(1.56.0) Which of the 24 places of a mod's job's own skillset hold an ability: its Actions the first
        /// places, its Others from JobFile.MostActions on (the skillset the framework writes for it, JobRoom).</summary>
        public static bool[] PlacesOfOwn(ModJob job)
        {
            var places = new bool[RowPlaces];
            for (int n = 0; n < job.Actions.Length && n < JobFile.MostActions; n++)
                places[n] = true;
            for (int n = 0; n < job.Others.Length && n < JobFile.MostOthers; n++)
                places[JobFile.MostActions + n] = true;
            return places;
        }

        /// <summary>(1.56.0) Whether a unit has mastered a mod's job, by its learned row in that job (`row`: the row's
        /// three bytes, the first place the highest bit of the first, as JobProgress.Row gives them) and which places of
        /// its skillset hold an ability: a place that holds none counts as learned, as the game counts its own.</summary>
        public static bool OwnMastered(int row, IReadOnlyList<bool>? places)
        {
            if (places == null)
                return false;
            for (int place = 0; place < RowPlaces && place < places.Count; place++)
                if (places[place] && (row & 0x800000 >> place) == 0)
                    return false;
            return true;
        }

        /// <summary>(1.56.0) What the log says of a job whose file asks the game's Dark Knight or Onion Knight its mod gives
        /// mastered.</summary>
        public static string GameMasteredLine(string who, string game)
            => $"{who} needs the game's {game} mastered: it is asked at level {JobFile.MostNeedLevel} (only a job made new or "
               + "one of the game's generic jobs is asked by its abilities learned).";

        /// <summary>What the log says of a job that needs one its mod doesn't give a number.</summary>
        public static string NeverLine(string who, string needed)
            => $"{who} can't be opened by any unit: it needs {needed}, a job of its mod that isn't given here.";

        /// <summary>What the log says of the jobs that need something: how many of the jobs given.</summary>
        public static string Line(int jobs, int all)
            => $"what opens a job: {jobs} of the mods' {all} job{(all == 1 ? "" : "s")} {(jobs == 1 ? "needs" : "need")} other jobs "
               + "first; a unit sees such a job locked on the job screen until it has them, and the window there says what is "
               + "missing.";

        /// <summary>What the log says where the needs aren't asked: the framework's own rows of the job screen aren't
        /// made (the other mod's page shows the jobs, or the screen wasn't found).</summary>
        public const string NotAskedLine = "what opens a job: what the mods' jobs need is asked only where the framework's own "
            + "rows of the job screen show them, and those aren't made here (Dark Knight & Onion Knight (Generic) shows the "
            + "jobs on its page, or the job screen wasn't found): every unit has every one of the mods' jobs open.";

        // --- the game table ----------------------------------------------------------------------------------------------

        static int I32(ReadOnlySpan<byte> b, int at) => BinaryPrimitives.ReadInt32LittleEndian(b.Slice(at, 4));

        /// <summary>The JP each level needs, from a loaded GeneralJob table's first row (every generic job's are the
        /// same list in the game), or null where the table has no such row or its list runs past the table.</summary>
        public static int[]? Exp(ReadOnlySpan<byte> table)
        {
            int at = Nxd.Find(table, new[] { 0 });
            if (at < 0 || at + RowBytes > table.Length)
                return null;
            int from = at + I32(table, at + ExpAt), count = I32(table, at + ExpAt + 4);
            if (count != ExpLevels || from < 0 || (long)from + 4 * count > table.Length)
                return null;
            var exp = new int[count];
            for (int n = 0; n < count; n++)
                exp[n] = I32(table, from + 4 * n);
            return exp;
        }

        /// <summary>What a row of a loaded GeneralJob table needs: each needed job as the row knows it and its level
        /// (1 where the row gives none, as the window takes it), or null where the table has no such row.</summary>
        public static (int Known, int Level)[]? RowNeeds(ReadOnlySpan<byte> table, int key)
        {
            int at = Nxd.Find(table, new[] { key });
            if (at < 0 || at + RowBytes > table.Length)
                return null;
            int from = at + I32(table, at + NeedsAt), count = I32(table, at + NeedsAt + 4);
            int levelsFrom = at + I32(table, at + LevelsAt), levels = I32(table, at + LevelsAt + 4);
            if (count < 0 || count > 64 || from < 0 || (long)from + 4 * count > table.Length || levels < 0
                || levelsFrom < 0 || (long)levelsFrom + 2 * Math.Min(levels, count) > table.Length)
                return null;
            var needs = new (int, int)[count];
            for (int n = 0; n < count; n++)
                needs[n] = (I32(table, from + 4 * n),
                            n < levels ? Math.Max(1, (int)BinaryPrimitives.ReadInt16LittleEndian(table.Slice(levelsFrom + 2 * n))) : 1);
            return needs;
        }

        /// <summary>A row of GeneralJob for a mod's job: no DLC flags, an empty comment, the JP each level needs
        /// (`exp`), its needs as the window's search knows them with their levels (1.55.1: a job needed mastered
        /// MasteredShown), no labels' places and no
        /// directions (Job Progress has no box of the game's for it), not seen at a new game's start. Laid out as the
        /// game's own rows: the lists after the fixed part, each pointed at from the row's start.</summary>
        public static byte[] Row(ReadOnlySpan<int> exp, ReadOnlySpan<Need> needs)
        {
            int expFrom = RowBytes, needsFrom = expFrom + 4 * exp.Length, levelsFrom = needsFrom + 4 * needs.Length,
                labelsFrom = levelsFrom + 2 * needs.Length, emptyFrom = (labelsFrom + 3) & ~3;
            var row = new byte[emptyFrom + 4];
            void Put(int at, int value) => BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(at), value);
            Put(CommentAt, emptyFrom);
            Put(ExpAt, expFrom);
            Put(ExpAt + 4, exp.Length);
            Put(NeedsAt, needsFrom);
            Put(NeedsAt + 4, needs.Length);
            Put(LevelsAt, levelsFrom);
            Put(LevelsAt + 4, needs.Length);
            Put(LabelsAt, labelsFrom);
            Put(LabelsAt + 4, 0);
            for (int n = 0; n < Directions; n++)
                Put(DirectionsAt + 4 * n, NoDirection);
            row[StartsUnseenAt] = 1;
            for (int n = 0; n < exp.Length; n++)
                Put(expFrom + 4 * n, exp[n]);
            for (int n = 0; n < needs.Length; n++)
            {
                Put(needsFrom + 4 * n, needs[n].Known);
                // (1.55.1) A job needed mastered: the level the window's texts show as "Mastered".
                BinaryPrimitives.WriteInt16LittleEndian(row.AsSpan(levelsFrom + 2 * n),
                                                        (short)(needs[n].Mastered ? MasteredShown : needs[n].Level));
            }
            return row;
        }

        /// <summary>The loaded GeneralJob table with a row for each job given (key OwnFirst plus its number), or null
        /// and why; `rows` how many. A row another mod has at a key is kept, said.</summary>
        public static byte[]? WithRows(ReadOnlySpan<byte> table, IList<JobRoom.Given> given, Plan plan, List<string> said,
                                       out string why, out int rows)
        {
            rows = 0;
            if (Nxd.Keys(table) != 1)
            {
                why = "it isn't a table of one key";
                return null;
            }
            int[]? exp = Exp(table);
            if (exp == null)
            {
                why = "its first row doesn't hold the JP each level needs";
                return null;
            }
            var added = new List<NewRow>();
            for (int k = 0; k < given.Count; k++)
            {
                int key = Identity(given[k].Number);
                if (Nxd.Find(table, new[] { key }) >= 0)
                {
                    said.Add($"{given[k].Job.Who}'s needs keep the row another mod gives them ({key}).");
                    continue;
                }
                added.Add(new NewRow(new[] { key }, Row(exp, plan.Needs[k])));
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

        /// <summary>The table's line, once its rows are written.</summary>
        public static string RowsLine(int rows)
            => $"GeneralJob: the mods' jobs' needs' {rows} row{(rows == 1 ? "" : "s")} written.";

        /// <summary>What is said where the table can't be given its rows.</summary>
        public static string NoRowsLine(string why)
            => $"GeneralJob gets no rows: {why}. The window of what a locked job needs shows nothing for the mods' jobs.";

        // --- (1.55.1) "Mastered" in the window ------------------------------------------------------------------------------

        /// <summary>(1.55.1) A text as a branch of the game's own choosing of words (`&lt;if([...],A,B)&gt;`): each mark as it
        /// is, every run of other characters in quotes, as the game's own branches put words between marks (UI-de's
        /// `&lt;y=5&gt;"Status-Effekte"&lt;y&gt;`, `"kann maximal "&lt;num=lnum0&gt;" Einheit"`). Null where a mark isn't closed
        /// or holds a mark, or a run holds a quote, a backslash or a mark's end (the game's escapes for those aren't
        /// known).</summary>
        public static string? Branch(string text)
        {
            var made = new StringBuilder();
            int i = 0;
            while (i < text.Length)
            {
                if (text[i] == '<')
                {
                    int end = text.IndexOf('>', i);
                    if (end < 0 || text.IndexOf('<', i + 1, end - i - 1) >= 0)
                        return null;
                    made.Append(text, i, end - i + 1);
                    i = end + 1;
                    continue;
                }
                int next = text.IndexOf('<', i);
                if (next < 0)
                    next = text.Length;
                string run = text.Substring(i, next - i);
                if (run.IndexOfAny(new[] { '"', '\\', '>' }) >= 0)
                    return null;
                made.Append('"').Append(run).Append('"');
                i = next;
            }
            return made.ToString();
        }

        /// <summary>(1.55.1) Whether a text is marks alone (or nothing).</summary>
        static bool MarksOnly(string text)
        {
            int i = 0;
            while (i < text.Length)
            {
                int end = text[i] == '<' ? text.IndexOf('>', i) : -1;
                if (end < 0)
                    return false;
                i = end + 1;
            }
            return true;
        }

        /// <summary>(1.55.1) A level's text (the language's own, with one `&lt;num=lnum0&gt;`) made to show the language's
        /// word for a job mastered (`mastered`) for MasteredShown and itself otherwise. The marks before its first words,
        /// and those after its number where only marks follow it, stay outside the choosing: they place and size the cell's
        /// words for both. Null where it has no number or more than one, or either text can't be put in a branch.</summary>
        public static string? MasteredWords(string level, string mastered)
        {
            const string Number = "<num=lnum0>";
            int number = level.IndexOf(Number, StringComparison.Ordinal);
            if (number < 0 || level.IndexOf(Number, number + Number.Length, StringComparison.Ordinal) >= 0)
                return null;
            int lead = 0;
            while (lead < number && level[lead] == '<')
            {
                int end = level.IndexOf('>', lead);
                if (end < 0 || end >= number)
                    return null;
                lead = end + 1;
            }
            int tail = number + Number.Length;
            bool trails = MarksOnly(level.Substring(tail));
            string core = level.Substring(lead, (trails ? tail : level.Length) - lead);
            string? chosen = Branch(mastered), otherwise = Branch(core);
            if (chosen == null || otherwise == null)
                return null;
            return level.Substring(0, lead) + $"<if([lnum0=={MasteredShown}],{chosen},{otherwise})>"
                   + (trails ? level.Substring(tail) : "");
        }

        /// <summary>(1.55.1) A row's text in a loaded UI table, or null where the table has no such row or its text runs
        /// past the table.</summary>
        public static string? UiText(ReadOnlySpan<byte> table, int key)
        {
            int at = Nxd.Find(table, new[] { key });
            if (at < 0 || at + UiRowBytes > table.Length)
                return null;
            long start = (long)at + UiTextAt + BinaryPrimitives.ReadInt32LittleEndian(table.Slice(at + UiTextAt));
            if (start < 0 || start >= table.Length)
                return null;
            int end = table.Slice((int)start).IndexOf((byte)0);
            return end < 0 ? null : Encoding.UTF8.GetString(table.Slice((int)start, end));
        }

        /// <summary>(1.55.1) A row of the UI table: its first word as it was (`first`), its text after the fixed part, the
        /// distance counted from its field.</summary>
        public static byte[] UiRow(int first, string text)
        {
            byte[] words = Encoding.UTF8.GetBytes(text);
            var row = new byte[(UiRowBytes + words.Length + 1 + 3) & ~3];
            BinaryPrimitives.WriteInt32LittleEndian(row, first);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(UiTextAt), UiRowBytes - UiTextAt);
            words.CopyTo(row, UiRowBytes);
            return row;
        }

        /// <summary>(1.55.1) The loaded UI table with the window's two level texts (RequiredText, CurrentText) made to show
        /// the language's "Mastered" (MasteredText) for MasteredShown, where a job given is needed mastered (the game's
        /// Dark Knight's rule). A text that isn't laid out as the game's (another mod's) is kept, said. Null and why where
        /// neither can be written; `written` how many were.</summary>
        public static byte[]? WithMasteredWords(ReadOnlySpan<byte> table, List<string> said, out string why, out int written)
        {
            written = 0;
            if (Nxd.Keys(table) != 1)
            {
                why = "it isn't a table of one key";
                return null;
            }
            string? mastered = UiText(table, MasteredText);
            if (string.IsNullOrEmpty(mastered))
            {
                why = $"it has no text {MasteredText}, the game's word for a job mastered";
                return null;
            }
            var rows = new List<NewRow>();
            foreach (int key in new[] { RequiredText, CurrentText })
            {
                int at = Nxd.Find(table, new[] { key });
                string? level = UiText(table, key);
                string? made = level == null ? null : MasteredWords(level, mastered);
                if (at < 0 || made == null)
                {
                    said.Add($"the window of what a job needs shows a job needed mastered as level {MasteredShown} in its "
                             + $"{(key == RequiredText ? "Required" : "Current")} Level column: the UI table's text {key} isn't "
                             + "as the game's.");
                    continue;
                }
                rows.Add(new NewRow(new[] { key }, UiRow(BinaryPrimitives.ReadInt32LittleEndian(table.Slice(at)), made)));
            }
            if (rows.Count == 0)
            {
                why = "neither of its two level texts is as the game's";
                return null;
            }
            var withRows = Nxd.WithRows(table, rows, out why, replace: true);
            if (withRows != null)
                written = rows.Count;
            return withRows;
        }

        /// <summary>(1.55.1) The UI table's line, once its texts are written.</summary>
        public static string MasteredLine(int written)
            => $"UI: the window of what a job needs shows Mastered for a job needed mastered (its {written} level "
               + $"text{(written == 1 ? "" : "s")} written).";

        /// <summary>(1.55.1) What is said where the UI table can't be given them.</summary>
        public static string NoMasteredLine(string why)
            => $"UI gets no Mastered for the window of what a job needs: {why}. A job needed mastered shows there as level "
               + $"{MasteredShown}.";

        // --- a place's record made for the window ---------------------------------------------------------------------------

        /// <summary>A job's name and its icon's number from a loaded Job table (the name a woman's where the row has
        /// one and `woman`), or null where the table has no such row.</summary>
        public static (string Name, int Icon)? Named(ReadOnlySpan<byte> jobs, int job, bool woman)
        {
            int at = Nxd.Find(jobs, new[] { job });
            if (at < 0 || at + JobRoom.RowBytes > jobs.Length)
                return null;
            string name = woman ? RowWord(jobs, at, JobRoom.RowUnknown4At) : "";
            if (name.Length == 0)
                name = RowWord(jobs, at, JobRoom.RowNameAt);
            return (name, I32(jobs, at + JobArt.JobIconAt));
        }

        /// <summary>A word of a Job table's row (at `at`), by the field that names it: "" where it runs past the table.</summary>
        static string RowWord(ReadOnlySpan<byte> jobs, int at, int field)
        {
            long start = (long)at + JobRoom.RowWordsFrom + I32(jobs, at + field);
            if (start < 0 || start >= jobs.Length)
                return "";
            int end = (int)start;
            while (end < jobs.Length && jobs[end] != 0)
                end++;
            return end < jobs.Length ? Encoding.UTF8.GetString(jobs.Slice((int)start, end - (int)start)) : "";
        }

        /// <summary>A place's record for a needed job that is on none of the places shown, written over `record` (0x94
        /// bytes): its name (cut to what a record holds, at a whole character), its icon's number, the unit's level in
        /// it, its job and whether it is open (0), locked (1) or not to be seen (2). Everything else of a record the
        /// window doesn't read is left 0.</summary>
        public static void Stand(Span<byte> record, string name, int icon, int level, int job, int closed)
        {
            record.Slice(0, PlaceBytes).Clear();
            byte[] words = Encoding.UTF8.GetBytes(name);
            int length = Math.Min(words.Length, PlaceName - 1);
            while (length > 0 && length < words.Length && (words[length] & 0xC0) == 0x80)
                length--;
            words.AsSpan(0, length).CopyTo(record);
            BinaryPrimitives.WriteInt32LittleEndian(record.Slice(PlaceIconAt), icon);
            BinaryPrimitives.WriteInt32LittleEndian(record.Slice(PlaceLevelAt), level);
            BinaryPrimitives.WriteInt32LittleEndian(record.Slice(PlaceJobAt), job);
            BinaryPrimitives.WriteInt32LittleEndian(record.Slice(PlaceClosedAt), closed);
        }
    }

    /// <summary>(1.48.0) What the game's code and the job screen's rows ask of the jobs' needs while the game runs: over
    /// the menu's records of the party's units (their table, a pointer a record, and the word that says which the
    /// screens are of), the units' levels in the mods' jobs (JobProgress) and the Job and GeneralJob tables as loaded
    /// with the mods' rows. Nothing here changes anything of the game's.</summary>
    public sealed unsafe class JobAsker
    {
        readonly JobNeeds.Plan _plan;
        readonly JobProgress _progress;
        readonly short* _menuIndex;
        readonly byte** _menuTable;
        readonly int _records;
        readonly short[] _mods;
        readonly object _lock;
        /// <summary>The loaded Job table and the loaded GeneralJob table, each with the mods' rows (null until loaded).</summary>
        public volatile byte[]? Jobs;
        public volatile byte[]? General;

        /// <summary>A man's and a woman's bits of a record's sex's byte.</summary>
        public const int People = 0xC0, Woman = 0x40;

        public JobNeeds.Plan Plan => _plan;

        /// <summary>`menuIndex` and `menuTable`: which of the menu's records the screens are of, and the table of them
        /// (`records` long). `lockOn`: what the units' progress is locked on while it is read.</summary>
        public JobAsker(JobNeeds.Plan plan, JobProgress progress, short* menuIndex, byte** menuTable, int records, object lockOn)
        {
            _plan = plan;
            _progress = progress;
            _menuIndex = menuIndex;
            _menuTable = menuTable;
            _records = records;
            _lock = lockOn;
            _mods = new short[plan.Numbers.Length];
            for (int k = 0; k < _mods.Length; k++)
                _mods[k] = (short)plan.Numbers[k];
        }

        byte* Record(int unit) => unit >= 0 && unit < _records ? _menuTable[unit] : null;

        /// <summary>Whether a job given is open to the unit of a record (the units' records looked at before this).</summary>
        bool OpenTo(int k, byte* record)
        {
            int index = _progress.IndexOf(record);
            var progress = _progress;
            var plan = _plan;
            return _plan.Open(k, new ReadOnlySpan<byte>(record, JobProgress.MenuBytes), job => progress.Level(job, index),
                              job => JobNeeds.OwnMastered(progress.Row(job, index), plan.OwnPlaces[job]));
        }

        /// <summary>Whether any man or woman of the party has a job given open, by the menu's records that are a unit
        /// of the party's.</summary>
        bool Anyone(int k)
        {
            for (int r = 0; r < _records && r < JobProgress.MenuRecords; r++)
            {
                byte* record = _menuTable[r];
                if (record == null || (record[JobNeeds.RecordSexAt] & People) == 0)
                    continue;
                int index = _progress.IndexOf(record);
                if (index >= 0 && _progress.Owned(index) && OpenTo(k, record))
                    return true;
            }
            return false;
        }

        /// <summary>Whether any man or woman of the party has one of the game's jobs open, by its slot.</summary>
        bool AnyoneGame(int slot)
        {
            for (int r = 0; r < _records && r < JobProgress.MenuRecords; r++)
            {
                byte* record = _menuTable[r];
                if (record == null || (record[JobNeeds.RecordSexAt] & People) == 0)
                    continue;
                int index = _progress.IndexOf(record);
                if (index >= 0 && _progress.Owned(index)
                    && JobNeeds.GameOpen(new ReadOnlySpan<byte>(record, JobProgress.MenuBytes), slot))
                    return true;
            }
            return false;
        }

        /// <summary>The mark of one of the jobs given (its place among them) for the unit the screens are of: none
        /// where it needs nothing or the unit has it open, JobNeeds.Locked where another unit of the party has,
        /// else JobNeeds.Unseen.</summary>
        public int Mark(int k)
        {
            if (k < 0 || k >= _plan.Numbers.Length || (_plan.Needs[k].Length == 0 && !_plan.Never[k]))
                return 0;
            byte* record = Record(*_menuIndex);
            if (record == null)
                return 0;
            lock (_lock)
            {
                _progress.Looked();
                return JobNeeds.Plan.Mark(OpenTo(k, record), Anyone(k));
            }
        }

        /// <summary>Whether a job (its number) is open to a unit (the number of its record among the menu's): 1, or 0.
        /// A job that isn't one of the jobs given, or needs nothing, is.</summary>
        public int Open(int unit, int number)
        {
            int k = _plan.IndexOf(number);
            if (k < 0 || (_plan.Needs[k].Length == 0 && !_plan.Never[k]))
                return 1;
            byte* record = Record(unit & 0xFFFF);
            if (record == null)
                return 1;
            lock (_lock)
            {
                _progress.Looked();
                return OpenTo(k, record) ? 1 : 0;
            }
        }

        /// <summary>What a job needs, each needed job as the window's search knows it, from the loaded GeneralJob
        /// table; null where the table isn't known or has no row for the job.</summary>
        public int[]? Needed(int job)
        {
            byte[]? general = General;
            if (general == null)
                return null;
            var needs = JobNeeds.RowNeeds(general, JobNeeds.Known(job, _mods));
            return needs == null ? null : Array.ConvertAll(needs, n => n.Known);
        }

        /// <summary>(1.55.1) Which of a job's needs are of a job mastered, in the order its GeneralJob row has them (the
        /// plan's), or null where it isn't one of the jobs given or needs no job mastered.</summary>
        public bool[]? MasteredNeeds(int job)
        {
            int k = _plan.IndexOf(job);
            if (k < 0 || !Array.Exists(_plan.Needs[k], n => n.Mastered))
                return null;
            return Array.ConvertAll(_plan.Needs[k], n => n.Mastered);
        }

        /// <summary>(1.55.1) The game's Onion Knight's slot, and its level once every job it counts is mastered.</summary>
        public const int OnionSlot = 21, OnionTop = 8;

        /// <summary>(1.55.1) The job help table's key Job Summary reads for a key it asks: the game's Onion Knight's own key,
        /// where the screens' unit's Onion Knight is level 8 (the game's own rule sets it: dark_onion.py's OK_LEVEL), its
        /// words for that level's (the key of the job the game takes a level 8 Onion Knight's words from, JobWords); any
        /// other as asked.</summary>
        public int SummaryKey(int key)
        {
            if (key != JobWords.HelpKey(JobFile.OnionKnight))
                return key;
            byte* record = Record(*_menuIndex);
            if (record == null)
                return key;
            return JobNeeds.GameLevel(new ReadOnlySpan<byte>(record, JobProgress.MenuBytes), OnionSlot) >= OnionTop
                   ? JobWords.HelpKey(JobFile.MasteredOnion) : key;
        }

        /// <summary>(1.55.1) Whether the unit the screens are of has mastered one of the game's jobs (by its slot): every
        /// place of its skillset learned, as the framework's test asks of a need of it mastered. (1.56.0) Or one of the
        /// jobs given (by its Identity): every place of its own skillset learned.</summary>
        public bool HasMastered(int known)
        {
            byte* record = Record(*_menuIndex);
            if (record == null || known < 0)
                return false;
            if (known >= JobNeeds.OwnFirst)
            {
                int k = _plan.IndexOf(known - JobNeeds.OwnFirst);
                if (k < 0)
                    return false;
                lock (_lock)
                {
                    _progress.Looked();
                    return JobNeeds.OwnMastered(_progress.Row(k, _progress.IndexOf(record)), _plan.OwnPlaces[k]);
                }
            }
            if (known >= _plan.Places.Length)
                return false;
            lock (_lock)
                return JobNeeds.Mastered(new ReadOnlySpan<byte>(record, JobProgress.MenuBytes), known, _plan.Places[known]);
        }

        /// <summary>(1.56.0) Whether the unit the screens are of has mastered a job, by its number (one of the jobs given
        /// or one of the game's generic jobs): HasMastered of what the window's search knows it by.</summary>
        public bool HasMasteredJob(int job) => HasMastered(JobNeeds.Known(job, _mods));

        /// <summary>A place's record for a needed job that is on none of the places shown, for the unit the screens are
        /// of: its name and icon from the loaded Job table, the unit's level in it, and whether it is open (`closed`
        /// as the unit's list has it: 0, 1 locked, 2 not to be seen; below 0 where the list doesn't hold the job:
        /// worked out here). False where the table isn't known or has no row for the job.</summary>
        public bool Stand(int job, int closed, nint to)
        {
            byte[]? jobs = Jobs;
            byte* record = Record(*_menuIndex);
            if (jobs == null || record == null || to == 0)
                return false;
            var named = JobNeeds.Named(jobs, job, (record[JobNeeds.RecordSexAt] & Woman) != 0);
            if (named == null)
                return false;
            int k = _plan.IndexOf(job), level;
            var view = new ReadOnlySpan<byte>(record, JobProgress.MenuBytes);
            lock (_lock)
            {
                _progress.Looked();
                if (k >= 0 && _plan.GameSlots[k] >= 0)
                {
                    // (1.55.0) The game's Dark Knight or Onion Knight a mod gives: the unit's own level, the framework's test.
                    level = JobNeeds.GameLevel(view, _plan.GameSlots[k]);
                    if (closed < 0)
                        closed = OpenTo(k, record) ? 0 : Anyone(k) ? 1 : 2;
                }
                else if (k >= 0)
                {
                    level = _progress.Level(k, _progress.IndexOf(record));
                    if (closed < 0)
                        closed = OpenTo(k, record) ? 0 : Anyone(k) ? 1 : 2;
                }
                else
                {
                    int slot = JobNeeds.Known(job, ReadOnlySpan<short>.Empty);
                    level = JobNeeds.GameLevel(view, slot);
                    if (closed < 0)
                        closed = JobNeeds.GameOpen(view, slot) ? 0 : AnyoneGame(slot) ? 1 : 2;
                }
            }
            JobNeeds.Stand(new Span<byte>((void*)to, JobNeeds.PlaceBytes), named.Value.Name, named.Value.Icon, level, job, closed);
            return true;
        }
    }
}
