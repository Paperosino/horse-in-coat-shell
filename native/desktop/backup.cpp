#include "service.hpp"
#include "util/applicationenv.hpp"
#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QStandardPaths>
#include <QStorageInfo>
#include <QUuid>
#include <unistd.h>
#pragma push_macro("signals")
#undef signals
#include <libsecret/secret.h>
#pragma pop_macro("signals")
namespace HicsDesktop {
namespace {
QString diskUuid(const QStorageInfo &storage) {
  const auto device =
      QFileInfo(QString::fromUtf8(storage.device())).canonicalFilePath();
  if (device.isEmpty())
    return {};
  for (const auto &entry : QDir("/dev/disk/by-uuid")
                               .entryInfoList(QDir::AllEntries | QDir::System |
                                              QDir::NoDotAndDotDot)) {
    if (entry.canonicalFilePath() == device)
      return entry.fileName();
  }
  return {};
}
const SecretSchema schema = {"org.hics.Backup",
                             SECRET_SCHEMA_NONE,
                             {{"repository", SECRET_SCHEMA_ATTRIBUTE_STRING},
                              {nullptr, SECRET_SCHEMA_ATTRIBUTE_STRING}},
                             0,
                             nullptr,
                             nullptr,
                             nullptr,
                             nullptr,
                             nullptr,
                             nullptr,
                             nullptr};
} // namespace
void Service::backup(const QSharedPointer<Job> &job) {
  const auto dir = directory, op = job->operation;
  if (op == "backup.snapper-manager") {
    const auto executable = QStandardPaths::findExecutable("btrfs-assistant");
    if (executable.isEmpty()) {
      finish(job, {}, "Btrfs Assistant is not installed");
      return;
    }
    process(
        job, "systemd-run",
        {"--user", "--wait", "--collect", "--quiet", "--pipe",
         "--expand-environment=no",
         "--unit=hics-snapshots-" + QUuid::createUuid().toString(QUuid::Id128),
         "--", executable},
        false);
    return;
  }
  if (op == "backup.timeshift-manager") {
    QString desktop;
    for (const auto &root : QStandardPaths::standardLocations(
             QStandardPaths::GenericDataLocation)) {
      const auto candidate = root + "/applications/timeshift-gtk.desktop";
      if (QFileInfo::exists(candidate)) {
        desktop = candidate;
        break;
      }
    }
    if (desktop.isEmpty()) {
      finish(job, {}, "The Timeshift desktop launcher is not installed");
      return;
    }
    process(
        job, "systemd-run",
        {"--user", "--wait", "--collect", "--quiet", "--pipe",
         "--expand-environment=no",
         "--unit=hics-snapshots-" + QUuid::createUuid().toString(QUuid::Id128),
         "--", QStandardPaths::findExecutable("gio"), "launch", desktop},
        false);
    return;
  }
  auto args = job->arguments;
  job->arguments.remove("password");
  const auto cancel = job->cancel;
  worker(
      job,
      [this, job, dir, op, args, cancel] {
        const auto file = dir + "/backup.json";
        auto config = readJson(file);
        if (op == "backup.config")
          return config;
        if (op == "backup.configure") {
          auto repository = QDir::cleanPath(args["repository"].toString());
          if (!QFileInfo(repository).isAbsolute() ||
              (QFileInfo::exists(repository) && !QFileInfo(repository).isDir()))
            return QJsonObject{
                {"error", "Choose an absolute repository folder"}};

          const auto parent = QFileInfo(QFileInfo(repository).absolutePath())
                                  .canonicalFilePath();
          if (parent.isEmpty())
            return QJsonObject{{"error", "Connect the backup disk and choose "
                                         "an existing parent folder"}};
          if (QFileInfo::exists(repository))
            repository = QFileInfo(repository).canonicalFilePath();
          else
            repository =
                QDir(parent).filePath(QFileInfo(repository).fileName());

          if (!QFileInfo(repository).isAbsolute() || repository == "/" ||
              repository == QDir::homePath())
            return QJsonObject{
                {"error", "Choose a dedicated absolute repository directory"}};
          QJsonArray folders;
          for (const auto &value : args["folders"].toArray()) {
            auto path = QFileInfo(value.toString()).canonicalFilePath();
            if (path.isEmpty() || !QFileInfo(path).isDir() ||
                path == repository || repository.startsWith(path + "/"))
              return QJsonObject{{"error", "Backup folders must exist and must "
                                           "not contain the repository"}};
            folders.append(path);
          }
          if (folders.isEmpty() || folders.size() > 32)
            return QJsonObject{
                {"error", "Choose between one and 32 source folders"}};
          QStorageInfo storage(QFileInfo::exists(repository)
                                   ? repository
                                   : QFileInfo(repository).absolutePath());
          if (!storage.isValid() || !storage.isReady())
            return QJsonObject{{"error", "The backup disk is unavailable"}};
          config = {
              {"repository", repository},
              {"folders", folders},
              {"device", QString::fromLatin1(storage.device().toBase64())},
              {"deviceUuid", diskUuid(storage)},
              {"mount", storage.rootPath()},
              {"intervalHours", qBound(0, args["intervalHours"].toInt(), 168)}};
          QJsonArray excluded;
          for (const auto &row : args["excluded"].toArray()) {
            if (excluded.size() >= 128 || row.toString().size() > 1024)
              return QJsonObject{
                  {"error", "Too many or oversized backup exclusions"}};
            excluded.append(row.toString());
          }
          config["excluded"] = excluded;
          config["oneFileSystem"] = args["oneFileSystem"].toBool();
          config["excludeCaches"] = args["excludeCaches"].toBool(true);
          config["limitKiB"] = qBound(0, args["limitKiB"].toInt(), 1048576);
          config["minFreeMiB"] =
              qBound(0, args["minFreeMiB"].toInt(256), 1048576);
          const auto compression = args["compression"].toString("auto");
          if (!QStringList{"auto", "off", "fastest", "better", "max"}.contains(
                  compression))
            return QJsonObject{
                {"error", "Choose a supported compression mode"}};
          config["compression"] = compression;
          auto password = args["password"].toString().toUtf8();
          if (!password.isEmpty()) {
            if (QFileInfo::exists(repository + "/config")) {
              auto env = hics::util::applicationEnvironment();
              env.insert("RESTIC_PASSWORD", QString::fromUtf8(password));
              QProcess verify;
              verify.setProcessEnvironment(env);
              verify.start("restic", {"--repo", repository, "cat", "config"});
              if (!verify.waitForStarted(5000) ||
                  !verify.waitForFinished(15000) ||
                  verify.exitStatus() != QProcess::NormalExit ||
                  verify.exitCode() != 0) {
                verify.kill();
                verify.waitForFinished(1000);
                password.fill('\0');
                return QJsonObject{
                    {"error", "Cannot unlock this repository with the supplied "
                              "password; the saved credential was kept"}};
              }
            }

            GError *error = nullptr;
            auto repo = repository.toUtf8();
            bool ok = secret_password_store_sync(
                &schema, SECRET_COLLECTION_DEFAULT, "hics backup repository",
                password.constData(), nullptr, &error, "repository",
                repo.constData(), nullptr);
            password.fill('\0');
            if (!ok) {
              if (error)
                g_error_free(error);
              return QJsonObject{
                  {"error", "Cannot save the backup password in your keyring"}};
            }
          }
          writeJson(file, config);
          return config;
        }
        if (config.isEmpty())
          return QJsonObject{
              {"error", "Configure a repository and its password first"}};
        const auto repo = config["repository"].toString();
        if (!QFileInfo(QFileInfo(repo).absolutePath()).isDir())
          return QJsonObject{{"error", "The backup disk is not connected"}};
        QStorageInfo storage(
            QFileInfo::exists(repo) ? repo : QFileInfo(repo).absolutePath());
        if (!storage.isValid() || !storage.isReady() ||
            (config["deviceUuid"].toString().isEmpty()
                 ? QString::fromLatin1(storage.device().toBase64()) !=
                       config["device"].toString()
                 : diskUuid(storage) != config["deviceUuid"].toString()) ||
            storage.rootPath() != config["mount"].toString())
          return QJsonObject{{"error", "The configured backup disk is not "
                                       "mounted at its original location"}};
        GError *error = nullptr;
        auto bytes = repo.toUtf8();
        auto *password = secret_password_lookup_sync(
            &schema, nullptr, &error, "repository", bytes.constData(), nullptr);
        if (!password) {
          if (error)
            g_error_free(error);
          return QJsonObject{
              {"error",
               "Unlock your keyring or save the repository password again"}};
        }
        auto env = hics::util::applicationEnvironment();
        env.insert("RESTIC_PASSWORD", QString::fromUtf8(password));
        secret_password_free(password);
        QStringList options{"--repo", repo, "--json"};
        if (config["limitKiB"].toInt() > 0)
          options << "--limit-upload"
                  << QString::number(config["limitKiB"].toInt())
                  << "--limit-download"
                  << QString::number(config["limitKiB"].toInt());

        if (op == "backup.init")
          options << "init";
        else if (op == "backup.run") {
          if (storage.bytesAvailable() <
              qint64(config["minFreeMiB"].toInt(256)) * 1024 * 1024)
            return QJsonObject{{"error", "The backup disk has less free space "
                                         "than the configured minimum"}};
          options << "--compression" << config["compression"].toString("auto")
                  << "backup";
          if (config["oneFileSystem"].toBool())
            options << "--one-file-system";
          if (config["excludeCaches"].toBool(true))
            options << "--exclude-caches";
          for (const auto &value : config["excluded"].toArray())
            options << "--exclude" << value.toString();
          options << "--";
          for (const auto &folder : config["folders"].toArray())
            options << folder.toString();
        } else if (op == "backup.snapshots")
          options << "snapshots";
        else if (op == "backup.check")
          options << "check";
        else if (op == "backup.files") {
          const auto snapshot = args["snapshot"].toString();
          if (!QRegularExpression("^[a-fA-F0-9]{8,64}$")
                   .match(snapshot)
                   .hasMatch())
            return QJsonObject{{"error", "Select a snapshot ID"}};
          const auto folder = QDir::cleanPath(args["folder"].toString("/"));
          if (!folder.startsWith('/'))
            return QJsonObject{
                {"error", "Choose a folder inside the snapshot"}};
          options << "ls" << snapshot << folder;
        } else if (op == "backup.restore") {
          const auto snapshot = args["snapshot"].toString();
          if (!QRegularExpression("^[a-fA-F0-9]{8,64}$")
                   .match(snapshot)
                   .hasMatch())
            return QJsonObject{{"error", "Select a snapshot ID"}};
          const auto target = QDir::cleanPath(args["target"].toString());
          if (!QFileInfo(target).isAbsolute() || QFileInfo::exists(target))
            return QJsonObject{
                {"error", "Restore into a new, separate directory to protect "
                          "existing files"}};
          options << "restore" << snapshot << "--target" << target
                  << "--overwrite" << "never";
          auto include = args["include"].toString();
          if (args["literal"].toBool()) {
            QString escaped;
            for (const auto ch : include) {
              if (QString("\\*?[]").contains(ch))
                escaped += '\\';
              escaped += ch;
            }
            include = escaped;
          }

          if (!include.isEmpty())
            options << "--include" << include;
        } else
          return QJsonObject{{"error", "Unknown backup operation"}};
        QProcess process;
        process.setProcessEnvironment(env);
        env.remove("RESTIC_PASSWORD");
        process.start("restic", options);
        if (!process.waitForStarted(5000))
          return QJsonObject{{"error", process.errorString()}};
        QByteArray output, errors, pending;
        QJsonArray listing;
        bool listTruncated = false;
        QElapsedTimer timer;
        timer.start();
        auto readOutput = [&] {
          auto bytes = process.readAllStandardOutput();
          if (op == "backup.files") {
            pending += bytes;
            int end = 0;
            while ((end = pending.indexOf('\n')) >= 0) {
              const auto line = pending.left(end);
              pending.remove(0, end + 1);
              const auto node = QJsonDocument::fromJson(line).object();
              if (node["struct_type"].toString() == "node" ||
                  node["message_type"].toString() == "node") {
                if (listing.size() < 1000)
                  listing.append(QJsonObject{{"path", node["path"]},
                                             {"name", node["name"]},
                                             {"type", node["type"]},
                                             {"size", node["size"]}});
                else
                  listTruncated = true;
              }
            }
            if (pending.size() > 1024 * 1024)
              process.kill();
            return;
          }
          if (op != "backup.run") {
            output += bytes;
            return;
          }
          pending += bytes;
          int end = 0;
          while ((end = pending.indexOf('\n')) >= 0) {
            const auto line = pending.left(end);
            pending.remove(0, end + 1);
            const auto value = QJsonDocument::fromJson(line).object();
            if (value["message_type"].toString() == "status") {
              const auto fraction = value["percent_done"].toDouble(-1);
              QMetaObject::invokeMethod(
                  this,
                  [this, job, fraction] {
                    if (!job->finished) {
                      job->progress = qBound(0.0, fraction, 1.0);
                      publish();
                    }
                  },
                  Qt::QueuedConnection);
            } else
              output = line;
          }
          if (pending.size() > 1024 * 1024)
            process.kill();
        };
        while (process.state() != QProcess::NotRunning) {
          process.waitForReadyRead(100);
          readOutput();
          errors += process.readAllStandardError();
          if (output.size() > 2 * 1024 * 1024 || errors.size() > 65536 ||
              timer.elapsed() > 3600000 || cancel->load()) {
            process.terminate();
            if (!process.waitForFinished(3000)) {
              process.kill();
              process.waitForFinished();
            }
            return QJsonObject{
                {"error", cancel->load()
                              ? "Backup operation cancelled"
                              : "Backup exceeded its time or output limit"}};
          }
        }
        readOutput();
        errors += process.readAllStandardError();
        if (process.exitStatus() != QProcess::NormalExit ||
            process.exitCode() != 0)
          return QJsonObject{
              {"error",
               QString::fromUtf8(errors.left(65536)).trimmed().isEmpty()
                   ? QString("Restic failed (%1)").arg(process.exitCode())
                   : QString::fromUtf8(errors.left(65536))}};
        if (op == "backup.files")
          return QJsonObject{{"items", listing}, {"limited", listTruncated}};
        const auto document = QJsonDocument::fromJson(output);
        if (document.isArray())
          return QJsonObject{{"items", document.array()}};
        if (document.isObject())
          return document.object();
        return QJsonObject{{"ok", true},
                           {"output", QString::fromUtf8(output.left(65536))}};
      },
      op != "backup.config" && op != "backup.configure");
}
void Service::scheduledBackups() {
  const auto config = readJson(directory + "/backup.json");
  const int hours = config["intervalHours"].toInt();
  if (hours <= 0 || stopping)
    return;
  for (const auto &job : jobs)
    if (job->operation == "backup.run" && !job->finished)
      return;
  const auto state = readJson(directory + "/backup-schedule.json");
  const auto now = QDateTime::currentSecsSinceEpoch();
  if (now - state["lastAttempt"].toInteger() < qint64(hours) * 3600)
    return;
  try {
    writeJson(directory + "/backup-schedule.json", {{"lastAttempt", now}});
    enqueue("backup.run", "{}");
  } catch (const std::exception &) {
  }
}
} // namespace HicsDesktop
