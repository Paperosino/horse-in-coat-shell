#include "desktopentry.hpp"
#include "service.hpp"
#include <QCryptographicHash>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSet>
#include <QSettings>
#include <QStandardPaths>
namespace HicsDesktop {
namespace {
QString appId(const QJsonObject &args) {
  const auto id = args["id"].toString();
  if (!QRegularExpression("^[A-Za-z0-9][A-Za-z0-9_.+-]{0,240}$")
           .match(id)
           .hasMatch())
    throw std::runtime_error("Invalid application identifier");
  return id;
}
QJsonObject failure(const CommandResult &result) {
  return {{"error", QString::fromUtf8(result.error).trimmed().isEmpty()
                        ? QString("Operation failed (%1)").arg(result.exitCode)
                        : QString::fromUtf8(result.error).trimmed()}};
}
QJsonObject ini(const QByteArray &bytes) {
  QJsonObject object;
  QString section;
  for (const auto &line : QString::fromUtf8(bytes).split('\n')) {
    const auto value = line.trimmed();
    if (value.startsWith('#') || value.isEmpty())
      continue;
    if (value.startsWith('[') && value.endsWith(']')) {
      section = value.mid(1, value.size() - 2);
      continue;
    }
    const int equals = value.indexOf('=');
    if (equals < 1 || section.isEmpty())
      continue;
    auto group = object[section].toObject();
    group[value.left(equals)] = value.mid(equals + 1);
    object[section] = group;
  }
  return object;
}
} // namespace
void Service::applications(const QSharedPointer<Job> &job) {
  const QString operation = job->operation;
  if (operation == "apps.apparmor-service") {
    root(job, "applications", "service-enable",
         {{"enabled", job->arguments["enabled"]}});
    return;
  }
  if (operation == "apps.apparmor-save") {
    root(job, "applications", "profile-save", job->arguments);
    return;
  }
  if (operation == "apps.remove") {
    const auto id = appId(job->arguments);
    root(job, "applications", "remove",
         {{"desktop", id.endsWith(".desktop") ? id : id + ".desktop"},
          {"version", job->arguments["version"]}});
    return;
  }
  if (operation == "apps.apparmor-mode") {
    const auto mode = job->arguments["mode"].toString();
    if (!QStringList{"enforce", "complain", "disable-profile"}.contains(mode)) {
      finish(job, {}, "Unknown AppArmor mode");
      return;
    }
    root(job, "applications", mode, {{"profile", job->arguments["profile"]}});
    return;
  }
  if (operation == "apps.apparmor-status") {
    auto call = QDBusMessage::createMethodCall(
        "org.hics.System1", "/org/hics/System1", "org.hics.System1", "Status");
    call.setArguments({"applications"});
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::systemBus().asyncCall(call, 15000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this, watcher, job] {
              QDBusPendingReply<QString> result = *watcher;
              watcher->deleteLater();
              if (result.isError())
                finish(job, {}, result.error().message());
              else {
                auto value =
                    QJsonDocument::fromJson(result.value().toUtf8()).object();
                const auto error = value.take("error").toString();
                finish(job, value, error);
              }
            });
    return;
  }
  if (operation == "apps.apparmor-read") {
    const auto profile = job->arguments["profile"].toString();
    worker(job, [profile] {
      if (!QRegularExpression("^[A-Za-z0-9][A-Za-z0-9_.+-]{0,199}$")
               .match(profile)
               .hasMatch())
        return QJsonObject{{"error", "Choose an AppArmor profile file"}};
      const auto path = "/etc/apparmor.d/" + profile;
      QFileInfo info(path);
      if (info.isSymLink() || info.ownerId() != 0 ||
          !info.canonicalFilePath().startsWith("/etc/apparmor.d/"))
        return QJsonObject{{"error", "Select an existing system profile"}};
      QFile file(path);
      if (!file.open(QIODevice::ReadOnly) || file.size() > 65536)
        return QJsonObject{
            {"error", "Cannot read this profile or it exceeds 64 KiB"}};
      const auto bytes = file.readAll();
      return QJsonObject{
          {"profile", profile},
          {"content", QString::fromUtf8(bytes)},
          {"sha256", QString::fromLatin1(QCryptographicHash::hash(
                                             bytes, QCryptographicHash::Sha256)
                                             .toHex())}};
    });
    return;
  }
  if (operation == "apps.portal-camera") {
    const auto id = appId(job->arguments);
    const auto policy = job->arguments["policy"].toString();
    if (!QStringList{"yes", "no", "ask"}.contains(policy)) {
      finish(job, {}, "Choose a valid camera policy");
      return;
    }
    auto call = QDBusMessage::createMethodCall(
        "org.freedesktop.impl.portal.PermissionStore",
        "/org/freedesktop/impl/portal/PermissionStore",
        "org.freedesktop.impl.portal.PermissionStore",
        policy == "ask" ? "DeletePermission" : "SetPermission");
    call.setArguments(
        policy == "ask"
            ? QVariantList{QString("devices"), QString("camera"), id}
            : QVariantList{QString("devices"), true, QString("camera"), id,
                           QStringList{policy}});
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(call, 5000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this, watcher, job] {
              QDBusPendingReply<> reply = *watcher;
              watcher->deleteLater();
              finish(job, {},
                     reply.isError() ? reply.error().message() : QString());
            });
    return;
  }
  const auto args = job->arguments;
  worker(job, [operation, args] {
    const auto id = appId(args);
    QString desktop = id.endsWith(".desktop") ? id : id + ".desktop";
    if (operation == "apps.info") {
      const QString requested = args["path"].toString();
      QString path = QFileInfo(requested).isAbsolute()
                         ? requested
                         : QString("/usr/share/applications/") + desktop;
      if (QFileInfo(path).suffix() != "desktop" || !QFileInfo(path).isFile() ||
          QFileInfo(path).size() > 1024 * 1024)
        return QJsonObject{
            {"error", "Application desktop file is unavailable"}};
      QSettings file(path, QSettings::IniFormat);
      file.beginGroup("Desktop Entry");
      const auto flatpak = file.value("X-Flatpak").toString();
      QJsonObject result{{"id", id},
                         {"flatpak", flatpak},
                         {"path", path},
                         {"native", flatpak.isEmpty()}};
      const auto userStart =
          QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) +
          "/autostart/" + desktop;
      const auto autoPath = QFileInfo::exists(userStart)
                                ? userStart
                                : QString("/etc/xdg/autostart/") + desktop;
      QSettings start(autoPath, QSettings::IniFormat);
      result["autostart"] =
          QFileInfo::exists(autoPath) &&
          !start.value("Desktop Entry/Hidden", false).toBool();
      if (!flatpak.isEmpty()) {
        if (!QRegularExpression("^[A-Za-z0-9_-]+(?:\\.[A-Za-z0-9_-]+){2,}$")
                 .match(flatpak)
                 .hasMatch())
          return QJsonObject{{"error", "Invalid Flatpak application ID"}};
        const auto info =
            command("flatpak", {"info", "--show-permissions", flatpak});
        if (info.exitCode != 0)
          return failure(info);
        const auto overrides =
            command("flatpak", {"override", "--user", "--show", flatpak});
        auto permissions = ini(info.output);
        const auto overridesObject = ini(overrides.output);
        auto context = permissions["Context"].toObject();
        const auto changed = overridesObject["Context"].toObject();
        for (auto it = changed.begin(); it != changed.end(); ++it) {
          QSet<QString> enabled;
          for (const auto &token :
               context[it.key()].toString().split(';', Qt::SkipEmptyParts))
            enabled.insert(token);
          for (const auto &token :
               it.value().toString().split(';', Qt::SkipEmptyParts)) {
            if (token.startsWith('!')) {
              const auto removed = token.mid(1);
              for (auto entry = enabled.begin(); entry != enabled.end();)
                if (*entry == removed || entry->startsWith(removed + ":"))
                  entry = enabled.erase(entry);
                else
                  ++entry;
            } else
              enabled.insert(token);
          }
          auto values = enabled.values();
          values.sort();
          context[it.key()] = values.join(';');
        }
        permissions["Context"] = context;
        result["permissions"] = permissions;
        result["overrides"] = overridesObject;
        result["overrideText"] = QString::fromUtf8(overrides.output);
        return result;
      }
      const auto system =
          QFileInfo("/usr/share/applications/" + desktop).canonicalFilePath();
      if (!system.startsWith("/usr/share/applications/")) {
        result["removable"] = false;
        return result;
      }
      const auto owner = command("pacman", {"-Qoq", "--", system});
      if (owner.exitCode == 0) {
        const auto package = QString::fromUtf8(owner.output).trimmed();
        if (!package.contains('\n')) {
          const auto version = command("pacman", {"-Q", "--", package});
          result["package"] = package;
          result["version"] =
              QString::fromUtf8(version.output).trimmed().section(' ', 1);
          result["removable"] = true;
        }
      }
      result["limits"] =
          "Native applications are not sandboxed by these controls. AppArmor "
          "applies only when a matching profile is loaded and enforced.";
      return result;
    }
    // All changes target a single application's per-user overrides. Never
    // accept
    // --system, --installation, global resets, or a caller-provided program.
    if (operation == "apps.flatpak-reset") {
      if (!QRegularExpression("^[A-Za-z0-9_-]+(?:\\.[A-Za-z0-9_-]+){2,}$")
               .match(id)
               .hasMatch())
        return QJsonObject{{"error", "Invalid Flatpak application ID"}};
      const auto result =
          command("flatpak", {"override", "--user", "--reset", id});
      return result.exitCode == 0 ? QJsonObject{{"ok", true}} : failure(result);
    }
    if (operation == "apps.flatpak-override") {
      if (!QRegularExpression("^[A-Za-z0-9_-]+(?:\\.[A-Za-z0-9_-]+){2,}$")
               .match(id)
               .hasMatch())
        return QJsonObject{{"error", "Invalid Flatpak application ID"}};
      const QStringList allowed{"share-if",
                                "socket-if",
                                "device-if",
                                "allow-if",
                                "a11y-own-name",
                                "usb-list",
                                "usb-list-file",
                                "share",
                                "unshare",
                                "socket",
                                "nosocket",
                                "device",
                                "nodevice",
                                "allow",
                                "disallow",
                                "filesystem",
                                "nofilesystem",
                                "persist",
                                "env",
                                "unset-env",
                                "own-name",
                                "talk-name",
                                "no-talk-name",
                                "system-own-name",
                                "system-talk-name",
                                "system-no-talk-name",
                                "add-policy",
                                "remove-policy",
                                "usb",
                                "nousb"};
      QStringList options{"override", "--user"};
      const auto values = args["options"].toArray();
      if (values.size() > 64)
        return QJsonObject{{"error", "Too many permission changes"}};
      for (const auto &value : values) {
        const auto option = value.toString();
        if (!option.startsWith("--") || option.size() > 4096 ||
            option.contains(QChar::Null))
          return QJsonObject{{"error", "Invalid Flatpak override"}};
        const auto key = option.mid(2).section('=', 0, 0);
        if (!allowed.contains(key))
          return QJsonObject{
              {"error", "Unsupported permission override: " + key}};
        if (!option.contains('='))
          return QJsonObject{{"error", "Override values must follow '='"}};
        options << option;
      }
      options << id;
      const auto result = command("flatpak", options);
      return result.exitCode == 0 ? QJsonObject{{"ok", true}} : failure(result);
    }
    if (operation == "apps.autostart") {
      const auto config =
          QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) +
          "/autostart/" + desktop;
      const auto system = "/etc/xdg/autostart/" + desktop;
      const auto source = QFileInfo(config).isFile() ? config
                          : QFileInfo(system).isFile()
                              ? system
                              : args["path"].toString();
      if (!QFileInfo(source).isFile() || QFileInfo(source).isSymLink() ||
          QFileInfo(source).size() > 1024 * 1024)
        return QJsonObject{{"error", "No usable application desktop file"}};
      QFile input(source);
      if (!input.open(QIODevice::ReadOnly))
        return QJsonObject{{"error", "Cannot read autostart entry"}};
      const auto bytes = input.readAll();
      saveAutostart(config, bytes, !args["enabled"].toBool());
      return QJsonObject{{"ok", true}};
    }
    return QJsonObject{{"error", "Unknown application operation"}};
  });
}
} // namespace HicsDesktop
