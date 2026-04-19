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
    _, myapp, selfcheck = _build("Release")
    assert myapp.exists()
    assert selfcheck.exists()


def test_release_runtime_outputs():
    _, myapp, selfcheck = _build("Release")
    assert _run_binary(myapp) == [
        "text: HELLO",
        "hash: 0x05e918d2",
        "valid: yes",
        "profile: Release",
    ]
    assert _run_binary(selfcheck) == ["selfcheck: ok (Release)"]


def test_debug_build_produces_binaries():
    _, myapp, selfcheck = _build("Debug")
    assert myapp.exists()
    assert selfcheck.exists()


def test_debug_runtime_outputs():
    _, myapp, selfcheck = _build("Debug")
    assert _run_binary(myapp) == [
        "text: HELLO",
        "hash: 0x05e918d2",
        "valid: yes",
        "profile: Debug",
    ]
    assert _run_binary(selfcheck) == ["selfcheck: ok (Debug)"]


def test_generated_headers_track_build_type():
    release_dir, _, _ = _build("Release")
    debug_dir, _, _ = _build("Debug")

    release_header = (release_dir / "app" / "build_profile.h").read_text()
    debug_header = (debug_dir / "app" / "build_profile.h").read_text()

    assert 'return "Release";' in release_header
    assert 'return "Debug";' in debug_header


def test_no_generated_headers_in_source_tree():
    _build("Release")
    _build("Debug")
    assert not (ROOT / "app" / "build_profile.h").exists()


def test_compile_commands_show_cxx20():
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
    plugin_cmake = (ROOT / "plugin" / "CMakeLists.txt").read_text()
    app_cmake = (ROOT / "app" / "CMakeLists.txt").read_text()

    assert "add_library(plugin OBJECT" in plugin_cmake
    assert (
        "TARGET_OBJECTS:plugin" in app_cmake
        or "target_link_libraries(myapp PRIVATE engine plugin)" in app_cmake
    )


def test_engine_links_thread_support():
    engine_cmake = (ROOT / "engine" / "CMakeLists.txt").read_text()
    assert (
        "Threads::Threads" in engine_cmake
        or "pthread" in engine_cmake
    ), "engine target must link thread support"


def test_engine_uses_cmake_threads_package():
    engine_cmake = (ROOT / "engine" / "CMakeLists.txt").read_text()
    assert "find_package(Threads REQUIRED)" in engine_cmake
    assert "Threads::Threads" in engine_cmake


def test_ninja_release_build_and_runtime():
    _, myapp, selfcheck = _build("Release", "Ninja")
    assert _run_binary(myapp) == [
        "text: HELLO",
        "hash: 0x05e918d2",
        "valid: yes",
        "profile: Release",
    ]
    assert _run_binary(selfcheck) == ["selfcheck: ok (Release)"]


def test_ninja_debug_build_and_runtime():
    _, myapp, selfcheck = _build("Debug", "Ninja")
    assert _run_binary(myapp) == [
        "text: HELLO",
        "hash: 0x05e918d2",
        "valid: yes",
        "profile: Debug",
    ]
    assert _run_binary(selfcheck) == ["selfcheck: ok (Debug)"]


def test_core_headers_exported_and_engine_links_core():
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
    root_cmake = (ROOT / "CMakeLists.txt").read_text().lower()
    assert "cmake_cxx_standard" not in root_cmake


def test_target_compile_features_are_declared():
    core_cmake = (ROOT / "core" / "CMakeLists.txt").read_text().lower()
    plugin_cmake = (ROOT / "plugin" / "CMakeLists.txt").read_text().lower()
    engine_cmake = (ROOT / "engine" / "CMakeLists.txt").read_text().lower()
    app_cmake = (ROOT / "app" / "CMakeLists.txt").read_text().lower()

    assert "target_compile_features(core public cxx_std_17)" in core_cmake
    assert "target_compile_features(plugin public cxx_std_17)" in plugin_cmake
    assert "target_compile_features(engine public cxx_std_20)" in engine_cmake
    assert "target_compile_features(myapp private cxx_std_20)" in app_cmake
    assert "target_compile_features(selfcheck private cxx_std_20)" in app_cmake


def test_app_does_not_hardcode_plugin_include_path():
    app_cmake = (ROOT / "app" / "CMakeLists.txt").read_text().lower()
    assert "${project_source_dir}/plugin" not in app_cmake
