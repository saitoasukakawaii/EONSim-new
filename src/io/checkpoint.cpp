#include "eonsim/checkpoint.hpp"
#include <hdf5.h>
#include <cmath>
#include <algorithm>
#include <chrono>
#include <fstream>
#include <limits>
#include <iomanip>
#include <sstream>
#include <stdexcept>
namespace eonsim {
namespace {
struct Handle {
    hid_t id; herr_t(*close)(hid_t);
    Handle(hid_t value,herr_t(*destroy)(hid_t)):id(value),close(destroy) { if(id<0) throw std::runtime_error("Checkpoint HDF5 operation failed"); }
    ~Handle() { if(id>=0) close(id); }
    void finish() { if(close(id)<0) throw std::runtime_error("Checkpoint HDF5 close failed"); id=-1; }
    Handle(const Handle&)=delete;
};
void check(herr_t code) { if(code<0) throw std::runtime_error("Checkpoint HDF5 I/O failed"); }
void write(hid_t file,const char* name,hid_t type,std::size_t count,const void* data) {
    const hsize_t n=count; Handle space(H5Screate_simple(1,&n,nullptr),H5Sclose);
    Handle dataset(H5Dcreate2(file,name,type,space.id,H5P_DEFAULT,H5P_DEFAULT,H5P_DEFAULT),H5Dclose);
    check(H5Dwrite(dataset.id,type,H5S_ALL,H5S_ALL,H5P_DEFAULT,data));
    dataset.finish(); space.finish();
}
void read(hid_t file,const char* name,hid_t type,std::size_t count,void* data) {
    Handle dataset(H5Dopen2(file,name,H5P_DEFAULT),H5Dclose),space(H5Dget_space(dataset.id),H5Sclose);
    if(H5Sget_simple_extent_ndims(space.id)!=1 || H5Sget_simple_extent_npoints(space.id)!=static_cast<hssize_t>(count))
        throw std::runtime_error(std::string("Checkpoint field size mismatch: ")+name);
    check(H5Dread(dataset.id,type,H5S_ALL,H5S_ALL,H5P_DEFAULT,data));
    space.finish(); dataset.finish();
}
std::filesystem::path rank_path(const std::filesystem::path& dir,int rank) { return dir/("state_rank"+std::to_string(rank)+".h5"); }
// 每阶段完成或失败后所有 rank 都到达同一规约；不让单 rank 的 I/O 异常挂住其余参与者。
template<class Work> void stage(MPI_Comm comm,const char* name,const Work& work) {
    int rank; MPI_Comm_rank(comm,&rank);
    std::string error;
    try { work(); } catch(const std::exception& e) { error=e.what(); }
    int failed=error.empty()?std::numeric_limits<int>::max():rank,first;
    MPI_Allreduce(&failed,&first,1,MPI_INT,MPI_MIN,comm);
    if(first==std::numeric_limits<int>::max()) return;
    int size=static_cast<int>(error.size()); MPI_Bcast(&size,1,MPI_INT,first,comm);
    error.resize(size); MPI_Bcast(error.data(),size,MPI_CHAR,first,comm);
    throw std::runtime_error(std::string("Checkpoint ")+name+" failed on rank "+std::to_string(first)+": "+error);
}
void write_text(const std::filesystem::path& path,const std::string& text) {
    std::ofstream out; out.exceptions(std::ios::failbit|std::ios::badbit);
    out.open(path); out<<text; out.close();
}
std::filesystem::path resolve_generation(const std::filesystem::path& directory) {
    if(!std::filesystem::exists(directory/"current")) return directory;
    std::ifstream current(directory/"current"); std::string format,name,extra;
    if(!(current>>format>>name)||format!="EONSim_checkpoint_v3"||current>>extra||
       name.rfind("generation_",0)!=0||name.size()<=11||
       !std::all_of(name.begin()+11,name.end(),[](char c){return c>='0'&&c<='9';}))
        throw std::runtime_error("Invalid checkpoint current pointer");
    return directory/name;
}
}
std::uint64_t state_signature(const MeshPartition& mesh,const std::string& physics,const std::vector<double>& parameters)
{
    std::uint64_t hash=1469598103934665603ULL;
    auto bytes=[&](const void* data,std::size_t size) { const auto* p=static_cast<const unsigned char*>(data); for(std::size_t i=0;i<size;++i) { hash^=p[i]; hash*=1099511628211ULL; } };
    bytes(physics.data(),physics.size()); bytes(parameters.data(),parameters.size()*sizeof(double));
    for(const auto& n:mesh.nodes) { bytes(&n.global_id,sizeof(n.global_id)); bytes(n.position.data(),n.position.size()*sizeof(double)); }
    for(const auto& c:mesh.cells) { bytes(&c.global_id,sizeof(c.global_id)); bytes(c.nodes.data(),c.nodes.size()*sizeof(LocalId)); bytes(&c.physical_tag,sizeof(c.physical_tag)); }
    for(const auto& f:mesh.boundary) { bytes(f.nodes.data(),f.nodes.size()*sizeof(LocalId)); bytes(&f.physical_tag,sizeof(f.physical_tag)); }
    if(mesh.topological_dimension==2) {
        bytes(&mesh.topological_dimension,sizeof(int));
        for(const auto& c:mesh.cells2) { bytes(&c.global_id,sizeof(c.global_id)); bytes(&c.vertices,sizeof(int)); bytes(c.nodes.data(),c.vertices*sizeof(LocalId)); bytes(&c.physical_tag,sizeof(int)); }
        for(const auto& e:mesh.edges) { bytes(e.nodes.data(),e.nodes.size()*sizeof(LocalId)); bytes(&e.physical_tag,sizeof(int)); }
    }
    bytes(mesh.algebra_ids.data(),mesh.algebra_ids.size()*sizeof(GlobalId));
    bytes(mesh.owners.data(),mesh.owners.size()*sizeof(int));
    return hash;
}
void write_checkpoint(MPI_Comm comm,const std::filesystem::path& dir,const MeshPartition& mesh,
                      std::uint64_t signature,const Checkpoint& state)
{
    stage(comm,"validation",[&] {
        if(state.step<0||state.time<0||!(state.next_dt>0)||!std::isfinite(state.time+state.next_dt))
            throw std::runtime_error("Invalid accepted checkpoint clock");
        int rank,ranks; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&ranks);
        if(mesh.rank!=rank||mesh.ranks!=ranks) throw std::runtime_error("Checkpoint communicator/layout mismatch");
    });
    const double clock[]={double(state.step),state.time,state.next_dt}; double low[3],high[3];
    MPI_Allreduce(clock,low,3,MPI_DOUBLE,MPI_MIN,comm); MPI_Allreduce(clock,high,3,MPI_DOUBLE,MPI_MAX,comm);
    for(int i=0;i<3;++i) if(low[i]!=high[i]) throw std::runtime_error("Inconsistent accepted checkpoint clock across ranks");
    std::string generation;
    stage(comm,"generation creation",[&] {
        if(mesh.rank!=0) return;
        std::filesystem::create_directories(dir);
        auto id=static_cast<std::uint64_t>(std::chrono::system_clock::now().time_since_epoch().count());
        do {
            generation="generation_"+std::to_string(id++);
        } while(!std::filesystem::create_directory(dir/generation));
    });
    int length=static_cast<int>(generation.size()); MPI_Bcast(&length,1,MPI_INT,0,comm);
    generation.resize(length); MPI_Bcast(generation.data(),length,MPI_CHAR,0,comm);
    const auto destination=dir/generation;
    stage(comm,"rank write",[&] {
        const auto path=rank_path(destination,mesh.rank);
        Handle file(H5Fcreate(path.c_str(),H5F_ACC_EXCL,H5P_DEFAULT,H5P_DEFAULT),H5Fclose);
        const std::uint64_t meta[]={3,static_cast<std::uint64_t>(mesh.rank),static_cast<std::uint64_t>(mesh.ranks),
            mesh.owned_nodes,static_cast<std::uint64_t>(mesh.owned_begin),static_cast<std::uint64_t>(mesh.global_nodes),
            static_cast<std::uint64_t>(mesh.global_cells),signature,static_cast<std::uint64_t>(state.step)};
        write(file.id,"metadata",H5T_NATIVE_UINT64,9,meta);
        write(file.id,"clock",H5T_NATIVE_DOUBLE,2,clock+1);
        for(const auto& field:state.fields) {
            for(double x:field.second) if(!std::isfinite(x)) throw std::runtime_error("Nonfinite accepted checkpoint field");
            write(file.id,field.first.c_str(),H5T_NATIVE_DOUBLE,field.second.size(),field.second.data());
        }
        check(H5Fflush(file.id,H5F_SCOPE_GLOBAL));
        file.finish();
    });
    stage(comm,"publication",[&] {
        if(mesh.rank!=0) return;
        std::ostringstream manifest;
        manifest<<std::setprecision(17)<<"EONSim_checkpoint_v3 "<<mesh.ranks<<' '<<state.step<<' '<<state.time<<' '<<state.next_dt<<'\n';
        write_text(destination/"manifest",manifest.str());
        write_text(dir/"current.tmp","EONSim_checkpoint_v3 "+generation+"\n");
        // 同一目录内 rename：发布前旧指针与旧代始终可读，禁止先 remove(current)。
        std::filesystem::rename(dir/"current.tmp",dir/"current");
    });
}
Checkpoint read_checkpoint(const std::filesystem::path& dir,const MeshPartition& mesh,std::uint64_t signature,
                           const std::map<std::string,std::size_t>& sizes)
{
    const auto generation=resolve_generation(dir);
    std::ifstream manifest(generation/"manifest"); std::string format,extra; int ranks=0,step=-1;
    double time=0,next_dt=0;
    if(!(manifest>>format>>ranks>>step>>time>>next_dt) || format!="EONSim_checkpoint_v3" || ranks!=mesh.ranks || step<0 ||
        time<0||!(next_dt>0)||!std::isfinite(time+next_dt)||manifest>>extra)
        throw std::runtime_error("Incomplete checkpoint or incompatible rank count");
    const auto path=rank_path(generation,mesh.rank);
    if(!std::filesystem::exists(path)) throw std::runtime_error("Missing checkpoint rank file");
    Handle file(H5Fopen(path.c_str(),H5F_ACC_RDONLY,H5P_DEFAULT),H5Fclose);
    std::uint64_t meta[9]{}; read(file.id,"metadata",H5T_NATIVE_UINT64,9,meta);
    if(meta[0]!=3 || meta[1]!=static_cast<std::uint64_t>(mesh.rank) || meta[2]!=static_cast<std::uint64_t>(mesh.ranks)
       || meta[3]!=mesh.owned_nodes || meta[4]!=static_cast<std::uint64_t>(mesh.owned_begin)
       || meta[5]!=static_cast<std::uint64_t>(mesh.global_nodes) || meta[6]!=static_cast<std::uint64_t>(mesh.global_cells)
       || meta[7]!=signature || meta[8]!=static_cast<std::uint64_t>(step))
        throw std::runtime_error("Checkpoint mesh/partition/physics mismatch");
    Checkpoint state; state.step=step;
    double clock[2]; read(file.id,"clock",H5T_NATIVE_DOUBLE,2,clock); state.time=clock[0]; state.next_dt=clock[1];
    if(state.time!=time||state.next_dt!=next_dt) throw std::runtime_error("Checkpoint clock/manifest mismatch");
    for(const auto& field:sizes) {
        auto& values=state.fields[field.first]; values.resize(field.second);
        read(file.id,field.first.c_str(),H5T_NATIVE_DOUBLE,values.size(),values.data());
        for(double x:values) if(!std::isfinite(x)) throw std::runtime_error("Nonfinite checkpoint field");
    }
    file.finish();
    return state;
}
}
