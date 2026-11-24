# Tet4 黏性项的配对实验

数值基线 `89a1a3d823396df02fa9e8acb5ded36b70938e9c`，候选 `4095e4bd4e18a350e62fd2e295d88de3a6d48640`。数值推导、完整范围与上游来源见[调研报告](../../HPC_UPSTREAM_REVIEW_2026-11-24.md)。[逐次测量](pairs.json)包括两版二进制哈希、四组实验的预热和每对样本、最终场差、逐步迭代数。[编译与测试收据](validation.json)记录三个源码组合的提交、版本锁和逐项结果。外部 svFSI 的原始大算例保存在报告所链的原 PR。

## 用仓库脚本复现

从包含本文件的干净工作树运行。相邻的临时目录容纳源码、二进制和所有原始输出。使用与仓库锁文件兼容的 Linux x86-64 机器。选择文件仅使用 ASCII 和标准 JSON。

```bash
root_dir="$PWD"
study_dir="$(mktemp -d)"
test_dir="$root_dir/docs/research/data/tet4-viscosity-2026-11-24"
git worktree add --detach "$study_dir/base" 89a1a3d823396df02fa9e8acb5ded36b70938e9c
git worktree add --detach "$study_dir/candidate" 4095e4bd4e18a350e62fd2e295d88de3a6d48640
scripts/cloud/restore.sh 3.23.7 "$study_dir/lock"
python3 - "$test_dir/validation.json" "$study_dir" <<'PY'
import json, sys
from pathlib import Path
record = json.loads(Path(sys.argv[1]).read_text())
for key in ("baseline", "candidate", "open_pr_integration"):
    target = Path(sys.argv[2]) / (key + ".json")
    target.write_text(json.dumps({"tests": [t["name"] for t in record[key]["tests"]]}))
PY
"$study_dir/base/scripts/cloud/run.sh" 3.23.7 release explicit "$study_dir/lock" "$study_dir/baseline.json"
"$study_dir/candidate/scripts/cloud/run.sh" 3.23.7 release explicit "$study_dir/lock" "$study_dir/candidate.json"
prefix_dir="$study_dir/lock/petsc-3.23.7"
PATH="$prefix_dir/bin:$PATH" LD_LIBRARY_PATH="$prefix_dir/lib" \
  "$prefix_dir/bin/python3" "$test_dir/compare.py" \
  --base "$study_dir/base/build/cloud-3.23.7-release/eonsim" \
  --candidate "$study_dir/candidate/build/cloud-3.23.7-release/eonsim" \
  --mpiexec "$prefix_dir/bin/mpiexec" --work "$study_dir/paired" --pairs 6
```

需要复现两份未合并 PR 的兼容性检查时，另在独立工作树检出 PR #41 的 `10197d0161d87796611a39f5ced22e700fb91d96`，合并 #42 的 `0c8f6fbd057028021fe8b598e037ebc0956254a9`，再 cherry-pick 候选数值提交。从该树执行同一个 `scripts/cloud/run.sh`，向显式选测传入上段生成的 `open_pr_integration.json`。本地合并和 cherry-pick 的提交时间可能不同，代码组合由上述三个固定 SHA 唯一指定。

每组先跑两版各一次预热，再交替先后顺序取六对。冻结默认 BE、物理输入、网格和停止准则。两个二进制使用相同的 `-solver_report`，流体另外启用两版相同的 `-fluid_element_report`。结果目录要求不存在，避免将旧输出当作本次输出。若耗时不稳定，先查逐对样本、节点亲和性、线程、线性迭代和其他同机作业。基线时长不同的机器只比较同机配对量。
