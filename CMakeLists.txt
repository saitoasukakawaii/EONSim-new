cmake_minimum_required(VERSION 3.21)

project(EONSim VERSION 0.1.0 LANGUAGES C CXX)

list(PREPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")

if(NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug CACHE STRING "Build type" FORCE)
endif()
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
option(BUILD_TESTING "Build focused P0 verification" OFF)

set(EONSIM_ENABLE_PETSC ON CACHE STRING "PETSc runtime: AUTO, ON, or OFF")
include(EONSimBlasLapackProvider)
include(EONSimPETScProvider)
if(NOT EONSIM_HAVE_PETSC)
    message(FATAL_ERROR "The P0 solver requires PETSc; configure with EONSIM_ENABLE_PETSC=ON and a real-double PETSc installation.")
endif()
find_package(MPI REQUIRED COMPONENTS C CXX)
find_package(yaml-cpp CONFIG REQUIRED)
find_path(EONSIM_METIS_INCLUDE_DIR metis.h HINTS "${EONSIM_PETSC_ROOT}/${EONSIM_PETSC_ARCH}/include" REQUIRED)
find_library(EONSIM_METIS_LIBRARY metis HINTS ${EONSIM_PETSC_LIBRARY_DIRS} "${EONSIM_PETSC_ROOT}/${EONSIM_PETSC_ARCH}/lib" REQUIRED)
find_path(EONSIM_HDF5_INCLUDE_DIR hdf5.h HINTS "${EONSIM_PETSC_ROOT}/${EONSIM_PETSC_ARCH}/include" PATH_SUFFIXES hdf5/serial hdf5/openmpi REQUIRED)
find_library(EONSIM_HDF5_LIBRARY hdf5 HINTS ${EONSIM_PETSC_LIBRARY_DIRS} "${EONSIM_PETSC_ROOT}/${EONSIM_PETSC_ARCH}/lib" PATH_SUFFIXES hdf5/serial hdf5/openmpi REQUIRED)
add_library(EONSimPartitionDeps INTERFACE)
target_include_directories(EONSimPartitionDeps INTERFACE "${EONSIM_METIS_INCLUDE_DIR}" "${EONSIM_HDF5_INCLUDE_DIR}")
target_link_libraries(EONSimPartitionDeps INTERFACE "${EONSIM_METIS_LIBRARY}" "${EONSIM_HDF5_LIBRARY}")

add_library(eonsim_build_options INTERFACE)
target_compile_definitions(eonsim_build_options INTERFACE
    MHPC_DEBUG=$<IF:$<CONFIG:Debug>,1,0>
    EONSIM_BUILD_TYPE="$<CONFIG>"
)

add_library(eonsim_core
    src/core/config.cpp
    src/mesh/gmsh.cpp
    src/mesh/partition.cpp
    src/fem/tet4.cpp
    src/fem/field_layout.cpp
    src/algebra/linear_system.cpp
    src/algebra/nonlinear_system.cpp
    src/physics/fluid_element.cpp
    src/fem/reduced_layout.cpp
    src/physics/fsi.cpp
    src/physics/fsi_element.cpp
    src/physics/motion.cpp
    src/physics/ale.cpp
    src/physics/solid.cpp
    src/physics/hyperelastic.cpp
    src/physics/solid_element.cpp
    src/physics/fluid.cpp
    src/physics/poisson.cpp
    src/io/vtu.cpp
)
target_include_directories(eonsim_core PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/include")
target_link_libraries(eonsim_core
    PUBLIC eonsim_build_options PETSc::PETSc MPI::MPI_CXX
    PRIVATE EONSimBLAS::BLASLAPACK yaml-cpp::yaml-cpp EONSimPartitionDeps
)

add_executable(eonsim src/main.cpp)
target_link_libraries(eonsim PRIVATE eonsim_core)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(eonsim_core PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(eonsim PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(BUILD_TESTING)
    enable_testing()
    add_executable(verify_hyperelastic_element tests/verify_hyperelastic_element.cpp)
    target_link_libraries(verify_hyperelastic_element PRIVATE eonsim_core)
    add_test(NAME hyperelastic_element_jacobian COMMAND verify_hyperelastic_element)
    add_executable(verify_fsi_element tests/verify_fsi_element.cpp)
    target_link_libraries(verify_fsi_element PRIVATE eonsim_core)
    add_test(NAME fsi_element_jacobian COMMAND verify_fsi_element)
    add_executable(verify_solid_element tests/verify_solid_element.cpp)
    target_link_libraries(verify_solid_element PRIVATE eonsim_core)
    add_test(NAME solid_element_jacobian COMMAND verify_solid_element)
    add_executable(verify_fluid_element tests/verify_fluid_element.cpp)
    target_link_libraries(verify_fluid_element PRIVATE eonsim_core)
    add_test(NAME fluid_element_jacobian COMMAND verify_fluid_element)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_test(NAME hyperelastic_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_hyperelastic.py"
            --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
            --root "${CMAKE_CURRENT_SOURCE_DIR}" --work "${CMAKE_CURRENT_BINARY_DIR}/hyperelastic_verification")
    set_tests_properties(hyperelastic_verification PROPERTIES TIMEOUT 300
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME elastic_fsi_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_elastic_fsi.py"
            --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
            --case "${CMAKE_CURRENT_SOURCE_DIR}/cases/fsi/elastic.yaml"
            --work "${CMAKE_CURRENT_BINARY_DIR}/elastic_fsi_verification")
    set_tests_properties(elastic_fsi_verification PROPERTIES TIMEOUT 240
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME rigid_fsi_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_fsi.py"
            --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
            --case "${CMAKE_CURRENT_SOURCE_DIR}/cases/fsi/rigid.yaml"
            --work "${CMAKE_CURRENT_BINARY_DIR}/fsi_verification")
    set_tests_properties(rigid_fsi_verification PROPERTIES TIMEOUT 240
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME motion_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_motion.py"
            --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
            --case "${CMAKE_CURRENT_SOURCE_DIR}/cases/motion"
            --work "${CMAKE_CURRENT_BINARY_DIR}/motion_verification")
    set_tests_properties(motion_verification PROPERTIES TIMEOUT 120
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME solid_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_solid.py"
            --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
            --case "${CMAKE_CURRENT_SOURCE_DIR}/cases/solid"
            --work "${CMAKE_CURRENT_BINARY_DIR}/solid_verification")
    set_tests_properties(solid_verification PROPERTIES TIMEOUT 180
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME fluid_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_fluid.py"
            --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
            --work "${CMAKE_CURRENT_BINARY_DIR}/fluid_verification")
    set_tests_properties(fluid_verification PROPERTIES TIMEOUT 180
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME poisson_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_poisson.py"
            --executable $<TARGET_FILE:eonsim>
            --case "${CMAKE_CURRENT_SOURCE_DIR}/cases/poisson/case.yaml"
            --work "${CMAKE_CURRENT_BINARY_DIR}/verification")
    set_tests_properties(poisson_verification PROPERTIES
        TIMEOUT 90 ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME poisson_parallel
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_parallel.py"
            --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
            --case "${CMAKE_CURRENT_SOURCE_DIR}/cases/poisson/case.yaml"
            --work "${CMAKE_CURRENT_BINARY_DIR}/parallel_verification")
    set_tests_properties(poisson_parallel PROPERTIES
        TIMEOUT 120 ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
endif()
