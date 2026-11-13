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
add_executable(memcached_workload_test tests/memcached_workload.cpp)
target_link_libraries(memcached_workload_test PRIVATE Threads::Threads)
if(MSVC)
  target_compile_options(memcached_workload_test PRIVATE /UNDEBUG)
else()
  target_compile_options(memcached_workload_test PRIVATE -UNDEBUG)
endif()
add_test(NAME memcached_workload_test COMMAND memcached_workload_test)
add_executable(memcached_measurement_test tests/memcached_measurement.cpp)
if(MSVC)
  target_compile_options(memcached_measurement_test PRIVATE /UNDEBUG)
else()
  target_compile_options(memcached_measurement_test PRIVATE -UNDEBUG)
endif()
add_test(NAME memcached_measurement_test COMMAND memcached_measurement_test)
add_executable(runtime_hardening tests/runtime_hardening.cpp)
target_link_libraries(runtime_hardening PRIVATE interspec::runtime Threads::Threads)
add_test(NAME runtime_hardening COMMAND runtime_hardening)
add_executable(runtime_object_layout tests/runtime_object_layout.cpp)
target_link_libraries(runtime_object_layout PRIVATE interspec::runtime Threads::Threads)
add_test(NAME runtime_object_layout COMMAND runtime_object_layout)
add_executable(policy_runtime tests/policy_runtime.cpp)
target_link_libraries(policy_runtime PRIVATE interspec::runtime)
add_test(NAME policy_runtime COMMAND policy_runtime)
add_executable(p9b_wasm_runtime tests/p9b_wasm_runtime.cpp)
target_link_libraries(p9b_wasm_runtime PRIVATE interspec::runtime)
add_test(NAME p9b_wasm_runtime COMMAND p9b_wasm_runtime)
add_executable(p6_security_eval evaluation/security_eval.cpp)
target_link_libraries(p6_security_eval PRIVATE interspec::runtime)
add_test(NAME p6_security_eval COMMAND p6_security_eval)
add_executable(p6_runtime_bench evaluation/runtime_bench.cpp)
target_link_libraries(p6_runtime_bench PRIVATE interspec::runtime Threads::Threads)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(NAME runtime_microbench_evidence COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/runtime_microbench_evidence.py)
add_executable(memcached_client evaluation/memcached_client.cpp)
target_link_libraries(memcached_client PRIVATE Threads::Threads)
add_test(NAME memcached_client_protocol COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/memcached_client_protocol.py $<TARGET_FILE:memcached_client>)
add_test(NAME memcached_buffered_protocol COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/memcached_buffered_protocol.py $<TARGET_FILE:memcached_client>)
add_test(NAME evaluation_checkpoint COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/evaluation_checkpoint.py)
add_test(NAME checkpointed_memcached COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/checkpointed_memcached.py)
add_test(NAME matrix_checkpoint COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/matrix_checkpoint.py)
add_test(NAME capacity_diagnostic COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/capacity_diagnostic.py)
add_test(NAME capacity_affinity_observation COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/capacity_affinity_observation.py)
add_test(NAME memcached_matrix_evidence COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/memcached_matrix_evidence.py)
add_test(NAME memcached_workload_metadata COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/memcached_workload_metadata.py)
add_test(NAME memcached_lru_transform COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/memcached_lru_transform.py
  --compiler ${CMAKE_CXX_COMPILER})
add_test(NAME sp3_security_delta_evidence COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/sp3_security_delta_evidence.py)
add_executable(diagnostics tests/diagnostics.cpp)
target_link_libraries(diagnostics PRIVATE interspec::runtime Threads::Threads)
target_compile_definitions(diagnostics PRIVATE INTERSPEC_ENABLE_TRACE=1)
add_test(NAME diagnostics COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/diagnostics.py $<TARGET_FILE:diagnostics>)
add_test(NAME policy_codegen COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_policy.py
  --policy ${CMAKE_CURRENT_SOURCE_DIR}/policy/poc_policy.json
  --source ${CMAKE_CURRENT_SOURCE_DIR}/poc/typed_poc_untrusted.c
  --out-dir ${CMAKE_CURRENT_BINARY_DIR}/generated-policy)
add_test(NAME policy_codegen_hardening COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/policy_codegen_hardening.py)
add_test(NAME policy_inference_build COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/policy_inference_build.py)
add_test(NAME boundary_codegen COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/boundary_codegen.py)
add_test(NAME p9b_wasm_codegen COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/p9b_wasm_codegen.py)
add_test(NAME p11_wasm_bridge_transform COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/p11_wasm_bridge_transform.py)
add_test(NAME p11_controlled_validation COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/p11_controlled_validation.py)
add_test(NAME p7c_report COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/p7c_report.py)
add_test(NAME p7c_report_complete COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tools/p7c_report.py --require-complete)
add_test(NAME p8_report COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/p8_report.py)
add_test(NAME p8_performance_summary COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/p8_performance.py)
add_test(NAME p8_application_summary COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/p8_application.py)
add_test(NAME p8_result_renderer COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/p8_render.py)
add_test(NAME p9a_bridge_transform COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/p9a_bridge_transform.py)
add_test(NAME p9a_application_summary COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/p9a_application.py)
add_test(NAME p9a_result_renderer COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/p9a_render.py)

add_executable(pointer_census tests/pointer_census.cpp)
target_link_libraries(pointer_census PRIVATE interspec::runtime Threads::Threads ${CMAKE_DL_LIBS})
add_test(NAME pointer_census COMMAND pointer_census)
add_test(NAME pointer_census_evidence COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/pointer_census_evidence.py)
add_test(NAME behavioral_parity_evidence COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/behavioral_parity_evidence.py)
