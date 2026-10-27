// Diagnostic only: distinguish owned configurations from Fontconfig's global
// configuration. Never call FcFini while Qt/font consumers are still alive.
#include <fontconfig/fontconfig.h>
#include <cstring>
#include <cstdio>

int main(int argc, char **argv) {
    if (argc != 2 || (std::strcmp(argv[1], "owned") &&
                      std::strcmp(argv[1], "global") &&
                      std::strcmp(argv[1], "finalized")))
        return 2;
    constexpr auto xml = R"(<?xml version="1.0"?>
<fontconfig><selectfont><rejectfont>
<pattern><patelt name="fontwrapper"><string>woff</string></patelt></pattern>
<pattern><patelt name="fontwrapper"><string>woff2</string></patelt></pattern>
</rejectfont></selectfont></fontconfig>)";
    for (int i = 0; i < 100; ++i) {
        auto *config = FcConfigCreate();
        if (!config)
            return 3;
        if (!FcConfigParseAndLoadFromMemory(config,
                reinterpret_cast<const FcChar8 *>(xml), FcTrue)) {
            FcConfigDestroy(config);
            return 4;
        }
        if (std::strcmp(argv[1], "owned") && !FcConfigSetCurrent(config)) {
            FcConfigDestroy(config);
            return 5;
        }
        FcConfigDestroy(config);
    }
    if (!std::strcmp(argv[1], "finalized"))
        FcFini();
    std::puts("FONTCONFIG_FILTER_COMPLETE");
}
