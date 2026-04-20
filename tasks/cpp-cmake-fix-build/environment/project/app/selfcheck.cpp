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
