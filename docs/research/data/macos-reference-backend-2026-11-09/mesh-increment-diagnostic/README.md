# Mesh increment evaluation diagnostic (not adopted)

Base svFSI7bdb74cdd517310d6bf32c0bb7d42072aeac8658. Source inspection:
PIC.f PICI156 forms Dg=(1-af)*Do+af*Dn; MESH.f CONSTRUCT_MESH92 then
subtracts Do. The separate derivative evaluates af*(Dn-Do) locally instead.
It keeps old-configuration coordinates x+Do, generalized-alpha tangent,
all tolerances, and original stopping branches. It does not include the
strict-stop patch and cannot repair coarseN800's absolute-stop defect.

This is a cancellation hypothesis, not an established cause or production
adoption. Configure81584 passed with CMake3.31.10, GNU Fortran16.2, Release,
Trilinos13.2, systemzlib. Build16572 completed0. Diagnostic controller10552 now runs only fineN800401..540 from the verified original step400,
CG/FSILS mesh and ILUT FSI,1rank/1thread,2GiB RSS/20GiB free/1800s bounds.
It retains full per-step fields/native checkpoints and external convergence
audits. Diagnostic10552 completed0: all280 final equation rows401..540 pass original relative tolerances; maximumFS9.3e-12/MS8.3e-11, no cap,379.78s/275628032B peak RSS. Field/native comparison4370 completed0:140 pairs pass original bounds, maxnode3.15944e-19/P1mass5.00108e-17/history1.63005e-16; exact time and saved norms. Consumed raw files are SHA-bound in field-diagnostic.json. No old-workspace data used.

Build command: `build/analysis-venv/bin/cmake --build
build/recompute-20261109/svfsi-mesh-increment-build --parallel 2`.

Normal coarseN400 startup/loaded/replay equivalence55589 is now running in a separate folder, using unchanged thresholds. Its50 pairs and independent native review passed; see ../mesh-increment-equivalence/. No production adoption.
