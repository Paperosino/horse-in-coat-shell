#pragma once
#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QStandardPaths>
namespace hics::performance {
inline QString helperPath(const QString &name) {
  const auto configured = qEnvironmentVariable("HICS_HELPER_DIR");
  const auto application = QCoreApplication::applicationDirPath();
  // Wrapper location handles Nix and user prefixes; the relative fallback
  // handles the bundled <prefix>/share/hics/qs/bin runtime launched directly.
  for (const auto &directory :
       {configured, application,
        QDir(application)
            .absoluteFilePath(QStringLiteral("../../../../bin"))}) {
    if (directory.isEmpty())
      continue;
    const auto candidate = QDir(directory).filePath(name);
    if (QFileInfo(candidate).isExecutable())
      return candidate;
  }
  return QStandardPaths::findExecutable(name);
}
} // namespace hics::performance
