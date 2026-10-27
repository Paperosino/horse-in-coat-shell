#pragma once

#include <qlocalsocket.h>
#include <qobject.h>
#include <qqmlintegration.h>
#include <qpointer.h>
#include <QJSValue>
#include <QTimer>
#include <qvariant.h>
#include <functional>

namespace hyprstack::services::hypr {

class HyprDevices;

class HyprExtras : public QObject {
    Q_OBJECT
    QML_ELEMENT
    Q_MOC_INCLUDE("hyprdevices.hpp")

    Q_PROPERTY(QVariantHash options READ options NOTIFY optionsChanged)
    Q_PROPERTY(hyprstack::services::hypr::HyprDevices* devices READ devices CONSTANT)
    Q_PROPERTY(bool usingLua MEMBER m_usingLua NOTIFY usingLuaChanged)

public:
    explicit HyprExtras(QObject* parent = nullptr);

    [[nodiscard]] QVariantHash options() const;
    [[nodiscard]] HyprDevices* devices() const;

    Q_INVOKABLE void request(const QString& message, QJSValue callback);
    Q_INVOKABLE void message(const QString& message);
    Q_INVOKABLE void batchMessage(const QStringList& messages);
    Q_INVOKABLE void applyOptions(const QVariantHash& options);

    Q_INVOKABLE void refreshOptions(bool afterReload = false);
    Q_INVOKABLE void refreshDevices();

signals:
    void optionsChanged();
    void configOptionsReloaded();
    void usingLuaChanged();

private:
    using SocketPtr = QPointer<QLocalSocket>;

    QString m_requestSocket;
    QString m_eventSocket;
    QLocalSocket* m_socket;
    bool m_socketValid;
    bool m_usingLua = false;
    QByteArray m_eventLine;
    bool m_discardingEvent = false;
    bool m_badEventWarned = false, m_longEventWarned = false;
    bool m_everConnected = false;
    QTimer* m_reconnect = nullptr;
    int m_reconnectDelay = 1000;

    QVariantHash m_options;
    HyprDevices* const m_devices;

    quint64 m_optionsGeneration = 0;
    bool m_configOptionsPending = false;
    SocketPtr m_optionsRefresh;
    SocketPtr m_devicesRefresh;

    void socketError(QLocalSocket::LocalSocketError error) const;
    void socketStateChanged(QLocalSocket::LocalSocketState state);
    void readEvent();
    void handleEvent(const QString& event);

    SocketPtr makeRequestJson(const QString& request, const std::function<void(bool, QJsonDocument)>& callback);
    SocketPtr makeRequest(const QString& request, const std::function<void(bool, QByteArray)>& callback);
};

} // namespace hyprstack::services::hypr
