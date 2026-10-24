#pragma once
#include <QList>
#include <QMap>
#include <QStringList>
#include <cmath>
#include <optional>
namespace hics::performance {
struct Visit {
  QString id, executable;
  qint64 time;
};
struct Prediction {
  QString id, executable;
  int confidence;
};
inline std::optional<Prediction> predict(const QList<Visit> &visits,
                                         const QString &current,
                                         const QStringList &allowed,
                                         int minimum, int confidence,
                                         qint64 now, int maximumAge) {
  if (visits.isEmpty() || visits.last().id != current ||
      visits.last().time > now || now - visits.last().time > maximumAge)
    return {};
  QMap<QString, int> counts;
  QMap<QString, QString> executables;
  int observations = 0;
  for (qsizetype i = 1; i < visits.size(); ++i) {
    const auto &from = visits[i - 1];
    const auto &to = visits[i];
    if (from.id != current || to.id == current || to.time < from.time ||
        to.time - from.time > 600 || to.time > now ||
        now - from.time > 30 * 86400)
      continue;
    ++counts[to.id];
    ++observations;
    executables[to.id] = to.executable;
  }
  if (!observations)
    return {};
  QString next;
  int count = 0;
  for (auto it = counts.begin(); it != counts.end(); ++it)
    if (it.value() > count) {
      next = it.key();
      count = it.value();
    }
  if (count < minimum || count * 100 / observations < confidence ||
      !allowed.contains(next))
    return {};
  return Prediction{next, executables.value(next), count * 100 / observations};
}
inline bool prefetchBudget(double cpu, double memory, double memoryStall,
                           double ioStall, int cpuLimit, int memoryLimit) {
  return std::isfinite(cpu) && std::isfinite(memory) &&
         std::isfinite(memoryStall) && std::isfinite(ioStall) && cpu >= 0 &&
         memory >= 0 && cpu < cpuLimit && memory < memoryLimit &&
         memoryStall >= 0 && memoryStall <= .1 && ioStall >= 0 && ioStall <= 1;
}
} // namespace hics::performance
