# HPC-01B：装配阶段基线

日期：2026-10-30（Asia/Shanghai）。main 基线 7f2bc51（PR #13 合并），测量脚本提交 d1708e1。
本轮只扩展脚本汇总与数据检查，不改 C++、物理模型、容差或 CMake。

## 问题、环境与复现

用新计时定位后续调查范围，分清回调与最终装配；不从一次计时接线推断性能改善。
沿用 [SOLVER-04 设置](SCHUR_MESH_PROFILE_2026-10-30.md)：单位立方体稳态流体、rho=mu=1、既有抛物速度边界及原点压力定标、Tet4/P1 与 SUPG/PSPG。
网格 n=2/4/6，108/500/1372 DoF（含约束行）；每个 1/2 rank 配置运行一次直接参考和三次 Schur，总计 6 次参考、18 次重复。
SNES rtol=1e-10、atol=1e-12、max_it=30；Schur FGMRES rtol=1e-9、atol=1e-13，FULL/SELFP、GAMG、粗层 GMRES/Jacobi。完整输入和全部命令保存在 [results.json](data/assembly-phase-2026-10-30/results.json)。

Release、GCC 15.3.0、PETSc 3.23.7；沿用已验证的 Open MPI 5.0.8 工具链。CPU Intel Xeon Platinum 8573C，cgroup 4 CPU/32 GiB，OMP/OpenBLAS/MKL 每 rank 单线程。
CPU 与本次采集的软件版本见 [environment.json](data/assembly-phase-2026-10-30/environment.json)。没有专门预热、随机顺序或独占节点控制；每组仅三次。

```sh
source /workspace/.eonsim-tools/activate.sh
cmake --build --preset release --target eonsim --parallel 4
python3 scripts/profile_schur_mesh.py --executable build/release/eonsim \
  --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-assembly-baseline
```

work 必须是新目录。原始证据包含 30 份日志及结果/环境 JSON；网格由脚本固定生成，YAML 内容与网格哈希记录在 JSON，未重复提交上轮相同网格。
source_commit、可执行文件 SHA256、CPU/内存限制、每次层级及完整计时均已记录。历史 SOLVER-04 数据不用于跨提交加速比，本轮也未测新增时钟读取的开销。

## 统计与计时口径

表内单位均为 ms，格式为中位数 [最小值, 最大值]，每组 n=3。每个样本的时间已按 rank 取最大，再跨重复统计。
字段定义以 [L2 计时契约](../architecture/L2_DISCRETIZATION_AND_OPERATORS.md) 为准：callback 包含物理回调和插入；failure_sync 是错误状态规约；assembly_finalize 包含原始 Vec/Mat 最终装配的本地工作与通信；constraint 是约束替换。
只累计成功评价，并在 SNESSolve 返回时冻结，不含最终验收/反力重装配。样本中 domain_rejections 全为 0。ghost 是已有累计字段。

| 网格 n | rank | assembly | callback | failure_sync | assembly_finalize | constraint | ghost |
|---|---:|---|---|---|---|---|---|
| 2 | 1 | 1.358 [1.317, 1.430] | 1.212 [1.114, 1.289] | 0.002 [0.002, 0.003] | 0.064 [0.056, 0.076] | 0.021 [0.020, 0.095] | 0.037 [0.036, 0.039] |
| 2 | 2 | 1.860 [1.760, 2.024] | 0.496 [0.486, 0.576] | 0.033 [0.026, 0.192] | 1.058 [1.038, 1.152] | 0.240 [0.230, 0.336] | 0.075 [0.063, 0.075] |
| 4 | 1 | 8.481 [8.465, 9.219] | 8.255 [8.254, 8.618] | 0.007 [0.006, 0.007] | 0.094 [0.090, 0.364] | 0.044 [0.042, 0.048] | 0.043 [0.041, 0.046] |
| 4 | 2 | 8.463 [7.858, 9.598] | 4.046 [3.770, 5.129] | 0.555 [0.149, 1.640] | 3.954 [3.784, 4.098] | 0.585 [0.571, 0.643] | 0.087 [0.065, 0.276] |
| 6 | 1 | 26.029 [24.610, 26.090] | 25.487 [24.085, 25.550] | 0.010 [0.008, 0.011] | 0.138 [0.132, 0.142] | 0.085 [0.081, 0.087] | 0.049 [0.046, 0.049] |
| 6 | 2 | 24.684 [21.865, 25.095] | 13.779 [12.449, 13.973] | 1.557 [0.822, 2.125] | 9.609 [8.435, 10.729] | 1.218 [1.066, 1.330] | 0.156 [0.090, 0.358] |

这些阶段有嵌套关系，各列最大值还可能来自不同 rank；不得将列相加或计算“百分比之和”当作时间分解。清零等开销也不在四个新增子区间中。

## 数值与解析检查

所有 24 次求解成功，且没有拒绝试探点。Schur 对同网格同 rank 直接解最大节点字段差为 4.0834e-12，直接解 1/2 rank 差为 5.1626e-15；阈值仍为 2e-8，按 owner 和原始节点 ID 对齐，不调整压力定标。
这只是离散解一致性，不证明连续方程精度；各字段单位不同，最大绝对差不是无量纲范数。

脚本现在要求四个阶段字段齐全，并拒绝 domain_rejections 非零的样本以保持本研究口径；这不表示拒绝试探点是求解器缺陷。若研究拒绝成本需另设测量协议。
有效日志通过；缺失 callback、NaN、阶段大于 assembly、非零 domain_rejections 四个负对照均被拒绝。已有有限性、层级、直接解对照检查继续执行。

## 结论与后续边界

- n=6 的 callback 中位数从单 rank 25.487 ms 降到双 rank 13.779 ms；最终装配从 0.138 ms 增至 9.609 ms。相应 assembly 仅从 26.029 ms 降至 24.684 ms。
- 这提示在当前小案例上，进一步减少本地回调工作未必能转化为同等总时间下降。最终装配包含本地整理、同步等待和数据交换，不能将 9.609 ms 全部称为网络时间。
- 错误状态同步时间和样本范围体现了等待与调度波动，但没有独占资源或更细 MPI 事件证据，不能据此推断负载不均的具体来源。
- 本轮不改变稀疏插入策略，不实施 COO 或缓存重构。HPC-01 尚缺纯 kernel/插入分离；如要优化，下一步应在明确目标规模下补装配事件/远程贡献证据。

未运行全套 CTest、FSI、跨节点测试或计时开销 A/B 实验。不将三次小网格测量外推到生产 HPC。

## 参考资料

- [PETSc performance manual](https://petsc.org/release/manual/performance/)
- [MatAssemblyBegin](https://petsc.org/release/manualpages/Mat/MatAssemblyBegin/)
- [MatAssemblyEnd](https://petsc.org/release/manualpages/Mat/MatAssemblyEnd/)
