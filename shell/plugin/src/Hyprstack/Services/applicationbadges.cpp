#include "applicationbadges.hpp"
#include <QDBusConnection>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QRegularExpression>
#include <algorithm>
namespace hyprstack::services {
QString ApplicationBadges::canonicalId(QString id) {
    if (id.startsWith(u"application://")) id.remove(0,14);
    if (id.endsWith(u".desktop",Qt::CaseInsensitive)) id.chop(8);
    if (!QRegularExpression(QStringLiteral("^[A-Za-z0-9][A-Za-z0-9_.+@-]{0,240}$")).match(id).hasMatch()) return {};
    return id.toLower();
}
ApplicationBadges::ApplicationBadges(QObject *parent):QObject(parent),m_watcher(this) {
    auto bus=QDBusConnection::sessionBus();
    m_ownsUnity=bus.registerService(QStringLiteral("com.canonical.Unity"));
    m_watcher.setConnection(bus);
    m_watcher.setWatchMode(QDBusServiceWatcher::WatchForUnregistration);
    connect(&m_watcher,&QDBusServiceWatcher::serviceUnregistered,this,[this](const QString &owner) {
        forgetOwner(owner);
    });
    bus.connect({}, {}, QStringLiteral("com.canonical.Unity.LauncherEntry"), QStringLiteral("Update"),
                this,SLOT(update(QString,QVariantMap,QDBusMessage)));
}
void ApplicationBadges::forgetOwner(const QString &owner) {
    bool removed=false;
    for(auto it=m_entries.begin();it!=m_entries.end();) {
        if(it->owner==owner){it=m_entries.erase(it);removed=true;}else ++it;
    }
    m_watcher.removeWatchedService(owner);
    if(removed)emit changed();
}
ApplicationBadges::~ApplicationBadges() {
    if(m_ownsUnity)QDBusConnection::sessionBus().unregisterService(QStringLiteral("com.canonical.Unity"));
}
QVariantMap ApplicationBadges::entries() const {
    QVariantMap result;
    for(auto it=m_entries.cbegin();it!=m_entries.cend();++it)
        result.insert(it.key(),QVariantMap{{QStringLiteral("count"),it->count},{QStringLiteral("visible"),it->visible}});
    return result;
}
void ApplicationBadges::update(const QString &uri,const QVariantMap &properties,const QDBusMessage &message) {
    if(!uri.startsWith(u"application://") || !message.service().startsWith(u':'))return;
    const auto id=canonicalId(uri);if(id.isEmpty())return;
    const auto countKey=QStringLiteral("count"),visibleKey=QStringLiteral("count-visible");
    if(!properties.contains(countKey)&&!properties.contains(visibleKey))return;
    if(!m_entries.contains(id)&&m_entries.size()>=512)return;
    if(!m_watcher.watchedServices().contains(message.service())&&m_watcher.watchedServices().size()>=128)return;
    auto value=m_entries.value(id);
    const auto old=value;
    // Do not inherit another sender's count when ownership changes.
    if(value.owner!=message.service())value={message.service(),0,false};
    if(properties.contains(countKey)) {
        bool ok=false;auto count=properties.value(countKey).toLongLong(&ok);
        if(!ok)return;
        value.count=std::clamp<qint64>(count,0,999999);
    }
    if(properties.contains(visibleKey)) {
        if(properties.value(visibleKey).metaType().id()!=QMetaType::Bool)return;
        value.visible=properties.value(visibleKey).toBool();
    }
    m_entries.insert(id,value);
    const bool newOwner=!m_watcher.watchedServices().contains(value.owner);
    m_watcher.addWatchedService(value.owner);
    if(newOwner) {
        // A short-lived emitter may disconnect before its watch is installed.
        // Reconcile asynchronously, never block the GUI on the bus daemon.
        auto check=QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.DBus"),QStringLiteral("/org/freedesktop/DBus"),QStringLiteral("org.freedesktop.DBus"),QStringLiteral("NameHasOwner"));
        check<<value.owner;
        auto *pending=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(check,1000),this);
        connect(pending,&QDBusPendingCallWatcher::finished,this,[this,pending,owner=value.owner] {
            const QDBusPendingReply<bool> reply=*pending;
            pending->deleteLater();
            if(!reply.isError()&&!reply.value())forgetOwner(owner);
        });
    }
    if(old.owner!=value.owner&&!old.owner.isEmpty()) {
        bool used=false;for(const auto &entry:m_entries)if(entry.owner==old.owner){used=true;break;}
        if(!used)m_watcher.removeWatchedService(old.owner);
    }
    if(old.owner!=value.owner||old.count!=value.count||old.visible!=value.visible)emit changed();
}
}
