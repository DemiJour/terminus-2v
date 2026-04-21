# Repair a regressed CMake build

I’ve got a small C++ project in `/app` that used to build fine, but after splitting it into `core`, `engine`, `plugin`, and `app`, the CMake setup got messy. The source files themselves are fine; the breakage is in the CMake wiring.

Please fix the build configuration using only `CMakeLists.txt` changes. Don’t edit any `.cpp`, `.h`, or `.in` files.

## Success criteria (what must work)

- **Out-of-source builds** for **Release** and **Debug** succeed, and the same holds when using the **Ninja** generator.
- **Both programs** `myapp` and `selfcheck` **build and run** for each configuration above.
- **`myapp` stdout** (exact lines):

```
text: HELLO
hash: 0x05e918d2
valid: yes
profile: <build type>
```

- **`selfcheck` stdout** (exact line):

```
selfcheck: ok (<build type>)
```

  where `<build type>` is `Release` or `Debug` matching the configuration you built.

- **Build profile in the binary**: the profile string in that output must reflect the active build type. The project ships `/app/app/build_profile.h.in`; the configured header must appear in the **build tree** under the exact filename **`build_profile.h`** (one generated file per build directory, not committed under `/app/app` in the source tree).

- **Headers and dependencies**
  - Targets that include **`core`** headers must obtain them through **`core`’s usage requirements** (dependents should not need extra manual include roots for `core`).
  - **`engine`** must **link `core`** for headers and symbols, and must use **CMake’s portable threading integration** (the imported threading target CMake defines for `find_package(Threads)`), not only ad‑hoc raw linker flags, so the build stays portable.
  - **`plugin`** must remain an **object-style library** in the final graph, and **`myapp` / `selfcheck`** must **pull in `plugin`’s objects** through normal CMake target relationships (not by wiring include paths straight to the plugin source tree on the app targets).

- **C++ language levels**
  - **`core`** and **`plugin`** only need **C++17**-level language features for their sources.
  - **`engine`**, **`myapp`**, and **`selfcheck`** need **C++20** for their sources (when compile commands are exported, the compile line for `/app/engine/engine.cpp` and `/app/app/main.cpp` should reflect a C++20 language mode).
  - The **root** project must **not** pin a single global C++ standard for the whole tree; language levels must be **scoped to the targets** that need them.

## Scope

You may reorganize targets, `configure_file`, link lines, and generator choices as long as the outcomes above hold and you only change **`CMakeLists.txt`** files.
