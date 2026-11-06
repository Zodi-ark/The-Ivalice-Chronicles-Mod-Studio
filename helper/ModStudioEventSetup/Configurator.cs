// Mod Studio Framework: (1.29.0) its one setting in Reloaded-II (the mod's
// Configure button), and reading it as the game starts. Part of The Ivalice
// Chronicles Mod Studio, GPL-3.0.
//
// Zodi's sixth of 3 November ("very simple process to flush out old unwanted
// items and rumors"), his choice "Tick in Reloaded-II": ticked, the next
// start frees the numbers of every mod that isn't enabled (Numbers.Free),
// says which, and unticks it. Reloaded-II finds this class in the mod's
// program (an IConfigurator), shows each configurable's properties and calls
// its Save; the helper reads the same file from its settings folder.
using System;
using System.ComponentModel;
using System.IO;
using Reloaded.Mod.Interfaces;

namespace ModStudioEventSetup
{
    /// <summary>The helper's settings, as Reloaded-II's Configure shows them.</summary>
    public sealed class Config : IUpdatableConfigurable
    {
        // (1.29.1, Zodi after test 62: "the name and description ... is way too long") Reloaded-II's Configure cuts a
        // name past about 30 characters, and shows the description on one line.
        [DisplayName("Free disabled mods' numbers")]
        [Description("At the next start, frees the numbers of mods that aren't enabled, says which in its log, then "
                     + "unticks itself.")]
        [DefaultValue(false)]
        public bool FreeNumbers { get; set; }

        [Browsable(false)]
        public string ConfigName { get; set; } = "Mod Studio Framework";

        [Browsable(false)]
        public Action Save { get; set; } = () => { };

        public event Action<IUpdatableConfigurable>? ConfigurationUpdated;

        internal void Updated() => ConfigurationUpdated?.Invoke(this);
    }

    /// <summary>Reloaded-II's way to the settings: the file Config.json (Settings.cs) in the mod's settings folder
    /// (Reloaded-II's, given by SetConfigDirectory), else in the mod's own folder.</summary>
    public sealed class Configurator : IConfiguratorV3
    {
        string _modFolder = "", _configFolder = "";

        public void SetModDirectory(string modDirectory) => _modFolder = modDirectory ?? "";

        public void SetConfigDirectory(string configDirectory) => _configFolder = configDirectory ?? "";

        public void SetContext(in ConfiguratorContext context)
        {
        }

        public void Migrate(string oldDirectory, string newDirectory)
        {
            try
            {
                string from = Path.Combine(oldDirectory, Settings.FileName);
                string to = Path.Combine(newDirectory, Settings.FileName);
                if (File.Exists(from) && !File.Exists(to))
                {
                    Directory.CreateDirectory(newDirectory);
                    File.Move(from, to);
                }
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }

        public bool TryRunCustomConfiguration() => false;

        public IConfigurable[] GetConfigurations() => new IConfigurable[] { Load() };

        /// <summary>Where the settings are kept.</summary>
        public string SettingsFile => Path.Combine(_configFolder.Length > 0 ? _configFolder : _modFolder, Settings.FileName);

        /// <summary>The settings as kept (a file that can't be read gives the defaults), their Save writing them back.
        /// </summary>
        public Config Load()
        {
            string path = SettingsFile;
            var config = new Config { FreeNumbers = Settings.ReadFreeNumbers(path) };
            config.Save = () =>
            {
                Settings.Write(path, config.FreeNumbers);
                config.Updated();
            };
            return config;
        }
    }
}
