#include "mask_trace.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <random>
#include <unordered_map>

namespace {

// A directed unit step along a grid line between pixels. Edges are stored
// by their start vertex so chaining is a hash lookup, not a search.
struct Edge { int x0, y0, x1, y1; bool used = false; };

inline long long vkey(int x, int y, int w) { return (long long)y * (w + 1) + x; }

double signedArea(const std::vector<Vec2>& ring) {
    double a = 0;
    size_t n = ring.size();
    for (size_t i = 0; i < n; i++) {
        const Vec2& p = ring[i];
        const Vec2& q = ring[(i + 1) % n];
        a += p.x * q.y - q.x * p.y;
    }
    return a * 0.5;
}

// Perpendicular distance from p to the infinite line ab (or to a, if a==b).
double pointLineDist(const Vec2& p, const Vec2& a, const Vec2& b) {
    double dx = b.x - a.x, dy = b.y - a.y;
    double len2 = dx * dx + dy * dy;
    if (len2 < 1e-18) return std::hypot(p.x - a.x, p.y - a.y);
    return std::fabs(dy * (p.x - a.x) - dx * (p.y - a.y)) / std::sqrt(len2);
}

// Douglas-Peucker over an OPEN polyline pts[first..last], keeping endpoints.
void dpRecurse(const std::vector<Vec2>& pts, size_t first, size_t last, double eps,
               std::vector<bool>& keep) {
    if (last <= first + 1) return;
    double worst = -1; size_t worstI = first;
    for (size_t i = first + 1; i < last; i++) {
        double d = pointLineDist(pts[i], pts[first], pts[last]);
        if (d > worst) { worst = d; worstI = i; }
    }
    if (worst <= eps) return;
    keep[worstI] = true;
    dpRecurse(pts, first, worstI, eps, keep);
    dpRecurse(pts, worstI, last, eps, keep);
}

// Drops points that sit exactly on the segment between their neighbours.
// Runs before Douglas-Peucker and is lossless, which is what turns a
// crack-traced rectangle from 4*perimeter points back into 4 corners.
std::vector<Vec2> dropCollinear(const std::vector<Vec2>& ring) {
    size_t n = ring.size();
    if (n < 3) return ring;
    std::vector<Vec2> out;
    out.reserve(n);
    for (size_t i = 0; i < n; i++) {
        const Vec2& prev = ring[(i + n - 1) % n];
        const Vec2& cur = ring[i];
        const Vec2& next = ring[(i + 1) % n];
        double cross = (cur.x - prev.x) * (next.y - prev.y) - (cur.y - prev.y) * (next.x - prev.x);
        if (std::fabs(cross) > 1e-9) out.push_back(cur);
    }
    return out.size() >= 3 ? out : ring;
}

} // namespace

std::vector<Vec2> simplifyRing(const std::vector<Vec2>& ring, double eps) {
    std::vector<Vec2> base = dropCollinear(ring);
    if (eps <= 0.0 || base.size() < 4) return base;

    // Split the closed ring at its two most distant-ish points so both
    // halves are open polylines Douglas-Peucker can handle normally.
    size_t anchor = 0, far = 0;
    double best = -1;
    for (size_t i = 1; i < base.size(); i++) {
        double d = std::hypot(base[i].x - base[anchor].x, base[i].y - base[anchor].y);
        if (d > best) { best = d; far = i; }
    }

    std::vector<bool> keep(base.size(), false);
    keep[anchor] = true;
    keep[far] = true;
    dpRecurse(base, anchor, far, eps, keep);

    // Second half wraps past the end, so walk it in a rotated copy.
    std::vector<Vec2> tail;
    std::vector<size_t> tailIdx;
    for (size_t i = far; i <= base.size(); i++) {
        size_t j = i % base.size();
        tail.push_back(base[j]);
        tailIdx.push_back(j);
    }
    std::vector<bool> tailKeep(tail.size(), false);
    tailKeep.front() = tailKeep.back() = true;
    dpRecurse(tail, 0, tail.size() - 1, eps, tailKeep);
    for (size_t i = 0; i < tail.size(); i++) if (tailKeep[i]) keep[tailIdx[i]] = true;

    std::vector<Vec2> out;
    for (size_t i = 0; i < base.size(); i++) if (keep[i]) out.push_back(base[i]);
    return out.size() >= 3 ? out : base;
}

std::vector<std::vector<Vec2>> traceContours(const std::vector<uint8_t>& gray, int w, int h,
                                              const TraceOptions& opts) {
    std::vector<std::vector<Vec2>> rings;
    if (w <= 0 || h <= 0 || gray.size() < (size_t)w * h) return rings;

    auto inside = [&](int x, int y) -> bool {
        if (x < 0 || y < 0 || x >= w || y >= h) return false;   // outside the image is never mask
        bool v = gray[(size_t)y * w + x] >= opts.threshold;
        return opts.invertInput ? !v : v;
    };

    // Every boundary between an inside pixel and an outside one becomes one
    // directed edge, wound so the inside stays on the right of travel.
    // Outer rings then come out positive-area and holes negative, which is
    // exactly what the nonzero fill rule needs.
    std::vector<Edge> edges;
    std::unordered_map<long long, std::vector<int>> outgoing;
    auto addEdge = [&](int x0, int y0, int x1, int y1) {
        outgoing[vkey(x0, y0, w)].push_back((int)edges.size());
        edges.push_back({x0, y0, x1, y1, false});
    };
    for (int y = 0; y < h; y++) {
        for (int x = 0; x < w; x++) {
            if (!inside(x, y)) continue;
            if (!inside(x, y - 1)) addEdge(x,     y,     x + 1, y);
            if (!inside(x + 1, y)) addEdge(x + 1, y,     x + 1, y + 1);
            if (!inside(x, y + 1)) addEdge(x + 1, y + 1, x,     y + 1);
            if (!inside(x - 1, y)) addEdge(x,     y + 1, x,     y);
        }
    }

    for (size_t start = 0; start < edges.size(); start++) {
        if (edges[start].used) continue;
        std::vector<Vec2> ring;
        int cur = (int)start;
        while (cur >= 0 && !edges[cur].used) {
            Edge& e = edges[cur];
            e.used = true;
            ring.push_back({(double)e.x0, (double)e.y0});
            int dx = e.x1 - e.x0, dy = e.y1 - e.y0;

            // At a diagonal pinch two edges leave the same vertex. Taking
            // the sharpest right turn keeps the two pixels as separate
            // 4-connected regions; either choice covers the same pixels.
            int prefDx[4] = {-dy,  dx,  dy, -dx};   // right, straight, left, back
            int prefDy[4] = { dx,  dy, -dx, -dy};
            int next = -1;
            auto it = outgoing.find(vkey(e.x1, e.y1, w));
            if (it != outgoing.end()) {
                for (int p = 0; p < 4 && next < 0; p++) {
                    for (int cand : it->second) {
                        if (edges[cand].used) continue;
                        if (edges[cand].x1 - edges[cand].x0 == prefDx[p] &&
                            edges[cand].y1 - edges[cand].y0 == prefDy[p]) { next = cand; break; }
                    }
                }
            }
            cur = next;
        }
        if (ring.size() < 4) continue;
        if (std::fabs(signedArea(ring)) < (double)opts.minArea) continue;
        rings.push_back(simplifyRing(ring, opts.simplifyEps));
    }
    return rings;
}

std::string makeGuid(unsigned seed) {
    if (seed == 0) seed = (unsigned)std::chrono::steady_clock::now().time_since_epoch().count();
    std::mt19937 rng(seed);
    std::uniform_int_distribution<int> hex(0, 15);
    const char* digits = "0123456789ABCDEF";
    std::string s = "{";
    const int groups[5] = {8, 4, 4, 4, 12};
    for (int g = 0; g < 5; g++) {
        if (g) s += '-';
        for (int i = 0; i < groups[g]; i++) s += digits[hex(rng)];
    }
    return s + "}";
}

MaskShape ringToShape(const std::vector<Vec2>& pixelRing, const MaskSpace& space,
                      double level, double gamma, unsigned guidSeed) {
    MaskShape shape;
    shape.level = level;
    shape.gamma = gamma;
    shape.guid = makeGuid(guidSeed);
    shape.nodes.reserve(pixelRing.size());
    for (const auto& p : pixelRing) {
        Vec2 u = space.toUnits(p.x, p.y);
        MaskNode nd;
        // Straight segments: both handles sit on the point itself, which is
        // exactly how Hippotizer writes a corner node (Type="1").
        nd.pos = nd.inH = nd.outH = u;
        nd.featherPos = nd.featherIn = nd.featherOut = u;
        nd.type = "1";
        nd.featherType = "1";
        shape.nodes.push_back(nd);
    }
    return shape;
}

HippoMask traceMask(const std::vector<uint8_t>& gray, int w, int h,
                    const MaskSpace& space, const std::string& name,
                    const std::string& index, const TraceOptions& opts) {
    HippoMask mask;
    mask.index = index;
    mask.name = name;
    mask.xres = space.declW;   // Hippotizer always writes the editor canvas here,
    mask.yres = space.declH;   // never the resolution the mask was drawn against
    mask.blur = 0.0;

    unsigned seed = opts.guidSeed;
    for (const auto& ring : traceContours(gray, w, h, opts))
        mask.shapes.push_back(ringToShape(ring, space, opts.level, opts.gamma, seed ? seed++ : 0));
    return mask;
}
