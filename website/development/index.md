# EONSim 项目研发

本栏目记录公开的研发方向、架构决策和已经合入主线的技术工作。当前状态以 GitHub `main` 为准。

## 当前主线

- 仓库：[saitoasukakawaii/EONSim-new](https://github.com/saitoasukakawaii/EONSim-new)
- 此页按 2026-11-26 的 [主线提交 3472a18](https://github.com/saitoasukakawaii/EONSim-new/commit/3472a18a5c7ad112084ec551a28a11d84bd3c4e7) 核对；[当前能力矩阵](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/CURRENT_STATUS.md) 记录实现和证据边界。
- 刚性管已有稳态与振荡流对照，弹性通道有移动域质量预算。仿射 Tet4 黏性项的单进程测量分别给出了单元核和整次运行的收益。

## 最近合入的研发里程碑

| 任务 | 合入状态 | 主要交付 |
|---|---|---|
| FSI-PC-05 · [PR #59](https://github.com/saitoasukakawaii/EONSim-new/pull/59) | 已合入 | field-aware 速度 AMG、稳定化 LSC/BFBt、物理 PCD、界面 mixed patch 与局部 FP32；均为可选 |
| RCR-PC-01 · [PR #58](https://github.com/saitoasukakawaii/EONSim-new/pull/58) | 已合入 | RCR port Schur、单/多出口低秩缓存与 GAMG/BoomerAMG 组合 |
| HPC · [PR #55](https://github.com/saitoasukakawaii/EONSim-new/pull/55)、[#56](https://github.com/saitoasukakawaii/EONSim-new/pull/56)、[#57](https://github.com/saitoasukakawaii/EONSim-new/pull/57) | 已合入 | 聚合多层、MPI overlap、AD SIMD、自适应 PC、collective HDF5 及后续修复 |
| FSI 性能 · [PR #51](https://github.com/saitoasukakawaii/EONSim-new/pull/51)–[#54](https://github.com/saitoasukakawaii/EONSim-new/pull/54) | 已合入 | 固定稀疏图/COO、持久会话、运行与输出优化、联合速度 GAMG/参考刚体模式 |
| HPC 单元积分 · [PR #43](https://github.com/saitoasukakawaii/EONSim-new/pull/43) | 已合入 | [Tet4 黏性积分与配对性能](/knowledge/tet4-viscosity)，以及 [50 个上游项目的阅读入口](/learning/open-source-hpc) |
| FSI-PROD-02B · [PR #41](https://github.com/saitoasukakawaii/EONSim-new/pull/41) | 已合入 | [Womersley 振荡圆管](/knowledge/womersley-verification)的解析流量、端面压差和同网格 svFSI 对照 |
| FSI-PROD-02A · [PR #38](https://github.com/saitoasukakawaii/EONSim-new/pull/38) | 已合入 | [稳态刚性管的网格与压力验证](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/development/RIGID_TUBE_QUALIFICATION.md) |
| FSI-LOAD-01 · [PR #31](https://github.com/saitoasukakawaii/EONSim-new/pull/31) | 已合入 `06b05c4` | 平滑周期压力载荷、阶段时间评价、接受步 CSV/PVD 历史与恢复检查 |
| FSI-NEXT-01 · [PR #32](https://github.com/saitoasukakawaii/EONSim-new/pull/32) | 已合入 `b2755b6` | 固定仿射速度入口、阶段和终点几何有效性、分布式界面面积观测 |
| FSI-NEXT-02 · [PR #33](https://github.com/saitoasukakawaii/EONSim-new/pull/33) | 已合入 `4f3a995` | 周期体积流量入口、无滑移弹性壁通道、独立表面/体积质量诊断 |
| FEM-G2A · [PR #27](https://github.com/saitoasukakawaii/EONSim-new/pull/27) | 已合入 `c0745ea` | 直边 Tri3 几何上的共享边 P2 标量空间、稳态 Poisson D/N 求解与分区输出 |
| FEM-G2B · [PR #28](https://github.com/saitoasukakawaii/EONSim-new/pull/28) | 已合入 `1bc87a7` | P2 Robin 边界、纯 Neumann 相容性、常数零空间与体积均值处理 |
| FEM-G2C · [PR #29](https://github.com/saitoasukakawaii/EONSim-new/pull/29) | 已合入 `dff9116` | P2 瞬态扩散、一致质量矩阵、BE/BDF2/alpha、同分区历史恢复与接受步输出 |

## 验证证据

- #59 源码 CI 85/85 选测 Release、54/54 Python；最终 PCD 38 次物理求解通过。#55 的 703–17,839 DoF 研究不支持网格无关迭代；FP32 只减少 patch 局部因子数组，未证明全局内存或时间收益。新方案保留显式选择，合成曲管的 8 本地 rank 验证不代表多节点扩展。

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
