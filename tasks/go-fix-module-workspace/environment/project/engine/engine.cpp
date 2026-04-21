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
