#pragma once
/** @file
 * @brief YAML 物理参数与命令行覆盖的运行控制；每个算例只选择一种入口。 */

#include "eonsim/discretization.hpp"
#include <cstdint>
#include <optional>
#include <map>
#include <string>
#include <filesystem>
#include <vector>

namespace eonsim {

enum class ExactSolution { affine, quadratic };

/** @brief 非线性方程字段的接受尺度；在一次 NonlinearSystem::solve 内固定。
 * residual_scale 与已装配物理方程行同单位；constraint_scale 与该字段未知量同单位。
 * 非约束行按无量纲 RMS 验收，约束替换行按无量纲最大误差单独验收。
 */
struct FieldTolerance {
    double residual_scale=1,absolute_tolerance=1e-12,relative_tolerance=1e-10;
    double constraint_scale=1,constraint_tolerance=1e-12;
};
struct SolverConfig {
    std::string pc_recipe; ///< Empty preserves legacy/default solver; physics, quantity, hybrid opt in.
    double relative_tolerance = 1e-10;
    double absolute_tolerance = 1e-12;
    int maximum_iterations = 1000;
    std::map<std::string,FieldTolerance> fields; ///< 非空时须覆盖该非线性布局的全部字段。
};

/** @brief 按 physical tag 的固定网格流体边界。
 * velocity/traction: value + gradient*(x-origin)，gradient 按行存储；pressure: t=-pressure*n。
 * ramp_time=0 表示立即施加，否则乘 min(t/ramp_time,1)；稳态忽略 ramp。
 */
struct FluidBoundary {
    enum class Type { velocity, traction, pressure };
    std::vector<int> components{0,1,2}; // 全局笛卡尔分量；未指定分量为零自然牵引
    int tag=0;
    Type type=Type::velocity;
    Space3::Vector<double> value{},origin{};
    Space3::Tensor<double> gradient{};
    double pressure=0,ramp_time=0;
};
struct PressureGauge { std::int64_t node; double value; }; // 原始网格 ID，非 PETSc 编号

struct FluidMaterial { double density=1,viscosity=1; };
struct SolidMaterial { double young=100,poisson=.3,density=1; bool neo_hookean=false; };

struct FluidConfig {
    enum class Mode { stokes, steady, transient };
    Mode mode = Mode::stokes;
    std::vector<FluidBoundary> boundaries; // 空时保留内置单位通道基准
    std::optional<PressureGauge> pressure_gauge;
    bool mean_pressure=false;
    std::map<int,FluidMaterial> regions;
    bool traction_outlet=false;
    // Fixed SUPG/PSPG coefficient (units time/density) for a time-step-independent
    // spatial discretization. Unset preserves the original transient estimate.
    std::optional<double> stabilization_tau;
    double density=1, viscosity=1, pressure_drop=1, dt=.05, ramp_time=.1;
    int steps=10;
};

struct SolidConfig {
    std::vector<FluidBoundary> boundaries; // velocity 类型在此表示位移 Dirichlet
    std::map<int,SolidMaterial> regions;
    bool transient=false, neo_hookean=false;
    double young=100, poisson=.3, density=1, traction=1, dt=.01;
    int steps=20;
};

struct MotionConfig {
    enum class Mode { uniform, shear, rigid };
    Mode mode=Mode::uniform;
    double dt=.02, speed=.1, amplitude=.02, mass=1, damping=.1, stiffness=10, force=1;
    int steps=5;
};

struct ComponentConstraint { int tag; std::vector<int> components; };
struct FsiDomains {
    std::filesystem::path solid_mesh;
    int fluid_region=10,solid_region=20,fluid_interface=2,solid_interface=12;
    double match_tolerance=1e-10;
    std::vector<int> pressure_tags;
    std::vector<ComponentConstraint> fluid_constraints,mesh_constraints,solid_constraints;
};
struct FsiConfig {
    FsiDomains domains;
    std::optional<double> stabilization_tau;
    bool elastic=false, neo_hookean=false;
    double young=100, poisson=.3, solid_density=1, thickness=.25;
    double dt=.02, mass=2, damping=.3, stiffness=5, pressure=1, density=1, viscosity=1;
    int steps=5;
};

struct TimeControl {
    int max_retries=0; double minimum_dt=1e-10,reduction=.5;
    std::vector<double> step_sizes; ///< 候选步长按accepted步号选取，末值延续；拒绝优先缩步。
    std::vector<double> events; ///< 必须命中的不连续时刻；新格式在事件后重新启动历史。
};
enum class TimeScheme { backward_euler, bdf2 };
struct TimeIntegration { TimeScheme scheme=TimeScheme::backward_euler; };

struct Config {
    TimeIntegration time_integration;
    TimeControl time_control;
    std::filesystem::path checkpoint, restart;
    int stop_after=0;
    bool fsi_problem=false;
    FsiConfig fsi;
    bool motion_problem=false;
    MotionConfig motion;
    bool solid_problem=false;
    SolidConfig solid;
    bool fluid_problem=false;
    FluidConfig fluid;
    std::filesystem::path mesh;
    std::filesystem::path output;
    double diffusivity = 1.0;
    ExactSolution exact_solution = ExactSolution::quadratic;
    std::vector<int> dirichlet_tags;
    SolverConfig solver;
};

// Relative paths are resolved against the YAML file, never the working directory.
Config read_config(const std::filesystem::path& path);

} // namespace eonsim
