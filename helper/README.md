# Mod Studio Event Setup

A Reloaded-II mod, part of The Ivalice Chronicles Mod Studio (GPL-3.0, as
Mod Studio), that applies the event setup changes a mod made with Mod
Studio lists. Zodi's choice, 21 October 2026: "Lets go with "One shared
helper mod"", called "Mod Studio Event Setup", shipped as "Its own release,
and in Mod Studio".

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
`BattleRules`. Each a whole number the field holds.

## Building

With the .NET 8 SDK, offline, from Mod Studio's folder:

    python3 helper/build.py <Reloaded.Mod.Interfaces.dll>

The DLL is Reloaded-II's interfaces (GPL-3.0, Reloaded-II's own; not copied
beside the mod, as Reloaded-II brings it), from
`reloaded.mod.interfaces.2.5.0.nupkg` (a zip: `lib/netcoreapp3.1/`,
https://www.nuget.org/api/v2/package/Reloaded.Mod.Interfaces/2.5.0). The
build lands in `tools/ModStudioEventSetup/`, Mod Studio's copy:
`ModConfig.json`, `ModStudioEventSetup.dll`, its `.deps.json` and
`Preview.png` (Mod Studio's icon). It is deterministic: the same source
makes the same DLL byte for byte, which `dev/test_event_setup.py` checks of
the shipped one. Online, `dotnet build` in `helper/ModStudioEventSetup`
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
(`dev/test_event_setup.py` builds and runs it): the program's file laid
out as it lies in memory, the table found, mods' files applied to a copy,
every byte changed reported. It doesn't ship.

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
for him to publish; players also get the helper from whoever shares the
mod (Mod Studio puts it beside every mod that needs it).

To make a release (Reloaded-II's "Creating a Release" page):

1. Copy `tools/ModStudioEventSetup`'s four files into Reloaded-II's
   `Mods/fftivc.utility.modstudio.eventsetup` folder, over the older ones.
2. In Reloaded-II, right-click Mod Studio Event Setup and choose Publish;
   pick GitHub as the Publish Target if it is in the list, else Default,
   and Publish. It writes the mod as a `.7z` and its release metadata (a
   `.json`) into its output folder.
3. On GitHub, Releases, Draft a new release: the tag is the version
   (`1.0.2`), and every `.7z` and `.json` of the output folder goes in as
   its files. Publish it.

A newer version is the same steps with its own tag; Reloaded-II offers it
to every player who has the helper. Mods made with Mod Studio never need
remaking for it: their `EventSetup.json` names events and fields, not
places in the program.
