# Pinned svFSI rebuilt and stage-pressure checked on macOS

The clean upstream commit is `7bdb74cdd517310d6bf32c0bb7d42072aeac8658` from
`https://github.com/SimVascular/svFSI.git`. The source was not modified; binary
hash and actual environment are in [source.json](source.json). This is a fresh
native arm64 build, not the old Linux executable or a recovered trajectory.

System CMake 4.4.3 rejected the upstream minimum-version compatibility policy.
That [failed configuration](configure-cmake4-failed.log) is retained. A separate
project-local Python environment supplied CMake 3.31.10; no upstream policy was
edited. Actual successful commands from repository root:

```sh
build/analysis-venv/bin/cmake -S build/recompute-20261109/svfsi-source/Code -B build/recompute-20261109/svfsi-build-cmake3 -DCMAKE_BUILD_TYPE=Release -DCMAKE_Fortran_COMPILER=/opt/homebrew/bin/gfortran -DCMAKE_Fortran_FLAGS=-fallow-argument-mismatch -DSV_USE_TRILINOS=OFF -DSV_USE_SYSTEM_ZLIB=ON
build/analysis-venv/bin/cmake --build build/recompute-20261109/svfsi-build-cmake3 --parallel 2
python3 cases/fsi/generate_pressure_tube.py --output build/recompute-20261109/reference-smoke-case --sectors 12 --radial 2 --axial 12 --steps-per-cycle 100 --cycles 1
python3 scripts/export_svfsi_tube.py --case build/recompute-20261109/reference-smoke-case/case.json --output build/recompute-20261109/reference-uniform-stage --hydrostatic-smoke --stage-pressure
```

The run executed `../svfsi-build-cmake3/bin/svFSI svFSI.inp` inside the new
`reference-uniform-stage` directory, with one rank and OMP/OpenBLAS/Accelerate
threads each limited to one. Actual audit:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 build/analysis-venv/bin/python scripts/analyze_svfsi_uniform_pressure.py --work build/recompute-20261109/reference-uniform-stage
```

All 100 output states were read. [The audit](uniform-analysis.json) passes the
unchanged `1e-9` limits: maximum velocity `2.26e-15`, pressure spatial range
`3.92e-13`, endpoint recurrence error `4.00e-13`, stage-load error `1.07e-13`.
This confirms the exact discrete pressure-time convention and input/output
path on this build. It does not qualify elastic dynamics, mesh refinement,
long-time periodicity or multi-rank reference performance.

[uniform-stage-raw.tar.gz](uniform-stage-raw.tar.gz) contains all 121 original
input/output/log/audit files (567,100 compressed bytes).
[The manifest](manifest.json) lists every SHA256 and the archive hash. Every
archive member was read back and verified; the archive is actual raw evidence,
not a pointer to an omitted archive. Build warnings remain visible in
[build.log](build.log); no errors occurred in the successful build.
