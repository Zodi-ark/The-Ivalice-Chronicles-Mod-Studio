// Mod Studio Framework: (1.45.0) a job's own portraits. Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// The road's step 5, its second part, a mod's own art, the last in Zodi's order of 12 November ("Colors first", then the
// sprites' textures, then the portraits), measured in dev/research/sidequests/portraits.py (claude/job-sprites-research.md
// says what it means).
//
// The Enhanced look loads every face it draws (the party menu, the status screen, the battle's panels, the turn list, the
// talk windows) through one routine (0xFC22C): handed the portrait's number and its colors (the team's: 8 to 12), it
// writes the face's file's name, `UITextureParts://ui/ffto/common/face/textureparts/wldface_<number>_<colors>_uitx`, and
// the caller loads that part list and the texture it names. A unit's portrait's number comes, in a battle, from its
// graphics slot (the slots' table 1.42.2 writes: a generic's numbered as its sprite), and, outside one, from its sprite's
// face word through the face to portrait routine (0x274028). On the way each is bounded at the game's last, 205.
//
// So a job whose Look gives Portraits has each of its own sprites so given a portrait number of the framework's (Number:
// its sprite's plus 86, 256 to 340, past every number of the game's and of the mods' known); its face word names that
// number as its face (SpriteRoom.Fill), and the face to portrait routine answers such a face with itself (a call of the
// framework's code in place of its first two instructions); its graphics slot's number is that number (SpriteRoom.Code);
// the six bounds on the way to the Enhanced look are widened to the last of them (three in place; three held in a
// register the routine's switch also answers face 0xCD with, made from another register so face 0xCD is still 205); and
// a hook on the face's file's routine (SpritePortraitHooks.cs) names the job's own part list for that number, the one of
// the team's colors (the first where the job gives fewer). Every other number is the game's own routine's. The other
// places that take a portrait's number (the older drawing code the Classic look uses, its atlas of units, the face slots
// it reads) keep their own bounds or take a face's low byte only: there, a job's own portrait is none or another's. Only
// the Enhanced look is supported (his word, 12 November).
//
// The face's file's routine is found by a call of it, and where it doesn't start as the game's own (another mod's hook),
// taken where the game's program file has it (as SpriteTextures.cs finds its routines). With no job with portraits of its
// own none of this is made.
//
// (1.45.1, test 106's report: the small faces right, the big ones empty) Two more places on the way to the Enhanced look:
// the routines that fill a battle's unit cards (the formation's and the battle's at the bottom right) bound the slot's
// number at 205 themselves, and the face routine's way for the party's units (the status screen, the job screen, the
// party list) asks a portrait routine that takes a face word with bit 8 or 9 set as no face at all (a face of the
// framework's has bit 8 set). Each now calls the framework's code in place of its test: a number of the framework's kept
// (the cards' offset into the older drawing's face sprites 0, as for none), a face of the framework's answered with
// itself and its colors written as the game's routine writes them; every other as the game's.
using System;
using System.Collections.Generic;
using System.Text;

namespace ModStudioEventSetup
{
    public static partial class SpritePortraits
    {
        /// <summary>A job's own sprite's portrait number is its sprite's plus OwnPlus: the first sprite past the game's (170)
        /// is First, the last a sprite can be (254) is Last.</summary>
        public const int OwnPlus = 86, First = SpriteRoom.GameCount + OwnPlus, Last = SpriteRoom.Count - 1 + OwnPlus;
        /// <summary>The game's last portrait (each bound before it is widened), and the colors of the player's team's (the
        /// first of a job's Portraits; the teams' are 8 to 12).</summary>
        public const int GameLast = 205, FirstColors = 8;
        /// <summary>Where the face's file's name starts, as the game's routine writes it (UILoadTexturePath's row 4, its
        /// folder), and the most bytes the caller's buffer holds.</summary>
        public const string FilePrefix = "UITextureParts://ui/ffto/common/face/textureparts/";
        public const int FileBytes = 0x100;

        /// <summary>A job's own sprite's portrait number.</summary>
        public static int Number(int sprite) => sprite + OwnPlus;

        /// <summary>The places found, each from the program's start: the face to portrait routine's first instructions, each
        /// bound's four bytes, each answer, and the face's file's routine.</summary>
        public sealed class Sites
        {
            public int FaceMap { get; internal set; } = -1;
            public int[] BoundAt { get; } = new int[Bounds.Length];
            public int[] AnswerAt { get; } = new int[Answers.Length];
            public int FaceFile { get; internal set; } = -1;
            /// <summary>(1.45.1) The two bounds of a battle's unit cards, and the test of the party's faces.</summary>
            public int[] HudBoundAt { get; } = new int[HudBound.Count];
            public int FaceTestAt { get; internal set; } = -1;
            public List<string> Missing { get; } = new List<string>();
            public bool Ok => Missing.Count == 0;
        }

        /// <summary>Every place, each found once by its pattern and held to what it must be (the routine's two instructions,
        /// a bound's 205, an answer's bytes); the face's file's routine by a call of it (found once), starting as the game's
        /// own in `image` or in `file` (its program file, where another mod has hooked it).</summary>
        public static Sites Find(ReadOnlySpan<byte> image, List<Section> sections, ProgramFile? file)
        {
            var sites = new Sites();
            int map = SpriteTextures.Once(image, sections, FaceMap.Pattern, "the face to portrait routine", sites.Missing);
            if (map >= 0)
            {
                if (Holds(image, map + FaceMap.At, FaceMap.Bytes))
                    sites.FaceMap = map + FaceMap.At;
                else
                    sites.Missing.Add("the face to portrait routine (its first instructions aren't the game's)");
            }
            for (int n = 0; n < Bounds.Length; n++)
            {
                sites.BoundAt[n] = -1;
                int at = SpriteTextures.Once(image, sections, Bounds[n].Pattern, $"a portrait's bound ({n + 1} of {Bounds.Length})",
                                             sites.Missing);
                if (at < 0)
                    continue;
                if (BitConverter.ToInt32(image.Slice(at + Bounds[n].At, 4)) == GameLast)
                    sites.BoundAt[n] = at + Bounds[n].At;
                else
                    sites.Missing.Add($"a portrait's bound ({n + 1} of {Bounds.Length}: it isn't {GameLast})");
            }
            for (int n = 0; n < Answers.Length; n++)
            {
                sites.AnswerAt[n] = -1;
                int at = SpriteTextures.Once(image, sections, Answers[n].Pattern,
                                             $"a portrait's bound's answer ({n + 1} of {Answers.Length})", sites.Missing);
                if (at < 0)
                    continue;
                if (Holds(image, at + Answers[n].At, Answers[n].Bytes))
                    sites.AnswerAt[n] = at + Answers[n].At;
                else
                    sites.Missing.Add($"a portrait's bound's answer ({n + 1} of {Answers.Length}: it isn't the game's)");
            }
            var cards = Places.Search(image, sections, Places.Pattern(HudBound.Pattern));
            cards.Sort();
            for (int n = 0; n < HudBound.Count; n++)
                sites.HudBoundAt[n] = cards.Count == HudBound.Count ? cards[n] : -1;
            if (cards.Count != HudBound.Count)
                sites.Missing.Add($"the bounds of a battle's unit cards ({cards.Count} places like them, not {HudBound.Count})");
            int test = SpriteTextures.Once(image, sections, FaceTest.Pattern, "the test of the party's faces", sites.Missing);
            if (test >= 0)
            {
                if (Holds(image, test + FaceTest.At, FaceTest.Bytes))
                    sites.FaceTestAt = test + FaceTest.At;
                else
                    sites.Missing.Add("the test of the party's faces (it isn't the game's)");
            }
            int call = SpriteTextures.Once(image, sections, FaceFileCall.Pattern, "a call of the face's file's routine",
                                           sites.Missing);
            if (call >= 0)
                sites.FaceFile = SpriteTextures.Routine(image, call + FaceFileCall.At, FaceFileOwn, "the face's file's routine",
                                                        sites.Missing, file);
            return sites;
        }

        static bool Holds(ReadOnlySpan<byte> image, int at, string hex)
        {
            var bytes = Convert.FromHexString(hex);
            return at >= 0 && at + bytes.Length <= image.Length && image.Slice(at, bytes.Length).SequenceEqual(bytes);
        }

        /// <summary>The framework's answer for its own portraits' faces, written in `a` (the jobs' native code), and the
        /// changes of the game's code: a call of it in place of the face to portrait routine's first two instructions
        /// (`or ecx, -1; cmp edx, 0x9F`: a face of the framework's numbers is answered with itself, straight to the
        /// routine's caller; any other goes on as the game's, those two done and the flags as their compare left them);
        /// every bound's 205 made Last; every answer made from eax. (1.45.1) A call in place of each bound of a battle's
        /// unit cards (`cmp r11d, 0xCD; jbe; mov r11d, edi; mov edx, esi`): a number of the framework's kept and edx (its
        /// offset into the older drawing's face sprites) as for none, every other as the game's, every register but those
        /// two as it was; and a call in place of the test of the party's faces (`test edx, 0x300`): a face of the
        /// framework's numbers in the word answered with itself (esi, the portrait routine's answer) and its colors
        /// written as the game's routine writes them ((word >> 10 &amp; 3) + 8, to r9), the flags made so the jump after
        /// goes to the routine's end; any other word tested as the game's; every register but esi as it was.</summary>
        internal static void Code(Destinations.Asm a, Sites sites, ulong imageBase, List<JobRoom.Change> made)
        {
            ulong map = a.Here;
            a.Hex("81 FA");                                    // cmp edx, First
            a.Bytes(BitConverter.GetBytes(First));
            a.Short(0x72, "portraitMapGame");                  // jb
            a.Hex("81 FA");                                    // cmp edx, Last
            a.Bytes(BitConverter.GetBytes(Last));
            a.Short(0x77, "portraitMapGame");                  // ja
            a.Hex("8B C2 48 83 C4 08 C3");                     // mov eax, edx; add rsp, 8; ret (to the routine's caller)
            a.Label("portraitMapGame");
            a.Bytes(Convert.FromHexString(FaceMap.Bytes));     // or ecx, -1; cmp edx, 0x9F
            a.Bytes(0xC3);
            made.Add(new JobRoom.Change(sites.FaceMap, SpriteRoom.CallFrom(imageBase, sites.FaceMap, map, FaceMap.Bytes.Length / 2)));
            foreach (int at in sites.BoundAt)
                made.Add(new JobRoom.Change(at, BitConverter.GetBytes(Last)));
            for (int n = 0; n < Answers.Length; n++)
                made.Add(new JobRoom.Change(sites.AnswerAt[n], Convert.FromHexString(Answers[n].Becomes)));

            ulong cards = a.Here;
            a.Hex("41 81 FB CD 00 00 00");                     // cmp r11d, 205
            a.Short(0x76, "portraitCardKeep");                 // jbe: the game's own, kept as the game keeps it
            a.Hex("41 81 FB");                                 // cmp r11d, First
            a.Bytes(BitConverter.GetBytes(First));
            a.Short(0x72, "portraitCardNone");                 // jb
            a.Hex("41 81 FB");                                 // cmp r11d, Last
            a.Bytes(BitConverter.GetBytes(Last));
            a.Short(0x77, "portraitCardNone");                 // ja
            a.Hex("8B D6 C3");                                 // mov edx, esi; ret (the framework's number kept)
            a.Label("portraitCardNone");
            a.Hex("44 8B DF 8B D6");                           // mov r11d, edi; mov edx, esi (none, as the game's)
            a.Label("portraitCardKeep");
            a.Bytes(0xC3);
            int cardBytes = HudBound.Pattern.Split(' ').Length;
            foreach (int at in sites.HudBoundAt)
                made.Add(new JobRoom.Change(at, SpriteRoom.CallFrom(imageBase, at, cards, cardBytes)));

            ulong test = a.Here;
            a.Hex("50 8B C2 25 FF 03 00 00 3D");               // push rax; mov eax, edx; and eax, 0x3FF; cmp eax, First
            a.Bytes(BitConverter.GetBytes(First));
            a.Short(0x72, "portraitTestGame");                 // jb
            a.Bytes(0x3D);                                     // cmp eax, Last
            a.Bytes(BitConverter.GetBytes(Last));
            a.Short(0x77, "portraitTestGame");                 // ja
            a.Hex("8B F0");                                    // mov esi, eax (the routine's answer: the face)
            a.Hex("8B C2 C1 E8 0A 83 E0 03 83 C0 08 41 89 01"); // its colors: (edx >> 10 & 3) + 8, to [r9]
            a.Hex("58 48 85 E4 C3");                           // pop rax; test rsp, rsp (not zero: the jne goes); ret
            a.Label("portraitTestGame");
            a.Bytes(0x58);                                     // pop rax
            a.Bytes(Convert.FromHexString(FaceTest.Bytes));    // test edx, 0x300 (the game's own)
            a.Bytes(0xC3);
            made.Add(new JobRoom.Change(sites.FaceTestAt, SpriteRoom.CallFrom(imageBase, sites.FaceTestAt, test,
                                                                              FaceTest.Bytes.Length / 2)));
        }

        /// <summary>The part lists the framework names, by portrait number: for each job's own sprite whose job's Look gives
        /// it portraits (its man's, its woman's), its names, one a team's colors.</summary>
        public static Dictionary<int, string[]> Plan(IList<JobRoom.Given> given)
        {
            var plan = new Dictionary<int, string[]>();
            foreach (var g in given)
                if (g.Sprite >= 0)
                    for (int woman = 0; woman < 2; woman++)
                    {
                        var names = g.Job.Portraits[woman];
                        if (names != null && names.Length > 0)
                            plan[Number(g.Sprite + woman)] = names;
                    }
            return plan;
        }

        /// <summary>Which of a job's portraits is named for colors: the one of those colors (8 the first), or its first where it
        /// gives none of them.</summary>
        public static int Which(string[] names, int colors)
        {
            int n = colors - FirstColors;
            return n >= 0 && n < names.Length ? n : 0;
        }

        /// <summary>The part list named for a portrait number and colors; null for a number not the framework's.</summary>
        public static string? NameFor(Dictionary<int, string[]> plan, int portrait, int colors)
            => plan.TryGetValue(portrait, out var names) ? names[Which(names, colors)] : null;

        /// <summary>The face's file's name as the game's routine would write it for a part list of `name`, ended by a 0.</summary>
        public static byte[] FileName(string name) => Encoding.ASCII.GetBytes(FilePrefix + name + "\0");

        /// <summary>Whose each of the framework's portrait numbers is, for the log: the job's and the man's or the woman's.</summary>
        public static Dictionary<int, string> Whose(IList<JobRoom.Given> given)
        {
            var whose = new Dictionary<int, string>();
            string[] sex = { "man's", "woman's" };
            foreach (var g in given)
                if (g.Sprite >= 0)
                    for (int woman = 0; woman < 2; woman++)
                        if (g.Job.Portraits[woman] != null)
                            whose[Number(g.Sprite + woman)] = $"{g.Job.Who}, the {sex[woman]}";
            return whose;
        }

        /// <summary>What the log says the first time the game is given a job's own portrait (`whose`: Whose's; `which`: the
        /// place in the job's Portraits of the one named).</summary>
        public static string FirstLine(string whose, int which)
            => $"the game was given a job's own portrait for the first time ({whose} {JobFile.PaletteOrdinals[which]} portrait).";

        /// <summary>What the log says where the jobs keep their Look's portraits.</summary>
        public static string NotLine(string why)
            => $"the jobs' own portraits can't be given: {why}. Each job with portraits of its own has its Look's.";
    }
}
