// Mod Studio Framework: (1.45.0) a job's own portraits, the hook that names their files (SpritePortraits.cs says what it
// answers and why). Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using Reloaded.Hooks.Definitions;
using Reloaded.Hooks.Definitions.X64;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    public sealed class SpritePortraitHooks
    {
        [Function(CallingConventions.Microsoft)]
        public delegate void FaceFileFunction(nint name, int portrait, int colors);

        readonly Dictionary<int, string[]> _plan;
        readonly Dictionary<int, string> _whose;
        readonly Action<string> _say;
        readonly HashSet<string> _saidOnce = new HashSet<string>();
        int _given;
        IHook<FaceFileFunction>? _faceFile;

        SpritePortraitHooks(Dictionary<int, string[]> plan, Dictionary<int, string> whose, Action<string> say)
        {
            _plan = plan;
            _whose = whose;
            _say = say;
        }

        /// <summary>The hook made, naming the jobs' own portraits' files; each job's sprite whose portraits it names is marked
        /// (Given.Portraits), so its face word and its graphics slot name its own portrait's number (SpriteRoom) and the
        /// game's code takes it (SpritePortraits.Code). Null and why where it can't be (none marked then).</summary>
        public static unsafe SpritePortraitHooks? Arm(IReloadedHooks reloaded, GameMemory memory, SpritePortraits.Sites sites,
                                                      IList<JobRoom.Given> given, Action<string> say, out string why)
        {
            var plan = SpritePortraits.Plan(given);
            if (plan.Count == 0)
            {
                why = "no job with sprites of its own has portraits of its own";
                return null;
            }
            var portraits = new SpritePortraitHooks(plan, SpritePortraits.Whose(given), say);
            try
            {
                portraits._faceFile = reloaded.CreateHook<FaceFileFunction>(portraits.FaceFile, (long)(memory.Base + sites.FaceFile), -1);
                portraits._faceFile.Activate();
            }
            catch (Exception e)
            {
                portraits.TurnOff();
                why = $"its hook couldn't be made ({e.GetType().Name}: {e.Message})";
                return null;
            }
            foreach (var g in given)
                if (g.Sprite >= 0)
                    for (int woman = 0; woman < 2; woman++)
                        g.Portraits[woman] = g.Job.Portraits[woman] != null;
            why = "";
            return portraits;
        }

        void TurnOff()
        {
            try
            {
                if (_faceFile != null && _faceFile.IsHookActivated)
                    _faceFile.Disable();
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

        void FaceFile(nint name, int portrait, int colors)
        {
            try
            {
                if (_plan.TryGetValue(portrait, out var names))
                {
                    int which = SpritePortraits.Which(names, colors);
                    var bytes = SpritePortraits.FileName(names[which]);
                    if (bytes.Length <= SpritePortraits.FileBytes)
                    {
                        Marshal.Copy(bytes, 0, name, bytes.Length);
                        if (System.Threading.Interlocked.Exchange(ref _given, 1) == 0 && _whose.TryGetValue(portrait, out var whose))
                            _say(SpritePortraits.FirstLine(whose, which));
                        return;
                    }
                }
            }
            catch (Exception e)
            {
                SayOnce($"a job's own portrait couldn't be named ({e.GetType().Name}: {e.Message}).");
            }
            _faceFile!.OriginalFunction(name, portrait, colors);
        }
    }
}
