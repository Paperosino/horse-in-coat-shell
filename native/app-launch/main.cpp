#include <QCoreApplication>
#include <QProcess>
#include <QTextStream>
#include <unistd.h>
#include <vector>
#include "util/applicationlaunch.hpp"
#pragma push_macro("signals")
#undef signals
#include <gio/gdesktopappinfo.h>
#pragma pop_macro("signals")
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    auto args = app.arguments().mid(1);
    if (args.size() >= 2 && args[0] == "--execute") {
        QProcess launch;
        launch.setProgram(args[1]); launch.setArguments(args.mid(2));
        launch.setProcessEnvironment(hics::util::applicationEnvironment());
        if (launch.startDetached()) return 0;
        QTextStream(stderr) << launch.errorString() << Qt::endl;
        return 1;
    }
    if (args.size() >= 3 && args[0] == "--scope-stage") {
        const auto file = args[1];
        const auto runtime = qEnvironmentVariable("XDG_RUNTIME_DIR");
        if (!file.startsWith(runtime + "/hics-launch-") || !file.endsWith(".env") || (QFileInfo::exists(file) && !QFile::remove(file))) return 2;
        args = args.mid(2);
        QList<QByteArray> bytes;
        for (const auto &arg : args) bytes << arg.toLocal8Bit();
        std::vector<char *> argv;
        for (auto &arg : bytes) argv.push_back(arg.data());
        argv.push_back(nullptr);
        ::execvp(argv[0], argv.data());
        return 127;
    }
    if (args.size() == 3 && args[0] == "--desktop-action") {
        auto *info = g_desktop_app_info_new_from_filename(args[1].toUtf8());
        if (!info) return 1;
        bool found = false;
        for (auto actions = g_desktop_app_info_list_actions(info); actions && *actions; ++actions)
            found |= args[2] == QString::fromUtf8(*actions);
        if (!found) { g_object_unref(info); return 2; }
        g_desktop_app_info_launch_action(info, args[2].toUtf8(), nullptr);
        g_object_unref(info);
        return 0;
    }
    if (!args.isEmpty() && args[0] == "--") args.removeFirst();
    if (args.isEmpty()) { QTextStream(stderr) << "Usage: hics-launch -- PROGRAM [ARGUMENT...]\n"; return 2; }
    QProcess launch;
    launch.setProgram(args.takeFirst()); launch.setArguments(args);
    launch.setProcessEnvironment(hics::util::applicationEnvironment());
    hics::util::isolateApplication(launch);
    return launch.startDetached() ? 0 : 1;
}
