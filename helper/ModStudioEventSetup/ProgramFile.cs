// Mod Studio Framework: (1.44.2) the game's program as its file keeps it. Part of The Ivalice Chronicles Mod Studio,
// GPL-3.0.
//
// In the running game another mod's hook may sit at the start of a routine the framework looks for (his test 104: the
// mod loader's hooks on the two routines that read g2d.dat's entries begin with a jump of a kind the framework didn't
// know). The program's file is never hooked: it still holds the routine's own first bytes where memory holds the hook.
// The file keeps each section's bytes at a place of its own (the section table at the program's start says where), so
// the bytes memory has at an address are read from the file there.
using System;
using System.Buffers.Binary;
using System.IO;

namespace ModStudioEventSetup
{
    public sealed class ProgramFile
    {
        readonly string _path;
        readonly (int Address, int Size, int Raw, int Stored)[] _sections;

        ProgramFile(string path, (int Address, int Size, int Raw, int Stored)[] sections)
        {
            _path = path;
            _sections = sections;
        }

        /// <summary>The program's file at `path`, read by the section table at the start of `image` (the program as it lies
        /// in memory); null where there is no path or the table can't be read.</summary>
        public static ProgramFile? Of(string? path, ReadOnlySpan<byte> image)
        {
            if (string.IsNullOrEmpty(path) || image.Length < 0x40 || image[0] != (byte)'M' || image[1] != (byte)'Z')
                return null;
            int pe = BinaryPrimitives.ReadInt32LittleEndian(image.Slice(0x3C, 4));
            if (pe < 0 || pe + 24 > image.Length || image[pe] != (byte)'P' || image[pe + 1] != (byte)'E'
                || image[pe + 2] != 0 || image[pe + 3] != 0)
                return null;
            int count = BinaryPrimitives.ReadUInt16LittleEndian(image.Slice(pe + 6, 2));
            int optionalSize = BinaryPrimitives.ReadUInt16LittleEndian(image.Slice(pe + 20, 2));
            int first = pe + 24 + optionalSize;
            if (first + 40L * count > image.Length)
                return null;
            var sections = new (int Address, int Size, int Raw, int Stored)[count];
            for (int n = 0; n < count; n++)
            {
                var row = image.Slice(first + 40 * n, 40);
                sections[n] = (BinaryPrimitives.ReadInt32LittleEndian(row.Slice(12, 4)),
                               BinaryPrimitives.ReadInt32LittleEndian(row.Slice(8, 4)),
                               BinaryPrimitives.ReadInt32LittleEndian(row.Slice(20, 4)),
                               BinaryPrimitives.ReadInt32LittleEndian(row.Slice(16, 4)));
            }
            return new ProgramFile(path!, sections);
        }

        /// <summary>Where in the file lie the `length` bytes memory has at `address` (counted from the program's start):
        /// inside one section's bytes as the file stores them; -1 where no section's stored bytes hold all of them.</summary>
        public long Offset(int address, int length)
        {
            foreach (var s in _sections)
            {
                long within = (long)address - s.Address;
                long size = s.Size == 0 ? s.Stored : Math.Min(s.Size, s.Stored);
                if (within >= 0 && length >= 0 && within + length <= size && s.Raw >= 0)
                    return s.Raw + within;
            }
            return -1;
        }

        /// <summary>The `length` bytes the file keeps for memory's `address`; null where the file doesn't keep them or can't
        /// be read.</summary>
        public byte[]? At(int address, int length)
        {
            long offset = Offset(address, length);
            if (offset < 0)
                return null;
            try
            {
                using var file = new FileStream(_path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
                if (offset + length > file.Length)
                    return null;
                file.Seek(offset, SeekOrigin.Begin);
                var bytes = new byte[length];
                int read = 0;
                while (read < length)
                {
                    int got = file.Read(bytes, read, length - read);
                    if (got <= 0)
                        return null;
                    read += got;
                }
                return bytes;
            }
            catch (Exception e) when (e is IOException || e is UnauthorizedAccessException || e is ArgumentException
                                      || e is NotSupportedException || e is System.Security.SecurityException)
            {
                return null;
            }
        }
    }
}
