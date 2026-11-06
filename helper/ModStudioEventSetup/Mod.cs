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
        readonly Dictionary<string, int> _itemNumbers = new Dictionary<string, int>(StringComparer.Ordinal);
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
            if (items.Count == 0)
                return;
            string them = items.Count == 1 ? "the mods' item" : $"the mods' {items.Count} items";
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
            var given = ItemRoom.Plan(items, numbers, firstRow, said);
            foreach (var line in said)
                Say(line);
            if (given.Count == 0)
                return;
            ItemHooks? hooks;
            string why;
            unsafe
            {
                // (1.27.0) The game's own towns' Outfitters too, through the stock (places.Stock, -1 when not found).
                hooks = ItemHooks.Arm((IReloadedHooks)reloaded, _memory.Base, _memory.Bytes.Length, found, given,
                                      places.WorldBank, places.SheetInit, Say, out why, places.Stock);
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
            foreach (var g in given)
            {
                _itemNumbers[g.Item.Key] = g.Number;
                Say(ItemRoom.Line(g));
                // (1.27.0) The game's towns whose Outfitters sell it.
                if (hooks.SellsAtGameTowns && g.Item.Shops.Length > 0)
                    Say(ItemRoom.ShopsLine(g));
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
            => SaveFallbackHook.Make(reloaded, _memory!.Base, places, _given, numbers, Say, marks);

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
                                      floorStarts, _itemNumbers);
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
                                          _itemNumbers);
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
