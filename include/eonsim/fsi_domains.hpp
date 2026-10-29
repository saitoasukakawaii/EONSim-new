#pragma once
/** @file @brief 独立流固网格的离线共形界面配对与联合分区输入。 */
#include "eonsim/mesh.hpp"
#include "eonsim/config.hpp"
namespace eonsim {
/// 串行预处理：只合并指定界面节点，检查节点/三角形双射和相反外法向。
/// 联合节点/单元 ID 按输入顺序重建；体标签保持输入值。运行阶段只读取联合分区。
MeshPartition read_fsi_domains(const std::filesystem::path& fluid,const FsiDomains& config);
bool node_in_region(const MeshPartition& mesh,std::size_t node,int tag);
}
