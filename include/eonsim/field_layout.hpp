#pragma once
/** @file
 * @brief 网格节点所有权到分量/field IS 的映射。 */
#include "eonsim/mesh.hpp"
#include "eonsim/linear_system.hpp"

namespace eonsim {
/** @brief 构造节点交错布局，global_dof = algebra_node * components + component。
 * @ingroup mhpc_parallel
 * groups 将字段名映射到分量集合；每个分量恰好属于一个字段。
 * meanings 可选，非空时每分量一个显式语义；不从验收字段名称推导PC含义。
 * 不通信，不持有 mesh 引用；返回 owned 行完整块稀疏图及局部 ghost 编号。
 */
AlgebraLayout make_field_layout(const MeshPartition& mesh, int components,
                               const std::map<std::string, std::vector<int>>& groups,
                               const std::vector<ComponentMeaning>& meanings = {});
} // namespace eonsim
