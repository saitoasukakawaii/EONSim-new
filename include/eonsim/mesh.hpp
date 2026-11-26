#pragma once
/** @file
 * @brief Tet4 网格、稳定 ID 和本地 owned/ghost 数据。 */

#include "eonsim/discretization.hpp"
#include <array>
#include <cstdint>
#include <filesystem>
#include <map>
#include <string>
#include <vector>

namespace eonsim {

using GlobalId = std::int64_t;
using LocalId = std::int32_t;
using Point = Space3::Vector<double>;

struct Node { GlobalId global_id; Point position; };
struct Tet4 { GlobalId global_id; Tet4Topology::Nodal<LocalId> nodes; int physical_tag; };
struct BoundaryTriangle { GlobalId global_id; Tri3Topology::Nodal<LocalId> nodes; int physical_tag; };
struct Cell2D {
    GlobalId global_id;
    std::array<LocalId,4> nodes{}; ///< Only the first vertices entries participate.
    int physical_tag=0,vertices=3; ///< Tri3=3 or Quad4=4; no subdivision.
};
struct BoundaryEdge { GlobalId global_id; std::array<LocalId,2> nodes; int physical_tag; };

/** @brief 一个 rank 持有的单元与节点；节点按 owned 在前、ghost 在后存储。
 * @ingroup mhpc_parallel
 * 单元仅由一个 rank 积分；连通性为本地下标，algebra_ids 为按 owner 连续的全局节点编号。
 * node_boundary_tags 含所有邻接边界的标签，即使对应边界面由其他 rank 持有。
 */
struct MeshPartition {
    std::vector<Node> nodes;
    std::vector<Tet4> cells;
    std::vector<BoundaryTriangle> boundary;
    int topological_dimension=3; ///< Coordinates remain 3D; scalar 2D uses an XY plane.
    std::vector<Cell2D> cells2;
    std::vector<BoundaryEdge> edges;
    std::map<std::pair<int, int>, std::string> physical_names;
    int rank = 0, ranks = 1;
    GlobalId global_nodes = 0, global_cells = 0, owned_begin = 0;
    std::size_t owned_nodes = 0;
    std::uint64_t fingerprint = 0;
    std::vector<GlobalId> algebra_ids;
    std::vector<int> owners;
    std::vector<std::vector<int>> node_boundary_tags, node_cell_tags;
    std::vector<GlobalId> row_offsets, row_columns;
};

MeshPartition read_gmsh22(const std::filesystem::path& path);
/// Gmsh 2.2/4.1 normalized first-order XY scalar mesh; validates conforming edges.
MeshPartition read_gmsh2d(const std::filesystem::path& path);

/// 为已读入的完整串行网格建立单 rank 所有权、边界节点标签和精确稀疏邻接。
void initialize_serial_partition(MeshPartition& mesh);

struct PartitionRankReport {
    int rank=0;
    GlobalId cells=0,nodes=0,owned_nodes=0,ghost_nodes=0,faces=0;
    std::map<int,GlobalId> cells_by_tag;
    std::uint64_t weighted_cost=0;
};
/** @brief 一次成功离线分区的时间与负载；不包含调用前的网格读取。
 * layout_seconds 包括验证、分桶、编号和 P2 空间准备；write_seconds 包括目录、HDF5 与 manifest。
 * 仅调用者请求时计时和收集逐 rank 计数，不在网格层输出日志或调用 MPI/PETSc。
 */
struct PartitionReport {
    bool weighted=false;
    std::uint64_t total_weighted_cost=0,metis_index_max=0;
    double total_seconds=0,metis_seconds=0,layout_seconds=0,write_seconds=0;
    std::vector<PartitionRankReport> ranks;
};

/** @brief 串行离线 METIS 分区并写出每 rank 的 HDF5 输入；不参与求解循环。
 * cell_weights 是显式 physical tag 到正整数单元成本的映射；未列出的 tag 成本为 1。
 * 权重只影响离线分配，不改变 physical tag、材料、方程或解的接受条件。
 * 空映射保留原 METIS 无权调用；拒绝未知 tag、无效成本或总权重超出 METIS 索引范围。
 * 非空映射将实际单元分区纳入 fingerprint，阻止混用不同布局的分片/checkpoint。
 * 默认空映射的 fingerprint 保持不变；非空映射产生相同实际布局时保持相同身份。
 * report 非空时只在全部文件及 manifest 成功写入后发布本次计时/负载报告。
 * @throws std::runtime_error 输入、METIS 或文件失败。manifest.yaml 最后写入。
 */
void prepare_partitions(const MeshPartition& mesh, int ranks, const std::filesystem::path& directory,
                        int scalar_degree=1, const std::map<int,int>& cell_weights={},
                        PartitionReport* report=nullptr);

/// 只读取指定 rank 的文件；校验格式、所有权布局和 communicator 大小，不读全局网格。
MeshPartition read_partition(const std::filesystem::path& directory, int rank, int ranks);

struct ScalarDofMap {
    // Compact scalar algebra numbering, distinct from original node global_id.
    std::vector<GlobalId> local_to_algebra;
    std::vector<LocalId> dirichlet_nodes;
    std::vector<double> dirichlet_values;
};

} // namespace eonsim
