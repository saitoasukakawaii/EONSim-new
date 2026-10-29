#pragma once
/** @file @brief Tet4 外表面关联、物理面积和外法向；不依赖 MPI/PETSc。 */
#include "eonsim/mesh.hpp"
namespace eonsim {
/// 与 MeshPartition::boundary 同序；面节点保持输入三角形顺序，cell 为本地单元下标。
struct BoundaryFacet {
    std::size_t cell;
    Tri3Topology::Nodal<int> local_nodes;
    int opposite;
};
/** @brief 建立每个已标记外表面与其唯一相邻本地 Tet4 的关系。
 * 不通信；分区文件须将外表面交给相邻单元的 owner。重复/无邻接/双邻接面抛异常。
 * 仅拓扑变化时重建；不缓存几何，ALE 可复用该关联并更新坐标。
 */
std::vector<BoundaryFacet> build_boundary_facets(const MeshPartition& mesh);
struct TriangleGeometry {
    double area;
    Point normal; ///< 单位外法向，由面外的相邻单元顶点确定方向，与面节点排列无关。
};
/** @brief 给定同一构形下的三角形顶点及其 Tet4 对顶点，返回面积与外法向。
 * 无状态修改/通信/堆分配；拒绝非有限坐标、退化面或共面体顶点。
 */
TriangleGeometry triangle_geometry(const Tri3Topology::Nodal<Point>& face,const Point& opposite);
/// 读取给定网格坐标；固定网格可缓存结果，移动网格必须在新构形下重新计算。
TriangleGeometry boundary_geometry(const MeshPartition& mesh,std::size_t face,const BoundaryFacet& facet);
}
