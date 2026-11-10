# Coarse N800 full reference convergence failure

Solver exit0 after25600 steps; controller95639 exit1 after full independent
convergence audit. All51200 final equation rows were read. No iteration caps,
FS max9.8e-11, but all25600 MS rows fail strict1e-10 relative evidence
(maxratio1). No completion receipt or eligible numerical budget.

Pinned MOD.f defines equation absTol1e-15. PIC.f tests its saved initial iNorm
against that threshold as an alternate stop branch. Actual coarse N800 native
saved MS norm is1.8580032716317855e-16, while coarse N400 is2.608465364e-15.
Thus the original N800 run can stop its mesh equation without relative
convergence. The linear Absolute tolerance1e-26 is a different setting and
cannot fix this branch. The fixed source has no input reader for equation
absTol. Source excerpts/hashes and actual saved values are included.

Full convergence report is losslessly gzip-compressed and byte-readback verified;
summary includes its raw and compressed hashes. All raw trajectory/checkpoints
remain locally. Do not promote these fields or weaken the relative gate.
A valid remedy must preserve the intended physical comparison and be independently
verified; none adopted yet. Fine N800 iteration-cap failure is a separate
observed issue. Other studies continue; no push/PR.
