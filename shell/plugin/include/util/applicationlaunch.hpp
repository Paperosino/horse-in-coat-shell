#pragma once
#include "applicationenv.hpp"
#include <QFileInfo>
#include <QCoreApplication>
#include <QTemporaryFile>
#include <QProcess>
#include <QStandardPaths>
#include <QUuid>
namespace hics::util {
// A fresh user-manager service avoids inheriting a broker's NoNewPrivileges.
// Its only process immediately moves into app.slice and execs the application.
// No launch wrapper remains resident, and no hics unit owns the application.
inline bool isolateApplication(QProcess &process) {
    const auto runtime = qEnvironmentVariable("XDG_RUNTIME_DIR");
    const auto runner = QStandardPaths::findExecutable(QStringLiteral("systemd-run"));
    if (runtime.isEmpty() || runner.isEmpty() || !QFileInfo::exists(runtime + QStringLiteral("/systemd/private")))
        return false; // Non-systemd/test sessions retain detached launch support.
    const auto id = QUuid::createUuid().toString(QUuid::Id128);
    QStringList args{QStringLiteral("--expand-environment=no"), QStringLiteral("--user"), QStringLiteral("--quiet"), QStringLiteral("--collect"), QStringLiteral("--wait"), QStringLiteral("--property=Type=exec"),
                     QStringLiteral("--property=KillMode=process"), QStringLiteral("--unit=hics-launch-") + id};
    const auto env = process.processEnvironment().isEmpty() ? applicationEnvironment() : applicationEnvironment(process.processEnvironment());
    // Keep the complete application environment, including custom variables,
    // out of argv and the journal. The stage consumes and immediately removes
    // this owner-only runtime file before entering the application scope.
    QTemporaryFile environment(runtime + QStringLiteral("/hics-launch-XXXXXX.env"));
    if (!environment.open() || !environment.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner)) return false;
    QByteArray content;
    for (const auto &key : env.keys()) {
        bool valid = !key.isEmpty() && (key[0].isLetter() || key[0] == u'_');
        for (const auto c : key) valid &= (c.isLetterOrNumber() || c == u'_') && c.unicode() < 128;
        if (!valid) continue;
        auto value = env.value(key);
        value.replace(u'\\', QStringLiteral("\\\\"));
        value.replace(u'"', QStringLiteral("\\\""));
        content += key.toUtf8() + "=\"" + value.toUtf8() + "\"\n";
    }
    if (environment.write(content) != content.size() || !environment.flush()) return false;
    environment.setAutoRemove(false);
    const auto environmentPath = environment.fileName();
    environment.close();
    args << QStringLiteral("--property=EnvironmentFile=") + environmentPath;
    // A private bundled Qt runtime must never leak into an external GUI.
    QStringList unset;
    for (const auto &key : {QStringLiteral("QT_PLUGIN_PATH"), QStringLiteral("QT_QPA_PLATFORM_PLUGIN_PATH"), QStringLiteral("QML_IMPORT_PATH"), QStringLiteral("QML2_IMPORT_PATH"), QStringLiteral("LD_PRELOAD"), QStringLiteral("LD_LIBRARY_PATH"), QStringLiteral("XDG_ACTIVATION_TOKEN"), QStringLiteral("DESKTOP_STARTUP_ID")}) {
        if (!env.contains(key)) unset << key;
    }
    if (!unset.isEmpty()) args << QStringLiteral("--property=UnsetEnvironment=") + unset.join(u' ');
    if (!process.workingDirectory().isEmpty()) args << QStringLiteral("--working-directory=") + process.workingDirectory();
    auto stage = QStandardPaths::findExecutable(QStringLiteral("hics-launch"));
    if (QFileInfo(QCoreApplication::applicationFilePath()).fileName() == QStringLiteral("hics-launch")) stage = QCoreApplication::applicationFilePath();
    if (stage.isEmpty()) {
        QFile::remove(environmentPath);
        return false;
    }
    args << QStringLiteral("--") << stage << QStringLiteral("--scope-stage") << environmentPath
         << runner << QStringLiteral("--expand-environment=no") << QStringLiteral("--user") << QStringLiteral("--scope") << QStringLiteral("--quiet") << QStringLiteral("--collect")
         << QStringLiteral("--slice=app.slice") << QStringLiteral("--property=PartOf=graphical-session.target") << QStringLiteral("--unit=hics-app-") + id
         << QStringLiteral("--") << process.program();
    const auto targetProgram = process.program();
    const auto targetArguments = process.arguments();
    // GIO exits after activation and provides a useful startup exit status.
    // Other programs use a brief exec-checking helper; --wait must never
    // leave a systemd-run monitor resident for the application's lifetime.
    if (QFileInfo(targetProgram).fileName() != QStringLiteral("gio") &&
        !(QFileInfo(targetProgram).fileName() == QStringLiteral("hics-launch") && targetArguments.value(0) == QStringLiteral("--desktop-action"))) {
        args.removeLast();
        args << stage << QStringLiteral("--execute") << targetProgram;
    }
    args << targetArguments;
    const auto log = process.property("hics.application.log").toString();
    if (!log.isEmpty()) {
        const auto separator = args.indexOf(QStringLiteral("--"));
        args.insert(separator, QStringLiteral("--property=StandardOutput=append:") + log);
        args.insert(separator + 1, QStringLiteral("--property=StandardError=inherit"));
    }
    QObject::connect(&process, &QProcess::errorOccurred, &process, [environmentPath] { QFile::remove(environmentPath); });
    QObject::connect(&process, &QProcess::finished, &process, [environmentPath](int, QProcess::ExitStatus) { QFile::remove(environmentPath); });
    process.setProgram(runner);
    process.setArguments(args);
    return true;
}
}
