# PETSc is a foundational external numerical runtime for EONSim. It is not
# vendored under third_party because PETSc owns its own configure/build graph,
# MPI ABI, BLAS/LAPACK selection, and optional external solver packages.

if(DEFINED EONSIM_PETSC_PROVIDER_INCLUDED)
  return()
endif()
set(EONSIM_PETSC_PROVIDER_INCLUDED TRUE)

set(EONSIM_ENABLE_PETSC "AUTO" CACHE STRING "PETSc runtime: AUTO, ON, or OFF")
set_property(CACHE EONSIM_ENABLE_PETSC PROPERTY STRINGS AUTO ON OFF)
string(TOUPPER "${EONSIM_ENABLE_PETSC}" _eonsim_petsc_mode)
if(NOT _eonsim_petsc_mode STREQUAL "AUTO" AND
   NOT _eonsim_petsc_mode STREQUAL "ON" AND
   NOT _eonsim_petsc_mode STREQUAL "OFF")
  message(FATAL_ERROR
    "EONSIM_ENABLE_PETSC must be AUTO, ON, or OFF; got '${EONSIM_ENABLE_PETSC}'.")
endif()
set(EONSIM_ENABLE_PETSC "${_eonsim_petsc_mode}" CACHE STRING
    "PETSc runtime: AUTO, ON, or OFF" FORCE)
unset(_eonsim_petsc_mode)

set(EONSIM_PETSC_ROOT "" CACHE PATH
    "Configured PETSc source/install root; defaults to the PETSC_DIR environment variable")
set(EONSIM_PETSC_ARCH "" CACHE STRING
    "PETSc architecture name for an in-tree PETSc build; defaults to PETSC_ARCH")
set(EONSIM_PETSC_PKG_CONFIG_PATH "" CACHE PATH
    "Optional directory containing PETSc.pc/petsc.pc when it cannot be inferred")

if(NOT EONSIM_PETSC_ROOT AND DEFINED ENV{PETSC_DIR} AND NOT "$ENV{PETSC_DIR}" STREQUAL "")
  set(EONSIM_PETSC_ROOT "$ENV{PETSC_DIR}" CACHE PATH
      "Configured PETSc source/install root" FORCE)
endif()
if(NOT EONSIM_PETSC_ARCH AND DEFINED ENV{PETSC_ARCH} AND NOT "$ENV{PETSC_ARCH}" STREQUAL "")
  set(EONSIM_PETSC_ARCH "$ENV{PETSC_ARCH}" CACHE STRING
      "PETSc architecture name" FORCE)
endif()
if(NOT EONSIM_PETSC_PKG_CONFIG_PATH AND
   DEFINED ENV{EONSIM_PETSC_PKG_CONFIG_PATH} AND
   NOT "$ENV{EONSIM_PETSC_PKG_CONFIG_PATH}" STREQUAL "")
  set(EONSIM_PETSC_PKG_CONFIG_PATH "$ENV{EONSIM_PETSC_PKG_CONFIG_PATH}" CACHE PATH
      "Directory containing PETSc.pc/petsc.pc" FORCE)
endif()

set(EONSIM_HAVE_PETSC OFF CACHE INTERNAL "PETSc runtime compiled into EONSim" FORCE)
set(EONSIM_PETSC_DISCOVERY "disabled" CACHE INTERNAL "PETSc discovery method" FORCE)

if(EONSIM_ENABLE_PETSC STREQUAL "OFF")
  message(STATUS "EONSim PETSc runtime: OFF")
  return()
endif()

set(_eonsim_petsc_prefix_hints)
set(_eonsim_petsc_pkg_hints)
if(EONSIM_PETSC_ROOT)
  list(APPEND _eonsim_petsc_prefix_hints "${EONSIM_PETSC_ROOT}")
  if(EONSIM_PETSC_ARCH)
    list(APPEND _eonsim_petsc_prefix_hints
      "${EONSIM_PETSC_ROOT}/${EONSIM_PETSC_ARCH}"
      "${EONSIM_PETSC_ROOT}/${EONSIM_PETSC_ARCH}/lib/cmake")
    list(APPEND _eonsim_petsc_pkg_hints
      "${EONSIM_PETSC_ROOT}/${EONSIM_PETSC_ARCH}/lib/pkgconfig")
  else()
    list(APPEND _eonsim_petsc_prefix_hints
      "${EONSIM_PETSC_ROOT}/lib/cmake")
    list(APPEND _eonsim_petsc_pkg_hints
      "${EONSIM_PETSC_ROOT}/lib/pkgconfig")
  endif()
endif()
if(EONSIM_PETSC_PKG_CONFIG_PATH)
  list(PREPEND _eonsim_petsc_pkg_hints "${EONSIM_PETSC_PKG_CONFIG_PATH}")
endif()
list(REMOVE_DUPLICATES _eonsim_petsc_pkg_hints)

set(_eonsim_saved_prefix_path "${CMAKE_PREFIX_PATH}")
if(_eonsim_petsc_prefix_hints)
  list(PREPEND CMAKE_PREFIX_PATH ${_eonsim_petsc_prefix_hints})
endif()

# EONSim always links the stable PETSc::PETSc target. Do not make that target
# an ALIAS of a discovery-specific imported target because installed EONSim
# packages must recreate the same stable dependency name.
find_package(PETSc CONFIG QUIET)
if(TARGET PETSc::PETSc)
  set(EONSIM_HAVE_PETSC ON CACHE INTERNAL "PETSc runtime compiled into EONSim" FORCE)
  set(EONSIM_PETSC_DISCOVERY "cmake-config" CACHE INTERNAL "PETSc discovery method" FORCE)
elseif(TARGET PETSC::PETSC)
  add_library(PETSc::PETSc INTERFACE IMPORTED GLOBAL)
  set_target_properties(PETSc::PETSc PROPERTIES
    INTERFACE_LINK_LIBRARIES PETSC::PETSC)
  set(EONSIM_HAVE_PETSC ON CACHE INTERNAL "PETSc runtime compiled into EONSim" FORCE)
  set(EONSIM_PETSC_DISCOVERY "cmake-config" CACHE INTERNAL "PETSc discovery method" FORCE)
endif()

if(WIN32)
  function(_eonsim_petsc_windows_to_cygwin output_variable input_path)
    file(TO_CMAKE_PATH "${input_path}" _eonsim_path)
    if(_eonsim_path MATCHES "^([A-Za-z]):/(.*)$")
      string(TOLOWER "${CMAKE_MATCH_1}" _eonsim_drive)
      set(_eonsim_path "/cygdrive/${_eonsim_drive}/${CMAKE_MATCH_2}")
    endif()
    set(${output_variable} "${_eonsim_path}" PARENT_SCOPE)
  endfunction()

  function(_eonsim_petsc_cygwin_to_windows output_variable input_path)
    set(_eonsim_path "${input_path}")
    if(_eonsim_path MATCHES "^/cygdrive/([A-Za-z])(/.*)?$")
      string(TOUPPER "${CMAKE_MATCH_1}" _eonsim_drive)
      set(_eonsim_tail "${CMAKE_MATCH_2}")
      if(NOT _eonsim_tail)
        set(_eonsim_tail "/")
      endif()
      set(_eonsim_path "${_eonsim_drive}:${_eonsim_tail}")
    endif()
    file(TO_CMAKE_PATH "${_eonsim_path}" _eonsim_path)
    set(${output_variable} "${_eonsim_path}" PARENT_SCOPE)
  endfunction()

  # PETSc's native Windows build is configured under Cygwin. Its PETSc.pc
  # therefore contains /cygdrive/... paths. Query Cygwin pkgconf directly
  # instead of routing it through CMake's FindPkgConfig, which is a native
  # Windows module and does not reliably bridge that path model.
  if(NOT PKG_CONFIG_EXECUTABLE)
    set(_eonsim_cygwin_roots)
    if(DEFINED ENV{CYGWIN_ROOT} AND NOT "$ENV{CYGWIN_ROOT}" STREQUAL "")
      list(APPEND _eonsim_cygwin_roots "$ENV{CYGWIN_ROOT}")
    endif()
    list(APPEND _eonsim_cygwin_roots "C:/cygwin64" "C:/cygwin")
    list(REMOVE_DUPLICATES _eonsim_cygwin_roots)
    foreach(_eonsim_cygwin_root IN LISTS _eonsim_cygwin_roots)
      if(EXISTS "${_eonsim_cygwin_root}/bin/pkgconf.exe")
        set(PKG_CONFIG_EXECUTABLE "${_eonsim_cygwin_root}/bin/pkgconf.exe"
            CACHE FILEPATH "pkg-config executable used for PETSc discovery" FORCE)
        break()
      endif()
    endforeach()
  endif()

  if(NOT EONSIM_HAVE_PETSC AND PKG_CONFIG_EXECUTABLE AND _eonsim_petsc_pkg_hints)
    set(_eonsim_petsc_cygwin_pkg_hints)
    foreach(_eonsim_petsc_pkg_hint IN LISTS _eonsim_petsc_pkg_hints)
      _eonsim_petsc_windows_to_cygwin(
        _eonsim_petsc_cygwin_pkg_hint "${_eonsim_petsc_pkg_hint}")
      list(APPEND _eonsim_petsc_cygwin_pkg_hints "${_eonsim_petsc_cygwin_pkg_hint}")
    endforeach()
    string(JOIN ":" _eonsim_petsc_pkg_path ${_eonsim_petsc_cygwin_pkg_hints})

    set(_eonsim_petsc_pc_module "PETSc")
    execute_process(
      COMMAND "${CMAKE_COMMAND}" -E env
              "PKG_CONFIG_PATH=${_eonsim_petsc_pkg_path}"
              "${PKG_CONFIG_EXECUTABLE}" --modversion "${_eonsim_petsc_pc_module}"
      RESULT_VARIABLE _eonsim_petsc_pkg_result
      OUTPUT_VARIABLE _eonsim_petsc_pkg_version
      ERROR_QUIET
      OUTPUT_STRIP_TRAILING_WHITESPACE)
    if(NOT _eonsim_petsc_pkg_result EQUAL 0)
      set(_eonsim_petsc_pc_module "petsc")
      execute_process(
        COMMAND "${CMAKE_COMMAND}" -E env
                "PKG_CONFIG_PATH=${_eonsim_petsc_pkg_path}"
                "${PKG_CONFIG_EXECUTABLE}" --modversion "${_eonsim_petsc_pc_module}"
        RESULT_VARIABLE _eonsim_petsc_pkg_result
        OUTPUT_VARIABLE _eonsim_petsc_pkg_version
        ERROR_QUIET
        OUTPUT_STRIP_TRAILING_WHITESPACE)
    endif()

    if(_eonsim_petsc_pkg_result EQUAL 0)
      execute_process(
        COMMAND "${CMAKE_COMMAND}" -E env
                "PKG_CONFIG_PATH=${_eonsim_petsc_pkg_path}"
                "${PKG_CONFIG_EXECUTABLE}" --cflags-only-I "${_eonsim_petsc_pc_module}"
        RESULT_VARIABLE _eonsim_petsc_cflags_result
        OUTPUT_VARIABLE _eonsim_petsc_cflags_text
        ERROR_QUIET
        OUTPUT_STRIP_TRAILING_WHITESPACE)
      execute_process(
        COMMAND "${CMAKE_COMMAND}" -E env
                "PKG_CONFIG_PATH=${_eonsim_petsc_pkg_path}"
                "${PKG_CONFIG_EXECUTABLE}" --libs --static "${_eonsim_petsc_pc_module}"
        RESULT_VARIABLE _eonsim_petsc_libs_result
        OUTPUT_VARIABLE _eonsim_petsc_libs_text
        ERROR_QUIET
        OUTPUT_STRIP_TRAILING_WHITESPACE)

      if(_eonsim_petsc_cflags_result EQUAL 0 AND _eonsim_petsc_libs_result EQUAL 0)
        separate_arguments(_eonsim_petsc_cflag_tokens UNIX_COMMAND "${_eonsim_petsc_cflags_text}")
        separate_arguments(_eonsim_petsc_link_tokens UNIX_COMMAND "${_eonsim_petsc_libs_text}")

        set(_eonsim_petsc_include_dirs_native)
        foreach(_eonsim_token IN LISTS _eonsim_petsc_cflag_tokens)
          if(_eonsim_token MATCHES "^-I(.+)$")
            _eonsim_petsc_cygwin_to_windows(_eonsim_native_path "${CMAKE_MATCH_1}")
            list(APPEND _eonsim_petsc_include_dirs_native "${_eonsim_native_path}")
          endif()
        endforeach()

        # Resolve every -L directory first. Native MSVC linking must not rely on
        # CMake's INTERFACE_LINK_DIRECTORIES here: with the mixed MSVC/oneAPI
        # toolchain CMake can wrap /LIBPATH as /Qoption,link,/LIBPATH, which is
        # rejected when the generated command invokes link.exe directly.
        set(_eonsim_petsc_library_dirs_native)
        foreach(_eonsim_token IN LISTS _eonsim_petsc_link_tokens)
          if(_eonsim_token MATCHES "^-L(.+)$")
            _eonsim_petsc_cygwin_to_windows(_eonsim_native_path "${CMAKE_MATCH_1}")
            list(APPEND _eonsim_petsc_library_dirs_native "${_eonsim_native_path}")
          endif()
        endforeach()
        list(REMOVE_DUPLICATES _eonsim_petsc_library_dirs_native)

        set(_eonsim_petsc_libraries_native)
        set(_eonsim_petsc_link_options)
        foreach(_eonsim_token IN LISTS _eonsim_petsc_link_tokens)
          if(_eonsim_token MATCHES "^-L(.+)$")
            # Already consumed above.
          elseif(_eonsim_token MATCHES "^-l(.+)$")
            set(_eonsim_lib_name "${CMAKE_MATCH_1}")
            set(_eonsim_resolved_lib "")
            set(_eonsim_lib_candidates
              "${_eonsim_lib_name}.lib"
              "lib${_eonsim_lib_name}.lib"
              "${_eonsim_lib_name}.a"
              "lib${_eonsim_lib_name}.a")
            foreach(_eonsim_lib_dir IN LISTS _eonsim_petsc_library_dirs_native)
              foreach(_eonsim_lib_candidate IN LISTS _eonsim_lib_candidates)
                if(EXISTS "${_eonsim_lib_dir}/${_eonsim_lib_candidate}")
                  set(_eonsim_resolved_lib "${_eonsim_lib_dir}/${_eonsim_lib_candidate}")
                  break()
                endif()
              endforeach()
              if(_eonsim_resolved_lib)
                break()
              endif()
            endforeach()
            if(_eonsim_resolved_lib)
              list(APPEND _eonsim_petsc_libraries_native "${_eonsim_resolved_lib}")
              if(_eonsim_lib_name STREQUAL "petsc")
                message(STATUS "EONSim PETSc archive: '${_eonsim_resolved_lib}'")
              endif()
            elseif(_eonsim_lib_name STREQUAL "petsc")
              message(FATAL_ERROR
                "PETSc pkgconf returned -lpetsc but no native PETSc archive was found in '${_eonsim_petsc_library_dirs_native}'. Expected petsc.lib, libpetsc.lib, petsc.a, or libpetsc.a.")
            else()
              list(APPEND _eonsim_petsc_libraries_native "${_eonsim_lib_name}.lib")
            endif()
          elseif(_eonsim_token MATCHES "^/cygdrive/")
            _eonsim_petsc_cygwin_to_windows(_eonsim_native_path "${_eonsim_token}")
            list(APPEND _eonsim_petsc_libraries_native "${_eonsim_native_path}")
          elseif(_eonsim_token MATCHES "^-")
            list(APPEND _eonsim_petsc_link_options "${_eonsim_token}")
          else()
            list(APPEND _eonsim_petsc_libraries_native "${_eonsim_token}")
          endif()
        endforeach()

        list(REMOVE_DUPLICATES _eonsim_petsc_include_dirs_native)

        add_library(PETSc::PETSc INTERFACE IMPORTED GLOBAL)
        set_property(TARGET PETSc::PETSc PROPERTY INTERFACE_INCLUDE_DIRECTORIES
          "${_eonsim_petsc_include_dirs_native}")
        set_property(TARGET PETSc::PETSc PROPERTY INTERFACE_LINK_LIBRARIES
          "${_eonsim_petsc_libraries_native}")
        if(_eonsim_petsc_link_options)
          set_property(TARGET PETSc::PETSc PROPERTY INTERFACE_LINK_OPTIONS
            "${_eonsim_petsc_link_options}")
        endif()

        set(EONSIM_HAVE_PETSC ON CACHE INTERNAL "PETSc runtime compiled into EONSim" FORCE)
        set(EONSIM_PETSC_DISCOVERY "pkgconf-direct" CACHE INTERNAL "PETSc discovery method" FORCE)
        message(STATUS
          "EONSim PETSc pkgconf: ${_eonsim_petsc_pkg_version}; executable='${PKG_CONFIG_EXECUTABLE}'")
      endif()
    endif()
  endif()

  if(NOT EONSIM_HAVE_PETSC AND EONSIM_PETSC_ROOT AND NOT PKG_CONFIG_EXECUTABLE)
    message(STATUS
      "EONSim PETSc pkgconf bridge: pkgconf.exe was not found; install the Cygwin pkgconf package or set PKG_CONFIG_EXECUTABLE explicitly")
  endif()
else()
  if(NOT EONSIM_HAVE_PETSC)
    find_package(PkgConfig QUIET)
    if(PkgConfig_FOUND)
      set(_eonsim_saved_pkg_config_path "$ENV{PKG_CONFIG_PATH}")
      set(_eonsim_petsc_pkg_path "")
      if(_eonsim_petsc_pkg_hints)
        string(JOIN ":" _eonsim_petsc_pkg_path ${_eonsim_petsc_pkg_hints})
        if(_eonsim_saved_pkg_config_path)
          string(APPEND _eonsim_petsc_pkg_path ":${_eonsim_saved_pkg_config_path}")
        endif()
        set(ENV{PKG_CONFIG_PATH} "${_eonsim_petsc_pkg_path}")
      endif()

      pkg_check_modules(EONSIM_PETSC QUIET IMPORTED_TARGET GLOBAL PETSc)
      if(NOT TARGET PkgConfig::EONSIM_PETSC)
        pkg_check_modules(EONSIM_PETSC QUIET IMPORTED_TARGET GLOBAL petsc)
      endif()
      if(TARGET PkgConfig::EONSIM_PETSC)
        add_library(PETSc::PETSc INTERFACE IMPORTED GLOBAL)
        set_target_properties(PETSc::PETSc PROPERTIES
          INTERFACE_LINK_LIBRARIES PkgConfig::EONSIM_PETSC)
        set(EONSIM_HAVE_PETSC ON CACHE INTERNAL "PETSc runtime compiled into EONSim" FORCE)
        set(EONSIM_PETSC_DISCOVERY "pkg-config" CACHE INTERNAL "PETSc discovery method" FORCE)
      endif()

      set(ENV{PKG_CONFIG_PATH} "${_eonsim_saved_pkg_config_path}")
    endif()
  endif()
endif()

set(CMAKE_PREFIX_PATH "${_eonsim_saved_prefix_path}")
unset(_eonsim_saved_prefix_path)
unset(_eonsim_petsc_prefix_hints)
unset(_eonsim_petsc_pkg_hints)
unset(_eonsim_cygwin_roots)
unset(_eonsim_cygwin_root)
unset(_eonsim_petsc_cygwin_pkg_hints)
unset(_eonsim_petsc_cygwin_pkg_hint)
unset(_eonsim_petsc_pkg_path)
unset(_eonsim_petsc_pc_module)
unset(_eonsim_petsc_pkg_result)
unset(_eonsim_petsc_pkg_version)
unset(_eonsim_petsc_cflags_result)
unset(_eonsim_petsc_libs_result)
unset(_eonsim_petsc_cflags_text)
unset(_eonsim_petsc_libs_text)
unset(_eonsim_petsc_cflag_tokens)
unset(_eonsim_petsc_link_tokens)
unset(_eonsim_petsc_include_dirs_native)
unset(_eonsim_petsc_library_dirs_native)
unset(_eonsim_petsc_libraries_native)
unset(_eonsim_petsc_link_options)
unset(_eonsim_token)
unset(_eonsim_native_path)
unset(_eonsim_lib_name)
unset(_eonsim_lib_dir)
unset(_eonsim_lib_candidates)
unset(_eonsim_lib_candidate)
unset(_eonsim_resolved_lib)
unset(_eonsim_saved_pkg_config_path)

# PETSc headers use variadic macro machinery that requires MSVC's conforming
# preprocessor. Propagate the modern switch through the stable PETSc interface
# so every EONSim target that includes PETSc headers compiles consistently.
if(EONSIM_HAVE_PETSC AND MSVC AND TARGET PETSc::PETSc)
  set_property(TARGET PETSc::PETSc APPEND PROPERTY
    INTERFACE_COMPILE_OPTIONS "/Zc:preprocessor")
endif()

if(EONSIM_HAVE_PETSC)
  message(STATUS
    "EONSim PETSc runtime: ON (${EONSIM_PETSC_DISCOVERY}); root='${EONSIM_PETSC_ROOT}', arch='${EONSIM_PETSC_ARCH}'")
elseif(EONSIM_ENABLE_PETSC STREQUAL "ON")
  message(FATAL_ERROR
    "EONSIM_ENABLE_PETSC=ON but PETSc was not found. Do not copy PETSc into EONSim/third_party. Configure and install PETSc externally, then set PETSC_DIR/PETSC_ARCH or EONSIM_PETSC_ROOT. If the installation exposes only PETSc.pc/petsc.pc, ensure pkg-config/pkgconf is available and set EONSIM_PETSC_PKG_CONFIG_PATH when needed.")
else()
  message(STATUS
    "EONSim PETSc runtime: AUTO (not found); native algebra remains available only as the migration/regression path")
endif()