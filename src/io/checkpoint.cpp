#include "eonsim/checkpoint.hpp"
#include <hdf5.h>
#include <cmath>
#include <fstream>
#include <limits>
#include <stdexcept>
namespace eonsim {
namespace {
struct Handle {
    hid_t id; herr_t(*close)(hid_t);
    Handle(hid_t value,herr_t(*destroy)(hid_t)):id(value),close(destroy) { if(id<0) throw std::runtime_error("Checkpoint HDF5 operation failed"); }
    ~Handle() { close(id); }
    Handle(const Handle&)=delete;
};
void check(herr_t code) { if(code<0) throw std::runtime_error("Checkpoint HDF5 I/O failed"); }
void write(hid_t file,const char* name,hid_t type,std::size_t count,const void* data) {
    const hsize_t n=count; Handle space(H5Screate_simple(1,&n,nullptr),H5Sclose);
    Handle dataset(H5Dcreate2(file,name,type,space.id,H5P_DEFAULT,H5P_DEFAULT,H5P_DEFAULT),H5Dclose);
    check(H5Dwrite(dataset.id,type,H5S_ALL,H5S_ALL,H5P_DEFAULT,data));
}
void read(hid_t file,const char* name,hid_t type,std::size_t count,void* data) {
    Handle dataset(H5Dopen2(file,name,H5P_DEFAULT),H5Dclose),space(H5Dget_space(dataset.id),H5Sclose);
    if(H5Sget_simple_extent_ndims(space.id)!=1 || H5Sget_simple_extent_npoints(space.id)!=static_cast<hssize_t>(count))
        throw std::runtime_error(std::string("Checkpoint field size mismatch: ")+name);
    check(H5Dread(dataset.id,type,H5S_ALL,H5S_ALL,H5P_DEFAULT,data));
}
std::filesystem::path rank_path(const std::filesystem::path& dir,int rank) { return dir/("state_rank"+std::to_string(rank)+".h5"); }
}
std::uint64_t state_signature(const MeshPartition& mesh,const std::string& physics,const std::vector<double>& parameters)
{
    std::uint64_t hash=1469598103934665603ULL;
    auto bytes=[&](const void* data,std::size_t size) { const auto* p=static_cast<const unsigned char*>(data); for(std::size_t i=0;i<size;++i) { hash^=p[i]; hash*=1099511628211ULL; } };
    bytes(physics.data(),physics.size()); bytes(parameters.data(),parameters.size()*sizeof(double));
    for(const auto& n:mesh.nodes) { bytes(&n.global_id,sizeof(n.global_id)); bytes(n.position.data(),n.position.size()*sizeof(double)); }
    for(const auto& c:mesh.cells) { bytes(&c.global_id,sizeof(c.global_id)); bytes(c.nodes.data(),c.nodes.size()*sizeof(LocalId)); bytes(&c.physical_tag,sizeof(c.physical_tag)); }
    for(const auto& f:mesh.boundary) { bytes(f.nodes.data(),f.nodes.size()*sizeof(LocalId)); bytes(&f.physical_tag,sizeof(f.physical_tag)); }
    bytes(mesh.algebra_ids.data(),mesh.algebra_ids.size()*sizeof(GlobalId));
    bytes(mesh.owners.data(),mesh.owners.size()*sizeof(int));
    return hash;
}
void write_checkpoint(MPI_Comm comm,const std::filesystem::path& dir,const MeshPartition& mesh,
                      std::uint64_t signature,const Checkpoint& state)
{
    if(state.step<0) throw std::runtime_error("Negative checkpoint step");
    if(mesh.rank==0) { std::filesystem::create_directories(dir); std::filesystem::remove(dir/"manifest"); }
    MPI_Barrier(comm);
    const auto path=rank_path(dir,mesh.rank),temporary=std::filesystem::path(path.string()+".tmp");
    {
        Handle file(H5Fcreate(temporary.c_str(),H5F_ACC_TRUNC,H5P_DEFAULT,H5P_DEFAULT),H5Fclose);
        const std::uint64_t meta[]={1,static_cast<std::uint64_t>(mesh.rank),static_cast<std::uint64_t>(mesh.ranks),
            mesh.owned_nodes,static_cast<std::uint64_t>(mesh.owned_begin),static_cast<std::uint64_t>(mesh.global_nodes),
            static_cast<std::uint64_t>(mesh.global_cells),signature,static_cast<std::uint64_t>(state.step)};
        write(file.id,"metadata",H5T_NATIVE_UINT64,9,meta);
        for(const auto& field:state.fields) {
            for(double x:field.second) if(!std::isfinite(x)) throw std::runtime_error("Nonfinite accepted checkpoint field");
            write(file.id,field.first.c_str(),H5T_NATIVE_DOUBLE,field.second.size(),field.second.data());
        }
        check(H5Fflush(file.id,H5F_SCOPE_GLOBAL));
    }
    std::filesystem::rename(temporary,path);
    MPI_Barrier(comm);
    if(mesh.rank==0) {
        std::ofstream out; out.exceptions(std::ios::failbit|std::ios::badbit);
        out.open(dir/"manifest.tmp"); out << "EONSim_checkpoint_v1 " << mesh.ranks << ' ' << state.step << '\n'; out.close();
        std::filesystem::rename(dir/"manifest.tmp",dir/"manifest");
    }
    MPI_Barrier(comm);
}
Checkpoint read_checkpoint(const std::filesystem::path& dir,const MeshPartition& mesh,std::uint64_t signature,
                           const std::map<std::string,std::size_t>& sizes)
{
    std::ifstream manifest(dir/"manifest"); std::string format; int ranks=0,step=-1;
    if(!(manifest>>format>>ranks>>step) || format!="EONSim_checkpoint_v1" || ranks!=mesh.ranks || step<0)
        throw std::runtime_error("Incomplete checkpoint or incompatible rank count");
    const auto path=rank_path(dir,mesh.rank);
    if(!std::filesystem::exists(path)) throw std::runtime_error("Missing checkpoint rank file");
    Handle file(H5Fopen(path.c_str(),H5F_ACC_RDONLY,H5P_DEFAULT),H5Fclose);
    std::uint64_t meta[9]{}; read(file.id,"metadata",H5T_NATIVE_UINT64,9,meta);
    if(meta[0]!=1 || meta[1]!=static_cast<std::uint64_t>(mesh.rank) || meta[2]!=static_cast<std::uint64_t>(mesh.ranks)
       || meta[3]!=mesh.owned_nodes || meta[4]!=static_cast<std::uint64_t>(mesh.owned_begin)
       || meta[5]!=static_cast<std::uint64_t>(mesh.global_nodes) || meta[6]!=static_cast<std::uint64_t>(mesh.global_cells)
       || meta[7]!=signature || meta[8]!=static_cast<std::uint64_t>(step))
        throw std::runtime_error("Checkpoint mesh/partition/physics mismatch");
    Checkpoint state; state.step=step;
    for(const auto& field:sizes) {
        auto& values=state.fields[field.first]; values.resize(field.second);
        read(file.id,field.first.c_str(),H5T_NATIVE_DOUBLE,values.size(),values.data());
        for(double x:values) if(!std::isfinite(x)) throw std::runtime_error("Nonfinite checkpoint field");
    }
    return state;
}
}
