# SOLVER-03：Newton 变量与方程一致缩放审查

日期：2026-10-30（Asia/Shanghai）。审查基线：`717b25b5abb4d62e4c219c1b751fd0b9676d9352`。
状态：候选算法规格及独立代数验证，尚未接入 EONSim 求解器或 YAML。
本文件定义候选变换；现有接受规则仍以 [L2 离散契约](../architecture/L2_DISCRETIZATION_AND_OPERATORS.md) 为唯一依据。

## 1. 当前实现与缺口

| 源码位置 | 实际行为 | 对缩放的含义 |
|---|---|---|
| `include/eonsim/config.hpp` / `FieldTolerance` | residual_scale 与方程同单位，constraint_scale 与未知量同单位 | 没有独立的 Newton 未知量尺度配置 |
| `src/algebra/nonlinear_system.cpp` / `FieldAcceptance::measure` | 对物理行计算尺度归一后的 RMS，对约束行计算最大误差 | 属于验收，不改变 SNES 残量和 Jacobian |
| 同文件 / `Context::evaluate` | 物理态传给 assemble；约束行写 x-g；MatZeroRows 对角为 1 | 当前组装的是物理坐标方程 |
| 同文件 / `convergence`、`NonlinearSystem::solve` | 默认 SNES 停止条件之后再检查字段；最终重新装配验收 | 不能由验收尺度推断线搜索或 Krylov 已无量纲化 |
| `src/algebra/schur_solver.cpp` | 从实际矩阵构造 field-split、SELFP、GAMG | 以后必须消费变换后的矩阵及一致的子块 |
| `tests/verify_nonlinear_acceptance.cpp` | 极端方程尺度、提前停止、约束、反力验收测试 | 不是完整 Newton 坐标缩放实现的证据 |

本轮继续研发先完成原队列要求的规格。不存在本轮实测证明的缩放性能瓶颈，因此不直接更改物理求解路径，也不宣称缩放改善条件数或收敛速度。

## 2. 候选数学变换

考虑已经完成接口消元、并替换 Dirichlet 行后的方程 `F(x)=0`，Jacobian 为 `J=dF/dx`。
令正有限对角矩阵 `Sx=diag(s_i)` 表示未知量特征尺度，`Sr=diag(r_i)` 表示方程特征尺度。
物理行的 r_i 与装配残量同单位，约束行 F_i=x_i-g_i 的 r_i 与该未知量同单位。
每次 solve 内固定尺度，包括所有线搜索评价；下一时间步或重试可以重新建立尺度。

```text
y = Sx^-1 x
Fhat(y) = Sr^-1 F(Sx y)
Jhat(y) = Sr^-1 J(Sx y) Sx
Jhat Δy = -Fhat
Δx = Sx Δy
```

在精确线性求解下，左右乘恢复 `J Δx=-F`。有限精度、迭代线性容差和线搜索可能改变实际轨迹。
若尺度依赖当前 trial，链式法则会增加导数项；首版候选禁止这种变化，不把自动逐迭代平衡混入固定尺度方案。

未知量尺度与约束验收尺度不能自动视为同一配置。现有 constraint_scale 表示验收归一化，不能悄然重解释为 s_i。候选实现应有独立、默认关闭的开关及显式未知量尺度；具体配置键尚未确定。

## 3. 约束与状态恢复

先在物理坐标形成约束替换行，再应用左右缩放：

```text
Fhat_i = (s_i y_i - g_i)/r_i
Jhat_ii = s_i/r_i
Jhat_ij = 0  (j != i)
y_i(initial) = g_i/s_i
```

只在 s_i=r_i 时对角恰为 1。缩放后再次调用对角为 1 的 MatZeroRows 会破坏导数一致性。
物理 Dirichlet 初态满足约束时，精确 Newton 步保持约束；测试仍应从违约状态验证该公式，避免零约束增量掩盖错误。
接口 reduced layout 的消元先完成，再缩放有效未知量。不能对含速度、位移和 BE 时间因子的接口映射直接套用同一数值尺度。
所有 kernel、材料定义域判断、输出、checkpoint、accepted 状态和原始反力都保持物理坐标；只有成功的最终物理验收后才能提交状态。

## 4. 线搜索、停止准则与诊断

候选默认只支持明确审查过的 Newton 线搜索路径。试探点为 `y_trial=y+αΔy`，映射后等于 `x+αΔx`。
采用残量二范数 merit 时，新的目标是 `φ(y)=0.5 ||Sr^-1 F(Sx y)||²`。它等于物理坐标的加权 merit，通常不等于当前未加权 merit，因此不能保证原线搜索接受相同 α。

全局二范数不等于逐字段 RMS 与约束最大值的合取。候选接线要求：

1. 初始状态施加 prescribed 后，在物理坐标冻结现有字段阈值。
2. SNES 看到缩放残量；检查字段时使用独立的物理残量，避免对 Fhat 再除一次 residual_scale。
3. 默认 SNES 容差现在作用于缩放坐标，需显式记录其语义；字段物理验收继续作为成功的必要条件。
4. 最终重新装配物理残量，不允许 options 的正 reason 绕过验收。定义域错误仍按现有共同错误传播规则处理。
5. 不支持的 SNES 类型或叠加对角缩放选项应明确拒绝，直到对应坐标路径被验证。

线性诊断分别命名缩放空间缺陷 `Jhat Δy+Fhat` 与物理缺陷 `J Δx+F`，两者满足前者为后者乘 Sr^-1。不得沿用旧标签却报告新单位。
原始约束反力来自未替换行的物理残量，不能由约束误差或缩放后行恢复。

## 5. 预条件器与 Schur

如果物理预条件矩阵为 P，则一致变换为 `Phat=Sr^-1 P Sx`。
如果现有的是近似逆作用 B（近似 P^-1），对应作用为 `Bhat(q)=Sx^-1 B(Sr q)`；不要混淆矩阵与逆作用的缩放方向。

对 `J=[[A,B],[C,D]]`，设每块有相应的行尺度 R1/R2 与列尺度 X1/X2：

```text
Ahat=R1^-1 A X1   Bhat=R1^-1 B X2
Chat=R2^-1 C X1   Dhat=R2^-1 D X2
Shat=Dhat-Chat Ahat^-1 Bhat = R2^-1 (D-C A^-1 B) X2
```

正对角尺度下，若 A 对角非零，SELFP 的 `diag(A)^-1` 近似同样有该代数变换形式；这不保证 GAMG 重新构造的近似逆与原层级严格等价。
field IS 与 owner 编号不变。右零空间向量应变换为 Sx^-1 n，左零空间向量为 Sr m；近零空间也需按未知量坐标变换并重新正交化。
一般左右尺度不保持对称性，不得因此自动选 CG。当前 FGMRES 路径仍需用实际算子和容差验证。

## 6. 实现边界与并行接线建议（未实现）

- 在 NonlinearSystem 适配层维护 y、物理 trial scratch、owned 行尺度和 ghost 未知量尺度；不用全局 gather。
- 装配回调始终接收物理 x；约束替换之后对 residual 做点乘、对 Mat 做左右对角缩放。重装配前按现有路径清零，禁止重复累乘尺度。
- Jacobian、显式 Schur 初次 setup 和后续 PC 更新必须在同一坐标系；物理验收与反力使用独立缓冲区。
- 空本地字段参与必要规约。尺度检查应覆盖正值、有限值、字段覆盖、owned/ghost 一致性；无效配置是输入错误，不能通过缩步掩盖。
- 额外向量存储为 O(本地 owned+ghost)，显式矩阵缩放工作为 O(本地非零元)。通信量及实际开销未测量。

## 7. 已执行证据

执行 `python3 scripts/verify_newton_scaling.py`：两组尺度（单位、非均匀）全部通过。
脚本使用 Python 标准库 Fraction 精确算术，检查 Newton 增量、二次残量的中心差分 Jv、非零 Dirichlet、三种步长的物理试探点和加权 merit、预条件逆作用、两块 Schur 恒等式。
负对照确认“只缩放残量”和“强制单位约束对角”不满足要求。脚本自身的 check 在 Python 优化模式下仍有效。

这只是小型代数模型的公式验证，不执行 EONSim/PETSc，也不验证浮点鲁棒性、MPI、非线性收敛或性能。C++ 数值测试本轮未运行。

## 8. 后续实现验收条件（未执行）

1. 默认关闭时既有算例结果保持；单位尺度模式与默认模式对照。
2. 非均匀尺度下 Jv、非零约束、物理解、原始反力符合独立参考。
3. 直接解与 field-split/Schur 解对照；物理验收和缩放诊断分别检查。
4. 1/2 rank 包含空本地字段和 ghost，检查解、字段阈值及失败分类。
5. 线搜索定义域拒绝、零迭代提前停止、失败后重试与 checkpoint 恢复不污染接受状态。
6. 非正/非有限尺度和不支持的 PETSc 组合明确报错。

实现任务保持 deferred，触发条件是明确的算例尺度需求及本规格评审意见。不能将本轮规格标为求解器缩放已交付。

## 参考资料

- [PETSc SNES manual](https://petsc.org/release/manual/snes/)：Newton、线搜索及收敛接口。
- [MatDiagonalScale](https://petsc.org/release/manualpages/Mat/MatDiagonalScale/)：左右对角矩阵缩放。
- [PCFIELDSPLIT](https://petsc.org/release/manualpages/PC/PCFIELDSPLIT/)：块分裂和 Schur。
- [SNESSetConvergenceTest](https://petsc.org/release/manualpages/SNES/SNESSetConvergenceTest/)：自定义停止条件。
