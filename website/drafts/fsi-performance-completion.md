---
title: "算法说明：让 FSI 的稀疏图、贡献缓冲与求解器会话各自复用"
description: "从精确物理图、rank 内 COO 去重到线程暂存和求解器生命周期，解释组合优化的实测收益、初始化回退及其修复。"
contentStatus: draft
algorithm: "Projected FSI sparsity, locally coalesced COO and reusable nonlinear sessions"
sourceReferences:
  - "https://petsc.org/release/manualpages/Mat/MatSetValuesCOO/"
  - "https://petsc.org/release/manualpages/Vec/VecSetPreallocationCOO/"
  - "https://petsc.org/release/manualpages/Vec/VecSetValuesCOO/"
  - "https://petsc.org/release/manualpages/SNES/SNESDestroy/"
  - "https://petsc.org/release/manualpages/Mat/MatCreateBAIJ/"
eonsimCommit: "2b0b30bc2e1b036b8b97c9424cc6d41abd5af105"
baseCommit: "4e25e2a7b1aa921dc473fe09cd5f9b3f09d4645f"
validationCommit: "7f3d12ed6d0a1abc67d5f5606bf644b142a3197f"
benchmarkBaselineCommit: "df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e"
benchmarkDriverCommit: "7f3d12ed6d0a1abc67d5f5606bf644b142a3197f"
cooFinalCommit: "2b0b30bc2e1b036b8b97c9424cc6d41abd5af105"
cooValidationCommit: "2b0b30bc2e1b036b8b97c9424cc6d41abd5af105"
cooBenchmarkDriverCommit: "2b0b30bc2e1b036b8b97c9424cc6d41abd5af105"
pullRequest: "https://github.com/saitoasukakawaii/EONSim-new/pull/52"
---

# 算法说明：让 FSI 的稀疏图、贡献缓冲与求解器会话各自复用

**审核草稿；默认与线程的最终性能证据来自 7f3d12e，最终 COO 证据来自 2b0b30b，二者分别记录验证与二进制来源。**
本文面向使用低阶有限元与 MPI/PETSc 的开发者，说明三个容易混淆的对象：
固定矩阵图、每次评价的局部贡献，以及跨非线性调用保留的求解器对象。
学习目标是判断哪些内容可复用、哪些必须刷新，以及局部 RAII 为什么还需要集体生命周期规则。

| 证据类别 | 本文已有内容 | 当前不能据此声称什么 |
|---|---|---|
| 理论 | test/trial 投影、物理依赖计数、缓冲内存公式 | 实测速度或峰值 RSS 改善 |
| 实现 | 主体源码 `7f3d12e`；COO 行分桶修复已推送为 `2b0b30b` | 用源码完成状态替代数值验收 |
| 数值验证 | `7f3d12e` 本地 Release 13/13；`2b0b30b` 受影响回归 1/1 | 将不同源码、不同范围的测试合并成一套全量记录 |
| 性能 | 默认/线程为 `7f3d12e`，最终 COO 为 `2b0b30b`；另保留前版回退证据 | residual COO/session 的独立因果收益，或多节点扩展性 |

## 1. 问题定义：三个生命周期不能合并成一个缓存开关

上一轮已经保留 PREALLOCATOR 生成的最终 AIJ，并缓存单元的有效行列映射。
但默认图仍保守，COO 值缓冲仍按重复贡献条数增长，残量采用逐次 Vec 插入，
每次 solve 还重新创建 SNES/KSP/PC。这些是不同阶段的成本，应分别处理。[E1] [S1] [S2] [S3]

本轮保持相同残量、Jacobian、物理验收和接受后历史提交规则，改变存储与执行方式。
图的有效期取决于拓扑、分区、编号和约束支撑；数值依赖 trial、材料、几何和时间系数；
求解器会话还依赖配置、PETSc options 和约束行列表。坐标变化不要求重建图，
却必须更新 ALE 梯度、体积、面积及其导数；复用 PC 对象也不意味着复用旧数值因子。

## 2. 数学定义：测试映射与试探映射独立

令有效未知量为 \(q\)，单元物理状态为 \(x_e=T_eq+g_e\)。固定一次 Newton 中的时间系数后，

\[
R(q)=\sum_e P_e r_e(T_eq+g_e)+R_{\mathrm{port/body}}(q),\qquad
J(q)=\sum_e P_e J_e T_e+J_{\mathrm{port/body}}.
\]

\(T_e\) 展开试探状态，\(P_e\) 投影测试残量；不能直接令 \(P_e=T_e^\mathsf T\)。
FSI 界面流体速度关联结构速度，网格位移通过当前 `mesh_dt` 恢复，但人工网格的接口
测试行被丢弃。因此同一个物理 slot 可以有有效 trial column 而没有有效 test row。[S1]

BE、变步 BDF2 和 generalized-alpha 使用各自的位移恢复系数。计划只保存 trace 标记，
每次 attempt 再乘当前系数；拒绝步之后不能继续使用前一次的 `mesh_dt`。
刚体 alias、分量约束和双域 inactive 分量也通过这两套映射处理，不重新发明一套编号。

## 3. 精确物理图：默认 AIJ 与 COO 使用同一依赖

共用 `fsi_coupling_pattern.hpp` 定义五个矩形：流体测试分量 0–3 对列 0–6、
三个 mesh 同分量块，以及结构分量 7–9 的完整块。它描述方程可能依赖哪些变量，
不从某个 Newton 状态的数值零推断结构。[S1]

| 未约束 Tet4 形式 | 物理依赖槽数 | dense 槽数 |
|---|---:|---:|
| Fluid/ALE | `16*28 + 3*4*4 = 496` | 784 |
| Solid | `12*12 = 144` | 144 |
| 旧单网格 elastic，同时评价两种 kernel | `496 + 144 = 640` | 1600 |

默认 PREALLOCATOR 在各块内分别收集 test rows 和 trial columns，排序去重后插入其
笛卡尔积。这与 COO 逐物理槽枚举再合并坐标得到同一集合；接口 alias 只合并坐标，
不会丢掉各自的数值贡献。所有 owned 对角项也保留，覆盖仅需对角支撑的行。

固定 RCR 有速度与压力的双向耦合；移动平面 RCR 还必须包含压力行及法向速度行
对全部面内 mesh 列的面积导数。旧保守 cell 图会隐式覆盖部分项，精确图必须显式列出。
图填入最终 AIJ 后才启用 `MAT_IGNORE_ZERO_ENTRIES`，以继续使用一次 dense
`MatSetValues(..., ADD_VALUES)`；图外精确零被跳过，图外非零仍触发 location error。
这一选项控制插入，不能代替物理依赖推导。[S1] [P1]

## 4. COO 的 K→U：把重复归并前移到本 rank

设本 rank 有 \(K\) 条单元、端口和刚体贡献，其中 \(K_c\) 条来自单元；
这些贡献映射到 \(U\) 个不同的全局 `(row,column)` 坐标，拥有 \(n\) 行。
初始化按 reduced local row 分桶，把 32 位 contribution index 放入各行区间，
随后按全局行号遍历桶，仅在桶内按全局列号排序，生成 `uint32_t value_slots[K]`。
所有已发出矩阵行都属于 `local_to_global`：单元/端口速度来自 physical slot 映射，
body/port 则有显式 owned 或 ghost 支撑；负测试行在枚举时已跳过。
代码仍检查找不到行和索引容量溢出，并经 setup 的共同失败路径报错。[S1] [S6]

输出仍是与原全量排序相同的 `(global row,global column)` 字典序；重复坐标的
贡献索引先后不影响 `value_slots`，数值阶段仍使用原 contribution 顺序。
转换后的 K 项临时行数组在分桶完成后立即释放，随后只积累 U 项全局坐标交给 PETSc。
初始化暂存随后释放，持久层没有多存一份 K 项完整 tangent。[S6]

每次评价先清零值缓冲，再按固定 cell→port→body 顺序执行
`values[value_slots[k]] += contribution[k]`。本 rank 的 alias 和跨单元重复项先相加，
跨 rank 重复仍由 PETSc COO 完成；没有另一套 MPI 反向累加。[P2]

忽略 PETSc 内部计划和准备期临时量，只计算 double 值、16 位局部槽及新增映射：

\[
M_{\mathrm{old}}=8(K+n)+2K_c,\qquad
M_{\mathrm{new}}=8(U+n)+4K+2K_c,\qquad
M_{\mathrm{old}}-M_{\mathrm{new}}=4K-8U.
\]

因此这一部分在 \(K>2U\) 时节省内存。`7f3d12e` 细网格单 rank 报告
K=1,590,346、U=260,010，scatter 为 6,361,384 B，矩阵 COO 值为 2,123,016 B。
公式给出约 4.28 MB 的持久应用数组差额；**数组差额不等于 RSS 差额**，PETSc 内部
计划、残量计划和 setup 峰值也会影响内存。两 rank 的 U 总和为 267,570，大于全局
唯一 nnz=260,010，说明 rank 内去重没有消除跨 rank 重复。[E3]

**一次初始化回退及修复。** 首版 `7f3d12e` 对全部 K 个索引做间接坐标排序。
6,147 cells / 1 rank 的实际结果显示，减少 PETSc COO 工作量并未使总初始化更快：[E3]

| 中间版本 COO 指标，各三次正式 run 的中位数 | 基线 `df6e9ac` | 首版 `7f3d12e` |
|---|---:|---:|
| plan | 29.44 ms | 207.21 ms |
| system | 156.88 ms | 33.01 ms |
| 总初始化 | 187.04 ms | 241.73 ms |
| 单 rank 峰值 RSS | 160.23 MB | 150.20 MB |

配对总初始化中位数为 **+23.03%**，RSS 为 **−6.28%**。配对百分比先对每对 run
计算再取中位数，不由表中两列中位数相除得到。plan 包含整个贡献计划构造，
207.21 ms 不是纯排序 timer；源码检查把其中新增的 K 项全量间接排序确定为修复目标。

`2b0b30b` 将它改成上面的行分桶。设本地行数为 R、ghost 数为 G，需查询的连续行组
为 q，每行贡献数为 \(k_r\)，工作量约为
\(O(K+q\log(G+1)+R\log(R+1)+\sum_r k_r\log(k_r+1))\)。owned 行直接计算 local ID，
ghost 行二分查询并缓存连续重复；每行只排序列，减少大范围间接访问。
若贡献集中到极少数 alias 行，最坏情况仍可接近 `O(K log K)`，不能把整个过程称为线性。
数值阶段依旧执行 K 次原序 scatter-add，持久存储公式也不变。
修复后的独立 campaign 使用 `2b0b30b` 二进制重测，细网格单 rank 的 plan 中位数为
85.67 ms、system 为 34.11 ms；同批基线与候选的总初始化中位数为 201.91/121.35 ms，
配对变化中位数为 **−39.90%**，三对范围为 −46.04% 至 −29.73%。因此首版的
初始化回退在该配置的重测中消除。这里没有把不同 campaign 的 207.21/85.67 ms
相除作为独立的排序加速比；最终比较仍以同批基线/候选配对为准。[E3]

## 5. 残量 COO：计划属于实际 Vec

FSI 默认启用固定残量 COO，`-fsi_residual_coo false` 保留普通 Vec 插入对照；
该选择独立于 `-fsi_coo`。残量计划保留单元测试行、各端口牵引/流量项和 owner 的刚体项。
负行忽略，重复项相加，远程行交给 PETSc；所有 rank 成功后才发布整份缓冲。[S2] [P3]

一个隐蔽边界是 SNES 线搜索可能提供自己的工作 Vec。仅给持久 residual Vec 配好
COO，并不能推出它的 duplicate 也携带同一计划。实现给 residual/scratch 先准备，
再按 `PetscObjectId` 为首次遇到的实际回调 Vec 准备；只保存 ID，不额外持有借用 Vec。[S3]
失败评价不发布部分 COO 值，普通插入的 stash 仍排空；owned 约束行在本地替换，
全局没有约束时跳过 `MatZeroRows`。原始反力仍在最终物理验收后独立计算。

## 6. 64 单元线程暂存与局部核

`-fsi_threads 1` 是默认值。N>1 要求 OpenMP 构建和至少 `MPI_THREAD_FUNNELED`；
worker 只评价纯 kernel，输入 trial、历史和时间系数只读，不调用 PETSc、MPI、日志或 I/O。
每批最多 64 个单元，worker 复用私有工作区，残量写不重叠贡献区，切线写批次缓冲。
主线程 join 后按 cell 顺序进行 compact COO 累加或普通 Mat/Vec 插入。[S2]

不同单元经 alias 映射到相同值槽，因此压缩 COO 不能让 worker 直接共享 scatter-add。
目前由主线程归并，避免浮点 atomics 和线程相关的局部加和次序。按最大 40-DoF 单元，
64 份 double dense tangent 的暂存上界为 `64*40*40*8 = 819,200 B`，
另有 worker 工作区和残量缓冲；不保存所有本地单元的完整切线。异常在线程 join 后重抛，
再由统一 rank 间错误检查决定发布或拒绝。

局部 kernel 还把不需 Dual 传播的参考 mesh Laplace 和压力面积导数直接解析填写，
流体部分保留完整 28 方向几何/输运导数；几何有效性检查不因零压力跳过。
界面力仍重放相邻单元的原始物理残量并加入端口牵引，不以投影后的残量替代。[S4]
`FSIElementBatch` 包含批次调度和插入，内部 `FSIInsert` 不能与它相加当作总时间。

## 7. 求解器会话：复用对象，不复用过期数值

会话 key 精确比较完整 `SolverConfig`、PETSc options 字符串和 owned 约束行列表。
任一 rank 的 key 改变，所有 rank 一起重建；初值、prescribed 值、dt 和 J 数值不属于 key。
默认只复用 `SNESNEWTONLS` 且 Jacobian/PC lag 都为 1 的成功会话；显式
reuse-preconditioner、`-snes_ksp_ew true`、`-verify_operator_permutation true` 保持 fresh。
`-nonlinear_reuse false` 提供对照，并在成功返回时也释放会话。[S3]

每次 solve 重新计算初始字段范数，数值 Jacobian 更新后刷新 USER Schur 矩阵，PETSc
按当前 Mat 状态更新数值 PC。稳定 callback holder 仅在本次调用绑定当前 Context，
退出清空借用；SNES/KSP/PC 先于所引用的 USER 矩阵销毁。最终异常/StepRejected 后
重建会话；同一次线搜索已恢复的 domain rejection 不使成功会话失效。

**推送前静态审查发现：析构本身也是 collective。** 早期实现按本地
`reuse && reusable` 决定是否保留 Workspace。若只有 rank 0 关闭复用，一部分 rank 会
调用 `SNESDestroy`，另一部分直接返回保留对象，破坏集体操作顺序；C++ RAII 本身不会
替应用统一这个决定。`7f3d12e` 在成功出口对 keep 标志做 `MPI_MIN`，与入口的统一
rebuild 决策配对。新增回归只在 rank 0 关闭复用，要求所有 rank 的连续调用均 fresh。
这是静态发现并在推送前修复的问题，并非已经观测到的运行死锁。随后 `7f3d12e`
的 1/2-rank 回归在普通 Vec/Mat 和双 COO 路径均通过，验证了统一保留/销毁决策。[S3] [S5] [P4] [V1]

## 8. 没有采用的方案也需要证据

**BAIJ 适配判断。** 当前 reduced 编号混合 7/3/部分约束分量、接口 alias 和单自由度
body/port，不具有统一方块结构。`bs>1` 需要 padding 或编号重构，`bs=1` 没有块收益。
因此保留 AIJ；这不是实测 BAIJ 更慢的结论。[S1] [P5]

**Halo 重叠成本判断。** 以下仅重算 PR #51 最终归档：各五步正式 run 对逐步 max-rank
计时求和，先计算比例，再取三次重复的中位数。不是本轮结果，也不是新的数值运行。[E1] [E2]

| 上一轮 2-rank 配置 | ghost / solve | (ghost + finalize) / solve |
|---|---:|---:|
| 771 cells，default | 0.133% | 6.114% |
| 6,147 cells，default | 0.023% | 3.068% |
| 771 cells，COO | 0.461% | 3.251% |
| 6,147 cells，COO | 0.015% | 1.585% |

finalize 包含本地整理/归并，不是纯网络等待；各阶段独立取最大 rank，不能相加还原
真实临界路径。failure-sync 的大比例可能来自负载不均衡，不能解释成 halo 通信主导。
本轮未引入 interior/boundary 双阶段 callback。普通 Mat/Vec 路径仅把最终装配次序
组织成 `VecBegin→MatBegin→VecEnd→MatEnd`，允许两类独立 stash 通信同时推进；
这与 ghost 和 kernel 计算重叠是两回事。更高 rank 或多节点数据出现明确等待热点后再评估。

## 9. 验证、计时与证据边界

**已完成的本地验证。** `7f3d12e`、PETSc 3.23.7、Release 的 13 项选测全部通过，
0 failed、0 skipped。FSI 执行对照共 31 条命令，其中 1 个预期失败场景，最大 owned 场差
为 `4.72e-13`，最大归一化历史差为 `5.92e-14`；48 项局部方向导数检查的最大相对差
为 `2.24e-10`。移动 RCR 两 rank 全局 Jacobian FD 差约 `1.98e-8`。
回归还覆盖配置/选项/约束行失效、仅 rank 0 关闭复用、异常后恢复和线搜索 domain 恢复。[V1]

`2b0b30b` 的独立受影响验证为 `fsi_coo_verification` 1/1 通过，共 31 条命令、其中
1 个预期失败。与 `7f3d12e` 保存的 107 项场/历史差、迭代轨迹和 Jacobian/nnz 摘要
逐项比较无差异；未重跑未改路径的其他本地测试。该二进制 SHA-256 为
`d3fc4988ade068fcc2a6141635085efd8bc6cfc489da3ce2aa1a575836c6bfbb`。[V2]

此外，`7f3d12e` 的 CI 在 PR merge SHA `9393f27` 上实际执行 Release 51/51，
0 failed、0 skipped；Python 检查为 65 项，Website job 成功。Debug 和 PETSc 3.19.6
两个手动 job skipped。[V3]
`2b0b30b` 的后续 CI 在 merge SHA `a071ed2` 上实际执行 Release **28/28**，
另复用上述 `7f3d12e` 运行的 **23 项**已验证结果，合计覆盖 51 项；本轮 Python 检查
为 **6 项**，Website job 也成功。不能将覆盖 51 项写成新源码重新执行了 51 项，
也不能将两轮 Python 数量相加当成不同检查数。本地、修复复验与两轮 CI 分别保留来源。[V4]

**性能口径。** 基线二进制来自 `df6e9ac`；默认和线程试验使用固定 `7f3d12e` 二进制，
SHA-256 为 `109078ae403dbf2708febf9279cd368c198d51f0b155ffeb604c9a7fb87364cb`。
默认/线程 campaign 捕获的驱动来源为 `7f3d12e`，最终 COO 为 `2b0b30b`；
两个源码版本的驱动内容未变，脚本 SHA-256 均为
`ec96b06dc6b6378877a44a6c88d946d8834be1c1a6766b97e8c6aefb8bc61e5c`。
环境为共享 Linux x86-64 主机、Intel Xeon Platinum 8573C、进程可见 9 个 CPU，
未证明独占物理核；GCC 15.3、Open MPI 5.0.8、PETSc 3.23.7，每 rank 数值库线程为 1。
输入含 771/6,147 cells、703/5,367 DoF，两种 rank 数为 1/2；每 run 20 步，
预热 pair 不入统计，正式执行三次交替配对。默认与 COO 比较的 solver、容差和输出一致，
线程对照在同一候选二进制上比较每 rank 1/2 个 worker，使用 `--bind-to none`。[E3]

| 保留为最终证据的试验 | 装配配对中位数变化 | 墙钟配对中位数变化 | 墙钟配对范围 |
|---|---:|---:|---:|
| 默认，771 cells / 1 rank | −15.00% | −12.39% | −15.12% 至 +0.74% |
| 默认，771 cells / 2 ranks | −9.47% | −0.89% | −6.89% 至 +5.50% |
| 默认，6,147 cells / 1 rank | −20.34% | −12.53% | −16.56% 至 −0.57% |
| 默认，6,147 cells / 2 ranks | −18.95% | −8.25% | −17.69% 至 +18.36% |
| 最终 COO，771 cells / 1 rank | −13.82% | −12.82% | −13.06% 至 −11.60% |
| 最终 COO，771 cells / 2 ranks | −20.23% | −14.34% | −24.86% 至 −5.97% |
| 最终 COO，6,147 cells / 1 rank | −2.44% | −0.62% | −11.29% 至 +5.78% |
| 最终 COO，6,147 cells / 2 ranks | −19.95% | −10.97% | −15.54% 至 −8.24% |
| 线程 1→2，6,147 cells / 1 rank | −17.45% | −1.86% | −3.10% 至 +3.00% |
| 线程 1→2，6,147 cells / 2 ranks | −15.98% | −8.14% | −10.03% 至 +0.76% |

默认和最终 COO 的四组装配样本均下降；默认细网格单 rank，以及最终 COO 除细网格
单 rank 外的三组配置，墙钟配对也都下降。其余墙钟范围跨零，线程两 rank 的装配范围
也跨零，不能宣称每次执行都更快。
这些是**整组改动的收益**；residual COO 和 session reuse 未分别做性能消融，
不能把单个 timer 的变化解释成其中任一机制的独立收益。
默认细网格单 rank 峰值 RSS 的配对中位数反而上升 4.01%，两 rank 下降 7.45%。
最终 COO 的四组峰值 RSS 中位数下降 2.13%–8.89%；两组细网格分别下降 8.36%/8.89%。
精确图减少 nnz 并不保证所有配置的总 RSS 都下降。[E3]

| 最终 COO 配置 | 总初始化配对中位数变化 | 总初始化配对范围 | 峰值 RSS 配对中位数变化 |
|---|---:|---:|---:|
| 771 cells / 1 rank | −44.11% | −51.93% 至 −20.77% | −2.13% |
| 771 cells / 2 ranks | −20.17% | −35.85% 至 +13.84% | −3.28% |
| 6,147 cells / 1 rank | −39.90% | −46.04% 至 −29.73% | −8.36% |
| 6,147 cells / 2 ranks | −47.72% | −48.92% 至 −43.34% | −8.89% |

最终三项 campaign 共 80 runs / 1,600 steps，含预热；正式样本为 60 runs / 1,200 steps。
`7f3d12e` COO 的另 32 runs / 640 steps 仅保留为初始化回退的中间证据，
不能与最终 COO 混为同一个候选版本。默认图和最终 COO 在两种网格、1/2 ranks 中均为
27,226/260,010 nnz，矩阵 mallocs=0。最终 COO 的全部候选 run 最大 owned 场差
`4.44e-16`、最大历史差 `2.61e-15`；最终线程对照的对应差值均为零。[E3]

独立只读审计已通过，核对最终 **80 runs / 1,600 steps / 3,200 次线性修正**，
重算 **13,787 份文件哈希**并重读 **5,040 份体 VTU 分片**。跨三项 campaign 的
最大字段差为 `6.661338147750939e-16`，最大历史差为 `2.609024107869118e-15`，
最大 true residual / gate 比为 `0.00019408852157546064`。这些是对既有日志、CSV、
VTU 和摘要的独立复核，没有为审计额外执行求解器。[E4]

复现实验使用现有驱动，以下仅是可替换参数的入口示例：

```bash
python scripts/benchmark_fsi_assembly.py --baseline BASE --candidate CANDIDATE \
  --baseline-commit BASE_SHA --candidate-commit CANDIDATE_SHA \
  --mpiexec mpiexec --work NEW_DIRECTORY --subdivisions 4 8 --ranks 1 2 \
  --steps 20 --repeats 3 --baseline-assembly-report \
  --baseline-options=-fsi_coo --candidate-options=-fsi_coo
```

setup/assembly/solve 区间可能嵌套；`solver_generation` 证明对象生命周期，不证明加速。
当前基线已有初始化 timer，但各阶段因 residual COO 的设置位置而可能转移成本，必须同时
看总初始化；不能只看 PETSc system 阶段就宣称启动加速。上一轮已修复 POSIX
`wait(timeout)` 的墙钟轮询量化，本轮采用无轮询的 blocking wait 与独立超时 watchdog。[E1] [E3]

## 10. 适用范围、练习与参考

本方案服务固定拓扑、固定约束支撑的 assembled 低阶 Tet4 单体 FSI；不包含在线重分区、
通用 MPC、GPU、matrix-free 或多节点性能资格。线程需要足够本地工作量，COO 需要同时
考虑 setup 摊销和内存，求解器对象复用不能放宽物理停止条件。
练习：选一个含接口与移动出口的分区，独立枚举投影后的坐标集合，比较 K、U、唯一 nnz；
再构造只改变 prescribed 值和只改变约束行的两组调用，解释为何它们的会话生命周期不同。

- [S1] [物理依赖掩码](https://github.com/saitoasukakawaii/EONSim-new/blob/7f3d12ed6d0a1abc67d5f5606bf644b142a3197f/include/eonsim/fsi_coupling_pattern.hpp)；[有效映射与默认图](https://github.com/saitoasukakawaii/EONSim-new/blob/7f3d12ed6d0a1abc67d5f5606bf644b142a3197f/src/fem/reduced_layout.cpp)，`build_layout`。
- [S2] [贡献计划、端口、批次与接口力](https://github.com/saitoasukakawaii/EONSim-new/blob/7f3d12ed6d0a1abc67d5f5606bf644b142a3197f/src/physics/fsi.cpp)，`FsiAssemblyPlan`、`outlet_*_entries`、`solve_fsi_impl`。
- [S3] [Vec/Mat COO、会话和集体析构](https://github.com/saitoasukakawaii/EONSim-new/blob/7f3d12ed6d0a1abc67d5f5606bf644b142a3197f/src/algebra/nonlinear_system.cpp)，`prepare_residual_coo`、`Context::evaluate`、`Workspace`、`NonlinearSystem::solve`。
- [S4] [局部流体/ALE 核](https://github.com/saitoasukakawaii/EONSim-new/blob/7f3d12ed6d0a1abc67d5f5606bf644b142a3197f/src/physics/fsi_element.cpp)，`fsi_element`、`add_mesh_and_pressure`。
- [S5] [会话与失败回归源码](https://github.com/saitoasukakawaii/EONSim-new/blob/7f3d12ed6d0a1abc67d5f5606bf644b142a3197f/tests/verify_nonlinear_acceptance.cpp)，`verify_lifetime`；[FSI 执行对照源码](https://github.com/saitoasukakawaii/EONSim-new/blob/7f3d12ed6d0a1abc67d5f5606bf644b142a3197f/tests/verify_fsi_coo.py)。源码链接不代表执行收据。
- [S6] [行分桶 COO 去重修复](https://github.com/saitoasukakawaii/EONSim-new/blob/2b0b30bc2e1b036b8b97c9424cc6d41abd5af105/src/physics/fsi.cpp)，`FsiAssemblyPlan`，仅改变矩阵 COO 初始化去重；默认和线程路径的代码未改变。
- [P1] PETSc [MatPreallocatorPreallocate](https://petsc.org/release/manualpages/Mat/MatPreallocatorPreallocate/)、[MatSetOption](https://petsc.org/release/manualpages/Mat/MatSetOption/)，图填充与位置检查。
- [P2] PETSc [MatSetValuesCOO](https://petsc.org/release/manualpages/Mat/MatSetValuesCOO/)，重复项求和和 INSERT 语义。
- [P3] PETSc [VecSetPreallocationCOO](https://petsc.org/release/manualpages/Vec/VecSetPreallocationCOO/)、[VecSetValuesCOO](https://petsc.org/release/manualpages/Vec/VecSetValuesCOO/)，实际目标 Vec、负/远程行与重复项。
- [P4] PETSc [SNESDestroy](https://petsc.org/release/manualpages/SNES/SNESDestroy/)，collective 生命周期要求。
- [P5] PETSc [MatCreateBAIJ](https://petsc.org/release/manualpages/Mat/MatCreateBAIJ/)，统一方块存储定义。
- [E1] [上一轮证据与方法](https://github.com/saitoasukakawaii/EONSim-new/blob/4e25e2a7b1aa921dc473fe09cd5f9b3f09d4645f/docs/research/data/fsi-assembly-2026-11-25/README.md)；[正式汇总](https://github.com/saitoasukakawaii/EONSim-new/blob/4e25e2a7b1aa921dc473fe09cd5f9b3f09d4645f/docs/research/data/fsi-assembly-2026-11-25/performance-summary.json)。仅用作既有优化目标的证据。
- [E2] [历史 halo 成本重算](../../docs/research/data/fsi-performance-2026-11-25/overlap-review.json)；输入为上一轮归档中的两个 final `results.json`，不使用 pilot。输入 archive SHA-256 为 `3f992cdd5943dc489b3fc5a58ac76f8feea0c8a463eda4081f984f57dfd25656`。
- [E3] [本轮完整方法与证据索引](../../docs/research/data/fsi-performance-2026-11-25/README.md)、[性能汇总](../../docs/research/data/fsi-performance-2026-11-25/performance-summary.json)。归档中的 `perf2-default/results.json`、`perf2-threads/results.json` 为 `7f3d12e` 最终证据，`perf2-coo-final/results.json` 为 `2b0b30b` 最终证据，`perf2-coo/results.json` 为前版回退记录；各 campaign 保留命令、输入、环境、资源、二进制和计时来源。
- [E4] [最终独立审计](../../docs/research/data/fsi-performance-2026-11-25/independent-audit.json)，范围为三项最终 campaign，中间 COO 回退记录不混入正式汇总。
- [V1] [首版验证汇总](../../docs/research/data/fsi-performance-2026-11-25/validation-summary.json)、[原始 Release 收据](../../docs/research/data/fsi-performance-2026-11-25/release-summary-7f3.json)，对应本地 `7f3d12e` 的 13 项选测。
- [V2] [行分桶修复验证](../../docs/research/data/fsi-performance-2026-11-25/validation-bucket-summary.json)、[原始 Release 收据](../../docs/research/data/fsi-performance-2026-11-25/release-summary-2b0.json)，对应 `2b0b30b` 的受影响回归。
- [V3] [7f3d12e 源码 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45644776027)、[CI 收据](../../docs/research/data/fsi-performance-2026-11-25/ci-source-7f3.json)，PR merge SHA `9393f27daa8a1b03b7f4843e0706e885c81e03b6`。
- [V4] [2b0b30b 源码 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45649236866)、[CI 收据](../../docs/research/data/fsi-performance-2026-11-25/ci-source-2b0.json)，PR merge SHA `a071ed230ba3fe80ac2f56c33e8075a93c5bd5d3`；23 项复用来源为 `7f3d12e` 的 CI 运行。

本稿保留在 `website/drafts/` 供开发审核，不自动发布。
