#pragma once
/** @file @brief 时间控制与有上限的失败缩步；不持有物理状态。 */
#include "eonsim/config.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <limits>
namespace eonsim {
/// 仅可重试的数值失败；输入/通信/I/O 错误不转换为此类型。
struct StepRejected : std::runtime_error { using std::runtime_error::runtime_error; };
class TimeStepper {
public:
    TimeStepper(double dt,int steps,const TimeControl& options):next_dt(dt),end_(dt*steps),options_(options) {
        if(!(dt>0&&end_>0)||!std::isfinite(end_)) throw std::runtime_error("Invalid final time");
        if(!options_.step_sizes.empty()) next_dt=options_.step_sizes.front();
        for(double event:options_.events) if(event>end_) throw std::runtime_error("Time event exceeds final time");
    }
    int step=0,retries=0;
    double time=0,next_dt;
    double dt() const {
        double h=std::min(next_dt,end_-time);
        for(double event:options_.events) if(event>time+32*std::numeric_limits<double>::epsilon()*end_) { h=std::min(h,event-time); break; }
        return h;
    }
    bool at_event() const {
        for(double event:options_.events) if(std::abs(time-event)<=32*std::numeric_limits<double>::epsilon()*end_) return true;
        return false;
    }
    bool active(int stop_after=0) const { return time<end_-32*std::numeric_limits<double>::epsilon()*end_ && (!stop_after||step<stop_after); }
    void restore(int accepted_step,double accepted_time,double saved_dt) {
        if(accepted_step<0||accepted_time<0||accepted_time>=end_||!(saved_dt>0)||!std::isfinite(accepted_time+saved_dt)) throw std::runtime_error("Invalid restart time or final time already reached");
        step=accepted_step; time=accepted_time; next_dt=saved_dt; time_correction_=0;
    }
    void accept() {
        if(step==std::numeric_limits<int>::max()||!(time+dt()>time)) throw std::runtime_error("Time or step counter cannot advance");
        // Compensated accumulation prevents O(step*epsilon) clock drift from
        // introducing an artificial near-zero final step. Restart resets only
        // this floating-point correction, not the integration history.
        const double increment=dt()-time_correction_;
        const double updated=time+increment;
        time_correction_=(updated-time)-increment;
        time=updated; ++step; retries=0;
        if(!options_.step_sizes.empty()) next_dt=options_.step_sizes[std::min(std::size_t(step),options_.step_sizes.size()-1)];
    }
    void reject(const std::string& reason) {
        const double reduced=dt()*options_.reduction;
        if(retries>=options_.max_retries || reduced<options_.minimum_dt) throw StepRejected("Time-step retries exhausted: "+reason);
        next_dt=reduced; ++retries;
    }
private:
    double end_;
    double time_correction_=0;
    TimeControl options_;
};
}
