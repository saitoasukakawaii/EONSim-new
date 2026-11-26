# RCR 端口 Schur 与低秩预条件器

状态：2026-11-26 已合入 main；`codex/rcr-port-schur` 实现完成，本地代数与真实 FSI 验收已通过；交付
[PR #58](https://github.com/saitoasukakawaii/EONSim-new/pull/58)。基线为已合并 #57 的
`main@b731d4713ab8428e02fb52af6547e1aa3097eca0`，当前生产源码为
`28e6d54701abced040752aff70b69d29b35f1d01`，最终物理验证驱动为
`ad08887f8b357ef16e6a6b49b89d968f531f8053`。源码先同步远程，再构建/执行。
此处记录固定源码证据；#58 已合并，源码 CI 65/65 Release、54/54 Python。后续 #59 增加 RCR bulk 中的高级压力辅助传播与界面校正；见 [高级 PC](FSI_ADVANCED_PRECONDITIONERS.md) 和 [当前能力矩阵](CURRENT_STATUS.md)。

## 1. 入口与适用范围

显式启用：

```text
-pc_recipe hybrid -pc_plan_rcr_ports true
-pc_plan_velocity_solver gamg
-pc_plan_schur_approx nodal
-ksp_type fgmres
```

`-pc_plan_rcr_ports` 包裹现有语义 PC recipe，将 `fluid/pressure/boundary` 自由度
识别为 RCR 端口，将其他自由度放入 bulk 块。bulk 含内部流体速度、流体压力、固体
速度和 ALE 位移；它不是只有速度的矩阵。原 root Jacobian、残量、物理验收字段和
编号保持不变，仅预条件器使用子矩阵编号。

bulk 继续使用所选 recipe，在根 KSP 原前缀后追加 `rcr_bulk_`，再接原子树前缀。
根前缀为空时，例如 hybrid 联合速度块的主前缀为 `rcr_bulk_fieldsplit_dynamics_fieldsplit_velocity_`；压力
内解和 upper 解仍遵守原 recipe 的前缀规则。`-pc_plan_report` 用于检查实际树。
启用选项需要至少一个端口；无端口问题应沿用原 recipe。

| 组合 | 用途与边界 |
| --- | --- |
| `-pc_plan_velocity_solver split` | bulk 保留原分离速度子块；端口修正在外层统一处理 |
| `-pc_plan_velocity_solver coupled` | bulk 的联合流固速度块使用现有 ASM/ILU 路径 |
| `-pc_plan_velocity_solver gamg` | bulk 的联合流固速度块使用 PETSc scalar GAMG |
| `-pc_plan_velocity_solver boomeramg` | bulk 的联合流固速度块使用 PETSc 的 hypre BoomerAMG 接口 |
| `-pc_plan_velocity_solver twolevel` 或 `aggregate` | bulk 保留已有两层/聚合速度响应，端口修正不替换其近似 |
| `-nonlinear_adaptive_pc true` | 端口数值缓存随已有自适应 PC 更新决定一同保留或刷新 |

联合速度选项继续服从完整 FSI 的 hybrid/quantity 适用条件；不能通过启用端口包装
绕过 recipe、实体类型、粗空间和参考几何的既有检查。GAMG/BoomerAMG 不自动表示
已建立任意网格独立收敛性。BoomerAMG 需要 PETSc 实际具有 hypre 支持。

## 2. 从实际 Jacobian 提取符号

将已约束的完整 Jacobian 按 bulk 与端口压力重新分块：

\[
J=\begin{bmatrix}A&U\\V&D\end{bmatrix},\qquad
r=\begin{bmatrix}r_b\\r_p\end{bmatrix}.
\]

矩阵块直接来自当前已约束 Jacobian，不从配置中的电阻、电容重新构造。
因此 BE/BDF2/generalized-alpha 进入有效阻抗的时间权重、约束投影、接口 alias 和
移动出口几何导数都由现有装配定义。

固定出口、保留对偶关系的活动速度/端口子块具有 `J_uq=+B`、`J_qu=-Bᵀ`、
`J_qq=diag(1/Z)`，其中每列 `B` 是带方向的离散通量/压力牵引权重，`Z` 是时间
离散后的总阻抗。消元端口压力后速度算子为 `A+B Z Bᵀ`。

仅替换 Dirichlet 行、保留原矩阵列的约束处理也可能破坏完整 `U/V` 的转置关系。
移动出口的端口行还有 ALE/界面几何导数。特别是 `outlet_jacobian_entries` 中
`-velocity_sum*slope` 进入端口对网格/约束映射列的导数。故一般的完整 bulk 分块
不能假定 `V=-Uᵀ`；实现必须分别提取 `U` 与 `V`。这里 `q` 表示端口压力修正，
不是体积流量。

## 3. 端口 Schur 和低秩作用

令 `H` 为一次 bulk 预条件器作用，首先建立

\[
Y=HU,\qquad \widehat S_p=D-VY.
\]

对每个待预条件的残量，依次执行

\[
z=Hr_b,\qquad
q=\widehat S_p^{-1}(r_p-Vz),\qquad
x_b=z-Yq.
\]

最后按原 owned 编号写回 `(x_b,q)`。这是一层端口 Schur 消元；bulk 内部现有的
速度/压力、流体/结构 Schur 与之是不同层次。

若 `H=A⁻¹`，且相应 Schur 块可逆，上式就是原增广系统的精确块逆。
若 `H` 是固定可逆线性近似，则它是将 `A` 替换为 `H⁻¹` 后的精确块逆。
若 bulk 含依赖残量的内层 Krylov/粗层求解，`H` 一般不满足线性叠加；此时缓存列
`H U_j` 构成近似响应预条件器，不能称为原矩阵的精确 Woodbury 逆。外层固定使用
FGMRES，并继续以原完整 Jacobian 检查真实残量。

当端口 RHS 为零，bulk 上的作用是

\[
H+HU(D-VHU)^{-1}VH.
\]

固定出口且耦合满足 `U=B`、`V=-Bᵀ` 时，化为

\[
H-HB(Z^{-1}+B^THB)^{-1}B^TH.
\]

单出口只需解一个标量 Schur，即 Sherman–Morrison 修正；多出口需解保留所有
交叉项的小型稠密系统，即 Woodbury 修正。不能逐出口分别执行秩一修正并丢弃
`B_iᵀ H B_j`，因为 bulk 响应通常会耦合不同出口。

## 4. MPI 和缓存

全局端口次序由 owned 原矩阵行的稳定顺序确定。每个端口压力只有一个 owner；
bulk 的内积只累计 owned 数据，ghost 不重复贡献。端口个数为 `k` 时：

1. setup 对全部 `D−VY` 的 `k²` 个条目批量规约；小系统在所有 rank 上得到相同值。
2. apply 将端口 owner 的 `r_p` 与全部 `−Vz` 本地贡献合并为一次 `k` 标量规约。
3. 每个 rank 解相同的小系统，然后仅写回自身 owned bulk/port 条目。

失败标记可与这些数值缓冲一起规约，使空 bulk rank 和无端口 owner rank 走相同
集体顺序。这些计数只描述端口修正本身，不包含 bulk KSP、AMG、子矩阵提取或
PETSc 内部通信，不能把“一次端口规约”写成整个 PC 只有一次 MPI 通信。

固定子矩阵索引、owned 映射、工作向量、端口列和小系统缓冲跨 PC apply 复用。
`PcSchurUpdates` 控制数值更新：刷新 bulk `A`，刷新其 USER Schur/基础 PC，随后
计算新的 `Y` 和端口 Schur。数值 generation 必须作为整体发布；中途失败使缓存
不可用，不能保留一半新列与一半旧因子。

默认每次应更新的 Jacobian 对应一次 PC 数值更新；自适应 PC 可以暂时保留整套
旧近似，同时完整 Jacobian 仍逐 Newton 修正更新。时间系数、配置、约束集合、
矩阵漂移、使用年龄、迭代增长和失败恢复遵守既有求解器会话策略。
现有漂移量基于对角和绝对行和，是有界启发式；保持这些量不变的耦合方向变化
可能不会立即触发漂移更新，因此不能把监测器描述成所有矩阵变化的精确检测器。

成本上，一次数值更新增加 `k` 次 bulk 响应、`O(n_local k²)` 本地积及
`O(k³)` 小系统分解；每次 apply 增加 `O(n_local k+k²)` 工作。响应列存储为
`O(n_local k)`，不收集完整全局场或全局 bulk 矩阵。出口很多时，setup 与列存储
成本会增长；是否获益需要比较相同物理门槛下的 setup、外迭代和总耗时。

## 5. 数值安全和诊断

小 Schur 使用带主元的稠密分解及数值尺度检查；奇异、非有限或失败的 bulk 响应
必须明确失败。不能通过向 `D` 加任意正数、减小实际阻抗、放宽 KSP/物理门槛等
方式把失败改成通过。异常不得穿过 PETSc C 回调，MPI rank 也不得单独提前退出。

只读统计用于区分初始化/数值重建、列响应次数、apply 次数，以及端口 setup/apply
批量归约次数。统计属于同一 shell 生命周期；重建求解器会话后重新计数。
solver tree 应包含 shell 内的 bulk KSP，实际 GAMG/hypre 选择以树和日志为证。

## 6. 验证结果与入口

完整原件、失败尝试、机器环境与独立审计归档在
[`docs/research/data/rcr-port-2026-11-26`](../research/data/rcr-port-2026-11-26/)。
`evidence.tar.xz` 保留 683 个原始文件，`archive-manifest.json` 列出每个文件的
源路径、归档路径、长度与 SHA256；独立审计 JSON 与只读脚本在同目录。

### 6.1 代数与故障恢复

生产修复 `28e6d54` 的以下 Release 代数命令已实际执行，**3/3 通过、0 跳过**：

```sh
ctest --test-dir build/cloud-3.23.7-release \
  -R '^pc_rcr_port_mpi(1|2|4)$' --output-on-failure
```

每个 rank 配置均通过完整增广矩阵的独立 long-double 消元对照，覆盖单/双/三出口、
非对称 `U/V`、非零端口 RHS、第二步主元交换、跨 20 个数量级的端口表尺度、
端口 owner、空 bulk/全空 rank、非零→零→恢复数值更新、奇异 Schur 拒绝及恢复。
统计断言确认 `response_solves=k*rebuilds`，apply 不重算响应列，端口 apply 归约数
等于应用数。非有限端口 RHS 检查了真实 PC 失败状态及随后刷新恢复。

合成非线性场景直接记录同一会话 `generation=1` 中两次新 Jacobian、零 USER
更新，以及拒绝后的 `generation=2`；使用年龄、时间系数和大漂移触发更新均通过。
原始记录为 `build/rcr-port/algebra-28e6d54.log/.xml` 与相邻 `-LastTest.log`。

首轮源码 `94046b1` 的 7 项选测中，原有 `pc_plan_mpi1/2/4` 和
`adaptive_pc_mpi2` 共 **4 项通过**；新 RCR 的 **3 项失败**。原因是失效缓存的
shell apply 返回 API 错误，PETSc `PCApply` 提前返回而未清除输入向量读锁，
随后的恢复用例因此失败。`28e6d54` 改用 `PC_SUBPC_ERROR`、`PETSC_INFINITY` 哨兵输出和正常返回，
让 PETSc 完成锁清理后再报告数值失败。测试与容差未改；仅复跑受影响的新 3 项，
旧 4 项复用本轮首轮通过证据，不记为再次执行。另 32 项选测/证据 Python 检查
在 `94046b1` 通过，原件为 `build/rcr-port/python-94046b1.log`。

### 6.2 真实移动出口 FSI

以下算例入口在驱动 `ad08887` 上实际执行，**1/1 通过、0 跳过**，CTest 用时
21.5413 秒；生产代码及二进制沿用已构建的 `28e6d54`：

```sh
ctest --test-dir build/cloud-3.23.7-release \
  -R '^rcr_port_fsi$' --output-on-failure
```

首轮 FSI 驱动在 checkpoint 恢复后的步数断言失败，原件保留在
`build/rcr-port/fsi-28e6d54-first`。变步序列总长 `.056` 小于 `steps*dt=.06`，
应用正确追加一个 `.004` 步到终止时间，故恢复段有 3 步而不是驱动假定的 2 步。
驱动修复将 nominal `dt*steps` 与指定步长总和对齐，并明确检查终止时间及历史
时间戳；未改生产方程、容差或残差门槛。修复先推送，再运行完整验收，首次失败
不改记为通过。

最终包含 **13 次独立求解、43 个接受时间步**：单出口 8 次求解、28 步；双出口
5 次求解、15 步。单出口使用 `generalized_alpha`、步长 `.015/.015/.013/.013`，
终止 `.056`；双出口使用 `.016/.014/.017`，终止 `.047`。两组都包含直接解、
同一 GAMG 基础 PC 的无端口包装基线、split、GAMG 和 BoomerAMG 包装路径；
单出口另含自适应缓存，以及 GAMG checkpoint → BoomerAMG restart。
两个出口具有相反外法向和不同阻抗；由原始网格与输出场独立重积的面积变化为
单出口 `−5.19735e−4`，双出口 `+1.35499e−4/+7.10693e−5`，确实覆盖移动出口。

验证对照采用相同物理配置；基线与包装路径的外层容差均为 `rtol=1e−11`、
`atol=1e−13`、`max_it=1500`，FGMRES 右预条件、非预条件残差范数。
完整点场比较包括两域坐标、速度/位移、流体压力、网格速度及全部输出的算法
加速度，不比较分区 owner 和局部代数编号。独立审计重新读取 VTU、CSV 和原始
日志，不导入原验证器辅助函数，也不再启动物理求解。

| 独立核验量 | 实测最大值 | 验收门槛 |
| --- | ---: | ---: |
| 最终完整点场与直接解的绝对差 | `7.57780e−11` | `<2e−8` |
| 全接受步的端口/电容历史绝对差 | `2.15827e−12` | `<2e−9` |
| 电路关系、面流量/压力与压力功缺陷 | `1.69548e−13` | `<2e−10` |
| 真实线性残差 / $\max(10^{-12},10^{-9}\lVert b\rVert)$ | `0.0997252` | `≤1` |
| MSH+VTU 重积面积与面历史之差 | `5.55112e−17` | `<2e−12` |
| MSH+VTU 重积有向通量与端口历史之差 | `1.08420e−19` | `<2e−12` |
| TET4 重积终点体积与历史之差 | `2.22045e−16` | `<2e−12` |

11 个开启诊断的求解共记录 **96 个真实线性残差样本**，全部通过严格门槛；
798 条实际 solver node 记录均为正 KSP reason、零 PC failure reason。
全部 43 步共有 114 次 Newton 迭代，其中两个直接解参考的 18 次没有开启
`linear_report/solver_report`，故其线性残差和 reason 不纳入上述 96/798 条观测。
所有原始场与历史有限，最小已记录流体/固体阶段或终点 Jacobian 为 `0.996154`。
跨基础 PC 重启的最终场与不间断 BoomerAMG 解相差 `5.77105e−11`。

日志证实速度叶实际为 `preonly/gamg` 或 `preonly/hypre`，BoomerAMG 配置报告
存在，未把选项字符串当作实际 PC 的证据。所有端口统计满足
`responses=k*rebuilds`、`setup_reductions=rebuilds`、
`apply_reductions=applications`，同一求解的各 rank 最终统计相同。
自适应单出口同一 `generation=1` 中有 **12 次完整 Jacobian 装配、8 次 PC
刷新、4 次复用**，最终 shell 计数为 8 次响应重建和 144 次应用；完整 Jacobian
未因缓存复用而停止更新。

### 6.3 性能观测与未验证边界

相同两 rank、相同 GAMG 基础速度 PC 下，当前小算例的观测如下。时间为各步
`solver_report` 同名计时字段之和，单位秒；`schur_setup_seconds` 是该字段的
统计口径，不能解释为包含所有迭代内更新的完整 PC 成本。

| 算例与全局 DoF | 外迭代，基线→包装 | `linear_seconds` | `schur_setup_seconds` | `solve_seconds` |
| --- | ---: | ---: | ---: | ---: |
| 单出口，350 | `145→144` | `0.034643→0.017749` | `0.011083→0.015333` | `0.081757→0.076040` |
| 双出口，1020 | `53→53` | `0.024721→0.012196` | `0.016434→0.017932` | `0.072828→0.068904` |

这两组仅是共享单机的一次样本，外迭代几乎未减少且初始 Schur setup 字段增加。
阶段计时的下降不足以建立稳定加速结论；没有重复基准、置信区间、跨网格或
跨节点扩展数据。当前证据支持实现正确、组合实际生效、合并归约和缓存按预期
执行，不支持任意阻抗、出口数量或大规模问题的通用性能承诺。

实现入口：`include/eonsim/rcr_port_pc.hpp`、`src/algebra/rcr_port_pc.cpp`；
语义路由：`src/algebra/pc_plan.cpp`；会话与更新：
`src/algebra/nonlinear_system.cpp`；物理符号来源：`src/physics/fsi.cpp`。
本轮本地环境为 PETSc 3.23.7 Release、hypre 2.32、共享单机；本地未执行 Debug、
旧 PETSc 或全量验证。本节证据不等于大规模性能、任意网格独立收敛或多节点验证；
远程 CI 的补充结果另随 PR 的最终 head 记录。

## 7. 依据

- 本仓库基线 `b731d471` 的 `src/physics/fsi.cpp::outlet_jacobian_entries`：
  RCR 耦合符号、总阻抗倒数与移动出口导数。
- [PETSc PCSHELL](https://petsc.org/release/manualpages/PC/PCSHELL/)：用户 PC 的
  context、apply、setup 和 destroy 接口。
- [PETSc KSPFGMRES](https://petsc.org/release/manualpages/KSP/KSPFGMRES/)：可变或
  非线性内层预条件作用与右预条件 FGMRES。
- [PETSc PCGAMG](https://petsc.org/release/manualpages/PC/PCGAMG/)：AMG 和插值复用。
- [PETSc PCHYPRE](https://petsc.org/release/manualpages/PC/PCHYPRE/)：BoomerAMG
  每次应用的 cycle/tolerance 语义；这些参数与外层 Krylov 上限不同。

在线手册随 PETSc release 变化；本次实际运行依赖仍锁定为 PETSc 3.23.7。
