cmake_minimum_required(VERSION 3.16)
project(interspec_typed_allocator LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(interspec_runtime INTERFACE)
set_target_properties(interspec_runtime PROPERTIES EXPORT_NAME runtime)
target_include_directories(interspec_runtime INTERFACE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
add_library(interspec::runtime ALIAS interspec_runtime)

include(GNUInstallDirs)
install(TARGETS interspec_runtime EXPORT interspec_runtime_targets)
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT interspec_runtime_targets
  NAMESPACE interspec::
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/interspec-runtime)

enable_testing()
add_executable(core_poc tests/core_poc.cpp)
target_link_libraries(core_poc PRIVATE interspec::runtime)
add_test(NAME core_poc COMMAND core_poc)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(NAME policy_codegen
  COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_policy.py
    --policy ${CMAKE_CURRENT_SOURCE_DIR}/policy/poc_policy.json
    --source ${CMAKE_CURRENT_SOURCE_DIR}/poc/typed_poc_untrusted.c
    --out-dir ${CMAKE_CURRENT_BINARY_DIR}/generated-policy)
