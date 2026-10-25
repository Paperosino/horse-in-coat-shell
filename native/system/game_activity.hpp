#pragma once
#include <QDir>
#include <QDirIterator>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QString>
namespace hics::game {
inline QByteArray processStart(const QString &path) {
  QFile file(path);
  if (!file.open(QIODevice::ReadOnly))
    return {};
  const auto stat = file.read(4096);
  const auto end = stat.lastIndexOf(')');
  return end < 0 ? QByteArray() : stat.mid(end + 2).split(' ').value(19);
}
// A user may defer automatic reclamation, never arbitrary privileged commands.
// Bind the marker to a live same-UID process and its start time (PID reuse
// safe).
inline bool active(const QString &runtime = QStringLiteral("/run/user"),
                   const QString &proc = QStringLiteral("/proc")) {
  for (const auto &user :
       QDir(runtime).entryInfoList(QDir::Dirs | QDir::NoDotAndDotDot)) {
    bool valid = false;
    const uint uid = user.fileName().toUInt(&valid);
    if (!valid || user.isSymLink() || user.ownerId() != uid)
      continue;
    const QString folder = user.filePath() + QStringLiteral("/hics");
    if (QFileInfo(folder).isSymLink())
      continue;
    QDirIterator markers(folder, {QStringLiteral("game-mode-*.json")},
                         QDir::Files | QDir::NoSymLinks);
    int checked = 0;
    while (markers.hasNext() && checked++ < 64) {
      const QFileInfo info = markers.nextFileInfo();
      const QString path = info.filePath();
      if (info.isSymLink() || !info.isFile() || info.ownerId() != uid ||
          info.size() > 4096)
        continue;
      QFile file(path);
      if (!file.open(QIODevice::ReadOnly))
        continue;
      const auto marker = QJsonDocument::fromJson(file.read(4097)).object();
      const qint64 pid = marker.value(QStringLiteral("pid")).toInteger();
      if (pid < 1 || !marker.value(QStringLiteral("active")).toBool())
        continue;
      const QString process = proc + u'/' + QString::number(pid);
      if (QFileInfo(process).ownerId() != uid)
        continue;
      const auto start = processStart(process + QStringLiteral("/stat"));
      if (!start.isEmpty() &&
          start == marker.value(QStringLiteral("start")).toString().toLatin1())
        return true;
    }
  }
  return false;
}
} // namespace hics::game
