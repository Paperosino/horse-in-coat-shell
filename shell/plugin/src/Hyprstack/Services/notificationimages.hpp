#pragma once
#include <QJSValue>
#include <QObject>
#include <QThreadPool>
#include <QtQmlIntegration/qqmlintegration.h>
namespace hyprstack::services {
class NotificationImages : public QObject {
  Q_OBJECT
  QML_ELEMENT
  QML_SINGLETON
public:
  explicit NotificationImages(QObject *parent = nullptr);
  ~NotificationImages() override;
  Q_INVOKABLE void cache(const QString &source, bool original,
                         QJSValue callback);

private:
  QThreadPool m_pool;
  int m_pending = 0;
  qint64 m_pendingBytes = 0;
};
} // namespace hyprstack::services
