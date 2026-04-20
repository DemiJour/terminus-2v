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
