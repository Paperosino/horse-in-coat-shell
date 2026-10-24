// Bounded local diagnostics, invoked by ExecStopPost inside the broker sandbox.
#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QRegularExpression>
#include <QSaveFile>
#include <sys/stat.h>
#include <unistd.h>

namespace {
constexpr qint64 MaxLog = 256 * 1024;
QByteArray read(const QString &path, qint64 cap) {
  QFile file(path);
  return file.open(QIODevice::ReadOnly) ? file.read(cap) : QByteArray();
}
void write(const QString &path, const QByteArray &bytes) {
  QSaveFile file(path);
  if (!file.open(QIODevice::WriteOnly))
    return;
  file.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);
  if (file.write(bytes) == bytes.size())
    file.commit();
}
QByteArray command(const QString &executable, const QStringList &args,
                   int timeout) {
  QProcess process;
  process.setStandardErrorFile(QProcess::nullDevice());
  process.start(executable, args);
  QByteArray output;
  QElapsedTimer clock;
  clock.start();
  if (!process.waitForStarted(std::min(300, timeout)))
    return {};
  while (process.state() != QProcess::NotRunning && clock.elapsed() < timeout) {
    process.waitForReadyRead(25);
    output += process.readAllStandardOutput();
    if (output.size() > MaxLog) {
      output.truncate(MaxLog);
      break;
    }
  }
  if (process.state() != QProcess::NotRunning) {
    process.kill();
    process.waitForFinished(300);
  }
  output += process.readAllStandardOutput();
  output.truncate(MaxLog);
  return output;
}
} // namespace
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  const auto result = qEnvironmentVariable("SERVICE_RESULT");
  if (result.isEmpty() || result == QStringLiteral("success"))
    return 0;
  auto root = qEnvironmentVariable("STATE_DIRECTORY");
  if (root.isEmpty())
    root = QStringLiteral("/var/lib/hics/crashes");
  if (root.contains(':'))
    return 1;
  const auto encoded = QFile::encodeName(root);
  struct stat st{};
  if (lstat(encoded.constData(), &st) || !S_ISDIR(st.st_mode) ||
      st.st_uid != geteuid() || (st.st_mode & 0077))
    return 1;
  QDir directory(root);
  // The private root is not writable by other users. Qt removes symlinks
  // themselves and never follows them when pruning these report directories.
  auto reports = directory.entryInfoList(
      {QStringLiteral("report-*")},
      QDir::Dirs | QDir::NoDotAndDotDot | QDir::NoSymLinks, QDir::Name);
  const auto cutoff = QDateTime::currentDateTimeUtc().addDays(-7);
  while (!reports.isEmpty() &&
         (reports.size() >= 10 || reports.first().lastModified() < cutoff)) {
    QDir(reports.takeFirst().absoluteFilePath()).removeRecursively();
  }
  const auto name = QStringLiteral("report-") +
                    QDateTime::currentDateTimeUtc().toString(
                        QStringLiteral("yyyyMMddTHHmmsszzz")) +
                    QStringLiteral("-") + QString::number(getpid());
  if (!directory.mkdir(name))
    return 1;
  const auto report = directory.filePath(name);
  QFile::setPermissions(report, QFileDevice::ReadOwner |
                                    QFileDevice::WriteOwner |
                                    QFileDevice::ExeOwner);
  const auto invocation = qEnvironmentVariable("INVOCATION_ID");
  const bool validInvocation =
      QRegularExpression(QStringLiteral("^[a-fA-F0-9]{32}$"))
          .match(invocation)
          .hasMatch();
  QJsonObject metadata{
      {QStringLiteral("service"), QStringLiteral("hics-system.service")},
      {QStringLiteral("result"), result.left(64)},
      {QStringLiteral("exitCode"), qEnvironmentVariable("EXIT_CODE").left(64)},
      {QStringLiteral("exitStatus"),
       qEnvironmentVariable("EXIT_STATUS").left(64)},
      {QStringLiteral("time"),
       QDateTime::currentDateTimeUtc().toString(Qt::ISODate)}};
  write(report + QStringLiteral("/report.json"),
        QJsonDocument(metadata).toJson());
  write(report + QStringLiteral("/meminfo.txt"),
        read(QStringLiteral("/proc/meminfo"), 65536));
  write(report + QStringLiteral("/pressure.txt"),
        read(QStringLiteral("/proc/pressure/memory"), 4096));
  QStringList journal{QStringLiteral("--no-pager"),
                      QStringLiteral("--unit=hics-system.service"),
                      QStringLiteral("--since=-1min"),
                      QStringLiteral("--lines=200"),
                      QStringLiteral("--output=short-monotonic")};
  if (validInvocation)
    journal << QStringLiteral("_SYSTEMD_INVOCATION_ID=") + invocation;
  write(report + QStringLiteral("/journal.log"),
        command(QStringLiteral("journalctl"), journal, 1200));
  if (validInvocation)
    write(report + QStringLiteral("/coredump.log"),
          command(QStringLiteral("coredumpctl"),
                  {QStringLiteral("--no-pager"), QStringLiteral("info"),
                   QStringLiteral("COREDUMP_UNIT=hics-system.service"),
                   QStringLiteral("--since=-1min"), QStringLiteral("-1")},
                  1200));
  return 0;
}
