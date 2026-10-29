#pragma once
/** @file
 * @brief 独立静态高斯积分规则。所有权重归一化为和为 1，调用者乘物理体积。
 * points 数组在 C++17 编译期生成，无运行时初始化或堆分配。
 */
#include "eonsim/discretization.hpp"
namespace eonsim {
/// [0,1] 上 Gauss-Legendre，模板参数是点数而非精确阶数；仅提供已实现的特化。
template<int Points> struct GaussLegendre;
template<> struct GaussLegendre<1> {
    inline static constexpr std::array<double,1> points{.5},weights{1.};
};
template<> struct GaussLegendre<2> {
    inline static constexpr std::array<double,2> points{.21132486540518711775,.78867513459481288225},weights{.5,.5};
};
template<> struct GaussLegendre<3> {
    inline static constexpr std::array<double,3> points{.11270166537925831148,.5,.88729833462074168852};
    inline static constexpr std::array<double,3> weights{5./18,4./9,5./18};
};
template<> struct GaussLegendre<4> {
    inline static constexpr std::array<double,4> points{.06943184420297371,.33000947820757187,.6699905217924281,.9305681557970262};
    inline static constexpr std::array<double,4> weights{.17392742256872692,.32607257743127307,.32607257743127307,.17392742256872692};
};
template<class Element> struct QuadraturePoint {
    typename Element::template Nodal<double> shape{}; // 重心坐标，也是 P1 形函数值
    double weight=0;
};
/// 对称单纯形积分：当前提供 Tet4 的四点二阶精确规则。
template<class Element,int Points> struct SimplexGauss;
template<> struct SimplexGauss<Tri3Topology,3> {
    using Element=Tri3Topology;
    static constexpr int size=3, exact_degree=2;
    inline static constexpr auto points=[] {
        std::array<QuadraturePoint<Element>,size> rule{};
        for(int q=0;q<size;++q) {
            for(int a=0;a<Element::nodes;++a) rule[q].shape[a]=a==q?2./3:1./6;
            rule[q].weight=1.0/size;
        }
        return rule;
    }();
};
template<> struct SimplexGauss<Tet4Topology,4> {
    using Element=Tet4Topology;
    static constexpr int size=4, exact_degree=2;
    inline static constexpr auto points=[] {
        std::array<QuadraturePoint<Element>,size> rule{};
        for(int q=0;q<size;++q) {
            for(int a=0;a<Element::nodes;++a) rule[q].shape[a]=a==q?.5854101966249685:.1381966011250105;
            rule[q].weight=1.0/size;
        }
        return rule;
    }();
};
/// Gauss-Legendre 张量积经 Duffy 映射到四面体；阶数包含映射 Jacobian 的影响。
template<int PointsPerAxis> struct TetDuffyGauss {
    static_assert(PointsPerAxis >= 2, "Duffy Jacobian requires at least two Gauss points per axis");
    using Element=Tet4Topology;
    using Line=GaussLegendre<PointsPerAxis>;
    static constexpr int size=PointsPerAxis*PointsPerAxis*PointsPerAxis;
    static constexpr int exact_degree=2*PointsPerAxis-3;
    inline static constexpr auto points=[] {
        std::array<QuadraturePoint<Element>,size> rule{};
        int q=0;
        for(int i=0;i<PointsPerAxis;++i) for(int j=0;j<PointsPerAxis;++j) for(int k=0;k<PointsPerAxis;++k) {
            const double r=Line::points[i],s=Line::points[j],t=Line::points[k];
            rule[q].shape={(1-r)*(1-s)*(1-t),r,(1-r)*s,(1-r)*(1-s)*t};
            rule[q++].weight=Element::jacobian_scale*Line::weights[i]*Line::weights[j]*Line::weights[k]*(1-r)*(1-r)*(1-s);
        }
        return rule;
    }();
};
using BoundaryQuadrature=SimplexGauss<Tri3Topology,3>;
using FluidQuadrature=SimplexGauss<Tet4Topology,4>;
using ErrorQuadrature=TetDuffyGauss<4>;
}
