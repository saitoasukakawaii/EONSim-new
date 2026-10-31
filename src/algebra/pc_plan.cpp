#include "eonsim/pc_plan.hpp"
#include <algorithm>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
namespace eonsim {
namespace {
void common_check(MPI_Comm comm,bool good,const std::string& message) {
    int bad=!good,any=0;
    if(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("PC plan validation communication failed");
    if(any) throw std::runtime_error("PC plan: "+message);
}
using D=DofDomain; using Q=DofQuantity;
struct Spec {
    std::string name; int select; bool schur; std::vector<Spec> children;
    Spec(std::string n,int s,bool h=false,std::vector<Spec> c={}):
        name(std::move(n)),select(s),schur(h),children(std::move(c)) {}
};
bool selected(const DofKey& key,int choice) {
    switch(choice) {
    case 0:return true;
    case 1:return key.domain==D::fluid;
    case 2:return key.domain==D::solid;
    case 3:return key.domain==D::mesh;
    case 4:return key.quantity==Q::velocity;
    case 5:return key.quantity==Q::pressure;
    case 6:return key.quantity==Q::velocity||key.quantity==Q::pressure;
    }
    return false;
}
PcBlock build(MPI_Comm comm,const AlgebraLayout& layout,const Spec& spec,
              const std::vector<PetscInt>& roots,const std::vector<PetscInt>& parent_rows) {
    PcBlock node; node.name=spec.name; node.schur=spec.schur;
    node.root_rows=roots; node.parent_rows=parent_rows;
    PetscInt count=roots.size(); int rank=0; MPI_Comm_rank(comm,&rank);
    if(MPI_Exscan(&count,&node.begin,1,MPIU_INT,MPI_SUM,comm)!=MPI_SUCCESS ||
       MPI_Allreduce(&count,&node.global,1,MPIU_INT,MPI_SUM,comm)!=MPI_SUCCESS)
        throw std::runtime_error("PC plan count communication failed");
    if(rank==0) node.begin=0;
    if(spec.name=="root") common_check(comm,node.begin==layout.begin&&node.global==layout.global,
        "root ownership is inconsistent with distributed counts");
    if(node.global==0) throw std::runtime_error("PC plan globally empty block: "+spec.name);
    if(spec.children.empty()) return node;
    std::vector<int> hits(roots.size(),0);
    for(const auto& child:spec.children) {
        std::vector<PetscInt> subroots,indices;
        for(std::size_t i=0;i<roots.size();++i) if(selected(layout.owned_semantics.at(roots[i]-layout.begin),child.select)) {
            ++hits[i]; subroots.push_back(roots[i]); indices.push_back(node.begin+i);
        }
        node.children.push_back(build(comm,layout,child,subroots,indices));
    }
    common_check(comm,std::all_of(hits.begin(),hits.end(),[](int n){return n==1;}),
                 "children must cover parent exactly once at "+spec.name);
    return node;
}
void defaults(KSP ksp) {
    PC pc; EONSIM_PETSC(KSPGetPC(ksp,&pc));
    EONSIM_PETSC(KSPSetType(ksp,KSPPREONLY)); EONSIM_PETSC(PCSetType(pc,PCGAMG));
    const char* prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(ksp,&prefix));
    const std::string base="-"+std::string(prefix?prefix:"");
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"mg_coarse_ksp_type","gmres"},{"mg_coarse_pc_type","jacobi"},
        {"mg_coarse_ksp_rtol","1e-10"},{"mg_coarse_ksp_max_it","200"},
        {"mg_coarse_ksp_norm_type","unpreconditioned"}}) {
        PetscBool found=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,(base+option.first).c_str(),&found));
        if(!found) EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+option.first).c_str(),option.second.c_str()));
    }
    EONSIM_PETSC(KSPSetFromOptions(ksp));
}
struct SubSolvers { KSP* values=nullptr; ~SubSolvers(){ PetscFree(values); } };
void configure(MPI_Comm comm,KSP ksp,const PcBlock& node,bool root,bool schur_parent=false) {
    Mat a=nullptr; EONSIM_PETSC(KSPGetOperators(ksp,&a,nullptr));
    PetscInt m=0,n=0,begin=0,end=0;
    EONSIM_PETSC(MatGetSize(a,&m,&n)); EONSIM_PETSC(MatGetOwnershipRange(a,&begin,&end));
    common_check(comm,m==node.global&&n==m&&begin==node.begin&&end-begin==static_cast<PetscInt>(node.root_rows.size()),
                 "submatrix ownership does not match provenance at "+node.name);
    PetscBool report=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&report,nullptr));
    if(report) {
        int rank=0; MPI_Comm_rank(comm,&rank);
        const char* prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(ksp,&prefix));
        EONSIM_PETSC(PetscSynchronizedPrintf(comm,"pc_block rank=%d name=%s prefix=%s global=%" PetscInt_FMT " begin=%" PetscInt_FMT " owned=%zu children=%zu\n",
            rank,node.name.c_str(),prefix?prefix:"-",node.global,node.begin,node.root_rows.size(),node.children.size()));
        EONSIM_PETSC(PetscSynchronizedFlush(comm,PETSC_STDOUT));
    }
    PC pc; EONSIM_PETSC(KSPGetPC(ksp,&pc));
    if(node.children.empty()) {
        // Raw stabilized J_pp may have a constant nullspace even when the full
        // traction-coupled system is nonsingular. Do not invert that block with
        // an AMG coarse solve; the quantity recipe uses its diagonal action.
        if(node.global==1 || (node.name=="pressure"&&!schur_parent)) {
            EONSIM_PETSC(KSPSetType(ksp,KSPPREONLY)); EONSIM_PETSC(PCSetType(pc,PCJACOBI));
            EONSIM_PETSC(KSPSetFromOptions(ksp));
        } else defaults(ksp);
        return;
    }
    if(!root) EONSIM_PETSC(KSPSetType(ksp,KSPPREONLY));
    EONSIM_PETSC(PCSetType(pc,PCFIELDSPLIT));
    EONSIM_PETSC(PCFieldSplitSetType(pc,node.schur?PC_COMPOSITE_SCHUR:PC_COMPOSITE_MULTIPLICATIVE));
    if(node.schur) {
        EONSIM_PETSC(PCFieldSplitSetSchurFactType(pc,PC_FIELDSPLIT_SCHUR_FACT_FULL));
        EONSIM_PETSC(PCFieldSplitSetSchurPre(pc,PC_FIELDSPLIT_SCHUR_PRE_SELFP,nullptr));
    }
    for(const auto& child:node.children) {
        PetscOwner<IS,ISDestroy> is;
        EONSIM_PETSC(ISCreateGeneral(comm,child.parent_rows.size(),child.parent_rows.data(),PETSC_COPY_VALUES,is.put()));
        EONSIM_PETSC(PCFieldSplitSetIS(pc,child.name.c_str(),is.get()));
    }
    // Options are applied after registering IS, before setup. The topology is fixed.
    EONSIM_PETSC(KSPSetFromOptions(ksp));
    PCType type=nullptr; EONSIM_PETSC(PCGetType(pc,&type));
    common_check(comm,type&&std::string(type)==PCFIELDSPLIT,"internal node requires fieldsplit at "+node.name);
    const char* prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(ksp,&prefix));
    const std::string base="-"+std::string(prefix?prefix:"");
    PCCompositeType actual; EONSIM_PETSC(PCFieldSplitGetType(pc,&actual));
    common_check(comm,actual==(node.schur?PC_COMPOSITE_SCHUR:PC_COMPOSITE_MULTIPLICATIVE),
                 "options changed recipe split type at "+node.name);
    bool separate=false;
    if(node.schur) {
        char* options=nullptr; EONSIM_PETSC(PetscOptionsGetAll(nullptr,&options));
        std::istringstream tokens(options?options:""); EONSIM_PETSC(PetscFree(options));
        const auto second=base+"fieldsplit_"+node.children[1].name;
        std::string token;
        while(tokens>>token) if(token.rfind(second+"_inner_",0)==0||token.rfind(second+"_upper_",0)==0) separate=true;
    }
    common_check(comm,!separate,"separate Schur inner/upper solvers are not supported");
    EONSIM_PETSC(PCSetUp(pc));
    PetscInt count=0; SubSolvers sub;
    EONSIM_PETSC(PCFieldSplitGetSubKSP(pc,&count,&sub.values));
    common_check(comm,count==static_cast<PetscInt>(node.children.size()),"subsolver count changed at "+node.name);
    for(PetscInt i=0;i<count;++i) configure(comm,sub.values[i],node.children[i],false,node.schur);
}
}
PcBlock make_pc_plan(MPI_Comm comm,const AlgebraLayout& layout,const std::string& recipe) {
    int choice=recipe=="physics"?1:recipe=="quantity"?2:recipe=="hybrid"?3:0;
    int lo=0,hi=0;
    MPI_Allreduce(&choice,&lo,1,MPI_INT,MPI_MIN,comm); MPI_Allreduce(&choice,&hi,1,MPI_INT,MPI_MAX,comm);
    common_check(comm,lo==hi&&lo!=0,"recipe must be physics, quantity or hybrid and identical on every rank");
    common_check(comm,layout.owned>=0&&layout.begin>=0&&layout.global>0&&
        static_cast<long long>(layout.begin)+layout.owned<=layout.global,"invalid root ownership range");
    bool owned_order=layout.local_to_global.size()>=static_cast<std::size_t>(layout.owned);
    if(owned_order) for(PetscInt i=0;i<layout.owned;++i) owned_order=owned_order&&layout.local_to_global[i]==layout.begin+i;
    common_check(comm,owned_order,"owned storage must precede ghosts in root order");
    common_check(comm,layout.owned_semantics.size()==static_cast<std::size_t>(layout.owned),"missing owned semantic identities");
    std::set<DofKey> keys(layout.owned_semantics.begin(),layout.owned_semantics.end());
    common_check(comm,keys.size()==layout.owned_semantics.size(),"duplicate owned semantic identity");
    common_check(comm,std::all_of(layout.owned_semantics.begin(),layout.owned_semantics.end(),[](const DofKey& k) {
        return static_cast<int>(k.domain)<=2 && static_cast<int>(k.quantity)<=2;
    }),"invalid semantic domain or quantity");
    int local[3]{},global[3]{};
    for(const auto& key:layout.owned_semantics) ++local[static_cast<int>(key.domain)];
    MPI_Allreduce(local,global,3,MPI_INT,MPI_SUM,comm);
    const bool coupled=global[1]||global[2];
    common_check(comm,global[0]>0&&(!coupled||(global[1]>0&&global[2]>0)),"recipes require independent fluid or complete FSI layout");
    Spec v{"velocity",4}, p{"pressure",5}, mesh{"mesh",3}, solid{"structure",2}, fluid{"fluid_interior",1};
    Spec root{"root",0};
    if(!coupled) { root.schur=true; root.children={v,p}; }
    else if(choice==1) root.children={{"fluid",1,true,{v,p}},{"solid",2},mesh};
    else {
        v.children={fluid,solid};
        if(choice==2) root.children={v,p,mesh};
        else root.children={{"dynamics",6,true,{v,p}},mesh};
    }
    std::vector<PetscInt> rows(layout.owned); std::iota(rows.begin(),rows.end(),layout.begin);
    return build(comm,layout,root,rows,rows);
}
namespace {
void validate_options(MPI_Comm comm,const PcBlock& node,const std::string& prefix,const std::vector<std::string>& tokens) {
    if(node.children.empty()) return;
    const auto base="-"+prefix;
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"pc_type","fieldsplit"},{"pc_fieldsplit_type",node.schur?"schur":"multiplicative"}}) {
        char value[128]{}; PetscBool set=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+option.first).c_str(),value,sizeof(value),&set));
        common_check(comm,!set||value==option.second,"options changed recipe at "+prefix+option.first);
    }
    bool valid=true;
    if(node.schur) {
        const auto second=base+"fieldsplit_"+node.children[1].name;
        for(const auto& token:tokens)
            if(token.rfind(second+"_inner_",0)==0||token.rfind(second+"_upper_",0)==0) valid=false;
    }
    common_check(comm,valid,"separate Schur inner/upper solvers are not supported at "+prefix);
    for(const auto& child:node.children) validate_options(comm,child,prefix+"fieldsplit_"+child.name+"_",tokens);
}
}
void validate_pc_plan_options(MPI_Comm comm,KSP solver,const PcBlock& plan) {
    char* text=nullptr; EONSIM_PETSC(PetscOptionsGetAll(nullptr,&text));
    std::istringstream stream(text?text:""); EONSIM_PETSC(PetscFree(text));
    std::vector<std::string> tokens; std::string token;
    while(stream>>token) tokens.push_back(token);
    const char* prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix));
    validate_options(comm,plan,prefix?prefix:"",tokens);
}
void configure_pc_plan(MPI_Comm comm,KSP solver,Mat matrix,const PcBlock& plan) {
    validate_pc_plan_options(comm,solver,plan);
    EONSIM_PETSC(KSPSetOperators(solver,matrix,matrix));
    configure(comm,solver,plan,true);
}
}
