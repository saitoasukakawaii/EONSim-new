# 远程分支清理与整合记录

日期：2026-10-30（Asia/Shanghai）。用户明确要求：删除完全合并的 18 个远程分支，审查其余 6 个，将需要保留的内容合入 main；优先架构和 CI，禁止编译。

## 范围与交付方式

整合前 main 为 `38a5e516ffe129d1b70c7c1bd8365deb5ded101a`。先逐分支验证 tip 是该主线的祖先，再使用精确旧 SHA 保护和原子推送删除 18 个远程引用；没有改写提交历史。删除后复核远程只剩 main 与下面 6 个分支。

使用本地整合分支逐次审查和解决冲突，再正常快进推送 main，不强制覆盖 main。用户已明确授权本次合并，因此无需另建等待审批的 PR。内容有选择地保留，六个源分支的受审查 tip 均通过 merge commit 纳入历史；这不表示采纳了所有旧文件版本。原六个远程分支引用保留，不扩大本次指定的 18 个删除范围。

## 六个分支的审查决定

| 分支 | 受审查 tip | 决定 |
|---|---|---|
| `docs/general-fem-architecture-plan` | [1585585](https://github.com/saitoasukakawaii/EONSim-new/commit/1585585f8b6ef52d9e52ad12df0eaa5d207cdd6f) | 完整保留 16 份架构/规划 Markdown；G0–G8 仍 deferred，不代表功能实现。 |
| `codex/infra-reproducible-mpi-ci` | [5745fd3](https://github.com/saitoasukakawaii/EONSim-new/commit/5745fd3912151fd895fbad89138795092c1b99bc) | 保留依赖锁、CI、失败恢复和证据；修正固定 ABI 检查范围及 JUnit 证据解析。审查期间新增两次提交，复核后纳入。 |
| `codex/fluid-cached-coo` | [c1fef03](https://github.com/saitoasukakawaii/EONSim-new/commit/c1fef032f32b0da9c76b8db3d61427beebdfb737) | 实现已在 PR #21 合并；补齐 PR 链接及历史交付日志，舍弃会把 done 退回 review 的旧状态。 |
| `audit/petsc-nonlinear-lifecycle` | [51ef2e5](https://github.com/saitoasukakawaii/EONSim-new/commit/51ef2e50b70c5906aa80cdd526a51cac1f142572) | 保留 ALE 调用方与原稿追溯链接，补入现有 PETSc 生命周期报告；不新增重复报告/草稿，不恢复旧任务队列。 |
| `docs/codex-research-workflow` | [45a324f](https://github.com/saitoasukakawaii/EONSim-new/commit/45a324f905eb2569cf4332c3aefb3d5bf85ab7e1) | 保留网站源码/产物检查、CI 隔离哨兵及贡献补充；沿用主线更完整的模板、AGENTS 和队列，舍弃过时 PR API 阻塞记录。 |
| `docs/refresh-continuous-loop-state` | [0f9ea3c](https://github.com/saitoasukakawaii/EONSim-new/commit/0f9ea3cf4ae4f1c1a39bd1eeebeb302dcdf1e3fa) | Goal 可用性说明已在主线；其余为 PR #12 后的旧检查点，已由后续交付取代，合并历史时保持现有状态。 |

## 合并审查修正

1. **锁定 ABI 的探针范围。** 原 CI 分支在所有 BUILD_TESTING 配置中强制 OpenMPI/int32 检查。新增默认关闭的 `EONSIM_VERIFY_LOCKED_RUNTIME`，仅云入口开启；普通测试配置不被锁定环境的假设误拒绝。
2. **成功证据必须完整。** JUnit 按测试名与 inventory 一一对应，重复不能顶替缺失；未知、缺失、无效时长拒绝，`error`/`failure` 均算失败，跳过不能算成功。6 项纯 Python 回归覆盖有效结果和负例。
3. **文档检查可独立运行。** 保留旧工作流的内容检查工具，增加 `--source-only` 并明确不证明产物隔离；支持 Windows CRLF 检出。CI 同时放置 draft/template 哨兵，默认检查仍要求已有网站构建产物。
4. **状态与契约一致。** 不回退已完成的 COO、生命周期审计和 profiling 任务；更正构建文档中的 Doxygen target、锁定探针开关及上游 SNES 行号。原分支的运行记录与本次整合检查分开。

## 实际验证与未验证范围

- `python -B tests/test_cloud_evidence.py`：6 项通过，只处理合成 XML，不启动编译器、CTest 或 MPI。
- `node website/scripts/check-content.mjs --source-only`：10 份作者工作流 Markdown 的结构与本地链接通过；未检查生成网站。
- Python AST、两份 Bash 脚本的 `bash -n`、两份 GitHub 工作流 YAML、JSON 证据与依赖锁结构检查；两锁分别有 96 和 101 个带 SHA256 的固定包 URL。没有安装依赖或执行恢复入口。
- 整合差异的空白/冲突检查、25 份变更 Markdown 的围栏及 156 个本地文件链接检查通过；Git 祖先关系验证六个受审查 tip 已纳入整合历史。
- 原分支 d3f69d1 的 [CI 41060786421](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41060786421) 三个数值 job 已成功；本次只读取历史状态。完整历史证据见 [INFRA-01](../research/INFRA_01_REPRODUCIBLE_MPI_CI_2026-10-30.md)。后续分支运行不由本会话启动。
- **本次未运行 CMake 配置、项目编译、CTest、MPI、数值算例、性能实验、网站构建。** 推送提交包含 `[skip ci]`，避免 push 启动构建。最终集成的数值验证尚未执行，INFRA-01 保留 review；架构 G0–G8 仍 deferred。

## 已删除的 18 个分支

以下提交均在整合前 main 中可达；删除的只是远程分支名，提交可从主线历史追溯。需要恢复名称时可从下列完整 SHA 建立新引用。

| 已删除远程分支 | 删除时 tip |
|---|---|
| `docs/codex-goal-driven-development-loop` | `0f632434d03dada0daea25001d10610f75c5a7fe` |
| `docs/eonsim-engineering-program` | `b0905de1b76fb5b633199248d475cc895d56b274` |
| `docs/goal-mode-and-hpc01-checkpoint` | `1b11fd8b7f9add5134f87ba5f22ec7030d6ef3e1` |
| `docs/newton-scaling-spec` | `25d53427d7cb61ac563f3c7d4a92395a9d65a08d` |
| `docs/solver-baseline-audit` | `ac35d87036909dfb65b3b407cc4b2f7c461145a3` |
| `feat/assembly-phase-timers` | `3c9612423034182a9a3889e0edcfe89bdd57de3d` |
| `feat/codex-continuous-development-workflow` | `24547e7e564fa777a0edf15f6df98e00d45b97d1` |
| `feat/eonsim-research-learning-hub` | `d65142dbf3e645487bddedb86ff18248e377efc6` |
| `feat/fluid-element-timers` | `5a00907b2d8fbf927bcf1fc135bea14d75be44c8` |
| `feat/solver-level-dimensions` | `40b3b814104a76291bcd8c9f0f6f2c9f687bc64f` |
| `fix/linear-solve-ksp-lifetime` | `835bc9681d413f48b7e3ee4dac9daef2a549ca0d` |
| `fix/profile-log-validation` | `e4a14c87e656e819c24b6431c1c4c0809a5a731b` |
| `perf/assembly-phase-baseline` | `f5ce29373bf89bb177c8ffe9d9c1153dd6b9978f` |
| `perf/fluid-element-overhead` | `934a62e92e91bf6f4e7f32f040877803c978843c` |
| `perf/multistep-setup-profile` | `4c421123a71597f31f372edacf16e3e387dc9066` |
| `perf/nonlinear-setup-baseline` | `c162b31532b8c4124dc481c7e41ec50ee6d54090` |
| `perf/schur-mesh-profile` | `f16ebedf4181a741d0ffbf695c07312d5bd03e17` |
| `perf/transient-assembly-profile` | `be779fdecc84461f3734d28c7ab171e7cec51c07` |

机器可读清单：[branches.json](../research/data/branch-integration-2026-10-30/branches.json)。知识草稿：[MPI 失败与云端验证](../../website/drafts/mpi-failure-cloud-reproducibility.md)，按仓库知识采集 Skill 更新，仍未发布。
