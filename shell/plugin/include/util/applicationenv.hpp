#pragma once
#include <QDir>
#include <QProcessEnvironment>
#include <QStringList>
namespace hics::util {
inline QProcessEnvironment applicationEnvironment(QProcessEnvironment env = QProcessEnvironment::systemEnvironment()) {
    QStringList roots{QStringLiteral("/usr/share/hics"), QStringLiteral("/usr/share/hyprstack")};
    const auto configured = env.value(QStringLiteral("HICS_DATA_DIR"), env.value(QStringLiteral("HYPRSTACK_DATA_DIR")));
    if (!configured.isEmpty()) roots << configured;
    const auto data = env.value(QStringLiteral("XDG_DATA_HOME"), env.value(QStringLiteral("HOME")) + QStringLiteral("/.local/share"));
    roots << data + QStringLiteral("/hics") << data + QStringLiteral("/hyprstack");
    for (const auto &key : {QStringLiteral("LD_LIBRARY_PATH"), QStringLiteral("LD_PRELOAD"), QStringLiteral("QT_PLUGIN_PATH"),
             QStringLiteral("QT_QPA_PLATFORM_PLUGIN_PATH"), QStringLiteral("QML_IMPORT_PATH"), QStringLiteral("QML2_IMPORT_PATH")}) {
        if (!env.contains(key)) continue;
        QStringList kept;
        for (const auto &entry : env.value(key).split(u':', Qt::SkipEmptyParts)) {
            const auto path = QDir::cleanPath(entry);
            bool bundled = false;
            for (const auto &root : roots)
                for (const auto &suffix : {QStringLiteral("/qs"), QStringLiteral("/qml"), QStringLiteral("/lib")}) {
                    const auto prefix = QDir::cleanPath(root + suffix);
                    bundled |= path == prefix || path.startsWith(prefix + u'/');
                }
            if (!bundled) kept << entry;
        }
        if (kept.isEmpty()) env.remove(key);
        else env.insert(key, kept.join(u':'));
    }
    return env;
}
}
