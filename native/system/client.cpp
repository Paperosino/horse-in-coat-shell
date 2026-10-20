#include "backend.hpp"
#include <QCoreApplication>
#include <QDBusMessage>
#include <QJsonDocument>
#include <QTextStream>
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  auto args = app.arguments();
  QJsonObject out;
  try {
    if (args.size() < 3 || !QStringList{"status", "apply"}.contains(args[1]))
      throw System::Failure("invalid",
                            "Usage: hyprstack-systemctl status SECTION | apply "
                            "SECTION OPERATION < JSON");
    bool write = args[1] == "apply";
    QJsonObject options;
    if (write) {
      if (args.size() != 4)
        throw System::Failure("invalid", "Missing operation");
      QTextStream input(stdin);
      auto raw = input.read(16385);
      if (raw.size() > 16384)
        throw System::Failure("invalid", "Request is too large");
      QJsonParseError error;
      auto doc = QJsonDocument::fromJson(raw.toUtf8(), &error);
      if (error.error != QJsonParseError::NoError || !doc.isObject())
        throw System::Failure("invalid", "Invalid request");
      options = doc.object();
    }
    if (write && args[2] == "storage" &&
        !QStringList{"configure", "trim", "defragment", "stop-maintenance"}
             .contains(args[3]))
      out = System::storageAction(args[3], options);
    else {
      if (write)
        System::validate(args[2], args[3], options);
      auto call = QDBusMessage::createMethodCall(System::Service, System::Path,
                                                 System::Interface,
                                                 write ? "Apply" : "Status");
      if (write)
        call.setArguments({args[2], args[3], System::encode(options)});
      else
        call.setArguments({args[2]});
      call.setInteractiveAuthorizationAllowed(write);
      auto reply =
          QDBusConnection::systemBus().call(call, QDBus::Block, 150000);
      if (reply.type() == QDBusMessage::ErrorMessage)
        throw System::Failure("daemon-unavailable", reply.errorMessage());
      auto doc = QJsonDocument::fromJson(
          reply.arguments().value(0).toString().toUtf8());
      if (!doc.isObject())
        throw System::Failure("failed", "Invalid system service response");
      out = doc.object();
    }
  } catch (const std::exception &e) {
    out = System::failure(e);
  }
  QTextStream(stdout) << System::encode(out) << Qt::endl;
  return out.contains("error") ? 1 : 0;
}
