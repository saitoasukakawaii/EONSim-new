# FSI-PERF-02：精确图、贡献压缩、单元批次与求解器会话

本轮在已合并 [PR #51](https://github.com/saitoasukakawaii/EONSim-new/pull/51) 上完成已识别、适合当前 CPU/MPI 路径的优化，交付 [PR #52](https://github.com/saitoasukakawaii/EONSim-new/pull/52)。
默认 AIJ 装配配对中位数下降 **9.47%–20.34%**；最终 COO 的一次性装配初始化下降 **20.17%–47.72%**，峰值 RSS 下降 **2.13%–8.89%**。
这些数值分别比较各后端与上一轮相同后端，不能相加，也不能将阶段下降当作整次加速。

当前保持默认 AIJ、默认残量 COO、合资格的默认 Newton 会话复用和每 rank 一个单元线程。
矩阵 COO 与多线程仍显式开启。细网格单 rank 的 COO 整次 wall 范围跨零；两线程的 wall 范围也均跨零。
默认细网格单 rank 的峰值 RSS 约增加 4.01%，因此没有声称所有模式都省内存或普遍加速。

## 1. 固定来源与执行顺序

| 对象 | 实际来源 |
|---|---|
| 开发起点 | main `4e25e2a7b1aa921dc473fe09cd5f9b3f09d4645f`，已核实 PR #51 合并 |
| 实际基线二进制构建源码 | `df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e`；与上述 main 的 src/include/CMake/cmake/env 及 cloud 构建入口无差异 |
| 首轮实现、13 项定向验收、默认与线程性能 | `7f3d12ed6d0a1abc67d5f5606bf644b142a3197f` |
| 行分桶修复、受影响复验与最终 COO 性能 | `2b0b30bc2e1b036b8b97c9424cc6d41abd5af105` |
| 基线二进制 SHA-256 | `b782a4e043b5e91a4e53652ce325ccf79bfac7696522f90a50f61f6fb3f6d9a0` |
| 首轮候选二进制 SHA-256 | `109078ae403dbf2708febf9279cd368c198d51f0b155ffeb604c9a7fb87364cb` |
| 最终候选二进制 SHA-256 | `d3fc4988ade068fcc2a6141635085efd8bc6cfc489da3ce2aa1a575836c6bfbb` |
| 性能驱动内容 SHA-256 | `ec96b06dc6b6378877a44a6c88d946d8834be1c1a6766b97e8c6aefb8bc61e5c`，两源码版本相同 |

两次源码均先推送到远端，再编译、验证和测量；本地构建收据与全部 campaign 均记录干净工作树。
2b0 只修改 `if(coo)` 内的一次性坐标合并，没有修改默认/线程执行路径。
默认与线程的测量明确引用 7f3，本次未重复执行；相关 FSI 对照在 2b0 重新通过。
两版二进制分别固定保存，后续构建覆盖 build 路径时仍能通过原始 SHA 验证测量对象。
[来源核对](baseline-equivalence.json) · [完整统计与元数据](performance-summary.json)。

## 2. 已完成的优化和适用判断

| 优化项 | 本轮结果 | 正确性与成本边界 |
|---|---|---|
| 默认稀疏图 | 默认 PREALLOCATOR 和 COO 共用五个物理耦合块，分别投影 test rows / trial columns | 保留移动 RCR 的面积导数、接口 alias 和 owned 对角；不以当前数值零推断结构 |
| 局部 COO 去重 | 原贡献 K 映射到本 rank 唯一坐标 U；按局部行分桶、桶内列排序 | 保留原 contribution→slot 和浮点累加顺序；无全局尺寸数组，释放已用完的 K 项临时行 |
| 固定残量 COO | 默认批量发布固定残量贡献，准备实际回调 Vec | 包括 SNES line-search work Vec、重复/负行、remote-only 和空 rank；失败同步后才发布 |
| 单元核 | 线性参考 mesh 方程与解析压力面面积导数移出流体 AD | 保留全部 28 个导数列、当前几何/metric、面有效性与零载荷检查 |
| 有界线程批次 | `-fsi_threads N`，64 单元批次；OpenMP 为可选依赖 | worker 只运行纯核和私有写入；PETSc/MPI、按原顺序 scatter 和异常传播在主线程 |
| 求解器会话 | SNES/KSP/PC、field/diagnostic 缓冲跨成功 solve 复用 | 配置/options/约束行变化、失败或不合资格则共同重建；每次刷新 Jacobian 和数值 PC |
| 约束与末端通信 | owned 约束直接替换数组；全局零约束跳过 MatZeroRows；普通双 stash 的 Begin/End 交错 | 不改变约束列导数与原始反力，不宣称已有 ghost/单元计算重叠 |
| BAIJ | 完成适配性评估，本轮不采用整体 BAIJ | reduced 编号混合 7/3/部分节点分量、接口 alias、单值 body/port；需要额外 padding/重排，未实测声称更慢 |
| interior/halo 双阶段回调 | 完成成本评估，本轮不新增 | 上一轮细网格双 rank ghost/solve 中位数仅 0.023%（默认）/0.015%（COO）；证据不支持增加当前复杂度 |

上述判断关闭当前已识别的适用优化项；没有把 GPU、matrix-free、在线重分区或多节点扩展性写成已实现。
[算子契约](../../../architecture/L2_DISCRETIZATION_AND_OPERATORS.md) ·
[并行/内存契约](../../../architecture/L2_PARALLEL_MEMORY_AND_BACKENDS.md) ·
[halo 只读成本复核](overlap-review.json) ·
[未发布算法草稿](../../../../website/drafts/fsi-performance-completion.md)。

## 3. 数值验收

PETSc **3.23.7 Release**，Open MPI 5.0.8、GCC 15.3.0、SuperLU_DIST 9.1.0。
首轮实际执行 **13/13** 定向 CTest，0 failed/skipped/timeout，构建 43.153 s，CTest 调用 73.414 s。
行分桶修复后只执行受影响的 `fsi_coo_verification`，**1/1** 通过，构建 26.815 s，CTest 调用 9.151 s。
后一次是同一检查的复验，不能称为 14 项不同的测试；未重跑无关检查。

| 覆盖 | 证据 |
|---|---|
| 求解器生命周期，1/2 rank | 普通/双 COO、数值因子刷新、约束值变化保持复用、约束支撑/config/options 改变重建、fatal/StepRejected/真实线搜索拒绝恢复 |
| collective 保留/销毁 | 仅 rank 0 设置 `-nonlinear_reuse false` 后连续求解，验证所有 rank 共同释放与 generation 递增 |
| FSI 后端与线程 | 31 条命令含 1 个预期失败控制；刚体、共享弹性、独立双域 Neo-Hookean、固定/移动 RCR、1/2 rank、2 单元线程、retry/restart |
| 默认与 COO 图 | 对应案例唯一 nnz 相等，数值插入无额外 malloc；完整移动 RCR Jacobian FD 分别为 1.98523e-8 / 1.98495e-8 |
| 局部导数 | 48 个方向差分最大相对误差 2.23866e-10；独立 mesh 块、24 个面排列及几何拒绝用例通过 |
| FSI 字段与历史 | 最大 owned field 差 4.716782520119978e-13；最大归一化 history 差 5.920877545347623e-14 |
| 共享代数与语义 PC | fluid COO 1/2/4 rank、solver failures、metric、时间重试、nodal/twolevel retry 和 PC restart；restart 31 cases 最大 direct_error 3.3710811919718253e-12 |

7f3 和 2b0 保存的 FSI 结果 JSON 中，107 个共有数值摘要一致；这次对比是只读后处理，没有新增求解。
[首轮摘要](validation-summary.json) · [修复复验摘要](validation-bucket-summary.json) ·
[首轮原始收据](release-summary-7f3.json) · [修复原始收据](release-summary-2b0.json)。

实际命令如下，选测 JSON 已单独保存：

```bash
OMPI_MCA_smsc=^cma bash scripts/cloud/run.sh 3.23.7 release explicit \
  /workspace/scratch/6d25aa929185/pr42/.cloud \
  /workspace/scratch/d56ec93a621c/perf2-tests.json
# 2b0 仅把最后一项改为 perf2-bucket-tests.json
```

7f3 的 [源 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45644776027)
在 PR merge commit `9393f27daa8a1b03b7f4843e0706e885c81e03b6` 实际执行 **51/51 Release** 和 **65 项 Python** 检查，通过且未复用历史数值项。
[CI 源收据](ci-source-7f3.json)列出每项原始来源。
2b0 的 [源 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45649236866)
在 PR merge commit `a071ed230ba3fe80ac2f56c33e8075a93c5bd5d3` 实际 **28/28 Release、6 项 Python** 通过；
另 **23 项复用 7f3 的成功证据，本次未运行**，总覆盖 51 项。[修复 CI 源收据](ci-source-2b0.json)保留每项来源。
两次源 CI 的选测、Release、证据收据和网站检查均成功；文档/归档后续提交依既有规则复用相容证据。
本地未运行默认全套、Debug 或 PETSc 3.19.6；远端对应手动 job 跳过。

## 4. 性能实验方法

同一共享 Linux 主机，CPU 标识 Intel Xeon Platinum 8573C，进程可见 9 个 CPU，未证明独占物理核。
两套独立流固网格：n4 为 **771 单元 / 703 DoF**，n8 为 **6,147 单元 / 5,367 DoF**；各取 1/2 MPI rank。
使用相同输入和分区、20 个 BE 接受步、dt=0.02、相同直接解与验收门槛。
双方固定 PREONLY/LU/SuperLU_DIST，均开启 solver_report、linear_report、fsi_assembly_report，不开启 log_view。
所有 OpenMP/BLAS 依赖库线程固定 1；只有 `-fsi_threads` 控制单元 worker。
线程对照双方均使用 `--bind-to none`，不把额外依赖库线程或不同绑核策略计作单元并行收益。

每组 1 对预热 + 3 对交替测量。最终三组 campaign 合计 **80 次运行、1,600 个接受步**，
其中正式样本 60 次 / 1,200 步、预热 20 次 / 400 步；另保留中间 COO 的 32 次 / 640 步作为回退记录。
每步均为 2 次 SNES、2 次累计 KSP 修正，逐步时刻和迭代轨迹一致。
全部已保存的两域字段、ghost、CSV 历史、字段接受和真实线性残量均有检查。
最终默认/COO/线程最大字段差分别为 **6.661338147750939e-16 / 4.440892098500626e-16 / 0**，
最大 history 差分别为 **2.273355221146724e-15 / 2.609024107869118e-15 / 0**。
每次现代版本运行首步新建、后 19 步复用，generation 保持 1；数值矩阵与 PC 仍更新。

以下是 **三对相对变化的中位数 [最小, 最大]**，负数表示降低；范围不是置信区间。
它不同于“双方中位数的比值”，不能用绝对中位数重新相除替代。
`assembly` 含核、插入/归并与相关同步；`solve` 还含线性求解等。
`initialization_*` 仅记录一次性的 pattern/plan/system 准备，不是完整进程启动。
`wall` 独立包含启动、未细分准备、求解、输出和退出；各阶段取最大 rank 且可能重叠，不可相加当作 wall。

### 4.1 默认 AIJ：上一轮默认 → 本轮默认

| 网格 / MPI ranks | 装配时间变化 | 求解时间变化 | 整次 wall 变化 |
|---|---:|---:|---:|
| n4 / 1 | -15.00% [-16.24, -12.78] | -16.39% [-18.21, -8.87] | -12.39% [-15.12, +0.74] |
| n4 / 2 | -9.47% [-16.74, -5.49] | -2.54% [-2.96, +2.67] | -0.89% [-6.89, +5.50] |
| n8 / 1 | -20.34% [-23.81, -16.11] | -13.24% [-17.84, -1.55] | -12.53% [-16.56, -0.57] |
| n8 / 2 | -18.95% [-25.33, -7.68] | -8.89% [-17.47, +20.22] | -8.25% [-17.69, +18.36] |

| 网格 / MPI ranks | 一次性装配初始化变化 | 最大 rank 峰值 RSS 变化 |
|---|---:|---:|
| n4 / 1 | -19.92% [-22.52, +53.31] | +0.11% [+0.08, +0.19] |
| n4 / 2 | -9.70% [-29.02, +15.47] | -1.64% [-1.71, -0.20] |
| n8 / 1 | -6.80% [-38.70, +12.37] | +4.01% [+4.00, +4.07] |
| n8 / 2 | -32.69% [-51.28, -13.66] | -7.45% [-9.07, -7.35] |

默认的结构 nnz 在 n4 由 **36,643→27,226（−25.70%）**，n8 由 **364,635→260,010（−28.69%）**。
两种 rank 数均一致，等于当前 COO 的唯一图；`matrix_mallocs=0`、`nnz_unneeded=0`。
四组 assembly 的全部配对均下降；整次 wall 只有细网格单 rank 的范围全部为负。
细网格单 rank RSS 的配对中位数增加 **4.01%**，双 rank 下降 **7.45%**。
图更小并不意味着所有工作缓冲和总进程峰值都更小。

### 4.2 最终 COO：上一轮 COO → 本轮行分桶 COO

| 网格 / MPI ranks | 装配时间变化 | 求解时间变化 | 整次 wall 变化 |
|---|---:|---:|---:|
| n4 / 1 | -13.82% [-16.07, -5.08] | -13.67% [-15.86, -13.19] | -12.82% [-13.06, -11.60] |
| n4 / 2 | -20.23% [-37.12, -11.07] | -22.17% [-36.24, -8.45] | -14.34% [-24.86, -5.97] |
| n8 / 1 | -2.44% [-15.86, -0.10] | -0.47% [-11.31, +5.72] | -0.62% [-11.29, +5.78] |
| n8 / 2 | -19.95% [-21.22, -9.95] | -11.26% [-15.64, -8.43] | -10.97% [-15.54, -8.24] |

| 网格 / MPI ranks | 一次性装配初始化变化 | 最大 rank 峰值 RSS 变化 |
|---|---:|---:|
| n4 / 1 | -44.11% [-51.93, -20.77] | -2.13% [-2.27, -2.07] |
| n4 / 2 | -20.17% [-35.85, +13.84] | -3.28% [-4.45, -2.87] |
| n8 / 1 | -39.90% [-46.04, -29.73] | -8.36% [-8.50, -8.36] |
| n8 / 2 | -47.72% [-48.92, -43.34] | -8.89% [-9.18, -8.36] |

n8 单 rank，原始贡献 **K=1,590,346**，本地唯一坐标 **U=260,010**。
贡献值缓冲从 **12,765,704 B→2,123,016 B**；新增 contribution→slot 映射为 **6,361,384 B**。
残量值缓冲另计 **983,328 B**，PETSc 内部 COO 计划与 setup 临时内存须由 RSS 实测反映。
双 rank 的 U 之和为 **267,570**，大于全局唯一 nnz=260,010，因为不同 rank 仍可贡献同一坐标。
因此 U、K、全局 nnz 和峰值 RSS 是不同指标，不能互换。

最终 COO 四组峰值 RSS 全部配对下降；细网格 1/2 rank 分别约 **−8.36% / −8.89%**。
整次 wall 三组全部配对下降，细网格单 rank 的范围跨零，不能称其已获稳定整次加速。
没有将该结果与默认 campaign 作未经配对的跨后端速度比较。

### 4.3 两个单元线程：同一 7f3 二进制 AIJ，1 → 2

| 网格 / MPI ranks | 装配时间变化 | 求解时间变化 | 整次 wall 变化 |
|---|---:|---:|---:|
| n8 / 1 | -17.45% [-19.75, -5.97] | -1.95% [-2.47, +3.24] | -1.86% [-3.10, +3.00] |
| n8 / 2 | -15.98% [-30.34, +1.36] | -8.36% [-10.99, +0.04] | -8.14% [-10.03, +0.76] |

字段、ghost 和历史逐项相同；数值 scatter 次序没有改变。
assembly 配对中位数下降 **17.45%（1 rank）/15.98%（2 rank）**，wall 中位数下降 **1.86%/8.14%**，
但两组 wall 范围均跨零；新增有界暂存带来约 **0.85%/0.93%** 的峰值 RSS 中位增幅。
直接线性求解仍占主要成本，单元核加速不会等比例改善整次运行，因此默认线程数保持 1。

## 5. 开发中实际发现的问题与修复

**collective 生命周期。** 独立静态审查发现 rank-local 的 keep/release 决策可能让部分 rank 析构 SNES、其它 rank 保留。
推送前改为共同 MPI_MIN 决策，补充仅 rank 0 关闭复用的普通/双 COO、连续求解回归。
这是静态发现并已验证的修复，没有将其写成曾实测死锁。

**COO 初始化回退。** 7f3 中先对 K 项间接索引全局排序，细网格单 rank 的完整 plan 阶段中位数为 **207.212 ms**，
上一轮为 **29.445 ms**；system 阶段虽由 **156.877→33.014 ms**，总准备仍配对增加 **23.03%**。
没有撤销 K→U 压缩，而是在 2b0 改为局部行分桶和短列排序，并提前释放 K 项临时行。
最终同组 plan/system 中位数为 **85.668/34.110 ms**，总准备配对 **−39.90%**，三对均下降。
这是不同 campaign 的测量，不能将 207→86 ms 直接当作单独排序核的配对速度证明；plan 还含其它计划工作。

**证据审计的显示精度与求和。** 首版审计误把首步六有效位的 `4.97787e+07` 与后续完整精度 `49778688`
当作 RSS 下降 12 B；实际首个数字的显示末位为 100 B。审计按每个原始 token 的显示精度区间核对单调性，
聚合仍严格取原始打印值的 max，不改基准数据。
第二次发现 Python 3.12 的 `sum` 与审计逐项 `+=` 在极小配对比上相差 1 ULP；改用统计定义中的 `sum(raw step values)` 重算。
两次失败的审计脚本、输出和日志均保留；没有更改任何物理、字段或真实线性残量门槛，也未重跑求解器掩盖记录。

GCC 15.3 的 Tri3 小数组 `std::sort` 警告经独立静态审查：row_count 严格不超过 3，排序只访问已初始化前缀。
没有发现实际越界路径；未关闭编译警告或为此增加无关 Debug/全量测试。

## 6. 使用和复现

默认调用即可使用精确 AIJ、残量 COO 与合资格会话复用。可选执行开关：

```text
-fsi_coo                  # 矩阵也使用固定 COO
-fsi_threads 2            # 每 rank 两个纯单元 worker；需 OpenMP 和 MPI_THREAD_FUNNELED
-fsi_residual_coo false   # 回到普通残量 Vec 插入，用作对照
-nonlinear_reuse false    # 每次重建求解器，用作对照
-fsi_assembly_report      # 一次性图/计划/存储成本及缓冲计数
```

历史型 SNES、显式 lag/reuse-PC、EW 与 operator-permutation 诊断保留 fresh 语义；未静默更改用户的数值选项。
最终 benchmark 的可复现入口（BASE/CAND 指向表中已核验二进制，同一锁定运行环境）：

```bash
python scripts/benchmark_fsi_assembly.py \
  --baseline "$BASE" --candidate "$CAND" \
  --baseline-commit df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e \
  --candidate-commit 2b0b30bc2e1b036b8b97c9424cc6d41abd5af105 \
  --mpiexec mpiexec --work NEW_DIRECTORY \
  --subdivisions 4 8 --ranks 1 2 --steps 20 --repeats 3 \
  --baseline-assembly-report --baseline-options=-fsi_coo --candidate-options=-fsi_coo
```

默认 campaign 使用 7f3 候选并省略两端 COO 选项；线程 campaign 两端均为 7f3，n8、1/2 rank，
只给候选 `--candidate-options='-fsi_threads 2'`。原始命令、分区/输入和环境记录均在各 campaign 的 results.json。
不要覆盖既有结果目录。二进制依赖原锁定动态库，不是独立安装包。

## 7. 归档与审计

独立审计已通过：核验 **13,787 份文件哈希 / 985,204,950 B**，重读 **1,680 个保存状态、5,040 份体 VTU 分片**及 15,572,928 个 owned 标量值。
90 条命令（80 次运行、10 次准备）全部成功，1,600 个接受步、3,200 次线性修正和 6,400 条字段接受记录一致。
最大 true residual / gate 为 **0.00019408852157546064**；ghost 差为 0，跨 rank 字段差不超过 4.440892098500626e-16。
48 次现代版本运行中共 960 步、912 次复用，与每次 19/20 及 generation=1 一致。

- [performance-summary.json](performance-summary.json)：全部正式与中间 campaign 的来源、计数、原始统计。
- [independent-audit.json](independent-audit.json)：从原始日志、CSV、VTU 和文件摘要独立复算的最终结果。
- [archive.json](archive.json)：内容对象清单、计数、完整压缩流和分块 SHA、重组说明。
- [validation-summary.json](validation-summary.json)、[validation-bucket-summary.json](validation-bucket-summary.json)：13 项与受影响 1 项的实际验收。
- [ci-source-7f3.json](ci-source-7f3.json)：初始源码 CI 的 51 项执行来源；[ci-source-2b0.json](ci-source-2b0.json)记录修复后的 28 项新执行及 23 项复用。

归档共 **21,848 份原始逻辑文件 / 4,421 个去重内容对象**，压缩流 **19,946,772 B**，分五块交付；
全部对象、清单引用、二进制和分块重组摘要已读回校验。2b0 CI 收据为后到的相邻 JSON，未在压缩包内。
归档保留四个 campaign、实际三个二进制、构建与测试收据、完整日志、输入和分区、逐步与最终两域 VTU、CSV、
源码/驱动快照、独立审计及失败尝试。`manifest.json` 以 scratch 下原始相对文件名映射到 SHA-256，
唯一内容位于 `objects/<sha256>`；压缩流若拆分，按 archive.json 中的顺序连接后先核验完整 SHA。
从重组后的 tar.xz 读取原始结果时先核验对象，例如：

```python
import hashlib, json, tarfile
with tarfile.open('evidence.tar.xz', 'r:xz') as archive:
    manifest = json.load(archive.extractfile('manifest.json'))
    ref = manifest['files']['perf2-coo-final/results.json']
    payload = archive.extractfile('objects/' + ref['sha256']).read()
    assert hashlib.sha256(payload).hexdigest() == ref['sha256']
    result = json.loads(payload)
    assert result['status'] == 'passed'
```

本轮共享代数正确性覆盖最多单机 4 rank；正式 FSI 性能仅 1/2 rank、两套小网格和 20 步。
没有证明多节点扩展、GPU 收益、网格无关迭代或生产网格上的普遍加速。
残量 COO 与会话复用没有单独消融，本文的性能结论属于整体改动组合。
