# Immutable first300-step production convergence checks

For each newly started fineN400/N800 reference run, the log was copied only up
to the observed first iteration of step301. The unchanged
`audit_svfsi_convergence.analyze(work, prefix_log, last_step=300)` then verified
all600 final equation rows. Both passed, no iteration-cap rows; maximum printed
ratios FS5.0e-11/MS9.9e-11 for N400 and FS3.5e-11/MS9.9e-11 for N800.

These are finite immutable prefixes, not full-run or physics qualification.
The full producer logs continue unchanged and will be checked after completion.
