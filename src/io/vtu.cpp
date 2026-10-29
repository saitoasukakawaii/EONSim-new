#include "eonsim/vtu.hpp"

#include <fstream>
#include <iomanip>
#include <stdexcept>

namespace eonsim {
namespace {
void write_piece(const std::filesystem::path& path, const MeshPartition& mesh,
                 const std::vector<double>& values, const std::vector<double>& exact, bool boundary)
{
    std::ofstream out;
    out.exceptions(std::ios::badbit | std::ios::failbit);
    out.open(path);
    out << std::setprecision(17);
    const auto count = boundary ? mesh.boundary.size() : mesh.cells.size();
    const int arity = boundary ? 3 : 4;
    out << "<?xml version=\"1.0\"?>\n<VTKFile type=\"UnstructuredGrid\" version=\"0.1\" byte_order=\"LittleEndian\">\n"
        << "<UnstructuredGrid><Piece NumberOfPoints=\"" << mesh.nodes.size() << "\" NumberOfCells=\"" << count << "\">\n"
        << "<Points><DataArray type=\"Float64\" NumberOfComponents=\"3\" format=\"ascii\">\n";
    for (const auto& node : mesh.nodes) out << node.position[0] << ' ' << node.position[1] << ' ' << node.position[2] << '\n';
    out << "</DataArray></Points>\n<Cells><DataArray type=\"Int64\" Name=\"connectivity\" format=\"ascii\">\n";
    for (std::size_t i = 0; i < count; ++i) {
        for (int a = 0; a < arity; ++a) out << (boundary ? mesh.boundary[i].nodes[a] : mesh.cells[i].nodes[a]) << ' ';
        out << '\n';
    }
    out << "</DataArray><DataArray type=\"Int64\" Name=\"offsets\" format=\"ascii\">\n";
    for (std::size_t i = 1; i <= count; ++i) out << arity*i << '\n';
    out << "</DataArray><DataArray type=\"UInt8\" Name=\"types\" format=\"ascii\">\n";
    for (std::size_t i = 0; i < count; ++i) out << (boundary ? 5 : 10) << '\n';
    out << "</DataArray></Cells>\n<PointData Scalars=\"u\">\n"
        << "<DataArray type=\"Float64\" Name=\"u\" format=\"ascii\">\n";
    for (double value : values) out << value << '\n';
    out << "</DataArray><DataArray type=\"Float64\" Name=\"u_exact\" format=\"ascii\">\n";
    for (double value : exact) out << value << '\n';
    out << "</DataArray><DataArray type=\"Float64\" Name=\"nodal_error\" format=\"ascii\">\n";
    for (std::size_t i = 0; i < values.size(); ++i) out << values[i]-exact[i] << '\n';
    out << "</DataArray><DataArray type=\"Int64\" Name=\"mesh_node_id\" format=\"ascii\">\n";
    for (const auto& node : mesh.nodes) out << node.global_id << '\n';
    out << "</DataArray><DataArray type=\"Int32\" Name=\"owner\" format=\"ascii\">\n";
    for (int owner : mesh.owners) out << owner << '\n';
    out << "</DataArray><DataArray type=\"Int64\" Name=\"algebra_node_id\" format=\"ascii\">\n";
    for (auto id : mesh.algebra_ids) out << id << '\n';
    out << "</DataArray></PointData>\n<CellData><DataArray type=\"Int32\" Name=\"physical_tag\" format=\"ascii\">\n";
    for (std::size_t i = 0; i < count; ++i) out << (boundary ? mesh.boundary[i].physical_tag : mesh.cells[i].physical_tag) << '\n';
    out << "</DataArray><DataArray type=\"Int64\" Name=\"mesh_element_id\" format=\"ascii\">\n";
    for (std::size_t i = 0; i < count; ++i) out << (boundary ? mesh.boundary[i].global_id : mesh.cells[i].global_id) << '\n';
    out << "</DataArray></CellData></Piece></UnstructuredGrid></VTKFile>\n";
    out.close();
}
} // namespace

void write_vtu(const std::filesystem::path& path, const MeshPartition& mesh,
               const std::vector<double>& values, const std::vector<double>& exact)
{
    if (values.size() != mesh.nodes.size() || exact.size() != mesh.nodes.size())
        throw std::runtime_error("VTU field size does not match the mesh");
    if (!path.parent_path().empty()) std::filesystem::create_directories(path.parent_path());
    const auto actual = mesh.ranks == 1 ? path : path.parent_path() / (path.stem().string()+"_rank"+std::to_string(mesh.rank)+".vtu");
    write_piece(actual, mesh, values, exact, false);
    const auto boundary = actual.parent_path() / (actual.stem().string() + "_boundary.vtu");
    write_piece(boundary, mesh, values, exact, true);
}

void write_pvtu(const std::filesystem::path& path, int ranks)
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
        for (const char* field : {"u", "u_exact", "nodal_error"}) out << "<PDataArray type=\"Float64\" Name=\"" << field << "\"/>";
        out << "<PDataArray type=\"Int64\" Name=\"mesh_node_id\"/><PDataArray type=\"Int32\" Name=\"owner\"/>"
               "<PDataArray type=\"Int64\" Name=\"algebra_node_id\"/></PPointData>\n"
               "<PCellData><PDataArray type=\"Int32\" Name=\"physical_tag\"/><PDataArray type=\"Int64\" Name=\"mesh_element_id\"/></PCellData>\n";
        for (int rank = 0; rank < ranks; ++rank)
            out << "<Piece Source=\"" << path.stem().string() << "_rank" << rank << suffix << ".vtu\"/>\n";
        out << "</PUnstructuredGrid></VTKFile>\n";
        out.close();
    }
}
} // namespace eonsim
