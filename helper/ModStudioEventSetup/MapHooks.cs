// Mod Studio Framework: (1.10.0) the quest maps joined to the running game,
// through Reloaded-II's shared hooks. Part of The Ivalice Chronicles Mod
// Studio, GPL-3.0.
//
// Made only when some mod gives a quest map (MapFile.cs) and its memory is
// made (MapRoom.cs), apart from the side quests' hooks (Hooks.cs) and the
// places' (PlaceHooks.cs): three hooks.
// - The tables' setup (Places.SheetInit): the six tables a map is keyed by
//   get the quest maps' rows (MapRows.cs), each at its map's number, and
//   PlaceName each quest map's Title (MapTables), in a copy of the file they
//   loaded, before the game reads them.
// - The map's GNS's loader (MapRoom.Sites.GnsLoad), hooked to native code
//   that copies the game's 128 entries of the five tables into the helper's
//   copies, then runs the game's loader.
// - The PlayStation's file reader (MapRoom.Sites.FileRead), hooked to native
//   code that hands over a quest map's own files (from MapRoom.FakeFile) and
//   leaves every other read to the game's.
// Nothing here throws into the game: a fault is said once.
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using Reloaded.Hooks.Definitions;
using Reloaded.Hooks.Definitions.X64;
using IReloadedHooks = Reloaded.Hooks.ReloadedII.Interfaces.IReloadedHooks;

namespace ModStudioEventSetup
{
    public sealed unsafe class MapHooks
    {
        [Function(CallingConventions.Microsoft)]
        public delegate int SheetInitFunction(nint sheet, nint file);

        /// <summary>The map's GNS's loader (the map as 16 bits): the GNS's bytes, or 0.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate nint GnsLoadFunction(ushort map);

        /// <summary>The PlayStation's file reader (the file, a sector, a size, the buffer): 0 once read.</summary>
        [Function(CallingConventions.Microsoft)]
        public delegate int FileReadFunction(int file, int sector, int size, nint buffer);

        const int SheetNumber = 8, SheetFile = 0x30, FileBytes = 0x38, FileSize = 0x40;
        const long MostTable = 64L << 20;

        readonly MapTables _tables;
        readonly Action<string> _say;
        readonly object _lock = new object();
        readonly HashSet<string> _saidOnce = new HashSet<string>();
        readonly HashSet<nint> _copies = new HashSet<nint>();
        IHook<SheetInitFunction>? _sheetInit;
        IHook<GnsLoadFunction>? _gnsLoad;
        IHook<FileReadFunction>? _fileRead;

        MapHooks(MapTables tables, Action<string> say)
        {
            _tables = tables;
            _say = say;
        }

        /// <summary>The three hooks made, not yet active, the native ones' ways to the game's functions written into the
        /// block's data; null and why not.</summary>
        public static MapHooks? Make(IReloadedHooks reloaded, byte* start, Places places, MapRoom.Sites s,
                                     MapRoom.Block block, List<MapRoom.Given> maps, Action<string> say, out string why)
        {
            var hooks = new MapHooks(new MapTables(maps), say);
            long loaded = (long)(nint)start;
            hooks._sheetInit = reloaded.CreateHook<SheetInitFunction>(hooks.SheetInit, loaded + places.SheetInit, -1);
            hooks._gnsLoad = reloaded.CreateHook<GnsLoadFunction>((void*)(block.CodeAt + (ulong)block.Refresh),
                                                                  loaded + s.GnsLoad, -1);
            hooks._fileRead = reloaded.CreateHook<FileReadFunction>((void*)(block.CodeAt + (ulong)block.Reader),
                                                                    loaded + s.FileRead, -1);
            long gns = (long)hooks._gnsLoad.OriginalFunctionAddress, read = (long)hooks._fileRead.OriginalFunctionAddress;
            if (gns == 0 || read == 0)
            {
                why = "the hooks gave no way to the game's own map loader or file reader";
                return null;
            }
            *(long*)(block.DataAt + MapRoom.RefreshSlot) = gns;
            *(long*)(block.DataAt + MapRoom.ReaderSlot) = read;
            why = "";
            return hooks;
        }

        /// <summary>Once the program is changed (MapRoom.Join): the hooks active.</summary>
        public void Activate()
        {
            _sheetInit?.Activate();
            _gnsLoad?.Activate();
            _fileRead?.Activate();
        }

        void SayOnce(string line)
        {
            lock (_lock)
                if (!_saidOnce.Add(line))
                    return;
            _say(line);
        }

        int SheetInit(nint sheet, nint file)
        {
            try
            {
                Give(sheet, file);
            }
            catch (Exception e)
            {
                SayOnce($"a table's quest map rows weren't added ({e.GetType().Name}: {e.Message}); the game's table is "
                        + "used.");
            }
            return _sheetInit!.OriginalFunction(sheet, file);
        }

        void Give(nint sheet, nint file)
        {
            if (sheet == 0 || file == 0)
                return;
            int number = *(int*)(sheet + SheetNumber);
            if (!_tables.Adds(number))
                return;
            string name = MapTables.NameOf(number);
            if (*(nint*)(sheet + SheetFile) != file)
            {
                SayOnce($"{name} gets no quest map rows: the table isn't laid out as in the game this was made for.");
                return;
            }
            nint bytes = *(nint*)(file + FileBytes);
            long size = *(long*)(file + FileSize);
            lock (_lock)
                if (_copies.Contains(bytes))
                    return;
            if (bytes == 0 || size <= 0 || size > MostTable)
            {
                SayOnce($"{name} gets no quest map rows: its file is {size} bytes.");
                return;
            }
            var said = new List<string>();
            var table = _tables.WithRows(number, new ReadOnlySpan<byte>((void*)bytes, (int)size), said, out string why,
                                         out int added);
            foreach (var line in said)
                SayOnce(line);
            if (table == null)
            {
                SayOnce($"{name} gets no quest map rows: {why}.");
                return;
            }
            nint copy = (nint)NativeMemory.Alloc((nuint)table.Length);
            Marshal.Copy(table, 0, copy, table.Length);
            lock (_lock)
                _copies.Add(copy);
            *(long*)(file + FileSize) = table.Length;
            *(nint*)(file + FileBytes) = copy;
            _say($"{name}: the quest maps' {added} row{(added == 1 ? "" : "s")} added.");
        }
    }
}
