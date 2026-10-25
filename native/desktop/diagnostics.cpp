#include "service.hpp"
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusReply>
#include <QDBusVariant>
#include <QDateTime>
#include <QFileInfo>
#include <QJsonArray>
#include <QRegularExpression>
#include <QStandardPaths>
namespace HicsDesktop {
void Service::diagnostics(const QSharedPointer<Job> &job) {
  const auto args = job->arguments;
  const auto dir = directory;
  if (job->operation == "diagnostics.repair") {
    const auto id = args["id"].toString();
    if (id == "audio-output") {
      process(job, "wpctl", {"set-mute", "@DEFAULT_AUDIO_SINK@", "0"}, false,
              10000);
      return;
    }
    if (id == "audio-service") {
      process(job, "systemctl",
              {"--user", "restart", "pipewire.service",
               "pipewire-pulse.service", "wireplumber.service"},
              false, 30000);
      return;
    }
    if (id == "screen-sharing") {
      process(job, "systemctl",
              {"--user", "restart", "xdg-desktop-portal-hyprland.service",
               "xdg-desktop-portal.service"},
              false, 30000);
      return;
    }
    if (id == "internet-check") {
      worker(job, [] {
        auto call = QDBusMessage::createMethodCall(
            "org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager",
            "org.freedesktop.NetworkManager", "CheckConnectivity");
        const auto reply =
            QDBusConnection::systemBus().call(call, QDBus::Block, 15000);
        return reply.type() == QDBusMessage::ErrorMessage
                   ? QJsonObject{{"error", reply.errorMessage()}}
                   : QJsonObject{{"connectivity",
                                  int(reply.arguments().value(0).toUInt())}};
      });
      return;
    }
    finish(job, {}, "Choose an available repair action");
    return;
  }
  if (job->operation == "diagnostics.export") {
    worker(job, [args, dir] {
      const auto path = args["path"].toString();
      if (!QFileInfo(path).isAbsolute() || !path.endsWith(".json") ||
          QFileInfo(path).isSymLink())
        return QJsonObject{{"error", "Choose a local JSON file"}};
      const auto report = readJson(dir + "/diagnostics.json");
      if (report.isEmpty())
        return QJsonObject{{"error", "Run checks before exporting a report"}};
      writeJson(path, report);
      return QJsonObject{{"ok", true}, {"path", path}};
    });
    return;
  }
  if (job->operation != "diagnostics.check") {
    finish(job, {}, "Unknown diagnostic operation");
    return;
  }
  worker(job, [dir] {
    QJsonArray checks;
    auto service = [&](const QString &id, const QString &name,
                       const QString &busName, bool system,
                       const QString &hint) {
      auto bus =
          system ? QDBusConnection::systemBus() : QDBusConnection::sessionBus();
      auto result = bus.interface()->isServiceRegistered(busName);
      checks.append(QJsonObject{{"id", id},
                                {"name", name},
                                {"ok", result.isValid() && result.value()},
                                {"action", hint}});
    };
    service("network", "NetworkManager", "org.freedesktop.NetworkManager", true,
            "Open Network settings; check the connection and complete public "
            "Wi-Fi sign-in if offered.");
    auto get = QDBusMessage::createMethodCall(
        "org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager",
        "org.freedesktop.DBus.Properties", "Get");
    get.setArguments(
        {QString("org.freedesktop.NetworkManager"), QString("Connectivity")});
    const auto connectivity =
        QDBusConnection::systemBus().call(get, QDBus::Block, 3000);
    if (connectivity.type() != QDBusMessage::ErrorMessage) {
      const auto state =
          qvariant_cast<QDBusVariant>(connectivity.arguments().value(0))
              .variant()
              .toUInt();
      checks.append(QJsonObject{
          {"id", "internet"},
          {"name", "Internet connectivity"},
          {"ok", state == 4},
          {"state", int(state)},
          {"action",
           state == 2
               ? QString(
                     "Sign in to the public network using the network panel.")
               : QString("Recheck connectivity. A limited result can also mean "
                         "that the distribution's connectivity probe is "
                         "disabled or filtered.")}});
    }
    service("portal", "Desktop portal", "org.freedesktop.portal.Desktop", false,
            "Restart the sharing portal if the application shows no screen or "
            "window sources. Active sharing sessions will stop.");
    service("portal-backend", "Hyprland sharing backend",
            "org.freedesktop.impl.portal.desktop.hyprland", false,
            "Open screen sharing in an application to activate the backend; "
            "restart it if source selection fails.");
    service("keyring", "Password vault", "org.freedesktop.secrets", false,
            "Open Passwords & keys and unlock the login vault.");
    for (const auto &kind : {QString("output"), QString("microphone")}) {
      const auto result =
          command("wpctl",
                  {"get-volume", kind == "output" ? "@DEFAULT_AUDIO_SINK@"
                                                  : "@DEFAULT_AUDIO_SOURCE@"},
                  5000, 16384);
      const bool muted = result.output.contains("MUTED");
      checks.append(QJsonObject{
          {"id", kind},
          {"name", kind == "output" ? "Audio output" : "Microphone"},
          {"ok", result.exitCode == 0 && !muted},
          {"muted", muted},
          {"action",
           kind == "output"
               ? "Unmute the output, select the correct device and run the "
                 "left/right speaker test."
               : "Check the microphone privacy switch, select the input and "
                 "use the microphone test in Sound settings."}});
    }
    QJsonObject report{
        {"checks", checks},
        {"generated", QDateTime::currentDateTimeUtc().toString(Qt::ISODate)},
        {"scope", "Checks describe service availability and routing. Complete "
                  "the speaker, microphone or sharing test in the relevant "
                  "application to verify the entire path."}};
    // Allowlisted data only. Never collect journals, environment, arguments,
    // SSIDs, user paths, serials, passwords or authentication responses.
    writeJson(dir + "/diagnostics.json", report);
    return report;
  });
}
} // namespace HicsDesktop
