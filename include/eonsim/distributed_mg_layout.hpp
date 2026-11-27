#pragma once
/** @file Setup-only ownership migration for cut-spanning AMG aggregates. */
#include "eonsim/linear_system.hpp"

namespace eonsim {
struct MgRedistribution {
    /// T maps new ownership to the original algebra layout; A_new=T^T A T.
    PetscOwner<Mat,MatDestroy> permutation,matrix;
    std::vector<DofKey> semantics;
    std::vector<std::array<double,36>> candidates;
    std::vector<unsigned char> trace,active;
    /// Original row/rank for every newly owned row, without a global field copy.
    std::vector<PetscInt> original_rows;
    std::vector<int> origin_rank;
    PetscInt moved_rows=0;
};

/** Redistribute complete vertex blocks across actual nonzero rank cuts.
 * Input entity/mode/space blocks must already have one owner, as in the current
 * physical and coarse layouts; this helper does not repair split-node input.
 * Odd ranks propose their strongest adjacent even rank; each receiver accepts
 * at most one proposer. Matched senders migrate a bounded boundary-row budget
 * (one eighth of local rows, allowing one complete block of at most 512 rows)
 * and keep at least one local row. Body/boundary entities never migrate.
 * Only O(ranks) matching/count metadata is collective; row metadata is sent
 * directly to its new owner. No rank receives a global matrix or field.
 *
 * The exact permutation changes setup ownership, not the physical operator or
 * caller's DoF numbering. The caller constructs aggregates in the returned
 * layout and maps its prolongation back with T. A migration is not itself an
 * aggregate: origin_rank permits counting actual cut-spanning aggregates.
 * Matrices and all metadata are owned by the result. Collective on comm.
 */
MgRedistribution redistribute_mg_layout(MPI_Comm comm,Mat matrix,
    const std::vector<DofKey>& semantics,
    const std::vector<std::array<double,36>>& candidates,
    const std::vector<unsigned char>& trace,const std::vector<unsigned char>& active);
} // namespace eonsim
