#include "eonsim/quadrature.hpp"
#include <cmath>
#include <cstdint>
#include <iostream>
#include <stdexcept>
using namespace eonsim;
namespace {
void close(double actual,double expected) {
    if(std::abs(actual-expected)>2e-13) throw std::runtime_error("Quadrature moment mismatch");
}
double factorial(int n) { double result=1; for(int i=2;i<=n;++i) result*=i; return result; }
template<int N> void line_moments() {
    for(int degree=0;degree<2*N;++degree) {
        double sum=0;
        for(int q=0;q<N;++q) sum+=GaussLegendre<N>::weights[q]*std::pow(GaussLegendre<N>::points[q],degree);
        close(sum,1.0/(degree+1));
    }
}
template<class Rule> void simplex_moments() {
    for(const auto& q:Rule::points) {
        double sum=0;
        if(q.weight<=0) throw std::runtime_error("Nonpositive integration weight");
        for(double x:q.shape) { if(x<0||x>1) throw std::runtime_error("Point outside simplex"); sum+=x; }
        close(sum,1);
    }
    // Independent analytic normalized barycentric moment: 3! prod(alpha!)/(3+|alpha|)!.
    for(int a=0;a<=Rule::exact_degree;++a)
    for(int b=0;b<=Rule::exact_degree-a;++b)
    for(int c=0;c<=Rule::exact_degree-a-b;++c)
    for(int d=0;d<=Rule::exact_degree-a-b-c;++d) {
        double sum=0;
        for(const auto& q:Rule::points)
            sum+=q.weight*std::pow(q.shape[0],a)*std::pow(q.shape[1],b)*std::pow(q.shape[2],c)*std::pow(q.shape[3],d);
        close(sum,6*factorial(a)*factorial(b)*factorial(c)*factorial(d)/factorial(3+a+b+c+d));
    }
}
}
int main() {
    static_assert(Tet4Flow::dof(std::int64_t{1}<<32,0)==(std::int64_t{1}<<34), "Global index must not narrow");
    static_assert(NodalLayout<Simplex<2>,2>::dofs==6, "Layout derives topology and components independently");
    try {
        line_moments<1>(); line_moments<2>(); line_moments<3>(); line_moments<4>();
        simplex_moments<FluidQuadrature>();
        simplex_moments<TetDuffyGauss<2>>(); simplex_moments<TetDuffyGauss<3>>(); simplex_moments<ErrorQuadrature>();
        for(int a=0;a<Tet4Topology::nodes;++a) for(int b=0;b<Tet4Topology::nodes;++b) {
            double mass=0; for(const auto& q:FluidQuadrature::points) mass+=q.weight*q.shape[a]*q.shape[b];
            close(mass,Tet4Topology::mass_weight(a,b));
        }
    } catch(const std::exception& error) { std::cerr<<error.what()<<'\n'; return 1; }
    std::cout<<"Static Gauss and simplex polynomial moments passed\n";
}
