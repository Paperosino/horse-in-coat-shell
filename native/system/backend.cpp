#include "backend.hpp"
#include "memory.hpp"
#include <QDBusArgument>
#include <QDBusInterface>
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDBusReply>
#include <QDBusVariant>
#include <QDateTime>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QStorageInfo>
#include <QTimeZone>
#include <QUrl>
#include <cups/cups.h>
#include <cups/ipp.h>
#include <memory>
#include <pwd.h>
#include <sys/socket.h>
#include <unistd.h>
using StringMap = QMap<QString, QString>;
Q_DECLARE_METATYPE(StringMap)
using Interfaces = QMap<QString, QVariantMap>;
using Objects = QMap<QDBusObjectPath, Interfaces>;
Q_DECLARE_METATYPE(Interfaces)
Q_DECLARE_METATYPE(Objects)
namespace System {
QString encode(const QJsonObject &o) {
  return QString::fromUtf8(QJsonDocument(o).toJson(QJsonDocument::Compact));
}
QJsonObject failure(const std::exception &e) {
  auto f = dynamic_cast<const Failure *>(&e);
  return {{"error", QString::fromUtf8(e.what())},
          {"code", f ? f->code : "failed"}};
}
static QVariantList call(const QString &service, const QString &path,
                         const QString &interface, const QString &method,
                         QVariantList args = {}, int timeout = 12000) {
  auto msg = QDBusMessage::createMethodCall(service, path, interface, method);
  msg.setArguments(args);
  auto reply = QDBusConnection::systemBus().call(msg, QDBus::Block, timeout);
  if (reply.type() == QDBusMessage::ErrorMessage)
    throw Failure(reply.errorName().contains("NotAuthorized") ||
                          reply.errorName().contains("AccessDenied")
                      ? "denied"
                      : "unavailable",
                  reply.errorMessage());
  return reply.arguments();
}
static QVariantMap properties(const QString &service, const QString &path,
                              const QString &interface) {
  auto values = call(service, path, "org.freedesktop.DBus.Properties", "GetAll",
                     {interface});
  return values.isEmpty() ? QVariantMap{}
                          : qdbus_cast<QVariantMap>(values.first());
}
static QString userName(uint uid) {
  struct passwd entry, *found = nullptr;
  QByteArray buf(16384, 0);
  if (getpwuid_r(uid, &entry, buf.data(), size_t(buf.size()), &found) != 0 ||
      !found)
    throw Failure("denied", "Unknown caller");
  return QString::fromUtf8(entry.pw_name);
}
static QString text(const QJsonObject &o, const QString &key, int max = 1024) {
  auto v = o.value(key);
  if (!v.isString() || v.toString().isEmpty() || v.toString().size() > max ||
      v.toString().contains(QChar(0)))
    throw Failure("invalid", "Invalid setting value");
  return v.toString();
}
void authorize(const QString &sender, const QString &action, uint uid) {
  if (uid == 0)
    return;
  qDBusRegisterMetaType<StringMap>();
  QDBusArgument subject;
  subject.beginStructure();
  subject << QString("system-bus-name") << QVariantMap{{"name", sender}};
  subject.endStructure();
  auto values = call(
      "org.freedesktop.PolicyKit1", "/org/freedesktop/PolicyKit1/Authority",
      "org.freedesktop.PolicyKit1.Authority", "CheckAuthorization",
      {QVariant::fromValue(subject), action,
       QVariant::fromValue(QMap<QString, QString>{}), uint(1), QString()},
      150000);
  if (values.isEmpty())
    throw Failure("denied", "Authorization was cancelled or denied");
  const auto arg = qvariant_cast<QDBusArgument>(values.first());
  bool allowed = false, challenge = false;
  QMap<QString, QString> details;
  arg.beginStructure();
  arg >> allowed >> challenge >> details;
  arg.endStructure();
  if (!allowed)
    throw Failure("denied", "Authorization was cancelled or denied");
}
struct HttpCloser {
  void operator()(http_t *h) const { httpClose(h); }
};
using Http = std::unique_ptr<http_t, HttpCloser>;
static Http cups() {
  // Always use the local scheduler, never caller-supplied servers or
  // credentials.
  const char *server = QFileInfo::exists("/run/cups/cups.sock")
                           ? "/run/cups/cups.sock"
                           : "localhost";
  cupsSetServer(server);
  cupsSetUser("root");
  Http h(httpConnect2(server, ippPort(), nullptr, AF_UNSPEC,
                      HTTP_ENCRYPTION_IF_REQUESTED, 1, 3000, nullptr));
  if (!h)
    throw Failure("cups-unavailable", "Printing service is unavailable");
  httpSetTimeout(h.get(), 8, nullptr, nullptr);
  return h;
}
struct IppCloser {
  void operator()(ipp_t *p) const { ippDelete(p); }
};
using Ipp = std::unique_ptr<ipp_t, IppCloser>;
static Ipp request(http_t *h, ipp_t *req, const char *path) {
  Ipp r(cupsDoRequest(h, req, path));
  if (!r || ippGetStatusCode(r.get()) >= IPP_STATUS_ERROR_BAD_REQUEST)
    throw Failure("printing", QString::fromUtf8(cupsLastErrorString()));
  return r;
}
static QString attr(ipp_t *r, const char *key) {
  auto a = ippFindAttribute(r, key, IPP_TAG_ZERO);
  auto v = a ? ippGetString(a, 0, nullptr) : nullptr;
  return QString::fromUtf8(v ? v : "");
}
static QJsonObject printers(uint uid) {
  auto h = cups();
  cups_dest_t *dests = nullptr;
  int count = cupsGetDests2(h.get(), &dests);
  QJsonArray list, jobs;
  for (int i = 0; i < count; ++i) {
    const auto &d = dests[i];
    auto option = [&](const char *k) {
      auto v = cupsGetOption(k, d.num_options, d.options);
      return QString::fromUtf8(v ? v : "");
    };
    if (option("printer-state").isEmpty())
      continue;
    list.append(QJsonObject{
        {"name", QString::fromUtf8(d.name)},
        {"description", option("printer-info")},
        {"location", option("printer-location")},
        {"model", option("printer-make-and-model")},
        {"state", option("printer-state").toInt()},
        {"message", option("printer-state-message")},
        {"uri", QUrl(option("device-uri")).toString(QUrl::RemoveUserInfo)},
        {"isDefault", bool(d.is_default)}});
  }
  cupsFreeDests(count, dests);
  cups_job_t *queue = nullptr;
  int size = cupsGetJobs2(h.get(), &queue, nullptr, 0, CUPS_WHICHJOBS_ACTIVE);
  auto owner = userName(uid);
  for (int i = 0; i < size; ++i) {
    auto &j = queue[i];
    if (owner != QString::fromUtf8(j.user ? j.user : ""))
      continue;
    jobs.append(
        QJsonObject{{"id", j.id},
                    {"printer", QString::fromUtf8(j.dest ? j.dest : "")},
                    {"title", QString::fromUtf8(j.title ? j.title : "")},
                    {"state", int(j.state)},
                    {"size", j.size}});
  }
  cupsFreeJobs(size, queue);
  return {{"available", true}, {"printers", list}, {"jobs", jobs}};
}
static QJsonObject discoverPrinters() {
  cupsSetServer("localhost");
  struct Found {
    cups_dest_t *dests = nullptr;
    int count = 0;
  } found;
  cupsEnumDests(
      CUPS_DEST_FLAGS_NONE, 2000, nullptr, CUPS_PRINTER_DISCOVERED,
      CUPS_PRINTER_DISCOVERED,
      [](void *data, unsigned flags, cups_dest_t *dest) {
        auto f = static_cast<Found *>(data);
        if (!(flags & CUPS_DEST_FLAGS_REMOVED) && f->count < 6)
          f->count = cupsCopyDest(dest, f->count, &f->dests);
        return 1;
      },
      &found);
  QJsonArray devices;
  for (int i = 0; i < found.count; ++i) {
    auto &dest = found.dests[i];
    auto raw = cupsGetOption("device-uri", dest.num_options, dest.options);
    QUrl uri(QString::fromUtf8(raw ? raw : ""));
    if (uri.scheme() == "dnssd") {
      char resource[2048] = {};
      Http connection(cupsConnectDest(&dest, CUPS_DEST_FLAGS_DEVICE, 2000,
                                      nullptr, resource, sizeof(resource),
                                      nullptr, nullptr));
      if (!connection)
        continue;
      // libcups stores the fully resolved DNS-SD URI, including its service
      // port.
      raw = cupsGetOption("device-uri", dest.num_options, dest.options);
      uri = QUrl(QString::fromUtf8(raw ? raw : ""));
    }
    if ((uri.scheme() == "ipp" || uri.scheme() == "ipps") &&
        !uri.host().isEmpty())
      devices.append(QJsonObject{{"name", QString::fromUtf8(dest.name)},
                                 {"uri", uri.toString(QUrl::RemoveUserInfo)}});
  }
  cupsFreeDests(found.count, found.dests);
  return {{"available", true}, {"devices", devices}};
}
static QJsonObject timeStatus() {
  auto p = properties("org.freedesktop.timedate1", "/org/freedesktop/timedate1",
                      "org.freedesktop.timedate1");
  QJsonArray zones;
  for (const auto &z : qdbus_cast<QStringList>(
           call("org.freedesktop.timedate1", "/org/freedesktop/timedate1",
                "org.freedesktop.timedate1", "ListTimezones")
               .first()))
    zones.append(z);
  return {{"available", true},
          {"timezone", p.value("Timezone").toString()},
          {"ntp", p.value("NTP").toBool()},
          {"canNtp", p.value("CanNTP").toBool()},
          {"synchronized", p.value("NTPSynchronized").toBool()},
          {"localRtc", p.value("LocalRTC").toBool()},
          {"timezones", zones},
          {"localTime",
           QDateTime::currentDateTimeUtc()
               .toTimeZone(QTimeZone(p.value("Timezone").toString().toUtf8()))
               .toString(Qt::ISODate)}};
}
static QJsonObject powerStatus() {
  auto p = properties("org.freedesktop.UPower.PowerProfiles",
                      "/org/freedesktop/UPower/PowerProfiles",
                      "org.freedesktop.UPower.PowerProfiles");
  QJsonArray profiles;
  auto rows = qdbus_cast<QList<QVariantMap>>(p.value("Profiles"));
  for (const auto &r : rows)
    profiles.append(r.value("Profile").toString());
  return {{"available", true},
          {"active", p.value("ActiveProfile").toString()},
          {"profiles", profiles},
          {"degraded", p.value("PerformanceDegraded").toString()}};
}
QJsonObject status(const QString &domain, uint uid) {
  if (domain == "region")
    return regionStatus();
  if (domain == "printers")
    return printers(uid);
  if (domain == "printer-discovery")
    return discoverPrinters();
  if (domain == "memory")
    return memoryStatus();
  if (domain == "storage")
    return storageStatus();
  if (domain == "datetime")
    return timeStatus();
  if (domain == "power")
    return powerStatus();
  throw Failure("invalid", "Unknown system settings section");
}
void validate(const QString &d, const QString &op, const QJsonObject &o) {
  if (d == "region") {
    validateRegion(op, o);
    return;
  }
  if (d == "memory") {
    if (op != "configure") throw Failure("invalid", "Unknown memory operation");
    Memory::validate(o); return;
  }
  if (d == "storage") {
    validateStorage(op, o);
    return;
  }
  if (d == "printers") {
    if (op == "cancel-job") {
      auto id = o.value("id");
      if (!id.isDouble() || id.toDouble() != id.toInt() || id.toInt() < 1)
        throw Failure("invalid", "Invalid print job");
      return;
    }
    if (!QStringList{"add", "remove", "default", "pause", "resume"}.contains(
            op))
      throw Failure("invalid", "Unknown printer operation");
    auto name = text(o, "name", 127);
    if (!QRegularExpression("^[A-Za-z0-9][A-Za-z0-9_.-]{0,126}$")
             .match(name)
             .hasMatch())
      throw Failure("invalid", "Invalid printer name");
    if (op == "add") {
      QUrl u(text(o, "uri", 2048));
      if (!u.isValid() || !QStringList{"ipp", "ipps"}.contains(u.scheme()) ||
          u.host().isEmpty() || !u.userInfo().isEmpty())
        throw Failure("invalid", "Enter an IPP or IPPS printer address");
      text(o, "description", 256);
    }
    return;
  }
  if (d == "datetime") {
    if (op == "ntp") {
      if (!o.value("enabled").isBool())
        throw Failure("invalid", "Expected a switch value");
      return;
    }
    if (op == "timezone") {
      if (!QTimeZone::isTimeZoneIdAvailable(text(o, "timezone", 128).toUtf8()))
        throw Failure("invalid", "Unknown time zone");
      return;
    }
    if (op == "time") {
      auto t = QDateTime::fromString(text(o, "time", 40), Qt::ISODate);
      if (!t.isValid() || t.date().year() < 2020 || t.date().year() > 2100)
        throw Failure("invalid", "Enter a valid local date and time");
      return;
    }
  }
  if (d == "power" && op == "profile" &&
      QStringList{"power-saver", "balanced", "performance"}.contains(
          text(o, "profile", 32)))
    return;
  throw Failure("invalid", "Unknown system operation");
}
static void printerAction(const QString &op, const QJsonObject &o, uint uid) {
  auto h = cups();
  if (op == "cancel-job") {
    auto r = ippNewRequest(IPP_OP_GET_JOB_ATTRIBUTES);
    auto uri = QString("ipp://localhost/jobs/%1").arg(o["id"].toInt()).toUtf8();
    ippAddString(r, IPP_TAG_OPERATION, IPP_TAG_URI, "job-uri", nullptr,
                 uri.constData());
    auto response = request(h.get(), r, "/jobs/");
    if (uid != 0 &&
        attr(response.get(), "job-originating-user-name") != userName(uid))
      throw Failure("denied", "You can only cancel your own print jobs");
    auto cancel = ippNewRequest(IPP_OP_CANCEL_JOB);
    ippAddString(cancel, IPP_TAG_OPERATION, IPP_TAG_URI, "job-uri", nullptr,
                 uri.constData());
    auto owner = userName(uid).toUtf8();
    ippAddString(cancel, IPP_TAG_OPERATION, IPP_TAG_NAME,
                 "requesting-user-name", nullptr, owner.constData());
    request(h.get(), cancel, "/jobs/");
    return;
  }
  ipp_op_t operation = op == "add"       ? IPP_OP_CUPS_ADD_MODIFY_PRINTER
                       : op == "remove"  ? IPP_OP_CUPS_DELETE_PRINTER
                       : op == "default" ? IPP_OP_CUPS_SET_DEFAULT
                       : op == "pause"   ? IPP_OP_PAUSE_PRINTER
                                         : IPP_OP_RESUME_PRINTER;
  auto r = ippNewRequest(operation);
  auto uri =
      QString("ipp://localhost/printers/%1").arg(o["name"].toString()).toUtf8();
  ippAddString(r, IPP_TAG_OPERATION, IPP_TAG_URI, "printer-uri", nullptr,
               uri.constData());
  ippAddString(r, IPP_TAG_OPERATION, IPP_TAG_NAME, "requesting-user-name",
               nullptr, "root");
  if (op == "add") {
    auto device = o["uri"].toString().toUtf8(),
         desc = o["description"].toString().toUtf8();
    ippAddString(r, IPP_TAG_PRINTER, IPP_TAG_URI, "device-uri", nullptr,
                 device.constData());
    ippAddString(r, IPP_TAG_PRINTER, IPP_TAG_TEXT, "printer-info", nullptr,
                 desc.constData());
    ippAddString(r, IPP_TAG_PRINTER, IPP_TAG_NAME, "ppd-name", nullptr,
                 "everywhere");
    ippAddBoolean(r, IPP_TAG_PRINTER, "printer-is-accepting-jobs", 1);
    ippAddInteger(r, IPP_TAG_PRINTER, IPP_TAG_ENUM, "printer-state",
                  IPP_PSTATE_IDLE);
  }
  request(h.get(), r, "/admin/");
}
void apply(const QString &d, const QString &op, const QJsonObject &o,
           uint uid) {
  if (d == "region") {
    applyRegion(op, o);
    return;
  }
  if (d == "memory") { memoryApply(o); return; }
  if (d == "storage") {
    storageMaintenance(op, o);
    return;
  }
  if (d == "printers") {
    printerAction(op, o, uid);
    return;
  }
  if (d == "datetime") {
    QVariantList args;
    QString method;
    if (op == "timezone") {
      method = "SetTimezone";
      args = {o["timezone"].toString(), false};
    } else if (op == "ntp") {
      method = "SetNTP";
      args = {o["enabled"].toBool(), false};
    } else {
      method = "SetTime";
      auto date = QDateTime::fromString(o["time"].toString(), Qt::ISODate);
      if (date.timeSpec() == Qt::LocalTime) {
        auto zone = properties("org.freedesktop.timedate1",
                               "/org/freedesktop/timedate1",
                               "org.freedesktop.timedate1")
                        .value("Timezone")
                        .toString();
        date = QDateTime(date.date(), date.time(), QTimeZone(zone.toUtf8()));
      }
      args = {QVariant::fromValue(qint64(date.toMSecsSinceEpoch() * 1000)),
              false, false};
    }
    call("org.freedesktop.timedate1", "/org/freedesktop/timedate1",
         "org.freedesktop.timedate1", method, args);
    return;
  }
  if (d == "power") {
    if (!powerStatus()["profiles"].toArray().contains(o["profile"]))
      throw Failure("unavailable", "This power profile is not supported");
    call("org.freedesktop.UPower.PowerProfiles",
         "/org/freedesktop/UPower/PowerProfiles",
         "org.freedesktop.DBus.Properties", "Set",
         {"org.freedesktop.UPower.PowerProfiles", "ActiveProfile",
          QVariant::fromValue(QDBusVariant(o["profile"].toString()))});
    return;
  }
  throw Failure("invalid", "Unknown system operation");
}
} // namespace System
