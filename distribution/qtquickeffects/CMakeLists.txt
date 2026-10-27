# Build only audited QuickEffects, reusing the matching private Qt Qml/Quick ABI.
# System Qt and every other declarative module remain untouched.
cmake_minimum_required(VERSION 3.27)
if(NOT EXISTS "${HICS_QT_DECLARATIVE_SOURCE}/src/effects/CMakeLists.txt")
    message(FATAL_ERROR "HICS_QT_DECLARATIVE_SOURCE must name the verified patched source")
endif()
include("${HICS_QT_DECLARATIVE_SOURCE}/.cmake.conf")
project(QtQuickEffectsOverlay VERSION 6.12.0 LANGUAGES CXX C)
find_package(Qt6 6.12.0 EXACT CONFIG REQUIRED COMPONENTS BuildInternals)
qt_internal_project_setup()
find_package(Qt6 6.12.0 EXACT CONFIG REQUIRED COMPONENTS Core Gui Qml Quick ShaderTools)
qt_build_repo_begin()
add_subdirectory("${HICS_QT_DECLARATIVE_SOURCE}/src/effects" effects)
qt_build_repo_end()
