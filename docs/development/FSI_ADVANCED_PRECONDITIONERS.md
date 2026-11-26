# FSI 专用多层预条件器、压力 Schur 与混合精度界面校正

交付状态：PR [#59](https://github.com/saitoasukakawaii/EONSim-new/pull/59) 已于 2026-11-26 合入 `main@3472a18`；该 PR 的既有源码 CI 为 85/85 Release 与 54/54 Python，后续证据提交复用相容结果。[当前能力矩阵](CURRENT_STATUS.md) 汇总其他已合并实现及未达目标。

本文是 [FSI_BLOCK_PRECONDITIONER.md](FSI_BLOCK_PRECONDITIONER.md) 的增量说明，覆盖本轮五项功能的数学定义、实际开关、并行约束和已执行验证。当前生产实现固定于已同步的 `19cd26f2af9b02859fac28ca8f662c29c20d47f1`，包含 PCD 辅助边界尺度修正。此前代数验证固定于 `e565c9872551dad9dc7a01d4d7b613e8a96d3545`，首轮功能与物理验收固定于 `c5af27de8fdc7a42df855543ad6366ce7db70571`；这些测试均先同步源码、再构建和验证。测试驱动提交 `9dfd8ac` 未改变生产算法。**19cd26f 的 38 次 PCD 受影响物理求解已由原驱动验收通过，独立原件审计及最终归档均已完成，见第 8.4 节；旧收据与新边界收据分开保留。**

**当前交付是可组合、显式选择的求解能力。默认配置不变。** 新增 `field_amg`、`lsc/bfbt/pcd`、界面 `vanka/patch` 以及局部 FP32 因子。实现和小规模验证不等于已经证明物理问题的网格无关收敛、普遍运行时间收益或全局内存减半。本文将理论推导、代码实现、数值验证和性能证据分别说明。

## 1. 问题定义

对象是现有共形、约束消元后的单体 FSI Newton 系统。流体速度、独立结构速度、压力及 ALE 网格增量仍共同属于原始 Jacobian；选项只改变其预条件作用。压力稳定化、物理边界条件、时间离散、非线性接受门槛和历史提交规则由原模型决定。

| 开发目标 | 本轮实现 | 实现边界 |
|---|---|---|
| P0：FSI 专用 Block AMG | 语义 `hybrid` 树内的联合流固速度 `field_amg`，与压力 Schur、ALE 块组合 | 速度多层法与块分解共同构成 FSI 预条件器；完整混合 Jacobian 没有被改成单个标量 AMG |
| P0：PCD / LSC / BFBt Schur | 完整保留压力块的稳定化交换子变体，以及物理装配 PCD | 三者是可选近似，不承诺均优于既有 `nodal` |
| P1：流固界面 Vanka / Patch | 在整棵块预条件树之后，按真实界面顶点做混合未知量的重叠加权校正 | 当前是根部或 RCR bulk 上的后校正，尚未成为每个 AMG 层的界面 smoother |
| P1：Field-aware AMG 粗空间 | 13 个物理候选槽位、aggregate 局部秩筛选、逐层候选传播及完整 Galerkin 投影 | 适用于 P1 顶点速度与标量刚体速度；没有一般高阶/非共形接口扩展 |
| P1：混合精度预条件器 | 界面局部稠密 LU 可用 FP32；FP64 残量检查、迭代改进和显式 FP64 回退 | 全局矩阵、场向量、AMG、压力及 bulk 求解仍是 FP64 |

`field_amg` 要求完整 FSI 的 `hybrid` 或 `quantity` 语义布局。完整 FSI 的 `quantity` 使用原始压力块，没有压力 Schur，因此不能与 `lsc/bfbt/pcd` 组合；要同时使用本轮能力，应选择 `hybrid`。`physics`、`added_mass` 的内部压力 Schur 也可选择新压力近似，但其速度分组不同，不接受联合速度 `field_amg`。

## 2. 数学定义

### 2.1 保留完整稳定化的 LSC / BFBt 变体

在当前速度/压力语义子树上，记

\[
J_{vp}=\begin{bmatrix}A&B\\C&D\end{bmatrix},\qquad S=D-CA^{-1}B.
\]

在 `hybrid` 中，速度块同时含流体和结构速度。所有块从施加约束后的实际 Jacobian 提取；`B` 与 `C` 分别保留，不假定 \(C=\pm B^T\)。\(D\) 是完整压力块，包括非对角稳定化。

本轮 `lsc` 和 `bfbt` 分别采用

\[
W_{\rm lsc}=I,\qquad W_{\rm bfbt}=\operatorname{diag}(|A_{ii}|)^{-1},
\qquad s=\|WA\|_\infty,
\]

\[
L=-CWB+sD,\qquad H=-CWAWB+s^2D,\qquad
\mathcal B_p r\approx L^{-1}HL^{-1}r.
\]

\(s\) 是按全局最大绝对行和得到的正尺度，其量纲补偿两个稳定化项；它不是特征值估计。BFBt 拒绝零、非有限或倒数不可表示的动量对角。`lsc` 不装配有限元速度质量矩阵，`bfbt` 的权重就是这里定义的对角权重。

该实现是**保留完整 \(D\) 的 scaled stabilized commutator 变体**。稳定化 LSC 的文献依据见 Elman 等第 4 节、式 (4.13)，但本文的 \(sD,s^2D\) 不是该文逐单元构造的 \(C_1,C_2\)，也不是其式 (4.14)–(4.15) 的完整算法。[参考文献 1] PETSc `PCLSC` 文档明确说明其公式忽略 \(A_{11}\)；因此直接选择原生 `-pc_type lsc` 不能替代这里的稳定化处理。[参考文献 2]

公式中的逆定义目标作用。运行时两次 \(L^{-1}\) 都由辅助 KSP 的有限工作量响应近似，默认各应用一次 GAMG；不把这一响应称作精确逆。

### 2.2 物理 PCD 与辅助边界

物理层在每次成功的 Jacobian 装配后，提供压力空间上的正对角集中质量 \(M_p\)、Laplace 矩阵和压力输运矩阵。先记未处理辅助边界的算子为 \(K^0,F^0\)。对当前 ALE 四面体 \(K\)，使用当前坐标 \(x=X+d_m\)：

\[
(M_p^K)_{aa}=|K|/4,\qquad
(K^{0,K})_{ab}=|K|\nabla N_a\cdot\nabla N_b,
\]

\[
(F^{0,K})_{ab}=
\frac{\rho}{\Delta t_{\rm eff}}\frac{|K|}{20}(1+\delta_{ab})
+\mu(K^{0,K})_{ab}
+\rho\int_K N_a(u-w)\cdot\nabla N_b\,dx,
\quad w=\frac{d_m-d_m^{\rm previous}}{\Delta t_m}.
\]

\(N_a\) 为 P1 形函数，\(\rho\) 为流体密度，\(\mu\) 为黏度；时间系数直接取本次物理装配的有效阶段数据。输运项在 `fluid.convection=false` 时省略；否则采用四点四面体积分，对仿射 P1 单元上的该二次被积式精确。\(M_p\) 本身不包含密度，\(F^0\) 包含密度及当前相对网格速度。

辅助边界取现有 `pressure_tags` 对应的压力牵引边界。令 \(Q\) 为非辅助 Dirichlet 行的对角投影，\(E=I-Q\)，\(N=F^0-\mu K^0\) 为瞬态/对流项。本轮边界修正保留 \(M_p\) 的全部物理集中质量，构造

\[
K_p=QK^0+E,\qquad F_p=QF^0+\mu E=\mu K_p+QN.
\]

代码只用 `MatZeroRows` 替换 \(K^0,F^0\) 的边界行，分别置对角 1、\(\mu\)，不清除边界列。此表达要求所有流体单元、所有 MPI rank 的正黏度 \(\mu\) 相同；空流体 owner 仍参加校验。非均匀黏度会明确拒绝。其余边界使用自然 Neumann 条件。

边界行由 owned 节点的完整边界标签识别，包括 owner 没有本地牵引面的情况。没有任何此类全局边界行时明确拒绝；没有随意增加压力 pin。原始物理压力未知量和 Jacobian 不因辅助边界而改变。辅助边界只限制 Laplace 校正，不应把整个黏性质量逆项也清掉。FENaPack 的 BRM2 作用与数学说明提供了这一分项处理的概念参考；本轮没有实现其全部入口 Robin 项或基于离散速度质量的 PCDR 增强。[参考文献 7]

PCD 采用作用顺序 \(K_p^{-1}F_pM_p^{-1}\) 的变体，并以

\[
S_0=M_pF_p^{-1}K_p,\qquad
\widetilde S=D+S_0,\qquad
T=K_p+F_pM_p^{-1}D,
\]

\[
\mathcal B_{p,\rm PCD}r\approx T^{-1}F_pM_p^{-1}r
\]

纳入完整稳定化块。辅助 KSP 求解的是 \(T\)，不是单独 \(K_p\)。这里的 \(K_p,F_p\) 来自物理单元装配，不是由 \(B,C\) 合成的代数代理。PCD 的这种乘法顺序可参照 Firedrake `PCDPC.apply`；本实现的瞬态/ALE 系数、稳定化组合和边界选择由 EONSim 自己定义。[参考文献 3]

**历史实现与当前修正必须分开。** `c5af27d/e565c98` 同时把 \(M_p,K_p,F_p\) 的牵引边界行列置成单位。这破坏稳态 Stokes 的黏性/体积尺度极限，虽然外层仍求解未变的原 Jacobian 并通过真残量门槛。第 8.2 节首轮物理收据记录的是该历史实现；不能把它们作为本节新边界公式的执行证据。修正已同步于 `19cd26f`，其物理回放另见第 8.4 节。

### 2.3 逐层保留物理候选的 field AMG

联合速度层级的候选矩阵记为 \(N_\ell\)，每行有 13 个候选槽位：

| 槽位 | 意义 |
|---|---|
| 0–2 | 流体三个分量的平移 |
| 3–5 | 固体三个分量的平移 |
| 6–8 | 流体参考坐标旋转 \(\omega\times(X-X_c)\) |
| 9–11 | 固体参考坐标旋转 \(\omega\times(X-X_c)\) |
| 12 | 标量刚体速度 |

旋转仅在 `-pc_plan_velocity_coarse_space rigid` 时启用；默认 `constants` 下六个旋转槽位为零。坐标按 owned 有效顶点行计算全局中心与尺度；实际分量由 `DofKey.component` 评价，不假设 xyz 行号连续。精确恒等行的候选为零。候选是动态问题的 near modes，不声明为完整 FSI 的精确零空间。

细层节点块按完整语义键分组，仅将 component 清零；聚合时保留节点实际存在的所有分量。每个 MPI owner 在本地矩阵图上生成连接 aggregate，允许跨流/固场边；后续层的块是前一 aggregate 的所有粗系数。每个 aggregate 对 13 列做两遍 modified Gram–Schmidt，剔除零列及线性依赖列，得到局部正交基 \(Q_g\)。拼成 \(P_\ell\) 后，继续递归

\[
N_{\ell+1}=P_\ell^TN_\ell,\qquad
A_{\ell+1}=P_\ell^TA_\ell P_\ell.
\]

每层审核

\[
\frac{\|N_\ell-P_\ell N_{\ell+1}\|_F}
 {\max(1,\|N_\ell\|_F)}\le10^{-10}.
\]

因此可表达的流/固平移、旋转和它们的线性组合会传到后续层；完整 \(A_\ell\) 的跨场项进入 Galerkin 投影。每个 aggregate 的实际秩可以小于 13，避免强制为小型/缺分量 aggregate 生成 13 个粗列。本实现的插值没有额外平滑步骤；`field_amg` 不能与旧 `aggregate` 路径中“先构造一层语义粗空间、随后交给标量 GAMG”混同。

### 2.4 界面混合 patch 后校正

令 \(\mathcal H\) 为既有 bulk 块预条件器的单次响应，\(R_i\) 限制到第 \(i\) 个界面 patch。patch 取当前刷新代的实际混合子矩阵 \(J_i=R_iJR_i^T\)，包含可达的流体/固体速度、压力和 ALE 行。对每个全局行 \(j\)，令 \(m_j\) 为所有 MPI rank 上真实 patch 的覆盖次数，\(W_i=\operatorname{diag}(1/m_j)\)。一次作用为

\[
x_0=\mathcal Hr,\quad e=r-J_{\rm current}x_0,\quad
x=x_0+\omega\sum_iR_i^TW_iJ_i^{-1}R_ie.
\]

这是 bulk 与界面校正之间的乘法组合、patch 之间的加法组合。`vanka` 与 `patch` 是同一实现的别名。种子来自真实界面顶点的独立行元数据；图邻接扩展后排除精确恒等约束行与 boundary 端口标量。没有把每个压力节点自动当成界面，也没有将局部矩阵对角化来简化耦合。

若已有自适应 PC 策略选择复用，\(\mathcal H,J_i\) 可来自上一刷新代；后校正残量始终用当前原始 \(J_{\rm current}\)。该范围必须与“每次 Newton 都使用新因子”区分。

## 3. 算法步骤

1. **配置与元数据。** 集体检查 recipe、owned 语义、参考坐标、真实界面标记及选项；即使初始状态恰好零残量，也检查选项和 PCD 更新回调契约，但不分解未使用的 PC。
2. **成功装配。** 完成 owned/halo 物理装配、集体失败检查、矩阵归并及约束行处理，再调用 `NonlinearAssemblyPhases::after_jacobian`。FSI 重建同一阶段状态，包含界面 alias 与非零入口 lifting，然后更新 PCD 三元辅助算子。
3. **建立或刷新 PC。** 按现有刷新策略更新 USER 压力矩阵、patch 局部因子、bulk 数值层级和 RCR 响应。固定图、ownership、几何元数据与约束集合允许符号结构/插值复用；不满足这些条件则重建会话。原始 Jacobian 继续更新，不以旧 PC 替代它。
4. **单次响应。** 外层 FGMRES 使用块预条件器；联合速度默认 `PREONLY` 应用一次多层循环，压力默认 `PREONLY` 应用上述 shell，界面 wrapper 先调用一次 bulk，再做加权混合校正。RCR 存在时置于最外层。
5. **收敛与失败。** 保留原始 Jacobian 的真实残量检查和原非线性接受条件。局部奇异、非有限或子 PC 实质失败传播到外层；失败刷新使该代状态无效，成功刷新才重新可用。PETSc 回调恢复借用数组并完成必要 scatter，不把失败伪装成有效的有限响应。物理历史仅由原接受步路径提交。

### FP32 局部因子、改进与回退

对 patch 矩阵，取行最大值 \(r_a=\max_b|(J_i)_{ab}|\)，再取列最大值 \(c_b=\max_a|(J_i)_{ab}/r_a|\)，构造

\[
\widehat J_i=\operatorname{diag}(r)^{-1}J_i\operatorname{diag}(c)^{-1}.
\]

稠密 LU 使用部分选主元。FP32 分解阈值为 \(8\epsilon_{32}\max(1,n_i)\)，FP64 路径同样按本身机器精度检查；小于阈值或非有限的主元被拒绝，不加入对角正则化。右端按行缩放后再归一化，降低 float 上溢风险。

解与改进更新保存在 double；残量使用 FP64 patch 原矩阵，并以 long double 累积乘加。所有行必须满足分量后向误差门槛

\[
|b_a-(J_ix)_a|\le\tau\left(|b_a|+\sum_b|(J_i)_{ab}x_b|\right).
\]

默认 \(\tau=10^{-10}\)，最多三次 FP32 三角求解改进。FP32 setup 不安全，或改进未通过门槛，则显式重新以 FP64 分解；apply 时回退后，该 patch 在本代余下作用保持 FP64。FP64 也必须通过相同残量门槛，否则失败。保留原误差门槛，不通过降低准确度来获取“成功”。

## 4. 关键推导与不成立的推论

对交换子变体，若 \(D=0\)，公式还原相应带实际块符号的 LSC/BFBt 作用。若 \(WA=sI\)，则 \(W=sA^{-1}\)，从而 \(L=sS\)、\(H=s^2S\)，精确辅助求解给出 \(L^{-1}HL^{-1}=S^{-1}\)。这是一个可检验的精确极限，并未给出一般变系数、强对流 FSI 的谱等价证明。

对 PCD，\(\widetilde S=M_pF_p^{-1}T\)，所以在可逆且精确求解的条件下，\(\widetilde S^{-1}=T^{-1}F_pM_p^{-1}\)。该恒等式说明稳定化组合与作用顺序，不能证明 \(\widetilde S\) 对实际 \(S\) 总是更好的近似。压力辅助边界、ALE/材料系数和联合流固速度消元都会影响近似质量。

新边界公式在稳态无对流 \(N=0\) 时满足 \(F_p=\mu K_p\)。由此得到带完整稳定化的精确辅助作用

\[
\mathcal B_{p,\rm PCD}=(M_p/\mu+D)^{-1},\qquad
D=0\Longrightarrow\mathcal B_{p,\rm PCD}=\mu M_p^{-1}.
\]

这是独立 oracle 应直接构造质量/稳定化矩阵检查的极限，不应仅重复实现中的 \(T\) 公式来验证自己。它解释了本轮边界修正，但其新回归执行状态仍以第 8.4 节为准。

这里的恒等式属于 **PCD 近似模型自身**。它没有证明真实有限元 Stokes Schur 在任意边界/网格下都精确等于 \(M_p/\mu\)；对真实 Schur 的近似质量仍需独立物理验证。

对 field AMG，局部正交基使 \(P_\ell^TP_\ell=I\)，并在数值容差内重现候选的列空间。该事实只证明特定近模态不在层间丢失；网格无关收敛还取决于其是否覆盖实际低能量误差、平滑性质、聚合、粗网格求解和分区。

对混合精度，\(4\sum_i n_i^2\) 与 \(8\sum_i n_i^2\) 比较的是未回退的 float/double LU 数值数组，不包括稀疏 patch 原矩阵、向量、索引、通信、bulk/AMG 或压力产品矩阵。不能据此宣称整程序内存或总运行时间减半。

## 5. 数据结构与并行映射

`AlgebraLayout::owned_semantics`、`owned_reference_coordinates` 和 `owned_interface` 跟随 owned 独立行排列。约束 alias 不创建第二个未知量或第二份参考位置。RCR 提取 bulk 时同步压缩这些元数据；同时用 `propagate_pressure_auxiliaries` 按实际分布式 IS 顺序提取并重新组合 PCD 三元辅助算子，初次及后续数值刷新均执行。

PCD 辅助矩阵使用完整根编号以便组合和追踪来源，但仅压力行有单元条目；进入 Schur 后提取实际压力子矩阵。`eonsim_pcd_mass`、`eonsim_pcd_laplace`、`eonsim_pcd_transport` 必须是所有 rank 上完整、同编号/ownership 的三元组。独立 main/inner/upper 子树可共享一个压力状态，工作向量和辅助 KSP 分开持有；每个注册状态只做一次数值刷新。

field AMG 的候选数据量为每层 \(13n_{\rm owned}\)。聚合不跨 owner，但 Galerkin 矩阵保留跨 owner 和跨物理场耦合；候选审计、全局中心和粗行计数使用归约。插值及稀疏矩阵产品分布式存储，没有把全局矩阵或完整场向量 gather 到一个 rank。此设计仍可能在大量小分区下停止粗化，`coarse_limit` 不是一定能达到的粗网格尺寸。

patch 用 `MatCreateSubMatrices` 取得包含 off-rank 行的局部顺序子矩阵；`VecScatter` 获取残量并反向累加校正。覆盖次数由所有 patch 反向 `ADD_VALUES` 得到，再发送给需要它的 patch，因此重叠权重包括跨 rank 重复。没有界面种子的 rank 仍参加集体通信。每个 patch 的大小受上限保护，超过上限报错，不截断物理耦合行。

### 首轮空 owner 失败与修复

`c5af27d` 的界面测试在 1、2 rank 通过，4 rank 含空 patch owner 时失败：先出现 `MPI_ERR_BUFFER`，随后其他 rank 等待，120 秒超时。保留的 `-on_error_abort -info` 复现给出 `MPI_ERR_TRUNCATE`。当时环境没有 GDB/LLDB，不把本次诊断写成已经执行过调试器。[第 8 节证据]

根因在 PETSc **v3.23.7** 的 `MatIncreaseOverlap`：参数 `n` 有 logically collective 检查，而 `n==0` 会在进入 MPIAIJ overlap 通信之前返回。若直接传各 rank 不同的真实 patch 数，空 rank 跳到后面的 collective，非空 rank 仍在 overlap 内，后续 `VecScatterCreate` 上暴露通信错序。[参考文献 4]

`e565c98` 的修复只改变 setup：先归约得到最大 patch 数，临时补空 IS，使所有 rank 以相同正数参加 `MatIncreaseOverlap`，返回后销毁补位并恢复真实 patch 数。空补位从未成为数值 patch 或未知量；权重、局部矩阵及精度门槛不变。测试增强为 4 rank 的真实 patch 数 `2/1/0/0`，修复后的 1/2/4 rank 均通过。`MatCreateSubMatrices` 的契约不同，允许每个 rank 的局部数量不同，不能把这里的补位规则机械套用到其他 API。

## 6. EONSim 实现与完整前缀

### 选项

| 选项 | 默认值 | 本轮支持/限制 |
|---|---|---|
| `-pc_recipe` | 保持既有入口行为 | 组合本轮能力通常用 `hybrid`；所有 `pc_plan_*` 选项要求语义 recipe |
| `-pc_plan_velocity_solver` | `split` | 新增 `field_amg`；保留既有其它选择 |
| `-pc_plan_velocity_coarse_space` | `constants` | `field_amg` 支持 `rigid`，含流体和固体旋转候选 |
| `-pc_plan_velocity_aggregate_nodes` | `16` | `aggregate/field_amg` 专用，范围 2–4096；后续层指前一 aggregate 块的数量 |
| `-pc_plan_schur_approx` | `diagonal` | `diagonal/nodal/lsc/bfbt/pcd`；需要真正的压力 Schur |
| `-pc_plan_interface_smoother` | `none` | `vanka`、`patch` 同义；需要真实且非空的全局有效界面顶点 |
| `-pc_plan_patch_precision` | `double` | `double/fp64` 或 `single/fp32`；必须同时启用界面校正 |
| `-pc_plan_patch_overlap` | `1` | 图扩展层数，0–2 |
| `-pc_plan_patch_max_size` | `256` | 1–2048；超过则报错 |
| `-pc_plan_patch_refinement_steps` | `3` | 0–8；耗尽后仍可显式 FP64 回退 |
| `-pc_plan_patch_refinement_tolerance` | `1e-10` | 分量后向误差门槛，`1e-14`–`1e-4` |
| `-pc_plan_patch_damping` | `1` | \(0<\omega\le2\) |
| `-pc_plan_rcr_ports true` | 保持既有默认 | 有 boundary-pressure 端口的 PCD 必须开启，以把端口从物理压力空间排除 |
| `-pc_plan_report` | 关闭 | 输出块前缀、压力类型、AMG 层级/再现误差及 patch/精度计数 |

拓扑选项必须跨 rank 一致。新压力 shell 及 field AMG 的响应类型只接受 `PREONLY` 或显式 `FGMRES`。含上述可变内层作用的根求解器要求 `FGMRES`。`interface_bulk_` 和 `rcr_bulk_` 固定为 `PREONLY`，界面 bulk 还要求零初值。

对没有用户根前缀的 `hybrid`，完整前缀如下。表中是前缀本身，给 PETSc 选项时需加前导 `-` 和选项名。

| 对象 | 普通 hybrid | 加界面校正 | 同时加 RCR 与界面校正 |
|---|---|---|---|
| 联合速度 | `fieldsplit_dynamics_fieldsplit_velocity_` | `interface_bulk_fieldsplit_dynamics_fieldsplit_velocity_` | `rcr_bulk_interface_bulk_fieldsplit_dynamics_fieldsplit_velocity_` |
| 压力 shell | `fieldsplit_dynamics_fieldsplit_pressure_` | `interface_bulk_fieldsplit_dynamics_fieldsplit_pressure_` | `rcr_bulk_interface_bulk_fieldsplit_dynamics_fieldsplit_pressure_` |
| 压力辅助 KSP | `fieldsplit_dynamics_fieldsplit_pressure_pressure_aux_` | `interface_bulk_fieldsplit_dynamics_fieldsplit_pressure_pressure_aux_` | `rcr_bulk_interface_bulk_fieldsplit_dynamics_fieldsplit_pressure_pressure_aux_` |
| ALE mesh | `fieldsplit_mesh_` | `interface_bulk_fieldsplit_mesh_` | `rcr_bulk_interface_bulk_fieldsplit_mesh_` |

仅加 RCR 时，在普通前缀前加 `rcr_bulk_`；已有根前缀始终置于最前。实际包裹顺序为 RCR → interface → 语义树。独立 Schur inner/upper 速度响应使用相应压力叶前缀后的 `inner_` / `upper_`，不是主速度叶的同一实例；应以 `pc_block ... prefix=...` 输出为准。

field AMG 使用速度叶前缀后的 `field_amg_coarse_limit`（默认 64，范围 1–1000000）和 `field_amg_max_levels`（默认 10，范围 1–16）。达到目标、达到最大层数或无法继续降低维度时停止。不能用 `pc_mg_levels` 强行改层数；不支持在本实现下切换 adaptive coarse space。默认上下行 smoother 为一次 Richardson + ASM(overlap=1)/ILU(1)，粗层为 GMRES（rtol=`1e-10`、max_it=200、真实未预条件范数）+ ASM(overlap=1)/局部 LU；全恒等问题退化成单层精确 Jacobi。

压力辅助默认 `PREONLY` + GAMG；设置 rtol/max_it 不会使 `PREONLY` 自动开始迭代。显式改为迭代 KSP 才启用保留的 rtol=`1e-3`、max_it=30 默认预算。压力 GAMG 粗层默认 GMRES/Jacobi（rtol=`1e-10`、max_it=200）。例如，在同时有 RCR 和界面 wrapper 时，辅助迭代类型的完整选项为 `-rcr_bulk_interface_bulk_fieldsplit_dynamics_fieldsplit_pressure_pressure_aux_ksp_type gmres`。

下面是**配置示例，不是新增已执行实验记录**；实际问题路径、分区及停止门槛应与算例一致：

```text
-pc_recipe hybrid
-pc_plan_velocity_solver field_amg
-pc_plan_velocity_coarse_space rigid
-pc_plan_schur_approx bfbt
-pc_plan_interface_smoother vanka
-pc_plan_patch_precision single
-ksp_type fgmres
-pc_plan_report -linear_report -solver_report
```

若将 Schur 改为 `pcd`，算例必须提供有效物理 PCD 辅助算子及压力牵引边界；若还含 RCR 端口，则添加 `-pc_plan_rcr_ports true`。不要把根 `-pc_type` 改成其它 PC 来绕开 wrapper 校验。

### 源码入口

以下路径均按当前固定实现提交 `19cd26f2af9b02859fac28ca8f662c29c20d47f1` 核对；执行证据依第 8 节各自固定源码区分：

| 路径 | 核心职责 |
|---|---|
| `include/eonsim/linear_system.hpp`、`src/fem/reduced_layout.cpp` | owned 语义、参考坐标与真实界面标记 |
| `src/algebra/pc_plan.cpp` | recipe 装饰、选项验证、wrapper 顺序及递归前缀 |
| `include/eonsim/coupled_velocity_pc.hpp`、`src/algebra/coupled_velocity_pc.cpp` | `field_candidates`、`field_transfer`、`configure_coupled_velocity_field_amg` |
| `include/eonsim/pressure_schur_pc.hpp`、`src/algebra/pressure_schur_pc.cpp` | 共享压力状态、数值产品、shell、辅助算子传播 |
| `include/eonsim/fsi_pressure_operators.hpp`、`src/physics/fsi_pressure_operators.cpp` | P1 ALE 压力辅助单元算子及辅助边界 |
| `src/physics/fsi.cpp`、`src/algebra/nonlinear_system.cpp` | 同一阶段数据、成功 Jacobian 后的回调与会话/刷新管理 |
| `include/eonsim/interface_patch_pc.hpp`、`src/algebra/interface_patch_pc.cpp` | 混合 patch、跨 rank multiplicity、FP32/FP64 因子与诊断 |
| `src/algebra/rcr_port_pc.cpp` | RCR 外层响应与 compact bulk 上的辅助算子同步 |

诊断包括 `pc_field_amg`、`pc_field_amg_level`、`pressure_schur`、`interface_patch_pc` 和 `interface_patch_stats`。后两者含 `patches`、`fp32`、`fp64`、`factor_bytes`、`setup_fallbacks`、`apply_fallbacks`、`refinements`；运行结束应读取 stats，而不能仅凭 setup 输出断言没有发生 apply 回退。patch 数、因子字节与局部改进次数按 rank 求和；`applications` 是每个 rank 参加同一次分布式 PC 的次数，不能把其 rank 求和当成逻辑 PC 调用次数。

## 7. 复杂度和性能影响

界面 patch 的稠密分解工作量为 \(O(\sum_i n_i^3)\)，一次三角求解为 \(O(\sum_i n_i^2)\)；每次改进另需原 patch 的稀疏残量与一次三角求解。增加 overlap 既扩大空间覆盖，也可能明显增加因子内存、通信和 setup 成本。上限的作用是明确预算，而不是保证更大 patch 更快。

field AMG 的候选存储按每层 owned 行线性增长；每个 aggregate 的局部正交化最多处理 13 列。实际稀疏乘积 fill、层数和粗层迭代决定层级复杂度。LSC/BFBt 需要两次辅助逆作用与一个中间矩阵作用，PCD 需要质量对角逆、输运乘法和一次 \(T\) 辅助逆；仅比较辅助调用次数不足以推断总成本。

首轮同一双域例的全部 FP32/FP64 patch 因子数组总字节分别为 `108136/216272`，配对外迭代数相同。它仅支持局部因子数值数组减半的结论。第 8.3 节的单次局部门槛诊断仍发生大量改进，不支持把局部更低精度直接等同于端到端加速。

第 8.4 节已有当前 PCD 的三档物理加密原驱动结果：1 rank 的累计外迭代为 `142/160/225`，2 rank 为 `144/166/225`，对应 `703/2299/5367` 个自由度，每例均 6 次 Newton 线性修正。它显示此窗口内有限的增长，但不是网格无关的证明。

[完整跨方案与强耦合数据](../research/data/fsi-advanced-2026-11-26/README.md)已经归档。2 rank 三档 field+nodal 为 `82/99/131`，BFBt+FP32 patch 为 `94/109/140`，最终 PCD+FP32 patch 为 `144/166/225`。新 PCD 明显改善了旧边界版本，但仍多于前两者；field AMG 相对相同压力的旧 aggregate 也没有普遍迭代优势。

六组密度比 `1/.1/.01` 与时间步 `.02/.005` 的同 Schur 对照中，BFBt 加 patch 少 `2.44%–11.96%` 外迭代，但所记录的小算例线性时间更长。PCD 小例加 patch 反而更多迭代。当前没有独占资源上的重复计时；单次时间只作原始观测，未据此声明稳定时间、全局内存或带宽收益。完整物理配置、分区、容差、硬件、二进制/依赖摘要及计时边界见证据和 provenance。

## 8. 已执行验证与证据

### 8.1 定向代数验证

以下命令均在源码同步后执行；`N` 表示分别运行 1、2、4 rank，不是一个实际命令参数。原始记录及失败均已保留在[证据归档](../research/data/fsi-advanced-2026-11-26/README.md)，归档内部沿用对应 `build/` 路径。

```text
bash build/locked.sh mpiexec -n N build/cloud-3.23.7-release/verify_field_amg
bash build/locked.sh mpiexec -n N build/cloud-3.23.7-release/verify_pressure_schur
bash build/locked.sh mpiexec -n N build/cloud-3.23.7-release/verify_interface_patch
bash build/locked.sh mpiexec -n 1 build/cloud-3.23.7-release/verify_fsi_pressure_operators
bash build/locked.sh ctest --test-dir build/cloud-3.23.7-release \
  -R '^fsi_pressure_operators(_mpi2)?$' --output-on-failure -j1
```

| 检查 | 实际结果与源码 | 证据路径 |
|---|---|---|
| field AMG | `c5af27d`，MPI 1/2/4 全通过；385/1297 个制造代数自由度构造 3/4 层，逐层重现候选并独立审核数值变更后的 \(P^TAP\) | `build/fsi-advanced/initial/field/rank{1,2,4}.{command,exit,log}` |
| 压力 Schur | `e565c98`，MPI 1/2/4 全通过；独立稠密 oracle、完整/零 \(D\)、标量精确极限、empty owner、共享刷新、辅助三元组传播及失败/恢复 | `build/fsi-advanced/fix-e565c98/pressure/verify_pressure_schur_mpi{1,2,4}.{json,log}` |
| 界面 patch | `e565c98`，MPI 1/2/4 全通过；独立加权稠密/稀疏 oracle、非对称耦合、非局部行、约束/端口排除、`2/1/0/0` patch 数、FP32/改进/强制回退、刷新/恢复及原始残量 | `build/fsi-advanced/fix-e565c98/interface/results.json`、`rank{1,2,4}.log` |
| 最终物理 PCD oracle | `19cd26f`，1/2 进程两项通过，含 SELF oracle 与 WORLD fixture；6 个独立 Stokes 作用、4 代积分、WORLD 空 owner/黏度拒绝及恢复 | `build/fsi-advanced/pcd-fix-19cd26f/pcd-operators{,-full}.log`、`pcd-operators.xml` |
| 首轮失败 | `c5af27d` 界面 MPI 4 失败并超时；诊断与修复见第 5 节 | `build/fsi-advanced/initial/interface/results.json`、`diagnosis.json`、`rank4.log`、`abort-diagnostic.log` |

历史 e565 物理单元 oracle 使用 `PETSC_COMM_SELF`，以 2/4 进程启动只是重复串行 fixture；19cd 新增的 WORLD fixture 才覆盖空流体 owner、局部/跨 rank 黏度不一致与拒绝后恢复。制造 field AMG 的迭代数为小型代数证据，不能替代真实物理网格加密实验。界面 FP32 因子分支及回退以实际统计量断言，外层 FGMRES 解还检查 \(\|Jx-b\|<10^{-10}\|b\|\)。

### 8.2 首轮真实物理验收，固定 c5af27d

原始收据为 `build/fsi-advanced/initial/physical/1795682143415893521/results.json`，驱动为 `tests/verify_fsi_advanced_pc.py`，生产二进制 SHA256 为 `969465bbd83039c6f1847bf68ed69a0ffa07ab526e823efd079e53fae146a817`。收据含每条实际命令、完整输入、分区摘要、输出/日志哈希及源版本。独立原件审计见 `build/fsi-advanced/initial/independent-physical-audit.json`：重新解析全部步的 CSV/VTU、owner/ghost 与拓扑，核对原件哈希并重算日志残量/门槛比；该审计没有离线重新计算一次 \(J\Delta x-b\)。

本轮首批共 **20 次求解、54 个接受步、117 次显式线性真实残量检查**，全部通过。计数包括 `cases.runs` 中的 18 次汇总，以及 `commands` 中两次各运行一步的 checkpoint 生成；后两次分别增加 2、3 次线性修正。覆盖 1/2 rank 的 307 自由度双域弹性 FSI、2 rank 的 350 自由度移动 RCR 算例、变步广义 alpha 和两次 restart。

双域例使用 \(\rho_f=\rho_s=1\)、Young 模量 100、Poisson 比 0.3、步长 `[0.02, 0.015, 0.025]`，广义 alpha 的 `rho_infinity=0.5`。每个物理配置与同配置 MUMPS 直接解比较；最大场差 `1.257624560047077e-11 < 2e-9`，最大历史差 `8.104628079763643e-15`，真实线性残量与 `1e-12 + 1e-10 * rhs_norm` 门槛的最大比值为 `0.009257947264879914`。所有 single 物理路径实际产生 FP32 patch 因子。

这些结果证明本批算例的解、历史、真残量及组合路径正确性，**没有证明新压力近似普遍减少迭代**。例如同一个 2 rank 双域三步例，`nodal_field/lsc_field/bfbt_field/pcd_field/pcd_vanka_double/pcd_vanka_single` 的累计外迭代分别为 `72/100/87/442/400/400`。PCD 数字明确属于旧辅助边界版本，不能代表修正后的版本。这是相同输入下的收敛记录；本节不把并行执行验证期间的 wall time 当成独立性能比较。

### 8.3 单次 FP32 局部改进门槛诊断

使用已同步的冻结 `e565c98` 二进制 `build/fsi-advanced/fix-e565c98/eonsim-e565c98`（SHA256 `8a4e69f265f66b765036584ec42f2152f928163a50bae0b98b23726ead5d3a34`），复制初始 `domains-r2/pcd_vanka_single.json`，仅改输出路径，沿用原分区和完整原 flags，追加 `-pc_plan_patch_refinement_tolerance 1e-6`。未执行修改中的物理驱动，未修改生产默认。全部输入、命令、环境、哈希、输出与解析结果记录在 `build/fsi-advanced/fix-e565c98/precision-1e-6-diagnosis/results.json`。

此单次诊断 3 步、6 次修正通过，累计外迭代仍为 400；最大真残量/原门槛比 `0.009043401917193978`，全部步及 final 最大场差 `3.591377195633072e-12 < 2e-9`，历史差 `3.3306690738754696e-16`。16 个 patch 均保持 FP32，无 setup/apply 回退，因子数组 `108136` 字节。但局部改进总次数仍为 **5001**，原 `1e-10` 路径为 6406；并未消除改进。该结果不支持只通过放宽局部门槛就改变默认，也不形成稳定计时收益结论。

### 8.4 当前 PCD 边界修正后的物理回放，固定 19cd26f

原驱动收据 `build/fsi-advanced/pcd-fix-19cd26f/physical/1795683464167404865/results.json` 的 `status=passed`、`failures=[]`，记录 **38/38 次求解通过**。二进制 SHA256 为 `45ce710b6f7d1358c4b0524c9dc41d8cd2218beee2e416295d4c311d57132d77`，driver SHA256 为 `80130182769c0f93c634d241cd0533e5f7bb9adb4d80682df2375e91a72b12e7`。独立原件审计已通过，文件为 `build/fsi-advanced/pcd-fix-19cd26f/final-independent-physical-audit.json`；SHA256 `1e31e0149d9f8f5a24399316f29aa49be88bb813257f4b6e706573bfc0afb988`。

36 个 `cases.runs` 汇总加两次 checkpoint 生成共 38 次，即 34 个完整轨迹、2 次首段和 2 次续算；108 个接受步、225 次 Newton/已测线性修正。覆盖双域与移动 RCR、restart、1/2 rank 的三档加密、2 rank 下三档密度比及两档时间步。汇总中最大场差 `3.1915137199689525e-11 < 2e-9`，最大历史差 `5.684341886080802e-14`，最大真残量/原门槛比 `0.009273085855602773`。

相同 307 自由度、2 rank 三步输入中，`pcd_field` 的累计外迭代由历史 `442` 降为 `150`；PCD+patch 从 `400` 降为 `161`，double/single 均为 161。修正恢复了边界尺度，并改善了这组观测；当前 PCD+patch 仍比无 patch 的 150 多，不能把界面校正的效果写成单调改善。三档加密 PCD+single patch 结果见第 7 节；本轮仍需与 nodal/BFBt 同配置结果一起评估，而非只同旧 PCD 比较。

最终 2 项 PCD CTest 通过：六种 Stokes 作用最大相对误差 `2.06789e-15`，四代积分误差 `3.97763e-16`。同一新测试链接冻结 e565 静态库的负控实际 exit 1，首先报 `PCD failed independent Stokes mass-limit action oracle`；正式二进制未被替换。完整负控命令、编译器/库/源码摘要与原日志在 `build/fsi-advanced/pcd-fix-19cd26f/negative-control/`。

独立解析器重读全部步的场、历史、ghost、拓扑及原程序的显式残量诊断标量，1544 个历史 pin 全部匹配，owner/ghost 最大差 0。没有保存每步 J/b/dx，故不称为一次新的离线矩阵乘法验算。跨源比较还确认 15 个 case 的物理配置、网格和容差一致；26 对 HDF5 分区容器的原始 SHA 不同，但完整类型/数据/属性语义相同。原 SHA 与语义比较均保留在[对照收据](../research/data/fsi-advanced-2026-11-26/pcd-comparison.json)。

原始收据、独立解析器、首次失败和修复证据都见[完整归档](../research/data/fsi-advanced-2026-11-26/README.md)；源码 CI 收据单独保存，后续文档 head 只复用未受影响证据。未执行独占资源重复计时，不将单次时间样本升级为稳定加速结论。

## 9. 适用范围与失效模式

应监控原始残量、正收敛理由、Newton 接受步、AMG 每层再现误差/尺寸、压力数值刷新次数、patch 最大尺寸以及 FP64 回退数。以下情形会报错或需要重新选择配置：

- recipe/前缀与固定拓扑冲突、跨 rank 选项不一致、错误外层 KSP 类型，或者在没有界面 smoother 时设置 patch 参数。
- 缺少真实界面元数据、全局没有有效界面顶点、patch 为空/超限、奇异或非有限局部因子；不会静默丢行、pin 压力或正则化。
- PCD 缺少成功 Jacobian 后的更新回调、辅助三元组不完整、编号不匹配、质量非正或非集中、缺少现有牵引辅助边界；新边界版本拒绝非均匀或非正黏度，RCR 端口未隔离时也明确拒绝。
- 同一会话内拓扑、ownership、语义、参考位置或约束集合变化，导致固定插值/patch 图失效；需走现有会话重建机制。
- 多层粗化达到最大层数或停滞。粗层规模仍可能较大，且有限工作量 GMRES 不是精确粗解；强各向异性、极端材料比、强对流、高阶/非共形场需要另行设计与证据。

新增接口不会自动建立最优的 PCD 辅助边界，也没有把 Vanka 放进每一层 AMG。强耦合与附加质量问题的改善是需通过物性/时间步对照判定的目标；密度比本身不等于一个精确的附加质量数。全部能力保持显式选项，默认 `split/diagonal/none/double` 不变。

## 10. 参考文献与固定源码

1. H. Elman, V. E. Howle, J. Shadid, D. Silvester, R. Tuminaro, *Least Squares Preconditioners for Stabilized Discretizations of the Navier–Stokes Equations*, SIAM J. Sci. Comput. 30(1), 290–311；重点为第 4 节、p. 301 式 (4.13)。[DOI: 10.1137/060655742](https://doi.org/10.1137/060655742)，[作者公开稿](https://www.math.ttu.edu/~vhowle/publications/065574.pdf)。它提供稳定化交换子背景，不为本文的具体缩放变体提供普适最优性结论。
2. PETSc [`PCLSC`](https://petsc.org/release/manualpages/PC/PCLSC/)，Notes 中的 Schur 定义、忽略 \(A_{11}\) 的限制及矩阵组合接口。通用 API 文档会更新；实际验证环境为 PETSc 3.23.7。
3. Firedrake [`PCDPC` 源码](https://www.firedrakeproject.org/_modules/firedrake/preconditioners/pcd.html)，类说明与 `apply` 的 \(K^{-1}F_pM^{-1}\) 顺序。本文不复制其 Laplace 正则项或将其边界处理作为 EONSim 的实现。
4. PETSc **v3.23.7** [`src/mat/interface/matrix.c`](https://github.com/petsc/petsc/blob/v3.23.7/src/mat/interface/matrix.c)，`MatIncreaseOverlap` 中 `PetscValidLogicalCollectiveInt(mat,n,2)` 与 `!ov || !n` 返回；另见 [`MatIncreaseOverlap`](https://petsc.org/release/manualpages/Mat/MatIncreaseOverlap/)、[`MatCreateSubMatrices`](https://petsc.org/release/manualpages/Mat/MatCreateSubMatrices/) 的各自集体契约。
5. PETSc [`MatPtAP`](https://petsc.org/release/manualpages/Mat/MatPtAP/) 与 [`PCMG`](https://petsc.org/release/manualpages/PC/PCMG/)，Galerkin 乘积和多层应用接口；它们本身不提供本文候选集合的 FSI 收敛保证。
6. EONSim 当前固定源码树 [`19cd26f2af9b02859fac28ca8f662c29c20d47f1`](https://github.com/saitoasukakawaii/EONSim-new/tree/19cd26f2af9b02859fac28ca8f662c29c20d47f1)，具体路径/函数见第 6 节；修复后代数证据对应 [`e565c98`](https://github.com/saitoasukakawaii/EONSim-new/tree/e565c9872551dad9dc7a01d4d7b613e8a96d3545)，首轮物理证据对应 [`c5af27d`](https://github.com/saitoasukakawaii/EONSim-new/tree/c5af27de8fdc7a42df855543ad6366ce7db70571)。
7. FENaPack [Mathematical background](https://fenapack.readthedocs.io/en/latest/math.html)，BRM2 的 outlet Laplace 辅助条件及 time-dependent 扩展；[`PCDPC_BRM2.apply`](https://fenapack.readthedocs.io/en/latest/_modules/fenapack/preconditioners.html) 中保留质量逆并只对 Laplace 校正施加辅助边界的顺序，及同页 BRM1 对 leading Stokes term 的说明。EONSim 没有复制其实现，完整 \(D\) 的 \(T\) 扩展为本文显式推导的变体。

公开算法草稿见 [fsi-field-amg-pressure-interface.md](../../website/drafts/fsi-field-amg-pressure-interface.md)，仍保留在 drafts，不自动提升为正式知识页面。
