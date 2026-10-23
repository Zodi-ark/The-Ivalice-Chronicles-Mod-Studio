// Mod Studio Event Setup: the running game's program, as bytes. Part of The
// Ivalice Chronicles Mod Studio, GPL-3.0.
using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;

namespace ModStudioEventSetup
{
    /// <summary>The game's program as it lies in memory, from where it is loaded, and a way
    /// to make the table's bytes writable (they are in its writable data already; asked for
    /// all the same, then put back).</summary>
    public sealed unsafe class GameMemory
    {
        readonly byte* _base;
        readonly int _size;

        /// <summary>The program's file and its size ("FFT_enhanced.exe of 12,158,720 bytes"),
        /// for the log: after a game update, which program the helper met.</summary>
        public string Program { get; }

        GameMemory(byte* start, int size, string program)
        {
            _base = start;
            _size = size;
            Program = program;
        }

        public static GameMemory OfThisProcess()
        {
            var module = Process.GetCurrentProcess().MainModule
                ?? throw new InvalidOperationException("the game's program can't be seen");
            return new GameMemory((byte*)module.BaseAddress, module.ModuleMemorySize, Describe(module.FileName));
        }

        /// <summary>A program's file name and size, or its name alone when it can't be read.</summary>
        public static string Describe(string? path)
        {
            string name = string.IsNullOrEmpty(path) ? "the game's program" : Path.GetFileName(path);
            try
            {
                long size = new FileInfo(path!).Length;
                return $"{name} of {size.ToString("N0", CultureInfo.InvariantCulture)} bytes";
            }
            catch (Exception)
            {
                return name;
            }
        }

        public Span<byte> Bytes => new Span<byte>(_base, _size);

        const uint ReadWrite = 0x04;

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool VirtualProtect(void* address, nuint size, uint protect, out uint old);

        /// <summary>Runs a change to some of the program's bytes with them writable.</summary>
        public void Writing(int address, int length, Action change)
        {
            void* start = _base + address;
            bool asked = VirtualProtect(start, (nuint)length, ReadWrite, out uint old);
            try
            {
                change();
            }
            finally
            {
                if (asked)
                    VirtualProtect(start, (nuint)length, old, out _);
            }
        }
    }
}
