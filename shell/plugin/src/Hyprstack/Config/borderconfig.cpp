#include "borderconfig.hpp"

#include <algorithm>

namespace hyprstack::config {

int BorderConfig::minThickness() {
    return 2;
}

int BorderConfig::clampedThickness() const {
    return std::max(minThickness(), m_thickness);
}

} // namespace hyprstack::config
