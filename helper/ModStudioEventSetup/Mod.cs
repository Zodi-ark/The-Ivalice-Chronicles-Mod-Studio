// Mod Studio Framework: a Reloaded-II mod that applies the event setup
// changes mods made with The Ivalice Chronicles Mod Studio list in their
// EventSetup.json (an event's map, weather, time of day, music, enemy
// battle, deploy areas, what follows it and its battle rules, which the game
// keeps in its program rather than in a table the mod loader changes), and,
// since 1.1.0, the side quests' framework: the quests mods give in their
// ModStudioQuests folders, each name given a number of the game's
// (Framework.cs), joined to the game by hooks (Hooks.cs) made only when some
// mod gives a quest, so a game without side quests runs as with 1.0.2; and,
// since 1.2.0, their battles of their own (their units, numbered as the rest);
// since 1.2.1, the story kept from a quest's event (the game's progress and
// the story's progress variable left as they were while one plays); since
// 1.2.2, the way kept open (a quest's event waiting where you stand doesn't
// stop travel on); since 1.2.3, through native code that keeps the registers
// the game's travel step counts on (Thunks.cs: 1.2.2's C# hook changed them,
// and a travel through a town could stop the game); since 1.2.4, a start's
// event waits until its place is chosen, unless the start says it stops a
// travel passing through ("Passing": "Stops", as the game's own events do);
// since 1.2.5, a quest whose file gives a Marker has the world map's quest
// marker in its color where it waits (Marker.cs); since 1.3.0, a mod's own
// places (its ModStudioPlaces folder) are shown on the world map, pictures
// only (PlaceFile.cs, MapPieces.cs), through a hook of their own
// (PlaceHooks.cs) made only when some mod gives one; since 1.4.0, a mod's
// own roads (its ModStudioRoads folder) are drawn there too, pictures only
// (RoadFile.cs, MapRoads.cs), through the same hook; since 1.5.0, a mod's
// road between two of the game's places travelled (Travel.cs), since 1.6.0
// with the game's random battles where it arrives; since 1.7.0, a mod's own
// place somewhere Ramza goes, numbered past the game's 48 and kept
// (Destinations.cs), its road to it travelled; since 1.10.0, a quest's own
// maps (a mod's ModStudioMaps folder, MapFile.cs), numbered past the game's
// 128 and kept, loaded as the game's own (MapRoom.cs, MapHooks.cs); since
// 1.11.0, a quest's event copied from one of the game's (its From) plays the
// map's doors and moving parts as that event does (MapAnimations.cs).
//
// Part of The Ivalice Chronicles Mod Studio. GPL-3.0: see LICENSE in Mod
// Studio's folder. Written for Mod Studio from the game's own data and
// program and Reloaded-II's public interfaces (Reloaded.Mod.Interfaces,
// GPL-3.0; Reloaded.Hooks's, LGPL-3.0); nothing of the mod loader's.
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.CompilerServices;
using Reloaded.Mod.Interfaces;
using Reloaded.Mod.Interfaces.Internal;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    public sealed class Mod : IMod
    {
        public const string Name = "Mod Studio Framework";

        IModLoader? _loader;
        ILoggerV1? _logger;
        string _self = "";
        GameMemory? _memory;
        Table? _table;
        /// <summary>The side quests' hooks, once made: kept for as long as the game runs.</summary>
        Hooks? _hooks;
        /// <summary>(1.3.0) The mods' own places' hook, once made: kept for as long as the game runs.</summary>
        PlaceHooks? _placeHooks;
        /// <summary>(1.7.1) The places the mods give this time (numbered, the program given them), and the hook of a
        /// save's load moving Ramza off a mod's place no mod gives now.</summary>
        readonly List<int> _given = new List<int>();
        SaveFallbackHook? _saveHook;
        /// <summary>(1.8.0) Each mod's own places' names as read (a quest's start may name one), and the numbers of
        /// those the game goes to this time, by "modId/name".</summary>
        readonly Dictionary<string, List<string>> _placeNames = new Dictionary<string, List<string>>(StringComparer.Ordinal);
        readonly Dictionary<string, int> _placeNumbers = new Dictionary<string, int>(StringComparer.Ordinal);
        /// <summary>(1.26.0) The mods' own items, when armed, and each one's number by its mod and name.</summary>
        ItemHooks? _items;
        /// <summary>(2.0.0) War of the Lions' items the framework gives, by number (none where it gives none): what a
        /// unit's or a tile's item past 255 may name besides a mod's own.</summary>
        readonly Dictionary<int, string> _wotlItems = new Dictionary<int, string>();
        readonly Dictionary<string, int> _itemNumbers = new Dictionary<string, int>(StringComparer.Ordinal);
        /// <summary>(2.0.0) What each item past the game's 255 is worn as, by its number, for every such item the game
        /// has this time: War of the Lions' (the framework's own, or WotL Restoration's where it gives them) and the
        /// mods' own. The game's own five past 255 are BattleFile.GameKind's.</summary>
        readonly Dictionary<int, ItemKind> _itemKinds = new Dictionary<int, ItemKind>();
        /// <summary>(2.0.0) The side quests' plan, once made (its battles' names and their units' items past 255), and
        /// the battles' hooks, kept while the game runs.</summary>
        Framework? _questPlan;
        BattleHooks? _battles;
        /// <summary>(2.0.6) Random equipment reaching War of the Lions' items the framework gives: the game's function and
        /// its asks, found (null: Random is the game's own), the items that could be Random equipment by kind (none
        /// Rare), and every given one's name by its number.</summary>
        RandomItems.Found? _randomFound;
        Dictionary<ItemKind, List<int>>? _randomExtras;
        Dictionary<int, ModItem>? _randomPlanned;
        /// <summary>(2.0.6) WotL Restoration's 40 items shown with the framework's own pictures, kept while the game runs.
        /// </summary>
        WotLIcons? _theirIcons;
        /// <summary>Where the side quests and the places join the game, found once.</summary>
        Places? _found;
        /// <summary>(1.17.0) The mods' battle grounds with random battles of their own, each with the number it was
        /// given; and where a mod's own place's roll goes (the roll's native code's slot, 0 without it), which the side
        /// quests' hooks fill with the helper's own roll.</summary>
        readonly List<(MapPlace Place, int Number)> _grounds = new List<(MapPlace, int)>();
        /// <summary>(1.18.0) The mods' towns with a menu of their own, as their places were numbered.</summary>
        readonly List<(MapPlace Place, int Number)> _menuTowns = new List<(MapPlace, int)>();
        /// <summary>(1.20.0) The mods' towns darkened once a quest's flag is set, shown on the world map.</summary>
        readonly List<MapPlace> _darkPlaces = new List<MapPlace>();
        nint _groundSlot;
        /// <summary>(1.21.0) The mods' dungeons, as their places were numbered; the places' data holding their slots
        /// (0: none given).</summary>
        readonly List<(MapPlace Place, int Number)> _dungeons = new List<(MapPlace, int)>();
        nint _dungeonData;
        /// <summary>(1.10.0) The quest maps given numbers this time, by "modId/folder" (a quest's setup may name one),
        /// and their hooks, kept as long as the game runs.</summary>
        readonly Dictionary<string, int> _mapNumbers = new Dictionary<string, int>(StringComparer.Ordinal);
        /// <summary>(1.10.0) The quest maps given numbers: each number's Base.</summary>
        readonly Dictionary<int, int> _mapBases = new Dictionary<int, int>();
        MapHooks? _mapHooks;
        readonly Applier _applier = new Applier();
        /// <summary>(1.13.0) What reading the numbers' copies said, each line once as the game starts.</summary>
        readonly HashSet<string> _numbersSaid = new HashSet<string>(StringComparer.Ordinal);
        /// <summary>(1.32.0) The numbers the side quests were planned with and kept (their mark the one a flag set
        /// gives a save), for the save hook; null when no quest was.</summary>
        Numbers? _questNumbers;
        /// <summary>The mods to read, in the order Reloaded-II loaded them.</summary>
        readonly List<IModConfigV1> _order = new List<IModConfigV1>();
        readonly HashSet<string> _seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        bool _initialized;

        public Action Disposing { get; set; } = () => { };

        public void StartEx(IModLoaderV1 loaderApi, IModConfigV1 modConfig)
        {
            _loader = (IModLoader)loaderApi;
            _logger = _loader.GetLogger();
            _self = modConfig.ModId;
            string why;
            try
            {
                _memory = GameMemory.OfThisProcess();
                _table = Finder.Find(_memory.Bytes, out why);
            }
            catch (Exception e)
            {
                why = e.Message;
            }
            // Only what a user needs to debug: how the table was found, and in
            // which program of what size, are said only when it wasn't (Zodi,
            // 22 October, of 1.0.1's first line: "no need for the 'by WotL
            // Restoration's pattern, in FFT_enhanced.exe of 12,158,720 bytes.'
            // part").
            string program = _memory?.Program ?? "the game's program";
            if (_table == null)
                Say($"the game's event setup table wasn't found in {program} ({why}), so no mod's event setup is "
                    + "applied. A game update may have changed it: look for a newer " + Name + ".");
            else
                Say($"found the game's event setup table ({_table.SlotOf.Count} events).");

            foreach (var active in _loader.GetActiveMods())
                Note(active.Generic);
            _loader.ModLoaded += Loaded;
            _loader.OnModLoaderInitialized += Initialized;
        }

        void Say(string text)
        {
            string line = $"[{Name}] {text}";
            if (_logger is ILoggerV2 logger)
                logger.WriteLine(line);
            else
                _logger?.PrintMessage(line, System.Drawing.Color.White);
        }

        void Note(IModConfigV1 config)
        {
            if (config == null || string.Equals(config.ModId, _self, StringComparison.OrdinalIgnoreCase)
                || !_seen.Add(config.ModId))
                return;
            _order.Add(config);
        }

        void Loaded(IModV1 mod, IModConfigV1 config)
        {
            bool fresh = config != null && !_seen.Contains(config.ModId);
            Note(config!);
            // A mod loaded after the start (enabled while the game runs): its event setup is applied
            // at once; its side quests, which need numbers given before the game reads its tables,
            // come in when the game starts again.
            if (_initialized && fresh)
            {
                Apply(config!);
                string folder = Folder(config!);
                if (folder.Length > 0 && Directory.Exists(Path.Combine(folder, QuestFile.Folder)))
                    Say($"{ModName(config!)}'s side quests come in when the game starts again.");
                if (folder.Length > 0 && Directory.Exists(Path.Combine(folder, PlaceFile.Folder)))
                    Say($"{ModName(config!)}'s own places come in when the game starts again.");
                if (folder.Length > 0 && Directory.Exists(Path.Combine(folder, RoadFile.Folder)))
                    Say($"{ModName(config!)}'s own roads come in when the game starts again.");
                if (folder.Length > 0 && Directory.Exists(Path.Combine(folder, MapFile.Folder)))
                    Say($"{ModName(config!)}'s quest maps come in when the game starts again.");
            }
        }

        /// <summary>Every mod loaded, before the game runs: each one's event setup applied, then (1.8.0) the
        /// mods' own places and roads (numbered and given to the game first, so a quest's start may name one),
        /// then (1.10.0) the quest maps (numbered and given to the game, so a quest's setup may name one), then the
        /// side quests planned and joined to the game (1.9.0: the event tables given room first), then (1.9.0) that
        /// room made for a save's last event when no quest made it.</summary>
        void Initialized()
        {
            _initialized = true;
            foreach (var config in _order)
                Apply(config);
            try
            {
                FreeNumbersIfAsked();
            }
            catch (Exception e)
            {
                Say($"the numbers of mods not enabled weren't freed ({e.GetType().Name}: {e.Message}).");
            }
            try
            {
                PlanItems();
            }
            catch (Exception e)
            {
                Say($"the mods' items weren't added ({e.GetType().Name}: {e.Message}).");
            }
            try
            {
                PlanLooks();
            }
            catch (Exception e)
            {
                Say($"the game's weapons' looks in battle weren't changed ({e.GetType().Name}: {e.Message}).");
            }
            try
            {
                PlanJobs();
            }
            catch (Exception e)
            {
                Say($"the mods' own jobs weren't added ({e.GetType().Name}: {e.Message}).");
            }
            try
            {
                PlanPlaces();
            }
            catch (Exception e)
            {
                Say($"the mods' own places weren't added ({e.GetType().Name}: {e.Message}).");
            }
            try
            {
                PlanMaps();
            }
            catch (Exception e)
            {
                Say($"the quest maps weren't added ({e.GetType().Name}: {e.Message}).");
            }
            try
            {
                PlanQuests();
            }
            catch (Exception e)
            {
                Say($"the side quests weren't added ({e.GetType().Name}: {e.Message}).");
            }
            try
            {
                PlanBattles();
            }
            catch (Exception e)
            {
                Say($"the mods' battles weren't changed ({e.GetType().Name}: {e.Message}).");
            }
            try
            {
                PlanTextures();
            }
            catch (Exception e)
            {
                Say(BigTextures.NotLine($"{e.GetType().Name}: {e.Message}"));
            }
            try
            {
                PlanRoomForSaves();
            }
            catch (Exception e)
            {
                Say($"the game's event tables weren't given room for a save's last event ({e.GetType().Name}: "
                    + $"{e.Message}).");
            }
            try
            {
                PlanSaveFallback();
            }
            catch (Exception e)
            {
                Say($"a save standing on a mod's place no mod gives now isn't looked at ({e.GetType().Name}: {e.Message}).");
            }
        }

        /// <summary>(1.26.0) Every mod's own items, in Reloaded-II's order (ItemFile.cs): numbered from 316, past the
        /// game's and WotL Restoration's (Numbers.json's Items, the same number every time), the game given room for
        /// them (ItemRoom.cs, ItemHooks.cs: WotL Restoration's room taken on when it made one, else the same room made),
        /// their names as the Item table loads and their icons; what can't be used is left out and said.</summary>
        void PlanItems()
        {
            var items = new List<ModItem>();
            var problems = new List<string>();
            foreach (var config in _order)
            {
                string folder = Folder(config);
                if (folder.Length == 0)
                    continue;
                items.AddRange(ItemFile.ReadMod(config.ModId, ModName(config), folder, problems));
            }
            foreach (var problem in problems)
                Say($"{problem}; the item is left out.");
            // (2.0.0) War of the Lions' items (WotLItems.cs): asked for by a mod's ModStudioWotLItems.json, which may
            // give its own version of any (a later mod's in place of an earlier's).
            bool asked = false;
            var changed = new Dictionary<int, ModItem>();
            var theirProblems = new List<string>();
            foreach (var config in _order)
            {
                string folder = Folder(config);
                if (folder.Length == 0)
                    continue;
                var theirs = WotLItems.ReadMod(config.ModId, ModName(config), folder, theirProblems);
                if (theirs == null)
                    continue;
                asked = true;
                foreach (var (number, item) in theirs)
                    changed[number] = item;
            }
            foreach (var problem in theirProblems)
                Say($"{problem}; the framework's own stands.");
            // (2.0.6, his answer of 18 November: "yes we should considering WotL Restoration does not have any") Where
            // WotL Restoration has given War of the Lions' items (its room made), they are shown in the menus with the
            // framework's own pictures, his, whether or not a mod asks for them.
            ShowTheirIcons();
            if (items.Count == 0 && !asked)
                return;
            string them = items.Count == 0 ? "War of the Lions' items"
                          : items.Count == 1 ? "the mods' item" : $"the mods' {items.Count} items";
            if (_memory == null)
            {
                Say($"{them} can't be added: the game's program wasn't read.");
                return;
            }
            var image = (ReadOnlySpan<byte>)_memory.Bytes;
            var found = ItemRoom.Find(image, Finder.Sections(image));
            if (!found.Ok)
            {
                Say($"{them} can't be added: {string.Join(", ", found.Missing)} wasn't found in {_memory.Program}. A game "
                    + "update may have changed it: look for a newer " + Name + ".");
                return;
            }
            var places = Found();
            if (places.WorldBank < 0 || places.SheetInit < 0)
            {
                Say($"{them} can't be added: the world map's variables and the tables' setup weren't found in "
                    + $"{_memory.Program}. A game update may have changed them: look for a newer {Name}.");
                return;
            }
            var reloaded = SharedHooks();
            if (reloaded == null)
            {
                Say($"{them} can't be added: Reloaded-II's shared hooks (reloaded.sharedlib.hooks) aren't loaded. "
                    + "Enable them in Reloaded-II.");
                return;
            }
            var numbers = ReadNumbers();
            int firstRow;
            unsafe
            {
                firstRow = ItemHooks.FirstFreeRow(_memory.Base, found);
            }
            var said = new List<string>();
            // (2.0.0) War of the Lions' items first (their rows before the mods' own items'); WotL Restoration's where
            // it has made the items' room, none of the framework's then.
            List<ItemRoom.Given>? wotl = null;
            if (asked && found.Moved)
            {
                Say(WotLItems.TheirsLine);
                // WotL Restoration's are the same items at the same numbers: what each is worn as is known.
                foreach (var fact in WotLItems.Facts)
                    _itemKinds[fact.Number] = fact.Kind;
                // (2.0.6) Random equipment reaches them where a mod's version of one isn't Rare.
                var planned = new Dictionary<int, ModItem>();
                foreach (var fact in WotLItems.Facts)
                    planned[fact.Number] = changed.TryGetValue(fact.Number, out var theirs) ? theirs : WotLItems.Item(fact);
                PlanRandom(image, places, found, planned);
            }
            else if (asked)
                wotl = WotLItems.Plan(firstRow, changed, said, out firstRow);
            var given = ItemRoom.Plan(items, numbers, firstRow, said);
            foreach (var line in said)
                Say(line);
            if (given.Count == 0 && (wotl == null || wotl.Count == 0))
                return;
            ItemHooks? hooks;
            string why;
            unsafe
            {
                // (1.27.0) The game's own towns' Outfitters too, through the stock (places.Stock, -1 when not found).
                hooks = ItemHooks.Arm((IReloadedHooks)reloaded, _memory.Base, _memory.Bytes.Length, found, given,
                                      places.WorldBank, places.SheetInit, Say, out why, places.Stock, wotl);
            }
            if (hooks == null)
            {
                Say($"{them} can't be added: {why}.");
                return;
            }
            _items = hooks;
            // (1.35.0) Items' numbers no name had given: the numbers' new mark, so a save marked before has those items
            // taken out as it loads (Framework.Loaded); a save holding the mods' items marked as it is made.
            numbers.Stamp();
            hooks.Roster = places.Roster;
            KeepNumbers(numbers);
            Say(found.Moved
                ? $"the game's items have room for the mods' items, past WotL Restoration's: {ItemRoom.FirstItem} to "
                  + $"{ItemRoom.LastItem}."
                : $"the game's items have room for the mods' items: {ItemRoom.FirstItem} to {ItemRoom.LastItem}.");
            if (wotl != null && wotl.Count > 0)
            {
                int theirs = 0;
                foreach (var g in wotl)
                {
                    _itemNumbers[g.Item.Key] = g.Number;
                    _itemKinds[g.Number] = g.Item.Kind;
                    _wotlItems[g.Number] = g.Item.Name;
                    if (g.Item.ModId != WotLItems.ModId)
                        theirs++;
                }
                Say(WotLItems.Line(wotl, theirs));
                // (2.0.6, his answer of 18 November: "yes we should do that") Random equipment may give the ones that
                // aren't Rare.
                var planned = new Dictionary<int, ModItem>();
                foreach (var g in wotl)
                    planned[g.Number] = g.Item;
                PlanRandom(image, places, found, planned);
            }
            foreach (var g in given)
            {
                _itemNumbers[g.Item.Key] = g.Number;
                _itemKinds[g.Number] = g.Item.Kind;
                Say(ItemRoom.Line(g));
                // (1.27.0) The game's towns whose Outfitters sell it.
                if (hooks.SellsAtGameTowns && g.Item.Shops.Length > 0)
                    Say(ItemRoom.ShopsLine(g));
            }
        }

        /// <summary>(1.36.0) The numbers the mods' jobs were given (a save's unit in a job no mod gives now is put on a job
        /// of the game's as it loads: JobRoom.Settle), and their hooks, kept as long as the game runs.</summary>
        readonly HashSet<int> _jobsGiven = new HashSet<int>();
        /// <summary>(1.37.0) And the numbers their skillsets were given.</summary>
        readonly HashSet<int> _skillsetsGiven = new HashSet<int>();
        /// <summary>(1.53.0) And each one's number by its key, which a quest's battle's Jobs name (Framework.Plan).</summary>
        readonly Dictionary<string, int> _jobKeys = new Dictionary<string, int>(StringComparer.Ordinal);
        JobHooks? _jobs;
        /// <summary>(1.44.0) The jobs' own textures' two hooks (SpriteTextureHooks), kept while the game runs.</summary>
        SpriteTextureHooks? _textures;
        /// <summary>(2.0.0) The sprites' bigger pictures' four hooks (BigTextureHooks), kept while the game runs, and the
        /// jobs the game was given (a mod's bigger picture may be for a job of its own).</summary>
        BigTextureHooks? _bigTextures;
        /// <summary>(The twenty ninth session) The effects' bigger pictures' hook (EffectTextureHooks), kept while the game
        /// runs.</summary>
        EffectTextureHooks? _effectTextures;
        List<JobRoom.Given> _jobsMade = new List<JobRoom.Given>();
        /// <summary>(1.45.0) The hook that names the jobs' own portraits' files (null where none is made).</summary>
        SpritePortraitHooks? _portraits;
        /// <summary>(1.46.0) The jobs' own icons' and pictures' hooks (JobArtHooks), kept while the game runs.</summary>
        JobArtHooks? _art;
        /// <summary>(1.49.0) The hooks of the mods' jobs on Job Progress (JobTreeHooks), kept while the game runs.</summary>
        JobTreeHooks? _tree;
        /// <summary>(1.41.0) The mods' own action abilities' hooks, kept as long as the game runs.</summary>
        AbilityHooks? _abilities;

        /// <summary>(1.36.0) Every mod's own jobs, in Reloaded-II's order (JobFile.cs): numbered from what the game has free
        /// (Numbers.json's Jobs, the same number every time), made in the game (JobHooks.cs, JobRoom.cs) and given a place
        /// on the job screen; what can't be used is left out and said. (1.41.0) And every mod's own action abilities
        /// (AbilityFile.cs), which a mod's jobs' skillsets name: numbered (Numbers.json's Abilities), put in the places
        /// that name them (AbilityPlan.cs) and made in the game (AbilityHooks.cs) before the jobs are.</summary>
        void PlanJobs()
        {
            var jobs = new List<ModJob>();
            var abilities = new List<ModAbility>();
            var problems = new List<string>();
            var abilityProblems = new List<string>();
            foreach (var config in _order)
            {
                string folder = Folder(config);
                if (folder.Length == 0)
                    continue;
                jobs.AddRange(JobFile.ReadMod(config.ModId, ModName(config), folder, problems));
                abilities.AddRange(AbilityFile.ReadMod(config.ModId, ModName(config), folder, abilityProblems));
            }
            foreach (var problem in problems)
                Say($"{problem}; the job is left out.");
            foreach (var problem in abilityProblems)
                Say($"{problem}; the ability is left out.");
            if (jobs.Count == 0)
            {
                foreach (var ability in abilities)
                    Say(AbilityPlan.UnplacedLine(ability));
                return;
            }
            string them = jobs.Count == 1 ? "the mods' job" : $"the mods' {jobs.Count} jobs";
            if (_memory == null)
            {
                Say($"{them} can't be added: the game's program wasn't read.");
                return;
            }
            var image = (ReadOnlySpan<byte>)_memory.Bytes;
            var found = JobRoom.Find(image, Finder.Sections(image));
            if (!found.Ok)
            {
                Say($"{them} can't be added: {string.Join(", ", found.Missing)} wasn't found in {_memory.Program}. A game "
                    + "update may have changed it: look for a newer " + Name + ".");
                return;
            }
            var places = Found();
            if (places.SheetInit < 0)
            {
                Say($"{them} can't be added: the tables' setup wasn't found in {_memory.Program}. A game update may have "
                    + $"changed it: look for a newer {Name}.");
                return;
            }
            var reloaded = SharedHooks();
            if (reloaded == null)
            {
                Say($"{them} can't be added: Reloaded-II's shared hooks (reloaded.sharedlib.hooks) aren't loaded. Enable "
                    + "them in Reloaded-II.");
                return;
            }
            // (1.39.0) The job screen: with Dark Knight & Onion Knight (Generic) on, its second page's empty places
            // (Zodi's choice); without it, rows of the framework's own after the game's three (JobScreen), where the
            // screen is found.
            bool theirs = TheirsOn();
            JobRoom.Screen? screen = null;
            string? noRows = null;
            if (!theirs)
            {
                screen = JobRoom.FindScreen(image, Finder.Sections(image), found);
                if (!screen.Ok)
                {
                    noRows = string.Join(", ", screen.Missing);
                    screen = null;
                }
            }
            // (1.40.0) More than the game's eleven free job numbers: where the framework's own rows are on the job
            // screen (the other mod's page has eleven empty places and no more) and every place of the game's code that
            // names the job records is found, the numbers past the game's last can be given too (JobRecords).
            JobRecords.Sites? records = null;
            string? noMore = theirs ? "" : null;
            if (screen != null)
            {
                records = JobRecords.Find(image, Finder.Sections(image), found.Records);
                if (!records.Ok)
                {
                    noMore = string.Join(", ", records.Missing);
                    records = null;
                }
            }
            // (1.41.3, his test 96) Arithmeticks's list, made to reach the jobs' own skillsets where it is found.
            int arithmeticks = JobRoom.FindArithmeticks(image, Finder.Sections(image), out string? noArithmeticks);
            // (1.41.4, his word on test 97) And the units' two choices of an Arithmeticks spell.
            var (think, random) = JobRoom.FindArithmeticksUnits(image, Finder.Sections(image), out string? noUnits);
            // (1.53.0, Zodi's order of 13 November: "jobs in a quest's battle") And a unit of a battle's file in a mod's
            // job learning its job's abilities.
            var battle = JobRoom.FindBattleUnits(image, Finder.Sections(image), out string? noBattle);
            var numbers = ReadNumbers();
            var said = new List<string>();
            // (1.55.0) A mod's job may be the game's own Dark Knight or Onion Knight: not where the other mod is on.
            var given = JobRoom.Plan(jobs, numbers, said, JobRoom.OpenSkillsets(image, found),
                                     records != null ? JobRecords.Numbers : JobRoom.FreeNumbers,
                                     theirs ? JobRoom.TheirGameJobs : null);
            foreach (var line in said)
                Say(line);
            // (1.55.0, Zodi's word of 15 November: "What ever War of the Lions does we should do") Where a mod gives the
            // game's Dark Knight: its first ability is made War of the Lions' Sanguine Sword and Holy Sword's sixth place
            // Chant again (DarkKnightAbilities), its places found now, before anything of the program is changed (the
            // tables' readers name the game's own tables until the abilities' hooks are made).
            DarkKnightAbilities.Sites? darkSites = given.Exists(g => g.Job.Game == JobFile.DarkKnight)
                ? DarkKnightAbilities.Find(image, Finder.Sections(image), found.Skillsets) : null;
            if (given.Count < jobs.Count && records == null && jobs.Count > JobRoom.FreeNumbers.Length)
                Say(noMore == "" ? JobRecords.TheirsLine
                    : noMore != null ? $"more job numbers can't be made: {noMore} wasn't found in {_memory.Program}. A game "
                                       + $"update may have changed it: look for a newer {Name}."
                    : $"more job numbers can't be made: {noRows} wasn't found in {_memory.Program}.");
            if (given.Count == 0)
            {
                foreach (var ability in abilities)
                    Say(AbilityPlan.UnplacedLine(ability));
                return;
            }
            // (1.41.0) The abilities: numbered, put in the places of the jobs' skillsets that name them and, where any
            // does, made in the game. Before the jobs are made, whose skillsets' records are written as they are: a
            // place that names an ability holds the game's ability it is like, or nothing where the abilities can't be
            // made.
            var abilitiesSaid = new List<string>();
            var abilitiesGiven = AbilityFile.Plan(abilities, numbers, abilitiesSaid);
            var plan = AbilityPlan.Make(given, abilitiesGiven, abilitiesSaid);
            foreach (var line in abilitiesSaid)
                Say(line);
            bool made = false;
            if (plan.Places.Count > 0)
            {
                string abilityThem = abilitiesGiven.Count == 1 ? "the mods' ability" : $"the mods' {abilitiesGiven.Count} abilities";
                string Empty = $"The places of the jobs' skillsets that name {(abilitiesGiven.Count == 1 ? "it" : "them")} are "
                               + "left empty.";
                try
                {
                    // Found in the program as it is now (the items' changes made), so that a place another part has
                    // changed isn't taken.
                    var abilitySites = AbilityHooks.Find(image, Finder.Sections(image));
                    if (!abilitySites.Ok)
                        Say($"{abilityThem} can't be added: {string.Join(", ", abilitySites.Missing)} wasn't found in "
                            + $"{_memory.Program}. A game update may have changed it: look for a newer {Name}. {Empty}");
                    else
                    {
                        string abilityWhy;
                        unsafe
                        {
                            _abilities = AbilityHooks.Arm((IReloadedHooks)reloaded, _memory, abilitySites, abilitiesGiven,
                                                          plan.Places, places.SheetInit, found.At["Build"], places.SaveLoad, Say,
                                                          out abilityWhy);
                        }
                        if (_abilities == null)
                            Say($"{abilityThem} can't be added: {abilityWhy}. {Empty}");
                        made = _abilities != null;
                    }
                }
                catch (Exception e)
                {
                    Say($"{abilityThem} can't be added ({e.GetType().Name}: {e.Message}). {Empty}");
                    made = _abilities != null;
                }
            }
            given = plan.Jobs(made);
            _jobsMade = given;
            // The longer table is made only where a job has a number past the game's last.
            int past = given.FindAll(g => g.Number >= JobRecords.GameCount).Count;
            if (past == 0)
                records = null;
            // (1.42.0) A job's own sprites: where a job has a Look of its own and every place of the game's code they
            // need is found (in the program as it is now, so that a place another part has changed isn't taken), two
            // sprite numbers each. Otherwise each looks like its Like, as before.
            SpriteRoom.Sites? sprites = null;
            if (given.Exists(g => g.Job.LookLike > 0))
            {
                var spriteSites = SpriteRoom.Find(image, Finder.Sections(image));
                if (!spriteSites.Ok)
                    Say($"the jobs' own looks can't be made: {string.Join(", ", spriteSites.Missing)} wasn't found in "
                        + $"{_memory.Program}. A game update may have changed it: look for a newer {Name}. Each job looks like "
                        + "the game's job it is like.");
                else
                {
                    var spritesSaid = new List<string>();
                    if (SpriteRoom.Plan(given, numbers, spritesSaid, image, spriteSites) > 0)
                        sprites = spriteSites;
                    foreach (var line in spritesSaid)
                        Say(line);
                    // (1.53.0) The load's coloring of the figures, where a job's own sprites wear colors of their own.
                    if (sprites != null && sprites.WalkMissing != null && given.Exists(g => g.Sprite >= 0 && g.Job.HasColors))
                        Say(SpriteRoom.WalkNotLine(sprites.WalkMissing, _memory.Program, Name));
                }
            }
            // (1.44.0) A job's own textures: where a job with sprites of its own has textures of its own and both of the
            // routines that read a texture are found, the framework answers them (SpriteTextures), before the sprites'
            // table names them. Otherwise each such job wears its Look's textures. (1.44.2) A routine another mod has
            // hooked is taken where the game's program file has it; and hooks that can't be made leave the jobs as they
            // are, said (SpriteTextureHooks.Arm).
            if (sprites != null && given.Exists(g => g.Sprite >= 0 && g.Job.HasTextures))
            {
                var textureSites = SpriteTextures.Find(image, Finder.Sections(image), ProgramFile.Of(_memory.ProgramPath, image));
                if (!textureSites.Ok)
                    Say(SpriteTextures.NotLine($"{string.Join(", ", textureSites.Missing)} wasn't found in {_memory.Program}. "
                                               + $"A game update may have changed it: look for a newer {Name}"));
                else
                {
                    string texturesWhy;
                    unsafe
                    {
                        _textures = SpriteTextureHooks.Arm((IReloadedHooks)reloaded, _memory, textureSites, given, Say, out texturesWhy);
                    }
                    if (_textures == null)
                        Say(SpriteTextures.NotLine(texturesWhy));
                }
            }
            // (1.45.0) A job's own portraits: where a job with sprites of its own has portraits of its own and every place
            // of the game's code they need is found, the face's file's routine names the job's own part lists for its own
            // portraits' numbers (SpritePortraitHooks), and its sprites are given those numbers (SpriteRoom, through
            // JobHooks). Otherwise each such job has its Look's portraits.
            if (sprites != null && given.Exists(g => g.Sprite >= 0 && g.Job.HasPortraits))
            {
                var portraitSites = SpritePortraits.Find(image, Finder.Sections(image), ProgramFile.Of(_memory.ProgramPath, image));
                if (!portraitSites.Ok)
                    Say(SpritePortraits.NotLine($"{string.Join(", ", portraitSites.Missing)} wasn't found in {_memory.Program}. "
                                                + $"A game update may have changed it: look for a newer {Name}"));
                else
                {
                    _portraits = SpritePortraitHooks.Arm((IReloadedHooks)reloaded, _memory, portraitSites, given, Say,
                                                         out string portraitsWhy);
                    if (_portraits == null)
                        Say(SpritePortraits.NotLine(portraitsWhy));
                    else
                        sprites.Portraits = portraitSites;
                }
            }
            // (1.46.0) A job's own icons and pictures (Zodi's word of 12 November: "The modder can pick either their own
            // files or one of the game's for the job icon and skillset icon but not for the man art or woman art. The modder
            // should be able to choose their own art for male and or female or no art for the male and or female."; no art is
            // no picture anywhere, his word): where the four routines they are answered at are found, the framework's hooks
            // answer every job's pictures (its own, or none) and its own icons (JobArtHooks), and each job's own parts are
            // marked so its rows name them (JobRoom, JobArt through JobHooks). Otherwise each shows what it showed before;
            // the game's icons a job picks are its rows only.
            if (given.Count > 0)
            {
                var artSites = JobArt.Find(image, Finder.Sections(image), ProgramFile.Of(_memory.ProgramPath, image));
                if (!artSites.Ok)
                    Say(JobArt.NotLine($"{string.Join(", ", artSites.Missing)} wasn't found in {_memory.Program}. A game update "
                                       + $"may have changed it: look for a newer {Name}"));
                else
                {
                    _art = JobArtHooks.Arm((IReloadedHooks)reloaded, _memory, artSites, given, Say, out string artWhy);
                    if (_art == null)
                        Say(JobArt.NotLine(artWhy));
                }
            }
            // (1.49.0) The mods' jobs on Job Progress (Zodi's words of 13 November: "All jobs new and vanilla jobs together
            // on the Job Progress (the tree)"; the view sliding over to them, his choice): where the framework's own rows
            // of the job screen are made and the tree's places are found (before anything of the program is changed), its
            // boxes are made beside the game's and its cursor goes to them (JobTree, JobTreeHooks). Otherwise Job Progress
            // is the game's: where its places aren't found or its hooks can't be made, the log says so.
            JobTree.Sites? treeSites = screen != null ? JobTree.Find(image, Finder.Sections(image), screen.TreeJob) : null;
            // (1.55.0) The five portrait routines' second read of the job, where a mod gives the game's Dark Knight or Onion
            // Knight: found in the program as it is now. Where they aren't, those jobs keep the game's own portraits there.
            Dictionary<string, int>? special = null;
            // (1.55.1) The game's Onion Knight whose words for its level 8 Job Summary shows (its reads found), said once
            // the jobs are given. (1.55.2) And whose description for its level 8 the job screen's window shows.
            string? summaryWho = null, helpWordsWho = null;
            if (given.Exists(g => g.Game))
            {
                var specialMissing = new List<string>();
                special = JobRoom.FindSpecial(image, Finder.Sections(image), specialMissing);
                if (specialMissing.Count > 0)
                    Say(JobRoom.SpecialNotLine(specialMissing, _memory.Program, Name));
                // (1.55.1) Job Summary's two reads, where the game's Onion Knight a mod gives has words for its level 8:
                // found in the program as it is now. Where they aren't, Job Summary shows its words at every level.
                JobRoom.Given? onion = given.Find(g => g.Number == JobFile.OnionKnight && g.Job.MasteredWords);
                if (onion != null)
                {
                    var summaryMissing = new List<string>();
                    foreach (var site in JobRoom.FindSummary(image, Finder.Sections(image), summaryMissing))
                        special[site.Key] = site.Value;
                    if (summaryMissing.Count > 0)
                        Say(JobRoom.SummaryNotLine(summaryMissing, _memory.Program, Name));
                    else
                        summaryWho = onion.Job.Who;
                }
                // (1.55.2) The job screen's window's read of a job's words, where the game's Onion Knight a mod gives has a
                // description for its level 8: found in the program as it is now. Where it isn't, the window shows its
                // description at every level.
                JobRoom.Given? described = given.Find(g => g.Number == JobFile.OnionKnight && g.Job.MasteredDescription != null);
                if (described != null)
                {
                    var helpMissing = new List<string>();
                    foreach (var site in JobRoom.FindHelpWords(image, Finder.Sections(image), helpMissing))
                        special[site.Key] = site.Value;
                    if (helpMissing.Count > 0)
                        Say(JobRoom.HelpWordsNotLine(helpMissing, _memory.Program, Name));
                    else
                        helpWordsWho = described.Job.Who;
                }
            }
            string why;
            unsafe
            {
                _jobs = JobHooks.Arm((IReloadedHooks)reloaded, _memory, found, given, places.SheetInit, Say, out why, places,
                                     n => numbers.NameOf(Numbers.JobsKind, n), JobProgressFolders(), screen, records,
                                     arithmeticks, think, random, sprites, noBattle == null ? battle : null, special);
            }
            if (_jobs == null)
            {
                Say($"{them} can't be added: {why}.");
                return;
            }
            if (treeSites != null && _jobs.Tree != null && _jobs.Rows != null)
            {
                string treeLine = JobTree.NotFoundLine(treeSites.Missing, _memory.Program, Name);
                if (treeSites.Ok)
                {
                    _tree = JobTreeHooks.Arm((IReloadedHooks)reloaded, _memory, treeSites, places, _jobs.Tree, _jobs.Rows, Say,
                                             out string treeWhy);
                    treeLine = JobTree.NotLine(treeWhy);
                }
                if (_tree == null)
                {
                    _jobs.TreeOff();
                    Say(treeLine);
                }
            }
            KeepNumbers(numbers);
            foreach (var g in given)
            {
                _jobsGiven.Add(g.Number);
                // (1.55.0) The game's own Dark Knight's skillset is the game's, and a quest's battle names the mods' own jobs.
                if (!g.Game)
                {
                    _skillsetsGiven.Add(g.Skillset);
                    _jobKeys[g.Job.Key] = g.Number;
                }
                Say(JobRoom.Line(g));
            }
            if (summaryWho != null)
                Say(JobRoom.SummaryLine(summaryWho));
            if (helpWordsWho != null)
                Say(JobRoom.HelpWordsLine(helpWordsWho));
            if (darkSites != null)
                MakeDarkAbilities(darkSites);
            // (1.41.0) The abilities made, and the ones no job's skillset holds.
            if (made)
                foreach (var g in abilitiesGiven)
                    Say(AbilityFile.Line(g));
            foreach (var g in plan.Unplaced)
                Say(AbilityPlan.UnplacedLine(g.Ability));
            if (records != null)
                Say(JobRecords.Line(past));
            Say(JobRoom.ArithmeticksLine(noArithmeticks, _memory.Program, Name));
            Say(JobRoom.ArithmeticksUnitsLine(noUnits, _memory.Program, Name));
            Say(JobRoom.BattleUnitsLine(noBattle, _memory.Program, Name));
            if (theirs)
                PlaceJobs(given);
            else if (screen != null)
                Say(JobScreen.Line(given.Count));
            else
                Say($"the mods' jobs have no place on the job screen: {noRows} wasn't found in {_memory.Program}. A game update "
                    + $"may have changed it: look for a newer {Name}.");
        }

        /// <summary>(1.55.0) The game's Dark Knight's first ability made War of the Lions' Sanguine Sword and Holy Sword's
        /// sixth place Chant again, each part where it is still the game's own (DarkKnightAbilities), and said; the jobs'
        /// hooks told, for its row of the Ability table. Where a place isn't found, or a fault comes first, nothing of it
        /// is changed and the log says so.</summary>
        void MakeDarkAbilities(DarkKnightAbilities.Sites sites)
        {
            var memory = _memory!;
            if (!sites.Ok)
            {
                Say(DarkKnightAbilities.NotLine(sites.Missing, memory.Program, Name));
                return;
            }
            try
            {
                var kept = new List<string>();
                var changes = DarkKnightAbilities.Changes(memory.Bytes, sites, kept, out bool sanguine);
                foreach (var change in changes)
                    memory.Writing(change.At, change.Bytes.Length,
                                   () => change.Bytes.CopyTo(memory.At(change.At, change.Bytes.Length)));
                if (_jobs != null)
                    _jobs.Sanguine = sanguine;
                Say(DarkKnightAbilities.Line(sanguine, kept));
            }
            catch (Exception e)
            {
                Say($"the game's Dark Knight's first ability stays the game's copy of Chant ({e.GetType().Name}: {e.Message}).");
            }
        }

        /// <summary>(1.38.0) Where the units' progress in the mods' jobs is kept beside a save (JobProgress): a folder of
        /// the framework's beside each of the game's save folders, and one in Reloaded-II's settings folder for this
        /// mod.</summary>
        List<string> JobProgressFolders()
        {
            var folders = new List<string>();
            try
            {
                foreach (var saves in NumbersCopies.SaveFolders(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments)))
                    folders.Add(System.IO.Path.Combine(saves, JobProgress.Folder));
            }
            catch (Exception)
            {
            }
            try
            {
                string settings = ConfigFolder();
                if (!string.IsNullOrEmpty(settings))
                    folders.Add(System.IO.Path.Combine(settings, JobProgress.Folder));
            }
            catch (Exception)
            {
            }
            return folders;
        }

        /// <summary>(1.36.0) The jobs given a place on the job screen: with Dark Knight &amp; Onion Knight (Generic) on, its
        /// second page's empty places (Zodi's choice); said when they have none.</summary>
        void PlaceJobs(List<JobRoom.Given> given)
        {
            var numbers = given.ConvertAll(g => g.Number);
            foreach (var active in _loader.GetActiveMods())
            {
                if (active.Generic.ModId != JobRoom.OtherMod)
                    continue;
                string? stop;
                try
                {
                    stop = JobRoom.OnTheirPage(active.Mod, numbers);
                }
                catch (Exception e) when (e is not OutOfMemoryException)
                {
                    stop = $"{e.GetType().Name}: {e.Message}";
                }
                Say(stop == null
                    ? $"the job screen's second page lists the mods' job{(numbers.Count == 1 ? "" : "s")} after Dark Knight and Onion Knight."
                    : $"the mods' jobs have no place on the job screen: Dark Knight & Onion Knight (Generic) isn't as "
                      + $"this was made for ({stop}).");
                return;
            }
        }

        /// <summary>(1.28.0) Every mod's looks for the game's own weapons in battle (ItemLooks.cs: its
        /// ModStudioItemLooks.json), in Reloaded-II's order (a later mod's look for an item in place of an earlier's,
        /// said): each written where the game's own ItemSpritePair finds that item's sprite pair (found by its bytes,
        /// as the items' sites are), said; what can't be used is left out and said.</summary>
        void PlanLooks()
        {
            var looks = new List<ItemLook>();
            var problems = new List<string>();
            foreach (var config in _order)
            {
                string folder = Folder(config);
                if (folder.Length == 0)
                    continue;
                looks.AddRange(ItemLooks.ReadMod(config.ModId, ModName(config), folder, problems));
            }
            foreach (var problem in problems)
                Say($"{problem}; that look is left out.");
            if (looks.Count == 0)
                return;
            var said = new List<string>();
            var planned = ItemLooks.Plan(looks, said);
            foreach (var line in said)
                Say(line);
            if (_memory == null)
            {
                Say("the game's weapons' looks in battle can't be changed: the game's program wasn't read.");
                return;
            }
            var image = (ReadOnlySpan<byte>)_memory.Bytes;
            var found = ItemRoom.Find(image, Finder.Sections(image));
            if (!found.At.TryGetValue("ItemSpritePair", out int pairAt))
            {
                Say($"the game's weapons' looks in battle can't be changed: the item's ItemSpritePair function wasn't "
                    + $"found in {_memory.Program}. A game update may have changed it: look for a newer {Name}.");
                return;
            }
            unsafe
            {
                ItemLooks.Give(_memory.Base, pairAt, planned, Say);
            }
        }

        /// <summary>(1.7.1) The game's load of a save hooked: a save standing on a mod's place no mod gives now
        /// (`_given`) goes on from that place's home kept, said. (1.13.0) Once some quest's flag was ever numbered, the
        /// same hook looks at the save's mark of the numbers it was made with (Framework.Loaded); (1.35.0) or some
        /// mod's item, what the save holds of the mods' items too. (1.35.1, Zodi's test 72) Hooked whenever it is
        /// found: until 1.35.1 only once some mod's place was ever numbered, but a free lets a mod's places go with
        /// their homes (his save stood on Hermit's Rest, place 48, freed with test 71's mod: Ramza was nowhere). What
        /// wasn't found is said only when something was ever numbered.</summary>
        void PlanSaveFallback()
        {
            if (_memory == null)
                return;
            // (1.32.0) The quests' own numbers when they were planned and kept: the mark a flag set gives a save is
            // theirs (their new one, Numbers.Stamp), whether or not every copy could be written.
            var numbers = _questNumbers ?? ReadNumbers();
            // (1.35.0) A save holding the mods' items marked with them as it is made (ItemHooks).
            if (_items != null)
                _items.MarkWith = numbers.Id;
            bool placesNumbered = numbers.Used(Destinations.Kind).Count > 0;
            bool marks = numbers.Used("Flags").Count > 0 || numbers.Used(Numbers.ItemsKind).Count > 0;
            bool sayWhy = placesNumbered || marks;
            string what = placesNumbered || !marks
                ? "a save standing on a mod's place no mod gives now can't be moved off it"
                : "a save's mark of the side quests' numbers it was made with can't be looked at";
            var places = Found();
            if (!places.SaveFallback)
            {
                if (sayWhy)
                    Say($"{what}: {string.Join(", ", places.MissingForSaveFallback)} wasn't found in "
                        + $"{_memory.Program}. A game update may have changed it: look for a newer {Name}.");
                return;
            }
            var reloaded = SharedHooks();
            if (reloaded == null)
            {
                if (sayWhy)
                    Say($"{what}: Reloaded-II's shared hooks (reloaded.sharedlib.hooks) aren't loaded. Enable them "
                        + "in Reloaded-II.");
                return;
            }
            _saveHook = MakeSaveHook(reloaded, places, numbers, marks);
            // (1.35.0) Without the party the save's load fills, only its bag is looked at for the mods' items.
            if (marks && numbers.Used(Numbers.ItemsKind).Count > 0 && places.Roster < 0)
                Say($"what a save's units wear of the mods' items can't be looked at as it loads: "
                    + $"{string.Join(", ", places.MissingForRoster)} wasn't found in {_memory.Program}. A game update "
                    + $"may have changed it: look for a newer {Name}.");
        }

        unsafe SaveFallbackHook MakeSaveHook(IReloadedHooks reloaded, Places places, Numbers numbers, bool marks)
            => SaveFallbackHook.Make(reloaded, _memory!.Base, places, _given, numbers, Say, marks, _jobsGiven, _skillsetsGiven,
                                     !TheirsOn());

        /// <summary>(1.55.0) Whether Dark Knight &amp; Onion Knight (Generic) is on (it keeps the game's Dark Knight and Onion
        /// Knight, and the mods' jobs on its page).</summary>
        bool TheirsOn()
        {
            if (_loader == null)
                return false;
            foreach (var active in _loader.GetActiveMods())
                if (active.Generic.ModId == JobRoom.OtherMod)
                    return true;
            return false;
        }

        /// <summary>Where the side quests and the places join the game, found once.</summary>
        Places Found() => _found ??= Places.Find(_memory!.Bytes);

        string Folder(IModConfigV1 config)
        {
            try
            {
                return _loader!.GetDirectoryForModId(config.ModId) ?? "";
            }
            catch (Exception)
            {
                return "";
            }
        }

        /// <summary>A mod's name in the log: its ModName (its id if it has none); (1.22.0) with its id beside it when
        /// another mod loaded has the same name (Framework.LogName, Zodi's ninth).</summary>
        string ModName(IModConfigV1 config)
            => Framework.LogName(config.ModId, config.ModName, _order.ConvertAll(c => (c.ModId, c.ModName)));

        void Apply(IModConfigV1 config)
        {
            string folder = Folder(config);
            string path = Path.Combine(folder, SetupFile.Name);
            if (folder.Length == 0 || !File.Exists(path))
                return;
            string mod = ModName(config);
            if (_table == null || _memory == null)
            {
                Say($"{mod} changes events' setup, which isn't applied: the table wasn't found.");
                return;
            }
            var problems = new List<string>();
            List<Change> changes;
            try
            {
                changes = SetupFile.Read(File.ReadAllText(path), problems);
            }
            catch (IOException e)
            {
                Say($"{mod}'s {SetupFile.Name} can't be read ({e.Message}).");
                return;
            }
            foreach (var problem in problems)
                Say($"{mod}'s {SetupFile.Name}: {problem}; left out.");
            var table = _table;
            var memory = _memory;
            List<string> said = new List<string>();
            memory.Writing(table.Address, table.Bytes, () =>
                said = _applier.Apply(memory.At(table.Address, table.Bytes), table, mod, changes));
            foreach (var line in said)
                Say(line);
        }

        // --- the side quests ---------------------------------------------------

        /// <summary>(1.13.0) Where the numbers given are kept, most trusted first (NumbersCopies.Places, Zodi's choice):
        /// beside the game's saves (each Steam ID's folder of them in the player's Documents), Reloaded-II's settings
        /// folder for this mod (which an update of it leaves alone), and its own folder.</summary>
        List<NumbersCopies.Place> NumbersPlaces()
        {
            string documents, settings, own;
            try
            {
                documents = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
            }
            catch (Exception)
            {
                documents = "";
            }
            try
            {
                settings = ConfigFolder();
            }
            catch (Exception)
            {
                settings = "";
            }
            try
            {
                own = _loader!.GetDirectoryForModId(_self) ?? "";
            }
            catch (Exception)
            {
                own = "";
            }
            return NumbersCopies.Places(documents, settings.Length > 0 ? Path.Combine(settings, Numbers.FileName) : "",
                                        own.Length > 0 ? Path.Combine(own, Numbers.FileName) : "");
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        string ConfigFolder() => _loader is IModLoaderV3 three ? three.GetModConfigDirectory(_self) ?? "" : "";

        /// <summary>(1.29.0, Zodi's sixth of 3 November: "Tick in Reloaded-II") Its setting ticked in Reloaded-II, the
        /// numbers of every mod not enabled now freed (Numbers.Free), said mod by mod, and the setting unticked.</summary>
        void FreeNumbersIfAsked()
        {
            var configurator = new Configurator();
            configurator.SetConfigDirectory(ConfigFolder());
            string own = "";
            try
            {
                own = _loader!.GetDirectoryForModId(_self) ?? "";
            }
            catch (Exception)
            {
                own = "";
            }
            configurator.SetModDirectory(own);
            var config = configurator.Load();
            if (!config.FreeNumbers)
                return;
            var enabled = new HashSet<string>(StringComparer.Ordinal);
            foreach (var mod in _order)
                enabled.Add(mod.ModId);
            var numbers = ReadNumbers();
            var freed = numbers.Free(enabled);
            Say(Numbers.FreedLine(freed));
            if (freed.Count > 0)
                KeepNumbers(numbers);
            config.FreeNumbers = false;
            config.Save();
        }

        /// <summary>Reloaded-II's shared hooks, or null and why not.</summary>
        [MethodImpl(MethodImplOptions.NoInlining)]
        IReloadedHooks? SharedHooks()
        {
            IReloadedHooks? hooks = null;
            _loader!.GetController<IReloadedHooks>()?.TryGetTarget(out hooks);
            return hooks;
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        unsafe Hooks MakeHooks(object reloaded, Places places, Framework plan)
            => Hooks.Make((IReloadedHooks)reloaded, _memory!.Base, places, Say, plan, ModRows(), _groundSlot,
                          _dungeonData);

        /// <summary>(1.8.0) The screen's rows past its end, as the places given made them (Destinations.RowCount: up
        /// to the highest number given, a number kept for a mod not loaded now leaving its row empty).</summary>
        int ModRows()
        {
            int most = Destinations.FirstNumber - 1;
            foreach (int number in _given)
                most = Math.Max(most, number);
            return most - Destinations.FirstNumber + 1;
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        unsafe PlaceHooks MakePlaceHooks(object reloaded, Places places, List<MapPlace> mapPlaces, List<MapRoad> mapRoads,
                                         List<TravelRoad> travel, nint ready, List<Destination> destinations)
            => PlaceHooks.Make((IReloadedHooks)reloaded, _memory!.Base, places, Say, mapPlaces, mapRoads, travel, ready,
                               destinations);

        /// <summary>(1.14.0) Where the game's program is as loaded (the base its pointers are relocated from).</summary>
        unsafe long ModuleBase() => (long)(nint)_memory!.Base;

        /// <summary>(1.14.0) The quests' own squads given to the game's program (DeploySquads.Arm): why not, or null.</summary>
        unsafe string? ArmSquads(DeploySquads.Found found, List<(int Number, byte[] Bytes)> squads)
        {
            string? why = null;
            var memory = _memory!;
            try
            {
                memory.Writing(found.First, 16, () =>
                    why = DeploySquads.Arm(memory.Base, memory.Bytes.Length, found, squads));
            }
            catch (Exception e)
            {
                why = $"{e.GetType().Name}: {e.Message}";
            }
            return why;
        }

        /// <summary>(1.7.0) The places given to the game's program (Destinations.Arm).</summary>
        unsafe string? ArmDestinations(Places places, List<Destination> destinations)
        {
            string? why = Destinations.Arm(_memory!.Base, _memory.Bytes.Length, places, destinations, out nint data);
            // (1.21.0) A mod's dungeon's slots are in the places' data.
            if (why == null && Destinations.HasDungeons(places, destinations))
                _dungeonData = data;
            return why;
        }

        /// <summary>The numbers given and kept, from every copy (NumbersCopies.Read); what reading them said, each once
        /// as the game starts.</summary>
        Numbers ReadNumbers()
        {
            var said = new List<string>();
            var numbers = NumbersCopies.Read(NumbersPlaces(), said);
            foreach (var line in said)
                if (_numbersSaid.Add(line))
                    Say(line);
            return numbers;
        }

        /// <summary>(1.13.0) The numbers written into every copy when they changed (or a copy was missing or said
        /// other).</summary>
        void KeepNumbers(Numbers numbers) => NumbersCopies.Keep(NumbersPlaces(), numbers, Say);

        /// <summary>(1.5.0) The byte that lets the mods' roads be travelled (0 until their tables have their rows),
        /// kept as long as the game runs.</summary>
        static unsafe nint ReadyByte() => (nint)System.Runtime.InteropServices.NativeMemory.AllocZeroed(16);

        /// <summary>(1.5.0) The roads given to the game's program for travel (Travel.Arm); (1.17.0) where a mod's own
        /// place's roll goes (`groundSlot`: 0 without the roll's native code).</summary>
        unsafe string? ArmTravel(Places places, List<TravelRoad> travel, nint ready, out List<RoadBattle> battles,
                                 out nint groundSlot)
            => Travel.Arm(_memory!.Base, _memory.Bytes.Length, places, travel, ready, out battles, out groundSlot);

        /// <summary>(1.9.0) Whether the setup and finish tables were moved (EventRoom.cs), and whether that was tried
        /// (once: what stopped it is said once).</summary>
        bool _eventRoom, _eventRoomTried;

        /// <summary>(1.9.0) The setup and finish tables moved with room for 8192 events (once, before any quest is
        /// planned), the helper's table from then on the moved one; whether they were (said with `because`), else why
        /// not said.</summary>
        unsafe bool ArmEventRoom(string because)
        {
            if (_eventRoom || _eventRoomTried || _table == null || _memory == null)
                return _eventRoom;
            _eventRoomTried = true;
            var image = _memory.Bytes;
            var sites = EventRoom.Find(image, Finder.Sections(image), _table.Address, out string why);
            if (sites == null)
            {
                Say($"side quests' events stay under 887: {why} wasn't found in {_memory.Program}. A game update may "
                    + "have changed it: look for a newer " + Name + ".");
                return false;
            }
            var moved = EventRoom.Arm(_memory.Base, image.Length, sites, _table, out why);
            if (moved == null)
            {
                Say($"side quests' events stay under 887: {why}.");
                return false;
            }
            _table = moved;
            _eventRoom = true;
            Say($"the game's event setup and finish tables have room for {EventRoom.Events} events: {because}.");
            return true;
        }

        /// <summary>(1.11.0) The quests' events that say the game's event they were copied from (their From) play the
        /// map's doors and moving parts as that event does (MapAnimations.cs); without what that needs, as their own
        /// numbers, which open none, said.</summary>
        unsafe void ArmMapAnimations(Framework plan)
        {
            var copied = new List<(int Number, int From)>();
            foreach (var planned in plan.Events)
                if (planned.Event.From > 0)
                    copied.Add((planned.Number, planned.Event.From));
            if (copied.Count == 0 || _memory == null)
                return;
            var image = _memory.Bytes;
            var sites = MapAnimations.Find(image, Finder.Sections(image), out string why);
            if (sites == null)
            {
                Say($"{why} wasn't found in {_memory.Program}: the side quests' events copied from the game's open no "
                    + "door of the game's. A game update may have changed it: look for a newer " + Name + ".");
                return;
            }
            if (!MapAnimations.Arm(_memory.Base, image.Length, sites, copied, out why))
            {
                Say($"the side quests' events copied from the game's open no door of the game's: {why}.");
                return;
            }
            Say(copied.Count == 1
                ? "the side quests' event copied from the game's plays the map's doors and moving parts as the game's "
                  + "event it was copied from."
                : $"the side quests' {copied.Count} events copied from the game's play the map's doors and moving parts "
                  + "as the game's events they were copied from.");
        }

        /// <summary>(1.9.0) With no quest loaded, the tables' room made all the same once some quest's event was ever
        /// numbered past 886 (Numbers.json): a save made after it played keeps it as the last event played, whose word
        /// the game reads in the finish table by its number, past the game's own table but for the room.</summary>
        void PlanRoomForSaves()
        {
            if (_eventRoom || _table == null || _memory == null)
                return;
            var numbers = ReadNumbers();
            foreach (int number in numbers.Used("Events"))
                if (number > Framework.LastEvent)
                {
                    ArmEventRoom("a side quest's event was once numbered past 886, and a save may have played it");
                    return;
                }
        }

        /// <summary>(1.8.0) A mod's own places' names (as PlanPlaces read them; else read now).</summary>
        List<string> PlaceNamesOf(string modId, string folder)
        {
            if (_placeNames.TryGetValue(modId, out var names))
                return names;
            names = PlaceFile.ReadMod(modId, modId, folder, new List<string>()).ConvertAll(p => p.Name);
            _placeNames[modId] = names;
            return names;
        }

        void PlanQuests()
        {
            var quests = new List<Quest>();
            var problems = new List<string>();
            var otherScripts = new HashSet<int>();
            foreach (var config in _order)
            {
                string folder = Folder(config);
                if (folder.Length == 0)
                    continue;
                quests.AddRange(QuestFile.ReadMod(config.ModId, ModName(config), folder, problems,
                                                  PlaceNamesOf(config.ModId, folder), MapFile.NamesIn(folder)));
                QuestFile.ScriptNumbers(folder, otherScripts);
            }
            foreach (var problem in problems)
                Say($"{problem}; the quest is left out.");
            // (1.17.0) The mods' battle grounds with random battles of their own are planned with the quests: their
            // battles numbered as the quests' are, their units handed over as the quests' are.
            var grounds = new List<(MapPlace Place, int Number)>(_grounds);
            // (1.18.0) And the mods' towns with a menu of their own (their Outfitters, their taverns' rumors).
            var towns = new List<(MapPlace Place, int Number)>(_menuTowns);
            // (1.20.0) And the mods' towns darkened once one of their quests' flags is set: without the quest, said.
            var dark = new List<MapPlace>(_darkPlaces);
            // (1.21.0) And the mods' dungeons (their floors' battles numbered as the quests' are).
            var dungeons = new List<(MapPlace Place, int Number)>(_dungeons);
            void DarkUnplanned()
            {
                if (quests.Count == 0)
                    foreach (var place in dark)
                        Say(Framework.DarkLine(place, -1));
            }
            if (quests.Count == 0 && grounds.Count == 0 && towns.Count == 0 && dungeons.Count == 0)
            {
                DarkUnplanned();
                return;
            }
            string them = quests.Count > 0 ? (quests.Count == 1 ? "a side quest" : $"{quests.Count} side quests")
                          : grounds.Count > 0 ? "the mods' battle grounds' random battles"
                          : towns.Count > 0 ? "the mods' towns' menus"
                          : "the mods' dungeons";
            if (_table == null || _memory == null)
            {
                Say($"{them} can't be added: the game's event setup table wasn't found.");
                return;
            }
            var places = Found();
            if (!places.All)
            {
                Say($"{them} can't be added: {string.Join(", ", places.Missing)} wasn't found in {_memory.Program}. "
                    + "A game update may have changed it: look for a newer " + Name + ".");
                return;
            }
            // (1.17.0) A battle ground's random battles need what the roll keeps found, and the roll's native code
            // made (the mods' roads travelled with it); without the first, said.
            if (grounds.Count > 0 && !places.GroundBattles)
            {
                Say("the mods' battle grounds' own random battles aren't fought: "
                    + $"{string.Join(", ", places.RoadBattles ? places.MissingForGroundBattles : places.MissingForRoadBattles)} "
                    + $"wasn't found in {_memory.Program}. A game update may have changed it: look for a newer "
                    + Name + ".");
                grounds.Clear();
            }
            else if (_groundSlot == 0)
                grounds.Clear();
            if (!places.Battles)
            {
                // A quest with battles of its own needs the battles' units' place; the rest play.
                foreach (var quest in quests.FindAll(q => q.Battles.Count > 0))
                    Say($"{quest.Name} ({quest.ModName}) is left out: {string.Join(", ", places.MissingForBattles)} "
                        + $"wasn't found in {_memory.Program}. A game update may have changed it: look for a newer "
                        + Name + ".");
                quests.RemoveAll(q => q.Battles.Count > 0);
            }
            // (1.18.0) A town's menu opens by its record (Destinations); its Outfitter's own items need the stock's site
            // found: without it, said, an Outfitter selling nothing (as the game's code gives a place past its towns).
            if (towns.Count > 0 && !places.TownMenus)
                Say($"the mods' towns' Outfitters sell nothing: {string.Join(", ", places.MissingForTownMenus)} wasn't "
                    + $"found in {_memory.Program}. A game update may have changed it: look for a newer " + Name + ".");
            if (towns.Count > 0 && !places.Rumors)
                Say($"the mods' towns' taverns tell no side quest's rumor: {string.Join(", ", places.MissingForRumors)} "
                    + $"wasn't found in {_memory.Program}. A game update may have changed it: look for a newer "
                    + Name + ".");
            // (1.21.0) A dungeon needs its own sites found and its native code made with the places'.
            if (dungeons.Count > 0 && !places.Dungeons)
            {
                Say("the mods' dungeons list no floor: "
                    + $"{string.Join(", ", places.MissingForDungeons.Count > 0 ? places.MissingForDungeons : places.MissingForGroundBattles)} "
                    + $"wasn't found in {_memory.Program}. A game update may have changed it: look for a newer "
                    + Name + ".");
                dungeons.Clear();
            }
            else if (_dungeonData == 0)
                dungeons.Clear();
            // (1.23.0) A dungeon's list in its own looks, and its battles started at once (Zodi's test 49), once their
            // sites were found; else as the Deep's list, and with a random battle's white flash.
            if (dungeons.Count > 0 && !places.DungeonLooks)
                Say("the mods' dungeons' lists show Midlight's Deep's name, words and art: "
                    + $"{string.Join(", ", places.MissingForDungeonLooks.Count > 0 ? places.MissingForDungeonLooks : places.MissingForMenuArt)} "
                    + $"wasn't found in {_memory.Program}. A game update may have changed it: look for a newer "
                    + Name + ".");
            if (dungeons.Count > 0 && !places.InstantBattles)
                Say("the mods' dungeons' battles start with a random battle's white flash: "
                    + $"{string.Join(", ", places.MissingForInstantBattles)} wasn't found in {_memory.Program}. A game "
                    + "update may have changed it: look for a newer " + Name + ".");
            // (1.25.0) A quest's start waiting at a dungeon's floor needs the world map's start of an event found.
            bool floorStarts = places.FloorStarts;
            if (quests.Exists(q => q.Starts.Exists(s => s.Floor.Length > 0)) && !places.FloorStarts)
                Say("the side quests' starts waiting at the mods' dungeons' floors are left out: "
                    + $"{string.Join(", ", places.MissingForFloorStarts.Count > 0 ? places.MissingForFloorStarts : places.MissingForDungeons)} "
                    + $"wasn't found in {_memory.Program}. A game update may have changed it: look for a newer "
                    + Name + ".");
            if (quests.Count == 0 && grounds.Count == 0 && towns.Count == 0 && dungeons.Count == 0)
            {
                DarkUnplanned();
                return;
            }
            if (!places.Travel)
                // The quests play; one waiting where you stand stops travel on, as the game's events do.
                Say($"{string.Join(", ", places.MissingForTravel)} wasn't found in {_memory.Program}: a side "
                    + "quest's event waiting where you stand stops travel on, as the game's own do. A game update "
                    + "may have changed it: look for a newer " + Name + ".");
            if (!places.Passing && quests.Exists(q => q.Starts.Exists(s => !s.StopsPassing)))
                // (1.2.4) The quests play; a start that waits until its place is chosen stops a travel
                // passing through, as the game's events do.
                Say($"{string.Join(", ", places.MissingForPassing)} wasn't found in {_memory.Program}: a side "
                    + "quest's event that waits until its place is chosen stops a travel passing through, as the "
                    + "game's own do. A game update may have changed it: look for a newer " + Name + ".");
            if (!places.Markers && quests.Exists(q => q.Marker.Length > 0))
                // (1.2.5) The quests play; their markers aren't shown.
                Say($"{string.Join(", ", places.MissingForMarkers)} wasn't found in {_memory.Program}: the side "
                    + "quests' markers aren't shown on the world map. A game update may have changed it: look for a "
                    + "newer " + Name + ".");
            if (!places.Markers && dark.Count > 0)
                // (1.20.0) A darkened town is darkened as the world map is set up, not as it shows a place.
                Say($"{string.Join(", ", places.MissingForMarkers)} wasn't found in {_memory.Program}: the mods' towns "
                    + "darkened once a quest's flag is set are darkened only as the world map is set up again. A game "
                    + "update may have changed it: look for a newer " + Name + ".");
            if (!places.Rewards && quests.Exists(q => q.Events.Exists(e => e.Reward != null)))
                // (1.31.0) The quests play; their rewards aren't given.
                Say($"{string.Join(", ", places.MissingForRewards)} wasn't found in {_memory.Program}: the side "
                    + "quests' rewards aren't given. A game update may have changed it: look for a newer " + Name + ".");
            if (!places.Rumors && quests.Exists(q => q.Rumors.Count > 0))
                // (1.15.0) The quests play; their rumors aren't told, so a start waiting for one to be read never plays.
                Say($"{string.Join(", ", places.MissingForRumors)} wasn't found in {_memory.Program}: the side quests' "
                    + "rumors aren't told in the taverns. A game update may have changed it: look for a newer "
                    + Name + ".");
            object? reloaded;
            try
            {
                reloaded = SharedHooks();
            }
            catch (Exception)
            {
                reloaded = null;
            }
            if (reloaded == null)
            {
                Say($"{them} can't be added: Reloaded-II's shared hooks (reloaded.sharedlib.hooks) aren't loaded. "
                    + "Enable them in Reloaded-II.");
                return;
            }
            var numbers = ReadNumbers();
            // (1.9.0) Room for hundreds of quests: the setup and finish tables moved before any is planned, their
            // events numbered up to 8191; else the game's 886, said. (1.17.0) Not for battle grounds alone: their
            // random battles are no events.
            bool room = quests.Count > 0 && ArmEventRoom("side quests' events may be numbered past 886");
            var table = _table;
            var memory = _memory;
            int first = Framework.FirstEmpty(memory.At(table.Address, table.Bytes), table.Slots, out int free,
                                             room ? EventRoom.Events : Framework.SearchedSlots);
            // (1.14.0) The quests' own deploy areas: given the program as squads past its 768 (DeploySquads.cs), once
            // its squads and their pointers are found; else each battle keeps its setup's, said.
            DeploySquads.Found? squadsFound = null;
            bool questAreas = quests.Exists(q => q.Events.Exists(e => e.Battle != null && e.Battle.Deploy.Count > 0));
            if (questAreas || grounds.Count > 0 || dungeons.Count > 0)
            {
                squadsFound = DeploySquads.Find(memory.Bytes, ModuleBase(), out string squadsWhy);
                if (squadsFound == null && questAreas)
                    Say($"the side quests' own deploy areas aren't used, each battle starting where its setup says: "
                        + $"{squadsWhy} in {memory.Program}. A game update may have changed them: look for a newer "
                        + Name + ".");
                if (squadsFound == null && grounds.Count > 0)
                    Say($"the mods' battle grounds' own random battles aren't fought: {squadsWhy} in {memory.Program}. "
                        + "A game update may have changed them: look for a newer " + Name + ".");
                if (squadsFound == null && dungeons.Count > 0)
                    Say($"the mods' dungeons list no floor: {squadsWhy} in {memory.Program}. A game update may have "
                        + "changed them: look for a newer " + Name + ".");
            }
            var plan = Framework.Plan(table.SlotOf.Keys, free, otherScripts, quests, numbers, _placeNumbers,
                                      room ? EventRoom.LastEvent : Framework.LastEvent, _mapNumbers, _mapBases,
                                      squadsFound != null, places.Rumors, squadsFound != null ? grounds : null,
                                      places.Battles, towns, dark, squadsFound != null ? dungeons : null,
                                      floorStarts, _itemNumbers, _jobKeys);
            if (plan.Squads.Count > 0)
            {
                string? notArmed = ArmSquads(squadsFound!.Value, plan.Squads);
                if (notArmed != null)
                {
                    if (questAreas)
                        Say($"the side quests' own deploy areas aren't used, each battle starting where its setup says: "
                            + $"{notArmed}.");
                    if (plan.Grounds.Count > 0)
                        Say($"the mods' battle grounds' own random battles aren't fought: {notArmed}.");
                    if (plan.Dungeons.Count > 0)
                        Say($"the mods' dungeons list no floor: {notArmed}.");
                    plan = Framework.Plan(table.SlotOf.Keys, free, otherScripts, quests, numbers, _placeNumbers,
                                          room ? EventRoom.LastEvent : Framework.LastEvent, _mapNumbers, _mapBases,
                                          false, places.Rumors, null, places.Battles, towns, dark, null, true,
                                          _itemNumbers, _jobKeys);
                }
            }
            int written = 0;
            memory.Writing(table.Address, table.Bytes, () =>
                written = plan.WriteRecords(memory.At(table.Address, table.Bytes), first));
            if (written < plan.Records.Count)
            {
                Say($"{them} can't be added: only {written} of their {plan.Records.Count} setup "
                    + $"record{(plan.Records.Count == 1 ? "" : "s")} went in.");
                return;
            }
            try
            {
                _hooks = MakeHooks(reloaded, places, plan);
                _questPlan = plan;
                // (1.26.0) A mod's town's Outfitter lists its own items after the game's.
                _hooks.Items = _items;
                // (1.8.0) A quest's marker at a mod's own place shown as soon as the places' pieces are added too;
                // (1.20.0) and a mod's town darkened once its quest's flag is set.
                var hooks = _hooks;
                // (1.34.0) The mods' roads grayed with a mod's town darkened once its quest's flag is set.
                if (_placeHooks != null)
                    _placeHooks.Darkened = hooks.IsDarkened;
                if (_placeHooks != null && (hooks.MarksModPlaces || hooks.DarkensModPlaces))
                {
                    hooks.Darken = _placeHooks.Darken;
                    _placeHooks.PiecesAdded = screen =>
                    {
                        hooks.ModMarkers(screen);
                        hooks.ModDarkened(screen);
                    };
                }
            }
            catch (Exception e)
            {
                Say($"{them} can't be added: the game's functions couldn't be hooked ({e.GetType().Name}: "
                    + $"{e.Message}).");
                return;
            }
            KeepNumbers(numbers);
            _questNumbers = numbers;
            foreach (var line in plan.Said)
                Say(line);
            // (1.11.0) The quests' events copied from the game's play its maps' doors as those events.
            ArmMapAnimations(plan);
        }

        // --- (2.0.0) the mods' battles ------------------------------------------------

        /// <summary>(2.0.0, Zodi's points of 16 November 2026) Every mod's units of the game's battles and its buried
        /// treasures (BattleFile.cs: its ModStudioBattles.json), in Reloaded-II's order, with the quests' own battles'
        /// units' items past 255: planned once every item and job has its number (after the items, the jobs and the
        /// quests), then joined to the game (BattleHooks.cs). What can't be used is left out and said.</summary>
        void PlanBattles()
        {
            var mods = new List<BattleFile.ModBattles>();
            var problems = new List<string>();
            foreach (var config in _order)
            {
                string folder = Folder(config);
                if (folder.Length == 0)
                    continue;
                var read = BattleFile.ReadMod(config.ModId, ModName(config), folder, problems);
                if (read != null)
                    mods.Add(read);
            }
            foreach (var problem in problems)
                Say($"{problem}; it is left out.");
            var quests = _questPlan?.WideItems ?? new List<BattleFile.QuestItems>();
            // (2.0.6) Random equipment reaching War of the Lions' items needs the units' equipment hooked, battles of the
            // mods' or none.
            bool randoms = _randomFound != null && _randomExtras != null && _randomPlanned != null;
            if (mods.Count == 0 && quests.Count == 0 && !randoms)
                return;
            var plan = BattleFile.Make(mods, quests, _itemNumbers,
                                       n => _itemKinds.TryGetValue(n, out var kind) ? kind : BattleFile.GameKind(n),
                                       _jobKeys);
            foreach (var line in plan.Said)
                Say($"{line}.");
            if (!plan.Any && !randoms)
                return;
            if (_memory == null)
            {
                Say("the mods' battles can't be changed: the game's program wasn't read.");
                return;
            }
            var places = Found();
            var reloaded = SharedHooks();
            if (reloaded == null)
            {
                Say("the mods' battles can't be changed: Reloaded-II's shared hooks (reloaded.sharedlib.hooks) aren't "
                    + "loaded. Enable them in Reloaded-II.");
                return;
            }
            unsafe
            {
                _battles = BattleHooks.Arm(reloaded, _memory.Base, places, plan, Say, _randomFound, _randomExtras,
                                           _randomPlanned);
            }
            if (_battles == null)
                return;
            if (_hooks != null)
                _battles.QuestEntry = _hooks.EntryOf;
            if (_questPlan != null)
                _battles.BattleName = _questPlan.BattleNameOf;
            if (plan.Any)
                Say(BattleFile.Line(plan));
            if (_battles.Randoms)
                Say(RandomItems.Line(_randomExtras!));
        }

        /// <summary>(2.0.6) Random equipment reaching War of the Lions' items (`planned`: each by its number as the
        /// framework plans it), the ones that aren't Rare: the game's function and its asks found now, the hook made with
        /// the battles' (PlanBattles); said where they can't be found.</summary>
        void PlanRandom(ReadOnlySpan<byte> image, Places places, ItemRoom.Found found, Dictionary<int, ModItem> planned)
        {
            var extras = RandomItems.Extras(planned);
            if (extras.Count == 0 || _memory == null)
                return;
            var random = RandomItems.Find(image, places.UnitEquipment, found.At["ItemCommon"], found.At["ItemWeapon"]);
            if (!random.Ok)
            {
                Say($"Random equipment can't give War of the Lions' items: {string.Join(", ", random.Missing)} wasn't "
                    + $"found in {_memory.Program}. A game update may have changed it: look for a newer {Name}.");
                return;
            }
            _randomFound = random;
            _randomExtras = extras;
            _randomPlanned = planned;
        }

        /// <summary>(2.0.6) Where WotL Restoration has given War of the Lions' items (its room made: ItemRoom's Moved),
        /// each of the 40 shown in the menus with the framework's own pictures (his: WotLItems.IconName), the game's
        /// own two icon paths hooked for their numbers alone (WotLIcons.cs); said.</summary>
        void ShowTheirIcons()
        {
            if (_memory == null || _theirIcons != null)
                return;
            var image = (ReadOnlySpan<byte>)_memory.Bytes;
            var found = ItemRoom.Find(image, Finder.Sections(image));
            if (!found.Ok || !found.Moved)
                return;
            var reloaded = SharedHooks();
            if (reloaded == null)
            {
                Say("WotL Restoration's War of the Lions items can't be shown with the framework's own pictures: "
                    + "Reloaded-II's shared hooks (reloaded.sharedlib.hooks) aren't loaded. Enable them in Reloaded-II.");
                return;
            }
            unsafe
            {
                _theirIcons = WotLIcons.Arm((IReloadedHooks)reloaded, _memory.Base, found, Say);
            }
            if (_theirIcons != null)
                Say(WotLIcons.Line);
        }

        /// <summary>(2.0.0) The mods' bigger pictures of sprites (BigTextures.cs: each mod's ModStudioTextures.json), in
        /// Reloaded-II's order, planned once the jobs have their sprites (a picture may be for a job of its mod's own),
        /// then joined to the game (BigTextureHooks.cs); and (the twenty ninth session) of effects, named in the same file
        /// (EffectTextures.cs, EffectTextureHooks.cs). What can't be used is left out and said.</summary>
        void PlanTextures()
        {
            var mods = new List<BigTextures.ModTextures>();
            var problems = new List<string>();
            foreach (var config in _order)
            {
                string folder = Folder(config);
                if (folder.Length == 0)
                    continue;
                var read = BigTextures.ReadMod(config.ModId, ModName(config), folder, problems);
                if (read != null)
                    mods.Add(read);
            }
            foreach (var problem in problems)
                Say($"{problem}; it is left out.");
            if (mods.Count == 0)
                return;
            var plan = BigTextures.Make(mods, (modId, job, woman) =>
            {
                var g = _jobsMade.Find(made => made.Job.ModId == modId && made.Job.Name == job);
                return g != null && g.Sprite >= 0 && g.Textures[woman ? 1 : 0] ? SpriteTextures.Entry(g.Sprite + (woman ? 1 : 0)) : -1;
            });
            foreach (var line in plan.Said)
                Say($"{line}.");
            var effects = EffectTextures.Make(mods.ConvertAll(mod => mod.Effects));
            foreach (var line in effects.Said)
                Say($"{line}.");
            if (plan.Any)
                ArmSprites(plan);
            if (effects.Any)
                ArmEffects(effects);
        }

        /// <summary>(2.0.0) The sprites' bigger pictures joined to the game (BigTextureHooks.cs), or why not said.</summary>
        void ArmSprites(BigTextures.Plan plan)
        {
            if (_memory == null)
            {
                Say(BigTextures.NotLine("the game's program wasn't read"));
                return;
            }
            var reloaded = SharedHooks();
            if (reloaded == null)
            {
                Say(BigTextures.NotLine("Reloaded-II's shared hooks (reloaded.sharedlib.hooks) aren't loaded. Enable them in "
                                        + "Reloaded-II"));
                return;
            }
            var image = (ReadOnlySpan<byte>)_memory.Bytes;
            var sites = BigTextures.Find(image, Finder.Sections(image), ProgramFile.Of(_memory.ProgramPath, image));
            if (!sites.Ok)
            {
                Say(BigTextures.NotLine($"{string.Join(", ", sites.Missing)} wasn't found in {_memory.Program}. A game update "
                                        + $"may have changed it: look for a newer {Name}"));
                return;
            }
            string why;
            unsafe
            {
                _bigTextures = BigTextureHooks.Arm(reloaded, _memory, sites, plan, Say, out why);
            }
            if (_bigTextures == null)
            {
                Say(BigTextures.NotLine(why));
                return;
            }
            Say(BigTextures.Line(plan));
        }

        /// <summary>(The twenty ninth session) The effects' bigger pictures joined to the game (EffectTextureHooks.cs), or
        /// why not said.</summary>
        void ArmEffects(EffectTextures.Plan plan)
        {
            if (_memory == null)
            {
                Say(EffectTextures.NotLine("the game's program wasn't read"));
                return;
            }
            var reloaded = SharedHooks();
            if (reloaded == null)
            {
                Say(EffectTextures.NotLine("Reloaded-II's shared hooks (reloaded.sharedlib.hooks) aren't loaded. Enable them "
                                           + "in Reloaded-II"));
                return;
            }
            var image = (ReadOnlySpan<byte>)_memory.Bytes;
            var sites = EffectTextures.Find(image, Finder.Sections(image), ProgramFile.Of(_memory.ProgramPath, image));
            if (!sites.Ok)
            {
                Say(EffectTextures.NotLine($"{string.Join(", ", sites.Missing)} wasn't found in {_memory.Program}. A game "
                                           + $"update may have changed it: look for a newer {Name}"));
                return;
            }
            string why;
            unsafe
            {
                _effectTextures = EffectTextureHooks.Arm(reloaded, _memory, sites, plan, Say, out why);
            }
            if (_effectTextures == null)
            {
                Say(EffectTextures.NotLine(why));
                return;
            }
            Say(EffectTextures.Line(plan));
        }

        // --- (1.10.0) the quest maps -------------------------------------------------

        /// <summary>Every mod's quest maps, in Reloaded-II's order: numbered from 129 (kept with the side quests'
        /// numbers, so a save made in a quest's battle finds its map again), the program changed and hooked so that
        /// each loads as one of the game's (MapRoom.cs, MapHooks.cs); what can't be used is left out and said.</summary>
        void PlanMaps()
        {
            var maps = new List<QuestMap>();
            var problems = new List<string>();
            foreach (var config in _order)
            {
                string folder = Folder(config);
                if (folder.Length == 0)
                    continue;
                maps.AddRange(MapFile.ReadMod(config.ModId, ModName(config), folder, problems));
            }
            foreach (var problem in problems)
                Say($"{problem}; the quest map is left out.");
            if (maps.Count == 0)
                return;
            string them = maps.Count == 1 ? "a quest map" : $"{maps.Count} quest maps";
            if (_memory == null)
            {
                Say($"{them} can't be added: the game's program wasn't read.");
                return;
            }
            var image = _memory.Bytes;
            var sites = MapRoom.Find(image, Finder.Sections(image), out string why);
            var places = Found();
            if (sites == null || places.SheetInit < 0)
            {
                Say($"{them} can't be added: {(sites == null ? why : "the tables' setup")} wasn't found in "
                    + $"{_memory.Program}. A game update may have changed it: look for a newer " + Name + ".");
                return;
            }
            object? reloaded;
            try
            {
                reloaded = SharedHooks();
            }
            catch (Exception)
            {
                reloaded = null;
            }
            if (reloaded == null)
            {
                Say($"{them} can't be added: Reloaded-II's shared hooks (reloaded.sharedlib.hooks) aren't loaded. "
                    + "Enable them in Reloaded-II.");
                return;
            }
            var said = new List<string>();
            var numbers = ReadNumbers();
            var given = MapRoom.Plan(maps, numbers, image, sites, said);
            foreach (var line in said)
                Say(line);
            if (given.Count == 0)
                return;
            string? not;
            try
            {
                not = ArmMaps(reloaded, places, sites, given);
            }
            catch (Exception e)
            {
                not = $"{e.GetType().Name}: {e.Message}";
            }
            if (not != null)
            {
                Say($"the quest maps can't be added: {not}.");
                return;
            }
            KeepNumbers(numbers);
            foreach (var g in given)
            {
                _mapNumbers[g.Map.Key] = g.Number;
                _mapBases[g.Number] = g.Map.Base;
                Say($"the quest map {g.Map.Folder} ({g.Map.ModName}) is map {g.Number}, made from map {g.Map.Base}.");
            }
        }

        /// <summary>(1.10.0) The quest maps' memory made, their hooks made, the program changed, the hooks active; why
        /// not, or null.</summary>
        [MethodImpl(MethodImplOptions.NoInlining)]
        unsafe string? ArmMaps(object reloaded, Places places, MapRoom.Sites sites, List<MapRoom.Given> given)
        {
            var block = MapRoom.Make(_memory!.Base, _memory.Bytes.Length, sites, given, out string why);
            if (block == null)
                return why;
            var hooks = MapHooks.Make((IReloadedHooks)reloaded, _memory.Base, places, sites, block, given, Say, out why);
            if (hooks == null)
                return why;
            string? not = MapRoom.Join(_memory.Base, _memory.Bytes.Length, sites, block);
            if (not != null)
                return not;
            hooks.Activate();
            _mapHooks = hooks;
            return null;
        }

        // --- (1.3.0) the mods' own places ----------------------------------------

        /// <summary>Every mod's own places, in Reloaded-II's order, shown on the world map through a hook of the
        /// screen's setup of its places' pieces, and (1.4.0) every mod's own roads (their places the mod's own as
        /// read), drawn there through the same hook; what can't be used is left out and said.</summary>
        void PlanPlaces()
        {
            var mapPlaces = new List<MapPlace>();
            var mapRoads = new List<MapRoad>();
            var problems = new List<string>();
            var roadProblems = new List<string>();
            foreach (var config in _order)
            {
                string folder = Folder(config);
                if (folder.Length == 0)
                    continue;
                var own = PlaceFile.ReadMod(config.ModId, ModName(config), folder, problems);
                _placeNames[config.ModId] = own.ConvertAll(p => p.Name);
                mapPlaces.AddRange(own);
                mapRoads.AddRange(RoadFile.ReadMod(config.ModId, ModName(config), folder, own.ConvertAll(p => p.Name),
                                                   roadProblems));
            }
            foreach (var problem in problems)
                Say($"{problem}; the place is left out.");
            foreach (var problem in roadProblems)
                Say($"{problem}; the road is left out.");
            if (mapPlaces.Count == 0 && mapRoads.Count == 0)
                return;
            string them = mapRoads.Count == 0 ? "the mods' own places"
                          : mapPlaces.Count == 0 ? "the mods' own roads" : "the mods' own places and roads";
            if (_memory == null)
            {
                Say($"{them} can't be shown on the world map: the game's program wasn't read.");
                return;
            }
            var places = Found();
            if (mapPlaces.Count > 0 && !places.NewPlaces)
            {
                Say($"the mods' own places can't be shown on the world map: {string.Join(", ", places.MissingForPlaces)} "
                    + $"wasn't found in {_memory.Program}. A game update may have changed it: look for a newer "
                    + Name + ".");
                mapPlaces.Clear();
            }
            if (mapRoads.Count > 0 && !places.NewRoads)
            {
                Say($"the mods' own roads can't be drawn on the world map: {string.Join(", ", places.MissingForRoads)} "
                    + $"wasn't found in {_memory.Program}. A game update may have changed it: look for a newer "
                    + Name + ".");
                mapRoads.Clear();
            }
            if (mapPlaces.Count == 0 && mapRoads.Count == 0)
                return;
            object? reloaded;
            try
            {
                reloaded = SharedHooks();
            }
            catch (Exception)
            {
                reloaded = null;
            }
            if (reloaded == null)
            {
                Say($"{them} can't be shown on the world map: Reloaded-II's shared hooks "
                    + "(reloaded.sharedlib.hooks) aren't loaded. Enable them in Reloaded-II.");
                return;
            }
            // (1.7.0) The mods' places the game goes to: numbered past its 48 (kept with the side quests' numbers,
            // so a save standing on one finds it), the program given what it keeps for a place before the game runs.
            var destinations = new List<Destination>();
            Numbers? numbers = null;
            if (mapPlaces.Count > 0 && !places.Destinations)
                Say("the mods' own places are shown only, their roads to them drawn only: "
                    + $"{string.Join(", ", places.MissingForDestinations)} wasn't found in {_memory.Program}. A game "
                    + "update may have changed it: look for a newer " + Name + ".");
            else if (mapPlaces.Count > 0)
            {
                var said = new List<string>();
                numbers = ReadNumbers();
                destinations = Destinations.Plan(mapPlaces, numbers, said);
                foreach (var line in said)
                    Say(line);
                if (destinations.Count > 0)
                {
                    string? not;
                    try
                    {
                        not = ArmDestinations(places, destinations);
                    }
                    catch (Exception e)
                    {
                        not = $"{e.GetType().Name}: {e.Message}";
                    }
                    if (not != null)
                    {
                        Say($"the mods' own places are shown only, their roads to them drawn only: {not}.");
                        destinations.Clear();
                    }
                    else
                    {
                        // (1.23.0) The world map's location list: the mods' places in it once its sites were found.
                        if (!places.Locations)
                            Say("the mods' own places aren't in the world map's location list: "
                                + $"{string.Join(", ", places.MissingForLocations)} wasn't found in {_memory.Program}. A "
                                + "game update may have changed it: look for a newer " + Name + ".");
                        foreach (var d in destinations)
                        {
                            Say($"{d.Place.Name} ({d.Place.ModName}) is place {d.Number} of the world map.");
                            _given.Add(d.Number);
                            _placeNumbers[$"{d.Place.ModId}/{d.Place.Name}"] = d.Number;
                            // (1.17.0) A battle ground with random battles of its own: planned with the side quests.
                            if (!d.Place.Town && d.Place.Battles.Count > 0)
                                _grounds.Add((d.Place, d.Number));
                            // (1.18.0) A town with a menu of its own: planned with them (a quest's rumor may name it).
                            if (d.Place.Town && d.Place.Menu != null)
                                _menuTowns.Add((d.Place, d.Number));
                            // (1.21.0) A dungeon: planned with them (a floor may wait for one of their flags).
                            if (d.Place.Dungeon)
                                _dungeons.Add((d.Place, d.Number));
                        }
                    }
                }
            }
            // (1.5.0) The roads between two of the game's places, travelled as the game's own: numbered from 51,
            // given to the program before the game runs, their rows added as their tables load; (1.7.0) and the roads
            // to the mods' places the game goes to.
            var travelSaid = new List<string>();
            var travel = Travel.Plan(mapRoads, travelSaid, destinations);
            foreach (var line in travelSaid)
                Say(line);
            // (1.7.1) Each place's home kept with its number: where a save standing on it goes on from once no mod
            // gives it (SaveFallback.cs).
            if (numbers != null)
            {
                foreach (var (place, home) in SaveFallback.Homes(destinations, travel))
                    numbers.Home(place, home);
                KeepNumbers(numbers);
            }
            nint ready = 0;
            if (travel.Count > 0 && !places.Journeys)
            {
                Say("the mods' roads between the game's places aren't travelled, drawn only: "
                    + $"{string.Join(", ", places.MissingForJourneys)} wasn't found in {_memory.Program}. A game update "
                    + "may have changed it: look for a newer " + Name + ".");
                travel.Clear();
            }
            if (travel.Count > 0)
            {
                ready = ReadyByte();
                string? not;
                var battles = new List<RoadBattle>();
                nint slot = 0;
                try
                {
                    not = ArmTravel(places, travel, ready, out battles, out slot);
                }
                catch (Exception e)
                {
                    not = $"{e.GetType().Name}: {e.Message}";
                }
                if (not != null)
                {
                    Say($"the mods' roads between the game's places aren't travelled, drawn only: {not}.");
                    travel.Clear();
                }
                else
                {
                    _groundSlot = slot;
                    foreach (var road in travel)
                        Say($"{road.Road.Name} ({road.Road.ModName}) is road {road.Number} of the world map, between "
                            + $"its places {road.From} and {road.To}.");
                    // (1.6.0) Where each starts random battles, as the game's road whose entrance it uses there.
                    foreach (var battle in battles)
                        Say($"{battle.Road.Road.Name} ({battle.Road.Road.ModName}) arriving at place {battle.Place} "
                            + $"starts the random battles of the game's road {battle.GameRoad} there, from place "
                            + $"{battle.From}.");
                    if (!places.RoadBattles)
                        Say("the mods' roads start no random battles: "
                            + $"{string.Join(", ", places.MissingForRoadBattles)} wasn't found in {_memory.Program}. "
                            + "A game update may have changed it: look for a newer " + Name + ".");
                }
            }
            try
            {
                _placeHooks = MakePlaceHooks(reloaded, places, mapPlaces, mapRoads, travel, ready, destinations);
                // (1.20.0) The mods' towns darkened once a quest's flag is set: planned with the side quests.
                _darkPlaces.AddRange(mapPlaces.FindAll(p => p.Town && p.Darkened != null));
            }
            catch (Exception e)
            {
                Say($"{them} can't be shown on the world map: its setup couldn't be hooked "
                    + $"({e.GetType().Name}: {e.Message}).");
            }
        }

        public void Suspend() { }
        public void Resume() { }
        public void Unload() { }
        public bool CanUnload() => false;
        public bool CanSuspend() => false;
    }
}
