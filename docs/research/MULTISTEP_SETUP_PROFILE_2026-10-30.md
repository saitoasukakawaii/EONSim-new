# SOLVER-02：多时间步 solver setup 实测

日期：2026-10-30；基线：8c8a4af7448908dc7756f6ea7f9b4676d1d6af00

## 结论

**暂缓持久化 NonlinearSession 原型。** 在当前两种小网格、1/2 rank 上，后续时间步的 solve 内 setup 仅约 51–82 微秒；求解区间为约 3.3–8.3 毫秒。首步开销不能外推为每步可节省成本。未测的构造/析构与数值 PC setup 仍不能归入这项可优化收益。

## 方法与环境

Release GCC 15.3.0、PETSc 3.23.7 real double/32-bit、OpenMPI 5.0.8、OpenBLAS 0.3.34。CPU cgroup 配额4核，内存32 GiB，每rank单线程。使用现有固定 cases/fluid/transient.yaml 和 cases/fsi/elastic.yaml，依次各运行1/2 rank、每组3次独立进程。保留首次初始化成本，无丢弃首步、无预热剔除；进程启动、VTU写出和退出包含在wall，但不包含在solver_report计时。只启用 -solver_report，未启用 -linear_report、Schur或额外PETSc性能输出。

fluid 使用125节点/384 Tet4、500 DoF；elastic 运行规模以逐步日志 dofs/nnz 为准。两种原始case YAML全文、SHA256、可执行文件SHA256、完整命令均保存在结果JSON。物理参数和容差未修改。FSI 为同一流体网格上的共形弹性末端块基线，非通用业务模型。

## 首步与后续步

first：各重复的第1步；later：每次重复先取第2–10步平均，再对3个独立重复取中位数和最小–最大。样本数始终是3，不将27个时间步当作27次独立实验。单位均为秒。

| 案例 | rank | 阶段 | setup中位数（最小–最大） | solve中位数 | linear中位数 |
| --- | --- | --- | --- | --- | --- |
| fluid | 1 | first | 0.00089382 (0.00086918–0.00257316) | 0.01897130 | 0.01228140 |
| fluid | 1 | later | 0.00005402 (0.00005339–0.00005722) | 0.00830869 | 0.00504527 |
| fluid | 2 | first | 0.00080536 (0.00079048–0.00089910) | 0.01862880 | 0.01175660 |
| fluid | 2 | later | 0.00007237 (0.00007051–0.00008446) | 0.00832773 | 0.00515744 |
| elastic | 1 | first | 0.00076452 (0.00075482–0.00083915) | 0.00474425 | 0.00168197 |
| elastic | 1 | later | 0.00005125 (0.00004976–0.00007510) | 0.00326592 | 0.00097428 |
| elastic | 2 | first | 0.00099518 (0.00080471–0.00103725) | 0.00639101 | 0.00286204 |
| elastic | 2 | later | 0.00008173 (0.00007918–0.00009320) | 0.00392746 | 0.00119218 |

其他计时项 schur_setup/assembly/ghost/finalize、RSS 的逐步值和同样统计均在 results.json 中。默认LU路径 schur_setup 为0，不表示已测试Schur。

## 数值检查

12次运行均退出0，120个时间步都有报告、正SNES/KSP reason和有限残量；固定rank下所有重复输出 PointData 最大差为0（阈值1e-10*(1+abs(reference))）。这不是跨rank场映射比较，也不等价于对所有模型的独立验证。

最终fluid残量约为1rank 9.2913e-17、2rank 8.9871e-17；elastic约为1rank 7.1255e-14、2rank 7.1209e-14；各重复一致。每步SNES与KSP累计迭代、最终残量均已保存；本轮没有数值差异需调查。未额外运行全套CTest。

## 计时解释与限制

setup_seconds 从 solve 入口至初始残量评价前，不覆盖 NonlinearSystem 构造、全部PC数值建立或退出析构。solve_seconds 含初始残量、可选Schur配置与SNESSolve；assembly/ghost/linear 是其部分嵌套区间。各项按rank分别取最大值，不能相加当作总时间。finalize_seconds 不含其后的输出和函数返回析构。RSS是采样，不是单次分配量，峰值是进程生命周期高水位。

不从上述数据计算持久化加速比。三次测量规模有限，首步/后续差异可能涉及库初始化及数值状态变化。没有优化后对照，也没有量化PC数值重建可节省多少。无需为本轮稳定小算例申请更大环境；若业务规模需要，再增加网格和细分计时，重新评估原型必要性。

## 重现与证据

```bash
source /workspace/.eonsim-tools/activate.sh
cmake --build --preset release --parallel 4
python3 scripts/profile_multistep_setup.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-solver02-new
```

work必须不存在以排除旧结果。完整[结果JSON](data/multistep-setup-2026-10-30/results.json)及同目录16份日志已入Git。脚本遇到失败、步数缺失、非有限数值和重复输出差异时停止；有效日志及缺报告/负reason/NaN三类输入检查通过。该脚本复用 benchmark_nonlinear_setup.py 的VTU读取，未修改求解器。
