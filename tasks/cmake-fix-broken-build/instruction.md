# Repair a Regressed CMake Build

I’ve got a small C++ project in `/app` that used to build fine, but after splitting it into `core`, `engine`, `plugin`, and `app`, the CMake setup got messy. The source files themselves are fine; the breakage is in the CMake wiring.

Please fix the build configuration using only `CMakeLists.txt` changes. Don’t edit any `.cpp`, `.h`, or `.in` files.

What I need working again is pretty straightforward from the outside:
- clean out-of-source builds for both `Release` and `Debug`
- clean builds should also work with the `Ninja` generator for both `Release` and `Debug`
- both executables (`myapp` and `selfcheck`) must build and run
- `myapp` should print:

```
text: HELLO
hash: 0x05e918d2
valid: yes
profile: <build type>
```

- `selfcheck` should print:

```
selfcheck: ok (<build type>)
```

The build-profile header should be generated per build type (so Release and Debug runs show the right profile). Also make sure dependency wiring is clean: `core` headers should be exported correctly, and `engine` should declare its dependency on `core` and thread support by using CMake’s Threads package target.

Please keep language standard settings target-scoped (per target compile features) rather than a single global project-wide C++ standard. Concretely:

- Do **not** set `CMAKE_CXX_STANDARD` (or similar) at the top level; remove any project-wide C++ standard if present.
- The **`core`** and **`plugin`** libraries are small and only need **C++17**: add `target_compile_features(core PUBLIC cxx_std_17)` and `target_compile_features(plugin PUBLIC cxx_std_17)`.
- The **`engine`** static library and both executables use C++20 features in the existing sources: add `target_compile_features(engine PUBLIC cxx_std_20)`, `target_compile_features(myapp PRIVATE cxx_std_20)`, and `target_compile_features(selfcheck PRIVATE cxx_std_20)` so those translation units build as C++20 (this should show up in `compile_commands.json` for `engine/engine.cpp` and `app/main.cpp` when you export compile commands).

Export `core`’s public headers with `target_include_directories(core PUBLIC ...)`, and have `engine` link to the `core` target (so include paths propagate). You may split CMake arguments across lines; keep **`core`** and **`PUBLIC`** as the first two arguments to `target_include_directories` for the `core` target.

For threads, in **`engine/CMakeLists.txt`** call `find_package(Threads REQUIRED)` and link **`Threads::Threads`** to `engine` (that satisfies “CMake’s Threads package target”).

One more thing: keep `plugin` as an object-library-style component in the final setup.
