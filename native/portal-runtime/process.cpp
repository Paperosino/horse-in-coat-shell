#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include "process.hpp"
#include <array>
#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <spawn.h>
#include <stdexcept>
#include <sys/epoll.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <system_error>
#include <unistd.h>
#include <utility>
extern char **environ;
namespace hics::portal {
namespace {
constexpr std::size_t limit = 1024 * 1024;
void checked(int value) {
  if (value)
    throw std::system_error(value, std::generic_category());
}
struct Fd {
  int value;
  explicit Fd(int initial = -1) : value(initial) {}
  Fd(const Fd &) = delete;
  Fd &operator=(const Fd &) = delete;
  ~Fd() {
    if (value >= 0)
      ::close(value);
  }
  int release() { return std::exchange(value, -1); }
};
struct Actions {
  posix_spawn_file_actions_t value;
  Actions() { checked(posix_spawn_file_actions_init(&value)); }
  ~Actions() { posix_spawn_file_actions_destroy(&value); }
};
struct Attributes {
  posix_spawnattr_t value;
  Attributes() { checked(posix_spawnattr_init(&value)); }
  ~Attributes() { posix_spawnattr_destroy(&value); }
};
void killGroup(pid_t pid, int signal) {
  if (pid > 0)
    ::kill(-pid, signal);
}
void reap(pid_t pid) {
  while (::waitpid(pid, nullptr, 0) < 0 && errno == EINTR) {
  }
}
} // namespace
struct Processes::Job {
  pid_t pid = -1;
  Fd output, error, identity;
  EventLoop::Timer deadline = 0, escalation = 0;
  Reason reason = Reason::Exited;
  std::string out, err;
  Callback callback;
  ~Job() {
    if (pid > 0) {
      killGroup(pid, SIGKILL);
      reap(pid);
    }
  }
};
Processes::Processes(EventLoop &value) : loop(value) {}
Processes::~Processes() { shutdown(); }
void Processes::shutdown() {
  (void)loop.nativeHandle();
  if (stopped)
    return;
  stopped = true;
  auto retired = std::move(jobs);
  for (auto &[id, job] : retired) {
    (void)id;
    loop.removeFd(job->identity.value);
    if (job->output.value >= 0)
      loop.removeFd(job->output.value);
    if (job->error.value >= 0)
      loop.removeFd(job->error.value);
    loop.removeTimer(job->deadline);
    loop.removeTimer(job->escalation);
    killGroup(job->pid, SIGKILL);
    reap(job->pid);
    job->pid = -1;
  }
}
Processes::Id
Processes::start(const std::vector<std::string> &argv,
                 const std::map<std::string, std::string> &environment,
                 std::chrono::milliseconds timeout, Callback callback) {
  (void)loop.nativeHandle();
  if (stopped)
    throw std::logic_error("Portal process supervisor is shut down");
  if (sequence == UINT64_MAX)
    throw std::overflow_error("Portal process ids exhausted");
  if (argv.empty() || argv.front().empty() || !callback ||
      timeout.count() <= 0 || timeout > std::chrono::minutes(10))
    throw std::invalid_argument("Invalid portal process request");
  if (jobs.size() >= 8)
    throw std::runtime_error("Portal process capacity reached");
  for (const auto &arg : argv)
    if (arg.find('\0') != std::string::npos)
      throw std::invalid_argument("NUL in argument");
  std::map<std::string, std::string> env;
  for (char **p = environ; p && *p; ++p) {
    std::string entry = *p;
    auto split = entry.find('=');
    if (split != std::string::npos)
      env[entry.substr(0, split)] = entry.substr(split + 1);
  }
  for (const auto &[key, value] : environment) {
    if (key.empty() || key.find_first_of("=\0", 0, 2) != std::string::npos ||
        value.find('\0') != std::string::npos)
      throw std::invalid_argument("Invalid environment entry");
    env[key] = value;
  }
  std::vector<std::string> storage;
  for (const auto &[key, value] : env)
    storage.push_back(key + "=" + value);
  std::vector<char *> args, vars;
  for (const auto &arg : argv)
    args.push_back(const_cast<char *>(arg.c_str()));
  args.push_back(nullptr);
  for (auto &entry : storage)
    vars.push_back(entry.data());
  vars.push_back(nullptr);
  Fd output, outputWriter, error, errorWriter;
  const auto pipe = [](Fd &reader, Fd &writer) {
    int descriptors[2];
    if (pipe2(descriptors, O_CLOEXEC) < 0)
      throw std::system_error(errno, std::generic_category());
    reader.value = descriptors[0];
    writer.value = descriptors[1];
    // Missing inherited stdin/stdout/stderr must not let the child file actions
    // overwrite one of the pipe endpoints before its dup2 action runs.
    for (auto *fd : {&reader, &writer}) {
      if (fd->value >= 3)
        continue;
      const int promoted = fcntl(fd->value, F_DUPFD_CLOEXEC, 3);
      if (promoted < 0)
        throw std::system_error(errno, std::generic_category());
      ::close(fd->release());
      fd->value = promoted;
    }
  };
  pipe(output, outputWriter);
  pipe(error, errorWriter);
  // Only read ends are nonblocking: applications may use ordinary stdio writes.
  if (fcntl(output.value, F_SETFL, O_NONBLOCK) < 0 ||
      fcntl(error.value, F_SETFL, O_NONBLOCK) < 0)
    throw std::system_error(errno, std::generic_category());
  Actions actions;
  Attributes attributes;
  checked(posix_spawn_file_actions_addopen(&actions.value, STDIN_FILENO,
                                           "/dev/null", O_RDONLY, 0));
  checked(posix_spawn_file_actions_adddup2(&actions.value, outputWriter.value,
                                           STDOUT_FILENO));
  checked(posix_spawn_file_actions_adddup2(&actions.value, errorWriter.value,
                                           STDERR_FILENO));
  checked(posix_spawn_file_actions_addclosefrom_np(&actions.value, 3));
  sigset_t empty, defaults;
  sigemptyset(&empty);
  sigfillset(&defaults);
  checked(posix_spawnattr_setsigmask(&attributes.value, &empty));
  checked(posix_spawnattr_setsigdefault(&attributes.value, &defaults));
  checked(posix_spawnattr_setpgroup(&attributes.value, 0));
  checked(posix_spawnattr_setflags(
      &attributes.value,
      POSIX_SPAWN_SETPGROUP | POSIX_SPAWN_SETSIGMASK | POSIX_SPAWN_SETSIGDEF));
  auto job = std::make_unique<Job>();
  pid_t pid = -1;
  checked(posix_spawnp(&pid, args.front(), &actions.value, &attributes.value,
                       args.data(), vars.data()));
  job->pid = pid;
  job->output.value = output.release();
  job->error.value = error.release();
  job->identity.value = static_cast<int>(syscall(SYS_pidfd_open, pid, 0));
  if (job->identity.value < 0)
    throw std::system_error(errno, std::generic_category());
  const auto id = ++sequence;
  job->callback = std::move(callback);
  jobs.emplace(id, std::move(job));
  try {
    const auto &added = jobs.at(id);
    loop.addFd(added->output.value, EPOLLIN,
               [this, id](auto) { read(id, false); });
    loop.addFd(added->error.value, EPOLLIN,
               [this, id](auto) { read(id, true); });
    loop.addFd(added->identity.value, EPOLLIN,
               [this, id](auto) { finish(id); });
    added->deadline =
        loop.addTimer(timeout, [this, id] { stop(id, Reason::TimedOut); });
  } catch (...) {
    const auto &failed = jobs.at(id);
    loop.removeFd(failed->output.value);
    loop.removeFd(failed->error.value);
    loop.removeFd(failed->identity.value);
    jobs.erase(id);
    throw;
  }
  return id;
}
void Processes::read(Id id, bool error) {
  auto found = jobs.find(id);
  if (found == jobs.end())
    return;
  auto &job = *found->second;
  auto &fd = error ? job.error : job.output;
  auto &text = error ? job.err : job.out;
  if (fd.value < 0)
    return;
  std::array<char, 8192> bytes;
  // Bound each dispatch as well as retained bytes, preventing a chatty child
  // from starving the D-Bus cancellation handler.
  for (int reads = 0; reads < 16; ++reads) {
    auto size = ::read(fd.value, bytes.data(), bytes.size());
    if (size > 0) {
      if (job.out.size() + job.err.size() + static_cast<std::size_t>(size) >
          limit) {
        stop(id, Reason::OutputLimit);
        loop.removeFd(fd.value);
        ::close(fd.release());
        return;
      }
      text.append(bytes.data(), size);
    } else if (size == 0 || (size < 0 && errno != EINTR && errno != EAGAIN &&
                             errno != EWOULDBLOCK)) {
      loop.removeFd(fd.value);
      ::close(fd.release());
      return;
    } else if (size < 0 && errno != EINTR)
      return;
  }
}
void Processes::stop(Id id, Reason reason) {
  auto found = jobs.find(id);
  if (found == jobs.end() || found->second->reason != Reason::Exited)
    return;
  auto &job = *found->second;
  job.reason = reason;
  killGroup(job.pid, SIGTERM);
  job.escalation = loop.addTimer(std::chrono::milliseconds(500), [this, id] {
    auto found = jobs.find(id);
    if (found != jobs.end())
      killGroup(found->second->pid, SIGKILL);
  });
}
void Processes::cancel(Id id) {
  (void)loop.nativeHandle();
  stop(id, Reason::Cancelled);
}
void Processes::finish(Id id) {
  auto found = jobs.find(id);
  if (found == jobs.end())
    return;
  // pidfd readiness denotes exit while the zombie still pins the process id.
  // Kill remaining group members before reaping releases that identity.
  killGroup(found->second->pid, SIGKILL);
  int status = 0;
  pid_t result;
  do {
    result = waitpid(found->second->pid, &status, WNOHANG);
  } while (result < 0 && errno == EINTR);
  if (result == 0)
    return;
  if (result < 0)
    throw std::system_error(errno, std::generic_category());
  found->second->pid = -1;
  read(id, false);
  read(id, true);
  auto job = std::move(found->second);
  jobs.erase(found);
  loop.removeFd(job->identity.value);
  if (job->output.value >= 0)
    loop.removeFd(job->output.value);
  if (job->error.value >= 0)
    loop.removeFd(job->error.value);
  loop.removeTimer(job->deadline);
  loop.removeTimer(job->escalation);
  Result answer{job->reason, status, std::move(job->out), std::move(job->err)};
  auto callback = std::move(job->callback);
  job.reset();
  callback(std::move(answer));
}
} // namespace hics::portal
