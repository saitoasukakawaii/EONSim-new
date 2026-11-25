/** 独立解析预期：不等距二次多项式导数与指数衰减时间阶。 */
#include "eonsim/time_integration.hpp"
#include "eonsim/time_step.hpp"
#include "eonsim/fsi.hpp"
#include <iostream>
using namespace eonsim;
int main() {
    // A short capacitor step on top of a large pressure offset still has a finite rate.
    const RcrOutlet outlet{2,4.,16.,.01,100000.,100000.};
    for(double dt:{1e-12,1e-6,.1,1e4}) for(double q:{-1.,0.,1.}) {
        const double exact_rate=outlet.distal_resistance*q/(outlet.distal_resistance*outlet.compliance+dt);
        const double face=outlet.distal_pressure+dt*exact_rate+outlet.proximal_resistance*q;
        const RcrStage stage(outlet,outlet.initial_capacitor_pressure,dt);
        if(std::abs(stage.flow(face)-q)>4e-12 || std::abs(stage.capacitor_rate(face)-exact_rate)>4e-10
            || std::abs(stage.capacitor_pressure(face)-outlet.distal_pressure-dt*exact_rate)>2e-11)
            throw std::runtime_error("RCR pressure/flow/rate on a small step is inconsistent");
    }
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
