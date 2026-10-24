#include "graphicscache.hpp"
#include <QCryptographicHash>
#include <QDir>
#include <QFileInfo>
#include <QGuiApplication>
#include <QQuickGraphicsConfiguration>
#include <QQuickWindow>
#include <QScreen>
#include <QStandardPaths>
namespace hyprstack::components {
using namespace Qt::StringLiterals;
GraphicsCache::GraphicsCache(QQuickItem *parent) : QQuickItem(parent) {
  connect(this, &QQuickItem::windowChanged, this, [this] { configure(); });
}
void GraphicsCache::componentComplete() {
  QQuickItem::componentComplete();
  m_complete = true;
  configure();
}
void GraphicsCache::configure() {
  auto *target = window();
  if (!m_complete || m_key.isEmpty() || !target ||
      target->isSceneGraphInitialized() ||
      target->property("_hics_pipeline_cache").toBool())
    return;
  // Explicit administrator/application settings always take precedence.
  for (const auto *name :
       {"QSG_RHI_PIPELINE_CACHE_LOAD", "QSG_RHI_PIPELINE_CACHE_SAVE"})
    if (qEnvironmentVariableIsSet(name))
      return;
  for (const auto* name : {"QT_DISABLE_SHADER_DISK_CACHE", "QSG_RHI_DISABLE_SHADER_DISK_CACHE"})
    if (qEnvironmentVariableIntValue(name)!=0) return;
  auto config = target->graphicsConfiguration();
  if (!config.pipelineCacheLoadFile().isEmpty() || !config.pipelineCacheSaveFile().isEmpty() || !config.isAutomaticPipelineCacheEnabled() ||
      QGuiApplication::testAttribute(Qt::AA_DisableShaderDiskCache))
    return;
  const auto screen = target->screen();
  const auto identity = m_key + u':' + (screen ? screen->name() : QString()) +
                        u':' +
                        QString::number(int(QQuickWindow::graphicsApi()));
  const auto key = QString::fromLatin1(
      QCryptographicHash::hash(identity.toUtf8(), QCryptographicHash::Sha256)
          .toHex());
  const auto directory =
      QStandardPaths::writableLocation(QStandardPaths::CacheLocation) +
      u"/hics-pipelines/"_s + QString::fromLatin1(qVersion());
  if (!QDir().mkpath(directory))
    return;
  const auto path = directory + u'/' + key + u".qpc"_s;
  // Qt validates backend/device/driver metadata; these files never ship in
  // the package and no pipeline compilation or rendering happens here.
  config.setAutomaticPipelineCache(false);
  if (QFileInfo::exists(path))
    config.setPipelineCacheLoadFile(path);
  config.setPipelineCacheSaveFile(path);
  target->setGraphicsConfiguration(config);
  target->setProperty("_hics_pipeline_cache", true);
}
} // namespace hyprstack::components
