#include "backend.hpp"
#include <QDBusInterface>
#include <QDBusReply>
#include <QFile>
#include <QJsonArray>
#include <QLocale>
#include <QProcess>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSet>
namespace System {
static QStringList supportedLocales() {
  QFile file("/usr/share/i18n/SUPPORTED");
  QStringList result;
  if (file.open(QIODevice::ReadOnly))
    for (const auto &line : QString::fromUtf8(file.readAll()).split('\n')) {
      auto fields = line.simplified().split(' ');
      if (fields.size() == 2 && fields[1] == "UTF-8" &&
          QRegularExpression("^[A-Za-z0-9_@.-]{2,80}$")
              .match(fields[0])
              .hasMatch())
        result << fields[0];
    }
  result.removeDuplicates();
  result.sort();
  return result;
}
static QVariantMap localedProperties() {
  QDBusInterface iface("org.freedesktop.locale1", "/org/freedesktop/locale1",
                       "org.freedesktop.DBus.Properties",
                       QDBusConnection::systemBus());
  QDBusReply<QVariantMap> reply =
      iface.call("GetAll", "org.freedesktop.locale1");
  if (!reply.isValid())
    throw Failure("unavailable", reply.error().message());
  return reply.value();
}
QJsonObject regionStatus() {
  const auto props = localedProperties();
  QJsonArray locales;
  for (const auto &id : supportedLocales()) {
    QLocale locale(id.section('.', 0, 0));
    locales.append(
        QJsonObject{{"id", id},
                    {"name", locale.nativeLanguageName() + " · " +
                                 locale.nativeTerritoryName() + " · " + id}});
  }
  return {{"available", true},
          {"locales", locales},
          {"current",
           QJsonArray::fromStringList(props.value("Locale").toStringList())},
          {"layouts", props.value("X11Layout").toString()},
          {"options", props.value("X11Options").toString()}};
}
void validateRegion(const QString &op, const QJsonObject &o) {
  if (op != "locale" || o.size() > 2 || !o.value("locale").isString() ||
      !supportedLocales().contains(o.value("locale").toString()) ||
      o.contains("allFormats") && !o.value("allFormats").isBool())
    throw Failure("invalid", "Choose a supported UTF-8 system locale");
  for (auto it = o.begin(); it != o.end(); ++it)
    if (it.key() != "locale" && it.key() != "allFormats")
      throw Failure("invalid", "Unknown locale option");
}
void applyRegion(const QString &op, const QJsonObject &o) {
  static QMutex mutation;
  QMutexLocker lock(&mutation);
  validateRegion(op, o);
  const auto selected = o["locale"].toString();
  QFile input("/etc/locale.gen");
  if (!input.open(QIODevice::ReadOnly))
    throw Failure("unavailable", "System locale generation is unavailable");
  auto lines = QString::fromUtf8(input.readAll()).split('\n');
  bool changed = false, found = false;
  const QRegularExpression entry(
      "^\\s*#?\\s*" + QRegularExpression::escape(selected) + "\\s+UTF-8\\s*$");
  for (auto &line : lines)
    if (entry.match(line).hasMatch()) {
      found = true;
      if (line.trimmed().startsWith('#')) {
        line = selected + " UTF-8";
        changed = true;
      }
    }
  if (!found) {
    lines << selected + " UTF-8";
    changed = true;
  }
  if (changed) {
    QSaveFile file("/etc/locale.gen");
    if (!file.open(QIODevice::WriteOnly))
      throw Failure("failed", "Cannot update locale generation settings");
    file.setPermissions(QFile::ReadOwner | QFile::WriteOwner |
                        QFile::ReadGroup | QFile::ReadOther);
    file.write(lines.join('\n').toUtf8());
    if (!file.commit())
      throw Failure("failed", "Cannot save locale generation settings");
  }
  QProcess generator;
  generator.start("/usr/bin/locale-gen", {});
  if (!generator.waitForStarted(5000) || !generator.waitForFinished(120000) ||
      generator.exitCode() != 0) {
    generator.kill();
    throw Failure("failed", "Could not generate the selected locale");
  }
  auto values = localedProperties().value("Locale").toStringList();
  QStringList next;
  if (!o.value("allFormats").toBool(true))
    for (const auto &value : values)
      if (!value.startsWith("LANG="))
        next << value;
  next << "LANG=" + selected;
  QDBusInterface iface("org.freedesktop.locale1", "/org/freedesktop/locale1",
                       "org.freedesktop.locale1", QDBusConnection::systemBus());
  const auto reply = iface.call("SetLocale", next, false);
  if (reply.type() == QDBusMessage::ErrorMessage)
    throw Failure("failed", reply.errorMessage());
}
} // namespace System
