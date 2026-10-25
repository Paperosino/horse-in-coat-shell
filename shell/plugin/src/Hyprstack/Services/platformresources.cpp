#include "platformresources.hpp"
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QRegularExpression>
#include <QStandardPaths>
using namespace Qt::StringLiterals;
namespace hyprstack::services {
bool PlatformResources::hasExecutable(const QString &name) const {
  return !QStandardPaths::findExecutable(name).isEmpty();
}
QVariantList PlatformResources::displayBuses() const {
  QVariantList rows;
  for (const auto &entry :
       QDir(u"/sys/class/drm"_s)
           .entryInfoList(QDir::Dirs | QDir::NoDotAndDotDot)) {
    auto name = entry.fileName();
    name.remove(QRegularExpression(u"^card[0-9]+-"_s));
    if (name.startsWith(u"eDP-"_s) || name.startsWith(u"LVDS-"_s) ||
        !entry.fileName().contains(u'-'))
      continue;
    const auto ddc =
        QFileInfo(entry.filePath() + u"/ddc"_s).canonicalFilePath();
    if (ddc.isEmpty())
      continue;
    auto bus = QFileInfo(ddc).fileName();
    if (!bus.startsWith(u"i2c-"_s))
      continue;
    bool valid;
    const auto number = bus.mid(4).toUInt(&valid);
    if (valid)
      rows << QVariantMap{{u"connector"_s, name},
                          {u"busNum"_s, QString::number(number)}};
  }
  return rows;
}
QVariantMap PlatformResources::backlight() const {
  for (const auto &entry :
       QDir(u"/sys/class/backlight"_s)
           .entryInfoList(QDir::Dirs | QDir::NoDotAndDotDot)) {
    auto number = [&](const QString &name) {
      QFile f(entry.filePath() + u'/' + name);
      if (!f.open(QIODevice::ReadOnly))
        return -1.;
      bool ok;
      double value = f.read(64).trimmed().toDouble(&ok);
      return ok ? value : -1.;
    };
    const double current = number(u"brightness"_s),
                 maximum = number(u"max_brightness"_s);
    if (current >= 0 && maximum > 0)
      return {{u"value"_s, current / maximum}, {u"device"_s, entry.fileName()}};
  }
  return {};
}
} // namespace hyprstack::services
