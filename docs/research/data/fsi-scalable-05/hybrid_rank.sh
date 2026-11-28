#!/bin/sh
# Record the mask inherited from MPI before libgomp binds the two workers.
set -eu
rank=${OMPI_COMM_WORLD_RANK:?}
mask=$(awk '$1=="Cpus_allowed_list:" {print $2}' /proc/self/status)
printf 'fsi05_mpi_mask rank=%s cpus=%s\n' "$rank" "$mask"
export OMP_AFFINITY_FORMAT="fsi05_omp rank=$rank worker=%n team=%N cpus=%A"
exec "$@"
