# Agent PR 自动合并

2026-11-13 策略更新：PR 自动数值验证只执行 Release 增量测试；Debug 改为手动故障诊断。管理员必须将 main 必需检查从五项改为下列四项，并移除旧 Debug 必需项；源码修改不代表分支保护已完成部署。

## 授权与部署边界

2026-11-13：用户授权将普通研发 PR 改为 CI 通过后自动合并。开发基线为
`2baa1db9022a145adcc851fc1204790c02c0f62c`。实施范围是合并流程、网站检查触发方式和测试映射，未修改求解器、物理模型、容差、PETSc 锁文件或数值测试集合。

仓库 `Allow auto-merge` 在本次读取时已经开启；`main` 在本次读取时仍未保护。
当前 GitHub 连接访问分支保护管理接口返回 403，因此不能代替管理员修改该设置。
**代码部署不等于自动合并已经启用：缺少以下保护设置时，控制器保持关闭。**

## 管理员一次性设置

在 Settings → Branches 添加针对 `main` 的 classic branch protection rule：

- 启用 Require a pull request before merging，但不要求人工 Approvals。
- 启用 Require status checks to pass before merging，并开启 Require branches to be up to date before merging。
- 选择下列四个必需检查；检查来源选择 GitHub Actions。
- 开启 Do not allow bypassing the above settings 和 Require conversation resolution before merging。
- 不允许 force push 或删除 main。

必需检查的名称必须与工作流 job 的实际名称一致：

```
Select affected checks
PETSc 3.23.7 / release
Record incremental evidence
Build VitePress
```

Settings → General 保持 Allow squash merging / Allow auto-merge 开启；开启 Automatically delete head branches。控制器不自行删除分支，避免删除其它尚在使用的工作。

自动合并作业只申请 `contents: write`、`pull-requests: write`、`actions: read`。普通 CI 保持只读。不需要额外 PAT、自动 Approve 或将全仓默认 GITHUB_TOKEN 权限改成写入。若账户/组织策略禁止上述作业权限，需管理员允许该工作流使用这些权限。

控制器从公开分支元数据核对四项必需检查，并拒绝旧 Debug 仍为必需项的配置；未显示这些检查的其它 ruleset 配置会保持关闭，不能以删掉保护检查来解决。

## 运行方式与安全边界

`Agent PR Auto Merge` 在 Core numerical validation 或 Website Build Check 完成时重新检查 PR；也在取消 Draft、重新打开、编辑或移除标签时检查。手动重试：Actions → Agent PR Auto Merge → Run workflow，使用 main 并填写 PR 编号。

只接受同仓库 `codex/*` → `main`、非 Draft、无暂停标签的 PR。`workflow_run.pull_requests` 可能为空，因此按精确源分支查询开放 PR，再独立核验最新 head。不会执行 PR 分支中的合并脚本，不读取其缓存或 artifacts；特权作业仅检出可信 main 上的控制器。

两项工作流必须在当前 head 上成功；三个核心 job 和网站 job 必须明确 success，missing/skipped/neutral/cancelled/failed 均不能替代。读取最新 workflow run，而不是挑选历史成功结果。合并前重新读取 PR、文件列表、标签及 main 保护，确认 head/base 未变、无冲突且 GitHub 状态 clean，再用带 `sha` 的 REST Squash merge；不使用管理员绕过，不预先排队合并后续未检查提交。

必需检查保护仍由 GitHub 在合并时强制执行。多 PR 并行时，main 前进导致另一分支落后，应更新其分支并重新选测，不得关闭 strict 检查来合并。

以下情况保留人工处理：公开网站变更（website/drafts 和 website/templates 除外）、`.github/`、`.agents/`、`scripts/cloud/`、任意 AGENTS.md 和合并策略测试。改名会同时检查旧路径与新路径。涉及这些路径的混合 PR 也不会自动合并，应拆分普通代码与需人工审查的变更。

暂停单个 PR：转为 Draft，或添加 `manual-review`、`do-not-merge`、`no-automerge` 中任一标签。全局暂停：禁用 Agent PR Auto Merge 工作流。不要移除保护或必需检查。

网站检查现在对所有 PR 报告 `Build VitePress`：无网站改动时，只验证改动清单并成功退出，不安装 Node 依赖、不构建网站。相关改动仍执行原来的构建、链接和草稿隔离检查。

## 本次验证记录与未验证项

本次在隔离环境执行 `python tests/test_agent_auto_merge.py`，19 个离线测试通过，覆盖合并正例、失败/旧提交/缺失检查、最新 run 优先、head/base 变化、分支保护、标签/草稿/fork、网站与 CI 保护、重命名和空 PR 关联数组回退。测试中的合并 API 为模拟调用，**不是实际生产 PR 合并记录**。

现有 selection.json 原始 Git blob `d917eb670e4bb6c45697aab35e7312a4f08d3d59` 已按字节核对；仅增加自动合并工作流、控制器及其测试的显式映射，原有数值规则不变。新增规则仅运行该 Python 回归。修改 selection.json 本身仍遵循原策略选择 Poisson 最小回归，不扩大到全量或旧版 PETSc。

本次未在隔离环境运行 C++/MPI/PETSc 数值构建，也未声称完成远端端到端自动合并验收。管理员完成保护配置后，应用普通低风险 codex PR 验证实际 Squash 合并与分支清理；代码/测试通过和生产启用状态必须分别记录。

实现提交可用 `git log -1 --format=%H -- scripts/cloud/agent_auto_merge.py` 查询。历史任务中的“不自动合并”记录保持原貌，不改写历史事实；新的普通代码合并政策以根 AGENTS.md 的日期规则为准。
