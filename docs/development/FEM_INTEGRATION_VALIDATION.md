# FEM G0B → G0 → G5 → G1：实施与验证记录

状态：in_progress。基线 main `72a335604a50c1ae27516b8bde15e05564b5748b`。
工程量估计与依赖在现有 [队列](CODEX_TASK_QUEUE.md) 维护；本文仅记录实现和验证事实。

## 当前基线

PETSc 3.23.7 real/double/int32 + OpenMPI 5.0.8 + GCC 15.3.0，Linux x86_64，cgroup 4 CPU/32 GiB，4编译任务、CTest串行、每rank BLAS/OpenMP单线程。
锁定恢复入口和来源继续使用 `environments/` 与 `scripts/cloud/`，没有增加安装框架。

```bash
bash scripts/cloud/restore.sh 3.23.7 /workspace/eonsim-cloud
bash scripts/cloud/run.sh 3.23.7 debug all /workspace/eonsim-cloud
bash scripts/cloud/run.sh 3.23.7 release all /workspace/eonsim-cloud
bash scripts/cloud/restore.sh 3.19.6 /workspace/eonsim-cloud
bash scripts/cloud/run.sh 3.19.6 debug mpi-failure /workspace/eonsim-cloud
```

路径是本次示例，可替换为任意可写持久目录。快照旧构建缓存引用消失的 `/tmp/infra-pristine` Ninja；将旧目录移至证据目录后从空构建目录恢复成功。主环境初次依赖恢复使用新前缀及包缓存；再次恢复成功，不能将缓存命中代替运行验证。

| 代码 | 环境/模式 | 选择 | 实际结果 |
|---|---|---|---|
| 72a3356 | 3.23.7 Debug | 完整短套件 | 35/35，135.68秒CTest墙钟 |
| 72a3356 | 3.23.7 Release | 完整短套件 | 35/35，55.06秒CTest墙钟 |
| 72a3356 | 3.19.6 Debug | mpi-failure | 7/7 |

[机器可读清单](../research/data/fem-integration-2026-10-31/baseline.json) 保留实际dirty标记、依赖锁摘要、测试名/状态及日志摘要。原始日志位于 `/workspace/engineering-evidence/baseline-*-evidence/`。这些只是基线，不能用于声称新能力已验收。

## G0B 当前实现

- `DofKey` 在一个layout的网格命名空间中使用网格实体ID、域、量、分量、空间/局部模式；不使用rank/代数编号作为身份。joined网格仍使用重编号后的实体ID，不承诺跨导入或跨分区重启身份。
- `AlgebraLayout::owned_semantics` 与 `fields` 分开；后者继续独立控制物理验收。保留原 owned/ghost 映射、编号、图、默认LU及原block/schur选项。
- `ReducedLayout::slot` 明确试探列、局部代表、仿射lifting及测试行。界面mesh列乘时间重建系数、测试行舍弃；结构kernel内部链式导数不重复相乘。
- `solver.pc_recipe` 或 `-pc_recipe` 选择 physics/quantity/hybrid；不能同时指定旧block/schur选项。当前只支持独立流体及现有FSI；没有增加生产存储重排。
- `PcBlock` 保存owned root provenance和直接父编号；每层用本地计数前缀生成子矩阵空间，不把根编号传给嵌套IS。空本地块参与collective，全局空块共同拒绝。
- 三树见G0A。独立流体退化为共同u/p Schur；FSI physics为fluid(u/p Schur)/solid/mesh，quantity为velocity(fluid_interior/structure)/pressure/mesh，hybrid为dynamics(velocity(fluid_interior/structure)/pressure Schur)/mesh。
- 叶子默认GAMG；唯一标量刚体使用Jacobi。quantity的原始压力块使用Jacobi：实际测试发现原始Jpp的AMG粗层可能奇异；完整系统仍可逆。不改变方程或容差，不宣称某种分组更快。
- options prefix按树命名。固定分裂类型不能被options改写；独立Schur inner/upper尚未接线，按真实第二孩子prefix的所有选项共同拒绝。`-pc_plan_report` 输出块大小、owned区间和实际prefix。
- 索引计划在每次solve的准备阶段生成；Newton内不重建。没有承诺跨时间步缓存或预条件因子复用。

## G0 验收进展与边界

已执行的首轮 targeted 检查：1/2/4 rank 子矩阵手写oracle和错误配置；三recipe独立流体、双域弹性、刚体、超弹性与直接解对照；初态收敛、callback分类/accepted不变/同对象恢复；fluid COO与FSI重启对照。后续slot映射改造后的完整回归正在执行，最终状态以后续实际结果为准。

独立审查发现并修正：rank局部布局错误的共同传播、子KSP数组异常释放、命名Schur inner/upper选项漏检、options改变固定分裂类型。上述审查不替代运行验证。

最终Debug/Release、兼容新路径和故障/缩步已在后文更新；尚未关闭整体CI/PR与主线交付。G5、G1尚未实施。没有大规模性能或新物理能力结论。

## G0 主环境最终数值验收

当前G0源码清单与实际结果见 [g0.json](../research/data/fem-integration-2026-10-31/g0.json)。测试执行时HEAD仍为72a3356、工作区dirty；逐文件SHA256用于区分新增代码，不把这些结果归给未修改基线。

- 主环境Debug `all`：43/43，无跳过，254.53秒CTest墙钟。
- 主环境Release `all`：43/43，无跳过，102.11秒CTest墙钟。
- 3.19.6 Debug `mpi-failure`：10/10；新三recipe/重启/子矩阵7项 targeted 均通过；最新所有权负例与真实缩步4项补验也全部通过。
- 独立审查的阻塞项均修复；另将负例的异常分类失败改成清理后共同报告，避免测试自身残留错误handler或单rank提前抛出。
- 实际覆盖：非对称WᵀJK与非零lifting手算oracle、PETSc置换矩阵值/残量/解、三层真实子矩阵、空owned rank、1/2/4rank、非法配置、回调/PC/线性失败区别和同对象恢复；四类流体/FSI算例对直接解；27组COO/重启；hybrid真实缩步对直接小步长。
- 默认旧路径、Poisson、固体、COO、checkpoint、局部/整体导数等现有短套件均保留。没有生产存储重排、跨rank数重启或大规模扩展性声明。

这些墙钟是CTest执行记录，不是工程实际耗时，也不是同配置性能比较。正式PR与主线交付仍等待G5/G1和整体CI/审查。
