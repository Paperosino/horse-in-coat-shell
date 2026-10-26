#include "service.hpp"
#include <QDir>
#include <QFileInfo>
#include <QJsonArray>
#include <QSet>
#include <QStandardPaths>
#pragma push_macro("signals")
#undef signals
#include <gio/gio.h>
#pragma pop_macro("signals")
namespace HicsDesktop {
void Service::desktopFiles(const QSharedPointer<Job> &job) {
  const auto args = job->arguments;
  worker(
      job,
      [args, cancel = job->cancel] {
        const auto desktop =
            QStandardPaths::writableLocation(QStandardPaths::DesktopLocation);
        if (desktop.isEmpty() || QDir::cleanPath(desktop) == QDir::homePath() ||
            (!QFileInfo(desktop).canonicalFilePath().isEmpty() &&
             QFileInfo(desktop).canonicalFilePath() ==
                 QFileInfo(QDir::homePath()).canonicalFilePath()))
          return QJsonObject{{"error", "The XDG desktop folder is disabled"}};
        if (!QDir().mkpath(desktop))
          return QJsonObject{{"error", "Cannot create desktop folder"}};
        const auto action = args["action"].toString();
        const auto root = QDir(desktop).canonicalPath();
        const auto name = args["name"].toString();
        auto validName = [](const QString &n) {
          return !n.isEmpty() && n != "." && n != ".." && !n.contains('/') &&
                 !n.contains(QChar(0)) && n.toUtf8().size() <= 255;
        };
        auto direct = [&](const QString &path) {
          return QFileInfo(path).isAbsolute() &&
                 QFileInfo(path).absoluteDir().canonicalPath() == root &&
                 validName(QFileInfo(path).fileName());
        };
        auto gioError = [](GError *error) {
          const auto text = error ? QString::fromUtf8(error->message)
                                  : QString("File operation failed");
          if (error)
            g_error_free(error);
          return QJsonObject{{"error", text}};
        };
        if (action == "ensure")
          return QJsonObject{{"ok", true}};
        if (action == "mkdir") {
          if (!validName(name))
            return QJsonObject{{"error", "Choose a valid folder name"}};
          GError *error = nullptr;
          auto *file =
              g_file_new_for_path(QDir(desktop).filePath(name).toUtf8());
          const bool ok = g_file_make_directory(file, nullptr, &error);
          g_object_unref(file);
          if (!ok)
            return gioError(error);
        } else if (action == "rename") {
          const auto source = args["path"].toString();
          if (!direct(source) || !validName(name))
            return QJsonObject{
                {"error", "Choose a desktop item and a valid name"}};
          GError *error = nullptr;
          auto *file = g_file_new_for_path(source.toUtf8());
          auto *renamed =
              g_file_set_display_name(file, name.toUtf8(), nullptr, &error);
          g_object_unref(file);
          if (!renamed)
            return gioError(error);
          g_object_unref(renamed);
        } else if (action == "trash" || action == "move") {
          const auto sources = args["sources"].toArray();
          if (sources.isEmpty() || sources.size() > 128)
            return QJsonObject{{"error", "Choose between one and 128 items"}};
          // Validate the entire selection before changing anything.
          QSet<QString> destinations;
          for (const auto &source : sources) {
            const auto path = source.toString();
            const QFileInfo info(path);
            if (!info.isAbsolute() || (action == "trash" && !direct(path)) ||
                (!info.exists() && !info.isSymLink()))
              return QJsonObject{{"error", "Choose existing local files"}};
            if (action == "move" &&
                (info.absoluteFilePath() ==
                     QDir(desktop).filePath(info.fileName()) ||
                 (info.isDir() &&
                  (root == info.canonicalFilePath() ||
                   root.startsWith(info.canonicalFilePath() + "/")))))
              return QJsonObject{
                  {"error", "The destination is the source or is inside it"}};
          }
          if (action == "move")
            for (const auto &source : sources) {
              const auto destination = QDir(desktop).filePath(
                  QFileInfo(source.toString()).fileName());
              if (QFileInfo::exists(destination) ||
                  QFileInfo(destination).isSymLink() ||
                  destinations.contains(destination))
                return QJsonObject{
                    {"error", "A destination already exists; existing files "
                              "are never overwritten"}};
              destinations.insert(destination);
            }
          int done = 0;
          for (const auto &source : sources) {
            if (cancel->load())
              return QJsonObject{{"cancelled", true}, {"completed", done}};
            const auto path = source.toString();
            auto *file = g_file_new_for_path(path.toUtf8());
            GError *error = nullptr;
            bool ok;
            if (action == "trash")
              ok = g_file_trash(file, nullptr, &error);
            else {
              auto *target = g_file_new_for_path(
                  QDir(desktop).filePath(QFileInfo(path).fileName()).toUtf8());
              // No overwrite, no cross-filesystem recursive fallback: use the
              // FM for complex moves, rather than risk deleting partially
              // copied data.
              ok = g_file_move(file, target,
                               GFileCopyFlags(G_FILE_COPY_NOFOLLOW_SYMLINKS |
                                              G_FILE_COPY_NO_FALLBACK_FOR_MOVE),
                               nullptr, nullptr, nullptr, &error);
              g_object_unref(target);
            }
            g_object_unref(file);
            if (!ok) {
              auto result = gioError(error);
              result["completed"] = done;
              return result;
            }
            ++done;
          }
          return QJsonObject{{"ok", true}, {"completed", done}};
        } else
          return QJsonObject{{"error", "Unknown desktop file action"}};
        return QJsonObject{{"ok", true}};
      },
      true);
}
} // namespace HicsDesktop
