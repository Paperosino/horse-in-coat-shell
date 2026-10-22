#include "networkmanagervpn.hpp"
#include "vpnsecretagent.hpp"
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusMetaType>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusReply>
#include <QEventLoop>
#include <QFile>
#include <QJsonDocument>
#include <QTimer>
#include <QUuid>
#include <cstdio>
using namespace hyprstack::services;
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  NetworkManagerVpn vpn;
  auto mode = app.arguments().value(1);
  auto wait = [&] {
    QEventLoop loop;
    QObject::connect(&vpn, &NetworkManagerVpn::changed, &loop, [&] {
      if (!vpn.busy())
        loop.quit();
    });
    QTimer::singleShot(10000, &loop, &QEventLoop::quit);
    if (vpn.busy())
      loop.exec();
  };
  QVariantMap result;
  QString prefilled;
  if (mode.startsWith("agent-")) {
    VpnSecretAgent agent;
    QObject::connect(&agent, &VpnSecretAgent::changed, &app, [&] {
      if (!agent.challenge().isEmpty()) {
        prefilled = agent.challenge()
                        .value("fields")
                        .toList()
                        .value(0)
                        .toMap()
                        .value("value")
                        .toString();
        if (mode == "agent-cancel")
          agent.cancel();
        else
          agent.submit({{"password", "agent-fixture"}}, false);
      }
    });
    auto bus = QDBusConnection::systemBus();
    QEventLoop loop;
    QDBusMessage request;
    if (mode == "agent-untrusted") {
      request = QDBusMessage::createMethodCall(
          bus.baseService(), "/org/freedesktop/NetworkManager/SecretAgent",
          "org.freedesktop.NetworkManager.SecretAgent", "GetSecrets");
      VpnSettings connection{{"connection", {{"uuid", "test"}}}};
      request.setArguments({QVariant::fromValue(connection),
                            QVariant::fromValue(QDBusObjectPath("/test")),
                            "vpn", QStringList{}, uint(3)});
    } else {
      request = QDBusMessage::createMethodCall(
          "org.freedesktop.NetworkManager",
          "/org/freedesktop/NetworkManager/AgentManager", "org.hics.Test",
          "Request");
      request.setArguments({mode, bus.baseService()});
    }
    QDBusPendingCallWatcher watcher(bus.asyncCall(request));
    QObject::connect(&watcher, &QDBusPendingCallWatcher::finished, &loop,
                     &QEventLoop::quit);
    QTimer::singleShot(12000, &loop, &QEventLoop::quit);
    loop.exec();
    if (mode == "agent-untrusted") {
      QDBusPendingReply<VpnSettings> reply = watcher;
      result = {{"errorName", reply.error().name()}};
    } else {
      QDBusPendingReply<QString> reply = watcher;
      result = reply.isError()
                   ? QVariantMap{{"errorName", reply.error().name()}}
                   : QJsonDocument::fromJson(reply.value().toUtf8())
                         .toVariant()
                         .toMap();
    }
    if (mode == "agent-prompt-prefill")
      result["prefilled"] = prefilled;
  } else if (mode == "draft") {
    vpn.edit("/org/freedesktop/NetworkManager/Settings/1");
    wait();
    result = {{"draft", vpn.draft()}, {"error", vpn.error()}};
  } else if (mode == "roundtrip-no-secrets") {
    // Explicit host integration mode: never activate the disposable profile.
    QString path;
    QObject::connect(&vpn, &NetworkManagerVpn::saved, &app,
                     [&](const QString &p) { path = p; });
    auto settle = [&] {
      while (vpn.busy())
        wait();
    };
    vpn.create("org.freedesktop.NetworkManager.libreswan");
    auto draft = vpn.draft();
    draft["name"] = "hics-secret-check-" +
                    QUuid::createUuid().toString(QUuid::WithoutBraces);
    draft["data"] = QVariantMap{{"right", "vpn.invalid"},
                                {"pskvalue-flags", "0"},
                                {"xauthpassword-flags", "0"}};
    vpn.save(draft);
    settle();
    QString failure = vpn.error();
    if (failure.isEmpty() && !path.isEmpty()) {
      vpn.edit(path);
      settle();
      draft = vpn.draft();
      draft["secrets"] = QVariantMap{{"xauthpassword", "new-fixture-password"}};
      vpn.save(draft);
      settle();
      failure = vpn.error();
    }
    result = {{"error", failure}, {"path", path}};
    if (failure.isEmpty() && !path.isEmpty()) {
      qDBusRegisterMetaType<VpnSettings>();
      qDBusRegisterMetaType<QMap<QString, QString>>();
      auto request = QDBusMessage::createMethodCall(
          "org.freedesktop.NetworkManager", path,
          "org.freedesktop.NetworkManager.Settings.Connection", "GetSecrets");
      request.setArguments({"vpn"});
      QDBusReply<VpnSettings> reply =
          QDBusConnection::systemBus().call(request, QDBus::Block, 10000);
      auto values = qdbus_cast<QMap<QString, QString>>(
          reply.value().value("vpn").value("secrets"));
      result["readError"] = reply.error().name();
      result["secretKeys"] = values.keys();
      result["passwordPersisted"] =
          reply.isValid() &&
          values.value("xauthpassword") == "new-fixture-password";
    }
    if (!path.isEmpty()) {
      vpn.remove(path);
      settle();
      result["cleanupError"] = vpn.error();
    }
  } else if (mode == "change-protocol" || mode == "change-protocol-active") {
    auto request = QDBusMessage::createMethodCall(
        "org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager",
        "org.hics.Test", "SetActiveState");
    request.setArguments({uint(mode == "change-protocol-active" ? 2 : 0)});
    QDBusConnection::systemBus().call(request);
    vpn.edit("/org/freedesktop/NetworkManager/Settings/1");
    wait();
    auto draft = vpn.draft();
    auto ip = draft.value("ip4").toMap();
    ip["priority"] = -88;
    draft["ip4"] = ip;
    draft["type"] = "org.freedesktop.NetworkManager.l2tp";
    draft["data"] = QVariantMap{{"gateway", "vpn.example"},
                                {"user", "fixture"},
                                {"ipsec-enabled", "yes"}};
    draft["secrets"] = QVariantMap{{"password", "new-protocol-password"}};
    vpn.save(draft);
    wait();
    result = {{"error", vpn.error()}};
  } else if (mode == "export") {
    vpn.exportFile("/org/freedesktop/NetworkManager/Settings/1",
                   QUrl::fromLocalFile(app.arguments().value(2)));
    wait();
    result = {{"error", vpn.error()}};
  } else if (mode == "list" || mode == "list-disconnected") {
    auto request = QDBusMessage::createMethodCall(
        "org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager",
        "org.hics.Test", "SetActiveState");
    request.setArguments({uint(mode == "list-disconnected" ? 4 : 0)});
    QDBusConnection::systemBus().call(request);
    vpn.refresh();
    wait();
    result = {{"plugins", vpn.plugins()},
              {"profiles", vpn.profiles()},
              {"error", vpn.error()}};
  } else if (mode == "edit" || mode == "edit-no-secrets" ||
             mode == "edit-empty-secrets" || mode == "edit-denied") {
    vpn.edit(mode == "edit" ? "/org/freedesktop/NetworkManager/Settings/1"
             : mode == "edit-denied"
                 ? "/org/freedesktop/NetworkManager/Settings/4"
                 : "/org/freedesktop/NetworkManager/Settings/3");
    wait();
    auto draft = vpn.draft();
    auto ip = draft.value("ip4").toMap();
    ip["dns"] = "9.9.9.9";
    ip["ignoreAutoDns"] = true;
    ip["priority"] = -50;
    draft["ip4"] = ip;
    draft["name"] = "Edited VPN";
    if (mode == "edit-no-secrets")
      draft["secrets"] = QVariantMap{{"xauthpassword", "new-fixture-password"}};
    vpn.save(draft);
    wait();
    result = {{"error", vpn.error()}};
  } else if (mode == "invalid-dns" || mode == "invalid-route") {
    vpn.create("org.freedesktop.NetworkManager.pptp");
    auto draft = vpn.draft();
    draft["name"] = "Bad profile";
    draft["data"] = QVariantMap{{"gateway", "vpn.example"}};
    auto ip = draft.value("ip4").toMap();
    ip[mode == "invalid-dns" ? "dns" : "routes"] =
        mode == "invalid-dns" ? "not-an-ip" : "not-a-route";
    draft["ip4"] = ip;
    result = vpn.validate(draft);
  } else if (mode == "create") {
    vpn.create("org.freedesktop.NetworkManager.pptp");
    auto draft = vpn.draft();
    draft["name"] = "PPTP fixture";
    draft["data"] = QVariantMap{{"gateway", "vpn.example"},
                                {"user", "fixture"},
                                {"require-mppe", "yes"}};
    draft["secrets"] = QVariantMap{{"password", "test-password"}};
    vpn.save(draft);
    wait();
    result = {{"error", vpn.error()}};
  } else if (mode == "wireguard" || mode == "change-wireguard") {
    QVariantMap original;
    if (mode == "change-wireguard") {
      vpn.edit("/org/freedesktop/NetworkManager/Settings/1");
      wait();
      original = vpn.draft();
    }
    vpn.create("wireguard");
    auto draft = vpn.draft();
    if (!original.isEmpty())
      draft["path"] = original.value("path");
    draft["name"] = "WireGuard fixture";
    draft["interface"] = "wg-fixture";
    draft["secrets"] =
        QVariantMap{{"private-key", QString(QByteArray(32, 'a').toBase64())}};
    auto ip = draft.value("ip4").toMap();
    ip["addresses"] = "10.2.0.2/32";
    ip["dns"] = "9.9.9.9";
    draft["ip4"] = ip;
    draft["wireguard"] = QVariantMap{
        {"peerRoutes", true},
        {"peers", QVariantList{QVariantMap{
                      {"publicKey", QString(QByteArray(32, 'b').toBase64())},
                      {"endpoint", "vpn.example:51820"},
                      {"allowedIPs", "0.0.0.0/0, ::/0"},
                      {"keepalive", 25}}}}};
    vpn.save(draft);
    wait();
    if (!original.isEmpty() && vpn.error().isEmpty()) {
      if (vpn.busy())
        wait();
      vpn.save(original);
      wait();
    }
    result = {{"error", vpn.error()}};
  } else if (mode == "import") {
    vpn.importFile(app.arguments().value(2),
                   QUrl::fromLocalFile(app.arguments().value(3)));
    wait();
    result = {{"draft", vpn.draft()}, {"error", vpn.error()}};
  } else if (mode.startsWith("deactivate")) {
    vpn.deactivate("/org/freedesktop/NetworkManager/ActiveConnection/" +
                   QString(mode == "deactivate-inactive" ? "2"
                           : mode == "deactivate-denied" ? "3"
                                                         : "1"));
    wait();
    result = {{"error", vpn.error()}};
  } else if (mode == "activate" || mode == "activate-libreswan" ||
             mode == "activate-failure") {
    if (mode == "activate-failure") {
      auto request = QDBusMessage::createMethodCall(
          "org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager",
          "org.hics.Test", "SetFailure");
      request.setArguments({true});
      QDBusConnection::systemBus().call(request);
    }
    vpn.activate(mode == "activate-libreswan"
                     ? "/org/freedesktop/NetworkManager/Settings/3"
                     : "/org/freedesktop/NetworkManager/Settings/1");
    wait();
    if (mode == "activate-failure") {
      QEventLoop loop;
      QTimer::singleShot(400, &loop, &QEventLoop::quit);
      loop.exec();
    }
    result = {{"error", vpn.error()}};
  }
  auto data = QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact);
  puts(data.constData());
  return 0;
}
