We ship a stress binary that hammers `malloc` and a small wrapper object file that defines `logged_malloc`. I need a **Go** tool that edits an existing **64-bit little-endian ELF executable** on disk so PLT/GOT style relocations for `malloc` are retargeted to `logged_malloc` instead, without rebuilding from source.

Ship the implementation under the module already laid out in `/app` (see `/app/go.mod`). The CLI must be buildable with:

`cd /app && go build -o /app/got-patch ./cmd/got-patch`

CLI usage (exactly two or three arguments after the program name, i.e. three or four total `argv` tokens):

`/app/got-patch <input_elf> <output_elf> [wrapper_symbol]`

`wrapper_symbol` defaults to `logged_malloc` when omitted.

Hard rules:

- Parsing and patching must be **your own layout code** using `encoding/binary` (and normal stdlib I/O). Do **not** import `debug/elf`, other bundled object loaders in `debug/*` used as libraries (`debug/macho`, `debug/pe`, …), vendored ELF parsers, or non-stdlib module imports (for example paths under `github.com/`).
- The first **64 bytes** of the output ELF must match the input byte-for-byte (only edit relocation records and related bytes elsewhere is fine only if required, but the on-disk ELF header prefix through byte 63 must be identical).
- Output file mode must be executable (`0755`).
- When the wrapper symbol cannot be found or no applicable relocation targets `malloc`, exit non-zero and print a clear message to stderr mentioning the missing symbol or relocations.
- When patching succeeds, print human-readable lines to stderr or stdout that mention **symbols** and **relocations** (so a human can see what was touched), including relocation **type** numbers for each patched slot.

Build helpers and the C harness live in `/app` (`/app/setup.sh`, `/app/test_program.c`, `/app/malloc_wrapper.c`). Run `/app/setup.sh` before trying the patcher; it builds `/app/libmallocwrapper.so` and `/app/test_program_with_wrapper` linked against that shared object (with an RPATH so the binary can load it from `/app`) so `logged_malloc` is present in **`.dynsym`** alongside libc `malloc` — that is what RELA `r_sym` indices refer to.

Success for us: after `/app/setup.sh`, your tool patches `/app/test_program_with_wrapper` to `/app/test_program_patched`, and running `/app/test_program_patched` shows at least **100** lines containing the exact substring `MALLOC INTERCEPTED` in combined stdout/stderr. The unpatched `/app/test_program_with_wrapper` must **not** print that substring when executed normally.
