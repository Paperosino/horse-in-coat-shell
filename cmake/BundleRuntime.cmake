# Private quickshell + Qt runtime for binary packages (HYPRSTACK_BUNDLE_RUNTIME).
# Builds the pinned quickshell tag against the system Qt, then install(CODE)
# assembles a self-contained runtime under ${DATADIR}/hyprstack/qs.

include(ExternalProject)

find_program(QMAKE6 qmake6 REQUIRED)
execute_process(COMMAND "${QMAKE6}" -query QT_INSTALL_PLUGINS
    OUTPUT_VARIABLE HYPRSTACK_QT_PLUGINS OUTPUT_STRIP_TRAILING_WHITESPACE)
execute_process(COMMAND "${QMAKE6}" -query QT_INSTALL_QML
    OUTPUT_VARIABLE HYPRSTACK_QT_QML OUTPUT_STRIP_TRAILING_WHITESPACE)
execute_process(COMMAND "${QMAKE6}" -query QT_INSTALL_LIBS
    OUTPUT_VARIABLE HYPRSTACK_QT_LIBS OUTPUT_STRIP_TRAILING_WHITESPACE)

foreach(qt_dir IN ITEMS "${HYPRSTACK_QT_PLUGINS}" "${HYPRSTACK_QT_QML}" "${HYPRSTACK_QT_LIBS}")
    if(NOT IS_DIRECTORY "${qt_dir}")
        message(FATAL_ERROR "Qt directory from qmake6 -query does not exist: ${qt_dir}")
    endif()
endforeach()
message(STATUS "Bundling quickshell ${HYPRSTACK_QUICKSHELL_TAG} runtime")
message(STATUS "  Qt plugins: ${HYPRSTACK_QT_PLUGINS}")
message(STATUS "  Qt qml:     ${HYPRSTACK_QT_QML}")
message(STATUS "  Qt libs:    ${HYPRSTACK_QT_LIBS}")

# Extra prefix for header-only build dependencies of quickshell (CLI11,
# Vulkan-Headers) when they are installed into a user prefix instead of /usr.
set(HYPRSTACK_BUNDLE_PREFIX_PATH "$ENV{HOME}/.local"
    CACHE STRING "Extra CMAKE_PREFIX_PATH for the bundled quickshell build")

set(HYPRSTACK_QS_STAGE "${CMAKE_BINARY_DIR}/runtime/qs")
set(HYPRSTACK_QS_SOURCE "${CMAKE_BINARY_DIR}/runtime/src-quickshell")
set(HYPRSTACK_QS_BINARY "${CMAKE_BINARY_DIR}/runtime/build-quickshell")
set(HYPRSTACK_QS_PREFIX "${CMAKE_BINARY_DIR}/runtime/quickshell-runtime")

ExternalProject_Add(quickshell-runtime
    PREFIX "${HYPRSTACK_QS_PREFIX}"
    SOURCE_DIR "${HYPRSTACK_QS_SOURCE}"
    BINARY_DIR "${HYPRSTACK_QS_BINARY}"
    STAMP_DIR "${HYPRSTACK_QS_PREFIX}/stamp"
    TMP_DIR "${HYPRSTACK_QS_PREFIX}/tmp"
    URL "https://github.com/quickshell-mirror/quickshell/archive/refs/tags/${HYPRSTACK_QUICKSHELL_TAG}.tar.gz"
    URL_HASH "SHA256=946a27e2a276917a03c1079e5c60971af84ece73088c3661dee455d92eb420f7"
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
    CMAKE_GENERATOR Ninja
    CMAKE_ARGS
        "-DCMAKE_BUILD_TYPE=Release"
        "-DCMAKE_INSTALL_PREFIX=${HYPRSTACK_QS_STAGE}"
        "-DCMAKE_PREFIX_PATH=${HYPRSTACK_BUNDLE_PREFIX_PATH}"
        "-DDISTRIBUTOR=Hyprstack bundle"
        "-DUSE_JEMALLOC=OFF"
        "-DCRASH_HANDLER=OFF"
        "-DSOCKETS=ON"
        "-DWAYLAND=ON"
        "-DX11=OFF"
        "-DI3=OFF"
        "-DHYPRLAND=ON"
        "-DSERVICE_PAM=ON"
        "-DSERVICE_POLKIT=ON"
        "-DSERVICE_MPRIS=ON"
        "-DSERVICE_PIPEWIRE=ON"
    BUILD_BYPRODUCTS "${HYPRSTACK_QS_STAGE}/bin/quickshell"
)

# Staged quickshell tree (bin/quickshell, bin/qs symlink, share/) plus the
# assembled private Qt runtime, DESTDIR-safe via $ENV{DESTDIR} at install time.
install(DIRECTORY "${HYPRSTACK_QS_STAGE}/"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/hyprstack/qs"
    USE_SOURCE_PERMISSIONS)

install(CODE "
    set(bundle_root \"\$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/${CMAKE_INSTALL_DATADIR}/hyprstack/qs\")
    message(STATUS \"Assembling private Qt runtime in \${bundle_root}\")
    execute_process(
        COMMAND bash \"${CMAKE_CURRENT_SOURCE_DIR}/distribution/bundle-qt.sh\"
            \"\${bundle_root}/bin/quickshell\"
            \"\${bundle_root}\"
            \"${HYPRSTACK_QT_PLUGINS}\"
            \"${HYPRSTACK_QT_QML}\"
            \"${HYPRSTACK_QT_LIBS}\"
            \"${HYPRSTACK_QS_SOURCE}\"
        RESULT_VARIABLE bundle_result
        OUTPUT_VARIABLE bundle_output
        ERROR_VARIABLE bundle_error)
    message(STATUS \"\${bundle_output}\")
    if(NOT bundle_result EQUAL 0)
        message(STATUS \"\${bundle_error}\")
        message(FATAL_ERROR \"bundle-qt.sh failed (\${bundle_result})\")
    endif()
")
