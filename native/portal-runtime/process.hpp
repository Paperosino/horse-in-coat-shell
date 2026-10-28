#pragma once
#include "eventloop.hpp"
#include <map>
#include <string>
#include <vector>

namespace hics::portal {
// Owner-thread process supervisor. Loop must outlive this object. No shell;
// completion runs only after the direct child has been reaped and watches
// removed.
class Processes final {
public:
  using Id = std::uint64_t;
  enum class Reason { Exited, Cancelled, TimedOut, OutputLimit };
  struct Result {
    Reason reason;
    int status;
    std::string out, err;
  };
  using Callback = std::function<void(Result)>;
  explicit Processes(EventLoop &loop);
  ~Processes();
  Processes(const Processes &) = delete;
  Processes &operator=(const Processes &) = delete;
  Id start(const std::vector<std::string> &argv,
           const std::map<std::string, std::string> &environment,
           std::chrono::milliseconds timeout, Callback callback);
  void cancel(Id id);

private:
  struct Job;
  EventLoop &loop;
  Id sequence = 0;
  std::map<Id, std::unique_ptr<Job>> jobs;
  void read(Id id, bool error);
  void finish(Id id);
  void stop(Id id, Reason reason);
};
} // namespace hics::portal
