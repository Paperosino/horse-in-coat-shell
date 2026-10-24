#include "audiocollector.hpp"

#include <qloggingcategory.h>

#include <pipewire/pipewire.h>

#include <algorithm>
#include <stop_token>
#include <utility>
#include <vector>

#include "service.hpp"

namespace {

Q_LOGGING_CATEGORY(lcAcWorker, "hyprstack.services.ac.worker", QtInfoMsg)

} // namespace

namespace hyprstack::services {

PipeWireWorker::PipeWireWorker(std::stop_token token, AudioCollector* collector)
    : m_loop(nullptr)
    , m_stream(nullptr)
    , m_timer(nullptr)
    , m_idle(true)
    , m_token(std::move(token))
    , m_collector(collector) {
    if (!m_collector || m_token.stop_requested()) return;
    pw_init(nullptr, nullptr);

    m_loop = pw_main_loop_new(nullptr);
    if (!m_loop) {
        qCWarning(lcAcWorker) << "init: failed to create PipeWire main loop";
        pw_deinit();
        return;
    }

    timespec timeout = { .tv_sec = 0, .tv_nsec = 10 * SPA_NSEC_PER_MSEC };
    m_timer = pw_loop_add_timer(pw_main_loop_get_loop(m_loop), handleTimeout, this);
    if (!m_timer) {
        qCWarning(lcAcWorker) << "init: failed to create timer";
        pw_main_loop_destroy(m_loop);
        pw_deinit();
        return;
    }
    pw_loop_update_timer(pw_main_loop_get_loop(m_loop), m_timer, &timeout, &timeout, false);

    auto* props = pw_properties_new(
        PW_KEY_MEDIA_TYPE, "Audio", PW_KEY_MEDIA_CATEGORY, "Capture", PW_KEY_MEDIA_ROLE, "Music", nullptr);
    pw_properties_set(props, PW_KEY_STREAM_CAPTURE_SINK, "true");
    pw_properties_setf(
        props, PW_KEY_NODE_LATENCY, "%u/%u", nextPowerOf2(512 * ac::k_sampleRate / 48000), ac::k_sampleRate);
    pw_properties_set(props, PW_KEY_NODE_PASSIVE, "true");
    pw_properties_set(props, PW_KEY_NODE_VIRTUAL, "true");
    pw_properties_set(props, PW_KEY_STREAM_DONT_REMIX, "false");
    pw_properties_set(props, "channelmix.upmix", "true");

    std::vector<uint8_t> buffer(ac::k_chunkSize);
    spa_pod_builder b;
    spa_pod_builder_init(&b, buffer.data(), static_cast<quint32>(buffer.size()));

    spa_audio_info_raw info{};
    info.format = SPA_AUDIO_FORMAT_S16;
    info.rate = ac::k_sampleRate;
    info.channels = 1;

    const spa_pod* params[1];
    params[0] = spa_format_audio_raw_build(&b, SPA_PARAM_EnumFormat, &info);

    pw_stream_events events{};
    events.version = PW_VERSION_STREAM_EVENTS;
    events.state_changed = [](void* data, pw_stream_state, pw_stream_state state, const char*) {
        auto* self = static_cast<PipeWireWorker*>(data);
        self->streamStateChanged(state);
    };
    events.process = [](void* data) {
        auto* self = static_cast<PipeWireWorker*>(data);
        self->processStream();
    };

    m_stream = pw_stream_new_simple(pw_main_loop_get_loop(m_loop), "hics-shell", props, &events, this);
    if (!m_stream) {
        qCWarning(lcAcWorker) << "init: failed to create stream";
        pw_main_loop_destroy(m_loop);
        pw_deinit();
        return;
    }

    const auto flags = static_cast<pw_stream_flags>(static_cast<quint32>(PW_STREAM_FLAG_AUTOCONNECT) |
                                                    static_cast<quint32>(PW_STREAM_FLAG_MAP_BUFFERS) |
                                                    static_cast<quint32>(PW_STREAM_FLAG_RT_PROCESS));
    const int success = pw_stream_connect(m_stream, PW_DIRECTION_INPUT, PW_ID_ANY, flags, params, 1);
    if (success < 0) {
        qCWarning(lcAcWorker) << "init: failed to connect stream";
        pw_stream_destroy(m_stream);
        pw_main_loop_destroy(m_loop);
        pw_deinit();
        return;
    }

    auto* stopEvent = pw_loop_add_event(pw_main_loop_get_loop(m_loop), [](void* data, uint64_t) {
        pw_main_loop_quit(static_cast<pw_main_loop*>(data));
    }, m_loop);
    if (stopEvent) {
        // Wakes an idle or stalled STREAMING loop immediately. The stop
        // callback is removed (and joined) before its event/loop are destroyed.
        {
            std::stop_callback wake(m_token, [this, stopEvent] {
                pw_loop_signal_event(pw_main_loop_get_loop(m_loop), stopEvent);
            });
            if (!m_token.stop_requested()) pw_main_loop_run(m_loop);
        }
        pw_loop_destroy_source(pw_main_loop_get_loop(m_loop), stopEvent);
    } else {
        qCWarning(lcAcWorker) << "init: failed to create stop event";
    }

    pw_stream_destroy(m_stream);
    pw_main_loop_destroy(m_loop);
    pw_deinit();
}

void PipeWireWorker::handleTimeout(void* data, uint64_t expirations) {
    auto* self = static_cast<PipeWireWorker*>(data);

    if (self->m_token.stop_requested() || !self->m_collector) {
        pw_main_loop_quit(self->m_loop);
        return;
    }

    if (!self->m_idle) {
        if (expirations < 10) {
            self->m_collector->clearBuffer();
        } else {
            self->m_idle = true;
            timespec timeout = { .tv_sec = 0, .tv_nsec = 500 * SPA_NSEC_PER_MSEC };
            pw_loop_update_timer(pw_main_loop_get_loop(self->m_loop), self->m_timer, &timeout, &timeout, false);
        }
    }
}

void PipeWireWorker::streamStateChanged(pw_stream_state state) {
    m_idle = false;
    switch (state) {
    case PW_STREAM_STATE_PAUSED: {
        timespec timeout = { .tv_sec = 0, .tv_nsec = 10 * SPA_NSEC_PER_MSEC };
        pw_loop_update_timer(pw_main_loop_get_loop(m_loop), m_timer, &timeout, &timeout, false);
        break;
    }
    case PW_STREAM_STATE_STREAMING:
        pw_loop_update_timer(pw_main_loop_get_loop(m_loop), m_timer, nullptr, nullptr, false);
        break;
    case PW_STREAM_STATE_ERROR:
        pw_main_loop_quit(m_loop);
        break;
    default:
        break;
    }
}

void PipeWireWorker::processStream() {
    if (m_token.stop_requested() || !m_collector) {
        pw_main_loop_quit(m_loop);
        return;
    }

    pw_buffer* const buffer = pw_stream_dequeue_buffer(m_stream);
    if (buffer == nullptr) {
        return;
    }

    const spa_buffer* buf = buffer->buffer;
    if (buf && buf->n_datas > 0) {
        const auto& data = buf->datas[0];
        if (data.data && data.chunk && data.chunk->offset <= data.maxsize) {
            const auto size = std::min(data.chunk->size, data.maxsize - data.chunk->offset);
            const auto* bytes = static_cast<const uint8_t*>(data.data) + data.chunk->offset;
            // SPA PCM offsets are sample-aligned; reject malformed buffers.
            if (data.chunk->offset % alignof(qint16) == 0)
                m_collector->loadChunk(reinterpret_cast<const qint16*>(bytes), size / sizeof(qint16));
        }
    }

    pw_stream_queue_buffer(m_stream, buffer);
}

unsigned int PipeWireWorker::nextPowerOf2(unsigned int n) {
    if (n == 0) {
        return 1;
    }

    n--;
    n |= n >> 1u;
    n |= n >> 2u;
    n |= n >> 4u;
    n |= n >> 8u;
    n |= n >> 16u;
    n++;

    return n;
}

AudioCollector& AudioCollector::instance() {
    static AudioCollector s_instance;
    return s_instance;
}

void AudioCollector::clearBuffer() {
    std::unique_lock lock(m_bufferMutex, std::try_to_lock);
    if (lock.owns_lock()) m_buffer.fill(0.0f);
}

void AudioCollector::loadChunk(const qint16* samples, quint32 count) {
    // PipeWire's realtime producer never waits for a reader or allocates.
    std::unique_lock lock(m_bufferMutex, std::try_to_lock);
    if (!lock.owns_lock() || !samples) return;
    count = std::min(count, ac::k_chunkSize);
    std::transform(samples, samples + count, m_buffer.begin(), [](qint16 sample) {
        return static_cast<float>(sample) / 32768.0f;
    });
    std::fill(m_buffer.begin() + count, m_buffer.end(), 0.0f);
}

quint32 AudioCollector::readChunk(float* out, quint32 count) {
    if (!out) return 0;
    if (count == 0 || count > ac::k_chunkSize) count = ac::k_chunkSize;
    std::lock_guard lock(m_bufferMutex);
    std::memcpy(out, m_buffer.data(), count * sizeof(float));
    return count;
}

quint32 AudioCollector::readChunk(double* out, quint32 count) {
    if (!out) return 0;
    if (count == 0 || count > ac::k_chunkSize) count = ac::k_chunkSize;
    std::lock_guard lock(m_bufferMutex);
    std::transform(m_buffer.begin(), m_buffer.begin() + count, out, [](float sample) {
        return static_cast<double>(sample);
    });
    return count;
}

AudioCollector::AudioCollector(QObject* parent) : Service(parent) {}

AudioCollector::~AudioCollector() {
    AudioCollector::stop();
}

void AudioCollector::start() {
    if (m_thread.joinable()) {
        return;
    }

    clearBuffer();

    m_thread = std::jthread([this](std::stop_token token) {
        const PipeWireWorker worker(std::move(token), this);
    });
}

void AudioCollector::stop() {
    if (m_thread.joinable()) {
        m_thread.request_stop();
        m_thread.join();
    }
}

} // namespace hyprstack::services
