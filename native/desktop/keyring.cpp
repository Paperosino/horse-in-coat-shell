#include "service.hpp"
#include <QDBusObjectPath>
#include <QFile>
#include <QJsonArray>
#include <QRegularExpression>
#pragma push_macro("signals")
#undef signals
#include <libsecret/secret.h>
#pragma pop_macro("signals")
namespace HicsDesktop {
void Service::keyring(const QSharedPointer<Job> &job) {
  if (job->operation == "keyring.authorize") {
    root(job, "secrets", "authorize", {});
    return;
  }
  if (job->operation == "keyring.manager") {
    process(job, "seahorse", {}, false);
    return;
  }
  if (!QStringList{"keyring.status", "keyring.lock", "keyring.unlock"}.contains(
          job->operation)) {
    finish(job, {}, "Unknown keyring operation");
    return;
  }
  const auto operation = job->operation,
             path = job->arguments["path"].toString();
  worker(job, [operation, path] {
    GError *error = nullptr;
    auto *service = secret_service_get_sync(SECRET_SERVICE_LOAD_COLLECTIONS,
                                            nullptr, &error);
    if (!service) {
      const auto message = QString::fromUtf8(
          error ? error->message : "Secret Service is unavailable");
      if (error)
        g_error_free(error);
      return QJsonObject{{"error", message}};
    }
    auto *collections = secret_service_get_collections(service);
    QJsonArray rows;
    bool found = false;
    for (auto *it = collections; it; it = it->next) {
      auto *collection = SECRET_COLLECTION(it->data);
      const QString object = QString::fromUtf8(
          g_dbus_proxy_get_object_path(G_DBUS_PROXY(collection)));
      if (operation != "keyring.status" && object == path) {
        found = true;
        GList one{collection, nullptr, nullptr};
        GList *changed = nullptr;
        if (operation == "keyring.lock")
          secret_service_lock_sync(service, &one, nullptr, &changed, &error);
        else
          secret_service_unlock_sync(service, &one, nullptr, &changed, &error);
        g_list_free_full(changed, g_object_unref);
      }
      auto *label = secret_collection_get_label(collection);
      rows.append(QJsonObject{
          {"path", object},
          {"label", QString::fromUtf8(label ? label : "")},
          {"locked", bool(secret_collection_get_locked(collection))}});
      g_free(label);
    }
    g_list_free_full(collections, g_object_unref);
    g_object_unref(service);
    if (error) {
      QString message = QString::fromUtf8(error->message);
      g_error_free(error);
      return QJsonObject{{"error", message}};
    }
    if (operation != "keyring.status" && !found)
      return QJsonObject{{"error", "Keyring collection no longer exists"}};
    QJsonArray pam;
    for (const auto &name :
         {QString("sddm"), QString("sddm-autologin"), QString("gdm-password"),
          QString("greetd"), QString("login")}) {
      QFile file("/etc/pam.d/" + name);
      if (!file.open(QIODevice::ReadOnly))
        continue;
      const auto text = QString::fromUtf8(file.read(65536));
      bool auth = false, session = false, password = false;
      for (const auto &line : text.split('\n')) {
        const auto value = line.trimmed();
        if (value.startsWith('#') || !value.contains("pam_gnome_keyring.so"))
          continue;
        auth |= value.contains("auth");
        session |= value.contains("session") && value.contains("auto_start");
        password |= value.contains("password") && value.contains("use_authtok");
      }
      pam.append(QJsonObject{
          {"loginManager", name},
          {"unlockOnLogin", auth && session && !name.contains("autologin")},
          {"passwordless", name.contains("autologin")},
          {"passwordSync", password}});
    }
    return QJsonObject{{"collections", rows}, {"pam", pam}};
  });
}
} // namespace HicsDesktop
