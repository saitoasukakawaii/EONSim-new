# RCR 端口 Schur 与低秩预条件器

状态：`codex/rcr-port-schur` 实现和验证过程中。基线为已合并 #57 的
`main@b731d4713ab8428e02fb52af6547e1aa3097eca0`；本文件中的运行命令目前是验收入口，
尚未执行，不代表通过。源码先同步远程，再构建/执行；最终证据由本次验收记录补齐。

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

bulk 继续使用所选 recipe，其 PETSc 前缀比原树增加 `rcr_bulk_`。例如 hybrid
联合速度块的主前缀为 `rcr_bulk_fieldsplit_dynamics_fieldsplit_velocity_`；压力
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

固定出口的速度/端口子块具有 `J_uq=+B`、`J_qu=-Bᵀ`、
`J_qq=diag(1/Z)`，其中每列 `B` 是带方向的离散通量/压力牵引权重，`Z` 是时间
离散后的总阻抗。消元端口压力后速度算子为 `A+B Z Bᵀ`。

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

固定出口 `U=B`、`V=-Bᵀ` 时，化为

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

## 6. 验证状态与入口

本节目前为待执行验收入口，不能引用为已通过证据：

```sh
ctest --test-dir build/cloud-3.23.7-release \
  -R '^pc_rcr_port_mpi(1|2|4)$' --output-on-failure
ctest --test-dir build/cloud-3.23.7-release \
  -R '^rcr_port_fsi$' --output-on-failure
```

代数验证应独立比较完整增广矩阵逆，覆盖单出口、多出口、非对称耦合、端口
ownership、空 bulk rank、缓存更新、非有限/奇异失败及恢复。真实算例应比较
直接解与新 PC 的同分区场/历史，覆盖移动平面、多个出口、GAMG/BoomerAMG、
时间步变化和 checkpoint 重启，并检查独立真实线性残量。

实现入口：`include/eonsim/rcr_port_pc.hpp`、`src/algebra/rcr_port_pc.cpp`；
语义路由：`src/algebra/pc_plan.cpp`；会话与更新：
`src/algebra/nonlinear_system.cpp`；物理符号来源：`src/physics/fsi.cpp`。
所有测试/性能结论在实际执行后注明源码提交、配置、命令和原始输出。

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
