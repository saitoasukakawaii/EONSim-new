#pragma once
/** @file @brief BE/BDF2 的局部时间导数映射及只在接受后更新的二层历史。 */
#include "eonsim/config.hpp"
#include <cmath>
#include <limits>
#include <stdexcept>
#include <vector>

namespace eonsim {
/** ydot=(y-reference)/effective_dt；运动学 ydot=v 则 y=reference+effective_dt*v。
 * BDF2 使用实际已接受步长，首步BE启动。最大步长比2小于1+sqrt(2)。
 * 系数在每次候选步（包括拒绝重试）重算；对象不推进控制器或修改历史。
 */
struct TimeDerivative {
    double effective_dt=0, older_weight=0;
    int order=1;
    double reference(double accepted,double older) const {
        return older_weight==0?accepted:accepted+older_weight*(accepted-older);
    }
};
inline TimeDerivative time_derivative(TimeScheme scheme,double h,double previous_h) {
    if(!(h>0)||!std::isfinite(h)||previous_h<0||!std::isfinite(previous_h))
        throw std::runtime_error("Invalid integration step/history");
    if(scheme==TimeScheme::backward_euler||previous_h==0) return {h,0,1};
    const double ratio=h/previous_h;
    if(!std::isfinite(ratio)||ratio>2*(1+8*std::numeric_limits<double>::epsilon()))
        throw std::runtime_error("BDF2 step ratio exceeds 2");
    return {h*(1+ratio)/(1+2*ratio),ratio*ratio/(1+2*ratio),2};
}
/** previous 是当前 accepted 之前的状态，previous_dt是到当前accepted的步长。
 * 首步previous_dt=0。commit接收求解前的accepted，仅在所有物理验收通过后调用。
 * 不持有trial或引用；失败评价与拒绝不调用commit。分布式向量保留原owned+ghost顺序。
 */
struct TimeHistory {
    std::vector<double> previous;
    double previous_dt=0;
    explicit TimeHistory(std::size_t size):previous(size,0) {}
    std::vector<double> reference(const std::vector<double>& accepted,const TimeDerivative& derivative) const {
        if(accepted.size()!=previous.size()) throw std::runtime_error("Time history size mismatch");
        auto result=accepted;
        if(derivative.order==2) for(std::size_t i=0;i<result.size();++i)
            result[i]=derivative.reference(accepted[i],previous[i]);
        return result;
    }
    void commit(const std::vector<double>& accepted,double h) {
        if(accepted.size()!=previous.size()||!(h>0)||!std::isfinite(h)) throw std::runtime_error("Invalid accepted time history");
        previous=accepted; previous_dt=h;
    }
};
}
