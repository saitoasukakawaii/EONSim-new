#include "eonsim/motion.hpp"
#include "eonsim/tet4.hpp"
#include "eonsim/field_layout.hpp"
#include <cmath>
#include <stdexcept>
namespace eonsim {
namespace {
void validate(const RigidParameters& p,double dt) {
    if(!(p.mass>0 && p.damping>=0 && p.stiffness>=0 && dt>0) ||
       !std::isfinite(p.mass+p.damping+p.stiffness+dt)) throw std::runtime_error("Invalid rigid parameters");
}
}
double rigid_residual(const RigidParameters& p,const RigidState& old,double dt,double v,double force) {
    validate(p,dt);
    return p.mass*(v-old.velocity)/dt+p.damping*v+p.stiffness*(old.position+dt*v)-force;
}
RigidState rigid_step(const RigidParameters& p,const RigidState& old,double dt,double force) {
    validate(p,dt);
    const double v=(force+p.mass*old.velocity/dt-p.stiffness*old.position)/(p.mass/dt+p.damping+dt*p.stiffness);
    if(!std::isfinite(v)) throw std::runtime_error("Nonfinite rigid state");
    return {old.position+dt*v,v};
}
std::vector<double> extend_mesh(MPI_Comm comm,const MeshPartition& mesh,
    const std::vector<PetscInt>& dofs,const std::vector<double>& prescribed,const SolverConfig& solver)
{
    const auto layout=make_field_layout(mesh,3,{{"mesh",{0,1,2}}});
    LinearSystem system(comm,layout);
    for(const auto& cell:mesh.cells) {
        std::array<Point,4> xyz; std::array<PetscInt,12> ids;
        for(int a=0;a<4;++a) {
            xyz[a]=mesh.nodes[cell.nodes[a]].position;
            for(int c=0;c<3;++c) ids[3*a+c]=layout.local_to_global[3*cell.nodes[a]+c];
        }
        const auto scalar=poisson_element(tet4_geometry(xyz),1,0);
        std::array<double,144> k{}; std::array<double,12> load{};
        for(int a=0;a<4;++a) for(int b=0;b<4;++b) for(int c=0;c<3;++c) k[(3*a+c)*12+3*b+c]=scalar.stiffness[4*a+b];
        system.add(12,ids.data(),k.data(),load.data());
    }
    system.constrain(dofs,prescribed);
    return system.solve(solver,false).values;
}
}
