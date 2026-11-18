// (1.55.0, Zodi's word of 15 November 2026: "In WotL, and you can confirm with FFTPatcher to see this for the PSP, Dark
// Knight does not have Chant in its skill list. It has Sanguine Sword. What ever War of the Lions does we should do.") The
// game's own Dark Knight's abilities as War of the Lions has them. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// Measured (dev/research/sidequests/dark_onion.py; FFTPatcher's lists and tables of the PSP game, read for facts only):
// War of the Lions' Darkness (skillset 224) is Sanguine Sword (45), Infernal Strike (184), Crushing Blow (219), Abyssal
// Blade (220) and Unholy Sacrifice (357), then HP Boost (484), Vehemence (485), Movement +3 (488) and Jump +3 (491); its
// Holy Sword (skillset 29, Delita's) holds Chant as 152. The game made 45 a copy of Chant (152) in its common record, its
// action record, its effect, its animation and its row of the Ability table, and put it in Holy Sword's sixth place where
// 152 was. Every other ability of the nine is War of the Lions' in every number; the six of them the game doesn't name
// have no name.
//
// So, where a mod gives the game's Dark Knight: Holy Sword's sixth place is 152 again (the same Chant in every record and
// word: Delita sees no change), and 45 is War of the Lions' Sanguine Sword again: its common record (its cost of 500, its
// chance to be learned, its kind's flags), its action record (range 3, the dark element, formula 0x65, whose routine the
// program has), its animation (the other four actions'), and its effect. War of the Lions' effect (287) isn't among the
// game's files (his unpacked game has none from 274 to 287), so it shows Shadowblade's (Gaffgarion's, which absorbs HP
// with darkness too); the Abilities tab can change it. Each part only where it is still the game's own: a part another
// mod has changed is kept, and said. Its name and the others' are the job's file's, else War of the Lions'
// (AbilityWords.WithGameNames).
//
// (1.55.1, Zodi's test 122 and his words of 15 November) The seven's descriptions where the job's file gives none are War
// of the Lions' own, as he gave them, and each row is given an icon (Icons): with none, his game showed their
// descriptions but no names.
//
// The action records the game reads are made at their first use from a table of the program's (ActionSource), each row
// of the table's sheet then written over its ability's (a mod's changes): written before the game runs, the source is
// enough; where they are made already, the made one is written too.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public static class DarkKnightAbilities
    {
        /// <summary>Sanguine Sword's number (the game's copy of Chant), Chant's, Holy Sword's skillset, the place of it
        /// that holds 45 (its sixth), Shadowblade (whose effect Sanguine Sword shows) and Infernal Strike (whose row of the
        /// Ability table Sanguine Sword's is made like: no voice; its icon Icons').</summary>
        public const int Sanguine = 45, Chant = 152, HolySword = 29, ChantPlace = 5, Shadowblade = 165, RowLike = 184;
        /// <summary>War of the Lions' Sanguine Sword's cost to learn.</summary>
        public const int Cost = 500;
        /// <summary>War of the Lions' Sanguine Sword: its common record (its cost, its chance to be learned, its kind's
        /// flags), its action record (range 3, no area, no height, its flags, the dark element, formula 0x65; then the six
        /// bytes every action record of the game has), its animation (the other four actions').</summary>
        public static readonly byte[] Common = { 0xF4, 0x01, 0x32, 0x41, 0x42, 0x00, 0x01, 0x80 };
        public static readonly byte[] Action = { 0x03, 0x00, 0x00, 0x05, 0x11, 0x02, 0x08, 0x01, 0x65, 0x00, 0x00, 0x00, 0x00,
                                                 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF };
        public static readonly byte[] Animation = { 0x07, 0x00, 0x00 };
        /// <summary>The game's own 45 (Chant's copy) as each place holds it: a place that doesn't is another mod's.</summary>
        public static readonly byte[] GameCommon = { 0x00, 0x00, 0x64, 0x41, 0x81, 0x00, 0x00, 0x80 };
        public static readonly byte[] GameAction = { 0x01, 0x00, 0x03, 0x09, 0x10, 0x10, 0x00, 0x00, 0x3C, 0x00, 0x00, 0x00,
                                                     0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF };
        public static readonly byte[] GameAnimation = { 0x03, 0x66, 0x00 };
        public const short GameEffect = 161;
        /// <summary>War of the Lions' names of the game's Dark Knight's abilities the game names otherwise or not at all, and
        /// (1.55.1, Zodi's words of 15 November, War of the Lions' own) their descriptions.</summary>
        public static readonly (int Ability, string Name, string Description)[] Names =
        {
            (45, "Sanguine Sword", "Absorb HP from the target."),
            (184, "Infernal Strike", "Absorb MP from the target."),
            (219, "Crushing Blow", "Inflict damage with a sinister sword."),
            (220, "Abyssal Blade", "Sacrifice own HP to deal damage to others, with the nearest units suffering the most damage."),
            (357, "Unholy Sacrifice", "Sacrifice own HP to deal extensive damage to all units in range."),
            (484, "HP Boost", "Increase maximum HP by 20 percent."),
            (485, "Vehemence", "Increase attack power by 50 percent and decrease defensive power by 50 percent."),
        };
        /// <summary>(1.55.1, Zodi's test 122: the seven names didn't show, their descriptions did) The game shows no name for
        /// an ability whose row of the Ability table has no icon: the other mod's rows for the same seven, whose names show
        /// in his game, differ from the game's only in their icon and their words. So each is given the icon of the game's
        /// ability most like it: Sanguine Sword Shadowblade's (HP drawn with darkness), Infernal Strike Duskblade's (MP),
        /// Crushing Blow, Abyssal Blade and Unholy Sacrifice Shadowblade's (damage), HP Boost and Vehemence Attack
        /// Boost's.</summary>
        public static readonly (int Ability, int IconLike)[] Icons =
        {
            (45, Shadowblade), (184, 164), (219, Shadowblade), (220, Shadowblade), (357, Shadowblade), (484, 465), (485, 465),
        };

        /// <summary>(1.55.1) The game's ability whose icon one of the seven is given, or -1.</summary>
        public static int IconLike(int ability)
        {
            foreach (var (a, like) in Icons)
                if (a == ability)
                    return like;
            return -1;
        }

        /// <summary>An action record's bytes, how many the game has, a skillset record's bytes.</summary>
        const int ActionBytes = 20, ActionCount = 368, SkillsetBytes = 25;
        /// <summary>The action records' maker (0x2BAE24): its copy of the source to the records the game reads
        /// (mov r8d, 368 * 20; lea rdx, [rip + source]; lea rcx, [rip + records]).</summary>
        const string MakerBytes = "41 B8 C0 1C 00 00 48 8D 15 ?? ?? ?? ?? 48 8D 0D ?? ?? ?? ??";
        /// <summary>The action records' getter (0x2BB060), from its bound: the byte that says the records are made
        /// (cmp byte ptr [rip + made], 0), before its call of the maker.</summary>
        const string GetterBytes = "81 FB 6F 01 00 00 77 ?? 80 3D ?? ?? ?? ?? 00 75 ?? E8";

        /// <summary>The places found (from the program's start): the tables of the abilities' common records, effects
        /// and animations, the action records' source, the records made from it and the byte that says they are, the
        /// skillsets' records.</summary>
        public sealed class Sites
        {
            public int Records { get; set; } = -1;
            public int Effects { get; set; } = -1;
            public int Animations { get; set; } = -1;
            public int ActionSource { get; set; } = -1;
            public int Actions { get; set; } = -1;
            public int ActionsMade { get; set; } = -1;
            public int Skillsets { get; set; } = -1;
            /// <summary>Each place not found, in words.</summary>
            public List<string> Missing { get; } = new List<string>();
            public bool Ok => Missing.Count == 0;
        }

        static int I32(ReadOnlySpan<byte> b, int at) => BinaryPrimitives.ReadInt32LittleEndian(b.Slice(at, 4));

        /// <summary>Every place, found in the program as it is (before anything of it is changed: the tables' readers name
        /// the game's own tables then). `skillsets`: the skillsets' records, as the jobs found them.</summary>
        public static Sites Find(ReadOnlySpan<byte> image, List<Section> sections, int skillsets)
        {
            var sites = new Sites
            {
                Records = AbilityRecords.Locate(image, sections),
                Effects = AbilityEffects.Locate(image, sections),
                Animations = AbilityAnimations.Locate(image, sections),
                Skillsets = skillsets,
            };
            var maker = Places.Search(image, sections, Places.Pattern(MakerBytes));
            if (maker.Count == 1)
            {
                sites.ActionSource = maker[0] + 13 + I32(image, maker[0] + 9);
                sites.Actions = maker[0] + 20 + I32(image, maker[0] + 16);
            }
            else
                sites.Missing.Add($"the action records' maker ({maker.Count} places like it, not 1)");
            var getter = Places.Search(image, sections, Places.Pattern(GetterBytes));
            if (getter.Count == 1)
                sites.ActionsMade = getter[0] + 15 + I32(image, getter[0] + 10);
            else
                sites.Missing.Add($"the action records' getter ({getter.Count} places like it, not 1)");
            // Each table inside the program as it lies in memory.
            if (!Inside(image, sites.Records, AbilityRecords.GameCount * AbilityRecords.RecordBytes))
                sites.Missing.Add("the abilities' records (their first reader)");
            if (!Inside(image, sites.Effects, 2 * AbilityEffects.GameWords))
                sites.Missing.Add("the abilities' effects (their first reader)");
            if (!Inside(image, sites.Animations, AbilityAnimations.RowBytes * AbilityAnimations.GameRows))
                sites.Missing.Add("the abilities' animations (their first reader)");
            if (maker.Count == 1 && !(Inside(image, sites.ActionSource, ActionBytes * ActionCount)
                                      && Inside(image, sites.Actions, ActionBytes * ActionCount)))
                sites.Missing.Add("the action records (where the maker names them)");
            if (getter.Count == 1 && !Inside(image, sites.ActionsMade, 1))
                sites.Missing.Add("the action records' made byte (where the getter names it)");
            if (!Inside(image, skillsets, SkillsetBytes * (HolySword + 1)))
                sites.Missing.Add("the skillsets' records");
            return sites;
        }

        static bool Inside(ReadOnlySpan<byte> image, int at, int length) => at >= 0 && length >= 0 && at <= image.Length - length;

        /// <summary>What makes 45 War of the Lions' Sanguine Sword and Holy Sword's sixth place Chant again, in the
        /// program as it is now: each part only where it is still the game's own. `kept`: each part another mod has
        /// changed, in words. `sanguine`: whether 45 is made Sanguine Sword (its common or its action record).</summary>
        public static List<JobRoom.Change> Changes(ReadOnlySpan<byte> image, Sites sites, List<string> kept, out bool sanguine)
        {
            var changes = new List<JobRoom.Change>();
            sanguine = false;
            if (!sites.Ok)
                return changes;
            sanguine |= Part(image, sites.Records + AbilityRecords.RecordBytes * Sanguine, GameCommon, Common, "its common record",
                             changes, kept);
            sanguine |= Part(image, sites.ActionSource + ActionBytes * Sanguine, GameAction, Action, "its action record", changes,
                             kept);
            if (image[sites.ActionsMade] != 0)
                Part(image, sites.Actions + ActionBytes * Sanguine, GameAction, Action, "its action record as the game made it",
                     changes, kept);
            Part(image, sites.Animations + AbilityAnimations.RowBytes * Sanguine, GameAnimation, Animation, "its animation",
                 changes, kept);
            var game = new byte[2];
            BinaryPrimitives.WriteInt16LittleEndian(game, GameEffect);
            Part(image, sites.Effects + 2 * Sanguine, game, image.Slice(sites.Effects + 2 * Shadowblade, 2).ToArray(), "its effect",
                 changes, kept);
            // Holy Sword's sixth place: its byte, its ninth bit none (45 and 152 are both below 256).
            int skillset = sites.Skillsets + SkillsetBytes * HolySword;
            if (image[skillset + 3 + ChantPlace] == Sanguine && (image[skillset + ChantPlace / 8] & (0x80 >> ChantPlace % 8)) == 0)
                changes.Add(new JobRoom.Change(skillset + 3 + ChantPlace, new[] { (byte)Chant }));
            else
                kept.Add("Holy Sword's sixth place");
            return changes;
        }

        /// <summary>One part: War of the Lions' bytes where the place holds the game's own, else kept (in words).</summary>
        static bool Part(ReadOnlySpan<byte> image, int at, byte[] game, byte[] wotl, string what, List<JobRoom.Change> changes,
                         List<string> kept)
        {
            if (image.Slice(at, game.Length).SequenceEqual(game))
            {
                changes.Add(new JobRoom.Change(at, (byte[])wotl.Clone()));
                return true;
            }
            kept.Add(what);
            return false;
        }

        /// <summary>The log's line once the changes are made (`sanguine` as Changes gave it): each part another mod
        /// changed kept, said.</summary>
        public static string Line(bool sanguine, IList<string> kept)
        {
            bool effect = !kept.Contains("its effect"), holy = !kept.Contains("Holy Sword's sixth place");
            string line = sanguine ? "the game's Dark Knight's Sanguine Sword (ability 45) is War of the Lions' again"
                                   : "the game's Dark Knight's first ability (45) isn't made War of the Lions' Sanguine Sword";
            if (sanguine && effect)
                line += ", with Shadowblade's effect (War of the Lions' isn't among the game's files)";
            if (holy)
                line += sanguine ? ", and Holy Sword holds Chant (ability 152) again" : "; Holy Sword holds Chant (ability 152) again";
            if (kept.Count == 0)
                return line + ".";
            var all = new List<string>(kept).ToArray();
            string parts = all.Length == 1 ? all[0] : string.Join(", ", all, 0, all.Length - 1) + " and " + all[^1];
            return $"{line}; {parts} kept as another mod made {(kept.Count == 1 ? "it" : "them")}.";
        }

        /// <summary>What the log says where a place isn't found: 45 stays the game's copy of Chant.</summary>
        public static string NotLine(IList<string> missing, string program, string name)
            => $"the game's Dark Knight's first ability stays the game's copy of Chant: {string.Join(", ", missing)} wasn't found "
               + $"in {program}. A game update may have changed it: look for a newer {name}.";
    }
}
