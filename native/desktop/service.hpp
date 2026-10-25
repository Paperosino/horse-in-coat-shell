#pragma once
#include <QDBusContext>
#include <QHash>
#include <QJsonObject>
#include <QObject>
#include <QProcess>
#include <QSharedPointer>
#include <QThreadPool>
#include <QTimer>
#include <atomic>
#include <functional>
namespace HicsDesktop {
QString encode(const QJsonObject &);
QJsonObject readJson(const QString &);
void writeJson(const QString &, const QJsonObject &);
struct CommandResult {
  int exitCode = -1;
  QByteArray output, error;
  bool timeout = false;
};
CommandResult command(const QString &, const QStringList &, int timeout = 15000,
                      int limit = 1024 * 1024);
struct Job {
  QString id, operation, phase = "queued", error, description;
  QJsonObject arguments, result;
  qint64 created = 0, finished = 0, order = 0;
  double progress = -1;
  bool cancellable = false, retryable = false, notify = false,
       transient = false, seen = false;
  QString producer;
  qint64 producerPid = 0;
  QByteArray producerStart;
  QProcess *process = nullptr;
  QByteArray output, errorOutput;
  std::shared_ptr<std::atomic_bool> cancel =
      std::make_shared<std::atomic_bool>(false);
  QJsonObject metadata() const;
};
class Service : public QObject, protected QDBusContext {
  Q_OBJECT
  Q_CLASSINFO("D-Bus Interface", "org.hics.Desktop1")
public:
  explicit Service(QObject *parent = nullptr);
  ~Service() override;
  void stop();
  void jobProgress(const QSharedPointer<Job> &job, double progress);
  void finish(const QSharedPointer<Job> &, QJsonObject result = {},
              QString error = {});
  void worker(const QSharedPointer<Job> &, std::function<QJsonObject()>,
              bool cancellable = false);
  void process(const QSharedPointer<Job> &, const QString &,
               const QStringList &, bool cancellable = true, int timeout = 0);
  void root(const QSharedPointer<Job> &, const QString &, const QString &,
            const QJsonObject &);
  const QString directory;
public slots:
  QString Start(const QString &operation, const QString &arguments);
  QString Status() const;
  QString Result(const QString &id) const;
  bool Cancel(const QString &id);
  bool Acknowledge(const QString &id);
  QString Retry(const QString &id);
  QString Report(const QString &source, const QString &operation,
                 const QString &phase, double progress, qint64 owner,
                 const QString &error);
signals:
  void Changed(const QString &state);
  void CancelRequested(const QString &id);
  void Completed(const QString &id, const QString &result);

private:
  bool permitted() const;
  QString enqueue(const QString &, const QString &);
  void scheduledBackups();
  void scheduledSearch();
  void monitorSystemJob(const QSharedPointer<Job> &, const QString &);
  void dispatch(const QSharedPointer<Job> &);
  void publish();
  void persist();
  QHash<QString, QSharedPointer<Job>> jobs;
  QThreadPool pool;
  QTimer updates, schedule, producers, journal, reap;
  bool stopping = false;
  QJsonObject comfortState;
  QTimer comfortDeadline;
  void initComfort();
  void updateComfort();
  void comfort(const QSharedPointer<Job> &);
  void integration(const QSharedPointer<Job> &);
  void applications(const QSharedPointer<Job> &);
  void keyring(const QSharedPointer<Job> &);
  void backup(const QSharedPointer<Job> &);
  void search(const QSharedPointer<Job> &);
  void diagnostics(const QSharedPointer<Job> &);
  void transfer(const QSharedPointer<Job> &);
  void input(const QSharedPointer<Job> &);
};
} // namespace HicsDesktop
