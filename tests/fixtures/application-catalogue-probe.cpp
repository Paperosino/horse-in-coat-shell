#include "applicationcatalogue.hpp"
#include <QCoreApplication>
#include <QFile>
#include <QDir>
#include <QTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QElapsedTimer>
#include <cassert>
using namespace hyprstack::services;
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    ApplicationCatalogue catalogue;
    if (argc > 1) {
        int changes = 0, entryChanges = 0;
        QObject::connect(&catalogue, &ApplicationCatalogue::applicationsChanged, &app, [&] { ++changes; });
        auto *entry = qobject_cast<DesktopApplication*>(catalogue.byId("org.hics.Bench0"));
        if (!entry) return 2;
        QObject::connect(entry, &DesktopApplication::changed, &app, [&] { ++entryChanges; });
        QElapsedTimer timer; timer.start();
        for (int i=0; i<15; ++i) catalogue.refresh();
        const auto cachedNs = timer.nsecsElapsed();
        const bool idle = changes == 0 && entryChanges == 0 && catalogue.byId("org.hics.Bench0") == entry;
        timer.restart();
        for (int i=0; i<15; ++i) catalogue.refresh(true);
        const auto fullNs = timer.nsecsElapsed();
        const auto local = qEnvironmentVariable("XDG_DATA_HOME") + "/applications/org.hics.Bench0.desktop";
        QFile override(local);
        if (!override.open(QIODevice::WriteOnly)) return 3;
        override.write("[Desktop Entry]\nType=Application\nName=Override\nExec=/bin/true\n");override.close();
        catalogue.refresh();
        const bool overridden = entry->name() == "Override";
        QFile::remove(local);catalogue.refresh();
        const bool fallback = overridden && entry->name() == "Benchmark 0" && entry->filePath() != local;
        QFile source(entry->filePath());
        if (!source.open(QIODevice::Append)) return 4;
        source.write("Actions=New;\n[Desktop Action New]\nName=New action\nExec=/bin/true\n");source.close();
        catalogue.refresh(true);
        const bool actions = entry->actions().size() == 1 && entry->actions().first()->property("name") == "New action";
        const auto exe = qEnvironmentVariable("BENCH_TRYEXEC");
        const bool before = catalogue.byId("org.hics.TryExec") != nullptr;
        QFile::remove(exe); catalogue.refresh();
        const bool removed = catalogue.byId("org.hics.TryExec") == nullptr;
        QFile f(exe); if(f.open(QIODevice::WriteOnly)) {f.write("#!/bin/sh\n");f.close();f.setPermissions(QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner);}
        catalogue.refresh();
        const bool restored = catalogue.byId("org.hics.TryExec") != nullptr;
        const auto bytes = QJsonDocument(QJsonObject{{"idle",idle},{"cachedMs",cachedNs/1e6},{"fullMs",fullNs/1e6},
            {"tryExec",before && removed && restored},{"fallback",fallback},{"actions",actions}}).toJson(QJsonDocument::Compact);
        fwrite(bytes.constData(),1,size_t(bytes.size()),stdout);return 0;
    }
    const auto root = qEnvironmentVariable("XDG_DATA_HOME") + "/applications";
    QDir().mkpath(root);
    const auto file = root + "/org.hics.CatalogueFixture.desktop";
    assert(catalogue.heuristicLookup("OriginalFixture") == nullptr);
    assert(catalogue.heuristicLookup("") == nullptr);
    auto write = [&](const QString &name) {
        QFile f(file); f.open(QIODevice::WriteOnly);
        f.write(("[Desktop Entry]\nType=Application\nName=" + name + "\nExec=/bin/true %U\nStartupWMClass=" + (name == "Updated" ? "RenamedFixture" : "OriginalFixture") + "\n").toUtf8());
    };
    QJsonObject result;
    QTimer::singleShot(50, &app, [&] { write("Initial"); });
    QTimer::singleShot(800, &app, [&] {
        auto *entry = catalogue.byId("org.hics.CatalogueFixture.desktop");
        result["created"] = entry && entry->property("name").toString() == "Initial";
        result["lookup"] = catalogue.heuristicLookup("OriginalFixture") == entry;
        if (entry) QMetaObject::invokeMethod(entry, "execute");
        write("Updated");
    });
    QTimer::singleShot(1600, &app, [&] {
        auto *entry = catalogue.byId("org.hics.CatalogueFixture");
        result["updated"] = entry && entry->property("name").toString() == "Updated" && catalogue.heuristicLookup("RenamedFixture") == entry && catalogue.heuristicLookup("OriginalFixture") == nullptr;
        QFile::remove(file);
    });
    QTimer::singleShot(2400, &app, [&] {
        result["removed"] = catalogue.byId("org.hics.CatalogueFixture") == nullptr && catalogue.heuristicLookup("RenamedFixture") == nullptr;
        const auto bytes = QJsonDocument(result).toJson(QJsonDocument::Compact);
        fwrite(bytes.constData(), 1, size_t(bytes.size()), stdout);
        app.quit();
    });
    return app.exec();
}
