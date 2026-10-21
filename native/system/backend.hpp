#pragma once
#include <QDBusConnection>
#include <QJsonObject>
#include <QString>
#include <QVariantMap>
#include <stdexcept>
namespace System {
inline constexpr auto Service = "org.hics.System1";
inline constexpr auto Path = "/org/hics/System1";
inline constexpr auto Interface = "org.hics.System1";
struct Failure : std::runtime_error {
  QString code;
  Failure(QString code, QString message)
      : std::runtime_error(message.toStdString()), code(std::move(code)) {}
};
QJsonObject status(const QString &domain, uint uid);
void validate(const QString &domain, const QString &operation,
              const QJsonObject &options);
void authorize(const QString &sender, const QString &action, uint uid);
void apply(const QString &domain, const QString &operation,
           const QJsonObject &options, uint uid);
QJsonObject storageStatus();
void validateStorage(const QString &operation, const QJsonObject &options);
void storageMaintenance(const QString &operation, const QJsonObject &options);
QJsonObject storageAction(const QString &operation, const QJsonObject &options);
QString encode(const QJsonObject &value);
QJsonObject failure(const std::exception &error);
} // namespace System
