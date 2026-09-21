#include "xml_writer.h"
#include <fstream>
#include <sstream>

namespace {

std::string escapeAttr(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (char c : s) {
        switch (c) {
            case '&': out += "&amp;"; break;
            case '<': out += "&lt;"; break;
            case '>': out += "&gt;"; break;
            case '"': out += "&quot;"; break;
            default: out += c;
        }
    }
    return out;
}

void writeElement(std::ostringstream& out, const XmlElement& el, const XmlWriteOptions& opts, int depth) {
    for (int i = 0; i < depth; i++) out << opts.indent;
    out << "<" << el.tag;

    // Prefer the order attributes were first set (attrOrder); fall back to
    // whatever's in the map for any that were added directly to `attrs`
    // without going through setAttr (e.g. by hand-built code).
    for (const auto& name : el.attrOrder) {
        auto it = el.attrs.find(name);
        if (it == el.attrs.end()) continue;
        out << " " << name << "=\"" << escapeAttr(it->second) << "\"";
    }
    for (const auto& kv : el.attrs) {
        bool already = false;
        for (const auto& name : el.attrOrder) if (name == kv.first) { already = true; break; }
        if (!already) out << " " << kv.first << "=\"" << escapeAttr(kv.second) << "\"";
    }

    if (el.children.empty()) {
        out << "/>\n";
        return;
    }
    out << ">\n";
    for (const auto& child : el.children) writeElement(out, *child, opts, depth + 1);
    for (int i = 0; i < depth; i++) out << opts.indent;
    out << "</" << el.tag << ">\n";
}

} // namespace

std::string writeXmlString(const XmlElement& root, const XmlWriteOptions& opts) {
    std::ostringstream out;
    if (opts.declaration) out << "<?xml version=\"1.0\"?>\n";
    writeElement(out, root, opts, 0);
    return out.str();
}

void writeXmlFile(const std::string& path, const XmlElement& root, const XmlWriteOptions& opts) {
    std::ofstream f(path, std::ios::binary);
    f << writeXmlString(root, opts);
}
