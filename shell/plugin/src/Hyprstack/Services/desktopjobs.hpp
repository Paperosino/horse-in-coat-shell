#pragma once
#include <QJSValue>
#include <QObject>
#include <QPointer>
#include <QVariantList>
#include <QVariantMap>
#include <QtQmlIntegration/qqmlintegration.h>
namespace hyprstack::services {
class DesktopJobs : public QObject {
  Q_OBJECT
  QML_ELEMENT
  QML_SINGLETON
  Q_PROPERTY(QVariantList jobs READ jobs NOTIFY changed)
  Q_PROPERTY(QVariantMap comfort READ comfort NOTIFY changed)
  Q_PROPERTY(bool available READ available NOTIFY changed)
public:
  explicit DesktopJobs(QObject *parent = nullptr);
  QVariantList jobs() const { return m_jobs; }
  QVariantMap comfort() const { return m_comfort; }
  bool available() const { return m_available; }
  Q_INVOKABLE void request(const QString &, const QVariantMap &,
                           QJSValue callback = QJSValue(),
                           QObject *owner = nullptr);
  Q_INVOKABLE void details(const QString &, QJSValue callback,
                           QObject *owner = nullptr);
  Q_INVOKABLE void acknowledge(const QString &id = QString());
  Q_INVOKABLE void cancel(const QString &id);
  Q_INVOKABLE void retry(const QString &id);
  Q_INVOKABLE void refresh();
  Q_INVOKABLE void report(const QString &source, const QString &operation,
                          const QString &phase, double progress = -1,
                          const QString &error = QString());
signals:
  void changed();
private slots:
  void stateChanged(const QString &);
  void completed(const QString &, const QString &);

private:
  struct Pending {
    QJSValue callback;
    QPointer<QObject> owner;
    bool guarded = false;
  };
  void deliver(const Pending &, const QVariantMap &);
  QHash<QString, Pending> m_pending;
  QVariantList m_jobs;
  QVariantMap m_comfort;
  bool m_available = false;
};
} // namespace hyprstack::services
