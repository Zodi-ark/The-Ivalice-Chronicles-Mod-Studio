// Mod Studio Event Setup: a Reloaded-II mod that applies the event setup
// changes mods made with The Ivalice Chronicles Mod Studio list in their
// EventSetup.json: an event's map, weather, time of day, music, enemy
// battle, deploy areas, what follows it and its battle rules, which the game
// keeps in its program rather than in a table the mod loader changes.
//
// Part of The Ivalice Chronicles Mod Studio. GPL-3.0: see LICENSE in Mod
// Studio's folder. Written for Mod Studio from the game's own data and
// Reloaded-II's public interfaces (Reloaded.Mod.Interfaces, GPL-3.0);
// nothing of the mod loader's.
using System;
using System.Collections.Generic;
using System.IO;
using Reloaded.Mod.Interfaces;
using Reloaded.Mod.Interfaces.Internal;

namespace ModStudioEventSetup
{
    public sealed class Mod : IMod
    {
        public const string Name = "Mod Studio Event Setup";

        IModLoader? _loader;
        ILoggerV1? _logger;
        string _self = "";
        GameMemory? _memory;
        Table? _table;
        readonly Applier _applier = new Applier();
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
            // A mod loaded after the start (enabled while the game runs) is applied at once.
            if (_initialized && fresh)
                Apply(config!);
        }

        void Initialized()
        {
            _initialized = true;
            foreach (var config in _order)
                Apply(config);
        }

        void Apply(IModConfigV1 config)
        {
            string folder;
            try
            {
                folder = _loader!.GetDirectoryForModId(config.ModId);
            }
            catch (Exception)
            {
                return;
            }
            string path = Path.Combine(folder ?? "", SetupFile.Name);
            if (!File.Exists(path))
                return;
            string mod = string.IsNullOrWhiteSpace(config.ModName) ? config.ModId : config.ModName;
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
                said = _applier.Apply(memory.Bytes.Slice(table.Address, table.Bytes), table, mod, changes));
            foreach (var line in said)
                Say(line);
        }

        public void Suspend() { }
        public void Resume() { }
        public void Unload() { }
        public bool CanUnload() => false;
        public bool CanSuspend() => false;
    }
}
