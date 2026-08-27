cmake_minimum_required(VERSION 3.16)
project(interspec_runtime_consumer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(interspec-runtime CONFIG REQUIRED)

add_executable(interspec_runtime_consumer main.cpp)
target_link_libraries(interspec_runtime_consumer PRIVATE interspec::runtime)
