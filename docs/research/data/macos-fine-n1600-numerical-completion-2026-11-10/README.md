# 精细N1600全部数值步完成

基线4ad99fa。34110控制器退出0，completion确认51200接受步/20成功分段（early+19dense）；最后dense019到51200，冻结求解器、原时间步/容差/收敛及数值验收门槛未改变。完整末4800相位物理审计94137已启动、实际live，尚无物理验收结论；完整capture及独立误差预算仍待完成。预算前须恢复粗N1600体场与细N800体场。

92296最后段历史帧压缩退出0，220文件事后SHA通过，回收199954432B。7842在51064保留原7553。仅对最后136步按实测最大四文件总7742796B/步核算：136步1053020256B，增加10%输出余量、64MiB收尾和256MiB缓冲；恢复前free必须大于20GiB加上述预算。明确仅最终段提前保留线改为20.25GiB、每秒检查；原20GiB控制器硬下限不变。原7553保留81.732634秒后恢复，47799监测运行至控制器终态并退出0，没有触发新的保留。此资源策略不影响数值方程或验收标准，也不适用于其他长程任务未经重新核算的容量。

实际审计命令：`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 build/analysis-venv/bin/python scripts/audit_pressure_tube.py --case build/recompute-20261109/elastic-s24-l1-n1600/case.json --work build/recompute-20261109/elastic-s24-l1-n1600 --first-step 46401 --output build/recompute-20261109/elastic-s24-l1-n1600-audit.json`。

旧N800预算失败保持，不能把数值完成当作整体资格通过；svFSI参考仍运行，其他3组容量保留待恢复；未push/PR。
