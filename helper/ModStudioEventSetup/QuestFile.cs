// Mod Studio Framework: reading a side quest's file. Part of The Ivalice
// Chronicles Mod Studio, GPL-3.0.
//
// A side quest (Zodi's goal of 26 October: "different modders can create
// hundreds of new side quests that users can have loaded and can play") is a
// folder of its own in a mod, `ModStudioQuests/<quest>/`, holding
// `quest.json`, its events' scripts and (1.2.0) its battles' units. The file
// names everything the quest adds (its events, its battles, its flags) and
// gives numbers only for the game's own things (maps, music, a world map
// place, the story's progress, a battle of the game's); the framework gives
// each name a number as the game starts (his rule: a modder never chooses a
// number). Mod Studio writes it (`mod_studio/side_quests.py` reads and
// writes the same file); what can't be used is left out and said. (1.8.0) A
// start's place may be one of its mod's own places by its name (the mod's
// `ModStudioPlaces`), numbered as the helper numbers the places. (1.10.0) An
// event's setup may give its Map as one of its mod's quest maps by its name
// (the mod's `ModStudioMaps`, MapFile.cs), numbered as the helper numbers them.
// (1.11.0) An event may say the game's event it was copied from (`From`, 1 to
// 886): the remaster plays some of a map's animations by the event playing
// (its doors among them), and MapAnimations.cs has the copy play them as that
// event's. (1.12.0) A battle event's Battle may say how it is won (its
// `WonWhen`: one of its units beaten, worn down to a share of its HP, or Ramza
// on a tile), a unit it is lost without (`Protect`) and the event once it is
// lost (`Lost`), and its objective's words (`Objective`), which its start
// event shows where its `ObjectiveInScript` says. (1.12.1) A unit those rules
// name can't be one the game takes from the player's own units (Load
// Formation): his test 39's Delita was an empty place at 0 HP. (1.25.0) A
// start whose place is one of the mod's own dungeons may wait at one of its
// floors (`Floor`): its event plays as that floor is chosen, in place of the
// floor's battle, while its conditions hold. (1.30.0) An event's
// `RamzaInScript` lists where its script names Ramza (a unit's two bytes
// holding 1, 2 or 3, his identity by chapter), which the framework gives the
// identity of the Ramza in the party as it hands the script over (Zodi's test
// 64, his choice "Framework finds him"). (1.31.0) An event's `Reward` (Zodi, 3
// November: "A reward as a quest ends"; his choice "Its last step only") is
// gil and items the framework gives once its script sets the reward's flag,
// never on a replay, as WotL Restoration gives the Tynar Rouge. A battle's
// `During` (Zodi's test 65: "there should be three events. One at start, one
// mid battle mostly for dialogue, and then the ending event"; his choice
// "Either, picked on the card") lists its scenes that play during it, each
// once a battle, as a unit's turn comes or as a unit's HP falls to a share.
// (1.33.0) A battle's `Names` (Zodi's choice of 5 November: "As a renamed
// unit") give its units their own names, each written into its unit as the
// game makes it (as the game keeps a renamed unit's), which the game copies
// when the unit joins the party. (1.53.0, Zodi's order of 13 November: "jobs in
// a quest's battle") A battle's `Jobs` put its units in jobs of its mod's own,
// each by the job's Name: the framework writes the number the job was given
// into the unit's job as it plans the quests.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;

namespace ModStudioEventSetup
{
    /// <summary>One condition of a quest's start: a game variable's value, a quest flag, or a
    /// character in the party.</summary>
    public sealed class Condition
    {
        /// <summary>"Variable", "Flag" or "Character".</summary>
        public string Kind { get; }
        public int Variable { get; }
        public string Flag { get; }
        /// <summary>"Is", "AtLeast" or "AtMost".</summary>
        public string Test { get; }
        public int Value { get; }

        public Condition(string kind, int variable, string flag, string test, int value)
        {
            Kind = kind;
            Variable = variable;
            Flag = flag;
            Test = test;
            Value = value;
        }
    }

    /// <summary>Where and when a quest starts: a world map place, its conditions, its event.</summary>
    public sealed class QuestStart
    {
        /// <summary>One of the game's places (0 to 46), or -1 for one of the mod's own (PlaceName).</summary>
        public int Place { get; }
        /// <summary>(1.8.0) One of the mod's own places by its name, or "" for one of the game's (Place).</summary>
        public string PlaceName { get; }
        public List<Condition> When { get; }
        public string Event { get; }
        /// <summary>(1.2.4) Whether its event stops a travel passing through its place, as the game's
        /// own events do ("Passing": "Stops"), or waits until the place is chosen ("Waits", the
        /// default: a side quest doesn't stop a travel on its way elsewhere).</summary>
        public bool StopsPassing { get; }
        /// <summary>(1.25.0) A floor of its place, one of the mod's own dungeons (PlaceName), by the floor's name: its
        /// event plays as that floor is chosen while its conditions hold, in place of the floor's battle (Zodi, 2
        /// November: Midlight's Deep's END plays its boss battle, with a scene as it starts and one once it is won,
        /// the first time only, its random battles after). "" for a start at its place itself.</summary>
        public string Floor { get; }

        public QuestStart(int place, List<Condition> when, string ev, bool stopsPassing = false, string placeName = "",
                          string floor = "")
        {
            Place = placeName.Length > 0 ? -1 : place;
            PlaceName = placeName;
            When = when;
            Event = ev;
            StopsPassing = stopsPassing;
            Floor = floor;
        }
    }

    /// <summary>One of a quest's events: its name, script, words and setup.</summary>
    public sealed class QuestEvent
    {
        public string Name { get; }
        public byte[] Script { get; }
        public string Words { get; }
        /// <summary>The setup's fields by their names (as EventSetup.json names them), but NextEvent.</summary>
        public Dictionary<string, int> Setup { get; }
        /// <summary>The quest's own event that follows, by name, or "".</summary>
        public string NextEvent { get; }
        /// <summary>Where a flag's number goes in the script's bytes (16 bits).</summary>
        public List<(int At, string Flag)> FlagsInScript { get; }
        /// <summary>The setup's fields that name one of the quest's battles (EnemyBattle, SceneUnits).</summary>
        public Dictionary<string, string> SetupBattles { get; } = new Dictionary<string, string>(StringComparer.Ordinal);
        /// <summary>(1.10.0) The setup's Map when it names one of the mod's quest maps (by its name), else "".</summary>
        public string SetupMap { get; set; } = "";
        /// <summary>(1.11.0) The game's event it was copied from (its From, 1 to 886), else 0: the map's animations the
        /// game plays for that event play for it (MapAnimations.cs).</summary>
        public int From { get; set; }
        /// <summary>(1.12.0) Where its battle's objective goes in its script (its ObjectiveInScript): each the byte after
        /// an instruction 0x78 (DisplayConditions), which shows objective (the byte less 8) in the game's objective
        /// box. A battle's start event only.</summary>
        public List<int> ObjectiveInScript { get; set; } = new List<int>();
        /// <summary>(1.30.0) Where its script names Ramza (its RamzaInScript): each a unit's two bytes holding one of his
        /// identities (1 in chapter 1, 2 in chapters 2 and 3, 3 in chapter 4), given the party's Ramza's as the script is
        /// handed to the game (Framework.ScriptFor).</summary>
        public List<int> RamzaInScript { get; set; } = new List<int>();
        /// <summary>(1.31.0) Its reward (its Reward), else null: given once its script sets the reward's flag.</summary>
        public QuestReward? Reward { get; set; }
        /// <summary>When the event is a battle: what it is (else null). A battle's script is the
        /// framework's, as every battle of the game starts with the same three instructions.</summary>
        public QuestFight? Battle { get; }

        public QuestEvent(string name, byte[] script, string words, Dictionary<string, int> setup, string next,
                          List<(int, string)> flags, QuestFight? battle = null)
        {
            Name = name;
            Script = script;
            Words = words;
            Setup = setup;
            NextEvent = next;
            FlagsInScript = flags;
            Battle = battle;
        }
    }

    /// <summary>(1.31.0, Zodi's ask of 3 November: "A reward as a quest ends (In WotL Restoration this is done after
    /// Agrias birthday event and it rewards the player the Tynar Rouge)"; his choice "Its last step only") What an event
    /// gives as its script sets its Flag (one of the quest's flags): Gil to the war funds and Items to the bag, each an
    /// item of the game's by its number (Item) or one of the mod's own by its name (Own), and how many (Count). The
    /// framework gives it as the flag goes from 0 to 1, which the game refuses while a scene is replayed; a unit joining
    /// is the scene's own (the game's CallFunction 1, its unit marked to join).</summary>
    public sealed class QuestReward
    {
        public string Flag { get; }
        public int Gil { get; }
        public List<(int Item, string Own, int Count)> Items { get; }

        public QuestReward(string flag, int gil, List<(int, string, int)> items)
        {
            Flag = flag;
            Gil = gil;
            Items = items;
        }
    }

    /// <summary>A battle event: whose units it fights (one of the quest's battles by name, or
    /// one of the game's by its number), and the quest's events that play in it, as the game's
    /// battles' do: one as it starts (or none), one once it is won; (1.12.0) how it is won, a unit
    /// it is lost without and the event once it is lost, and the objective its start event shows.</summary>
    public sealed class QuestFight
    {
        public string Units { get; }
        public int GameUnits { get; }
        public string Start { get; }
        public string Won { get; }
        /// <summary>(1.12.0) How it is won (its WonWhen): "Enemies" (every enemy beaten, the default), "Beaten" (its
        /// unit WonUnit beaten), "WornDown" (its unit WonUnit's HP down to WonShare percent of its most) or
        /// "OnTile" (Ramza on the tile TileX, TileY, its upper level TileUpper; or every enemy beaten).</summary>
        public string WonBy { get; init; } = Enemies;
        /// <summary>(1.12.0) Its unit, 1 to 16, whose fall (or HP) wins it, else 0.</summary>
        public int WonUnit { get; init; }
        public int WonShare { get; init; }
        public int TileX { get; init; }
        public int TileY { get; init; }
        public int TileUpper { get; init; }
        /// <summary>(1.12.0) Its unit, 1 to 16, it is lost without (its Protect), else 0; and its event once it is lost
        /// (its Lost), after which the game starts over, as its own battles' lost scenes.</summary>
        public int Protect { get; init; }
        public string Lost { get; init; } = "";
        /// <summary>(1.12.0) Its objective's words, shown in the game's objective box by its start event (the event's
        /// ObjectiveInScript), else "".</summary>
        public string Objective { get; init; } = "";
        /// <summary>(1.14.0) Its own deploy areas (its Deploy: one or two), where the player's units start, in place of
        /// its setup's DeployArea1 and DeployArea2; none, its setup's.</summary>
        public List<DeployArea> Deploy { get; init; } = new List<DeployArea>();
        /// <summary>(1.31.0, Zodi's test 65; his choice "Either, picked on the card") Its scenes during the battle (its
        /// During), in their order: each plays once a battle, as its unit's turn comes (Turn) or as its unit's HP falls to
        /// Share percent of its most (Hp; 0, beaten); its unit Ramza (0) or one of its own, 1 to 16.</summary>
        public List<QuestDuring> During { get; init; } = new List<QuestDuring>();

        public const string Enemies = "Enemies", Beaten = "Beaten", WornDown = "WornDown", OnTile = "OnTile";
        public const string Turn = "Turn", Hp = "Hp";

        public QuestFight(string units, int gameUnits, string start, string won)
        {
            Units = units;
            GameUnits = gameUnits;
            Start = start;
            Won = won;
        }
    }

    /// <summary>(1.31.0) One of a battle's scenes during it: the event, when it plays (QuestFight.Turn or Hp), its unit
    /// (0 Ramza, else one of the battle's own, 1 to 16) and, for Hp, the share of its most its HP falls to (0 to 99).</summary>
    public sealed class QuestDuring
    {
        public string Event { get; }
        public string When { get; }
        public int Unit { get; }
        public int Share { get; }

        public QuestDuring(string ev, string when, int unit, int share)
        {
            Event = ev;
            When = when;
            Unit = unit;
            Share = share;
        }
    }

    /// <summary>A quest's own battle's units: 16 units of 40 bytes, as the game's battle files
    /// hold a battle (ENTD). (1.33.0, Zodi's choice of 5 November: "As a renamed unit") Its units' own names, by their
    /// place in the file (0 to 15). (1.53.0) Its units' jobs of its mod's own, by their place in the file and the job's
    /// Name.</summary>
    public sealed class QuestBattle
    {
        public string Name { get; }
        public byte[] Units { get; }
        public SortedDictionary<int, string> Names { get; }
        public SortedDictionary<int, string> Jobs { get; }
        /// <summary>(2.0.0, Zodi's first point of 16 November 2026: items past 255 in "modders new Battles") Its units'
        /// items past the 255 a byte of its file holds, by their place in the file: each of the five places a unit
        /// wears an item (BattleFile.Places), an item by its number or its mod's own item's Name, or none.</summary>
        public SortedDictionary<int, BattleFile.ItemRef?[]> Items { get; }

        public QuestBattle(string name, byte[] units, SortedDictionary<int, string>? names = null,
                           SortedDictionary<int, string>? jobs = null,
                           SortedDictionary<int, BattleFile.ItemRef?[]>? items = null)
        {
            Name = name;
            Units = units;
            Names = names ?? new SortedDictionary<int, string>();
            Jobs = jobs ?? new SortedDictionary<int, string>();
            Items = items ?? new SortedDictionary<int, BattleFile.ItemRef?[]>();
        }
    }

    /// <summary>(1.15.0) One of a quest's tavern rumors (Zodi's list, his third): its title and words, the towns whose
    /// taverns tell it (their world map places, 0 to 14; none named: every tavern), when it is told (conditions as a
    /// start's), and the quest's flag set once it is read, which a start may wait for.</summary>
    public sealed class QuestRumor
    {
        public string Name { get; }
        public string Title { get; }
        public string Text { get; }
        public List<int> Towns { get; }
        /// <summary>(1.18.0) The mod's own towns whose taverns tell it too, by their names (a town with a Menu).</summary>
        public List<string> TownNames { get; }
        public List<Condition> When { get; }
        public string Read { get; }

        public QuestRumor(string name, string title, string text, List<int> towns, List<Condition> when, string read,
                          List<string>? townNames = null)
        {
            Name = name;
            Title = title;
            Text = text;
            Towns = towns;
            TownNames = townNames ?? new List<string>();
            When = when;
            Read = read;
        }

        /// <summary>(1.18.0) Told in every tavern (it names no town).</summary>
        public bool EveryTavern => Towns.Count == 0 && TownNames.Count == 0;
    }

    /// <summary>A side quest, as its mod gives it.</summary>
    public sealed class Quest
    {
        /// <summary>Its mod's id (Reloaded-II keeps them apart) and name (for the log).</summary>
        public string ModId { get; }
        public string ModName { get; }
        /// <summary>Its folder's name in its mod: with the mod's id, what names it for good.</summary>
        public string Folder { get; }
        public string Name { get; }
        public List<string> Flags { get; }
        public List<QuestEvent> Events { get; }
        public List<QuestStart> Starts { get; }
        public List<QuestBattle> Battles { get; }
        /// <summary>(1.2.5) Its marker's color on the world map, "#RRGGBB", or "" for none (Zodi, 26
        /// October: "there should be a quest marker for every quest if the modders choses to have it,
        /// the marker should be a different hue that they can pick").</summary>
        public string Marker { get; }
        /// <summary>(1.15.0) Its tavern rumors.</summary>
        public List<QuestRumor> Rumors { get; }

        public Quest(string modId, string modName, string folder, string name, List<string> flags,
                     List<QuestEvent> events, List<QuestStart> starts, List<QuestBattle>? battles = null,
                     string marker = "", List<QuestRumor>? rumors = null)
        {
            ModId = modId;
            ModName = modName;
            Folder = folder;
            Name = name;
            Flags = flags;
            Events = events;
            Starts = starts;
            Battles = battles ?? new List<QuestBattle>();
            Marker = marker;
            Rumors = rumors ?? new List<QuestRumor>();
        }

        /// <summary>What names it in the framework's file: its mod and its folder.</summary>
        public string Key => $"{ModId}/{Folder}";

        public QuestEvent? EventNamed(string name)
        {
            foreach (var ev in Events)
                if (string.Equals(ev.Name, name, StringComparison.Ordinal))
                    return ev;
            return null;
        }

        /// <summary>The battle event an event plays in (as its start, its won scene or, 1.12.0, its lost scene), or
        /// null.</summary>
        public QuestEvent? FightOf(string name)
        {
            foreach (var ev in Events)
                if (ev.Battle != null && (ev.Battle.Start == name || ev.Battle.Won == name
                                          || (ev.Battle.Lost.Length > 0 && ev.Battle.Lost == name)
                                          || ev.Battle.During.Exists(d => d.Event == name)))
                    return ev;
            return null;
        }

    }

    public static class QuestFile
    {
        /// <summary>The folder of a mod that holds its side quests, one folder each.</summary>
        public const string Folder = "ModStudioQuests";
        public const string Name = "quest.json";
        public const string Format = "Mod Studio side quest";
        public const int Version = 1;
        /// <summary>The world map's places (the game's EnhancedWorldEvent keys 0 to 46).</summary>
        public const int Places = 47;
        /// <summary>The most a script may be: the game reads it into 10,240 bytes after a 4-byte size
        /// (its event loader, 0x2340A4 in Zodi's program, with 0x2800).</summary>
        public const int MostScript = 0x2800 - 4;
        /// <summary>The most conditions a start has: the world map writes a place's chain into 256
        /// words (0x343AF8), three a condition and three for the event it loads.</summary>
        public const int MostConditions = 16;
        /// <summary>The setup's fields a quest may give (EventSetup.json's names); NextEvent names
        /// the quest's own event, and battle rules are the framework's to give.</summary>
        static readonly string[] SetupFields =
        {
            "Map", "Weather", "Arrangement", "Night", "Music1", "Music2", "EnemyBattle", "DeployArea1",
            "DeployArea2", "Portrait", "PortraitUnit", "SceneUnits", "RamzaRequired", "AfterEvent",
        };
        /// <summary>The setup's fields that may name one of the quest's battles instead of the game's.</summary>
        static readonly string[] BattleFields = { "EnemyBattle", "SceneUnits" };
        /// <summary>A battle's units: 16 units of 40 bytes (the game's ENTD battles).</summary>
        public const int BattleBytes = 640;
        /// <summary>The game's battles a quest may fight by number: the program reads a setup
        /// record's battle as a signed 16-bit number.</summary>
        public const int MostGameBattle = 0x7FFF;
        /// <summary>(1.10.0) The game's maps a quest's setup may give by number: 0 to 127 (past them, a quest map's,
        /// by its name).</summary>
        public const int MostGameMap = 127;
        /// <summary>(1.11.0) The game's events an event may say it was copied from (its From).</summary>
        public const int MostGameEvent = 886;
        /// <summary>(1.12.0) A battle's units (16, of 40 bytes, the sprite set first: 0 an empty place): where a unit's
        /// ID and presence are (its unit ID at 32; at 24, Always Present 0x80 and Randomly Present 0x40), the most
        /// percent of a unit's HP a WornDown gives, a tile's most x and y, and the most characters an objective's words
        /// have.</summary>
        public const int Units = 16, UnitBytes = 40, UnitIdAt = 32, PresenceAt = 24, PresenceMask = 0xC0,
                         AlwaysPresent = 0x80, MostShare = 99, MostTile = 255, MostObjective = 64;
        /// <summary>(1.53.0) Where a unit's job is in its 40 bytes (FFTPatcher's EventUnit's Job), which a battle's Jobs
        /// write.</summary>
        public const int MainJobAt = 10;
        /// <summary>(1.15.0) A rumor's title (as an objective's words, on one line) and words (line breaks between
        /// paragraphs, as the game's own), at the most; the towns whose taverns tell rumors (the world map's places 0 to
        /// 14, as the program's masks of the game's own rumors name them).</summary>
        public const int MostRumorTitle = 64, MostRumorText = 3000, Towns = 15;
        /// <summary>(1.12.1) A unit's first flags (byte 1) and Load Formation among them (0x08): the game fills such a
        /// unit from the player's own units as the battle starts, and a side quest's battle that names it in its rules
        /// found an empty place there at 0 HP (Delita in Gariland's battle, his test 39).</summary>
        public const int FlagsAt = 1, LoadFormation = 0x08;
        /// <summary>(1.12.0) DisplayConditions, the instruction whose byte after it ObjectiveInScript names.</summary>
        public const byte DisplayConditions = 0x78;
        /// <summary>(1.30.0) Ramza's character identities (fft_decomp's unit_identity.h): 1 in chapter 1, 2 in chapters 2
        /// and 3, 3 in chapter 4. The game's scenes name him by their chapter's, a deployed Ramza keeps it as his unit
        /// ID, and a party member's first byte is its identity: what a quest's RamzaInScript places hold.</summary>
        public const int FirstRamza = 1, LastRamza = 3;
        /// <summary>(1.31.0) A reward's most gil (the war funds' own most: the game's add of them, 0x284684, stops them
        /// at 99,999,999), most items, and most of one item (the bag holds 99 of an item); the variable commands that set
        /// a reward's flag (0xB0 to 0xBE, add to clear: fft_decomp's script_instruction.h).</summary>
        public const int MostGil = 99999999, MostRewardItems = 8, MostOfAnItem = 99;
        /// <summary>(1.31.0) The most gil as words say it, whatever the computer's own way of writing numbers.</summary>
        public const string MostGilWords = "99,999,999";
        public const byte FirstVariableCommand = 0xB0, LastVariableCommand = 0xBE;
        /// <summary>(1.31.0) A battle's scenes during it at the most, and the variable each one sets as it ends, in their
        /// order, which its rules test so that it plays once a battle: the scenario's own variables the game's battles
        /// guard their scenes with (127 in 80 of its rules, 126 in 92, 125 in 126, 129 in 38), which the game zeroes
        /// each time a battle loads (fft_decomp's EVENT_SCRIPT_VAR_SCENARIO_LOCAL_FIRST, 0x70 to 0x8F) and never
        /// refuses a write to; and the most rules a battle has (the game runs 16, 0x2391C4).</summary>
        public const int MostDuring = 4, MostRules = 16, MostShareDuring = 99;
        public static readonly int[] Guards = { 127, 126, 125, 129 };

        public static bool IsRamza(int identity) => identity >= FirstRamza && identity <= LastRamza;

        /// <summary>Every quest of a mod, in its folders' order; what can't be used goes in problems. (1.8.0)
        /// `placeNames`: the mod's own places' names, which a start may name; (1.10.0) `mapNames` its quest maps',
        /// which an event's setup may name.</summary>
        public static List<Quest> ReadMod(string modId, string modName, string modFolder, List<string> problems,
                                          ICollection<string>? placeNames = null, ICollection<string>? mapNames = null)
        {
            var quests = new List<Quest>();
            string root = Path.Combine(modFolder, Folder);
            if (!Directory.Exists(root))
                return quests;
            var folders = new List<string>(Directory.GetDirectories(root));
            folders.Sort(StringComparer.Ordinal);
            foreach (var folder in folders)
            {
                string file = Path.Combine(folder, Name);
                if (!File.Exists(file))
                    continue;
                string folderName = Path.GetFileName(folder);
                var said = new List<string>();
                Quest? quest = null;
                try
                {
                    quest = Read(modId, modName, folderName, File.ReadAllText(file),
                                 name => File.ReadAllBytes(Path.Combine(folder, name)), said, placeNames, mapNames);
                }
                catch (Exception e) when (e is not OutOfMemoryException)
                {
                    said.Add($"it can't be read ({e.Message})");
                }
                foreach (var s in said)
                    problems.Add($"{modName}'s quest {folderName}: {s}");
                if (quest != null)
                    quests.Add(quest);
            }
            return quests;
        }

        /// <summary>The event numbers a mod ships scripts for (FFTIVC/data/*/script/*/eventNNN.e, the
        /// mod loader's paths), added to `numbers`: never given to a quest.</summary>
        public static void ScriptNumbers(string modFolder, ISet<int> numbers)
        {
            string data = Path.Combine(modFolder, "FFTIVC", "data");
            if (!Directory.Exists(data))
                return;
            foreach (var look in Directory.GetDirectories(data))
            {
                string scripts = Path.Combine(look, "script");
                if (!Directory.Exists(scripts))
                    continue;
                foreach (var kind in Directory.GetDirectories(scripts))
                    foreach (var file in Directory.GetFiles(kind))
                    {
                        string name = Path.GetFileName(file);
                        if (name.Length > 7 && name.StartsWith("event", StringComparison.OrdinalIgnoreCase)
                            && name.EndsWith(".e", StringComparison.OrdinalIgnoreCase)
                            && int.TryParse(name.AsSpan(5, name.Length - 7), System.Globalization.NumberStyles.None,
                                            System.Globalization.CultureInfo.InvariantCulture, out int n))
                            numbers.Add(n);
                    }
            }
        }

        /// <summary>(1.31.0) A field as the file gives it, or "none".</summary>
        static string Raw(JsonElement e, string name) => Has(e, name, out var value) ? value.GetRawText() : "none";

        static string Text(JsonElement e, string name)
        {
            foreach (var p in e.EnumerateObject())
                if (string.Equals(p.Name, name, StringComparison.OrdinalIgnoreCase) && p.Value.ValueKind == JsonValueKind.String)
                    return p.Value.GetString() ?? "";
            return "";
        }

        static bool Number(JsonElement e, string name, out int value)
        {
            value = 0;
            foreach (var p in e.EnumerateObject())
                if (string.Equals(p.Name, name, StringComparison.OrdinalIgnoreCase) && p.Value.ValueKind == JsonValueKind.Number)
                    return p.Value.TryGetInt32(out value);
            return false;
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

        /// <summary>(1.10.0) What a file is told that holds half a surrogate pair alone (a \u escape), after "its file ".
        /// </summary>
        public const string BrokenTextSaid = "has a text that isn't Unicode text (half of a surrogate pair alone)";

        /// <summary>(1.10.0) Whether a text in `e` (a field's name or a value, at any depth) holds half a surrogate pair
        /// alone, which System.Text.Json can't read as text: such a file is refused whole, before anything in it is
        /// read (mod_studio/helper_json.py says the same of it).</summary>
        public static bool BrokenText(JsonElement e)
        {
            switch (e.ValueKind)
            {
                case JsonValueKind.Object:
                    foreach (var p in e.EnumerateObject())
                    {
                        try
                        {
                            _ = p.Name;
                        }
                        catch (InvalidOperationException)
                        {
                            return true;
                        }
                        if (BrokenText(p.Value))
                            return true;
                    }
                    return false;
                case JsonValueKind.Array:
                    foreach (var item in e.EnumerateArray())
                        if (BrokenText(item))
                            return true;
                    return false;
                case JsonValueKind.String:
                    try
                    {
                        _ = e.GetString();
                        return false;
                    }
                    catch (InvalidOperationException)
                    {
                        return true;
                    }
                default:
                    return false;
            }
        }

        /// <summary>A name the quest gives: letters, digits, spaces, _ and -, 1 to 64 of them.</summary>
        public static bool GoodName(string name)
        {
            if (name.Length == 0 || name.Length > 64 || name.Trim() != name)
                return false;
            foreach (char c in name)
                if (!(char.IsLetterOrDigit(c) || c == ' ' || c == '_' || c == '-'))
                    return false;
            return true;
        }

        /// <summary>A quest from its file's text; null when it can't be used, why in problems.
        /// `script` reads one of its folder's files by name; (1.8.0) `placeNames` are the mod's own places' names,
        /// which a start may name; (1.10.0) `mapNames` its quest maps', which an event's setup may name.</summary>
        public static Quest? Read(string modId, string modName, string folder, string text, Func<string, byte[]> script,
                                  List<string> problems, ICollection<string>? placeNames = null,
                                  ICollection<string>? mapNames = null)
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
                var top = document.RootElement;
                if (top.ValueKind != JsonValueKind.Object)
                {
                    problems.Add($"its {Name} isn't a list of fields");
                    return null;
                }
                if (BrokenText(top))
                {
                    problems.Add($"its {Name} {BrokenTextSaid}");
                    return null;
                }
                if (Text(top, "Format") != Format || !Number(top, "Version", out int version) || version != Version)
                {
                    problems.Add($"its {Name} isn't a \"{Format}\" file of version {Version}");
                    return null;
                }
                string name = Text(top, "Name");
                if (name.Length == 0)
                    name = folder;
                int before = problems.Count;
                string marker = "";
                if (Has(top, "Marker", out var markerValue))
                {
                    string given = markerValue.ValueKind == JsonValueKind.String ? markerValue.GetString() ?? "" : "";
                    if (IsColor(given))
                        marker = given.ToUpperInvariant();
                    else
                        problems.Add($"its Marker is a color written #RRGGBB, not {markerValue.GetRawText()}");
                }
                var flags = new List<string>();
                if (Has(top, "Flags", out var flagList) && flagList.ValueKind == JsonValueKind.Array)
                    foreach (var f in flagList.EnumerateArray())
                    {
                        string flag = f.ValueKind == JsonValueKind.String ? f.GetString() ?? "" : "";
                        if (!GoodName(flag))
                            problems.Add($"a flag's name isn't one: {f.GetRawText()}");
                        else if (flags.Contains(flag))
                            problems.Add($"the flag {flag} is named twice");
                        else
                            flags.Add(flag);
                    }
                var battles = new List<QuestBattle>();
                if (Has(top, "Battles", out var battleList) && battleList.ValueKind == JsonValueKind.Array)
                    foreach (var b in battleList.EnumerateArray())
                    {
                        var battle = ReadBattle(b, script, problems);
                        if (battle == null)
                            continue;
                        if (battles.Exists(x => x.Name == battle.Name))
                            problems.Add($"the battle {battle.Name} is named twice");
                        else
                            battles.Add(battle);
                    }
                var events = new List<QuestEvent>();
                if (!Has(top, "Events", out var eventList) || eventList.ValueKind != JsonValueKind.Array)
                    problems.Add("it has no Events list");
                else
                    foreach (var e in eventList.EnumerateArray())
                    {
                        var ev = ReadEvent(e, flags, battles, script, problems, mapNames);
                        if (ev == null)
                            continue;
                        if (events.Exists(x => x.Name == ev.Name))
                            problems.Add($"the event {ev.Name} is named twice");
                        else
                            events.Add(ev);
                    }
                foreach (var ev in events)
                    if (ev.NextEvent.Length > 0 && !events.Exists(x => x.Name == ev.NextEvent))
                        problems.Add($"the event {ev.Name}'s next event {ev.NextEvent} isn't one of the quest's");
                FightsProblems(events, problems);
                UnitsProblems(events, battles, problems);
                // (1.31.0) A flag gives one reward.
                var rewarded = new Dictionary<string, string>(StringComparer.Ordinal);
                foreach (var ev in events)
                {
                    if (ev.Reward == null)
                        continue;
                    if (rewarded.TryGetValue(ev.Reward.Flag, out var first))
                    {
                        problems.Add($"the events {first} and {ev.Name} each give a reward with the flag {ev.Reward.Flag}: "
                                     + "a flag gives one");
                        ev.Reward = null;
                    }
                    else
                        rewarded[ev.Reward.Flag] = ev.Name;
                }
                var starts = new List<QuestStart>();
                if (Has(top, "Starts", out var startList) && startList.ValueKind == JsonValueKind.Array)
                    foreach (var s in startList.EnumerateArray())
                    {
                        var start = ReadStart(s, flags, events, problems, placeNames);
                        if (start != null)
                            starts.Add(start);
                    }
                // (1.15.0) Its tavern rumors.
                var rumors = new List<QuestRumor>();
                if (Has(top, "Rumors", out var rumorList))
                {
                    if (rumorList.ValueKind != JsonValueKind.Array)
                        problems.Add("its Rumors aren't a list");
                    else
                        foreach (var r in rumorList.EnumerateArray())
                        {
                            var rumor = ReadRumor(r, flags, problems, placeNames);
                            if (rumor == null)
                                continue;
                            if (rumors.Exists(x => x.Name == rumor.Name))
                                problems.Add($"the rumor {rumor.Name} is named twice");
                            else
                                rumors.Add(rumor);
                        }
                }
                if (problems.Count > before)
                    return null;
                if (events.Count == 0)
                {
                    problems.Add("it has no events");
                    return null;
                }
                return new Quest(modId, modName, folder, name, flags, events, starts, battles, marker, rumors);
            }
        }

        /// <summary>(1.2.5) A color as a quest's Marker gives it: # and six hex digits, red, green, blue.</summary>
        public static bool IsColor(string text)
        {
            if (text.Length != 7 || text[0] != '#')
                return false;
            for (int n = 1; n < 7; n++)
                if (!Uri.IsHexDigit(text[n]))
                    return false;
            return true;
        }

        /// <summary>(1.2.5) A Marker's color as the game's nodes hold one: bytes R, G, B, A in memory
        /// order (a little-endian number R | G &lt;&lt; 8 | B &lt;&lt; 16 | A &lt;&lt; 24), opaque.</summary>
        public static uint Rgba(string color)
        {
            uint rgb = Convert.ToUInt32(color.Substring(1), 16);
            return (rgb >> 16) | (rgb & 0xFF00) | ((rgb & 0xFF) << 16) | 0xFF000000u;
        }

        /// <summary>A file of the quest's folder by name, or null and why in problems.</summary>
        static byte[]? FileOf(string what, string file, Func<string, byte[]> read, List<string> problems)
        {
            if (file.Length == 0 || file.Contains("..") || Path.IsPathRooted(file))
            {
                problems.Add($"{what} names no file in its folder");
                return null;
            }
            try
            {
                return read(file);
            }
            catch (Exception ex) when (ex is IOException || ex is UnauthorizedAccessException)
            {
                problems.Add($"{what}'s file {file} can't be read ({ex.Message})");
                return null;
            }
        }

        static QuestBattle? ReadBattle(JsonElement b, Func<string, byte[]> read, List<string> problems)
        {
            string name = b.ValueKind == JsonValueKind.Object ? Text(b, "Name") : "";
            if (!GoodName(name))
            {
                problems.Add($"a battle's name isn't one: {b.GetRawText()}");
                return null;
            }
            var units = FileOf($"the battle {name}", Text(b, "Units"), read, problems);
            if (units == null)
                return null;
            if (units.Length != BattleBytes)
            {
                problems.Add($"the battle {name}'s units are {units.Length} bytes, not {BattleBytes} (16 units as the "
                             + "game's battles hold them)");
                return null;
            }
            // (1.33.0) Its units' own names: each a unit of its 16 (1 to 16) and a name, a unit named once.
            var names = new SortedDictionary<int, string>();
            if (Has(b, "Names", out var listed))
            {
                if (listed.ValueKind != JsonValueKind.Array)
                {
                    problems.Add($"the battle {name}'s Names isn't a list");
                    return null;
                }
                int n = 0;
                foreach (var entry in listed.EnumerateArray())
                {
                    n++;
                    if (entry.ValueKind != JsonValueKind.Object || !Number(entry, "Unit", out int unit) || unit < 1
                        || unit > Units)
                    {
                        problems.Add($"the battle {name}'s own name {n} names no unit: its Unit is 1 to {Units}");
                        return null;
                    }
                    string? text = Has(entry, "Name", out var value) && value.ValueKind == JsonValueKind.String
                        ? value.GetString() : null;
                    if (text == null || !GoodOwnName(text))
                    {
                        problems.Add($"the battle {name}'s unit {unit}'s own name isn't one: 1 to {MostOwnName} "
                                     + "characters, none a control character, no space at either end");
                        return null;
                    }
                    if (names.ContainsKey(unit - 1))
                    {
                        problems.Add($"the battle {name} gives unit {unit} two own names");
                        return null;
                    }
                    names[unit - 1] = text;
                }
            }
            // (1.53.0, Zodi's order of 13 November: "jobs in a quest's battle") Its units' jobs of its mod's own: each a unit
            // of its 16 (1 to 16) and the Name of one of its mod's jobs, a unit given one job. Whether its mod gives that job
            // is known as the quests are planned (Framework.Plan): where it doesn't, the unit keeps its file's job.
            var jobs = new SortedDictionary<int, string>();
            if (Has(b, "Jobs", out var jobList))
            {
                if (jobList.ValueKind != JsonValueKind.Array)
                {
                    problems.Add($"the battle {name}'s Jobs isn't a list");
                    return null;
                }
                int n = 0;
                foreach (var entry in jobList.EnumerateArray())
                {
                    n++;
                    if (entry.ValueKind != JsonValueKind.Object || !Number(entry, "Unit", out int unit) || unit < 1
                        || unit > Units)
                    {
                        problems.Add($"the battle {name}'s job {n} names no unit: its Unit is 1 to {Units}");
                        return null;
                    }
                    string? job = Has(entry, "Job", out var value) && value.ValueKind == JsonValueKind.String
                        ? value.GetString() : null;
                    if (job == null || !JobFile.GoodJobName(job))
                    {
                        problems.Add($"the battle {name}'s unit {unit}'s Job isn't a job's Name: 1 to {JobFile.NameMost} "
                                     + "characters, none a control character");
                        return null;
                    }
                    if (jobs.ContainsKey(unit - 1))
                    {
                        problems.Add($"the battle {name} gives unit {unit} two jobs");
                        return null;
                    }
                    jobs[unit - 1] = job;
                }
            }
            // (2.0.0) Its units' items past 255: each a unit of its 16 (1 to 16) and, for any of the five places a unit
            // wears an item, an item past the 255 its file's byte holds (BattleFile.ReadItems), a unit listed once.
            // Whether the game has that item this time is known as the battles are planned (BattleFile.Make).
            var items = new SortedDictionary<int, BattleFile.ItemRef?[]>();
            if (Has(b, "Items", out var itemList))
            {
                if (itemList.ValueKind != JsonValueKind.Array)
                {
                    problems.Add($"the battle {name}'s Items isn't a list");
                    return null;
                }
                int n = 0;
                foreach (var entry in itemList.EnumerateArray())
                {
                    n++;
                    if (entry.ValueKind != JsonValueKind.Object || !Number(entry, "Unit", out int unit) || unit < 1
                        || unit > Units)
                    {
                        problems.Add($"the battle {name}'s items {n} name no unit: its Unit is 1 to {Units}");
                        return null;
                    }
                    var worn = BattleFile.ReadItems(entry, $"the battle {name}'s unit {unit}", problems);
                    if (worn == null)
                        return null;
                    if (Array.TrueForAll(worn, w => w == null))
                    {
                        problems.Add($"the battle {name}'s unit {unit}'s items name none ("
                                     + $"{string.Join(", ", BattleFile.Places)})");
                        return null;
                    }
                    if (items.ContainsKey(unit - 1))
                    {
                        problems.Add($"the battle {name} gives unit {unit}'s items twice");
                        return null;
                    }
                    items[unit - 1] = worn;
                }
            }
            return new QuestBattle(name, units, names, jobs, items);
        }

        /// <summary>(1.33.0) A unit's own name at the most: the game shows a renamed unit's own text (64 bytes at a battle
        /// unit's + 0x14C, ended by a 0) for a generic's name, up to 16 characters in the remaster's mode
        /// (dev/research/sidequests/unit_names.py).</summary>
        public const int MostOwnName = 16, OwnNameBytes = 63;

        /// <summary>(1.33.0) A unit's own name: 1 to 16 characters (63 bytes of UTF-8 at the most), none a control
        /// character, no space at either end (mod_studio/side_quests.py's good_own_name, character for character).</summary>
        public static bool GoodOwnName(string text)
        {
            int characters = 0;
            foreach (var rune in text.EnumerateRunes())
            {
                characters++;
                if (Rune.GetUnicodeCategory(rune) == UnicodeCategory.Control)
                    return false;
            }
            if (characters < 1 || characters > MostOwnName || Encoding.UTF8.GetByteCount(text) > OwnNameBytes)
                return false;
            return !IsSpace(Rune.GetRuneAt(text, 0)) && !IsSpace(LastRune(text));
        }

        static bool IsSpace(Rune rune)
        {
            var kind = Rune.GetUnicodeCategory(rune);
            return kind == UnicodeCategory.SpaceSeparator || kind == UnicodeCategory.LineSeparator
                   || kind == UnicodeCategory.ParagraphSeparator;
        }

        static Rune LastRune(string text)
        {
            Rune last = default;
            foreach (var rune in text.EnumerateRunes())
                last = rune;
            return last;
        }

        /// <summary>What's wrong with the quest's battle events: each one's start and won events
        /// are events of the quest that aren't battles, played in no other battle.</summary>
        static void FightsProblems(List<QuestEvent> events, List<string> problems)
        {
            var playedIn = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (var ev in events)
            {
                if (ev.Battle == null)
                    continue;
                // (1.12.0) Its lost event too; the game starts over after it, so nothing follows it. Its objective
                // shown by its start event; and only a battle's start event with an objective shows one.
                var lost = ev.Battle.Lost.Length > 0 ? events.Find(x => x.Name == ev.Battle.Lost) : null;
                if (lost != null && lost.NextEvent.Length > 0)
                    problems.Add($"the battle {ev.Name}'s lost event {lost.Name} has no next event: the game starts "
                                 + "over after it");
                var start = ev.Battle.Start.Length > 0 ? events.Find(x => x.Name == ev.Battle.Start) : null;
                if (ev.Battle.Objective.Length > 0 && (start == null || start.ObjectiveInScript.Count == 0))
                    problems.Add($"the battle {ev.Name}'s objective is shown by its start event, which has no place for "
                                 + "it (its ObjectiveInScript)");
                var scenes = new List<(string, string)>
                {
                    ("start", ev.Battle.Start), ("won", ev.Battle.Won), ("lost", ev.Battle.Lost),
                };
                // (1.31.0) Its scenes during it, each setting its guard as it ends (QuestFile.Guards, by its place).
                foreach (var d in ev.Battle.During)
                    scenes.Add(("during", d.Event));
                for (int k = 0; k < ev.Battle.During.Count; k++)
                {
                    var mid = events.Find(x => x.Name == ev.Battle.During[k].Event);
                    if (mid != null && mid.Battle == null && !SetsVariable(mid.Script, Guards[k]))
                        problems.Add($"the battle {ev.Name}'s scene {mid.Name} during it never sets variable {Guards[k]}, "
                                     + "which keeps it to once a battle: it would play again and again");
                }
                foreach (var (what, scene) in scenes)
                {
                    if (scene.Length == 0)
                        continue;
                    var played = events.Find(x => x.Name == scene);
                    if (played == null)
                        problems.Add($"the battle {ev.Name}'s {what} event {scene} isn't one of the quest's");
                    else if (played.Battle != null)
                        problems.Add($"the battle {ev.Name}'s {what} event {scene} is a battle itself");
                    else if (playedIn.TryGetValue(scene, out var other))
                        problems.Add($"the event {scene} plays twice: as {other} event and as {ev.Name}'s {what} event");
                    else
                        playedIn[scene] = $"{ev.Name}'s {what}";
                }
            }
            foreach (var ev in events)
                if (ev.ObjectiveInScript.Count > 0 && !events.Exists(x => x.Battle != null && x.Battle.Start == ev.Name
                                                                          && x.Battle.Objective.Length > 0))
                    problems.Add($"the event {ev.Name} shows a battle's objective (its ObjectiveInScript), but starts no "
                                 + "battle with one");
        }

        static QuestEvent? ReadEvent(JsonElement e, List<string> flags, List<QuestBattle> battles,
                                     Func<string, byte[]> read, List<string> problems, ICollection<string>? mapNames)
        {
            if (e.ValueKind != JsonValueKind.Object)
            {
                problems.Add("an event isn't a list of fields");
                return null;
            }
            string name = Text(e, "Name");
            if (!GoodName(name))
            {
                problems.Add($"an event's name isn't one: {e.GetRawText()}");
                return null;
            }
            QuestFight? fight = null;
            if (Has(e, "Battle", out var battle))
            {
                fight = ReadFight(name, battle, battles, problems);
                if (fight == null)
                    return null;
                if (Has(e, "Script", out _) || Has(e, "Words", out _) || Has(e, "FlagsInScript", out _)
                    || Has(e, "ObjectiveInScript", out _) || Has(e, "RamzaInScript", out _) || Has(e, "Reward", out _))
                {
                    problems.Add($"the battle {name} has no script or words of its own: every battle starts with the "
                                 + "game's three instructions, and its start and won events say what is said");
                    return null;
                }
            }
            byte[] script = Array.Empty<byte>();
            string words = "";
            if (fight == null)
            {
                string scriptName = Text(e, "Script");
                if (scriptName.Length == 0 || scriptName.Contains("..") || Path.IsPathRooted(scriptName))
                {
                    problems.Add($"the event {name} names no script in its folder");
                    return null;
                }
                try
                {
                    script = read(scriptName);
                }
                catch (Exception ex) when (ex is IOException || ex is UnauthorizedAccessException)
                {
                    problems.Add($"the event {name}'s script {scriptName} can't be read ({ex.Message})");
                    return null;
                }
                if (script.Length == 0 || script.Length > MostScript)
                {
                    problems.Add($"the event {name}'s script is {script.Length} bytes; the game reads 1 to {MostScript}");
                    return null;
                }
                words = Text(e, "Words");
                if (words.Length > 0 && (!words.StartsWith("nxd/text/", StringComparison.Ordinal)
                                         || !words.EndsWith(".pzd", StringComparison.Ordinal) || words.Contains("..")))
                {
                    problems.Add($"the event {name}'s words aren't a text file under nxd/text/: {words}");
                    return null;
                }
            }
            var setup = new Dictionary<string, int>(StringComparer.Ordinal);
            var setupBattles = new Dictionary<string, string>(StringComparer.Ordinal);
            string setupMap = "";
            string next = "";
            if (Has(e, "Setup", out var s) && s.ValueKind == JsonValueKind.Object)
                foreach (var p in s.EnumerateObject())
                {
                    if (string.Equals(p.Name, "NextEvent", StringComparison.OrdinalIgnoreCase))
                    {
                        if (p.Value.ValueKind == JsonValueKind.String)
                            next = p.Value.GetString() ?? "";
                        else
                            problems.Add($"the event {name}'s NextEvent names the quest's own event, not a number");
                        continue;
                    }
                    string? key = Array.Find(SetupFields, f => string.Equals(f, p.Name, StringComparison.OrdinalIgnoreCase));
                    var field = key == null ? null : Fields.Find(key);
                    bool names = key != null && Array.IndexOf(BattleFields, key) >= 0;
                    if (field == null)
                        problems.Add($"the event {name}'s setup has no field {p.Name} a quest gives");
                    else if (fight != null && key == "EnemyBattle")
                        problems.Add($"the battle {name}'s enemies are its Battle's Units, not its setup's EnemyBattle");
                    else if (key == "Map" && p.Value.ValueKind == JsonValueKind.String)
                    {
                        // (1.10.0) One of the mod's quest maps, by its name.
                        string named = p.Value.GetString() ?? "";
                        if (mapNames == null || !mapNames.Contains(named))
                            problems.Add($"the event {name}'s Map names {named}, which isn't one of the mod's quest maps");
                        else
                            setupMap = named;
                    }
                    else if (names && p.Value.ValueKind == JsonValueKind.String)
                    {
                        string named = p.Value.GetString() ?? "";
                        if (!battles.Exists(b => b.Name == named))
                            problems.Add($"the event {name}'s {field.Key} names {named}, which isn't one of the quest's "
                                         + "battles");
                        else
                            setupBattles[field.Key] = named;
                    }
                    else if (p.Value.ValueKind != JsonValueKind.Number || !p.Value.TryGetInt32(out int v) || v < 0
                             || v > (names ? MostGameBattle : key == "Map" ? MostGameMap : field.Most))
                        problems.Add($"the event {name}'s {field.Key} holds 0 to "
                                     + $"{(names ? MostGameBattle : key == "Map" ? MostGameMap : field.Most)}"
                                     + $"{(names ? " or one of the quest's battles" : key == "Map" ? " or one of the mod's quest maps" : "")}"
                                     + $", not {p.Value.GetRawText()}");
                    else
                        setup[field.Key] = v;
                }
            var places = new List<(int, string)>();
            if (Has(e, "FlagsInScript", out var fl) && fl.ValueKind == JsonValueKind.Array)
                foreach (var f in fl.EnumerateArray())
                {
                    string flag = f.ValueKind == JsonValueKind.Object ? Text(f, "Flag") : "";
                    if (f.ValueKind != JsonValueKind.Object || !Number(f, "At", out int at) || at < 0
                        || at + 2 > script.Length)
                        problems.Add($"the event {name} puts a flag outside its script: {f.GetRawText()}");
                    else if (!flags.Contains(flag))
                        problems.Add($"the event {name}'s script names {flag}, which isn't one of the quest's flags");
                    else
                        places.Add((at, flag));
                }
            // (1.11.0) The game's event it was copied from.
            int from = 0;
            if (Has(e, "From", out var given))
            {
                if (given.ValueKind != JsonValueKind.Number || !given.TryGetInt32(out int f) || f < 1 || f > MostGameEvent)
                    problems.Add($"the event {name}'s From is the game's event it was copied from, 1 to {MostGameEvent}, "
                                 + $"not {given.GetRawText()}");
                else
                    from = f;
            }
            // (1.12.0) Where its battle's objective goes in its script: each the byte after an instruction 0x78.
            var objectiveAt = new List<int>();
            if (Has(e, "ObjectiveInScript", out var ol))
            {
                if (ol.ValueKind != JsonValueKind.Array || fight != null)
                    problems.Add($"the event {name}'s ObjectiveInScript is a list of places in its script");
                else
                    foreach (var o in ol.EnumerateArray())
                    {
                        if (o.ValueKind != JsonValueKind.Number || !o.TryGetInt32(out int at) || at < 1
                            || at >= script.Length || script[at - 1] != DisplayConditions)
                            problems.Add($"the event {name} puts its battle's objective where its script shows none: "
                                         + o.GetRawText());
                        else if (!objectiveAt.Contains(at))
                            objectiveAt.Add(at);
                    }
            }
            // (1.30.0) Where its script names Ramza: each a unit's two bytes holding one of his identities (1, 2 or 3).
            var ramzaAt = new List<int>();
            if (Has(e, "RamzaInScript", out var rl))
            {
                if (rl.ValueKind != JsonValueKind.Array)
                    problems.Add($"the event {name}'s RamzaInScript is a list of places in its script");
                else
                    foreach (var r in rl.EnumerateArray())
                    {
                        if (r.ValueKind != JsonValueKind.Number || !r.TryGetInt32(out int at) || at < 1
                            || at > script.Length - 2 || !IsRamza(script[at]) || script[at + 1] != 0)
                            problems.Add($"the event {name} puts Ramza where its script names no Ramza (1, 2 or 3): "
                                         + r.GetRawText());
                        else if (!ramzaAt.Contains(at))
                            ramzaAt.Add(at);
                    }
            }
            // (1.31.0) Its reward: given as its script sets the reward's flag.
            QuestReward? reward = null;
            if (Has(e, "Reward", out var rw))
                reward = ReadReward(name, rw, script, places, problems);
            var ev = new QuestEvent(name, script, words, setup, next, places, fight)
            {
                SetupMap = setupMap, From = from, ObjectiveInScript = objectiveAt, RamzaInScript = ramzaAt,
                Reward = reward,
            };
            foreach (var (field, named) in setupBattles)
                ev.SetupBattles[field] = named;
            return ev;
        }

        /// <summary>(1.31.0) An event's Reward: its Flag (one of the quest's flags, set by a variable command of its
        /// script, as its FlagsInScript put it), its Gil (0 to MostGil) and its Items (up to MostRewardItems, each Item
        /// one of the game's by its number or Own, one of the mod's own items by its name, once, and its Count, 1 to
        /// MostOfAnItem), giving something; null and why in problems.</summary>
        static QuestReward? ReadReward(string name, JsonElement given, byte[] script, List<(int At, string Flag)> places,
                                       List<string> problems)
        {
            if (given.ValueKind != JsonValueKind.Object)
            {
                problems.Add($"the event {name}'s Reward is its Flag, its Gil and its Items, not {given.GetRawText()}");
                return null;
            }
            string flag = Text(given, "Flag");
            if (!places.Exists(p => p.Flag == flag))
            {
                problems.Add($"the event {name}'s Reward comes with the flag {Raw(given, "Flag")}, which its script doesn't "
                             + "name");
                return null;
            }
            if (!places.Exists(p => p.Flag == flag && p.At >= 1 && script[p.At - 1] >= FirstVariableCommand
                                    && script[p.At - 1] <= LastVariableCommand))
            {
                problems.Add($"the event {name}'s Reward comes with the flag {flag}, which its script never sets");
                return null;
            }
            int gil = 0;
            if (Has(given, "Gil", out var g) && (g.ValueKind != JsonValueKind.Number || !g.TryGetInt32(out gil) || gil < 0
                                                  || gil > MostGil))
            {
                problems.Add($"the event {name}'s Reward's Gil is 0 to {MostGilWords}, not {g.GetRawText()}");
                return null;
            }
            var items = new List<(int, string, int)>();
            if (Has(given, "Items", out var listed))
            {
                bool good = listed.ValueKind == JsonValueKind.Array && listed.GetArrayLength() <= MostRewardItems;
                var taken = new HashSet<string>(StringComparer.Ordinal);
                if (good)
                    foreach (var it in listed.EnumerateArray())
                    {
                        if (it.ValueKind != JsonValueKind.Object || !Has(it, "Item", out var item)
                            || !Number(it, "Count", out int count) || count < 1 || count > MostOfAnItem)
                        {
                            good = false;
                            break;
                        }
                        if (item.ValueKind == JsonValueKind.String && ItemFile.GoodName(item.GetString() ?? "")
                            && taken.Add("own/" + item.GetString()))
                            items.Add((0, item.GetString() ?? "", count));
                        else if (item.ValueKind == JsonValueKind.Number && item.TryGetInt32(out int n)
                                 && ItemLooks.GameItem(n) && taken.Add($"game/{n}"))
                            items.Add((n, "", count));
                        else
                        {
                            good = false;
                            break;
                        }
                    }
                if (!good)
                {
                    problems.Add($"the event {name}'s Reward's Items are up to {MostRewardItems} items, each its Item (one "
                                 + $"of the game's by its number, 1 to {ItemLooks.MostGameItem} but 254 and 255, or one of "
                                 + $"the mod's own by its name) once and its Count, 1 to {MostOfAnItem}, not "
                                 + listed.GetRawText());
                    return null;
                }
            }
            if (gil == 0 && items.Count == 0)
            {
                problems.Add($"the event {name}'s Reward gives nothing: no Gil and no Items");
                return null;
            }
            return new QuestReward(flag, gil, items);
        }

        /// <summary>A battle event's Battle: its units (a battle of the quest's by name, or of the
        /// game's by number), its start event (if any) and its won event.</summary>
        static QuestFight? ReadFight(string name, JsonElement battle, List<QuestBattle> battles, List<string> problems)
        {
            if (battle.ValueKind != JsonValueKind.Object)
            {
                problems.Add($"the battle {name}'s Battle isn't a list of fields");
                return null;
            }
            string units = Text(battle, "Units");
            int gameUnits = 0;
            if (units.Length > 0)
            {
                if (!battles.Exists(b => b.Name == units))
                {
                    problems.Add($"the battle {name}'s units {units} aren't one of the quest's battles");
                    return null;
                }
            }
            else if (!Number(battle, "Units", out gameUnits) || gameUnits < 1 || gameUnits > MostGameBattle)
            {
                problems.Add($"the battle {name}'s units are one of the quest's battles by name, or the game's 1 to "
                             + $"{MostGameBattle}");
                return null;
            }
            string start = Text(battle, "Start"), won = Text(battle, "Won");
            if (won.Length == 0)
            {
                problems.Add($"the battle {name} names no won event (what plays once every enemy is beaten ends the "
                             + "battle)");
                return null;
            }
            // (1.12.0) How it is won: every enemy beaten unless its WonWhen says one of three other ways.
            string wonBy = QuestFight.Enemies;
            int wonUnit = 0, share = 0, x = 0, y = 0, upper = 0;
            if (Has(battle, "WonWhen", out var when))
            {
                if (when.ValueKind != JsonValueKind.Object)
                {
                    problems.Add($"the battle {name}'s WonWhen isn't a list of fields");
                    return null;
                }
                bool beaten = Has(when, "Beaten", out var beatenUnit), worn = Has(when, "WornDown", out var wornUnit),
                     onTile = Has(when, "OnTile", out var tile);
                if ((beaten ? 1 : 0) + (worn ? 1 : 0) + (onTile ? 1 : 0) != 1)
                {
                    problems.Add($"the battle {name}'s WonWhen gives one of Beaten, WornDown and OnTile");
                    return null;
                }
                if (beaten || worn)
                {
                    var unit = beaten ? beatenUnit : wornUnit;
                    if (unit.ValueKind != JsonValueKind.Number || !unit.TryGetInt32(out wonUnit) || wonUnit < 1
                        || wonUnit > Units)
                    {
                        problems.Add($"the battle {name}'s WonWhen names one of its {Units} units, 1 to {Units}, not "
                                     + unit.GetRawText());
                        return null;
                    }
                    wonBy = beaten ? QuestFight.Beaten : QuestFight.WornDown;
                    bool hasShare = Has(when, "Share", out _);
                    if (worn && (!Number(when, "Share", out share) || share < 1 || share > MostShare))
                    {
                        problems.Add($"the battle {name}'s WornDown gives a Share, 1 to {MostShare} percent of the "
                                     + "unit's HP");
                        return null;
                    }
                    if (beaten && hasShare)
                    {
                        problems.Add($"the battle {name}'s Share goes with WornDown, not Beaten");
                        return null;
                    }
                }
                else
                {
                    var at = new List<int>();
                    if (tile.ValueKind == JsonValueKind.Array)
                        foreach (var v in tile.EnumerateArray())
                            at.Add(v.ValueKind == JsonValueKind.Number && v.TryGetInt32(out int n) ? n : -1);
                    if (at.Count != 3 || at[0] < 0 || at[0] > MostTile || at[1] < 0 || at[1] > MostTile || at[2] < 0
                        || at[2] > 1)
                    {
                        problems.Add($"the battle {name}'s OnTile is a tile, its x and y (0 to {MostTile}) and its "
                                     + $"level (0, or 1 for its upper level), not {tile.GetRawText()}");
                        return null;
                    }
                    (x, y, upper) = (at[0], at[1], at[2]);
                    wonBy = QuestFight.OnTile;
                }
            }
            // (1.12.0) A unit it is lost without, and its event once it is lost.
            int protect = 0;
            string lost = Text(battle, "Lost");
            if (Has(battle, "Protect", out var protectUnit))
            {
                if (protectUnit.ValueKind != JsonValueKind.Number || !protectUnit.TryGetInt32(out protect) || protect < 1
                    || protect > Units)
                {
                    problems.Add($"the battle {name}'s Protect names one of its {Units} units, 1 to {Units}, not "
                                 + protectUnit.GetRawText());
                    return null;
                }
                if (lost.Length == 0)
                {
                    problems.Add($"the battle {name} names no lost event (what plays once the unit it protects is "
                                 + "beaten, after which the game starts over)");
                    return null;
                }
            }
            else if (lost.Length > 0)
            {
                problems.Add($"the battle {name}'s lost event {lost} plays once a unit it protects is beaten: it "
                             + "protects none");
                return null;
            }
            if (protect > 0 && protect == wonUnit)
            {
                problems.Add($"the battle {name} is won and lost by its unit {protect}");
                return null;
            }
            // (1.12.0) Its objective's words, which its start event shows.
            string objective = "";
            if (Has(battle, "Objective", out var words))
            {
                objective = words.ValueKind == JsonValueKind.String ? words.GetString() ?? "" : "";
                if (!GoodObjective(objective))
                {
                    problems.Add($"the battle {name}'s Objective is words of 1 to {MostObjective} characters on one "
                                 + $"line, not {words.GetRawText()}");
                    return null;
                }
            }
            // (1.14.0) Its own deploy areas.
            var deploy = new List<DeployArea>();
            if (Has(battle, "Deploy", out var areas) && !ReadDeploy($"the battle {name}", areas, deploy, problems))
                return null;
            // (1.31.0) Its scenes during it.
            var during = new List<QuestDuring>();
            if (Has(battle, "During", out var mid) && !ReadDuring(name, mid, during, problems))
                return null;
            var fight = new QuestFight(units, gameUnits, start, won)
            {
                WonBy = wonBy, WonUnit = wonUnit, WonShare = share, TileX = x, TileY = y, TileUpper = upper,
                Protect = protect, Lost = lost, Objective = objective, Deploy = deploy, During = during,
            };
            int rules = RulesOf(fight);
            if (rules > MostRules)
            {
                problems.Add($"the battle {name} has {rules} rules, more than the {MostRules} the game runs (each scene "
                             + "during it on Ramza's turn or HP takes 3: one for each of his chapters)");
                return null;
            }
            return fight;
        }

        /// <summary>(1.31.0) A battle's During: up to MostDuring scenes, each its Event (a name, once), its When (Turn or
        /// Hp), its Unit (0 Ramza, else one of the battle's 16) and, for Hp, its Share (0 to 99); false and why in
        /// problems.</summary>
        static bool ReadDuring(string name, JsonElement given, List<QuestDuring> during, List<string> problems)
        {
            bool good = given.ValueKind == JsonValueKind.Array && given.GetArrayLength() <= MostDuring;
            if (good)
                foreach (var d in given.EnumerateArray())
                {
                    string ev = d.ValueKind == JsonValueKind.Object ? Text(d, "Event") : "";
                    string when = d.ValueKind == JsonValueKind.Object ? Text(d, "When") : "";
                    if (!GoodName(ev) || during.Exists(x => x.Event == ev)
                        || (when != QuestFight.Turn && when != QuestFight.Hp)
                        || !Number(d, "Unit", out int unit) || unit < 0 || unit > Units)
                    {
                        good = false;
                        break;
                    }
                    int share = 0;
                    if (Has(d, "Share", out var given_)
                        && (when != QuestFight.Hp || given_.ValueKind != JsonValueKind.Number
                            || !given_.TryGetInt32(out share) || share < 0 || share > MostShareDuring))
                    {
                        problems.Add($"the battle {name}'s scene {ev} during it has a Share only when it plays as its "
                                     + $"unit's HP falls (Hp): 0 to {MostShareDuring} percent of its most, 0 beaten, not "
                                     + given_.GetRawText());
                        return false;
                    }
                    during.Add(new QuestDuring(ev, when, unit, share));
                }
            if (!good)
                problems.Add($"the battle {name}'s During is up to {MostDuring} scenes, each its Event once, its When "
                             + $"({QuestFight.Turn} or {QuestFight.Hp}) and its Unit (0 Ramza, else one of its {Units} "
                             + $"units), not {given.GetRawText()}");
            return good;
        }

        /// <summary>(1.31.0) How many rules a battle's chains are as the framework lays them out (Framework's battles'
        /// rules): its start, its protected unit's, how it is won (Ramza on a tile one for each of his chapters, then
        /// every enemy beaten), each scene during it (on Ramza's turn or HP one for each of his chapters).</summary>
        public static int RulesOf(QuestFight fight)
        {
            int rules = 1 + (fight.Protect > 0 ? 1 : 0);
            rules += fight.WonBy == QuestFight.OnTile ? 3 + 1 : 1;
            foreach (var d in fight.During)
                rules += d.Unit == 0 ? 3 : 1;
            return rules;
        }

        /// <summary>(1.31.0) Whether a script sets a variable: a variable command (0xB0 to 0xBE) naming it, found by its
        /// bytes.</summary>
        public static bool SetsVariable(byte[] script, int variable)
        {
            for (int at = 0; at + 3 <= script.Length; at++)
                if (script[at] >= FirstVariableCommand && script[at] <= LastVariableCommand
                    && BinaryPrimitives.ReadUInt16LittleEndian(script.AsSpan(at + 1, 2)) == variable)
                    return true;
            return false;
        }

        /// <summary>(1.14.0) A battle's Deploy: one or two deploy areas, each its Squares (1 to 25, each a tile's x and
        /// y, 0 to 255, within 5 by 5 squares), its Units (how many of the player's units start there, 1 to 5, no
        /// more than its squares), its Facing (South, West, North or East) and, if on their upper level, Upper. (1.17.0)
        /// `who` names the battle in what is said: "the battle X" (a quest's), "the random battle X" (a place's).</summary>
        public static bool ReadDeploy(string who, JsonElement areas, List<DeployArea> deploy, List<string> problems)
        {
            if (areas.ValueKind != JsonValueKind.Array || areas.GetArrayLength() < 1 || areas.GetArrayLength() > 2)
            {
                problems.Add($"{who}'s Deploy is one or two deploy areas");
                return false;
            }
            int n = 0;
            foreach (var area in areas.EnumerateArray())
            {
                n++;
                string which = $"{who}'s deploy area {n}";
                if (area.ValueKind != JsonValueKind.Object)
                {
                    problems.Add($"{which} isn't a list of fields");
                    return false;
                }
                var squares = new List<(int X, int Y)>();
                bool good = Has(area, "Squares", out var given) && given.ValueKind == JsonValueKind.Array
                            && given.GetArrayLength() >= 1 && given.GetArrayLength() <= DeployArea.MostSquares;
                if (good)
                    foreach (var square in given.EnumerateArray())
                    {
                        var at = new List<int>();
                        if (square.ValueKind == JsonValueKind.Array)
                            foreach (var v in square.EnumerateArray())
                                at.Add(v.ValueKind == JsonValueKind.Number && v.TryGetInt32(out int c) ? c : -1);
                        if (at.Count != 2 || at[0] < 0 || at[0] > MostTile || at[1] < 0 || at[1] > MostTile)
                        {
                            good = false;
                            break;
                        }
                        squares.Add((at[0], at[1]));
                    }
                if (!good)
                {
                    problems.Add($"{which}'s Squares are 1 to {DeployArea.MostSquares} tiles, each its x and y (0 to "
                                 + $"{MostTile}), not {(Has(area, "Squares", out var raw) ? raw.GetRawText() : "none")}");
                    return false;
                }
                var seen = new HashSet<(int, int)>();
                foreach (var square in squares)
                    if (!seen.Add(square))
                    {
                        problems.Add($"{which} gives the square {square.X}, {square.Y} twice");
                        return false;
                    }
                int minX = int.MaxValue, maxX = int.MinValue, minY = int.MaxValue, maxY = int.MinValue;
                foreach (var (sx, sy) in squares)
                {
                    minX = Math.Min(minX, sx);
                    maxX = Math.Max(maxX, sx);
                    minY = Math.Min(minY, sy);
                    maxY = Math.Max(maxY, sy);
                }
                int wide = maxX - minX + 1, deep = maxY - minY + 1;
                if (wide > DeployArea.MostSpan || deep > DeployArea.MostSpan)
                {
                    problems.Add($"{which}'s squares fit in {DeployArea.MostSpan} by {DeployArea.MostSpan} squares, "
                                 + $"not {wide} by {deep}");
                    return false;
                }
                if (!Number(area, "Units", out int count) || count < 1 || count > DeployArea.MostUnits
                    || count > squares.Count)
                {
                    problems.Add($"{which}'s Units is how many of the player's units start there, 1 to "
                                 + $"{DeployArea.MostUnits} and no more than its squares, not "
                                 + $"{(Has(area, "Units", out var units) ? units.GetRawText() : "none")}");
                    return false;
                }
                string facingName = Text(area, "Facing");
                int facing = DeploySquads.FacingOf(facingName);
                if (facing < 0)
                {
                    problems.Add($"{which}'s Facing is one of South, West, North and East, not "
                                 + $"{(Has(area, "Facing", out var f) ? f.GetRawText() : "none")}");
                    return false;
                }
                bool upper = false;
                if (Has(area, "Upper", out var up))
                {
                    if (up.ValueKind != JsonValueKind.True && up.ValueKind != JsonValueKind.False)
                    {
                        problems.Add($"{which}'s Upper is true or false, not {up.GetRawText()}");
                        return false;
                    }
                    upper = up.ValueKind == JsonValueKind.True;
                }
                deploy.Add(new DeployArea(squares, upper, count, facing));
            }
            return true;
        }

        /// <summary>(1.12.0) Words a battle's objective may be: 1 to 64 characters, no control character (a line
        /// break among them), no space at either end.</summary>
        public static bool GoodObjective(string words)
        {
            if (words.Length < 1 || words.Length > MostObjective || char.IsWhiteSpace(words[0])
                || char.IsWhiteSpace(words[^1]))
                return false;
            foreach (char c in words)
                if (char.IsControl(c))
                    return false;
            return true;
        }

        /// <summary>(1.12.0) Whether a battle's rules can name a unit by its unit ID: the game's CharaControlId table
        /// (0xDA) gives the unit ID a rule tests by the rule's key (its row + 8, read as the rules load, 0x2FC042), and
        /// its keys 1 to 52, 100 to 103 and 128 to 139 are those IDs themselves (the 1.5.2 tables and WotL
        /// Restoration's alike); a key the table hasn't gives no row, which the game reads at address 8.</summary>
        public static bool NamedUnit(int id) => (id >= 1 && id <= 52) || (id >= 100 && id <= 103) || (id >= 128 && id <= 139);

        /// <summary>(1.12.0) What's wrong with the units a battle event's WonWhen and Protect name: of one of the quest's
        /// own battles (whose units are in the quest's folder), each a unit (its sprite set not 0) always on the field
        /// (Always Present alone), its unit ID one the rules can name and no other unit's of its battle.</summary>
        static void UnitsProblems(List<QuestEvent> events, List<QuestBattle> battles, List<string> problems)
        {
            foreach (var ev in events)
            {
                var fight = ev.Battle;
                // (1.31.0) And its scenes during it, each by its unit's turn or HP (Ramza's, 0, needs none of its own).
                var named = new List<int> { fight?.WonUnit ?? 0, fight?.Protect ?? 0 };
                if (fight != null)
                    foreach (var d in fight.During)
                        if (d.Unit > 0 && !named.Contains(d.Unit))
                            named.Add(d.Unit);
                if (fight == null || named.TrueForAll(slot => slot == 0))
                    continue;
                var battle = fight.Units.Length > 0 ? battles.Find(b => b.Name == fight.Units) : null;
                if (battle == null)
                {
                    problems.Add($"the battle {ev.Name} names a unit of its own in its WonWhen, Protect or During: its "
                                 + "units are one of the quest's battles, by name, for that");
                    continue;
                }
                foreach (int slot in named)
                {
                    if (slot == 0)
                        continue;
                    int at = (slot - 1) * UnitBytes;
                    var units = battle.Units;
                    if (units[at] == 0)
                    {
                        problems.Add($"the battle {ev.Name}'s unit {slot} is an empty place");
                        continue;
                    }
                    int id = units[at + UnitIdAt];
                    if (!NamedUnit(id))
                        problems.Add($"the battle {ev.Name}'s unit {slot} has the unit ID {id}, which a battle's rules "
                                     + "can't name: give it one of 1 to 52, 100 to 103 or 128 to 139");
                    for (int other = 1; other <= Units; other++)
                        if (other != slot && units[(other - 1) * UnitBytes] != 0
                            && units[(other - 1) * UnitBytes + UnitIdAt] == id)
                        {
                            problems.Add($"the battle {ev.Name}'s unit {slot} shares its unit ID {id} with its unit "
                                         + $"{other}");
                            break;
                        }
                    if ((units[at + PresenceAt] & PresenceMask) != AlwaysPresent)
                        problems.Add($"the battle {ev.Name}'s unit {slot} isn't always on the field (Always Present "
                                     + "alone): its rules would wait for a unit that may not be there");
                    if ((units[at + FlagsAt] & LoadFormation) != 0)
                        problems.Add($"the battle {ev.Name}'s unit {slot} is taken from the player's own units as the "
                                     + "battle starts (Load Formation), which leaves an empty place at 0 HP when they "
                                     + "haven't that unit: build it from its own fields (Load Formation off)");
                }
            }
        }

        static QuestStart? ReadStart(JsonElement s, List<string> flags, List<QuestEvent> events, List<string> problems,
                                     ICollection<string>? placeNames)
        {
            int place = -1;
            string placeName = "";
            if (s.ValueKind == JsonValueKind.Object && Has(s, "Place", out var named) && named.ValueKind == JsonValueKind.String
                && (named.GetString() ?? "").Length > 0)
            {
                // (1.8.0) One of the mod's own places, by its name.
                placeName = named.GetString()!;
                if (placeNames == null || !placeNames.Contains(placeName))
                {
                    problems.Add($"a start's place names no place of the mod's ({placeName})");
                    return null;
                }
            }
            else if (s.ValueKind != JsonValueKind.Object || !Number(s, "Place", out place) || place < 0 || place >= Places)
            {
                problems.Add($"a start's place isn't one of the world map's 0 to {Places - 1}: {s.GetRawText()}");
                return null;
            }
            string ev = Text(s, "Event");
            if (!events.Exists(x => x.Name == ev))
            {
                problems.Add($"a start's event {ev} isn't one of the quest's");
                return null;
            }
            // (1.12.0) Its lost event too.
            var fight = events.Find(x => x.Battle != null && (x.Battle.Start == ev || x.Battle.Won == ev
                                                              || (x.Battle.Lost.Length > 0 && x.Battle.Lost == ev)));
            if (fight != null)
            {
                problems.Add($"a start's event {ev} plays in the battle {fight.Name}: a start loads the battle");
                return null;
            }
            bool stops = false;
            if (Has(s, "Passing", out var passing))
            {
                string how = passing.ValueKind == JsonValueKind.String ? passing.GetString() ?? "" : "";
                if (how != "Stops" && how != "Waits")
                {
                    problems.Add($"a start's Passing is Stops or Waits, not {passing.GetRawText()}");
                    return null;
                }
                stops = how == "Stops";
            }
            // (1.25.0) Waiting at a floor of one of the mod's own dungeons, its place named: played as the floor is
            // chosen, never as a travel passes.
            string floor = "";
            if (Has(s, "Floor", out var floorValue))
            {
                floor = floorValue.ValueKind == JsonValueKind.String ? floorValue.GetString() ?? "" : "";
                if (!GoodName(floor) || floor.Length > PlaceFile.MostFloorName)
                {
                    problems.Add($"a start's Floor is a floor's name, 1 to {PlaceFile.MostFloorName} letters, digits, "
                                 + $"spaces, underscores and hyphens, not {floorValue.GetRawText()}");
                    return null;
                }
                if (placeName.Length == 0)
                {
                    problems.Add($"a start's Floor {floor} is a floor of one of the mod's own dungeons, named by its "
                                 + $"Place, not of the world map's place {place}");
                    return null;
                }
                if (stops)
                {
                    problems.Add($"a start at a floor plays as the floor is chosen: its Passing can't be Stops");
                    return null;
                }
            }
            var when = ReadConditions(s, "a start", flags, problems);
            if (when == null)
                return null;
            return new QuestStart(place, when, ev, stops, placeName, floor);
        }

        /// <summary>The conditions of a start or (1.15.0) a rumor (`who` says which in its problems): its When, each a
        /// game variable's value, a quest flag's or a character in the party, as the world map tests them; null and why
        /// in problems.</summary>
        static List<Condition>? ReadConditions(JsonElement s, string who, List<string> flags, List<string> problems)
        {
            var when = new List<Condition>();
            if (Has(s, "When", out var list) && list.ValueKind == JsonValueKind.Array)
                foreach (var c in list.EnumerateArray())
                {
                    if (c.ValueKind != JsonValueKind.Object)
                    {
                        problems.Add($"{who}'s condition isn't a list of fields");
                        return null;
                    }
                    if (when.Count == MostConditions)
                    {
                        problems.Add($"{who} has more than {MostConditions} conditions");
                        return null;
                    }
                    string test = Number(c, "Is", out int value) ? "Is"
                        : Number(c, "AtLeast", out value) ? "AtLeast"
                        : Number(c, "AtMost", out value) ? "AtMost" : "";
                    if (Number(c, "Variable", out int variable))
                    {
                        if (test.Length == 0 || variable < 1 || variable > 0x3FF || value < 0 || value > 0xFFFF)
                        {
                            problems.Add($"{who}'s condition isn't one the world map tests: {c.GetRawText()}");
                            return null;
                        }
                        when.Add(new Condition("Variable", variable, "", test, value));
                    }
                    else if (Text(c, "Flag").Length > 0)
                    {
                        string flag = Text(c, "Flag");
                        if (!flags.Contains(flag) || test != "Is" || (value != 0 && value != 1))
                        {
                            problems.Add($"{who}'s flag condition isn't one of the quest's flags being 0 or 1: {c.GetRawText()}");
                            return null;
                        }
                        when.Add(new Condition("Flag", 0, flag, test, value));
                    }
                    else if (Number(c, "Character", out int character))
                    {
                        if (character < 1 || character > 0xFF)
                        {
                            problems.Add($"{who}'s character isn't one: {c.GetRawText()}");
                            return null;
                        }
                        when.Add(new Condition("Character", 0, "", "Is", character));
                    }
                    else
                    {
                        problems.Add($"{who}'s condition names no variable, flag or character: {c.GetRawText()}");
                        return null;
                    }
                }
            return when;
        }

        /// <summary>(1.15.0) Words a rumor's own may be (its Text): 1 to 3,000 characters, line breaks the only control
        /// characters among them, no space at either end.</summary>
        public static bool GoodRumorText(string words)
        {
            if (words.Length < 1 || words.Length > MostRumorText || char.IsWhiteSpace(words[0])
                || char.IsWhiteSpace(words[^1]))
                return false;
            foreach (char c in words)
                if (char.IsControl(c) && c != '\n')
                    return false;
            return true;
        }

        /// <summary>(1.15.0) A tavern rumor: its Name, Title (words as an objective's), Text, Towns (1 to 15 of the
        /// towns' places, 0 to 14, each once; none: every tavern), When (as a start's) and Read (one of the quest's flags,
        /// set once it is read); null and why in problems.</summary>
        static QuestRumor? ReadRumor(JsonElement r, List<string> flags, List<string> problems,
                                     ICollection<string>? placeNames = null)
        {
            string name = r.ValueKind == JsonValueKind.Object ? Text(r, "Name") : "";
            if (!GoodName(name))
            {
                problems.Add($"a rumor's name isn't one: {(r.ValueKind == JsonValueKind.Object && Has(r, "Name", out var n) ? n.GetRawText() : r.GetRawText())}");
                return null;
            }
            string which = $"the rumor {name}";
            string title = Has(r, "Title", out var t) && t.ValueKind == JsonValueKind.String ? t.GetString() ?? "" : "";
            if (!GoodObjective(title))
            {
                problems.Add($"{which}'s Title is words of 1 to {MostRumorTitle} characters on one line, not "
                             + $"{(Has(r, "Title", out var raw) ? raw.GetRawText() : "none")}");
                return null;
            }
            string text = Has(r, "Text", out var x) && x.ValueKind == JsonValueKind.String ? x.GetString() ?? "" : "";
            if (!GoodRumorText(text))
            {
                problems.Add($"{which}'s Text is words of 1 to {MostRumorText} characters, its paragraphs apart by line "
                             + $"breaks, not {(Has(r, "Text", out var raw) ? raw.GetRawText() : "none")}");
                return null;
            }
            var towns = new List<int>();
            var townNames = new List<string>();
            if (Has(r, "Towns", out var townList))
            {
                // The game's towns by their places; (1.18.0) the mod's own towns by their names.
                bool good = townList.ValueKind == JsonValueKind.Array && townList.GetArrayLength() >= 1;
                if (good)
                    foreach (var town in townList.EnumerateArray())
                    {
                        if (town.ValueKind == JsonValueKind.String)
                        {
                            string named = town.GetString() ?? "";
                            if (placeNames == null || !placeNames.Contains(named) || townNames.Contains(named))
                            {
                                good = false;
                                break;
                            }
                            townNames.Add(named);
                        }
                        else if (town.ValueKind != JsonValueKind.Number || !town.TryGetInt32(out int place) || place < 0
                                 || place >= Towns || towns.Contains(place))
                        {
                            good = false;
                            break;
                        }
                        else
                            towns.Add(place);
                    }
                if (!good)
                {
                    problems.Add($"{which}'s Towns are the towns whose taverns tell it, the game's by their places (0 "
                                 + $"to {Towns - 1}) or the mod's own by their names, each once, not "
                                 + townList.GetRawText());
                    return null;
                }
            }
            var when = ReadConditions(r, which, flags, problems);
            if (when == null)
                return null;
            string read = Text(r, "Read");
            if (!flags.Contains(read))
            {
                problems.Add($"{which}'s Read is the quest's flag set once it is read, not "
                             + $"{(Has(r, "Read", out var raw) ? raw.GetRawText() : "none")}");
                return null;
            }
            return new QuestRumor(name, title, text, towns, when, read, townNames);
        }
    }
}
