# 分支合并与清理记录（2026-10-31）

后续状态：本次清理之后 G0B/G0/G5/G1 与 INFRA-01 最终验收已在 PR #23 完成；下文未实现/review 只指清理当时。最新状态见 [进度](CODEX_PROGRESS.md)，分支名清单不是当前远程分支列表。

用户授权合并远程分支并清理多余分支。整合前 main 为 `f44c3e0e81f090637f6f21a7b63a9d12d3e30424`，远程共有 main 与 7 个非主分支；没有开放 PR，main 未设置保护。

## 审查与整合

6 个历史分支的最新提交已经是 main 的祖先，不重复移植内容。新增 `docs/fem-g0a-dof-design` 的 `b674d5a082173a695a0932c1f8f58f4e6563ff04` 比 main 多 1 个提交、没有落后提交，变更 14 个文件：详细设计、Python 标准库参考模型/测试/检查工具、文档状态和历史证据。

保留该分支的全部有效内容，采用 merge commit 纳入其历史。设计描述的 DoF 语义、独立代表、存储编号、物理验收和 PC 分组相互分离；参考模型验证固定 K/W、非零 lifting、嵌套父编号、共享界面和模拟分区，不能替代真实 PETSc/MPI 验收。

合并前运行检查发现两项 Windows 兼容问题：默认 GBK 不能读取 UTF-8 中文；Git 的 CRLF 检出使 14 份未改动源码的原始字节哈希与 Linux 审计不符。修复仅在检查工具中显式读取 UTF-8，并在计算哈希前将 CRLF 归一化为审计基线的 LF；源码、其他空白和历史基线哈希不改写。正反例确认实际代码及非换行空白变化仍可检出。

FEM-G0A 设计子任务标记 done；整体 G0 以及 G0B/G5/G1 尚无本次生产实现，INFRA-01 最终集成数值验收保持 review。原开发日志及测试证据保留其日期与提交范围，知识草稿仍未发布。

## 验证

- `python -B docs/research/fem_g0a/test_reference_model.py`：20/20 通过，含 Fraction 精确代数与 1/2/4 模拟分区索引逻辑。
- `python -B docs/research/fem_g0a/check_artifacts.py`：AST、Markdown、固定源码引用和 14 份源码哈希检查；本次运行输出单独保存，不覆盖原分支历史记录。
- 哈希正反例：LF/CRLF 等价，真实表达式变化和其他空白变化仍导致不同哈希。
- 整合差异、文档链接与围栏检查；所有待删除 tip 在最终整合提交中可达。
- 无生产 C++、CMake、算例、数值测试或 CI 改动；未运行编译、CTest、MPI、性能或网站构建。提交包含 `[skip ci]`，只运行此次变更相关的参考测试和静态检查。

## 远程操作与可追溯清单

采用一次原子推送，同时正常快进更新 main 并删除下列 7 个分支。操作前复核 main 和各分支 SHA；删除使用精确旧 SHA 保护，任何远程变化都先停止并重新审查。保留 main，不创建替代的远程整合分支。提交历史通过 main 保留，必要时可按下列完整 SHA 恢复分支名称。

| 清理分支 | 清理前 tip | 整合前状态 |
|---|---|---|
| `audit/petsc-nonlinear-lifecycle` | `51ef2e50b70c5906aa80cdd526a51cac1f142572` | 已包含于 main |
| `codex/fluid-cached-coo` | `c1fef032f32b0da9c76b8db3d61427beebdfb737` | 已包含于 main |
| `codex/infra-reproducible-mpi-ci` | `787372e746a3523194a8139bc36c70cee9e21f13` | 已包含于 main |
| `docs/codex-research-workflow` | `45a324f905eb2569cf4332c3aefb3d5bf85ab7e1` | 已包含于 main |
| `docs/fem-g0a-dof-design` | `b674d5a082173a695a0932c1f8f58f4e6563ff04` | 本轮审查合入 |
| `docs/general-fem-architecture-plan` | `1585585f8b6ef52d9e52ad12df0eaa5d207cdd6f` | 已包含于 main |
| `docs/refresh-continuous-loop-state` | `0f9ea3cf4ae4f1c1a39bd1eeebeb302dcdf1e3fa` | 已包含于 main |

机器可读清单：[branches.json](../research/data/branch-cleanup-2026-10-31/branches.json)。当前设计入口：[FEM-G0A](../architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md)。检查输出：[checks.txt](../research/data/branch-cleanup-2026-10-31/checks.txt)。
