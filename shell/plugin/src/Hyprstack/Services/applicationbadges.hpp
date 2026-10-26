#pragma once
#include <QObject>
#include <QQmlEngine>
#include <QDBusMessage>
#include <QDBusServiceWatcher>
#include <QVariantMap>
#include <QHash>
namespace hyprstack::services {
// LauncherEntry is a session-local integration, not a trusted unread database.
class ApplicationBadges final : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QVariantMap entries READ entries NOTIFY changed)
public:
    explicit ApplicationBadges(QObject *parent=nullptr);
    ~ApplicationBadges() override;
    QVariantMap entries() const;
    Q_INVOKABLE static QString canonicalId(QString id);
signals:
    void changed();
private slots:
    void update(const QString &uri, const QVariantMap &properties, const QDBusMessage &message);
private:
    struct Entry { QString owner; qint64 count=0; bool visible=false; };
    void forgetOwner(const QString &owner);
    QHash<QString,Entry> m_entries;
    QDBusServiceWatcher m_watcher;
    bool m_ownsUnity = false;
};
}
