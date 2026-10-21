#include "wallpaperplayer.hpp"
#include <QGuiApplication>
#include <QVideoFrame>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTextStream>
#include <QTimer>
using namespace hyprstack::services;
int main(int argc, char **argv) {
    QTextStream(stderr) << "before application" << Qt::endl;
    QGuiApplication app(argc, argv);
    QTextStream(stderr) << "before player" << Qt::endl;
    WallpaperPlayer player;
    QTextStream(stderr) << "player ready" << Qt::endl;
    QVideoSink sink;
    int frames = 0, pausedFrames = 0;
    bool pausedStable = false;
    QObject::connect(&sink, &QVideoSink::videoFrameChanged, &app, [&](const QVideoFrame &frame) { if (frame.isValid()) ++frames; });
    player.setMuted(true); player.setVideoSink(&sink);
    player.setSource(WallpaperPlayer::resolveVideo(QString::fromLocal8Bit(argv[1])));
    const bool watchdog = argc > 2;
    if (watchdog) QTimer::singleShot(800, &app, [&] { player.setVideoSink(nullptr); });
    else {
        QTimer::singleShot(1200, &app, [&] { player.setPaused(true); });
        QTimer::singleShot(1450, &app, [&] { pausedFrames = frames; });
        QTimer::singleShot(1900, &app, [&] { pausedStable = frames == pausedFrames; player.setPaused(false); });
        QTimer::singleShot(2900, &app, [&] { player.restart(); });
    }
    QTimer::singleShot(watchdog ? 36500 : 4400, &app, [&] {
        QTextStream(stdout) << QJsonDocument(QJsonObject{{"frames",frames},{"pausedStable",pausedStable},
            {"recoveries",player.recoveries()},{"error",player.error()}}).toJson(QJsonDocument::Compact) << Qt::endl;
        app.quit();
    });
    QTextStream(stderr) << "event loop" << Qt::endl;
    const auto result = app.exec();
    QTextStream(stderr) << "event loop done" << Qt::endl;
    return result;
}
