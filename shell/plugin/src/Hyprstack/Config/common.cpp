#include "common.hpp"

#include <qstandardpaths.h>

namespace hyprstack::config {

using Qt::StringLiterals::operator""_s;

Q_LOGGING_CATEGORY(lcConfig, "hyprstack.config", QtInfoMsg)

QString configDir() {
    return QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + u"/hyprstack"_s;
}

QString monitorConfigDir() {
    return configDir() + u"/monitors"_s;
}

} // namespace hyprstack::config
