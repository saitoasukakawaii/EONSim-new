#include "eonsim/vtu.hpp"
#include "parallel_hdf5.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <limits>
#include <locale>
#include <cmath>
#include <stdexcept>
#include <string_view>

namespace eonsim {
namespace {
VtuOptions output_options;
bool output_configured=false,output_started=false;
MPI_Comm output_communicator=MPI_COMM_NULL;

// Borrow fields while writing. The scalar error view avoids allocating/copying
// three complete vectors in write_vtu; other callers retain their PointField API.
using output_detail::FieldView;

std::uint64_t product(std::uint64_t count,std::uint64_t width) {
    if(width&&count>std::numeric_limits<std::uint64_t>::max()/width)
        throw std::runtime_error("VTU array size exceeds UInt64 capacity");
    return count*width;
}

bool little_endian() {
    const std::uint16_t one=1;
    return *reinterpret_cast<const unsigned char*>(&one)==1;
}

template<class T> void write_little(std::ostream& out,T* values,std::size_t count) {
    if(!little_endian()&&sizeof(T)>1) {
        auto* bytes=reinterpret_cast<unsigned char*>(values);
        for(std::size_t i=0;i<count;++i) std::reverse(bytes+i*sizeof(T),bytes+(i+1)*sizeof(T));
    }
    out.write(reinterpret_cast<const char*>(values),static_cast<std::streamsize>(count*sizeof(T)));
}

template<class T> class BinaryBlock {
    std::ostream& out_;
    std::array<T,2048> buffer_;
    std::size_t used_=0;
    std::uint64_t written_=0;
public:
    explicit BinaryBlock(std::ostream& out):out_(out) {}
    void append(T value) {
        buffer_[used_++]=value;
        ++written_;
        if(used_==buffer_.size()) flush();
    }
    void flush() {
        if(used_) write_little(out_,buffer_.data(),used_);
        used_=0;
    }
    void finish(std::uint64_t expected) {
        if(written_!=expected) throw std::runtime_error("VTU binary array length mismatch");
        flush();
    }
};

// Traverse the same array descriptions twice for appended output: first emit
// XML offsets, then stream each payload through a bounded buffer. No complete
// coordinates, remapped fields, connectivity, or encoded file are duplicated.
class ArrayWriter {
    std::ostream& out_;
    bool binary_,payload_;
    std::uint64_t offset_=0;
public:
    ArrayWriter(std::ostream& out,bool binary,bool payload=false)
        :out_(out),binary_(binary),payload_(payload) {}
    void markup(const char* text) {if(!payload_) out_<<text;}
    template<class T,class Emit>
    void array(const char* type,std::string_view name,int components,std::uint64_t count,const Emit& emit) {
        const auto bytes=product(count,sizeof(T));
        if(payload_) {
            auto header=bytes;
            write_little(out_,&header,1);
            BinaryBlock<T> block(out_);
            emit([&](T value) {block.append(value);});
            block.finish(count);
            return;
        }
        out_<<"<DataArray type=\""<<type<<'"';
        if(!name.empty()) out_<<" Name=\""<<name<<'"';
        if(components>1) out_<<" NumberOfComponents=\""<<components<<'"';
        if(binary_) {
            if(offset_>std::numeric_limits<std::uint64_t>::max()-sizeof(std::uint64_t)||
               bytes>std::numeric_limits<std::uint64_t>::max()-offset_-sizeof(std::uint64_t))
                throw std::runtime_error("VTU appended offset exceeds UInt64 capacity");
            out_<<" format=\"appended\" offset=\""<<offset_<<"\"/>\n";
            offset_+=sizeof(std::uint64_t)+bytes;
        } else {
            out_<<" format=\"ascii\">\n";
            emit([&](T value) {out_<<+value<<'\n';});
            out_<<"</DataArray>\n";
        }
    }
};

void write_piece(const std::filesystem::path& path,const MeshPartition& mesh,
                 const std::vector<FieldView>& fields,bool boundary)
{
    static_assert(sizeof(double)==8&&std::numeric_limits<double>::is_iec559,
                  "VTU Float64 requires IEEE 754 binary64");
    const bool planar=mesh.topological_dimension==2;
    const auto count=planar?(boundary?mesh.edges.size():mesh.cells2.size()):(boundary?mesh.boundary.size():mesh.cells.size());
    const auto arity=[&](std::size_t i) {return planar?(boundary?2:mesh.cells2[i].vertices):(boundary?3:4);};
    const auto vertex=[&](std::size_t i,int a) {return planar?(boundary?mesh.edges[i].nodes[a]:mesh.cells2[i].nodes[a]):(boundary?mesh.boundary[i].nodes[a]:mesh.cells[i].nodes[a]);};
    const auto tag=[&](std::size_t i) {return planar?(boundary?mesh.edges[i].physical_tag:mesh.cells2[i].physical_tag):(boundary?mesh.boundary[i].physical_tag:mesh.cells[i].physical_tag);};
    const auto id=[&](std::size_t i) {return planar?(boundary?mesh.edges[i].global_id:mesh.cells2[i].global_id):(boundary?mesh.boundary[i].global_id:mesh.cells[i].global_id);};
    std::uint64_t connectivity_count=0;
    for(std::size_t i=0;i<count;++i) {
        const int vertices=arity(i);
        if(vertices<1||vertices>4||connectivity_count>std::uint64_t(std::numeric_limits<std::int64_t>::max())-vertices)
            throw std::runtime_error("Invalid VTU cell connectivity size");
        connectivity_count+=vertices;
    }
    const bool compact=boundary&&output_options.compact_boundary;
    std::vector<LocalId> original_nodes,compact_ids;
    if(compact) {
        compact_ids.assign(mesh.nodes.size(),-1);
        for(std::size_t i=0;i<count;++i) for(int a=0;a<arity(i);++a) {
            const auto node=vertex(i,a);
            if(node<0||static_cast<std::size_t>(node)>=mesh.nodes.size())
                throw std::runtime_error("Invalid VTU boundary node");
            compact_ids[node]=-2;
        }
        original_nodes.reserve(static_cast<std::size_t>(std::min<std::uint64_t>(mesh.nodes.size(),connectivity_count)));
        for(std::size_t i=0;i<mesh.nodes.size();++i) if(compact_ids[i]==-2) {
            if(i>static_cast<std::size_t>(std::numeric_limits<LocalId>::max()))
                throw std::runtime_error("VTU boundary node exceeds local index capacity");
            compact_ids[i]=static_cast<LocalId>(original_nodes.size());
            original_nodes.push_back(static_cast<LocalId>(i));
        }
    }
    const auto points=compact?original_nodes.size():mesh.nodes.size();
    const auto node_at=[&](std::size_t i)->std::size_t {return compact?static_cast<std::size_t>(original_nodes[i]):i;};
    std::ofstream out;
    out.exceptions(std::ios::badbit|std::ios::failbit);
    out.open(path,std::ios::out|std::ios::binary);
    out.imbue(std::locale::classic());
    out<<std::setprecision(17);
    out<<"<?xml version=\"1.0\"?>\n<VTKFile type=\"UnstructuredGrid\" version=\"0.1\" byte_order=\"LittleEndian\"";
    if(output_options.binary) out<<" header_type=\"UInt64\"";
    out<<">\n<UnstructuredGrid><Piece NumberOfPoints=\""<<points<<"\" NumberOfCells=\""<<count<<"\">\n";
    const auto arrays=[&](ArrayWriter& writer) {
        writer.markup("<Points>\n");
        writer.array<double>("Float64",{},3,product(points,3),[&](const auto& emit) {
            for(std::size_t i=0;i<points;++i) for(double coordinate:mesh.nodes[node_at(i)].position) emit(coordinate);
        });
        writer.markup("</Points>\n<Cells>\n");
        writer.array<std::int64_t>("Int64","connectivity",1,connectivity_count,[&](const auto& emit) {
            for(std::size_t i=0;i<count;++i) for(int a=0;a<arity(i);++a) {
                const auto node=vertex(i,a);
                emit(compact?compact_ids[node]:node);
            }
        });
        writer.array<std::int64_t>("Int64","offsets",1,count,[&](const auto& emit) {
            std::int64_t offset=0;
            for(std::size_t i=0;i<count;++i) {offset+=arity(i);emit(offset);}
        });
        writer.array<std::uint8_t>("UInt8","types",1,count,[&](const auto& emit) {
            for(std::size_t i=0;i<count;++i) emit(planar?(boundary?3:(arity(i)==3?5:9)):(boundary?5:10));
        });
        writer.markup("</Cells>\n<PointData>\n");
        for(const auto& field:fields) writer.array<double>("Float64",field.name,field.components,product(points,field.components),[&](const auto& emit) {
            for(std::size_t i=0;i<points;++i) for(int c=0;c<field.components;++c)
                emit(field.value(node_at(i)*field.components+c));
        });
        writer.array<std::int64_t>("Int64","mesh_node_id",1,points,[&](const auto& emit) {
            for(std::size_t i=0;i<points;++i) emit(mesh.nodes[node_at(i)].global_id);
        });
        writer.array<std::int32_t>("Int32","owner",1,points,[&](const auto& emit) {
            for(std::size_t i=0;i<points;++i) emit(mesh.owners[node_at(i)]);
        });
        writer.array<std::int64_t>("Int64","algebra_node_id",1,points,[&](const auto& emit) {
            for(std::size_t i=0;i<points;++i) emit(mesh.algebra_ids[node_at(i)]);
        });
        writer.markup("</PointData>\n<CellData>\n");
        writer.array<std::int32_t>("Int32","physical_tag",1,count,[&](const auto& emit) {
            for(std::size_t i=0;i<count;++i) emit(tag(i));
        });
        writer.array<std::int64_t>("Int64","mesh_element_id",1,count,[&](const auto& emit) {
            for(std::size_t i=0;i<count;++i) emit(id(i));
        });
        writer.markup("</CellData>\n");
    };
    ArrayWriter metadata(out,output_options.binary);
    arrays(metadata);
    out<<"</Piece></UnstructuredGrid>\n";
    if(output_options.binary) {
        out<<"<AppendedData encoding=\"raw\">\n_";
        ArrayWriter payload(out,true,true);
        arrays(payload);
        out<<"\n</AppendedData>\n";
    }
    out<<"</VTKFile>\n";
    out.close();
}

void write_views(const std::filesystem::path& path,const MeshPartition& mesh,const std::vector<FieldView>& fields) {
    output_started=true;
    if(output_options.hdf5) {
        output_detail::write_parallel_hdf5(output_communicator,path,mesh,fields,output_options.boundary);
        return;
    }
    if(mesh.owners.size()!=mesh.nodes.size()||mesh.algebra_ids.size()!=mesh.nodes.size())
        throw std::runtime_error("Invalid VTU node identity layout");
    for(const auto& f:fields) {
        if(f.components<1||f.size!=product(mesh.nodes.size(),static_cast<std::uint64_t>(f.components))||
           f.name.empty()||f.name.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")!=std::string_view::npos)
            throw std::runtime_error("Invalid VTU field");
    }
    if(!path.parent_path().empty()) std::filesystem::create_directories(path.parent_path());
    const auto actual=mesh.ranks==1?path:path.parent_path()/(path.stem().string()+"_rank"+std::to_string(mesh.rank)+".vtu");
    write_piece(actual,mesh,fields,false);
    if(output_options.boundary)
        write_piece(actual.parent_path()/(actual.stem().string()+"_boundary.vtu"),mesh,fields,true);
}
} // namespace

void configure_vtu_output(const VtuOptions& options,MPI_Comm communicator) {
    if(output_configured||output_started) throw std::runtime_error("VTU output must be configured once before writing");
    if(options.hdf5&&(!output_detail::parallel_hdf5_available()||communicator==MPI_COMM_NULL))
        throw std::runtime_error("HDF5 output requires a parallel HDF5 build and an explicit communicator");
    if(options.hdf5&&options.binary) throw std::runtime_error("HDF5 and binary VTU output are mutually exclusive");
    output_options=options;
    output_communicator=communicator;
    output_configured=true;
}

bool hdf5_output_enabled() noexcept {return output_options.hdf5;}

std::filesystem::path output_dataset_path(const std::filesystem::path& path,int ranks) {
    auto result=path;
    result.replace_extension(output_options.hdf5?".xdmf":(ranks>1?".pvtu":".vtu"));
    return result;
}

void write_output_time_series(const std::filesystem::path& path,
                             const std::vector<std::pair<double,std::string>>& entries) {
    auto target=path;
    if(output_options.hdf5) target=path.parent_path()/(path.stem().string()+".series.xdmf");
    auto temporary=target; temporary+=".tmp";
    std::ofstream out;
    out.exceptions(std::ios::badbit|std::ios::failbit);
    out.open(temporary);
    out.imbue(std::locale::classic());out<<std::setprecision(17);
    if(output_options.hdf5)
        out<<"<?xml version=\"1.0\"?>\n<Xdmf Version=\"3.0\" xmlns:xi=\"http://www.w3.org/2001/XInclude\"><Domain>\n"
               "<Grid Name=\"TimeSeries\" GridType=\"Collection\" CollectionType=\"Temporal\">\n";
    else out<<"<?xml version=\"1.0\"?>\n<VTKFile type=\"Collection\" version=\"0.1\" byte_order=\"LittleEndian\"><Collection>\n";
    for(const auto& [time,file]:entries) {
        if(!std::isfinite(time)) throw std::runtime_error("Invalid output series time");
        const auto escaped=output_detail::xml_escape(file);
        if(output_options.hdf5)
            out<<"<Grid GridType=\"Collection\" CollectionType=\"Spatial\"><Time Value=\""<<time
               <<"\"/><xi:include href=\""<<escaped
               <<"\" xpointer=\"xpointer(/Xdmf/Domain/Grid/Grid)\"/></Grid>\n";
        else out<<"<DataSet timestep=\""<<time<<"\" group=\"\" part=\"0\" file=\""<<escaped<<"\"/>\n";
    }
    out<<(output_options.hdf5?"</Grid></Domain></Xdmf>\n":"</Collection></VTKFile>\n");
    out.close();
    std::filesystem::rename(temporary,target);
}

void write_fields(const std::filesystem::path& path,const MeshPartition& mesh,const std::vector<PointField>& fields) {
    std::vector<FieldView> views;
    views.reserve(fields.size());
    for(const auto& field:fields) views.push_back({field.name,field.components,field.values.data(),field.values.size()});
    write_views(path,mesh,views);
}

void write_field_index(const std::filesystem::path& path,int ranks,const std::vector<PointField>& fields) {
    output_started=true;
    if(output_options.hdf5) return; // Collective writer publishes XDMF after successful close.
    if(ranks==1) return;
    for(bool boundary:{false,true}) {
        if(boundary&&!output_options.boundary) continue;
        const auto suffix=boundary?"_boundary":"";
        std::ofstream out;
        out.exceptions(std::ios::badbit|std::ios::failbit);
        out.open(path.parent_path()/(path.stem().string()+suffix+".pvtu"));
        out<<"<?xml version=\"1.0\"?>\n<VTKFile type=\"PUnstructuredGrid\" version=\"0.1\" byte_order=\"LittleEndian\">\n"
             "<PUnstructuredGrid GhostLevel=\"0\"><PPoints><PDataArray type=\"Float64\" NumberOfComponents=\"3\"/></PPoints>\n"
             "<PPointData Scalars=\"u\">";
        for(const auto& field:fields) out<<"<PDataArray type=\"Float64\" Name=\""<<field.name<<"\" NumberOfComponents=\""<<field.components<<"\"/>";
        out<<"<PDataArray type=\"Int64\" Name=\"mesh_node_id\"/><PDataArray type=\"Int32\" Name=\"owner\"/>"
             "<PDataArray type=\"Int64\" Name=\"algebra_node_id\"/></PPointData>\n"
             "<PCellData><PDataArray type=\"Int32\" Name=\"physical_tag\"/><PDataArray type=\"Int64\" Name=\"mesh_element_id\"/></PCellData>\n";
        for(int rank=0;rank<ranks;++rank)
            out<<"<Piece Source=\""<<path.stem().string()<<"_rank"<<rank<<suffix<<".vtu\"/>\n";
        out<<"</PUnstructuredGrid></VTKFile>\n";
        out.close();
    }
}

void write_vtu(const std::filesystem::path& path,const MeshPartition& mesh,
               const std::vector<double>& values,const std::vector<double>& exact) {
    // HDF5 validates all local view lengths collectively, including exact.
    if(!output_options.hdf5&&values.size()!=exact.size()) throw std::runtime_error("Invalid exact field size");
    write_views(path,mesh,{{"u",1,values.data(),values.size()},
                           {"u_exact",1,exact.data(),exact.size()},
                           {"nodal_error",1,values.data(),values.size(),exact.data()}});
}

void write_pvtu(const std::filesystem::path& path,int ranks) {
    write_field_index(path,ranks,{{"u",1,{}},{"u_exact",1,{}},{"nodal_error",1,{}}});
}
} // namespace eonsim
