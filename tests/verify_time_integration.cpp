/** 独立解析预期：不等距二次多项式导数与指数衰减时间阶。 */
#include "eonsim/time_integration.hpp"
#include "eonsim/time_step.hpp"
#include <iostream>
using namespace eonsim;
int main() {
    // Reproduce the long production clock: the old continuation resets its
    // correction at11600, then a second restart at12400 used to lose it again.
    const double production_dt=2*std::acos(-1.)/400;
    TimeStepper warmup(production_dt,12800,TimeControl{});
    while(warmup.step<11600) warmup.accept();
    TimeStepper full(production_dt,12800,TimeControl{});
    full.restore(warmup.step,warmup.time,warmup.next_dt,0);
    while(full.step<12400) full.accept();
    if(full.correction()==0) throw std::runtime_error("Clock fixture has no correction to preserve");
    TimeStepper resumed(production_dt,12800,TimeControl{}),lost=resumed;
    resumed.restore(full.step,full.time,full.next_dt,full.correction());
    lost.restore(full.step,full.time,full.next_dt,0);
    bool old_clock_differs=false;
    while(full.active()) {
        if(resumed.step!=full.step||resumed.time!=full.time||resumed.dt()!=full.dt()||
           resumed.next_dt!=full.next_dt||resumed.correction()!=full.correction()||
           resumed.time+(2./3)*resumed.dt()!=full.time+(2./3)*full.dt())
            throw std::runtime_error("Restart changed an accepted or stage clock");
        old_clock_differs=old_clock_differs||lost.time!=full.time||lost.dt()!=full.dt();
        full.accept();resumed.accept();lost.accept();
    }
    if(resumed.active()||resumed.time!=full.time||resumed.correction()!=full.correction()||!old_clock_differs)
        throw std::runtime_error("Long compensated-clock restart regression failed");
    bool invalid_clock=false;
    try {resumed.restore(1,production_dt,production_dt,std::numeric_limits<double>::quiet_NaN());}
    catch(const std::runtime_error&) {invalid_clock=true;}
    if(!invalid_clock||resumed.time!=full.time) throw std::runtime_error("Nonfinite correction corrupted accepted clock");
    for(int steps:{320,10000}) {
        TimeStepper clock(.2/steps,steps,TimeControl{});
        while(clock.active()) clock.accept();
        if(clock.step!=steps||std::abs(clock.time-.2)>2e-16)
            throw std::runtime_error("Roundoff introduced an artificial final step");
    }
    for(double h:{.013,.05,.2}) for(double ratio:{.1,.7,1.,2.}) {
        const double k=h/ratio,t=.4;
        const auto map=time_derivative(TimeScheme::bdf2,h,k);
        const double derivative=((t+h)*(t+h)-map.reference(t*t,(t-k)*(t-k)))/map.effective_dt;
        if(std::abs(derivative-2*(t+h))>2e-12) throw std::runtime_error("Variable-step quadratic derivative is not exact");
    }
    for(auto scheme:{TimeScheme::backward_euler,TimeScheme::bdf2}) {
        double previous_error=0;
        for(int n:{20,40,80}) {
            double y=1,older=1,previous_h=0;
            // Alternating lengths give a variable-step sequence of total length 1.
            for(int step=0;step<n;++step) {
                const double h=(step%2?.8:1.2)/n;
                const auto map=time_derivative(scheme,h,previous_h);
                const double next=map.reference(y,older)/(1+map.effective_dt);
                older=y; y=next; previous_h=h;
            }
            const double error=std::abs(y-std::exp(-1.));
            const double order=previous_error?std::log(previous_error/error)/std::log(2.):0;
            std::cout << "scheme=" << int(scheme) << " n=" << n << " error=" << error << " order=" << order << '\n';
            if(previous_error&&order<(scheme==TimeScheme::bdf2?1.9:.95))
                throw std::runtime_error("Time order below analytic expectation");
            previous_error=error;
        }
    }
    bool rejected=false;
    try { (void)time_derivative(TimeScheme::bdf2,.3,.1); }
    catch(const std::runtime_error&) { rejected=true; }
    if(!rejected) throw std::runtime_error("Unstable BDF2 growth ratio accepted");
    for(double rho:{0.,.5,1.}) for(bool second:{false,true}) {
        double previous_error=0;
        for(int n:{40,80,160}) {
            const double h=1./n;
            double y=1,v=second?0:-1,a=-1;
            for(int step=0;step<n;++step) {
                const AlphaStep map(h,rho,second);
                if(second) {
                    const double vr=map.reference(v,a),dr=map.displacement_reference(y,v,a);
                    const double vf=(vr/map.effective_dt()-dr)/(1/map.effective_dt()+map.displacement_dt());
                    const double df=dr+map.displacement_dt()*vf;
                    a=map.endpoint_rate(v,a,vf); v=map.endpoint(v,vf); y=map.endpoint(y,df);
                } else {
                    const double stage=map.reference(y,v)/(1+map.effective_dt());
                    v=map.endpoint_rate(y,v,stage); y=map.endpoint(y,stage);
                }
            }
            const double error=second?std::hypot(y-std::cos(1.),v+std::sin(1.)):std::abs(y-std::exp(-1.));
            const double order=previous_error?std::log(previous_error/error)/std::log(2.):0;
            std::cout << "alpha second=" << second << " rho=" << rho << " n=" << n << " error=" << error << " order=" << order << '\n';
            if(previous_error&&order<1.9) throw std::runtime_error("generalized-alpha analytic order failed");
            previous_error=error;
        }
    }
}
