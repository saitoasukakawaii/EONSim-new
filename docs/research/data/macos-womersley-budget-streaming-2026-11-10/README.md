# Archived target Womersley budget streaming

基线72bb877。原audit-womersley-budget.py、compare_womersley.py及10%门槛未改。包装器仅适配alpha2细N800归档状态3201..4799（4000保留），每次compare/sampling独立恢复cursor，tail交替周期分别维护cursor；读取完成即清理，最终evidence只复用实际恢复读取时校验的SHA，未读缺失文件拒绝。元数据/仍保留文件继续直接哈希。

AST通过；`build/analysis-venv/bin/python build/recompute-20261109/check-womersley-budget-streaming.py`，65775 exit0，实际序列[3201,4001]重复两次及[4001,4000,4002]（采样可能倒序的保留端点），所有数组与原读取器完全一致，3个归档状态的实际SHA/evidence及清理通过。范围仅此真实读取机制，不替代完整预算。

完整入口保留六周期完成前置、原解析/周期/积分条件；fineN1600只比较第六周期，当前第六周期状态仍保留，若之后归档须相应适配。本次完整预算未运行，Wom9600/解析审计未结束。复用已有按序归档恢复方法，无新算法文章，无push/PR。
