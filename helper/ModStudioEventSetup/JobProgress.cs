// Mod Studio Framework: (1.38.0) a unit's progress in more than one of the mods'
// jobs. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Zodi's choice of 9 November for a unit's progress: "what ever allows for 22
// completlely new jobs or more". A unit's record has room for one more job
// than the game's (slot 22: JP, total JP and a level; the learned row 19,
// Mime's, never used): eight bytes. So ONE of the mods' jobs is "loaded" in
// that room of every unit at a time, and the others' eight bytes are kept
// here. Every reach of a mod's job's progress starts from the job (the slot's
// function, 0x2B8F18) or its skillset (the battle's two readers), and each of
// those asks for its job to be loaded first (JobRoom.Code): then every unit's
// eight bytes are put away under the job that was loaded and the asked job's
// put in their place, in the party's records, the menu's copies and the
// battle's units together (Swap).
//
// (1.38.2, Zodi's test 82) Two sides, as the game keeps its own jobs. JP is
// earned in a battle unit alone (0x283664) and reaches the party's record only
// as the game writes the unit back (0x274EB8); a battle the game throws away
// (started again from its start, 0x2CF768; left) leaves the party's records as
// they were. So what is kept for the jobs that aren't loaded is kept twice:
// the party's side (a unit's record holds the loaded job's, `_kept` the
// others') and the battle's side (a battle unit holds the loaded job's,
// `_there` the others' once it has any of its own). A swap moves each side on
// its own; nothing of a battle reaches the party's side but by the game's own
// writing back, when the other jobs' battle side is taken over too
// (WrittenBack). 1.38.1 put what a battle unit had earned into the party's
// record at a swap, so a battle started again kept it. The menu's copy is
// ahead of the party's only inside one change (0x285744 writes it back before
// anything else asks a job).
//
// (1.38.1, Zodi's test 81) Whose a battle unit or a record is, is read from
// what it holds, never remembered:
// - The game clears the battle's units as it sets a battle up (0x304B48) and
//   copies them back whole as a battle is taken up again (0x2CE5C8, 0x2CE7A8).
//   1.38.0 remembered which battle unit was whose: at the next battle the
//   cleared unit read as nothing, was taken for the loaded job's progress and
//   put away as that, for every unit of the battle before. Now a battle unit
//   is a unit of the party's while it names its place and holds the same
//   sex, birthday and name's number (Mine); what the battle's side keeps for
//   it is dropped as it becomes another's or the game makes it anew (Built).
// - A record of a unit (0x280 bytes) is made two ways. The menu's (0x284A08)
//   names the party's place at +0x2C and +0x22. The battle's (0x360048)
//   names the battle unit there and the party's place at +0x1E, and the menu
//   shows the battle's own records (0x3C46770, copied over the menu's by
//   0x284F6C in a battle) and one more on its own (0x3C51F10, 0x39231C).
//   1.38.0 took +0x2C for the party's place always, so in a battle the cards
//   showed another unit's numbers. Now a record that reads both ways is told
//   apart by the rest of what it holds (the other jobs' JP and learned rows).
//   (1.38.2) A record gets the side its maker read: the battle unit's for a
//   record the battle made, the party's record's for one the menu made.
// - What is put away for a job on the party's side is never less than was
//   brought in (total JP never falls, nothing learned is unlearned): if it
//   reads so, what was brought in is kept and it is counted (Refused), for
//   the log.
//
// (1.38.2) The game's own states. Every state the game keeps and puts back
// holds the party's records and the save's variables together, so the
// framework's bytes of the variables (the mark) say which job those records
// hold and which file holds the others':
// - The plain state (0x2E80450): written by 0x218F78 as the game saves and
//   before every battle (0x2CEEE8), read back by 0x21B0E8 (a save loaded) and
//   by 0x2CF768 (a battle started again from its start). Saving, Load.
// - The battle's copy (0x8167A0, taken by 0x2CDBC4 at moments of the game's
//   own, and what an in battle save is written from): the variables, the
//   party's records (0x279BF4), the battle's units and its records. Put back
//   by 0x2CE5C8 (the party's records and the units) and then 0x2CE7A8 (the
//   variables, the units and the records again). The mark is written before
//   the copy is taken, with a number of the copy's own, and the battle's side
//   is noted beside it (Copied); as the copy is put back the party's side is
//   read by its mark and the battle's side is what was noted for that copy
//   (Restored). A copy of another run of the game has no battle's side noted:
//   its units keep the loaded job's as they hold it, the others' are the
//   party's.
//
// (1.38.2) What the game copies before it asks. The status of a unit is drawn
// from a record made of the unit on the stack (0x2CBCA0: 0x360700, 0x360048)
// or from the battle unit's own bytes copied there (0xFCF80), and the view's
// maker (0xFBB7C) asks the job's slot only after: a swap then is too late for
// that copy, which showed the job loaded before (his test 82: Skirmisher with
// Battlemage's numbers). So the unit's own job is loaded as its record is made
// or its bytes are copied (Made, Shown), before the game reads them.
//
// (1.38.3, Zodi's test 83) That was two of the game's three ways, and not the
// one his screen is drawn by. The status card (the job's name with "Lv.",
// "Next" and "JP", in a battle and out of one, and over the job screen and the
// abilities) is made by 0x2C1310 from a copy of the MENU's record of the unit:
// the menu's update of the card (0x2BD05C) copies the record its table names
// (0x1800F50 by the word at 0x1811428) from + 0x70 on into a place of its own
// (0x1876C80) and only then calls 0x2C1310, whose view's maker asks the slot;
// 0x2C33D0 does the same with a copy on the stack. His Jill, a Skirmisher with
// Battlemage loaded, showed Battlemage's numbers under Skirmisher's name. So
// the record's own job (its word at + 0x24) is loaded as either starts, before
// the game copies (Seen): a swap writes the menu's records, so the copy is
// that job's. Inside a battle the same update lays the battle unit's numbers
// over its copy, from a record made of a copy of the unit (0x2BD27F; 0x368424
// does it too, and the battle keeps one more copy, 0x2FD1390): such a copy
// gets its battle unit's side, and only a unit the game has just made from a
// party's record (0x275B84, told by Built) the party's (Made).
//
// (1.38.4, Zodi's word of 10 November: "go on with what is still open with
// your recommendation") The battle's side beside the saves. What was noted of
// the battle's side for a copy was kept in this run of the game alone, so a
// battle taken up again after the game was closed had the loaded job's (in
// the copy's units) and, for every other job, what the unit had before the
// battle. Now each copy's battle's side is also written to a small file beside
// the saves, one of a ring of sixteen named by the copy's number (Battle/00.json
// to 15.json: the oldest is written over, none is ever deleted), with the
// copy's whole mark in it; a copy put back that wasn't noted in this run is
// looked for there, and taken only when the file's mark is the copy's. A
// copy's number starts from a number of this run's own, so two runs' copies
// don't share a mark.
//
// A unit is known by what never changes of it (its birthday, its name's
// number, its sex): a new unit's record isn't cleared as the game makes it
// (0x275310), so a place of the party can change hands, and what was kept for
// the unit before must not become the new one's.
//
// Beside the save: as the game writes a save (0x218F78) the jobs that aren't
// loaded are written to a file named by what it holds, beside the game's
// saves, and the file's key and the loaded job's number go into the
// framework's own bytes of the save's variables; as a save loads they are
// read back. The loaded job's progress is in the save itself.
//
// What a unit starts a job with. The game gives every job of a unit it makes
// 100 to 199 JP (0x2770BC), which is level 1: a job with less shows as the
// card's "--" (his word on test 76). The loaded job of a unit with none is given
// that as the menu makes its copy of the unit (JobRoom.Code, the level's copy),
// but a job brought in after that would show its nothing. So a job brought in
// for a man or a woman who has nothing in it is brought in with its start: a
// number of the unit's and the job's own (Start), the same whenever it is asked,
// so it needs no keeping.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;

namespace ModStudioEventSetup
{
    public sealed unsafe class JobProgress
    {
        public const int Places = Framework.RosterUnits, UnitBytes = Framework.RosterUnitBytes;
        /// <summary>The battle's units (0x1853CE0) and the menu's copies of the party's (0x37415A0), as the game keeps
        /// them.</summary>
        public const int BattleUnits = 21, BattleBytes = 0x200, MenuRecords = 55, MenuBytes = 0x280;
        /// <summary>(1.38.1) A battle unit's bytes that say whose it is, as the game makes one from a party's record
        /// (0x276758): the party's place, the sex's byte, the birthday's word (its nine bits and the zodiac's four; the
        /// three between aren't the unit's) and the name's number. (1.38.2) And its job.</summary>
        public const int BattleJobAt = 3;
        public const int BattlePlaceAt = 2, BattleSexAt = 6, BattleBirthAt = 8, BirthBits = 0xF1FF, BattleNameAt = 0x1FC;
        /// <summary>(1.38.3) A battle unit the battle isn't using holds 0xFF here (0x304B48 leaves it so; the game's own
        /// searches for a place's battle unit pass such by, 0x2BD1D0).</summary>
        public const int BattleUsedAt = 1, NotUsed = 0xFF;
        /// <summary>(1.38.1) A record of a unit: the number its maker knows the unit by, twice (MenuPlaceAt and here:
        /// the party's place in the menu's, the battle unit in the battle's), and a battle's record's party place.</summary>
        public const int RecordUnitAt = 0x22, RecordPartyAt = 0x1E;
        /// <summary>(1.38.3) A record's word of its unit's job, which the status card is made for (0x2BD05C, 0x2C33D0).</summary>
        public const int RecordJobAt = 0x24;
        /// <summary>(1.38.1) Every record there is: the menu's copies, the battle's own (one a battle unit, 0x3C46770)
        /// and the one on its own (0x3C51F10).</summary>
        public const int Records = MenuRecords + BattleUnits + 1;
        /// <summary>(1.38.1) A unit's JP and total JP are a slot's two bytes each, the mods' slot the last; its learned
        /// rows 22 of three bytes; a record shows no more than 9999 in the first 20 slots (0x360048, 0x284A08,
        /// 0x39231C).</summary>
        public const int LearnedRows = 22, ShownSlots = 20, MostShown = 9999;
        /// <summary>A unit's record: its place in the party (0xFF: none), its sex's bits, its birthday (two bytes) and
        /// its name's number; a menu's copy's party place (a word).</summary>
        public const int PlaceAt = 1, NoPlace = 0xFF, SexAt = 4, SexBits = 0xE0, BirthdayAt = 5, NameAt = 0x230,
                         MenuPlaceAt = 0x2C;
        /// <summary>A man's and a woman's bits of the sex's (a monster has no jobs), and what a job starts with: the least
        /// JP of level 1 and how many numbers from it a start can be.</summary>
        public const int People = 0xC0, StartJp = 100, StartSpan = 100;

        /// <summary>Where slot 22's JP, total JP and level (the high half of a byte) and the learned row 19 are.</summary>
        public readonly struct Where
        {
            public int Jp { get; }
            public int Total { get; }
            public int Level { get; }
            public int Row { get; }

            public Where(int jp, int total, int level, int row)
            {
                Jp = jp;
                Total = total;
                Level = level;
                Row = row;
            }
        }

        public static readonly Where Party = new Where(0x80 + 2 * JobRoom.Slot, 0xAE + 2 * JobRoom.Slot, 0x74 + JobRoom.Slot / 2,
                                                       0x32 + 3 * JobRoom.OwnRow);
        public static readonly Where Menu = new Where(0xCA + 2 * JobRoom.Slot, 0xF8 + 2 * JobRoom.Slot, 0xBD + JobRoom.Slot / 2,
                                                      0x7B + 3 * JobRoom.OwnRow);
        public static readonly Where Battle = new Where(0xF0 + 2 * JobRoom.Slot, 0x11E + 2 * JobRoom.Slot, 0xE4 + JobRoom.Slot / 2,
                                                        0xA2 + 3 * JobRoom.OwnRow);

        /// <summary>The framework's bytes of a save's variables for this: the file's key (0: none), then the loaded job's
        /// number (0: a save from before this, whose units hold the first number's job).</summary>
        public const int MarkAt = ItemRoom.JobsMark, MarkBytes = ItemRoom.JobsMarkBytes;
        public const string Folder = "fftivc.utility.modstudio.eventsetup.JobProgress", Format = "Mod Studio job progress";
        public const int Version = 1;
        /// <summary>(1.38.4) The battle's side beside the saves: its folder in Folder, its files' first words, how many
        /// files the ring is of, and a copy's file.</summary>
        public const string BattleFolder = "Battle", BattleFormat = "Mod Studio job progress in a battle";
        public const int RingFiles = 16;
        public static string BattleFileName(int copy) => (copy % RingFiles).ToString("00", CultureInfo.InvariantCulture) + ".json";
        /// <summary>(1.38.4) The log's line when no folder beside the saves took a copy's file.</summary>
        public const string BattleNotWritten = "what the battle's units have earned in the mods' other jobs couldn't be written "
            + "beside the game's saves: taken up again after the game was closed, this battle keeps it for the job they were "
            + "last seen in only.";

        readonly byte* _roster;
        readonly byte* _battle;
        readonly byte* _menu;
        readonly byte* _records;
        readonly byte* _one;
        readonly int* _cell;
        readonly string[] _names;
        readonly int[] _numbers;
        readonly IReadOnlyList<string> _folders;
        readonly ulong[,] _kept;
        /// <summary>What a save's file held for jobs no mod gives now, by the job's name and the party's place: carried
        /// to the next file.</summary>
        readonly SortedDictionary<string, ulong[]> _away = new SortedDictionary<string, ulong[]>(StringComparer.Ordinal);
        readonly ulong[] _unit = new ulong[Places];
        readonly bool[] _known = new bool[Places];
        /// <summary>(1.38.2) The battle's side: a battle unit's progress in the jobs that aren't loaded (the loaded
        /// job's is in the unit itself), whether it has any of its own there, and whose it is kept for (what
        /// Fingerprint knows a unit by; 0: nobody's).</summary>
        readonly ulong[,] _there;
        readonly bool[,] _has;
        readonly ulong[] _whoThere = new ulong[BattleUnits];
        /// <summary>(1.38.1) As last read (Map): the party's place each battle unit holds a unit of (-1: none), and the
        /// place each record is a unit's of (-1: none). (1.38.2) And the battle unit a record was made of (-1: made of
        /// the party's record).</summary>
        readonly int[] _slot = new int[BattleUnits];
        readonly int[] _owner = new int[Records];
        readonly int[] _ownerUnit = new int[Records];
        bool _changedHands;
        /// <summary>(1.38.3) The unit the game last made from a party's record outside the battle's units (0x275B84), by
        /// where it is.</summary>
        byte* _temp;
        /// <summary>(1.38.1) The loaded job's progress as it was last brought into a place, and how often what was read
        /// back was less (with the last such, for the log).</summary>
        readonly ulong[] _brought = new ulong[Places];
        /// <summary>(1.38.2) The battle's side as the game last took its copy of the battle, that copy's mark (the
        /// last three bytes a number of the copy's own) and how many copies were taken.</summary>
        readonly ulong[,] _copyThere;
        readonly bool[,] _copyHas;
        readonly ulong[] _copyWho = new ulong[BattleUnits];
        readonly byte[] _copyMark = new byte[MarkBytes];
        bool _copied;
        int _copies;
        /// <summary>(1.38.2) The files' words written in this run of the game, by their key: read back from here first.</summary>
        readonly Dictionary<uint, string> _texts = new Dictionary<uint, string>();
        /// <summary>(1.38.4) The ring's files' words of this run, by their place in the ring: read first.</summary>
        readonly Dictionary<int, string> _battleTexts = new Dictionary<int, string>();

        /// <summary>(1.38.1) How often a job's progress read back as less than was brought in and was kept as it was; the
        /// last such job's name and the party's place.</summary>
        public int Refused { get; private set; }
        public string RefusedJob { get; private set; } = "";
        public int RefusedPlace { get; private set; }

        /// <summary>(1.38.1) The log's line of it.</summary>
        public static string RefusedLine(string job, int place)
            => $"a unit's progress in {job} read as less than it had (the unit in place {place + 1} of the party): kept as it was.";

        /// <summary>The job loaded in every unit's slot 22 and row 19: its place among the jobs given.</summary>
        public int Loaded { get; private set; }

        /// <summary>`names` and `numbers` the jobs given (Numbers.json's names of them, their job numbers); `cell` where
        /// the native code reads the loaded job, or null. (1.38.1) `records` the battle's own records of its units and
        /// `one` the one record on its own. (1.38.4) `copiesBefore`: the number this run's copies of a battle are counted
        /// from (a number of the run's own, so that another run's copy has another mark).</summary>
        public JobProgress(byte* roster, byte* battle, byte* menu, byte* records, byte* one, IReadOnlyList<string> names,
                           IReadOnlyList<int> numbers, IReadOnlyList<string> folders, int* cell, int copiesBefore = 0)
        {
            _copies = copiesBefore & 0xFFFFFF;
            _roster = roster;
            _battle = battle;
            _menu = menu;
            _records = records;
            _one = one;
            _cell = cell;
            _names = new List<string>(names).ToArray();
            _numbers = new List<int>(numbers).ToArray();
            _folders = folders;
            _kept = new ulong[_names.Length, Places];
            _there = new ulong[_names.Length, BattleUnits];
            _has = new bool[_names.Length, BattleUnits];
            _copyThere = new ulong[_names.Length, BattleUnits];
            _copyHas = new bool[_names.Length, BattleUnits];
            Array.Fill(_slot, -1);
            Array.Fill(_owner, -1);
            Array.Fill(_ownerUnit, -1);
            if (_cell != null)
                *_cell = 0;
        }

        // --- the eight bytes ---------------------------------------------------------------------------------------

        public static ulong Read(byte* record, Where w)
            => *(ushort*)(record + w.Jp) | (ulong)*(ushort*)(record + w.Total) << 16 | (ulong)(record[w.Level] >> 4) << 32
               | (ulong)record[w.Row] << 40 | (ulong)record[w.Row + 1] << 48 | (ulong)record[w.Row + 2] << 56;

        public static void Write(byte* record, Where w, ulong value)
        {
            *(ushort*)(record + w.Jp) = (ushort)value;
            *(ushort*)(record + w.Total) = (ushort)(value >> 16);
            record[w.Level] = (byte)(record[w.Level] & 0x0F | (int)(value >> 32 & 0xF) << 4);
            record[w.Row] = (byte)(value >> 40);
            record[w.Row + 1] = (byte)(value >> 48);
            record[w.Row + 2] = (byte)(value >> 56);
        }

        byte* Unit(int place) => _roster + place * UnitBytes;
        bool Live(int place) => Unit(place)[PlaceAt] != NoPlace;

        /// <summary>What never changes of a unit: its sex, its birthday and its name's number. Never 0 for a unit.</summary>
        public static ulong Fingerprint(byte* unit)
            => (ulong)(unit[SexAt] & SexBits) | (ulong)unit[BirthdayAt] << 8 | (ulong)unit[BirthdayAt + 1] << 16
               | (ulong)*(ushort*)(unit + NameAt) << 24 | 1UL << 40;

        /// <summary>What a unit starts a job with: 100 to 199 JP, the same of total JP, level 1 and nothing learned. The
        /// number is by who the unit is and the job's name (Numbers.json's), so it is the same every time.</summary>
        public static ulong Start(ulong who, string job)
        {
            uint hash = 2166136261;
            for (int n = 0; n < 8; n++)
                hash = (hash ^ (byte)(who >> 8 * n)) * 16777619;
            foreach (byte b in Encoding.UTF8.GetBytes(job))
                hash = (hash ^ b) * 16777619;
            uint jp = StartJp + hash % StartSpan;
            return jp | (ulong)jp << 16 | 1UL << 32;
        }

        /// <summary>A unit's progress in a job as it is brought in: what was kept, or its start for a man or a woman
        /// with nothing kept (the place looked at before this).</summary>
        ulong Bring(int job, int place)
        {
            ulong kept = _kept[job, place];
            if (kept != 0 || (Unit(place)[SexAt] & People) == 0)
                return kept;
            return Start(_unit[place], _names[job]);
        }

        // --- whose place it is ---------------------------------------------------------------------------------------

        void Forget(int place)
        {
            for (int job = 0; job < _names.Length; job++)
                _kept[job, place] = 0;
            foreach (var kept in _away.Values)
                kept[place] = 0;
        }

        /// <summary>A place of the party looked at: an empty one is nobody's (whoever comes next is new there); one whose
        /// unit isn't the unit known there is a new unit's, which starts with nothing in any of the mods' jobs (what
        /// the game left in its record from the unit before it cleared too).</summary>
        void Look(int place)
        {
            byte* unit = Unit(place);
            if (unit[PlaceAt] == NoPlace)
            {
                _known[place] = true;
                _unit[place] = 0;
                return;
            }
            ulong now = Fingerprint(unit);
            if (!_known[place])
            {
                _known[place] = true;
                _unit[place] = now;
                _brought[place] = Read(unit, Party);
                return;
            }
            if (_unit[place] == now)
                return;
            _unit[place] = now;
            Forget(place);
            PutParty(place, 0);
            for (int b = 0; b < BattleUnits; b++)
                if (_slot[b] == place)
                    Write(BattleUnit(b), Battle, 0);
            _changedHands = true;
        }

        /// <summary>Every place of the party looked at (Look), whose each battle unit and record is read first (Map).</summary>
        public void LookAll()
        {
            Map();
            for (int place = 0; place < Places; place++)
                Look(place);
            if (_changedHands)
            {
                _changedHands = false;
                Show();
            }
        }

        // --- whose a battle unit or a record is -----------------------------------------------------------------------

        byte* BattleUnit(int b) => _battle + b * BattleBytes;

        /// <summary>(1.38.1) A battle unit that is the unit of the place of the party it names: it holds the same sex,
        /// birthday and name's number as that place's record does (what Fingerprint knows a unit by). A unit the game
        /// cleared (0x304B48), or one of another battle's, another save's or the enemy's, isn't.</summary>
        bool Mine(byte* unit, int place)
        {
            byte* record = Unit(place);
            return (record[SexAt] & SexBits) != 0 && (unit[BattleSexAt] & SexBits) == (record[SexAt] & SexBits)
                   && (*(ushort*)(unit + BattleBirthAt) & BirthBits) == (*(ushort*)(record + BirthdayAt) & BirthBits)
                   && *(ushort*)(unit + BattleNameAt) == *(ushort*)(record + NameAt);
        }

        byte* Record(int r) => r < MenuRecords ? _menu + r * MenuBytes
                               : r < MenuRecords + BattleUnits ? _records + (r - MenuRecords) * MenuBytes : _one;

        static int Shown(int slot, ushort value) => slot < ShownSlots && value > MostShown ? MostShown : value;

        /// <summary>(1.38.1) Two copies of a unit holding the same progress in every job but the mods' (the JP and total
        /// JP of the 22 slots before the mods' as a record shows them, the other 21 learned rows).</summary>
        static bool Same(byte* a, Where wa, byte* b, Where wb)
        {
            ushort* jpA = (ushort*)(a + wa.Jp - 2 * JobRoom.Slot), jpB = (ushort*)(b + wb.Jp - 2 * JobRoom.Slot);
            ushort* totalA = (ushort*)(a + wa.Total - 2 * JobRoom.Slot), totalB = (ushort*)(b + wb.Total - 2 * JobRoom.Slot);
            for (int slot = 0; slot < JobRoom.Slot; slot++)
                if (Shown(slot, jpA[slot]) != Shown(slot, jpB[slot]) || Shown(slot, totalA[slot]) != Shown(slot, totalB[slot]))
                    return false;
            byte* rowsA = a + wa.Row - 3 * JobRoom.OwnRow, rowsB = b + wb.Row - 3 * JobRoom.OwnRow;
            for (int n = 0; n < 3 * LearnedRows; n++)
                if (n / 3 != JobRoom.OwnRow && rowsA[n] != rowsB[n])
                    return false;
            return true;
        }

        /// <summary>(1.38.1) The party's place a record is a unit's of, or -1. The one record on its own names its battle
        /// unit and nothing else. Any other names its unit twice. Read the menu's way that is a place of the party's;
        /// read the battle's way it is a battle unit that holds someone, whose party place the record names too (so a
        /// record of the enemy's is nobody's). A record that reads both ways (a battle unit's number is a place of the
        /// party's too) is the battle's when the rest of what it holds is that battle unit's and not that place's
        /// record's; the menu's otherwise, since the menu writes its own back to the party (0x285744) and the battle's
        /// are only shown.</summary>
        /// (1.38.2) `battleUnit`: the battle unit the record was made of, when it is the battle's (-1: the menu's, made
        /// of the party's record).
        int Owner(byte* record, bool alone, out int battleUnit)
        {
            battleUnit = -1;
            int unit = *(ushort*)(record + MenuPlaceAt);
            if (alone)
            {
                if (unit >= BattleUnits)
                    return -1;
                battleUnit = unit;
                return _slot[unit];
            }
            if (*(ushort*)(record + RecordUnitAt) != unit)
                return -1;
            int byMenu = unit < Places && Live(unit) ? unit : -1;
            if (unit >= BattleUnits || (BattleUnit(unit)[BattleSexAt] & SexBits) == 0
                || *(ushort*)(record + RecordPartyAt) != BattleUnit(unit)[BattlePlaceAt])
                return byMenu;
            if (byMenu >= 0 && !(Same(record, Menu, BattleUnit(unit), Battle) && !Same(record, Menu, Unit(byMenu), Party)))
                return byMenu;
            battleUnit = unit;
            return _slot[unit];
        }

        /// <summary>(1.38.2) What the battle's side keeps for a battle unit, dropped.</summary>
        void Drop(int b)
        {
            for (int job = 0; job < _names.Length; job++)
                _has[job, b] = false;
        }

        /// <summary>(1.38.1) Whose each battle unit and each record is, read from what they hold now. (1.38.2) A battle
        /// unit that is another's than what the battle's side keeps for it was (or nobody's now) keeps nothing; one that
        /// names a place the game has emptied (a guest who joined is written to another, 0x274EB8) is nobody's.</summary>
        void Map()
        {
            for (int b = 0; b < BattleUnits; b++)
            {
                int place = BattleUnit(b)[BattlePlaceAt];
                _slot[b] = place < Places && Live(place) && Mine(BattleUnit(b), place) ? place : -1;
                ulong who = _slot[b] < 0 ? 0 : Fingerprint(Unit(place));
                if (who != _whoThere[b])
                {
                    Drop(b);
                    _whoThere[b] = who;
                }
            }
            for (int r = 0; r < Records; r++)
                _owner[r] = Owner(Record(r), r == Records - 1, out _ownerUnit[r]);
        }

        // --- the swap -------------------------------------------------------------------------------------------------

        /// <summary>(1.38.1) The loaded job's progress of a unit, to put away: what its record holds, unless that is
        /// less than was brought in (less total JP, or something learned that isn't): then what was brought in,
        /// counted.</summary>
        ulong Held(int place)
        {
            ulong truth = Read(Unit(place), Party), had = _brought[place];
            if ((ushort)(truth >> 16) >= (ushort)(had >> 16) && (had >> 40 & ~(truth >> 40)) == 0)
                return truth;
            Refused++;
            RefusedJob = _names[Loaded];
            RefusedPlace = place;
            return had;
        }

        /// <summary>A unit's loaded progress written to its record.</summary>
        void PutParty(int place, ulong value)
        {
            Write(Unit(place), Party, value);
            _brought[place] = value;
        }

        /// <summary>(1.38.2) Every record of a unit of the party's (as Map read them) written with the side its maker
        /// read: the battle unit's for the battle's, the party's record's for the menu's.</summary>
        void Show()
        {
            for (int r = 0; r < Records; r++)
                if (_owner[r] >= 0)
                    Write(Record(r), Menu, _ownerUnit[r] >= 0 ? Read(BattleUnit(_ownerUnit[r]), Battle)
                                                              : Read(Unit(_owner[r]), Party));
        }

        /// <summary>(1.38.2) The party's side of a swap: every unit's record's progress put away under the loaded job, the
        /// asked job's put in its place.</summary>
        void SwapParty(int job)
        {
            for (int place = 0; place < Places; place++)
            {
                if (!Live(place))
                    continue;
                _kept[Loaded, place] = Held(place);
                PutParty(place, Bring(job, place));
            }
        }

        void SetLoaded(int job)
        {
            Loaded = job;
            if (_cell != null)
                *_cell = job;
        }

        /// <summary>The job asked for loaded: every unit's progress in the loaded job put away, the asked job's put in
        /// its place. (1.38.2) Each side on its own: a battle unit of the party's keeps its own for the job put away and
        /// gets its own of the asked job, or the party's when it has none of its own yet (nothing at all kept for it is
        /// none too: the party's is its start then, as for the record).</summary>
        public void Swap(int job)
        {
            if (job == Loaded || job < 0 || job >= _names.Length)
                return;
            LookAll();
            SwapParty(job);
            for (int b = 0; b < BattleUnits; b++)
            {
                if (_slot[b] < 0)
                    continue;
                byte* unit = BattleUnit(b);
                _there[Loaded, b] = Read(unit, Battle);
                _has[Loaded, b] = true;
                Write(unit, Battle, _has[job, b] && _there[job, b] != 0 ? _there[job, b] : Read(Unit(_slot[b]), Party));
            }
            SetLoaded(job);
            Show();
        }

        int BattleIndex(byte* unit)
        {
            long off = unit - _battle;
            return off >= 0 && off < BattleUnits * BattleBytes && off % BattleBytes == 0 ? (int)(off / BattleBytes) : -1;
        }

        /// <summary>The game made a battle unit from a party's record (0x276758): (1.38.2) it holds the party's side
        /// now, so what the battle's side kept for that battle unit is dropped. (1.38.3) One made outside the battle's
        /// units is a unit for the moment (0x275B84), noted by where it is: the last such is the party's side's, where a
        /// copy of a battle unit is its battle unit's (Made).</summary>
        public void Built(byte* battleUnit)
        {
            int b = BattleIndex(battleUnit);
            if (b >= 0)
                Drop(b);
            else
                _temp = battleUnit;
        }

        /// <summary>(1.53.0, Zodi's order of 13 November: "jobs in a quest's battle") The game is about to write a battle
        /// unit back to a place of the party's (0x274EB8): its own job, when it is one of the mods', is loaded first, so the
        /// record gets that job's progress as the loaded job's. A guest's battle unit is no unit of the party's, so a swap
        /// passes over it and its slot 22 and row 19 hold its own job's whichever job is loaded: one who joins in one of the
        /// mods' jobs would otherwise have it put away under another job (dev/research/sidequests/quest_jobs.py).</summary>
        public void WritingBack(byte* battleUnit)
        {
            int job = Array.IndexOf(_numbers, battleUnit[BattleJobAt]);
            if (job >= 0)
                Swap(job);
        }

        /// <summary>The game wrote a battle unit back to a place of the party's (0x274EB8, which answers with the place
        /// or -1): (1.38.2) the loaded job's progress is in the record now, and the other jobs' of the battle's side
        /// are the party's side's from here. A unit written to another place than it had (a guest who joins) takes
        /// what was kept for it along; a unit never seen starts with what the game wrote.</summary>
        public void WrittenBack(byte* battleUnit, int place)
        {
            int b = BattleIndex(battleUnit);
            if (b < 0 || place < 0 || place >= Places || !Live(place))
                return;
            ulong who = Fingerprint(Unit(place));
            if (!_known[place] || _unit[place] != who)
            {
                Forget(place);
                for (int from = 0; from < Places; from++)
                    if (from != place && _known[from] && _unit[from] == who)
                    {
                        for (int job = 0; job < _names.Length; job++)
                            _kept[job, place] = _kept[job, from];
                        foreach (var kept in _away.Values)
                            kept[place] = kept[from];
                        Forget(from);
                        _unit[from] = 0;
                        break;
                    }
                _known[place] = true;
                _unit[place] = who;
            }
            if (_whoThere[b] == who)
                for (int job = 0; job < _names.Length; job++)
                    if (job != Loaded && _has[job, b])
                        _kept[job, place] = _there[job, b];
            _brought[place] = Read(Unit(place), Party);
            Drop(b);
        }

        // --- what the game copies before it asks ------------------------------------------------------------------------

        /// <summary>(1.38.2) The game is about to make a record of a battle unit (0x360048) or to copy its progress for
        /// a view (0xFCF80, through Shown): the unit's own job, when it is one of the mods', is loaded first, so what
        /// the game copies is that job's. A unit made for the moment from a party's record (0x275C70), which no swap
        /// reaches, gets the party's side written to it. (1.38.3) Any other unit outside the battle's units is a copy the
        /// game took of a battle unit (0x2BD05C and 0x368424 on their stacks, 0x2FD1390), to lay the battle's numbers
        /// over the menu's: it gets the side of the battle unit it was taken of, which is ahead of the party's by what
        /// the battle has given (1.38.2 wrote the party's to those too).</summary>
        public void Made(byte* unit)
        {
            int job = Array.IndexOf(_numbers, unit[BattleJobAt]);
            if (job < 0)
                return;
            Swap(job);
            if (BattleIndex(unit) >= 0)
                return;
            int place = unit[BattlePlaceAt];
            if (place >= Places || !Live(place) || !Mine(unit, place))
                return;
            int of = unit == _temp ? -1 : TakenOf(place);
            Write(unit, Battle, of >= 0 ? Read(BattleUnit(of), Battle) : Read(Unit(place), Party));
        }

        /// <summary>(1.38.3) The battle unit a copy of a place's unit was taken of, as the game looks for it (0x2BD1B0,
        /// 0x3685DC: the last battle unit in use that names the place), or -1: one that is that place's unit by what it
        /// holds.</summary>
        int TakenOf(int place)
        {
            int of = -1;
            for (int b = 0; b < BattleUnits; b++)
            {
                byte* unit = BattleUnit(b);
                if (unit[BattleUsedAt] != NotUsed && unit[BattlePlaceAt] == place && Mine(unit, place))
                    of = b;
            }
            return of;
        }

        /// <summary>(1.38.3, test 83) The game is about to copy a record of the menu's for the status card (0x2BD05C,
        /// 0x2C33D0), and will ask the job's slot only after: the record's own job, when it is one of the mods', is
        /// loaded first, so the record holds that job's as it is copied (a swap writes every record of the menu's). A
        /// record that isn't one of the menu's own (nowhere is before them) is left: the game's table of them names no
        /// other (0x2852A7, 0x285D9D, 0x28B84C).</summary>
        public void Seen(byte* record)
        {
            long off = record - _menu;
            if (off < 0 || off >= MenuRecords * MenuBytes || off % MenuBytes != 0)
                return;
            Swap(Array.IndexOf(_numbers, *(ushort*)(record + RecordJobAt)));
        }

        /// <summary>(1.38.2) The game is about to copy a battle unit's progress for a view, by the unit's number.</summary>
        public void Shown(int battleUnit)
        {
            if ((uint)battleUnit < BattleUnits)
                Made(BattleUnit(battleUnit));
        }

        // --- the battle's copy ------------------------------------------------------------------------------------------

        /// <summary>(1.38.2) The game is about to take its copy of the battle (0x2CDBC4), which holds the variables and
        /// the party's records: the mark written as for a save (Saving), with a number of this copy's own in its last
        /// three bytes, and the battle's side noted for that mark.</summary>
        public void Copied(Span<byte> bank, List<string> said)
        {
            // (1.55.0) No job of the mods' own (the mods give only the game's Dark Knight or Onion Knight): nothing to keep.
            if (_names.Length == 0)
                return;
            Saving(bank, said);
            _copies = _copies % 0xFFFFFF + 1;
            bank[MarkAt + 5] = (byte)_copies;
            bank[MarkAt + 6] = (byte)(_copies >> 8);
            bank[MarkAt + 7] = (byte)(_copies >> 16);
            bank.Slice(MarkAt, MarkBytes).CopyTo(_copyMark);
            Array.Copy(_there, _copyThere, _there.Length);
            Array.Copy(_has, _copyHas, _has.Length);
            Array.Copy(_whoThere, _copyWho, BattleUnits);
            _copied = true;
            WriteBattle(said);
        }

        /// <summary>(1.38.4) The battle's side as just noted for a copy, in a file's words: each battle unit that has
        /// something of its own in a job that isn't loaded, by its number, with whose it is. `any`: there is one.</summary>
        string BattleText(out bool any)
        {
            var units = new List<string>();
            for (int b = 0; b < BattleUnits; b++)
            {
                var each = new List<string>();
                for (int job = 0; job < _names.Length; job++)
                    if (job != Loaded && _copyHas[job, b] && _copyThere[job, b] != 0)
                        each.Add($"{Quote(_names[job])}:\"{Hex(_copyThere[job, b])}\"");
                if (each.Count != 0)
                    units.Add($"{{\"Battle\":{b},\"Unit\":\"{Hex(_copyWho[b])}\",\"Jobs\":{{{string.Join(",", each)}}}}}");
            }
            any = units.Count != 0;
            return $"{{\"Format\":{Quote(BattleFormat)},\"Version\":{Version},\"Mark\":\"{Convert.ToHexString(_copyMark)}\","
                   + $"\"Units\":[\n{string.Join(",\n", units)}\n]}}\n";
        }

        /// <summary>(1.38.4) The copy just noted written to its file of the ring, in every folder beside the saves. With
        /// nothing to keep no file is made (one job's users keep none at all), but one already there is written over:
        /// it is another copy's, and mustn't be read as this one's.</summary>
        void WriteBattle(List<string> said)
        {
            string text = BattleText(out bool any);
            _battleTexts[_copies % RingFiles] = text;
            bool written = false;
            foreach (var folder in _folders)
                try
                {
                    string file = Path.Combine(folder, BattleFolder, BattleFileName(_copies));
                    if (any || File.Exists(file))
                    {
                        Directory.CreateDirectory(Path.Combine(folder, BattleFolder));
                        File.WriteAllText(file, text);
                    }
                    written = true;
                }
                catch (Exception e) when (e is IOException || e is UnauthorizedAccessException)
                {
                }
            if (any && !written)
                said.Add(BattleNotWritten);
        }

        /// <summary>(1.38.4) The battle's side of a copy that wasn't the one last noted in this run (another run's, or an
        /// earlier one of this run's), read from its file of the ring: this run's words first, then each folder's. A file
        /// is that copy's only when it holds the copy's whole mark; a mark with no copy's number is a save's. What it
        /// holds is noted as the copy's, as Copied notes it.</summary>
        bool ReadBattle(ReadOnlySpan<byte> mark)
        {
            int copy = mark[5] | mark[6] << 8 | mark[7] << 16;
            if (copy == 0)
                return false;
            string wanted = Convert.ToHexString(mark);
            var texts = new List<string>();
            if (_battleTexts.TryGetValue(copy % RingFiles, out var mine))
                texts.Add(mine);
            foreach (var folder in _folders)
                try
                {
                    string file = Path.Combine(folder, BattleFolder, BattleFileName(copy));
                    if (File.Exists(file))
                        texts.Add(File.ReadAllText(file));
                }
                catch (Exception e) when (e is IOException || e is UnauthorizedAccessException)
                {
                }
            foreach (string text in texts)
                try
                {
                    using var doc = JsonDocument.Parse(text);
                    var root = doc.RootElement;
                    if (root.GetProperty("Format").GetString() != BattleFormat || root.GetProperty("Mark").GetString() != wanted)
                        continue;
                    var there = new ulong[_names.Length, BattleUnits];
                    var has = new bool[_names.Length, BattleUnits];
                    var who = new ulong[BattleUnits];
                    foreach (var unit in root.GetProperty("Units").EnumerateArray())
                    {
                        int b = unit.GetProperty("Battle").GetInt32();
                        if (b < 0 || b >= BattleUnits)
                            continue;
                        who[b] = ulong.Parse(unit.GetProperty("Unit").GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture);
                        foreach (var job in unit.GetProperty("Jobs").EnumerateObject())
                        {
                            int index = Array.IndexOf(_names, job.Name);
                            if (index < 0)
                                continue;
                            there[index, b] = ulong.Parse(job.Value.GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture);
                            has[index, b] = true;
                        }
                    }
                    Array.Copy(there, _copyThere, there.Length);
                    Array.Copy(has, _copyHas, has.Length);
                    Array.Copy(who, _copyWho, BattleUnits);
                    mark.CopyTo(_copyMark);
                    _copied = true;
                    return true;
                }
                catch (Exception e) when (e is JsonException || e is FormatException || e is KeyNotFoundException
                                          || e is InvalidOperationException)
                {
                }
            return false;
        }

        /// <summary>(1.38.2) The game put its copy of the battle back. `bank` the variables that came with it;
        /// `partyToo`: the party's records came back with it (0x2CE5C8), else they are as they were and only the
        /// variables, the units and the records came (0x2CE7A8), so the party's records are first brought to the job
        /// the copy's mark names. Then the party's side is read by the mark as for a save loaded, and the battle's side
        /// is what was noted for this copy ((1.38.4) or what its file of the ring beside the saves holds for it; none for
        /// a copy neither noted in this run of the game nor found there).</summary>
        public void Restored(ReadOnlySpan<byte> bank, bool partyToo, Func<int, string?> nameOf, List<string> said)
        {
            // (1.55.0) No job of the mods' own (the mods give only the game's Dark Knight or Onion Knight): nothing to keep.
            if (_names.Length == 0)
                return;
            int number = bank[MarkAt + 4] != 0 ? bank[MarkAt + 4] : JobRoom.FreeNumbers[0];
            int job = Array.IndexOf(_numbers, number);
            if (!partyToo && job >= 0 && job != Loaded)
            {
                LookAll();
                SwapParty(job);
                SetLoaded(job);
            }
            Load(bank, nameOf, said);
            var mark = bank.Slice(MarkAt, MarkBytes);
            if ((_copied && mark.SequenceEqual(_copyMark)) || ReadBattle(mark))
                for (int b = 0; b < BattleUnits; b++)
                    if (_copyWho[b] != 0 && _copyWho[b] == _whoThere[b])
                        for (int each = 0; each < _names.Length; each++)
                        {
                            _there[each, b] = _copyThere[each, b];
                            _has[each, b] = _copyHas[each, b];
                        }
            Show();
        }

        // --- beside the save -------------------------------------------------------------------------------------------

        static string Hex(ulong value) => value.ToString("X16", CultureInfo.InvariantCulture);

        static uint Key(string text)
        {
            uint hash = 2166136261;
            foreach (byte b in Encoding.UTF8.GetBytes(text))
                hash = (hash ^ b) * 16777619;
            return hash == 0 ? 1 : hash;
        }

        static string Quote(string text) => JsonSerializer.Serialize(text);

        /// <summary>The file's words: each unit's progress in every job but the loaded one, by the job's name; null when
        /// there is none to keep. A job a unit has only its start in isn't kept: its start is the same when it is next
        /// brought in.</summary>
        string? FileText()
        {
            var units = new List<string>();
            for (int place = 0; place < Places; place++)
            {
                if (!Live(place))
                    continue;
                var jobs = new SortedDictionary<string, ulong>(StringComparer.Ordinal);
                for (int job = 0; job < _names.Length; job++)
                    if (job != Loaded && _kept[job, place] != 0 && _kept[job, place] != Start(_unit[place], _names[job]))
                        jobs[_names[job]] = _kept[job, place];
                foreach (var (name, kept) in _away)
                    if (kept[place] != 0 && kept[place] != Start(_unit[place], name))
                        jobs[name] = kept[place];
                if (jobs.Count == 0)
                    continue;
                var each = new List<string>();
                foreach (var (name, value) in jobs)
                    each.Add($"{Quote(name)}:\"{Hex(value)}\"");
                units.Add($"{{\"Place\":{place},\"Unit\":\"{Hex(_unit[place])}\",\"Jobs\":{{{string.Join(",", each)}}}}}");
            }
            if (units.Count == 0)
                return null;
            return $"{{\"Format\":{Quote(Format)},\"Version\":{Version},\"Units\":[\n{string.Join(",\n", units)}\n]}}\n";
        }

        public static string FileName(uint key) => key.ToString("X8", CultureInfo.InvariantCulture) + ".json";

        /// <summary>As the game writes a save: the jobs that aren't loaded written to their file (none when there is
        /// nothing in them), the file's key and the loaded job's number written into the save's variables. The loaded
        /// job's progress is in the save itself.</summary>
        public void Saving(Span<byte> bank, List<string> said)
        {
            // (1.55.0) No job of the mods' own (the mods give only the game's Dark Knight or Onion Knight): nothing to keep.
            if (_names.Length == 0)
                return;
            LookAll();
            string? text = FileText();
            uint key = text == null ? 0 : Key(text);
            if (text != null)
            {
                _texts[key] = text;
                bool written = false;
                foreach (var folder in _folders)
                    try
                    {
                        Directory.CreateDirectory(folder);
                        string file = Path.Combine(folder, FileName(key));
                        if (!File.Exists(file))
                            File.WriteAllText(file, text);     // UTF-8 with no mark, the runtime's own way
                        written = true;
                    }
                    catch (Exception e) when (e is IOException || e is UnauthorizedAccessException)
                    {
                    }
                if (!written)
                    said.Add("the units' progress in the mods' jobs couldn't be written beside the game's saves: this save "
                             + "keeps it for the job they were last seen in only.");
            }
            bank.Slice(MarkAt, MarkBytes).Clear();
            BinaryPrimitives.WriteUInt32LittleEndian(bank.Slice(MarkAt, 4), key);
            bank[MarkAt + 4] = (byte)_numbers[Loaded];
        }

        bool ReadFile(uint key)
        {
            string? text = _texts.TryGetValue(key, out var written) ? written : null;
            foreach (var folder in _folders)
            {
                if (text != null)
                    break;
                try
                {
                    string file = Path.Combine(folder, FileName(key));
                    if (File.Exists(file))
                    {
                        text = File.ReadAllText(file);
                        break;
                    }
                }
                catch (Exception e) when (e is IOException || e is UnauthorizedAccessException)
                {
                }
            }
            if (text == null)
                return false;
            try
            {
                using var doc = JsonDocument.Parse(text);
                foreach (var unit in doc.RootElement.GetProperty("Units").EnumerateArray())
                {
                    int place = unit.GetProperty("Place").GetInt32();
                    ulong who = ulong.Parse(unit.GetProperty("Unit").GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture);
                    if (place < 0 || place >= Places || !Live(place) || Fingerprint(Unit(place)) != who)
                        continue;
                    foreach (var job in unit.GetProperty("Jobs").EnumerateObject())
                    {
                        ulong value = ulong.Parse(job.Value.GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture);
                        int index = Array.IndexOf(_names, job.Name);
                        if (index >= 0)
                            _kept[index, place] = value;
                        else
                            Away(job.Name)[place] = value;
                    }
                }
            }
            catch (Exception e) when (e is JsonException || e is FormatException || e is KeyNotFoundException
                                      || e is InvalidOperationException)
            {
                return false;
            }
            return true;
        }

        ulong[] Away(string name)
        {
            if (!_away.TryGetValue(name, out var kept))
                _away[name] = kept = new ulong[Places];
            return kept;
        }

        /// <summary>A save just loaded ((1.38.2) or the plain state put back as a battle is started again from its start,
        /// 0x2CF768): what was kept forgotten, on both sides, its file read by the key in its variables, its units
        /// known as they are. `nameOf` the name the numbers remember for a job's number. A save whose loaded job no mod
        /// gives now has that job's progress kept under its name and the first job given loaded.</summary>
        public void Load(ReadOnlySpan<byte> bank, Func<int, string?> nameOf, List<string> said)
        {
            // (1.55.0) No job of the mods' own (the mods give only the game's Dark Knight or Onion Knight): nothing to keep.
            if (_names.Length == 0)
                return;
            Array.Clear(_kept, 0, _kept.Length);
            _away.Clear();
            Array.Clear(_known, 0, Places);
            Array.Clear(_unit, 0, Places);
            Array.Clear(_has, 0, _has.Length);
            uint key = BinaryPrimitives.ReadUInt32LittleEndian(bank.Slice(MarkAt, 4));
            int number = bank[MarkAt + 4] != 0 ? bank[MarkAt + 4] : JobRoom.FreeNumbers[0];
            int index = Array.IndexOf(_numbers, number);
            if (key != 0 && !ReadFile(key))
                said.Add($"the save's units' progress in the mods' other jobs wasn't found ({FileName(key)}, beside the "
                         + "game's saves): they start again in those jobs.");
            LookAll();
            if (index < 0)
            {
                string? name = nameOf(number);
                for (int place = 0; place < Places; place++)
                {
                    if (!Live(place))
                        continue;
                    ulong held = Read(Unit(place), Party);
                    if (name != null && held != 0)
                        Away(name)[place] = held;
                    PutParty(place, Bring(0, place));
                    for (int b = 0; b < BattleUnits; b++)
                        if (_slot[b] == place)
                            Write(BattleUnit(b), Battle, Read(Unit(place), Party));
                }
                index = 0;
                Show();
            }
            SetLoaded(index);
        }

        /// <summary>For the checks: a unit's kept progress in a job (the party's side), and a battle unit's (the
        /// battle's side; null when it has none of its own).</summary>
        // --- a unit's level in a job, for what opens another (1.48.0) ---------------------------------------------------

        /// <summary>(1.48.0) Which of the records there are a record of a unit is, by where it is (the menu's copies,
        /// the battle's own, the one on its own), or -1.</summary>
        public int IndexOf(byte* record)
        {
            long off = record - _menu;
            if (off >= 0 && off < (long)MenuRecords * MenuBytes && off % MenuBytes == 0)
                return (int)(off / MenuBytes);
            off = record - _records;
            if (off >= 0 && off < (long)BattleUnits * MenuBytes && off % MenuBytes == 0)
                return MenuRecords + (int)(off / MenuBytes);
            return record == _one ? Records - 1 : -1;
        }

        /// <summary>(1.48.0) Whose every record is, read again (Level and Owned go by it).</summary>
        public void Looked() => LookAll();

        /// <summary>(1.48.0) Whether a record (as last looked: Looked) is a unit of the party's.</summary>
        public bool Owned(int record) => record >= 0 && record < Records && _owner[record] >= 0;

        /// <summary>(1.48.0) A unit's level in one of the mods' jobs (its place among the jobs given), by a record of the
        /// unit's as last looked (Looked): for the loaded job what the record holds; for another what is kept for the
        /// unit on the side the record was made from (the battle unit's own once it has any, else the party's, its
        /// start for a man or a woman with nothing kept), as a swap would bring it in. 0 for a record that is nobody's.</summary>
        public int Level(int job, int record)
        {
            if (job < 0 || job >= _names.Length || record < 0 || record >= Records)
                return 0;
            if (job == Loaded)
                return (int)(Read(Record(record), Menu) >> 32 & 0xF);
            int place = _owner[record], b = _ownerUnit[record];
            if (place < 0)
                return 0;
            ulong held = b >= 0 && _has[job, b] && _there[job, b] != 0 ? _there[job, b] : Bring(job, place);
            return (int)(held >> 32 & 0xF);
        }

        /// <summary>(1.56.0) A unit's learned row in one of the mods' jobs (its place among the jobs given): its three bytes
        /// (the first place the highest bit of the first), by a record of the unit's as last looked (Looked), read as Level
        /// reads the level. 0 for a record that is nobody's.</summary>
        public int Row(int job, int record)
        {
            if (job < 0 || job >= _names.Length || record < 0 || record >= Records)
                return 0;
            ulong held;
            if (job == Loaded)
                held = Read(Record(record), Menu);
            else
            {
                int place = _owner[record], b = _ownerUnit[record];
                if (place < 0)
                    return 0;
                held = b >= 0 && _has[job, b] && _there[job, b] != 0 ? _there[job, b] : Bring(job, place);
            }
            return RowOf(held);
        }

        /// <summary>(1.56.0) The learned row of a job's eight bytes as they are kept (Read's way): its three bytes, the first
        /// place the highest bit of the first.</summary>
        public static int RowOf(ulong held)
            => (int)(held >> 40 & 0xFF) << 16 | (int)(held >> 48 & 0xFF) << 8 | (int)(held >> 56 & 0xFF);

        public ulong Kept(int job, int place) => _kept[job, place];
        public ulong? There(int job, int battleUnit) => _has[job, battleUnit] ? _there[job, battleUnit] : null;
    }
}
