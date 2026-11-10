# 补丁版 svFSI 细网格 N400 计算完成

基线4823831。控制句柄68000退出0，12800步全部完成；completion及完整方程收敛审计保存在本目录。耗时29849.269148秒，峰值RSS274759680B。固定版本及补丁SHA见completion，未更改验收门槛。

全场物理审计84960已启动，命令：`build/analysis-venv/bin/python scripts/audit_pressure_tube.py --case build/recompute-20261109/elastic-s24-l1-n400/case.json --work build/recompute-20261109/reference-kinematic-elastic-s24-l1-n400-nu0 --svfsi --first-step 11601 --reference-log build/recompute-20261109/reference-kinematic-elastic-s24-l1-n400-nu0/solve.log --output build/recompute-20261109/reference-kinematic-elastic-s24-l1-n400-nu0/audit.json`。当前未完成，不能声明物理门槛通过。

首次误用导出目录source-case.json作为case入口，因其相对fluid.msh不在该目录，立即FileNotFoundError且未生成审计。核对原EONSim case.json与source-case.json字节完全一致后使用原案例路径，未改配置或网格。

N800参考及EONSim N1600仍运行；时间预算、交叉验证待后续完整结果。未push/PR，无新文章。
