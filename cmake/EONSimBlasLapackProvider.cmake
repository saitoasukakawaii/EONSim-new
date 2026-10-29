# Provider-neutral BLAS/LAPACK selection for EONSim and bundled solver TPLs.
#
# AUTO deliberately does not prefer oneMKL. On macOS it selects Accelerate;
# elsewhere it tries OpenBLAS, BLIS+libFLAME, generic system BLAS/LAPACK, and
# only then oneMKL as a last available fallback.

set(EONSIM_BLAS_LAPACK_PROVIDER "AUTO" CACHE STRING
    "BLAS/LAPACK provider: AUTO, SYSTEM, OPENBLAS, MKL, BLIS_FLAME, or ACCELERATE")
set_property(CACHE EONSIM_BLAS_LAPACK_PROVIDER PROPERTY STRINGS
             AUTO SYSTEM OPENBLAS MKL BLIS_FLAME ACCELERATE)
string(TOUPPER "${EONSIM_BLAS_LAPACK_PROVIDER}" _eonsim_blas_provider_requested)
set(_eonsim_blas_provider_values
    AUTO SYSTEM OPENBLAS MKL BLIS_FLAME ACCELERATE)
list(FIND _eonsim_blas_provider_values
     "${_eonsim_blas_provider_requested}" _eonsim_blas_provider_index)
if(_eonsim_blas_provider_index LESS 0)
  message(FATAL_ERROR
    "EONSIM_BLAS_LAPACK_PROVIDER must be AUTO, SYSTEM, OPENBLAS, MKL, "
    "BLIS_FLAME, or ACCELERATE; got '${EONSIM_BLAS_LAPACK_PROVIDER}'.")
endif()

# oneMKL BLACS is needed by MPI Cluster PARDISO, not by ordinary BLAS/LAPACK.
# The top-level configuration enables BLACS for AUTO/ON PARDISO discovery;
# explicitly disabling PARDISO must therefore also keep an explicitly selected
# MKL BLAS provider free of the cluster-MPI linkage.
if(DEFINED EONSIM_ENABLE_PARDISO AND EONSIM_ENABLE_PARDISO STREQUAL "OFF")
  set(ENABLE_BLACS OFF CACHE BOOL "Enable oneMKL BLACS/cluster solver support" FORCE)
endif()

function(_eonsim_define_blas_lapack_target provider link_items)
  if(NOT TARGET EONSimBLAS::BLASLAPACK)
    add_library(EONSimBLAS::BLASLAPACK INTERFACE IMPORTED GLOBAL)
  endif()
  set_target_properties(EONSimBLAS::BLASLAPACK PROPERTIES
    INTERFACE_LINK_LIBRARIES "${link_items}")
  set(EONSIM_BLAS_LAPACK_PROVIDER_EFFECTIVE "${provider}" CACHE INTERNAL
      "Resolved EONSim BLAS/LAPACK provider" FORCE)
endfunction()

function(_eonsim_try_find_cmake_blas vendor provider required out_found)
  set(_saved_bla_vendor "${BLA_VENDOR}")
  set(BLA_VENDOR "${vendor}")
  if(required)
    find_package(BLAS REQUIRED)
    find_package(LAPACK REQUIRED)
  else()
    find_package(BLAS QUIET)
    find_package(LAPACK QUIET)
  endif()
  set(BLA_VENDOR "${_saved_bla_vendor}")
  if(BLAS_FOUND AND LAPACK_FOUND)
    set(_items)
    if(TARGET LAPACK::LAPACK)
      list(APPEND _items LAPACK::LAPACK)
    else()
      list(APPEND _items ${LAPACK_LIBRARIES})
    endif()
    if(TARGET BLAS::BLAS)
      list(APPEND _items BLAS::BLAS)
    else()
      list(APPEND _items ${BLAS_LIBRARIES})
    endif()
    list(REMOVE_DUPLICATES _items)
    _eonsim_define_blas_lapack_target("${provider}" "${_items}")
    set(${out_found} TRUE PARENT_SCOPE)
  else()
    set(${out_found} FALSE PARENT_SCOPE)
  endif()
endfunction()

function(_eonsim_try_find_blis_flame required out_found)
  if(required)
    find_library(EONSIM_BLIS_LIBRARY NAMES blis REQUIRED)
    find_library(EONSIM_FLAME_LIBRARY NAMES flame libflame REQUIRED)
  else()
    find_library(EONSIM_BLIS_LIBRARY NAMES blis)
    find_library(EONSIM_FLAME_LIBRARY NAMES flame libflame)
  endif()
  if(EONSIM_BLIS_LIBRARY AND EONSIM_FLAME_LIBRARY)
    _eonsim_define_blas_lapack_target(
      "BLIS_FLAME" "${EONSIM_FLAME_LIBRARY};${EONSIM_BLIS_LIBRARY}")
    set(${out_found} TRUE PARENT_SCOPE)
  else()
    set(${out_found} FALSE PARENT_SCOPE)
  endif()
endfunction()

function(_eonsim_try_find_accelerate required out_found)
  if(NOT APPLE)
    if(required)
      message(FATAL_ERROR
        "EONSIM_BLAS_LAPACK_PROVIDER=ACCELERATE is supported only on macOS.")
    endif()
    set(${out_found} FALSE PARENT_SCOPE)
    return()
  endif()
  if(required)
    find_library(EONSIM_ACCELERATE_FRAMEWORK Accelerate REQUIRED)
  else()
    find_library(EONSIM_ACCELERATE_FRAMEWORK Accelerate)
  endif()
  if(EONSIM_ACCELERATE_FRAMEWORK)
    _eonsim_define_blas_lapack_target(
      "ACCELERATE" "${EONSIM_ACCELERATE_FRAMEWORK}")
    set(${out_found} TRUE PARENT_SCOPE)
  else()
    set(${out_found} FALSE PARENT_SCOPE)
  endif()
endfunction()

function(_eonsim_try_find_mkl required out_found)
  # Keep LP64 as EONSim's sparse/direct-solver ABI.
  set(MKL_INTERFACE lp64 CACHE STRING "oneMKL integer interface" FORCE)
  set(MKL_THREADING intel_thread CACHE STRING "oneMKL threading mode" FORCE)
  if(required)
    find_package(MKL CONFIG REQUIRED)
  else()
    find_package(MKL CONFIG QUIET)
  endif()
  if(TARGET MKL::MKL)
    _eonsim_define_blas_lapack_target("MKL" "MKL::MKL")
    set(${out_found} TRUE PARENT_SCOPE)
  else()
    set(${out_found} FALSE PARENT_SCOPE)
  endif()
endfunction()

set(_eonsim_blas_found FALSE)
if(_eonsim_blas_provider_requested STREQUAL "AUTO")
  if(APPLE)
    _eonsim_try_find_accelerate(FALSE _eonsim_blas_found)
  else()
    _eonsim_try_find_cmake_blas("OpenBLAS" "OPENBLAS" FALSE _eonsim_blas_found)
    if(NOT _eonsim_blas_found)
      _eonsim_try_find_blis_flame(FALSE _eonsim_blas_found)
    endif()
    if(NOT _eonsim_blas_found)
      _eonsim_try_find_cmake_blas("Generic" "SYSTEM" FALSE _eonsim_blas_found)
    endif()
    if(NOT _eonsim_blas_found)
      _eonsim_try_find_mkl(FALSE _eonsim_blas_found)
    endif()
  endif()
  if(NOT _eonsim_blas_found)
    message(FATAL_ERROR
      "No supported BLAS/LAPACK provider was found. Install OpenBLAS, "
      "BLIS+libFLAME, a generic BLAS/LAPACK, oneMKL, or use Accelerate on macOS; "
      "or select EONSIM_BLAS_LAPACK_PROVIDER explicitly.")
  endif()
elseif(_eonsim_blas_provider_requested STREQUAL "SYSTEM")
  _eonsim_try_find_cmake_blas("Generic" "SYSTEM" TRUE _eonsim_blas_found)
elseif(_eonsim_blas_provider_requested STREQUAL "OPENBLAS")
  _eonsim_try_find_cmake_blas("OpenBLAS" "OPENBLAS" TRUE _eonsim_blas_found)
elseif(_eonsim_blas_provider_requested STREQUAL "BLIS_FLAME")
  _eonsim_try_find_blis_flame(TRUE _eonsim_blas_found)
elseif(_eonsim_blas_provider_requested STREQUAL "ACCELERATE")
  _eonsim_try_find_accelerate(TRUE _eonsim_blas_found)
elseif(_eonsim_blas_provider_requested STREQUAL "MKL")
  _eonsim_try_find_mkl(TRUE _eonsim_blas_found)
endif()

# The public numerical API is provider-neutral.  The private Level-1 kernels
# use a CBLAS interface when the selected provider exposes one, with a scalar
# fallback retained for generic BLAS installations that ship only the Fortran
# ABI (and for vectors larger than an LP64 CBLAS integer can address).
set(EONSIM_BLAS_LEVEL1_COMPILE_DEFINITIONS)
set(EONSIM_BLAS_LEVEL1_INCLUDE_DIRS)
set(EONSIM_BLAS_LEVEL1_EXTERNAL OFF CACHE INTERNAL
    "Whether EONSim Level-1 kernels use the selected external BLAS" FORCE)
set(EONSIM_BLAS_LEVEL1_MODE "SCALAR" CACHE INTERNAL
    "EONSim Level-1 kernel implementation" FORCE)

if(EONSIM_BLAS_LAPACK_PROVIDER_EFFECTIVE STREQUAL "MKL")
  list(APPEND EONSIM_BLAS_LEVEL1_COMPILE_DEFINITIONS
       EONSIM_BLAS_USE_MKL_CBLAS)
  set(EONSIM_BLAS_LEVEL1_EXTERNAL ON CACHE INTERNAL "" FORCE)
  set(EONSIM_BLAS_LEVEL1_MODE "MKL_CBLAS" CACHE INTERNAL "" FORCE)
elseif(EONSIM_BLAS_LAPACK_PROVIDER_EFFECTIVE STREQUAL "ACCELERATE")
  list(APPEND EONSIM_BLAS_LEVEL1_COMPILE_DEFINITIONS
       EONSIM_BLAS_USE_ACCELERATE_CBLAS)
  set(EONSIM_BLAS_LEVEL1_EXTERNAL ON CACHE INTERNAL "" FORCE)
  set(EONSIM_BLAS_LEVEL1_MODE "ACCELERATE_CBLAS" CACHE INTERNAL "" FORCE)
else()
  find_path(EONSIM_CBLAS_INCLUDE_DIR NAMES cblas.h)
  if(EONSIM_CBLAS_INCLUDE_DIR)
    include(CheckCXXSourceCompiles)
    set(_eonsim_saved_required_includes "${CMAKE_REQUIRED_INCLUDES}")
    set(_eonsim_saved_required_libraries "${CMAKE_REQUIRED_LIBRARIES}")
    set(CMAKE_REQUIRED_INCLUDES "${EONSIM_CBLAS_INCLUDE_DIR}")
    set(CMAKE_REQUIRED_LIBRARIES EONSimBLAS::BLASLAPACK)
    unset(EONSIM_SELECTED_CBLAS_WORKS CACHE)
    check_cxx_source_compiles(
      "#include <cblas.h>\nint main(){double x[1]={1.0}; double y[1]={2.0}; return cblas_ddot(1,x,1,y,1)==2.0 ? 0 : 1;}"
      EONSIM_SELECTED_CBLAS_WORKS)
    set(CMAKE_REQUIRED_INCLUDES "${_eonsim_saved_required_includes}")
    set(CMAKE_REQUIRED_LIBRARIES "${_eonsim_saved_required_libraries}")
    unset(_eonsim_saved_required_includes)
    unset(_eonsim_saved_required_libraries)
    if(EONSIM_SELECTED_CBLAS_WORKS)
      list(APPEND EONSIM_BLAS_LEVEL1_COMPILE_DEFINITIONS
           EONSIM_BLAS_USE_GENERIC_CBLAS)
      list(APPEND EONSIM_BLAS_LEVEL1_INCLUDE_DIRS
           "${EONSIM_CBLAS_INCLUDE_DIR}")
      set(EONSIM_BLAS_LEVEL1_EXTERNAL ON CACHE INTERNAL "" FORCE)
      set(EONSIM_BLAS_LEVEL1_MODE "GENERIC_CBLAS" CACHE INTERNAL "" FORCE)
    endif()
  endif()
endif()

# Finalize PARDISO-specific target metadata only after AUTO discovery and the
# EONSim module targets both exist.  Multiphysics still has one legacy in-tree
# include of the private PARDISO adapter; keep its capability macro consistent
# with Linalg so an enabled build never mixes unavailable inline stubs with the
# real Linalg implementation.  The adapter header itself remains MKL-header
# free, so this does not leak a vendor include dependency into Multiphysics.
#
# Intel's MKL CMake target also does not guarantee the ELF link ordering
# required by MPI Cluster PARDISO.  Keeping MPI::MPI_C after MKL::MKL on the
# owning Linalg target ensures libmkl_blacs_* sees a live MPI provider under
# GNU/ELF --as-needed, and preserves the ordered static install-tree closure.
function(_eonsim_finalize_pardiso_targets)
  if(EONSIM_HAVE_PARDISO)
    if(TARGET eonsim_multiphysics)
      target_compile_definitions(eonsim_multiphysics PRIVATE
                                 EONSIM_HAVE_PARDISO=1)
    endif()
    if(TARGET eonsim_linalg AND TARGET MKL::MKL AND TARGET MPI::MPI_C)
      target_link_libraries(eonsim_linalg PRIVATE MKL::MKL MPI::MPI_C)
    endif()
  endif()
endfunction()
cmake_language(DEFER CALL _eonsim_finalize_pardiso_targets)

message(STATUS
  "EONSim BLAS/LAPACK provider: ${EONSIM_BLAS_LAPACK_PROVIDER_EFFECTIVE}")
message(STATUS
  "EONSim Level-1 kernels: ${EONSIM_BLAS_LEVEL1_MODE}")

unset(_eonsim_blas_provider_requested)
unset(_eonsim_blas_provider_values)
unset(_eonsim_blas_provider_index)
unset(_eonsim_blas_found)