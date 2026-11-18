// Mod Studio Framework: (1.36.0 to 1.37.0) where a mod's own job goes in the game. Part of
// The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Measured on his program (read as data, never run), the eleven job numbers no
// generic unit, story unit or monster has among the game's 174 records and
// Dark Knight & Onion Knight (Generic) or WotL Restoration don't take: 142, 143,
// 146 to 149 and 155 to 159 (dev/research/sidequests/jobs.py).
//
// A unit keeps each generic job's progress in a row of its record, by the job's
// slot (the game's 0x2B8F18: 74 to 93 are 0 to 19, 160 and 161 are 20 and 21,
// anything else 0). The record has words of JP and total JP for 23 slots and
// nibbles of level for 24, but learned abilities for 22 rows. So a mod's job has
// slot 22: its JP, total JP and level are the unit's own, kept in the save. Its
// abilities are for now one of the generic jobs' skillsets (5 to 23), and what it
// has learned of them is kept apart from that job's in Mime's row 19, which is
// never used (1.36.3, from test 76; it had shared that job's row): the battle
// finds a unit's learned abilities of such a skillset by the skillset
// (0x3170CC, 0x30E368: skillset less 5), so both are told that the job's own
// skillset, on a unit in that job, is that row. One job at a time, until the
// store of more than one is built (his choice: "what ever allows for 22
// completlely new jobs or more").
//
// Everything here works by the job numbers given: the game's own functions are
// stepped into only where a number given to a mod's job is met (`Code`).
//
// (1.36.2, from test 75) A job's cell on the job screen is drawn by the job only
// for the game's generic jobs, the unit's own sprite for any other job (0x368424),
// so the cell reads the job it looks like. An ability learned is written by the
// slot too (0x28936C), and a second list of a job's abilities reads by it
// (0x392620). And a level of 0 is the game's "--" on the unit's card (0x29B5CC):
// the card shows the menu's copy of a unit's levels, made once as the menu opens
// (0x284A08), and slot 22's is 0 until something has counted it, so it is
// counted just before that copy.
//
// (1.36.3, from test 76) A level is counted from the JP table's level 1 on, which
// needs 100: below 100 the level is 0, the card's "--". The game never lets that
// be seen, because a unit gets 100 to 199 JP in every job as it is made
// (0x2770BC, its random number), so a unit's slot 22 is given the same, by that
// function, the first time the menu finds it has no level. And the unit atlas
// (0x2897B4, read as a job is changed) is by the job too: past the game's jobs
// it reads whatever is there, which for a woman's place is a size that stops the
// game, so it reads the job the mod's job looks like.
//
// (1.37.0, his word on test 77) A job's own skillset. The game has 176 skillset
// records of 25 bytes (0x67E210; 0x275860 reads an ability of one), 58 of them
// empty and named by no job: the job is given one (Numbers.json's Skillsets), its
// record written there, its name the row of that number in JobCommand (sheet
// 0x29, read by 0xF84F4). The battle's two readers take a skillset that is no
// generic job's as Squire's row when it is the unit's own and as wholly learned
// when it is the unit's second, so both are told that the job's skillset is the
// job's row, whoever has it: a unit in another job that takes it as its second
// has what it learned in the job, and the job's unit that takes the Black Magicks
// has what it learned as a Black Mage.
//
// (1.41.3, his test 96) Arithmeticks. The battle's list of the spells it can cast
// (0x30EA38) goes through four skillsets written in its own code (10, 11, 12 and
// 16: White, Black and Time Magicks and the Mystic Arts), lists what the unit has
// learned of each by the menu's list maker (0x30E368, where a job's skillset is
// the job's row) and keeps each spell whose action record says "Castable with
// Arithmeticks". A job's own skillset is not among the four, so what a unit learned
// in it was never listed, though its page said so (his Flame Lance and Mending
// Light). The list's round reads its skillset from a list of the framework's: the
// game's four, then each job's own in the order the jobs are given. A spell is kept
// once (a game's spell in a job's skillset, as Haste in Battle Magicks, may be
// learned in its own job too), only where it has an action record (a job's
// skillset may hold an item's, a jump's, a charge's or a throw's number, as test
// 86's Alchemist, Lancer, Marksman and Shade do, which has none: the game would
// read its flag at address 5, never having met one in its four) and while the list
// holds fewer than 64: the battle menu's lists have room for 80 and the counter's
// (0x30E174) for more, and the game's four hold 57 abilities. Found apart from the
// jobs' places: a job is a job without it.
//
// (1.41.4, his word on test 97: "all Arithmeticks should be able to use new
// abilities as well just like we can now, enemies, charmed, or confused") The units
// the game moves choose an Arithmeticks spell in two routines of their own, over
// the same four (a table at 0x684E44). The thinking one (0x388EB4, a walk the look
// at a unit's actions comes back to) keeps the spell as its word's low byte (550,
// Mending Light, would be 38, Float) and passes over a word whose low byte is 0; it
// goes through the framework's list, keeps the whole word in a cell of the
// framework's (the game's byte as before) and reads the word where it read the
// byte. The random one (0x38BF34, a confused unit's) picks one of the four by the
// game's random number and 3: it picks one of the list by the number less every
// whole multiple of the list's length, with as many more tries as the list is
// longer (256 for each four). Both pass over a word with no action record, as the
// player's list does.
//
// (1.42.0, the road's step 5) A job with sprites of its own (SpriteRoom.cs): the
// routines that make a sprite from a job (the sprite set, the five portraits', the
// face's, the job screen's cell) are handed the job number its own sprites are made
// from where they were handed the job it looks like, and the atlas of units its
// Look's place.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Reflection;
using System.Text;

namespace ModStudioEventSetup
{
    public static class JobRoom
    {
        /// <summary>The JobCommand table's sheet (a skillset's name, as 0xF84F4 asks for it), a row's fixed part and its
        /// fields' places: its icon, its name, description and second description (from the row + 8), the skillset it is
        /// the same command as, its comment (from the row).</summary>
        public const int CommandSheet = 0x29, CommandRowBytes = 0x24, CommandNameAt = 8, CommandDescriptionAt = 0xC,
                         CommandDescription2At = 0x10, CommandSameAt = 0x14, CommandCommentAt = 0x18;
        /// <summary>A skillset's record: three bytes of ninth bits (16 actions, then 6 others, the first the highest
        /// bit), 16 action abilities' low bytes, 6 others'.</summary>
        public const int SkillsetBytes = 25, SkillsetCount = 176, SkillsetActionsAt = 3, SkillsetOthersAt = 19;
        /// <summary>The skillset numbers free in the game, in the order they are given: their record empty, no job's.</summary>
        public static readonly int[] FreeSkillsets =
        {
            77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 105, 106, 109,
            110, 113, 114, 117, 118, 121, 122, 127, 128, 129, 130, 131, 132, 133, 142, 143, 144, 145, 146, 147, 148, 149, 150,
            151, 152, 153, 154, 165, 166, 169,
        };
        /// <summary>The Job table's sheet, as the game asks for it (0x2CBED4, 0xF8574).</summary>
        public const int JobSheet = 0x2E;
        public const int RecordBytes = JobFile.RecordBytes, JobCount = 174;
        /// <summary>A mod's job's slot: past the game's 22, the last the unit's record has JP and level for.</summary>
        public const int Slot = 22;
        /// <summary>(1.55.0) The game's Dark Knight's slot and learned row, the unit's own (the game's 0x2B8F18).</summary>
        public const int DarkSlot = 20;
        /// <summary>The generic jobs' skillsets: 5 to 23 (Squire to Dancer, in the game's order), each its job's row of
        /// learned abilities (the skillset less 5), as the battle finds it.</summary>
        public const int FirstSkillset = JobFile.FirstSkillset, LastSkillset = JobFile.LastSkillset;
        /// <summary>The first generic job, the first row of GeneralJob (each generic job's JP table).</summary>
        public const int FirstGeneric = 74;
        /// <summary>How many of the mods' jobs can be given at once until a unit keeps more than one's progress.</summary>
        /// <summary>(1.38.0) The two cells the native code reads, a page past where it starts: the job loaded in every
        /// unit's slot 22 and row 19 (its place among the jobs given, a number of four bytes), and the framework's
        /// function that loads another (JobProgress.Swap, through JobHooks).</summary>
        public const int CellsAfter = 0x8000, CellsRoom = 0x1000, LoadedCell = 0, SwapCell = 8;
        /// <summary>(1.38.1) A third cell: the framework's function told of the game's copy of the battle, through
        /// JobHooks. (1.38.2) Told before the game takes the copy (RetryCopied), after it has put the party's records
        /// and the units back (RetryPart) and after it has put the rest back (RetryWhole).</summary>
        public const int RetryCell = 16, RetryCopied = 0, RetryPart = 1, RetryWhole = 2;
        /// <summary>(1.39.0) Two more cells, for the job screen's own rows (JobScreen, through JobHooks): the framework's
        /// function told the game's list of a unit's jobs is made, and its step between the screen's rows.</summary>
        public const int ScreenListCell = 24, ScreenVerticalCell = 32, ScreenTreeCell = 40, ScreenSidesCell = 48;
        /// <summary>(1.39.3) The framework's own function told after each of the game's fillings of the job screen;
        /// (1.39.5) a number the job screen's end makes 0 (JobScreen sets it while a screen it arranged is there).</summary>
        public const int ScreenAfterCell = 64, ScreenAliveCell = 72;
        /// <summary>(1.39.4) The cell of the framework's own step from one job to the next on the abilities' page.</summary>
        public const int ScreenCycleCell = 80;
        /// <summary>(1.48.0) Three more cells, for what opens a job (JobNeeds, through JobHooks): the framework's own
        /// showing of the window of what a job needs; its answer to whether a job is open to a unit (the menu's
        /// record's number, the job's number); and the unit the list of second skillsets is being made for (a number
        /// of four bytes, written by the native code as the game asks that list).</summary>
        public const int ScreenNeedsCell = 96, OpenCell = 104, UnitCell = 112;
        /// <summary>(1.49.0) One more, for the mods' jobs on Job Progress (JobTree, JobScreen.Harvest): a number of four
        /// bytes that isn't 0 while the game's filling is run for the mods' jobs alone. The native code then leaves out
        /// the filling's readying of the screen and its giving of a job to the screen's place.</summary>
        public const int ScreenHarvestCell = 120;
        /// <summary>(1.55.1) One more, for the game's Onion Knight's words on Job Summary: the framework's answer to which
        /// row of the job help table a key asks for (JobAsker.SummaryKey, through JobHooks).</summary>
        public const int SummaryCell = 128;

        /// <summary>The job numbers free in the game, in the order they are given.</summary>
        public static readonly int[] FreeNumbers = { 142, 143, 146, 147, 148, 149, 155, 156, 157, 158, 159 };

        /// <summary>A Job row's fixed part and its fields' places.</summary>
        public const int RowBytes = 0x40, RowFirstWord = 4, RowNameAt = 8, RowUnknown4At = 0xC, RowDescriptionAt = 0x10,
                         RowUnknown6At = 0x14, RowCommandAt = 0x20, RowHideTreeAt = 0x3C, RowWordsFrom = 8;

        /// <summary>A mod's job with the number it was given.</summary>
        public sealed class Given
        {
            public ModJob Job { get; }
            public int Number { get; }
            /// <summary>The number of its own skillset.</summary>
            public int Skillset { get; }
            /// <summary>(1.42.0) Its own sprites: the man's number (the woman's is the next), or -1 when it has none (it
            /// looks like its Like). SpriteRoom.Plan gives it.</summary>
            public int Sprite { get; internal set; } = -1;
            /// <summary>(1.44.0) Whether its own sprites wear textures of its own, its man's and its woman's: its Look gives
            /// them and the framework answers them (SpriteTextures.Arm).</summary>
            public bool[] Textures { get; } = new bool[2];
            /// <summary>(1.45.0) Whether its own sprites have portraits of its own, its man's and its woman's: its Look gives
            /// them and the framework sends their portraits to them (SpritePortraitHooks.Arm).</summary>
            public bool[] Portraits { get; } = new bool[2];
            /// <summary>(1.46.0) Whether its own icon, its skillset's own icon and its pictures (the man's, the woman's: its
            /// own or the game's it picks) are answered by the framework (JobArtHooks.Arm).</summary>
            public bool IconOwn { get; internal set; }
            public bool CommandOwn { get; internal set; }
            public bool[] Pictures { get; } = new bool[2];

            public Given(ModJob job, int number, int skillset)
            {
                Job = job;
                Number = number;
                Skillset = skillset;
            }

            /// <summary>(1.55.0) Whether it is the game's own Dark Knight or Onion Knight (its number the game's, its
            /// progress the unit's own rows), not a job of its mod's own.</summary>
            public bool Game => Job.Game != 0;

            /// <summary>(1.42.0) The job the game's routines that make a sprite from a job are handed for it: the one its
            /// own sprites are made from, or the job it looks like.</summary>
            public int Drawn => Sprite >= 0 ? SpriteRoom.Virtual(Sprite) : Job.Like;
            /// <summary>(1.42.0) The job whose place in the atlas of units it takes: its Look's with sprites of its own.</summary>
            public int Atlas => Sprite >= 0 ? Job.LookLike : Job.Like;
        }

        // --- the game's places ----------------------------------------------------------------------------------------

        sealed class Site
        {
            public string Name { get; }
            public int[] Pattern { get; }
            /// <summary>Where in the pattern the place is, how many bytes it changes (0: read only).</summary>
            public int Lead { get; }
            public int Length { get; }

            public Site(string name, string pattern, int lead, int length)
            {
                Name = name;
                Pattern = Places.Pattern(pattern);
                Lead = lead;
                Length = length;
            }
        }

        const string LeaTwice = "8D 0C 45 CC FF FF FF 3C 5D";

        static readonly Site[] Sites =
        {
            // The job's slot: its first two instructions (a jump to the stand in).
            new Site("Slot", "0F B7 D1 8D 42 B6 66 83 F8 13 77 06 66 83 C2 B6 EB 1D B9 A0 00 00 00", 0, 6),
            // A unit's sprite set: its job read (0x278EDC).
            new Site("Sprite", "45 0F B6 C8 4C 8B D1 C6 02 00 41 83 E9 5C", 0, 7),
            // A unit's portrait, in each of the five functions that work it out (a woman's; a man's).
            new Site("Woman1", "41 0F B6 4B 02 B8 35 00 00 00 80 F9 5D 44 8A C9", 5, 5),
            new Site("Man1", "41 0F B6 43 02 44 8A C8 " + LeaTwice, 5, 10),
            new Site("Woman2", "41 0F B6 49 02 B8 35 00 00 00 80 F9 5D 44 8A C1 44 8D 70 FE", 5, 5),
            new Site("Man2", "41 0F B6 41 02 44 8A C0 " + LeaTwice + " 75 92 41 2B CC", 5, 10),
            new Site("Woman3", "41 0F B6 49 02 B8 35 00 00 00 80 F9 5D 44 8A C1 44 8D 58 FE", 5, 5),
            new Site("Man3", "41 0F B6 41 02 44 8A C0 " + LeaTwice + " 75 85 41 2B CB", 5, 10),
            new Site("Woman4", "41 0F B6 49 02 B8 35 00 00 00 80 F9 5D 44 8A C1 44 8D 50 FE", 5, 5),
            new Site("Man4", "41 0F B6 41 02 44 8A C0 " + LeaTwice + " 0F 85 ?? ?? ?? ?? 2B CE", 5, 10),
            new Site("Woman5", "0F B6 4B 02 B8 35 00 00 00 80 F9 5D 8A D1 8D 78 FE", 4, 5),
            new Site("Man5", "0F B6 43 02 8A D0 " + LeaTwice + " 75 BE", 4, 9),
            new Site("Face", "0F B6 48 04 0F B6 50 02 C1 E9 07 83 C2 B6 F7 D1 83 E1 01 83 C9 60", 8, 6),
            // The reaches of a unit's learned row by the job's slot: three calls of the slot used for nothing else...
            new Site("RowBattle", "0F B6 4B 03 44 0F B6 7B 12 E8 ?? ?? ?? ?? 48 63 C8 48 83 C1 36", 9, 5),
            new Site("RowMenu", "C6 05 ?? ?? ?? ?? 01 4C 8B E0 E8 ?? ?? ?? ?? 48 0F BF D0 48 83 C2 36", 10, 5),
            new Site("RowUnit", "0F B6 8B 48 FE FF FF E8 ?? ?? ?? ?? 48 63 D0 41 8B FB 48 83 C2 36", 7, 5),
            // ...and two reading the slot for its JP first, then the row.
            new Site("RowList", "48 8D 50 29 48 8D 04 51 48 03 D0", 0, 8),
            new Site("RowMake", "49 8D 48 29 48 8D 04 4A 48 03 C8", 0, 8),
            // ...the writing of an ability learned (0x28936C, a call of the slot used for nothing else)...
            new Site("RowLearn", "0F B7 CD E8 ?? ?? ?? ?? 4C 8D 25 ?? ?? ?? ?? 48 63 F8", 3, 5),
            // ...and the second list of a job's abilities (0x392620: the slot in rsi, read into rcx just before).
            new Site("RowSecond", "48 0F BF CE 8B FD 48 83 C1 29", 0, 6),
            // A job's cell on the job screen: the job read to choose the sprite it shows (0x368424).
            new Site("Cell", "0F B6 4D E8 41 8D 46 3D 89 45 FC 41 BA 01 00 00 00", 0, 8),
            // A unit's place in the atlas of units, by its job and sex (0x2897B4: its first instruction).
            new Site("Atlas", "48 89 5C 24 08 48 89 74 24 10 48 89 7C 24 18 48 8D 35 ?? ?? ?? ?? 4D 8B C8 44 0F B7 D2 66 83 F9 34", 0, 5),
            // The battle's two readers of a unit's learned abilities by the skillset.
            new Site("LearnedBattle", "8D 4A FB 83 F9 12 76 ?? 81 FA E0 00 00 00", 0, 6),
            new Site("LearnedList", "41 8D 47 FB 3C 12 77 06 41 8D 47 FB EB ??", 0, 6),
            // The menu's copy of a unit's levels (0x284A08: its first instruction).
            new Site("LevelCopy", "F2 0F 10 47 74 F2 0F 11 83 BD 00 00 00", 0, 5),
            // GeneralJob, each generic job's JP table, by the slot (0x2CC008's first instruction).
            new Site("Table", "48 89 5C 24 10 48 89 74 24 18 57 48 83 EC 20 48 8B 05 ?? ?? ?? ?? 33 F6 48 63 FA 8B D9", 0, 5),
            // A unit's levels from its total JP, its two callers.
            new Site("LevelsA", "48 8D 8A AE 00 00 00 48 83 C2 74 E8 ?? ?? ?? ??", 11, 5),
            new Site("LevelsB", "48 8D 8D AE 00 00 00 48 8D 55 74 E8 ?? ?? ?? ??", 11, 5),
            // (1.37.1) The menu's two lists over a unit's jobs, which the game makes of its own jobs alone: the
            // skillsets to choose a second from (0x28A7C0: its count, after its last job) and the reaction, support
            // and movement abilities (0x28A8B0: its first call of the lister, the one for the unit's first job).
            new Site("SecondList", "66 41 3B C3 75 A0 49 63 D0 41 8B C0 66 44 89 54 24 20", 6, 6),
            new Site("OthersList", "8B D0 89 7C 24 20 45 8B C4 4C 8D 4C 24 50 41 0F B7 CF E8 ?? ?? ?? ?? 8B F0 BB 01 00 00 00",
                     18, 5),
            // (1.37.2) A Combat Set's job: the game's test of two jobs being the same job (0xF72F0: its first
            // instruction), and the showing of a set (0x33751C: its call for the unit's list of jobs).
            new Site("SameJob", "48 89 5C 24 08 57 48 83 EC 20 8B DA 3B CA 74 25 E8 ?? ?? ?? ?? 8B CB 48 8B F8 E8 ?? ?? ?? ?? "
                                + "48 85 FF 74 0D 48 85 C0 74 08 8B 48 18 39 4F 18", 0, 5),
            new Site("SetJob", "48 89 5C 24 62 48 89 5C 24 6C E8 ?? ?? ?? ?? 66 3B D8 7D 46 48 8D BD 88 01 00 00", 10, 5),
            // (1.38.0) Read only, for a unit's progress in more than one job (JobProgress): the making of a battle unit
            // from a party's record (0x276758), the writing of one back (0x274EB8), the writing of a save's state
            // (0x218F78), each at its first instruction and hooked whole; the battle's units (0x1853CE0, by its lea) and
            // the menu's copies of the party's (0x37415A0, as the program names it from its own start).
            new Site("Build", "48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18 57 48 83 EC 20 80 3A 04 48 8B FA 48 8B D9 41 B8 00 "
                              + "01 00 00", 0, 0),
            new Site("WriteBack", "48 89 5C 24 10 48 89 6C 24 18 56 57 41 54 41 56 41 57 48 83 EC 20 8A 59 06 45 33 E4 8A 01 "
                                  + "80 E3 01 48 8B F1 3C 7F", 0, 0),
            // (2.0.1, his test 126) Found from its fifteenth byte, as the items' Save (ItemRoom) is: it is the same
            // function, and the items hook it before the jobs' places are found (Mod.PlanItems before Mod.PlanJobs),
            // their jump over its first 14 bytes. Test 126 found no SaveWrite so and gave no job.
            new Site("SaveWrite", "41 56 41 57 48 83 EC 40 48 8B 05 ?? ?? ?? ?? 44 8B E1 B9 2F 00 00 00", -14, 0),
            new Site("Battle", "4C 8D 0D ?? ?? ?? ?? 4C 63 D6 49 C1 E2 09 43 80 7C 0A 01 FF", 0, 0),
            new Site("Menus", "4B 8D 3C B6 4C 8B C5 48 C1 E7 07 4C 8D 3D ?? ?? ?? ?? 49 8D 9F ?? ?? ?? ??", 21, 0),
            // (1.38.1, test 81) Read only: the battle's own records of its units (0x3C46770, by the lea of their maker,
            // 0x360780) and the one record on its own (0x3C51F10: its maker's first store, 0x39231C, is of the job's
            // word, 0x24 into it).
            new Site("BattleRecords", "48 8D 05 ?? ?? ?? ?? 8B EF 4C 8D 25 ?? ?? ?? ?? 40 38 3D", 0, 0),
            new Site("OneRecord", "48 89 5C 24 08 57 48 83 EC 20 0F B6 41 03 48 8B D9 66 89 05 ?? ?? ?? ?? 33 FF 8A 41 06 88 05",
                     17, 0),
            // (1.38.1) A battle started again: the game's two calls to take its copy of the battle (0x2CDBC4) and its
            // two to put it back (0x2CE5C8 the battle's units, then 0x2CE7A8 the whole), each call stepped into.
            new Site("RetryCopyA", "41 8B CE 44 89 2D ?? ?? ?? ?? E8 ?? ?? ?? ?? C7", 10, 5),
            new Site("RetryCopyB", "44 39 2D ?? ?? ?? ?? 75 0D 33 C9 E8 ?? ?? ?? ?? 89 35", 11, 5),
            new Site("RetryPart", "E8 ?? ?? ?? ?? E8 ?? ?? ?? ?? 83 CB FF 48 8D 0D ?? ?? ?? ?? 8B D3 41 B8 54 00 00 00", 5, 5),
            new Site("RetryWhole", "41 8A F6 E8 ?? ?? ?? ?? E8 ?? ?? ?? ?? 8B 05 ?? ?? ?? ?? 83 C0 FD 41 3B", 8, 5),
            // (1.38.2, test 82) Read only. Three functions at their first instruction, hooked whole: the maker of a
            // record of a battle unit (0x360048), the copier of a battle unit's progress for a view (0xFCF80), and the
            // putting back of the plain state as a battle is started again from its start (0x2CF768). And the game's
            // copy of the battle's variables (0x81A0E8), by the two leas of its taking (0x2CDBC4): the copy's, then the
            // variables' own.
            new Site("Made", "48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18 57 41 54 41 55 41 56 41 57 48 81 EC 80 00 00 00 48 "
                             + "8B DA 48 8B F9 48 8B CB 33 D2 41 B8 80 02 00 00", 0, 0),
            new Site("Shown", "40 55 48 8D AC 24 20 FE FF FF 48 81 EC E0 02 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 89 85 D0 01 "
                              + "00 00 4C 8B CA BA 14 00 00 00 3B CA", 0, 0),
            new Site("Restart", "48 89 5C 24 08 57 48 83 EC 30 BA 01 00 00 00 E8 ?? ?? ?? ?? 48 8D 05 ?? ?? ?? ?? 48 89 44 24 "
                                + "28 4C 8D 0D", 0, 0),
            new Site("CopyBank", "48 8D 05 ?? ?? ?? ?? 48 8D 0D ?? ?? ?? ?? 8D 72 78 0F 10 01", 0, 0),
            // (1.38.3, test 83) Read only. Two functions at their first instruction, hooked whole, each of which copies
            // a record of the menu's for the status card before the job's slot is asked: the menu's update of the card
            // (0x2BD05C; its first instructions name the word that says which record, 0x1811428, and the menu's table
            // of its records, 0x1800F50) and the card made of a record handed to it (0x2C33D0).
            new Site("Status", "48 8B C4 48 89 58 08 48 89 70 10 48 89 78 18 4C 89 60 20 55 41 55 41 56 48 8D A8 28 FC FF FF "
                               + "48 81 EC C0 04 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 89 85 B0 03 00 00 48 0F BF 35 ?? ?? ?? "
                               + "?? 4C 8D 2D ?? ?? ?? ?? 49 8B 5C F5 00", 0, 0),
            new Site("Card", "40 55 48 8D AC 24 30 FE FF FF 48 81 EC D0 02 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 89 85 C0 01 "
                             + "00 00 0F B7 41 20 BA 04 00 00 00 0F 10 01", 0, 0),
            // Read only: the skillset records (0x275860: where they are, from the program's start); the JP a unit's job
            // starts with; the level of one slot's total JP; the job records.
            new Site("Skillsets", "48 63 C1 4C 8D 15 ?? ?? ?? ?? 4C 6B C0 19 41 8B C1 99 83 E2 07 03 C2 8B C8 83 E0 07 C1 F9 03 2B "
                                  + "C2 48 63 C9 49 03 C8 42 0F B6 94 11", 44, 0),
            new Site("StartJp", "48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18 57 41 56 41 57 48 83 EC 20 49 63 F8 33 DB 41 8B E9 4C 8B F9 83 FF 12", 0, 0),
            new Site("LevelOf", "0F B7 16 8B CF E8 ?? ?? ?? ?? 0F B7 56 02", 5, 0),
            new Site("Records", "41 BB AE 00 00 00 4C 8D 35 ?? ?? ?? ?? 66 41 3B D3", 6, 0),
        };

        /// <summary>What was found of the game's program.</summary>
        public sealed class Found
        {
            public List<string> Missing { get; } = new List<string>();
            public Dictionary<string, int> At { get; } = new Dictionary<string, int>();
            public int Records { get; set; }
            public int LevelOf { get; set; }
            public int Levels { get; set; }
            public int StartJp { get; set; }
            public int Skillsets { get; set; }
            /// <summary>(1.38.0) The battle's units and the menu's copies of the party's.</summary>
            public int Battle { get; set; }
            public int Menus { get; set; }
            /// <summary>(1.38.1) The battle's own records of its units, and the one record on its own.</summary>
            public int BattleRecords { get; set; }
            public int OneRecord { get; set; }
            /// <summary>(1.38.2) The game's copy of the battle's variables, and the variables it is taken from.</summary>
            public int CopyBank { get; set; }
            public int CopyBankOf { get; set; }
            /// <summary>(1.38.3) The word that says which of the menu's records the status card is of, and the menu's
            /// table of its records (a pointer a record).</summary>
            public int MenuIndex { get; set; }
            public int MenuTable { get; set; }
            public bool Ok => Missing.Count == 0;
        }

        static int I32(ReadOnlySpan<byte> b, int at) => BinaryPrimitives.ReadInt32LittleEndian(b.Slice(at, 4));

        // --- the job screen's own rows (1.39.0) -----------------------------------------------------------------------

        /// <summary>(1.39.0) The job screen's places in the program, found apart from the jobs' own: only a game
        /// without Dark Knight &amp; Onion Knight (Generic) needs them, and a job is a job without them.</summary>
        static readonly Site[] ScreenSites =
        {
            // The filling of the job screen (0x368424), past its first instructions: the game's interface named.
            new Site("Fill", "48 8D A8 08 F9 FF FF 48 81 EC D0 07 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 89 85 C0 06 00 00 48 8B "
                             + "05 ?? ?? ?? ?? 4C 8D 25 ?? ?? ?? ?? 48 8B 48 10 48 0F BF 05 ?? ?? ?? ?? 48 8B 59 58", 0, 0),
            // Its screen taken from the unit screens' holder, before the screen is readied for the list.
            new Site("FillScreen", "48 8B 4B 78 48 85 C9 74 18 48 8B 53 50 48 85 D2 74 0F 48 81 C2 88 17 00 00 44 8A C7 E8", 0, 0),
            // Its readying of the screen (0x12EA68): the cursor's place forgotten while the screen's state is 2 or less.
            new Site("Ready", "83 BF 40 4A 00 00 02 7F 07 83 8F 48 4A 00 00 FF", 0, 0),
            // Its call of the game's lister of a unit's jobs (0x28662C: the unit, the list, 3), its count kept after.
            new Site("List", "8A 0D ?? ?? ?? ?? 48 8D 15 ?? ?? ?? ?? 41 B8 03 00 00 00 E8 ?? ?? ?? ?? 66 89 05 ?? ?? ?? ??", 19, 5),
            // Each job given to its place and to the job tree's, both by its number in the list (the tree is made with
            // the screen and always there; its call, the pattern's last, is changed: 1.39.1).
            new Site("Tree", "48 8B 4F 78 48 85 C9 74 24 45 8B C6 48 8D 55 A0 E8 ?? ?? ?? ?? 48 8B 8F 80 00 00 00 48 85 C9 74 0C "
                             + "45 8B C6 48 8D 55 A0 E8", 0, 0),
            // (1.39.2) Which side of the cursor's place its window goes (in 0x12FC6C): the row the place is in found
            // by the three row ends (the row's number in rdx, its end in eax, the place in r8d), then "its end less
            // the place, 3 or less: the left" (changed: six bytes, the ends the framework's own).
            new Site("Side", "48 8B D3 48 8D 4F 48 8B 01 44 3B C0 7C 12 44 03 E6 48 03 D6 48 83 C1 04 48 83 FA 03 7C E9 EB 0C 41 2B "
                             + "C0 83 F8 03 41 0F 9E C5 7E 06", 32, 6),
            // The cursor's step (0x130DF0): the cursor's place and the three row ends read, the step inside a row
            // asked, then the step between the three rows (the call changed).
            new Site("Vertical", "44 8B B3 48 4A 00 00 48 8D 43 48 33 D2 33 ED 44 8D 42 13 44 3B 30 7C 0F 8B 10 FF C5 48 83 C0 04 "
                                 + "83 FD 03 7C EE EB 03 44 8B 00 41 FF C8 44 89 7C 24 20 45 8B CC 41 8B CE E8 ?? ?? ?? ?? 8B F8 "
                                 + "41 8B D6 41 3B C6 75 7D 33 D2 44 89 7C 24 20 45 8B CC 8B CD 44 8D 42 02 E8 ?? ?? ?? ?? 48 63 "
                                 + "C8 41 8B D6", 87, 5),
            // After the step: the place under the mouse, then the cursor put on its new place and the places drawn.
            new Site("Moved", "8B 83 48 21 00 00 85 C0 78 08 3B C2 74 04 8B F8 EB 08 3B FA 0F 84 ?? ?? ?? ?? 45 33 C0 89 BB 48 4A "
                              + "00 00 8B D7 48 8B CB E8 ?? ?? ?? ?? 48 8B CB 89 7E 04 C6 46 08 01 E8 ?? ?? ?? ??", 0, 0),
            // The places' boxes, in the putting of the cursor on a place (0x131BF8).
            new Site("Slots", "45 33 D2 4C 8D 99 C0 2D 00 00 49 8B 03 4A 89 44 D4 30 4D 3B D1 75 ?? 4D 8B C1 49 C1 E0 08 49 8B 94 "
                              + "18 D8 2D 00 00 48 85 D2 74 ?? 48 83 C2 38", 0, 0),
            // (1.39.3) The game's two calls of the filling: in the menu's handler of the screen, and in its update of
            // the status card (while the menu's mode is one of the job screen's).
            new Site("FillCalled", "0F B7 05 ?? ?? ?? ?? 66 89 05 ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 8B 0D ?? ?? ?? ?? E8", 14, 5),
            new Site("FillCarded", "8D 83 88 FA FF FF 83 F8 0C 77 05 E8 ?? ?? ?? ?? 8B CB 81 E9 B0 04 00 00", 11, 5),
            // (1.39.4) The screen's step on the abilities' and the summary's pages (0x1312C8), where it asks the piece
            // at its + 0x1988 for the step from one job to the next (0x2A7D9C: the piece, what is pressed, what is
            // held, where to say which way): the call is changed.
            new Site("Cycle", "48 8D AB 88 19 00 00 48 8B CD 4C 8D 4C 24 30 45 8B C6 41 8B D7 E8 ?? ?? ?? ?? 83 F8 FF 74", 21, 5),
            // (1.39.3) The job screen's end (its deleting function, 0x12CFA0: the screen ended, 0x12CFD4, then its
            // 0x4A60 bytes given back): the call of the ending is changed, so the framework knows the screen it arranged is gone.
            new Site("Ended", "48 89 5C 24 08 57 48 83 EC 20 8B DA 48 8B F9 E8 ?? ?? ?? ?? F6 C3 01 74 0D BA 60 4A 00 00 48 8B CF "
                              + "E8", 15, 5),
            // A box's showing set by a layout's animation (in 0x400840): written as it is, nothing else told.
            new Site("Opacity", "F3 0F 10 45 B4 40 84 F6 75 0A F3 0F 59 43 6C F3 0F 11 45 B4 F3 0F 11 43 6C", 0, 0),
            // (1.48.0) What opens a job. The screen's change of state to the window of what the job at the cursor
            // needs (state 6, in 0x12FC6C): the window's piece opened, then the window filled (0x1321FC: the call
            // is changed).
            new Site("NeedsCall", "48 8D 8F 68 0A 00 00 45 8A C6 40 8A D6 E8 ?? ?? ?? ?? 48 8B CF E8 ?? ?? ?? ?? E9", 21, 5),
            // In that window: the slot of the job at the cursor asked (0x2B8F18), GeneralJob's row read by it; and,
            // for each needed job, the slot of each of the 19 places' jobs asked until one is the needed job's. Both
            // calls are changed: a mod's job answers a number of its own.
            new Site("NeedsSlot", "0F B7 8C 19 C8 22 00 00 E8 ?? ?? ?? ?? 8B D0 B9 BD 00 00 00 E8", 8, 5),
            new Site("NeedsSame", "42 8B 3C 30 41 0F B7 0A E8 ?? ?? ?? ?? 3B C7 74 ?? BA 01 00 00 00 49 81 C2 94 00 00 00", 8, 5),
            // The one call of the list of second skillsets (0x28A7C0, from the menu's lister 0x28A6E8: the unit's
            // record's number in cx): changed, so the unit is known where the mods' jobs' skillsets are added.
            new Site("SecondCall", "45 85 C0 75 ?? 49 8B D1 0F B7 CB E8 ?? ?? ?? ?? EB", 11, 5),
        };

        /// <summary>(1.55.0) The five portrait routines' second read of the job (dark_onion.py's PORTRAITS): after the
        /// formula the Woman and Man places change, each reads the unit's job again and gives a generic unit in 160 the
        /// portrait 0x68 and in 161 or 164 0x6A (a woman's one more). The read and the subtraction of 160 (12 bytes, or 10
        /// where the register is ecx) are changed: the game's own Dark Knight or Onion Knight a mod gives reads the job its
        /// look is drawn from there too, as a mod's job does. Found apart: only a game job given needs them.</summary>
        static readonly Site[] SpecialSites =
        {
            new Site("Special1", "45 0F B6 4B 02 41 81 E9 A0 00 00 00 74 ?? 41 83 E9 01 74 06 41 83 F9 03 75", 0, 12),
            new Site("Special2", "45 0F B6 41 02 41 81 E8 A0 00 00 00 74 ?? 41 83 E8 01 74 0A B8 03 00 00 00 44 3B C0 75", 0, 12),
            new Site("Special3", "45 0F B6 41 02 41 81 E8 A0 00 00 00 74 ?? 41 83 E8 01 74 06 41 83 F8 03 75", 0, 12),
            new Site("Special4", "45 0F B6 41 02 41 81 E8 A0 00 00 00 0F 84 ?? ?? ?? ?? 41 83 E8 01 74 09 44 3B C3 0F 85", 0, 12),
            new Site("Special5", "0F B6 4B 02 81 E9 A0 00 00 00 74 ?? 83 E9 01 74 05 83 F9 03 75", 0, 10),
        };
        /// <summary>(1.55.0) Each special site's register as a Like stand in compares and moves it (the instructions' bytes
        /// up to their value) and how long its read is (the rest of the site is the subtraction).</summary>
        static readonly (string Compare, string Move, int Read)[] SpecialRegisters =
        {
            ("41 80 F9", "41 B1", 5), ("41 80 F8", "41 B0", 5), ("41 80 F8", "41 B0", 5), ("41 80 F8", "41 B0", 5),
            ("80 F9", "B1", 4),
        };

        /// <summary>(1.55.0) The five portrait routines' second read of the job, each found once by its bytes: where (by
        /// name), or the missing ones said.</summary>
        public static Dictionary<string, int> FindSpecial(ReadOnlySpan<byte> image, List<Section> sections, List<string> missing)
        {
            var at = new Dictionary<string, int>();
            foreach (var s in SpecialSites)
            {
                var matches = Places.Search(image, sections, s.Pattern);
                if (matches.Count != 1)
                    missing.Add($"{s.Name} ({matches.Count} places like it, not 1)");
                else
                    at[s.Name] = matches[0] + s.Lead;
            }
            return at;
        }

        /// <summary>The JobCommand table's line once the skillsets' names are written: how many (1.55.0: the jobs that
        /// have a skillset, the game's Onion Knight none).</summary>
        public static string CommandLine(int named)
            => $"JobCommand: the mods' jobs' {named} skillset{(named == 1 ? "'s name" : "s' names")} written.";

        /// <summary>(1.55.0) What the log says where the five second reads aren't found: the game's Dark Knight and Onion
        /// Knight keep the game's own portrait numbers there.</summary>
        public static string SpecialNotLine(IList<string> missing, string program, string name)
            => $"the game's Dark Knight and Onion Knight keep the game's own portraits in some places: {string.Join(", ", missing)} "
               + $"wasn't found in {program}. A game update may have changed it: look for a newer {name}.";

        /// <summary>(1.55.1, Zodi's words of 15 November: "after every base game job is mastered making Onion Knight lvl 8
        /// the description changes") Job Summary's two reads of a job's words (dev/research/sidequests/job_words.py's
        /// SUMMARY_READS, in the job screen's change of state 0x12FC6C): the job at the cursor's Job row asked (0xF8574),
        /// its help key (+ 0x30) handed to the generic getter with the job help table's sheet (0x12F), the row's text
        /// handed to the summary's text box. The getter's call in each is changed: the game's Onion Knight's own key asks
        /// the framework which row to read (its mastered words' where the screen's unit's Onion Knight is level 8). Found
        /// apart: only an Onion Knight given with words for its level 8 needs them.</summary>
        static readonly Site[] SummarySites =
        {
            new Site("Summary1", "E8 ?? ?? ?? ?? 48 85 C0 0F 84 ?? ?? ?? ?? 8B 50 30 B9 2F 01 00 00 E8 ?? ?? ?? ?? 48 85 C0 0F 84 "
                                 + "?? ?? ?? ?? 48 83 C0 08 48 8D 9F 10 49 00 00 48 8B CB 48 63 10 48 03 D0 E8", 22, 5),
            new Site("Summary2", "E8 ?? ?? ?? ?? 48 85 C0 74 ?? 8B 50 30 B9 2F 01 00 00 E8 ?? ?? ?? ?? 48 85 C0 74 ?? 48 83 C0 08 "
                                 + "48 8D 9F 10 49 00 00 48 8B CB 48 63 10 48 03 D0 E8", 18, 5),
        };

        /// <summary>(1.55.2, Zodi's word on test 123: "the description for Onion Knight is still not correct") The job
        /// screen's window shows a job's description by the UI table's text 1019, "&lt;jobhelp(lnum0, lnum1)&gt;" (the job, the
        /// unit's sex), which the game's text maker turns into the Job row's words (dev/research/sidequests/job_words.py's
        /// HELP_WORDS): its tag reader (0xF2648) names a job's name ("jobname") or its words ("jobhelp", one more) and calls
        /// the Job row's words' reader (0xF4800: the words wanted, the job's key, the sex; the Job table's sheet, 0x2E,
        /// handed to the generic getter) from one place for both. That call is changed: the game's Onion Knight's words ask
        /// the framework which row to read (JobAsker.SummaryKey, as Job Summary's do: the row of the job the game takes a
        /// level 8 Onion Knight's words from, 164, where the screen's unit's Onion Knight is level 8). Found apart: only an
        /// Onion Knight given with a description for its level 8 needs it.</summary>
        static readonly Site[] HelpWordsSites =
        {
            new Site("HelpWords", "81 3A 6A 6F 62 6E 75 ?? 66 44 39 4A 04 75 ?? 40 38 7A 06 75 ?? 33 D2 44 8B 4B 10 48 8D 4D DF 44 8B "
                                  + "03 E8", 34, 5),
        };
        /// <summary>(1.55.2) Where the reader the call names begins: its own first bytes, the last the Job table's sheet
        /// handed to the getter (mov ecx, 0x2E).</summary>
        public const string HelpWordsReaderBytes = "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 8B DA 48 8B F1 41 8B D0 B9 2E 00 00 00";
        /// <summary>(1.55.2) The words the reader is asked for: a job's description (its name is 0).</summary>
        public const int HelpWordsAsked = 1;

        /// <summary>(1.55.2) The job screen's window's call of the reader of a job's words, found once by its bytes, its
        /// reader the Job table's (HelpWordsReaderBytes): where (by name, the reader as "HelpWordsReader"), or the missing
        /// ones said.</summary>
        public static Dictionary<string, int> FindHelpWords(ReadOnlySpan<byte> image, List<Section> sections, List<string> missing)
        {
            var at = new Dictionary<string, int>();
            foreach (var s in HelpWordsSites)
            {
                var matches = Places.Search(image, sections, s.Pattern);
                if (matches.Count != 1)
                    missing.Add($"{s.Name} ({matches.Count} places like it, not 1)");
                else
                    at[s.Name] = matches[0] + s.Lead;
            }
            if (at.Count != HelpWordsSites.Length)
                return new Dictionary<string, int>();
            int reader = CallTarget(image, at["HelpWords"]);
            byte[] begins = Convert.FromHexString(HelpWordsReaderBytes.Replace(" ", ""));
            if (reader <= 0 || reader + begins.Length > image.Length || !image.Slice(reader, begins.Length).SequenceEqual(begins))
            {
                missing.Add("HelpWordsReader (the call doesn't name the reader of a job's words)");
                return new Dictionary<string, int>();
            }
            at["HelpWordsReader"] = reader;
            return at;
        }

        /// <summary>(1.55.2) What the log says where the job screen's window shows the game's Onion Knight's description for
        /// its level 8, and where its call isn't found.</summary>
        public static string HelpWordsLine(string who)
            => $"the job screen's window shows {who}'s description for its level 8 to a unit whose Onion Knight is level 8.";

        public static string HelpWordsNotLine(IList<string> missing, string program, string name)
            => $"the job screen's window shows the game's Onion Knight's own description at every level: {string.Join(", ", missing)} "
               + $"wasn't found in {program}. A game update may have changed it: look for a newer {name}.";

        /// <summary>(1.55.1) Job Summary's two calls of the generic getter, each found once by its bytes, both calls of the
        /// same function: where (by name, the getter as "SummaryGetter"), or the missing ones said.</summary>
        public static Dictionary<string, int> FindSummary(ReadOnlySpan<byte> image, List<Section> sections, List<string> missing)
        {
            var at = new Dictionary<string, int>();
            foreach (var s in SummarySites)
            {
                var matches = Places.Search(image, sections, s.Pattern);
                if (matches.Count != 1)
                    missing.Add($"{s.Name} ({matches.Count} places like it, not 1)");
                else
                    at[s.Name] = matches[0] + s.Lead;
            }
            if (at.Count == SummarySites.Length)
            {
                int getter = CallTarget(image, at["Summary1"]);
                if (getter <= 0 || getter >= image.Length || CallTarget(image, at["Summary2"]) != getter)
                {
                    missing.Add("SummaryGetter (the two reads don't call the same function)");
                    at.Clear();
                }
                else
                    at["SummaryGetter"] = getter;
            }
            else
                at.Clear();
            return at;
        }

        /// <summary>(1.55.1) What the log says where the game's Onion Knight's words for its level 8 are shown, and where
        /// Job Summary's reads aren't found.</summary>
        public static string SummaryLine(string who)
            => $"Job Summary shows {who}'s words for its level 8 to a unit whose Onion Knight is level 8.";

        public static string SummaryNotLine(IList<string> missing, string program, string name)
            => $"Job Summary shows the game's Onion Knight's own words at every level: {string.Join(", ", missing)} wasn't found in "
               + $"{program}. A game update may have changed it: look for a newer {name}.";

        /// <summary>The game's step between rows (0xF6DD4) past its first instructions: its call of the reading of a
        /// step up or down (the step, whether the press is new, and the two it was handed), 0x34 into it.</summary>
        const string StepBytes = "83 64 24 20 00 41 8B C1 44 8B 4C 24 60 41 8B D8 8B FA C6 44 24 68 01 8B F1 49 8D 53 30 44 8B C0 "
                                 + "49 8D 4B E8 E8";
        const int StepBytesAt = 0x10, StepCallAt = 0x34;
        /// <summary>Into the screen's sites: from "Fill" back to the filling's start, on to its naming of the game's
        /// interface (mov rax, [rip + ..]) and of the word that says which record; in "List", the list named (lea
        /// rdx) and the count kept (mov [rip + ..], ax); in "Moved", its two calls.</summary>
        const int FillStartBefore = 0x18, FillRootAt = 0x1F, FillIndexAt = 0x31, ListIndexBefore = 19, ListListBefore = 13,
                  ListCountAfter = 5, MovedPlaceAt = 40, MovedRefreshAt = 55, TreeCallAt = 40;
        /// <summary>(1.49.0) Into "FillScreen", the filling's call of its readying of the screen (0x12EA68); into "Tree",
        /// its call that gives a job to the screen's place (0x12EC5C), before the tree's.</summary>
        public const int ReadyCallAt = 28, PlaceCallAt = 16;
        /// <summary>(1.39.3) In the layouts' move of a box: where it goes on after its first two instructions, and
        /// where it writes the box's place (its first jump's end).</summary>
        /// <summary>(1.48.0) How long the window of what a job needs (0x1321FC) and the list of second skillsets
        /// (0x28A7C0) are at most: a place found has to be inside.</summary>
        const int NeedsWindowBytes = 0x6D2, SecondListBytes = 0xF0;

        /// <summary>(1.39.0) What was found of the job screen.</summary>
        public sealed class Screen
        {
            public List<string> Missing { get; } = new List<string>();
            public Dictionary<string, int> At { get; } = new Dictionary<string, int>();
            /// <summary>The filling's start, the game's interface (a pointer), the list and its count.</summary>
            public int Fill { get; set; }
            public int Root { get; set; }
            public int ListAt { get; set; }
            public int Count { get; set; }
            /// <summary>The game's lister, its step between rows and its reading of a step up or down; its putting of
            /// the cursor on a place, its drawing of the places again and the layouts' move of a box.</summary>
            public int Lister { get; set; }
            public int Step { get; set; }
            public int UpDown { get; set; }
            public int Place { get; set; }
            public int Refresh { get; set; }
            public int Ending { get; set; }
            public int CycleStep { get; set; }
            /// <summary>(1.39.1) The game's giving of a job to the job tree's place.</summary>
            public int TreeJob { get; set; }
            /// <summary>(1.48.0) The game's window of what the job at the cursor needs, and its list of second skillsets.</summary>
            public int Window { get; set; }
            public int SecondWhole { get; set; }
            public bool Ok => Missing.Count == 0;
        }

        // --- Arithmeticks (1.41.3) ---------------------------------------------------------------------------------------

        /// <summary>(1.41.3) The battle's list of Arithmeticks's spells (0x30EA38): its bytes from its naming of the game's
        /// four skillsets (`mov dword [rsp + 0x40], 0x100C0B0A`) to its step to the next one, its three calls' distances
        /// left out. In them: the round's read of its skillset (`mov dl, [rsp + rdi + 0x40]`, then the game's `lea rax,
        /// [rsp + 0x48]`), the test of a spell's record and its keeping (`test byte [rax + 5], 0x40; je` the next; `mov
        /// [rbx], r15w; add rbx, 2; inc ebp`) and the step (`inc rdi; cmp rdi, 4; jl` the round).</summary>
        public const string ArithmeticksPattern =
            "C7 44 24 40 0A 0B 0C 10 44 8A C2 44 8B E1 33 ED E8 ?? ?? ?? ?? 48 85 C0 75 07 33 C0 E9 91 00 00 00 41 80 F8 15 74 08 "
            + "83 C8 FF 66 89 03 EB EB 33 FF 8A 54 3C 40 48 8D 44 24 48 48 89 44 24 38 4C 8D 8C 24 90 00 00 00 48 8D 44 24 60 41 8B "
            + "CC 48 89 44 24 30 4C 8D 84 24 A8 00 00 00 48 8D 44 24 78 48 89 44 24 20 E8 ?? ?? ?? ?? 85 C0 74 32 33 F6 4C 63 F0 85 "
            + "C0 7E 29 44 0F BF BC 74 A8 00 00 00 41 8B CF E8 ?? ?? ?? ?? F6 40 05 40 74 0A 66 44 89 3B 48 83 C3 02 FF C5 48 FF C6 "
            + "49 3B F6 7C D7 48 FF C7 48 83 FF 04 7C 87";
        public const int ArithmeticksRoundAt = 0x31, ArithmeticksRoundLength = 9, ArithmeticksKeepAt = 0x89,
                         ArithmeticksKeepLength = 16, ArithmeticksTestLength = 4, ArithmeticksAddAt = 6,
                         ArithmeticksAddLength = 10, ArithmeticksNextAt = 0xA1, ArithmeticksNextLength = 9;
        /// <summary>The game's four skillsets, in its order; and how many spells the list keeps at most.</summary>
        public static readonly byte[] ArithmeticksGame = { 10, 11, 12, 16 };
        public const int ArithmeticksMost = 64;

        /// <summary>(1.41.3) Where the list's bytes start (from the program's start), or -1 and in words why not.</summary>
        public static int FindArithmeticks(ReadOnlySpan<byte> image, List<Section> sections, out string? missing)
        {
            var matches = Places.Search(image, sections, Places.Pattern(ArithmeticksPattern));
            missing = matches.Count == 1 ? null : $"its list ({matches.Count} places like it, not 1)";
            return matches.Count == 1 ? matches[0] : -1;
        }

        /// <summary>(1.53.0, Zodi's order of 13 November: "jobs in a quest's battle") A unit a battle's file puts in a mod's
        /// job learns nothing of its job: the game's setup of such a unit's abilities (0x2771C8) learns in a loop over the
        /// twenty generic jobs alone (dev/research/sidequests/quest_jobs.py). Its last call of a job's learning (0x2781A8),
        /// the loop's end and, after it, the entry's first skillset read and ebx made 0 (8 bytes, where the framework's call
        /// goes: BattleOwnAt in the pattern); and in one ability's learning (0x2780B0) its learned row's start by the slot
        /// and the next instruction (7 bytes), where slot 22's row is made the job's own.</summary>
        public const string BattleOwnPattern =
            "E8 ?? ?? ?? ?? 83 C6 02 49 FF C5 83 FE 15 0F 82 ?? ?? ?? ?? 8A 45 1D BB 00 00 00 00 FE C8 3C FD 77 10";
        public const string BattleRowPattern = "48 8D 55 36 4D 63 C8 48 8D 0C 17 4C 8D 04 51";
        public const int BattleOwnAt = 20, BattleOwnLength = 8, BattleRowLength = 7;
        /// <summary>(1.53.0) A battle unit as the abilities' setup holds it: its job, its open jobs' last byte (slot 22's bit,
        /// 0x800000 shifted right by 22, is its 2), its level nibbles; the setup's frame (from its rsp in the loop): the sex's
        /// byte, the flag, the second list's count; a battle's entry's job level (its 10th byte's low nibble).</summary>
        public const int BattleUnitJob = 3, BattleOpenLast = 0xA1, BattleOpenBit = 2, BattleLevels = 0xE4,
                         FrameSex = 0x98, FrameFlag = 0x90, FrameSecondCount = 0xA8, EntryJobLevel = 9, MostJobLevel = 8;

        /// <summary>(1.53.0) Where the framework's two pieces go for a unit of a battle's file in a mod's job, and the job's
        /// learning the loop calls, each found once by its bytes: (-1, -1, -1) and why, where any isn't.</summary>
        public static (int Own, int Row, int Learn) FindBattleUnits(ReadOnlySpan<byte> image, List<Section> sections,
                                                                    out string? missing)
        {
            var own = Places.Search(image, sections, Places.Pattern(BattleOwnPattern));
            var row = Places.Search(image, sections, Places.Pattern(BattleRowPattern));
            missing = own.Count != 1 ? $"the battle units' setup of their abilities ({own.Count} places like it, not 1)"
                    : row.Count != 1 ? $"the learning of an ability ({row.Count} places like it, not 1)" : null;
            return missing == null ? (own[0] + BattleOwnAt, row[0], CallTarget(image, own[0])) : (-1, -1, -1);
        }

        /// <summary>(1.53.0) The log's line for it: found, or not and why (`missing`, from FindBattleUnits).</summary>
        public static string BattleUnitsLine(string? missing, string program, string name)
            => missing == null
               ? "A unit a battle's file puts in a mod's job learns its job's abilities as the game's own units learn their "
                 + "job's, at the job level its file gives."
               : $"A unit a battle's file puts in a mod's job knows none of its job's abilities: {missing} wasn't found in "
                 + $"{program}. A game update may have changed it: look for a newer {name}.";

        /// <summary>(1.41.3) The log's line for it: reached, or not and why (`missing`, from FindArithmeticks).</summary>
        public static string ArithmeticksLine(string? missing, string program, string name)
            => missing == null
               ? "Arithmeticks reaches the mods' jobs' own skillsets: a spell a unit has learned in one of them is in its list "
                 + "when it says Castable with Arithmeticks."
               : $"Arithmeticks can't reach the mods' jobs' own skillsets: {missing} wasn't found in {program}. A game update "
                 + $"may have changed it: look for a newer {name}.";

        /// <summary>(1.41.4) The units' thinking choice of an Arithmeticks spell (0x388EB4): its bytes from its bound of the
        /// skillsets' turns to its second read of the kept byte, the distances to the game's memory and calls left out. In
        /// them: the bound and the table's read (25 bytes), the word's low byte read, kept and tested with its record got
        /// and its flag tested (31), and the two reads of the kept byte (7 each); where the table's place is.</summary>
        public const string ArithmeticksThinkPattern =
            "83 F8 04 0F 8D 6A 01 00 00 48 98 BA 01 00 00 00 42 0F B6 8C 20 ?? ?? ?? ?? 89 0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 83 "
            + "25 ?? ?? ?? ?? 00 48 89 05 ?? ?? ?? ?? 33 C0 EB AD 48 63 C8 48 8B 05 ?? ?? ?? ?? 0F B6 14 48 88 15 ?? ?? ?? ?? "
            + "84 D2 74 87 8B CA E8 ?? ?? ?? ?? F6 40 05 40 0F 84 76 FF FF FF 0F B6 0D ?? ?? ?? ?? 44 8B 05 ?? ?? ?? ?? 8B 15 "
            + "?? ?? ?? ?? E8 ?? ?? ?? ?? 85 C0 0F 84 55 FF FF FF 0F B6 0D ?? ?? ?? ?? 41 8B 84 CC ?? ?? ?? ?? 89 05 ?? ?? ?? "
            + "?? E8 ?? ?? ?? ?? 0F B6 48 0B C6 05 ?? ?? ?? ?? 80 48 8D 14 49 0F B6 0D ?? ?? ?? ??";
        public const int ThinkRoundAt = 0, ThinkRoundLength = 25, ThinkTableAt = 0x15, ThinkSpellAt = 0x40,
                         ThinkSpellLength = 31, ThinkReadAt = 0x80, ThinkReadAgainAt = 0xA9, ThinkReadLength = 7;
        /// <summary>(1.41.4) The units' random choice (0x38BF34): its bytes from its pick of one of the four to its test of
        /// the flag. In them: the pick (`and eax, 3` and the table's read, 12 bytes), the bound of the tries (`cmp eax,
        /// 0x100`, 5) and the getter's call with the flag's test (11); where the table's place is.</summary>
        public const string ArithmeticksRandomPattern =
            "83 E0 03 46 0F B6 B4 20 ?? ?? ?? ?? 41 8B CE E8 ?? ?? ?? ?? 44 8B 05 ?? ?? ?? ?? 48 8B D0 8B 05 ?? ?? ?? ?? 8B "
            + "0D ?? ?? ?? ?? 89 05 ?? ?? ?? ?? 8B 05 ?? ?? ?? ?? 8B F8 C1 EF 0B 89 05 ?? ?? ?? ?? C1 E1 0B 33 0D ?? ?? ?? ?? "
            + "33 F9 44 89 05 ?? ?? ?? ?? C1 EF 08 33 F8 33 F9 8B C7 89 3D ?? ?? ?? ?? 83 E0 0F 44 8B F8 0F B7 34 42 8B C3 FF "
            + "C3 3D 00 01 00 00 0F 8F 3D 02 00 00 85 F6 0F 84 3D FF FF FF 41 80 BC F4 ?? ?? ?? ?? 00 0F 8D 2E FF FF FF 8B CE "
            + "E8 ?? ?? ?? ?? F6 40 05 40 74 18";
        public const int RandomPickAt = 0, RandomPickLength = 12, RandomTableAt = 8, RandomTriesAt = 0x70,
                         RandomTriesLength = 5, RandomTestAt = 0x94, RandomTestLength = 11, RandomTries = 0x100;
        /// <summary>(1.41.4) The cell the thinking choice keeps its spell's whole word in (in the cells' page).</summary>
        public const int ArithmeticksSpellCell = 88;

        /// <summary>(1.41.4) Where the two choices' bytes start (from the program's start), or -1 and in words why
        /// not: each found once, each naming the table of the game's four.</summary>
        public static (int Think, int Random) FindArithmeticksUnits(ReadOnlySpan<byte> image, List<Section> sections,
                                                                      out string? missing)
        {
            var think = Places.Search(image, sections, Places.Pattern(ArithmeticksThinkPattern));
            var random = Places.Search(image, sections, Places.Pattern(ArithmeticksRandomPattern));
            var why = new List<string>();
            if (think.Count != 1)
                why.Add($"its thinking choice ({think.Count} places like it, not 1)");
            if (random.Count != 1)
                why.Add($"its random choice ({random.Count} places like it, not 1)");
            if (why.Count == 0)
            {
                int table = I32(image, think[0] + ThinkTableAt);
                if (I32(image, random[0] + RandomTableAt) != table || table < 0 || table + 4 > image.Length
                    || !image.Slice(table, 4).SequenceEqual(ArithmeticksGame))
                    why.Add("its choices (their skillsets aren't the game's four)");
            }
            missing = why.Count == 0 ? null : string.Join(", ", why);
            return missing == null ? (think[0], random[0]) : (-1, -1);
        }

        /// <summary>(1.41.4) The log's line for them: reached, or not and why.</summary>
        public static string ArithmeticksUnitsLine(string? missing, string program, string name)
            => missing == null
               ? "Units the game moves choose Arithmeticks's spells from the mods' jobs' own skillsets too."
               : $"Units the game moves can't choose Arithmeticks's spells from the mods' jobs' own skillsets: {missing} "
                 + $"wasn't found in {program}. A game update may have changed it: look for a newer {name}.";

        /// <summary>(1.39.0) The job screen's places in the game's program, each found once by its bytes, and held to
        /// what the jobs' own places say of the menu's records.</summary>
        public static Screen FindScreen(ReadOnlySpan<byte> image, List<Section> sections, Found found)
        {
            var screen = new Screen();
            foreach (var s in ScreenSites)
            {
                var matches = Places.Search(image, sections, s.Pattern);
                if (matches.Count != 1)
                {
                    screen.Missing.Add($"{s.Name} ({matches.Count} places like it, not 1)");
                    continue;
                }
                screen.At[s.Name] = matches[0] + s.Lead;
            }
            if (!screen.Ok)
                return screen;
            int fill = screen.At["Fill"];
            screen.Fill = fill - FillStartBefore;
            screen.Root = fill + FillRootAt + 7 + I32(image, fill + FillRootAt + 3);
            if (fill + FillIndexAt + 8 + I32(image, fill + FillIndexAt + 4) != found.MenuIndex)
                screen.Missing.Add("Fill (it reads another word than the status card's for which record)");
            int list = screen.At["List"];
            if (list - ListIndexBefore + 6 + I32(image, list - ListIndexBefore + 2) != found.MenuIndex)
                screen.Missing.Add("List (it lists another unit's jobs than the record's)");
            screen.ListAt = list - ListListBefore + 7 + I32(image, list - ListListBefore + 3);
            screen.Count = list + ListCountAfter + 7 + I32(image, list + ListCountAfter + 3);
            screen.Lister = CallTarget(image, list);
            if (list < screen.Fill || list > screen.Fill + 0x200 || screen.At["FillScreen"] < screen.Fill
                || screen.At["FillScreen"] > list || screen.At["Tree"] < list)
                screen.Missing.Add("List (not in the job screen's filling)");
            int vertical = screen.At["Vertical"];
            screen.Step = CallTarget(image, vertical);
            if (screen.Step <= 0 || screen.Step + StepCallAt + 5 > image.Length
                || !Places.At(image, screen.Step + StepBytesAt, Places.Pattern(StepBytes)))
                screen.Missing.Add("Vertical (the game's step between rows isn't as in the game this was made for)");
            else
                screen.UpDown = CallTarget(image, screen.Step + StepCallAt);
            int moved = screen.At["Moved"];
            screen.Place = CallTarget(image, moved + MovedPlaceAt);
            screen.Refresh = CallTarget(image, moved + MovedRefreshAt);
            if (moved < vertical || moved > vertical + 0x100)
                screen.Missing.Add("Moved (not after the step between rows)");
            if (screen.At["Slots"] < screen.Place || screen.At["Slots"] > screen.Place + 0x200)
                screen.Missing.Add("Slots (not in the putting of the cursor on a place)");
            // (1.39.3) Both calls of the filling are calls of the filling found.
            if (CallTarget(image, screen.At["FillCalled"]) != screen.Fill || CallTarget(image, screen.At["FillCarded"]) != screen.Fill)
                screen.Missing.Add("FillCalled (the game's calls of the filling aren't of the filling found)");
            screen.CycleStep = CallTarget(image, screen.At["Cycle"]);
            if (screen.CycleStep <= 0 || screen.CycleStep >= image.Length)
                screen.Missing.Add("Cycle (the step from one job to the next isn't in the program)");
            screen.Ending = CallTarget(image, screen.At["Ended"]);
            if (screen.Ending <= 0 || screen.Ending >= image.Length)
                screen.Missing.Add("Ended (the job screen's ending isn't in the program)");
            // (1.39.1) The filling's call for the job tree, right after its test of the tree being there.
            screen.TreeJob = CallTarget(image, screen.At["Tree"] + TreeCallAt);
            if (screen.TreeJob <= 0 || screen.TreeJob >= image.Length)
                screen.Missing.Add("Tree (its call for the job tree isn't in the program)");
            if (screen.Root <= 0 || screen.ListAt <= 0 || screen.ListAt + 2 * (JobScreen.Places + 1) > image.Length)
                screen.Missing.Add("List (the list isn't in the program)");
            // (1.48.0) The window of what a job needs: its two askings of a job's slot are calls of the slot's
            // function, inside the window; the list of second skillsets called is the one the jobs' own place is in.
            screen.Window = CallTarget(image, screen.At["NeedsCall"]);
            if (screen.Window <= 0 || screen.Window >= image.Length)
                screen.Missing.Add("NeedsCall (the window of what a job needs isn't in the program)");
            foreach (string name in new[] { "NeedsSlot", "NeedsSame" })
                if (!found.At.TryGetValue("Slot", out int slot) || CallTarget(image, screen.At[name]) != slot
                    || screen.At[name] < screen.Window || screen.At[name] > screen.Window + NeedsWindowBytes)
                    screen.Missing.Add($"{name} (not the window's asking of a job's slot)");
            screen.SecondWhole = CallTarget(image, screen.At["SecondCall"]);
            if (!found.At.TryGetValue("SecondList", out int second) || second < screen.SecondWhole
                || second > screen.SecondWhole + SecondListBytes)
                screen.Missing.Add("SecondCall (not the call of the list of second skillsets)");
            return screen;
        }

        /// <summary>(1.38.1) Where a call (E8) at `at` goes, and where in the one record on its own its job's word is.</summary>
        static int CallTarget(ReadOnlySpan<byte> image, int at) => at + 5 + I32(image, at + 1);
        public const int OneRecordJobAt = 0x24;
        /// <summary>(1.38.3) Into the menu's update of the status card (0x2BD05C): its reading of the word that says which
        /// record (movsx rsi, word [rip + ..], eight bytes) and, straight after, its naming of the table (lea r13,
        /// [rip + ..], seven).</summary>
        public const int StatusIndexAt = 0x37, StatusTableAt = 0x3F;

        /// <summary>The places in the game's program, each found once by its bytes.</summary>
        public static Found Find(ReadOnlySpan<byte> image, List<Section> sections)
        {
            var found = new Found();
            foreach (var s in Sites)
            {
                var matches = Places.Search(image, sections, s.Pattern);
                if (matches.Count != 1)
                {
                    found.Missing.Add($"{s.Name} ({matches.Count} places like it, not 1)");
                    continue;
                }
                found.At[s.Name] = matches[0] + s.Lead;
            }
            if (!found.Ok)
                return found;
            int lea = found.At["Records"];
            found.Records = lea + 7 + I32(image, lea + 3);
            int of = found.At["LevelOf"];
            found.LevelOf = of + 5 + I32(image, of + 1);
            found.StartJp = found.At["StartJp"];
            found.Skillsets = I32(image, found.At["Skillsets"]);
            if (found.Skillsets <= 0 || found.Skillsets + SkillsetBytes * SkillsetCount > image.Length)
                found.Missing.Add("Skillsets (the records aren't in the program)");
            int battle = found.At["Battle"];
            found.Battle = battle + 7 + I32(image, battle + 3);
            found.Menus = I32(image, found.At["Menus"]);
            if (found.Battle <= 0 || found.Battle + JobProgress.BattleUnits * JobProgress.BattleBytes > image.Length
                || found.Menus <= 0 || found.Menus + JobProgress.MenuRecords * JobProgress.MenuBytes > image.Length)
                found.Missing.Add("Battle or Menus (the units aren't in the program)");
            int records = found.At["BattleRecords"];
            found.BattleRecords = records + 7 + I32(image, records + 3);
            int one = found.At["OneRecord"];
            found.OneRecord = one + 7 + I32(image, one + 3) - OneRecordJobAt;
            if (found.BattleRecords <= 0 || found.BattleRecords + JobProgress.BattleUnits * JobProgress.MenuBytes > image.Length
                || found.OneRecord <= 0 || found.OneRecord + JobProgress.MenuBytes > image.Length)
                found.Missing.Add("BattleRecords or OneRecord (the records aren't in the program)");
            int copy = found.At["CopyBank"];
            found.CopyBank = copy + 7 + I32(image, copy + 3);
            found.CopyBankOf = copy + 14 + I32(image, copy + 10);
            if (found.CopyBank <= 0 || found.CopyBank + Framework.BankBytes > image.Length)
                found.Missing.Add("CopyBank (the copy of the variables isn't in the program)");
            int status = found.At["Status"];
            found.MenuIndex = status + StatusIndexAt + 8 + I32(image, status + StatusIndexAt + 4);
            found.MenuTable = status + StatusTableAt + 7 + I32(image, status + StatusTableAt + 3);
            if (found.MenuIndex <= 0 || found.MenuIndex + 2 > image.Length
                || found.MenuTable <= 0 || found.MenuTable + 8 * JobProgress.MenuRecords > image.Length)
                found.Missing.Add("Status (the menu's table of its records isn't in the program)");
            foreach (var name in new[] { "RetryCopyA", "RetryCopyB", "RetryPart", "RetryWhole" })
                if (image[found.At[name]] != 0xE8)
                    found.Missing.Add($"{name} (no call there)");
            if (found.Ok && CallTarget(image, found.At["RetryCopyA"]) != CallTarget(image, found.At["RetryCopyB"]))
                found.Missing.Add("RetryCopyB (it calls another function than RetryCopyA does)");
            int levels = found.At["LevelsA"];
            found.Levels = levels + 5 + I32(image, levels + 1);
            int other = found.At["LevelsB"];
            if (other + 5 + I32(image, other + 1) != found.Levels)
                found.Missing.Add("LevelsB (it calls another function than LevelsA does)");
            return found;
        }

        /// <summary>The free skillset numbers still free in this program: their record empty, no job's record naming
        /// them (another mod may have filled one).</summary>
        public static HashSet<int> OpenSkillsets(ReadOnlySpan<byte> image, Found found)
        {
            var open = new HashSet<int>();
            foreach (int n in FreeSkillsets)
            {
                bool empty = true;
                foreach (byte b in image.Slice(found.Skillsets + SkillsetBytes * n, SkillsetBytes))
                    empty &= b == 0;
                for (int job = 0; empty && job < JobCount; job++)
                    empty = image[found.Records + RecordBytes * job] != n;
                if (empty)
                    open.Add(n);
            }
            return open;
        }

        /// <summary>A job's skillset as the game keeps one.</summary>
        public static byte[] SkillsetRecord(ModJob job)
        {
            var record = new byte[SkillsetBytes];
            void Put(int index, int at, int ability)
            {
                record[at] = (byte)ability;
                if (ability > 0xFF)
                    record[index >> 3] |= (byte)(0x80 >> (index & 7));
            }
            for (int n = 0; n < job.Actions.Length; n++)
                Put(n, SkillsetActionsAt + n, job.Actions[n]);
            for (int n = 0; n < job.Others.Length; n++)
                Put(JobFile.MostActions + n, SkillsetOthersAt + n, job.Others[n]);
            return record;
        }

        /// <summary>Each job's number and its skillset's, the same every time (Numbers.json's Jobs and Skillsets); what
        /// can't be given a number or a place is left out, said. A job's record is given its skillset's number.</summary>
        public static List<Given> Plan(IList<ModJob> jobs, Numbers numbers, List<string> said, ICollection<int> openSkillsets,
                                       IList<int>? free = null, string? noGameJobs = null)
        {
            // (1.40.0) `free`: the numbers to give from. The game's eleven free ones, or with them the numbers past
            // the game's last where the longer table of job records can be made (JobRecords.Numbers).
            free ??= FreeNumbers;
            var given = new List<Given>();
            // (1.55.0) The game's own Dark Knight and Onion Knight, as a mod's job gives them: the first mod in the order
            // to give one; none where `noGameJobs` says why (Dark Knight & Onion Knight (Generic) is on). After the mods'
            // own jobs, so each of those keeps its place among the jobs given.
            var games = new List<Given>();
            foreach (var job in jobs)
            {
                if (job.Game != 0)
                {
                    string gameName = JobFile.GameJobName(job.Game);
                    var first = games.Find(g => g.Number == job.Game);
                    if (noGameJobs != null)
                        said.Add($"{job.Who} is left out: {noGameJobs}");
                    else if (first != null)
                        said.Add($"{job.Who} is left out: {first.Job.Who} gives the game's {gameName} first.");
                    else
                        games.Add(new Given(job, job.Game, job.Game == JobFile.DarkKnight ? JobFile.DarkSkillset : 0));
                    continue;
                }
                int number = numbers.Give(Numbers.JobsKind, job.Key, free, _ => true, out _);
                if (number < 0)
                {
                    said.Add(free.Count == FreeNumbers.Length
                        ? $"{job.Who} is left out: the game's {FreeNumbers.Length} free job numbers are all given."
                        : $"{job.Who} is left out: all {free.Count} job numbers are given.");
                    continue;
                }
                if (!free.Contains(number))
                {
                    // (1.40.0) A number past the game's last, kept from when the longer table of job records was made,
                    // where it can't be made now: the job is left out and keeps its number for when it can.
                    said.Add($"{job.Who} is left out: its job number, {number}, is past the game's last, and more job "
                             + "numbers can't be made now.");
                    continue;
                }
                int skillset = numbers.Give(Numbers.SkillsetsKind, job.Key, FreeSkillsets, openSkillsets.Contains, out _);
                if (skillset < 0)
                {
                    said.Add($"{job.Who} is left out: the game's free skillset numbers are all given.");
                    continue;
                }
                job.Record[0] = (byte)skillset;
                given.Add(new Given(job, number, skillset));
            }
            given.AddRange(games);
            return given;
        }

        /// <summary>(1.55.0) Why the game's own Dark Knight and Onion Knight aren't given by a mod's job where Dark Knight
        /// &amp; Onion Knight (Generic) is on: that mod keeps them on its own page.</summary>
        public const string TheirGameJobs = "Dark Knight & Onion Knight (Generic) is on, and it keeps the game's Dark Knight "
                                            + "and Onion Knight on its own page.";

        /// <summary>(1.55.0) The jobs given in the order the framework's own rows and Job Progress show them (each by its
        /// place among the jobs given): the game's Dark Knight, then its Onion Knight (where a mod gives them), then the
        /// mods' own jobs in the order given.</summary>
        public static int[] Shown(IList<Given> given)
        {
            var shown = new List<int>();
            foreach (int game in new[] { JobFile.DarkKnight, JobFile.OnionKnight })
                for (int k = 0; k < given.Count; k++)
                    if (given[k].Game && given[k].Number == game)
                        shown.Add(k);
            for (int k = 0; k < given.Count; k++)
                if (!given[k].Game)
                    shown.Add(k);
            return shown.ToArray();
        }

        /// <summary>(1.55.0) The mods' own jobs among the jobs given: every one before the game's (Plan puts those last).</summary>
        public static List<Given> Mods(IList<Given> given)
        {
            var mods = new List<Given>();
            foreach (var g in given)
                if (!g.Game)
                    mods.Add(g);
            return mods;
        }

        /// <summary>A job's row of learned abilities: Mime's, which is never used.</summary>
        public const int OwnRow = 19;

        /// <summary>What the log says of a job given.</summary>
        public static string Line(Given g)
        {
            // (1.55.0) The game's own Dark Knight or Onion Knight: its number and skillset the game's.
            string what = !g.Game ? $"{g.Job.Who} is job {g.Number}, looking like the game's job {g.Job.Like}, with its own skillset {g.Skillset}"
                        : g.Number == JobFile.DarkKnight
                        ? $"{g.Job.Who} is the game's Dark Knight (job {g.Number}), looking like the game's job {g.Job.Like}, with "
                          + $"the game's skillset {g.Skillset}"
                        : $"{g.Job.Who} is the game's Onion Knight (job {g.Number}), looking like the game's job {g.Job.Like}, "
                          + "learning no abilities";
            // (1.55.1) The game's Onion Knight with sprites of its own: after "learning no abilities", "with".
            string joined = g.Game && g.Number == JobFile.OnionKnight ? ", with" : " and";
            return (g.Sprite < 0 ? what + "."
                    : $"{what}{joined} its own sprites {g.Sprite} and {g.Sprite + 1}, which use {TexturesOf(g)}{FramesOf(g)}"
                      + $"{ColorsOf(g.Job)}{PortraitsOf(g)}.")
                   + JobArt.ArtOf(g);
        }

        /// <summary>(1.54.0) The frames its own textures are drawn for, where its Look says and they are given to the game,
        /// for its line (nothing where neither is).</summary>
        static string FramesOf(Given g)
        {
            int man = g.Textures[0] ? g.Job.Frames[0] : 0, woman = g.Textures[1] ? g.Job.Frames[1] : 0;
            if (man > 0 && woman > 0)
                return man == woman ? $", drawn for Type {man} frames" : $", the man's drawn for Type {man} frames and the woman's for Type {woman}";
            if (man > 0)
                return $", the man's drawn for Type {man} frames";
            return woman > 0 ? $", the woman's drawn for Type {woman} frames" : "";
        }

        /// <summary>(1.45.0) What of a job's own sprites has portraits of its own, for its line (nothing where none has).</summary>
        static string PortraitsOf(Given g)
            => g.Portraits[0] && g.Portraits[1] ? " and portraits of their own"
             : g.Portraits[0] ? ", with the man's portraits of its own"
             : g.Portraits[1] ? ", with the woman's portraits of its own" : "";

        /// <summary>(1.44.0) Whose textures a job's own sprites wear, for its line.</summary>
        static string TexturesOf(Given g)
            => g.Textures[0] && g.Textures[1] ? "textures of their own"
             : g.Textures[0] ? $"the game's job {g.Job.LookLike}'s textures, the man's textures of its own"
             : g.Textures[1] ? $"the game's job {g.Job.LookLike}'s textures, the woman's textures of its own"
             : $"the game's job {g.Job.LookLike}'s textures";

        /// <summary>(1.43.0) What of a job's own sprites wears colors of its own, for its line.</summary>
        static string ColorsOf(ModJob job)
            => job.Colors[0] != null && job.Colors[1] != null ? " in colors of its own"
             : job.Colors[0] != null ? ", the man's in colors of its own"
             : job.Colors[1] != null ? ", the woman's in colors of its own" : "";

        // --- the native code ------------------------------------------------------------------------------------------

        const byte ShortJe = 0x74, ShortJne = 0x75, ShortJmp = 0xEB, ShortJs = 0x78;

        /// <summary>A unit's record in the party: where its second skillset is (0x276758 copies it to a battle unit).</summary>
        public const int UnitSecond = 7;

        /// <summary>A unit's record: where its levels (a nibble a slot) and its total JP (a word a slot) are; how far
        /// its JP and total JP are before where a battle unit has them.</summary>
        const int UnitLevels = 0x74, UnitTotals = 0xAE, UnitBattleJp = 0x70;

        /// <summary>The number of a mod's job turned into the job it looks like, in one byte register (`compare` and
        /// `move` the instructions' bytes up to their value). (1.42.0) `seen`: the job it is turned into, where not the
        /// job it looks like (Given.Drawn, Given.Atlas).</summary>
        static void Like(Destinations.Asm a, IList<Given> given, string compare, string move, int moveBytes,
                         Func<Given, int>? seen = null)
        {
            foreach (var g in given)
            {
                a.Hex(compare);
                a.Bytes((byte)g.Number);
                a.Bytes(ShortJne, (byte)moveBytes);
                a.Hex(move);
                a.Bytes((byte)(seen == null ? g.Job.Like : seen(g)));
            }
        }

        static byte[] Instruction(byte code, ulong imageBase, int site, ulong to, int length)
        {
            var bytes = new byte[length];
            for (int n = 5; n < length; n++)
                bytes[n] = 0x90;
            bytes[0] = code;
            BinaryPrimitives.WriteInt32LittleEndian(bytes.AsSpan(1), checked((int)((long)to - (long)(imageBase + (ulong)site + 5))));
            return bytes;
        }

        /// <summary>A change of the game's code: where (from the program's start) and its bytes.</summary>
        public readonly struct Change
        {
            public int At { get; }
            public byte[] Bytes { get; }

            public Change(int at, byte[] bytes)
            {
                At = at;
                Bytes = bytes;
            }
        }

        /// <summary>The native code, to be at `at`, for the jobs given (of a program at `imageBase`), and the changes of the
        /// game's code that reach it. It keeps every register the game's code it stands in for keeps.</summary>
        public static byte[] Code(ReadOnlySpan<byte> image, Found found, ulong imageBase, ulong at, IList<Given> given,
                                  out List<Change> changes, Screen? screen = null, int arithmeticks = -1,
                                  int arithmeticksThink = -1, int arithmeticksRandom = -1, SpriteRoom.Sites? sprites = null,
                                  int battleOwn = -1, int battleRow = -1, int battleLearn = -1,
                                  IReadOnlyDictionary<string, int>? special = null)
        {
            var a = new Destinations.Asm(at);
            var made = new List<Change>();
            // (1.55.0) The mods' own jobs (each with its place among the jobs given: Plan puts the game's last) and the
            // game's own Dark Knight and Onion Knight a mod gives (their numbers, slots and rows the game's).
            var mods = Mods(given);
            var games = new List<Given>();
            foreach (var g in given)
                if (g.Game)
                    games.Add(g);
            Given? dark = games.Find(g => g.Number == JobFile.DarkKnight);
            int Site(string name) => found.At[name];
            ulong Address(int rva) => imageBase + (ulong)rva;
            void Jump(string name, int length, ulong to) => made.Add(new Change(Site(name), Instruction(0xE9, imageBase, Site(name), to, length)));
            void Call(string name, int length, ulong to) => made.Add(new Change(Site(name), Instruction(0xE8, imageBase, Site(name), to, length)));

            // (1.38.0) More than one job: one is loaded in every unit's slot 22 and row 19 at a time (JobProgress). The
            // job loaded (its place among the jobs given) and the framework's own function that loads another are in two
            // cells a page past this code. `swap`: the job in eax loaded by that function, every register a function of
            // the game's may spoil kept (rax is the asker's to keep), the flags and the stack too.
            ulong loadedCell = at + CellsAfter + LoadedCell, swapCell = at + CellsAfter + SwapCell;
            ulong swap = a.Here;
            a.Hex("9C 51 52 41 50 41 51 41 52 41 53 53");      // pushfq; push rcx, rdx, r8, r9, r10, r11, rbx
            a.Hex("48 8B DC 48 83 E4 F0 48 81 EC 80 00 00 00"); // mov rbx, rsp; and rsp, -16; sub rsp, 0x80
            for (int x = 0; x < 6; x++)                        // movaps [rsp + 0x20 + 0x10 * x], xmm(x)
                a.Bytes(0x0F, 0x29, (byte)(0x44 + 8 * x), 0x24, (byte)(0x20 + 0x10 * x));
            a.Hex("8B C8 FF 15");                              // mov ecx, eax; call [rip + its cell]
            a.I32((long)swapCell - (long)(a.Here + 4));
            for (int x = 0; x < 6; x++)                        // movaps xmm(x), [rsp + 0x20 + 0x10 * x]
                a.Bytes(0x0F, 0x28, (byte)(0x44 + 8 * x), 0x24, (byte)(0x20 + 0x10 * x));
            a.Hex("48 8B E3 5B 41 5B 41 5A 41 59 41 58 5A 59 9D C3"); // mov rsp, rbx; pop rbx, r11, r10, r9, r8, rdx, rcx; popfq; ret

            // A job (its place among the given) made the loaded one when it isn't: the flags are spoiled, nothing else.
            void Ensure(int job)
            {
                a.Hex("83 3D");                                // cmp dword ptr [rip + the loaded job's cell], job
                a.I32((long)loadedCell - (long)(a.Here + 5));
                a.Bytes((byte)job);
                a.Bytes(ShortJe, 12);
                a.Bytes(0x50, 0xB8);                           // push rax; mov eax, job
                a.I32(job);
                a.Bytes(0xE8);                                 // call swap
                a.I32((long)swap - (long)(a.Here + 4));
                a.Bytes(0x58);                                 // pop rax
            }

            // (1.38.1) A battle started again. The game's call to take its copy of the battle, or to put it back, is made
            // from here as it came (its arguments untouched, the stack as a call's must be), then the framework's own
            // function is told which it was, and the game's answer is given back. (1.38.2) The taking of the copy is
            // told before the game's call (the mark must be in the variables the copy takes): the game's one argument,
            // ecx, is kept across the telling.
            ulong retryCell = at + CellsAfter + RetryCell;
            var theirs = new Dictionary<string, int>();
            foreach (var name in new[] { "RetryCopyA", "RetryCopyB", "RetryPart", "RetryWhole" })
                theirs[name] = CallTarget(image, Site(name));
            void Told(string name, int which, bool before = false)
            {
                ulong here = a.Here;
                a.Hex("48 83 EC 28");                          // sub rsp, 0x28
                if (before)
                    a.Hex("48 89 4C 24 20");                   // mov [rsp + 0x20], rcx
                else
                {
                    a.Call(Address(theirs[name]));
                    a.Hex("48 89 44 24 20");                   // mov [rsp + 0x20], rax
                }
                a.Bytes(0xB9);                                 // mov ecx, which
                a.I32(which);
                a.Hex("FF 15");                                // call [rip + its cell]
                a.I32((long)retryCell - (long)(a.Here + 4));
                if (before)
                {
                    a.Hex("48 8B 4C 24 20");                   // mov rcx, [rsp + 0x20]
                    a.Call(Address(theirs[name]));
                    a.Hex("48 83 C4 28 C3");                   // add rsp, 0x28; ret
                }
                else
                    a.Hex("48 8B 44 24 20 48 83 C4 28 C3");    // mov rax, [rsp + 0x20]; add rsp, 0x28; ret
                Call(name, 5, here);
            }
            Told("RetryCopyA", RetryCopied, before: true);
            Told("RetryCopyB", RetryCopied, before: true);
            Told("RetryPart", RetryPart);
            Told("RetryWhole", RetryWhole);

            // The slot: a mod's job's is 22, once it is the job loaded there. The game's own takes rax, rcx, rdx and the
            // flags; this takes rax, rdx and the flags.
            // (1.55.0) The mods' own jobs alone: the game's Dark Knight's and Onion Knight's slots are the game's (20, 21).
            ulong stub = a.Here;
            a.Hex("0F B7 D1");                                 // movzx edx, cx
            for (int k = 0; k < mods.Count; k++)
            {
                a.Hex("81 FA");                                 // cmp edx, number
                a.I32(given[k].Number);
                a.NearTo($"slot{k}", 0x84);                     // je
            }
            a.Hex("8D 42 B6");                                 // lea eax, [rdx - 0x4A]
            a.Near(Address(Site("Slot") + 6));
            for (int k = 0; k < mods.Count; k++)
            {
                a.Label($"slot{k}");
                Ensure(k);
                a.Bytes(0xB8);                                 // mov eax, 22
                a.I32(Slot);
                a.Bytes(0xC3);
            }
            Jump("Slot", 6, stub);

            // The sprite set: the job it looks like, in r8b as the game's own reads it first. (1.42.0) The job its own
            // sprites are made from, where it has them: each routine that makes a sprite from a job is handed that.
            Func<Given, int> drawn = g => g.Drawn;
            stub = a.Here;
            Like(a, given, "41 80 F8", "41 B0", 3, drawn);     // cmp r8b, number; jne; mov r8b, like
            a.Hex("45 0F B6 C8 4C 8B D1");                     // movzx r9d, r8b; mov r10, rcx
            a.Near(Address(Site("Sprite") + 7));
            Jump("Sprite", 7, stub);

            // A woman's portrait: the job read into ecx, the job it looks like there.
            ulong woman = a.Here;
            Like(a, given, "80 F9", "B1", 2, drawn);           // cmp cl, number; jne; mov cl, like
            a.Hex("B8 35 00 00 00 C3");                        // mov eax, 0x35; ret
            foreach (var name in new[] { "Woman1", "Woman2", "Woman3", "Woman4", "Woman5" })
                Call(name, 5, woman);

            // A man's: the job read into eax, the job it looks like there, then the game's two instructions as they were.
            foreach (var name in new[] { "Man1", "Man2", "Man3", "Man4", "Man5" })
            {
                int length = name == "Man5" ? 9 : 10;
                stub = a.Here;
                Like(a, given, "3C", "B0", 2, drawn);          // cmp al, number; jne; mov al, like
                a.Bytes(image.Slice(Site(name), length).ToArray());
                a.Bytes(0xC3);
                Call(name, length, stub);
            }

            // The face: the job read into edx.
            stub = a.Here;
            Like(a, given, "80 FA", "B2", 2, drawn);           // cmp dl, number; jne; mov dl, like
            a.Hex("C1 E9 07 83 C2 B6 C3");                     // shr ecx, 7; add edx, -0x4A; ret
            Call("Face", 6, stub);

            // (1.55.0) The five portrait routines' second read of the job (where found and a game job is given): the game's
            // read, the job its look is drawn from where it is the game's Dark Knight or Onion Knight a mod gives, then
            // the game's subtraction of 160 (its flags are what the jumps after it read; the return keeps them).
            if (special != null && games.Count > 0)
                for (int n = 0; n < SpecialSites.Length; n++)
                {
                    string name = SpecialSites[n].Name;
                    if (!special.TryGetValue(name, out int site))
                        continue;
                    var (compare, move, read) = SpecialRegisters[n];
                    int length = SpecialSites[n].Length;
                    stub = a.Here;
                    a.Bytes(image.Slice(site, read).ToArray());   // movzx reg, byte ptr [base + 2]
                    Like(a, games, compare, move, move.Split(' ').Length + 1, drawn);
                    a.Bytes(image.Slice(site + read, length - read).ToArray()); // sub reg, 0xA0
                    a.Bytes(0xC3);
                    made.Add(new Change(site, Instruction(0xE8, imageBase, site, stub, length)));
                }

            // (1.55.1) Job Summary's two reads of a job's words (where found and the game's Onion Knight is given with words
            // for its level 8): the getter is asked for a row by its key in edx (ecx the job help table's sheet). The game's
            // Onion Knight's own key asks the framework which key to read (JobAsker.SummaryKey: its level 8 words' where
            // the screen's unit's Onion Knight is level 8), every register a function may lose kept around that asking, the
            // stack aligned for it; then the getter, as the game's call would have gone.
            if (special != null && special.TryGetValue("Summary1", out int summary1) && special.TryGetValue("Summary2", out int summary2)
                && special.TryGetValue("SummaryGetter", out int summaryGetter)
                && games.Exists(g => g.Number == JobFile.OnionKnight && g.Job.MasteredWords))
            {
                ulong summaryCell = at + CellsAfter + SummaryCell;
                stub = a.Here;
                a.Hex("81 FA");                                // cmp edx, the game's Onion Knight's own key
                a.I32(JobWords.HelpKey(JobFile.OnionKnight));
                a.Short(ShortJne, "summaryGo");
                a.Hex("51 52 41 50 41 51 41 52 41 53 53");     // push rcx, rdx, r8, r9, r10, r11, rbx
                a.Hex("48 8B DC 48 83 E4 F0 48 81 EC 80 00 00 00"); // mov rbx, rsp; and rsp, -16; sub rsp, 0x80
                for (int x = 0; x < 6; x++)                    // movaps [rsp + 0x20 + 0x10 * x], xmm(x)
                    a.Bytes(0x0F, 0x29, (byte)(0x44 + 8 * x), 0x24, (byte)(0x20 + 0x10 * x));
                a.Hex("8B CA");                                // mov ecx, edx
                a.Hex("FF 15");                                // call [rip + its cell]
                a.I32((long)summaryCell - (long)(a.Here + 4));
                for (int x = 0; x < 6; x++)                    // movaps xmm(x), [rsp + 0x20 + 0x10 * x]
                    a.Bytes(0x0F, 0x28, (byte)(0x44 + 8 * x), 0x24, (byte)(0x20 + 0x10 * x));
                a.Hex("48 8B E3 5B 41 5B 41 5A 41 59 41 58 5A 59"); // mov rsp, rbx; pop rbx, r11, r10, r9, r8, rdx, rcx
                a.Hex("8B D0");                                // mov edx, eax: the key to read
                a.Label("summaryGo");
                a.Near(Address(summaryGetter));                // jmp the getter
                foreach (int site in new[] { summary1, summary2 })
                    made.Add(new Change(site, Instruction(0xE8, imageBase, site, stub, 5)));
            }

            // (1.55.2) The job screen's window's read of a job's words (where found and the game's Onion Knight is given with
            // a description for its level 8): the reader is handed the words wanted in edx (its description 1), the job's key
            // in r8d. The game's Onion Knight's description asks the framework which row to read, by its help key as Job
            // Summary's reads ask (JobAsker.SummaryKey: the level 8 words' key where the screen's unit's Onion Knight is level
            // 8), every register a function may lose kept around that asking, the stack aligned for it; that key's job (164)
            // is then read in its place. Then the reader, as the game's call would have gone.
            if (special != null && special.TryGetValue("HelpWords", out int helpWords)
                && special.TryGetValue("HelpWordsReader", out int helpWordsReader)
                && games.Exists(g => g.Number == JobFile.OnionKnight && g.Job.MasteredDescription != null))
            {
                ulong summaryCell = at + CellsAfter + SummaryCell;
                stub = a.Here;
                a.Hex("83 FA");                                // cmp edx, its description
                a.Bytes((byte)HelpWordsAsked);
                a.Short(ShortJne, "helpGo");
                a.Hex("41 81 F8");                             // cmp r8d, the game's Onion Knight
                a.I32(JobFile.OnionKnight);
                a.Short(ShortJe, "helpAsk");
                a.Label("helpGo");
                a.Near(Address(helpWordsReader));              // jmp the reader
                a.Label("helpAsk");
                a.Hex("51 52 41 50 41 51 41 52 41 53 53");     // push rcx, rdx, r8, r9, r10, r11, rbx
                a.Hex("48 8B DC 48 83 E4 F0 48 81 EC 80 00 00 00"); // mov rbx, rsp; and rsp, -16; sub rsp, 0x80
                for (int x = 0; x < 6; x++)                    // movaps [rsp + 0x20 + 0x10 * x], xmm(x)
                    a.Bytes(0x0F, 0x29, (byte)(0x44 + 8 * x), 0x24, (byte)(0x20 + 0x10 * x));
                a.Bytes(0xB9);                                 // mov ecx, the game's Onion Knight's help key
                a.I32(JobWords.HelpKey(JobFile.OnionKnight));
                a.Hex("FF 15");                                // call [rip + its cell]
                a.I32((long)summaryCell - (long)(a.Here + 4));
                for (int x = 0; x < 6; x++)                    // movaps xmm(x), [rsp + 0x20 + 0x10 * x]
                    a.Bytes(0x0F, 0x28, (byte)(0x44 + 8 * x), 0x24, (byte)(0x20 + 0x10 * x));
                a.Hex("48 8B E3 5B 41 5B 41 5A 41 59 41 58 5A 59"); // mov rsp, rbx; pop rbx, r11, r10, r9, r8, rdx, rcx
                a.Bytes(0x3D);                                 // cmp eax, the level 8 words' help key
                a.I32(JobWords.HelpKey(JobFile.MasteredOnion));
                a.Short(ShortJne, "helpRead");
                a.Hex("41 B8");                                // mov r8d, the job the level 8 words are read from
                a.I32(JobFile.MasteredOnion);
                a.Label("helpRead");
                a.Near(Address(helpWordsReader));              // jmp the reader
                made.Add(new Change(helpWords, Instruction(0xE8, imageBase, helpWords, stub, 5)));
            }

            // A unit's learned row: the slot 22's is the job's own, Mime's, which is never used.
            int learned = OwnRow;
            ulong row = a.Here;
            a.Call(Address(Site("Slot")));
            a.Hex("83 F8");                                    // cmp eax, 22
            a.Bytes((byte)Slot);
            a.Short(ShortJne, "row");
            a.Bytes(0xB8);                                     // mov eax, its row
            a.I32(learned);
            a.Label("row");
            a.Bytes(0xC3);
            foreach (var name in new[] { "RowBattle", "RowMenu", "RowUnit", "RowLearn" })
                Call(name, 5, row);

            // The two that read the slot for its JP first: rax (RowList) or r8 (RowMake) is the slot, and the row's
            // start is worked out from it. The register holding the slot is left as it was.
            stub = a.Here;
            a.Hex("48 83 F8");                                 // cmp rax, 22
            a.Bytes((byte)Slot);
            a.Short(ShortJne, "list");
            a.Bytes(0xBA);                                     // mov edx, row + 0x29
            a.I32(learned + 0x29);
            a.Short(ShortJmp, "listed");
            a.Label("list");
            a.Hex("48 8D 50 29");                              // lea rdx, [rax + 0x29]
            a.Label("listed");
            a.Hex("48 8D 04 51 C3");                           // lea rax, [rcx + rdx*2]; ret
            Call("RowList", 8, stub);

            stub = a.Here;
            a.Hex("49 83 F8");                                 // cmp r8, 22
            a.Bytes((byte)Slot);
            a.Short(ShortJne, "make");
            a.Bytes(0xB9);                                     // mov ecx, row + 0x29
            a.I32(learned + 0x29);
            a.Short(ShortJmp, "made");
            a.Label("make");
            a.Hex("49 8D 48 29");                              // lea rcx, [r8 + 0x29]
            a.Label("made");
            a.Hex("48 8D 04 4A C3");                           // lea rax, [rdx + rcx*2]; ret
            Call("RowMake", 8, stub);

            // The second list of a job's abilities: rcx is the slot, its row next; the instruction after it as it was.
            stub = a.Here;
            a.Hex("48 0F BF CE");                              // movsx rcx, si
            a.Hex("48 83 F9");                                 // cmp rcx, 22
            a.Bytes((byte)Slot);
            a.Short(ShortJne, "second");
            a.Bytes(0xB9);                                     // mov ecx, its row
            a.I32(learned);
            a.Label("second");
            a.Hex("8B FD C3");                                 // mov edi, ebp; ret
            Call("RowSecond", 6, stub);

            // The battle's two readers of a learned row by the skillset: the job's own skillset is the job's own row, for
            // a unit in the job and for one that has taken it as its second (the game alone reads Squire's row for the
            // first and takes everything as learned for the second). First (edx the skillset): the flags are as the jbe
            // after it wants.
            stub = a.Here;
            a.Hex("8D 4A FB");                                 // lea ecx, [rdx - 5]
            for (int k = 0; k < mods.Count; k++)
            {
                a.Hex("81 FA");                                // cmp edx, its skillset
                a.I32(given[k].Skillset);
                a.Short(ShortJne, $"own{k}");
                Ensure(k);                                     // (1.38.0) its job loaded in the row
                a.Bytes(0xB9);                                 // mov ecx, its row
                a.I32(learned);
                a.Hex("3B C9 C3");                             // cmp ecx, ecx; ret
                a.Label($"own{k}");
            }
            // (1.55.0) The game's Dark Knight's skillset (224) is its own row, 20, whoever has it: the game's reader takes
            // it as the row of the unit's job, so a unit that takes Dark Knight's abilities as its second read its own
            // job's row. Nothing to load: the row is the unit's own.
            if (dark != null)
            {
                a.Hex("81 FA");                                // cmp edx, its skillset
                a.I32(dark.Skillset);
                a.Short(ShortJne, "owndark");
                a.Bytes(0xB9);                                 // mov ecx, its row
                a.I32(DarkSlot);
                a.Hex("3B C9 C3");                             // cmp ecx, ecx; ret
                a.Label("owndark");
            }
            a.Hex("83 F9 12 C3");                              // cmp ecx, 0x12; ret
            Call("LearnedBattle", 6, stub);

            // Second (r15b the skillset): its row and on to where the game's short jump went, or the game's two
            // instructions and back to its test. (1.55.0) The game's Dark Knight's skillset is its row 20 here already.
            int joined = Site("LearnedList") + 14 + (sbyte)image[Site("LearnedList") + 13];
            stub = a.Here;
            for (int k = 0; k < mods.Count; k++)
            {
                a.Hex("41 80 FF");                             // cmp r15b, its skillset
                a.Bytes((byte)given[k].Skillset);
                a.Short(ShortJne, $"ownlist{k}");
                Ensure(k);                                     // (1.38.0) its job loaded in the row
                a.Bytes(0xB8);                                 // mov eax, its row
                a.I32(learned);
                a.Near(Address(joined));
                a.Label($"ownlist{k}");
            }
            a.Hex("41 8D 47 FB 3C 12");                        // lea eax, [r15 - 5]; cmp al, 0x12
            a.Near(Address(Site("LearnedList") + 6));
            Jump("LearnedList", 6, stub);

            // (1.37.1, Zodi's test 78: "Battle Magicks does not appear in the list to choose from") The skillsets a
            // unit may take as its second: the game lists its own jobs' (0x2864AC), so each mod's job's is added after
            // them, as a pair of words (the job, its skillset), unless the unit is in that job. There di is the unit's
            // job, rbx the list and r8d its count; the two instructions it stands in for follow.
            // (1.48.0, what opens a job) Only while a job is open to the unit, where the framework's own rows are
            // made (`screen`): `open` asks the framework's own function (the menu's record's number in ecx, the job's
            // number in edx), every register kept but rax, its answer (0: not open), and the flags. The unit is the
            // one the game's one call of this list hands it in cx, kept in a cell by that call's stand in.
            bool asks = screen != null;
            ulong openCell = at + CellsAfter + OpenCell, unitCell = at + CellsAfter + UnitCell, open = a.Here;
            if (asks)
            {
                a.Hex("51 52 41 50 41 51 41 52 41 53 53");     // push rcx, rdx, r8, r9, r10, r11, rbx
                a.Hex("48 8B DC 48 83 E4 F0 48 81 EC 80 00 00 00"); // mov rbx, rsp; and rsp, -16; sub rsp, 0x80
                for (int x = 0; x < 6; x++)                    // movaps [rsp + 0x20 + 0x10 * x], xmm(x)
                    a.Bytes(0x0F, 0x29, (byte)(0x44 + 8 * x), 0x24, (byte)(0x20 + 0x10 * x));
                a.Hex("FF 15");                                // call [rip + its cell]
                a.I32((long)openCell - (long)(a.Here + 4));
                for (int x = 0; x < 6; x++)                    // movaps xmm(x), [rsp + 0x20 + 0x10 * x]
                    a.Bytes(0x0F, 0x28, (byte)(0x44 + 8 * x), 0x24, (byte)(0x20 + 0x10 * x));
                a.Hex("48 8B E3 5B 41 5B 41 5A 41 59 41 58 5A 59 C3"); // mov rsp, rbx; pop rbx, r11, r10, r9, r8, rdx, rcx; ret
                ulong secondCall = a.Here;
                a.Hex("89 0D");                                // mov [rip + the unit's cell], ecx
                a.Rip(unitCell);
                a.Near(Address(screen!.SecondWhole));          // jmp the game's list of second skillsets
                made.Add(new Change(screen.At["SecondCall"], Instruction(0xE8, imageBase, screen.At["SecondCall"], secondCall, 5)));
            }
            stub = a.Here;
            foreach (var g in given)
            {
                if (g.Skillset == 0)
                    continue;                                  // (1.55.0) the game's Onion Knight learns no abilities
                a.Hex("66 81 FF");                             // cmp di, its job
                a.Bytes((byte)g.Number, (byte)(g.Number >> 8));
                a.Short(ShortJe, $"second{g.Number}");
                if (asks)
                {
                    a.Hex("8B 0D");                            // mov ecx, [rip + the unit's cell]
                    a.Rip(unitCell);
                    a.Bytes(0xBA);                             // mov edx, its job
                    a.I32(g.Number);
                    a.Call(open);
                    a.Hex("85 C0");                            // test eax, eax
                    a.Short(ShortJe, $"second{g.Number}");
                }
                if (g.Game)
                {
                    // (1.55.0) The game's Dark Knight is in the game's own list where its bit is set (a save from Dark
                    // Knight & Onion Knight (Generic)'s days, until the game makes the unit's bits again): not twice. edx is
                    // the game's to lose here (set from the count as this returns).
                    a.Hex("33 D2");                            // xor edx, edx
                    a.Label($"scan{g.Number}");
                    a.Hex("41 3B D0");                         // cmp edx, r8d
                    a.Short(0x7D, $"add{g.Number}");           // jge
                    a.Hex("66 81 3C D3");                      // cmp word ptr [rbx + rdx*8], its job
                    a.Bytes((byte)g.Number, (byte)(g.Number >> 8));
                    a.Short(ShortJe, $"second{g.Number}");
                    a.Hex("FF C2");                            // inc edx
                    a.Short(ShortJmp, $"scan{g.Number}");
                    a.Label($"add{g.Number}");
                }
                a.Hex("66 42 C7 04 C3");                       // mov word ptr [rbx + r8*8], its job
                a.Bytes((byte)g.Number, (byte)(g.Number >> 8));
                a.Hex("66 42 C7 44 C3 02");                    // mov word ptr [rbx + r8*8 + 2], its skillset
                a.Bytes((byte)g.Skillset, (byte)(g.Skillset >> 8));
                a.Hex("41 FF C0");                             // inc r8d
                a.Label($"second{g.Number}");
            }
            a.Hex("49 63 D0 41 8B C0 C3");                     // movsxd rdx, r8d; mov eax, r8d; ret
            Call("SecondList", 6, stub);

            // (1.37.1) The reaction, support and movement abilities a unit may set: the game asks its lister
            // (0x28A6E8) for the unit's first job, then for its generic jobs. Its first call is this instead: the same
            // call, then one for each mod's job as the game makes its others (the unit in r15w, the kind of ability in
            // r12d, which to list in edi, the list 0x50 above the game's stack, each call's after the last's), the
            // count of them all returned. esi is the game's count, which it sets from this as it returns.
            int lister = Site("OthersList") + 5 + BinaryPrimitives.ReadInt32LittleEndian(image.Slice(Site("OthersList") + 1, 4));
            stub = a.Here;
            a.Hex("48 83 EC 38");                              // sub rsp, 0x38
            a.Hex("89 7C 24 20");                              // mov [rsp + 0x20], edi
            a.Call(Address(lister));
            a.Hex("8B F0");                                    // mov esi, eax
            foreach (var g in given)
            {
                if (g.Skillset == 0)
                    continue;                                  // (1.55.0) the game's Onion Knight learns no abilities
                a.Hex("41 0F B7 CF");                          // movzx ecx, r15w
                a.Bytes(0xBA);                                 // mov edx, its job
                a.I32(g.Number);
                if (asks)
                {
                    // (1.48.0) Only while the job is open to the unit (ecx and edx as `open` takes them, both kept).
                    a.Call(open);
                    a.Hex("85 C0");                            // test eax, eax
                    a.Short(ShortJe, $"others{g.Number}");
                }
                a.Hex("45 8B C4");                             // mov r8d, r12d
                a.Hex("48 63 C6");                             // movsxd rax, esi
                a.Hex("4C 8D 8C C4 90 00 00 00");              // lea r9, [rsp + rax*8 + 0x90]
                a.Hex("89 7C 24 20");                          // mov [rsp + 0x20], edi
                a.Call(Address(lister));
                a.Hex("03 F0");                                // add esi, eax
                if (asks)
                    a.Label($"others{g.Number}");
            }
            a.Hex("8B C6");                                    // mov eax, esi
            a.Hex("48 83 C4 38 C3");                           // add rsp, 0x38; ret
            Call("OthersList", 5, stub);

            // (1.37.2, Zodi's word after test 79: "saving my Battlemage to Combat Set 2 saved the job as Knight") The
            // game takes two jobs as the same job when their Job rows name the same JobType (0xF72F0: Ramza's three
            // Squires), and a mod's job's row is the row of the job it looks like. A set keeps the job's own number, but
            // its showing took the first of the unit's jobs that is "the same" (the Knight), and applying it changed
            // the unit to that. A mod's job is the same job as itself alone (ecx and edx the two jobs).
            // (1.39.0) Each job's two jumps reach the end over every job after it: near ones, since with eight jobs or
            // more a short one doesn't reach (up to 1.38.4 the code couldn't be made for more than seven).
            stub = a.Here;
            foreach (var g in given)
            {
                a.Hex("81 F9");                                // cmp ecx, its job
                a.I32(g.Number);
                a.NearTo("exact", 0x84);                       // je
                a.Hex("81 FA");                                // cmp edx, its job
                a.I32(g.Number);
                a.NearTo("exact", 0x84);                       // je
            }
            a.Hex("48 89 5C 24 08");                           // mov [rsp + 8], rbx
            a.Near(Address(Site("SameJob") + 5));
            a.Label("exact");
            a.Hex("3B CA 0F 94 C0 C3");                        // cmp ecx, edx; sete al; ret
            Jump("SameJob", 5, stub);

            // (1.37.2) The showing of a set (0x33751C) marks it as one that can't be used unless its job is one of the
            // unit's jobs, by the game's own list of them, which never holds a mod's job. Its call for that list is
            // this instead: the same call, and then, for a set whose job (at rbp + 0x166) is a mod's job, the set
            // marked usable (r14 + 0xA4) and no job of the list to look through (eax 0), so its job stays its own.
            int jobList = Site("SetJob") + 5 + BinaryPrimitives.ReadInt32LittleEndian(image.Slice(Site("SetJob") + 1, 4));
            stub = a.Here;
            a.Hex("48 83 EC 28");                              // sub rsp, 0x28
            a.Call(Address(jobList));
            a.Hex("48 83 C4 28");                              // add rsp, 0x28
            foreach (var g in given)
            {
                a.Hex("80 BD 66 01 00 00");                    // cmp byte ptr [rbp + 0x166], its job
                a.Bytes((byte)g.Number);
                a.Bytes(ShortJne, 10);
                a.Hex("41 C6 86 A4 00 00 00 00");              // mov byte ptr [r14 + 0xA4], 0
                a.Hex("33 C0");                                // xor eax, eax
            }
            a.Bytes(0xC3);
            Call("SetJob", 5, stub);

            // The unit's place in the atlas of units, by the job in cx: the job it looks like. (1.42.0) Its Look's, where
            // it has sprites of its own (the atlas has a place for each of the game's jobs only).
            stub = a.Here;
            Like(a, given, "80 F9", "B1", 2, g => g.Atlas);    // cmp cl, number; jne; mov cl, like
            a.Hex("48 89 5C 24 08");                           // mov [rsp + 8], rbx
            a.Near(Address(Site("Atlas") + 5));
            Jump("Atlas", 5, stub);

            // A job's cell on the job screen: the job it looks like, in ecx, only for the sprite the cell shows (the
            // game's generic jobs draw by the job there, any other job as the unit already looks).
            stub = a.Here;
            a.Hex("0F B6 4D E8");                              // movzx ecx, byte ptr [rbp - 0x18]
            Like(a, given, "80 F9", "B1", 2, drawn);           // cmp cl, number; jne; mov cl, like
            a.Hex("41 8D 46 3D C3");                           // lea eax, [r14 + 0x3D]; ret
            Call("Cell", 8, stub);

            // GeneralJob's row: the slot 22's is the row of the job it looks like. (1.55.0) And the game's Dark Knight's
            // slot 20, whose row the game leaves with an empty list (read with no bound): the row of the job it looks like
            // (every generic job's list is the same). Onion Knight's 21 is the game's: its level is the game's own rule.
            stub = a.Here;
            a.Hex("83 F9");                                    // cmp ecx, 22
            a.Bytes((byte)Slot);
            a.Short(ShortJne, "table");
            a.Bytes(0xB9);                                     // mov ecx, row
            a.I32(given[0].Job.Like - FirstGeneric);
            a.Label("table");
            if (dark != null)
            {
                a.Hex("83 F9");                                // cmp ecx, 20
                a.Bytes((byte)DarkSlot);
                a.Short(ShortJne, "darktable");
                a.Bytes(0xB9);                                 // mov ecx, row
                a.I32(dark.Job.Like - FirstGeneric);
                a.Label("darktable");
            }
            a.Hex("48 89 5C 24 10");                           // mov [rsp + 0x10], rbx
            a.Near(Address(Site("Table") + 5));
            Jump("Table", 5, stub);

            // The levels: the game's own for its 20 generic jobs, then slot 22's in the high half of the 12th byte. (1.55.0)
            // And the game's Dark Knight's slot 20, in the high half of the 11th, which the game counts only as JP is gained.
            var counted = new List<int> { Slot };
            if (dark != null)
                counted.Add(DarkSlot);
            stub = a.Here;
            a.Hex("53 56 48 83 EC 28");                        // push rbx; push rsi; sub rsp, 0x28
            a.Hex("48 8B D9 48 8B F2");                        // mov rbx, rcx; mov rsi, rdx
            a.Call(Address(found.Levels));
            foreach (int slot in counted)
            {
                a.Hex("0F B7 53");                             // movzx edx, word ptr [rbx + 2 * slot]
                a.Bytes((byte)(2 * slot));
                a.Bytes(0xB9);                                 // mov ecx, slot
                a.I32(slot);
                a.Call(Address(found.LevelOf));
                a.Hex("C1 E0 04");                             // shl eax, 4
                a.Hex("0F B6 4E");                             // movzx ecx, byte ptr [rsi + slot / 2]
                a.Bytes((byte)(slot / 2));
                a.Hex("83 E1 0F 0B C8");                       // and ecx, 0xF; or ecx, eax
                a.Hex("88 4E");                                // mov byte ptr [rsi + slot / 2], cl
                a.Bytes((byte)(slot / 2));
            }
            a.Hex("48 83 C4 28 5E 5B C3");                     // add rsp, 0x28; pop rsi; pop rbx; ret
            Call("LevelsA", 5, stub);
            Call("LevelsB", 5, stub);

            // The menu's copy of the levels: slot 22's counted first, in the unit's record (rdi), from its total JP. A
            // level of 0 is the "--" of the unit's card: a man or a woman with none is given the JP the game gives a unit's
            // jobs as it is made (a monster has neither), by the game's own function, which writes where a battle unit
            // has them. There was no call here, so every register is kept. (1.55.0) The game's Dark Knight's slot 20 the
            // same way: the game gives a unit's slots 0 to 19 their JP as it is made, and counts slot 20 only as JP is
            // gained, so its card shows "--" until then.
            void CountSlot(int slot)
            {
                a.Hex("0F B7 97");                             // movzx edx, word ptr [rdi + its total JP]
                a.I32(UnitTotals + 2 * slot);
                a.Bytes(0xB9);                                 // mov ecx, slot
                a.I32(slot);
                a.Call(Address(found.LevelOf));
            }
            stub = a.Here;
            a.Hex("50 51 52 41 50 41 51 41 52 41 53");         // push rax, rcx, rdx, r8, r9, r10, r11
            a.Hex("48 83 EC 20");                              // sub rsp, 0x20
            foreach (int slot in counted)
            {
                CountSlot(slot);
                a.Hex("85 C0");                                // test eax, eax
                a.Short(ShortJne, $"counted{slot}");
                a.Hex("F6 47 04 C0");                          // test byte ptr [rdi + 4], 0xC0
                a.Short(ShortJe, $"counted{slot}");
                a.Hex("48 8D 4F");                             // lea rcx, [rdi - 0x70]
                a.Bytes(unchecked((byte)(-UnitBattleJp)));
                a.Hex("0F B6 57 04");                          // movzx edx, byte ptr [rdi + 4]
                a.Hex("41 B8");                                // mov r8d, slot
                a.I32(slot);
                a.Hex("45 33 C9");                             // xor r9d, r9d
                a.Call(Address(found.StartJp));
                CountSlot(slot);
                a.Label($"counted{slot}");
                a.Hex("C1 E0 04");                             // shl eax, 4
                a.Hex("0F B6 4F");                             // movzx ecx, byte ptr [rdi + its level's byte]
                a.Bytes((byte)(UnitLevels + slot / 2));
                a.Hex("83 E1 0F 0B C8");                       // and ecx, 0xF; or ecx, eax
                a.Hex("88 4F");                                // mov byte ptr [rdi + its level's byte], cl
                a.Bytes((byte)(UnitLevels + slot / 2));
            }
            a.Hex("48 83 C4 20");                              // add rsp, 0x20
            a.Hex("41 5B 41 5A 41 59 41 58 5A 59 58");         // pop r11, r10, r9, r8, rdx, rcx, rax
            a.Hex("F2 0F 10 47 74 C3");                        // movsd xmm0, qword ptr [rdi + 0x74]; ret
            Call("LevelCopy", 5, stub);

            // (1.39.0) The job screen's own rows (JobScreen), only where the screen was found and is the framework's
            // to arrange. The filling's call of the game's lister is this instead: the same call, then the framework
            // told how many jobs it listed, its answer the count the filling goes on with (the game keeps nothing in a
            // register across that call but what a function must keep).
            if (screen != null)
            {
                ulong listCell = at + CellsAfter + ScreenListCell, verticalCell = at + CellsAfter + ScreenVerticalCell;
                stub = a.Here;
                a.Hex("48 83 EC 28");                          // sub rsp, 0x28
                a.Call(Address(screen.Lister));
                a.Hex("0F BF C8");                             // movsx ecx, ax
                a.Hex("FF 15");                                // call [rip + its cell]
                a.I32((long)listCell - (long)(a.Here + 4));
                a.Hex("48 83 C4 28 C3");                       // add rsp, 0x28; ret
                made.Add(new Change(screen.At["List"], Instruction(0xE8, imageBase, screen.At["List"], stub, 5)));

                // The cursor's step between the three rows: the framework asked in the game's place, with what the
                // game hands its own (the row in ecx, the first and last rows, the two it hands on, the fifth above
                // the stack) and two more: the screen (rbx) and what the step tells its caller (rsi).
                stub = a.Here;
                a.Hex("48 83 EC 38");                          // sub rsp, 0x38
                a.Hex("8B 44 24 60");                          // mov eax, [rsp + 0x60]
                a.Hex("89 44 24 20");                          // mov [rsp + 0x20], eax
                a.Hex("48 89 5C 24 28");                       // mov [rsp + 0x28], rbx
                a.Hex("48 89 74 24 30");                       // mov [rsp + 0x30], rsi
                a.Hex("FF 15");                                // call [rip + its cell]
                a.I32((long)verticalCell - (long)(a.Here + 4));
                a.Hex("48 83 C4 38 C3");                       // add rsp, 0x38; ret
                made.Add(new Change(screen.At["Vertical"], Instruction(0xE8, imageBase, screen.At["Vertical"], stub, 5)));

                // (1.39.1) The filling's call that gives the job tree a job by its number in the list (the tree in
                // rcx, the job in rdx, the number in r8d): the framework asked which place of the tree's that job
                // has, then the game's own call with that place, or none for a job the tree has no place for. The
                // game keeps nothing in a register across that call but what a function must keep.
                // (1.49.0) The framework is handed the job's record and the tree too (rdx, and rcx as its third): in
                // a filling run for the mods' jobs alone each record is what Job Progress shows of that job (JobTree).
                ulong treeCell = at + CellsAfter + ScreenTreeCell;
                stub = a.Here;
                a.Hex("51 52");                                // push rcx; push rdx
                a.Hex("48 83 EC 28");                          // sub rsp, 0x28
                a.Hex("41 8B C0");                             // mov eax, r8d
                a.Hex("4C 8B C1");                             // mov r8, rcx
                a.Hex("8B C8");                                // mov ecx, eax
                a.Hex("FF 15");                                // call [rip + its cell]
                a.I32((long)treeCell - (long)(a.Here + 4));
                a.Hex("48 83 C4 28");                          // add rsp, 0x28
                a.Hex("5A 59");                                // pop rdx; pop rcx
                a.Hex("85 C0");                                // test eax, eax
                a.Short(ShortJs, "noTreePlace");
                a.Hex("44 8B C0");                             // mov r8d, eax
                a.Near(Address(screen.TreeJob));               // jmp the game's own
                a.Label("noTreePlace");
                a.Hex("C3");                                   // ret
                made.Add(new Change(screen.At["Tree"] + TreeCallAt,
                                    Instruction(0xE8, imageBase, screen.At["Tree"] + TreeCallAt, stub, 5)));

                // (1.49.0) The filling run again for the mods' jobs alone (JobScreen.Harvest): while the number says
                // so, its readying of the screen (the cursor's place forgotten, every place's box put back) and its
                // giving of a job to the screen's place are left out, so nothing of the screen changes; otherwise each
                // is the game's own, jumped to with every register as it came. The filling keeps nothing in a register
                // across either call but what a function must keep, and sets what it reads after each anew.
                ulong harvestCell = at + CellsAfter + ScreenHarvestCell;
                foreach (var (name, offset) in new[] { ("FillScreen", ReadyCallAt), ("Tree", PlaceCallAt) })
                {
                    int call = screen.At[name] + offset;
                    stub = a.Here;
                    a.Hex("83 3D");                            // cmp dword [rip + the number], 0
                    a.Rip(harvestCell, 1);
                    a.Hex("00");
                    a.Short(ShortJne, "harvest" + name);
                    a.Near(Address(CallTarget(image, call)));  // jmp the game's own
                    a.Label("harvest" + name);
                    a.Hex("C3");                               // ret
                    made.Add(new Change(call, Instruction(0xE8, imageBase, call, stub, 5)));
                }

                // (1.39.2) The window's side: "the row's end less the place, compared with 3" with the row's end read
                // from the framework's own three (where the row would end were it full), by the row's number in rdx.
                // rcx is the game's to lose there (it sets it anew before its next use); the flags go back with the
                // compare's, for the game's own setle and jle.
                ulong sides = at + CellsAfter + ScreenSidesCell;
                stub = a.Here;
                a.Hex("48 8D 0D");                             // lea rcx, [rip + the three]
                a.I32((long)sides - (long)(a.Here + 4));
                a.Hex("8B 04 91");                             // mov eax, [rcx + rdx * 4]
                a.Hex("41 2B C0");                             // sub eax, r8d
                a.Hex("83 F8 03");                             // cmp eax, 3
                a.Hex("C3");                                   // ret
                made.Add(new Change(screen.At["Side"], Instruction(0xE8, imageBase, screen.At["Side"], stub, 6)));

                // (1.39.3) After each of the game's two calls of the filling the framework is told (the rows noted at
                // that filling for the unit's own job are moved to at once, by the filling again): the same call,
                // then the framework's. Nothing is kept in a register across a call of the filling but what a
                // function must keep.
                ulong afterCell = at + CellsAfter + ScreenAfterCell;
                stub = a.Here;
                a.Hex("48 83 EC 28");                          // sub rsp, 0x28
                a.Call(Address(screen.Fill));
                a.Hex("FF 15");                                // call [rip + its cell]
                a.I32((long)afterCell - (long)(a.Here + 4));
                a.Hex("48 83 C4 28 C3");                       // add rsp, 0x28; ret
                foreach (string name in new[] { "FillCalled", "FillCarded" })
                    made.Add(new Change(screen.At[name], Instruction(0xE8, imageBase, screen.At[name], stub, 5)));

                // (1.39.3) The job screen's end: the number that says a screen the framework arranged is there made 0,
                // then the game's own ending. No register and no flag is changed. (1.39.5: the layouts' move of a
                // box, 0x3EF684, is the game's own again; no box is moved by the framework.)
                ulong alive = at + CellsAfter + ScreenAliveCell;
                stub = a.Here;
                a.Hex("C7 05");                                // mov dword [rip + the number], 0
                a.Rip(alive, 4);
                a.Hex("00 00 00 00");
                a.Near(Address(screen.Ending));                // jmp the game's ending
                made.Add(new Change(screen.At["Ended"], Instruction(0xE8, imageBase, screen.At["Ended"], stub, 5)));

                // (1.39.4) The step from one job to the next on the abilities' page: the framework asked, with what
                // the game hands its own step (rcx, edx, r8d, r9) and the job screen (rbx) as a fifth.
                ulong cycleCell = at + CellsAfter + ScreenCycleCell;
                stub = a.Here;
                a.Hex("48 83 EC 38");                          // sub rsp, 0x38
                a.Hex("48 89 5C 24 20");                       // mov [rsp + 0x20], rbx
                a.Hex("FF 15");                                // call [rip + its cell]
                a.I32((long)cycleCell - (long)(a.Here + 4));
                a.Hex("48 83 C4 38");                          // add rsp, 0x38
                a.Hex("C3");                                   // ret
                made.Add(new Change(screen.At["Cycle"], Instruction(0xE8, imageBase, screen.At["Cycle"], stub, 5)));

                // (1.48.0) The window of what the job at the cursor needs: the framework asked in place of the game's
                // call (the screen in rcx, handed on as it is), which shows the game's own window over records it
                // finds every needed job in (JobScreen.Needs). Nothing is kept in a register across that call but
                // what a function must keep.
                ulong needsCell = at + CellsAfter + ScreenNeedsCell;
                stub = a.Here;
                a.Hex("48 83 EC 28");                          // sub rsp, 0x28
                a.Hex("FF 15");                                // call [rip + its cell]
                a.I32((long)needsCell - (long)(a.Here + 4));
                a.Hex("48 83 C4 28 C3");                       // add rsp, 0x28; ret
                made.Add(new Change(screen.At["NeedsCall"], Instruction(0xE8, imageBase, screen.At["NeedsCall"], stub, 5)));

                // (1.48.0) In the window, a job's slot asked (the job in cx) to read GeneralJob's row by and to find a
                // needed job among the places: a mod's job answers a number of its own (JobNeeds.Identity), which
                // its row of GeneralJob has as its key and other jobs' rows name it by; any other job goes on to the
                // slot's own function. As that function, this takes rax, rcx, rdx and the flags, and nothing is
                // loaded: a job's slot isn't asked here for its progress.
                stub = a.Here;
                a.Hex("0F B7 D1");                             // movzx edx, cx
                foreach (var g in given)
                {
                    a.Hex("81 FA");                            // cmp edx, its number
                    a.I32(g.Number);
                    a.Bytes(ShortJne, 6);
                    a.Bytes(0xB8);                             // mov eax, what it is known by
                    a.I32(JobNeeds.Identity(g.Number));
                    a.Bytes(0xC3);                             // ret
                }
                a.Near(Address(Site("Slot")));                 // jmp the slot's function
                foreach (string name in new[] { "NeedsSlot", "NeedsSame" })
                    made.Add(new Change(screen.At[name], Instruction(0xE8, imageBase, screen.At[name], stub, 5)));
            }

            // (1.41.3, his test 96) Arithmeticks's list (where found: `arithmeticks`, the start of its bytes). Its
            // skillsets, the game's four and then the jobs' own; three pieces in place of three of its own.
            // (1.55.0) The mods' own jobs' skillsets alone: the game's Dark Knight's is the game's, as in its own list.
            int rounds = ArithmeticksGame.Length + mods.Count;
            ulong skillsets = 0;
            if (arithmeticks >= 0 || arithmeticksThink >= 0)
            {
                skillsets = a.Here;
                a.Bytes(ArithmeticksGame);
                foreach (var g in mods)
                    a.Bytes((byte)g.Skillset);
            }
            if (arithmeticks >= 0)
            {
                int round = arithmeticks + ArithmeticksRoundAt, keep = arithmeticks + ArithmeticksKeepAt,
                    next = arithmeticks + ArithmeticksNextAt;

                // The round's skillset: rax and rdx are the game's to set here (it sets rax again at once, and the list
                // maker reads dl alone); then the game's own lea.
                ulong roundAt = a.Here;
                a.Hex("48 8D 05");                             // lea rax, [rip + the skillsets]
                a.Rip(skillsets);
                a.Hex("0F B6 14 38");                          // movzx edx, byte ptr [rax + rdi]
                a.Hex("48 8D 44 24 48");                       // lea rax, [rsp + 0x48]
                a.Near(Address(round + ArithmeticksRoundLength));
                made.Add(new Change(round, Instruction(0xE9, imageBase, round, roundAt, ArithmeticksRoundLength)));

                // A spell kept: none without a record (the getter's 0 for a number past 367 that is no mod's ability; a
                // job's skillset may hold one, an item's, a jump's, where the game's four never do, and the game would
                // read its flag at address 5), none without the flag, none past the most, none already in the list (ebp
                // words before rbx). rax and rcx are the game's to lose here (it sets both before it reads them again);
                // the flags too (its next is a compare).
                ulong keepAt = a.Here;
                a.Hex("48 85 C0");                             // test rax, rax
                a.Short(ShortJe, "arith skip");
                a.Bytes(image.Slice(keep, ArithmeticksTestLength).ToArray()); // test byte ptr [rax + 5], 0x40
                a.Short(ShortJe, "arith skip");
                a.Hex("83 FD");                                // cmp ebp, the most
                a.Bytes((byte)ArithmeticksMost);
                a.Short(0x73, "arith skip");                   // jae
                a.Hex("8B CD 48 8B C3");                       // mov ecx, ebp; mov rax, rbx
                ulong seen = a.Here;
                a.Hex("85 C9");                                // test ecx, ecx
                a.Short(ShortJe, "arith add");
                a.Hex("48 83 E8 02");                          // sub rax, 2
                a.Hex("66 44 39 38");                          // cmp word ptr [rax], r15w
                a.Short(ShortJe, "arith skip");
                a.Hex("FF C9");                                // dec ecx
                a.Bytes(ShortJmp, unchecked((byte)(sbyte)((long)seen - (long)(a.Here + 2)))); // jmp back to the test
                a.Label("arith add");
                a.Bytes(image.Slice(keep + ArithmeticksAddAt, ArithmeticksAddLength).ToArray()); // mov [rbx], r15w; add rbx, 2; inc ebp
                a.Label("arith skip");
                a.Near(Address(keep + ArithmeticksKeepLength));
                made.Add(new Change(keep, Instruction(0xE9, imageBase, keep, keepAt, ArithmeticksKeepLength)));

                // The step: as many rounds as skillsets.
                ulong nextAt = a.Here;
                a.Hex("48 FF C7");                             // inc rdi
                a.Hex("48 83 FF");                             // cmp rdi, the rounds
                a.Bytes((byte)rounds);
                a.Near(roundAt, 0x8C);                         // jl the round
                a.Near(Address(next + ArithmeticksNextLength));
                made.Add(new Change(next, Instruction(0xE9, imageBase, next, nextAt, ArithmeticksNextLength)));
            }

            // (1.41.4, his word on test 97) The units' two choices of an Arithmeticks spell (where found).
            if (arithmeticksThink >= 0 && arithmeticksRandom >= 0)
            {
                ulong spellCell = at + CellsAfter + ArithmeticksSpellCell;
                int round = arithmeticksThink + ThinkRoundAt, spell = arithmeticksThink + ThinkSpellAt;
                // Where the game's own jumps and calls go, read from its bytes: the round's end (its jge), the next
                // place (the spell's je), the kept byte, the getter.
                int roundsDone = round + 9 + I32(image, round + 5);
                int nextPlace = spell + 14 + (sbyte)image[spell + 13];
                int keptByte = spell + 10 + I32(image, spell + 6);
                int getter = spell + 21 + I32(image, spell + 17);

                // The thinking one's round: as many as the list's skillsets, the skillset read from the list (rcx is the
                // game's to set here, to the skillset); then the game's own cdqe and mov edx, 1.
                ulong thinkRound = a.Here;
                a.Hex("83 F8");                                // cmp eax, the rounds
                a.Bytes((byte)rounds);
                a.Near(Address(roundsDone), 0x8D);             // jge the walk's end
                a.Hex("48 98 BA 01 00 00 00");                 // cdqe; mov edx, 1
                a.Hex("48 8D 0D");                             // lea rcx, [rip + the skillsets]
                a.Rip(skillsets);
                a.Hex("0F B6 0C 01");                          // movzx ecx, byte ptr [rcx + rax]
                a.Near(Address(round + ThinkRoundLength));
                made.Add(new Change(round, Instruction(0xE9, imageBase, round, thinkRound, ThinkRoundLength)));

                // Its spell: the whole word, kept in the framework's cell and as the game's byte; none of 0, none
                // without a record, none without the flag (each to the next place, as the game's je goes).
                ulong thinkSpell = a.Here;
                a.Hex("0F B7 14 48");                          // movzx edx, word ptr [rax + rcx*2]
                a.Hex("88 15");                                // mov byte ptr [rip + the kept byte], dl
                a.Rip(Address(keptByte));
                a.Hex("66 89 15");                             // mov word ptr [rip + the cell], dx
                a.Rip(spellCell);
                a.Hex("85 D2");                                // test edx, edx
                a.Near(Address(nextPlace), 0x84);              // je the next place
                a.Hex("8B CA");                                // mov ecx, edx
                a.Call(Address(getter));
                a.Hex("48 85 C0");                             // test rax, rax
                a.Near(Address(nextPlace), 0x84);
                a.Hex("F6 40 05 40");                          // test byte ptr [rax + 5], 0x40
                a.Near(Address(nextPlace), 0x84);
                a.Near(Address(spell + ThinkSpellLength));
                made.Add(new Change(spell, Instruction(0xE9, imageBase, spell, thinkSpell, ThinkSpellLength)));

                // Its two reads of the kept byte read the cell's word (movzx ecx, word ptr [rip + the cell]).
                foreach (int read in new[] { arithmeticksThink + ThinkReadAt, arithmeticksThink + ThinkReadAgainAt })
                {
                    var bytes = new byte[ThinkReadLength];
                    bytes[0] = 0x0F; bytes[1] = 0xB7; bytes[2] = 0x0D;
                    BinaryPrimitives.WriteInt32LittleEndian(bytes.AsSpan(3),
                        checked((int)((long)spellCell - (long)Address(read + ThinkReadLength))));
                    made.Add(new Change(read, bytes));
                }

                // The random one's pick: the skillset of the list at the random number less every whole multiple of the
                // list's length (edx is 1 again for the lister, as the game set it; rcx is the game's to set).
                int pick = arithmeticksRandom + RandomPickAt, tries = arithmeticksRandom + RandomTriesAt,
                    test = arithmeticksRandom + RandomTestAt;
                int noRecord = test + RandomTestLength + (sbyte)image[test + RandomTestLength - 1];
                int randomGetter = test + 5 + I32(image, test + 1);
                ulong randomPick = a.Here;
                a.Hex("33 D2 B9");                             // xor edx, edx; mov ecx, the rounds
                a.I32(rounds);
                a.Hex("F7 F1");                                // div ecx
                a.Hex("48 8D 05");                             // lea rax, [rip + the skillsets]
                a.Rip(skillsets);
                a.Hex("44 0F B6 34 10");                       // movzx r14d, byte ptr [rax + rdx]
                a.Hex("BA 01 00 00 00");                       // mov edx, 1
                a.Near(Address(pick + RandomPickLength));
                made.Add(new Change(pick, Instruction(0xE9, imageBase, pick, randomPick, RandomPickLength)));

                // Its tries: 256 for each four of the list's skillsets.
                var bound = new byte[RandomTriesLength];
                bound[0] = 0x3D;
                BinaryPrimitives.WriteInt32LittleEndian(bound.AsSpan(1),
                    (RandomTries * rounds + ArithmeticksGame.Length - 1) / ArithmeticksGame.Length);
                made.Add(new Change(tries, bound));

                // Its test: none without a record.
                ulong randomTest = a.Here;
                a.Call(Address(randomGetter));
                a.Hex("48 85 C0");                             // test rax, rax
                a.Near(Address(noRecord), 0x84);
                a.Hex("F6 40 05 40");                          // test byte ptr [rax + 5], 0x40
                a.Near(Address(noRecord), 0x84);
                a.Near(Address(test + RandomTestLength));
                made.Add(new Change(test, Instruction(0xE9, imageBase, test, randomTest, RandomTestLength)));
            }

            // (1.42.0) Where a job has sprites of its own: the framework's own tests of a sprite and of the cell's job.
            bool ownSprites = false;
            foreach (var g in given)
                ownSprites |= g.Sprite >= 0;
            if (sprites != null && ownSprites)
                SpriteRoom.Code(a, sprites, imageBase, given, made);
            // (1.45.0) Where a job's own sprite has portraits of its own (its places found and its hook made: the sprites'
            // places hold them then): the face to portrait routine's answer for the framework's portraits, and the bounds
            // widened to them.
            bool ownPortraits = false;
            foreach (var g in given)
                ownPortraits |= g.Sprite >= 0 && (g.Portraits[0] || g.Portraits[1]);
            if (sprites?.Portraits != null && ownPortraits)
                SpritePortraits.Code(a, sprites.Portraits, imageBase, made);

            // (1.53.0, Zodi's order of 13 November: "jobs in a quest's battle") A unit of a battle's file in a mod's job
            // (where found: FindBattleUnits). The game's setup of its abilities (0x2771C8) learns in a loop over the twenty
            // generic jobs alone, so the job a unit is in is learned too, after the loop, by the game's own routines handed
            // what the loop hands them; and one ability's learning (0x2780B0) writes slot 22's into the job's own row.
            // (1.55.0) The mods' own jobs alone: a unit of a battle's file in the game's Dark Knight or Onion Knight is left
            // to the game.
            if (battleOwn >= 0 && battleRow >= 0 && battleLearn >= 0)
                BattleCode(a, mods, imageBase, battleOwn, battleRow, battleLearn, (int)found.StartJp, made);

            changes = made;
            return a.Done();
        }

        /// <summary>(1.53.0) The two pieces for a unit of a battle's file in a mod's job (dev/research/sidequests/
        /// quest_jobs.py), written in `a`, and the calls of them in place of the game's bytes at `own` and `row`.
        ///
        /// In place of the learned row's start in one ability's learning (`row`, 0x2780B0: rbp the slot, rdi the unit):
        /// slot 22's row is the job's own (Mime's, OwnRow), as every other reach of a learned row gives it, where the game
        /// would take the unit's level bytes for a row 22; its JP stays slot 22's. Every register but rdx and r9 (the two
        /// the game's instructions set) and the flags (set again before they are read) as it was.
        ///
        /// In place of what follows the setup's loop over the generic jobs (`own`, 0x2771C8: rdi the unit, rbp the entry,
        /// r15 the first list and r14d its count, rbx the second list; the sex's byte, the flag and the second list's count
        /// on its frame): where the unit's job is one of the jobs given, its slot 22's level is the entry's job level (its
        /// tenth byte's low nibble, 1 to 8), its JP is the game's own for that level (`startJp`, 0x2770BC: the unit, the
        /// sex's byte, the slot, the level), and its job is learned by the game's own learning (`learn`, 0x2781A8), handed
        /// what the loop hands it for a job, with the job open to the unit for that call only (slot 22's bit of its open
        /// jobs). Then the game's two instructions it stands in for. The calls keep the stack 16 bytes aligned with room for
        /// their four arguments; rax, rcx, rdx, r8 to r11 and the flags are set again by the game's code after it.</summary>
        static void BattleCode(Destinations.Asm a, IList<Given> given, ulong imageBase, int own, int row, int learn,
                               int startJp, List<Change> made)
        {
            ulong Address(int rva) => imageBase + (ulong)rva;
            ulong rowStub = a.Here;
            a.Hex("4D 63 C8");                                 // movsxd r9, r8d
            a.Hex("48 8D 55 36");                              // lea rdx, [rbp + 0x36]
            a.Hex("83 FD");                                    // cmp ebp, 22
            a.Bytes((byte)Slot);
            a.Short(ShortJne, "battleRowDone");
            a.Bytes(0xBA);                                     // mov edx, the job's own row + 0x36
            a.I32(OwnRow + 0x36);
            a.Label("battleRowDone");
            a.Bytes(0xC3);
            made.Add(new Change(row, SpriteRoom.CallFrom(imageBase, row, rowStub, BattleRowLength)));

            ulong ownStub = a.Here;
            a.Hex("48 83 EC 48");                              // sub rsp, 0x48
            a.Hex("0F B6 57");                                 // movzx edx, byte ptr [rdi + its job]
            a.Bytes((byte)BattleUnitJob);
            for (int k = 0; k < given.Count; k++)
            {
                a.Hex("81 FA");                                // cmp edx, the job's number
                a.I32(given[k].Number);
                a.NearTo("battleOwnJob", 0x84);                // je
            }
            a.NearTo("battleOwnBack");
            a.Label("battleOwnJob");
            // Its level: the entry's job level, 1 to 8.
            a.Hex("44 0F B6 4D");                              // movzx r9d, byte ptr [rbp + the job level]
            a.Bytes((byte)EntryJobLevel);
            a.Hex("41 83 E1 0F");                              // and r9d, 0xF
            a.Short(ShortJne, "battleOwnSome");
            a.Hex("41 B9 01 00 00 00");                        // mov r9d, 1
            a.Label("battleOwnSome");
            a.Hex("41 83 F9");                                 // cmp r9d, 8
            a.Bytes((byte)MostJobLevel);
            a.Short(0x76, "battleOwnLevel");                   // jbe
            a.Hex("41 B9");                                    // mov r9d, 8
            a.I32(MostJobLevel);
            a.Label("battleOwnLevel");
            // Slot 22's level nibble: the high half of the twelfth level byte.
            int nibble = BattleLevels + Slot / 2;
            a.Hex("8A 87");                                    // mov al, [rdi + the byte]
            a.I32(nibble);
            a.Hex("24 0F");                                    // and al, 0xF
            a.Hex("44 88 C9");                                 // mov cl, r9b
            a.Hex("C0 E1 04");                                 // shl cl, 4
            a.Hex("08 C8");                                    // or al, cl
            a.Hex("88 87");                                    // mov [rdi + the byte], al
            a.I32(nibble);
            // Its JP: the game's own for the level.
            a.Hex("48 8B CF");                                 // mov rcx, rdi
            a.Hex("8A 94 24");                                 // mov dl, [rsp + 0x50 + the sex's byte]
            a.I32(0x50 + FrameSex);
            a.Hex("41 B8");                                    // mov r8d, 22
            a.I32(Slot);
            a.Call(Address(startJp));
            // The job open to the unit for the learning's call only.
            a.Hex("8A 87");                                    // mov al, [rdi + the open jobs' last byte]
            a.I32(BattleOpenLast);
            a.Hex("88 44 24 40");                              // mov [rsp + 0x40], al
            a.Hex("80 8F");                                    // or byte ptr [rdi + the open jobs' last byte], slot 22's bit
            a.I32(BattleOpenLast);
            a.Bytes((byte)BattleOpenBit);
            // Its abilities: the game's own learning, handed what the loop hands it.
            a.Hex("8B 84 24");                                 // mov eax, [rsp + 0x50 + the second list's count]
            a.I32(0x50 + FrameSecondCount);
            a.Hex("89 44 24 30");                              // mov [rsp + 0x30], eax
            a.Hex("8A 84 24");                                 // mov al, [rsp + 0x50 + the flag]
            a.I32(0x50 + FrameFlag);
            a.Hex("88 44 24 38");                              // mov [rsp + 0x38], al
            a.Hex("48 89 5C 24 28");                           // mov [rsp + 0x28], rbx
            a.Hex("44 89 74 24 20");                           // mov [rsp + 0x20], r14d
            a.Hex("0F B6 57");                                 // movzx edx, byte ptr [rdi + its job]
            a.Bytes((byte)BattleUnitJob);
            a.Hex("4D 8B CF");                                 // mov r9, r15
            a.Hex("4C 8B C5");                                 // mov r8, rbp
            a.Hex("48 8B CF");                                 // mov rcx, rdi
            a.Call(Address(learn));
            a.Hex("8A 44 24 40");                              // mov al, [rsp + 0x40]
            a.Hex("88 87");                                    // mov [rdi + the open jobs' last byte], al
            a.I32(BattleOpenLast);
            a.Label("battleOwnBack");
            a.Hex("48 83 C4 48");                              // add rsp, 0x48
            a.Hex("8A 45 1D BB 00 00 00 00 C3");               // mov al, [rbp + 0x1D]; mov ebx, 0; ret
            made.Add(new Change(own, SpriteRoom.CallFrom(imageBase, own, ownStub, BattleOwnLength)));
        }

        // --- the Job table --------------------------------------------------------------------------------------------

        /// <summary>A job's row: the fields of the job it looks like (its art, its help, its JP sort) and its own name,
        /// description and skillset, all words after the 64 bytes and an empty word they may point at. (1.46.0) `icon`: its
        /// icon's number (TexturePartsIndex) where it isn't its Like's (the job's own, or the game's job's it picks), else
        /// -1. (1.47.0) `help`: the key of its own row of the job help table (JobWords.HelpKey: its words on Job Summary),
        /// or -1 for its Like's. (1.55.2) `words`: a description in place of its own (the game's Onion Knight's for its
        /// level 8, in the row of the job the game takes a level 8 Onion Knight's words from).</summary>
        public static byte[] JobRow(ReadOnlySpan<byte> likeRow, ModJob job, int icon = -1, int help = -1, string? words = null)
        {
            byte[] name = Encoding.UTF8.GetBytes(job.WordName), description = Encoding.UTF8.GetBytes(words ?? job.Description);
            int empty = RowBytes, nameAt = empty + 1, descriptionAt = nameAt + name.Length + 1;
            int size = (descriptionAt + description.Length + 1 + 3) & ~3;
            var row = new byte[size];
            likeRow.Slice(0, RowBytes).CopyTo(row);
            void Put(int at, int value) => BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(at), value);
            Put(RowFirstWord, empty);
            Put(RowNameAt, nameAt - RowWordsFrom);
            Put(RowUnknown4At, empty - RowWordsFrom);
            Put(RowDescriptionAt, descriptionAt - RowWordsFrom);
            Put(RowUnknown6At, empty - RowWordsFrom);
            Put(RowCommandAt, job.Record[0]);
            Put(RowHideTreeAt, 0);
            if (icon >= 0)
                Put(JobArt.JobIconAt, icon);
            if (help >= 0)
                Put(JobWords.JobHelpAt, help);
            name.CopyTo(row, nameAt);
            description.CopyTo(row, descriptionAt);
            return row;
        }

        /// <summary>The loaded Job table (its loaded language's) with the jobs' rows in place of the numbers' empty ones,
        /// or null and why.</summary>
        public static byte[]? WithJobRows(ReadOnlySpan<byte> table, IEnumerable<Given> given, List<string> said, out string why)
        {
            why = "";
            if (Nxd.Keys(table) != 1)
            {
                why = "it isn't a table of one key";
                return null;
            }
            var rows = new List<NewRow>();
            foreach (var g in given)
            {
                int at = Nxd.Find(table, new[] { g.Job.Like });
                if (at < 0 || at + RowBytes > table.Length)
                {
                    said.Add($"{g.Job.Who} has no name in the game: the table has no row for job {g.Job.Like}.");
                    continue;
                }
                rows.Add(new NewRow(new[] { g.Number }, JobRow(table.Slice(at, RowBytes), g.Job, IconOf(table, g, said),
                                                               JobWords.HelpKey(g.Number))));
                // (1.55.2, Zodi's word on test 123: "the description for Onion Knight is still not correct") The game's
                // Onion Knight with a description for its level 8: the row of the job the game takes a level 8 Onion
                // Knight's words from (164, empty in the game) is its row with that description and its level 8 Job Summary,
                // read by the job screen's window where the unit's Onion Knight is level 8 (HelpWordsSites).
                if (g.Number == JobFile.OnionKnight && g.Job.MasteredDescription != null)
                    rows.Add(new NewRow(new[] { JobFile.MasteredOnion },
                                        JobRow(table.Slice(at, RowBytes), g.Job, IconOf(table, g, said),
                                               JobWords.HelpKey(JobFile.MasteredOnion), g.Job.MasteredDescription)));
            }
            // (1.40.0) Past the game's last number the rows go on without a gap, so a row's place in the table is its
            // number, as it is for the game's own 174: a number between that no job has now (kept for a mod that isn't
            // enabled) gets a row with no name.
            var have = new HashSet<int>();
            int last = -1;
            foreach (var g in given)
            {
                have.Add(g.Number);
                last = Math.Max(last, g.Number);
            }
            int blank = Nxd.Find(table, new[] { FreeNumbers[0] });
            for (int n = JobRecords.GameCount; n < last; n++)
                if (!have.Contains(n) && Nxd.Find(table, new[] { n }) < 0 && blank >= 0 && blank + RowBytes <= table.Length)
                    rows.Add(new NewRow(new[] { n }, BlankRow(table.Slice(blank, RowBytes))));
            return Nxd.WithRows(table, rows, out why, replace: true);
        }

        /// <summary>(1.46.0) A job's icon's number in its row: the job's own number for its own icon (the framework names
        /// its part list for it, JobArtHooks), the game's job's it picks (that row's), or -1 for its Like's.</summary>
        static int IconOf(ReadOnlySpan<byte> table, Given g, List<string> said)
        {
            if (g.IconOwn)
                return g.Number;
            int pick = g.Job.Art.IconJob;
            if (pick <= 0)
                return -1;
            int at = Nxd.Find(table, new[] { pick });
            if (at < 0 || at + RowBytes > table.Length)
            {
                said.Add($"{g.Job.Who} keeps its Like's icon: the table has no row for job {pick}.");
                return -1;
            }
            return BinaryPrimitives.ReadInt32LittleEndian(table.Slice(at + JobArt.JobIconAt, 4));
        }

        /// <summary>(1.40.0) A row with no name, for a number past the game's last that no job has now: the fields of
        /// one of the game's own unused rows, every word the empty one.</summary>
        public static byte[] BlankRow(ReadOnlySpan<byte> likeRow)
        {
            int empty = RowBytes;
            var row = new byte[(empty + 1 + 3) & ~3];
            likeRow.Slice(0, RowBytes).CopyTo(row);
            void Put(int at, int value) => BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(at), value);
            Put(RowFirstWord, empty);
            Put(RowNameAt, empty - RowWordsFrom);
            Put(RowUnknown4At, empty - RowWordsFrom);
            Put(RowDescriptionAt, empty - RowWordsFrom);
            Put(RowUnknown6At, empty - RowWordsFrom);
            return row;
        }

        // --- the JobCommand table --------------------------------------------------------------------------------------

        /// <summary>A skillset's row: the icon of the skillset it looks like, its own name and description, itself as
        /// the command it is the same as (the game takes two skillsets as one command by that field: 0xF7334), all
        /// words after the row's fixed part and an empty word the others point at.</summary>
        public static byte[] CommandRow(ReadOnlySpan<byte> likeRow, ModJob job, int skillset, int icon = -1)
        {
            byte[] name = Encoding.UTF8.GetBytes(job.SkillsetName), description = Encoding.UTF8.GetBytes(job.SkillsetDescription);
            int empty = CommandRowBytes, nameAt = empty + 1, descriptionAt = nameAt + name.Length + 1;
            int size = (descriptionAt + description.Length + 1 + 3) & ~3;
            var row = new byte[size];
            likeRow.Slice(0, CommandRowBytes).CopyTo(row);
            void Put(int at, int value) => BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(at), value);
            Put(CommandNameAt, nameAt - RowWordsFrom);
            Put(CommandDescriptionAt, descriptionAt - RowWordsFrom);
            Put(CommandDescription2At, empty - RowWordsFrom);
            Put(CommandSameAt, skillset);
            Put(CommandCommentAt, empty);
            if (icon >= 0)
                Put(JobArt.CommandIconAt, icon);
            name.CopyTo(row, nameAt);
            description.CopyTo(row, descriptionAt);
            return row;
        }

        /// <summary>The loaded JobCommand table (its loaded language's) with the jobs' skillsets' rows in place of the
        /// numbers' empty ones, or null and why.</summary>
        public static byte[]? WithCommandRows(ReadOnlySpan<byte> table, IEnumerable<Given> given, List<string> said,
                                              out string why)
        {
            why = "";
            if (Nxd.Keys(table) != 1)
            {
                why = "it isn't a table of one key";
                return null;
            }
            var rows = new List<NewRow>();
            foreach (var g in given)
            {
                if (g.Skillset == 0)
                    continue;                                  // (1.55.0) the game's Onion Knight has no skillset
                int at = Nxd.Find(table, new[] { g.Job.SkillsetLike });
                if (at < 0 || at + CommandRowBytes > table.Length)
                {
                    said.Add($"{g.Job.Who}'s skillset has no name in the game: the table has no row for skillset "
                             + $"{g.Job.SkillsetLike}.");
                    continue;
                }
                rows.Add(new NewRow(new[] { g.Skillset }, CommandRow(table.Slice(at, CommandRowBytes), g.Job, g.Skillset,
                                                                     CommandIconOf(table, g, said))));
            }
            return Nxd.WithRows(table, rows, out why, replace: true);
        }

        /// <summary>(1.46.0) A job's skillset's icon's number in its row: the job's own number for its own icon (the
        /// framework names its part list for it, JobArtHooks), the game's skillset's it picks (that row's), or -1 for its
        /// Like's.</summary>
        static int CommandIconOf(ReadOnlySpan<byte> table, Given g, List<string> said)
        {
            if (g.CommandOwn)
                return g.Number;
            int pick = g.Job.Art.CommandSkillset;
            if (pick <= 0)
                return -1;
            int at = Nxd.Find(table, new[] { pick });
            if (at < 0 || at + CommandRowBytes > table.Length)
            {
                said.Add($"{g.Job.Who}'s skillset keeps its Like's icon: the table has no row for skillset {pick}.");
                return -1;
            }
            return BinaryPrimitives.ReadInt32LittleEndian(table.Slice(at + JobArt.CommandIconAt, 4));
        }

        // --- the job screen's other page ------------------------------------------------------------------------------

        /// <summary>Dark Knight &amp; Onion Knight (Generic), its id, and what is read of it: the object its Reloaded-II
        /// mod holds, its list of the second page's jobs.</summary>
        public const string OtherMod = "ffttic.jobs.genericjobs", OtherModField = "_mod", OtherListField = "_extraJobs";

        /// <summary>The numbers added to the list the other mod's second page shows, the object its Reloaded-II mod holds
        /// (`startup`); what stops it, or null when done.</summary>
        public static string? OnTheirPage(object startup, IEnumerable<int> numbers)
        {
            const BindingFlags Field = BindingFlags.Instance | BindingFlags.NonPublic;
            var modField = startup.GetType().GetField(OtherModField, Field);
            object? mod = modField?.GetValue(startup);
            if (mod == null)
                return $"it has no {OtherModField}";
            var listField = mod.GetType().GetField(OtherListField, Field);
            if (listField == null || listField.GetValue(mod) is not ushort[] had)
                return $"it has no {OtherListField} of job numbers";
            var list = new List<ushort>(had);
            foreach (int n in numbers)
                if (!list.Contains((ushort)n))
                    list.Add((ushort)n);
            listField.SetValue(mod, list.ToArray());
            return null;
        }

        // --- a save -------------------------------------------------------------------------------------------------

        /// <summary>(1.37.1) The skillset numbers the framework gave a mod's job that isn't here now: every number its
        /// numbers remember having given, but for the ones given this time.</summary>
        public static HashSet<int> Gone(Numbers numbers, ICollection<int> skillsets)
        {
            var gone = new HashSet<int>(numbers.Used(Numbers.SkillsetsKind));
            gone.ExceptWith(skillsets);
            return gone;
        }

        /// <summary>A save's units in a job no mod gives now put on a job of the game's as it loads: a generic unit
        /// on Squire, a story unit on its own (the job its first byte names, as the game's job list starts them).
        /// (1.37.1) A unit's second skillset is taken off only when it is one of `gone`: the numbers the framework
        /// gave a mod's job that isn't here now. Zodi's test 78: 1.37.0 took off any free number no mod of its own
        /// gave ("2 units had a second skillset no mod gives now"), which two of his units had from elsewhere; the
        /// game itself shows a second skillset it can't place as none (0x367939). What was done, or null.</summary>
        /// (1.55.0) `gameJobs`: whether the game's own Dark Knight and Onion Knight are the framework's to settle (Dark
        /// Knight &amp; Onion Knight (Generic) is off): a unit in one no mod gives now is put on a job of the game's the
        /// same way (the game never puts a unit in either: it was the framework's, through a mod no longer on).
        public static string? Settle(Span<byte> roster, ICollection<int> given, ICollection<int> gone, bool gameJobs = false)
        {
            int moved = 0, cleared = 0;
            for (int n = 0; (n + 1) * Framework.RosterUnitBytes <= roster.Length && n < Framework.RosterUnits; n++)
            {
                var unit = roster.Slice(n * Framework.RosterUnitBytes, Framework.RosterUnitBytes);
                if (unit[1] == 0xFF)
                    continue;
                // (1.37.0) A man's, a woman's or a story unit's second skillset that was a mod's job's own.
                if (unit[0] <= 0x81 && gone.Contains(unit[UnitSecond]))
                {
                    unit[UnitSecond] = 0;
                    cleared++;
                }
                bool gameJob = gameJobs && (unit[2] == JobFile.DarkKnight || unit[2] == JobFile.OnionKnight);
                if (!JobRecords.Given(unit[2]) && !gameJob || given.Contains(unit[2]))
                    continue;
                if (unit[0] == 0x80 || unit[0] == 0x81)
                    unit[2] = FirstGeneric;
                else if (unit[0] < 0x80)
                    unit[2] = unit[0];
                else
                    continue;
                moved++;
            }
            var said = new List<string>();
            if (moved > 0)
                said.Add($"{moved} unit{(moved == 1 ? " was" : "s were")} in a job no mod gives now: put on a job of the game's "
                         + "as the save loaded.");
            if (cleared > 0)
                said.Add($"{cleared} unit{(cleared == 1 ? "" : "s")} had a second skillset no mod gives now: taken off as the "
                         + "save loaded.");
            return said.Count == 0 ? null : string.Join(" ", said);
        }
    }
}
