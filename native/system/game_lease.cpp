// Per-game leases live outside the render process. EOF, game exit and shell
// crashes all release them; no polling, sudo, governor writes or global quotas.
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusUnixFileDescriptor>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSocketNotifier>
#include <QTextStream>
#include <QTimer>
#include <fcntl.h>
#include <optional>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  const auto args = app.arguments();
  bool ok = false;
  const int pid = args.value(1).toInt(&ok);
  struct stat st{};
  const auto process = QByteArray("/proc/") + QByteArray::number(pid);
  if (!ok || pid <= 1 || ::stat(process.constData(), &st) ||
      st.st_uid != getuid())
    return 2;
  const int pidfd = syscall(SYS_pidfd_open, pid, 0);
  const int selfFd = syscall(SYS_pidfd_open, getpid(), 0);
  if (selfFd < 0 || pidfd < 0)
    return 2; // Never manage a recycled PID on older kernels.
  fcntl(STDIN_FILENO, F_SETFL, fcntl(STDIN_FILENO, F_GETFL) | O_NONBLOCK);
  const auto session = QDBusConnection::sessionBus(),
             system = QDBusConnection::systemBus();
  const QString gameService = QStringLiteral("com.feralinteractive.GameMode");
  const QString gamePath = QStringLiteral("/com/feralinteractive/GameMode");
  const QString powerService =
      QStringLiteral("org.freedesktop.UPower.PowerProfiles");
  const QString powerPath =
      QStringLiteral("/org/freedesktop/UPower/PowerProfiles");
  auto call = [](const QDBusConnection &bus, const QString &service,
                 const QString &path, const QString &method,
                 const QVariantList &values) {
    auto message =
        QDBusMessage::createMethodCall(service, path, service, method);
    message.setArguments(values);
    return bus.asyncCall(message, 2000);
  };
  // GameMode 1.8+ PIDFD API orders descriptors as game, requestor.
  // Keep the same open descriptors for registration and release.
  const QVariantList gameArguments{
      QVariant::fromValue(QDBusUnixFileDescriptor(pidfd)),
      QVariant::fromValue(QDBusUnixFileDescriptor(selfFd))};
  bool stopping = false, registered = false;
  std::optional<uint> cookie;
  int pending = 0;
  auto output = [](const QString &kind, const QString &error) {
    QTextStream(stdout) << QJsonDocument(
                               QJsonObject{{QStringLiteral("lease"), kind},
                                           {QStringLiteral("error"), error}})
                               .toJson(QJsonDocument::Compact)
                        << Qt::endl;
  };
  auto release = [&] {
    if (registered) {
      call(session, gameService, gamePath,
           QStringLiteral("UnregisterGameByPIDFd"), gameArguments);
      registered = false;
    }
    if (cookie) {
      call(system, powerService, powerPath, QStringLiteral("ReleaseProfile"),
           {*cookie});
      cookie.reset();
    }
  };
  auto stop = [&] {
    if (stopping)
      return;
    stopping = true;
    release();
    // Allow already outstanding acquisitions to answer and be released.
    QTimer::singleShot(2500, &app, &QCoreApplication::quit);
    if (!pending)
      QTimer::singleShot(100, &app, &QCoreApplication::quit);
  };
  QSocketNotifier input(STDIN_FILENO, QSocketNotifier::Read),
      exited(pidfd, QSocketNotifier::Read);
  QObject::connect(&input, &QSocketNotifier::activated, &app, [&] {
    char bytes[64];
    const auto n = ::read(STDIN_FILENO, bytes, sizeof(bytes));
    if (!n) {
      input.setEnabled(false);
      stop();
    }
  });
  QObject::connect(&exited, &QSocketNotifier::activated, &app, [&] {
    exited.setEnabled(false);
    stop();
  });
  if (args.contains(QStringLiteral("--gamemode"))) {
    ++pending;
    auto *watcher = new QDBusPendingCallWatcher(
        call(session, gameService, gamePath,
             QStringLiteral("RegisterGameByPIDFd"), gameArguments),
        &app);
    QObject::connect(
        watcher, &QDBusPendingCallWatcher::finished, &app,
        [&](QDBusPendingCallWatcher *w) {
          QDBusPendingReply<int> reply = *w;
          registered = !reply.isError() && reply.value() >= 0;
          output(QStringLiteral("gamemode"),
                 registered
                     ? QString()
                     : (reply.isError()
                            ? reply.error().message()
                            : QStringLiteral("GameMode rejected the request")));
          --pending;
          w->deleteLater();
          if (stopping) {
            release();
            if (!pending)
              QTimer::singleShot(100, &app, &QCoreApplication::quit);
          }
        });
  }
  if (args.contains(QStringLiteral("--performance"))) {
    ++pending;
    auto *watcher = new QDBusPendingCallWatcher(
        call(system, powerService, powerPath, QStringLiteral("HoldProfile"),
             {QStringLiteral("performance"), QStringLiteral("Fullscreen game"),
              QStringLiteral("org.hics.Shell")}),
        &app);
    QObject::connect(
        watcher, &QDBusPendingCallWatcher::finished, &app,
        [&](QDBusPendingCallWatcher *w) {
          QDBusPendingReply<uint> reply = *w;
          if (!reply.isError())
            cookie = reply.value();
          output(QStringLiteral("power"),
                 reply.isError() ? reply.error().message() : QString());
          --pending;
          w->deleteLater();
          if (stopping) {
            release();
            if (!pending)
              QTimer::singleShot(100, &app, &QCoreApplication::quit);
          }
        });
  }
  const auto result = app.exec();
  release();
  ::close(pidfd);
  ::close(selfFd);
  return result;
}
