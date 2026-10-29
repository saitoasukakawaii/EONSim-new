#pragma once
/** @file
 * @brief 编译期几何拓扑、节点优先场布局与行优先张量索引；不依赖 MPI/PETSc。
 */
#include <array>
namespace eonsim {
/// 维数及二/四阶张量尺寸。模板只表达存储语义，不自动提供任意维数的物理模型。
template<int Dimension> struct CartesianSpace {
    static_assert(Dimension>0,"Space dimension must be positive");
    static constexpr int dimension=Dimension;
    static constexpr int tensor_size=dimension*dimension;
    static constexpr int tangent_size=tensor_size*tensor_size;
    template<class T> using Vector=std::array<T,dimension>;
    template<class T> using Tensor=std::array<T,tensor_size>;
    static constexpr int index(int row,int column) { return row*dimension+column; }
    static constexpr int derivative(int i,int j,int k,int l) { return index(i,j)*tensor_size+index(k,l); }
};
/// P1 单纯形拓扑及解析积分矩；平均值与质量权重均相对于物理体积/面积归一化。
template<int Dimension> struct Simplex {
    using Space=CartesianSpace<Dimension>;
    static constexpr int dimension=Dimension, nodes=dimension+1, face_nodes=dimension, faces=nodes;
    static constexpr int jacobian_scale=[] { int n=1; for(int i=2;i<=dimension;++i) n*=i; return n; }();
    static constexpr double mean_weight=1.0/nodes;
    static constexpr double mass_weight(int a,int b) { return double(a==b?2:1)/(nodes*(nodes+1)); }
    template<class T> using Nodal=std::array<T,nodes>;
};
/// node-major DoF，矩阵 row-major；索引保留调用者的整数宽度。
template<class Element,int Components> struct NodalLayout {
    static_assert(Components>0,"Field needs at least one component");
    using Topology=Element;
    static constexpr int dimension=Element::dimension, nodes=Element::nodes, components=Components;
    static constexpr int dofs=nodes*components, matrix_size=dofs*dofs;
    template<class T> using State=std::array<T,dofs>;
    template<class T> using Matrix=std::array<T,matrix_size>;
    template<class Index> static constexpr auto dof(Index node,int component=0) { return node*components+component; }
    template<class Index> static constexpr auto matrix(Index row,int column) { return row*dofs+column; }
    static constexpr int node(int dof_index) { return dof_index/components; }
    static constexpr int component(int dof_index) { return dof_index%components; }
};
template<class Element> struct FluidLayout : NodalLayout<Element,Element::dimension+1> {
    static constexpr int pressure=Element::dimension;
};
template<class Element,bool Elastic> struct CoupledLayout : NodalLayout<Element,(Elastic?3:2)*Element::dimension+1> {
    static constexpr int pressure=Element::dimension;
    static constexpr int mesh_offset=FluidLayout<Element>::components;
    static constexpr int structure_offset=mesh_offset+Element::dimension;
    static constexpr bool elastic=Elastic;
    static constexpr bool is_mesh(int c) { return c>=mesh_offset && c<structure_offset; }
};
using Space3=CartesianSpace<3>;
using Tet4Topology=Simplex<Space3::dimension>;
using Tri3Topology=Simplex<Space3::dimension-1>;
using Tet4Scalar=NodalLayout<Tet4Topology,1>;
using Tet4Vector=NodalLayout<Tet4Topology,Space3::dimension>;
using Tet4Flow=FluidLayout<Tet4Topology>;
using Tet4Ale=CoupledLayout<Tet4Topology,false>;
using Tet4Elastic=CoupledLayout<Tet4Topology,true>;
}
