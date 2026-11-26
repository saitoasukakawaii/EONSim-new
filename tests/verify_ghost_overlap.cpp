/** Owned/halo assembly: exact coupled solution, remote contributions and drained failures. */
#include "eonsim/nonlinear_system.hpp"
#include "eonsim/time_step.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>

using namespace eonsim;
namespace {
void require(bool condition,const char* message) { if(!condition) throw std::runtime_error(message); }

void verify(MPI_Comm comm,bool coo,bool empty_owner)
{
    int rank=0,ranks=0;
    MPI_Comm_rank(comm,&rank);MPI_Comm_size(comm,&ranks);
    AlgebraLayout layout;
    layout.global=4;
    layout.owned=empty_owner?(rank==0?4:0):4/ranks;
    layout.begin=empty_owner?(rank==0?0:4):rank*layout.owned;
    auto& field=layout.fields["state"]; // Empty ranks retain the same field schema.
    for(PetscInt row=layout.begin;row<layout.begin+layout.owned;++row) {
        layout.local_to_global.push_back(row);field.push_back(row);
    }
    for(PetscInt row=0;row<4;++row)
        if(row<layout.begin||row>=layout.begin+layout.owned) layout.local_to_global.push_back(row);
    layout.diagonal.assign(layout.owned,layout.owned);
    layout.off_diagonal.assign(layout.owned,4-layout.owned);
    std::array<PetscInt,4> index{};
    for(std::size_t i=0;i<layout.local_to_global.size();++i) index[layout.local_to_global[i]]=i;
    std::vector<PetscInt> edges;
    for(PetscInt edge=0;edge<4;++edge) if(edge%ranks==rank) edges.push_back(edge);

    // The local diagonal belongs to the owned phase. A separately partitioned
    // ring edge supplies both endpoint rows in the halo phase, including remote
    // rows and a rank that owns no equations but still produces contributions.
    NonlinearSystem system(comm,layout);
    if(coo) {
        std::vector<PetscInt> residual_rows=field,matrix_rows=field,matrix_columns=field;
        for(PetscInt edge:edges) {
            const PetscInt next=(edge+1)%4;
            residual_rows.insert(residual_rows.end(),{edge,next});
            matrix_rows.insert(matrix_rows.end(),{edge,edge,next,next});
            matrix_columns.insert(matrix_columns.end(),{edge,next,edge,next});
        }
        system.set_jacobian_coo(matrix_rows,matrix_columns);
        system.set_residual_coo(residual_rows);
    }
    auto* residual_values=system.residual_coo_values();
    auto* matrix_values=system.jacobian_coo_values();
    int failure=0,failure_phase=0;
    bool failure_jacobian=false;
    double shift=0;
    int owned_calls=0,halo_calls=0,fallback_calls=0;
    const auto target=[&](PetscInt row) {return row+1.+shift;};
    const auto inject=[&](int phase,Mat j) {
        if(!failure||phase!=failure_phase||bool(j)!=failure_jacobian||rank!=ranks-1) return;
        const std::string detail="intentional overlap failure phase="+std::to_string(phase);
        if(failure==1) throw StepRejected(detail);
        throw std::runtime_error(detail);
    };
    const auto owned=[&](const std::vector<double>& x,Vec r,Mat j) {
        ++owned_calls;
        for(PetscInt local=0;local<layout.owned;++local) {
            const PetscInt row=layout.begin+local;
            const double value=x[local],exact=target(row);
            const double residual=4*(value-exact)+.05*(value*value-exact*exact)+(row==3?10:0);
            const double tangent=4+.1*value;
            if(coo) {
                residual_values[local]=residual;
                if(j) matrix_values[local]=tangent;
            } else {
                EONSIM_PETSC(VecSetValue(r,row,residual,ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValue(j,row,row,tangent,ADD_VALUES));
            }
        }
        inject(0,j);
    };
    const auto halo=[&](const std::vector<double>& x,Vec r,Mat j) {
        ++halo_calls;
        for(std::size_t e=0;e<edges.size();++e) {
            const PetscInt row=edges[e],next=(row+1)%4;
            const double weight=.2*(row+1);
            const double difference=weight*(x[index[row]]-x[index[next]]-target(row)+target(next));
            const PetscInt rows[]{row,next};
            const double residual[]{difference,-difference};
            const double tangent[]{weight,-weight,-weight,weight};
            if(coo) {
                std::copy(residual,residual+2,residual_values+layout.owned+2*e);
                if(j) std::copy(tangent,tangent+4,matrix_values+layout.owned+4*e);
            } else {
                EONSIM_PETSC(VecSetValues(r,2,rows,residual,ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValues(j,2,rows,2,rows,tangent,ADD_VALUES));
            }
        }
        inject(1,j);
    };
    const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
        ++fallback_calls;owned(x,r,j);halo(x,r,j);
    };
    NonlinearAssemblyPhases phases;
    phases.owned=owned;phases.halo=halo;
    SolverConfig config;
    config.absolute_tolerance=1e-11;config.relative_tolerance=0;
    std::vector<PetscInt> constrained;
    if(3>=layout.begin&&3<layout.begin+layout.owned) constrained.push_back(3);
    const auto run=[&](bool split) {
        // Ghost initial entries are deliberately unrelated to owners. The
        // current exchange, including every later Newton update, is essential.
        std::vector<double> initial(4,-1e90);
        std::fill_n(initial.begin(),layout.owned,0.);
        const std::vector<double> prescribed(constrained.size(),target(3));
        return system.solve(config,initial,constrained,prescribed,assemble,
                            split?phases:NonlinearAssemblyPhases{});
    };
    const auto check=[&](const NonlinearResult& result) {
        for(PetscInt row=0;row<4;++row) {
            require(std::abs(result.values[index[row]]-target(row))<2e-11,
                    "Overlapped solve disagrees with the exact coupled solution");
            require(std::abs(result.raw_residual[index[row]]-(row==3?10:0))<1e-10,
                    "Overlapped remote contributions or raw reaction were lost");
        }
        require(result.field_residuals.size()==1,"Unexpected overlap field schema");
        const auto& norm=result.field_residuals.front();
        require(norm.equation_rows==3&&norm.constraint_rows==1&&norm.constraint_max==0,
                "Empty owners or constraints changed global row counts");
        std::array<double,4> initial{},raw{};
        initial[3]=target(3);
        for(PetscInt row=0;row<4;++row)
            raw[row]=4*(initial[row]-target(row))+.05*(initial[row]*initial[row]-target(row)*target(row));
        for(PetscInt edge=0;edge<4;++edge) {
            const PetscInt next=(edge+1)%4;
            const double value=.2*(edge+1)*(initial[edge]-initial[next]-target(edge)+target(next));
            raw[edge]+=value;raw[next]-=value;
        }
        const double expected=std::hypot(raw[0],raw[1],raw[2])/std::sqrt(3.);
        require(std::abs(norm.initial_rms-expected)<2e-13*expected,
                "Fused field norm differs from independently scaled RMS");
    };

    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-nonlinear_fused_reductions","false"));
    const auto reference=run(false);check(reference);
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-nonlinear_fused_reductions","true"));
    const int saved_fallback=fallback_calls;
    const auto overlapped=run(true);check(overlapped);
    require(fallback_calls==saved_fallback,"Split assembly unexpectedly called the monolithic fallback");
    require(overlapped.iterations==reference.iterations,"Assembly split changed the Newton trajectory");
    require(std::abs(overlapped.field_residuals[0].initial_rms-reference.field_residuals[0].initial_rms)<1e-12,
            "One- and two-collective field norms disagree");
    const int before_owned=owned_calls,before_halo=halo_calls;
    const auto repeated=run(true);check(repeated);
    require(repeated.solver_reused&&owned_calls-before_owned==halo_calls-before_halo,
            "Retained overlap callbacks or paired phase invocation failed");

    // Every failure happens after local writes, while owned-phase failures also
    // have a pending forward exchange. A later call reuses the same matrix,
    // ghost Vec and COO buffers, which detects undrained messages/stashes.
    for(int phase:{0,1}) for(bool jacobian:{false,true}) for(int severity:{1,2}) {
        failure_phase=phase;failure_jacobian=jacobian;failure=severity;
        bool caught=false;
        try {run(true);}
        catch(const StepRejected& e) {
            caught=severity==1&&std::string(e.what()).find("intentional overlap failure")!=std::string::npos;
        }
        catch(const std::runtime_error& e) {
            caught=severity==2&&std::string(e.what()).find("intentional overlap failure")!=std::string::npos;
        }
        require(caught,"Rank-local overlap failure was lost or misclassified");
        failure=0;shift+=.01;
        const auto recovered=run(true);check(recovered);
        require(!recovered.solver_reused,"Failed overlap solve retained its solver session");
    }
    check(run(false));
    // Compare both reduction algorithms on magnitudes whose squares underflow
    // or approach the large end of double. No linear solve is needed here: the
    // deliberately looser acceptance threshold lets us inspect the exact RMS.
    for(double scale:{1e-200,1e150}) {
        std::array<double,2> measured{};
        for(int fused=0;fused<2;++fused) {
            EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-nonlinear_fused_reductions",fused?"true":"false"));
            const std::array<double,4> loads{{scale,3*scale,4*scale,10}};
            const auto constant=[&](const std::vector<double>&,Vec r,Mat j) {
                require(j==nullptr,"Stationary norm check unexpectedly requested a Jacobian");
                for(PetscInt local=0;local<layout.owned;++local) {
                    const PetscInt row=layout.begin+local;
                    if(coo) residual_values[local]=loads[row];
                    else EONSIM_PETSC(VecSetValue(r,row,loads[row],ADD_VALUES));
                }
            };
            auto tolerant=config;tolerant.absolute_tolerance=10*scale;
            const auto result=system.solve(tolerant,std::vector<double>(4,0),constrained,
                                           std::vector<double>(constrained.size(),0),constant);
            const auto& norm=result.field_residuals.front();
            measured[fused]=norm.rms/scale;
            const double expected=std::sqrt(26./3.);
            require(std::abs(measured[fused]-expected)<2e-14,
                    "Scaled field RMS underflowed, overflowed or lost a remote contribution");
            require(norm.initial_rms==norm.rms,"Constant residual RMS changed between evaluations");
        }
        require(std::abs(measured[0]-measured[1])<2e-14,"Fused extreme-magnitude RMS changed");
    }
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-nonlinear_fused_reductions"));
    if(rank==0) std::cout<<"ghost_overlap coo="<<coo<<" empty_owner="<<empty_owner
                        <<" ranks="<<ranks<<" passed\n";
}
}

int main(int argc,char** argv)
{
    if(PetscInitialize(&argc,&argv,nullptr,nullptr)) return 1;
    try {
        EONSIM_PETSC(PetscPushErrorHandler(PetscReturnErrorHandler,nullptr));
        int ranks=0;MPI_Comm_size(PETSC_COMM_WORLD,&ranks);
        require(ranks==1||ranks==2||ranks==4,"Use 1/2/4 MPI ranks");
        for(bool coo:{false,true}) {
            verify(PETSC_COMM_WORLD,coo,false);
            if(ranks>1) verify(PETSC_COMM_WORLD,coo,true);
        }
        EONSIM_PETSC(PetscPopErrorHandler());
    } catch(const std::exception& e) {
        std::cerr<<e.what()<<'\n';MPI_Abort(PETSC_COMM_WORLD,1);
    }
    return PetscFinalize();
}
