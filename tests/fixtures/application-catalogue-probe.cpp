#include "applicationcatalogue.hpp"
#include <QCoreApplication>
#include <QFile>
#include <QDir>
#include <QTimer>
#include <QJsonDocument>
#include <QJsonObject>
using namespace hyprstack::services;
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    ApplicationCatalogue catalogue;
    const auto root = qEnvironmentVariable("XDG_DATA_HOME") + "/applications";
    QDir().mkpath(root);
    const auto file = root + "/org.hics.CatalogueFixture.desktop";
    auto write = [&](const QString &name) {
        QFile f(file); f.open(QIODevice::WriteOnly);
        f.write(("[Desktop Entry]\nType=Application\nName=" + name + "\nExec=/bin/true %U\nStartupWMClass=CatalogueFixture\n").toUtf8());
    };
    QJsonObject result;
    QTimer::singleShot(50, &app, [&] { write("Initial"); });
    QTimer::singleShot(800, &app, [&] {
        auto *entry = catalogue.byId("org.hics.CatalogueFixture.desktop");
        result["created"] = entry && entry->property("name").toString() == "Initial";
        result["lookup"] = catalogue.heuristicLookup("CatalogueFixture") == entry;
        if (entry) QMetaObject::invokeMethod(entry, "execute");
        write("Updated");
    });
    QTimer::singleShot(1600, &app, [&] {
        auto *entry = catalogue.byId("org.hics.CatalogueFixture");
        result["updated"] = entry && entry->property("name").toString() == "Updated";
        QFile::remove(file);
    });
    QTimer::singleShot(2400, &app, [&] {
        result["removed"] = catalogue.byId("org.hics.CatalogueFixture") == nullptr;
        const auto bytes = QJsonDocument(result).toJson(QJsonDocument::Compact);
        fwrite(bytes.constData(), 1, size_t(bytes.size()), stdout);
        app.quit();
    });
    return app.exec();
}
