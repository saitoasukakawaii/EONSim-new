#pragma once
/** @file
 * @brief 本地 VTU 结果与 PVTU 汇总索引。 */

#include "eonsim/mesh.hpp"

namespace eonsim {
struct PointField {
    std::string name;
    int components=1;
    std::vector<double> values;
};
/// 本地写出节点优先的具名标量/向量；不通信。
void write_fields(const std::filesystem::path& path, const MeshPartition& mesh,
                  const std::vector<PointField>& fields);
void write_field_index(const std::filesystem::path& path, int ranks,
                       const std::vector<PointField>& fields);
// Writes volume solution and a companion *_boundary.vtu containing physical tags.
void write_vtu(const std::filesystem::path& path, const MeshPartition& mesh,
               const std::vector<double>& values, const std::vector<double>& exact);
/// 全部 rank 写完本地 VTU 后，由 rank 0 调用；仅写文件引用，不收集网格或场。
void write_pvtu(const std::filesystem::path& path, int ranks);
} // namespace eonsim
