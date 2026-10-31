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
