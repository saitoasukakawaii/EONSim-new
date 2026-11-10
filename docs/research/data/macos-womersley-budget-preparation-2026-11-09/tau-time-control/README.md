# Fresh alpha1 stabilization-time control (running)

Original acceptance explicitly requires separating default stabilization's
integration-time dependence from time-discretization effects. Session36987
computes alpha1 S96level1 N800 six cycles from zero with tau time scale
(2/3)*(2pi/400)=0.010471975511965976, the uniform BDF2 effective time of
N400. The actual integration remainsN800 and convective/geometric tau terms
remain dynamic: this is not a constant-full-tau study. The first BE startup
also uses the explicit override; two full warmup cycles and periodic gates
are still required. No default production run was modified.

The same verified binary/serial MUMPS/LU32/chord path and process-group6GiB,
free-disk20GiB bounds apply. No result or adoption claim. After full completion,
compare actual cycle fields N400default→N800fixedtime and N800fixedtime→
N800default at matched phases. Use field differences, not scalar error norm
subtraction; do not infer additive scalar norms. The original default family
must independently pass its own10% budgets. Alpha2 counterpart still pending
capacity and this first control's validation. All raw data are freshly computed.
