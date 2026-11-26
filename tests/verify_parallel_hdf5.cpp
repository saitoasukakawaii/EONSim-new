/** Shared result files: ownership, mixed topology, empty selections and publication. */
#include "eonsim/vtu.hpp"
#include <hdf5.h>
#include <array>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>

using namespace eonsim;
namespace {
void require(bool condition,const char* message) {if(!condition)throw std::runtime_error(message);}
std::string bytes(const std::filesystem::path& path) {
    std::ifstream input(path,std::ios::binary);require(bool(input),"Cannot read verification output");
    return {std::istreambuf_iterator<char>(input),{}};
}
std::filesystem::path payload(const std::filesystem::path& index) {
    const auto xml=bytes(index);const auto begin=xml.find("Format=\"HDF\">");
    require(begin!=std::string::npos,"XDMF has no HDF data item");
    const auto start=begin+13,end=xml.find(":/",start);
    require(end!=std::string::npos,"Invalid XDMF HDF reference");
    return index.parent_path()/xml.substr(start,end-start);
}
template<class T> std::vector<T> read(hid_t file,const char* name,hid_t type,const std::vector<hsize_t>& shape) {
    const auto dataset=H5Dopen2(file,name,H5P_DEFAULT);require(dataset>=0,"Missing HDF5 dataset");
    const auto space=H5Dget_space(dataset);require(space>=0,"Missing HDF5 dataspace");
    require(H5Sget_simple_extent_ndims(space)==static_cast<int>(shape.size()),"HDF5 dataset rank mismatch");
    std::vector<hsize_t> dims(shape.size());H5Sget_simple_extent_dims(space,dims.data(),nullptr);
    require(dims==shape,"HDF5 dataset extent mismatch");
    std::size_t count=1;for(auto n:shape)count*=n;
    std::vector<T> values(count);if(count)require(H5Dread(dataset,type,H5S_ALL,H5S_ALL,H5P_DEFAULT,values.data())>=0,"HDF5 read failed");
    require(H5Sclose(space)>=0&&H5Dclose(dataset)>=0,"HDF5 reader close failed");return values;
}
MeshPartition fixture(int rank,int ranks) {
    MeshPartition mesh;mesh.rank=rank;mesh.ranks=ranks;mesh.global_nodes=4;mesh.global_cells=1;
    mesh.owned_begin=ranks==1?0:std::min(rank,2)*2;
    mesh.owned_nodes=ranks==1?4:(rank<2?2:0);
    const std::array<Point,4> positions{{{{0,0,0}},{{1,0,0}},{{0,1,0}},{{0,0,1}}}};
    for(GlobalId i=mesh.owned_begin;i<mesh.owned_begin+static_cast<GlobalId>(mesh.owned_nodes);++i) {
        mesh.nodes.push_back({1001+i,positions[i]});mesh.algebra_ids.push_back(i);mesh.owners.push_back(rank);
    }
    if(rank==0) {
        for(GlobalId i=mesh.owned_nodes;i<4;++i) {
            mesh.nodes.push_back({1001+i,positions[i]});mesh.algebra_ids.push_back(i);mesh.owners.push_back(1);
        }
        mesh.cells.push_back({2001,{0,1,2,3},10});mesh.boundary.push_back({3001,{0,2,1},20});
    }
    return mesh;
}
std::vector<PointField> fields(const MeshPartition& mesh,double increment=0) {
    std::vector<PointField> result{{"pressure",1,{}},{"velocity",3,{}}};
    for(auto n:mesh.algebra_ids) {
        result[0].values.push_back(10+2*n+increment);
        result[1].values.insert(result[1].values.end(),{double(n),double(n)+1,double(n)+2});
    }
    return result;
}
void inspect(const std::filesystem::path& index,int ranks,double increment=0) {
    const auto file=H5Fopen(payload(index).c_str(),H5F_ACC_RDONLY,H5P_DEFAULT);require(file>=0,"Cannot open shared HDF5 payload");
    require(read<std::int64_t>(file,"/Mesh/mesh_node_id",H5T_NATIVE_INT64,{4})==std::vector<std::int64_t>({1001,1002,1003,1004}),"Owned point identity mismatch");
    require(read<std::int64_t>(file,"/Mesh/algebra_node_id",H5T_NATIVE_INT64,{4})==std::vector<std::int64_t>({0,1,2,3}),"Algebra identity mismatch");
    const std::vector<std::int32_t> expected_owners=ranks==1?std::vector<std::int32_t>{0,0,0,0}:std::vector<std::int32_t>{0,0,1,1};
    require(read<std::int32_t>(file,"/Mesh/owner",H5T_NATIVE_INT32,{4})==expected_owners,"Node owners mismatch");
    require(read<double>(file,"/Mesh/coordinates",H5T_NATIVE_DOUBLE,{4,3})==std::vector<double>({0,0,0,1,0,0,0,1,0,0,0,1}),"Coordinates mismatch");
    require(read<double>(file,"/Fields/pressure",H5T_NATIVE_DOUBLE,{4})==std::vector<double>({10+increment,12+increment,14+increment,16+increment}),"Point field mismatch");
    require(read<double>(file,"/Fields/velocity",H5T_NATIVE_DOUBLE,{4,3})==std::vector<double>({0,1,2,1,2,3,2,3,4,3,4,5}),"Vector field mismatch");
    require(read<std::int64_t>(file,"/Volume/connectivity",H5T_NATIVE_INT64,{1,4})==std::vector<std::int64_t>({0,1,2,3}),"Ghost connectivity did not use global algebra IDs");
    require(read<std::int64_t>(file,"/Boundary/connectivity",H5T_NATIVE_INT64,{1,3})==std::vector<std::int64_t>({0,2,1}),"Boundary orientation mismatch");
    require(read<std::int32_t>(file,"/Volume/physical_tag",H5T_NATIVE_INT32,{1})==std::vector<std::int32_t>({10}),"Cell tag mismatch");
    require(read<std::int64_t>(file,"/Boundary/mesh_element_id",H5T_NATIVE_INT64,{1})==std::vector<std::int64_t>({3001}),"Boundary stable ID mismatch");
    const auto modes=read<std::uint64_t>(file,"/Partition/io_modes",H5T_NATIVE_UINT64,{static_cast<hsize_t>(ranks),3});
    for(int r=0;r<ranks;++r) {
        require(modes[3*r]>0&&modes[3*r]==modes[3*r+1]+modes[3*r+2],"Invalid actual I/O diagnostics");
        if(ranks>1)require(modes[3*r+1]>0,"No actual collective I/O occurred");
    }
    require(H5Fclose(file)>=0,"HDF5 reader file close failed");
    const auto xml=bytes(index);
    require(xml.find("NumberOfElements=\"1\"")!=std::string::npos&&xml.find("Center=\"Node\"")!=std::string::npos,"Invalid XDMF topology/fields");
}
void verify(const std::filesystem::path& directory) {
    int rank,ranks;MPI_Comm_rank(MPI_COMM_WORLD,&rank);MPI_Comm_size(MPI_COMM_WORLD,&ranks);
    if(rank==0){std::filesystem::remove_all(directory);std::filesystem::create_directories(directory);}
    MPI_Barrier(MPI_COMM_WORLD);
    VtuOptions options;options.hdf5=true;configure_vtu_output(options,MPI_COMM_WORLD);
    auto mesh=fixture(rank,ranks);const auto path=directory/"solution.vtu",index=directory/"solution.xdmf";
    auto values=fields(mesh);
    write_fields(path,mesh,values);
    const auto first=bytes(index);
    const auto old_payload=payload(index);
    if(rank==0)inspect(index,ranks);
    MPI_Barrier(MPI_COMM_WORLD);
    const auto fail_all=[&](const auto& action,const char* reason) {
        bool failed=false;try {action();}catch(const std::exception& e){failed=std::string(e.what()).find(reason)!=std::string::npos;}
        int failed_local=failed?1:0,failed_global=0;MPI_Allreduce(&failed_local,&failed_global,1,MPI_INT,MPI_SUM,MPI_COMM_WORLD);
        require(failed_global==ranks,"I/O failure was not propagated to every rank");
        require(bytes(index)==first&&std::filesystem::exists(old_payload),"Failed output changed previous published snapshot");
    };
    auto invalid=values;if(rank==ranks-1)invalid[0].values.push_back(0);
    fail_all([&]{write_fields(path,mesh,invalid);},"input validation");
    if(ranks>1) {
        auto different=values;if(rank==ranks-1)different[0].name="different";
        fail_all([&]{write_fields(path,mesh,different);},"schema agreement");
    }
    if(rank==0)std::filesystem::create_directory(directory/"solution.xdmf.tmp");
    MPI_Barrier(MPI_COMM_WORLD);
    fail_all([&]{write_fields(path,mesh,fields(mesh,3));},"index publication");
    if(rank==0)std::filesystem::remove(directory/"solution.xdmf.tmp");
    MPI_Barrier(MPI_COMM_WORLD);
    write_fields(path,mesh,fields(mesh,3));
    if(rank==0) {
        inspect(index,ranks,3);require(payload(index)!=old_payload&&!std::filesystem::exists(old_payload),"Snapshot overwrite did not reclaim its own prior payload");
        int live=0;for(const auto& item:std::filesystem::directory_iterator(directory))
            if(item.path().filename().string().rfind("solution.data.",0)==0)++live;
        require(live==1,"Repeated current output leaked unreferenced payloads");
    }
    MPI_Barrier(MPI_COMM_WORLD);
    auto planar=mesh;planar.topological_dimension=2;planar.cells.clear();planar.boundary.clear();
    for(std::size_t n=0;n<planar.nodes.size();++n)if(planar.algebra_ids[n]==3)planar.nodes[n].position={1,1,0};
    if(rank==0) {
        planar.cells2.push_back({5001,{0,1,2,0},31,3});planar.cells2.push_back({5002,{0,1,3,2},32,4});
        planar.edges.push_back({6001,{0,1},40});
    }
    write_fields(directory/"planar.vtu",planar,values);
    if(rank==0) {
        const auto file=H5Fopen(payload(directory/"planar.xdmf").c_str(),H5F_ACC_RDONLY,H5P_DEFAULT);require(file>=0,"Cannot read planar output");
        require(read<std::int64_t>(file,"/Volume/connectivity",H5T_NATIVE_INT64,{9})==std::vector<std::int64_t>({4,0,1,2,5,0,1,3,2}),"Mixed Tri3/Quad4 XDMF connectivity mismatch");
        require(read<std::int64_t>(file,"/Boundary/connectivity",H5T_NATIVE_INT64,{1,2})==std::vector<std::int64_t>({0,1}),"Boundary edge connectivity mismatch");
        require(H5Fclose(file)>=0,"Planar file close failed");
    }
    MPI_Barrier(MPI_COMM_WORLD);
    MeshPartition empty;empty.rank=rank;empty.ranks=ranks;
    write_fields(directory/"empty.vtu",empty,{{"pressure",1,{}}});
    if(rank==0) {
        const auto file=H5Fopen(payload(directory/"empty.xdmf").c_str(),H5F_ACC_RDONLY,H5P_DEFAULT);require(file>=0,"Cannot read empty output");
        require(read<double>(file,"/Mesh/coordinates",H5T_NATIVE_DOUBLE,{0,3}).empty(),"Globally empty coordinates failed");
        require(read<std::int64_t>(file,"/Volume/connectivity",H5T_NATIVE_INT64,{0,4}).empty(),"Globally empty cells failed");
        require(H5Fclose(file)>=0,"Empty file close failed");
        write_output_time_series(directory/"solution.pvd",{{.1,"solution.xdmf"},{.2,"planar.xdmf"}});
        require(bytes(directory/"solution.series.xdmf").find("CollectionType=\"Temporal\"")!=std::string::npos,"Temporal XDMF collection missing");
        std::cout<<"Parallel HDF5 ownership, empty selections, mixed topology, collective failures and publication passed on "<<ranks<<" ranks\n";
    }
    MPI_Barrier(MPI_COMM_WORLD);
}
}
int main(int argc,char** argv) {
    MPI_Init(&argc,&argv);
    try {require(argc==2,"Expected dedicated verification directory");verify(argv[1]);}
    catch(const std::exception& e){std::cerr<<e.what()<<'\n';MPI_Abort(MPI_COMM_WORLD,1);}
    return MPI_Finalize();
}
