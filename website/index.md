---
layout: home
title: EONSim Research & Learning
titleTemplate: 高性能多物理场计算 · 研究与教学
hero:
  name: EONSim Research & Learning
  text: 从方程到可验证的多物理场求解器
  tagline: 用解析解检查流固耦合，用可复算的数据理解有限元与并行计算。
  actions:
    - theme: brand
      text: 阅读知识专题
      link: /knowledge/
    - theme: alt
      text: 查阅 50 个开源项目
      link: /learning/open-source-hpc
    - theme: alt
      text: 从基础开始
      link: /learning/
features:
  - title: 振荡圆管的流量与压力
    details: 从 Womersley 解析解读出相位，再对照 EONSim 和 svFSI 的末周期波形。
    link: /knowledge/womersley-verification
  - title: 移动域的质量预算
    details: 对齐入口流量、壁面通量和体积变化，检查弹性管内暂存的流体。
    link: /knowledge/ale-mass-budget
  - title: 四面体黏性积分
    details: 从节点力推导几何与速度切线，观察单元核加速怎样传到整次求解。
    link: /knowledge/tet4-viscosity
  - title: P2 三角形验证教程
    details: 运行共享边、Poisson 加密与瞬态制造解，分别检验空间阶和时间阶。
    link: /tutorials/p2-verification
---

## 从哪里开始

初次使用 EONSim，可以先[构建并运行示例](/tutorials/build-and-run)。要读求解器实现，可以从[单体 FSI 架构](/knowledge/monolithic-fsi)追踪流体、结构和网格未知量，或从[并行稀疏矩阵装配](/knowledge/parallel-sparse-assembly)追踪单元项如何进入 PETSc。

当前代码能复现哪些结果、后续开发还有哪些待验证的问题，见[研发记录](/development/)。
