#pragma once
#include <optional>
#include <string>
#include <tuple>

namespace engine {
std::tuple<std::string, int> process(const std::string& input);
std::optional<std::string> validate(const std::string& input);
}
