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
