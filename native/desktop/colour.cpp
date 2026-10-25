#include "service.hpp"
#include <QColorSpace>
#include <QCryptographicHash>
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusObjectPath>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QSaveFile>
#include <QStandardPaths>
namespace HicsDesktop {
namespace {
QString quote(const QString &text) { return QString::fromUtf8(QJsonDocument(QJsonArray{text}).toJson(QJsonDocument::Compact)).mid(1).chopped(1); }
QMutex colourMutex;
QByteArray profile(const QString &path) {
    if (!QFileInfo(path).isAbsolute() || path.contains(QChar::Null) || path.contains(QLatin1Char('\n')) || path.contains(QLatin1Char('\r'))) throw std::runtime_error("Choose an absolute ICC file path");
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly) || file.size() < 128 || file.size() > 16 * 1024 * 1024)
        throw std::runtime_error("Choose a readable ICC profile smaller than 16 MiB");
    auto data = file.readAll();
    if (data.mid(36, 4) != "acsp" || data.mid(16, 4) != "RGB " || data.mid(12, 4) != "mntr" || !QColorSpace::fromIccProfile(data).isValid())
        throw std::runtime_error("This is not a supported RGB display ICC profile");
    return data;
}
void write(const QString &path, const QByteArray &data) {
    QSaveFile file(path);
    if (!file.open(QIODevice::WriteOnly) || !file.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner) || file.write(data) != data.size() || !file.commit())
        throw std::runtime_error("Cannot save colour profile settings");
}
void recover(const QString &journal, const QString &config) {
    if (!QFileInfo::exists(journal)) return;
    const auto entries = readJson(journal)["files"].toArray();
    if (entries.size() != 3) throw std::runtime_error("Colour recovery journal is invalid");
    const QStringList names{"hypr-user.lua", "colour-profiles.lua", "colour-profiles.json"};
    for (int i = 0; i < entries.size(); ++i) {
        const auto entry = entries[i].toObject();
        const auto before = QByteArray::fromBase64(entry["before"].toString().toLatin1());
        QFile current(config + "/" + names[i]);
        const bool exists = current.exists();
        if (exists && (!current.open(QIODevice::ReadOnly) || current.size() > 1024 * 1024)) throw std::runtime_error("Cannot inspect colour recovery files");
        const auto bytes = exists ? current.readAll() : QByteArray{};
        const auto hash = QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
        if (!((exists == entry["existed"].toBool() && bytes == before) || (exists && hash == entry["afterHash"].toString())))
            throw std::runtime_error("A colour configuration file changed elsewhere; automatic recovery preserved it");
    }
    for (int i = 0; i < entries.size(); ++i) {
        const auto entry = entries[i].toObject();
        const auto path = config + "/" + names[i];
        if (entry["existed"].toBool()) write(path, QByteArray::fromBase64(entry["before"].toString().toLatin1()));
        else if (QFileInfo::exists(path) && !QFile::remove(path)) throw std::runtime_error("Cannot restore colour configuration");
    }
    if (!QFile::remove(journal)) throw std::runtime_error("Cannot complete colour recovery");
    command("hyprctl", {"reload"}, 10000);
}
QJsonArray monitors() {
    auto result = command("hyprctl", {"monitors", "all", "-j"}, 5000);
    auto doc = QJsonDocument::fromJson(result.output);
    if (result.exitCode || !doc.isArray()) throw std::runtime_error("Cannot read connected monitors");
    return doc.array();
}
void reload() {
    auto r = command("hyprctl", {"reload"}, 10000);
    if (r.exitCode || r.output.trimmed() != "ok") throw std::runtime_error("Hyprland rejected the colour configuration");
    auto errors = command("hyprctl", {"configerrors"}, 5000);
    if (errors.exitCode || (!errors.output.trimmed().isEmpty() && errors.output.trimmed() != "ok"))
        throw std::runtime_error("Hyprland reported a configuration error; the previous colour settings were restored");
}
}
void Service::colour(const QSharedPointer<Job> &job) {
    const auto op = job->operation;
    const auto args = job->arguments;
    worker(job, [op, args, stateDirectory = directory] {
        QMutexLocker guard(&colourMutex);
        const auto config = QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + "/hics";
        const auto data = QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation) + "/icc";
        QDir().mkpath(config); QDir().mkpath(data);
        const auto journal = stateDirectory + "/colour-rollback.json";
        recover(journal, config);
        if (op == "colour.recover") return QJsonObject{{"ok", true}};
        if (op == "colour.import") {
            const auto bytes = profile(args["path"].toString());
            const auto path = data + "/hics-" + QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex()) + ".icc";
            write(path, bytes);
            return QJsonObject{{"path", path}};
        }
        if (op == "colour.status") {
            QJsonArray profiles; QStringList files;
            for (const auto &name : QDir(data).entryList({"*.icc", "*.icm"}, QDir::Files)) files << data + "/" + name;
            bool colord = false; QString colordError;
            auto get = [](const QString &path, const QString &iface, const QString &method, QVariantList args = {}) {
                auto msg = QDBusMessage::createMethodCall("org.freedesktop.ColorManager", path, iface, method); msg.setArguments(args);
                return QDBusConnection::systemBus().call(msg, QDBus::Block, 5000);
            };
            const auto reply = get("/org/freedesktop/ColorManager", "org.freedesktop.ColorManager", "GetProfiles");
            if (reply.type() == QDBusMessage::ReplyMessage && !reply.arguments().isEmpty()) {
                colord = true;
                for (const auto &path : qdbus_cast<QList<QDBusObjectPath>>(reply.arguments()[0])) {
                    const auto props = get(path.path(), "org.freedesktop.DBus.Properties", "GetAll", {"org.freedesktop.ColorManager.Profile"});
                    if (props.type() != QDBusMessage::ReplyMessage || props.arguments().isEmpty()) continue;
                    files << qdbus_cast<QVariantMap>(props.arguments()[0]).value("Filename").toString();
                }
            } else colordError = reply.errorMessage();
            files.removeDuplicates();
            for (const auto &path : files.mid(0, 256)) {
                try {
                    const auto bytes = profile(path);
                    const auto space = QColorSpace::fromIccProfile(bytes);
                    profiles.append(QJsonObject{{"path", path}, {"name", space.description().isEmpty() ? QFileInfo(path).fileName() : space.description()}});
                } catch (...) {} // Non-display printer/scanner profiles are not selectable.
            }
            return QJsonObject{{"profiles", profiles}, {"monitors", monitors()}, {"assignments", readJson(config + "/colour-profiles.json")}, {"colord", colord}, {"colordError", colordError}};
        }
        if (op == "colour.assign") {
            const auto output = args["output"].toString(), path = args["path"].toString();
            if (!QRegularExpression("^[A-Za-z0-9_.:-]{1,128}$").match(output).hasMatch()) throw std::runtime_error("Choose a connected monitor");
            bool found = false;
            for (const auto &m : monitors()) if (m.toObject()["name"].toString() == output) found = true;
            if (!found) throw std::runtime_error("The selected monitor was disconnected");
            if (!path.isEmpty()) profile(path);
            if (QFileInfo::exists(QFileInfo(stateDirectory).absolutePath() + "/configuration-preview.json")) throw std::runtime_error("Confirm or revert the configuration preview first");
            const auto runtime = QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);
            for (const auto &folder : QDir(runtime).entryList({"hics-displays-*"}, QDir::Dirs | QDir::NoDotAndDotDot))
                if (QFileInfo::exists(runtime + "/" + folder + "/pending.json")) throw std::runtime_error("Confirm or revert display changes first");
            auto assignments = readJson(config + "/colour-profiles.json");
            if (assignments.size() > 64) throw std::runtime_error("Too many colour assignments");
            // Keep an explicit empty ICC on reset: omitting it would retain the
            // previously applied profile inside the compositor's monitor rule.
            assignments[output] = path;
            QByteArray generated("-- Generated by hics colour profile settings.\n");
            for (auto it = assignments.begin(); it != assignments.end(); ++it) {
                if (!QRegularExpression("^[A-Za-z0-9_.:-]{1,128}$").match(it.key()).hasMatch() || !it.value().isString()) throw std::runtime_error("Invalid saved monitor assignment");
                const auto saved = it.value().toString();
                if (!saved.isEmpty()) profile(saved);
                generated += ("hl.monitor({output=" + quote(it.key()) + ",icc=" + quote(saved) + "})\n").toUtf8();
            }
            const auto hookPath = config + "/hypr-user.lua", generatedPath = config + "/colour-profiles.lua", jsonPath = config + "/colour-profiles.json";
            const QStringList targets{hookPath, generatedPath, jsonPath};
            QMap<QString, QByteArray> before; QSet<QString> existed;
            for (const auto &target : targets) { QFile f(target); if (f.exists()) { if (!f.open(QIODevice::ReadOnly) || f.size() > 1024 * 1024) throw std::runtime_error("Cannot back up colour configuration"); before[target] = f.readAll(); existed.insert(target); } }
            auto hook = before.value(hookPath);
            if (!hook.contains("colour-profiles.lua")) hook += ("\n-- hics colour profiles\ndo local p=" + quote(generatedPath) + ";local f=io.open(p);if f then f:close();dofile(p) end end\n").toUtf8();
            const QList<QByteArray> after{hook, generated, QJsonDocument(assignments).toJson()};
            QJsonArray entries; qsizetype total = 0;
            for (int i = 0; i < targets.size(); ++i) {
                total += before.value(targets[i]).size();
                entries.append(QJsonObject{{"before", QString::fromLatin1(before.value(targets[i]).toBase64())}, {"existed", existed.contains(targets[i])},
                    {"afterHash", QString::fromLatin1(QCryptographicHash::hash(after[i], QCryptographicHash::Sha256).toHex())}});
            }
            if (total > 1024 * 1024) throw std::runtime_error("Colour configuration is too large for safe recovery");
            writeJson(journal, {{"files", entries}});
            try { write(generatedPath, generated); write(hookPath, hook); write(jsonPath, QJsonDocument(assignments).toJson()); reload(); QFile::remove(journal); }
            catch (...) {
                recover(journal, config);
                throw;
            }
            return QJsonObject{{"ok", true}};
        }
        throw std::runtime_error("Unknown colour profile operation");
    });
}
}
