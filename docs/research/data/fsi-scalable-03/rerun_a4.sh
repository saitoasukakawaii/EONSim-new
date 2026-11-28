#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --cpus-per-task=1
#SBATCH --time=00:08:00
#SBATCH --job-name=fsi03-A4
set -eu
# sbatch copies this script. Pass the checked-out source root as its first argument.
src=$(realpath "${1:?pass the EONSim source root}")
ws="$HOME/workspace"
binary="$ws/EONSim-fsi-scalable-02/build/release/eonsim"
echo "a647f6259725218bfadd8a6e60b59aa209096028d6dd98822262175eb2a0abbe  $binary" | sha256sum -c -
mpi_dir=/opt/software/openmpi-4.1.8-gcc-11.5.0
export PATH="$mpi_dir/bin:/opt/software/gcc-11.5.0/bin:$PATH"
export LD_LIBRARY_PATH="/opt/software/gcc-11.5.0/lib64:$mpi_dir/lib:${LD_LIBRARY_PATH:-}"
data="$src/docs/research/data"
export PYTHONPATH="$src/tests:$src/scripts:$src/cases/fsi:$data/fsi-pressure-faces-2026-11-24:$data/fsi-smooth-load-2026-11-24:$ws/EONSim-fsi-scalable-02/tests"
exec "$HOME/miniforge/envs/moose/bin/python" "$data/fsi-scalable-02/screen_tube.py" \
    --binary "$binary" --mpiexec "$mpi_dir/bin/mpiexec" --ranks 4 \
    --gate "$ws/fsi-scalable-02-runs/A20-batch" --modes asm physics \
    --root "$ws/fsi-scalable-03-runs/A4-$SLURM_JOB_ID"
