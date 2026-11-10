# Womersley解析分析的有界HDF恢复

基线9fd0e46，原生产求解器和分析器未改。

## 2026-11-10：Womersley原分析器按状态恢复入口验证

[证据](../research/data/macos-womersley-streaming-analysis-2026-11-10/README.md)：67041真实4801/4802/6399/6400四状态验证退出0，直接采用生产wrapper factory，3个归档状态与1个保留端点经原Study.state读取后与先展开读取数组完全一致。峰值展开3241128B，异常清理与端点保留通过；未完成9600步前置拒绝且不生成输出/证明。新入口只恢复cycle4原HDF，原analyze_womersley.main、三周期选择、quadrature4及全部门槛不变；完整分析未执行，不能将四状态验证算作验收。后续N1600完整解析分析可使用analyze-womersley-n1600-streaming.py，每帧先恢复并核对原字节；原预算中N800归档恢复义务仍保留。94137完整FSI审计继续，无push/PR。

实际验证：OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 build/analysis-venv/bin/python build/recompute-20261109/test-streaming-womersley-analysis.py。每个归档与原清单/收据SHA绑定，每次解码恢复原路径，调用原Study.state校验元数据/时钟/签名和读取字段，再校验并删除该次创建副本。原保留端点不删除。完整archive SHA在流式读取前验证；本次只解码需要成员，不宣称每次重解码全部归档尾部。全量预算、全部三周期指标及最终验收尚未执行。

完成9600步后入口：build/analysis-venv/bin/python build/recompute-20261109/analyze-womersley-n1600-streaming.py --work build/recompute-20261109/alpha2-s96-l1-n1600 --quadrature 4 --output build/recompute-20261109/alpha2-s96-l1-n1600-analysis.json。要求输出不存在，完成后另查完整materialization proof和原门槛；不能只依赖进程退出0。
