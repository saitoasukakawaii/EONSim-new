#pragma once
/** @file
 * @brief 同 rank 数、同分区的 accepted 状态 HDF5 checkpoint。 */
#include "eonsim/mesh.hpp"
#include <mpi.h>
#include <map>
#include <string>
namespace eonsim {
struct Checkpoint {
    int step=0;
    std::map<std::string,std::vector<double>> fields;
};
/// 本地网格/参数签名；包含节点、单元、所有权与物理参数，不绑定求解器选项。
std::uint64_t state_signature(const MeshPartition& mesh,const std::string& physics,const std::vector<double>& parameters);
/// collective；每 rank 临时 HDF5 文件完成后替换，最终发布 manifest；只写 accepted 状态。
void write_checkpoint(MPI_Comm comm,const std::filesystem::path& directory,const MeshPartition& mesh,
                      std::uint64_t signature,const Checkpoint& state);
/// collective 使用；本地读取，拒绝缺失 manifest、不同分区/参数、字段尺寸与非有限数据。
Checkpoint read_checkpoint(const std::filesystem::path& directory,const MeshPartition& mesh,
                           std::uint64_t signature,const std::map<std::string,std::size_t>& sizes);
}
