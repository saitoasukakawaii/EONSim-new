#pragma once
/** @file
 * @brief 可压缩 Neo-Hookean 的参考构形应力与一致材料切线。 */
#include "eonsim/discretization.hpp"
namespace eonsim {
template<int Dimension> struct HyperelasticResponseData {
    using Space=CartesianSpace<Dimension>;
    double energy=0,jacobian=1;
    typename Space::template Tensor<double> first_piola{},cauchy{};
    std::array<double,Space::tangent_size> tangent{};
};
using HyperelasticResponse=HyperelasticResponseData<Space3::dimension>;
/** F/应力 row-major，切线 A[(iJ)*9+kL]=dP_iJ/dF_kL。
 * W=mu/2*(tr(F^T F)-3)-mu*ln(J)+lambda/2*ln(J)^2，参考体积能量密度。
 * Cauchy=PF^T/J；J<=0 或非有限输入失败，无历史或通信。
 */
HyperelasticResponse neo_hookean(const Space3::Tensor<double>& F,double young,double poisson);
}
