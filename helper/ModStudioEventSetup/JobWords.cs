// Mod Studio Framework: a job's own words on Job Summary (1.47.0; Zodi's
// order of 13 November, "the Job Tree and Job Summary for our new jobs", and
// his choice the same night for a job whose file gives none: "Its own
// description"). Part of The Ivalice Chronicles Mod Studio, GPL-3.0.
//
// What the game does, measured in his program (17 September 2026, read as
// data; dev/research/sidequests/job_words.py holds each place to its bytes):
//
// Job Summary's words (the job screen's Y: Job Overview, Usable Equipment,
// Select Abilities and the rest, one text) are a row of the game table
// UiJobAbilityHelp (sheet 0x12F, one key, a file for each language): the
// job's Job row names it at + 0x30 (uijobabilityhelp+Id), and the job screen
// reads it in two places of its change of state (0x12FC6C, at 0x1307A0 and
// 0x130898): the Job row of the job at the cursor's place (0xF8574), the
// help row by that key through the generic getter (0x3DBC74), its text at
// the row's + 8 counted from there, handed to the summary's text box
// (0x28F728). No row, and the box keeps what it showed. Nothing else reads
// that sheet. A mod's job's Job row is its Like's with its own name and
// description (JobRoom.JobRow), so until 1.47.0 Job Summary showed its
// Like's words (his test 88's screenshot: Skirmisher with the Thief's).
//
// So: a job's file's Words may give a Summary, the text as the game shows
// it (its line breaks, and the game's own marks for a heading or an icon
// where the modder wants them). Every job a mod gives names a help row of
// its own in its Job row (HelpKey: 0x10000 plus the job, past the game's 0 to
// 34, WotL Restoration's to 40 and Dark Knight & Onion Knight (Generic)'s to
// 36), and UiJobAbilityHelp is given that row as it loads (WithHelpRows, from
// the jobs' hook of the tables' setup): its Summary, or where it gives none
// its Description under the heading the loaded language's first two jobs
// share (English "Job Overview"; in French each job's heading names the job,
// so there the Description alone). A row another mod has at a key is kept,
// said. No change of the game's code.
//
// (1.55.1, Zodi's words of 15 November: War of the Lions' Onion Knight's
// description changes once every job is mastered, its level 8) The game's
// Onion Knight a mod gives with a MasteredDescription has a second row, at
// the key of the job the game takes a level 8 Onion Knight's record and older
// words from (164): those words under the same heading (or, Zodi's word of
// 05:49, its MasteredSummary whole, laid out as the game's own rows are). Job Summary's two
// reads of a row by its key are changed for it (JobRoom's SummarySites): the
// Onion Knight's own key reads that row where the screen's unit's Onion
// Knight is level 8 (JobAsker.SummaryKey).
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Text;

namespace ModStudioEventSetup
{
    public static class JobWords
    {
        /// <summary>The job help table: its sheet, a row's fixed part, its comment and its text (a distance counted from
        /// the field itself), and where a Job row names its help row.</summary>
        public const int HelpSheet = 0x12F, HelpRowBytes = 0xC, HelpCommentAt = 4, HelpTextAt = 8, JobHelpAt = 0x30;
        /// <summary>The first key of the framework's own rows: a job's is this plus its number.</summary>
        public const int HelpFirst = 0x10000;
        /// <summary>The two game rows whose shared heading a job's Description is shown under (the Squire's and the
        /// Chemist's), and what ends a heading in the game's words.</summary>
        public const int HeadingRow = 1, HeadingOther = 2;
        public const string HeadingEnd = "</color>";

        /// <summary>The key of a job's own row of the job help table.</summary>
        public static int HelpKey(int job) => HelpFirst + job;

        /// <summary>A row of the job help table with these words: no DLC flags, an empty comment (empty read from the
        /// row's start or from its own field), the text after eight empty bytes, its distance counted from its
        /// field.</summary>
        public static byte[] HelpRow(string text)
        {
            byte[] words = Encoding.UTF8.GetBytes(text);
            int empty = HelpRowBytes, textAt = empty + 8;
            var row = new byte[(textAt + words.Length + 1 + 3) & ~3];
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(HelpCommentAt), empty);
            BinaryPrimitives.WriteInt32LittleEndian(row.AsSpan(HelpTextAt), textAt - HelpTextAt);
            words.CopyTo(row, textAt);
            return row;
        }

        /// <summary>A row's text in a loaded job help table, or null where the table has no such row or its text runs
        /// past the table.</summary>
        public static string? TextAt(ReadOnlySpan<byte> table, int key)
        {
            int at = Nxd.Find(table, new[] { key });
            if (at < 0 || at + HelpRowBytes > table.Length)
                return null;
            long start = (long)at + HelpTextAt + BinaryPrimitives.ReadInt32LittleEndian(table.Slice(at + HelpTextAt));
            if (start < 0 || start >= table.Length)
                return null;
            int end = (int)start;
            while (end < table.Length && table[end] != 0)
                end++;
            return end < table.Length ? Encoding.UTF8.GetString(table.Slice((int)start, end - (int)start)) : null;
        }

        /// <summary>The heading the loaded language's first two jobs' words share (each text up to the end of its first
        /// heading), or "" where they share none.</summary>
        public static string Heading(ReadOnlySpan<byte> table)
        {
            string? first = TextAt(table, HeadingRow), other = TextAt(table, HeadingOther);
            if (first == null || other == null)
                return "";
            int end = first.IndexOf(HeadingEnd, StringComparison.Ordinal);
            if (end < 0)
                return "";
            string heading = first.Substring(0, end + HeadingEnd.Length);
            return other.StartsWith(heading, StringComparison.Ordinal) ? heading : "";
        }

        /// <summary>What Job Summary shows for a job: its own Summary, or its Description under the heading, each of
        /// its lines a space in as the game's own lines are.</summary>
        public static string TextOf(ModJob job, string heading)
            => job.Summary ?? Described(job.Description, heading);

        /// <summary>(1.55.1) What Job Summary shows for the game's Onion Knight at its level 8: its own whole words there
        /// (its MasteredSummary, Zodi's word of 05:49: as the game's own rows are laid out), or its MasteredDescription
        /// under the heading.</summary>
        public static string MasteredTextOf(ModJob job, string heading)
            => job.MasteredSummary ?? Described(job.MasteredDescription ?? job.Description, heading);

        /// <summary>(1.55.1) A description under the heading, each of its lines a space in as the game's own lines are.</summary>
        public static string Described(string description, string heading)
        {
            string described = " " + description.Replace("\n", "\n ");
            return heading.Length == 0 ? described : heading + "\n\n" + described;
        }

        /// <summary>The loaded job help table with a row for each job given, or null and why; `rows` how many. A row
        /// another mod has at a key is kept, said.</summary>
        public static byte[]? WithHelpRows(ReadOnlySpan<byte> table, IEnumerable<JobRoom.Given> given, List<string> said,
                                           out string why, out int rows)
        {
            rows = 0;
            if (Nxd.Keys(table) != 1)
            {
                why = "it isn't a table of one key";
                return null;
            }
            string heading = Heading(table);
            var added = new List<NewRow>();
            foreach (var g in given)
            {
                int key = HelpKey(g.Number);
                if (Nxd.Find(table, new[] { key }) >= 0)
                {
                    said.Add($"{g.Job.Who}'s Job Summary keeps the row another mod gives it ({key}).");
                    continue;
                }
                added.Add(new NewRow(new[] { key }, HelpRow(TextOf(g.Job, heading))));
                // (1.55.1) The game's Onion Knight's words for its level 8, at the key of the job the game takes a level 8
                // Onion Knight's words from (JobRoom's SummarySites read it for such a unit), under the same heading.
                if (g.Number == JobFile.OnionKnight && g.Job.MasteredWords)
                {
                    int mastered = HelpKey(JobFile.MasteredOnion);
                    if (Nxd.Find(table, new[] { mastered }) >= 0)
                        said.Add($"{g.Job.Who}'s Job Summary for its level 8 keeps the row another mod gives it ({mastered}).");
                    else
                        added.Add(new NewRow(new[] { mastered }, HelpRow(MasteredTextOf(g.Job, heading))));
                }
            }
            if (added.Count == 0)
            {
                why = "";
                return table.ToArray();
            }
            var made = Nxd.WithRows(table, added, out why);
            if (made != null)
                rows = added.Count;
            return made;
        }

        /// <summary>The job help table's line, once its rows are written.</summary>
        public static string HelpRowsLine(int rows)
            => $"UiJobAbilityHelp: the mods' jobs' Job Summary words' {rows} row{(rows == 1 ? "" : "s")} written.";

        /// <summary>What is said where the table can't be given its rows.</summary>
        public static string NoRowsLine(string why)
            => $"UiJobAbilityHelp gets no rows: {why}. The mods' jobs show no words of their own on Job Summary.";
    }
}
