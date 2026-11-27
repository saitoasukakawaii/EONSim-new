#pragma once
/** @file Small SoA arithmetic pack for independent fluid/solid element actions.
 * Each lane belongs to one cell. No reductions or reordering within a cell;
 * no fast-math requirement, MPI, PETSc or allocation in arithmetic operations.
 */
#include <array>
#include <cstddef>
#if defined(EONSIM_ELEMENT_SIMD) && EONSIM_ELEMENT_SIMD && defined(_OPENMP)
#define EONSIM_ACTION_SIMD _Pragma("omp simd")
#else
#define EONSIM_ACTION_SIMD
#endif
namespace eonsim {
struct alignas(32) ActionLanes {
    static constexpr std::size_t width=4;
    std::array<double,width> values{};
    ActionLanes()=default;
    ActionLanes(double value) { values.fill(value); }
    friend ActionLanes operator+(const ActionLanes& a,const ActionLanes& b) {
        ActionLanes out;
        EONSIM_ACTION_SIMD
        for(std::size_t i=0;i<width;++i) out.values[i]=a.values[i]+b.values[i];
        return out;
    }
    friend ActionLanes operator-(const ActionLanes& a,const ActionLanes& b) {
        ActionLanes out;
        EONSIM_ACTION_SIMD
        for(std::size_t i=0;i<width;++i) out.values[i]=a.values[i]-b.values[i];
        return out;
    }
    friend ActionLanes operator*(const ActionLanes& a,const ActionLanes& b) {
        ActionLanes out;
        EONSIM_ACTION_SIMD
        for(std::size_t i=0;i<width;++i) out.values[i]=a.values[i]*b.values[i];
        return out;
    }
    friend ActionLanes operator/(const ActionLanes& a,const ActionLanes& b) {
        ActionLanes out;
        EONSIM_ACTION_SIMD
        for(std::size_t i=0;i<width;++i) out.values[i]=a.values[i]/b.values[i];
        return out;
    }
    ActionLanes& operator+=(const ActionLanes& b) {
        EONSIM_ACTION_SIMD
        for(std::size_t i=0;i<width;++i) values[i]+=b.values[i];
        return *this;
    }
    ActionLanes& operator-=(const ActionLanes& b) {
        EONSIM_ACTION_SIMD
        for(std::size_t i=0;i<width;++i) values[i]-=b.values[i];
        return *this;
    }
};
}
#undef EONSIM_ACTION_SIMD
