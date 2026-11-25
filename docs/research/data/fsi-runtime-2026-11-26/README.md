# FSI-PERF-03 evidence

Source preparation in progress on `codex/fsi-performance-runtime`, based on
main `2dcb06c26a0359175e4f5a771d5bbff6dfc928af` and runtime commit
`47237a033820b53ceb19003d032bb50f70994bb0`.

No new compile, numerical verification or performance run has occurred at this
checkpoint. The required order is source → remote push → targeted Release
validation → paired measurements → protected head-locked squash merge.

Implementation and runtime option semantics are in
[FSI_RUNTIME_OPTIMIZATION.md](../../../development/FSI_RUNTIME_OPTIMIZATION.md).
The final evidence index will identify every source/build, accepted test,
failure, raw run, timing method, correctness comparison and CI check; a planned
run is not evidence. The locked environment is PETSc 3.23.7 Release.
