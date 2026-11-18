// Mod Studio Framework: (1.46.0) a job's own icons and pictures, the hooks that answer them (JobArt.cs says what they
// answer and why). Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using Reloaded.Hooks.Definitions;
using Reloaded.Hooks.Definitions.X64;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    public sealed unsafe class JobArtHooks
    {
        [Function(CallingConventions.Microsoft)]
        public delegate void PictureFunction(nint answer, nint record, byte asked);

        [Function(CallingConventions.Microsoft)]
        public delegate void IconFunction(nint holder, nint box, int number, nint second, nint fifth, byte question);

        [Function(CallingConventions.Microsoft)]
        public delegate int CommandNameFunction(nint buffer, int number, int size);

        [Function(CallingConventions.Microsoft)]
        public delegate int CommandIconFunction(nint buffer, int skillset);

        /// <summary>A job's record as the picture routine reads it: the job (+0), a generic unit's 0x4A else the unit's
        /// own (+4), the unit's sex byte (+8, its top bit a man).</summary>
        const int RecordJob = 0, RecordSex = 8;

        readonly JobArt.Plan _plan;
        readonly Action<string> _say;
        readonly HashSet<string> _saidOnce = new HashSet<string>();
        readonly nint _boxLoad;
        IHook<PictureFunction>? _picture;
        IHook<IconFunction>? _icon;
        IHook<CommandNameFunction>? _commandName;
        IHook<CommandIconFunction>? _commandIcon;

        JobArtHooks(JobArt.Plan plan, nint boxLoad, Action<string> say)
        {
            _plan = plan;
            _boxLoad = boxLoad;
            _say = say;
        }

        /// <summary>The hooks made: the picture routine's for every job given (its own pictures, or none), the icons' only
        /// where a job gives an icon of its own; each job's own parts answered are marked (Given.IconOwn, CommandOwn,
        /// Pictures), so its rows name them (JobRoom, JobArt through JobHooks). Null and why where they can't be (none
        /// marked then).</summary>
        public static JobArtHooks? Arm(IReloadedHooks reloaded, GameMemory memory, JobArt.Sites sites, IList<JobRoom.Given> given,
                                       Action<string> say, out string why)
        {
            var plan = JobArt.PlanOf(given);
            if (plan.Empty)
            {
                why = "no job is given";
                return null;
            }
            var hooks = new JobArtHooks(plan, (nint)(memory.Base + sites.BoxLoad), say);
            try
            {
                if (plan.Pictures.Count > 0)
                {
                    hooks._picture = reloaded.CreateHook<PictureFunction>(hooks.Picture, (long)(memory.Base + sites.Picture), -1);
                    hooks._picture.Activate();
                }
                if (plan.Icons.Count > 0)
                {
                    hooks._icon = reloaded.CreateHook<IconFunction>(hooks.Icon, (long)(memory.Base + sites.Icon), -1);
                    hooks._icon.Activate();
                }
                if (plan.Commands.Count > 0)
                {
                    hooks._commandName = reloaded.CreateHook<CommandNameFunction>(hooks.CommandName,
                                                                                  (long)(memory.Base + sites.CommandName), -1);
                    hooks._commandName.Activate();
                    hooks._commandIcon = reloaded.CreateHook<CommandIconFunction>(hooks.CommandIcon,
                                                                                  (long)(memory.Base + sites.CommandIcon), -1);
                    hooks._commandIcon.Activate();
                }
            }
            catch (Exception e)
            {
                hooks.TurnOff();
                why = $"their hooks couldn't be made ({e.GetType().Name}: {e.Message})";
                return null;
            }
            foreach (var g in given)
            {
                g.IconOwn = plan.Icons.ContainsKey(g.Number);
                g.CommandOwn = plan.Commands.ContainsKey(g.Number);
                for (int woman = 0; woman < 2; woman++)
                    g.Pictures[woman] = JobArt.PictureFor(plan, g.Number, woman == 0) > 0;
            }
            why = "";
            return hooks;
        }

        void TurnOff()
        {
            foreach (var hook in new IHook[] { _picture!, _icon!, _commandName!, _commandIcon! })
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

        void First(string what, int job)
            => SayOnce(JobArt.FirstLine(what, _plan.Whose.TryGetValue(job, out var whose) ? whose : $"job {job}"));

        /// <summary>The picture routine: the game's answer, then for a job given its own picture's key (shown on the job
        /// screen as the game shows its generic jobs') or, where it gives no art for that sex, the key 0 (shown nowhere);
        /// every other job's as the game's.</summary>
        void Picture(nint answer, nint record, byte asked)
        {
            _picture!.OriginalFunction(answer, record, asked);
            try
            {
                int job = *(int*)(record + RecordJob);
                bool man = *(sbyte*)(record + RecordSex) < 0;
                int? key = JobArt.PictureFor(_plan, job, man);
                if (key == null)
                    return;
                JobArt.Answer(new Span<byte>((void*)answer, 5), key.Value, asked != 0);
                if (key > 0)
                    First(man ? "man's picture" : "woman's picture", job);
            }
            catch (Exception e)
            {
                SayOnce($"a job's own picture couldn't be given ({e.GetType().Name}: {e.Message}).");
            }
        }

        /// <summary>The icon routine: a number of a job's own icon loads its part list into the box as the game's routine
        /// loads its own (the question mark, and every other number, as the game's).</summary>
        void Icon(nint holder, nint box, int number, nint second, nint fifth, byte question)
        {
            try
            {
                if (question == 0 && _plan.Icons.TryGetValue(number, out var name))
                {
                    var bytes = JobArt.IconName(name);
                    if (bytes.Length <= JobArt.IconBytes)
                    {
                        fixed (byte* text = bytes)
                            ((delegate* unmanaged<nint, nint, nint, nint, nint, void>)_boxLoad)(holder, box, (nint)text, second, fifth);
                        First("icon", number);
                        return;
                    }
                }
            }
            catch (Exception e)
            {
                SayOnce($"a job's own icon couldn't be given ({e.GetType().Name}: {e.Message}).");
            }
            _icon!.OriginalFunction(holder, box, number, second, fifth, question);
        }

        /// <summary>The skillset icon's name routine: a number of a job's skillset's own icon writes its part list's name
        /// as the game's routine writes its own; every other as the game's.</summary>
        int CommandName(nint buffer, int number, int size)
        {
            try
            {
                if (_plan.Commands.TryGetValue(number, out var name) && Write(buffer, JobArt.CommandName(name), size))
                {
                    First("skillset icon", number);
                    return JobArt.CommandName(name).Length - 1;
                }
            }
            catch (Exception e)
            {
                SayOnce($"a job's skillset's own icon couldn't be named ({e.GetType().Name}: {e.Message}).");
            }
            return _commandName!.OriginalFunction(buffer, number, size);
        }

        /// <summary>The skillset icon routine: a job's own skillset with an icon of its own writes its part list's name (the
        /// game's routine would turn the job's number into the empty icon); every other as the game's.</summary>
        int CommandIcon(nint buffer, int skillset)
        {
            try
            {
                if (_plan.CommandsBySkillset.TryGetValue(skillset, out var name)
                    && Write(buffer, JobArt.CommandName(name), JobArt.CommandBytes))
                {
                    if (_plan.SkillsetJob.TryGetValue(skillset, out int job))
                        First("skillset icon", job);
                    return JobArt.CommandName(name).Length - 1;
                }
            }
            catch (Exception e)
            {
                SayOnce($"a job's skillset's own icon couldn't be named ({e.GetType().Name}: {e.Message}).");
            }
            return _commandIcon!.OriginalFunction(buffer, skillset);
        }

        static bool Write(nint buffer, byte[] bytes, int size)
        {
            if (buffer == 0 || bytes.Length > size)
                return false;
            Marshal.Copy(bytes, 0, buffer, bytes.Length);
            return true;
        }
    }
}
