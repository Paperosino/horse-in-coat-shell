#include "backend.hpp"
#include <QCoreApplication>
#include <QDBusConnectionInterface>
#include <QDBusContext>
#include <QDBusMessage>
#include <QDBusReply>
#include <QJsonDocument>
#include <QRunnable>
#include <QSemaphore>
#include <QTextStream>
#include <QThreadPool>
class Broker final : public QObject, protected QDBusContext {
  Q_OBJECT
  Q_CLASSINFO("D-Bus Interface", "org.hics.System1")
  QSemaphore capacity{16};
  QString submit(const QString &domain, const QString &op, const QString &raw,
                 bool write) {
    if (!calledFromDBus())
      return System::encode(
          {{"error", "D-Bus caller required"}, {"code", "denied"}});
    auto request = message();
    auto conn = connection();
    auto sender = request.service();
    auto uid = conn.interface()->serviceUid(sender);
    if (!uid.isValid())
      return System::encode({{"error", "Unknown caller"}, {"code", "denied"}});
    if (domain.size() > 32 || op.size() > 32 || raw.toUtf8().size() > 16384)
      return System::encode(
          {{"error", "Request is too large"}, {"code", "invalid"}});
    QJsonParseError error;
    auto doc = QJsonDocument::fromJson(raw.toUtf8(), &error);
    if (write && (error.error != QJsonParseError::NoError || !doc.isObject()))
      return System::encode(
          {{"error", "Invalid request"}, {"code", "invalid"}});
    if (!capacity.tryAcquire())
      return System::encode(
          {{"error", "System settings are busy"}, {"code", "busy"}});
    setDelayedReply(true);
    QThreadPool::globalInstance()->start(
        QRunnable::create([this, conn, request, sender, user = uid.value(),
                           domain, op, options = doc.object(), write] {
          QJsonObject result;
          try {
            if (write) {
              System::validate(domain, op, options);
              if (!(domain == "printers" && op == "cancel-job"))
                System::authorize(sender, "org.hics.system." + domain,
                                  user);
              System::apply(domain, op, options, user);
            }
            result = System::status(domain, user);
          } catch (const std::exception &e) {
            result = System::failure(e);
          }
          conn.send(request.createReply(System::encode(result)));
          capacity.release();
        }));
    return {};
  }
public slots:
  QString Status(const QString &domain) {
    return submit(domain, {}, "{}", false);
  }
  QString Apply(const QString &domain, const QString &operation,
                const QString &options) {
    return submit(domain, operation, options, true);
  }
};
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  QThreadPool::globalInstance()->setMaxThreadCount(4);
  auto bus = QDBusConnection::systemBus();
  Broker broker;
  if (!bus.isConnected() || !bus.registerService(System::Service) ||
      !bus.registerObject(System::Path, &broker,
                          QDBusConnection::ExportAllSlots)) {
    QTextStream(stderr) << bus.lastError().message() << Qt::endl;
    return 1;
  }
  return app.exec();
}
#include "main.moc"
