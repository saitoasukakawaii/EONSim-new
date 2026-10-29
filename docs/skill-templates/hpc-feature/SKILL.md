---
name: hpc-feature
description: Implement or refactor a concrete FEM or multiphysics HPC feature as one runnable application path, using the repository's existing architecture and a small set of relevant checks. Use for adding physics, coupling, distributed assembly, or a solver capability; not for general document editing or unrelated software work.
---

# 完成一个 HPC 功能闭环

1. 读取仓库 AGENTS.md 和本次相关的模块/数值/并行约束。若有架构入口，沿路由读取；不要把其他项目的技术栈或本模板的来源项目当作默认事实。
2. 从用户目标确定一个可交付结果和最小相关算例。利用现有代码、配置和输入补全上下文；能合理决定的细节自行推进，仅对真正阻塞结果的缺失信息提问。
3. 写明会改变的未知量、残量/边界项、时间层、材料历史或 owned/ghost 关系；只有本次涉及的内容才需要处理，不要求单独创建计划文件。
4. 沿现有主路径实现。优先具体函数和类型，复用已有 FEM/solver；不顺便引入第二后端、通用插件框架或不需要的恢复系统。只有实际重复出现后才提炼公共层。
5. 保持残量评价可重复、历史在接受时间步后提交、局部核与通信边界清楚。遵从项目已有数值语义；近似算法如实命名。
6. 使用项目现有 Debug/Release 构建约定：Debug 帮助诊断，Release 使用相同方程和停止准则。Release 保留结果有效性和收敛失败处理。
7. 只做与改动有关的验证：编译受影响目标＋一个相关小算例；通信/所有权改动补小规模多 rank 对照；公式改动补一个针对性数值检查；性能比较使用 Release。项目或用户已有更具体约定时采用该约定。
8. 依据具体失败修正；检查通过后不无理由扩展测试范围。交付实际改动、运行结果、尚未实现部分，并在架构决定确实变化时更新唯一负责的项目文档。

