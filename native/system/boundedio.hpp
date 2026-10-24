#pragma once
#include "backend.hpp"
#include <QFile>
namespace System {
inline QByteArray readBounded(QFile& file, qint64 limit) {
  if ((!file.isSequential() && file.size() > limit))
    throw Failure("invalid", "Controller file exceeds its size limit: " + file.fileName());
  // Small sysfs files must not allocate the entire safety limit on each tick.
  QByteArray bytes;
  for (;;) {
    const auto part = file.read(qMin<qint64>(4096, limit + 1 - bytes.size()));
    if (part.isEmpty()) break;
    bytes += part;
    if (bytes.size() > limit)
      throw Failure("invalid", "Controller file exceeds its size limit: " + file.fileName());
  }
  if (file.error() != QFileDevice::NoError)
    throw Failure("failed", "Cannot read controller file: " + file.fileName());
  return bytes;
}
}
