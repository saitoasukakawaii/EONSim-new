# 全仓 Markdown 进度审查（2026-10-31）

源码基线：`a508e3d`（PR #24 合并）；本地工作分支：`codex/markdown-progress-audit`。
审查范围为 Git 管理的全部 88 份 Markdown，另新增本文；不包含依赖包、构建产物或 Git 内部文件。没有改动生产代码、算例、CI 配置或原始数值证据。

## 依据与处理原则

- Git 历史确认 PR #23/#24 已合入；当前工作流 `.github/workflows/core-numerics.yml` 确认日常仅 3.23.7 Debug/Release，3.19.6 仅手动专项。本次未读取远程 Checks，不将合并本身当作测试通过证据。
- [集成验收](FEM_INTEGRATION_VALIDATION.md) 及其归档 JSON 确认 G0B/G0/G5/G1 的交付范围；G2/G4 只有必需子集，其余阶段 deferred。60/60/13 是 PR #23 检查点记录，非本次运行结果。
- 对照 `src/io/checkpoint.cpp`、`src/mesh/partition.cpp`、`src/physics/scalar2d.cpp`、时间与 DoF/PC 接口、`CMakeLists.txt`、`docs/doxygen/Doxyfile`，核对格式、失败策略、测试注册和文档输入。
- 现行指南直接修正；历史实验、设计快照和会话日志保留原日期、提交、失败及测量数据，必要时添加后续状态导航。没有把原失败记录改成通过，也没有外推性能。
- Skill 与模板检查其适用范围，通用教学页保留理论内容；已有知识草稿按 eonsim-knowledge-capture 补状态与证据链接，仍不发布。未新增无技术成果的教学文章。

## 主要修正

1. 入口与路线不再将 G0–G8 一概写为未实现，明确二维标量与三维多物理场、可选 PC 树与固定存储的区别。
2. 时间与状态文档对应 BE/BDF2/generalized-alpha 的适用支持矩阵；保留 BE 原始推导，指向高阶历史/共同 stage 契约。checkpoint 容器仍 v3，二维分区 v3、三维 v2。
3. PR #24 从 review 更新为已合入；当前队列不重复安排 SOLVER-02。知识索引中已有文章改为 draft，保持人工发布边界。
4. 删除“源码目录尚未创建”“所有平台均未验证 WSL”等过时描述；测试数量按检查点记录，要求读取实际 inventory。
5. 修复知识索引的站点根路径；原机 Windows 源码链接改为带来源提交的文本定位。外部原工程不在本仓库，未重新取得或验证。

## 实际验证与限制

- `python3 /tmp/eonsim_md_audit.py`：对全部项目 Markdown 检查 UTF-8 读取、结束换行、代码围栏、冲突标记、标题（首页使用 home 布局）、本地目标与 Markdown 锚点；本仓库的固定 SHA 源码链接通过 `git cat-file --batch-check` 核对目标存在。
- `git diff --check`：检查修改空白；另核对变更清单只有 Markdown、草稿仍有 `contentStatus: draft`。
- 临时检查脚本位于 `/tmp`，用于本次审查，不新增项目检查门禁。最终检查结果在下方补记。
- `command -v node` 未找到 Node：未运行 VitePress 构建、渲染或生成物隔离检查。静态检查不等于站点构建通过。
- 未运行 CMake、C++ 编译、CTest、MPI、数值/性能实验；未逐式重新推导全部历史数学内容，未访问外部文献/网站链接验证其在线可用性。源码链接检查只证明路径存在，不重新证明引用算法或历史测试结论。
- 审查结束时修订保留在本地分支。用户随后追加授权推送及合并，交付状态以 CODEX_PROGRESS/CODEX_TASK_QUEUE 和 Git 历史为准；草稿不提升为正式文章。

## 逐文件处理清单

“保留”表示已纳入本次状态/链接审查，未发现需要随当前进度修改的内容；不是新的数值、理论或性能验收。

| 文件 | 处理 | 说明 |
|---|---|---|
| [.agents/skills/eonsim-knowledge-capture/SKILL.md](../../.agents/skills/eonsim-knowledge-capture/SKILL.md) | 保留 | 流程/模板适用范围仍成立，无需改动 |
| [AGENTS.md](../../AGENTS.md) | 修订 | 注明 PR #24 工程规则已合入 |
| [MULTIPHYSICS_HPC_DESIGN_PRINCIPLES.md](../../MULTIPHYSICS_HPC_DESIGN_PRINCIPLES.md) | 修订 | 同步 G 阶段、时间格式及已提供 Skill |
| [README.md](../../README.md) | 修订 | 同步 CI/能力/目录；区分历史环境和默认 BE 案例 |
| [docs/architecture/EONSIM_NEXT_STAGE_DESIGN.md](../architecture/EONSIM_NEXT_STAGE_DESIGN.md) | 修订 | 区分已落地功能、历史推导及剩余建议 |
| [docs/architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md](../architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md) | 修订 | 原参考模型不冒充生产验证；补 G0 后续交付 |
| [docs/architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md](../architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md) | 修订 | 标明原基线缺口表与历史整合验证语境 |
| [docs/architecture/L1_LAYERS_AND_DEPENDENCIES.md](../architecture/L1_LAYERS_AND_DEPENDENCIES.md) | 修订 | 更新实际目录、拓扑、时间格式与平台边界 |
| [docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md](../architecture/L2_DISCRETIZATION_AND_OPERATORS.md) | 修订 | 更新 G0/G1/G5 与计时后续成果 |
| [docs/architecture/L2_MONOLITHIC_FSI.md](../architecture/L2_MONOLITHIC_FSI.md) | 修订 | 保留 BE 推导，指向已交付高阶映射 |
| [docs/architecture/L2_MULTIPHYSICS_AND_STATE.md](../architecture/L2_MULTIPHYSICS_AND_STATE.md) | 修订 | 更新 G5 历史、步控制和模型特定失败策略 |
| [docs/architecture/L2_PARALLEL_MEMORY_AND_BACKENDS.md](../architecture/L2_PARALLEL_MEMORY_AND_BACKENDS.md) | 保留 | 现有契约、支持边界或导航与本次状态一致 |
| [docs/development/AGENTS_AND_SKILLS.md](AGENTS_AND_SKILLS.md) | 修订 | 同步当前能力、工程状态或文档入口 |
| [docs/development/B5_ACCURACY_AND_PERFORMANCE.md](B5_ACCURACY_AND_PERFORMANCE.md) | 保留 | 固定日期/提交的研究或实验记录保留 |
| [docs/development/BRANCH_CLEANUP_2026-10-31.md](BRANCH_CLEANUP_2026-10-31.md) | 修订 | 补后续进度导航；保留原提交的历史证据 |
| [docs/development/BRANCH_INTEGRATION_2026-10-30.md](BRANCH_INTEGRATION_2026-10-30.md) | 修订 | 补后续进度导航；保留原提交的历史证据 |
| [docs/development/BUILD_AND_VALIDATION.md](BUILD_AND_VALIDATION.md) | 修订 | 修正旧 inventory、平台限制与已实现重试策略 |
| [docs/development/CLOUD_ENVIRONMENT_DIAGNOSTICS_2026-10-30.md](CLOUD_ENVIRONMENT_DIAGNOSTICS_2026-10-30.md) | 保留 | 固定日期/提交的研究或实验记录保留 |
| [docs/development/CODEX_GOAL_WORKFLOW.md](CODEX_GOAL_WORKFLOW.md) | 修订 | 移除重复领取已完成 SOLVER-02 的推荐 |
| [docs/development/CODEX_PROGRESS.md](CODEX_PROGRESS.md) | 修订 | PR #24 完成，新增本次文档审查检查点 |
| [docs/development/CODEX_SESSION_LOG.md](CODEX_SESSION_LOG.md) | 修订 | 追加本次实际操作、检查与未运行项目 |
| [docs/development/CODEX_TASK_QUEUE.md](CODEX_TASK_QUEUE.md) | 修订 | 更新已完成任务；标记历史任务规格与本地待审状态 |
| [docs/development/DOCUMENTATION_AND_COMMENTS.md](DOCUMENTATION_AND_COMMENTS.md) | 修订 | Doxygen INPUT 已包含真实源码目录 |
| [docs/development/DOF_AND_PC_GROUPING.md](DOF_AND_PC_GROUPING.md) | 保留 | 现有契约、支持边界或导航与本次状态一致 |
| [docs/development/EONSim_ENGINEERING_PROGRAM.md](EONSim_ENGINEERING_PROGRAM.md) | 修订 | 同步当前能力、工程状态或文档入口 |
| [docs/development/FEM_INTEGRATION_VALIDATION.md](FEM_INTEGRATION_VALIDATION.md) | 修订 | 同步当前能力、工程状态或文档入口 |
| [docs/development/PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md) | 保留 | 固定日期/提交的研究或实验记录保留 |
| [docs/development/ROADMAP.md](ROADMAP.md) | 修订 | 同步当前能力、工程状态或文档入口 |
| [docs/development/SCALAR_2D.md](SCALAR_2D.md) | 修订 | 补瞬态线性失败有限缩步与稳态报错边界 |
| [docs/development/TIME_INTEGRATION.md](TIME_INTEGRATION.md) | 保留 | 现有契约、支持边界或导航与本次状态一致 |
| [docs/doxygen/index.md](../doxygen/index.md) | 修订 | 同步当前能力、工程状态或文档入口 |
| [docs/research/ASSEMBLY_PHASE_BASELINE_2026-10-30.md](../research/ASSEMBLY_PHASE_BASELINE_2026-10-30.md) | 修订 | 补后续进度导航；保留原提交的历史证据 |
| [docs/research/EONSIM_ARCHITECTURE_AUDIT_2026-10-29.md](../research/EONSIM_ARCHITECTURE_AUDIT_2026-10-29.md) | 修订 | 补后续进度导航；保留原提交的历史证据 |
| [docs/research/EONSIM_PERIGEE_REVIEW.md](../research/EONSIM_PERIGEE_REVIEW.md) | 修订 | 区分原工程；失效机器链接转为原提交相对源码定位 |
| [docs/research/FEM_FRAMEWORK_LEARNING_2026-10-30.md](../research/FEM_FRAMEWORK_LEARNING_2026-10-30.md) | 保留 | 固定日期/提交的研究或实验记录保留 |
| [docs/research/FLUID_COO_ASSEMBLY_2026-10-30.md](../research/FLUID_COO_ASSEMBLY_2026-10-30.md) | 修订 | 补后续进度导航；保留原提交的历史证据 |
| [docs/research/FLUID_ELEMENT_OVERHEAD_2026-10-30.md](../research/FLUID_ELEMENT_OVERHEAD_2026-10-30.md) | 保留 | 固定日期/提交的研究或实验记录保留 |
| [docs/research/INFRA_01_REPRODUCIBLE_MPI_CI_2026-10-30.md](../research/INFRA_01_REPRODUCIBLE_MPI_CI_2026-10-30.md) | 修订 | 补后续进度导航；保留原提交的历史证据 |
| [docs/research/KNOWLEDGE_LOG.md](../research/KNOWLEDGE_LOG.md) | 修订 | 补齐 draft 状态、仓库链接和后续验收来源 |
| [docs/research/MULTISTEP_SETUP_PROFILE_2026-10-30.md](../research/MULTISTEP_SETUP_PROFILE_2026-10-30.md) | 保留 | 固定日期/提交的研究或实验记录保留 |
| [docs/research/NEWTON_SCALING_SPEC_2026-10-30.md](../research/NEWTON_SCALING_SPEC_2026-10-30.md) | 保留 | 固定日期/提交的研究或实验记录保留 |
| [docs/research/NONLINEAR_SETUP_BASELINE_2026-10-30.md](../research/NONLINEAR_SETUP_BASELINE_2026-10-30.md) | 修订 | 补后续进度导航；保留原提交的历史证据 |
| [docs/research/PETSC_LIFECYCLE_AUDIT_2026-10-30.md](../research/PETSC_LIFECYCLE_AUDIT_2026-10-30.md) | 修订 | 补后续进度导航；保留原提交的历史证据 |
| [docs/research/SCHUR_MESH_PROFILE_2026-10-30.md](../research/SCHUR_MESH_PROFILE_2026-10-30.md) | 修订 | 补后续进度导航；保留原提交的历史证据 |
| [docs/research/TRANSIENT_ASSEMBLY_PROFILE_2026-10-30.md](../research/TRANSIENT_ASSEMBLY_PROFILE_2026-10-30.md) | 修订 | 补后续进度导航；保留原提交的历史证据 |
| [docs/research/UPSTREAM_ARCHITECTURE_REVIEW.md](../research/UPSTREAM_ARCHITECTURE_REVIEW.md) | 保留 | 固定日期/提交的研究或实验记录保留 |
| [docs/skill-templates/hpc-feature/SKILL.md](../skill-templates/hpc-feature/SKILL.md) | 保留 | 流程/模板适用范围仍成立，无需改动 |
| [environments/README.md](../../environments/README.md) | 修订 | 主力/旧锁 CI、WSL2 范围与已修复超时 |
| [website/README.md](../../website/README.md) | 保留 | 现有契约、支持边界或导航与本次状态一致 |
| [website/development/contribution.md](../../website/development/contribution.md) | 保留 | 现有契约、支持边界或导航与本次状态一致 |
| [website/development/index.md](../../website/development/index.md) | 修订 | 同步当前能力、工程状态或文档入口 |
| [website/drafts/README.md](../../website/drafts/README.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/drafts/assembled-permutation-and-pc-verification.md](../../website/drafts/assembled-permutation-and-pc-verification.md) | 修订 | 同步后续交付或验证状态；保留原数据与 draft |
| [website/drafts/assembly-phase-baseline.md](../../website/drafts/assembly-phase-baseline.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/drafts/assembly-phase-timers.md](../../website/drafts/assembly-phase-timers.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/drafts/bdf2-time-error-and-stabilization.md](../../website/drafts/bdf2-time-error-and-stabilization.md) | 修订 | 同步后续交付或验证状态；保留原数据与 draft |
| [website/drafts/dof-semantics-and-nested-fsi-blocks.md](../../website/drafts/dof-semantics-and-nested-fsi-blocks.md) | 修订 | 同步后续交付或验证状态；保留原数据与 draft |
| [website/drafts/fluid-coo-assembly.md](../../website/drafts/fluid-coo-assembly.md) | 修订 | 同步后续交付或验证状态；保留原数据与 draft |
| [website/drafts/fluid-element-overhead.md](../../website/drafts/fluid-element-overhead.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/drafts/fluid-element-timing.md](../../website/drafts/fluid-element-timing.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/drafts/general-fem-dof-architecture.md](../../website/drafts/general-fem-dof-architecture.md) | 修订 | 同步后续交付或验证状态；保留原数据与 draft |
| [website/drafts/generalized-alpha-stage-and-physical-output.md](../../website/drafts/generalized-alpha-stage-and-physical-output.md) | 修订 | 同步后续交付或验证状态；保留原数据与 draft |
| [website/drafts/linear-solve-ksp-lifetime.md](../../website/drafts/linear-solve-ksp-lifetime.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/drafts/mpi-failure-cloud-reproducibility.md](../../website/drafts/mpi-failure-cloud-reproducibility.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/drafts/multistep-setup-profile.md](../../website/drafts/multistep-setup-profile.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/drafts/newton-scaling.md](../../website/drafts/newton-scaling.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/drafts/nonlinear-setup-baseline.md](../../website/drafts/nonlinear-setup-baseline.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/drafts/normalized-mesh-and-bilinear-scalar-elements.md](../../website/drafts/normalized-mesh-and-bilinear-scalar-elements.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/drafts/petsc-object-lifetime.md](../../website/drafts/petsc-object-lifetime.md) | 修订 | 同步后续交付或验证状态；保留原数据与 draft |
| [website/drafts/profile-log-validation.md](../../website/drafts/profile-log-validation.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/drafts/schur-mesh-profile.md](../../website/drafts/schur-mesh-profile.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/drafts/semantic-blocks-and-parent-numbering.md](../../website/drafts/semantic-blocks-and-parent-numbering.md) | 修订 | 同步后续交付或验证状态；保留原数据与 draft |
| [website/drafts/solver-level-dimensions.md](../../website/drafts/solver-level-dimensions.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/drafts/transient-assembly-profile.md](../../website/drafts/transient-assembly-profile.md) | 保留 | 原证据及局限仍适用，保持未发布 |
| [website/index.md](../../website/index.md) | 保留 | 现有契约、支持边界或导航与本次状态一致 |
| [website/knowledge/index.md](../../website/knowledge/index.md) | 保留 | 现有契约、支持边界或导航与本次状态一致 |
| [website/knowledge/monolithic-fsi.md](../../website/knowledge/monolithic-fsi.md) | 修订 | 同步 G0/G5 并限定概念方程；修正 LaTeX 换行 |
| [website/knowledge/parallel-sparse-assembly.md](../../website/knowledge/parallel-sparse-assembly.md) | 修订 | 区分物理验收字段与 PC 树；补已有 profiling 状态 |
| [website/learning/cfd.md](../../website/learning/cfd.md) | 保留 | 通用教学路线，不作为新增能力声明 |
| [website/learning/fem.md](../../website/learning/fem.md) | 保留 | 通用教学路线，不作为新增能力声明 |
| [website/learning/hpc.md](../../website/learning/hpc.md) | 保留 | 通用教学路线，不作为新增能力声明 |
| [website/learning/index.md](../../website/learning/index.md) | 保留 | 通用教学路线，不作为新增能力声明 |
| [website/templates/algorithm-note.md](../../website/templates/algorithm-note.md) | 保留 | 流程/模板适用范围仍成立，无需改动 |
| [website/templates/benchmark-report.md](../../website/templates/benchmark-report.md) | 保留 | 流程/模板适用范围仍成立，无需改动 |
| [website/templates/development-log.md](../../website/templates/development-log.md) | 保留 | 流程/模板适用范围仍成立，无需改动 |
| [website/templates/knowledge-article.md](../../website/templates/knowledge-article.md) | 保留 | 流程/模板适用范围仍成立，无需改动 |
| [website/tutorials/build-and-run.md](../../website/tutorials/build-and-run.md) | 修订 | 同步当前能力、工程状态或文档入口 |
| [website/tutorials/index.md](../../website/tutorials/index.md) | 保留 | 现有契约、支持边界或导航与本次状态一致 |

清单合计：88 份既有文件，修订 47 份、保留 41 份；另新增本文。

## 最终静态检查结果

`python3 /tmp/eonsim_md_audit.py` 退出 0：89 份 Markdown、530 个本地目标、5 个 Markdown 锚点、71 个固定 Git 目标，错误 0。240 个外部链接未请求网络验证。`git diff --check` 退出 0；47 份既有修改均为 Markdown，改动的知识草稿全部保留 draft。新增本文后共 48 个变更文件；未执行网站构建和数值测试。
