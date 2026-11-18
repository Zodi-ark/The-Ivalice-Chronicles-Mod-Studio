// Mod Studio Framework: (1.26.0) a mod's own items in the running game. Part
// of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// ItemRoom.cs measures and plans; this makes it so as the game starts: the
// items' data and the nine functions' native code, hooked; the bounds raised;
// and, with no other mod's page, the page made, the reaches and the two calls
// changed, a thread keeping the game's own arrays and the page's alike. Either
// way the items' counts are kept in the save's event variables (a save hook
// and the same thread), a mod's town's Outfitter lists its items after the
// game's, and an item's icon is its own or a game item's.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using Reloaded.Hooks.Definitions;
using Reloaded.Hooks.Definitions.X64;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    public sealed unsafe class ItemHooks
    {
        [Function(CallingConventions.Microsoft)]
        public delegate nint GetterFunction(ushort id);

        [Function(CallingConventions.Microsoft)]
        public delegate nint SaveFunction(nint a, nint b, nint c, nint d);

        [Function(CallingConventions.Microsoft)]
        public delegate int IconPathFunction(nint buffer, int number, int size);

        [Function(CallingConventions.Microsoft)]
        public delegate int SheetInitFunction(nint sheet, nint file);

        readonly byte* _base;
        readonly ItemRoom.Found _found;
        readonly List<ItemRoom.Given> _given;
        readonly Dictionary<int, ItemRoom.Given> _byNumber = new Dictionary<int, ItemRoom.Given>();
        readonly Action<string> _say;
        readonly int _worldBank;
        readonly object _lock = new object();
        readonly HashSet<string> _saidOnce = new HashSet<string>(StringComparer.Ordinal);
        readonly ItemRoom.Counts _counts = new ItemRoom.Counts();
        /// <summary>(2.0.0) War of the Lions' items where the framework gives them (WotLItems.cs; empty where it gives
        /// none), with the mods' own after them (`_all`: every item whose row, icon and place in a shop are the
        /// framework's), and their counts kept in a save where WotL Restoration keeps its own.</summary>
        readonly List<ItemRoom.Given> _wotl, _all;
        readonly WotLItems.Counts _wotlCounts = new WotLItems.Counts();
        readonly List<object> _kept = new List<object>();
        IHook<SaveFunction>? _save;
        IHook<IconPathFunction>? _icon, _smallIcon;
        IHook<SheetInitFunction>? _sheetInit;
        readonly HashSet<nint> _copies = new HashSet<nint>();
        byte* _page;
        byte* _bag;
        // (no other mod's page) the game's own arrays and the page's, as last seen alike
        byte[]? _lastBag, _lastPageBag, _lastRows;
        readonly List<(nint Game, int GameWords, nint Page, byte[] LastGame, byte[] LastPage)> _lists =
            new List<(nint, int, nint, byte[], byte[])>();

        /// <summary>How often the thread keeps the counts and the arrays alike (ms).</summary>
        public const int Interval = 200;

        ItemHooks(byte* start, ItemRoom.Found found, List<ItemRoom.Given> given, int worldBank, Action<string> say,
                  List<ItemRoom.Given>? wotl = null)
        {
            _base = start;
            _found = found;
            _given = given;
            _wotl = wotl ?? new List<ItemRoom.Given>();
            _all = new List<ItemRoom.Given>(_wotl);
            _all.AddRange(given);
            foreach (var g in _all)
                _byNumber[g.Number] = g;
            _worldBank = worldBank;
            _say = say;
        }

        public IReadOnlyList<ItemRoom.Given> Given => _given;
        /// <summary>(2.0.0) War of the Lions' items the framework gives (none where it gives none).</summary>
        public IReadOnlyList<ItemRoom.Given> WotL => _wotl;
        public bool Has(int number) => _byNumber.ContainsKey(number);

        /// <summary>(1.35.0) The numbers' ID a save holding the mods' items is marked with as it is made, when it has
        /// no mark yet (0: none), and where the party a save keeps is (Places.Roster, -1 for its bag alone): so a free
        /// from then on takes them out of it as it loads (Framework.Loaded).</summary>
        public uint MarkWith { get; set; }
        public int Roster { get; set; } = -1;

        void SayOnce(string line)
        {
            lock (_saidOnce)
                if (!_saidOnce.Add(line))
                    return;
            _say(line);
        }

        // --- in the game ---------------------------------------------------------------------------------------------

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern nint VirtualAlloc(nint address, nuint size, uint type, uint protect);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool VirtualProtect(nint address, nuint size, uint protect, out uint old);

        [DllImport("kernel32.dll")]
        static extern nint GetCurrentProcess();

        [DllImport("kernel32.dll")]
        static extern bool FlushInstructionCache(nint process, nint address, nuint size);

        const uint Commit = 0x1000, Reserve = 0x2000, ReadWrite = 0x04, ExecuteRead = 0x20, ExecuteReadWrite = 0x40;
        const long Reach = 0x7F000000;

        static nint Near(ulong imageBase, int imageSize, int size)
        {
            const ulong Granularity = 0x10000;
            ulong start = (imageBase + (ulong)imageSize + Granularity - 1) & ~(Granularity - 1);
            for (ulong at = start; at + (ulong)size < imageBase + (ulong)Reach; at += Granularity)
            {
                nint got = VirtualAlloc((nint)at, (nuint)size, Commit | Reserve, ReadWrite);
                if (got != 0)
                    return got;
            }
            return 0;
        }

        /// <summary>The items made so in the game, or null and why (nothing of the game's changed then). `firstRow` was
        /// planned with: a bonus row past every one an item of the game's (or another mod's) names.</summary>
        public static ItemHooks? Arm(IReloadedHooks reloaded, byte* start, int imageSize, ItemRoom.Found found,
                                     List<ItemRoom.Given> given, int worldBank, int sheetInit, Action<string> say,
                                     out string why, int stock = -1, List<ItemRoom.Given>? wotl = null)
        {
            var image = new ReadOnlySpan<byte>(start, imageSize);
            ulong imageBase = (ulong)start;
            if (wotl != null && wotl.Count > 0 && found.Moved)
            {
                why = "War of the Lions' items can't be given where another mod has made the items' room";
                return null;
            }
            var hooks = new ItemHooks(start, found, given, worldBank, say, wotl);
            // The items' data (anywhere: the native code reaches it by its address) and the native code.
            nint data = (nint)NativeMemory.AllocZeroed((nuint)ItemRoom.DataBytes);
            var made = ItemRoom.Data(given, (ulong)data);
            Marshal.Copy(made, 0, data, made.Length);
            var code = ItemRoom.Code((ulong)data, out int[] starts);
            nint codeAt = Thunks.Executable(code);
            if (codeAt == 0)
            {
                why = "Windows gave no memory for the items' native code";
                return null;
            }
            // (2.0.0) War of the Lions' items: a block of their own, laid out as the mods' own items', and their native
            // code, each function's way on the mods' own items' code (whose way on is the game's).
            nint wotlCode = 0;
            int[] wotlStarts = starts;
            if (hooks._wotl.Count > 0)
            {
                nint wotlData = (nint)NativeMemory.AllocZeroed((nuint)ItemRoom.DataBytes);
                var wotlMade = ItemRoom.Data(hooks._wotl, (ulong)wotlData, WotLItems.First);
                Marshal.Copy(wotlMade, 0, wotlData, wotlMade.Length);
                var theirCode = ItemRoom.Code((ulong)wotlData, out wotlStarts, WotLItems.First, WotLItems.Count);
                wotlCode = Thunks.Executable(theirCode);
                if (wotlCode == 0)
                {
                    why = "Windows gave no memory for War of the Lions' items' native code";
                    return null;
                }
                for (int g = 0; g < ItemRoom.Getters.Length; g++)
                    *(long*)(wotlData + ItemRoom.SlotsAt + 8 * g) = (long)(codeAt + starts[g]);
                hooks._kept.Add(theirCode);
            }
            // No other mod's page: the page, within 2 GB of the program, and the item test's way for its two calls.
            nint page = 0, lowTest = 0;
            if (!found.Moved)
            {
                page = Near(imageBase, imageSize, ItemRoom.PageBytes);
                lowTest = Near(imageBase, imageSize, 0x1000);
                if (page == 0 || lowTest == 0)
                {
                    why = "Windows gave no memory within 2 GB of the game's program for the items";
                    return null;
                }
                var lists = ItemRoom.Lists(image, found, imageBase);
                if (Array.Exists(lists, l => l < 0))
                {
                    why = "the menus' item lists aren't the game's where its pointers lead";
                    return null;
                }
                var bytes = ItemRoom.Page(image, found, lists, hooks._all);
                Marshal.Copy(bytes, 0, page, bytes.Length);
            }
            var patches = ItemRoom.Patches(image, found, page == 0 ? 0 : (long)((ulong)page - imageBase),
                                           lowTest == 0 ? 0 : (long)((ulong)lowTest - imageBase), out why);
            if (patches == null)
                return null;
            foreach (var patch in patches)
                if (!image.Slice(patch.At, patch.Old.Length).SequenceEqual(patch.Old))
                {
                    why = $"{patch.What} isn't as it was found";
                    return null;
                }
            // The nine functions hooked (not yet active), each one's way on written in its slot first.
            var getters = new List<IHook<GetterFunction>>();
            for (int g = 0; g < ItemRoom.Getters.Length; g++)
            {
                // (2.0.0) War of the Lions' items' code first where the framework gives them.
                void* entry = wotlCode != 0 ? (void*)(wotlCode + wotlStarts[g]) : (void*)(codeAt + starts[g]);
                var hook = reloaded.CreateHook<GetterFunction>(entry, (long)(start + found.At[ItemRoom.Getters[g]]), -1);
                long original = (long)hook.OriginalFunctionAddress;
                if (original == 0)
                {
                    why = $"the item's {ItemRoom.Getters[g]} function's hook gave no way to the game's own";
                    return null;
                }
                *(long*)(data + ItemRoom.SlotsAt + 8 * g) = original;
                getters.Add(hook);
            }
            if (lowTest != 0)
            {
                // jmp [rip + 0]; the game's own item test's way (the hook's), so the two calls answer the game's own.
                var jump = new byte[14];
                jump[0] = 0xFF;
                jump[1] = 0x25;
                BinaryPrimitives.WriteInt64LittleEndian(jump.AsSpan(6),
                                                        *(long*)(data + ItemRoom.SlotsAt + 8 * (ItemRoom.Getters.Length - 1)));
                Marshal.Copy(jump, 0, lowTest, jump.Length);
                if (!VirtualProtect(lowTest, 0x1000, ExecuteRead, out _))
                {
                    why = "the item test's native code couldn't be made runnable";
                    return null;
                }
                FlushInstructionCache(GetCurrentProcess(), lowTest, 0x1000);
            }
            // Every change made writable first, so that either all are made or none.
            var protections = new uint[patches.Count];
            for (int n = 0; n < patches.Count; n++)
            {
                if (VirtualProtect((nint)(start + patches[n].At), (nuint)patches[n].New.Length, ExecuteReadWrite,
                                   out protections[n]))
                    continue;
                for (int m = n - 1; m >= 0; m--)
                    VirtualProtect((nint)(start + patches[m].At), (nuint)patches[m].New.Length, protections[m], out _);
                why = $"{patches[n].What} couldn't be changed";
                return null;
            }
            // The list pointers (no other mod's page): each to the page's list of its own.
            if (page != 0)
            {
                var lists = ItemRoom.Lists(image, found, imageBase);
                for (int s = 0; s < ItemRoom.Slots.Length; s++)
                {
                    int at = SlotAt(found, s);
                    if (!VirtualProtect((nint)(start + at), 8, ReadWrite, out uint old))
                    {
                        why = "the menus' lists' pointers couldn't be changed";
                        return null;
                    }
                    *(long*)(start + at) = (long)page + ItemRoom.PageCharts + ItemRoom.Slots[s].List * ItemRoom.ChartWords * 2;
                    VirtualProtect((nint)(start + at), 8, old, out _);
                }
                hooks._page = (byte*)page;
                for (int n = 0; n < lists.Length; n++)
                {
                    int words = ItemRoom.Slots[Array.FindIndex(ItemRoom.Slots, x => x.List == n)].Words;
                    nint gameList = (nint)(start + lists[n]);
                    nint pageList = page + ItemRoom.PageCharts + n * ItemRoom.ChartWords * 2;
                    hooks._lists.Add((gameList, words, pageList, Copy(gameList, words * 2),
                                      Copy(pageList, ItemRoom.ChartWords * 2)));
                }
                nint all = (nint)(start + found.Array["allitems"]);
                hooks._lists.Add((all, ItemRoom.GameAllItems, page + ItemRoom.PageAllItems,
                                  Copy(all, ItemRoom.GameAllItems * 2), Copy(page + ItemRoom.PageAllItems,
                                                                             ItemRoom.AllItemsWords * 2)));
                hooks._lastBag = Copy((nint)(start + found.Array["bag"]), ItemRoom.GameBag);
                hooks._lastPageBag = Copy(page, ItemRoom.GameBag);
                hooks._lastRows = Copy((nint)(start + found.Array["attribute"]), ItemRoom.GameRows * ItemRoom.RowBytes);
            }
            foreach (var patch in patches)
                Marshal.Copy(patch.New, 0, (nint)(start + patch.At), patch.New.Length);
            for (int m = patches.Count - 1; m >= 0; m--)
            {
                nint where = (nint)(start + patches[m].At);
                VirtualProtect(where, (nuint)patches[m].New.Length, protections[m], out _);
                FlushInstructionCache(GetCurrentProcess(), where, (nuint)patches[m].New.Length);
            }
            // Another mod's page: its bag (where its reaches lead) and the mods' items' bonus rows written into its rows.
            hooks._bag = page != 0 ? (byte*)page : (byte*)((long)start + found.Array["bag"]);
            if (page == 0)
            {
                byte* rows = (byte*)((long)start + found.Array["attribute"]);
                foreach (var g in given)
                    if (g.Item.Bonus != null)
                        Marshal.Copy(g.Item.Bonus, 0, (nint)(rows + g.Row * ItemRoom.RowBytes), ItemRoom.RowBytes);
            }
            foreach (var hook in getters)
            {
                hook.Activate();
                hooks._kept.Add(hook);
            }
            hooks._kept.Add(code);
            // The save: the items' counts written to the event variables first.
            hooks._save = reloaded.CreateHook<SaveFunction>(hooks.Save, (long)(start + found.At["Save"]), -1);
            hooks._save.Activate();
            // The icons' two paths.
            hooks._icon = reloaded.CreateHook<IconPathFunction>(hooks.IconPath, (long)(start + found.At["IconPath"]), -1);
            hooks._icon.Activate();
            hooks._smallIcon = reloaded.CreateHook<IconPathFunction>(hooks.SmallIconPath,
                                                                     (long)(start + found.At["SmallIconPath"]), -1);
            hooks._smallIcon.Activate();
            // The Item table: the items' rows (their names and words) as it loads.
            hooks._sheetInit = reloaded.CreateHook<SheetInitFunction>(hooks.SheetInit, (long)(start + sheetInit), -1);
            hooks._sheetInit.Activate();
            // (1.27.0) The game's towns' Outfitters selling the mods' items their files name: the stock hooked for them
            // (`stock`, its site, -1 when it wasn't found; said then, the items sold at the mods' towns only).
            hooks._townItems = ItemRoom.TownItems(hooks._all);
            if (hooks._townItems.Count > 0)
            {
                var calls = stock >= 0 ? Places.StockCalls(new ReadOnlySpan<byte>(start + stock, Places.StockSortAt + 5),
                                                           stock)
                                       : (0, 0, 0);
                if (calls.Item1 == 0)
                    say("the mods' items aren't sold at the game's own Outfitters: "
                        + (stock < 0 ? "the Outfitter's stock wasn't found" : "the stock's calls aren't where they were")
                        + ". A game update may have changed it: look for a newer Mod Studio Framework.");
                else
                {
                    (hooks._stockSort, hooks._stockEquips, hooks._stockUnits) = calls;
                    hooks._stock = reloaded.CreateHook<Hooks.StockFunction>(hooks.Stock, (long)(start + stock), -1);
                    hooks._stock.Activate();
                }
            }
            var thread = new Thread(hooks.SyncLoop) { IsBackground = true, Name = "Mod Studio Framework items" };
            thread.Start();
            why = "";
            return hooks;
        }

        static byte[] Copy(nint at, int length)
        {
            var bytes = new byte[length];
            Marshal.Copy(at, bytes, 0, length);
            return bytes;
        }

        /// <summary>The 14 list pointers' place (each 8 bytes on: the first five from the first pointer of the menus'
        /// own, the second five from the second's, the last four from the all-items block's).</summary>
        public static int SlotAt(ItemRoom.Found found, int slot) => ItemRoom.SlotAt(found, slot);

        /// <summary>Each of the nine lists the 14 pointers point at, by its number (ItemRoom.Slots' List), from the
        /// program's start (`imageBase`: where it is loaded, its pointers' addresses counted from there).</summary>
        public static int[] Lists(ReadOnlySpan<byte> image, ItemRoom.Found found, ulong imageBase)
            => ItemRoom.Lists(image, found, imageBase);

        // --- the save and the thread ----------------------------------------------------------------------------------

        nint Save(nint a, nint b, nint c, nint d)
        {
            try
            {
                lock (_lock)
                    Sync(true);
            }
            catch (Exception e)
            {
                SayOnce($"the mods' items' counts weren't kept in the save ({e.GetType().Name}: {e.Message}).");
            }
            return _save!.OriginalFunction(a, b, c, d);
        }

        void SyncLoop()
        {
            while (true)
            {
                Thread.Sleep(Interval);
                try
                {
                    lock (_lock)
                        Sync(false);
                }
                catch (Exception e)
                {
                    SayOnce($"the mods' items' counts weren't kept ({e.GetType().Name}: {e.Message}).");
                }
            }
        }

        void Sync(bool atSave)
        {
            nint bankAt = *(nint*)(_base + _worldBank);
            if (bankAt != 0)
            {
                var bank = new Span<byte>((void*)bankAt, Framework.BankBytes);
                var bag = new Span<byte>(_bag, ItemRoom.LastItem + 1);
                int done = _counts.Sync(bag, bank, atSave);
                if (done == 1)
                    SayOnce("the mods' items' counts are taken from the save loaded.");
                // (2.0.0) War of the Lions' items' counts, where the framework gives them: kept where WotL Restoration
                // keeps its own.
                if (_wotl.Count > 0 && _wotlCounts.Sync(bag, bank, atSave) == 1)
                    SayOnce("War of the Lions' items' counts are taken from the save loaded.");
                // (1.35.0) A save holding the mods' items (in its bag or worn) marked with the numbers as it is made.
                if (atSave && MarkWith != 0 && Framework.ReadMark(bank) == 0)
                {
                    var roster = Roster >= 0
                        ? new ReadOnlySpan<byte>(_base + Roster, Framework.RosterBytes) : ReadOnlySpan<byte>.Empty;
                    if (Framework.AnyItem(bank, roster))
                        Framework.WriteMark(bank, MarkWith);
                }
            }
            if (_page == null)
                return;
            // The game's own bag, lists and bonus rows and the page's alike: whichever changed since last is taken.
            var gameBag = new Span<byte>(_base + _found.Array["bag"], ItemRoom.GameBag);
            var pageBag = new Span<byte>(_page + ItemRoom.PageBag, ItemRoom.GameBag);
            if (!gameBag.SequenceEqual(_lastBag))
                gameBag.CopyTo(pageBag);
            else if (!pageBag.SequenceEqual(_lastPageBag))
                pageBag.CopyTo(gameBag);
            gameBag.CopyTo(_lastBag);
            pageBag.CopyTo(_lastPageBag);
            for (int n = 0; n < _lists.Count; n++)
            {
                var (game, words, pageList, lastGame, lastPage) = _lists[n];
                var g = new Span<byte>((void*)game, words * 2);
                var p = new Span<byte>((void*)pageList, lastPage.Length);
                if (!g.SequenceEqual(lastGame))
                    ItemRoom.Adopt(g, p);
                else if (!p.SequenceEqual(lastPage))
                    ItemRoom.GiveBack(p, g);
                g.CopyTo(lastGame);
                p.CopyTo(lastPage);
            }
            var rows = new Span<byte>(_base + _found.Array["attribute"], ItemRoom.GameRows * ItemRoom.RowBytes);
            if (!rows.SequenceEqual(_lastRows))
            {
                rows.CopyTo(new Span<byte>(_page + ItemRoom.PageAttribute, rows.Length));
                rows.CopyTo(_lastRows);
            }
        }

        // --- the Item table ------------------------------------------------------------------------------------------

        int SheetInit(nint sheet, nint file)
        {
            try
            {
                Give(sheet, file);
            }
            catch (Exception e)
            {
                SayOnce($"the mods' items got no names ({e.GetType().Name}: {e.Message}); the game's Item table is used.");
            }
            return _sheetInit!.OriginalFunction(sheet, file);
        }

        void Give(nint sheet, nint file)
        {
            if (sheet == 0 || file == 0 || *(int*)(sheet + Hooks.SheetNumber) != ItemRoom.ItemSheet)
                return;
            if (*(nint*)(sheet + Hooks.SheetFile) != file)
            {
                SayOnce("Item gets no rows: the table isn't laid out as in the game this was made for.");
                return;
            }
            nint bytes = *(nint*)(file + Hooks.FileBytes);
            long size = *(long*)(file + Hooks.FileSize);
            lock (_copies)
                if (_copies.Contains(bytes))
                    return;
            if (bytes == 0 || size <= 0 || size > Hooks.MostTable)
            {
                SayOnce($"Item gets no rows: its file is {size} bytes.");
                return;
            }
            var said = new List<string>();
            var table = ItemRoom.WithItemRows(new ReadOnlySpan<byte>((void*)bytes, (int)size), _all, said, out string why);
            foreach (var line in said)
                SayOnce(line);
            if (table == null)
            {
                SayOnce($"Item gets no rows: {why}.");
                return;
            }
            nint copy = (nint)NativeMemory.Alloc((nuint)table.Length);
            Marshal.Copy(table, 0, copy, table.Length);
            lock (_copies)
                _copies.Add(copy);
            *(long*)(file + Hooks.FileSize) = table.Length;
            *(nint*)(file + Hooks.FileBytes) = copy;
            int added = _given.Count;
            if (added > 0)
                _say($"Item: the mods' items' {added} row{(added == 1 ? "" : "s")} added.");
            if (_wotl.Count > 0)
                _say($"Item: War of the Lions' items' {_wotl.Count} rows added.");
        }

        /// <summary>The first equipment bonus row past every one an item names (the game's, and another mod's: each
        /// valid item's record's + 7, asked of the game's own functions, another mod's hooks answering its own), at
        /// least past the game's 85.</summary>
        public static int FirstFreeRow(byte* start, ItemRoom.Found found)
        {
            var valid = (delegate* unmanaged<ushort, int>)(start + found.At["IsValidItem"]);
            var common = (delegate* unmanaged<ushort, byte*>)(start + found.At["ItemCommon"]);
            int most = ItemRoom.GameRows - 1;
            for (int id = 1; id < ItemRoom.FirstItem; id++)
            {
                if ((valid((ushort)id) & 0xFF) == 0)
                    continue;
                byte* record = common((ushort)id);
                if (record != null)
                    most = Math.Max(most, record[ItemFile.BonusAt]);
            }
            return most + 1;
        }

        // --- the icons ---------------------------------------------------------------------------------------------

        int IconPath(nint buffer, int number, int size) => Icon(buffer, number, size, false);

        int SmallIconPath(nint buffer, int number, int size) => Icon(buffer, number, size, true);

        int Icon(nint buffer, int number, int size, bool small)
        {
            var original = small ? _smallIcon! : _icon!;
            if (!_byNumber.TryGetValue(number, out var g))
                return original.OriginalFunction(buffer, number, size);
            try
            {
                if (g.Item.Icon > 0)
                    return original.OriginalFunction(buffer, g.Item.Icon, size);
                string path = ItemIconPath(g.Item.IconPicture, small);
                var bytes = Encoding.UTF8.GetBytes(path);
                if (bytes.Length + 1 > size)
                    return original.OriginalFunction(buffer, 0, size);
                Marshal.Copy(bytes, 0, buffer, bytes.Length);
                *((byte*)buffer + bytes.Length) = 0;
                return bytes.Length;
            }
            catch (Exception e)
            {
                SayOnce($"a mod's item's icon wasn't given its path ({e.GetType().Name}: {e.Message}).");
                return original.OriginalFunction(buffer, number, size);
            }
        }

        /// <summary>An item's own icon's path, as the Icon table's two give the game's (under the UI's texture parts of
        /// ui/ffto/icon/, as a town's own art's path is made, PlaceHooks.BaseArt).</summary>
        public static string ItemIconPath(string picture, bool small)
            => small ? $"UITextureParts://ui/ffto/icon/equip_item_s/textureparts/{picture}_s"
                     : $"UITextureParts://ui/ffto/icon/equip_item/textureparts/{picture}";

        // --- the Outfitter ------------------------------------------------------------------------------------------

        /// <summary>A mod's town's Outfitter: after the game's own list (`listed` words written at `list`, its end
        /// after them), the town's own items of the tab asked for, each once the story reaches the point the shops sell
        /// it from (variable 0x6F, as the game's own), checked against the unit as the game's loop checks its own when
        /// asked (`mode` 1: listed, marked 0x4000 when the unit can't use it; 2: listed only when it can), up to 255 in
        /// all; the end written after them. How many were added. The caller sorts the whole list after, if asked.</summary>
        public int Append(IReadOnlyList<int> items, short category, nint list, int listed, int storyPoint,
                          Func<int, int>? equips, int mode)
        {
            var entries = ItemRoom.Appended(items, n => _byNumber.TryGetValue(n, out var g) ? g : null, category,
                                            listed, storyPoint, equips, mode);
            ushort* words = (ushort*)list;
            for (int n = 0; n < entries.Count; n++)
                words[listed + n] = (ushort)entries[n];
            words[listed + entries.Count] = 0xFFFF;
            return entries.Count;
        }

        // --- (1.27.0) the game's own towns' Outfitters -----------------------------------------------------------------

        /// <summary>The game's towns that sell a mod's item (ItemRoom.TownItems), the stock's hook for them and what it
        /// calls (Hooks.StockCalls: the list's sort, the check of an item against the unit, the units' table).</summary>
        Dictionary<int, List<int>> _townItems = new Dictionary<int, List<int>>();
        IHook<Hooks.StockFunction>? _stock;
        int _stockSort, _stockEquips, _stockUnits;

        /// <summary>Whether the game's towns' Outfitters sell the mods' items (the stock hooked for them).</summary>
        public bool SellsAtGameTowns => _stock != null;

        /// <summary>A game town's Outfitter: the game's own list made unsorted, the mods' items it sells added (as a
        /// mod's town's are, Append), then sorted as asked. A mod's town's call through the borrowed town's bit
        /// (Hooks.Borrowing) and any other town go on to the game's own.</summary>
        int Stock(short unit, short town, short category, nint list, int mode, byte sort)
        {
            if (Hooks.Borrowing || !_townItems.TryGetValue(town, out var items))
                return _stock!.OriginalFunction(unit, town, category, list, mode, sort);
            int listed = _stock!.OriginalFunction(unit, town, category, list, mode, 0);
            try
            {
                listed += Append(items, category, list, listed, StoryPoint(),
                                 mode == 0 ? null : id => Equips(unit, id), mode);
            }
            catch (Exception e)
            {
                SayOnce($"a game town's Outfitter didn't add the mods' items ({e.GetType().Name}: {e.Message}).");
            }
            if (sort != 0)
                ((delegate* unmanaged<int, nint, void>)(_base + _stockSort))(Hooks.StockSortKind, list);
            return listed;
        }

        /// <summary>The story's point the shops sell from (variable 0x6F of the world map's variables, as
        /// Hooks.StoryPoint reads it).</summary>
        int StoryPoint()
        {
            nint bank = *(nint*)(_base + _worldBank);
            return bank == 0 ? 0 : BinaryPrimitives.ReadInt32LittleEndian(
                new ReadOnlySpan<byte>((void*)(bank + Hooks.StoryPointVariable * 4), 4));
        }

        /// <summary>The stock's check of an item against the unit (-1: it can't), as Hooks.Equips asks it.</summary>
        int Equips(short unit, int item)
        {
            nint u = *(nint*)(_base + _stockUnits + 8 * unit);
            if (u == 0)
                return -1;
            return ((delegate* unmanaged<ushort, ushort, nint, int>)(_base + _stockEquips))((ushort)item,
                                                                                         *(ushort*)(u + 0x24), u + 0x73);
        }
    }
}
