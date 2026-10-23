#include "applicationcatalogue.hpp"
#include "util/applicationenv.hpp"
#include <QDirIterator>
#include <QFileInfo>
#include <QDateTime>
#include <QFile>
#include <QIcon>
#include <QCryptographicHash>
#include <QProcess>
#include <QSet>
#include <QStandardPaths>
#pragma push_macro("signals")
#undef signals
#include <gio/gdesktopappinfo.h>
#pragma pop_macro("signals")

namespace hyprstack::services {
namespace {
QString take(gchar *s) {
  const auto result = QString::fromUtf8(s);
  g_free(s);
  return result;
}
QStringList strings(const gchar *const *values) {
  QStringList result;
  if (values)
    for (; *values; ++values)
      result.append(QString::fromUtf8(*values));
  return result;
}
QStringList roots() {
  auto result =
      QStandardPaths::standardLocations(QStandardPaths::GenericDataLocation);
  for (auto &path : result)
    path += "/applications";
  return result;
}
} // namespace
DesktopApplicationAction::DesktopApplicationAction(QString path, QString id,
                                                   QString name,
                                                   QObject *parent)
    : QObject(parent), m_path(std::move(path)), m_id(std::move(id)),
      m_name(std::move(name)) {}
void DesktopApplicationAction::execute() {
  auto *app = g_desktop_app_info_new_from_filename(m_path.toUtf8().constData());
  if (!app)
    return;
  auto *context = g_app_launch_context_new();
  const auto environment = hics::util::applicationEnvironment();
  for (const auto *key : {"LD_LIBRARY_PATH", "LD_PRELOAD", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML_IMPORT_PATH", "QML2_IMPORT_PATH"}) {
    if (environment.contains(QString::fromLatin1(key)))
      g_app_launch_context_setenv(context, key, environment.value(QString::fromLatin1(key)).toUtf8().constData());
    else g_app_launch_context_unsetenv(context, key);
  }
  g_desktop_app_info_launch_action(app, m_id.toUtf8().constData(), context);
  g_object_unref(context);
  g_object_unref(app);
}
void DesktopApplication::execute() {
  // GIO handles DBusActivatable, quoting, field codes and the current desktop
  // file. This is deliberately the same path as `gio launch FILE`.
  auto *process = new QProcess(this);
  process->setUnixProcessParameters(QProcess::UnixProcessFlag::CreateNewSession);
  process->setProcessEnvironment(hics::util::applicationEnvironment());
  process->setProgram("gio");
  process->setArguments({"launch", m_path});
  // gio exits before the application finishes starting. Pipes owned by this
  // QProcess disappear on deleteLater(), giving the application SIGPIPE on
  // its next log write. A regular file remains valid in the spawned process.
  const auto logDirectory = QStandardPaths::writableLocation(
      QStandardPaths::GenericStateLocation) + "/hics/applications";
  QDir().mkpath(logDirectory);
  QFile::setPermissions(logDirectory, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner);
  const auto logPath = logDirectory + "/" + id() + ".log";
  if (QFileInfo(logPath).size() > 1024 * 1024) {
    QFile::remove(logPath + ".old");
    QFile::rename(logPath, logPath + ".old");
  }
  QFile log(logPath);
  if (!log.open(QIODevice::WriteOnly | QIODevice::Append)) {
    emit launchFailed(tr("Cannot open application launch log: %1").arg(log.errorString()));
    process->deleteLater();
    return;
  }
  log.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
  const auto logOffset = log.size();
  log.close();
  process->setProcessChannelMode(QProcess::MergedChannels);
  process->setStandardOutputFile(logPath, QIODevice::Append);
  connect(process, &QProcess::errorOccurred, this, [this, process] {
    emit launchFailed(process->errorString());
    process->deleteLater();
  });
  connect(process, &QProcess::finished, this, [this, process, logPath, logOffset](int code) {
    if (code) {
      QFile output(logPath);
      QString detail;
      if (output.open(QIODevice::ReadOnly)) {
        output.seek(logOffset);
        detail = QString::fromUtf8(output.read(16384)).trimmed();
      }
      emit launchFailed(detail.isEmpty() ? tr("Application launcher exited with code %1").arg(code) : detail);
    }
    process->deleteLater();
  });
  process->start();
}
QString DesktopApplication::animationIcon() {
  const auto theme = QIcon::themeName();
  if (!m_animationIcon.isEmpty() && theme == m_iconTheme) return m_animationIcon;
  m_iconTheme = theme;
  const auto image = QFileInfo(icon()).isAbsolute() ? QIcon(icon()) : QIcon::fromTheme(icon());
  if (image.isNull()) return {};
  const auto directory = QStandardPaths::writableLocation(QStandardPaths::GenericCacheLocation) + "/hics/task-icons";
  if (!QDir().mkpath(directory)) return {};
  const auto key = QCryptographicHash::hash((icon() + "\n" + theme).toUtf8(), QCryptographicHash::Sha256).toHex();
  const auto path = directory + "/" + QString::fromLatin1(key) + ".png";
  if (!image.pixmap(96,96).save(path)) return {};
  m_animationIcon = path;
  return path;
}
bool DesktopApplication::update(const QVariantMap &data, const QString &path, bool fileChanged) {
  if (m_data == data && m_path == path && !fileChanged)
    return false;
  m_data = data;
  m_path = path;
  m_animationIcon.clear();
  for (auto *action : m_actions)
    action->deleteLater();
  m_actions.clear();
  if (auto *app =
          g_desktop_app_info_new_from_filename(path.toUtf8().constData())) {
    const auto actions = g_desktop_app_info_list_actions(app);
    if (actions)
      for (auto action = actions; *action; ++action) {
        const auto title =
            take(g_desktop_app_info_get_action_name(app, *action));
        m_actions.append(new DesktopApplicationAction(
            path, QString::fromUtf8(*action), title, this));
      }
    g_object_unref(app);
  }
  emit changed();
  return true;
}
ApplicationCatalogue::ApplicationCatalogue(QObject *parent) : QObject(parent) {
  m_debounce.setSingleShot(true);
  m_debounce.setInterval(250);
  connect(&m_watcher, &QFileSystemWatcher::directoryChanged, this,
          [this] { m_debounce.start(); });
  connect(&m_watcher, &QFileSystemWatcher::fileChanged, this,
          [this](const QString &path) { m_dirtyFiles.insert(path); m_debounce.start(); });
  connect(&m_debounce, &QTimer::timeout, this, [this] { scan(false); });
  // Reconcile new XDG roots, nested directories and atomically replaced files.
  m_reconcile.setInterval(15000);
  connect(&m_reconcile, &QTimer::timeout, this, [this] { scan(false); });
  m_reconcile.start();
  refresh();
}
QObject *ApplicationCatalogue::byId(QString id) const {
  if (id.endsWith(".desktop"))
    id.chop(8);
  return m_entries.value(id, nullptr);
}
QObject *ApplicationCatalogue::heuristicLookup(QString name) const {
  if (auto *entry = byId(name))
    return entry;
  name = name.toLower();
  for (auto *entry : m_entries) {
    if (entry->id().toLower() == name ||
        entry->startupClass().toLower() == name)
      return entry;
  }
  for (auto *entry : m_entries) {
    if (entry->id().section('.', -1).compare(name, Qt::CaseInsensitive) == 0)
      return entry;
  }
  return nullptr;
}
void ApplicationCatalogue::refresh(bool force) { scan(force); }
void ApplicationCatalogue::scan(bool force) {
  QSet<QString> seen, watched, filesSeen;
  bool entriesChanged = false;
  QObjectList visible;
  for (const auto &root : roots()) {
    if (QDir(root).exists())
      watched.insert(root);
    // Watch the nearest existing parent so first-time installations are seen.
    auto parent = QFileInfo(root).dir();
    while (!parent.exists() && parent.cdUp()) {
    }
    if (parent.exists())
      watched.insert(parent.path());
    QDirIterator dirs(root, QDir::Dirs | QDir::NoDotAndDotDot,
                      QDirIterator::Subdirectories);
    while (dirs.hasNext())
      watched.insert(dirs.next());
    QDirIterator files(root, {"*.desktop"}, QDir::Files,
                       QDirIterator::Subdirectories);
    while (files.hasNext()) {
      const auto path = files.next();
      auto id = QDir(root).relativeFilePath(path);
      id.replace('/', '-');
      id.chop(8);
      if (seen.contains(id))
        continue;
      seen.insert(id);
      watched.insert(path);
      filesSeen.insert(path);
      const auto info = files.fileInfo();
      const auto stamp = QByteArray::number(info.size()) + ':' +
          QByteArray::number(info.lastModified().toMSecsSinceEpoch()) + ':' +
          QByteArray::number(info.metadataChangeTime().toMSecsSinceEpoch());
      const auto cached = m_cachedFiles.constFind(path);
      auto *existing = m_entries.value(id);
      const bool fileChanged = cached == m_cachedFiles.cend() || cached->stamp != stamp || m_dirtyFiles.contains(path);
      if (!force && !fileChanged && existing && existing->filePath() == path &&
          (cached->tryExec.isEmpty() || cached->executable == QStandardPaths::findExecutable(cached->tryExec))) {
        if (!existing->noDisplay()) visible.append(existing);
        continue;
      }
      auto *app =
          g_desktop_app_info_new_from_filename(path.toUtf8().constData());
      if (!app) {
        if (auto *old = m_entries.take(id)) {
          entriesChanged = true;
          old->deleteLater();
        }
        continue;
      }
      if (g_desktop_app_info_get_is_hidden(app)) {
        if (auto *old = m_entries.take(id)) {
          entriesChanged = true;
          old->deleteLater();
        }
        g_object_unref(app);
        continue;
      }
      const auto tryExec = take(g_desktop_app_info_get_string(app, "TryExec"));
      m_cachedFiles.insert(path, {stamp, tryExec, tryExec.isEmpty() ? QString{} : QStandardPaths::findExecutable(tryExec)});
      auto *appInfo = G_APP_INFO(app);
      QVariantMap data{
          {"id", id},
          {"name", QString::fromUtf8(g_app_info_get_display_name(appInfo))},
          {"comment", QString::fromUtf8(g_app_info_get_description(appInfo))},
          {"genericName",
           QString::fromUtf8(g_desktop_app_info_get_generic_name(app))},
          {"startupClass",
           QString::fromUtf8(g_desktop_app_info_get_startup_wm_class(app))},
          {"execString", QString::fromUtf8(g_app_info_get_commandline(appInfo))},
          {"icon", take(g_desktop_app_info_get_string(app, "Icon"))},
          {"workingDirectory",
           take(g_desktop_app_info_get_string(app, "Path"))},
          {"runInTerminal",
           bool(g_desktop_app_info_get_boolean(app, "Terminal"))},
          {"noDisplay", !bool(g_app_info_should_show(appInfo))},
          {"categories",
           QString::fromUtf8(g_desktop_app_info_get_categories(app))
               .split(';', Qt::SkipEmptyParts)},
          {"keywords", strings(g_desktop_app_info_get_keywords(app))}};
      gint argc = 0;
      gchar **argv = nullptr;
      const auto exec = data.value("execString").toString().toUtf8();
      QStringList command;
      if (g_shell_parse_argv(exec.constData(), &argc, &argv, nullptr)) {
        for (int i = 0; i < argc; ++i) {
          auto arg = QString::fromUtf8(argv[i]);
          if (arg == "%f" || arg == "%F" || arg == "%u" || arg == "%U" ||
              arg == "%i")
            continue;
          arg.replace("%c", data.value("name").toString());
          arg.replace("%k", path);
          arg.replace("%%", "%");
          command.append(arg);
        }
        g_strfreev(argv);
      }
      data.insert("command", command);
      auto *entry = m_entries.value(id);
      if (!entry) {
        entry = new DesktopApplication(this);
        m_entries.insert(id, entry);
        connect(entry, &DesktopApplication::launchFailed, this,
                [this](const QString &message) {
                  m_error = message;
                  emit errorChanged();
                });
      }
      entriesChanged |= entry->update(data, path, fileChanged || force);
      if (!data.value("noDisplay").toBool())
        visible.append(entry);
      g_object_unref(app);
    }
  }
  for (auto it = m_entries.begin(); it != m_entries.end();) {
    if (!seen.contains(it.key())) {
      entriesChanged = true;
      it.value()->deleteLater();
      it = m_entries.erase(it);
    } else
      ++it;
  }
  auto current = m_watcher.directories();
  current.append(m_watcher.files());
  const QSet<QString> old(current.begin(), current.end());
  const auto removed = (old - watched).values(),
             added = (watched - old).values();
  if (!removed.isEmpty())
    m_watcher.removePaths(removed);
  if (!added.isEmpty())
    m_watcher.addPaths(added);
  std::sort(visible.begin(), visible.end(), [](QObject *a, QObject *b) {
    return a->property("id").toString() < b->property("id").toString();
  });
  for (auto it = m_cachedFiles.begin(); it != m_cachedFiles.end();)
    if (!filesSeen.contains(it.key())) it = m_cachedFiles.erase(it);
    else ++it;
  m_dirtyFiles.clear();
  if (m_visible != visible || entriesChanged) {
    m_visible = visible;
    emit applicationsChanged();
  }
}
} // namespace hyprstack::services
