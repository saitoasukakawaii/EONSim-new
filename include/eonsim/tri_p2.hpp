#pragma once
/** @file Straight-triangle P2 field tabulation, independent of geometry and algebra.
 * Local order: vertices 0,1,2, then edge midpoints 01,12,20.
 * Coordinates are reference (r,s); gradients below are reference derivatives.
 */
#include <array>
namespace eonsim {
struct TriP2Tabulation {
    std::array<double,6> value{};
    std::array<std::array<double,2>,6> gradient{};
};
inline TriP2Tabulation tabulate_tri_p2(double r,double s) {
    const std::array<double,3> l{1-r-s,r,s};
    constexpr std::array<std::array<double,2>,3> g{{{-1,-1},{1,0},{0,1}}};
    TriP2Tabulation result;
    for(int i=0;i<3;++i) {
        result.value[i]=l[i]*(2*l[i]-1);
        for(int d=0;d<2;++d)result.gradient[i][d]=(4*l[i]-1)*g[i][d];
        const int j=(i+1)%3;
        result.value[3+i]=4*l[i]*l[j];
        for(int d=0;d<2;++d)result.gradient[3+i][d]=4*(g[i][d]*l[j]+l[i]*g[j][d]);
    }
    return result;
}
}
