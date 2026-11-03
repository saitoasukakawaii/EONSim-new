"""Phase-aligned scalar diagnostics; never a full-field convergence certificate."""
import bisect
import math


def compare_cycles(times, values, period, end, scale, samples=128):
    """Compare adjacent complete cycles using accepted timestamps, without extrapolation.

    scale is a fixed physical oscillation scale, not the (possibly large) mean.
    Linear interpolation requires a separate sampling-error check in studies.
    """
    if not (math.isfinite(period) and period > 0 and math.isfinite(scale) and scale > 0
            and math.isfinite(end) and isinstance(samples, int) and samples >= 4):
        raise ValueError('Invalid cycle definition')
    if len(times) != len(values) or len(times) < 2:
        raise ValueError('Incomplete history')
    if not all(math.isfinite(x) for x in (*times, *values)):
        raise ValueError('Nonfinite history')
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('Accepted times must increase strictly')
    if times[0] > end-2*period or times[-1] < end:
        raise ValueError('Two complete cycles required')

    def sample(t):
        i = bisect.bisect_left(times, t)
        if i < len(times) and times[i] == t:
            return values[i]
        a, b = i-1, i
        w = (t-times[a])/(times[b]-times[a])
        return (1-w)*values[a]+w*values[b]

    # Uniform periodic quadrature excludes the repeated end point.
    old = [sample(end-2*period+j*period/samples) for j in range(samples)]
    new = [sample(end-period+j*period/samples) for j in range(samples)]
    delta = [b-a for a, b in zip(old, new)]
    return dict(relative_rms=math.sqrt(sum(d*d for d in delta)/samples)/scale,
                relative_mean_drift=abs(sum(delta)/samples)/scale,
                relative_max=max(map(abs, delta))/scale,
                mean=sum(new)/samples,
                amplitude=(max(new)-min(new))/2)


def volume_budget(rows, initial_time=0., initial_volume=1., initial_net_flow=0.):
    """Integrate endpoint net flux on actual accepted times (trapezoidal diagnostic).

    This is an independent quadrature budget, not the scheme's stage derivative.
    Initial data must describe the same physical state as the first accepted step.
    """
    if not rows:raise ValueError('Empty mass history')
    previous_time=initial_time;previous_net=initial_net_flow;integral=0.;maximum=0.
    for row in rows:
        t=row['time'];dt=t-previous_time
        net=row['endpoint_inlet_flow']-row['endpoint_outlet_flow']
        if not all(math.isfinite(x) for x in (t,net,row['endpoint_volume'],row['accepted_dt'])):
            raise ValueError('Nonfinite mass history')
        if dt<=0 or abs(dt-row['accepted_dt'])>1e-10*max(1.,abs(t)):
            raise ValueError('Gap or duplicate in accepted mass history')
        integral+=dt*(previous_net+net)/2
        defect=integral-(row['endpoint_volume']-initial_volume)
        maximum=max(maximum,abs(defect));previous_time=t;previous_net=net
    return dict(final_defect=defect,max_absolute_defect=maximum,integrated_net_flow=integral,
                volume_change=rows[-1]['endpoint_volume']-initial_volume)
