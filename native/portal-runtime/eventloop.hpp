#pragma once

#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>

struct sd_event;

namespace hics::portal {
// Single-owner loop for the portal backend. No polling thread, periodic tick or
// callback under a container iterator. A callback may remove its own watch.
// Fds remain owned by the caller. Construction, use and destruction belong
// to one thread; external users of nativeHandle() must obey the same contract.
class EventLoop final {
public:
    using Timer = std::uint64_t;
    EventLoop();
    ~EventLoop();
    EventLoop(const EventLoop &) = delete;
    EventLoop &operator=(const EventLoop &) = delete;

    void addFd(int fd, std::uint32_t events, std::function<void(std::uint32_t)> callback);
    void removeFd(int fd);
    Timer addTimer(std::chrono::microseconds delay, std::function<void()> callback);
    void removeTimer(Timer timer);
    int run();
    int runOnce(std::chrono::microseconds timeout);
    void exit(int code = 0);
    sd_event *nativeHandle() const;

private:
    struct Impl;
    std::unique_ptr<Impl> m_impl;
};
}
