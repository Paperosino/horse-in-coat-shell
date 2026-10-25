#include "../system/shutdown.hpp"
#include "service.hpp"
#include <QCoreApplication>
#include <QDir>
#include <QDBusConnection>
#include <QDBusError>
#include <QTextStream>
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  QCoreApplication::setApplicationName("hics-desktopd");
  const auto plugins = QDir(QCoreApplication::applicationDirPath())
                           .absoluteFilePath("../share/hics/qs/lib/qt6/plugins");
  if (QDir(plugins).exists())
    QCoreApplication::addLibraryPath(plugins);
  HicsDesktop::Service service;
  auto bus = QDBusConnection::sessionBus();
  if (!bus.registerService("org.hics.Desktop1") ||
      !bus.registerObject("/org/hics/Desktop1", &service,
                          QDBusConnection::ExportAllSlots |
                              QDBusConnection::ExportAllSignals)) {
    QTextStream(stderr) << bus.lastError().message() << Qt::endl;
    return 1;
  }
  // D-Bus activation also runs without a user systemd manager, for example in
  // nested sessions. Do not outlive that session or keep inherited pipes open.
  bus.connect(QString(), "/org/freedesktop/DBus/Local",
              "org.freedesktop.DBus.Local", "Disconnected", &app, SLOT(quit()));
  System::ShutdownSignals shutdown(&app, [&] { service.stop(); });
  return app.exec();
}
