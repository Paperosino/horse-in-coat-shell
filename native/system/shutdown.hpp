#pragma once
#include <QSocketNotifier>
#include <QObject>
#include <functional>
#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <stdexcept>
#include <unistd.h>

namespace System {
namespace {
volatile sig_atomic_t shutdownWriteFd = -1;
void shutdownSignal(int signal) {
  const int saved = errno;
  const unsigned char value = static_cast<unsigned char>(signal);
  if (shutdownWriteFd >= 0) {
    const auto ignored = ::write(shutdownWriteFd, &value, sizeof(value));
    (void)ignored; // A full pipe already has a pending shutdown notification.
  }
  errno = saved;
}
}
// The signal handler only performs an async-signal-safe write. Qt, locks and
// thread-pool operations run in the application's event loop instead.
class ShutdownSignals final {
public:
  explicit ShutdownSignals(QObject* context, std::function<void()> stop) {
    if (pipe2(m_pipe, O_NONBLOCK | O_CLOEXEC)) throw std::runtime_error("Cannot create shutdown pipe");
    struct sigaction action{};
    action.sa_handler = shutdownSignal;
    sigemptyset(&action.sa_mask); action.sa_flags = SA_RESTART;
    shutdownWriteFd = m_pipe[1];
    if (sigaction(SIGTERM, &action, &m_term)) { closePipe(); throw std::runtime_error("Cannot register SIGTERM"); }
    if (sigaction(SIGINT, &action, &m_int)) {
      sigaction(SIGTERM, &m_term, nullptr); closePipe();
      throw std::runtime_error("Cannot register SIGINT");
    }
    m_notifier = new QSocketNotifier(m_pipe[0], QSocketNotifier::Read, context);
    QObject::connect(m_notifier, &QSocketNotifier::activated, context, [this, stop] {
      unsigned char buffer[64];
      while (::read(m_pipe[0], buffer, sizeof(buffer)) > 0) {}
      stop();
    });
  }
  ~ShutdownSignals() {
    sigaction(SIGTERM, &m_term, nullptr); sigaction(SIGINT, &m_int, nullptr);
    delete m_notifier; closePipe();
  }
private:
  void closePipe() { shutdownWriteFd = -1; for (int& fd : m_pipe) { if (fd >= 0) ::close(fd); fd = -1; } }
  int m_pipe[2]{-1,-1};
  struct sigaction m_term{}, m_int{};
  QSocketNotifier* m_notifier = nullptr;
};
}
