#include "backend.hpp"
#include <QDBusArgument>
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QProcess>
#include <QRegularExpression>
#include <QStorageInfo>

// UDisks configuration is a typed D-Bus structure, not an editable fstab line.
struct DiskConfig {
  QString type;
  QVariantMap fields;
};
Q_DECLARE_METATYPE(DiskConfig)
using DiskConfigs = QList<DiskConfig>;
Q_DECLARE_METATYPE(DiskConfigs)
QDBusArgument &operator<<(QDBusArgument &a, const DiskConfig &v) {
  a.beginStructure();
  a << v.type << v.fields;
  a.endStructure();
  return a;
}
const QDBusArgument &operator>>(const QDBusArgument &a, DiskConfig &v) {
  a.beginStructure();
  a >> v.type >> v.fields;
  a.endStructure();
  return a;
}
using DiskInterfaces = QMap<QString, QVariantMap>;
using DiskObjects = QMap<QDBusObjectPath, DiskInterfaces>;
Q_DECLARE_METATYPE(DiskInterfaces)
Q_DECLARE_METATYPE(DiskObjects)
namespace System {
namespace {
constexpr auto U = "org.freedesktop.UDisks2";
constexpr auto B = "org.freedesktop.UDisks2.Block";
constexpr auto F = "org.freedesktop.UDisks2.Filesystem";
constexpr auto A = "org.freedesktop.UDisks2.Drive.Ata";
constexpr auto N = "org.freedesktop.UDisks2.NVMe.Controller";
QVariantList invoke(const QString &service, const QString &path,
                    const QString &iface, const QString &method,
                    const QVariantList &args = {}, int timeout = 12000) {
  auto m = QDBusMessage::createMethodCall(service, path, iface, method);
  m.setArguments(args);
  m.setInteractiveAuthorizationAllowed(true);
  auto r = QDBusConnection::systemBus().call(m, QDBus::Block, timeout);
  if (r.type() == QDBusMessage::ErrorMessage)
    throw Failure(r.errorName().contains("NotAuthorized") ||
                          r.errorName().contains("AccessDenied")
                      ? "denied"
                      : "unavailable",
                  r.errorMessage());
  return r.arguments();
}
QVariantMap props(const QString &path, const QString &iface) {
  return qdbus_cast<QVariantMap>(
      invoke(U, path, "org.freedesktop.DBus.Properties", "GetAll", {iface})
          .value(0));
}
void registerTypes() {
  qDBusRegisterMetaType<DiskConfig>();
  qDBusRegisterMetaType<DiskConfigs>();
  qDBusRegisterMetaType<DiskInterfaces>();
  qDBusRegisterMetaType<DiskObjects>();
}
QString bytes(const QVariant &v) {
  return QString::fromUtf8(v.toByteArray().split('\0').first());
}
QByteArray terminated(const QString &v) {
  auto b = v.toUtf8();
  b.append('\0');
  return b;
}
QString pathOf(const QJsonObject &o) {
  auto p = o.value("path");
  if (!p.isString() ||
      !QRegularExpression(
           "^/org/freedesktop/UDisks2/block_devices/[A-Za-z0-9_]{1,200}\\z")
           .match(p.toString())
           .hasMatch())
    throw Failure("invalid", "Invalid volume");
  return p.toString();
}
QString mountOf(const QVariantMap &fs) {
  for (const auto &v : qdbus_cast<QList<QByteArray>>(fs.value("MountPoints"))) {
    auto p = QString::fromUtf8(v.split('\0').first());
    if (!p.isEmpty())
      return p;
  }
  return {};
}
DiskConfigs configs(const QVariantMap &b) {
  return qdbus_cast<DiskConfigs>(b.value("Configuration"));
}
bool editable(const DiskConfigs &all, const QString &uuid) {
  if (uuid.isEmpty() || all.size() > 1)
    return false;
  if (all.isEmpty())
    return true;
  auto dir = bytes(all.first().fields.value("dir"));
  return all.first().type == "fstab" &&
         (dir.startsWith("/mnt/") || dir.startsWith("/media/"));
}
QString unitOf(const QString &path) {
  return "hyprstack-disk-" + path.section('/', -1) + ".service";
}
QJsonObject jobState(const QString &path) {
  try {
    auto p = qdbus_cast<QDBusObjectPath>(
                 invoke("org.freedesktop.systemd1", "/org/freedesktop/systemd1",
                        "org.freedesktop.systemd1.Manager", "GetUnit",
                        {unitOf(path)})
                     .value(0))
                 .path();
    auto get = [&](const QString &iface) {
      return qdbus_cast<QVariantMap>(invoke("org.freedesktop.systemd1", p,
                                            "org.freedesktop.DBus.Properties",
                                            "GetAll", {iface})
                                         .value(0));
    };
    auto u = get("org.freedesktop.systemd1.Unit"),
         s = get("org.freedesktop.systemd1.Service");
    return {{"active", u.value("SubState").toString() == "running" ||
                           u.value("ActiveState").toString() == "activating"},
            {"result", s.value("Result").toString()},
            {"description", u.value("Description").toString()}};
  } catch (const Failure &) {
    return {{"active", false}};
  }
}
QJsonObject smart(const DiskInterfaces &interfaces) {
  bool nvme = interfaces.contains(N);
  auto a = interfaces.value(nvme ? N : A);
  bool supported = nvme || a.value("SmartSupported").toBool();
  auto updated = a.value("SmartUpdated").toULongLong();
  QJsonObject result{{"supported", supported},
                     {"enabled", nvme || a.value("SmartEnabled").toBool()},
                     {"updated", double(updated)},
                     {"nvme", nvme}};
  if (!updated)
    return result;
  auto warnings = a.value("SmartCriticalWarning").toStringList();
  result["failing"] =
      nvme ? !warnings.isEmpty() : a.value("SmartFailing").toBool();
  result["warnings"] = QJsonArray::fromStringList(warnings);
  if (a.value("SmartTemperature").toDouble() > 0)
    result["temperature"] = a.value("SmartTemperature").toDouble() - 273.15;
  result["hours"] =
      nvme ? double(a.value("SmartPowerOnHours").toULongLong())
           : double(a.value("SmartPowerOnSeconds").toULongLong()) / 3600;
  result["test"] = a.value("SmartSelftestStatus").toString();
  result["remaining"] = a.value("SmartSelftestPercentRemaining").toInt();
  if (!nvme) {
    result["badSectors"] = double(a.value("SmartNumBadSectors").toLongLong());
    result["failingAttributes"] = a.value("SmartNumAttributesFailing").toInt();
  }
  return result;
}
} // namespace
QJsonObject storageStatus() {
  registerTypes();
  auto objects = qdbus_cast<DiskObjects>(
      invoke(U, "/org/freedesktop/UDisks2",
             "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")
          .value(0));
  QJsonArray volumes;
  for (auto it = objects.cbegin(); it != objects.cend(); ++it) {
    auto fs = it.value().value(F), b = it.value().value(B);
    if (fs.isEmpty() || b.value("HintIgnore").toBool())
      continue;
    auto mount = mountOf(fs), uuid = b.value("IdUUID").toString();
    auto interfaces =
        objects.value(qdbus_cast<QDBusObjectPath>(b.value("Drive")));
    auto drive = interfaces.value("org.freedesktop.UDisks2.Drive");
    auto all = configs(b);
    QVariantMap entry;
    if (all.size() == 1 && all.first().type == "fstab")
      entry = all.first().fields;
    auto opts = bytes(entry.value("opts")).split(',', Qt::SkipEmptyParts);
    bool ssd = drive.contains("RotationRate") &&
               drive.value("RotationRate").toInt() == 0;
    QString fsType = b.value("IdType").toString();
    QJsonObject v{
        {"path", it.key().path()},
        {"device", bytes(b.value("PreferredDevice"))},
        {"uuid", uuid},
        {"label", b.value("IdLabel").toString()},
        {"filesystem", fsType},
        {"size", double(b.value("Size").toULongLong())},
        {"mountPoint", mount},
        {"removable", drive.value("Removable").toBool()},
        {"readOnly", b.value("ReadOnly").toBool()},
        {"model", drive.value("Model").toString()},
        {"serial", drive.value("Serial").toString()},
        {"ssd", ssd},
        {"smart", smart(interfaces)},
        {"mountEditable", editable(all, uuid)},
        {"configured", !entry.isEmpty()},
        {"automatic", !entry.isEmpty() && !opts.contains("noauto")},
        {"mountDirectory", entry.isEmpty() ? "/mnt/hics-" + uuid
                                           : bytes(entry.value("dir"))},
        {"mountOptions", bytes(entry.value("opts"))},
        {"maintenance", jobState(it.key().path())},
        {"canTrim",
         ssd && !mount.isEmpty() && QFileInfo::exists(HYPRSTACK_FSTRIM) &&
             QStringList{"ext4", "btrfs", "xfs", "f2fs"}.contains(fsType)},
        {"canDefragment", !ssd && drive.value("RotationRate").toInt() > 0 &&
                              fsType == "ext4" && !mount.isEmpty() &&
                              QFileInfo::exists(HYPRSTACK_E4DEFRAG)}};
    if (interfaces.contains(N) &&
        v["smart"].toObject()["updated"].toDouble() > 0) {
      try {
        auto p = qdbus_cast<QDBusObjectPath>(b.value("Drive")).path();
        auto attr = qdbus_cast<QVariantMap>(
            invoke(U, p, N, "SmartGetAttributes", {QVariantMap{}}).value(0));
        auto health = v["smart"].toObject();
        for (auto key :
             {"percent_used", "avail_spare", "media_errors", "total_data_read",
              "total_data_written", "unsafe_shutdowns"})
          if (attr.contains(key))
            health[key] = double(attr.value(key).toULongLong());
        v["smart"] = health;
      } catch (const Failure &) {
      }
    }
    QStorageInfo info(mount);
    // The broker's ProtectSystem sandbox makes its own mount namespace
    // read-only. Read PID 1's mount flags rather than reporting sandbox flags.
    QFile mountInfo("/proc/1/mountinfo");
    if (!mount.isEmpty() && mountInfo.open(QIODevice::ReadOnly)) {
      const auto lines = mountInfo.readAll().split('\n');
      for (const auto &line : lines) {
        auto fields = line.split(' ');
        if (fields.size() < 7)
          continue;
        auto target = fields[4];
        target.replace("\\040", " ");
        target.replace("\\011", "\t");
        target.replace("\\012", "\n");
        target.replace("\\134", "\\");
        if (QString::fromUtf8(target) == mount)
          v["readOnly"] =
              v["readOnly"].toBool() || fields[5].split(',').contains("ro");
      }
    }
    if (!mount.isEmpty() && info.isValid() && info.isReady()) {
      v["free"] = double(info.bytesAvailable());
      v["total"] = double(info.bytesTotal());
    }
    volumes.append(v);
  }
  return {{"available", true}, {"volumes", volumes}};
}
void validateStorage(const QString &op, const QJsonObject &o) {
  pathOf(o);
  if (!QStringList{"mount", "unmount", "configure", "smart-refresh",
                   "smart-short", "smart-extended", "smart-abort", "trim",
                   "defragment", "stop-maintenance"}
           .contains(op))
    throw Failure("invalid", "Unknown storage operation");
  if (op == "configure") {
    for (auto k : {"automatic", "readOnly", "noexec", "nosuid", "nodev",
                   "nofail", "noatime"})
      if (!o.value(k).isBool())
        throw Failure("invalid", "Expected a switch value");
    auto dir = o.value("directory").toString();
    if (dir.size() > 240 ||
        !QRegularExpression("^/(mnt|media)/[A-Za-z0-9][A-Za-z0-9_./-]*\\z")
             .match(dir)
             .hasMatch() ||
        QDir::cleanPath(dir) != dir)
      throw Failure("invalid", "Choose a mount point inside /mnt or /media");
  }
}
QJsonObject storageAction(const QString &op, const QJsonObject &o) {
  validateStorage(op, o);
  registerTypes();
  auto path = pathOf(o);
  auto b = props(path, B);
  if (b.value("IdUsage").toString() != "filesystem")
    throw Failure("invalid", "Invalid volume");
  if (op == "mount" || op == "unmount") {
    auto fs = props(path, F);
    auto mount = mountOf(fs);
    if (op == "unmount" && !mount.startsWith("/run/media/") &&
        !mount.startsWith("/media/") && !mount.startsWith("/mnt/"))
      throw Failure("invalid", "System volumes cannot be unmounted here");
    auto values = invoke(U, path, F, op == "mount" ? "Mount" : "Unmount",
                         {QVariantMap{}}, 150000);
    return {{"ok", true}, {"mountPoint", values.value(0).toString()}};
  }
  if (op == "configure") {
    auto all = configs(b);
    if (!editable(all, b.value("IdUUID").toString()))
      throw Failure("invalid", "System mount configuration is protected");
    auto dir = o["directory"].toString();
    // Do not allow fstab entries to traverse symlinks into system directories.
    for (auto p = dir; p != "/"; p = QFileInfo(p).path())
      if (QFileInfo(p).isSymLink())
        throw Failure("invalid", "Mount point must not contain symbolic links");
    auto allObjects = qdbus_cast<DiskObjects>(
        invoke(U, "/org/freedesktop/UDisks2",
               "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")
            .value(0));
    for (auto it = allObjects.cbegin(); it != allObjects.cend(); ++it)
      if (it.key().path() != path)
        for (const auto &item : configs(it.value().value(B)))
          if (item.type == "fstab" && bytes(item.fields.value("dir")) == dir)
            throw Failure("invalid",
                          "Mount point is already used by another volume");
    DiskConfig next =
        all.isEmpty()
            ? DiskConfig{"fstab",
                         {{"fsname",
                           terminated("UUID=" + b.value("IdUUID").toString())},
                          {"type", terminated(b.value("IdType").toString())},
                          {"freq", 0},
                          {"passno",
                           b.value("IdType").toString() == "ext4" ? 2 : 0}}}
            : all.first();
    auto opts = bytes(next.fields.value("opts")).split(',', Qt::SkipEmptyParts);
    for (auto k : {"defaults", "auto", "rw", "exec", "suid", "dev", "noauto",
                   "ro", "noexec", "nosuid", "nodev", "nofail", "noatime",
                   "x-systemd.automount"})
      opts.removeAll(k);
    if (!o["automatic"].toBool()) {
      opts.append("noauto");
      opts.removeAll("x-systemd.automount");
    }
    opts.append(o["readOnly"].toBool() ? "ro" : "rw");
    opts.append(o["noexec"].toBool() ? "noexec" : "exec");
    opts.append(o["nosuid"].toBool() ? "nosuid" : "suid");
    opts.append(o["nodev"].toBool() ? "nodev" : "dev");
    for (auto k : {"nofail", "noatime"})
      if (o[k].toBool())
        opts.append(k);
    if (o["noatime"].toBool()) {
      opts.removeAll("atime");
      opts.removeAll("relatime");
      opts.removeAll("strictatime");
    }
    if (opts.isEmpty())
      opts.append("defaults");
    next.fields["dir"] = terminated(dir);
    next.fields["opts"] = terminated(opts.join(','));
    QVariantList args;
    if (!all.isEmpty())
      args.append(QVariant::fromValue(all.first()));
    args.append(QVariant::fromValue(next));
    args.append(QVariantMap{});
    invoke(U, path, B,
           all.isEmpty() ? "AddConfigurationItem" : "UpdateConfigurationItem",
           args, 150000);
    return {{"ok", true}};
  }
  auto drive = qdbus_cast<QDBusObjectPath>(b.value("Drive")).path();
  QVariantMap nvme;
  try {
    nvme = props(drive, N);
  } catch (const Failure &) {
  }
  auto iface = nvme.isEmpty() ? A : N;
  QString method = op == "smart-refresh" ? "SmartUpdate"
                   : op == "smart-abort" ? "SmartSelftestAbort"
                                         : "SmartSelftestStart";
  QVariantList args;
  if (method == "SmartSelftestStart")
    args.append(op == "smart-short" ? "short" : "extended");
  args.append(QVariantMap{});
  invoke(U, drive, iface, method, args, 150000);
  return {{"ok", true}};
}
void storageMaintenance(const QString &op, const QJsonObject &o) {
  validateStorage(op, o);
  if (op == "configure") {
    storageAction(op, o);
    invoke("org.freedesktop.systemd1", "/org/freedesktop/systemd1",
           "org.freedesktop.systemd1.Manager", "Reload", {}, 150000);
    return;
  }
  auto path = pathOf(o);
  auto unit = unitOf(path);
  if (op == "stop-maintenance") {
    invoke("org.freedesktop.systemd1", "/org/freedesktop/systemd1",
           "org.freedesktop.systemd1.Manager", "StopUnit", {unit, "replace"});
    return;
  }
  auto volumes = storageStatus()["volumes"].toArray();
  QJsonObject volume;
  for (auto v : volumes)
    if (v.toObject()["path"].toString() == path)
      volume = v.toObject();
  if ((op != "trim" && op != "defragment") ||
      !volume[op == "trim" ? "canTrim" : "canDefragment"].toBool() ||
      volume["readOnly"].toBool())
    throw Failure("invalid", "This operation is not supported by the volume");
  if (volume["maintenance"].toObject()["active"].toBool())
    throw Failure("busy", "Disk maintenance is already running");
  // systemd owns the long-running task, outside the broker sandbox. No shell,
  // caller-provided executable, device or command-line arguments are accepted.
  auto mount = volume["mountPoint"].toString();
  if (QFileInfo(mount).canonicalFilePath() != mount ||
      mount.contains(QRegularExpression("[\\s\\\\\"]")))
    throw Failure("invalid", "Invalid mount point");
  QProcess process;
  QStringList args{"--quiet",
                   "--no-block",
                   "--expand-environment=no",
                   "--unit=" + unit,
                   "--description=" + (op == "trim"
                                           ? QString("SSD TRIM")
                                           : QString("ext4 defragmentation")),
                   "--property=Type=exec",
                   "--property=RemainAfterExit=yes",
                   "--property=Nice=19",
                   "--property=IOSchedulingClass=idle",
                   "--property=NoNewPrivileges=yes",
                   "--property=ProtectHome=read-only",
                   "--property=ProtectSystem=strict",
                   "--property=ReadWritePaths=" + mount,
                   "--property=PrivateTmp=yes",
                   "--property=ProtectKernelTunables=yes",
                   "--property=ProtectControlGroups=yes",
                   "--property=RestrictAddressFamilies=AF_UNIX"};
  // A completed transient job must be stopped before it can be started again.
  QProcess stop;
  stop.start(HYPRSTACK_SYSTEMCTL, {"stop", unit});
  if (!stop.waitForFinished(10000)) {
    stop.kill();
    stop.waitForFinished();
    throw Failure("busy", "Could not stop previous maintenance task");
  }
  try {
    invoke("org.freedesktop.systemd1", "/org/freedesktop/systemd1",
           "org.freedesktop.systemd1.Manager", "ResetFailedUnit", {unit});
  } catch (const Failure &) {
  }
  args << (op == "trim" ? HYPRSTACK_FSTRIM : HYPRSTACK_E4DEFRAG) << "--"
       << mount;
  process.start(HYPRSTACK_SYSTEMD_RUN, args);
  if (!process.waitForFinished(10000)) {
    process.kill();
    process.waitForFinished();
    throw Failure("unavailable", "Could not start disk maintenance");
  }
  if (process.exitCode() != 0)
    throw Failure("unavailable",
                  QString::fromUtf8(process.readAllStandardError()));
}
} // namespace System
