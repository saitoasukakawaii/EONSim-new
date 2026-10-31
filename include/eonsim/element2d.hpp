#pragma once
/** @file Tri3/P1 and Quad4/Q1 XY maps. Pure local geometry; no MPI or I/O. */
#include "eonsim/mesh.hpp"
#include <cmath>
#include <stdexcept>
namespace eonsim {
struct Point2DMapping {
    std::array<double,4> shape{};
    std::array<std::array<double,2>,4> gradient{};
    Point position{};
    double determinant=0;
};
/// Reference triangle (0,0),(1,0),(0,1); square (0,0),(1,0),(1,1),(0,1).
/// Jacobian and physical gradients are evaluated at each quadrature point.
inline Point2DMapping map2d(const std::array<Point,4>& x,int vertices,double r,double s) {
    Point2DMapping q; std::array<std::array<double,2>,4> g{};
    if(vertices==3) { q.shape={1-r-s,r,s,0}; g={{{-1,-1},{1,0},{0,1},{0,0}}}; }
    else if(vertices==4) {
        q.shape={(1-r)*(1-s),r*(1-s),r*s,(1-r)*s};
        g={{{s-1,r-1},{1-s,-r},{s,r},{-s,1-r}}};
    } else throw std::runtime_error("Only Tri3/P1 and Quad4/Q1 are supported");
    double a=0,b=0,c=0,d=0;
    for(int i=0;i<vertices;++i) {
        // Subtract the first vertex for translation-invariant Jacobians.
        a+=(x[i][0]-x[0][0])*g[i][0]; b+=(x[i][0]-x[0][0])*g[i][1];
        c+=(x[i][1]-x[0][1])*g[i][0]; d+=(x[i][1]-x[0][1])*g[i][1];
        for(int k=0;k<3;++k) q.position[k]+=q.shape[i]*x[i][k];
    }
    q.determinant=a*d-b*c;
    const double scale=a*a+b*b+c*c+d*d;
    if(!std::isfinite(q.determinant)||!std::isfinite(scale)||q.determinant<=1e-14*scale)
        throw std::runtime_error("Inverted or degenerate 2D element Jacobian");
    for(int i=0;i<vertices;++i) q.gradient[i]={(d*g[i][0]-c*g[i][1])/q.determinant,(-b*g[i][0]+a*g[i][1])/q.determinant};
    return q;
}
/// For a planar bilinear quadrilateral detJ is affine in (r,s), so testing
/// all four corners bounds it over the entire square, not just Gauss points.
inline void validate2d(const std::array<Point,4>& x,int vertices) {
    for(const auto& rs:std::array<std::array<double,2>,4>{{{0,0},{1,0},{1,1},{0,1}}})
        (void)map2d(x,vertices,rs[0],rs[1]);
}
}
