#include "service.hpp"
#include "../system/game_activity.hpp"
#include "util/applicationenv.hpp"
#include <QCoreApplication>
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusObjectPath>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QFutureWatcher>
#include <QJsonArray>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QSaveFile>
#include <QStandardPaths>
#include <QUuid>
#include <QtConcurrent>
#include <cmath>
#include <unistd.h>
namespace HicsDesktop {
QString encode(const QJsonObject &value) {
  return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
QJsonObject readJson(const QString &path) {
  QFile file(path);
  if (!file.open(QIODevice::ReadOnly) || file.size() > 2 * 1024 * 1024)
    return {};
  return QJsonDocument::fromJson(file.readAll()).object();
}
void writeJson(const QString &path, const QJsonObject &value) {
  QDir().mkpath(QFileInfo(path).absolutePath());
  QSaveFile file(path);
  const auto bytes = QJsonDocument(value).toJson();
  if (!file.open(QIODevice::WriteOnly) ||
      !file.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner) ||
      file.write(bytes) != bytes.size() || !file.commit())
    throw std::runtime_error("Cannot save desktop service state");
}
CommandResult command(const QString &program, const QStringList &args,
                      int timeout, int limit) {
  CommandResult result;
  QProcess p;
  p.setProcessEnvironment(hics::util::applicationEnvironment());
  p.start(program, args);
  if (!p.waitForStarted(5000)) {
    result.error = p.errorString().toUtf8();
    return result;
  }
  QElapsedTimer clock;
  clock.start();
  auto drain = [&] {
    result.output += p.readAllStandardOutput();
    result.error += p.readAllStandardError();
  };
  while (p.state() != QProcess::NotRunning && clock.elapsed() < timeout) {
    p.waitForReadyRead(100);
    drain();
    if (result.output.size() + result.error.size() > limit) {
      p.kill();
      p.waitForFinished();
      result.error = "Command output exceeded its limit";
      result.output.clear();
      return result;
    }
  }
  if (p.state() != QProcess::NotRunning) {
    p.kill();
    p.waitForFinished();
    result.timeout = true;
  }
  drain();
  result.exitCode = result.timeout                           ? -1
                    : p.exitStatus() == QProcess::NormalExit ? p.exitCode()
                                                             : -1;
  return result;
}
QJsonObject Job::metadata() const {
  return {{"id", id},
          {"operation", operation},
          {"description", description},
          {"phase", phase},
          {"progress", progress},
          {"error", error.isEmpty()
                        ? QString()
                        : QString("The operation failed; open its details")},
          {"created", created},
          {"order", order},
          {"finished", finished},
          {"cancellable", cancellable},
          {"retryable", retryable},
          {"notify", notify},
          {"seen", seen},
          {"producer", producer},
          {"producerPid", producerPid},
          {"producerStart", QString::fromLatin1(producerStart)}};
}
Service::Service(QObject *parent)
    : QObject(parent), directory(QStandardPaths::writableLocation(
                                     QStandardPaths::GenericStateLocation) +
                                 "/hics/desktop") {
  QDir().mkpath(directory);
  QFile::setPermissions(directory, QFileDevice::ReadOwner |
                                       QFileDevice::WriteOwner |
                                       QFileDevice::ExeOwner);
  pool.setMaxThreadCount(2);
  pool.setExpiryTimeout(1000);
  const auto previous = readJson(directory + "/jobs.json");
  for (const auto &row : previous["jobs"].toArray()) {
    const auto o = row.toObject();
    auto job = QSharedPointer<Job>::create();
    job->id = o["id"].toString();
    job->operation = o["operation"].toString();
    job->description = o["description"].toString();
    job->created = o["created"].toInteger();
    job->order = o["order"].toInteger(job->created * 1000);
    job->finished = o["finished"].toInteger();
    job->phase = o["phase"].toString();
    job->error = o["error"].toString();
    job->seen = o["seen"].toBool(true);
    job->producer = o["producer"].toString();
    job->producerPid = o["producerPid"].toInteger();
    job->producerStart = o["producerStart"].toString().toLatin1();
    job->result = o["result"].toObject();
    if (job->result.isEmpty())
      job->result = {
          {"message",
           "Detailed output was not retained across the service restart"}};
    job->retryable = QStringList{"search.index", "backup.run", "backup.check",
                                 "backup.snapshots", "diagnostics.check"}
                         .contains(job->operation);
    if (!QStringList{"completed", "failed", "cancelled", "interrupted"}
             .contains(job->phase)) {
      if (job->producerPid > 0 &&
          QFileInfo("/proc/" + QString::number(job->producerPid)).ownerId() ==
              ::getuid() &&
          hics::game::processStart(
              "/proc/" + QString::number(job->producerPid) + "/stat") ==
              job->producerStart) {
        job->phase = "running";
        job->error.clear();
        jobs.insert(job->id, job);
        continue;
      }
      job->phase = "interrupted";
      job->finished = QDateTime::currentSecsSinceEpoch();
      job->error = "The desktop service stopped before the result was "
                   "recorded. Check the operation before retrying.";
    }
    jobs.insert(job->id, job);
  }
  updates.setSingleShot(true);
  updates.setInterval(80);
  reap.setInterval(1000);
  connect(&reap, &QTimer::timeout, this, [this] {
    const auto now = QDateTime::currentSecsSinceEpoch();
    bool remaining = false;
    for (auto it = jobs.begin(); it != jobs.end();) {
      const auto &job = it.value();
      if (job->transient && job->finished && now - job->finished >= 10) {
        it = jobs.erase(it);
        continue;
      }
      remaining |= job->transient && job->finished;
      ++it;
    }
    if (!remaining)
      reap.stop();
  });
  journal.setSingleShot(true);
  journal.setInterval(2000);
  connect(&journal, &QTimer::timeout, this, [this] { persist(); });
  connect(&updates, &QTimer::timeout, this, [this] {
    emit Changed(Status());
    if (!journal.isActive())
      journal.start();
  });
  producers.setInterval(2000);
  connect(&producers, &QTimer::timeout, this, [this] {
    bool live = false;
    for (const auto &job : jobs)
      if (!job->finished && job->producerPid) {
        live = true;
        const auto start = hics::game::processStart(
            "/proc/" + QString::number(job->producerPid) + "/stat");
        if (start.isEmpty() || start != job->producerStart)
          finish(
              job, {},
              "The application stopped before reporting the operation result");
      }
    if (!live)
      producers.stop();
  });
  for (const auto &job : jobs)
    if (!job->finished && job->producerPid) {
      producers.start();
      break;
    }
  schedule.setInterval(60000);
  schedule.start();
  connect(&schedule, &QTimer::timeout, this, [this] {
    scheduledBackups();
    scheduledSearch();
  });
}
Service::~Service() {
  for (auto job : jobs) {
    job->cancel->store(true);
    if (job->process) {
      job->process->kill();
      job->process->waitForFinished(1000);
    }
  }
  pool.clear();
  pool.waitForDone();
}
bool Service::permitted() const {
  if (!calledFromDBus())
    return qEnvironmentVariableIntValue("HICS_DESKTOP_TEST") == 1;
  const auto uid = connection().interface()->serviceUid(message().service());
  return uid.isValid() && uid.value() == ::getuid();
}
void Service::stop() {
  if (stopping)
    return;
  stopping = true;
  for (auto job : jobs)
    if (job->cancellable) {
      job->cancel->store(true);
      if (job->process)
        job->process->terminate();
    }
  persist();
  QTimer::singleShot(2500, QCoreApplication::instance(), [] { ::_exit(0); });
}
QString Service::Start(const QString &operation, const QString &raw) {
  if (!permitted())
    return encode({{"error", "D-Bus caller must own this session"}});
  return enqueue(operation, raw);
}
QString Service::enqueue(const QString &operation, const QString &raw) {
  if (stopping || raw.toUtf8().size() > 65536 || operation.size() > 64)
    return encode(
        {{"error", "Desktop service is busy or request is too large"}});
  int active = 0;
  for (auto job : jobs)
    if (!job->finished)
      ++active;
  if (active >= 16)
    return encode({{"error", "Too many pending desktop operations"}});
  QJsonParseError parse;
  const auto doc = QJsonDocument::fromJson(raw.toUtf8(), &parse);
  if (parse.error != QJsonParseError::NoError || !doc.isObject())
    return encode({{"error", "Invalid desktop request"}});
  auto job = QSharedPointer<Job>::create();
  job->id = QUuid::createUuid().toString(QUuid::Id128);
  job->operation = operation;
  job->arguments = doc.object();
  job->created = QDateTime::currentSecsSinceEpoch();
  job->order = QDateTime::currentMSecsSinceEpoch();
  job->description = operation;
  job->transient =
      operation.startsWith("input.") || QStringList{"apps.apparmor-read",
                                                    "keyring.manager",
                                                    "backup.timeshift-manager",
                                                    "backup.snapper-manager",
                                                    "backup.files",
                                                    "backup.snapshots",
                                                    "search.query",
                                                    "search.recent",
                                                    "search.config",
                                                    "backup.config",
                                                    "apps.info",
                                                    "apps.apparmor-status",
                                                    "keyring.status",
                                                    "input.status"}
                                            .contains(operation);
  job->notify = QStringList{"backup.init", "backup.run", "backup.restore",
                            "backup.check", "apps.remove"}
                    .contains(operation);
  job->retryable = QStringList{"search.index", "backup.run", "backup.check",
                               "backup.snapshots", "diagnostics.check"}
                       .contains(operation);
  jobs.insert(job->id, job);
  if (!job->transient)
    publish();
  QTimer::singleShot(0, this, [this, job] { dispatch(job); });
  return encode({{"id", job->id}});
}
QString Service::Status() const {
  QJsonArray list;
  auto values = jobs.values();
  std::sort(values.begin(), values.end(), [](auto a, auto b) {
    return a->order == b->order ? a->id > b->id : a->order > b->order;
  });
  for (auto job : values)
    if (!job->transient)
      list.append(job->metadata());
  return encode({{"jobs", list}});
}
QString Service::Result(const QString &id) const {
  if (!permitted())
    return encode({{"error", "Access denied"}});
  const auto job = jobs.value(id);
  if (!job)
    return encode({{"error", "Operation is no longer available"}});
  return encode({{"id", id},
                 {"finished", job->finished > 0},
                 {"error", job->error},
                 {"result", job->result}});
}
bool Service::Acknowledge(const QString &id) {
  if (!permitted())
    return false;
  bool changed = false;
  for (const auto &job : jobs)
    if (job->finished && !job->seen && (id.isEmpty() || job->id == id)) {
      job->seen = true;
      changed = true;
    }
  if (changed)
    publish();
  return changed;
}
bool Service::Cancel(const QString &id) {
  if (!permitted())
    return false;
  auto job = jobs.value(id);
  if (!job || job->finished || !job->cancellable)
    return false;
  job->cancel->store(true);
  emit CancelRequested(id);
  if (job->process) {
    job->process->terminate();
    QTimer::singleShot(3000, job->process, [process = job->process] {
      if (process->state() != QProcess::NotRunning)
        process->kill();
    });
  }
  publish();
  return true;
}
QString Service::Report(const QString &source, const QString &operation,
                        const QString &phase, double progress, qint64 owner,
                        const QString &error) {
  if (!permitted() ||
      !QRegularExpression("^[a-zA-Z0-9_.-]{1,80}$").match(source).hasMatch() ||
      !QStringList{"update.install", "maintenance.cleanup", "transfer.send",
                   "transfer.copy", "maintenance.disk"}
           .contains(operation) ||
      !QStringList{"running", "completed", "failed", "cancelled"}.contains(
          phase) ||
      !std::isfinite(progress))
    return encode({{"error", "Invalid operation report"}});
  const auto sender = connection().interface()->servicePid(message().service());
  if (!sender.isValid())
    return encode({{"error", "Cannot identify the reporting process"}});
  qint64 cursor = sender.value();
  bool ancestor = false;
  for (int i = 0; i < 12 && cursor > 0; ++i) {
    if (cursor == owner) {
      ancestor = true;
      break;
    }
    QFile status("/proc/" + QString::number(cursor) + "/status");
    if (!status.open(QIODevice::ReadOnly))
      break;
    const auto text = status.read(32768);
    const auto match = QRegularExpression(R"((?:^|\n)PPid:\s+(\d+))")
                           .match(QString::fromLatin1(text));
    if (!match.hasMatch())
      break;
    cursor = match.captured(1).toLongLong();
  }
  const auto proc = "/proc/" + QString::number(owner);
  if (!ancestor || QFileInfo(proc).ownerId() != ::getuid())
    return encode(
        {{"error", "The report must belong to this process or its parent"}});
  const auto identity = QString::number(owner) + ":" + source;
  QSharedPointer<Job> job;
  for (const auto &candidate : jobs)
    if (candidate->producer == identity && !candidate->finished)
      job = candidate;
  if (!job) {
    if (phase != "running")
      return encode({{"error", "No matching active operation"}});
    int active = 0;
    for (const auto &item : jobs)
      if (!item->finished)
        ++active;
    if (active >= 16)
      return encode({{"error", "Too many active operations"}});
    job = QSharedPointer<Job>::create();
    job->id = QUuid::createUuid().toString(QUuid::Id128);
    job->operation = operation;
    job->description = operation;
    job->producer = identity;
    job->producerPid = owner;
    job->producerStart = hics::game::processStart(proc + "/stat");
    job->created = QDateTime::currentSecsSinceEpoch();
    job->order = QDateTime::currentMSecsSinceEpoch();
    jobs.insert(job->id, job);
  }
  job->progress = qBound(-1.0, progress, 1.0);
  job->phase = phase;
  if (phase != "running") {
    if (phase == "cancelled")
      job->cancel->store(true);
    finish(job, {},
           phase == "failed"
               ? (error.isEmpty()
                      ? QString("The operation failed; open its details")
                      : error.left(512))
               : QString());
  } else {
    producers.start();
    publish();
  }
  return encode({{"id", job->id}});
}
QString Service::Retry(const QString &id) {
  if (!permitted())
    return encode({{"error", "Access denied"}});
  auto job = jobs.value(id);
  if (!job || !job->finished || !job->retryable)
    return encode({{"error", "This operation cannot safely be retried"}});
  return Start(job->operation, encode(job->arguments));
}
void Service::jobProgress(const QSharedPointer<Job> &job, double progress) {
  if (job->finished)
    return;
  job->phase = "running";
  job->progress = qBound(-1.0, progress, 1.0);
  publish();
}
void Service::publish() {
  if (!updates.isActive())
    updates.start();
}
void Service::persist() {
  try {
    auto state = QJsonDocument::fromJson(Status().toUtf8()).object();
    auto rows = state["jobs"].toArray();
    while (rows.size() > 128)
      rows.removeLast();
    for (int i = 0; i < rows.size(); ++i) {
      auto row = rows[i].toObject();
      auto job = jobs.value(row["id"].toString());
      if (job &&
          QStringList{"search.index", "search.clear", "backup.init",
                      "backup.run", "backup.restore", "backup.check",
                      "backup.snapshots", "diagnostics.check", "apps.remove",
                      "apps.apparmor-mode", "apps.flatpak-override",
                      "apps.flatpak-reset", "apps.autostart"}
              .contains(job->operation) &&
          QJsonDocument(job->result).toJson().size() <= 65536) {
        row["result"] = job->result;
        rows[i] = row;
      }
    }
    state["jobs"] = rows;
    writeJson(directory + "/jobs.json", state);
  } catch (const std::exception &) {
  }
}
void Service::finish(const QSharedPointer<Job> &job, QJsonObject result,
                     QString error) {
  if (job->finished)
    return;
  job->result = result;
  job->error = error;
  job->phase = job->cancel->load() ? "cancelled"
               : error.isEmpty()   ? "completed"
                                   : "failed";
  job->finished = QDateTime::currentSecsSinceEpoch();
  job->cancellable = false;
  job->progress = error.isEmpty() ? 1 : job->progress;
  // Never keep passwords or arbitrary CLI output in the persisted job journal.
  job->arguments.remove("password");
  job->arguments.remove("secret");
  if (!job->retryable)
    job->arguments = QJsonObject{};
  job->output.clear();
  job->errorOutput.clear();
  if (job->notify) {
    auto message = QDBusMessage::createMethodCall(
        "org.freedesktop.Notifications", "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications", "Notify");
    message.setArguments(
        {QString("hics"), uint(0), QString("dialog-information"),
         job->phase == "completed" ? QString("Operation completed")
                                   : QString("Operation needs attention"),
         job->description, QStringList{}, QVariantMap{}, int(-1)});
    QDBusConnection::sessionBus().asyncCall(message, 5000);
  }
  emit Completed(
      job->id, encode({{"id", job->id}, {"result", result}, {"error", error}}));
  if (!job->transient)
    publish();
  if (job->transient && !reap.isActive())
    reap.start();
  int retained = 0, transient = 0;
  for (const auto &item : jobs) {
    if (item->transient)
      ++transient;
    else
      ++retained;
  }
  if (retained > 128 || transient > 256) {
    auto oldest = jobs.end();
    const bool transientLimit = transient > 256;
    for (auto it = jobs.begin(); it != jobs.end(); ++it)
      if (it.value()->finished && it.value()->transient == transientLimit &&
          it.key() != job->id &&
          (oldest == jobs.end() || it.value()->order < oldest.value()->order))
        oldest = it;
    if (oldest != jobs.end())
      jobs.erase(oldest);
  }
}
void Service::worker(const QSharedPointer<Job> &job,
                     std::function<QJsonObject()> work, bool cancellable) {
  job->phase = "running";
  job->cancellable = cancellable;
  auto *watcher = new QFutureWatcher<QJsonObject>(this);
  connect(watcher, &QFutureWatcher<QJsonObject>::finished, this,
          [this, job, watcher] {
            auto value = watcher->result();
            watcher->deleteLater();
            auto error = value.take("error").toString();
            finish(job, value, error);
          });
  watcher->setFuture(QtConcurrent::run(&pool, [work, cancel = job->cancel] {
    try {
      if (cancel->load())
        return QJsonObject{{"cancelled", true}};
      return work();
    } catch (const std::exception &e) {
      return QJsonObject{{"error", QString::fromUtf8(e.what())}};
    }
  }));
  if (!job->transient)
    publish();
}
void Service::process(const QSharedPointer<Job> &job, const QString &program,
                      const QStringList &args, bool cancellable, int timeout) {
  if (QStandardPaths::findExecutable(program).isEmpty()) {
    finish(job, {}, "Required application is not installed: " + program);
    return;
  }
  auto *p = new QProcess(this);
  job->process = p;
  job->phase = "running";
  job->cancellable = cancellable;
  auto read = [this, job, p] {
    job->output += p->readAllStandardOutput();
    job->errorOutput += p->readAllStandardError();
    if (job->output.size() > 2 * 1024 * 1024) {
      job->errorOutput = "Operation produced too much output";
      p->kill();
    }
    if (job->errorOutput.size() > 65536)
      job->errorOutput = job->errorOutput.right(65536);
    publish();
  };
  connect(p, &QProcess::readyReadStandardOutput, this, read);
  connect(p, &QProcess::readyReadStandardError, this, read);
  connect(p, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
          [this, job, p, read](int code, QProcess::ExitStatus status) {
            read();
            job->process = nullptr;
            p->deleteLater();
            QJsonParseError error;
            auto document = QJsonDocument::fromJson(job->output, &error);
            QJsonObject value;
            if (document.isObject())
              value = document.object();
            else if (document.isArray())
              value["items"] = document.array();
            else
              value["output"] = QString::fromUtf8(job->output.left(65536));
            finish(job, value,
                   code == 0 && status == QProcess::NormalExit ? QString()
                   : QString::fromUtf8(job->errorOutput).trimmed().isEmpty()
                       ? QString("Operation failed (%1)").arg(code)
                       : QString::fromUtf8(job->errorOutput));
          });
  connect(p, &QProcess::errorOccurred, this,
          [this, job, p](QProcess::ProcessError e) {
            if (e == QProcess::FailedToStart) {
              job->process = nullptr;
              finish(job, {}, p->errorString());
              p->deleteLater();
            }
          });
  p->setProcessEnvironment(hics::util::applicationEnvironment());
  p->start(program, args);
  if (timeout > 0)
    QTimer::singleShot(timeout, p, [p] {
      if (p->state() != QProcess::NotRunning)
        p->kill();
    });
  publish();
}
void Service::root(const QSharedPointer<Job> &job, const QString &domain,
                   const QString &op, const QJsonObject &args) {
  job->phase = "authorizing";
  job->cancellable = false;
  auto call = QDBusMessage::createMethodCall(
      "org.hics.System1", "/org/hics/System1", "org.hics.System1", "Apply");
  call.setArguments({domain, op, encode(args)});
  auto *watcher = new QDBusPendingCallWatcher(
      QDBusConnection::systemBus().asyncCall(call, 960000), this);
  connect(
      watcher, &QDBusPendingCallWatcher::finished, this,
      [this, job, watcher, domain, op, args] {
        QDBusPendingReply<QString> reply = *watcher;
        watcher->deleteLater();
        if (reply.isError()) {
          finish(job, {}, reply.error().message());
          return;
        }
        auto value = QJsonDocument::fromJson(reply.value().toUtf8()).object();
        auto error = value.take("error").toString();
        if (error.isEmpty() && domain == "storage") {
          const auto unit =
              op == "clean-packages" ? QString("hics-clean-packages.service")
              : op == "clean-coredumps"
                  ? QString("hics-clean-coredumps.service")
                  : QString("hyprstack-disk-") +
                        args["path"].toString().section('/', -1) + ".service";
          job->phase = "running";
          monitorSystemJob(job, unit);
          return;
        }
        finish(job, value, error);
      });
  publish();
}
void Service::monitorSystemJob(const QSharedPointer<Job> &job,
                               const QString &unit) {
  auto call = QDBusMessage::createMethodCall(
      "org.freedesktop.systemd1", "/org/freedesktop/systemd1",
      "org.freedesktop.systemd1.Manager", "GetUnit");
  call.setArguments({unit});
  auto *lookup = new QDBusPendingCallWatcher(
      QDBusConnection::systemBus().asyncCall(call, 5000), this);
  connect(
      lookup, &QDBusPendingCallWatcher::finished, this,
      [this, job, lookup, unit] {
        QDBusPendingReply<QDBusObjectPath> reply = *lookup;
        lookup->deleteLater();
        if (reply.isError()) {
          finish(job, {},
                 "The system job result is unavailable; inspect the unit "
                 "before retrying");
          return;
        }
        auto request = QDBusMessage::createMethodCall(
            "org.freedesktop.systemd1", reply.value().path(),
            "org.freedesktop.DBus.Properties", "GetAll");
        request.setArguments({QString("org.freedesktop.systemd1.Unit")});
        auto *state = new QDBusPendingCallWatcher(
            QDBusConnection::systemBus().asyncCall(request, 5000), this);
        connect(
            state, &QDBusPendingCallWatcher::finished, this,
            [this, job, unit, state, path = reply.value().path()] {
              QDBusPendingReply<QVariantMap> value = *state;
              state->deleteLater();
              if (value.isError()) {
                finish(job, {}, value.error().message());
                return;
              }
              const auto active = value.value()["ActiveState"].toString(),
                         sub = value.value()["SubState"].toString();
              if (active == "activating" || sub == "running") {
                if (QDateTime::currentSecsSinceEpoch() - job->created > 3600) {
                  finish(job, {},
                         "The system job is still running; inspect its systemd "
                         "unit");
                  return;
                }
                QTimer::singleShot(2000, this, [this, job, unit] {
                  monitorSystemJob(job, unit);
                });
                return;
              }
              auto request = QDBusMessage::createMethodCall(
                  "org.freedesktop.systemd1", path,
                  "org.freedesktop.DBus.Properties", "GetAll");
              request.setArguments(
                  {QString("org.freedesktop.systemd1.Service")});
              auto *result = new QDBusPendingCallWatcher(
                  QDBusConnection::systemBus().asyncCall(request, 5000), this);
              connect(result, &QDBusPendingCallWatcher::finished, this,
                      [this, job, result] {
                        QDBusPendingReply<QVariantMap> value = *result;
                        result->deleteLater();
                        if (value.isError()) {
                          finish(job, {}, value.error().message());
                          return;
                        }
                        const auto status = value.value()["Result"].toString();
                        finish(job, {{"result", status}},
                               status == "success"
                                   ? QString()
                                   : QString("System operation failed: ") +
                                         status);
                      });
            });
      });
  publish();
}
void Service::dispatch(const QSharedPointer<Job> &job) {
  try {
    if (job->operation == "maintenance.disk") {
      const auto op = job->arguments["operation"].toString();
      if (!QStringList{"trim", "defragment", "clean-packages",
                       "clean-coredumps"}
               .contains(op)) {
        finish(job, {}, "Unknown disk maintenance operation");
        return;
      }
      root(job, "storage", op, job->arguments["options"].toObject());
    } else if (job->operation.startsWith("apps."))
      applications(job);
    else if (job->operation.startsWith("keyring."))
      keyring(job);
    else if (job->operation.startsWith("backup."))
      backup(job);
    else if (job->operation.startsWith("search."))
      search(job);
    else if (job->operation.startsWith("diagnostics."))
      diagnostics(job);
    else if (job->operation.startsWith("transfer."))
      transfer(job);
    else if (job->operation.startsWith("input."))
      input(job);
    else
      finish(job, {}, "Unknown desktop operation");
  } catch (const std::exception &e) {
    finish(job, {}, QString::fromUtf8(e.what()));
  }
}
} // namespace HicsDesktop
