#include <QQmlExtensionPlugin>
#include <QQuickItem>
#include <QPointer>
#include <QSet>
#include <QDebug>

class ObjectLifetimeProbe : public QObject {
    Q_OBJECT
public:
    using QObject::QObject;
    Q_INVOKABLE void track(QObject *object) {
        QSet<QObject *> visited;
        const auto visit = [&](auto &&self, QObject *entry) -> void {
            if (!entry || visited.contains(entry)) return;
            visited.insert(entry);
            const QByteArray type = entry->metaObject()->className();
            if ((type.contains("ShaderEffect") || type.contains("MultiEffect")) && !m_seen.contains(entry)) {
                const auto *item = qobject_cast<QQuickItem *>(entry);
                qInfo() << "LIFETIME_TRACK" << type << entry << "owner" << entry->parent()
                        << "visualParent" << (item ? item->parentItem() : nullptr)
                        << "shader" << entry->property("vertexShader");
                m_seen.insert(entry);
                m_objects.append({entry, type});
                connect(entry, &QObject::destroyed, this, [this, entry] { m_seen.remove(entry); });
            }
            for (auto *child : entry->children()) self(self, child);
            if (auto *item = qobject_cast<QQuickItem *>(entry))
                for (auto *child : item->childItems()) self(self, child);
        };
        visit(visit, object);
    }
    Q_INVOKABLE int report() {
        int alive = 0;
        for (const auto &entry : std::as_const(m_objects)) {
            if (entry.object) {
                ++alive;
                qInfo() << "LIFETIME_ALIVE" << entry.type << entry.object.data()
                        << "owner" << entry.object->parent();
            }
        }
        qInfo() << "LIFETIME_OBJECTS" << m_objects.size() << "alive" << alive;
        return alive;
    }
private:
    struct Entry {QPointer<QObject> object; QByteArray type;};
    QList<Entry> m_objects;
    QSet<QObject *> m_seen;
};
class LifetimeProbePlugin final : public QQmlExtensionPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID QQmlExtensionInterface_iid)
public:
    void registerTypes(const char *uri) override {qmlRegisterType<ObjectLifetimeProbe>(uri,1,0,"ObjectLifetimeProbe");}
};
#include "qt-object-lifetime-probe.moc"
