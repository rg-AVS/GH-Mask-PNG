// cli.h -- a 60-line argument reader shared by every tool here, so none of
// them grows its own half-parser. Header-only on purpose: it is small
// enough that linking a .cpp for it would cost more than it saves.
#pragma once
#include <algorithm>
#include <stdexcept>
#include <string>
#include <vector>

struct Cli {
    std::vector<std::string> args;
    std::vector<std::string> positional;

    Cli(int argc, char** argv) {
        for (int i = 1; i < argc; i++) args.push_back(argv[i]);
        for (size_t i = 0; i < args.size(); i++) {
            if (args[i].rfind("--", 0) == 0) {
                // Flags that take a value swallow the next token; bare flags do not.
                if (i + 1 < args.size() && args[i + 1].rfind("--", 0) != 0) i++;
            } else {
                positional.push_back(args[i]);
            }
        }
    }

    bool has(const std::string& flag) const {
        return std::find(args.begin(), args.end(), flag) != args.end();
    }

    std::string str(const std::string& flag, const std::string& def) const {
        auto it = std::find(args.begin(), args.end(), flag);
        if (it == args.end() || ++it == args.end()) return def;
        return *it;
    }

    double num(const std::string& flag, double def) const {
        std::string s = str(flag, "");
        if (s.empty()) return def;
        try { return std::stod(s); } catch (...) {
            throw std::runtime_error(flag + " expects a number, got '" + s + "'");
        }
    }

    int integer(const std::string& flag, int def) const { return (int)num(flag, def); }
};

// "1920x1080" -> 1920, 1080.
inline void parseRes(const std::string& s, int& w, int& h) {
    size_t x = s.find_first_of("xX*");
    if (x == std::string::npos) throw std::runtime_error("resolution must look like 1920x1080, got '" + s + "'");
    w = std::stoi(s.substr(0, x));
    h = std::stoi(s.substr(x + 1));
    if (w <= 0 || h <= 0) throw std::runtime_error("resolution must be positive, got '" + s + "'");
}

inline std::string sanitizeFilename(std::string s) {
    for (auto& c : s) if (c == ' ' || c == '/' || c == '\\' || c == ':') c = '_';
    return s.empty() ? "mask" : s;
}
