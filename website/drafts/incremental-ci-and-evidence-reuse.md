---
title: "从全量 CI 转向增量检查：选择、执行与证据复用"
description: "EONSim 如何区分本次通过、历史证据和无需运行，避免跳过检查被误报为数值验收。"
contentStatus: draft
taskId: "CI-INCREMENTAL-01"
pullRequest: "https://github.com/saitoasukakawaii/EONSim-new/pull/26"
baseCommit: "ef20e03"
resultCommit: "8f695cc6ed17fcbbd2736cceba38e7984de2b67e"
date: "2026-10-31"
---

# 从全量 CI 转向增量检查：选择、执行与证据复用

## 目标和读者

面向维护 CMake/CTest 与 GitHub Actions 的开发者。目标是让测试成本跟随本次改动，同时保存可审查的执行证据。本任务不涉及新的有限元公式或数值性能结论。

## 原有行为与原因

原工作流在分支 Push、PR 和 main Push 上运行 Debug/Release 全套；云入口即使选择一个标签，也先编译全部目标。只在文档中声明“少量测试”不会改变这条执行链。

因此要分开处理：事件触发、改动到检查的映射、构建目标、实际执行、证据记录。取消 Push 数值触发解决跨事件重复；按 PR 差异选测解决无关模块重复；同一 PR 的成功 receipt 解决只补文档时重复原有检查。

## 实现契约

本稿对应开发分支 `codex/pr-incremental-ci`；源码提交与最终云端结果以[会话记录](../../docs/development/CODEX_SESSION_LOG.md)为准。

- `scripts/cloud/selection.json` 为显式规则，源代码必须覆盖相关耦合使用者。未知非文档路径失败，不默认运行所有测试。共享模块只选择代表性入口，不声称所有下游行为都已重验。
- `scripts/cloud/selection.py` 从 PR base 与实际 merge preview 计算首次选择。重命名同时处理删除和新增路径；现有 CTest 名称、目标、rank 纳入映射。
- `scripts/cloud/validate.py` 接收精确清单，配置后检查真实 inventory，构建相关目标，并要求 JUnit 与清单完全一致。核心库仍整体构建，没有跨任务编译缓存。
- `scripts/cloud/receipt.py` 只使用同 PR 的成功 workflow artifact。base、规则/环境指纹和历史祖先关系必须匹配，Debug/Release 来源完整；当前结果与历史继承分别保存。新文件或新输入影响原有路径时，必须重验受影响项。

证据继承不是“当前提交又通过一次”。一个文档后续提交可以通过选测检查，而数值运行次数为零。报告必须能指出每项数值证据来自哪个原提交和 run。

## 错误与排查

本地首轮覆盖检查发现 `fsi_element.hpp` 缺少路径映射，说明规则需要覆盖公共头文件，而不只是 `.cpp`。补齐后覆盖检查通过。映射仍须随代码依赖变化维护；它不是自动推导完整 C++ 依赖图的工具。

工作流级路径过滤可能让 required check 留在 Pending；本实现保留检查名称，在 job 内跳过不需要的数值步骤。选择器失败时数值检查也失败，不能把依赖被跳过当成功。[GitHub 官方说明](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs)

artifact 缺失、过期或 API 不可用时，没有有效复用基线；应重新选择 PR 涉及的项，而不是复用无法核实的结果。取消和失败的运行不能成为成功基线。

## 验证与限制

初次提交前执行：`python3 tests/test_ci_selection.py`（24 项通过）、`python3 tests/test_cloud_evidence.py`（6 项通过）、`bash -n scripts/cloud/run.sh`、actionlint 1.7.7 与 `git diff --check`。随后补充手动 all/explicit 入口与 PR 禁止全量的 2 项测试并通过；选测测试现共 26 项。这些是 CI 逻辑证据，不是求解器数值验收。

[首轮云端证据](../../docs/research/data/ci-incremental-2026-10-31/initial.json)确认 Debug/Release 各只运行 `poisson_verification` 一项并通过，构建目标仅 eonsim 与 verify_runtime。[后续文档提交](../../docs/research/data/ci-incremental-2026-10-31/reuse.json)已验证两种模式均跳过恢复、构建和数值执行，新的 receipt 保留首次数值 run/提交来源。没有运行全量套件或旧锁数值测试。

当前只在同一 PR、相同 base 与指纹下复用，最多查询最近 90 个成功 PR runs；不跨 PR 缓存测试结果。artifact 保留 14 天，过期会失去可复用证据。没有测量节省百分比，不作性能承诺。网站工作流保持独立。

## 进一步检查

新增共享算子时，除了自身单元测试，还应把哪些耦合使用者纳入映射？一个仅改文档的提交继承了旧数值证据后，报告中如何避免把它误计入本次通过数？这两个问题应在日常 review 中结合 diff 和 receipt 一起回答。
