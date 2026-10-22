#include "vpnsecretagent.hpp"
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMetaType>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QFileInfo>
#include <QFutureWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcessEnvironment>
#include <QTimer>
#include <QtConcurrent>
#pragma push_macro("signals")
#undef signals
#include <NetworkManager.h>
#include <libsecret/secret.h>
#pragma pop_macro("signals")

namespace hyprstack::services {
namespace {
const char *nm = "org.freedesktop.NetworkManager";
const SecretSchema schema = {"org.hics.NetworkManagerVPN",
                             SECRET_SCHEMA_NONE,
                             {{"uuid", SECRET_SCHEMA_ATTRIBUTE_STRING},
                              {"setting", SECRET_SCHEMA_ATTRIBUTE_STRING},
                              {nullptr, SECRET_SCHEMA_ATTRIBUTE_STRING}},
                             0,
                             nullptr,
                             nullptr,
                             nullptr,
                             nullptr,
                             nullptr,
                             nullptr,
                             nullptr};
QVariantMap secrets(const QVariant &v) {
  auto strings = qdbus_cast<QMap<QString, QString>>(v);
  QVariantMap result;
  for (auto i = strings.begin(); i != strings.end(); ++i)
    result[i.key()] = i.value();
  return result;
}
QString keyring(const QString &uuid, const QString &setting,
                const QVariantMap &values, bool store, bool remove = false,
                bool allowUnlock = true) {
  GError *error = nullptr;
  auto u = uuid.toUtf8(), s = setting.toUtf8();
  QString result;
  if (remove)
    secret_password_clear_sync(&schema, nullptr, &error, "uuid", u.constData(),
                               "setting", s.constData(), nullptr);
  else if (store) {
    auto data =
        QJsonDocument::fromVariant(values).toJson(QJsonDocument::Compact);
    secret_password_store_sync(&schema, SECRET_COLLECTION_DEFAULT, "hics VPN",
                               data.constData(), nullptr, &error, "uuid",
                               u.constData(), "setting", s.constData(),
                               nullptr);
  } else {
    if (allowUnlock) {
      char *password = secret_password_lookup_sync(
          &schema, nullptr, &error, "uuid", u.constData(), "setting",
          s.constData(), nullptr);
      if (password) {
        result = QString::fromUtf8(password);
        secret_password_free(password);
      }
    } else {
      // An automatic activation may read an already unlocked keyring, but must
      // never open an unlock prompt when NetworkManager forbids interaction.
      auto *service =
          secret_service_get_sync(SECRET_SERVICE_OPEN_SESSION, nullptr, &error);
      if (service) {
        auto *attributes = secret_attributes_build(
            &schema, "uuid", u.constData(), "setting", s.constData(), nullptr);
        GList *items = secret_service_search_sync(service, &schema, attributes,
                                                  SECRET_SEARCH_LOAD_SECRETS,
                                                  nullptr, &error);
        for (auto *item = items; item && result.isEmpty(); item = item->next) {
          auto *value = secret_item_get_secret(SECRET_ITEM(item->data));
          if (value) {
            result = QString::fromUtf8(secret_value_get_text(value));
            secret_value_unref(value);
          }
        }
        g_list_free_full(items, g_object_unref);
        g_hash_table_unref(attributes);
        g_object_unref(service);
      }
    }
  }
  if (error) {
    result = "ERROR:" + QString::fromUtf8(error->message);
    g_error_free(error);
  }
  return result;
}
} // namespace
VpnSecretAgent::VpnSecretAgent(QObject *parent) : QObject(parent) {
  qDBusRegisterMetaType<VpnSettings>();
  qDBusRegisterMetaType<QMap<QString, QString>>();
  QDBusConnection::systemBus().registerObject(
      "/org/freedesktop/NetworkManager/SecretAgent", this,
      QDBusConnection::ExportAllSlots);
  auto *watcher =
      new QDBusServiceWatcher(nm, QDBusConnection::systemBus(),
                              QDBusServiceWatcher::WatchForOwnerChange, this);
  connect(watcher, &QDBusServiceWatcher::serviceOwnerChanged, this, [this] {
    cancel();
    registerAgent();
  });
  registerAgent();
}
bool VpnSecretAgent::authorized() {
  if (!calledFromDBus() || message().service() != m_owner ||
      m_owner.isEmpty()) {
    if (calledFromDBus())
      sendErrorReply(QDBusError::AccessDenied,
                     "Only NetworkManager may request credentials");
    return false;
  }
  return true;
}
void VpnSecretAgent::registerAgent() {
  auto owner = QDBusConnection::systemBus().interface()->serviceOwner(nm);
  m_owner = owner.isValid() ? owner.value() : QString();
  if (m_owner.isEmpty())
    return;
  auto request = QDBusMessage::createMethodCall(
      nm, "/org/freedesktop/NetworkManager/AgentManager",
      "org.freedesktop.NetworkManager.AgentManager",
      "RegisterWithCapabilities");
  request.setArguments({"org.hics.Shell.Vpn", uint(1)});
  auto *watcher = new QDBusPendingCallWatcher(
      QDBusConnection::systemBus().asyncCall(request), this);
  connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, watcher] {
    QDBusPendingReply<> result = *watcher;
    if (result.isError() &&
        !result.error().name().endsWith("AlreadyRegistered"))
      m_error = result.error().message();
    else
      m_error.clear();
    emit changed();
    watcher->deleteLater();
  });
}
VpnSettings VpnSecretAgent::GetSecrets(const VpnSettings &connection,
                                       const QDBusObjectPath &path,
                                       const QString &setting,
                                       const QStringList &hints, uint flags) {
  if (!authorized())
    return {};
  if (setting != "vpn" && setting != "wireguard") {
    sendErrorReply("org.freedesktop.NetworkManager.SecretAgent.NoSecrets",
                   "This agent handles VPN credentials");
    return {};
  }
  auto uuid = connection.value("connection").value("uuid").toString();
  if (uuid.isEmpty()) {
    sendErrorReply(QDBusError::InvalidArgs, "Connection UUID is missing");
    return {};
  }
  auto cache = m_session.value(uuid + "/" + setting);
  if (!(flags & 2) && !cache.isEmpty()) {
    QMap<QString, QString> strings;
    for (auto i = cache.begin(); i != cache.end(); ++i)
      strings[i.key()] = i.value().toString();
    return {
        {setting, setting == "vpn"
                      ? QVariantMap{{"secrets", QVariant::fromValue(strings)}}
                      : cache}};
  }
  if (m_waiting) {
    sendErrorReply("org.freedesktop.NetworkManager.SecretAgent.Failed",
                   "Another VPN authentication request is pending");
    return {};
  }
  m_helperValues.clear();
  setDelayedReply(true);
  m_pending = message();
  m_waiting = true;
  m_setting = setting;
  m_uuid = uuid;
  m_path = path.path();
  const auto serial = ++m_request;
  QVariantList fields;
  QString prompt;
  QStringList keys;
  for (const auto &hint : hints) {
    if (hint.startsWith("x-vpn-message:"))
      prompt = hint.mid(14);
    else if (!hint.contains(':') && !hint.isEmpty())
      keys << hint;
  }
  if (keys.isEmpty()) {
    if (setting == "wireguard")
      keys << "private-key";
    else {
      auto data = secrets(connection.value("vpn").value("data"));
      auto protocol = connection.value("vpn").value("service-type").toString();
      if (protocol.endsWith(".l2tp")) {
        keys << (data.value("user-auth-type") == "tls" ? "user-certpass"
                                                       : "password");
        if (data.value("ipsec-enabled") == "yes")
          keys << (data.value("machine-auth-type") == "tls" ? "machine-certpass"
                                                            : "ipsec-psk");
      } else if (protocol.endsWith(".vpnc"))
        keys << "Xauth password" << "IPSec secret";
      else if (protocol.endsWith(".libreswan"))
        keys << "xauthpassword" << "pskvalue";
      else if (protocol.endsWith(".openvpn") &&
               data.value("connection-type") == "tls")
        keys << "cert-pass";
      else if (protocol.endsWith(".openconnect"))
        keys << "cookie";
      else
        keys << "password";
    }
  }
  keys.removeDuplicates();
  for (const auto &key : keys)
    fields << QVariantMap{{"key", key}, {"label", key}};
  QVariantMap challenge{{"name", connection.value("connection").value("id")},
                        {"prompt", prompt},
                        {"fields", fields}};
  if ((flags & 2) && (flags & 1)) {
    if (setting == "vpn" && startPluginAuthentication(connection, hints, flags))
      return {};
    m_challenge = challenge;
    m_error.clear();
    emit changed();
    return {};
  }
  auto *watcher = new QFutureWatcher<QString>(this);
  connect(
      watcher, &QFutureWatcher<QString>::finished, this,
      [this, watcher, serial, challenge, flags, connection, hints] {
        auto result = watcher->result();
        watcher->deleteLater();
        if (serial != m_request || !m_waiting)
          return;
        if (!(flags & 2) && !result.startsWith("ERROR:") && !result.isEmpty()) {
          auto values =
              QJsonDocument::fromJson(result.toUtf8()).object().toVariantMap();
          if (!values.isEmpty()) {
            reply(values);
            return;
          }
        }
        if (!(flags & 1)) {
          QDBusConnection::systemBus().send(m_pending.createErrorReply(
              "org.freedesktop.NetworkManager.SecretAgent.NoSecrets",
              "No unlocked VPN credentials are available"));
          m_waiting = false;
          ++m_request;
          emit changed();
          return;
        }
        if (m_setting == "vpn" &&
            startPluginAuthentication(connection, hints, flags))
          return;
        m_challenge = challenge;
        m_error = result.startsWith("ERROR:")
                      ? tr("The keyring is unavailable. Credentials can still "
                           "be used for this session.")
                      : QString();
        emit changed();
      });
  watcher->setFuture(QtConcurrent::run([uuid, setting, flags] {
    return keyring(uuid, setting, {}, false, false, flags & 1);
  }));
  return {};
}
// NetworkManager's standard auth-dialog protocol. Plugins which support
// external UI provide field metadata; hics renders those fields in QML. A
// plugin with its own web/certificate flow retains its official authentication
// helper.
bool VpnSecretAgent::startPluginAuthentication(const VpnSettings &connection,
                                               const QStringList &hints,
                                               uint flags) {
  auto service = connection.value("vpn").value("service-type").toString();
  GSList *plugins = nm_vpn_plugin_info_list_load();
  auto *plugin = nm_vpn_plugin_info_list_find_by_service(
      plugins, service.toUtf8().constData());
  QString executable =
      plugin ? QString::fromUtf8(nm_vpn_plugin_info_get_auth_dialog(plugin))
             : QString();
  bool external =
      plugin && g_strcmp0(nm_vpn_plugin_info_lookup_property(
                              plugin, "GNOME", "supports-external-ui-mode"),
                          "true") == 0;
  bool supportsHints = plugin && nm_vpn_plugin_info_supports_hints(plugin);
  g_slist_free_full(plugins, g_object_unref);
  // Helpers come only from installed, root-owned NetworkManager plugin files.
  if (executable.isEmpty() || !QFileInfo(executable).isExecutable())
    return false;
  auto *process = new QProcess(this);
  m_helper = process;
  const auto serial = m_request;
  auto environment = QProcessEnvironment::systemEnvironment();
  environment.remove("G_MESSAGES_DEBUG");
  process->setProcessEnvironment(environment);
  QStringList arguments{
      "-u", m_uuid,
      "-n", connection.value("connection").value("id").toString(),
      "-s", service,
      "-i"};
  if (flags & 2)
    arguments << "-r";
  if (supportsHints)
    for (const auto &hint : hints)
      arguments << "-t" << hint;
  if (external)
    arguments << "--external-ui-mode";
  QByteArray input;
  auto append = [&](const QByteArray &tag, const QString &value) {
    auto line = value;
    line.replace('\n', ' ');
    line.replace('\r', ' ');
    input += tag + '=' + line.toUtf8() + '\n';
  };
  for (const auto &group : QStringList{"data", "secrets"}) {
    auto values = secrets(connection.value("vpn").value(group));
    for (auto i = values.begin(); i != values.end(); ++i) {
      append(group == "data" ? "DATA_KEY" : "SECRET_KEY", i.key());
      append(group == "data" ? "DATA_VAL" : "SECRET_VAL", i.value().toString());
    }
  }
  input += "DONE\n\nQUIT\n\n";
  connect(process, &QProcess::started, this, [process, input] {
    process->write(input);
    process->closeWriteChannel();
  });
  connect(process, &QProcess::errorOccurred, this,
          [this, process, serial](QProcess::ProcessError error) {
            if (serial != m_request || !m_waiting)
              return;
            if (error == QProcess::FailedToStart) {
              m_error = tr("The VPN authentication helper could not start");
              cancel();
              process->deleteLater();
            }
          });
  connect(
      process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
      [this, process, serial, external,
       connection](int code, QProcess::ExitStatus status) {
        auto output = process->readAllStandardOutput();
        process->deleteLater();
        if (m_helper == process)
          m_helper.clear();
        if (serial != m_request || !m_waiting)
          return;
        if (code != 0 || status != QProcess::NormalExit) {
          cancel();
          return;
        }
        if (!external) {
          auto lines = output.split('\n');
          QVariantMap values;
          for (qsizetype i = 0; i + 1 < lines.size() && !lines[i].isEmpty();
               i += 2)
            values[QString::fromUtf8(lines[i])] =
                QString::fromUtf8(lines[i + 1]);
          if (values.isEmpty()) {
            m_error = tr("The VPN plugin returned no credentials");
            cancel();
            return;
          }
          reply(values);
          return;
        }
        auto *keyfile = g_key_file_new();
        if (!g_key_file_load_from_data(keyfile, output.constData(),
                                       gsize(output.size()), G_KEY_FILE_NONE,
                                       nullptr)) {
          g_key_file_unref(keyfile);
          m_error =
              tr("The VPN plugin returned an invalid authentication request");
          cancel();
          return;
        }
        auto value = [&](const char *group, const char *key) {
          char *v = g_key_file_get_string(keyfile, group, key, nullptr);
          auto result = QString::fromUtf8(v);
          g_free(v);
          return result;
        };
        if (value("VPN Plugin UI", "Version") != "2") {
          g_key_file_unref(keyfile);
          cancel();
          return;
        }
        QVariantList fields;
        gsize count = 0;
        char **groups = g_key_file_get_groups(keyfile, &count);
        for (gsize i = 0; i < count; ++i) {
          if (g_str_equal(groups[i], "VPN Plugin UI"))
            continue;
          auto key = QString::fromUtf8(groups[i]);
          bool isSecret =
              g_key_file_get_boolean(keyfile, groups[i], "IsSecret", nullptr);
          if (g_key_file_get_boolean(keyfile, groups[i], "ShouldAsk", nullptr))
            fields << QVariantMap{{"key", key},
                                  {"label", value(groups[i], "Label")},
                                  {"secret", isSecret}};
          else if (isSecret && !value(groups[i], "Value").isEmpty())
            m_helperValues[key] = value(groups[i], "Value");
        }
        g_strfreev(groups);
        auto prompt = value("VPN Plugin UI", "Description");
        g_key_file_unref(keyfile);
        if (fields.isEmpty()) {
          reply(m_helperValues);
          return;
        }
        m_challenge = {{"name", connection.value("connection").value("id")},
                       {"prompt", prompt},
                       {"fields", fields}};
        m_error.clear();
        emit changed();
      });
  QTimer::singleShot(300000, process, [this, process, serial] {
    if (process->state() != QProcess::NotRunning && serial == m_request) {
      m_error = tr("VPN authentication timed out");
      cancel();
    }
  });
  process->start(executable, arguments);
  return true;
}
void VpnSecretAgent::reply(const QVariantMap &values) {
  if (!m_waiting)
    return;
  VpnSettings settings;
  if (m_setting == "vpn") {
    QMap<QString, QString> strings;
    for (auto i = values.begin(); i != values.end(); ++i)
      strings[i.key()] = i.value().toString();
    settings[m_setting] = {{"secrets", QVariant::fromValue(strings)}};
  } else
    settings[m_setting] = values;
  QDBusConnection::systemBus().send(
      m_pending.createReply({QVariant::fromValue(settings)}));
  m_session[m_uuid + "/" + m_setting] = values;
  m_waiting = false;
  m_challenge.clear();
  emit changed();
}
void VpnSecretAgent::submit(const QVariantMap &input, bool remember) {
  if (!m_waiting)
    return;
  QVariantMap values = m_helperValues;
  for (auto i = input.begin(); i != input.end(); ++i)
    values[i.key()] = i.value();
  if (remember) {
    auto uuid = m_uuid, setting = m_setting;
    auto *watcher = new QFutureWatcher<QString>(this);
    connect(watcher, &QFutureWatcher<QString>::finished, this, [this, watcher] {
      auto result = watcher->result();
      watcher->deleteLater();
      if (result.startsWith("ERROR:")) {
        m_error = tr("Credentials were not saved in the keyring");
        emit changed();
      }
    });
    watcher->setFuture(QtConcurrent::run([uuid, setting, values] {
      return keyring(uuid, setting, values, true);
    }));
  }
  reply(values);
}
void VpnSecretAgent::cancel() {
  if (m_waiting)
    QDBusConnection::systemBus().send(m_pending.createErrorReply(
        "org.freedesktop.NetworkManager.SecretAgent.UserCanceled",
        "Authentication canceled"));
  ++m_request;
  m_waiting = false;
  m_challenge.clear();
  m_helperValues.clear();
  if (m_helper) {
    m_helper->kill();
    m_helper.clear();
  }
  emit changed();
}
void VpnSecretAgent::CancelGetSecrets(const QDBusObjectPath &path,
                                      const QString &setting) {
  if (authorized() && path.path() == m_path && setting == m_setting)
    cancel();
}
void VpnSecretAgent::SaveSecrets(const VpnSettings &connection,
                                 const QDBusObjectPath &) {
  if (!authorized())
    return;
  auto uuid = connection.value("connection").value("uuid").toString();
  auto values = secrets(connection.value("vpn").value("secrets"));
  if (!uuid.isEmpty() && !values.isEmpty())
    m_session[uuid + "/vpn"] = values;
  // Agent-owned credentials are saved only with explicit Remember consent in
  // the shell prompt. Profile-editor credentials are owned by NetworkManager.
}
void VpnSecretAgent::DeleteSecrets(const VpnSettings &connection,
                                   const QDBusObjectPath &) {
  if (!authorized())
    return;
  auto uuid = connection.value("connection").value("uuid").toString();
  m_session.remove(uuid + "/vpn");
  m_session.remove(uuid + "/wireguard");
  if (!uuid.isEmpty())
    (void)QtConcurrent::run([uuid] {
      keyring(uuid, "vpn", {}, false, true);
      keyring(uuid, "wireguard", {}, false, true);
    });
}
} // namespace hyprstack::services
