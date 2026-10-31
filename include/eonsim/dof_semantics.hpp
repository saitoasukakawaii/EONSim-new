#pragma once
/** @file Semantic identities independent of storage numbering and PC partitions. */
#include <cstdint>
#include <tuple>
namespace eonsim {
enum class DofDomain : std::uint8_t { fluid, solid, mesh };
enum class DofQuantity : std::uint8_t { velocity, pressure, displacement };
enum class DofEntity : std::uint8_t { vertex, body };
/** Identity in one layout's mesh namespace (not a restart identifier).
 * entity is the imported/joined mesh ID, never MPI rank or algebra row.
 * Tet4 vertex P1 uses mode=0, space=1; the global rigid scalar uses space=0.
 * Multiple physical slots may refer to one canonical identity through ReducedLayout.
 */
struct DofKey {
    std::int64_t entity=0;
    DofDomain domain=DofDomain::fluid;
    DofQuantity quantity=DofQuantity::velocity;
    DofEntity kind=DofEntity::vertex;
    std::uint16_t component=0, mode=0, space=1;
    auto tuple() const { return std::make_tuple(entity,domain,quantity,kind,component,mode,space); }
    bool operator==(const DofKey& other) const { return tuple()==other.tuple(); }
    bool operator<(const DofKey& other) const { return tuple()<other.tuple(); }
};
/** Explicit per-component meaning supplied by the physical driver. */
struct ComponentMeaning {
    DofDomain domain;
    DofQuantity quantity;
    std::uint16_t component;
};
} // namespace eonsim
