#include "common.hpp"

#include <qstandardpaths.h>
#include <QTimer>
#include <QVariant>

namespace hyprstack::config {

using Qt::StringLiterals::operator""_s;

Q_LOGGING_CATEGORY(lcConfig, "hyprstack.config", QtInfoMsg)

void warnMissingScreen(const QObject *attached, const char *scope, const char *property) {
    auto *owner = const_cast<QObject*>(attached);
    const auto key = QString::fromLatin1(scope) + u'.' + QString::fromLatin1(property);
    constexpr auto flag = "_hicsMissingScreenWarnings";
    auto pending = owner->property(flag).toStringList();
    if (pending.contains(key)) return;
    pending.append(key); owner->setProperty(flag, pending);
    // Window/Popup bindings can be evaluated before their screen binding.
    // The context cancels this callback if the attached object is destroyed.
    QTimer::singleShot(0, owner, [owner, key] {
        if (owner->property("screen").toString().isEmpty()) {
            if (const auto parent = owner->parent())
                qCWarning(lcConfig, "%s accessed without a screen set on %s", qUtf8Printable(key), parent->metaObject()->className());
        } else {
            auto remaining = owner->property("_hicsMissingScreenWarnings").toStringList();
            remaining.removeAll(key); owner->setProperty("_hicsMissingScreenWarnings", remaining);
        }
    });
}

QString configDir() {
    return QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + u"/hics"_s;
}

QString monitorConfigDir() {
    return configDir() + u"/monitors"_s;
}

} // namespace hyprstack::config
