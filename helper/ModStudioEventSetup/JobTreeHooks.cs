// Mod Studio Framework: (1.49.0) the mods' jobs on Job Progress, the hooks and the game's own functions (JobTree.cs
// says what the game does and what the framework does with it). Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Three functions of the tree's own are hooked, each one of the tree's class with one way to it: its update (0x133FA4,
// called by the unit screens' holder, which goes straight to its end after the call), its showing as the menu's mode
// changes (0x133F30, called through the tree's own table by the holder, which sets every register it reads after the
// call anew or keeps it where a function must keep it) and its giving back of its figures (0x133EB8, in the tree's
// own table; no call of it was found). So no caller keeps anything in a register a function may change.
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using Reloaded.Hooks.Definitions;
using Reloaded.Hooks.Definitions.X64;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    public sealed unsafe class JobTreeHooks
    {
        [Function(CallingConventions.Microsoft)]
        public delegate void UpdateFunction(nint tree, nint mode);

        [Function(CallingConventions.Microsoft)]
        public delegate void ShownFunction(nint tree, int mode, int was);

        [Function(CallingConventions.Microsoft)]
        public delegate void ReleaseFunction(nint tree);

        readonly JobTree _tree;
        readonly Action<string> _say;
        readonly HashSet<string> _saidOnce = new HashSet<string>();
        IHook<UpdateFunction>? _update;
        IHook<ShownFunction>? _shown;
        IHook<ReleaseFunction>? _release;

        JobTreeHooks(JobTree tree, Action<string> say)
        {
            _tree = tree;
            _say = say;
        }

        void SayOnce(string line)
        {
            lock (_saidOnce)
                if (!_saidOnce.Add(line))
                    return;
            _say(line);
        }

        /// <summary>The layouts' functions the boxes are made with, each found by the world map's places (Places): null
        /// where all are there, else what isn't.</summary>
        public static string? Lacking(Places places)
        {
            var lacking = new List<string>();
            void Need(int at, string what)
            {
                if (at < 0)
                    lacking.Add(what);
            }
            Need(places.ChildPiece, "the layouts' finding of a piece");
            Need(places.BoxNamed, "the layouts' finding of a box");
            Need(places.PieceCopy, "the layouts' copy of a box");
            Need(places.PieceMove, "the layouts' move of a box");
            Need(places.PieceAdd, "the layouts' putting of a box in a layer");
            Need(places.AnimationPlay, "the layouts' playing of an animation");
            Need(places.AnimationStop, "the layouts' stopping of an animation");
            Need(places.AnimationsStop, "the layouts' stopping of a piece's animations");
            Need(places.StringMake, "the game's making of a string");
            Need(places.StringAssign, "the game's giving of a string");
            Need(places.StringRelease, "the game's letting go of a string");
            Need(places.StringPool, "the game's strings");
            return lacking.Count == 0 ? null : string.Join(", ", lacking);
        }

        /// <summary>The tree given the game's own functions, the job screen's rows told to run the filling for the mods'
        /// jobs, and the three hooks made. Null and why where they can't be (the rows are then told nothing, and Job
        /// Progress is the game's).</summary>
        public static JobTreeHooks? Arm(IReloadedHooks reloaded, GameMemory memory, JobTree.Sites sites, Places places, JobTree tree,
                                        JobScreen rows, Action<string> say, out string why)
        {
            string? lacking = Lacking(places);
            if (lacking != null)
            {
                why = $"{lacking} wasn't found";
                return null;
            }
            byte* start = memory.Base;
            var hooks = new JobTreeHooks(tree, say);
            Wire(start, sites, places, tree);
            tree.Say = hooks.SayOnce;
            tree.ShowJob = rows.Show;
            try
            {
                hooks._update = reloaded.CreateHook<UpdateFunction>(hooks.Update, (long)(start + sites.Update), -1);
                hooks._shown = reloaded.CreateHook<ShownFunction>(hooks.Shown, (long)(start + sites.Shown), -1);
                hooks._release = reloaded.CreateHook<ReleaseFunction>(hooks.Release, (long)(start + sites.Release), -1);
                var update = hooks._update;
                tree.GameUpdate = (at, mode) => update.OriginalFunction(at, mode);
                hooks._update.Activate();
                hooks._shown.Activate();
                hooks._release.Activate();
            }
            catch (Exception e)
            {
                hooks.TurnOff();
                why = $"its hooks couldn't be made ({e.GetType().Name}: {e.Message})";
                return null;
            }
            rows.Harvested = hooks.Harvested;
            rows.HarvestBegins = tree.Begin;
            rows.HarvestNone = hooks.None;
            why = "";
            return hooks;
        }

        /// <summary>The tree's own functions of the game's, each called as the game calls it.</summary>
        static void Wire(byte* start, JobTree.Sites sites, Places places, JobTree tree)
        {
            var child = (delegate* unmanaged<nint, nint, nint>)(start + places.ChildPiece);
            var named = (delegate* unmanaged<nint, nint, nint>)(start + places.BoxNamed);
            var copy = (delegate* unmanaged<nint, nint, byte, nint>)(start + places.PieceCopy);
            var move = (delegate* unmanaged<nint, int, int, void>)(start + places.PieceMove);
            var add = (delegate* unmanaged<nint, nint, nint, void>)(start + places.PieceAdd);
            var play = (delegate* unmanaged<nint, nint, int, void>)(start + places.AnimationPlay);
            var stop = (delegate* unmanaged<nint, nint, void>)(start + places.AnimationStop);
            var stopAll = (delegate* unmanaged<nint, void>)(start + places.AnimationsStop);
            var make = (delegate* unmanaged<nint, nint, nint>)(start + places.StringMake);
            var assign = (delegate* unmanaged<nint, nint, nint>)(start + places.StringAssign);
            var release = (delegate* unmanaged<nint, uint, int>)(start + places.StringRelease);
            nint* pool = (nint*)(start + places.StringPool);
            var focus = (delegate* unmanaged<nint, void>)(start + sites.Focus);
            var finish = (delegate* unmanaged<nint, int, int, byte, void>)(start + sites.Finish);
            var figure = (delegate* unmanaged<nint, nint, nint, byte>)(start + sites.Figure);
            var clear = (delegate* unmanaged<nint, void>)(start + sites.Clear);
            var free = (delegate* unmanaged<nint, int, void>)(start + sites.Free);
            var write = (delegate* unmanaged<nint, nint, nint, byte, void>)(start + sites.Write);
            var setter = (delegate* unmanaged<nint, nint>)(start + sites.Setter);
            var bind = (delegate* unmanaged<nint, nint, void>)(start + sites.Bind);
            var pressed = (delegate* unmanaged<int, int, int, byte, byte>)(start + sites.Pressed);
            nint* keeper = (nint*)(start + sites.Keeper);
            nint* sprites = (nint*)(start + sites.Sprites);

            tree.Child = (piece, name) => child(piece, name);
            tree.Named = (boxes, name) => named(boxes, name);
            tree.Copy = (layouts, box) => copy(layouts, box, 0);
            tree.Move = (box, x, y) => move(box, x, y);
            tree.Add = (layer, box, after) => add(layer, box, after);
            // A box's name: a string of the game's made of the characters, given to the box's, the framework's let go
            // (as MapPieces names a place's copy).
            tree.Rename = (box, characters) =>
            {
                byte* made = stackalloc byte[16];
                for (int n = 0; n < 16; n++)
                    made[n] = 0;
                make((nint)made, characters);
                assign(box + MapPieces.BoxName, (nint)made);
                uint number = *(uint*)(made + 8);
                if (number != 0)
                    release(*pool, number);
            };
            // An animation played from its start, as the tree's own giving of a job plays one.
            tree.Play = (piece, name) => play(piece, name, 0);
            tree.Stop = (piece, name) => stop(piece, name);
            tree.StopAll = piece => stopAll(piece);
            tree.Focus = piece => focus(piece);
            // A figure's record finished as the tree finishes it (facing 0, the kind 4, not turned), then given to the
            // keeper with its picture box.
            tree.Finish = record => finish(record, 0, 4, 0);
            tree.Figure = (record, box) =>
            {
                if (*keeper != 0)
                    figure(*keeper, record, box);
            };
            tree.KeeperSlot = slot => *keeper == 0 ? 0 : *keeper + JobTree.KeeperSlots + slot * JobTree.KeeperSlotBytes;
            tree.SpriteSlot = slot =>
            {
                nint table = *sprites == 0 ? 0 : *(nint*)(*sprites + JobTree.SpriteSlots);
                return table == 0 ? 0 : table + slot * JobTree.SpriteSlotBytes;
            };
            // A slot given back as the tree gives its own back: the keeper's cleared, the sprite's given back.
            tree.Free = slot =>
            {
                if (slot < 0 || slot > JobTree.LastSlot || *keeper == 0)
                    return;
                clear(*keeper + JobTree.KeeperSlots + slot * JobTree.KeeperSlotBytes);
                nint table = *sprites == 0 ? 0 : *(nint*)(*sprites + JobTree.SpriteSlots);
                if (table != 0)
                    free(table, slot);
            };
            tree.Write = (holder, places6, record, unseen) => write(holder, places6, record, (byte)(unseen ? 1 : 0));
            // A text setter: its bytes, never given back (the game's keeper of them knows it from then on), made by
            // the game's own maker.
            tree.Setter = () =>
            {
                nint memory = (nint)NativeMemory.AllocZeroed(JobTree.SetterBytes);
                setter(memory);
                return memory;
            };
            tree.Bind = (made, box) => bind(made, box);
            // (1.50.0) The lines and the small icons: a box sized as the game's animations size one, and the tree's
            // own play of a line's look and of a label's (each: -, the piece, under the cursor, met). Where one of
            // the three isn't found the tree is told, and its boxes stand without lines.
            if (places.BoxSize >= 0 && sites.LinePlay >= 0 && sites.LabelPlay >= 0)
            {
                var size = (delegate* unmanaged<nint, int, int, void>)(start + places.BoxSize);
                var linePlay = (delegate* unmanaged<nint, nint, byte, byte, void>)(start + sites.LinePlay);
                var labelPlay = (delegate* unmanaged<nint, nint, byte, byte, void>)(start + sites.LabelPlay);
                tree.Size = (box, wide, tall) => size(box, wide, tall);
                tree.LinePlay = (piece, on, met) => linePlay(0, piece, (byte)(on ? 1 : 0), (byte)(met ? 1 : 0));
                tree.LabelPlay = (piece, on, met) => labelPlay(0, piece, (byte)(on ? 1 : 0), (byte)(met ? 1 : 0));
            }
            else
            {
                var lacking = new List<string>(sites.LinesMissing);
                if (places.BoxSize < 0)
                    lacking.Add("the layouts' sizing of a box");
                tree.LinesWithout = JobTree.LinesNotFound(lacking);
            }
            tree.Pressed = action => pressed(0, 0, action, 0) != 0;
            // The receiver told as the tree's update tells it: its function at + 0x30 (the receiver, the tree, what,
            // which, and a fifth of 0).
            tree.Tell = (receiver, sender, what, which) =>
            {
                nint function = *(nint*)(*(nint*)receiver + JobTree.ReceiverTell);
                ((delegate* unmanaged<nint, nint, int, int, int, void>)function)(receiver, sender, what, which, 0);
            };
        }

        void TurnOff()
        {
            foreach (var hook in new IHook[] { _update!, _shown!, _release! })
                try
                {
                    if (hook != null && hook.IsHookActivated)
                        hook.Disable();
                }
                catch (Exception)
                {
                }
        }

        void Harvested(int job, nint record, nint tree)
        {
            try
            {
                _tree.Harvested(job, record, tree);
            }
            catch (Exception e)
            {
                SayOnce($"one of the mods' jobs couldn't be given to its box on Job Progress ({e.GetType().Name}: {e.Message}); "
                        + "its box shows what it showed.");
            }
        }

        void None(nint tree)
        {
            try
            {
                _tree.Empty(tree);
            }
            catch (Exception e)
            {
                SayOnce($"the mods' jobs' boxes on Job Progress couldn't be put away ({e.GetType().Name}: {e.Message}).");
            }
        }

        /// <summary>The tree's update: the framework's (JobTree.Update), which hands on to the game's own. A fault before
        /// the game's update ran runs it once, as it came.</summary>
        void Update(nint tree, nint mode)
        {
            try
            {
                _tree.Update(tree, mode);
            }
            catch (Exception e)
            {
                SayOnce($"the cursor on Job Progress couldn't be moved among the mods' jobs ({e.GetType().Name}: {e.Message}); "
                        + "the game's own cursor is used.");
                if (!_tree.Handled)
                    _update!.OriginalFunction(tree, mode);
            }
        }

        /// <summary>The tree's showing: the game's own, then the framework's.</summary>
        void Shown(nint tree, int mode, int was)
        {
            _shown!.OriginalFunction(tree, mode, was);
            try
            {
                _tree.Shown(tree, mode);
            }
            catch (Exception e)
            {
                SayOnce($"Job Progress couldn't be opened on one of the mods' jobs ({e.GetType().Name}: {e.Message}); it opens as "
                        + "the game opens it.");
            }
        }

        /// <summary>The tree's giving back of its figures: the framework's given back, then the game's own.</summary>
        void Release(nint tree)
        {
            try
            {
                _tree.Released();
            }
            catch (Exception e)
            {
                SayOnce($"the mods' jobs' figures on Job Progress couldn't be given back ({e.GetType().Name}: {e.Message}).");
            }
            _release!.OriginalFunction(tree);
        }
    }
}
