#include "service.hpp"
#include "util/applicationlaunch.hpp"
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusObjectPath>
#include <QDBusVariant>
#include <QJsonArray>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QStandardPaths>
#include <QMutex>
#include <QMutexLocker>
#include <unistd.h>
namespace HicsDesktop {
namespace {
QVariantList call(const QString &service, const QString &path, const QString &interface,
                  const QString &method, const QVariantList &args = {}) {
    auto message = QDBusMessage::createMethodCall(service, path, interface, method);
    message.setArguments(args);
    message.setInteractiveAuthorizationAllowed(true);
    const auto reply = QDBusConnection::systemBus().call(message, QDBus::Block, 60000);
    if (reply.type() == QDBusMessage::ErrorMessage)
        throw std::runtime_error((reply.errorName() + ": " + reply.errorMessage()).toStdString());
    return reply.arguments();
}
QVariantMap properties(const QString &service, const QString &path, const QString &interface) {
    const auto reply = call(service, path, "org.freedesktop.DBus.Properties", "GetAll", {interface});
    return reply.isEmpty() ? QVariantMap{} : qdbus_cast<QVariantMap>(reply[0]);
}
QList<QDBusObjectPath> paths(const QVariantList &reply) {
    return reply.isEmpty() ? QList<QDBusObjectPath>{} : qdbus_cast<QList<QDBusObjectPath>>(reply[0]);
}
const QString accounts = "org.freedesktop.Accounts", accountPath = "/org/freedesktop/Accounts";
QJsonArray users() {
    QJsonArray rows;
    for (const auto &path : paths(call(accounts, accountPath, accounts, "ListCachedUsers"))) {
        const auto p = properties(accounts, path.path(), accounts + ".User");
        if (p.value("SystemAccount").toBool() || p.value("Uid").toULongLong() == 0) continue;
        rows.append(QJsonObject{{"path", path.path()}, {"uid", qint64(p.value("Uid").toULongLong())},
            {"name", p.value("UserName").toString()}, {"realName", p.value("RealName").toString()},
            {"administrator", p.value("AccountType").toInt() == 1}, {"locked", p.value("Locked").toBool()},
            {"current", p.value("Uid").toULongLong() == ::getuid()}});
    }
    return rows;
}
QJsonObject selectedUser(const QJsonObject &args, const QJsonArray &rows) {
    for (const auto &row : rows) if (row.toObject()["path"] == args["path"]) return row.toObject();
    throw std::runtime_error("Select an existing regular user");
}
QJsonArray sessions() {
    QJsonArray rows;
    const auto result = call("org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager", "ListSessions");
    if (result.isEmpty()) return rows;
    const auto argument = qvariant_cast<QDBusArgument>(result[0]);
    argument.beginArray();
    while (!argument.atEnd()) {
        QString id, user, seat; uint uid; QDBusObjectPath path;
        argument.beginStructure(); argument >> id >> uid >> user >> seat >> path; argument.endStructure();
        rows.append(QJsonObject{{"id", id}, {"uid", qint64(uid)}, {"user", user}, {"seat", seat},
            {"current", id == qEnvironmentVariable("XDG_SESSION_ID")}});
    }
    argument.endArray();
    return rows;
}
QJsonObject firmwareJson(const QStringList &args) {
    const auto result = command("fwupdmgr", QStringList{"--json", "--no-metadata-check", "--no-unreported-check"} + args, 45000, 4 * 1024 * 1024);
    const auto doc = QJsonDocument::fromJson(result.output);
    if (!doc.isObject()) throw std::runtime_error((result.error.isEmpty() ? QByteArray("fwupd did not return a structured response") : result.error.left(2048)).toStdString());
    auto json = doc.object();
    if (result.exitCode && result.exitCode != 2) {
        // fwupdmgr uses status 2 for 'nothing to do'; other failures remain visible.
        throw std::runtime_error((json["Error"].toString().isEmpty() ? QString::fromUtf8(result.error.left(2048)) : json["Error"].toString()).toStdString());
    }
    return json;
}
}
void Service::application(const QSharedPointer<Job> &job, const QString &program, const QStringList &args) {
    QProcess launch;
    launch.setProgram(program); launch.setArguments(args);
    if (!hics::util::isolateApplication(launch)) {
        launch.setProcessEnvironment(hics::util::applicationEnvironment());
        if (launch.startDetached()) finish(job, {{"launched", true}, {"isolated", false}, {"notice", "No user systemd manager: detached launch cannot guarantee cgroup isolation"}});
        else finish(job, {}, launch.errorString());
        return;
    }
    process(job, launch.program(), launch.arguments(), false, 15000);
}
void Service::platform(const QSharedPointer<Job> &job) {
    const auto op = job->operation;
    const auto args = job->arguments;
    if (op == "professional.remapper") {
        const auto tool = QStandardPaths::findExecutable("input-remapper-gtk");
        if (tool.isEmpty()) { finish(job, {}, "Install input-remapper to configure device button mappings"); return; }
        application(job, tool, {}); return;
    }
    if (op == "accounts.password") {
        // The system passwd/PAM stack owns password updates and keyring hooks.
        // Never retain plaintext or implement a parallel authentication stack.
        const auto name = args["name"].toString();
        if (!name.isEmpty() && !QRegularExpression("^[a-z_][a-z0-9_-]{0,31}$").match(name).hasMatch()) {
            finish(job, {}, "Invalid user name"); return;
        }
        if (!name.isEmpty() && !args["current"].toBool())
            application(job, "kitty", {"--hold", "--title", "hics · Password", "--", "pkexec", "/usr/bin/passwd", name});
        else application(job, "kitty", {"--hold", "--title", "hics · Password", "--", "/usr/bin/passwd"});
        return;
    }
    if (op == "accounts.fingerprint-enroll" || op == "accounts.fingerprint-verify") {
        const auto finger = args["finger"].toString();
        if (!QStringList{"left-thumb", "left-index-finger", "left-middle-finger", "left-ring-finger", "left-little-finger", "right-thumb", "right-index-finger", "right-middle-finger", "right-ring-finger", "right-little-finger"}.contains(finger)) {
            finish(job, {}, "Choose a valid finger"); return;
        }
        const auto tool = op == "accounts.fingerprint-enroll" ? QString("fprintd-enroll") : QString("fprintd-verify");
        if (QStandardPaths::findExecutable(tool).isEmpty()) { finish(job, {}, "Install fprintd to use fingerprints"); return; }
        application(job, "kitty", {"--hold", "--title", "hics · Fingerprint", "--", tool, "-f", finger});
        return;
    }
    if (op == "firmware.update") {
        const auto id = args["id"].toString();
        if (!QRegularExpression("^[a-fA-F0-9]{40}$").match(id).hasMatch() || !args["confirmed"].toBool()) {
            finish(job, {}, "Select a device and confirm the firmware update"); return;
        }
        // Keep upstream's device requests and confirmations interactive. No
        // --force, automatic reboot, power bypass or silent yes-to-all.
        application(job, "kitty", {"--hold", "--title", "hics · Firmware", "--", "fwupdmgr", "update", id});
        return;
    }
    if (op == "firmware.refresh") {
        process(job, "fwupdmgr", {"--json", "refresh"}, true, 180000); return;
    }
    worker(job, [op, args] {
        if (op == "accounts.fingerprint-delete") {
            const auto finger = args["finger"].toString();
            if (!QRegularExpression("^(left|right)-(thumb|index-finger|middle-finger|ring-finger|little-finger)$").match(finger).hasMatch() || !args["confirmed"].toBool())
                throw std::runtime_error("Select a finger and confirm its removal");
            static QMutex fingerprint; QMutexLocker lock(&fingerprint);
            const auto reply = call("net.reactivated.Fprint", "/net/reactivated/Fprint/Manager", "net.reactivated.Fprint.Manager", "GetDefaultDevice");
            if (reply.isEmpty()) throw std::runtime_error("No fingerprint reader available");
            const auto path = qvariant_cast<QDBusObjectPath>(reply[0]).path();
            call("net.reactivated.Fprint", path, "net.reactivated.Fprint.Device", "Claim", {QString()});
            try { call("net.reactivated.Fprint", path, "net.reactivated.Fprint.Device", "DeleteEnrolledFinger", {finger}); }
            catch (...) { try { call("net.reactivated.Fprint", path, "net.reactivated.Fprint.Device", "Release"); } catch (...) {} throw; }
            call("net.reactivated.Fprint", path, "net.reactivated.Fprint.Device", "Release");
            return QJsonObject{{"ok", true}};
        }
        if (op == "accounts.status") {
            QJsonObject out{{"users", users()}, {"sessions", sessions()}};
            try {
                const auto reply = call("net.reactivated.Fprint", "/net/reactivated/Fprint/Manager", "net.reactivated.Fprint.Manager", "GetDefaultDevice");
                if (!reply.isEmpty()) {
                    const auto path = qvariant_cast<QDBusObjectPath>(reply[0]).path();
                    const auto p = properties("net.reactivated.Fprint", path, "net.reactivated.Fprint.Device");
                    out["fingerprintReader"] = p.value("name").toString();
                    const auto enrolled = call("net.reactivated.Fprint", path, "net.reactivated.Fprint.Device", "ListEnrolledFingers", {QString()});
                    if (!enrolled.isEmpty()) out["fingers"] = QJsonArray::fromStringList(qdbus_cast<QStringList>(enrolled[0]));
                }
            } catch (const std::exception &e) { out["fingerprintError"] = QString::fromUtf8(e.what()); }
            return out;
        }
        if (op == "accounts.create" || op == "accounts.rename" || op == "accounts.role") {
            static QMutex mutations; QMutexLocker lock(&mutations);
            auto rows = users();
            if (op == "accounts.create") {
                const auto name = args["name"].toString(), real = args["realName"].toString().trimmed();
                if (!QRegularExpression("^[a-z_][a-z0-9_-]{0,31}$").match(name).hasMatch() || real.size() > 128 || real.contains(QChar::Null))
                    throw std::runtime_error("Invalid user name");
                const auto reply = call(accounts, accountPath, accounts, "CreateUser", {name, real, args["administrator"].toBool() ? 1 : 0});
                return QJsonObject{{"created", true}, {"path", reply.isEmpty() ? QString() : qvariant_cast<QDBusObjectPath>(reply[0]).path()},
                    {"notice", "The new account is locked until an administrator sets its initial password."}};
            }
            const auto user = selectedUser(args, rows);
            if (op == "accounts.role") {
                int administrators = 0;
                for (const auto &row : rows) if (row.toObject()["administrator"].toBool() && !row.toObject()["locked"].toBool()) ++administrators;
                if (!args["administrator"].toBool() && user["administrator"].toBool() && !user["locked"].toBool() && administrators <= 1)
                    throw std::runtime_error("The last available administrator must remain an administrator");
                call(accounts, user["path"].toString(), accounts + ".User", "SetAccountType", {args["administrator"].toBool() ? 1 : 0});
            } else {
                const auto name = args["realName"].toString().trimmed();
                if (name.isEmpty() || name.size() > 128 || name.contains(QChar::Null)) throw std::runtime_error("Invalid display name");
                call(accounts, user["path"].toString(), accounts + ".User", "SetRealName", {name});
            }
            return QJsonObject{{"ok", true}};
        }
        if (op == "accounts.activate" || op == "accounts.terminate") {
            const auto id = args["id"].toString(); bool found = false;
            for (const auto &row : sessions()) if (row.toObject()["id"].toString() == id) found = true;
            if (!found || id.isEmpty()) throw std::runtime_error("The selected session no longer exists");
            if (op == "accounts.terminate" && (!args["confirmed"].toBool() || id == qEnvironmentVariable("XDG_SESSION_ID")))
                throw std::runtime_error("Confirm another session before terminating it");
            call("org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager", op == "accounts.activate" ? "ActivateSession" : "TerminateSession", {id});
            return QJsonObject{{"ok", true}};
        }
        if (op == "firmware.history") return firmwareJson({"get-history"});
        if (op == "firmware.status") {
            if (QStandardPaths::findExecutable("fwupdmgr").isEmpty()) return QJsonObject{{"available", false}};
            auto state = firmwareJson({"get-devices"}); state["available"] = true;
            QJsonArray named;
            for (const auto &device : state["Devices"].toArray()) if (!device.toObject()["Name"].toString().isEmpty()) named.append(device);
            state["Devices"] = named;
            try { state["updates"] = firmwareJson({"get-updates"}); }
            catch (const std::exception &e) { state["updateError"] = QString::fromUtf8(e.what()); }
            return state;
        }
        throw std::runtime_error("Unknown platform operation");
    });
}
}
