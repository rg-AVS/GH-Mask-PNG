#include "mask_render.h"
#include <algorithm>
#include <cmath>
#include <map>

namespace {

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

void rasterizeRings(const std::vector<std::vector<Vec2>>& rings, int w, int h,
                    std::vector<float>& coverage, int ySubsamples) {
    double minY = 1e18, maxY = -1e18;
    size_t total = 0;
    for (const auto& ring : rings) {
        total += ring.size();
        for (const auto& p : ring) { minY = std::min(minY, p.y); maxY = std::max(maxY, p.y); }
    }
    if (total < 3) return;

    int y0 = std::max(0, (int)std::floor(minY));
    int y1 = std::min(h - 1, (int)std::ceil(maxY));
    std::vector<float> rowAccum(w);
    std::vector<std::pair<double, int>> xs;
    const float inv = 1.0f / ySubsamples;

    for (int y = y0; y <= y1; y++) {
        std::fill(rowAccum.begin(), rowAccum.end(), 0.0f);
        for (int s = 0; s < ySubsamples; s++) {
            double sy = y + (s + 0.5) / ySubsamples;
            xs.clear();
            // Every ring contributes crossings to the same list, so winding
            // accumulates across rings and a reversed hole ring subtracts.
            for (const auto& ring : rings) {
                size_t n = ring.size();
                for (size_t i = 0; i < n; i++) {
                    const Vec2& a = ring[i];
                    const Vec2& b = ring[(i + 1) % n];
                    if (a.y == b.y) continue;
                    if (sy < std::min(a.y, b.y) || sy >= std::max(a.y, b.y)) continue;
                    double t = (sy - a.y) / (b.y - a.y);
                    xs.push_back({a.x + t * (b.x - a.x), (b.y > a.y) ? 1 : -1});
                }
            }
            std::sort(xs.begin(), xs.end());

            int winding = 0;
            double spanStart = 0;
            for (size_t i = 0; i < xs.size(); i++) {
                bool wasIn = winding != 0;
                winding += xs[i].second;
                bool isIn = winding != 0;
                if (!wasIn && isIn) {
                    spanStart = xs[i].first;
                } else if (wasIn && !isIn) {
                    // Exact horizontal overlap per column, so an integer-edged
                    // span fills whole pixels and nothing else, and a fractional
                    // one antialiases instead of snapping.
                    double spanEnd = xs[i].first;
                    if (spanEnd <= spanStart) continue;
                    int xa = std::max(0, (int)std::floor(spanStart));
                    int xb = std::min(w - 1, (int)std::ceil(spanEnd) - 1);
                    for (int x = xa; x <= xb; x++) {
                        double lo = std::max(spanStart, (double)x);
                        double hi = std::min(spanEnd, (double)x + 1.0);
                        if (hi > lo) rowAccum[x] += (float)(hi - lo) * inv;
                    }
                }
            }
        }
        for (int x = 0; x < w; x++) {
            size_t i = (size_t)y * w + x;
            coverage[i] = std::min(1.0f, coverage[i] + rowAccum[x]);
        }
    }
}

std::vector<Vec2> shapeToPixelPolygon(const MaskShape& shape, const MaskSpace& space,
                                       int segmentsPerCurve) {
    std::vector<Vec2> poly;
    size_t n = shape.nodes.size();
    if (n == 0) return poly;

    auto px = [&](const Vec2& u) { return space.toPixels(u.x, u.y); };
    poly.push_back(px(shape.nodes[0].pos));
    for (size_t i = 0; i < n; i++) {
        const MaskNode& cur = shape.nodes[i];
        const MaskNode& nxt = shape.nodes[(i + 1) % n];
        Vec2 p0 = px(cur.pos), c1 = px(cur.outH), c2 = px(nxt.inH), p1 = px(nxt.pos);
        // A corner node stores its handles on the point itself. Flattening
        // that cubic would waste 24 collinear vertices per edge, so emit the
        // straight segment instead -- which also keeps a traced crack polygon
        // bit-exact on the way back.
        bool straight = c1.x == p0.x && c1.y == p0.y && c2.x == p1.x && c2.y == p1.y;
        if (straight) poly.push_back(p1);
        else flattenCubic(p0, c1, c2, p1, segmentsPerCurve, poly);
    }
    if (poly.size() > 1) poly.pop_back();  // the flatten/append closes the ring already
    return poly;
}

std::vector<uint8_t> renderMask(const HippoMask& mask, const MaskSpace& space, double blurScale) {
    const int w = space.imgW, h = space.imgH;
    std::vector<float> coverage((size_t)w * h, 0.0f);
    if (w <= 0 || h <= 0) return {};

    // Shapes sharing a Level are one figure: filled in a single nonzero pass
    // so reversed rings cut holes. Separate Levels are separate figures,
    // combined with max ("lighten").
    std::map<long long, std::vector<const MaskShape*>> byLevel;
    for (const auto& shape : mask.shapes) {
        long long key = (long long)std::llround(shape.level * 1000.0);
        byLevel[key].push_back(&shape);
    }

    for (const auto& entry : byLevel) {
        std::vector<std::vector<Vec2>> rings;
        double level = 255.0, gamma = 1.0;
        for (const MaskShape* shape : entry.second) {
            auto poly = shapeToPixelPolygon(*shape, space);
            if (poly.size() >= 3) rings.push_back(std::move(poly));
            level = shape->level;
            gamma = shape->gamma > 0 ? shape->gamma : 1.0;
        }
        if (rings.empty()) continue;

        std::vector<float> figure((size_t)w * h, 0.0f);
        rasterizeRings(rings, w, h, figure);

        double a01 = std::max(0.0, std::min(1.0, level / 255.0));
        a01 = std::pow(a01, 1.0 / gamma);
        for (size_t i = 0; i < figure.size(); i++)
            coverage[i] = std::max(coverage[i], (float)(figure[i] * a01));
    }

    gaussianBlur(coverage, w, h, mask.blur * blurScale);

    std::vector<uint8_t> gray(coverage.size());
    for (size_t i = 0; i < coverage.size(); i++) {
        float v = coverage[i];
        if (mask.invert) v = 1.0f - v;
        v = std::max(0.0f, std::min(1.0f, v));
        gray[i] = (uint8_t)std::lround(v * 255.0f);
    }
    return gray;
}
