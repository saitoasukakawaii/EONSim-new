# EONSim 项目研发

本栏目记录公开的研发方向、架构决策和已完成的技术工作。

## 研发原则

- 文献结论、数学推导、软件设计判断和代码实现分别标识。
- 每项算法说明应链接到数学契约、源码和验证案例。
- 性能结论必须说明硬件、软件版本、网格、容差和 MPI 配置。
- 未实现、未充分验证或仅有设计的能力必须明确标注。
- 内部工作草稿通过 Pull Request 审查；合并到 main 后才进入生产网站。

## 当前交付

2026-10-31：P0–P8、B0–B5 及 G0B/G0/G5/G1 已交付，包括语义 DoF/三种 PC 树、适用的 BE/BDF2/generalized-alpha、Tri3/Quad4 相容混合二维标量。验证最多 4 rank，尚无多节点生产扩展证明。PR #24 已将日常 CI 固定为 PETSc 3.23.7 Debug/Release，旧版仅手动专项。详见 [进度与证据](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/CODEX_PROGRESS.md)。

## 研发主线

1. 数值可靠性和求解器治理；
2. 有限元 Kernel 与装配性能；
3. MPI 多节点扩展；
4. 多物理场能力扩展；
5. 由性能证据驱动的异构计算。

总体工程路线见 [EONSim 工程研发总纲](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/EONSim_ENGINEERING_PROGRAM.md)。
