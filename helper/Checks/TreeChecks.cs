// Mod Studio's checks of the helper: (1.49.0) the mods' jobs on Job Progress (JobTree.cs) over a stand-in for the job
// tree, its layout, the figures' keeper and the game's own functions. Part of The Ivalice Chronicles Mod Studio,
// GPL-3.0. Not shipped.
//
//     Checks --tree <request.json>
//
// The request: "own" (for each of the mods' jobs, the jobs of its mod it needs: their places among the jobs), "names",
// "directions" (the game's 20 places' directions as the tree keeps them: 32 bytes a place, eight directions of two
// boxes, each a place and whether the move goes round the board: GeneralJob's, from the 1.5.2 tables), "boxes" (where
// the layout has the game's 20 boxes, by name), and "steps". The stand-in is made up as the game lays the tree out
// (dev/research/sidequests/job_boxes.py holds each place to his program's bytes): a tree of 0x2FD8 bytes, pieces and
// boxes of memory with the fields the framework reads and writes, the layouts' functions as dictionaries by name. It
// proves the framework's code does what was meant over such a tree, never that the game's own functions do what they
// were read to do: only his game shows that (said first in the test's notes).
//
// The game's own update isn't stood in by a model: each time the framework runs it, the tree (or the copy) it is run
// over is reported whole, with a name for every pointer in it, and dev/test_jobs.py runs his program's own update over
// those bytes.
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using ModStudioEventSetup;

static class TreeChecks
{
    public static unsafe int Run(string[] args)
    {
        using var request = JsonDocument.Parse(File.ReadAllText(args[1]));
        var r = request.RootElement;
        var own = new List<int[]>();
        foreach (var list in r.GetProperty("own").EnumerateArray())
        {
            var needs = new List<int>();
            foreach (var n in list.EnumerateArray())
                needs.Add(n.GetInt32());
            own.Add(needs.ToArray());
        }
        var names = new List<string>();
        foreach (var n in r.GetProperty("names").EnumerateArray())
            names.Add(n.GetString()!);
        // (1.50.0) With "needs" (for each job its needs, each [a job of the mods' or -1, the job's number, the level])
        // the tree is made of them and draws its lines and icons; without, as before.
        bool lined = r.TryGetProperty("needs", out var needsGiven);
        var allNeeds = new List<JobTree.Need[]>();
        if (lined)
            foreach (var list in needsGiven.EnumerateArray())
            {
                var of = new List<JobTree.Need>();
                // (1.55.2) A fourth value, true: the job (one of the game's; (1.56.0) or of the mods') needed mastered.
                foreach (var n in list.EnumerateArray())
                    of.Add(new JobTree.Need(n[0].GetInt32(), n[1].GetInt32(), n[2].GetInt32(),
                                            n.GetArrayLength() > 3 && n[3].GetBoolean()));
                allNeeds.Add(of.ToArray());
            }
        var tree = lined ? new JobTree(allNeeds, names) : new JobTree(own, names);
        var plan = tree.Placed;

        byte* Block(int bytes) => (byte*)NativeMemory.AllocZeroed((nuint)bytes);
        string Text(nint name) => Marshal.PtrToStringAnsi(*(nint*)name) ?? "";
        const int PieceBytes = 0x300, BoxBytes = 0x140;
        // Every pointer the stand-in hands out, by a name of its own.
        var labels = new Dictionary<nint, string>();
        nint Label(byte* at, string name)
        {
            labels[(nint)at] = name;
            return (nint)at;
        }
        // The layouts: a piece's pieces and boxes by name, a box's piece (a reference's), a layer's boxes in order.
        var children = new Dictionary<nint, Dictionary<string, nint>>();
        var boxesOf = new Dictionary<nint, Dictionary<string, nint>>();
        var pieceOf = new Dictionary<nint, nint>();
        var holderOf = new Dictionary<nint, nint>();
        var layers = new Dictionary<nint, List<nint>>();
        var playing = new Dictionary<nint, List<string>>();
        var calls = new List<string>();
        var said = new List<string>();
        byte* keeper = Block(JobTree.KeeperSlots + 256 * JobTree.KeeperSlotBytes);
        byte* sprites = Block(256 * JobTree.SpriteSlotBytes);
        bool keeperThere = true;
        byte* gameTree = null, jobTree = null, layer = null, branches = null, receiver = Block(0x40);
        // (1.50.0) What a box is to the layouts' copy (a job's box where it isn't here), a text's number as last
        // written through a setter and the key it was written with, an icon's box's icon, and what the asker knows of
        // a needed job (its icon, the unit's level, whether it is open).
        var kindOf = new Dictionary<nint, string>();
        var written = new Dictionary<nint, int>();
        var writtenKey = new Dictionary<nint, int>();
        var iconOf = new Dictionary<nint, string>();
        var stands = new Dictionary<int, int[]>();
        bool partsReady = true, standFaults = false;
        // (1.55.2) The game's jobs the unit on screen has mastered (by number), as the asker answers.
        var mastered = new HashSet<int>();
        // How many copies the layouts make before their copy answers nothing ("copiesAllowed"; below 0: any number).
        int copiesAllowed = r.TryGetProperty("copiesAllowed", out var allowed) ? allowed.GetInt32() : -1;
        int partsNamed = 0;
        string missingLine = r.TryGetProperty("noLine", out var noLine) ? noLine.GetString()! : "";
        int rightKey = r.TryGetProperty("rightKey", out var rk) ? rk.GetInt32() : 0;
        int topKey = r.TryGetProperty("topKey", out var tk) ? tk.GetInt32() : 1073;
        Label(receiver, "receiver");
        int copies = 0, widgets = 0, setters = 0;
        bool copyFails = false, bare = false;

        nint Piece(string name, nint within)
        {
            byte* piece = Block(PieceBytes);
            children[(nint)piece] = new Dictionary<string, nint>();
            boxesOf[(nint)piece + Marker.PieceTree] = new Dictionary<string, nint>();
            playing[(nint)piece] = new List<string>();
            if (within != 0)
                children[within][name] = (nint)piece;
            return (nint)piece;
        }
        nint Box(string name, nint piece, int kind, int x = 0, int y = 0)
        {
            byte* box = Block(BoxBytes);
            *(int*)(box + Marker.BoxKind) = kind;
            *(int*)(box + JobTree.BoxX) = x;
            *(int*)(box + JobTree.BoxY) = y;
            if (piece != 0)
            {
                boxesOf[piece + Marker.PieceTree][name] = (nint)box;
                holderOf[(nint)box] = piece;
            }
            return (nint)box;
        }
        // A job's box as the layout has one: a reference to a UnitJob piece, which holds the unit's piece (its picture
        // box) and the name board (its title and its level's text).
        nint JobBox(string name, int x, int y, string label)
        {
            nint box = Box(name, (nint)jobTree, MapPieces.ReferenceKind, x, y);
            *(nint*)(box + MapPieces.BoxParent) = (nint)layer;
            nint unitJob = Piece(name, (nint)jobTree);
            pieceOf[box] = unitJob;
            Label((byte*)box, label + " box");
            Label((byte*)unitJob, label);
            if (!bare)
            {
                nint unit = Piece("Unit", unitJob);
                Label((byte*)Box("Unit", unit, Marker.PictureKind), label + " figure");
                nint board = Piece("TextBoardJobName", unitJob);
                Label((byte*)board, label + " board");
                Label((byte*)Box("Title", board, JobTree.TextKind), label + " title");
                Label((byte*)Box("TextLvNum", board, JobTree.TextKind), label + " level");
                if (lined)
                    foreach (string side in new[] { "TextBoardJobLvR", "TextBoardJobLvT" })
                        LabelPiece(side, unitJob, label + (side.EndsWith("R") ? " right label" : " top label"),
                                   side.EndsWith("R") ? rightKey : topKey);
            }
            return box;
        }
        // (1.50.0) A level's label: a piece with its number's text, "Title" (its key as the layout has it, or none
        // where the tree's setup has bound it). In a job's box it is a reference inside the box's piece.
        nint LabelPiece(string name, nint within, string label, int key)
        {
            nint piece = Piece(name, within);
            Label((byte*)piece, label);
            nint title = Box("Title", piece, JobTree.TextKind);
            *(int*)(title + JobTree.TextKey) = key;
            Label((byte*)title, label + " number");
            if (within != 0)
            {
                // In a job's box a label is drawn at 1.2 of its size, as his layout has it.
                nint box = Box(name, within, MapPieces.ReferenceKind);
                pieceOf[box] = piece;
                kindOf[box] = "label";
                *(float*)(box + MapRoads.BoxOpacity) = 1f;
                *(float*)(box + JobTree.BoxScaleX) = 1.2f;
                *(float*)(box + JobTree.BoxScaleY) = 1.2f;
                Label((byte*)box, label + " box");
            }
            return piece;
        }
        // (1.50.0) A line: a reference in the lines' layer to a piece with a bar and a head, each a picture.
        nint LineBox(string name, int x, int y, int wide, int tall, string label)
        {
            nint box = Box(name, (nint)jobTree, MapPieces.ReferenceKind, x, y);
            *(int*)(box + MapPieces.BoxWidth) = wide;
            *(int*)(box + MapPieces.BoxHeight) = tall;
            *(nint*)(box + MapPieces.BoxParent) = (nint)branches;
            *(float*)(box + MapRoads.BoxOpacity) = 1f;
            // (1.52.0) Its scale and its middle as his layout has a line's (1 by 1, half its size).
            *(float*)(box + JobTree.BoxScaleX) = 1f;
            *(float*)(box + JobTree.BoxScaleY) = 1f;
            *(int*)(box + JobTree.BoxMiddleX) = wide / 2;
            *(int*)(box + JobTree.BoxMiddleY) = tall / 2;
            nint piece = Piece(name, (nint)jobTree);
            pieceOf[box] = piece;
            kindOf[box] = "line";
            Label((byte*)box, label + " box");
            Label((byte*)piece, label);
            foreach (string part in new[] { "Image05", "Image02" })
            {
                nint picture = Box(part, piece, Marker.PictureKind);
                *(int*)(picture + Marker.PicturePart) = part == "Image05" ? 6 : 9;
                *(float*)(picture + MapRoads.BoxOpacity) = 1f;
                kindOf[picture] = "picture";
                Label((byte*)picture, label + (part == "Image05" ? " head" : " bar"));
            }
            playing[piece].Add("Unlock");
            return box;
        }

        tree.Child = (piece, name) => children.TryGetValue(piece, out var of) && of.TryGetValue(Text(name), out nint found) ? found : 0;
        tree.Named = (boxes, name) => boxesOf.TryGetValue(boxes, out var of) && of.TryGetValue(Text(name), out nint found) ? found : 0;
        tree.Copy = (layouts, model) =>
        {
            calls.Add($"copy {(labels.TryGetValue(model, out var what) ? what : "?")}{(layouts == (nint)gameTree + 0x1000 ? "" : " elsewhere")}");
            if (copyFails || (copiesAllowed >= 0 && copies >= copiesAllowed))
                return 0;
            // (1.50.0) A line, a level's label or a picture copied: a box of its kind, a reference's piece with it
            // (its boxes as the model's are, its animations as the model's play), sized and placed as the model.
            if (kindOf.TryGetValue(model, out string? kind))
            {
                string made = "copy" + copies++;
                int x = *(int*)(model + JobTree.BoxX), y = *(int*)(model + JobTree.BoxY);
                nint copy;
                if (kind == "line")
                {
                    copy = LineBox(made, x, y, *(int*)(model + MapPieces.BoxWidth), *(int*)(model + MapPieces.BoxHeight), made);
                    playing[pieceOf[copy]].Clear();
                    playing[pieceOf[copy]].AddRange(playing[pieceOf[model]]);
                }
                else if (kind == "label")
                {
                    nint labelCopy = LabelPiece(made, (nint)jobTree, made, *(int*)(boxesOf[pieceOf[model] + Marker.PieceTree]["Title"] + JobTree.TextKey));
                    copy = boxesOf[(nint)jobTree + Marker.PieceTree][made];
                    playing[labelCopy].AddRange(playing[pieceOf[model]]);
                    *(int*)(copy + JobTree.BoxX) = x;
                    *(int*)(copy + JobTree.BoxY) = y;
                    *(float*)(copy + JobTree.BoxScaleX) = *(float*)(model + JobTree.BoxScaleX);
                    *(float*)(copy + JobTree.BoxScaleY) = *(float*)(model + JobTree.BoxScaleY);
                }
                else
                {
                    copy = Box(made, (nint)jobTree, Marker.PictureKind, x, y);
                    kindOf[copy] = "picture";
                    Label((byte*)copy, made + " box");
                    *(int*)(copy + Marker.PicturePart) = *(int*)(model + Marker.PicturePart);
                    *(int*)(copy + MapPieces.BoxWidth) = *(int*)(model + MapPieces.BoxWidth);
                    *(int*)(copy + MapPieces.BoxHeight) = *(int*)(model + MapPieces.BoxHeight);
                    *(float*)(copy + MapRoads.BoxOpacity) = *(float*)(model + MapRoads.BoxOpacity);
                    *(uint*)(copy + Marker.BoxColor) = 0x11223344;
                    *(int*)(copy + MapRoads.BoxColorNumber) = 7;
                }
                *(nint*)(copy + MapPieces.BoxParent) = 0;
                return copy;
            }
            // A copy keeps the copied box's name until it is named, its place and its piece's tag and place.
            string name = "copy" + copies++;
            nint box = JobBox(name, *(int*)(model + JobTree.BoxX), *(int*)(model + JobTree.BoxY), name);
            layers[(nint)layer].Remove(box);
            nint piece = pieceOf[box], from = pieceOf[model];
            *(int*)(piece + JobTree.PieceTag) = *(int*)(from + JobTree.PieceTag);
            *(int*)(piece + JobTree.PiecePlace) = *(int*)(from + JobTree.PiecePlace);
            *(byte*)(piece + JobTree.PieceByte) = 1;
            playing[piece].AddRange(playing[from]);
            return box;
        };
        tree.Rename = (box, characters) =>
        {
            string name = Marshal.PtrToStringAnsi(characters) ?? "";
            var all = boxesOf[(nint)jobTree + Marker.PieceTree];
            foreach (var pair in new List<KeyValuePair<string, nint>>(all))
                if (pair.Value == box)
                {
                    all.Remove(pair.Key);
                    children[(nint)jobTree].Remove(pair.Key);
                }
            all[name] = box;
            if (kindOf.ContainsKey(box))
            {
                // (1.50.0) A line, a label or a picture: its box, its piece and its piece's boxes known by the name.
                labels[box] = name + " box";
                if (pieceOf.TryGetValue(box, out nint named))
                {
                    children[(nint)jobTree][name] = named;
                    labels[named] = name;
                    foreach (var inner in boxesOf[named + Marker.PieceTree])
                        labels[inner.Value] = name + (inner.Key == "Image05" ? " head" : inner.Key == "Image02" ? " bar" : " number");
                }
                return;
            }
            children[(nint)jobTree][name] = pieceOf[box];
            foreach (nint part in new[] { box, pieceOf[box] })
                foreach (string suffix in new[] { "" })
                    labels[part] = name + (part == box ? " box" : suffix);
            foreach (var pair in children[pieceOf[box]])
            {
                if (pair.Key.StartsWith("TextBoardJobLv"))
                {
                    labels[pair.Value] = name + (pair.Key.EndsWith("R") ? " right label" : " top label");
                    labels[boxesOf[pair.Value + Marker.PieceTree]["Title"]] = labels[pair.Value] + " number";
                    continue;
                }
                labels[pair.Value] = name + (pair.Key == "Unit" ? " unit" : " board");
                foreach (var inner in boxesOf[pair.Value + Marker.PieceTree])
                    labels[inner.Value] = name + (inner.Key == "Unit" ? " figure" : inner.Key == "Title" ? " title" : " level");
            }
        };
        tree.Move = (box, x, y) =>
        {
            *(int*)(box + JobTree.BoxX) = x;
            *(int*)(box + JobTree.BoxY) = y;
        };
        tree.Add = (into, box, after) =>
        {
            var list = layers[into];
            list.Remove(box);
            list.Insert(list.IndexOf(after) + 1, box);
            *(nint*)(box + MapPieces.BoxParent) = into;
        };
        tree.Play = (piece, name) =>
        {
            playing[piece].Remove(Text(name));
            playing[piece].Add(Text(name));
        };
        tree.Stop = (piece, name) => playing[piece].Remove(Text(name));
        tree.StopAll = piece => playing[piece].Clear();
        // (1.50.0) A box sized; a line's look and a label's played as the game's two routines play them (0x1347DC,
        // 0x1348B0): the one chosen played, the others stopped; and the asker's record of a needed job.
        tree.Size = (box, wide, tall) =>
        {
            *(int*)(box + MapPieces.BoxWidth) = wide;
            *(int*)(box + MapPieces.BoxHeight) = tall;
            // (1.52.0) As the layouts' sizing (0x3EF6B4): the box changed, its middle half its size (none is fixed here).
            *(byte*)(box + JobTree.BoxChanged) = 1;
            *(int*)(box + JobTree.BoxMiddleX) = wide / 2;
            *(int*)(box + JobTree.BoxMiddleY) = tall / 2;
        };
        void Chosen(nint piece, string[] all, int which)
        {
            foreach (string other in all)
                playing[piece].Remove(other);
            playing[piece].Add(all[which]);
        }
        tree.LinePlay = (piece, on, met) =>
            Chosen(piece, new[] { "Lock", "Unlock", "LockOnCursor", "UnlockOnCursor" }, (met ? 1 : 0) + (on ? 2 : 0));
        tree.LabelPlay = (piece, on, met) => Chosen(piece, new[] { "Hide", "ShowLock", "ShowUnlock" }, on ? met ? 2 : 1 : 0);
        tree.Stand = (job, to) =>
        {
            if (standFaults)
                throw new InvalidOperationException("the asker");
            if (!stands.TryGetValue(job, out int[]? known))
                return false;
            new Span<byte>((void*)to, JobTree.RecordBytes).Clear();
            *(int*)(to + JobTree.RecordIcon) = known[0];
            *(int*)(to + JobTree.RecordLevel) = known[1];
            *(int*)(to + JobTree.RecordClosed) = known[2];
            *(int*)(to + JobTree.RecordJob) = job;
            return true;
        };
        tree.HasMastered = job => mastered.Contains(job);
        var focused = new List<string>();
        tree.Focus = piece => focused.Add(labels.TryGetValue(piece, out var what) ? what : "?");
        tree.Finish = record => *(byte*)(record + 0x1F) = 0x46;
        tree.Figure = (record, box) =>
        {
            // The keeper's giving (0xED9F8): the slot's sprite in use, the keeper's slot the box's.
            int slot = *(int*)record;
            calls.Add($"figure {slot} {(labels.TryGetValue(box, out var what) ? what : "?")} finished {*(byte*)(record + 0x1F) == 0x46}");
            sprites[slot * JobTree.SpriteSlotBytes + JobTree.SpriteInUse] = 1;
            *(nint*)(keeper + JobTree.KeeperSlots + slot * JobTree.KeeperSlotBytes + JobTree.KeeperSlotBox) = box;
            *(int*)(keeper + JobTree.KeeperSlots + slot * JobTree.KeeperSlotBytes + JobTree.KeeperSlotNumber) = slot;
        };
        tree.Free = slot =>
        {
            calls.Add($"free {slot}");
            sprites[slot * JobTree.SpriteSlotBytes + JobTree.SpriteInUse] = 0;
            *(nint*)(keeper + JobTree.KeeperSlots + slot * JobTree.KeeperSlotBytes + JobTree.KeeperSlotBox) = 0;
            *(int*)(keeper + JobTree.KeeperSlots + slot * JobTree.KeeperSlotBytes + JobTree.KeeperSlotNumber) = -1;
        };
        tree.KeeperSlot = slot => keeperThere ? (nint)keeper + JobTree.KeeperSlots + slot * JobTree.KeeperSlotBytes : 0;
        tree.SpriteSlot = slot => keeperThere ? (nint)sprites + slot * JobTree.SpriteSlotBytes : 0;
        var bound = new Dictionary<nint, nint>();
        // (1.49.1) A setter bound to a text box takes the box's text's key and clears it, as the game's does (0x28F5E4).
        var keyOf = new Dictionary<nint, int>();
        tree.Setter = () =>
        {
            setters++;
            return Label(Block(JobTree.SetterBytes), "setter " + setters);
        };
        tree.Bind = (setter, box) =>
        {
            bound[setter] = box;
            keyOf[setter] = *(int*)(box + JobTree.TextKey);
            *(int*)(box + JobTree.TextKey) = 0;
        };
        tree.Write = (holder, six, record, unseen) =>
        {
            var given = new List<string>();
            for (int n = 0; n < JobTree.WriterPlaces; n++)
            {
                nint at = ((nint*)six)[n];
                given.Add(at == 0 ? "-" : labels.TryGetValue(at, out var what) ? what + (bound.TryGetValue(at, out nint to) ? " of " + labels[to] : "") : "?");
            }
            calls.Add($"write {(holder == (nint)gameTree + JobTree.TreeWriter ? "tree" : "elsewhere")} [{string.Join(", ", given)}] job "
                      + $"{*(int*)(record + JobTree.RecordJob)} level {*(int*)(record + JobTree.RecordLevel)} unseen {unseen}");
            // (1.50.0) What the game's writer does with what it is handed: the icon's box given the record's icon (the
            // question mark's where the job isn't to be seen), the level written through the setter with the key it
            // holds (with no key it writes nothing: 0x28F754).
            nint iconBox = ((nint*)six)[JobTree.WriterIcon], levelSetter = ((nint*)six)[JobTree.WriterLevel];
            if (iconBox != 0 && partsReady)
            {
                // The box's parts are named anew only where the name differs (0x29BC00), once they are ready.
                string icon = unseen ? "?" : (*(int*)(record + JobTree.RecordIcon)).ToString();
                if (!iconOf.TryGetValue(iconBox, out var had) || had != icon)
                    *(nint*)(iconBox + Marker.PictureParts) = (nint)(0x5000 + ++partsNamed);
                iconOf[iconBox] = icon;
            }
            if (levelSetter != 0 && bound.TryGetValue(levelSetter, out nint text) && keyOf[levelSetter] != 0)
            {
                written[text] = *(int*)(record + JobTree.RecordLevel);
                writtenKey[text] = keyOf[levelSetter];
            }
        };
        var pressed = new HashSet<int>();
        tree.Pressed = action => pressed.Contains(action);
        var updates = new List<Dictionary<string, object?>>();
        bool updateFaults = false;
        tree.GameUpdate = (at, mode) =>
        {
            if (updateFaults)
                throw new InvalidOperationException("the game's update");
            var pointers = new Dictionary<string, string>();
            for (int place = 0; place < JobTree.GamePlaces; place++)
            {
                nint piece = *(nint*)(at + JobTree.TreePlaces + place * JobTree.PlaceBytes);
                pointers[place.ToString()] = piece == 0 ? "-" : labels.TryGetValue(piece, out var what) ? what : "?";
            }
            updates.Add(new Dictionary<string, object?>
            {
                ["tree"] = at == (nint)gameTree, ["bytes"] = Convert.ToBase64String(new ReadOnlySpan<byte>((void*)at, JobTree.TreeBytes)),
                ["pieces"] = pointers, ["cursor"] = *(int*)(at + JobTree.TreeCursor), ["clicked"] = *(byte*)(at + JobTree.TreeClicked),
                ["receiver"] = labels.TryGetValue(*(nint*)(at + JobTree.TreeReceiver), out var who) ? who : "?",
            });
        };
        var tells = new List<string>();
        tree.Tell = (to, sender, what, which) =>
            tells.Add($"{(labels.TryGetValue(to, out var who) ? who : "?")} {(sender == (nint)gameTree ? "tree" : "elsewhere")} {what:X} {which}");
        int showAnswers = -1;
        var shows = new List<int>();
        tree.ShowJob = job =>
        {
            shows.Add(job);
            return showAnswers;
        };
        tree.Say = said.Add;

        // A tree as the game makes one, set up over a layout read anew: its JobTree piece, the layer with the game's 20
        // boxes where the layout has them, each place's piece and directions.
        void NewTree(bool sameMemory)
        {
            widgets++;
            if (!sameMemory || gameTree == null)
            {
                gameTree = Block(JobTree.TreeBytes + 0x2000);
                Label(gameTree, "tree");
            }
            else
                new Span<byte>(gameTree, JobTree.TreeBytes).Clear();
            jobTree = (byte*)Piece("JobTree" + widgets, 0);
            Label(jobTree, "JobTree " + widgets);
            layer = Block(BoxBytes);
            Label(layer, "LayerRoot " + widgets);
            *(int*)(layer + JobTree.BoxX) = 0;
            *(int*)(layer + JobTree.BoxY) = 32;
            layers[(nint)layer] = new List<nint>();
            if (lined)
            {
                // (1.50.0) The lines' layer and the three of the game's lines copied, where his layout has them.
                branches = Block(BoxBytes);
                Label(branches, "LayerBranches " + widgets);
                layers[(nint)branches] = new List<nint>();
                foreach (var (name, x, y, wide, tall) in new[] { ("LineThiefNinja", 262, 682, 100, 10), ("LineThiefDragoon", 228, 632, 134, 307),
                                                                 ("LineDragoonDancer", 434, 788, 130, 78), ("LineArcherNinja", 267, 364, 174, 194) })
                    if (name != missingLine)
                        layers[(nint)branches].Add(LineBox(name, x, y, wide, tall, name));
            }
            *(int*)(gameTree + JobTree.TreeActor) = 77;
            *(nint*)(gameTree + JobTree.TreeReceiver) = (nint)receiver;
            *(nint*)(gameTree + JobTree.TreeLayouts) = (nint)gameTree + 0x1000;
            *(nint*)(gameTree + JobTree.TreePiece) = (nint)jobTree;
            *(int*)(gameTree + JobTree.TreeOwn) = 0;
            var where = r.GetProperty("boxes");
            for (int place = 0; place < JobTree.GamePlaces; place++)
            {
                string name = JobTree.GameBoxes[place];
                var at = where.GetProperty(name);
                nint box = JobBox(name, at[0].GetInt32(), at[1].GetInt32(), name);
                layers[(nint)layer].Add(box);
                nint piece = pieceOf[box];
                *(int*)(piece + JobTree.PieceTag) = JobTree.JobTag;
                *(int*)(piece + JobTree.PiecePlace) = place;
                *(int*)(piece + JobTree.PieceTells) = 5;
                *(int*)(piece + JobTree.PieceTells + 4) = 77;
                playing[piece].Add("Unlock");
                *(nint*)(gameTree + JobTree.TreePlaces + place * JobTree.PlaceBytes) = piece;
                // The place's own setter holds its level's text's key since the tree's setup bound it (the box's own
                // is 0 from then on, and so is a copy's): "levelKey" in the request, 1073 as his layout has it.
                *(int*)(gameTree + JobTree.TreePlaces + place * JobTree.PlaceBytes + JobTree.PlaceSetter + JobTree.SetterKey) =
                    r.TryGetProperty("levelKey", out var levelKey) ? levelKey.GetInt32() : 1073;
                int n = 0;
                foreach (var value in r.GetProperty("directions")[place].EnumerateArray())
                    gameTree[JobTree.TreeDirections + place * JobTree.PlaceBytes + n++] = (byte)value.GetInt32();
            }
        }

        Dictionary<string, object?> State(object? answer)
        {
            var boxes = new List<Dictionary<string, object?>>();
            for (int k = 0; k < plan.Count; k++)
            {
                nint box = jobTree == null ? 0 : tree.Named((nint)jobTree + Marker.PieceTree, Name(JobTree.BoxPrefix + k));
                if (box == 0)
                {
                    boxes.Add(new Dictionary<string, object?> { ["there"] = false });
                    continue;
                }
                nint piece = pieceOf[box];
                var tells = new List<int>();
                for (int n = 0; n < JobTree.Tells; n++)
                    tells.Add(*(int*)(piece + JobTree.PieceTells + 4 * n));
                int slot = -1;
                nint figure = children[piece].TryGetValue("Unit", out nint unit) ? boxesOf[unit + Marker.PieceTree]["Unit"] : 0;
                for (int s = 0; s <= JobTree.LastSlot && figure != 0; s++)
                    if (*(nint*)(keeper + JobTree.KeeperSlots + s * JobTree.KeeperSlotBytes + JobTree.KeeperSlotBox) == figure)
                        slot = s;
                boxes.Add(new Dictionary<string, object?>
                {
                    ["there"] = true, ["at"] = new[] { *(int*)(box + JobTree.BoxX), *(int*)(box + JobTree.BoxY) },
                    ["layer"] = labels.TryGetValue(*(nint*)(box + MapPieces.BoxParent), out var into) ? into : "?",
                    ["after"] = layers[(nint)layer].IndexOf(box), ["tag"] = *(int*)(piece + JobTree.PieceTag),
                    ["place"] = *(int*)(piece + JobTree.PiecePlace), ["tells"] = tells, ["byte"] = *(byte*)(piece + JobTree.PieceByte),
                    ["playing"] = new List<string>(playing[piece]), ["board"] = children[piece].TryGetValue("TextBoardJobName", out nint board) ? new List<string>(playing[board]) : null,
                    ["slot"] = slot, ["levelKey"] = LevelKey(piece),
                });
            }
            var games = new List<string>();
            if (gameTree != null)
                for (int place = 0; place < JobTree.GamePlaces; place++)
                {
                    nint piece = *(nint*)(gameTree + JobTree.TreePlaces + place * JobTree.PlaceBytes);
                    games.Add($"{*(int*)(piece + JobTree.PieceTag)}:{*(int*)(piece + JobTree.PiecePlace)}:{string.Join("+", playing[piece])}");
                }
            var inUse = new List<int>();
            for (int s = 0; s <= JobTree.LastSlot; s++)
                if (sprites[s * JobTree.SpriteSlotBytes + JobTree.SpriteInUse] != 0)
                    inUse.Add(s);
            var state = new Dictionary<string, object?>
            {
                ["answer"] = answer, ["boxes"] = boxes, ["games"] = games, ["calls"] = new List<string>(calls),
                ["said"] = new List<string>(said), ["focused"] = new List<string>(focused), ["updates"] = new List<object?>(updates),
                ["tells"] = new List<string>(tells), ["shows"] = new List<int>(shows), ["slide"] = tree.Slide, ["worn"] = tree.Worn,
                ["built"] = tree.Built, ["handled"] = tree.Handled, ["inUse"] = inUse, ["setters"] = setters,
                ["layer"] = layer == null ? null : new[] { *(int*)(layer + JobTree.BoxX), *(int*)(layer + JobTree.BoxY) },
                ["order"] = layer == null ? null : layers[(nint)layer].ConvertAll(b => labels.TryGetValue(b, out var what) ? what : "?"),
            };
            if (lined)
            {
                // (1.50.0) What is drawn for each job's needs, the trunks and the right labels, by their names.
                var all = jobTree == null ? null : boxesOf[(nint)jobTree + Marker.PieceTree];
                Dictionary<string, object?>? Shape(string name)
                {
                    if (all == null || !all.TryGetValue(name, out nint box))
                        return null;
                    var shape = new Dictionary<string, object?>
                    {
                        ["at"] = new[] { *(int*)(box + JobTree.BoxX), *(int*)(box + JobTree.BoxY) },
                        ["size"] = new[] { *(int*)(box + MapPieces.BoxWidth), *(int*)(box + MapPieces.BoxHeight) },
                        ["layer"] = labels.TryGetValue(*(nint*)(box + MapPieces.BoxParent), out var into) ? into : "?",
                        ["opacity"] = *(float*)(box + MapRoads.BoxOpacity),
                    };
                    if (pieceOf.TryGetValue(box, out nint piece))
                    {
                        shape["playing"] = new List<string>(playing[piece]);
                        var inner = boxesOf[piece + Marker.PieceTree];
                        if (inner.TryGetValue("Image05", out nint head))
                            shape["head"] = *(float*)(head + MapRoads.BoxOpacity);
                        // (1.52.0) A line's scale (a lead up flipped), its middle, and whether it was changed.
                        if (kindOf.TryGetValue(box, out var isLine) && isLine == "line")
                        {
                            shape["scale"] = new[] { *(float*)(box + JobTree.BoxScaleX), *(float*)(box + JobTree.BoxScaleY) };
                            shape["middle"] = new[] { *(int*)(box + JobTree.BoxMiddleX), *(int*)(box + JobTree.BoxMiddleY) };
                            shape["changed"] = *(byte*)(box + JobTree.BoxChanged);
                        }
                        if (inner.TryGetValue("Title", out nint title))
                        {
                            shape["number"] = written.TryGetValue(title, out int number) ? number : (int?)null;
                            shape["key"] = writtenKey.TryGetValue(title, out int key) ? key : (int?)null;
                            shape["scale"] = new[] { *(float*)(box + JobTree.BoxScaleX), *(float*)(box + JobTree.BoxScaleY) };
                            shape["changed"] = *(byte*)(box + JobTree.BoxChanged);
                        }
                    }
                    else
                    {
                        shape["part"] = *(int*)(box + Marker.PicturePart);
                        shape["color"] = *(uint*)(box + Marker.BoxColor);
                        shape["colorNumber"] = *(int*)(box + MapRoads.BoxColorNumber);
                        shape["visible"] = *(byte*)(box + MapPieces.BoxVisible);
                        shape["icon"] = iconOf.TryGetValue(box, out var icon) ? icon : null;
                    }
                    return shape;
                }
                var drawn = new List<object?>();
                var trunks = new List<object?>();
                var rights = new List<object?>();
                for (int k = 0; k < plan.Count; k++)
                {
                    var of = new List<object?>();
                    for (int n = 0; n < allNeeds[k].Length; n++)
                        of.Add(new Dictionary<string, object?>
                        {
                            ["line"] = Shape($"{JobTree.LinePrefix}{k}_{n}"), ["icon"] = Shape($"{JobTree.IconPrefix}{k}_{n}"),
                            ["label"] = Shape($"{JobTree.LevelPrefix}{k}_{n}"),
                            // (1.51.0) A branch's lead, and the lit copies of the line and of the lead.
                            ["lead"] = Shape($"{JobTree.LeadPrefix}{k}_{n}"), ["lit"] = Shape($"{JobTree.LitPrefix}{k}_{n}"),
                            ["litLead"] = Shape($"{JobTree.LitLeadPrefix}{k}_{n}"),
                        });
                    drawn.Add(of);
                    // (1.51.0) No trunk is made any more (1.50.0's, named so): each is looked for all the same.
                    trunks.Add(Shape("MsqTrunk" + k));
                    nint box = all != null && all.TryGetValue(JobTree.BoxPrefix + k, out nint found) ? found : 0;
                    if (box != 0 && children[pieceOf[box]].TryGetValue("TextBoardJobLvR", out nint right))
                    {
                        nint title = boxesOf[right + Marker.PieceTree]["Title"];
                        rights.Add(new Dictionary<string, object?>
                        {
                            ["playing"] = new List<string>(playing[right]), ["number"] = written.TryGetValue(title, out int number) ? number : (int?)null,
                            ["key"] = writtenKey.TryGetValue(title, out int key) ? key : (int?)null,
                        });
                    }
                    else
                        rights.Add(null);
                }
                state["drawn"] = drawn;
                state["models"] = Array.ConvertAll(JobTree.LineModels, Shape);
                state["trunks"] = trunks;
                state["rights"] = rights;
                state["lines"] = tree.Lines;
                state["lit"] = tree.LitJob;
                state["branches"] = branches == null ? null : layers[(nint)branches].ConvertAll(b => labels.TryGetValue(b, out var what) ? what : "?");
            }
            calls.Clear();
            said.Clear();
            focused.Clear();
            updates.Clear();
            tells.Clear();
            shows.Clear();
            return state;
        }
        // The key the setter bound to a box's level took (-1: none is bound to it).
        int LevelKey(nint piece)
        {
            if (!children[piece].TryGetValue("TextBoardJobName", out nint board)
                || !boxesOf[board + Marker.PieceTree].TryGetValue("TextLvNum", out nint level))
                return -1;
            foreach (var pair in bound)
                if (pair.Value == level)
                    return keyOf[pair.Key];
            return -1;
        }
        // A name as the framework hands one: 16 bytes, where its characters are.
        var madeNames = new Dictionary<string, nint>();
        nint Name(string text)
        {
            if (madeNames.TryGetValue(text, out nint made))
                return made;
            byte* name = Block(16 + text.Length + 1);
            *(nint*)name = (nint)(name + 16);
            Encoding.ASCII.GetBytes(text, new Span<byte>(name + 16, text.Length));
            return madeNames[text] = (nint)name;
        }

        var report = new List<Dictionary<string, object?>>();
        byte* record = Block(JobTree.RecordBytes);
        int mode = 0;
        foreach (var step in r.GetProperty("steps").EnumerateArray())
        {
            string what = step.GetProperty("do").GetString()!;
            object? answer = null;
            if (what == "plan")
            {
                var ways = new List<int[]>();
                for (int k = 0; k < plan.Count; k++)
                {
                    var from = new int[JobTree.Directions];
                    for (int d = 0; d < JobTree.Directions; d++)
                        from[d] = plan.Neighbour(k, d);
                    ways.Add(from);
                }
                var rows = new List<int>();
                var enters = new List<int>();
                for (int row = 0; row < JobTree.Rows; row++)
                    rows.Add(tree.Back(row));
                for (int place = 0; place < JobTree.GamePlaces; place++)
                    enters.Add(tree.Enter(place));
                answer = new Dictionary<string, object?>
                {
                    ["column"] = plan.Column, ["row"] = plan.Row, ["columns"] = plan.Columns, ["ways"] = ways, ["back"] = rows,
                    ["enter"] = enters, ["x"] = Array.ConvertAll(plan.Column, c => JobTree.FirstColumn + JobTree.ColumnStep * c),
                    ["views"] = new[] { JobTree.SlideOf(0), JobTree.SlideOf(1), JobTree.SlideOf(2), JobTree.SlideOf(3) },
                    ["slots"] = new List<int>(JobTree.Slots()), ["gameBoxes"] = JobTree.GameBoxes,
                    ["line"] = JobTree.Line(plan.Count), ["notLine"] = JobTree.NotLine("why"),
                };
                if (lined)
                {
                    // (1.50.0) Where each need's line stands (its kind, place, size and how far its trunk reaches) or
                    // its icon's cell, and the lines' words.
                    var places = new List<object?>();
                    for (int k = 0; k < plan.Count; k++)
                    {
                        var of = new List<object?>();
                        int icons = 0;
                        foreach (var need in allNeeds[k])
                            if (need.Own >= 0)
                            {
                                var at = tree.LineAt(k, need.Own);
                                var lead = tree.LeadAt(k, need.Own);
                                // (1.51.0) With a branch's lead: where it starts and how wide it is. (1.52.0) The lead's
                                // kind, place and size and whether it is flipped; then the way: its place at the job's
                                // side, its way out, its lane of how many, whether it turns into its job, its level.
                                var way = tree.WayOf(k, need.Own);
                                of.Add(new[] { at.Kind, at.X, at.Y, at.Wide, at.Tall, lead.Kind, lead.X, lead.Y, lead.Wide, lead.Tall,
                                               lead.Flip ? 1 : 0, way.Entry, way.Exit, way.Lane, way.Lanes, way.Far ? 1 : 0, way.Level });
                            }
                            else
                            {
                                var cell = tree.IconCell(k, icons++);
                                of.Add(new[] { cell.X, cell.Y });
                            }
                        places.Add(of);
                    }
                    var more = (Dictionary<string, object?>)answer;
                    more["needs"] = places;
                    more["linesLine"] = JobTree.LinesLine;
                    more["linesNotLine"] = JobTree.LinesNotLine("why");
                    more["linesNotFound"] = JobTree.LinesNotFound(new[] { "this", "that" });
                    more["linesFaultLine"] = JobTree.LinesFaultLine("what");
                    more["lineModels"] = JobTree.LineModels;
                }
            }
            else if (what == "tree")
            {
                bare = step.TryGetProperty("bare", out var isBare) && isBare.GetBoolean();
                NewTree(!step.TryGetProperty("moved", out var moved) || !moved.GetBoolean());
                if (step.TryGetProperty("unset", out var unset) && unset.GetBoolean())
                    *(nint*)(gameTree + JobTree.TreePiece) = 0;
            }
            else if (what == "give")
            {
                new Span<byte>(record, JobTree.RecordBytes).Clear();
                *(int*)(record + JobTree.RecordJob) = step.GetProperty("number").GetInt32();
                *(int*)(record + JobTree.RecordLevel) = step.GetProperty("level").GetInt32();
                *(int*)(record + JobTree.RecordClosed) = step.GetProperty("closed").GetInt32();
                record[JobTree.RecordWorn] = (byte)(step.TryGetProperty("worn", out var worn) && worn.GetBoolean() ? 1 : 0);
                *(int*)(record + JobTree.RecordFigure) = 0x3D + step.GetProperty("job").GetInt32() % 19;
                copyFails = step.TryGetProperty("copyFails", out var fails) && fails.GetBoolean();
                tree.Harvested(step.GetProperty("job").GetInt32(), (nint)record, (nint)gameTree);
                copyFails = false;
                var kept = tree.Record(step.GetProperty("job").GetInt32());
                answer = kept == null ? null : new[] { *(int*)(kept + JobTree.RecordFigure), *(int*)(kept + JobTree.RecordJob) };
            }
            else if (what == "begin")
                tree.Begin();
            else if (what == "empty")
                tree.Empty((nint)gameTree);
            else if (what == "taken")
            {
                // Slots other screens have: a sprite in use there, or a picture box of another's in the keeper's.
                foreach (var s in step.GetProperty("slots").EnumerateArray())
                    sprites[s.GetInt32() * JobTree.SpriteSlotBytes + JobTree.SpriteInUse] = 1;
                if (step.TryGetProperty("boxes", out var others))
                    foreach (var s in others.EnumerateArray())
                        *(nint*)(keeper + JobTree.KeeperSlots + s.GetInt32() * JobTree.KeeperSlotBytes + JobTree.KeeperSlotBox) = (nint)receiver;
            }
            else if (what == "keeper")
                keeperThere = step.GetProperty("there").GetBoolean();
            else if (what == "update")
            {
                pressed.Clear();
                if (step.TryGetProperty("pressed", out var keys))
                    foreach (var key in keys.EnumerateArray())
                        pressed.Add(key.GetInt32());
                *(int*)(gameTree + JobTree.TreeCursor) = step.GetProperty("cursor").GetInt32();
                gameTree[JobTree.TreeClicked] = (byte)(step.TryGetProperty("clicked", out var clicked) && clicked.GetBoolean() ? 1 : 0);
                showAnswers = step.TryGetProperty("shows", out var shown) ? shown.GetInt32() : -1;
                updateFaults = step.TryGetProperty("faults", out var faults) && faults.GetBoolean();
                mode = JobTree.TreeMode;
                int times = step.TryGetProperty("times", out var repeat) ? repeat.GetInt32() : 1;
                var slides = new List<float>();
                string? fault = null;
                for (int n = 0; n < times; n++)
                {
                    try
                    {
                        tree.Update((nint)gameTree, (nint)(&mode));
                    }
                    catch (Exception e)
                    {
                        fault = e.GetType().Name;
                    }
                    slides.Add(tree.Slide);
                }
                updateFaults = false;
                answer = new Dictionary<string, object?> { ["mode"] = mode, ["slides"] = slides, ["fault"] = fault };
            }
            else if (what == "shown")
                tree.Shown((nint)gameTree, step.GetProperty("mode").GetInt32());
            else if (what == "released")
                tree.Released();
            else if (what == "stand")
            {
                // (1.50.0) What the asker knows of the needed jobs from now on: each job's icon, the unit's level in it
                // and whether it is open (0), locked (1) or not to be seen (2).
                stands.Clear();
                foreach (var job in step.GetProperty("jobs").EnumerateObject())
                    stands[int.Parse(job.Name)] = new[] { job.Value[0].GetInt32(), job.Value[1].GetInt32(), job.Value[2].GetInt32() };
            }
            else if (what == "mastered")
            {
                // (1.55.2) The game's jobs the unit on screen has mastered from now on (by number).
                mastered.Clear();
                foreach (var job in step.GetProperty("jobs").EnumerateArray())
                    mastered.Add(job.GetInt32());
            }
            else if (what == "parts")
                // (1.50.0) Whether an icon's texture parts are ready when the writer asks for them.
                partsReady = step.GetProperty("ready").GetBoolean();
            else if (what == "asker")
                // (1.50.0) Whether the asker faults when it is asked for a needed job's record.
                standFaults = step.GetProperty("faults").GetBoolean();
            else if (what == "without")
                // (1.50.0) A place the lines need wasn't found in the program: the tree is told why.
                tree.LinesWithout = step.GetProperty("why").GetString();
            else if (what == "rest")
                // (1.49.1) The layout rests the layer where it has it, whatever it was moved by.
                *(int*)(layer + JobTree.BoxX) = 0;
            else
                throw new InvalidOperationException($"no step {what}");
            report.Add(State(answer));
        }
        Console.WriteLine(JsonSerializer.Serialize(report));
        return 0;
    }
}
