#pragma once
#include "eonsim/vtu.hpp"
#include <string_view>

namespace eonsim::output_detail {
// A borrowed view also represents scalar error without copying all point data.
struct FieldView {
    std::string_view name;
    int components;
    const double* values;
    std::size_t size;
    const double* subtract=nullptr;
    double value(std::size_t i) const {return subtract?values[i]-subtract[i]:values[i];}
};
bool parallel_hdf5_available() noexcept;
void write_parallel_hdf5(MPI_Comm comm,const std::filesystem::path& path,
                         const MeshPartition& mesh,const std::vector<FieldView>& fields,
                         bool boundary);
std::string xml_escape(std::string_view value);
}
