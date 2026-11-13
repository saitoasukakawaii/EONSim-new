# CI-gated agent auto-merge smoke test (2026-11-13)

This documentation-only fixture exercises EONSim-new's `codex/*` → `main`
pull-request path after configuring the four required GitHub Actions checks.

It changes no solver, tests, build inputs, dependencies, permissions,
publication rules, or website content. The fixture alone is **not** proof
of successful automatic merging: verify the associated PR's GitHub Actions
results, merge timestamp and merge actor before drawing that conclusion.

See [Agent PR auto-merge policy](AGENT_AUTO_MERGE.md) for the protected
workflow and fail-closed prerequisites.
