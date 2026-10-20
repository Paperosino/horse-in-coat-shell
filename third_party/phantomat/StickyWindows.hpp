#pragma once
#include <algorithm>
#include <cmath>
#include <optional>
#include <vector>

namespace CanvasSticky {
struct Rect { double x, y, w, h; };
struct Axis {
    std::optional<double> held, blocked;
    double apply(double raw, const std::vector<double>& targets, double acquire, double release) {
        if (blocked && std::abs(raw - *blocked) > release + acquire) blocked.reset();
        if (held) {
            const bool exists = std::any_of(targets.begin(), targets.end(), [&](double v) { return std::abs(v - *held) < .01; });
            if (exists && std::abs(raw - *held) <= release) return *held;
            blocked = held;
            held.reset();
        }
        double best = acquire;
        for (double target : targets) {
            if (blocked && std::abs(target - *blocked) < .01) continue;
            if (const double distance = std::abs(raw - target); distance <= best) {
                best = distance;
                held = target;
            }
        }
        return held.value_or(raw);
    }
};
struct State {
    Axis x, y;
    Rect apply(Rect raw, const std::vector<Rect>& peers, double gap, double acquire, double release) {
        std::vector<double> xs, ys;
        for (const auto& peer : peers) {
            if (raw.y + raw.h >= peer.y - gap && raw.y <= peer.y + peer.h + gap)
                xs.insert(xs.end(), {peer.x - raw.w - gap, peer.x + peer.w + gap, peer.x, peer.x + peer.w - raw.w});
            if (raw.x + raw.w >= peer.x - gap && raw.x <= peer.x + peer.w + gap)
                ys.insert(ys.end(), {peer.y - raw.h - gap, peer.y + peer.h + gap, peer.y, peer.y + peer.h - raw.h});
        }
        return {x.apply(raw.x, xs, acquire, release), y.apply(raw.y, ys, acquire, release), raw.w, raw.h};
    }
};
}
