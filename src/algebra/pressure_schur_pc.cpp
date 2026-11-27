#include "eonsim/pressure_schur_pc.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <limits>
#include <map>
#include <numeric>
#include <set>

namespace eonsim {
namespace {
void common_check(MPI_Comm comm,bool valid,const std::string& message) {
    int bad=!valid,any=0;
    if(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("pressure Schur validation communication failed");
    if(any) throw std::runtime_error("Pressure Schur: "+message);
}
const char* kind_name(PressureSchurKind kind) {
    switch(kind) {
    case PressureSchurKind::lsc:return "lsc";
    case PressureSchurKind::bfbt:return "bfbt";
    case PressureSchurKind::pcd:return "pcd";
    case PressureSchurKind::added_mass:return "added_mass";
    }
    return "invalid";
}
void finite_matrix(MPI_Comm comm,Mat matrix,const char* description) {
    PetscInt begin=0,end=0; EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    bool finite=true;
    for(PetscInt row=begin;row<end;++row) {
        PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
        EONSIM_PETSC(MatGetRow(matrix,row,&count,&columns,&values));
        for(PetscInt j=0;j<count;++j) finite=finite&&std::isfinite(values[j]);
        EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&columns,&values));
    }
    common_check(comm,finite,std::string(description)+" has nonfinite entries");
}
void sum_matrix(Mat first,double a,Mat second,double b,PetscOwner<Mat,MatDestroy>& output) {
    if(!output.get()) {
        EONSIM_PETSC(MatDuplicate(first,MAT_COPY_VALUES,output.put()));
        EONSIM_PETSC(MatScale(output.get(),a));
        EONSIM_PETSC(MatAXPY(output.get(),b,second,DIFFERENT_NONZERO_PATTERN));
        EONSIM_PETSC(MatSetOption(output.get(),MAT_NEW_NONZERO_LOCATION_ERR,PETSC_TRUE));
    } else {
        EONSIM_PETSC(MatZeroEntries(output.get()));
        EONSIM_PETSC(MatAXPY(output.get(),a,first,SUBSET_NONZERO_PATTERN));
        EONSIM_PETSC(MatAXPY(output.get(),b,second,SUBSET_NONZERO_PATTERN));
    }
}
void option_default(const std::string& name,const char* value) {
    PetscBool found=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,name.c_str(),&found));
    if(!found) EONSIM_PETSC(PetscOptionsSetValue(nullptr,name.c_str(),value));
}
std::pair<bool,double> pcd_mass_options(MPI_Comm comm) {
    PetscBool enhanced=PETSC_FALSE,blend_set=PETSC_FALSE;
    PetscReal blend=.5;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_pcd_velocity_mass",&enhanced,nullptr));
    EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,"-pc_plan_pcd_velocity_mass_weight",&blend,&blend_set));
    int option=enhanced?1:0,option_min=0,option_max=0;
    double weight_min=0.,weight_max=0.;
    EONSIM_PETSC(MPI_Allreduce(&option,&option_min,1,MPI_INT,MPI_MIN,comm));
    EONSIM_PETSC(MPI_Allreduce(&option,&option_max,1,MPI_INT,MPI_MAX,comm));
    EONSIM_PETSC(MPI_Allreduce(&blend,&weight_min,1,MPI_DOUBLE,MPI_MIN,comm));
    EONSIM_PETSC(MPI_Allreduce(&blend,&weight_max,1,MPI_DOUBLE,MPI_MAX,comm));
    common_check(comm,option_min==option_max&&weight_min==weight_max&&std::isfinite(blend)&&blend>=0.&&blend<=1.,
        "PCD velocity-mass options must agree across ranks and blend weight must be in [0,1]");
    common_check(comm,!blend_set||enhanced,"PCD velocity-mass blend weight requires its enhancement option");
    return {enhanced!=PETSC_FALSE,blend};
}

// Each inverse is strictly local, but its sparse products retain off-owner
// couplings. The root grouping is semantic; row adjacency is not used to guess
// whether a velocity represents fluid or structure.
struct NodalCompliance {
    std::vector<std::vector<PetscInt>> groups;
    std::vector<std::size_t> offsets;
    std::vector<PetscScalar> values;
    PetscOwner<Mat,MatDestroy> inverse;

    void initialize(MPI_Comm comm,Mat matrix,const std::vector<PetscInt>& root_rows,
                    const std::vector<std::vector<PetscInt>>& root_groups) {
        PetscInt begin=0,end=0,global=0;
        EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
        EONSIM_PETSC(MatGetSize(matrix,&global,nullptr));
        std::map<PetscInt,PetscInt> compact;
        for(std::size_t i=0;i<root_rows.size();++i) compact.emplace(root_rows[i],begin+i);
        bool valid=static_cast<PetscInt>(root_rows.size())==end-begin;
        std::set<PetscInt> covered;
        std::vector<PetscInt> rows,columns;
        for(const auto& root_group:root_groups) {
            std::vector<PetscInt> group;
            valid=valid&&!root_group.empty()&&root_group.size()<=3;
            for(const auto root_row:root_group) {
                const auto found=compact.find(root_row);
                if(found==compact.end()) { valid=false; continue; }
                valid=valid&&covered.insert(found->second).second;
                group.push_back(found->second);
            }
            offsets.push_back(rows.size());
            for(const auto row:group) for(const auto column:group) {rows.push_back(row);columns.push_back(column);}
            groups.push_back(std::move(group));
        }
        common_check(comm,valid&&covered.size()==root_rows.size(),"structural/fluid compliance groups must cover each owned momentum row once");
        EONSIM_PETSC(MatCreate(comm,inverse.put()));
        EONSIM_PETSC(MatSetSizes(inverse.get(),end-begin,end-begin,global,global));
        EONSIM_PETSC(MatSetType(inverse.get(),MATAIJ));
        EONSIM_PETSC(MatSetPreallocationCOO(inverse.get(),rows.size(),rows.data(),columns.data()));
        EONSIM_PETSC(MatSetOption(inverse.get(),MAT_NEW_NONZERO_LOCATION_ERR,PETSC_TRUE));
        values.resize(rows.size());
    }

    void update(MPI_Comm comm,Mat matrix) {
        bool valid=true;
        for(std::size_t block=0;block<groups.size();++block) {
            const auto& rows=groups[block]; const PetscInt n=rows.size();
            std::array<PetscScalar,9> local{},inverted{};
            EONSIM_PETSC(MatGetValues(matrix,n,rows.data(),n,rows.data(),local.data()));
            long double scale=0.;
            for(PetscInt i=0;i<n*n;++i) {valid=valid&&std::isfinite(local[i]);scale=std::max(scale,std::abs(static_cast<long double>(local[i])));}
            if(!(scale>0.)||!std::isfinite(scale)) {valid=false;continue;}
            std::array<long double,18> augmented{};
            for(PetscInt i=0;i<n;++i) for(PetscInt j=0;j<n;++j) {
                augmented[i*2*n+j]=local[i*n+j]/scale;
                augmented[i*2*n+n+j]=i==j?1.L:0.L;
            }
            bool nonsingular=true;
            for(PetscInt column=0;column<n;++column) {
                PetscInt pivot=column;
                for(PetscInt row=column+1;row<n;++row)
                    if(std::abs(augmented[row*2*n+column])>std::abs(augmented[pivot*2*n+column])) pivot=row;
                const auto magnitude=std::abs(augmented[pivot*2*n+column]);
                if(!std::isfinite(magnitude)||magnitude<=64.L*std::numeric_limits<double>::epsilon()) {nonsingular=false;break;}
                for(PetscInt j=0;j<2*n;++j) std::swap(augmented[column*2*n+j],augmented[pivot*2*n+j]);
                const auto divisor=augmented[column*2*n+column];
                for(PetscInt j=0;j<2*n;++j) augmented[column*2*n+j]/=divisor;
                for(PetscInt row=0;row<n;++row) if(row!=column) {
                    const auto multiplier=augmented[row*2*n+column];
                    for(PetscInt j=0;j<2*n;++j) augmented[row*2*n+j]-=multiplier*augmented[column*2*n+j];
                }
            }
            valid=valid&&nonsingular;
            for(PetscInt i=0;i<n;++i) for(PetscInt j=0;j<n;++j) {
                inverted[i*n+j]=static_cast<PetscScalar>(augmented[i*2*n+n+j]/scale);
                valid=valid&&std::isfinite(inverted[i*n+j]);
            }
            std::copy_n(inverted.begin(),n*n,values.begin()+offsets[block]);
        }
        common_check(comm,valid,"singular or nonfinite nodal structural/fluid compliance block");
        EONSIM_PETSC(MatSetValuesCOO(inverse.get(),values.data(),INSERT_VALUES));
    }
};

struct AddedMassPressure {
    MPI_Comm comm;
    PressureComplianceLayout layout;
    std::vector<PetscInt> fluid_rows,solid_rows;
    PetscOwner<IS,ISDestroy> fluid,solid;
    PetscOwner<Mat,MatDestroy> f,e,g,k,bf,bs,cf,cs;
    PetscOwner<Mat,MatDestroy> hsg,ehsg,fh,hsbs,ehsbs,bh,cshsg,ch,cshsbs,dh,hfbh,chhfbh;
    NodalCompliance hs,hf;

    AddedMassPressure(MPI_Comm communicator,const std::vector<PetscInt>& velocity_rows,
                      const PressureComplianceLayout& groups):comm(communicator),layout(groups) {
        std::set<PetscInt> seen;
        bool valid=true;
        for(const auto& group:layout.fluid_groups) for(auto row:group) {
            valid=valid&&seen.insert(row).second;fluid_rows.push_back(row);
        }
        for(const auto& group:layout.structure_groups) for(auto row:group) {
            valid=valid&&seen.insert(row).second;solid_rows.push_back(row);
        }
        const std::set<PetscInt> expected(velocity_rows.begin(),velocity_rows.end());
        common_check(comm,valid&&seen==expected,"added_mass pressure groups must partition the supplied velocity rows");
        std::sort(fluid_rows.begin(),fluid_rows.end());std::sort(solid_rows.begin(),solid_rows.end());
        EONSIM_PETSC(ISCreateGeneral(comm,fluid_rows.size(),fluid_rows.data(),PETSC_COPY_VALUES,fluid.put()));
        EONSIM_PETSC(ISCreateGeneral(comm,solid_rows.size(),solid_rows.data(),PETSC_COPY_VALUES,solid.put()));
        PetscInt nf=0,ns=0;EONSIM_PETSC(ISGetSize(fluid.get(),&nf));EONSIM_PETSC(ISGetSize(solid.get(),&ns));
        common_check(comm,nf>0&&ns>0,"added_mass pressure requires both fluid and structural velocity rows in the pressure split");
    }

    void update(Mat root,IS pressure,Mat d,PetscOwner<Mat,MatDestroy>& output) {
        const bool first=!f.get(); const auto reuse=first?MAT_INITIAL_MATRIX:MAT_REUSE_MATRIX;
        EONSIM_PETSC(MatCreateSubMatrix(root,fluid.get(),fluid.get(),reuse,f.put()));
        EONSIM_PETSC(MatCreateSubMatrix(root,fluid.get(),solid.get(),reuse,e.put()));
        EONSIM_PETSC(MatCreateSubMatrix(root,solid.get(),fluid.get(),reuse,g.put()));
        EONSIM_PETSC(MatCreateSubMatrix(root,solid.get(),solid.get(),reuse,k.put()));
        EONSIM_PETSC(MatCreateSubMatrix(root,fluid.get(),pressure,reuse,bf.put()));
        EONSIM_PETSC(MatCreateSubMatrix(root,solid.get(),pressure,reuse,bs.put()));
        EONSIM_PETSC(MatCreateSubMatrix(root,pressure,fluid.get(),reuse,cf.put()));
        EONSIM_PETSC(MatCreateSubMatrix(root,pressure,solid.get(),reuse,cs.put()));
        if(first) hs.initialize(comm,k.get(),solid_rows,layout.structure_groups);
        hs.update(comm,k.get());
        // Retain all three structural corrections, including direct pressure
        // work on moving interface velocities. E and G, and B and C, are never
        // silently replaced by transposes in this nonsymmetric ALE Jacobian.
        EONSIM_PETSC(MatMatMult(hs.inverse.get(),g.get(),reuse,PETSC_DEFAULT,hsg.put()));
        EONSIM_PETSC(MatMatMult(e.get(),hsg.get(),reuse,PETSC_DEFAULT,ehsg.put()));
        sum_matrix(f.get(),1.,ehsg.get(),-1.,fh);
        if(first) hf.initialize(comm,fh.get(),fluid_rows,layout.fluid_groups);
        hf.update(comm,fh.get());
        EONSIM_PETSC(MatMatMult(hs.inverse.get(),bs.get(),reuse,PETSC_DEFAULT,hsbs.put()));
        EONSIM_PETSC(MatMatMult(e.get(),hsbs.get(),reuse,PETSC_DEFAULT,ehsbs.put()));
        sum_matrix(bf.get(),1.,ehsbs.get(),-1.,bh);
        EONSIM_PETSC(MatMatMult(cs.get(),hsg.get(),reuse,PETSC_DEFAULT,cshsg.put()));
        sum_matrix(cf.get(),1.,cshsg.get(),-1.,ch);
        EONSIM_PETSC(MatMatMult(cs.get(),hsbs.get(),reuse,PETSC_DEFAULT,cshsbs.put()));
        sum_matrix(d,1.,cshsbs.get(),-1.,dh);
        EONSIM_PETSC(MatMatMult(hf.inverse.get(),bh.get(),reuse,PETSC_DEFAULT,hfbh.put()));
        EONSIM_PETSC(MatMatMult(ch.get(),hfbh.get(),reuse,PETSC_DEFAULT,chhfbh.put()));
        sum_matrix(dh.get(),1.,chhfbh.get(),-1.,output);
    }
};
} // namespace

struct PressureSchurState {
    MPI_Comm comm;
    PressureSchurKind kind;
    PetscOwner<IS,ISDestroy> velocity,pressure;
    PetscOwner<Mat,MatDestroy> a,b,c,d,wb,awb,cb,cawb,p,middle;
    PetscOwner<Mat,MatDestroy> mass,laplace,transport,scaled_d,transport_d;
    PetscOwner<Mat,MatDestroy> velocity_mass,viscosity,boundary,mass_b,mass_laplace,mass_laplace_bc,blended_laplace,laplace_change,enhanced_transport;
    PetscOwner<Vec,VecDestroy> weight,inverse_mass;
    PetscOwner<Vec,VecDestroy> inverse_velocity_mass,pressure_viscosity,boundary_mask;
    std::unique_ptr<AddedMassPressure> compliance;
    PetscInt updates=0;
    double scale=1.;
    double mass_blend=.5;
    bool ready=false,velocity_mass_enhanced=false;

    PressureSchurState(MPI_Comm communicator,Mat root,
        const std::vector<PetscInt>& vr,const std::vector<PetscInt>& pr,
        PressureSchurKind selection,const PressureComplianceLayout& groups):comm(communicator),kind(selection) {
        PetscInt begin=0,end=0,m=0,n=0;
        EONSIM_PETSC(MatGetOwnershipRange(root,&begin,&end));
        EONSIM_PETSC(MatGetSize(root,&m,&n));
        std::set<PetscInt> seen;
        bool valid=m==n&&(kind==PressureSchurKind::lsc||kind==PressureSchurKind::bfbt||kind==PressureSchurKind::pcd||kind==PressureSchurKind::added_mass);
        for(auto row:vr) valid=valid&&row>=begin&&row<end&&seen.insert(row).second;
        for(auto row:pr) valid=valid&&row>=begin&&row<end&&seen.insert(row).second;
        common_check(comm,valid,"indices must be distinct locally owned root rows");
        EONSIM_PETSC(ISCreateGeneral(comm,vr.size(),vr.data(),PETSC_COPY_VALUES,velocity.put()));
        EONSIM_PETSC(ISCreateGeneral(comm,pr.size(),pr.data(),PETSC_COPY_VALUES,pressure.put()));
        PetscInt velocities=0,pressures=0;
        EONSIM_PETSC(ISGetSize(velocity.get(),&velocities)); EONSIM_PETSC(ISGetSize(pressure.get(),&pressures));
        common_check(comm,velocities>0&&pressures>0,"requires nonempty global velocity and pressure blocks");
        if(kind==PressureSchurKind::added_mass) compliance=std::make_unique<AddedMassPressure>(comm,vr,groups);
        const auto mass_options=pcd_mass_options(comm);
        velocity_mass_enhanced=mass_options.first;mass_blend=mass_options.second;
        common_check(comm,!velocity_mass_enhanced||kind==PressureSchurKind::pcd,
            "velocity-mass pressure enhancement requires physical PCD");
    }

    void pcd_auxiliary(Mat root,const char* key,PetscOwner<Mat,MatDestroy>& output,IS rows=nullptr) {
        Mat full=nullptr;
        EONSIM_PETSC(PetscObjectQuery(reinterpret_cast<PetscObject>(root),key,
            reinterpret_cast<PetscObject*>(&full)));
        common_check(comm,full!=nullptr,std::string("physical PCD requires assembled auxiliary ")+key);
        PetscInt rm=0,rn=0,rb=0,re=0,fm=0,fn=0,fb=0,fe=0;
        EONSIM_PETSC(MatGetSize(root,&rm,&rn)); EONSIM_PETSC(MatGetOwnershipRange(root,&rb,&re));
        EONSIM_PETSC(MatGetSize(full,&fm,&fn)); EONSIM_PETSC(MatGetOwnershipRange(full,&fb,&fe));
        common_check(comm,rm==fm&&rn==fn&&rb==fb&&re==fe,
            std::string("PCD auxiliary root numbering/ownership mismatch for ")+key);
        if(!rows) rows=pressure.get();
        EONSIM_PETSC(MatCreateSubMatrix(full,rows,rows,
            output.get()?MAT_REUSE_MATRIX:MAT_INITIAL_MATRIX,output.put()));
        finite_matrix(comm,output.get(),key);
    }

    void enhance_pcd(Mat root,bool first) {
        const auto reuse=first?MAT_INITIAL_MATRIX:MAT_REUSE_MATRIX;
        pcd_auxiliary(root,pressure_pcd_velocity_mass_key,velocity_mass,velocity.get());
        pcd_auxiliary(root,pressure_pcd_viscosity_key,viscosity);
        pcd_auxiliary(root,pressure_pcd_boundary_key,boundary);
        EONSIM_PETSC(MatCreateSubMatrix(root,velocity.get(),pressure.get(),reuse,b.put()));
        EONSIM_PETSC(MatCreateSubMatrix(root,pressure.get(),velocity.get(),reuse,c.put()));
        if(first) {
            EONSIM_PETSC(MatCreateVecs(velocity_mass.get(),inverse_velocity_mass.put(),nullptr));
            EONSIM_PETSC(MatCreateVecs(viscosity.get(),pressure_viscosity.put(),nullptr));
            EONSIM_PETSC(VecDuplicate(pressure_viscosity.get(),boundary_mask.put()));
            EONSIM_PETSC(MatDuplicate(b.get(),MAT_DO_NOT_COPY_VALUES,mass_b.put()));
        }
        EONSIM_PETSC(MatGetDiagonal(velocity_mass.get(),inverse_velocity_mass.get()));
        PetscScalar* weights=nullptr; PetscInt size=0;
        EONSIM_PETSC(VecGetLocalSize(inverse_velocity_mass.get(),&size));
        EONSIM_PETSC(VecGetArray(inverse_velocity_mass.get(),&weights));
        bool valid=true;
        for(PetscInt i=0;i<size;++i) {
            valid=valid&&std::isfinite(weights[i])&&weights[i]>=0.;
            // Structural-interior rows are outside the fluid L2 mass. Their
            // weight is zero, not an arbitrary replacement mass or infinity.
            if(weights[i]>0.) {weights[i]=1./weights[i];valid=valid&&std::isfinite(weights[i]);}
        }
        EONSIM_PETSC(VecRestoreArray(inverse_velocity_mass.get(),&weights));
        PetscInt begin=0,end=0;
        EONSIM_PETSC(MatGetOwnershipRange(velocity_mass.get(),&begin,&end));
        for(PetscInt row=begin;row<end;++row) {
            PetscInt count=0;const PetscInt* columns=nullptr;const PetscScalar* entries=nullptr;
            EONSIM_PETSC(MatGetRow(velocity_mass.get(),row,&count,&columns,&entries));
            for(PetscInt i=0;i<count;++i) if(columns[i]!=row&&entries[i]!=0.) valid=false;
            EONSIM_PETSC(MatRestoreRow(velocity_mass.get(),row,&count,&columns,&entries));
        }
        common_check(comm,valid,"PCD velocity mass must be finite, nonnegative and lumped with representable reciprocals");
        EONSIM_PETSC(MatCopy(b.get(),mass_b.get(),SAME_NONZERO_PATTERN));
        EONSIM_PETSC(MatDiagonalScale(mass_b.get(),inverse_velocity_mass.get(),nullptr));
        EONSIM_PETSC(MatMatMult(c.get(),mass_b.get(),reuse,PETSC_DEFAULT,mass_laplace.put()));
        if(first) {
            EONSIM_PETSC(MatDuplicate(mass_laplace.get(),MAT_COPY_VALUES,mass_laplace_bc.put()));
            EONSIM_PETSC(MatSetOption(mass_laplace_bc.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_FALSE));
            EONSIM_PETSC(MatSetOption(mass_laplace_bc.get(),MAT_IGNORE_ZERO_ENTRIES,PETSC_FALSE));
            EONSIM_PETSC(MatGetOwnershipRange(mass_laplace_bc.get(),&begin,&end));
            for(PetscInt row=begin;row<end;++row) EONSIM_PETSC(MatSetValue(mass_laplace_bc.get(),row,row,0.,ADD_VALUES));
            EONSIM_PETSC(MatAssemblyBegin(mass_laplace_bc.get(),MAT_FINAL_ASSEMBLY));
            EONSIM_PETSC(MatAssemblyEnd(mass_laplace_bc.get(),MAT_FINAL_ASSEMBLY));
        } else {
            EONSIM_PETSC(MatZeroEntries(mass_laplace_bc.get()));
            EONSIM_PETSC(MatAXPY(mass_laplace_bc.get(),1.,mass_laplace.get(),SUBSET_NONZERO_PATTERN));
        }
        EONSIM_PETSC(MatScale(mass_laplace_bc.get(),-1.));
        EONSIM_PETSC(MatGetDiagonal(viscosity.get(),pressure_viscosity.get()));
        EONSIM_PETSC(MatGetDiagonal(boundary.get(),boundary_mask.get()));
        const PetscScalar* mu=nullptr;const PetscScalar* mask=nullptr;
        EONSIM_PETSC(VecGetLocalSize(boundary_mask.get(),&size));
        EONSIM_PETSC(VecGetOwnershipRange(boundary_mask.get(),&begin,&end));
        EONSIM_PETSC(VecGetArrayRead(pressure_viscosity.get(),&mu));
        EONSIM_PETSC(VecGetArrayRead(boundary_mask.get(),&mask));
        std::vector<PetscInt> boundary_rows;
        for(PetscInt i=0;i<size;++i) {
            valid=valid&&std::isfinite(mu[i])&&mu[i]>0.&&(mask[i]==0.||mask[i]==1.);
            if(mask[i]==1.) boundary_rows.push_back(begin+i);
        }
        EONSIM_PETSC(VecRestoreArrayRead(boundary_mask.get(),&mask));
        EONSIM_PETSC(VecRestoreArrayRead(pressure_viscosity.get(),&mu));
        common_check(comm,valid,"invalid PCD viscosity or auxiliary boundary mask");
        EONSIM_PETSC(MatZeroRows(mass_laplace_bc.get(),boundary_rows.size(),boundary_rows.data(),1.,nullptr,nullptr));
        sum_matrix(laplace.get(),1.-mass_blend,mass_laplace_bc.get(),mass_blend,blended_laplace);
        // Replacing K alone destroys the BRM2 viscosity/mass limit. Rebuild
        // F with exactly the same diffusion change while preserving physical
        // reaction, convection, Robin terms and homogeneous auxiliary rows.
        sum_matrix(blended_laplace.get(),1.,laplace.get(),-1.,laplace_change);
        EONSIM_PETSC(MatDiagonalScale(laplace_change.get(),pressure_viscosity.get(),nullptr));
        sum_matrix(transport.get(),1.,laplace_change.get(),1.,enhanced_transport);
        finite_matrix(comm,enhanced_transport.get(),"velocity-mass enhanced PCD transport");
    }

    void update(Mat root) {
        // Refresh failure invalidates every action sharing this state; a
        // partially updated product must never be applied as the old PC.
        ready=false;
        const bool first=!d.get();
        const MatReuse reuse=first?MAT_INITIAL_MATRIX:MAT_REUSE_MATRIX;
        EONSIM_PETSC(MatCreateSubMatrix(root,pressure.get(),pressure.get(),reuse,d.put()));
        finite_matrix(comm,d.get(),"pressure block");
        if(kind==PressureSchurKind::pcd) {
            pcd_auxiliary(root,pressure_pcd_mass_key,mass);
            pcd_auxiliary(root,pressure_pcd_laplace_key,laplace);
            pcd_auxiliary(root,pressure_pcd_transport_key,transport);
            if(velocity_mass_enhanced) enhance_pcd(root,first);
            if(first) {
                EONSIM_PETSC(MatCreateVecs(mass.get(),inverse_mass.put(),nullptr));
                EONSIM_PETSC(MatDuplicate(d.get(),MAT_DO_NOT_COPY_VALUES,scaled_d.put()));
            }
            EONSIM_PETSC(MatGetDiagonal(mass.get(),inverse_mass.get()));
            PetscScalar* values=nullptr; PetscInt size=0;
            EONSIM_PETSC(VecGetLocalSize(inverse_mass.get(),&size));
            EONSIM_PETSC(VecGetArray(inverse_mass.get(),&values));
            bool valid=true;
            for(PetscInt i=0;i<size;++i) {
                valid=valid&&std::isfinite(values[i])&&values[i]>0;
                if(values[i]>0) { values[i]=1./values[i]; valid=valid&&std::isfinite(values[i]); }
            }
            EONSIM_PETSC(VecRestoreArray(inverse_mass.get(),&values));
            PetscInt begin=0,end=0;
            EONSIM_PETSC(MatGetOwnershipRange(mass.get(),&begin,&end));
            for(PetscInt row=begin;row<end;++row) {
                PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* entries=nullptr;
                EONSIM_PETSC(MatGetRow(mass.get(),row,&count,&columns,&entries));
                for(PetscInt j=0;j<count;++j) if(columns[j]!=row&&entries[j]!=0.) valid=false;
                EONSIM_PETSC(MatRestoreRow(mass.get(),row,&count,&columns,&entries));
            }
            common_check(comm,valid,"PCD mass must be finite positive and lumped, with a representable reciprocal");
            EONSIM_PETSC(MatCopy(d.get(),scaled_d.get(),SAME_NONZERO_PATTERN));
            EONSIM_PETSC(MatDiagonalScale(scaled_d.get(),inverse_mass.get(),nullptr));
            const auto active_transport=velocity_mass_enhanced?enhanced_transport.get():transport.get();
            const auto active_laplace=velocity_mass_enhanced?blended_laplace.get():laplace.get();
            EONSIM_PETSC(MatMatMult(active_transport,scaled_d.get(),reuse,PETSC_DEFAULT,transport_d.put()));
            sum_matrix(active_laplace,1.,transport_d.get(),1.,p);
        } else if(kind==PressureSchurKind::added_mass) {
            compliance->update(root,pressure.get(),d.get(),p);
        } else {
            EONSIM_PETSC(MatCreateSubMatrix(root,velocity.get(),velocity.get(),reuse,a.put()));
            EONSIM_PETSC(MatCreateSubMatrix(root,velocity.get(),pressure.get(),reuse,b.put()));
            EONSIM_PETSC(MatCreateSubMatrix(root,pressure.get(),velocity.get(),reuse,c.put()));
            if(first) {
                EONSIM_PETSC(MatCreateVecs(a.get(),weight.put(),nullptr));
                EONSIM_PETSC(MatDuplicate(b.get(),MAT_DO_NOT_COPY_VALUES,wb.put()));
            }
            bool valid=true;
            if(kind==PressureSchurKind::bfbt) {
                EONSIM_PETSC(MatGetDiagonal(a.get(),weight.get()));
                PetscScalar* values=nullptr; PetscInt size=0;
                EONSIM_PETSC(VecGetLocalSize(weight.get(),&size));
                EONSIM_PETSC(VecGetArray(weight.get(),&values));
                for(PetscInt i=0;i<size;++i) {
                    valid=valid&&std::isfinite(values[i])&&values[i]!=0.;
                    if(values[i]!=0.) { values[i]=1./std::abs(values[i]); valid=valid&&std::isfinite(values[i]); }
                }
                EONSIM_PETSC(VecRestoreArray(weight.get(),&values));
                common_check(comm,valid,"BFBt requires finite nonzero momentum diagonals with representable reciprocals");
            } else EONSIM_PETSC(VecSet(weight.get(),1.));
            // s supplies the units needed for both stabilization terms. The
            // infinity norm is an inexpensive upper bound, not an eigenvalue
            // estimate or a claim of optimal stabilization for all FSI regimes.
            const PetscScalar* weights=nullptr;
            EONSIM_PETSC(VecGetArrayRead(weight.get(),&weights));
            PetscInt begin=0,end=0; EONSIM_PETSC(MatGetOwnershipRange(a.get(),&begin,&end));
            double local=0.;
            for(PetscInt row=begin;row<end;++row) {
                PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
                EONSIM_PETSC(MatGetRow(a.get(),row,&count,&columns,&values));
                long double sum=0.;
                for(PetscInt j=0;j<count;++j) {
                    valid=valid&&std::isfinite(values[j]);
                    sum+=std::abs(static_cast<long double>(weights[row-begin])*values[j]);
                }
                local=std::max(local,static_cast<double>(sum));
                valid=valid&&std::isfinite(static_cast<double>(sum));
                EONSIM_PETSC(MatRestoreRow(a.get(),row,&count,&columns,&values));
            }
            EONSIM_PETSC(VecRestoreArrayRead(weight.get(),&weights));
            common_check(comm,valid,"nonfinite scaled momentum matrix");
            if(MPI_Allreduce(&local,&scale,1,MPI_DOUBLE,MPI_MAX,comm)!=MPI_SUCCESS)
                throw std::runtime_error("pressure commutator scale reduction failed");
            common_check(comm,scale>0&&std::isfinite(scale*scale),"invalid or unrepresentable commutator scale");
            EONSIM_PETSC(MatCopy(b.get(),wb.get(),SAME_NONZERO_PATTERN));
            EONSIM_PETSC(MatDiagonalScale(wb.get(),weight.get(),nullptr));
            EONSIM_PETSC(MatMatMult(c.get(),wb.get(),reuse,PETSC_DEFAULT,cb.put()));
            EONSIM_PETSC(MatMatMult(a.get(),wb.get(),reuse,PETSC_DEFAULT,awb.put()));
            EONSIM_PETSC(MatDiagonalScale(awb.get(),weight.get(),nullptr));
            EONSIM_PETSC(MatMatMult(c.get(),awb.get(),reuse,PETSC_DEFAULT,cawb.put()));
            sum_matrix(cb.get(),-1.,d.get(),scale,p);
            sum_matrix(cawb.get(),-1.,d.get(),scale*scale,middle);
            finite_matrix(comm,middle.get(),"stabilized commutator middle matrix");
        }
        finite_matrix(comm,p.get(),"pressure auxiliary solve matrix");
        ++updates;
        ready=true;
        PetscBool report=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&report,nullptr));
        if(report) {
            PetscInt rows=0; EONSIM_PETSC(MatGetSize(p.get(),&rows,nullptr));
            EONSIM_PETSC(PetscPrintf(comm,"pressure_schur kind=%s rows=%" PetscInt_FMT
                " numerical_updates=%" PetscInt_FMT " scale=%.17g velocity_mass=%d mass_blend=%.17g\n",
                kind_name(kind),rows,updates,scale,int(velocity_mass_enhanced),mass_blend));
        }
    }
};

namespace {
constexpr const char* shell_name="EONSim stabilized pressure commutator/PCD";
struct PressureAction {
    PressureSchurHandle state;
    PetscOwner<KSP,KSPDestroy> auxiliary;
    PetscOwner<Vec,VecDestroy> first,second;

    PetscErrorCode solve(PC pc,Vec rhs,Vec solution,PetscBool* success) {
        PetscFunctionBeginUser;
        // Finite work caps are approximate inverses. Breakdown, failed local
        // factors and nonfinite outputs must reach the containing outer solve.
        // Convert numerical subsolve failure to PC failure rather than throwing
        // across a PETSc callback while the caller holds read-locked vectors.
        const PetscErrorCode error=KSPSolve(auxiliary.get(),rhs,solution);
        KSPConvergedReason reason=KSP_CONVERGED_ITERATING;
        PC subpc=nullptr; PCFailedReason failed=PC_NOERROR;
        const auto reason_error=KSPGetConvergedReason(auxiliary.get(),&reason);
        const auto pc_error=KSPGetPC(auxiliary.get(),&subpc);
        const auto failure_error=subpc?PCGetFailedReason(subpc,&failed):PETSC_ERR_ARG_WRONGSTATE;
        bool valid=error==PETSC_SUCCESS&&reason_error==PETSC_SUCCESS&&pc_error==PETSC_SUCCESS&&
            failure_error==PETSC_SUCCESS&&failed==PC_NOERROR&&(reason>0||reason==KSP_DIVERGED_ITS);
        const PetscScalar* values=nullptr; PetscInt size=0;
        PetscCall(VecGetLocalSize(solution,&size)); PetscCall(VecGetArrayRead(solution,&values));
        for(PetscInt i=0;i<size;++i) valid=valid&&std::isfinite(values[i]);
        PetscCall(VecRestoreArrayRead(solution,&values));
        int local=valid,all=0;
        PetscCallMPI(MPI_Allreduce(&local,&all,1,MPI_INT,MPI_MIN,state->comm));
        *success=all?PETSC_TRUE:PETSC_FALSE;
        if(!all) PetscCall(PCSetFailedReason(pc,PC_SUBPC_ERROR));
        PetscFunctionReturn(PETSC_SUCCESS);
    }
    PetscErrorCode apply(PC pc,Vec input,Vec output) {
        PetscFunctionBeginUser;
        if(!state->ready) {
            PetscCall(PCSetFailedReason(pc,PC_SUBPC_ERROR));
            PetscCall(VecSet(output,PETSC_INFINITY));
            PetscFunctionReturn(PETSC_SUCCESS);
        }
        PetscCall(PCSetFailedReason(pc,PC_NOERROR));
        PetscBool success=PETSC_FALSE;
        if(state->kind==PressureSchurKind::pcd) {
            PetscCall(VecPointwiseMult(first.get(),state->inverse_mass.get(),input));
            PetscCall(MatMult(state->velocity_mass_enhanced?state->enhanced_transport.get():state->transport.get(),first.get(),second.get()));
            PetscCall(solve(pc,second.get(),output,&success));
        } else if(state->kind==PressureSchurKind::added_mass) {
            PetscCall(solve(pc,input,output,&success));
        } else {
            PetscCall(solve(pc,input,first.get(),&success));
            if(!success) {
                PetscCall(VecSet(output,PETSC_INFINITY));
                PetscFunctionReturn(PETSC_SUCCESS);
            }
            PetscCall(MatMult(state->middle.get(),first.get(),second.get()));
            PetscCall(solve(pc,second.get(),output,&success));
        }
        if(!success) PetscCall(VecSet(output,PETSC_INFINITY));
        PetscFunctionReturn(PETSC_SUCCESS);
    }
};
PetscErrorCode apply_pressure(PC pc,Vec input,Vec output) {
    PetscFunctionBeginUser;
    PressureAction* action=nullptr; PetscCall(PCShellGetContext(pc,&action));
    PetscCall(action->apply(pc,input,output));
    PetscFunctionReturn(PETSC_SUCCESS);
}
PetscErrorCode destroy_pressure(PC pc) {
    PetscFunctionBeginUser;
    PressureAction* action=nullptr; PetscCall(PCShellGetContext(pc,&action));
    delete action;
    PetscFunctionReturn(PETSC_SUCCESS);
}
PetscErrorCode view_pressure(PC pc,PetscViewer viewer) {
    PetscFunctionBeginUser;
    PressureAction* action=nullptr; PetscCall(PCShellGetContext(pc,&action));
    PetscBool ascii=PETSC_FALSE;
    PetscCall(PetscObjectTypeCompare(reinterpret_cast<PetscObject>(viewer),PETSCVIEWERASCII,&ascii));
    if(ascii) {
        PetscCall(PetscViewerASCIIPrintf(viewer,"Pressure %s, numerical updates=%" PetscInt_FMT
            ", stabilization scale=%.17g\n",kind_name(action->state->kind),action->state->updates,action->state->scale));
        PetscCall(PetscViewerASCIIPushTab(viewer));
        PetscCall(KSPView(action->auxiliary.get(),viewer));
        PetscCall(PetscViewerASCIIPopTab(viewer));
    }
    PetscFunctionReturn(PETSC_SUCCESS);
}
} // namespace

PressureSchurHandle make_pressure_schur_state(MPI_Comm comm,Mat root,
    const std::vector<PetscInt>& velocity_root_rows,
    const std::vector<PetscInt>& pressure_root_rows,PressureSchurKind kind,const PressureComplianceLayout& compliance) {
    auto result=std::make_shared<PressureSchurState>(comm,root,velocity_root_rows,pressure_root_rows,kind,compliance);
    result->update(root); return result;
}
Mat pressure_schur_matrix(const PressureSchurHandle& state) { return state->p.get(); }
void refresh_pressure_schur(const PressureSchurHandle& state,Mat root) { state->update(root); }

void propagate_pressure_auxiliaries(Mat root,Mat child,IS child_rows) {
    const auto comm=PetscObjectComm(reinterpret_cast<PetscObject>(root));
    const std::array<const char*,6> keys{{pressure_pcd_mass_key,pressure_pcd_laplace_key,pressure_pcd_transport_key,
        pressure_pcd_velocity_mass_key,pressure_pcd_viscosity_key,pressure_pcd_boundary_key}};
    std::array<Mat,6> sources{};
    int count[2]{};
    for(std::size_t i=0;i<keys.size();++i) {
        EONSIM_PETSC(PetscObjectQuery(reinterpret_cast<PetscObject>(root),keys[i],
            reinterpret_cast<PetscObject*>(&sources[i])));
        count[i/3]+=sources[i]!=nullptr;
    }
    int lo[2]{},hi[2]{};
    if(MPI_Allreduce(count,lo,2,MPI_INT,MPI_MIN,comm)!=MPI_SUCCESS||
       MPI_Allreduce(count,hi,2,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("pressure auxiliary propagation communication failed");
    common_check(comm,lo[0]==hi[0]&&(count[0]==0||count[0]==3),"PCD auxiliary composition must be a complete triple on every rank");
    common_check(comm,lo[1]==hi[1]&&(count[1]==0||count[1]==3)&&(!count[1]||count[0]==3),
        "PCD velocity-mass enhancement composition must be a complete triple with the base auxiliaries on every rank");
    if(count[0]==0) return;
    for(std::size_t i=0;i<keys.size();++i) {
        if(!sources[i]) {
            EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(child),keys[i],nullptr));
            continue;
        }
        Mat previous=nullptr;
        EONSIM_PETSC(PetscObjectQuery(reinterpret_cast<PetscObject>(child),keys[i],
            reinterpret_cast<PetscObject*>(&previous)));
        PetscOwner<Mat,MatDestroy> extracted;
        if(previous) {
            EONSIM_PETSC(PetscObjectReference(reinterpret_cast<PetscObject>(previous)));
            *extracted.put()=previous;
        }
        EONSIM_PETSC(MatCreateSubMatrix(sources[i],child_rows,child_rows,
            previous?MAT_REUSE_MATRIX:MAT_INITIAL_MATRIX,extracted.put()));
        EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(child),keys[i],
            reinterpret_cast<PetscObject>(extracted.get())));
    }
}

void validate_pressure_schur_options(MPI_Comm comm,const std::string& pressure_prefix) {
    (void)pcd_mass_options(comm); // Also validate an exactly converged initial state.
    char requested[64]{}; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,("-"+pressure_prefix+"pc_type").c_str(),requested,sizeof(requested),&set));
    common_check(comm,!set||std::strcmp(requested,PCSHELL)==0,
        "pressure commutator/PCD requires its shell PC at "+pressure_prefix);
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,("-"+pressure_prefix+"ksp_type").c_str(),requested,sizeof(requested),&set));
    const int local=!set||std::strcmp(requested,KSPPREONLY)==0?1:std::strcmp(requested,KSPFGMRES)==0?2:0;
    int lo=0,hi=0;
    if(MPI_Allreduce(&local,&lo,1,MPI_INT,MPI_MIN,comm)!=MPI_SUCCESS||
       MPI_Allreduce(&local,&hi,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("pressure solver option communication failed");
    common_check(comm,lo==hi&&lo!=0,
        "pressure commutator/PCD KSP must be preonly or fgmres and identical on every rank at "+pressure_prefix);
}

void configure_pressure_schur_pc(MPI_Comm comm,KSP pressure,const PressureSchurHandle& state) {
    const char* prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(pressure,&prefix));
    const std::string own=prefix?prefix:"",aux=own+"pressure_aux_";
    validate_pressure_schur_options(comm,own);
    auto action=std::make_unique<PressureAction>(); action->state=state;
    EONSIM_PETSC(KSPCreate(comm,action->auxiliary.put()));
    EONSIM_PETSC(KSPSetOptionsPrefix(action->auxiliary.get(),aux.c_str()));
    EONSIM_PETSC(KSPSetOperators(action->auxiliary.get(),state->p.get(),state->p.get()));
    EONSIM_PETSC(KSPSetType(action->auxiliary.get(),KSPPREONLY));
    EONSIM_PETSC(KSPSetTolerances(action->auxiliary.get(),1e-3,PETSC_DEFAULT,PETSC_DEFAULT,30));
    PC auxiliary_pc=nullptr; EONSIM_PETSC(KSPGetPC(action->auxiliary.get(),&auxiliary_pc));
    EONSIM_PETSC(PCSetType(auxiliary_pc,PCGAMG));
    EONSIM_PETSC(PCSetUseAmat(auxiliary_pc,PETSC_FALSE));
    option_default("-"+aux+"mg_coarse_ksp_type","gmres");
    option_default("-"+aux+"mg_coarse_pc_type","jacobi");
    option_default("-"+aux+"mg_coarse_ksp_rtol","1e-10");
    option_default("-"+aux+"mg_coarse_ksp_max_it","200");
    option_default("-"+aux+"mg_coarse_ksp_norm_type","unpreconditioned");
    EONSIM_PETSC(KSPSetFromOptions(action->auxiliary.get()));
    EONSIM_PETSC(MatCreateVecs(state->p.get(),action->first.put(),nullptr));
    EONSIM_PETSC(VecDuplicate(action->first.get(),action->second.put()));
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(pressure,&pc));
    EONSIM_PETSC(KSPSetType(pressure,KSPPREONLY));
    EONSIM_PETSC(PCSetType(pc,PCSHELL));
    EONSIM_PETSC(PCSetUseAmat(pc,PETSC_FALSE));
    EONSIM_PETSC(PCShellSetContext(pc,action.get()));
    EONSIM_PETSC(PCShellSetDestroy(pc,destroy_pressure));
    action.release();
    EONSIM_PETSC(PCShellSetName(pc,shell_name));
    EONSIM_PETSC(PCShellSetApply(pc,apply_pressure));
    EONSIM_PETSC(PCShellSetView(pc,view_pressure));
    EONSIM_PETSC(KSPSetFromOptions(pressure));
    PCType actual=nullptr; EONSIM_PETSC(PCGetType(pc,&actual));
    common_check(comm,actual&&std::strcmp(actual,PCSHELL)==0,"options changed pressure shell PC at "+own);
}
KSP pressure_schur_auxiliary_solver(PC pc) {
    PCType type=nullptr; EONSIM_PETSC(PCGetType(pc,&type));
    if(!type||std::strcmp(type,PCSHELL)!=0) return nullptr;
    const char* name=nullptr; EONSIM_PETSC(PCShellGetName(pc,&name));
    if(!name||std::strcmp(name,shell_name)!=0) return nullptr;
    PressureAction* action=nullptr; EONSIM_PETSC(PCShellGetContext(pc,&action));
    return action?action->auxiliary.get():nullptr;
}
} // namespace eonsim
