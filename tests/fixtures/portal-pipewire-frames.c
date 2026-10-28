/* Disposable VM diagnostic: consume only the FD granted by ScreenCast portal.
 * No default PipeWire connection, device access, frame files or RT callback IO.
 */
#include <pipewire/pipewire.h>
#include <spa/param/video/format-utils.h>
#include <sys/stat.h>
#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#ifdef HICS_TEST_RESIDENT_DBUS
#include <dbus/dbus.h>
#endif
#include <string.h>
#include <unistd.h>

struct capture {
    struct pw_main_loop *loop;
    struct pw_stream *stream;
    struct spa_video_info_raw format;
    uint32_t frames, changes;
    uint64_t first_hash, bytes;
    int error;
    bool timeout;
};
static void core_error(void *data, uint32_t id, int seq, int res, const char *message) {
    (void)id; (void)seq; (void)message;
    struct capture *c = data;
    c->error = res;
    pw_main_loop_quit(c->loop);
}
static void state_changed(void *data, enum pw_stream_state old,
                          enum pw_stream_state state, const char *message) {
    (void)old; (void)message;
    struct capture *c = data;
    if (state == PW_STREAM_STATE_ERROR) {
        c->error = -EIO;
        pw_main_loop_quit(c->loop);
    }
}
static void format_changed(void *data, uint32_t id, const struct spa_pod *param) {
    struct capture *c = data;
    if (id != SPA_PARAM_Format || !param) return;
    uint32_t type, subtype;
    if (spa_format_parse(param, &type, &subtype) < 0 || type != SPA_MEDIA_TYPE_video
        || subtype != SPA_MEDIA_SUBTYPE_raw) return;
    if (spa_format_video_raw_parse(param, &c->format) < 0
        || !c->format.size.width || !c->format.size.height
        || c->format.size.width > 4096 || c->format.size.height > 4096) {
        c->error = -EINVAL;
        pw_main_loop_quit(c->loop);
    }
}
static void process(void *data) {
    struct capture *c = data;
    struct pw_buffer *buffer = pw_stream_dequeue_buffer(c->stream);
    if (!buffer) return;
    const struct spa_buffer *spa = buffer->buffer;
    if (spa && spa->n_datas && spa->datas[0].data && spa->datas[0].chunk) {
        const struct spa_data *plane = &spa->datas[0];
        const struct spa_chunk *chunk = plane->chunk;
        if (!(chunk->flags & SPA_CHUNK_FLAG_CORRUPTED) && chunk->size && chunk->offset <= plane->maxsize
            && chunk->size <= plane->maxsize-chunk->offset && chunk->size <= 64u*1024u*1024u
            && c->format.size.width && c->format.size.height) {
            const uint8_t *bytes = (const uint8_t *)plane->data+chunk->offset;
            uint64_t hash = UINT64_C(14695981039346656037);
            const uint32_t samples = chunk->size < 4096 ? chunk->size : 4096;
            for (uint32_t i = 0; i < samples; ++i) {
                hash ^= bytes[(uint64_t)i*chunk->size/samples];
                hash *= UINT64_C(1099511628211);
            }
            if (!c->frames) c->first_hash = hash;
            else if (hash != c->first_hash) ++c->changes;
            ++c->frames;
            c->bytes += chunk->size;
        }
    }
    /* Return every dequeued buffer, including unsupported/empty planes. */
    pw_stream_queue_buffer(c->stream, buffer);
    if (c->frames >= 12 && c->changes) pw_main_loop_quit(c->loop);
}
static void deadline(void *data, uint64_t expirations) {
    (void)expirations;
    struct capture *c = data;
    c->timeout = true;
    pw_main_loop_quit(c->loop);
}
int main(int argc, char **argv) {
    if (argc != 4) return 2;
    char *end = NULL;
    errno = 0;
    long descriptor = strtol(argv[1], &end, 10);
    if (errno || end == argv[1] || *end || descriptor < 3 || descriptor > 65535) return 3;
    struct stat status;
    if (fstat((int)descriptor, &status) || !S_ISSOCK(status.st_mode)) return 4;
    end = NULL;
    errno = 0;
    unsigned long node = strtoul(argv[2], &end, 10);
    if (errno || end == argv[2] || *end || node >= UINT32_MAX) return 5;
    const bool use_serial = strcmp(argv[3], "-") != 0;
    if (use_serial) {
        char *serial_end = NULL;
        errno = 0;
        const unsigned long long serial = strtoull(argv[3], &serial_end, 10);
        if (errno || serial_end == argv[3] || *serial_end || !serial
            || argv[3][0] < '0' || argv[3][0] > '9' || strlen(argv[3]) > 20) return 6;
    }
#ifdef HICS_TEST_RESIDENT_DBUS
    // Explicit application-owned DBus control; not the raw PipeWire baseline.
    if (!dbus_threads_init_default()) return 13;
#endif
    pw_init(&argc, &argv);
    struct capture c = {0};
    c.loop = pw_main_loop_new(NULL);
    if (!c.loop) {pw_deinit();return 7;}
    struct pw_loop *loop = pw_main_loop_get_loop(c.loop);
    struct pw_context *context = pw_context_new(loop, NULL, 0);
    if (!context) {pw_main_loop_destroy(c.loop);pw_deinit();return 8;}
    struct pw_core *core = pw_context_connect_fd(context, (int)descriptor, NULL, 0);
    if (!core) {pw_context_destroy(context);pw_main_loop_destroy(c.loop);pw_deinit();return 9;}
    struct spa_hook core_hook, stream_hook;
    const struct pw_core_events core_events = {.version=PW_VERSION_CORE_EVENTS, .error=core_error};
    pw_core_add_listener(core, &core_hook, &core_events, &c);
    struct pw_properties *props = pw_properties_new(PW_KEY_MEDIA_TYPE, "Video",
        PW_KEY_MEDIA_CATEGORY, "Capture", PW_KEY_MEDIA_ROLE, "Screen", NULL);
    if (use_serial) pw_properties_set(props, PW_KEY_TARGET_OBJECT, argv[3]);
    c.stream = pw_stream_new(core, "HICS portal frame fixture", props);
    if (!c.stream) {
        spa_hook_remove(&core_hook);pw_core_disconnect(core);
        pw_context_destroy(context);pw_main_loop_destroy(c.loop);pw_deinit();return 10;
    }
    const struct pw_stream_events events = {.version=PW_VERSION_STREAM_EVENTS,
        .state_changed=state_changed, .param_changed=format_changed, .process=process};
    pw_stream_add_listener(c.stream, &stream_hook, &events, &c);
    uint8_t storage[1024];
    struct spa_pod_builder builder = SPA_POD_BUILDER_INIT(storage, sizeof(storage));
    struct spa_rectangle preferred = SPA_RECTANGLE(640,360), minimum = SPA_RECTANGLE(1,1), maximum = SPA_RECTANGLE(4096,4096);
    const struct spa_pod *params[] = {spa_pod_builder_add_object(&builder,
        SPA_TYPE_OBJECT_Format, SPA_PARAM_EnumFormat,
        SPA_FORMAT_mediaType, SPA_POD_Id(SPA_MEDIA_TYPE_video),
        SPA_FORMAT_mediaSubtype, SPA_POD_Id(SPA_MEDIA_SUBTYPE_raw),
        SPA_FORMAT_VIDEO_format, SPA_POD_CHOICE_ENUM_Id(5, SPA_VIDEO_FORMAT_BGRx,
            SPA_VIDEO_FORMAT_BGRx, SPA_VIDEO_FORMAT_BGRA, SPA_VIDEO_FORMAT_RGBx, SPA_VIDEO_FORMAT_RGBA),
        SPA_FORMAT_VIDEO_size, SPA_POD_CHOICE_RANGE_Rectangle(&preferred,&minimum,&maximum))};
    struct spa_source *timer = pw_loop_add_timer(loop, deadline, &c);
    if (!timer) {
        spa_hook_remove(&stream_hook);pw_stream_destroy(c.stream);
        spa_hook_remove(&core_hook);pw_core_disconnect(core);
        pw_context_destroy(context);pw_main_loop_destroy(c.loop);pw_deinit();return 11;
    }
    struct timespec limit = {.tv_sec=20};
    pw_loop_update_timer(loop, timer, &limit, NULL, false);
    int result = pw_stream_connect(c.stream, PW_DIRECTION_INPUT, use_serial ? PW_ID_ANY : (uint32_t)node,
        PW_STREAM_FLAG_AUTOCONNECT | PW_STREAM_FLAG_MAP_BUFFERS, params, 1);
    if (result < 0) c.error = result;
    else pw_main_loop_run(c.loop);
    printf("{\"frames\":%u,\"changingFrames\":%u,\"width\":%u,\"height\":%u,"
           "\"format\":%u,\"bytes\":%" PRIu64 ",\"error\":%d,\"timeout\":%s,\"serialTarget\":%s}\n",
        c.frames,c.changes,c.format.size.width,c.format.size.height,c.format.format,c.bytes,
        c.error,c.timeout?"true":"false",use_serial?"true":"false");
    fflush(stdout); // Keep functional evidence even if LSan rejects shutdown.
    const char *maps_path = getenv("HICS_PIPEWIRE_MAPS");
    if (maps_path) {
        FILE *input = fopen("/proc/self/maps", "r"), *output = fopen(maps_path, "wx");
        if (input && output) {
            char block[4096]; size_t remaining = 2u*1024u*1024u;
            while (remaining) {
                const size_t count = fread(block, 1, remaining < sizeof(block) ? remaining : sizeof(block), input);
                if (!count) break;
                fwrite(block, 1, count, output); remaining -= count;
            }
        }
        if (input) fclose(input);
        if (output) fclose(output);
    }
    pw_loop_destroy_source(loop, timer);
    spa_hook_remove(&stream_hook);
    pw_stream_destroy(c.stream);
    spa_hook_remove(&core_hook);
    pw_core_disconnect(core);
    pw_context_destroy(context);
    pw_main_loop_destroy(c.loop);
    pw_deinit();
    return !c.error && !c.timeout && c.frames>=12 && c.changes ? 0 : 1;
}
