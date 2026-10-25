#include "service.hpp"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusObjectPath>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDirIterator>
#include <QElapsedTimer>
#include <QFileInfo>
#include <QJsonArray>
#include <QRegularExpression>
#include <QSaveFile>
#include <QTemporaryFile>
#include <sys/syscall.h>
#include <linux/fs.h>
#include <fcntl.h>
#include <unistd.h>
#include <QSet>
namespace HicsDesktop {
class BluetoothTransfer : public QObject {
  Q_OBJECT
  Service *owner;
  QSharedPointer<Job> job;
  QString session, path, file;
  bool done = false;
  void invoke(const QString &target, const QString &interface,
              const QString &method, const QVariantList &args,
              std::function<void(QDBusMessage)> callback) {
    auto call = QDBusMessage::createMethodCall("org.bluez.obex", target,
                                               interface, method);
    call.setArguments(args);
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(call, 20000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this, watcher, callback] {
              const auto reply = watcher->reply();
              watcher->deleteLater();
              if (reply.type() == QDBusMessage::ErrorMessage) {
                complete(reply.errorMessage());
                return;
              }
              callback(reply);
            });
  }
  void complete(const QString &error = {}) {
    if (done)
      return;
    done = true;
    if (!path.isEmpty())
      QDBusConnection::sessionBus().disconnect(
          "org.bluez.obex", path, "org.freedesktop.DBus.Properties",
          "PropertiesChanged", this,
          SLOT(changed(QString, QVariantMap, QStringList)));
    if (!session.isEmpty()) {
      auto call = QDBusMessage::createMethodCall(
          "org.bluez.obex", "/org/bluez/obex", "org.bluez.obex.Client1",
          "RemoveSession");
      call.setArguments({QVariant::fromValue(QDBusObjectPath(session))});
      QDBusConnection::sessionBus().asyncCall(call, 5000);
    }
    owner->finish(job, {{"ok", error.isEmpty()}}, error);
    deleteLater();
  }

public:
  BluetoothTransfer(Service *owner, const QSharedPointer<Job> &job,
                    const QString &file)
      : QObject(owner), owner(owner), job(job), file(file) {
    job->cancellable = true;
    owner->jobProgress(job, -1);
    connect(owner, &Service::CancelRequested, this, [this](const QString &id) {
      if (id != this->job->id || done)
        return;
      if(session.isEmpty())return;
      if (!path.isEmpty()) {
        auto call = QDBusMessage::createMethodCall(
            "org.bluez.obex", path, "org.bluez.obex.Transfer1", "Cancel");
        QDBusConnection::sessionBus().asyncCall(call, 5000);
      }
      complete("Transfer cancelled");
    });
  }
  void start(const QString &address) {
    invoke(
        "/org/bluez/obex", "org.bluez.obex.Client1", "CreateSession",
        {address, QVariantMap{{"Target", QString("opp")}}},
        [this](const QDBusMessage &reply) {
          session =
              qvariant_cast<QDBusObjectPath>(reply.arguments().value(0)).path();
          if (session.isEmpty()) {
            complete("Bluetooth did not create an OBEX session");
            return;
          }
          if (job->cancel->load()) {
            complete("Transfer cancelled");
            return;
          }
          invoke(session, "org.bluez.obex.ObjectPush1", "SendFile", {file},
                 [this](const QDBusMessage &reply) {
                   path = qvariant_cast<QDBusObjectPath>(
                              reply.arguments().value(0))
                              .path();
                   if (path.isEmpty()) {
                     complete("Bluetooth did not create a transfer");
                     return;
                   }
                   QDBusConnection::sessionBus().connect(
                       "org.bluez.obex", path,
                       "org.freedesktop.DBus.Properties", "PropertiesChanged",
                       this, SLOT(changed(QString, QVariantMap, QStringList)));
                   invoke(path, "org.freedesktop.DBus.Properties", "GetAll",
                          {QString("org.bluez.obex.Transfer1")},
                          [this](const QDBusMessage &properties) {
                            changed("org.bluez.obex.Transfer1",
                                    qdbus_cast<QVariantMap>(
                                        properties.arguments().value(0)),
                                    {});
                          });
                 });
        });
  }
private slots:
  void changed(const QString &interface, const QVariantMap &values,
               const QStringList &) {
    if (done || interface != "org.bluez.obex.Transfer1")
      return;
    const auto status = values["Status"].toString();
    if (status == "complete") {
      owner->jobProgress(job, 1);
      complete();
      return;
    }
    if (status == "error") {
      complete("Bluetooth transfer failed. Check the other device and retry.");
      return;
    }
    if (values.contains("Transferred")) {
      const auto size = QFileInfo(file).size();
      owner->jobProgress(
          job,
          size > 0 ? qMin(1.0, values["Transferred"].toDouble() / size) : -1);
    }
  }
};
void Service::transfer(const QSharedPointer<Job> &job) {
  const auto args = job->arguments;
  if (job->operation == "transfer.send") {
    const auto address = args["address"].toString(),
               file = args["path"].toString();
    QFileInfo info(file);
    if (!QRegularExpression("^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
             .match(address)
             .hasMatch() ||
        !info.isAbsolute() || !info.isFile() || info.isSymLink()) {
      finish(job, {}, "Choose a Bluetooth device and a regular local file");
      return;
    }
    auto *transfer = new BluetoothTransfer(this, job, file);
    transfer->start(address);
    return;
  }
  if (job->operation != "transfer.copy") {
    finish(job, {}, "Unknown file transfer operation");
    return;
  }
  const auto cancel = job->cancel;
  worker(
      job,
      [this, job, args, cancel] {
        const auto target =
            QFileInfo(args["target"].toString()).canonicalFilePath();
        if (target.isEmpty() || !QFileInfo(target).isDir())
          return QJsonObject{
              {"error", "Choose an existing destination folder"}};
        const auto sources = args["sources"].toArray();
        if (sources.isEmpty() || sources.size() > 128)
          return QJsonObject{{"error", "Choose between one and 128 sources"}};
        struct Copy {
          QString source, destination;
        };
        QList<Copy> files;QStringList directories;
        QSet<QString> destinations;
        qint64 total = 0, copied = 0;
        int folders = 0;
        for (const auto &value : sources) {
          QFileInfo source(value.toString());
          if (!source.isAbsolute() || source.isSymLink() || !source.exists())
            return QJsonObject{{"error", "Sources must be existing local files "
                                         "or folders without symlinks"}};
          const auto base = target + "/" + source.fileName();
          if (source.isDir() &&
              (target == source.canonicalFilePath() ||
               target.startsWith(source.canonicalFilePath() + "/")))
            return QJsonObject{
                {"error", "The destination cannot be inside a source folder"}};
          if (QFileInfo::exists(base) || destinations.contains(base))
            return QJsonObject{
                {"error", "A destination already exists; existing files are "
                          "never overwritten"}};
          destinations.insert(base);
          auto add = [&](const QFileInfo &entry, const QString &destination) {
            if (entry.isSymLink())
              throw std::runtime_error(
                  "Symbolic links are not copied by this operation");
            if (entry.isDir()) {
              directories.append(destination);
          if (++folders > 4096)
                throw std::runtime_error("Too many folders in one transfer");
            } else if (entry.isFile()) {
              if (files.size() >= 50000)
                throw std::runtime_error("Too many files in one transfer");
              files.append({entry.absoluteFilePath(), destination});
              total += entry.size();
            }
          };
          add(source, base);
          if (source.isDir()) {
            QDirIterator it(source.absoluteFilePath(),
                            QDir::AllEntries | QDir::NoDotAndDotDot |
                                QDir::Hidden,
                            QDirIterator::Subdirectories);
            while (it.hasNext() && !cancel->load()) {
              it.next();
              add(it.fileInfo(), base + "/" +
                                     QDir(source.absoluteFilePath())
                                         .relativeFilePath(it.filePath()));
            }
          }
        }
        for(const auto& folder:directories){if(cancel->load())break;if(!QDir().mkpath(folder))return QJsonObject{{"error","Cannot create a copied folder"}};}
    QElapsedTimer update;
        update.start();
        QJsonArray completed;
        for (const auto &item : files) {
          if (cancel->load())
            break;
          QFile source(item.source);
          if (!source.open(QIODevice::ReadOnly))
            return QJsonObject{{"error", "Cannot read a selected source"}};
          if (!QDir().mkpath(QFileInfo(item.destination).absolutePath()) ||
              QFileInfo::exists(item.destination))
            return QJsonObject{
                {"error",
                 "Cannot create destination without overwriting files"}};
          QTemporaryFile destination(QFileInfo(item.destination).absolutePath()+"/.hics-copy-XXXXXX");
          if (!destination.open() || !destination.setPermissions(source.permissions()))
            return QJsonObject{{"error", "Cannot write the destination"}};
          while (!source.atEnd() && !cancel->load()) {
            auto bytes = source.read(256 * 1024);
            if (bytes.isEmpty() && source.error() != QFileDevice::NoError)
              return QJsonObject{{"error", "Source read failed"}};
            if (destination.write(bytes) != bytes.size())
              return QJsonObject{
                  {"error", "Destination write failed; check available space"}};
            copied += bytes.size();
            if (update.elapsed() > 100) {
              QMetaObject::invokeMethod(
                  this,
                  [this, job, copied, total] {
                    jobProgress(job, total > 0 ? double(copied) / total : 0);
                  },
                  Qt::QueuedConnection);
              update.restart();
            }
          }
          if (cancel->load()) {
            destination.remove();
            break;
          }
          if (!destination.flush() || ::syscall(SYS_renameat2,AT_FDCWD,destination.fileName().toUtf8().constData(),AT_FDCWD,item.destination.toUtf8().constData(),RENAME_NOREPLACE)!=0)
            return QJsonObject{
                {"error", "Cannot finish writing a copied file"}};
          completed.append(item.destination);
        }
        return QJsonObject{{"files", completed.size()},
                           {"bytes", copied},
                           {"cancelled", cancel->load()}};
      },
      true);
}
} // namespace HicsDesktop
#include "transfers.moc"
