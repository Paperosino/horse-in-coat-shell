#include "memory.hpp"
#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLockFile>
#include <QProcess>
#include <QRegularExpression>
#include <QSaveFile>
#include <QStorageInfo>
#include <QTextStream>
#include <QTimer>
#include <chrono>
#include <sys/stat.h>
#include <unistd.h>
using System::Failure;
namespace {
constexpr qint64 MiB = 1048576;
const QString ownerPath = "/run/hics-memory/owner.json";
const QString overridePath =
    "/etc/systemd/zram-generator.conf.d/90-hics-memory.conf";
const QByteArray generatorOverride =
    "# Managed by hics memory controller\n[zram0]\nzram-size = 0\n";
QJsonObject readJson(const QString &path) {
  QFile f(path);
  if (!f.open(QIODevice::ReadOnly))
    return {};
  auto d = QJsonDocument::fromJson(f.readAll());
  if (!d.isObject())
    throw Failure("failed", "Invalid controller state: " + path);
  return d.object();
}
void save(const QString &path, const QJsonObject &o) {
  auto bytes = QJsonDocument(o).toJson(QJsonDocument::Compact);
  QFile old(path);
  if (old.open(QIODevice::ReadOnly) && old.readAll() == bytes)
    return;
  QSaveFile f(path);
  if (!f.open(QIODevice::WriteOnly) || f.write(bytes) != bytes.size() ||
      !f.commit())
    throw Failure("failed", "Cannot save memory settings: " + path);
}
void write(const QString &path, const QByteArray &value) {
  QFile f(path);
  if (!f.open(QIODevice::WriteOnly) || f.write(value) != value.size())
    throw Failure("failed", "Cannot update " + path + ": " + f.errorString());
}
QString read(const QString &path) {
  QFile f(path);
  if (!f.open(QIODevice::ReadOnly))
    throw Failure("failed", "Cannot read " + path);
  return QString::fromUtf8(f.readAll()).trimmed();
}
void command(const QString &exe, const QStringList &args, int timeout = 30000) {
  QProcess p;
  p.start("/usr/bin/" + exe, args);
  if (!p.waitForFinished(timeout)) {
    p.kill();
    p.waitForFinished();
    throw Failure("failed",
                  exe + ": timed out; existing swap has been preserved");
  }
  if (p.exitStatus() != QProcess::NormalExit || p.exitCode() != 0)
    throw Failure("failed",
                  exe + ": " +
                      QString::fromUtf8(p.readAllStandardError()).trimmed());
}
void directory(const QString &path) {
  QDir().mkpath(path);
  struct stat s{};
  auto bytes = QFile::encodeName(path);
  if (lstat(bytes, &s) || !S_ISDIR(s.st_mode) || s.st_uid || s.st_mode & 0022)
    throw Failure("failed", "Unsafe memory controller directory: " + path);
}
QJsonArray swaps() { return Memory::metrics()["swaps"].toArray(); }
bool active(const QString &path) {
  for (auto row : swaps())
    if (row.toObject()["path"] == path)
      return true;
  return false;
}
QString device(const QJsonObject &owner) {
  auto d = owner["device"].toString();
  if (!d.isEmpty() &&
      !QRegularExpression("^/dev/zram[0-9]+$").match(d).hasMatch())
    throw Failure("failed", "Invalid managed ZRAM device");
  return d;
}
QStringList chunks() {
  QStringList r;
  for (auto name :
       QDir(Memory::SwapDirectory).entryList({"swap-*.swap"}, QDir::Files))
    if (QRegularExpression("^swap-[0-9]+\\.swap$").match(name).hasMatch())
      r << QString(Memory::SwapDirectory) + "/" + name;
  return r;
}
bool owned(const QString &path, const QJsonObject &owner) {
  return path == device(owner) || chunks().contains(path);
}
void headroom(const QJsonArray &rows) {
  double used = 0;
  for (auto r : rows)
    used += r.toObject()["used"].toDouble();
  if (used > 0 &&
      used * 1.25 + 512 * MiB > Memory::metrics()["available"].toDouble())
    throw Failure("failed", "Not enough free RAM to safely turn off swap. "
                            "Close applications and try again.");
}
void checkForeign(const QJsonObject &c, const QJsonObject &owner,
                  bool takeover) {
  QJsonArray foreign;
  for (auto r : swaps())
    if (!owned(r.toObject()["path"].toString(), owner))
      foreign.append(r);
  if (foreign.isEmpty())
    return;
  if (!takeover || !c["takeOver"].toBool() || foreign.size() != 1 ||
      foreign[0].toObject()["path"] != "/dev/zram0")
    throw Failure(
        "failed",
        "Another swap manager is active. hics can take over systemd ZRAM0; "
        "disable other swap devices before enabling this mode.");
  QProcess state;
  state.start("/usr/bin/systemctl",
              {"is-active", "--quiet", "systemd-zram-setup@zram0.service"});
  state.waitForFinished(5000);
  if (state.exitCode() != 0)
    throw Failure("failed",
                  "Existing ZRAM0 is not managed by systemd-zram-generator");
  headroom(foreign);
  directory("/etc/systemd/zram-generator.conf.d");
  QFile file(overridePath);
  if (file.exists() &&
      read(overridePath).toUtf8() != generatorOverride.trimmed())
    throw Failure("failed",
                  "Memory generator override belongs to another configuration");
  // Validate before draining; only our explicit override is persisted.
  command("systemctl", {"stop", "dev-zram0.swap"}, 90000);
  command("systemctl", {"stop", "systemd-zram-setup@zram0.service"}, 10000);
  write(overridePath, generatorOverride);
  command("systemctl", {"daemon-reload"});
}
void drain(QJsonObject &owner) {
  QJsonArray managed;
  for (auto row : swaps())
    if (owned(row.toObject()["path"].toString(), owner))
      managed.append(row);
  headroom(managed);
  for (auto row : managed)
    command("swapoff", {"--", row.toObject()["path"].toString()}, 90000);
  auto d = device(owner);
  if (!d.isEmpty() &&
      QFile::exists("/sys/block/" + QFileInfo(d).fileName() + "/reset")) {
    write("/sys/block/" + QFileInfo(d).fileName() + "/reset", "1");
    write("/sys/class/zram-control/hot_remove", d.mid(9).toUtf8());
  }
  for (const auto &path : chunks())
    if (!active(path))
      QFile::remove(path);
  owner = {};
  save(ownerPath, owner);
}
void restoreSystem() {
  QFile f(overridePath);
  if (f.exists() &&
      read(overridePath).toUtf8() == generatorOverride.trimmed()) {
    f.remove();
    command("systemctl", {"daemon-reload"});
    command("systemctl", {"start", "dev-zram0.swap"}, 90000);
  }
  const auto originalPath = QString(Memory::SwapDirectory) + "/original.json";
  auto original = readJson(originalPath);
  for (auto key : {"max_pool_percent", "compressor", "enabled"})
    if (original.contains(key))
      write(QString("/sys/module/zswap/parameters/") + key,
            original[key].toString().toUtf8());
  QFile::remove(originalPath);
}
void zram(QJsonObject &owner, const QJsonObject &c) {
  auto d = device(owner);
  if (!d.isEmpty() && active(d))
    return;
  if (!d.isEmpty() &&
      QFile::exists("/sys/block/" + QFileInfo(d).fileName() + "/reset")) {
    write("/sys/block/" + QFileInfo(d).fileName() + "/reset", "1");
    write("/sys/class/zram-control/hot_remove", d.mid(9).toUtf8());
    owner = {};
    save(ownerPath, owner);
  }
  if (!QFile::exists("/sys/class/zram-control/hot_add"))
    command("modprobe", {"zram"});
  auto id = read("/sys/class/zram-control/hot_add");
  bool ok = false;
  id.toUInt(&ok);
  if (!ok)
    throw Failure("failed", "Could not allocate ZRAM device");
  d = "/dev/zram" + id;
  owner["device"] = d;
  owner["zramMiB"] = c["zramMiB"];
  owner["compressor"] = c["compressor"];
  save(ownerPath, owner);
  auto base = "/sys/block/zram" + id + "/";
  auto algorithms = read(base + "comp_algorithm");
  if (!algorithms.replace('[', "").replace(']', "").split(' ').contains(
          c["compressor"].toString()))
    throw Failure("failed", "Requested ZRAM compressor is unavailable");
  write(base + "comp_algorithm", c["compressor"].toString().toUtf8());
  write(base + "disksize",
        QByteArray::number(qint64(c["zramMiB"].toInt()) * MiB));
  for (int i = 0; i < 50 && !QFile::exists(d); ++i)
    usleep(20000);
  command("mkswap", {"--quiet", d});
  command("swapon", {"--priority", "100", "--", d});
}
void growDisk(const QJsonObject &c) {
  double total = 0, used = 0;
  int count = 0;
  for (auto row : swaps()) {
    auto s = row.toObject();
    if (chunks().contains(s["path"].toString())) {
      total += s["size"].toDouble();
      used += s["used"].toDouble();
      ++count;
    }
  }
  if (total > 0 && used / total * 100 < c["diskThreshold"].toInt())
    return;
  qint64 limit =
      qint64(c["diskMaxMiB"].toInt()) *
      MiB; // Disk grows through additional areas, never by resizing live swap.
  qint64 amount =
      qMin(qint64(c["chunkMiB"].toInt()) * MiB, limit - qint64(total));
  if (amount < 64 * MiB)
    return;
  if (count >= 24)
    throw Failure("failed", "Swap area limit reached");
  QStorageInfo volume(Memory::SwapDirectory);
  if (volume.bytesAvailable() - amount < qint64(c["reserveMiB"].toInt()) * MiB)
    throw Failure("failed", "Disk reserve prevents adding more swap");
  if (!QList<QByteArray>{"btrfs", "ext4", "xfs"}.contains(
          volume.fileSystemType()))
    throw Failure("failed", "Managed swap requires Btrfs, ext4 or XFS");
  QString path;
  for (int i = 0; i < 32; ++i) {
    auto p = QString(Memory::SwapDirectory) + "/swap-" + QString::number(i) +
             ".swap";
    if (!active(p)) {
      path = p;
      break;
    }
  }
  if (path.isEmpty())
    throw Failure("failed", "No free swap area slot");
  QFileInfo existing(path);
  if (existing.isSymLink() || (existing.exists() && existing.ownerId() != 0))
    throw Failure("failed", "Unsafe swap file");
  QFile::remove(path);
  command("mkswap",
          {"--file", "--size", QString::number(amount), "--label",
           "hics-memory", path},
          90000);
  QFile::setPermissions(path, QFileDevice::ReadOwner | QFileDevice::WriteOwner);
  command("swapon", {"--priority", "10", "--", path});
}
class Controller {
  QJsonObject owner = readJson(ownerPath),
              previous =
                  readJson(Memory::RuntimePath).value("config").toObject();
  qint64 lowSince = 0;
  bool managed = false;

public:
  void tick() {
    QLockFile lock("/run/hics-memory/operation.lock");
    if (!lock.tryLock(0))
      return;
    QJsonObject report;
    try {
      auto c = Memory::configuration();
      auto mode = c["mode"].toString();
      auto m = Memory::metrics();
      if (mode == "system") {
        if (managed || !owner.isEmpty() || QFile::exists(overridePath)) {
          drain(owner);
          restoreSystem();
        }
        managed = false;
        previous = c;
        report = {{"stage", 0}, {"phase", "system"}};
      } else {
        managed = true;
        checkForeign(c, owner, false);
        if (!previous.isEmpty() &&
            (previous["mode"] != c["mode"] ||
             owner["zramMiB"].toInt(c["zramMiB"].toInt()) !=
                 c["zramMiB"].toInt() ||
             owner["compressor"].toString(c["compressor"].toString()) !=
                 c["compressor"].toString())) {
          drain(owner);
          m = Memory::metrics();
        }
        previous = c;
        bool zr = !device(owner).isEmpty() && active(device(owner));
        bool disk = false;
        double percent = 0;
        for (auto row : m["swaps"].toArray()) {
          auto s = row.toObject();
          if (s["path"] == device(owner) && s["size"].toDouble() > 0)
            percent = s["used"].toDouble() / s["size"].toDouble() * 100;
          if (chunks().contains(s["path"].toString()))
            disk = true;
        }
        int stage = Memory::targetStage(c,
                                        disk ? 2
                                        : zr ? 1
                                             : 0,
                                        m["ramPercent"].toDouble(), percent);
        double managedUsed = 0;
        for (auto row : m["swaps"].toArray())
          if (owned(row.toObject()["path"].toString(), owner))
            managedUsed += row.toObject()["used"].toDouble();
        if (mode == "smart" && c["releaseIdle"].toBool() && stage > 0 &&
            Memory::recoveryPressureLow(c, m["total"].toDouble(),
                                        m["available"].toDouble(),
                                        managedUsed)) {
          if (!lowSince)
            lowSince = std::chrono::duration_cast<std::chrono::seconds>(
                           std::chrono::steady_clock::now().time_since_epoch())
                           .count();
          if (std::chrono::duration_cast<std::chrono::seconds>(
                  std::chrono::steady_clock::now().time_since_epoch())
                      .count() -
                  lowSince >=
              c["releaseSeconds"].toInt()) {
            drain(owner);
            stage = 0;
            lowSince = 0;
          }
        } else
          lowSince = 0;
        if (stage == 0) {
          if (!owner.isEmpty() || disk || !chunks().isEmpty())
            drain(owner);
          if (m["zswapSupported"].toBool())
            write("/sys/module/zswap/parameters/enabled", "0");
        } else {
          if (mode != "zswap")
            zram(owner, c);
          if (stage == 2) {
            if (!m["zswapSupported"].toBool())
              throw Failure("failed", "This kernel does not support ZSwap");
            write("/sys/module/zswap/parameters/max_pool_percent",
                  QByteArray::number(c["poolPercent"].toInt()));
            write("/sys/module/zswap/parameters/compressor",
                  c["compressor"].toString().toUtf8());
            write("/sys/module/zswap/parameters/enabled", "1");
            growDisk(c);
          } else if (m["zswapSupported"].toBool())
            write("/sys/module/zswap/parameters/enabled", "0");
        }
        report = {{"stage", stage},
                  {"phase", stage == 0   ? "ram"
                            : stage == 1 ? "zram"
                                         : "zswap"},
                  {"zramPercent", percent}};
      }
    } catch (const std::exception &e) {
      report["error"] = QString::fromUtf8(e.what());
    }
    report["applied"] = !report.contains("error");
    report["config"] = Memory::configuration();
    report["updated"] = QDateTime::currentSecsSinceEpoch();
    save(Memory::RuntimePath, report);
  }
};
void configure(const QJsonObject &raw) {
  auto c = Memory::validate(raw);
  auto m = Memory::metrics();
  if (QStringList{"zswap", "both", "smart"}.contains(c["mode"].toString()) &&
      !m["zswapSupported"].toBool())
    throw Failure("failed", "This kernel does not support ZSwap");
  if (QStringList{"zram", "both", "smart"}.contains(c["mode"].toString()) &&
      qint64(c["zramMiB"].toInt()) * MiB > m["total"].toDouble() * 2)
    throw Failure("failed", "ZRAM size must not exceed twice the physical RAM");
  QLockFile lock("/run/hics-memory/operation.lock");
  if (!lock.tryLock(1000))
    throw Failure("busy", "Memory controller is busy; try again");
  auto owner = readJson(ownerPath);
  if (c["mode"] != "system")
    checkForeign(c, owner, true);
  auto originalPath = QString(Memory::SwapDirectory) + "/original.json";
  if (!QFile::exists(originalPath)) {
    QJsonObject original;
    if (m["zswapSupported"].toBool())
      for (auto key : {"enabled", "max_pool_percent", "compressor"})
        original[key] = read(QString("/sys/module/zswap/parameters/") + key);
    save(originalPath, original);
  }
  directory("/etc/hics");
  save(Memory::ConfigPath, c);
  lock.unlock();
  command("systemctl", {"start", "hics-memory.service"});
}
} // namespace
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  try {
    if (geteuid())
      throw Failure("denied", "Memory controller requires root");
    directory("/run/hics-memory");
    directory("/var/lib/hics-memory");
    chmod("/var/lib/hics-memory", 0700);
    if (!QFile::exists(Memory::SwapDirectory) &&
        QStorageInfo("/var/lib/hics-memory").fileSystemType() == "btrfs")
      command("btrfs", {"subvolume", "create", Memory::SwapDirectory});
    directory(Memory::SwapDirectory);
    chmod(Memory::SwapDirectory, 0700);
    if (app.arguments().size() == 3 && app.arguments()[1] == "configure") {
      auto doc = QJsonDocument::fromJson(app.arguments()[2].toUtf8());
      if (!doc.isObject())
        throw Failure("invalid", "Invalid memory configuration");
      configure(doc.object());
      return 0;
    }
    if (app.arguments().size() != 1)
      throw Failure("invalid", "Usage: hics-memory [configure JSON]");
    QLockFile singleton("/run/hics-memory/daemon.lock");
    if (!singleton.tryLock())
      throw Failure("busy", "Memory controller is already running");
    Controller controller;
    QTimer timer;
    QObject::connect(&timer, &QTimer::timeout, &app,
                     [&] { controller.tick(); });
    controller.tick();
    timer.start(5000);
    return app.exec();
  } catch (const std::exception &e) {
    QTextStream(stderr) << e.what() << Qt::endl;
    return 1;
  }
}
