# 知识专题

## 流体与流固耦合

| 想解决的问题 | 阅读内容 |
|---|---|
| 如何验证脉动流的幅值和相位？ | [用振荡圆管同时验证流量和压力](/knowledge/womersley-verification)提供解析解、同网格跨程序波形和归档复算命令。 |
| 移动管壁时怎样核算流量？ | [移动流体域的质量预算](/knowledge/ale-mass-budget)从 P1 入口积分走到每个接受步的体积变化。 |
| 流体、结构和网格如何共同收敛？ | [单体 FSI 架构](/knowledge/monolithic-fsi)说明联合未知量、界面约束与块预条件。 |

## 离散与高性能计算

| 想解决的问题 | 阅读内容 |
|---|---|
| 什么工作能移出积分点循环？ | [四面体黏性项如何只积分一次](/knowledge/tet4-viscosity)给出速度切线、ALE 几何导数和同机配对计时。 |
| MPI 进程如何装配它所拥有的稀疏矩阵行？ | [并行稀疏矩阵装配](/knowledge/parallel-sparse-assembly)追踪分区、Owned/Ghost、预分配与插入。 |
| 怎样独立验证高阶标量场？ | [P2 三角形验证教程](/tutorials/p2-verification)从共享边开始，分别检查空间加密和时间加密。 |

查找其他框架对同一问题的处理方式，可用[50 个 HPC 开源项目阅读指南](/learning/open-source-hpc)。查阅实验来源或待审文章，可用仓库的[知识记录](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/research/KNOWLEDGE_LOG.md)和[草稿目录](https://github.com/saitoasukakawaii/EONSim-new/blob/main/website/drafts/README.md)。
