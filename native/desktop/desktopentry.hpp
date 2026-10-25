#pragma once
#include <QByteArray>
#include <QDir>
#include <QFileInfo>
#include <QSaveFile>
#include <QStringList>
#include <stdexcept>
namespace HicsDesktop {
// Desktop-entry files are not Qt INI files: QSettings escapes their group and
// localized key names and can rewrite Exec quoting. Change only Hidden.
inline void saveAutostart(const QString &target, const QByteArray &source,
                          bool hidden) {
  auto lines = QString::fromUtf8(source).split('\n');
  bool inEntry = false, found = false, changed = false;
  int insert = -1;
  for (int index = 0; index < lines.size(); ++index) {
    auto line = lines[index].trimmed();
    if (line.startsWith(QChar(0xfeff)))
      line.remove(0, 1);
    if (line.startsWith('[') && line.endsWith(']')) {
      inEntry = line == "[Desktop Entry]";
      if (inEntry) {
        found = true;
        if (insert < 0)
          insert = index + 1;
      }
      continue;
    }
    if (!inEntry || line.startsWith('#'))
      continue;
    const int equal = line.indexOf('=');
    if (equal >= 0 && line.left(equal).trimmed() == "Hidden") {
      lines[index] = QString("Hidden=") + (hidden ? "true" : "false") +
                     (lines[index].endsWith('\r') ? "\r" : "");
      changed = true;
    }
  }
  if (!found || QFileInfo(target).isSymLink())
    throw std::runtime_error(
        "Cannot change a malformed or symbolic-link autostart entry");
  if (!changed)
    lines.insert(insert, QString("Hidden=") + (hidden ? "true" : "false"));
  auto bytes = lines.join('\n').toUtf8();
  if (!bytes.endsWith('\n'))
    bytes += '\n';
  QDir().mkpath(QFileInfo(target).absolutePath());
  QSaveFile file(target);
  if (!file.open(QIODevice::WriteOnly) ||
      !file.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner) ||
      file.write(bytes) != bytes.size() || !file.commit())
    throw std::runtime_error("Cannot save the autostart entry");
}
} // namespace HicsDesktop
