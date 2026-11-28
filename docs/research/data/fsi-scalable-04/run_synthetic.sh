#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=64
#SBATCH --cpus-per-task=2
#SBATCH --exclusive
#SBATCH --time=03:00:00
#SBATCH --job-name=fsi04-synthetic
set -eu
src=$(realpath "${1:?pass the checked-out source root}")
experiment=${2:?pass owner or telescope}
binary=$(realpath "${3:?pass the Release executable}")
binary_commit=${4:?pass the actual binary source commit}
mpi=/opt/software/openmpi-4.1.8-gcc-11.5.0
export PATH="$mpi/bin:/opt/software/gcc-11.5.0/bin:$PATH"
export LD_LIBRARY_PATH="/opt/software/gcc-11.5.0/lib64:$mpi/lib:${LD_LIBRARY_PATH:-}"
data="$src/docs/research/data"
export PYTHONPATH="$src/tests:$src/scripts:$src/cases/fsi:$data/fsi-pressure-faces-2026-11-24:$data/fsi-smooth-load-2026-11-24"
exec "$HOME/miniforge/envs/moose/bin/python" "$data/fsi-scalable-04/synthetic_pairs.py" \
    "$experiment" "$binary" "$binary_commit" "$HOME/workspace/fsi-scalable-02-runs/large-t2/1795788192001678783/results.json" \
    "$HOME/workspace/fsi-scalable-04-runs/$experiment-$SLURM_JOB_ID"
