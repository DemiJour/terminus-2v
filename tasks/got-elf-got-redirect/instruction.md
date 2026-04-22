Please implement a **Go** tool under `/app` (see `/app/go.mod`) that edits an existing **64-bit little-endian ELF** executable on disk so that `R_X86_64_JUMP_SLOT` and `R_X86_64_GLOB_DAT` relocations that target **`malloc`** instead target a **wrapper** symbol (default **`logged_malloc`**). The goal is to redirect the GOT/PLT path used for dynamic `malloc` calls **without** rebuilding the program from source.

**Leave the C harness as-is.** The verifier expects `/app/setup.sh`, `malloc_wrapper.c`, `test_program.c`, and the small extra `test_program_*.c` sources to keep building unchanged. Implement your solution in **Go only** (under `/app`, typically by replacing the stub in `cmd/got-patch`); do not “simplify” the harness or drop link flags from `setup.sh`.

The environment ships a stress binary and a tiny shared object that defines `logged_malloc`. Run `/app/setup.sh` first; it builds `/app/libmallocwrapper.so`, `/app/test_program_with_wrapper`, and two extra harness binaries used only to check failure modes (`/app/test_elf_no_malloc_sym`, `/app/test_elf_static_malloc`).

**Practical outline (you still own the details):** read the ELF64 header and program/section tables with `encoding/binary`; locate dynamic symbols (`.dynsym` / `.dynstr`) and relocation sections (`SHT_RELA` / `SHT_REL`, often `.rela.plt` / `.rela.dyn`). For each relocation whose type is `R_X86_64_JUMP_SLOT` (7) or `R_X86_64_GLOB_DAT` (6) and whose symbol is `malloc` (ignore `@GLIBC_…` version suffixes when matching the name), either rewrite the relocation’s symbol index to the wrapper’s **`.dynsym`** index, or—if the wrapper is only resolvable at a concrete address—write that address into the GOT slot at the file offset that corresponds to the relocation’s `r_offset` (VMA → file mapping via `PT_LOAD` or section headers). Copy the input bytes, apply patches, then write the output with mode `0755` and restore the first 64 bytes from the original file.

Build your CLI with:

`cd /app && go build -o /app/got-patch ./cmd/got-patch`

## How the CLI should work

Usage (three or four `argv` entries total, i.e. two or three arguments after the program name):

`/app/got-patch <input_elf> <output_elf> [wrapper_symbol]`

If `wrapper_symbol` is omitted, treat it as `logged_malloc`.

## Implementation constraints

- Parse and patch the ELF with **your own layout logic** using `encoding/binary` and normal stdlib I/O. Do **not** import `debug/elf`, other `debug/*` loaders used as libraries (`debug/macho`, `debug/pe`, …), vendored ELF parsers, or **non-stdlib** modules. Third-party import path prefixes such as `github.com/`, `golang.org/x/`, and `google.golang.org/` are not allowed.
- The first **64 bytes** of the output file must match the input byte-for-byte (only bytes that must change for relocation patching may differ elsewhere).
- The output file’s permission bits must be **exactly** `0755` (`rwxr-xr-x`).

## When patching cannot succeed

Exit with a **non-zero** status and print a **clear message to stderr** (stdout is fine too, but stderr is expected). The verifier builds separate ELFs for each case; your wording should make the cause obvious:

1. **Wrapper missing** — the named wrapper symbol cannot be used as the replacement target (for example it is not present in the dynamic symbol table and you cannot apply the fallback your design uses). Say that the **wrapper** / replacement symbol is the problem, not `malloc` itself.
2. **No `malloc` to retarget** — the input does not expose a dynamic **`malloc`** symbol your tool can treat as the source of the relocations (the harness for this is `/app/test_elf_no_malloc_sym`). Say that **`malloc`** is missing or not visible for retargeting.
3. **No applicable relocations** — `malloc` may appear in symbol tables, but there are no **`R_X86_64_JUMP_SLOT`** or **`R_X86_64_GLOB_DAT`** relocations referring to it (the harness for this is `/app/test_elf_static_malloc`). Say that there are **no** such **relocations** (or equivalent plain language).

These three cases must be distinguishable from each other in the message text.

## On success

Emit human-readable lines that mention **symbols** and **relocations**, including relocation **type** numbers for each patched slot. Stderr must also include:

- a line **`wrote patched ELF to`** the output path **with file mode** `0755` or `0o755`, and  
- a line naming **`R_X86_64_JUMP_SLOT`** and **`R_X86_64_GLOB_DAT`** with their numeric type constants.

## What “done” looks like

- After `/app/setup.sh`, patching `/app/test_program_with_wrapper` → `/app/test_program_patched` succeeds.
- Running `/app/test_program_patched` prints at least **120** lines containing the exact substring `MALLOC INTERCEPTED` in combined stdout/stderr.
- Running the **unpatched** `/app/test_program_with_wrapper` must **not** print `MALLOC INTERCEPTED`.

You may add or edit Go sources under `/app` as needed, provided you follow the rules above and satisfy the verifier.
