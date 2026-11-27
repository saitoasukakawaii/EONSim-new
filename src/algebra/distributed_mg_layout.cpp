#include "eonsim/distributed_mg_layout.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>
#include <tuple>

namespace eonsim {
namespace {
void collective_check(MPI_Comm comm,bool valid,const char* message) {
    int bad=!valid,any=0;
    EONSIM_PETSC(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm));
    if(any) throw std::runtime_error(std::string("Distributed MG layout: ")+message);
}
struct RowRecord {
    // Explicit integer representation avoids transmitting DofKey padding and
    // lets MPI convert scalar representations on heterogeneous machines.
    std::array<std::int64_t,11> identity{};
    std::array<double,36> modes{};
};
class RowDatatype {
public:
    RowDatatype() {
        RowRecord sample;
        MPI_Aint base=0,offsets[2]{};
        EONSIM_PETSC(MPI_Get_address(&sample,&base));
        EONSIM_PETSC(MPI_Get_address(sample.identity.data(),&offsets[0]));
        EONSIM_PETSC(MPI_Get_address(sample.modes.data(),&offsets[1]));
        for(auto& offset:offsets) offset-=base;
        const int counts[2]={11,36};
        MPI_Datatype types[2]={MPI_INT64_T,MPI_DOUBLE},raw=MPI_DATATYPE_NULL;
        EONSIM_PETSC(MPI_Type_create_struct(2,counts,offsets,types,&raw));
        const auto error=MPI_Type_create_resized(raw,0,sizeof(RowRecord),&type_);
        MPI_Type_free(&raw);
        EONSIM_PETSC(error);
        EONSIM_PETSC(MPI_Type_commit(&type_));
    }
    ~RowDatatype() { if(type_!=MPI_DATATYPE_NULL) MPI_Type_free(&type_); }
    MPI_Datatype get() const { return type_; }
private:
    MPI_Datatype type_=MPI_DATATYPE_NULL;
};
}

MgRedistribution redistribute_mg_layout(MPI_Comm comm,Mat matrix,
    const std::vector<DofKey>& semantics,
    const std::vector<std::array<double,36>>& candidates,
    const std::vector<unsigned char>& trace,const std::vector<unsigned char>& active) {
    int rank=0,size=1;
    EONSIM_PETSC(MPI_Comm_rank(comm,&rank));
    EONSIM_PETSC(MPI_Comm_size(comm,&size));
    PetscInt begin=0,end=0,n=0,m=0,cbegin=0,cend=0;
    EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    EONSIM_PETSC(MatGetOwnershipRangeColumn(matrix,&cbegin,&cend));
    EONSIM_PETSC(MatGetSize(matrix,&n,&m));
    const auto local=end-begin;
    collective_check(comm,n==m&&begin==cbegin&&end==cend&&local>=0&&
        semantics.size()==static_cast<std::size_t>(local)&&candidates.size()==semantics.size()&&
        trace.size()==semantics.size()&&active.size()==semantics.size(),
        "matrix layout and owned metadata disagree");
    const PetscInt* ranges=nullptr;
    EONSIM_PETSC(MatGetOwnershipRanges(matrix,&ranges));
    using BlockKey=std::tuple<std::int64_t,DofEntity,std::uint16_t,std::uint16_t>;
    std::map<BlockKey,std::vector<PetscInt>> blocks;
    for(PetscInt i=0;i<local;++i) {
        const auto& key=semantics[i];
        blocks[{key.entity,key.kind,key.mode,key.space}].push_back(i);
    }
    struct BoundaryBlock { std::vector<PetscInt> rows; std::map<int,long double> strength; };
    std::vector<BoundaryBlock> boundary;
    std::vector<long double> rank_strength(size,0.);
    bool valid=true;
    for(const auto& block:blocks) {
        BoundaryBlock item{block.second,{}};
        const bool eligible=std::get<1>(block.first)==DofEntity::vertex&&block.second.size()<=512;
        for(const auto row:block.second) {
            for(const auto value:candidates[row]) valid=valid&&std::isfinite(value);
            PetscInt count=0;const PetscInt* columns=nullptr;const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,begin+row,&count,&columns,&values));
            for(PetscInt j=0;j<count;++j) {
                valid=valid&&std::isfinite(values[j]);
                if(!eligible||!active[row]||values[j]==0.||columns[j]>=n||columns[j]<0) continue;
                const int owner=static_cast<int>(std::upper_bound(ranges,ranges+size+1,columns[j])-ranges)-1;
                if(owner!=rank&&owner%2==0) item.strength[owner]+=std::abs(static_cast<long double>(values[j]));
            }
            EONSIM_PETSC(MatRestoreRow(matrix,begin+row,&count,&columns,&values));
        }
        if(eligible&&!item.strength.empty()) {
            for(const auto& edge:item.strength) rank_strength[edge.first]+=edge.second;
            boundary.push_back(std::move(item));
        }
    }
    collective_check(comm,valid,"nonfinite matrix or near-mode coefficient");
    int proposed=-1;
    if(rank%2==1) for(int peer=0;peer<size;++peer)
        if(rank_strength[peer]>0&&(proposed<0||rank_strength[peer]>rank_strength[proposed])) proposed=peer;
    std::vector<double> offers(size,0.),incoming(size,0.);
    if(proposed>=0) offers[proposed]=static_cast<double>(std::min(rank_strength[proposed],
        static_cast<long double>(std::numeric_limits<double>::max())));
    EONSIM_PETSC(MPI_Alltoall(offers.data(),1,MPI_DOUBLE,incoming.data(),1,MPI_DOUBLE,comm));
    int accepted=-1;
    if(rank%2==0) for(int peer=0;peer<size;++peer)
        if(incoming[peer]>0&&(accepted<0||incoming[peer]>incoming[accepted])) accepted=peer;
    std::vector<int> replies(size,0),acknowledgements(size,0);
    if(accepted>=0) replies[accepted]=1;
    EONSIM_PETSC(MPI_Alltoall(replies.data(),1,MPI_INT,acknowledgements.data(),1,MPI_INT,comm));
    const int destination=proposed>=0&&acknowledgements[proposed]?proposed:rank;
    std::vector<unsigned char> migrating(local,0);
    PetscInt migrated=0;
    if(destination!=rank) {
        auto strength=[&](const BoundaryBlock& b) {
            const auto it=b.strength.find(destination);
            return it==b.strength.end()?0.L:it->second;
        };
        std::sort(boundary.begin(),boundary.end(),[&](const auto& a,const auto& b) {
            const auto first=strength(a),second=strength(b);
            return first!=second?first>second:a.rows.front()<b.rows.front();
        });
        const PetscInt budget=std::max<PetscInt>(1,local/8);
        for(const auto& block:boundary) {
            const auto count=static_cast<PetscInt>(block.rows.size());
            if(strength(block)<=0||migrated+count>=local||
               (migrated>0&&migrated+count>budget)) continue;
            for(const auto row:block.rows) migrating[row]=1;
            migrated+=count;
            if(migrated>=budget) break;
        }
    }
    collective_check(comm,migrated<=std::numeric_limits<int>::max(),"metadata exchange exceeds MPI count range");
    std::vector<int> send_counts(size,0),receive_counts(size,0),send_offsets(size,0),receive_offsets(size,0);
    if(destination!=rank) send_counts[destination]=static_cast<int>(migrated);
    EONSIM_PETSC(MPI_Alltoall(send_counts.data(),1,MPI_INT,receive_counts.data(),1,MPI_INT,comm));
    std::int64_t received=0;
    for(int peer=0;peer<size;++peer) {
        receive_offsets[peer]=static_cast<int>(received);
        received+=receive_counts[peer];
    }
    collective_check(comm,received<=std::numeric_limits<int>::max(),"received metadata exceeds MPI count range");
    std::vector<RowRecord> outgoing,incoming_rows(static_cast<std::size_t>(received)),owned;
    outgoing.reserve(migrated);owned.reserve(static_cast<std::size_t>(local-migrated+received));
    for(PetscInt i=0;i<local;++i) {
        const auto& key=semantics[i];
        RowRecord record;
        record.identity={begin+i,key.entity,static_cast<std::int64_t>(key.domain),
            static_cast<std::int64_t>(key.quantity),static_cast<std::int64_t>(key.kind),
            key.component,key.mode,key.space,trace[i],active[i],rank};
        record.modes=candidates[i];
        if(migrating[i]) outgoing.push_back(record);else owned.push_back(record);
    }
    RowDatatype datatype;
    EONSIM_PETSC(MPI_Alltoallv(outgoing.data(),send_counts.data(),send_offsets.data(),datatype.get(),
        incoming_rows.data(),receive_counts.data(),receive_offsets.data(),datatype.get(),comm));
    owned.insert(owned.end(),incoming_rows.begin(),incoming_rows.end());
    std::sort(owned.begin(),owned.end(),[](const auto& a,const auto& b){return a.identity[0]<b.identity[0];});
    collective_check(comm,owned.size()<=static_cast<std::size_t>(std::numeric_limits<PetscInt>::max()),
        "new local row count overflows PetscInt");
    MgRedistribution result;
    EONSIM_PETSC(MPI_Allreduce(&migrated,&result.moved_rows,1,MPIU_INT,MPI_SUM,comm));
    const auto new_local=static_cast<PetscInt>(owned.size());
    PetscInt new_begin=0,new_global=0;
    EONSIM_PETSC(MPI_Exscan(&new_local,&new_begin,1,MPIU_INT,MPI_SUM,comm));
    if(rank==0) new_begin=0;
    EONSIM_PETSC(MPI_Allreduce(&new_local,&new_global,1,MPIU_INT,MPI_SUM,comm));
    collective_check(comm,new_global==n,"ownership migration lost rows");
    EONSIM_PETSC(MatCreateAIJ(comm,local,new_local,n,n,1,nullptr,1,nullptr,result.permutation.put()));
    EONSIM_PETSC(MatSetOption(result.permutation.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_TRUE));
    for(PetscInt i=0;i<new_local;++i) {
        const auto& record=owned[i];const auto& word=record.identity;
        const auto original=static_cast<PetscInt>(word[0]);
        EONSIM_PETSC(MatSetValue(result.permutation.get(),original,new_begin+i,1.,INSERT_VALUES));
        DofKey key;key.entity=word[1];key.domain=static_cast<DofDomain>(word[2]);
        key.quantity=static_cast<DofQuantity>(word[3]);key.kind=static_cast<DofEntity>(word[4]);
        key.component=static_cast<std::uint16_t>(word[5]);key.mode=static_cast<std::uint16_t>(word[6]);
        key.space=static_cast<std::uint16_t>(word[7]);
        result.semantics.push_back(key);result.candidates.push_back(record.modes);
        result.trace.push_back(static_cast<unsigned char>(word[8]));
        result.active.push_back(static_cast<unsigned char>(word[9]));
        result.origin_rank.push_back(static_cast<int>(word[10]));result.original_rows.push_back(original);
    }
    EONSIM_PETSC(MatAssemblyBegin(result.permutation.get(),MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatAssemblyEnd(result.permutation.get(),MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatPtAP(matrix,result.permutation.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,result.matrix.put()));
    return result;
}
} // namespace eonsim
