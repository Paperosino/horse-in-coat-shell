// Diagnostic: isolate default client modules from ScreenCast/stream ownership.
#include <pipewire/pipewire.h>
#include <stdio.h>
#include <stdlib.h>
#ifdef HICS_TEST_RESIDENT_DBUS
#include <dbus/dbus.h>
#endif
int main(int argc, char **argv) {
    if (argc!=2) return 2;
    char *end=NULL;
    const long count=strtol(argv[1],&end,10);
    if (end==argv[1] || *end || count<1 || count>100) return 3;
#ifdef HICS_TEST_RESIDENT_DBUS
    // Model an application already using DBus, without preload/suppression.
    if (!dbus_threads_init_default()) return 13;
#endif
    pw_init(&argc,&argv);
    for (long i=0;i<count;++i) {
        struct pw_main_loop *loop=pw_main_loop_new(NULL);
        if (!loop) {pw_deinit();return 4;}
        struct pw_context *context=pw_context_new(pw_main_loop_get_loop(loop),NULL,0);
        if (!context) {pw_main_loop_destroy(loop);pw_deinit();return 5;}
        pw_context_destroy(context);
        pw_main_loop_destroy(loop);
    }
    pw_deinit();
    printf("PIPEWIRE_CONTEXT_COMPLETE %ld\n",count);fflush(stdout);
    return 0;
}
