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
#include <cmath>
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
      fail("response timed out");
    });
  }
  ~GpuMetricsSampler() {
    reset();
    delete m_timeout;
  }
  GpuMetricsSampler(const GpuMetricsSampler &) = delete;
  GpuMetricsSampler &operator=(const GpuMetricsSampler &) = delete;
  void reset() {
    m_timeout->stop();
    m_callback = {};
    m_buffer.clear();
    m_activeId.clear();
    if (!m_process)
      return;
    auto *process = m_process.data();
    m_process = nullptr;
    process->disconnect(m_owner);
    // Keep a shutdown owner if the event loop exits before finished/deleteLater.
    // Removing the sampler must still never wait for a driver on the UI thread.
    process->setParent(QCoreApplication::instance());
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
    if (!callback)
      return;
    if (m_callback) {
      callback(-1, -1, -1, false);
      return;
    }
    if (m_backoff.isValid() && m_backoff.elapsed() < 30000) {
      callback(-1, -1, -1, false);
      return;
    }
    const auto command =
        thermal ? QByteArray("thermal\n")
                : (source.isEmpty() ? QByteArray("sample\n") : source + '\n');
    if (command != "thermal\n" && command != "sample\n" &&
        command != "generic\n" && command != "nvidia\n") {
      callback(-1, -1, -1, false);
      return;
    }
    m_activeId = QByteArray::number(++m_serial);
    m_command = command.chopped(1) + ' ' + m_activeId + '\n';
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
            // One bounded, tagged response per request. Never re-enter a
            // second request from a callback while consuming the old frame.
            if (!m_callback || process->bytesAvailable() + m_buffer.size() > 4096) {
              fail("unsolicited or oversized response");
              return;
            }
            m_buffer += process->read(4097 - m_buffer.size());
            const auto newline = m_buffer.indexOf('\n');
            if (newline < 0)
              return;
            if (newline != m_buffer.size() - 1) {
              fail("multiple response frames");
              return;
            }
            QJsonParseError error;
            const auto document = QJsonDocument::fromJson(m_buffer, &error);
            const auto object = document.object();
            const auto usage = object.value(QStringLiteral("usage"));
            const auto temperature = object.value(QStringLiteral("temperature"));
            const auto cpu = object.value(QStringLiteral("cpuTemperature"));
            const auto available = object.value(QStringLiteral("available"));
            const auto validMetric = [](const QJsonValue &value, double maximum) {
              return value.isDouble() && std::isfinite(value.toDouble()) &&
                     (value == QJsonValue(-1) || (value.toDouble() >= 0 && value.toDouble() <= maximum));
            };
            if (error.error != QJsonParseError::NoError || !document.isObject() ||
                object.value(QStringLiteral("requestId")).toString().toLatin1() != m_activeId ||
                !available.isBool() || !validMetric(usage, 100) ||
                !validMetric(temperature, 149) || !validMetric(cpu, 149) ||
                available.toBool() != (usage.toDouble() >= 0 || temperature.toDouble() >= 0 || cpu.toDouble() >= 0)) {
              fail("invalid or mismatched response");
              return;
            }
            m_buffer.clear();
            m_activeId.clear();
            if (!available.toBool())
              m_backoff.start();
            // Callback may reset/delete this sampler or its QObject owner.
            complete(usage.toDouble(), temperature.toDouble(), cpu.toDouble(), available.toBool());
          });
      QObject::connect(process, &QProcess::errorOccurred, m_owner,
                       [this, process](QProcess::ProcessError error) {
                         if (process != m_process ||
                             error != QProcess::FailedToStart)
                           return;
                         fail("helper failed to start");
                       });
      QObject::connect(process, &QProcess::finished, m_owner, [this, process] {
        if (process == m_process)
          fail("helper exited");
      });
      const auto helper = helperPath(QStringLiteral("hics-gpu-monitor"));
      process->start(helper, {});
    } else if (m_process->state() == QProcess::Running)
      m_process->write(m_command);
  }

private:
  void fail(const char *reason) {
    qWarning("hics GPU sampler: %s; backing off", reason);
    auto callback = std::exchange(m_callback, {});
    reset();
    m_backoff.start();
    if (callback)
      callback(-1, -1, -1, false);
  }
  void complete(double usage, double temperature, double cpuTemperature,
                bool available) {
    m_timeout->stop();
    auto callback = std::exchange(m_callback, {});
    if (callback)
      callback(usage, temperature, cpuTemperature, available);
  }
  QByteArray m_command;
  QByteArray m_buffer, m_activeId;
  quint64 m_serial = 0;
  QObject *m_owner;
  QPointer<QProcess> m_process;
  QTimer *m_timeout;
  QElapsedTimer m_backoff;
  std::function<void(double, double, double, bool)> m_callback;
};
} // namespace hics::performance
