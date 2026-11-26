#pragma once
/** @file
 * @brief Physical equation dependencies shared by the FSI AIJ and COO graphs.
 */
#include "eonsim/discretization.hpp"

namespace eonsim {
/** A dense physical-component rectangle, repeated over the cell's four nodes.
 * The test and trial maps are applied independently after this dependency mask.
 * These are structural dependencies, never zeros sampled from a Newton state.
 */
struct FsiCouplingBlock {
    int row_first,row_count,column_first,column_count;
};
inline constexpr std::array<FsiCouplingBlock,5> fsi_coupling_blocks{{
    {0,Tet4Flow::components,0,Tet4Ale::components},
    {Tet4Ale::mesh_offset,1,Tet4Ale::mesh_offset,1},
    {Tet4Ale::mesh_offset+1,1,Tet4Ale::mesh_offset+1,1},
    {Tet4Ale::mesh_offset+2,1,Tet4Ale::mesh_offset+2,1},
    {Tet4Ale::structure_offset,Tet4Vector::components,
     Tet4Ale::structure_offset,Tet4Vector::components}
}};

/** Frozen-geometry physics preconditioner. Fluid u/p, structural elasticity,
 * mesh extension and the shared velocity trace remain coupled. The fluid-row
 * ALE-column derivatives are omitted from P only; exact Jv keeps them. Port
 * face derivatives are added separately and remain present in either graph.
 */
inline constexpr std::array<FsiCouplingBlock,5> fsi_reduced_pc_blocks{{
    {0,Tet4Flow::components,0,Tet4Flow::components},
    {Tet4Ale::mesh_offset,1,Tet4Ale::mesh_offset,1},
    {Tet4Ale::mesh_offset+1,1,Tet4Ale::mesh_offset+1,1},
    {Tet4Ale::mesh_offset+2,1,Tet4Ale::mesh_offset+2,1},
    {Tet4Ale::structure_offset,Tet4Vector::components,
     Tet4Ale::structure_offset,Tet4Vector::components}
}};

constexpr const std::array<FsiCouplingBlock,5>& fsi_blocks(bool reduced_pc) noexcept {
    return reduced_pc?fsi_reduced_pc_blocks:fsi_coupling_blocks;
}

constexpr bool fsi_cell_coupling(int row,int column,bool reduced_pc=false) noexcept {
    for(const auto& block:fsi_blocks(reduced_pc))
        if(row>=block.row_first&&row<block.row_first+block.row_count&&
           column>=block.column_first&&column<block.column_first+block.column_count)
            return true;
    return false;
}
} // namespace eonsim
