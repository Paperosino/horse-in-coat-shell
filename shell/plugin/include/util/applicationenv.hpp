#pragma once
#include <QDir>
#include <QProcessEnvironment>
#include <QStringList>
#include <QFileInfo>
#include <QSettings>
#include <QStandardPaths>
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
// A vendor's Qt cannot load a host QPA plugin built against another minor
// version. Respect explicit theme choices; use its own GTK bridge when its
// qt.conf declares a private runtime. Never inject the shell's Qt libraries.
inline QProcessEnvironment applicationEnvironmentForExecutable(const QString &program, QProcessEnvironment env = QProcessEnvironment::systemEnvironment()) {
    env = applicationEnvironment(env);
    if (env.value(QStringLiteral("QT_QPA_PLATFORMTHEME")) != QStringLiteral("hics")) return env;
    const auto resolved = QFileInfo(program.isEmpty() ? QString{} :
        (QFileInfo(program).isAbsolute() ? program : QStandardPaths::findExecutable(program, env.value(QStringLiteral("PATH")).split(u':')))).canonicalFilePath();
    if (resolved.isEmpty()) return env;
    const QDir directory = QFileInfo(resolved).absoluteDir();
    const auto config = directory.filePath(QStringLiteral("qt.conf"));
    const QFileInfo info(config);
    if (!info.isFile() || info.size() > 65536) return env;
    QSettings settings(config, QSettings::IniFormat);
    const QDir prefix(directory.filePath(settings.value(QStringLiteral("Paths/Prefix"), QStringLiteral(".")).toString()));
    const auto plugins = prefix.filePath(settings.value(QStringLiteral("Paths/Plugins"), QStringLiteral("plugins")).toString());
    if (QFileInfo::exists(plugins + QStringLiteral("/platformthemes/libqgtk3.so")))
        env.insert(QStringLiteral("QT_QPA_PLATFORMTHEME"), QStringLiteral("gtk3"));
    return env;
}
}
