#include "eonsim/mesh.hpp"
#include <hdf5.h>
#include <metis.h>
#include <algorithm>
#include <fstream>
#include <limits>
#include <numeric>
#include <set>
#include <stdexcept>
#include <unordered_map>

namespace eonsim {
namespace {
template<herr_t (*Close)(hid_t)> struct H5Owner {
    hid_t id;
    explicit H5Owner(hid_t value) : id(value) { if (id < 0) throw std::runtime_error("HDF5 operation failed"); }
    ~H5Owner() { Close(id); }
    H5Owner(const H5Owner&) = delete;
};
template<class T> hid_t h5type();
template<> hid_t h5type<double>() { return H5T_NATIVE_DOUBLE; }
template<> hid_t h5type<GlobalId>() { return H5T_NATIVE_INT64; }
template<> hid_t h5type<int>() { return H5T_NATIVE_INT; }
template<> hid_t h5type<std::uint64_t>() { return H5T_NATIVE_UINT64; }
template<class T> void write(hid_t file, const char* name, const std::vector<T>& values) {
    hsize_t count = values.size();
    H5Owner<H5Sclose> space(H5Screate_simple(1, &count, nullptr));
    H5Owner<H5Dclose> data(H5Dcreate2(file, name, h5type<T>(), space.id, H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT));
    if (!values.empty() && H5Dwrite(data.id, h5type<T>(), H5S_ALL, H5S_ALL, H5P_DEFAULT, values.data()) < 0)
        throw std::runtime_error("HDF5 write failed");
}
template<class T> std::vector<T> read(hid_t file, const char* name) {
    H5Owner<H5Dclose> data(H5Dopen2(file, name, H5P_DEFAULT));
    H5Owner<H5Sclose> space(H5Dget_space(data.id));
    hsize_t count = 0;
    if (H5Sget_simple_extent_ndims(space.id) != 1 || H5Sget_simple_extent_dims(space.id, &count, nullptr) < 0 ||
        count > static_cast<hsize_t>(std::numeric_limits<int>::max())) throw std::runtime_error("Invalid HDF5 dataset extent");
    std::vector<T> values(count);
    if (count && H5Dread(data.id, h5type<T>(), H5S_ALL, H5S_ALL, H5P_DEFAULT, values.data()) < 0)
        throw std::runtime_error("HDF5 read failed");
    return values;
}
std::filesystem::path filename(const std::filesystem::path& directory, int rank) {
    return directory / ("rank_" + std::to_string(rank) + ".h5");
}
std::vector<std::set<GlobalId>> adjacency(const MeshPartition& mesh) {
    std::vector<std::set<GlobalId>> rows(mesh.nodes.size());
    for (const auto& cell : mesh.cells) for (auto row : cell.nodes)
        for (auto col : cell.nodes) rows[row].insert(col);
    return rows;
}
std::uint64_t fingerprint(const MeshPartition& mesh, int ranks) {
    std::uint64_t hash = 1469598103934665603ULL;
    const auto append = [&](const void* value, std::size_t n) {
        const auto* data = static_cast<const unsigned char*>(value);
        for (std::size_t i = 0; i < n; ++i) { hash ^= data[i]; hash *= 1099511628211ULL; }
    };
    append(&ranks, sizeof(ranks));
    for (const auto& node : mesh.nodes) { append(&node.global_id, sizeof(node.global_id)); append(node.position.data(), sizeof(Point)); }
    for (const auto& cell : mesh.cells) {
        append(&cell.global_id, sizeof(cell.global_id)); append(cell.nodes.data(), sizeof(cell.nodes)); append(&cell.physical_tag, sizeof(int));
    }
    for (const auto& face : mesh.boundary) { append(face.nodes.data(), sizeof(face.nodes)); append(&face.physical_tag, sizeof(int)); }
    return hash;
}
void save(const MeshPartition& mesh, const std::filesystem::path& path) {
    H5Owner<H5Fclose> file(H5Fcreate(path.string().c_str(), H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT));
    write<GlobalId>(file.id, "meta", {2, mesh.rank, mesh.ranks, static_cast<GlobalId>(mesh.owned_nodes), mesh.owned_begin, mesh.global_nodes, mesh.global_cells});
    write<std::uint64_t>(file.id, "fingerprint", {mesh.fingerprint});
    std::vector<GlobalId> ids;
    std::vector<double> coordinates;
    for (const auto& node : mesh.nodes) { ids.push_back(node.global_id); coordinates.insert(coordinates.end(), node.position.begin(), node.position.end()); }
    write(file.id, "node_ids", ids); write(file.id, "coordinates", coordinates);
    write(file.id, "algebra_ids", mesh.algebra_ids); write(file.id, "owners", mesh.owners);
    std::vector<int> nodes, tags;
    ids.clear();
    for (const auto& cell : mesh.cells) { ids.push_back(cell.global_id); nodes.insert(nodes.end(), cell.nodes.begin(), cell.nodes.end()); tags.push_back(cell.physical_tag); }
    write(file.id, "cell_ids", ids); write(file.id, "cell_nodes", nodes); write(file.id, "cell_tags", tags);
    ids.clear(); nodes.clear(); tags.clear();
    for (const auto& face : mesh.boundary) { ids.push_back(face.global_id); nodes.insert(nodes.end(), face.nodes.begin(), face.nodes.end()); tags.push_back(face.physical_tag); }
    write(file.id, "face_ids", ids); write(file.id, "face_nodes", nodes); write(file.id, "face_tags", tags);
    std::vector<GlobalId> offsets{0}; tags.clear();
    for (const auto& list : mesh.node_boundary_tags) { tags.insert(tags.end(), list.begin(), list.end()); offsets.push_back(tags.size()); }
    write(file.id, "boundary_offsets", offsets); write(file.id, "boundary_tags", tags);
    offsets={0}; tags.clear();
    for(const auto& list:mesh.node_cell_tags) { tags.insert(tags.end(),list.begin(),list.end()); offsets.push_back(tags.size()); }
    write(file.id,"region_offsets",offsets); write(file.id,"region_tags",tags);
    write(file.id, "row_offsets", mesh.row_offsets); write(file.id, "row_columns", mesh.row_columns);
}
} // namespace

void initialize_serial_partition(MeshPartition& mesh) {
    mesh.global_nodes = mesh.nodes.size(); mesh.global_cells = mesh.cells.size(); mesh.owned_nodes = mesh.nodes.size();
    mesh.algebra_ids.resize(mesh.nodes.size());
    std::iota(mesh.algebra_ids.begin(), mesh.algebra_ids.end(), GlobalId{0});
    mesh.owners.assign(mesh.nodes.size(), 0);
    mesh.node_boundary_tags.assign(mesh.nodes.size(),{});
    mesh.node_cell_tags.assign(mesh.nodes.size(),{});
    for(const auto& cell:mesh.cells) for(auto n:cell.nodes) mesh.node_cell_tags[n].push_back(cell.physical_tag);
    for(auto& tags:mesh.node_cell_tags) { std::sort(tags.begin(),tags.end()); tags.erase(std::unique(tags.begin(),tags.end()),tags.end()); }
    for (const auto& face : mesh.boundary) for (auto node : face.nodes) mesh.node_boundary_tags[node].push_back(face.physical_tag);
    for (auto& tags : mesh.node_boundary_tags) { std::sort(tags.begin(), tags.end()); tags.erase(std::unique(tags.begin(), tags.end()), tags.end()); }
    mesh.row_offsets = {0}; mesh.row_columns.clear();
    for (const auto& row : adjacency(mesh)) {
        mesh.row_columns.insert(mesh.row_columns.end(), row.begin(), row.end()); mesh.row_offsets.push_back(mesh.row_columns.size());
    }
    mesh.fingerprint = fingerprint(mesh, 1);
}

void prepare_partitions(const MeshPartition& mesh, int ranks, const std::filesystem::path& directory) {
    if (ranks < 1 || static_cast<std::size_t>(ranks) > mesh.cells.size()) throw std::runtime_error("Invalid partition count");
    if (mesh.cells.size() > static_cast<std::size_t>(std::numeric_limits<idx_t>::max()/Tet4Topology::nodes) ||
        mesh.nodes.size() > static_cast<std::size_t>(std::numeric_limits<idx_t>::max())) throw std::runtime_error("Mesh exceeds METIS index range");
    idx_t ne = mesh.cells.size(), nn = mesh.nodes.size(), parts = ranks, common = Tet4Topology::face_nodes, objective = 0;
    std::vector<idx_t> pointer(ne+1), connectivity, cell_part(ne, 0), node_part(nn);
    for (idx_t i = 0; i < ne; ++i) {
        connectivity.insert(connectivity.end(), mesh.cells[i].nodes.begin(), mesh.cells[i].nodes.end()); pointer[i+1] = connectivity.size();
    }
    if (ranks > 1) {
        idx_t options[METIS_NOPTIONS]; METIS_SetDefaultOptions(options); options[METIS_OPTION_SEED] = 0;
        if (METIS_PartMeshDual(&ne, &nn, pointer.data(), connectivity.data(), nullptr, nullptr, &common,
                              &parts, nullptr, options, &objective, cell_part.data(), node_part.data()) != METIS_OK)
            throw std::runtime_error("METIS_PartMeshDual failed");
    }
    std::vector<int> owners(nn, ranks);
    for (idx_t c = 0; c < ne; ++c) for (auto node : mesh.cells[c].nodes) owners[node] = std::min(owners[node], static_cast<int>(cell_part[c]));
    std::vector<GlobalId> algebra(nn), begins(ranks+1, 0);
    for (int r = 0; r < ranks; ++r) {
        begins[r+1] = begins[r];
        for (idx_t n = 0; n < nn; ++n) if (owners[n] == r) algebra[n] = begins[r+1]++;
    }
    const auto rows = adjacency(mesh);
    std::map<Tri3Topology::Nodal<LocalId>, int> face_owner;
    for (idx_t c = 0; c < ne; ++c) for (int omit = 0; omit < Tet4Topology::faces; ++omit) {
        Tri3Topology::Nodal<LocalId> key{}; int j = 0;
        for (int a = 0; a < Tet4Topology::nodes; ++a) if (a != omit) key[j++] = mesh.cells[c].nodes[a];
        std::sort(key.begin(), key.end()); face_owner[key] = cell_part[c];
    }
    std::filesystem::create_directories(directory);
    // Remove an old completion marker before replacing any partition files.
    std::filesystem::remove(directory / "manifest.yaml");
    for (int rank = 0; rank < ranks; ++rank) {
        MeshPartition local;
        local.rank = rank; local.ranks = ranks; local.global_nodes = nn; local.global_cells = ne;
        local.owned_begin = begins[rank]; local.owned_nodes = begins[rank+1]-begins[rank]; local.fingerprint = fingerprint(mesh, ranks);
        std::set<LocalId> needed;
        for (idx_t c = 0; c < ne; ++c) if (cell_part[c] == rank) needed.insert(mesh.cells[c].nodes.begin(), mesh.cells[c].nodes.end());
        std::vector<LocalId> order;
        for (auto n : needed) if (owners[n] == rank) order.push_back(n);
        for (auto n : needed) if (owners[n] != rank) order.push_back(n);
        std::unordered_map<LocalId,LocalId> lookup;
        for (auto n : order) {
            lookup[n] = local.nodes.size(); local.nodes.push_back(mesh.nodes[n]);
            local.algebra_ids.push_back(algebra[n]); local.owners.push_back(owners[n]); local.node_boundary_tags.push_back(mesh.node_boundary_tags[n]); local.node_cell_tags.push_back(mesh.node_cell_tags[n]);
        }
        for (idx_t c = 0; c < ne; ++c) if (cell_part[c] == rank) {
            auto cell = mesh.cells[c]; for (auto& node : cell.nodes) node = lookup.at(node); local.cells.push_back(cell);
        }
        for (auto face : mesh.boundary) {
            auto key = face.nodes; std::sort(key.begin(), key.end());
            if (face_owner.at(key) == rank) { for (auto& node : face.nodes) node = lookup.at(node); local.boundary.push_back(face); }
        }
        local.row_offsets = {0};
        for (std::size_t i = 0; i < local.owned_nodes; ++i) {
            std::vector<GlobalId> columns;
            for (auto n : rows[order[i]]) columns.push_back(algebra[n]);
            std::sort(columns.begin(), columns.end());
            local.row_columns.insert(local.row_columns.end(), columns.begin(), columns.end()); local.row_offsets.push_back(local.row_columns.size());
        }
        save(local, filename(directory, rank));
    }
    std::ofstream marker(directory / "manifest.yaml");
    marker << "version: 1\nranks: " << ranks << "\nglobal_nodes: " << nn << "\nglobal_cells: " << ne << '\n';
    marker.close(); if (!marker) throw std::runtime_error("Cannot write partition manifest");
}

MeshPartition read_partition(const std::filesystem::path& directory, int rank, int ranks) {
    if (!std::filesystem::exists(directory / "manifest.yaml")) throw std::runtime_error("Incomplete partition directory: no manifest");
    H5Owner<H5Fclose> file(H5Fopen(filename(directory, rank).string().c_str(), H5F_ACC_RDONLY, H5P_DEFAULT));
    const auto meta = read<GlobalId>(file.id, "meta");
    if (meta.size() != 7 || meta[0] != 2 || meta[1] != rank || meta[2] != ranks || meta[3] < 0 || meta[4] < 0 || meta[5] < 1 || meta[6] < 1)
        throw std::runtime_error("Partition metadata does not match this MPI job");
    MeshPartition mesh;
    mesh.rank = rank; mesh.ranks = ranks; mesh.owned_nodes = meta[3]; mesh.owned_begin = meta[4]; mesh.global_nodes = meta[5]; mesh.global_cells = meta[6];
    const auto hash = read<std::uint64_t>(file.id, "fingerprint");
    if (hash.size() != 1) throw std::runtime_error("Invalid partition fingerprint");
    mesh.fingerprint = hash[0];
    auto ids = read<GlobalId>(file.id, "node_ids");
    const auto coordinates = read<double>(file.id, "coordinates");
    mesh.algebra_ids = read<GlobalId>(file.id, "algebra_ids"); mesh.owners = read<int>(file.id, "owners");
    if (coordinates.size() != Space3::dimension*ids.size() || mesh.algebra_ids.size() != ids.size() || mesh.owners.size() != ids.size() || mesh.owned_nodes > ids.size())
        throw std::runtime_error("Inconsistent partition node arrays");
    for (std::size_t i = 0; i < ids.size(); ++i) {
        if (mesh.algebra_ids[i] < 0 || mesh.algebra_ids[i] >= mesh.global_nodes || mesh.owners[i] < 0 || mesh.owners[i] >= ranks ||
            (i < mesh.owned_nodes && (mesh.owners[i] != rank || mesh.algebra_ids[i] != mesh.owned_begin+static_cast<GlobalId>(i))) ||
            (i >= mesh.owned_nodes && mesh.owners[i] == rank)) throw std::runtime_error("Invalid owned/ghost numbering");
        Point point{};
        std::copy_n(coordinates.begin()+Space3::dimension*i, point.size(), point.begin());
        mesh.nodes.push_back({ids[i], point});
    }
    ids = read<GlobalId>(file.id, "cell_ids"); auto nodes = read<int>(file.id, "cell_nodes"); auto tags = read<int>(file.id, "cell_tags");
    const auto check_nodes = [&] { for (int n : nodes) if (n < 0 || static_cast<std::size_t>(n) >= mesh.nodes.size()) throw std::runtime_error("Invalid local connectivity"); };
    if (nodes.size() != Tet4Topology::nodes*ids.size() || tags.size() != ids.size()) throw std::runtime_error("Invalid cell arrays");
    check_nodes();
    for (std::size_t i = 0; i < ids.size(); ++i) {
        Tet4Topology::Nodal<LocalId> connectivity{};
        std::copy_n(nodes.begin()+Tet4Topology::nodes*i, connectivity.size(), connectivity.begin());
        mesh.cells.push_back({ids[i], connectivity, tags[i]});
    }
    ids = read<GlobalId>(file.id, "face_ids"); nodes = read<int>(file.id, "face_nodes"); tags = read<int>(file.id, "face_tags");
    if (nodes.size() != Tri3Topology::nodes*ids.size() || tags.size() != ids.size()) throw std::runtime_error("Invalid boundary arrays");
    check_nodes();
    for (std::size_t i = 0; i < ids.size(); ++i) {
        Tri3Topology::Nodal<LocalId> connectivity{};
        std::copy_n(nodes.begin()+Tri3Topology::nodes*i, connectivity.size(), connectivity.begin());
        mesh.boundary.push_back({ids[i], connectivity, tags[i]});
    }
    const auto offsets = read<GlobalId>(file.id, "boundary_offsets"); tags = read<int>(file.id, "boundary_tags");
    const auto valid_csr = [](const std::vector<GlobalId>& ptr, std::size_t rows, std::size_t entries) {
        return ptr.size() == rows+1 && ptr.front() == 0 && ptr.back() == static_cast<GlobalId>(entries) && std::is_sorted(ptr.begin(),ptr.end());
    };
    if (!valid_csr(offsets, mesh.nodes.size(), tags.size())) throw std::runtime_error("Invalid boundary tag offsets");
    for (std::size_t i = 0; i < mesh.nodes.size(); ++i) mesh.node_boundary_tags.emplace_back(tags.begin()+offsets[i], tags.begin()+offsets[i+1]);
    const auto region_offsets=read<GlobalId>(file.id,"region_offsets"); const auto region_tags=read<int>(file.id,"region_tags");
    if(!valid_csr(region_offsets,mesh.nodes.size(),region_tags.size())) throw std::runtime_error("Invalid node region CSR");
    for(std::size_t i=0;i<mesh.nodes.size();++i) mesh.node_cell_tags.emplace_back(region_tags.begin()+region_offsets[i],region_tags.begin()+region_offsets[i+1]);
    mesh.row_offsets = read<GlobalId>(file.id, "row_offsets"); mesh.row_columns = read<GlobalId>(file.id, "row_columns");
    if (!valid_csr(mesh.row_offsets, mesh.owned_nodes, mesh.row_columns.size())) throw std::runtime_error("Invalid adjacency offsets");
    for (auto col : mesh.row_columns) if (col < 0 || col >= mesh.global_nodes) throw std::runtime_error("Invalid adjacency column");
    return mesh;
}
} // namespace eonsim
