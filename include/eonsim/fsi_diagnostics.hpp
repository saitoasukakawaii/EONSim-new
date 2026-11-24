#pragma once
#include "eonsim/tet4.hpp"
#include <mpi.h>
namespace eonsim {
/// One-time distributed face incidence query. Only exterior faces of the fluid
/// with a solid neighbor survive (legacy region=0 uses exterior trace faces); no global mesh replication.
std::vector<Tri3Topology::Nodal<LocalId>> fsi_interface_faces(MPI_Comm comm,
    const MeshPartition& mesh,const std::vector<bool>& trace,int fluid_region);
/// [current volume, integral div(u), outward flux on faces opposite nodes 0..3].
/// Pure P1/Tet4 integration; caller selects physical exterior faces before MPI reduction.
std::array<double,6> fsi_tet_mass_observation(const Tet4Topology::Nodal<Point>& current,
    const Tet4Topology::Nodal<Point>& velocity);
/// On the current face opposite a local vertex, integrate [1, p, n·σn, u·n].
/// n is the outward fluid unit normal and σ = -p I + μ(grad u + grad uᵀ).
/// P1 pressure and velocity traces and the one-sided Tet4 gradient use the same time level.
std::array<double,4> fsi_pressure_face_integrals(const Tet4Topology::Nodal<Point>& current,
    const Tet4Topology::Nodal<Point>& velocity,const Tet4Topology::Nodal<double>& pressure,
    int opposite,double viscosity);
/// Pure local signed geometry validation; throws StepRejected before commit.
double fsi_volume_ratio(const Tet4Topology::Nodal<Point>& reference,const Tet4Topology::Nodal<Point>& current);
/// [reference area,current area, integral_ref(d_xyz),integral_ref(v_xyz)].
/// Affine nodal fields, one triangle, no MPI or state changes.
std::array<double,8> fsi_surface_observation(const Tri3Topology::Nodal<Point>& reference,
    const Tri3Topology::Nodal<Point>& current,const Tri3Topology::Nodal<Point>& displacement,
    const Tri3Topology::Nodal<Point>& velocity);
}
