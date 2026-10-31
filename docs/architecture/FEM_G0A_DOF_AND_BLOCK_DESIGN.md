# FEM-G0A：DoF 语义、存储排列与 FSI 分块接入设计

日期：2026-10-30（Asia/Shanghai）。2026-10-31 合并更新：**设计与独立参考验证已审查合入，未实现 C++ 接入**。
唯一源码基线：`f44c3e0e81f090637f6f21a7b63a9d12d3e30424`。
本专题细化 [通用规划](GENERAL_FEM_ARCHITECTURE_PLAN.md) §6–7/G0；以下接口和配置均为设计，当前程序不能直接读取。

## 1. 基线、范围与决策

开始时 `git fetch origin main` 后，HEAD 与 origin/main 均为上述 SHA，ahead/behind 为 0/0，工作区干净。
GitHub 只读查询 `repo:saitoasukakawaii/EONSim-new is:pr is:open` 返回空列表；这是本次查询快照，不保证远程以后不变。
设计阶段在本地 `docs/fem-g0a-dof-design` 工作，没有提交、推送、PR、远程构建操作。2026-10-31 用户追加授权提交并推送该设计分支；不创建 PR、不合并、不触发远程构建。未修改 `sources/` 同步参考文件。
[基线记录](../research/data/fem-g0a-2026-10-30/baseline.json) 保存本次快照。

2026-10-31 后续用户明确授权合并远程分支并清理多余分支。本次复核源提交 `b674d5a082173a695a0932c1f8f58f4e6563ff04`、重跑 20 项参考测试，并修复检查工具的 UTF-8 读取与 Windows CRLF 哈希误报；见 [合并清理记录](../development/BRANCH_CLEANUP_2026-10-31.md)。下文原始设计过程保留其当时状态；当前 FEM-G0A 设计子任务已交付，G0 的生产实现与真实数值验收仍未完成。

10 h 是工程量预算：基线 0.5、审计 1.5、接口 2、FSI/PETSc 2、参考验证 2、性能/切片 1、交叉审查 1 h。
预算不是实际耗时；不以等待凑时，不报告“实际工作 10 小时”。
本次只读源码/官方资料，写文档和标准库 Python；没有 CMake、编译器、CTest、MPI、EONSim、性能或网站构建。
FEM-G0A 从 `in_progress` 转 `review`；FEM-G0 整体仍 deferred，其他 G 阶段没有启动。

历史证据不升级：[BRANCH-01](../development/BRANCH_INTEGRATION_2026-10-30.md) 只做合并期静态/脚本检查；
[INFRA-01](../research/INFRA_01_REPRODUCIBLE_MPI_CI_2026-10-30.md) 的原分支 CI 对应其记录的提交，最终集成数值验收仍待执行，保持 review；
[HPC-02](../research/FLUID_COO_ASSEMBLY_2026-10-30.md) 的独立流体 COO、历史 Release 故障与后续修复各有提交/环境边界，不能当作本设计或 FSI COO 的验证。

确定的设计决策：

1. 第一接入保持原 root 存储、约束、默认求解行为和验收字段，仅增加语义到 owned IS 的适配。
2. 语义身份、独立代表、分布式映射、存储编号、验收划分、PC 树是六项不同契约；禁止用一个 `fields` 同时驱动可变 PC 与物理验收。
3. 界面代表固定选结构速度或单轴刚体速度。多个标签不产生多个独立行；ALE 界面位移是带 BE 系数和历史 lifting 的重建量。
4. 子块 IS 使用**直接父算子的分布式全局编号**；既不是根全局编号，也不是当前 rank 的局部数组下标。
5. 首个后端为标量索引的 AIJ + IS（block size 1）；约束后分量数不齐，不能从“3D”强行设 IS block size 3。不依赖 MatNest、DM、新 FEM 框架或持久 SNES 改造。

## 2. 固定提交的源码映射

表中链接均固定到基线提交，行号指该提交。迁移位置是未来职责，不是已经存在的类。

| 源码位置 | 当前行为 | 限制/不能推断的能力 | 拟迁移位置 |
|---|---|---|---|
| [discretization.hpp:27–57](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/include/eonsim/discretization.hpp#L27-L57) `NodalLayout/CoupledLayout` | `node*components+c`，Tet4Flow 4、Tet4Ale 7、Tet4Elastic 10 分量；压力 3、mesh 4–6、structure 7–9 | 局部 kernel 分量槽，不是通用空间身份或全局 DoF 编号 | 保留固定尺寸 kernel；语义适配放 `field_layout/reduced_layout` |
| [mesh.hpp:15–40](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/include/eonsim/mesh.hpp#L15-L40)、[partition.cpp:125–164](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/mesh/partition.cpp#L125-L164) | `Node.global_id` 与 `algebra_ids` 分开；owner 是邻接单元 rank 的最小值；节点 owned 在前，cell.nodes 是本地下标 | 只有节点型 DoF；当前分区 fingerprint 含 rank 数 | mesh 保持权威 owner；新增语义键关联当前实体 ID |
| [field_layout.cpp:7–30](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/fem/field_layout.cpp#L7-L30) | `global_dof=algebra_node*nc+c`；groups 每分量恰覆盖一次；owned 行生成 fields，ghost 只进 local_to_global | 分组依赖统一节点分量数；没有独立验收/PC 配置 | 原编号保持；生成最小 `DofSemantics` 与验收标签 |
| [linear_system.hpp:46–55](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/include/eonsim/linear_system.hpp#L46-L55) `AlgebraLayout` | owned/global/begin，owned+ghost global 编号，AIJ diagonal/off_diagonal 预分配，owned fields | fields 是行列表，不是身份；diagonal/off_diagonal 指 MPI 列归属，不是物理块 | 保留存储对象；首切片明确 fields 只作旧验收事实来源，PC 改用另一个 plan |
| [reduced_layout.cpp:17–53](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/fem/reduced_layout.cpp#L17-L53) | alias 自指为独立，`-1` 为零约束或 inactive，`-2` 为刚体；双域去除不存在字段，流体/mesh 界面分量指向 structure 主分量 | `-1` 混合了两种语义；当前 FSI 本质条件是齐次分量约束，不支持通用非零 FSI BC | 语义记录区分 absent/prescribed/alias；首切片不改消元代码 |
| [reduced_layout.cpp:54–102](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/fem/reduced_layout.cpp#L54-L102) | rank owned 计数前缀和编号；刚体最后 rank 拥有全局最后一行；用 ghost Vec 交换编号，ghost 去重；`global/local` 将完整槽映到有效行/本地数组 | 编号通过 PetscScalar 暂存，不应作为未来通用 int64 ID 交换方式；没有跨分区永久身份表 | 引用既有 reduced 映射；未来整数通信与来源 ID 独立审查 |
| [reduced_layout.cpp:103–125](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/fem/reduced_layout.cpp#L103-L125) | 单元有效列并集送 PETSc preallocator，包含远程 body 行；提取 owned 行 diag/offdiag 数 | 保守 Tet4 图，不是按任意形式项构造的通用图 | 第一接入复用图；约束支撑/排列改变才重建 |
| [fsi_domains.cpp:14–81](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/mesh/fsi_domains.cpp#L14-L81) | 两原始域先匹配节点、三角面、法向/面积；合并界面节点；joined 节点重新赋 `n+1`，cell/face 也重编号 | 没有保存两侧原始 ID 到 joined ID 的持久来源表；不支持非匹配 trace | G0 仅以当前 joined 实体为身份锚；来源表是另一个明确切片 |
| [fsi.cpp:66–104](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/physics/fsi.cpp#L66-L104) | accepted reduced、physical、solid_d、body 分存；界面 `dm=solid_d+dt*vs` 或 `q_n+dt*V`；每次尝试更新 current_dt | reduced 行号相同不等于物理量相同；步长变化必须刷新系数/历史输入 | 固定支撑映射 + 每次试步的数值系数/历史快照 |
| [fsi.cpp:148–176](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/physics/fsi.cpp#L148-L176) | 行列均先取 reduced.global；界面 mesh 行改为 -1，列乘 dt；流体/结构动量累加到共享行；刚体惯性/弹簧仅 owner 加一次；传空通用 constraints | `W≠K`；人工 ALE 界面反力不参与结构动量；不能给结构切线再统一乘一次 dt | 显式区分 trial/test 映射，维持全局项唯一装配 |
| [solid_element.cpp:13–50](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/physics/solid_element.cpp#L13-L50) | 动态结构 `d=dn+dt*x`、惯性 `M(x-vn)/dt`；切线已含 `dt*K_s+M/dt` | 静态 dt=0 时 x 是位移；FSI 动态 structure 是速度，不能按名称归为位移块 | 语义由具体入口/求解阶段确定，不能仅凭字段名 |
| [nonlinear_system.hpp:21–59](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/include/eonsim/nonlinear_system.hpp#L21-L59)、[nonlinear_system.cpp:93–175](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/algebra/nonlinear_system.cpp#L93-L175) | 系统复制固定 layout；fields 验证 owned 全覆盖互斥；非约束行 RMS、约束行最大误差，固定每次 solve 的初始尺度 | 改 fields 会改 N/尺度/初始范数乃至停止条件；不能拿 PC 合并后的 velocity 覆盖它 | `AcceptancePartition` 独立于 `PcIndexPlan`，保持旧字段名/尺度 |
| [nonlinear_system.cpp:349–353](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/algebra/nonlinear_system.cpp#L349-L353)、[427–522](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/algebra/nonlinear_system.cpp#L427-L522) | 通用边界保留行并替换为 x-g/单位行；linear_report 复制验收划分；PC 路径合并 velocity+pressure 为 flow；每 solve 新建 SNES | 保留行约束不同于 FSI 消元；本次不统一改写两者。PC 实例寿命不等于索引缓存寿命 | 保留验收/反力路径，只替换 PC 数据来源；每 solve 新 PC 使用缓存索引 |
| [schur_solver.cpp:23–70](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/algebra/schur_solver.cpp#L23-L70) | 外层 multiplicative，map 顺序 flow/mesh/structure 或 rigid；flow 排序后 Exscan 数量得到子编号，内层 velocity/pressure Schur full+SELFP；GAMG，刚体 Jacobi | 仅 hard-coded 两层；binary_search 假定 pressure 已排序；没有显式结构/ALE 近零空间注入 | 先用通用父编号适配重现现有树，再接三种 recipe |
| [fsi.cpp:177–235](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/physics/fsi.cpp#L177-L235)、[vtu.cpp:31–59](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/io/vtu.cpp#L31-L59) | 收敛后重算界面力，更新历史；按完整物理槽重建节点字段；双域输出筛 cell 保留共同点表；VTU 写 mesh ID/owner/algebra node ID | 输出不是 reduced 向量的直接拷贝；不属于某域单元的点没有该域物理解释 | 独立输出映射，PC 重组无需变化，存储置换须更新反向 scatter |
| [checkpoint.cpp:61–70](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/io/checkpoint.cpp#L61-L70)、[122–146](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/io/checkpoint.cpp#L122-L146)、[fsi.cpp:83–87](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/physics/fsi.cpp#L83-L87) | v3 同 rank/分区、physics signature、字段尺寸/时钟检查；保存 reduced/physical/solid_displacement/rigid | 签名没有独立 reduced 排列版本；只改排列而尺寸不变可能无法靠旧签名发现；不得宣称通用语义重启 | 首切片字节布局不变；真重排切片必须增加 schema/排列标识或规范化编码 |
| [verify_nonlinear_acceptance.cpp:18–105](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/tests/verify_nonlinear_acceptance.cpp#L18-L105)、[verify_schur.py:63–128](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/tests/verify_schur.py#L63-L128)、[verify_domains.py:27–54](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/tests/verify_domains.py#L27-L54) | 已有空字段/尺度/反力、Schur 1/2/4 rank、双域接口/恢复/Jacobian 验证入口 | 本次只阅读，没有执行；入口存在不等于基线提交通过这些检查 | 后续接入在这些入口旁添加针对性对照，不能以本次 Python 替代 |

当前普通布局的一条完整数据链为：`cell.nodes[a]`（本地点下标）→ `algebra_ids[n]`（节点代数号）→ `nc*id+c`（root 行）→ owned Vec 槽 `row-begin` 或 ghost 槽。
FSI 则是 `nc*n+c`（完整物理槽）→ `reduced.global[i]` / `reduced.local[i]`；多个完整槽可指同一个有效行。被消元槽不存在可逆 root 映射。

## 3. 六项 DoF 契约

### 3.1 身份与代表

`DofKey=(mesh_namespace, domain, space_signature, quantity, entity_kind, entity_id, local_mode, component)`。
当前 Tet4 P1 的 entity 是 vertex，`entity_id=mesh.nodes[n].global_id`，mode=0，vector 分量 0/1/2，压力分量 0。
quantity 区分 velocity/pressure/mesh_displacement；space_signature 包含族/阶/连续性与分量解释。
domain 是物理域身份，不把当前 region tag 的数值直接当永久命名空间；tag/region/interface 是附加选择标签。
刚体键使用 `(body_registry, body_id, single_axis_velocity, global_entity, component=0)`，不伪造网格节点。

mesh_namespace 为同一导入/规范化网格谱系的标识，与 rank 数、当前坐标变形和 algebra ID 无关。
**当前 `MeshPartition::fingerprint` 含 rank 数**（[partition.cpp:52–64](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/mesh/partition.cpp#L52-L64)），不可直接用作跨 repartition 的永久 namespace。
首切片由准备期持有一个运行内 mesh token，关联当前 joined `global_id`；不修改分区格式或宣称跨作业身份持久化。
以后保存规范化网格标识和两侧 `(source domain, original ID)→joined entity` 来源表；重新导入顺序、空间/basis 或网格改变必须做迁移，不自动继承键。

约束后独立代表 `IndependentId` 用代表的 DofKey 标识；与它占用的 root 行子集双向映射。
完整语义键到独立代表一般是多对一，已消元固定槽/absent 无代表，不能宣称全部语义 DoF 与行号双射。
**保留行 Dirichlet 是另一种存储情形：**当前普通布局仍有 prescribed 槽的 root 行，由 `x-g` 方程固定；该行不是可自由变化的物理独立量。首适配为每个存储行记录 `row_kind=free|retained_prescribed`，canonical row key 与 root 双射，IndependentId 只对应 free 子集。PC 必须覆盖包括 retained_prescribed 在内的全部有效存储行，验收按 equation/constraint 分开；不为统一概念而在本任务设计的首切片中消掉这些行。下文 FSI 示例已消元固定槽，因此其 root 行恰好全是独立未知量；K/W 公式及参考模型只描述该消元坐标。
共形弹性界面速度选 solid velocity 为代表；fluid velocity 是系数 1 alias，mesh displacement 是 `dt` 系数加历史 lifting 的关联，不是同单位 alias。
固定结构分量意味着界面流体速度固定、界面网格位移由已接受位移重建；inactive 槽没有物理方程/输出意义。
首切片不把当前齐次 FSI 边界扩展成任意非零边界；参考模型的非零 lifting 只证明契约代数。

### 3.2 所有权与编号空间

| 空间 | 内容/拥有者 | 合法转换 |
|---|---|---|
| semantic | DofKey，语义表 owner | 到独立代表/固定数据；不进行 PetscInt 窄化 |
| independent | 消元后的 canonical key | 与 free root 行子集双向映射；retained prescribed 行另标记 |
| root global | `PetscInt`，当前 communicator owned 前缀和 | 行 owner 区间；本地 owned/ghost 槽 |
| local storage | `[owned, unique ghosts]` 数组下标 | `local_to_global`；不作为 PETSc 全局插入号 |
| full local slot | 当前 `nc*node+c` kernel 槽 | 固定支撑 trial/test map，可重复指同一 root |
| parent global | 某 PC 树节点算子的分布式全局行号 | 由父块保留的 root provenance 和 rank 前缀和求出 |
| parent local | 该块 Vec 本地数组下标 | `parent_global-parent_begin`，不能直接传 SetIS |

owner 来自独立代表的 mesh owner；单轴刚体保持最后 rank 一个 owner。ghost 只是读取缓存，不生成新的独立行、验收计数或 owned IS 项。
通信只交换需要的 ghost/alias 映射和少量计数；生产实现不复制参考模型的全局字典。
本阶段同一方阵的试探/测试 reduced 坐标维数相同，但完整映射 K、W 不同；一般矩形 Petrov–Galerkin 是后续扩展。

### 3.3 最小数据与函数（伪代码，未实现）

```cpp
struct DofSemantics {
  // owner: setup context; one entry per local algebra owned/ghost row
  vector<DofKey> key;
  vector<CanonicalRole> role; // physics, quantity, legacy acceptance field
  vector<TagMask> tags;       // optional multi-label selection, never duplicate rows
  vector<RowKind> row_kind;   // free or retained_prescribed; refreshed with BC set
};
struct AffineSlot {
  SlotKind kind;              // absent, prescribed, independent, affine_alias
  LocalSlot representative;  // absent/prescribed: invalid, never a PETSc index
  double trial_weight, lift; // K row and g; current one-master support only
  double test_weight;        // W row; interface ALE is zero
};
struct BlockSpec {
  string name; Selector selector; SplitKind kind; vector<BlockSpec> children;
};
struct BlockIndices {
  BlockId parent;
  vector<PetscInt> owned_parent_rows; // sorted global indices in parent
  vector<PetscInt> owned_root_rows;   // provenance in the same order
  PetscInt global_size, owned_begin; // THIS block's resulting numbering
};
struct PcIndexPlan { vector<BlockIndices> blocks; LayoutEpoch layout; RecipeId recipe; };

// Local adapter. Inputs borrowed until return; result owns compact local metadata.
// Checks the existing maps; never renumbers or modifies AlgebraLayout::fields.
DofSemantics describe_tet4_dofs(mesh, reduced_or_nodal_layout, physics_stage);

// Logically collective setup: local validation -> common failure -> counts/maps.
// Inputs are immutable; output owns arrays (no borrowed temporary selector data).
PcIndexPlan prepare_pc_indices(comm, storage, semantics, compiled_spec);

// No MPI/PETSc. accepted/history and positive dt borrowed for this evaluation.
// Refresh K weights/g, never change support, commit history, or rebuild IS.
void refresh_affine_values(slot_map, accepted, dt);

// Collective PETSc adapter, same communicator and square root A/P layouts.
// Borrow plan through return; PETSC_COPY_VALUES owns copies in IS.
// Installs onto a fresh PC before setup; errors leave no published replacement.
void configure_pc_tree(ksp, A, Pmat, const PcIndexPlan& plan, recipe_options);
```

这些职责优先合入现有头/源文件；只有两个实际消费者需要时才拆新头，不建立空基类或 backend registry。
`AffineSlot` 是映射契约说明，第一 PC 切片仍读取既有 reduced.global/local 和 FSI 代码，不提前迁移残量装配。
单 master 只是当前能力：若关系需要多个 master/非匹配投影，准备期明确拒绝，不能挑一个代表丢掉权重。
alias 图须无环、引用存在、同一实体/分量解释相容；每个有效 owned 存储行恰有一个 canonical role。`AffineSlot` 服务消元与重建；普通保留行边界继续走现有 `x-g/MatZeroRows`，不把其替换行伪装成消元矩阵 W。

验收划分先继续以 `AlgebraLayout::fields` 为唯一事实源，保持 `velocity/pressure/mesh/structure|rigid`。
PC plan 不回写它，`solver.fields` 继续配置物理尺度/容差。后续真正拆名为 `AcceptancePartition` 时一次迁移所有验收和 linear_report 使用方，不长期维护两份验收列表。
合并 PC velocity 后仍分别验收 fluid velocity、structure/rigid 的动量行；这是避免改变 RMS 分母和单位尺度的必要条件。

所有索引视图有效至其 owner 析构或相关 layout epoch 改变；solve 只读准备结果，不持有可变 mesh 的悬空引用。
`NonlinearSystem` 的固定布局约束保持；PC plan 可跨时间步缓存，PETSc PC 仍按每 solve 创建，不暗中开启持久化求解器项目。
类型窄化在准备期检查范围，root/local/parent 行用不同小型包装或明确参数命名，不靠相同整数类型推断空间。
错误报告最少含 phase、tree path、rank、semantic key/root row、expected parent range、reason。
输入/布局错误不是 `StepRejected`，不得通过缩 dt 修复。local 检查失败先在共同阶段传播，再进入 IS/Mat collective；不能某 rank 抛错而其余继续 setup。

### 3.4 失效矩阵

| 变化 | 索引/IS/ghost | 图/矩阵 | nullspace 与输出/重启 |
|---|---|---|---|
| trial 值、材料数值、固定支撑的 dt/g/K/W 系数 | 保留；重试刷新系数、初始验收范数 | 更新数值/PC 数值，图不变 | 几何相关模式按需更新；输出值刷新，accepted 不提前改变 |
| ALE 坐标，拓扑/界面关联不变 | 保留身份/索引 | 更新几何及切线；图通常不变 | 依赖当前坐标的模式/采样刷新，不能误用旧几何缓存 |
| PC recipe/顺序改变 | 重建 PC IS/parent maps；root/ghost 不变 | root AIJ/COO 图不变；重建子矩阵/PC | 重新限制/排序子块模式；物理验收和输出映射不变 |
| 保留行 Dirichlet 值或约束行集合改变，支撑仍在图内 | root 不变；重建验收 equation/constraint 列表 | 数值清零/重装配，再替换行 | 检查 nullspace 与反力语义；不等同消元集合变化 |
| 消元活跃集合、alias master 或支撑改变 | 独立代表/编号/ghost/IS 失效 | 重建图、COO contribution plan、系统 | 重建模式和输出展开；迁移 accepted 或拒绝不相容重启 |
| rank 分区、存储排列、空间/basis、拓扑变化 | 对应所有映射失效 | 重建图/分布式对象 | checkpoint schema/映射和输出计划必检；新网格另需历史 transfer |
| 仅尺度/容差配置改变 | PC 索引不变 | 不改 R/J 数学坐标 | 下次 solve 验收采用新配置，不在一次 solve 中更改 |

## 4. 三种 FSI 分组及可核对的编号

### 4.1 同一 14 行示例

这是 Tet4 P1 节点槽的**索引摘录**，不是只有三个节点的 Tet4 网格，也不是新的物理算例。
设 F10 为流体内部点，I20 为共享界面点，S30 为结构内部点；其它节点/固定槽省略。

| root 行 | 节点/独立量 | 其它语义/重建 | 物理验收字段 |
|---|---|---|---|
| 0,1,2 | F10: u_x,u_y,u_z | fluid velocity | velocity |
| 3 | F10: p | 无 solid pressure | pressure |
| 4,5,6 | F10: dm_x,dm_y,dm_z | 内部网格位移，非网格速度 | mesh |
| 7 | I20: p | 压力仍为独立流体量 | pressure |
| 8,9,10 | I20: vs_x,vs_y,vs_z | `uΓ=vsΓ`，`dmΓ=ds_n+dt*vsΓ` | structure |
| 11,12,13 | S30: vs_x,vs_y,vs_z | `ds=ds_n+dt*vs` 在结构 kernel 内 | structure |

模拟 owned：1 分区 `[0..13]`；2 分区 `[0..6] | [7..13]`；4 分区 `[0..6] | [7..10] | [11..13] | []`。
节点分量不跨 owner；第四分区无 owned 行用于检查逻辑边界，不声称当前离线分区器会生成此物理划分。
ghost 可引用远程 0/8/13，但不进入该分区 IS。

### 4.2 physics：fluid / solid / ALE

**设计示例，当前程序不可直接读取。** 名称/语法说明选择规则，不增加现有 YAML 配置键。

```yaml
design_only: true
storage: existing_rank_owned
acceptance: existing_physical_fields
pc:
  prefix: fsi_
  kind: multiplicative
  children:
    - name: fluid
      select: canonical.physics == fluid
      kind: schur_full_selfp
      children:
        - {name: velocity, select: canonical.quantity == velocity}
        - {name: pressure, select: canonical.quantity == pressure}
    - {name: solid, select: canonical.physics == solid}
    - {name: ale, select: canonical.physics == ale}
```

root IS：fluid `[0,1,2,3,7]`、solid `[8,9,10,11,12,13]`、ale `[4,5,6]`。
fluid 子算子编号 `[0,1,2,3,4]` 分别对应 root `[0,1,2,3,7]`；内层 velocity `[0,1,2]`、pressure `[3,4]`。
2 分区 pressure IS 为 `[3] | [4]`，不是 `[3] | [7]`。
界面速度只进 solid；fluid 子矩阵不包含完整界面动量耦合，耦合仍存在 root 非对角块中。
默认顺序 fluid→solid→ale 是示例的 PC 顺序，会影响 multiplicative PC；兼容 recipe 必须保留旧 map 的 flow→mesh→structure 顺序和旧 prefix。

### 4.3 quantity：velocity / pressure / mesh displacement

**设计示例，当前程序不可直接读取。** 当前动态结构速度可归入 velocity，不能把结构位移历史另添为未知量。

```yaml
design_only: true
storage: existing_rank_owned
acceptance: existing_physical_fields
pc:
  prefix: fsi_
  kind: multiplicative
  children:
    - name: velocity
      select: canonical.quantity == velocity
      kind: multiplicative
      children:
        - {name: fluid_interior, select: canonical.physics == fluid}
        - {name: structure, select: canonical.physics == solid}
    - {name: pressure, select: canonical.quantity == pressure}
    - {name: mesh_displacement, select: canonical.quantity == mesh_displacement}
```

root IS：velocity `[0,1,2,8,9,10,11,12,13]`、pressure `[3,7]`、mesh_displacement `[4,5,6]`。
velocity 子算子编号 0..8；fluid_interior `[0,1,2]`，structure `[3,4,5,6,7,8]`。
4 分区 structure IS 为 `[] | [3,4,5] | [6,7,8] | []`。
接口的 fluid_trace 标签不会使 8/9/10 又进入 fluid_interior；这里 interior 指接口消元后保留的流体速度，可能含未消元的外边界槽。
三块不能直接设为 PETSc Schur 类型；要得到 velocity/pressure 二块 Schur，使用下一种 dynamics 包装。

### 4.4 hybrid：dynamics / mesh → velocity / pressure → fluid / structure

**设计示例，当前程序不可直接读取。**

```yaml
design_only: true
storage: existing_rank_owned
acceptance: existing_physical_fields
pc:
  prefix: fsi_
  kind: multiplicative
  children:
    - name: dynamics
      select: canonical.quantity in [velocity, pressure]
      kind: schur_full_selfp
      children:
        - name: velocity
          select: canonical.quantity == velocity
          kind: multiplicative
          children:
            - {name: fluid_interior, select: canonical.physics == fluid}
            - {name: structure, select: canonical.physics == solid}
        - {name: pressure, select: canonical.quantity == pressure}
    - {name: mesh, select: canonical.quantity == mesh_displacement}
```

三层关系（横线只作列表分隔，不表示连续块）：

| 节点 | 此节点 owned IS 所在空间 | 4 分区 IS |
|---|---|---|
| dynamics | root | `[0,1,2,3]` / `[7,8,9,10]` / `[11,12,13]` / `[]` |
| mesh | root | `[4,5,6]` / `[]` / `[]` / `[]` |
| dynamics/velocity | dynamics 全局 0..10 | `[0,1,2]` / `[5,6,7]` / `[8,9,10]` / `[]` |
| dynamics/pressure | dynamics 全局 0..10 | `[3]` / `[4]` / `[]` / `[]` |
| dynamics/velocity/fluid_interior | velocity 全局 0..8 | `[0,1,2]` / `[]` / `[]` / `[]` |
| dynamics/velocity/structure | velocity 全局 0..8 | `[]` / `[3,4,5]` / `[6,7,8]` / `[]` |

例如 root 8 → dynamics 5 → velocity 3；root 7 → dynamics 4 是压力。
把 root 7 当作 dynamics 编号 7 不会越界，却会错误选择 root 10；必须检查 provenance，不能只检查范围。

### 4.5 刚体、空块与多标签

刚体独立示例为 F10 的 0..6 加全局 V 行 7；最后分区唯一拥有 V，其余分区可 ghost V。
多个界面节点的流体 x 速度都映到行 7，网格 x 位移为 `q_n+dt*V`；没有每节点一个刚体独立量。
physics 的 solid 叶子含 V；quantity/hybrid 的 velocity/structure 含 V；验收字段仍叫 rigid。
这是对三种分组的刚体替换规则，不把 elastic 与 rigid 当作当前同一算例同时存在的两套结构。
rigid 总惯性/弹簧项只 owner 装配一次，远程流体界面力仍累加到这一行。

所有 recipe 同层 children 必须互斥且并集为父块；父/子相互包含是正常，兄弟重复才是错误。
不允许用“fluid 或 interface 标签”分别选择两个叶子后静默去重；选择器冲突应报告具体代表和路径。
全局非空、本地空块保留同名 IS，`n=0,idx=nullptr`，所有 rank 按相同顺序调用；不因本地空块跳过 Exscan/IS/PC setup。
全局空块默认拒绝并定位配置；某 recipe 不适用（如纯固体没有 pressure）选择另一显式 recipe，不自动改 Schur 维数/删除节点。
内部节点至少两个孩子；Schur 恰好两个且顺序固定。首适配不实现 overlapping Schwarz、子 communicator 或全局空问题求解。

## 5. 父编号转换及 PETSc 接入

### 5.1 编号算法

父节点 B 在 rank r 按 IS/子矩阵顺序保存 root provenance `L_B^r`，长度 `n_B^r`。
同一 communicator 的 rank 顺序不变，定义 `o_B^r=Σ(s<r)n_B^s`，则：

```text
phi_B(L_B^r[k]) = o_B^r + k
child C's IS on rank r = [phi_B(root) for root in L_B^r if selected(C, root)]
L_C^r = retained roots in precisely that order
```

root 的 `L` 是 `[begin, begin+owned)`。每次递归都重算 **C 自己**的前缀和用于下一层；不用 root.begin 替代。
生产只保留本地 owned provenance/查找，Exscan 只规约长度（可把同层计数打包）；rank0 显式设 prefix=0。
顺序保持父列表递增，因此 IS 递增且无重复。若 caller 给未排序 raw selector，先排序检查重复，再生成子矩阵；不能生成后另行排序而不更新 provenance。
ghost 永远不送 owned IS；真实矩阵的跨 rank 列通过 PETSc 子矩阵机制处理。
校验子 Mat 的全局/local 大小和 ownership range 与 `n_C/o_C` 一致；不相等停止，禁止猜测补 offset。
根→叶的映射可递归复合，但每次 SetIS 只接受相邻层映射。

### 5.2 两个指定版本的官方源码核对

[release PCFieldSplitSetIS 入口](https://petsc.org/release/manualpages/PC/PCFieldSplitSetIS/) 在查阅时是 3.26 文档，只用作导航。
下表核对 **v3.19.6 与 v3.23.7 的官方 tag 源码**；这是接口/实现静态兼容证据，不是本次运行或 ABI 验收。

| 核对项 | v3.19.6 | v3.23.7 | 本设计采用的共同子集 |
|---|---|---|---|
| SetIS、引用计数、options prefix | [fieldsplit.c:1711–1751](https://github.com/petsc/petsc/blob/v3.19.6/src/ksp/pc/impls/fieldsplit/fieldsplit.c#L1711-L1751) | [2005–2048](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/fieldsplit/fieldsplit.c#L2005-L2048) | 名称+IS；PC 引用 IS，子 KSP prefix 由父 prefix 加 fieldsplit 名组成；已定义 split 后不追加 |
| IS 创建和零本地长度 | [general.c:417–469](https://github.com/petsc/petsc/blob/v3.19.6/src/vec/is/is/impls/general/general.c#L417-L469) | [561–613](https://github.com/petsc/petsc/blob/v3.23.7/src/vec/is/is/impls/general/general.c#L561-L613) | distributed IS，COPY_VALUES；空本地数组合法不代表所有子 PC 都已实测支持 |
| AIJ 子矩阵、同 communicator、重复项/reuse 条件 | [matrix.c:7604–7666](https://github.com/petsc/petsc/blob/v3.19.6/src/mat/interface/matrix.c#L7604-L7666) | [7638–7703](https://github.com/petsc/petsc/blob/v3.23.7/src/mat/interface/matrix.c#L7638-L7703) | parallel row/column IS，禁止重复；同图/同选择才复用；首方案对角子块同一 IS 作行列 |
| 排序与子矩阵创建 | [fieldsplit.c:595–633](https://github.com/petsc/petsc/blob/v3.19.6/src/ksp/pc/impls/fieldsplit/fieldsplit.c#L595-L633) | [595–662](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/fieldsplit/fieldsplit.c#L595-L662) | 递增 IS；使用明确子编号，不依赖 MATNEST 默认场或 block-size 自动推断 |
| 子矩阵重编号实现 | [mpiaij.c:2977–2988](https://github.com/petsc/petsc/blob/v3.19.6/src/mat/impls/aij/mpi/mpiaij.c#L2977-L2988) | [2984–2995](https://github.com/petsc/petsc/blob/v3.23.7/src/mat/impls/aij/mpi/mpiaij.c#L2984-L2995) | 相同 owned 分布子集的 column map 使用 rank 计数前缀加本地 IS 位置；与本文 phi 一致 |
| GetSubKSP 生命周期 | [fieldsplit.c:2024–2065](https://github.com/petsc/petsc/blob/v3.19.6/src/ksp/pc/impls/fieldsplit/fieldsplit.c#L2024-L2065) | [2331–2372](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/fieldsplit/fieldsplit.c#L2331-L2372) `PCFieldSplitGetSubKSP` | PCSetUp 后获得借用 KSP；调用者 PetscFree 返回数组，不销毁子 KSP |

项目锁定环境说明在 [environments/README](../../environments/README.md)：两包 real/double/32 位 PetscInt；本设计不依赖 3.23 特有设备接口，也不以 64 位 semantic ID 推断 PetscInt 是 64 位。
本次直接下载官方源码到临时目录的尝试超时，改用浏览工具读取上述官方 tag 页面；没有安装依赖或保存未经读取的源码哈希。

### 5.3 创建顺序、prefix 与失败

1. 在共同准备阶段验证 schema/名称/顺序一致（长度和序列检查，不能只各 rank 自测），解析选择器并建立完整索引计划。
2. 在已有 root J/P 装配完成后配置新 PC；行列布局必须一致。设置明确的 split kind，Schur 不接受三个 children。
3. 为每个子节点 `ISCreateGeneral(parent_comm,n,ids,PETSC_COPY_VALUES)`，然后 `PCFieldSplitSetIS`；销毁 caller 的 IS 引用，PC 保留自己的引用。首次可将叶模式附到该 IS 的匹配生命周期，或在子矩阵创建后显式附上。
4. `PCSetUp` 建立父的子系统，`PCFieldSplitGetSubKSP` 获得孩子，核对 count、A/P 类型/大小/ownership 和 prefix，再递归配置孩子 PC。释放返回的指针数组，孩子属于父 PC。
5. Schur 的 velocity 是 A00 KSP 可继续嵌套；pressure KSP 的 A 是 Schur 算子，不把它当成可直接提取 AIJ 的普通父矩阵。本设计不在 pressure 节点继续划分。新 recipe 首接入只支持默认共享 A00 求解器；另设 Schur inner/upper 的选项须被检测并明确拒绝，后续另行接线和验收。普通 GetSubKSP 不代表枚举了所有 Schur 内部 KSP，不能漏配另设的 A00 作用。兼容 recipe 保留现有选项行为。
6. 每次 solve 的新 PC 复用已验证的数字数组；Newton 中只更新算子/PC 数值。不对已 setup PC 反复 SetIS“更新”树；换 recipe 销毁/重建 PC。

新显式 recipe 示例 prefix 是 `fsi_`（传 API 时无前导 `-`）；最深选项如
`-fsi_fieldsplit_dynamics_fieldsplit_velocity_fieldsplit_structure_pc_type`。
名称限 `[a-z][a-z0-9_]*`、兄弟名称唯一、路径确定；两旧版都有长度 128 的内部 prefix 缓冲，首适配对完整拼接字节长度 `<128` 作保守检查，不允许截断碰撞。
兼容 recipe 使用当前空 root prefix 和原 `flow/mesh/structure|rigid` 名，保持现有命令行选项。
options 可覆盖求解方法/容差，但不得偷偷覆盖语义 IS、children 数和顺序；不相容 PC type 报配置错误。
所有 rank，包括零 owned rank，执行相同 setup 阶段。先汇总本地验证错误，PETSc/MPI 不可恢复错误沿已有作业级错误路径；不加新的缩步/静默 fallback。

### 5.4 Schur 与近零空间的数学影响

令 V 是合并后的流体内部/结构速度，D 是 dynamics=(V,p)，M 是内部 ALE 位移。
精确压力 Schur 为 `S_p=J_pp-J_pV J_VV^{-1} J_Vp`，不是把 `J_pp` 认作零；当前稳定化等阶流体允许非零 `J_pp`。
physics 模式的 fluid 内 Schur 只含 `u_I,p`，结构通过外层非对角作用参与；quantity 的 velocity 大块包含流固动量耦合，但示例 velocity 内 multiplicative 仍是近似作用。
hybrid 在 dynamics 内做压力 Schur，同时 outer dynamics/mesh multiplicative 近似处理几何反馈。
若精确消掉 mesh，则 dynamics 有 `J_DD-J_DM J_MM^{-1}J_MD` 修正；示例没有承诺实现这一精确消元。
这些分组改变 PC 近似，不能改变完整 root J/R 或共同 Newton；忽略速度间耦合可能影响附加质量敏感问题，不承诺收敛率或性能收益。

目前项目 schur_solver 只配置 GAMG，src/include 未发现显式 `MatSetNearNullSpace/MatSetNullSpace/PCSetCoordinates` 接线。
未来结构速度块的低能模式要结合 `M/dt+dt*K`、固定边界和参考/当前坐标确定；不能直接把六个刚体模式称作动态结构精确零空间。
ALE 向量 Laplace 的分量常量候选与边界相容后才能作为近零空间；压力常数是否为精确零空间取决于压力规范/边界/稳定化。
合并 velocity 块模式必须给流体槽和共享界面一致分量，只数代表一次。模式向量与子块布局同序，限制/置换后重新正交化，零向量丢弃；不假定任意 root 零空间限制到子块仍是零空间。
PC 改组/消元/存储重排要求重建子块模式。为不改变首切片行为，显式模式接线独立验收，默认保持现状。

## 6. 独立代数参考验证

[reference_model.py](../research/fem_g0a/reference_model.py) 与 [test_reference_model.py](../research/fem_g0a/test_reference_model.py)
只使用 Python 标准库、Fraction 和 unittest，不导入生产脚本，不调用进程/求解器，不求线性系统的解。
全局小字典仅为清楚展示分区索引规则，不能复制成生产分布式实现。

### 6.1 固定映射的定义与手算 oracle

完整局部物理槽 x、独立变量 q，固定于一次 Newton 的 K/W/g：

```text
x = K q + g
R_reduced(q) = W^T R(Kq+g)
J_reduced = W^T J K
```

若有 body/global 项另加 `R_global(q)` 及其导数；不能把它分配到每个共享界面副本。
W 是独立测试坐标到完整测试槽的映射；普通 Galerkin 约束可以 W=K，本 FSI 的人工网格行舍弃和 dt 系数提供具体反例。
结构 kernel 内部的 BE 链式导数已经包含在 J；K 只补该 kernel 输入之外的界面 mesh 重建，防止双乘 dt。

取无量纲合成 5×5 非对称矩阵（不是 FSI 离散矩阵、不是性能样本）：

```text
x slots = [u_I, u_Gamma, v_s, dm_Gamma, fixed]
q = [u_I, v_s], dt=2, dm_accepted=3, fixed=5
J = [ 2  1 -1  3  4 ]    b = [1,2,3,4,5]^T
    [ 5  6  2  0  1 ]
    [-2  4  7  1 -3 ]    R(x)=J*x-b
    [ 9  8  6  5  2 ]
    [ 1  0  3  2  4 ]

K = [1 0]   W = [1 0]   g = [0,0,0,3,5]^T
    [0 1]       [0 1]
    [0 1]       [0 1]
    [0 2]       [0 0]
    [0 0]       [0 0]
```

手算第一缩减行：`[2, 1-1+3*2]=[2,6]`；第二行由完整第 2/3 行相加，得 `[5-2,6+2+4+7+1*2]=[3,21]`。
`Wᵀ(Jg-b)=[28,-12]`，所以 `J_reduced=[[2,6],[3,21]]`，`R_reduced=[2q0+6q1+28,3q0+21q1-12]`。
q=[1,2] 时 x=[1,2,2,7,5]，完整 R=[42,24,9,78,36]，缩减 R=[42,33]。
人工 ALE 行 78 被舍弃，固定槽原始残量 36 保留为可解释反力量，但不进入自由方程验收。
错用 W=K 会得 R=[42,189]、J=[[2,6],[21,69]]，测试明确验证这个反例。
缩步 dt=1/2 时支撑不变，J=[[2,3/2],[3,39/2]]、同一 q 下 R=[33,30]；不可以复用旧数值系数。

状态相关映射是边界：若 `x(q)=K(q)q+g(q)`、`W=W(q)`，则方向导数为
`dR_reduced[δq]=(dW[δq])ᵀR + WᵀJ (Kδq+dK[δq]q+dg[δq])`，加全局项导数。
本模型不验证姿态/接触/非匹配搜索产生的这些项，不将固定映射公式外推为通用状态相关正确性。

### 6.2 置换是坐标变换

独立变量 `q=P y`，P 是置换矩阵、列 j 在 old row new_to_old[j] 为 1：

```text
R_new(y) = P^T R_reduced(P y)
J_new    = P^T J_reduced P
K_new=K P, W_new=W P, g_new=g
```

交换两列/行时 y=[2,1]，R_new=[33,42]，J_new=[[21,3],[6,2]]。
测试同时从变换 K/W 和从 PᵀJ_reduced P 两条路径核对，并断言上述独立写定的常数，不全由被测函数产生预期值。
这不验证 SNES 线搜索、舍入行为、KSP 性能或 FSI 稳定性。

### 6.3 验收项目与证据

执行命令：`python3 -B docs/research/fem_g0a/test_reference_model.py`。
实际 **20/20 项 unittest 通过**（含每项内的多分区/多分组子例）。输出在 [reference-tests.txt](../research/data/fem-g0a-2026-10-30/reference-tests.txt)；覆盖：

| 范围 | 正例 | 负例/独立检查 |
|---|---|---|
| 身份/编号 | independent key↔root、逆序/非平凡置换，domain/mesh 区分 | 重复身份、重复编号、缺号、越界 |
| 三树 | 14 行覆盖、兄弟互斥、界面代表唯一 | 重叠、遗漏、非法引用、全局空、重名/非法名、prefix 超长 |
| 嵌套 | 两层 physics 和三层 hybrid 手写 IS；跨 rank offset | root 编号误用于 parent，即使仍在合法范围也拒绝 |
| 约束 | 齐次/非零固定值、alias、传递 lifting、独立 K/W | 循环、未知 master、固定和独立重定义、维度错误、W=K 反例 |
| 刚体 | 最后分区唯一 global V、多个界面 alias | owned 重复/遗漏与 ghost 重复/越界拒绝 |
| 分区 | 1/2/4 模拟分区 owned/ghost，空本地物理块、零 owned 分区 | ghost 不可作为自己的 owned，不参与 IS 计数 |
| 代数/验收 | Fraction 精确残量、切线方向差分、非对称置换、物理字段平方均值 | PC 改组不改尺度/计数；不调用任何求解器 |

**证据等级：分区索引逻辑验证和合成代数一致性。** 不是 MPI 测试，不是 PETSc 嵌套 FieldSplit 执行，不是物理解/反力数值回归，不是收敛稳定性或性能证明。
Python 模型不模拟普通保留行边界替换、通信异常、IS 引用计数、HDF5 发布、COO 库内图，也未证明生产 C++ 和模型自动等价。

## 7. 成本、缓存与真正的存储重排

### 7.1 元数据预算（估算，不是实测）

令 n_o/n_g 为 owned/unique ghost 有效代数行数（本例等于独立 DoF 数），n_s 为完整语义槽数，d 为树最大深度（本例 3），b 为块数，w=sizeof(PetscInt)（项目锁为 4），a 为单 master affine slot 数。
数字为显式数组负载，不含 allocator、C++ padding、Python 对象、哈希桶、PETSc 内部 Mat/PC 存储。

| 数据 | 每项估算/总量 | 策略 |
|---|---|---|
| compact DofKey | 40 B：mesh/entity 2×u64，domain/space/quantity/mode 4×u32，kind/component 2×u16，加 4B 保留/对齐预算 | 字符串/空间定义在共享表中 intern；空间 ID 表本身需持久规范，不把运行序号当跨作业键 |
| canonical role + tags + row_kind | 16 B/有效本地代数行（role/acceptance/tag 引用） | 多标签用共享字典，禁止每 DoF 一组 std::string |
| root + local representative + owner | `(2w+4)` B/有效本地代数行 | 首适配尽量借用既有 local_to_global 和 owner，避免双份权威映射 |
| 概念合计 | `(60+2w)(n_o+n_g)` B，w=4 时 68 B/DoF | 是全量直观表示上界预算；首切片可只保留 16B role 并从 mesh 按需构键 |
| affine 单 master 数值/下标 | 约 `(2w+24+4)a` B（root/local、trial/test/lift、kind），另需必要语义索引 | 借用既有 reduced.global/local 时不要再算作新增数组；K/W 不形成大稠密矩阵 |
| PC 计划 | 每层 owned parent IS + root provenance，至多 `2wd*n_o` B | 流式遍历/临时反查可降低；ghost 没有额外 IS；只缓存选中 recipe |
| PETSc COPY_VALUES IS | 至多 `wd*n_o` B 另加对象元数据 | 3 层、w=4 时计划+IS 上界 36 B/owned 行；不包括子矩阵与 PC |
| 双向存储置换（未来） | 至少 `2w(n_o+n_g)` B 加跨 owner 迁移缓冲 | 第一接入不分配 |

例如 10^6 owned、2×10^5 ghost、w=4、d=3，概念语义/映射约 81.6 MB，PC 索引上界约 36 MB（十进制），另加原约束槽/图/矩阵/PC；这是容量计算，不是 RSS 测量或目标内存承诺。
对当前 nc=10 FSI，完整槽 n_s 可远大于有效独立数，不能按独立数低估 reduced 两数组与别名数据。

准备期：语义生成 O(n_s)，单 master 无环扁平化 O(n_s)；不排序的选择扫描 O(d*n_o)，排序最坏 O(Σ_B n_B log n_B)，owned 反查可用临时整数数组或排序二分 O(log n_B)。
拓扑标签解析一次，schema/名称跨 rank 校验 O(b) 数据；计数前缀和按层打包、最多 d 轮。需跨 owner 的别名以后单独计通信，不引入 global field gather。
子矩阵/Schur/GAMG 的内存与 setup 不包含在上述 O(d*n_o) 内，依 nnz、填充和算法，必须另测。
索引缓存键至少 `(topology/space, partition, constraint_support, storage_order, semantics_role, recipe)`；数值 epoch 为 geometry/history/dt/material，与索引分开。
默认 Newton 内不解析字符串、不排序、不重建 block IS；沿现有生命周期每 solve 新 PC 仍有 PETSc 对象 setup 成本，不能将索引缓存说成消除了它。

固定 Tet4 拓扑、局部分量、局部张量维数可用模板/constexpr。全局网格大小、rank 数、分组、标签、空间实例和材料/步长属于运行期数据；不以模板参数编码整道 FSI 问题。

### 7.2 真正重排单列为后续切片

第一阶段只有 IS 选行，root 向量/矩阵编号不变。真正置换需要：

1. 明确 `new_to_old` 和逆映射，先做 rank 内排列（owner 不变）。若全局 field-major 使 owner 区间不连续，则必须重分布，不能称作仅局部重排。
2. 同时迁移 accepted/trial/必要历史的独立系数，重建 local_to_global、ghost scatter、cell gather、K/W 的列/缩减行、约束行、原始反力和输出 scatter；完整物理历史数组保持其独立节点语义。
3. root 图行列、diag/offdiag 计数、COO 的 contribution 顺序/slot 和矩阵全部按新编号重建，原 cached COO 对象不允许就地改 pattern；PC/IS/模式向量同时变换。
4. checkpoint 首选明确排列 schema+语义/顺序标识，或保存规范化独立键顺序并在恢复时重排。当前 v3 没有 reduced 排列版本；在生产实现前选择一种并拒绝不兼容文件，不能静默读入等尺寸错序数据。
5. 验收按身份迁移行列表和尺度，保持物理 RMS/N/约束容差；输出仍按实体/物理字段重建，不显示内部 PC 分块。

跨 rank 数重启、重网格历史 transfer 不因上述置换设计自动支持；本次仅给依赖和失效责任。

## 8. 后续 C++ 可独立验收切片（本次均未执行）

| 切片 | 修改位置/依赖 | 未来最小验收 | 回退 |
|---|---|---|---|
| G0-B1：旧存储上的语义→IS 适配，最高优先 | `field_layout/reduced_layout` 头与 cpp 生成 role；`linear_system.hpp` 保留 fields 契约；`schur_solver.hpp/cpp` 和 `nonlinear_system.cpp` 接可选 PC plan；仅在确需共享时新增小头 | 先重现旧 flow/mesh/structure 或 rigid 树，默认 LU/旧 options/编号不变；用现有 Tet4 流体与双域 FSI 对比解、反力、验收记录；真实 1/2 rank 与两个指定 PETSc 版本 targeted 检查 | plan 未启用走原路径；新路径不改 checkpoint/图，容易撤回 |
| G0-B2：三 recipe 与父编号通用化 | 依赖 B1；`src/algebra/schur_solver.cpp`、`include/eonsim/config.hpp` / `src/core/config.cpp`、只读块摘要；避免同时开放任意 DSL | 真实 1/2/4 rank 三树，根/父子矩阵抽取值/size/ownership、空本地块和非法配置共同失败；prefix/options 覆盖；同一物理验收 | 显式 recipe 开关；保留 compatibility recipe，失败不静默换树 |
| G0-B3：映射与原始反力显式化 | 依赖 B1；`reduced_layout`、`fsi.cpp` 和相关映射头；保持现有 kernel | 完整 Jv、BE 缩步重试/失败后恢复、齐次接口与非零 lifting 的新专用小例；确认 solid dt 不双乘、ALE 界面行不入结构力 | 原映射仍作对照；切换前后以同状态回放，不混合两套历史 |
| G0-B4：近零空间和 PC 数值策略 | 依赖 B2；`schur_solver.cpp` 与物理提供的模式数据 | 压力规范、边界限制、模式布局/正交化，直接解对照和失败恢复；之后才允许测 setup/迭代/总成本 | 不注入新模式的原 GAMG 路径，禁止称未测模式为默认改进 |
| G0-B5：rank 内真实重排及 restart/output 迁移 | 依赖 B1–B3；`field/reduced_layout`、algebra、`checkpoint.cpp`、`fsi.cpp`/输出适配、流体 COO 图消费方 | PᵀJP/物理解/反力、ghost、同分区 checkpoint 双向迁移或明确拒绝旧 schema、原装配/COO 图值、输出 ID 对照 | 默认 identity permutation；版本化 checkpoint，绝不覆盖旧格式而不标记 |
| 来源身份持久化（另行触发） | `fsi_domains.cpp`、`mesh.hpp`、分区 I/O；不依赖建立新 FEM 框架 | 原始双域 ID→joined 往返、重导入/分区映射边界 | 首切片运行内语义 token，不宣传跨作业稳定身份 |

未来验证清单：真实 MPI 1/2/4 rank 所有权/ghost/空 local block；PETSc 3.19.6/3.23.7 嵌套子矩阵和 Schur；同一状态下 R/J/fields/停止准则不变；压力规范、界面速度/位移、总力和反力；SNES 正 reason 后最终验收拒绝；局部错误同步、失败不提交和同对象恢复；缩步后 K/g/历史一致；checkpoint generation 和同分区恢复；固定 COO 重复/远程/清零/图失效；输出实体身份和值。
真实数值验收前应按用户另行授权安排 INFRA-01 最终集成检查；其待验收不阻止当前纯设计，但本任务结果不能替代它。

## 9. 交叉审查与剩余事项

同一作者做源码事实、接口、手算 oracle 和索引反例之间的交叉审查，未冒称独立多人评审。
重点结论：结构变量是 velocity；界面 mesh alias 带 dt；结构 kernel 已含 dt；joined ID 非原始双域 ID；partition fingerprint 含 rank；acceptance 与 PC 必须解耦；嵌套 IS 是父全局编号；checkpoint v3 不检查独立排列版本。
实际检查及修正记录见 [检查记录](../research/data/fem-g0a-2026-10-30/checks.txt) 和 [会话日志](../development/CODEX_SESSION_LOG.md)。
知识草稿位于 [DoF 与嵌套分块](../../website/drafts/dof-semantics-and-nested-fsi-blocks.md)，保持 draft，待人工核对设计和证据边界。

没有新增有限元求解能力。本次合并审查覆盖设计与参考验证；剩余为 B1 开始的 C++/真实 PETSc/MPI 接入和数值验证。非匹配、高阶、BDF2、重网格、全局重分布和其它 deferred 阶段未启动。
下一次最小任务是 **G0-B1：在不改变 root 编号、默认 PC 和验收字段的条件下，为现有 Tet4 布局增加 canonical role 到现有 IS 的适配**。
