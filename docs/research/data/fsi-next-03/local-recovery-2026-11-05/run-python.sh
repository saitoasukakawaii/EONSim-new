#!/usr/bin/env bash
set -euo pipefail
prefix=/home/tfblab633/EONSim/.cloud/petsc-3.23.7
export PATH="$prefix/bin:$PATH"
export LD_LIBRARY_PATH="$prefix/lib" LIBRARY_PATH="$prefix/lib"
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig" PETSC_DIR="$prefix"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export OMPI_MCA_btl=self,sm,tcp OMPI_MCA_pml=ob1
export PRTE_MCA_rmaps_default_mapping_policy=:oversubscribe
unset PETSC_ARCH PYTHONOPTIMIZE
export TMPDIR
TMPDIR=$(mktemp -d /tmp/eonsim-next03-20261105.XXXXXX)
exec "$prefix/bin/python" "$@"
