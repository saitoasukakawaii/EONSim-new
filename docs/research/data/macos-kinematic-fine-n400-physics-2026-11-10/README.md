# 补丁版 svFSI N400 局部物理审计

基线 ea6dfff，审计句柄84960退出0。实际窗口11601..12800，共1200个相位，使用真实11600端点。方程收敛、运动学、阶段质量与散度检查通过；两域Jacobian为正。末两周期五场最大相对差7.91847473385e-06<1e-5。Lamé均值误差1.23758810011%<2%，参照输入平均压力0.02。完整审计gzip读回逐字节一致，完整本地原始文件清单已记录；原始数据未上传。

执行命令：`build/analysis-venv/bin/python scripts/audit_pressure_tube.py --case build/recompute-20261109/elastic-s24-l1-n400/case.json --work build/recompute-20261109/reference-kinematic-elastic-s24-l1-n400-nu0 --svfsi --first-step 11601 --reference-log build/recompute-20261109/reference-kinematic-elastic-s24-l1-n400-nu0/solve.log --output build/recompute-20261109/reference-kinematic-elastic-s24-l1-n400-nu0/audit.json`。

采用已批准并验证的固定版本补丁，身份见completion。独立空间/时间/尾周期/采样预算、细网格跨求解器比较仍未完成；历史粗网格和时间预算失败保留。无完整资格或48小时完成声明，无push/PR。复用现有审计方法，不新增文章。
