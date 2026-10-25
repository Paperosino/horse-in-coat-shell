#pragma once
#include <QJSValue>
#include <QObject>
#include <QVariantMap>
#include <QtQmlIntegration/qqmlintegration.h>
#include <memory>
#include <thread>
namespace hyprstack::services {
class NetworkService : public QObject {
  Q_OBJECT
  QML_ELEMENT
  QML_SINGLETON
  Q_PROPERTY(QVariantMap state READ state NOTIFY stateChanged)
public:
  struct Worker;
  explicit NetworkService(QObject *parent = nullptr);
  ~NetworkService() override;
  QVariantMap state() const { return m_state; }
  Q_INVOKABLE int request(const QString &operation,
                          const QVariantMap &args = {});
  Q_INVOKABLE QVariantMap interfaceStats(const QString &interface) const;
signals:
  void stateChanged();
  void operationFinished(int id, const QVariantMap &result);

private:
  std::shared_ptr<Worker> m_worker;
  std::thread m_thread;
  QVariantMap m_state;
  int m_serial = 0;
};
} // namespace hyprstack::services
