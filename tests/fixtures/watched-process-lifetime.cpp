#include "util/watchedprocess.hpp"
#include <QElapsedTimer>
#include <QEventLoop>
#include <QFile>
#include <QTemporaryDir>
#include <csignal>
#include <memory>
#include <unistd.h>

void require(bool ok, const char *message) { if (!ok) qFatal("%s", message); }
void until(const std::function<bool()> &condition) {
    QEventLoop loop;
    QTimer poll, deadline;
    poll.setInterval(5); deadline.setSingleShot(true); deadline.setInterval(4000);
    QObject::connect(&poll, &QTimer::timeout, &loop, [&] { if (condition()) loop.quit(); });
    QObject::connect(&deadline, &QTimer::timeout, &loop, [&] { qFatal("lifecycle fixture timed out"); });
    poll.start(); deadline.start(); if (!condition()) loop.exec();
}
qint64 pid(const QString &path) { QFile f(path); return f.open(QIODevice::ReadOnly) ? f.readAll().toLongLong() : 0; }
bool gone(qint64 value) { return value > 0 && kill(value, 0) == -1 && errno == ESRCH; }
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    if (app.arguments().value(1) == "--child") {
        signal(SIGTERM, SIG_IGN);
        QFile f(app.arguments().at(2)); require(f.open(QIODevice::WriteOnly), "child ready file");
        f.write(QByteArray::number(getpid())); f.close(); return app.exec();
    }
    QTemporaryDir tmp; require(tmp.isValid(), "temporary dir");
    const auto command = [&](const QString &name) { return QStringList{app.applicationFilePath(), "--child", tmp.filePath(name)}; };
    int changes = 0, errors = 0;
    auto watcher = std::make_unique<hics::util::WatchedProcess>([&] { ++changes; }, [&](QString) { ++errors; });
    watcher->request(command("a")); until([&] { return pid(tmp.filePath("a")) > 0; });
    const auto a = pid(tmp.filePath("a"));
    QElapsedTimer duration; duration.start();
    watcher->request(command("b")); watcher->request({}); watcher->request(command("c"));
    require(duration.elapsed() < 50, "replacement blocked UI");
    until([&] { return pid(tmp.filePath("c")) > 0; });
    require(!QFile::exists(tmp.filePath("b")) && gone(a), "old capture overlapped/newest request lost");
    const auto c = pid(tmp.filePath("c")); duration.restart(); watcher.reset();
    require(duration.elapsed() < 50, "owner destruction blocked UI");
    until([&] { return gone(c); }); require(errors == 0 && changes > 0, "cancellation reported error");
    watcher = std::make_unique<hics::util::WatchedProcess>([] {}, [&](QString) { ++errors; });
    watcher->request({tmp.filePath("absent")}); until([&] { return errors == 1; });
    watcher->request(command("retry")); until([&] { return pid(tmp.filePath("retry")) > 0; });
    const auto retry = pid(tmp.filePath("retry")); watcher.reset(); until([&] { return gone(retry); });
    std::unique_ptr<hics::util::WatchedProcess> reentrant;
    reentrant = std::make_unique<hics::util::WatchedProcess>([&] { reentrant.reset(); }, [](QString) {});
    reentrant->request(command("reentrant")); until([&] { return !reentrant; });
    // Exercise the app-destructor fallback without another event-loop turn.
    watcher = std::make_unique<hics::util::WatchedProcess>([] {}, [](QString) {});
    watcher->request(command("final")); until([&] { return pid(tmp.filePath("final")) > 0; });
    const auto final = pid(tmp.filePath("final")); watcher.reset();
    printf("FINAL_CHILD %lld\n", static_cast<long long>(final));
    puts("WATCHED_PROCESS_COMPLETE");
    return 0;
}
