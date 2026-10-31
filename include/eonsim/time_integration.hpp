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
    if(scheme!=TimeScheme::backward_euler&&scheme!=TimeScheme::bdf2) throw std::runtime_error("This derivative map requires BE or BDF2");
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

/** 新时刻权重：x_f=(1-alpha_f)x_n+alpha_f*x_(n+1)。
 * 参数与PETSc v3.23.7 TSALPHA/TSALPHA2一致；不能与Chung原文的旧时刻权重混用。
 * beta只供二阶位移重建。一阶与二阶共享alpha_f，但有各自的alpha_m/gamma及导数历史。
 */
struct AlphaParameters { double alpha_m,alpha_f,gamma,beta; };
inline AlphaParameters alpha_parameters(double rho,bool second_order) {
    if(!std::isfinite(rho)||rho<0||rho>1) throw std::runtime_error("generalized-alpha rho_infinity must be in [0,1]");
    const double am=second_order?(2-rho)/(1+rho):(3-rho)/(2*(1+rho));
    const double af=1/(1+rho),gamma=.5+am-af;
    const double beta=second_order?.25*(1+am-af)*(1+am-af):0;
    return {am,af,gamma,beta};
}
/** stage速度（或一阶状态）为独立未知量。导数评价=(stage-reference)/effective_dt。
 * 二阶位移链系数与惯性effective_dt不同，ALE/结构接口必须使用displacement_dt。
 * 所有方法只计算数值，不推进时钟或提交历史。
 */
struct AlphaStep {
    AlphaParameters p;
    double h;
    AlphaStep(double step,double rho,bool second_order):p(alpha_parameters(rho,second_order)),h(step) {
        if(!(h>0)||!std::isfinite(h)) throw std::runtime_error("Invalid generalized-alpha step");
    }
    double effective_dt() const { return p.alpha_f*p.gamma*h/p.alpha_m; }
    double reference(double accepted,double rate) const {
        return accepted+p.alpha_f*h*(1-p.gamma/p.alpha_m)*rate;
    }
    double endpoint(double accepted,double stage) const { return accepted+(stage-accepted)/p.alpha_f; }
    double endpoint_rate(double accepted,double rate,double stage) const {
        return (stage-accepted)/(p.alpha_f*p.gamma*h)-(1-p.gamma)/p.gamma*rate;
    }
    double displacement_dt() const {
        if(!(p.beta>0)) throw std::runtime_error("Displacement mapping requires second-order alpha parameters");
        return p.beta*h/p.gamma;
    }
    double displacement_reference(double d,double v,double a) const {
        if(!(p.beta>0)) throw std::runtime_error("Displacement mapping requires second-order alpha parameters");
        return d+h*(p.alpha_f-p.beta/p.gamma)*v+p.alpha_f*h*h*(.5-p.beta/p.gamma)*a;
    }
};
}
