// Mod Studio Framework: (1.10.0) the quest maps' rows as each table loads
// (MapHooks.cs gives them to the game): the six tables keyed by a map get each
// quest map's rows at its number (MapRows.cs), PlaceName each quest map's
// Title. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
using System;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    /// <summary>The quest maps' rows, for each table as it loads: works on bytes, so the checks run it over the game's
    /// tables.</summary>
    public sealed class MapTables
    {
        readonly List<MapRoom.Given> _maps;

        public MapTables(List<MapRoom.Given> maps)
        {
            _maps = new List<MapRoom.Given>(maps);
        }

        public static string NameOf(int sheet)
            => sheet == Destinations.NameSheet ? "PlaceName" : MapRows.TableOf(sheet)?.Name ?? $"table {sheet}";

        /// <summary>Whether a table gets rows: the six with a quest map's rows, PlaceName with a Title.</summary>
        public bool Adds(int sheet)
        {
            if (sheet == Destinations.NameSheet)
                return _maps.Exists(g => g.Map.Title.Length > 0);
            var table = MapRows.TableOf(sheet);
            return table != null && _maps.Exists(g => g.Map.Rows.TryGetValue(table.Name, out var rows) && rows.Count > 0);
        }

        /// <summary>A quest map's Map row as it goes in: with a Title, its name (Unknown8) the Title's key in PlaceName,
        /// its place and part (UnknownC, Unknown10) none.</summary>
        static MapRow MapRowOf(MapRoom.Given g, MapRow row)
        {
            if (g.Map.Title.Length == 0)
                return row;
            var values = new Dictionary<string, object?>(row.Values, StringComparer.Ordinal)
            {
                ["Unknown8"] = (long)MapRoom.TitleKey(g.Number), ["UnknownC"] = 0L, ["Unknown10"] = 0L,
            };
            return new MapRow(row.Keys, values);
        }

        /// <summary>The rows a table gets.</summary>
        public List<NewRow> RowsFor(int sheet)
        {
            var rows = new List<NewRow>();
            if (sheet == Destinations.NameSheet)
            {
                foreach (var g in _maps)
                    if (g.Map.Title.Length > 0)
                        rows.Add(new NewRow(new[] { MapRoom.TitleKey(g.Number) }, Destinations.NameRowOf(g.Map.Title)));
                return rows;
            }
            var table = MapRows.TableOf(sheet);
            if (table == null)
                return rows;
            foreach (var g in _maps)
            {
                if (!g.Map.Rows.TryGetValue(table.Name, out var list))
                    continue;
                foreach (var row in list)
                {
                    var r = table.Name == "Map" ? MapRowOf(g, row) : row;
                    var keys = new int[1 + r.Keys.Length];
                    keys[0] = g.Number;
                    r.Keys.CopyTo(keys, 1);
                    rows.Add(new NewRow(keys, MapRows.Bytes(table, r)));
                }
            }
            return rows;
        }

        /// <summary>The loaded table with the quest maps' rows, or null and why: a table of as many keys as its rows
        /// have; a row whose keys it has already (another mod's) left out, said in `said`.</summary>
        public byte[]? WithRows(int sheet, ReadOnlySpan<byte> table, List<string> said, out string why, out int added)
        {
            added = 0;
            var rows = RowsFor(sheet);
            if (rows.Count == 0)
            {
                why = "it gets no rows";
                return null;
            }
            int keys = Nxd.Keys(table);
            if (keys != rows[0].Keys.Length)
            {
                why = $"it isn't a table of {rows[0].Keys.Length} key{(rows[0].Keys.Length == 1 ? "" : "s")} (byte 8: "
                      + $"{(table.Length > 8 ? table[8] : 0)})";
                return null;
            }
            var kept = new List<NewRow>();
            foreach (var row in rows)
            {
                if (Nxd.Find(table, row.Keys) >= 0)
                    said.Add($"{NameOf(sheet)}'s row {string.Join(", ", row.Keys)} of a quest map is left out: the table "
                             + "has one there already.");
                else
                    kept.Add(row);
            }
            if (kept.Count == 0)
            {
                why = "every row of the quest maps' is there already";
                return null;
            }
            var output = Nxd.WithRows(table, kept, out why);
            if (output != null)
                added = kept.Count;
            return output;
        }
    }
}
