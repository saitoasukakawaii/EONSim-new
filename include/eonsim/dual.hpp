#pragma once
/** @file @brief 固定宽度前向链式导数；只用于实际单元局部切线，无动态分配。 */
#include <array>
namespace eonsim {
template<int Width> struct Dual {
    double value=0;
    std::array<double,Width> derivative{};
    Dual()=default;
    Dual(double x):value(x) {}
    friend Dual operator+(const Dual& a,const Dual& b) { Dual r(a.value+b.value); for(int i=0;i<Width;++i) r.derivative[i]=a.derivative[i]+b.derivative[i]; return r; }
    friend Dual operator-(const Dual& a,const Dual& b) { Dual r(a.value-b.value); for(int i=0;i<Width;++i) r.derivative[i]=a.derivative[i]-b.derivative[i]; return r; }
    friend Dual operator-(const Dual& a) { return Dual{}-a; }
    friend Dual operator*(const Dual& a,const Dual& b) { Dual r(a.value*b.value); for(int i=0;i<Width;++i) r.derivative[i]=a.derivative[i]*b.value+a.value*b.derivative[i]; return r; }
    friend Dual operator/(const Dual& a,const Dual& b) { Dual r(a.value/b.value); for(int i=0;i<Width;++i) r.derivative[i]=(a.derivative[i]-r.value*b.derivative[i])/b.value; return r; }
    Dual& operator+=(const Dual& b) { *this=*this+b; return *this; }
    Dual& operator-=(const Dual& b) { *this=*this-b; return *this; }
};
inline double primal(double x) { return x; }
template<int N> double primal(const Dual<N>& x) { return x.value; }
}
