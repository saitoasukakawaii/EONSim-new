/** Fixed COO assembly: duplicate/remote rows, empty producers, constraints and failure recovery. */
#include "eonsim/nonlinear_system.hpp"
#include "eonsim/time_step.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
using namespace eonsim;
namespace {
void require(bool condition,const char* message) { if(!condition) throw std::runtime_error(message); }
void verify(MPI_Comm comm)
{
    int rank,ranks; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&ranks);
    require(ranks==1||ranks==2||ranks==4,"Use 1/2/4 ranks");
    AlgebraLayout layout;
    layout.global=4; layout.owned=4/ranks; layout.begin=rank*layout.owned;
    for(PetscInt row=layout.begin;row<layout.begin+layout.owned;++row) {
        layout.local_to_global.push_back(row); layout.fields["state"].push_back(row);
    }
    for(PetscInt row=0;row<4;++row)
        if(row<layout.begin||row>=layout.begin+layout.owned) layout.local_to_global.push_back(row);
    layout.diagonal.assign(layout.owned,layout.owned);
    layout.off_diagonal.assign(layout.owned,4-layout.owned);
    PetscInt local[4];
    for(std::size_t i=0;i<4;++i) local[layout.local_to_global[i]]=static_cast<PetscInt>(i);
    SolverConfig config;
    config.relative_tolerance=1e-12; config.absolute_tolerance=1e-12;
    // shared=false deliberately leaves all other ranks without any cell contribution.
    for(bool shared:{false,true}) {
        const bool producer=shared||rank==ranks-1;
        const double weight=shared?1./ranks:1.;
        std::vector<PetscInt> rows,columns;
        if(producer) for(int copy=0;copy<2;++copy) for(PetscInt row=0;row<4;++row)
            for(PetscInt column=0;column<4;++column) { rows.push_back(row); columns.push_back(column); }
        NonlinearSystem system(comm,layout);
        auto invalid_rows=rows;
        if(rank==ranks-1) invalid_rows[0]=layout.global;
        bool invalid=false;
        try { system.set_jacobian_coo(invalid_rows,columns); }
        catch(const std::runtime_error&) { invalid=true; }
        require(invalid,"A rank-local invalid index did not fail collectively");
        system.set_jacobian_coo(rows,columns);
        auto* buffer=system.jacobian_coo_values();
        PetscObjectId matrix_id=0;
        int phase=0,failure=0;
        const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
            require(buffer==system.jacobian_coo_values(),"COO value storage changed between solves");
            if(j) {
                PetscObjectId id; EONSIM_PETSC(PetscObjectGetId(reinterpret_cast<PetscObject>(j),&id));
                if(matrix_id) require(matrix_id==id,"COO matrix was recreated");
                matrix_id=id;
            }
            double matrix[4][4]={{4,1,0,1},{-1,5,2,0},{0,1,3,1},{2,0,0,2}};
            if(phase) for(int i=0;i<4;++i) for(int k=0;k<4;++k) matrix[i][k]=i==k?i+2.:0.;
            const PetscInt fixed=phase?0:3;
            if(producer) {
                double residual[4]{};
                for(int row=0;row<4;++row) {
                    for(int column=0;column<4;++column)
                        residual[row]+=matrix[row][column]*(x[local[column]]-(column+1));
                    if(row==fixed) residual[row]+=10;
                    residual[row]*=weight;
                }
                const PetscInt ids[]={0,1,2,3};
                EONSIM_PETSC(VecSetValues(r,4,ids,residual,ADD_VALUES));
                if(j) for(std::size_t k=0;k<rows.size();++k) {
                    // Leave the new zero slots unwritten: the driver must clear old off-diagonals.
                    if(matrix[rows[k]][columns[k]]!=0) buffer[k]=.5*weight*matrix[rows[k]][columns[k]];
                }
            }
            // This occurs after remote Vec insertion and local COO packing, but before any COO collective.
            if(j&&rank==ranks-1) {
                if(failure==1) throw StepRejected("injected local COO domain rejection");
                if(failure==2) throw std::runtime_error("injected local COO fatal failure");
            }
        };
        const auto solve=[&] {
            const PetscInt fixed=phase?0:3;
            std::vector<PetscInt> bc; std::vector<double> prescribed;
            if(fixed>=layout.begin&&fixed<layout.begin+layout.owned) { bc.push_back(fixed); prescribed.push_back(fixed+1.); }
            return system.solve(config,std::vector<double>(4,0),bc,prescribed,assemble);
        };
        const auto check=[&](const NonlinearResult& result) {
            for(int row=0;row<4;++row) {
                require(std::abs(result.values[local[row]]-(row+1))<1e-10,"COO solution differs from exact oracle");
                require(std::abs(result.raw_residual[local[row]]-(row==(phase?0:3)?10:0))<1e-10,
                        "COO raw reaction/remote residual differs from oracle");
            }
            require(result.field_residuals.size()==1&&result.field_residuals[0].equation_rows==3,
                    "Constraint polluted physical field acceptance");
        };
        check(solve());
        for(failure=1;failure<=2;++failure) {
            bool caught=false;
            try { solve(); }
            catch(const StepRejected& e) { caught=failure==1&&std::string(e.what()).find("injected local COO")!=std::string::npos; }
            catch(const std::runtime_error& e) { caught=failure==2&&std::string(e.what()).find("injected local COO")!=std::string::npos; }
            require(caught,"Rank-local callback failure was lost or misclassified");
        }
        failure=0; check(solve());
        phase=1; check(solve()); check(solve());
        bool late=false;
        try { system.set_jacobian_coo(rows,columns); } catch(const std::runtime_error&) { late=true; }
        require(late,"COO graph was changed after solve");
    }
    // Three constraint-only rows are absent from the user graph; a real Newton step must
    // still replace them using the internally reserved diagonals. Other ranks have empty COO input.
    NonlinearSystem constrained(comm,layout);
    const std::vector<PetscInt> pattern=rank==ranks-1?std::vector<PetscInt>{0}:std::vector<PetscInt>{};
    constrained.set_jacobian_coo(pattern,pattern);
    std::vector<PetscInt> bc;
    for(auto row:layout.fields.at("state")) if(row!=0) bc.push_back(row);
    std::vector<double> prescribed(bc.size(),2);
    const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
        for(auto row:bc) EONSIM_PETSC(VecSetValue(r,row,7,ADD_VALUES));
        if(rank==ranks-1) {
            EONSIM_PETSC(VecSetValue(r,0,2*(x[local[0]]-1),ADD_VALUES));
            if(j) constrained.jacobian_coo_values()[0]=2;
        }
    };
    const auto result=constrained.solve(config,std::vector<double>(4,0),bc,prescribed,assemble);
    require(result.iterations>0,"Constraint-only diagonal test did not assemble a Jacobian");
    for(int row=0;row<4;++row) {
        require(std::abs(result.values[local[row]]-(row?2:1))<1e-12,"Sparse COO pattern lost constraints");
        require(std::abs(result.raw_residual[local[row]]-(row?7:0))<1e-12,"Sparse COO pattern lost reactions");
    }
    if(rank==0) std::cout<<"COO duplicate/remote/empty rows, exact solutions, reactions, reset and failure recovery passed on "<<ranks<<" ranks\n";
}
}
int main(int argc,char** argv)
{
    if(PetscInitialize(&argc,&argv,nullptr,nullptr)) return 1;
    try {
        EONSIM_PETSC(PetscPushErrorHandler(PetscReturnErrorHandler,nullptr));
        verify(PETSC_COMM_WORLD);
        EONSIM_PETSC(PetscPopErrorHandler());
    } catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; MPI_Abort(PETSC_COMM_WORLD,1); }
    return PetscFinalize();
}
