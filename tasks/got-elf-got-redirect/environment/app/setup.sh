#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

gcc -shared -fPIC -o "$ROOT/libmallocwrapper.so" "$ROOT/malloc_wrapper.c" -ldl
# test_program.c references logged_malloc (dynsym anchor); link the DSO so the symbol resolves.
# Main still calls libc malloc(); loading the .so does not interpose malloc without patching.
gcc -O2 -o "$ROOT/test_program" "$ROOT/test_program.c" \
  -L"$ROOT" -lmallocwrapper \
  -Wl,-rpath,"\$ORIGIN"
# Link the wrapper from a DSO so "logged_malloc" appears in the main binary's .dynsym
# (required for RELA r_sym indices). RPATH lets the patched/unpatched binary find the .so.
# -u forces an undefined dynamic symbol so logged_malloc is always in .dynsym
# (not only .symtab), which RELA r_sym indices require.
gcc -O2 -o "$ROOT/test_program_with_wrapper" "$ROOT/test_program.c" \
  -Wl,-u,logged_malloc \
  -L"$ROOT" -lmallocwrapper \
  -Wl,-rpath,"\$ORIGIN" \
  -Wl,--export-dynamic \
  -Wl,--export-dynamic-symbol=logged_malloc
