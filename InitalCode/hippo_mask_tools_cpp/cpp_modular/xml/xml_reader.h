// xml_reader.h -- minimal generic XML DOM reader. Elements + double/single
// -quoted attributes only: no namespaces, no CDATA, no entity decoding
// beyond none-needed-here, no DTD/schema validation. That's deliberate --
// it covers Masks.xml's flat, regular structure, and is meant as a
// from-scratch reference, not a replacement for a real XML library in
// production code.
#pragma once
#include <map>
#include <memory>
#include <string>
#include <vector>

struct XmlElement {
    std::string tag;
    std::map<std::string, std::string> attrs;   // insertion order NOT preserved (std::map sorts by key) --
                                                 // see xml_writer.h if attribute order must be preserved
    std::vector<std::string> attrOrder;         // attribute names in the order they appeared / were added
    std::vector<std::shared_ptr<XmlElement>> children;

    std::string attr(const std::string& name, const std::string& def = "") const;
    double attrD(const std::string& name, double def = 0.0) const;
    bool attrB(const std::string& name, bool def = false) const;

    // Sets/replaces an attribute, tracking first-seen order for the writer.
    void setAttr(const std::string& name, const std::string& value);
    void setAttrD(const std::string& name, double value, int precision = 15);
    void setAttrB(const std::string& name, bool value);

    std::vector<std::shared_ptr<XmlElement>> childrenNamed(const std::string& name) const;
    std::shared_ptr<XmlElement> addChild(const std::string& tag);
};

// Parses `text` (the full contents of an XML file) and returns the root
// element, or nullptr on a hard parse failure. Throws std::runtime_error
// only for things that make no sense to continue from (empty document).
std::shared_ptr<XmlElement> parseXmlString(const std::string& text);

// Convenience: reads the file at `path` and parses it.
std::shared_ptr<XmlElement> parseXmlFile(const std::string& path);
