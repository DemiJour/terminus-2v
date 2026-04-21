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
