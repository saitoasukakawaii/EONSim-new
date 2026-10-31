#include "eonsim/element2d.hpp"
#include "eonsim/quadrature.hpp"
#include <iostream>
int main() {
    try {
        const std::array<eonsim::Point,4> square{{{0,0,0},{1,0,0},{1,1,0},{0,1,0}}};
        double mass[4][4]{},stiffness[4][4]{};
        for(int i=0;i<4;++i)for(int j=0;j<4;++j) {
            const auto q=eonsim::map2d(square,4,eonsim::GaussLegendre<4>::points[i],eonsim::GaussLegendre<4>::points[j]);
            const double w=eonsim::GaussLegendre<4>::weights[i]*eonsim::GaussLegendre<4>::weights[j]*q.determinant;
            for(int a=0;a<4;++a)for(int b=0;b<4;++b) {
                mass[a][b]+=w*q.shape[a]*q.shape[b];
                stiffness[a][b]+=w*(q.gradient[a][0]*q.gradient[b][0]+q.gradient[a][1]*q.gradient[b][1]);
            }
        }
        for(int a=0;a<4;++a)for(int b=0;b<4;++b) {
            const bool opposite=(a+2)%4==b;
            const double m=a==b?1./9:opposite?1./36:1./18,k=a==b?2./3:opposite?-1./3:-1./6;
            if(std::abs(mass[a][b]-m)>2e-15||std::abs(stiffness[a][b]-k)>2e-15)throw std::runtime_error("Q1 exact mass/stiffness mismatch");
        }
        // A folded quadrilateral can have a positive center determinant.
        auto folded=square;folded[2]={.2,.2,0};
        (void)eonsim::map2d(folded,4,.5,.5);
        bool rejected=false;try {eonsim::validate2d(folded,4);}catch(const std::runtime_error&){rejected=true;}
        if(!rejected)throw std::runtime_error("Corner inversion not detected");
        const std::array<eonsim::Point,4> triangle{{{1,2,0},{3,2,0},{1,5,0},{}}};
        const auto t=eonsim::map2d(triangle,3,.2,.3);
        if(std::abs(t.determinant-6)>1e-15||std::abs(t.gradient[1][0]-.5)>1e-15||std::abs(t.gradient[2][1]-1./3)>1e-15)throw std::runtime_error("P1 map oracle mismatch");
        std::cout << "Tri3 map, Quad4 exact matrices and corner inversion passed\n";
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
