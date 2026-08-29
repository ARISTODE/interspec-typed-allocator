cmake_minimum_required(VERSION 3.16)
project(interspec_typed_allocator VERSION 0.1.0 LANGUAGES CXX)

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
include(CMakePackageConfigHelpers)
set(INTERSPEC_CMAKE_INSTALL_DIR ${CMAKE_INSTALL_LIBDIR}/cmake/interspec-runtime)
install(TARGETS interspec_runtime EXPORT interspec_runtime_targets)
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT interspec_runtime_targets NAMESPACE interspec:: DESTINATION ${INTERSPEC_CMAKE_INSTALL_DIR})
configure_package_config_file(${CMAKE_CURRENT_SOURCE_DIR}/cmake/interspec-runtimeConfig.cmake.in
  ${CMAKE_CURRENT_BINARY_DIR}/interspec-runtimeConfig.cmake
  INSTALL_DESTINATION ${INTERSPEC_CMAKE_INSTALL_DIR})
write_basic_package_version_file(${CMAKE_CURRENT_BINARY_DIR}/interspec-runtimeConfigVersion.cmake
  VERSION ${PROJECT_VERSION} COMPATIBILITY SameMajorVersion)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/interspec-runtimeConfig.cmake
  ${CMAKE_CURRENT_BINARY_DIR}/interspec-runtimeConfigVersion.cmake
  DESTINATION ${INTERSPEC_CMAKE_INSTALL_DIR})

enable_testing()
add_executable(core_poc tests/core_poc.cpp)
target_link_libraries(core_poc PRIVATE interspec::runtime)
add_test(NAME core_poc COMMAND core_poc)
find_package(Threads REQUIRED)
add_executable(runtime_hardening tests/runtime_hardening.cpp)
target_link_libraries(runtime_hardening PRIVATE interspec::runtime Threads::Threads)
add_test(NAME runtime_hardening COMMAND runtime_hardening)
add_executable(policy_runtime tests/policy_runtime.cpp)
target_link_libraries(policy_runtime PRIVATE interspec::runtime)
add_test(NAME policy_runtime COMMAND policy_runtime)
add_executable(p6_security_eval evaluation/security_eval.cpp)
target_link_libraries(p6_security_eval PRIVATE interspec::runtime)
add_test(NAME p6_security_eval COMMAND p6_security_eval)
add_executable(p6_runtime_bench evaluation/runtime_bench.cpp)
target_link_libraries(p6_runtime_bench PRIVATE interspec::runtime Threads::Threads)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(NAME policy_codegen COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_policy.py
  --policy ${CMAKE_CURRENT_SOURCE_DIR}/policy/poc_policy.json
  --source ${CMAKE_CURRENT_SOURCE_DIR}/poc/typed_poc_untrusted.c
  --out-dir ${CMAKE_CURRENT_BINARY_DIR}/generated-policy)
add_test(NAME policy_codegen_hardening COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/policy_codegen_hardening.py)
add_test(NAME boundary_codegen COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/boundary_codegen.py)
add_test(NAME p7c_report COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/p7c_report.py)
add_test(NAME p7c_report_complete COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tools/p7c_report.py --require-complete)
add_test(NAME p8_collect COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/p8_collect.py)
