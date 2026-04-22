#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

gcc -shared -fPIC -o "$ROOT/libmallocwrapper.so" "$ROOT/malloc_wrapper.c" -ldl
# Link by explicit path to the .so so the wrapper is always pulled in (avoids --as-needed
# dropping -lmallocwrapper on some toolchains). Do not build a separate test_program binary:
# the verifier only needs test_program_with_wrapper.
# -u keeps logged_malloc in .dynsym for RELA r_sym indices; RPATH finds the DSO at runtime.
gcc -O2 -o "$ROOT/test_program_with_wrapper" "$ROOT/test_program.c" \
  "$ROOT/libmallocwrapper.so" \
  -Wl,-u,logged_malloc \
  -Wl,-rpath,"\$ORIGIN" \
  -Wl,--export-dynamic \
  -Wl,--export-dynamic-symbol=logged_malloc

# Harness ELFs for negative tests (error messages must match instruction.md).
gcc -O2 -o "$ROOT/test_elf_no_malloc_sym" "$ROOT/test_program_minimal.c"
gcc -static -O2 -o "$ROOT/test_elf_static_malloc" "$ROOT/test_program_malloc_only.c"
