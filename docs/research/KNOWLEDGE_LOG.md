# EONSim Knowledge Log

本文件是知识资产索引，不代替文章正文、文献阅读笔记或实验原始数据。

## 状态定义

- idea：值得研究的主题，尚无完整内容。
- draft：已有草稿，尚未审核。
- review：正在人工审核。
- published：已合并到 main 并出现在公开网站。
- superseded：被更新版本替代，保留历史链接。

## 已发布知识

| Topic | 状态 | 主题 | 文章 |
|---|---|---|---|
| HUB-K001 | published | CFD 求解器学习路径 | [CFD](/learning/cfd) |
| HUB-K002 | published | 有限元与固体力学 | [FEM](/learning/fem) |
| HUB-K003 | published | HPC 与并行计算 | [HPC](/learning/hpc) |
| HUB-K004 | published | EONSim 并行稀疏矩阵装配 | [Parallel Sparse Assembly](/knowledge/parallel-sparse-assembly) |
| HUB-K005 | published | EONSim 单体 FSI 架构 | [Monolithic FSI](/knowledge/monolithic-fsi) |
| HUB-K006 | published | EONSim 构建与运行 | [Build and Run](/tutorials/build-and-run) |

## 候选知识主题

| Topic | 状态 | 主题 | 文章/预期证据 |
|---|---|---|---|
| HUB-K007 | draft | PETSc 非线性求解器对象生命周期 | [PETSc object lifetime](../../website/drafts/petsc-object-lifetime.md)；源码审计已完成，性能尚未测量 |
| HUB-K008 | idea | Newton 变量/残量一致缩放 | 数学推导、Jacobian 变换、Jv 与线搜索验证 |
| HUB-K009 | idea | Schur/GAMG 网格规模行为 | 多网格规模迭代数、内存和耗时 |
| HUB-K010 | idea | MPIAIJ 对角/非对角预分配和装配成本 | d_nnz/o_nnz、远程插入、MatAssembly 计时 |
| HUB-K011 | idea | PETSc SNES/KSP/PC setup profiling | 多时间步日志、重复运行统计和环境信息 |

## 登记规则

- 只有形成可复用知识的任务才登记；普通 typo、纯格式变更不登记。
- 每个条目关联文章路径、源码 commit、参考来源和验证证据（如有）。
- 没有运行数据时不得填写性能数值；没有测试时不得标记为已验证。
- 草稿位于公开仓库，不能存放私密研究笔记、凭据、受限数据或未授权论文全文。
- 发布状态只有在文章进入正式栏目并合并到 main 后才改为 published。
