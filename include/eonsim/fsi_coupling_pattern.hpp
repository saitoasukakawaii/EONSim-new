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

constexpr bool fsi_cell_coupling(int row,int column) noexcept {
    for(const auto& block:fsi_coupling_blocks)
        if(row>=block.row_first&&row<block.row_first+block.row_count&&
           column>=block.column_first&&column<block.column_first+block.column_count)
            return true;
    return false;
}
} // namespace eonsim
