#!/usr/bin/env bash
# Build the pinned independent solver with the compiler/MPI environment used in the study.
set -euo pipefail
src=$(cd "${1:?svFSI checkout required}" && pwd)
prefix=$(cd "${2:?dependency prefix required}" && pwd)
build=${3:?new build directory required}
test "$(git -C "$src" rev-parse HEAD)" = 94a2ff5cab2ad9e89e9bf12e0de36eaaa9b85571
export PATH="$prefix/bin:$PATH" LD_LIBRARY_PATH="$prefix/lib"
cmake -S "$src/Code" -B "$build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER="$prefix/bin/gcc" -DCMAKE_CXX_COMPILER="$prefix/bin/g++" \
    -DCMAKE_Fortran_COMPILER="$prefix/bin/gfortran" -DMPI_C_COMPILER="$prefix/bin/mpicc" \
    -DMPI_CXX_COMPILER="$prefix/bin/mpicxx" -DMPI_Fortran_COMPILER="$prefix/bin/mpifort" \
    -DCMAKE_PREFIX_PATH="$prefix" -DSV_USE_TRILINOS=OFF
cmake --build "$build" --parallel 3
