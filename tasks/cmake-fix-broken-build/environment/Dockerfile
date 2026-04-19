# Pinned digest for ubuntu:24.04 (multi-arch manifest); resolves reproducibly per platform.
FROM ubuntu:24.04@sha256:c4a8d5503dfb2a3eb8ab5f807da5bc69a85730fb49b5cfca2330194ebcc41c7b

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-pip cmake g++ make ninja-build \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir -p core engine plugin app

RUN cat > core/core.h <<'EOF_CORE_H'
#pragma once
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace core {
std::uint32_t hash(std::string_view s);
std::vector<int> encode(std::string_view s);
std::string decode(const std::vector<int>& v);
}
EOF_CORE_H

RUN cat > core/core.cpp <<'EOF_CORE_CPP'
#include "core.h"

namespace core {
std::uint32_t hash(std::string_view s) {
    std::uint32_t h = 0;
    for (unsigned char c : s) {
        h = h * 31u + static_cast<std::uint32_t>(c);
    }
    return h & 0x7fffffffu;
}

std::vector<int> encode(std::string_view s) {
    std::vector<int> v;
    v.reserve(s.size());
    for (unsigned char c : s) {
        v.push_back(static_cast<int>(c ^ 42));
    }
    return v;
}

std::string decode(const std::vector<int>& v) {
    std::string s;
    s.reserve(v.size());
    for (int c : v) {
        s += static_cast<char>(c ^ 42);
    }
    return s;
}
}
EOF_CORE_CPP

RUN cat > engine/engine.h <<'EOF_ENGINE_H'
#pragma once
#include <optional>
#include <string>
#include <tuple>

namespace engine {
std::tuple<std::string, int> process(const std::string& input);
std::optional<std::string> validate(const std::string& input);
}
EOF_ENGINE_H

RUN cat > engine/engine.cpp <<'EOF_ENGINE_CPP'
#include "engine.h"
#include "core.h"
#include <algorithm>
#include <cctype>
#include <span>
#include <thread>

namespace {
bool has_nonzero(std::span<const int> values) {
    for (int value : values) {
        if (value != 0) {
            return true;
        }
    }
    return false;
}
}

namespace engine {
std::tuple<std::string, int> process(const std::string& input) {
    auto encoded = core::encode(input);
    auto decoded = core::decode(encoded);
    int h = static_cast<int>(core::hash(decoded));

    std::string upper(decoded.size(), '\0');
    std::thread worker([&]() {
        std::transform(decoded.begin(), decoded.end(), upper.begin(), [](unsigned char c) {
            return static_cast<char>(std::toupper(c));
        });
    });
    worker.join();

    if (!has_nonzero(std::span<const int>(encoded.data(), encoded.size()))) {
        return {upper, h};
    }
    return {upper, h};
}

std::optional<std::string> validate(const std::string& input) {
    if (input.empty()) {
        return std::nullopt;
    }
    auto [text, h] = process(input);
    if (h == 0) {
        return std::nullopt;
    }
    return text;
}
}
EOF_ENGINE_CPP

RUN cat > plugin/plugin.h <<'EOF_PLUGIN_H'
#pragma once
#include <string>

std::string to_hex(int value);
std::string banner(const std::string& profile);
EOF_PLUGIN_H

RUN cat > plugin/plugin.cpp <<'EOF_PLUGIN_CPP'
#include "plugin.h"
#include <iomanip>
#include <sstream>

std::string to_hex(int value) {
    std::stringstream ss;
    ss << "0x" << std::hex << std::setfill('0') << std::setw(8) << value;
    return ss.str();
}

std::string banner(const std::string& profile) {
    return "profile: " + profile;
}
EOF_PLUGIN_CPP

RUN cat > app/main.cpp <<'EOF_MAIN_CPP'
#include <iostream>
#include "engine.h"
#include "plugin.h"
#include "build_profile.h"

int main() {
    auto result = engine::validate("hello");
    if (result.has_value()) {
        auto [text, h] = engine::process("hello");
        std::cout << "text: " << text << "\n";
        std::cout << "hash: " << to_hex(h) << "\n";
        if constexpr (sizeof(int) >= 4) {
            std::cout << "valid: yes\n";
        }
        std::cout << banner(std::string(build_profile())) << "\n";
    }
    return 0;
}
EOF_MAIN_CPP

RUN cat > app/selfcheck.cpp <<'EOF_SELFCHECK_CPP'
#include <iostream>
#include "engine.h"
#include "plugin.h"
#include "build_profile.h"

int main() {
    auto check = engine::validate("harbor");
    if (!check.has_value()) {
        return 2;
    }

    auto [text, hash] = engine::process("harbor");
    if (text != "HARBOR") {
        return 3;
    }

    if (to_hex(hash).empty()) {
        return 4;
    }

    std::cout << "selfcheck: ok (" << build_profile() << ")\n";
    return 0;
}
EOF_SELFCHECK_CPP

RUN cat > app/build_profile.h.in <<'EOF_PROFILE_IN'
#pragma once
#include <string_view>

inline std::string_view build_profile() {
    return "@CMAKE_BUILD_TYPE@";
}
EOF_PROFILE_IN

RUN cat > CMakeLists.txt <<'EOF_ROOT_CMAKE'
cmake_minimum_required(VERSION 3.16)
project(CryptoEngine CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_subdirectory(app)
add_subdirectory(core)
add_subdirectory(engine)
add_subdirectory(plugin)
EOF_ROOT_CMAKE

RUN cat > core/CMakeLists.txt <<'EOF_CORE_CMAKE'
add_library(core STATIC core.cpp)
target_include_directories(core PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
EOF_CORE_CMAKE

RUN cat > engine/CMakeLists.txt <<'EOF_ENGINE_CMAKE'
add_library(engine STATIC engine.cpp)
target_include_directories(engine PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
EOF_ENGINE_CMAKE

RUN cat > plugin/CMakeLists.txt <<'EOF_PLUGIN_CMAKE'
add_library(plugin OBJECT plugin.cpp)
target_include_directories(plugin PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
EOF_PLUGIN_CMAKE

RUN cat > app/CMakeLists.txt <<'EOF_APP_CMAKE'
add_executable(myapp main.cpp)
target_link_libraries(myapp PRIVATE engine)
EOF_APP_CMAKE
