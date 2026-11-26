---
title: "缩减 FSI 系统的旋转粗模态与联合速度 AMG"
description: "用真实参考坐标与语义行构造粗空间，区分预条件层级复用和数值更新。"
contentStatus: draft
algorithm: "Reference-coordinate rigid modes and coupled velocity GAMG"
sourceReferences:
  - "https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/gamg/agg.c"
  - "https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/gamg/gamg.c"
eonsimCommit: "88e6c3359b742735877177eb4584b987caae1790"
---

# 缩减 FSI 系统的旋转粗模态与联合速度 AMG

未发布算法草稿。目标读者为了解有限元、块预条件和分布式稀疏矩阵的开发者。
源码/修复均先推送后验证。最终实现与驱动为 `88e6c335`，实际证据限定为共享单机小网格；
本稿区分算法能力、正确性与性能结论。

## 问题与数学对象

共形单体 FSI 将界面速度消元为唯一代表，联合速度块 $A_v$ 同时包含流体、结构和两者之间
的非对角项。压力和 ALE 仍由外层语义树处理，主 Newton 方程 $J\Delta x=-R$ 保持完整。

在参考位置 $X_i$ 上，三个位移/速度平移候选为 $e_j$，三个旋转候选为
$e_j\times(X_i-X_c)$。每个代数行只取它的实际物理分量。本质约束行对应的候选值设为零。
惯性、约束和非对称耦合使这些向量通常不是 $A_v$ 的精确零空间；它们作为粗近似信息。

twolevel 原有分片常数按 rank、domain、entity kind、component、mode、space 分组，
新增固体 P1 旋转后用两次正交化剔除线性相关候选。插值 $P$ 保持分布式稀疏结构，
粗矩阵为 $A_c=P^T A_vP$。ASM 处理局部误差，粗校正为
$z\leftarrow z+P A_c^{-1}P^T(r-A_vz)$。

GAMG 使用活动标量行上的一个归一化常数近模态，由 PETSc 根据完整 $A_v$ 构造聚合层级，
不为每个 MPI rank 或每个物理分量添加全局模态。`rigid` 仅支持 twolevel；在 GAMG 上
请求它会明确报错。两条算法的粗空间不同，scalar GAMG 不等于向量弹性 AMG。

该边界来自固定版本实现：PETSc 3.23.7 的聚合会为每个 aggregate 保留 nvec 个粗列，
局部 QR 没有按真实局部秩截断。即使全局平移/旋转向量线性无关，小型非单点或仅覆盖
部分物理分量的 aggregate，其局部候选矩阵仍可能秩亏。因此本轮不向不规则 scalar AIJ 盲目附加六模态；
packed-vector 辅助空间及相应转移算子仍需独立实现和证据。

## 几何、约束与并行身份

坐标由物理布局提供，按 owned 独立代表排序，接口 alias 不复制。缩减后的节点可能缺少
一个或多个分量，有限维刚体和端口也不是三分量节点，因此不能将矩阵强制标为 blocksize 3。
P1 顶点、body 和边界压力由明确的 `DofKey` 区分；body 的零占位坐标没有几何意义。

旧镜像弹性示例尤其容易出错：流体逻辑网格的 $x$ 与固体物理参考位置不同，后者为
$1+h(1-x)$，$h$ 是固体厚度。粗模态必须采用与结构单元一致的变换。双域输入已经存储实际
参考位置，无须该映射。ALE 当前坐标不会在每次 Newton 迭代重定义参考粗空间。

## 层级复用和更新

固定拓扑与参考基允许复用插值。PETSc 3.23.7 的 GAMG reuse 分支仍重新计算 Galerkin
矩阵数值并更新各层算子，不能把这称为使用旧 Jacobian。系数变化过大时固定插值可能变差，
因此保留 `pc_gamg_reuse_interpolation false`。配置或约束变化由现有会话机制共同重建。

默认 PREONLY 的含义是一次 V-cycle。粗 GMRES 根据右端和容差改变工作量，因此外层仍用
FGMRES；一次 PREONLY 正收敛理由不证明满足某个备用内层 rtol。

## 实现与证据

实现位于 `src/algebra/coupled_velocity_pc.cpp`、`src/algebra/pc_plan.cpp`、
`src/fem/field_layout.cpp`、`src/fem/reduced_layout.cpp` 和 `src/physics/fsi.cpp`。
配置及最终证据入口为 [FSI 分块预条件器](../../docs/development/FSI_BLOCK_PRECONDITIONER.md)。

代数验证应检查模态张成空间、约束零行、独立 Galerkin 作用、真实残量及矩阵数值更新，
而不要求正交化后某列的符号固定。物理验证应在相同密度、步长和输入分区下与直接解比较，
包括 RCR 历史、重启、真实非线性回滚及全部接受步。性能须分别报告建立、线性解和总时间。
实际 a7e0 代数 3/3、RCR/动脉/recipe/域布局 4/4 通过，两种新配置的 1/2-rank 真实回滚与重启通过。
最终 88e6 只改变故障标记刷新与验证器生命周期，受影响 COO 1/1 和进程控制 9/9 通过；
未重复运行未受影响的已有通过项目。原重启 helper 没有保留子进程原始 stdout，独立审计仅直接
重放了其保存的字段/拓扑/checkpoint；cutback 次序仍以执行时断言和完成摘要为依据。

最终 quick/full/robustness 共 **78/78 runs、656 接受步、1,282 次线性修正**，含 8 条完整
32 步轨迹和 30 次密度比/时间步对照。独立 raw/log/owned-VTU 重放通过，真实残量/门槛最大
`0.6010255`，五场相对直接参考峰值差最大 `2.6171e-9`；门槛仍为 `2e-6`。
`rho_s/rho_f=1,.1,.01`、`dt=1/32,1/128` 的八步对照不代表任意附加质量或高 Re 参数保证。

细网格 3,024 DoF/2 rank 的 rigid 完整轨迹外迭代从 `5445` 减到 `5050`。
三个交替四步样本相对常数基线的 wall 配对变化中位数 `−10.79%`，范围
`[−13.14%,+0.44%]`；linear 中位变化 `−15.10%`，范围也跨零。
粗网格 rigid 无时间优势；GAMG 两档 wall 配对中位变化为 `+5.35%/+4.83%`。
因此两项保持显式选项，不因模态/层级更丰富就切换默认，亦不把有限样本写成普遍加速。

实际命令、统计定义、二进制/源提交及全部失败原件见
[完整验证索引](../../docs/research/data/fsi-block-multilevel-2026-11-26/README.md)。
没有多节点、GPU、百万自由度或网格无关复杂度结论。

## 开发中暴露的三个错误

GAMG 对象创建后尚未具备 MG 层级，直接调用 `PCMGSetCycleType` 会返回 wrong order。
将 V-cycle 默认选项交由 GAMG 在创建层级时应用即可修复，不能用删除层级检查或忽略 PETSc 错误规避。
初始三个代数失败及远端相关失败均保留，修复后才计入通过结果。

致命故障前的 stdout 若未刷新，可能被另一个 rank 的 stderr 前缀拼接，导致严格的行首
标记解析丢失真实事件。本例标记实际包含正确 `team=2,batch=1,thread=0`；在 collective
错误传播前刷新解决了已观察的事件边界，验证器和 fatal 无输出/无接受步门槛没有放宽。

短命令的外部耗时还受 `subprocess.run(timeout=...)` 的等待轮询影响。验证驱动改为阻塞
child wait 与独立 watchdog，排除后续日志解析；父 SIGTERM 和 watchdog 启动异常也必须
进入清理，避免 detached MPI rank 留在后台。真实退出码和超时部分日志应保留。
这些机制只服务可靠测量和失败清理，不是物理求解性能收益。

## 进一步检查

本轮已验证 twolevel 改变参考坐标原点后的张成空间、缺分量/退化坐标/空 owner，以及
固定插值下改变矩阵数值的 Galerkin 作用。强制 `reuse_interpolation=false` 重建路径未单独测量。
若以后采用不同系数范围或网格，应针对该真实使用者比较固定/重建插值与总成本；
本轮结论不外推为所有网格的推荐配置。
