// Disposable-VM debugger helper only. No Qt, timer, purge or production preload.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <string.h>
#include <unistd.h>

struct output { int fd; size_t remaining; int failed; };
static void write_stats(void *opaque, const char *text) {
    struct output *out = opaque;
    size_t count = strlen(text);
    if (count > out->remaining) { out->failed = 1; return; }
    while (count && !out->failed) {
        ssize_t done = write(out->fd, text, count);
        if (done < 0 && errno == EINTR) continue;
        if (done <= 0) { out->failed = 1; break; }
        text += done;
        count -= done;
        out->remaining -= done;
    }
}
int hics_snapshot_jemalloc(const char *path) {
    typedef void (*stats_fn)(void (*)(void *, const char *), void *, const char *);
    stats_fn stats = (stats_fn)dlsym(RTLD_DEFAULT, "malloc_stats_print");
    if (!stats) return 2;
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0) return 3;
    struct output out = {fd, 65536, 0};
    stats(write_stats, &out, "Jmdablxe");
    int failed = out.failed;
    if (close(fd)) failed = 1;
    return failed ? 4 : 0;
}

// Requires opt.prof=true at startup. Caller supplies a fresh path inside its
// private VM diagnostic directory; never enabled by the production shell.
int hics_dump_jemalloc_profile(const char *path) {
    typedef int (*control_fn)(const char *, void *, size_t *, void *, size_t);
    control_fn control = (control_fn)dlsym(RTLD_DEFAULT, "mallctl");
    if (!control) return 2;
    return control("prof.dump", NULL, NULL, &path, sizeof(path));
}
