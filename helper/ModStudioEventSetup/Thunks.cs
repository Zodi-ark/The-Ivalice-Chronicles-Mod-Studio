// Mod Studio Framework: native code standing in for a function of the game's
// that its callers count on to leave registers alone. Part of The Ivalice
// Chronicles Mod Studio, GPL-3.0.
//
// (1.2.3) The world map's travel check (Places.TravelCheck, the game's own,
// called from travel start and from each stop of a travel) touches no
// register but rax, rcx, rdx and r8, and the game's compiler counted on it:
// the travel step keeps r9 (the route it takes next, 0x248794), r10 and r11
// across the call. The Windows x64 convention lets any function change r8 to
// r11, and a hook's C# code does, so 1.2.2's hook (C#, through Reloaded-II's
// shared hooks) left the travel step a changed r9 once .NET had compiled the
// hook again: Zodi's game stopped (0xC0000005 at 0x248794) passing a town,
// after a quest line and a save loaded. The check is now hooked to the code
// made here, which keeps every register but rax and the flags: it runs the
// game's check, and asks C# only when the game would stop a travel.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace ModStudioEventSetup
{
    public static class Thunks
    {
        /// <summary>The registers the stand-in keeps around its calls, besides rbx, rbp, rsi, rdi
        /// and r12 to r15, which any function keeps: rcx, rdx, r8, r9, r10, r11 and xmm0 to
        /// xmm5.</summary>
        public static readonly string[] Kept =
            { "rcx", "rdx", "r8", "r9", "r10", "r11", "xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5" };

        /// <summary>The stand-in for the travel check, x64: the game's check called through the
        /// address kept at `original` (the hook's way to the game's own, written there once the
        /// hook is made); when it answers 0, that is the answer, else `decide` (no arguments, the
        /// Microsoft x64 convention) gives it, 0 to let the travel go, 1 to stop it. Each call has
        /// the stack aligned and its 32 bytes of shadow space; rcx, rdx, r8 to r11 and xmm0 to xmm5
        /// are as they were when it returns.</summary>
        public static byte[] TravelCheck(ulong original, ulong decide)
        {
            var code = new List<byte>();
            void Add(params byte[] bytes) => code.AddRange(bytes);
            void Address(ulong value)
            {
                var bytes = new byte[8];
                BinaryPrimitives.WriteUInt64LittleEndian(bytes, value);
                code.AddRange(bytes);
            }
            // push rcx; push rdx; push r8; push r9; push r10; push r11: 48 bytes, so the stack is
            // as it came (8 off 16) until sub rsp, 0x88 aligns it, with the shadow space at the
            // bottom and xmm0 to xmm5 above it.
            Add(0x51, 0x52, 0x41, 0x50, 0x41, 0x51, 0x41, 0x52, 0x41, 0x53);
            Add(0x48, 0x81, 0xEC, 0x88, 0x00, 0x00, 0x00);
            for (byte n = 0; n < 6; n++)
                Add(0x0F, 0x11, (byte)(0x44 | (n << 3)), 0x24, (byte)(0x20 + 0x10 * n)); // movups [rsp + d], xmmN
            Add(0x48, 0xA1);                                                     // mov rax, [original]
            Address(original);
            Add(0xFF, 0xD0);                                                     // call rax
            Add(0x84, 0xC0);                                                     // test al, al
            Add(0x74, 0x0C);                                                     // jz past the next two
            Add(0x48, 0xB8);                                                     // mov rax, decide
            Address(decide);
            Add(0xFF, 0xD0);                                                     // call rax
            for (byte n = 0; n < 6; n++)
                Add(0x0F, 0x10, (byte)(0x44 | (n << 3)), 0x24, (byte)(0x20 + 0x10 * n)); // movups xmmN, [rsp + d]
            Add(0x48, 0x81, 0xC4, 0x88, 0x00, 0x00, 0x00);                       // add rsp, 0x88
            Add(0x41, 0x5B, 0x41, 0x5A, 0x41, 0x59, 0x41, 0x58, 0x5A, 0x59);    // pop r11 ... pop rcx
            Add(0xC3);                                                           // ret
            return code.ToArray();
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern nint VirtualAlloc(nint address, nuint size, uint type, uint protect);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool VirtualProtect(nint address, nuint size, uint protect, out uint old);

        [DllImport("kernel32.dll")]
        static extern nint GetCurrentProcess();

        [DllImport("kernel32.dll")]
        static extern bool FlushInstructionCache(nint process, nint address, nuint size);

        /// <summary>The code put where it can run (memory of its own, never freed while the game
        /// runs), read-only once written; 0 when Windows gives none.</summary>
        public static nint Executable(byte[] code)
        {
            const uint Commit = 0x1000, Reserve = 0x2000, ReadWrite = 0x04, ExecuteRead = 0x20;
            nint at = VirtualAlloc(0, (nuint)code.Length, Commit | Reserve, ReadWrite);
            if (at == 0)
                return 0;
            Marshal.Copy(code, 0, at, code.Length);
            if (!VirtualProtect(at, (nuint)code.Length, ExecuteRead, out _))
                return 0;
            FlushInstructionCache(GetCurrentProcess(), at, (nuint)code.Length);
            return at;
        }
    }
}
