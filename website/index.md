---
layout: home
title: EONSim Research & Learning
titleTemplate: 高性能多物理场计算 · 研究 · 开发 · 教学
hero:
  name: EONSim Research & Learning
  text: 从数学理论到 HPC 多物理场软件
  tagline: 记录可追溯的研究、可复现的数值实验，以及可以分享和教学的工程知识。
  actions:
    - theme: brand
      text: 开始学习
      link: /learning/
    - theme: alt
      text: 浏览知识专题
      link: /knowledge/
    - theme: alt
      text: 查看 EONSim 源码
      link: https://github.com/saitoasukakawaii/EONSim-new
features:
  - title: 数学与数值方法
    details: 从控制方程、弱形式、有限元离散到时间积分、稳定化和误差分析。
    link: /learning/fem
  - title: CFD 与流固耦合
    details: 理解 Navier–Stokes、ALE、单体 FSI、界面条件与耦合 Jacobian。
    link: /learning/cfd
  - title: HPC 与并行计算
    details: 学习 MPI、Owned/Ghost、稀疏矩阵装配、PETSc 和块预条件。
    link: /learning/hpc
  - title: 科研软件工程
    details: 了解 C++ 架构、文献到规格、测试、性能分析和可复现研发流程。
    link: /development/
---

## 从研究问题到可验证的软件

EONSim Research & Learning 是围绕 EONSim 多物理场求解器建设的公开知识平台。内容覆盖数学基础、数值算法、软件实现、并行计算和研发实践。

这里的文章不仅解释“是什么”，还尽量回答：
- 数学模型和假设是什么？
- 离散后得到什么残量和代数系统？
- 算法如何映射到数据结构和代码？
- 用什么解析解、制造解或基准验证？
- 性能数据在什么硬件、网格和容差下得到？

## 内容状态

所有内容会区分理论说明、代码实现和实验验证状态。开发中的草稿通过 GitHub Pull Request 审核；只有审核并合并到生产分支的内容才会进入正式网站。

## 2026-11-03 主线进展

本次内容核对所依据的功能主线检查点为 [`4f3a995`](https://github.com/saitoasukakawaii/EONSim-new/commit/4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e)。近期已合入的工作包括：

- **单体 FSI**：平滑周期压力与接受步历史、固定速度入口与阶段/终点几何检查，以及周期体积流量入口、无滑移弹性壁通道和移动域质量预算。
- **二维 P2 标量有限元**：直边三角形六节点二次场、稳态 Poisson 的 D/N/Robin/纯 Neumann 边界，以及 BE、变步 BDF2 和一阶 generalized-alpha 瞬态扩散。

这些结果有针对性 Debug/Release、MPI、重启和数值研究证据；它们不等同于全量测试、大规模生产扩展或实验验证。可从 [研发状态](/development/) 和 [知识专题](/knowledge/) 查看范围与限制。

## 推荐起点

- [CFD 求解器学习路径](/learning/cfd)
- [有限元与固体力学](/learning/fem)
- [HPC 与并行计算](/learning/hpc)
- [EONSim 并行稀疏矩阵装配专题](/knowledge/parallel-sparse-assembly)
- [构建与运行 EONSim](/tutorials/build-and-run)
