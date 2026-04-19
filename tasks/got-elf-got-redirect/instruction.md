# Retarget `malloc` GOT/RELA slots in a 64-bit ELF (Go)

We ship a stress binary that hammers `malloc` and a small shared object that defines `logged_malloc`. Build a **Go** tool that edits an existing **64-bit little-endian ELF** executable on disk so PLT/GOT-style relocations for `malloc` point at `logged_malloc` instead, **without** rebuilding the program from source.

Implement under the module in `/app` (`/app/go.mod`). The CLI must build with:

`cd /app && go build -o /app/got-patch ./cmd/got-patch`

## CLI

Usage (two or three arguments after `argv[0]`, i.e. three or four total argv tokens):

`/app/got-patch <input_elf> <output_elf> [wrapper_symbol]`

`wrapper_symbol` defaults to `logged_malloc` when omitted.

## Hard rules

- Parsing and patching must be **your own layout code** using `encoding/binary` (and normal stdlib I/O). Do **not** import `debug/elf`, other `debug/*` object loaders used as libraries (`debug/macho`, `debug/pe`, …), vendored ELF parsers, or **non-stdlib** module imports. Forbidden import path prefixes include `github.com/`, `golang.org/x/`, and `google.golang.org/` (and similarly for other third-party module hosts).
- The first **64 bytes** of the output ELF must match the input byte-for-byte (only relocation-related bytes elsewhere may change when required).
- Output file mode must be **exactly** `0755` (`rwxr-xr-x`).
- If the wrapper symbol cannot be found, **no** `malloc` symbol is visible, or there are **no applicable** `R_X86_64_JUMP_SLOT` / `R_X86_64_GLOB_DAT` relocations targeting `malloc`, exit non-zero and print a clear stderr message that distinguishes missing symbol vs. missing relocations.
- On success, print human-readable lines (stdout or stderr) that mention **symbols** and **relocations**, including relocation **type** numbers for each patched slot. Stderr must also include a line **`wrote patched ELF to`** the output path **with file mode** `0755` (or `0o755`), and a line naming **`R_X86_64_JUMP_SLOT`** and **`R_X86_64_GLOB_DAT`** with their numeric type constants.

## Harness

Helpers live in `/app` (`/app/setup.sh`, `/app/test_program.c`, `/app/malloc_wrapper.c`). Run `/app/setup.sh` first; it builds `/app/libmallocwrapper.so` and `/app/test_program_with_wrapper` (RPATH `$ORIGIN`) so `logged_malloc` appears in **`.dynsym`** next to libc `malloc` for RELA `r_sym` indices.

## Success criteria (what must work)

- After `/app/setup.sh`, your tool patches `/app/test_program_with_wrapper` → `/app/test_program_patched`.
- Running `/app/test_program_patched` prints at least **120** lines containing the exact substring `MALLOC INTERCEPTED` in combined stdout/stderr.
- Running the **unpatched** `/app/test_program_with_wrapper` must **not** print `MALLOC INTERCEPTED`.

## Scope

You may add or edit Go sources under `/app` as needed, provided you follow the rules above and satisfy the verifier.
