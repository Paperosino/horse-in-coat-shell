#pragma once
#include "performancehelpers.hpp"
#include <QCoreApplication>
#include <QElapsedTimer>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QProcess>
#include <QStandardPaths>
#include <QTimer>
#include <functional>
#include <utility>
namespace hics::performance {
// Driver calls can stall too. Keep NVML outside the UI, retain one sleeping
// native helper, and never wait for its shutdown on the GUI thread.
class GpuMetricsSampler {
public:
  explicit GpuMetricsSampler(QObject *owner)
      : m_owner(owner), m_timeout(new QTimer(owner)) {
    m_timeout->setSingleShot(true);
    m_timeout->setInterval(1500);
    QObject::connect(m_timeout, &QTimer::timeout, owner, [this] {
      m_backoff.start();
      if (m_process)
        m_process->kill();
      complete(-1, -1, -1, false);
    });
  }
  ~GpuMetricsSampler() {
    reset();
    delete m_timeout;
  }
  void reset() {
    m_timeout->stop();
    m_callback = {};
    if (!m_process)
      return;
    auto *process = m_process.data();
    m_process = nullptr;
    process->disconnect(m_owner);
    process->setParent(nullptr);
    process->closeWriteChannel();
    process->kill();
    if (process->state() == QProcess::NotRunning)
      process->deleteLater();
    else
      QObject::connect(process, &QProcess::finished, process,
                       &QObject::deleteLater);
  }
  void request(std::function<void(double, double, double, bool)> callback,
               bool thermal = false, const QByteArray &source = {}) {
    if (m_callback)
      return;
    if (m_backoff.isValid() && m_backoff.elapsed() < 30000) {
      callback(-1, -1, -1, false);
      return;
    }
    m_command =
        thermal ? QByteArray("thermal\n")
                : (source.isEmpty() ? QByteArray("sample\n") : source + '\n');
    m_callback = std::move(callback);
    m_timeout->start();
    if (!m_process) {
      auto *process = new QProcess(m_owner);
      m_process = process;
      process->setStandardErrorFile(QProcess::nullDevice());
      QObject::connect(process, &QProcess::started, m_owner,
                       [this, process] { process->write(m_command); });
      QObject::connect(
          process, &QProcess::readyReadStandardOutput, m_owner,
          [this, process] {
            if (process != m_process)
              return;
            while (process->canReadLine()) {
              const auto object =
                  QJsonDocument::fromJson(process->readLine(4096)).object();
              const bool available =
                  object.value(QStringLiteral("available")).toBool();
              if (!available)
                m_backoff.start();
              complete(
                  object.value(QStringLiteral("usage")).toDouble(-1),
                  object.value(QStringLiteral("temperature")).toDouble(-1),
                  object.value(QStringLiteral("cpuTemperature")).toDouble(-1),
                  available);
            }
          });
      QObject::connect(process, &QProcess::errorOccurred, m_owner,
                       [this, process](QProcess::ProcessError error) {
                         if (process != m_process ||
                             error != QProcess::FailedToStart)
                           return;
                         m_process = nullptr;
                         m_backoff.start();
                         complete(-1, -1, -1, false);
                         process->deleteLater();
                       });
      QObject::connect(process, &QProcess::finished, m_owner, [this, process] {
        if (process == m_process) {
          m_process = nullptr;
          m_backoff.start();
          complete(-1, -1, -1, false);
        }
        process->deleteLater();
      });
      const auto helper = helperPath(QStringLiteral("hics-gpu-monitor"));
      process->start(helper, {});
    } else if (m_process->state() == QProcess::Running)
      m_process->write(m_command);
  }

private:
  void complete(double usage, double temperature, double cpuTemperature,
                bool available) {
    m_timeout->stop();
    auto callback = std::exchange(m_callback, {});
    if (callback)
      callback(usage, temperature, cpuTemperature, available);
  }
  QByteArray m_command;
  QObject *m_owner;
  QPointer<QProcess> m_process;
  QTimer *m_timeout;
  QElapsedTimer m_backoff;
  std::function<void(double, double, double, bool)> m_callback;
};
} // namespace hics::performance
