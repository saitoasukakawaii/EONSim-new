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

add_library(eonsim_build_options INTERFACE)
target_compile_definitions(eonsim_build_options INTERFACE
    MHPC_DEBUG=$<IF:$<CONFIG:Debug>,1,0>
    EONSIM_BUILD_TYPE="$<CONFIG>"
)

add_library(eonsim_core
    src/core/config.cpp
    src/mesh/gmsh.cpp
    src/fem/tet4.cpp
    src/algebra/linear_system.cpp
    src/physics/poisson.cpp
    src/io/vtu.cpp
)
target_include_directories(eonsim_core PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/include")
target_link_libraries(eonsim_core
    PUBLIC eonsim_build_options PETSc::PETSc MPI::MPI_CXX
    PRIVATE EONSimBLAS::BLASLAPACK yaml-cpp::yaml-cpp
)

add_executable(eonsim src/main.cpp)
target_link_libraries(eonsim PRIVATE eonsim_core)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(eonsim_core PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(eonsim PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(BUILD_TESTING)
    enable_testing()
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_test(NAME poisson_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_poisson.py"
            --executable $<TARGET_FILE:eonsim>
            --case "${CMAKE_CURRENT_SOURCE_DIR}/cases/poisson/case.yaml"
            --work "${CMAKE_CURRENT_BINARY_DIR}/verification")
    set_tests_properties(poisson_verification PROPERTIES
        TIMEOUT 90 ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
endif()
