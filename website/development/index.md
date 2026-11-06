# EONSim 项目研发

本栏目记录公开的研发方向、架构决策和已经合入主线的技术工作。当前状态以 GitHub `main` 为准。

## 当前主线

- 仓库：[saitoasukakawaii/EONSim-new](https://github.com/saitoasukakawaii/EONSim-new)
- 检查点：[`4f3a995de45d`](https://github.com/saitoasukakawaii/EONSim-new/commit/4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e)，2026-11-03
- 当前开发交付：单体 FSI 周期流量与移动域质量验证；P2 标量有限元稳态和瞬态闭环。

## 最近合入的研发里程碑

| 任务 | 合入状态 | 主要交付 |
|---|---|---|
| FSI-LOAD-01 · [PR #31](https://github.com/saitoasukakawaii/EONSim-new/pull/31) | 已合入 `06b05c4` | 平滑周期压力载荷、阶段时间评价、接受步 CSV/PVD 历史与恢复检查 |
| FSI-NEXT-01 · [PR #32](https://github.com/saitoasukakawaii/EONSim-new/pull/32) | 已合入 `b2755b6` | 固定仿射速度入口、阶段和终点几何有效性、分布式界面面积观测 |
| FSI-NEXT-02 · [PR #33](https://github.com/saitoasukakawaii/EONSim-new/pull/33) | 已合入 `4f3a995` | 周期体积流量入口、无滑移弹性壁通道、独立表面/体积质量诊断 |
| FEM-G2A · [PR #27](https://github.com/saitoasukakawaii/EONSim-new/pull/27) | 已合入 `c0745ea` | 直边 Tri3 几何上的共享边 P2 标量空间、稳态 Poisson D/N 求解与分区输出 |
| FEM-G2B · [PR #28](https://github.com/saitoasukakawaii/EONSim-new/pull/28) | 已合入 `1bc87a7` | P2 Robin 边界、纯 Neumann 相容性、常数零空间与体积均值处理 |
| FEM-G2C · [PR #29](https://github.com/saitoasukakawaii/EONSim-new/pull/29) | 已合入 `dff9116` | P2 瞬态扩散、一致质量矩阵、BE/BDF2/alpha、同分区历史恢复与接受步输出 |

## 验证证据

- FSI-LOAD-01：PETSc 3.23.7 云端 Debug/Release 各 24/24 项相关检查通过；网站构建检查通过。
- FSI-NEXT-01：本地 Debug/Release 各累计 5 项针对性检查通过；开展 1/2/4 rank 小规模测量。测量不支持大规模扩展或稳定加速结论。
- FSI-NEXT-02：PETSc 3.23.7 云端 Debug/Release 各 29/29 项通过；[数值 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424335) 与 [网站/草稿隔离 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424264) 均成功。六周期研究最大阶段质量残差为 3.08e-16；空间渐近收敛和严格周期稳态尚未证明。
- FEM-G2A/B/C：云端 PETSc 3.23.7 Debug/Release 相关检查分别为 19/19、10/10、15/15；这些是按 PR 变更选择的相关检查，不是全量测试。

## 研发原则与边界

- 文献结论、数学推导、软件设计判断和代码实现分别标识。
- 每项算法说明应链接到数学契约、源码和验证案例。
- 性能结论必须说明硬件、软件版本、网格、容差和 MPI 配置。
- 未实现、未充分验证或仅有设计的能力必须明确标注。
- 当前相关算例以共形双域、Tet4 和小规模 MPI 验证为主；不能据此宣称非匹配界面、自动重网格、多节点生产扩展或实验验证已经完成。
- 内部工作草稿通过 Pull Request 审查；合并到 `main` 后才进入生产网站。

## 研发路线

后续工作以 [开发路线](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/ROADMAP.md) 和 [跨任务进度](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/CODEX_PROGRESS.md) 为准。