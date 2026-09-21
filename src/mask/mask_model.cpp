#include "mask_model.h"
#include "../xml/xml_reader.h"
#include "../xml/xml_writer.h"

std::vector<HippoMask> parseMasksXml(const std::string& path) {
    auto root = parseXmlFile(path); // <Masks>

    std::vector<HippoMask> masks;
    for (auto& maskEl : root->childrenNamed("Mask")) {
        HippoMask m;
        m.index = maskEl->attr("index");
        m.name = maskEl->attr("name");
        m.invert = maskEl->attrB("invert");
        m.alpha = maskEl->attrB("alpha");
        m.blur = maskEl->attrD("Blur", 0.0);
        m.showpoints = maskEl->attrB("showpoints");
        m.xres = (int)maskEl->attrD("xres", 0);
        m.yres = (int)maskEl->attrD("yres", 0);

        for (auto& shapeEl : maskEl->childrenNamed("Shape")) {
            MaskShape sh;
            sh.level = shapeEl->attrD("Level", 255.0);
            sh.guid = shapeEl->attr("guid");
            sh.angle = shapeEl->attrD("angle", 0.0);
            sh.locked = shapeEl->attrB("locked");
            sh.outline = shapeEl->attrB("Outline");
            sh.linewidth = shapeEl->attrD("linewidth", 1.0);
            sh.gamma = shapeEl->attrD("gamma", 1.0);
            if (sh.gamma <= 0) sh.gamma = 1.0;
            sh.infill = shapeEl->attrB("infill");
            sh.hvmix = (int)shapeEl->attrD("hvmix", 127);
            sh.hblend = (int)shapeEl->attrD("hblend", 127);
            sh.vblend = (int)shapeEl->attrD("vblend", 127);

            for (auto& nodeEl : shapeEl->childrenNamed("Node")) {
                MaskNode nd;
                nd.pos = {nodeEl->attrD("PosX"), nodeEl->attrD("PosY")};
                nd.inH = {nodeEl->attrD("InHandleX"), nodeEl->attrD("InHandleY")};
                nd.outH = {nodeEl->attrD("OutHandleX"), nodeEl->attrD("OutHandleY")};
                nd.type = nodeEl->attr("Type");
                nd.featherPos = {nodeEl->attrD("FeatherPosX"), nodeEl->attrD("FeatherPosY")};
                nd.featherIn = {nodeEl->attrD("FeatherInHandleX"), nodeEl->attrD("FeatherInHandleY")};
                nd.featherOut = {nodeEl->attrD("FeatherOutHandleX"), nodeEl->attrD("FeatherOutHandleY")};
                nd.featherType = nodeEl->attr("FeatherType");
                sh.nodes.push_back(nd);
            }
            m.shapes.push_back(sh);
        }
        masks.push_back(m);
    }
    return masks;
}

void writeMasksXml(const std::string& path, const std::vector<HippoMask>& masks) {
    XmlElement root;
    root.tag = "Masks";

    for (const auto& m : masks) {
        auto maskEl = root.addChild("Mask");
        maskEl->setAttr("index", m.index);
        maskEl->setAttr("name", m.name);
        maskEl->setAttrB("invert", m.invert);
        maskEl->setAttrB("alpha", m.alpha);
        maskEl->setAttrD("Blur", m.blur);
        maskEl->setAttrB("showpoints", m.showpoints);
        maskEl->setAttrD("xres", m.xres, 0);
        maskEl->setAttrD("yres", m.yres, 0);

        for (const auto& sh : m.shapes) {
            auto shapeEl = maskEl->addChild("Shape");
            shapeEl->setAttrD("Level", sh.level);
            shapeEl->setAttr("guid", sh.guid);
            shapeEl->setAttrD("angle", sh.angle);
            shapeEl->setAttrB("locked", sh.locked);
            shapeEl->setAttrB("Outline", sh.outline);
            shapeEl->setAttrD("linewidth", sh.linewidth);
            shapeEl->setAttrD("gamma", sh.gamma);
            shapeEl->setAttrB("infill", sh.infill);
            shapeEl->setAttrD("hvmix", sh.hvmix, 0);
            shapeEl->setAttrD("hblend", sh.hblend, 0);
            shapeEl->setAttrD("vblend", sh.vblend, 0);

            for (const auto& nd : sh.nodes) {
                auto nodeEl = shapeEl->addChild("Node");
                nodeEl->setAttrD("PosX", nd.pos.x);
                nodeEl->setAttrD("PosY", nd.pos.y);
                nodeEl->setAttrD("InHandleX", nd.inH.x);
                nodeEl->setAttrD("InHandleY", nd.inH.y);
                nodeEl->setAttrD("OutHandleX", nd.outH.x);
                nodeEl->setAttrD("OutHandleY", nd.outH.y);
                nodeEl->setAttr("Type", nd.type);
                nodeEl->setAttrD("FeatherPosX", nd.featherPos.x);
                nodeEl->setAttrD("FeatherPosY", nd.featherPos.y);
                nodeEl->setAttrD("FeatherInHandleX", nd.featherIn.x);
                nodeEl->setAttrD("FeatherInHandleY", nd.featherIn.y);
                nodeEl->setAttrD("FeatherOutHandleX", nd.featherOut.x);
                nodeEl->setAttrD("FeatherOutHandleY", nd.featherOut.y);
                nodeEl->setAttr("FeatherType", nd.featherType);
            }
        }
    }

    XmlWriteOptions opts;
    opts.declaration = false; // the sample files have no <?xml ?> prologue
    writeXmlFile(path, root, opts);
}
