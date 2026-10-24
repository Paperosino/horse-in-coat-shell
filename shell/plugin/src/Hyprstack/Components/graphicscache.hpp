#pragma once
#include <QQuickItem>
#include <QtQmlIntegration/qqmlintegration.h>
namespace hyprstack::components {
// Configure before scene-graph creation. Each logical panel/output gets its
// own Qt-managed cache, rather than all threaded windows overwriting one file.
class GraphicsCache : public QQuickItem {
  Q_OBJECT
  QML_ELEMENT
  Q_PROPERTY(QString cacheKey MEMBER m_key)
public:
  explicit GraphicsCache(QQuickItem *parent = nullptr);

protected:
  void componentComplete() override;

private:
  void configure();
  QString m_key;
  bool m_complete = false;
};
} // namespace hyprstack::components
