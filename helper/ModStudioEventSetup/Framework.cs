// Mod Studio Framework: the side quests' framework. Part of The Ivalice
// Chronicles Mod Studio, GPL-3.0.
//
// Zodi's goal (26 October): "Adding new events on new maps for new battles
// while maintaining compatibility so different modders can create hundreds
// of new side quests that users can have loaded and can play", and his rule:
// a modder never chooses a number. Each quest names what it adds; this gives
// each name a number of the game's as the game starts (kept in Numbers.json,
// the same every time), writes the quests' events' setup records into the
// empty slots after the game's, adds their rows to the game's tables as the
// game loads them (after every row the loaded table has, so the story and
// other mods come first), hands the game their scripts by number, keeps
// their flags in the part of the game's saved variables nothing uses, and
// (1.2.0) gives their battles what the game's have: their units by a number
// of their own, battle rules, a deploy prompt and a row of the battles'
// units table. (1.2.1) A quest's event never moves the story: what a story
// scene's script copied into a quest would set of the game's progress (its
// instruction E9), or of the story's progress variable, is left out as it
// plays; (1.2.2) and never blocks the way: a quest's event waiting where you
// stand doesn't stop travel on, as the game's own events do (it plays when
// you come back); (1.2.4) and, unless its start says it stops a passing
// travel ("Passing": "Stops", as the game's own events do), waits until its
// place is chosen: a travel passing through goes on. (1.8.0) A start at one
// of its mod's own places (by its name) is added at the number the places
// were given (Destinations.cs): the world map runs a place's chains by its
// number whatever it is (0x343AF8), as Ramza arrives or chooses it. (1.10.0)
// An event's setup naming one of its mod's quest maps gets the number the
// quest maps were given (MapRoom.cs): its setup record's map, and its
// battle's deploy prompt's.
//
// Everything here works on bytes, so Mod Studio's checks run it over the
// game's program and tables laid out as in memory; Hooks.cs joins it to the
// running game, and Places.cs finds where. What was measured is in Mod
// Studio's notes (claude/event-script-research.md, "Side quests from many
// mods") and dev/research/sidequests/.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Text;

namespace ModStudioEventSetup
{
    public sealed class Framework
    {
        // --- what was measured in the game ---------------------------------

        /// <summary>The event variables are one block of 1,024 bytes (the program's bank, which a
        /// new game clears whole and every save and load copies whole); the variables use its
        /// first 684 (128 words, 736 bits from byte 512, 160 four-bit values from byte 604) and no
        /// code reads the rest. The quests' flags are its last 340 bytes' bits.</summary>
        public const int BankBytes = 0x400, BankTail = 0x2AC;
        /// <summary>(1.13.0) The bank's last 4 bytes: the mark of the numbers a save was made with (their ID,
        /// Numbers.Id), written as a quest flag is set and looked at as a save loads (SaveFallbackHook); the quests'
        /// flags the bits before it (4096 to 6783: far past any Zodi's numbers ever gave).</summary>
        public const int MarkAt = BankBytes - 4;
        public const int FlagBits = (MarkAt - BankTail) * 8;
        /// <summary>A quest flag's variable number: from 4096 up, past the game's 1,024 (the
        /// scripts and the world map hold a variable's number in 16 bits).</summary>
        public const int FlagBase = 0x1000;
        /// <summary>(1.2.4) A variable of the framework's own, never the game's (past its 1,023,
        /// before the flags' 4096): 1 while a travel passes through the place whose chains the
        /// world map runs (a travel under way, with roads still to go after this place), else 0.
        /// A start that waits until its place is chosen tests it last, so a travel passing
        /// through doesn't load its event.</summary>
        public const int PassingThrough = FlagBase - 1;
        /// <summary>(1.2.4) What is said, once, when a travel passing through doesn't load an event
        /// that waits until its place is chosen.</summary>
        public const string PassingGoesOn = "a side quest's event here waits until its place is chosen: a travel "
                                            + "passing through goes on.";
        /// <summary>The game's variable that says an event is being replayed: the game's variable
        /// functions then refuse writes to all but a few variables, so a replay never changes the
        /// save; a quest flag is one of the refused.</summary>
        public const int ReplayVariable = 0x1FC;
        /// <summary>(1.2.1) The event playing's number (variable 0x27: the game sets it to an event
        /// to load it, and as an event ends to the one its record has next, 0 for the world map),
        /// and the story's progress (variable 0x6E, 110, which the world map's story steps test and
        /// the story's scenes set): while one of the quests' events plays, a change to the story's
        /// progress is left out (Hooks.EventVariables).</summary>
        public const int CurrentEvent = 0x27, StoryProgress = 0x6E;
        /// <summary>(1.2.1) A script's instruction that sets the game's progress: E9, a track (0 the
        /// story's) and its value, two 32-bit numbers. The world map shows the objective and markers
        /// of the point track 0 names; a story scene sets it at its end.</summary>
        public const byte ProgressInstruction = 0xE9;
        /// <summary>The tables' numbers in the program (nxd/root.nxl's): the world map's starts, the
        /// scenes' words, the words' files and the battle rules. Each loaded table is checked for
        /// its own shape before rows are added.</summary>
        public const int WorldStarts = 0xC7, Scenes = 0x3B, Texts = 0xA9, Rules = 0xA3;
        /// <summary>The events' own table (EventId, one row an event, found by its number): what the
        /// world map shows before an event it loads (a union of a table and its key at 0x10, the
        /// game's openings' a SortieConfirm row), and at 0x20 a byte every scene the game's
        /// openings start and that goes back to the world map or on has 1.</summary>
        public const int EventRows = 0x9C;
        public const int EventRowShows = 0x10, EventRowScene = 0x20, EventRowBytes = 0x2C;
        /// <summary>The game's own opening whose EventId row a quest's opening's is made like
        /// (Gariland's, 13, before its scene 14).</summary>
        public const int GameOpening = 13;
        /// <summary>The last event number the program's tables hold (887 slots, 0 to 886; its
        /// search for a setup record stops after 887); (1.9.0) once the helper has moved them,
        /// EventRoom.LastEvent and EventRoom.Events.</summary>
        public const int LastEvent = 886, SearchedSlots = 887;
        /// <summary>The numbers the game's own scripts have (its script/enhanced, 560 files), and
        /// the downloadable content's two: never given.</summary>
        static readonly (int First, int Last)[] GameScripts =
        {
            (0, 491), (590, 591), (593, 593), (595, 595), (750, 750), (755, 755), (760, 764), (770, 773),
            (780, 784), (790, 790), (795, 796), (800, 802), (805, 807), (810, 811), (815, 816), (820, 822),
            (825, 827), (830, 832), (835, 840), (845, 849), (855, 855), (860, 861), (865, 866), (870, 871),
            (875, 882), (885, 886),
        };
        /// <summary>Keys the framework gives: battle rules from 16384 to 32767 (a setup record's
        /// bytes 22 and 23, which the program reads as a signed 16-bit number), scenes', words'
        /// and deploy prompts' keys from 900000; each checked against the loaded table.</summary>
        public const int FirstRules = 0x4000, LastRules = 0x7FFF, FirstScene = 900000, FirstText = 900000,
                         FirstPrompt = 900000;
        /// <summary>The numbers a quest's own battles are given: past the game's (0 to 511) and the
        /// add-on file's room (512 to 591), up to what a setup record's signed 16 bits hold. The
        /// program reads a battle past 511 from the add-on file into room for 80; a quest's is
        /// handed to it by the framework instead (Hooks.Encounter).</summary>
        public const int FirstBattle = 0x1000, LastBattle = 0x7FFF;
        /// <summary>The battles' units table (EntryNo, one row a battle by its number, which the
        /// formation screen needs for every battle: the program reads a missing row's fields at
        /// address 8) and the deploy prompts' (SortieConfirm, one row a prompt by its key).</summary>
        public const int EntryRows = 0x6D, Prompts = 0x36;
        public const int EntryRowBytes = 0x1C, PromptRowBytes = 0x30;
        /// <summary>A deploy prompt's fields: its map at 4, what it is at 0x10 (1507 a battle's, 1506
        /// a scene's), a threat at 0x1C (-1 none).</summary>
        const int PromptMap = 4, PromptKind = 0x10, PromptThreat = 0x1C, BattlePrompt = 1507;
        /// <summary>(1.17.0) A battle's deploy prompt's key in its EntryNo row (the game's random battles' only: the
        /// world map's prompt, 0x2477C8, finds it through 0xFB65C); a prompt the world map shows has a byte at 0x2C
        /// (the game's random battles' 1, its story battles' 0).</summary>
        const int EntryPrompt = 8, PromptShown = 0x2C;
        /// <summary>How the world map loads a battle (the start's second number).</summary>
        public const int BattleMode = 1;
        /// <summary>(1.11.1) The game's battle start (event 401: a sweep of the camera and its objective, "Defeat all
        /// enemies!"), which its random battles play as they start (the scenario check `0x2387C4`, while the battle
        /// isn't started, 509): a quest's battle without a start event of its own starts with it.</summary>
        public const int BattleStart = 401;
        /// <summary>(1.12.0) The battle rules' tests of a unit (its unit ID by the CharaControlId key that names it,
        /// QuestFile.NamedUnit): there (4), its HP at most a number (6), its HP in hundredths of its most at most a
        /// number (8), on a tile (24: its x, y and upper level); as `0x239294` tests them and the game's battles use them
        /// (dev/research/sidequests/battle_rules.py: 17 won once a unit is beaten, 8 once its HP is down to a share,
        /// the sluice at Fort Besselat by Ramza on a tile, 10 lost once a unit is beaten).</summary>
        public const short Present = 4, HpAtMost = 6, ShareAtMost = 8, OnTileStep = 24;
        /// <summary>(1.31.0) The tests a scene during a battle needs besides those: a unit's HP at least a number (5) and
        /// the unit acting, its turn come (11), as Gariland's battle plays its event 11 on Ramza's turn (key 3's second
        /// chain) and the game's battles start 115 of their rules (in 33 battles) on a unit's turn.</summary>
        public const short HpAtLeast = 5, Acting = 11;
        /// <summary>(1.12.0) Ramza, by chapter, as the rules name a member of the player's party (1, 2 and 3: the
        /// game's sluice names 3); a battle won with Ramza on a tile is won by whichever is there.</summary>
        public static readonly int[] Ramzas = { 1, 2, 3 };
        /// <summary>(1.12.0) What follows an event once its battle is lost: the game starts over (its own lost scenes,
        /// 21 and nine more, have 0x82).</summary>
        public const int StartOver = 0x82;
        /// <summary>(1.12.0) The battles' objectives (BattleObjective, sheet 0x2F, its loaded language's: a row's words
        /// pointed at from its Name, + 4, IsProtectionMission at + 0xC; 16 bytes, then its words): the keys a quest's
        /// battle's objective is given (past the game's 0 to 68; DisplayConditions shows the key + 8, one byte), and the
        /// first of DisplayConditions' numbers that is an objective.</summary>
        public const int Objectives = 0x2F, ObjectiveRowBytes = 0x10, FirstObjective = 69, LastObjective = 247,
                         FirstShown = 8, ObjectiveName = 4, ObjectiveProtects = 0xC;
        /// <summary>(1.15.0) The taverns' rumors (Gossip, sheet 0xB5, its loaded language's: 48 bytes a row, its title's
        /// and words' places at + 0xC and + 0x10, each counted from + 0xC, as the tavern's screen reads them at
        /// 0x1A041C; two lists at + 0x14 and + 0x1C, empty, pointed at the row's end as the game's are): the keys a
        /// quest's rumor is given, past the game's 23 and WotL Restoration's 4, up to the last the taverns list
        /// (0x36EE50: 0 to 63; RumorKeys, measured); a town's bit, as the program's masks of the game's rumors hold
        /// them (0x4000 shifted right by the town's place, 0 to 14), every town's.</summary>
        public const int Rumors = 0xB5, RumorRowBytes = 0x30, RumorTitle = 0x0C, RumorText = 0x10, RumorLists = 0x14,
                         FirstRumor = 27, LastRumor = 63, TownBit = 0x4000, EveryTavern = 0x7FFF;
        /// <summary>(1.29.0) The numbers' kind of the rumors' keys, numbered as each game starts (Numbers.EachStart).</summary>
        public const string RumorsKind = "Rumors";
        /// <summary>The battle rules' step that passes once every enemy is beaten.</summary>
        public const short EnemiesDefeated = 22;
        /// <summary>The variable the game's own victory steps test first (0x80, the first of a
        /// scenario's bits, which the game clears as each one loads): 26 of its battles win with
        /// it 0 and every enemy beaten.</summary>
        public const int VictoryGuard = 128;
        /// <summary>EventId's fields for battles: the battle's first scene's number at 4 (each of
        /// its scenes', as the game's), the union's table (7, SortieConfirm) and key at 0x10.</summary>
        public const int EventRowFirstScene = 4, PromptUnion = 7;
        /// <summary>Every world map event of the game is an opening of three instructions (the
        /// map comes in, a wait, the end) whose battle rules start its scene when the
        /// battle-loaded variable (509) is 1; a quest's opening is the same.</summary>
        public static readonly byte[] OpeningScript = { 0x4D, 0x02, 0xF1, 0x1E, 0x00, 0xDB };
        public const int BattleLoaded = 509;
        /// <summary>How the world map loads a scene's opening (the start's second number; 1 is a battle's).</summary>
        public const int SceneMode = 2;
        /// <summary>The world map's and the battle rules' step types (the PlayStation's location
        /// script instructions): a variable equal to a number, at least, at most, a character in
        /// the party, load an event.</summary>
        public const short Equal = 1, AtLeast = 2, AtMost = 3, InParty = 4, LoadEvent = 25;
        /// <summary>What follows an event (its setup's byte 20): the world map, its next event.</summary>
        public const int WorldMap = 0x80, NextEvent = 0x81;
        /// <summary>(1.30.0) Map 116, "(No name) - Battle Arena" in the map table's comments, where Mod Studio's samples
        /// play (11 by 11, flat, no event of the game's set on it). Its Map row's name (Unknown8, its + 8) is PlaceName
        /// 10100, which has no row (maps 0, 101, 102 and 104 name it too: the empty map, the two tutorials', the
        /// Beoulve manse's), so the plate naming the map as a battle starts showed nothing (Zodi's test 64). The game
        /// reads a map's name from its Map row's + 8 (0x102BDC, 0x148D24: PlaceName's Title by 0xFB44C); the framework
        /// gives map 116's row the key a quest map numbered 116 would have (MapRoom.TitleKey) and PlaceName a row
        /// there, its name (Zodi's choice "One name for the arena"), once a quest or a mod's place fights or plays
        /// there.</summary>
        public const int ArenaMap = 116, ArenaUnnamed = 10100, MapName = 8, MapRowBytes = 0x20;
        public const int MapSheet = MapRows.MapSheet, NameSheet = Destinations.NameSheet;
        public const string ArenaName = "Battle Arena";
        public static int ArenaKey => MapRoom.TitleKey(ArenaMap);

        public static bool IsGameScript(int ev)
        {
            foreach (var (first, last) in GameScripts)
                if (ev >= first && ev <= last)
                    return true;
            return false;
        }

        // --- the plan ------------------------------------------------------

        /// <summary>One quest event that will play: its number, its script with its flags' numbers in.</summary>
        public sealed class Planned
        {
            public Quest Quest { get; }
            public QuestEvent Event { get; }
            public int Number { get; }
            public byte[] Script { get; }
            public int Scene { get; set; } = -1;
            public int Text { get; set; } = -1;

            public Planned(Quest quest, QuestEvent ev, int number, byte[] script)
            {
                Quest = quest;
                Event = ev;
                Number = number;
                Script = script;
            }
        }

        /// <summary>A quest's start at a world map place: its steps' rows, without their keys.</summary>
        public sealed class Start
        {
            public Quest Quest { get; }
            public int Place { get; }
            public List<byte[]> Steps { get; }

            public Start(Quest quest, int place, List<byte[]> steps)
            {
                Quest = quest;
                Place = place;
                Steps = steps;
            }
        }

        /// <summary>(1.25.0) A quest's start waiting at a floor of one of its mod's dungeons (Zodi, 2 November: Midlight's
        /// Deep's END plays its boss battle, a scene as it starts and one once it is won, the first time only, its random
        /// battles after; his choices "Boss again until won" and "Yes, it counts"), as planned: its quest, the dungeon's
        /// place's number and the floor's name, the floor's place among the dungeon's floors once the dungeons are
        /// planned (Index, -1 until then or none), its conditions as the world map's steps with its load last (Holds
        /// runs them as the world map would), the event it loads (a battle as itself, a scene its opening), the event's
        /// name, and a battle's won event (-1: a scene's start).</summary>
        public sealed class FloorStart
        {
            public Quest Quest { get; }
            public int Place { get; }
            public string Floor { get; }
            public int Index { get; internal set; } = -1;
            public List<byte[]> Steps { get; }
            public int Event { get; }
            public string Name { get; }
            public int Won { get; }

            public string PlaceName { get; }

            public FloorStart(Quest quest, int place, string placeName, string floor, List<byte[]> steps, int ev,
                              string name, int won)
            {
                Quest = quest;
                Place = place;
                PlaceName = placeName;
                Floor = floor;
                Steps = steps;
                Event = ev;
                Name = name;
                Won = won;
            }

            public string Who => $"{Quest.Name} ({Quest.ModName})";
        }

        /// <summary>(1.25.0) The quests' starts waiting at the mods' dungeons' floors, each at its floor (its Index) once the
        /// dungeons are planned; those whose floor isn't planned are said and left out.</summary>
        public List<FloorStart> FloorStarts { get; } = new List<FloorStart>();
        /// <summary>(1.25.0) Whether a start may wait at a floor (the world map's start of an event found, Places.FloorStarts);
        /// else they are left out, said once.</summary>
        public bool OwnFloorStarts { get; private set; } = true;
        readonly List<FloorStart> _floorStartsWaiting = new List<FloorStart>();

        /// <summary>(1.17.0) One of a mod's battle ground's own random battles as planned: its name, its battle's number
        /// (its own units', numbered as a quest's battles are, or one of the game's), its map's number (one of the
        /// game's, or a quest map's as the maps were numbered), the squad its deploy area was given, and the story's
        /// progress it waits for (-1: none).</summary>
        public sealed class GroundBattle
        {
            public string Name { get; }
            public int Battle { get; }
            public int Map { get; }
            public int Squad { get; }
            public int From { get; }

            public GroundBattle(string name, int battle, int map, int squad, int from)
            {
                Name = name;
                Battle = battle;
                Map = map;
                Squad = squad;
                From = from;
            }
        }

        /// <summary>(1.17.0) A mod's battle ground with random battles of its own, as planned: its place, its number of
        /// the world map's, how many of 100 arrivals start one, its battles.</summary>
        public sealed class GroundPlan
        {
            public MapPlace Place { get; }
            public int Number { get; }
            public int Chance { get; }
            public List<GroundBattle> Battles { get; }

            public GroundPlan(MapPlace place, int number, int chance, List<GroundBattle> battles)
            {
                Place = place;
                Number = number;
                Chance = chance;
                Battles = battles;
            }

            public string Who => $"{Place.Name} ({Place.ModName})";
        }

        /// <summary>(1.15.0) A rumor as planned: its key, its quest, the rumor, its When as the world map's steps (with a
        /// last step where it is told, as a start's load, for Holds), the number of the flag set once it is read, and its
        /// towns' mask (TownBit shifted right by each town's place).</summary>
        public sealed class RumorPlan
        {
            public int Key { get; }
            public Quest Quest { get; }
            public QuestRumor Rumor { get; }
            public List<byte[]> Steps { get; }
            public int Flag { get; }
            public int Mask { get; }
            /// <summary>Whether its key's row of Gossip is another mod's (found there as the table loaded): then the
            /// taverns tell that row as the game's own test says, and reading it sets no flag of the quest's.</summary>
            public bool Taken { get => _taken; set => _taken = value; }
            volatile bool _taken;

            /// <summary>(1.18.0) The mods' own towns (their places' numbers) whose taverns tell it, of those it names.</summary>
            public HashSet<int> ModTowns { get; }

            /// <summary>(1.29.0) Its mark in its key's first save byte while it is unread (RumorTag).</summary>
            public byte Tag { get; }

            public RumorPlan(int key, Quest quest, QuestRumor rumor, List<byte[]> steps, int flag, int mask,
                             HashSet<int>? modTowns = null)
            {
                Key = key;
                Quest = quest;
                Rumor = rumor;
                Steps = steps;
                Flag = flag;
                Mask = mask;
                ModTowns = modTowns ?? new HashSet<int>();
                Tag = RumorTag($"{quest.Key}/{rumor.Name}");
            }

            public string Who => $"{Quest.Name} ({Quest.ModName})";
        }

        /// <summary>What the plan says, a line a quest (its numbers) or a quest left out (why).</summary>
        public List<string> Said { get; } = new List<string>();
        /// <summary>Scripts by event number: the quests' events and their openings.</summary>
        public Dictionary<int, byte[]> Scripts { get; } = new Dictionary<int, byte[]>();
        /// <summary>(1.30.0) Where each event's script names Ramza (its RamzaInScript), by event number: the party's
        /// Ramza's identity written there as it is handed to the game (ScriptFor).</summary>
        public Dictionary<int, int[]> RamzaPlaces { get; } = new Dictionary<int, int[]>();
        /// <summary>(1.31.0) Each quest's reward (QuestReward), by the number of the flag whose setting gives it.</summary>
        public Dictionary<int, RewardPlan> Rewards { get; } = new Dictionary<int, RewardPlan>();
        /// <summary>(1.31.0) The mods' own items' numbers by their keys (Mod.PlanItems), which a reward's own items
        /// name.</summary>
        IReadOnlyDictionary<string, int>? _items;
        /// <summary>(1.53.0) The mods' own jobs' numbers by their keys, of the jobs given to the game this time
        /// (Mod.PlanJobs), which a quest's battle's Jobs name.</summary>
        IReadOnlyDictionary<string, int>? _jobs;
        /// <summary>(1.30.0) Who plays or fights on map 116 (ArenaMap), which the framework then names: each once.</summary>
        public List<string> ArenaUsers { get; } = new List<string>();
        /// <summary>(1.30.0) Whether map 116 is given its name (ArenaName): a quest's event or a mod's place's battle is
        /// set there.</summary>
        public bool NamesArena => ArenaUsers.Count > 0;

        void UsesArena(string who)
        {
            if (!ArenaUsers.Contains(who))
                ArenaUsers.Add(who);
        }
        /// <summary>The setup records to add, in the order they go in the empty slots.</summary>
        public List<byte[]> Records { get; } = new List<byte[]>();
        public List<Start> Starts { get; } = new List<Start>();
        /// <summary>Battle rules by key, whose they are and their chains of steps: an opening's one
        /// (start its scene), a battle's one or two (its start event, its won event).</summary>
        public SortedDictionary<int, (Quest Quest, List<List<byte[]>> Chains)> RuleSets { get; }
            = new SortedDictionary<int, (Quest, List<List<byte[]>>)>();
        public List<Planned> Events { get; } = new List<Planned>();
        /// <summary>Each opening and the scene it starts.</summary>
        public List<(int Opening, int Scene)> Openings { get; } = new List<(int, int)>();
        /// <summary>Each battle event and its deploy prompt's key.</summary>
        public List<(int Battle, int Prompt)> Fights { get; } = new List<(int, int)>();
        /// <summary>Each event that plays in a battle and the battle's first scene's number.</summary>
        public List<(int Scene, int First)> FightScenes { get; } = new List<(int, int)>();
        /// <summary>Each deploy prompt the quests' battles need: its key, its battle's map, whose.</summary>
        public List<(int Key, int Map, string Who)> PromptRowsNeeded { get; } = new List<(int, int, string)>();
        /// <summary>(1.17.0) Each deploy prompt a battle ground's own random battles need (their units their own): its
        /// key, its battle's map, whose. The world map shows a random battle's prompt as Ramza arrives or searches for
        /// enemies, as the game's own (their EntryNo row names it: EntryPrompts); without one, searching starts no
        /// battle.</summary>
        public List<(int Key, int Map, string Who)> GroundPrompts { get; } = new List<(int, int, string)>();
        /// <summary>(1.17.0) The deploy prompt's key each of those battles' EntryNo row names, by its battle's
        /// number.</summary>
        public Dictionary<int, int> EntryPrompts { get; } = new Dictionary<int, int>();
        /// <summary>(1.21.0) The battles of their own units the mods' battle grounds and dungeons fight (PlanBattles), by
        /// their numbers: whose EntryNo rows are whose (RowsWhose).</summary>
        readonly HashSet<int> _groundBattles = new HashSet<int>(), _dungeonBattles = new HashSet<int>();
        /// <summary>(1.12.0) Each battle's objective: its key, its words, whether it protects a unit, whose.</summary>
        public List<(int Key, string Words, bool Protects, string Who)> ObjectiveRows { get; }
            = new List<(int, string, bool, string)>();
        /// <summary>(1.10.0) The quest maps given numbers, each by its number: the game's map it is made from.</summary>
        public Dictionary<int, int> MapBases { get; } = new Dictionary<int, int>();
        /// <summary>The quests' own battles' units by the number given each.</summary>
        public SortedDictionary<int, byte[]> Units { get; } = new SortedDictionary<int, byte[]>();
        /// <summary>(1.33.0, Zodi's choice of 5 November: "As a renamed unit") The quests' battles' units' own names, by
        /// the battle's number and the unit's place in its file (0 to 15).</summary>
        public Dictionary<int, SortedDictionary<int, string>> OwnNames { get; }
            = new Dictionary<int, SortedDictionary<int, string>>();
        /// <summary>(2.0.0) The quests' battles' units' items past 255 (a battle's Items), which the battles' plan puts
        /// on with every mod's units' (BattleFile.Make).</summary>
        public List<BattleFile.QuestItems> WideItems { get; } = new List<BattleFile.QuestItems>();
        /// <summary>(1.33.0) A battle unit's party byte (0xFF: not from the party) and its own text (64 bytes, ended by a
        /// 0), which the game shows in place of a generic's name (0x1E8B7C) and copies to the party's unit as it joins
        /// (0x274EB8: to + 0xDC); the battle file's entry of a unit, 40 bytes (dev/research/sidequests/unit_names.py).
        /// </summary>
        public const int UnitPartyAt = 2, NotFromParty = 0xFF, UnitOwnName = 0x14C, OwnNameSize = 0x40, EntryBytes = 40;

        /// <summary>(1.33.0) Which quest battle's unit a battle file's entry is: its battle's number and its place, found
        /// among the battles' units given the game (each its 16 entries where the helper keeps them); null for an entry
        /// that is none of them.</summary>
        public static (int Battle, int Slot)? EntryOf(IReadOnlyDictionary<int, nint> blocks, nint entry)
        {
            foreach (var (battle, block) in blocks)
            {
                long distance = (long)entry - (long)block;
                if (distance >= 0 && distance < QuestFile.BattleBytes && distance % EntryBytes == 0)
                    return (battle, (int)(distance / EntryBytes));
            }
            return null;
        }

        /// <summary>(1.33.0) A unit's own name written where the game keeps a renamed unit's (UTF-8, the rest 0).</summary>
        public static void WriteOwnName(Span<byte> text, string name)
        {
            text.Clear();
            byte[] utf8 = System.Text.Encoding.UTF8.GetBytes(name);
            utf8.AsSpan(0, Math.Min(utf8.Length, text.Length - 1)).CopyTo(text);
        }

        /// <summary>(1.33.0) What is said, once, of a quest battle's unit given its own name: "Test 69 Quest's Opening
        /// units: unit 1 named Ser Corvin."</summary>
        public static string NamedLine(string battle, int slot, string name) => $"{battle}: unit {slot + 1} named {name}.";

        /// <summary>(1.33.0) A battle unit the game just made (its first + 0x18C bytes) given its own name: when it is
        /// one of a quest battle's units (its entry among `blocks`), not from the party (+ 2 0xFF), and its battle names
        /// it, written where the game keeps a renamed unit's; the battle, the place and the name, or null.</summary>
        public static (int Battle, int Slot, string Name)? NameUnit(Span<byte> unit, nint entry,
                                                                    IReadOnlyDictionary<int, nint> blocks,
                                                                    IReadOnlyDictionary<int, SortedDictionary<int, string>> names)
        {
            if (unit.Length < UnitOwnName + OwnNameSize || unit[UnitPartyAt] != NotFromParty)
                return null;
            var found = EntryOf(blocks, entry);
            if (found == null || !names.TryGetValue(found.Value.Battle, out var named)
                || !named.TryGetValue(found.Value.Slot, out string? name))
                return null;
            WriteOwnName(unit.Slice(UnitOwnName, OwnNameSize), name);
            return (found.Value.Battle, found.Value.Slot, name);
        }
        /// <summary>What each event given is, for the log: "Quest A's intro"; (1.9.0) the flags' apart, as an event's
        /// number may now be a flag's (both from 4096).</summary>
        readonly Dictionary<int, string> _names = new Dictionary<int, string>();
        readonly Dictionary<int, string> _flagNames = new Dictionary<int, string>();
        readonly Dictionary<int, string> _battleNames = new Dictionary<int, string>();

        /// <summary>The quest's name and the name an event number was given, or "".</summary>
        public string NameOf(int number) => _names.TryGetValue(number, out var name) ? name : "";
        /// <summary>(1.9.0) The quest's name and the name a flag was given, or "".</summary>
        public string FlagNameOf(int flag) => _flagNames.TryGetValue(flag, out var name) ? name : "";
        /// <summary>Whether an event number is one of the quests' (a scene, an opening or a battle).</summary>
        public bool IsQuestEvent(int ev) => ev >= 0 && ev <= _lastEvent && _names.ContainsKey(ev);
        /// <summary>(1.9.0) The last event number given: the game's 886, or 8191 with the tables moved.</summary>
        int _lastEvent = LastEvent;
        public int LastNumber => _lastEvent;

        // --- (1.2.1) the story, never moved by a side quest ---------------------

        /// <summary>Each track and value the quests' scripts set the game's progress to (their
        /// instructions E9, found by their bytes).</summary>
        readonly HashSet<(int Track, int Value)> _progressSets = new HashSet<(int, int)>();

        /// <summary>The track and value of each instruction E9 in a script, found by its bytes (the
        /// opcode and two 32-bit numbers); a byte E9 inside another instruction adds a pair too,
        /// which matters only should the game's own code set that very pair while a quest's
        /// event plays.</summary>
        public static void ProgressSetsIn(byte[] script, ISet<(int, int)> into)
        {
            for (int at = 0; at + 9 <= script.Length; at++)
                if (script[at] == ProgressInstruction)
                    into.Add((BinaryPrimitives.ReadInt32LittleEndian(script.AsSpan(at + 1, 4)),
                              BinaryPrimitives.ReadInt32LittleEndian(script.AsSpan(at + 5, 4))));
        }

        /// <summary>What is said when the game's progress would be set to what one of the quests'
        /// scripts sets it to (its instruction E9) while `current`, the event playing, is one of
        /// the quests': the set is left out. Null otherwise: the game's own (a story scene's E9,
        /// or the game's other caller, its interface raising a track to a table's value), which
        /// sets it.</summary>
        public string? ProgressKept(int current, int track, int value)
            => IsQuestEvent(current) && _progressSets.Contains((track, value))
                ? $"{NameOf(current)} would set the game's progress {track} to {value}: left as it was, as a side "
                  + "quest never moves the story."
                : null;

        /// <summary>What is said when a variable command would change the story's progress
        /// (variable 110) while `current`, the event playing, is one of the quests': the command
        /// is left out. Null when it isn't, or the command's variable isn't 110 (one that only
        /// reads it, into another variable, is the game's).</summary>
        public string? VariableKept(int current, int variable)
            => variable == StoryProgress && IsQuestEvent(current)
                ? $"{NameOf(current)} would change variable {StoryProgress}, the story's progress: left as it was, "
                  + "as a side quest never moves the story."
                : null;

        /// <summary>(1.2.2) What is said when the world map would stop a travel from where `pending`,
        /// the event it found waiting there, is one of the quests' (the game lets you go back
        /// only the way you came, "You cannot travel to the selected location at this time..."):
        /// the travel goes on, and the event waits for you to come back. Null when it isn't one of
        /// theirs (the game's own events stop it, as they do).</summary>
        public string? TravelFreed(int pending)
            => IsQuestEvent(pending)
                ? $"{NameOf(pending)} waits here: travel on isn't stopped for it, as a side quest never blocks "
                  + "the way."
                : null;

        /// <summary>(1.2.4) Whether a travel passes through the place whose chains the world map
        /// runs, from the travel's state as the travel step leaves it when it runs them: a travel
        /// under way (its flags' bit 0) with roads still to go (fewer taken, counting the one that
        /// came here, than it has). At its last stop the roads taken are all it has: arrived.</summary>
        public static bool Passing(int flags, int taken, int roads) => (flags & 1) != 0 && taken < roads;

        /// <summary>(1.2.4) A command of the world map's variable function where the passing-through
        /// variable is its variable or its operand: none when it is the command's variable (it is
        /// only read), the same command with its value when it is read into a game variable (odd
        /// commands read a second variable), else as it was.</summary>
        public static (int Op, int Dest, int Src)? PassingCommand(int op, int dest, int src, bool passing)
        {
            if (dest == PassingThrough)
                return null;
            bool reads = op != 0xBE && (op & 1) == 1;
            if (reads && src == PassingThrough)
                return (op - 1, dest, passing ? 1 : 0);
            return (op, dest, src);
        }

        // --- (1.2.5) the quests' markers ------------------------------------------

        /// <summary>(1.2.5) A variable as the world map reads it (0x2E9898): its value, but variable 34,
        /// which it makes from variables 35 and 36 as it reads it (36's bit 0 at bit 15, 35's bits 0 to
        /// 2 at bit 12); a quest flag is its bit.</summary>
        public static int WorldValue(ReadOnlySpan<byte> bank, int variable)
            => variable == 34 ? ((ReadGame(bank, 36) & 1) << 15) + ((ReadGame(bank, 35) & 7) << 12)
                : IsFlag(variable) ? ReadFlag(bank, variable) : ReadGame(bank, variable);

        /// <summary>(1.2.5) The party's units as the world map's test of a character reads them
        /// (instruction 4, 0x344134): 54 units of 0x258 bytes.</summary>
        public const int PartyUnits = 54, UnitBytes = 0x258;

        /// <summary>(1.2.5) Whether a character is in the party, as the world map's test of one finds:
        /// a unit (its second byte not 0xFF) that is the character (its first byte); else one that
        /// carries it (the low byte of its four bytes at 0x230, their second byte 0, its byte at
        /// 0x11E 0), unless `strict` (the number at the script reader's pointer + 8 isn't 0, or no
        /// pointer) and its third byte is 0x82.</summary>
        public static bool HasCharacter(ReadOnlySpan<byte> units, int character, bool strict)
        {
            bool carried = false;
            for (int n = 0; n < PartyUnits; n++)
            {
                var unit = units.Slice(n * UnitBytes, UnitBytes);
                if (unit[1] == 0xFF)
                    continue;
                if (unit[0] == character)
                    return true;
                uint held = BinaryPrimitives.ReadUInt32LittleEndian(unit.Slice(0x230, 4));
                if ((held & 0xFF) == character && (held & 0xFF00) == 0 && unit[0x11E] == 0 && (!strict || unit[2] != 0x82))
                    carried = true;
            }
            return carried;
        }

        /// <summary>A start's or (1.15.0) a rumor's conditions as the world map's steps (EnhancedWorldEvent's rows): a
        /// character in the party, a variable or a quest flag (its number) being a value, at least or at most one.</summary>
        static List<byte[]> ConditionSteps(List<Condition> when, Dictionary<string, int> flags)
        {
            var steps = new List<byte[]>();
            foreach (var c in when)
            {
                if (c.Kind == "Character")
                    steps.Add(WorldRow(InParty, 0, new[] { (short)c.Value }));
                else
                {
                    int variable = c.Kind == "Flag" ? flags[c.Flag] : c.Variable;
                    short value = unchecked((short)c.Value);
                    steps.Add(c.Test == "Is"
                        ? WorldRow(Equal, variable, new[] { value })
                        : WorldRow(c.Test == "AtLeast" ? AtLeast : AtMost, 0, new[] { (short)variable, value }));
                }
            }
            return steps;
        }

        /// <summary>(1.15.0) The rumor planned at `key`, or null.</summary>
        public RumorPlan? RumorAt(int key)
        {
            foreach (var r in RumorPlans)
                if (r.Key == key && !r.Taken)
                    return r;
            return null;
        }

        /// <summary>(1.15.0) The taverns' test of a rumor told (0x36F53C, its key and a place) for one of the quests'
        /// rumors, as the game's own tests one of its own: a place given (0 or more), the place's bit in its mask (the
        /// shift counted as the program's `shr eax, cl` counts it, by the place's last five bits), then its When as the
        /// world map tests it (where the game's reads its variable 0x2D1 plus the key: those of keys past 28 are the
        /// game's other bits, so a quest's rumor keeps none). Null for a key no quest's rumor has (the game's test
        /// then).</summary>
        public static bool? RumorTold(RumorPlan? rumor, int place, Func<int, int> value, Func<int, bool> inParty)
        {
            if (rumor == null)
                return null;
            if (place >= Destinations.FirstNumber)
            {
                // (1.18.0) A mod's town's tavern: a rumor naming it, or one told in every tavern.
                if (!rumor.Rumor.EveryTavern && !rumor.ModTowns.Contains(place))
                    return false;
            }
            else if (place >= 0 && (rumor.Mask & (TownBit >> place)) == 0)
                return false;
            return Holds(rumor.Steps, value, inParty);
        }

        /// <summary>(1.29.0) A rumor's mark in its key's first save byte while unread: 2 to 255 from its name (FNV-1a;
        /// 1 is a new game's, no rumor's), so a key given another rumor at another start is told apart in a save. The
        /// game reads the byte only as 0 or not (the tavern's new mark `0x19E35C`, the news, the world map's towns) and
        /// writes only 0 (read) and a new game's 1.</summary>
        public static byte RumorTag(string name)
        {
            uint hash = 2166136261;
            foreach (char c in name)
            {
                hash ^= c;
                hash *= 16777619;
            }
            return (byte)(2 + hash % 254);
        }

        /// <summary>(1.29.0, Zodi's sixth of 3 November) Each planned rumor's two save bytes (`bytes`, two a key: its
        /// first 0 once read, its second its news still to come) made its own, its keys being given as the game starts:
        /// its mark there, it is its own and unread; 0 with its flag set, its own and read; anything else (a save made
        /// when another rumor had the key, a new game's 1, another rumor's read 0) settled from its flag: read (0, 0)
        /// when set, else its mark and its news to come (its mark, 1). A rumor read sets its flag as the tavern's agent
        /// marks it (RumorReadNow), so a 0 without the flag is never its own. Returns how many keys were settled.</summary>
        public int SettleRumors(ReadOnlySpan<byte> bank, Span<byte> bytes)
        {
            int settled = 0;
            foreach (var r in RumorPlans)
            {
                if (r.Taken || 2 * r.Key + 1 >= bytes.Length)
                    continue;
                bool read = ReadFlag(bank, r.Flag) != 0;
                byte first = bytes[2 * r.Key];
                if (first == r.Tag && !read || first == 0 && read)
                    continue;
                bytes[2 * r.Key] = read ? (byte)0 : r.Tag;
                bytes[2 * r.Key + 1] = read ? (byte)0 : (byte)1;
                settled++;
            }
            return settled;
        }

        /// <summary>(1.29.0) The tavern's agent marking `key` read (`0x19D548`, action 0): the quest's rumor of that key, its
        /// flag set and what to say of it; null for a key no quest's rumor has, or one already read.</summary>
        public string? RumorReadNow(Span<byte> bank, int key)
        {
            var rumor = RumorAt(key);
            if (rumor == null || rumor.Taken || ReadFlag(bank, rumor.Flag) != 0)
                return null;
            WriteFlag(bank, rumor.Flag, 1);
            return $"{FlagNameOf(rumor.Flag)} is 1 (flag {rumor.Flag}): its rumor {rumor.Rumor.Name} was read.";
        }


        /// <summary>(1.2.5) Whether a start's steps reach its load as the world map runs them (0x343AF8:
        /// a row's words, then its tests 1 to 4, the first that fails stopping the chain), but for the
        /// passing-through variable, which a marker doesn't wait for: where a quest's marker shows.
        /// `value` is a variable as the world map reads it; `inParty` its test of a character.</summary>
        public static bool Holds(List<byte[]> steps, Func<int, int> value, Func<int, bool> inParty)
        {
            foreach (var row in steps)
            {
                short kind = BinaryPrimitives.ReadInt16LittleEndian(row.AsSpan(4, 2));
                int count = BinaryPrimitives.ReadInt32LittleEndian(row.AsSpan(0x0C, 4));
                int first = count > 0 ? BinaryPrimitives.ReadUInt16LittleEndian(row.AsSpan(0x20, 2)) : 0;
                int second = count > 1 ? BinaryPrimitives.ReadUInt16LittleEndian(row.AsSpan(0x22, 2)) : 0;
                switch (kind)
                {
                    case Equal:
                        int variable = BinaryPrimitives.ReadInt32LittleEndian(row.AsSpan(0x10, 4)) & 0xFFFF;
                        if (variable != PassingThrough && value(variable) != first)
                            return false;
                        break;
                    case AtLeast:
                        if (value(first) < second)
                            return false;
                        break;
                    case AtMost:
                        if (value(first) > second)
                            return false;
                        break;
                    case InParty:
                        if (!inParty(first))
                            return false;
                        break;
                    case LoadEvent:
                        return true;
                    default:
                        return false;
                }
            }
            return false;
        }

        /// <summary>(1.2.5) The marker's color at a world map place (bytes R, G, B, A, as the game's
        /// nodes hold one), or null: the first quest with a Marker, in the plan's order, one of whose
        /// starts there holds.</summary>
        public uint? MarkerAt(int place, Func<int, int> value, Func<int, bool> inParty)
            => MarkedAt(place, value, inParty) is Quest quest ? QuestFile.Rgba(quest.Marker) : (uint?)null;

        /// <summary>(1.2.5) The quest whose marker a world map place shows, or null (MarkerAt's).</summary>
        public Quest? MarkedAt(int place, Func<int, int> value, Func<int, bool> inParty)
        {
            foreach (var start in Starts)
                if (start.Place == place && start.Quest.Marker.Length > 0 && Holds(start.Steps, value, inParty))
                    return start.Quest;
            // (1.25.0) A start waiting at one of the place's floors, the dungeon being the place.
            foreach (var first in FloorStarts)
                if (first.Place == place && first.Quest.Marker.Length > 0 && Holds(first.Steps, value, inParty))
                    return first.Quest;
            return null;
        }

        /// <summary>(1.2.5) Whether any quest planned has a Marker.</summary>
        public bool HasMarkers => Starts.Exists(s => s.Quest.Marker.Length > 0)
                                  || FloorStarts.Exists(f => f.Quest.Marker.Length > 0);

        /// <summary>The quest's name and the name a battle number was given, or "".</summary>
        public string BattleNameOf(int number) => _battleNames.TryGetValue(number, out var name) ? name : "";
        /// <summary>Every flag given, by its quest's key and its name.</summary>
        public Dictionary<string, int> Flags { get; } = new Dictionary<string, int>(StringComparer.Ordinal);
        /// <summary>(1.13.0) The numbers' ID, which a save is marked with as a quest flag is set (Mark); (1.32.0) the
        /// new mark's when the plan gave flags no name had (Numbers.Stamp).</summary>
        public uint NumbersId { get; private set; }
        /// <summary>(1.14.0) The quests' own deploy areas' squads, each its number and 12 bytes (DeploySquads.Arm);
        /// whether they may be given (the program's squads and their pointers found), else each battle keeps its
        /// setup's.</summary>
        public List<(int Number, byte[] Bytes)> Squads { get; } = new List<(int Number, byte[] Bytes)>();
        /// <summary>(1.21.0) One of a mod's dungeon's floors as planned (Zodi's list, his seventh): its name and
        /// description, the quest flag it waits for (its number, -1 listed from the start), its battles (planned as a
        /// battle ground's random battles are), and its place in its dungeon's list of floors (its entry FloorEntry plus
        /// it, the variable FloorVariable it once chosen). (1.24.0) A floor listed once the floor before it is won
        /// waits for that floor's won flag (After, its name); a floor a floor waits for so has its WonFlag (-1 none),
        /// set once one of its battles is won (Hooks.FloorWon), and WonLists, the floor that lists.</summary>
        public sealed class DungeonFloor
        {
            public string Name { get; }
            public string Description { get; }
            public int Flag { get; }
            public List<GroundBattle> Battles { get; }
            public int Index { get; }
            public string After { get; }
            public int WonFlag { get; internal set; } = -1;
            public string WonLists { get; internal set; } = "";
            /// <summary>(1.25.0) The quests' starts waiting at it, in the quests' order: as the floor is chosen, the
            /// first whose conditions hold plays in place of its battle.</summary>
            public List<FloorStart> Firsts { get; } = new List<FloorStart>();

            public DungeonFloor(string name, string description, int flag, List<GroundBattle> battles, int index,
                                string after = "")
            {
                Name = name;
                Description = description;
                Flag = flag;
                Battles = battles;
                Index = index;
                After = after;
            }
        }

        /// <summary>(1.21.0) A mod's dungeon as planned: its place, its number of the world map's, its floors (those
        /// that can be fought, in its list's order).</summary>
        public sealed class DungeonPlan
        {
            public MapPlace Place { get; }
            public int Number { get; }
            public List<DungeonFloor> Floors { get; }

            public DungeonPlan(MapPlace place, int number, List<DungeonFloor> floors)
            {
                Place = place;
                Number = number;
                Floors = floors;
            }

            public string Who => $"{Place.Name} ({Place.ModName})";
        }

        /// <summary>(1.21.0) A floor's entry in a settlement menu (Midlight's Deep's: 0xB800 a settlement's entry and
        /// 0xED on its floors, 0x3449B0), and the variable the game sets to the entry chosen less 0xB8ED (92, 0x3459A3:
        /// the floor chosen).</summary>
        public const int FloorEntry = 0xB8ED, FloorVariable = 92;

        public bool OwnSquads { get; private set; } = true;
        /// <summary>(1.15.0) The quests' rumors, and whether they may be told (the taverns' test of a rumor told and
        /// the read bytes found), else none is.</summary>
        public List<RumorPlan> RumorPlans { get; } = new List<RumorPlan>();
        public bool OwnRumors { get; private set; } = true;
        /// <summary>(1.17.0) The mods' battle grounds with random battles of their own, each by its place's number.</summary>
        public SortedDictionary<int, GroundPlan> Grounds { get; } = new SortedDictionary<int, GroundPlan>();
        /// <summary>(1.18.0) The mods' towns with a menu of their own (Enter Settlement), each by its place's number.</summary>
        public SortedDictionary<int, MenuTown> MenuTowns { get; } = new SortedDictionary<int, MenuTown>();
        /// <summary>(1.21.0) The mods' dungeons, each by its place's number.</summary>
        public SortedDictionary<int, DungeonPlan> Dungeons { get; } = new SortedDictionary<int, DungeonPlan>();

        /// <summary>(1.18.0) A mod's town with a menu of its own: its place (its Menu) and the number it was given.</summary>
        public sealed class MenuTown
        {
            public MapPlace Place { get; }
            public int Number { get; }
            public TownMenu Menu => Place.Menu!;
            public string Who => $"{Place.Name} ({Place.ModName})";
            /// <summary>(1.26.0) Its Outfitter's own items' numbers (its mod's items it names, as numbered), in its
            /// Shop's order.</summary>
            public List<int> OwnItems { get; } = new List<int>();

            public MenuTown(MapPlace place, int number)
            {
                Place = place;
                Number = number;
            }
        }

        /// <summary>(1.20.0) The mods' towns darkened once a quest's flag is set, each with the flag's number, in the
        /// places' order.</summary>
        public List<DarkPlace> DarkPlaces { get; } = new List<DarkPlace>();

        /// <summary>(1.20.0) A mod's town darkened once its quest's flag is set (its place's Darkened): its place and
        /// the flag's number.</summary>
        public sealed class DarkPlace
        {
            public MapPlace Place { get; }
            public int Flag { get; }
            public string Who => $"{Place.Name} ({Place.ModName})";

            public DarkPlace(MapPlace place, int flag)
            {
                Place = place;
                Flag = flag;
            }
        }

        /// <summary>(1.20.0) What a town darkened once a quest's flag is set says as it is planned: the quest's flag
        /// its Darkened names (of its own mod's quests planned), or why it isn't darkened.</summary>
        public static string DarkLine(MapPlace place, int flag)
            => flag >= 0
                ? $"{place.Name} ({place.ModName}) is darkened once {place.Darkened!.Quest}'s {place.Darkened.Flag} is "
                  + $"set (flag {flag})."
                : $"{place.Name} ({place.ModName}) isn't darkened: its mod has no side quest {place.Darkened!.Quest} "
                  + $"added with a flag {place.Darkened.Flag}.";

        /// <summary>(1.18.0) A place the taverns' test is asked with when a mod's town's tavern asks of one of the
        /// game's own rumors: one with no town's bit in any rumor's mask (0x4000 shifted right by 15), so only those
        /// told in every tavern are told there, as the game tells them at any tavern.</summary>
        public const int NoTownPlace = 15;
        /// <summary>(1.18.0) The shops' masks (0x67F890: two bytes an item, its first shifted 8 left plus its second; a
        /// town t's bit 0x8000 shifted right by t, as the Outfitter's stock tests it, 0x288E54): 256 items; the town
        /// whose bit a mod's town borrows as its Outfitter's stock is built (14, the second byte's 2), each item's bit
        /// as the town's items say for the call, then every byte as it was.</summary>
        public const int ShopItems = 256, BorrowedTown = 14, BorrowedBit = 0x8000 >> BorrowedTown;

        /// <summary>(1.18.0) The shops' masks given a mod's town's items under the borrowed town's bit: each item's
        /// second byte kept in `kept`, then its borrowed bit cleared, then set for the town's items (1 to 255).</summary>
        public static void BorrowMasks(Span<byte> masks, IEnumerable<int> items, Span<byte> kept)
        {
            for (int n = 0; n < ShopItems; n++)
            {
                kept[n] = masks[2 * n + 1];
                masks[2 * n + 1] = (byte)(masks[2 * n + 1] & ~BorrowedBit);
            }
            foreach (int item in items)
                if (item > 0 && item < ShopItems)
                    masks[2 * item + 1] |= (byte)BorrowedBit;
        }

        /// <summary>(1.18.0) The shops' masks as they were before BorrowMasks.</summary>
        public static void GiveBackMasks(Span<byte> masks, ReadOnlySpan<byte> kept)
        {
            for (int n = 0; n < ShopItems; n++)
                masks[2 * n + 1] = kept[n];
        }

        /// <summary>Plans the quests: numbers for their names, records, scripts and rows. `records`
        /// is the events the game's setup table has records for; `freeSlots` how many slots the
        /// game searches after its last record; `otherScripts` the event numbers other mods ship
        /// scripts for.</summary>
        public static Framework Plan(IReadOnlyCollection<int> records, int freeSlots, ISet<int> otherScripts,
                                     IList<Quest> quests, Numbers numbers,
                                     IReadOnlyDictionary<string, int>? places = null, int lastEvent = LastEvent,
                                     IReadOnlyDictionary<string, int>? maps = null,
                                     IReadOnlyDictionary<int, int>? mapBases = null, bool ownSquads = true,
                                     bool ownRumors = true, IList<(MapPlace Place, int Number)>? grounds = null,
                                     bool ownUnits = true, IList<(MapPlace Place, int Number)>? menuTowns = null,
                                     IList<MapPlace>? darkPlaces = null,
                                     IList<(MapPlace Place, int Number)>? dungeons = null, bool floorStarts = true,
                                     IReadOnlyDictionary<string, int>? items = null,
                                     IReadOnlyDictionary<string, int>? jobs = null)
        {
            var plan = new Framework
            {
                _lastEvent = lastEvent, NumbersId = numbers.Id, OwnSquads = ownSquads, OwnRumors = ownRumors,
                OwnFloorStarts = floorStarts, _items = items, _jobs = jobs,
            };
            if (mapBases != null)
                foreach (var (number, made) in mapBases)
                    plan.MapBases[number] = made;
            var candidates = new List<int>();
            for (int ev = 1; ev <= lastEvent; ev++)
                candidates.Add(ev);
            var recordSet = new HashSet<int>(records);
            bool Free(int ev) => ev >= 1 && ev <= lastEvent && !recordSet.Contains(ev) && !IsGameScript(ev)
                                 && !otherScripts.Contains(ev);
            int slotsLeft = freeSlots;
            // (1.22.0) Two mods' quests, or battle grounds and dungeons, of one name: named with their mods' names.
            var questNames = new List<string>();
            foreach (var quest in quests)
                questNames.Add(quest.Name);
            plan._sharedQuests = SharedNames(questNames);
            var placeNames = new List<string>();
            foreach (var (place, _) in grounds ?? Array.Empty<(MapPlace, int)>())
                placeNames.Add(place.Name);
            foreach (var (place, _) in dungeons ?? Array.Empty<(MapPlace, int)>())
                placeNames.Add(place.Name);
            plan._sharedPlaces = SharedNames(placeNames);
            // (1.18.0) The mods' towns with a menu of their own, before the quests: a quest's rumor may name one.
            foreach (var (place, number) in menuTowns ?? Array.Empty<(MapPlace, int)>())
                if (place.Town && place.Menu != null)
                {
                    var town = new MenuTown(place, number);
                    // (1.26.0) Its own items, as numbered (an item of its mod's not added: said, not sold).
                    foreach (var name in place.Menu.OwnItems)
                    {
                        if (items != null && items.TryGetValue($"{place.ModId}/{name}", out int item))
                            town.OwnItems.Add(item);
                        else
                            plan.Said.Add($"{town.Who}'s Outfitter doesn't sell {name}: its mod has no item {name} "
                                          + "added.");
                    }
                    plan.MenuTowns[number] = town;
                }
            // (1.29.0, Zodi's sixth of 3 November) The rumors numbered afresh as the game starts: each enabled quest's
            // rumor keeps the key it had while no other enabled rumor has it; a rumor no longer enabled frees its key.
            var rumorNames = new List<string>();
            if (ownRumors)
                foreach (var quest in quests)
                    foreach (var rumor in quest.Rumors)
                        rumorNames.Add($"{quest.Key}/{rumor.Name}");
            numbers.BeginNow(RumorsKind, rumorNames);
            foreach (var quest in quests)
                plan.PlanQuest(quest, numbers, candidates, Free, ref slotsLeft, places, maps);
            numbers.SettleNow(RumorsKind);
            // (1.17.0) The mods' battle grounds' own random battles, after the quests (their numbers kept apart).
            foreach (var (place, number) in grounds ?? Array.Empty<(MapPlace, int)>())
                plan.PlanGround(place, number, numbers, maps, ownUnits);
            foreach (var town in plan.MenuTowns.Values)
                plan.Said.Add(plan.MenuLine(town));
            // (1.21.0) The mods' dungeons, after the quests (a floor may wait for one of their flags).
            foreach (var (place, number) in dungeons ?? Array.Empty<(MapPlace, int)>())
                plan.PlanDungeon(place, number, numbers, maps, ownUnits);
            // (1.25.0) A quest's start waiting at a floor no dungeon planned lists: said, left out.
            foreach (var first in plan._floorStartsWaiting)
                if (first.Index < 0)
                    plan.Said.Add($"{first.Who}'s start at {first.PlaceName}'s floor {first.Floor} is left out: "
                                  + $"{first.PlaceName} has no floor {first.Floor} listed.");
            // (1.20.0) The mods' towns darkened once a quest's flag is set: the flag's number, its quest planned.
            foreach (var place in darkPlaces ?? Array.Empty<MapPlace>())
            {
                if (!place.Town || place.Darkened == null)
                    continue;
                int flag = plan.Flags.TryGetValue($"{place.ModId}/{place.Darkened.Quest}/{place.Darkened.Flag}",
                                                  out int n) ? n : -1;
                if (flag >= 0)
                    plan.DarkPlaces.Add(new DarkPlace(place, flag));
                plan.Said.Add(DarkLine(place, flag));
            }
            // (1.32.0) Flags no name had given: the numbers' new mark, which a save is marked with from now on (a save
            // marked before has those flags cleared as it loads, Loaded).
            numbers.Stamp();
            plan.NumbersId = numbers.Id;
            return plan;
        }

        /// <summary>(1.18.0) What a mod's town's menu holds, said once: its Outfitter's items, its tavern's side quest
        /// rumors (those naming it, and those told in every tavern), the Warriors' Guild, its Poachers' Den; (1.19.0)
        /// its own art, if it has it.</summary>
        public string MenuLine(MenuTown town)
        {
            int items = town.Menu.Shop.Count;
            int rumors = 0;
            foreach (var r in RumorPlans)
                if (!r.Taken && (r.Rumor.EveryTavern || r.ModTowns.Contains(town.Number)))
                    rumors++;
            // (1.26.0) And its own items, after the game's.
            int own = town.OwnItems.Count;
            string selling = own == 0 ? $"{items} item{(items == 1 ? "" : "s")}"
                             : $"{items} of the game's item{(items == 1 ? "" : "s")} and {own} of its "
                               + $"mod's own";
            return $"{town.Who} has a menu of its own (Enter Settlement): an Outfitter selling {selling}"
                   + $", a tavern telling {rumors} side quest "
                   + $"rumor{(rumors == 1 ? "" : "s")}, the Warriors' Guild"
                   + (town.Menu.Poachers ? " and a Poachers' Den" : "")
                   // (1.19.0) Its own art, if it has it.
                   + (town.Menu.ArtPicture.Length > 0 ? "; its art is its own." : ".");
        }

        /// <summary>(1.17.0) What Numbers.json keeps a battle ground's random battle by (its battle's number, and its
        /// deploy area's squad with "#1"): its mod, "place:" and its place's name (no quest's folder holds a colon),
        /// and its name.</summary>
        public static string GroundKey(MapPlace place, string battle) => $"{place.ModId}/place:{place.Name}/{battle}";

        /// <summary>(1.22.0) A mod's name in the log: its ModName, or its id when it has none; with its id beside it
        /// when another mod loaded (`loaded`, each its id and name) has the same name, so two modders' mods of one
        /// name are told apart (Zodi's ninth).</summary>
        public static string LogName(string id, string name, IEnumerable<(string Id, string Name)> loaded)
        {
            string own = string.IsNullOrWhiteSpace(name) ? id : name;
            foreach (var (otherId, otherName) in loaded)
            {
                string other = string.IsNullOrWhiteSpace(otherName) ? otherId : otherName;
                if (!string.Equals(otherId, id, StringComparison.OrdinalIgnoreCase)
                    && string.Equals(other, own, StringComparison.OrdinalIgnoreCase))
                    return $"{own}, {id}";
            }
            return own;
        }

        /// <summary>(1.22.0) The names given more than once, whatever their case: two mods' quests, or places, of one
        /// name.</summary>
        static HashSet<string> SharedNames(IEnumerable<string> names)
        {
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var shared = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (string name in names)
                if (!seen.Add(name))
                    shared.Add(name);
            return shared;
        }

        /// <summary>(1.22.0) The quests' and the places' names two mods give alike: their events, flags and battles
        /// are named in the log with their mod's name too ("Thieves at Gariland (Test 51 First)'s Ambush"), else by
        /// the quest's or place's name alone, as before.</summary>
        HashSet<string> _sharedQuests = new HashSet<string>(StringComparer.OrdinalIgnoreCase),
                        _sharedPlaces = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        // --- (1.31.0) a quest's reward ---------------------------------------------

        /// <summary>(1.31.0, Zodi's ask of 3 November: "A reward as a quest ends"; his choice "Its last step only") A
        /// quest's reward as planned: whose (the quest's event giving it), the flag giving it, its gil, and its items by
        /// their numbers (the game's as they are, the mod's own as Mod.PlanItems numbered them), each with its count and
        /// what the log names it.</summary>
        public sealed class RewardPlan
        {
            public string Who { get; }
            public string Flag { get; }
            public int Gil { get; }
            public List<(int Number, int Count, string Named)> Items { get; }

            public RewardPlan(string who, string flag, int gil, List<(int, int, string)> items)
            {
                Who = who;
                Flag = flag;
                Gil = gil;
                Items = items;
            }
        }

        /// <summary>(1.31.0) An event's reward planned under its flag's number: a mod's own item its mod hasn't added
        /// left out, said.</summary>
        void PlanReward(Quest quest, QuestEvent ev, int flag)
        {
            var reward = ev.Reward!;
            string who = $"{QuestNamed(quest)}'s {ev.Name}";
            var items = new List<(int, int, string)>();
            foreach (var (item, own, count) in reward.Items)
            {
                if (own.Length == 0)
                    items.Add((item, count, $"item {item}"));
                else if (_items != null && _items.TryGetValue($"{quest.ModId}/{own}", out int number))
                    items.Add((number, count, own));
                else
                    Said.Add($"{who}'s reward leaves out {own}: its mod has no item {own} added.");
            }
            if (reward.Gil > 0 || items.Count > 0)
                Rewards[flag] = new RewardPlan(who, reward.Flag, reward.Gil, items);
        }

        /// <summary>(1.31.0) The reward a flag gives as it goes from `was` to `now`: only from 0 to 1 (a flag isn't set
        /// while a scene is replayed, Command), else null.</summary>
        public RewardPlan? RewardGiven(int flag, int was, int now)
            => was == 0 && now == 1 && Rewards.TryGetValue(flag, out var reward) ? reward : null;

        /// <summary>(1.31.0) What a reward gives, in words: "1,000 gil, item 240 (3 of them) and Moon Sword".</summary>
        public static string RewardWords(RewardPlan reward)
        {
            var parts = new List<string>();
            if (reward.Gil > 0)
                parts.Add($"{reward.Gil.ToString("N0", System.Globalization.CultureInfo.InvariantCulture)} gil");
            foreach (var (_, count, named) in reward.Items)
                parts.Add(count == 1 ? named : $"{named} ({count} of them)");
            return parts.Count == 1 ? parts[0] : $"{string.Join(", ", parts.GetRange(0, parts.Count - 1))} and {parts[^1]}";
        }

        string QuestNamed(Quest quest) => _sharedQuests.Contains(quest.Name) ? $"{quest.Name} ({quest.ModName})"
                                                                             : quest.Name;

        string PlaceNamed(MapPlace place) => _sharedPlaces.Contains(place.Name) ? $"{place.Name} ({place.ModName})"
                                                                                : place.Name;

        /// <summary>(1.17.0) A mod's battle ground's own random battles (its place given number `number`): each its
        /// battle's number (its own units numbered as a quest's battles are, kept as "Battles"; one of the game's as it
        /// is), its map's (a quest map's as the maps were numbered, else the game's), its deploy area given a squad
        /// past the game's 768 (kept as "Squads"); one that can't be fought is said and left out, the others are.
        /// `ownUnits`: whether the battles' units' place was found (a battle of its own units needs it).</summary>
        void PlanGround(MapPlace place, int number, Numbers numbers, IReadOnlyDictionary<string, int>? maps,
                        bool ownUnits)
        {
            string who = $"{place.Name} ({place.ModName})";
            if (place.Battles.Count == 0)
                return;
            var parts = new List<string>();
            var battles = PlanBattles(place, who, place.Battles, numbers, maps, ownUnits, parts, true);
            if (battles.Count == 0)
                return;
            Grounds[number] = new GroundPlan(place, number, place.Chance, battles);
            Said.Add($"{who}'s random battles start on {place.Chance} of 100 arrivals: {string.Join("; ", parts)}.");
        }

        /// <summary>(1.17.0, 1.21.0 a dungeon's floors' too) A place's random battles planned: each its battle's number,
        /// its map's, its deploy area's squad and, `prompted` (a battle ground's), its deploy prompt (PlanGround); one
        /// that can't be fought said and left out. What each is goes in `parts`. A dungeon's floor starts its battle at
        /// once, as Midlight's Deep's do: no prompt, its EntryNo row's 0, as the Deep's battles' rows have.</summary>
        List<GroundBattle> PlanBattles(MapPlace place, string who, IEnumerable<PlaceBattle> list, Numbers numbers,
                                       IReadOnlyDictionary<string, int>? maps, bool ownUnits, List<string> parts,
                                       bool prompted)
        {
            var battles = new List<GroundBattle>();
            foreach (var battle in list)
            {
                string key = GroundKey(place, battle.Name);
                int map = battle.Map;
                if (battle.MapName.Length > 0
                    && (maps == null || !maps.TryGetValue($"{place.ModId}/{battle.MapName}", out map)))
                {
                    Said.Add($"{who}'s random battle {battle.Name} isn't fought: its quest map {battle.MapName} isn't "
                             + "in the game this time.");
                    continue;
                }
                if (!OwnSquads)
                {
                    Said.Add($"{who}'s random battle {battle.Name} isn't fought: its deploy area can't be given.");
                    continue;
                }
                if (battle.Units != null && !ownUnits)
                {
                    Said.Add($"{who}'s random battle {battle.Name} isn't fought: its own units can't be given.");
                    continue;
                }
                int fought = battle.Units != null
                    ? numbers.Give("Battles", key, Range(FirstBattle, LastBattle), _ => true, out _)
                    : battle.GameUnits;
                if (fought < 0)
                {
                    Said.Add($"{who}'s random battle {battle.Name} isn't fought: no battle number is left for it.");
                    continue;
                }
                int squad = numbers.Give("Squads", key + "#1", Range(DeploySquads.FirstOwn, DeploySquads.LastOwn),
                                         _ => true, out _);
                if (squad < 0)
                {
                    Said.Add($"{who}'s random battle {battle.Name} isn't fought: no deploy area number is left for it.");
                    continue;
                }
                // Its deploy prompt, as the game's random battles' (one of the game's battles keeps its own); (1.21.0)
                // none for a dungeon's floor's.
                int prompt = battle.Units != null && prompted
                    ? numbers.Give("Prompts", key, Range(FirstPrompt, int.MaxValue - 1), _ => true, out _)
                    : 0;
                if (prompt < 0)
                {
                    Said.Add($"{who}'s random battle {battle.Name} isn't fought: no deploy prompt key is left for it.");
                    continue;
                }
                Squads.Add((squad, battle.Deploy[0].Squad(squad, map)));
                if (battle.Units != null)
                {
                    Units[fought] = (byte[])battle.Units.Clone();
                    _battleNames[fought] = $"{PlaceNamed(place)}'s {battle.Name}";
                    (prompted ? _groundBattles : _dungeonBattles).Add(fought);
                    if (prompt > 0)
                    {
                        EntryPrompts[fought] = prompt;
                        GroundPrompts.Add((prompt, map, $"{who}'s random battle {battle.Name}"));
                    }
                }
                battles.Add(new GroundBattle(battle.Name, fought, map, squad, battle.From));
                if (map == ArenaMap)
                    UsesArena(who);
                parts.Add($"{battle.Name} is battle {fought} on map {map}, its deploy area squad {squad}"
                          + (prompt > 0 ? $", its deploy prompt {prompt}" : "")
                          + (battle.From >= 0 ? $", once the story's progress is {battle.From}" : ""));
            }
            return battles;
        }

        /// <summary>(1.21.0) A mod's dungeon (its place given number `number`): each floor's battles planned as a
        /// battle ground's random battles are (PlanBattles), the quest flag it waits for found among its own mod's
        /// quests' (planned before it); a floor none of whose battles can be fought, or waiting for a flag its mod's
        /// quests don't have, is said and left out of its list (never listed), the others listed in its file's
        /// order. (1.24.0) A floor listed once the floor before it is won waits for that floor's won flag, given as
        /// a quest's flags are (WonKey); one whose floor before it is left out is left out too.</summary>
        void PlanDungeon(MapPlace place, int number, Numbers numbers, IReadOnlyDictionary<string, int>? maps,
                         bool ownUnits)
        {
            if (!place.Dungeon)
                return;
            string who = $"{place.Name} ({place.ModName})";
            var floors = new List<DungeonFloor>();
            var lines = new List<string>();
            // The floor before this one in its file, as planned (null: none, or left out).
            DungeonFloor? before = null;
            for (int n = 0; n < place.Floors.Count; n++)
            {
                var floor = place.Floors[n];
                var prior = before;
                before = null;
                int flag = -1;
                if (floor.AfterWin && prior == null)
                {
                    Said.Add($"{who}'s floor {floor.Name} isn't listed: the floor before it, "
                             + $"{(n > 0 ? place.Floors[n - 1].Name : "none")}, isn't listed.");
                    continue;
                }
                if (floor.Opens != null
                    && !Flags.TryGetValue($"{place.ModId}/{floor.Opens.Quest}/{floor.Opens.Flag}", out flag))
                {
                    Said.Add($"{who}'s floor {floor.Name} isn't listed: its mod has no side quest {floor.Opens.Quest} "
                             + $"added with a flag {floor.Opens.Flag}.");
                    continue;
                }
                var parts = new List<string>();
                var battles = PlanBattles(place, who, floor.Battles, numbers, maps, ownUnits, parts, false);
                if (battles.Count == 0)
                {
                    Said.Add($"{who}'s floor {floor.Name} isn't listed: none of its battles can be fought.");
                    continue;
                }
                if (floor.AfterWin)
                {
                    // (1.13.0) As a quest's flags: one past FlagBits would be the save's mark's.
                    int bit = numbers.Give("Flags", WonKey(place, prior!.Name), Range(0, FlagBits - 1),
                                           ItemRoom.FlagFree, out _);
                    if (bit < 0)
                    {
                        Said.Add($"{who}'s floor {floor.Name} isn't listed: no flag is left for {prior.Name} won.");
                        continue;
                    }
                    flag = FlagBase + bit;
                    prior.WonFlag = flag;
                    prior.WonLists = floor.Name;
                    _flagNames[flag] = $"{PlaceNamed(place)}'s floor {prior.Name} won";
                }
                var made = new DungeonFloor(floor.Name, floor.Description, flag, battles, floors.Count,
                                            floor.AfterWin ? prior!.Name : "");
                // (1.25.0) The quests' starts waiting at it, in the quests' order.
                foreach (var first in _floorStartsWaiting)
                    if (first.Place == number && first.Index < 0
                        && string.Equals(first.Floor, floor.Name, StringComparison.Ordinal))
                    {
                        first.Index = made.Index;
                        made.Firsts.Add(first);
                        FloorStarts.Add(first);
                    }
                floors.Add(made);
                before = made;
                lines.Add($"{floor.Name} "
                          + (floor.AfterWin ? $"(listed once {prior!.Name} is won, flag {flag})"
                             : flag >= 0 ? $"(listed once {floor.Opens!.Quest}'s {floor.Opens.Flag} is set, flag {flag})"
                             : "(listed from the start)")
                          + $": {string.Join("; ", parts)}");
            }
            if (floors.Count == 0)
            {
                Said.Add($"{who} is a dungeon with no floor to list.");
                return;
            }
            Dungeons[number] = new DungeonPlan(place, number, floors);
            Said.Add($"{who} is a dungeon of {floors.Count} floor{(floors.Count == 1 ? "" : "s")}: "
                     + string.Join(" | ", lines) + ".");
            foreach (var floor in floors)
                foreach (var first in floor.Firsts)
                    Said.Add(FirstLine(first, PlaceNamed(place), floor.Name));
        }

        /// <summary>(1.25.0) What a quest's start waiting at a floor says as it is planned.</summary>
        public static string FirstLine(FloorStart first, string place, string floor)
            => $"{first.Who}'s {first.Name} (event {first.Event}) waits at {place}'s floor {floor}: the floor plays it "
               + "in place of its battle while its conditions hold.";

        /// <summary>(1.25.0) The floor of `dungeon` at `index` (variable 92, the floor chosen) one of whose starts'
        /// battles has `won` as its won event, when a floor waits for it to be won (its WonFlag); else null. The game's
        /// rules give the event playing (variable 0x27) the won event as the battle is won (0x239294's load, 25: the
        /// variable cleared, then the event added, through the events' variable function), as the battle won event of a
        /// battle with no rules of its own (WonFloor).</summary>
        public static DungeonFloor? FirstWonFloor(DungeonPlan dungeon, int index, int won)
        {
            var floor = dungeon.Floors.Find(f => f.Index == index);
            return floor != null && floor.WonFlag >= 0 && won >= 0 && floor.Firsts.Exists(f => f.Won == won)
                ? floor : null;
        }

        /// <summary>(1.25.0) The first of a floor's starts whose conditions hold (`value` a variable as the world map
        /// reads it, `inParty` its test of a character), or null.</summary>
        public static FloorStart? FirstHolding(DungeonFloor floor, Func<int, int> value, Func<int, bool> inParty)
            => floor.Firsts.Find(f => Holds(f.Steps, value, inParty));

        /// <summary>(1.25.0) Whether `ev` is the won event of a battle a start waiting at a floor plays.</summary>
        public bool IsFirstWon(int ev) => ev >= 0 && FloorStarts.Exists(f => f.Won == ev);

        /// <summary>(1.25.1) The floors whose win was given in the battle being fought, a battle being from its floor
        /// chosen (Zodi's test 56: "Deepest Pit is won", then in the same second "Deepest Pit is won again"). As an
        /// action ends the battle asks its turn check twice: first only to see whether an event would play (its mode 2,
        /// 0x2389B1: a battle with rules of its own runs them, the event they load set aside at 0x2FF8274 and the event
        /// playing given its value back), then to play it (mode 0: its rules run again). Each run of the rules gives the
        /// event playing the won event through the events' variable function, so a quest's battle's win is given
        /// twice; a battle with no rules of its own is given the battle won event once (mode 2 only sets it aside,
        /// 0x238A6E). So a floor's win is one win a battle.</summary>
        public sealed class FloorWins
        {
            readonly HashSet<(int Place, int Index)> _won = new HashSet<(int, int)>();

            /// <summary>A floor of a mod's dungeon chosen: a battle of its own begins there.</summary>
            public void Chosen()
            {
                lock (_won)
                    _won.Clear();
            }

            /// <summary>Whether this is the first time the win of the floor at `index` of the dungeon at `place` is
            /// given in this battle.</summary>
            public bool First(int place, int index)
            {
                lock (_won)
                    return _won.Add((place, index));
            }
        }

        /// <summary>(1.24.0) A dungeon's floor's won flag's name in the numbers (a quest's are its mod and folder, then the
        /// flag: "place:" can't begin a quest's folder's name).</summary>
        public static string WonKey(MapPlace place, string floor) => $"{place.ModId}/place:{place.Name}/floor:{floor}#won";

        /// <summary>(1.24.0) The game's battle won event (0x192: its turn check gives the event playing, variable 0x27,
        /// it once every enemy is beaten in a battle with no rules of its own, as a random battle, 0x238A29: the
        /// variable cleared, then 0x192 added, AddCommand, by the events' variable function, 0x233368; the PlayStation's
        /// EVENT_ID_BATTLE_WON, as fft_decomp names it), and the battle being fought (variable 0x32, 50: the random
        /// battle's setup sets it).</summary>
        public const int BattleWonEvent = 0x192, CurrentBattle = 0x32, AddCommand = 0xB0;

        /// <summary>(1.24.0) The floor of `dungeon` won as the battle won event starts there: the floor chosen (at
        /// `index`, variable 92) when `battle` (variable 50) is one of its battles and a floor waits for it to be won;
        /// else null.</summary>
        public static DungeonFloor? WonFloor(DungeonPlan dungeon, int index, int battle)
        {
            var floor = dungeon.Floors.Find(f => f.Index == index);
            return floor != null && floor.WonFlag >= 0 && floor.Battles.Exists(b => b.Battle == battle) ? floor : null;
        }

        /// <summary>(1.21.0) A dungeon's floors listed now: those listed from the start, and those whose quest flag
        /// (as `flag` reads it) is set; each its place in the dungeon's floors.</summary>
        public static List<int> OpenFloors(DungeonPlan dungeon, Func<int, int> flag)
        {
            var open = new List<int>();
            foreach (var floor in dungeon.Floors)
                if (floor.Flag < 0 || flag(floor.Flag) != 0)
                    open.Add(floor.Index);
            return open;
        }

        /// <summary>(1.21.0) A floor's DeepDungeon row as the Deep's list reads it (0x161704, 0x161C70): DLCFlags 0, its name
        /// and its words each a distance from + 4, then the name and the words (the game's own centered, as its
        /// floors' are).</summary>
        public static byte[] FloorRow(Framework.DungeonFloor floor)
        {
            var name = Encoding.UTF8.GetBytes(floor.Name);
            var words = Encoding.UTF8.GetBytes(floor.Description.Length > 0
                                                   ? $"<center>{floor.Description}</center>" : "");
            var row = new byte[(12 + name.Length + 1 + words.Length + 1 + 3) & ~3];
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(4), 12 - 4);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(8), 12 + name.Length + 1 - 4);
            name.CopyTo(row, 12);
            words.CopyTo(row, 12 + name.Length + 1);
            return row;
        }

        /// <summary>(1.23.0) The game's words of the Deep's list (its Exit and About prompts, in the language the game
        /// shows) for a mod's dungeon (Zodi's answer after test 49, "Exit Old Quarry": the dungeon's name where the game's
        /// words name the Deep, in each language): each place they name the Deep (`deep`, its name in that language,
        /// found as it is written or in other capitals) the dungeon's name instead; words that don't name it as they
        /// are.</summary>
        public static string DungeonWords(string game, string deep, string dungeon)
        {
            if (game.Length == 0 || deep.Length == 0)
                return game;
            var built = new StringBuilder();
            int from = 0;
            while (true)
            {
                int at = game.IndexOf(deep, from, StringComparison.OrdinalIgnoreCase);
                if (at < 0)
                    break;
                built.Append(game, from, at - from).Append(dungeon);
                from = at + deep.Length;
            }
            return built.Append(game, from, game.Length - from).ToString();
        }

        /// <summary>(1.23.0) A mod's dungeon's About page (Zodi's answer after test 49, "About Old Quarry: a guide page
        /// of the dungeon's own, showing its place's description"), as the guide's window reads a GuidePage row (sheet
        /// 0xBC, 0x1A798E): DLCFlags 0, its comment and its pictures none (a distance into its zeros, no picture), its
        /// words and its title each a distance from + 0x10 (the window's reads), then the words and the title.</summary>
        public static byte[] AboutPage(string title, string words)
        {
            var w = Encoding.UTF8.GetBytes(words);
            var t = Encoding.UTF8.GetBytes(title);
            int zeros = PageHead, text = PageHead + PageZeros;
            var row = new byte[(text + w.Length + 1 + t.Length + 1 + 3) & ~3];
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(4), zeros);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(8), zeros);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(0x10), text - PageBase);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(0x14), text + w.Length + 1 - PageBase);
            w.CopyTo(row, text);
            t.CopyTo(row, text + w.Length + 1);
            return row;
        }

        /// <summary>(1.23.0) A GuidePage row's head (0x18 bytes: DLCFlags, its comment, its pictures and their count,
        /// its words, its title), the zeros after it its comment and pictures point into, and where its words' and
        /// title's distances are from (+ 0x10).</summary>
        public const int PageHead = 0x18, PageZeros = 0x20, PageBase = 0x10;

        /// <summary>(1.23.0) Whether a mod's dungeon has an About page (its place's description); one without has no About
        /// prompt in its list, and the T key opens nothing there.</summary>
        public static bool HasAbout(DungeonPlan dungeon) => dungeon.Place.Description.Length > 0;

        /// <summary>(1.21.0) The battle a dungeon's floor starts as it is chosen, or null: those the story's progress
        /// (`progress`, variable 110) has reached, one of them picked evenly, as a battle ground's battles are picked
        /// (GroundPick, always one).</summary>
        public static GroundBattle? FloorPick(DungeonFloor floor, int progress, Func<int, int> next)
        {
            var open = floor.Battles.FindAll(b => b.From < 0 || progress >= b.From);
            return open.Count == 0 ? null : open[next(open.Count)];
        }

        /// <summary>(1.17.0) The random battle a mod's battle ground starts as Ramza arrives (`forced` false) or as the
        /// battle ground he stands on is chosen (`forced`: always one), or null: those the story's progress has reached
        /// (`progress`, variable 110), one of them picked evenly, as the game picks among its own; arriving, only on
        /// Chance of 100 arrivals. `next(n)` is a random number from 0 to n less 1 (the hook's own).</summary>
        public static GroundBattle? GroundPick(GroundPlan ground, int progress, bool forced, Func<int, int> next)
        {
            var open = ground.Battles.FindAll(b => b.From < 0 || progress >= b.From);
            if (open.Count == 0)
                return null;
            if (!forced && next(100) >= ground.Chance)
                return null;
            return open[next(open.Count)];
        }

        /// <summary>Why an event's kept number was given up for another: (1.9.0) past the last the game's tables
        /// hold this time (their room not made: EventRoom.cs), else the game or another mod took it.</summary>
        string MovedWhy(int was) => was > _lastEvent
            ? $"as the game's tables hold events up to {_lastEvent} this time"
            : "as the game or another mod now uses its number";

        static IEnumerable<int> Range(int first, int last)
        {
            for (int n = first; n <= last; n++)
                yield return n;
        }

        void PlanQuest(Quest quest, Numbers numbers, List<int> candidates, Func<int, bool> free, ref int slotsLeft,
                       IReadOnlyDictionary<string, int>? places, IReadOnlyDictionary<string, int>? maps)
        {
            string who = $"{quest.Name} ({quest.ModName})";
            // (1.10.0) Its events' quest maps, each at the number the maps were given; one without, the quest left out.
            var mapNumbers = new Dictionary<string, int>(StringComparer.Ordinal);
            foreach (var ev in quest.Events)
            {
                if (ev.SetupMap.Length == 0 || mapNumbers.ContainsKey(ev.SetupMap))
                    continue;
                if (maps == null || !maps.TryGetValue($"{quest.ModId}/{ev.SetupMap}", out int number))
                {
                    Said.Add($"{who} is left out: its quest map {ev.SetupMap} isn't in the game this time.");
                    return;
                }
                mapNumbers[ev.SetupMap] = number;
            }
            // Which of its events a start loads: each scene gets an opening event and its battle
            // rules, as the game's world map scenes have; a battle is loaded as itself.
            var started = new List<string>();
            foreach (var start in quest.Starts)
                if (!started.Contains(start.Event) && quest.EventNamed(start.Event)!.Battle == null)
                    started.Add(start.Event);
            int needed = quest.Events.Count + started.Count;
            if (needed > slotsLeft)
            {
                Said.Add($"{who} is left out: it needs {needed} setup records and the game searches {slotsLeft} "
                         + "more slots.");
                return;
            }
            var battleNumbers = new Dictionary<string, int>(StringComparer.Ordinal);
            foreach (var battle in quest.Battles)
            {
                int n = numbers.Give("Battles", $"{quest.Key}/{battle.Name}", Range(FirstBattle, LastBattle), _ => true,
                                     out _);
                if (n < 0)
                {
                    Said.Add($"{who} is left out: no battle number is left for {battle.Name}.");
                    return;
                }
                battleNumbers[battle.Name] = n;
            }
            // (1.14.0) Each battle's own deploy areas: a squad each, numbered past the game's 768 (kept as "Squads"),
            // given the program only once the quest is planned whole; without the squads found, its setup's.
            var squadNumbers = new Dictionary<string, List<int>>(StringComparer.Ordinal);
            var squads = new List<(int Number, byte[] Bytes)>();
            foreach (var ev in quest.Events)
            {
                if (ev.Battle == null || ev.Battle.Deploy.Count == 0 || !OwnSquads)
                    continue;
                int map = ev.SetupMap.Length > 0 && mapNumbers.TryGetValue(ev.SetupMap, out int made) ? made
                          : ev.Setup.TryGetValue("Map", out int game) ? game : 0;
                var given = new List<int>();
                for (int a = 0; a < ev.Battle.Deploy.Count; a++)
                {
                    int n = numbers.Give("Squads", $"{quest.Key}/{ev.Name}#{a + 1}",
                                         Range(DeploySquads.FirstOwn, DeploySquads.LastOwn), _ => true, out _);
                    if (n < 0)
                    {
                        Said.Add($"{who} is left out: no deploy area number is left for {ev.Name}.");
                        return;
                    }
                    given.Add(n);
                    squads.Add((n, ev.Battle.Deploy[a].Squad(n, map)));
                }
                squadNumbers[ev.Name] = given;
            }
            var eventNumbers = new Dictionary<string, int>(StringComparer.Ordinal);
            var said = new List<string>();
            foreach (var ev in quest.Events)
            {
                numbers.Has("Events", $"{quest.Key}/{ev.Name}", out int was);
                int n = numbers.Give("Events", $"{quest.Key}/{ev.Name}", candidates, free, out bool moved);
                if (n < 0)
                {
                    Said.Add($"{who} is left out: no event number is left for {ev.Name}.");
                    return;
                }
                if (moved)
                    said.Add($"{ev.Name} moved to event {n}, {MovedWhy(was)}");
                eventNumbers[ev.Name] = n;
            }
            var openings = new Dictionary<string, int>(StringComparer.Ordinal);
            var rules = new Dictionary<string, int>(StringComparer.Ordinal);
            foreach (var name in started)
            {
                numbers.Has("Events", $"{quest.Key}/{name}#opening", out int was);
                int n = numbers.Give("Events", $"{quest.Key}/{name}#opening", candidates, free, out bool moved);
                int r = numbers.Give("Rules", $"{quest.Key}/{name}#opening", Range(FirstRules, LastRules), _ => true,
                                     out _);
                if (n < 0 || r < 0)
                {
                    Said.Add($"{who} is left out: no {(n < 0 ? "event number" : "battle rules key")} is left for "
                             + $"{name}'s opening.");
                    return;
                }
                if (moved)
                    said.Add($"{name}'s opening moved to event {n}, {MovedWhy(was)}");
                openings[name] = n;
                rules[name] = r;
            }
            var prompts = new Dictionary<string, int>(StringComparer.Ordinal);
            foreach (var ev in quest.Events)
            {
                if (ev.Battle == null)
                    continue;
                int r = numbers.Give("Rules", $"{quest.Key}/{ev.Name}#battle", Range(FirstRules, LastRules), _ => true,
                                     out _);
                int k = numbers.Give("Prompts", $"{quest.Key}/{ev.Name}", Range(FirstPrompt, int.MaxValue - 1),
                                     _ => true, out _);
                if (r < 0 || k < 0)
                {
                    Said.Add($"{who} is left out: no {(r < 0 ? "battle rules key" : "deploy prompt key")} is left for "
                             + $"{ev.Name}.");
                    return;
                }
                rules[ev.Name] = r;
                prompts[ev.Name] = k;
            }
            var flags = new Dictionary<string, int>(StringComparer.Ordinal);
            foreach (var flag in quest.Flags)
            {
                // (1.13.0) A flag kept past FlagBits (none ever was) would be the save's mark's: given another. (1.26.0)
                // Nor in WotL Restoration's items' counts' bytes or the mods' items' (ItemRoom.FlagFree).
                int bit = numbers.Give("Flags", $"{quest.Key}/{flag}", Range(0, FlagBits - 1), ItemRoom.FlagFree,
                                       out _);
                if (bit < 0)
                {
                    Said.Add($"{who} is left out: no flag is left for {flag}.");
                    return;
                }
                flags[flag] = FlagBase + bit;
            }
            // (1.12.0) Each battle's objective a key past the game's, which its start event shows (DisplayConditions'
            // byte the key + 8, where its ObjectiveInScript says).
            var objectives = new Dictionary<string, int>(StringComparer.Ordinal);
            foreach (var ev in quest.Events)
            {
                if (ev.Battle == null || ev.Battle.Objective.Length == 0)
                    continue;
                int k = numbers.Give("Objectives", $"{quest.Key}/{ev.Name}", Range(FirstObjective, LastObjective),
                                     _ => true, out _);
                if (k < 0)
                {
                    Said.Add($"{who} is left out: no objective is left for {ev.Name}.");
                    return;
                }
                objectives[ev.Name] = k;
            }
            // (1.15.0) Each rumor a key of the taverns' rumors past the game's and WotL Restoration's, up to the last the
            // taverns list (kept as "Rumors"); none when they can't be told. (1.29.0) Given as the game starts, from the
            // rumors enabled now (Plan's BeginNow).
            var rumorKeys = new Dictionary<string, int>(StringComparer.Ordinal);
            if (OwnRumors)
                foreach (var rumor in quest.Rumors)
                {
                    int k = numbers.GiveNow(RumorsKind, $"{quest.Key}/{rumor.Name}", Range(FirstRumor, LastRumor), out _);
                    if (k < 0)
                    {
                        Said.Add($"{who} is left out: no rumor number is left for {rumor.Name} (they are the rumors "
                                 + "enabled at once).");
                        return;
                    }
                    rumorKeys[rumor.Name] = k;
                }
            var planned = new List<Planned>();
            foreach (var ev in quest.Events)
            {
                var script = ev.Battle != null ? (byte[])OpeningScript.Clone() : (byte[])ev.Script.Clone();
                foreach (var (at, flag) in ev.FlagsInScript)
                    BinaryPrimitives.WriteUInt16LittleEndian(script.AsSpan(at, 2), (ushort)flags[flag]);
                var shows = quest.FightOf(ev.Name);
                if (shows != null && shows.Battle!.Start == ev.Name && objectives.TryGetValue(shows.Name, out int shown))
                    foreach (int at in ev.ObjectiveInScript)
                        script[at] = (byte)(FirstShown + shown);
                var p = new Planned(quest, ev, eventNumbers[ev.Name], script);
                if (ev.Words.Length > 0)
                {
                    p.Scene = numbers.Give("Scenes", $"{quest.Key}/{ev.Name}", Range(FirstScene, int.MaxValue - 1),
                                           _ => true, out _);
                    p.Text = numbers.Give("Texts", $"{quest.Key}/{ev.Name}", Range(FirstText, int.MaxValue - 1),
                                          _ => true, out _);
                }
                planned.Add(p);
            }
            // An event's setup with its battles' names made numbers; a battle's enemies its units'; (1.10.0) its quest
            // map its number.
            Dictionary<string, int> Resolved(QuestEvent ev)
            {
                var setup = new Dictionary<string, int>(ev.Setup, StringComparer.Ordinal);
                foreach (var (field, named) in ev.SetupBattles)
                    setup[field] = battleNumbers[named];
                if (ev.SetupMap.Length > 0)
                    setup["Map"] = mapNumbers[ev.SetupMap];
                if (ev.Battle != null)
                    setup["EnemyBattle"] = ev.Battle.Units.Length > 0 ? battleNumbers[ev.Battle.Units]
                                                                     : ev.Battle.GameUnits;
                // (1.14.0) Its own deploy areas in place of its setup's.
                if (squadNumbers.TryGetValue(ev.Name, out var own))
                {
                    setup["DeployArea1"] = own[0];
                    setup["DeployArea2"] = own.Count > 1 ? own[1] : 0;
                }
                return setup;
            }
            // Records: each event's, then each opening's (the scene's record with its rules, as the game's).
            foreach (var p in planned)
            {
                var ev = p.Event;
                int next = ev.NextEvent.Length > 0 ? eventNumbers[ev.NextEvent] : 0;
                var fight = quest.FightOf(ev.Name);
                Dictionary<string, int> setup;
                int rulesKey = 0;
                if (ev.Battle != null)
                {
                    // The game's battle events: the battle's setup and rules, nothing after it of its own.
                    setup = Resolved(ev);
                    rulesKey = rules[ev.Name];
                }
                else if (fight != null)
                {
                    // An event in a battle has the battle's setup (its map, music, units), with its own
                    // fields over it; the battle goes on after its start event, and its won event goes
                    // back to the world map (or on), as the game's.
                    setup = Resolved(fight);
                    setup.Remove("AfterEvent");
                    foreach (var (field, value) in Resolved(ev))
                        setup[field] = value;
                    if (fight.Battle!.Won == ev.Name)
                        setup = WithAfter(setup, next);
                    else if (fight.Battle.Lost == ev.Name)
                        setup["AfterEvent"] = StartOver;
                    else if (!setup.ContainsKey("AfterEvent"))
                        setup["AfterEvent"] = 0;
                }
                else
                    setup = WithAfter(Resolved(ev), next);
                Records.Add(Record(p.Number, setup, next, rulesKey));
                Scripts[p.Number] = p.Script;
                // (1.30.0) Where its script names Ramza; and map 116 named when it plays there.
                if (ev.RamzaInScript.Count > 0)
                    RamzaPlaces[p.Number] = ev.RamzaInScript.ToArray();
                // (1.31.0) Its reward, by the flag whose setting gives it.
                if (ev.Reward != null)
                    PlanReward(quest, ev, flags[ev.Reward.Flag]);
                if (setup.TryGetValue("Map", out int onMap) && onMap == ArenaMap)
                    UsesArena(who);
                ProgressSetsIn(p.Script, _progressSets);
                Events.Add(p);
            }
            foreach (var name in started)
            {
                var scene = quest.EventNamed(name)!;
                var setup = Resolved(scene);
                setup["AfterEvent"] = 0;
                Records.Add(Record(openings[name], setup, 0, rules[name]));
                Scripts[openings[name]] = (byte[])OpeningScript.Clone();
                Openings.Add((openings[name], eventNumbers[name]));
                RuleSets[rules[name]] = (quest, new List<List<byte[]>>
                {
                    new List<byte[]>
                    {
                        RuleRow(Equal, BattleLoaded, 0, new short[] { 1 }),
                        RuleRow(LoadEvent, 0, eventNumbers[name], Array.Empty<short>()),
                    },
                });
            }
            foreach (var ev in quest.Events)
            {
                if (ev.Battle == null)
                    continue;
                // The game's battles' rules: its start event as the battle loads (the battle not
                // started, 509, is 1), its won event once every enemy is beaten (with the victory
                // guard 0 first, as 26 of the game's battles). (1.11.1) A battle without a start event
                // of its own starts with the game's battle start (event 401, as its random battles do):
                // the game runs a story battle's rules as its formation screen closes, before its
                // enemies are on the field, and every one of its battles plays its start event first
                // (Zodi's test 37: the battle won at once).
                var chains = new List<List<byte[]>>
                {
                    new List<byte[]>
                    {
                        RuleRow(Equal, BattleLoaded, 0, new short[] { 1 }),
                        RuleRow(LoadEvent, 0, ev.Battle.Start.Length > 0 ? eventNumbers[ev.Battle.Start] : BattleStart,
                                Array.Empty<short>()),
                    },
                };
                // (1.12.0) Lost once the unit it protects is beaten (before it is won, as the game's battles test),
                // its lost event then; won as its WonWhen says. A unit by its unit ID, which names it (CharaControlId).
                var fight = ev.Battle;
                var units = fight.Units.Length > 0 ? quest.Battles.Find(b => b.Name == fight.Units)?.Units : null;
                int UnitId(int slot) => units![(slot - 1) * QuestFile.UnitBytes + QuestFile.UnitIdAt];
                int won = eventNumbers[fight.Won];
                if (fight.Protect > 0)
                    chains.Add(new List<byte[]>
                    {
                        RuleRow(Equal, VictoryGuard, 0, new short[] { 0 }),
                        RuleRow(Present, 0, 0, Array.Empty<short>(), UnitId(fight.Protect)),
                        RuleRow(HpAtMost, 0, 0, new short[] { 0 }, UnitId(fight.Protect)),
                        RuleRow(LoadEvent, 0, eventNumbers[fight.Lost], Array.Empty<short>()),
                    });
                // (1.31.0, Zodi's test 65: "one mid battle mostly for dialogue"; his choice "Either, picked on the card")
                // Each scene during it, once a battle: its guard (QuestFile.Guards, by its place: the scenario's own
                // variable it sets as it ends) and the victory guard 0, its unit there, then its unit acting and alive
                // (as Gariland's key 3 plays event 11 on Ramza's turn), or its HP at most its share (0: beaten). Ramza by
                // whichever of his chapters is there.
                for (int k = 0; k < fight.During.Count; k++)
                {
                    var d = fight.During[k];
                    int mid = eventNumbers[d.Event];
                    foreach (int unit in d.Unit == 0 ? Ramzas : new[] { UnitId(d.Unit) })
                    {
                        var chain = new List<byte[]>
                        {
                            RuleRow(Equal, QuestFile.Guards[k], 0, new short[] { 0 }),
                            RuleRow(Equal, VictoryGuard, 0, new short[] { 0 }),
                            RuleRow(Present, 0, 0, Array.Empty<short>(), unit),
                        };
                        if (d.When == QuestFight.Turn)
                        {
                            chain.Add(RuleRow(Acting, 0, 0, Array.Empty<short>(), unit));
                            chain.Add(RuleRow(HpAtLeast, 0, 0, new short[] { 1 }, unit));
                        }
                        else
                            chain.Add(d.Share == 0 ? RuleRow(HpAtMost, 0, 0, new short[] { 0 }, unit)
                                                   : RuleRow(ShareAtMost, 0, 0, new short[] { (short)d.Share }, unit));
                        chain.Add(RuleRow(LoadEvent, 0, mid, Array.Empty<short>()));
                        chains.Add(chain);
                    }
                }
                if (fight.WonBy == QuestFight.Beaten || fight.WonBy == QuestFight.WornDown)
                    chains.Add(new List<byte[]>
                    {
                        RuleRow(Equal, VictoryGuard, 0, new short[] { 0 }),
                        RuleRow(Present, 0, 0, Array.Empty<short>(), UnitId(fight.WonUnit)),
                        fight.WonBy == QuestFight.Beaten
                            ? RuleRow(HpAtMost, 0, 0, new short[] { 0 }, UnitId(fight.WonUnit))
                            : RuleRow(ShareAtMost, 0, 0, new short[] { (short)fight.WonShare }, UnitId(fight.WonUnit)),
                        RuleRow(LoadEvent, 0, won, Array.Empty<short>()),
                    });
                if (fight.WonBy == QuestFight.OnTile)
                    foreach (int ramza in Ramzas)
                        chains.Add(new List<byte[]>
                        {
                            RuleRow(Equal, VictoryGuard, 0, new short[] { 0 }),
                            RuleRow(OnTileStep, 0, 0, new[] { (short)fight.TileX, (short)fight.TileY,
                                                              (short)fight.TileUpper }, ramza),
                            RuleRow(LoadEvent, 0, won, Array.Empty<short>()),
                        });
                if (fight.WonBy == QuestFight.Enemies || fight.WonBy == QuestFight.OnTile)
                    chains.Add(new List<byte[]>
                    {
                        RuleRow(Equal, VictoryGuard, 0, new short[] { 0 }),
                        RuleRow(EnemiesDefeated, 0, 0, Array.Empty<short>()),
                        RuleRow(LoadEvent, 0, won, Array.Empty<short>()),
                    });
                RuleSets[rules[ev.Name]] = (quest, chains);
                if (objectives.TryGetValue(ev.Name, out int objective))
                    ObjectiveRows.Add((objective, fight.Objective, fight.Protect > 0, $"{who}'s {ev.Name}"));
                Fights.Add((eventNumbers[ev.Name], prompts[ev.Name]));
                PromptRowsNeeded.Add((prompts[ev.Name], Resolved(ev).TryGetValue("Map", out int map) ? map : 0,
                                      $"{who}'s {ev.Name}"));
                int first = eventNumbers[ev.Battle.Start.Length > 0 ? ev.Battle.Start : ev.Battle.Won];
                if (ev.Battle.Start.Length > 0)
                    FightScenes.Add((eventNumbers[ev.Battle.Start], first));
                FightScenes.Add((eventNumbers[ev.Battle.Won], first));
                if (ev.Battle.Lost.Length > 0)
                    FightScenes.Add((eventNumbers[ev.Battle.Lost], first));
                // (1.31.0) Its scenes during it too.
                foreach (var d in ev.Battle.During)
                    FightScenes.Add((eventNumbers[d.Event], first));
            }
            foreach (var start in quest.Starts)
            {
                var steps = ConditionSteps(start.When, flags);
                // (1.2.4) A start that waits until its place is chosen: last, no travel passing through (the
                // world map stops at a chain's first test that fails, so it is read only where the event
                // would load, and the helper says so then).
                if (!start.StopsPassing)
                    steps.Add(WorldRow(Equal, PassingThrough, new short[] { 0 }));
                var fought = quest.EventNamed(start.Event)!.Battle;
                bool battle = fought != null;
                int loaded = battle ? eventNumbers[start.Event] : openings[start.Event];
                if (start.Floor.Length > 0)
                {
                    // (1.25.0) Waiting at a floor of one of its mod's dungeons: its conditions, then its load as the
                    // floor's code starts it (at once, as the floor's battles leave the world map); found at its floor
                    // as the dungeons are planned, after the quests.
                    var floorSteps = ConditionSteps(start.When, flags);
                    floorSteps.Add(WorldRow(LoadEvent, 0, new[] { (short)loaded, (short)Places.InstantTransition }));
                    if (places == null || start.PlaceName.Length == 0
                        || !places.TryGetValue($"{quest.ModId}/{start.PlaceName}", out int dungeonPlace))
                    {
                        said.Add($"its start at {start.PlaceName}'s floor {start.Floor} is left out ({start.PlaceName} "
                                 + "isn't somewhere to go)");
                        continue;
                    }
                    if (OwnFloorStarts)
                        _floorStartsWaiting.Add(new FloorStart(quest, dungeonPlace, start.PlaceName, start.Floor,
                                                               floorSteps, loaded, start.Event,
                                                               battle ? eventNumbers[fought!.Won] : -1));
                    continue;
                }
                steps.Add(battle
                    ? WorldRow(LoadEvent, 0, new[] { (short)loaded, (short)BattleMode })
                    : WorldRow(LoadEvent, 0, new[] { (short)loaded, (short)SceneMode }));
                int place = start.Place;
                if (start.PlaceName.Length > 0)
                {
                    // (1.8.0) One of its mod's own places, at the number the places were given; none, left out.
                    if (places == null || !places.TryGetValue($"{quest.ModId}/{start.PlaceName}", out place))
                    {
                        said.Add($"its start at {start.PlaceName} is left out ({start.PlaceName} isn't somewhere to go)");
                        continue;
                    }
                }
                Starts.Add(new Start(quest, place, steps));
            }
            // (1.15.0) Its rumors: told in their towns while their When holds (the world map's own tests, run as Holds
            // runs them: RumorTold), the flag each sets once it is read.
            foreach (var rumor in quest.Rumors)
            {
                if (!rumorKeys.TryGetValue(rumor.Name, out int key))
                    continue;
                var steps = ConditionSteps(rumor.When, flags);
                steps.Add(WorldRow(LoadEvent, 0, new short[] { 0, 0 }));
                int mask = rumor.EveryTavern ? EveryTavern : 0;
                foreach (int town in rumor.Towns)
                    mask |= TownBit >> town;
                // (1.18.0) The mod's own towns it names: each one of its mod's towns with a menu (a tavern), else said.
                var modTowns = new HashSet<int>();
                foreach (string named in rumor.TownNames)
                {
                    if (places != null && places.TryGetValue($"{quest.ModId}/{named}", out int at)
                        && MenuTowns.ContainsKey(at))
                        modTowns.Add(at);
                    else
                        said.Add($"its rumor {rumor.Name} isn't told at {named} ({named} has no tavern: no menu of its "
                                 + "own)");
                }
                RumorPlans.Add(new RumorPlan(key, quest, rumor, steps, flags[rumor.Read], mask, modTowns));
            }
            var worn = new List<string>();
            foreach (var battle in quest.Battles)
            {
                Units[battleNumbers[battle.Name]] = (byte[])battle.Units.Clone();
                _battleNames[battleNumbers[battle.Name]] = $"{QuestNamed(quest)}'s {battle.Name}";
                // (1.33.0) Its units' own names.
                if (battle.Names.Count > 0)
                    OwnNames[battleNumbers[battle.Name]] = new SortedDictionary<int, string>(battle.Names);
                // (2.0.0) Its units' items past 255.
                if (battle.Items.Count > 0)
                    WideItems.Add(new BattleFile.QuestItems(quest.ModId, _battleNames[battleNumbers[battle.Name]],
                                                            battleNumbers[battle.Name], battle.Items));
                // (1.53.0) Its units' jobs of its mod's own: each the number its job was given, where its mod gives that
                // job to the game this time; else the unit keeps its file's job, said.
                WearJobs(quest, battle, Units[battleNumbers[battle.Name]], worn, said);
            }
            Squads.AddRange(squads);
            foreach (var (flag, n) in flags)
            {
                Flags[$"{quest.Key}/{flag}"] = n;
                _flagNames[n] = $"{QuestNamed(quest)}'s {flag}";
            }
            foreach (var p in planned)
                _names[p.Number] = $"{QuestNamed(quest)}'s {p.Event.Name}";
            foreach (var (name, n) in openings)
                _names[n] = $"{QuestNamed(quest)}'s {name} (its opening)";
            slotsLeft -= planned.Count + started.Count;
            var parts = new List<string>();
            foreach (var p in planned)
                parts.Add(openings.TryGetValue(p.Event.Name, out int o) ? $"{p.Event.Name} is event {p.Number} (its opening {o})"
                    : p.Event.Battle != null && p.Event.Battle.Start.Length == 0
                        ? $"{p.Event.Name} is event {p.Number} (a battle, starting with the game's battle start, event "
                          + $"{BattleStart})"
                    : p.Event.Battle != null ? $"{p.Event.Name} is event {p.Number} (a battle)"
                    : $"{p.Event.Name} is event {p.Number}");
            foreach (var battle in quest.Battles)
                parts.Add($"{battle.Name} is battle {battleNumbers[battle.Name]}");
            parts.AddRange(worn);
            // (1.12.0) How each battle is won and lost, and its objective's number.
            foreach (var ev in quest.Events)
            {
                var fight = ev.Battle;
                if (fight == null)
                    continue;
                if (fight.WonBy == QuestFight.Beaten)
                    parts.Add($"{ev.Name} is won once its unit {fight.WonUnit} is beaten");
                else if (fight.WonBy == QuestFight.WornDown)
                    parts.Add($"{ev.Name} is won once its unit {fight.WonUnit} is down to {fight.WonShare} percent of "
                              + "its HP");
                else if (fight.WonBy == QuestFight.OnTile)
                    parts.Add($"{ev.Name} is won once Ramza stands on the tile at {fight.TileX}, {fight.TileY}"
                              + (fight.TileUpper == 1 ? " (its upper level)" : "") + ", or once every enemy is beaten");
                if (fight.Protect > 0)
                    parts.Add($"{ev.Name} is lost once its unit {fight.Protect} is beaten");
                if (objectives.TryGetValue(ev.Name, out int k))
                    parts.Add($"{ev.Name}'s objective is objective {k}");
                // (1.14.0) Its own deploy areas' squads.
                if (squadNumbers.TryGetValue(ev.Name, out var own))
                    parts.Add(own.Count == 1 ? $"{ev.Name}'s deploy area is squad {own[0]}"
                                             : $"{ev.Name}'s deploy areas are squads {own[0]} and {own[1]}");
            }
            // (1.15.0) Its rumors' keys.
            foreach (var rumor in quest.Rumors)
                if (rumorKeys.TryGetValue(rumor.Name, out int key))
                    parts.Add($"{rumor.Name} is rumor {key}");
            foreach (var (flag, n) in flags)
                parts.Add($"{flag} is flag {n}");
            parts.AddRange(said);
            Said.Add($"{who}: {string.Join(", ", parts)}.");
        }

        /// <summary>(1.53.0, Zodi's order of 13 November: "jobs in a quest's battle") A quest's battle's units put in jobs
        /// of its mod's own (its Jobs): each named unit's job (QuestFile.MainJobAt in its 40 bytes) the number its job was
        /// given, where its mod gives that job to the game this time (`_jobs`, by the job's key); else the unit keeps its
        /// file's job. What was put on (`worn`, for the quest's line) and what wasn't (`said`).</summary>
        void WearJobs(Quest quest, QuestBattle battle, byte[] units, List<string> worn, List<string> said)
        {
            foreach (var (slot, job) in battle.Jobs)
            {
                int at = slot * QuestFile.UnitBytes + QuestFile.MainJobAt;
                if (_jobs != null && _jobs.TryGetValue($"{quest.ModId}/{job}", out int number))
                {
                    units[at] = (byte)number;
                    worn.Add(WornLine(battle.Name, slot, job, number));
                }
                else
                    said.Add(NotWornLine(battle.Name, slot, job, units[at]));
            }
        }

        /// <summary>(1.53.0) The quest's line's parts for a battle's unit put in a job of its mod's own, and for one that
        /// keeps its file's job.</summary>
        public static string WornLine(string battle, int slot, string job, int number)
            => $"unit {slot + 1} of {battle} is put in its mod's {job} (job {number})";

        public static string NotWornLine(string battle, int slot, string job, int kept)
            => $"unit {slot + 1} of {battle} keeps job {kept} (its mod gives the game no job {job} this time)";

        /// <summary>An event's setup with what follows it: as given, else its next event when it
        /// has one, else the world map (a side quest's event goes on or back, as the game's
        /// world map scenes do).</summary>
        static Dictionary<string, int> WithAfter(Dictionary<string, int> setup, int next)
        {
            var with = new Dictionary<string, int>(setup, StringComparer.Ordinal);
            if (!with.ContainsKey("AfterEvent"))
                with["AfterEvent"] = next > 0 ? NextEvent : WorldMap;
            return with;
        }

        /// <summary>A setup record: the event, the fields given, the next event and the battle
        /// rules (16 bits at 22, as the program reads them).</summary>
        public static byte[] Record(int ev, Dictionary<string, int> setup, int next, int rules)
        {
            var record = new byte[Table.RecordBytes];
            BinaryPrimitives.WriteUInt16LittleEndian(record.AsSpan(0, 2), (ushort)ev);
            foreach (var (key, value) in setup)
                Fields.Find(key)!.Write(record, value);
            Fields.Find("NextEvent")!.Write(record, next);
            Fields.Find("BattleRules")!.Write(record, rules);
            return record;
        }

        // --- rows, laid out as the game's tables' ---------------------------

        static void I32(byte[] b, int at, int v) => BinaryPrimitives.WriteInt32LittleEndian(b.AsSpan(at, 4), v);
        static void I16(byte[] b, int at, int v) => BinaryPrimitives.WriteInt16LittleEndian(b.AsSpan(at, 2), unchecked((short)v));

        /// <summary>A world map step (EnhancedWorldEvent's 32 bytes, then its list of numbers): its
        /// type, a variable (an equal test's), its numbers; places 47 (none), as the game's tests.</summary>
        public static byte[] WorldRow(short type, int variable, short[] numbers)
        {
            var row = new byte[0x20 + ((numbers.Length * 2 + 3) & ~3)];
            I16(row, 4, type);
            I32(row, 8, 0x20);
            I32(row, 0x0C, numbers.Length);
            I32(row, 0x10, variable);
            I32(row, 0x14, 47);
            I32(row, 0x18, 47);
            for (int n = 0; n < numbers.Length; n++)
                I16(row, 0x20 + 2 * n, numbers[n]);
            return row;
        }

        /// <summary>A battle rules step (EnhancedBattleEvent's 40 bytes, its list, then its empty
        /// comment): its type, a variable (an equal test's), an event (a load's), its numbers.</summary>
        public static byte[] RuleRow(short type, int variable, int ev, short[] numbers, int unit = 0)
        {
            int list = (numbers.Length * 2 + 3) & ~3;
            var row = new byte[0x28 + list + 4];
            I16(row, 4, type);
            // (1.12.0) The unit a test names, by its CharaControlId key (its unit ID: QuestFile.NamedUnit).
            I16(row, 8, unit);
            I16(row, 0x0C, variable);
            I16(row, 0x10, ev);
            I32(row, 0x14, 0x28);
            I32(row, 0x18, numbers.Length);
            I32(row, 0x24, 0x28 + list);
            for (int n = 0; n < numbers.Length; n++)
                I16(row, 0x28 + 2 * n, numbers[n]);
            return row;
        }

        /// <summary>A battle's row of the battles' units table (EntryNo, 28 bytes then its lists):
        /// no deploy prompt of its own, no changes by difficulty but the game's own 130 each (as
        /// 263 of the game's battles have), and an empty comment. (1.17.0) A battle ground's random battle's names
        /// its deploy prompt (`prompt`, its SortieConfirm key at 8), as each of the game's random battles'
        /// does.</summary>
        public static byte[] EntryRow(int prompt = 0)
        {
            var row = new byte[EntryRowBytes + 3 * 4 + 4];
            I32(row, 4, EntryRowBytes + 3 * 4);
            I32(row, EntryPrompt, prompt);
            I32(row, 0x0C, EntryRowBytes);
            I32(row, 0x10, 0);
            I32(row, 0x14, EntryRowBytes);
            I32(row, 0x18, 3);
            for (int n = 0; n < 3; n++)
                I32(row, EntryRowBytes + 4 * n, 130);
            return row;
        }

        /// <summary>A scene's row (ScenarioId: its events, then its words' file's key).</summary>
        public static byte[] SceneRow(int ev, int text)
        {
            var row = new byte[0x14];
            I32(row, 4, 0x10);
            I32(row, 8, 1);
            I32(row, 0x0C, text);
            I32(row, 0x10, ev);
            return row;
        }

        /// <summary>(1.12.0) A battle's objective's row (BattleObjective), as the game's 69 are: its words after its 16
        /// bytes, pointed at from its Name (+ 4: the program reads them at the Name's own place plus the number it
        /// holds, 0x0FB5B0, not from the row's start as ScionFiles' path); its IsProtectionMission (+ 0xC) 1 when the
        /// battle protects a unit, as the game's "Protect" objectives have (read at 0x1EB5D0); the rest 0.</summary>
        public static byte[] ObjectiveRow(string words, bool protects)
        {
            var bytes = Encoding.UTF8.GetBytes(words);
            var row = new byte[(ObjectiveRowBytes + bytes.Length + 1 + 3) & ~3];
            I32(row, ObjectiveName, ObjectiveRowBytes - ObjectiveName);
            row[ObjectiveProtects] = (byte)(protects ? 1 : 0);
            bytes.CopyTo(row, ObjectiveRowBytes);
            return row;
        }

        /// <summary>(1.15.0) A rumor's row (Gossip), as the game's 23 are: its title then its words after its 48 bytes,
        /// each pointed at from + 0xC (the title's place there, the words' at + 0x10, both counted from + 0xC, as the
        /// tavern's screen reads them at 0x1A041C); its two lists empty, pointed at the row's end; no counter or stage
        /// (+ 4, + 8: no lists done as it is read, no picture), no situation (+ 0x24), not told in every tavern by its
        /// own byte (+ 0x2C: its towns and its When say where and when, RumorTold).</summary>
        public static byte[] RumorRow(string title, string text)
        {
            var heading = Encoding.UTF8.GetBytes(title);
            var words = Encoding.UTF8.GetBytes(text);
            var row = new byte[(RumorRowBytes + heading.Length + 1 + words.Length + 1 + 3) & ~3];
            I32(row, RumorTitle, RumorRowBytes - RumorTitle);
            I32(row, RumorText, RumorRowBytes + heading.Length + 1 - RumorTitle);
            I32(row, RumorLists, RumorRowBytes);
            I32(row, RumorLists + 8, RumorRowBytes);
            heading.CopyTo(row, RumorRowBytes);
            words.CopyTo(row, RumorRowBytes + heading.Length + 1);
            return row;
        }

        /// <summary>A words file's row (ScionFiles: its path, pointed at from the row's start, as the
        /// program reads it at 0x1DA7A4).</summary>
        public static byte[] TextRow(string path)
        {
            var bytes = Encoding.UTF8.GetBytes(path);
            var row = new byte[(8 + bytes.Length + 1 + 3) & ~3];
            I32(row, 4, 8);
            bytes.CopyTo(row, 8);
            return row;
        }

        // --- the tables, as the game loads them ------------------------------

        /// <summary>Whether a table gets rows (or, EventId, its rows of the quests' events made).</summary>
        public bool Adds(int sheet) => sheet switch
        {
            WorldStarts => Starts.Count > 0,
            Rules => RuleSets.Count > 0,
            Scenes or Texts => Events.Exists(p => p.Scene >= 0),
            // (1.9.0) Rows for the quests' events past 886, which every event the game plays needs.
            EventRows => Openings.Count > 0 || Fights.Count > 0 || FightScenes.Count > 0 || EventsPastGame().Count > 0,
            EntryRows => Units.Count > 0,
            Prompts => PromptRowsNeeded.Count > 0 || GroundPrompts.Count > 0,
            Objectives => ObjectiveRows.Count > 0,
            Rumors => RumorPlans.Count > 0,
            // (1.30.0) Map 116's name: its Map row named, made in place (NameArena), and PlaceName's row of it.
            MapSheet or NameSheet => NamesArena,
            _ => false,
        };

        /// <summary>(1.30.0) Map 116's Map row naming its own PlaceName row (ArenaKey), in place: only the row the game
        /// has, naming the game's 10100 (no row); already named so, nothing. Why not, or "".</summary>
        public static string NameArena(Span<byte> table)
        {
            var rows = Nxd.Rows(table, out string why);
            if (rows == null)
                return why;
            if (Nxd.Keys(table) != 1)
                return $"it isn't a table of one key (byte 8: {table[8]})";
            int found = rows.FindIndex(r => r.Keys[0] == ArenaMap);
            if (found < 0)
                return $"it has no row {ArenaMap}";
            int at = rows[found].At;
            if (at + MapRowBytes > table.Length)
                return "its row is cut short";
            int named = BinaryPrimitives.ReadInt32LittleEndian(table.Slice(at + MapName, 4));
            if (named == ArenaKey)
                return "";
            if (named != ArenaUnnamed)
                return $"its row {ArenaMap} names PlaceName {named}, not the game's {ArenaUnnamed}: another mod named it";
            BinaryPrimitives.WriteInt32LittleEndian(table.Slice(at + MapName, 4), ArenaKey);
            return "";
        }

        /// <summary>The events' table's rows of the quests' openings, battles and scenes made as the
        /// game's are, in place: each opening's what-it-shows as the game's opening 13's, each
        /// scene an opening starts its byte at 0x20 as the game's world map scenes' (1); each
        /// battle's what-it-shows its deploy prompt (SortieConfirm, its key), each event in a
        /// battle the battle's first scene's number at 4, as the game's battles'. Why not, or "".</summary>
        public string MakeEventRows(Span<byte> table, List<string> said, bool grown = false)
        {
            var rows = Nxd.Rows(table, out string why);
            if (rows == null)
                return why;
            // (1.9.0) The helper's copy with rows past 886 added (`grown`: EventRowsAdded) searched by key once their
            // keys skip a number; the game's found by their place.
            if (table[8] != 1 || table[9] != 1 || (grown ? table[10] > 1 : table[10] != 1) || rows.Count < SearchedSlots)
                return $"its header isn't the one the game's EventId has (bytes 8 to 10: {table[8]}, {table[9]}, "
                       + $"{table[10]}; {rows.Count} rows)";
            var at = new Dictionary<int, int>();
            foreach (var row in rows)
            {
                if (row.At + EventRowBytes > table.Length)
                    return "a row of it is cut short";
                at[row.Keys[0]] = row.At;
            }
            if (!at.TryGetValue(GameOpening, out int game))
                return $"it has no row for the game's opening {GameOpening}";
            var shows = table.Slice(game + EventRowShows, 8).ToArray();
            if (BinaryPrimitives.ReadInt32LittleEndian(shows) == 0)
                return $"the game's opening {GameOpening} shows nothing before it";
            foreach (var (opening, scene) in Openings)
            {
                if (!at.TryGetValue(opening, out int o) || !at.TryGetValue(scene, out int s))
                {
                    said.Add($"EventId has no row for event {opening} or {scene}: the world map may show nothing "
                             + "before it.");
                    continue;
                }
                shows.CopyTo(table.Slice(o + EventRowShows, 8));
                table[s + EventRowScene] = 1;
            }
            foreach (var (battle, prompt) in Fights)
            {
                if (!at.TryGetValue(battle, out int b))
                {
                    said.Add($"EventId has no row for event {battle}: the battle has no deploy prompt.");
                    continue;
                }
                BinaryPrimitives.WriteInt32LittleEndian(table.Slice(b + EventRowShows, 4), PromptUnion);
                BinaryPrimitives.WriteInt32LittleEndian(table.Slice(b + EventRowShows + 4, 4), prompt);
            }
            foreach (var (scene, first) in FightScenes)
                if (at.TryGetValue(scene, out int s))
                    BinaryPrimitives.WriteInt32LittleEndian(table.Slice(s + EventRowFirstScene, 4), first);
            return "";
        }

        /// <summary>(1.9.0) The quests' events numbered past the game's 886, which EventId has no rows for (its
        /// rows stop at 886), in order.</summary>
        public List<int> EventsPastGame()
        {
            var past = new List<int>();
            foreach (int ev in _names.Keys)
                if (ev > LastEvent)
                    past.Add(ev);
            past.Sort();
            return past;
        }

        /// <summary>(1.9.0) EventId's row for one of the quests' events past 886: as the game's plain events' (no
        /// union, Unknown4 -1, SeadStateParameterId 1), its two comments empty (each a distance from the row's start
        /// to a zero past its fields); MakeEventRows then gives it what the game's rows of its kind have.</summary>
        public static byte[] EventRow()
        {
            var row = new byte[EventRowBytes + 4];
            I32(row, 4, -1);
            I32(row, 8, EventRowBytes);
            I32(row, 0xC, EventRowBytes);
            I32(row, 0x18, 1);
            return row;
        }

        /// <summary>(1.9.0) The loaded EventId with a row for each of the quests' events past 886 (null when none
        /// is, or why it can't have them).</summary>
        public byte[]? EventRowsAdded(ReadOnlySpan<byte> table, out string why, out int added)
        {
            var past = EventsPastGame();
            added = 0;
            why = "";
            if (past.Count == 0)
                return null;
            var rows = new List<NewRow>();
            foreach (int ev in past)
                rows.Add(new NewRow(new[] { ev }, EventRow()));
            var output = Nxd.WithRows(table, rows, out why);
            if (output != null)
                added = rows.Count;
            return output;
        }

        public static string SheetName(int sheet) => sheet switch
        {
            WorldStarts => "EnhancedWorldEvent",
            Rules => "EnhancedBattleEvent",
            Scenes => "ScenarioId",
            Texts => "ScionFiles",
            EventRows => "EventId",
            EntryRows => "EntryNo",
            Prompts => "SortieConfirm",
            Objectives => "BattleObjective",
            Rumors => "Gossip",
            MapSheet => "Map",
            NameSheet => "PlaceName",
            _ => $"table {sheet}",
        };

        static int I32(ReadOnlySpan<byte> b, int at) => BinaryPrimitives.ReadInt32LittleEndian(b.Slice(at, 4));

        /// <summary>(1.30.0) Why a loaded table isn't one the framework changes, or "": PlaceName as the places' rows go
        /// in (Destinations.ShapeProblem), Map as map 116's row is named (NameArena, on a copy), any other as
        /// ShapeProblem has it.</summary>
        public static string TableShape(int sheet, ReadOnlySpan<byte> table)
        {
            if (sheet == NameSheet)
                return Destinations.ShapeProblem(NameSheet, table, new List<Destination>());
            if (sheet == MapSheet)
            {
                var copy = table.ToArray();
                return NameArena(copy);
            }
            return ShapeProblem(sheet, table);
        }

        /// <summary>Why a loaded table isn't the one its number should be, or "": its header (how
        /// many keys, how it is kept, its rows found by their keys) and each row's own shape, as
        /// the game's and WotL Restoration's are, so a game update that numbered or laid out the
        /// tables otherwise gets nothing added.</summary>
        public static string ShapeProblem(int sheet, ReadOnlySpan<byte> table)
        {
            var rows = Nxd.Rows(table, out string why);
            if (rows == null)
                return why;
            int keys = sheet == WorldStarts || sheet == Rules ? 3 : 1;
            // (1.12.0) BattleObjective, one of a language's tables, is kept as 2 (the setup, 0x3D3F3C, reads it as 1).
            int kept = keys == 3 ? 5 : sheet == Objectives || sheet == Rumors ? 2 : 1;
            // EntryNo, SortieConfirm and (1.12.0) BattleObjective are found by their rows' places (byte 10, 1) in the
            // game's and WotL Restoration's; a copy given rows at other keys is searched (0).
            bool placed = sheet == EntryRows || sheet == Prompts || sheet == Objectives || sheet == Rumors;
            if (table[8] != keys || table[9] != kept || (placed ? table[10] > 1 : table[10] != 0))
                return $"its header isn't the one the game's {SheetName(sheet)} has (bytes 8 to 10: {table[8]}, "
                       + $"{table[9]}, {table[10]})";
            foreach (var row in rows)
            {
                int at = row.At;
                switch (sheet)
                {
                    case EntryRows:
                    {
                        if (at + EntryRowBytes > table.Length)
                            return "a row of it is cut short";
                        foreach (int list in new[] { 0x0C, 0x14 })
                        {
                            int start = at + I32(table, at + list), count = I32(table, at + list + 4);
                            if (count < 0 || count > 16 || start < 0 || start + 4 * count > table.Length)
                                return $"its row {row.Keys[0]}'s lists aren't lists of its own";
                        }
                        break;
                    }
                    case Prompts:
                        if (at + PromptRowBytes > table.Length)
                            return "a row of it is cut short";
                        break;
                    case Objectives:
                        if (at + ObjectiveRowBytes > table.Length)
                            return "a row of it is cut short";
                        break;
                    case Rumors:
                        if (at + RumorRowBytes > table.Length)
                            return "a row of it is cut short";
                        break;
                    case WorldStarts:
                    {
                        if (at + 0x20 > table.Length)
                            return "a row of it is cut short";
                        int type = BinaryPrimitives.ReadInt16LittleEndian(table.Slice(at + 4, 2));
                        if (row.Keys[0] < 0 || row.Keys[0] >= QuestFile.Places || type < 0 || type > 43)
                            return $"its row {string.Join(", ", row.Keys)} isn't a world map step (type {type})";
                        break;
                    }
                    case Rules:
                    {
                        if (at + 0x28 > table.Length)
                            return "a row of it is cut short";
                        int type = BinaryPrimitives.ReadInt16LittleEndian(table.Slice(at + 4, 2));
                        if (type < 0 || type > 43)
                            return $"its row {string.Join(", ", row.Keys)} isn't a battle rules step (type {type})";
                        break;
                    }
                    case Scenes:
                    {
                        if (at + 0x10 > table.Length)
                            return "a row of it is cut short";
                        int list = at + I32(table, at + 4), count = I32(table, at + 8);
                        if (count < 0 || count > 64 || list < 0 || list + 4 * count > table.Length)
                            return $"its row {row.Keys[0]}'s events aren't a list of its own";
                        break;
                    }
                    case Texts:
                    {
                        if (at + 8 > table.Length)
                            return "a row of it is cut short";
                        int path = at + I32(table, at + 4);
                        if (path < 0 || path + 4 > table.Length || table[path] != (byte)'n' || table[path + 1] != (byte)'x'
                            || table[path + 2] != (byte)'d' || table[path + 3] != (byte)'/')
                            return $"its row {row.Keys[0]}'s path isn't under nxd/";
                        break;
                    }
                }
            }
            return "";
        }

        /// <summary>The loaded table with the quests' rows, or null and why; `said` gets a line for
        /// each quest whose rows can't go in (a key the loaded table already has, a place whose
        /// chains aren't numbered from 0), whose rows are left out.</summary>
        /// <summary>(1.21.0) Whose rows a table is given, as its line says them ("EntryNo: the mods' dungeons' 4 rows
        /// added."): the side quests', the mods' battle grounds' or dungeons' (their random battles' units, and a
        /// battle ground's deploy prompts), or both; each table's own, so a table only the quests give rows to says
        /// the side quests' alone.</summary>
        public string RowsWhose(int sheet)
        {
            bool quests = sheet != EntryRows && sheet != Prompts, grounds = false, dungeons = false;
            if (sheet == EntryRows)
                foreach (int battle in Units.Keys)
                {
                    if (_groundBattles.Contains(battle))
                        grounds = true;
                    else if (_dungeonBattles.Contains(battle))
                        dungeons = true;
                    else
                        quests = true;
                }
            else if (sheet == Prompts)
            {
                quests = PromptRowsNeeded.Count > 0;
                grounds = GroundPrompts.Count > 0;
            }
            if (!grounds && !dungeons)
                return "the side quests'";
            string theirs = grounds && dungeons ? "battle grounds' and dungeons'" : grounds ? "battle grounds'"
                            : "dungeons'";
            return quests ? $"the side quests' and the mods' {theirs}" : $"the mods' {theirs}";
        }

        public byte[]? WithRows(int sheet, ReadOnlySpan<byte> table, List<string> said, out string why, out int added)
        {
            added = 0;
            // (1.30.0) PlaceName gets map 116's name's row only while a quest or a mod's place plays there.
            if (sheet == NameSheet)
                return NamesArena ? ArenaNamed(table, said, out why, out added)
                                  : Nxd.WithRows(table, new List<NewRow>(), out why);
            why = ShapeProblem(sheet, table);
            if (why.Length > 0)
                return null;
            var rows = new List<NewRow>();
            switch (sheet)
            {
                case WorldStarts:
                {
                    var chains = new Dictionary<int, int>();
                    foreach (var start in Starts)
                    {
                        if (!chains.TryGetValue(start.Place, out int chain))
                        {
                            // The game runs a place's chains 0, 1, 2... as many as it has (0x343AF8):
                            // a new chain is numbered after them, so the story's come first.
                            chain = Nxd.SecondKeys(table, start.Place);
                            for (int c = 0; c < chain; c++)
                                if (Nxd.ThirdKeys(table, start.Place, c) == 0)
                                {
                                    chain = -1;
                                    break;
                                }
                            chains[start.Place] = chain;
                        }
                        if (chain < 0)
                        {
                            said.Add($"{start.Quest.Name} ({start.Quest.ModName})'s start at world map place "
                                     + $"{start.Place} is left out: the place's chains aren't numbered from 0.");
                            continue;
                        }
                        chains[start.Place] = chain + 1;
                        for (int step = 0; step < start.Steps.Count; step++)
                            rows.Add(new NewRow(new[] { start.Place, chain, step }, start.Steps[step]));
                    }
                    break;
                }
                case Rules:
                    foreach (var (key, (quest, chains)) in RuleSets)
                    {
                        if (Nxd.SecondKeys(table, key) > 0)
                        {
                            said.Add($"{quest.Name} ({quest.ModName})'s battle rules {key} are left out: another mod's "
                                     + "are there already.");
                            continue;
                        }
                        for (int chain = 0; chain < chains.Count; chain++)
                            for (int step = 0; step < chains[chain].Count; step++)
                                rows.Add(new NewRow(new[] { key, chain, step }, chains[chain][step]));
                    }
                    break;
                case EntryRows:
                    foreach (var battle in Units.Keys)
                    {
                        if (Nxd.Find(table, new[] { battle }) >= 0)
                            said.Add($"{BattleNameOf(battle)} is left out of EntryNo: battle {battle} is another mod's "
                                     + "already.");
                        else
                            rows.Add(new NewRow(new[] { battle },
                                                EntryRow(EntryPrompts.TryGetValue(battle, out int prompt) ? prompt : 0)));
                    }
                    break;
                case Prompts:
                {
                    // Each battle's deploy prompt is a copy of the game's battle prompt for its map
                    // (1507 at 0x10); (1.10.0) for a quest map's, of its Base's with the map its own; else of the
                    // first battle prompt with the map and no threat.
                    var game = new List<(int At, int Map)>();
                    foreach (var row in Nxd.Rows(table, out _)!)
                        if (I32(table, row.At + PromptKind) == BattlePrompt)
                            game.Add((row.At, I32(table, row.At + PromptMap)));
                    foreach (var (key, map, owner) in PromptRowsNeeded)
                    {
                        if (Nxd.Find(table, new[] { key }) >= 0)
                        {
                            said.Add($"{owner} has no deploy prompt: SortieConfirm {key} is another mod's already.");
                            continue;
                        }
                        int like = game.FindIndex(g => g.Map == map);
                        bool same = like >= 0, based = false;
                        if (!same && MapBases.TryGetValue(map, out int made))
                        {
                            like = game.FindIndex(g => g.Map == made);
                            based = like >= 0;
                        }
                        if (!same && !based && game.Count == 0)
                        {
                            said.Add($"{owner} has no deploy prompt: SortieConfirm has no battle's to copy.");
                            continue;
                        }
                        var copy = table.Slice(game[same || based ? like : 0].At, PromptRowBytes).ToArray();
                        if (based)
                            I32(copy, PromptMap, map);
                        else if (!same)
                        {
                            I32(copy, PromptMap, map);
                            I32(copy, 8, 0);
                            I32(copy, PromptThreat, -1);
                        }
                        rows.Add(new NewRow(new[] { key }, copy));
                    }
                    // (1.17.0) A battle ground's random battle's is a copy of one of the game's random battles' (a
                    // battle prompt the world map shows) for its map; for a quest map's, of its Base's with the map its
                    // own; else of the first random battle's with the map set.
                    var random = new List<(int At, int Map)>();
                    foreach (var row in Nxd.Rows(table, out _)!)
                        if (I32(table, row.At + PromptKind) == BattlePrompt && table[row.At + PromptShown] != 0)
                            random.Add((row.At, I32(table, row.At + PromptMap)));
                    foreach (var (key, map, owner) in GroundPrompts)
                    {
                        if (Nxd.Find(table, new[] { key }) >= 0)
                        {
                            said.Add($"{owner} has no deploy prompt: SortieConfirm {key} is another mod's already.");
                            continue;
                        }
                        int like = random.FindIndex(g => g.Map == map);
                        if (like < 0 && MapBases.TryGetValue(map, out int made))
                            like = random.FindIndex(g => g.Map == made);
                        if (like < 0 && random.Count == 0)
                        {
                            said.Add($"{owner} has no deploy prompt: SortieConfirm has no random battle's to copy.");
                            continue;
                        }
                        var copy = table.Slice(random[Math.Max(like, 0)].At, PromptRowBytes).ToArray();
                        I32(copy, PromptMap, map);
                        rows.Add(new NewRow(new[] { key }, copy));
                    }
                    break;
                }
                case Scenes:
                    foreach (var p in Events)
                        if (p.Scene >= 0)
                        {
                            if (Nxd.Find(table, new[] { p.Scene }) >= 0)
                                said.Add($"{p.Quest.Name} ({p.Quest.ModName})'s {p.Event.Name} has no words: scene "
                                         + $"{p.Scene} is another mod's already.");
                            else
                                rows.Add(new NewRow(new[] { p.Scene }, SceneRow(p.Number, p.Text)));
                        }
                    break;
                case Texts:
                    foreach (var p in Events)
                        if (p.Text >= 0)
                        {
                            if (Nxd.Find(table, new[] { p.Text }) >= 0)
                                said.Add($"{p.Quest.Name} ({p.Quest.ModName})'s {p.Event.Name} has no words: words "
                                         + $"file {p.Text} is another mod's already.");
                            else
                                rows.Add(new NewRow(new[] { p.Text }, TextRow(p.Event.Words)));
                        }
                    break;
                case Objectives:
                    // (1.12.0) Each battle's objective, in the language the game loads (its words as the quest gives
                    // them).
                    foreach (var (key, words, protects, owner) in ObjectiveRows)
                    {
                        if (Nxd.Find(table, new[] { key }) >= 0)
                            said.Add($"{owner} has no objective of its own: BattleObjective {key} is another mod's "
                                     + "already.");
                        else
                            rows.Add(new NewRow(new[] { key }, ObjectiveRow(words, protects)));
                    }
                    break;
                case Rumors:
                    // (1.15.0) Each rumor, in the language the game loads (its words as the quest gives them).
                    foreach (var r in RumorPlans)
                    {
                        if (Nxd.Find(table, new[] { r.Key }) >= 0)
                        {
                            r.Taken = true;
                            said.Add($"{r.Who}'s rumor {r.Rumor.Name} isn't told: Gossip {r.Key} is another mod's "
                                     + "already.");
                        }
                        else
                            rows.Add(new NewRow(new[] { r.Key }, RumorRow(r.Rumor.Title, r.Rumor.Text)));
                    }
                    break;
                default:
                    why = "it gets no rows";
                    return null;
            }
            var output = Nxd.WithRows(table, rows, out why);
            if (output != null)
                added = rows.Count;
            return output;
        }

        // --- the setup table ----------------------------------------------------

        /// <summary>The first slot the game's search ends at (the first record numbered 0), and how
        /// many slots it searches after it: where the quests' records go, one after another.</summary>
        public static int FirstEmpty(ReadOnlySpan<byte> table, int slots, out int free, int searchedSlots = SearchedSlots)
        {
            int searched = Math.Min(slots, searchedSlots);
            for (int slot = 0; slot < searched; slot++)
                if (BinaryPrimitives.ReadUInt16LittleEndian(table.Slice(slot * Table.RecordBytes, 2)) == 0)
                {
                    free = searched - slot;
                    return slot;
                }
            free = 0;
            return searched;
        }

        /// <summary>Writes the records into the slots from `first` (each all zero before); how many.</summary>
        public int WriteRecords(Span<byte> table, int first)
        {
            int written = 0;
            foreach (var record in Records)
            {
                int at = (first + written) * Table.RecordBytes;
                if (at + Table.RecordBytes > table.Length)
                    break;
                var slot = table.Slice(at, Table.RecordBytes);
                if (slot.IndexOfAnyExcept((byte)0) >= 0)
                    break;
                record.CopyTo(slot);
                written++;
            }
            return written;
        }

        // --- the scripts ------------------------------------------------------

        /// <summary>The game's script reader's output for one of the quests' events: a 4-byte size
        /// (the script's length plus 4, as the program writes it) and the script; null when the
        /// event isn't one of theirs.</summary>
        public byte[]? ScriptFor(int ev, int ramza = 0)
        {
            if (!Scripts.TryGetValue(ev, out var script))
                return null;
            var output = new byte[4 + script.Length];
            BinaryPrimitives.WriteInt32LittleEndian(output.AsSpan(0, 4), script.Length + 4);
            script.CopyTo(output, 4);
            // (1.30.0) The party's Ramza where its script names him (RamzaPlaces): his identity, 1 to 3.
            if (QuestFile.IsRamza(ramza) && RamzaPlaces.TryGetValue(ev, out var places))
                foreach (int at in places)
                    BinaryPrimitives.WriteUInt16LittleEndian(output.AsSpan(4 + at, 2), (ushort)ramza);
            return output;
        }

        /// <summary>(1.30.0) Whether an event's script names Ramza (its RamzaInScript).</summary>
        public bool NamesRamza(int ev) => RamzaPlaces.ContainsKey(ev);

        /// <summary>(1.30.0) The identity of the Ramza in the party (1 in chapter 1, 2 in chapters 2 and 3, 3 in chapter
        /// 4), as the world map's test of a character reads the party's units (PartyUnits of UnitBytes): the first unit
        /// (its second byte not 0xFF) whose first byte, its identity, is one of his; 0 when none is.</summary>
        public static int RamzaOf(ReadOnlySpan<byte> units)
        {
            for (int n = 0; n < PartyUnits && (n + 1) * UnitBytes <= units.Length; n++)
            {
                var unit = units.Slice(n * UnitBytes, UnitBytes);
                if (unit[1] != 0xFF && QuestFile.IsRamza(unit[0]))
                    return unit[0];
            }
            return 0;
        }

        /// <summary>(1.30.0) Ramza's chapters in words, by his identity, for the log.</summary>
        public static string RamzaChapter(int ramza) => ramza switch
        {
            1 => "chapter 1",
            2 => "chapters 2 and 3",
            3 => "chapter 4",
            _ => "no chapter",
        };

        /// <summary>(1.30.0) The loaded PlaceName with map 116's name (ArenaName at ArenaKey), as a quest map's Title is
        /// given one (Destinations.NameRowOf); its row there already (another's), left out, said.</summary>
        byte[]? ArenaNamed(ReadOnlySpan<byte> table, List<string> said, out string why, out int added)
        {
            added = 0;
            why = Destinations.ShapeProblem(NameSheet, table, new List<Destination>());
            if (why.Length > 0)
                return null;
            if (Nxd.Find(table, new[] { ArenaKey }) >= 0)
            {
                said.Add($"PlaceName's row {ArenaKey} for map {ArenaMap}'s name is left out: the table has one there "
                         + "already.");
                why = "its row of map 116's name is there already";
                return null;
            }
            var output = Nxd.WithRows(table, new List<NewRow> { new NewRow(new[] { ArenaKey },
                                                                         Destinations.NameRowOf(ArenaName)) }, out why);
            if (output != null)
                added = 1;
            return output;
        }

        /// <summary>The event a sector is, as the script reader counts: the sector over 5 (over 3
        /// when `mode` is 0), or -1 when it isn't one.</summary>
        public static int EventOfSector(uint sector, int mode)
        {
            uint by = mode != 0 ? 5u : 3u;
            return sector % by == 0 && sector / by <= EventRoom.LastEvent ? (int)(sector / by) : -1;
        }

        // --- the flags ----------------------------------------------------------

        public static bool IsFlag(int variable) => variable >= FlagBase && variable < FlagBase + FlagBits;

        public static int ReadFlag(ReadOnlySpan<byte> bank, int variable)
        {
            int bit = variable - FlagBase;
            return (bank[BankTail + (bit >> 3)] >> (bit & 7)) & 1;
        }

        public static void WriteFlag(Span<byte> bank, int variable, int value)
        {
            int bit = variable - FlagBase;
            int at = BankTail + (bit >> 3);
            bank[at] = (byte)((value & 1) != 0 ? bank[at] | (1 << (bit & 7)) : bank[at] & ~(1 << (bit & 7)));
        }

        // --- (1.13.0) the mark of the numbers a save was made with ------------------

        public static uint ReadMark(ReadOnlySpan<byte> bank) => BinaryPrimitives.ReadUInt32LittleEndian(bank.Slice(MarkAt, 4));

        /// <summary>(1.32.0) Whether a byte of the bank's tail holds quest flags: before WotL Restoration's items'
        /// counts or after them, before the mods' items' counts (ItemRoom.FlagFree's bytes; the mark's after those).</summary>
        public static bool IsFlagByte(int at)
            => at >= BankTail && at < ItemRoom.JobsMark && (at < ItemRoom.WotLTail || at >= ItemRoom.WotLTailEnd);

        /// <summary>Whether any quest flag is set (a save of a quest played). (1.32.0) Only the flags' bytes: WotL
        /// Restoration's items' counts and the mods' items' are no flags.</summary>
        public static bool AnyFlag(ReadOnlySpan<byte> bank)
        {
            for (int at = BankTail; at < MarkAt; at++)
                if (bank[at] != 0 && IsFlagByte(at))
                    return true;
            return false;
        }

        /// <summary>(1.32.0) Every quest flag cleared (the flags' bytes only).</summary>
        public static void ClearFlags(Span<byte> bank)
        {
            for (int at = BankTail; at < MarkAt; at++)
                if (IsFlagByte(at))
                    bank[at] = 0;
        }

        /// <summary>A quest flag set: the bank marked with the numbers' ID when it has no mark yet (a new game, or a
        /// save from before 1.13.0). (1.32.0) A save loaded is marked with them as it loads (Loaded).</summary>
        public static void Mark(Span<byte> bank, uint id)
        {
            if (id != 0 && ReadMark(bank) == 0)
                WriteMark(bank, id);
        }

        /// <summary>(1.32.0) The bank marked with an ID (0: no mark).</summary>
        public static void WriteMark(Span<byte> bank, uint id) => BinaryPrimitives.WriteUInt32LittleEndian(bank.Slice(MarkAt, 4), id);

        /// <summary>A save just loaded: what is said of its mark, null for nothing. (1.32.0, Zodi's choice of 4 November
        /// after test 67, whose battle never came: both saves he loaded held its Battle done, set long before by quests
        /// numbered before his numbers were freed) The side quest flags it can't really hold are cleared, said: those
        /// given or freed since its mark (a mark the numbers had before, Numbers.Marks), every one when it was made
        /// with other numbers (a mark they never had: freed before 1.32.0, lost from every copy, another computer's) or
        /// before saves were marked (flags and no mark: before 1.13.0); then it is marked with the numbers' own ID (one
        /// with no flag and no mark left unmarked). Until 1.32.0, the first kept its flags, the second was said and
        /// kept them, the third was marked with the numbers, unsaid. (1.35.0) Its bank alone: the mods' items it holds
        /// are looked at only in its counts (Loaded with its party).</summary>
        public static string? Loaded(Span<byte> bank, Numbers numbers) => Loaded(bank, Span<byte>.Empty, numbers, out _);

        /// <summary>(1.35.0, Zodi's word of 5 November: "a save made before you freed numbers could hand out a new item
        /// for free, the same kind of problem test 67's flags were"; his choices "Count and worn copies", "Keep their
        /// items" and "Clear them too") Loaded, with the save's party (`roster`: Places.Roster's units, or empty when it
        /// wasn't found): the mods' items it can't really hold taken out too, said in `items` (null for nothing): those
        /// given or freed since its mark, each one's count in its bag cleared and any unit wearing it given none
        /// (TakeOutItems); every one of them when it was made with other numbers; none when it has no mark (a save
        /// older than 1.35.0 that set no flag: its items kept, as an older save's are, and it is marked with the
        /// numbers' own ID so a free from now on takes them out).</summary>
        public static string? Loaded(Span<byte> bank, Span<byte> roster, Numbers numbers, out string? items)
        {
            items = null;
            uint id = numbers.Id;
            uint mark = ReadMark(bank);
            if (id == 0 || mark == id)
                return null;
            if (mark == 0)
            {
                // (1.35.0) Its mods' items kept, the save marked with these numbers from now on.
                bool held = AnyItem(bank, roster);
                string? flags = null;
                if (AnyFlag(bank))
                {
                    ClearFlags(bank);
                    flags = "the save loaded was made before side quest saves were marked (Mod Studio Framework 1.13.0), "
                            + "so its side quests' flags are cleared: each quest starts again in it.";
                }
                if (held)
                    WriteMark(bank, id);
                return flags;
            }
            var marks = numbers.Marks;
            int at = numbers.MarkIndex(mark);
            if (at < 0)
            {
                bool any = AnyFlag(bank);
                ClearFlags(bank);
                // (1.35.0, his choice "Clear them too") Every one of the mods' items in it taken out.
                var gone = TakeOutItems(bank, roster, null);
                WriteMark(bank, id);
                if (gone.Bag + gone.Worn > 0)
                    items = $"the save loaded was made with other side quest numbers (its mark {mark:X8}, these "
                            + $"numbers' {id:X8}), so the mods' items in it are taken out: {TakenWords(gone)}.";
                return !any ? null
                    : $"the save loaded was made with other side quest numbers (its mark {mark:X8}, these numbers' "
                      + $"{id:X8}), so its side quests' flags are cleared: each quest starts again in it. The numbers "
                      + "it was made with aren't the ones kept here: freed before Mod Studio Framework 1.32.0, lost "
                      + "from every place they were kept, or another computer's.";
            }
            // A mark the numbers had before: the flags given or freed since, each cleared where it is set.
            var given = new SortedSet<int>();
            var freed = new SortedSet<int>();
            var itemsSince = new SortedSet<int>();
            var itemsGiven = new SortedSet<int>();
            for (int n = at + 1; n < marks.Count; n++)
            {
                foreach (int bit in marks[n].Flags)
                    if (ClearBit(bank, bit))
                        given.Add(bit);
                foreach (int bit in marks[n].Freed)
                    if (ClearBit(bank, bit))
                        freed.Add(bit);
                // (1.35.0) The mods' items' numbers given or freed since.
                foreach (int item in marks[n].Items)
                {
                    itemsSince.Add(item);
                    itemsGiven.Add(item);
                }
                foreach (int item in marks[n].FreedItems)
                    itemsSince.Add(item);
            }
            var taken = TakeOutItems(bank, roster, itemsSince);
            WriteMark(bank, id);
            if (taken.Bag + taken.Worn > 0)
                items = ItemsLine(taken, itemsGiven, numbers);
            return given.Count == 0 && freed.Count == 0 ? null : ClearedLine(given, freed, numbers);
        }

        // --- (1.35.0) a save's mods' items -------------------------------------------------------------------------

        /// <summary>(1.35.0) The game's party as a save keeps it (Places.Roster, 0x11A7D10, which the game's load of a
        /// save fills from the save's + 0x518): 54 units of 0x258 bytes, a place with none when its byte 1 is 0xFF
        /// (the game's copy of a unit at 0x275B84 gives up on one so). What a unit wears is at + 0x0E: seven items of
        /// two bytes (its head, body, accessory, right hand's weapon and shield, left hand's weapon and shield: the
        /// game's copy of a unit at 0x276758 takes those 14 bytes), none 0xFF (the game's menu copy at 0x284BFF takes
        /// a hand of 0xFF for an empty one; fft_decomp's equipment_commit_loadout writes ITEM_ID_NONE, 255).</summary>
        public const int RosterUnits = 0x36, RosterUnitBytes = 0x258, RosterBytes = RosterUnits * RosterUnitBytes;
        public const int RosterEmpty = 1, RosterWorn = 0x0E, WornSlots = 7, NoItem = 0xFF;

        /// <summary>(1.35.0) What a save gave up of the mods' items: copies cleared from its bag, copies taken off its
        /// units, and the units that wore them, by their places in the party, and the items' numbers.</summary>
        public readonly struct Taken
        {
            public int Bag { get; }
            public int Worn { get; }
            public int Units { get; }
            public IReadOnlyList<int> Numbers { get; }

            public Taken(int bag, int worn, int units, IReadOnlyList<int> numbers)
            {
                Bag = bag;
                Worn = worn;
                Units = units;
                Numbers = numbers;
            }
        }

        static bool IsModItem(int number) => number >= ItemRoom.FirstItem && number <= ItemRoom.LastItem;

        /// <summary>(1.35.0) Whether a save holds any of the mods' items: a count in its bank (ItemRoom.CountAt) or a
        /// copy worn by a unit of its party (`roster`, empty for none looked at).</summary>
        public static bool AnyItem(ReadOnlySpan<byte> bank, ReadOnlySpan<byte> roster)
        {
            for (int n = ItemRoom.FirstItem; n <= ItemRoom.LastItem; n++)
                if (bank[ItemRoom.CountAt(n)] != 0)
                    return true;
            for (int unit = 0; unit + 1 <= RosterUnits && (unit + 1) * RosterUnitBytes <= roster.Length; unit++)
            {
                var u = roster.Slice(unit * RosterUnitBytes, RosterUnitBytes);
                if (u[RosterEmpty] == 0xFF)
                    continue;
                for (int slot = 0; slot < WornSlots; slot++)
                    if (IsModItem(BinaryPrimitives.ReadUInt16LittleEndian(u.Slice(RosterWorn + 2 * slot, 2))))
                        return true;
            }
            return false;
        }

        /// <summary>(1.35.0, his choice "Count and worn copies") The mods' items `numbers` (null: every one of them,
        /// ItemRoom.FirstItem to LastItem) taken out of a save: each one's count in its bank cleared and each copy a unit
        /// of its party wears given none (NoItem, as the game empties a place). What was taken, the items' numbers each
        /// once in order: none at all leaves the save as it was.</summary>
        public static Taken TakeOutItems(Span<byte> bank, Span<byte> roster, ICollection<int>? numbers)
        {
            bool Asked(int n) => IsModItem(n) && (numbers == null || numbers.Contains(n));
            int bag = 0, worn = 0, units = 0;
            var which = new SortedSet<int>();
            for (int n = ItemRoom.FirstItem; n <= ItemRoom.LastItem; n++)
            {
                int at = ItemRoom.CountAt(n);
                if (!Asked(n) || bank[at] == 0)
                    continue;
                bag += bank[at];
                bank[at] = 0;
                which.Add(n);
            }
            for (int unit = 0; unit + 1 <= RosterUnits && (unit + 1) * RosterUnitBytes <= roster.Length; unit++)
            {
                var u = roster.Slice(unit * RosterUnitBytes, RosterUnitBytes);
                if (u[RosterEmpty] == 0xFF)
                    continue;
                bool wore = false;
                for (int slot = 0; slot < WornSlots; slot++)
                {
                    var place = u.Slice(RosterWorn + 2 * slot, 2);
                    int item = BinaryPrimitives.ReadUInt16LittleEndian(place);
                    if (!Asked(item))
                        continue;
                    BinaryPrimitives.WriteUInt16LittleEndian(place, NoItem);
                    worn++;
                    wore = true;
                    which.Add(item);
                }
                if (wore)
                    units++;
            }
            return new Taken(bag, worn, units, new List<int>(which));
        }

        /// <summary>(1.35.0) What was taken, in words: "3 cleared from the bag and 1 taken off a unit".</summary>
        public static string TakenWords(Taken taken)
        {
            var parts = new List<string>();
            if (taken.Bag > 0)
                parts.Add($"{taken.Bag} cleared from the bag");
            if (taken.Worn > 0)
                parts.Add($"{taken.Worn} taken off {(taken.Units == 1 ? "a unit" : $"{taken.Units} units")}");
            return AndList(parts);
        }

        /// <summary>(1.35.0) What is said of the mods' items taken out of a save made before they were given or freed:
        /// "the save loaded was made before New Ring (item 321) was given, and held old items there: 1 cleared from the
        /// bag and 1 taken off a unit." An item given since (`given`) and named now is named, by its name past its mod
        /// in the numbers' key; any other was freed.</summary>
        public static string ItemsLine(Taken taken, ICollection<int> given, Numbers numbers)
        {
            var named = new List<string>();
            var freed = new List<string>();
            foreach (int n in taken.Numbers)
            {
                string? key = given.Contains(n) ? numbers.NameOf(Numbers.ItemsKind, n) : null;
                int slash = key == null ? -1 : key.IndexOf('/');
                if (key != null && slash > 0 && slash < key.Length - 1)
                    named.Add($"{key.Substring(slash + 1)} (item {n})");
                else
                    freed.Add(n.ToString());
            }
            string what = named.Count == 0 ? "" : $"{AndList(named)} {(named.Count == 1 ? "was" : "were")} given";
            if (freed.Count > 0)
                what += (what.Length > 0 ? " and " : "") + $"item{(freed.Count == 1 ? "" : "s")} {AndList(freed)} "
                        + $"{(freed.Count == 1 ? "was" : "were")} freed";
            return $"the save loaded was made before {what}, and held old items there: {TakenWords(taken)}.";
        }

        /// <summary>(1.32.0) A quest flag's bit cleared: whether it was set.</summary>
        static bool ClearBit(Span<byte> bank, int bit)
        {
            if (bit < 0 || bit >= FlagBits || ReadFlag(bank, FlagBase + bit) == 0)
                return false;
            WriteFlag(bank, FlagBase + bit, 0);
            return true;
        }

        /// <summary>(1.32.0) What is said of the flags cleared in a save made before they were given (`given`, each
        /// named by its quest and flag where a quest has it now) or freed (`freed`): "the save loaded was made before
        /// Test 68 Quest's Battle done (flag 4115) and Ending done (flag 4116) were given, and held old flags there:
        /// cleared, so that quest starts again in it."</summary>
        public static string ClearedLine(IEnumerable<int> given, IEnumerable<int> freed, Numbers numbers)
        {
            // Each quest's flags in their order, the quests in the order their first flag comes.
            var quests = new List<(string Quest, List<string> Flags)>();
            var unnamed = new List<int>();
            foreach (int bit in given)
            {
                string? key = numbers.NameOf(Numbers.FlagsKind, bit);
                int quest = key == null ? -1 : key.LastIndexOf('/');
                int mod = key == null ? -1 : key.IndexOf('/');
                if (key == null || quest <= mod || mod <= 0)
                {
                    unnamed.Add(bit);
                    continue;
                }
                string name = key.Substring(mod + 1, quest - mod - 1);
                string flag = $"{key.Substring(quest + 1)} (flag {FlagBase + bit})";
                int found = quests.FindIndex(q => q.Quest == name);
                if (found < 0)
                    quests.Add((name, new List<string> { flag }));
                else
                    quests[found].Flags.Add(flag);
            }
            var freedBits = new List<int>(freed);
            freedBits.AddRange(unnamed);
            freedBits.Sort();
            var parts = new List<string>();
            int flags = 0;
            foreach (var (quest, list) in quests)
            {
                parts.Add($"{quest}'s {AndList(list)}");
                flags += list.Count;
            }
            string what = quests.Count == 0 ? ""
                : $"{string.Join("; ", parts)} {(flags == 1 ? "was" : "were")} given";
            if (freedBits.Count > 0)
                what += (what.Length > 0 ? " and " : "")
                        + $"flag{(freedBits.Count == 1 ? "" : "s")} {AndList(freedBits.ConvertAll(b => (FlagBase + b).ToString()))} "
                        + $"{(freedBits.Count == 1 ? "was" : "were")} freed";
            string after = quests.Count == 0 ? "cleared in it."
                : quests.Count == 1 ? "cleared, so that quest starts again in it."
                : "cleared, so those quests start again in it.";
            return $"the save loaded was made before {what}, and held old flags there: {after}";
        }

        static string AndList(List<string> parts)
            => parts.Count < 2 ? string.Join("", parts)
               : string.Join(", ", parts.GetRange(0, parts.Count - 1)) + " and " + parts[parts.Count - 1];

        /// <summary>A game variable as the bank holds it: 0 to 127 words, then bits, then four-bit
        /// values (the program's 0x242984).</summary>
        public static int ReadGame(ReadOnlySpan<byte> bank, int variable)
        {
            if (variable < 0)
                return 0;
            if (variable < 0x80)
                return I32(bank, variable * 4);
            if (variable < 0x360)
                return (I32(bank, 0x200 + ((variable - 0x80) >> 5) * 4) >> ((variable - 0x80) & 31)) & 1;
            if (variable < 0x400)
                return (I32(bank, 0x25C + ((variable - 0x360) >> 3) * 4) >> (((variable - 0x360) & 7) * 4)) & 0xF;
            return 0;
        }

        /// <summary>What the game's variable functions make of a variable's value and an operand
        /// (commands 0xB0 to 0xBD in pairs: add, subtract, multiply, divide, remainder, and, or;
        /// 0xBE clears); null where they would stop (a division by zero).</summary>
        public static int? Operate(int op, int value, int operand)
        {
            if (op == 0xBE)
                return 0;
            if (op <= 0xB1)
                return value + operand;
            if (op <= 0xB3)
                return value - operand;
            if (op <= 0xB5)
                return value * operand;
            if (op <= 0xB7)
                return operand == 0 ? (int?)null : value / operand;
            if (op <= 0xB9)
                return operand == 0 ? (int?)null : value % operand;
            if (op <= 0xBB)
                return value & operand;
            if (op <= 0xBD)
                return value | operand;
            return value;
        }

        /// <summary>One variable command where a quest flag is its variable or its operand (odd
        /// commands read a second variable): what it does to the bank, and what the game's own
        /// function is to be given instead (null: nothing). A flag that is the command's variable
        /// is written here, as a bit, unless an event is being replayed (as the game's function
        /// refuses); a flag read into a game variable becomes the same command with the flag's
        /// value, the even command that takes a number.</summary>
        public static (int Op, int Dest, int Src)? Command(Span<byte> bank, int op, int dest, int src)
        {
            bool reads = op != 0xBE && (op & 1) == 1;
            if (IsFlag(dest))
            {
                int operand = op == 0xBE ? 0 : !reads ? src : IsFlag(src) ? ReadFlag(bank, src) : ReadGame(bank, src);
                var result = Operate(op, ReadFlag(bank, dest), operand);
                if (result != null && ReadGame(bank, ReplayVariable) == 0)
                    WriteFlag(bank, dest, result.Value);
                return null;
            }
            if (reads && IsFlag(src))
                return (op - 1, dest, ReadFlag(bank, src));
            return (op, dest, src);
        }
    }
}
