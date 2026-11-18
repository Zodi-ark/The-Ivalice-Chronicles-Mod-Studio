// Mod Studio Framework: (1.44.0) a job's own textures, the two hooks that answer them (SpriteTextures.cs says what they
// answer and why). Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using Reloaded.Hooks.Definitions;
using Reloaded.Hooks.Definitions.X64;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    public sealed unsafe class SpriteTextureHooks
    {
        [Function(CallingConventions.Microsoft)]
        public delegate int OpenFunction(nint archive, int first, int last, int cached);

        [Function(CallingConventions.Microsoft)]
        public delegate int DecodeFunction(nint archive, int entry, nint into);

        readonly Dictionary<int, byte[]> _entries;
        readonly Dictionary<int, string> _firstLines;
        readonly nint* _texturesFile;
        readonly Action<string> _say;
        readonly HashSet<string> _saidOnce = new HashSet<string>();
        int _given;
        IHook<OpenFunction>? _open;
        IHook<DecodeFunction>? _decode;

        SpriteTextureHooks(Dictionary<int, byte[]> entries, Dictionary<int, string> firstLines, nint* texturesFile,
                           Action<string> say)
        {
            _entries = entries;
            _firstLines = firstLines;
            _texturesFile = texturesFile;
            _say = say;
        }

        /// <summary>The two hooks made, answering the jobs' own textures; each job's sprite whose textures they answer is
        /// marked (Given.Textures), so the sprites' table names them (SpriteRoom.Fill). Null and why where they can't be
        /// (1.44.2: a hook that can't be made among them, none left on and no job marked).</summary>
        public static SpriteTextureHooks? Arm(IReloadedHooks reloaded, GameMemory memory, SpriteTextures.Sites sites, IList<JobRoom.Given> given,
                                          Action<string> say, out string why)
        {
            var entries = SpriteTextures.Entries(given);
            if (entries.Count == 0)
            {
                why = "no job with sprites of its own has textures of its own";
                return null;
            }
            byte* start = memory.Base;
            var textures = new SpriteTextureHooks(entries, SpriteTextures.FirstLines(given), (nint*)(start + sites.Archive),
                                                  say);
            try
            {
                textures._open = reloaded.CreateHook<OpenFunction>(textures.Open, (long)(start + sites.Open), -1);
                textures._decode = reloaded.CreateHook<DecodeFunction>(textures.Decode, (long)(start + sites.Decode), -1);
                textures._open.Activate();
                textures._decode.Activate();
            }
            catch (Exception e)
            {
                textures.TurnOff();
                why = $"their hooks couldn't be made ({e.GetType().Name}: {e.Message})";
                return null;
            }
            foreach (var g in given)
                if (g.Sprite >= 0)
                    for (int woman = 0; woman < 2; woman++)
                        g.Textures[woman] = g.Job.Textures[woman] != null;
            why = "";
            return textures;
        }

        /// <summary>Whichever of the two hooks is made, turned off, as far as it can be.</summary>
        void TurnOff()
        {
            try
            {
                if (_open != null && _open.IsHookActivated)
                    _open.Disable();
            }
            catch (Exception)
            {
            }
            try
            {
                if (_decode != null && _decode.IsHookActivated)
                    _decode.Disable();
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

        int Open(nint archive, int first, int last, int cached)
        {
            try
            {
                if (SpriteTextures.Opens(_entries, archive, *_texturesFile, first, last))
                    return 0;
            }
            catch (Exception e)
            {
                SayOnce($"a job's own texture couldn't be opened ({e.GetType().Name}: {e.Message}).");
            }
            return _open!.OriginalFunction(archive, first, last, cached);
        }

        int Decode(nint archive, int entry, nint into)
        {
            try
            {
                var bytes = SpriteTextures.Unpacks(_entries, archive, *_texturesFile, entry);
                if (bytes != null)
                {
                    Marshal.Copy(bytes, 0, into, bytes.Length);
                    if (System.Threading.Interlocked.Exchange(ref _given, 1) == 0 && _firstLines.TryGetValue(entry, out var line))
                        _say(line);
                    return bytes.Length;
                }
            }
            catch (Exception e)
            {
                SayOnce($"a job's own texture couldn't be given ({e.GetType().Name}: {e.Message}).");
            }
            return _decode!.OriginalFunction(archive, entry, into);
        }

    }
}
