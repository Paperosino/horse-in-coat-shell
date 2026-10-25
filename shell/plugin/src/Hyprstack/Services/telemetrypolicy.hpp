#pragma once
#include <QCoreApplication>
#include <QObject>
#include <QPointer>
#include <QVariant>
namespace hics::performance {
inline QObject *telemetryPolicy() {
  static QPointer<QObject> policy;
  if (!policy)
    policy = new QObject(QCoreApplication::instance());
  return policy;
}
inline bool telemetryGaming() {
  return telemetryPolicy()->property("gaming").toBool();
}
inline void setTelemetryGaming(bool active) {
  telemetryPolicy()->setProperty("gaming", active);
}
} // namespace hics::performance
