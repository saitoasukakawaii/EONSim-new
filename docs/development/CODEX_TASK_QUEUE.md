# Codex 任务队列

优先级：P0 阻塞/可靠性，P1 基线与近期增量，P2 研究候选。状态：ready → active → review → done；blocked 必须注明阻塞条件。仅 ready 且依赖已满足的任务可以直接领取。review 不等于合并完成。

| ID | 优先级 | 状态 | 目标及范围 | 依赖 | 验收条件 |
| --- | --- | --- | --- | --- | --- |
| WF-001 | P1 | blocked | 状态文件、模板、知识规则及 PR 工作流 | e40599b | 七个要求文件齐备；Markdown 检查、网站构建、草稿隔离通过；CMake 与求解器文件不变；独立 PR 待审核 |
| AUD-001 | P1 | blocked | 复核 a2dfb60 的求解器诊断及测试证据 | WF-001 合并 | 在明确提交上编译受影响目标；solver_failures、nonlinear_acceptance、schur_verification 通过；记录实际 rank/命令和结果；修复失败需另列范围 |
| KNOW-001 | P1 | blocked | 从 solver_report 实现形成知识草稿 | AUD-001 完成 | 固定 commit 源码链接；区分真实残量、预条件残量和各层 reason；引用实际输出；不声明未测性能；仅进入 drafts |
| PERF-001 | P2 | blocked | 独立流体时间步对象生命周期及 profiling 基线 | AUD-001 完成 | 选定一个已有 transient case；固定网格、容差、Release 环境；至少 3 次实测并报告离散程度、阶段耗时和内存；明确复用候选与正确性检查；不先改求解算法 |
| SPEC-001 | P2 | blocked | 完整 Newton 缩放的最小数学规格 | AUD-001 完成 | 在已有 L2 契约中明确变量/残量缩放、约束、线搜索、增量恢复、原始验收及 Jv 等价验证计划；不得把规格当作实现 |

这些候选来自工程总纲 A/B，优先级不代表已经测得性能瓶颈。新增任务必须有 ID、依赖、范围及可判定验收；领取后把分支/基线写入进度和日志。下一候选为 AUD-001，等待 WF-001 人工合并。

WF-001 阻塞仅在 PR 创建：独立分支已推送，实现与本地验收完成；GitHub REST/GraphQL API 返回 Forbidden。恢复访问后创建 PR 并转为 review，人工合并后转 done。
