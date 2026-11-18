// (1.41.0) A mod's own action abilities made in the running game (the road's step 4; Zodi's answer of 10 November 2026:
// "Straight to more"; test 94). Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// What AbilityRoom, AbilityRecords, AbilityEffects, AbilityAnimations and AbilityWords make, put in the game: a room of
// the framework's own near the program (its code; the lists of the mods' abilities and of the skillsets' places that
// hold them; the longer tables of the abilities' records, effects and how their users move), every place of the game's
// code that names one of those three tables told the same place in the longer one, the game's central routines and the
// turn order's two readers sent to the framework's code, and the older text's loader made to ask for the names' file's
// room with more bytes and to call the framework once it is read. And three hooks of the game's own: the tables' setup
// (the Ability table given the mods' abilities' rows), its making of a battle unit and its load of a save; at each, what
// others have written to the game's own three tables since is brought over to the longer ones (the mod loader writes a
// mod's ability data there), as the jobs' longer table is kept in step.
//
// Everything is found before anything is changed (Find): one place not found, and nothing of the game's is.
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using Reloaded.Hooks.Definitions;

namespace ModStudioEventSetup
{
    public sealed unsafe class AbilityHooks
    {
        /// <summary>Every place of the game's the abilities need, found in the program as it is.</summary>
        public sealed class Sites
        {
            public AbilityRoom.Found Entries { get; }
            public AbilityRecords.Sites Records { get; }
            public AbilityEffects.Sites Effects { get; }
            public AbilityAnimations.Sites Animations { get; }
            /// <summary>Each place not found, in words.</summary>
            public List<string> Missing { get; } = new List<string>();
            public bool Ok => Missing.Count == 0;

            internal Sites(AbilityRoom.Found entries, AbilityRecords.Sites records, AbilityEffects.Sites effects,
                           AbilityAnimations.Sites animations)
            {
                Entries = entries;
                Records = records;
                Effects = effects;
                Animations = animations;
                Missing.AddRange(entries.Missing);
                Missing.AddRange(records.Missing);
                Missing.AddRange(effects.Missing);
                Missing.AddRange(animations.Missing);
            }
        }

        /// <summary>The central routines and their compares, the older text's loader, the turn order's readers and
        /// units, and every reader of the three tables, each found once.</summary>
        public static Sites Find(ReadOnlySpan<byte> image, List<Section> sections)
            => new Sites(AbilityRoom.Find(image, sections),
                         AbilityRecords.Find(image, sections, AbilityRecords.Locate(image, sections)),
                         AbilityEffects.Find(image, sections, AbilityEffects.Locate(image, sections)),
                         AbilityAnimations.Find(image, sections, AbilityAnimations.Locate(image, sections)));

        readonly IList<AbilityFile.Given> _given;
        readonly Action<string> _say;
        readonly HashSet<string> _saidOnce = new HashSet<string>();
        readonly HashSet<nint> _copies = new HashSet<nint>();
        static readonly object s_lock = new object();
        static AbilityHooks? s_hooks;
        IHook<ItemHooks.SheetInitFunction>? _sheetInit;
        IHook<JobHooks.FourFunction>? _build;
        IHook<SaveFallbackHook.SaveLoadFunction>? _saveLoad;
        /// <summary>The game's own three tables, the longer ones, and the game's as they were last seen.</summary>
        byte* _gameRecords, _records, _gameEffects, _effects, _gameAnimations, _animations;
        byte[] _recordsSeen = Array.Empty<byte>(), _effectsSeen = Array.Empty<byte>(), _animationsSeen = Array.Empty<byte>();

        AbilityHooks(IList<AbilityFile.Given> given, Action<string> say)
        {
            _given = given;
            _say = say;
        }

        void SayOnce(string line)
        {
            lock (_saidOnce)
                if (!_saidOnce.Add(line))
                    return;
            _say(line);
        }

        /// <summary>The abilities made so in the game, or null and why (nothing of the game's changed then). `places`:
        /// each place of a skillset that holds a mod's ability (AbilityPlan); `sheetInit`, `build` and `saveLoad`: where
        /// the tables' setup, the making of a battle unit and the load of a save start (the last not hooked where it is
        /// -1).</summary>
        public static AbilityHooks? Arm(IReloadedHooks reloaded, GameMemory memory, Sites sites, IList<AbilityFile.Given> given,
                                        IList<(int Skillset, int Place, int Number)> places, int sheetInit, int build,
                                        int saveLoad, Action<string> say, out string why)
        {
            byte* start = memory.Base;
            var image = new ReadOnlySpan<byte>(start, memory.Bytes.Length);
            ulong imageBase = (ulong)start;
            if (!sites.Ok)
            {
                why = $"{string.Join(", ", sites.Missing)} wasn't found";
                return null;
            }
            nint room = JobHooks.Near(imageBase, memory.Bytes.Length, AbilityRoom.Room);
            if (room == 0)
            {
                why = "Windows gave no memory near the game's program for the abilities' native code";
                return null;
            }
            byte* at = (byte*)room;
            var code = AbilityRoom.Code(image, sites.Entries, imageBase, (ulong)room, out var changes);
            var recordChanges = AbilityRecords.Changes(sites.Records, imageBase, (ulong)(at + AbilityRoom.RecordsAt));
            var effectChanges = AbilityEffects.Changes(sites.Effects, imageBase, (ulong)(at + AbilityRoom.EffectsAt));
            var animationChanges = AbilityAnimations.Changes(sites.Animations, imageBase, (ulong)(at + AbilityRoom.AnimationsAt));
            if (recordChanges == null || effectChanges == null || animationChanges == null)
            {
                why = "the abilities' longer tables are too far from the game's program";
                return null;
            }
            changes.AddRange(recordChanges);
            changes.AddRange(effectChanges);
            changes.AddRange(animationChanges);
            var hooks = new AbilityHooks(given, say);
            // The room's lists and the longer tables as they start (AbilityRoom.Start), and the game's own three tables
            // as they are now, kept to see what others write to them.
            int recordBytes = AbilityRecords.GameCount * AbilityRecords.RecordBytes;
            hooks._gameRecords = start + sites.Records.Records;
            hooks._gameEffects = start + sites.Effects.Effects;
            hooks._gameAnimations = start + sites.Animations.Animations;
            hooks._records = at + AbilityRoom.RecordsAt;
            hooks._effects = at + AbilityRoom.EffectsAt;
            hooks._animations = at + AbilityRoom.AnimationsAt;
            AbilityRoom.Start(new Span<byte>(at, AbilityRoom.Room), new ReadOnlySpan<byte>(hooks._gameRecords, recordBytes),
                              new ReadOnlySpan<byte>(hooks._gameEffects, AbilityEffects.Bytes),
                              new ReadOnlySpan<byte>(hooks._gameAnimations, AbilityAnimations.Bytes), given, places);
            hooks._recordsSeen = new ReadOnlySpan<byte>(hooks._gameRecords, recordBytes).ToArray();
            hooks._effectsSeen = new ReadOnlySpan<byte>(hooks._gameEffects, 2 * AbilityEffects.GameWords).ToArray();
            hooks._animationsSeen = new ReadOnlySpan<byte>(hooks._gameAnimations,
                                                           AbilityAnimations.RowBytes * AbilityAnimations.GameRows).ToArray();
            // The code and its cell, then its page made to run (the rest of the room stays the framework's to write).
            Marshal.Copy(code, 0, room, code.Length);
            *(nint*)(at + AbilityRoom.NamesCell) = (nint)(delegate* unmanaged<nint, int, void>)&NamesEntry;
            if (!JobHooks.VirtualProtect(room, (nuint)AbilityRoom.CodeRoom, JobHooks.ExecuteRead, out _))
            {
                why = "Windows wouldn't let the abilities' native code run";
                return null;
            }
            JobHooks.FlushInstructionCache(JobHooks.GetCurrentProcess(), room, (nuint)AbilityRoom.CodeRoom);
            lock (s_lock)
                s_hooks = hooks;
            hooks._sheetInit = reloaded.CreateHook<ItemHooks.SheetInitFunction>(hooks.SheetInit, (long)(start + sheetInit), -1);
            hooks._build = reloaded.CreateHook<JobHooks.FourFunction>(hooks.Build, (long)(start + build), -1);
            hooks._sheetInit.Activate();
            hooks._build.Activate();
            if (saveLoad >= 0)
            {
                hooks._saveLoad = reloaded.CreateHook<SaveFallbackHook.SaveLoadFunction>(hooks.SaveLoad, (long)(start + saveLoad), -1);
                hooks._saveLoad.Activate();
            }
            foreach (var change in changes)
            {
                memory.Writing(change.At, change.Bytes.Length,
                               () => Marshal.Copy(change.Bytes, 0, (nint)(start + change.At), change.Bytes.Length));
                JobHooks.FlushInstructionCache(JobHooks.GetCurrentProcess(), (nint)(start + change.At), (nuint)change.Bytes.Length);
            }
            why = "";
            return hooks;
        }

        Span<byte> Records => new Span<byte>(_records, AbilityRecords.Bytes);
        Span<byte> Effects => new Span<byte>(_effects, AbilityEffects.Bytes);
        Span<byte> Animations => new Span<byte>(_animations, AbilityAnimations.Bytes);

        /// <summary>What others have written to the game's own three tables since they were last seen brought over to
        /// the longer ones; the mods' effects and how their users move made again from the game's abilities they are
        /// like.</summary>
        void BringOver()
        {
            lock (s_lock)
            {
                AbilityRecords.Sync(new ReadOnlySpan<byte>(_gameRecords, _recordsSeen.Length), _recordsSeen, Records);
                if (AbilityEffects.Sync(new ReadOnlySpan<byte>(_gameEffects, _effectsSeen.Length), _effectsSeen, Effects) > 0)
                    AbilityEffects.Likes(Effects, _given);
                if (AbilityAnimations.Sync(new ReadOnlySpan<byte>(_gameAnimations, _animationsSeen.Length), _animationsSeen,
                                           Animations) > 0)
                    AbilityAnimations.Likes(Animations, _given);
            }
        }

        /// <summary>The framework's function in the room's first cell: the older text's names' file has been read into
        /// a room of its size and NamesExtra bytes more (AbilityWords.Longer). A fault leaves the file as the game read
        /// it.</summary>
        [UnmanagedCallersOnly]
        static void NamesEntry(nint room, int size)
        {
            var hooks = s_hooks;
            try
            {
                if (hooks == null || room == 0 || size < 0 || size > int.MaxValue - AbilityWords.NamesExtra)
                    return;
                var said = new List<string>();
                AbilityWords.Longer(new Span<byte>((void*)room, size + AbilityWords.NamesExtra), size, hooks._given, said);
                foreach (var line in said)
                    hooks.SayOnce(line);
            }
            catch (Exception e)
            {
                hooks?.SayOnce($"the older text's names of the mods' abilities weren't written ({e.GetType().Name}: {e.Message}).");
            }
        }

        int SheetInit(nint sheet, nint file)
        {
            try
            {
                BringOver();
                Give(sheet, file);
            }
            catch (Exception e)
            {
                SayOnce($"the mods' abilities got no names ({e.GetType().Name}: {e.Message}); the game's Ability table is used.");
            }
            return _sheetInit!.OriginalFunction(sheet, file);
        }

        nint Build(nint a, nint b, nint c, nint d)
        {
            try
            {
                BringOver();
            }
            catch (Exception)
            {
                // The game's own making goes on with the tables as they are.
            }
            return _build!.OriginalFunction(a, b, c, d);
        }

        int SaveLoad(int mode)
        {
            int answer = _saveLoad!.OriginalFunction(mode);
            try
            {
                BringOver();
            }
            catch (Exception)
            {
                // The tables stay as they were last brought over.
            }
            return answer;
        }

        /// <summary>The Ability table given a row for each ability given (AbilityWords.WithRows), once.</summary>
        void Give(nint sheet, nint file)
        {
            if (sheet == 0 || file == 0 || *(int*)(sheet + Hooks.SheetNumber) != AbilityWords.Sheet)
                return;
            if (*(nint*)(sheet + Hooks.SheetFile) != file)
            {
                SayOnce("Ability gets no rows: the table isn't laid out as in the game this was made for.");
                return;
            }
            nint bytes = *(nint*)(file + Hooks.FileBytes);
            long size = *(long*)(file + Hooks.FileSize);
            lock (_copies)
                if (_copies.Contains(bytes))
                    return;
            if (bytes == 0 || size <= 0 || size > Hooks.MostTable)
            {
                SayOnce($"Ability gets no rows: its file is {size} bytes.");
                return;
            }
            var said = new List<string>();
            var table = AbilityWords.WithRows(new ReadOnlySpan<byte>((void*)bytes, (int)size), _given, said, out string why);
            foreach (var line in said)
                SayOnce(line);
            if (table == null)
            {
                SayOnce($"Ability gets no rows: {why}.");
                return;
            }
            nint copy = (nint)NativeMemory.Alloc((nuint)table.Length);
            Marshal.Copy(table, 0, copy, table.Length);
            lock (_copies)
                _copies.Add(copy);
            *(long*)(file + Hooks.FileSize) = table.Length;
            *(nint*)(file + Hooks.FileBytes) = copy;
            _say($"Ability: the mods' abilities' {_given.Count} row{(_given.Count == 1 ? "" : "s")} written.");
        }
    }
}
