> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Pinned svFSI import and pressure-time check

Reference repository: [SimVascular/svFSI](https://github.com/SimVascular/svFSI),
commit `7bdb74cdd517310d6bf32c0bb7d42072aeac8658`. The existing local repository
was read only; a clean git archive was exported and built separately. No
reference source was modified. `source.json`, `commands.json`, configure/build
logs and the original build helper preserve the exact provenance and options.
The source archive digest is recorded, while the upstream source itself and
the binary are not redistributed here.

The system GCC/GFortran/OpenMPI/OpenBLAS environment built Release with
`-fallow-argument-mismatch`, Trilinos disabled and system zlib. This environment
is separate from EONSim's PETSc lock. The actual solver binary hash is retained
in the successful attempt's `process.json`.

The exporter/auditor are checkpointed in EONSim `d280e7f`. Generator correction
`b9075f0` preserves solid volume tag20: the original prepared Gmsh solid used
tag10, inconsistent with EONSim's independent-domain configuration. That old
input is retained here; it was never run as a coupled EONSim case. The fluid-only
reference check is unaffected. Fresh coupled inputs use the corrected generator,
whose three geometry/export and three prior rigid-grid checks passed. The exported
linear elastic tube has R=1, outer radius1.2, L=12, E=1000, nu=.3, both densities
1 and fluid viscosity1. Here the solid is omitted and the fluid wall is fixed:
equal `.02+.01*sin(t)` pressure on both end caps gives **exactly zero velocity
and spatially uniform pressure**, independent of mesh accuracy.

## Actual discrete check

The successful `reference/uniform-pressure-s12-zlib` attempt used 325 nodes,
1296 tetrahedra, 100 steps over one period, generalized-alpha rho_infinity=.5,
one rank. All 100 output fields were read with VTK 9.6.1 and NumPy 1.26.4.
Maximum speed `2.50644e-15`; spatial pressure range `4.52879e-13`; difference
from the exact endpoint recurrence `4.60553e-13`; reconstructed stage/load
difference `1.06071e-13`. All four limits were `1e-9`.

The source increments global time before evaluating its Fourier pressure, but
interpolates pressure at alpha_f during assembly. Therefore the stored endpoint
pressure satisfies

```
alpha_f*p[n+1] + (1-alpha_f)*p[n] = P(t[n+1]), p[0]=0, alpha_f=2/3.
```

The measured first pressure is `.03094185779294`; interpreting it as the
continuous endpoint pressure would be wrong. The auditor verifies this entire
recurrence, not merely the sign or final snapshot. Sources at the pinned commit:
`Code/Source/svFSI/MAIN.f` (outer step/SETBCNEU), `PIC.f:PICI`,
`SETBC.f:SETBCNEUL`, `FFT.f:IFFT`, `INITIALIZE.f` (alpha weights).

The exporter now offers explicit `--stage-pressure`: Fourier initial time is
`(1-alpha_f)*dt`, so the endpoint-time read supplies `P(t_n+alpha_f*dt)`.
This is derived from the inspected integrator, not fitted to a comparison.
That new option's actual reference run is queued, **not passed by this archive**.
EONSim's first BE startup and the two codes' other discrete operators also
remain distinct. No elastic, MPI or spatial-accuracy acceptance is claimed here.

## Failed attempts retained

`attempt-observations.json` and the archive retain the original attempted inputs:

- Compact ASCII XML: the old parser failed to find the next tag.
- Line-separated ASCII: connectivity length mismatch.
- Multi-component ASCII connectivity: rejected by a general VTK reader before
  svFSI was launched; this workaround was abandoned.
- Standard uncompressed appended raw data: VTK passed, but svFSI reported
  expected block size1300 versus actual1299. A padding attempt did not fix it.
- Native zlib-compressed appended raw data: both VTK and svFSI passed, followed
  by the physical/discrete check above.

The exporter uses the last encoding, matching the pinned native writer.
Three Python geometry/Fourier tests passed, including independent surface
orientation, face-parent membership, divergence theorem and opposite interface
triangles. A general VTK reader independently checked all nine exported mesh
files. The failed svFSI runs returned exit code0; exit status must not be used
as an acceptance oracle. All failures remain failures.

## Replay

```sh
python cases/fsi/generate_pressure_tube.py --output /new/eonsim-case
python scripts/export_svfsi_tube.py --case /new/eonsim-case/case.json \
  --output /new/reference --hydrostatic-smoke
# In /new/reference, using the separately built, pinned executable:
/path/to/svFSI svFSI.inp
python scripts/analyze_svfsi_uniform_pressure.py --work /new/reference
```

The ordinary exporter needs only Python's standard library. The auditor needs
the separate NumPy/VTK environment. To reproduce the **new** stage-load check,
add `--stage-pressure` to export; do not rewrite an earlier input directory.

All 213 raw files were read back and SHA256-verified. `manifest.json` and
`archives.json` contain member and archive hashes. The archive includes the
actual output fields, input meshes and failed attempts, and is a local evidence
checkpoint only. The complete elastic comparison is still pending.
