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
where WotL Restoration keeps its counts (flags 4736 to 5239). A mod's
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
it, so **1.35.1 is the one to publish now**, 1.30.0 to 1.35.0 within it
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
