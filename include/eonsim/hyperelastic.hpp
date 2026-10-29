#pragma once
/** @file
 * @brief 可压缩 Neo-Hookean 的参考构形应力与一致材料切线。 */
#include <array>
namespace eonsim {
struct HyperelasticResponse {
    double energy=0,jacobian=1;
    std::array<double,9> first_piola{},cauchy{};
    std::array<double,81> tangent{};
};
/** F/应力 row-major，切线 A[(iJ)*9+kL]=dP_iJ/dF_kL。
 * W=mu/2*(tr(F^T F)-3)-mu*ln(J)+lambda/2*ln(J)^2，参考体积能量密度。
 * Cauchy=PF^T/J；J<=0 或非有限输入失败，无历史或通信。
 */
HyperelasticResponse neo_hookean(const std::array<double,9>& F,double young,double poisson);
}
