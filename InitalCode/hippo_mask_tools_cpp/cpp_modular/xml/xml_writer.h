// xml_writer.h -- serializes an XmlElement tree (see xml_reader.h) back to
// indented XML text, escaping attribute values. Pairs with xml_reader.h so
// a file can be read into the DOM, edited, and written back out.
#pragma once
#include <string>
#include "xml_reader.h"

struct XmlWriteOptions {
    bool declaration = true;   // emit <?xml version="1.0"?> up top
    std::string indent = "";   // e.g. "  " for pretty-printed output; "" (default)
                                // matches the compact, no-newline style Hippotizer
                                // itself writes (see the sample Masks.xml files)
};

std::string writeXmlString(const XmlElement& root, const XmlWriteOptions& opts = {});
void writeXmlFile(const std::string& path, const XmlElement& root, const XmlWriteOptions& opts = {});
