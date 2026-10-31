cmake_minimum_required(VERSION 3.21)

project(EONSim VERSION 0.1.0 LANGUAGES C CXX)

list(PREPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")

if(NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug CACHE STRING "Build type" FORCE)
endif()
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
option(BUILD_TESTING "Build numerical and distributed verification" OFF)
option(EONSIM_VERIFY_LOCKED_RUNTIME "Verify the cloud lock's OpenMPI/int32 ABI" OFF)
option(MHPC_BUILD_DOCS "Enable the optional Doxygen target" OFF)
if(MHPC_BUILD_DOCS)
    find_package(Doxygen REQUIRED COMPONENTS doxygen)
    add_custom_target(docs
        COMMAND "${CMAKE_COMMAND}" -E make_directory "${CMAKE_CURRENT_SOURCE_DIR}/build/docs"
        COMMAND Doxygen::doxygen "${CMAKE_CURRENT_SOURCE_DIR}/docs/doxygen/Doxyfile"
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" VERBATIM)
endif()

set(EONSIM_ENABLE_PETSC ON CACHE STRING "PETSc runtime: AUTO, ON, or OFF")
include(EONSimBlasLapackProvider)
include(EONSimPETScProvider)
if(NOT EONSIM_HAVE_PETSC)
    message(FATAL_ERROR "EONSim requires PETSc; configure with EONSIM_ENABLE_PETSC=ON and a real-double PETSc installation.")
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
    src/mesh/mesh_import.cpp
    src/mesh/fsi_domains.cpp
    src/mesh/partition.cpp
    src/fem/tet4.cpp
    src/fem/boundary_geometry.cpp
    src/fem/field_layout.cpp
    src/algebra/linear_system.cpp
    src/algebra/nonlinear_system.cpp
    src/algebra/schur_solver.cpp
    src/algebra/pc_plan.cpp
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
    src/physics/fluid_boundary.cpp
    src/physics/poisson.cpp
    src/physics/scalar2d.cpp
    src/io/checkpoint.cpp
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
    if(EONSIM_VERIFY_LOCKED_RUNTIME)
        add_executable(verify_runtime tests/verify_runtime.cpp)
        target_link_libraries(verify_runtime PRIVATE PETSc::PETSc MPI::MPI_CXX)
        add_test(NAME runtime_mpi COMMAND "${MPIEXEC_EXECUTABLE}" "${MPIEXEC_NUMPROC_FLAG}" 2
            ${MPIEXEC_PREFLAGS} $<TARGET_FILE:verify_runtime> ${MPIEXEC_POSTFLAGS})
        set_tests_properties(runtime_mpi PROPERTIES TIMEOUT 30 PROCESSORS 2 LABELS "core;mpi-failure")
    endif()
    add_executable(verify_pc_plan tests/verify_pc_plan.cpp)
    target_link_libraries(verify_pc_plan PRIVATE eonsim_core)
    foreach(ranks IN ITEMS 1 2 4)
        add_test(NAME pc_plan_mpi${ranks} COMMAND "${MPIEXEC_EXECUTABLE}" "${MPIEXEC_NUMPROC_FLAG}" ${ranks}
            ${MPIEXEC_PREFLAGS} $<TARGET_FILE:verify_pc_plan> ${MPIEXEC_POSTFLAGS})
        set_tests_properties(pc_plan_mpi${ranks} PROPERTIES TIMEOUT 60 PROCESSORS ${ranks}
            LABELS "core;mpi-failure;rank-${ranks}" ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    endforeach()
    add_executable(verify_coo_jacobian tests/verify_coo_jacobian.cpp)
    target_link_libraries(verify_coo_jacobian PRIVATE eonsim_core)
    add_test(NAME coo_jacobian COMMAND verify_coo_jacobian)
    foreach(ranks IN ITEMS 2 4)
        add_test(NAME coo_jacobian_mpi${ranks} COMMAND "${MPIEXEC_EXECUTABLE}" "${MPIEXEC_NUMPROC_FLAG}" ${ranks}
            ${MPIEXEC_PREFLAGS} $<TARGET_FILE:verify_coo_jacobian> ${MPIEXEC_POSTFLAGS})
        set_tests_properties(coo_jacobian_mpi${ranks} PROPERTIES PROCESSORS ${ranks})
    endforeach()
    set_tests_properties(coo_jacobian coo_jacobian_mpi2 coo_jacobian_mpi4 PROPERTIES TIMEOUT 60
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_executable(verify_linear_lifetime tests/verify_linear_lifetime.cpp)
    target_link_libraries(verify_linear_lifetime PRIVATE eonsim_core)
    add_test(NAME linear_lifetime COMMAND verify_linear_lifetime)
    add_test(NAME linear_lifetime_mpi COMMAND "${MPIEXEC_EXECUTABLE}" "${MPIEXEC_NUMPROC_FLAG}" 2
        ${MPIEXEC_PREFLAGS} $<TARGET_FILE:verify_linear_lifetime> ${MPIEXEC_POSTFLAGS})
    set_tests_properties(linear_lifetime linear_lifetime_mpi PROPERTIES TIMEOUT 60
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_executable(verify_solver_failures tests/verify_solver_failures.cpp)
    target_link_libraries(verify_solver_failures PRIVATE eonsim_core)
    add_test(NAME solver_failures COMMAND verify_solver_failures)
    add_test(NAME solver_failures_mpi COMMAND "${MPIEXEC_EXECUTABLE}" "${MPIEXEC_NUMPROC_FLAG}" 2
        ${MPIEXEC_PREFLAGS} $<TARGET_FILE:verify_solver_failures> ${MPIEXEC_POSTFLAGS})
    set_tests_properties(solver_failures solver_failures_mpi PROPERTIES TIMEOUT 60
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_executable(verify_checkpoint tests/verify_checkpoint.cpp)
    target_link_libraries(verify_checkpoint PRIVATE eonsim_core)
    add_test(NAME checkpoint_publication COMMAND verify_checkpoint "${CMAKE_CURRENT_BINARY_DIR}/checkpoint_publication")
    add_test(NAME checkpoint_publication_mpi COMMAND "${MPIEXEC_EXECUTABLE}" "${MPIEXEC_NUMPROC_FLAG}" 2
        ${MPIEXEC_PREFLAGS} $<TARGET_FILE:verify_checkpoint> ${MPIEXEC_POSTFLAGS} "${CMAKE_CURRENT_BINARY_DIR}/checkpoint_publication_mpi")
    set_tests_properties(checkpoint_publication checkpoint_publication_mpi PROPERTIES TIMEOUT 60
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_executable(verify_nonlinear_acceptance tests/verify_nonlinear_acceptance.cpp)
    target_link_libraries(verify_nonlinear_acceptance PRIVATE eonsim_core)
    add_test(NAME nonlinear_acceptance COMMAND verify_nonlinear_acceptance)
    add_test(NAME nonlinear_acceptance_mpi COMMAND "${MPIEXEC_EXECUTABLE}" "${MPIEXEC_NUMPROC_FLAG}" 2
        ${MPIEXEC_PREFLAGS} $<TARGET_FILE:verify_nonlinear_acceptance> ${MPIEXEC_POSTFLAGS})
    set_tests_properties(nonlinear_acceptance nonlinear_acceptance_mpi PROPERTIES TIMEOUT 60
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_executable(verify_boundary_geometry tests/verify_boundary_geometry.cpp)
    target_link_libraries(verify_boundary_geometry PRIVATE eonsim_core)
    add_test(NAME boundary_geometry COMMAND verify_boundary_geometry)
    add_executable(verify_element2d tests/verify_element2d.cpp)
    target_link_libraries(verify_element2d PRIVATE eonsim_core)
    add_test(NAME element2d_oracles COMMAND verify_element2d)
    set_tests_properties(element2d_oracles PROPERTIES LABELS "core;rank-1")
    add_executable(verify_quadrature tests/verify_quadrature.cpp)
    target_link_libraries(verify_quadrature PRIVATE eonsim_core)
    add_test(NAME quadrature_moments COMMAND verify_quadrature)
    add_executable(verify_hyperelastic_element tests/verify_hyperelastic_element.cpp)
    target_link_libraries(verify_hyperelastic_element PRIVATE eonsim_core)
    add_test(NAME hyperelastic_element_jacobian COMMAND verify_hyperelastic_element)
    add_executable(verify_fsi_element tests/verify_fsi_element.cpp)
    target_link_libraries(verify_fsi_element PRIVATE eonsim_core)
    add_test(NAME fsi_element_jacobian COMMAND verify_fsi_element)
    add_executable(verify_time_integration tests/verify_time_integration.cpp)
    target_link_libraries(verify_time_integration PRIVATE eonsim_core)
    add_test(NAME time_integration COMMAND verify_time_integration)
    set_tests_properties(time_integration PROPERTIES LABELS "core;rank-1")
    add_executable(verify_solid_element tests/verify_solid_element.cpp)
    target_link_libraries(verify_solid_element PRIVATE eonsim_core)
    add_test(NAME solid_element_jacobian COMMAND verify_solid_element)
    add_executable(verify_fluid_element tests/verify_fluid_element.cpp)
    target_link_libraries(verify_fluid_element PRIVATE eonsim_core)
    add_test(NAME fluid_element_jacobian COMMAND verify_fluid_element)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_test(NAME layout_policy_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_layout_policy.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
        --work "${CMAKE_CURRENT_BINARY_DIR}/layout_policy_verification")
    set_tests_properties(layout_policy_verification PROPERTIES TIMEOUT 120 PROCESSORS 2 LABELS "core;rank-1;rank-2"
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME mesh_import_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_mesh_import.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
        --work "${CMAKE_CURRENT_BINARY_DIR}/mesh_import_verification")
    set_tests_properties(mesh_import_verification PROPERTIES TIMEOUT 120 PROCESSORS 4 LABELS "core;rank-1;rank-2;rank-4"
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    foreach(check space time failure)
        add_test(NAME scalar2d_${check}
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_scalar2d.py"
            --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}" --checks ${check}
            --work "${CMAKE_CURRENT_BINARY_DIR}/scalar2d_${check}")
        set_tests_properties(scalar2d_${check} PROPERTIES TIMEOUT 300 PROCESSORS 4 LABELS "core;rank-1;rank-2;rank-4"
            ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    endforeach()
    add_test(NAME fluid_alpha_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_fluid_time.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}" --alpha
        --work "${CMAKE_CURRENT_BINARY_DIR}/fluid_alpha_verification")
    add_test(NAME solid_alpha_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_solid_time.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}" --alpha
        --work "${CMAKE_CURRENT_BINARY_DIR}/solid_alpha_verification")
    set_tests_properties(fluid_alpha_verification solid_alpha_verification PROPERTIES TIMEOUT 300 PROCESSORS 4 LABELS "core;rank-1;rank-2;rank-4"
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME ale_time_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_ale_time.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
        --work "${CMAKE_CURRENT_BINARY_DIR}/ale_time_verification")
    add_test(NAME ale_alpha_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_ale_time.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}" --alpha
        --work "${CMAKE_CURRENT_BINARY_DIR}/ale_alpha_verification")
    add_test(NAME fsi_alpha_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_fsi_time.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}" --alpha
        --work "${CMAKE_CURRENT_BINARY_DIR}/fsi_alpha_verification")
    add_test(NAME domains_alpha_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_domains.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}" --scheme generalized_alpha
        --work "${CMAKE_CURRENT_BINARY_DIR}/domains_alpha_verification")
    set_tests_properties(ale_alpha_verification domains_alpha_verification PROPERTIES TIMEOUT 300 PROCESSORS 4 LABELS "core;rank-1;rank-2;rank-4"
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    set_tests_properties(fsi_alpha_verification PROPERTIES TIMEOUT 600 PROCESSORS 4 LABELS "core;rank-1;rank-2;rank-4"
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME fsi_time_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_fsi_time.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
        --work "${CMAKE_CURRENT_BINARY_DIR}/fsi_time_verification")
    add_test(NAME domains_bdf2_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_domains.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}" --scheme bdf2
        --work "${CMAKE_CURRENT_BINARY_DIR}/domains_bdf2_verification")
    set_tests_properties(ale_time_verification domains_bdf2_verification PROPERTIES TIMEOUT 300 PROCESSORS 4 LABELS "core;rank-1;rank-2;rank-4"
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    set_tests_properties(fsi_time_verification PROPERTIES TIMEOUT 600 PROCESSORS 4 LABELS "core;rank-1;rank-2;rank-4"
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME solid_time_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_solid_time.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
        --work "${CMAKE_CURRENT_BINARY_DIR}/solid_time_verification")
    set_tests_properties(solid_time_verification PROPERTIES TIMEOUT 300 PROCESSORS 4 LABELS "core;rank-1;rank-2;rank-4"
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME fluid_time_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_fluid_time.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
        --work "${CMAKE_CURRENT_BINARY_DIR}/fluid_time_verification")
    set_tests_properties(fluid_time_verification PROPERTIES TIMEOUT 300 PROCESSORS 4 LABELS "core;rank-1;rank-2;rank-4"
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME fluid_coo_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_fluid_coo.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
        --work "${CMAKE_CURRENT_BINARY_DIR}/fluid_coo_verification")
    set_tests_properties(fluid_coo_verification PROPERTIES TIMEOUT 300 PROCESSORS 4
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME profile_log_validation
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_profile_validation.py")
    set_tests_properties(profile_log_validation PROPERTIES TIMEOUT 30)
    add_test(NAME fluid_element_report
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_fluid_element_report.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
        --work "${CMAKE_CURRENT_BINARY_DIR}/fluid_element_report")
    set_tests_properties(fluid_element_report PROPERTIES TIMEOUT 120 PROCESSORS 2
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME pc_recipe_retry
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_time_retry.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}" --recipe hybrid
        --work "${CMAKE_CURRENT_BINARY_DIR}/pc_recipe_retry")
    set_tests_properties(pc_recipe_retry PROPERTIES TIMEOUT 300 PROCESSORS 2 LABELS "core;rank-1;rank-2"
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME pc_recipe_restart
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_pc_restart.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
        --work "${CMAKE_CURRENT_BINARY_DIR}/pc_recipe_restart")
    set_tests_properties(pc_recipe_restart PROPERTIES TIMEOUT 300 PROCESSORS 4 LABELS "core;rank-1;rank-2;rank-4"
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    foreach(recipe IN ITEMS physics quantity hybrid)
        add_test(NAME pc_recipe_${recipe}
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_schur.py"
            --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
            --recipe ${recipe} --work "${CMAKE_CURRENT_BINARY_DIR}/pc_recipe_${recipe}")
        set_tests_properties(pc_recipe_${recipe} PROPERTIES TIMEOUT 300 PROCESSORS 4
            LABELS "core;rank-1;rank-2;rank-4" ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    endforeach()
    add_test(NAME schur_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_schur.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
        --work "${CMAKE_CURRENT_BINARY_DIR}/schur_verification")
    set_tests_properties(schur_verification PROPERTIES TIMEOUT 300 PROCESSORS 4
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME time_retry_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_time_retry.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
        --work "${CMAKE_CURRENT_BINARY_DIR}/time_retry_verification")
    set_tests_properties(time_retry_verification PROPERTIES TIMEOUT 300 ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME domains_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_domains.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
        --work "${CMAKE_CURRENT_BINARY_DIR}/domains_verification")
    set_tests_properties(domains_verification PROPERTIES TIMEOUT 240 ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME regions_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_regions.py"
        --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
        --work "${CMAKE_CURRENT_BINARY_DIR}/regions_verification")
    set_tests_properties(regions_verification PROPERTIES TIMEOUT 180 ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME tagged_fluid_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_tagged_fluid.py"
            --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
            --work "${CMAKE_CURRENT_BINARY_DIR}/tagged_fluid_verification")
    set_tests_properties(tagged_fluid_verification PROPERTIES TIMEOUT 180
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
    add_test(NAME restart_block_verification
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_restart.py"
            --executable $<TARGET_FILE:eonsim> --mpiexec "${MPIEXEC_EXECUTABLE}"
            --root "${CMAKE_CURRENT_SOURCE_DIR}" --work "${CMAKE_CURRENT_BINARY_DIR}/restart_verification")
    set_tests_properties(restart_block_verification PROPERTIES TIMEOUT 300 PROCESSORS 4
        ENVIRONMENT "OMP_NUM_THREADS=1;OPENBLAS_NUM_THREADS=1;MKL_NUM_THREADS=1")
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
    # Reuse numerical assertions in the existing tests; labels only select runs.
    set_tests_properties(scalar2d_failure PROPERTIES LABELS "core;mpi-failure;rank-1;rank-2;rank-4")
    set_tests_properties(linear_lifetime linear_lifetime_mpi PROPERTIES LABELS "core;mpi-failure")
    set_tests_properties(solver_failures solver_failures_mpi
        nonlinear_acceptance nonlinear_acceptance_mpi coo_jacobian coo_jacobian_mpi2
        PROPERTIES LABELS "core;mpi-failure")
    set_tests_properties(poisson_verification poisson_parallel fluid_verification
        solid_verification rigid_fsi_verification checkpoint_publication checkpoint_publication_mpi
        restart_block_verification coo_jacobian_mpi4 fluid_coo_verification
        PROPERTIES LABELS "core")
    get_property(eonsim_tests DIRECTORY PROPERTY TESTS)
    foreach(test IN LISTS eonsim_tests)
        get_property(test_timeout TEST ${test} PROPERTY TIMEOUT)
        if(NOT test_timeout)
            set_property(TEST ${test} PROPERTY TIMEOUT 30)
        endif()
        if(test MATCHES "mpi4$" OR test STREQUAL "coo_jacobian_mpi4")
            set_property(TEST ${test} APPEND PROPERTY LABELS "rank-4")
        elseif(test MATCHES "_mpi$|mpi2$")
            set_property(TEST ${test} APPEND PROPERTY LABELS "rank-2")
        elseif(test MATCHES "^(fluid_coo_verification|schur_verification|restart_block_verification)$")
            set_property(TEST ${test} APPEND PROPERTY LABELS "rank-1;rank-2;rank-4")
        elseif(test STREQUAL "poisson_verification")
            set_property(TEST ${test} APPEND PROPERTY LABELS "rank-1")
        elseif(test MATCHES "verification$|^poisson_parallel$|^fluid_element_report$")
            set_property(TEST ${test} APPEND PROPERTY LABELS "rank-1;rank-2")
        else()
            set_property(TEST ${test} APPEND PROPERTY LABELS "rank-1")
        endif()
    endforeach()
endif()
