if(HICS_AUDIO_VISUALIZER)
    set(audio_sources beattracker.cpp audiocollector.cpp audioprovider.cpp cavaprovider.cpp)
    set(audio_libraries PkgConfig::Pipewire PkgConfig::Aubio PkgConfig::Cava)
else()
    set(audio_sources audiostubs.cpp)
endif()

qml_module(hyprstack-services
    URI Hyprstack.Services
    SOURCES
        runtimeperformance.cpp
        applicationcatalogue.cpp
        workspacetools.cpp
        workspacestore.cpp
        vpnsecretagent.cpp
        networkmanagervpn.cpp
        wallpaperplayer.cpp
        desktopintegration.cpp
        notificationpolicy.cpp
        service.cpp
        serviceref.cpp
        ${audio_sources}
        tickingservice.cpp
        sensorslib.cpp
        cpu.cpp
        gpu.cpp
        memory.cpp
        diskinfo.cpp
        storage.cpp
        lyriccandidate.cpp
        lyrics.cpp
        sessionmanager.cpp
        networkusage.cpp
        hyprdevices.cpp
        hyprextras.cpp
    LIBRARIES
        PkgConfig::Secret
        PkgConfig::NetworkManager
        Qt::Concurrent
        Qt::DBus
        Qt::Network
        Qt::Multimedia
        ${audio_libraries}
        Sensors::Sensors
        hyprstack-util
        hyprstack-core
        hyprstack-config
    DEPENDENCIES
        Hyprstack
        Hyprstack.Config
)

qt_add_resources(hyprstack-services vpn_protocol_catalogue PREFIX "/hics/vpn" FILES vpn-protocols.json)
# This adapter interleaves libnm's UTF-8 property names with Qt map keys.
set_source_files_properties(networkmanagervpn.cpp vpnsecretagent.cpp PROPERTIES
    SKIP_PRECOMPILE_HEADERS ON
    COMPILE_OPTIONS "-UQT_NO_CAST_FROM_ASCII;-UQT_NO_CAST_TO_ASCII")

set_source_files_properties(workspacetools.cpp workspacestore.cpp workspacecli.cpp PROPERTIES
    SKIP_PRECOMPILE_HEADERS ON
    COMPILE_OPTIONS "-UQT_NO_CAST_FROM_ASCII;-UQT_NO_CAST_TO_ASCII;-UQT_NO_CAST_FROM_BYTEARRAY")
add_executable(hics-workspace workspacecli.cpp workspacetools.cpp workspacetools.hpp workspacestore.cpp)
set_target_properties(hics-workspace PROPERTIES AUTOMOC ON INSTALL_RPATH "$ORIGIN/../share/hics/qs/lib" INSTALL_RPATH_USE_LINK_PATH ON)
target_include_directories(hics-workspace PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/../../../include")
target_link_libraries(hics-workspace PRIVATE PkgConfig::NetworkManager Qt::Core Qt::Gui Qt::Qml Qt::Concurrent Qt::DBus)
install(TARGETS hics-workspace RUNTIME DESTINATION bin)

set_source_files_properties(applicationcatalogue.cpp PROPERTIES SKIP_PRECOMPILE_HEADERS ON COMPILE_OPTIONS "-UQT_NO_CAST_FROM_ASCII;-UQT_NO_CAST_TO_ASCII;-UQT_NO_CAST_FROM_BYTEARRAY")

set_source_files_properties(runtimeperformance.cpp PROPERTIES SKIP_PRECOMPILE_HEADERS ON COMPILE_OPTIONS "-UQT_NO_CAST_FROM_ASCII;-UQT_NO_CAST_TO_ASCII;-UQT_NO_CAST_FROM_BYTEARRAY")
