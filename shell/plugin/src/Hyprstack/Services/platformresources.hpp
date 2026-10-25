#pragma once
#include <QObject>
#include <QVariantList>
#include <QVariantMap>
#include <QtQmlIntegration/qqmlintegration.h>
namespace hyprstack::services {
class PlatformResources : public QObject {
  Q_OBJECT
  QML_ELEMENT
  QML_SINGLETON
public:
  using QObject::QObject;
  Q_INVOKABLE bool hasExecutable(const QString &name) const;
  Q_INVOKABLE QVariantList displayBuses() const;
  Q_INVOKABLE QVariantMap backlight() const;
};
} // namespace hyprstack::services
