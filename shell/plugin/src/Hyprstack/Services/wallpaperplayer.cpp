#include "wallpaperplayer.hpp"
#include <QDir>
#include <QVideoFrame>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
namespace hyprstack::services {
using namespace Qt::StringLiterals;
QUrl WallpaperPlayer::resolveVideo(const QString &path) {
    QFileInfo info(path);
    if (info.isDir()) {
        QFile project(QDir(path).filePath(u"project.json"_s));
        if (!project.open(QIODevice::ReadOnly)) return {};
        const auto data = QJsonDocument::fromJson(project.readAll()).object();
        if (data[u"type"_s].toString() != u"video"_s) return {};
        info.setFile(QDir(path).filePath(data[u"file"_s].toString()));
        if (!info.canonicalFilePath().startsWith(QFileInfo(path).canonicalFilePath() + u'/' )) return {};
    }
    if (!info.isFile() || !QStringList{u"mp4"_s,u"webm"_s,u"mkv"_s,u"mov"_s,u"m4v"_s,u"ogv"_s,u"avi"_s}.contains(info.suffix().toLower())) return {};
    return QUrl::fromLocalFile(info.canonicalFilePath());
}
WallpaperPlayer::WallpaperPlayer(QObject *parent) : QObject(parent) {
    m_player.setAudioOutput(&m_audio);
    m_player.setLoops(QMediaPlayer::Infinite);
    m_lastFrame.start(); m_failureWindow.start();
    m_retry.setSingleShot(true);
    connect(&m_retry, &QTimer::timeout, this, [this] {
        if (m_source.isEmpty() || m_paused) return;
        // Recreate the decoder after a stuck EOF, resume or GPU reset.
        m_player.setSource(m_source); m_player.play(); m_lastFrame.restart();
    });
    connect(&m_player, &QMediaPlayer::errorOccurred, this, [this](QMediaPlayer::Error, const QString &error) {
        m_error = error; emit changed(); QTimer::singleShot(0, this, &WallpaperPlayer::recover);
    });
    m_watchdog.setInterval(5000);
    connect(&m_watchdog, &QTimer::timeout, this, [this] {
        if (!m_paused && !m_source.isEmpty() && !m_retry.isActive() && m_lastFrame.elapsed() > 30000) recover();
    });
    m_watchdog.start();
}
WallpaperPlayer::~WallpaperPlayer() {
    m_watchdog.stop(); m_retry.stop();
    m_player.stop(); m_player.setVideoSink(nullptr); m_player.setAudioOutput(nullptr);
}
void WallpaperPlayer::setSource(const QUrl &source) {
    if (m_source == source) return;
    m_source = source; restart(); emit changed();
}
void WallpaperPlayer::setVideoSink(QVideoSink *sink) {
    if (m_sink == sink) return;
    disconnect(m_frameConnection);
    m_sink = sink; m_player.setVideoSink(sink);
    if (sink) m_frameConnection = connect(sink, &QVideoSink::videoFrameChanged, this, [this](const QVideoFrame &frame) {
        if (!frame.isValid()) return;
        ++m_frames; m_lastFrame.restart(); emit frameReceived();
        if (!m_error.isEmpty()) { m_error.clear(); emit changed(); }
    });
    emit changed();
}
void WallpaperPlayer::setPaused(bool paused) {
    if (m_paused == paused) return;
    m_paused = paused; m_lastFrame.restart();
    if (paused) { m_retry.stop(); m_player.pause(); }
    else if (!m_source.isEmpty()) {
        if (m_player.source().isEmpty()) m_player.setSource(m_source);
        m_player.play();
    }
    emit changed();
}
void WallpaperPlayer::restart() {
    m_retry.stop(); m_player.stop(); m_player.setSource({});
    m_error.clear(); m_recoveries = 0; m_failureWindow.restart(); m_lastFrame.restart();
    if (!m_source.isEmpty() && !m_paused) m_retry.start(100);
    emit changed();
}
void WallpaperPlayer::recover() {
    if (m_paused || m_source.isEmpty() || m_retry.isActive()) return;
    if (m_failureWindow.elapsed() > 600000) { m_failureWindow.restart(); m_recoveries = 0; }
    if (m_recoveries >= 6) {
        m_error = tr("Wallpaper playback could not recover. Use Restart wallpaper to try again.");
        emit changed(); return;
    }
    ++m_recoveries;
    m_player.stop(); m_player.setSource({});
    m_lastFrame.restart(); m_retry.start(qMin(30000, 500 * (1 << m_recoveries)));
    emit changed();
}
}
