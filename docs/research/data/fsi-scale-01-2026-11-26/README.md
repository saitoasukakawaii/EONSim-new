# FSI-SCALE-01：可扩展 Matrix-free 路径的实现与验收证据

对应 [PR #64](https://github.com/saitoasukakawaii/EONSim-new/pull/64)，基线为
`88257a9be35008b0063820910843625fa17bb267`（#63）。本轮遵循用户指定顺序：完成每批源码，
先同步远端并核对完整 Git tree，再构建及运行；发现问题后也先发布修正源码，再复验。
文档、审计和归档不记作新的数值运行。

十二项方向都有实际实现或可执行验证入口；**严格近网格无关收敛及百万自由度、多节点验证
必须分别按实测结果判断，不能由实现数量推导完成状态。** 使用方式见
[运行与数学说明](../../../development/FSI_SCALABLE_MATRIX_FREE.md)，可复用推导与故障分析见
[未发布草稿](../../../../website/drafts/fsi-scalable-matrix-free.md)。

最终生产/驱动源码为 `50b41ae19067bd8853a482ab853805e23c096ec5`：严格网格窗口 **9/9**、
默认及移动 NH/RCR **15/15** 全部通过原数值门槛和独立审计。Supremizer 的平均迭代
增长比为 **2.1630 > 1.3**，该性能目标仍 **OPEN**；实际最大规模只有 **10,387 DoF、
一个 host**，百万自由度与多节点强弱扩展未执行。

快速索引：[机器可读结论](summary.json)、[来源与二进制摘要](provenance.json)、
[原件逐文件清单](raw-manifest.json)、[压缩包与清单校验和](raw-SHA256SUMS.txt)。
任务始于北京时间 2026-11-26，最终验收记录于 2026-11-27；目录保留任务起始日期。

## 来源与复现约定

以下是已经执行构建或测试的修订；各批原命令、输入、输出和失败记录均保留。

| 源码 | 已发布改动与验证用途 |
| --- | --- |
| `e0edc6b83fa2a3b61ac64f758e7be9ab96f40539` | 十二方向初版：reduced P、缓存/批量/overlap、缩放/候选/patch/native、forcing/recycling、规模驱动 |
| `707a6a6dd92c9cbbea8bb24708c17da5b381aa4a` | 抑制投影梯度中被精确线搜索放大的舍入噪声，补齐物理驱动所需 action telemetry |
| `8410818a4930902ffbef2f16ac35d46bddf21e8a` | 初版当前算子真实残差 guard、RSS 口径修正；guard 的 reason 发布顺序有缺陷，相关结果仅作诊断 |
| `6378f4cca035bcf8a29150ef21588528c70aa824` | guard 先在局部 proposed reason 上判断，再用当前 Krylov 近似构建真实残差；固定输入成本与强弱 smoke |
| `116836b9d4143a280759a2e69e6c1b31156fb616` | 缩放后保持物理 Galerkin 投影的首层带权限制；压力/散度配对候选；停止近恒等粗化 |
| `30e29411431d4f721f1a9aa4b9b55fc685f70e7b` | 两方向 K-cycle 与实际工作计数；native 生命周期、CSR patch、filtered lifting、halo 容量收缩 |
| `06411830f5589a4f295081c099c3a1719733c82f` | 仅修正新增 Python 负例期望的异常类型；生产代码和数值驱动与 `30e2941` 相同 |
| `50b41ae19067bd8853a482ab853805e23c096ec5` | 固定谱预算内的 pressure supremizer、冻结成对插值列与真实粗耦合审计；最终网格/物理验证 |

GitHub API 创建的提交与本地等价提交完整 tree 相等后才运行。保留本地等价备份分支，
没有强推 main 或修改分支保护。当前数值原件使用固定归档二进制，后续工作树修改不改变它。
例如 `30e2941` 的 tree 为 `6d0608d21c2ec61626fcbfc90c0dec99fd738809`，二进制 SHA256 为
`bfadbb0c3aab7d3c9507560aaac3940a352f76f16f3de285fb254b8872bd782f`。
最终 `50b41ae` 的 tree 为 `7f66c8b02d62ed67606f7bf5f94fd5af34915f6e`，固定二进制 SHA256 为
`dea9ab78339d4d07a8a83bac11fb22f733898d45ef681d51b99f71adfa3522e7`。

环境为共享 Linux 单机，AMD EPYC 9V74、9 个可用 CPU affinity、约 9.7 GiB 内存，
GNU 15.3.0、Open MPI 5.0.8、锁定 PETSc 3.23.7、FP64 PetscScalar/32-bit PetscInt。
Release 增量构建并行度 2，各数值 rank 使用一个 OMP/BLAS 线程。
全部本地实际节点报告为一个 host；MPI rank 数不等于节点数。

## 实际检查与执行顺序

工作目录为仓库根；原环境 wrapper 位于另一个共享依赖目录，命令用 `bash` 调用。
在新环境复现时应按仓库锁定环境流程准备同版本依赖并替换 wrapper 路径，不照搬临时绝对路径。

```bash
bash /workspace/scratch/ae740e1dde63/EONSim-new/build/locked.sh \
  cmake --build build/release --target eonsim verify_monolithic_fsi_mg \
  verify_fsi_level_smoother verify_interface_patch verify_matrix_free -j 2
bash /workspace/scratch/ae740e1dde63/EONSim-new/build/locked.sh \
  ctest --test-dir build/release --no-tests=error \
  -R '^(monolithic_fsi_mg|fsi_level_smoother|interface_patch)_mpi[124]$' \
  --output-on-failure --output-junit build/fsi-scale-01/unit-30e2941.xml
bash /workspace/scratch/ae740e1dde63/EONSim-new/build/locked.sh \
  python -m unittest discover -s tests -p test_fsi_runner.py -v
```

`30e2941` 的上述 9 项 CTest 全部通过，覆盖 K-cycle 独立制造解、有限粗解次数、零 RHS、
native 重建失败及后续恢复、dense/CSR patch、源 Mat 释放后作用、远端 identity lifting
以及 4 ranks 中两个空 owner。`0641183` 的 16 个 Python 测试方法全部通过。
原 `30e2941` Python 执行中的两个方法出现 13 条错误，原因是负例预期 RuntimeError，
而既有审计接口实际抛 ValueError；没有修改审计拒绝条件，旧失败日志保持原样。

`50b41ae` 增量重建 `eonsim` 与 `verify_monolithic_fsi_mg`，MG MPI **1/2/4 rank 三项**
及 **19/19 Python 测试方法**通过。制造回归实际检查两条原候选无法表示的压力通道、
weighted coarse pairing、velocity-only 支撑、跨 owner 冻结列、空 owner、数值刷新、
plain/scaled/native 作用与原方程真残量；依赖选项缺失和零谱预算均明确拒绝。

其余本地检查按影响范围分源记录：初版 11 项中 9 通过、MG 1/2 rank 失败；
`707a6a6` 的 MG 1/2/4 与 MF2 共 4 项通过；`8410818` 的 MF1/2/4 因 guard 缺陷失败；
`6378f4c` 同三项通过；`116836b` 的 MG1/2/4 通过。
一次错误正则选择到零个 CTest，明确记为**没有执行**，不计通过。
未受后续改动影响的检查引用原证据，没有为提交号变化重跑全量、Debug 或旧 PETSc。

## 严格网格窗口：物理通过与收敛目标分开

驱动固定 n=4/6/8、2 ranks、三个时间步，预先写入最大/最小平均线性迭代数 **≤1.3**
的有限窗口目标。严格模式都采用相同 Krylov 与物理门槛；inexact 的平均迭代不能用于此目标。

最终 `50b41ae` 同源 direct、增强 V、supremizer V 共 **9/9 求解通过**。两种 V 之间只改
pressure supremizer 选项；它占用既有 spectral slots，没有增加 aggregate 大小、平滑次数
或粗解预算。独立审计核对 27 接受步、54 条线性记录、480 个原件 hash、144 个体场分片
与 12 个命令 hash；最大场差 `3.5779713e-13`、历史差 `8.0491169e-16`、ghost 差 0，
严格真残量/门槛最大 `0.00872922`，36 次 guard 检查、0 次拒绝。

| 最终同源模式 | 703 DoF：总迭代/6 | 2,299 DoF：总迭代/6 | 5,367 DoF：总迭代/6 | 平均迭代最大/最小 |
| --- | ---: | ---: | ---: | ---: |
| 增强 V | 97/6 = 16.17 | 160/6 = 26.67 | 227/6 = 37.83 | 2.3402 |
| Supremizer V | 92/6 = 15.33 | 138/6 = 23.00 | 199/6 = 33.17 | 2.1630 |

每次细层 setup 实际生成方向/配对 aggregate 数为 20/10、56/28、118/59；n8 所选局部
归一化耦合最小奇异值约 `0.149842`，实际 FP64 粗耦合相对变化约 `3.37e-16`。
这些量证明选定配对被保留，不证明所有压力模态或后续混合粗层具有统一 inf-sup 常数，
也不把 FP64 setup 的保持精度当作 FP32 apply 的精度证明。**近网格无关目标仍 OPEN。**
该次求解时间 V 为 2.799/12.955/54.289 秒，supremizer 为 2.273/10.421/43.767 秒；
仅为一次正确性窗口的成本观测，不作为稳定加速结论。

以下为保留的早期 K-cycle 同源窗口，不与最终 9 个运行混计。

`30e2941` 同源 direct、原 mono、增强 V、增强 K 共 **12/12 求解通过**，结果如下。
独立审计核对 36 个接受步、72 条线性记录、639 个原件 hash 和 192 个体场 VTU 分片；
最大场差 `9.3983154592e-13`、历史差 `5.6843418861e-14`、owner/ghost 差 0，
严格真残量/门槛最大 `0.00820136`，54 次 guard 检查没有拒绝。

| 模式 | 703 DoF：总迭代/6 | 2,299 DoF：总迭代/6 | 5,367 DoF：总迭代/6 | 平均迭代最大/最小 |
| --- | ---: | ---: | ---: | ---: |
| 原 mono V | 103/6 = 17.17 | 151/6 = 25.17 | 206/6 = 34.33 | 2.0000 |
| scaling/candidates/adaptive/native V | 97/6 = 16.17 | 160/6 = 26.67 | 227/6 = 37.83 | 2.3402 |
| 同一组合 K | 98/6 = 16.33 | 148/6 = 24.67 | 202/6 = 33.67 | 2.0612 |

三者均未达到 1.3。K 在后两档少用外层迭代，但本窗口仍未达到近网格无关目标，
也不构成粗空间逼近或全局混合稳定性的证明。
K 每次 PC 的 coarse solves 在 4/4/5 层上为 4/4/8；V 均为 1。K 的 level matvec 为
23/23/51，V 为 6/6/8；K 的 smoother applications 为 14/14/30，V 为 6/6/8。
K 的 VecNorm/VecDot 请求数为 36/36/84，不能等同于实测 MPI 包或 collective 数。

本次 K 的求解时间为 2.840/13.157/57.771 秒，V 为 2.778/12.993/54.032 秒；
这是共享节点的一次窗口执行，不是稳定计时研究。K 的减少迭代没有转化为这次求解加速。
统计按 `(rank,path,solver_generation)` 保留末次累计值，不跨接受步重复相加；
RCR bulk 的额外响应求解也在计数中。

原 `707a6a6` 窗口 12/12 物理通过，但 enhanced V 平均迭代增长到 19.83/38.33/81.33；
`116836b` 的物理带权限制消除了这一缩放回归，15/15 通过，增强 V 为 16.17/26.67/37.83。
随后一个 n8 W-cycle 诊断通过全部原门槛，但平均迭代 46.50，比 V 更差。
这些负性能结果保留，不能因后来改进而删除。

## Native FP32：系数、因子和进程内存分别测量

`116836b` 的 native-only n8 与 FP64 对照分别使用 205/206 次迭代，均通过原数值门槛。
LU 数组从 40,025,728 降到 20,012,864 bytes，但最大 rank 峰值 RSS 由 210,153,472
升到 283,660,288 bytes（约 +35%）。这暴露了旧/新层级同时驻留、临时 setup 与容器容量问题。

`30e2941` 在重建前释放旧 native generation；patch 选择按实际字节较小的 dense float 或
float/uint16/uint32 CSR；直接提取 identity 列，避免整个 FP64 lifting 副本；
清除 setup-only 数据及去重后仍占 nnz 容量的列数组。原 P、最粗解、PETSc 向量/MPI 仍为 FP64。

修复后的同源 n8 pair 双方都使用 `-solver_rank_report`，仅 native 选项不同；
同输入、分区、3 个时间步，206/205 次迭代，场最大差 `7.534806112e-13`，历史差
`2.331468352e-15`，native 真残量/门槛最大 `0.0069361`。

| 指标 | FP64 | native FP32 | 变化 |
| --- | ---: | ---: | ---: |
| 最大 rank 的归一化峰值 RSS（bytes） | 210,673,664 | 202,129,408 | −4.0557% |
| 各 rank 峰值 RSS 之和（bytes） | 316,915,712 | 303,300,608 | −4.2961% |
| 最大 rank 的原始 OS 峰值（bytes） | 210,206,720 | 202,129,408 | −3.8426% |
| 首次报告的系数 + LU + patch CSR 索引（bytes） | 70,004,704 | 36,207,846 | 不等于全部进程内存 |

归一化峰值定义为 `max(已观测 current RSS, raw system peak)`，两种原始口径分别保留；
各 rank 峰值求和不是同一时刻整个作业的总峰值。进程 RSS 的下降只有这一次同源 pair 的
证据，不能称总内存减半或实测带宽减半。native 最后一次报告有 1,175 个 sparse 和
248 个 dense patch，显式存储随数值零项可变化，末次系数/LU/patch 索引总计
39,848,732 bytes；FP64 只输出了一次初始层级报告。上述数组统计还不包括其他索引、
外层 P、PETSc 向量和通信缓冲区。完整审计比较了 64 个 VTU（含边界）及 432 组数组。

## Reduced P、方向缓存、SIMD、overlap、forcing 与 recycling

初版 reduced P 在双域例将 NNZ 从 10,170 降到 7,788（−23.42%），移动 RCR 例从
14,639 降到 11,418（−22.00%）；AIJ 与 COO 都使用缩小后的真实符号图。
它省去 P 中流体方程对 ALE 列的预条件导数，包括对应入口压力面的 ALE 导数；移动 RCR
端口的额外耦合仍单独装配。外层继续使用完整精确 Jv、原残量和接受门槛。

`116836b` 的 default/moving 共 15/15 通过，45 接受步、119 次修正；独立审计读取
200 个体场 VTU 分片、643 个 artifact hash 及 18 个命令 hash。最大场差 `5.1654747e-10`、
历史差 `9.8855e-12`，均低于 `2e-9`；owner/ghost 差为 0。
严格真残量/门槛最大 `0.0071973`，inexact forcing 比值最大 `0.9257869`，
最终物理门槛比值最大 `0.792828`，RCR 恒等式缺陷 `2.819e-16`。

`6378f4c` 固定 703 DoF、2 ranks、2 步的成本研究包括 1 个参考、4 个 warmup、
12 个正式运行（四模式各 3 次），17/17 全部通过，每次都是 78 次线性迭代和 4 次修正。
下表是每一对候选/未缓存 matrix-free 的比值，再取中位数与范围；不是不同算例的相除。

| 模式 | rank0 方向作用耗时比值中位 [最小,最大] | 求解耗时比值中位 | wall 比值中位 |
| --- | ---: | ---: | ---: |
| Partial assembly | 0.83468 [0.80165,0.86185] | 0.89716 | 0.92830 |
| Partial assembly + SIMD | 0.63194 [0.60230,0.69134] | 0.85716 | 0.89533 |
| MPI overlap | 0.83667 [0.82983,1.02719] | 0.87524 | 0.93731 |

SIMD 对已缓存 scalar 路径的作用耗时比值中位为 0.78830，wall 比值范围跨过 1；
SSE2 packed arithmetic 的实际反汇编证据也保留。未新增独立 cache preparation timer，
不能将较宽的 assembly 时间全部归因于缓存准备。没有跨节点通信隐藏或普遍端到端加速声明。

Inexact Newton 使用有界 forcing，最终物理门槛不变。Recycling 复用的是有限个成功修正
向量的 span，按当前算子重新形成 images 并检查初值残量；不是完整 Arnoldi/GCRO-DR。
双域/移动例和多步日志验证了实际 cache、batch、overlap、forcing、recycle counters，
不能仅因选项被接受就认定路径执行。

## 最终默认与移动 NH/RCR 物理验收

`50b41ae` 的双域 1/2 ranks 与移动 NH/RCR，每个场景比较 direct、增强 V、K、supremizer V、
全功能组合，共 **15/15** 通过。独立审计核对 45 接受步、117 条线性记录、643 个原件 hash、
200 个体场分片、18 个命令 hash。最大场差 `2.9099984e-10`、历史差 `4.1689985e-12`，
均低于原 `2e-9` 门槛；owner/ghost 差为 0。

| 场景 | 增强 V：总迭代/修正 | K：总迭代/修正 | Supremizer V：总迭代/修正 | 全功能：总迭代/修正 |
| --- | ---: | ---: | ---: | ---: |
| 双域，1 rank | 72/6 | 70/6 | 71/6 | 38/11 |
| 双域，2 ranks | 68/6 | 69/6 | 67/6 | 36/10 |
| 移动 NH/RCR | 134/9 | 189/9 | 133/9 | 112/12 |

K 在移动场景使用更多迭代，不能声称普遍改善；全功能采用 inexact Newton，不能用其总迭代
与严格线性精度模式直接衡量网格收敛。所有原接受门槛保持：严格真残量比最大 `0.00786282`，
inexact 请求门槛比最大 `0.99621455`，最终物理接受比最大 `0.53790668`；约束差 0，
RCR 恒等式缺陷 `4.0766e-17`，96 次 guard 检查、0 次拒绝。
Supremizer 与全功能每次细层 setup 实际产生 8 个方向/4 个配对 aggregate，最大 FP64
配对变化 `5.1160e-16`。全功能实际 P NNZ 为 7,788/11,418，三个场景的 recycling
projection 次数为 10/9/11，路径执行由原日志计数证明。

## 大规模基准入口与实际规模

强/弱扩展驱动支持任意正 rank 数、MPI launcher 参数、真实 host 分布、最低 DoF/节点数
门槛与磁盘 SQLite 全场拓扑审计。large campaign 的参考是明确标注的同方程 iterative mono，
没有伪称稀疏直接解。网格准备仍是串行阶段。

`6378f4c` 的 strong smoke（n3，1/2 ranks）和 weak smoke（n8/1 rank、n10/2 ranks）
合计 8/8 通过；weak 每 rank DoF 从 5,367 到 5,193.5，变化 −3.23%，在固定 10% 负载
容差内。完整 host、RSS、SQLite 场/拓扑与原物理门槛均通过，场最大差 `2.22e-16`。
**实际最大规模是 10,387 DoF、一个 host；百万 DoF、多节点及强弱扩展效率均未验证。**
不存在可用集群 allocation，不能把同机 2/4 ranks 当作多节点结果。

## 保留的失败、诊断与修复

| 记录 | 真实分类与根因 |
| --- | --- |
| 初次 wrapper 调用 | exit126，尚未编译；改用 `bash` 后完成配置/构建 |
| 初版 MG1/2 rank | 候选约束张成整行空间时，投影残余舍入噪声被精确线搜索放大；按机器精度检测零投影，原候选再现门槛不变 |
| 初版 physical-actions | 24 个运行中 15 audit pass，9 因缺 action telemetry 失败；离线证实数值通过也不改写原 campaign failed 状态 |
| `707a6a6` physical-optimized | 30 个中 29 通过，moving scaled 的原算子残差超限；递归残差不是当前真实残差 |
| `8410818` guard | 正收敛 reason 过早发布，使公开 `KSPBuildSolution` 读取旧 restart solution；MF1/2/4 失败，物理诊断虽通过却过度迭代，不作为性能验收 |
| `6378f4c` guard 修复 | 在 KSP 仍为 ITERATING 时构建当前残差，再发布候选原因；MF1/2/4 及 moving scaled/PIPE 对照通过，无私有 PETSc 访问或重置预算 |
| 原 RSS telemetry | current 与 getrusage 峰值来自不同采样接口，出现 peak<current；保留 raw OS 并给出归一化峰值定义 |
| `8410818` weak smoke | 人工中断 exit130，保持 interrupted；没有将未运行的 n10 或终止的候选标为失败/通过 |
| `116836b` native-only | 物理通过但峰值 RSS 增加约35%；由 `30e2941` 生命周期与容量改动作同源复验 |
| `30e2941` Python 负例 | 测试期望异常类型错误；修正为既有 ValueError，未改变拒绝条件 |

GDB/LLDB 在本环境不可用，检测记录保留；guard 调查使用最小复现、实际日志与 PETSc 3.23.7
公开源代码核对，没有修改库私有状态。原始故障日志、被中断收据和诊断通过记录分别保存。

## 独立审计的范围

独立 Python 标准库程序重读实际 log/CSV/VTU/XML、校验原件 SHA256，并按原门槛比较
每个接受步和最终场、坐标、全局编号、所有权、连接关系、历史、RCR 恒等式与日志残差。
没有保存每次线性化的 J、b、dx，因此**不声称离线重新计算了 Jdx−b**；
真实残差由求解时原算子计算，离线审计核查其原始标量及对应门槛。

原件归档共 28 个压缩包、9,195 个文件，压缩后 15,024,112 bytes；保留全部成功、失败和
中断 campaign 的输入、分区、命令、日志、CSV 和 VTU。
压缩包成员以 `fsi-scale-01/` 为前缀；收据中的原绝对路径映射到解包后 `build/fsi-scale-01/`。
ELF 二进制只记录 SHA256 和构建来源，SQLite 审计 spool/Python cache 可重建而不入包。
`archive-evidence.py` 对每个成员逐文件核对 hash、读取归档复核，并拒绝源文件在归档中改变。

```bash
# 最终原件生成后，使用其中的清单及程序复核；这不会启动数值求解。
python build/fsi-scale-01/archive-evidence.py --verify docs/research/data/fsi-scale-01-2026-11-26
```

源码 `116836b` 的远端 CI45843939196 实际执行 **66/66 Release**，JUnit 零失败/跳过、
receipt 零复用；merge-preview `ec20328c2fee5fd356f67c28f30942caa070434e` 的完整 tree
与该源码一致。`0641183` 的 CI45849752858 实际执行 **32/32 Release + 16/16 Python**，
另 34 项复用 `116836b` 成功证据；完整 receipt 与 JUnit 已下载，merge-preview
`2ce0ea05fe8eb3f0649500bf37440b0152865b65` 的 tree 也与源码相等。
最终源码 `50b41ae` 的 [CI45853312807](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45853312807)
实际新跑 **4/4 Release + 19/19 Python**，另 62 项按有效 receipt 复用，covered 总计 66；
不能写成此次新跑 66 项。merge-preview `3ca62ae4c0c037ca59c255fc8cd1754f1101f7ea` 的完整
tree 与源码相等。官方 plan、numerics、receipt 三个 ZIP 已逐一按 GitHub SHA256 核实，
原件与校验记录完整保存。该源码的网站检查
[45853312823](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45853312823) 通过。
后续仅文档/归档提交的检查不算新的数值运行；最终四项必需检查及精确 head squash 合并
状态以 [PR #64](https://github.com/saitoasukakawaii/EONSim-new/pull/64) 的 GitHub 记录为准。
