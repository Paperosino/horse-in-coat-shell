#include "networkservice.hpp"
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QHostAddress>
#include <QPointer>
#include <QRegularExpression>
#include <QUuid>
#include <sys/socket.h>
#include <unordered_map>
#pragma push_macro("signals")
#undef signals
#include <NetworkManager.h>
#pragma pop_macro("signals")
using namespace Qt::StringLiterals;
namespace hyprstack::services {
namespace {
QString str(const char *v) { return QString::fromUtf8(v ? v : ""); }
QString ssid(GBytes *bytes) {
  if (!bytes)
    return {};
  gsize size;
  const auto *data = static_cast<const char *>(g_bytes_get_data(bytes, &size));
  return QString::fromUtf8(data, int(size));
}
QString deviceState(NMDeviceState state) {
  if (state == NM_DEVICE_STATE_ACTIVATED)
    return u"connected"_s;
  if (state >= NM_DEVICE_STATE_PREPARE && state <= NM_DEVICE_STATE_SECONDARIES)
    return u"connecting"_s;
  if (state == NM_DEVICE_STATE_UNAVAILABLE ||
      state == NM_DEVICE_STATE_UNMANAGED)
    return u"unavailable"_s;
  return u"disconnected"_s;
}
QString security(NMSettingWirelessSecurity *s) {
  if (!s)
    return {};
  const auto key = str(nm_setting_wireless_security_get_key_mgmt(s));
  if (key == u"sae"_s)
    return u"WPA3"_s;
  if (key.contains(u"eap"_s) || key == u"ieee8021x"_s)
    return u"WPA-EAP"_s;
  if (key == u"owe"_s)
    return u"OWE"_s;
  if (key == u"none"_s)
    return u"WEP"_s;
  return u"WPA2"_s;
}
QVariantMap ip(NMDevice *device) {
  QVariantMap r{{u"ipAddress"_s, u""_s},
                {u"gateway"_s, u""_s},
                {u"dns"_s, QStringList{}},
                {u"subnet"_s, u""_s}};
  auto *config = nm_device_get_ip4_config(device);
  if (!config)
    return r;
  auto *addresses = nm_ip_config_get_addresses(config);
  if (addresses && addresses->len) {
    auto *address = static_cast<NMIPAddress *>(addresses->pdata[0]);
    const int prefix = nm_ip_address_get_prefix(address);
    r[u"ipAddress"_s] = str(nm_ip_address_get_address(address));
    r[u"prefix"_s] = prefix;
    r[u"subnet"_s] =
        QHostAddress(prefix ? quint32(0xffffffffU << (32 - prefix)) : 0)
            .toString();
  }
  r[u"gateway"_s] = str(nm_ip_config_get_gateway(config));
  QStringList dns;
  const auto *servers = nm_ip_config_get_nameservers(config);
  if (servers)
    for (int i = 0; servers[i]; ++i)
      dns << str(servers[i]);
  r[u"dns"_s] = dns;
  return r;
}
QVariantMap ipv4(NMConnection *c) {
  auto *p = nm_connection_get_setting_ip4_config(c);
  auto *setting = nm_connection_get_setting_connection(c);
  QVariantMap r{
      {u"method"_s, u"auto"_s},
      {u"address"_s, u""_s},
      {u"gateway"_s, u""_s},
      {u"dns"_s, u""_s},
      {u"ignoreAutoDns"_s, false},
      {u"autoconnect"_s,
       !setting || bool(nm_setting_connection_get_autoconnect(setting))}};
  if (!p)
    return r;
  const bool ignore = nm_setting_ip_config_get_ignore_auto_dns(p);
  QString method = str(nm_setting_ip_config_get_method(p));
  r[u"method"_s] = method == u"auto"_s && ignore ? u"auto-dns"_s : method;
  r[u"ignoreAutoDns"_s] = ignore;
  r[u"gateway"_s] = str(nm_setting_ip_config_get_gateway(p));
  if (nm_setting_ip_config_get_num_addresses(p)) {
    auto *a = nm_setting_ip_config_get_address(p, 0);
    r[u"address"_s] = str(nm_ip_address_get_address(a)) + u"/"_s +
                      QString::number(nm_ip_address_get_prefix(a));
  }
  QStringList dns;
  for (guint i = 0; i < nm_setting_ip_config_get_num_dns(p); ++i)
    dns << str(nm_setting_ip_config_get_dns(p, i));
  r[u"dns"_s] = dns.join(u", "_s);
  return r;
}
} // namespace
struct NetworkService::Worker {
  QPointer<NetworkService> owner;
  GMainContext *context = g_main_context_new();
  GMainLoop *loop = g_main_loop_new(context, false);
  GCancellable *cancel = g_cancellable_new();
  NMClient *client = nullptr;
  bool closing = false;
  int pending = 1;
  GSource *debounce = nullptr;
  std::unordered_map<GObject *, std::vector<gulong>> watches;
  ~Worker() {
    g_object_unref(cancel);
    g_main_loop_unref(loop);
    g_main_context_unref(context);
  }
  void quitIfDone() {
    if (closing && pending == 0)
      g_main_loop_quit(loop);
  }
  void post(QVariantMap state) {
    auto target = owner;
    if (target)
      QMetaObject::invokeMethod(
          target,
          [target, state] {
            if (target && target->m_state != state) {
              target->m_state = state;
              emit target->stateChanged();
            }
          },
          Qt::QueuedConnection);
  }
  void result(int id, QString error = {}, QVariantMap data = {}) {
    data[u"success"_s] = error.isEmpty();
    data[u"error"_s] = error;
    data[u"exitCode"_s] = error.isEmpty() ? 0 : 1;
    data[u"output"_s] = QString();
    data[u"needsPassword"_s] =
        error.contains(u"secret"_s, Qt::CaseInsensitive) ||
        error.contains(u"password"_s, Qt::CaseInsensitive);
    auto target = owner;
    if (target)
      QMetaObject::invokeMethod(
          target,
          [target, id, data] {
            if (target)
              emit target->operationFinished(id, data);
          },
          Qt::QueuedConnection);
  }
  void schedule() {
    if (closing || debounce)
      return;
    debounce = g_timeout_source_new(30);
    g_source_set_callback(
        debounce,
        [](gpointer data) -> gboolean {
          auto *self = static_cast<Worker *>(data);
          auto *source = self->debounce;
          self->debounce = nullptr;
          g_source_unref(source);
          self->snapshot();
          return G_SOURCE_REMOVE;
        },
        this, nullptr);
    g_source_attach(debounce, context);
  }
  void watch(GObject *object, const char *signal = "notify") {
    if (!object || watches.contains(object))
      return;
    g_object_ref(object);
    watches[object].push_back(g_signal_connect_swapped(
        object, signal, G_CALLBACK(+[](Worker *self) { self->schedule(); }),
        this));
  }
  void resetWatches() {
    for (auto &[object, ids] : watches) {
      for (auto id : ids)
        g_signal_handler_disconnect(object, id);
      g_object_unref(object);
    }
    watches.clear();
  }
  void snapshot() {
    if (closing || !client)
      return;
    resetWatches();
    watch(G_OBJECT(client));
    // Object lists are cached by a single NMClient. No per-profile bus round
    // trips.
    QVariantList wireless, ethernet, aps, profiles;
    bool connected = false;
    QString activeInterface, activeConnection;
    QVariantMap unique;
    const auto *connections = nm_client_get_connections(client);
    if (connections)
      for (guint i = 0; i < connections->len; ++i) {
        auto *c = NM_CONNECTION(connections->pdata[i]);
        watch(G_OBJECT(c), "changed");
        auto *w = nm_connection_get_setting_wireless(c);
        auto *cs = nm_connection_get_setting_connection(c);
        if (!cs)
          continue;
        profiles << QVariantMap{
            {u"id"_s, str(nm_setting_connection_get_id(cs))},
            {u"uuid"_s, str(nm_setting_connection_get_uuid(cs))},
            {u"type"_s, str(nm_setting_connection_get_connection_type(cs))},
            {u"ssid"_s, w ? ssid(nm_setting_wireless_get_ssid(w)) : QString()},
            {u"security"_s,
             security(nm_connection_get_setting_wireless_security(c))},
            {u"autoconnect"_s, bool(nm_setting_connection_get_autoconnect(cs))},
            {u"ipv4"_s, ipv4(c)}};
      }
    const auto *devices = nm_client_get_devices(client);
    if (devices)
      for (guint i = 0; i < devices->len; ++i) {
        auto *d = NM_DEVICE(devices->pdata[i]);
        watch(G_OBJECT(d));
        auto *config = nm_device_get_ip4_config(d);
        if (config)
          watch(G_OBJECT(config));
        auto *active = nm_device_get_active_connection(d);
        if (active)
          watch(G_OBJECT(active));
        const QString iface = str(nm_device_get_iface(d));
        const bool online = nm_device_get_state(d) == NM_DEVICE_STATE_ACTIVATED;
        const QString name =
            active ? str(nm_active_connection_get_id(active)) : QString();
        auto row = ip(d);
        row[u"interface"_s] = iface;
        row[u"device"_s] = iface;
        row[u"state"_s] = deviceState(nm_device_get_state(d));
        row[u"connection"_s] = name;
        row[u"connected"_s] = online;
        row[u"failed"_s] = nm_device_get_state(d) == NM_DEVICE_STATE_FAILED;
        row[u"reason"_s] = int(nm_device_get_state_reason(d));
        row[u"needsPassword"_s] = nm_device_get_state_reason(d) ==
                                      NM_DEVICE_STATE_REASON_NO_SECRETS ||
                                  nm_device_get_state_reason(d) ==
                                      NM_DEVICE_STATE_REASON_SUPPLICANT_FAILED;
        row[u"macAddress"_s] = str(nm_device_get_hw_address(d));
        row[u"type"_s] = NM_IS_DEVICE_WIFI(d) ? u"wifi"_s : u"ethernet"_s;
        if (online && (activeInterface.isEmpty() ||
                       nm_client_get_primary_connection(client) == active)) {
          connected = true;
          activeInterface = iface;
          activeConnection = name;
        }
        if (NM_IS_DEVICE_ETHERNET(d) && !nm_device_is_software(d)) {
          row[u"carrier"_s] =
              bool(nm_device_ethernet_get_carrier(NM_DEVICE_ETHERNET(d)));
          row[u"speedMbps"_s] =
              nm_device_ethernet_get_speed(NM_DEVICE_ETHERNET(d));
          ethernet << row;
        }
        if (!NM_IS_DEVICE_WIFI(d))
          continue;
        wireless << row;
        auto *wifi = NM_DEVICE_WIFI(d);
        auto *apActive = nm_device_wifi_get_active_access_point(wifi);
        const auto *points = nm_device_wifi_get_access_points(wifi);
        if (points)
          for (guint j = 0; j < points->len; ++j) {
            auto *ap = NM_ACCESS_POINT(points->pdata[j]);
            watch(G_OBJECT(ap));
            const QString name = ssid(nm_access_point_get_ssid(ap));
            if (name.isEmpty())
              continue;
            auto flags = nm_access_point_get_rsn_flags(ap);
            auto wpa = nm_access_point_get_wpa_flags(ap);
            QString sec;
            if (flags & NM_802_11_AP_SEC_KEY_MGMT_SAE)
              sec = u"WPA3"_s;
            else if (flags & NM_802_11_AP_SEC_KEY_MGMT_OWE)
              sec = u"OWE"_s;
            else if ((flags | wpa) & NM_802_11_AP_SEC_KEY_MGMT_802_1X)
              sec = u"WPA-EAP"_s;
            else if (flags)
              sec = u"WPA2"_s;
            else if (wpa)
              sec = u"WPA"_s;
            else if (nm_access_point_get_flags(ap) & NM_802_11_AP_FLAGS_PRIVACY)
              sec = u"WEP"_s;
            QVariantMap point{
                {u"ssid"_s, name},
                {u"bssid"_s, str(nm_access_point_get_bssid(ap))},
                {u"strength"_s, nm_access_point_get_strength(ap)},
                {u"frequency"_s, nm_access_point_get_frequency(ap)},
                {u"active"_s, ap == apActive},
                {u"security"_s, sec},
                {u"interface"_s, iface}};
            auto old = unique.value(name).toMap();
            if (old.isEmpty() || point[u"active"_s].toBool() ||
                (!old[u"active"_s].toBool() &&
                 point[u"strength"_s].toInt() > old[u"strength"_s].toInt()))
              unique[name] = point;
          }
      }
    for (auto it = unique.cbegin(); it != unique.cend(); ++it)
      aps << it.value();
    post({{u"connectivity"_s,int(nm_client_get_connectivity(client))},
          {u"connectivityCheckAvailable"_s,bool(nm_client_connectivity_check_get_available(client))},
          {u"connectivityCheckEnabled"_s,bool(nm_client_connectivity_check_get_enabled(client))},
          {u"connectivityCheckUri"_s,str(nm_client_connectivity_check_get_uri(client))},
          {u"available"_s, bool(nm_client_get_nm_running(client))},
          {u"wifiEnabled"_s, bool(nm_client_wireless_get_enabled(client))},
          {u"wireless"_s, wireless},
          {u"ethernet"_s, ethernet},
          {u"networks"_s, aps},
          {u"profiles"_s, profiles},
          {u"connected"_s, connected},
          {u"activeInterface"_s, activeInterface},
          {u"activeConnection"_s, activeConnection}});
  }
  NMRemoteConnection *profile(QString name) {
    const auto *rows = nm_client_get_connections(client);
    if (rows)
      for (guint i = 0; i < rows->len; ++i) {
        auto *c = NM_REMOTE_CONNECTION(rows->pdata[i]);
        if (str(nm_connection_get_uuid(NM_CONNECTION(c))) == name ||
            str(nm_connection_get_id(NM_CONNECTION(c))) == name)
          return c;
      }
    return nullptr;
  }
  NMDevice *device(QString name, bool wifi = false) {
    const auto *rows = nm_client_get_devices(client);
    if (rows)
      for (guint i = 0; i < rows->len; ++i) {
        auto *d = NM_DEVICE(rows->pdata[i]);
        if ((!wifi || NM_IS_DEVICE_WIFI(d)) &&
            (name.isEmpty() || str(nm_device_get_iface(d)) == name))
          return d;
      }
    return nullptr;
  }
  struct Job {
    Worker *self;
    int id;
    QString kind;
    NMConnection *draft = nullptr;
    NMDevice *dev = nullptr;
    NMRemoteConnection *remote = nullptr;
    bool activate = false;
    ~Job() {
      if (draft)
        g_object_unref(draft);
      if (dev)
        g_object_unref(dev);
      if (remote)
        g_object_unref(remote);
    }
  };
  void complete(Job *job, GError *error = nullptr) {
    result(job->id, error ? str(error->message) : QString());
    if (error)
      g_error_free(error);
    delete job;
    --pending;
    schedule();
    quitIfDone();
  }
  static void finished(GObject *source, GAsyncResult *result, gpointer data) {
    auto *job = static_cast<Job *>(data);
    auto *self = job->self;
    GError *error = nullptr;
    if (job->kind == u"connectivity"_s)
      nm_client_check_connectivity_finish(NM_CLIENT(source),result,&error);
    else if (job->kind == u"wifi"_s)
      nm_client_dbus_set_property_finish(NM_CLIENT(source), result, &error);
    else if (job->kind == u"scan"_s)
      nm_device_wifi_request_scan_finish(NM_DEVICE_WIFI(source), result,
                                         &error);
    else if (job->kind == u"disconnect"_s)
      nm_device_disconnect_finish(NM_DEVICE(source), result, &error);
    else if (job->kind == u"forget"_s)
      nm_remote_connection_delete_finish(NM_REMOTE_CONNECTION(source), result,
                                         &error);
    else if (job->kind == u"update"_s) {
      auto *value = nm_remote_connection_update2_finish(
          NM_REMOTE_CONNECTION(source), result, &error);
      if (value)
        g_variant_unref(value);
      if (!error && job->activate && !self->closing) {
        job->kind = u"activate"_s;
        nm_client_activate_connection_async(
            self->client, NM_CONNECTION(job->remote), job->dev, nullptr,
            self->cancel, finished, job);
        return;
      }
    } else {
      NMActiveConnection *connection =
          job->kind == u"add"_s
              ? nm_client_add_and_activate_connection_finish(NM_CLIENT(source),
                                                             result, &error)
              : nm_client_activate_connection_finish(NM_CLIENT(source), result,
                                                     &error);
      if (connection)
        g_object_unref(connection);
    }
    self->complete(job, error);
  }
  void update(Job *job) {
    job->kind = u"update"_s;
    auto *settings = g_variant_ref_sink(
        nm_connection_to_dbus(job->draft, NM_CONNECTION_SERIALIZE_ALL));
    nm_remote_connection_update2(job->remote, settings,
                                 NM_SETTINGS_UPDATE2_FLAG_TO_DISK, nullptr,
                                 cancel, finished, job);
    g_variant_unref(settings);
  }
  void request(int id, QString op, QVariantMap args) {
    if (pending >= 64) {
      result(id, u"Too many pending network operations"_s);
      return;
    }
    if (closing || !client || !nm_client_get_nm_running(client)) {
      result(id, u"NetworkManager is not available"_s);
      return;
    }
    if (op == u"refresh"_s) {
      snapshot();
      result(id);
      return;
    }

    auto *job = new Job{this, id, op};
    ++pending;
    auto *d = device(args.value(u"interface"_s).toString(),
                     op == u"connect"_s || op == u"scan"_s);
    if (d)
      job->dev = NM_DEVICE(g_object_ref(d));
    auto fail = [&](QString message) {
      result(id, message);
      delete job;
      --pending;
      quitIfDone();
    };
    if(op == u"connectivity"_s){nm_client_check_connectivity_async(client,cancel,finished,job);return;}
    if (op == u"wifi"_s) {
      nm_client_dbus_set_property(
          client, NM_DBUS_PATH, NM_DBUS_INTERFACE, "WirelessEnabled",
          g_variant_new_boolean(args.value(u"enabled"_s).toBool()), 15000,
          cancel, finished, job);
      return;
    }
    if (op == u"scan"_s) {
      if (!NM_IS_DEVICE_WIFI(d)) {
        fail(u"No wireless interface"_s);
        return;
      }
      nm_device_wifi_request_scan_async(NM_DEVICE_WIFI(d), cancel, finished,
                                        job);
      return;
    }
    if (op == u"disconnect"_s) {
      if (!d) {
        auto *c = profile(args.value(u"connection"_s).toString());
        const auto *rows = nm_client_get_devices(client);
        if (rows)
          for (guint i = 0; i < rows->len; ++i) {
            auto *candidate = NM_DEVICE(rows->pdata[i]);
            auto *a = nm_device_get_active_connection(candidate);
            if (a && nm_active_connection_get_connection(a) == c) {
              d = candidate;
              break;
            }
          }
      }
      if (!d) {
        fail(u"Connection is already disconnected"_s);
        return;
      }
      nm_device_disconnect_async(d, cancel, finished, job);
      return;
    }
    auto *c = profile(args.value(u"connection"_s).toString());
    if (op == u"connect"_s) {
      if (!NM_IS_DEVICE_WIFI(d)) {
        fail(u"No wireless interface"_s);
        return;
      }
      const QString name = args.value(u"ssid"_s).toString(),
                    password = args.value(u"password"_s).toString(),
                    bssid = args.value(u"bssid"_s).toString();
      if (name.toUtf8().isEmpty() || name.toUtf8().size() > 32) {
        fail(u"SSID must contain 1–32 bytes"_s);
        return;
      }
      NMAccessPoint *selected = nullptr;
      const auto *points = nm_device_wifi_get_access_points(NM_DEVICE_WIFI(d));
      if (points)
        for (guint i = 0; i < points->len; ++i) {
          auto *ap = NM_ACCESS_POINT(points->pdata[i]);
          if (ssid(nm_access_point_get_ssid(ap)) == name &&
              (bssid.isEmpty() ||
               str(nm_access_point_get_bssid(ap))
                       .compare(bssid, Qt::CaseInsensitive) == 0)) {
            selected = ap;
            break;
          }
        }
      const auto *rows = nm_client_get_connections(client);
      if (rows)
        for (guint i = 0; i < rows->len; ++i) {
          auto *candidate = NM_CONNECTION(rows->pdata[i]);
          auto *w = nm_connection_get_setting_wireless(candidate);
          if (w && ssid(nm_setting_wireless_get_ssid(w)) == name &&
              nm_device_connection_valid(d, candidate)) {
            c = NM_REMOTE_CONNECTION(candidate);
            break;
          }
        }
      if (c && password.isEmpty()) {
        job->kind = u"activate"_s;
        nm_client_activate_connection_async(
            client, NM_CONNECTION(c), d,
            selected ? nm_object_get_path(NM_OBJECT(selected)) : nullptr,
            cancel, finished, job);
        return;
      }
      job->draft = c ? nm_simple_connection_new_clone(NM_CONNECTION(c))
                     : nm_simple_connection_new();
      if (!c) {
        auto *cs = nm_setting_connection_new();
        const auto uuid =
            QUuid::createUuid().toString(QUuid::WithoutBraces).toUtf8();
        const auto bytes = name.toUtf8();
        g_object_set(cs, NM_SETTING_CONNECTION_ID, bytes.constData(),
                     NM_SETTING_CONNECTION_UUID, uuid.constData(),
                     NM_SETTING_CONNECTION_TYPE,
                     NM_SETTING_WIRELESS_SETTING_NAME, nullptr);
        nm_connection_add_setting(job->draft, cs);
        auto *wifi = nm_setting_wireless_new();
        auto *value = g_bytes_new(bytes.constData(), bytes.size());
        g_object_set(wifi, NM_SETTING_WIRELESS_SSID, value,
                     NM_SETTING_WIRELESS_HIDDEN,
                     args.value(u"hidden"_s).toBool(), nullptr);
        g_bytes_unref(value);
        nm_connection_add_setting(job->draft, wifi);
        auto *v4 = nm_setting_ip4_config_new();
        g_object_set(v4, NM_SETTING_IP_CONFIG_METHOD, "auto", nullptr);
        nm_connection_add_setting(job->draft, v4);
      }
      if (!password.isEmpty()) {
        auto *sec = nm_connection_get_setting_wireless_security(job->draft);
        if (!sec) {
          sec =
              NM_SETTING_WIRELESS_SECURITY(nm_setting_wireless_security_new());
          nm_connection_add_setting(job->draft, NM_SETTING(sec));
        }
        const QString key = str(nm_setting_wireless_security_get_key_mgmt(sec));
        const bool enterprise = key.contains(u"eap"_s) || key == u"ieee8021x"_s;
        const bool wep =
            key == u"none"_s ||
            (selected && !nm_access_point_get_rsn_flags(selected) &&
             !nm_access_point_get_wpa_flags(selected) &&
             (nm_access_point_get_flags(selected) &
              NM_802_11_AP_FLAGS_PRIVACY));
        if (enterprise) {
          auto *auth = nm_connection_get_setting_802_1x(job->draft);
          if (!auth) {
            fail(u"Configure an enterprise Wi-Fi profile before connecting"_s);
            return;
          }
          g_object_set(auth, NM_SETTING_802_1X_PASSWORD,
                       password.toUtf8().constData(), nullptr);
        } else if (wep) {
          g_object_set(sec, NM_SETTING_WIRELESS_SECURITY_KEY_MGMT, "none",
                       NM_SETTING_WIRELESS_SECURITY_WEP_KEY0,
                       password.toUtf8().constData(),
                       NM_SETTING_WIRELESS_SECURITY_WEP_KEY_TYPE,
                       NM_WEP_KEY_TYPE_KEY, nullptr);
        } else {
          const bool sae = selected &&
                           (nm_access_point_get_rsn_flags(selected) &
                            NM_802_11_AP_SEC_KEY_MGMT_SAE) &&
                           !(nm_access_point_get_rsn_flags(selected) &
                             NM_802_11_AP_SEC_KEY_MGMT_PSK);
          g_object_set(sec, NM_SETTING_WIRELESS_SECURITY_KEY_MGMT,
                       sae ? "sae" : "wpa-psk",
                       NM_SETTING_WIRELESS_SECURITY_PSK,
                       password.toUtf8().constData(),
                       NM_SETTING_WIRELESS_SECURITY_PSK_FLAGS,
                       NM_SETTING_SECRET_FLAG_NONE, nullptr);
        }
      }
      GError *error = nullptr;
      if (!nm_connection_verify(job->draft, &error)) {
        const auto message = str(error->message);
        g_error_free(error);
        fail(message);
        return;
      }
      if (c) {
        job->remote = NM_REMOTE_CONNECTION(g_object_ref(c));
        job->activate = true;
        update(job);
      } else {
        job->kind = u"add"_s;
        nm_client_add_and_activate_connection_async(
            client, job->draft, d,
            selected ? nm_object_get_path(NM_OBJECT(selected)) : nullptr,
            cancel, finished, job);
      }
      return;
    }
    if (op == u"activate"_s) {
      if (c) {
        job->kind = u"activate"_s;
        nm_client_activate_connection_async(client, NM_CONNECTION(c), d,
                                            nullptr, cancel, finished, job);
        return;
      }
      if (d && NM_IS_DEVICE_ETHERNET(d)) {
        job->kind = u"add"_s;
        nm_client_add_and_activate_connection_async(client, nullptr, d, nullptr,
                                                    cancel, finished, job);
        return;
      }
    }
    if (!c) {
      fail(u"Saved connection not found"_s);
      return;
    }
    if (op == u"forget"_s) {
      job->kind = u"forget"_s;
      nm_remote_connection_delete_async(c, cancel, finished, job);
      return;
    }
    if (op == u"ipv4"_s || op == u"autoconnect"_s) {
      job->draft = nm_simple_connection_new_clone(NM_CONNECTION(c));
      job->remote = NM_REMOTE_CONNECTION(g_object_ref(c));
      if (op == u"autoconnect"_s)
        g_object_set(nm_connection_get_setting_connection(job->draft),
                     NM_SETTING_CONNECTION_AUTOCONNECT,
                     args.value(u"enabled"_s).toBool(), nullptr);
      else {
        const auto cfg = args.value(u"config"_s).toMap();
        const auto method = cfg.value(u"method"_s, u"auto"_s).toString();
        if (method != u"auto"_s && method != u"auto-dns"_s &&
            method != u"manual"_s && method != u"disabled"_s &&
            method != u"link-local"_s) {
          fail(u"Invalid IPv4 method"_s);
          return;
        }
        auto *setting = nm_connection_get_setting_ip4_config(job->draft);
        if (!setting) {
          setting = NM_SETTING_IP_CONFIG(nm_setting_ip4_config_new());
          nm_connection_add_setting(job->draft, NM_SETTING(setting));
        }
        g_object_set(
            setting, NM_SETTING_IP_CONFIG_METHOD,
            method == u"auto-dns"_s ? "auto" : method.toUtf8().constData(),
            NM_SETTING_IP_CONFIG_IGNORE_AUTO_DNS, method == u"auto-dns"_s,
            NM_SETTING_IP_CONFIG_GATEWAY,
            cfg.value(u"gateway"_s).toString().isEmpty()
                ? nullptr
                : cfg.value(u"gateway"_s).toString().toUtf8().constData(),
            nullptr);
        nm_setting_ip_config_clear_addresses(setting);
        nm_setting_ip_config_clear_dns(setting);
        if (method == u"manual"_s) {
          const auto fields = cfg.value(u"address"_s).toString().split(u'/');
          GError *error = nullptr;
          NMIPAddress *address =
              fields.size() == 2
                  ? nm_ip_address_new(AF_INET, fields[0].toUtf8().constData(),
                                      fields[1].toUInt(), &error)
                  : nullptr;
          if (!address) {
            QString message = error ? str(error->message)
                                    : u"Use an IPv4 address with prefix"_s;
            if (error)
              g_error_free(error);
            fail(message);
            return;
          }
          nm_setting_ip_config_add_address(setting, address);
          nm_ip_address_unref(address);
        }
        const auto servers = cfg.value(u"dns"_s).toString().split(
            QRegularExpression(u"[,;\\s]+"_s), Qt::SkipEmptyParts);
        for (const auto &server : servers) {
          QHostAddress addr(server);
          if (addr.protocol() != QAbstractSocket::IPv4Protocol) {
            fail(u"Invalid IPv4 DNS address"_s);
            return;
          }
          nm_setting_ip_config_add_dns(setting, server.toUtf8().constData());
        }
        job->activate = true;
      }
      GError *error = nullptr;
      if (!nm_connection_verify(job->draft, &error)) {
        const auto message = str(error->message);
        g_error_free(error);
        fail(message);
        return;
      }
      update(job);
      return;
    }
    fail(u"Unknown network operation"_s);
  }
  void run() {
    g_main_context_push_thread_default(context);
    client = NM_CLIENT(g_object_new(NM_TYPE_CLIENT, nullptr));
    g_async_initable_init_async(
        G_ASYNC_INITABLE(client), G_PRIORITY_DEFAULT, cancel,
        [](GObject *object, GAsyncResult *result, gpointer data) {
          auto *self = static_cast<Worker *>(data);
          GError *error = nullptr;
          const bool initialized = g_async_initable_init_finish(
              G_ASYNC_INITABLE(object), result, &error);
          --self->pending;
          if (error) {
            self->post(
                {{u"available"_s, false}, {u"error"_s, str(error->message)}});
            g_error_free(error);
          }
          if (initialized && !self->closing)
            self->snapshot();
          self->quitIfDone();
        },
        this);
    g_main_loop_run(loop);
    if (debounce) {
      g_source_destroy(debounce);
      g_source_unref(debounce);
      debounce = nullptr;
    }
    resetWatches();
    if (client) {
      gpointer busy = nm_client_get_context_busy_watcher(client);
      if (busy)
        g_object_add_weak_pointer(G_OBJECT(busy), &busy);
      g_object_unref(client);
      client = nullptr;
      while (busy)
        g_main_context_iteration(context, true);
    }
    // Drain libnm's destruction work before dropping its owning GLib context.
    while (g_main_context_pending(context))
      g_main_context_iteration(context, false);
    g_main_context_pop_thread_default(context);
  }
};
NetworkService::NetworkService(QObject *parent)
    : QObject(parent), m_worker(std::make_shared<Worker>()) {
  m_worker->owner = this;
  m_thread = std::thread([worker = m_worker] { worker->run(); });
}
NetworkService::~NetworkService() {
  auto *w = m_worker.get();
  g_main_context_invoke(
      w->context,
      [](gpointer data) -> gboolean {
        auto *self = static_cast<Worker *>(data);
        self->closing = true;
        g_cancellable_cancel(self->cancel);
        self->quitIfDone();
        return G_SOURCE_REMOVE;
      },
      w);
  if (m_thread.joinable())
    m_thread.join();
}
int NetworkService::request(const QString &op, const QVariantMap &args) {
  const int id = ++m_serial;
  struct Request {
    std::shared_ptr<Worker> worker;
    int id;
    QString op;
    QVariantMap args;
  };
  auto *request = new Request{m_worker, id, op, args};
  g_main_context_invoke_full(
      m_worker->context, G_PRIORITY_DEFAULT,
      [](gpointer data) -> gboolean {
        auto *req = static_cast<Request *>(data);
        req->worker->request(req->id, req->op, req->args);
        return G_SOURCE_REMOVE;
      },
      request, [](gpointer data) { delete static_cast<Request *>(data); });
  return id;
}
QVariantMap NetworkService::interfaceStats(const QString &iface) const {
  static const QRegularExpression valid(u"^[A-Za-z0-9_.:-]{1,15}$"_s);
  if (!valid.match(iface).hasMatch() || iface == u"."_s || iface == u".."_s)
    return {};
  auto read = [&](QString file) -> QVariant {
    QFile f(u"/sys/class/net/"_s + iface + u"/"_s + file);
    if (!f.open(QIODevice::ReadOnly))
      return {};
    bool ok;
    const auto n = f.read(64).trimmed().toULongLong(&ok);
    return ok ? QVariant::fromValue(n) : QVariant();
  };
  return {{u"rx"_s, read(u"statistics/rx_bytes"_s)},
          {u"tx"_s, read(u"statistics/tx_bytes"_s)},
          {u"speedMbps"_s, read(u"speed"_s)},
          {u"physical"_s,
           QFileInfo::exists(u"/sys/class/net/"_s + iface + u"/device"_s)}};
}
} // namespace hyprstack::services
