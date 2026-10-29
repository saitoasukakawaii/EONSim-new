#pragma once
/** @file @brief 按体标签准备单元材料；空映射使用显式全域默认值。 */
#include "eonsim/mesh.hpp"
#include <mpi.h>
#include <stdexcept>
namespace eonsim {
/// collective，检查配置/网格标签双向覆盖；只规约区域计数，不收集单元。
template<class Material>
std::vector<Material> cell_materials(MPI_Comm comm,const MeshPartition& mesh,const std::map<int,Material>& regions,const Material& fallback)
{
    std::vector<Material> result; result.reserve(mesh.cells.size());
    std::map<int,int> indices; int i=0; for(const auto& r:regions) indices[r.first]=i++;
    std::vector<int> seen(regions.size(),0),all(seen.size());
    for(const auto& cell:mesh.cells) {
        if(regions.empty()) result.push_back(fallback);
        else {
            const auto m=regions.find(cell.physical_tag);
            if(m==regions.end()) throw std::runtime_error("Missing material for region "+std::to_string(cell.physical_tag));
            seen[indices.at(m->first)]=1; result.push_back(m->second);
        }
    }
    if(!regions.empty()) {
        MPI_Allreduce(seen.data(),all.data(),static_cast<int>(all.size()),MPI_INT,MPI_MAX,comm);
        for(int exists:all) if(!exists) throw std::runtime_error("Configured material region not found");
    }
    return result;
}
}
