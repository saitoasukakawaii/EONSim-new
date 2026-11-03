# FSI-LOAD-01 本地验收

源码 `a6c6761084f2003c72593107c6aa5cbc351d75bb`，基线 `417e6f9`。
日常锁 PETSc 3.23.7，WSL2 本地执行器，Debug/Release，新增验证最多 2 rank。
绘图标签后续仅作换行调整；没有因此重跑数值验证。

## 实际命令

构建分别运行（MODE 为 debug/release）：

```bash
.cloud/micromamba run -p .cloud/petsc-3.23.7 cmake --build build/cloud-3.23.7-MODE --target eonsim verify_fsi_element -j 4
```

下面数值命令均通过同一运行前缀执行：

```bash
.cloud/micromamba run -p .cloud/petsc-3.23.7 env \
 LD_LIBRARY_PATH=/home/tfblab633/EONSim/.cloud/petsc-3.23.7/lib \
 OMPI_MCA_pml=ob1 OMPI_MCA_btl=self,sm,tcp \
 PRTE_MCA_rmaps_default_mapping_policy=:oversubscribe \
 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 <command>
```

`LD_LIBRARY_PATH` 为本机恢复前缀；其他环境按实际恢复目录调整。
实际命令主体如下，全部退出 0：

```bash
python tests/verify_fsi_pressure.py --executable build/cloud-3.23.7-debug/eonsim --mpiexec .cloud/petsc-3.23.7/bin/mpiexec --work build/fsi-pressure-debug --checks state
python tests/verify_fsi_pressure.py --executable build/cloud-3.23.7-debug/eonsim --mpiexec .cloud/petsc-3.23.7/bin/mpiexec --work build/fsi-pressure-convergence-debug-final --checks convergence
python tests/verify_fsi_pressure.py --executable build/cloud-3.23.7-release/eonsim --mpiexec .cloud/petsc-3.23.7/bin/mpiexec --work build/fsi-pressure-convergence-release --checks convergence
ctest --test-dir build/cloud-3.23.7-debug -R '^(fsi_element_jacobian|rigid_fsi_verification)$' --output-on-failure --output-junit fsi-pressure-checks.xml
ctest --test-dir build/cloud-3.23.7-release -R '^(fsi_pressure_state|fsi_element_jacobian|rigid_fsi_verification)$' --output-on-failure --output-junit fsi-pressure-checks.xml
```

Debug：直接脚本 state/convergence 通过，CTest 2/2。
Release：直接脚本 convergence 通过，CTest 3/3。
两种模式各覆盖四个相关检查，不能把直接脚本运行写成 CTest 4/4。
精度证据在 `convergence-*.json`，CTest 实际结果在 `ctest-*.xml`。
选择规则 `python3 tests/test_ci_selection.py` 26/26 通过，修改路径均有映射；预期 PR 选择 24 项，尚不是本地 24 项通过证据。

示例按 [使用说明](../../../development/FSI_PRESSURE_HISTORY.md) 实际运行，Release、2 rank、100 步、t=0.2；
`example.csv` 为原始响应，`example.png` 使用系统 Python matplotlib 3.6.3 生成并检查。
配置：默认生成器 n=2，流体 48/固体 51 Tet4；相对容差 1e-10、绝对容差 1e-12、字段缩放沿生成器。
精度测试相对容差 1e-11、绝对容差 1e-13、固定 tau=0.05，参考 BDF2 h=1/64000，终止时间 .04。
BE h=.00025/.000125/.0000625；BDF2/alpha h=.0005/.00025/.000125，alpha rho=.5。

## 失败与修正

- 初始测试脚本写 `backward_euler`，而配置接口实际是 `be`：修正测试，未改变生产接口。
- 比较器只取 owned 且本 rank 有域单元的节点，漏掉跨域 ownership 节点：改为读取实际域单元使用的本地/ghost 节点，按稳定 mesh ID 对照。
- checkpoint 改参数确实拒绝；断言由不存在的 `signature` 文本改为实际 `Checkpoint mesh/partition/physics mismatch`。
- 刚体配置误继承 `structure` 字段缩放，读取阶段拒绝：刚体变体去掉弹性字段缩放。
- JSON 的 Infinity 在 yaml-cpp 转换阶段被拒绝；改用 `.inf` 标量以直接测试有限性检查。
- BE 粗网格 h=.001/.0005 的速度阶数 0.745，未达门槛。缩小时间步、细化参考后速度阶数 0.942/0.971，通过原门槛 0.85；没有修改数学模型或停止容差。
- 单 rank 写片失败是预期负例；无 PVTU/PVD 发布，无成功状态，无 MPI 挂起。
- Release 编译在未修改的 `pc_plan.cpp` 出现 GCC `-Wfree-nonheap-object` 警告；编译成功，本任务没有修复或归因为已确认误报。

没有运行全量、PETSc 3.19.6、新增 4 rank 或性能测量。其他模块历史证据不计入本次通过数。
