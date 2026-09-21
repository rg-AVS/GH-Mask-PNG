#include "xml_reader.h"
#include <cctype>
#include <cstring>
#include <fstream>
#include <sstream>
#include <stdexcept>

std::string XmlElement::attr(const std::string& name, const std::string& def) const {
    auto it = attrs.find(name);
    return it == attrs.end() ? def : it->second;
}
double XmlElement::attrD(const std::string& name, double def) const {
    auto it = attrs.find(name);
    if (it == attrs.end() || it->second.empty()) return def;
    try { return std::stod(it->second); } catch (...) { return def; }
}
bool XmlElement::attrB(const std::string& name, bool def) const {
    auto it = attrs.find(name);
    return it == attrs.end() ? def : (it->second == "true" || it->second == "1");
}
void XmlElement::setAttr(const std::string& name, const std::string& value) {
    if (attrs.find(name) == attrs.end()) attrOrder.push_back(name);
    attrs[name] = value;
}
void XmlElement::setAttrD(const std::string& name, double value, int precision) {
    std::ostringstream ss;
    ss.precision(precision);
    ss << value;
    setAttr(name, ss.str());
}
void XmlElement::setAttrB(const std::string& name, bool value) {
    setAttr(name, value ? "true" : "false");
}
std::vector<std::shared_ptr<XmlElement>> XmlElement::childrenNamed(const std::string& name) const {
    std::vector<std::shared_ptr<XmlElement>> out;
    for (auto& c : children) if (c->tag == name) out.push_back(c);
    return out;
}
std::shared_ptr<XmlElement> XmlElement::addChild(const std::string& tag) {
    auto el = std::make_shared<XmlElement>();
    el->tag = tag;
    children.push_back(el);
    return el;
}

namespace {

class XmlParser {
public:
    explicit XmlParser(const std::string& text) : s(text), pos(0), n(text.size()) {}

    std::shared_ptr<XmlElement> parseDocument() {
        skipProlog();
        skipWhitespaceAndComments();
        return parseElement();
    }

private:
    const std::string& s;
    size_t pos, n;

    void skipProlog() {
        skipWhitespaceAndComments();
        if (match("<?")) {
            size_t end = s.find("?>", pos);
            pos = (end == std::string::npos) ? n : end + 2;
        }
    }

    void skipWhitespaceAndComments() {
        for (;;) {
            while (pos < n && std::isspace((unsigned char)s[pos])) pos++;
            if (match("<!--")) {
                size_t end = s.find("-->", pos);
                pos = (end == std::string::npos) ? n : end + 3;
                continue;
            }
            break;
        }
    }

    bool match(const char* lit) const {
        size_t len = std::strlen(lit);
        if (pos + len > n) return false;
        return s.compare(pos, len, lit) == 0;
    }
    bool consume(const char* lit) {
        if (!match(lit)) return false;
        pos += std::strlen(lit);
        return true;
    }

    std::string parseName() {
        size_t start = pos;
        while (pos < n && (std::isalnum((unsigned char)s[pos]) || s[pos] == '_' || s[pos] == '-' || s[pos] == ':' || s[pos] == '.'))
            pos++;
        return s.substr(start, pos - start);
    }

    std::shared_ptr<XmlElement> parseElement() {
        skipWhitespaceAndComments();
        if (pos >= n || s[pos] != '<') return nullptr;
        pos++; // consume '<'
        auto el = std::make_shared<XmlElement>();
        el->tag = parseName();

        for (;;) {
            while (pos < n && std::isspace((unsigned char)s[pos])) pos++;
            if (match("/>") || (pos < n && s[pos] == '>')) break;
            std::string attrName = parseName();
            if (attrName.empty()) { pos++; continue; } // defensive skip on malformed input
            while (pos < n && std::isspace((unsigned char)s[pos])) pos++;
            if (pos < n && s[pos] == '=') {
                pos++;
                while (pos < n && std::isspace((unsigned char)s[pos])) pos++;
                if (pos < n && (s[pos] == '"' || s[pos] == '\'')) {
                    char quote = s[pos];
                    pos++;
                    size_t start = pos;
                    while (pos < n && s[pos] != quote) pos++;
                    el->setAttr(attrName, s.substr(start, pos - start));
                    if (pos < n) pos++; // closing quote
                }
            }
        }

        if (consume("/>")) return el; // self-closing
        if (pos < n && s[pos] == '>') pos++;

        for (;;) {
            skipWhitespaceAndComments();
            if (pos >= n) break;
            if (match("</")) {
                pos += 2;
                parseName(); // closing tag name -- assumed to match, not re-checked
                while (pos < n && s[pos] != '>') pos++;
                if (pos < n) pos++;
                break;
            }
            if (s[pos] == '<') {
                auto child = parseElement();
                if (child) el->children.push_back(child);
                else break;
            } else {
                while (pos < n && s[pos] != '<') pos++; // skip stray text content
            }
        }
        return el;
    }
};

} // namespace

std::shared_ptr<XmlElement> parseXmlString(const std::string& text) {
    XmlParser parser(text);
    auto root = parser.parseDocument();
    if (!root) throw std::runtime_error("xml_reader: failed to parse document (empty or malformed)");
    return root;
}

std::shared_ptr<XmlElement> parseXmlFile(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("xml_reader: cannot open " + path);
    std::stringstream ss;
    ss << in.rdbuf();
    return parseXmlString(ss.str());
}
