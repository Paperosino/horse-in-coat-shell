#pragma once
#include <QObject>
#include <QtQmlIntegration/qqmlintegration.h>
#include <QMediaPlayer>
#include <QAudioOutput>
#include <QVideoSink>
#include <QElapsedTimer>
#include <QTimer>
namespace hyprstack::services {
class WallpaperPlayer : public QObject {
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QUrl source READ source WRITE setSource NOTIFY changed)
    Q_PROPERTY(QVideoSink *videoSink READ videoSink WRITE setVideoSink NOTIFY changed)
    Q_PROPERTY(bool paused READ paused WRITE setPaused NOTIFY changed)
    Q_PROPERTY(bool muted READ muted WRITE setMuted NOTIFY changed)
    Q_PROPERTY(qreal volume READ volume WRITE setVolume NOTIFY changed)
    Q_PROPERTY(QString error READ error NOTIFY changed)
    Q_PROPERTY(int recoveries READ recoveries NOTIFY changed)
public:
    explicit WallpaperPlayer(QObject *parent = nullptr);
    ~WallpaperPlayer() override;
    QUrl source() const { return m_source; }
    void setSource(const QUrl &source);
    QVideoSink *videoSink() const { return m_sink; }
    void setVideoSink(QVideoSink *sink);
    bool paused() const { return m_paused; }
    void setPaused(bool paused);
    bool muted() const { return m_audio.isMuted(); }
    void setMuted(bool muted) { m_audio.setMuted(muted); emit changed(); }
    qreal volume() const { return m_audio.volume(); }
    void setVolume(qreal volume) { m_audio.setVolume(float(qBound(qreal(0), volume, qreal(1)))); emit changed(); }
    QString error() const { return m_error; }
    int recoveries() const { return m_recoveries; }
    Q_INVOKABLE void restart();
    Q_INVOKABLE quint64 frames() const { return m_frames; }
    static QUrl resolveVideo(const QString &path);
signals:
    void changed();
    void frameReceived();
private:
    void recover();
    QMediaPlayer m_player;
    QAudioOutput m_audio;
    QVideoSink *m_sink = nullptr;
    QUrl m_source;
    QString m_error;
    bool m_paused = false;
    int m_recoveries = 0;
    quint64 m_frames = 0;
    QElapsedTimer m_lastFrame, m_failureWindow;
    QTimer m_watchdog, m_retry;
    QMetaObject::Connection m_frameConnection;
};
}
