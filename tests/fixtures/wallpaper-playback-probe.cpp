#include "wallpaperplayer.hpp"
#include <QGuiApplication>
#include <QVideoFrame>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTextStream>
#include <QTimer>
#include <QImage>
#include <QSet>
#include <QElapsedTimer>
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
    bool colorful = false;
    const bool watchdog = argc > 2;
    bool sinkDetached = false;
    QElapsedTimer clock;clock.start();
    qint64 firstFrameMs = -1;
    QObject::connect(&sink, &QVideoSink::videoFrameChanged, &app, [&](const QVideoFrame &frame) {
        if (!frame.isValid()) return;
        ++frames;
        if (firstFrameMs < 0) firstFrameMs = clock.elapsed();
        if (watchdog && !sinkDetached) {
            sinkDetached = true;
            QTimer::singleShot(200, &app, [&] { player.setVideoSink(nullptr); });
        }
        if (colorful) return;
        const auto image = frame.toImage();
        if (image.size() != QSize(64,64)) return;
        QSet<QRgb> colors;
        for (int y=0;y<64;y+=8) for (int x=0;x<64;x+=8) colors.insert(image.pixel(x,y));
        colorful = colors.size()>4;
    });
    player.setMuted(true); player.setVideoSink(&sink);
    player.setSource(WallpaperPlayer::resolveVideo(QString::fromLocal8Bit(argv[1])));
    if (!watchdog) {
        QTimer::singleShot(1200, &app, [&] { player.setPaused(true); });
        QTimer::singleShot(1450, &app, [&] { pausedFrames = frames; });
        QTimer::singleShot(1900, &app, [&] { pausedStable = frames == pausedFrames; player.setPaused(false); });
        QTimer::singleShot(2900, &app, [&] { player.restart(); });
    }
    QTimer::singleShot(watchdog ? 36500 : 4400, &app, [&] {
        QTextStream(stdout) << QJsonDocument(QJsonObject{{"frames",frames},{"nativeFrames",qint64(player.frames())},{"pausedStable",pausedStable},
            {"recoveries",player.recoveries()},{"error",player.error()},{"colorful",colorful},{"firstFrameMs",firstFrameMs},{"sinkDetached",sinkDetached}}).toJson(QJsonDocument::Compact) << Qt::endl;
        app.quit();
    });
    QTextStream(stderr) << "event loop" << Qt::endl;
    const auto result = app.exec();
    QTextStream(stderr) << "event loop done" << Qt::endl;
    return result;
}
