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
    const auto layout=make_field_layout(mesh,Tet4Vector::components,{{"mesh",{0,1,2}}});
    LinearSystem system(comm,layout);
    for(const auto& cell:mesh.cells) {
        Tet4Topology::Nodal<Point> xyz; Tet4Vector::State<PetscInt> ids;
        for(int a=0;a<Tet4Topology::nodes;++a) {
            xyz[a]=mesh.nodes[cell.nodes[a]].position;
            for(int c=0;c<Space3::dimension;++c) ids[Tet4Vector::components*a+c]=layout.local_to_global[Tet4Vector::components*cell.nodes[a]+c];
        }
        const auto scalar=poisson_element(tet4_geometry(xyz),1,0);
        Tet4Vector::Matrix<double> k{}; Tet4Vector::State<double> load{};
        for(int a=0;a<Tet4Topology::nodes;++a) for(int b=0;b<Tet4Topology::nodes;++b) for(int c=0;c<Space3::dimension;++c) k[Tet4Vector::matrix(Tet4Vector::dof(a,c),Tet4Vector::dof(b,c))]=scalar.stiffness[Tet4Scalar::matrix(a,b)];
        system.add(Tet4Vector::dofs,ids.data(),k.data(),load.data());
    }
    system.constrain(dofs,prescribed);
    return system.solve(solver,false).values;
}
}
