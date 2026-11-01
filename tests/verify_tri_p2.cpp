#include "eonsim/tri_p2.hpp"
#include "eonsim/quadrature.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
namespace {
void near(double a,double b) {
    if(!std::isfinite(a)||std::abs(a-b)>2e-13)throw std::runtime_error("P2 polynomial reproduction mismatch");
}
double polynomial(int k,double x,double y) {
    switch(k) {case 0:return 1;case 1:return x;case 2:return y;case 3:return x*x;case 4:return x*y;default:return y*y;}
}
}
int main() {
    try {
        constexpr std::array<std::array<double,2>,6> nodes{{{0,0},{1,0},{0,1},{.5,0},{.5,.5},{0,.5}}};
        for(int i=0;i<6;++i) {
            const auto q=eonsim::tabulate_tri_p2(nodes[i][0],nodes[i][1]);
            for(int j=0;j<6;++j)near(q.value[j],i==j?1:0);
        }
        for(int a=0;a<=8;++a)for(int b=0;b<=8-a;++b) {
            const double x=a/8.,y=b/8.;const auto q=eonsim::tabulate_tri_p2(x,y);
            for(int k=0;k<6;++k) {
                double value=0,dx=0,dy=0;
                for(int i=0;i<6;++i) {
                    const auto coefficient=polynomial(k,nodes[i][0],nodes[i][1]);
                    value+=coefficient*q.value[i];dx+=coefficient*q.gradient[i][0];dy+=coefficient*q.gradient[i][1];
                }
                near(value,polynomial(k,x,y));
                near(dx,k==1?1:k==3?2*x:k==4?y:0);
                near(dy,k==2?1:k==4?x:k==5?2*y:0);
            }
            // A shared edge's quadratic trace is invariant under endpoint reversal.
            const auto forward=eonsim::tabulate_tri_p2(x,0),reverse=eonsim::tabulate_tri_p2(1-x,0);
            near(forward.value[0],reverse.value[1]);near(forward.value[3],reverse.value[3]);
            near(forward.value[2],0);near(forward.value[4],0);near(forward.value[5],0);
        }
        // Independent exact reference-triangle stiffness and constant-load integrals.
        const double expected[6][6]={{1,1./6,1./6,-2./3,0,-2./3},{1./6,.5,0,-2./3,0,0},{1./6,0,.5,0,0,-2./3},{-2./3,-2./3,0,8./3,-4./3,0},{0,0,0,-4./3,8./3,-4./3},{-2./3,0,-2./3,0,-4./3,8./3}};
        double stiffness[6][6]{},load[6]{};
        for(int i=0;i<4;++i)for(int j=0;j<4;++j){const double r=eonsim::GaussLegendre<4>::points[i],s=(1-r)*eonsim::GaussLegendre<4>::points[j];
            const double w=(1-r)*eonsim::GaussLegendre<4>::weights[i]*eonsim::GaussLegendre<4>::weights[j];const auto q=eonsim::tabulate_tri_p2(r,s);
            for(int a=0;a<6;++a){load[a]+=w*q.value[a];for(int b=0;b<6;++b)stiffness[a][b]+=w*(q.gradient[a][0]*q.gradient[b][0]+q.gradient[a][1]*q.gradient[b][1]);}}
        for(int a=0;a<6;++a){near(load[a],a<3?0:1./6);for(int b=0;b<6;++b)near(stiffness[a][b],expected[a][b]);}
        std::cout<<"P2 nodal interpolation, six polynomial values/gradients and edge traces passed\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
