# CMAKE_PROJECT_quickshell_INCLUDE runs before upstream creates its executable.
# Defer attaching the process-local policy until that target exists.
function(hics_configure_allocator_policy)
    if(USE_JEMALLOC)
        if(NOT TARGET quickshell)
            message(FATAL_ERROR "The audited Quickshell allocator target is missing")
        endif()
        target_sources(quickshell PRIVATE "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/policy.cpp")
        target_link_options(quickshell PRIVATE "-Wl,--export-dynamic-symbol=malloc_conf")
    endif()
endfunction()
cmake_language(DEFER CALL hics_configure_allocator_policy)
