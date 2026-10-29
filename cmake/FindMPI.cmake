# Project-local Intel MPI discovery for Windows.
#
# The bundled MUMPS and HYPRE projects call find_package(MPI) from nested
# directories.  CMake 3.29 may re-run its staged Fortran probe there and the
# legacy oneAPI 2022 wrappers do not provide metadata in the form expected by
# that probe.  For Intel MPI on Windows we can construct the public FindMPI
# interface directly from the wrapper location.  Other platforms and MPI
# implementations use CMake's upstream module unchanged.

set(_fem_intel_mpi_compiler_hint "${MPI_C_COMPILER};${MPI_CXX_COMPILER};${MPI_Fortran_COMPILER}")
set(_fem_intel_mpi_hint_text "${_fem_intel_mpi_compiler_hint}")
string(TOLOWER "${_fem_intel_mpi_hint_text}" _fem_intel_mpi_hint_lower)

if(WIN32 AND _fem_intel_mpi_hint_lower MATCHES "intel[/\\]oneapi[/\\]mpi")
  set(_fem_intel_mpi_root "")
  foreach(_fem_mpi_wrapper ${MPI_C_COMPILER} ${MPI_CXX_COMPILER} ${MPI_Fortran_COMPILER})
    if(NOT _fem_mpi_wrapper STREQUAL "")
      get_filename_component(_fem_mpi_bin "${_fem_mpi_wrapper}" DIRECTORY)
      get_filename_component(_fem_mpi_root_candidate "${_fem_mpi_bin}" DIRECTORY)
      if(EXISTS "${_fem_mpi_root_candidate}/include/mpi.h")
        set(_fem_intel_mpi_root "${_fem_mpi_root_candidate}")
        break()
      endif()
    endif()
  endforeach()

  if(_fem_intel_mpi_root STREQUAL "" AND DEFINED ENV{I_MPI_ROOT})
    set(_fem_intel_mpi_root "$ENV{I_MPI_ROOT}")
  endif()

  set(_fem_intel_mpi_include "${_fem_intel_mpi_root}/include")
  set(_fem_intel_mpi_lib_dir "${_fem_intel_mpi_root}/lib/release")
  set(_fem_intel_mpi_c_lib "${_fem_intel_mpi_lib_dir}/impi.lib")
  set(_fem_intel_mpi_cxx_lib "${_fem_intel_mpi_lib_dir}/impicxx.lib")

  if(EXISTS "${_fem_intel_mpi_include}/mpi.h" AND EXISTS "${_fem_intel_mpi_c_lib}")
    set(MPI_INCLUDE_DIR "${_fem_intel_mpi_include}")
    set(MPI_INCLUDE_PATH "${_fem_intel_mpi_include}")
    set(MPI_VERSION 3.1)
    set(MPI_VERSION_MAJOR 3)
    set(MPI_VERSION_MINOR 1)

    set(MPI_C_FOUND TRUE)
    set(MPI_C_INCLUDE_DIRS "${_fem_intel_mpi_include}")
    set(MPI_C_INCLUDE_PATH "${_fem_intel_mpi_include}")
    set(MPI_C_COMPILER_INCLUDE_DIRS "${_fem_intel_mpi_include}")
    set(MPI_C_LIBRARIES "${_fem_intel_mpi_c_lib}")
    set(MPI_C_LIB_NAMES impi)
    set(MPI_C_WORKS TRUE)

    if(EXISTS "${_fem_intel_mpi_cxx_lib}")
      set(MPI_CXX_FOUND TRUE)
      set(MPI_CXX_INCLUDE_DIRS "${_fem_intel_mpi_include}")
      set(MPI_CXX_INCLUDE_PATH "${_fem_intel_mpi_include}")
      set(MPI_CXX_COMPILER_INCLUDE_DIRS "${_fem_intel_mpi_include}")
      set(MPI_CXX_LIBRARIES "${_fem_intel_mpi_c_lib};${_fem_intel_mpi_cxx_lib}")
      set(MPI_CXX_LIB_NAMES impi;impicxx)
      set(MPI_CXX_WORKS TRUE)
    else()
      set(MPI_CXX_FOUND FALSE)
    endif()

    if(MPI_Fortran_COMPILER OR EXISTS "${_fem_intel_mpi_root}/bin/mpiifort.bat")
      set(MPI_Fortran_FOUND TRUE)
      set(MPI_Fortran_INCLUDE_DIRS "${_fem_intel_mpi_include}")
      set(MPI_Fortran_INCLUDE_PATH "${_fem_intel_mpi_include}")
      set(MPI_Fortran_COMPILER_INCLUDE_DIRS "${_fem_intel_mpi_include}")
      set(MPI_Fortran_MODULE_DIR "${_fem_intel_mpi_include}")
      set(MPI_Fortran_F77_HEADER_DIR "${_fem_intel_mpi_include}")
      set(MPI_Fortran_LIBRARIES "${_fem_intel_mpi_c_lib}")
      set(MPI_Fortran_LIB_NAMES impi)
      set(MPI_Fortran_WORKS TRUE)
      set(MPI_Fortran_F77_HEADER_WORKS TRUE)
    endif()

    set(MPI_C_FOUND "${MPI_C_FOUND}" CACHE BOOL "Intel MPI C component" FORCE)
    set(MPI_CXX_FOUND "${MPI_CXX_FOUND}" CACHE BOOL "Intel MPI CXX component" FORCE)
    if(DEFINED MPI_Fortran_FOUND)
      set(MPI_Fortran_FOUND "${MPI_Fortran_FOUND}" CACHE BOOL "Intel MPI Fortran component" FORCE)
    endif()
    set(MPI_CXX_SKIP_MPICXX OFF)
    set(MPI_FOUND TRUE)
    set(MPIEXEC_EXECUTABLE "${_fem_intel_mpi_root}/bin/mpiexec.exe")
    set(MPIEXEC_NUMPROC_FLAG -n)
    set(MPIEXEC_PREFLAGS -localonly)
    set(MPIEXEC_POSTFLAGS)

    if(NOT TARGET MPI::MPI_C)
      add_library(MPI::MPI_C INTERFACE IMPORTED)
      set_target_properties(MPI::MPI_C PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${MPI_C_INCLUDE_DIRS}"
        INTERFACE_LINK_LIBRARIES "${MPI_C_LIBRARIES}")
    endif()
    if(MPI_CXX_FOUND AND NOT TARGET MPI::MPI_CXX)
      add_library(MPI::MPI_CXX INTERFACE IMPORTED)
      set_target_properties(MPI::MPI_CXX PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${MPI_CXX_INCLUDE_DIRS}"
        INTERFACE_LINK_LIBRARIES "${MPI_CXX_LIBRARIES}")
    endif()
    if(MPI_Fortran_FOUND AND NOT TARGET MPI::MPI_Fortran)
      add_library(MPI::MPI_Fortran INTERFACE IMPORTED)
      set_target_properties(MPI::MPI_Fortran PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${MPI_Fortran_INCLUDE_DIRS}"
        INTERFACE_LINK_LIBRARIES "${MPI_Fortran_LIBRARIES}")
    endif()

    set(MPI_C_ADDITIONAL_INCLUDE_DIRS)
    set(MPI_CXX_ADDITIONAL_INCLUDE_DIRS)
    set(MPI_Fortran_ADDITIONAL_INCLUDE_DIRS)
    set(MPI_C_COMPILE_OPTIONS)
    set(MPI_CXX_COMPILE_OPTIONS)
    set(MPI_Fortran_COMPILE_OPTIONS)
    set(MPI_C_COMPILE_DEFINITIONS)
    set(MPI_CXX_COMPILE_DEFINITIONS)
    set(MPI_Fortran_COMPILE_DEFINITIONS)
    set(MPI_C_LINK_FLAGS)
    set(MPI_CXX_LINK_FLAGS)
    set(MPI_Fortran_LINK_FLAGS)
    set(MPI_CXX_SKIP_MPICXX OFF)

    include(FindPackageHandleStandardArgs)
    find_package_handle_standard_args(MPI
      REQUIRED_VARS MPI_C_FOUND MPI_CXX_FOUND
      VERSION_VAR MPI_VERSION)
    return()
  endif()
endif()

# Fallback for non-Windows and non-Intel-MPI toolchains.
include("${CMAKE_ROOT}/Modules/FindMPI.cmake")