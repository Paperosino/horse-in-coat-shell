# Private quickshell + Qt runtime for binary packages (HICS_BUNDLE_RUNTIME).
# Builds the pinned quickshell tag against the system Qt, then install(CODE)
# assembles a self-contained runtime under ${DATADIR}/hics/qs.

include(ExternalProject)
find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)
option(HICS_PATCH_QT_RUNTIME "Apply audited source fixes to the private Qt runtime" ON)
set(HICS_QT_RUNTIME_JOBS 2 CACHE STRING "Parallel jobs for the private Qt build")
set(HICS_QT_PATCH_OVERLAY "")
if(HICS_PATCH_QT_RUNTIME)
    if(NOT Qt6_VERSION VERSION_EQUAL "6.12.0")
        message(FATAL_ERROR "The patched binary runtime requires audited Qt 6.12.0. HICS_PATCH_QT_RUNTIME=OFF is for development with other Qt versions, not a patched release.")
    endif()
    find_package(Qt6 6.12.0 EXACT REQUIRED COMPONENTS WaylandClient Multimedia)
    set(qt_patch_inputs
        "${CMAKE_CURRENT_SOURCE_DIR}/distribution/build_qt_runtime_patches.py"
        "${CMAKE_CURRENT_SOURCE_DIR}/distribution/patches/qtbase-6.12.0-portal-registration.patch"
        "${CMAKE_CURRENT_SOURCE_DIR}/distribution/patches/qtbase-6.12.0-text-input-focus.patch"
        "${CMAKE_CURRENT_SOURCE_DIR}/distribution/patches/qtmultimedia-6.12.0-lazy-hw-diagnostics.patch")
    set(qt_patch_signature "${Qt6_VERSION}")
    foreach(input IN LISTS qt_patch_inputs)
        file(SHA256 "${input}" input_sha)
        string(APPEND qt_patch_signature "${input_sha}")
    endforeach()
    foreach(module Core Gui WaylandClient Multimedia)
        get_target_property(qt_module_library Qt6::${module} IMPORTED_LOCATION_RELEASE)
        if(NOT EXISTS "${qt_module_library}")
            get_target_property(qt_module_library Qt6::${module} IMPORTED_LOCATION)
        endif()
        file(SHA256 "${qt_module_library}" qt_module_sha)
        string(APPEND qt_patch_signature "${qt_module_sha}")
    endforeach()
    string(SHA256 qt_patch_hash "${qt_patch_signature}")
    string(SUBSTRING "${qt_patch_hash}" 0 16 qt_patch_id)
    set(qt_patch_work "${CMAKE_BINARY_DIR}/runtime/qt-patches-${qt_patch_id}")
    set(HICS_QT_PATCH_OVERLAY "${qt_patch_work}/overlay")
    add_custom_command(OUTPUT "${HICS_QT_PATCH_OVERLAY}/hics-qt-patches.json"
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/distribution/build_qt_runtime_patches.py"
            --work "${qt_patch_work}" --stage "${HICS_QT_PATCH_OVERLAY}" --jobs "${HICS_QT_RUNTIME_JOBS}"
        DEPENDS ${qt_patch_inputs}
        COMMENT "Building audited private Qt runtime fixes"
        VERBATIM)
    add_custom_target(hics-qt-runtime-patches DEPENDS "${HICS_QT_PATCH_OVERLAY}/hics-qt-patches.json")
endif()

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
message(STATUS "Bundling quickshell ${HICS_QUICKSHELL_TAG} runtime")
message(STATUS "  Qt plugins: ${HYPRSTACK_QT_PLUGINS}")
message(STATUS "  Qt qml:     ${HYPRSTACK_QT_QML}")
message(STATUS "  Qt libs:    ${HYPRSTACK_QT_LIBS}")

# Extra prefix for header-only build dependencies of quickshell (CLI11,
# Vulkan-Headers) when they are installed into a user prefix instead of /usr.
if(DEFINED HYPRSTACK_BUNDLE_PREFIX_PATH AND NOT DEFINED HICS_BUNDLE_PREFIX_PATH)
    set(HICS_BUNDLE_PREFIX_PATH "${HYPRSTACK_BUNDLE_PREFIX_PATH}" CACHE PATH "Private runtime dependency prefix")
endif()
set(HICS_BUNDLE_PREFIX_PATH "$ENV{HOME}/.local"
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
    URL "https://github.com/quickshell-mirror/quickshell/archive/refs/tags/${HICS_QUICKSHELL_TAG}.tar.gz"
    URL_HASH "SHA256=946a27e2a276917a03c1079e5c60971af84ece73088c3661dee455d92eb420f7"
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
    CMAKE_GENERATOR Ninja
    CMAKE_ARGS
        "-DCMAKE_BUILD_TYPE=Release"
        "-DCMAKE_INSTALL_PREFIX=${HYPRSTACK_QS_STAGE}"
        "-DCMAKE_PREFIX_PATH=${HICS_BUNDLE_PREFIX_PATH}"
        "-DDISTRIBUTOR=hics bundle"
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
if(HICS_PATCH_QT_RUNTIME)
    # Avoid multiplying nested compiler pools and finish the immutable overlay
    # before assembling the executable's private runtime.
    add_dependencies(quickshell-runtime hics-qt-runtime-patches)
endif()

# Staged quickshell tree (bin/quickshell, bin/qs symlink, share/) plus the
# assembled private Qt runtime, DESTDIR-safe via $ENV{DESTDIR} at install time.
install(DIRECTORY "${HYPRSTACK_QS_STAGE}/"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/hics/qs"
    USE_SOURCE_PERMISSIONS)

install(CODE "
    set(bundle_root \"\$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/${CMAKE_INSTALL_DATADIR}/hics/qs\")
    message(STATUS \"Assembling private Qt runtime in \${bundle_root}\")
    execute_process(
        COMMAND bash \"${CMAKE_CURRENT_SOURCE_DIR}/distribution/bundle-qt.sh\"
            \"\${bundle_root}/bin/quickshell\"
            \"\${bundle_root}\"
            \"${HYPRSTACK_QT_PLUGINS}\"
            \"${HYPRSTACK_QT_QML}\"
            \"${HYPRSTACK_QT_LIBS}\"
            \"${HYPRSTACK_QS_SOURCE}\"
            \"${HICS_QT_PATCH_OVERLAY}\"
        RESULT_VARIABLE bundle_result
        OUTPUT_VARIABLE bundle_output
        ERROR_VARIABLE bundle_error)
    message(STATUS \"\${bundle_output}\")
    if(NOT bundle_result EQUAL 0)
        message(STATUS \"\${bundle_error}\")
        message(FATAL_ERROR \"bundle-qt.sh failed (\${bundle_result})\")
    endif()
")
