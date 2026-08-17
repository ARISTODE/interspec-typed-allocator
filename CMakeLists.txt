cmake_minimum_required(VERSION 3.16)
project(interspec_typed_allocator LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

enable_testing()
add_executable(core_poc tests/core_poc.cpp)
target_include_directories(core_poc PRIVATE src)
add_test(NAME core_poc COMMAND core_poc)
