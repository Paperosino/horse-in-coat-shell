#include "util/applicationlaunch.hpp"
#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
#include <QTimer>
#include <QTextStream>
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    QProcess launch;
    launch.setProgram("gio");launch.setArguments({"launch", app.arguments().value(1)});
    launch.setProcessEnvironment(hics::util::applicationEnvironment());
    const auto log = app.arguments().value(2);
    launch.setProcessChannelMode(QProcess::MergedChannels);
    launch.setStandardOutputFile(log, QIODevice::Append);
    launch.setProperty("hics.application.log", log);
    if (!hics::util::isolateApplication(launch)) return 3;
    QObject::connect(&launch, &QProcess::finished, &app, [&](int code) {
        QFile f(log);if (!f.open(QIODevice::ReadOnly)) { app.exit(5); return; }
        QTextStream(stdout) << QJsonDocument(QJsonObject{{"code", code}, {"error", QString::fromUtf8(f.readAll())}}).toJson(QJsonDocument::Compact) << Qt::endl;
        app.quit();
    });
    QTimer::singleShot(12000, &app, [&] { app.exit(4); });
    launch.start();
    return app.exec();
}
