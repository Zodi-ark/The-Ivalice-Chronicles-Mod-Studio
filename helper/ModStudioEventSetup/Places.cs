// Mod Studio Framework: the places in the game's program the side quests'
// framework joins. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Each is found by its own instructions' bytes (a pattern, any byte where an
// address or a jump's distance stands), in the program as it lies in memory,
// and must be found exactly where it is meant to be: once (the two variable
// functions twice, one the events', one the world map's, told apart by their
// own bytes). A function's first instructions aren't looked at: another mod
// may have hooked it already (WotL Restoration hooks the events' variable
// function), which puts a jump there; the rest of it is as the game has it.
// Found in Zodi's program of 17 September 2026 (12,158,720 bytes; the
// addresses in brackets are its own, from where it is loaded) by reading it
// as data, never running it; the patterns are Mod Studio's own
// (dev/research/sidequests/), none of another mod's. A game update that
// changes any of them finds nothing, and the framework adds nothing, saying
// which wasn't found; (1.2.0) the two a quest's own battles need (a
// battle's units, its number) are found apart, and only quests with battles
// of their own are left out without them. (1.2.1) The game's progress, which
// a quest's event is kept from moving, is one every quest needs. (1.2.2) The
// world map's travel check is found apart too: without it the quests play,
// and a quest's event waiting where you stand stops travel on, as the game's
// own events do. (1.2.3) The game's travel step keeps r9 to r11 across its
// call of the check, so it is hooked to native code that keeps them
// (Thunks.cs); dev/test_side_quests.py holds every place hooked to what the
// game keeps across its calls. (1.2.4) The travel's state (its flags, the
// roads taken, the roads it has), read where travel start asks the travel
// check found, is found apart as well: without it a start that waits until
// its place is chosen stops a travel passing through, as the game's own
// events do. (1.2.5) What the quests' markers need is found apart: without
// it the quests play without markers. (1.3.0) So is what the mods' own
// places need (the world map screen's setup of its places' pieces, and the
// layouts' copy of a box, its move, its putting in a layer, its piece's
// animations played and stopped): without it they aren't shown, said.
// (1.4.0) So is what the mods' own roads need besides (the screen's keeping
// of its Route piece, a box sized): without it they aren't drawn, said.
// (1.5.0) So is what travel along them needs (the path search, the walk's
// setup of a road, the travel's read of its last road, the world map's test
// of a place shown): without it they are drawn only, said. (1.6.0) And what
// random battles on arriving by them need (the roll, its table of the battle
// grounds' entrances, its two calls): without it they are travelled and
// start no random battle, said. (1.7.0) And what a mod's own place needs to
// be somewhere Ramza goes (the game's places' records and the world map's
// dots, each with every instruction that reads them; the world map screen's
// reads of a place's row, its two allocations and their constructor, its
// switch of its places' collision boxes; the setting of a text): without it
// the places are pictures only and their roads drawn only, said.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public sealed class Places
    {
        /// <summary>The function that sets a table up from its file as the game loads it (0x3D3F3C):
        /// (the table, its file); the table's number at the table + 8, its file at the table +
        /// 0x30, the file's bytes and size at the file + 0x38 and + 0x40.</summary>
        public int SheetInit { get; private set; } = -1;
        /// <summary>The function that reads an event's script (0x2F3BC4): (the PlayStation's
        /// sector, the buffer); the event's number is the sector over 5, or 3 when the number at
        /// ScriptMode's pointer + 8 is 0.</summary>
        public int ScriptReader { get; private set; } = -1;
        /// <summary>Where the pointer the script reader reads its divisor through is (0x3CD9B10).</summary>
        public int ScriptMode { get; private set; } = -1;
        /// <summary>The events' variable function (0x242700): (the command, its variable, its
        /// operand, -, a fifth the event script gives 0).</summary>
        public int EventVariables { get; private set; } = -1;
        /// <summary>The world map's variable function (0x2EC038): (the command, its variable, its
        /// operand).</summary>
        public int WorldVariables { get; private set; } = -1;
        /// <summary>Where each variable function's pointer to the variables is (0x7830D8, 0x78DCE8):
        /// both point at the same 1,024 bytes.</summary>
        public int EventBank { get; private set; } = -1;
        public int WorldBank { get; private set; } = -1;

        /// <summary>The function that gives a battle's units as it loads (0x28416C): no arguments; the
        /// units (16 of 40 bytes) of the battle whose number is at EncounterNumber, from the file
        /// read for it, or 0 while it is read.</summary>
        public int Encounter { get; private set; } = -1;
        /// <summary>Where the number of the battle being loaded is (0x1856930), as the two functions
        /// that load a battle set it from variable 0x32 before reading its file.</summary>
        public int EncounterNumber { get; private set; } = -1;
        /// <summary>(1.2.1) The function that sets the game's progress (0xFF660): (the progress, a
        /// track, its value), what event instruction E9 calls; the value goes into one of two
        /// arrays, as a flag of the progress picks (a replay's or the game's own), and those
        /// waiting on the progress are told.</summary>
        public int Progress { get; private set; } = -1;
        /// <summary>(1.2.2) The world map's check of a travel from where an event waits (0x247D70, no
        /// arguments): 1 stops it ("You cannot travel to the selected location at this time..."),
        /// unless the travel goes back the way you came or the event is one of five the game lets
        /// wait (by place and number); what travel start and each stop on the way ask.</summary>
        public int TravelCheck { get; private set; } = -1;
        /// <summary>Where the event the world map found waiting is (0xD493CC: the location script's
        /// first argument, an event its LoadEvent gives), as the travel check reads it.</summary>
        public int PendingEvent { get; private set; } = -1;
        /// <summary>(1.2.4) The travel's state, as travel start reads it before it asks the travel
        /// check: its flags (0xD8DBB0, bit 0 while a travel is under way), how many of its roads
        /// are taken (0xD8DC08; each stop on the way counts its road before the world map runs
        /// the place's chains) and how many it has (0xD8DC0C).</summary>
        public int TravelFlags { get; private set; } = -1;
        public int TravelDone { get; private set; } = -1;
        public int TravelLegs { get; private set; } = -1;
        /// <summary>(1.2.5) The world map's test of a character in the party (0x344134, its instruction
        /// 4), the party's units it reads (0x11A7D10: 54 of 0x258 bytes) and the pointer it reads
        /// (0x3CD9B10, the script reader's ScriptMode), whose number at + 8 says how it tests.</summary>
        public int PartyTest { get; private set; } = -1;
        public int Party { get; private set; } = -1;
        public int PartyMode { get; private set; } = -1;
        /// <summary>(1.2.5) The world map screen's showing of a place and its marker (0x15AE14: the screen,
        /// the place's state, the place): the state (16 bytes: its marker 0 none, 1 Quest, 2
        /// MidwayPoint, 3 Next; its job icon at 4; shown at 8; its marker's Loop at 9) kept at the
        /// screen + MarkerStates + place x 16, the place's piece of the layout at the screen +
        /// MarkerPieces + place x 24; places 0 to 47.</summary>
        public int MarkerState { get; private set; } = -1;
        public const int MarkerStates = 0x9C8, MarkerPieces = 0x208, MarkerStateSize = 16, MarkerPieceSize = 24;
        /// <summary>(1.2.5) The layouts' finding of a piece's child piece by its name (0x4091AC: the
        /// piece, a name), and of a box in a piece by its name (0x3F0794, which it calls first: the
        /// piece's tree, a name). A name is the game's string: its characters, then its number (0
        /// is looked for by its characters).</summary>
        public int ChildPiece { get; private set; } = -1;
        public int BoxNamed { get; private set; } = -1;
        /// <summary>(1.2.5) What the world map screen's change of a texture calls (0x15EC04, the game's
        /// own change of the walking Ramza's picture): the texture parts made ready (0x3FBE3C: the
        /// screen's layouts at + 0x18, the parts' name "UITextureParts://...", 0), a string made from
        /// characters (0x3D87BC), one string given another (0x3D87F4), one let go (0x3D8D1C: the
        /// strings' pool, its number), and where the pool's pointer is (0x3CDA2A0).</summary>
        public int PartsReady { get; private set; } = -1;
        public int StringMake { get; private set; } = -1;
        public int StringAssign { get; private set; } = -1;
        public int StringRelease { get; private set; } = -1;
        public int StringPool { get; private set; } = -1;
        /// <summary>(1.3.0) The world map screen's setup of its places' pieces (0x159304: the screen; the
        /// screen's own method, from 0x15EA90): its layouts' root, MapAll, Route and Bases found, then, for
        /// each place 0 to 47 with a name in the Town table, its piece ("Base" and the name for a town,
        /// "Point" and it for a battle ground) kept at the screen + MarkerPieces + place x 24 (its piece at
        /// + 0, its box at + 8, whether it is a town at + 0x14).</summary>
        public int MapSetup { get; private set; } = -1;
        public const int PieceBox = 8, PieceTown = 0x14;
        /// <summary>(1.3.0) The layouts' copy of a box (0x3FAD88: the screen's layouts, the box, whether the
        /// tracks of the piece holding it that name it are copied too): a new box of its kind, a reference's
        /// piece copied with it (its boxes, its animations) under a name of its own, as the game's own code
        /// copies boxes it shows more than once (21 places call it). What that code does with a copy, the
        /// helper does: moves it (0x3EF684: the box, x, y), puts it in a layer (0x3F0654: the layer, the
        /// box, the box it follows or 0) and plays its animations (0x409824: the piece, a name, the frame,
        /// -1 its last, as the screen shows a place; 0x40996C: every animation of a piece stopped).</summary>
        public int PieceCopy { get; private set; } = -1;
        public int PieceMove { get; private set; } = -1;
        public int PieceAdd { get; private set; } = -1;
        public int AnimationPlay { get; private set; } = -1;
        public int AnimationsStop { get; private set; } = -1;
        /// <summary>(1.20.0) One animation of a piece stopped by its name (0x409ECC: the piece, the name's string), as
        /// the game's two-way play (0xF638C) stops the other before it plays one: the call every animation's stopping
        /// makes (at its AnimationsStopOne).</summary>
        public int AnimationStop { get; private set; } = -1;
        /// <summary>(1.4.0) A box sized (0x3EF6B4: the box, its width, its height): its size at + 0x40 and + 0x44,
        /// made to be drawn again (+ 0x95), its middle kept half its size unless fixed (+ 0x8E); what the game's
        /// animations call to size a box. The mods' roads' pictures are sized to theirs.</summary>
        public int BoxSize { get; private set; } = -1;
        /// <summary>(1.5.0) The world map's travel along roads (Travel.cs): the path search (0x2471FC: from, to; the
        /// fewest roads, then the shortest, over the roads shown, 16 at most), its count of roads taken (cmp dword [rip
        /// + x], 16 at + 0x1D: 0xD49A98), its table of the program's 51 roads (lea r14, [rip + x] at + 0x31:
        /// 0x684980), its read of whether a road is shown (lea ecx, [rbx + 0x22C]; call x at + 0x92: the variables'
        /// read, 0x2E9898) and its loop to 51 (cmp ebx, 0x33; jl x at + 0x1C7); the walk's
        /// setup of a road (0x341A0C), its table (lea r8, [rip + x] at + 9); the travel's read of its last road's
        /// record when it stops short (0x247931 in 0x2477C8: mov rcx, [r8 + rax*8 + x] at + 0x23, x the table from the
        /// program's start, r8 its start); and the world map's test of a place shown (0x1DF4F0: -, the place).</summary>
        public int PathSearch { get; private set; } = -1;
        public int RoadRecords { get; private set; } = -1;
        public int VariableGet { get; private set; } = -1;
        public int WalkSetup { get; private set; } = -1;
        public int LastRoad { get; private set; } = -1;
        public int PlaceShown { get; private set; } = -1;
        /// <summary>(1.5.0) The path search's count of roads taken (cmp dword [rip + x], 16 at + 0x1D: 0xD49A98) and
        /// their cost so far (mov r9d, [rip + x] at + 0xE9: 0xD49A9C), each written where it goes on (mov [rip + x],
        /// r10d at + 0x1A0; mov [rip + x], r9d at + 0x1A9), which the helper's answer reads (Ways).</summary>
        public int SearchDepth { get; private set; } = -1;
        public int SearchCost { get; private set; } = -1;
        public const int PathSearchTable = 0x31, PathSearchShown = 0x8C, PathSearchCall = 0x92, PathSearchLoop = 0x1C7,
                         PathSearchLoopStart = 0x42, PathSearchDepth = 0x1D, PathSearchCost = 0xE9,
                         PathSearchDepthOn = 0x1A0, PathSearchCostOn = 0x1A9, WalkSetupTable = 9, LastRoadPath = 0x1C,
                         LastRoadTable = 0x23;
        /// <summary>(1.6.0) The random battles on arriving at a battle ground (Travel.cs): the roll (0x248BE4: the
        /// place, the road arrived along, its low byte, and whether a battle is forced), which looks for the road among
        /// the place's three entrances in its table (lea r12, [rip + x] at + 0x34: 0x7B69D0; the 19 battle grounds from
        /// 24, 72 bytes each, three entrances of 24, the road the first byte: where the party deploys, four tiers of the
        /// chance by the story's progress, eight enemy formations, the map), none found no battle; and its two calls:
        /// the travel step's as Ramza arrives (0x2485B7), and the world map's as the battle ground he stands on is
        /// chosen, a battle forced (0x2D134A).</summary>
        public int BattleRoll { get; private set; } = -1;
        public int BattleTable { get; private set; } = -1;
        public int BattleRollArriving { get; private set; } = -1;
        public int BattleRollForced { get; private set; } = -1;
        public const int BattleRollTable = 0x34, BattleGroundFirst = 24, BattleGrounds = 19, BattleGroundBytes = 72,
                         BattleEntrances = 3, BattleEntranceBytes = 24;
        /// <summary>(1.17.0) Where the roll keeps what it chose, each 32 bits (`dev/research/sidequests/README.md`, A
        /// battle on a mod's battle ground): the deployment squad (0x200 plus its entrance's byte, kept as soon as the
        /// road is found: 0xD49468), the battle (an enemy formation of its eight: 0xD494C8) and the map (0xD49464), kept
        /// as it returns 1. The travel step and the world map's battle on the ground it stands on then hand the battle
        /// to the encounter check (0x2477C8) and the random battle's setup (0x248254: variable 50 the battle, 52 one
        /// squad, 53 the squad, the next map the map). Each found once, within the roll.</summary>
        public int RandomSquad { get; private set; } = -1;
        public int RandomBattle { get; private set; } = -1;
        public int RandomMap { get; private set; } = -1;
        /// <summary>(1.17.0) What wasn't found of what a mod's battle ground's own random battles need (the roll's
        /// three keeps, besides what the mods' roads' random battles need).</summary>
        public List<string> MissingForGroundBattles { get; } = new List<string>();
        public bool GroundBattles => RoadBattles && MissingForGroundBattles.Count == 0;

        /// <summary>What wasn't found, and why: the five every quest needs, the two a quest's own
        /// battles need, and (1.2.2) the travel check, without which a quest's event waiting where
        /// you stand stops travel on.</summary>
        public List<string> Missing { get; } = new List<string>();
        public List<string> MissingForBattles { get; } = new List<string>();
        public List<string> MissingForTravel { get; } = new List<string>();
        /// <summary>(1.2.4) What wasn't found of the travel's state, without which a start that
        /// waits until its place is chosen stops a travel passing through, as the game's do.</summary>
        public List<string> MissingForPassing { get; } = new List<string>();
        /// <summary>(1.2.5) What wasn't found of what the quests' markers need.</summary>
        public List<string> MissingForMarkers { get; } = new List<string>();
        /// <summary>(1.3.0) What wasn't found of what the mods' own places need (the layouts' finding of a
        /// piece and the change of a picture among it, which the markers need too).</summary>
        public List<string> MissingForPlaces { get; } = new List<string>();
        /// <summary>(1.4.0) What wasn't found of what the mods' own roads need (all the places need, the screen's
        /// keeping of its Route piece, a box sized).</summary>
        public List<string> MissingForRoads { get; } = new List<string>();
        /// <summary>(1.5.0) What wasn't found of what travel along the mods' roads needs.</summary>
        public List<string> MissingForJourneys { get; } = new List<string>();
        /// <summary>(1.6.0) What wasn't found of what random battles on arriving by the mods' roads need.</summary>
        public List<string> MissingForRoadBattles { get; } = new List<string>();

        // --- (1.7.0) a mod's own place as a destination ------------------------------------------------------

        /// <summary>(1.7.0) The game's places' records (0x693530, the PlayStation's location records: 4 bytes a
        /// place, its picture set + 1 at + 2, its menu's kind at + 3; 44 of them, then other data): the table, its
        /// reads by the place (movzx ebx, byte [base + place*4 + table + 2]: each instruction's start) and the lea
        /// of its + 3 (the menu's entries, lea rcx, [rip + table + 3]).</summary>
        public int LocationRecords { get; private set; } = -1;
        public List<int> LocationRecordReads { get; } = new List<int>();
        public int LocationRecordLea { get; private set; } = -1;
        /// <summary>(1.7.0) The world map's dots (0xD4AFD0, the PlayStation's g_world_map_dots: 52 bytes a place, 43 of
        /// them, built by the world map's setup): the array, its rip-relative leas (each instruction's start, 7 bytes)
        /// and its reads by a register and a distance from the program's start (each instruction's start and where
        /// its distance is).</summary>
        public int Dots { get; private set; } = -1;
        public List<int> DotLeas { get; } = new List<int>();
        public List<(int At, int Distance)> DotReads { get; } = new List<(int At, int Distance)>();
        /// <summary>(1.7.0) The world map screen's reads of a place's row (its 48 at + 0x208): its position of a place
        /// (0x15C9BC), the cursor put on a place (0x15CA54), a place's distance from the cursor (its bound at 0x15CD18,
        /// its row's read at 0x15CD6B), the marker arrived (two reads, 0x15CEAA and 0x15CED8), the handler of a piece's
        /// events (0x15A008), the help of the place under the cursor (its bound at 0x15B99C, reads at 0x15BA2C and
        /// 0x15BA72), the marker put on its place (0x15A7C0).</summary>
        public int PlacePosition { get; private set; } = -1;
        public int CursorAtPlace { get; private set; } = -1;
        public int DistanceBound { get; private set; } = -1;
        public int DistanceRead { get; private set; } = -1;
        public int ArrivedFirst { get; private set; } = -1;
        public int ArrivedSecond { get; private set; } = -1;
        public int PieceEvents { get; private set; } = -1;
        public int HelpBound { get; private set; } = -1;
        public int HelpKind { get; private set; } = -1;
        public int HelpKindAgain { get; private set; } = -1;
        public int MarkerPlace { get; private set; } = -1;
        /// <summary>(1.7.0) The world map screen's two allocations (its map, 0xDB0 bytes, at 0x157100; its frame menu,
        /// 0xF70, at 0x1571AB) and the constructor both call (0x159020); its switch of its places' collision boxes
        /// (0x15CB04) with the two functions it calls (a box of a kind, 0x3F081C; a box refreshed, 0x3EFF08); the
        /// setting of a box's text (0x3F113C, as the location info sets its name).</summary>
        public int MapAlloc { get; private set; } = -1;
        public int FrameAlloc { get; private set; } = -1;
        public int ScreenCtor { get; private set; } = -1;
        public int CollisionSwitch { get; private set; } = -1;
        public int BoxOfKind { get; private set; } = -1;
        public int BoxRefresh { get; private set; } = -1;
        public int SetText { get; private set; } = -1;
        /// <summary>(1.7.1) A place's distance from the cursor (0x15CD08: the screen, the place; more than 0 within its
        /// reach), the place nearest the cursor (0x15CC70, over the 48 rows), and the pad's focus of that place (in
        /// 0x15BE8C: its call of the nearest, then three reads of its row).</summary>
        public int Distance { get; private set; } = -1;
        public int Nearest { get; private set; } = -1;
        public int NearestFocus { get; private set; } = -1;
        /// <summary>(1.23.1) Zodi's test 52: travelling to Old Quarry (place 69) stopped the game at 0x342116. As Ramza
        /// arrives at a place, the travel's step keeps it plus one (0xD496C4: at 0x2486E3 and 0x24772D, then waits for
        /// the frames to draw, 0x343564), and the PlayStation's world map draws that place's name (0x3433FC, its only
        /// reader: the sprite 0x36 plus it, of the sprites' table 0x693A50, 0x342070) at its dot. The table holds 123
        /// sprites: places 0 to 47's names at 55 to 102, then other sprites to 122, so a mod's place from 68 on read
        /// past it (place 69's 124 is no sprite: its frames' read faults). Found: that read (ArrivalName, `mov r11d,
        /// [rip + the place plus one]`, 7 bytes; the place plus one at ArrivalNameValue), which the helper gives
        /// native code holding a mod's place's (48 on) as none, so no name is drawn there.</summary>
        public int ArrivalName { get; private set; } = -1;
        public int ArrivalNameValue { get; private set; } = -1;
        /// <summary>(1.23.2) Zodi's test 53: standing on Old Quarry (place 69), choosing it stopped the game at
        /// 0x342116 again. The menu's opening (0x344B68, its place in r14) makes the PlayStation menu's name of its
        /// place a sprite of its own (a slot of the sprites' list, 0xD4C4B0), its sprite 0x37 plus the place, of the
        /// same table of 123: a place from 68 on past it. Found: that `lea eax, [r14 + 0x37]` and the instruction after
        /// it (MenuName, 16 bytes), which the helper gives native code giving a mod's place (48 on) the game's blank
        /// sprite (BlankSprite, 122: no piece to draw, but in the game's mode 2, whose dates draw it), so no name of
        /// another place, and none past the table, is drawn.</summary>
        public int MenuName { get; private set; } = -1;
        public List<string> MissingForDestinations { get; } = new List<string>();
        /// <summary>(1.7.1) The game's load of a save's state (0x21B0E8) and the variables it copies into (0xD40060):
        /// what a save standing on a mod's place no mod gives now needs to go on from a place of the game's.</summary>
        public int SaveLoad { get; private set; } = -1;
        public int SaveBank { get; private set; } = -1;
        public List<string> MissingForSaveFallback { get; } = new List<string>();
        /// <summary>(1.35.0) The party the game's load of a save fills (0x11A7D10: Framework.RosterUnits of
        /// Framework.RosterUnitBytes), what its units wear looked at as a save loads; -1, and why in MissingForRoster,
        /// when not found.</summary>
        public int Roster { get; private set; } = -1;
        public List<string> MissingForRoster { get; } = new List<string>();
        /// <summary>(1.15.0) What a quest's tavern rumors need (dev/research/sidequests/tavern_rumors.py): the taverns'
        /// test of a rumor told (0x36F53C: its key and a place; every caller's, the list's, the town's and the news's),
        /// which the helper answers for the quests' rumors; the taverns' list (0x36EE50) the save's two bytes a rumor
        /// (0x11A7299, the first 0 once read) and the keys it lists (0 to 63).</summary>
        public int RumorTest { get; private set; } = -1;
        public int RumorsRead { get; private set; } = -1;
        public int RumorKeys { get; private set; } = -1;
        /// <summary>(1.29.0) The tavern's agent (0x19D548: its screen, its state, an action, a key), whose action 0 marks
        /// a rumor read (the key's first byte 0, at 0x19D76A), which the helper hooks to set a quest's rumor's flag as it
        /// is read, its keys being given as the game starts.</summary>
        public int RumorAgent { get; private set; } = -1;
        public List<string> MissingForRumors { get; } = new List<string>();
        /// <summary>(1.31.0) What a quest's reward needs (dev/research/sidequests/rewards.py): the game's own giving of
        /// an event's item to the bag (0x101058: an item, 1 to 260, the bag's count of it added to, 99 at the most less
        /// the copies the party wears, the rest sold; the mods' items too once their room is made, 1.26.0) and its add to
        /// the war funds (0x284684, which the giving calls for an item sold: variable 0x2C, stopped at 99,999,999).
        /// Else said (MissingForRewards).</summary>
        public int ItemGive { get; private set; } = -1;
        public int WarFundsAdd { get; private set; } = -1;
        public List<string> MissingForRewards { get; } = new List<string>();
        /// <summary>(1.33.0) What a quest's unit's own name needs (Zodi's choice of 5 November: "As a renamed unit";
        /// dev/research/sidequests/unit_names.py): the game's making of a battle's unit from its battle file's entry
        /// (0x275CA4: the unit, the entry, a number, a mode, its OverrideEntryData row), whose unit's setup ends by
        /// jumping to the name's assignment (0x277CF0: a unit not from the party, + 2 0xFF, given a name and its own
        /// text, + 0x14C, cleared), which the helper's own text follows. Else said (MissingForNames).</summary>
        public int UnitMade { get; private set; } = -1;
        public List<string> MissingForNames { get; } = new List<string>();
        /// <summary>(1.34.0) What a mod's road shown and grayed with its places needs (Zodi's choices of 5 November: "Once
        /// both its places show", "Gray with its places"; dev/research/sidequests/road_looks.py): the game's test of a
        /// place shown (0x1DF4F0: variable 512 + the place for places 0 to 42, the remaster's for 44 to 46; found here by
        /// itself, as PlaceShown, the same, is the journeys' and goes with them), and the
        /// screen's graying of a place as it shows it (0x15AEF5: its Town row, sheet 0x34, by the rows' lookup 0x3DBC74;
        /// the row's situation, + 0x28, tested by 0xFF8A4: Color_Grayout while it holds), with the screen's showing of
        /// a place (MarkerState, 0x15AE14), which the story's drawing of a place calls while the world map is up. Else
        /// said (MissingForRoadLooks).</summary>
        public int PlaceTest { get; private set; } = -1;
        public int TownRow { get; private set; } = -1;
        public int Situation { get; private set; } = -1;
        public List<string> MissingForRoadLooks { get; } = new List<string>();
        /// <summary>(1.18.0) What a mod's town's menu needs besides its record (dev/research/sidequests/town_menus.py):
        /// the Outfitter's stock (0x288E54: a unit, a town, a list's category, the list, how it is checked against
        /// the unit, sorted or not), which the helper hooks to list a mod's town's own items, and the shops' masks it
        /// reads (0x67F890, from its lea of their second bytes). A mod's town's tavern offers no errand without a hook:
        /// each of the game's 96 names one of its 15 towns.</summary>
        public int Stock { get; private set; } = -1;
        public int ShopMasks { get; private set; } = -1;
        public List<string> MissingForTownMenus { get; } = new List<string>();
        /// <summary>(1.19.0) What a mod's town's own art and own picture in its menu need: the base art's
        /// path by its number (0xFC1C0: the out buffer, the number, its size; the thumbnail's, from a Town row's
        /// + 0x1C), which the helper hooks for its own numbers (from 1000); the menu's town picture (0x158E30: -, the
        /// piece, the place, its Town row: plays TexChange of the row's + 0x2C), which the helper hooks for a mod's
        /// town with its own picture; the UI's root (0x3CD9DA8), from which the menu opener finds its UI object
        /// (+ 0x10, + 0xA0, + 0x48; its layouts at + 0x18, its town picture's piece at + 0x48).</summary>
        public int BaseArt { get; private set; } = -1;
        public int MenuIcon { get; private set; } = -1;
        public int UiRoot { get; private set; } = -1;
        public List<string> MissingForMenuArt { get; } = new List<string>();
        /// <summary>(1.21.0) What a mod's dungeon needs (Zodi's list, his seventh: a place like Midlight's Deep): a
        /// place's settlement menu's entries (0x3449B0: ecx the place, rdx where its entries go, its count returned;
        /// place 22 its floors, 0xB8ED on), which the helper hooks for a mod's dungeon; in the menu's opening (0x344B68,
        /// r14d the place) its two tests of the Deep (0x345056: its list's block, the count read 10 on, a town's path
        /// the jne's target, the block copied to the list at 0x3450F1; 0x345619: the Deep's screen, 9, else a town's,
        /// 3), and in its choosing (0x3457E8, the place read from 0xD493E8) a third; the floor chosen (0x3459A3: the
        /// variable 92 set, the menu closed, the place's chains asked at 0x3459C8, 0x343AF8, its way out at 0x345B18);
        /// the random battle's setup (0x248254, reading the roll's keeps); and the Deep's list's two reads of a floor's
        /// row (0x16173E its name, 0x161CA0 its words; DeepDungeon, sheet 0x65, by 0x3DBC74). Else said
        /// (MissingForDungeons) and none kept.</summary>
        public int Entries { get; private set; } = -1;
        public int DungeonBlock { get; private set; } = -1;
        public int DungeonTown { get; private set; } = -1;
        public int DungeonCopy { get; private set; } = -1;
        public int DungeonScreen { get; private set; } = -1;
        public int DungeonHandler { get; private set; } = -1;
        public int CurrentPlace { get; private set; } = -1;
        public int FloorCall { get; private set; } = -1;
        public int Chains { get; private set; } = -1;
        public int FloorOut { get; private set; } = -1;
        public int RandomSetup { get; private set; } = -1;
        public int RowTitleCall { get; private set; } = -1;
        public int RowInfoCall { get; private set; } = -1;
        public int RowLookup { get; private set; } = -1;
        public List<string> MissingForDungeons { get; } = new List<string>();
        /// <summary>(1.23.0) Zodi, test 49: "there was a white flash when transitioning to the battle as if it were a
        /// random battlefield battle. For the dungeon in vanilla it is straight to black to the battle." The random
        /// battle's setup (0x248254) queues the world map's transition (0x2CC2E0, ecx its kind: the command 0x23 put last
        /// in the world map's list of commands, 0xD4C948, by its count at 0xD8DBA0, its kind at + 0x20 of its record, from
        /// 0xD8D8C0, 0x5C bytes each). The transition's handler (0x2CC42C) flashes white for the kinds 0 (a random
        /// battle's) and 1, and leaves the world map at once for 2 (its test of + 0x20 against 2, 0x2CC52A), as 33 of the
        /// game's world events that load an event ask (their transition 2); Midlight's Deep's floors leave at once their
        /// own way (0x345AFA: the state's bit 0 turned). Found: the queue's count, list and kinds (TransitionCount,
        /// TransitionCommands, TransitionKinds: where the first record's kind is); else said (MissingForInstantBattles)
        /// and a mod's dungeon's battle starts as a random battle's.</summary>
        public int TransitionCount { get; private set; } = -1;
        public int TransitionCommands { get; private set; } = -1;
        public int TransitionKinds { get; private set; } = -1;
        public List<string> MissingForInstantBattles { get; } = new List<string>();
        /// <summary>(1.23.0) The transition's command, its record's size, and the kind that leaves at once.</summary>
        public const int TransitionCommand = 0x23, TransitionRecord = 0x5C, InstantTransition = 2;
        /// <summary>(1.25.0) Zodi, 2 November: "in Midlight's Deep Dungeon when the player reaches the final floor "END" for
        /// the first time a specific battle occurs and a scripted event occur at the beginning and end of the battle
        /// after they defeat the boss ... That first boss battle that plays the first time you play that floor never
        /// happens again. Do we support this functionality as well? If not we should." (The Deep's END: its world
        /// events' kind 30 with the event 111 while variable 149 is 0, whose setup fights the boss's battle by its rules,
        /// 36; then 114.) A quest's start may wait at a mod's dungeon's floor (his choices "Boss again until won" and
        /// "Yes, it counts"): the floor chosen while its conditions hold starts its event as a place starts the event
        /// its chains loaded (0x247E10, ecx which: the event at 0xD493CC plus it times 4, its transition's kind at
        /// 0xD493D0), called once a place's event has no prompt (0x248076) or its prompt is answered yes (0x247697):
        /// the last command's sprite hidden, variable 0x27 given the event, its transition queued (0x2CC2E0), the
        /// state's bit 13 set. The floor chosen closed the menu first (0x345EFC: its command taken off the queue, bit 13
        /// cleared), so the queue is the place's as a place's event starts. The battle then loads by the event's setup
        /// (0x2FB7C8: its record found by variable 0x27, its map, units, deploy areas and rules), as a quest's battle at
        /// a place; the random battle's way would give it a random battle's weather and music (0x304330, its state 11).
        /// Found: it (EventStart), the event it loads (LoadedEvent) and its kind (LoadedKind), the queue's count it
        /// reads (QueueCount, the transition's); else said (MissingForFloorStarts) and a start waiting at a floor is
        /// left out.</summary>
        public int EventStart { get; private set; } = -1;
        public int LoadedEvent { get; private set; } = -1;
        public int LoadedKind { get; private set; } = -1;
        public int QueueCount { get; private set; } = -1;
        public List<string> MissingForFloorStarts { get; } = new List<string>();
        /// <summary>(1.23.0) Zodi, test 49: "Our new modded in locations are not appearing in the location list. There
        /// are three types, Settlements, Battlegrounds, and Miscellaneous." The world map's location list
        /// (UIAddonFFTOWorldMapBaseList, the world map frame's + 0x50) is built at 0x36E5DC over places 0 to 47 only (its
        /// loop's `cmp ebx, 0x30`), each shown place (0x1DF4F0) an entry of 0x40 bytes made at rsp + 0x40 (its place at
        /// + 0x34, its sort at + 0x38: the Town row's + 0x20; 3 at + 0x33 the story's next place, 2 a midway one; the
        /// Poachers' Den at + 0x3E; Ramza's place at + 0x3F) and put last in its tab's list (the list's + 0x6A0, 0x20
        /// each, by its Town row's kind, + 0x24: 0 Settlements, 1 Battlegrounds, 2 Miscellaneous; its end at + 0x10, its
        /// room's end at + 0x18, a full one grown by 0x1CBF50); then each tab sorted by its entries' sort, then place.
        /// Found: the loop's end (ListEnd: its `mov rax, [the UI's root]` after it), the grow (ListGrow), the row lookup
        /// it calls (ListRowLookup); else said (MissingForLocations) and the mods' places aren't listed.</summary>
        public int ListEnd { get; private set; } = -1;
        public int ListGrow { get; private set; } = -1;
        public int ListRowLookup { get; private set; } = -1;
        /// <summary>(1.23.1) Zodi's test 52: Hermit's Rest, a mod's town with a menu, under Settlements, showed the
        /// last town's panel. The panel (0x1607D4, as the cursor rests on an entry) fills its town part (+ 0x700: the
        /// place's art and words, its errands, the kinds its shop sells) only for a place whose Town row's + 0x31 is
        /// set, else its plain part (+ 0x718), which a Settlements entry doesn't show; and the list makes a town's
        /// entry's kinds (its + 0x10 on, one byte a kind, 35) from its shop: each of the Outfitter's five lists (1 to 4,
        /// and 7) asked of the stock into the items' list (0x1811470), each item's kind (+ 5 of its data, 0x2B8C44)
        /// marked. Found: the items' list (ListItems) and the item's data (ListItem), the stock the list asks the
        /// Outfitter's.</summary>
        public int ListItems { get; private set; } = -1;
        public int ListItem { get; private set; } = -1;
        public List<string> MissingForLocations { get; } = new List<string>();
        /// <summary>(1.23.0) The frame's location list (+ 0x50) and main map (+ 0x40: its places' rows, a mod's place's
        /// at Destinations.ScreenRows); the list's tabs (+ 0x6A0, 0x20 each: their end at + 0x10, their room's at
        /// + 0x18); an entry (0x40 bytes, made at rsp + 0x40): its tab's marks at + 0x33, its place at + 0x34, its sort
        /// at + 0x38, the third of its marks at + 0x3D, the Poachers' Den at + 0x3E, Ramza's place at + 0x3F; the story's
        /// next place and a midway one at rsp + 0x30 and + 0x34.</summary>
        public const int FrameList = 0x50, FrameMap = 0x40, ListTabs = 0x6A0, TabSize = 0x20, TabEnd = 0x10,
                         TabRoom = 0x18, EntrySize = 0x40, EntryAt = 0x40, EntryNext = 0x33, EntryPlace = 0x34,
                         EntrySort = 0x38, EntryUnmarked = 0x3D, EntryDen = 0x3E, EntryHere = 0x3F, NextPlaceAt = 0x30,
                         MidwayPlaceAt = 0x34;
        /// <summary>(1.23.0) Zodi, test 49: "After selecting the Old Quarry the dungeon UI still said "Midlight's
        /// Deep", "About Midlight's Deep", and "Exit Midlight's Deep"". The Deep's list (the frame's + 0x60) shows the UI
        /// text 1620 as its title (worldmap_deep_dungeon_ver02.uib's DeepDungeonList, Title, Text00), its Thumbnail
        /// (+ 0x268) the texture base_18_uitx (the Deep's Town row's art, 18), and the button guide 0xBBD (3005: "Exit
        /// Midlight's Deep", 1607; "Enter"; "About Midlight's Deep", 1614, the T key, which opens the guide 0xE6's page:
        /// "Midlight's Deep is a subterranean labyrinth ..."). Found: the UI text by its number (0x3DBE88), the row of
        /// two keys (0x3DBCE4: the guide's page, GuidePage, sheet 0xBC, read at 0x1A798E), the button guide shown
        /// (0xEB65C, as the frame's mode 4 shows the Deep's: 0x1579E7), the About key's guide (0xEE118, the guide 0xE6,
        /// called at 0x157E5A), a place's name by its number (0xFB44C), and a thumbnail's art set by its path (0x158D98,
        /// the menu's own: the UI, its picture, the base art's path); else said (MissingForDungeonLooks) and a mod's
        /// dungeon's list shows the Deep's words and art.</summary>
        public int UiText { get; private set; } = -1;
        public int TwoKeyRow { get; private set; } = -1;
        public int GuideShow { get; private set; } = -1;
        public int DeepGuide { get; private set; } = -1;
        public int AboutOpen { get; private set; } = -1;
        public int AboutGuide { get; private set; } = -1;
        public int PlaceNameText { get; private set; } = -1;
        public int ArtSetter { get; private set; } = -1;
        /// <summary>(1.23.0) A text box made again from its number (0x3F1234: the box; its UI text through 0x3DBE88), as
        /// the button guide makes its rows'.</summary>
        public int TextRemake { get; private set; } = -1;
        public List<string> MissingForDungeonLooks { get; } = new List<string>();
        /// <summary>(1.23.0) The frame's Deep list (+ 0x60) and its mode (+ 0xE4: 4 while the Deep's list is up); the
        /// list's Thumbnail (+ 0x268); a text's number (+ 0xF8) and its "made again" byte (+ 0x13C), a box's kind of
        /// text (3); the Deep's list's title, Exit and About texts (1620, 1607, 1614: the guide's row 2); the Deep's
        /// name's number (1230); the guide's pages' sheet (0xBC).</summary>
        public const int FrameDeep = 0x60, FrameMode = 0xE4, DeepListMode = 4, DeepThumbnail = 0x268, TextNumber = 0xF8,
                         TextRemade = 0x13C, TextKind = 3, TitleText = 1620, ExitText = 1607, AboutText = 1614,
                         AboutRow = 2, DeepNameText = 1230, PageSheet = 0xBC;
        /// <summary>(1.24.0) The world map's prompt to enter the place Ramza stands at (Zodi's test 54: "standing on Old
        /// Quarry it says "Enter Settlement" and standing on Midlight's Deep it says "Enter Midlight's Deep""; his
        /// answer "Enter Old Quarry"). The help of the place under the cursor (0x15B970) gives, with the cursor on
        /// Ramza's place, the Deep (0x16) its button guide 0xBC5, whose fifth row is the UI text 1626 ("Enter
        /// Midlight's Deep"), and a place whose screen row's kind is 0 (a town's, a mod's dungeon's too) the guide
        /// 0xBC1, whose fifth row is 1618 ("Enter Settlement"), the guides' other rows the same; a guide shown
        /// (0xEB65C, 0x13D5F4) makes its rows' words again unless it is the one shown already.</summary>
        public const int SettlementText = 1618, EnterDeepText = 1626;

        public bool All => Missing.Count == 0;
        public bool Battles => MissingForBattles.Count == 0;
        public bool Travel => MissingForTravel.Count == 0;
        public bool Passing => MissingForPassing.Count == 0;
        public bool Markers => MissingForMarkers.Count == 0;
        public bool NewPlaces => MissingForPlaces.Count == 0;
        public bool NewRoads => MissingForRoads.Count == 0;
        public bool Journeys => MissingForJourneys.Count == 0;
        public bool RoadBattles => MissingForRoadBattles.Count == 0;
        public bool Destinations => MissingForDestinations.Count == 0;
        public bool SaveFallback => MissingForSaveFallback.Count == 0;
        public bool Rumors => MissingForRumors.Count == 0;
        public bool Rewards => MissingForRewards.Count == 0;
        public bool Names => MissingForNames.Count == 0;
        public bool RoadLooks => MissingForRoadLooks.Count == 0;
        public bool TownMenus => MissingForTownMenus.Count == 0;
        public bool MenuArt => MissingForMenuArt.Count == 0;
        /// <summary>(1.21.0) A mod's dungeon: its own sites found, and a mod's places and battle grounds' random
        /// battles (the setup reads the roll's keeps).</summary>
        public bool Dungeons => MissingForDungeons.Count == 0 && Destinations && GroundBattles;
        /// <summary>(1.23.0) A mod's dungeon's battle started at once (its sites found, and a dungeon's).</summary>
        public bool InstantBattles => MissingForInstantBattles.Count == 0 && Dungeons;
        /// <summary>(1.25.0) A quest's start waiting at a mod's dungeon's floor (its sites found, and a dungeon's).</summary>
        public bool FloorStarts => MissingForFloorStarts.Count == 0 && Dungeons;
        /// <summary>(1.23.0) The mods' places in the world map's location list (its sites found, and a mod's places').</summary>
        public bool Locations => MissingForLocations.Count == 0 && Destinations;
        /// <summary>(1.23.0) A mod's dungeon's list's words, art and About page (its sites found, a dungeon's and the
        /// menus' art's).</summary>
        public bool DungeonLooks => MissingForDungeonLooks.Count == 0 && Dungeons && MenuArt;

        // (1.21.0) A mod's dungeon's sites (FindDungeons): the entries' function from its start (its first 15 bytes
        // not looked at: a hook's jump); the opening's block (its test 10 on) and the list's copy; its screen; the
        // choosing's test; the floor chosen (its call 0x25 on, its way out 0x14 on); the random battle's setup; the
        // two reads of a floor's row (their calls 0x0E and 8 on).
        const string EntriesBytes =
            "48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18 57 48 83 EC 20 48 63 E9 48 8B FA 83 FD 16 75 ?? 8D 4D 4F E8";
        const int EntriesPrologue = 15;
        const string DungeonBlockBytes =
            "45 8D 54 24 09 45 8D 6C 24 03 41 83 FE 16 0F 85 ?? ?? ?? ?? 44 8B 84 3B ?? ?? ?? ?? 33 C0 48 89 45 1B";
        const string DungeonCopyBytes = "49 8B 41 10 48 8B 88 A0 00 00 00 48 8B 49 60 48 85 C9 74 ?? 0F 10 45 17";
        const string DungeonScreenBytes = "41 83 FE 16 B8 09 00 00 00 44 0F 44 E8 48 81 C1 30 05 00 00";
        const string DungeonHandlerBytes = "83 3D ?? ?? ?? ?? 16 49 8B C3 48 8B 0D ?? ?? ?? ?? 49 0F 44 C7 0F 94 C2";
        const string FloorBytes = "8D 96 13 FF FF FF B9 5C 00 00 00 E8 ?? ?? ?? ?? 33 D2 48 8B CB E8 ?? ?? ?? ?? 8B 0D "
                                  + "?? ?? ?? ?? BA 20 00 00 00 E8 ?? ?? ?? ?? 85 C0 0F 84";
        const string FloorOutBytes = "41 33 C4 40 80 C6 13 89 05 ?? ?? ?? ?? 40 88 35 ?? ?? ?? ?? E9";
        const string RandomSetupBytes = "48 83 EC 28 E8 ?? ?? ?? ?? 8B 05 ?? ?? ?? ?? B9 32 00 00 00 8B 15 ?? ?? ?? ?? "
                                        + "0F BA 2D ?? ?? ?? ?? 0F 89 05";
        const string RowTitleBytes = "8B 92 24 02 00 00 B9 65 00 00 00 45 8B F8 E8";
        const string RowInfoBytes = "48 8B D9 B9 65 00 00 00 E8 ?? ?? ?? ?? 48 85 C0";
        // (1.23.0) Test 49's findings' sites. The random battle's setup's call of its transition (xor ecx, ecx: kind 0);
        // the queue's block in the function it calls (its count read, the program's start in r8, the record's size,
        // the command 0x23 put, the count stored, the kind put: ecx kept in esi); the handler's test of kind 2.
        const string TransitionCallBytes = "33 C9 E8 ?? ?? ?? ?? 48 63 05";
        const string TransitionBytes = "48 63 15 ?? ?? ?? ?? 4C 8D 05 ?? ?? ?? ?? 48 6B C2 5C 41 C7 84 90 ?? ?? ?? ?? 23 00 "
                                       + "00 00 FF C2 89 15 ?? ?? ?? ?? 42 89 B4 00 ?? ?? ?? ??";
        const string InstantBytes = "83 79 20 02 75 ?? 8B 05 ?? ?? ?? ?? A8 08 0F 85";
        // (1.25.0) The world map's start of the event a place's chains loaded (its first 14 bytes not looked at: a
        // hook's jump, to its call's end): the queue's count read (+ 0xE), the program's start (+ 0x14), the last
        // command's sprite hidden, the event loaded read by which (+ 0x49, its place + 0x4C), variable 0x27 given it,
        // its kind read (+ 0x5A), the transition queued, the state's bit 13 set.
        const string EventStartBytes =
            "40 53 48 83 EC 20 48 63 D9 E8 ?? ?? ?? ?? 8B 05 ?? ?? ?? ?? 48 8D 0D ?? ?? ?? ?? 83 25 ?? ?? ?? ?? 00 FF C8 "
            + "48 63 D0 48 6B C2 5C C7 05 ?? ?? ?? ?? 01 00 00 00 48 63 84 08 ?? ?? ?? ?? 48 8D 14 C0 83 8C 91 ?? ?? ?? ?? "
            + "10 8B 94 99 ?? ?? ?? ?? B9 27 00 00 00 E8 ?? ?? ?? ?? 8B 0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 0F BA 2D ?? ?? ?? ?? 0D";
        public const int EventStartPrologue = 14, EventStartCountAt = 0x0E, EventStartBaseAt = 0x14,
                         EventStartLoadedAt = 0x4C, EventStartKindAt = 0x5A;
        public const int TransitionReach = 0x100, QueueReach = 0x200, TransitionBase = 7, TransitionCommandsAt = 0x16,
                         TransitionStore = 0x20, TransitionKindsAt = 0x2A;
        // The location list's loop's end: the UI's root read, Ramza's place tested, the list from the frame, the place's
        // Town row (sheet 0x34), its tab by its kind (+ 0x24, above 2 the first), the entry put last in its tab or the
        // tab grown, the loop's next place (cmp ebx, 0x30), the UI's root read again (ListEndAt, 7 bytes).
        const string ListBytes = "48 8B 05 ?? ?? ?? ?? 3B 1D ?? ?? ?? ?? 0F 94 44 24 7F 48 8B 48 10 48 8B 81 A0 00 00 00 48 "
                                 + "8B 78 50 48 85 FF 74 ?? 41 8B D7 B9 34 00 00 00 E8 ?? ?? ?? ?? 48 85 C0 74 ?? 83 78 24 "
                                 + "02 77 ?? 48 63 48 24 48 83 C1 35 48 C1 E1 05 48 03 CF EB ?? 48 8D 8F A0 06 00 00 48 8B "
                                 + "51 10 48 3B 51 18 74 ?? 0F 28 44 24 40 0F 11 02 0F 28 44 24 70 0F 11 4A 10 0F 11 52 20 "
                                 + "0F 11 42 30 48 83 41 10 40 EB ?? 4C 8D 44 24 40 E8 ?? ?? ?? ?? FF C3 83 FB 30 0F 8C ?? "
                                 + "?? ?? ?? 48 8B 05 ?? ?? ?? ??";
        public const int ListPlaceAt = 7, ListLookupAt = 0x2E, ListGrowAt = 0x85, ListEndAt = 0x95, ListEndLength = 7;
        // (1.23.1) The list's kinds of a town's shop: its first list (mov edi, 1), the items' list (lea r15, ListKindsItemsAt),
        // the fifth list 7, the stock asked (call, ListKindsStockAt), each item's data (call, ListKindsItemAt), its kind
        // (+ 5) below 0x23 marked in the entry (or byte [rsp + rax + 0x50], 1).
        const string ListKindsBytes = "BF 01 00 00 00 4C 8D 3D ?? ?? ?? ?? 44 0F B7 C7 44 88 74 24 28 B8 07 00 00 00 44 89 "
                                      + "74 24 20 83 FF 05 4D 8B CF 0F B7 D3 49 8B F6 66 44 0F 44 C0 83 C9 FF E8 ?? ?? ?? "
                                      + "?? 4C 63 C0 85 C0 7E 2E 41 0F B7 0C 77 B8 FF 03 00 00 66 23 C8 E8 ?? ?? ?? ?? 48 85 "
                                      + "C0 74 0F 80 78 05 23 73 09 0F B6 40 05 80 4C 04 50 01";
        public const int ListKindsItemsAt = 5, ListKindsStockAt = 0x33, ListKindsItemAt = 0x4C;
        /// <summary>(1.23.1) A Town row's town part (+ 0x31: the location panel's town part, as the game's towns'), an
        /// item's kind (+ 5 of its data), how many kinds an entry marks (0x23, from its + 0x10), the fifth list's
        /// number (7).</summary>
        public const int TownPart = 0x31, ItemKind = 5, Kinds = 0x23, EntryKinds = 0x10, FifthList = 7;
        // (1.23.1) The PlayStation world map's name of the place arrived at (0x3433FC): its first instructions (18 bytes,
        // as far as another mod's hook reaches) not looked at; its flags tested (0x2000: none drawn), the place plus one
        // read (ArrivalNameAt, 7 bytes) and tested, its dot by it less one; its name's sprite 0x36 plus it
        // (ArrivalSpriteAt).
        const string ArrivalNameBytes = "F7 05 ?? ?? ?? ?? 00 20 00 00 48 8B F9 0F 85 ?? ?? ?? ?? 44 8B 1D ?? ?? ?? ?? 45 33 C0 "
                                        + "45 85 DB 0F 84 ?? ?? ?? ?? 8B 1D ?? ?? ?? ?? 41 8D 43 FF 48 63 D0 48 6B CA 34 48 "
                                        + "8D 15";
        const string ArrivalSpriteBytes = "41 8D 43 36 89 45 D4";
        public const int ArrivalNameAt = 0x13, ArrivalNameLength = 7, ArrivalSpriteAt = 0x90;
        // (1.23.2) The menu's name of its place (in 0x344B68): its sprite's slot kept in the menu's record (+ 4), its
        // sprite 0x37 plus the place (MenuNameAt: `lea eax, [r14 + 0x37]`), the record's + 0x18 given 8 (12 bytes, by
        // the program's base in rdi: copied whole into the native code), then the slot's sprite written.
        const string MenuNameBytes = "4C 63 E0 41 89 84 3A ?? ?? ?? ?? 41 8D 46 37 41 C7 84 3A ?? ?? ?? ?? 08 00 00 00 "
                                     + "4B 8D 0C E4 89 84 8F ?? ?? ?? ??";
        public const int MenuNameAt = 0xB, MenuNameLength = 16, MenuNameKept = 4, NameSprite = 0x37, BlankSprite = 0x7A;
        // The Deep's list's looks: the UI's text by its number (sheet 0x13, the text from + 4); a row by two keys; the
        // guide's page read by it (sheet 0xBC); the frame's mode 4's guide (B8: its number, then E9 to its showing: the
        // guide and the mask in edx and r8d, then the call); the frame's mode read (+ 0xE4); the About key's guide (the
        // Guide table, sheet 0xBB, then the guide's number), and the Deep's list's About key (0xA2) calling it; the
        // frame's Deep list (+ 0x60, the About key's function); the Deep's list's Thumbnail kept (+ 0x268); a place's
        // name by its number (PlaceName, sheet 0x55); the menu's art set: the base art's path, then the setter. The
        // functions' own first instructions (as far as another mod's hook of 14 bytes reaches) aren't looked at: the
        // helper hooks four of them, and another mod may have first (each pattern is the only one past them).
        const string UiTextBytes = "48 83 EC 28 8B D1 B9 13 00 00 00 E8 ?? ?? ?? ?? 48 85 C0 74 0C 48 8D 48 04 48 63 01 48 "
                                   + "03 C1 EB 07 48 8D 05 ?? ?? ?? ?? 48 83 C4 28 C3";
        const int UiTextPrologue = 16;
        const string TwoKeyRowBytes = "48 89 5C 24 08 57 48 83 EC 20 8B FA 41 8B D8 8B D1 48 8B 0D ?? ?? ?? ?? 48 85 C9 74 4F "
                                      + "E8 ?? ?? ?? ?? 4C 8B C8 48 85 C0 74 42 8B 48 0C 83 E9 02";
        const int TwoKeyRowPrologue = 15;
        const string PageCallBytes = "8B 57 10 44 8B C5 B9 BC 00 00 00 E8 ?? ?? ?? ??";
        const string DeepGuideBytes = "83 ED 01 0F 84 ?? ?? ?? ?? 83 ED 01 0F 84 ?? ?? ?? ?? 83 ED 01 0F 84 ?? ?? ?? ?? 83 FD "
                                      + "01 0F 85 ?? ?? ?? ?? B8 ?? ?? ?? ?? E9";
        const string GuideCallBytes = "45 8B C7 8B D0 E8";
        const string FrameModeBytes = "44 8B B1 E4 00 00 00 41 8B F0 8B EA 48 8B D9 41 3B D6";
        const string AboutBytes = "40 53 48 83 EC 30 48 8B 05 ?? ?? ?? ?? 48 8B 48 10 48 8B 05 ?? ?? ?? ?? 48 8B 99 08 01 00 "
                                  + "00 48 85 C0 75 2A 48 8B 0D ?? ?? ?? ?? 48 85 C9 0F 84 ?? ?? ?? ?? BA BB 00 00 00 E8 ?? ?? "
                                  + "?? ?? 48 89 05 ?? ?? ?? ?? 48 85 C0 0F 84 ?? ?? ?? ?? BA ?? ?? ?? ?? 48 8B C8 E8";
        const int AboutPrologue = 17;
        const string AboutKeyBytes = "41 B8 A2 00 00 00 E8 ?? ?? ?? ?? 84 C0 74 ?? E8 ?? ?? ?? ??";
        const string DeepKeyBytes = "48 89 5C 24 10 57 48 83 EC 30 48 8B 79 60 33 DB 48 85 FF";
        const string ThumbnailBytes = "4C 8D 45 D0 48 8B CB 48 8D 55 E0 E8 ?? ?? ?? ?? 48 85 C0 74 06 83 78 34 02 74 02 33 C0 "
                                      + "8B 55 E8 48 89 87 ?? ?? ?? ??";
        const string PlaceNameBytes = "40 53 48 83 EC 20 48 8B 05 ?? ?? ?? ?? 8B D9 48 85 C0 75 20 48 8B 0D ?? ?? ?? ?? 48 85 "
                                      + "C9 74 60 8D 50 55 E8";
        const int PlaceNamePrologue = 15;
        const string ArtSetBytes = "8B 50 1C 48 8D 4C 24 20 41 B8 04 01 00 00 E8 ?? ?? ?? ?? 4C 8D 44 24 20 48 8B D5 49 8B CE "
                                   + "E8 ?? ?? ?? ??";
        const string TextRemakeBytes = "48 89 5C 24 08 57 48 83 EC 20 8B 91 2C 01 00 00 48 8B D9 48 8B 0D ?? ?? ?? ?? E8 ?? ?? "
                                       + "?? ?? 84 C0 74 ?? 83 BB A0 01 00 00 03 48 8D BB 40 01 00 00 75 ?? 48 8B CF E8 ?? ?? ?? "
                                       + "?? 84 C0 74 ?? 8B 8B F8 00 00 00 85 C9 74 ?? E8";
        const int TextRemakePrologue = 16, TextRemakeCallAt = 73;
        public const int PageCallAt = 11, DeepGuideAt = 37, DeepGuideJump = 41, GuideCallAt = 5, AboutGuideAt = 79,
                         AboutKeyCallAt = 15, ThumbnailAt = 35, ArtPathCallAt = 14, ArtSetCallAt = 30;
        /// <summary>(1.21.0) Where in each pattern its site is, and how long the instruction it changes.</summary>
        public const int DungeonBlockTest = 10, DungeonBlockLength = 10, DungeonCountLength = 8, DungeonScreenLength = 13,
                         DungeonHandlerLength = 7, FloorCallAt = 0x25, FloorPlaceRead = 0x1A, FloorOutAt = 0x14,
                         RowTitleCallAt = 0x0E, RowInfoCallAt = 8, CallLength = 5, CopyReach = 0x100,
                         ScreenReach = 0x800, FloorReach = 0x200;

        // The patterns: two hex digits a byte, ?? any byte; each function's from its start, its
        // first instructions (as many bytes as a hook's jump would take, `Prologue`) not looked at.
        const string SheetInitBytes =
            "48 89 5C 24 08 48 89 74 24 10 48 89 7C 24 18 41 56 48 83 EC 20 4C 8B 72 38 48 8B D9 48 8B 51 28 "
            + "33 FF 41 0F B6 4E 09 83 E9 01 74 45 83 E9 01 74 40";
        const int SheetInitPrologue = 15;
        const string ScriptReaderBytes =
            "48 89 5C 24 18 55 56 57 48 8D 6C 24 80 48 81 EC 80 01 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 89 45 "
            + "70 48 8B 05 ?? ?? ?? ?? 33 DB 48 8B F2 44 8B C1 48 85 C0 75 05 8D 43 01 EB 03 8B 40 08 33 C9 89 4C "
            + "24 58 F7 D8 88 4C 24 5C 41 8B C0 1B C9 33 D2 83 E1 02 83 C1 03 F7 F1";
        const int ScriptReaderPrologue = 20;
        /// <summary>The script reader's `mov rax, [rip + x]` of the divisor's pointer.</summary>
        const int ScriptModeLoad = 0x22;
        const string VariablesBytes =
            "48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18 57 41 54 41 55 41 56 41 57 48 83 EC 20 33 FF 41 8B D8 "
            + "8B F2 8B E9 41 BD 60 03 00 00 44 8D 7F 0F 44 8D 67 01 81 F9 BE 00 00 00 74 70 41 84 EC 75 04";
        const int VariablesPrologue = 15;
        /// <summary>Where the two variable functions differ: the events' looks at its fifth (cmp byte
        /// [rsp + 0x70], 0), the world map's at a byte of its own (cmp byte [rip + x], 0).</summary>
        const int VariablesFork = 0x185;
        const string EventFork = "80 7C 24 70 00";
        const string WorldFork = "80 3D ?? ?? ?? ?? 00";
        /// <summary>Each variable function calls the one that finds a variable's bytes (call x).</summary>
        const int VariablesLookup = 0x65;
        const string LookupBytes =
            "40 53 48 83 EC 20 33 DB 81 F9 80 00 00 00 7D 10 48 8B 05 ?? ?? ?? ?? 48 63 C9 48 8D 1C 88 EB 58";
        const int LookupPrologue = 16;
        /// <summary>The lookup's `mov rax, [rip + x]` of the variables' pointer.</summary>
        const int LookupLoad = 0x10;
        /// <summary>The battle's units: from its start (its first four instructions, 17 bytes, as much
        /// as another mod's hook's jump would take, not looked at) to its first return.</summary>
        const string EncounterBytes =
            "8B 05 ?? ?? ?? ?? 85 C0 74 56 83 3D ?? ?? ?? ?? 00 75 4D 3D 00 02 00 00 7C 18 05 00 FE FF FF 48 63 C8 48 8D "
            + "04 89 48 C1 E0 07 48 03 05 ?? ?? ?? ?? C3";
        const int EncounterPrologue = 17;
        /// <summary>A battle loading: variable 0x32 read (mov ecx, 0x32; call x), the battle's number
        /// set from it (mov [rip + x], eax), its file read (call x).</summary>
        const string EncounterSetBytes = "B9 32 00 00 00 E8 ?? ?? ?? ?? 89 05 ?? ?? ?? ?? E8 ?? ?? ?? ?? 85 C0";
        const int EncounterSetStore = 10;
        /// <summary>The game's progress set, from its start to its return: the value stored by its
        /// track (test byte [rcx + 0x10], 1; mov [rcx + rax*4 + 0x68] or [rcx + rax*4 + 0x18], r8d),
        /// then each one waiting on it called; its first four instructions (15 bytes) not looked at.
        /// The function beside it, which sets a progress flag (a byte), stores bytes there.</summary>
        const string ProgressBytes =
            "48 89 5C 24 18 48 89 74 24 20 57 48 83 EC 20 F6 41 10 01 8B C2 74 07 44 89 44 81 68 EB 05 44 89 44 81 "
            + "18 48 8B 35 ?? ?? ?? ?? 48 8B 7E 18 48 8B 1F EB 10 48 8B 4B 10 48 8B D6 48 8B 01 FF 50 08 48 8B 1B 48 "
            + "3B DF 75 EB";
        const int ProgressPrologue = 15;
        /// <summary>The travel check, whole: whether an event waits where the travel starts (cmp byte
        /// [rip + x], 0), the place it was found at against the marker's (cmp edx, [rip + x]), the
        /// way the marker came against the travel's first route (going back is let go), then the
        /// game's five places and events (cmp edx, 8; cmp [rip + x], 0xCC; 2 and 0x1B1; 0xE and
        /// 0xDA; 0xB; 0 and 0x1D0); its first three instructions (15 bytes) not looked at.</summary>
        const string TravelCheckBytes =
            "80 3D ?? ?? ?? ?? 00 74 44 8B 15 ?? ?? ?? ?? 3B 15 ?? ?? ?? ?? 75 36 44 8B 05 ?? ?? ?? ?? 41 83 F8 FF 74 78 "
            + "48 63 05 ?? ?? ?? ?? 48 8D 0D ?? ?? ?? ?? 8B 0C 81 41 33 C8 84 C9 74 11 83 FA 08 75 0F 81 3D ?? ?? ?? ?? "
            + "CC 00 00 00 74 4F 32 C0 C3 83 FA 02 75 0C 81 3D ?? ?? ?? ?? B1 01 00 00 EB 0F 83 FA 0E 75 0E 81 3D ?? ?? ?? "
            + "?? DA 00 00 00 75 2A EB D9 83 FA 0B 75 13 8B 0D ?? ?? ?? ?? 81 E9 D2 00 00 00 74 C6 83 E9 02 EB C1 85 D2 75 "
            + "0C 81 3D ?? ?? ?? ?? D0 01 00 00 74 B1 B0 01 C3";
        const int TravelCheckPrologue = 15;
        /// <summary>(1.2.4) Travel start asking the travel check: whether a travel was found (test byte
        /// [rip + x], 1: the travel's flags), the roads it has against 0 (cmp [rip + x], r14d: its
        /// legs), the roads taken set to 0 (mov [rip + x], r14d), then the call; the call's target
        /// must be the travel check found.</summary>
        const string TravelStateBytes =
            "F6 05 ?? ?? ?? ?? 01 0F 84 ?? ?? ?? ?? 44 39 35 ?? ?? ?? ?? 44 89 35 ?? ?? ?? ?? 0F 84 ?? ?? ?? ?? E8";
        const int TravelFlagsTest = 0, TravelLegsCompare = 13, TravelDoneSet = 20, TravelCheckCall = 33;
        /// <summary>(1.2.5) The world map screen's showing of a place, from its start to its test of
        /// the place's state (cmp byte [r13 + 8], 0) and the two names it plays (Show, Hide): the
        /// place 47 or less (cmp ebx, 0x2F), the state kept at 0x9C8 + place x 16, the piece at
        /// 0x208 + place x 24; its first five instructions (15 bytes) not looked at.</summary>
        const string MarkerStateBytes =
            "48 89 5C 24 08 44 89 44 24 18 55 56 57 41 54 41 55 41 56 41 57 48 8B EC 48 83 EC 70 49 63 D8 4C 8B EA "
            + "4C 8B F1 83 FB 2F 0F 87 ?? ?? ?? ?? 0F 10 02 48 8D 34 5B 48 8B C3 48 03 C0 48 89 75 58 45 33 E4 F3 0F 7F "
            + "84 C1 C8 09 00 00 4C 39 A4 F1 08 02 00 00 0F 84 ?? ?? ?? ?? 45 38 65 08 4C 8D 3D ?? ?? ?? ?? 49 8B D7 48 "
            + "8D 3D ?? ?? ?? ?? 48 0F 45 D7";
        const int MarkerStatePrologue = 15;
        /// <summary>(1.2.5) A piece's child piece by its name, whole: the box by that name in the piece's
        /// tree (at + 0x110, call x), then, a reference (its kind 0x0C or 9), the piece it places.</summary>
        const string ChildPieceBytes =
            "48 83 EC 28 4C 8B D1 48 81 C1 10 01 00 00 E8 ?? ?? ?? ?? 48 85 C0 74 48 83 78 34 0C 75 25 4C 8D 88 30 01 00 "
            + "00 4C 8D 80 E0 00 00 00 48 8D 90 D0 00 00 00 49 8B 8A F0 01 00 00 48 83 C4 28 E9 ?? ?? ?? ?? 83 78 34 09 75 "
            + "17 4C 8D 88 20 01 00 00 4C 8D 80 08 01 00 00 48 8D 90 F8 00 00 00 EB D3 33 C0 48 83 C4 28 C3";
        const int ChildPieceBoxCall = 0x0E;
        /// <summary>(1.2.5) The world map screen's change of the walking Ramza's picture, to its strings'
        /// pool: its picture's parts' name made (formatted into rsp + 0x30) and compared with the
        /// picture's (at + 0xE8), the parts made ready (call x), a string made of the name (call x),
        /// given to the picture (call x), let go (mov rcx, [rip + x]; call x).</summary>
        const string PictureChangeBytes =
            "40 53 48 81 EC 50 01 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 89 84 24 40 01 00 00 48 83 B9 50 08 00 00 00 48 "
            + "8B D9 0F 84 ?? ?? ?? ?? E8 ?? ?? ?? ?? 41 B8 04 01 00 00 48 8D 54 24 30 8B C8 E8 ?? ?? ?? ?? 48 8B 83 50 08 "
            + "00 00 4C 8D 44 24 30 48 8B 88 E8 00 00 00 4C 2B C1 0F B6 01 42 0F B6 14 01 2B C2 75 07 48 FF C1 85 D2 75 ED "
            + "85 C0 74 ?? 48 8B 4B 18 48 85 C9 74 ?? 45 33 C0 48 8D 54 24 30 E8 ?? ?? ?? ?? 84 C0 74 ?? 48 8D 54 24 30 48 "
            + "8D 4C 24 20 E8 ?? ?? ?? ?? 48 8B 8B 50 08 00 00 48 8D 54 24 20 48 81 C1 E8 00 00 00 E8 ?? ?? ?? ?? 8B 54 24 "
            + "28 85 D2 74 ?? 48 8B 0D ?? ?? ?? ?? E8 ?? ?? ?? ??";
        const int PartsReadyCall = 0x81, StringMakeCall = 0x94, StringAssignCall = 0xAC, StringPoolLoad = 0xB9,
                  StringReleaseCall = 0xC0;
        /// <summary>(1.2.5) The world map's test of a character, whole but its first three instructions
        /// (15 bytes, which another mod's hook of 14 bytes would cover): its word read from the chain (the chain's place, its words), a pointer (mov r11,
        /// [rip + x]: the script reader's), its 54 units (cmp edx, 0x36), each 0x258 bytes from x
        /// (lea rax, [rip + x]): skipped when its second byte is 0xFF, the character when its first
        /// byte is, or one carrying it (its four bytes at 0x230, the second of them 0, its byte at
        /// 0x11E 0, its third byte not 0x82 unless the pointer's number at + 8 is 0); the chain's
        /// test failed (or [rip + x], 2) when none is.</summary>
        const string PartyTestBytes =
            "48 89 7C 24 08 0F B7 15 ?? ?? ?? ?? 45 33 C0 48 8B 05 ?? ?? ?? ?? 4C 8B 1D ?? ?? ?? ?? 41 8D 78 01 44 0F "
            + "B7 14 50 66 03 D7 66 89 15 ?? ?? ?? ?? 33 D2 83 FA 36 72 04 33 C9 EB 14 48 63 C2 48 69 C8 58 02 00 00 "
            + "48 8D 05 ?? ?? ?? ?? 48 03 C8 80 79 01 FF 74 65 0F B6 01 41 3B C2 74 68 4D 85 DB 74 2E 41 83 7B 08 00 "
            + "75 27 44 8B 89 30 02 00 00 41 0F B6 C1 41 3B C2 75 41 41 F7 C1 00 FF 00 00 75 38 80 B9 1E 01 00 00 00 "
            + "75 2F 44 8B C7 EB 2A 44 8B 89 30 02 00 00 41 0F B6 C1 41 3B C2 75 1A 41 F7 C1 00 FF 00 00 75 11 80 B9 "
            + "1E 01 00 00 00 75 08 80 79 02 82 44 0F 45 C7 03 D7 83 FA 36 0F 82 76 FF FF FF 83 FA 36 75 0C 45 85 C0 "
            + "75 07 83 0D ?? ?? ?? ?? 02 48 8B 7C 24 08 C3";
        const int PartyTestPrologue = 15;
        /// <summary>Its mov r11, [rip + x] of the pointer, and its lea rax, [rip + x] of the units.</summary>
        const int PartyModeLoad = 0x16, PartyUnitsLoad = 0x45;
        /// <summary>(1.3.0) The world map screen's setup of its places' pieces, from its start to its finding of
        /// Bases' tree: its layouts' root (mov rcx, [rcx + 0x18]; call x) kept at + 0x1F0, MapAll found in
        /// it and kept at + 0x1F8; its first four instructions (15 bytes) not looked at.</summary>
        const string MapSetupBytes =
            "48 8B C4 48 89 58 10 48 89 70 18 48 89 78 20 55 41 54 41 55 41 56 41 57 48 8D A8 B8 FD FF FF 48 81 EC 20 "
            + "03 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 89 85 10 02 00 00 48 8B D9 48 8B 49 18 E8 ?? ?? ?? ?? 45 33 FF "
            + "48 8B F0 48 85 C0 0F 84 ?? ?? ?? ?? 48 8B CB 48 89 83 F0 01 00 00 E8 ?? ?? ?? ?? 48 8D 15 ?? ?? ?? ?? 48 "
            + "8D 4C 24 70 E8 ?? ?? ?? ?? 48 8D 54 24 70 48 8B CE E8 ?? ?? ?? ?? 8B 54 24 78 4C 8B F0 85 D2 74 0C 48 8B "
            + "0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 4D 85 F6 0F 84 ?? ?? ?? ?? 48 8D 15 ?? ?? ?? ?? 4C 89 B3 F8 01 00 00 48 8D "
            + "4C 24 60 E8 ?? ?? ?? ?? 48 8D 8E 10 01 00 00 48 8D";
        const int MapSetupPrologue = 15;
        /// <summary>...and, at + 0x1C2, its keeping of each place's piece: the pieces from + 0x208 (lea rdi, [rbx
        /// + 0x208]), the Town table's row (table 0x34) and its name, "Point%s" or "Base%s" as the row's town
        /// byte (+ 0x30) says, kept at + 0x14 (mov [rdi + 0x14], al), the piece found (mov [rdi], rax), its
        /// box (mov [rdi + 8], rax), the screen made one it tells (+ 0x248).</summary>
        const int MapSetupPieces = 0x1C2;
        const string MapSetupPiecesBytes =
            "48 8D BB 08 02 00 00 41 8B D7 B9 34 00 00 00 E8 ?? ?? ?? ?? 4C 8B E8 48 85 C0 0F 84 ?? ?? ?? ?? 4C 63 48 18 "
            + "4C 03 C8 0F 84 ?? ?? ?? ?? 48 83 C9 FF 48 FF C1 41 80 3C 09 00 75 F6 48 85 C9 0F 84 ?? ?? ?? ?? 41 80 7D "
            + "30 00 48 8D 05 ?? ?? ?? ?? 4C 8D 05 ?? ?? ?? ?? BA 04 01 00 00 4C 0F 44 C0 48 8D 8D 00 01 00 00 E8 ?? ?? "
            + "?? ?? 41 8A 45 30 48 8D 95 00 01 00 00 88 47 14 48 8D 4C 24 70 41 8B 45 24 89 47 10 E8 ?? ?? ?? ?? 48 8D "
            + "54 24 70 49 8B CC E8 ?? ?? ?? ?? 8B 54 24 78 48 89 07 85 D2 74 0C 48 8B 0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 "
            + "8D 95 00 01 00 00 48 8D 4C 24 50 E8 ?? ?? ?? ?? 49 8D 8C 24 10 01 00 00 48 8D 54 24 50 E8 ?? ?? ?? ?? 8B "
            + "54 24 58 48 89 47 08 85 D2 74 0C 48 8B 0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 8B 07 48 85 C0 0F 84 ?? ?? ?? ?? "
            + "C7 80 20 02 00 00 1F 00 00 00 33 D2 48 8B 07 44 89 B8 24 02 00 00 33 C0 48 8B 0F 44 8B 43 08 44 39 84 "
            + "81 48 02 00 00 74 1E 83 BC 81 48 02 00 00 00 74 0C FF C2 48 FF C0 83 FA 04 7C E2 EB 08 44 89 84 81 48 "
            + "02 00 00";
        /// <summary>(1.3.0) The layouts' copy of a box, from its start to its sixth case: the box's kind read
        /// (mov ecx, [rdx + 0x34]) and told apart (cmp ecx, 7; jg; je; sub ecx, 1; je ...).</summary>
        const string PieceCopyBytes =
            "48 89 5C 24 20 55 56 57 41 54 41 55 41 56 41 57 48 83 EC 30 48 8B E9 44 88 44 24 20 8B 4A 34 33 F6 45 8A "
            + "E0 48 8B DA 83 F9 07 0F 8F ?? ?? ?? ?? 0F 84 ?? ?? ?? ?? 83 E9 01 0F 84 ?? ?? ?? ?? 83 E9 01 0F 84 ?? ?? "
            + "?? ?? 83 E9 01 0F 84 ?? ?? ?? ?? 83 E9 01 0F 84 ?? ?? ?? ?? 83 E9 01 74 68 83";
        /// <summary>(1.3.0) A box moved, whole: x at + 0x38, y at + 0x3C, made to be drawn again (+ 0x95).</summary>
        const string PieceMoveBytes =
            "39 51 38 75 06 44 39 41 3C 74 22 F6 81 8C 00 00 00 03 89 51 38 44 89 41 3C C6 81 95 00 00 00 01 74 0B B8 "
            + "FF FF 7F 7F 89 41 74 89 41 78 C3";
        /// <summary>(1.3.0) A box put in a layer, whole: its parent (+ 0x18) the layer, after the box given
        /// (+ 0x20 the next, + 0x28 the one before) or first of the layer's (+ 0xD0).</summary>
        const string PieceAddBytes =
            "48 89 5C 24 10 57 48 83 EC 20 48 83 62 20 00 48 8B DA 48 83 62 28 00 48 8B F9 48 89 4A 18 8B 41 30 89 42 "
            + "30 4D 85 C0 74 1F 49 8B 40 20 48 85 C0 74 0C 48 89 42 20 49 8B 40 20 48 89 50 28 4C 89 42 28 49 89 58 20 "
            + "EB 22 48 8B 81 D0 00 00 00 48 85 C0 74 0F 48 89 42 20 48 8B 81 D0 00 00 00 48 89 58 28 48 89 99 D0 00 00 "
            + "00 48 81 C2 8C 00 00 00 80 3A 00 74 24 F3 0F 10 05 ?? ?? ?? ?? 48 8D 4B 74 4C 8D 44 24 30 F3 0F 11 44 24 "
            + "30 E8 ?? ?? ?? ?? 48 8B CB E8 ?? ?? ?? ?? 8B 57 30 85 D2 74 13 83 7B 34 01 75 0D 48 85 DB 74 08 48 8B CB "
            + "E8 ?? ?? ?? ?? 83 7B 5C 00 74 07 C6 87 D8 00 00 00 01 48 8B 5C 24 38 48 83 C4 20 5F C3";
        /// <summary>(1.3.0) A piece's animation played, whole: found by its name (call x), started (+ 0x68 1,
        /// call x), its frame the one given, or its last for -1 (+ 0x58), its time set to it.</summary>
        const string AnimationPlayBytes =
            "40 53 48 83 EC 30 41 8B D8 E8 ?? ?? ?? ?? 45 33 C9 48 8B C8 48 85 C0 74 54 C6 40 68 01 E8 ?? ?? ?? ?? 4C "
            + "8D 41 58 85 DB 78 19 41 3B 18 48 8D 44 24 20 89 5C 24 20 49 0F 4D C0 44 39 08 44 0F 4F 08 EB 07 45 39 08 "
            + "45 0F 4F 08 66 41 0F 6E C1 0F 5B C0 C6 41 6A 01 F3 0F 11 41 54 F3 0F 11 41 50 F3 0F 5E 05 ?? ?? ?? ?? F3 "
            + "0F 11 41 4C 48 83 C4 30 5B C3";
        /// <summary>(1.3.0) Every animation of a piece stopped, whole: its animations (+ 0x268 to + 0x270)
        /// each stopped by its name (call x).</summary>
        const string AnimationsStopBytes =
            "48 89 5C 24 10 48 89 74 24 18 57 48 83 EC 20 48 8B B9 70 02 00 00 48 8B F1 48 8B 99 68 02 00 00 EB 0F 48 "
            + "8B 13 48 8B CE E8 ?? ?? ?? ?? 48 83 C3 08 48 3B DF 75 EC 48 8B 5C 24 38 48 8B 74 24 40 48 83 C4 20 5F C3";
        /// <summary>(1.20.0) ...its call of the stopping of one animation by its name (call x), for each.</summary>
        const int AnimationsStopOne = 0x28;
        /// <summary>(1.4.0) ...and, at + 0x14B, its keeping of its Route piece (which holds the roads' pictures):
        /// "Route" found in MapAll (lea rdx, [rip + x], its string made; mov rcx, r14; call x) and kept at + 0x200
        /// (mov [rbx + 0x200], rax), the string let go.</summary>
        const int MapSetupRoute = 0x14B;
        const string MapSetupRouteBytes =
            "48 8D 15 ?? ?? ?? ?? 48 8D 4C 24 60 E8 ?? ?? ?? ?? 48 8D 54 24 60 49 8B CE E8 ?? ?? ?? ?? 8B 54 24 68 48 89 "
            + "83 00 02 00 00 85 D2 74 0C 48 8B 0D ?? ?? ?? ?? E8 ?? ?? ?? ??";
        /// <summary>(1.4.0) A box sized, whole: its width at + 0x40, its height at + 0x44, made to be drawn again
        /// (+ 0x95), its middle (+ 0x48, + 0x4C) half its size unless fixed (+ 0x8E).</summary>
        const string BoxSizeBytes =
            "39 51 40 75 06 44 39 41 44 74 43 F6 81 8C 00 00 00 0C 89 51 40 44 89 41 44 C6 81 95 00 00 00 01 74 0E B8 "
            + "FF FF 7F 7F 89 41 7C 89 81 80 00 00 00 80 B9 8E 00 00 00 00 75 15 8B C2 99 2B C2 D1 F8 89 41 48 41 8B C0 "
            + "99 2B C2 D1 F8 89 41 4C C3";
        /// <summary>(1.5.0) The path search, from its start to its test of whether a road is shown (its first four
        /// instructions not looked at); its loop's end (cmp ebx, 0x33; jl back to + 0x42).</summary>
        const string PathSearchBytes =
            "?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? 48 89 78 20 41 54 41 56 41 57 48 83 EC 20 83 3D ?? ?? "
            + "?? ?? 10 8B EA 8B F1 0F 8D ?? ?? ?? ?? 45 33 FF 4C 8D 35 ?? ?? ?? ?? 41 8B DF 4C 8D 25 ?? ?? ?? ?? "
            + "E8 ?? ?? ?? ?? 8B 05 ?? ?? ?? ?? 83 E8 10 41 0F 48 C7 89 05 ?? ?? ?? ?? E8 ?? ?? ?? ?? 4C 63 0D ?? "
            + "?? ?? ?? 48 8D 05 ?? ?? ?? ?? 49 69 C9 00 E8 00 00 44 89 0D ?? ?? ?? ?? 48 03 C8 48 89 0D ?? ?? ?? "
            + "?? 48 89 0D ?? ?? ?? ?? 8D 8B 2C 02 00 00 E8 ?? ?? ?? ?? 85 C0 0F 84 ?? ?? ?? ??";
        const string PathSearchLoopBytes = "83 FB 33 0F 8C ?? ?? ?? ??";
        /// <summary>(1.5.0) The path search's read of its cost so far (mov r9d, [rip + x]), and its writes of its count
        /// of roads taken and their cost as it goes on (mov [rip + x], r10d; mov [rip + x], r9d).</summary>
        const string PathSearchCostBytes = "44 8B 0D ?? ?? ?? ??", PathSearchDepthOnBytes = "44 89 15 ?? ?? ?? ??",
                     PathSearchCostOnBytes = "44 89 0D ?? ?? ?? ??";
        /// <summary>(1.5.0) The walk's setup of a road, a leaf: its road's number and direction, the table (its first
        /// three instructions not looked at).</summary>
        const string WalkSetupBytes =
            "?? ?? ?? ?? ?? ?? ?? ?? ?? 4C 8D 05 ?? ?? ?? ?? 83 E2 01 89 41 04 03 D2 4C 8B C9 09 11 F6 01 02 4D "
            + "8B 04 C0";
        /// <summary>(1.5.0) The travel's read of its last road when it stops short: the road from its path (mov edx,
        /// [r8 + rcx*4 + x], the path from the program's start), its record (mov rcx, [r8 + rax*8 + x]), its place
        /// (the record's + 2, or + 1 the other way).</summary>
        const string LastRoadBytes =
            "85 C0 7E 45 3B 05 ?? ?? ?? ?? 74 3D FF C8 4C 8D 05 ?? ?? ?? ?? 48 63 C8 41 8B 94 88 ?? ?? ?? ?? 0F B6 "
            + "C2 49 8B 8C C0 ?? ?? ?? ?? F7 C2 00 FF FF FF 75 0C 0F B6 41 02 89 05 ?? ?? ?? ?? EB 0A 0F B6 49 01 "
            + "89 0D ?? ?? ?? ??";
        /// <summary>(1.5.0) The world map's test of a place shown, whole but its first three instructions: places 0 to
        /// 42 by variable 512 + the place (the variables' read), 44 to 46 by three flags, the rest never.</summary>
        const string PlaceShownBytes =
            "?? ?? ?? ?? ?? ?? ?? ?? ?? 83 FA 2B 73 12 8D 8A 00 02 00 00 E8 ?? ?? ?? ?? 85 C0 0F 95 C0 EB 43 83 "
            + "EA 2B 74 3C 83 EA 01 74 16 83 EA 01 74 0A 83 FA 01 75 2D 8D 42 02 EB 0C B8 02 00 00 00 EB 05 B8 01 "
            + "00 00 00 48 8B 0D ?? ?? ?? ?? F6 41 10 01 74 09 8A 84 08 98 00 00 00 EB 08 8A 44 08 48 EB 02 32 C0 "
            + "48 83 C4 28 C3";
        const int PlaceShownCall = 0x14;
        /// <summary>(1.6.0) The random battles' roll, from its start (its first three instructions not looked at) to
        /// its look for the road arrived along among the place's three entrances (movzx eax, byte [rdx]; cmp eax, r11d,
        /// the road from edx; 24 bytes on, three times).</summary>
        const string BattleRollBytes =
            "?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? 57 41 54 41 56 48 83 EC 20 83 C1 E8 41 8A F0 44 8B DA 83 F9 "
            + "12 0F 87 ?? ?? ?? ?? 33 DB 44 8D 14 C9 41 C1 E2 03 4C 8D 25 ?? ?? ?? ?? 49 63 D2 8B CB 49 03 D4 44 8B "
            + "CB 0F B6 02 41 3B C3 74 0F FF C1 49 FF C1 48 83 C2 18 49 83 F9 03 7C E9";
        /// <summary>(1.6.0) The roll's calls: the travel step's as Ramza arrives (no battle forced: xor r8d, r8d; the
        /// place, mov ecx, [rip + x]; the road arrived along, the low byte of the travel's path at its count less one:
        /// movzx edx, byte [rdi + rdx*4 + 0x18]; call x), and the world map's as the battle ground he stands on is
        /// chosen (a battle forced: mov r8b, 1; the same from its own copy of the travel's state).</summary>
        const string BattleRollArrivingBytes = "45 33 C0 8B 0D ?? ?? ?? ?? FF C8 48 63 D0 0F B6 54 97 18 E8 ?? ?? ?? ??";
        const string BattleRollForcedBytes =
            "41 B0 01 8B 0D ?? ?? ?? ?? FF C8 48 63 D0 41 0F B6 94 97 ?? ?? ?? ?? E8 ?? ?? ?? ??";
        const int BattleRollArrivingCall = 19, BattleRollForcedCall = 23;
        /// <summary>(1.17.0) The roll's keeps: the squad's (movzx eax, byte [r14 + r12 + 1], the entrance's squad;
        /// movzx ecx, byte [r14 + r12 + 0x17], its variable; add eax, 0x200; mov [rip + x], eax), and the battle's and
        /// the map's (movzx ecx, byte [rcx + r12 + 0x15], the formation picked; mov [rip + x], ecx; movzx ecx, byte
        /// [r14 + r12 + 0x16], the entrance's map; mov [rip + y], ecx). Each within RollReach of the roll's start.</summary>
        const string RandomSquadBytes = "43 0F B6 44 26 01 43 0F B6 4C 26 17 05 00 02 00 00 89 05 ?? ?? ?? ??";
        const string RandomChoiceBytes = "42 0F B6 4C 21 15 89 0D ?? ?? ?? ?? 43 0F B6 4C 26 16 89 0D ?? ?? ?? ??";
        const int RandomSquadStore = 17, RandomBattleStore = 6, RandomMapStore = 18, RollReach = 0x300;

        // (1.7.0) A mod's own place as a destination.
        /// <summary>The game's places' records: 4 bytes a place (its picture set + 1 at + 2, its menu's kind at + 3),
        /// the program's own read as far as place 47 (its 44, then the bytes after them, as the game reads them).</summary>
        public const int RecordSize = 4, RecordPicture = 2, RecordMenu = 3, GameRecordBytes = 48 * RecordSize;
        /// <summary>The menu's entries of a place (0x3449B0): lea rcx, [rip + the records + 3]; cmp byte [rcx +
        /// rbp*4], 1 (its menu a town's).</summary>
        const string RecordsLeaBytes = "48 8D 0D ?? ?? ?? ?? 80 3C A9 01";
        /// <summary>A read of a place's record's picture (movzx ebx, byte [the program's start + place*4 + the
        /// records + 2]): its first three bytes, the distance at + 4; three of them.</summary>
        const string RecordReadBytes = "0F B6 9C";
        const int RecordReadDistance = 4, RecordReadCount = 3;
        /// <summary>The world map's dots: 52 bytes a place, the game's 43 (0 to 42) built by the world map's setup.</summary>
        public const int DotSize = 0x34, GameDots = 43;
        /// <summary>The world map's setup's loop over the places' dots (0x33F2E9): lea rbx, [rip + the dots + 4]; lea
        /// r15, [rip + the dots + 0x10]; lea rsi, [rip + its source rows]; cmp edi, 0x2f (47, no place); je; cmp edi,
        /// 0x2b (43 on: no dot); jae.</summary>
        const string DotsLoopBytes =
            "48 8D 1D ?? ?? ?? ?? 4C 8D 3D ?? ?? ?? ?? 48 8D 35 ?? ?? ?? ?? 83 FF 2F 0F 84 ?? ?? ?? ?? 83 FF 2B 0F 83";
        const int DotsLoopFlags = 7, DotsFlags = 0x10, DotLeaCount = 11, DotReadCount = 7;
        /// <summary>The dots' reads by the program's start in a register and a distance, as his program has them: the
        /// bytes before the distance (lea rdx, [rdi + d]; lea rcx, [rcx + d]; mov eax, [rcx + rbx + d]; or dword
        /// [rcx + rdi + d], n; mov rax, [rax + rdi + d]).</summary>
        static readonly string[] DotReadPrefixes = { "48 8D 97", "48 8D 89", "8B 84 19", "83 8C 39", "48 8B 84 38" };
        /// <summary>The screen's position of a place (0x15C9BC: rcx the screen, rdx where it goes, r8d the place;
        /// cmp r8d, 0x2f; ja its end; its row's box (movsxd rax, r8d; add rax, 0x16; lea r8, [rax + rax*2]; mov rax,
        /// [rcx + r8*8]); none: its end).</summary>
        const string PlacePositionBytes =
            "41 83 F8 2F 0F 87 ?? ?? ?? ?? 49 63 C0 48 83 C0 16 4C 8D 04 40 4A 8B 04 C1 48 85 C0";
        public const int PlacePositionBody = 0x0A, PlacePositionLoad = 0x15;
        /// <summary>The cursor put on a place (0x15CA54): its bound (cmp r9d, 0x2f; ja short its end) at + 7, its call
        /// of the position at + 0x10, its row's town byte read (lea rax, [r9 + r9*2]; cmp byte [rcx + rax*8 + 0x21c],
        /// 0) at + 0x15.</summary>
        const string CursorAtPlaceBytes =
            "48 83 EC 28 4D 63 C8 41 83 F9 2F 77 ?? 45 8B C1 E8 ?? ?? ?? ?? 4B 8D 04 49 80 BC C1 1C 02 00 00 00 74";
        public const int CursorBound = 7, CursorBoundLength = 6, CursorCall = 0x10, CursorRead = 0x15,
                         CursorReadLength = 12;
        /// <summary>A place's distance from the cursor (0x15CD08): movsxd rbx, edx; mov rdi, rcx; its bound (cmp ebx,
        /// 0x2f; ja) at + 6 of this; its call of the position at + 0x17; then, 0x59 on, its row's town byte read (lea
        /// rcx, [rbx + rbx*2]; mov al, [rdi + rcx*8 + 0x21c]).</summary>
        const string DistanceBoundBytes = "48 63 DA 48 8B F9 83 FB 2F 0F 87 ?? ?? ?? ?? 44 8B C3 48 8D 54 24 40 E8";
        const int DistanceBoundFrom = 6, DistanceCall = 0x17, DistanceReadFrom = 0x59;
        public const int BoundLength = 9, DistanceReadLength = 11;
        const string DistanceReadBytes = "48 8D 0C 5B 8A 84 CF 1C 02 00 00 84 C0";
        /// <summary>The marker arrived at its place (0x15CE8C): twice, its place's piece read (movsxd rax, [rbx +
        /// 0xd08]; lea rdx (rcx), [rax + rax*2]; mov rax, [rbx + rdx*8 + 0x208]) at + 0x0B, its seen byte set (0, then
        /// 1); 0x2E apart.</summary>
        const string ArrivedFirstBytes =
            "48 63 83 08 0D 00 00 48 8D 14 40 48 8B 84 D3 08 02 00 00 48 85 C0 74 ?? C6 80 2D 02 00 00 00";
        const string ArrivedSecondBytes =
            "48 63 83 08 0D 00 00 48 8D 0C 40 48 8B 84 CB 08 02 00 00 48 85 C0 74 ?? C6 80 2D 02 00 00 01";
        public const int ArrivedRead = 0x0B, RowReadLength = 8;
        const int ArrivedApart = 0x2E;
        /// <summary>The screen's handler of a piece's events (0x15A008; its prologue not looked at): 12 the mouse on a
        /// piece, 13 off it, for the map (its number 0x8B); four reads of the place's piece (mov rcx, [rdi + rbx*8 +
        /// 0x208] twice, then by rsi twice) at + 0x90, + 0xC4, + 0x172, + 0x1A6.</summary>
        const string PieceEventsBytes =
            "?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? 55 48 8B EC 48 83 EC 40 49 8B D8 48 8B F2 48 8B F9 E8 ?? ?? ?? ?? "
            + "8B 0B 83 E9 0C 0F 84 ?? ?? ?? ?? 83 F9 01 0F 85 ?? ?? ?? ?? 81 7F 24 8B 00 00 00";
        public static readonly int[] PieceEventsReads = { 0x90, 0xC4, 0x172, 0x1A6 };
        public const string PieceReadByRbx = "48 8B 8C DF 08 02 00 00", PieceReadByRsi = "48 8B 8C F7 08 02 00 00";
        /// <summary>The help of the place under the cursor (0x15B970): its bound (cmp esi, 0x2f; ja; cmp esi, [rip +
        /// Ramza's place]), then 0x90 on its row's kind read (lea rcx, [rsi + rsi*2]; mov r9d, n; mov r8d, [rdi +
        /// rcx*8 + 0x218]: at + 0x0A), 0xD6 on again (lea rcx, [rsi + rsi*2]; mov edx, [rdi + rcx*8 + 0x218]: at +
        /// 4).</summary>
        const string HelpBoundBytes = "83 FE 2F 0F 87 ?? ?? ?? ?? 3B 35";
        const string HelpKindBytes = "48 8D 0C 76 41 B9 ?? ?? ?? ?? 44 8B 84 CF 18 02 00 00";
        const string HelpKindAgainBytes = "48 8D 0C 76 8B 94 CF 18 02 00 00 85 D2";
        const int HelpKindFrom = 0x90, HelpKindAgainFrom = 0xD6;
        public const int HelpKindRead = 0x0A, HelpKindAgainRead = 4, HelpKindAgainLength = 7;
        /// <summary>The marker put on its place as the screen is set up (0x15A754): its bound (cmp dword [rdi], 0x2f;
        /// ja), then its row's piece tested (movsxd rax, [rdi]; add rax, 0x16; lea rax, [rax + rax*2]; cmp qword [rbx
        /// + rax*8], 0) at + 0x14.</summary>
        const string MarkerPlaceBytes =
            "83 3F 2F 0F 87 ?? ?? ?? ?? 48 63 07 48 83 C0 16 48 8D 04 40 48 83 3C C3 00 74";
        public const int MarkerPlaceTest = 0x14, MarkerPlaceTestLength = 5;
        /// <summary>The screen's two allocations (mov ecx, its size; the allocation; then its constructor called):
        /// the map's (0xDB0 bytes) and the frame menu's (0xF70), the size's four bytes at + 1 and + 4, the
        /// constructor's call at + 0x18 of each.</summary>
        const string MapAllocBytes = "B9 B0 0D 00 00 45 8B C7 E8 ?? ?? ?? ?? 48 8B D8 48 85 C0 74 ?? 48 8B C8 E8";
        const string FrameAllocBytes = "4D 8B C7 B9 70 0F 00 00 E8 ?? ?? ?? ?? 48 8B D8 48 85 C0 74 ?? 48 8B C8 E8";
        public const int MapAllocSize = 1, FrameAllocSize = 4, AllocCall = 8, AllocCtorCall = 0x18;
        public const int MapBytes = 0xDB0, FrameBytes = 0xF70;
        /// <summary>The screen's switch of its places' collision boxes (0x15CB04: the screen, on or off, which of two
        /// reasons): its body from + 0x0F; its calls of a box of a kind (tree, kind 13, 0 then 1) at + 0x93 and + 0xC1,
        /// of a box refreshed at + 0xA9 and + 0xD7.</summary>
        const string CollisionSwitchBytes =
            "49 63 C0 44 8A CA 48 8B D9 48 83 F8 02 0F 83 ?? ?? ?? ?? 4C 8B C0 BA 01 00 00 00 24 1F 49 C1 E8 05";
        const int CollisionSwitchFrom = 0x0F, CollisionBoxCall = 0x93, CollisionBoxCallAgain = 0xC1,
                  CollisionRefreshCall = 0xA9, CollisionRefreshCallAgain = 0xD7;
        /// <summary>The location info's name of its place (in 0x158CB0): mov ecx, [rsi + 0x14] (its Town row's name's
        /// number); call the name's text; mov rdx, rax; mov rcx, rdi; call the setting of a box's text (at + 0x0E).</summary>
        const string SetTextBytes = "8B 4E 14 E8 ?? ?? ?? ?? 48 8B D0 48 8B CF E8 ?? ?? ?? ??";
        const int SetTextCall = 0x0E;
        /// <summary>(1.7.1) A place's distance from the cursor starts 0x0A before its pattern (DistanceBoundBytes).</summary>
        const int DistanceStart = 0x0A;
        /// <summary>(1.7.1) The place nearest the cursor (0x15CC70: rcx the screen, rdx where its distance goes; the
        /// place, -1 none; its prologue not looked at): over the 48 rows, a place whose piece is there and that is
        /// shown, its distance (the call at + 0x48) more than 0 and the least; the loop's top at + 0x37, its end (cmp
        /// ebx, 0x30; jl its top) at + 0x76, its return from + 0x7B.</summary>
        const string NearestBytes =
            "?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? 57 41 56 41 57 48 83 EC 20 83 CF FF C7 02 00 00 80 BF 33 DB "
            + "48 8D B1 D0 09 00 00 4C 8B F2 48 8D A9 08 02 00 00 4C 8B F9 48 83 7D 00 00 74 ?? 80 3E 00 74 ?? 8B D3 "
            + "49 8B CF E8";
        public const int NearestTop = 0x37, NearestCall = 0x48, NearestEnd = 0x76, NearestEndLength = 5,
                         NearestReturn = 0x7B;
        const string NearestEndBytes = "83 FB 30 7C";
        /// <summary>(1.7.1) The pad's focus of the nearest place (in 0x15BE8C): its call of the nearest, then three
        /// reads of the place's row by three times it (mov rax, [rbx + rdi*8 + 0x208]; mov r8, ...; mov rax, ...) at
        /// + 0x0F, + 0x2A and + 0x3B.</summary>
        const string NearestFocusBytes =
            "E8 ?? ?? ?? ?? 85 C0 78 ?? 48 98 48 8D 3C 40 48 8B 84 FB 08 02 00 00 48 85 C0 74 ?? 48 8B 0D ?? ?? ?? ?? "
            + "C6 80 2D 02 00 00 00 4C 8B 84 FB 08 02 00 00 48 8B 53 18 E8 ?? ?? ?? ?? 48 8B 84 FB 08 02 00 00 "
            + "C6 80 2D 02 00 00 01";
        public static readonly int[] NearestFocusReads = { 0x0F, 0x2A, 0x3B };
        public const string FocusReadRax = "48 8B 84 FB", FocusReadR8 = "4C 8B 84 FB";
        /// <summary>(1.7.1) The game's load of a save's state (0x21B0E8: ecx a mode; its prologue not looked at): its
        /// lea of the variables (lea rcx, [rip + them]) at + 0x1A1, their copy from the save (lea rax, [r8 + 0x8634];
        /// movups xmm0, [rax]; movups [rcx], xmm0) at + 0x235.</summary>
        const string SaveLoadBytes =
            "?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? 48 89 78 20 41 56 48 83 EC 20 4C 8B 05 ?? ?? ?? ?? 48 8D 15 "
            + "?? ?? ?? ?? BB 04 00 00 00 4D 8B C8 8B F9 4C 2B CA 8D 73 7C 44 8D 5B 32 8D 6B FD";
        const int SaveLoadBank = 0x1A1, SaveLoadCopy = 0x235;
        const string SaveLoadBankBytes = "48 8D 0D ?? ?? ?? ?? 88 42 04 BA 08 00 00 00";
        const string SaveLoadCopyBytes = "49 8D 80 34 86 00 00 0F 10 00 0F 11 01";
        /// <summary>(1.35.0) The party it copies from the save (Framework.RosterUnits, 0x11A7D10): its lea of them (lea
        /// rdx, [rip + them]) at + 0x20, 54 of them (mov r11d, 0x36 in SaveLoadBytes), the next one 0x258 bytes on
        /// (add rdx, 0x258) at + 0x9A.</summary>
        const int SaveLoadRoster = 0x20, SaveLoadStride = 0x9A;
        const string SaveLoadStrideBytes = "48 81 C2 58 02 00 00";

        /// <summary>The travel check's five reads of the event waiting (cmp [rip + x], n and mov ecx,
        /// [rip + x]: where each starts, how long it is; x at its third byte), which must all be of
        /// one place.</summary>
        static readonly (int At, int Length)[] PendingEventReads =
            { (0x41, 10), (0x55, 10), (0x66, 10), (0x79, 6), (0x90, 10) };

        /// <summary>A pattern's bytes, -1 for any; the first `prologue` any.</summary>
        public static int[] Pattern(string text, int prologue = 0)
        {
            var parts = text.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            var pattern = new int[parts.Length];
            for (int n = 0; n < parts.Length; n++)
                pattern[n] = n < prologue || parts[n] == "??" ? -1 : Convert.ToInt32(parts[n], 16);
            return pattern;
        }

        public static bool At(ReadOnlySpan<byte> image, int at, int[] pattern)
        {
            if (at < 0 || at + pattern.Length > image.Length)
                return false;
            for (int k = 0; k < pattern.Length; k++)
                if (pattern[k] >= 0 && image[at + k] != pattern[k])
                    return false;
            return true;
        }

        /// <summary>Every place in the program's code where the pattern is (its start).</summary>
        public static List<int> Search(ReadOnlySpan<byte> image, List<Section> sections, int[] pattern)
        {
            var found = new List<int>();
            int anchor = Array.FindIndex(pattern, b => b >= 0);
            if (anchor < 0)
                return found;
            byte first = (byte)pattern[anchor];
            foreach (var section in sections)
            {
                if (!section.Code)
                    continue;
                int end = Math.Min(section.Address + section.Size, image.Length) - pattern.Length;
                for (int at = section.Address; at <= end; at++)
                {
                    int next = image.Slice(at + anchor, end - at + 1).IndexOf(first);
                    if (next < 0)
                        break;
                    at += next;
                    if (At(image, at, pattern))
                        found.Add(at);
                }
            }
            return found;
        }

        /// <summary>Where an instruction of `length` bytes at `at` whose last four are a distance
        /// from its end (a `mov reg, [rip + x]`, a `call x`) leads.</summary>
        static int Target(ReadOnlySpan<byte> image, int at, int length)
            => at + length + BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at + length - 4, 4));

        /// <summary>One site found by its pattern: where (-1 when it isn't exactly once), and what is said when not.</summary>
        static int One(ReadOnlySpan<byte> image, List<Section> sections, string bytes, string what, List<string> missing,
                       int prologue = 0)
        {
            var found = Search(image, sections, Pattern(bytes, prologue));
            if (found.Count == 1)
                return found[0];
            missing.Add($"{what} ({found.Count} places like it, not 1)");
            return -1;
        }

        /// <summary>(1.7.0) Every 4 bytes in the program's code that are `value`, as a distance after one of
        /// `prefixes` (each instruction's start, where its distance is).</summary>
        internal static List<(int At, int Distance)> Distances(ReadOnlySpan<byte> image, List<Section> sections, int low,
                                                               int high, string[] prefixes)
        {
            var found = new List<(int, int)>();
            var patterns = Array.ConvertAll(prefixes, p => Pattern(p));
            foreach (var section in sections)
            {
                if (!section.Code)
                    continue;
                int end = Math.Min(section.Address + section.Size, image.Length) - 4;
                for (int at = section.Address + 3; at <= end; at++)
                {
                    int value = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at, 4));
                    if (value < low || value >= high)
                        continue;
                    foreach (var pattern in patterns)
                        if (At(image, at - pattern.Length, pattern))
                        {
                            found.Add((at - pattern.Length, at));
                            break;
                        }
                }
            }
            return found;
        }

        /// <summary>(1.7.0) Every rip-relative operand in the program's code reaching [low, high): the leas (48 or 4C,
        /// 8D, its operand's byte, the distance: 7 bytes, their starts) and how many other instructions do (an operand's
        /// byte before a distance, the instruction ending there).</summary>
        internal static List<int> RipLeas(ReadOnlySpan<byte> image, List<Section> sections, long low, long high,
                                          out int others)
        {
            var leas = new List<int>();
            others = 0;
            foreach (var section in sections)
            {
                if (!section.Code)
                    continue;
                int end = Math.Min(section.Address + section.Size, image.Length) - 4;
                for (int at = section.Address + 1; at <= end; at++)
                {
                    if ((image[at - 1] & 0xC7) != 0x05)
                        continue;
                    long target = at + 4L + BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at, 4));
                    if (target < low || target >= high)
                        continue;
                    if (at >= 3 && (image[at - 3] == 0x48 || image[at - 3] == 0x4C) && image[at - 2] == 0x8D)
                        leas.Add(at - 3);
                    else
                        others++;
                }
            }
            return leas;
        }

        /// <summary>(1.7.0) What a mod's own place needs to be somewhere Ramza goes: each found exactly where it is
        /// meant to be, else said (MissingForDestinations) and none of it kept.</summary>
        static void FindDestinations(ReadOnlySpan<byte> image, List<Section> sections, Places places)
        {
            var missing = places.MissingForDestinations;
            // The places' records: from the menu's entries' lea; its three reads of a picture.
            int lea = One(image, sections, RecordsLeaBytes, "the menu's entries of a place", missing);
            if (lea >= 0)
            {
                int records = Target(image, lea, 7) - RecordMenu;
                var reads = Distances(image, sections, records + RecordPicture, records + RecordPicture + 1,
                                      new[] { RecordReadBytes + " ??" });
                if (reads.Count == RecordReadCount)
                {
                    places.LocationRecords = records;
                    places.LocationRecordLea = lea;
                    foreach (var (at, _) in reads)
                        places.LocationRecordReads.Add(at);
                }
                else
                    missing.Add($"the reads of a place's picture ({reads.Count} of them, not {RecordReadCount})");
            }
            // The dots: from the setup's loop; every lea of them and every read of them by a distance.
            int loop = One(image, sections, DotsLoopBytes, "the world map's setup's loop over its places' dots", missing);
            if (loop >= 0)
            {
                int dots = Target(image, loop, 7) - 4;
                if (Target(image, loop + DotsLoopFlags, 7) != dots + DotsFlags)
                    missing.Add("the world map's dots (its setup reads two arrays)");
                else
                {
                    var leas = RipLeas(image, sections, dots, dots + (long)GameDots * DotSize, out int others);
                    var reads = Distances(image, sections, dots, dots + GameDots * DotSize, DotReadPrefixes);
                    if (leas.Count != DotLeaCount || others != 0)
                        missing.Add($"the world map's dots' leas ({leas.Count} of them, not {DotLeaCount}; {others} other "
                                    + "instructions reach them)");
                    else if (reads.Count != DotReadCount)
                        missing.Add($"the world map's dots' reads ({reads.Count} of them, not {DotReadCount})");
                    else
                    {
                        places.Dots = dots;
                        places.DotLeas.AddRange(leas);
                        places.DotReads.AddRange(reads);
                    }
                }
            }
            // The screen's reads of a place's row.
            int position = One(image, sections, PlacePositionBytes, "the world map screen's position of a place", missing);
            int cursor = One(image, sections, CursorAtPlaceBytes, "the world map screen's cursor put on a place", missing);
            if (cursor >= 0 && position >= 0 && Target(image, cursor + CursorCall, 5) != position)
                missing.Add("the world map screen's cursor put on a place (it asks another position)");
            int distance = One(image, sections, DistanceBoundBytes, "the world map screen's distance of a place", missing);
            if (distance >= 0 && position >= 0 && Target(image, distance + DistanceCall, 5) != position)
                missing.Add("the world map screen's distance of a place (it asks another position)");
            if (distance >= 0 && !At(image, distance + DistanceReadFrom, Pattern(DistanceReadBytes)))
                missing.Add("the world map screen's distance of a place (its row read isn't where it was)");
            int arrived = One(image, sections, ArrivedFirstBytes, "the world map screen's marker arrived", missing);
            if (arrived >= 0 && !At(image, arrived + ArrivedApart, Pattern(ArrivedSecondBytes)))
                missing.Add("the world map screen's marker arrived (its second read isn't where it was)");
            int events = One(image, sections, PieceEventsBytes, "the world map screen's handler of a piece's events",
                             missing);
            if (events >= 0)
                for (int n = 0; n < PieceEventsReads.Length; n++)
                    if (!At(image, events + PieceEventsReads[n], Pattern(n < 2 ? PieceReadByRbx : PieceReadByRsi)))
                    {
                        missing.Add("the world map screen's handler of a piece's events (its reads aren't where they were)");
                        events = -1;
                        break;
                    }
            int help = One(image, sections, HelpBoundBytes, "the world map screen's help of a place", missing);
            if (help >= 0 && (!At(image, help + HelpKindFrom, Pattern(HelpKindBytes))
                              || !At(image, help + HelpKindAgainFrom, Pattern(HelpKindAgainBytes))))
            {
                missing.Add("the world map screen's help of a place (its reads aren't where they were)");
                help = -1;
            }
            int marker = One(image, sections, MarkerPlaceBytes, "the world map screen's marker put on its place", missing);
            // The screen's allocations and their constructor.
            int map = One(image, sections, MapAllocBytes, "the world map screen's map made", missing);
            int frame = One(image, sections, FrameAllocBytes, "the world map screen's frame menu made", missing);
            if (map >= 0 && frame >= 0 && (Target(image, map + AllocCall, 5) != Target(image, frame + AllocCall, 5)
                                           || Target(image, map + AllocCtorCall, 5) != Target(image, frame + AllocCtorCall, 5)))
                missing.Add("the world map screen's two parts made (made otherwise)");
            int collision = One(image, sections, CollisionSwitchBytes, "the world map screen's switch of its places' boxes",
                                missing);
            if (collision >= 0)
            {
                int start = collision - CollisionSwitchFrom;
                int box = Target(image, start + CollisionBoxCall, 5), refresh = Target(image, start + CollisionRefreshCall, 5);
                if (image[start + CollisionBoxCall] != 0xE8 || image[start + CollisionRefreshCall] != 0xE8
                    || Target(image, start + CollisionBoxCallAgain, 5) != box
                    || Target(image, start + CollisionRefreshCallAgain, 5) != refresh)
                    missing.Add("the world map screen's switch of its places' boxes (its calls aren't where they were)");
                else
                {
                    places.CollisionSwitch = start;
                    places.BoxOfKind = box;
                    places.BoxRefresh = refresh;
                }
            }
            int text = One(image, sections, SetTextBytes, "the setting of a box's text", missing);
            // (1.7.1) The place nearest the cursor, its call of the distance, its loop's end; the pad's focus of it.
            int nearest = One(image, sections, NearestBytes, "the world map screen's place nearest the cursor", missing);
            if (nearest >= 0 && distance >= 0 && (Target(image, nearest + NearestCall, 5) != distance - DistanceStart
                                                  || !At(image, nearest + NearestEnd, Pattern(NearestEndBytes))
                                                  || nearest + NearestEnd + NearestEndLength + (sbyte)image[nearest + NearestEnd + 4]
                                                     != nearest + NearestTop))
            {
                missing.Add("the world map screen's place nearest the cursor (it isn't laid out as it was)");
                nearest = -1;
            }
            int focus = One(image, sections, NearestFocusBytes, "the world map screen's pad's focus of a place", missing);
            if (focus >= 0 && nearest >= 0 && Target(image, focus, 5) != nearest)
                missing.Add("the world map screen's pad's focus of a place (it asks another nearest)");
            // (1.23.1) The name of the place arrived at, drawn from a table of the game's places' (Zodi's test 52).
            int name = One(image, sections, ArrivalNameBytes, "the world map's name of the place arrived at", missing);
            if (name >= 0 && !At(image, name + ArrivalSpriteAt, Pattern(ArrivalSpriteBytes)))
                missing.Add("the world map's name of the place arrived at (its sprite isn't where it was)");
            // (1.23.2) The menu's name of its place, from the same table (Zodi's test 53).
            int menuName = One(image, sections, MenuNameBytes, "the menu's name of its place", missing);
            if (missing.Count > 0)
            {
                places.LocationRecords = places.LocationRecordLea = places.Dots = places.CollisionSwitch
                    = places.BoxOfKind = places.BoxRefresh = -1;
                places.LocationRecordReads.Clear();
                places.DotLeas.Clear();
                places.DotReads.Clear();
                return;
            }
            places.PlacePosition = position;
            places.CursorAtPlace = cursor;
            places.DistanceBound = distance + DistanceBoundFrom;
            places.DistanceRead = distance + DistanceReadFrom;
            places.ArrivedFirst = arrived + ArrivedRead;
            places.ArrivedSecond = arrived + ArrivedApart + ArrivedRead;
            places.PieceEvents = events;
            places.HelpBound = help;
            places.HelpKind = help + HelpKindFrom + HelpKindRead;
            places.HelpKindAgain = help + HelpKindAgainFrom + HelpKindAgainRead;
            places.MarkerPlace = marker;
            places.MapAlloc = map;
            places.FrameAlloc = frame;
            places.ScreenCtor = Target(image, map + AllocCtorCall, 5);
            places.SetText = Target(image, text + SetTextCall, 5);
            places.Distance = distance - DistanceStart;
            places.Nearest = nearest;
            places.NearestFocus = focus;
            places.ArrivalName = name + ArrivalNameAt;
            places.MenuName = menuName + MenuNameAt;
            places.ArrivalNameValue = Target(image, name + ArrivalNameAt, ArrivalNameLength);
        }

        /// <summary>(1.15.0) The taverns' test of a rumor told (ecx its key, edx a place; al 1 if told), whole: its row
        /// of Gossip (mov ecx, 0xB5; call), the row's situation if it has one (+ 0x24: call; test al, al), its every
        /// tavern byte (+ 0x2C), else, a place given (test esi, esi; js), the place's bit in the rumor's mask (mov eax,
        /// 0x4000; lea r8, [rip + masks]; shr eax, cl; test [r8 + rdi*4], eax), then the rumor's variable 0x2D1 plus its
        /// key not 0 (lea ecx, [rdi + 0x2D1]; call); its first four instructions (15 bytes) not looked at.</summary>
        const string RumorTestBytes =
            "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 48 63 F9 8B F2 8B D7 B9 B5 00 00 00 E8 ?? ?? ?? ?? 48 8B D8 "
            + "48 85 C0 74 16 8B 50 24 85 D2 74 09 E8 ?? ?? ?? ?? 84 C0 74 2F 80 7B 2C 00 75 2D 85 F6 78 16 B8 00 40 00 "
            + "00 4C 8D 05 ?? ?? ?? ?? 8B CE D3 E8 41 85 04 B8 74 0F 8D 8F D1 02 00 00 E8 ?? ?? ?? ?? 85 C0 75 04 32 C0 "
            + "EB 02 B0 01 48 8B 5C 24 30 48 8B 74 24 38 48 83 C4 20 5F C3";
        const int RumorTestPrologue = 15;
        /// <summary>(1.18.0) The Outfitter's stock (0x288E54): its saves of r9 and cx and pushes (its first seven
        /// instructions, 16 bytes, not looked at), then its frame, its town (movsx ebp, dx) and its list kept; its
        /// bound of the game's towns (cmp ebp, 0xF at + 0xA0) and its lea of the shops' masks' second bytes (lea r12,
        /// [rip + masks + 1] at + 0xAD).</summary>
        const string StockBytes = "4C 89 4C 24 20 66 89 4C 24 08 53 55 56 57 41 54 41 55 41 56 41 57 48 83 EC 28 33 C0 "
                                  + "0F BF EA 4D 8B E9 44 8B F0 8D 48 01 8D 50 02 44 8D 78 06";
        const int StockPrologue = 16, StockBound = 0xA0, StockMasks = 0xAD;
        const string StockBoundBytes = "83 FD 0F", StockMasksBytes = "4C 8D 25";
        /// <summary>(1.19.0) The base art's path (0xFC1C0): its pushes and frame and cookie (18 bytes, not
        /// looked at), its size, number and buffer kept, the Icon table's format by key 0x15 (the base art's), then
        /// the path made.</summary>
        const string BaseArtBytes = "40 53 56 57 48 81 EC 40 01 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 89 84 24 30 01 00 "
                                    + "00 49 63 F8 8B DA 48 8B F1 48 8D 54 24 20 41 B0 01 B9 15 00 00 00 41 B9 04 01 00 "
                                    + "00 E8";
        const int BaseArtPrologue = 18;
        /// <summary>(1.19.0) The menu's town picture (0x158E30): its tests, push and frame (17 bytes, not
        /// looked at), its cookie, the piece kept, then the number made: place 21's 14_34, else "%02d" of the Town
        /// row's + 0x2C.</summary>
        const string MenuIconBytes = "48 85 D2 0F 84 ?? ?? ?? ?? 57 48 81 EC 60 02 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 "
                                     + "89 84 24 50 02 00 00 48 8B FA 4D 85 C9 0F 84 ?? ?? ?? ?? 48 8D 4C 24 30 BA 04 01 "
                                     + "00 00 41 83 F8 15 75 0E 4C 8D 05 ?? ?? ?? ?? E8 ?? ?? ?? ?? EB 11 45 0F BF 49 2C";
        const int MenuIconPrologue = 17;
        /// <summary>(1.19.0) The menu opener's finding of its UI object (0x345469: the UI's root, + 0x10,
        /// + 0xA0, + 0x48), its thumbnail and title set (0x158CB0), the town's Town row, then the town picture's piece
        /// (+ 0x48) given the menu's town picture (its call at MenuUiIconCall).</summary>
        const string MenuUiBytes = "48 8B 0D ?? ?? ?? ?? 89 45 1F 8B B4 3A ?? ?? ?? ?? 83 FE 04 48 8B 51 10 41 0F 94 C7 44 88 "
                                   + "7D 23 48 8B 8A A0 00 00 00 48 8B 59 48 48 85 DB 0F 84 ?? ?? ?? ?? 0F 10 45 17 4C 8D 83 "
                                   + "98 00 00 00 48 8B CB F3 0F 7F 83 D8 01 00 00 66 0F 73 D8 04 66 0F 7E C7 8B D7 E8 ?? ?? "
                                   + "?? ?? 8B D7 B9 34 00 00 00 E8 ?? ?? ?? ?? 48 85 C0 0F 84 ?? ?? ?? ?? 48 8B 53 48 4C 8B "
                                   + "C8 44 8B C7 E8";
        const int MenuUiIconCall = 0x79;
        /// <summary>(1.19.0) The menu's UI object from the UI's root (+ 0x10, then + 0xA0, then + 0x48),
        /// its layouts (+ 0x18, as the thumbnail's setter 0x158D98 makes parts ready with) and its town picture's
        /// piece (+ 0x48).</summary>
        public const int UiFirst = 0x10, UiMenus = 0xA0, UiMenu = 0x48, UiLayouts = 0x18, UiMenuIcon = 0x48;

        /// <summary>(1.15.0) The taverns' list's read of a rumor's first byte (cmp bl, 0x40; jae; movsx rax, bl; mov cl,
        /// [r14 + rax*2 + read], r14 the program's start), and its loop's last key (inc ebx; cmp ebx, 0x40; jb).</summary>
        const string RumorListBytes = "80 FB 40 73 ?? 48 0F BE C3 41 8A 8C 46 ?? ?? ?? ??";
        const int RumorListKeys = 2, RumorListRead = 13;
        const string RumorLoopBytes = "FF C3 83 FB 40 0F 82";
        const int RumorLoopKeys = 4;
        /// <summary>(1.29.0) The tavern's agent's start, through its lea of the rumors' bytes less 0x19 (rdx, at + 0x44),
        /// which must be the list's read bytes less 0x19; its first seven instructions (14 bytes, its save of rbx and
        /// its first six pushes, where a hook's jump goes) not looked at.</summary>
        const string RumorAgentBytes = "48 89 5C 24 10 55 56 57 41 54 41 55 41 56 41 57 48 8D AC 24 00 FE FF FF "
                                       + "48 81 EC 00 03 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 89 85 F0 01 00 00 "
                                       + "48 8B F1 48 89 4C 24 30 48 8B 49 70 33 DB 4D 63 F1 4C 8B EA "
                                       + "48 8D 15 ?? ?? ?? ?? 41 8B F8";
        const int RumorAgentLea = 0x44, RumorAgentRead = 0x19, RumorAgentPrologue = 14;

        /// <summary>(1.15.0) Where a quest's rumors go in the program (MissingForRumors when not exactly so): the taverns'
        /// test of a rumor told, the read bytes the taverns' list reads, the keys it lists (its loop's and its read's
        /// bound the same: 64, the read's pinned, the quests' rumors numbered up to 63).</summary>
        static void FindRumors(ReadOnlySpan<byte> image, List<Section> sections, Places places)
        {
            var missing = places.MissingForRumors;
            int test = One(image, sections, RumorTestBytes, "the taverns' test of a rumor told", missing,
                           RumorTestPrologue);
            int list = One(image, sections, RumorListBytes, "the taverns' list of rumors", missing);
            var loops = Search(image, sections, Pattern(RumorLoopBytes));
            if (test < 0 || list < 0)
                return;
            int keys = image[list + RumorListKeys];
            bool looped = false;
            foreach (int at in loops)
                looped |= at > list && at - list < 0x100 && image[at + RumorLoopKeys] == keys;
            if (!looped)
            {
                missing.Add("the taverns' list of rumors (its loop's last key isn't its read's)");
                return;
            }
            int read = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(list + RumorListRead, 4));
            if (read < 0 || read + 2 * keys > image.Length)
            {
                missing.Add("the rumors' read bytes (outside the program)");
                return;
            }
            // (1.29.0) The tavern's agent, its lea of the read bytes' block the list's.
            int agent = One(image, sections, RumorAgentBytes, "the tavern's agent", missing, RumorAgentPrologue);
            if (agent < 0)
                return;
            int block = agent + RumorAgentLea + 7
                        + BinaryPrimitives.ReadInt32LittleEndian(image.Slice(agent + RumorAgentLea + 3, 4));
            if (block + RumorAgentRead != read)
            {
                missing.Add("the tavern's agent (its read bytes aren't the list's)");
                return;
            }
            places.RumorTest = test;
            places.RumorsRead = read;
            places.RumorKeys = keys;
            places.RumorAgent = agent;
        }

        /// <summary>(1.21.0) What a mod's dungeon needs (the sites' summary at Entries); else said (MissingForDungeons) and
        /// none kept.</summary>
        static void FindDungeons(ReadOnlySpan<byte> image, List<Section> sections, Places places)
        {
            var missing = places.MissingForDungeons;
            int entries = One(image, sections, EntriesBytes, "a place's settlement menu's entries", missing, EntriesPrologue);
            int block = One(image, sections, DungeonBlockBytes, "the settlement menu's test of Midlight's Deep (its list)",
                            missing);
            int screen = One(image, sections, DungeonScreenBytes,
                             "the settlement menu's test of Midlight's Deep (its screen)", missing);
            int handler = One(image, sections, DungeonHandlerBytes,
                              "the settlement menu's choosing's test of Midlight's Deep", missing);
            int floor = One(image, sections, FloorBytes, "a floor of Midlight's Deep chosen", missing);
            int setup = One(image, sections, RandomSetupBytes, "the random battle's setup", missing);
            int title = One(image, sections, RowTitleBytes, "the Deep's list's name of a floor", missing);
            int info = One(image, sections, RowInfoBytes, "the Deep's list's words of a floor", missing);
            if (missing.Count > 0)
                return;
            int test = block + DungeonBlockTest;
            var copy = Search(image, sections, Pattern(DungeonCopyBytes));
            copy.RemoveAll(at => at <= test || at > test + CopyReach);
            var outs = Search(image, sections, Pattern(FloorOutBytes));
            outs.RemoveAll(at => at <= floor || at > floor + FloorReach);
            int place = handler + DungeonHandlerLength + BinaryPrimitives.ReadInt32LittleEndian(image.Slice(handler + 2, 4));
            int read = floor + FloorPlaceRead;
            int title0 = Target(image, title + RowTitleCallAt, CallLength), info0 = Target(image, info + RowInfoCallAt, CallLength);
            if (copy.Count != 1)
                missing.Add("the settlement menu's copy of Midlight's Deep's list (not after its test)");
            else if (screen <= test || screen > test + ScreenReach)
                missing.Add("the settlement menu's test of Midlight's Deep (its screen not after its list)");
            else if (outs.Count != 1)
                missing.Add("a floor of Midlight's Deep chosen (its way out not after it)");
            else if (read + 6 + BinaryPrimitives.ReadInt32LittleEndian(image.Slice(read + 2, 4)) != place)
                missing.Add("a floor of Midlight's Deep chosen (its place read isn't the menu's)");
            else if (title0 != info0)
                missing.Add("the Deep's list's reads of a floor's row (they call two)");
            else if (places.RandomMap >= 0 && (Target(image, setup + 9, 6) != places.RandomMap
                                               || Target(image, setup + 0x14, 6) != places.RandomBattle))
                missing.Add("the random battle's setup (it reads others than the roll's keeps)");
            if (missing.Count > 0)
                return;
            places.Entries = entries;
            places.DungeonBlock = test;
            places.DungeonTown = Target(image, test + 4, 6);
            places.DungeonCopy = copy[0];
            places.DungeonScreen = screen;
            places.DungeonHandler = handler;
            places.CurrentPlace = place;
            places.FloorCall = floor + FloorCallAt;
            places.Chains = Target(image, floor + FloorCallAt, CallLength);
            places.FloorOut = outs[0] + FloorOutAt;
            places.RandomSetup = setup;
            places.RowTitleCall = title + RowTitleCallAt;
            places.RowInfoCall = info + RowInfoCallAt;
            places.RowLookup = title0;
        }

        /// <summary>(1.23.0) A mod's dungeon's battle started at once: the random battle's setup's call of its
        /// transition (kind 0) and the queue in the function it calls (its count, its list, its records' kinds; the
        /// program's start its base), and the handler's test of kind 2; else said (MissingForInstantBattles).</summary>
        static void FindInstantBattles(ReadOnlySpan<byte> image, List<Section> sections, Places places)
        {
            var missing = places.MissingForInstantBattles;
            int setup = places.RandomSetup;
            if (setup < 0)
            {
                missing.Add("the random battle's setup");
                return;
            }
            var calls = Search(image, sections, Pattern(TransitionCallBytes));
            calls.RemoveAll(at => at <= setup || at > setup + TransitionReach);
            if (calls.Count != 1)
            {
                missing.Add("the random battle's transition (its call isn't in the random battle's setup)");
                return;
            }
            int queue = Target(image, calls[0] + 2, 5);
            var blocks = Search(image, sections, Pattern(TransitionBytes));
            blocks.RemoveAll(at => at < queue || at > queue + QueueReach);
            One(image, sections, InstantBytes, "the transition's test of its kind 2", missing);
            if (blocks.Count != 1)
                missing.Add("the transition's queue (not in the function the random battle's setup calls)");
            if (missing.Count > 0)
                return;
            int block = blocks[0];
            int count = Target(image, block, 7);
            if (Target(image, block + TransitionBase, 7) != 0)
                missing.Add("the transition's queue (its base isn't the program's start)");
            else if (Target(image, block + TransitionStore, 6) != count)
                missing.Add("the transition's queue (the count it stores isn't the one it reads)");
            if (missing.Count > 0)
                return;
            places.TransitionCount = count;
            places.TransitionCommands = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(block + TransitionCommandsAt, 4));
            places.TransitionKinds = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(block + TransitionKindsAt, 4));
        }

        /// <summary>(1.25.0) A quest's start waiting at a mod's dungeon's floor: the world map's start of the event a
        /// place's chains loaded, the event it loads and its kind (the event's next 4 bytes), and the queue's count it
        /// reads (the transition's, when found); else said (MissingForFloorStarts).</summary>
        static void FindFloorStarts(ReadOnlySpan<byte> image, List<Section> sections, Places places)
        {
            var missing = places.MissingForFloorStarts;
            int start = One(image, sections, EventStartBytes, "the world map's start of an event loaded", missing,
                            EventStartPrologue);
            if (missing.Count > 0)
                return;
            int count = Target(image, start + EventStartCountAt, 6);
            int loaded = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(start + EventStartLoadedAt, 4));
            int kind = Target(image, start + EventStartKindAt, 6);
            if (Target(image, start + EventStartBaseAt, 7) != 0)
                missing.Add("the world map's start of an event loaded (its base isn't the program's start)");
            else if (kind != loaded + 4)
                missing.Add("the world map's start of an event loaded (its kind isn't after the event)");
            else if (places.TransitionCount >= 0 && count != places.TransitionCount)
                missing.Add("the world map's start of an event loaded (the queue's count it reads isn't the transition's)");
            if (missing.Count > 0)
                return;
            places.EventStart = start;
            places.LoadedEvent = loaded;
            places.LoadedKind = kind;
            places.QueueCount = count;
        }

        /// <summary>(1.23.0) The mods' places in the world map's location list: its loop's end, its grow and its row
        /// lookup (the UI's root and the menu's place, when found, the ones it reads); else said
        /// (MissingForLocations).</summary>
        static void FindLocations(ReadOnlySpan<byte> image, List<Section> sections, Places places)
        {
            var missing = places.MissingForLocations;
            int list = One(image, sections, ListBytes, "the world map's location list", missing);
            // (1.23.1) Its kinds of a town's shop (Zodi's test 52: a mod's town's panel under Settlements).
            int kinds = One(image, sections, ListKindsBytes, "the location list's kinds of a town's shop", missing);
            if (places.UiRoot < 0)
                missing.Add("the UI's root (found with the menus' art)");
            if (places.CurrentPlace < 0)
                missing.Add("Ramza's place (found with the dungeons')");
            if (missing.Count > 0)
                return;
            if (Target(image, list, 7) != places.UiRoot || Target(image, list + ListEndAt, ListEndLength) != places.UiRoot)
                missing.Add("the world map's location list (the UI's root it reads isn't the menus')");
            else if (Target(image, list + ListPlaceAt, 6) != places.CurrentPlace)
                missing.Add("the world map's location list (Ramza's place it reads isn't the menu's)");
            else if (places.Stock >= 0 && Target(image, kinds + ListKindsStockAt, 5) != places.Stock)
                missing.Add("the location list's kinds of a town's shop (the stock it asks isn't the Outfitter's)");
            if (missing.Count > 0)
                return;
            places.ListEnd = list + ListEndAt;
            places.ListGrow = Target(image, list + ListGrowAt, 5);
            places.ListRowLookup = Target(image, list + ListLookupAt, 5);
            places.ListItems = Target(image, kinds + ListKindsItemsAt, 7);
            places.ListItem = Target(image, kinds + ListKindsItemAt, 5);
        }

        /// <summary>(1.31.0) The game's giving of an event's item to the bag, whole but its first three instructions (15
        /// bytes, which another mod's hook of 14 bytes would cover): the item a signed 16-bit number (movsx rdi, dx), at
        /// most 0x104 (mov eax, x: the mods' items' room raises it, 1.26.0, as WotL Restoration's does), the count r9's
        /// low byte added to the bag's (lea r8, [rip + x], which the room moves), the copies the party wears (call x)
        /// less 99 sold (call x, the item's price) for the war funds (call x: WarFundsAdd), a sale listed where r8 points
        /// when it isn't 0.</summary>
        const string ItemGiveBytes =
            "48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18 57 48 83 EC 30 48 0F BF FA B8 ?? ?? ?? ?? 41 8B F1 49 8B D8 66 "
            + "3B F8 0F 87 ?? ?? ?? ?? 0F B7 CF E8 ?? ?? ?? ?? 4C 8D 05 ?? ?? ?? ?? 42 02 34 07 40 0F B6 CE 8D 68 9D 42 "
            + "88 0C 07 03 E9 85 ED 7E ?? 40 2A CD 42 88 0C 07 0F B7 CF E8 ?? ?? ?? ?? 8B F0 0F AF F5 8B CE E8 ?? ?? ?? ??";
        const int ItemGivePrologue = 15, ItemGiveFundsCall = 0x66;
        /// <summary>(1.31.0) The game's add to the war funds, whole but its first four instructions and its first call
        /// (18 bytes, which another mod's hook of 14 bytes would cover): variable 0x2C read (mov ecx, 0x2c; call x), the
        /// amount added, kept from 0 to 99,999,999 (0x5F5E0FF), written (call x), the total given back.</summary>
        const string WarFundsBytes =
            "40 53 48 83 EC 20 8B D9 B9 2C 00 00 00 E8 ?? ?? ?? ?? B9 2C 00 00 00 8D 14 18 33 DB 85 D2 B8 FF E0 F5 05 0F "
            + "49 DA 3B D8 0F 4F D8 8B D3 E8 ?? ?? ?? ?? 48 63 C3 48 83 C4 20 5B C3";
        const int WarFundsPrologue = 18;

        /// <summary>(1.31.0) What a quest's reward needs: the giving of an event's item and the add to the war funds,
        /// each found once, the giving's call for an item sold reaching the add; else said (MissingForRewards).</summary>
        static void FindRewards(ReadOnlySpan<byte> image, List<Section> sections, Places places)
        {
            var missing = places.MissingForRewards;
            int give = One(image, sections, ItemGiveBytes, "the game's giving of an event's item", missing,
                           ItemGivePrologue);
            int funds = One(image, sections, WarFundsBytes, "the game's add to the war funds", missing,
                            WarFundsPrologue);
            if (give < 0 || funds < 0)
                return;
            if (Target(image, give + ItemGiveFundsCall, 5) != funds)
            {
                missing.Add("the game's giving of an event's item, whose call for an item sold isn't its add to the war "
                            + "funds");
                return;
            }
            places.ItemGive = give;
            places.WarFundsAdd = funds;
        }

        /// <summary>(1.33.0) The game's making of a battle's unit from its battle file's entry, whole but its first five
        /// instructions (19 bytes, which another mod's hook of 14 bytes would cover): r9d its mode (0x82 an event's own
        /// unit), r8d kept, rdx the entry, rcx the unit; its call of the unit's setup at + 0x1A8.</summary>
        const string UnitMadeBytes =
            "48 89 5C 24 18 55 56 57 48 83 EC 50 48 8B 05 ?? ?? ?? ?? 48 33 C4 48 89 44 24 48 48 8B AC 24 90 00 00 00 41 "
            + "8B F1 44 89 05 ?? ?? ?? ?? 48 8B FA 48 8B D9 41 81 F9 82 00 00 00 74";
        const int UnitMadePrologue = 19, UnitMadeSetupCall = 0x1A8, UnitSetupJump = 0x3F;
        /// <summary>(1.33.0) The name's assignment, whole but its first three instructions (15 bytes): the unit's party
        /// byte (+ 2) read, its own text (+ 0x14C) kept in rsi, 0xFF (not from the party, a random name) compared.</summary>
        const string NameAssignBytes =
            "48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18 57 41 54 41 55 41 56 41 57 48 83 EC 20 0F B6 41 02 48 8D B1 "
            + "4C 01 00 00 41 B8 FF 00 00 00 48 8B D9 41 3A C0";
        const int NameAssignPrologue = 15;

        /// <summary>(1.33.0) What a quest's unit's own name needs: the making of a battle's unit, found once, its unit's
        /// setup ending by jumping to the name's assignment as measured (its party byte, its own text); else said
        /// (MissingForNames).</summary>
        static void FindNames(ReadOnlySpan<byte> image, List<Section> sections, Places places)
        {
            var missing = places.MissingForNames;
            int made = One(image, sections, UnitMadeBytes, "the game's making of a battle's unit", missing,
                           UnitMadePrologue);
            if (made < 0)
                return;
            int call = made + UnitMadeSetupCall;
            if (call + 5 > image.Length || image[call] != 0xE8)
            {
                missing.Add("the unit's setup (the making of a battle's unit doesn't call it where measured)");
                return;
            }
            int setup = Target(image, call, 5);
            int jump = setup + UnitSetupJump;
            if (setup < 0 || jump + 5 > image.Length || image[jump] != 0xE9
                || !At(image, Target(image, jump, 5), Pattern(NameAssignBytes, NameAssignPrologue)))
            {
                missing.Add("the name's assignment (the unit's setup doesn't end by jumping to it as measured)");
                return;
            }
            places.UnitMade = made;
        }

        /// <summary>(1.34.0) The screen's graying of a place as it shows it: its Town row (sheet 0x34, by the place:
        /// mov edx, ebx; mov ecx, 0x34; call x), the row's situation (+ 0x28) tested (call x) when it has one, gray (1)
        /// while it holds.</summary>
        const string PlaceGrayBytes =
            "8B D3 B9 34 00 00 00 E8 ?? ?? ?? ?? 48 85 C0 74 ?? 8B 50 28 85 D2 74 ?? E8 ?? ?? ?? ?? B2 01 84 C0";
        const int PlaceGrayRow = 7, PlaceGraySituation = 0x18;

        /// <summary>(1.34.0) What a mod's road shown and grayed with its places needs: the world map screen's showing of
        /// a place (MarkerState, found with the markers: the roads are looked at again each time it shows one), the
        /// game's test of a place shown (the journeys' pattern, 1.5.0) and the screen's graying of a place, each found
        /// once, the latter giving the rows' lookup and the situation's test it calls; else said
        /// (MissingForRoadLooks).</summary>
        static void FindRoadLooks(ReadOnlySpan<byte> image, List<Section> sections, Places places)
        {
            var missing = places.MissingForRoadLooks;
            if (places.MarkerState < 0)
                missing.Add("the world map screen's showing of a place");
            int shown = One(image, sections, PlaceShownBytes, "the game's test of a place shown", missing);
            int gray = One(image, sections, PlaceGrayBytes, "the screen's graying of a place", missing);
            if (shown < 0 || gray < 0 || places.MarkerState < 0)
                return;
            places.PlaceTest = shown;
            places.TownRow = Target(image, gray + PlaceGrayRow, 5);
            places.Situation = Target(image, gray + PlaceGraySituation, 5);
        }

        /// <summary>(1.23.0) A mod's dungeon's list's looks: the UI's text by its number, the row of two keys (the
        /// guide's page's read calling it), the button guide shown as the frame's mode 4 shows the Deep's (its number),
        /// the frame's mode, the About key's guide (the Deep's list's About key calling it; its guide's number), the
        /// frame's Deep list, its Thumbnail, a place's name by its number, the menu's art's setter (after the base
        /// art's path); else said (MissingForDungeonLooks).</summary>
        static void FindDungeonLooks(ReadOnlySpan<byte> image, List<Section> sections, Places places)
        {
            var missing = places.MissingForDungeonLooks;
            int text = One(image, sections, UiTextBytes, "the UI's text by its number", missing, UiTextPrologue);
            int row = One(image, sections, TwoKeyRowBytes, "a row by two keys", missing, TwoKeyRowPrologue);
            int page = One(image, sections, PageCallBytes, "the guide's page's read", missing);
            int deep = One(image, sections, DeepGuideBytes, "the Deep's list's button guide", missing);
            One(image, sections, FrameModeBytes, "the world map frame's mode", missing);
            int about = One(image, sections, AboutBytes, "the About key's guide", missing, AboutPrologue);
            int key = One(image, sections, AboutKeyBytes, "the Deep's list's About key", missing);
            One(image, sections, DeepKeyBytes, "the frame's Deep list", missing);
            int thumbnail = One(image, sections, ThumbnailBytes, "the Deep's list's art", missing);
            int name = One(image, sections, PlaceNameBytes, "a place's name by its number", missing, PlaceNamePrologue);
            int art = One(image, sections, ArtSetBytes, "the menu's art's setter", missing);
            int remake = One(image, sections, TextRemakeBytes, "a text made again from its number", missing,
                             TextRemakePrologue);
            if (missing.Count > 0)
                return;
            int show = Target(image, deep + DeepGuideJump, 5);
            if (Target(image, page + PageCallAt, 5) != row)
                missing.Add("the guide's page's read (it calls another than the row of two keys)");
            else if (!At(image, show, Pattern(GuideCallBytes)))
                missing.Add("the Deep's list's button guide (its showing isn't where it jumps)");
            else if (Target(image, key + AboutKeyCallAt, 5) != about)
                missing.Add("the Deep's list's About key (it calls another than the About key's guide)");
            else if (BinaryPrimitives.ReadInt32LittleEndian(image.Slice(thumbnail + ThumbnailAt, 4)) != DeepThumbnail)
                missing.Add($"the Deep's list's art (its Thumbnail isn't kept at + {DeepThumbnail:X})");
            else if (places.BaseArt >= 0 && Target(image, art + ArtPathCallAt, 5) != places.BaseArt)
                missing.Add("the menu's art's setter (the path it is given isn't the base art's)");
            else if (Target(image, remake + TextRemakeCallAt, 5) != text)
                missing.Add("a text made again from its number (it calls another than the UI's text)");
            if (missing.Count > 0)
                return;
            places.UiText = text;
            places.TwoKeyRow = row;
            places.GuideShow = Target(image, show + GuideCallAt, 5);
            places.DeepGuide = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(deep + DeepGuideAt, 4));
            places.AboutOpen = about;
            places.AboutGuide = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(about + AboutGuideAt, 4));
            places.PlaceNameText = name;
            places.ArtSetter = Target(image, art + ArtSetCallAt, 5);
            places.TextRemake = remake;
        }

        /// <summary>(1.18.0) What a mod's town's menu needs: the Outfitter's stock with its bound of the game's towns and
        /// its shops' masks; else said (MissingForTownMenus) and none kept.</summary>
        static void FindTownMenus(ReadOnlySpan<byte> image, List<Section> sections, Places places)
        {
            var missing = places.MissingForTownMenus;
            int stock = One(image, sections, StockBytes, "the Outfitter's stock", missing, StockPrologue);
            if (stock < 0)
                return;
            if (!At(image, stock + StockBound, Pattern(StockBoundBytes))
                || !At(image, stock + StockMasks, Pattern(StockMasksBytes)))
            {
                missing.Add("the Outfitter's stock (its bound of the towns or its masks' read isn't where it was)");
                return;
            }
            int masks = Target(image, stock + StockMasks, 7) - 1;
            if (masks < 0 || masks + 2 * Framework.ShopItems > image.Length)
            {
                missing.Add("the shops' masks (outside the program)");
                return;
            }
            places.Stock = stock;
            places.ShopMasks = masks;
        }

        /// <summary>(1.26.0) What the stock function calls, read from its own code (where each is in it, checked by its
        /// bytes): the list's sort, the check of an item against the unit, the units' table; (1.27.0) read here for
        /// both stock hooks (a mod's town's, Hooks.cs; the game's towns' for the mods' items, ItemHooks.cs). `stock` is
        /// where it starts, `code` its first StockSortAt + 5 bytes; (0, 0, 0) when its bytes aren't the game's this was
        /// made for.</summary>
        public static (int, int, int) StockCalls(ReadOnlySpan<byte> code, int stock)
        {
            if (code.Length < StockSortAt + 5 || code[StockSortAt] != 0xE8 || code[StockEquipsAt] != 0xE8
                || !At(code, StockUnitsAt, Pattern("48 8B 84 C1")))
                return (0, 0, 0);
            return (stock + StockSortAt + 5 + BinaryPrimitives.ReadInt32LittleEndian(code.Slice(StockSortAt + 1, 4)),
                    stock + StockEquipsAt + 5 + BinaryPrimitives.ReadInt32LittleEndian(code.Slice(StockEquipsAt + 1, 4)),
                    BinaryPrimitives.ReadInt32LittleEndian(code.Slice(StockUnitsAt + 4, 4)));
        }

        public const int StockSortAt = 0x250, StockEquipsAt = 0x145, StockUnitsAt = 0x132;

        /// <summary>(1.19.0) What a mod's town's own art and picture in its menu need: the base art's path,
        /// the menu's town picture, and the menu opener's finding of its UI object calling it; else said
        /// (MissingForMenuArt) and none kept.</summary>
        static void FindMenuArt(ReadOnlySpan<byte> image, List<Section> sections, Places places)
        {
            var missing = places.MissingForMenuArt;
            int art = One(image, sections, BaseArtBytes, "the base art's path", missing, BaseArtPrologue);
            int icon = One(image, sections, MenuIconBytes, "the menu's town texture", missing, MenuIconPrologue);
            int ui = One(image, sections, MenuUiBytes, "the menu's UI object", missing);
            if (art < 0 || icon < 0 || ui < 0)
                return;
            if (Target(image, ui + MenuUiIconCall, 5) != icon)
            {
                missing.Add("the menu's UI object (its town texture's call isn't the menu's town texture)");
                return;
            }
            int root = Target(image, ui, 7);
            if (root < 0 || root + 8 > image.Length)
            {
                missing.Add("the UI's root (outside the program)");
                return;
            }
            places.BaseArt = art;
            places.MenuIcon = icon;
            places.UiRoot = root;
        }

        /// <summary>(1.7.1) What a save standing on a mod's place no mod gives now needs: the game's load of a save's
        /// state, its lea of the variables and their copy from the save where they were, else said
        /// (MissingForSaveFallback).</summary>
        static void FindSaveFallback(ReadOnlySpan<byte> image, List<Section> sections, Places places)
        {
            var missing = places.MissingForSaveFallback;
            int load = One(image, sections, SaveLoadBytes, "the game's load of a save", missing);
            if (load < 0)
                return;
            if (!At(image, load + SaveLoadBank, Pattern(SaveLoadBankBytes))
                || !At(image, load + SaveLoadCopy, Pattern(SaveLoadCopyBytes)))
            {
                missing.Add("the game's load of a save (its copy of the variables isn't where it was)");
                return;
            }
            places.SaveLoad = load;
            places.SaveBank = Target(image, load + SaveLoadBank, 7);
            // (1.35.0) The party it fills: what a save's units wear.
            if (At(image, load + SaveLoadRoster, Pattern("48 8D 15 ?? ?? ?? ??"))
                && At(image, load + SaveLoadStride, Pattern(SaveLoadStrideBytes)))
                places.Roster = Target(image, load + SaveLoadRoster, 7);
            else
                places.MissingForRoster.Add("the game's load of a save (its copy of the party isn't 54 units of 0x258 "
                                            + "bytes where it was)");
        }

        public static Places Find(ReadOnlySpan<byte> image)
        {
            var places = new Places();
            List<Section> sections;
            try
            {
                sections = Finder.Sections(image);
            }
            catch (InvalidOperationException e)
            {
                places.Missing.Add($"the program ({e.Message})");
                return places;
            }
            var sheet = Search(image, sections, Pattern(SheetInitBytes, SheetInitPrologue));
            if (sheet.Count == 1)
                places.SheetInit = sheet[0];
            else
                places.Missing.Add($"the tables' setup ({sheet.Count} places like it, not 1)");
            var reader = Search(image, sections, Pattern(ScriptReaderBytes, ScriptReaderPrologue));
            if (reader.Count == 1)
            {
                places.ScriptReader = reader[0];
                places.ScriptMode = Target(image, reader[0] + ScriptModeLoad, 7);
            }
            else
                places.Missing.Add($"the scripts' reader ({reader.Count} places like it, not 1)");
            var variables = Search(image, sections, Pattern(VariablesBytes, VariablesPrologue));
            var lookup = Pattern(LookupBytes, LookupPrologue);
            int events = 0, world = 0;
            foreach (int at in variables)
            {
                bool isEvents = At(image, at + VariablesFork, Pattern(EventFork));
                bool isWorld = At(image, at + VariablesFork, Pattern(WorldFork));
                int call = at + VariablesLookup;
                if (isEvents == isWorld || call + 5 > image.Length || image[call] != 0xE8)
                    continue;
                int find = Target(image, call, 5);
                if (!At(image, find, lookup))
                    continue;
                int bank = Target(image, find + LookupLoad, 7);
                if (isEvents)
                {
                    events++;
                    places.EventVariables = at;
                    places.EventBank = bank;
                }
                else
                {
                    world++;
                    places.WorldVariables = at;
                    places.WorldBank = bank;
                }
            }
            if (variables.Count != 2 || events != 1 || world != 1)
            {
                places.Missing.Add($"the variables' two functions ({variables.Count} places like them, {events} the "
                                   + $"events', {world} the world map's)");
                places.EventVariables = places.WorldVariables = places.EventBank = places.WorldBank = -1;
            }
            var progress = Search(image, sections, Pattern(ProgressBytes, ProgressPrologue));
            if (progress.Count == 1)
                places.Progress = progress[0];
            else
                places.Missing.Add($"the game's progress ({progress.Count} places like it, not 1)");
            var travel = Search(image, sections, Pattern(TravelCheckBytes, TravelCheckPrologue));
            if (travel.Count == 1)
            {
                var reads = new HashSet<int>();
                foreach (var (at, length) in PendingEventReads)
                    reads.Add(travel[0] + at + length
                              + BinaryPrimitives.ReadInt32LittleEndian(image.Slice(travel[0] + at + 2, 4)));
                if (reads.Count == 1)
                {
                    places.TravelCheck = travel[0];
                    foreach (int read in reads)
                        places.PendingEvent = read;
                }
                else
                    places.MissingForTravel.Add($"the event waiting where a travel starts ({reads.Count} places "
                                                + "read for it, not 1)");
            }
            else
                places.MissingForTravel.Add($"the world map's travel check ({travel.Count} places like it, not 1)");
            // (1.2.4) The travel's state, from where travel start asks the check found.
            var state = new List<int>();
            if (places.TravelCheck >= 0)
                foreach (int at in Search(image, sections, Pattern(TravelStateBytes)))
                    if (Target(image, at + TravelCheckCall, 5) == places.TravelCheck)
                        state.Add(at);
            if (state.Count == 1)
            {
                int at = state[0];
                // test byte [rip + x], 1 is 7 bytes, x at its third; the cmp and mov 7, x at their fourth.
                places.TravelFlags = at + TravelFlagsTest + 7
                                     + BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at + TravelFlagsTest + 2, 4));
                places.TravelLegs = Target(image, at + TravelLegsCompare, 7);
                places.TravelDone = Target(image, at + TravelDoneSet, 7);
            }
            else
                places.MissingForPassing.Add($"the travel's state ({state.Count} places ask the travel check so, not 1)");
            // (1.2.5) The world map's test of a character, the party's units and the pointer it reads.
            var party = Search(image, sections, Pattern(PartyTestBytes, PartyTestPrologue));
            if (party.Count == 1)
            {
                places.PartyTest = party[0];
                places.Party = Target(image, party[0] + PartyUnitsLoad, 7);
                places.PartyMode = Target(image, party[0] + PartyModeLoad, 7);
            }
            else
                places.MissingForMarkers.Add($"the world map's test of a character ({party.Count} places like it, not 1)");
            var marker = Search(image, sections, Pattern(MarkerStateBytes, MarkerStatePrologue));
            if (marker.Count == 1)
                places.MarkerState = marker[0];
            else
                places.MissingForMarkers.Add($"the world map screen's markers ({marker.Count} places like it, not 1)");
            var child = Search(image, sections, Pattern(ChildPieceBytes));
            if (child.Count == 1)
            {
                places.ChildPiece = child[0];
                places.BoxNamed = Target(image, child[0] + ChildPieceBoxCall, 5);
            }
            else
                places.MissingForMarkers.Add($"the layouts' finding of a piece by its name ({child.Count} places like it, "
                                             + "not 1)");
            var change = Search(image, sections, Pattern(PictureChangeBytes));
            if (change.Count == 1)
            {
                int at = change[0];
                places.PartsReady = Target(image, at + PartsReadyCall, 5);
                places.StringMake = Target(image, at + StringMakeCall, 5);
                places.StringAssign = Target(image, at + StringAssignCall, 5);
                places.StringRelease = Target(image, at + StringReleaseCall, 5);
                places.StringPool = Target(image, at + StringPoolLoad, 7);
            }
            else
                places.MissingForMarkers.Add($"the world map screen's change of a texture ({change.Count} places like it, "
                                             + "not 1)");
            // (1.3.0) What the mods' own places need: the finding of a piece and the change of a picture as the
            // markers do, the screen's setup of its places' pieces, and a box copied, moved, put in a layer, its
            // piece's animations played and stopped.
            if (places.ChildPiece < 0)
                places.MissingForPlaces.Add(places.MissingForMarkers.Find(m => m.StartsWith("the layouts' finding",
                                                                                             StringComparison.Ordinal))!);
            if (places.PartsReady < 0)
                places.MissingForPlaces.Add(places.MissingForMarkers.Find(m => m.StartsWith(
                    "the world map screen's change of a texture", StringComparison.Ordinal))!);
            var setup = Search(image, sections, Pattern(MapSetupBytes, MapSetupPrologue));
            if (setup.Count == 1 && At(image, setup[0] + MapSetupPieces, Pattern(MapSetupPiecesBytes)))
                places.MapSetup = setup[0];
            else
                places.MissingForPlaces.Add(setup.Count == 1
                    ? "the world map screen's keeping of its places' pieces (not where it was)"
                    : $"the world map screen's setup ({setup.Count} places like it, not 1)");
            foreach (var (what, bytes, keep) in new (string, string, Action<int>)[]
                     {
                         ("the layouts' copy of a box", PieceCopyBytes, at => places.PieceCopy = at),
                         ("the layouts' move of a box", PieceMoveBytes, at => places.PieceMove = at),
                         ("the layouts' putting of a box in a layer", PieceAddBytes, at => places.PieceAdd = at),
                         ("the layouts' playing of an animation", AnimationPlayBytes, at => places.AnimationPlay = at),
                         ("the layouts' stopping of a piece's animations", AnimationsStopBytes,
                          at => places.AnimationsStop = at),
                     })
            {
                var found = Search(image, sections, Pattern(bytes));
                if (found.Count == 1)
                    keep(found[0]);
                else
                    places.MissingForPlaces.Add($"{what} ({found.Count} places like it, not 1)");
            }
            // (1.20.0) One animation stopped by its name: the call the stopping of every one makes for each.
            if (places.AnimationsStop >= 0)
                places.AnimationStop = Target(image, places.AnimationsStop + AnimationsStopOne, 5);
            // (1.4.0) What the mods' own roads need: all the places need, the screen's keeping of its Route piece in
            // its setup, and a box sized.
            places.MissingForRoads.AddRange(places.MissingForPlaces);
            if (places.MapSetup >= 0 && !At(image, places.MapSetup + MapSetupRoute, Pattern(MapSetupRouteBytes)))
                places.MissingForRoads.Add("the world map screen's keeping of its Route piece (not where it was)");
            var sized = Search(image, sections, Pattern(BoxSizeBytes));
            if (sized.Count == 1)
                places.BoxSize = sized[0];
            else
                places.MissingForRoads.Add($"the layouts' sizing of a box ({sized.Count} places like it, not 1)");
            // (1.5.0) What travel along the mods' roads needs: the path search with its table, its read of a road shown
            // and its loop to 51; the walk's setup reading the same table; the travel's read of its last road's
            // record, the same table counted from the program's start, the path the travel's own; the test of a
            // place shown, reading the variables as the path search does.
            var search = Search(image, sections, Pattern(PathSearchBytes, 15));
            if (search.Count == 1)
            {
                int at = search[0];
                // cmp dword [rip + x], 16: x from its third byte, counted from the instruction's end.
                int depth = at + PathSearchDepth + 7
                            + BinaryPrimitives.ReadInt32LittleEndian(image.Slice(at + PathSearchDepth + 2, 4));
                if (!At(image, at + PathSearchLoop, Pattern(PathSearchLoopBytes))
                    || Target(image, at + PathSearchLoop + 3, 6) != at + PathSearchLoopStart)
                    places.MissingForJourneys.Add("the path search's loop over the roads (not where it was)");
                else if (!At(image, at + PathSearchCost, Pattern(PathSearchCostBytes))
                         || !At(image, at + PathSearchDepthOn, Pattern(PathSearchDepthOnBytes))
                         || !At(image, at + PathSearchCostOn, Pattern(PathSearchCostOnBytes))
                         || Target(image, at + PathSearchDepthOn, 7) != depth
                         || Target(image, at + PathSearchCostOn, 7) != Target(image, at + PathSearchCost, 7))
                    places.MissingForJourneys.Add("the path search's count of roads taken and their cost (not where they "
                                                  + "were)");
                else
                {
                    places.PathSearch = at;
                    places.RoadRecords = Target(image, at + PathSearchTable, 7);
                    places.VariableGet = Target(image, at + PathSearchCall, 5);
                    places.SearchDepth = depth;
                    places.SearchCost = Target(image, at + PathSearchCost, 7);
                }
            }
            else
                places.MissingForJourneys.Add($"the path search ({search.Count} places like it, not 1)");
            // The others read the path search's table and variables: looked for once it is found (else it alone is
            // said).
            if (places.PathSearch >= 0)
            {
                var walk = Search(image, sections, Pattern(WalkSetupBytes));
                if (walk.Count == 1 && Target(image, walk[0] + WalkSetupTable, 7) == places.RoadRecords)
                    places.WalkSetup = walk[0];
                else
                    places.MissingForJourneys.Add(walk.Count == 1
                        ? "the walk's setup of a road (it reads another table)"
                        : $"the walk's setup of a road ({walk.Count} places like it, not 1)");
                var last = Search(image, sections, Pattern(LastRoadBytes));
                if (last.Count == 1 && Target(image, last[0] + 0x0E, 7) == 0
                    && BinaryPrimitives.ReadInt32LittleEndian(image.Slice(last[0] + LastRoadTable + 4, 4)) == places.RoadRecords
                    && (places.TravelFlags < 0
                        || BinaryPrimitives.ReadInt32LittleEndian(image.Slice(last[0] + LastRoadPath, 4)) == places.TravelFlags + 0x18))
                    places.LastRoad = last[0];
                else
                    places.MissingForJourneys.Add(last.Count == 1
                        ? "the travel's read of its last road (it reads another table or path)"
                        : $"the travel's read of its last road ({last.Count} places like it, not 1)");
                var shown = Search(image, sections, Pattern(PlaceShownBytes));
                if (shown.Count == 1 && Target(image, shown[0] + PlaceShownCall, 5) == places.VariableGet)
                    places.PlaceShown = shown[0];
                else
                    places.MissingForJourneys.Add(shown.Count == 1
                        ? "the world map's test of a place shown (it reads the variables otherwise)"
                        : $"the world map's test of a place shown ({shown.Count} places like it, not 1)");
            }
            if (places.SheetInit < 0)
                places.MissingForJourneys.Add("the tables' setup (the roads' rows go in as it reads them)");
            if (!places.Journeys)
                places.PathSearch = places.RoadRecords = places.VariableGet = places.WalkSetup = places.LastRoad
                    = places.PlaceShown = places.SearchDepth = places.SearchCost = -1;
            // (1.6.0) What random battles on arriving by the mods' roads need: the roll with its table of the battle
            // grounds' entrances (all 19 inside the program), and its two calls, each calling it.
            var roll = Search(image, sections, Pattern(BattleRollBytes));
            if (roll.Count == 1)
            {
                int table = Target(image, roll[0] + BattleRollTable, 7);
                if (table < 0 || table + BattleGrounds * BattleGroundBytes > image.Length)
                    places.MissingForRoadBattles.Add("the random battles' table (outside the program)");
                else
                {
                    places.BattleRoll = roll[0];
                    places.BattleTable = table;
                }
            }
            else
                places.MissingForRoadBattles.Add($"the random battles' roll ({roll.Count} places like it, not 1)");
            if (places.BattleRoll >= 0)
            {
                foreach (var (bytes, call, what, forced) in new[]
                         {
                             (BattleRollArrivingBytes, BattleRollArrivingCall, "the travel's roll of a random battle as it "
                                                                              + "arrives", false),
                             (BattleRollForcedBytes, BattleRollForcedCall, "the world map's battle on the ground it stands "
                                                                          + "on", true),
                         })
                {
                    var found = Search(image, sections, Pattern(bytes));
                    if (found.Count == 1 && Target(image, found[0] + call, 5) == places.BattleRoll)
                    {
                        if (forced)
                            places.BattleRollForced = found[0] + call;
                        else
                            places.BattleRollArriving = found[0] + call;
                    }
                    else
                        places.MissingForRoadBattles.Add(found.Count == 1
                            ? $"{what} (it calls another)"
                            : $"{what} ({found.Count} places like it, not 1)");
                }
            }
            if (!places.RoadBattles)
                places.BattleRoll = places.BattleTable = places.BattleRollArriving = places.BattleRollForced = -1;
            // (1.17.0) What a mod's battle ground's own random battles need besides: where the roll keeps its choice.
            if (places.BattleRoll >= 0)
            {
                foreach (var (bytes, what) in new[]
                         {
                             (RandomSquadBytes, "the random battles' keep of their squad"),
                             (RandomChoiceBytes, "the random battles' keep of their battle and map"),
                         })
                {
                    var found = Search(image, sections, Pattern(bytes));
                    if (found.Count == 1 && found[0] > places.BattleRoll && found[0] < places.BattleRoll + RollReach)
                    {
                        if (bytes == RandomSquadBytes)
                            places.RandomSquad = Target(image, found[0] + RandomSquadStore, 6);
                        else
                        {
                            places.RandomBattle = Target(image, found[0] + RandomBattleStore, 6);
                            places.RandomMap = Target(image, found[0] + RandomMapStore, 6);
                        }
                    }
                    else
                        places.MissingForGroundBattles.Add(found.Count == 1
                            ? $"{what} (outside the random battles' roll)"
                            : $"{what} ({found.Count} places like it, not 1)");
                }
            }
            else
                places.MissingForGroundBattles.Add("the random battles' roll");
            if (!places.GroundBattles)
                places.RandomSquad = places.RandomBattle = places.RandomMap = -1;
            FindDestinations(image, sections, places);
            FindSaveFallback(image, sections, places);
            FindRumors(image, sections, places);
            FindTownMenus(image, sections, places);
            FindMenuArt(image, sections, places);
            FindDungeons(image, sections, places);
            FindInstantBattles(image, sections, places);
            FindFloorStarts(image, sections, places);
            FindLocations(image, sections, places);
            FindDungeonLooks(image, sections, places);
            FindRewards(image, sections, places);
            FindNames(image, sections, places);
            FindRoadLooks(image, sections, places);
            var encounter = Search(image, sections, Pattern(EncounterBytes, EncounterPrologue));
            if (encounter.Count == 1)
                places.Encounter = encounter[0];
            else
                places.MissingForBattles.Add($"the battles' units ({encounter.Count} places like it, not 1)");
            // Both places that load a battle set the same number; the getter's own first instruction
            // reads it too, unless another mod's hook stands there.
            var set = Search(image, sections, Pattern(EncounterSetBytes));
            var numbers = new HashSet<int>();
            foreach (int at in set)
                numbers.Add(Target(image, at + EncounterSetStore, 6));
            if (set.Count == 2 && numbers.Count == 1)
            {
                int number = Target(image, set[0] + EncounterSetStore, 6);
                if (places.Encounter >= 0 && image[places.Encounter] == 0x8B && image[places.Encounter + 1] == 0x05
                    && Target(image, places.Encounter, 6) != number)
                    places.MissingForBattles.Add("the battle's number (the battles' units read another)");
                else
                    places.EncounterNumber = number;
            }
            else
                places.MissingForBattles.Add($"the battle's number ({set.Count} places set it, {numbers.Count} numbers)");
            if (!places.Battles)
                places.Encounter = places.EncounterNumber = -1;
            return places;
        }
    }
}
