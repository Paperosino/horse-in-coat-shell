// Disposable nested-compositor fixture: threaded Qt Quick and real Qt CSD.
#include <QGuiApplication>
#include <QQuickWindow>
#include <QSGRendererInterface>
#include <QThread>
#include <atomic>
#include <memory>
#include <QOpenGLContext>
#include <QOpenGLFunctions>
#include <QSurfaceFormat>
#include <QSocketNotifier>
#include <QTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTextStream>
#include <QtWaylandClient/private/qwaylandwindow_p.h>
#include <QtWaylandClient/private/qwaylandabstractdecoration_p.h>
#include <unistd.h>

struct RenderState {
    std::atomic<quintptr> contextId{0};
    std::atomic<int> api{0};
    std::atomic<int> error{0};
    std::atomic<bool> valid{false};
    std::atomic<bool> threaded{false};
};

class Probe : public QQuickWindow {
public:
    int frames = 0;
    int phase = 0;
    QString output;
    std::shared_ptr<RenderState> render = std::make_shared<RenderState>();
    Probe() {
        setColor(QColor::fromRgbF(.21, .37, .54, 1));
        QObject::connect(this, &QQuickWindow::beforeRendering, this, [state = render] {
            state->threaded.store(QThread::currentThread() != QCoreApplication::instance()->thread());
            auto *context = QOpenGLContext::currentContext();
            state->valid.store(context && context->isValid());
            state->contextId.store(reinterpret_cast<quintptr>(context));
            if (context) {
                state->api.store(int(context->format().renderableType()));
                state->error.fetch_or(int(context->functions()->glGetError()));
            }
        }, Qt::DirectConnection);
    }
    void report() {
        auto *native = static_cast<QtWaylandClient::QWaylandWindow *>(handle());
        auto *decoration = native ? native->decoration() : nullptr;
        bool image = false;
        if (decoration)
            image = decoration->contentImage().save(output + "/decoration-" + QString::number(phase) + ".png");
        QTextStream(stdout) << QJsonDocument(QJsonObject{
            {"phase", phase}, {"frames", frames}, {"decorated", decoration != nullptr},
            {"decorationImageSaved", image}, {"contextValid", render->valid.load()}, {"renderThreaded", render->threaded.load()},
            {"renderableType", render->api.load()}, {"glError", render->error.load()},
            {"width", width()}, {"height", height()}
            , {"configuredMaximized", native && native->windowStates().testFlag(Qt::WindowMaximized)}
            , {"xdgWidth", native ? native->windowContentGeometry().width() : 0}
            , {"xdgHeight", native ? native->windowContentGeometry().height() : 0}
            , {"contextId", QString::number(render->contextId.load(), 16)}
        }).toJson(QJsonDocument::Compact) << Qt::endl;
    }
};

int main(int argc, char **argv) {
    if (argc != 3 && argc != 4) return 2;
    QSurfaceFormat format;
    if (QString::fromLatin1(argv[1]) == "gl") {
        format.setRenderableType(QSurfaceFormat::OpenGL);
        format.setVersion(3, 3);
        format.setProfile(QSurfaceFormat::CoreProfile);
    } else if (QString::fromLatin1(argv[1]) == "gles") {
        format.setRenderableType(QSurfaceFormat::OpenGLES);
        format.setVersion(2, 0);
    } else return 3;
    QSurfaceFormat::setDefaultFormat(format);
    QQuickWindow::setGraphicsApi(QSGRendererInterface::OpenGL);
    QGuiApplication app(argc, argv);
    Probe window;
    window.output = QString::fromLocal8Bit(argv[2]);
    window.setFormat(format);
    window.setTitle("HICS threaded Quick decoration probe");
    window.setFlags(Qt::Window | Qt::WindowTitleHint | Qt::WindowCloseButtonHint | Qt::WindowMinMaxButtonsHint | Qt::FramelessWindowHint);
    if (argc == 4) {
        if (QString::fromLatin1(argv[3]) != "decorated") return 5;
        window.setFlag(Qt::FramelessWindowHint, false);
    }
    window.resize(400, 240);
    QObject::connect(&window, &QQuickWindow::frameSwapped, &app, [&] {
        if (++window.frames == 5) window.report();
        else if (window.frames < 5) QTimer::singleShot(20, &window, [&] { window.update(); });
    });
    QSocketNotifier input(STDIN_FILENO, QSocketNotifier::Read, &app);
    QObject::connect(&input, &QSocketNotifier::activated, &app, [&] {
        char buffer[64];
        auto count = ::read(STDIN_FILENO, buffer, sizeof(buffer));
        if (count <= 0) { app.quit(); return; }
        auto command = QString::fromUtf8(buffer, int(count)).trimmed();
        if (command == "quit") { app.quit(); return; }
        if (command != "decorate" && command != "frameless") { app.exit(4); return; }
        ++window.phase;
        window.frames = 0;
        window.setFlag(Qt::FramelessWindowHint, command == "frameless");
        window.update();
    });
    QTimer::singleShot(45000, &app, [&] { app.exit(99); });
    window.showMaximized();
    return app.exec();
}
