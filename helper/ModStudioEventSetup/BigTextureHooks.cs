// Mod Studio Framework: (2.0.0, in the making) a sprite's textures at a higher resolution, the four hooks that hand the
// game the bigger pictures (BigTextures.cs says what they do and what was measured). Part of The Ivalice Chronicles Mod
// Studio, GPL-3.0.
//
// The four: the unpacking of a texture's entry (which entry the game unpacked last, where to, how many bytes), the
// making of a palette's 32 bit colors (kept), the battle's making of a slot's texture (its rectangle and palette), and
// the making of a texture on the card (where the bigger pixels are handed over). Each calls the game's own routine; a
// fault in the framework's part is said once and the game's routine runs as if the framework weren't there.
using System;
using System.Collections.Generic;
using Reloaded.Hooks.Definitions;
using Reloaded.Hooks.Definitions.X64;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    public sealed unsafe class BigTextureHooks
    {
        [Function(CallingConventions.Microsoft)]
        public delegate int DecodeFunction(nint archive, int entry, nint into);

        [Function(CallingConventions.Microsoft)]
        public delegate nint PaletteFunction(nint from, int halfSeen, int firstClear, nint into, int count);

        [Function(CallingConventions.Microsoft)]
        public delegate nint SlotFunction(nint slot, int variant, nint palette, int hash, int x, int y, int w, int h,
                                          nint into, int stride, int bits);

        [Function(CallingConventions.Microsoft)]
        public delegate int MakeFunction(nint texture);

        readonly nint* _texturesFile;
        readonly Action<string> _say;
        readonly HashSet<string> _saidOnce = new HashSet<string>();
        BigTextures.Logic _logic = null!;
        IHook<DecodeFunction>? _decode;
        IHook<PaletteFunction>? _palette;
        IHook<SlotFunction>? _slot;
        IHook<MakeFunction>? _make;
        /// <summary>How many times the game's own making of a texture ran on this thread (so a fault before it still
        /// leaves the texture made).</summary>
        [ThreadStatic] static int t_made;

        BigTextureHooks(nint* texturesFile, Action<string> say)
        {
            _texturesFile = texturesFile;
            _say = say;
        }

        /// <summary>The four hooks made, answering the plan's sheets. Null and why where they can't be (a hook that
        /// can't be made among them, none left on).</summary>
        public static BigTextureHooks? Arm(IReloadedHooks reloaded, GameMemory memory, BigTextures.Sites sites,
                                           BigTextures.Plan plan, Action<string> say, out string why)
        {
            byte* start = memory.Base;
            var hooks = new BigTextureHooks((nint*)(start + sites.Archive), say);
            var free = (delegate* unmanaged[Cdecl]<nint, void>)(start + sites.Free);
            var freeVariant = (delegate* unmanaged[Cdecl]<nint, int, int, void>)(start + sites.FreeVariant);
            try
            {
                hooks._decode = reloaded.CreateHook<DecodeFunction>(hooks.Decode, (long)(start + sites.Decode), -1);
                hooks._palette = reloaded.CreateHook<PaletteFunction>(hooks.Palette, (long)(start + sites.Palette), -1);
                hooks._slot = reloaded.CreateHook<SlotFunction>(hooks.Slot, (long)(start + sites.Slot), -1);
                hooks._make = reloaded.CreateHook<MakeFunction>(hooks.Make, (long)(start + sites.Make), -1);
                var make = hooks._make;
                hooks._logic = new BigTextures.Logic(plan.Sheets, texture =>
                                                     {
                                                         t_made++;
                                                         return make.OriginalFunction(texture);
                                                     },
                                                     texture => free(texture),
                                                     (slot, variant) => freeVariant(slot, variant, 1), say);
                hooks._decode.Activate();
                hooks._palette.Activate();
                hooks._slot.Activate();
                hooks._make.Activate();
            }
            catch (Exception e)
            {
                hooks.TurnOff();
                why = $"their hooks couldn't be made ({e.GetType().Name}: {e.Message})";
                return null;
            }
            why = "";
            return hooks;
        }

        /// <summary>Whichever of the hooks is made, turned off, as far as it can be.</summary>
        void TurnOff()
        {
            foreach (var hook in new IHook?[] { _make, _slot, _palette, _decode })
                try
                {
                    if (hook != null && hook.IsHookActivated)
                        hook.Disable();
                }
                catch (Exception)
                {
                }
        }

        void SayOnce(string line)
        {
            lock (_saidOnce)
                if (!_saidOnce.Add(line))
                    return;
            _say(line);
        }

        int Decode(nint archive, int entry, nint into)
        {
            int length = _decode!.OriginalFunction(archive, entry, into);
            try
            {
                if (archive != 0 && archive == *_texturesFile)
                    _logic.OnDecode(entry, into, length);
            }
            catch (Exception e)
            {
                SayOnce($"a texture's unpacking couldn't be followed ({e.GetType().Name}: {e.Message}).");
            }
            return length;
        }

        nint Palette(nint from, int halfSeen, int firstClear, nint into, int count)
        {
            nint result = _palette!.OriginalFunction(from, halfSeen, firstClear, into, count);
            try
            {
                _logic.OnPalette(into, count);
            }
            catch (Exception e)
            {
                SayOnce($"a palette's colors couldn't be kept ({e.GetType().Name}: {e.Message}).");
            }
            return result;
        }

        nint Slot(nint slot, int variant, nint palette, int hash, int x, int y, int w, int h, nint into, int stride, int bits)
        {
            bool called = false;
            try
            {
                return _logic.OnSlot(slot, variant, palette, x, y, w, h, into, stride, bits, () =>
                {
                    called = true;
                    return _slot!.OriginalFunction(slot, variant, palette, hash, x, y, w, h, into, stride, bits);
                });
            }
            catch (Exception e)
            {
                SayOnce($"a sprite's bigger picture couldn't be given ({e.GetType().Name}: {e.Message}).");
                return called ? 0 : _slot!.OriginalFunction(slot, variant, palette, hash, x, y, w, h, into, stride, bits);
            }
        }

        int Make(nint texture)
        {
            int before = t_made;
            try
            {
                return _logic.OnMake(texture);
            }
            catch (Exception e)
            {
                SayOnce($"a bigger picture couldn't be made a texture ({e.GetType().Name}: {e.Message}).");
                return t_made != before ? 0 : _make!.OriginalFunction(texture);
            }
        }
    }
}
