#!/bin/bash
set -e
cd /app

cat > CMakeLists.txt <<'EOF_ROOT'
cmake_minimum_required(VERSION 3.16)
project(CryptoEngine CXX)

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

add_subdirectory(core)
add_subdirectory(plugin)
add_subdirectory(engine)
add_subdirectory(app)
EOF_ROOT

cat > core/CMakeLists.txt <<'EOF_CORE'
add_library(core STATIC core.cpp)
target_include_directories(core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_features(core PUBLIC cxx_std_17)
EOF_CORE

cat > engine/CMakeLists.txt <<'EOF_ENGINE'
add_library(engine STATIC engine.cpp)
target_include_directories(engine PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_features(engine PUBLIC cxx_std_20)
find_package(Threads REQUIRED)
target_link_libraries(engine PUBLIC core Threads::Threads)
EOF_ENGINE

cat > plugin/CMakeLists.txt <<'EOF_PLUGIN'
add_library(plugin OBJECT plugin.cpp)
target_include_directories(plugin PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_features(plugin PUBLIC cxx_std_17)
EOF_PLUGIN

cat > app/CMakeLists.txt <<'EOF_APP'
configure_file(build_profile.h.in ${CMAKE_CURRENT_BINARY_DIR}/build_profile.h @ONLY)

add_executable(myapp main.cpp)
add_executable(selfcheck selfcheck.cpp)

target_include_directories(myapp PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
target_include_directories(selfcheck PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
target_compile_features(myapp PRIVATE cxx_std_20)
target_compile_features(selfcheck PRIVATE cxx_std_20)

target_link_libraries(myapp PRIVATE engine plugin)
target_link_libraries(selfcheck PRIVATE engine plugin)
EOF_APP

cmake -S /app -B /app/build -G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Release
cmake --build /app/build -j"$(nproc)"
