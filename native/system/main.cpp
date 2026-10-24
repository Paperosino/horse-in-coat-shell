#include "backend.hpp"
#include "admission.hpp"
#include "shutdown.hpp"
#include <QCoreApplication>
#include <QDBusConnectionInterface>
#include <QDBusContext>
#include <QDBusMessage>
#include <QDBusReply>
#include <QDBusServiceWatcher>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QRunnable>
#include <QTextStream>
#include <QThreadPool>
#include <QTimer>
#include <memory>
#include <cstdlib>
#include <systemd/sd-daemon.h>

class Broker final : public QObject, protected QDBusContext {
  Q_OBJECT
  Q_CLASSINFO("D-Bus Interface", "org.hics.System1")
public:
  explicit Broker(const QDBusConnection& bus) : m_watch(this) {
    m_pool.setMaxThreadCount(4);
    m_clock.start();
    m_watch.setConnection(bus);
    m_watch.setWatchMode(QDBusServiceWatcher::WatchForUnregistration);
    connect(&m_watch, &QDBusServiceWatcher::serviceUnregistered, this, [this](const QString& name) {
      m_uids.remove(name); m_admission->disconnected(name); m_watch.removeWatchedService(name);
    });
    m_draining.setInterval(20);
    connect(&m_draining, &QTimer::timeout, this, [this] {
      if (!m_admission->pending()) QCoreApplication::quit();
    });
  }
  void stop() {
    if (m_admission->stopping()) return;
    m_admission->stop();
    sd_notify(0, "STOPPING=1\nSTATUS=Finishing pending settings requests");
    m_draining.start();
    // Never destroy Qt/DBus state underneath a running job. Queued jobs return
    // shutdown errors; after the grace period the OS closes the process intact.
    // Mutations run in CUPS, system daemons or separate privileged workers.
    QTimer::singleShot(5000, this, [state = m_admission] {
      if (state->pending()) {
        QTextStream(stderr) << "hics: shutdown grace expired; external settings operations may still be finishing" << Qt::endl;
        ::_exit(EXIT_SUCCESS);
      }
    });
  }
private:
  QThreadPool m_pool; // destroyed last, after every worker has finished
  std::shared_ptr<System::Admission> m_admission = std::make_shared<System::Admission>();
  QElapsedTimer m_clock;
  QHash<QString, uint> m_uids;
  QDBusServiceWatcher m_watch;
  QTimer m_draining;
  QString submit(const QString &domain, const QString &op, const QString &raw, bool write) {
    if (!calledFromDBus()) return System::encode({{"error", "D-Bus caller required"}, {"code", "denied"}});
    if (domain.size() > 32 || op.size() > 32 || raw.size() > 16384 || raw.toUtf8().size() > 16384)
      return System::encode({{"error", "Request is too large"}, {"code", "invalid"}});
    if (m_admission->stopping()) return System::encode({{"error", "System settings are stopping"}, {"code", "shutting_down"}});
    auto request = message(); auto conn = connection(); auto sender = request.service();
    uint user;
    if (const auto it = m_uids.constFind(sender); it != m_uids.cend()) user = *it;
    else {
      if (m_uids.size() >= 1024) {
        const auto old = m_uids.begin().key();
        m_uids.remove(old); m_watch.removeWatchedService(old);
      }
      auto uid = conn.interface()->serviceUid(sender);
      if (!uid.isValid()) return System::encode({{"error", "Unknown caller"}, {"code", "denied"}});
      user = uid.value(); m_uids.insert(sender, user); m_watch.addWatchedService(sender);
    }
    const auto decision = m_admission->reserve(user, sender, m_clock.elapsed());
    if (decision == System::Admission::Result::RateLimited)
      return System::encode({{"error", "Too many settings requests; retry shortly"}, {"code", "rate_limited"}});
    if (decision != System::Admission::Result::Allowed)
      return System::encode({{"error", "System settings are busy; retry shortly"}, {"code", "busy"}});
    QJsonParseError error;
    const auto doc = QJsonDocument::fromJson(raw.toUtf8(), &error);
    if (write && (error.error != QJsonParseError::NoError || !doc.isObject())) {
      m_admission->finish(user, sender);
      return System::encode({{"error", "Invalid request"}, {"code", "invalid"}});
    }
    setDelayedReply(true);
    auto state = m_admission;
    m_pool.start(QRunnable::create([state, conn, request, sender, user, domain, op, options = doc.object(), write] {
      struct Complete { std::shared_ptr<System::Admission> state; uint uid; QString sender; ~Complete() { state->finish(uid, sender); } } complete{state, user, sender};
      QJsonObject result;
      try {
        if (state->stopping()) throw System::Failure("shutting_down", "System settings are stopping");
        if (write) {
          System::validate(domain, op, options);
          if (!(domain == "printers" && op == "cancel-job")) System::authorize(sender, "org.hics.system." + domain, user);
          if (state->stopping()) throw System::Failure("shutting_down", "System settings are stopping");
          System::apply(domain, op, options, user);
        }
        result = System::status(domain, user);
      } catch (const std::exception &e) { result = System::failure(e); }
      conn.send(request.createReply(System::encode(result)));
    }));
    return {};
  }
public slots:
  QString Status(const QString &domain) { return submit(domain, {}, "{}", false); }
  QString Apply(const QString &domain, const QString &operation, const QString &options) { return submit(domain, operation, options, true); }
};
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  auto bus = QDBusConnection::systemBus();
  Broker broker(bus);
  System::ShutdownSignals shutdownSignals(&broker, [&broker] { broker.stop(); });
  if (!bus.isConnected() || !bus.registerService(System::Service) ||
      !bus.registerObject(System::Path, &broker, QDBusConnection::ExportAllSlots)) {
    QTextStream(stderr) << bus.lastError().message() << Qt::endl; return 1;
  }
  sd_notify(0, "READY=1\nSTATUS=System settings broker ready");
  uint64_t watchdogUsec = 0;
  QTimer watchdog;
  if (sd_watchdog_enabled(0, &watchdogUsec) > 0) {
    watchdog.setInterval(int(qBound<uint64_t>(1, watchdogUsec / 2000, 10000)));
    QObject::connect(&watchdog, &QTimer::timeout, &app, [] { sd_notify(0, "WATCHDOG=1"); });
    watchdog.start();
  }
  return app.exec();
}
#include "main.moc"
