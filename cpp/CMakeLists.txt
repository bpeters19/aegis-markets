cmake_minimum_required(VERSION 3.24)
project(aegis_cpp VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Strict warnings, treated as errors, on both compilers.
function(aegis_strict_warnings target)
    if(MSVC)
        target_compile_options(${target} PRIVATE /W4 /WX /permissive-)
    else()
        target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
    endif()
endfunction()

add_library(aegis_core src/price.cpp)
target_include_directories(aegis_core PUBLIC include)
aegis_strict_warnings(aegis_core)

# Tests: GoogleTest, downloaded at a pinned version.
include(FetchContent)
FetchContent_Declare(
    googletest
    URL https://github.com/google/googletest/archive/refs/tags/v1.15.2.zip
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

enable_testing()
add_executable(aegis_tests tests/test_price.cpp)
target_link_libraries(aegis_tests PRIVATE aegis_core GTest::gtest_main)
aegis_strict_warnings(aegis_tests)
include(GoogleTest)
gtest_discover_tests(aegis_tests)
