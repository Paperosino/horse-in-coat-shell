#include "workspacestore.hpp"
#include "workspacetools.hpp"
#include <QCoreApplication>
#include <QFile>
#include <QJsonDocument>
#include <QLockFile>
#include <QSettings>
#include <QMimeDatabase>
#include <QStandardPaths>
#include <QTimer>
#include <cstdio>
using namespace hyprstack::services;
namespace W = hics::workspace;
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  auto args = app.arguments();
  args.removeFirst();
  try {
    if (args.isEmpty() || args.first() == "--help") {
      puts(
          "hics-workspace capture [name] [--automatic]\nhics-workspace "
          "list\nhics-workspace restore <snapshot-id>\nhics-workspace startup");
      return 0;
    }
    if (args.first() == "cleanup") {
      if (W::settings("clipboard").value("clearOnLogout").toBool())
        W::clearClipboard(false);
      return 0;
    }
    if (args.first() == "clipboard-store") {
      const auto settings = W::settings("clipboard");
      if (!settings.value("enabled").toBool() ||
          settings.value("paused").toBool())
        return 0;
      if (qEnvironmentVariable("CLIPBOARD_STATE") == "sensitive" &&
          settings.value("ignoreSecrets").toBool())
        return 0;
      if (QFile::exists(QStandardPaths::writableLocation(
                            QStandardPaths::RuntimeLocation) +
                        "/hics-clipboard-locked") &&
          settings.value("pauseWhenLocked").toBool())
        return 0;
      QByteArray types;
      try {
        types = W::command("wl-paste", {"--list-types"}, 1500);
      } catch (...) {
      }
      if (settings.value("ignoreSecrets").toBool() &&
          (types.contains("x-kde-passwordManagerHint") ||
           types.contains("application/x-keepassxc")))
        return 0;
      QString mime = args.value(1, "text/plain;charset=utf-8");
      QFile input;
      if (!input.open(stdin, QIODevice::ReadOnly))
        return 1;
      const auto bytes =
          input.read(settings.value("maxMiB").toLongLong() * 1024 * 1024 + 1);
      if(mime=="image/auto"){mime=QMimeDatabase().mimeTypeForData(bytes).name();if(!mime.startsWith("image/"))return 0;}
      QString source;
      try {
        source = QJsonDocument::fromJson(
                     W::command("hyprctl", {"-j", "activewindow"}, 1500))
                     .toVariant()
                     .toMap()
                     .value("class")
                     .toString();
      } catch (...) {
      }
      W::storeClipboard(bytes, mime, source);
      return 0;
    }
    WorkspaceSession session;
    if (args.first() == "list") {
      session.refresh();
      puts(QJsonDocument::fromVariant(session.snapshots())
               .toJson(QJsonDocument::Indented)
               .constData());
      return session.error().isEmpty() ? 0 : 1;
    }
    QObject::connect(&session, &WorkspaceSession::finished, &app,
                     [&](bool success) {
                       if (!success)
                         fprintf(stderr, "%s\n", qPrintable(session.error()));
                       app.exit(success ? 0 : 1);
                     });
    const auto mode = args.first();
    QTimer::singleShot(0, &app, [&] {
      try {
        if (mode == "capture")
          session.capture(args.contains("--automatic")
                              ? "Automatic checkpoint"
                              : args.value(1, "Session"),
                          args.contains("--automatic"));
        else if (mode == "restore")
          session.restore(args.value(1, "automatic"));
        else if (mode == "startup") {
          const auto settings = W::settings("session");
          if (!settings.value("enabled").toBool() ||
              settings.value("startup") == "none") {
            app.quit();
            return;
          }
          const auto id =
              settings.value("startupSnapshot", "automatic").toString();
          if (!QFile::exists(W::statePath() + "/sessions/" + id + ".json")) {
            app.quit();
            return;
          }
          const auto marker = W::startupPath();
          QLockFile startupLock(marker + ".lock");
          if (!startupLock.tryLock(0)) {
            app.quit();
            return;
          }
          const auto desktop = qEnvironmentVariable("XDG_CURRENT_DESKTOP");
          if (!desktop.contains("Hyprland", Qt::CaseInsensitive) &&
              !settings.value("crossDesktop").toBool()) {
            app.quit();
            return;
          }
          // One request per login, including shell/service restarts.
          const auto login =
              qEnvironmentVariable("XDG_SESSION_ID") + ":" +
              qEnvironmentVariable("HYPRLAND_INSTANCE_SIGNATURE");
          if (W::readMap(marker).value("login") == login) {
            app.quit();
            return;
          }
          W::writeMap(marker,
                      {{"login", login},
                       {"id", id},
                       {"pending", settings.value("startup") == "ask"}});
          if (settings.value("startup") == "automatic")
            session.restore(id);
          else if (desktop.contains("Hyprland", Qt::CaseInsensitive))
            app.quit();
          else {
            try {
              const auto action =
                  W::command("notify-send",
                             {"--wait", "--action=restore=Restore", "hics",
                              "Restore your saved application session?"},
                             120000);
              if (action.trimmed() == "restore") {
                session.restore(id);
                return;
              }
            } catch (...) {
            }
            app.quit();
          }
        } else
          app.exit(2);
      } catch (const std::exception &e) {
        fprintf(stderr, "%s\n", e.what());
        app.exit(1);
      }
    });
    return app.exec();
  } catch (const std::exception &e) {
    fprintf(stderr, "%s\n", e.what());
    return 1;
  }
}
