# Completed alpha1 N400 archive re-encoding staging

基线49e615f。原alpha1-s96-l1-n400.json记录zstd3 --long=27，原包2021659536B。复用已验证stage-full-n800-recompression控制器，AST通过；`python3 build/recompute-20261109/stage-wom-alpha1-n400-recompression.py`，38852运行，已进入encoding。

原归档/源清单SHA前置通过；预留20GiB加原包大小和256MiB暂存空间，运行时20.5GiB停止保护，新包大于原包亦停止。候选包须完整旧/新解码tar SHA一致后才能标verified-staged，目前尚未完成。原归档和全部恢复收据不改，阶段结束后需另行事务采用、全成员验证和总目录更新。

当前引用同一包的5个顶层记录：alpha1-s96-l1-n400.json、completed-consumers-materialization、cycle3-materialization、post-budget-materialization及cycle3-one-member-restore-probe.json；后续采用必须全部一致更新，不遗漏恢复探测收据。τ75128/Wom6194存活且容量暂停，原期限保留。无push/PR，无新增算法文章。
