# EONSim 项目研发

本栏目记录公开的研发方向、架构决策和已完成的技术工作。

## 研发原则

- 文献结论、数学推导、软件设计判断和代码实现分别标识。
- 每项算法说明应链接到数学契约、源码和验证案例。
- 性能结论必须说明硬件、软件版本、网格、容差和 MPI 配置。
- 未实现、未充分验证或仅有设计的能力必须明确标注。
- 内部工作草稿通过 Pull Request 审查；合并到 main 后才进入生产网站。

## 研发主线

1. 数值可靠性和求解器治理；
2. 有限元 Kernel 与装配性能；
3. MPI 多节点扩展；
4. 多物理场能力扩展；
5. 由性能证据驱动的异构计算。

总体工程路线见 [EONSim 工程研发总纲](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/EONSim_ENGINEERING_PROGRAM.md)。
