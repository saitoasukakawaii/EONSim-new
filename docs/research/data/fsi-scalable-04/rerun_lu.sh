#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --cpus-per-task=1
#SBATCH --time=00:08:00
set -eu
src=$(realpath "${1:?pass the tested source checkout}")
binary=$(realpath "${2:?pass the Release executable}")
data="$src/docs/research/data"
mpi=/opt/software/openmpi-4.1.8-gcc-11.5.0
export PATH="$mpi/bin:/opt/software/gcc-11.5.0/bin:$PATH"
export LD_LIBRARY_PATH="/opt/software/gcc-11.5.0/lib64:$mpi/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$src/tests:$src/scripts:$src/cases/fsi:$data/fsi-pressure-faces-2026-11-24:$data/fsi-smooth-load-2026-11-24"
exec "$HOME/miniforge/envs/moose/bin/python" "$data/fsi-scalable-04/tube_probe.py" B32 "$binary" \
    "$HOME/workspace/fsi-scalable-04-runs/B-lu-$SLURM_JOB_ID"
