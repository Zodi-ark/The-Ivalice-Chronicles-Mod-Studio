// (1.41.0) The mods' own action abilities put in their jobs' skillsets (the road's step 4; Zodi's answer of 10 November
// 2026: "Straight to more"; test 94). Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// A mod's job names one of its mod's own abilities in its skillset's Actions by the ability's Name (JobFile). Once the
// abilities have their numbers (AbilityFile.Plan) and the jobs theirs and their skillsets' (JobRoom.Plan), each such
// place is settled: the skillset's record, which holds an ability in nine bits, is given the game's ability the mod's
// is like, and the framework's list of places (AbilityRoom) the mod's own number, which the game's reader answers with.
// Where the mod has no ability of that name that has a number, or the abilities can't be made in the game, the place
// is left empty, and that is said.
using System.Collections.Generic;

namespace ModStudioEventSetup
{
    public static class AbilityPlan
    {
        /// <summary>The places settled: each skillset's place that holds a mod's ability, and the jobs as they name
        /// them.</summary>
        public sealed class Made
        {
            readonly List<JobRoom.Given> _jobs;
            readonly List<int[]> _actions;

            /// <summary>Each place of a skillset that holds a mod's ability: the skillset, the place (0 to 15), the
            /// ability's number.</summary>
            public List<(int Skillset, int Place, int Number)> Places { get; } = new List<(int Skillset, int Place, int Number)>();
            /// <summary>The abilities given that no job's skillset holds.</summary>
            public List<AbilityFile.Given> Unplaced { get; } = new List<AbilityFile.Given>();

            internal Made(List<JobRoom.Given> jobs, List<int[]> actions)
            {
                _jobs = jobs;
                _actions = actions;
            }

            /// <summary>The jobs given, each with its skillset's Actions settled: where a place names a mod's ability
            /// that has a number, the game's ability it is like when the abilities are made in the game (`made`), else
            /// nothing (0).</summary>
            public List<JobRoom.Given> Jobs(bool made)
            {
                var jobs = new List<JobRoom.Given>();
                for (int n = 0; n < _jobs.Count; n++)
                {
                    var g = _jobs[n];
                    var actions = (int[])g.Job.Actions.Clone();
                    for (int place = 0; place < actions.Length; place++)
                        if (place < g.Job.ActionNames.Length && g.Job.ActionNames[place] != null)
                            actions[place] = made ? _actions[n][place] : 0;
                    jobs.Add(new JobRoom.Given(g.Job.WithActions(actions), g.Number, g.Skillset));
                }
                return jobs;
            }
        }

        /// <summary>Each place of the jobs' skillsets that names a mod's ability settled over the abilities given; a
        /// name the job's mod has no ability with a number for said. And each ability no skillset holds.</summary>
        public static Made Make(IList<JobRoom.Given> jobs, IList<AbilityFile.Given> abilities, List<string> said)
        {
            var byKey = new Dictionary<string, AbilityFile.Given>();
            foreach (var a in abilities)
                byKey[a.Ability.Key] = a;
            var placed = new HashSet<int>();
            var settled = new List<int[]>();
            var made = new Made(new List<JobRoom.Given>(jobs), settled);
            foreach (var g in jobs)
            {
                var job = g.Job;
                var actions = new int[job.Actions.Length];
                for (int place = 0; place < actions.Length; place++)
                {
                    string? name = place < job.ActionNames.Length ? job.ActionNames[place] : null;
                    if (name == null)
                        continue;
                    if (!byKey.TryGetValue($"{job.ModId}/{name}", out var ability))
                    {
                        said.Add($"{job.Who}'s skillset leaves out {name}: {job.ModName} has no ability of that name that "
                                 + "can be added.");
                        continue;
                    }
                    actions[place] = ability.Ability.Like;
                    made.Places.Add((g.Skillset, place, ability.Number));
                    placed.Add(ability.Number);
                }
                settled.Add(actions);
            }
            foreach (var a in abilities)
                if (!placed.Contains(a.Number))
                    made.Unplaced.Add(a);
            return made;
        }

        /// <summary>What the log says of an ability no job's skillset holds.</summary>
        public static string UnplacedLine(ModAbility ability)
            => $"{ability.Who} is in none of its mod's jobs' skillsets, so no unit can learn it.";
    }
}
