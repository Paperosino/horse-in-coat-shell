#pragma once
#include <QObject>
#include <QQmlEngine>
#include <QtQmlIntegration/qqmlintegration.h>
#include <QVariantList>
#include <QJsonObject>
#include <QTimer>
namespace hyprstack::services {
class NotificationPolicy : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QVariantList applications READ applications NOTIFY changed)
    Q_PROPERTY(bool paused READ paused NOTIFY changed)
    Q_PROPERTY(qint64 pausedUntil READ pausedUntil NOTIFY changed)
    Q_PROPERTY(QString error READ error NOTIFY changed)
public:
    explicit NotificationPolicy(QObject *parent = nullptr);
    ~NotificationPolicy() override;
    QVariantList applications() const;
    bool paused() const;
    qint64 pausedUntil() const { return m_until; }
    QString error() const { return m_error; }
    Q_INVOKABLE void observe(const QString &id, const QString &name);
    Q_INVOKABLE void setRule(const QString &id, const QString &mode);
    Q_INVOKABLE QString rule(const QString &id) const;
    Q_INVOKABLE void pauseFor(int minutes);
    Q_INVOKABLE void resume();
private:
    void save();
    QJsonObject m_apps;
    qint64 m_until = 0;
    QString m_path, m_error;
    QTimer m_expiry, m_saveTimer;
signals:
    void changed();
};
}
