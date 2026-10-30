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
    double time=0,next_dt=0;
};
/// 本地网格/参数签名；包含节点、单元、所有权与物理参数，不绑定求解器选项。
std::uint64_t state_signature(const MeshPartition& mesh,const std::string& physics,const std::vector<double>& parameters);
/// collective；只写 accepted 状态到独立 generation，全部 flush/close 成功后原子替换 current。
/// 失败在全 communicator 传播，旧代不覆盖；保留所有代与未发布目录，当前无自动清理。
/// 同一根目录只允许一个 writer；保证进程/I/O 失败下的发布顺序，不承诺断电持久性。
void write_checkpoint(MPI_Comm comm,const std::filesystem::path& directory,const MeshPartition& mesh,
                      std::uint64_t signature,const Checkpoint& state);
/// collective 使用、本地读取；directory 可为稳定的根目录或显式 generation 目录。
/// 只接受 v3 完整代，拒绝不同分区/参数、字段尺寸与非有限数据；不自动扫描未发布代。
Checkpoint read_checkpoint(const std::filesystem::path& directory,const MeshPartition& mesh,
                           std::uint64_t signature,const std::map<std::string,std::size_t>& sizes);
}
