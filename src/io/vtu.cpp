#include "eonsim/vtu.hpp"

#include <fstream>
#include <iomanip>
#include <stdexcept>

namespace eonsim {
namespace {
void write_piece(const std::filesystem::path& path, const MeshPartition& mesh,
                 const std::vector<PointField>& fields, bool boundary)
{
    std::ofstream out;
    out.exceptions(std::ios::badbit | std::ios::failbit);
    out.open(path);
    out << std::setprecision(17);
    const bool planar=mesh.topological_dimension==2;
    const auto count=planar?(boundary?mesh.edges.size():mesh.cells2.size()):(boundary?mesh.boundary.size():mesh.cells.size());
    const auto arity=[&](std::size_t i) { return planar?(boundary?2:mesh.cells2[i].vertices):(boundary?3:4); };
    const auto vertex=[&](std::size_t i,int a) { return planar?(boundary?mesh.edges[i].nodes[a]:mesh.cells2[i].nodes[a]):(boundary?mesh.boundary[i].nodes[a]:mesh.cells[i].nodes[a]); };
    const auto tag=[&](std::size_t i) { return planar?(boundary?mesh.edges[i].physical_tag:mesh.cells2[i].physical_tag):(boundary?mesh.boundary[i].physical_tag:mesh.cells[i].physical_tag); };
    const auto id=[&](std::size_t i) { return planar?(boundary?mesh.edges[i].global_id:mesh.cells2[i].global_id):(boundary?mesh.boundary[i].global_id:mesh.cells[i].global_id); };
    out << "<?xml version=\"1.0\"?>\n<VTKFile type=\"UnstructuredGrid\" version=\"0.1\" byte_order=\"LittleEndian\">\n"
        << "<UnstructuredGrid><Piece NumberOfPoints=\"" << mesh.nodes.size() << "\" NumberOfCells=\"" << count << "\">\n"
        << "<Points><DataArray type=\"Float64\" NumberOfComponents=\"3\" format=\"ascii\">\n";
    for (const auto& node : mesh.nodes) out << node.position[0] << ' ' << node.position[1] << ' ' << node.position[2] << '\n';
    out << "</DataArray></Points>\n<Cells><DataArray type=\"Int64\" Name=\"connectivity\" format=\"ascii\">\n";
    for (std::size_t i = 0; i < count; ++i) {
        for (int a = 0; a < arity(i); ++a) out << vertex(i,a) << ' ';
        out << '\n';
    }
    out << "</DataArray><DataArray type=\"Int64\" Name=\"offsets\" format=\"ascii\">\n";
    std::size_t offset=0;
    for(std::size_t i=0;i<count;++i) { offset+=arity(i); out << offset << '\n'; }
    out << "</DataArray><DataArray type=\"UInt8\" Name=\"types\" format=\"ascii\">\n";
    for (std::size_t i = 0; i < count; ++i) out << (planar?(boundary?3:(arity(i)==3?5:9)):(boundary?5:10)) << '\n';
    out << "</DataArray></Cells>\n<PointData>\n";
    for(const auto& field : fields) {
        out << "<DataArray type=\"Float64\" Name=\"" << field.name
            << "\" NumberOfComponents=\"" << field.components << "\" format=\"ascii\">\n";
        for(double value : field.values) out << value << '\n';
        out << "</DataArray>";
    }
    out << "<DataArray type=\"Int64\" Name=\"mesh_node_id\" format=\"ascii\">\n";
    for (const auto& node : mesh.nodes) out << node.global_id << '\n';
    out << "</DataArray><DataArray type=\"Int32\" Name=\"owner\" format=\"ascii\">\n";
    for (int owner : mesh.owners) out << owner << '\n';
    out << "</DataArray><DataArray type=\"Int64\" Name=\"algebra_node_id\" format=\"ascii\">\n";
    for (auto id : mesh.algebra_ids) out << id << '\n';
    out << "</DataArray></PointData>\n<CellData><DataArray type=\"Int32\" Name=\"physical_tag\" format=\"ascii\">\n";
    for (std::size_t i = 0; i < count; ++i) out << tag(i) << '\n';
    out << "</DataArray><DataArray type=\"Int64\" Name=\"mesh_element_id\" format=\"ascii\">\n";
    for (std::size_t i = 0; i < count; ++i) out << id(i) << '\n';
    out << "</DataArray></CellData></Piece></UnstructuredGrid></VTKFile>\n";
    out.close();
}
} // namespace

void write_fields(const std::filesystem::path& path, const MeshPartition& mesh,
                  const std::vector<PointField>& fields)
{
    for(const auto& f : fields) {
        if(f.components<1 || f.values.size()!=mesh.nodes.size()*f.components ||
           f.name.empty() || f.name.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")!=std::string::npos)
            throw std::runtime_error("Invalid VTU field");
    }
    if (!path.parent_path().empty()) std::filesystem::create_directories(path.parent_path());
    const auto actual = mesh.ranks == 1 ? path : path.parent_path() / (path.stem().string()+"_rank"+std::to_string(mesh.rank)+".vtu");
    write_piece(actual, mesh, fields, false);
    const auto boundary = actual.parent_path() / (actual.stem().string() + "_boundary.vtu");
    write_piece(boundary, mesh, fields, true);
}

void write_field_index(const std::filesystem::path& path, int ranks, const std::vector<PointField>& fields)
{
    if (ranks == 1) return;
    for (bool boundary : {false, true}) {
        const auto suffix = boundary ? "_boundary" : "";
        std::ofstream out;
        out.exceptions(std::ios::badbit | std::ios::failbit);
        out.open(path.parent_path()/(path.stem().string()+suffix+".pvtu"));
        out << "<?xml version=\"1.0\"?>\n<VTKFile type=\"PUnstructuredGrid\" version=\"0.1\" byte_order=\"LittleEndian\">\n"
               "<PUnstructuredGrid GhostLevel=\"0\"><PPoints><PDataArray type=\"Float64\" NumberOfComponents=\"3\"/></PPoints>\n"
               "<PPointData Scalars=\"u\">";
        for (const auto& field : fields) out << "<PDataArray type=\"Float64\" Name=\"" << field.name << "\" NumberOfComponents=\"" << field.components << "\"/>";
        out << "<PDataArray type=\"Int64\" Name=\"mesh_node_id\"/><PDataArray type=\"Int32\" Name=\"owner\"/>"
               "<PDataArray type=\"Int64\" Name=\"algebra_node_id\"/></PPointData>\n"
               "<PCellData><PDataArray type=\"Int32\" Name=\"physical_tag\"/><PDataArray type=\"Int64\" Name=\"mesh_element_id\"/></PCellData>\n";
        for (int rank = 0; rank < ranks; ++rank)
            out << "<Piece Source=\"" << path.stem().string() << "_rank" << rank << suffix << ".vtu\"/>\n";
        out << "</PUnstructuredGrid></VTKFile>\n";
        out.close();
    }
}
void write_vtu(const std::filesystem::path& path,const MeshPartition& mesh,
               const std::vector<double>& values,const std::vector<double>& exact)
{
    if(values.size()!=exact.size()) throw std::runtime_error("Invalid exact field size");
    std::vector<double> error(values.size());
    for(std::size_t i=0;i<error.size();++i) error[i]=values[i]-exact[i];
    write_fields(path,mesh,{{"u",1,values},{"u_exact",1,exact},{"nodal_error",1,error}});
}
void write_pvtu(const std::filesystem::path& path,int ranks)
{
    write_field_index(path,ranks,{{"u",1,{}},{"u_exact",1,{}},{"nodal_error",1,{}}});
}
} // namespace eonsim
