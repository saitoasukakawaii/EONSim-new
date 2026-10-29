#pragma once
/** @file
 * @brief Tet4 网格、稳定 ID 和本地 owned/ghost 数据。 */

#include <array>
#include <cstdint>
#include <filesystem>
#include <map>
#include <string>
#include <vector>

namespace eonsim {

using GlobalId = std::int64_t;
using LocalId = std::int32_t;
using Point = std::array<double, 3>;

struct Node { GlobalId global_id; Point position; };
struct Tet4 { GlobalId global_id; std::array<LocalId, 4> nodes; int physical_tag; };
struct BoundaryTriangle { GlobalId global_id; std::array<LocalId, 3> nodes; int physical_tag; };

/** @brief 一个 rank 持有的单元与节点；节点按 owned 在前、ghost 在后存储。
 * @ingroup mhpc_parallel
 * 单元仅由一个 rank 积分；连通性为本地下标，algebra_ids 为按 owner 连续的全局节点编号。
 * node_boundary_tags 含所有邻接边界的标签，即使对应边界面由其他 rank 持有。
 */
struct MeshPartition {
    std::vector<Node> nodes;
    std::vector<Tet4> cells;
    std::vector<BoundaryTriangle> boundary;
    std::map<std::pair<int, int>, std::string> physical_names;
    int rank = 0, ranks = 1;
    GlobalId global_nodes = 0, global_cells = 0, owned_begin = 0;
    std::size_t owned_nodes = 0;
    std::uint64_t fingerprint = 0;
    std::vector<GlobalId> algebra_ids;
    std::vector<int> owners;
    std::vector<std::vector<int>> node_boundary_tags;
    std::vector<GlobalId> row_offsets, row_columns;
};

MeshPartition read_gmsh22(const std::filesystem::path& path);

/// 为已读入的完整串行网格建立单 rank 所有权、边界节点标签和精确稀疏邻接。
void initialize_serial_partition(MeshPartition& mesh);

/** @brief 串行离线 METIS 分区并写出每 rank 的 HDF5 输入；不参与求解循环。
 * @throws std::runtime_error 输入、METIS 或文件失败。manifest.yaml 最后写入。
 */
void prepare_partitions(const MeshPartition& mesh, int ranks, const std::filesystem::path& directory);

/// 只读取指定 rank 的文件；校验格式、所有权布局和 communicator 大小，不读全局网格。
MeshPartition read_partition(const std::filesystem::path& directory, int rank, int ranks);

struct ScalarDofMap {
    // Compact scalar algebra numbering, distinct from original node global_id.
    std::vector<GlobalId> local_to_algebra;
    std::vector<LocalId> dirichlet_nodes;
    std::vector<double> dirichlet_values;
};

} // namespace eonsim
