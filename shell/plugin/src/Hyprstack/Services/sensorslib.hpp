#pragma once

#include <optional>

namespace hyprstack::services::sensorslib {

void ensureInit();

[[nodiscard]] std::optional<double> cpuPackageTemp();
[[nodiscard]] std::optional<double> gpuPciAverageTemp();

} // namespace hyprstack::services::sensorslib
