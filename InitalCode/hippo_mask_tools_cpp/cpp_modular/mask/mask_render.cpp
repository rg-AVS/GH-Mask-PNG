#include "mask_render.h"
#include <algorithm>
#include <cmath>

namespace {

Vec2 toPixel(const Vec2& p, double cx, double cy) {
    return {cx + p.x, cy + p.y};
}

void flattenCubic(const Vec2& p0, const Vec2& c1, const Vec2& c2, const Vec2& p1,
                   int segments, std::vector<Vec2>& out) {
    for (int i = 1; i <= segments; i++) {
        double t = (double)i / segments;
        double u = 1.0 - t;
        double bx = u*u*u*p0.x + 3*u*u*t*c1.x + 3*u*t*t*c2.x + t*t*t*p1.x;
        double by = u*u*u*p0.y + 3*u*u*t*c1.y + 3*u*t*t*c2.y + t*t*t*p1.y;
        out.push_back({bx, by});
    }
}

void rasterizePolygon(const std::vector<Vec2>& poly, int xres, int yres,
                       std::vector<float>& coverage, int ySubsamples = 4) {
    if (poly.size() < 2) return;
    double minY = 1e18, maxY = -1e18;
    for (auto& p : poly) { minY = std::min(minY, p.y); maxY = std::max(maxY, p.y); }
    int y0 = std::max(0, (int)std::floor(minY));
    int y1 = std::min(yres - 1, (int)std::ceil(maxY));

    std::vector<float> rowAccum(xres);
    for (int y = y0; y <= y1; y++) {
        std::fill(rowAccum.begin(), rowAccum.end(), 0.0f);
        for (int s = 0; s < ySubsamples; s++) {
            double sy = y + (s + 0.5) / ySubsamples;
            std::vector<std::pair<double, int>> xs;
            size_t n = poly.size();
            for (size_t i = 0; i < n; i++) {
                Vec2 a = poly[i], b = poly[(i + 1) % n];
                if (a.y == b.y) continue;
                double ymin = std::min(a.y, b.y), ymax = std::max(a.y, b.y);
                if (sy < ymin || sy >= ymax) continue;
                double t = (sy - a.y) / (b.y - a.y);
                double x = a.x + t * (b.x - a.x);
                int dir = (b.y > a.y) ? 1 : -1;
                xs.push_back({x, dir});
            }
            std::sort(xs.begin(), xs.end());
            // Walk crossings left to right, track nonzero-rule winding, and
            // fill each contiguous span where winding != 0.
            int winding = 0;
            for (size_t i = 0; i < xs.size(); i++) {
                bool wasIn = winding != 0;
                winding += xs[i].second;
                bool isIn = winding != 0;
                if (!wasIn && isIn) {
                    double spanStart = xs[i].first;
                    int w2 = winding;
                    size_t j = i + 1;
                    for (; j < xs.size(); j++) {
                        w2 += xs[j].second;
                        if (w2 == 0) break;
                    }
                    double spanEnd = (j < xs.size()) ? xs[j].first : spanStart;
                    int xa = std::max(0, (int)std::floor(spanStart + 0.5));
                    int xb = std::min(xres - 1, (int)std::floor(spanEnd - 0.5));
                    for (int x = xa; x <= xb; x++) rowAccum[x] += 1.0f / ySubsamples;
                }
            }
        }
        for (int x = 0; x < xres; x++) {
            float v = coverage[(size_t)y * xres + x] + rowAccum[x];
            coverage[(size_t)y * xres + x] = std::min(1.0f, v);
        }
    }
}

void gaussianBlur(std::vector<float>& buf, int w, int h, double sigma) {
    if (sigma <= 0.01) return;
    int radius = std::max(1, (int)std::ceil(sigma * 3.0));
    std::vector<double> kernel(2 * radius + 1);
    double sum = 0;
    for (int i = -radius; i <= radius; i++) {
        double v = std::exp(-(i * i) / (2.0 * sigma * sigma));
        kernel[i + radius] = v;
        sum += v;
    }
    for (auto& v : kernel) v /= sum;

    std::vector<float> tmp(buf.size());
    for (int y = 0; y < h; y++) {
        for (int x = 0; x < w; x++) {
            double acc = 0;
            for (int k = -radius; k <= radius; k++) {
                int xx = std::min(w - 1, std::max(0, x + k));
                acc += buf[(size_t)y * w + xx] * kernel[k + radius];
            }
            tmp[(size_t)y * w + x] = (float)acc;
        }
    }
    for (int y = 0; y < h; y++) {
        for (int x = 0; x < w; x++) {
            double acc = 0;
            for (int k = -radius; k <= radius; k++) {
                int yy = std::min(h - 1, std::max(0, y + k));
                acc += tmp[(size_t)yy * w + x] * kernel[k + radius];
            }
            buf[(size_t)y * w + x] = (float)acc;
        }
    }
}

} // namespace

std::vector<Vec2> shapeToPixelPolygon(const MaskShape& shape, int xres, int yres, int segmentsPerCurve) {
    std::vector<Vec2> poly;
    double cx = xres / 2.0, cy = yres / 2.0;
    size_t n = shape.nodes.size();
    if (n == 0) return poly;
    poly.push_back(toPixel(shape.nodes[0].pos, cx, cy));
    for (size_t i = 0; i < n; i++) {
        const MaskNode& cur = shape.nodes[i];
        const MaskNode& nxt = shape.nodes[(i + 1) % n];
        Vec2 p0 = toPixel(cur.pos, cx, cy);
        Vec2 c1 = toPixel(cur.outH, cx, cy);
        Vec2 c2 = toPixel(nxt.inH, cx, cy);
        Vec2 p1 = toPixel(nxt.pos, cx, cy);
        flattenCubic(p0, c1, c2, p1, segmentsPerCurve, poly);
    }
    return poly;
}

std::vector<uint8_t> renderMask(const HippoMask& mask, double blurScale) {
    std::vector<float> coverage((size_t)mask.xres * mask.yres, 0.0f);

    for (const auto& shape : mask.shapes) {
        auto poly = shapeToPixelPolygon(shape, mask.xres, mask.yres);
        if (poly.size() < 3) continue;

        std::vector<float> shapeCoverage((size_t)mask.xres * mask.yres, 0.0f);
        rasterizePolygon(poly, mask.xres, mask.yres, shapeCoverage);

        double a01 = std::max(0.0, std::min(1.0, shape.level / 255.0));
        a01 = std::pow(a01, 1.0 / shape.gamma);
        for (size_t i = 0; i < shapeCoverage.size(); i++) {
            float v = (float)(shapeCoverage[i] * a01);
            coverage[i] = std::max(coverage[i], v); // "lighten" combine across shapes
        }
    }

    gaussianBlur(coverage, mask.xres, mask.yres, mask.blur * blurScale);

    std::vector<uint8_t> gray(coverage.size());
    for (size_t i = 0; i < coverage.size(); i++) {
        float v = coverage[i];
        if (mask.invert) v = 1.0f - v;
        v = std::max(0.0f, std::min(1.0f, v));
        gray[i] = (uint8_t)std::round(v * 255.0f);
    }
    return gray;
}
