// Mod Studio Framework: (2.0.6) WotL Restoration's War of the Lions items shown with the framework's own pictures.
// Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi's report of 18 November 2026 (13:13): "Another bug the moonblade is missing the art texture", with WotL
// Restoration on: its 40 items are its own then (the framework gives none of its own, WotLItems.cs), each shown with
// its own pictures, and its picture for the menus (the Art Texture) of each is its small icon at that size (its
// `ei_<n>_uitx` files, looked at for facts only). Offered: the framework showing his pictures on them too. His answer
// (14:05): "yes we should considering WotL Restoration does not have any".
//
// So where WotL Restoration has made the items' room (ItemRoom's Moved), the game's own two icon paths (the Art
// Texture's and the Sprite Texture's: ItemRoom's IconPath and SmallIconPath, the functions ItemHooks hooks for the
// mods' own items) are hooked for the 40 numbers alone: each named the framework's own pictures of it (his, which the
// framework carries beside itself: WotLItems.IconName, ItemHooks.ItemIconPath), whether or not a mod asks for the 40.
// Every other number is the game's own answer (or another hook's, as Reloaded-II's shared hooks go one into another).
// WotL Restoration's items themselves (their records, names, words, looks in battle and counts) stay its own.
//
// Nothing here throws into the game: a fault is said once and the game's own answer stands.
using System;
using System.Collections.Generic;
using Reloaded.Hooks.Definitions;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    public sealed unsafe class WotLIcons
    {
        /// <summary>What is said once they are shown.</summary>
        public const string Line = WotLItems.PicturesLine;

        readonly HashSet<int> _numbers = new HashSet<int>();
        readonly Action<string> _say;
        readonly object _lock = new object();
        readonly HashSet<string> _saidOnce = new HashSet<string>(StringComparer.Ordinal);
        IHook<ItemHooks.IconPathFunction>? _icon, _smallIcon;

        WotLIcons(Action<string> say)
        {
            _say = say;
            foreach (var fact in WotLItems.Facts)
                _numbers.Add(fact.Number);
        }

        /// <summary>The two icon paths hooked for the 40 numbers (found by the items' room: IconPath, SmallIconPath);
        /// null where either wasn't found.</summary>
        public static WotLIcons? Arm(IReloadedHooks reloaded, byte* start, ItemRoom.Found found, Action<string> say)
        {
            if (!found.At.TryGetValue("IconPath", out int big) || !found.At.TryGetValue("SmallIconPath", out int small)
                || big < 0 || small < 0)
                return null;
            var icons = new WotLIcons(say);
            icons._icon = reloaded.CreateHook<ItemHooks.IconPathFunction>(icons.IconPath, (long)(start + big), -1);
            icons._smallIcon = reloaded.CreateHook<ItemHooks.IconPathFunction>(icons.SmallIconPath, (long)(start + small), -1);
            icons._icon.Activate();
            icons._smallIcon.Activate();
            return icons;
        }

        void SayOnce(string line)
        {
            lock (_lock)
                if (!_saidOnce.Add(line))
                    return;
            _say(line);
        }

        int IconPath(nint buffer, int number, int size) => Icon(buffer, number, size, false);

        int SmallIconPath(nint buffer, int number, int size) => Icon(buffer, number, size, true);

        int Icon(nint buffer, int number, int size, bool small)
        {
            var original = small ? _smallIcon! : _icon!;
            if (!_numbers.Contains(number))
                return original.OriginalFunction(buffer, number, size);
            try
            {
                int written = WotLItems.WritePicturePath(buffer, number, size, small);
                return written >= 0 ? written : original.OriginalFunction(buffer, number, size);
            }
            catch (Exception e)
            {
                SayOnce($"one of WotL Restoration's War of the Lions items wasn't given the framework's own picture "
                        + $"({e.GetType().Name}: {e.Message}).");
                return original.OriginalFunction(buffer, number, size);
            }
        }
    }
}
