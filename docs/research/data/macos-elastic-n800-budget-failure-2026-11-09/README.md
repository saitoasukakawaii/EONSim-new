# Fresh EON N800 independent error budget: FAILED

70281 completed with exit1 after full budget generation. Every input study passes periodicity, quality and positive-geometry prerequisites. Original unchanged N800 kernel and10% gates retained.

Time/space ratios: fluid velocity26.7138438%, fluid pressure67.3757014%, solid velocity13.2007138% FAIL; mesh displacement3.8287887%, solid displacement3.9705006% pass. Every tail and sampling term passes. The complete field differences and all consumed raw hashes are retained; large reports gzip-compressed and decoded readback exact. Local physical/Lamé success does not qualify this numerical budget.

Next diagnostic: determine the contribution of the stabilization time term before attributing all differences to temporal truncation. EON FSI currently supports fixed full tau only, whereas standalone fluid already supports explicit stabilization_time_scale; any FSI diagnostic extension must preserve the absent-option default, reject conflicting/invalid settings and bind restart signatures. No new default stabilization or threshold adopted, no existing production binary replaced, no rerun launched here. Resolution extension remains necessary if original default budget cannot pass.

Command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 build/analysis-venv/bin/python build/recompute-20261109/analyze-fresh-elastic-budget.py --solver eonsim --output build/recompute-20261109/elastic-n800-budgets`.
