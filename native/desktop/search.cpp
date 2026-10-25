#include "../system/game_activity.hpp"
#include "service.hpp"
#include <QDateTime>
#include <QDirIterator>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QMutex>
#include <QScopeGuard>
#include <QSet>
#include <QSqlDatabase>
#include <QSqlError>
#include <QSqlQuery>
#include <QStandardPaths>
#include <QThread>
#include <QUrl>
#include <QUuid>
#include <QXmlStreamReader>
namespace HicsDesktop {
void Service::search(const QSharedPointer<Job> &job) {
  const auto args = job->arguments;
  const auto op = job->operation;
  const auto dir = directory;
  const auto cancel = job->cancel;
  worker(
      job,
      [args, op, dir, cancel] {
        static QMutex indexMutex;
        if (!indexMutex.tryLock())
          return QJsonObject{{"error", "Another search operation is running"}};
        auto unlock = qScopeGuard([&] { indexMutex.unlock(); });
        auto config = readJson(dir + "/search.json");
        if (config.isEmpty())
          config = {
              {"folders", QJsonArray{QStandardPaths::writableLocation(
                                         QStandardPaths::DocumentsLocation),
                                     QStandardPaths::writableLocation(
                                         QStandardPaths::DesktopLocation)}},
              {"excluded", QJsonArray{}},
              {"contents", false},
              {"maxFiles", 10000}};
        if (op == "search.config")
          return config;
        if (op == "search.configure") {
          QJsonObject value = config;
          for (const auto &key : {"folders", "excluded"})
            if (args.contains(key)) {
              QJsonArray paths;
              for (const auto &row : args[key].toArray()) {
                auto path = QFileInfo(row.toString()).canonicalFilePath();
                if (path.isEmpty() || !QFileInfo(path).isDir())
                  return QJsonObject{{"error", "Choose existing folders"}};
                paths.append(path);
              }
              if (paths.size() > 32)
                return QJsonObject{{"error", "Too many search folders"}};
              value[key] = paths;
            }
          if (args.contains("contents"))
            value["contents"] = args["contents"].toBool();
          for (const auto &key :
               {"automatic", "pauseOnBattery", "pauseForGames", "pdf"})
            if (args.contains(key))
              value[key] = args[key].toBool();
          for (const auto &field : QList<QPair<QString, QPair<int, int>>>{
                   {"intervalMinutes", {1, 1440}},
                   {"budgetMs", {100, 10000}},
                   {"contentMiB", {1, 64}},
                   {"maxCpuLoadPercent", {10, 95}}})
            if (args.contains(field.first))
              value[field.first] =
                  qBound(field.second.first, args[field.first].toInt(),
                         field.second.second);
          if (args.contains("maxFiles"))
            value["maxFiles"] = qBound(100, args["maxFiles"].toInt(), 50000);
          writeJson(dir + "/search.json", value);
          if (args.contains("folders") || args.contains("excluded") ||
              args.contains("contents") || args.contains("pdf") ||
              args.contains("contentMiB") || args.contains("maxFiles"))
            QFile::remove(dir + "/files.sqlite");
          return value;
        }
        if (op == "search.recent") {
          QFile recent(QStandardPaths::writableLocation(
                           QStandardPaths::GenericDataLocation) +
                       "/recently-used.xbel");
          QJsonArray items;
          if (recent.open(QIODevice::ReadOnly) &&
              recent.size() <= 2 * 1024 * 1024) {
            QXmlStreamReader xml(recent.readAll());
            QSet<QString> seen;
            while (!xml.atEnd() && items.size() < 40) {
              xml.readNext();
              if (!xml.isStartElement() ||
                  xml.name() != QStringLiteral("bookmark"))
                continue;
              const auto url = QUrl(xml.attributes().value("href").toString());
              if (!url.isLocalFile())
                continue;
              const auto path =
                  QFileInfo(url.toLocalFile()).canonicalFilePath();
              if (path.isEmpty() || !QFileInfo(path).isFile() ||
                  seen.contains(path))
                continue;
              bool blocked = false;
              for (const auto &part : path.split('/'))
                if (part.startsWith('.'))
                  blocked = true;
              for (const auto &row : config["excluded"].toArray())
                if (path == row.toString() ||
                    path.startsWith(row.toString() + "/"))
                  blocked = true;
              if (!blocked) {
                seen.insert(path);
                items.append(QJsonObject{{"path", path},
                                         {"name", QFileInfo(path).fileName()}});
              }
            }
          }
          return QJsonObject{{"items", items}};
        }
        QDir().mkpath(dir);
        const auto name = QUuid::createUuid().toString();
        auto cleanup = qScopeGuard([&] { QSqlDatabase::removeDatabase(name); });
        auto db = QSqlDatabase::addDatabase("QSQLITE", name);
        db.setDatabaseName(dir + "/files.sqlite");
        db.setConnectOptions("QSQLITE_BUSY_TIMEOUT=2000");
        if (!db.open())
          return QJsonObject{{"error", "Cannot open file index"}};
        QSqlQuery q(db);
        if (!q.exec("CREATE VIRTUAL TABLE IF NOT EXISTS files USING fts5(path "
                    "UNINDEXED,name,body)"))
          return QJsonObject{{"error", q.lastError().text()}};
        if (op == "search.index") {
          if (!q.exec("CREATE TABLE IF NOT EXISTS filemeta(path TEXT PRIMARY "
                      "KEY, stamp INTEGER, size INTEGER, body TEXT)"))
            return QJsonObject{
                {"error", "Cannot prepare incremental file index"}};
          QSqlQuery cached(db), cacheSave(db);
          cached.prepare(
              "SELECT body FROM filemeta WHERE path=? AND stamp=? AND size=?");
          cacheSave.prepare("INSERT OR REPLACE INTO "
                            "filemeta(path,stamp,size,body) VALUES(?,?,?,?)");
          const auto contentBudget =
              qint64(config["contentMiB"].toInt(8)) * 1024 * 1024;
          int reused = 0, pdfs = 0;

          if (!db.transaction())
            return QJsonObject{{"error", "Index is busy"}};
          q.exec("DELETE FROM files");
          QSqlQuery add(db);
          add.prepare("INSERT INTO files(path,name,body) VALUES(?,?,?)");
          QElapsedTimer timer;
          timer.start();
          int count = 0;
          qint64 contentBytes = 0;
          bool limited = false;
          QSet<QString> seen;
          const auto excluded = config["excluded"].toArray();
          auto blocked = [&](const QString &path) {
            for (const auto &row : excluded) {
              auto prefix = row.toString();
              if (path == prefix || path.startsWith(prefix + "/"))
                return true;
            }
            auto rel = QDir::home().relativeFilePath(path);
            for (const auto &part : rel.split('/'))
              if (part.startsWith('.') && part != "..")
                return true;
            return false;
          };
          for (const auto &folder : config["folders"].toArray()) {
            const auto root = folder.toString();
            if (root.isEmpty() || blocked(root))
              continue;
            // Explicit traversal prunes private directories before entering
            // them and never follows symlinks.
            QStringList pending{root};
            while (!pending.isEmpty() && !cancel->load()) {
              const auto current = pending.takeLast();
              QDirIterator entries(current, QDir::AllEntries |
                                                QDir::NoDotAndDotDot |
                                                QDir::Readable);
              while (entries.hasNext()) {
                entries.next();
                const auto info = entries.fileInfo();
                const auto path = info.absoluteFilePath();
                if (info.isSymLink() || blocked(path))
                  continue;
                if (timer.elapsed() > config["budgetMs"].toInt(10000) ||
                    count >= config["maxFiles"].toInt(10000)) {
                  limited = true;
                  pending.clear();
                  break;
                }
                if (info.isDir()) {
                  if (pending.size() < 4096)
                    pending.append(path);
                  continue;
                }
                if (!info.isFile() || seen.contains(path))
                  continue;
                seen.insert(path);
                QString body;
                bool hit = false;
                cached.bindValue(0, path);
                cached.bindValue(1, info.lastModified().toMSecsSinceEpoch());
                cached.bindValue(2, info.size());
                if (cached.exec() && cached.next()) {
                  body = cached.value(0).toString();
                  hit = true;
                  ++reused;
                }
                cached.finish();

                const auto suffix = info.suffix().toLower();
                if (!hit && config["contents"].toBool() &&
                    info.size() <= 262144 &&
                    contentBytes + info.size() <= contentBudget &&
                    QStringList{"txt", "md", "csv", "log", "rst", "tex"}
                        .contains(suffix)) {
                  QFile file(path);
                  if (file.open(QIODevice::ReadOnly)) {
                    auto bytes = file.read(262144);
                    if (!bytes.contains('\0'))
                      body = QString::fromUtf8(bytes);
                  }
                }
                if (!hit && config["contents"].toBool() &&
                    config["pdf"].toBool() && suffix == "pdf" &&
                    info.size() <= 2 * 1024 * 1024 && pdfs < 4 &&
                    timer.elapsed() + 2000 < config["budgetMs"].toInt(10000)) {
                  ++pdfs;
                  const auto text =
                      command("pdftotext",
                              {"-f", "1", "-l", "5", "-nopgbrk", path, "-"},
                              2000, 262144);
                  if (text.exitCode == 0)
                    body = QString::fromUtf8(text.output);
                }
                const auto length = body.toUtf8().size();
                if (contentBytes + length > contentBudget)
                  body.clear();
                else
                  contentBytes += length;
                const bool deferredPdf = !hit && body.isEmpty() && config["contents"].toBool() &&
                    config["pdf"].toBool() && suffix == "pdf";
                cacheSave.bindValue(0, path);
                cacheSave.bindValue(1, info.lastModified().toMSecsSinceEpoch());
                cacheSave.bindValue(2, info.size());
                cacheSave.bindValue(3, body);
                if (!deferredPdf && !cacheSave.exec()) {
                  db.rollback();
                  return QJsonObject{
                      {"error", "Cannot update incremental index"}};
                }
                add.bindValue(0, path);
                add.bindValue(1, info.fileName());
                add.bindValue(2, body);
                if (!add.exec()) {
                  db.rollback();
                  return QJsonObject{{"error", "Cannot update file index"}};
                }
                ++count;
              }
            }
            if (limited || cancel->load())
              break;
          }
          if (cancel->load()) {
            db.rollback();
            return QJsonObject{{"cancelled", true}};
          }
          q.exec("DELETE FROM filemeta WHERE path NOT IN (SELECT path FROM "
                 "files)");
          if (!db.commit())
            return QJsonObject{{"error", "Cannot commit file index"}};
          return QJsonObject{{"count", count},
                             {"limited", limited},
                             {"contentBytes", contentBytes},
                             {"reused", reused}};
        }
        if (op == "search.query") {
          const auto text = args["query"].toString().trimmed().left(256);
          if (text.isEmpty())
            return QJsonObject{{"items", QJsonArray{}}};
          QString escaped = text;
          escaped.replace('"', "\"\"");
          q.prepare("SELECT path,name FROM files WHERE files MATCH ? LIMIT 40");
          q.addBindValue("\"" + escaped + "\"*");
          if (!q.exec())
            return QJsonObject{{"error", "Cannot search the file index"}};
          QJsonArray items;
          while (q.next()) {
            const auto path = q.value(0).toString();
            if (QFileInfo(path).isFile())
              items.append(
                  QJsonObject{{"path", path}, {"name", q.value(1).toString()}});
          }
          return QJsonObject{{"items", items}};
        }
        if (op == "search.clear") {
          q.exec("DELETE FROM files");
          q.exec("DROP TABLE IF EXISTS filemeta");
          q.exec("VACUUM");
          return QJsonObject{{"ok", true}};
        }
        return QJsonObject{{"error", "Unknown search operation"}};
      },
      op == "search.index");
}
void Service::scheduledSearch() {
  const auto config = readJson(directory + "/search.json");
  if (!config["automatic"].toBool() || stopping)
    return;
  for (const auto &job : jobs)
    if (!job->finished && job->operation == "search.index")
      return;
  const auto now = QDateTime::currentSecsSinceEpoch(),
             last = readJson(directory + "/search-schedule.json")["lastAttempt"]
                        .toInteger();
  if (now - last < qint64(config["intervalMinutes"].toInt(15)) * 60)
    return;
  if (config["pauseForGames"].toBool(true) && hics::game::active())
    return;
  if (config["pauseOnBattery"].toBool(true)) {
    bool battery = false, powered = false;
    for (const auto &entry :
         QDir("/sys/class/power_supply")
             .entryInfoList(QDir::Dirs | QDir::NoDotAndDotDot)) {
      QFile type(entry.filePath() + "/type");
      if (type.open(QIODevice::ReadOnly) && type.readAll().trimmed() == "Battery")
        battery = true;
      QFile online(entry.filePath() + "/online");
      if (online.open(QIODevice::ReadOnly) && online.readAll().trimmed() == "1")
        powered = true;
    }
    if (battery && !powered)
      return;
  }
  QFile load("/proc/loadavg");
  if (load.open(QIODevice::ReadOnly) &&
      load.read(128).split(' ').value(0).toDouble() >
          qMax(1, QThread::idealThreadCount()) *
              config["maxCpuLoadPercent"].toInt(70) / 100.0)
    return;
  try {
    writeJson(directory + "/search-schedule.json", {{"lastAttempt", now}});
    enqueue("search.index", "{}");
  } catch (const std::exception &) {
  }
}
} // namespace HicsDesktop
