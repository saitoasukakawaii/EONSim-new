---
title: "FSI Matrix-free 的下一步：缩小 P、缓存精确作用与保留物理粗模式"
description: "区分精确 Jacobian 作用、稀疏预条件近似、层内精度和物理接受，并说明哪些代码机制尚待大规模证据。"
contentStatus: draft
algorithm: "Reduced assembled FSI preconditioning, cached exact actions, discrete pressure enrichment, bounded coarse Krylov cycles, and compact native storage"
sourceReferences:
  - "https://github.com/saitoasukakawaii/EONSim-new/blob/50b41ae19067bd8853a482ab853805e23c096ec5/src/physics/fsi.cpp"
  - "https://github.com/saitoasukakawaii/EONSim-new/blob/50b41ae19067bd8853a482ab853805e23c096ec5/src/algebra/monolithic_fsi_mg.cpp"
  - "https://github.com/saitoasukakawaii/EONSim-new/blob/50b41ae19067bd8853a482ab853805e23c096ec5/src/algebra/nonlinear_system.cpp"
  - "https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/ksp/interface/itfunc.c"
eonsimCommit: "50b41ae19067bd8853a482ab853805e23c096ec5"
---

# FSI Matrix-free 的下一步：缩小 P、缓存精确作用与保留物理粗模式

本文面向了解有限元、Newton 和 Krylov 求解的科学软件开发者。学习目标是把四件事分开判断：
原方程的精确方向作用、预条件矩阵的近似、层内数据表示，以及最终物理接受。文章还说明
哪些机制能通过源码和小例确认，哪些性能目标必须等待网格加密和真实多节点实验。

本文为未发布算法草稿。完整选项和运行步骤见
[运行指南](../../docs/development/FSI_SCALABLE_MATRIX_FREE.md)，执行来源、原件与当前结果见
[FSI-SCALE-01 证据索引](../../docs/research/data/fsi-scale-01-2026-11-26/README.md)。

## 1. 问题定义与证据等级

研究对象是现有 EONSim 共形低阶单体 FSI。独立未知量包括流体速度/压力、结构速度与内部 ALE
位移；结构位移通过对应时间关系恢复。流固界面使用原测试/试探消元映射，支撑、压力面和 RCR
端口仍参与同一残量。所有必要字段和约束共同接受后才提交历史。

- **理论推导**：下文缩放和投影关系可直接按矩阵代数复核；不提供一般 FSI 网格无关、inf-sup 或混合精度稳定性定理。
- **代码实现**：当前生产版本为 `50b41ae19067bd8853a482ab853805e23c096ec5`，初始实现提交为 `e0edc6b83fa2a3b61ac64f758e7be9ab96f40539`；新增离散 pressure-supremizer 已完成同源 MPI 检查和小规模物理对照，各次通过和失败按实际源码分别记录。
- **数值验证**：独立 assembled tangent、原算子真残量、保存场/历史及执行计数的实际记录；失败证据和修复后复验分开保留。
- **性能证据**：仅对附有环境、尺寸、容差、rank/主机和测量方法的实际样本作结论。机器 SIMD、系数字节或小例迭代数都不能单独证明端到端收益。

## 2. 把精确算子与 P 的存储分开

设约束后的非线性残量为 \(\mathcal R(x)\)，当前精确线性化为

\[
J_kv=\left.\frac{d}{d\epsilon}\mathcal R(x_k+\epsilon v)\right|_{\epsilon=0}.
\]

外层 flexible Krylov 使用 \(J_k\)，预条件器使用近似 \(P_k\)。只把 \(J_k\) 改成 `MatShell`
还不能证明矩阵内存下降：如果 P 继续保存完整 Jacobian 图，主要稀疏存储仍存在。

本轮 `-fsi_reduced_pc true` 在物理分量图上省去流体方程对 ALE 列的预条件导数，再独立应用
测试和试探映射。AIJ 预分配与 COO 索引均使用这个较小图。流体 u/p、ALE 分量扩展、完整结构
块和共享界面速度贡献仍保留；移动 RCR 端口的额外耦合继续单独装配。
入口压力面中属于流体/ALE 的导数也从 P 省去。精确 Jv 仍保留全部这些导数。

这项近似的代价是 P 更便宜但可能更弱。评估需要同时记录 nnz、setup、外层迭代和总时间，
不能只报告单项字节减少。初始 307 DoF 双域和 350 DoF 移动 RCR 小例中，P nnz 分别约减少
23.42% 和 22.00%；这些数据说明符号图真正变小，不代表所有网格都获得相同比例。

源码对应：[分量依赖图](../../include/eonsim/fsi_coupling_pattern.hpp)、
[分布式符号图](../../src/fem/reduced_layout.cpp)、[FSI 装配计划](../../src/physics/fsi.cpp)。

## 3. 缓存中间量仍可得到精确 Jv

当前低阶核为每次 Newton 冻结状态准备中间数据，流体/ALE 为 132 个系数及压力面几何，固体为
27 个系数。它们保存体积、形函数梯度、原始场梯度、对流/稳定化中间量和材料响应所需量。
方向作用继续执行几何和物理链式求导；没有以“冻结缓存”省略对当前 ALE 或稳定化的导数。

以有限变形固体为例，变形梯度记为 \(F_s\)，其逆转置为 \(H=F_s^{-T}\)，体积比为 \(j_s\)。
缓存 \(H\) 和 \(c=\lambda\log j_s-\mu\)，对方向变形梯度 \(\delta F_s\) 计算

\[
\delta\log j_s=H:\delta F_s,\qquad
\delta P_s=\mu\delta F_s+\lambda\,\delta\log j_s\,H
-c\,H(\delta F_s)^T H.
\]

再加入同一时间链系数、一致质量和节点积分。缓存 \(H\) 等原始量不等于缓存完整材料或节点切线。
流体/ALE 也显式传递体积、梯度、相对速度、压力、SUPG/PSPG 和稳定化系数的方向导数。

缓存必须与当前 Newton 算子同步。P 按间隔复用时，精确方向缓存仍重新准备；线搜索试探残量
不能覆盖该冻结状态。非法几何和材料检查在准备时继续生效。局部验证将缓存作用与独立的完整
assembled tangent 比较，同时保留原残量有限差分检查。

`-fsi_matrix_free_simd true` 将四个单元的缓存和方向转成独立 lane，流体/ALE、固体分别批量
运算，尾批次以零方向填充。边界小核单独补充，PETSc 插入保持原单元顺序，因此没有在 SIMD
循环中引入共享节点回写竞争。实际 Release 反汇编在两个 batch 函数中观察到 packed double
算术指令；这证明代码生成使用 SIMD，不是吞吐提升测量。

源码对应：[流体缓存与 batch 核](../../src/physics/fsi_element.cpp)、
[固体缓存与 batch 核](../../src/physics/solid_element.cpp)、
[lane 算术](../../include/eonsim/action_lanes.hpp)。

## 4. 物理缩放与 FSI 粗模式

速度、压力、结构和 ALE 系数的尺度可能相差很大。本节将 assembled 预条件矩阵记为 \(A\)，
将插值记为 \(Z\)。当前实现按真实 DoF 语义分组，以全局行/列系数极值形成左右缩放 \(L,R\)，只在 MG 内建立

\[
A_s=LAR,\qquad B(r)=R M_s^{-1}Lr.
\]

若 \(N\) 是原物理坐标下的候选，缩放后必须使用 \(R^{-1}N\)，因为原修正与缩放修正满足
\(x=Ry\)。外层原算子、物理字段和约束门槛不变。数值变化时缩放和层级共同重建，其 setup
成本也必须计入实验。

独立行/列缩放下，第一层采用带权限制 \(Z^T W\)，其中 \(W=RL^{-1}\)。对应粗矩阵为

\[
A_c=Z^T W A_s Z=(RZ)^T A(RZ),\qquad r_c=Z^T W r_s.
\]

原物理坐标中的试探和测试空间由此都保持为 \(RZ\)，后续粗层继续普通 Galerkin。W 在 FP64
或 native FP32 限制之前作用；保留的是其对角向量，临时加权 FP64 矩阵及 product 引用在 setup
后释放。旧的 \(Z^T LARZ\) 是缩放坐标下另一种可定义的粗近似；本次改进针对粗测试空间及其
数值效果，两版精细方程和物理验收均保持原定义。

原候选已有各向量场平移/旋转及压力常数等方向。`fsi_candidates` 进一步保留压力坐标模式、
真实界面上的协同平移/旋转与界面压力模式。`116836b` 增加四个流体速度候选：在归一化参考
坐标 \(\hat x\) 下，

\[
v_0=\hat x/3,\quad v_i=e_i\hat x_i^2/2,\qquad
\nabla_{\hat x}\cdot v_0=1,\quad \nabla_{\hat x}\cdot v_i=\hat x_i\quad(i=1,2,3).
\]

这给常数和三个线性压力模式提供非零散度的配对速度；仅有平移/旋转候选的连续散度为零。
实现采用节点采样并排除约束行，上式是连续参考场关系，不意味着 P1 离散散度精确匹配。
候选容器有 36 个槽位，实际独立列数受局部语义、约束及去相关影响，不应报告为每个聚合体
均保留 36 个独立模式。插值仍保持 \(Z N_c=N_f\)。

局部 QR 去掉相关候选，粗系数逐层传播。局部正规能量谱增强仍是局部困难方向的代理；保留这些
模式不等于知道整个耦合系统的低频误差，更不能直接推出网格无关收敛。

### 从连续候选到局部离散压力响应

`50b41ae` 新增可选 `-monolithic_mg_pressure_supremizers true`，RCR bulk 前缀对应
`-rcr_bulk_monolithic_mg_pressure_supremizers true`。默认关闭，启用时要求同前缀的
`fsi_candidates=true` 和 `spectral_modes>0`。谱模态预算默认 2、允许 0–8，但开启本选项时
不能将预算设为 0。它只在细层原物理语义仍可区分压力和流体速度时构造响应，后续 mixed scalar
层不再生成新配对。

在聚合体 \(\omega\) 内，取实际算子的压力行/流体速度列块
\(B_\omega=(W A_s)_{p,u}\)，与最终物理 Galerkin 粗矩阵使用同一测试权重；未缩放时 \(W=I\)。
用本地速度块的绝对列和建立正对角代理

\[
H_{jj}=\sum_{i\in u_\omega}|(W A_s)_{ij}|,\qquad
D=(\min_j H_{jj})H^{-1}.
\]

设 \(V\) 为已有粗基限制到流体速度后的空间，\(Q=\operatorname{orth}(D^{1/2}V)\)。对已有
纯压力列中的方向 \(q\)，先形成

\[
s(q)=D^{1/2}(I-QQ^T)D^{1/2}B_\omega^Tq.
\]

这利用实际离散 \(B^T\)，但只使用对角速度能量代理，不是完整速度逆块的精确 supremizer。
实现对 \(B_\omega\) 作共同尺度归一化，通过小型响应 Gram 问题选取缺失响应能量较大的压力
组合，再仅在速度子空间中去相关，避免向 ALE 或结构分量引入支撑。最多采用
`min(2, spectral_modes)` 个方向，并从原 spectral 名额中扣除；零能量、相关或不可用的配对
不占名额。没有新增内层 KSP，也不增加既定聚合体、平滑或粗解调用预算，但会增加局部 setup 工作。

组成这些压力组合的原压力基列和响应列在 energy descent 中整体冻结，冻结标记随 transfer
halo 传播。由此保护的是选中局部配对的 \(q_i^T B_\omega s_j\)；代码在形成最终 FP64
`MatPtAP` 后读回实际粗子块，与冻结前的独立计算比较，相对变化门槛为 `1e-10`。数值刷新
重新生成这些响应。`pressure_supremizer_modes`、`pressure_paired_aggregates` 报告实际数量；
`pressure_pair_min_singular` 是选中行归一化局部块的最小奇异值，
`pressure_pair_relative_change` 是这次 FP64 setup 配对审计的变化。

上述量没有覆盖所有压力方向、后续粗层或全局 inf-sup 条件。尤其它们在 native transfer
量化之前计算，不能把 `1e-10` 审计误差解释为 FP32 作用的精确配对保证；最终仍由原算子真实
残量和物理门槛接受。新增机制已有 `50b41ae` 的同源 MPI 检查和两组物理结果，详见第 8 节；
它们确认局部配对和有限输入上的正确性，窗口近网格无关目标仍未达到。下面 `30e2941` 的
K/RSS 结果继续保留原源码归属，没有转记为新机制的验证。
源码对应：[局部响应与 coarse 审计](../../src/algebra/monolithic_fsi_mg.cpp)、
[接口范围](../../include/eonsim/monolithic_fsi_mg.hpp)。

丰富候选会形成局部秩下限，可能出现下一层只减少很少行的弱粗化。
`-monolithic_mg_max_coarse_ratio` 在启用 `fsi_candidates` 时默认 0.8，其他配置默认 1，
允许范围为 (0,1]。若 proposed coarse rows / parent rows 超过上限，就以 parent 为最粗层，
不继续创建该 proposed 层。`weak_coarsening_stop_rows` 和 `weak_coarsening_proposed_rows`
报告停止处规模，未触发时为零。这控制层级工作量，不改变物理或 Krylov 容差；较大的最粗问题
也可能增加 coarse solve 成本，需要实测。

V-cycle 保持默认。可选 W-cycle 在下一层得到第一次修正后，用该层剩余残量再访问一次，
最后合并修正。它可能降低外层迭代，也可能因粗工作增加而更慢，需要完整成本对比。

### K-cycle：最多两个方向的粗残量最小化

`30e2941` 增加 `-monolithic_mg_cycle k`。对非最粗层的完整耦合算子 \(A_c\)，以行最大系数
的倒数构造对角度量 \(D_c\)，在至多两个递归预条件 Arnoldi 方向组成的空间内求

\[
\min_{\alpha_1,\alpha_2}
\left\|D_c\bigl(b_c-A_c(\alpha_1z_1+\alpha_2z_2)\bigr)\right\|_2.
\]

第一次递归作用产生 \(z_1\)；需要时按 Arnoldi 方向生成第二个递归输入。实现对作用向量做
两遍 modified Gram–Schmidt，并同步变换修正向量，形成小 QR 而不解正规方程。按层内精度
识别相关方向，实际返回的修正再重算完整加权粗残量。若有限残量增大，就选取试探空间内的
零修正并记录拒绝；非有限作用仍作为 PC 失败传播。这不改变粗方程、物理候选或外层容差。

这个循环的工作有界，但并非免费。含 \(L\) 层时，每个非平凡应用至多调用最粗求解
\(2^{L-2}\) 次，\(L\le2\) 时一次；还增加粗 matvec、工作向量和 dot/norm 请求。外层要求
flexible Krylov。不能只比较更少的外层迭代，而忽略每次预条件作用增加的工作。

`monolithic_mg_stats` 记录 coarse solves/iterations、smoother applications、方向、降秩、拒绝、
归约请求和返回粗残量的最大比值。它们跨数值重建累计，应按 rank/path/solver generation
取末值，不能把每步快照相加；RCR response 的内部作用也会计入。归约字段是 VecDot/VecNorm
请求计数，不是实测 MPI 包数，缓存范数可能不发生通信。

物理 driver 的 `mono_kcycle` 保持严格线性容差，`mono_optimized` 显式保留 V-cycle。
从该源码起 `mono_all` 也显式选 K-cycle，但同时包含 inexact Newton；旧 `116836b` 同名模式
使用 V-cycle。跨版本比较需同时注明 driver 和二进制，不能把名字相同视为配置相同。
`50b41ae` 另增 `mono_supremizer`，以严格 V-cycle 的 `mono_optimized` 为对照，只额外开启
离散压力响应；当前 `mono_all` 也加入这个新开关。旧 `30e2941` 的 K-cycle 与 RSS 数据不含此项。

### 实际失败：约束张满后的投影舍入噪声

能量下降要求 \(\delta ZN_c=0\)。增强候选可能张满某行允许的插值支撑，此时可行下降方向应为零。
初始实现的正交投影只剩浮点舍入噪声，随后的一维精确线搜索却用极小曲率将噪声放大，导致
候选重构检查失败。

修复在投影后范数不大于 `1024 * epsilon * 未投影梯度范数` 时将该数值噪声归零。候选、物理
方程和原重构门槛保持不变。这个错误说明：可行空间退化时，投影“几乎为零”与线搜索中的
“可以作为非零方向”不是同一个数值判断。失败原件和后续复验应分别记账。

源码对应：[候选、缩放、受约束能量下降和循环](../../src/algebra/monolithic_fsi_mg.cpp)。

## 5. 选择性 Vanka：核心覆盖与重叠选择分开

自适应 patch 并不只平滑选中的强耦合区域。每个活动实体的核心始终存在；真实界面实体及
满足下式的实体才扩展所配置的图重叠：

\[
\frac{\sum_{j\notin\operatorname{core}(i)}|P_{ij}|}
{\sum_j|P_{ij}|}\ge\theta.
\]

只要实体任一行达到阈值即可触发；当前默认 \(\theta=0.25\)。数值变化时重建选择，避免把
初始一次筛选称为动态自适应。粗层默认 overlap 为零，保留完整混合聚合体核心，防止沿稠密
Galerkin 图扩展出过大局部问题。

需要共同观察核心/扩展 patch 数、所有 rank 的活动行覆盖、最大 patch、分解次数与外层迭代。
更少扩展通常减少局部工作，但不保证整体收敛更快。
源码对应：[patch 选择与存储](../../src/algebra/interface_patch_pc.cpp)。

## 6. Native FP32 的系数存储与刷新峰值

既有单精度循环保留 FP64 setup 矩阵。Native 路径在形成 float CSR、传递系数和 patch 数据后，
释放非最粗层 FP64 矩阵、传递矩阵、patch 子矩阵以及 Galerkin product 对操作数的引用。
如果漏掉最后一类引用，表面销毁矩阵句柄也不会释放实际存储。

局部残量细化使用保留的均衡 FP32 系数；不能形成可用 FP32 因子时明确失败，不悄悄保留一套
FP64 因子作为兜底。数值变化仍需临时重建 setup，然后再次释放。

实际 n8 回归说明仅检查释放后的系数还不够。`116836b` 的一次 native-only 对照中，
系数字节约下降 5.8%，LU 字节减半，但 normalized peak rank RSS 最大值从
210,153,472 增至 283,660,288 bytes，约增加 35%。这是两个单次样本的内存观察，
没有计时结论；原件为 `native-only-n8-116836b/independent-audit.json`，保留于证据索引。

源码分析找到三类具体分配：重建时旧 native hierarchy 与新 FP64 setup 同时存在；patch
残量系数从原稀疏 Mat 变成了稠密 float；去重的 halo 列向量 `erase` 后仍保留原 nnz 容量。
`30e2941` 分别作了以下修改：

1. 数值刷新先保留 fine metadata，释放旧 coarse solver、层系数/因子和工作向量，再建新 setup。
   失败保持不可应用的 metadata-only 状态，允许后续合法刷新重新构造；外层 P 不被释放。
2. 局部系数在稠密 float 和 CSR 之间按实际字节择小。CSR 的 uint16 局部列号和 uint32 行偏移
   先检查范围；LU 仍稠密。直接读取稀疏行转换，不再建立每个 patch 的稠密 double 暂存。
3. 约束 lifting 直接提取源矩阵列，不复制整份 FP64 矩阵。是否跳过零 lifting 由全局判定控制，
   空 owner 与 remote constraint 仍完成一致通信。释放 setup IS、语义副本和不再使用的工作数组。
4. Float 系数/索引按实际计数预分配，压缩去重列映射的容量，避免逻辑 size 掩盖常驻 capacity。

这些修改针对生命周期和存储问题。下面的同源配对测量给出该输入上的 RSS 改善；需要把
局部显式存储与整个进程的观测分别报告，才能限定这个结论。

| 存储/算术 | 本实现范围 |
| --- | --- |
| 非粗层稀疏系数、传递、局部矩阵/因子 | 保留 FP32 系数，释放相关 FP64 setup 副本 |
| 最外层 P 和最粗层求解 | 保留 FP64 |
| PETSc 向量、Krylov 和 MPI 数据 | 保留 FP64 |
| setup 峰值、索引/halo 元数据、总 RSS | 需要各自口径；下文 pair 测得进程 RSS，未独立剖析 setup 瞬时分配峰值 |

因此当前名称表示 native coefficient storage，不表示整个程序已经是 FP32 向量和 FP32 MPI。
带宽是否成为瓶颈、精度转换与重建是否抵消收益，都需要实测。
`fp32_value_bytes` 包含 native patch/lifting 系数，不含 LU；`factor_bytes` 独立计因子，
`native_index_bytes` 只计局部 patch CSR 索引。总 RSS 还包括其他索引、向量、通信、outer P
和暂态 setup，不能把这些局部计数直接解释为进程峰值。
源码对应：[float sparse](../../include/eonsim/native_float_sparse.hpp)、
[MG 释放路径](../../src/algebra/monolithic_fsi_mg.cpp)、[层 smoother](../../src/algebra/fsi_level_smoother.cpp)。

内存报告也需要清楚的定义。每次记录的 normalized peak 取当前观测 RSS 与原始 OS peak 的最大值，
`system_peak_rss_bytes` 保留 Linux `getrusage` 的原值。PETSc 当前 RSS 和系统高水位的采样途径
不同，初始 cluster smoke 曾因原始 peak 小于另一路 current 估计而在审计时失败。归一后的量
满足该次观测的 peak/current 关系，但不能冒称纯系统高水位，也不能由修复统计口径推断新的内存收益。

### 同源 n8 配对：RSS 改善小于局部存储降幅

`30e2941` 的固定二进制在同一 n8 输入、5,367 DoF、2 ranks、一个 host、三步上各运行一次
FP64 与 native-only。双方共同开启 `-solver_rank_report`；除输出路径和 native 开关外参数
相同，均为 V-cycle，没有启用 scaling、增强候选、adaptive patch 或 K-cycle。
两者均通过原严格线性与物理门槛，各完成六次 Newton 校正、六次真实残量检查且零拒绝，
外迭代为 206/205。完整保存轨迹及最终场差 `7.534806112374781e-13`、历史差
`2.3314683517128287e-15`；native 真实残量/原门槛最大 `0.0069361029682299446`。

| 观测，bytes | FP64 | native-only | 变化 |
| --- | ---: | ---: | ---: |
| 最大 rank 的归一化峰值 RSS | 210,673,664 | 202,129,408 | −4.0557% |
| 各 rank 归一化峰值之和 | 316,915,712 | 303,300,608 | −4.2961% |
| 最大 rank 的原始 OS 峰值 | 210,206,720 | 202,129,408 | −3.8426% |

首次报告的保留系数从 29,978,976 降至 13,430,456 bytes，LU 从 40,025,728 降至
20,012,864 bytes，native patch CSR 索引另占 2,764,526 bytes；三项合计为
70,004,704→36,207,846 bytes。Native 最后一次报告的这三项为 15,867,872、20,012,864、
3,967,996 bytes，合计 39,848,732 bytes，sparse/dense patch 数为 1,175/248。
它们随线性化的非零项变化，不能只取首次最小值当作整个求解的固定存储。FP64 只有初始
报告，native 每次重建另有报告，比较时保留这一差异。

单次 pair 表明这组生命周期与存储改动修复了该输入上的 RSS 回归，尚不能推断普遍的
内存缩减比例、实测带宽下降或端到端加速。局部存储合计不包含其他索引、向量、MPI 缓冲、
outer P 和运行时分配；rank 峰值之和也不是同一时刻测得的总分配峰值。Rank 1 的最后
current RSS 还由 100,478,976 增至 101,171,200 bytes，不能笼统写成每个 rank 的所有内存均下降。

独立审计重新读取 64 份 VTU（含边界）、比较 432 组数值数组和整数拓扑/编号，核对 112 个
hash 条目、110 个不同运行/输入文件及 54 个既有 direct 参考文件；不从 VTU 重建每次 J、b、dx。
原命令/source/binary/input/output hash 与 rank 明细见证据索引内
`native-paired-30e2941/invocation.json`、`independent-audit.json`、`rank-memory-summary.csv`。
这组 RSS 观察没有附带计时结论。

## 7. MPI overlap、forcing 和跨步修正空间

Matrix-free overlap 在方向 halo 传输期间计算纯 owned 单元，再计算 halo 单元。分组依据约束后
试探 aliases，端口项在通信完成后单独加入一次。冻结状态本身已准备完整；不会用过期 halo
状态解释当前 Jv。实际重叠收益依赖通信进展和本地工作比例，`owned_cells` 不是隐藏率。

### 候选收敛、真实残量与公开 API 的状态顺序

某些缩放配置中，Krylov 递推残量已经满足停止条件，实际 \(b-Jx\) 却仍超出原门槛。
`-nonlinear_true_residual` 对 `monolithic_mg` 默认开启，其他 recipe 可显式开启；支持
unpreconditioned FGMRES/PIPEFGMRES 的 assembled 和 matrix-free 路径。
只有原 convergence test 提出候选成功时才额外构造当前真实残量，并用同一个原测试检查该范数。
不改变容差、迭代预算和最终物理接受；忽略残量即可报成功的 `skip` / `converged_maxits` 策略
与此保护不兼容。

初版 `8410818` guard 暴露了一个具体状态顺序错误。Convergence callback 的 `reason` 参数
指向求解器停止原因；直接让原测试先写入正值，会影响随后调用的公共 `KSPBuildSolution`。
PETSc 3.23.7 的入口看到原因已非 `ITERATING` 就复制旧 `vec_sol`，不会调用当前 FGMRES
解重构。所谓“真实残量”因此基于旧 restart 基解，造成大量假拒绝，并让 PIPEFGMRES 的
happy breakdown 变成失败。

正确顺序是先把候选原因保存在局部变量，在公开回调原因仍为 `ITERATING` 时调用
`KSPBuildResidual`，最后才发布真实检查后的原因。这遵守公开 callback/API 契约，不读写
PETSc 私有字段。修复之后也仍须保留真实 breakdown：若候选被真实残量拒绝且没有可继续的
Krylov 方向，库可以返回 `KSP_DIVERGED_BREAKDOWN`，不能把所有拒绝都描述为必然自然重启。
[PETSc v3.23.7 的 `KSPBuildSolution` / `KSPBuildResidual`](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/ksp/interface/itfunc.c)

此保护增加的 Jv 计入原 matrix-free 作用计数；`true_residual_seconds_rank0` 又包含这些作用
及解重构/范数工作，所以不能再与 `matrix_free_seconds_rank0` 相加当作两个互斥阶段。
验收应分别记录 checks 和 rejections，且有真正触发拒绝分支的回归，不能仅以 checks 大于零
证明已修复假收敛。

### 中间精度与跨步初值

Inexact Newton 的 forcing 使用连续 Newton RHS 范数变化，并受原 KSP rtol 和显式最大值限制。
每次修正按当次 \(\eta_k\) 检查当前原算子真残量：

\[
\|J_k s_k-b_k\|\le a_{\rm KSP}+\eta_k\|b_k\|.
\]

最终仍重新计算物理残量，逐字段和约束检查，再共同提交。节省早期线性工作不能通过修改最终
验收来实现；测试也应分别识别中间 forcing 门槛和最终物理门槛。

Recycling 保存至多指定数量的成功修正方向。每次使用当前算子重新计算其像，正交化后生成
使当前残量降低的初值；不利或相关方向丢弃，失败会话清空缓存。这是 solution/correction
subspace recycling，没有实现 GCRO-DR，也没有保存完整 Arnoldi 基。额外 Jv、归约和向量内存
可能超过省下的迭代成本，不能只报告成功投影次数。

源码对应：[FSI owned/halo 作用](../../src/physics/fsi.cpp)、
[冻结算子生命周期及线性策略](../../src/algebra/nonlinear_system.cpp)。

## 8. 十二项目标如何验收

| 方向 | 需要的证据 |
| --- | --- |
| MG 收敛优化 | 同物理问题网格加密，记录每次修正迭代、层级、粗工作和总时间；近似网格无关仍待证明 |
| Reduced P | 同输入完整 P/reduced P 的实际 nnz、矩阵分配、原算子残量和物理解对照 |
| 物理缩放 | 原始尺度的物理接受、候选缩放一致性、迭代与 setup 成本 |
| FSI 粗空间 | 候选重构、跨层传播、约束保护，以及真实强耦合参数范围 |
| Adaptive Vanka | 全活动行覆盖、扩展选择随数值变化、局部分解和外层成本 |
| Partial assembly | 独立 tangent/Jv 对照、当前代准备、缓存复用和非法状态检查 |
| Native FP32 | 实际释放的副本、保留系数字节、粗解/向量边界、总 RSS 与原残量 |
| SIMD | 混合单元尾批次数值对照、实际对象 SIMD 指令，以及独立吞吐测量 |
| MPI overlap | owned/halo 作用和错误回收、1/多 rank 等价、同环境配对计时 |
| Inexact Newton | 每次 forcing 的真残量和最终原物理门槛，不混淆两种标准 |
| Recycling | 当前算子投影、跨成功会话复用、失效清空、额外 Jv/归约成本 |
| 大规模 benchmark | 实际百万约束后 DoF、真实多节点放置、固定问题强扩展及可比 DoF/rank 弱扩展 |

局部验证入口是 `fsi_element_jacobian`、`solid_element_jacobian` 和相关 MG/MF MPI CTests。
物理驱动为 `tests/verify_fsi_multigrid.py`；强弱扩展入口为
`scripts/benchmark_fsi_block_scaling.py --campaign strong/weak`。
完整可复制命令在运行指南，实际执行命令及结果在证据索引，不用示例命令代替执行记录。

大规模驱动记录实际主机名、约束后 DoF、原始日志及 hash；`--minimum-nodes` 和
`--minimum-dofs` 检查观测值，不估算节点或自由度。Weak 网格/rank 一一配对，另检查实际
DoF/rank 漂移。计时至少三个样本，零计时重复只产生正确性 smoke。
大规模路径审计最终场/拓扑及全部接受历史、线性残量，不保存所有中间体场；网格生成和 METIS
preparation 仍为串行全网格工作。

当前结果还保留 action accounting 缺失引起的初始证据失败：即使离线物理场相符，也不能把
缺失所请求机制记录的原 campaign 记为通过。后续真实残量差距、初版 guard 状态错误和 RSS
审计失败同样按源版本保留，不能用别的成功子案例覆盖。修复后的复验与旧通过证据的适用范围分别列入
[证据索引](../../docs/research/data/fsi-scale-01-2026-11-26/README.md)。本文不预填尚未完成 campaign 的总数或时间。

### 已完成的定向修复验证

下面的通过记录均按各自源码引用。`50b41ae` 的 MG MPI 1/2/4 检查已通过，见
`unit-50b41ae-summary.json`；同源严格网格 9/9 与 default/moving 物理 15/15 的具体结果列在
本节末尾。旧 K/RSS 结果保持原源码归属，不因后续版本加入新机制而改变历史通过数。

正确公开 API 状态顺序的 guard 在 `6378f4cca035bcf8a29150ef21588528c70aa824` 通过
matrix-free MPI 1/2/4-rank 检查，以及 moving-RCR 的 direct、scaled MG、matrix-free
PIPEFGMRES 三次物理对照。Scaled MG 实测 176 次候选检查、167 次拒绝和 441 次外层迭代，
原算子残量及物理场门槛通过。这是拒绝分支和正确性证据，不把较高迭代成本解释为收敛优化完成。
对应原件为 `residual-guard-6378-summary.json`。

`116836b9d4143a280759a2e69e6c1b31156fb616` 的 MG MPI 1/2/4-rank 检查通过，包含同一物理
候选 span、关闭能量/谱变化时的两层缩放投影不变量，以及弱粗化停止行为。该代数验证支持
新增投影和层级工作控制的契约。同源固定 n=4/6/8、2-rank 网格 campaign 已完成 15/15
物理通过；另一个 default/moving campaign 15/15 通过，独立审计覆盖 45 个接受步、119 次
线性校正和 200 个体场分片。两批分别记录为 `grid-scaling-116-summary.json` 与
`physical-116836b-independent-audit.json`。

`30e2941` 的 patch、MG、层 smoother MPI 1/2/4-rank 共九项通过，包含 compact native 表示、
remote constraint/空 owner、源 Mat 释放后作用，以及 native 重建失败后的恢复，记录为
`unit-30e2941-summary.json`。同源 K-cycle 网格 12/12 通过物理检查，但有限窗口收敛目标
未达到；native-only 两次对照通过原门槛，RSS 观察见前一节。

### 中间网格加密结果没有证明网格无关

`707a6a6` 的 2-rank 固定线性容差实验得到以下每个 Newton 线性修正平均外迭代数。
增强组合 `mono_optimized` 同时启用物理缩放、FSI 候选、adaptive Vanka 和 native FP32。
原件对应证据索引中的 `grid-scaling-707-summary.json`。

| 实际约束后 DoF | 基线 `mono` | 增强组合 `mono_optimized` |
| ---: | ---: | ---: |
| 703 | 17.17 | 19.83 |
| 2299 | 25.17 | 38.33 |
| 5367 | 34.33 | 81.33 |

基线迭代约增长两倍，增强组合约增长 4.1 倍。这是该版本的性能退化证据；增加物理候选、
缩放或降低存储精度并未自动获得更好的网格扩展。MG 改进仍在继续，必须把未来复验与本组
中间结果分开。含 inexact Newton 的 `mono_all` 改变中间线性精度，因此它的较低迭代数
不能单独作为 MG 收敛改进的证据。

后续 `116836b` 保持原严格线性门槛，在同一窗口得到：

| 实际约束后 DoF | 基线 `mono` | V-cycle `mono_optimized` |
| ---: | ---: | ---: |
| 703 | 17.17 | 16.17 |
| 2299 | 25.17 | 26.67 |
| 5367 | 34.33 | 37.83 |

增强组合仍有约 2.34 的最大/最小迭代比，尚未展示近似网格无关。新 driver 在运行前声明
相同严格门槛下 n=4/6/8 窗口的比值不超过 1.3 为有限窗口目标，并与物理接受分开报告。
即便这个窗口达标，也不能替代百万自由度、多节点或一般 FSI 收敛证明；inexact 模式不适用
这个固定线性精度目标。

### `30e2941` 的 K-cycle：外层迭代减少，粗层工作增加

固定三档网格、2 ranks、三个时间步，direct、`mono`、增强 V 的 `mono_optimized`、
同一组合 K 的 `mono_kcycle` 共 **12/12** 物理通过。以下均保持严格线性容差，数字是每次
Newton 校正的平均外迭代数，每个运行有六次校正：

| 实际约束后 DoF | 基线 V | 增强 V | 增强 K |
| ---: | ---: | ---: | ---: |
| 703 | 17.17 | 16.17 | 16.33 |
| 2,299 | 25.17 | 26.67 | 24.67 |
| 5,367 | 34.33 | 37.83 | 33.67 |
| 最大/最小比 | 2.0000 | 2.3402 | 2.0612 |

三种模式都没有达到预先声明的 **≤1.3** 窗口目标。K 在后两档减少了增强 V 的外层迭代，
但不能把通过物理比较或局部粗残量下降解释为网格无关收敛或全局 inf-sup 稳定性。
独立审计核验 36 个接受步、72 次校正、192 个体场分片、639 个 artifact hash 及 15 个命令
日志；最大场差 `9.398315459208106e-13`、历史差 `5.684341886080802e-14`，严格真实残量
与原门槛之比最大为 `0.008201356570989377`。原件为 `grid-kcycle-30-summary.json` 和
`grid-kcycle-30e2941-independent-audit.json`。

这一增强组合在三档分别有 4/4/5 层。每次 PC 作用的 coarse solves 从 V 的 1/1/1 增为 K 的
4/4/8，层 matvec 从 6/6/8 增为 23/23/51，smoother applications 从 6/6/8 增为 14/14/30；
K 还增加 36/36/84 次 VecNorm/VecDot 请求。这些是按 rank、path、solver generation 的
末次累计快照归一后的工作量，不重复累加接受步，也不把请求次数冒称为实测 MPI collective。

这次共享节点窗口的 V 求解时间是 2.778/12.993/54.032 秒，K 是 2.840/13.157/57.771 秒。
减少外层迭代没有转化为本次求解加速；这只是一轮正确性执行中的时间观察，不是重复计时研究。
后续粗空间机制必须按自己的源码和结果单独验证，不能继承本组物理通过作为性能证明。

### `50b41ae`：离散响应改善迭代，但窗口目标仍开放

同源二进制与 driver 在 n=4/6/8、2 ranks、三个时间步上比较 direct、严格增强 V 的
`mono_optimized` 和只再加入离散响应的 `mono_supremizer`，共 **9/9** 通过。
每个运行有六次 Newton 校正，线性与物理门槛保持原定义：

| DoF | 增强 V，总迭代 / 校正 | 增强 V + 离散响应，总迭代 / 校正 | 每次 setup 的响应 / 聚合体 |
| ---: | ---: | ---: | ---: |
| 703 | 97/6 = 16.1667 | 92/6 = 15.3333 | 20 / 10 |
| 2,299 | 160/6 = 26.6667 | 138/6 = 23.0000 | 56 / 28 |
| 5,367 | 227/6 = 37.8333 | 199/6 = 33.1667 | 118 / 59 |

平均迭代最大/最小比由 `2.3402061855670104` 降至 `2.163043478260869`，仍超过事先设定的
**1.3**，所以有限窗口目标保持 **OPEN**。减少这三档迭代支持这一组输入上的改善，不构成
近网格无关、普遍加速或全局 inf-sup 稳定性的证明。

实际局部配对块的最小行归一化奇异值为 `0.1498419920143982`，FP64 setup 配对变化最大
`3.6505504122740457e-16`；这些统计不包含 native 量化后的精确配对保证。独立审计核验
27 个接受步、54 条线性记录、144 个体场分片、480 个 artifact hash 及 12 个命令日志。
最大场差 `3.577971252610723e-13`、历史差 `8.049116928532385e-16`、owner/ghost 差为 0；
原严格残量/门槛最大 `0.00872921617003258`，36 次 guard 检查零拒绝。对应原件为
`grid-supremizer-50b41ae-summary.json` 和 `grid-supremizer-50b41ae-independent-audit.json`。

### 同源双域与移动 RCR：正确性通过不等于普遍更快

最终 default/moving campaign 在 domains-r1、domains-r2、moving-rcr 上各运行 direct、
增强 V、增强 K、增强 V + 离散响应和 `mono_all`，共 **15/15** 通过。下表为总外层迭代 / Newton 校正：

| 案例，DoF / ranks | 增强 V | 增强 K | 增强 V + 离散响应 | `mono_all` |
| --- | ---: | ---: | ---: | ---: |
| domains-r1，307 / 1 | 72/6 | 70/6 | 71/6 | 38/11 |
| domains-r2，307 / 2 | 68/6 | 69/6 | 67/6 | 36/10 |
| moving-rcr，350 / 2 | 134/9 | 189/9 | 133/9 | 112/12 |

Moving RCR 的 K-cycle 比 V 多用迭代，离散响应的改善也仅为 134→133。`mono_all` 含 inexact
forcing、recycling、reduced P 及缓存等多项机制，其中间线性精度和校正次数不同；不能把 112
直接当作 MG 同精度收敛改善。这里没有重复计时研究，不声明这些配置普遍更快。

独立审计核验 45 个接受步、117 条线性记录、200 个体场分片、643 个 artifact hash 及
18 个命令日志。最大场差 `2.909998353395338e-10`、历史差 `4.168998479769925e-12`，
仍满足原 `2e-9` 场/历史比较门槛；owner/ghost 差为 0。严格真实残量/门槛最大
`0.007862816997846028`，inexact 按当次 forcing 检查的最大比值 `0.9962145448716808`；
最终物理接受比值最大 `0.5379066790177952`、约束比值为 0，RCR 恒等式缺陷最大
`4.0766001685454967e-17`。96 次 guard 检查没有拒绝。

带离散响应的模式每次 setup 实际生成 8 个方向、覆盖 4 个聚合体；最小局部奇异值为
`0.14278562400145994`，FP64 setup 配对变化最大 `5.11600760109919e-16`。
原件为 `physical-supremizer-50b41ae-summary.json` 和
`physical-supremizer-50b41ae-independent-audit.json`。审计同时确认真实机制计数、coarse
工作和 native 保留存储；真实残量仍读取运行时原算子诊断，没有从 VTU 重新构造 J、b、dx。

## 9. 已知限制与进一步研究

本轮代码机制覆盖请求的十二个方向，性能目标仍有各自边界。近似网格无关、百万自由度和
多节点强弱扩展没有因为增加驱动或开关而自动完成。Native FP32 不是全向量/全通信单精度；
recycling 不是 GCRO-DR；局部压力/界面候选不提供一般稳定性证明；reduced P 的耦合省略
可能在更强几何反馈下增加迭代。
`50b41ae` 两批仍是单 host 小规模验证，本轮最大实际规模是既有 smoke 的 10,387 DoF。
**百万自由度、真实多节点强弱扩展没有运行，近网格无关目标仍未达到。**

下一次实验应明确区分：算子计算、缓存准备、P 装配、层级 setup、平滑、粗解、通信、额外
recycling 工作和端到端时间。比较时固定离散模型、时间步、容差及物理接受，保留失败样本。

## 10. 参考源码与思考

本草稿的理论说明为上文矩阵恒等式及方向导数推导；具体行为以固定源码提交为依据，未把任何
外部文献算法名称作为等价实现证明。主要参考如下：

1. 固定源码 `50b41ae19067bd8853a482ab853805e23c096ec5`，`src/physics/fsi.cpp`、`fsi_element.cpp`、`solid_element.cpp`：分量图、状态准备、精确方向作用及缓存。
2. 同提交，`src/algebra/monolithic_fsi_mg.cpp`：`fine_data`、`pressure_enrichment`、`audit_pressure_pairs`、`minimize_transfer_energy`、`Hierarchy::equilibrate`、`minimize_coarse_residual`、`release_native_before_rebuild` 和循环作用。
3. 同提交，`src/algebra/interface_patch_pc.cpp`、`include/eonsim/native_float_sparse.hpp`：选择性重叠、局部精度、稀疏存储。
4. 同提交，`src/algebra/nonlinear_system.cpp` 的 `LinearPolicy`：forcing、当前算子投影、真残量与最终物理接受。
5. [单体 FSI 契约](../../docs/architecture/L2_MONOLITHIC_FSI.md)与[运行指南](../../docs/development/FSI_SCALABLE_MATRIX_FREE.md)：模型、测试/试探映射及适用范围。
6. [FSI-SCALE-01 证据索引](../../docs/research/data/fsi-scale-01-2026-11-26/README.md)：实际命令、source/tree、二进制/对象 hash、成功/失败原件和性能环境。
7. PETSc v3.23.7，[`itfunc.c`](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/ksp/interface/itfunc.c) 的 `KSPBuildSolution` / `KSPBuildResidual`：公开构造入口对停止原因的分支；[`fgmres.c`](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/ksp/impls/gmres/fgmres/fgmres.c) 和 [`pipefgmres.c`](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/ksp/impls/gmres/pipefgmres/pipefgmres.c) 的 cycle：候选收敛及 happy-breakdown 处理。

思考：如果 P 的 nnz 降低而总时间增加，应先检查哪些阶段？当粗候选张满插值支撑时，能量下降
还剩多少自由度？为什么使用当前 J 的投影比直接复用旧解更容易给出可检验的残量保证？
