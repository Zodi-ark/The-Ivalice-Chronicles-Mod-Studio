// Mod Studio Framework: (1.7.1) the hook of the game's load of a save's
// state (Places.SaveLoad), through Reloaded-II's shared hooks: the game's own
// load, then Ramza's place moved off a mod's place no mod gives now
// (SaveFallback.cs), and (1.13.0) the save's mark of the numbers it was made
// with looked at (Framework.Loaded; 1.32.0: the side quest flags it can't
// really hold cleared, said, Zodi's choice after test 67; 1.35.0: the mods'
// items it can't really hold taken out, from its bag and its party, his
// word of 5 November). (1.35.1, his test 72) The save's place looked at by
// every hook made, which is made whenever the load is found: until 1.35.1
// only once some mod's place was ever numbered, which a free undoes. The
// load's callers keep nothing in the registers a C# hook may change
// (dev/research/sidequests/registers.py). Part of The Ivalice Chronicles Mod
// Studio, GPL-3.0.
using System;
using System.Collections.Generic;
using Reloaded.Hooks.Definitions;
using Reloaded.Hooks.Definitions.X64;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    /// <summary>(1.7.1) The hook of the game's load of a save's state (Places.SaveLoad): the game's own, then Ramza's
    /// place moved to a place of the game's when no mod gives it now (SaveFallback.MoveOff).</summary>
    public sealed unsafe class SaveFallbackHook
    {
        /// <summary>The game's load of a save's state: a mode; what it answers.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate int SaveLoadFunction(int mode);

        readonly byte* _start;
        readonly Places _places;
        readonly HashSet<int> _given;
        readonly Numbers _numbers;
        readonly Action<string> _say;
        /// <summary>(1.13.0) Whether a save's mark is looked at (some quest's flag, or 1.35.0 some mod's item, was
        /// ever numbered), with the numbers' ID. (1.35.1) Its place always is.</summary>
        readonly bool _marks;
        IHook<SaveLoadFunction>? _load;

        SaveFallbackHook(byte* start, Places places, IEnumerable<int> given, Numbers numbers, Action<string> say,
                         bool marks)
        {
            _start = start;
            _places = places;
            _given = new HashSet<int>(given);
            _numbers = numbers;
            _say = say;
            _marks = marks;
        }

        /// <summary>The hook, made and active (before the game runs): `given` the places the mods give now (the
        /// program given them), `numbers` the numbers kept with their homes and (1.13.0) their ID; `marks` whether a
        /// save's mark is looked at; (1.35.0) what its units wear looked at when its party was found
        /// (places.Roster).</summary>
        public static SaveFallbackHook Make(IReloadedHooks reloaded, byte* start, Places places, IEnumerable<int> given,
                                            Numbers numbers, Action<string> say, bool marks = false)
        {
            var hook = new SaveFallbackHook(start, places, given, numbers, say, marks);
            hook._load = reloaded.CreateHook<SaveLoadFunction>(hook.Load, (long)(nint)start + places.SaveLoad, -1);
            hook._load.Activate();
            return hook;
        }

        int Load(int mode)
        {
            int answer = _load!.OriginalFunction(mode);
            try
            {
                // (1.35.1) Whatever the numbers still remember: a free lets a mod's places go with their homes.
                string? said = SaveFallback.MoveOff(new Span<byte>(_start + _places.SaveBank, Framework.BankBytes),
                                                    _given, _numbers);
                if (said != null)
                    _say(said);
            }
            catch (Exception e)
            {
                _say($"a save's place wasn't looked at as it loaded ({e.GetType().Name}: {e.Message}).");
            }
            if (_marks)
            {
                try
                {
                    // (1.32.0) Its side quest flags it can't really hold cleared, said, and marked with the numbers;
                    // (1.35.0) the mods' items it can't really hold taken out of its bag and its party, said.
                    var roster = _places.Roster >= 0
                        ? new Span<byte>(_start + _places.Roster, Framework.RosterBytes) : Span<byte>.Empty;
                    string? said = Framework.Loaded(new Span<byte>(_start + _places.SaveBank, Framework.BankBytes),
                                                    roster, _numbers, out string? items);
                    if (said != null)
                        _say(said);
                    if (items != null)
                        _say(items);
                }
                catch (Exception e)
                {
                    _say($"a save's mark wasn't looked at as it loaded ({e.GetType().Name}: {e.Message}).");
                }
            }
            return answer;
        }
    }
}
