---
title: 首步初始化成本不能外推为每步优化收益
contentStatus: draft
---

# 首步初始化成本不能外推为每步优化收益

## 研究问题与理论

Newton步需要当前状态的残量和Jacobian。对象存储、稀疏图、矩阵数值、PC数值的复用条件不同；一次首步耗时不能证明后续都存在相同浪费。

## 算法与实现证据

scripts/profile_multistep_setup.py 对 fluid/transient 与 fsi/elastic 的1/2 rank各运行3次。只使用solver_report，保留原容差；先在每次运行内平均第2–10步，再对3次重复求统计。源码基线8c8a4af，详细报告在 docs/research/MULTISTEP_SETUP_PROFILE_2026-10-30.md。

## 数值与性能证据

12次运行、120个接受步成功，固定rank重复输出最大差0。后续步setup中位数约51–82微秒，solve约3.3–8.3毫秒。完整逐步数据、RSS、残量、迭代及统计见研发报告的归档JSON。

## 局限

setup计时不等于全部构造/析构或PC数值setup。嵌套区间不能相加；没有持久化原型对照，不报告加速比。结论为暂缓原型，需求或更大规模证据出现后复评。本稿待人工审核，不自动发布。

## 参考资料

[PETSc profiling](https://petsc.org/release/manual/profiling/)，[固定源码](https://github.com/saitoasukakawaii/EONSim-new/tree/8c8a4af)。
