#include "process.hpp"
#include <cassert>
#include <csignal>
#include <cstring>
#include <dirent.h>
#include <fcntl.h>
#include <iostream>
#include <sys/wait.h>
#include <unistd.h>
using namespace hics::portal;
using namespace std::chrono_literals;
int main(int argc, char **argv) {
  assert(argc == 2);
  std::string mode = argv[1];
  if (mode == "child-echo") {
    std::cout << getenv("HICS_PROBE") << '\n';
    std::cerr << "error";
    return 7;
  }
  if (mode == "child-slow") {
    signal(SIGTERM, SIG_IGN);
    for (;;)
      pause();
  }
  if (mode == "child-flood") {
    char data[8192];
    memset(data, 'x', sizeof(data));
    for (;;)
      if (write(1, data, sizeof(data)) < 0)
        return 0;
  }
  if (mode == "child-fds") {
    // Ignore the directory descriptor opened for this inspection.
    auto *dir = opendir("/proc/self/fd");
    assert(dir);
    int own = dirfd(dir);
    while (auto *entry = readdir(dir)) {
      int fd = atoi(entry->d_name);
      if (fd > 2 && fd != own)
        return 9;
    }
    closedir(dir);
    return 0;
  }
  if (mode == "child-descendant") {
    if (fork() == 0) {
      for (;;)
        pause();
    }
    return 0;
  }
  if (mode == "cleanup") {
    auto count = [] {
      int total = 0;
      auto *directory = opendir("/proc/self/fd");
      assert(directory);
      while (readdir(directory))
        ++total;
      closedir(directory);
      return total;
    };
    const int before = count();
    for (int i = 0; i < 100; ++i) {
      EventLoop loop;
      Processes owner(loop);
      owner.start({"/proc/self/exe", "child-slow"}, {}, 1s,
                  [](auto) { assert(false); });
    }
    assert(count() == before);
    int status;
    assert(waitpid(-1, &status, WNOHANG) == -1 && errno == ECHILD);
    std::cout << "PASS " << mode << '\n';
    return 0;
  }
  EventLoop loop;
  auto guard = loop.addTimer(5s, [&] {
    std::cerr << "deadline\n";
    loop.exit(99);
  });
  std::unique_ptr<Processes> processes = std::make_unique<Processes>(loop);
  auto child = [&](const std::string &name) {
    return std::vector<std::string>{"/proc/self/exe", name};
  };
  int savedInput = -1;
  if (mode == "closed-stdin") {
    savedInput = fcntl(STDIN_FILENO, F_DUPFD_CLOEXEC, 64);
    assert(savedInput >= 0);
    close(STDIN_FILENO);
  }
  int completions = 0;
  auto done = [&](Processes::Result result) {
    if (mode == "echo") {
      assert(result.reason == Processes::Reason::Exited);
      assert(WIFEXITED(result.status) && WEXITSTATUS(result.status) == 7);
      assert(result.out == "literal ; $(no shell)\n" && result.err == "error");
    }
    if (mode == "timeout")
      assert(result.reason == Processes::Reason::TimedOut &&
             WIFSIGNALED(result.status));
    if (mode == "cancel")
      assert(result.reason == Processes::Reason::Cancelled &&
             WIFSIGNALED(result.status));
    if (mode == "flood")
      assert(result.reason == Processes::Reason::OutputLimit &&
             result.out.size() + result.err.size() <= 1024 * 1024);
    if (mode == "fds" || mode == "descendant" || mode == "closed-stdin")
      assert(WIFEXITED(result.status) && WEXITSTATUS(result.status) == 0);
    ++completions;
    if (mode == "delete")
      processes.reset();
    loop.exit();
  };
  if (mode == "shutdown") {
    auto captured = std::make_shared<int>(1);
    std::weak_ptr<int> weak = captured;
    processes->start(child("child-slow"), {}, 1s,
                     [captured](auto) { assert(false); });
    captured.reset();
    assert(!weak.expired());
    processes->shutdown();
    assert(weak.expired());
    processes->shutdown();
    bool rejected = false;
    try {
      processes->start(child("child-slow"), {}, 1s, done);
    } catch (const std::logic_error &) {
      rejected = true;
    }
    assert(rejected);
    loop.exit();
  } else if (mode == "capacity") {
    std::vector<Processes::Id> ids;
    for (int i = 0; i < 8; ++i)
      ids.push_back(
          processes->start(child("child-slow"), {}, 3s, [&](auto answer) {
            assert(answer.reason == Processes::Reason::Cancelled);
            if (++completions == 8)
              loop.exit();
          }));
    bool limited = false;
    try {
      processes->start(child("child-slow"), {}, 1s, done);
    } catch (const std::runtime_error &) {
      limited = true;
    }
    assert(limited);
    for (auto id : ids)
      processes->cancel(id);
  } else if (mode == "failed") {
    bool failed = false;
    try {
      processes->start({"/hics-nonexistent-picker"}, {}, 1s, done);
    } catch (const std::system_error &) {
      failed = true;
    }
    assert(failed);
    loop.exit();
  } else if (mode == "destroy") {
    processes->start(child("child-slow"), {}, 1s, done);
    processes.reset();
    loop.exit();
  } else {
    std::string kind = mode == "echo"                              ? "echo"
                       : mode == "flood"                           ? "flood"
                       : (mode == "fds" || mode == "closed-stdin") ? "fds"
                       : mode == "descendant" ? "descendant"
                                              : "slow";
    auto id = processes->start(child("child-" + kind),
                               {{"HICS_PROBE", "literal ; $(no shell)"}},
                               mode == "timeout" ? 100ms : 3s, done);
    if (mode == "cancel" || mode == "delete")
      loop.addTimer(100ms, [&, id] {
        processes->cancel(id);
        processes->cancel(id);
      });
  }
  assert(loop.run() == 0);
  if (savedInput >= 0) {
    assert(dup2(savedInput, STDIN_FILENO) == STDIN_FILENO);
    close(savedInput);
  }
  loop.removeTimer(guard);
  processes.reset();
  assert(completions ==
         (mode == "capacity"                                              ? 8
          : (mode == "failed" || mode == "destroy" || mode == "shutdown") ? 0
                                                                          : 1));
  int status;
  assert(waitpid(-1, &status, WNOHANG) == -1 && errno == ECHILD);
  std::cout << "PASS " << mode << '\n';
}
