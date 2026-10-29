# P8 小规模并行性能基线

测量日期：2026-10-29。环境为本机 Linux/WSL、GCC 13.3、Release、PETSc 3.23.2 优化构建、
OpenMPI 4.1.6；本机可用 24 个逻辑 CPU，本次最多使用 4 rank。
每 rank 的 OMP/OpenBLAS/MKL 线程数均为 1；`SUPERLU_ACC_OFFLOAD=0`、`-device_enable none`。
这是 CPU 路径的单次运行记录，不是 GPU、生产规模或统计重复实验。

两个真实耦合算例均使用 4³ 细分，每个域 125 节点/384 Tet4，运行前 5 个 BE 步。
刚体系统消元后 511 DoF、30,475 个结构非零元；超弹性双域系统 730 DoF、60,796 个结构非零元。
直接解为单个 SuperLU_DIST；块解为 FGMRES＋乘法 field-split，flow/mesh/structure 使用 ASM＋局部 ILU，
rigid 使用 Jacobi。两者保留相同 operator、物理模型与非线性容差。

复现：

```bash
python3 scripts/benchmark_fsi.py --executable build/release/eonsim \
  --mpiexec /usr/bin/mpiexec --work results/benchmark --subdivisions 4
```

输出各次完整日志、VTU 与 `summary.json`。下表 solve/assembly/ghost 是各时间步最大 rank 耗时之和；
assembly 包含残量/Jacobian 装配与同步，ghost 是其中的子集，不能相加解释总时间。
wall 包含进程启动、输入、输出和其他准备。线性迭代是 5 步累计，直接解也按 PETSc 计数。
峰值 RSS 使用 Linux `getrusage(RUSAGE_SELF).ru_maxrss`，包含动态库，报告所有 rank 中的最大值；
各 rank 峰值之和不等于同一时刻的总峰值，完整数据仍保存在 JSON。

| 算例 | rank | 求解器 | wall(s) | solve(s) | assembly(s) | ghost(ms) | 线性迭代 | 最大 rank 峰值 RSS(MiB) |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| 刚体 | 1 | direct | 0.683 | 0.218 | 0.083 | 0.130 | 10 | 329.1 |
| 刚体 | 1 | block | 0.569 | 0.087 | 0.077 | 0.037 | 140 | 246.9 |
| 刚体 | 2 | direct | 0.743 | 0.221 | 0.054 | 0.123 | 10 | 330.3 |
| 刚体 | 2 | block | 0.509 | 0.070 | 0.055 | 0.096 | 144 | 246.0 |
| 刚体 | 4 | direct | 0.842 | 0.287 | 0.044 | 0.166 | 10 | 328.6 |
| 刚体 | 4 | block | 0.569 | 0.068 | 0.047 | 0.193 | 152 | 245.4 |
| 超弹性 | 1 | direct | 0.811 | 0.340 | 0.158 | 0.132 | 15 | 333.2 |
| 超弹性 | 1 | block | 0.638 | 0.184 | 0.162 | 0.063 | 217 | 248.2 |
| 超弹性 | 2 | direct | 0.875 | 0.334 | 0.115 | 0.143 | 15 | 331.1 |
| 超弹性 | 2 | block | 0.601 | 0.148 | 0.122 | 0.110 | 231 | 250.4 |
| 超弹性 | 4 | direct | 0.984 | 0.409 | 0.099 | 0.199 | 15 | 329.6 |
| 超弹性 | 4 | block | 0.638 | 0.127 | 0.095 | 0.161 | 286 | 246.4 |

在这个很小的规模上，块解减少了 factorization 成本，但 rank 增加也带来通信和启动开销；
总 wall 时间不呈现稳定线性加速。不能将该表外推到大规模网格，块内局部 ILU 也未证明网格无关收敛。
FSI 流体/ALE 局部中心差分仍占装配成本，后续性能工作应在扩大真实问题后再确定优先级。

## 相关可靠性检查

- Debug/Release 均通过 13 项 CTest；恢复测试覆盖 transient 流体、线弹性撤载、刚体 FSI、线弹性与超弹性 FSI。
- 1/2 rank 的 checkpoint 第 3 步恢复到最终步与连续运行逐字段比较；不匹配参数、rank 数和缺失 rank 文件正确失败。
- 有限变形 FSI 的整体直接解与块解在 1/2/4 rank 上一致，逐字段比较阈值 2e-8。
- 默认块解的针对性 Valgrind 检查（两步，禁用设备初始化，检查非法读写）为 0 errors；未宣称全部依赖库无泄漏。
- 本机多个 SuperLU_DIST LU 子块曾在销毁时触发 communicator 重复释放：
  Valgrind 记录同一对象先由 `MatDestroy_SuperLU_DIST` / `superlu_gridexit` 释放，
  后由 `Petsc_Superlu_dist_keyval_DeleteFn` 再次访问。默认 ASM 块解避免该路径，未修改系统 PETSc。
