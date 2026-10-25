#include "workspacetools.hpp"
#include "workspacestore.hpp"
#include "util/applicationenv.hpp"
#include "util/applicationlaunch.hpp"
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QDirIterator>
#include <QFile>
#include <QFileInfo>
#include <QFutureWatcher>
#include <QJsonArray>
#include <QJsonDocument>
#include <QKeySequence>
#include <QProcessEnvironment>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSettings>
#include <QStandardPaths>
#include <QThread>
#include <QUuid>
#include <QtConcurrent>
#include <algorithm>
#include <stdexcept>
#pragma push_macro("signals")
#undef signals
#include <glib.h>
#pragma pop_macro("signals")

namespace hyprstack::services {
namespace W = hics::workspace;
namespace {
void fail(const QString &s) { throw std::runtime_error(s.toStdString()); }
QString helper() {
  const auto override = qEnvironmentVariable("HICS_WORKSPACE_HELPER");
  return override.isEmpty() ? QStandardPaths::findExecutable("hics-workspace")
                            : override;
}
QVariantList clients() {
  return QJsonDocument::fromJson(W::command("hyprctl", {"-j", "clients"}))
      .array()
      .toVariantList();
}
bool excluded(const QString &patterns, const QString &value) {
  for (const auto &line : patterns.split('\n', Qt::SkipEmptyParts))
    if (QRegularExpression(line.trimmed(),
                           QRegularExpression::CaseInsensitiveOption)
            .match(value)
            .hasMatch())
      return true;
  return false;
}
QString snapshotPath(const QString &id) {
  if (!QRegularExpression("^(?:automatic|[a-f0-9-]{36})$").match(id).hasMatch())
    fail("Invalid session snapshot identifier");
  return W::statePath() + "/sessions/" + id + ".json";
}
QStringList strings(const QVariant &value) {
  QStringList out;
  for (const auto &v : value.toList())
    out << v.toString();
  return out;
}
QString normalizedApp(QString s) {
  s = s.toLower();
  if (s.endsWith(".desktop"))
    s.chop(8);
  return s;
}
QVariantMap readDesktop(const QString &path) {
  GKeyFile *key = g_key_file_new();
  if (!g_key_file_load_from_file(key, path.toUtf8().constData(),
                                 G_KEY_FILE_NONE, nullptr)) {
    g_key_file_unref(key);
    return {};
  }
  QVariantMap result;
  for (const auto *name :
       {"Type", "Hidden", "Exec", "StartupWMClass", "Icon"}) {
    char *value = g_key_file_get_string(key, "Desktop Entry", name, nullptr);
    result[name] = QString::fromUtf8(value ? value : "");
    g_free(value);
  }
  char *name = g_key_file_get_locale_string(key, "Desktop Entry", "Name",
                                            nullptr, nullptr);
  result["Name"] = QString::fromUtf8(name ? name : "");
  g_free(name);
  g_key_file_unref(key);
  return result;
}
QVariantList desktopFiles() {
  QVariantList list;
  auto paths =
      QStandardPaths::standardLocations(QStandardPaths::ApplicationsLocation);
  paths << QDir::homePath() + "/.local/share/flatpak/exports/share/applications"
        << "/var/lib/flatpak/exports/share/applications";
  QSet<QString> seen;
  for (const auto &dir : paths) {
    QDirIterator it(dir, {"*.desktop"}, QDir::Files,
                    QDirIterator::Subdirectories);
    while (it.hasNext()) {
      const auto path = it.next();
      const auto id = QDir(dir).relativeFilePath(path).replace('/', '-');
      if (seen.contains(id))
        continue;
      seen.insert(id);
      const auto f = readDesktop(path);
      if (f.value("Hidden").toString() == "true" ||
          (!f.value("Type").toString().isEmpty() &&
           f.value("Type") != "Application"))
        continue;
      list << QVariantMap{{"id", id},
                          {"file", path},
                          {"name", f.value("Name")},
                          {"exec", f.value("Exec")},
                          {"wmclass", f.value("StartupWMClass")},
                          {"icon", f.value("Icon")}};
    }
  }
  return list;
}
QVariantMap desktopFor(const QString &app, const QVariantList &files) {
  for (const auto &v : files) {
    auto f = v.toMap();
    if (normalizedApp(f.value("id").toString()) == normalizedApp(app) ||
        normalizedApp(f.value("wmclass").toString()) == normalizedApp(app))
      return f;
  }
  for (const auto &v : files) {
    auto f = v.toMap();
    const auto parts = QProcess::splitCommand(f.value("exec").toString());
    if (!parts.isEmpty() &&
        normalizedApp(QFileInfo(parts.first()).fileName()) ==
            normalizedApp(app))
      return f;
  }
  return {};
}
QStringList desktopExec(const QString &value, const QString &file = {},
                        const QString &name = {}) {
  int count = 0;
  char **argv = nullptr;
  GError *error = nullptr;
  if (!g_shell_parse_argv(value.toUtf8().constData(), &count, &argv, &error)) {
    QString message =
        QString::fromUtf8(error ? error->message : "Invalid desktop command");
    g_clear_error(&error);
    fail(message);
  }
  QStringList list;
  for (int i = 0; i < count; ++i)
    list << QString::fromUtf8(argv[i]);
  g_strfreev(argv);
  QStringList out;
  for (auto arg : list) {
    if (arg == "%f" || arg == "%F" || arg == "%u" || arg == "%U" || arg == "%i")
      continue;
    QString expanded;
    for (qsizetype i = 0; i < arg.size(); ++i) {
      if (arg[i] != '%') {
        expanded += arg[i];
        continue;
      }
      if (++i >= arg.size())
        fail("Unsupported desktop command field code");
      const auto code = arg[i];
      if (code == '%')
        expanded += '%';
      else if (code == 'c')
        expanded += name;
      else if (code == 'k')
        expanded += file;
      else if (code != 'f' && code != 'F' && code != 'u' && code != 'U')
        fail("Unsupported desktop command field code");
    }
    arg = expanded;
    out << arg;
  }
  return out;
}
QVariantMap validateSnapshot(QVariantMap snapshot) {
  if (snapshot.value("version").toInt() != 1)
    fail("Unsupported session snapshot format");
  if (snapshot.value("name").toString().trimmed().isEmpty())
    fail("Session name is required");
  const auto project = snapshot.value("project").toMap();
  if (project.value("enabled").toBool()) {
    const auto target = project.value("workspace").toInt();
    if (target < 1 || target > 1000000 ||
        project.value("workspaceName").toString().size() > 256 ||
        !QStringList{"canvas", "tiling", "scrolling", "stacking"}.contains(
            snapshot.value("mode").toString()))
      fail("Invalid workspace project");
    const auto theme = project.value("theme").toMap();
    for (const auto &key : {"name", "flavour", "accent", "variant"})
      if (theme.value(key).toString().size() > 128 ||
          theme.value(key).toString().contains(QChar(0)))
        fail("Invalid project theme");
    if (theme.value("name").toString().size() > 128 ||
        !QStringList{"dark", "light"}.contains(
            theme.value("mode", "dark").toString()))
      fail("Invalid project theme");
  }
  auto entries = snapshot.value("windows").toList();
  if (entries.size() > 500)
    fail("Too many applications in session");
  for (auto &item : entries) {
    auto entry = item.toMap();
    const auto argv = strings(entry.value("command"));
    if (argv.size() > 256)
      fail("Application command is too long");
    for (const auto &arg : argv)
      if (arg.contains(QChar(0)) || arg.size() > 65536)
        fail("Invalid application argument");
    item = entry;
  }
  snapshot["windows"] = entries;
  return snapshot;
}
QVariantMap makeSnapshot(const QString &name) {
  auto config = W::settings("session");
  auto files = desktopFiles();
  QVariantList entries;
  const auto windows = clients();
  const auto monitors =
      QJsonDocument::fromJson(W::command("hyprctl", {"-j", "monitors"}))
          .array()
          .toVariantList();
  for (const auto &v : windows) {
    const auto c = v.toMap();
    const auto app = c.value("initialClass", c.value("class")).toString();
    if (!c.value("mapped").toBool() || c.value("hidden").toBool() ||
        c.value("pinned").toBool() ||
        excluded(config.value("excludedApps").toString(), app))
      continue;
    auto workspace = c.value("workspace").toMap();
    if (workspace.value("id").toInt() < 1)
      continue;
    auto file = desktopFor(app, files);
    QStringList argv;
    // Never persist a process command line: it may contain passwords/tokens.
    if (!file.isEmpty())
      argv = desktopExec(file.value("exec").toString(),
                         file.value("file").toString(),
                         file.value("name").toString());
    QString monitor;
    QVariantList monitorAt;
    for (const auto &m : monitors)
      if (m.toMap().value("id") == c.value("monitor")) {
        auto mm = m.toMap();
        monitor = mm.value("name").toString();
        monitorAt = {mm.value("x"), mm.value("y")};
      }
    entries << QVariantMap{
        {"key", QUuid::createUuid().toString(QUuid::WithoutBraces)},
        {"workingDirectory",
         QFileInfo("/proc/" + QString::number(c.value("pid").toInt()) + "/cwd")
             .symLinkTarget()},
        {"application", app},
        {"name", file.value("name", app)},
        {"desktopId", file.value("id")},
        {"command", argv},
        {"title", c.value("title")},
        {"workspace", workspace.value("id")},
        {"monitor", monitor},
        {"monitorAt", monitorAt},
        {"at", c.value("at")},
        {"size", c.value("size")},
        {"floating", c.value("floating")},
        {"fullscreen", c.value("fullscreen")},
        {"focusOrder", c.value("focusHistoryID", 10000)},
        {"enabled", !argv.isEmpty()},
        {"reason", argv.isEmpty() ? "No matching desktop entry. Set a launch "
                                    "command before restoring."
                                  : ""}};
  }
  QString mode = "scrolling";
  try {
    mode =
        QString::fromUtf8(
            W::command("hyprctl", {"repl", "return hyprstack_layouts.mode()"}))
            .trimmed();
  } catch (...) {
  }
  return {{"version", 1},
          {"name", name},
          {"created", QDateTime::currentSecsSinceEpoch()},
          {"source", "hics"},
          {"mode", mode},
          {"windows", entries}};
}
} // namespace

ClipboardHistory::ClipboardHistory(QObject *parent) : QObject(parent) {
  m_refresh.setSingleShot(true);
  m_refresh.setInterval(120);
  connect(&m_refresh, &QTimer::timeout, this, &ClipboardHistory::refresh);
  connect(&m_files, &QFileSystemWatcher::fileChanged, this,
          [this] { m_refresh.start(); });
  connect(&m_files, &QFileSystemWatcher::directoryChanged, this,
          [this](const QString &directory) {
    // Atomic index replacement drops the file watch. Directory notifications
    // only rearm that watch; lock/payload files must not refresh the history.
    const auto index = directory + "/index.json";
    if (QFileInfo::exists(index) && !m_files.files().contains(index)) {
      m_files.addPath(index);
      m_refresh.start();
    }
  });
  for(auto *process:{&m_text,&m_image}) {
    connect(process,&QProcess::errorOccurred,this,[this](QProcess::ProcessError error){if(!m_restarting&&error==QProcess::FailedToStart){m_error="Clipboard capture could not start. Check wl-clipboard installation.";emit changed();}});
    connect(process,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this,process](int code,QProcess::ExitStatus){
      if(!m_restarting&&code!=0){const auto detail=QString::fromUtf8(process->readAllStandardError()).trimmed();m_error=detail.isEmpty()?"Clipboard capture stopped unexpectedly":detail;emit changed();}
    });
    connect(process,&QProcess::stateChanged,this,[this]{emit changed();});
  }
  QTimer::singleShot(0, this, [this] {
    refresh();
    watchers();
  });
  auto *cleanup = new QTimer(this);
  cleanup->setInterval(15 * 60 * 1000);
  connect(cleanup, &QTimer::timeout, this, &ClipboardHistory::refresh);
  cleanup->start();
}
void ClipboardHistory::perform(const std::function<void()> &action) {
  try {
    m_error.clear();
    action();
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
  }
  emit changed();
}
void ClipboardHistory::refresh() {
  try {
    m_settings = W::settings("clipboard");
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
    emit changed();
    return;
  }
  if (m_refreshing) {
    m_refreshAgain = true;
    return;
  }
  m_refreshing = true;
  auto *watcher = new QFutureWatcher<QVariantMap>(this);
  connect(watcher, &QFutureWatcher<QVariantMap>::finished, this, [this, watcher] {
    const auto result = watcher->result();
    watcher->deleteLater();
    m_refreshing = false;
    m_error = result.value("error").toString();
    if (m_error.isEmpty()) {
      m_entries = result.value("entries").toList();
      const auto directory = result.value("directory").toString();
      if (!m_files.directories().contains(directory)) {
        if (!m_files.directories().isEmpty()) m_files.removePaths(m_files.directories());
        if (!m_files.files().isEmpty()) m_files.removePaths(m_files.files());
        m_files.addPath(directory);
      }
      const auto index = directory + "/index.json";
      if (QFileInfo::exists(index) && !m_files.files().contains(index)) m_files.addPath(index);
    }
    emit changed();
    if (m_refreshAgain) {
      m_refreshAgain = false;
      m_refresh.start();
    }
  });
  // Acquiring the history lock and pruning files can wait for a clipboard
  // writer. Never block Qt's GUI/render synchronization while doing so.
  watcher->setFuture(QtConcurrent::run([] {
    try {
      return QVariantMap{{"entries", W::clipboardEntries()},
                         {"directory", W::clipboardDirectory()}};
    } catch (const std::exception &e) {
      return QVariantMap{{"error", QString::fromUtf8(e.what())}};
    }
  }));
}
void ClipboardHistory::watchers() {
  const bool wanted =
      m_settings.value("enabled").toBool() &&
      !m_settings.value("paused").toBool() &&
      !(m_locked && m_settings.value("pauseWhenLocked").toBool());
  m_restarting=true;
  for (auto *p : {&m_text, &m_image}) {
    if (p->state() != QProcess::NotRunning) {
      p->terminate();
      if (!p->waitForFinished(800))
        p->kill();
    }
  }
  m_restarting=false;
  if (!wanted || qEnvironmentVariableIsEmpty("WAYLAND_DISPLAY"))
    return;
  if (m_settings.value("text").toBool())
    m_text.start("wl-paste", {"--type", "text", "--watch", helper(),
                              "clipboard-store", "text/plain;charset=utf-8"});
  if (m_settings.value("images").toBool())
    m_image.start("wl-paste", {"--type", "image", "--watch", helper(),
                               "clipboard-store", "image/auto"});
}
void ClipboardHistory::configure(const QVariantMap &values) {
  perform([&] {
    W::setSettings("clipboard", values);
    refresh();
    watchers();
  });
}
void ClipboardHistory::setLocked(bool locked) {
  m_locked = locked;
  const auto marker =
      QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) +
      "/hics-clipboard-locked";
  if (locked) {
    QFile f(marker);
    if (f.open(QIODevice::WriteOnly))
      f.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
  } else
    QFile::remove(marker);
  watchers();
}
void ClipboardHistory::copy(const QString &id) {
  perform([&] {
    QString mime;
    for (const auto &e : m_entries)
      if (e.toMap().value("id") == id)
        mime = e.toMap().value("mime").toString();
    if (mime.isEmpty())
      fail("Clipboard entry no longer exists");
    auto *p = new QProcess(this);
    connect(p, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), p,
            &QObject::deleteLater);
    p->setStandardInputFile(W::clipboardFile(id));
    connect(p, &QProcess::errorOccurred, this, [this, p](QProcess::ProcessError) {
      m_error = "Cannot copy clipboard entry: " + p->errorString();
      p->deleteLater(); emit changed();
    });
    p->start("wl-copy", {"--type", mime});

  });
}
void ClipboardHistory::pasteLatest() {
  if (m_locked || m_entries.isEmpty())
    return;
  perform([&] {
    const auto active =
        QJsonDocument::fromJson(W::command("hyprctl", {"-j", "activewindow"}))
            .toVariant()
            .toMap();
    const auto address = active.value("address").toString();
    const auto pid = active.value("pid").toInt();
    if (address.isEmpty())
      return;
    auto entries = W::readMap(W::clipboardDirectory() + "/index.json")
                       .value("entries")
                       .toList();
    if (entries.isEmpty())
      return;
    const auto entry = entries.first().toMap();
    auto *process = new QProcess(this);
    connect(
        process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished),
        this, [this, process, address, pid](int code, QProcess::ExitStatus) {
          process->deleteLater();
          if (code || m_locked)
            return;
          QTimer::singleShot(80, this, [this, address, pid] {
            perform([&] {
              if (m_locked)
                return;
              const auto script = "local w=hl.get_window(" +
                                  W::luaString("address:" + address) +
                                  "); if w and w.pid==" + QString::number(pid) +
                                  " and hl.get_active_window()==w then "
                                  "hl.dispatch(hl.dsp.send_shortcut({mods='"
                                  "CTRL',key='V',window=w})) end";
              W::command("hyprctl", {"eval", script});
            });
          });
        });
    process->setStandardInputFile(W::clipboardFile(entry.value("id").toString()));
    connect(process, &QProcess::errorOccurred, this, [this, process](QProcess::ProcessError) {
      m_error = "Cannot copy clipboard entry: " + process->errorString();
      process->deleteLater(); emit changed();
    });
    process->start("wl-copy", {"--type", entry.value("mime").toString()});

  });
}
QString ClipboardHistory::decode(const QString &id) {
  QString out;
  perform([&] { out = QString::fromUtf8(W::clipboardData(id)); });
  return out;
}
void ClipboardHistory::edit(const QString &id, const QString &value) {
  perform([&] {
    if (W::storeClipboard(value.toUtf8(), "text/plain;charset=utf-8", {},
                          true)) {
      const auto replacement = QString::fromLatin1(
          QCryptographicHash::hash(QByteArray("text/plain;charset=utf-8") +
                                       '\0' + value.toUtf8(),
                                   QCryptographicHash::Sha256)
              .toHex());
      bool wasPinned = false;
      for (const auto &entry : m_entries)
        if (entry.toMap().value("id") == id)
          wasPinned = entry.toMap().value("pinned").toBool();
      if (replacement != id) {
        if (wasPinned)
          W::alterClipboard(replacement, "pin");
        W::alterClipboard(id, "delete");
      }
      refresh();
    } else
      fail("The edited content was excluded or exceeded the clipboard size "
           "limit");
  });
}
void ClipboardHistory::remove(const QString &id) {
  perform([&] {
    W::alterClipboard(id, "delete");
    refresh();
  });
}
void ClipboardHistory::pin(const QString &id) {
  perform([&] {
    W::alterClipboard(id, "pin");
    refresh();
  });
}
void ClipboardHistory::clear(bool keepPinned) {
  perform([&] {
    W::clearClipboard(keepPinned);
    refresh();
  });
}
void ClipboardHistory::prepareLogout() {
  perform([&] {
    if (m_settings.value("clearOnLogout").toBool())
      W::clearClipboard(false);
  });
}
void ClipboardHistory::importLegacy() {
  if (m_importing)
    return;
  m_importing = true;
  m_error.clear();
  emit changed();
  const auto limit = m_settings.value("maxEntries").toInt();
  auto *watcher = new QFutureWatcher<QString>(this);
  connect(watcher, &QFutureWatcher<QString>::finished, this, [this, watcher] {
    m_error = watcher->result();
    watcher->deleteLater();
    m_importing = false;
    const auto error = m_error;
    refresh();
    m_error = error;
    emit changed();
  });
  watcher->setFuture(QtConcurrent::run([limit] {
    try {
      auto lines = W::command("cliphist", {"list"}).split('\n');
      if (lines.size() > limit)
        lines = lines.mid(0, limit);
      std::reverse(lines.begin(), lines.end());
      for (const auto &line : lines) {
        auto id = line.left(line.indexOf('\t'));
        if (id.isEmpty())
          continue;
        QProcess p;
        p.start("cliphist", {"decode"});
        if (!p.waitForStarted())
          continue;
        p.write(id);
        p.closeWriteChannel();
        if (!p.waitForFinished(3000)) {
          p.kill();
          continue;
        }
        const auto data = p.readAllStandardOutput();
        const bool image =
            data.startsWith("\x89PNG") || data.startsWith("\xff\xd8");
        W::storeClipboard(
            data,
            image ? (data.startsWith("\x89PNG") ? "image/png" : "image/jpeg")
                  : "text/plain;charset=utf-8",
            "Imported from cliphist");
      }
      return QString();
    } catch (const std::exception &e) {
      return QString::fromUtf8(e.what());
    }
  }));
}

ShortcutEditor::ShortcutEditor(QObject *parent) : QObject(parent) {
  QTimer::singleShot(0, this, &ShortcutEditor::refresh);
}
void ShortcutEditor::refresh() {
  try {
    m_error.clear();
    m_settings = W::settings("shortcuts");
    m_actions.clear();
    const auto signature = qEnvironmentVariable("HYPRLAND_INSTANCE_SIGNATURE");
    if (!QRegularExpression("^[A-Za-z0-9_.-]+$").match(signature).hasMatch()) {
      emit changed();
      return;
    }
    const auto catalogue = W::readMap(
        QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) +
        "/hics-shortcuts-" + signature + ".json");
    if (catalogue.isEmpty() && !m_attemptedReload) {
      m_attemptedReload = true;
      W::command("hyprctl", {"reload"});
      QTimer::singleShot(300, this, &ShortcutEditor::refresh);
      emit changed();
      return;
    }
    const auto overrides = m_settings.value("overrides").toMap();
    const auto liveDocument =
        QJsonDocument::fromJson(W::command("hyprctl", {"-j", "binds"}));
    QSet<QString> liveActions;
    for (const auto &bind : liveDocument.array()) {
      const auto b = bind.toObject().toVariantMap();
      liveActions.insert(b.value("description").toString() + "\n" +
                         b.value("submap").toString());
    }
    for (const auto &value : catalogue.value("actions").toList()) {
      auto action = value.toMap();
      const auto id = action.value("id").toString();
      if (liveDocument.isArray() && !liveActions.contains(id) &&
          !overrides.contains(id))
        continue;
      action["defaultKeys"] = action.value("keys");
      action["modified"] = overrides.contains(id);
      if (overrides.contains(id)) {
        const auto o = overrides.value(id).toMap();
        for (auto i = o.begin(); i != o.end(); ++i)
          action[i.key()] = i.value();
      }
      m_actions << action;
    }
    for (const auto &value : m_settings.value("custom").toList()) {
      auto action = value.toMap();
      action["custom"] = true;
      action["modified"] = true;
      m_actions << action;
    }
    std::sort(m_actions.begin(), m_actions.end(),
              [](const QVariant &a, const QVariant &b) {
                return a.toMap().value("description").toString() <
                       b.toMap().value("description").toString();
              });
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
  }
  emit changed();
}
QVariantList ShortcutEditor::conflicts(const QString &id, const QString &chord,
                                       const QString &submap) const {
  QVariantList result;
  QString key;
  try {
    key = W::normalizedChord(chord).toLower();
  } catch (...) {
    return result;
  }
  for (const auto &v : m_actions) {
    const auto a = v.toMap();
    if (a.value("id") == id || a.value("disabled").toBool() ||
        a.value("submap").toString() != submap)
      continue;
    for (const auto &old : strings(a.value("keys")))
      try {
        if (W::normalizedChord(old).toLower() == key) {
          result << a;
          break;
        }
      } catch (...) {
      }
  }
  return result;
}
QString ShortcutEditor::recordKey(int key, int modifiers,
                                  int nativeScanCode) const {
  if (key == Qt::Key_Control || key == Qt::Key_Meta || key == Qt::Key_Alt ||
      key == Qt::Key_Shift || key == Qt::Key_unknown)
    return {};
  QString name = QKeySequence(key).toString(QKeySequence::PortableText);
  const QMap<int, QString> names = {
      {Qt::Key_Return, "Return"},
      {Qt::Key_Enter, "Return"},
      {Qt::Key_Space, "Space"},
      {Qt::Key_Escape, "Escape"},
      {Qt::Key_Backspace, "BackSpace"},
      {Qt::Key_PageUp, "Page_Up"},
      {Qt::Key_PageDown, "Page_Down"},
      {Qt::Key_Plus, "equal"},
      {Qt::Key_VolumeUp, "XF86AudioRaiseVolume"},
      {Qt::Key_VolumeDown, "XF86AudioLowerVolume"},
      {Qt::Key_VolumeMute, "XF86AudioMute"},
      {Qt::Key_MediaPlay, "XF86AudioPlay"},
      {Qt::Key_MediaNext, "XF86AudioNext"},
      {Qt::Key_MediaPrevious, "XF86AudioPrev"},
      {Qt::Key_MediaStop, "XF86AudioStop"},
      {Qt::Key_MonBrightnessUp, "XF86MonBrightnessUp"},
      {Qt::Key_MonBrightnessDown, "XF86MonBrightnessDown"}};
  name = names.value(key, name);
  QStringList parts;
  if (modifiers & Qt::MetaModifier)
    parts << "SUPER";
  if (modifiers & Qt::ControlModifier)
    parts << "CTRL";
  if (modifiers & Qt::AltModifier)
    parts << "ALT";
  if (modifiers & Qt::ShiftModifier)
    parts << "SHIFT";
  if (m_settings.value("physicalKeys").toBool() && nativeScanCode > 0)
    name = "code:" + QString::number(nativeScanCode);
  parts << name;
  try {
    return W::normalizedChord(parts.join(" + "));
  } catch (...) {
    return {};
  }
}
void ShortcutEditor::persist(const QVariantMap &value) {
  const auto before = W::settings("shortcuts");
  W::setSettings("shortcuts", value);
  try {
    W::command("hyprctl", {"reload"});
    const auto errors =
        QString::fromUtf8(W::command("hyprctl", {"configerrors"})).trimmed();
    if (!errors.isEmpty())
      fail("Hyprland rejected shortcut configuration: " + errors);
  } catch (...) {
    W::setSettings("shortcuts", before);
    try {
      W::command("hyprctl", {"reload"});
    } catch (...) {
    }
    throw;
  }
  QTimer::singleShot(300, this, &ShortcutEditor::refresh);
}
void ShortcutEditor::save(const QVariantMap &input) {
  try {
    m_error.clear();
    auto action = input;
    auto config = W::settings("shortcuts");
    auto id = action.value("id").toString();
    const bool custom = action.value("custom").toBool() ||
                        id.startsWith("custom:") || id.isEmpty();
    if (custom && id.isEmpty())
      id = "custom:" + QUuid::createUuid().toString(QUuid::WithoutBraces);
    if (!custom && !std::any_of(m_actions.begin(), m_actions.end(),
                                [&](const QVariant &v) {
                                  return v.toMap().value("id") == id;
                                }))
      fail("Unknown shortcut action");
    action["id"] = id;
    QStringList keys;
    for (const auto &key : strings(action.value("keys"))) {
      auto normalized = W::normalizedChord(key);
      if (!conflicts(id, normalized, action.value("submap").toString())
               .isEmpty())
        fail("This shortcut is already assigned to another action");
      if (!keys.contains(normalized))
        keys << normalized;
    }
    if (keys.isEmpty() && !action.value("disabled").toBool())
      fail("Press a key combination");
    action["keys"] = keys;
    if (custom) {
      if (action.value("description").toString().trimmed().isEmpty() ||
          action.value("command").toString().trimmed().isEmpty())
        fail("Shortcut name and command are required");
      auto list = config.value("custom").toList();
      bool found = false;
      for (auto &v : list)
        if (v.toMap().value("id") == id) {
          v = action;
          found = true;
        }
      if (!found)
        list << action;
      config["custom"] = list;
    } else {
      auto overrides = config.value("overrides").toMap();
      overrides[id] = action;
      config["overrides"] = overrides;
    }
    persist(config);
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
  }
  emit changed();
}
void ShortcutEditor::reset(const QString &id) {
  try {
    m_error.clear();
    for (const auto &v : m_actions) {
      const auto action = v.toMap();
      if (action.value("id") == id && !action.value("custom").toBool()) {
        for (const auto &key : strings(action.value("defaultKeys")))
          if (!conflicts(id, key, action.value("submap").toString()).isEmpty())
            fail("A default shortcut conflicts with another action. Reassign "
                 "it before resetting.");
      }
    }
    auto config = W::settings("shortcuts");
    auto overrides = config.value("overrides").toMap();
    overrides.remove(id);
    config["overrides"] = overrides;
    auto list = config.value("custom").toList();
    for (qsizetype i = list.size(); i-- > 0;)
      if (list[i].toMap().value("id") == id)
        list.removeAt(i);
    config["custom"] = list;
    persist(config);
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
  }
  emit changed();
}
void ShortcutEditor::resetAll() {
  try {
    m_error.clear();
    persist(W::defaults("shortcuts"));
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
  }
  emit changed();
}
void ShortcutEditor::configure(const QVariantMap &values) {
  try {
    m_error.clear();
    W::setSettings("shortcuts", values);
    refresh();
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
  }
  emit changed();
}
void ShortcutEditor::exportFile(const QUrl &url) {
  try {
    if (!url.isLocalFile())
      fail("Select a local file");
    W::writeMap(url.toLocalFile(),
                {{"version", 1}, {"shortcuts", W::settings("shortcuts")}});
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
  }
  emit changed();
}
void ShortcutEditor::importFile(const QUrl &url) {
  try {
    m_error.clear();
    if (!url.isLocalFile())
      fail("Select a local file");
    auto data = W::readMap(url.toLocalFile());
    if (data.value("version").toInt() != 1)
      fail("Unsupported shortcut format");
    const auto config = data.value("shortcuts").toMap();
    QSet<QString> used;
    auto check = [&](const QVariantMap &a) {
      if (a.value("disabled").toBool())
        return;
      for (const auto &key : strings(a.value("keys"))) {
        auto k = a.value("submap").toString() + "\n" +
                 W::normalizedChord(key).toLower();
        if (used.contains(k))
          fail("Imported shortcuts contain conflicting assignments");
        used.insert(k);
      }
    };
    const auto overrides = config.value("overrides").toMap();
    for (const auto &v : m_actions) {
      const auto a = v.toMap();
      if (a.value("custom").toBool())
        continue;
      check(overrides.contains(a.value("id").toString())
                ? overrides.value(a.value("id").toString()).toMap()
                : a);
    }
    for (const auto &v : config.value("custom").toList())
      check(v.toMap());
    persist(config);
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
  }
  emit changed();
}

WorkspaceSession::~WorkspaceSession() {
  m_cancel->store(true);
  // QFutureWatcher destruction does not join the worker. Keep Qt alive until
  // cancellation has terminated its subprocesses and detached value work.
  m_task.waitForFinished();
}
WorkspaceSession::WorkspaceSession(QObject *parent) : QObject(parent) {
  m_refreshTimer.setSingleShot(true);
  m_refreshTimer.setInterval(100);
  connect(&m_sessionFiles, &QFileSystemWatcher::fileChanged, this,
          [this] { m_refreshTimer.start(); });
  connect(&m_sessionFiles, &QFileSystemWatcher::directoryChanged, this,
          [this] { m_refreshTimer.start(); });
  connect(&m_refreshTimer, &QTimer::timeout, this, &WorkspaceSession::refresh);
  connect(this, &WorkspaceSession::finished, this, [this] { m_refreshTimer.start(); });
  QTimer::singleShot(0, this, &WorkspaceSession::refresh);
}
QString WorkspaceSession::desktop() const {
  return qEnvironmentVariable("XDG_CURRENT_DESKTOP");
}
void WorkspaceSession::refresh() {
  // Files written by a worker must not publish a partially updated session.
  if (m_busy) return;
  try {
    const auto settings = W::settings("session");
    const auto request = W::readMap(W::startupPath());
    const bool pending = request.value("pending").toBool() &&
                         settings.value("enabled").toBool();
    QVariantList snapshots;
    QDir dir(W::statePath() + "/sessions");
    QStringList watched{W::configPath(), W::startupPath(), dir.absolutePath()};
    for (const auto &file :
         dir.entryList({"*.json"}, QDir::Files, QDir::Time)) {
      auto snapshot = W::readMap(dir.filePath(file));
      snapshot["id"] = QFileInfo(file).baseName();
      snapshot["count"] = snapshot.value("windows").toList().size();
      snapshot.remove("windows");
      snapshots << snapshot;
      watched << dir.filePath(file);
    }
    // Watch parents too: QSaveFile replaces inodes, and directories may not
    // exist until the first saved session. Re-arm file watches after each event.
    const auto paths = watched;
    for (const auto &path : paths) {
      auto parent = QFileInfo(path).absoluteDir();
      while (!parent.exists() && !parent.isRoot())
        parent = QDir(QFileInfo(parent.absolutePath()).absolutePath());
      watched << parent.absolutePath();
    }
    watched.removeDuplicates();
    for (const auto &path : watched)
      if (QFileInfo::exists(path) && !m_sessionFiles.files().contains(path) &&
          !m_sessionFiles.directories().contains(path)) m_sessionFiles.addPath(path);
    const bool recovered = !m_refreshError.isEmpty() && m_error == m_refreshError;
    if (recovered) m_error.clear();
    m_refreshError.clear();
    const bool dirty = recovered || m_settings != settings || m_snapshots != snapshots ||
                       m_startupPending != pending;
    m_settings = settings;
    m_snapshots = snapshots;
    m_startupPending = pending;
    if (dirty) emit changed();
  } catch (const std::exception &e) {
    const auto error = QString::fromUtf8(e.what());
    if (m_error.isEmpty() || m_error == m_refreshError) {
      const bool dirty = m_error != error;
      m_error = m_refreshError = error;
      if (dirty) emit changed();
    }
  }
}
void WorkspaceSession::autostart() {
  const auto dir =
      QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) +
      "/autostart";
  const auto path = dir + "/hics-session-restore.desktop";
  if (!m_settings.value("enabled").toBool() ||
      m_settings.value("startup") == "none") {
    QFile::remove(path);
    return;
  }
  QDir().mkpath(dir);
  QSaveFile file(path);
  if (!file.open(QIODevice::WriteOnly))
    fail("Cannot configure session autostart");
  QByteArray data = "[Desktop Entry]\nType=Application\nName=hics session "
                    "restore\nExec=hics-workspace "
                    "startup\nTerminal=false\nX-GNOME-Autostart-enabled=true\n";
  if (!m_settings.value("crossDesktop").toBool())
    data += "OnlyShowIn=Hyprland;hics;\n";
  file.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
  file.write(data);
  if (!file.commit())
    fail("Cannot configure session autostart");
}
void WorkspaceSession::configure(const QVariantMap &values) {
  try {
    m_error.clear();
    W::setSettings("session", values);
    m_settings = W::settings("session");
    autostart();
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
  }
  emit changed();
}
void WorkspaceSession::task(
    const std::function<QVariantMap()> &work,
    const std::function<void(const QVariantMap &)> &done) {
  if (m_busy)
    return;
  m_busy = true;
  m_error.clear();
  emit changed();
  auto *watcher = new QFutureWatcher<QVariantMap>(this);
  connect(watcher, &QFutureWatcher<QVariantMap>::finished, this,
          [this, watcher, done] {
            auto result = watcher->result();
            watcher->deleteLater();
            m_busy = false;
            const bool success = !result.contains("error");
            if (success)
              done(result);
            else
              m_error = result.value("error").toString();
            emit changed();
            emit finished(success);
          });
  if (m_cancel->load()) m_cancel = std::make_shared<std::atomic_bool>(false);
  auto cancellation = m_cancel;
  m_task = QtConcurrent::run([work, cancellation] {
    struct Reset { ~Reset() { W::commandCancellation.reset(); } } reset;
    W::commandCancellation = cancellation;
    try {
      if (cancellation->load()) fail("Operation cancelled");
      return work();
    } catch (const std::exception &e) {
      return QVariantMap{{"error", QString::fromUtf8(e.what())}};
    }
  });
  watcher->setFuture(m_task);
}
void WorkspaceSession::capture(const QString &name, bool automatic) {
  task(
      [name, automatic] {
        auto snapshot = makeSnapshot(name);
        const auto id =
            automatic ? QString("automatic")
                      : QUuid::createUuid().toString(QUuid::WithoutBraces);
        snapshot["id"] = id;
        W::writeMap(snapshotPath(id), snapshot);
        const auto count =
            W::settings("session").value("keepSnapshots").toInt();
        QDir dir(W::statePath() + "/sessions");
        auto files = dir.entryList({"*.json"}, QDir::Files, QDir::Time);
        int kept = 0;
        for (const auto &file : files) {
          if (file == "automatic.json" || W::readMap(dir.filePath(file)).value("project").toMap().value("enabled").toBool())
            continue;
          if (++kept > count)
            dir.remove(file);
        }
        return snapshot;
      },
      [this, automatic](const QVariantMap &s) {
        if (!automatic)
          m_preview = s;
        refresh();
      });
}
void WorkspaceSession::captureProject(const QString &name, int sourceWorkspace,
                                      int targetWorkspace, const QString &mode,
                                      bool keepTheme) {
  task(
      [=] {
        if (name.trimmed().isEmpty() || name.size() > 256 ||
            targetWorkspace < 1 || targetWorkspace > 1000000 ||
            !QStringList{"canvas", "tiling", "scrolling", "stacking"}.contains(
                mode))
          fail("Invalid workspace project");
        auto snapshot = makeSnapshot(name.trimmed());
        int source = sourceWorkspace;
        if (source < 0) {
          source = QJsonDocument::fromJson(
                       W::command("hyprctl", {"-j", "activeworkspace"}))
                       .object()
                       .value("id")
                       .toInt();
          if (source < 1)
            fail("No active workspace is available");
        }
        QVariantList windows;
        for (auto value : snapshot.value("windows").toList()) {
          auto entry = value.toMap();
          if (source > 0 && entry.value("workspace").toInt() != source)
            continue;
          entry["workspace"] = targetWorkspace;
          windows << entry;
        }
        snapshot["windows"] = windows;
        snapshot["mode"] = mode;
        QVariantMap project{{"enabled", true},
                            {"workspace", targetWorkspace},
                            {"workspaceName", name.trimmed()},
                            {"applyTheme", keepTheme}};
        if (keepTheme) {
          auto theme = W::readMap(QStandardPaths::writableLocation(
                                      QStandardPaths::GenericStateLocation) +
                                  "/hics/scheme.json");
          QVariantMap selection;
          for (const auto &key :
               {"name", "mode", "flavour", "accent", "variant"})
            if (theme.contains(key))
              selection[key] = theme.value(key);
          project["theme"] = selection;
        }
        snapshot["project"] = project;
        snapshot["id"] = QUuid::createUuid().toString(QUuid::WithoutBraces);
        snapshot = validateSnapshot(snapshot);
        W::writeMap(snapshotPath(snapshot.value("id").toString()), snapshot);
        return snapshot;
      },
      [this](const QVariantMap &snapshot) {
        m_preview = snapshot;
        refresh();
      });
}
void WorkspaceSession::inspect(const QString &id) {
  try {
    m_error.clear();
    m_preview = validateSnapshot(W::readMap(snapshotPath(id)));
    m_preview["id"] = id;
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
  }
  emit changed();
}
void WorkspaceSession::savePreview(const QVariantMap &value) {
  try {
    m_error.clear();
    auto snapshot = validateSnapshot(value);
    auto id = snapshot.value("id").toString();
    if (id.isEmpty())
      id = QUuid::createUuid().toString(QUuid::WithoutBraces);
    snapshot["id"] = id;
    W::writeMap(snapshotPath(id), snapshot);
    m_preview = snapshot;
    refresh();
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
  }
  emit changed();
}
void WorkspaceSession::remove(const QString &id) {
  try {
    m_error.clear();
    QFile::remove(snapshotPath(id));
    if (m_preview.value("id") == id)
      m_preview.clear();
    refresh();
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
  }
  emit changed();
}
void WorkspaceSession::cancel() { m_cancel->store(true); }
void WorkspaceSession::restore(const QString &id,
                               const QVariantList &selected) {
  if (m_busy)
    return;
  m_cancel = std::make_shared<std::atomic_bool>(false);
  auto cancelled = m_cancel;
  task(
      [id, selected, cancelled] {
        const auto snapshot = validateSnapshot(W::readMap(snapshotPath(id)));
        auto settings = W::settings("session");
        const bool hyprland =
            !qEnvironmentVariableIsEmpty("HYPRLAND_INSTANCE_SIGNATURE") &&
            qEnvironmentVariable("XDG_CURRENT_DESKTOP")
                .contains("Hyprland", Qt::CaseInsensitive);
        QVariantList existing = hyprland ? clients() : QVariantList{};
        QVariantList report;
        QSet<QString> launched, used;
        const auto files = desktopFiles();
        const auto project = snapshot.value("project").toMap();
        if (project.value("enabled").toBool())
          for (const auto &key : {"skipRunning", "launchPerWindow"})
            if (project.contains(key))
              settings[key] = project.value(key);
        if (hyprland && project.value("enabled").toBool()) {
          const int workspace = project.value("workspace").toInt();
          const auto name = project.value("workspaceName").toString();
          W::command(
              "hyprctl",
              {"eval",
               "hl.dispatch(hl.dsp.focus({workspace=" +
                   W::luaString(QString::number(workspace)) +
                   "}));hl.dispatch(hl.dsp.workspace.rename({workspace=" +
                   W::luaString(QString::number(workspace)) +
                   ",name=" + W::luaString(name) + "}))"});
          if (project.value("applyTheme").toBool()) {
            const auto theme = project.value("theme").toMap();
            if (!theme.value("name").toString().isEmpty()) {
              QStringList command{
                  "scheme", "set",
                  "--name", theme.value("name").toString(),
                  "--mode", theme.value("mode", "dark").toString()};
              const bool dynamic = theme.value("name") == "dynamic";
              for (const auto &key : {"flavour", "accent", "variant"})
                if (theme.contains(key) &&
                    !theme.value(key).toString().isEmpty() &&
                    (dynamic ? QLatin1String(key) == "variant"
                             : QLatin1String(key) != "variant"))
                  command << "--" + QLatin1String(key)
                          << theme.value(key).toString();
              W::command("hics", command, 20000);
            }
          }
        }
        if (hyprland && (settings.value("restoreMode").toBool() ||
                         project.value("enabled").toBool())) {
          const auto mode = snapshot.value("mode").toString();
          if (QStringList{"canvas", "tiling", "scrolling", "stacking"}.contains(
                  mode))
            W::command("hyprctl", {"eval", "hyprstack_layouts.set_mode(" +
                                               W::luaString(mode) + ")"});
        }
        QVariantList pending;
        QString focusAddress;
        int focusRank = 100000;
        for (const auto &v : snapshot.value("windows").toList()) {
          if (cancelled->load())
            break;
          auto entry = v.toMap();
          if (project.value("enabled").toBool())
            entry["workspace"] = project.value("workspace");
          const auto key = entry.value("key").toString();
          const auto app = entry.value("application").toString();
          if (!entry.value("enabled", true).toBool() ||
              (!selected.isEmpty() && !selected.contains(key)) ||
              excluded(settings.value("excludedApps").toString(), app))
            continue;
          QStringList argv = strings(entry.value("command"));
          QString status;
          bool running = false;
          for (const auto &c : existing)
            if (normalizedApp(
                    c.toMap()
                        .value("initialClass", c.toMap().value("class"))
                        .toString()) == normalizedApp(app))
              running = true;
          auto desktop =
              desktopFor(entry.value("desktopId", app).toString(), files);
          const auto desktopId = entry.value("desktopId").toString();
          const auto launchKey = desktopId.isEmpty() ? app : desktopId;
          if (running && settings.value("skipRunning").toBool())
            status = "Already running";
          else if (launched.contains(launchKey) &&
                   !settings.value("launchPerWindow").toBool())
            status = "Shared application launch";
          else if (argv.isEmpty())
            status = "No launch command";
          else {
            QProcess launch;
            launch.setProcessEnvironment(hics::util::applicationEnvironment());
            launch.setWorkingDirectory(entry.value("workingDirectory").toString());
            if (!desktop.isEmpty() && argv == desktopExec(desktop.value("exec").toString(),desktop.value("file").toString(),desktop.value("name").toString())) {
              launch.setProgram("gio");
              launch.setArguments({"launch", desktop.value("file").toString()});
            } else {
              launch.setProgram(argv.takeFirst());
              launch.setArguments(argv);
            }
            hics::util::isolateApplication(launch);
            const bool ok=launch.startDetached();
            status = ok ? "Launched" : "Launch failed";
            if (ok)
              launched.insert(launchKey);
            int delay = std::clamp(
                entry.value("launchDelay", settings.value("launchDelay"))
                    .toInt(),
                0, 60000);
            while (delay > 0 && !cancelled->load()) {
              QThread::msleep(50);
              delay -= 50;
            }
          }
          entry["status"] = status;
          report << entry;
          if (hyprland && status != "No launch command" &&
              status != "Launch failed")
            pending << entry;
        }
        const auto deadline = QDateTime::currentMSecsSinceEpoch() +
                              settings.value("windowTimeout").toInt() * 1000;
        while (!pending.isEmpty() &&
               QDateTime::currentMSecsSinceEpoch() < deadline &&
               !cancelled->load()) {
          auto live = clients();
          for (qsizetype i = pending.size(); i-- > 0;) {
            const auto entry = pending[i].toMap();
            QVariantMap match;
            for (const auto &cv : live) {
              auto c = cv.toMap();
              const auto address = c.value("address").toString();
              if (used.contains(address) || !c.value("mapped").toBool())
                continue;
              if (normalizedApp(
                      c.value("initialClass", c.value("class")).toString()) !=
                  normalizedApp(entry.value("application").toString()))
                continue;
              if (settings.value("matchTitles").toBool() &&
                  c.value("title") != entry.value("title"))
                continue;
              match = c;
              break;
            }
            if (match.isEmpty())
              continue;
            const auto address = match.value("address").toString();
            used.insert(address);
            const auto selector = "address:" + address;
            const auto w = "hl.get_window(" + W::luaString(selector) + ")";
            QStringList code;
            if (settings.value("restoreMonitors").toBool() &&
                !entry.value("monitor").toString().isEmpty()) {
              const auto monitors =
                  QJsonDocument::fromJson(
                      W::command("hyprctl", {"-j", "monitors"}))
                      .array()
                      .toVariantList();
              QString target;
              for (const auto &monitor : monitors)
                if (monitor.toMap().value("name") == entry.value("monitor"))
                  target = entry.value("monitor").toString();
              if (target.isEmpty() &&
                  settings.value("monitorPolicy") == "fallback" &&
                  !monitors.isEmpty())
                target = monitors.first().toMap().value("name").toString();
              if (!target.isEmpty())
                code << "hl.dispatch(hl.dsp.window.move({window=" + w +
                            ",monitor=" + W::luaString(target) +
                            ",follow=false}))";
            }

            if (settings.value("restoreWorkspaces").toBool() &&
                entry.value("workspace").toInt() > 0)
              code << "hl.dispatch(hl.dsp.window.move({window=" + w +
                          ",workspace=" +
                          W::luaString(QString::number(
                              entry.value("workspace").toInt())) +
                          ",follow=false}))";
            if (settings.value("restoreGeometry").toBool() &&
                entry.value("floating").toBool()) {
              const auto at = entry.value("at").toList(),
                         size = entry.value("size").toList();
              if (at.size() == 2 && size.size() == 2) {
                int x = at[0].toInt(), y = at[1].toInt();
                bool monitorPresent = false;
                const auto monitors =
                    QJsonDocument::fromJson(
                        W::command("hyprctl", {"-j", "monitors"}))
                        .array()
                        .toVariantList();
                for (const auto &m : monitors)
                  if (m.toMap().value("name") == entry.value("monitor"))
                    monitorPresent = true;
                if (!monitorPresent &&
                    settings.value("monitorPolicy") == "fallback" &&
                    !monitors.isEmpty()) {
                  const auto m = monitors.first().toMap();
                  x = m.value("x").toInt() + 40;
                  y = m.value("y").toInt() + 80;
                }
                code << "hl.dispatch(hl.dsp.window.float({window=" + w +
                            ",action='enable'}))";
                code << "hl.dispatch(hl.dsp.window.resize({window=" + w +
                            ",x=" +
                            QString::number(
                                std::clamp(size[0].toInt(), 100, 16384)) +
                            ",y=" +
                            QString::number(
                                std::clamp(size[1].toInt(), 80, 16384)) +
                            ",relative=false}))";
                code << "hl.dispatch(hl.dsp.window.move({window=" + w +
                            ",x=" + QString::number(x) +
                            ",y=" + QString::number(y) + ",relative=false}))";
              }
            }
            if (settings.value("restoreFullscreen").toBool() &&
                entry.value("fullscreen").toInt() > 0)
              code << "hl.dispatch(hl.dsp.window.fullscreen_state({window=" +
                          w + ",internal=" +
                          QString::number(std::clamp(
                              entry.value("fullscreen").toInt(), 0, 2)) +
                          ",client=0,action='set'}))";
            if (!code.isEmpty())
              W::command("hyprctl", {"eval", code.join(";")});
            if (entry.value("focusOrder", 10000).toInt() < focusRank) {
              focusRank = entry.value("focusOrder").toInt();
              focusAddress = address;
            }
            for (auto &r : report)
              if (r.toMap().value("key") == entry.value("key")) {
                auto rm = r.toMap();
                rm["placement"] = "Restored";
                r = rm;
              }
            pending.removeAt(i);
          }
          if (!pending.isEmpty())
            QThread::msleep(200);
        }
        for (auto &r : report) {
          auto entry = r.toMap();
          if (!hyprland)
            entry["placement"] = "Application launch only on this desktop";
          else if (!entry.contains("placement"))
            entry["placement"] = cancelled->load()
                                     ? "Cancelled"
                                     : "Window not found before timeout";
          r = entry;
        }
        if (!cancelled->load() && hyprland &&
            settings.value("restoreFocus").toBool() && !focusAddress.isEmpty())
          W::command(
              "hyprctl",
              {"eval",
               "local w=hl.get_window(" +
                   W::luaString("address:" + focusAddress) +
                   "); if w then hl.dispatch(hl.dsp.focus({window=w})) end"});
        return QVariantMap{{"report", report},
                           {"cancelled", cancelled->load()}};
      },
      [this](const QVariantMap &result) {
        m_report = result.value("report").toList();
        dismissStartup();
      });
}
QVariantList WorkspaceSession::desktopSessions() const {
  QVariantList result;
  const auto config =
      QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation);
  if (QDir(config + "/gnome-session/saved-session")
          .entryList({"*.desktop"}, QDir::Files)
          .size())
    result << QVariantMap{{"value", "gnome"}, {"label", "GNOME"}};
  QSettings kde(config + "/ksmserverrc", QSettings::IniFormat);
  for (const auto &group : kde.childGroups())
    if (group.startsWith("Session:") && group.size() <= 512)
      result << QVariantMap{{"value", "kde:" + group},
                            {"label", "KDE · " + group.mid(8).trimmed()}};
  return result;
}
void WorkspaceSession::importDesktop(const QString &source) {
  task(
      [source] {
        QVariantList entries;
        const auto config = QStandardPaths::writableLocation(
            QStandardPaths::GenericConfigLocation);
        if (source == "gnome") {
          QDir dir(config + "/gnome-session/saved-session");
          for (const auto &file : dir.entryList({"*.desktop"}, QDir::Files)) {
            const auto f = readDesktop(dir.filePath(file));
            if (f.value("Hidden").toString() == "true")
              continue;
            auto argv =
                desktopExec(f.value("Exec").toString(), dir.filePath(file),
                            f.value("Name").toString());
            entries << QVariantMap{
                {"key", QUuid::createUuid().toString(QUuid::WithoutBraces)},
                {"name", f.value("Name", file)},
                {"application",
                 f.value("StartupWMClass", QFileInfo(file).baseName())},
                {"command", argv},
                {"enabled", !argv.isEmpty()},
                {"desktopId", file}};
          }
        } else if (source == "kde" || source.startsWith("kde:Session:")) {
          QSettings f(config + "/ksmserverrc", QSettings::IniFormat);
          auto groups = f.childGroups();
          QString group;
          for (const auto &g : groups)
            if (g.startsWith("Session:")) {
              group = g;
              if (g == "Session: saved at previous logout")
                break;
            }
          if(source.startsWith("kde:")) {
            group = source.mid(4);
            if (!groups.contains(group))
              fail("Saved KDE session was not found");
          }
          if (!group.isEmpty()) {
            f.beginGroup(group);
            int count = std::clamp(f.value("count").toInt(), 0, 500);
            for (int i = 1; i <= count; ++i) {
              const auto suffix = QString::number(i);
              auto raw = f.value("restartCommand" + suffix);
              QStringList argv;
              if (raw.metaType().id() == QMetaType::QStringList)
                argv = raw.toStringList();
              else {
                auto text = raw.toString();
                QString part;
                bool escaped = false;
                for (auto ch : text) {
                  if (escaped) {
                    part += ch;
                    escaped = false;
                  } else if (ch == '\\')
                    escaped = true;
                  else if (ch == ',') {
                    argv << part;
                    part.clear();
                  } else
                    part += ch;
                }
                if (!part.isEmpty())
                  argv << part;
              }
              if (argv.isEmpty())
                continue;
              entries << QVariantMap{
                  {"key", QUuid::createUuid().toString(QUuid::WithoutBraces)},
                  {"name", f.value("program" + suffix, argv.first())},
                  {"application", QFileInfo(argv.first()).baseName()},
                  {"command", argv},
                  {"enabled", true},
                  {"sessionClientId", f.value("clientId" + suffix)}};
            }
          }
        } else
          fail("Unknown desktop session source");
        if (entries.isEmpty())
          fail("No saved applications were found for this desktop");
        return QVariantMap{
            {"version", 1},
            {"id", QUuid::createUuid().toString(QUuid::WithoutBraces)},
            {"name", source.startsWith("kde:")?"KDE · "+source.mid(12).trimmed():source.toUpper()+" session"},
            {"source", source},
            {"created", QDateTime::currentSecsSinceEpoch()},
            {"windows", entries}};
      },
      [this](const QVariantMap &snapshot) { m_preview = snapshot; });
}
void WorkspaceSession::importFile(const QUrl &url) {
  try {
    m_error.clear();
    if (!url.isLocalFile())
      fail("Select a local file");
    m_preview = validateSnapshot(W::readMap(url.toLocalFile()));
    m_preview["id"] = QUuid::createUuid().toString(QUuid::WithoutBraces);
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
  }
  emit changed();
}
void WorkspaceSession::exportFile(const QString &id, const QUrl &url,
                                  bool portable) {
  try {
    m_error.clear();
    if (!url.isLocalFile())
      fail("Select a local file");
    auto snapshot = validateSnapshot(W::readMap(snapshotPath(id)));
    if (!portable)
      W::writeMap(url.toLocalFile(), snapshot);
    else {
      QDir dir(url.toLocalFile());
      if (!QDir().mkpath(dir.path()))
        fail("Cannot create export directory");
      int n = 0;
      for (const auto &v : snapshot.value("windows").toList()) {
        const auto e = v.toMap();
        if (!e.value("enabled", true).toBool())
          continue;
        auto argv = strings(e.value("command"));
        if (argv.isEmpty())
          continue;
        QStringList quoted;
        for (auto arg : argv) {
          arg.replace('\\', "\\\\")
              .replace('"', "\\\"")
              .replace('`', "\\`")
              .replace('$', "\\$")
              .replace('%', "%%");
          quoted << '"' + arg + '"';
        }
        QSaveFile f(
            dir.filePath("hics-session-" + QString::number(++n) + ".desktop"));
        if (!f.open(QIODevice::WriteOnly))
          fail("Cannot export desktop entry");
        auto name = e.value("name", e.value("application")).toString();
        name.replace('\n', ' ').replace('\r', ' ');
        f.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
        GKeyFile *entry = g_key_file_new();
        g_key_file_set_string(entry, "Desktop Entry", "Type", "Application");
        g_key_file_set_string(entry, "Desktop Entry", "Name",
                              name.toUtf8().constData());
        g_key_file_set_string(entry, "Desktop Entry", "Exec",
                              quoted.join(' ').toUtf8().constData());
        g_key_file_set_string(entry, "Desktop Entry", "X-hics-Session",
                              id.toUtf8().constData());
        g_key_file_set_boolean(entry, "Desktop Entry", "Terminal", false);
        gsize length = 0;
        char *contents = g_key_file_to_data(entry, &length, nullptr);
        const auto written = f.write(contents, static_cast<qint64>(length));
        g_free(contents);
        g_key_file_unref(entry);
        if (written != static_cast<qint64>(length))
          fail("Cannot export desktop entry");
        if (!f.commit())
          fail("Cannot export desktop entry");
      }
    }
  } catch (const std::exception &e) {
    m_error = QString::fromUtf8(e.what());
  }
  emit changed();
}
void WorkspaceSession::dismissStartup() {
  m_startupPending = false;
  try {
    const auto path = W::startupPath();
    auto request = W::readMap(path);
    request["pending"] = false;
    W::writeMap(path, request);
  } catch (...) {
  }
  emit changed();
}
void WorkspaceSession::saveBeforeExit() {
  try {
    auto s = W::settings("session");
    if (s.value("enabled").toBool() && s.value("autosave").toBool())
      W::command(helper(), {"capture", "--automatic"}, 5000);
    if (W::settings("clipboard").value("clearOnLogout").toBool())
      W::clearClipboard(false);
  } catch (...) {
  } // A failed checkpoint must not prevent logout or shutdown.
}
} // namespace hyprstack::services
