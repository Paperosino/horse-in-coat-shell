// jemalloc reads this constant before main(), including allocations made by Qt
// static initialization. Do not export MALLOC_CONF to applications launched by
// the shell or periodically force heap purges from the render/event loop.
// https://jemalloc.net/jemalloc.3.html (TUNING and opt.dirty_decay_ms).
extern "C" {
__attribute__((visibility("default"))) const char *malloc_conf =
    "dirty_decay_ms:1000,muzzy_decay_ms:0";
}
