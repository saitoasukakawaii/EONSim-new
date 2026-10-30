#!/usr/bin/env bash
set -eo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
version=${1:-3.23.7}
mode=${2:-release}
selection=${3:-core}
state=${4:-"$root/.cloud"}
state=$(cd "$state" && pwd)
export MAMBA_ROOT_PREFIX="$state/mamba"
eval "$("$state/micromamba" shell hook -s bash)"
micromamba activate "$state/petsc-$version"
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
exec python3 "$root/scripts/cloud/validate.py" --mode "$mode" --selection "$selection" --version "$version"
