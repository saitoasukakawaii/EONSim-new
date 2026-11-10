# FSI 显式稳定化时间尺度诊断

基线提交 `371233305833ccb9c523b62a77b4ec989a568ad5`，本目录 source.patch 和测试源码固定本次实现。生产 binary 未覆盖。

`fsi.stabilization_time_scale` 仅替换 SUPG/PSPG tau 分母中的有效时间，不改变实际步长、流体惯性、固体或 ALE 时间映射。必须有限且正；与固定完整 tau 互斥；显式值进入 checkpoint 签名，缺省不改变旧签名。

## 实际验证

macOS arm64、应用 Release、PETSc 3.25.6、单线程、1/2 rank。实际命令：

```sh
cmake -S . -B build/macos-fsi-tau-diagnostic -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DCMAKE_PREFIX_PATH=/opt/homebrew -DEONSIM_PETSC_ROOT=/Users/chen/software/petsc-3.25.6-install
cmake --build build/macos-fsi-tau-diagnostic --target eonsim -j 2
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PETSC_OPTIONS='-mat_mumps_icntl_20 0' build/analysis-venv/bin/python tests/verify_fsi_stabilization_time.py --executable build/macos-fsi-tau-diagnostic/eonsim --baseline build/macos-release/eonsim --mpiexec /opt/homebrew/bin/mpiexec --work build/recompute-20261109/fsi-tau-option-check
python3 tests/test_ci_selection.py
```

构建与功能检查退出0，选测映射26项通过；重新配置后 CTest inventory 注册 fsi_stabilization_time（只检查注册，没有再重复运行）。原有 scalar_p2.cpp 编译警告保留于日志。

- BE 缺省与显式同尺度差异1.38778e-17；改变尺度产生0.0471674的实际场差异。
- 相同显式尺度1/2 rank差异1.38778e-17。
- BE/BDF2/generalized-alpha各自checkpoint续算差异0；实际时间网格仍为8步、每步0.02。
- 三种格式缺省路径与原生产程序差异均0。
- 非法值、与完整tau冲突、续算改变/移除尺度均拒绝。
- 补充旧生产binary写checkpoint、新诊断binary读取，generalized-alpha续算差异0；具体命令与两binary哈希见 old-checkpoint-summary.json，运行脚本与日志一并保存。

851个实际输入/日志/场/检查点文件压缩为732794字节，逐成员解码SHA核对通过，完整清单见 manifest.json；归档仅在本地build，原始展开文件保留。报告不声称远端可取得本地原始归档。

Debug和主锁PETSc3.23.7本次未运行；没有新增Jacobian公式，tau仍在时间步内冻结。当前功能检查不是长程误差预算，也没有改变默认生产方法或放宽10%门槛。下一步用相同物理条件的长程显式干预分解tau时间项影响。
