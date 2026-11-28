#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --time=00:10:00
set -eu
root="$HOME/workspace/fsi-scalable-05-runs"
old="$HOME/workspace/fsi-scalable-04-runs/release-final/build/release"
mpi=/opt/software/openmpi-4.1.8-gcc-11.5.0
export PATH="$mpi/bin:/opt/software/gcc-11.5.0/bin:$PATH"
export LD_LIBRARY_PATH="/opt/software/gcc-11.5.0/lib64:$mpi/lib:${LD_LIBRARY_PATH:-}"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p "$root/build"
exec "$HOME/miniforge/envs/moose/bin/python" "$1" "$root/source" "$root/build" "$old" "$2"
