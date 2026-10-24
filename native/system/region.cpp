#include "backend.hpp"
#include <QDBusInterface>
#include <QDBusReply>
#include <QFile>
#include <QJsonArray>
#include <QLocale>
#include <QMap>
#include <QMutex>
#include <QMutexLocker>
#include <QProcess>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSet>
namespace System {
static QStringList supportedLocales() {
  QFile file("/usr/share/i18n/SUPPORTED");
  QStringList result{"C.UTF-8"};
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
    if (id == "C.UTF-8") {
      locales.append(QJsonObject{{"id", id},
                                 {"name", id},
                                 {"language", "System default"},
                                 {"territory", ""}});
      continue;
    }
    QLocale locale(id.section('.', 0, 0));
    locales.append(QJsonObject{
        {"id", id},
        {"language", QLocale::languageToString(locale.language())},
        {"territory", QLocale::territoryToString(locale.territory())},
        {"name", locale.nativeLanguageName() + " · " +
                     locale.nativeTerritoryName() + " · " + id}});
  }
  const auto assignments = props.value("Locale").toStringList();
  QString currentLocale = "C.UTF-8";
  for (const auto &entry : assignments)
    if (entry.startsWith("LANG="))
      currentLocale = entry.mid(5);
  return {{"available", true},
          {"currentLocale", currentLocale},
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
QStringList regionAssignments(const QStringList &current,
                              const QString &selected, bool allFormats) {
  QMap<QString, QString> previous;
  for (const auto &entry : current) {
    const auto separator = entry.indexOf('=');
    if (separator > 0)
      previous.insert(entry.left(separator), entry.mid(separator + 1));
  }
  QStringList result{"LANG=" + selected};
  if (!allFormats) {
    // Explicitly preserve inherited formats too. Merely copying LC_* loses
    // the old formats when they previously inherited LANG.
    for (const auto &key :
         {"LC_NUMERIC", "LC_TIME", "LC_COLLATE", "LC_MONETARY", "LC_PAPER",
          "LC_NAME", "LC_ADDRESS", "LC_TELEPHONE", "LC_MEASUREMENT",
          "LC_IDENTIFICATION"})
      result << QString(key) + "=" +
                    previous.value(key, previous.value("LANG", "C.UTF-8"));
  }
  return result;
}
void generateRegion(const QString &op, const QJsonObject &o) {
  static QMutex mutation;
  QMutexLocker lock(&mutation);
  validateRegion(op, o);
  const auto selected = o["locale"].toString();
  if (selected != "C.UTF-8") {
    QFile input("/etc/locale.gen");
    if (!input.open(QIODevice::ReadOnly))
      throw Failure("unavailable", "System locale generation is unavailable");
    auto lines = QString::fromUtf8(input.readAll()).split('\n');
    bool changed = false, found = false;
    const QRegularExpression entry("^\\s*#?\\s*" +
                                   QRegularExpression::escape(selected) +
                                   "\\s+UTF-8\\s*$");
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
  }
  const auto next =
      regionAssignments(localedProperties().value("Locale").toStringList(),
                        selected, o.value("allFormats").toBool(true));
  QDBusInterface iface("org.freedesktop.locale1", "/org/freedesktop/locale1",
                       "org.freedesktop.locale1", QDBusConnection::systemBus());
  const auto reply = iface.call("SetLocale", next, false);
  if (reply.type() == QDBusMessage::ErrorMessage)
    throw Failure("failed", reply.errorMessage());
}
void applyRegion(const QString &op, const QJsonObject &o) {
  static QMutex requests;
  QMutexLocker lock(&requests);
  validateRegion(op, o);
  QProcess worker;
  worker.start(HYPRSTACK_SYSTEMD_RUN,
               {"--quiet", "--wait", "--pipe", "--collect",
                "--expand-environment=no", "--unit=hics-region-configure",
                "--property=Type=exec", "--property=NoNewPrivileges=yes",
                "--property=ProtectSystem=strict", "--property=ProtectHome=yes",
                "--property=PrivateTmp=yes",
                "--property=ReadWritePaths=/etc /usr/lib/locale",
                "--property=RestrictAddressFamilies=AF_UNIX",
                "--property=MemoryMax=512M", "--property=TasksMax=32",
                "--property=RuntimeMaxSec=140", HYPRSTACK_REGION_EXECUTABLE,
                o["locale"].toString(),
                o.value("allFormats").toBool(true) ? "all" : "language"});
  if (!worker.waitForStarted(5000) || !worker.waitForFinished(140000)) {
    worker.kill();
    worker.waitForFinished();
    throw Failure("busy", "Locale generation did not finish; check "
                          "hics-region-configure.service");
  }
  if (worker.exitStatus() != QProcess::NormalExit || worker.exitCode() != 0)
    throw Failure("failed",
                  QString::fromUtf8(worker.readAllStandardError()).trimmed());
}
} // namespace System
