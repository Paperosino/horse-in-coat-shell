#pragma once
#include <QCoreApplication>
#include <QPointer>
#include <QProcess>
#include <QTimer>
#include <functional>
#include <utility>

namespace hics::util {
// Ordinary QML teardown only schedules SIGKILL/reaping. The application
// destructor is the sole bounded wait, after rendering has stopped.
class ProcessReaper final : public QObject {
public:
    using QObject::QObject;
    ~ProcessReaper() override {
        for (auto *process : findChildren<QProcess *>(QString(), Qt::FindDirectChildrenOnly)) {
            if (process->state() != QProcess::NotRunning) {
                process->kill();
                process->waitForFinished(1000);
            }
        }
    }
    static ProcessReaper *instance() {
        static QPointer<ProcessReaper> reaper;
        if (!reaper) reaper = new ProcessReaper(QCoreApplication::instance());
        return reaper;
    }
    void adopt(QProcess *process) {
        process->setParent(this);
        process->disconnect();
        if (process->state() == QProcess::NotRunning) process->deleteLater();
        else {
            // Failed exec has no finished() signal; reap on either terminal path.
            connect(process, &QProcess::stateChanged, process, [process](QProcess::ProcessState state) {
                if (state == QProcess::NotRunning) process->deleteLater();
            });
            process->kill();
        }
    }
};

// At most one child, latest-request-wins replacement, no GUI waits or idle
// polling. Failure retries require another explicit request.
class WatchedProcess final : public QObject {
public:
    WatchedProcess(std::function<void()> onChanged, std::function<void(QString)> onError,
                   QObject *parent = nullptr)
        : QObject(parent), m_changed(std::move(onChanged)), m_error(std::move(onError)),
          m_process(new QProcess(this)), m_reaper(ProcessReaper::instance()) {
        m_process->setStandardOutputFile(QProcess::nullDevice());
        m_timeout.setSingleShot(true);
        m_timeout.setInterval(800);
        connect(&m_timeout, &QTimer::timeout, this, [this] { m_process->kill(); });
        connect(m_process, &QProcess::readyReadStandardError, this, [this] {
            const auto data = m_process->readAllStandardError();
            m_detail.append(data.left(qMax(0, 4096 - int(m_detail.size()))));
        });
        connect(m_process, &QProcess::stateChanged, this, [this] { notify(); });
        connect(m_process, &QProcess::errorOccurred, this, [this](QProcess::ProcessError error) {
            if (error != QProcess::FailedToStart) return;
            m_timeout.stop();
            if (std::exchange(m_stopping, false)) scheduleStart();
            else report(QStringLiteral("Clipboard capture could not start. Check wl-clipboard installation."));
        });
        connect(m_process, &QProcess::finished, this, [this](int code, QProcess::ExitStatus) {
            m_timeout.stop();
            const bool replacing = std::exchange(m_stopping, false);
            if (replacing) scheduleStart();
            else if (code != 0) report(m_detail.isEmpty()
                ? QStringLiteral("Clipboard capture stopped unexpectedly")
                : QString::fromUtf8(m_detail).trimmed());
        });
    }
    ~WatchedProcess() override {
        m_timeout.stop();
        m_reaper->adopt(m_process);
    }
    bool running() const { return m_process->state() != QProcess::NotRunning; }
    void request(QStringList command) {
        if (m_command == command && running() && !m_stopping) return;
        ++m_generation;
        m_command = std::move(command);
        reconcile();
    }
private:
    void notify() {
        // A receiver may destroy the owner. Never invoke it inside a process
        // state transition, or access this after invoking it.
        if (m_notifyPending) return;
        m_notifyPending = true;
        QMetaObject::invokeMethod(this, [this] { m_notifyPending = false; m_changed(); }, Qt::QueuedConnection);
    }
    void report(QString error) {
        const auto generation = m_generation;
        QMetaObject::invokeMethod(this, [this, generation, error = std::move(error)] {
            if (generation == m_generation) m_error(error);
        }, Qt::QueuedConnection);
    }
    void scheduleStart() {
        QMetaObject::invokeMethod(this, [this] {
            if (!running()) reconcile();
        }, Qt::QueuedConnection);
    }
    void reconcile() {
        if (running()) {
            if (!m_stopping) {
                m_stopping = true;
                m_process->terminate();
                m_timeout.start();
            }
        } else if (!m_command.isEmpty()) {
            m_detail.clear();
            m_process->start(m_command.first(), m_command.sliced(1));
        }
    }
    std::function<void()> m_changed;
    std::function<void(QString)> m_error;
    QProcess *m_process;
    ProcessReaper *m_reaper;
    QTimer m_timeout;
    QStringList m_command;
    QByteArray m_detail;
    quint64 m_generation = 0;
    bool m_stopping = false, m_notifyPending = false;
};
} // namespace hics::util
