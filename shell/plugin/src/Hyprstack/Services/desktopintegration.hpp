#pragma once
#include <QObject>
#include <QQmlEngine>
#include <QtQmlIntegration/qqmlintegration.h>
#include <QVariantList>
#include <QTimer>
#include <QAudioSource>
#include <QMediaDevices>
#include <functional>

namespace hyprstack::services {
// User-session operations: NetworkManager/UDisks enforce the caller's own policy.
// Passwords travel over D-Bus, never through a command line or a config file.
class DesktopIntegration : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(int portalSourceTypes READ portalSourceTypes NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
    Q_PROPERTY(QString error READ error NOTIFY changed)
    Q_PROPERTY(QVariantList cards READ cards NOTIFY changed)
    Q_PROPERTY(QVariantList wifiDevices READ wifiDevices NOTIFY changed)
    Q_PROPERTY(QVariantList encryptedVolumes READ encryptedVolumes NOTIFY changed)
    Q_PROPERTY(QVariantList removableDrives READ removableDrives NOTIFY changed)
    Q_PROPERTY(QVariantList captureStreams READ captureStreams NOTIFY changed)
    Q_PROPERTY(QVariantList recordingSources READ recordingSources NOTIFY changed)
    Q_PROPERTY(bool captureMonitorAvailable READ captureMonitorAvailable NOTIFY changed)
    Q_PROPERTY(bool microphoneTesting READ microphoneTesting NOTIFY microphoneChanged)
    Q_PROPERTY(qreal microphoneLevel READ microphoneLevel NOTIFY microphoneChanged)
public:
    explicit DesktopIntegration(QObject *parent = nullptr);
    int portalSourceTypes() const { return m_portalSourceTypes; }
    bool busy() const { return m_pending > 0; }
    QString error() const { return m_error; }
    QVariantList cards() const { return m_cards; }
    QVariantList wifiDevices() const { return m_wifi; }
    QVariantList encryptedVolumes() const { return m_encrypted; }
    QVariantList removableDrives() const { return m_drives; }
    QVariantList captureStreams() const { return m_captures; }
    QVariantList recordingSources() const { return m_recordingSources; }
    bool captureMonitorAvailable() const { return m_captureAvailable; }
    bool microphoneTesting() const { return m_audio != nullptr; }
    qreal microphoneLevel() const { return m_level; }
    Q_INVOKABLE QUrl wallpaperVideo(const QString &path) const;
    Q_INVOKABLE void refresh();
    Q_INVOKABLE void setCardProfile(const QString &card, const QString &profile);
    Q_INVOKABLE void startMicrophoneTest();
    Q_INVOKABLE void stopMicrophoneTest();
    Q_INVOKABLE void startHotspot(const QString &device, const QString &ssid, const QString &password);
    Q_INVOKABLE bool connectHiddenNetwork(const QString &ssid, const QString &password, bool secured, bool hidden);
    Q_INVOKABLE void stopHotspot(const QString &activeConnection);
    Q_INVOKABLE void unlockVolume(const QString &path, const QString &password);
    Q_INVOKABLE void lockVolume(const QString &path);
    Q_INVOKABLE void ejectDrive(const QString &path, bool powerOff);
    Q_INVOKABLE void mountVolume(const QString &path);
signals:
    void changed();
    void microphoneChanged();
    void operationSucceeded();
    void hiddenNetworkFinished(bool success);
    void volumeMounted(const QString &mountPoint);
    void removableVolumeAdded(const QString &path);
private:
    using Result = std::function<void(const QByteArray &)>;
    void process(const QString &program, const QStringList &args, Result result, bool reportError = true);
    void diskCall(const QString &path, const QString &interface, const QString &method, const QVariantList &args);
    void fail(const QString &message);
    void refreshDisks();
    void refreshWifi();
    void awaitActivation(const QString &path, std::function<void(bool)> done);
    int m_pending = 0;
    int m_portalSourceTypes = 0;
    QString m_error;
    QVariantList m_cards, m_wifi, m_encrypted, m_drives, m_captures, m_recordingSources;
    bool m_captureAvailable = false, m_disksLoaded = false;
    QSet<QString> m_knownVolumes;
    QAudioSource *m_audio = nullptr;
    qreal m_level = 0;
    QTimer m_micTimeout;
    QMediaDevices m_mediaDevices;
};
}
