#include "networkmanagervpn.hpp"
#include <QDBusConnection>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QFutureWatcher>
#include <QJsonArray>
#include <QJsonDocument>
#include <QProcess>
#include <QRandomGenerator>
#include <QRegularExpression>
#include <QSaveFile>
#include <QStandardPaths>
#include <QTemporaryDir>
#include <QThread>
#include <QUuid>
#include <QtConcurrent>
#include <cstring>
#include <stdexcept>
#include <sys/socket.h>
#pragma push_macro("signals")
#undef signals
#include <NetworkManager.h>
#pragma pop_macro("signals")

namespace hyprstack::services {
namespace {
using V = std::shared_ptr<GVariant>;
using C = std::shared_ptr<NMConnection>;
using B = std::shared_ptr<GDBusConnection>;
V variant(GVariant *value) {
  return V(value, [](GVariant *v) {
    if (v)
      g_variant_unref(v);
  });
}
C connection(NMConnection *value) {
  return C(value, [](NMConnection *v) {
    if (v)
      g_object_unref(v);
  });
}
NMSettingWireGuard *getWireGuard(NMConnection *c) {
  return NM_SETTING_WIREGUARD(
      nm_connection_get_setting(c, NM_TYPE_SETTING_WIREGUARD));
}
QString text(const char *value) {
  return QString::fromUtf8(value ? value : "");
}
[[noreturn]] void fail(const QString &message) {
  throw std::runtime_error(message.toStdString());
}
void check(GError *error) {
  if (error) {
    QString message = text(error->message);
    g_error_free(error);
    fail(message);
  }
}
const char *service = "org.freedesktop.NetworkManager";
const char *root = "/org/freedesktop/NetworkManager";
const char *settings = "/org/freedesktop/NetworkManager/Settings";
const char *settingsInterface =
    "org.freedesktop.NetworkManager.Settings.Connection";
B bus() {
  GError *error = nullptr;
  auto *b = g_bus_get_sync(G_BUS_TYPE_SYSTEM, nullptr, &error);
  check(error);
  return B(b, [](GDBusConnection *p) { g_object_unref(p); });
}
V call(GDBusConnection *b, const QString &path, const char *iface,
       const char *method, GVariant *args = nullptr) {
  GError *error = nullptr;
  auto *reply = g_dbus_connection_call_sync(
      b, service, path.toUtf8().constData(), iface, method, args, nullptr,
      G_DBUS_CALL_FLAGS_ALLOW_INTERACTIVE_AUTHORIZATION, 90000, nullptr,
      &error);
  check(error);
  return variant(reply);
}
V child(GVariant *value, gsize index = 0) {
  return variant(g_variant_get_child_value(value, index));
}
V property(GDBusConnection *b, const QString &path, const char *iface,
           const char *name) {
  auto reply = call(b, path, "org.freedesktop.DBus.Properties", "Get",
                    g_variant_new("(ss)", iface, name));
  auto wrapped = child(reply.get());
  return variant(g_variant_get_variant(wrapped.get()));
}
void ensureLibreswanService(GDBusConnection *b) {
  auto systemd = [&](const QString &path, const char *iface, const char *method,
                     GVariant *args) {
    GError *error = nullptr;
    auto reply = variant(g_dbus_connection_call_sync(
        b, "org.freedesktop.systemd1", path.toUtf8().constData(), iface, method,
        args, nullptr, G_DBUS_CALL_FLAGS_ALLOW_INTERACTIVE_AUTHORIZATION, 30000,
        nullptr, &error));
    if (error) {
      auto detail = text(error->message);
      g_error_free(error);
      fail("Cannot start the Libreswan IPsec service: " + detail);
    }
    return reply;
  };
  auto reply =
      systemd("/org/freedesktop/systemd1", "org.freedesktop.systemd1.Manager",
              "LoadUnit", g_variant_new("(s)", "ipsec.service"));
  auto object = child(reply.get());
  auto path = text(g_variant_get_string(object.get(), nullptr));
  auto state = [&] {
    auto reply = systemd(
        path, "org.freedesktop.DBus.Properties", "Get",
        g_variant_new("(ss)", "org.freedesktop.systemd1.Unit", "ActiveState"));
    auto wrapped = child(reply.get());
    auto value = variant(g_variant_get_variant(wrapped.get()));
    return text(g_variant_get_string(value.get(), nullptr));
  };
  if (state() == "active")
    return;
  systemd("/org/freedesktop/systemd1", "org.freedesktop.systemd1.Manager",
          "StartUnit", g_variant_new("(ss)", "ipsec.service", "replace"));
  QElapsedTimer timer;
  timer.start();
  while (timer.elapsed() < 20000) {
    const auto current = state();
    if (current == "active")
      return;
    if (current == "failed")
      fail("Libreswan IPsec service failed to start. Check ipsec.service.");
    QThread::msleep(100);
  }
  fail("Libreswan IPsec service did not become ready in time");
}
QString string(GVariant *value) {
  return value ? text(g_variant_get_string(value, nullptr)) : QString();
}
QString settingPath(const QString &path) {
  if (!QRegularExpression("^/org/freedesktop/NetworkManager/Settings/[0-9]+$")
           .match(path)
           .hasMatch())
    fail("Invalid NetworkManager profile path");
  return path;
}
C readConnection(GDBusConnection *b, const QString &path) {
  auto reply = call(b, settingPath(path), settingsInterface, "GetSettings");
  auto data = child(reply.get());
  GError *error = nullptr;
  auto c = connection(nm_simple_connection_new_from_dbus(data.get(), &error));
  check(error);
  if (!c)
    fail("NetworkManager returned an invalid profile");
  auto *meta = nm_connection_get_setting_connection(c.get());
  const auto type = text(nm_setting_connection_get_connection_type(meta));
  if (type != "vpn" && type != "wireguard")
    fail("This profile is not a VPN or WireGuard connection");
  return c;
}
void preserveSecrets(GDBusConnection *b, const QString &path, NMConnection *c) {
  const char *kind = nm_connection_get_setting_vpn(c) ? "vpn" : "wireguard";
  GError *error = nullptr;
  auto reply = variant(g_dbus_connection_call_sync(
      b, service, path.toUtf8().constData(), settingsInterface, "GetSecrets",
      g_variant_new("(s)", kind), nullptr,
      G_DBUS_CALL_FLAGS_ALLOW_INTERACTIVE_AUTHORIZATION, 90000, nullptr,
      &error));
  if (error) {
    char *remote = g_dbus_error_get_remote_error(error);
    const bool absent =
        g_strcmp0(remote,
                  "org.freedesktop.NetworkManager.AgentManager.NoSecrets") ==
            0 ||
        g_strcmp0(remote,
                  "org.freedesktop.NetworkManager.SecretAgent.NoSecrets") ==
            0 ||
        g_strcmp0(
            remote,
            "org.freedesktop.NetworkManager.Settings.Connection.NoSecrets") ==
            0;
    g_free(remote);
    // GetSecrets is non-interactive. A new, certificate-only or ask-each-time
    // profile may have no retrievable secrets. Keep its secret flags and apply
    // the user's new values normally; this does not mean the agent is absent.
    // Permission, transport and all other errors still abort the update.
    if (absent) {
      g_error_free(error);
      return;
    }
    check(error);
  }
  auto secrets = child(reply.get());
  if (!nm_connection_update_secrets(c, kind, secrets.get(), &error))
    check(error);
}
QStringList words(const QVariant &value) {
  if (value.metaType().id() == QMetaType::QStringList ||
      value.metaType().id() == QMetaType::QVariantList)
    return value.toStringList();
  return value.toString().split(QRegularExpression("[,\\s]+"),
                                Qt::SkipEmptyParts);
}
QString addresses(NMSettingIPConfig *ip) {
  QStringList values;
  for (guint i = 0; i < nm_setting_ip_config_get_num_addresses(ip); ++i) {
    auto *address = nm_setting_ip_config_get_address(ip, i);
    values << text(nm_ip_address_get_address(address)) + '/' +
                  QString::number(nm_ip_address_get_prefix(address));
  }
  return values.join('\n');
}
QString routes(NMSettingIPConfig *ip) {
  QStringList values;
  for (guint i = 0; i < nm_setting_ip_config_get_num_routes(ip); ++i) {
    auto *route = nm_setting_ip_config_get_route(ip, i);
    values << QString("%1/%2 %3 %4")
                  .arg(text(nm_ip_route_get_dest(route)))
                  .arg(nm_ip_route_get_prefix(route))
                  .arg(text(nm_ip_route_get_next_hop(route)).isEmpty()
                           ? "-"
                           : text(nm_ip_route_get_next_hop(route)))
                  .arg(nm_ip_route_get_metric(route));
  }
  return values.join('\n');
}
QVariantMap ipDraft(NMSettingIPConfig *ip) {
  if (!ip)
    return {};
  QStringList dns, domains, rules;
  for (guint i = 0; i < nm_setting_ip_config_get_num_dns(ip); ++i)
    dns << text(nm_setting_ip_config_get_dns(ip, i));
  for (guint i = 0; i < nm_setting_ip_config_get_num_dns_searches(ip); ++i)
    domains << text(nm_setting_ip_config_get_dns_search(ip, i));
  for (guint i = 0; i < nm_setting_ip_config_get_num_routing_rules(ip); ++i) {
    char *value = nm_ip_routing_rule_to_string(
        nm_setting_ip_config_get_routing_rule(ip, i),
        NM_IP_ROUTING_RULE_AS_STRING_FLAGS_NONE, nullptr, nullptr);
    rules << text(value);
    g_free(value);
  }
  return {{"method", text(nm_setting_ip_config_get_method(ip))},
          {"dns", dns.join(", ")},
          {"domains", domains.join(", ")},
          {"priority", nm_setting_ip_config_get_dns_priority(ip)},
          {"ignoreAutoDns", bool(nm_setting_ip_config_get_ignore_auto_dns(ip))},
          {"neverDefault", bool(nm_setting_ip_config_get_never_default(ip))},
          {"ignoreAutoRoutes",
           bool(nm_setting_ip_config_get_ignore_auto_routes(ip))},
          {"metric", qlonglong(nm_setting_ip_config_get_route_metric(ip))},
          {"gateway", text(nm_setting_ip_config_get_gateway(ip))},
          {"addresses", addresses(ip)},
          {"routes", routes(ip)},
          {"rules", rules.join('\n')}};
}
QVariantMap toDraft(NMConnection *c, const QString &path = {}) {
  auto *meta = nm_connection_get_setting_connection(c);
  auto *vpn = nm_connection_get_setting_vpn(c);
  QVariantMap data;
  if (vpn)
    nm_setting_vpn_foreach_data_item(
        vpn,
        [](const char *key, const char *value, gpointer out) {
          static_cast<QVariantMap *>(out)->insert(text(key), text(value));
        },
        &data);
  QVariantMap credentials;
  if (vpn)
    nm_setting_vpn_foreach_secret(
        vpn,
        [](const char *key, const char *value, gpointer out) {
          static_cast<QVariantMap *>(out)->insert(text(key), text(value));
        },
        &credentials);
  else if (auto *wg = getWireGuard(c))
    credentials["private-key"] = text(nm_setting_wireguard_get_private_key(wg));
  QVariantMap result{
      {"path", path},
      {"uuid", text(nm_connection_get_uuid(c))},
      {"name", text(nm_connection_get_id(c))},
      {"type", vpn ? text(nm_setting_vpn_get_service_type(vpn)) : "wireguard"},
      {"interface", text(nm_connection_get_interface_name(c))},
      {"autoconnect", bool(nm_setting_connection_get_autoconnect(meta))},
      {"data", data},
      {"secrets", credentials},
      {"ip4", ipDraft(nm_connection_get_setting_ip4_config(c))},
      {"ip6", ipDraft(nm_connection_get_setting_ip6_config(c))}};
  if (auto *wg = getWireGuard(c)) {
    guint port, mtu, fwmark;
    gboolean peerRoutes;
    g_object_get(wg, "listen-port", &port, "mtu", &mtu, "fwmark", &fwmark,
                 "peer-routes", &peerRoutes, nullptr);
    QVariantList peers;
    for (guint i = 0; i < nm_setting_wireguard_get_peers_len(wg); ++i) {
      auto *p = nm_setting_wireguard_get_peer(wg, i);
      QStringList allowed;
      for (guint j = 0; j < nm_wireguard_peer_get_allowed_ips_len(p); ++j)
        allowed << text(nm_wireguard_peer_get_allowed_ip(p, j, nullptr));
      peers << QVariantMap{
          {"publicKey", text(nm_wireguard_peer_get_public_key(p))},
          {"endpoint", text(nm_wireguard_peer_get_endpoint(p))},
          {"presharedKey", text(nm_wireguard_peer_get_preshared_key(p))},
          {"allowedIPs", allowed.join(", ")},
          {"keepalive", int(nm_wireguard_peer_get_persistent_keepalive(p))}};
    }
    result["wireguard"] = QVariantMap{{"listenPort", port},
                                      {"mtu", mtu},
                                      {"fwmark", fwmark},
                                      {"peerRoutes", bool(peerRoutes)},
                                      {"peers", peers}};
  }
  return result;
}
QList<QStringList> lines(const QString &value) {
  QList<QStringList> result;
  for (const auto &line : value.split('\n', Qt::SkipEmptyParts)) {
    auto parts =
        line.trimmed().split(QRegularExpression("\\s+"), Qt::SkipEmptyParts);
    if (!parts.isEmpty())
      result << parts;
  }
  return result;
}
void applyIp(NMConnection *c, const QVariantMap &data, bool ipv6) {
  if (data.isEmpty())
    return;
  auto *ip = ipv6 ? nm_connection_get_setting_ip6_config(c)
                  : nm_connection_get_setting_ip4_config(c);
  if (!ip) {
    nm_connection_add_setting(c, ipv6 ? nm_setting_ip6_config_new()
                                      : nm_setting_ip4_config_new());
    ip = ipv6 ? nm_connection_get_setting_ip6_config(c)
              : nm_connection_get_setting_ip4_config(c);
  }
  const int family = ipv6 ? AF_INET6 : AF_INET;
  auto method = data.value("method", "auto").toString().toUtf8();
  g_object_set(ip, "method", method.constData(), "ignore-auto-dns",
               data.value("ignoreAutoDns").toBool(), "never-default",
               data.value("neverDefault").toBool(), "ignore-auto-routes",
               data.value("ignoreAutoRoutes").toBool(), "dns-priority",
               data.value("priority").toInt(), "route-metric",
               gint64(data.value("metric", -1).toLongLong()), nullptr);
  if (data.contains("gateway")) {
    auto gateway = data.value("gateway").toString().toUtf8();
    g_object_set(ip, "gateway",
                 gateway.isEmpty() ? nullptr : gateway.constData(), nullptr);
  }
  nm_setting_ip_config_clear_dns(ip);
  nm_setting_ip_config_clear_dns_searches(ip);
  for (auto dns : words(data.value("dns"))) {
    auto encoded = dns.toUtf8();
    if (!nm_setting_ip_config_add_dns(ip, encoded.constData()))
      fail("Invalid or duplicate DNS server: " + dns);
  }
  for (auto domain : words(data.value("domains"))) {
    auto encoded = domain.toUtf8();
    if (!nm_setting_ip_config_add_dns_search(ip, encoded.constData()))
      fail("Invalid or duplicate DNS domain: " + domain);
  }
  // Preserve attributes of existing routes/addresses unless the user edited
  // them.
  if (data.contains("addresses") &&
      data.value("addresses").toString().trimmed() != addresses(ip)) {
    nm_setting_ip_config_clear_addresses(ip);
    for (const auto &line : lines(data.value("addresses").toString())) {
      auto address = line[0].split('/');
      bool ok = false;
      guint prefix = address.size() == 2 ? address[1].toUInt(&ok) : 0;
      if (!ok)
        fail("IP addresses need a prefix length");
      GError *error = nullptr;
      auto *value = nm_ip_address_new(family, address[0].toUtf8().constData(),
                                      prefix, &error);
      check(error);
      nm_setting_ip_config_add_address(ip, value);
      nm_ip_address_unref(value);
    }
  }
  if (data.contains("routes") &&
      data.value("routes").toString().trimmed() != routes(ip)) {
    nm_setting_ip_config_clear_routes(ip);
    for (const auto &line : lines(data.value("routes").toString())) {
      if (line.size() > 3)
        fail("Route format: network/prefix next-hop metric");
      auto destination = line[0].split('/');
      bool ok = false;
      guint prefix = destination.size() == 2 ? destination[1].toUInt(&ok) : 0;
      if (!ok)
        fail("Routes need a prefix length");
      auto next =
          line.size() > 1 && line[1] != "-" ? line[1].toUtf8() : QByteArray();
      qlonglong metric = line.size() > 2 ? line[2].toLongLong(&ok) : -1;
      if (!ok || metric < -1)
        fail("Invalid route metric");
      GError *error = nullptr;
      auto *value = nm_ip_route_new(
          family, destination[0].toUtf8().constData(), prefix,
          next.isEmpty() ? nullptr : next.constData(), metric, &error);
      check(error);
      nm_setting_ip_config_add_route(ip, value);
      nm_ip_route_unref(value);
    }
  }
  if (data.contains("rules")) {
    QStringList current;
    for (guint i = 0; i < nm_setting_ip_config_get_num_routing_rules(ip); ++i) {
      char *value = nm_ip_routing_rule_to_string(
          nm_setting_ip_config_get_routing_rule(ip, i),
          NM_IP_ROUTING_RULE_AS_STRING_FLAGS_NONE, nullptr, nullptr);
      current << text(value);
      g_free(value);
    }
    if (data.value("rules").toString().trimmed() != current.join('\n')) {
      nm_setting_ip_config_clear_routing_rules(ip);
      for (const auto &line :
           data.value("rules").toString().split('\n', Qt::SkipEmptyParts)) {
        GError *error = nullptr;
        auto *rule = nm_ip_routing_rule_from_string(
            line.toUtf8().constData(),
            ipv6 ? NM_IP_ROUTING_RULE_AS_STRING_FLAGS_AF_INET6
                 : NM_IP_ROUTING_RULE_AS_STRING_FLAGS_AF_INET,
            nullptr, &error);
        check(error);
        nm_setting_ip_config_add_routing_rule(ip, rule);
        nm_ip_routing_rule_unref(rule);
      }
    }
  }
}
C build(const C &base, const QVariantMap &draft) {
  auto c = base ? connection(nm_simple_connection_new_clone(base.get()))
                : connection(nm_simple_connection_new());
  const QString type = draft.value("type").toString();
  const bool wireguard = type == "wireguard";
  if (!wireguard && !type.startsWith("org.freedesktop.NetworkManager."))
    fail("Invalid VPN service type");
  const auto *oldVpn =
      base ? nm_connection_get_setting_vpn(base.get()) : nullptr;
  const QString oldType = oldVpn ? text(nm_setting_vpn_get_service_type(
                                       const_cast<NMSettingVpn *>(oldVpn)))
                                 : (base ? "wireguard" : "");
  if (base && oldType != type) {
    // Plugin credentials and settings belong to their original protocol only.
    nm_connection_remove_setting(c.get(), NM_TYPE_SETTING_VPN);
    nm_connection_remove_setting(c.get(), NM_TYPE_SETTING_WIREGUARD);
  }
  auto *meta = nm_connection_get_setting_connection(c.get());
  if (!meta) {
    nm_connection_add_setting(c.get(), nm_setting_connection_new());
    meta = nm_connection_get_setting_connection(c.get());
  }
  QString uuid = base ? text(nm_connection_get_uuid(base.get()))
                      : QUuid::createUuid().toString(QUuid::WithoutBraces);
  auto name = draft.value("name").toString().trimmed().toUtf8();
  if (name.isEmpty())
    fail("Connection name is required");
  auto iface = draft.value("interface").toString().trimmed().toUtf8();
  g_object_set(meta, "id", name.constData(), "uuid", uuid.toUtf8().constData(),
               "type", wireguard ? "wireguard" : "vpn", "interface-name",
               iface.isEmpty() ? nullptr : iface.constData(), "autoconnect",
               draft.value("autoconnect").toBool(), nullptr);
  const auto secrets = draft.value("secrets").toMap();
  if (!wireguard) {
    auto *vpn = nm_connection_get_setting_vpn(c.get());
    if (!vpn) {
      nm_connection_add_setting(c.get(), nm_setting_vpn_new());
      vpn = nm_connection_get_setting_vpn(c.get());
    }
    g_object_set(vpn, "service-type", type.toUtf8().constData(), nullptr);
    const auto data = draft.value("data").toMap();
    // The draft contains the full VPN dictionary. Unrecognized plugin keys
    // remain visible/editable and survive ordinary edits unchanged.
    QStringList old;
    nm_setting_vpn_foreach_data_item(
        vpn,
        [](const char *k, const char *, gpointer out) {
          static_cast<QStringList *>(out)->append(text(k));
        },
        &old);
    for (const auto &key : old)
      if (!data.contains(key))
        nm_setting_vpn_remove_data_item(vpn, key.toUtf8().constData());
    for (auto i = data.begin(); i != data.end(); ++i) {
      auto key = i.key().toUtf8();
      auto value = i.value().toString().toUtf8();
      if (!value.isEmpty())
        nm_setting_vpn_add_data_item(vpn, key.constData(), value.constData());
      else
        nm_setting_vpn_remove_data_item(vpn, key.constData());
    }
    for (const auto &key : draft.value("clearSecrets").toStringList())
      nm_setting_vpn_remove_secret(vpn, key.toUtf8().constData());
    for (auto i = secrets.begin(); i != secrets.end(); ++i)
      if (!i.value().toString().isEmpty()) {
        nm_setting_vpn_add_secret(vpn, i.key().toUtf8().constData(),
                                  i.value().toString().toUtf8().constData());
        auto flag = (i.key() + "-flags").toUtf8();
        nm_setting_vpn_add_data_item(vpn, flag.constData(), "0");
      }
  } else {
    auto *wg = getWireGuard(c.get());
    if (!wg) {
      nm_connection_add_setting(c.get(), nm_setting_wireguard_new());
      wg = getWireGuard(c.get());
    }
    const auto settings = draft.value("wireguard").toMap();
    g_object_set(wg, "listen-port",
                 guint(settings.value("listenPort").toUInt()), "mtu",
                 guint(settings.value("mtu").toUInt()), "fwmark",
                 guint(settings.value("fwmark").toUInt()), "peer-routes",
                 settings.value("peerRoutes", true).toBool(), nullptr);
    if (!secrets.value("private-key").toString().isEmpty())
      g_object_set(wg, "private-key",
                   secrets.value("private-key").toString().toUtf8().constData(),
                   "private-key-flags", guint(0), nullptr);
    if (draft.value("clearSecrets").toStringList().contains("private-key"))
      g_object_set(wg, "private-key", nullptr, nullptr);
    QMap<QString, std::shared_ptr<NMWireGuardPeer>> previous;
    for (guint i = 0; i < nm_setting_wireguard_get_peers_len(wg); ++i) {
      auto *p = nm_setting_wireguard_get_peer(wg, i);
      previous[text(nm_wireguard_peer_get_public_key(p))] = {
          nm_wireguard_peer_new_clone(p, true), nm_wireguard_peer_unref};
    }
    nm_setting_wireguard_clear_peers(wg);
    for (const auto &row : settings.value("peers").toList()) {
      const auto peer = row.toMap();
      auto key = peer.value("publicKey").toString();
      auto *p = previous.contains(key)
                    ? nm_wireguard_peer_new_clone(previous[key].get(), true)
                    : nm_wireguard_peer_new();
      if (!nm_wireguard_peer_set_public_key(p, key.toUtf8().constData(),
                                            false)) {
        nm_wireguard_peer_unref(p);
        fail("Invalid WireGuard public key");
      }
      if (!nm_wireguard_peer_set_endpoint(
              p, peer.value("endpoint").toString().toUtf8().constData(),
              false)) {
        nm_wireguard_peer_unref(p);
        fail("Invalid WireGuard endpoint");
      }
      nm_wireguard_peer_clear_allowed_ips(p);
      for (const auto &ip : words(peer.value("allowedIPs")))
        if (!nm_wireguard_peer_append_allowed_ip(p, ip.toUtf8().constData(),
                                                 false)) {
          nm_wireguard_peer_unref(p);
          fail("Invalid WireGuard allowed IP");
        }
      if (!peer.value("presharedKey").toString().isEmpty() &&
          !nm_wireguard_peer_set_preshared_key(
              p, peer.value("presharedKey").toString().toUtf8().constData(),
              false)) {
        nm_wireguard_peer_unref(p);
        fail("Invalid WireGuard preshared key");
      }
      if (!peer.value("presharedKey").toString().isEmpty())
        nm_wireguard_peer_set_preshared_key_flags(p,
                                                  NM_SETTING_SECRET_FLAG_NONE);
      int keepalive = peer.value("keepalive").toInt();
      if (keepalive < 0 || keepalive > 65535) {
        nm_wireguard_peer_unref(p);
        fail("Invalid WireGuard keepalive");
      }
      nm_wireguard_peer_set_persistent_keepalive(p, keepalive);
      nm_setting_wireguard_append_peer(wg, p);
      nm_wireguard_peer_unref(p);
    }
  }
  applyIp(c.get(), draft.value("ip4").toMap(), false);
  applyIp(c.get(), draft.value("ip6").toMap(), true);
  GError *error = nullptr;
  if (!nm_connection_normalize(c.get(), nullptr, nullptr, &error))
    check(error);
  if (!nm_connection_verify(c.get(), &error))
    check(error);
  if (!nm_connection_verify_secrets(c.get(), &error))
    check(error);
  return c;
}
QVariantList catalogue() {
  QFile file(":/hics/vpn/vpn-protocols.json");
  if (!file.open(QIODevice::ReadOnly))
    fail("VPN protocol catalogue is unavailable");
  auto result = QJsonDocument::fromJson(file.readAll()).array().toVariantList();
  GSList *plugins = nm_vpn_plugin_info_list_load();
  for (auto &row : result) {
    auto p = row.toMap();
    auto service = p.value("service").toString().toUtf8();
    auto *info =
        nm_vpn_plugin_info_list_find_by_service(plugins, service.constData());
    p["installed"] = p.value("id") == "wireguard" || info;
    p["canImport"] = p.value("id") == "wireguard";
    p["canExport"] = p.value("id") == "wireguard";
    if (info) {
      GError *error = nullptr;
      auto *editor = nm_vpn_plugin_info_load_editor_plugin(info, &error);
      if (editor) {
        auto capabilities = nm_vpn_editor_plugin_get_capabilities(editor);
        p["canImport"] =
            bool(capabilities & NM_VPN_EDITOR_PLUGIN_CAPABILITY_IMPORT);
        p["canExport"] =
            bool(capabilities & NM_VPN_EDITOR_PLUGIN_CAPABILITY_EXPORT);
      }
      if (error)
        g_error_free(error);
    }
    row = p;
  }
  for (auto *node = plugins; node; node = node->next) {
    auto *info = static_cast<NMVpnPluginInfo *>(node->data);
    auto service = text(nm_vpn_plugin_info_get_service(info));
    bool found = false;
    for (const auto &row : result)
      if (row.toMap().value("service") == service)
        found = true;
    if (!found) {
      bool canImport = false, canExport = false;
      GError *error = nullptr;
      auto *editor = nm_vpn_plugin_info_load_editor_plugin(info, &error);
      if (editor) {
        auto caps = nm_vpn_editor_plugin_get_capabilities(editor);
        canImport = caps & NM_VPN_EDITOR_PLUGIN_CAPABILITY_IMPORT;
        canExport = caps & NM_VPN_EDITOR_PLUGIN_CAPABILITY_EXPORT;
      }
      if (error)
        g_error_free(error);
      result << QVariantMap{{"id", text(nm_vpn_plugin_info_get_name(info))},
                            {"name", text(nm_vpn_plugin_info_get_name(info))},
                            {"service", service},
                            {"installed", true},
                            {"canImport", canImport},
                            {"canExport", canExport},
                            {"fields", QVariantList{}}};
    }
  }
  g_slist_free_full(plugins, g_object_unref);
  return result;
}
QVariantList listProfiles(GDBusConnection *b) {
  auto activePaths = property(b, root, service, "ActiveConnections");
  QMap<QString, QVariantMap> active;
  for (gsize i = 0; i < g_variant_n_children(activePaths.get()); ++i) {
    auto path = string(child(activePaths.get(), i).get());
    auto uuid = property(
        b, path, "org.freedesktop.NetworkManager.Connection.Active", "Uuid");
    auto state = property(
        b, path, "org.freedesktop.NetworkManager.Connection.Active", "State");
    if (g_variant_get_uint32(state.get()) ==
        NM_ACTIVE_CONNECTION_STATE_DEACTIVATED)
      continue;
    active[string(uuid.get())] = {{"activePath", path},
                                  {"state", g_variant_get_uint32(state.get())}};
  }
  auto reply = call(b, settings, "org.freedesktop.NetworkManager.Settings",
                    "ListConnections");
  auto paths = child(reply.get());
  QVariantList result;
  for (gsize i = 0; i < g_variant_n_children(paths.get()); ++i) {
    auto path = string(child(paths.get(), i).get());
    try {
      auto c = readConnection(b, path);
      auto *vpn = nm_connection_get_setting_vpn(c.get());
      auto uuid = text(nm_connection_get_uuid(c.get()));
      auto item = active.value(uuid);
      item["path"] = path;
      item["uuid"] = uuid;
      item["name"] = text(nm_connection_get_id(c.get()));
      item["type"] =
          vpn ? text(nm_setting_vpn_get_service_type(vpn)) : "wireguard";
      item["active"] = item.contains("activePath");
      result << item;
    } catch (const std::exception
                 &) { /* Non-VPN profiles are not part of this page. */
    }
  }
  return result;
}
} // namespace
struct NetworkManagerVpn::State {
  QMap<QString, C> imported;
};
NetworkManagerVpn::NetworkManagerVpn(QObject *parent)
    : QObject(parent), m_state(std::make_shared<State>()) {}
NetworkManagerVpn::~NetworkManagerVpn() = default;
void NetworkManagerVpn::run(std::function<QVariantMap()> task,
                            std::function<void(const QVariantMap &)> done,
                            bool clearError) {
  if (m_busy)
    return;
  m_busy = true;
  if (clearError)
    m_error.clear();
  emit changed();
  auto *watcher = new QFutureWatcher<QVariantMap>(this);
  connect(watcher, &QFutureWatcher<QVariantMap>::finished, this,
          [this, watcher, done, clearError] {
            auto result = watcher->result();
            watcher->deleteLater();
            m_busy = false;
            if (clearError || result.contains("error"))
              m_error = result.value("error").toString();
            emit changed();
            if (!result.contains("error"))
              done(result);
          });
  watcher->setFuture(QtConcurrent::run([task] {
    try {
      return task();
    } catch (const std::exception &e) {
      return QVariantMap{{"error", QString::fromUtf8(e.what())}};
    }
  }));
}
void NetworkManagerVpn::refresh() {
  run(
      [] {
        auto plugins = catalogue();
        auto b = bus();
        return QVariantMap{{"plugins", plugins},
                           {"profiles", listProfiles(b.get())}};
      },
      [this](const QVariantMap &result) {
        m_plugins = result.value("plugins").toList();
        m_profiles = result.value("profiles").toList();
        emit changed();
      },
      false);
}
void NetworkManagerVpn::create(const QString &service) {
  if (m_busy)
    return;
  discard();
  m_error.clear();
  m_draft = {
      {"name", ""},
      {"type", service},
      {"data", QVariantMap{}},
      {"secrets", QVariantMap{}},
      {"ip4",
       QVariantMap{{"method", service == "wireguard" ? "manual" : "auto"},
                   {"metric", -1}}},
      {"ip6",
       QVariantMap{{"method", service == "wireguard" ? "disabled" : "auto"},
                   {"metric", -1}}},
      {"wireguard",
       QVariantMap{{"peerRoutes", true}, {"peers", QVariantList{}}}}};
  emit changed();
  emit draftChanged();
}
void NetworkManagerVpn::edit(const QString &path) {
  run(
      [path] {
        auto b = bus();
        auto c = readConnection(b.get(), path);
        preserveSecrets(b.get(), path, c.get());
        return toDraft(c.get(), path);
      },
      [this](const QVariantMap &draft) {
        discard();
        m_draft = draft;
        emit draftChanged();
      });
}
QVariantMap NetworkManagerVpn::validate(const QVariantMap &draft) const {
  try {
    build({}, draft);
    return {};
  } catch (const std::exception &e) {
    return {{"error", QString::fromUtf8(e.what())}};
  }
}
void NetworkManagerVpn::save(const QVariantMap &draft) {
  auto state = m_state;
  run(
      [draft, state] {
        auto b = bus();
        const auto path = draft.value("path").toString();
        C base;
        if (!path.isEmpty()) {
          base = readConnection(b.get(), path);
          auto *oldVpn = nm_connection_get_setting_vpn(base.get());
          const QString oldType =
              oldVpn ? text(nm_setting_vpn_get_service_type(oldVpn))
                     : "wireguard";
          if (oldType == draft.value("type").toString())
            preserveSecrets(b.get(), path, base.get());
          else {
            for (const auto &entry : listProfiles(b.get())) {
              const auto profile = entry.toMap();
              if (profile.value("path").toString() == path &&
                  profile.value("active").toBool())
                fail("Disconnect the VPN before changing its protocol");
            }
          }
        } else
          base = state->imported.value(draft.value("importToken").toString());
        auto c = build(base, draft);
        auto data = variant(
            nm_connection_to_dbus(c.get(), NM_CONNECTION_SERIALIZE_ALL));
        QString saved;
        if (path.isEmpty()) {
          auto reply =
              call(b.get(), settings, "org.freedesktop.NetworkManager.Settings",
                   "AddConnection2",
                   g_variant_new("(@a{sa{sv}}ua{sv})",
                                 g_variant_ref(data.get()), 1u, nullptr));
          saved = string(child(reply.get()).get());
        } else {
          call(b.get(), path, settingsInterface, "Update2",
               g_variant_new("(@a{sa{sv}}ua{sv})", g_variant_ref(data.get()),
                             1u, nullptr));
          saved = path;
        }
        state->imported.remove(draft.value("importToken").toString());
        return QVariantMap{{"path", saved}};
      },
      [this](const QVariantMap &result) {
        m_draft.clear();
        emit draftChanged();
        emit saved(result.value("path").toString());
        refresh();
      });
}
void NetworkManagerVpn::remove(const QString &path) {
  run(
      [path] {
        auto b = bus();
        auto c = readConnection(b.get(), path);
        call(b.get(), path, settingsInterface, "Delete");
        return QVariantMap{};
      },
      [this](const QVariantMap &) {
        emit operationSucceeded();
        refresh();
      });
}
void NetworkManagerVpn::activate(const QString &path) {
  run(
      [path] {
        auto b = bus();
        auto c = readConnection(b.get(), path);
        if (auto *vpn = nm_connection_get_setting_vpn(c.get());
            vpn && text(nm_setting_vpn_get_service_type(vpn)) ==
                       "org.freedesktop.NetworkManager.libreswan")
          ensureLibreswanService(b.get());
        auto reply =
            call(b.get(), root, service, "ActivateConnection",
                 g_variant_new("(ooo)", path.toUtf8().constData(), "/", "/"));
        return QVariantMap{{"activePath", string(child(reply.get()).get())}};
      },
      [this](const QVariantMap &result) {
        if (!m_activationPath.isEmpty()) {
          QDBusConnection::systemBus().disconnect(
              service, m_activationPath,
              "org.freedesktop.NetworkManager.VPN.Connection",
              "VpnStateChanged", this, SLOT(vpnStateChanged(uint, uint)));
          QDBusConnection::systemBus().disconnect(
              service, m_activationPath,
              "org.freedesktop.NetworkManager.Connection.Active",
              "StateChanged", this, SLOT(activationStateChanged(uint, uint)));
        }
        m_vpnFailureReceived = false;
        m_activationPath = result.value("activePath").toString();
        QDBusConnection::systemBus().connect(
            service, m_activationPath,
            "org.freedesktop.NetworkManager.Connection.Active", "StateChanged",
            this, SLOT(activationStateChanged(uint, uint)));
        QDBusConnection::systemBus().connect(
            service, m_activationPath,
            "org.freedesktop.NetworkManager.VPN.Connection", "VpnStateChanged",
            this, SLOT(vpnStateChanged(uint, uint)));
        emit operationSucceeded();
        refresh();
      });
}
void NetworkManagerVpn::vpnStateChanged(uint state, uint reason) {
  if (state != NM_VPN_CONNECTION_STATE_FAILED &&
      state != NM_VPN_CONNECTION_STATE_DISCONNECTED)
    return;
  if (reason == NM_VPN_CONNECTION_STATE_REASON_USER_DISCONNECTED)
    return;
  activationStateChanged(4, reason);
  m_vpnFailureReceived = true;
}
void NetworkManagerVpn::activationStateChanged(uint state, uint reason) {
  if (state != NM_ACTIVE_CONNECTION_STATE_DEACTIVATED)
    return;
  for (auto &entry : m_profiles) {
    auto profile = entry.toMap();
    if (profile.value("activePath").toString() != m_activationPath)
      continue;
    profile.remove("activePath");
    profile["active"] = false;
    profile["state"] = NM_ACTIVE_CONNECTION_STATE_DEACTIVATED;
    entry = profile;
  }
  emit changed();
  if (reason == 2 || (reason == 0 && m_vpnFailureReceived))
    return;
  switch (reason) {
  case 3:
    m_error = tr("The underlying network disconnected");
    break;
  case 4:
    m_error = tr("The VPN service stopped. Check the protocol service and its "
                 "configuration.");
    break;
  case 5:
    m_error = tr("The VPN returned an invalid IP configuration");
    break;
  case 6:
  case 7:
    m_error = tr("The VPN connection timed out");
    break;
  case 8:
    m_error = tr(
        "The VPN plugin could not start. Check that its package is installed.");
    break;
  case 9:
    m_error = tr("VPN credentials are missing or authentication was canceled");
    break;
  case 10:
    m_error = tr("The VPN server rejected authentication");
    break;
  default:
    m_error = tr("The VPN connection failed before completion. See the "
                 "protocol service log for details.");
    break;
  }
  emit changed();
}
void NetworkManagerVpn::installPlugin(const QString &id) {
  run(
      [id] {
        QVariantMap selected;
        for (const auto &entry : catalogue())
          if (entry.toMap().value("id") == id)
            selected = entry.toMap();
        auto package = selected.value("package").toString();
        if (!QRegularExpression("^networkmanager-[a-z0-9-]+$")
                 .match(package)
                 .hasMatch())
          fail("This plugin has no supported Arch package");
        if (!QFileInfo::exists("/usr/bin/pacman") ||
            QStandardPaths::findExecutable("pkexec").isEmpty())
          fail("Install the VPN plugin with your distribution's package "
               "manager: " +
               package);
        QProcess process;
        process.start("pkexec", {"/usr/bin/pacman", "-S", "--needed",
                                 "--noconfirm", package});
        if (!process.waitForStarted(10000))
          fail("Could not start the package installer");
        if (!process.waitForFinished(300000)) {
          process.kill();
          process.waitForFinished();
          fail("Plugin installation timed out");
        }
        if (process.exitCode() != 0)
          fail(QString::fromUtf8(process.readAllStandardError()).trimmed());
        return QVariantMap{};
      },
      [this](const QVariantMap &) {
        emit operationSucceeded();
        refresh();
      });
}

void NetworkManagerVpn::deactivate(const QString &path) {
  run(
      [path] {
        if (!QRegularExpression(
                 "^/org/freedesktop/NetworkManager/ActiveConnection/[0-9]+$")
                 .match(path)
                 .hasMatch())
          fail("Invalid active connection path");
        auto b = bus();
        GError *error = nullptr;
        auto reply = variant(g_dbus_connection_call_sync(
            b.get(), service, root, service, "DeactivateConnection",
            g_variant_new("(o)", path.toUtf8().constData()), nullptr,
            G_DBUS_CALL_FLAGS_ALLOW_INTERACTIVE_AUTHORIZATION, 90000, nullptr,
            &error));
        if (error) {
          // The VPN may finish disconnecting between the UI click and this
          // call.
          auto name = g_dbus_error_get_remote_error(error);
          const bool alreadyInactive =
              g_strcmp0(name,
                        "org.freedesktop.NetworkManager.ConnectionNotActive") ==
              0;
          g_free(name);
          if (!alreadyInactive)
            check(error);
          else
            g_error_free(error);
        }
        return QVariantMap{};
      },
      [this](const QVariantMap &) {
        emit operationSucceeded();
        refresh();
      });
}
void NetworkManagerVpn::importFile(const QString &service, const QUrl &url) {
  auto state = m_state;
  run(
      [service, url, state] {
        if (!url.isLocalFile() || !QFileInfo(url.toLocalFile()).isFile())
          fail("Select a local VPN configuration file");
        auto filename = url.toLocalFile().toUtf8();
        GError *error = nullptr;
        C c;
        if (url.toLocalFile().endsWith(".nmconnection")) {
          GKeyFile *keyfile = g_key_file_new();
          if (g_key_file_load_from_file(keyfile, filename.constData(),
                                        G_KEY_FILE_NONE, &error))
            c = connection(nm_keyfile_read(keyfile,
                                           QFileInfo(url.toLocalFile())
                                               .absolutePath()
                                               .toUtf8()
                                               .constData(),
                                           NM_KEYFILE_HANDLER_FLAGS_NONE,
                                           nullptr, nullptr, &error));
          g_key_file_unref(keyfile);
          if (c && !nm_connection_get_setting_vpn(c.get()) &&
              !getWireGuard(c.get()))
            fail("The imported profile is not a VPN or WireGuard connection");
        } else if (service == "wireguard")
          c = connection(
              nm_conn_wireguard_import(filename.constData(), &error));
        else {
          GSList *plugins = nm_vpn_plugin_info_list_load();
          auto name = service.toUtf8();
          auto *info = nm_vpn_plugin_info_list_find_by_service(
              plugins, name.constData());
          if (!info) {
            g_slist_free_full(plugins, g_object_unref);
            fail("Install the NetworkManager plugin before importing this "
                 "protocol");
          }
          auto *editor = nm_vpn_plugin_info_load_editor_plugin(info, &error);
          if (editor)
            c = connection(nm_vpn_editor_plugin_import(
                editor, filename.constData(), &error));
          g_slist_free_full(plugins, g_object_unref);
        }
        check(error);
        if (!c)
          fail("This plugin could not import the configuration");
        auto uuid = QUuid::createUuid().toString(QUuid::WithoutBraces).toUtf8();
        g_object_set(nm_connection_get_setting_connection(c.get()), "uuid",
                     uuid.constData(), nullptr);
        auto token = QUuid::createUuid().toString();
        state->imported.clear();
        state->imported[token] = c;
        auto draft = toDraft(c.get());
        draft["importToken"] = token;
        return draft;
      },
      [this](const QVariantMap &draft) {
        m_draft = draft;
        emit draftChanged();
      });
}
void NetworkManagerVpn::exportFile(const QString &path, const QUrl &url) {
  run(
      [path, url] {
        if (!url.isLocalFile())
          fail("Select a local export destination");
        auto b = bus();
        auto c = readConnection(b.get(), path);
        preserveSecrets(b.get(), path, c.get());
        auto *vpn = nm_connection_get_setting_vpn(c.get());
        if (url.toLocalFile().endsWith(".nmconnection")) {
          GError *error = nullptr;
          auto *keyfile = nm_keyfile_write(
              c.get(), NM_KEYFILE_HANDLER_FLAGS_NONE, nullptr, nullptr, &error);
          check(error);
          gsize length = 0;
          char *data = g_key_file_to_data(keyfile, &length, &error);
          g_key_file_unref(keyfile);
          check(error);
          QByteArray bytes(data, qsizetype(length));
          g_free(data);
          QSaveFile file(url.toLocalFile());
          if (!file.open(QIODevice::WriteOnly))
            fail(file.errorString());
          file.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);
          if (file.write(bytes) != bytes.size() || !file.commit())
            fail(file.errorString());
          return QVariantMap{};
        }
        if (!vpn) {
          auto *wg = getWireGuard(c.get());
          QStringList output;
          output << "[Interface]"
                 << "PrivateKey = " +
                        text(nm_setting_wireguard_get_private_key(wg));
          QStringList allAddresses, dns;
          for (auto *ip : {nm_connection_get_setting_ip4_config(c.get()),
                           nm_connection_get_setting_ip6_config(c.get())})
            if (ip) {
              allAddresses << addresses(ip).split('\n', Qt::SkipEmptyParts);
              for (guint i = 0; i < nm_setting_ip_config_get_num_dns(ip); ++i)
                dns << text(nm_setting_ip_config_get_dns(ip, i));
            }
          if (!allAddresses.isEmpty())
            output << "Address = " + allAddresses.join(", ");
          if (!dns.isEmpty())
            output << "DNS = " + dns.join(", ");
          auto port = nm_setting_wireguard_get_listen_port(wg);
          if (port)
            output << "ListenPort = " + QString::number(port);
          auto mtu = nm_setting_wireguard_get_mtu(wg);
          if (mtu)
            output << "MTU = " + QString::number(mtu);
          auto fwmark = nm_setting_wireguard_get_fwmark(wg);
          if (fwmark)
            output << "FwMark = " + QString::number(fwmark);
          for (guint i = 0; i < nm_setting_wireguard_get_peers_len(wg); ++i) {
            auto *p = nm_setting_wireguard_get_peer(wg, i);
            output << "" << "[Peer]"
                   << "PublicKey = " +
                          text(nm_wireguard_peer_get_public_key(p));
            auto endpoint = text(nm_wireguard_peer_get_endpoint(p));
            if (!endpoint.isEmpty())
              output << "Endpoint = " + endpoint;
            QStringList allowed;
            for (guint j = 0; j < nm_wireguard_peer_get_allowed_ips_len(p); ++j)
              allowed << text(nm_wireguard_peer_get_allowed_ip(p, j, nullptr));
            if (!allowed.isEmpty())
              output << "AllowedIPs = " + allowed.join(", ");
            auto preshared = text(nm_wireguard_peer_get_preshared_key(p));
            if (!preshared.isEmpty())
              output << "PresharedKey = " + preshared;
            auto keepalive = nm_wireguard_peer_get_persistent_keepalive(p);
            if (keepalive)
              output << "PersistentKeepalive = " + QString::number(keepalive);
          }
          QSaveFile file(url.toLocalFile());
          if (!file.open(QIODevice::WriteOnly))
            fail(file.errorString());
          file.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);
          auto bytes = (output.join('\n') + '\n').toUtf8();
          if (file.write(bytes) != bytes.size() || !file.commit())
            fail(file.errorString());
          return QVariantMap{};
        }
        GSList *plugins = nm_vpn_plugin_info_list_load();
        auto *info = nm_vpn_plugin_info_list_find_by_service(
            plugins, nm_setting_vpn_get_service_type(vpn));
        GError *error = nullptr;
        auto *editor = info
                           ? nm_vpn_plugin_info_load_editor_plugin(info, &error)
                           : nullptr;
        QTemporaryDir directory(QFileInfo(url.toLocalFile()).absolutePath() +
                                "/.hics-vpn-export-XXXXXX");
        if (!directory.isValid()) {
          g_slist_free_full(plugins, g_object_unref);
          check(error);
          fail("Cannot create a private export directory");
        }
        auto temporary =
            directory.filePath(QFileInfo(url.toLocalFile()).fileName());
        bool ok = editor &&
                  nm_vpn_editor_plugin_export(
                      editor, temporary.toUtf8().constData(), c.get(), &error);
        g_slist_free_full(plugins, g_object_unref);
        check(error);
        if (!ok)
          fail("This plugin does not support export");
        QFile source(temporary);
        if (!source.open(QIODevice::ReadOnly))
          fail(source.errorString());
        auto bytes = source.readAll();
        QSaveFile target(url.toLocalFile());
        if (!target.open(QIODevice::WriteOnly))
          fail(target.errorString());
        if (!target.setPermissions(QFileDevice::ReadOwner |
                                   QFileDevice::WriteOwner))
          fail(target.errorString());
        if (target.write(bytes) != bytes.size() || !target.commit())
          fail(target.errorString());
        return QVariantMap{};
      },
      [this](const QVariantMap &) { emit operationSucceeded(); });
}
QString NetworkManagerVpn::generateWireGuardKey() const {
  QByteArray key(32, Qt::Uninitialized);
  for (int i = 0; i < 32; i += 4) {
    quint32 value = QRandomGenerator::system()->generate();
    std::memcpy(key.data() + i, &value, 4);
  }
  key[0] = char(uchar(key[0]) & 248);
  key[31] = char((uchar(key[31]) & 127) | 64);
  return QString::fromLatin1(key.toBase64());
}
void NetworkManagerVpn::discard() {
  if (m_busy)
    return;
  m_draft.clear();
  m_state->imported.clear();
  emit draftChanged();
}
} // namespace hyprstack::services
