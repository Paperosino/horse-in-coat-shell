#include "nvmlmetrics.hpp"
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <csignal>
#include <iostream>
#include <sys/prctl.h>
#include <unistd.h>
namespace {
QByteArray read(const QString &path) {
  QFile f(path);
  return f.open(QIODevice::ReadOnly) ? f.read(256).trimmed() : QByteArray();
}
struct Sensors {
  QStringList busy, gpu, cpu;
  Sensors() {
    auto root = qEnvironmentVariable("HICS_GPU_SYSFS_ROOT");
    if (root.isEmpty())
      root = QStringLiteral("/sys");
    for (const auto &card :
         QDir(root + QStringLiteral("/class/drm"))
             .entryList({QStringLiteral("card*")}, QDir::Dirs)) {
      if (!QRegularExpression(QStringLiteral("^card[0-9]+$"))
               .match(card)
               .hasMatch())
        continue;
      const auto path = root + QStringLiteral("/class/drm/") + card +
                        QStringLiteral("/device/gpu_busy_percent");
      if (QFile::exists(path))
        busy << path;
    }
    const auto hwmon = root + QStringLiteral("/class/hwmon/");
    for (const auto &hw :
         QDir(hwmon).entryList(QDir::Dirs | QDir::NoDotAndDotDot)) {
      const auto dir = hwmon + hw + QStringLiteral("/");
      const auto name = read(dir + QStringLiteral("name"));
      const bool isCpu = name == "coretemp" || name == "k10temp" ||
                         name == "zenpower" || name == "cpu_thermal";
      const bool isGpu = name == "amdgpu" || name == "nouveau";
      if (!isCpu && !isGpu)
        continue;
      for (const auto &file :
           QDir(dir).entryList({QStringLiteral("temp*_input")}, QDir::Files)) {
        auto label = file;
        label.replace(QStringLiteral("_input"), QStringLiteral("_label"));
        const auto text = read(dir + label);
        const bool package = text.startsWith("Package id ") || text == "Tdie" ||
                             text == "Tctl" || name == "cpu_thermal";
        const bool die = text == "edge" || text == "junction" ||
                         text == "GPU core" || text.isEmpty();
        if ((isCpu && package) || (isGpu && die))
          (isCpu ? cpu : gpu) << dir + file;
      }
    }
  }
  static double maximum(const QStringList &paths, bool temperature) {
    double result = -1;
    for (const auto &path : paths) {
      bool ok = false;
      auto v = read(path).toDouble(&ok);
      if (temperature)
        v /= 1000.0;
      if (ok && v >= 0 && v <= (temperature ? 149 : 100))
        result = std::max(result, v);
    }
    return result;
  }
};
} // namespace
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  const auto parent = getppid();
  prctl(PR_SET_PDEATHSIG, SIGTERM);
  if (getppid() != parent)
    return 1;
  hics::performance::NvidiaMetrics metrics;
  Sensors sensors;
  char command[32];
  while (std::cin.getline(command, sizeof(command))) {
    const bool thermal = std::string_view(command) == "thermal";
    const bool nvidia = std::string_view(command) == "nvidia",
               generic = std::string_view(command) == "generic";
    if (!thermal && !nvidia && !generic &&
        std::string_view(command) != "sample")
      return 2;
    double usage = nvidia ? -1 : Sensors::maximum(sensors.busy, false),
           temperature = nvidia ? -1 : Sensors::maximum(sensors.gpu, true);
    if (!generic)
      metrics.sample(usage, temperature);
    const auto cpu = thermal ? Sensors::maximum(sensors.cpu, true) : -1;
    const QJsonObject result{{QStringLiteral("available"),
                              usage >= 0 || temperature >= 0 || cpu >= 0},
                             {QStringLiteral("usage"), usage},
                             {QStringLiteral("temperature"), temperature},
                             {QStringLiteral("cpuTemperature"), cpu}};
    std::cout
        << QJsonDocument(result).toJson(QJsonDocument::Compact).constData()
        << std::endl;
  }
}
