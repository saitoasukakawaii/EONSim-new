# Time-dependent downstream pressure in an RCR terminal

Each terminal may specify its own time-dependent reservoir pressure downstream of the distal resistance. Positive Q leaves the 3D domain. The capacitor stores the absolute node pressure relative to a fixed reference. The equations are

$$
C\dot p_c=Q-(p_c-p_d(t))/R_d,\qquad p_b=p_c+R_pQ.
$$

The optional profile uses the existing pressure waveform in physical solver time. A positive ramp duration multiplies both mean and sinusoid by the smooth quintic startup. If an initial capacitor pressure is omitted it defaults to the *initial value* of the downstream reservoir. At every Newton evaluation the terminal uses the forcing at the integration stage. The pressure history includes the applied stage and endpoint reservoir values for each driven tag. A checkpoint identifies the waveform parameters and tag so a mid-cycle restart can resume at the same physical phase.

```yaml
rcr_outlet:
  tag: 2
  proximal_resistance: 3
  distal_resistance: 8
  compliance: 0.025
  distal_pressure: 0.08
  distal_pressure_time: {amplitude: 0.07, period: 1.0}
```

## Rigid-tube measurement at two independent frequencies

A clamped 3D slab receives inlet flow 0.004 sin(4πt) and reservoir pressure 0.08 + 0.07 sin(2πt), in native SI units. These independent inputs give distinct frequencies at the same fluid boundary. The analytical pressure transfer from the reservoir is H = 1/(1+iωR_d C), and the flow-to-pressure impedance is Z = R_p + R_d H. At 1 Hz the reservoir contributes a pressure gain of 0.62268 with a phase lag of 51.49°. At 2 Hz the flow-to-pressure impedance is 4.09341 − 2.74804i Pa·s/m³. The initial capacitor pressure is set to its periodic value. Maximum errors use all accepted endpoint pressures over one second, and Fourier errors compare each resolved frequency separately.

| Integrator | Maximum pressure error at 64, 128, 256 steps (Pa) | Last observed order | Complex reservoir-transfer error at 256 steps | Complex flow-impedance error at 256 steps |
|---|---|---:|---:|---:|
| Backward Euler | 2.306e−3, 1.165e−3, 5.859e−4 | 0.992 | 0.729% | 0.973% |
| BDF2 | 3.992e−4, 1.154e−4, 3.140e−5 | 1.878 | 0.0133% | 0.0413% |
| Generalized-alpha | 3.286e−4, 8.969e−5, 2.374e−5 | 1.918 | 0.0107% | 0.0183% |

The original 32–64-step BDF2 pressure refinement gave order 1.597, with only 16 steps per cycle at the higher inlet frequency on the coarse grid. The three resolutions in the table give 32, 64 and 128 steps per inlet cycle. The largest stage circuit defect among the finest-grid histories was 3.99e−17.

## Unequal downstream pressures at a junction

Two daughter reservoirs use different means, amplitudes and periods. One daughter expands in its fixed axial plane and the other remains clamped. The two-rank field differs from the one-rank field by at most 8.77e−13 in native nodal units. Reordering the two input tags gave identical restarted fields. A checkpoint taken without diagnostics during the startup ramp reproduced the subsequent port histories within 1.39e−17. In a separate expanding tube, three rejected trials reduced an attempted step from 0.1 s to 0.0125 s. Explicit replay of that accepted step recovered both fields and pressure exactly. [Measured responses and restart differences](reservoir-pressure.json) · [Physical test and accepted-step audit](../../../../tests/verify_fsi_reservoir.py)


## Sampled distal pressure and sampled inflow

A tagged fluid pressure, the FSI prescribed end pressure, and each RCR reservoir can use a periodic table of **pressure increments in Pa**. The scalar pressure supplies the datum. Each pair contains phase time in seconds and the pressure increment at that time. Linear interpolation supplies intermediate values. A positive ramp duration multiplies the sum of the datum and interpolated value. Canonical closure makes an explicitly repeated first value at the end of the period equivalent to omitting that final row. The existing inlet table specifies signed flow in m³/s.

```yaml
distal_pressure: 0.04
distal_pressure_time:
  period: 1.0
  offset_samples: [[0.0, 0.01], [0.125, 0.08], [0.375, -0.026], [0.75, 0.023]]
```

With this profile the initial reservoir pressure is 0.05 Pa and the first peak is 0.12 Pa. The clamped 3D tube also receives a non-sinusoidal inlet with four flow knots per second. The solution for the capacitor on each interval between consecutive knots is explicit. Write $g(t)=p_d(t)+R_d Q(t)$, its constant slope on the interval as $m$, and $T_c=R_d C$. For an interval of length $h$,

$$
p_c(t+h)=p_c(t)+(1-e^{-h/T_c})[g(t)-p_c(t)]+m[h-T_c(1-e^{-h/T_c})].
$$

The periodic fixed point of this recurrence gives $p_c(0)=0.0559842260$ Pa. Adding $R_p Q$ gives the independently predicted fluid boundary pressure throughout the cycle. The maximum errors cover every accepted endpoint.

| Time integrator | Maximum pressure error at 32 / 64 / 128 steps, Pa | Last observed order |
|---|---|---:|
| Backward Euler | 3.169e−3 / 1.644e−3 / 8.379e−4 | 0.972 |
| BDF2 | 1.421e−3 / 4.335e−4 / 1.240e−4 | 1.806 |
| Generalized-alpha | 1.245e−3 / 3.515e−4 / 9.553e−5 | 1.879 |

A separate two-rank restart at 0.244 s falls between pressure knots. Explicit and implicit periodic closure reproduced the subsequent capacitor history and node fields exactly. Changing one interior ordinate was detected on restart. Direct pressure loading on fixed fluid and elastic FSI faces is covered by two additional physical regressions. [Full measurements](sampled-pressure.json) · [Sampled RCR and inlet](../../../../tests/verify_fsi_reservoir.py) · [Fixed fluid](../../../../tests/verify_womersley.py) · [Moving-domain FSI](../../../../tests/verify_fsi_pressure.py)
