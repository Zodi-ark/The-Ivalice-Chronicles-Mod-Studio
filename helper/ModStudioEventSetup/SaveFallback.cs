// Mod Studio Framework: (1.7.1) a save standing on a mod's place whose mod
// is gone. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Variable 49 is the place Ramza stands on, kept in the save. A save made
// standing on a mod's own place (Destinations.cs: numbered 48 on) holds that
// number; loaded once no mod gives the place (its mod taken away, or the
// program not given the places), the game would set the world map up at a
// place it has nothing for: the places' records and dots past their end, the
// screen's row past its rows (the marker's arrival writes through it). So
// each mod's place keeps a home with its number (Numbers.json's "Homes": the
// first of the game's places its roads reach, in their order), and as the
// game loads a save's state (Places.SaveLoad, hooked through Reloaded-II's
// shared hooks: SaveFallbackHook.cs), a place no mod gives now becomes its
// home, else Gariland, said.
//
// (1.35.1) Zodi's test 72 (5 November): his save stood on Hermit's Rest
// (place 48, test 71's), and the free of 12:48 (1.29.0's setting) let test
// 71's places go with their homes. Until 1.35.1 a save's place was looked at
// only once some mod's place was ever numbered; after that free none was, so
// nothing moved Ramza: the world map set up at place 48 showed no Ramza, and
// Center on Ramza went to its top left. A save's place is looked at now
// whenever the game's load of a save is found (MoveOff), whatever the numbers
// still remember.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public static class SaveFallback
    {
        /// <summary>The variable of the place Ramza stands on (49), and the game's place a save goes on from when its
        /// place has no home kept (Gariland, 6: shown from the story's start).</summary>
        public const int PlaceVariable = 49, Gariland = 6;

        /// <summary>Each mod's place's home: the first of the game's places (0 to 47) its roads reach, the roads taken
        /// in their order (through other mods' places, nearest first); a place no road reaches has none.</summary>
        public static Dictionary<int, int> Homes(List<Destination> destinations, List<TravelRoad> travel)
        {
            var homes = new Dictionary<int, int>();
            foreach (var d in destinations)
            {
                var seen = new HashSet<int> { d.Number };
                var reached = new Queue<int>();
                reached.Enqueue(d.Number);
                int home = -1;
                while (home < 0 && reached.Count > 0)
                {
                    int place = reached.Dequeue();
                    foreach (var road in travel)
                    {
                        int other = road.From == place ? road.To : road.To == place ? road.From : -1;
                        if (other < 0 || !seen.Add(other))
                            continue;
                        if (other < Destinations.FirstNumber)
                        {
                            home = other;
                            break;
                        }
                        reached.Enqueue(other);
                    }
                }
                if (home >= 0)
                    homes[d.Number] = home;
            }
            return homes;
        }

        /// <summary>The place a save standing on `place` goes on from: the place itself when it is the game's (0 to
        /// 47) or a mod gives it now (`given`); else its home kept, else Gariland, and `said` says so.</summary>
        public static int Fallback(int place, ICollection<int> given, Numbers numbers, out string? said)
        {
            said = null;
            if (place < Destinations.FirstNumber || given.Contains(place))
                return place;
            int home = numbers.HomeOf(place);
            if (home < 0 || home >= Destinations.FirstNumber)
                home = Gariland;
            string? key = numbers.NameOf(Destinations.Kind, place);
            int split = key?.LastIndexOf('/') ?? -1;
            string which = key == null ? $"place {place}"
                : split < 0 ? $"{key} (place {place})" : $"{key.Substring(split + 1)} (place {place} of {key.Substring(0, split)})";
            said = $"the save stood on {which}, which no mod gives now: Ramza goes on from place {home}.";
            return home;
        }

        /// <summary>(1.35.1) A save's state just loaded (`variables`: the variables the game's load copied, from the
        /// first, as Places.SaveBank has them): the place it stands on (variable 49) moved where Fallback says, written
        /// back. What is said, null when it stays.</summary>
        public static string? MoveOff(Span<byte> variables, ICollection<int> given, Numbers numbers)
        {
            var place = variables.Slice(4 * PlaceVariable, 4);
            int was = BinaryPrimitives.ReadInt32LittleEndian(place);
            int now = Fallback(was, given, numbers, out string? said);
            if (now == was)
                return null;
            BinaryPrimitives.WriteInt32LittleEndian(place, now);
            return said;
        }
    }
}
