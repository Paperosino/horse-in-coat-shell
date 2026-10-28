// Public native-context interoperability and ownership regression fixture.
#include <QGuiApplication>
#include <QOpenGLContext>
#include <QOpenGLFramebufferObject>
#include <QOpenGLFunctions>
#include <QOffscreenSurface>
#include <QColor>
#include <QWindow>
#include <QElapsedTimer>
#include <QThread>
#include <QImage>
#include <QtGui/qopenglcontext_platform.h>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTextStream>
#include <memory>

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    QSurfaceFormat format;
    const QString api = QString::fromLatin1(argv[1]);
    if (api == "gl") {
        format.setRenderableType(QSurfaceFormat::OpenGL);
        format.setVersion(3, 3);
        format.setProfile(QSurfaceFormat::CoreProfile);
    } else if (api == "gles") {
        format.setRenderableType(QSurfaceFormat::OpenGLES);
        format.setVersion(2, 0);
    } else return 3;
    QSurfaceFormat::setDefaultFormat(format);
    QGuiApplication app(argc, argv);
    QOpenGLContext owner;
    owner.setFormat(format);
    if (!owner.create() || !owner.isValid()) return 4;
    auto *native = owner.nativeInterface<QNativeInterface::QEGLContext>();
    if (!native) return 5;
    const auto handle = native->nativeContext();
    QOffscreenSurface surface;
    surface.setFormat(owner.format());
    surface.create();
    if (!surface.isValid()) return 6;
    QTextStream(stdout) << "EGL_OWNER_CREATED" << Qt::endl;
    std::unique_ptr<QOpenGLContext> borrowed(QNativeInterface::QEGLContext::fromNative(handle, native->display(), &owner));
    if (!borrowed || !borrowed->isValid() || !borrowed->makeCurrent(&surface)) return 7;
    const bool sharing = QOpenGLContext::areSharing(&owner, borrowed.get());
    QColor pixel;
    int glError = 0;
    {
        QOpenGLFramebufferObject fbo(8, 8);
        if (!fbo.isValid() || !fbo.bind()) return 8;
        auto *functions = borrowed->functions();
        functions->glClearColor(.25f, .5f, .75f, 1.0f);
        functions->glClear(GL_COLOR_BUFFER_BIT);
        const QImage image = fbo.toImage();
        if (image.isNull()) return 9;
        pixel = image.pixelColor(4, 4);
        glError = int(functions->glGetError());
        fbo.release();
    }
    const int renderableType = int(borrowed->format().renderableType());
    // Exercise the adopted context's decorated-window path, not only pbuffers.
    QWindow window;
    window.setSurfaceType(QSurface::OpenGLSurface);
    window.setFormat(owner.format());
    window.setTitle("HICS adopted EGL context");
    window.resize(320, 240);
    window.show();
    QElapsedTimer exposed;
    exposed.start();
    while (!window.isExposed() && exposed.elapsed() < 5000) {
        app.processEvents();
        QThread::msleep(5);
    }
    if (!window.isExposed()) return 11;
    const bool decoratedWindow = !window.frameMargins().isNull();
    for (int frame = 0; frame < 3; ++frame) {
        if (!borrowed->makeCurrent(&window)) return 12;
        auto *functions = borrowed->functions();
        functions->glBindFramebuffer(GL_FRAMEBUFFER, borrowed->defaultFramebufferObject());
        functions->glClearColor(.25f, .5f, .75f, 1.0f);
        functions->glClear(GL_COLOR_BUFFER_BIT);
        glError |= int(functions->glGetError());
        borrowed->swapBuffers(&window);
        app.processEvents();
    }
    borrowed->doneCurrent();
    borrowed.reset();
    const bool ownerRetained = owner.isValid() && native->nativeContext() == handle && owner.makeCurrent(&surface);
    owner.doneCurrent();
    const bool colorful = pixel.red() > 30 && pixel.green() > pixel.red() && pixel.blue() > pixel.green() && pixel.alpha() == 255;
    QTextStream(stdout) << QJsonDocument(QJsonObject{{"ownerRetained", ownerRetained}, {"sharing", sharing},
        {"renderableType", renderableType}, {"decoratedWindow", decoratedWindow}, {"colorful", colorful}, {"glError", glError},
        {"red", pixel.red()}, {"green", pixel.green()}, {"blue", pixel.blue()}}).toJson(QJsonDocument::Compact) << Qt::endl;
    return ownerRetained && sharing && colorful && decoratedWindow && !glError ? 0 : 10;
}
