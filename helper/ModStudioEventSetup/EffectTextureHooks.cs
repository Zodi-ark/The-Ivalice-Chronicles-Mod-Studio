// Mod Studio Framework: (2.0.0, in the making) an effect's picture at a higher resolution, the one hook that hands the
// game the bigger pictures (EffectTextures.cs says what it does and what was measured). Part of The Ivalice Chronicles Mod
// Studio, GPL-3.0.
//
// The hook sits on the making of a page's texture (0x41E05C). For a record whose page holds a mod's bigger picture the
// framework makes the texture itself through the game's own routines (the page's pixels 0x418F20, the sending again
// 0x3D0BF8, the noting 0x3D0A80 and the making 0x3D0B10); every other record goes to the game's own routine. A fault in
// the framework's part is said once and the game's routine runs as if the framework weren't there.
using System;
using System.Collections.Generic;
using Reloaded.Hooks.Definitions;
using Reloaded.Hooks.Definitions.X64;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    public sealed unsafe class EffectTextureHooks
    {
        [Function(CallingConventions.Microsoft)]
        public delegate int RecordFunction(int index);

        readonly Action<string> _say;
        readonly HashSet<string> _saidOnce = new HashSet<string>();
        EffectTextures.Logic _logic = null!;
        IHook<RecordFunction>? _record;

        EffectTextureHooks(Action<string> say) => _say = say;

        /// <summary>The hook made, answering the plan's pictures. Null and why where it can't be.</summary>
        public static EffectTextureHooks? Arm(IReloadedHooks reloaded, GameMemory memory, EffectTextures.Sites sites,
                                              EffectTextures.Plan plan, Action<string> say, out string why)
        {
            byte* start = memory.Base;
            var hooks = new EffectTextureHooks(say);
            var pixels = (delegate* unmanaged[Cdecl]<int, nint>)(start + sites.Pixels);
            var send = (delegate* unmanaged[Cdecl]<nint, nint, int, int, int, int, int>)(start + sites.Send);
            var note = (delegate* unmanaged[Cdecl]<nint, nint, int, int, int, int, int, byte, void>)(start + sites.Note);
            var make = (delegate* unmanaged[Cdecl]<nint, int>)(start + sites.Make);
            nint scratch = (nint)(start + sites.Scratch), scratchAt = (nint)(start + sites.ScratchAt);
            try
            {
                hooks._record = reloaded.CreateHook<RecordFunction>(hooks.Record, (long)(start + sites.Record), -1);
                hooks._logic = new EffectTextures.Logic(
                    plan, (nint)(start + sites.Records), (nint)(start + sites.Objects), (nint)(start + sites.Pages4),
                    (nint)(start + sites.Pages8),
                    index =>
                    {
                        // The game's own making of the page's pixels, into the scratch memory as 0x41E05C reckons it.
                        pixels(index);
                        nint block = *(nint*)scratch;
                        return block == 0 ? 0 : block + ((nint)(*(int*)scratchAt) << 10) - 0x280000;
                    },
                    (texture, at, x, y, w, h) => send(texture, at, x, y, w, h),
                    (texture, at, w, h, bits, keptW, keptH, kind) => note(texture, at, w, h, bits, keptW, keptH, kind),
                    texture => make(texture), say);
                hooks._record.Activate();
            }
            catch (Exception e)
            {
                try
                {
                    if (hooks._record != null && hooks._record.IsHookActivated)
                        hooks._record.Disable();
                }
                catch (Exception)
                {
                }
                why = $"its hook couldn't be made ({e.GetType().Name}: {e.Message})";
                return null;
            }
            why = "";
            return hooks;
        }

        void SayOnce(string line)
        {
            lock (_saidOnce)
                if (!_saidOnce.Add(line))
                    return;
            _say(line);
        }

        int Record(int index)
        {
            try
            {
                if (_logic.OnRecord(index))
                    return 0;
            }
            catch (Exception e)
            {
                SayOnce($"an effect's bigger picture couldn't be given ({e.GetType().Name}: {e.Message}).");
            }
            return _record!.OriginalFunction(index);
        }
    }
}
