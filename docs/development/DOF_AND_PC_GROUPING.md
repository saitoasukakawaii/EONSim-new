# DoF 语义与预条件分组

独立流体及现有单体刚体/弹性 FSI 可选择三种预条件器树：

```yaml
layout:
  semantic_order: entity_first
  storage_order: owner_node
solver:
  pc_recipe: hybrid # physics / quantity / hybrid
```

命令行等价选项为 `-pc_recipe hybrid`。省略时保持既有默认求解器行为；
不能与旧 `-block_pc`、`-schur_pc` 同时选择。二维标量和独立固体目前不开放这三种多物理树。

| 分组 | FSI 树 |
|---|---|
| physics | fluid（velocity/pressure Schur）、solid、mesh |
| quantity | velocity（fluid_interior/structure）、pressure、mesh |
| hybrid | dynamics（velocity（fluid_interior/structure）/pressure Schur）、mesh |

独立流体三种选择退化为共同的速度/压力 Schur。树仅改变预条件过程，不改变物理残量字段、
约束、压力规范、accepted/trial 状态或停止准则；不同 recipe 可以有不同迭代轨迹。
共享接口独立速度只属于一个非重叠叶子，流体与结构方程仍可共同依赖它。
刚体是全局单轴未知量，并非给定轨迹冒充双向耦合。

`DofKey` 表达物理域、空间、物理量、分量、实体与局部模式；它不是 PETSc 行号。
约束后的独立代表和重建关系由 `ReducedLayout::slot` 给出，试探列 K 与残量投影 W 分开。
owned/ghost 由网格所有权决定，存储索引与语义身份分离；嵌套子块同时保存根索引和父矩阵编号。
构造时集体检查子块互斥/覆盖、所有权及结构一致性；允许本地空块，全局空块明确拒绝。

三项配置彼此独立：`layout.semantic_order` 当前仅支持 `entity_first`，
声明DofKey的固定规范比较顺序 `(entity,domain,quantity,kind,component,mode,space)`；
它不是向量排列操作。`layout.storage_order` 当前仅支持 `owner_node`，声明现有
owner连续、rank内节点分量布局（约束消元及全局刚体未知量按现有ReducedLayout规则）。
两项默认值与旧行为一致；其它顺序明确报错，尚未提供可切换的生产排列策略。
启动摘要`layout_policy`报告所选策略；独立测试验证显式策略与三recipe不改变输出存储ID和物理解。

当前接入采用 AIJ+IS；默认节点存储不变。切换 recipe 不进行全局或 rank 内内存重排。
装配置换诊断用于检查残量/Jacobian/解等价，不能被解释为生产存储布局配置。
物理验收字段也不随 recipe 改名或拆分。

```sh
mpiexec -n 4 build/cloud-3.23.7-release/eonsim -case cases/fsi/elastic.yaml \
  -partition results/part4 -pc_recipe hybrid -pc_plan_report -solver_report
```

先用同一算例的 `-prepare results/part4 -parts 4` 生成分区。
`-pc_plan_report` 按 rank 输出实际块名、全局大小、owned 区间和 PETSc options prefix；
子 KSP/PC 选项使用报告中的真实 prefix，不把根行号当嵌套子矩阵行号。
固定分裂方式不能被 options 静默改写；尚未接线的独立 Schur inner/upper 选项明确拒绝。
叶子默认 GAMG，单自由度刚体和 quantity 原始压力块默认 Jacobi，细节见实现/诊断。

验收包括真实装配 J/R 置换、直接解对照、三层子矩阵、1/2/4rank、空本地块、
共享接口、约束重建、失败与同对象恢复、COO 和 checkpoint。
[受控小算例性能记录](../research/data/fem-integration-2026-10-31/pc-recipes-benchmark.json)
包含 setup/迭代/solve/内存；这些小问题的直接解更快，不宣称新分组必然改善性能。
完整来源、参数及限制见 [集成验证](FEM_INTEGRATION_VALIDATION.md) 和
[G0A 数学契约](../architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md)。

## 独立流体的可选速度块元数据

旧 `-schur_pc` 路径另有显式选项 `-schur_velocity_block3`，目前只支持独立
三维 Tet4/P1 流体。它在分裂前集体核验 owned 语义中的同节点 0/1/2 速度三分量，
再核验提取子矩阵的全局大小与 owned 区间，将速度子矩阵的块大小设置为3。
本地空块允许；缺语义、分量不完整、多物理字段或各 rank 选项不一致均明确拒绝。
必须与 `-schur_pc` 一同使用，不能用于 `-pc_recipe` 或旧 FSI 分裂。

原 AIJ 矩阵、物理编号、压力子块、残量和停止准则不变；不是切换到 BAIJ 或重排未知量。
固定 PETSc3.23.7 的 GAMG 在未提供显式近零空间时依据块大小产生每分量常数候选，
这些是插值候选，不能解释为当前边界问题的精确零空间。实现依据
[该版本 GAMG 聚合源码](https://raw.githubusercontent.com/petsc/petsc/v3.23.7/src/ksp/pc/impls/gamg/agg.c)。

`study_womersley.py --schur --velocity-block3` 将选项写入不可变研究定义；
向既有研究的 `--resume` 增加它会被拒绝。策略或二进制变化须显式派生研究，保留完整
接受态及来源哈希，不覆盖旧尝试。该设置默认关闭。

054b64a后的可选实现完成 Debug 六项、Release 五项加同源码失败补验一项；
包含实际1/2/4rank小管与直接解比较、空 owner、集体拒绝和同 KSP 恢复。
四rank共享一个WSL核分组的细网格三步末态场差5.09e-12通过2e-9，局部耗时733.27→539.74秒；
这是有界筛查，不是通用扩展性或长期精度资格。原 Release Schur 测试在默认 MPI 空等下
超时，启用空等让出后通过原时限，失败证据保留。旧依赖版本与全量测试本次未运行。
完整命令、源码和[967份核验证据](../research/data/womersley-vector-metadata-2026-11-08/README.md)可复查。

## 独立瞬态流体的可选 LU 预条件器复用

`-pc_factor_mat_solver_type mumps -fluid_lu_pc_reuse_window 8` 显式允许一个
MUMPS LU 因子预条件最多8次有线性工作的成功求解。默认窗口0保持原行为；上限1000000，
各rank必须相同。应用入口仅开放独立固定网格瞬态流体。FGMRES求解当前方程，要求未预条件
残差范数和非原位MUMPS分解；不能用旧LU作PREONLY直接解。最终重新装配的字段验收不变。
该选项不跨物理步复用Jacobian；单步内既有chord策略须另行显式设置。

不能与`-schur_pc`、`-block_pc`、`-pc_recipe`、其它PC类型或单独的
`-snes_lag_preconditioner`、`-snes_lag_preconditioner_persists`、
`-ksp_reuse_preconditioner`混用。`NonlinearSystem`只保留PC及独立LU因子；SNES/KSP、
回调和物理历史仍按原生命周期管理。任意失败、关闭/改变窗口或任一rank的options数据库
变化都会使缓存失效。无需线性工作的精确初值不消耗窗口。Checkpoint不存因子，重启后重建。

`study_womersley.py --mumps --lu-reuse-window 8` 将策略写入不可变研究定义；
更改既有研究的恢复策略会被拒绝。长研究采用前仍需同态字段和受限资源成本对照。
当前[锁定3.23.7检查](../research/data/lu-preconditioner-reuse-2026-11-08/README.md)
覆盖真实1/2/4rank、空owner、AIJ/COO、改变算子、窗口/选项变化、回调失败恢复、变步长
BDF2和完整重启历史。独立实际LU次数验证避免仅凭对象仍存活或输出一致就认定有复用。
这批证据不包含细网格性能、长期物理资格、旧PETSc或全套测试。

后续系数刷新修正 `a6643c8` 在任一 rank 请求时共同重建因子，包含没有 owned 行的 rank。
流体驱动比较相邻 accepted 求解的有效积分时间；BE→BDF2 启动、实际步长或事件导致该
系数变化时立即刷新，窗口长度不覆盖此条件。缓存及上次系数不写 checkpoint。对应
[Debug/Release 各6项及完整历史验证](../research/data/lu-time-coefficient-refresh-2026-11-08/README.md)
与原选项检查分开记录；[后续源码复核](../research/data/solver-clock-source-review-2026-11-09/README.md)
确认相关源码与实际验证快照逐字一致，没有重新运行未受影响的数值检查。
