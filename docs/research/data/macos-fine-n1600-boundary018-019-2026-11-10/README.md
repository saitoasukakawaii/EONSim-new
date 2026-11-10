# 最后两个完成分段的边界快照归档

基线dfee737，固定生产程序未变。

## 2026-11-10：完成N1600最后边界子集归档

[证据](../research/data/macos-fine-n1600-boundary018-019-2026-11-10/README.md)：95400归档完成0，4515独立重新解码11块896成员SHA全部通过，2成员真实恢复通过；净回收301940917B。10128统一清单核对442归档/14完整清单/7不可变子集通过，采用v10。最终capture加入第五边界子集；所有体场/PVD/检查点保留，94137物理审计和38893参考仍实际live。另检查最后段through51199原字节压缩，764文件均已压缩，新增回收0，不能重复计收益。完整预算尚未执行，无push/PR。

实际运行：python3 build/recompute-20261109/prepare-fine-n1600-boundary018-019.py；archive-fine-n1600-boundary018-019.py；verify-fine-n1600-boundary018-019.py；review-current-archive-catalog-v10.py。全量原字节哈希清单、归档收据、独立解码和恢复证据随附。仅归档不被PVD引用的boundary文件；不修改正在运行的审计输入体场。统一catalog对旧归档复用先前完整解码哈希，本次不宣称重新解码所有442归档。恢复命令仍为restore-womersley-materialization.py RECEIPT。
