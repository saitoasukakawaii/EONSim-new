#pragma once
/** @file @brief 固定宽度前向链式导数；只用于实际单元局部切线，无动态分配。 */
#include <array>
#include <cmath>

// Each derivative lane is independent: there are no reductions or cross-lane
// writes. This directive changes neither accumulation order nor FP semantics.
// Builds without OpenMP retain the same ordinary loops and compiler auto-SIMD.
#if defined(EONSIM_ELEMENT_SIMD) && EONSIM_ELEMENT_SIMD && defined(_OPENMP)
#define EONSIM_DUAL_SIMD _Pragma("omp simd")
#else
#define EONSIM_DUAL_SIMD
#endif

namespace eonsim {
template<int Width> struct Dual {
    static_assert(Width>0,"Dual derivative width must be positive");
    double value=0;
    std::array<double,Width> derivative{};
    Dual()=default;
    Dual(double x):value(x) {}
    friend Dual operator+(const Dual& a,const Dual& b) {
        Dual r(a.value+b.value);
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) r.derivative[i]=a.derivative[i]+b.derivative[i];
        return r;
    }
    friend Dual operator-(const Dual& a,const Dual& b) {
        Dual r(a.value-b.value);
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) r.derivative[i]=a.derivative[i]-b.derivative[i];
        return r;
    }
    friend Dual operator-(const Dual& a) {
        Dual r(0.-a.value);
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) r.derivative[i]=0.-a.derivative[i];
        return r;
    }
    friend Dual operator*(const Dual& a,const Dual& b) {
        Dual r(a.value*b.value);
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) r.derivative[i]=a.derivative[i]*b.value+a.value*b.derivative[i];
        return r;
    }
    friend Dual operator/(const Dual& a,const Dual& b) {
        Dual r(a.value/b.value);
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) r.derivative[i]=(a.derivative[i]-r.value*b.derivative[i])/b.value;
        return r;
    }

    // Passive coefficients are common throughout the fluid/ALE residual. Avoid
    // materializing a zero-filled derivative array for each scalar operand.
    // Retain the original zero products/subtractions: 0*Inf and 0*NaN must still
    // contaminate the derivative, so a nonfinite primal cannot be hidden by an
    // algebraic simplification. No finite-math-only assumptions are required.
    friend Dual operator+(const Dual& a,double b) {
        Dual r(a.value+b);
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) r.derivative[i]=a.derivative[i]+0.;
        return r;
    }
    friend Dual operator+(double a,const Dual& b) {
        Dual r(a+b.value);
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) r.derivative[i]=0.+b.derivative[i];
        return r;
    }
    friend Dual operator-(const Dual& a,double b) {
        Dual r(a.value-b);
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) r.derivative[i]=a.derivative[i]-0.;
        return r;
    }
    friend Dual operator-(double a,const Dual& b) {
        Dual r(a-b.value);
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) r.derivative[i]=0.-b.derivative[i];
        return r;
    }
    friend Dual operator*(const Dual& a,double b) {
        Dual r(a.value*b);
        const double passive=a.value*0.;
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) r.derivative[i]=a.derivative[i]*b+passive;
        return r;
    }
    friend Dual operator*(double a,const Dual& b) {
        Dual r(a*b.value);
        const double passive=0.*b.value;
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) r.derivative[i]=passive+a*b.derivative[i];
        return r;
    }
    friend Dual operator/(const Dual& a,double b) {
        Dual r(a.value/b);
        const double passive=r.value*0.;
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) r.derivative[i]=(a.derivative[i]-passive)/b;
        return r;
    }
    friend Dual operator/(double a,const Dual& b) {
        Dual r(a/b.value);
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) r.derivative[i]=(0.-r.value*b.derivative[i])/b.value;
        return r;
    }
    Dual& operator+=(const Dual& b) {
        value+=b.value;
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) derivative[i]+=b.derivative[i];
        return *this;
    }
    Dual& operator-=(const Dual& b) {
        value-=b.value;
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) derivative[i]-=b.derivative[i];
        return *this;
    }
    Dual& operator+=(double b) {
        value+=b;
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) derivative[i]+=0.;
        return *this;
    }
    Dual& operator-=(double b) {
        value-=b;
        EONSIM_DUAL_SIMD
        for(int i=0;i<Width;++i) derivative[i]-=0.;
        return *this;
    }
};

inline void add_product(double& sum,double a,double b) { sum+=a*b; }
/** Accumulate one product without a temporary derivative vector.
 * The order within every lane is exactly that of sum += a*b. Capturing the
 * primals and updating sum.value last also permits sum to alias either input.
 * This is loop fusion, not a reassociation or a request for fused FP arithmetic.
 */
template<int N> void add_product(Dual<N>& sum,const Dual<N>& a,const Dual<N>& b) {
    const double av=a.value,bv=b.value;
    EONSIM_DUAL_SIMD
    for(int i=0;i<N;++i)
        sum.derivative[i]+=a.derivative[i]*bv+av*b.derivative[i];
    sum.value+=av*bv;
}
template<int N> Dual<N> sqrt(const Dual<N>& x) {
    Dual<N> result(std::sqrt(x.value));
    EONSIM_DUAL_SIMD
    for(int i=0;i<N;++i) result.derivative[i]=x.derivative[i]/(2*result.value);
    return result;
}
inline double primal(double x) { return x; }
template<int N> double primal(const Dual<N>& x) { return x.value; }
}
#undef EONSIM_DUAL_SIMD
