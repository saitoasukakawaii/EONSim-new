#include "parallel_hdf5.hpp"
#include <hdf5.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <locale>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>

namespace eonsim::output_detail {
std::string xml_escape(std::string_view value) {
    std::string result;
    for(char c:value) {
        switch(c) {
        case '&':result+="&amp;";break;
        case '<':result+="&lt;";break;
        case '>':result+="&gt;";break;
        case '\"':result+="&quot;";break;
        case '\'':result+="&apos;";break;
        default:result+=c;
        }
    }
    return result;
}

bool parallel_hdf5_available() noexcept {
#ifdef H5_HAVE_PARALLEL
    return true;
#else
    return false;
#endif
}

#ifdef H5_HAVE_PARALLEL
namespace {
using Count=std::uint64_t;
// Only payloads produced by this process for an already published entry are
// eligible for reclamation. Never parse an arbitrary pre-existing XML file to
// obtain a deletion target. Each snapshot name has one live owned generation.
std::map<std::filesystem::path,std::filesystem::path> published_payloads;

// Local validation, allocation and rank-zero publication must finish on every
// rank before the next collective HDF5 call. No rank returns early on an error.
template<class Work> void local_stage(MPI_Comm comm,const char* phase,const Work& work) {
    int rank; MPI_Comm_rank(comm,&rank);
    std::string error;
    try {work();} catch(const std::exception& e) {error=e.what();}
    int failed=error.empty()?std::numeric_limits<int>::max():rank,first=0;
    MPI_Allreduce(&failed,&first,1,MPI_INT,MPI_MIN,comm);
    if(first==std::numeric_limits<int>::max()) return;
    int length=static_cast<int>(std::min<std::size_t>(error.size(),4096));
    MPI_Bcast(&length,1,MPI_INT,first,comm);
    error.resize(length);MPI_Bcast(error.data(),length,MPI_CHAR,first,comm);
    throw std::runtime_error(std::string("Parallel HDF5 ")+phase+" failed on rank "+std::to_string(first)+": "+error);
}

void broadcast_string(MPI_Comm comm,int rank,std::string& value) {
    int length=rank==0?static_cast<int>(value.size()):0;
    MPI_Bcast(&length,1,MPI_INT,0,comm);
    value.resize(length);MPI_Bcast(value.data(),length,MPI_CHAR,0,comm);
}

// A failed collective file/dataset operation is not a recoverable time-step
// rejection. Abort collectively before stack unwinding can attempt H5Fclose on
// a subset of valid handles. Locally invalid inputs and XML errors use stage().
void h5_collective_check(MPI_Comm comm,bool ok,const char* phase) {
    int bad=ok?0:1,any=0;MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm);
    if(!any) return;
    int rank;MPI_Comm_rank(comm,&rank);
    if(!ok) std::cerr<<"Parallel HDF5 "<<phase<<" failed on rank "<<rank<<'\n'<<std::flush;
    MPI_Abort(comm,1);
    throw std::runtime_error("MPI_Abort returned after parallel HDF5 failure");
}

struct Handle {
    hid_t id=-1;
    herr_t(*destroy)(hid_t)=nullptr;
    Handle()=default;
    Handle(hid_t value,herr_t(*close)(hid_t)):id(value),destroy(close) {}
    ~Handle(){if(id>=0&&destroy)destroy(id);}
    Handle(const Handle&)=delete;
    Handle& operator=(const Handle&)=delete;
    bool finish() {if(id<0)return true;const auto old=id;id=-1;return destroy(old)>=0;}
};

void local_check(bool ok) {if(!ok)throw std::runtime_error("HDF5 dataspace/property operation failed");}

struct Topology {
    std::vector<std::int64_t> connectivity,ids;
    std::vector<std::int32_t> tags;
    int width=0; // Zero denotes the 2D mixed Tri3/Quad4 stream.
};

Topology topology(const MeshPartition& mesh,bool boundary) {
    Topology result;
    const bool planar=mesh.topological_dimension==2;
    result.width=planar?(boundary?2:0):(boundary?3:4);
    const auto count=planar?(boundary?mesh.edges.size():mesh.cells2.size()):(boundary?mesh.boundary.size():mesh.cells.size());
    result.ids.reserve(count);result.tags.reserve(count);
    if(count>std::numeric_limits<std::size_t>::max()/5)throw std::runtime_error("Connectivity size overflow");
    result.connectivity.reserve(count*(result.width?result.width:5));
    const auto add=[&](const auto& cell,int vertices) {
        if(vertices<2||vertices>4)throw std::runtime_error("Unsupported HDF5 first-order cell topology");
        result.ids.push_back(cell.global_id);result.tags.push_back(cell.physical_tag);
        if(!result.width) result.connectivity.push_back(vertices==3?4:5); // XDMF Mixed codes.
        for(int a=0;a<vertices;++a) {
            const auto node=cell.nodes[a];
            if(node<0||static_cast<std::size_t>(node)>=mesh.nodes.size())
                throw std::runtime_error("Invalid HDF5 cell node");
            result.connectivity.push_back(mesh.algebra_ids[node]);
        }
    };
    if(planar) {
        if(boundary)for(const auto& cell:mesh.edges)add(cell,2);
        else for(const auto& cell:mesh.cells2) {
            if(cell.vertices!=3&&cell.vertices!=4)throw std::runtime_error("HDF5 2D output requires Tri3 or Quad4");
            add(cell,cell.vertices);
        }
    } else {
        if(boundary)for(const auto& cell:mesh.boundary)add(cell,3);
        else for(const auto& cell:mesh.cells)add(cell,4);
    }
    return result;
}

struct Writer {
    MPI_Comm comm;
    hid_t file,transfer;
    std::array<Count,3> modes{}; // nonempty writes, actual collective, actual other.
    void dataset(const char* name,hid_t file_type,hid_t memory_type,Count global,Count begin,
                 Count count,int width,const void* data) {
        Handle file_space,mem_space;
        local_stage(comm,"dataset selection",[&] {
            if(width<1||begin>global||count>global-begin)throw std::runtime_error("Invalid HDF5 hyperslab");
            const hsize_t extent[2]={global,static_cast<hsize_t>(width)};
            const hsize_t local[2]={std::max<Count>(1,count),static_cast<hsize_t>(width)};
            const hsize_t offset[2]={begin,0},selection[2]={count,static_cast<hsize_t>(width)};
            const int dimensions=width==1?1:2;
            file_space.id=H5Screate_simple(dimensions,extent,nullptr);file_space.destroy=H5Sclose;
            mem_space.id=H5Screate_simple(dimensions,local,nullptr);mem_space.destroy=H5Sclose;
            local_check(file_space.id>=0&&mem_space.id>=0);
            if(count) local_check(H5Sselect_hyperslab(file_space.id,H5S_SELECT_SET,offset,nullptr,selection,nullptr)>=0);
            else local_check(H5Sselect_none(file_space.id)>=0&&H5Sselect_none(mem_space.id)>=0);
        });
        Handle set(H5Dcreate2(file,name,file_type,file_space.id,H5P_DEFAULT,H5P_DEFAULT,H5P_DEFAULT),H5Dclose);
        h5_collective_check(comm,set.id>=0,"dataset creation");
        const double dummy=0;
        h5_collective_check(comm,H5Dwrite(set.id,memory_type,mem_space.id,file_space.id,transfer,count?data:&dummy)>=0,"dataset write");
        H5D_mpio_actual_io_mode_t mode=H5D_MPIO_NO_COLLECTIVE;
        local_stage(comm,"transfer diagnostics",[&] {
            local_check(H5Pget_mpio_actual_io_mode(transfer,&mode)>=0);
            if(count) {
                ++modes[0];
                ++modes[(mode==H5D_MPIO_CONTIGUOUS_COLLECTIVE||mode==H5D_MPIO_CHUNK_COLLECTIVE)?1:2];
            }
        });
        h5_collective_check(comm,set.finish(),"dataset close");
        local_stage(comm,"dataspace close",[&] {const bool a=mem_space.finish(),b=file_space.finish();local_check(a&&b);});
    }
};

void xdmf_item(std::ostream& out,const std::string& payload,const std::string& name,
               Count count,int width,const char* type,int precision) {
    out<<"<DataItem Dimensions=\""<<count;
    if(width>1)out<<' '<<width;
    out<<"\" NumberType=\""<<type<<"\" Precision=\""<<precision<<"\" Format=\"HDF\">"
       <<xml_escape(payload)<<":"<<name<<"</DataItem>\n";
}

void xdmf_grid(std::ostream& out,const std::string& payload,const char* group,
               const MeshPartition& mesh,const std::vector<FieldView>& fields,Count cells,Count connectivity,int width) {
    out<<"<Grid Name=\""<<group<<"\" GridType=\"Uniform\">\n";
    const bool boundary=std::string_view(group)=="Boundary";
    const char* kind=width==0?"Mixed":(width==2?"Polyline":(width==3?"Triangle":"Tetrahedron"));
    out<<"<Topology TopologyType=\""<<kind<<"\" NumberOfElements=\""<<cells<<'"';
    if(width==2)out<<" NodesPerElement=\"2\"";
    out<<">\n";
    const std::string prefix=std::string("/")+group;
    xdmf_item(out,payload,prefix+"/connectivity",width?cells:connectivity,width?width:1,"Int",8);
    out<<"</Topology><Geometry GeometryType=\"XYZ\">\n";
    xdmf_item(out,payload,"/Mesh/coordinates",mesh.global_nodes,3,"Float",8);
    out<<"</Geometry>\n";
    const auto attribute=[&](std::string_view name,const std::string& dataset,Count count,int components,
                             const char* center,const char* type,int precision) {
        const char* shape=components==1?"Scalar":(components<=3?"Vector":(components==6?"Tensor6":(components==9?"Tensor":"Matrix")));
        out<<"<Attribute Name=\""<<xml_escape(name)<<"\" AttributeType=\""<<shape<<"\" Center=\""<<center<<"\">\n";
        xdmf_item(out,payload,dataset,count,components,type,precision);out<<"</Attribute>\n";
    };
    for(const auto& field:fields)attribute(field.name,"/Fields/"+std::string(field.name),mesh.global_nodes,field.components,"Node","Float",8);
    attribute("mesh_node_id","/Mesh/mesh_node_id",mesh.global_nodes,1,"Node","Int",8);
    attribute("algebra_node_id","/Mesh/algebra_node_id",mesh.global_nodes,1,"Node","Int",8);
    attribute("owner","/Mesh/owner",mesh.global_nodes,1,"Node","Int",4);
    attribute("physical_tag",prefix+"/physical_tag",cells,1,"Cell","Int",4);
    attribute("mesh_element_id",prefix+"/mesh_element_id",cells,1,"Cell","Int",8);
    if(boundary)out<<"<Information Name=\"SharedPoints\" Value=\"Boundary reuses the global owned point datasets\"/>\n";
    out<<"</Grid>\n";
}
}
#endif

void write_parallel_hdf5(MPI_Comm comm,const std::filesystem::path& path,
                         const MeshPartition& mesh,const std::vector<FieldView>& fields,bool boundary) {
#ifndef H5_HAVE_PARALLEL
    (void)comm;(void)path;(void)mesh;(void)fields;(void)boundary;
    throw std::runtime_error("HDF5 output requires a parallel HDF5 build");
#else
    if(comm==MPI_COMM_NULL)throw std::runtime_error("HDF5 output requires a valid communicator");
    int rank=0,ranks=0;MPI_Comm_rank(comm,&rank);MPI_Comm_size(comm,&ranks);
    Topology volume,faces;
    std::vector<double> coordinates,subtracted;
    std::vector<std::int64_t> node_ids,algebra_ids;
    std::vector<std::int32_t> owners;
    std::string schema;
    local_stage(comm,"input validation",[&] {
        if(mesh.rank!=rank||mesh.ranks!=ranks||mesh.global_nodes<0||mesh.owned_begin<0||
           mesh.owned_nodes>mesh.nodes.size()||mesh.owners.size()!=mesh.nodes.size()||
           mesh.algebra_ids.size()!=mesh.nodes.size()||(mesh.topological_dimension!=2&&mesh.topological_dimension!=3))
            throw std::runtime_error("Invalid HDF5 mesh ownership/communicator");
        if(mesh.owned_nodes>std::numeric_limits<std::size_t>::max()/3)throw std::runtime_error("HDF5 point size overflow");
        for(std::size_t n=0;n<mesh.nodes.size();++n) {
            if(mesh.algebra_ids[n]<0||mesh.algebra_ids[n]>=mesh.global_nodes||mesh.owners[n]<0||mesh.owners[n]>=ranks||
               (n<mesh.owned_nodes&&(mesh.owners[n]!=rank||mesh.algebra_ids[n]!=mesh.owned_begin+static_cast<GlobalId>(n))))
                throw std::runtime_error("Invalid HDF5 owned/ghost node identity");
        }
        std::set<std::string_view> names;
        std::ostringstream description;description<<path.string()<<'\n'<<mesh.global_nodes<<' '<<mesh.topological_dimension<<' '<<boundary<<'\n';
        for(const auto& f:fields) {
            if(f.components<1||mesh.nodes.size()>std::numeric_limits<std::size_t>::max()/static_cast<std::size_t>(f.components)||
               f.size!=mesh.nodes.size()*static_cast<std::size_t>(f.components)||(!f.values&&f.size)||
               f.name.empty()||f.name.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")!=std::string_view::npos||
               !names.insert(f.name).second)
                throw std::runtime_error("Invalid HDF5 field");
            description<<f.name<<' '<<f.components<<'\n';
        }
        schema=description.str();
        if(schema.size()>1024*1024)throw std::runtime_error("HDF5 output schema exceeds supported metadata size");
        coordinates.reserve(mesh.owned_nodes*3);node_ids.reserve(mesh.owned_nodes);
        algebra_ids.reserve(mesh.owned_nodes);owners.reserve(mesh.owned_nodes);
        for(std::size_t n=0;n<mesh.owned_nodes;++n) {
            for(double x:mesh.nodes[n].position)coordinates.push_back(x);
            node_ids.push_back(mesh.nodes[n].global_id);algebra_ids.push_back(mesh.algebra_ids[n]);owners.push_back(rank);
        }
        volume=topology(mesh,false);
        if(boundary)faces=topology(mesh,true);
        if(std::any_of(fields.begin(),fields.end(),[](const auto& f){return f.subtract!=nullptr;})) {
            std::size_t maximum=0;for(const auto& f:fields)if(f.subtract)maximum=std::max(maximum,mesh.owned_nodes*static_cast<std::size_t>(f.components));
            subtracted.resize(maximum);
        }
    });
    std::string expected=rank==0?schema:"";broadcast_string(comm,rank,expected);
    local_stage(comm,"schema agreement",[&] {if(schema!=expected)throw std::runtime_error("Output path, dimensions or fields differ across ranks");});
    const std::array<Count,5> counts{{mesh.owned_nodes,volume.ids.size(),volume.connectivity.size(),faces.ids.size(),faces.connectivity.size()}};
    std::array<Count,5> begins{},totals{};
    MPI_Exscan(counts.data(),begins.data(),5,MPI_UINT64_T,MPI_SUM,comm);if(rank==0)begins.fill(0);
    MPI_Allreduce(counts.data(),totals.data(),5,MPI_UINT64_T,MPI_SUM,comm);
    local_stage(comm,"ownership coverage",[&] {
        if(begins[0]!=static_cast<Count>(mesh.owned_begin)||totals[0]!=static_cast<Count>(mesh.global_nodes))
            throw std::runtime_error("Owned points do not cover the global HDF5 dataset exactly once");
    });

    auto entry=path;entry.replace_extension(".xdmf");
    std::string payload_name;
    std::filesystem::path entry_key;
    local_stage(comm,"payload allocation",[&] {
        if(rank!=0)return;
        if(!path.parent_path().empty())std::filesystem::create_directories(path.parent_path());
        entry_key=std::filesystem::weakly_canonical(entry.has_parent_path()?entry.parent_path():std::filesystem::current_path())/entry.filename();
        published_payloads.try_emplace(entry_key,std::filesystem::path{});
        auto generation=static_cast<Count>(std::chrono::high_resolution_clock::now().time_since_epoch().count());
        do {payload_name=path.stem().string()+".data."+std::to_string(generation++)+".h5";}
        while(std::filesystem::exists(path.parent_path()/payload_name));
    });
    broadcast_string(comm,rank,payload_name);
    const auto payload=path.parent_path()/payload_name;
    Handle access,transfer;
    local_stage(comm,"property allocation",[&] {
        access.id=H5Pcreate(H5P_FILE_ACCESS);access.destroy=H5Pclose;
        transfer.id=H5Pcreate(H5P_DATASET_XFER);transfer.destroy=H5Pclose;
        local_check(access.id>=0&&transfer.id>=0);
    });
    // HDF5 duplicates the communicator internally; all ranks must reach this
    // operation after successful local property-list allocation.
    h5_collective_check(comm,H5Pset_fapl_mpio(access.id,comm,MPI_INFO_NULL)>=0,"MPI-IO communicator setup");
    local_stage(comm,"MPI-IO properties",[&] {
        local_check(H5Pset_dxpl_mpio(transfer.id,H5FD_MPIO_COLLECTIVE)>=0);
#if H5_VERSION_GE(1,10,0)
        local_check(H5Pset_all_coll_metadata_ops(access.id,1)>=0&&H5Pset_coll_metadata_write(access.id,1)>=0);
#endif
    });
    Handle file(H5Fcreate(payload.c_str(),H5F_ACC_EXCL,H5P_DEFAULT,access.id),H5Fclose);
    h5_collective_check(comm,file.id>=0,"file creation");
    for(const char* group:{"/Mesh","/Fields","/Volume","/Partition"}) {
        Handle value(H5Gcreate2(file.id,group,H5P_DEFAULT,H5P_DEFAULT,H5P_DEFAULT),H5Gclose);
        h5_collective_check(comm,value.id>=0,"group creation");
        h5_collective_check(comm,value.finish(),"group close");
    }
    if(boundary) {
        Handle value(H5Gcreate2(file.id,"/Boundary",H5P_DEFAULT,H5P_DEFAULT,H5P_DEFAULT),H5Gclose);
        h5_collective_check(comm,value.id>=0,"boundary group creation");
        h5_collective_check(comm,value.finish(),"boundary group close");
    }
    Writer writer{comm,file.id,transfer.id,{}};
    const auto node_dataset=[&](const char* name,hid_t file_type,hid_t memory_type,int width,const void* data) {
        writer.dataset(name,file_type,memory_type,totals[0],begins[0],counts[0],width,data);
    };
    node_dataset("/Mesh/coordinates",H5T_IEEE_F64LE,H5T_NATIVE_DOUBLE,3,coordinates.data());
    node_dataset("/Mesh/mesh_node_id",H5T_STD_I64LE,H5T_NATIVE_INT64,1,node_ids.data());
    node_dataset("/Mesh/algebra_node_id",H5T_STD_I64LE,H5T_NATIVE_INT64,1,algebra_ids.data());
    node_dataset("/Mesh/owner",H5T_STD_I32LE,H5T_NATIVE_INT32,1,owners.data());
    for(const auto& field:fields) {
        const double* data=field.values;
        if(field.subtract) {
            for(std::size_t n=0;n<mesh.owned_nodes*static_cast<std::size_t>(field.components);++n)subtracted[n]=field.value(n);
            data=subtracted.data();
        }
        node_dataset(("/Fields/"+std::string(field.name)).c_str(),H5T_IEEE_F64LE,H5T_NATIVE_DOUBLE,field.components,data);
    }
    const auto cells=[&](const Topology& value,const char* prefix,int index) {
        const std::string group=prefix;
        writer.dataset((group+"/connectivity").c_str(),H5T_STD_I64LE,H5T_NATIVE_INT64,
                       totals[index+(value.width?0:1)],begins[index+(value.width?0:1)],counts[index+(value.width?0:1)],
                       value.width?value.width:1,value.connectivity.data());
        writer.dataset((group+"/mesh_element_id").c_str(),H5T_STD_I64LE,H5T_NATIVE_INT64,totals[index],begins[index],counts[index],1,value.ids.data());
        writer.dataset((group+"/physical_tag").c_str(),H5T_STD_I32LE,H5T_NATIVE_INT32,totals[index],begins[index],counts[index],1,value.tags.data());
    };
    cells(volume,"/Volume",1);if(boundary)cells(faces,"/Boundary",3);
    // Rank-local offsets and actual HDF5 transfer modes are compact evidence;
    // no full mesh/field or per-rank list is gathered to the coordinator.
    std::array<Count,10> layout{};
    for(int i=0;i<5;++i){layout[2*i]=begins[i];layout[2*i+1]=counts[i];}
    writer.dataset("/Partition/offsets_counts",H5T_STD_U64LE,H5T_NATIVE_UINT64,ranks,rank,1,10,layout.data());
    const auto modes=writer.modes;
    writer.dataset("/Partition/io_modes",H5T_STD_U64LE,H5T_NATIVE_UINT64,ranks,rank,1,3,modes.data());
    h5_collective_check(comm,H5Fflush(file.id,H5F_SCOPE_GLOBAL)>=0,"file flush");
    h5_collective_check(comm,file.finish(),"file close");
    local_stage(comm,"property close",[&] {const bool a=transfer.finish(),b=access.finish();local_check(a&&b);});

    // A unique payload plus a single atomic XML rename retains the previous
    // published snapshot when validation, I/O, or final publication fails.
    // After success reclaim only the superseded generation from this writer;
    // repeated current-state output does not accumulate unreferenced payloads.
    try {local_stage(comm,"index publication",[&] {
        if(rank!=0)return;
        auto replacement=payload; // Allocate before publication; swap is noexcept.
        auto temporary=entry;temporary+=".tmp";
        std::ofstream out;out.exceptions(std::ios::badbit|std::ios::failbit);out.open(temporary);
        out.imbue(std::locale::classic());out<<std::setprecision(17);
        out<<"<?xml version=\"1.0\"?>\n<Xdmf Version=\"3.0\"><Domain>\n"
               "<Grid Name=\"EONSim\" GridType=\"Collection\" CollectionType=\"Spatial\">\n";
        xdmf_grid(out,payload_name,"Volume",mesh,fields,totals[1],totals[2],volume.width);
        if(boundary)xdmf_grid(out,payload_name,"Boundary",mesh,fields,totals[3],totals[4],faces.width);
        out<<"</Grid></Domain></Xdmf>\n";out.close();std::filesystem::rename(temporary,entry);
        published_payloads.at(entry_key).swap(replacement);
        if(!replacement.empty()) {
            std::error_code error;std::filesystem::remove(replacement,error);
            if(error)std::cerr<<"Parallel HDF5 retained superseded payload "<<replacement<<": "<<error.message()<<'\n';
        }
    });} catch(...) {
        // All ranks have closed the candidate file. A failed XML publication
        // never made this unique payload reachable, so this writer may remove it.
        if(rank==0) {std::error_code ignored;std::filesystem::remove(payload,ignored);}
        throw;
    }
#endif
}
}
