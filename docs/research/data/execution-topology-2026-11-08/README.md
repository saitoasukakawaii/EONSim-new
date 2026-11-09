> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Host CPU metadata and WSL affinity scope

The UTC03:59–04:00 observations distinguish Windows hardware metadata from
the topology presented inside the WSL2 virtual machine.

| Observation | Reported configuration |
|---|---|
| [Windows CIM](windows-host.json) | Intel Core i9-12900K;16 cores,24 logical processors |
| [WSL lscpu/sysfs](wsl-guest.json) |24 guest logical CPUs;12 core groups,2 threads per group |
| Actual study binding | Linux CPU-affinity masks using guest CPU indices |
| Host physical-core binding | Not measured or configured by these studies |

Microsoft documents `processors` as the number of logical processors assigned
to the WSL2 VM. Consequently, guest affinity and guest topology alone do not
establish a one-to-one binding to host physical cores.
[Microsoft WSL configuration documentation](https://learn.microsoft.com/en-us/windows/wsl/wsl-config).

Earlier study records used “physical cores” for the guest-reported core
groups. Read those labels as **WSL guest core groups**, with the actual CPU
indices recorded in each command/guard. The corresponding README/draft labels
are corrected; immutable JSON, raw logs, frozen controllers and archive hashes
remain intact. This clarification does not change any numerical field, clock,
convergence or memory-limit result.

Concurrent project workloads and Windows scheduling were not isolated. Local
elapsed-time comparisons support only the recorded execution conditions,
not host-core scalability or a universally faster allocation. The
[manifest](manifest.json) records the byte counts and SHA256 of both observations.
