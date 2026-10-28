// Actual threaded Qt Quick video presentation and repeated decoder teardown.
#include <QGuiApplication>
#include <QQuickView>
#include <QElapsedTimer>
#include <QThread>
#include <QQuickItem>
#include <QMediaPlayer>
#include <QVideoSink>
#include <QVideoFrame>
#include <QEventLoop>
#include <QTimer>
#include <QImage>
#include <QSet>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTextStream>
#include <memory>

int main(int argc, char **argv) {
    if (argc != 5) return 2;
    QQuickWindow::setGraphicsApi(QSGRendererInterface::OpenGL);
    QGuiApplication app(argc, argv);
    const QUrl qml = QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1]));
    const QUrl media = QUrl::fromLocalFile(QString::fromLocal8Bit(argv[2]));
    const QString output = QString::fromLocal8Bit(argv[3]);
    bool ok = false;
    const int cycles = QString::fromLatin1(argv[4]).toInt(&ok);
    if (!ok || cycles < 1 || cycles > 100) return 3;
    QJsonArray samples;
    for (int cycle = 0; cycle < cycles; ++cycle) {
        auto view = std::make_unique<QQuickView>();
        view->setResizeMode(QQuickView::SizeRootObjectToView);
        view->setSource(qml);
        QElapsedTimer loading;
        loading.start();
        while (view->status() == QQuickView::Loading && loading.elapsed() < 5000) {
            app.processEvents();
            QThread::msleep(5);
        }
        if (view->status() != QQuickView::Ready || !view->rootObject()) {
            for (const auto &error : view->errors()) QTextStream(stderr) << error.toString() << Qt::endl;
            return 4;
        }
        auto *sink = view->rootObject()->property("videoSink").value<QVideoSink *>();
        if (!sink) return 5;
        view->resize(256, 256);
        view->show();
        QMediaPlayer player;
        player.setLoops(QMediaPlayer::Infinite);
        player.setVideoSink(sink);
        int frames = 0;
        bool timedOut = false;
        bool scheduled = false;
        QString error;
        QEventLoop loop;
        QTimer deadline;
        deadline.setSingleShot(true);
        QObject::connect(&deadline, &QTimer::timeout, &loop, [&] { timedOut = true; loop.quit(); });
        QObject::connect(&player, &QMediaPlayer::errorOccurred, &loop,
                         [&](QMediaPlayer::Error, const QString &message) { error = message; loop.quit(); });
        QObject::connect(sink, &QVideoSink::videoFrameChanged, &loop, [&](const QVideoFrame &frame) {
            if (frame.isValid() && ++frames >= 6 && !scheduled) {
                scheduled = true;
                player.pause();
                QTimer::singleShot(120, &loop, &QEventLoop::quit);
            }
        });
        player.setSource(media);
        player.play();
        deadline.start(8000);
        loop.exec();
        deadline.stop();
        if (timedOut || !error.isEmpty() || frames < 6) {
            QTextStream(stderr) << "video failed: " << error << " frames=" << frames << Qt::endl;
            return 6;
        }
        const QImage image = view->grabWindow();
        if (image.isNull()) return 7;
        QSet<QRgb> colors;
        for (int y = 16; y < image.height()-16; y += 16)
            for (int x = 16; x < image.width()-16; x += 16)
                colors.insert(image.pixel(x, y));
        if (colors.size() < 5) return 8;
        if ((cycle == 0 || cycle == cycles-1)
            && !image.save(output + "/video-" + QString::number(cycle) + ".png")) return 9;
        player.stop();
        player.setVideoSink(nullptr);
        // Destroy the player before its view/sink and flush deferred teardown.
        // This inner scope is closed below by normal C++ destruction order.
        samples.append(QJsonObject{{"cycle", cycle}, {"frames", frames}, {"colors", colors.size()}});
        QTextStream(stderr) << "VIDEO_CYCLE " << cycle << Qt::endl;
    }
    QTextStream(stdout) << QJsonDocument(QJsonObject{{"cycles", cycles}, {"samples", samples},
        {"colorful", true}, {"errors", false}}).toJson(QJsonDocument::Compact) << Qt::endl;
}
