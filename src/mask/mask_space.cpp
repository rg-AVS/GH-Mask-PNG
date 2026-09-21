#include "mask_space.h"
#include <algorithm>
#include <stdexcept>

double MaskSpace::scaleX() const {
    if (imgW <= 0 || imgH <= 0) return 1.0;
    switch (mode) {
        case Mode::Native:  return 1.0;
        case Mode::Stretch: return (double)declW / imgW;
        case Mode::Fit:     return std::min((double)declW / imgW, (double)declH / imgH);
    }
    return 1.0;
}

double MaskSpace::scaleY() const {
    if (imgW <= 0 || imgH <= 0) return 1.0;
    switch (mode) {
        case Mode::Native:  return 1.0;
        case Mode::Stretch: return (double)declH / imgH;
        case Mode::Fit:     return std::min((double)declW / imgW, (double)declH / imgH);
    }
    return 1.0;
}

Vec2 MaskSpace::toUnits(double px, double py) const {
    double u = (px - imgW / 2.0) * scaleX();
    double v = (py - imgH / 2.0) * scaleY();
    return {u, yFlip ? -v : v};
}

Vec2 MaskSpace::toPixels(double ux, double uy) const {
    if (yFlip) uy = -uy;
    return {ux / scaleX() + imgW / 2.0, uy / scaleY() + imgH / 2.0};
}

void MaskSpace::unitBounds(double& minX, double& maxX, double& minY, double& maxY) const {
    Vec2 a = toUnits(0, 0), b = toUnits(imgW, imgH);
    minX = std::min(a.x, b.x); maxX = std::max(a.x, b.x);
    minY = std::min(a.y, b.y); maxY = std::max(a.y, b.y);
}

MaskSpace::Mode parseSpaceMode(const std::string& name) {
    if (name == "native")  return MaskSpace::Mode::Native;
    if (name == "stretch") return MaskSpace::Mode::Stretch;
    if (name == "fit")     return MaskSpace::Mode::Fit;
    throw std::runtime_error("unknown mapping '" + name + "' (expected native, stretch or fit)");
}

const char* spaceModeName(MaskSpace::Mode mode) {
    switch (mode) {
        case MaskSpace::Mode::Native:  return "native";
        case MaskSpace::Mode::Stretch: return "stretch";
        case MaskSpace::Mode::Fit:     return "fit";
    }
    return "native";
}
