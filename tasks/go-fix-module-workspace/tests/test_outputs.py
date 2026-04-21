import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path("/app")

# Baseline digests for non-CMake sources (task ships broken CMake only).
_IMMUTABLE_SOURCE_SHA256 = {
    "core/core.cpp": "2f5820abd77e149805b2a5742101a076f59c8b8f88a4722abd033b90a2b5395f",
    "core/core.h": "13ebac91f5fcaf8c68412684cc3d6a9e64744b3d4c59cbaa6753cca08cbe8c10",
    "engine/engine.cpp": "497979a3e5d28a2217fe62a8d349e8017fd5e95b413a40eeb64f49541bed7c0f",
    "engine/engine.h": "5b64a6acec2e7ed9b788b0d1cd856db00ed1d78e3f91569588c6b4241f0c7213",
    "plugin/plugin.cpp": "d1caf22bcde5129c0a632d0021e686c2ed4b8ea7340c24cef109a4bd511a9cec",
    "plugin/plugin.h": "7c674c1c6b4217df363ab614c76acffb1fc542918a12a9ee03ba3705d20fd99b",
    "app/main.cpp": "89cbae85a610b55f6673c33673d6fd096620eefe69dfd2e320b8e275f1d18887",
    "app/selfcheck.cpp": "327b6805c54db910fd2c1cc9fc25cbfe999800002607df887c12a6140e9a43e2",
    "app/build_profile.h.in": "4d1333da1e6ae6221507d23d3a1395956fc0da2093d19cc72410ee7064ee5ac5",
}

_CACHE = {}


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=240)


def _find_binary(build_dir, name):
    candidates = [
        build_dir / "bin" / name,
        build_dir / "app" / name,
        build_dir / name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _cmake_call_argument_texts(source: str, command: str) -> list[str]:
    """Return the inner text of each balanced `command(...)` CMake invocation."""
    bodies: list[str] = []
    pattern = re.compile(rf"{re.escape(command)}\s*\(", re.IGNORECASE)
    for m in pattern.finditer(source):
        start = m.end()
        depth = 1
        i = start
        while i < len(source) and depth > 0:
            c = source[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            i += 1
        bodies.append(source[start : i - 1])
    return bodies


def _object_library_named_plugin(plugin_cmake: str) -> bool:
    """True if `plugin` is declared as a CMake OBJECT library (layout-independent)."""
    return bool(
        re.search(
            r"add_library\s*\(\s*plugin\s+OBJECT\b",
            plugin_cmake,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )


def _target_link_body_first_target(body: str) -> str | None:
    m = re.match(r"\s*(\S+)", body)
    return m.group(1) if m else None


def _executable_links_plugin_in_target_link_libraries(app_cmake: str, exe: str) -> bool:
    """True if some `target_link_libraries(<exe> ...)` body lists the `plugin` target."""
    want = exe.lower()
    for body in _cmake_call_argument_texts(app_cmake, "target_link_libraries"):
        first = _target_link_body_first_target(body)
        if not first or first.lower() != want:
            continue
        if re.search(r"\bplugin\b", body, flags=re.IGNORECASE):
            return True
    return False


def _assert_target_compile_feature(
    cmake_text: str, target: str, visibility: str, std_feature: str, message: str
) -> None:
    """Require a target_compile_features(...) call, allowing CMake/Make formatting whitespace."""
    pat = rf"target_compile_features\s*\(\s*{re.escape(target)}\s+{re.escape(visibility)}\s+{re.escape(std_feature)}\s*\)"
    assert re.search(pat, cmake_text, flags=re.IGNORECASE | re.DOTALL), message


def _executables_consume_plugin_target(app_cmake: str) -> bool:
    """
    True if the app CMake consumes the `plugin` OBJECT library in a CMake-correct way:
    either `$<TARGET_OBJECTS:plugin>` / `TARGET_OBJECTS:plugin`, or each executable has a
    `target_link_libraries` invocation (multi-line bodies allowed) that names `plugin`.
    """
    if re.search(r"\$<\s*TARGET_OBJECTS\s*:\s*plugin\s*>", app_cmake, flags=re.IGNORECASE):
        return True
    if re.search(r"(?<!\w)TARGET_OBJECTS\s*:\s*plugin\b", app_cmake, flags=re.IGNORECASE):
        return True

    return all(
        _executable_links_plugin_in_target_link_libraries(app_cmake, exe)
        for exe in ("myapp", "selfcheck")
    )


def _build(build_type, generator="Unix Makefiles"):
    key = (build_type, generator)
    if key in _CACHE:
        return _CACHE[key]

    gen_tag = "ninja" if generator == "Ninja" else "make"
    build_dir = ROOT / f"build-{build_type.lower()}-{gen_tag}"
    if build_dir.exists():
        shutil.rmtree(build_dir)

    configure = _run(
        [
            "cmake",
            "-S",
            str(ROOT),
            "-B",
            str(build_dir),
            "-G",
            generator,
            f"-DCMAKE_BUILD_TYPE={build_type}",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        ],
        cwd=ROOT,
    )
    assert configure.returncode == 0, configure.stderr + configure.stdout

    build = _run(["cmake", "--build", str(build_dir), "-j4"], cwd=ROOT)
    assert build.returncode == 0, build.stderr + build.stdout

    myapp = _find_binary(build_dir, "myapp")
    selfcheck = _find_binary(build_dir, "selfcheck")
    assert myapp.exists(), f"missing binary: {myapp}"
    assert selfcheck.exists(), f"missing binary: {selfcheck}"

    _CACHE[key] = (build_dir, myapp, selfcheck)
    return _CACHE[key]


def _run_binary(path):
    result = subprocess.run([str(path)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()


def test_release_build_produces_binaries():
    """Verify a Release out-of-source build produces `myapp` and `selfcheck` binaries."""
    _, myapp, selfcheck = _build("Release")
    assert myapp.exists()
    assert selfcheck.exists()


def test_release_runtime_outputs():
    """Assert Release runs of `myapp` and `selfcheck` print the expected lines including profile."""
    _, myapp, selfcheck = _build("Release")
    assert _run_binary(myapp) == [
        "text: HELLO",
        "hash: 0x05e918d2",
        "valid: yes",
        "profile: Release",
    ]
    assert _run_binary(selfcheck) == ["selfcheck: ok (Release)"]


def test_debug_build_produces_binaries():
    """Verify a Debug out-of-source build produces `myapp` and `selfcheck` binaries."""
    _, myapp, selfcheck = _build("Debug")
    assert myapp.exists()
    assert selfcheck.exists()


def test_debug_runtime_outputs():
    """Assert Debug runs of `myapp` and `selfcheck` print the expected lines including profile."""
    _, myapp, selfcheck = _build("Debug")
    assert _run_binary(myapp) == [
        "text: HELLO",
        "hash: 0x05e918d2",
        "valid: yes",
        "profile: Debug",
    ]
    assert _run_binary(selfcheck) == ["selfcheck: ok (Debug)"]


def test_generated_headers_track_build_type():
    """Check generated `build_profile.h` in each build tree embeds Release vs Debug strings."""
    release_dir, _, _ = _build("Release")
    debug_dir, _, _ = _build("Debug")

    release_header = (release_dir / "app" / "build_profile.h").read_text()
    debug_header = (debug_dir / "app" / "build_profile.h").read_text()

    assert 'return "Release";' in release_header
    assert 'return "Debug";' in debug_header


def test_no_generated_headers_in_source_tree():
    """Ensure `build_profile.h` is not written into `/app` source (only under build directories)."""
    _build("Release")
    _build("Debug")
    assert not (ROOT / "app" / "build_profile.h").exists()


def test_compile_commands_show_cxx20():
    """Require `compile_commands.json` entries for engine and app to use a C++20 standard flag."""
    build_dir, _, _ = _build("Release")
    compile_commands = build_dir / "compile_commands.json"
    assert compile_commands.exists(), "compile_commands.json not generated"

    entries = json.loads(compile_commands.read_text())
    engine_entries = [e for e in entries if e["file"].endswith("/engine/engine.cpp")]
    app_entries = [e for e in entries if e["file"].endswith("/app/main.cpp")]
    assert engine_entries, "missing engine compile command"
    assert app_entries, "missing app compile command"

    def _cmd(entry):
        if "command" in entry:
            return entry["command"]
        return " ".join(entry.get("arguments", []))

    engine_cmd = "\n".join(_cmd(e) for e in engine_entries)
    app_cmd = "\n".join(_cmd(e) for e in app_entries)
    assert "-std=gnu++20" in engine_cmd or "-std=c++20" in engine_cmd
    assert "-std=gnu++20" in app_cmd or "-std=c++20" in app_cmd


def test_plugin_remains_object_library_and_is_consumed_as_objects():
    """
    Verify `plugin` stays an OBJECT library and that app executables consume it via CMake
    linking or `TARGET_OBJECTS`, using balanced-parse of `target_link_libraries` (not
    single-line string equality).
    """
    plugin_cmake = (ROOT / "plugin" / "CMakeLists.txt").read_text()
    app_cmake = (ROOT / "app" / "CMakeLists.txt").read_text()

    assert _object_library_named_plugin(plugin_cmake), "plugin must remain an OBJECT library"
    assert _executables_consume_plugin_target(
        app_cmake
    ), "myapp/selfcheck must link plugin or use TARGET_OBJECTS:plugin"


def test_engine_links_thread_support():
    """Require the engine target to link POSIX or CMake thread interfaces (`Threads::Threads` or pthread)."""
    engine_cmake = (ROOT / "engine" / "CMakeLists.txt").read_text()
    assert (
        "Threads::Threads" in engine_cmake
        or "pthread" in engine_cmake
    ), "engine target must link thread support"


def test_engine_uses_cmake_threads_package():
    """Require `find_package(Threads REQUIRED)` and linking `Threads::Threads` in engine CMake."""
    engine_cmake = (ROOT / "engine" / "CMakeLists.txt").read_text()
    assert "find_package(Threads REQUIRED)" in engine_cmake
    assert "Threads::Threads" in engine_cmake


def test_ninja_release_build_and_runtime():
    """Same as Release runtime checks but using the Ninja generator."""
    _, myapp, selfcheck = _build("Release", "Ninja")
    assert _run_binary(myapp) == [
        "text: HELLO",
        "hash: 0x05e918d2",
        "valid: yes",
        "profile: Release",
    ]
    assert _run_binary(selfcheck) == ["selfcheck: ok (Release)"]


def test_ninja_debug_build_and_runtime():
    """Same as Debug runtime checks but using the Ninja generator."""
    _, myapp, selfcheck = _build("Debug", "Ninja")
    assert _run_binary(myapp) == [
        "text: HELLO",
        "hash: 0x05e918d2",
        "valid: yes",
        "profile: Debug",
    ]
    assert _run_binary(selfcheck) == ["selfcheck: ok (Debug)"]


def test_core_headers_exported_and_engine_links_core():
    """Check `core` uses PUBLIC include dirs (multi-line allowed) and `engine` links `core`."""
    core_cmake = (ROOT / "core" / "CMakeLists.txt").read_text()
    engine_cmake = (ROOT / "engine" / "CMakeLists.txt").read_text().lower()

    assert re.search(
        r"target_include_directories\s*\(\s*core\s+public\b",
        core_cmake,
        flags=re.IGNORECASE | re.DOTALL,
    ), "core must export include directories with PUBLIC (multi-line CMake allowed)"
    assert "target_link_libraries(engine" in engine_cmake
    assert "core" in engine_cmake


def test_no_global_cxx_standard_setting():
    """Forbid project-wide `CMAKE_CXX_STANDARD` in the root CMakeLists (standards must be per-target)."""
    root_cmake = (ROOT / "CMakeLists.txt").read_text().lower()
    assert "cmake_cxx_standard" not in root_cmake


def test_target_compile_features_are_declared():
    """Assert each target declares the expected `target_compile_features` C++ standard levels."""
    core_cmake = (ROOT / "core" / "CMakeLists.txt").read_text()
    plugin_cmake = (ROOT / "plugin" / "CMakeLists.txt").read_text()
    engine_cmake = (ROOT / "engine" / "CMakeLists.txt").read_text()
    app_cmake = (ROOT / "app" / "CMakeLists.txt").read_text()

    _assert_target_compile_feature(
        core_cmake, "core", "PUBLIC", "cxx_std_17", "core must declare target_compile_features PUBLIC cxx_std_17"
    )
    _assert_target_compile_feature(
        plugin_cmake,
        "plugin",
        "PUBLIC",
        "cxx_std_17",
        "plugin must declare target_compile_features PUBLIC cxx_std_17",
    )
    _assert_target_compile_feature(
        engine_cmake,
        "engine",
        "PUBLIC",
        "cxx_std_20",
        "engine must declare target_compile_features PUBLIC cxx_std_20",
    )
    _assert_target_compile_feature(
        app_cmake,
        "myapp",
        "PRIVATE",
        "cxx_std_20",
        "myapp must declare target_compile_features PRIVATE cxx_std_20",
    )
    _assert_target_compile_feature(
        app_cmake,
        "selfcheck",
        "PRIVATE",
        "cxx_std_20",
        "selfcheck must declare target_compile_features PRIVATE cxx_std_20",
    )


def test_only_shipped_sources_unchanged_non_cmake():
    """Enforce CMake-only edits: every shipped .cpp/.h/.in file must match the task baseline bytes."""
    for rel, expected_hex in _IMMUTABLE_SOURCE_SHA256.items():
        path = ROOT / rel
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == expected_hex, f"unexpected change in {rel} (CMake-only task)"


def test_app_does_not_hardcode_plugin_include_path():
    """Disallow pointing app includes at the plugin source tree; use target propagation instead."""
    app_cmake = (ROOT / "app" / "CMakeLists.txt").read_text().lower()
    assert "${project_source_dir}/plugin" not in app_cmake
    assert "${cmake_source_dir}/plugin" not in app_cmake
