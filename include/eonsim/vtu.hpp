#pragma once
/** @file
 * @brief 本地 VTU 结果与 PVTU 汇总索引。 */

#include "eonsim/mesh.hpp"
#include <mpi.h>

namespace eonsim {
struct VtuOptions {
    bool binary=false;
    bool boundary=true;
    bool compact_boundary=true;
    bool hdf5=false; ///< Shared MPI-IO HDF5 payload and atomically published XDMF.
};
/// Set once on the main thread before output. Binary uses raw appended little-endian
/// arrays with UInt64 byte-count headers; compact boundary pieces keep stable IDs.
/// HDF5 requires a parallel HDF5 build and a borrowed communicator that outlives output.
void configure_vtu_output(const VtuOptions& options,MPI_Comm communicator=MPI_COMM_NULL);
bool hdf5_output_enabled() noexcept;
/// Actual visualization entry point (.xdmf for shared HDF5, otherwise .vtu/.pvtu).
std::filesystem::path output_dataset_path(const std::filesystem::path& path,int ranks);
/// Rank-zero publication of PVD or <stem>.series.xdmf, with no field gathering.
/// entries contain time and visualization entry-point filenames, not HDF5 payload names.
void write_output_time_series(const std::filesystem::path& path,
                             const std::vector<std::pair<double,std::string>>& entries);

struct PointField {
    std::string name;
    int components=1;
    std::vector<double> values;
};
/// VTU writes local point fields without communication. HDF5 is collective on
/// the configured communicator and writes each owned node and cell once.
void write_fields(const std::filesystem::path& path, const MeshPartition& mesh,
                  const std::vector<PointField>& fields);
void write_field_index(const std::filesystem::path& path, int ranks,
                       const std::vector<PointField>& fields);
// Writes volume solution and, when enabled, a companion *_boundary.vtu with physical tags.
void write_vtu(const std::filesystem::path& path, const MeshPartition& mesh,
               const std::vector<double>& values, const std::vector<double>& exact);
/// 全部 rank 写完本地 VTU 后，由 rank 0 调用；仅写文件引用，不收集网格或场。
void write_pvtu(const std::filesystem::path& path, int ranks);
} // namespace eonsim
