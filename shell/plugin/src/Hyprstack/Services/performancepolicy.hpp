#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace hics::performance {
// Missing samples never count as low load. Hysteresis and elapsed time, rather
// than a frame timer, make the policy independent of screen refresh and jitter.
struct QualityPolicy {
  int level = 2;
  bool hot = false;
  int highSamples = 0, lowSamples = 0, coolSamples = 0;
  std::int64_t changedAt = 0;
  void reset() { *this = {}; }
  void sample(double gpu, double temperature, bool adaptive, bool thermal,
              int minimum, double high, double low, double hotAt, double coolAt,
              std::int64_t now, int dwellMs) {
    if (!thermal)
      hot = false;
    else if (std::isfinite(temperature) && temperature > 0) {
      if (temperature >= hotAt) {
        hot = true;
        coolSamples = 0;
      } else if (temperature <= coolAt) {
        if (++coolSamples >= 3)
          hot = false;
      } else
        coolSamples = 0;
    }
    if (!adaptive) {
      level = 2;
      highSamples = lowSamples = 0;
      return;
    }
    if (!std::isfinite(gpu) || gpu < 0 || gpu > 100) {
      highSamples = lowSamples = 0;
      return;
    }
    highSamples = gpu >= high ? highSamples + 1 : 0;
    lowSamples = gpu <= low ? lowSamples + 1 : 0;
    if (now - changedAt < dwellMs)
      return;
    if (highSamples >= 3 && level > minimum) {
      --level;
      changedAt = now;
      highSamples = lowSamples = 0;
    } else if (lowSamples >= 5 && level < 2) {
      ++level;
      changedAt = now;
      highSamples = lowSamples = 0;
    }
  }
};
} // namespace hics::performance
