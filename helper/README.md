# Mod Studio Framework

A Reloaded-II mod, part of The Ivalice Chronicles Mod Studio (GPL-3.0, as
Mod Studio), that applies the event setup changes a mod made with Mod
Studio lists, and (since 1.1.0) the side quests' framework: it plays the
side quests mods give, numbering what each one names as the game starts.
Zodi's choice, 21 October 2026: "Lets go with "One shared helper mod"",
called "Mod Studio Event Setup", shipped as "Its own release, and in Mod
Studio"; and, 26 October: "If we need to expand the capabilities of Mod
Studio Event Setup as a mod framework to achieve any part of this that we
cannot already do feel free to".

**Its name** (1.22.0, Zodi's list, his eighth, 2 November): "the name
"Mod Studio Event Setup" does not really reflect what it is now that it is
more of a modding framework, so we should change the name. We should also
change the description to something shorter and simple and mention to the
user to place it directly after the mod loader in their load order." His
choice: Mod Studio Framework, its description "Needed by mods made with
The Ivalice Chronicles Mod Studio: it adds their side quests, places,
roads, dungeons, maps and event changes to the game. Place it directly
after the mod loader in your load order." Its mod id
(`fftivc.utility.modstudio.eventsetup`), its folder, its files' names
(`ModStudioEventSetup.dll`) and its GitHub repository are as before: every
mod made names it by that id, and Reloaded-II finds and updates it by it.
Each line of its log starts `[Mod Studio Framework]`.

## Why it exists

Every event has a setup record: its map, weather, time of day, two pieces
of music, enemy battle, deploy areas, what follows it and its battle rules.
The game keeps these 887 records of 24 bytes in its program
(`FFT_enhanced.exe`), not in a table the mod loader changes, so a mod
can't change them with data alone. This helper changes them in the running
game, as the game starts, from each enabled mod's `EventSetup.json`.

`mod_studio/event_setup.py` describes the records (measured on Zodi's
program) and writes and reads the file; the Event Editor shows each event's
record and changes it; Export Mod writes the file beside the mod's
`ModConfig.json`, lists this helper among the mod's dependencies (with
where Reloaded-II fetches it), and puts Mod Studio's copy of the helper
beside the mod.

## What it does

As the game starts (its `StartEx`):

1. It finds the table in the game's program as loaded, never at a fixed
   address: by WotL Restoration's pattern in the code (`48 8D 1D ?? ?? ??
   ?? 41 8B D4 BD 27 00 00 00`, a `lea` of the table), else by the
   records' own bytes (events 1, 2 and 3 in a row outside the code). It
   reads the table as far as its records go (empty slots among them read
   past, 2,048 slots at the most), so a game update that moves the table,
   or gives it more or fewer events, leaves it found. Every record must be
   laid out as the game's are (bytes 21 and 23 zero, what follows 0, 128,
   129 or 130, night and Ramza required 0 or 1, as in all 713 of the
   game's), events 1 and 2 first, each event higher than the one before,
   at least 480 records. If it isn't found, or an update laid the records
   out otherwise, it changes nothing and says why in Reloaded-II's log,
   naming the program and its size, so no mod's change goes into the wrong
   byte. (Since 1.0.1; 1.0.0 assumed 887 slots and checked only the
   events' order.)
2. It notes every mod Reloaded-II loads, in the order it loads them.
3. Once Reloaded-II has loaded them all (`OnModLoaderInitialized`), it reads
   each one's `EventSetup.json` (at the mod's top, beside `ModConfig.json`)
   and changes the fields it names, event by event; the game's own values
   stay where no mod says otherwise. Of two mods changing one field, the
   later in Reloaded-II's order wins, and the log says whose it took over.
   A mod loaded later, while the game runs, is applied as it loads.

Each change is a line in Reloaded-II's log, beginning `[Mod Studio Event
Setup]`, after the line saying it found the table (`found the game's event
setup table (713 events).`): `Gariland Music Test: event 9's Music1 3 to
66`. Only a table not found says how it looked and in which program, with
its size (since 1.0.2: Zodi asked on 22 October for the log to hold only
what users need to debug; 1.0.1's found line said "by WotL Restoration's
pattern, in FFT_enhanced.exe of 12,158,720 bytes" too).
Seen in the game on 21 October: Gariland's battle played Ovelia's Theme,
and on 048 with the highlight panels Mod Studio made. What it can't
apply (an unknown field, a value the field can't hold, an event the game
has no record of) is left out and said.

With WotL Restoration installed too, the two meet only where both change
the same event's field: WotL Restoration's DLL changes its own events'
records (578 and 579 among them).

## The file a mod gives it

`EventSetup.json`, as Mod Studio writes it (`event_setup.file_text`):

```json
{
  "Helper": "fftivc.utility.modstudio.eventsetup",
  "Version": 1,
  "Events": [
    {"Event": 9, "Music1": 66},
    {"Event": 10, "Map": 85, "Weather": 2}
  ]
}
```

Per event, only the fields changed, by these names (without case): `Map`,
`Weather` (byte 3's low half), `Arrangement` (its high half), `Night`,
`Music1`, `Music2`, `EnemyBattle`, `DeployArea1`, `DeployArea2`,
`Portrait`, `PortraitUnit`, `SceneUnits`, `RamzaRequired`, `NextEvent`,
`AfterEvent` (128 the world map, 129 the next event, 130 a reset),
`BattleRules`. Each a whole number the field holds (`BattleRules` two
bytes since 1.1.0, as the program reads it).

## The side quests' framework (1.1.0 to 1.29.0)

Zodi's goal (26 October): "Adding new events on new maps for new battles
while maintaining compatibility so different modders can create hundreds
of new side quests that users can have loaded and can play"; his rule: a
modder never chooses a number. A side quest's mod names everything it adds,
and this helper gives each name a number of the game's as the game starts,
the same every time, never one number to two names.

**A quest** is a folder of a mod, `ModStudioQuests/<quest>/`, holding
`quest.json` and its files (`mod_studio/side_quests.py` writes and reads
it; `QuestFile.cs` reads it here and says the same problems):

```json
{
  "Format": "Mod Studio side quest",
  "Version": 1,
  "Name": "Ambush at Gariland",
  "Marker": "#E03030",
  "Flags": ["beaten"],
  "Battles": [{"Name": "ambushers", "Units": "ambushers.entd"}],
  "Events": [
    {"Name": "ambush", "Battle": {"Units": "ambushers", "Start": "ambush opening", "Won": "ambush won"},
     "Setup": {"Map": 22, "Music1": 3, "DeployArea1": 256, "RamzaRequired": 1}},
    {"Name": "ambush opening", "Script": "opening.e",
     "Words": "nxd/text/scenario/msq_modstudio_test15_battle_ambush_ambush_opening.pzd"},
    {"Name": "ambush won", "Script": "won.e",
     "Words": "nxd/text/scenario/msq_modstudio_test15_battle_ambush_ambush_won.pzd",
     "FlagsInScript": [{"At": 28, "Flag": "beaten"}, {"At": 31, "Flag": "beaten"}]}
  ],
  "Starts": [
    {"Place": 6, "When": [{"Variable": 110, "AtLeast": 3}, {"Flag": "beaten", "Is": 0}], "Event": "ambush",
     "Passing": "Waits"}
  ]
}
```

- (1.2.5) Its Marker, if it wants one: a color, `#` and six hex digits
  (red, green, blue). Where one of its starts waits, the world map shows
  the game's quest marker there in that color (below, 4).
- Names for everything the quest adds: its events, flags and (1.2.0)
  battles. Numbers only for the game's own things: a map, music, a deploy
  area, a world map place (0 to 46), a game variable (110, the story's
  progress), a battle of the game's.
- An event: its script in the folder, its words (a `.pzd` under the mod's
  `FFTIVC/data/enhanced/`, the path without the language), its setup by
  `EventSetup.json`'s names (not `BattleRules`, the framework's; its
  `NextEvent` names the quest's own event: a battle event too, and the
  scene goes straight into the battle on the same visit, as the game's
  scene 69 goes into its battle 70), and where its flags' numbers go in
  the script (each a variable command's variable). (1.11.0) A copy of one
  of the game's scenes may say which (`"From": 160`, 1 to 886): the map's
  doors and moving parts then play as that event's (below, A copied
  scene's doors).
- (1.2.0) A battle: a file of 640 bytes, its 16 units as the game's battle
  files hold a battle. A battle event has no script: it names its units (a
  battle of the quest's, or the game's by number to 32,767), the event
  that plays as it starts (or none) and the one once every enemy is
  beaten; those two play with its setup. `EnemyBattle` and `SceneUnits`
  may name a quest's battle. (1.14.0) Its own deploy areas (`Deploy`), in
  place of its setup's (below, A battle's own deploy areas).
- A start: a world map place, conditions (a game variable is, at least or
  at most a number; a quest flag is 0 or 1; a character in the party) and
  the event it loads (a scene, or a battle). A quest's later steps are
  starts elsewhere whose conditions are the flags its earlier steps set
  (test 17: Gariland, then Gariland again, then Mandalia Plains). (1.2.4)
  And what a travel passing through its place does (Zodi: "these should
  all be optional features for modders if they want them"): `"Passing":
  "Waits"` (the default) goes on, and the event plays when the place is
  chosen; `"Stops"` stops there and plays it, as the game's own events
  do.
- (1.15.0) Its tavern rumors (`Rumors`): each its title and words, the
  towns whose taverns tell it, when it is told (conditions as a start's)
  and the flag it sets once it is read, which a start may wait for (below,
  Tavern rumors).

**As the game starts**, once Reloaded-II has loaded every mod, and only
when some mod gives a quest (else nothing is hooked, as with 1.0.2):

1. It reads every mod's quests, in Reloaded-II's order (one it can't use is
   left out, saying why) and the event numbers other mods ship scripts for.
2. It gives each name a number, kept in `Numbers.json` in Reloaded-II's
   settings folder for this mod (`User/Mods/fftivc.utility.modstudio.
   eventsetup/`, which an update leaves alone; else this mod's folder;
   since 1.13.0 in two more copies, below "The numbers kept three times"):
   events from the numbers no setup record, script of the game's or any
   mod's uses (up to 886; since 1.9.0 on past it, to 8,191, once the game's
   event tables have room: below); each scene a start loads an opening of its own (the game's
   world map scenes all start so); flags 4096 to 6815 (6783 since 1.13.0); battle rules keys
   16,384 to 32,767; scenes', words files' and deploy prompts' keys from
   900,000; (1.2.0) battles 4096 to 32,767; (1.14.0) a battle's own deploy
   areas' squads 768 to 4,095; (1.15.0) the quests' tavern rumors 27 to
   63; (1.17.0) a battle ground's own random battles' battles, squads and
   deploy prompts as a quest battle's. A number given never goes to
   another name, even after its quest is taken away; a number the game or
   another mod's script comes to use moves, said.
3. It writes the quests' events' setup records into the empty slots after
   the game's (713 on), which the program's search finds; (1.9.0) first
   giving the game's event setup and finish tables room for 8,192 events
   (below, "Room for hundreds of quests").
4. It hooks four of the game's functions (`Places.cs` finds each by its
   own bytes; `Hooks.cs`), through Reloaded-II's shared hooks: the tables'
   setup (each table the quests add rows to is given a copy of the file it
   loaded with their rows after its own: the world map's starts after each
   place's chains, so the story's and other mods' come first; battle
   rules; scenes and words files; (1.2.0) the battles' units table and
   deploy prompts; and `EventId`'s rows of the quests' events made as the
   game's), the scripts' reader (a quest's script handed over at its
   number), and the events' and the world map's variable functions (a
   quest flag kept in the 340 bytes of the saved variables no code reads,
   saved and loaded with them; not written while an event is replayed).
   (1.2.0) A fifth, a battle's units, only when a quest has battles of its
   own: the game is handed the quest's units for its battle's number.
   (1.2.1) And the game's progress (the point of the story the world map
   shows: its objective and markers), which a story scene sets at its end
   with its instruction E9: **a side quest never moves the story**. While
   one of the quests' events plays, the progress isn't set to what a
   quest's script sets it to, and a variable command on variable 110 (the
   story's progress) isn't done, each said once in the log ("Story Kept
   Scene's visit would set the game's progress 0 to 80: left as it was, as
   a side quest never moves the story."). A story scene copied into a quest
   keeps those instructions: Zodi's tests 14 and 15 showed the world map's
   objective going back after them, with 1.2.0. The game's own events, the
   world map and every other variable stay the game's. A progress flag
   (instruction EA) isn't kept here: Mod Studio refuses a quest whose
   script sets one (`side_quests.story_problem`). (1.2.2) And the world
   map's travel check (found apart: without it the quests play): where an
   event waits, the game lets you go back only the way you came ("You
   cannot travel to the selected location at this time..."); **a side
   quest never blocks the way**, so a travel it would stop for one of the
   quests' events goes on, said once ("A Side Journey's reward (its
   opening) waits here: travel on isn't stopped for it, as a side quest
   never blocks the way."), and the event plays when you come back.
   (1.2.3) The travel check is hooked to native code (`Thunks.cs`) that
   keeps every register the convention lets a function change, and asks
   the C# only when the game would stop a travel: the game's travel step
   keeps the route it takes next in a register across the call, and
   1.2.2's C# hook, once .NET had compiled it again, changed it (his test
   17: the game stopped as a travel went through a town). (1.2.4) A start
   that waits until its place is chosen tests the framework's variable
   4095 last, which the world map's variable function hook answers from
   the travel's state (1 while a travel passes through the place), said
   once when it keeps an event from loading ("a side quest's event here
   waits until its place is chosen: a travel passing through goes
   on."). (1.2.5) And, only when a quest has a Marker, the world map
   screen's showing of a place (`Marker.cs`): where the game shows the
   place and no marker of its own, and a start of a quest with a Marker
   holds there (its conditions run as the world map runs them, but for
   passing through; the first quest loaded wins a place), the game is
   handed a copy of the place's state with its quest marker on (and its
   Loop), and the state the screen keeps is set back to the game's; the
   marker's pin is given the helper's picture (a
   light grey pin, `marker/`, shipped at the game's paths under `FFTIVC/`,
   which the mod loader serves) as the game changes a picture, and it and
   its two glows the quest's color, said once ("Red Trail (Test 20 Quest
   Markers)'s marker shows at place 9."). A place it no longer marks gets
   the game's picture and colors back. The game colors a marker by
   multiplying, so its blue pin could only be darkened.
5. It says each quest's numbers in the log (`Ambush at Gariland (Test 15
   Battle): ambush is event 496 (a battle), ambush opening is event 497,
   ambush won is event 498, ambushers is battle 4096, beaten is flag
   4098.`), each table's rows added, and, as the game runs, each quest
   event as it begins, each flag as it changes, each quest battle as it is
   fought.

A game update that changes one of the places it hooks makes it add no
quest and say which place wasn't found (only quests with battles of their
own need the battles' units; every quest needs the game's progress, since
1.2.1; without the travel check, since 1.2.2, the quests play and a
quest's event waiting where you stand stops travel on, as the game's own
do; without the travel's state, since 1.2.4, a start that waits stops a
travel passing through, as the game's own do; without what the markers
need, since 1.2.5, the quests play without markers, and without the
marker's picture made ready, a marker shows the game's pin in its color;
without what the event tables' room needs, since 1.9.0, the quests' events
stay under 887);
a table laid out otherwise
gets nothing, said. What was measured for
all of it is in Mod Studio's notes (`claude/event-script-research.md`,
"The side quests' framework, as built") and `dev/research/sidequests/`.

### A mod's own places (1.3.0, 1.3.1)

Zodi, 26 October: "real new places, built in steps". The first step: a
mod's places shown on the world map, pictures only. A place is a folder of
its own in a mod, `ModStudioPlaces/<place>/`, holding `place.json`
(`PlaceFile.cs`; Mod Studio's `mod_studio/map_places.py` reads and writes
the same file and says the same problems):

```json
{
  "Format": "Mod Studio place",
  "Version": 1,
  "Name": "Hidden Grove",
  "Kind": "Town",
  "At": [1630, 720],
  "Picture": "msq_modstudio_test22_places_1_hidden_grove_uitx"
}
```

- `Kind`: `Town` (the map's Base piece, a town's picture) or `Battle` (its
  Point piece, the game's brown point).
- `At`: where its middle is on the world map's picture (`ui_wm_map_uitx`,
  3840 x 2288; Gariland's middle is at 1030, 1106, Dorter's at 1592, 1147).
- A town's picture: its own (`Picture`: its files' name, small letters,
  digits and `_`; its texture and part list in the mod at the game's paths,
  `FFTIVC/data/enhanced/ui/ffto/worldmap/texture/<Picture>.tex` and
  `.../textureparts/<Picture>.utexpt`, its part 1 the picture, 172 x 172 as
  the game's are, which the mod loader serves), or one of the game's town
  pictures (`Icon`: 01, 03, 05, 07, 10, 11, 14_34, 15, 17, 19, 20, 22, 23,
  24, 26, 28, 30, 32, 35, 38, 40, 41 or 42); a battle ground has neither.
- (1.16.0) `Description`, if it has one: what the world map's location
  info shows under its name (below, A place's description).
- (1.17.0) A battle ground's `RandomBattles`, if it has them: random
  battles of its own (below, A battle on a mod's battle ground).
- (1.18.0) A town's `Menu`, if it has one: a menu of its own for Enter
  Settlement (below, A town's menu at a mod's town); (1.19.0) its art a
  game town's or its own (below, A town's own art in its menu).
- (1.20.0) A town's `Darkened`, if it has one: darkened on the world map
  once one of its mod's quests' flags is set (below, A place darkened once
  its event is done).

Only when some mod gives a place, the world map screen's setup of its
places' pieces is hooked (`PlaceHooks.cs`, apart from the side quests'
hooks): the game's setup runs whole, then for each mod's place (in
Reloaded-II's order) the helper (`MapPieces.cs`) copies a town's or a
battle ground's piece of the game's (the layouts' copy of a box, as the
game's own code copies boxes it shows more than once: the piece it places
copied with it under a name of its own), names the copy `MsqPlace` and its
number, moves it so its middle is the place's, puts it in the layer after
the piece copied, stops its animations and plays `Show` (and a town's
`Color_Default`) to their last frame as the screen shows a place, hides its
markers, and gives it its picture (the mod's, made ready as the quests'
marker's is, part 1) or the game's (its `TexChange`). Each is said once
(`Hidden Grove (Test 22 New Places) is on the world map at 1630, 720.`), or
why not. The copy is the screen's like its own pieces: it goes with the
screen, and a screen set up again gets it again; the game's own code never
looks at it (the screen's pieces are its 48). Pictures only: no road leads
there, the cursor doesn't stop there, no quest starts there yet. Without
what it needs found, the places aren't shown, said.

**1.3.1, a picture only.** His test 22 drew the places where asked and kept
them through towns, menus and battles, but the mouse took each for the
place its piece was copied from: Royal City of Lesalia for the towns (the
first town the screen keeps is Lesalia's `Base24`, place 0) and Mandalia
Plain for the battle ground (`Point02`, place 24), Travel Here and all. The
screen tags each of its places' pieces as it sets them up (0x1F at
+ 0x220, the place at + 0x224) and knows the place under the mouse by that
tag; the mouse finds a piece by its collision boxes (the layout's
`Collision` boxes, kind 13 in memory, only while seen and shown); the copy
of a piece copies both. So once a copy's piece is found, its tag is
cleared (0, as untagged pieces have it) and its own collision boxes,
through its layers, are switched off (seen and shown 0: they are never
drawn, so nothing on the screen changes). The mouse never finds a mod's
place, and the screen never takes it for one of its own. Its own name, the
cursor's stop and travel there come with the next steps.

### A mod's own roads (1.4.0)

Zodi, after test 23: "Roads to new places", step 2. Its first part: a mod's
roads drawn on the world map, pictures only. A road is a folder of its own
in a mod, `ModStudioRoads/<road>/`, holding `road.json` (`RoadFile.cs`;
Mod Studio's `mod_studio/map_roads.py` reads and writes the same file,
says the same problems and draws the picture):

```json
{
  "Format": "Mod Studio road",
  "Version": 1,
  "Name": "Grove Path",
  "From": 28,
  "To": "Hidden Grove",
  "Via": [[1668, 925], [1662, 860], [1645, 795]],
  "Picture": "msq_modstudio_test24_roads_road_1_grove_path_uitx",
  "PictureAt": [1620, 757]
}
```

- `From` and `To`: the places it joins, each one of the world map's places
  by its number (0 to 46, as a quest's start names one; not 20 or 43, which
  have none: 28 is Zeklaus Desert) or one of the mod's own places by its
  name (as its `place.json` names it).
- `Via`: the turns it takes between them, on the map's picture (at most
  62; none for a straight road). Mod Studio draws the picture along them;
  the helper draws the picture as it is.
- `Picture`: its trail texture's files' name (its texture and part list in
  the mod at the game's paths, as a town's own texture's; its part 1 the
  texture, up to 4096 pixels each way, drawn at its own size), and
  `PictureAt`: where the texture's top left corner is on the world map.
  Mod Studio draws it in the look of the game's 51 trails (11 pixels wide,
  205 of 255 opaque, soft edges and round ends, a faint shadow, painted in
  the trails' sand colors), along a smooth curve through the road's places
  and turns, stopping 60 pixels short of a town's middle and 13 of a battle
  ground's, as the game's do.

In the same hook as the places (only when some mod gives a place or a
road), after the game's setup and the mods' places: the helper
(`MapRoads.cs`) finds the screen's Route piece (kept at + 0x200 as the
screen sets itself up) and the first road picture in its layers, and for
each mod's road (in Reloaded-II's order) makes its picture ready, copies
that picture box (the layouts' copy, as for a place), names the copy
`MsqRoad` and its number, gives it the mod's texture (part 1), its color
white, its opacity 1 and seen (the game shows and hides its own roads by
their opacity, and grays them by their color, each by its name: never
this one's), moves it to `PictureAt`, sizes it to its picture (the layouts'
sizing of a box) and puts it after the picture copied, under every place
as the game's roads are. Each is said once (`Grove Path (Test 24 New Roads)
is on the world map, its texture at 1620, 757.`; until 1.22.0, "its
picture at"), or why not. A picture box
has no collision box and no tag, so the mouse leaves it alone. The game
doesn't travel it yet: that takes its place becoming somewhere the game
travels to (the next step). Without what it needs found, the roads aren't
drawn, said apart from the places.

(1.4.1) His test 24 drew the three roads as described ("Test 24 was a
success and looks as you described. It is great"), but its log said first
"the world map has no Route where its roads are": the screen's setup runs
once before its layout is read, and keeps nothing then (without its
layouts' root it returns before keeping MapAll or Route). The places
already waited for MapAll; the roads now wait for it too, and once the
screen keeps MapAll its setup keeps its Route right after, so a Route
missing then is said.

### Travel along a mod's road (1.5.0)

A road between two of the world map's own places (`From` and `To` both
numbers) is travelled as the game's own when its file has a `Walk`: the
points Ramza's marker walks along it, From to To, on the map's picture (2
to 64 of them). Mod Studio writes it with every road it draws: where his
marker stands at its From (the game's `Town` table's middle), the drawn
trail every 60 pixels or so with his feet on it (3 pixels right of and 19
below the trail's middle), where he stands at its To.

```json
  "Walk": [[1910, 1470], [1840, 1474], [1782, 1494], [1731, 1529], [1692, 1577], [1668, 1643]]
```

The game keeps every road twice: in its program (the PlayStation's: a
table of 51 records, which its route-finding, its walk's setup of a road
and its read of the last road when a travel stops short read by the road's
number) and in two tables (`Route`: a road's name and its places, where the
world map screen walks Ramza to; `MapRouteTable`: the points it walks him
along). Before the game runs, the helper (`Travel.cs`) numbers the roads
past the game's 51 in Reloaded-II's order (51, 52, ...; 204 at most, a
road's number being a byte of the travel's way), gives each a record as the
remaster's own three roads have theirs (two points at 0, 0; its cost its
walk's length), copies the program's table with them after the game's into
memory of its own within 2 GB of the program and has the three readers use
the copy, and the route-finding look at them too. As the game loads `Route`
and `MapRouteTable`, it adds each road's row (`MsqRoad` and its number, its
places) and its walk's points (`TravelTables`), as the side quests' rows
are added. Only once both tables have them does the route-finding see the
mods' roads (a road without its points would never be walked to its end),
and only while both its places are shown. Each road is said with its number
(`Fenland Path (Test 26 Roads Travelled) is road 51 of the world map,
between its places 10 and 30.`), then the tables' rows (`Route: the mods'
2 roads added.`, `MapRouteTable: the mods' roads' 11 points added.`, `the
mods' roads between the game's places are travelled from now.`), or why
not: then they are drawn only. A game that isn't laid out as this was made
for gets no changes at all (each is checked against the bytes it replaces).

The game's route-finding (its path search) tries every road from where it
stands, then every road from there, 16 deep, and keeps the route of the
fewest roads, then the shortest: every road between its places a mod adds
makes it slower (over every route between the world map's places: with 5
more roads 3 times as many tries, with 10 more 7 times, with 20 more 37
times on average, 32 million tries on the worst route). So the helper
answers its question whether a road is shown (`Ways`): as the game would,
and, from where the search stands, only for roads onto a route of the
fewest roads and the least cost, counted as each search begins. The
search still tries every such route in its own order, so it ends with the
same route as without the helper; it only stops trying the others: a few
hundred tries a route, with hundreds of roads too.

Not yet: a road's picture hidden while its places aren't shown. (1.6.0
has random battles on arriving by a mod's road, and 1.7.0 travels a road
to a mod's own place, below.)

### Random battles on a mod's road (1.6.0)

A mod's road arriving at one of the world map's battle grounds (24 to 42)
starts the game's random battles there, as the game's own roads do. The
game picks a random battle by the road Ramza arrived along: each battle
ground has three entrances in a table of its program, each belonging to
one road (where the party deploys, eight enemy formations, and how often
a battle starts as the story goes on), and a road that is none of them
starts none. So the helper gives each mod's road arriving at a battle
ground the entrance of the game's road arriving there from the most
similar direction (its heading over the last 100 pixels of the road,
against each of the game's roads' there), and says so:
`Fenland Path (Test 26 Roads Travelled) arriving at place 30 starts the
random battles of the game's road 43 there, from place 3.` Both of the
game's calls of its roll, as Ramza arrives and as the battle ground he
stands on is chosen (a battle forced), go first through a few bytes of
native code that turn a mod's road into that road; the game's own roads
pass as they are. There is nothing for the modder to set. A game that
isn't laid out as this was made for keeps the roads travelled, without
random battles, said.

### A mod's own place as a destination (1.7.0)

A mod's own place is now one of the world map's places: Ramza walks to it
along a road to it (a road whose `To` or `From` names the place), stands on
it, sees its name, and walks away again; a save made there keeps him there.
Nothing happens at it yet: no menu, no battle, no event.

The game keeps a place by its number (0 to 47) in many places: in its
program (the PlayStation's records of each place's picture and menu, and
the world map's dots, each place's position on its map) and in the world
map screen (a row of 24 bytes for each of its 48 places: its piece, its
box, its kind, a town's byte). Before the game runs, the helper
(`Destinations.cs`) numbers each mod's place past the game's (48 on, in
Reloaded-II's order, kept in `Numbers.json` under `Places` by the mod and
the place's name, so a save standing on one finds it again; 207 at most),
and gives the program what it keeps for a place by its number: the places'
records copied into memory of its own with room for 256 (the mods' none:
no menu), the world map's dots moved there with room for 256 (a mod's
place's made from where Ramza stands at it), the program's 22 instructions
reaching them changed to reach them there; the screen made bigger by a row
for each mod's place past its end, and each of the screen's 16 reads of a
place's row that a mod's place reaches sent through a few bytes of native
code that read the mod's row for a mod's place and as before for anything
else (each changing only what the instructions it stands for change). As
the game loads `Town` and `PlaceName`, each place gets its row (where
Ramza's marker stands at it, its name's number, its kind; its name), as the
roads' rows are added. The copy of the place's piece on the world map keeps
the tag the screen gives its own places, with the place's number, and its
collision boxes, so the mouse finds it, and its label shows its name.

Each place is said with its number (`Hidden Grove (Test 28 New Places
Travelled) is place 48 of the world map.`), then its road's as before (`...
is road 51 of the world map, between its places 28 and 48.`), the tables'
rows (`Town: the mods' 3 places added.`, `PlaceName: the mods' 3 places'
names added.`), and `the mods' roads are travelled from now.` A game that
isn't laid out as this was made for gets no changes at all (each is checked
against the bytes it replaces, and all are made or none): the places are
then pictures only and their roads drawn only, said.

Not yet: a menu or a battle ground at a mod's place. (1.7.1 stops the
cursor moved by the keys or the gamepad on it, and moves a save standing
on one whose mod is gone; 1.8.0 starts a side quest there; both below.)

### The cursor's stop and a save without its mod (1.7.1)

The cursor moved by the keys (W, A, S, D) or the gamepad's stick stops on
a place as it comes near: the game asks which of its 48 places is nearest
the cursor (a place whose piece is there and is shown, within its reach,
the least distance away) and puts the cursor on it. The helper's native
code goes on asking over the mods' places by the same rule as the game's
loop ends, and the three reads of the place's row that follow read a mod's
place's own; so the cursor stops on a mod's place, its name shows, and
Travel Here takes Ramza there, as with the mouse.

A save keeps the place Ramza stands on (the game's variable 49). Loaded
once no mod gives that place (its mod taken away), the game would set the
world map up at a place it has nothing for. So each mod's place keeps a
home with its number in `Numbers.json` (`Homes`: the first of the game's
places its roads reach, through other mods' places if need be), and as
the game loads a save (its load hooked through Reloaded-II's shared hooks,
after the game's own), a place no mod gives now becomes its home, or
Gariland if it has none, said: `the save stood on Hidden Grove (place 48
of modstudio.test28.destinations), which no mod gives now: Ramza goes on
from place 28.` With the mod enabled again, the place is given again and
such a save loads on it. The load list shows no place name for a save
standing on a place no mod gives.

A game that isn't laid out as this was made for: without the nearest
place's code as it was found, the places get no changes at all (as
1.7.0's, said); without the load's, saves load as before, and a save
standing on a place no mod gives can't be moved off it, said.

### Side quests at a mod's own place (1.8.0)

A quest's start may name one of its mod's own places by its name, as a
road's `From` and `To` may:

    "Starts": [{"Place": "Hidden Grove", "When": [...], "Event": "secret"}]

The helper plans the mods' places first (numbering them as before), then
the quests: a start naming a place is given that place's number, and its
chain added there in the world map's table as a start's at one of the
game's places is. The world map runs a place's chains by its number
whatever it is: as Ramza arrives at a place, chooses the place he stands
on, or comes back to the world map, the game asks the chains of where he
stands, so the quest's event plays at the mod's place as at the game's
(its scene's opening, or its battle). A start naming a place its mod
doesn't have is refused by both readers (`a start's place names no place
of the mod's (Hidden Grove)`); one whose place isn't given to the game this
time (the places pictures only, or no room left) is left out, said with
the quest's numbers (`its start at Hidden Grove is left out (Hidden Grove
isn't somewhere to go)`).

A quest's Marker shows over a mod's place too. The screen's own showing of
a place stops at its 48 and keeps a state for each, so the helper shows the
marker on the place's piece itself, as the screen shows one (the Quest
marker's Show and Loop played, our pin in the quest's color; Hide played
once nothing waits there), whenever the screen shows any place and as the
places' pieces are added.

His test 30 (test 28's places and roads in a mod of their own, three
quests starting at them) played as described: the places numbered past
test 28's kept ones (51 to 53), a teal marker over Hidden Grove and an
orange one over Ambush Ridge, each quest's scene or battle as Ramza
arrived, once, its marker gone after it; a save made on Hidden Grove
shows its name in the load list while its mod is enabled.

Not yet: a menu or a random battle at a mod's place.

### Room for hundreds of quests (1.9.0, 1.9.1)

Zodi, 27 October, after test 30: "Room for hundreds of quests". The game's
event numbers stopped at 886: its event setup table has 887 slots (713 of
them the game's records, searched by their events' numbers), and its
finish table (887 words, one an event's by its number: the event after it
and what follows it, written from every setup record as a scenario loads)
has the scenario's flags and condition offsets right after it, so a record
numbered past 886 would write over them. That left 97 numbers under 887
for every mod's quests together, a scene and its opening taking two.

As the game starts, once every mod has loaded and before any quest is
planned, the helper gives both tables, and the battle retry's copy of the
finish table, room for 8,192 events in memory of its own within 2 GB of the
program (`EventRoom.cs`). It copies them there as they are (with WotL
Restoration's changes to the records, made as it loads) and changes 35 of
the program's numbers to reach them: the setup table's four leas and its
three bounds of 887 (8,192 now); the finish table's six leas, its four
reaches by a distance from the program's start and its six writes of
events 400 to 404's own; the retry copy's two leas and two sizes; and, so
a next event may be numbered up to 8,191, the next event's two decodes (13
bits, from 10), what follows' four tests (0x8300, from 0xF300: what
follows is 0x80 to 0x82 times 0x100, so the game's own records read as
before) and (1.9.1) the two masks by which the event chain decides what
follows an event as it ends (0x83 of the word's high byte, from 0xF3, and
0x8300, from 0xF300). Each is a distance or a number of the same size, found by its own
bytes (every instruction reaching a table counted where it reaches, an
immediate after its distance taken into account) and checked against the
bytes it replaces; all are made or none, said: `the game's event setup and
finish tables have room for 8192 events: side quests' events may be
numbered past 886.` A mod that changes the setup records later through the
table's lea (WotL Restoration's pattern) reaches the moved table.

The quests' events are then numbered from what is left under 887 and on
past 886, up to 8,191; their records written after the game's in the moved
table; `EventId` (its rows stop at 886, and the game looks an event's up as
it plays) given a row for each event past 886 before its rows are made as
the game's (`EventId: the side quests' 142 rows past 886 added.`); a flag's
name kept apart from an event's in the log, as either may now be 4096 or
more. A number kept past 886 when the room can't be made moves under 887,
said (`intro moved to event 492, as the game's tables hold events up to
886 this time`). With no quest loaded, the room is made all the same once
some quest's event was ever numbered past 886, since a save made after one
played may remember it as the last event played (`... room for 8192
events: a side quest's event was once numbered past 886, and a save may
have played it.`).

A game update that changes what the room needs: the quests' events stay
under 887, said with what wasn't found. `dev/research/sidequests/
event_room.py` runs his program's own code over the moved tables
(unicorn): the finish table written from every record, each record found,
the next event made current past 1023, what follows, the retry's copies.

His test 31 (27 October, 1.9.0): 97 quests in one mod, 95 of them waiting
for a flag nothing sets, a scene numbered 888 and a scene going straight
into its battle at 1024 and 1025. The room was made, every number as
planned, the scene at 888 played and its flag was set, both markers
showed; but the scene at 1024 went back to the world map instead of into
its battle, again each time Ramza came back. As an event ends, the event
chain (`0x23987C`) decides what follows it from its finish word's high
byte masked by 0xF3, which keeps the bits a next event past 1023 sets: the
scene's kind read as none of the three, the current event was cleared and
the world map came back. 1.9.1 changes those two masks too (35 changes);
`event_room.py` runs the chain whole for every one of the game's events
(each decided as before) and for next events past 1023. His test 32 (1.9.1,
test 31's mod again): "The test was a success and functioned as you described it would" (the scene at 1024
straight into its battle, won; the save made after it loaded with no side
quest ticked, the room made for it).

### A quest's own maps (1.10.0)

Zodi, 27 October, after test 32: "A quest's own maps". A mod's quest map
is a folder of its own, `ModStudioMaps/<map>/`, holding `map.json` and any
files of its own (`mod_studio/quest_maps.py` writes and reads the same
file and says the same problems, word for word):

```json
{
 "Format": "Mod Studio quest map",
 "Version": 1,
 "Base": 22,
 "Title": "Terracotta Gariland",
 "Grid": {"1": "grid.bin"},
 "Rows": {
  "Map": {"DLCFlags": 0, "Comment": null, "Unknown8": 12200, "UnknownC": 0, "Unknown10": 0, "Unknown14": [[2, 5, ...]], "Unknown1C": 1},
  "RefinedBgTexture": [
   {"Key2": 0, "Key3": 0, "DLCFlags": 0, "Comment": null, "Unknown8": ["msq_modstudio_test33_questmaps_gariland_recoloured_gt_0_map022_map_color"], "Unknown10": [1], "Unknown18": [], "Unknown20": []},
   ...
  ],
  ...
 }
}
```

It is made from one of the game's maps, its `Base` (0 to 127); what it
doesn't give is that map's:

- `Rows`: its rows in the six tables the game keys by a map (`Map`,
  `RefinedBgTexture`, `RefinedBgSystemTexture`, `RefinedBgMeshNode`,
  `RefinedBgAnim`, `RefinedBgMeshPolygon`), whole, as Mod Studio's database
  holds a row: its keys after the map's (`Key2`, `Key3`), its list columns
  as lists, never the map's own number (`Key`: the helper's to give). The
  pictures they name are looked for in its Base's folder of pictures
  (`bg/textures/NNN/`): the game's own there, and the mod's own, which take
  names of their own (`msq_<mod>_<map>_<picture>`, with `.tga`, in the
  mod's `FFTIVC/data/enhanced/`), so no two mods' meet.
- `Mesh` and `Anims`: its own enhanced mesh and anims, at paths of the
  mod's own under `bg/meshes/` and `bg/anims/`
  (`msq_<mod>_<map>_mesh.bin`); without them, its Base's.
- `Grid`: its own PlayStation files (its battle grid's), each by its place
  among its Base's numbered files (the place its Base's GNS names a file
  by: the numbered files in number order; the game's lists give some places
  a revised copy, as 022's place 1 its `new_map_new_map022_9.bin`), each a
  file in its folder of 1 to 1,048,576 bytes.
- `Title`: its name where the game shows a map's (the battle's prompt),
  else its Base's (its `Map` row's).

A quest's event names it by its folder's name, `"Setup": {"Map": "Gariland
Recoloured", ...}`; a number there is one of the game's maps, 0 to 127.

As the game starts, after the mods' places and before the quests, the
helper reads every mod's quest maps (what can't be used is left out, said:
`Test 33 Quest Maps's quest map X: its Grid's place 01 isn't 0 to 63; the
quest map is left out.`), gives each a number from 129 to 255 (its
`Numbers.json`'s `Maps`, by the mod and the folder: the same every time,
never given twice; from 1.29.0 numbered afresh as each game starts, the
same while the same maps are enabled, below; 128 is a row of the game's
own `Map` table, nothing but lighting), and makes the game load that number as a map of its own
(`MapRoom.cs`, read from his program as data:
`dev/research/sidequests/README.md`, A quest's own maps):

- **the PlayStation side** (the battle grid and the classic look): the five
  tables of 128 the map loader reads (each pack's GNS file indices and
  lists of each map's numbered files, and the move-find data) moved to
  copies of 256 in memory of the helper's (five `lea`s), the game's 128
  entries copied again each time a map loads (so what the mod loader writes
  there, mods' hidden items, stays the game's); a quest map's entries are
  its Base's GNS, its Base's numbered files with its own in their places
  (handed to the game under file indices from 0x10000 at the PlayStation's
  file reader, `0x2F40C4`, hooked: its bytes, then zeros to the sector, the
  reader's word cleared as the game's own read clears it), and no hidden
  items; the polygon lists' setter (`0x249CB8`) given its Base;
- **the enhanced look**: the five calls that make a map's file names given
  its own mesh and anims (else its Base's), and its Base's number for its
  pictures' folder and the classic look's pictures; the mesh's and anims'
  checks of their own number (byte 8) against the map's taken out, and the
  textures' limit of 127 made -2 (only no map, -1, past it);
- **its rows** in the six tables and its Title in `PlaceName` (key
  950,000 and its number; its `Map` row's name that key, its place and
  part, `UnknownC` and `Unknown10`, none), added as each table loads
  through the tables' setup's hook, in a copy of its file; a row whose keys
  a table has already (another mod's) left out, said.

Fourteen changes to the program, each found by its own bytes and checked
against the bytes it replaces, all made or none, said; then, for each, `the
quest map Gariland Copy (Test 33 Quest Maps) is map 129, made from map
22.`, and as the tables load, `Map: the quest maps' 2 rows added.` and the
rest. A quest map whose Base has no battle grid in the game (120 to 124)
is left out, said; a quest whose map isn't in the game this time is left
out, said (`Recoloured Map (Test 33 Quest Maps) is left out: its quest map
Gariland Recoloured isn't in the game this time.`). A battle on a quest
map gets its Base's deploy prompt at its own map, so the prompt names it
by its Title. `dev/research/sidequests/quest_maps.py` runs his program's
own map loading over what the helper makes (unicorn): the GNS, every
numbered file, a quest map's own grid file handed over, the paths, and the
rows found by the game's own lookups.

Not in this step: a classic look of its own, a scene's change of map to a
quest map (an event's map change takes the map as 16 bits; not yet
followed), deploy areas of its own (its Base's squads serve).

Also in 1.10.0: one mod's file the helper can't read (its quests', places',
roads' or quest maps') is that file's problem only, said, never every
mod's; and a file holding half a surrogate pair alone (a `\u` escape) is
refused before anything in it is read, as Mod Studio refuses it
(`mod_studio/helper_json.py`, which reads every mod's file as the helper
does).

His test 33 (27 October, 1.10.0): two quest maps made from Gariland's map,
one copied whole and one with its ground's texture a single terracotta
color and three squares no unit can enter, and two quests with a battle
on each, at the Zeklaus Desert and Mount Bervenia. It passed ("Test 33
was a complete success and ran as you described it would"): both battles
on their own maps, the copy as Gariland's, the recoloured one terracotta
with its three squares refused, and the same numbers when the game started
again.

### A copied scene's doors (1.11.0)

Zodi, 28 October, test 35, of a copy of the game's scene at the Bunansa
residence (event 160) made on Mod Studio's New Content page: "In the
original scene when the enemies break into the room the door opens. In the
copied scene the door remains closed as they enter." The copy's script was
the game's, its instruction 0x55 starting the door's texture animation
(record 0) as the game's does. But the remaster plays a map's doors, and
some of its other moving parts, by the number of the event playing: the
map's command 0x83 (`0x24F5A0`), which starts a texture animation record,
reads the event playing (variable 0x27, through the variables' read,
`0x2332D8`) and hands it with the record to the enhanced look (`0xC9538`:
light shafts and the like of events 4, 6, 117, 167, 275 and 429;
`0xC729C`: the doors, event 160's for record 0), which does nothing for an
event it doesn't know; a palette animation reads it once more (event 14's
colors), and the animations' step (`0x24FBD8`) as a record ends (events
156, 193, 205 and 290). The copy played as event 1044.

So a quest's event may say the game's event it was copied from (`"From":
160`; the New Content page wrote it for every scene and battle it copied,
and since 4 November, when it copies none, a scene's Doors sets it: the
game's event on the scene's map whose doors it plays),
and while that event plays those four reads give the From: each of their
calls of the variables' read goes to a few bytes of native code in memory
the helper takes within 2 GB of the program, which call the read as the
program did and, when the event playing is a quest's event with a From,
give the From (a table of 8,192 words, one for each event number). Every
other reader of the event playing (the event chain, the finish table, the
helper's own hooks, the program's 27 other calls of the variables' read
for it) still sees the quest's own number. Each read is found by its own bytes, all four
calling one function; the four calls are checked against the bytes they
replace and changed all or none, said: `the side quests' event copied from
the game's plays the map's doors and moving parts as the game's event it
was copied from.` Only when some quest's event has a From.
`dev/research/sidequests/map_animations.py` runs the native code and the
game's own map command 0x83 over his program with unicorn: event 160's door
started for a quest's event copied from it, none for one that isn't.

Not in this step: what the game keys to an event's number elsewhere
(`dev/research/sidequests/event_reads.py`: 31 reads of the event playing,
the four here and 27 in 20 other functions, some compared with events'
numbers such as 300, 388, 396, 404, 429, 465 and 518, not followed yet).

His test 36 (28 October, 1.11.0): the copy of event 160 again, its
thirteen lines numbered in the order the scene shows them. It passed
("Test 36 was a complete success and functioned exactly as you described.
Everything is correct."): the door opened as the men came in, the lines 1
to 13 in order, his log as planned (event 1046, its opening 1047, flag
4217).

### A battle with no scene of its own as it starts (1.11.1)

Zodi, 28 October, test 37, of a quest battle made on Mod Studio's New
Content page with no scene of its own as it starts: "the battle at Gariland
began I selected my units and after was a black screen saying I had won
the battle. I suspect the enemies were not placed giving me the instant
win." It was the first quest battle without one (tests 15, 30, 31 and 35
each had a scene as their battle started). His program runs a story
battle's rules as its formation screen closes (the scenario check,
`0x2387C4`), before the battle has begun (variable 509, the battle not
started, still 1) and before its enemies are on the field; every one of
the game's 72 battles has a first rule that plays its start event then
(509 is 1, play the event), and the game's random battles, which have no
rules, play the game's battle start (event 401) there. The quest battle's
only rule, its won scene once every enemy is beaten, ran first.

So a quest battle with no `Start` of its own gets the game's battle start
as its first rule (509 is 1, play event 401: a sweep of the camera over the
field and the objective box, "Defeat all enemies!"), as the game's random
battles start; the event's finish (back to the battle) is the game's own,
which the scenario setup writes for 401 (and 1.9.0 writes into the moved
table). Its line says so: `Bervenia ambush is event 1052 (a battle, starting
with the game's battle start, event 401)`. A battle with its own `Start`
plays it first, as before. `dev/test_side_quests.py` holds a battle's rules
to both (tests 38 and 35).

### How a battle is won and lost, and its objective (1.12.0)

Zodi's choices (28 October, from the list measured on the game's own
battles): a battle won once one unit is beaten, once one unit is worn
down, or once Ramza stands on a tile; a unit it is lost without; and its
objective in the quest's own words. A battle event's `Battle` may give:

```json
{"Units": "ambushers", "Start": "ambush starts", "Won": "ambush won",
 "WonWhen": {"Beaten": 5}, "Protect": 1, "Lost": "ambush lost",
 "Objective": "Defeat the Chemist! Delita must not fall."}
```

- `WonWhen`: one of `{"Beaten": unit}`, `{"WornDown": unit, "Share": 1 to
  99}` (its HP down to that share of its most) or `{"OnTile": [x, y,
  level]}` (level 1 its upper level); none, every enemy beaten, as
  before. A unit is one of its battle's 16 by place (1 to 16), of one of
  the quest's own battles.
- `Protect` (a unit, 1 to 16) and `Lost`, the quest's event that plays
  once that unit is beaten, after which the game starts over.
- `Objective`: 1 to 64 characters on one line. Its start event shows it:
  the event's `ObjectiveInScript` lists where, each the byte after a
  DisplayConditions (0x78) in its script.

**What the game does** (his program, read as data; the game's tables,
1.5.2's database and WotL Restoration's whole copies, read for their
facts; `dev/research/sidequests/battle_rules.py` surveys them). Its
battles' rules test a unit through the rules' checker (`0x239294`): 4 the
unit there, 6 its HP at most a number, 8 its HP in hundredths of its most
(its HP times 100 over its most and 1) at most a number, 24 on a tile (its
x, y and level); a unit missing fails each test. A rule names a unit by a
key of CharaControlId (sheet 0xDA, read as the rules load, `0x2FC042`),
whose row gives the unit ID the game finds the unit by (`0x239144`); keys
1 to 52, 100 to 103 and 128 to 139 are those IDs themselves, and a key the
table hasn't gives no row, which the program reads at address 8. Of the
game's 71 battles with rules, 45 are won once every enemy is beaten (the
sluice at Fort Besselat also by Ramza on a tile), 17 once one unit is
beaten, 8 once one is worn down to a share of its HP, 1 once a unit's HP
is down to a number, and 10 are lost
once a unit is beaten: their lost scenes say a line and end with the game
over's instructions (event 400's), and what follows them is 0x82, the
game starting over. A battle's objective is a row of BattleObjective
(sheet 0x2F, a language's table, 69 rows, keys 0 to 68): its start event's
DisplayConditions shows the display less 8 (`0x2CA3AC` keeps it at
`0xD3AD54` and finds the words at the Name's own place plus the number it
holds, `0x0FB5B0`: from the Name, not from the row's start as ScionFiles'
path); IsProtectionMission (+ 0xC, read at `0x1EB5D0`) marks a battle
whose guests are units to protect. The game's 80 objective boxes show
keys 0 to 34, each a row with words.

**What this helper does.** Each battle's rules after its start (1.11.1):
with a unit protected, the victory guard (128) 0, that unit there and its
HP at most 0, its lost event (laid out row for row as the game's own
"Protect Ovelia!" and "Protect Agrias!" lost chains, rules 41's chain 4
and 57's chain 2); then won as its `WonWhen` says: the guard 0, the unit
there and its HP at most 0 (Beaten) or its share at most the `Share`
(WornDown), its won event; or, for `OnTile`, one chain for each Ramza the
rules name (1, 2 and 3, by the story's chapter), the guard 0 and Ramza on
the tile, its won event, then the guard 0 and every enemy beaten, as the
sluice; with no `WonWhen`, every enemy beaten, as before. The lost event's
record has the battle's setup and 0x82 after it, and EventId the battle's
first scene, as its other scenes. Each objective is given a key past the
game's (69 on, up to 247: one byte holds the display, the key and 8; kept
in `Numbers.json` as `Objectives`), written into its start event's script
where `ObjectiveInScript` says, and added to BattleObjective as the game
loads it, in whatever language: 16 bytes as the game's rows (its Name
pointing at the words after them, IsProtectionMission 1 for a battle that
protects a unit), the words after. A key another mod's row has already is
left alone, said. The log's line says how each battle is won and lost and
its objective's number: `Chemist hunt is won once its unit 5 is beaten,
Chemist hunt is lost once its unit 1 is beaten, Chemist hunt's objective
is objective 69`.

Mod Studio's New Content page gives a battle's start scene for an
objective (a copy of the game's battle start, event 401, which a battle
without one played) and the box of the game's openings to a start scene
that shows none, and makes a lost scene from the game's game over (event
400) with a line first. Also in 1.12.0: a table given one row says "1
row" (Zodi's list, his tenth).

### The numbers kept three times, and each save's mark (1.13.0)

Zodi's list, his first (28 October): "a second copy of the helper's
numbers file, so a lost file never renumbers anyone's quests or reads a
save's flags as another quest's". His choices: the numbers kept beside the
game's saves, in Reloaded-II's settings folder and in the helper's own
folder; and a mark in each save.

**What was measured.** The game keeps every save slot in one file,
`fftsave.bin` (2,008,200 bytes), in the player's Documents: `My Games`,
`FINAL FANTASY TACTICS - The Ivalice Chronicles`, `Steam`, the Steam ID
(his program: the Documents from `SHGetSpecialFolderLocation`'s 5 at
`0x6DE34`, "/My Games/" and the game's title at `0x6E5DC`, "Steam/%llu/"
at `0x6B144`); it deletes only files it names (each by its name, through
`0x27EA0` and `0x51CF8`). A Reloaded-II update (Sewer56.Update, as
Reloaded-II applies it with `CleanupAfterUpdate`) removes the files of the
helper's folder its new release hasn't, but those its `IgnoreRegexes`
match (`.*\.json`, but its `ModConfig.json` and the build's `.json`
files): a release made with Reloaded-II's Publish keeps them, one made
from a plain zip doesn't. Reloaded-II's settings folder for the helper is
never touched. The bank's last 340 bytes, which no code of the game's
reads, are saved and loaded whole with the rest.

**What this helper does.** Its numbers are kept in three places, read
together as the game starts, the most trusted first: beside the game's
saves (`fftivc.utility.modstudio.eventsetup.Numbers.json` in each Steam
ID's folder of them: a backup or a move of the saves takes it along; the
saves were made with it), Reloaded-II's settings folder (`Numbers.json`,
as before), and its own folder (`Numbers.json`). The first copy found
gives the numbers; every name another copy has that it hasn't is taken in
at its number, where no name of the first has it; a name two copies number
apart keeps the first's, said, its other number never given again. A copy
missing is written again from the first, said ("its numbers' copy in
Reloaded-II's settings folder was missing, so it is written from the one
beside the game's saves."); every copy is written whenever the numbers
change. The numbers have an ID of their own (`"Id"`, made once). Each save
carries it in the bank's last 4 bytes (`Framework.MarkAt`, 1020 to 1023;
the quests' flags 4096 to 6783 before them, far past any his numbers
ever gave), written as a quest flag is set when the save has no mark.
As a save loads (the hook of 1.7.1's fallback, `0x21B0E8`), one with quest
flags and no mark (made before 1.13.0) is marked with these numbers; one
marked with other numbers is said: "the save loaded was made with other
side quest numbers (its mark ..., these numbers' ...): its quests' flags
may be read as other quests'. The numbers it was made with aren't the
ones kept here: lost from every place they were kept, or another
computer's."

### A unit taken from the player's own units (1.12.1)

His test 39 (28 October): "I instantly lost and it said Delita fell. I
believe this is because Delita is not on the map, instead of where he
should be I see a Squire." Gariland's battle marks Delita Load Formation
and Save Formation (a unit's byte 1, 0x08 and 0x01, FFTPatcher's names):
his program builds each of a battle's units from its fields (`0x275CA4`,
for each of the 16, from `0x27128C`) unless it has Load Formation, which
leaves it to the player's own units. A side quest's battle has no Delita
among them, so his place was an empty unit at 0 HP, and the rule "lost
once Delita is beaten" passed at once. 31 units of the game's battles
have Load Formation, all story characters; the same characters are built
from their own fields in many other battles and scenes (Delita 21 times:
`dev/research/sidequests/formation_units.py`). So a unit a battle's rules
name (`WonWhen`'s or `Protect`'s) can't have Load Formation: the quest is
left out, said ("the battle Chemist hunt's unit 1 is taken from the
player's own units as the battle starts (Load Formation), which leaves an
empty place at 0 HP when they haven't that unit: build it from its own
fields (Load Formation off)"). Mod Studio's copy of one of the game's
battles has both flags off for every unit.

### A battle's own deploy areas (1.14.0)

Zodi's list, his second (28 October): "custom deploy areas", a quest
battle's own squares where the player's units start. A battle's `Deploy`
gives one or two areas, each its `Squares` (1 to 25 tiles, each its x and
y, within 5 by 5 squares, none twice), its `Units` (how many of the
player's units start there: 1 to 5, no more than its squares), its
`Facing` (`South`, `West`, `North` or `East`, as a unit's facing in the
game's battle files) and, on the squares' upper level, `Upper`:

```json
"Battle": {"Units": "Flank attack", "Won": "Flank attack won",
           "Deploy": [{"Squares": [[8, 13], [9, 13], [8, 14]], "Units": 3, "Facing": "South"},
                      {"Squares": [[0, 5], [0, 6]], "Units": 2, "Facing": "East", "Upper": true}]}
```

**What was measured** (`dev/research/sidequests/deploy_squads.py`, his
program read as data). A setup record names its deploy areas by two
numbers (DeployArea1 and DeployArea2, kept in the battle's variables 0x35
and 0x36, how many in 0x34) of the program's 768 squads of 12 bytes at
`0x7AE2D0` (`deploy_squad_t`: a 5 by 5 grid of tiles as 25 bits, the
middle tile's x and y, its level, the grid's orientation, how many units,
the map, its own number). No instruction names the squads or any byte of
them: they are read only through two pointers in the program's data,
`0x8ECA58` (the squads) and `0x8ECA60` (the squad in use, set from the
first as a squad is taken), each reader multiplying a squad's number by 12
and adding it, with no bound. Only the debug battles' search for a map's
squads stops at 768 (`0x2FB4F8`, variable 0x1FE set: fft_decomp names it
the world's debug battle style; corrected 2 November, once called the
random battles'); any other battle's squad, the game's random battles'
too, is taken as variable 0x35 gives it, and its units' most read from it. The formation screen
lays a squad's tiles about its middle tile, turned as its orientation says
(`0x303408`: the turn is the orientation's low half less 1 plus its high
half, the units facing south, east, north or west by turn). EntryArea
(sheet 0xF4, keyed by squad and tile) gives every tile of every squad 0,
as a squad without rows has.

**What this helper does.** Each of a quest battle's own areas is given a
squad numbered past the game's (768 up to 4,095; kept with the rest as
`Squads`, by mod, quest, battle and area), made as the formation screen
will lay it: its middle tile the middle of its squares' box, its grid the
game's turned for its facing, each square's bit at its place, its level,
its units, the battle's map (a quest map's own number) and its number.
Once every quest is planned, the program's squads are copied into memory
of the helper's with room up to the highest number given, the game's 768
as they are and each quest's at its number, and both pointers are given
the copy; the battle's setup record names its squads (its first area
DeployArea1, its second DeployArea2, else 0) in place of its setup's. Its
line says them ("Flank attack's deploy areas are squads 768 and 769").
Where the squads or their two pointers aren't found as measured (a game
update may move them), each battle starts where its setup says, said:
"the side quests' own deploy areas aren't used, each battle starting where
its setup says: the deploy squads weren't found in FFT_enhanced.exe of ...
bytes. A game update may have changed them: look for a newer Mod Studio
Event Setup." Mod Studio's New Content page makes them: a battle's card,
"Where your units start", on the game's deploy areas or on deploy areas of
its own, their squares clicked on the battle's map; its setup's are then
where it starts without this helper.

### Tavern rumors (1.15.0)

Zodi's list, his third (28 October): "Feature where you read a tavern
rumor and the side quest can now start (the tavern rumor only appears
after certain story conditions) similar how Nelveska Temple works in
game". A quest's `Rumors` gives each rumor its `Name`, its `Title` (1 to
64 characters on one line, as the tavern's list shows it), its `Text` (1
to 3,000 characters, line breaks its only control characters: the game's
own leave an empty line between paragraphs), its `Towns` (1 to 15 of the
game's towns, by their places 0 to 14, each once; without it, every
tavern), its `When` (conditions as a start's, the story's progress or a
flag of the quest among them) and its `Read` (one of the quest's flags,
set once the rumor is read). A start waiting for that flag (`{"Flag":
"Ghost rumor read", "Is": 1}`) plays only after the rumor is read:

```json
"Rumors": [
  {"Name": "Ghost rumor", "Title": "A Ghost at Dugeura Pass",
   "Text": "Travelers coming in from the west swear a ghost walks the road through Dugeura Pass at dusk.",
   "Towns": [13], "When": [{"Variable": 110, "AtLeast": 3}], "Read": "Ghost rumor read"}
]
```

**What was measured** (`dev/research/sidequests/tavern_rumors.py`, his
program read as data, WotL Restoration's tables as the game loads them).
The taverns' rumors are the table Gossip (sheet 0xB5, one file a
language): a row of 48 bytes, its title's and words' places at + 0xC and
+ 0x10 (each counted from + 0xC), two lists the game does as the rumor is
read (+ 0x14, + 0x1C), a situation (+ 0x24), a picture (+ 0x28) and a
byte for every tavern (+ 0x2C); the game's first twenty have none of
those. The taverns' list (`0x36EE50`) lists keys 0 to 63, each as the
taverns' test of a rumor told says (`0x36F53C`, a key and a place): its
situation if it has one, its every tavern byte, else the place's bit in
the program's 64 masks (`0x7BE620`: 0x4000 shifted right by the place,
the towns being places 0 to 14) and world variable 0x2D1 plus the key not
0, which the game's scenes set and clear as the story goes. The test has
three other callers: the news of new rumors and, twice, the world map's
towns. The save keeps two bytes a rumor (64 of them, from `0x11A7299`),
both 1 on a new game: the tavern sets the first to 0 as a rumor is read
(the list shows a rumor whose first is 1 as new), the news the second. The
game's rumors are keys 0 to 22 and WotL Restoration's 23 to 26 (its own
strings: "Rumor town masks", "town mask was already"). The variables past
key 28 are the game's own bits for other things: its world map tests 0x2EE
to 0x2FD at its towns and its battle rules 0x2EE to 0x310.

**What this helper does.** Each of a quest's rumors is given a key past
the game's and WotL Restoration's (27 to 63; kept with the rest as
`Rumors`, by mod, quest and rumor; from 1.29.0 numbered afresh as each
game starts, below), and Gossip, in the language the game
loads, a row at that key as the game's plain rumors are (its title and
words after its 48 bytes, none of the rest). It hooks the taverns' test of
a rumor told: for a quest's rumor, told where its towns say while its
`When` holds (the world map's own tests, as a start's conditions are
run); for every other key, the game's own test. It never touches a
variable for it. Once the taverns have shown a quest's rumor (the save's
first byte for it 0), its flag is set before any quest flag is read (from
1.29.0 as the tavern marks it read, below), said
("Ghost Pass's Ghost rumor read is 1 (flag 4224): its rumor Ghost rumor
was read."), and the save marked as for any flag. Its line says each
rumor's key ("Ghost rumor is rumor 27"). A Gossip row at its key that
another mod gave first keeps that mod's, said ("Ghost Pass (Test 43
Tavern Rumors)'s rumor Ghost rumor isn't told: Gossip 27 is another mod's
already."), and the taverns tell it as the game's test says. Where the
taverns' test or their list isn't found as measured (a game update may
change them), the quests play and their rumors aren't told, said: "the
taverns' test of a rumor told (0 places like it, not 1) wasn't found in
FFT_enhanced.exe of ... bytes: the side quests' rumors aren't told in the
taverns. A game update may have changed it: look for a newer Mod Studio
Event Setup." Mod Studio's New Content page makes them: Add a rumor, its
card (its title and words, its towns ticked or clicked on the world map,
when it is told, and the steps waiting until it is read).

### A place's description (1.16.0)

Zodi's list, his fourth (28 October): "We can add the world map place name
but we can not yet add its description." A place's `Description` gives it:
1 to 200 characters, a line break the only control character among them
and once at the most, no space at either end (`"Description": "A quiet
grove beyond the desert's edge.\nNobody lives here now."`).

**What was measured** (his program read as data; `dev/research/
sidequests/destinations.py`). When the cursor rests on a place, the world
map's location info (`0x158CB0`) takes the place's Town row (sheet 0x34)
and sets its title box to the place's name (PlaceName, by the row's
PlaceNameId) and its detail box to the row's Description, read from + 4
(`0x158D67`: `lea rax, [rsi + 4]`, the distance there added), and its
picture from the row's Unknown1C. The detail box
(`wm_location_info.uib`'s `text_detail`) is 1750 by 106 at 28 points, a
line 44 high: two lines. The game's descriptions are 80 to 160
characters; four of them break their second line themselves.

**What this helper does.** A mod's place's Town row (1.7.0) carries the
place's description after the row's zeros, from + 4 as the location info
reads it; a place without one has an empty description, as before. Mod
Studio's New Content page gives a place's card a Description box. A mod's
place has no picture of its own for the location info yet.

### A battle on a mod's battle ground (1.17.0)

Zodi's list, his fifth, its first part: "A battle on a mod's own battle
ground", his choice "Its own battles". A battle ground's place file may
give random battles of its own, each made as a quest's battle is:

```json
"RandomBattles": {
  "Chance": 30,
  "Battles": [
    {"Name": "Quarry Brigands", "Units": "quarry_brigands.entd", "Map": 76,
     "Deploy": [{"Squares": [[8, 12], [9, 12]], "Units": 2, "Facing": "North"}]},
    {"Name": "Quarry Bones", "Units": 25, "Map": 74, "From": 3,
     "Deploy": [{"Squares": [[3, 4], [4, 4], [3, 5]], "Units": 3, "Facing": "East"}]}
  ]
}
```

- `Chance`: how many of 100 arrivals start one, 0 to 100 (the game's
  own grounds: about 31). Searching for enemies there always starts one.
- `Battles`: 1 to 8, each its `Name` (as a quest's battle's), its `Units`
  (its file in the place's folder, 640 bytes as the game's battles hold
  16 units, or one of the game's battles by its number), its `Map` (one
  of the game's by number, 1 to 127, or one of the mod's quest maps by
  name), its `Deploy` (one deploy area, as a quest battle's: a random
  battle starts the party on one, as the game's own do) and, if it waits
  for the story, `From` (the story's progress it waits for, variable 110,
  as a quest's step waits for it). A town has none.

**What was measured** (his program read as data;
`dev/research/sidequests/ground_battles.py`). The game's roll
(`0x248BE4`) takes its own 19 battle grounds only (the place less 24, up
to 18), so it never rolls a mod's place (48 on). It keeps its choice in
three places: the squad (`0xD49468`), the battle (`0xD494C8`) and the map
(`0xD49464`), and writes nothing else but its random numbers. What
follows reads only those: as Ramza arrives, the world map's deploy prompt
(`0x2477C8`), or with none the battle's setup at once (`0x248254`:
variable 50 the battle, 52 one deploy area, 53 the squad, the next map the
map); as he searches for enemies on the ground he stands on, the prompt
and a sound only. The prompt is the battle's EntryNo row's (its key at
+ 8) in SortieConfirm, shown when its byte at + 0x2C isn't 0: each of the
game's 195 random battles has one; a battle without one starts at once on
arriving, but searching starts none. The 13 entrances the game never
rolls are unfinished (their squads have no squares; in 9, units stand off
the map's ground), so a mod's battle ground has battles of its own.

**What this helper does.** The roll's native code (1.6.0's) sends a place
from 48 to a slot of the helper's, which holds the native code's own "no
battle" until the hooks are made, then the helper's own roll: of the
place's battles those the story has reached, arriving one on `Chance` of
100 arrivals, searching always one, picked evenly; its squad, battle and
map kept where the game's roll keeps its own, so the game goes on as with
its own random battle (the prompt, the formation, the battle). Each battle
is planned with the quests: its own units numbered as a quest's battles'
(4096 on, kept as `Battles`), its deploy area a squad past the game's 768
(kept as `Squads`) and its deploy prompt a copy of the game's first random
battle's on its map (a quest map's, its Base's with the map its own; from
900,000, kept as `Prompts`), named by its EntryNo row; all three kept by
the mod, `place:` and its place's name, and the battle's name. One by the
game's number keeps that battle's own (each of the game's random battles
has a prompt). Said once: `Old Quarry (Test 45 Ground Battles)'s random
battles start on 30 of 100 arrivals: Quarry Brigands is battle 4096 on map
76, its deploy area squad 768, its deploy prompt 900000; ...`, and as one
is picked: `Old Quarry (Test 45 Ground Battles)'s random battle Quarry
Brigands is picked (battle 4096, map 76).` Without what it needs found (the
roll's keeps, its native code, the squads), the battle ground's own
battles aren't fought, said. Mod Studio's New Content page makes them on a
battle ground's card (Add a battle, How often).

### A town's menu at a mod's town (1.18.0)

Zodi's list, his fifth, its second part: "a town's menu at a mod's own
town", his choice "Its own": "An Outfitter selling items picked on the
page, a tavern telling the quests' rumors that name the town (no errands),
the Warriors' Guild, and a Poachers' Den if ticked". A town's place file
may give a menu of its own (Enter Settlement); a town without one has no
settlement to enter, as some of the game's places have none:

```json
"Menu": {"Art": 9, "Shop": [1, 19, 51, 59, 128, 157, 186, 240, 246, 253], "Poachers": true}
```

- `Art`: the game's town (by its place, 0 to 14) whose art its menu and
  its location info show.
- `Shop`: its Outfitter's items, each one of the game's by its number (1
  to 255) and once; none, an Outfitter selling nothing; (1.26.0) after
  them, its mod's own items by their names. Each is sold as
  the game's own shops sell it: once the story reaches its Shop
  Availability (the game's scenes go up to 16, Chapter4_KillZalbag; an item
  past it is never sold).
- `Poachers`: true for a Poachers' Den, open once the story opens the
  game's own.

A quest's rumor may name the mod's own towns with a menu by their names
among its `Towns`, beside the game's by their places (`"Towns": [13,
"Hermit's Rest"]`); none named, every tavern, the mods' towns' too.

**What was measured** (his program read as data;
`dev/research/sidequests/town_menus.py`). Enter Settlement's entries
(`0x3449B0`) are the tavern, the Outfitter and the Warriors' Guild for a
place whose record's fourth byte is 1, and the Poachers' Den once variable
0x90 is set and its Town row's byte at + 0x32 is; the menu's opening
(`0x344B68`) loads the picture set the record's third byte names. The
Outfitter (`0x2C35FC`) takes its town from variable 0x31, the place Ramza
stands on, and its stock (`0x288E54`) lists each item whose bit for that
town is set in the shops' masks (`0x67F890`, the mod loader's
ItemShopsData), from 15 none: a mod's town sells nothing. The game's 96
errands each name one of its 15 towns, so a mod's town's tavern offers
none. The taverns' test of a rumor shifts a town's bit by the place's last
five bits: place 15 no town's.

**What this helper does.** A town with a menu gets a town's record (its
fourth byte 1, its third its art town's picture set) and a Town row with
its art town's picture (+ 0x1C), its town texture's number when it shows
one of the game's (+ 0x2C and + 0x2E) and its Poachers' Den (+ 0x32).
The helper hooks the Outfitter's stock: for a mod's town with a menu, it
gives town 14's bit (Sal Ghidos', the second byte's 2) to the town's items
alone for the call, asks the game's own code for town 14 and gives every
byte back after, so the game lists them as a town's (by tab, by the
story's point, checked against the unit). The taverns' test at a mod's
town tells the quests' rumors naming it and those told in every tavern,
and the game's rumors told in every tavern (asked at place 15). Said once:
`Hermit's Rest (Test 46 Town Menu) has a menu of its own (Enter
Settlement): an Outfitter selling 10 items, a tavern telling 1 side quest
rumor, the Warriors' Guild and a Poachers' Den.` Without the stock found,
its Outfitter sells nothing, said; a rumor naming a town without a menu
isn't told there, said. As the game's own code has it, the menu's mark of
new items on the Outfitter isn't shown at a mod's town (it tests the
place's own bit), and the location info keeps its plain panel (the town
panel's lists take the game's places only). Mod Studio's New Content page
makes it on a town's card (Enter Settlement: its art, its Outfitter's
items added, copied from a town's or none, its Poachers' Den) and names
the mod's towns on a rumor's card.

### A town's own art in its menu (1.19.0)

Zodi's answer for a town's menu's art: "Just like the map place icon the
modder should be able to chose between using their own or a game town's
picked from one of the game's". A town's `Menu` may name its own art's
files in place of a game town:

```json
"Menu": {"Art": "msq_mymod_hermits_rest__art_uitx", "Shop": [1, 240]}
```

- `Art`: its own art's files' name (small letters, digits and `_`, 1 to
  64 of them): its texture and part list in the mod at the game's paths,
  `FFTIVC/data/enhanced/ui/ffto/worldmap/texture/<Art>.tex` and
  `.../textureparts/<Art>.utexpt`, its part 0 the art, 680 x 452 as the
  game's town art is, which the mod loader serves (as a town's own
  `Picture`'s are). Mod Studio names them of the mod and the place.

**What was measured** (his program read as data;
`dev/research/sidequests/town_menus.py`). The menu and the location info
show a town's art as their thumbnail (680 x 452, part 0 of its part list)
from its Town row's + 0x1C: the game's base art's path by that number
(`0xFC1C0`: the Icon table's row 21, `base/textureparts/base_%02d_uitx`,
under `UITextureParts://ui/ffto/icon/`; the game's numbers 1 to 26, a
tavern rumor's picture by its Gossip row), made ready with the screen's
layouts and given its box (`0x158D98`). The menu's town picture
(worldmap_base_menu.uib's IconBase, its Icon 172 x 172) is TexChange of
the Town row's + 0x2C played on its piece (`0x158E30`), which the menu
opener finds on its UI object (from the UI's root: + 0x10, + 0xA0, + 0x48;
its piece at + 0x48, its layouts at + 0x18).

**What this helper does.** A town with its own art gets its Town row's art
numbered 1000 plus its place's number, and its record's third byte 0 (the
opening loads no picture set of the game's); the base art's path is hooked
(found by its first bytes and the Icon table's key 0x15 it asks) and, for
a town's own number, writes `UITextureParts://ui/ffto/worldmap/textureparts/<Art>`,
any other number the game's own. A town with its own texture (`Picture`)
and a menu has no TexChange of the game's (+ 0x2C -1): the menu's town
picture is hooked and, on the menu's own piece, gives its box the town's
own texture's part list (made ready with the menu's layouts, as the game
makes its thumbnail's), part 1, keeping what the box had; before a game
town's TexChange plays there, the box gets back its own. Said with the
menu's line: `...the Warriors' Guild; its art is its own.` Without what it
needs found, its own art and texture aren't shown in the menu, said
(`the mods' towns' own art and textures aren't shown in their menus:
...`); a fault is said once and the game's own code goes on. Mod Studio's
New Content page chooses it on a town's card (Its art: one of the game's
towns' art, or your own, from any image file, fitted into 680 by 452).

### A place darkened once its event is done (1.20.0)

Zodi's list, his sixth: places like Ziekden Fortress, Brigands' Den,
Nelveska Temple, Fort Besselat, Mullonde and Golgollada Gallows, with no
menu, whose texture darkens on the world map once their event is done:
"We should also support this functionality for modders." A town's place
file may give what darkens it:

```json
"Darkened": {"Quest": "The Hermit", "Flag": "Hermit visit done"}
```

- `Quest`: one of its mod's quests, by its folder's name; `Flag`: one of
  that quest's flags (a step's `<event> done`, set once its event has
  played; a rumor's `<rumor> read`; one of its own). Each a name as a
  quest's are. A battle ground has none (only a town's texture darkens).

**What was measured** (his program read as data;
`dev/research/sidequests/darkened_places.py`). As the world map shows one
of its 48 places (`0x15AE14`), a shown place's Town row's + 0x28 (a
situation of the UserSituation table, checks of the story's variables and
flags, `0xFF8A4`) decides its color: Color_Grayout when it holds (the
town's texture drawn at 155 of 255), else Color_Default, the other stopped
first (`0xF638C`). The game's darkened places are the seven above it, each
with its own situation; a mod's place is never shown by it.

**What this helper does.** It plans the town's flag with the side quests
(the flag's number as the quest gives it: `Hermit's Rest (Test 48 Darkened
Place) is darkened once The Hermit's Hermit visit done is set (flag
4228).`; without the quest or the flag added, `isn't darkened`, said) and,
on its copy of the town's piece, stops one color by its name and plays
the other to its last frame as the game does: Color_Grayout once the flag
is set (read where the quests' markers read theirs), Color_Default before.
It does so as the world map is set up and each time the screen shows one
of the game's places (the quests' markers' hook, made for this too); said
once as it first darkens (`... is darkened: The Hermit's Hermit visit done
is 1 (flag 4228).`). Without the screen's showing of a place found, as the
world map is set up only, said. Mod Studio's New Content page picks it on a
town's card (Darkened: Never, or once one of the mod's quests' flags is
set).

### A dungeon like Midlight's Deep (1.21.0)

Zodi's list, his seventh: "the ability to add a place location that
exists as a dungeon similarly how Midlight's Deep functions on the world
map where clicking on it brings up a list of maps in the dungeon and after
selecting one it takes you to a randomly selected battle on that map", his
choices "each floor waiting for a quest flag the modder picks, or showing
from the start if none is picked" and "a few random battles per floor". A
place file of the kind `Dungeon` is drawn as a town is (an `Icon` or a
`Picture`) and has `Floors` in place of a town's menu:

```json
"Kind": "Dungeon",
"Icon": "19",
"Floors": [
  {"Name": "Upper Pit", "Description": "Listed from the start.",
   "Battles": [{"Name": "Pit Goblins", "Units": "pit_goblins.entd", "Map": 76,
                "Deploy": [{"Squares": [[8, 12], [9, 12]], "Units": 2, "Facing": "West"}]}]},
  {"Name": "Lower Pit", "Opens": {"Quest": "The Hermit", "Flag": "Hermit visit done"},
   "Battles": [{"Name": "Deep Goblins", "Units": 25, "Map": 74,
                "Deploy": [{"Squares": [[3, 4], [4, 4]], "Units": 2, "Facing": "East"}]}]}
]
```

- `Floors`: 1 to 10 (the Deep's list holds ten), listed in this order,
  each its `Name` (1 to 24 characters, the list's width, no two alike),
  its `Description` if it has one (the words the list shows for it, as a
  place's description is written, at most 200 characters), `Opens` if it
  waits for a quest flag (one of its own mod's quests and the flag's name,
  as a town's `Darkened`; 1.24.0, or `"FloorBeforeWon"`, below; without
  it, listed from the start) and its
  `Battles`, 1 to 8, each as a battle ground's random battle is (above),
  their names unique in the dungeon. A dungeon has no `Menu`, no
  `RandomBattles` and no `Darkened`.

**What was measured** (his program read as data, the 1.5.2 database;
`dev/research/sidequests/dungeon_places.py`). Choosing a place asks the
program for its entries (`0x3449B0`): a town's menu (the tavern, the
Outfitter, the Warriors' Guild, the Poachers' Den), and at Midlight's Deep
(place 22) its floors opened so far, entries `0xB8ED` on. The menu's
opening tests the Deep twice (`0x345056` its list's block: the count, the
ten floors' cleared bytes, the cursor's floor; `0x345619` its screen, 9, a
town's 3), and the choosing once (`0x3457E8`); a floor chosen sets
variable 92 to it and asks the place's world events (`0x3459C8`), which at
the Deep pick its battle from the battle sets table, bytes only (so a
battle from 4096, a squad from 768 or a map past 255 can't be one), and
start it at once, with no deploy prompt. The remaster's list reads each
floor's name and words from the DeepDungeon table (sheet 0x65) by its
place in the list. The Deep's 40 battles' EntryNo rows name no prompt.

**What this helper does.** It hooks the entries (in C#): a mod's dungeon
lists its floors listed now, those from the start and those whose flag is
set, each `0xB8ED` plus its place among the dungeon's floors. The three
tests of the Deep, the floor's ask of the world events and the list's two
reads of a row go through the places' native code (`Destinations.cs`): a
mod's dungeon's list its own block (its count, no floor marked cleared),
its screen the Deep's; a floor chosen asks the helper, which picks one of
the floor's battles the story has reached, evenly, and keeps it where the
roll keeps a battle ground's (its squad, battle and map), then the random
battle's setup runs (`0x248254`, as after a battle ground's prompt
answered yes) and the floor's code leaves as the Deep's does; a floor's
row is the helper's (its name, and its words centered as the game's).
Each floor's battles are planned as a battle ground's (their own units
numbered from 4096, their squads from 768, kept as `Battles` and
`Squads`), with no deploy prompt, as the Deep's own. Said once: `Old
Quarry (Test 49 Dungeon) is a dungeon of 2 floors: Upper Pit (listed from
the start): Pit Goblins is battle 4096 on map 76, its deploy area squad
768; ... | Lower Pit (listed once The Hermit's Hermit visit done is set,
flag 4096): ...`; as it is chosen, `Old Quarry (Test 49 Dungeon) lists 1
floor.`; as a floor is, `Old Quarry (Test 49 Dungeon)'s floor Upper Pit
starts its battle Pit Goblins (battle 4096, map 76).` A floor waiting for
a flag its mod's quests don't have, or with no battle that can be fought,
isn't listed, said. Without what it needs found (the entries, the sites,
the squads), the mods' dungeons list no floor, said. Mod Studio's New
Content page makes a dungeon on a place's card (Kind: Dungeon; Add a
floor, each floor's card its name, words, the flag it waits for and its
battles).

### Two modders' quests and battles of one name (1.22.0)

Zodi's list, his ninth: "what happens when two different modders give
their quest the same exact name. What if they give their battle the same
name". What the helper numbers, it keeps by the mod's id, the quest's
name and the name (`Numbers.json`: `<mod id>/<quest>/<name>`), so two
mods' quests, events, battles and flags of one name are numbered apart
and play side by side (measured 28 October: two copies of test 35's mod
under two ids, every name alike, planned with nothing to say; test 14 had
two mods' events and flags of one name play in his game). What was left
was the log: it named a quest's events, flags and battles by the quest's
name alone, and a mod by its name, which two mods may share.

**What this helper does.** A mod's name in its log has the mod's id
beside it when another mod loaded has the same name (`Framework.LogName`:
`Thieves at Gariland (Test 51 Same Names, modstudio.test51.first): ...`);
a quest's events, flags and battles carry their mod's name when another
mod's quest has the same name (`Thieves at Gariland (Test 51 Same Names,
modstudio.test51.second)'s Ambush opening begins (event 1075).`), as do
a battle ground's or a dungeon's battles when another mod's place has its
name. A name no other mod shares is said as before. Mod Studio's New
Content page refuses a second quest of one name in one mod (its folder is
its name).

### A dungeon's own looks, its battles at once, and the location list (1.23.0)

Zodi's test 49 (2 November: "success", and three things shown wrong):
"After selecting the Old Quarry the dungeon UI still said "Midlight's
Deep", "About Midlight's Deep", and "Exit Midlight's Deep""; "after
selecting upper pit or lower pit there was a white flash when
transitioning to the battle as if it were a random battlefield battle.
For the dungeon in vanilla it is straight to black to the battle."; "Our
new modded in locations are not appearing in the location list. There are
three types, Settlements, Battlegrounds, and Miscellaneous." His answers:
"Exit Old Quarry" and "About Old Quarry" (the dungeon's name where the
game's words name the Deep, in each language; a page of the dungeon's own
showing its place's description), "Its own art" (one of the game's places'
art or the modder's own, the location list's too), and "As the game sorts
its own". A dungeon's place file may name its art:

```json
"Kind": "Dungeon",
"Icon": "19",
"Description": "Its pits run deep into the hills.",
"Art": "msq_mymod_old_quarry__art_uitx",
"Floors": [ ... ]
```

- `Art`: one of the game's places by its number, whose art the dungeon's
  list and its location info show (0 to 19, or 21 to 23: the towns and the
  other places with a settlement's art; 20 has none), or its own art's
  files' name, its two files at the game's paths as a town's menu's own art
  (680 by 452). Without it, Midlight's Deep's (22). Only a dungeon has one.
- Its `Description` is its list's About page too; a dungeon without one has
  no About prompt.

**What was measured** (`dev/research/sidequests/dungeon_places.py`).
The Deep's list (the world map frame's + 0x60) shows the UI text 1620 as
its title (`worldmap_deep_dungeon_ver02.uib`: DeepDungeon, DeepDungeonList,
Title, Text00), its Thumbnail (+ 0x268) the Deep's Town row's art (18), and
the button guide 0xBBD while the frame is in its mode 4 (`0x1579E7`): "Exit
Midlight's Deep" (1607), Enter, and "About Midlight's Deep" (1614, its row
2), the About key opening the guide 0xE6's page (`0xEE118`, called at
`0x157E5A`; the page a GuidePage row, sheet 0xBC, read at `0x1A798E`). The
UI's text by its number is `0x3DBE88` (sheet 0x13), a row by two keys
`0x3DBCE4`, a button guide shown `0xEB65C`, a place's name by its number
`0xFB44C` (the Deep's, text 1230, in the language shown), a text box made
again `0x3F1234`, a thumbnail's art set by its path `0x158D98`. The random
battle's setup queues the world map's transition (`0x2CC2E0`, kind 0: the
command 0x23 last in its commands at `0xD4C948` by their count at
`0xD8DBA0`, its kind at + 0x20 of its record, 0x5C bytes each from
`0xD8D8C0`); the handler (`0x2CC42C`) flashes white for kinds 0 and 1 and
leaves at once for 2 (`0x2CC52A`), as 33 of the game's world events that
load an event ask; the Deep's floors leave their own way (`0x345AFA`). The
location list (`0x36E5DC`, UIAddonFFTOWorldMapBaseList) goes over places 0
to 47 only, each shown place an entry of 0x40 bytes (its place, its sort:
its Town row's + 0x20; the story's next place marked 3, a midway one 2;
the Poachers' Den; Ramza's place), put last in its tab (the list's
+ 0x6A0, 0x20 each, by its Town row's kind, + 0x24: 0 Settlements, 1
Battlegrounds, 2 Miscellaneous) or the tab grown (`0x1CBF50`); then each
tab sorted by its entries' sort, then place.

**What this helper does.** A mod's place's Town row is given its kind as
the game sorts its own (a town with a menu 0, a battle ground 1, a dungeon
or a town without a menu 2: `Destinations.KindOf`) and a sort after the
game's (1000 and its number); after the list's loop over the game's places
(`0x36ECF6`), the places' native code gives each mod's place shown on the
map an entry as the game makes its own, in its tab. A dungeon's floor,
after the random battle's setup, gives its transition (the last command
queued, when it is 0x23) kind 2: straight to black. Four hooks (in C#,
`DungeonLooks.cs`): at a mod's dungeon (Ramza standing there), the UI
text 1620 is the dungeon's name and 1607 and 1614 the game's words with
its name where they name the Deep (any capitals); the About key's page,
while the list is up, its own (its name and description); a dungeon
without a description has no About row and its About key opens nothing.
As a dungeon's list opens (the entries' hook), its title is made again and
its Thumbnail given its place's art by the game's own setter: a mod's
dungeon its Town row's art (a game place's, or its own through the base
art's path, as a town's menu's own art), the Deep its own again. Said
once a session: `Old Quarry (Test 52 Dungeon Looks)'s list shows its own
name and art, and its About page its description.` (or `; it has no
About page.`), `Old Quarry (Test 52 Dungeon Looks)'s About page opens.`;
without what each needs found, `the mods' dungeons' lists show Midlight's
Deep's name, words and art: ...`, `the mods' dungeons' battles start with
a random battle's white flash: ...` or `the mods' own places aren't in
the world map's location list: ...`, each with what wasn't found. The
functions it hooks are found past their first instructions (as far as
another mod's hook of 14 bytes reaches). Mod Studio's New Content page
gives a dungeon's card Its art (one of the game's places', or your own).

### A mod's town's panel in the location list, and arriving at a mod's place (1.23.1, 1.23.2)

Zodi's test 52 (2 November: "Test 50 and 51 ran perfectly as you
described. Test 52 ran into issues."): "The Hermit's rest Settlement
location menu UI seemed to just copy the last towns UI" (it showed Trade
City of Sal Ghidos), and "I went and selected Old Quarry on the map and
when I traveled there the game crashed" (`0xc0000005`, "Fault offset:
0x0000000000342116"; Old Quarry was place 69).

**What was measured** (`dev/research/sidequests/dungeon_places.py`,
`destinations.py`). The location list's panel (`0x1607D4`, as its list
is made and as the cursor moves) looks up the chosen entry's place's Town
row: a battle ground's (kind 1) it leaves as it is; for the others the
location info (`0x158CB0`) fills its town part (+ 0x700, the one shown
under Settlements) when the row's + 0x31 is set, else its plain part
(+ 0x718) and no more. Only the game's towns, 0 to 14, have + 0x31 set.
The town part then shows the errands (as the game's progress has them:
the user situation 0xC94; their counts the entry's + 0, + 4 and + 8, none
the text 1583, "None available at this time.") and one icon for each of
35 kinds of item, On where the entry marks the kind (+ 0x10 on). The
list marks them for the game's towns (`0x36EB25`): each of the
Outfitter's five lists (1 to 4, then 7) asked of its stock (`0x288E54`,
no unit, not checked or sorted) into the items' list (`0x1811470`), each
item's kind the byte + 5 of its data (`0x2B8C44`), below 35. As Ramza
arrives at a place, the travel's step keeps the place plus one at
`0xD496C4` and the PlayStation world map draws its name (`0x3433FC`, its
only read of it for the name at `0x343421`): the sprite 0x36 plus that,
of a table of 123 (`0x693A50`; read only by the drawer, `0x3420BB`). The
game's places' names are sprites 55 to 102; a place from 48 to 67 asked
another of the table's sprites, a place from 68 on one past its end, whose
frames the drawer read from memory that isn't there (`0x342116`).

**What this helper does.** A mod's town with a menu has its Town row's
+ 0x31 set, as the game's towns: its panel's town part is filled with its
own art and words, its errands (none, so "None available at this time."
once the story shows errands), and its kinds' icons; the places' native
code after the list's loop (`ListStub`) marks its entry's kinds as the
game marks its towns', its five lists asked of the stock for its place
(the helper's stock hook gives a mod's town its own items, as its
Outfitter shows them). The world map's read of the place arrived at for
its name (`0x343421`) goes through the places' native code: a place of
the game's as before, a mod's place none (no name drawn, as when Ramza
has arrived nowhere). Without what each needs found: `the mods' own
places are shown only, their roads to them drawn only: the world map's
name of the place arrived at wasn't found in ...` (no place of a mod's a
destination, so none arrived at), or `the mods' own places aren't in the
world map's location list: the location list's kinds of a town's shop
wasn't found in ...`.

**1.23.2** (Zodi's test 53, 18:20: "The location menu is now working
correctly. Futhermore, now I can stand on Old Quarry but clicking on it to
bring up its menu crashes the game", `0x342116` again). As a place's menu
opens (`0x344B68`, its place in r14), it makes the PlayStation menu's name
of its place a slot of the sprites' list (`0xD4C4B0`, 36 bytes each) with
the sprite 0x37 plus the place (`0x344C2B`), of the same table of 123: a
place from 68 on past it. The places' native code (its `lea` and the
instruction after it, 16 bytes) gives a mod's place there the game's
blank sprite (122: no piece to draw, but one in the game's mode 2, whose
dates draw it). Every write of a sprite's number into the sprites' list
read where it is made (22 from a register, only this one from a place),
and the drawer's two other callers (the date, and the name of the place
arrived at): no other name is drawn by a place's number. Without it found:
`the mods' own places are shown only, their roads to them drawn only: the
menu's name of its place wasn't found in ...`.

### A dungeon's floors listed once the floor before is won, and its prompt (1.24.0)

Zodi, with test 54 (2 November, "a complete success"): "I know some
people want to make a dungeon where after they defeat all enemies the
next floor becomes available and so on. With the tools and functionality
we have so far is that possible. If not it should be." His choice, "Win
once": any one battle of a floor won once lists the next floor from then
on. And his test 54's answer, "standing on Old Quarry it says "Enter
Settlement" and standing on Midlight's Deep it says "Enter Midlight's
Deep"", his choice "Enter Old Quarry". A floor's `Opens` has a third
way, the floor before it won (never the first floor's):

```json
"Floors": [
  {"Name": "Upper Pit", "Battles": [...]},
  {"Name": "Lower Pit", "Opens": "FloorBeforeWon", "Battles": [...]},
  {"Name": "Deepest Pit", "Opens": "FloorBeforeWon", "Battles": [...]}
]
```

**What was measured** (`dev/research/sidequests/dungeon_places.py`, a
battle won and the world map's prompt; the PlayStation's names as
fft_decomp has them, read for facts). The battle's turn check
(`0x2387C4`, the PlayStation's scenario check of the menu's requests)
asks the battle's outcome (`0x30FC00`: 0 every enemy beaten, less than 0
the party beaten). Lost, its battle started, the event playing (variable
0x27) is given the game over (0x190). A battle with rules of its own (its
scenario's events on, `0xD407CC`) goes by its rules. Else, every enemy
beaten, it is given the battle won event (0x192, the one that says
"Victory is yours!") through `0x233368`: the variable cleared, then the
number added, each by the events' variable function (`0x242700`, which
the helper hooks); its task is started (`0x236378`). A random battle, a
dungeon's floor's among them, has no rules of its own; a battle fled
("Return to World Map") or lost never gets it. With the cursor on the
place Ramza stands at (`0xD493E8`), the help of the place under the
cursor (`0x15B970`) gives the Deep its button guide 0xBC5 (its fifth row
the UI text 1626, "Enter Midlight's Deep") and a place whose screen
row's kind is 0, a town's and a mod's dungeon's (drawn as a town is),
the guide 0xBC1 (its fifth row 1618, "Enter Settlement"); the two
guides' other rows are the same. A guide shown makes its rows' words
again unless it is the guide and rows shown already (`0x13D5F4`).

**What this helper does.** Each floor that waits for the floor before it
gets that floor's won flag, a flag in the quests' bank given as a quest's
flags are (`Flags`, its key the mod, the place and the floor). In the
events' variable function, before the game's own: the event playing
given the battle won event while Ramza stands at a mod's dungeon, the
floor chosen (variable 92) one of whose battles is the battle fought
(variable 50), and a floor waiting for it: its won flag set (never while
a scene is replayed), the save marked with the numbers as a quest's flag
marks it. All of it is the game's own variables, so a battle saved and
loaded before it is won counts too. Said: in the dungeon's line, `Lower
Pit (listed once Upper Pit is won, flag 4233)`; as a floor is won, `Old
Quarry (Test 55 Floors Won)'s floor Upper Pit is won: Lower Pit is listed
from now on (flag 4233).`; won again, `...'s floor Upper Pit is won
again.` A floor whose floor before it isn't listed isn't listed either,
said. At a mod's dungeon the UI text 1618 is the game's 1626 with the
dungeon's name where it names the Deep (as Exit and About: `Enter Old
Quarry`, French's `Pénétrer dans les Old Quarry`; German's has no name,
`Betreten`, as the Deep's). Mod Studio's New Content page offers it on a
floor's card, Listed: `Once the floor before it is won` (not on the
first floor's; a floor taken out leaves the floor now first listed from
the start).

### A quest's step waiting at a dungeon's floor, its first battle (1.25.0)

Zodi, 2 November, while test 55 was being made: "in Midlight's Deep
Dungeon when the player reaches the final floor "END" for the first time
a specific battle occurs and a scripted event occur at the beginning and
end of the battle after they defeat the boss. After winning and the
players selects "END" again afterwards then it selects from a random
battle on that map. That first boss battle that plays the first time you
play that floor never happens again. Do we support this functionality as
well? If not we should." It didn't. His choices: how it is made his to
leave ("What ever makes the most sense for the logevity, compatibility,
and most functionality for modders of the Mod Studio Framework"), "Boss
again until won", and "Yes, it counts" (winning it counts as winning the
floor). Made so: a quest's start whose place is one of its mod's own
dungeons may wait at one of its floors, `Floor`:

```json
"Starts": [
  {"Place": "Old Quarry", "Floor": "Deepest Pit", "When": [{"Flag": "Quarry boss done", "Is": 0}],
   "Event": "Quarry boss", "Passing": "Waits"}
]
```

As the floor is chosen while its conditions hold, its event plays in
place of the floor's battle: a quest's battle with everything a quest's
battle has (its units, map, music, deploy areas, a scene as it starts
and one once won, how it is won and lost, its objective), or a scene.
A step Mod Studio makes plays once (its own flag 0, set as its last
scene ends), so its battle plays each time the floor is chosen until it
is won, then the floor's own battles; any other conditions (the story,
another step done, someone in the party) are a start's. Its battle won
counts as the floor won. Its quest's marker shows at the dungeon while it
waits. A travel never passes through a floor: its `Passing` can't be
`Stops`.

**What was measured** (`dev/research/sidequests/dungeon_places.py`,
`first_facts` and `first_runs`; the 1.5.2 database's
EnhancedWorldEvent). The Deep's END (its world events' chains 9 and 10:
variable 92 is 9, then variable 149 is 0 or 1) loads its kind 30 with
the event 111 the first time (its setup the boss's battle, EnemyBattle
402, by its rules 36: a scene as it starts and one once won; event 113
sets variable 149), then 114. The world map starts the event a place's
chains loaded at `0x247E10` (ecx which of them): the last command's
sprite hidden (the queue's count at `0xD8DBA0`, each command's record
of 0x5C bytes at `0xD8D8C0`, its first number a sprite of `0xD4C4B0`),
variable 0x27 given the event (`0xD493CC` plus which times 4) by the
setter (`0x2E9918`), its transition queued (`0x2CC2E0`) by its kind
(`0xD493D0`: 1 a white flash, 2 at once), the state's bit 13 set; a
place's event without a prompt (`0x248076`) and a prompt answered yes
(`0x247697`) call it. A floor chosen closes the menu first (`0x345EFC`:
its command off the queue, bit 13 cleared), so the queue is the place's
as when a place's event starts. The battle then loads by its event's
setup (`0x2FB7C8`: the record whose event is variable 0x27 found in the
setup table, its map to variable 0x33, its EnemyBattle to variable 0x32
when it has one, its deploy areas to 0x34 to 0x36, its rules loaded and
counted at `0xD407CC`), as a quest's battle at a place does, whatever
the world map's mode (`0x246078`: the state's bit 25 the Deep's own 4,
bit 21 or 18 an event's 2, bit 15 a random battle's 1). A random
battle's way would give it a random battle's weather (`0x304330`, by the
month and day) and music (the battle's setup's state 11); the Deep's
own way (4) does what the Deep's battles do. So the helper starts it the
way a place starts its event: the event's own setup, music and weather.
Its battle's rules give the event playing its won event as it is won
(`0x239294`'s load, 25: the variable cleared, then the event added,
through the events' variable function).

**What this helper does.** A start waiting at a floor is planned with
the dungeons (after the quests): its conditions as the world map's
steps, its event loaded at once (a battle as itself, a scene its
opening), at its floor (its place among the dungeon's floors); one whose
dungeon has no such floor listed is said and left out. The floor slot
(`Hooks.Floor`, asked by the floor's native code) first tests the
floor's starts, in the quests' order, as the world map tests a place's
(`Framework.FirstHolding`, by `Holds`, as the markers are): the first
whose conditions hold has its event written where a place's chains load
theirs (`LoadedEvent`, its kind 2 at `LoadedKind`) and answers 2; the
native code then calls the world map's start of an event (ecx 0) and
goes out as the floor code goes out. Else the floor's battle as before.
With nothing on the world map's queue (never seen) the floor's battle
is fought instead, said. In the events' variable function, the event
playing given a won event of a start's battle at the dungeon whose floor
chosen (variable 92) is that start's (`Framework.FirstWonFloor`) sets
that floor's won flag, as the battle won event of one of its own
battles does. Found: the world map's start of an event (`EventStart`,
its first 14 bytes not looked at), the event it loads and its kind, the
queue's count it reads (the transition's); else said, and a start
waiting at a floor is left out. Said as it is planned, after the
dungeon's line: `Quarry Boss (Test 56 First Battle)'s Quarry boss (event
1078) waits at Old Quarry's floor Deepest Pit: the floor plays it in
place of its battle while its conditions hold.`; as the floor is chosen,
`Old Quarry (Test 56 First Battle)'s floor Deepest Pit plays Quarry Boss
(Test 56 First Battle)'s Quarry boss in place of its battle (event
1078).`; won, as a floor's battle won, `...'s floor Deepest Pit is won:
Pit Bottom is listed from now on (flag 4236).` Mod Studio's New Content
page offers each floor of the mod's dungeons as a step's Place (`Old
Quarry, floor Deepest Pit`), and a floor's card lists its First battle.

### A floor's win said once a battle (1.25.1)

Zodi's test 56 (2 November): "Test 56 was a complete success and
functioned exactly as you described", and its log showed one line wrong:
as the Chemist fell, `Old Quarry (Test 56 First Battle)'s floor Deepest
Pit is won: Pit Bottom is listed from now on (flag 4236).` and in the same
second `Old Quarry (Test 56 First Battle)'s floor Deepest Pit is won
again.` The floor was won once.

**What was measured** (`dev/research/sidequests/dungeon_places.py`,
`peek_facts`). As an action ends the battle asks its turn check
(`0x2387C4`) twice: first only to see whether an event would play (its
mode 2), then to play it (mode 0); its three callers (`0x202686`,
`0x204BC1`, `0x21263C`) ask mode 2, then, an event set aside whose
attributes say so, mode 0. In mode 2 a battle with rules of its own runs
them (`0x2391C4`; their play, 25, gives variable 0x27 the event through
`0x233368`, the events' variable function), sets the event they loaded
aside (`0x2FF8274`) and gives the event playing back the value it had as
the check began; mode 0 runs them again and plays it. So a quest's
battle's won event is given twice. A battle with no rules of its own (a
floor's random battle) has the battle won event only set aside in mode 2
(`0x238A6E`) and given once in mode 0, as test 55 showed.

**What this helper does.** A floor's win is one win a battle, a battle
being from its floor chosen: the floors whose win was given since a
floor of a mod's dungeon was chosen are kept (`Framework.FloorWins`,
cleared by the floor slot, `Hooks.Floor`); a win given again in the same
battle says nothing. Its won flag is set the first time it is given, as
before, and `...is won again.` is said only when the floor was won before
this battle.

### A mod's own items at its town's Outfitter (1.26.0)

Zodi's list of 3 November, his first: "Adding new items to go into the new
towns outfitter". His choices (asked once measured): new items first; an
Items tab on the New Content page; an icon of the game's or a texture of
the modder's own; a new item started as a copy of one of the game's. A
mod's item is a folder of its own, `ModStudioItems/<item>/item.json`
(`mod_studio/mod_items.py` writes and reads it; `ItemFile.cs` reads it here
and says the same problems):

```json
{
  "Format": "Mod Studio item",
  "Version": 1,
  "Name": "Moon Sword",
  "Kind": "Weapon",
  "Record": [1, 16, 15, 128, 24, 3, 0, 0, 192, 18, 1, 0],
  "KindRecord": [1, 142, 1, 255, 14, 5, 64, 0],
  "SpritePair": [112, 2],
  "Bonus": null,
  "Words": {"Name": "Moon Sword", "Singular": "moon sword", "Plural": "moon swords",
            "Description": "Test 58: a mod's own sword, a copy of the Coral Sword with a Power of 14."},
  "Icon": 24,
  "UiCategory": 3,
  "Sort": 206
}
```

- `Kind`: Weapon, Shield, Head, Body, Accessory or Item.
- `Record`: its 12 bytes as the game keeps an item's (its palette and
  sprite, the level it is found from, its type flags, which must be its
  kind's, its category, its equipment bonus row, its price, the story
  point the shops sell it from, 1 to 16); `KindRecord` its kind's record
  (a weapon's 8 bytes, a shield's, a head's, a body's or an accessory's 2,
  an item's 3); `SpritePair` a weapon's or a shield's two bytes; `Bonus`
  its equipment bonuses' 26 bytes, or none. The helper gives the record's
  kind number and bonus row itself.
- `Words`: its name (1 to 64 characters) and, if it has them, its
  singular, plural and description (up to 400 characters, two line
  breaks at most): its row in the Item table, the same in every language.
- `Icon`: one of the game's items' icons by its number (1 to 253, 256 to
  260), or its own texture's files' name, the files beside the game's item
  icons in the mod (`FFTIVC/data/enhanced/ui/ffto/icon/equip_item/` and
  `equip_item_s/`, a 100 by 100 and a 48 by 48 texture with their part
  lists).
- `UiCategory`, `Sort`: its Item table row's menu tab and order, its
  copy's.

A town's `Menu` names its mod's items by their names in its `Shop`, after
the game's numbers: `"Shop": [1, 19, 51, 59, 128, 157, 186, 240, 246, 253,
"Moon Sword", "Star Cape", "Elixir Plus"]`.

**What was measured** (his program read as data, never run;
`dev/research/sidequests/items.py`; WotL Restoration 2.0.7's DLL's strings
and metadata read for facts only, its code never copied). The game's items
are 1 to 253 and 256 to 260 (`IsValidItem`, `0x2B8EBC`); each is found
through nine small functions: its segment (`0x2B8BCC`, the boundaries at
`0x6804E0`), its 12 byte record (`0x2B8C44`), its kind's record (a
weapon's `0x2B8C74`, a shield's `0x2B8CD4`, armor's `0x2B8D3C`, an
accessory's `0x2B8DA0`, an item's `0x2B8E04`, each in the PlayStation's
table or the remaster's), its sprite pair (`0x2B8E60`) and whether it is
an item. The bag of counts (261 bytes, 0 to 99 each), the owned copy, the
85 equipment bonus rows and the menus' lists are arrays the game's code
reaches in 63 places; 44 walks over the bag stop at 0x105; the Outfitter's
stock (`0x288E54`) walks 0 to 255. WotL Restoration adds its 40 items,
numbered 261 to 315, as it loads: a page of memory within 2 GB of the
program holding the arrays with room, the 63 reaches pointed at it, the 44
bounds raised to 0x13C, the nine functions hooked, 14 list pointers
pointed at its page's lists, two calls of the item test sent to the game's
own test, and a thread keeping the game's own arrays and its page's alike;
it keeps its items' counts in the event variables' bytes 0x2FC to 0x33A.
120 sites in all, each found by its own bytes, again with WotL
Restoration's changes made.

**What this helper does.** It numbers every mod's items from 316, past
the game's and WotL Restoration's, to 381 (the walks the game bounds with
a byte reach no further where they are), in Reloaded-II's order, the same
number every time (`Numbers.json`'s `Items`). With WotL Restoration's page
already made it takes that room on: it raises the bounds again and hooks
the nine functions for its own numbers first (native code, the game's own
after it). Without, it makes the same room itself, its own page. All or
none: every change checked against the bytes it replaces before any is
made. Each item's equipment bonuses get a row past every row an item
names (the game's 85, and another mod's); its words a row of the Item
table as it loads (its UI category and sort its copy's); its icon the
game item's it names, or its own (the Icon table's two paths hooked); its
count kept in the save's event variables, one byte a number from the
bank's mark down (0x3FB for 316), as the game saves and as a save loads.
The side quests' flags are never given there (flags 6256 to 6783), nor
where WotL Restoration keeps its counts (flags 4736 to 5239), nor, from
1.38.0, in the eight bytes just before the items' counts, where a save's
mark of its units' progress in the mods' jobs is (flags 6192 to 6255). A mod's
town's Outfitter asks the game's stock for the game's items unsorted, adds
its own items it sells (each under its kind's tab, once the story reaches
its point), then has the game sort the list as asked; the Poachers' Den's
walks of its own stock are left as they are. Said as the game starts:

```
[Mod Studio Framework] the game's items have room for the mods' items: 316 to 381.
[Mod Studio Framework] Moon Sword (Test 58 Items) is item 317, a weapon, its icon the game's item 24's.
[Mod Studio Framework] Star Cape (Test 58 Items) is item 318, an accessory, its equipment bonuses in row 85, its icon its own.
[Mod Studio Framework] Item: the mods' items' 3 rows added.
```

(with WotL Restoration's room, "..., past WotL Restoration's: 316 to
381."). An item that can't be read is left out and said; past 381, or
with no bonus row left, left out and said; a town naming an item its mod
hasn't, said, the rest sold. Mod Studio's New Content page makes an item
on its Items tab and sells it on a town's card (Enter Settlement: the
Outfitter offering the mod's own items first).

### The game's own Outfitters, and what an item does (1.27.0)

Zodi's observations of 3 November after test 58 ("Test 58 was a complete
success"): a new item's Formula, Inflict Status or Cast Spell, and its
equipment bonuses' statuses and elements; its small icon and its art
apart; the game's own Outfitters selling it ("If it is simple to support
we should"); its UI values set for the modder from what it does; no new
items to use for now. His choices: the game's 15 towns ticked on the
item's card, none to start; an item to use made before kept, its card
saying why; the UI values set automatically and shown. An item's file
may name three more fields (after `Sort`, each read here and by Mod
Studio alike, each problem said in the same words):

```json
  "Shops": [6, 9],
  "UiStatus": 1001,
  "RandomDamage": true
```

- `Shops`: the game's towns whose Outfitters sell it, each by its place
  (0 Royal City of Lesalia to 14 Trade City of Sal Ghidos), once; none
  when it isn't there.
- `UiStatus`: its Item row's UI status effect (+ 0x1C, 0 to 65535), and
  `RandomDamage` its random damage (+ 0x2D), as Mod Studio sets them from
  what the item does, the game's own rows' way for all 258 of its items: a
  weapon whose formula takes the hit points it deals (6, the Blood
  Sword's) 1001, one that heals by them (7, the Healing Staff's) 1002;
  random damage for the axes, flails and bags (categories 6, 9 and 17),
  or a weapon whose formula casts by its element (4, the magic guns').
  0 and false when it isn't there, as 1.26.0 wrote every row.

The formula, the spell and the elements are bytes of `KindRecord` and the
statuses and elements of `Bonus`, as before (FFTPatcher's layout, read for
facts: a weapon's formula + 2, its elements + 6, its Inflict Status or
spell + 7; the bonus row's statuses always had + 5, immune to + 10, at a
battle's start + 15, five bytes each; elements absorbed + 20, cancelled
+ 21, halved + 22, weak to + 23, strengthened + 24). Its small icon's
texture is its own when Mod Studio was given one, else made from its art.

**What this helper does.** It hooks the Outfitter's stock (`0x288E54`)
for the game's towns any item names: a town's own list asked of the game
unsorted, the mods' items it sells added as a mod's town's are (each
under its kind's tab, once the story reaches its point, marked or left
out as the list asks when the unit can't use it), then the list sorted as
asked (`0x285B10`, kind 6). The stock's three calls are read from its
code by their bytes for both hooks (`Places.StockCalls`). A mod's town's
Outfitter asks the game's stock through Sal Ghidos's place (1.18.0's
borrowed shop bit): that call is let past this hook (`Hooks.Borrowing`,
set round it), so a mod's town never lists Sal Ghidos's mod items,
whichever hook wraps the other. Said as the game starts, after each
item's line:

```
[Mod Studio Framework] Moon Sword (Test 59 Items) is sold at the Outfitters of Magick City of Gariland and Merchant City of Dorter.
```

and, if the stock's calls aren't where they were, "the mods' items aren't
sold at the game's own Outfitters: the stock's calls aren't where they
were. A game update may have changed it: look for a newer Mod Studio
Framework." (the items sold at the mods' towns all the same). Each item's
Item row gets its `UiStatus` and `RandomDamage`.

**A weapon's look in battle** (his second observation, its third texture:
"the in game attacking animation texture"; his choice "A game weapon's
look"). Measured in his program: the weapon's sprite pair (`ItemSpritePair`,
`0x2B8E60`) is read only by the swing, at `0x26A3CD` (its first byte: the
high four bits one of the 16 palettes of the game's one weapon texture,
kept at `0xD35750`, 32 bytes each, the low four bits a second palette
loaded with it) and at `0x26BC89` (its second byte: the look's row on
that texture, eight pixels a row, in its type's column); the enhanced
look's is the g2d texture 161 (`0xA1` given at `0x2617F1`), its colors
still the palettes'. The record's first two bytes (FFTPatcher's Palette and
Graphic) draw only the classic icon and the item a unit holds up or
throws, never the swing. The weapon types whose swings share their frames
(so one column): the ninja blades, swords, knight swords, katanas, rods and
staves; the axes and flails; the spears and poles; every other type its
own. Mod Studio writes the look picked as the item's `SpritePair`, which
this helper gives the game for a mod's item since 1.26.0 (its hooked
`ItemSpritePair`); nothing new here. A texture of the modder's own would
mean changing the one texture every weapon shares (two mods' would take
each other's place): not built.

### The game's own weapons' looks in battle (1.28.0)

Zodi, 3 November, after tests 59 and 60: "We should probably also apply
our item's sprite pair findings to the Items page on the Mod Studio so
that users can also change the vanilla items look and palette". The game
keeps its weapons' sprite pairs in its program, not in a table the mod
loader changes, so the Items page's In battle (Looks like and Palette, as
the item card's; since 4 November its Attack, beside Held or thrown) goes
into one file at the mod's root,
`ModStudioItemLooks.json` (`ItemLooks.cs` reads it here, Mod Studio's
`mod_items.read_looks_text` alike, each problem said in the same words):

```json
{
  "Format": "Mod Studio item looks",
  "Version": 1,
  "Looks": [
    {"Item": 19, "SpritePair": [224, 14]},
    {"Item": 51, "SpritePair": [64, 26]}
  ]
}
```

- `Item`: one of the game's items by its number (1 to 253, 256 to 260);
  `SpritePair` its look's two bytes. A look whose item or pair can't be
  read, or a second look for one item, is left out and said; a file whose
  Format, Version or Looks can't be read, all of it.

**What this helper does.** As the game starts, after the mods' items, it
reads every mod's looks in Reloaded-II's order (a later mod's look for an
item in place of an earlier's, said), finds the game's own ItemSpritePair
(`0x2B8E60`) among the items' sites by its bytes, and for each look asks
it where that item's sprite pair is: for the game's items up to 255
`0x785CF0` plus twice the number (the program's data), for 256 and 257
`0x672B54` plus twice it (its read only data), none for an item without a
look in battle (an item to use, 258 to 260: said, left as it is). It makes
those two bytes writable, writes the look, and gives their protection
back, said:

```
[Mod Studio Framework] the game's item 19 swings another look in battle (Test 61 Game Looks): its sprite pair 224 0 made 224 14.
```

Every look is the game's own sprite pair table changed in place, so the
classic look and the enhanced look show it alike, and a mod taken out
leaves the game's own looks the next time it starts.

### Quest maps and rumors numbered at each start, and freeing numbers (1.29.0)

Zodi's sixth of 3 November: "you said there is only room for a total
history of 66 new items and 37 new Tavern rumors I can foresee that being
a problem almost instantly. Once many modders and users begin consuming
mods. In a perfect scenario we find a way to let users have a total
history of hundreds for both and very simple process to flush out old
unwanted items and rumors and to an extend Quest Maps that take up
valuable real estate." His answers: quest maps and rumors "What ever is
best for the longvity, compadibilty and success for mod studio and what
ever gets to us being able to have many loaded at the same time";
freeing numbers "Tick in Reloaded-II (Recommended)".

**What was measured** (his program read as data). No save keeps a quest
map's number: a battle's map is its setup record's byte, which the helper
writes as the game starts (1.10.0). A save keeps a rumor only as its two
bytes from `0x11A7299` (the first 0 once read, the second its news still
to come; both 1 on a new game, `0x33FCB8`), which the game reads only as
zero or not (the tavern's new mark, `0x19E35C`; the news; the world map's
towns) and writes only as a read's 0 and a new game's 1. The tavern marks
a rumor read through its agent (`0x19D548`, called through a pointer: its
third argument the action, 0 a rumor marked read, its fourth the key).
An item's number, though, is in the bag's counts and in what units wear,
so it can't move while a save holds it; nor can an event's, a flag's or a
place's.

**What this helper does.**

- **Quest maps and rumors** (`Maps`, `Rumors`) are numbered afresh as
  each game starts (`Numbers.EachStart`: `BeginNow`, `GiveNow`,
  `SettleNow`): one enabled keeps the number it had while no other enabled
  one has it, a new one takes the first number no enabled one has, and the
  names of those not enabled are dropped, their numbers free for the next.
  Their room (quest maps 129 to 255, rumors 27 to 63) is what is enabled at
  once, never what was ever installed; while the same mods are enabled,
  nothing moves. A quest map or a rumor past it is left out, said: "the
  quest map Map 127 (modstudio.full) is left out: no map number from 129
  to 255 is left (they are the quest maps enabled at once)."; "... is left
  out: no rumor number is left for X (they are the rumors enabled at
  once)."
- **A rumor read stays read, whatever its key.** While a quest's rumor is
  unread, its key's first save byte holds its tag (2 to 255 from its name,
  FNV-1a over `<mod id>/<quest>/<rumor>`: 1 is a new game's), and the
  tavern's agent is hooked (the game's own first, then for action 0 the
  rumor's flag set, said, the save marked). Before the taverns read the
  bytes (their walk's key 0), before a quest's marker is shown and as a
  flag is read, each rumor's two bytes are made its own
  (`Framework.SettleRumors`): its tag there, it is its own and unread; 0
  with its flag set, its own and read; anything else (a save made when
  another rumor had the key, a new game's 1, another rumor's read 0) put
  right from its flag: read (0, 0) when it is set, else its tag and its
  news to come. Said once a start: "the side quests' rumors are read as
  the save loaded says (their keys given as the game started)."
- **His setting in Reloaded-II** (the mod's Configure: `Configurator.cs`;
  its file `Config.json` in the helper's Reloaded-II settings folder,
  `Settings.cs`): "Free disabled mods' numbers" (1.29.1, its words "At the
  next start, frees the numbers of mods that aren't enabled, says which in
  its log, then unticks itself."; 1.29.0 named it "Free the numbers of mods
  not enabled", which Configure cut short), unticked to start. Ticked, the next start, before anything is numbered, drops from
  every kind kept for good (items, places and their homes, events, flags
  and the rest; never quest maps and rumors, which free themselves) the
  names of every mod not enabled then (`Numbers.Free`), gives the numbers
  a new ID (a save made before says so as it loads: 1.13.0's line, which
  now names the setting), keeps them into every copy, says which mods and
  how many of each kind, and unticks the setting:

```
[Mod Studio Framework] freed the numbers of a mod not enabled: modstudio.test62.c (2 of its Events, 2 of its Flags, 1 of its Rules, 1 of its Scenes and 1 of its Texts). A save made with them says so as it loads. Its setting is unticked.
```

  With every mod they name enabled: "frees no numbers: every mod they name
  is enabled. Its setting is unticked." The setting takes from Reloaded-II's
  interfaces only what WotL Restoration's own settings take (built against
  2.4.0), so the helper still loads in a Reloaded-II from before 1.30.

Test 62 (`dev/research/sidequests/make_test62.py`): three mods, each one
quest whose rumor is told in every tavern from the start, its scene
waiting at its town until the rumor is read; enabled two at a time and
then all three, one rumor read, and the setting ticked with one of them
taken out.

### Ramza named as the party has him (1.30.0)

Zodi's test 64: a quest's scene named Ramza by one fixed identity. A
quest's event now lists where its script names Ramza (`RamzaInScript`,
which Mod Studio writes where a sample scene names unit 1), and as the
helper hands such a script over it finds the Ramza in the party as the
world map's test of a character does (`0x344134`: 54 units of 0x258 bytes
at `0x11A7D10`) and writes his identity there (1 in chapter 1, 2 in
chapters 2 and 3, 3 in chapter 4), saying which (his test 68's log: "Test
68 Quest's Battle start begins (event 769), naming Ramza as he is in
chapter 4."), or that he isn't in the party. Map 116 is named Battle Arena (PlaceName 950116) once a
quest plays or fights there, another mod's name for it kept and said
(`dev/research/sidequests/ramza.py`). Test 65.

### A quest's reward, and scenes during a battle (1.31.0)

Zodi's first of 3 November ("a reward as a quest ends"), his choices "Its
last step only" and "A line in the scene"; and his notes on test 65 (a
battle's three scenes, the balloons over their speakers). A quest's last
step's last scene may give gil (0 to 99,999,999), up to 8 items (the
game's by number, a mod's own by name, 1 to 99 each) and one of its own
units: the helper gives the gil (the war funds, `0x284684`) and the items
(the game's giving of an event's item, `0x101058`) as that step's flag goes
from 0 to 1, never as a scene is replayed, said (his test 68's log: "Test
68 Quest's Ending gives its reward: 1,500 gil, item 240 (3 of them) and
Wayfarer's Ring.").
Since test 66 the unit is asked to join by the game's own party changes
(DisplayConditions 7: the New Party Member screen, and with the party full
the dismissal screen), and the gil and items are said in the game's
narration (Mod Studio's scene, nothing of the helper's). A battle's During
gives it up to 4 scenes, each played once a battle as its unit's turn
comes or as its HP falls to a share of its most (0: beaten), its unit
Ramza or one of the battle's own, each chain as Gariland's scene on
Ramza's turn (`dev/research/sidequests/rewards.py`, `battle_scenes.py`).
Tests 65 and 66.

### A save's old side quest flags cleared as it loads (1.32.0)

Zodi's test 67 (5 November): "I tried it twice. The battle at mandalia
never appears after reading the rumor and after the Gariland event." Its
battle waits at Mandalia Plain for two of its quest's flags, Opening done
at 1 and Battle done at 0. His log said "Test 67 Quest's Opening done is 1
(flag 4110)" and never that the battle's marker showed, nor any marker at
Gariland: both saves he loaded already held Battle done (flag 4111), set
long before by quests numbered before his numbers were freed (1.29.0). His
second save the helper knew ("made with other side quest numbers") but only
warned of; his first was older than the saves' mark (1.13.0), so its old
flags were taken as today's quests'. Test 66's flags (4104 to 4107) had
happened to be clear in his saves. His choice (asked once measured):
"Clear them, and log it".

**What this helper does.** The numbers keep the marks they have had
(`Numbers.Marks`, the file's `"Marks"`: each its ID, the flags' bits given
with it, the flags' bits freed with it). A game start that gives flags no
name had makes a new mark as the side quests' plan ends (`Numbers.Stamp`):
a new ID, the numbers' own from then on, those flags its own, the ID they
had kept as an older mark. A free (1.29.0's setting) makes one too, with
the flags it freed. A save is marked with the numbers' ID as a quest flag
is set (1.13.0), and as a save loads (`Framework.Loaded`), the side quest
flags it can't really hold are cleared, said, and it is marked with the
numbers' own ID:

- marked with an older mark: the flags given or freed since, where set
  ("the save loaded was made before Test 68 Quest's Battle done (flag 4115)
  and Ending done (flag 4116) were given, and held old flags there:
  cleared, so that quest starts again in it."); the flags it was made with
  are kept;
- marked with a mark the numbers never had (freed before 1.32.0, lost from
  every copy, another computer's): every flag ("the save loaded was made
  with other side quest numbers (its mark 655261FB, these numbers'
  ...), so its side quests' flags are cleared: each quest starts again in
  it. ...");
- flags and no mark (made before 1.13.0): every flag ("the save loaded was
  made before side quest saves were marked (Mod Studio Framework 1.13.0),
  so its side quests' flags are cleared: each quest starts again in it.").

Only the flags' bytes are cleared: WotL Restoration's items' counts
(`0x2FC` on) and the mods' items' (1.26.0) are kept, and a save holding
only those is no save of quests. When copies of the numbers differ, a
later copy whose marks go on from the most trusted one's gives the ID (it
was written since). The save hook is given the quests' own numbers as
they were planned, so a save marked in this game is never taken for
another numbers' whatever a copy could be written. Freeing says "A save
made before has their flags cleared as it loads." when it frees flags.

Test 68 (`dev/research/sidequests/make_test68.py`): test 67's quest again,
renamed so its flags are new ones, for his saves of test 67.

### A quest unit's own name (1.33.0)

Zodi's second of 3 November, "a quest unit's own name"; his choice once
measured, "As a renamed unit". His program read as data
(`dev/research/sidequests/unit_names.py`): a renamed unit keeps its name as
its own text (64 bytes at a battle unit's `+ 0x14C`, a party unit's
`+ 0xDC`); the game's name getter (`0x1E8B7C`) shows that text in place of
a generic's name (its CharaName row's IsGeneric set), cut to 16 characters
in the remaster's mode, and a unit joining keeps it (`0x274EB8`). The
quest file's battle gives its units' own names (`Names`: each a unit's
place in the battle's file, 1 to 16, and its name: 1 to 16 characters,
none a control character, no space at either end; both readers say the
same), its units' names made Random by Mod Studio (a generic's name, so the
own text shows, and a generic's voice of its gender). The helper hooks the
game's making of a battle's unit from its battle file's entry
(`0x275CA4`, whose unit's setup ends by jumping to the name's assignment)
and, once the game has made it, writes the own name of a quest battle's
unit not from the party into it, said once a game ("Test 69 Quest's
Opening units: unit 1 named Ser Corvin."); without the hook's place:
"the side quests' units' own names aren't shown: ... wasn't found." The
name over its balloons is Mod Studio's: a `<speaker="...">` mark at the
start of each line it says (test 70, which passed). Test 69, which passed
(5 November).

### A mod's road shown and grayed with its places (1.34.0)

Zodi's last of 3 November, "a mod's road hidden until its places show,
grayed with them"; his choices once measured, "Once both its places show"
and "Gray with its places". His program and layout read as data
(`dev/research/sidequests/road_looks.py`): each of the game's 51 roads is a
picture box of the layout's Route, shown and hidden by `Show_R_` and
`Hide_R_` (its opacity, 1 and 0) as its own variable (556 + the road)
says, and 25 of them gray (`Color_Grayout`, 90, 90, 90) while they lie
ahead on the way to the story's objective, not with their places. A game
place shows by the game's test of a place shown (`0x1DF4F0`) and grays
while its Town row's situation holds (the screen's own test, `0x15AEF5`:
the row by `0x3DBC74`, its `+ 0x28` tested by `0xFF8A4`).

**What this helper does.** Each mod road's copy (1.4.0) is given its
look as the world map screen sets its pieces up and each time the screen
shows a place (`0x15AE14`, hooked here too: the story's drawing of a place
calls it while the world map is up): its opacity 1 once both its places
show, 0 while either doesn't; the game's roads' gray while either place is
grayed, white otherwise (`MapRoads.RoadLook`, `MapRoads.Look`). A mod's own
place always shows, and a mod's town is grayed once its Darkened flag is
set (1.20.0). Without what it needs: "the mods' roads are shown whatever
their places do: ... wasn't found. A game update may have changed it:
look for a newer Mod Studio Framework." Test 71
(`dev/research/sidequests/make_test71.py`): test 48's places, roads and
quest, and a road to Fort Besselat. It passed (5 November: "Test 71
functioned exactly how you said it would"): in his chapter 4 save Hermit's
Path and Quarry Trail white and Besselat Track gray, after The Hermit all
three gray, at a new game's first world map Quarry Trail alone shown.

### A save's old items taken out as it loads (1.35.0)

Zodi's word of 5 November, on the next session's recommendation: "a save
made before you freed numbers could hand out a new item for free, the same
kind of problem test 67's flags were." A freed item's number goes to the
next new item (1.29.0's free), and a save made before still holds the old
item there. His program read as data (`dev/research/sidequests/old_items.py`):
a save keeps a mod's item's number in its bag's count (this helper's, in the
event variables' last bytes, 1.26.0) and in what its party's units wear: the
game's load of a save (`0x21B0E8`) copies 54 units of 0x258 bytes from the
save's + 0x518 to `0x11A7D10`, each wearing seven items of two bytes at
+ 0x0E (head, body, accessory, each hand's weapon and shield), none 0xFF (as
the game empties a place), a place with no unit its byte 1 0xFF.

**What this helper does.** His choices: "Count and worn copies", "Keep their
items" and "Clear them too". The numbers' marks (1.32.0) write down the
mods' items' numbers given with them (no name having had them: a game start
that numbers a new item makes a mark, `Numbers.Stamp`) and freed with them
(`Numbers.Free`), as `Items` and `FreedItems` in `Numbers.json`'s `Marks`.
As a save loads (`Framework.Loaded`, the party its load fills found from the
load itself, `Places.Roster`), the items given or freed since its mark have
their counts cleared from its bag and their worn copies taken off its units,
said ("the save loaded was made before New Ring (item 316) was given, and
held old items there: 1 cleared from the bag and 1 taken off a unit."; an
item freed and not given since named by its number); a save made with other
numbers has every mod's item taken out ("...so the mods' items in it are
taken out: ..."); a save with no mark keeps its items and is marked with
the numbers (no free before 1.35.0 wrote down its items). A save holding
the mods' items, in its bag or worn, is marked with the numbers as it is
made (the items' save hook), and a free's line says "A save made before has
their items taken out as it loads." Without the party: "what a save's units
wear of the mods' items can't be looked at as it loads: ... wasn't found."
A game item's look given (1.28.0) is said "has another look in battle" now,
a shield's as a weapon's (Mod Studio's Guard, 5 November). Test 72
(`dev/research/sidequests/make_test72.py`): an Old Ring bought, worn and
saved, its mod's numbers freed and a New Ring numbered, the save loaded.

### A save's place looked at whatever the numbers remember (1.35.1)

Zodi's test 72 (5 November, 12:51): "upon loading into the world map Ramza
is not anywhere to be seen and when I click the center on Ramza button it
takes me to the top left of the world map". His save stood on Hermit's Rest
(place 48, test 71's), and test 72's first free let test 71's numbers go,
its places and their homes among them. Since 1.7.1 a save standing on a
mod's place no mod gives now goes on from its home, else Gariland, but the
save's place was looked at only once some mod's place was ever numbered;
after that free none was, so the world map set itself up at a place the
game has nothing for.

**What this helper does.** The game's load of a save is hooked whenever it
is found (and Reloaded-II's shared hooks are loaded), and every hook looks
at the save's place first (`SaveFallback.MoveOff`: variable 49 among the
variables the load copied, moved where `Fallback` says): his save goes on
from Gariland, said ("the save stood on place 48, which no mod gives now:
Ramza goes on from place 6."), Hermit's Rest's home having gone with the
free. Why the hook isn't made is said only once something was ever
numbered, as before. Test 73 (`dev/research/sidequests/make_test73.py`):
test 72's two mods, file for file, his save loaded again, then test 72's
steps; it passed (5 November: "Test 73 was a complete success and
functioned exactly as you said it would"), his save moved to Gariland as
it loaded, said, and save X losing its Old Ring from the bag and from
Ramza.

### A mod's own job (1.36.0 to 1.41.0)

Zodi's ask of 9 November: "in Mod Studio New Content page the Mod Studio
Framework now allows us to create new quests, locations, and items. The
final touch would be adding new Jobs and Abilities for those jobs." It was
measured first (`claude/jobs-research.md`, `dev/research/sidequests/jobs.py`);
his first step: "One job, start to finish", on the other mod's second page
of the job screen ("Its empty places").

**What a mod gives.** `ModStudioJobs/<job>/job.json`: its name, `Like` (the
game's generic job it looks like, 74 to 93), `Record` (49 numbers, as the
game keeps a job's), `Words` (its name and description; from 1.47.0 its
`Summary` too, below), from 1.37.0 its `Skillset` (below) and, from 1.48.0, its
`Needs` (what opens it, below). **A modder never
chooses a number**: the first of the eleven free ones (142, 143, 146 to 149,
155 to 159), kept in `Numbers.json`'s `Jobs`, the same every time. Up to
1.37.2 one job at a time; from 1.38.0 as many as there are free numbers
(below).

**What this helper does.** Its record goes into the game's job records; its
`Job` row is written as the table loads (the row of the job it looks like,
its own name and description, its skillset's command). Its progress is the
unit's own slot 22 (JP, total JP, level; the JP table of the job it looks
like) and a row of learned abilities of its own (1.36.3: Mime's, which is
never used; the battle reads learned abilities by the skillset, not the job,
so its two readers are told that the job's own skillset, on a unit in that
job, is that row; 1.36.1 and 1.36.2 shared the row of the job whose skillset
it is). Its skillset was one of the game's generic jobs' (5
to 23) until 1.37.0 gave it its own (below). Its sprites, portraits and face are the job it looks like's. With Dark Knight
& Onion Knight (Generic) on, its number is added to that mod's second page
(`JobRoom.OnTheirPage`, reflection, its fields found by name; said when it
can't). A save's unit in one of the eleven no mod gives now is put on a job
of the game's as it loads, said.

**1.36.2, from test 75.** Its place on the job screen stands as the job it
looks like (the screen draws any job that isn't one of the game's generic
ones as the unit already looks: `0x368424`). What's learned is written where
it is read: the code that writes an ability learned (`0x28936C`) and the
game's second list of a job's abilities (`0x392620`) reach its row by the
slot too. The unit's card shows "--" for a level of 0 (`0x29B5CC`), and shows
the menu's copy of a unit's levels (`0x284A08`), made as the menu opens; so
slot 22's level is counted just before that copy, every time.

**1.36.3, from test 76.** A level is counted from level 1's 100 JP on, so a job
below 100 is level 0, the card's "--". The game never lets that be seen: it
gives every job of a unit it makes 100 to 199 JP (`0x2770BC`), so the helper
gives a man's or a woman's slot 22 the same, by that function, the first time
the menu finds it has no level. And the atlas of units (`0x2897B4`, read as
a job is changed) is by the job and the unit's sex: past the game's jobs it
reads whatever is there, which for a woman's place is a size that stops the game
(a man's happened to be harmless), so it reads the job the mod's job looks
like. Everything is in `JobFile.cs`, `JobRoom.cs`
(what is found and written, the native code) and `JobHooks.cs` (armed at the
game's start).

Tests 74 and 75 (`dev/research/sidequests/make_test74.py`, `make_test75.py`;
`Job_Test_75.zip` for 1.36.1, which replaced 74 before it was played), and
test 76 (`make_test76.py`, `Job_Test_76.zip` for 1.36.2): test 75's five
things put right, the job's Move and Jump where the game's records keep them,
and test 77 (`make_test77.py`, `Job_Test_77.zip` for 1.36.3): test 76's four
("Test 77 was a complete success and functioned how you said it would").

**1.37.0: a job's own skillset** (his word on test 77: "Go on and complete
this"). Until here the job had one of the game's skillsets, so a unit in
another job that took it as its second set had what it learned in the game's
job, not the mod's. Now `job.json` (version 2; version 1 isn't read) has a
`Skillset`: `Like` (the game's generic skillset whose icon it has, 5 to 23),
`Actions` (1 to 16 of the game's action abilities, 1 to 421), `Others` (up to
6 reaction, support and movement abilities, 422 to 511) and `Words` (its name
and description). The helper gives it one of the game's 58 free skillset
numbers (77 first; `Numbers.json`'s `Skillsets`; one another mod has filled is
passed over), writes its record where the game keeps skillsets (25 bytes,
`0x67E210`), puts that number in the job's record, and writes its name as
that number's row of `JobCommand` (sheet `0x29`) as the table loads. The
battle's two readers of what a unit has learned (`0x3170CC`, `0x30E368`) take
a skillset that is no generic job's as Squire's row when it is the unit's
job's and as wholly learned otherwise, so both are told that this skillset is
the job's own row, whoever has it. A unit whose second skillset is one of
those numbers with no mod giving it now has it taken off as the save loads,
said. **JP for the other units** (his question, "JP spill over"): the game's
own code gives every other unit a quarter of an action's JP for the acting
unit's job's slot (`0x28338C`), and a mod's job's slot goes through it like
any other; `test_jobs` runs it. Test 78 (`make_test78.py`,
`Job_Test_78.zip`).

**1.37.1: a mod's job in the menu's lists** (his word on test 78: "Battle
Magicks does not appear in the list to choose from"). The game makes its list
of a unit's jobs from its own (`0x2864AC`: the unit's first job, jobs 75 to
93, then 160 and 161), so two lists of the menu never held a mod's job. The
skillsets a unit may take as its second (`0x28A7C0`): the helper adds each
mod's job's pair, the job and its skillset, after the game's, unless the unit
is in that job (site `SecondList`, where the game counts and ends the list).
The reaction, support and movement abilities a unit may set (`0x28A8B0`: the
game's lister `0x28A6E8` called for the unit's first job, then for jobs 75 to
92): the first call is made as it was, then one for each mod's job as the
game makes its others (site `OthersList`). Dark Knight & Onion Knight
(Generic) hooks that lister and widens that loop for its Dark Knight; neither
is touched. **And a wrong done by 1.37.0 put right**: as a save loaded it took
a second skillset off any unit that had one of the game's free skillset
numbers the helper hadn't given, and two of Zodi's units had one from
elsewhere ("2 units had a second skillset no mod gives now"). From 1.37.1 only
a number the helper's own numbers remember giving a job that isn't here now is
taken off (`JobRoom.Gone`); the game itself shows a second skillset it can't
place as none. **1.37.0 is not one to publish.** Test 79 (`make_test79.py`,
`Job_Test_79.zip`): "Test 79 was a complete success and functioned how you
said it would."

**1.37.2: a mod's job in a unit's Combat Sets** (his word after test 79:
"saving my Battlemage to Combat Set 2 saved the job as Knight"). A set keeps
the job's own number (`0x337F50`), but the game shows a set (`0x33751C`) with
the first of the unit's jobs that is "the same job" as the set's, and applies
the job shown (`0x3333F0`). Two jobs are the same to it when their Job rows
name the same JobType (`0xF72F0`), and a mod's job's row is the row of the job
it looks like. From 1.37.2 a mod's job is the same job as itself alone (site
`SameJob`, the test's first instruction), and a set whose job is a mod's job
is marked usable though the game's list of the unit's jobs never holds it
(site `SetJob`, the showing's call for that list). Test 80 (`make_test80.py`,
`Job_Test_80.zip`): "Test 80 was a complete success and functioned as you said
it would."

**1.38.0: a unit's progress in more than one of the mods' jobs** (the first
step of his road of 9 November to 22 or more jobs). A unit's record has room
for one job more than the game's: slot 22's JP, total JP and level and the
learned row 19, eight bytes. So one of the mods' jobs is "loaded" there at a
time, every unit's together, and the others are kept by the framework
(`JobProgress.cs`). Everything the game asks of a mod's job's progress starts
from the job (the slot's function, `0x2B8F18`) or its skillset (the battle's
two readers of a learned row); each of those now asks first whether its job
is the loaded one (a cell beside the stubs) and calls the framework's `Swap`
when it isn't: every unit's eight bytes put away under the job that was
loaded and the asked job's put in their place, in the party's records, the
battle units made from them and the menu's copies together.

- **Which copy is true as a job is put away**: the party's record, unless
  a battle unit made from it (`0x276758`) has changed since it was made or
  last written back (`0x274EB8`); both are hooked to keep what the battle
  unit held then.
- **Who a unit is**: its birthday, its name's number and its sex. The game
  doesn't clear a new unit's record, so a place of the party that holds
  another unit than before starts new in every job.
- **A job's start**: a job brought in for a man or a woman with nothing in
  it comes with 100 to 199 JP at level 1, as the game starts a job of its
  own; the number is worked out from who the unit is and the job's name,
  so it is the same every time and is never kept in a file.
- **Beside the save**: before the game writes a save (`0x218F78`) the jobs
  that aren't loaded are written to `<key>.json` in
  `fftivc.utility.modstudio.eventsetup.JobProgress`, beside the game's saves
  (and in Reloaded-II's settings folder for this mod), and the key and the
  loaded job's number go into eight bytes of the save's variables (0x3B2 to
  0x3B9, the end of the flags' free bytes). As a save loads they are read
  back. A save of before 1.38.0 holds the first number's job. A job whose
  mod is turned off is kept under its name until it is back. A save whose
  file isn't found keeps the loaded job's progress and starts the others
  again, said: "the save's units' progress in the mods' other jobs wasn't
  found (...)".

The files are never tidied yet (one small file for each different state
saved). Test 81 (`make_test81.py`, `Job_Test_81.zip`): test 74's mod with a
second job, Skirmisher. His word: "Most things ran perfectly as you described
I did find these bugs in Test 81": in a battle the cards of both jobs showed
nothing, the Job Progress button on the second page stopped the game, and
from the second battle on the loaded job was lost for the units of the
battle before. **1.38.0 is never to be published.**

**1.38.1: whose a battle unit or a record is, read from what it holds**
(test 82, `make_test82.py`, `Job_Test_82.zip`: test 81's mod as it was).

- **A battle unit** is a unit of the party's while it names that unit's
  place and holds the same sex, birthday and name's number (`Mine`). The
  game clears the battle's units as it sets a battle up (`0x304B48`); 1.38.0
  remembered which had been whose and took the cleared one's nothing for the
  loaded job's progress. Nothing is remembered from battle to battle now:
  whose each is is read again at every ask (`Map`), and a battle unit is
  taken over the party's record only when it was made, written back or
  written by the framework for that unit and has changed since.
- **A record of a unit** is made three ways: the menu's names the party's
  place, the battle's names the battle unit and that unit's party place (the
  menu shows the battle's in a battle), and one on its own names its battle
  unit alone. 1.38.0 read every one the menu's way. `Owner` reads each as
  its maker wrote it; a record that reads both ways is told apart by the
  rest of what it holds (`Same`: the other jobs' JP, total JP and learned
  rows), and is the menu's when that doesn't settle it, since the menu
  writes its own back to the party.
- **A battle started again**: the game takes a copy of the battle
  (`0x2CDBC4`) and puts it back (`0x2CE5C8`, `0x2CE7A8`); the copy's units
  hold the job that was loaded as it was taken. The game's four calls go
  through a stub that makes the call as it came and then tells the
  framework, which notes every job's progress as the copy is taken and puts
  it back with it. Put back with no copy seen taken (a save made in a
  battle holds the same copy), the party's records are what is true.
- **Never less**: what is put away for a job is never less than was brought
  in (less total JP, or something learned that isn't). If it reads so, what
  was brought in is kept and the log says: "a unit's progress in (the job)
  read as less than it had (the unit in place (n) of the party): kept as it
  was."

His word on test 82: "The test was largely a success." Both jobs showed
right in a battle and kept everything from battle to battle. Two faults in
his third battle (below), and the Job Progress button's stop is the other
mod's own (his word: without it the button works with the test's jobs).
**1.38.1 is not one to publish.**

**1.38.2: the party's side and the battle's side kept apart** (test 83,
`make_test83.py`, `Job_Test_83.zip`: test 81's mod as it was). Each
measured in his program first (`dev/research/sidequests/jobs.py`, "The
game's own states, and what it copies before it asks").

- **Two sides, as the game keeps its own jobs.** JP is earned in a battle
  unit alone and reaches the party's record only as the game writes the
  unit back. 1.38.1's swap put what a battle unit had earned into the
  party's record, so a battle the game threw away kept it ("restarting the
  battle from the start her job level is 3 and JP is 343"). Now what is kept
  for the jobs that aren't loaded is kept twice: for the party's record
  (`_kept`) and for each battle unit once it has any of its own (`_there`).
  A swap moves each side on its own; a record gets the side its maker read
  (`Show`); the game's writing back of a unit is where the other jobs'
  battle side becomes the party's (`WrittenBack`, which is given the place
  the game wrote: a guest who joins takes what was kept along now).
- **Before the game copies.** A unit's status is drawn from a record the
  game makes of its battle unit on the stack (`0x2CBCA0`, `0x360048`), or
  from its progress copied there (`0xFCF80`), and only then is the job's
  slot asked: a swap at the asking came too late, and the status showed the
  job with the numbers of the job loaded before ("level went down to 1 and
  JP was 41": her other job's). Two hooks of the game's own load the unit's
  own job first (`Made`, `Shown`).
- **The game's own states.** Both states the game keeps and puts back hold
  the party's records and the save's variables together, so the framework's
  eight bytes in the variables say which job the records hold. The plain
  state is written before every battle and put back as a battle starts
  again from its start (`0x2CF768`, hooked: read as a save loaded). The
  battle's copy (`0x2CDBC4`, also what a save made in a battle is written
  from) is told before it is taken: the mark is written into the variables
  it takes, with a number of the copy's own, and the battle's side is noted.
  As the game puts it back (`0x2CE5C8`, then `0x2CE7A8`) the party's side is
  read by the mark and the battle's side is what was noted for that copy.

His word on test 83: "Bug in test 83. 1st, The skirmisher status card Lv.
Next and JP matches Battlemages instead of Skirmisher." He named nothing
else of test 83's steps. **1.38.2 is not one to publish.**

**1.38.3: the status card** (test 84, `make_test84.py`, `Job_Test_84.zip`:
test 81's mod as it was). Measured in his program first
(`dev/research/sidequests/jobs.py`, "The status card").

- **What his screen is drawn by.** 1.38.2 took the Status screen to be
  made from a record of the battle unit (`0x2CBCA0`). It isn't. The status
  card (the job's name with "Lv.", "Next" and "JP", in a battle and out of
  one, and over the job screen and the abilities) is made by `0x2C1310`
  from a copy of the MENU's record of the unit. The menu's update of the
  card (`0x2BD05C`) copies the record its table names (`0x1800F50`, by the
  word at `0x1811428`) from + 0x70 on into a place of its own (`0x1876C80`)
  and only then calls `0x2C1310`, whose view's maker asks the job's slot;
  `0x2C33D0` does the same with a copy on its stack. A swap at the asking
  wrote the record and the game read its copy: his Jill, a Skirmisher,
  showed "Lv. 1 Next 69 JP 61", her Battlemage's.
- **Before the game copies** (`JobProgress.Seen`). Two more hooks of the
  game's own, at `0x2BD05C` and `0x2C33D0`, told before the game's code
  runs: the record's own job (its word at + 0x24), when it is a mod's, is
  loaded first. A swap writes every record of the menu's, so the copy the
  game then takes is that job's. A record that isn't one of the menu's own
  is left: the game's table names no other.
- **A copy of a battle unit** (`JobProgress.Made`, `TakenOf`). In a battle
  the same update lays the battle unit's numbers over its copy, from a
  record it makes of a copy of the unit (`0x2BD27F`; `0x368424` does it
  too, and the battle keeps one more copy). 1.38.2 wrote the party's side
  to any unit outside the battle's units; a copy of a battle unit gets the
  side of the battle unit it was taken of now (found as the game finds it),
  and only a unit the game has just made from a party's record
  (`0x275B84`, told by `Built`) the party's.

**1.38.4: the battle's side beside the saves** (test 85, `make_test85.py`,
`Job_Test_85.zip`). His word of 10 November: "go on with what is still open
with your recommendation". What the framework notes of the battle's side for
each copy the game takes of a battle was kept in the run's memory alone, so
a battle taken up again after the game was closed had every job but the
loaded one as before the battle. Each copy's side is now also written to a
file of a ring of sixteen (`Battle/00.json` to `15.json` in the framework's
folder beside the game's saves; the oldest is written over, none is ever
deleted), with the copy's whole mark in it. A copy put back that the run
didn't note is looked for there, in each folder, and taken only when the
file holds that copy's mark and, for each battle unit, the unit is still
the one the file names. With nothing to keep no file is made, but one
already at the copy's place in the ring is written over. A run's copies are
counted from a number of the run's own, so two runs' copies don't share a
mark. Where no folder can be written it is said in the log, once.

Not put right yet, each known: the cards where units are placed before a
battle, which the game draws from a copy it makes once for that screen (the
unit's own job is right there, a card of another of the mods' jobs may not
be); two battle units the menu makes for itself; the files named by what
they hold beside the saves are never tidied. **Tests 84 and 85 passed** (10
November: "Test 84 was a complete success and functioned how you said it
would. Test 85 was a complete success and functioned how you said it
would.").

**1.39.0: the job screen's own rows** (test 86, `make_test86.py`,
`Job_Test_86.zip`; `JobScreen.cs`). His choice of 9 November for a game
without Dark Knight & Onion Knight (Generic), "Framework's own page", and
his ask with tests 82 and 83: the jobs "scrolling down row by row". Up to
1.38.4 the mods' jobs had no place on the job screen without that mod.
Measured first (`dev/research/sidequests/job_screen.py`,
`claude/job-screen-research.md`): the screen has 19 places in rows of 6, 7
and 6 and keeps where each row ends; its filling asks the game's lister for
the unit's jobs and gives each to its place by its number in the list; its
cursor steps between the three rows by the row ends alone.

Without that mod, and where the screen is found, the mods' jobs are rows
after the game's three, six a row, and the screen shows three rows at a
time:

- The filling's call of the lister goes to a stand in that makes the same
  call and tells the framework (`Listed`): the list becomes the three rows
  shown (the game's 19, then the mods' jobs, cut to the rows from the one
  scrolled to). The rows shown are 6, 7 and 6 (the game's own, nothing
  moved), 7, 6 and up to 6, or up to 6 each.
- Each place's box is moved to its row and column with the game's own move
  (a row of seven on the wide columns, any other on the narrow ones), a
  place with no job made unseen, and the screen's three row ends written
  (`Arrange`), at each filling and each frame the cursor's step runs.
- The cursor's call of its step between rows asks the framework
  (`Vertical`): inside the three rows it answers as the game does; past the
  last row shown, with a row below, the rows move up by one (the game's own
  filling called again) and the cursor is put in the new last row, in its
  column or on the row's last job; the same going up. At the very last row
  a new press goes round to the very first, and from the first to the last;
  a held press stops there.
- A screen opens on the rows that show the unit's own job, the fewest
  moved, wherever the game puts the cursor on it (its state 2 or less). The
  job tree open, the list is the game's own 19. A unit with fewer than 19
  jobs (a guest, a monster) is left as the game has it.

Its log, in place of the second page's line:

```
[Mod Studio Framework] the job screen lists the mods' jobs on rows of their own after the game's: move down past the last row to see them.
```

Where the screen isn't found the jobs are still added, said: "the mods' jobs
have no place on the job screen: ... wasn't found in ... A game update may
have changed it: look for a newer Mod Studio Framework." A fault in either
of its two entries is said once and the game's own answer given. **With
Dark Knight & Onion Knight (Generic) on, none of it is made**: the jobs are
on that mod's second page, as before.

**Found on the way, a fault since 1.38.0**: the same job test's stand in
(1.37.2) reached its end by short jumps, a pair for each job, so with eight
or more of the mods' jobs the native code couldn't be made and none was
added ("the mods' own jobs weren't added (OverflowException ...)"). Near
jumps now; the code is made and run for all eleven numbers in
`dev/test_jobs.py` (3,862 of its 4,096 bytes of room).

**None of the screen itself could be run here**: test 86 was the first
time it ran.

**1.39.1: the job tree is always there** (test 87, `make_test87.py`,
`Job_Test_87.zip`). His word on test 86 (10 November, his log and a
screenshot of Jill's job screen, a Skirmisher, on the game's three rows): "I
am on the Job page and pressed the down key but it is not bringing to the
new row with Battlemage and Skirmisher." His log was the rehearsal's line
for line. The cause was a misreading: the unit screens' holder keeps the job
tree (Job Progress) at + 0x80, and 1.39.0 took that being set for the tree
being open and showed the game's three rows whenever it was. The holder's
maker (`0x113970`) makes the job screen and the job tree together, so it is
always set: the list was always the game's 19, and a step past the last row
filled the screen again from the same rows. Which of the two is on screen is
the menu's mode (0x581 for Job Progress), not that pointer. The checks ran
over a screen made up without a tree, as believed, and passed.

- Nothing is read of the job tree.
- The filling gives the tree every job by its number in the list, at every
  filling, and the tree shows what it was last given. That call
  (`0x368A5C`) is the framework's now (`TreePlace`, `TreeEntry`, a third
  cell): a job of the game's goes to the place it has in the game's own
  list, whatever rows are shown, and a mod's job to none.
- `Listed` never moves the rows itself. A screen just made or another unit
  starts from the game's own three rows, so the tree is given every job of
  that unit's; where the game is about to put the cursor on the unit's own
  job (the screen's state 2 or less) and that job's row isn't shown, the
  rows to show it are noted (`Pending`).
- The rows move only at the cursor's step (`Vertical`): past the last or
  the first row shown, as in 1.39.0, and to the rows noted, once the boxes
  are at rest (found unmoved for six steps in a row, `Rested`; or 90 steps
  gone by). So a unit in a mod's job opens on the game's three rows with the
  game's own slide of the places, and a moment later the rows move and the
  cursor is on its job.
- While the rows shown are the game's three and the framework has moved no
  box, no box is touched. The boxes' rest places are the layout's own
  numbers until the screen's boxes have been found still and laid out as a
  layout rests them.
- A unit with fewer than 19 jobs: the game's list, and the screen given
  back as the game has it (its row ends, any box moved back where it rests
  and seen).

Three changes more than the jobs' own now (36 become 39); eleven jobs take
3,896 of the native code's 4,096 bytes. One more line its log can have:
"the job screen's own rows couldn't be matched to Job Progress (...); the
game's own places are used."

**1.39.2: the rows' own pattern, and the window's side** (test 88,
`make_test88.py`, `Job_Test_88.zip`). His word on test 87 (10 November,
11:45, ten screenshots): "I can now reach Battlemage and Skirmisher but the
alternating row pattern does not match the black mage row ... also when
selecting a Job the Learn Abilities and and Change Job menu opens from the
left on the last three Jobs of the row on the right hand side. This is
causing the menu for Battlemage and Skirmisher to appear partly offscreen
because for what ever reason its menu is opening to the left."

- **The pattern.** 1.39.0 put a row of seven on the wide columns and any
  other on the narrow ones, so the mods' first row stood straight under the
  game's third. The game sets every other row half a place over. Now a row
  stands on the wide columns or the narrow ones by which row of all it is
  (`Wide`: the second, fourth, sixth), whatever rows are shown. A row of the
  mods' on the wide columns takes the first six of the seven: 19 places
  can't hold seven, six and seven.
- **The window's side.** The game puts the window beside the cursor (a
  job's name, level, JP and its two buttons) to the left of a place when
  "its row's end less the place is 3 or less" (`0x12FF08`, in `0x12FC6C`),
  the row found by the screen's three row ends: the last three places of a
  row. In a row of two both are, and the window opened to the left and off
  the screen. Those six bytes are a call now (a fourth stand in): the row's
  end is read from three numbers of the framework's own in the cells' page
  (`Sides`: where each row would end were it full, seven on the wide
  columns and six on the narrow), by the row's number in `rdx`, and the
  game's own compare, `setle` and `jle` go on from its flags. With the
  game's three rows the numbers are the game's own (6, 13, 19).
  `dev/test_jobs.py` runs that code in the program as it is with his test
  87's rows (7, 13, 15) and gets his screenshots place by place, then in
  the program as changed.
- **The game's count held to.** A unit whose job's `Job` row hides the job
  tree (`0x2CBED4`: the Lucavi's and other enemies' jobs, 60 to 73 and 144
  to 154 in the game's own table) is given a list of one job by the game
  after the framework has listed 19. `Vertical` and `TreePlace` now leave
  such a unit to the game (the count at `0x3C510D8` isn't the
  framework's).

Four changes more than the jobs' own (36 become 40); eleven jobs take 3,913
of the native code's 4,096 bytes.

**1.39.3: the game's slide on the framework's rows, and a unit's own rows
from the first frame** (test 89, `make_test89.py`, `Job_Test_89.zip`). His
word on test 88 (10 November, 12:16, five screenshots): "For step 7a I
noticed Geomancer appearing in the middle row for a few frames before
correctly going to the end of the first row ... That of course messes up
the alternating pattern for a few frames. For 7b one thing I did notice was
that switching between two Skirmishers causes the first three vanilla rows
to flash on screen for a couple of frames."

- **What a box's place is.** Nothing in the screen's own code moves a
  place's box: the layout's timelines do, each key a place of its own
  (`job_screen.unit_moves`: `Show` slides all 19 in over 16 frames as the
  screen opens, `ShowUnit` rests the first at every filling, `HomePosition`
  the rest). A key reaches its box through the animation's applier
  (`0x400840`), which calls the layouts' move of a box (`0x3EF684`: x at
  + 0x38, y at + 0x3C). 1.39.2 wrote a box's place itself, so every frame
  of the slide put it back where the game's rows rest it. With the rows
  moved by one, Geomancer's box (the seventh) rests first in the middle
  row: `dev/test_jobs.py` runs the applier in the program as it is with
  that box where 1.39.2 had it and gets his screenshot.
- **The move's stand in.** The move's first two instructions (five bytes)
  are a jump to native code that, for a box the framework has told it of,
  adds how far that box's row and column stand from the game's to the
  place asked, and runs the game's own code with that (every register but
  `rax` as it was after, as the game's own leaves them); for any other box,
  or told of none, it is the game's own. `Arrange` writes the count (19,
  or 0 while the rows are the game's) and the 19 boxes with their
  distances in the cells' page, and where a distance changes has the
  game's move put that box again. The framework writes no box's place.
- **The boxes end with their screen.** The job screen's deleting function
  (`0x12CFA0`) calls its ending at `0x12CFAF`; that call goes through a
  stand in that makes the count 0 first. `Listed` takes a count of 0 while
  it holds boxes moved for "that screen has ended".
- **Told after the filling** (`After`, `AfterEntry`): each of the game's
  two calls of the filling (`0x36906C`, `0x2BD619`) calls the filling and
  then the framework, which moves to the rows noted at that filling by
  having the game fill again, there and then. 1.39.1's wait for the boxes
  to be still (`Rested`) is gone.

Eight changes more than the jobs' own (36 become 44); eleven jobs take 4,029
of the native code's 4,096 bytes. One more line its log can have: "the job
screen's own rows couldn't be moved to a unit's own job (...); the rows
stay as they are."

**1.39.4: rows of seven and six, Q and E through every job, each row
sliding as one** (test 90, `make_test90.py`, `Job_Test_90.zip`). His word
on test 89 (10 November, 15:17, his log and four screenshots): "Much
better", and: Geomancer "sliding in Right to Left" where its row slides
left to right; "Shade was not next to Mender. It should be because the
alternating rows goes from seven units on a row to six units on a row";
and on the Learn Abilities page Q and E went through "the jobs that were
last displayed on your Jobs menu" only, from Dragoon to "Mender", and from
Timekeeper "the game crashes".

- **Q and E.** Going to the abilities' or the summary's page (in
  `0x12FC6C`) the game hands a piece of the screen (+ 0x1988: the panel
  with the job's name and the two arrows) every one of the 19 places whose
  record is open (+ 0x84 of its 0x94 bytes from + 0x2280: 0 open, 1
  locked, 2 not to be seen), whatever is listed; the piece's step
  (`0x2A7D9C`, called at `0x1313A1` in the screen's step for those pages,
  `0x1312C8`) goes through them and round, and the place it answers is made
  the cursor's. The filling writes the records of the places it lists and
  no others, so with 14 jobs listed places 14 to 18 held what the rows
  shown before had left (Mender in the nineteenth) and the list's word for
  place 14 was the end the framework writes after the last job. Now
  `Arrange` closes the record of every place with no job; and the call at
  `0x1313A1` is the framework's (`Cycle`): the game's own step, and where
  it went round the rows shown, the next open job of everything listed is
  gone to (past the very last, the very first), the rows moved to show it
  by the game's filling with the cursor's place set first, the piece's
  places made again from the rows then shown.
- **Seven and six.** A row of the mods' on the wide columns holds seven
  (`RowSizes`). Three rows are shown only where they fit the 19 places
  (`Fits`, `Scrolls`): seven, six and seven are 20, so the cursor still
  goes one row at a step and the rows shown move as little as shows its
  row, by two there (`Step`, `Showing`); where the last three rows don't
  fit, the last two are shown.
- **Each row slides as one.** The game slides its first and third rows in
  from 300 to the left and its middle row from 200 to the right, box by
  box. A box of the game's middle row that stands in the first row shown
  (the seventh, where that row is one of seven) is told to come from the
  other side: the move's stand in (24 bytes a box now: the box, the two
  distances, where the game rests it across, whether it is turned) puts it
  as far to the left of its place as it is asked to the right of its rest,
  half as far again.
- Where a screen's end was never told, the first box, which the game's
  readying has put through what the last screen told, is put again.

Nine changes more than the jobs' own (36 become 45); eleven jobs take 4,068
of the native code's 4,096 bytes. One more line its log can have: "the job
screen's own rows couldn't go from one job to the next (...); the job stays
as it is."

Not built or not known, each said to him: the mouse's wheel (where the game
keeps it wasn't found); each move of the rows fills the screen again; the
rows move by two where seven, six and seven would be shown; a held Q or E
stops at the last job of the rows shown; Job Summary shows the overview of
the job a mod's job looks like; which rows the job screen shows on coming
back from Job Progress.

**1.39.5: the rows move the same way for any number of jobs, and no box is
moved** (test 91, `make_test91.py`, `Job_Test_91.zip`). His word on test 90
(10 November, 16:55): "The test was a complete success and functioned as
you said it would", and of the rows moving by two: "make it consistent on
how many rows move no matter how many jobs are added ... I'd perfer 1 but
if it has to be two it is ok as long as it it consistent from here on out."

- One can't be kept: three rows from a row of seven are seven, six and
  seven, 20, and the screen has 19 places. `JobScreen.Scrolls` is every
  second row that has a row after it, so the three rows shown are always
  six, seven and six places and stand where the game's own three stand.
  The cursor still goes one row of all the rows at a step (`Step`,
  `Showing`); the rows shown move by two when it leaves them.
- So nothing of a box's place is read or written. Out: `MoveBox`, the
  distances, the turned box (`Across`, `Asked`), `LayoutRest`, `Layout`,
  the 19 boxes told, the site "Move" and its stand in. **The layouts' move
  of a box (`0x3EF684`) is the game's own again.** `Arrange` writes the
  three row ends, the three numbers of the window's side, the records of
  places with no job (closed) and each box's opacity.
- The job screen's end is still told (site "Ended"): its stand in makes
  `ScreenAliveCell` 0, `Arrange` makes it 1 and notes the screen. `Listed`
  reads an end as "the screen noted is gone", and the next filling on a
  screen made where it was starts from the game's three rows, so the job
  tree is given every job. (Before, an end was only seen where a box had
  been moved, which with eight jobs was never.)
- Eight screen changes (44 with the jobs' own). The native code for eight
  jobs is 3,122 bytes with the screen's.

**1.40.0: more than eleven jobs** (test 92, `make_test92.py`,
`Job_Test_92.zip`; the road's step 3). His word on test 91 (10 November,
17:47): "a complete success and functioned perfectly as you said it
would."

The game keeps 174 job records of 0x31 bytes (`0x785E30`), the abilities'
table right after them, and eleven numbers are free. `JobRecords.cs`:

- Measured first (`dev/research/sidequests/jobs.py`): 40 instructions in
  30 functions name the records (`RECORD_SITES`: 35 by a distance from
  the instruction's end, 5 from the image's base) and 15 bound a job's
  number by 174 (`RECORD_BOUNDS`). `JobRecordSites.cs` holds a pattern for
  each, written by `dev/research/sidequests/make_record_sites.py` (whole
  instructions, every distance to elsewhere left open, found once; it
  needs capstone and is run only when the lists change).
- `Find`: each found once, a reader held to what its distance names.
  `Changes`: each reader's distance to the same place in a table at an
  address, each bound's number 255. `Fill`: the game's 174 records, then
  the empty record to 255. `Sync`: each record of the game's own table
  that differs from a copy of it as last seen brought over, and kept.
- `JobHooks.Arm` makes the table after the code's room (`JobRoom.
  CellsAfter`, 0x8000 now) and the cells, **only when a job has a number
  past 173**, fills it, writes every job's record into it (and a job of
  the game's own numbers into the game's table too, as before), then
  changes the code. `BringOver` runs `Sync` at the tables' load, a
  save's load, a battle's build and the job screen's filling.
- `Mod.cs` looks for the places only without Dark Knight & Onion Knight
  (Generic) and with the job screen found, before `JobRoom.Plan`, which
  gives from `JobRecords.Numbers` (the eleven, then 174 to 254) or from
  the eleven. A job whose kept number can't be used now is left out and
  keeps it.
- The Job table's rows past 173 go on without a gap (`JobRoom.BlankRow`).
  A unit in a number past 173 no mod gives now goes on a job of the
  game's as a save loads (`JobRecords.Given`).

A save with a unit in a job past 173 needs the framework: the log says so
where the table is made.

**1.40.1: the Job Abilities window's bound** (test 93, `make_test93.py`,
`Job_Test_93.zip`). His word on test 92: "a complete success", and for the
five jobs past 173, "Pressing T to bring up the Job Abilities menu on the
Jobs menu shows their Job Command is blank" until the unit wore the job.

- The window's maker (`0x2BA1FC`) takes the command from the unit where
  the job is its own, else from the first byte of the job's record, and
  bounds the job by 174 first: a 174 made in a register (`mov ebx, 0x40`,
  then `lea eax, [rbx + 0x6E]`, then `cmp si, ax; jae`), which the search
  for 174 as a number couldn't find.
- `jobs.py`'s `RECORD_COMPUTED`; `JobRecordSites.cs` has `Computed` (the
  span from the `mov` to past the `jae` as one pattern);
  `JobRecords.Find` finds it once and `Changes` makes the `lea`
  `imul eax, ebx, 4` (256, in the same three bytes). 56 changes for the
  longer table.
- Found by `dev/research/sidequests/compares.py`: every compare of the
  program with 173 or 174 on one side however the number is made (35; this
  one, the 15 known and their loops, and 19 not about jobs).

**1.41.0: new abilities** (test 94, `make_test94.py`, `Job_Test_94.zip`).
Zodi's answer on the road's step 4 was "Straight to more": a mod's own
action abilities on numbers past the game's own (549 to 1023), with no test
until the whole rehearsed. It was built beside the helper (`helper/Abilities`,
into the checks program only) and moved in whole for test 94.

- **A mod's ability** is a folder of its own,
  `ModStudioAbilities/<ability>/ability.json` (`AbilityFile.cs`): its Name
  (what its mod's jobs call it), the game's action ability it is Like (1 to
  367: how it looks when used, its effect, how its user moves, its sound),
  its Record (8 bytes: its cost to learn in the first two, its chance to be
  learned, its kind's flags, four of flags for the units the game moves),
  its Action (14 bytes: Range, EffectArea, Vertical, four of Flags,
  Element, Formula, X, Y, InflictStatus, CT, MPCost) and its Words (a name
  of up to 40 characters, a description of up to 300 with up to two line
  breaks). What can't be used is left out and said. Only action
  abilities: what a reaction, support or movement ability does is the
  game's code.
- **A job names it** in its skillset's Actions by its Name, beside the
  game's numbers (`JobFile.cs`: `[16, 1, "Flame Lance"]`). A name is the
  job's own mod's ability; one its mod has no ability of that a number
  can be given is said and its place left empty.
- **Its number**: the framework gives each ability one from 549 to 1023
  and keeps it in `Numbers.json`'s `Abilities` (by `{mod id}/{name}`), as
  it keeps a job's. The log: "{mod}'s {ability} is ability {n}, looking
  like the game's ability {like}." An ability no job's skillset names:
  "... is in none of its mod's jobs' skillsets, so no unit can learn it."
- **Where a skillset names one** (`AbilityPlan.cs`): the skillset's record
  (which holds an ability in nine bits) gets the game's ability it is
  like at that place, and the framework's own list of places (a word for
  each place of each of 256 skillsets) the mod's own number, which the
  game's reader answers with first.
- **What is made in the game** (`AbilityHooks.cs`), only where every place
  is found, else "the mods' abilities can't be added: {what} wasn't found
  in {program}. A game update may have changed it: look for a newer Mod
  Studio Framework." and the places that name them left empty. Made
  before the jobs are (whose skillsets' records are written as they are
  made). A room of the framework's own near the program (`AbilityRoom.cs`,
  0xB400 bytes): its code, the lists, and three longer tables.
  - The game reads an ability through a few central routines: the
    reader of a skillset's place, the getter of an action's record and
    the chooser of an effect are each taken at their first instructions
    and answer for a mod's ability (the effect: its Like's).
  - Nineteen compares that would take a mod's ability for something
    other than a plain action (and two that bound the name of the ability
    in use) are taken by one shape of code; nine places that cut an
    ability's number to nine bits keep a mod's whole.
  - The abilities' records (8 bytes), effects (a word) and how their users
    move (3 bytes) are each read by the number with no bound, so each
    table is moved to a longer one of 1,024 (`AbilityRecords.cs`,
    `AbilityEffects.cs`, `AbilityAnimations.cs`): every instruction that
    names it given the same place there (21, 4 and 8), each found once by
    its bytes (`AbilityRecordSites.cs`, written by
    `dev/research/sidequests/make_ability_sites.py`). What others write to
    the game's own three since (the mod loader writes a mod's ability data
    there) is brought over at the tables' setup, a battle unit's making
    and a save's load.
  - **Its name, description and cost to learn** (`AbilityWords.cs`): a row
    of the game's Ability table (sheet 0x27) for each: the row of its Like
    with its own name, description (a line break written `<br>`) and cost
    (the game's code reads the cost there). The log: "Ability: the mods'
    abilities' {n} rows written." The older text's names' file
    (`9999_sys_abilityn.mes`, which a text routine walks with no bound) is
    made longer where the game loads it, an entry for every index to
    2047; a mod's ability's there is the name of the ability it is like
    (the file's letters aren't known, so its own name can't go there:
    where that text shows, if anywhere, test 94 asks).
  - **The turn order** keeps the ability a unit readies as its low byte
    and a flag past 255, and two routines that show the turn order make
    the number again from that: both taken, so a mod's ability readied
    is named as itself.
- Rehearsed in the program's own code by `dev/test_jobs.py`, the whole of
  test 94's package among it (the game's lister and info run with the
  room as the helper starts it).
- Whether a unit the game moves picks a mod's ability is that unit's own
  judgment of its data (its record's choosing bytes are read whole); no
  test shows it until a mod's job stands among a battle's enemies.
- The measure and what is still open: `claude/abilities-research.md`.

**1.41.1: the abilities screens' tabs** (test 95, `make_test95.py`,
`Job_Test_95.zip`). His word on test 94: "Focus is the last action ability
in the list, Flame Lance, Mending Light and Swift Step do not appear" (Learn
Abilities, and Job Abilities on T; his log as rehearsed).

- Every place that lists a skillset's abilities by tab asks the lister for
  all of them and keeps only the tab's range: actions 1 to 421, reactions
  422 to 453, supports 454 to 485, movements 486 to 509. A mod's ability
  (549 to 1023) was in none, so the action tab dropped it too.
- Three loops of one shape (`abilities.py`'s `FILTER_SITES`;
  `AbilityRoom.Filters`, written by `make_ability_sites.py`): each one's
  two compares and their jumps become a jump to the framework's code, which
  compares a number from 549 to 1023 as 1 (inside the action tab's range,
  below every other tab's) and any other as it is, then goes back to the
  game's store of 0 or its step to the next word. The word stays as it is.
- The measure had found these and judged them right for a new action
  ability, as halves of a range of another kind; they are the action tab's
  own. Every other range check was read again: each is another kind's.

**2.0.4: the 16 summons' own sheets, bigger and in more colors** (test 130, `make_test130.py`,
`Lich_Test_130.zip`; nothing of it has run in the game). His Lich test of 17 November (his picture of Lich didn't
show) was traced in the thirty third session: in the enhanced look the game draws each of the 16 summons from a sheet
of its own in g2d.dat (entry 1426 plus two times the effect's number), not from its effect file. **Measured in his
program first** (`claude/texture-resolution-research-continued.md`, "The summons' remastered sheets, measured";
`dev/research/sidequests/summon_sheets.py`): battle slots 15 to 17 make a rectangle of the sheet at twice the draw's
texture coordinates, each pixel through 256 colors read at the draw's color table word, in the routine the slots'
part already hooks for the units' sprites. **What 2.0.4 changes** (`BigTextures.cs`): a sheet named by an entry from
1426 to 2449 is read at 8 bits a pixel (`BitsOf`; "MSBT" files of 8 bits, and sheets of more colors whose numbers have
8 bits); a slot is drawn from a bigger sheet only at the bits the game draws it at (a summon's at 8, through the
slot's 256 colors; a sprite's at 4); the menus' figure and a whole entry take only sheets of 4 bits; its line says
"summons' sheets" ("N picture(s) of summons' sheets is/are shown where the game draws..."), a summon's sheet is named
"...bigger picture of effect N's own sheet (the game's texture E)", and a sheet of the wrong bits "...has 4 bits a
pixel, and a summon's sheet has 8". Mod Studio writes the sheet at the game's size as the mod loader's `tex_N.bin`
(no framework needed) and, twice the size or in more colors, `ModStudioTextures/summon_N.bin` for the framework.
Checked here: the framework's own reader takes test 130's mods with nothing to say and draws Lich's sheet over a
stand-in for the game's routines (`dev/test_big_textures.py`; `Checks --textures`' `summonScenes`). **The stand-in is
not the game.**

**2.0.3: War of the Lions' 40 items' looks in battle matched to his icons** (test 129, `make_test129.py`,
`Looks_Test_129.zip`). Zodi's ask of 17 November: "the Battle Sprite Attack/Guard and Held or thrown option for the
WotL items is a bit off can you match them closer to the looks of their Sprite texture", and his new Sprite Textures
of that evening (PNG, a soft dark edge). Each of the 40 was drawn every way the game draws it from his game's three
files and held to his icon (`dev/research/sidequests/wotl_looks.py`; `claude/wotl-items-research.md`, "The 40's
looks in battle, matched to his icons"): held or thrown, War of the Lions' own icon in its own palette where the game
has it, the nearest of the game's 16 palettes where it asks for one past them; attack or guard, the swing of the
game's weapons drawn on the same icon, in the swing palette nearest his icon's colors; a fell sword (type 0x23) swings
as a sword, the frames the game's own routine gives it. **What 2.0.3 changes**: `WotLItems.cs`'s facts (each item's
record and pair, made again by `wotl_items.py --csharp`), its line ("...each with its own icon and a look in battle
matched to its icon; N as the mods changed them."), and the 40 small icons from his new Sprite Textures. Nothing else
of the framework changed. Checked here: the framework's own reader takes test 129's mod with nothing to say and gives
the 40 with the chosen looks (`dev/test_wotl_items.py`). Test 128 (2.0.2) and test 129 (2.0.3) passed in his game.

**2.0.2: a picture of more colors through the game's tints** (test 128, `make_test128.py`, `Job_Test_128.zip`: test
127 again with this helper). Zodi's answer after test 127 (17 November, 14:59): "The full colors should stay through the
highlight with what ever appropriate tints applied to them"; and to the question whether a status's tints keep them
too (recommended yes), "I go with your recommendation": one rule for both. **Measured in his program first**
(`claude/texture-resolution-research.md`, "Measured in the thirty second session"; `dev/research/sidequests/tints.py`
holds every instruction it names): the battle changes a unit's palette before its colors are made, by halving, making
grey (the parts weighed 2, 3 and 1, over 6 or 12) or neither, then adding an offset to each part kept to 0 and 31
(`0x2F7628`; a status's at `0x269330`, the menus' at `0xCE5D9`), and by blending toward a color or back from it in 8
or 32 steps (`0x2F4944`, `0x2F5F78`, their two tables of steps in the program byte for byte as the PlayStation's rule
makes them): the selection highlight and the teams' pulses (blue 24 for the player's units, red 16 for an enemy, red
16 with green 8), the statuses (Petrify grey, Blood Suck grey with a color, Berserk red, Poison halved with green,
Regen blue, Oil and others halved and darkened, Undead halved with a color), and the shading of the tile a unit stands
on with rain and night (`0x269074`). Black is left alone and a color made black that wasn't keeps blue 1, as the game
does. **What 2.0.2 does**: where the palette in hand isn't the one a picture was given in, `OwnColors.Tint.Find` looks
for the tint that gives every drawn color of the palette in hand from the given one exactly (a change alone, a blend
alone, then a blend on a change; each part's offsets narrowed to what fits, the game's known offsets tried first; the
whole tint checked under the game's rule), cached by palette (512 kept); `Tint.Apply` puts each own color through it,
its five bits exactly as the palette's colors go and its finer three along the slope, so the game's palette points
come out exact and a picture under no tint is as it was. A palette no tint gives (a team's other palette) draws the
nearest colors as before. The effects are unchanged. The log says once: "the game tinted a picture of more colors for
the first time, and its own colors were kept through the tint (<who>: <the tint>)". **Checked here** (not in the
game): every one of the game's tints over 60 random palettes run in a machine over the program's own code (586) found
and drawn exactly at the palette's points (27,000), the C# and the Python searches finding the same tints over 290
palettes and drawing the same, a palette no tint gives refused, a game tint found in 0.07 ms at the median and about 11
at the most (`dev/test_own_colors.py`, its section on the game's tints). **Test 128**: test 127's package made again
with this helper, its notes saying what to look at (the highlight toward blue or red, the statuses by what they do,
shaded tiles, rain and night, a team's other palette in its nearest colors) and the log's lines.

**2.0.1: the jobs find the game's save routine past the items' hook** (test 127, `make_test127.py`,
`Job_Test_127.zip`: test 126 again with this helper). Zodi's report on test 126 (17 November, 13:29, his log and five
screenshots): at step 4 no job of the mods (no Battlemage on the job screen, no Frost Mage) and the Squire man in his
own look; before it, Gariland's Outfitter selling the three items as the notes said, the Knight woman's stripes, and
the log's lines of the items, the battles and the pictures as the notes quote them. The log: "the mods' 21 jobs can't
be added: SaveWrite (0 places like it, not 1) wasn't found". `Mod.Initialized` plans the items before the jobs, and
the items hook the game's save routine (0x218F78: `ItemRoom`'s Save, found from its fifteenth byte), a jump written
over its first 14 bytes before the jobs looked for the same routine (`JobRoom`'s SaveWrite) from its first byte.
2.0.1 finds SaveWrite from the fifteenth byte too (its lead -14); nothing else of this helper changed. Checked here:
the checks program runs `JobRoom.Find` again over his program with each of the 14 functions the items hook given a
jump of 14 bytes (`Checks --jobs`: `withItemsHooked`), every place found and none moved; and every pattern of this
helper's parts held against every other in Mod.cs's order (`dev/research/sidequests/pattern_overlaps.py`,
`dev/test_event_setup.py`): the save routine was the only pattern one part's hook hid from a part after it, and the
other nine pairs are each safe (HANDOFF). The Squire man's fault was Mod Studio's: its list of the units' sprites gave
him sheets 924 and 925, another sprite's copy of his picture, where the game draws him from 992 and 993 (its own
table); put right there, nothing of this helper.

**Test 127** (`dev/research/sidequests/make_test127.py`, `Job_Test_127.zip`; `dev/test_qt_job_tabs.py`'s section "Test
127's package"): test 126 again (made again from his four zips over test 125's package) with this helper, the Squire
man's picture at 992 and 993, its quest renamed Test 127 Quest so it plays again (the ring keeps its name: an item's
key is its mod and name, and his file has it at 316 since test 126). Its notes say what was wrong and ask for steps 4,
6, 7 and 8 again at least. Checked here as test 126 was, and the jobs found with the items' hooks in place. **His
report (17 November, 14:39)**: steps 4 to 7 as the notes say, and every line of this helper as they quote them: the 21
jobs given (Battlemage 142, Frost Mage 147) beside the items, the battles and the bigger pictures; "the game was given
a bigger picture of more colors for the first time (Test 74 New Job's bigger picture of the game's texture 992 in more
colors, 1024 by 1024 pixels where the game's are 512 by 512)."; the quest's, the arena's and battle 167's lines. The
selected Squire man's colors are the sheet's while the game's selection highlight fades in and out (a flash: the
palette in hand isn't the one given), as designed; his answer (14:59): "The full colors should stay through the
highlight with what ever appropriate tints applied to them", the next session's work, measured first. Steps 8 to 10
"were a success"; the log of the run his effects' screenshots came from wasn't sent.

**2.0.0: War of the Lions' items, a mod's units of any battle, items past 255 on units and tiles, a sprite's sheet
and an effect's picture at a bigger size and in more colors** (test 126, `make_test126.py`, `Job_Test_126.zip`: test
125's two mods, 1.24.0 and 1.17.0, the first opened in Mod Studio, given all of it on Mod Studio's pages and written by
its Export; and this helper). Zodi's four points of 16 November, 01:58, after test 125 passed; his word then: "Feel free
to run the tests and suite checks for these three points until after everything is completed"; his fourth point: the
version is 2.0.0 "when the three points are complete". The thirty first session (17 November) made the bump with test
126, the one test for everything (below: "Test 126"). **Nothing of it has run in the game yet**: test 126 is its first
test there.

**Mod Studio's side, since the twenty fourth session (16 November)**: its pages write both files (`ModStudioBattles.json`
from the Encounters and Treasure Hunter pages, a quest's battle's `Items` from the New Content page,
`ModStudioWotLItems.json` whenever a mod names or changes one of the 40), and `dev/test_mod_battles.py` runs this
helper's own reader (`Checks --battles`) over what Mod Studio writes and holds each fault's words to Mod Studio's. No
file of the helper was changed for it. **Since the twenty fifth session (16 November)** Mod Studio's Items page lists
the 40 and edits one (the New Content page's item sheet, shown inside the Items page), a changed one written into
`ModStudioWotLItems.json`, a picture of the mod's own for it as an item icon's four files named of the mod and the
item; `dev/test_mod_battles.py` runs this helper's reader (`Checks --items`) over that too. No file of the helper was
changed for it either. **Since the twenty sixth session (16 and 17 November)** the units' sprites of his second
point are built (below: "A sprite's sheet at a bigger size"), with Mod Studio's Textures page writing what this helper
reads. **Since the twenty ninth session (17 November)** an effect's picture at a bigger size too (below: "An
effect's picture at a bigger size"), and War of the Lions' 40 items' small icons are his icons of 32 by 32
(below). **Since the thirtieth session (17 November)** pictures of more colors than a sheet's, tied to one palette
(below: "A picture of more colors"). **The thirty first session (17 November)**: the bump to 2.0.0 and test 126
(below: "Test 126").

**A sprite's sheet at a bigger size** (`BigTextures.cs`, `BigTextureHooks.cs`; measured in
`dev/research/sidequests/big_textures.py`, `claude/texture-resolution-research.md`; his second point: "replace the ...
files with those of higher resolution ... In game the texture upscaled will be the same size on the screen as before but
higher resolution. New Jobs sprites should be able to have this as well").

- **Asked for by a mod**: `ModStudioTextures.json` at a mod's root, `{"Sprites": [...]}` (and since the twenty ninth
  session `"Effects"`: below), each `{"Entry": <an entry of
  g2d.dat, 0 to 16383>, "File": "<a file inside the mod's folder>"}` or `{"Job": "<the Name of a job of the mod's own>",
  "Who": "Man" or "Woman", "Half": "Upper" or "Lower", "File": ...}` (a job the game was given textures for:
  `SpriteTextures.cs`). The file is a sheet as Mod Studio writes one: "MSBT", its version (1), its bits a pixel (4), its
  scale (2 to 8, two bytes), its width (512 times the scale) and its height in pixels (four bytes each, whole rows of
  the game's, 512 at most), then its rows, the left pixel in a byte's low four bits. The mods are read in Reloaded-II's
  order; a later mod's sheet for an entry is shown in an earlier one's place, said. Each fault is said and that sheet
  left out.
- **What the game does** (his program, as data): nothing draws from a sheet. The game makes 32 bit pixels on the CPU
  from an entry unpacked by `0x3D25D8` and a palette of 32 bit colors made by `0x41DC34`, in three places (the battle's
  slots, `0x3D0F8C`: a rectangle of the sheet; a whole entry in the battle, `0x415D30`; the menus' figures, `0xCE204`),
  and hands them to the card through `0x3D0B10`. No draw asks the card's texture for its size: each divides by numbers
  of the game's own.
- **What the framework does**: four hooks, each calling the game's own routine (the unpacking of an entry, the making
  of a palette, the battle's making of a slot's texture, the making of a texture on the card). Where the texture now
  made stands for an entry with a bigger sheet, the same rectangle is made from the bigger sheet **through the game's
  own palette of that moment**, the game's routine makes the texture from those pixels at their size, and the object's
  width, height and two floats are put back to the game's. A slot's variant that has a texture is freed first by the
  game's own routine (`0x3D11DC`), so the game makes it anew; a texture that is bigger and is next given pixels of the
  game's size, or the other way, is freed (`0x3D0C6C`) and made anew. Pixels the game owns are left to the game. A
  place not found (a game update) leaves every sprite at the game's size, said. With no bigger sheet in any mod none
  of it is made.
- **Its lines**: "N bigger pictures of sprites are shown where the game draws their textures, at the same size on the
  screen."; once, "the game was given a bigger picture for the first time (<whose>, <its size> where the game's are
  <the game's>)."; "the sprites' bigger pictures can't be shown: <why>. Each sprite is drawn at the game's size."
- **Checked here**: `dev/test_big_textures.py` (the measure held to his program; this reader over what Mod Studio
  writes; the hooks' part over a stand-in for the game's routines, written from their instructions: the stand-in is not
  the game). **Not run in the game.** Not built: pictures of more than a sheet's 16 colors (the effects' pictures:
  below; the twenty seventh session's word that they reach the card as rectangles of a shared texture was
  corrected by the twenty ninth's measure).

**An effect's picture at a bigger size** (`EffectTextures.cs`, `EffectTextureHooks.cs`; measured in
`dev/research/sidequests/effect_textures.py`, `claude/texture-resolution-research.md`, "Measured in the twenty ninth
session"; his second point, "replace the effect sprites ... files with those of higher resolution", and his answer of
17 November: "Yes, up to 4 times (Recommended)").

- **Asked for by a mod**: the same `ModStudioTextures.json`, its list `"Effects"`, each `{"Effect": <the effect's
  number, 0 to 511>, "File": "<the bigger sheet, a file inside the mod's folder>", "Picture": "<the mod's own file of
  the effect, at the game's size>"}`. The sheet is "MSBT", its version (1), its bits a pixel (4 or 8: the bits the
  effect's frames draw it at that the picture was given in), its scale (2 to 4), its width and height (the effect's
  sheet at that scale), then its rows, at 4 bits the left pixel in a byte's low four bits; its color numbers are the
  sheet's. A later mod's picture of an effect is tried before an earlier one's, said. Each fault is said and that
  picture left out.
- **What the game does** (his program, as data): an effect's picture is put in the emulated video memory at x 384, y 0
  (`0x2741E0`); a draw takes a page of that memory, and a page with a palette is a record (`0x3C7C960`, made by
  `0x418A48`) whose texture `0x41E05C` makes. Only pages 12 to 15 are ever given a cell of the game's one shared
  texture there; every other record, an effect's pages 6 and 7 always, is a texture of its own, its pixels made on the
  CPU (`0x418F20`) and sent again (`0x3D0BF8`) or noted and made (`0x3D0A80`, `0x3D0B10`) at the record's size. The
  draw divides by the record's own width and height, and the game itself makes seven of its pages' textures 512 by 512
  for records of 256 by 256: a bigger texture under the same record covers the same place.
- **What the framework does**: one hook, on `0x41E05C`, calling the game's own routine for every record but one whose
  page (its plain copy, at the bits the picture was given at) holds part of a mod's effect picture, its bytes there
  the mod's picture at the game's size; for that one the game's own routine makes the page's pixels, the framework
  makes them 2 to 4 times bigger (the picture's part from the bigger sheet's color numbers through the record's own
  palette, so every palette and every change of color the game makes is kept; the rest of the page the game's pixels
  repeated) and hands them to the game's own routines as the game does at that place. The texture costs a page's
  memory (4 MB at 4 times) only while the effect plays. With no bigger picture in any mod the hook isn't made; a place
  not found (a game update) leaves every effect at the game's size, said.
- **Its lines**: "N bigger pictures of effects are shown where the game makes their textures, at the same size on the
  screen."; once, "the game was given a bigger picture of an effect for the first time (<whose>, <size> by <size>
  pixels for a page of the game's 256 by 256)."; "the effects' bigger pictures can't be shown: <why>. Each effect is
  drawn at the game's size."
- **Checked here**: `dev/test_big_textures.py` (the measure held to his program and `0x41E05C` run in a machine; this
  reader over what Mod Studio writes; the hook's part over a stand-in for the game's routines, written from their
  instructions: the stand-in is not the game). **Not run in the game.** Not built: a picture drawn bigger at the bits
  it wasn't given in, a page drawn through a texture window bigger (pictures of more colors: below).

**A picture of more colors** (`OwnColors.cs`, with `BigTextures.cs` and `EffectTextures.cs`; measured in
`dev/research/sidequests/deep_colors.py`, `claude/texture-resolution-research.md`, "Measured in the thirtieth session";
his second point, "higher resolution and deeper color depths. For instance using PPSSPP texture packs", and his
answers of 17 November: tied to one palette, PPSSPP's way; "Up to 4 times (Recommended)"; "Keep its colors
(Recommended)").

- **Asked for by a mod**: the same `ModStudioTextures.json` and the same entries (a unit sprite's by Entry, a job's
  figure by Job, Who and Half, an effect's by Effect, File and Picture), the sheet's file at its version 2: "MSBT", 2,
  32 (bits a pixel), its scale (1 to 4, two bytes), its width and height (four bytes each: a sprite's 512 times the
  scale and whole rows of the game's; an effect's its sheet's at those bits and that scale); then its color numbers'
  bits (4, or an effect's 4 or 8), 0, how many colors the palette it was given in has (two bytes: 16 or 256) and their
  15 bit words; then its rows compressed (zlib), four bytes a pixel: its own red, green and blue (red first) and its
  color number. Each fault is said and that sheet left out.
- **What the game does** (his program, as data): where the framework makes a sprite's pixels the palette in hand is
  16 colors made by `0x41DC34` (each part's five bits shifted up three) from the emulated video memory's color table in
  the battle and from the sprite's own colors in the menus, each changed first by the unit's status there; where it
  makes an effect's page's pixels, the record's 16 or 256 colors made by `0x25EB10` through a table of its own (each
  part over 31 times 255, cut). A team's colors are another palette; a status's, a flash and an effect's colors as they
  change are colors changed before they are made. Under both rules each color's five bits a part come back as its 32
  bit part shifted down three, and a color made never drawn is 0.
- **What the framework does**: no hook more. Where the game makes a texture from such a sheet (a battle's slot, the
  menus' figure, a whole entry, an effect's page), it is made as a bigger sheet is, but where the palette in hand is
  the one it was given in (every color the same five bits a part, or 0) each pixel is its own color, kept see through
  or blended as the game made its number's color; in any other palette its numbers go through the palette in hand.
  Memory: 4 bytes a pixel, held while the mod is enabled (a unit sprite 2 MB at the game's size, 32 MB at 4 times).
- **Its lines**: the sprites' and the effects' lines say how many of their pictures are of more colors ("N pictures of
  sprites are shown where the game draws their textures, at the same size on the screen, M of them of more colors
  where the game draws them in the palette each was given in."); once, "the game was given a picture of more colors
  for the first time (...)" ("a bigger picture of more colors" where it is bigger too; "of an effect" for an effect's).
- **Checked here**: `dev/test_own_colors.py` (the measure held to his program and both rules run in a machine; this
  reader over what Mod Studio writes; the hooks' part over a stand-in for the game's routines, written from their
  instructions: the stand-in is not the game). **Not run in the game.**

His first point: "Like we made Dark Knight and Onion Onion In Mod Studio Framework we should do the same for WotLs items
from WotL Restoration to be able to be used by the framework so they can be edited on the Items page and can be used in
Encounters page and modders new Battles and for Treasure Hunter." His third: "The ENTD only supports a limited amount of
override slots, can we overcome this and allow users to override every single 16 unit slot for every battle."

- **War of the Lions' 40 items** (`WotLItems.cs`, `ItemHooks.cs`, `ItemRoom.cs`; measured in
  `dev/research/sidequests/wotl_items.py`). Nothing of them is in the game: his program holds item records for 0 to 255
  and its own five (256 to 260: its boundaries at `0x6804E2` end at 261) and its Item table stops at 260; only its code
  still knows five of the numbers (Onion Knight's own equipment) and the fell swords' item type. So the framework
  carries each whole: its record, its kind's record and its equipment bonuses as War of the Lions has them (FFTPatcher's
  PSP files, Glain's, GPL-3, read for facts: `NOTICE.md`), at WotL Restoration's numbers (261 to 277 War of the Lions'
  own; the five fell swords at 278 to 282; then 288, 289, 292 to 295, 300 to 305 and 308 to 313), so a mod that names
  one means the same item with either. WotL Restoration's art is its author's and isn't copied. **Their icons and
  words are Zodi's** (his message of 16 November, 05:26: "Here are my items icons and the descriptions, you can rename
  the icon files as you wish"), and since 17 November his art of 100 by 100 ("here is my item art for the War of the
  Lions items"), each carried beside the helper as an item icon's four files (`helper/wotl_items/`,
  `msf_wotl_<number>`: the menus' 100 by 100 his art pixel for pixel; the small one of 48 by 48, since his word of
  17 November that the art is the Art Texture only, his 32 by 32 icon of `Items_and_Descriptions.zip` pixel for
  pixel in its middle, kept as he sent it in `helper/wotl_items/sprite/`;
  `dev/research/sidequests/make_wotl_icons.py`), and War of the Lions' description of each
  as he gave it (`helper/wotl_items/descriptions.txt`; the item its line calls Crown Sceptre is Crown Scepter, his
  word of 06:50). Each still swings the look in
  battle of the game's nearest item of its kind (a fell sword's a knight's sword's, Tynar Rouge's a perfume's).
  - **Asked for by a mod**: `ModStudioWotLItems.json` at a mod's root (`{"Format": "Mod Studio War of the Lions
    items", "Version": 1, "Items": [...]}`). Its being there asks for the 40. `Items` may give the mod's own version of
    any: a whole item in `item.json`'s format plus `"Item"`, one of the 40's numbers, of the item's own Kind; its
    story point (its Record's byte 10) is 1 to 16 as a shop item's, or War of the Lions' own 20, which no shop reaches;
    its Icon is the framework's own for that item by its name (`"msf_wotl_262"`), one of the game's items' by its
    number, or a picture of the mod's own. A later mod's version stands over an earlier's. What can't be used is said and the framework's own stands.
  - **Given only where WotL Restoration hasn't given them** (its page made: its items stay its own, said: "War of the
    Lions' items are WotL Restoration's here: Mod Studio Framework gives none of its own."). Else a second block and
    native code like the mods' own items' (`ItemRoom.Data` and `Code` from 261, 55 numbers) stand before them: each of
    the nine item functions asks War of the Lions' code first, whose way on is the mods' own items' code, whose way on
    is the game's. Their bonus rows come before the mods' own items' (from the first row free), their Item rows with
    the mods'.
  - **Their counts in a save** where WotL Restoration keeps its own (the event variables' `0x2FC`: its four bytes
    `57 43 01 00`, then a count for each of the 55 numbers), so a save goes from one to the other; a save that never
    held one is left as it was (no mark written).
  - In the log: "War of the Lions' 40 items are given (261 to 313), each with its own icon and the look in battle of
    the game's nearest item of its kind." (and "; N as the mods changed it/them."); "Item: War of the
    Lions' items' N rows added."; "War of the Lions' items' counts are taken from the save loaded."
- **A mod's units of any battle** (`BattleFile.cs`, `BattleHooks.cs`, `Places.FindBattleUnits`; measured in
  `dev/research/sidequests/battle_units.py`). As a battle loads (`0x30428C`) the game looks its OverrideEntryData row
  up for each of the 16 places by the battle and the place (`0x1EA574`: no count of rows anywhere; made only when the
  dword at `0x7D453C` isn't 0) and writes the row's columns into the place's 40 byte entry, then makes the units. A row
  has no column for an entry's name, birthday, palette, team, war trophy, gil or AI, so a row can't make a unit where the
  battle file has none. The framework's hook of that function runs the game's own first, then writes the mods' units'
  bits into the entries: a mod's `ModStudioBattles.json` (`"Units"`) gives a unit by its battle (any of the game's, 0 to
  4095) and its place (1 to 16) as `Mask` and `Values`, 40 bytes in hex each: where a bit of Mask is set the entry's
  bit is Values'. A place the file leaves empty is a unit like any other (all 40 bytes). `Job`: one of its mod's own
  jobs by its Name, its number written as the entry's job. A later mod's bits stand over an earlier's.
- **An item past 255 on a unit** (his first point; his answer on a mod's own items there: "Yes, those too"). An entry
  keeps its five items in bytes and the game's rows' columns are cast to bytes, but the unit keeps words. The one
  function that puts an entry's equipment on (`0x277564`, called once, by the unit's making, before its stats) is
  hooked: the game's own first, then the unit's `Head`, `Body`, `Accessory`, `RightHand` and `LeftHand` of its
  `ModStudioBattles.json` unit (or of a quest's own battle's `Items`: `{"Unit": 3, "RightHand": 262}`), each a number
  (256 to 315) or the Name of one of its mod's own items, written as the game writes a byte's (a hand's shield in its
  shield's word, its weapon's none, and the other way). An item is put on only where it is worn (a weapon or a shield
  in a hand), and War of the Lions' only when the game has them this time; else said.
- **An item past 255 as a buried treasure** ("for Treasure Hunter"). The game's own table (`0x783840`: 128 maps, four
  records of 6 bytes) keeps a tile's rare and common item as words and the battle reads them as words; the map's load
  (`0x251584`) copies the map's 24 bytes to where the battle reads them (`0xD8DC90`). Its hook runs the game's own
  first, then writes the mods' items over the copy: `"Treasures": [{"Map": 74, "Tile": 2, "Rare": 262, "Common": "Moon
  Sword"}]`, whatever a table of another mod's put there.
- In the log: "The mods' battles: 2 units changed in 1 battle, 2 units wearing items past 255, 2 buried treasures on 2
  maps."; then once each as it happens: "battle 387: 2 of its units are as the mods have them.", "battle 387: unit 5
  wears item 293 (head), Moon Sword (right hand) and item 288 (left hand).", "map 74: its buried treasure is as the mods
  have it."; what is left out, each in a line.
- Rehearsed (`dev/test_wotl_items.py`, 42 checks and a SKIP without his art's zip; `dev/test_battle_units.py`, 25): the 40 against War of the Lions'
  PSP data, WotL Restoration's Item table and his program; their icons' files read back against his pictures and his
  words against the facts; a mod's asking and its own versions; his program's own nine
  item functions run over the 40 (each number's records, the game's and the mods' own numbers as before, every register
  kept), an item given, counted, listed and put under its tab; the counts in a save; the three sites found where
  measured, each called only where measured, nothing after a call counting on a register a hook may change; the game's
  own putting of equipment run and the framework's words in the same places; the map's treasures copied and read as
  words; a mod's file read and each way it can be wrong; the plan over two mods; a block, a unit and a map's treasures
  as the hooks leave them. **What could not be run here**: the game. No hook of this section has run in it.
- **Not looked after**: a save whose unit wears one of the 40 loaded with neither giver on (1.35.0's taking out
  covers 316 to 381 only). Mod Studio's side of all of it is built (above), and his second point (the three sections
  before this one).

**Test 126** (`dev/research/sidequests/make_test126.py`, `Job_Test_126.zip`; `dev/test_qt_job_tabs.py`'s section "Test
126's package", nine checks): test 125's package (made again from his four zips), its first mod opened in Mod Studio and
given, on Mod Studio's own pages:

- **Items**: a new item, Test 126 Ring (a copy of the game's Reflect Ring, with its icon); Moonblade (its price 1,260)
  and Acacia Hat (a picture of the mod's own as its icon) changed on the Items page; the three sold at the Outfitter of
  Magick City of Gariland from the story's first point. Over his numbers the ring is item 316 (his own mod keeps 317).
- **Battles**: the quest renamed Test 126 Quest (so it plays again), its first unit, a Battlemage, wearing Durandal and
  the ring; Mandalia Plain's 13 random battles (155, 157 to 168), in each the first unit always there that no row of the
  game's covers made one of the green team, and its first empty place given a unit (Add a unit's copy) made a Frost
  Mage man, an enemy in the enemies' palette, on the free tile next to that unit, wearing the Stardust Rod and the ring;
  South 4's (164) row's unit, a Dragoon woman of the player's side who comes at random, wearing the Gae Bolg and the
  ring; the Battle Arena's (map 116) tile 1 moved to 3, 8 (no unit of the quest's battle starts there), its treasures
  the Sage's Ring and the ring.
- **Pictures**, made up for the test: the Squire man's (sprite 96, entries 924 and 925, which seven other sprites wear:
  the list's numbers then, wrong, as his report showed; the game draws him from 992 and 993, test 127)
  twice the size in colors of its own, kept for its first palette; the Knight woman's (101) at the game's size; Frost
  Mage's man's figure twice the size in colors of its own, kept for palette 0; Potion's (260, 8 bits) and Rush's (154, 4
  bits) effects twice their size in colors of their own; Ether's (269) at the game's size. The bigger ones' white lines
  show only at twice the size (each block's middle pixel, the one the game's size keeps, is never one of them). This
  helper keeps about 16 MB for the pictures of more colors.
- **Checked here**: the package's files against test 125's; Mod Studio reading its own files back; this helper's checks
  (`Checks --jobs`, `--items`, `--battles`, `--textures`, `--quests`) over the package with his `Numbers.json`: nothing
  said, every place found in his program, each line as the test's notes quote it, every job the number test 125's plan
  gave it, the 13 battles' blocks as the hook leaves them; the notes' names held to the files. **What could not be run
  here**: the game. The add on file's battles (512 to 588) are in no scenario, no random battle's row and no table of
  1.5.2, so no test reaches them, and test 126 has none.

**1.56.0: a job may need a job of its own mod mastered** (test 125, `make_test125.py`,
`Job_Test_125.zip`: test 124's two mods, 1.23.0 and 1.16.0, Timekeeper needing Duelist mastered, the two jobs'
textures as Mod Studio's Export writes them now; and this helper). His report of 16 November on test 124: Onion
Knight's description right now, the rectangles under the feet still there; his answers: "Mod Studio should fix it
automatically", and "yes build both mastered job line and yes a job also be able to need one of your own mod's jobs
mastered". His word on test 125 (02:43): "Test 125 was a complete success and functioned how you said it would."

- **A job of its own mod needed mastered** (`JobFile`'s Needs): a need's Level may be the word `Mastered` for another
  job of the same mod too: `{"Job": "Duelist", "Level": "Mastered"}`. That job's own places are those its skillset
  fills (its Actions the first places, its Others from place 16 on; `JobNeeds.PlacesOfOwn`); a place that holds no
  ability counts as learned, as the game counts its own. The job needing it is open to a unit only where the unit has
  learned every one of those places, whatever its level, and the job needed is open to it. The unit's learned row in
  that job is read as its level is (`JobProgress.Row`): the menu's record's own where it is the job loaded in slot 22,
  else what the framework keeps of the job (bytes 5 to 7 of its eight, `JobProgress.RowOf`). GeneralJob's row asks it
  at 9, which the window shows as "Mastered"; the window's answer whether the unit has mastered it takes a job of the
  mods' by its identity (`JobAsker.HasMastered`).
- **Job Progress** (`JobTreeLines`): a line from a job of the mods' needed mastered is met only where the unit has
  mastered that job; with the cursor on the job that needs it, the needed job's right label shows the job screen's
  mastered stars in place of a level (`Master`), red until mastered and green once; on a job that asks a level of it,
  the label shows a level again (`Leveled`: its `LvMaster` stopped and its `LvNum` played).
- **The game's Dark Knight or Onion Knight its mod gives, asked mastered**: asked at level 8, by its own test as
  before (only a job made new or one of the game's generic jobs is asked by its abilities learned), and said: "{who}
  needs the game's {game} mastered: it is asked at level 8 (only a job made new or one of the game's generic jobs is
  asked by its abilities learned)."
- 1.55.2's fault for a job of the same mod asked mastered is gone; a Level that is neither 1 to 8 nor Mastered is said
  with "({least} to {most}, or Mastered)".
- **The bars under the feet, for good** (not the framework's: Mod Studio's Export, his answer): measured again in his
  program, the menus' figure routine (`0xCD458`, its size table read at `0xCDAB9`) takes each piece's texture from
  half a classic pixel in (`(u + 0.5) / 256`: the constant 0.5 at `0x722D60`, 1/256 at `0x722C94`, the adds at
  `0xCDC25` and `0xCDC31`) with the texture filtered, so the game's size's two rows past a piece's bottom and two
  columns past its right show along its edge; nothing above its top or left of its left. Test 124 cleared only the
  first; the second still showed, fainter (his woman Dark Knight's line: her texture's row 401). Export now clears both
  wherever a frame shows them over nothing (`classic_sprites.cleared_edges`, by `job_looks.cleared`, again until a pass
  clears nothing), for every job it writes; the game's own generic jobs' classic sheets, doubled so, come out untouched
  (Type 1), its own textures of the game's size with a few pixels cleared (12 to 43 a sheet where measured).
- New in the log: the line of the game's Dark Knight or Onion Knight asked mastered, above.
- Rehearsed (`dev/test_jobs.py`, "(1.56.0 ...)"; `dev/test_qt_job_tabs.py`): a need of a job of the mod's own asked
  mastered read, planned with its places and tested over four units by their learned rows; a job's learned row out of
  its kept bytes; the game's Dark Knight asked mastered; Job Progress's line and the needed job's right label over the
  tree's stand in; the wiring; test 125's package planned over his numbers (Timekeeper open only for a unit with all of
  Duelist's abilities learned). **What could not be run here**: the game; test 125 then passed in his game.

**1.55.2: test 123 put right** (test 124, `make_test124.py`, `Job_Test_124.zip`: test
123's two mods, 1.22.0 and 1.15.0, Shade needing the Ninja mastered, the two jobs' textures
made again; and this helper). His report of 15 November on test 123: a bar under the
woman Dark Knight's feet in the raised hands jump on the job screen, one under the woman
Onion Knight ("I wonder if there is a root cause for this issue for all these sprite
issues"); Onion Knight's description still its first words at level 8; Onion Knight's
level counting the Squire, the Chemist, the Mime and Dark Knight; Job Progress still
saying level 8 for the Knight and the Black Mage; "can new jobs could also get the
Mastered jobs requirement like Dark Knight does".

- **The job screen's window's words** (`JobRoom.HelpWordsSites`, row 164): the window
  shows a job's words by the UI table's text 1019, `<jobhelp(lnum0, lnum1)>`, which the
  game's text maker turns into the Job row's words (its tag reader `0xF2648` calling the
  Job row's words' reader `0xF4800` from one place, `0xF31CE`, for a name and words
  alike; `dev/research/sidequests/job_words.py`). So it read the job's own row at every
  level. The game's Onion Knight with a `MasteredDescription` now has the Job table's
  row 164 (the job the game takes a level 8 Onion Knight's words from, empty in the game)
  written as its row with that description, and that call goes through the framework's
  code: for the Onion Knight's description it asks the framework the key Job Summary
  would read (`JobAsker.SummaryKey`) and reads row 164 on its level 8 words' key. Where
  the call isn't found, the window shows its first words at every level, said.
- **Mastered on Job Progress** (`JobTreeLines`): a level's label of the tree's layout
  (`TextBoardJobLv`) has `LvMaster` besides `LvNum`: its "Lv." and number hidden and the
  job screen's own mastered stars shown (`ui_master_uitx` part 0, the job screen's
  `Unit` `Star`); the game's own code never plays it on the tree. A small icon of a job
  needed mastered has it played, and is green only where the unit has mastered the job
  (`JobAsker.HasMastered`), red otherwise; the other icons as before.
- **A mod's job may need one of the game's jobs mastered** (`JobFile`'s Needs, Zodi's
  word: "Like if the user wanted Ninja master as a requirement for its job"): a need's
  Level may be the word `Mastered` (in any case) for one of the game's generic jobs (74
  to 93): `{"Job": 89, "Level": "Mastered"}`. It is planned as the game's Dark Knight's
  Knight and Black Mage are (open and every place of its skillset learned, whatever its
  level; GeneralJob's level 9 and the window's "Mastered"; the tree's stars). A job of
  the same mod asked mastered is a fault: "its Needs ask {name} mastered: only one of the
  game's generic jobs (74 to 93) can be asked mastered". Mod Studio's Jobs tab offering
  it comes with Zodi's word on its look.
- **Onion Knight's level, measured, no change**: the game's own count (`0x348828`), run
  in his program, counts only the jobs 76 to 92 (Knight to Dancer), two a level, 14 make
  level 8; never the Squire, the Chemist, the Mime, Dark Knight or Onion Knight. The
  framework touches nothing on that path.
- **The bars under the feet** (not the framework's: Mod Studio's textures of his sheets,
  measured over TYPE1's 364 frames): the game draws each piece of a sprite with a sliver
  of what lies just past its bottom (or right) edge in the sheet; the game's own sheets
  leave that line empty where a frame draws the edge over nothing, his didn't in a few
  pieces. Test 124's copy has that line taken out (`make_test124.scrubbed`); whether Mod
  Studio does it for every classic sprite it doubles is Zodi's choice.
- New in the log: "the job screen's window shows {who}'s description for its level 8 to a
  unit whose Onion Knight is level 8." (or "the job screen's window shows the game's Onion
  Knight's own description at every level: {missing} wasn't found in {program}. A game
  update may have changed it: look for a newer {name}.").
- Rehearsed (`dev/test_jobs.py`, "(1.55.2 ...)"; `dev/test_qt_job_tabs.py`): a need asked
  Mastered read, planned and tested over five units, its faults; the tree's icon of a job
  needed mastered over the tree's stand in; the Job table's row 164; the window's call
  found and changed, left alone in a program whose call names another function, and run
  in his program's own code with the framework's answer; test 124's package planned over
  his numbers. **What could not be run here**: the game drawing the window, Job Progress
  and the sprites.

**1.55.1: test 122 put right** (test 123, `make_test123.py`, `Job_Test_123.zip`: test
122's two mods, 1.21.0 and 1.14.0, its two job files written again with Zodi's words, his
Dark Knight and Onion Knight sprites, job art and portraits, a man's and a woman's each, and
Job Summary laid out as the game's own jobs'; and this helper).
His report of 15 November on test 122 (with his words of 05:41 and 05:49 on his job art, his
portraits and Job Summary's layout): the seven abilities' names blank on the abilities
page and in the job screen's window (their descriptions shown), War of the Lions' words
for Dark Knight, Darkness, Onion Knight (two: below and at its level 8) and the seven
abilities, and "on the Level requirements menu in this screenshot it should say Mastered
for Knight and Black Mages Required Level column"; his answer on the 20 kills: "Leave the
kills out".

- **The seven abilities' names shown** (`DarkKnightAbilities.Icons`,
  `AbilityWords.WithIcon`): the game shows no name for an ability whose row has no icon
  (its IconId, the row's + 4, 0), and 1.55.0's rows had none, as the game's own rows of
  those abilities have. Measured by comparison: the other mod's rows of the same seven,
  whose names show in his game, differ from the game's in their icon and words only.
  Each row written now takes the icon of one of the game's own abilities, as the loaded
  table has it: Sanguine Sword, Crushing Blow, Abyssal Blade and Unholy Sacrifice
  Shadowblade's (165), Infernal Strike Duskblade's (164), HP Boost and Vehemence Attack
  Boost's (465).
- **War of the Lions' descriptions**: where the job's file gives none, the seven get War
  of the Lions' names and, now, its descriptions as Zodi gave them ("Absorb HP from the
  target.", and so on; `DarkKnightAbilities.Names`).
- **Mastered in the window of what a job needs** (`JobNeeds`, `JobScreen.Needs`): its
  Required Level cell is the UI table's text 1012 ("Lv. <num=lnum0>", its layout's own)
  handed the need's level from GeneralJob's row; its Current Level cell is 1004 handed
  the record's level, red where it is below the need's. A need of a job mastered is now
  level 9 in GeneralJob (`MasteredShown`, a level no job has); the window's record of
  that job has 9, for the window's call alone, where the unit has mastered it; and both
  texts, as the UI table loads, show the language's own word for mastered (UI 1077:
  "Mastered", French "Maîtrisée", German "Meister", "Master" in the others) for 9 and
  themselves otherwise, in the game's own way of choosing words by a number
  (`<if([lnum0==9],"Mastered","Lv. "<num=lnum0>)>`, as its text 3883 does for 8). Only
  where a mod's job needs a job mastered (the game's Dark Knight: the Knight and the Black
  Mage). A text not as the game's is kept, said.
- **Onion Knight's words for its level 8**: its Words may give `MasteredDescription`
  (the Description's rules; only the game's Onion Knight, Game 161). The job help table
  gets a second row at the key of the job the game takes a level 8 Onion Knight's
  record and older words from (164), under the same heading; Job Summary's two reads of
  a row by its key (`JobRoom.SummarySites`) call the framework's code instead of the
  generic getter, which reads that row where the screen's unit's Onion Knight is level 8
  (`JobAsker.SummaryKey`, the menu record's level of slot 21) and the key asked
  otherwise. Where the reads aren't found, its words show at every level, said. Its
  Words may give `MasteredSummary` too (Zodi's word of 05:49: "make sure the Job Summary
  for the two jobs matches the format of the vanilla jobs"): its whole Job Summary for its
  level 8, as a Summary's rules, laid out as the game's own rows are (Job Overview, Usable
  Equipment, Select Abilities); that row is it, else the MasteredDescription under the
  heading. Faults: "its Words' MasteredSummary can't be given: only the game's Onion
  Knight (Game 161) has words for its level 8"; "its Words' MasteredSummary is {value},
  not text of 1 to 4000 characters".
- **The game's jobs with their own sprites**: a Look on the game's Dark Knight or Onion
  Knight gives it a pair of sprites of its own, as any job's (here his four, each told
  Type 1, as the Knight's and the Squire's frames are), with portraits of their own, and
  its Pictures its own job screen art, as any job's (1.42.0 to 1.46.0, no change). The
  line: "..., learning no abilities, with its own sprites ...".
- New in the log: "Job Summary shows {who}'s words for its level 8 to a unit whose Onion
  Knight is level 8." (or "Job Summary shows the game's Onion Knight's own words at every
  level: {missing} wasn't found in {program}. A game update may have changed it: look for
  a newer {name}."); "UI: the window of what a job needs shows Mastered for a job needed
  mastered (its {n} level text(s) written)." (or "UI gets no Mastered for the window of
  what a job needs: {why}. A job needed mastered shows there as level 9.").
- Rehearsed (`dev/test_jobs.py`, "(1.55.1 ...)"; `dev/test_qt_job_tabs.py`): the icons
  and descriptions in the Ability table (WotL Restoration's copy of the game's, read as
  data); the two level texts made for four languages (English, German, Japanese, French
  with its scale marks) from the 1.5.2 tables, and each text not as the game's kept;
  GeneralJob's rows; the window's records with a job needed mastered and mastered or not;
  the asker's answers on the menu record's levels and learned rows; `MasteredDescription`
  read and its faults; the job help table's second row; Job Summary's two reads found
  and changed, and run in his program's own code with the framework's answer; test 123's
  package planned over his numbers. **What could not be run here**: the game drawing the
  texts and the job screen, Job Summary and a battle.

**1.55.0: the game's own Dark Knight and Onion Knight** (test 122, `make_test122.py`,
`Job_Test_122.zip`: test 121's two mods, 1.20.0 and 1.13.0, the first with two job files
more, Dark Knight and Onion Knight, written by hand; and this helper). Zodi's order of 13
November ("Dark Knight and Onion Knight on the framework's own rows"), his three answers
of 14 November (a mod gives them; the game's own rule, less the kills; the game's own
abilities, named by the mod) and his word of 15 November, once ability 45 turned out to be
Chant: "In WotL, and you can confirm with FFTPatcher to see this for the PSP, Dark Knight
does not have Chant in its skill list. It has Sanguine Sword. What ever War of the Lions
does we should do." Measured first (`dev/research/sidequests/dark_onion.py`;
`claude/dark-onion-knight-research.md`): every way the game reaches 160 and 161.

- **A job's file may be the game's job**: `"Game": 160` (Dark Knight) or `161` (Onion
  Knight), with its Name, Like, Record and Words as any job's (the record's first
  number the game's: 224, none). Needs can't be given (the game's own rule opens it);
  Onion Knight takes no Skillset (it learns no abilities); Dark Knight's Skillset gives
  its Words, Like (its icon) and, if it likes, `Names` for the game's abilities of
  skillset 224 (45, 184, 219, 220, 357, 484, 485, 488, 491; each an Ability, a Name and
  a Description), never Actions or Others: its abilities are skillset 224 as the game's
  and the mods' tables make it. The first mod in load order that gives one gives it, a
  later one's left out and said; with Dark Knight & Onion Knight (Generic) on, neither is
  given (that mod keeps them on its own page). Each fault in words, the job left out.
- **Where they live**: each keeps the game's number, given after the mods' own jobs (which
  keep their places and progress); shown first on the framework's rows and on Job
  Progress (Dark Knight, then Onion Knight, then the mods' own). The look's places and
  the five portrait routines that read the job again (`Special1` to `Special5`) take the
  job its look is drawn from; the same job, the job set, the second skillsets (Dark
  Knight's pair once, not where the game's list holds it), the other abilities, the
  needs window's slot (0x100 and the job, GeneralJob's rows 416 and 417), the battle's
  learned row of skillset 224 (row 20 for any unit), the JP table of slot 20 (its Like's
  row) and the levels of slot 20 as the mods' jobs'. Slot 21 is never counted: **Onion
  Knight is the game's own** (no EXP and no JP for acting; its level set at each write
  back from the jobs a unit has mastered, one more than half, 8 at most).
- **What opens them**: the game's own rule, less the 20 kills nothing in the game counts:
  Onion Knight the Squire and the Chemist at level 6; Dark Knight the Geomancer, the
  Dragoon, the Samurai and the Ninja at 8 and the Knight and the Black Mage mastered
  (every place of their skillsets learned, shown Lv. 8). A mod's job may need the game's
  Dark Knight or Onion Knight its mod gives.
- **War of the Lions' Dark Knight** (`DarkKnightAbilities.cs`): FFTPatcher's PSP data
  (read for facts only) has Sanguine Sword at 45 and Delita's Holy Sword holding Chant as
  152; the game made 45 an exact copy of 152 and put it in Holy Sword. Where a mod gives
  the game's Dark Knight, 45 is made War of the Lions' again (its common record, cost
  500; its action record's source, formula 0x65, range 3, the dark element, and the
  records the game made from it where it has; its animation; its effect Shadowblade's,
  173, as War of the Lions' 287 isn't among the game's files) and Holy Sword's sixth place
  152 again: each part only where it is still the game's own (another mod's change kept,
  said), its places found before anything of the program is changed. The names
  (`AbilityWords.WithGameNames`): the job's file's, else War of the Lions' (Sanguine Sword,
  Infernal Strike, Crushing Blow, Abyssal Blade, Unholy Sacrifice, HP Boost, Vehemence)
  with no description; Sanguine Sword's row made like Infernal Strike's (no icon, no
  voice), cost 500. A save's unit in 160 or 161 that no mod gives now is put on a job of
  the game's, where the other mod is off.
- New in the log: "{who} is the game's Dark Knight (job 160), looking like the game's job
  {Like}, with the game's skillset 224." and "... is the game's Onion Knight (job 161),
  looking like the game's job {Like}, learning no abilities."; "the game's Dark Knight's
  Sanguine Sword (ability 45) is War of the Lions' again, with Shadowblade's effect (War
  of the Lions' isn't among the game's files), and Holy Sword holds Chant (ability 152)
  again."; "Ability: the names of {n} of the game's Dark Knight's abilities written (the
  job's file's, else War of the Lions')." The JobCommand line counts the jobs that have a
  skillset.
- Rehearsed (`dev/test_jobs.py`, "(1.55.0 ...)"; `dev/test_qt_job_tabs.py`): the measure
  held to his program, War of the Lions' facts to FFTPatcher's PSP files; the job files,
  their faults, the plan, the order shown, the needs and the opening by the rule; the
  tables' rows and names; Sanguine Sword's places and changes, a part another mod changed
  kept, a place not found; run in his program's own code: each slot, Onion Knight's level
  (the game's own count), the portrait routines, the battle's learned row, the JP table,
  the levels and the menu's copy, the second and other lists, the same job, the needs
  window's slot, and the game's reading of Sanguine Sword after the change; test 122's
  package planned over his numbers. **What could not be run here**: the game itself, the
  job screen and Job Progress drawing them, a battle and the effects.

**1.54.0: a job's own textures drawn for Type 1 or Type 2 frames** (test 121,
`make_test121.py`, `Job_Test_121.zip`: test 120's two mods, 1.19.0 and 1.12.0, the
first with two new jobs made on Mod Studio's Jobs tab, Blue Mage with his Type 2 sprite
for its man and Berserker with his Type 1 sprite; and this helper). His 8th note of 14
November: "Sprites for humans have two kinds that the community refers to as Type1 and
Type2. When replacing the squires sprites for the users modded sprite we should account
for this", and his pick "Framework sets its frames". Measured first
(`claude/classic-sprites-research.md`): a sprite's attributes (BATTLE.BIN's table, the
program's `0x673300`) pick its frames and animations by their first two bytes, and every
one of the game's 38 generic sprites has one of two rows, (0, 0, 0, 36) for Type 1 (the
Squire, Knight, Archer, Monk, Thief, Dragoon, Samurai and Ninja) and (1, 1, 0, 36) for
Type 2 (the other twelve). FFT Sprite Porter (Lucifeh, MIT, read for facts only)
switches a character's layout by those two bytes. Every new job is based on the Squire,
and the framework gave a job's own sprites its Like's row, so a Type 2 sprite would have
come apart as it moved.

- **A job's file says the frames its own textures are drawn for**: its Look's `Frames`,
  a man's and a woman's (`Man`, `Woman`, either or both), each 1 or 2, its names in any
  case; only for one whose Look's Textures give textures of its own (one wearing its
  Look's is drawn in their frames). Not said, its own textures are drawn in its Like's
  frames, as before. What is wrong is said and the job left out: "its Look's Frames
  isn't a list of fields with a Man's or a Woman's frames", "its Look's Frames' Man is
  3, not 1 or 2 (Type 1 or Type 2 frames)", "its Look's Frames give the woman's frames,
  but its Look's Textures give the woman no textures of its own to draw in them". Both
  readers alike (`JobFile.cs`, `mod_studio/mod_jobs.py`).
- **The attributes' row**: a man's or a woman's own sprite whose textures are given to
  the game and drawn for frames its Look names takes the row of the game's generic job
  drawn for them, the Squire's for Type 1 and the Chemist's for Type 2
  (`SpriteRoom.Source`, `FramesJob`); every other row, and that sex's where the
  textures' hooks can't be made, as before. What others write to the game's own rows is
  brought over to the sprites that take them (Sync). No change of the game's code.
- New in the log: the job's line says it after its textures (", the man's drawn for Type
  2 frames", ", drawn for Type 2 frames" for both, ", the man's drawn for Type 1 frames
  and the woman's for Type 2").
- Rehearsed (`dev/test_jobs.py`, "(1.54.0 ...)"; `dev/test_job_looks.py`;
  `dev/test_qt_job_tabs.py`): the two rows held to his program for all 38 generic
  sprites; four jobs' Frames read (both sexes, either, each kind, names in any case), the
  attributes' rows each sex takes, the same plan without the textures' hooks (every row
  its Like's, nothing else changed), what others write brought over, eight faults said
  in words; a job as Mod Studio's Export writes it taken with nothing to say; test 121's
  package planned over his numbers (Blue Mage's man the Type 2 row, its woman and the
  Berserker the Type 1). **What could not be run here**: the game itself, a Type 2
  sprite moving on a job based on the Squire.
- **Test 121 passed** (14 November, 23:26): "Test 121 was a complete success and
  functioned how you said it would." Every line its notes quote in his log word for
  word; his screenshots show both sprites whole, a woman in either job the Squire's.
  The jobs' numbers were his game's own, not the plan's (he had ticked "Free disabled
  mods' numbers"): Blue Mage job 146 with sprites 176 and 177, Berserker 143 with 172
  and 173.

**1.53.0: the new jobs in a side quest's battle** (test 117, `make_test117.py`,
`Job_Test_117.zip`: test 116's two mods, 1.15.0 and 1.8.0, the first with a side quest
whose battle puts its units in its two jobs; and this helper). His order of 13
November, its next step after the Job Tree: jobs in a quest's battle, enemy or guest
units in a side quest's battle wearing the new jobs (his answer "Before the Jobs
page"). Measured first (`dev/research/sidequests/quest_jobs.py`;
`claude/quest-jobs-research.md`). **Test 117 ran (14 November, 02:36): "almost a
complete success and functioned how you said it would"**: every unit in its job at
its job level with its abilities, an enemy Battlemage using Swift Step, the knight
joining as a Battlemage at job level 4 with every ability of his job. Its one fault
was the test's own: its guest was on the green team, which the game counts as an
enemy (its battle files hold blue and red only; a guest is a blue unit without
Control). **Test 118** (`make_test118.py`, `Job_Test_118.zip`: the guest a blue unit
without Control; this helper unchanged) **passed (02:46): "I now have a guest during
the battle."**

- **A quest's battle names a job of its mod's own** for any of its 16 units: the
  quest file's battle `Jobs`, each its unit (1 to 16) and the job's Name (1 to 40
  characters, none a control character); a unit given two jobs, or one past 16, is a
  problem, said. Both readers alike (`QuestFile.cs`, `mod_studio/side_quests.py`).
- **The framework puts the unit in it** as it plans the quests (after the jobs, as the
  game starts): the unit's job (the 11th of its 40 bytes) the number the job was given
  this time, as it gives the units' own names theirs. Where the quest's mod gives no
  such job this time (not given, or the jobs not made at all), the unit keeps its
  file's job, said. The quest's line says each: "unit 1 of Battle is put in its mod's
  Battlemage (job 142)", "unit 2 of Battle keeps job 76 (its mod gives the game no job
  Shade this time)".
- **It learns its job's abilities as the game's own units learn their job's**, at the
  job level its file gives (its career job's level, the 10th byte's low half, 1 to
  8): every one where its first skillset is 0, else each by its chance, paid from its
  JP (the game's way for its generics, 0xFF). The game's setup loops over its twenty
  generic jobs only: the framework's code after the loop (`0x277463`) gives slot 22 its
  JP and level and runs the game's own learning for the unit's job; and one ability's
  learning (`0x278178`) writes slot 22's bit in the job's own row (19, Mime's), where
  the game alone would write it into the unit's level bytes. A unit in a game's job,
  or in a job no mod gives, is made as before, byte for byte.
- **After a load it keeps its palette**: the load's walk over the figures
  (`0x1009E8`, its write at `0x100F0D`) gives a figure of the framework's sprites (170
  to 254) the palette it was made with, any other the skin's as the game gives it.
  Only where a job has its own sprites and colors.
- **A unit who joins** (a guest, or a scene's unit asked to join): its job is loaded
  for the party before the game writes its battle unit back (`0x274EB8`), so its
  progress in that job is kept under its own job.
- **Mod Studio** keeps the quest file's Jobs as it opens and saves a mod
  (`side_quests.py`, read with the helper's words; `quest_edits.py`: a unit's job of
  its mod's own given up when its main job is changed on its card, worn by a copy of
  it, gone with the unit taken out). Choosing a mod's job on a unit's card comes with
  the Jobs page.
- New words in the log: "A unit a battle's file puts in a mod's job learns its job's
  abilities as the game's own units learn their job's, at the job level its file
  gives." (where its places aren't found: "... knows none of its job's abilities:
  ... wasn't found in .... A game update may have changed it: look for a newer Mod
  Studio Framework."); "after a load, a unit of another team in a mod's job with
  colors of its own wears the player's colors: ..." (only where the walk isn't
  found); and the quest's line's two parts above.
- Rehearsed (`dev/test_jobs.py`, "(1.53.0 ...)"; `dev/test_side_quests.py`;
  `dev/test_quest_edits.py`): the measure held to his program's bytes; the places
  found, and not found in a program moved; the game's own setup of a unit's abilities
  run whole in his program's code for a man and a woman, the first skillset 0 and
  0xFF, the job levels 0 to 0x23, and four other units byte for byte; one ability's
  learning for slots 0 to 22; the walk for ten sprites; a guest who joins, over the
  progress' stand in; the quests planned with jobs given and not; test 117's package
  planned over his numbers. **What could not be run here**: the game itself: the
  figures, the colors after a load, what the units do on their turns.

**1.52.0: the lines' bends rounded, every line out of its job, one line for one
level, the jobs that need only the game's jobs after those that need nothing**
(test 116, `make_test116.py`, `Job_Test_116.zip`: test 115's two mods, 1.14.0 and
1.7.0, with Warden needing Sage at level 2, as Evoker does, so the two share one line;
and this helper). His word on test 115 (13 November, 22:36): "There is room for three
jobs under the Timekeeper in this example. ... two of the lines make sharp angles. ...
both of those lines do not extend into the Sage correctly ... Jobs that have no New Job
requirements but have Vanilla job requirements should appear after the Jobs that have no
requirements at all. ... in vanilla, two different jobs that share the same lv
requirement from a job will share the same line ... They only get their own line if the
lv requirements are different. ... After you fix these bugs our dynamic Job Tree will be
complete." (`claude/job-tree-research.md`). **Test 116 ran (13 November, 23:47): "Test
116 is a complete success and functions how it is supposed to. Thank you for completing
the dynamic new jobs progress tree."** His four screenshots: the cursor on Evoker (the
line from Duelist green with its label 1, Sage's shared line red whole, its label 2), on
Warden (the same shared line lit, its flipped bend up turning as the game's own), on
Herald (Sage's line at 4 and Herald's to Mender, red) and the view slid to Mender and
Shade. The log's lines as they should be, no fault. **The DLL test 116 carried was
built two minutes before 1.52.0's last two changes** (up to five corridors into a column
where it had three, and a way out on the other side past a side's two): they place test
116's sixteen alike (measured, and the two builds' code compared method by method: only
those two differ), and the DLL shipped is built again with them.

- **The jobs in his order**: of the jobs no line joins, those that need nothing come
  first, then those that need only the game's jobs; the jobs other jobs need follow in
  the same run of places, under them, not from a column of their own; then each job
  right of the job it needs, as before.
- **One line for each needed job and level**, as the game draws its own (Squire to
  Archer and Knight): the jobs that need a job at the same level share one line, which
  splits where it turns (the furthest job turns into its side, the others branch off
  the upright); a job that needs it at another level has a line of its own.
- **Every line starts under the job it comes from**, behind its figure, so it comes out
  of the figure's base (or from behind the figure). A job's lines of different levels
  leave it 12 apart, the line with a job in its row at the straight line's height.
- **Each bend is the game's own**: a line up or down is a copy of the game's right then
  down line (the Archer's line to the Ninja) from under the figure to its corridor, or
  flipped top to bottom to turn up, as the game flips its own Monk to Geomancer line,
  and the game's down then right or up then right line into the job, the two strokes on
  the same pixels (measured on his screenshots: a stroke runs 1 to 4 pixels inside a
  bent piece's outer edges).
- **Lit as the game lights its own**: with the cursor on a job, its lines out and every
  line into it, whole.
- **Corridors**: up to five lines into a column each have their own (1.51.0 had three,
  and a fourth ran on the first's pixels).
- No new words in the log.
- Rehearsed (`dev/test_jobs.py`, "(1.52.0 ...)", and the 1.49.0 to 1.51.0 sections'
  checks brought up to it; the rule held by `dev/research/sidequests/job_lines.py`):
  the plan over test 116's sixteen and others; what a flipped copy rests on in his
  program and his layout; the strokes on eight lines of his screenshots, to the pixel;
  each line's own way over nine shapes and how its pieces meet (21 bends); test 116's
  sixteen drawn and lit; over the stand-in for the tree. **What could not be run
  here**: the game's drawing of what is placed, above all a flipped copy (the game
  flips its own line by the scale -1 by 1 and a half turn, the framework by 1 by -1).
- **Not changed**: the pointing hand covers the first small icon of the job under the
  cursor. **Not a fault** (found at the close): Battlemage's blue checkerboard in its box
  on Job Progress is its own test texture (test 103's checkerboard in the woman's own
  blues), drawn right, as on the job screen and in battle; the tests' notes since 113
  had called it not put right.

**1.51.0: the lines joined up, the jobs with no lines first, the view sliding
further right** (test 115, `make_test115.py`, `Job_Test_115.zip`: test 114's two
mods, 1.13.0 and 1.6.0, with Mender needing Herald 2 and Shade needing Mender 2 only
so the new jobs reach a fifth and a sixth column; and this helper). His word on test
114 (13 November, 21:06): "Test 114 was largely a success. In this example with the
sage, two of the lines do not fully connect back to it. ... one design choice I want
is that new Jobs that do not have any requirements be order on the left most columns.
That way if the user adds more jobs with more requirements for their existing new
jobs they can continue towards the right hand side for as many jobs that they add.
The menu should should obviously be able to continuously panned to the right to
accommodate the amount of added jobs." (`claude/job-tree-research.md`). **Test 115
ran** (22:36): the bends met square, two lines stopped short of Sage, and his order
and the game's shared lines: put right as 1.52.0 (above).

- **Each line has its own way, all the way from the job it starts at**: a line
  going up leaves the needed job's box a little above the straight line's height, a
  line going down a little below it, each by a lead of its own to its corridor (the
  line along the needed job's row that every bent line shared is no longer made);
  each needed job's lines into a column run in a corridor of their own; each line
  goes into its job at a height of its own, the straight one where the game's own go
  in, then those from above, then those from below. So no line runs along another.
- **A lit line is drawn in front of every other line**: each line has a lit copy of
  itself (a bent one's lead too), made after every other line and drawn only while
  the cursor's job lights it. Under it the line keeps its look.
- **The jobs no line joins stand first**: the new jobs that need no other new job
  and that no new job needs fill the leftmost columns, five to a column; the jobs
  joined by lines start in the next column (first the ones others need, then each
  job right of the job it needs, as before), so a mod's jobs that need its other
  jobs grow to the right.
- **The view slides four columns at a time for as many columns as there are**, as
  it already did (his sixteen never needed a fifth column). The framework takes up to
  58 jobs (a free skillset each); the tree was rehearsed with 58 in one chain.
- No new words in the log.
- Rehearsed (`dev/test_jobs.py`, "(1.51.0 ...)", and the 1.49.0 and 1.50.0 sections'
  checks of where things stand brought up to them; the rule held by
  `dev/research/sidequests/job_lines.py`'s `arrange`, `line_at` and `lead_at`): the
  plan for several sets of jobs, 58 among them; the view over 58 jobs in one chain;
  each line's own way over five shapes; test 115's sixteen drawn and lit; over the
  stand-in for the tree (`helper/Checks/TreeChecks.cs`). **What could not be run
  here**: the game's drawing of what is placed, as with 1.50.0.
- **Not changed**: the pointing hand covers the first small icon of the job under
  the cursor (put to him with test 115). Battlemage's figure is a blue checkerboard
  in its box on Job Progress (its own test texture drawn right: not a fault, found at
  1.52.0's close).

**1.50.0: the lines and the small icons on Job Progress** (test 114,
`make_test114.py`, `Job_Test_114.zip`: test 113's two mods, 1.12.0 and 1.5.0, with
Evoker needing Duelist 1 and Sage 2 and Herald Sage 4, so a line of each kind is
drawn; and this helper). The last of the four steps of the Job Tree's build (the
design he signed off: "Between two new jobs: a line, with the level it asks, as the
game draws its own. For each of the game's jobs a new job needs: a small icon of
that job with the level, beside the new job's box."; his screenshots' words: "green
line for level requirements already met. Red lines for job levels not yet met.";
`claude/job-tree-research.md`). **Test 114 ran** (21:06): "largely a success";
two of Sage's lines didn't join back to it: put right as 1.51.0 (above).

- **A job's file needs nothing new**: its `Needs` (1.48.0) say what is drawn.
- **A line between two of the mods' jobs** where one needs the other: a copy of one
  of the game's own lines, sized by the game's own sizing of a box (its animations
  size references so while it runs) and put with the game's lines. In one row a
  straight line from the needed job's box to an arrow's head before the needing
  job's; in different rows a line down or up a corridor 180 left of the needing
  job's box that turns into its side, off a line along the needed job's row (its
  head not drawn). A job's needs are of the game's jobs or of its own mod's, so a
  line is always within one mod.
- **A small icon for each of the game's jobs a job needs**, left of its box, three a
  row (the second row above the first): a copy of a picture box of the tree's own
  given the job's icon by the game's own name board writer (the question mark where
  the game hides that job from the unit), with a copy of a level's label under it
  showing the level asked. Not shown until the game has given it its icon.
- **The colors are the game's own**: a line light where the unit has the needed job
  open at the level asked and dark where it hasn't; an icon's level green or red
  the same way. With the cursor on a job the lines into it and out of it light up
  green or red, as the game's own do, and by each line into it the level asked
  shows beside the job it starts from.
- **Where any of it can't be drawn** the boxes stand without it. The log, once:
  "Job Progress draws a line between two of the mods' jobs where one needs the
  other, and beside a job a small icon of each of the game's jobs it needs with the
  level asked: green where the unit has the level, red where it doesn't." Where it
  can't be: "Job Progress shows the mods' jobs without their lines and small icons:
  {why}." A fault while they are brought up: "the lines and small icons on Job
  Progress couldn't be drawn (...); the boxes show without them."
- Rehearsed (`dev/test_jobs.py`, "(1.50.0 ...)"; the measure held to his program's
  bytes and his layouts by `dev/research/sidequests/job_lines.py`): **his program's
  own play of a line and of a label and its name board's writer, run in his
  program's own code as the framework calls them**; where each need is drawn, the
  copies, the looks for two units and under the cursor, every way it can fail, over
  a stand-in for the tree (`helper/Checks/TreeChecks.cs`). **What could not be run
  here**: what the game's layout code does with a copied line sized, a picture box
  given an icon and a label's copy. Only his test shows it.
- Battlemage's figure (the one test job with sprites and textures of its own) is a
  blue checkerboard in its box on Job Progress (its own test texture drawn right: not
  a fault, found at 1.52.0's close).

**1.49.1: test 112's three faults put right** (test 113, `make_test113.py`,
`Job_Test_113.zip`: test 112's two mods, 1.11.0 and 1.4.0, nothing else of them
changed; and this helper). **Test 113 passed** (13 November, 16:56: "Test 113 was a
complete success and functioned how you said it would.").

- **The game's own tree right for the unit as it is now**: with the framework's rows
  of the job screen scrolled down, the game's fillings gave the tree only the jobs on
  the rows shown, so the game's places kept what another filling had left (his
  Chemist kept the check mark of the job the unit was in before it was made an
  Alchemist; a fault since 1.39.1, never seen until the tree had the unit's own box
  beside it). Where the rows shown don't start at the game's first, the filling is
  now run for the game's own list first, each of the game's jobs going to its own
  place.
- **Only the box under the cursor shows the ring and its name**: each copy is played
  the piece's own `CursorOut` as it is made (a copy came up showing them).
- **The level's number shows after "Lv."**: the copied level's text had given its
  key to the tree's own text setter (binding a setter takes a text's key); the
  copy's text is given that key back before the framework's setter is bound.

**1.49.0: the new jobs on Job Progress** (test 112, `make_test112.py`,
`Job_Test_112.zip`: test 111's two mods, 1.10.0 and 1.3.0, nothing else of them
changed; and this helper). The second and third of the four steps of the Job Tree's
build: the new jobs' boxes, the cursor and the view (his words of 13 November: "All
jobs new and vanilla jobs together on the Job Progress (the tree). Ideally nothing
about the original Job Progress but in addendum to it our framework adds boxes and
lines for the new jobs around the original job progress."; his choice of the sketch,
"Slide to the side"; `claude/job-tree-research.md`). **Test 112 ran** (13 November,
16:32): the boxes, each with its figure, and the slide shown in his game; his three
faults put right as 1.49.1 (above).

- **A job's file needs nothing new.** Every one of the mods' jobs gets a box; where a
  job's `Needs` name another job of its mod, its box stands right of that job's.
- **Where the boxes stand**: right of the game's tree, in columns of five (from 1,960
  every 340 in the layer the game's boxes are in, rows from 120 every 175: the
  sketch he signed off). The jobs in the order the framework is given them. First
  the jobs others need that need none of their mod, from the first column's top;
  then each job that needs one, in the column after it and in its row (the nearest
  free row where that is taken; the next column where the column is full); last the
  jobs that neither need nor are needed, in the places left.
- **A box is a copy of one of the game's own** (Squire's), made by the game's own
  copy of a box as a mod's places on the world map are, named `MsqJob` and its
  number, tagged as the tree tags its own with a place from 20 on. Everything it
  shows is the game's piece's own: the unit's figure in the job, the ring and the
  name board with the level under the cursor, the grey figure of a locked job, the
  black one and "???" of a job no unit has open, the check mark on the job the unit
  is in.
- **A job's record is the game's own**: after each of the game's fillings of the job
  screen the framework has the filling run again for the mods' jobs alone (18 at a
  time after the unit's first job), the two calls that touch the job screen left out
  meanwhile, the list and its count put back. A unit whose list is the game's own (a
  guest, a monster) has the boxes put away.
- **A figure's slot of the framework's own**: the game numbers its figures 0 to 255
  (the job screen's from 0x3D, the tree's from 0x50). The framework takes its own
  from 76 numbers no screen was seen to use (0x89 to 0xAD, 0xB8 to 0xC7, 0x6D to
  0x7C, 0x64 to 0x6A), each only while the game has it free. Not every place that
  numbers a figure was read. A job that gets none still shows its name and level,
  said in the log.
- **The cursor**: the tree's update is hooked. One of the mods' jobs chosen (F or
  Enter, or a click) shows its row on the job screen and goes back there with the
  cursor on it, as the game does for its own (its Learn Abilities and Change Job
  menu, or the Level Requirements window for a job that isn't open). Every move is
  the game's own update, run over the tree or over a copy of it in which the
  cursor's place's directions name the framework's boxes: right from Black Mage,
  Time Mage or Summoner goes to the first column's box at that height (until now it
  went round to Archer, Monk or Thief), left from the first column comes back. The
  framework reads no key itself.
- **The view**: the layer that holds the game's boxes and lines is moved left 1,400
  for the first four columns and 1,360 more for each four after, a part of the way
  each frame; the stone board is another box and stays. As the tree comes up on a
  unit in one of the mods' jobs it is put there at once, the cursor on that job.
  (The sketch moved it 1,160; at that the fourth column's name board would pass the
  screen's edge.)
- **The mouse** reaches the boxes on screen; the keys move the view.
- **Only where the framework's own rows of the job screen are made** and every place
  of the tree is found in the program. Otherwise Job Progress is the game's.
- The log, once, as the boxes are first made: "Job Progress shows the mods' jobs in
  columns to the right of the game's tree: move right past Black Mage, Time Mage or
  Summoner and the view slides over to them." Where they can't be: "Job Progress
  doesn't show the mods' jobs: {why}. The job screen's own rows show them as
  before." A job with no slot free: "{job} has no figure on Job Progress: none of
  the figures' places the framework takes its own from was free."
- Rehearsed (`dev/test_jobs.py`, "(1.49.0 ...)", 22 checks; the measure held to his
  program's bytes by `dev/research/sidequests/job_boxes.py`): the plan; the boxes,
  the giving, the slots and what can't be made, over a stand-in for the tree
  (`helper/Checks/TreeChecks.cs`); the filling run again over the stand-in screen;
  **his program's own update run over each tree the framework would run it over**,
  every direction from each of the sixteen test jobs' boxes and from the game's
  three rightmost; the filling's three changed calls run in his program's own code.
  **What could not be run here**: everything the game's layout code does with the
  copies. Only his test shows it.
- **Not in this helper**: the lines between new jobs and the small icons of the
  game's jobs a new job needs (the tree's last step: 1.50.0, above).

**1.48.0: what opens a job** (test 111, `make_test111.py`, `Job_Test_111.zip`:
test 110's two mods, the first 1.9.0 and the second 1.2.0, six of their sixteen jobs
given Needs; and this helper). The first of the four steps of the Job Tree's build
(his order of 13 November; `claude/job-tree-research.md`). Until now a mod's job was
open to every unit: what opens one of the game's jobs is a table inside the program
that a mod's job isn't in.

- **A job's file may give `Needs`**: a list of up to 6, each with a `Job` (one of the
  game's generic jobs, 74 to 93, or the `Name` of another job of the same mod) and a
  `Level` (1 to 8). Left out, or null, is none: the job is open to every unit, as
  before.

  ```json
  "Needs": [ { "Job": 76, "Level": 3 }, { "Job": "Battlemage", "Level": 2 } ]
  ```

- **A file whose Needs aren't such a list leaves the job out, said**: "its Needs
  {aren't a list | are {n} | hold something that isn't a Job with a Level | ask the
  level {x} | name the job {x} | name the job itself | name {x} twice}: a list of up
  to 6, each with a Job (one of the game's generic jobs, 74 to 93, or the Name of
  another job of this mod) and a Level (1 to 8)". Between a mod's jobs: "{mod}'s job
  {Name}: its Needs name {x}, which isn't a job this mod gives", and "{mod}'s job
  {Name}: its Needs go round in a ring (a job it needs needs it in turn)"; a job that
  needed one taken out so goes too. A needed job of the mod's that has no number here
  (it was left out: the free numbers ran out, say): "{job} can't be opened by any unit: it needs {x}, a job
  of its mod that isn't given here."
- **The framework tests it itself** (`JobNeeds.Plan.Open`): a job is open to a unit
  that has every needed job open and at the level asked or more. The game's jobs are
  read from the unit's menu record as the game keeps them (its opened jobs' bits at +
  0x78, its levels' nibbles at + 0xBD); a mod's own needed job is tested the same way
  in turn, its level from the unit's progress in it (`JobProgress.Level`). **The job
  a unit is in is always open to that unit.** No rule of a man's or a woman's job is
  added: a need of the Bard is a need only a man can meet, of the Dancer only a
  woman.
- **On the job screen's own rows** (`JobScreen.Listed`) a job that isn't open to the
  unit gets the game's own mark: locked (0x4000) where another unit of the party has
  it open, not to be seen (0x2000) where none has. Everything after that is the
  game's: the place's record, its look, "???" for a name, and confirm opening the
  window of what the job needs.
- **The window of what a job needs** (the game's `0x1321FC`) reads the game table
  GeneralJob by the job's slot, and finds each needed job among the 19 places on
  screen. Three things are given it:
  - **GeneralJob gets a row for each mod's job** as it loads (key 0x100 plus the
    job's number, past the game's 0 to 21): the JP each level needs (the game's
    own list), its needs with their levels, no place on Job Progress yet. A row
    another mod already has at a key is kept, said.
  - **Two calls in the window** (`0x132255`, `0x1323CC`: a job's slot asked) go to
    code of the framework's that answers 0x100 plus the number for a mod's job and
    the game's own answer for any other.
  - **The window's one call** (`0x12FDE9`) goes through `JobScreen.Needs`: where a
    needed job isn't on one of the places shown, the 19 records are, for that call
    alone, the cursor's own and one for each needed job (its name and icon from the
    Job table, the unit's level, whether it is open), and are put back as they were
    after it. This also puts right the game's own third row's jobs while the rows
    are scrolled down (a needed job on a row not shown had its level alone).
- **A job that isn't open to a unit isn't offered to it**: its skillset in the list
  of second skillsets (the list's one call, `0x28A71D`, keeps the unit's record
  number for it) and its reaction, support and movement abilities. Both ask the
  framework (`open`, every register kept but rax).
- **Only where the framework's own rows of the job screen are made.** With Dark
  Knight & Onion Knight (Generic) showing the jobs on its page, or the job screen
  not found, nothing is asked and every unit has every one of the mods' jobs open,
  said.
- The log, as the game starts: "what opens a job: {n} of the mods' {m} jobs need
  other jobs first; a unit sees such a job locked on the job screen until it has
  them, and the window there says what is missing."; as the tables load:
  "GeneralJob: the mods' jobs' needs' {n} rows written." A table that can't be
  given its rows: "GeneralJob gets no rows: {why}. The window of what a locked job
  needs shows nothing for the mods' jobs."
- Rehearsed in his program's own code (`dev/test_jobs.py`, "(1.48.0 ...)", 26
  checks; the measure held to its bytes by `dev/research/sidequests/job_needs.py`):
  the window run whole with GeneralJob set up by the game's own setup and the
  framework's rows, the Mime's the same as the unchanged game's over the same
  records, a mod's job's needs found with one of its mod's own among them; both
  lists with a job open and not, every kept register kept whatever the framework's
  function loses (the six xmm registers too), each asking made with the stack 16
  bytes aligned; the two changed calls; the native code inside its room with 58
  jobs.
- **Test 111 passed** (13 November, 12:15): "Test 111 was a complete success and functioned how you said it would." For
  Aerith, Skirmisher, Lancer and Warden are black figures with no name, and
  Battlemage, Brawler and Sage are open; the Level Requirements window shows
  Lancer's Dragoon (Lv. 5, her Lv. 1 in red), Warden's Sage and Geomancer
  (Geomancer with its icon and name though its row isn't on screen) and
  Skirmisher's Thief, Monk and Battlemage (with Battlemage's own icon); in a
  party that only knows Squire and Chemist, Sage's window shows them at Lv. 1
  in red and four rows of the question mark, "???" and "Locked". The log's two
  lines, with 6 of 16 jobs and 16 rows.
- **Job Progress (the tree) is not changed by this helper**: the mods' jobs aren't
  on it yet. The boxes and the cursor are 1.49.0 (above); the lines are after.
- **Combat Sets** still show a set with a mod's job as usable whatever the unit's
  levels (the stand in of 1.37.2); left as it is for now.

**1.47.0: a job's own words on Job Summary** (test 110, `make_test110.py`,
`Job_Test_110.zip`: test 109's two mods, the first 1.8.0 with Battlemage's file
giving a Summary; and this helper). His order of 13 November: "the Job Tree and Job
Summary for our new jobs". Job Summary (the job screen's Y: Job Overview, Usable
Equipment, Select Abilities and the rest) is one text, a row of the game table
UiJobAbilityHelp that the job's row of the Job table names. A mod's job's row was
the row of the game's job it looks like, so Job Summary showed that job's words (a
Battlemage the Knight's). His word on a job whose file gives no words of its own:
"Its own description (Recommended)".

- **A job's file's `Words` may give a `Summary`**: the whole text as the game shows
  it, 1 to 4,000 characters, line breaks allowed and no other control character;
  left out, or null, is none. The game's own marks work in it (a heading as the
  game's: `<color=abilityhint_cap_01><icon=104>Job Overview</color>`). A Summary
  that isn't such text leaves the job out, said: "its Words' Summary is {value}, not
  text of 1 to 4000 characters".
- **Every mod's job's Job row names a row of its own** in UiJobAbilityHelp (key
  0x10000 plus the job's number, far past the game's 0 to 34 and the other mods'
  40), and the table is given that row as it loads: the job's Summary, or its
  Description under the heading the loaded language's first two jobs share ("Job
  Overview" in English; where they share none, as in French, whose headings name
  each job, the Description alone). Each line of the Description starts with a
  space, as the game's own lines do.
- **No code of the game's is changed**: the job screen's two reads of the table
  (`0x130792`, `0x13088E`) find the row by the key the Job row gives them. A row
  another mod already has at a key is kept, said ("{mod}'s {job}'s Job Summary
  keeps the row another mod gives it ({key})."); a table that isn't one of one key
  gets none, said ("UiJobAbilityHelp gets no rows: {why}. The mods' jobs show no
  words of their own on Job Summary.").
- The log, as the tables load: "UiJobAbilityHelp: the mods' jobs' Job Summary
  words' {n} rows written."
- Rehearsed in his program's own code: the tables set up by the game's own setup
  with the jobs' rows, both of the job screen's reads run to the text box's call
  (a mod's job's own words handed to it, the game's jobs' their own); over the
  game's tables, the other mod's English and French tables and WotL Restoration's;
  test 110's package from its zip.
- **Test 110 passed** (13 November, 02:13): "Test 110 was a complete success and
  functioned how you said it would." Battlemage's own words on both pages of its
  summary; Skirmisher and Brawler each their Description under Job Overview; the
  Knight as the game has it; the log's line with 16 rows.
- **The Job Tree (Job Progress) is not in this helper.** It is measured and its
  design signed off (`claude/job-tree-research.md`): what opens a job is a table
  inside the program that a mod's job isn't in, so a mod's job stays open to every
  unit until the framework keeps and tests its requirements itself (the next
  build).

**1.46.0: a job's own icons and pictures** (test 109, `make_test109.py`,
`Job_Test_109.zip`: test 108's two mods, the first 1.7.0 with Battlemage giving
its own icon, skillset icon and pictures, and Skirmisher the game's icons, a man's
picture of its own and no woman's art; and this helper). The road's step 5, its
third part (his pick of 11 November, "Job screen picture and icons"). A job's art is
four pictures the game names from its tables: its icon (the Job row's
TexturePartsIndex, a number printed into `j_%03d_uitx`), its skillset's icon (the
JobCommand row's IconId, printed into `jc_%03d_uitx`), and its two job screen
pictures, a man's and a woman's (its jobtype+Id names a JobType row whose two keys
name rows of the Icon table). The job screen shows those pictures only for the
game's 20 generic jobs, so a mod's job showed none there, and its Like's on the
equipment screen and in Combat Sets. His word (12 November, his second on it): "The
modder can pick either their own files or one of the game's for the job icon and
skillset icon but not for the man art or woman art. The modder should be able to
choose their own art for male and or female or no art for the male and or female.";
and where a job has no art of its own, "No picture there either".

- **A job's file can pick its two icons**: `"Icon"` (74 to 93, the generic job whose
  icon it shows, or the name of a part list in its mod at
  `FFTIVC/data/enhanced/ui/ffto/icon/job/textureparts/`) and its Skillset's
  `"Icon"` (5 to 24, the skillset whose icon it shows, or a part list at
  `.../icon/job_comm/textureparts/`). One not picked is its Like's, as before.
- **And give its two pictures**: `"Pictures": {"Man": ..., "Woman": ...}`, each a
  part list at `.../icon/job_visual/textureparts/` or none (left out, or null). A sex
  with no art shows no picture anywhere: the job screen, the equipment screen, Combat
  Sets. A part list is laid out as the game's (one part, the whole sheet) and names
  its texture; the game reads both through the mod loader.
- **The game's icons a job picks are its rows only**: its Job row's
  TexturePartsIndex and its skillset's JobCommand row's IconId are the picked one's.
- **Its own icon and its skillset's own icon are numbered as the job**: three hooks
  name its part lists for that number, on the icon routine (`0x29B054`: through the
  game's box loader, `0x29BC00`, as the routine calls it), on the skillset icon's
  name routine (`0xFBF30`) and at the start of the skillset icon routine (`0xFBF9C`,
  by the skillset: its bound would turn the number into the empty icon). Made only
  where a job gives an icon of its own.
- **Every job's pictures are answered at the picture routine** (`0xFBEB8`, its hook
  made wherever a mod gives a job): after the game's answer, its own picture's key
  (0x10000 and twice the job, the woman's the next), shown on the job screen as the
  game shows its generic jobs', with a row of the Icon table for each such key as the
  table loads (its path the job's own part list; a row another mod gives at a key is
  kept, said); or 0 for no art, which the game shows nowhere. Its jobtype+Id stays
  its Like's: the game also takes two jobs as the same job, clears the units' "new"
  marks and tells a Chemist by it.
- Each routine is found by a call of it, and taken where the game's program file
  has it if another mod hooks it (as 1.44.2's).
- New in the log: the job's line ends with what it shows ("It shows its own icon,
  its skillset's own icon and pictures of its own.", "It shows the game's job 87's
  icon, the game's skillset 18's icon and the man's picture of its own.", "It shows
  the game's job 74's icon, its skillset's own icon and the woman's picture of its
  own."); "Icon: the mods' jobs' own pictures' {n} rows written."; once each, "the
  game was given a job's own icon for the first time ({mod}'s {job})." (and "skillset
  icon", "man's picture", "woman's picture"); where they can't be given, "the jobs'
  own icons and pictures can't be given: {why}. A job with an icon of its own shows
  its Like's and a skillset with an icon of its own its Like's; the game's icons a job
  picks are still shown. Each job's pictures are as they were before: none on the job
  screen, its Like's elsewhere." ({why}: "a call of the picture routine (0 places like
  it, not 1) wasn't found in {program}. A game update may have changed it: look for a
  newer Mod Studio Framework", and the like for the icon routine, the skillset icon's
  name routine, the skillset icon routine and the box loader; or "their hooks
  couldn't be made ({kind}: {message})"); "Icon gets no rows: {why}. The jobs with
  pictures of their own show none."; "a job's own picture couldn't be given
  ({error}).", "a job's own icon couldn't be given ({error}).", "a job's skillset's
  own icon couldn't be named ({error})." (each said once). A job's file's faults:
  "its Icon is {value}, not one of the game's generic jobs whose icon it shows (74 to
  93) or the name of its own icon's part list (1 to 64 letters, digits and _)", "its
  Skillset's Icon is {value}, not one of the game's skillsets whose icon it shows (5
  to 24) or ...", "its Pictures' {Man or Woman} is {value}, not the name of its own
  picture's part list (1 to 64 letters, digits and _)", "its {which}, {name}, isn't
  in its mod's folder ({folder}/{name}.utexpt)", "its Pictures isn't a list of fields
  with a Man's or a Woman's picture".
- Only the Enhanced look (his word).
- Rehearsed in his program's own code: the tables with the jobs' rows read by the
  game's own setup and getters, the picture routine whole, where a picture is set
  and the image box's reads for the row as the hook leaves it, the icon's and the
  skillset icon's numbers on their way to the routines that name them; test 109's
  package from its zip.
- **Test 109 passed** (12 November, 21:50): "The test was a complete success and
  functioned how you said it would." Battlemage's own icon, skillset icon and
  pictures on the job screen, the status screen's job panel and Combat Sets;
  Skirmisher with the Dragoon's icon, its man's picture and no woman's picture.

**1.45.1: a job's own portraits on the big cards too** (test 107,
`make_test107.py`, `Job_Test_107.zip`: test 106's two mods as they were, and
this helper). His test 106: "The portrait for the male and female battlemage
is empty", the faces showing in the formation's list and the battle's turn
list but not in the big cards: the job screen's at the top left, the
formation's and the battle's at the bottom right. His log named the first of
the job's own portraits given only when the formation opened.

- **The cards in a battle** are written by four routines; two of them read the
  graphics slots' numbers themselves and bounded them at 205 before handing
  them to the card (`0x228778` and its twin `0x2DF374`, the same fourteen
  bytes at `0x229A50` and `0x2E065A`, found by them twice). A call of the
  framework's code in their place keeps a number of the framework's (256 to
  340) with its offset into the older drawing's face sprites 0, as for none;
  every other number as the game's.
- **The cards outside a battle** (the job screen, the status screen, the party
  list) come through the face routine's way for the party's units, which asks
  a portrait routine (`0x32AB3C`) that takes a face word with bit 8 or 9 set as
  no face at all: every face of the framework's has bit 8 set, so the card had
  no number and no colors. A call of the framework's code in place of that
  test (`0x32AC46`) answers a face of the framework's with itself and writes
  its colors as the game's own routine writes them; any other word is tested
  as the game's.
- New in the log, where they aren't found: "the bounds of a battle's unit
  cards ({n} places like them, not 2)", "the test of the party's faces ({n}
  places like it, not 1)" or "the test of the party's faces (it isn't the
  game's)", in the line "the jobs' own portraits can't be given: ...". Each
  job then keeps its Look's portraits.
- Rehearsed in his program's own code: both card routines from the slots'
  table through their bound for every number and face; the portrait routine
  whole for a unit of the roster; the face routine whole for one (a Battlemage
  man 256, a woman 257, in the first team's colors; every generic job as the
  game's); test 107's package from its zip.
- **Test 107 passed** (12 November, 17:10): "Test 107 was a success and
  functioned how you said it would." The faces on every card. His one note, a
  line across the talking face where its eyes' part and its mouth's part meet,
  was the test's own faces' (cut at one row, black under the see through
  pixels); test 108 makes them as the game's own are, with Mod Studio's
  portrait seam fix, the helper as it was: passed (17:24, "They are now
  talking and blinking perfectly").

**1.45.0: a job's own portraits** (test 106, `make_test106.py`,
`Job_Test_106.zip`: test 105's two mods, the first 1.6.0 with Battlemage given
portraits of its own, and this helper). The road's step 5, its second part,
the last in his order. He sent the game's faces to read their format: a sheet
of 520 by 388 for each portrait and team color, its part list naming nine
parts (the sheet, three eye frames, four mouth frames, the whole face).

- **A job's file's Look can give its own portraits**: `"Portraits": {"Man":
  [...], "Woman": [...]}`, either or both, each 1 to 5 names of part lists in
  the job's mod at `FFTIVC/data/enhanced/ui/ffto/common/face/textureparts/`
  (one a team's colors, the first the player's team's), laid out as the
  game's faces and naming their textures. The game reads them itself, through
  the mod loader.
- **Each of the job's own sprites so given has a portrait number of the
  framework's**: its sprite's plus 86 (256 to 340), past the game's 205 and
  the numbers other mods use. Its face word names that number; the face to
  portrait routine answers such a face with itself (a call of the framework's
  code in place of its first two instructions, WotL Restoration's bytes left
  as they are); its graphics slot's number is that number; the six bounds at
  205 on the way to the Enhanced look are widened to 340 (three in place,
  three held in a register whose switch answer is made from another so face
  0xCD stays 205).
- **A hook on the face's file's routine** (`0xFC22C`, found by a call of it,
  taken where the game's program file has it if another mod hooks it) names
  the job's own part list for such a number, the one of the team's colors
  (the first where the job gives fewer). Every other number is the game's own
  routine's.
- New in the log: the job's line ends "... and portraits of their own." (or
  ", with the man's portraits of its own", or the woman's); once, "the game
  was given a job's own portrait for the first time (Test 74 New Job's
  Battlemage, the man's first portrait)."; where it can't be done, "the jobs'
  own portraits can't be given: {why}. Each job with portraits of its own has
  its Look's." A job's file's faults: a Portraits that isn't a list of fields,
  a list not of 1 to 5 names, a name not of 1 to 64 letters, digits and _, a
  part list not in the job's mod.
- Only the Enhanced look (his word): in the Classic look a job's own portrait
  is none or another's.
- **Test 106** (12 November, 16:11): the faces in the formation's list and the
  battle's turn list, none in the big cards (1.45.1).

**1.44.2: hooked routines taken where the game's program file has them**
(test 105, `make_test105.py`, `Job_Test_105.zip`: test 104's two mods as they
were, and this helper). His test 104: "Their texture did not change", and the
man red in the menus and purple in battle (his own colors under the battle's
blue light: settled). His log: "the jobs' own textures can't be used: the
textures' opening of an entry (the place the call names starts as neither the
routine nor a jump), ..."; the mod loader's own lines in it name the routines
it hooks, the same two. Its hooks start with a jump of a kind 1.44.1 didn't
take.

- **A routine the calls name is taken where its own first bytes are**: in the
  game as it runs or, whatever another mod's hook starts with there, in the
  game's program file at the same place (`ProgramFile.cs`: each section's
  bytes read from the file's own place for it; the file's path from the
  game's process). The framework's hook is then made in front of the other
  mod's, as Reloaded-II's shared hooks stack them.
- **A hook that can't be made** turns both off and is said ("the jobs' own
  textures can't be used: their hooks couldn't be made (...)"); the jobs are
  added as they are.
- **Once in all**, the first time the game is given one of the jobs' own
  textures: "the game was given a job's own texture for the first time (Test
  74 New Job's Battlemage, the man's upper texture)."
- New in the log, where a routine can't be taken: "the textures' opening of
  an entry (the place the call names isn't the routine as the game runs, and
  the game's program file couldn't be read to see whether another mod has
  hooked it there)" or "... (the place the call names isn't the routine, as
  the game runs or in the game's program file)".
- Rehearsed: the routines found past near and far jumps, a far jump through a
  pointer, a push and return and jumps through a register, each with his
  program's file beside; with no file, and with a file whose routine differs,
  said; the file read at each section's own place; test 105's package, and
  its zip over his numbers over a program hooked as the mod loader's.
- **Test 105 passed** (12 November, 13:41): "The texture changed as you said
  it would." His log had the first line ("the game was given a job's own
  texture for the first time (Test 74 New Job's Battlemage, the man's upper
  texture).") and no "can't be used" line; his screenshots showed each
  Battlemage a checkered box on the job screen (its preview and its cell in
  the grid), in the formation and in battle.

**1.44.1: a job's own textures found by their calls** (test 104,
`make_test104.py`, `Job_Test_104.zip`: test 103's two mods, the first 1.5.0
with Battlemage's man in shades of red, and this helper). His test 103: "The
texture did not change"; his log: "the jobs' own textures can't be used: the
textures' opening of an entry (0 places like it, not 1), the textures'
unpacking of an entry (0 places like it, not 1) wasn't found". In the running
game the mod loader has hooked both routines (it serves its `tex_N.bin`
through them), so their first bytes are its jumps.

- **The routines are found by the menus' figures' calls of them** (`0xCE31F`,
  found once: the opening's, the unpacking's and the closing's calls), each
  taken where it starts as the game's routine or with another mod's hook's
  jump. Reloaded-II's shared hooks stack the framework's hook on the mod
  loader's; the framework's, made later, is asked first.
- New in the log, where they can't be found: "the menus' read of a texture (0
  places like it, not 1)", "the textures' opening of an entry (the place the
  call names starts as neither the routine nor a jump)".
- Rehearsed: the routines found the same in a program whose two starts carry a
  near and a far jump, one starting as neither said, test 104's package from
  its zip, over that program too.
- **Test 104** (12 November): the man red in the menus and purple in battle,
  his own colors (settled). The textures didn't change: the mod loader's
  hooks start with a jump of another kind, and neither routine was taken
  (1.44.2).

**1.44.0: a job's own textures** (test 103, `make_test103.py`,
`Job_Test_103.zip`: test 102's two mods, Battlemage given textures of its
own, and this helper). The road's step 5, its second part, next in his order
after the colors.

- **A job's file's Look can give its own textures**: `"Textures": {"Man":
  ["upper", "lower"], "Woman": [...]}`, either or both, each two names of
  files in the job's folder, its upper texture and its lower, as g2d.dat
  keeps a sprite's: 4 bits a pixel, 512 pixels wide, the left pixel in a
  byte's low four bits; the upper 512 rows (131,072 bytes), the lower 1 to
  512 rows (the game's own 464, 118,784 bytes; other mods' `tex_N.bin` 512).
  Drawn for its Like's frames, colored by its colors (its own or its
  Look's).
- **How the game reads a sprite's textures**: the sprites' table names its
  upper texture's g2d.dat entry, its lower is the next. The menus' figures
  (`0xCE204`), the textures as they are drawn (`0x415D30`) and the screens'
  (`0x41E05C`) each open one entry (`0x3D2450`, by the file's own index; its
  count is never asked), unpack it into their memory (`0x3D25D8`) and close
  (`0x3D25A4`).
- **The framework's part**: each of the job's own sprites with textures of
  its own is given two entries of the framework's (from 0x4000, far past
  the file's 2,450), named in the sprites' table in place of its Look's; two
  hooks answer them: the opening of one of them opens nothing and says it
  did, the unpacking copies the job's texture and says how many bytes.
  Every other entry and file is the game's own routine's. No change of the
  game's code. Where the routines aren't found, said, and the job wears its
  Look's textures.
- Rehearsed in his program: the menus' figures' read run in the game's own
  code (a job's own sprite's entries opened alone, unpacked and closed,
  given its texture; any other sprite's the game's), the battle's figure's
  entries, the sprites' table and its Sync, the job file's faults, test
  103's package over his numbers and from its zip.
- New in the log: the job's line says "... which use textures of their own"
  (or "the game's job 78's textures, the man's textures of its own", or the
  woman's); where the routines aren't found, "the jobs' own textures can't
  be used: the textures' opening of an entry (0 places like it, not 1)
  wasn't found in FFT_enhanced.exe. A game update may have changed it: look
  for a newer Mod Studio Framework. Each job with textures of its own wears
  its Look's." A job's file's faults: "its Look's Textures isn't a list of
  fields with a Man's or a Woman's textures", "its Look's Textures' Man isn't
  a list of two file names (its upper texture's and its lower texture's)",
  "its Look's Textures' Man's upper texture is "../up.bin", not the name of a
  file in the job's folder", "..., gone.bin, isn't in the job's folder",
  "... is 131,071 bytes, not 131,072 (512 by 512 pixels at 4 bits a pixel)",
  "its Look's Textures' Man's lower texture, low.bin, is 300 bytes, not 512
  pixels wide at 4 bits a pixel with 1 to 512 rows (the game's own are
  118,784 bytes)".
- **Test 103** (12 November): each Battlemage in a checkerboard made up for
  the test, in its own colors. The textures didn't change: the routines
  weren't found in his running game (1.44.1).

**1.43.0: a job's own colors** (test 102, `make_test102.py`,
`Job_Test_102.zip`: test 101's two mods, Battlemage given colors of its own,
and this helper). The road's step 5, its second part, a mod's own art; his
order of it (12 November): "Colors first", then the sprites' textures, then
the portraits, a test each.

- **A job's file's Look can give its own colors**: `"Colors": {"Man":
  [...], "Woman": [...]}`, either or both, each a list of 1 to 5 palettes in
  the order the game keeps a figure's (the first the player's team's), each
  16 colors written "#RRGGBB", the first "#000000" (see through). A palette
  not given keeps its Look's colors, as do the portraits.
- **How the game colors a figure**: both routes, the menus' (`0x26E750`)
  and the battle's (`0x26E838`), copy its 16 palettes from its classic file
  and hand its sprite to one routine (`0x26C7AC`). Where the sprite's
  CharShape row names a CharCLUT number (+0xC), the game table **CharCLUT**
  (sheet 0xD2, two keys: that number and a palette's; 16 colors of red,
  green and blue a row, used when +0x14 isn't 0) is written over the
  palettes its rows name, as colors of 15 bits (`0x26C530`): how the game colors
  Ramza's three looks.
- **The framework's part**: a job's own sprites' CharShape rows name a
  CharCLUT number of their own (the sprite's own number) where that sex has
  colors, and CharCLUT gets a row for each palette as it loads
  (`SpriteRoom.WithClutRows`, from the jobs' hook of the tables' setup, only
  with a job with sprites and colors of its own). A row another mod has
  there is kept, said. No change of the game's code.
- Rehearsed in his program: the coloring of every sprite 0 to 255 run in the
  game's own code with CharShape and CharCLUT kept as the game keeps them
  (the game's tables color only Ramza's; the helper's the jobs' own sprites
  too, every other palette as handed), the tables read by the game's own
  setup and lookups, the job file's faults, test 102's package over his
  numbers.
- New in the log: the job's line ends "... which use the game's job 78's
  textures in colors of its own." (or ", the man's in colors of its own." or
  ", the woman's ..."); "CharCLUT: the mods' jobs' own colors' 2 rows
  written."; where another mod has a row there, "Mod S's Battlemage's sprite
  171 keeps the CharCLUT row another mod gives its first palette."; where the
  table can't be given them, "CharCLUT gets no rows: it isn't a table of two
  keys (byte 8: 1). The jobs with colors of their own wear their Look's
  colors instead." A job's file's faults: "its Look's Colors isn't a list of
  fields with a Man's or a Woman's palettes", "its Look's Colors' Man isn't a
  list of 1 to 5 palettes", "its Look's Colors' Man's second palette isn't a
  list of 16 colors", "... has "#12345", not a color written "#RRGGBB"", "...
  starts with a color that isn't "#000000" (the first color is
  see through)".
- One more thing the game does with a CharCLUT number: as a save loads or a
  battle starts again (`0x1009E8`), a figure whose sprite names one wears the
  palette its first row's color skin gives (0 for none): for the party's
  units the palette they wear. For a unit of another team in a mod's job
  (jobs in a quest's battle, a later step) it would be the player's colors
  after a load; to be measured then.
- **Test 102 passed** (12 November): the log's lines as rehearsed; the party
  menu, the job screen's figures and its grid's small figure, the battle's
  formation and the battle, each Battlemage in its own colors. (His battle
  screenshots were first read as the man in the woman's colors; every unit
  of his team there, the game's own too, carried the same blue light, and
  with it taken away each Battlemage wears its own.) A grey screen entering
  a battle on one of his saves came with 1.42.2 too, not from the colors.

**1.42.2: a job's own sprites' colors and portraits in battle** (test 101,
`make_test101.py`, `Job_Test_101.zip`: test 99's two mods as they were, and
this helper). His test 100: "I can place them down now but what appears to
be the palette and portrait is incorrect", with two screenshots of the
formation: each Battlemage in other colors than a Monk's, and the panel's
portrait a story character's.

- **The battle colors a figure from the classic file its loader reads**
  (`0x26FB28`, by the classic files' tables at `0x26FD69` and `0x26FD5C`), in
  the Enhanced look too: the figure's palettes function (`0x26E838`, called
  with the loaded file at `0x26EF81`) copies the file's first 512 bytes into
  the figure's graphics slot. For a job's own sprites those rows were its
  Like's (the Knight's file) while its sheets were its Look's. **They are its
  Look's now**, as the palettes' copy the menus read (`0x26E750`) already
  was; its attributes stay its Like's (the same frames).
- **The battle's panels show the graphics slot's sprite as the portrait**:
  the same function keeps each slot's sprite in a table of ten (`0x37A59E0`,
  two writes), and ten readers take it as the unit's portrait (a generic's
  numbered as its sprite; 170 and 171 are the game's own portraits of
  others). **At both writes the framework's code writes a job's own sprite as
  its Look's** (a woman's the woman's), every other as it is: the fourth and
  fifth of the places the sprites take, each a call, held to its bytes as
  measured (the write names the table in four bytes its pattern leaves open).
- Rehearsed in his program: the write run alone at both places for every
  sprite 0 to 255 (a job's own written as its Look's, the rest as the game
  writes them, every register but ecx as the game's), the classic files'
  rows, a program whose write names another table (said, and no job is given
  sprites of its own), test 101's package.
- Only the Enhanced look is supported (his word, 12 November).

**1.42.1: a job's own sprites on the battlefield** (test 100,
`make_test100.py`, `Job_Test_100.zip`: test 99's two mods as they were, and
this helper). His test 99: the party menu, the portraits with their talking
and blinking frames, and the job screen's figures showed Battlemage as a
Monk; putting it on a tile in the battle's formation stopped the game, and
Windows's record of it named an access violation at `0x217172` of his
program. And his word the same night: "I do not want to support classic
mode only Enhanced."

- **One more table is keyed by a sprite**, a game table: CharShape (sheet
  0xAE), a row for each of the game's sprites (0 to 158; WotL Restoration's
  0 to 169 and Dark Knight & Onion Knight (Generic)'s 0 to 162, each adding
  rows for its own): a unit's height above the ground (+0x2C) and its
  shadow, colors and light as rows of other tables. Twelve places get it to
  find a sprite's row; five read the row with no test for none (`0x217172`,
  `0x221AB9`, `0x26456E`, `0x2648C6`, `0x264CE9`; a sixth, `0x21714B`, its
  +0x2F the same way). The first is in the function that shows a unit on
  the battlefield: for Battlemage's sprite 170 it read the height of no row.
- **Each job's own sprite is given a row as the table loads**
  (`SpriteRoom.WithShapeRows`, from the jobs' hook of the tables' setup): its
  Look's sprite's row, a woman's the woman's, its Comment empty. A row
  another mod already has at that number is kept, said. A table found by its
  rows' places whose keys no longer follow on is searched by key, as
  `Nxd.WithRows` has done since 1.5.0.
- Rehearsed in his program (`dev/test_jobs.py`): the game's own setup and
  lookup find the new rows in the game's table, the other mod's and WotL
  Restoration's, every row they had as it was; the crash's stretch, run with
  the game's table, faults at `0x217172` as his did, and with the
  framework's reads the Monk's height and goes on.
- New in the log: "CharShape: the mods' jobs' own sprites' 2 rows
  written."; where another mod has a row there, "Mod S's Battlemage's sprite
  171 keeps the CharShape row another mod gives it."; where the table can't
  be given them, "CharShape gets no rows: it has no row for the game's
  sprite 104, which Mod S's Battlemage looks like. Putting a unit of a job
  with its own sprites on the battlefield stops the game."

**1.42.0: a job's own sprites** (test 99, `make_test99.py`,
`Job_Test_99.zip`). The road's step 5, its first part. His word on test 98:
"Continue on. I believe Sprites are next on our list for new Jobs"; his
picks for the step, built in this order: battle sprite and faces, the job
screen's picture and icons, its own colors; not the Classic look (there a
mod's job shows the job it is like).

- **A job's file can name a look of its own**: `"Look": {"Like": 74 to
  93}`, the game's generic job whose look it wears. It must be drawn for the
  same frames as the job's Like (the sprite's attributes' first two bytes),
  or the job keeps its Like's look and the log says so.
- **Two sprite numbers a job** (`Numbers.json`'s `Sprites`, kept for good):
  a man's (even) and the woman's after it, past the game's 169, below 255,
  not 202 to 209 (the game keeps faces for 203 to 209): 38 pairs. The
  routines that make a sprite from a job (the sprite set, the five
  portraits', the face's, the job screen's cell) are handed a job number of
  the framework's that makes them make those two ((sprite + 0x34) / 2, 111
  to 126 and 131 to 152); the atlas of units the Look's place.
- **The tables of what a sprite looks like made longer** (`SpriteRoom`,
  its places written by `make_sprite_sites.py` into `SpriteRoomSites.cs`):
  14 tables of 255 rows in memory near the program, after the jobs' cells
  (and the longer job records, where made): the attributes, the classic
  files (two copies: the classic look's and the palettes' the Enhanced
  sheets are drawn with), the big monsters' second classic files, the
  sheets, the second sheets, and five face words' tables. The game's rows as
  they are, the Squire's past them for numbers no job has, and each job's
  own two rows: its Like's where the classic look reads and where both
  looks read the same, its Look's where the Enhanced look reads and in its
  faces. The 44 instructions that name those tables name the same place in
  the longer ones, the 16 bounds of a sprite are widened, the two tests that
  sort a sprite as a generic's or a story unit's take 170 to 254 as a
  generic's, and the job screen's cell draws a job with its own sprites by
  its job. One place not found and no job has a look of its own.
- What others write to the game's own tables (WotL Restoration's portraits'
  faces) is brought over to the longer ones as the job records' is.
- New in the log, for a job with its own sprites: "Test 74 New Job's
  Battlemage is job 142, looking like the game's job 76, with its own
  skillset 77 and its own sprites 170 and 171, which use the game's job
  78's textures."; where its Look can't be used: "Mod S's Mismatch keeps the
  look of the game's job 76: the game's job 79's sprites have other frames,
  so its look can't be used." or "...: all 38 pairs of sprite numbers are
  given."; where a place isn't found: "the jobs' own looks can't be made:
  the sprites' test 3 (0 places like it, not 1) wasn't found in
  FFT_enhanced.exe. A game update may have changed it: look for a newer Mod
  Studio Framework. Each job looks like the game's job it is like."

**1.41.4: the units the game moves reach them through Arithmeticks too**
(test 98, `make_test98.py`, `Job_Test_98.zip`). His word on test 97: "a
complete success", and "all Arithmeticks should be able to use new
abilities as well just like we can now, enemies, charmed, or confused."

- **The units choose an Arithmeticks spell in two routines of their own**,
  both over the game's four skillsets (a table at `0x684E44`): the thinking
  one (`0x388EB4`), which kept the spell as its word's low byte (550,
  Mending Light, would have been 38, Float) and passed over a word whose
  low byte is 0; and the random one (`0x38BF34`, a unit acting at random),
  which picked one of the four by the game's random number and 3.
- **The framework's code there** (`JobRoom`, found apart; where either isn't
  found, the jobs and the player's list are made without it and the log
  says so): the thinking one goes through the framework's list of
  skillsets, keeps the whole word in a cell of the framework's (the game's
  byte as before) and reads it where it read the byte; the random one picks
  a skillset of the list at the random number less every whole multiple of
  the list's length, with 256 tries for each four of the list. Both pass
  over a word with no action record.
- New in the log: "Units the game moves choose Arithmeticks's spells from
  the mods' jobs' own skillsets too.", or where it isn't found, "Units the
  game moves can't choose Arithmeticks's spells from the mods' jobs' own
  skillsets: its thinking choice (n places like it, not 1) wasn't found in
  FFT_enhanced.exe. ..."

**1.41.3: Arithmeticks reaches the mods' jobs' own skillsets** (test 97,
`make_test97.py`, `Job_Test_97.zip`). His word on test 96: "a complete
success", and Flame Lance's and Mending Light's pages say "Castable with
Arithmeticks", but learned on his Arithmetician as a Battlemage neither was
in Arithmeticks's list of spells.

- **The battle's list of Arithmeticks's spells** (`0x30EA38`: the battle
  menu's, its twin's and the counter's of a skillset's entries) goes through
  four skillsets written in its own code (White, Black and Time Magicks and
  the Mystic Arts), lists what the unit learned of each and keeps each spell
  whose action record has the flag. A job's own skillset was not among them.
- **The framework's code there** (`JobRoom`, found apart from the jobs'
  places: where it isn't found the jobs are made without it and the log
  says so): the round's skillset read from a list of its own (the game's
  four, then each job's in the order the jobs are given); a spell kept only
  where it has an action record (a job's skillset may hold an item's, a
  jump's, a charge's or a throw's number, as test 86's Alchemist, Lancer,
  Marksman and Shade do, which has none: the game would have read its flag
  at address 5), has the flag, isn't in the list already (a game's spell,
  as Haste in Battle Magicks, may be learned in its own job too) and the
  list holds fewer than 64; as many rounds as skillsets.
- What follows a spell chosen was already the framework's (1.41.0 and
  1.41.2): the action's check, its setup with its own record and formula;
  Arithmeticks costs no MP.
- The units the game moves choose an Arithmeticks spell from the game's four
  as before.
- New in the log: "Arithmeticks reaches the mods' jobs' own skillsets: a
  spell a unit has learned in one of them is in its list when it says
  Castable with Arithmeticks.", or where it isn't found, "Arithmeticks
  can't reach the mods' jobs' own skillsets: its list (n places like it, not
  1) wasn't found in FFT_enhanced.exe. ..."

**1.41.2: a mod's ability used in battle as itself** (test 96, `make_test96.py`,
`Job_Test_96.zip`). His word on test 95: in battle Mending Light (550, 4 MP)
said "Insufficient MP to use Mending Light" with 13 MP, the Combat Timeline
called it "Wind Anima", and Float was cast (its 50%, its 8 MP), then "Failed
to perform ability!".

- **The battle menu's confirm** (`0x237FA4`) made the chosen word of the
  menu's list (an ability's text code, 0x7000 and its number) the action's
  ability by keeping nine bits: 550 became 38, Float. The framework's code
  there (`AbilityRoom.MenuCut`): a word with the text code 0x7000 and a
  number from 549 to 1023 in its eleven bits gives that number; any other
  word is cut as the game cuts it.
- **Six compares more** (`abilities.py`'s `MISSED_COMPARES`, now in
  `COMPARE_SITES` and `AbilityRoom.Compares`, each taking a mod's ability
  for a plain action by the same code): three of "1 to 367" written as one
  less (`lea eax, [x - 1]` and 366, so the framework's edges are 548 and
  1022 there: `Less`), among them the battle menu's own list of each
  action's MP and charge time, which the "Insufficient MP" box reads; two
  on a register still holding 367 (the MP a charged ability costs, as it is
  done and as the action is set up: a mod's ability cost nothing); and the
  action's setup's own (`0x309CFF`), where a mod's ability had its formula
  made a weapon's.
- **The turn order**: 1.41.0 made a readied ability again from the turn
  order's low byte and past 255 flag with the unit's own word as the
  timeline is drawn; while the menu is open the game works the turn order
  out with the chosen action put in the unit and puts the unit's own back
  after. The writer itself is taken now (`AbilityRoom.Writer`): where it
  loads a unit's readied word it keeps the word in a table of the
  framework's (`TurnOrderAt`, a word for each of the 21 units), and the
  four places that make an entry's ability again read that table: the two
  of 1.41.0 and two more that make it a text code for the timeline's list
  (`AbilityRoom.Texts`).
- 83 changes of the program now (the code's 50). `test_jobs` runs each
  piece alone and the battle's own routines with test 94's package: the
  action's setup takes Mending Light's own record and Cure's formula, the
  MP paid as it is done is 4, the MP asked as it is set up is 4, and the
  menu's list gives the three their own MP and charge time.

## Building

With the .NET 8 SDK, offline, from Mod Studio's folder:

    python3 helper/build.py <Reloaded.Mod.Interfaces.dll> \
        <Reloaded.Hooks.Definitions.dll> <Reloaded.Hooks.ReloadedII.Interfaces.dll>

The first DLL is Reloaded-II's interfaces (GPL-3.0, Reloaded-II's own; not
copied beside the mod, as Reloaded-II brings it), from
`reloaded.mod.interfaces.2.5.0.nupkg` (a zip: `lib/netcoreapp3.1/`,
https://www.nuget.org/api/v2/package/Reloaded.Mod.Interfaces/2.5.0). The
other two (since 1.1.0) are Reloaded-II's shared hooks' interfaces
(LGPL-3.0: Mod Studio's `NOTICE.md`), from `reloaded.hooks.definitions.1.11.0.nupkg`
(`lib/net6.0/`) and `reloaded.sharedlib.hooks.1.9.0.nupkg`
(`lib/netstandard2.0/`): the versions WotL Restoration is built with, and
carried beside the helper as it carries them. The helper needs the
`reloaded.sharedlib.hooks` mod (its `ModConfig.json` names it, with where
Reloaded-II fetches it, as WotL Restoration's does) and (1.2.5) the mod
loader (`fftivc.utility.modloader`), which serves its files under
`FFTIVC/`. The build lands in `tools/ModStudioEventSetup/`, Mod Studio's
copy: `ModConfig.json`, `ModStudioEventSetup.dll`, its `.deps.json`,
`Preview.png` (Mod Studio's icon), the two hooks' interfaces, (1.2.5) the
side quests' marker's picture and its part list at the game's paths
(`FFTIVC/data/enhanced/ui/ffto/worldmap/texture/msq_quest_marker_uitx.tex`
and `.../textureparts/msq_quest_marker_uitx.utexpt`, from `helper/marker/`,
which `dev/research/sidequests/make_marker_picture.py` draws: since 1.2.6
to the game's quest pin's measures and shading, its inside see-through,
not copied from the game's picture), and the
licenses that go wherever they go: `NOTICE.md` (`helper/NOTICE.md`: the two DLLs, their versions and
sources, with LGPL-3.0's text as their package gives it) and `LICENSE`
(the GPL's, Mod Studio's own). It is deterministic: the same source makes
the same DLL byte for byte, which `dev/test_event_setup.py` checks of the
shipped one. Online, `dotnet build` in `helper/ModStudioEventSetup`
fetches the interfaces (2.4.0) from NuGet instead (delete
`helper/NuGet.config`, which turns package sources off for the offline
build).

The helper asks Reloaded-II for its interfaces at 2.4.0 or newer: what
Reloaded-II shipped from April 2023 until 1.30 (January 2026), and what
WotL Restoration asks for. A DLL built against 2.5.0 as it is asks for
2.5.0, and .NET won't load it in a Reloaded-II from before 1.30, so
`build.py` compiles against a copy of 2.5.0's DLL whose own version reads
2.4.0 (made in its scratch folder, never shipped; 2.4.0's DLL is compiled
against as it is). The helper uses nothing 2.5.0 added: its mod entry,
the loader's `GetLogger`, `GetActiveMods`, `ModLoaded`,
`OnModLoaderInitialized` and `GetDirectoryForModId`, the mod
configuration's `ModId` and `ModName`, and the logger's `WriteLine` and
`PrintMessage`. `dev/test_event_setup.py` checks that the shipped DLL asks
for 2.4.0, no newer than WotL Restoration's DLL does.

`helper/Checks` is Mod Studio's check of the helper's own code
(`dev/test_event_setup.py` and `dev/test_side_quests.py` build and run it):
the program's file laid out as it lies in memory, the table found, mods'
files applied to a copy, every byte changed reported; and mods' side
quests planned over the program and the tables as the game loads them
(WotL Restoration's copies), every number, record, script and row said.
The hooks themselves are seen only in the game. It doesn't ship.

## Its own release

Zodi's repository, https://github.com/Zodi-ark/Mod-Studio-Event-Setup (21
October: "I created the github page"; the helper's author "Mod Studio", as
he set it). Mods made with Mod Studio name where Reloaded-II fetches the
helper (`event_setup.HELPER_RELEASE`): a GitHub release of that repository,
by its tag, with release metadata
`fftivc.utility.modstudio.eventsetup.ReleaseMetadata.json` (and an
`AssetFileName` of `Mod.zip`, as WotL Restoration's `ModConfig.json` gives
two of its three dependencies); the helper's own `ModConfig.json`
names the same repository for its updates. 1.0.1 is published there (Zodi,
21 October's evening), 1.0.2 (the shorter found line) made on 22 October
for him to publish; 1.1.0 (the side quests) and 1.2.0 (their battles)
made on 26 October and sent with his tests 14 and 15, which played (the
world map's objective going back after them, fixed in 1.2.1); 1.2.1 (the
story kept) passed his test 16; 1.2.2 (the way kept open) played in his
test 17 but then stopped his game on the world map (its hook changed
registers the game's travel step keeps): never to be published; 1.2.3
keeps them, and 1.2.4 (a start's choice when a travel passes through)
passed his tests 18 and 19 ("No more crashing and both tests ran perfectly
as you described them"); 1.2.5 (markers) passed his test 20 ("Test 20 ran
perfectly and as you described"), his one nitpick the pin's dark inside;
1.2.6 (the pin redrawn to the game's) passed his test 21 ("Test 21 was a
complete success and the pin looks much better and closer to the
original"); 1.3.0 (a mod's own places, with 1.2.6's pin) drew them in his
test 22, but they answered the mouse as the places copied (never to be
published); 1.3.1 makes them pictures only and passed his test 23 ("Test
23 was a success and is how you described it to be"); 1.4.0 (a mod's
own roads, drawn) passed his test 24 ("Test 24 was a success and looks as
you described. It is great"), its log's one wrong line (no Route, said
before the roads were drawn) put right by 1.4.1, which passed his test 25
("Test 25 was a complete success": its log the seven lines, no more);
1.5.0 (the roads travelled, 1.4.1 within it) passed his test 26 ("Test 26
ran perfectly and as you described"); 1.6.0 (random battles on a mod's
road) passed his test 27 ("The test was a success and as you
described"); 1.7.0 (a mod's own place as a destination) passed his test 28
("Test 28 was a complete success and was exactly how you described even
the saving and loading"); 1.7.1 (the cursor's stop on a mod's place and a
save without its mod) passed his test 29 ("Test 29 was a complete success
and functioned exactly as you said it would"); 1.8.0 (side quests at a
mod's own place) passed his test 30 ("The test was a success and
functioned exactly as you said it would"); 1.9.0 (room for hundreds of
quests) played in his test 31 but sent a scene whose next event was past
1023 back to the world map (never to be published); 1.9.1 passed his test
32 ("The test was a success and functioned as you described it would");
1.10.0 (a quest's own maps) passed his test 33 ("Test 33 was a complete
success and ran as you described it would"); 1.11.0 (a copied scene's
doors) passed his test 36 ("Test 36 was a complete success and functioned
exactly as you described. Everything is correct."); 1.11.1 (a battle with
no scene of its own as it starts plays the game's battle start, test 37's
finding) goes to his test 38, and once it passes is the one to publish in
place of 1.11.0 (its question asked again by test 42); 1.12.0 (how a
battle is won and lost, and its objective) went to his test 39, which
played its objective and lost Delita's battle at once, his place an empty
unit (Mod Studio's copy had kept the game's Load Formation: not 1.12.0's
doing); 1.12.1 (such a unit refused, said) passed his test 40 ("Test 40
was a complete success"; never 1.12.0 alone: it would let a battle be lost
at once unsaid); 1.13.0 (the numbers kept three times, each save's mark)
passed his test 41 ("Test 41 was a success"); 1.14.0 (a battle's own
deploy areas) goes to his test 42, whose battle has no scene of its own as
it starts (test 38's question); 1.15.0 (tavern rumors) to his test 43;
1.16.0 (a place's description) to his test 44; 1.17.0 (a battle on a mod's
battle ground) to his test 45; 1.18.0 (a town's menu at a mod's town) to
his test 46; 1.19.0 (a town's own art in its menu) to his test 47; 1.20.0 (a
place darkened once its event is done) to his test 48; tests 42 to 48
passed (2 November: each "a complete success and functioned exactly as you
described", 45 "a mixed success", its two findings Mod Studio's: the deploy
area on a tile where an enemy stood, since refused on the page, and every
arrival starting a battle, as that test asked), so 1.20.0 was the one to
publish then, 1.11.1 to 1.19.0 within it; 1.21.0 (a dungeon like Midlight's
Deep) goes to his test 49; 1.22.0 (its new name, Mod Studio Framework, its
words saying "texture" where a texture is meant, and two modders' names
alike told apart in its log) to his tests 50 and 51; test 49 passed
(2 November: "success", its three findings: the dungeon's list showing
Midlight's Deep's words, a white flash before a floor's battle, and the
mods' places missing from the location list), each put right by 1.23.0,
which went to his test 52; tests 50 and 51 passed (2 November: "Test 50
and 51 ran perfectly as you described"); test 52 showed two things wrong
(under Settlements a mod's town's panel kept the last town's, and
travelling to Old Quarry, place 69, stopped the game), each put right by
1.23.1, which went to his test 53 (its panel right, Ramza standing on
Old Quarry; then choosing it stopped the game: the menu's name of its
place, a sprite of the same table), put right by 1.23.2, which passed his
test 54 (2 November: "Test 54 was a complete success"); 1.24.0 (a
dungeon's floors listed once the floor before is won, and its prompt
"Enter Old Quarry") passed his test 55 (2 November: "Test 55 was a
complete success and functioned exactly how you said it would"), so
1.24.0 was the one to publish then, 1.21.0 to 1.23.2 within it; 1.25.0 (a
quest's step waiting at a dungeon's floor, its first battle) passed his
test 56 (2 November: "Test 56 was a complete success and functioned
exactly as you described"), its log saying a floor won again in the same
second as its win (a side quest's battle is asked twice as it is won),
put right by 1.25.1, which passed his test 57 (2 November: "Test 57 was a
complete success"); 1.26.0 (a mod's own items at its town's Outfitter)
passed his test 58 (3 November: "Test 58 was a complete success and
functioned as you described it would"), so 1.26.0 was the one to publish
then, 1.21.0 to 1.25.1 within it; 1.27.0 (the game's own Outfitters
selling the mods' items, and their Item rows' UI values) passed his test
59 (3 November: "Test 59 was a complete success and functioned how you
said it would"), and a new weapon's look in battle (Mod Studio's alone)
his test 60 ("Test 60 was a complete success"), so 1.27.0 was the one to
publish then, 1.21.0 to 1.26.0 within it; 1.28.0 (the game's own weapons'
looks in battle) passed his test 61 (3 November: "Test 61 was a complete
success and functioned how you described it would"), so 1.28.0 was the
one to publish then, 1.21.0 to 1.27.0 within it; 1.29.0 (quest maps and
rumors numbered at each start, and the setting that frees a mod's numbers)
passed his test 62 (3 November: "Test 62 was a success and functioned how
you said it would"), and 1.29.1 (that setting's shorter name and words)
his test 63 (4 November: "Test 63 was a complete success and functioned
how you said it would"), so 1.29.1 was the one to publish then, 1.21.0
to 1.29.0 within it; 1.30.0 (Ramza named as the party has him) passed his
test 65 (4 November: "largely a success"), 1.31.0 (a quest's reward, and
scenes during a battle) his test 66 ("The test was a success and
functioned as you said it would"); test 67 (Mod Studio's three notes on
66, with 1.31.0) never showed its battle at Mandalia Plain, as both his
saves held old quests' flags at its numbers: put right by 1.32.0 (a save's
old flags cleared as it loads), which passed his test 68 (5 November:
"almost a complete success and functioned as you said it would", its one
note Mod Studio's narration); 1.33.0 (a quest unit's own name) passed his
test 69 ("a success", the names over the balloons Mod Studio's: his test
70, "a complete success and functioned exactly how you said it would"),
and 1.34.0 (a mod's road shown and grayed with its places) his test 71 (5
November: "Test 71 functioned exactly how you said it would"), so
1.35.0 (a save's old items taken out as it loads) went out as test 72,
which showed a save standing on a place the free let go loading with Ramza
nowhere, as every helper from 1.29.0 to 1.35.0 would once no mod's place
was numbered; 1.35.1 (a save's place looked at whatever the numbers
remember) passed his test 73 (5 November: "Test 73 was a complete success
and functioned exactly as you said it would"), test 72's items part with
it, so **1.35.1 is the one to publish now** (1.36.3 passed his test 77 and
can be published in its place when he chooses, 1.36.0 to 1.36.2 within it;
1.37.0 is not one to publish, 1.37.1 passed his test 79 and 1.37.2 his test 80 and either can be published when he chooses, 1.38.0 is never to be published (it loses a job's progress), 1.38.1 isn't one to publish either (a battle started again keeps its JP), nor 1.38.2 (its status card shows another job's numbers), 1.38.3 passed his test 84 and 1.38.4 his test 85, so 1.38.4 can be published when he chooses, 1.39.0 is not one to publish (its rows never move: test 86), nor 1.39.1 (a short row's window opens off the screen: test 87), nor 1.39.2 (the game's slide puts the places on the game's rows for a few frames: test 88), nor 1.39.3 (Q and E on the abilities' page can stop the game: test 89), and 1.39.4 waits for test 90), 1.30.0 to 1.35.0 within it
(never 1.35.0 alone). Every helper from 1.7.0
(a mod's place a destination) to 1.23.0
stops the game as Ramza arrives at a mod's place numbered 68 or more, and
from 1.18.0 (a mod's town's menu) to 1.23.1 as its menu opens there (a
player's numbers count every mod's place ever enabled), 1.20.0 too;
never 1.2.0, 1.2.2, 1.3.0, 1.4.0 or 1.9.0;
players also get the helper from whoever shares the mod (Mod Studio puts
it beside every mod that needs it).

To make a release (Reloaded-II's "Creating a Release" page):

1. Copy `tools/ModStudioEventSetup`'s eight files and (1.2.5) its
   `FFTIVC` folder into Reloaded-II's
   `Mods/fftivc.utility.modstudio.eventsetup` folder, over the older ones.
2. In Reloaded-II, right-click Mod Studio Framework (Mod Studio Event
   Setup before 1.22.0) and choose Publish;
   pick GitHub as the Publish Target if it is in the list, else Default,
   and Publish. It writes the mod as a `.7z` and its release metadata (a
   `.json`) into its output folder.
3. On GitHub, Releases, Draft a new release: the tag is the version
   (`1.35.1` now), and every `.7z` and `.json` of the
   output folder goes in as its files. Publish it.

A newer version is the same steps with its own tag; Reloaded-II offers it
to every player who has the helper. Mods made with Mod Studio never need
remaking for it: their `EventSetup.json` names events and fields, and
their quests name everything they add, not places in the program.
