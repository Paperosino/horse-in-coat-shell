#include "desktopintegration.hpp"
#include "wallpaperplayer.hpp"
#include <QAudioDevice>
#include <QCoreApplication>
#include <QElapsedTimer>
#include <QPointer>
#include <memory>
#include <QAudioFormat>
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusVariant>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLoggingCategory>
#include <QProcess>
#include <QStandardPaths>
#include <QUuid>
#include <cstring>
#include <cmath>
#include <algorithm>

using SettingsMap = QMap<QString, QVariantMap>;
using ManagedObjects = QMap<QDBusObjectPath, SettingsMap>;
Q_DECLARE_METATYPE(SettingsMap)
Q_DECLARE_METATYPE(ManagedObjects)
namespace hyprstack::services {
using namespace Qt::StringLiterals;
namespace {
Q_LOGGING_CATEGORY(lcDesktopOperations, "hics.services.desktop")
const auto NM = u"org.freedesktop.NetworkManager"_s;
const auto NP = u"/org/freedesktop/NetworkManager"_s;
const auto UD = u"org.freedesktop.UDisks2"_s;
void watchReply(QObject *owner, const QDBusPendingCall &call,
                std::function<void(const QDBusMessage &)> done) {
    auto *watcher = new QDBusPendingCallWatcher(call, owner);
    const QPointer<QDBusPendingCallWatcher> guard(watcher);
    auto consumed = std::make_shared<bool>(false);
    auto finish = [guard, consumed, done] {
        if (*consumed || !guard) return;
        *consumed = true;
        const auto reply = guard->reply();
        guard->deleteLater();
        done(reply);
    };
    QObject::connect(watcher, &QDBusPendingCallWatcher::finished, owner, finish);
    // A disconnected bus / immediately rejected request can already be done
    // when the watcher is constructed. Its signal must not strand busy state.
    if (watcher->isFinished()) QTimer::singleShot(0, owner, finish);
}
void asyncCall(QObject *owner, const QString &service, const QString &path,
               const QString &iface, const QString &method, const QVariantList &args,
               std::function<void(const QDBusMessage &)> done, int timeout = 90000) {
    auto message = QDBusMessage::createMethodCall(service, path, iface, method);
    message.setArguments(args);
    message.setInteractiveAuthorizationAllowed(true);
    watchReply(owner, QDBusConnection::systemBus().asyncCall(message, timeout), std::move(done));
}
bool validDisk(const QString &path, const QString &kind) {
    return path.startsWith(u"/org/freedesktop/UDisks2/"_s + kind + u"/"_s) &&
        !path.section(u'/', -1).isEmpty() && !path.contains(u".."_s);
}
}
DesktopIntegration::DesktopIntegration(QObject *parent) : QObject(parent) {
    qDBusRegisterMetaType<SettingsMap>();
    qDBusRegisterMetaType<ManagedObjects>();
    m_micTimeout.setSingleShot(true);
    m_micTimeout.setInterval(15000);
    connect(&m_micTimeout, &QTimer::timeout, this, &DesktopIntegration::stopMicrophoneTest);
}
DesktopIntegration::~DesktopIntegration() {
    // QProcess destruction waits for a running child. Reap killed helpers from
    // the event loop instead of blocking QML teardown or deleting their signal
    // sender while Qt is still handling a completion event.
    for (auto *process : findChildren<QProcess *>(QString(), Qt::FindDirectChildrenOnly)) {
        process->disconnect(this);
        for (auto *timer : process->findChildren<QTimer *>()) timer->stop();
        process->setParent(QCoreApplication::instance());
        process->closeReadChannel(QProcess::StandardOutput);
        process->closeReadChannel(QProcess::StandardError);
        if (process->state() == QProcess::NotRunning) process->deleteLater();
        else {
            connect(process, &QProcess::finished, process, &QObject::deleteLater);
            process->kill();
        }
    }
}
void DesktopIntegration::notifyChanged() {
    if (m_changedQueued) return;
    m_changedQueued = true;
    QMetaObject::invokeMethod(this, [this] {
        m_changedQueued = false;
        emit changed();
    }, Qt::QueuedConnection);
}
void DesktopIntegration::notifyMicrophoneChanged() {
    if (m_microphoneQueued) return;
    m_microphoneQueued = true;
    QMetaObject::invokeMethod(this, [this] {
        m_microphoneQueued = false;
        emit microphoneChanged();
    }, Qt::QueuedConnection);
}
QUrl DesktopIntegration::wallpaperVideo(const QString &path) const { return WallpaperPlayer::resolveVideo(path); }
void DesktopIntegration::fail(const QString &message) { m_error = message; notifyChanged(); }
void DesktopIntegration::process(const QString &program, const QStringList &args, Result result, bool reportError) {
    auto executable = QStandardPaths::findExecutable(program);
    if (executable.isEmpty()) {
        if (reportError) fail(tr("Required component is missing: %1").arg(program));
        return;
    }
    auto *p = new QProcess(this);
    auto env = QProcessEnvironment::systemEnvironment();
    env.insert(u"LC_ALL"_s, u"C"_s);
    p->setProcessEnvironment(env);
    ++m_pending; notifyChanged();
    auto *timeout = new QTimer(p);
    timeout->setSingleShot(true);
    struct Output {
        QByteArray standard, diagnostic;
        bool complete = false, overflow = false, timedOut = false;
    };
    auto output = std::make_shared<Output>();
    // Bound both pipes while they are being drained. A timeout alone allows a
    // fast or broken helper to allocate arbitrary memory before it expires.
    const auto drain = [p, output] {
        for (const auto channel : {QProcess::StandardOutput, QProcess::StandardError}) {
            p->setReadChannel(channel);
            auto &buffer = channel == QProcess::StandardOutput ? output->standard : output->diagnostic;
            const qsizetype limit = channel == QProcess::StandardOutput ? 16 * 1024 * 1024 : 64 * 1024;
            while (p->bytesAvailable() > 0) {
                const auto chunk = p->read(64 * 1024);
                if (chunk.isEmpty()) break;
                if (output->overflow) continue;
                if (chunk.size() > limit - buffer.size()) {
                    output->overflow = true;
                    output->standard.clear(); output->diagnostic.clear();
                    p->kill();
                } else buffer.append(chunk);
            }
        }
    };
    connect(p, &QProcess::readyReadStandardOutput, this, drain);
    connect(p, &QProcess::readyReadStandardError, this, drain);
    connect(timeout, &QTimer::timeout, p, [p, output] {
        output->timedOut = true;
        p->kill();
    });
    const auto finish = [this, p, timeout, output, drain, result, reportError, program](bool failedToStart, int code, QProcess::ExitStatus status) {
        if (output->complete) return;
        drain();
        output->complete = true;
        timeout->stop();
        --m_pending;
        if (output->overflow || output->timedOut)
            qCWarning(lcDesktopOperations) << program << (output->overflow ? "response size limit exceeded" : "operation timed out");
        // Detach before any result callback: it may synchronously delete this
        // owner while Qt is still emitting QProcess::finished/errorOccurred.
        p->disconnect(this);
        p->setParent(QCoreApplication::instance());
        p->deleteLater();
        notifyChanged();
        // Do not log argv or raw stderr: helpers can return private user data.
        if (!failedToStart && !output->overflow && !output->timedOut && code == 0 && status == QProcess::NormalExit)
            result(output->standard);
        else if (reportError) {
            if (output->overflow) fail(tr("The system component returned too much data. Refresh the page and check the system journal."));
            else if (output->timedOut) fail(tr("The system component did not respond in time. Check that its service is running and try again."));
            else if (failedToStart) fail(p->errorString());
            else {
                const auto detail = QString::fromUtf8(output->diagnostic.left(4096)).trimmed();
                fail(detail.isEmpty() ? tr("Operation failed or timed out") : detail);
            }
        } else result({});

    };
    connect(p, &QProcess::errorOccurred, this, [finish](QProcess::ProcessError error) {
        if (error == QProcess::FailedToStart) finish(true, -1, QProcess::CrashExit);
    });
    connect(p, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
            [finish](int code, QProcess::ExitStatus status) { finish(false, code, status); });
    timeout->start(15000); p->start(executable, args);
}
void DesktopIntegration::refresh() {
    if (busy()) return;
    auto message = QDBusMessage::createMethodCall(u"org.freedesktop.portal.Desktop"_s,
        u"/org/freedesktop/portal/desktop"_s, u"org.freedesktop.DBus.Properties"_s, u"Get"_s);
    message.setArguments({u"org.freedesktop.portal.ScreenCast"_s, u"AvailableSourceTypes"_s});
    ++m_pending;
    watchReply(this, QDBusConnection::sessionBus().asyncCall(message, 3000), [this](const QDBusMessage &reply) {
        --m_pending;
        m_portalSourceTypes = reply.type() == QDBusMessage::ErrorMessage ? 0
            : qdbus_cast<QDBusVariant>(reply.arguments().value(0)).variant().toInt();
        notifyChanged();
    });
    refreshDisks(); refreshWifi();
    m_recordingSources.clear();
    for (const auto &kind : {QString(u"monitors"_s), QString(u"clients"_s)}) {
        process(u"hyprctl"_s, {u"-j"_s, kind}, [this, kind](const QByteArray &raw) {
            const auto array = QJsonDocument::fromJson(raw).array();
            for (const auto &value : array) {
                const auto row = value.toObject();
                const bool window = kind == u"clients"_s;
                if (window && (!row[u"mapped"_s].toBool() || row[u"hidden"_s].toBool())) continue;
                const auto at = row[u"at"_s].toArray(), size = row[u"size"_s].toArray();
                const auto scale = std::max(0.25, row[u"scale"_s].toDouble(1));
                const auto transform = row[u"transform"_s].toInt();
                const int width = row[(transform % 2) ? u"height"_s : u"width"_s].toInt();
                const int height = row[(transform % 2) ? u"width"_s : u"height"_s].toInt();
                const int x = window ? at[0].toInt() : row[u"x"_s].toInt();
                const int y = window ? at[1].toInt() : row[u"y"_s].toInt();
                const int w = window ? size[0].toInt() : int(width / scale);
                const int h = window ? size[1].toInt() : int(height / scale);
                if (w <= 0 || h <= 0) continue;
                m_recordingSources.append(QVariantMap{{u"label"_s, window ? row[u"title"_s].toString() : row[u"name"_s].toString()},
                    {u"window"_s, window}, {u"geometry"_s, QString(u"%1,%2 %3x%4"_s).arg(x).arg(y).arg(w).arg(h)}});
            }
        }, false);
    }
    process(u"pactl"_s, {u"--format=json"_s, u"list"_s, u"cards"_s}, [this](const QByteArray &raw) {
        QJsonParseError error;
        auto document = QJsonDocument::fromJson(raw, &error);
        if (error.error != QJsonParseError::NoError || !document.isArray()) { fail(tr("Invalid audio device response")); return; }
        m_cards.clear();
        for (const auto &value : document.array()) {
            auto card = value.toObject();
            QVariantList profiles;
            auto all = card[u"profiles"_s].toObject();
            for (auto it = all.begin(); it != all.end(); ++it) {
                auto profile = it.value().toObject();
                if (profile[u"available"_s].toString() == u"no"_s) continue;
                profiles.append(QVariantMap{{u"name"_s, it.key()}, {u"description"_s, profile[u"description"_s].toString()}});
            }
            m_cards.append(QVariantMap{{u"name"_s, card[u"name"_s].toString()},
                {u"description"_s, card[u"properties"_s].toObject()[u"device.description"_s].toString()},
                {u"active"_s, card[u"active_profile"_s].toString()}, {u"profiles"_s, profiles}});
        }
    });
    refreshCapture();
}
void DesktopIntegration::refreshMonitoring() {
    if (busy()) return;
    refreshDisks();
    refreshCapture();
}
void DesktopIntegration::refreshCapture() {
    m_captureAvailable = !QStandardPaths::findExecutable(u"pw-dump"_s).isEmpty();
    if (!m_captureAvailable) { m_captures.clear(); notifyChanged(); return; }
    process(u"pw-dump"_s, {}, [this](const QByteArray &raw) {
        QJsonParseError error;
        auto document = QJsonDocument::fromJson(raw, &error);
        m_captureAvailable = error.error == QJsonParseError::NoError && document.isArray();
        if (!m_captureAvailable) { m_captures.clear(); return; }
        m_captures.clear();
        for (const auto &value : document.array()) {
            auto item = value.toObject();
            auto info = item[u"info"_s].toObject();
            auto props = info[u"props"_s].toObject();
            // Video capture includes cameras: only label a stream as screen capture
            // when PipeWire explicitly supplies a screen-sharing role.
            if (props[u"media.class"_s].toString() != u"Stream/Input/Video"_s) continue;
            auto role = props[u"media.role"_s].toString();
            m_captures.append(QVariantMap{{u"id"_s, item[u"id"_s].toInt()},
                {u"application"_s, props[u"application.name"_s].toString(props[u"node.name"_s].toString())},
                {u"screen"_s, role == u"Screen"_s || role == u"ScreenCapture"_s},
                {u"state"_s, info[u"state"_s].toString()}});
        }
    }, false);
}
void DesktopIntegration::setCardProfile(const QString &card, const QString &profile) {
    if (busy()) return;
    m_error.clear();
    process(u"pactl"_s, {u"set-card-profile"_s, card, profile}, [this](const QByteArray &) {
        QTimer::singleShot(0, this, &DesktopIntegration::refresh); emit operationSucceeded();
    });
}
void DesktopIntegration::startMicrophoneTest() {
    stopMicrophoneTest(); m_error.clear();
    auto device = QMediaDevices::defaultAudioInput();
    if (device.isNull()) { fail(tr("No microphone is available")); return; }
    // Connecting this signal initializes Qt's multimedia integration, including
    // codec/hardware probing. Network/storage status must not pay that cost.
    m_mediaDevices = new QMediaDevices(this);
    connect(m_mediaDevices, &QMediaDevices::audioInputsChanged, this, &DesktopIntegration::stopMicrophoneTest);
    auto format = device.preferredFormat();
    m_audio = new QAudioSource(device, format, this);
    connect(m_audio, &QAudioSource::stateChanged, this, [this](QtAudio::State) {
        if (m_audio && m_audio->error() != QtAudio::NoError) {
            fail(tr("Unable to read the microphone. Check its connection and permissions."));
            QTimer::singleShot(0, this, &DesktopIntegration::stopMicrophoneTest);
        }
    });
    auto *input = m_audio->start();
    if (!input) { fail(tr("Unable to start the microphone test")); stopMicrophoneTest(); return; }
    connect(input, &QIODevice::readyRead, this, [this, input, format] {
        auto data = input->readAll();
        const int bytes = format.bytesPerSample();
        qreal peak = 0;
        for (qsizetype i = 0; bytes > 0 && i + bytes <= data.size(); i += bytes) {
            float sample = 0;
            switch (format.sampleFormat()) {
            case QAudioFormat::UInt8: sample = (quint8(data[i]) - 128) / 128.f; break;
            case QAudioFormat::Int16: { qint16 v; std::memcpy(&v, data.constData()+i, 2); sample = v / 32768.f; break; }
            case QAudioFormat::Int32: { qint32 v; std::memcpy(&v, data.constData()+i, 4); sample = float(v) / 2147483648.f; break; }
            case QAudioFormat::Float: std::memcpy(&sample, data.constData()+i, 4); break;
            default: break;
            }
            if (std::isfinite(sample)) peak = std::max(peak, qreal(std::abs(sample)));
        }
        m_level = std::min(peak, qreal(1)); notifyMicrophoneChanged();
    });
    m_micTimeout.start(); notifyMicrophoneChanged();
}
void DesktopIntegration::stopMicrophoneTest() {
    m_micTimeout.stop();
    if (m_mediaDevices) {
        auto *devices = m_mediaDevices; m_mediaDevices = nullptr;
        disconnect(devices, nullptr, this, nullptr);
        devices->deleteLater();
    }
    if (m_audio) { auto *audio = m_audio; m_audio = nullptr; audio->stop(); audio->deleteLater(); }
    m_level = 0; notifyMicrophoneChanged();
}
void DesktopIntegration::refreshWifi() {
    ++m_pending;
    asyncCall(this, NM, NP, NM, u"GetDevices"_s, {}, [this](const QDBusMessage &r) {
        --m_pending;
        m_wifi.clear();
        if (r.type() == QDBusMessage::ErrorMessage) { notifyChanged(); return; }
        const auto paths = qdbus_cast<QList<QDBusObjectPath>>(r.arguments().value(0));
        for (const auto &path : paths) {
            ++m_pending;
            asyncCall(this, NM, path.path(), u"org.freedesktop.DBus.Properties"_s, u"GetAll"_s,
                {QString(NM) + u".Device"_s}, [this, path](const QDBusMessage &reply) {
                --m_pending;
                if (reply.type() != QDBusMessage::ErrorMessage) {
                    auto p = qdbus_cast<QVariantMap>(reply.arguments().value(0));
                    if (p.value(u"DeviceType"_s).toUInt() == 2) {
                        auto active = qdbus_cast<QDBusObjectPath>(p.value(u"ActiveConnection"_s)).path();
                        ++m_pending;
                        asyncCall(this, NM, path.path(), u"org.freedesktop.DBus.Properties"_s, u"GetAll"_s,
                            {QString(NM) + u".Device.Wireless"_s}, [this, path, p, active](const QDBusMessage &wireless) {
                            --m_pending;
                            const auto w = qdbus_cast<QVariantMap>(wireless.arguments().value(0));
                            m_wifi.append(QVariantMap{{u"path"_s, path.path()}, {u"name"_s, p.value(u"Interface"_s)}, {u"active"_s, active}, {u"hotspot"_s, w.value(u"Mode"_s).toUInt() == 3}, {u"supportsAp"_s, (w.value(u"WirelessCapabilities"_s).toUInt() & 0x40) != 0}});
                            notifyChanged();
                        }, 5000);
                    }
                }
                notifyChanged();
            }, 5000);
        }
        notifyChanged();
    }, 5000);
}
void DesktopIntegration::startHotspot(const QString &device, const QString &ssid, const QString &password) {
    if (busy()) return;
    if (!device.startsWith(QString(NP) + u"/Devices/"_s) || ssid.toUtf8().isEmpty() || ssid.toUtf8().size() > 32 ||
        password.size() < 8 || password.size() > 63 || std::any_of(password.begin(), password.end(), [](QChar c) { return c.unicode() < 32 || c.unicode() > 126; })) {
        fail(tr("Choose a Wi-Fi adapter, a name of 1–32 bytes and a password of 8–63 ASCII characters")); return;
    }
    SettingsMap settings{
        {u"connection"_s, {{u"id"_s, ssid}, {u"uuid"_s, QUuid::createUuid().toString(QUuid::WithoutBraces)}, {u"type"_s, u"802-11-wireless"_s}, {u"autoconnect"_s, false}}},
        {u"802-11-wireless"_s, {{u"ssid"_s, ssid.toUtf8()}, {u"mode"_s, u"ap"_s}}},
        {u"802-11-wireless-security"_s, {{u"key-mgmt"_s, u"wpa-psk"_s}, {u"psk"_s, password}}},
        {u"ipv4"_s, {{u"method"_s, u"shared"_s}}}, {u"ipv6"_s, {{u"method"_s, u"disabled"_s}}}};
    ++m_pending; m_error.clear(); notifyChanged();
    // Volatile connection disappears when deactivated; its password is not persisted.
    asyncCall(this, NM, NP, NM, u"AddAndActivateConnection2"_s,
        {QVariant::fromValue(settings), QVariant::fromValue(QDBusObjectPath(device)), QVariant::fromValue(QDBusObjectPath(u"/"_s)),
         QVariantMap{{u"persist"_s, u"volatile"_s}}}, [this](const QDBusMessage &r) {
        --m_pending; notifyChanged();
        if (r.type() == QDBusMessage::ErrorMessage) fail(tr("Could not start the hotspot: %1").arg(r.errorMessage()));
        else awaitActivation(qdbus_cast<QDBusObjectPath>(r.arguments().value(1)).path(), [this](bool success) {
            if (success) { QTimer::singleShot(0, this, &DesktopIntegration::refresh); emit operationSucceeded(); }
        });
    });
}
bool DesktopIntegration::connectHiddenNetwork(const QString &ssid, const QString &password, bool secured, bool hidden) {
    if (busy()) { fail(tr("System operations are busy. Try again shortly.")); return false; }
    if (ssid.toUtf8().isEmpty() || ssid.toUtf8().size() > 32 || (secured && (password.size() < 8 || password.size() > 63))) {
        fail(tr("Enter a network name of 1–32 bytes and a password of 8–63 characters")); return false;
    }
    SettingsMap settings{
        {u"connection"_s, {{u"id"_s, ssid}, {u"uuid"_s, QUuid::createUuid().toString(QUuid::WithoutBraces)}, {u"type"_s, u"802-11-wireless"_s}}},
        {u"802-11-wireless"_s, {{u"ssid"_s, ssid.toUtf8()}, {u"hidden"_s, hidden}}},
        {u"ipv4"_s, {{u"method"_s, u"auto"_s}}}, {u"ipv6"_s, {{u"method"_s, u"auto"_s}}}};
    if (secured) settings[u"802-11-wireless-security"_s] = {{u"key-mgmt"_s, u"wpa-psk"_s}, {u"psk"_s, password}};
    ++m_pending; m_error.clear(); notifyChanged();
    asyncCall(this, NM, NP, NM, u"AddAndActivateConnection2"_s,
        {QVariant::fromValue(settings), QVariant::fromValue(QDBusObjectPath(u"/"_s)), QVariant::fromValue(QDBusObjectPath(u"/"_s)),
         QVariantMap{{u"persist"_s, u"disk"_s}}}, [this](const QDBusMessage &r) {
        --m_pending; notifyChanged();
        if (r.type() == QDBusMessage::ErrorMessage) {
            fail(r.errorMessage()); emit hiddenNetworkFinished(false);
        } else awaitActivation(qdbus_cast<QDBusObjectPath>(r.arguments().value(1)).path(), [this](bool success) {
            const QPointer<DesktopIntegration> guard(this);
            emit hiddenNetworkFinished(success);
            if (!guard) return;
            if (success) { QTimer::singleShot(0, this, &DesktopIntegration::refresh); emit operationSucceeded(); }
        });
    });
    return true;
}
void DesktopIntegration::awaitActivation(const QString &path, std::function<void(bool)> done) {
    if (!path.startsWith(NP + u"/ActiveConnection/"_s)) {
        fail(tr("NetworkManager returned an invalid connection")); done(false); return;
    }
    ++m_pending;
    auto *timer = new QTimer(this);
    timer->setInterval(300);
    auto elapsed = std::make_shared<QElapsedTimer>();
    elapsed->start();
    QPointer<QTimer> guard(timer);
    const auto finish = [this, guard, done](bool success, const QString &error) {
        if (!guard) return;
        guard->stop(); guard->deleteLater();
        --m_pending;
        if (!success) fail(error);
        notifyChanged(); done(success);
    };
    connect(timer, &QTimer::timeout, this, [this, guard, path, finish, elapsed] {
        if (!guard || guard->property("waiting").toBool()) return;
        if (elapsed->elapsed() >= 60000) {
            finish(false, tr("Connection timed out. Check the network name, password and signal.")); return;
        }
        guard->setProperty("waiting", true);
        asyncCall(this, NM, path, u"org.freedesktop.DBus.Properties"_s, u"GetAll"_s,
            {NM + u".Connection.Active"_s}, [guard, finish](const QDBusMessage &reply) {
                if (!guard) return;
                guard->setProperty("waiting", false);
                if (reply.type() == QDBusMessage::ErrorMessage) { finish(false, reply.errorMessage()); return; }
                const auto state = qdbus_cast<QVariantMap>(reply.arguments().value(0)).value(u"State"_s).toUInt();
                if (state == 2) finish(true, {});
                else if (state == 4) finish(false, tr("Connection failed. Check the password, adapter and network availability."));
            }, 5000);
    });
    timer->start();
}
void DesktopIntegration::stopHotspot(const QString &active) {
    if (busy() || !active.startsWith(QString(NP) + u"/ActiveConnection/"_s)) return;
    // The UI only offers this for adapters whose wireless mode is AP (see status).
    ++m_pending; m_error.clear(); notifyChanged();
    asyncCall(this, NM, NP, NM, u"DeactivateConnection"_s, {QVariant::fromValue(QDBusObjectPath(active))}, [this](const QDBusMessage &r) {
        --m_pending; notifyChanged();
        if (r.type() == QDBusMessage::ErrorMessage) fail(r.errorMessage());
        else { QTimer::singleShot(0, this, &DesktopIntegration::refresh); emit operationSucceeded(); }
    });
}
void DesktopIntegration::refreshDisks() {
    ++m_pending;
    asyncCall(this, UD, u"/org/freedesktop/UDisks2"_s, u"org.freedesktop.DBus.ObjectManager"_s, u"GetManagedObjects"_s, {}, [this](const QDBusMessage &r) {
        --m_pending;
        if (r.type() == QDBusMessage::ErrorMessage) { m_encrypted.clear(); m_drives.clear(); notifyChanged(); return; }
        auto objects = qdbus_cast<ManagedObjects>(r.arguments().value(0));
        m_encrypted.clear(); m_drives.clear();
        QSet<QString> volumes;
        for (auto it = objects.cbegin(); it != objects.cend(); ++it) {
            const auto &ifaces = it.value();
            if (ifaces.contains(QString(UD) + u".Encrypted"_s)) {
                const auto p = ifaces.value(QString(UD) + u".Block"_s);
                const auto encrypted = ifaces.value(QString(UD) + u".Encrypted"_s);
                m_encrypted.append(QVariantMap{{u"path"_s, it.key().path()}, {u"label"_s, p.value(u"IdLabel"_s).toString()},
                    {u"device"_s, QString::fromUtf8(p.value(u"PreferredDevice"_s).toByteArray().split('\0').first())},
                    {u"unlocked"_s, qdbus_cast<QDBusObjectPath>(encrypted.value(u"CleartextDevice"_s)).path() != u"/"_s}});
            }
            if (ifaces.contains(QString(UD) + u".Drive"_s)) {
                const auto p = ifaces.value(QString(UD) + u".Drive"_s);
                if (p.value(u"Removable"_s).toBool() || p.value(u"ConnectionBus"_s).toString() == u"usb"_s)
                    m_drives.append(QVariantMap{{u"path"_s, it.key().path()}, {u"model"_s, p.value(u"Model"_s)},
                        {u"powerOff"_s, p.value(u"CanPowerOff"_s)}, {u"ejectable"_s, p.value(u"Ejectable"_s)}});
            }
            const auto block = ifaces.value(QString(UD) + u".Block"_s);
            auto drivePath = qdbus_cast<QDBusObjectPath>(block.value(u"Drive"_s));
            if (drivePath.path() == u"/"_s) {
                const auto backing = objects.value(qdbus_cast<QDBusObjectPath>(block.value(u"CryptoBackingDevice"_s))).value(UD + u".Block"_s);
                drivePath = qdbus_cast<QDBusObjectPath>(backing.value(u"Drive"_s));
            }
            const auto drive = objects.value(drivePath).value(UD + u".Drive"_s);
            if (ifaces.contains(QString(UD) + u".Filesystem"_s) && !block.value(u"HintIgnore"_s).toBool() &&
                (drive.value(u"Removable"_s).toBool() || drive.value(u"ConnectionBus"_s).toString() == u"usb"_s)) {
                volumes.insert(it.key().path());
                if (m_disksLoaded && !m_knownVolumes.contains(it.key().path())) {
                    const auto filesystem = ifaces.value(UD + u".Filesystem"_s);
                    const auto mounts = qdbus_cast<QList<QByteArray>>(filesystem.value(u"MountPoints"_s));
                    const QPointer<DesktopIntegration> guard(this);
                    if (mounts.isEmpty()) emit removableVolumeAdded(it.key().path());
                    else emit volumeMounted(QString::fromUtf8(mounts.first().split('\0').first()));
                    if (!guard) return;
                }
            }
        }
        m_knownVolumes = volumes; m_disksLoaded = true; notifyChanged();
    }, 5000);
}
void DesktopIntegration::diskCall(const QString &path, const QString &iface, const QString &method, const QVariantList &args) {
    if (busy()) return;
    const bool drive = iface.endsWith(u".Drive"_s);
    if (!validDisk(path, drive ? u"drives"_s : u"block_devices"_s)) { fail(tr("Invalid device path")); return; }
    ++m_pending; m_error.clear(); notifyChanged();
    asyncCall(this, UD, path, iface, method, args, [this, method](const QDBusMessage &r) {
        --m_pending; notifyChanged();
        if (r.type() == QDBusMessage::ErrorMessage) fail(r.errorMessage());
        else {
            QTimer::singleShot(0, this, &DesktopIntegration::refresh);
            const QPointer<DesktopIntegration> guard(this);
            if (method == u"Mount"_s) emit volumeMounted(r.arguments().value(0).toString());
            if (!guard) return;
            emit operationSucceeded();
        }
    });
}
void DesktopIntegration::unlockVolume(const QString &p, const QString &password) {
    diskCall(p, QString(UD) + u".Encrypted"_s, u"Unlock"_s, {password, QVariantMap{}});
}
void DesktopIntegration::lockVolume(const QString &p) { diskCall(p, QString(UD) + u".Encrypted"_s, u"Lock"_s, {QVariantMap{}}); }
void DesktopIntegration::ejectDrive(const QString &p, bool powerOff) {
    diskCall(p, QString(UD) + u".Drive"_s, powerOff ? u"PowerOff"_s : u"Eject"_s, {QVariantMap{}});
}
void DesktopIntegration::mountVolume(const QString &p) { diskCall(p, QString(UD) + u".Filesystem"_s, u"Mount"_s, {QVariantMap{}}); }
}
