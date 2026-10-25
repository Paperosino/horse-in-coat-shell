#include "service.hpp"
#include "util/applicationenv.hpp"
#include <QCryptographicHash>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QMutex>
#include <QMutexLocker>
#include <QSaveFile>
#include <QStandardPaths>
#include <QUrl>
#pragma push_macro("signals")
#undef signals
#include <gio/gdesktopappinfo.h>
#pragma pop_macro("signals")
namespace HicsDesktop {
namespace {
const QStringList managers{"org.gnome.Nautilus.desktop",
                           "org.kde.dolphin.desktop",
                           "thunar.desktop",
                           "nemo.desktop",
                           "pcmanfm-qt.desktop",
                           "pcmanfm.desktop",
                           "caja.desktop",
                           "spacefm.desktop",
                           "org.xfce.Thunar.desktop",
                           "org.mate.Caja.desktop"};
const QStringList archivers{"org.gnome.FileRoller.desktop",
                            "org.kde.ark.desktop",
                            "xarchiver.desktop",
                            "engrampa.desktop",
                            "org.xfce.Xarchiver.desktop",
                            "org.mate.Engrampa.desktop"};
const QStringList archiveTypes{"application/zip",
                               "application/x-tar",
                               "application/gzip",
                               "application/x-compressed-tar",
                               "application/x-7z-compressed",
                               "application/vnd.rar",
                               "application/x-bzip-compressed-tar",
                               "application/x-xz-compressed-tar",
                               "application/zstd"};
QString current(const char *mime) {
  auto *app = g_app_info_get_default_for_type(mime, false);
  if (!app)
    return {};
  const auto id = QString::fromUtf8(g_app_info_get_id(app));
  g_object_unref(app);
  return id;
}
} // namespace
void Service::integration(const QSharedPointer<Job> &job) {
  const auto args = job->arguments;
  const auto op = job->operation;
  if (op == "integration.reveal") {
    const auto path = QFileInfo(args["path"].toString()).canonicalFilePath();
    if (path.isEmpty()) {
      finish(job, {}, "Choose an existing file");
      return;
    }
    auto call = QDBusMessage::createMethodCall(
        "org.freedesktop.FileManager1", "/org/freedesktop/FileManager1",
        "org.freedesktop.FileManager1", "ShowItems");
    call.setArguments(
        {QStringList{QUrl::fromLocalFile(path).toString(QUrl::FullyEncoded)},
         QString()});
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(call, 10000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this, watcher, job, path] {
              QDBusPendingReply<> reply = *watcher;
              watcher->deleteLater();
              if (!reply.isError()) {
                finish(job, {{"ok", true}});
                return;
              }
              // FileManager1 is optional: opening the parent works with every
              // default FM.
              application(job, "gio", {"open", QFileInfo(path).absolutePath()});
            });
    return;
  }
  if (op == "integration.open") {
    const auto target = args["target"].toString();
    QString path;
    if (target == "home")
      path = QDir::homePath();
    else if (target == "downloads")
      path = QStandardPaths::writableLocation(QStandardPaths::DownloadLocation);
    else if (target == "trash")
      path = "trash:///";
    else if (target == "archive") {
      path = QFileInfo(args["path"].toString()).canonicalFilePath();
      if (path.isEmpty() || !QFileInfo(path).isFile()) {
        finish(job, {}, "Choose an existing archive");
        return;
      }
      // Always delegate to the selected archiver, even if the chosen file has
      // an executable or document MIME type. Never execute a selected archive.
      const auto id = current("application/zip");
      auto *app = id.isEmpty() ? nullptr : g_desktop_app_info_new(id.toUtf8());
      if (!app) {
        finish(job, {}, "Choose an installed archive application first");
        return;
      }
      const auto desktop =
          QString::fromUtf8(g_desktop_app_info_get_filename(app));
      g_object_unref(app);
      application(job, "gio", {"launch", desktop, QUrl::fromLocalFile(path).toString(QUrl::FullyEncoded)});
      return;
    } else {
      finish(job, {}, "Unknown file manager destination");
      return;
    }
    application(job, "gio", {"open", path});
    return;
  }
  worker(job, [this, op, args] {
    if (op == "integration.status") {
      const auto fm = current("inode/directory"),
                 zip = current("application/zip");
      auto inspect = [](const QStringList &ids, const QString &active) {
        QJsonArray result;
        for (const auto &id : ids) {
          auto *app = g_desktop_app_info_new(id.toUtf8());
          if (!app)
            continue;
          result.append(QJsonObject{
              {"id", id},
              {"name",
               QString::fromUtf8(g_app_info_get_display_name(G_APP_INFO(app)))},
              {"selected", id == active}});
          g_object_unref(app);
        }
        // Keep an unknown but valid installed default visible, too.
        if (!active.isEmpty() && !ids.contains(active)) {
          auto *app = g_desktop_app_info_new(active.toUtf8());
          if (app) {
            result.append(QJsonObject{
                {"id", active},
                {"name", QString::fromUtf8(
                             g_app_info_get_display_name(G_APP_INFO(app)))},
                {"selected", true}});
            g_object_unref(app);
          }
        }
        return result;
      };
      return QJsonObject{
          {"managers", inspect(managers, fm)},
          {"archivers", inspect(archivers, zip)},
          {"manager", fm},
          {"archiver", zip},
          {"canUndo",
           !readJson(directory + "/file-defaults-undo.json").isEmpty()}};
    }
    if (op != "integration.prefer" && op != "integration.undo")
      return QJsonObject{{"error", "Unknown desktop integration operation"}};
    static QMutex defaultsMutex;
    QMutexLocker guard(&defaultsMutex);
    const auto associations = QStandardPaths::writableLocation(
                                  QStandardPaths::GenericConfigLocation) +
                              "/mimeapps.list";
    QFile file(associations);
    if (QFileInfo(associations).isSymLink() || file.size() > 1024 * 1024)
      return QJsonObject{
          {"error",
           "Cannot safely edit a linked or oversized MIME configuration"}};
    const bool existed = file.exists();
    QByteArray before;
    if (existed) {
      if (!file.open(QIODevice::ReadOnly))
        return QJsonObject{{"error", "Cannot read MIME configuration"}};
      before = file.readAll();
      file.close();
    }
    const auto digest = [](const QByteArray &bytes) {
      return QString::fromLatin1(
          QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
    };
    if (op == "integration.undo") {
      const auto undo = readJson(directory + "/file-defaults-undo.json");
      if (undo.isEmpty() || undo["after"].toString() != digest(before))
        return QJsonObject{{"error", "Defaults changed since this operation; "
                                     "refusing to overwrite newer choices"}};
      if (!undo["existed"].toBool()) {
        if (file.exists() && !file.remove())
          return QJsonObject{{"error", "Cannot restore MIME defaults"}};
      } else {
        const auto original =
            QByteArray::fromBase64(undo["before"].toString().toLatin1());
        QSaveFile saved(associations);
        if (!saved.open(QIODevice::WriteOnly) ||
            saved.write(original) != original.size() || !saved.commit())
          return QJsonObject{{"error", "Cannot restore MIME defaults"}};
      }
      writeJson(directory + "/file-defaults-undo.json", {});
      return QJsonObject{{"ok", true}};
    }
    const auto kind = args["kind"].toString(), id = args["id"].toString();
    const auto allowed = kind == "manager"    ? managers
                         : kind == "archiver" ? archivers
                                              : QStringList{};
    const auto existing =
        current(kind == "manager" ? "inode/directory" : "application/zip");
    if (allowed.isEmpty() || (!allowed.contains(id) && id != existing))
      return QJsonObject{
          {"error", "Choose an installed file manager or archiver"}};
    auto *app = g_desktop_app_info_new(id.toUtf8());
    if (!app)
      return QJsonObject{{"error", "This application is no longer installed"}};
    // Save first, including an originally absent file. Update the expected
    // digest after GIO writes, so Undo cannot replace unrelated later edits.
    QJsonObject undo{{"before", QString::fromLatin1(before.toBase64())},
                     {"existed", existed},
                     {"after", digest(before)}};
    writeJson(directory + "/file-defaults-undo.json", undo);
    QString failure;
    for (const auto &mime :
         kind == "manager"
             ? QStringList{"inode/directory", "x-scheme-handler/trash"}
             : archiveTypes) {
      GError *error = nullptr;
      if (!g_app_info_set_as_default_for_type(G_APP_INFO(app), mime.toUtf8(),
                                              &error)) {
        failure = error ? QString::fromUtf8(error->message)
                        : QString("Cannot update application defaults");
        if (error)
          g_error_free(error);
        break;
      }
    }
    g_object_unref(app);
    if (file.open(QIODevice::ReadOnly)) {
      undo["after"] = digest(file.readAll());
      file.close();
    }
    writeJson(directory + "/file-defaults-undo.json", undo);
    if (!failure.isEmpty())
      return QJsonObject{{"error", failure}};
    return QJsonObject{{"ok", true}};
  });
}
} // namespace HicsDesktop
