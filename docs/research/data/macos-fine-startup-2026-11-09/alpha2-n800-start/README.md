# Fresh alpha2 time-step control (running)

Session45315 starts S96 level1 alpha2 N800 from zero, six cycles with two warmup
cycles, all accepted phases thereafter. It uses the same previously checked
binary, serial MUMPS/LU32/chord and default stabilization as the N400 target.
The wrapper freezes source/proof hashes and actual command. Process-group RSS
limit6GiB, free-disk floor20GiB, timeout24h. Resource review observed11 numerical
processes before launch and about13GiB combined resident use; the extra job is
single-threaded. This is execution authorization, not physical qualification.

On actual completion, analyze all analytic/periodic gates then compare coarse
N400, fineN400, fineN800 using audit-womersley-budget.py. No partial result or
older raw data substitutes for this fresh time-control trajectory.
