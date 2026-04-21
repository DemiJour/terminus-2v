import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path("/app")

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


def _compile_command_texts_for_suffix(entries: list, path_suffix: str) -> str:
    """Join compile command strings for entries whose file path ends with path_suffix."""
    matched = [e for e in entries if e["file"].endswith(path_suffix)]
    assert matched, f"missing compile command for *{path_suffix}"

    def _cmd(entry):
        if "command" in entry:
            return entry["command"]
        return " ".join(entry.get("arguments", []))

    return "\n".join(_cmd(e) for e in matched)


def _compile_command_uses_cpp17_mode(cmd: str) -> bool:
    """
    True when the compile line is not forcing C++20+ and either names C++17 explicitly or omits
    -std= so a typical GCC default (gnu++17) satisfies CMake's cxx_std_17 without a redundant flag.
    """
    if "-std=gnu++20" in cmd or "-std=c++20" in cmd:
        return False
    if "-std=gnu++2a" in cmd or "-std=c++2a" in cmd:
        return False
    if "-std=gnu++23" in cmd or "-std=c++23" in cmd:
        return False
    if (
        "-std=gnu++17" in cmd
        or "-std=c++17" in cmd
        or "-std=gnu++1z" in cmd
        or "-std=c++1z" in cmd
    ):
        return True
    if "-std=" in cmd:
        return False
    return True


def _compile_command_uses_cpp20_mode(cmd: str) -> bool:
    """True when the compile line explicitly selects C++20 or newer."""
    if "-std=gnu++20" in cmd or "-std=c++20" in cmd:
        return True
    if "-std=gnu++2a" in cmd or "-std=c++2a" in cmd:
        return True
    if "-std=gnu++23" in cmd or "-std=c++23" in cmd:
        return True
    return False


def test_compile_commands_reflect_per_target_standards():
    """Verify compile_commands.json shows C++17 for core/plugin and C++20 for engine and app sources."""
    build_dir, _, _ = _build("Release")
    compile_commands = build_dir / "compile_commands.json"
    assert compile_commands.exists(), "compile_commands.json not generated"

    entries = json.loads(compile_commands.read_text())

    core_cmd = _compile_command_texts_for_suffix(entries, "/core/core.cpp")
    plugin_cmd = _compile_command_texts_for_suffix(entries, "/plugin/plugin.cpp")
    engine_cmd = _compile_command_texts_for_suffix(entries, "/engine/engine.cpp")
    main_cmd = _compile_command_texts_for_suffix(entries, "/app/main.cpp")
    selfcheck_cmd = _compile_command_texts_for_suffix(entries, "/app/selfcheck.cpp")

    assert _compile_command_uses_cpp17_mode(core_cmd), core_cmd
    assert _compile_command_uses_cpp17_mode(plugin_cmd), plugin_cmd
    assert _compile_command_uses_cpp20_mode(engine_cmd), engine_cmd
    assert _compile_command_uses_cpp20_mode(main_cmd), main_cmd
    assert _compile_command_uses_cpp20_mode(selfcheck_cmd), selfcheck_cmd


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


def test_app_does_not_hardcode_plugin_include_path():
    """Disallow pointing app includes at the plugin source tree; use target propagation instead."""
    app_cmake = (ROOT / "app" / "CMakeLists.txt").read_text().lower()
    assert "${project_source_dir}/plugin" not in app_cmake
    assert "${cmake_source_dir}/plugin" not in app_cmake
