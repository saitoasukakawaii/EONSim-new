#!/usr/bin/env bash
set -e -o pipefail
export LC_ALL=C PAGER=cat MODULES_PAGER=cat
source ~/.svMultiPhysics-new.sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMPI_MCA_pml=ob1 OMPI_MCA_btl=self,vader,tcp
runs=$HOME/workspace/fsi-scalable-01-runs
src=$HOME/workspace/EONSim-fsi-scalable-01
repo=https://github.com/saitoasukakawaii/EONSim-new
cd "$src"
export FSI_RUNS="$runs" OMP_DYNAMIC=FALSE OMP_PLACES=cores OMP_PROC_BIND=close
remote=796153b6ebf5a665d6f0ed30a037d9a7c154e78d
test "$(git rev-parse HEAD)" = "$remote"
test "$(sha256sum build/release/eonsim | cut -d' ' -f1)" = "$(tail -1 "$runs/transfer-metrics-source.txt" | cut -d' ' -f1)"
python=$HOME/miniforge/bin/python
mpi=$(command -v mpiexec)
"$python" "$runs/zero-lift-ab-retry.py" > "$runs/zero-lift-ab-retry.log" 2>&1 || printf '%s\n' 'zero-lift comparison had a failure'
(export OMPI_MCA_hwloc_base_binding_policy=core OMPI_MCA_rmaps_base_mapping_policy=core; "$python" "$runs/verify_pulsatile_robin_rcr_retry.py" --executable build/release/eonsim --mpiexec "$mpi" --work "$runs/pulsatile-robin-rcr-retry" > "$runs/pulsatile-robin-rcr-retry.log" 2>&1) || printf '%s\n' 'pulsatile tube test had a failure'
(export OMPI_MCA_hwloc_base_binding_policy=core OMPI_MCA_rmaps_base_mapping_policy=core; ctest --test-dir build/release --output-on-failure -R '^(fluid_verification|solid_verification|hyperelastic_verification|rigid_fsi_verification|elastic_fsi_verification|fsi_flow|fsi_branched_rcr|fsi_curved_inlet|fsi_tube|fsi_tube_wall_support|fsi_tube_rcr)$' > "$runs/physics-coverage.log" 2>&1) || printf '%s\n' 'physical regression had a failure'
"$python" scripts/benchmark_fsi_block_scaling.py --executable build/release/eonsim --mpiexec "$mpi" --build-source "$remote" --mpi-arg=--bind-to --mpi-arg=core --mpi-arg=--report-bindings --mpi-arg=--map-by --mpi-arg=socket --local-rss-limit-gib 180 --work "$runs/weak" --campaign weak --subdivisions 16 20 25 32 40 50 --ranks 4 8 16 32 64 128 --reference-mode mono_braess_tentative --modes mono_pressure_auto --timing-repeats 3 --timeout 650 > "$runs/weak-retry.log" 2>&1 || printf '%s\n' 'weak study had a failure'
set -- "$runs"/scale-n22/*/results.json
"$python" "$runs/benchmark_hybrid_retry.py" --receipt "$1" --executable build/release/eonsim --work "$runs/hybrid-128" --build-source "$remote" > "$runs/hybrid-128-retry.log" 2>&1
