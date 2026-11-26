---
title: "数值与性能基准草稿：FSI 五项并行优化"
description: "记录块 AMG、MPI 通信、单元核 SIMD、自适应预条件器和并行 HDF5 的实现、验证与性能证据边界。"
contentStatus: draft
benchmark: "FSI five-track optimization, PR 55"
sourceReference: "https://github.com/saitoasukakawaii/EONSim-new/pull/55"
eonsimCommit: "27889707a3c650d532c2845b2f6da7fc5d2324d4"
---

# 数值与性能基准草稿：FSI 五项并行优化

**未发布草稿。** 本稿面向维护有限元、PETSc 和并行输出代码的开发者，记录五项实现、已经执行的验证及共享单机性能范围。[归档证据索引](../../docs/research/data/hpc-five-track-2026-11-26/README.md)保存原始日志、失败尝试、字段与统计审计。

本轮生产代码对应 `27889707a3c650d532c2845b2f6da7fc5d2324d4`，整程序基线构建源为 `88e6c3359b742735877177eb4584b987caae1790`，变更入口为 [PR #55](https://github.com/saitoasukakawaii/EONSim-new/pull/55)。生产代码和仓库验证驱动的变更均先同步远程，再构建或用于验证；一次性活动命令和脚本随证据归档。运行时检出的测试驱动提交与生产二进制提交分开记录，不能用后来的 HEAD 替换已经测量的二进制来源。

## 1. 验证目标与当前结论

本稿包含代码验证和性能评估，没有实验数据支撑的物理模型验证，也没有把 1–2 个 MPI rank 的单机测量解释为大规模集群可扩展性。

| 优先级与任务 | 已实现的机制 | 本稿已核验的证据 | 当前性能结论 |
| --- | --- | --- | --- |
| P0 FSI Block AMG | 语义联合速度块上构造局部图聚合与粗模态，再由 PETSc GAMG 处理 Galerkin 辅助问题 | 703–17,839 DoF、1/2 rank 的 112 次网格对照通过 | 2 rank 上相对旧 twolevel 的迭代差异随网格变化；未实现网格无关迭代数 |
| P0 MPI 通信优化 | owned/halo 装配阶段与 ghost exchange 重叠；稳定字段范数合并归约 | 1/2/4 rank 代数回归、同一二进制开关对照、真实 FSI 字段和残量审计 | 同一二进制对照中 ghost 计时配对中位变化 −41.34%；整程序 wall 范围跨过零 |
| P1 单元核 SIMD | 独立 AD 导数通道、标量重载和乘积累加消除临时向量 | 解析导数、别名与非有限数回归、编译器向量化报告、隔离微基准 | 四组单元核配对 wall 中位变化为 −30.99% 至 −34.58% |
| P1 自适应 PC 更新 | 新鲜 Jacobian 配合有界的 PC 数值复用；漂移、年龄、迭代和时间系数触发重建 | 生成算例 USER 更新 10→2–3；32 步动脉强漂移时仍刷新 61–62 次 | 不以重建次数减少直接替代求解时间收益 |
| P2 并行 HDF5 I/O | 分布式 owner 数据集、collective hyperslab 写入、XDMF 原子发布 | 合成边界测试、真实 Poisson/FSI、原生 HDF5 对照、实际 ParaView 读取 | n=32 输出阶段快于 ASCII，慢于已有 binary VTU；保持显式选择 |

表中的负变化表示候选耗时减少。所有范围均为实际样本最小值至最大值，**不是置信区间**。实现能力、正确性通过和性能收益是三个独立结论，不能相互替代。

## 2. 理论对象与源码实现

### 2.1 FSI 块粗空间

主方程仍是完整的单体 Newton 系统 $J\Delta x=-R$；物理场之间的交叉导数没有因为预条件优化而删除。联合速度块 $A_v$ 包含流体与结构的活动语义行。`aggregate` 路径先按照局部矩阵图及节点身份形成有界聚合，构造常数或参考坐标刚体候选，正交化并去除相关方向，形成分布式稀疏插值 $P$，然后使用

$$
A_c=P^T A_v P.
$$

该第一层粗空间保留约束消元后的真实分量和机械模态；后续在 $A_c$ 上调用标量 GAMG。它与把每个缩减节点强制标为三个完整分量的块矩阵有不同的适用条件。`twolevel` 保留原有按 owner/domain 构造粗空间的路径；`gamg` 保留直接在活动标量行上构造层级的路径。`rigid` 可以用于 `twolevel` 和 `aggregate`，直接 `gamg` 仍只接受 `constants`。这些都是源码能力，不能单凭粗空间公式宣称网格可扩展性。[S1]

实现使用 Galerkin 粗算子、局部平滑和粗层校正；`aggregate` 的辅助 GAMG 默认复用插值，数值算子更新仍由相应 setup 管理。非对称 FSI 块及可变内部求解要求在真实配置中核验外层 FGMRES、实际层数、粗算子维数、PC 失败状态和真残量。只看到选项字符串 `gamg` 不足以证明运行了预期层级。

### 2.2 MPI 重叠与稳定范数

`NonlinearAssemblyPhases` 把一次残量或 Jacobian 装配分成两个阶段。在 `VecGhostUpdateBegin` 与 `VecGhostUpdateEnd` 之间，只运行读 owned 试探值的回调；ghost 值完成后运行 halo 回调。FSI 单元分类检查 **缩减试探自由度的 alias**，以免界面或刚体代表的远程依赖被网格节点 owner 掩盖。端口和其他需要完整展开状态的贡献在 halo 阶段处理一次。[S2]

已发起的 exchange 必须先结束，再共同处理 owned 回调的异常。协议同时检查所有 rank 是否采用相同阶段与归约选项。普通插入和 COO 装配共用该顺序；空 owned rank 也参与必要通信。PETSc 的 Begin/End 接口定义了 ghost 更新的配对调用，[R1] 但能否隐藏网络时延仍依赖 MPI 的实际进展和可用 owned 工作量。

对于字段 $f$，接受判据继续使用缩放后的 RMS 和独立的约束最大误差：

$$
q_f=\sqrt{\frac{1}{N_f}\sum_{i\in f}\left(\frac{R_i}{s_f}\right)^2},
\qquad
c_f=\max_{i\in C_f}\left|\frac{R_i}{s_{c,f}}\right|.
$$

实现把每个局部平方和表示为 $(a,b)$，其中 $a$ 是绝对值尺度，$b=\sum_i(r_i/a)^2$。合并两个分片时，以较大尺度为公共尺度再合并 $b$，同时归约 $c_f$。这样一次 `MPI_Allreduce` 就能完成旧路径的最大值与平方和两次归约，同时避免直接平方极小/极大残量。全零字段和非有限残量保持明确处理。`field_reduction_calls` 只统计该物理接受范数路径，不代表 KSP、诊断、失败同步及其他全局通信的总次数。[S2]

### 2.3 SIMD 与数据流

前向 AD 的导数通道彼此独立，例如

$$
\partial_i(ab)=(\partial_i a)b+a(\partial_i b).
$$

`Dual<Width>` 将这些通道表达为连续循环；启用构建选项且编译器支持 OpenMP 时使用 `omp simd`。标量重载避免为被动系数生成完整零导数数组；`+=`/`-=` 原位更新，`add_product` 将乘积与累加放在一次通道遍历中。流体/ALE 残量中的梯度、应力、对流和稳定化累加采用该接口。[S3]

优化保留每一通道的算术依赖，不启用 fast-math，不添加跨通道归约。标量重载保留 `0*Inf`、`0*NaN` 等原有传播；别名更新先保存原值，防止 `a+=a` 或累加器同时作为乘数时读到已修改数据。OpenMP SIMD 是当前线程内的向量执行机制，[R2] 不创建单元线程团队。关闭 SIMD 指令提示后，通道循环与数据流优化仍存在，编译器也可能自动向量化。因此本稿的旧版/新版微基准衡量整个单元核修改，不能将全部收益归因于一条 pragma。

### 2.4 自适应预条件器

该策略始终保留当前残量与 Jacobian，只允许 PC 数值因子在有界窗口中复用。每次采样当前矩阵的对角线 $d_i$ 和绝对行和 $s_i$；相对漂移使用该行当前/参考绝对行和的较大值归一化，不以近零压力对角线或跨物理场的单一全局尺度归一化。漂移超过阈值、复用年龄到限、迭代增长、物理时间系数变化或失败均触发重建。[S2]

FSI 传入 `dt`、各积分时间系数和广义 alpha 系数作为上下文。未知上下文只允许当前 solve 内复用。一次旧 PC 导致 KSP 迭代数耗尽且没有 PC 硬失败时，驱动保留上一个接受的 Newton 状态和原始物理接受基线，强制重建 PC 后重试至多一次；容差和每次尝试的迭代上限保持；至多一次重试可再消耗一份原预算，累计工作计入报告。其他失败不由该特例吞掉。

减少 PC 更新可能增加 Krylov 工作；PETSc 的复用接口也明确存在这一权衡。[R3] 因而最终证据应同时给出刷新/复用/重试计数、监测时间、线性迭代和总耗时，不能只报告少做了几次 setup。

### 2.5 并行结果输出与发布语义

`-vtu_format hdf5` 为每个快照写一个共享 HDF5 payload 和一个 XDMF 入口。节点只由 owner 写入，单元由其所属 rank 写入，连接关系使用全局代数节点编号；全局稳定 ID、物理标签、owner、点字段和 ALE 坐标都保存。体域与边界复用点数据集。字段和网格保持分布式，通信只交换计数和小型 schema，不汇聚完整场或网格到根进程。[S4]

所有 rank 按共同顺序创建元数据并参与 collective hyperslab 写入，包括本地无单元或空选择的 rank。HDF5 的 collective 调用约束与实际数据传输模式是两件需要分别检查的事。[R4] `/Partition/io_modes` 记录非空写入数、实际 collective 次数和其他实际模式次数；诊断数据集自身的写入不计入统计。该数据来自原生传输属性查询，不能用“请求了 collective”替代“实际执行了 collective”。[R5]

每次写入先生成唯一 payload。全部 rank 成功 flush 并显式关闭 HDF5 后，rank 0 才用一次 rename 原子替换稳定的 XDMF 入口。XML 发布失败保留旧入口并删除本次未发布候选；旧 payload 仅在本写入器的内存记录证明其来源时回收，不把任意现存 XDMF 内容解析为删除目标。真正的 collective HDF5 失败会终止 communicator，避免部分 rank 独自清理集体句柄；本地输入和 XML 错误按共同路径传播。这是完成快照的发布协议，没有增加 fsync 持久性保证。

时间集合使用独立的 `*.series.xdmf`，不会覆盖最后一个静态快照入口。该功能用于结果输出，不扩展 checkpoint/restart 格式。

## 3. 数值设置、默认值和支持范围

### 3.1 实际开关

| 选项 | 默认值 | 本轮实现与限制 |
| --- | --- | --- |
| CMake `EONSIM_ENABLE_ELEMENT_SIMD` | `ON` | 定义 `EONSIM_ELEMENT_SIMD`；仅在 OpenMP 编译支持存在时使用 SIMD 指令提示，无热循环运行时开关 |
| CMake `EONSIM_ENABLE_OPENMP` | `ON`，可用时启用 | 公共头文件模板与核心目标共用编译支持；未找到 OpenMP 时使用普通循环 |
| `-fsi_threads N` | `1` | 原有单元批次线程数；范围 1–256，独立于 SIMD。本文性能对照保持每 rank 一个单元线程 |
| `-fsi_overlap true\|false` | `false` | FSI owned/halo 重叠，显式开启；普通插入和 COO 均有代数验证 |
| `-nonlinear_fused_reductions true\|false` | `true` | 字段范数一次合并归约；所有 rank 的选择必须一致 |
| `-pc_plan_velocity_solver` | `split` | 可选 `split/coupled/twolevel/gamg/aggregate`；新粗空间不改变默认求解器拓扑 |
| `-pc_plan_velocity_coarse_space` | `constants` | `rigid` 仅适用于 `twolevel/aggregate`；直接标量 `gamg` 不支持刚体六模态 |
| `-pc_plan_velocity_aggregate_nodes` | `16` | 仅在 `aggregate` 路径可显式设置，范围 2–4096；为聚合目标规模，不保证边界聚合具有恰好该节点数 |
| `-nonlinear_adaptive_pc true\|false` | `false` | 仅支持兼容的默认 Newton、当前 Jacobian 和 FGMRES；手工 PC lag/reuse、EW 等冲突配置报错 |
| `-nonlinear_pc_max_reuse` | `4` | 1–1000 次有界复用；需连同漂移与迭代触发一起解释 |
| `-nonlinear_pc_change_tolerance` | `0.1` | 有限值，范围 $(0,1]$ |
| `-nonlinear_pc_iteration_growth` | `1.5` | 有限值且不小于 1；迭代触发阈值取倍率阈值与参考迭代数加 2 的较大者 |
| `-vtu_format ascii\|binary\|hdf5` | `ascii` | HDF5 需要 parallel HDF5 与明确 communicator；不静默回退串行或分片模式 |
| `-vtu_boundary true\|false` | `true` | 控制结果边界输出；HDF5 边界与体域共享点存储 |
| `-vtu_compact_boundary true\|false` | `true` | VTU 紧凑边界设置，在 HDF5 中没有独立的紧凑点副本 |

HDF5 支持当前一阶网格结果及混合 Tri3/Quad4 P1 输出；CLI 对二次 scalar 空间显式拒绝 HDF5。输入的输出后缀通常为 `.vtu`，在 HDF5 模式也接受 `.h5/.xdmf`，实际入口使用 `.xdmf`。精确选项来源见 [S1]–[S5]。

### 3.2 已完成性能实验

FSI 对照使用 `cases/fsi/generate_domains.py` 生成的独立流体/固体双域：n=4 时流体/固体分别为 384/387 个 Tet4，n=8 时为 3,072/3,075 个 Tet4。材料与载荷采用生成算例的数值单位：$E=100$、$\nu=0.3$，流体密度和黏度为 1，压力为 1。约束标签和输入网格完整记录在每组 `case.yaml` 与输入哈希中；这些参数不是针对特定实验装置的标定。

两个规模均使用默认 backward Euler、$\Delta t=0.02$、5 个接受时间步，每步保存结果。所有对照固定相同分区和 SuperLU_DIST 直接线性解法：`-ksp_type preonly -pc_type lu -pc_factor_mat_solver_type superlu_dist`。Newton 容差为相对 `1e-10`、绝对 `1e-12`，最大 30 次；速度/结构的残量尺度为 1，压力/ALE 尺度为 0.01。该组合装配实验用于隔离执行路径，不能作为新 AMG 求解器性能证据。

HDF5 成本对照使用 n=32 Poisson 网格，共 35,937 节点、196,608 个 Tet4。ASCII、binary、HDF5 采用同一生产二进制与输入，分别在 1/2 rank 上运行一个预热三元组和三个测量三元组，并轮换执行顺序。

环境为 PETSc 3.23.7 Release、Open MPI 5.0.8、GCC 15.3.0、HDF5 1.14.6（`H5_HAVE_PARALLEL=1`），共享 Linux x86-64 主机报告 AMD EPYC 9V74。进程可见 9 个逻辑 CPU；不能由主机型号的 80-Core 字样推断容器有 80 个可用核。依赖库线程数固定为 1，性能运行期间暂停本团队其他构建和计时任务，主机外部负载不受本实验控制。

## 4. 正确性与计时定义

对照脚本先要求每一步接受、预期 solver/PC 实际生效、物理字段与保存时间网格一致，再统计耗时。真线性残量门限为

$$
\|b-A\Delta x\|_2\le 10^{-12}+10^{-10}\|b\|_2.
$$

保存字段和历史量按稳定身份及相同时间比较，绝对差上限为 `2e-9`。组合装配及同一二进制 MPI 对照的最大字段差均为 `2.220446049250313e-16`，最大历史差均为 `3.2751579226442118e-15`；Newton/线性迭代轨迹均保持每步 `[2,2]`，每次运行检查 6 组保存状态。没有在后处理阶段通过任意压力平移降低这些误差。

计时采用每个匹配样本的比值

$$
\delta_k=100\left(\frac{t_{\mathrm{candidate},k}}{t_{\mathrm{baseline},k}}-1\right),
$$

再报告 $\delta_k$ 的中位数和范围。该数值一般不等于“两个独立时间中位数之比”。预热样本排除。整程序 wall 使用带独立超时监护的阻塞子进程等待，包含启动、输出和退出；每步分项按最大 rank 时间统计，部分区间彼此重叠，不能全部相加得到总时间。`ghost_seconds` 包含通信发起、等待及相关拷贝，不包含两者之间的 owned 计算；`ghost_overlap_seconds` 记录 pending 期间完成的 owned 工作，不单独证明 MPI 后台传输的比例。

HDF5 的 `seconds(max_rank) ... output=` 包括写入、库 flush/close 和入口发布，不包括 fsync 物理落盘保证。并行输出正确性期间的 wall 与其他验证重叠，不纳入性能样本；第 5.4 节只使用另行隔离的性能活动。

## 5. 已完成结果

### 5.1 SIMD：正确性、生成指令和单元核成本

本轮针对性测试 **7/7 通过**：`ghost_overlap_mpi1/2/4`、`nonlinear_acceptance`、`nonlinear_acceptance_mpi`、`fsi_element_jacobian` 和 `fluid_element_jacobian`。这组执行对应 `bb4fd3be8afd657bba6749d7fbc01b74bc8594fc`；后续 `2788970` 只在别处调整自适应策略，相关 SIMD/MPI 测试源未变。不能把这些结果记作在后续提交重新跑过。

单元测试覆盖宽度 1/7/24/28 的解析导数、累加别名、NaN/Inf/有符号零。ghost 测试覆盖普通/COO、零 owned rank、owned/halo × residual/Jacobian × recoverable/fatal 异常；每次注入失败后使用同一系统和变化后的目标继续成功求解。独立 RMS oracle 验证 `1e-200` 和 `1e150` 残量尺度，补充既有的极小残量下溢拒绝测试。

等价 Release 编译参数生成的单个 FSI object 报告 AD 通道使用 16-byte 向量化；反汇编含 `addpd/mulpd/subpd/divpd`。这是生成指令的证据，不作为单独的时间收益。报告未使用 fast-math、整应用重编译或非基线 CPU 指令集。

微基准每个稳定化配置一个预热对和五个交替顺序测量对；每条核记录计算 50,000 次。24 次进程调用生成 48 条核记录，其中 40 条测量记录形成 20 对，8 条预热记录排除。所有 Jacobian 累积 checksum 完全相等，前后可执行文件哈希一致。

| 稳定化 | 压力面 | 基线 wall 中位数，s/50,000 次 | 候选 wall 中位数，s/50,000 次 | 配对 wall 变化中位数 | 配对 wall 范围 | 配对 CPU 中位变化 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 固定 tau | 无 | 0.358792 | 0.237839 | −32.14% | [−40.06%, −27.39%] | −32.14% |
| 固定 tau | 有 | 0.364051 | 0.241018 | −30.99% | [−38.94%, −30.46%] | −31.04% |
| 当前度量 | 无 | 0.446073 | 0.285311 | −34.58% | [−42.76%, −32.41%] | −34.58% |
| 当前度量 | 有 | 0.462727 | 0.299759 | −34.24% | [−39.95%, −33.14%] | −34.23% |

证据：`simd-mpi/kernel-benchmark.json`、`kernel-*.log`、`vectorization.json`、`fsi-vectorization.log` 和 `independent-kernel-audit.json`。后一审计独立回放 24 个日志哈希、48 条记录和 20 个测量对，没有再运行数值计算。这些结果只覆盖本次流体/ALE 切线输入，不能推导整个求解器、所有单元类型或多核扩展收益。

### 5.2 MPI：同一二进制的开关对照

n=8、2 ranks、5 步，双方都使用生产提交 `2788970` 的同一可执行文件。基线显式关闭 overlap 和 fused reductions，候选显式开启两者。一个预热对加三个测量对共 8 次运行，全部通过物理与求解审计；这一对照排除了旧/新 SIMD 实现的差别，但没有把 overlap 与归约两项再分别分离。

每步日志中 `field_reduction_calls` 从 **6 降为 3**，`ghost_exchanges` 仍为 **6**。因此这里减少的是字段范数的全局归约次数，并未减少 ghost 交换总数。

| 指标 | 配对变化中位数 | 三对样本范围 |
| --- | ---: | ---: |
| ghost 计时 | −41.34% | [−54.42%, −23.54%] |
| 装配计时 | −6.57% | [−9.62%, +5.85%] |
| 线性求解计时 | +1.37% | [−11.45%, +9.83%] |
| 整程序 wall | −0.89% | [−10.67%, +8.03%] |

ghost 计时的独立中位数为基线 `0.000797528 s`、候选 `0.000417693 s`，在整步成本中占比很小。整程序 wall 的样本范围跨零，当前证据支持ghost 阶段计时改善和归约次数减少，不支持稳定的端到端加速承诺。证据：`mpi-ablation/results.json` 及其命令、分区、二进制 receipt 和原始日志。

### 5.3 旧/新整程序组合对照

基线源 `88e6c335` 与候选源 `2788970` 比较，候选启用 overlap 和 fused reductions。n=4/8 × 1/2 rank，每组一个预热对加三个测量对，共 **32 次通过的运行**、12 个测量对。因为双方单元实现和通信路径均不同，该实验只给出组合效果。

| n | ranks | 装配配对中位变化 | 装配样本范围 | 整程序 wall 配对中位变化 | wall 样本范围 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 1 | −17.51% | [−18.61%, −6.52%] | −1.00% | [−7.70%, +5.77%] |
| 4 | 2 | −11.19% | [−16.63%, −9.46%] | +1.95% | [−4.70%, +8.88%] |
| 8 | 1 | −15.99% | [−18.79%, −15.53%] | +1.44% | [−2.47%, +2.45%] |
| 8 | 2 | −13.95% | [−13.97%, −0.68%] | −1.23% | [−4.39%, −0.07%] |

所有测量对的装配时间均改善；wall 结果混合，线性直接解法占据较多时间。组合对照中的 ghost 子计时也没有在各规模一致改善，不能用整包比较代替第 5.2 节的同二进制通信结论。现有数据不支持把各模块百分比相加为总加速。证据：`assembly-combined/results.json`。

### 5.4 并行 HDF5：数据等价、实际读取和输出成本

`parallel_hdf5` 与 `parallel_hdf5_mpi` **2/2 通过**，覆盖 owner-only 数据、无单元 rank、全局空数据集、混合二维拓扑、边界方向、schema 不一致、入口发布失败、旧结果保留、已知 generation 回收及实际 collective 诊断。

真实 Poisson 和独立流/固双域 FSI 分别以 ASCII/HDF5 在 1/2 ranks 运行，**8/8 求解成功**。FSI 保存 `0.02` 和 `0.04` 两个接受时刻及终值。通过原生 `h5dump -x -m %.17g` 与 ASCII VTU 独立对照，**14/14** 数据检查通过，共检查 1,298 条节点记录和 2,226 个单元；点字段、坐标、整数身份、物理标签和有向连接关系完全相同。每个观测到的非空 HDF5 写入都报告 collective，其他模式计数为零。

已安装的 ParaView `XDMFReader` 实际读取 **10 个入口**，其中 4 个时间集合均识别 `[0.02,0.04]`，各时刻流体/固体数据非空；另有静态合成输出读取通过。该结论来自 reader 执行，不是 XML 格式检查。`paraview.json` 原始记录前含环境 UCX 提示行，随后保存成功的 reader JSON；该提示没有阻止本次完成，也未从证据中删除。

独立 n=32 性能活动共 24 次通过的求解，其中 6 次预热排除、18 次计入性能。下表为输出阶段，单位秒。

| ranks | ASCII 中位数 | binary 中位数 | HDF5 中位数 | HDF5 相对 ASCII 配对中位变化 | HDF5 相对 binary 配对中位变化 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.117940491 | 0.012727172 | 0.031628952 | −73.22% | +152.78% |
| 2 | 0.057236560 | 0.012047565 | 0.031440347 | −44.73% | +164.99% |

1 rank 的 HDF5/ASCII 配对范围为 `[−74.51%,−72.70%]`，HDF5/binary 为 `[+28.10%,+237.86%]`；2 ranks 分别为 `[−49.71%,−33.48%]` 和 `[+124.36%,+216.01%]`。每个 HDF5/ASCII 样本都改善，每个 HDF5/binary 样本都退化。本次共享主机、本地文件系统及热页缓存条件下，已有 binary VTU 更快。

| ranks | ASCII 总字节 / 文件数 | binary 总字节 / 文件数 | HDF5 总字节 / 文件数 |
| ---: | ---: | ---: | ---: |
| 1 | 12,402,006 / 2 | 13,837,624 / 2 | 11,552,661 / 2 |
| 2 | 12,236,742 / 6 | 13,926,468 / 6 | 11,552,765 / 2 |

性能活动末尾六次独立 ASCII/HDF5 数据对照完全一致，共检查 252,498 条节点记录和 1,253,376 个体域/边界单元。非空传输计数每 rank 为 `[14,14,0]`，三种输出模式在每个匹配三元组内的迭代、残量、范数、积分及误差指标相同。证据：`io/manifest.json`、`data_comparison.json`、`paraview.json` 和 `io/performance/summary.json`。

### 5.5 聚合 AMG 与自适应 PC：完整网格对照

生成双域模型使用相同的压力 1、Young 模量 100、Poisson 比 .3、五步 `dt=.02` 及原有四字段尺度；每个规模/进程数共享一个分区。外层请求 `rtol=5e-11`、`atol=5e-24`，显式真实线性残差门槛保持 `1e-12 + 1e-10*||rhs||`，场量和物理历史门槛保持 `2e-9`。只将 Newton 次数从物理历史等值项中分开，实际次数仍记录并审计。

n=4/6/8 × 1/2 rank，direct 参考与四种迭代配置共 **102/102 runs、510 接受步、1,020 次线性修正**通过。每个迭代模式先做一次未计时准入/预热，再做三次交错测量。n=12 的 **10/10 runs、50 步、100 次修正**作为更大规模正确性扩展，不用于新的性能统计。独立回放 112 次运行、672 组保存状态及 5,998 条文件哈希断言通过；最大场差 `3.9968e-15`、物理历史差 `3.2085e-14`。

下表是两进程下五步累计外层迭代数，不能与内层最后一次调用的迭代快照混用：

| n | 约束消元后总 DoF | twolevel rigid | aggregate rigid | aggregate + adaptive | 第一粗空间维数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4 | 703 | 150 | 152 | 152 | 60 |
| 6 | 2,299 | 192 | 187 | 188 | 174 |
| 8 | 5,367 | 264 | 244 | 244 | 393 |
| 12 | 17,839 | 414 | 370 | 370 | 1,164 |

粗层实际使用两级 GAMG；n=12 的两进程底层算子有 13 个方程。第一粗空间随网格增长，原始联合速度算子的耦合仍完整保留。该数据支持局部聚合和辅助 GAMG 在这些网格上可运行，并在较大两进程算例降低相对旧粗空间的外迭代；迭代仍随网格增长，不能写成 mesh-independent 或多节点扩展已证明。

n=8、2 ranks 的独立三样本中位数为：

| 响应 | 外迭代 | 线性阶段 / s | 整程序 wall / s |
| --- | ---: | ---: | ---: |
| coupled nodal | 199 | 0.425123 | 1.028140 |
| twolevel rigid | 264 | 0.247413 | 0.854776 |
| aggregate rigid | 244 | 0.270783 | 0.880059 |
| aggregate + adaptive | 244 | 0.195364 | 0.771388 |

单独的 fresh aggregate 比 twolevel 少迭代，总线性阶段仍更耗时，未形成普遍时间优势；本轮没有将 setup、apply 与 inner 成本分别隔离。对 aggregate 的同轮 fresh/adaptive 配对，n=8/2-rank 线性阶段中位变化 **−27.852%**，范围 **[−34.163%, −19.988%]**；wall 为 **−13.350%**，范围 **[−16.753%, −5.323%]**。所有配置仍组装 10 次完整 J；此例实际 USER Schur 更新和刷新决策均 **10→2**，复用 8 次。n=4/6 为 **10→3**，并未仅根据策略计数推断矩阵更新次数。

六组 fresh/adaptive 配对 wall 中位数均下降，但 n=8/1-rank 范围包含 **+3.892%**；性能收益受本机波动、矩阵变化和 PC 设置成本影响。原始统计同时保留所有模式和网格，不能只拿最优点替代整个结果集。

### 5.6 完整动脉轨迹：保留一次严格失败并修正停止请求

原 `rtol=5e-11` 请求下，粗网格 fresh aggregate 的第 14 步第二次线性修正出现残差间隙：PETSc 报告 `CONVERGED_RTOL`、47 次迭代及估计范数 `7.35209e-20`，显式计算 `||J dx-rhs||=2.93746e-19`，超过独立门槛 `2.42972e-19`，比值 **1.2089702**。该轨迹虽然输出完整、物理场也一致，仍按失败保存。PETSc 3.23.7 的 GMRES 残差 API 明确区分估计范数与显式残差；正的退出 reason 不是独立验收的替代物。[残差 API][R6]及[FGMRES 源码][R7]解释了该差别。

测试驱动 `ceaa680c5c2c521abc71f0014337dc3ea16796a9` 增加公共 `--outer-rtol`，原默认 `5e-11` 保留，只额外提供更严格的 `1e-11`。对 fresh/adaptive、两档网格一律使用同一个更严格请求；不改物理、生产默认或原 `max(1e-23, 1e-10*||rhs||)` 验收门槛，也不重复搜索不同参数。

该有界修正后的 quick **6/6**、full **30/30** 通过，共 **312 接受步、624 次真实线性修正**。full 内包括六条完整 32 步轨迹（两条直接参考、四条迭代轨迹），另有四步预热和交错样本；计时样本只代表四步窗口。最大真实残差/门槛 **0.8439101**，最大五场相对峰值差 **7.5813e-12 < 2e-6**。原失败位置显式残差降为 `2.05047e-19`，仍按同一独立门槛判断。

32 步自适应轨迹在粗/细网格分别刷新 **61/62** 次、复用 **3/2** 次；fresh 对应实际 USER 更新均为 64 次，完整 J 仍均为 64 次。强变化压力轨迹没有可推广的 PC 复用收益，因此本稿不把生成算例的 80% 更新削减移植到动脉结论。四步计时也没有给出统一的自适应优势。

两个失败来源分别保留：首轮 mesh 驱动遗漏 `-pc_plan_report`，18 个模式的粗空间元数据审计失败；原 32 步动脉的独立真实残差失败。前者在 a63aa2e 补齐报告后才重跑，后者在 ceaa680 推送后才采用公共更严格请求。不存在修改旧 receipt 将失败改写为通过。

## 6. 收敛、守恒与适用边界

已完成 FSI 活动验证了相同接受时间网格、字段接受、真线性残量和输出一致性；它们没有重新测定空间/时间观测阶，也没有在本报告中增加独立的实验质量、动量或能量基准。保存历史的相等证明执行路径保持既有离散结果，不能代替对物理模型的独立验证。

SIMD 的向量指令、MPI 的归约次数和 HDF5 的 collective 计数是实现与执行机制证据；相应计时只对本次输入和环境有效。当前所有整程序性能结果限于单机 1/2 ranks。代数正确性扩展到 4 ranks，不等同于 4 ranks 性能或跨节点强扩展。并行文件系统、大规模端口/刚体组合、不同编译器和高阶 HDF5 输出均不能从这些数据推出。

`-fsi_overlap`、`aggregate`、自适应 PC 和 HDF5 保持显式选择；本轮没有因小规模数据改写默认物理算法。SIMD 编译选项和稳定合并范数默认开启，其失败/非有限数行为分别由针对性回归覆盖。

## 7. 可复现信息与证据索引

### 7.1 来源与构建身份

| 对象 | 来源 / SHA256 |
| --- | --- |
| 生产实现 | `27889707a3c650d532c2845b2f6da7fc5d2324d4` |
| 整程序基线构建源 | `88e6c3359b742735877177eb4584b987caae1790` |
| SIMD/组合/MPI 运行时驱动 HEAD | `9c4af0dbb20e8ce059423b2c7e6a6f061cd40313` |
| AMG 网格运行时驱动 HEAD | `a63aa2e3d0283dbe489912451f9073feac5fc85e` |
| 最终动脉驱动 HEAD | `ceaa680c5c2c521abc71f0014337dc3ea16796a9` |
| 候选 `eonsim` | `b4fe71840296bb0533d95a59c906d3062b14d3bfc1203dac60dfb1f590d0b3d9` |
| 基线 `eonsim` | `c57ab409a125d759fd51513cf5c03024feec2f67a0f224fd1aa40cc87be1cf09` |
| 候选 `verify_fsi_element` | `4f304b8350abfee7f69a8f1df8d5ace700791d2eb9c0d05e04bfe58b3aadb17e` |
| 保留的基线 `verify_fsi_element` | `ea9eb55e7c643a3216d3df5db1024ae7347984dc5a524d66b7903e316f9f15c3` |

基线微基准 executable 是在主线合并点 `f8dbd6991f8057fc84d0a49dc6d9c9b3c38028fe` 时保存的已有产物，本活动没有重新构建它；其绑定身份以 `kernel-benchmark.json` 和 `baseline-sha256.txt` 为准，不能只根据保存时的 checkout 推断新的构建过程。

自动复制的 `*-build_receipt.json` 是保留目录中 `7e8868e` 的历史产物，不能作为本轮候选构建证据。
当前身份由实际 ELF 哈希、`binary-sources.json`、显式 build-source、同步后增量构建日志和源码 CI 固定。
旧 receipt 原样保留并标注其范围，未重写为当前提交。

### 7.2 已执行命令的复现形式

以下命令从仓库根目录运行；新输出目录与原证据分开。重新计时前应确保没有同时运行的构建或本项目性能任务，并保持已记录的工具链与线程设置。命令展示不代表本草稿又执行了一轮计算。

针对性测试与单元核：

```bash
bash build/locked.sh ctest --test-dir build/cloud-3.23.7-release -j1 \
  -R '^ghost_overlap_mpi[124]$|^nonlinear_acceptance(_mpi)?$|^(fsi|fluid)_element_jacobian$' \
  --output-on-failure

bash build/locked.sh build/cloud-3.23.7-release/verify_fsi_element --kernel-samples 50000
bash build/locked.sh build/cloud-3.23.7-release/verify_fsi_element --metric-kernel-samples 50000
```

单条核命令只产生一次记录；完整协议需要同样运行保留基线、执行预热和五个交替顺序配对，并核对 JSON 中的 checksum、schema、样本数和哈希。原始 24 条命令均在 `simd-mpi/kernel-benchmark.json`。

组合装配对照：

```bash
bash build/locked.sh python scripts/benchmark_fsi_assembly.py \
  --baseline build/hpc-five-track/baseline/eonsim \
  --candidate build/cloud-3.23.7-release/eonsim \
  --baseline-commit 88e6c3359b742735877177eb4584b987caae1790 \
  --candidate-commit 27889707a3c650d532c2845b2f6da7fc5d2324d4 \
  --mpiexec .cloud/petsc-3.23.7/bin/mpiexec \
  --work build/reproduce-hpc/assembly-combined \
  --subdivisions 4 8 --ranks 1 2 --steps 5 --repeats 3 \
  --solver direct --baseline-assembly-report \
  --candidate-options='-fsi_overlap true -nonlinear_fused_reductions true'
```

同一二进制 MPI 对照将上述双方 executable 与 build commit 都设为候选，规模改为 `--subdivisions 8 --ranks 2`，并显式传入：

```text
--baseline-options='-fsi_overlap false -nonlinear_fused_reductions false'
--candidate-options='-fsi_overlap true -nonlinear_fused_reductions true'
```

并行输出合成测试及原活动的已执行命令：

```bash
bash build/locked.sh ctest --test-dir build/cloud-3.23.7-release \
  -R '^parallel_hdf5(_mpi)?$' --output-on-failure -V
python build/hpc-five-track/io/run_correctness.py
python build/hpc-five-track/io/run_benchmark.py \
  --build-source 27889707a3c650d532c2845b2f6da7fc5d2324d4
```

后两项为证据包内的活动脚本，并非所有 checkout 自带的安装命令。它们按脚本位置写入固定活动目录，不能直接在保留证据的位置重跑；复现时应先复制脚本及其读取依赖到独立活动目录，并核对根目录和输入路径。完整输入、命令、工具版本、文件哈希与原生读取 receipts 以相邻 JSON 为准。

### 7.3 审计文件

所有下列路径相对于仓库根目录，不是已公开网站资源：

| 证据目录 | 主要入口 | 用途 |
| --- | --- | --- |
| `build/hpc-five-track/simd-mpi/` | `README.md`、`ctest.log`、`kernel-benchmark.json`、`vectorization.json`、`independent-kernel-audit.json` | 七项测试、编译器报告、核计时与独立回放 |
| `build/hpc-five-track/assembly-combined/` | `results.json`、`candidate-build_receipt.json` | 旧/新二进制组合装配活动 |
| `build/hpc-five-track/mpi-ablation/` | `results.json`、双方 `*-build_receipt.json` | 同二进制通信开关活动 |
| `build/hpc-five-track/io/` | `environment.json`、`commands.json`、`manifest.json`、`data_comparison.json`、`paraview.json` | 输出正确性、实际 reader 和产物哈希 |
| `build/hpc-five-track/io/performance/` | `summary.json`、`samples.json`、`comparison.json`、`manifest.json` | 独立输出成本及数据对照 |

`simd-mpi/ctest-collided-other-job.log` 与 `ctest-collided-cost.txt` 来自共享 CTest 临时目录被另一个 HDF5 作业覆盖后的拷贝，**不属于七项 SIMD/MPI 测试的原始日志**，不计入本稿测试证据。七项通过状态保存在独立 `ctest.log`。原活动保留该碰撞说明，没有为覆盖它而重跑数值测试。

## 8. 结论与限制

完成的证据已经支持单元核成本下降、字段范数归约次数减少、同二进制 ghost 阶段计时改善以及可由真实 ParaView 读取的并行结果格式。组合装配时间改善，但整程序 wall 尚未稳定受益；HDF5 在当前单机场景显著优于 ASCII，同时明显慢于 binary VTU。

聚合辅助层级和有界自适应 PC 已在四档网格和完整动脉轨迹验证。实际更新削减、外迭代和耗时是不同指标：较少迭代不保证更快，较少刷新也不能保证强变化问题受益。最终交付以 PR #55 的受保护检查及合并记录为准；本草稿保持在 drafts，未部署或公开发表。

## 源码与一手资料

[S1]: https://github.com/saitoasukakawaii/EONSim-new/blob/27889707a3c650d532c2845b2f6da7fc5d2324d4/src/algebra/coupled_velocity_pc.cpp
[S2]: https://github.com/saitoasukakawaii/EONSim-new/blob/27889707a3c650d532c2845b2f6da7fc5d2324d4/src/algebra/nonlinear_system.cpp
[S3]: https://github.com/saitoasukakawaii/EONSim-new/blob/27889707a3c650d532c2845b2f6da7fc5d2324d4/include/eonsim/dual.hpp
[S4]: https://github.com/saitoasukakawaii/EONSim-new/blob/27889707a3c650d532c2845b2f6da7fc5d2324d4/src/io/parallel_hdf5.cpp
[S5]: https://github.com/saitoasukakawaii/EONSim-new/blob/27889707a3c650d532c2845b2f6da7fc5d2324d4/src/main.cpp
[R1]: https://petsc.org/release/manualpages/Vec/VecGhostUpdateBegin/
[R2]: https://www.openmp.org/spec-html/5.2/openmpse60.html
[R3]: https://web.cels.anl.gov/projects/petsc/vault/petsc-3.23/docs/manualpages/KSP/KSPSetReusePreconditioner.html
[R4]: https://support.hdfgroup.org/documentation/hdf5-docs/hdf5_topics/CollectiveCallsInParallel.html
[R5]: https://support.hdfgroup.org/documentation/hdf5/latest/group___d_x_p_l.html

- [联合速度与聚合实现][S1]；配套选项见同提交 `src/algebra/pc_plan.cpp`。
- [非线性通信、字段范数与自适应 PC][S2]；物理分阶段实现见同提交 `src/physics/fsi.cpp`。
- [AD 通道与标量操作][S3]；调用点见同提交 `include/eonsim/fluid_residual.hpp` 和 `src/physics/fsi_element.cpp`。
- [并行 HDF5 写入与发布][S4]；输出路由见同提交 `src/io/vtu.cpp` 和 [CLI][S5]。
- [PETSc ghost 更新 API][R1]、[PC 复用 API][R3]：用于解释接口语义；在线 release 手册可能对应更新版本，本文执行版本始终是 3.23.7。
- [OpenMP 5.2 SIMD construct][R2]：解释独立迭代通道与当前线程的向量执行。
- [HDF5 collective 调用要求][R4]、[数据传输属性与实际 I/O 模式][R5]：解释集体元数据顺序和实际传输模式诊断。

相关仓库草稿：[缩减 FSI 系统的旋转粗模态与联合速度 AMG](./fsi-reference-modes-and-gamg.md)。该稿对应上一轮实现，历史数字不能直接移作本轮证据。

[R6]: https://web.cels.anl.gov/projects/petsc/vault/petsc-3.23/docs/manualpages/KSP/KSPGetResidualNorm.html
[R7]: https://web.cels.anl.gov/projects/petsc/vault/petsc-3.23/docs/src/ksp/ksp/impls/gmres/fgmres/fgmres.c.html
