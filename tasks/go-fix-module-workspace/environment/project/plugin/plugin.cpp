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
