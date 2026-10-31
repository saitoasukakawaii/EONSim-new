#!/usr/bin/env bash
set -eo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
version=${1:-3.23.7}
mode=${2:-release}
selection=${3:-core}
state=${4:-"$root/.cloud"}
tests_file=${5:-}
state=$(cd "$state" && pwd)
export MAMBA_ROOT_PREFIX="$state/mamba"
eval "$("$state/micromamba" shell hook -s bash)"
micromamba activate "$state/petsc-$version"
# A developer shell may already expose another PETSc/MPI/MKL installation.
# Keep both direct and transitive link/runtime lookup inside this explicit lock.
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib"
export LIBRARY_PATH="$CONDA_PREFIX/lib"
export PKG_CONFIG_PATH="$CONDA_PREFIX/lib/pkgconfig"
unset CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH CMAKE_PREFIX_PATH
export PETSC_DIR="$CONDA_PREFIX"
export CC="$CONDA_PREFIX/bin/gcc" CXX="$CONDA_PREFIX/bin/g++"
# OpenMPI 4.1.6 bundles hwloc 2.0: its x86 CPUID scanner faults on newer CPUs.
# Linux/sysfs topology remains active; this is unrelated to the PETSc failure.
if [[ "$version" == 3.19.6 ]]; then
    export HWLOC_COMPONENTS=-x86
    # Kernel-restricted containers may not implement process_vm_readv (CMA).
    export OMPI_MCA_btl_vader_single_copy_mechanism=none
    export OMPI_MCA_btl=self,vader,tcp
else
    export OMPI_MCA_btl=self,sm,tcp
fi
# These are single-node correctness runs. Hosted Azure MANA devices may be
# visible but reject UCX UD queue creation; do not auto-select an RDMA PML.
export OMPI_MCA_pml=ob1
unset PETSC_ARCH PYTHONOPTIMIZE
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
# CTest runs one test at a time; some existing tests explicitly need four ranks.
export OMPI_MCA_rmaps_base_oversubscribe=1
# OpenMPI 5 delegates mapping to PRRTE; the old OMPI variable is ignored there.
export PRTE_MCA_rmaps_default_mapping_policy=:oversubscribe
# Compiler activation supplies optimized CXXFLAGS: let existing presets choose flags.
unset CFLAGS CXXFLAGS CPPFLAGS LDFLAGS
args=(--mode "$mode" --selection "$selection" --version "$version")
if [[ -n "$tests_file" ]]; then
    args+=(--tests-file "$tests_file")
fi
exec python3 "$root/scripts/cloud/validate.py" "${args[@]}"
