#include "memory.hpp"
#include "boundedio.hpp"
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QProcess>
#include <QRegularExpression>
#include <cmath>
namespace Memory {
QJsonObject defaults() {
  return {{"mode", "system"},    {"zramMiB", 4096},       {"ramThreshold", 75},
          {"zramThreshold", 80}, {"poolPercent", 20},     {"chunkMiB", 1024},
          {"diskMaxMiB", 8192},  {"diskThreshold", 75},   {"reserveMiB", 4096},
          {"hysteresis", 10},    {"releaseSeconds", 120}, {"releaseIdle", true},
          {"takeOver", false},   {"compressor", "zstd"}};
}
QJsonObject configuration() {
  QFile file(ConfigPath);
  if (!file.open(QIODevice::ReadOnly))
    return defaults();
  auto doc = QJsonDocument::fromJson(System::readBounded(file, 256 * 1024));
  if (!doc.isObject())
    throw System::Failure("failed", "Invalid memory configuration");
  return validate(doc.object());
}
QJsonObject validate(const QJsonObject &o) {
  auto c = defaults();
  for (auto it = o.begin(); it != o.end(); ++it) {
    if (!c.contains(it.key()))
      throw System::Failure("invalid", "Unknown memory setting: " + it.key());
    c[it.key()] = it.value();
  }
  if (!c["mode"].isString() ||
      !QStringList{"system", "off", "zram", "zswap", "both", "smart"}.contains(
          c["mode"].toString()))
    throw System::Failure("invalid", "Invalid memory mode");
  if (!c["compressor"].isString() ||
      !QStringList{"zstd", "lz4", "lzo-rle"}.contains(
          c["compressor"].toString()))
    throw System::Failure("invalid", "Invalid memory compressor");
  const QMap<QString, QPair<int, int>> bounds{
      {"zramMiB", {64, 1048576}},  {"ramThreshold", {20, 95}},
      {"zramThreshold", {20, 95}}, {"poolPercent", {1, 50}},
      {"chunkMiB", {64, 16384}},   {"diskMaxMiB", {64, 1048576}},
      {"diskThreshold", {20, 95}}, {"reserveMiB", {512, 1048576}},
      {"hysteresis", {3, 30}},     {"releaseSeconds", {15, 3600}}};
  for (auto it = bounds.begin(); it != bounds.end(); ++it) {
    auto v = c[it.key()];
    if (!v.isDouble() || v.toDouble() != std::floor(v.toDouble()) ||
        v.toDouble() < it->first || v.toDouble() > it->second)
      throw System::Failure("invalid",
                            "Memory setting is out of range: " + it.key());
  }
  for (auto key : {"releaseIdle", "takeOver"})
    if (!c[key].isBool())
      throw System::Failure("invalid", "Invalid memory switch");
  if (c["chunkMiB"].toInt() > c["diskMaxMiB"].toInt() ||
      c["hysteresis"].toInt() >= c["ramThreshold"].toInt() ||
      c["hysteresis"].toInt() >= c["zramThreshold"].toInt())
    throw System::Failure("invalid", "Inconsistent memory thresholds or sizes");
  return c;
}
QJsonObject metrics() {
  QFile mem("/proc/meminfo");
  QJsonObject result;
  if (mem.open(QIODevice::ReadOnly))
    for (const auto &line : mem.readAll().split('\n')) {
      auto fields = line.simplified().split(' ');
      if (fields.size() > 1 &&
          (fields[0] == "MemTotal:" || fields[0] == "MemAvailable:"))
        result[fields[0] == "MemTotal:" ? "total" : "available"] =
            double(fields[1].toLongLong()) * 1024;
    }
  auto total = result["total"].toDouble();
  result["ramPercent"] =
      total > 0 ? (1 - result["available"].toDouble() / total) * 100 : 0;
  QFile swaps("/proc/swaps");
  QJsonArray devices;
  if (swaps.open(QIODevice::ReadOnly)) {
    auto lines = swaps.readAll().split('\n');
    for (int i = 1; i < lines.size(); ++i) {
      auto f = lines[i].simplified().split(' ');
      if (f.size() < 5)
        continue;
      devices.append(QJsonObject{{"path", QString::fromUtf8(f[0])},
                                 {"size", double(f[2].toLongLong()) * 1024},
                                 {"used", double(f[3].toLongLong()) * 1024},
                                 {"priority", f[4].toInt()}});
    }
  }
  result["swaps"] = devices;
  QFile enabled("/sys/module/zswap/parameters/enabled");
  result["zswapSupported"] = enabled.exists();
  result["zswapEnabled"] =
      enabled.open(QIODevice::ReadOnly) && enabled.readAll().trimmed() == "Y";
  result["zramSupported"] = QFile::exists("/sys/class/zram-control/hot_add") ||
                            QFile::exists("/sys/module/zram");
  return result;
}
bool recoveryPressureLow(const QJsonObject &c, double total, double available,
                         double swapped) {
  // Conservatively assume every swapped byte must remain in RAM after drain.
  // Compression can lower current usage below the activation threshold on its
  // own; that is not evidence that the workload no longer needs swap.
  return total > 0 && available >= swapped &&
         (1.0 - (available - swapped) / total) * 100 <
             c["ramThreshold"].toInt() - c["hysteresis"].toInt();
}
int targetStage(const QJsonObject &c, int stage, double ram, double zram) {
  auto mode = c["mode"].toString();
  if (mode == "off" || mode == "system")
    return 0;
  if (mode == "zram")
    return 1;
  if (mode == "zswap" || mode == "both")
    return 2;
  if (stage == 0 && ram >= c["ramThreshold"].toInt())
    return 1;
  if (stage == 1 && zram >= c["zramThreshold"].toInt())
    return 2;
  return stage;
}
} // namespace Memory
namespace System {
QJsonObject memoryStatus() {
  auto result = Memory::metrics();
  result["config"] = Memory::configuration();
  QFile runtime(Memory::RuntimePath);
  if (runtime.open(QIODevice::ReadOnly))
    result["controller"] = QJsonDocument::fromJson(runtime.readAll()).object();
  return result;
}
void memoryApply(const QJsonObject &o) {
  auto config = Memory::validate(o);
  QProcess p;
  p.start(HYPRSTACK_SYSTEMD_RUN,
          {"--quiet", "--wait", "--pipe", "--collect",
           "--unit=hics-memory-configure", "--property=Type=exec",
           "--property=UMask=0077", HYPRSTACK_MEMORY_EXECUTABLE, "configure",
           encode(config)});
  if (!p.waitForFinished(120000)) {
    p.kill();
    p.waitForFinished();
    throw Failure("busy", "Memory configuration is still busy; check "
                          "hics-memory-configure.service");
  }
  if (p.exitCode() != 0)
    throw Failure("memory-failed",
                  QString::fromUtf8(p.readAllStandardError()).trimmed());
}
} // namespace System
