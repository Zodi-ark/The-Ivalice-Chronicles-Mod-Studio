// Mod Studio Framework: (2.0.0) a mod's units of any battle, the items past
// 255 its units wear and its buried treasures hold, joined to the running
// game through Reloaded-II's shared hooks. Part of The Ivalice Chronicles
// Mod Studio, GPL-3.0.
//
// Made only when some mod asks for one of them (BattleFile.cs: its
// ModStudioBattles.json, or a quest's battle's Items). Three hooks, each of a
// function of the game's that runs first, whole, each made only where its
// site was found as measured (Places.FindBattleUnits) and only when a mod
// needs it:
//
// - the game's own changes to a battle's units as it loads
//   (Places.UnitOverrides): then the mods' units' bits are written into the
//   battle's 16 entries (BattleFile.Apply), and the battle and its block are
//   kept, so a unit made from one of those entries is known by its place;
// - the putting of an entry's equipment on its unit (Places.UnitEquipment):
//   then the unit's items past 255 are put on as words (BattleFile.Wear),
//   before the game works the unit's stats out. The unit is known by its
//   entry: one of the block the game's changes were last made to, while the
//   battle loading is still that battle (Places.EncounterNumber); else one of
//   a quest's own battle's (QuestEntry, the side quests' hooks');
// - the map's load (Places.MapTreasures): then the mods' items are written
//   over the map's treasures where the battle reads them (BattleFile.Bury).
//
// Nothing here throws into the game: a fault is said once.
using System;
using System.Collections.Generic;
using Reloaded.Hooks.Definitions;
using Reloaded.Hooks.Definitions.X64;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    public sealed unsafe class BattleHooks
    {
        /// <summary>The game's own changes to a battle's units: the battle, its block of 16 entries, 16 flags, 16 rows.
        /// </summary>
        [Function(CallingConventions.Microsoft)]
        public delegate nint OverridesFunction(int battle, nint block, nint flags, nint rows);

        /// <summary>The putting of an entry's equipment on its unit: the unit, the entry.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate void EquipmentFunction(nint unit, nint entry);

        /// <summary>The map's load: the map; what it answers is the game's own.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate nint MapLoadFunction(int map);

        readonly byte* _start;
        readonly Places _places;
        readonly BattleFile.Plan _plan;
        readonly Action<string> _say;
        readonly object _lock = new object();
        readonly HashSet<string> _saidOnce = new HashSet<string>();
        IHook<OverridesFunction>? _overrides;
        IHook<EquipmentFunction>? _equipment;
        IHook<MapLoadFunction>? _mapLoad;
        /// <summary>The battle the game's changes were last made to, and its block.</summary>
        int _battle = -1;
        nint _block;
        /// <summary>Which quest's own battle's unit an entry is (the side quests' hooks': Hooks.EntryOf), set once the
        /// quests are planned; null: none.</summary>
        public Func<nint, (int Battle, int Slot)?>? QuestEntry { get; set; }
        /// <summary>What each battle is called in a line: a quest's own by its name (the side quests' plan's), else its
        /// number.</summary>
        public Func<int, string>? BattleName { get; set; }

        BattleHooks(byte* start, Places places, BattleFile.Plan plan, Action<string> say)
        {
            _start = start;
            _places = places;
            _plan = plan;
            _say = say;
        }

        void SayOnce(string line)
        {
            lock (_lock)
                if (!_saidOnce.Add(line))
                    return;
            _say(line);
        }

        string Named(int battle)
        {
            string name = BattleName?.Invoke(battle) ?? "";
            return name.Length > 0 ? name : $"battle {battle}";
        }

        /// <summary>What can't be done of the plan here, in words (each a sentence's end): the units' changes, their items
        /// past 255, the buried treasures. Empty: all of it can.</summary>
        public static List<string> Missing(Places places, BattleFile.Plan plan)
        {
            var lines = new List<string>();
            if (plan.UnitsChanged > 0 && !places.Units)
                lines.Add($"the mods' units aren't changed: {string.Join(", ", places.MissingForUnits)} wasn't found.");
            if (plan.UnitsWearing > 0 && !places.WideItems)
                lines.Add("the mods' units aren't given their items past 255: "
                          + $"{string.Join(", ", places.MissingForWideItems)} wasn't found.");
            if (plan.TreasuresChanged > 0 && !places.Treasures)
                lines.Add("the mods' buried treasures aren't changed: "
                          + $"{string.Join(", ", places.MissingForTreasures)} wasn't found.");
            return lines;
        }

        /// <summary>The hooks the plan needs, made and active; what can't be done said. Null when nothing can.</summary>
        public static BattleHooks? Arm(IReloadedHooks reloaded, byte* start, Places places, BattleFile.Plan plan,
                                       Action<string> say)
        {
            foreach (string line in Missing(places, plan))
                say(line);
            var hooks = new BattleHooks(start, places, plan, say);
            long loaded = (long)(nint)start;
            bool units = plan.UnitsChanged > 0 && places.Units;
            bool wears = plan.UnitsWearing > 0 && places.WideItems;
            bool treasures = plan.TreasuresChanged > 0 && places.Treasures;
            if (!units && !wears && !treasures)
                return null;
            // Each kept before it is active, so a call the moment it is finds the game's own function. A unit's items
            // need its battle's block too, which the game's own changes are handed (where that site was found).
            if ((units || wears) && places.Units)
                hooks._overrides = reloaded.CreateHook<OverridesFunction>(hooks.Overrides, loaded + places.UnitOverrides, -1);
            if (wears)
                hooks._equipment = reloaded.CreateHook<EquipmentFunction>(hooks.Equipment, loaded + places.UnitEquipment, -1);
            if (treasures)
                hooks._mapLoad = reloaded.CreateHook<MapLoadFunction>(hooks.MapLoad, loaded + places.MapTreasures, -1);
            hooks._overrides?.Activate();
            hooks._equipment?.Activate();
            hooks._mapLoad?.Activate();
            return hooks;
        }

        nint Overrides(int battle, nint block, nint flags, nint rows)
        {
            nint answer = _overrides!.OriginalFunction(battle, block, flags, rows);
            try
            {
                _battle = battle;
                _block = block;
                if (block != 0 && _plan.Battles.TryGetValue(battle, out var units))
                {
                    int planned = 0;
                    foreach (var unit in units)
                        if (unit != null && unit.Changes)
                            planned++;
                    if (planned > 0)
                    {
                        BattleFile.Apply(new Span<byte>((void*)block, BattleFile.Units * BattleFile.EntryBytes), units);
                        SayOnce(BattleFile.UnitsLine(Named(battle), planned));
                    }
                }
            }
            catch (Exception e)
            {
                SayOnce($"a battle's units weren't changed as the mods have them ({e.GetType().Name}: {e.Message}).");
            }
            return answer;
        }

        void Equipment(nint unit, nint entry)
        {
            _equipment!.OriginalFunction(unit, entry);
            try
            {
                if (unit == 0 || entry == 0)
                    return;
                int battle = -1, slot = BattleFile.SlotOf(_block, entry);
                // The block kept is this battle's only while the battle loading is still the one it was kept for.
                if (slot >= 0 && (_places.EncounterNumber < 0 || *(int*)(_start + _places.EncounterNumber) == _battle))
                    battle = _battle;
                else
                {
                    var quest = QuestEntry?.Invoke(entry);
                    if (quest != null)
                        (battle, slot) = quest.Value;
                }
                if (battle < 0 || slot < 0 || !_plan.Battles.TryGetValue(battle, out var units))
                    return;
                var planned = units[slot];
                if (planned == null || !planned.Wears)
                    return;
                if (BattleFile.Wear(new Span<byte>((void*)unit, BattleFile.UnitBytes), planned) > 0)
                    SayOnce(BattleFile.WearsLine(Named(battle), slot, planned));
            }
            catch (Exception e)
            {
                SayOnce($"a unit wasn't given its items past 255 ({e.GetType().Name}: {e.Message}).");
            }
        }

        nint MapLoad(int map)
        {
            nint answer = _mapLoad!.OriginalFunction(map);
            try
            {
                if (_plan.Maps.TryGetValue(map & 0xFFFF, out var planned)
                    && BattleFile.Bury(new Span<byte>(_start + _places.TreasuresNow,
                                                      BattleFile.Tiles * BattleFile.TreasureBytes), planned) > 0)
                    SayOnce(BattleFile.TreasuresLine(map & 0xFFFF));
            }
            catch (Exception e)
            {
                SayOnce($"a map's buried treasure wasn't changed as the mods have it ({e.GetType().Name}: {e.Message}).");
            }
            return answer;
        }
    }
}
