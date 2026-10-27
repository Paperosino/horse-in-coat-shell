#include "runtimeperformance.hpp"
#include "telemetrypolicy.hpp"
#include "../../../../../native/system/game_activity.hpp"
#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMap>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSet>
#include <QStandardPaths>
#include <cmath>
#include <utility>

namespace hyprstack::services {
namespace {
void retireLeaseProcess(QProcess *process, QObject *owner) {
  process->disconnect(owner);
  for (auto *timer : process->findChildren<QTimer *>(QString(), Qt::FindDirectChildrenOnly))
    timer->stop();
  process->setParent(QCoreApplication::instance());
  // Disconnecting a consumer does not stop QProcess buffering stdout. Allow
  // small late release replies, but do not let a retiring helper flood RAM.
  auto budget = std::make_shared<qint64>(65536);
  const auto discard = [process, budget] {
    process->setReadChannel(QProcess::StandardOutput);
    const auto available = process->bytesAvailable();
    if (available > *budget) {
      qWarning("hics game lease: retired helper exceeded output budget");
      process->kill();
      process->closeReadChannel(QProcess::StandardOutput);
      return;
    }
    *budget -= available;
    if (available > 0) process->read(available);
  };
  QObject::connect(process, &QProcess::readyReadStandardOutput, process, discard);
  discard();
  // EOF allows acquired power/GameMode leases, including late replies, to
  // unwind in the helper. Never wait for D-Bus or the driver in the UI thread.
  process->closeWriteChannel();
  if (process->state() == QProcess::NotRunning) {
    process->deleteLater();
    return;
  }
  QObject::connect(process, &QProcess::finished, process, &QObject::deleteLater);
  QTimer::singleShot(4000, process, [process] {
    if (process->state() != QProcess::NotRunning)
      process->kill();
  });
}
QVariantMap defaults() {
  return {{"autoGameMode", false},
          {"fullscreenOnly", true},
          {"gameRules", QStringList{"steam_app_*", "gamescope"}},
          {"excludeRules",
           QStringList{"steam", "steamwebhelper", "lutris", "heroic"}},
          {"disableEffects", true},
          {"pauseWallpapers", true},
          {"reduceDockMotion", true},
          {"directScanout", 0},
          {"allowTearing", false},
          {"feralGameMode", false},
          {"performanceProfile", false},
          {"adaptiveQuality", false},
          {"qualityFloor", 1},
          {"sampleInterval", 3000},
          {"gpuHigh", 85},
          {"gpuLow", 50},
          {"qualityDwell", 15000},
          {"thermalGuard", false},
          {"temperatureHigh", 85},
          {"temperatureLow", 75},
          {"prefetch", false},
          {"allowOnBattery", false},
          {"prefetchAllowlist", QStringList{}},
          {"prefetchMiB", 8},
          {"prefetchCooldown", 60},
          {"prefetchCpu", 50},
          {"prefetchMemory", 75},
          {"prefetchConfidence", 70},
          {"prefetchTransitions", 3},
          {"prefetchMaxAge", 300}};
}
QByteArray read(const QString &path, qint64 limit = 65536) {
  QFile file(path);
  if (!file.open(QIODevice::ReadOnly))
    return {};
  const auto value = file.read(limit + 1);
  return value.size() <= limit ? value : QByteArray();
}
bool save(const QString &path, const QJsonObject &object) {
  if (!QDir().mkpath(QFileInfo(path).absolutePath()))
    return false;
  QSaveFile file(path);
  if (!file.open(QIODevice::WriteOnly))
    return false;
  file.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);
  const auto bytes = QJsonDocument(object).toJson(QJsonDocument::Compact);
  return file.write(bytes) == bytes.size() && file.commit();
}
bool matches(const QString &value, const QStringList &rules) {
  for (const auto &rule : rules)
    if (QRegularExpression::fromWildcard(
            rule, Qt::CaseInsensitive,
            QRegularExpression::NonPathWildcardConversion)
            .match(value)
            .hasMatch())
      return true;
  return false;
}
QString configPath() {
  return QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) +
         "/hics";
}
} // namespace
RuntimePerformance::RuntimePerformance(QObject *parent)
    : QObject(parent), m_directory(configPath()),
      m_historyPath(QStandardPaths::writableLocation(
                        QStandardPaths::GenericStateLocation) +
                    "/hics/prefetch.json"),
      m_settings(defaults()), m_nvidia(this) {
  m_clock.start();
  // Apply the same validation to disk and UI input, without rewriting every
  // key.
  const auto stored =
      QJsonDocument::fromJson(read(m_directory + "/performance.json"))
          .object()
          .toVariantMap();
  m_loading = true;
  for (auto it = stored.begin(); it != stored.end(); ++it)
    set(it.key(), it.value());
  m_loading = false;
  // Validate paired thresholds together, independent of JSON key ordering.
  if (m_settings.value("gpuLow").toInt() + 10 >
      m_settings.value("gpuHigh").toInt()) {
    m_settings["gpuLow"] = 50;
    m_settings["gpuHigh"] = 85;
  }
  if (m_settings.value("temperatureLow").toInt() + 5 >
      m_settings.value("temperatureHigh").toInt()) {
    m_settings["temperatureLow"] = 75;
    m_settings["temperatureHigh"] = 85;
  }
  if (m_settings.value("prefetch").toBool()) {
    const auto entries = QJsonDocument::fromJson(read(m_historyPath))
                             .object()
                             .value("visits")
                             .toArray();
    const auto now = QDateTime::currentSecsSinceEpoch();
    for (const auto &entry : entries) {
      const auto o = entry.toObject();
      const auto id = o.value("id").toString(),
                 exe = o.value("executable").toString();
      const auto time = o.value("time").toInteger();
      if (id.size() <= 160 && !id.isEmpty() && exe.size() <= 4096 && time > 0 &&
          time <= now && now - time < 30 * 86400)
        m_visits.push_back({id, exe, time});
    }
    while (m_visits.size() > 256)
      m_visits.removeFirst();
  }
  m_timer.setTimerType(Qt::CoarseTimer);
  connect(&m_timer, &QTimer::timeout, this, &RuntimePerformance::sample);
  m_saveTimer.setSingleShot(true);
  m_saveTimer.setInterval(5000);
  connect(&m_saveTimer, &QTimer::timeout, this,
          &RuntimePerformance::saveHistory);
  updateTimer();
}
RuntimePerformance::~RuntimePerformance() {
  m_gameMode=false;publishGameActivity();
  hics::performance::setTelemetryGaming(false);
  if (m_prefetch) {
    m_prefetch->disconnect(this);
    m_prefetch->setParent(nullptr);
    m_prefetch->closeWriteChannel();
    m_prefetch->kill();
    if (m_prefetch->state() == QProcess::NotRunning)
      m_prefetch->deleteLater();
    else
      connect(m_prefetch, &QProcess::finished, m_prefetch,
              &QObject::deleteLater);
  }
  if (m_saveTimer.isActive())
    saveHistory();
  // EOF lets the independent helper unwind acquisitions even after QML reload.
  if (m_lease) {
    retireLeaseProcess(std::exchange(m_lease, nullptr), this);
  }
}
bool RuntimePerformance::set(const QString &key, const QVariant &value) {
  if (!m_settings.contains(key))
    return false;
  QVariant next;
  const auto def = defaults().value(key);
  if (def.metaType().id() == QMetaType::Bool) {
    if (value.metaType().id() != QMetaType::Bool)
      return false;
    next = value.toBool();
  } else if (def.metaType().id() == QMetaType::QStringList) {
    if (!value.canConvert<QStringList>())
      return false;
    auto rules = value.toStringList();
    if (rules.size() > 64)
      return false;
    for (auto &rule : rules) {
      rule = rule.trimmed();
      if (rule.isEmpty() || rule.size() > 160 || rule.contains(QChar::Null))
        return false;
    }
    rules.removeDuplicates();
    next = rules;
  } else {
    bool ok = false;
    const auto number = value.toDouble(&ok);
    if (!ok || !std::isfinite(number) || std::floor(number) < number)
      return false;
    int low = 0, high = 100;
    if (key == "directScanout")
      high = 2;
    else if (key == "qualityFloor")
      high = 2;
    else if (key == "sampleInterval") {
      low = 2000;
      high = 30000;
    } else if (key == "qualityDwell") {
      low = 5000;
      high = 120000;
    } else if (key == "temperatureHigh") {
      low = 50;
      high = 110;
    } else if (key == "temperatureLow") {
      low = 30;
      high = 100;
    } else if (key == "prefetchMiB") {
      low = 1;
      high = 32;
    } else if (key == "prefetchCooldown") {
      low = 30;
      high = 3600;
    } else if (key == "prefetchTransitions") {
      low = 3;
      high = 30;
    } else if (key == "prefetchMaxAge") {
      low = 30;
      high = 600;
    } else {
      low = 10;
      high = 95;
    }
    if (number < low || number > high)
      return false;
    next = int(number);
  }
  auto updated = m_settings;
  updated[key] = next;
  // Avoid two independent governor owners fighting over CPU policy.
  if (key == "feralGameMode" && next.toBool())
    updated["performanceProfile"] = false;
  if (key == "performanceProfile" && next.toBool())
    updated["feralGameMode"] = false;
  if (!m_loading && (updated.value("gpuLow").toInt() + 10 >
                         updated.value("gpuHigh").toInt() ||
                     updated.value("temperatureLow").toInt() + 5 >
                         updated.value("temperatureHigh").toInt()))
    return false;
  if (m_loading) {
    m_settings = updated;
    return true;
  }
  if (m_settings == updated)
    return true;
  if (!m_directory.isEmpty() && !save(m_directory + "/performance.json",
                                      QJsonObject::fromVariantMap(updated))) {
    m_status["error"] = "Unable to save performance preferences";
    queueStatus();
    return false;
  }
  m_status.remove("error");
  m_settings = updated;
  if (!m_settings.value("prefetch").toBool())
    stopPrefetch();
  const QPointer<RuntimePerformance> guard(this);
  evaluateGame();
  if (!guard) return false;
  updateTimer();
  updateLease();
  emit settingsChanged();
  return true;
}
void RuntimePerformance::observeWindow(const QVariantMap &window,
                                       const QString &desktopId,
                                       const QString &executable) {
  m_window = window;
  const QPointer<RuntimePerformance> guard(this);
  evaluateGame();
  if (!guard) return;
  const auto application = window.value("class").toString();
  if (!application.isEmpty() && application.size() <= 160 &&
      application != "org.quickshell" && !application.startsWith("org.hics.") &&
      application != "hics" &&
      m_status.value("lastApplication").toString() != application) {
    m_status["lastApplication"] = application;
    queueStatus();
  }
  if (!m_settings.value("prefetch").toBool() || m_locked ||
      desktopId.isEmpty() || desktopId.size() > 160 || executable.size() > 4096)
    return;
  if (desktopId == m_desktopId)
    return;
  m_desktopId = desktopId;
  m_executable = executable;
  if (executable.section('/', -1) == "env")
    m_executable.clear();
  const auto now = QDateTime::currentSecsSinceEpoch();
  m_visits.push_back({desktopId, m_executable, now});
  while (m_visits.size() > 256)
    m_visits.removeFirst();
  if (!m_saveTimer.isActive())
    m_saveTimer.start();
  // Prediction follows application changes, not a repeated spawn timer.
  tryPrefetch();
}
void RuntimePerformance::evaluateGame() {
  const auto cls = m_window.value("class").toString();
  const int fullscreen = m_window.value("fullscreen").toInt();
  // Hyprland: 1=maximized, 2=fullscreen, 3=both. Maximized is not fullscreen.
  const bool candidate =
      !m_locked && m_window.value("mapped", true).toBool() &&
      matches(cls, m_settings.value("gameRules").toStringList()) &&
      !matches(cls, m_settings.value("excludeRules").toStringList());
  const int pid = candidate ? m_window.value("pid").toInt() : 0;
  const bool automatic =
      m_settings.value("autoGameMode").toBool() && candidate &&
      (!m_settings.value("fullscreenOnly").toBool() || (fullscreen & 2));
  if (automatic == m_autoGame && pid == m_gamePid)
    return;
  m_autoGame = automatic;
  m_gamePid = pid;
  updateLease();
  emit gameChanged();
}
void RuntimePerformance::publishGameActivity() {
  const QString root=QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation)+"/hics";
  const QString path=root+"/game-mode-"+QString::number(QCoreApplication::applicationPid())+".json";
  if(!m_gameMode){QFile::remove(path);return;}
  QDir().mkpath(root);
  const auto pid=QCoreApplication::applicationPid();
  const auto start=hics::game::processStart("/proc/"+QString::number(pid)+"/stat");
  if(start.isEmpty())return;
  QSaveFile file(path);file.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner);
  if(file.open(QIODevice::WriteOnly)){file.write(QJsonDocument(QJsonObject{{"active",true},{"pid",pid},{"start",QString::fromLatin1(start)}}).toJson(QJsonDocument::Compact));file.commit();}
}
void RuntimePerformance::setSessionState(bool gameMode, bool onBattery,
                                         bool locked) {
  if (m_gameMode == gameMode && m_onBattery == onBattery && m_locked == locked)
    return;
  m_gameMode = gameMode;
  hics::performance::setTelemetryGaming(gameMode);
  publishGameActivity();
  m_onBattery = onBattery;
  m_locked = locked;
  if (gameMode || locked ||
      (onBattery && !m_settings.value("allowOnBattery").toBool()))
    stopPrefetch();
  const QPointer<RuntimePerformance> guard(this);
  evaluateGame();
  if (!guard) return;
  updateTimer();
  updateLease();
}
void RuntimePerformance::updateTimer() {
  const bool needed =
      !m_locked && ((m_settings.value("adaptiveQuality").toBool() &&
                     m_settings.value("qualityFloor").toInt() < 2) ||
                    m_settings.value("thermalGuard").toBool() ||
                    m_settings.value("prefetch").toBool());
  if (needed) {
    m_timer.setInterval(m_settings.value("sampleInterval").toInt());
    if (!m_timer.isActive())
      m_timer.start();
  } else {
    m_timer.stop();
    m_lastTotal = m_lastIdle = 0;
    m_nvidia.reset();
    m_nvidiaUsage = m_nvidiaTemperature = -1;
  }
  if (!m_settings.value("adaptiveQuality").toBool() &&
      !m_settings.value("thermalGuard").toBool()) {
    m_nvidia.reset();
    m_nvidiaUsage = m_nvidiaTemperature = -1;
  }
  m_policy.level =
      std::max(m_policy.level, m_settings.value("qualityFloor").toInt());
  if (!m_settings.value("adaptiveQuality").toBool()) {
    m_policy.level = 2;
    m_policy.highSamples = m_policy.lowSamples = 0;
  }
  if (!m_settings.value("thermalGuard").toBool())
    m_policy.hot = false;
  m_status["monitoring"] = needed;
  queueStatus();
}
void RuntimePerformance::sample() {
  double cpu = -1, gpu = -1, temperature = -1, memory = -1;
  QFile stat("/proc/stat");
  if (stat.open(QIODevice::ReadOnly)) {
    const auto fields = stat.readLine(1024).simplified().split(' ');
    if (fields.size() >= 9 && fields[0] == "cpu") {
      quint64 total = 0;
      for (int i = 1; i <= 8; ++i)
        total += fields[i].toULongLong();
      const quint64 idle = fields[4].toULongLong() + fields[5].toULongLong();
      if (m_lastTotal && total > m_lastTotal && idle >= m_lastIdle)
        cpu = std::clamp(100.0 * (1.0 - double(idle - m_lastIdle) /
                                            double(total - m_lastTotal)),
                         0.0, 100.0);
      m_lastTotal = total;
      m_lastIdle = idle;
    }
  }
  quint64 total = 0, available = 0;
  for (const auto &line : read("/proc/meminfo").split('\n')) {
    const auto fields = line.simplified().split(' ');
    if (fields.size() < 2)
      continue;
    if (fields[0] == "MemTotal:")
      total = fields[1].toULongLong();
    if (fields[0] == "MemAvailable:")
      available = fields[1].toULongLong();
  }
  if (total && available <= total)
    memory = 100.0 * (1.0 - double(available) / double(total));
  const bool graphics = m_settings.value("adaptiveQuality").toBool() ||
                        m_settings.value("thermalGuard").toBool();
  if (graphics) {
    m_nvidia.request(
        [this](double usage, double temp, double cpuTemp, bool valid) {
          m_nvidiaUsage = valid ? usage : -1;
          m_nvidiaTemperature = std::max(temp, cpuTemp);
          m_nvidiaSampledAt = m_clock.elapsed();
        },
        m_settings.value("thermalGuard").toBool());
    if (m_clock.elapsed() - m_nvidiaSampledAt <=
        std::max(5000, m_settings.value("sampleInterval").toInt() * 2)) {
      gpu = m_nvidiaUsage;
      temperature = m_nvidiaTemperature;
    }
  }
  m_policy.sample(
      gpu, temperature, m_settings.value("adaptiveQuality").toBool(),
      m_settings.value("thermalGuard").toBool(),
      m_settings.value("qualityFloor").toInt(),
      m_settings.value("gpuHigh").toInt(), m_settings.value("gpuLow").toInt(),
      m_settings.value("temperatureHigh").toInt(),
      m_settings.value("temperatureLow").toInt(), m_clock.elapsed(),
      m_settings.value("qualityDwell").toInt());
  const bool wasHot = m_status.value("thermalLimited").toBool();
  m_sampledAt = m_clock.elapsed();
  m_status["cpu"] = cpu;
  m_status["gpu"] = gpu;
  m_status["temperature"] = temperature;
  m_status["memory"] = memory;
  m_status["quality"] = quality();
  m_status["thermalLimited"] = m_policy.hot;

  if (m_policy.hot)
    stopPrefetch();
  if (wasHot != m_policy.hot)
    updateLease();
  queueStatus();
}
void RuntimePerformance::updateLease() {
  const bool eligible =
      m_gameMode && m_gamePid > 1 && !m_locked && !m_policy.hot &&
      (!m_onBattery || m_settings.value("allowOnBattery").toBool());
  const bool feral = eligible && m_settings.value("feralGameMode").toBool(),
             power =
                 eligible && m_settings.value("performanceProfile").toBool();
  const auto key = feral || power
                       ? QString::number(m_gamePid) + QString::number(feral) +
                             QString::number(power)
                       : QString();
  if (key == m_leaseKey)
    return;
  m_leaseKey = key;
  if (m_lease) {
    auto *previous = std::exchange(m_lease, nullptr);
    retireLeaseProcess(previous, this);
  }
  bool cleared = false;
  for (const auto &field : {"leaseError", "gamemodeError", "powerError"})
    cleared |= m_status.remove(field) > 0;
  if (cleared)
    queueStatus();
  if (key.isEmpty())
    return;
  const auto helper =
      hics::performance::helperPath(QStringLiteral("hics-game-lease"));
  auto *process = new QProcess(this);
  m_lease = process;
  process->setStandardErrorFile(QProcess::nullDevice());
  QStringList arguments{QString::number(m_gamePid)};
  if (feral)
    arguments << "--gamemode";
  if (power)
    arguments << "--performance";
  struct Response {
    QByteArray bytes;
    qsizetype total = 0;
    QSet<QString> received;
  };
  auto response = std::make_shared<Response>();
  QSet<QString> expected;
  if (feral) expected.insert(QStringLiteral("gamemode"));
  if (power) expected.insert(QStringLiteral("power"));
  auto *deadline = new QTimer(process);
  deadline->setSingleShot(true);
  connect(deadline, &QTimer::timeout, this, [this, process] {
    failLease(process, "acquisition response timed out");
  });
  connect(process, &QProcess::readyReadStandardOutput, this, [this, process, response, expected, deadline] {
    if (process != m_lease) return;
    if (process->bytesAvailable() > 16384 - response->total) {
      failLease(process, "response size limit exceeded");
      return;
    }
    const auto data = process->read(16385 - response->total);
    response->total += data.size();
    response->bytes += data;
    const auto previousCount = response->received.size();
    while (response->bytes.contains('\n')) {
      const auto end = response->bytes.indexOf('\n');
      if (end >= 8192) { failLease(process, "response frame too large"); return; }
      QJsonParseError error;
      const auto document = QJsonDocument::fromJson(response->bytes.left(end), &error);
      response->bytes.remove(0, end + 1);
      const auto row = document.object();
      const auto kind = row.value("lease").toString();
      if (error.error != QJsonParseError::NoError || !document.isObject() ||
          !expected.contains(kind) || response->received.contains(kind) || !row.value("error").isString()) {
        failLease(process, "invalid or repeated response");
        return;
      }
      response->received.insert(kind);
      m_status[kind + "Error"] = row.value("error").toString();
    }
    if (response->bytes.size() >= 8192 || (response->received == expected && !response->bytes.isEmpty())) {
      failLease(process, "unterminated or extra response");
      return;
    }
    if (response->received == expected) deadline->stop();
    if (response->received.size() != previousCount) queueStatus();
  });
  connect(process, &QProcess::errorOccurred, this,
          [this, process](QProcess::ProcessError) {
            failLease(process, "helper process error");
          });
  connect(process, &QProcess::finished, this,
          [this, process, response, expected](int code, QProcess::ExitStatus exit) {
            if (process != m_lease) return;
            m_lease = nullptr;
            if (code || exit != QProcess::NormalExit || response->received != expected) {
              m_status["leaseError"] = "Game lease ended unexpectedly";
              queueStatus();
            }
            retireLeaseProcess(process, this);
          });
  deadline->start(4000);
  process->start(helper, arguments);
}
void RuntimePerformance::queueStatus() {
  if (m_statusQueued) return;
  m_statusQueued = true;
  QMetaObject::invokeMethod(this, [this] {
    m_statusQueued = false;
    emit statusChanged(); // Receivers may synchronously destroy this object.
  }, Qt::QueuedConnection);
}
void RuntimePerformance::failLease(QProcess *process, const char *reason) {
  if (process != m_lease) return;
  qWarning("hics game lease: %s", reason); // Never log helper payloads.
  m_lease = nullptr;
  m_status["leaseError"] = tr("The game performance helper failed. Disable and re-enable its power-profile or GameMode integration to retry. See the system journal for details.");
  retireLeaseProcess(process, this);
  queueStatus();
}
void RuntimePerformance::saveHistory() {
  if (!m_settings.value("prefetch").toBool())
    return;
  QJsonArray entries;
  for (const auto &visit : m_visits)
    entries.append(QJsonObject{{"id", visit.id},
                               {"executable", visit.executable},
                               {"time", visit.time}});
  while (!entries.isEmpty() && QJsonDocument(QJsonObject{{"visits", entries}})
                                       .toJson(QJsonDocument::Compact)
                                       .size() > 65536)
    entries.removeFirst();
  save(m_historyPath, {{"visits", entries}});
}
void RuntimePerformance::forgetHistory() {
  ++m_prefetchSerial;
  stopPrefetch();
  m_visits.clear();
  m_desktopId.clear();
  m_saveTimer.stop();
  QFile::remove(m_historyPath);
  m_status.remove("prediction");
  m_status["prefetchedBytes"] = 0;
  queueStatus();
}
void RuntimePerformance::tryPrefetch() {
  if (!m_settings.value("prefetch").toBool() || m_gameMode || m_gamePid > 0 ||
      (m_window.value("fullscreen").toInt() & 2) || m_policy.hot || m_locked ||
      (m_onBattery && !m_settings.value("allowOnBattery").toBool()) ||
      m_prefetch ||
      m_clock.elapsed() - m_lastPrefetch <
          m_settings.value("prefetchCooldown").toInt() * 1000LL)
    return;
  const double cpu = m_status.value("cpu", -1).toDouble(),
               memory = m_status.value("memory", -1).toDouble();
  if (m_clock.elapsed() - m_sampledAt > 5000)
    return;
  const auto pressure = [](const QString &file) {
    const auto match = QRegularExpression("some avg10=([0-9.]+)")
                           .match(QString::fromLatin1(read(file, 4096)));
    return match.hasMatch() ? match.captured(1).toDouble() : -1.0;
  };
  if (!hics::performance::prefetchBudget(
          cpu, memory, pressure("/proc/pressure/memory"),
          pressure("/proc/pressure/io"),
          m_settings.value("prefetchCpu").toInt(),
          m_settings.value("prefetchMemory").toInt()))
    return;
  const auto prediction = hics::performance::predict(
      m_visits, m_desktopId,
      m_settings.value("prefetchAllowlist").toStringList(),
      m_settings.value("prefetchTransitions").toInt(),
      m_settings.value("prefetchConfidence").toInt(),
      QDateTime::currentSecsSinceEpoch(),
      m_settings.value("prefetchMaxAge").toInt());
  if (!prediction)
    return;
  const auto predicted = prediction->id;
  const auto path = prediction->executable;
  if (path.isEmpty())
    return;
  m_lastPrefetch = m_clock.elapsed();
  m_status["prediction"] = predicted;
  m_status["prefetchedBytes"] = 0;
  m_status["prefetchBusy"] = true;
  queueStatus();
  const auto serial = ++m_prefetchSerial;
  const auto helper =
      hics::performance::helperPath(QStringLiteral("hics-prefetch"));
  auto *process = new QProcess(this);
  m_prefetch = process;
  process->setStandardErrorFile(QProcess::nullDevice());
  connect(process, &QProcess::finished, this,
          [this, process, serial](int code, QProcess::ExitStatus exit) {
            if (m_prefetch == process)
              m_prefetch = nullptr;
            if (serial == m_prefetchSerial && !code &&
                exit == QProcess::NormalExit) {
              const auto result =
                  QJsonDocument::fromJson(process->readAllStandardOutput())
                      .object();
              m_status["prefetchedBytes"] =
                  result.value("advisedBytes").toInteger();
            }
            m_status["prefetchBusy"] = false;
            process->deleteLater();
            queueStatus();
          });
  connect(process, &QProcess::errorOccurred, this,
          [this, process](QProcess::ProcessError error) {
            if (error != QProcess::FailedToStart)
              return;
            if (m_prefetch == process)
              m_prefetch = nullptr;
            m_status["prefetchBusy"] = false;
            process->deleteLater();
            queueStatus();
          });
  // Never wait for a blocked filesystem operation in the GUI or a destructor.
  QTimer::singleShot(4000, process, [process] {
    if (process->state() != QProcess::NotRunning)
      process->kill();
  });
  process->start(
      helper, {path, QString::number(m_settings.value("prefetchMiB").toInt())});
}
void RuntimePerformance::stopPrefetch() {
  if (m_prefetch) {
    m_prefetch->closeWriteChannel();
    m_prefetch->kill();
  }
}
} // namespace hyprstack::services
