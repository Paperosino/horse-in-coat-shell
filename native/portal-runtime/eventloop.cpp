#include "eventloop.hpp"

#include <systemd/sd-event.h>
#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <limits>
#include <map>
#include <stdexcept>
#include <system_error>
#include <thread>
#include <utility>

namespace hics::portal {
namespace {
void check(int result) {
    if (result < 0) throw std::system_error(-result, std::generic_category());
}
struct EventRef {
    explicit EventRef(sd_event *value) : event(sd_event_ref(value)) {}
    ~EventRef() { sd_event_unref(event); }
    sd_event *event;
};
// Exceptions cannot cross the C dispatch frame. The event reference also makes
// destruction of the owning C++ loop inside a callback safe.
template<typename F> int dispatch(sd_event_source *source, F &&callback) noexcept {
    EventRef event(sd_event_source_get_event(source));
    try {
        std::forward<F>(callback)();
    } catch (const std::exception &error) {
        std::fprintf(stderr, "hics portal event callback failed: %s\n", error.what());
        sd_event_exit(event.event, 1);
    } catch (...) {
        std::fputs("hics portal event callback failed\n", stderr);
        sd_event_exit(event.event, 1);
    }
    return 0;
}
}

struct EventLoop::Impl {
    struct Watch {
        sd_event_source *source = nullptr;
        Impl *owner = nullptr;
        Timer timer = 0;
        std::function<void(std::uint32_t)> io;
        std::function<void()> timeout;
        ~Watch() { sd_event_source_unref(source); }
    };
    sd_event *event = nullptr;
    const std::thread::id thread = std::this_thread::get_id();
    Timer sequence = 0;
    std::map<int, std::unique_ptr<Watch>> fds;
    std::map<Timer, std::unique_ptr<Watch>> timers;

    Impl() { check(sd_event_new(&event)); }
    ~Impl() {
        sd_event_exit(event, 0);
        timers.clear();
        fds.clear();
        sd_event_unref(event);
    }
    void requireOwner() const {
        if (std::this_thread::get_id() != thread)
            throw std::logic_error("Portal event loop must be used on its owner thread");
    }
    static int onIo(sd_event_source *source, int, std::uint32_t events, void *data) noexcept {
        return dispatch(source, [data, events] {
            // The original Watch may be destroyed or replaced by this callback.
            const auto callback = static_cast<Watch *>(data)->io;
            callback(events);
        });
    }
    static int onTimer(sd_event_source *source, std::uint64_t, void *data) noexcept {
        return dispatch(source, [data] {
            auto *watch = static_cast<Watch *>(data);
            const auto callback = watch->timeout;
            const auto timer = watch->timer;
            auto *owner = watch->owner;
            owner->timers.erase(timer);
            callback();
        });
    }
};

EventLoop::EventLoop() : m_impl(std::make_unique<Impl>()) {}
EventLoop::~EventLoop() = default;

void EventLoop::addFd(int fd, std::uint32_t events, std::function<void(std::uint32_t)> callback) {
    m_impl->requireOwner();
    if (fd < 0 || !callback) throw std::invalid_argument("Invalid portal fd watch");
    if (const auto existing = m_impl->fds.find(fd); existing != m_impl->fds.end()) {
        check(sd_event_source_set_io_events(existing->second->source, events));
        existing->second->io = std::move(callback);
        return;
    }
    auto watch = std::make_unique<Impl::Watch>();
    watch->owner = m_impl.get();
    watch->io = std::move(callback);
    check(sd_event_add_io(m_impl->event, &watch->source, fd, events, &Impl::onIo, watch.get()));
    m_impl->fds.emplace(fd, std::move(watch));
}
void EventLoop::removeFd(int fd) {
    m_impl->requireOwner();
    m_impl->fds.erase(fd);
}
EventLoop::Timer EventLoop::addTimer(std::chrono::microseconds delay, std::function<void()> callback) {
    m_impl->requireOwner();
    if (!callback) throw std::invalid_argument("Invalid portal timer callback");
    if (m_impl->sequence == std::numeric_limits<Timer>::max()) throw std::overflow_error("Portal timer ids exhausted");
    auto watch = std::make_unique<Impl::Watch>();
    watch->owner = m_impl.get();
    watch->timer = ++m_impl->sequence;
    watch->timeout = std::move(callback);
    const auto usec = static_cast<std::uint64_t>(std::max<std::int64_t>(0, delay.count()));
    check(sd_event_add_time_relative(m_impl->event, &watch->source, CLOCK_MONOTONIC, usec, 1, &Impl::onTimer, watch.get()));
    const auto timer = watch->timer;
    m_impl->timers.emplace(timer, std::move(watch));
    return timer;
}
void EventLoop::removeTimer(Timer timer) {
    m_impl->requireOwner();
    m_impl->timers.erase(timer);
}
int EventLoop::run() {
    m_impl->requireOwner();
    EventRef event(m_impl->event);
    const int result = sd_event_loop(event.event);
    check(result);
    return result;
}
int EventLoop::runOnce(std::chrono::microseconds timeout) {
    m_impl->requireOwner();
    EventRef event(m_impl->event);
    const int result = sd_event_run(event.event, static_cast<std::uint64_t>(std::max<std::int64_t>(0, timeout.count())));
    check(result);
    return result;
}
void EventLoop::exit(int code) {
    m_impl->requireOwner();
    check(sd_event_exit(m_impl->event, code));
}
sd_event *EventLoop::nativeHandle() const {
    m_impl->requireOwner();
    return m_impl->event;
}
}
