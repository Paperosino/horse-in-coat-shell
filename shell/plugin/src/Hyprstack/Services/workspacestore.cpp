#include "workspacestore.hpp"
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLockFile>
#include <QProcess>
#include <QRegularExpression>
#include <QSaveFile>
#include <QStandardPaths>
#include <QUrl>
#include <algorithm>
#include <stdexcept>

namespace hics::workspace {
static void fail(const QString &s) {
  throw std::runtime_error(s.toStdString());
}
static void privateDirectory(const QString &path) {
  const bool existed = QFileInfo::exists(path);
  if (!QDir().mkpath(path))
    fail("Cannot create workspace data directory");
  if (!existed)
    QFile::setPermissions(path, QFile::ReadOwner | QFile::WriteOwner |
                                    QFile::ExeOwner);
}
QString configPath() {
  return QStandardPaths::writableLocation(
             QStandardPaths::GenericConfigLocation) +
         "/hics/workspace.json";
}
QString statePath() {
  return QStandardPaths::writableLocation(
             QStandardPaths::GenericStateLocation) +
         "/hics/workspace";
}
QString startupPath() {
  const auto login = qEnvironmentVariable("XDG_SESSION_ID") + ":" +
                     qEnvironmentVariable("HYPRLAND_INSTANCE_SIGNATURE") + ":" +
                     qEnvironmentVariable("WAYLAND_DISPLAY");
  return QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) +
         "/hics-workspace-startup-" +
         QString::fromLatin1(QCryptographicHash::hash(
                                 login.toUtf8(), QCryptographicHash::Sha256)
                                 .toHex()
                                 .left(20)) +
         ".json";
}
QString clipboardDirectory() {
  // Ephemeral history lives in the runtime directory, never in a disk cache.
  auto base =
      settings("clipboard").value("persistent", true).toBool()
          ? statePath()
          : QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) +
                "/hics-workspace";
  return base + "/clipboard";
}
QVariantMap readMap(const QString &path) {
  QFile f(path);
  if (!f.exists())
    return {};
  if (!f.open(QIODevice::ReadOnly))
    fail("Cannot read " + path);
  QJsonParseError error;
  const auto doc = QJsonDocument::fromJson(f.readAll(), &error);
  if (error.error != QJsonParseError::NoError || !doc.isObject())
    fail("Invalid workspace data: " + path);
  return doc.toVariant().toMap();
}
void writeMap(const QString &path, const QVariantMap &value) {
  privateDirectory(QFileInfo(path).absolutePath());
  QSaveFile f(path);
  if (!f.open(QIODevice::WriteOnly))
    fail("Cannot write " + path);
  f.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
  const auto bytes =
      QJsonDocument::fromVariant(value).toJson(QJsonDocument::Indented);
  if (f.write(bytes) != bytes.size() || !f.commit())
    fail("Cannot save " + path);
}
QVariantMap defaults(const QString &group) {
  if (group == "clipboard")
    return {{"enabled", true},        {"paused", false},
            {"text", true},           {"images", true},
            {"persistent", true},     {"maxEntries", 500},
            {"maxMiB", 10},           {"expiryDays", 30},
            {"ignoreSecrets", true},  {"pauseWhenLocked", true},
            {"clearOnLogout", false}, {"excludedApps", ""},
            {"excludedText", ""}};
  if (group == "session")
    return {{"enabled", false},
            {"autosave", true},
            {"interval", 120},
            {"startup", "ask"},
            {"startupSnapshot", "automatic"},
            {"crossDesktop", false},
            {"restoreGeometry", true},
            {"restoreMonitors", true},
            {"restoreWorkspaces", true},
            {"restoreFullscreen", true},
            {"restoreFocus", true},
            {"restoreMode", true},
            {"skipRunning", true},
            {"launchPerWindow", false},
            {"launchDelay", 500},
            {"windowTimeout", 20},
            {"keepSnapshots", 12},
            {"excludedApps", ""},
            {"matchTitles", false},
            {"monitorPolicy", "fallback"}};
  return {{"overrides", QVariantMap{}},
          {"custom", QVariantList{}},
          {"physicalKeys", false}};
}
QVariantMap settings(const QString &group) {
  auto result = defaults(group);
  const auto saved = readMap(configPath()).value(group).toMap();
  for (auto i = saved.begin(); i != saved.end(); ++i)
    result[i.key()] = i.value();
  return result;
}
void setSettings(const QString &group, const QVariantMap &value) {
  privateDirectory(QFileInfo(configPath()).absolutePath());
  QLockFile lock(configPath() + ".lock");
  if (!lock.tryLock(3000))
    fail("Workspace settings are busy");
  auto config = readMap(configPath());
  auto result = settings(group);
  for (auto i = value.begin(); i != value.end(); ++i) {
    if (!defaults(group).contains(i.key()))
      fail("Unknown workspace setting: " + i.key());
    result[i.key()] = i.value();
  }
  auto bound = [&](const char *key, int low, int high) {
    if (result.contains(key))
      result[key] = std::clamp(result[key].toInt(), low, high);
  };
  bound("maxEntries", 1, 10000);
  bound("maxMiB", 1, 100);
  bound("expiryDays", 0, 3650);
  bound("interval", 30, 3600);
  bound("launchDelay", 0, 10000);
  bound("windowTimeout", 2, 120);
  bound("keepSnapshots", 1, 100);
  for (const auto &key : {"excludedApps", "excludedText"}) {
    for (const auto &line :
         result.value(key).toString().split('\n', Qt::SkipEmptyParts))
      if (!QRegularExpression(line.trimmed()).isValid())
        fail("Invalid exclusion expression: " + line);
  }
  config[group] = result;
  writeMap(configPath(), config);
}
QByteArray command(const QString &program, const QStringList &args,
                   int timeout) {
  QProcess p;
  p.start(program, args);
  if (!p.waitForStarted(2000))
    fail("Cannot start " + program);
  if (!p.waitForFinished(timeout)) {
    p.kill();
    p.waitForFinished();
    fail(program + " timed out");
  }
  if (p.exitStatus() != QProcess::NormalExit || p.exitCode() != 0)
    fail(QString::fromUtf8(p.readAllStandardError()).trimmed().isEmpty()
             ? program + " failed"
             : QString::fromUtf8(p.readAllStandardError()).trimmed());
  return p.readAllStandardOutput();
}
static bool matches(const QString &patterns, const QString &value) {
  for (const auto &line : patterns.split('\n', Qt::SkipEmptyParts))
    if (QRegularExpression(line.trimmed(),
                           QRegularExpression::CaseInsensitiveOption)
            .match(value)
            .hasMatch())
      return true;
  return false;
}
static QString safeId(const QString &id) {
  if (!QRegularExpression("^[a-f0-9]{64}$").match(id).hasMatch())
    fail("Invalid clipboard entry");
  return id;
}
static QVariantList pruneEntries(QVariantList entries, const QString &dir) {
  const auto config = settings("clipboard");
  const auto cutoff = QDateTime::currentSecsSinceEpoch() -
                      config.value("expiryDays").toLongLong() * 86400;
  QVariantList kept;
  int count = 0;
  for (const auto &item : entries) {
    const auto e = item.toMap();
    const auto id = safeId(e.value("id").toString());
    const bool pinned = e.value("pinned").toBool();
    const bool expired = config.value("expiryDays").toInt() > 0 &&
                         e.value("timestamp").toLongLong() < cutoff;
    if (QFile::exists(dir + "/" + id) &&
        (pinned || (!expired && count++ < config.value("maxEntries").toInt())))
      kept << e;
    else
      QFile::remove(dir + "/" + id);
  }
  return kept;
}
QVariantList clipboardEntries(bool prune) {
  const auto dir = clipboardDirectory();
  privateDirectory(dir);
  QLockFile lock(dir + "/lock");
  if (!lock.tryLock(2000))
    fail("Clipboard history is busy");
  auto entries = readMap(dir + "/index.json").value("entries").toList();
  if (prune) {
    const auto before = entries;
    entries = pruneEntries(entries, dir);
    if (entries != before)
      writeMap(dir + "/index.json", {{"entries", entries}});
  }
  QVariantList result;
  for (const auto &item : entries) {
    auto e = item.toMap();
    e["raw"] = e.value("id");
    if (e.value("isBinary").toBool())
      e["imagePath"] =
          QUrl::fromLocalFile(dir + "/" + safeId(e.value("id").toString()))
              .toString();
    else
      e["imagePath"] = "";
    result << e;
  }
  std::stable_sort(result.begin(), result.end(),
                   [](const QVariant &a, const QVariant &b) {
                     return a.toMap().value("pinned").toBool() >
                            b.toMap().value("pinned").toBool();
                   });
  return result;
}
bool storeClipboard(const QByteArray &bytes, const QString &mime,
                    const QString &application, bool explicitAction) {
  const auto config = settings("clipboard");
  const bool image = mime.startsWith("image/");
  if (bytes.isEmpty() ||
      bytes.size() > config.value("maxMiB").toLongLong() * 1024 * 1024 ||
      (!explicitAction &&
       (!config.value("enabled").toBool() || config.value("paused").toBool())))
    return false;
  if ((image && !config.value("images").toBool()) ||
      (!image && !config.value("text").toBool()))
    return false;
  if (!image && !mime.startsWith("text/"))
    return false;
  if (matches(config.value("excludedApps").toString(), application) ||
      (!image && matches(config.value("excludedText").toString(),
                         QString::fromUtf8(bytes))))
    return false;
  const auto dir = clipboardDirectory();
  privateDirectory(dir);
  QLockFile lock(dir + "/lock");
  if (!lock.tryLock(3000))
    fail("Clipboard history is busy");
  auto entries = readMap(dir + "/index.json").value("entries").toList();
  const auto id =
      QString::fromLatin1(QCryptographicHash::hash(mime.toUtf8() + '\0' + bytes,
                                                   QCryptographicHash::Sha256)
                              .toHex());
  bool pinned = false;
  for (qsizetype i = entries.size(); i-- > 0;)
    if (entries[i].toMap().value("id") == id) {
      pinned = entries[i].toMap().value("pinned").toBool();
      entries.removeAt(i);
    }
  QSaveFile f(dir + "/" + id);
  if (!f.open(QIODevice::WriteOnly))
    fail("Cannot store clipboard entry");
  f.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
  if (f.write(bytes) != bytes.size() || !f.commit())
    fail("Cannot store clipboard entry");
  entries.prepend(QVariantMap{
      {"id", id},
      {"mime", mime},
      {"text",
       image ? mime + " · " + QString::number(bytes.size() / 1024) + " KiB"
             : QString::fromUtf8(bytes).left(4096)},
      {"isBinary", image},
      {"pinned", pinned},
      {"bytes", bytes.size()},
      {"application", application},
      {"timestamp", QDateTime::currentSecsSinceEpoch()}});
  entries = pruneEntries(entries, dir);
  writeMap(dir + "/index.json", {{"entries", entries}});
  return true;
}
QByteArray clipboardData(const QString &id) {
  QFile f(clipboardDirectory() + "/" + safeId(id));
  if (!f.open(QIODevice::ReadOnly))
    fail("Clipboard entry no longer exists");
  return f.readAll();
}
void alterClipboard(const QString &id, const QString &operation) {
  const auto dir = clipboardDirectory();
  safeId(id);
  privateDirectory(dir);
  QLockFile lock(dir + "/lock");
  if (!lock.tryLock(2000))
    fail("Clipboard history is busy");
  auto entries = readMap(dir + "/index.json").value("entries").toList();
  for (qsizetype i = entries.size(); i-- > 0;) {
    auto e = entries[i].toMap();
    if (e.value("id") != id)
      continue;
    if (operation == "delete") {
      entries.removeAt(i);
      QFile::remove(dir + "/" + id);
    } else if (operation == "pin") {
      e["pinned"] = !e.value("pinned").toBool();
      entries[i] = e;
    } else
      fail("Invalid clipboard operation");
  }
  writeMap(dir + "/index.json", {{"entries", entries}});
}
void clearClipboard(bool keepPinned) {
  QStringList dirs{clipboardDirectory()};
  if (!keepPinned)
    dirs = {statePath() + "/clipboard",
            QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) +
                "/hics-workspace/clipboard"};
  for (const auto &dir : dirs) {
    if (!QDir(dir).exists())
      continue;
    QLockFile lock(dir + "/lock");
    if (!lock.tryLock(2000))
      fail("Clipboard history is busy");
    auto entries = readMap(dir + "/index.json").value("entries").toList();
    QVariantList kept;
    QSet<QString> pins;
    for (const auto &v : entries) {
      auto e = v.toMap();
      if (keepPinned && e.value("pinned").toBool()) {
        kept << e;
        pins.insert(e.value("id").toString());
      }
    }
    for (const auto &file : QDir(dir).entryList(QDir::Files))
      if (QRegularExpression("^[a-f0-9]{64}$").match(file).hasMatch() &&
          !pins.contains(file))
        QFile::remove(dir + "/" + file);
    writeMap(dir + "/index.json", {{"entries", kept}});
  }
}
QString normalizedChord(const QString &value) {
  auto parts = value.split('+', Qt::SkipEmptyParts);
  if (parts.isEmpty())
    fail("Press a key combination");
  QStringList mods;
  QString key;
  for (auto part : parts) {
    part = part.trimmed();
    const auto lower = part.toLower();
    if (lower == "super" || lower == "meta" || lower == "win")
      mods << "SUPER";
    else if (lower == "ctrl" || lower == "control")
      mods << "CTRL";
    else if (lower == "alt")
      mods << "ALT";
    else if (lower == "shift")
      mods << "SHIFT";
    else if (key.isEmpty())
      key = part;
    else
      fail("Use one key with optional modifiers");
  }
  const QMap<QString, QString> aliases = {
      {"enter", "Return"},    {"esc", "Escape"},
      {"space", "Space"},     {"backspace", "BackSpace"},
      {"page up", "Page_Up"}, {"page down", "Page_Down"},
      {"pgup", "Page_Up"},    {"pgdown", "Page_Down"},
      {"plus", "equal"}};
  if (aliases.contains(key.toLower()))
    key = aliases.value(key.toLower());
  if (key.isEmpty() ||
      !QRegularExpression(
           "^(?:[A-Za-z0-9_]+|code:[0-9]+|mouse:[0-9]+|[.,/;='\\[\\]\\\\`-])$")
           .match(key)
           .hasMatch())
    fail("Unsupported shortcut key");
  if (key.size() == 1 && key[0].isLetter())
    key = key.toUpper();
  QStringList result;
  for (const auto &mod : {"SUPER", "CTRL", "ALT", "SHIFT"})
    if (mods.contains(mod))
      result << mod;
  result << key;
  return result.join(" + ");
}
QString luaString(const QString &s) {
  // JSON escaping is not Lua escaping: encode UTF-8 bytes explicitly.
  QString out = "\"";
  for (unsigned char c : s.toUtf8()) {
    if (c >= 32 && c < 127 && c != '"' && c != '\\')
      out += QChar(c);
    else
      out += "\\" + QString::number(c).rightJustified(3, '0');
  }
  return out + '"';
}
} // namespace hics::workspace
