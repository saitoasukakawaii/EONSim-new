# SOLVER-04：稳态流体 Schur/GAMG 网格测量

后续状态：SOLVER-04B 已补充每层 A 算子尺寸诊断，见 [实现与验证草稿](../../website/drafts/solver-level-dimensions.md)。下文原始测量没有该字段，不追补其未测数据；独立 PC 累计成本仍未实现。

日期：2026-10-30（Asia/Shanghai）；同步基线 a4957e0（PR #10 已合并）。
测量脚本提交 79eb826，求解器相对基线无修改；完整提交号与 executable SHA256 记录于 [results.json](data/schur-mesh-2026-10-30/results.json)。

## 问题与设置

目的：在现有算例上量化网格增加后的迭代和成本，不预设网格无关性。
使用 cases/fluid/steady.yaml 的单位立方体、Tet4/P1 等阶速度/压力与既有 SUPG/PSPG 实现；rho=1、mu=1、pressure_drop=1，稳态含对流。
内置边界在 x=0/1 施加抛物速度 u_x=y(1-y)/2，在 y=0/1 为零速度，在 z=0/1 约束法向速度；原点压力定标为 1。pressure_drop 参数不能直接视为离散输出压差精确等于 1。
初始内部未知量沿驱动默认零值，随后施加 prescribed。没有时间步或模型参数变化。

网格 subdivisions 为 2/4/6，节点 27/125/343，四面体 48/384/1296，代数 DoF 108/500/1372（含约束行）。
每个网格各用 1/2 rank：直接解一次作参考，Schur 三次独立进程重复；合计 24 次求解和 6 次预处理。
按固定顺序运行，无专门预热或随机化。直接解不是多次计时基准，本报告不据此计算 direct/Schur 加速比。

Release，GCC 15.3.0、PETSc 3.23.7、Open MPI 5.0.8、CMake 4.4.5；CPU 为 Intel Xeon Platinum 8573C，cgroup 配额 4 CPU、32 GiB；每 rank 的 OMP/OpenBLAS/MKL 线程均为 1。软件版本与 CPU 信息归档于 [environment.json](data/schur-mesh-2026-10-30/environment.json)。
SNES rtol=1e-10、atol=1e-12、max_it=30；字段使用现有默认验收。Schur 顶层 FGMRES 的默认 rtol=1e-9、atol=1e-13、max_it=500；FULL/SELFP 分解，速度/压力块 GAMG，粗层 GMRES/Jacobi，默认粗层 rtol=1e-10、max_it=200。配置来自固定版本 src/algebra/schur_solver.cpp 和 nonlinear_system.cpp；未放宽容差。

## 可复现命令与证据

```sh
source /workspace/.eonsim-tools/activate.sh
cmake --build --preset release --target eonsim --parallel 4
python3 scripts/profile_schur_mesh.py --executable build/release/eonsim \
  --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-schur-mesh
```

脚本要求 work 不存在，避免混合旧证据。归档的 [数据目录](data/schur-mesh-2026-10-30) 含 30 份原始日志、三个 YAML、三个网格、结果和环境 JSON。
JSON 保存全部命令、每次计时、层级、字段差、输入和可执行文件哈希。命令中的 /tmp 路径为本次工作目录，重跑可换路径；输入相对网格名可移植。VTU 和分区文件未入 Git，可通过脚本重建。

## 实测结果

solve 秒数为三次的中位数 [最小值, 最大值]；setup 为显式 Schur setup 中位数；RSS 为求解后各 rank 最大驻留内存采样的中位数，不是内存高水位或作业总内存。

| n | DoF | rank | 顶层累计 KSP 迭代中位数 | solve s | Schur setup s | RSS MiB | 对直接解最大节点字段差 |
|---|---:|---:|---:|---|---:|---:|---:|
| 2 | 108 | 1 | 25 | 0.006406 [0.006159, 0.007380] | 0.000582 | 26.83 | 7.472e-14 |
| 2 | 108 | 2 | 27 | 0.015055 [0.014197, 0.015061] | 0.001189 | 28.12 | 1.292e-13 |
| 4 | 500 | 1 | 31 | 0.025670 [0.023659, 0.026381] | 0.001140 | 27.99 | 3.881e-13 |
| 4 | 500 | 2 | 31 | 0.038243 [0.036961, 0.046289] | 0.003099 | 29.38 | 3.774e-13 |
| 6 | 1372 | 1 | 39 | 0.076670 [0.076430, 0.087778] | 0.002433 | 31.26 | 4.083e-12 |
| 6 | 1372 | 2 | 39 | 0.087477 [0.082622, 0.089555] | 0.002971 | 32.31 | 1.717e-12 |

24 次求解全部成功，Schur 与同网格同 rank 直接解差不超过 4.084e-12（检查阈值 2e-8）；直接解 1/2 rank 最大差为 5.163e-15。
比较按 owner 与原始 mesh_node_id 对齐，遍历 VTU 的物理点字段，剔除编号/owner 元数据，检查形状与有限值。各字段单位不同，表中最大绝对差是回归指标，不是无量纲误差范数。压力使用相同定标，不另做均值平移。

## 层级与成本解释

所有样本可见速度、压力 GAMG 各一个 coarse 和一个 down1；粗层 GMRES/Jacobi，下平滑 Chebyshev/Jacobi。以下为每组首次运行 rank 0 的最后一次子求解迭代，不是累计迭代：

| n | rank | 顶层最后一次 | velocity coarse 最后一次 | pressure coarse 最后一次 |
|---|---:|---:|---:|---:|
| 2 | 1 | 6 | 1 | 1 |
| 2 | 2 | 6 | 3 | 1 |
| 4 | 1 | 7 | 8 | 3 |
| 4 | 2 | 7 | 7 | 3 |
| 6 | 1 | 8 | 9 | 8 |
| 6 | 2 | 8 | 9 | 6 |

完整每 rank、每次层级在 JSON/日志中。当前诊断未输出每层矩阵尺寸或独立 PC setup 累计时间，不能从最后一次粗层迭代分摊总成本。
solve 包含初始装配、显式 Schur setup 和 SNESSolve；assembly 包含 ghost；linear 包含 PC setup/内层求解。各计时按 rank 取最大且存在嵌套，不应相加；进程 wall 还含 MPI 启动、输入和输出。首次显式 Schur setup 不代表全部预条件准备成本。

## 结论与限制

- 本次单 rank 累计迭代随 n 从 25 增至 31、39；双 rank 从 27 增至 31、39，没有证据宣称网格无关收敛。
- 三个小网格上双 rank 的 solve 中位数均高于单 rank。这里不据此判断更大问题或跨节点效率，也不作瓶颈归因。
- direct/Schur 一致只证明离散代数求解对照。n=6 日志的速度 L2 误差约 0.007574、divergence L2 约 0.018998、输出压差约 0.675767；代数残量很小不意味着离散误差很小。本轮没有重新开展空间收敛阶研究。
- 未运行 FSI、4 rank、跨节点、全套 CTest，未更改 PETSc 或 C++ 源码。本机小规模结果不能作为生产 HPC 验收。

后续更大网格或 FSI 研究应先确认目标精度与资源预算；若要优化粗层，需要补每层尺寸和累计成本，而不是从本表直接调整预条件器。

## 验证记录

脚本运行退出 0；有效日志解析通过，缺报告、NaN 计时、负 SNES reason 三种变异被拒绝；节点集合不符、非有限字段、超阈值字段差三个负对照被拒绝。Release 构建退出 0（no work to do）。

## 参考资料

- [既有 B5 精度/性能记录](../development/B5_ACCURACY_AND_PERFORMANCE.md)：不同环境和算例的数据，不与本表直接计算加速比。
- [PETSc PCFIELDSPLIT](https://petsc.org/release/manualpages/PC/PCFIELDSPLIT/)
- [PETSc PCGAMG](https://petsc.org/release/manualpages/PC/PCGAMG/)
