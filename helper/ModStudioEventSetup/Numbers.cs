// Mod Studio Framework: the framework's file of names and the numbers it
// gave them. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi's rule (26 October): a modder never chooses a number. The framework
// gives each name a side quest adds (an event, a flag, a row's key) one of
// the game's numbers as the game starts, and keeps what it gave in a file of
// its own, so a name gets the same number every time (a save made in the
// middle of a quest finds its events again) and a number given once never
// goes to another name, even after its quest is taken away (a save still
// holding that quest's flags never hands them to another).
//
// (1.32.0) Zodi's test 67 (4 November): its battle never came, both saves he
// loaded holding its Battle done already, set long before by quests numbered
// before his numbers were freed. His choice: a save's side quest flags it
// can't really hold cleared as it loads, said. So the numbers keep the marks
// they have had (Marks: each its ID, the flags given with it, the flags freed
// with it): a new mark each time a game start gives flags no name had, or a
// free drops some, so a save marked before them has those flags cleared as
// it loads (Framework.Loaded).
//
// (1.35.0) Zodi's word of 5 November, on the next session's recommendation
// ("a save made before you freed numbers could hand out a new item for
// free, the same kind of problem test 67's flags were"): the marks keep the
// mods' items' numbers given and freed with them too (Items, FreedItems), so
// a save marked before has those items taken out as it loads, its bag's
// count cleared and any unit wearing one given none (his choice "Count and
// worn copies"). A free made before 1.35.0 wrote down no items: a save older
// than it keeps them (his choice "Keep their items").
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Json;

namespace ModStudioEventSetup
{
    public sealed class Numbers
    {
        public const string FileName = "Numbers.json";
        /// <summary>The kinds of numbers given, each kept apart (1.2.0: a quest's battles and their
        /// deploy prompts' keys; 1.7.0: a mod's places the game goes to, Destinations.cs; 1.10.0: the quest maps,
        /// MapRoom.cs; 1.12.0: the battles' objectives, Framework.cs; 1.14.0: the battles' own deploy areas'
        /// squads, DeploySquads.cs; 1.15.0: the quests' tavern rumors' keys, Framework.cs; 1.26.0: the mods' own items,
        /// ItemRoom.cs).</summary>
        public static readonly string[] Kinds = { "Events", "Flags", "Rules", "Scenes", "Texts", "Battles", "Prompts",
                                                   "Places", "Maps", "Objectives", "Squads", "Rumors", "Items" };
        /// <summary>(1.29.0, Zodi's sixth of 3 November) The kinds no save keeps a number of, numbered afresh as each
        /// game starts (`GiveNow`): a quest map's (a save keeps no map; a battle's map is its setup record's, written
        /// as the game starts) and a rumor's (a save keeps only its two bytes, which the helper settles from its flag,
        /// Framework.SettleRumors). Only the names present at a start hold one, so their room is what is enabled at
        /// once, never what ever was.</summary>
        public static readonly string[] EachStart = { "Maps", "Rumors" };
        readonly Dictionary<string, HashSet<string>> _present = new Dictionary<string, HashSet<string>>();
        readonly Dictionary<string, HashSet<string>> _givenNow = new Dictionary<string, HashSet<string>>();

        readonly Dictionary<string, Dictionary<string, int>> _given = new Dictionary<string, Dictionary<string, int>>();
        readonly Dictionary<string, HashSet<int>> _used = new Dictionary<string, HashSet<int>>();
        /// <summary>(1.7.1) Each mod's place's home: the game's place a save standing on it goes on from when no mod
        /// gives it any more (SaveFallback.cs), kept under "Homes" by the place's number.</summary>
        readonly SortedDictionary<int, int> _homes = new SortedDictionary<int, int>();
        public const string HomesKind = "Homes";
        public bool Changed { get; private set; }
        /// <summary>(1.13.0) The numbers' own ID, made once (a whole number from 1 up, kept as "Id"): each save
        /// carries it (Framework.MarkAt) as a quest flag is set, so a save loaded with other numbers is said. (1.32.0)
        /// Made again with each new mark (Stamp, Free).</summary>
        public uint Id { get; private set; }
        public const string IdField = "Id";

        /// <summary>(1.32.0) One mark the numbers have had: its ID (a save's mark while it was the numbers' own), the
        /// flags' bits given with it (the new ones of the game start that made it) and freed with it (a free's);
        /// (1.35.0) the mods' items' numbers given with it (no name having had them) and freed with it.</summary>
        public sealed class Mark
        {
            public uint Id { get; }
            public List<int> Flags { get; }
            public List<int> Freed { get; }
            public List<int> Items { get; }
            public List<int> FreedItems { get; }

            public Mark(uint id, IEnumerable<int>? flags = null, IEnumerable<int>? freed = null,
                        IEnumerable<int>? items = null, IEnumerable<int>? freedItems = null)
            {
                Id = id;
                Flags = flags == null ? new List<int>() : new List<int>(flags);
                Freed = freed == null ? new List<int>() : new List<int>(freed);
                Items = items == null ? new List<int>() : new List<int>(items);
                FreedItems = freedItems == null ? new List<int>() : new List<int>(freedItems);
            }
        }

        /// <summary>(1.35.0) A mark's lists of the mods' items' numbers as its file names them.</summary>
        public const string ItemsField = "Items", FreedItemsField = "FreedItems";

        /// <summary>(1.32.0) The marks kept ("Marks"), oldest first, the last the numbers' own ID; none before the
        /// numbers had a second.</summary>
        readonly List<Mark> _marks = new List<Mark>();
        public const string MarksField = "Marks";
        /// <summary>(1.32.0) The flags' bits given since the numbers were read, no name having had them: the next
        /// mark's (Stamp).</summary>
        readonly SortedSet<int> _flagsNow = new SortedSet<int>();
        /// <summary>(1.35.0) The mods' items' numbers given since the numbers were read, no name having had them: the
        /// next mark's (Stamp).</summary>
        readonly SortedSet<int> _itemsNow = new SortedSet<int>();

        /// <summary>(1.32.0) The marks the numbers have had, oldest first, the last their own ID (only it, before a
        /// second was made; none without an ID).</summary>
        public IReadOnlyList<Mark> Marks
            => _marks.Count > 0 ? _marks : Id != 0 ? new List<Mark> { new Mark(Id) } : new List<Mark>();

        /// <summary>(1.32.0) Where a save's mark is among the marks the numbers have had (0 the oldest), -1 for none of
        /// them (0, no mark, is none of them).</summary>
        public int MarkIndex(uint id)
        {
            var marks = Marks;
            for (int n = 0; id != 0 && n < marks.Count; n++)
                if (marks[n].Id == id)
                    return n;
            return -1;
        }

        /// <summary>(1.32.0) A new mark, when flags no name had were given since the numbers were read (Give): its ID
        /// new (the numbers' own from now on), those flags its own, so a save marked before has them cleared as it
        /// loads. (1.35.0) The same for the mods' items' numbers no name had: a save marked before has those items
        /// taken out as it loads. Whether one was made.</summary>
        public bool Stamp()
        {
            if (_flagsNow.Count == 0 && _itemsNow.Count == 0)
                return false;
            NewMark(_flagsNow, null, _itemsNow, null);
            _flagsNow.Clear();
            _itemsNow.Clear();
            return true;
        }

        /// <summary>(1.32.0) The numbers given a mark of their own: the ID they had kept as a mark first, then a new
        /// ID, never one of the marks', with the flags given and freed; (1.35.0) and the mods' items' numbers.</summary>
        void NewMark(IEnumerable<int>? flags, IEnumerable<int>? freed, IEnumerable<int>? items = null,
                     IEnumerable<int>? freedItems = null)
        {
            if (_marks.Count == 0 && Id != 0)
                _marks.Add(new Mark(Id));
            uint id;
            do
                id = NewId();
            while (id == Id || MarkIndex(id) >= 0);
            _marks.Add(new Mark(id, flags, freed, items, freedItems));
            Id = id;
            Changed = true;
        }

        /// <summary>(1.32.0) Whether these numbers' marks go on from another's: the other's marks, oldest first, are
        /// the first of these, and these have more (a copy written since the other was).</summary>
        bool GoesOnFrom(Numbers other)
        {
            var mine = Marks;
            var theirs = other.Marks;
            if (theirs.Count == 0 || mine.Count <= theirs.Count)
                return false;
            for (int n = 0; n < theirs.Count; n++)
                if (mine[n].Id != theirs[n].Id)
                    return false;
            return true;
        }

        public Numbers()
        {
            foreach (var kind in Kinds)
            {
                _given[kind] = new Dictionary<string, int>(StringComparer.Ordinal);
                _used[kind] = new HashSet<int>();
            }
            foreach (var kind in EachStart)
            {
                _present[kind] = new HashSet<string>(StringComparer.Ordinal);
                _givenNow[kind] = new HashSet<string>(StringComparer.Ordinal);
            }
        }

        /// <summary>The numbers in a file's text; a file that can't be read gives none, and why in problems.</summary>
        public static Numbers FromText(string? text, List<string> problems)
        {
            var numbers = new Numbers();
            if (string.IsNullOrWhiteSpace(text))
                return numbers;
            try
            {
                using var document = JsonDocument.Parse(text);
                foreach (var kind in Kinds)
                {
                    if (!document.RootElement.TryGetProperty(kind, out var list) || list.ValueKind != JsonValueKind.Object)
                        continue;
                    foreach (var p in list.EnumerateObject())
                        if (p.Value.ValueKind == JsonValueKind.Number && p.Value.TryGetInt32(out int n))
                        {
                            numbers._given[kind][p.Name] = n;
                            numbers._used[kind].Add(n);
                        }
                }
                if (document.RootElement.TryGetProperty(HomesKind, out var homes) && homes.ValueKind == JsonValueKind.Object)
                    foreach (var p in homes.EnumerateObject())
                        if (int.TryParse(p.Name, out int place) && p.Value.ValueKind == JsonValueKind.Number
                            && p.Value.TryGetInt32(out int home))
                            numbers._homes[place] = home;
                if (document.RootElement.TryGetProperty(IdField, out var id) && id.ValueKind == JsonValueKind.Number
                    && id.TryGetUInt32(out uint given))
                    numbers.Id = given;
                // (1.32.0) The marks they have had: each its ID (from 1 up, once) and the flags given and freed with it;
                // (1.35.0) and the mods' items' numbers.
                if (document.RootElement.TryGetProperty(MarksField, out var marks) && marks.ValueKind == JsonValueKind.Array)
                {
                    foreach (var mark in marks.EnumerateArray())
                    {
                        if (mark.ValueKind != JsonValueKind.Object || !mark.TryGetProperty(IdField, out var markId)
                            || markId.ValueKind != JsonValueKind.Number || !markId.TryGetUInt32(out uint m) || m == 0
                            || numbers._marks.Exists(k => k.Id == m))
                            continue;
                        numbers._marks.Add(new Mark(m, Bits(mark, "Flags"), Bits(mark, "Freed"), Bits(mark, ItemsField),
                                                    Bits(mark, FreedItemsField)));
                    }
                    // Its own ID the last mark (a file that says otherwise: its ID kept as the newest).
                    if (numbers._marks.Count > 0 && numbers.Id == 0)
                        numbers.Id = numbers._marks[numbers._marks.Count - 1].Id;
                    else if (numbers._marks.Count > 0 && numbers._marks[numbers._marks.Count - 1].Id != numbers.Id)
                    {
                        numbers._marks.RemoveAll(k => k.Id == numbers.Id);
                        numbers._marks.Add(new Mark(numbers.Id));
                    }
                }
            }
            catch (JsonException e)
            {
                problems.Add($"its {FileName} isn't JSON ({e.Message}), so numbers are given afresh");
            }
            return numbers;
        }

        /// <summary>(1.32.0) A mark's list of flags' bits (Flags or Freed): its whole numbers from 0 up, each once.</summary>
        static List<int> Bits(JsonElement mark, string field)
        {
            var bits = new List<int>();
            if (mark.TryGetProperty(field, out var list) && list.ValueKind == JsonValueKind.Array)
                foreach (var bit in list.EnumerateArray())
                    if (bit.ValueKind == JsonValueKind.Number && bit.TryGetInt32(out int n) && n >= 0 && !bits.Contains(n))
                        bits.Add(n);
            return bits;
        }

        /// <summary>(1.13.0) One place a copy of the numbers is kept: where, in words (e.g. "beside the game's saves"),
        /// and its text, null when it has none.</summary>
        public readonly struct Copy
        {
            public string Where { get; }
            public string? Text { get; }

            public Copy(string where, string? text)
            {
                Where = where;
                Text = text;
            }
        }

        /// <summary>(1.13.0) The numbers kept in several copies (Zodi's choice, 28 October: beside the game's saves, in
        /// Reloaded-II's settings folder for the helper, in the helper's own folder), the first copy there the one
        /// trusted most (the saves' own first: the saves were made with it). The numbers are the first readable
        /// copy's, with every name the others have that it hasn't, at their numbers where no name of it has them; a
        /// name two copies number apart keeps the first's, said, and the other number is never given again. Its ID
        /// the first copy's that has one, else made now. Changed (so every copy is written again) when a copy is
        /// missing or says other than the numbers do; a copy missing while another was read is said.</summary>
        public static Numbers Merge(IReadOnlyList<Copy> copies, List<string> said)
        {
            var read = new List<(string Where, Numbers Numbers)>();
            var broken = new List<string>();
            foreach (var copy in copies)
            {
                if (copy.Text == null || copy.Text.Trim().Length == 0)
                    continue;
                var problems = new List<string>();
                var numbers = FromText(copy.Text, problems);
                if (problems.Count > 0)
                {
                    broken.Add(copy.Where);
                    continue;
                }
                read.Add((copy.Where, numbers));
            }
            foreach (var where in broken)
                said.Add($"its numbers' copy {where} isn't JSON, "
                         + (read.Count > 0 ? "so the other copies are used." : "so numbers are given afresh."));
            var merged = new Numbers();
            if (read.Count > 0)
                merged.Absorb(read[0].Numbers, "", "", said);
            for (int n = 1; n < read.Count; n++)
                merged.Absorb(read[n].Numbers, read[n].Where, read[0].Where, said);
            // Its ID the first copy's that has one; (1.32.0) or a later copy's whose marks go on from it (a copy
            // written since the first was: a save marked with the newer ID is then the numbers' own), with its marks.
            Numbers? marked = null;
            foreach (var (_, numbers) in read)
                if (numbers.Id != 0 && (marked == null || numbers.GoesOnFrom(marked)))
                    marked = numbers;
            if (marked != null)
            {
                merged.Id = marked.Id;
                merged._marks.AddRange(marked._marks);
            }
            merged.Changed = false;
            if (merged.Id == 0)
            {
                merged.Id = NewId();
                merged.Changed = true;
            }
            string text = merged.Text();
            foreach (var copy in copies)
            {
                if (copy.Text != text)
                    merged.Changed = true;
                if ((copy.Text == null || copy.Text.Trim().Length == 0) && read.Count > 0)
                    said.Add($"its numbers' copy {copy.Where} was missing, so it is written from the one "
                             + $"{read[0].Where}.");
            }
            return merged;
        }

        /// <summary>(1.13.0) Another copy's names taken in (`Merge`): a name this hasn't, at its number where no name
        /// here has it; a name numbered apart keeps this one's, said, its other number never given again.</summary>
        void Absorb(Numbers other, string where, string first, List<string> said)
        {
            foreach (var kind in Kinds)
            {
                var names = new List<string>(other._given[kind].Keys);
                names.Sort(StringComparer.Ordinal);
                foreach (var name in names)
                {
                    int number = other._given[kind][name];
                    // (1.29.0) Numbered afresh as the game starts: nothing to say of copies that differ.
                    if (Array.IndexOf(EachStart, kind) >= 0)
                    {
                        if (!_given[kind].ContainsKey(name) && !_given[kind].ContainsValue(number))
                        {
                            _given[kind][name] = number;
                            _used[kind].Add(number);
                        }
                        continue;
                    }
                    if (_given[kind].TryGetValue(name, out int had))
                    {
                        if (had != number)
                        {
                            said.Add($"its numbers' copies give {name} two numbers of its {kind}: {had} {first}, "
                                     + $"{number} {where}. {had} is kept.");
                            _used[kind].Add(number);
                        }
                        continue;
                    }
                    if (_used[kind].Contains(number))
                    {
                        said.Add($"its numbers' copy {where} gives {name} the {kind} number {number}, which another "
                                 + $"name has {first}: {name} is given another.");
                        continue;
                    }
                    _given[kind][name] = number;
                    _used[kind].Add(number);
                }
                foreach (int used in other._used[kind])
                    _used[kind].Add(used);
            }
            foreach (var (place, home) in other._homes)
                if (!_homes.ContainsKey(place))
                    _homes[place] = home;
        }

        /// <summary>(1.13.0) A new ID for numbers made afresh: from 1 up, never 0 (a save without a mark). Random's
        /// own, which asks for nothing past what the helper already does.</summary>
        static uint NewId() => (uint)Random.Shared.Next(1, int.MaxValue);

        /// <summary>The file's text: each kind, its names in order with their numbers.</summary>
        public string Text()
        {
            var sb = new StringBuilder();
            sb.Append("{\n  \"Version\": 1");
            if (Id != 0)
                sb.Append(",\n  \"").Append(IdField).Append("\": ").Append(Id);
            // (1.32.0) The marks, oldest first, once there is more than the first.
            if (_marks.Count > 0)
            {
                sb.Append(",\n  \"").Append(MarksField).Append("\": [");
                for (int n = 0; n < _marks.Count; n++)
                {
                    var mark = _marks[n];
                    sb.Append(n == 0 ? "\n    {\"" : ",\n    {\"").Append(IdField).Append("\": ").Append(mark.Id);
                    if (mark.Flags.Count > 0)
                        sb.Append(", \"Flags\": [").Append(string.Join(", ", mark.Flags)).Append(']');
                    if (mark.Freed.Count > 0)
                        sb.Append(", \"Freed\": [").Append(string.Join(", ", mark.Freed)).Append(']');
                    // (1.35.0) The mods' items' numbers given and freed with it.
                    if (mark.Items.Count > 0)
                        sb.Append(", \"").Append(ItemsField).Append("\": [").Append(string.Join(", ", mark.Items))
                          .Append(']');
                    if (mark.FreedItems.Count > 0)
                        sb.Append(", \"").Append(FreedItemsField).Append("\": [")
                          .Append(string.Join(", ", mark.FreedItems)).Append(']');
                    sb.Append('}');
                }
                sb.Append("\n  ]");
            }
            foreach (var kind in Kinds)
            {
                sb.Append(",\n  \"").Append(kind).Append("\": {");
                var names = new List<string>(_given[kind].Keys);
                names.Sort(StringComparer.Ordinal);
                for (int n = 0; n < names.Count; n++)
                {
                    sb.Append(n == 0 ? "\n    " : ",\n    ");
                    sb.Append(JsonSerializer.Serialize(names[n])).Append(": ").Append(_given[kind][names[n]]);
                }
                sb.Append(names.Count == 0 ? "}" : "\n  }");
            }
            sb.Append(",\n  \"").Append(HomesKind).Append("\": {");
            bool first = true;
            foreach (var (place, home) in _homes)
            {
                sb.Append(first ? "\n    " : ",\n    ").Append('"').Append(place).Append("\": ").Append(home);
                first = false;
            }
            sb.Append(_homes.Count == 0 ? "}" : "\n  }");
            sb.Append("\n}\n");
            return sb.ToString();
        }

        /// <summary>(1.7.1) A mod's place's home kept (its number, the game's place), changed only when it differs.</summary>
        public void Home(int place, int home)
        {
            if (_homes.TryGetValue(place, out int had) && had == home)
                return;
            _homes[place] = home;
            Changed = true;
        }

        /// <summary>(1.7.1) A mod's place's home, -1 when none is kept.</summary>
        public int HomeOf(int place) => _homes.TryGetValue(place, out int home) ? home : -1;

        /// <summary>(1.7.1) The name a number of a kind was given to (its key), null when none was.</summary>
        public string? NameOf(string kind, int number)
        {
            foreach (var (name, n) in _given[kind])
                if (n == number)
                    return name;
            return null;
        }

        public bool Has(string kind, string name, out int number) => _given[kind].TryGetValue(name, out number);

        /// <summary>The number a name has, or the first number `free` allows that no name has had;
        /// -1 when none is left. A number the name had that `free` no longer allows (the game took
        /// it) is given up for a new one, and `moved` says so.</summary>
        public int Give(string kind, string name, IEnumerable<int> candidates, Func<int, bool> free, out bool moved)
        {
            moved = false;
            if (_given[kind].TryGetValue(name, out int had))
            {
                if (free(had))
                    return had;
                moved = true;
            }
            foreach (int n in candidates)
            {
                if (_used[kind].Contains(n) || !free(n))
                    continue;
                _given[kind][name] = n;
                _used[kind].Add(n);
                Changed = true;
                // (1.32.0) A flag no name had: the next mark's (Stamp). (1.35.0) A mod's item's number too.
                if (kind == FlagsKind)
                    _flagsNow.Add(n);
                if (kind == ItemsKind)
                    _itemsNow.Add(n);
                return n;
            }
            return -1;
        }

        /// <summary>(1.32.0) The kind a save keeps: the side quests' flags. (1.35.0) And the mods' items, in its bag's
        /// counts and what its units wear.</summary>
        public const string FlagsKind = "Flags", ItemsKind = "Items";

        /// <summary>Every number of a kind any name has had.</summary>
        public IReadOnlyCollection<int> Used(string kind) => _used[kind];

        // --- (1.29.0) numbered as each game starts, and freed ----------------------------------------------------------

        /// <summary>A kind numbered as each game starts (`EachStart`), begun again: `names` are the ones present now,
        /// each keeping the number it had (so nothing moves while the same mods are enabled), none given yet.</summary>
        public void BeginNow(string kind, IEnumerable<string> names)
        {
            _present[kind].Clear();
            _givenNow[kind].Clear();
            foreach (var name in names)
                _present[kind].Add(name);
        }

        /// <summary>A present name's number of a kind numbered as each game starts: the one it had while no other
        /// present name has it, else the first candidate no present name has (a name not present that held it drops
        /// it at `SettleNow`); -1 when none is left. `moved` when it had another.</summary>
        public int GiveNow(string kind, string name, IEnumerable<int> candidates, out bool moved)
        {
            moved = false;
            _present[kind].Add(name);
            bool HeldByAnother(int n)
            {
                foreach (var (other, number) in _given[kind])
                    if (number == n && other != name && _present[kind].Contains(other))
                        return true;
                return false;
            }
            if (_given[kind].TryGetValue(name, out int had))
            {
                if (!HeldByAnother(had))
                {
                    _givenNow[kind].Add(name);
                    return had;
                }
                moved = true;
            }
            foreach (int n in candidates)
            {
                if (HeldByAnother(n))
                    continue;
                _given[kind][name] = n;
                _used[kind].Add(n);
                _givenNow[kind].Add(name);
                Changed = true;
                return n;
            }
            return -1;
        }

        /// <summary>A kind numbered as each game starts, settled once its names are given: every name not given a
        /// number at this start dropped, its number free for the next.</summary>
        public void SettleNow(string kind)
        {
            foreach (var name in new List<string>(_given[kind].Keys))
                if (!_givenNow[kind].Contains(name))
                {
                    _given[kind].Remove(name);
                    Changed = true;
                }
            _used[kind].Clear();
            foreach (int n in _given[kind].Values)
                _used[kind].Add(n);
        }

        /// <summary>(1.29.0) What freeing said: each mod's numbers freed, kind by kind, or that none was.</summary>
        public static string FreedLine(SortedDictionary<string, SortedDictionary<string, int>> freed)
        {
            if (freed.Count == 0)
                return "frees no numbers: every mod they name is enabled. Its setting is unticked.";
            var mods = new List<string>();
            bool flags = false, items = false;
            foreach (var (mod, kinds) in freed)
            {
                var parts = new List<string>();
                foreach (var (kind, n) in kinds)
                    parts.Add($"{n} of its {kind}");
                mods.Add($"{mod} ({And(parts)})");
                flags |= kinds.ContainsKey(FlagsKind);
                items |= kinds.ContainsKey(ItemsKind);
            }
            // (1.32.0) A save made before has the freed flags cleared as it loads (Framework.Loaded); (1.35.0) and the
            // freed items taken out.
            string after = flags && items ? " A save made before has their flags cleared and their items taken out as it "
                                            + "loads."
                           : flags ? " A save made before has their flags cleared as it loads."
                           : items ? " A save made before has their items taken out as it loads."
                           : "";
            return $"freed the numbers of {(freed.Count == 1 ? "a mod" : $"{freed.Count} mods")} not enabled: "
                   + $"{And(mods)}.{after} Its setting is unticked.";
        }

        static string And(List<string> parts)
            => parts.Count < 2 ? string.Join("", parts)
               : string.Join(", ", parts.GetRange(0, parts.Count - 1)) + " and " + parts[parts.Count - 1];

        /// <summary>(1.29.0, his Reloaded-II setting) Every name whose mod (its first part, before the first /) isn't one
        /// of `enabled` dropped from every kind kept for good (not EachStart's, which free themselves), the homes of the
        /// places dropped with them, and the numbers given a new ID. Returns what was dropped, mod by mod: each kind and
        /// how many. (1.32.0) The new ID a mark, with the flags freed: a save made before has them cleared as it loads
        /// (until 1.32.0, a save made before said so as it loaded). (1.35.0) With the mods' items' numbers freed too: a
        /// save made before has those items taken out as it loads.</summary>
        public SortedDictionary<string, SortedDictionary<string, int>> Free(ISet<string> enabled)
        {
            var freed = new SortedDictionary<string, SortedDictionary<string, int>>(StringComparer.Ordinal);
            var freedFlags = new SortedSet<int>();
            var freedItems = new SortedSet<int>();
            foreach (var kind in Kinds)
            {
                // The kinds numbered as each game starts free themselves (SettleNow).
                if (Array.IndexOf(EachStart, kind) >= 0)
                    continue;
                foreach (var name in new List<string>(_given[kind].Keys))
                {
                    int slash = name.IndexOf('/');
                    string mod = slash > 0 ? name.Substring(0, slash) : name;
                    if (enabled.Contains(mod))
                        continue;
                    int number = _given[kind][name];
                    _given[kind].Remove(name);
                    if (kind == "Places")
                        _homes.Remove(number);
                    if (kind == FlagsKind)
                        freedFlags.Add(number);
                    if (kind == ItemsKind)
                        freedItems.Add(number);
                    if (!freed.TryGetValue(mod, out var kinds))
                        freed[mod] = kinds = new SortedDictionary<string, int>(StringComparer.Ordinal);
                    kinds[kind] = kinds.TryGetValue(kind, out int n) ? n + 1 : 1;
                }
                _used[kind].Clear();
                foreach (int n in _given[kind].Values)
                    _used[kind].Add(n);
            }
            if (freed.Count > 0)
                NewMark(null, freedFlags, null, freedItems);
            return freed;
        }
    }
}
