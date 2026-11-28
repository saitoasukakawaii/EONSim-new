#!/bin/bash
#SBATCH --nodes=1
#SBATCH --exclusive
set -eu
case_name=${1:?A, B or C}
shift
root=${FSI05_ROOT:-"$HOME/workspace/fsi-scalable-05-runs"}
src="$root/source"
data="$src/docs/research/data"
mpi=/opt/software/openmpi-4.1.8-gcc-11.5.0
export PATH="$mpi/bin:/opt/software/gcc-11.5.0/bin:$PATH"
export LD_LIBRARY_PATH="/opt/software/gcc-11.5.0/lib64:$mpi/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$src/tests:$src/scripts:$src/cases/fsi:$data/fsi-pressure-faces-2026-11-24:$data/fsi-smooth-load-2026-11-24"
py="$HOME/miniforge/envs/moose/bin/python"
case "$case_name" in A) cores=4;; B) cores=32;; C) cores=64;; *) exit 2;; esac
if [ "$case_name" = C ]; then
    for arg in "$@"; do
        if [ "$arg" = --scaling-from ]; then cores="${SLURM_NTASKS:?}"; fi
    done
fi
cpus=$("$py" -c 'import os,sys; a=sorted(os.sched_getaffinity(0)); n=int(sys.argv[1]); assert len(a)>=n; print(",".join(map(str,a[:n])))' "$cores")
if [ "${1:-}" = "--timing" ]; then
    shift
    exec taskset -c "$cpus" "$py" "$data/fsi-scalable-05/time_forcing.py" "$@"
fi
exec taskset -c "$cpus" "$py" "$data/fsi-scalable-05/run_window.py" "$case_name" "$@"
