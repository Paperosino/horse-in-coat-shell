#include "desktopconveniences.hpp"
#include "safecleanup.hpp"
#include "util/applicationenv.hpp"
#include <QAudioDevice>
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusObjectPath>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QDBusVariant>
#include <QDateTime>
#include <QDir>
#include <QDirIterator>
#include <QFileInfo>
#include <QFutureWatcher>
#include <QMediaDevices>
#include <QProcess>
#include <QProcessEnvironment>
#include <QSaveFile>
#include <QStandardPaths>
#include <QTimer>
#include <QUrl>
#include <QtConcurrent>
#include <cmath>
#include <cstring>
#include <memory>
#include <utility>
using namespace Qt::StringLiterals;
namespace hyprstack::services {
DesktopConveniences::DesktopConveniences(QObject *p) : QObject(p) {
  auto *watcher = new QDBusServiceWatcher(
      u"org.freedesktop.login1"_s, QDBusConnection::systemBus(),
      QDBusServiceWatcher::WatchForOwnerChange, this);
  connect(watcher, &QDBusServiceWatcher::serviceOwnerChanged, this,
          [this](const QString &, const QString &, const QString &owner) {
            m_lid = QDBusUnixFileDescriptor();
            m_sessionActive = false;
            m_sessionPath.clear();
            ++m_busGeneration;
            m_sessionPending = m_lidPending = false;
            emit changed();
            if (!owner.isEmpty() && m_dockRequested)
              ensureSession();
          });
  m_cameraBlocked = QFileInfo::exists(
      QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) +
      u"/wireplumber/wireplumber.conf.d/90-hics-camera-privacy.conf"_s);
}
DesktopConveniences::~DesktopConveniences() {
  stopSpeakerTest();
  if (m_portal && m_portal->state() != QProcess::NotRunning) {
    m_portal->terminate();
    if (!m_portal->waitForFinished(1000)) {
      m_portal->kill();
      m_portal->waitForFinished(200);
    }
  }
}
void DesktopConveniences::fail(const QString &error) {
  m_error = error;
  emit changed();
}
void DesktopConveniences::setDockInhibitRequested(bool requested) {
  m_dockRequested = requested;
  if (!requested) {
    m_lid = QDBusUnixFileDescriptor();
    emit changed();
    return;
  }
  if (!m_sessionActive) {
    ensureSession();
    return;
  }
  if (m_lid.isValid() || m_lidPending)
    return;
  m_lidPending = true;
  const int generation = m_busGeneration;
  auto call = QDBusMessage::createMethodCall(
      u"org.freedesktop.login1"_s, u"/org/freedesktop/login1"_s,
      u"org.freedesktop.login1.Manager"_s, u"Inhibit"_s);
  call.setArguments({u"handle-lid-switch"_s, u"hics"_s,
                     u"External display connected"_s, u"block"_s});
  auto *watcher = new QDBusPendingCallWatcher(
      QDBusConnection::systemBus().asyncCall(call, 5000), this);
  connect(watcher, &QDBusPendingCallWatcher::finished, this,
          [this, watcher, generation] {
            QDBusPendingReply<QDBusUnixFileDescriptor> reply = *watcher;
            watcher->deleteLater();
            if (generation != m_busGeneration)
              return;
            m_lidPending = false;
            if (reply.isError())
              fail(reply.error().message());
            else if (m_dockRequested && m_sessionActive) {
              m_lid = reply.value();
              m_error.clear();
              emit changed();
            }
          });
}
void DesktopConveniences::sessionProperties(const QString &interface,
                                            const QVariantMap &values,
                                            const QStringList &invalidated) {
  if (interface != u"org.freedesktop.login1.Session"_s)
    return;
  if (values.contains(u"Active"_s)) {
    m_sessionActive = values.value(u"Active"_s).toBool();
    if (!m_sessionActive) {
      m_lid = QDBusUnixFileDescriptor();
      emit changed();
    } else if (m_dockRequested)
      setDockInhibitRequested(true);
  } else if (invalidated.contains(u"Active"_s)) {
    m_lid = QDBusUnixFileDescriptor();
    m_sessionActive = false;
    ensureSession();
  }
}
void DesktopConveniences::ensureSession() {
  if (m_sessionPending)
    return;
  m_sessionPending = true;
  const int generation = m_busGeneration;
  auto call = QDBusMessage::createMethodCall(
      u"org.freedesktop.login1"_s, u"/org/freedesktop/login1"_s,
      u"org.freedesktop.login1.Manager"_s, u"GetSession"_s);
  call.setArguments({u"auto"_s});
  auto *watcher = new QDBusPendingCallWatcher(
      QDBusConnection::systemBus().asyncCall(call, 5000), this);
  connect(
      watcher, &QDBusPendingCallWatcher::finished, this,
      [this, watcher, generation] {
        QDBusPendingReply<QDBusObjectPath> reply = *watcher;
        watcher->deleteLater();
        if (generation != m_busGeneration)
          return;
        if (reply.isError()) {
          m_sessionPending = false;
          fail(reply.error().message());
          return;
        }
        const QString path = reply.value().path();
        if (m_sessionPath != path) {
          m_sessionPath = path;
          QDBusConnection::systemBus().connect(
              u"org.freedesktop.login1"_s, path,
              u"org.freedesktop.DBus.Properties"_s, u"PropertiesChanged"_s,
              this, SLOT(sessionProperties(QString, QVariantMap, QStringList)));
        }
        auto get = QDBusMessage::createMethodCall(
            u"org.freedesktop.login1"_s, path,
            u"org.freedesktop.DBus.Properties"_s, u"Get"_s);
        get.setArguments({u"org.freedesktop.login1.Session"_s, u"Active"_s});
        auto *state = new QDBusPendingCallWatcher(
            QDBusConnection::systemBus().asyncCall(get, 5000), this);
        connect(state, &QDBusPendingCallWatcher::finished, this,
                [this, state, generation] {
                  QDBusPendingReply<QDBusVariant> active = *state;
                  state->deleteLater();
                  if (generation != m_busGeneration)
                    return;
                  m_sessionPending = false;
                  if (active.isError()) {
                    fail(active.error().message());
                    return;
                  }
                  m_sessionActive = active.value().variant().toBool();
                  if (m_sessionActive && m_dockRequested)
                    setDockInhibitRequested(true);
                });
      });
}
void DesktopConveniences::stopSpeakerTest() {
  if (m_audio) {
    auto *audio = m_audio;
    m_audio = nullptr;
    audio->stop();
    audio->deleteLater();
  }
  if (m_buffer) {
    m_buffer->deleteLater();
    m_buffer = nullptr;
  }
  emit changed();
}
void DesktopConveniences::testSpeaker(int channel) {
  stopSpeakerTest();
  if (channel < 0 || channel > 1)
    return;
  const auto device = QMediaDevices::defaultAudioOutput();
  QAudioFormat format;
  format.setSampleRate(48000);
  format.setChannelCount(2);
  format.setSampleFormat(QAudioFormat::Int16);
  if (device.isNull() || !device.isFormatSupported(format)) {
    fail(u"Stereo speaker testing is not supported by this output"_s);
    return;
  }
  QByteArray data(48000 * 2 * 2, 0);
  for (int frame = 0; frame < 48000; ++frame) {
    const double envelope =
        std::min({1., frame / 2400., (48000 - frame) / 2400.});
    const qint16 sample =
        qint16(std::sin(frame * 2. * 3.141592653589793 * 440. / 48000.) *
               4500. * envelope);
    const int offset = (frame * 2 + channel) * 2;
    std::memcpy(data.data() + offset, &sample, sizeof(sample));
  }
  m_buffer = new QBuffer(this);
  m_buffer->setData(data);
  m_buffer->open(QIODevice::ReadOnly);
  m_audio = new QAudioSink(device, format, this);
  m_audio->setVolume(.5);
  connect(m_audio, &QAudioSink::stateChanged, this,
          [this](QAudio::State state) {
            if (state == QAudio::IdleState)
              stopSpeakerTest();
            else if (state == QAudio::StoppedState && m_audio &&
                     m_audio->error() != QAudio::NoError)
              fail(u"Audio output could not start"_s);
          });
  m_error.clear();
  m_audio->start(m_buffer);
  emit changed();
  QTimer::singleShot(2000, m_audio, [this, audio = m_audio] {
    if (m_audio == audio)
      stopSpeakerTest();
  });
}
void DesktopConveniences::setCameraBlocked(bool blocked) {
  if (m_busy || blocked == m_cameraBlocked)
    return;
  const QString directory = QStandardPaths::writableLocation(
                                QStandardPaths::ConfigLocation) +
                            u"/wireplumber/wireplumber.conf.d"_s,
                path = directory + u"/90-hics-camera-privacy.conf"_s;
  const QByteArray rule =
      "# Managed by hics: software camera privacy (PipeWire "
      "only)\nwireplumber.profiles = { main = { monitor.v4l2 = disabled "
      "monitor.libcamera = disabled } }\n";
  QFile old(path);
  QByteArray previous;
  if (old.exists()) {
    if (!old.open(QIODevice::ReadOnly) || old.size() > 4096) {
      fail(u"Cannot read camera privacy configuration"_s);
      return;
    }
    previous = old.readAll();
    if (previous != rule) {
      fail(u"Camera privacy configuration was modified externally"_s);
      return;
    }
  }
  if (blocked) {
    QDir().mkpath(directory);
    QSaveFile file(path);
    if (!file.open(QIODevice::WriteOnly) || file.write(rule) != rule.size() ||
        !file.commit()) {
      fail(u"Could not save camera privacy configuration"_s);
      return;
    }
  } else if (!QFile::remove(path)) {
    fail(u"Could not remove camera privacy configuration"_s);
    return;
  }
  m_busy = true;
  m_error.clear();
  emit changed();
  auto *process = new QProcess(this);
  auto done = std::make_shared<bool>(false);
  auto finish = [this, process, path, previous, blocked,
                 done](int code, QProcess::ExitStatus status) {
    if (std::exchange(*done, true))
      return;
    m_busy = false;
    if (code == 0 && status == QProcess::NormalExit)
      m_cameraBlocked = blocked;
    else {
      if (previous.isEmpty())
        QFile::remove(path);
      else {
        QSaveFile file(path);
        if (file.open(QIODevice::WriteOnly)) {
          file.write(previous);
          file.commit();
        }
      }
      m_error =
          u"WirePlumber could not apply camera privacy; the configuration was restored"_s;
    }
    process->deleteLater();
    emit changed();
  };
  connect(process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished),
          this, finish);
  connect(process, &QProcess::errorOccurred, this,
          [finish](QProcess::ProcessError error) {
            if (error == QProcess::FailedToStart)
              finish(-1, QProcess::CrashExit);
          });
  process->setProcessEnvironment(hics::util::applicationEnvironment());
  process->start(u"systemctl"_s,
                 {u"--user"_s, u"restart"_s, u"wireplumber.service"_s});
  QTimer::singleShot(15000, process, [process] {
    if (process->state() != QProcess::NotRunning)
      process->kill();
  });
}
void DesktopConveniences::automaticCleanup(int days) {
  if (m_busy)
    return;
  const QString marker =
      QStandardPaths::writableLocation(QStandardPaths::GenericCacheLocation) +
      u"/hics/thumbnail-cleanup"_s;
  const QFileInfo info(marker);
  if (info.exists() &&
      info.lastModified().secsTo(QDateTime::currentDateTime()) < 86400)
    return;
  QDir().mkpath(QFileInfo(marker).absolutePath());
  QSaveFile file(marker);
  if (file.open(QIODevice::WriteOnly)) {
    file.write("1");
    file.commit();
  }
  clean(u"thumbnails"_s, qBound(1, days, 3650));
}
void DesktopConveniences::inspectCleanup() { cleanupJob({}, 0, false); }
void DesktopConveniences::clean(const QString &category, int days) {
  if (category != u"thumbnails"_s && category != u"trash"_s) {
    fail(u"Unknown cleanup category"_s);
    return;
  }
  cleanupJob(category, qBound(0, days, 3650), true);
}
void DesktopConveniences::cleanupJob(const QString &category, int days,
                                     bool remove) {
  if (m_busy)
    return;
  m_busy = true;
  m_error.clear();
  emit changed();
  const auto cache =
      QStandardPaths::writableLocation(QStandardPaths::GenericCacheLocation) +
      u"/thumbnails"_s;
  const auto trash =
      QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation) +
      u"/Trash"_s;
  auto *watcher = new QFutureWatcher<QVariantMap>(this);
  connect(watcher, &QFutureWatcher<QVariantMap>::finished, this,
          [this, watcher] {
            m_cleanup = watcher->result();
            m_error = m_cleanup.value(u"error"_s).toString();
            watcher->deleteLater();
            m_busy = false;
            emit changed();
          });
  watcher->setFuture(QtConcurrent::run([cache, trash, category, days, remove] {
    QVariantMap result;
    const auto cutoff = QDateTime::currentDateTime().addDays(-days);
    int failed = 0;
    for (const auto &type : {u"thumbnails"_s, u"trash"_s}) {
      const QString root = type == u"trash"_s ? trash + u"/files"_s : cache;
      quint64 size = 0;
      int count = 0;
      if (QFileInfo(root).isSymLink() ||
          QFileInfo(QFileInfo(root).absolutePath()).isSymLink()) {
        result[u"error"_s] = u"Cleanup location is a symbolic link"_s;
        continue;
      }
      const auto scan = hics::cleanup::scan(
          root, remove && category == type && type == u"thumbnails"_s,
          days == 0 ? 0 : cutoff.toSecsSinceEpoch());
      size = scan.bytes;
      count = scan.files;
      failed += scan.failed;
      if (scan.partial)
        result[u"partial"_s] = true;
      result[type] = QVariant::fromValue(size);
      if (count >= 100000)
        result[u"partial"_s] = true;
    }
    if (remove && category == u"trash"_s) {
      QProcess process;
      process.start(u"gio"_s, {u"trash"_s, u"--empty"_s});
      if (!process.waitForFinished(60000)) {
        process.kill();
        process.waitForFinished();
        ++failed;
      } else if (process.exitCode() != 0)
        ++failed;
    }
    if (failed)
      result[u"error"_s] = u"Some files could not be removed"_s;
    return result;
  }));
}
void DesktopConveniences::closePortal() {
  if (m_portal)
    m_portal->terminate();
}
void DesktopConveniences::openPortal(const QString &uri,
                                     const QString &language) {
  QUrl url(uri);
  if (!url.isValid() ||
      !QStringList{u"http"_s, u"https"_s}.contains(url.scheme()) ||
      url.host().isEmpty() || !url.userInfo().isEmpty()) {
    fail(u"Invalid captive portal address"_s);
    return;
  }
  if (m_portal && m_portal->state() != QProcess::NotRunning)
    return;
  const auto program = QStandardPaths::findExecutable(u"hics-portal"_s);
  if (program.isEmpty()) {
    fail(u"The network sign-in browser is not installed"_s);
    return;
  }
  m_error.clear();
  emit changed();
  auto *process = new QProcess(this);
  m_portal = process;
  connect(process, &QProcess::errorOccurred, this,
          [this, process](QProcess::ProcessError error) {
            fail(process->errorString());
            if (error == QProcess::FailedToStart) {
              if (m_portal == process)
                m_portal = nullptr;
              process->deleteLater();
            }
          });
  connect(process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished),
          this, [this, process](int, QProcess::ExitStatus) {
            if (m_portal == process)
              m_portal = nullptr;
            process->deleteLater();
          });
  auto env = hics::util::applicationEnvironment();
  if (!language.isEmpty())
    env.insert(u"LANGUAGE"_s, language);
  process->setProcessEnvironment(env);
  process->start(program, {url.toString()});
}
bool DesktopConveniences::launch(const QString &application) {
  const QMap<QString, QStringList> commands{
      {u"localsend"_s, {u"localsend"_s}},
      {u"kdeconnect"_s, {u"kdeconnect-app"_s}},
      {u"bluetooth"_s, {u"blueman-sendto"_s}},
      {u"bluetooth-receive"_s, {u"blueman-applet"_s}},
      {u"trash"_s, {u"gio"_s, u"open"_s, u"trash:///"_s}}};
  const auto args = commands.value(application);
  if (args.isEmpty())
    return false;
  if (QStandardPaths::findExecutable(args[0]).isEmpty()) {
    fail(u"Install the selected file sharing application first"_s);
    return false;
  }
  QProcess process;
  process.setProcessEnvironment(hics::util::applicationEnvironment());
  process.setProgram(args[0]);
  process.setArguments(args.mid(1));
  if (!process.startDetached()) {
    fail(u"Unable to open the selected application"_s);
    return false;
  }
  m_error.clear();
  emit changed();
  return true;
}
} // namespace hyprstack::services
