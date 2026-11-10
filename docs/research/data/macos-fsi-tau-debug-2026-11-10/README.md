# FSI 稳定化时间尺度 Debug 验证

源码基线bb20088c2916484ef1cf0c0e281d79c521fc5bf4，macOS arm64，应用Debug、PETSc3.25.6，1/2rank、每rank单线程。增量构建会话18201退出0；功能会话46780退出0；旧检查点续算及捕获退出0。原scalar_p2.cpp缩进警告保留。未覆盖运行中的冻结生产binary。

实际命令：

```sh
cmake --build build/macos-debug --target eonsim -j 2
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PETSC_OPTIONS='-mat_mumps_icntl_20 0' build/analysis-venv/bin/python tests/verify_fsi_stabilization_time.py --executable build/macos-debug/eonsim --baseline build/macos-release/eonsim --mpiexec /opt/homebrew/bin/mpiexec --work build/recompute-20261109/fsi-tau-debug-check
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PETSC_OPTIONS='-mat_mumps_icntl_20 0' build/analysis-venv/bin/python build/recompute-20261109/check-fsi-tau-debug-default-restart.py
build/analysis-venv/bin/python build/recompute-20261109/capture-fsi-tau-debug.py
```

BE默认与显式同尺度差异1.3877787807814457e-17；改变尺度的场差异0.047167415392552814。1/2rank差异1.3877787807814457e-17。BE/BDF2/generalized-alpha同设置续算差异均0，三种默认路径与旧Release生产程序差异均0。旧生产检查点由新Debug读取的generalized-alpha续算差异0。非法值、固定tau冲突、续算改变/移除时间尺度均拒绝；每组实际时间仍8步、dt=.02。

851原始文件完整SHA清单；730838字节本地归档逐成员解码SHA核对通过，原文件保留。binary/source/config/log绑定见manifest及CMakeCache。测试覆盖小算例的默认行为、显式干预、重启、输入拒绝及MPI一致性，不替代长程误差预算。主锁PETSc3.23.7仍未验证，不能用本机3.25.6代替。复用已有稳定化文章，无新算法结论，未push/PR。
