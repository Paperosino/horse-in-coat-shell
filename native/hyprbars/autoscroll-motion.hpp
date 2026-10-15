#pragma once
#include <algorithm>
#include <cmath>

namespace HyprstackAutoscroll {
inline constexpr double DEAD_ZONE = 12;

inline double velocity(double distance) {
    const double outside = std::max(0.0, std::abs(distance) - DEAD_ZONE);
    return std::copysign(std::min(3000.0, std::pow(outside, 2.2) * 0.008), distance);
}

inline double intervalFor(double refreshRate) {
    return 1.0 / std::clamp(refreshRate, 30.0, 500.0);
}

// Exact integration keeps travel and acceleration independent of the output
// refresh rate. Wayland represents an axis delta with 1/256-pixel precision.
inline double advance(double target, double elapsed, double& current, double& residual) {
    constexpr double rampSeconds = 0.09;
    if (target == 0) { current = residual = 0; return 0; }
    const double decay = std::exp(-elapsed/rampSeconds);
    const double movement = target*elapsed + (current-target)*rampSeconds*(1-decay);
    current = target + (current-target)*decay;
    residual += movement;
    const double emitted = std::trunc(residual*256.0)/256.0;
    residual -= emitted;
    return emitted;
}
}
