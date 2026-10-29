#pragma once
/** @file
 * @brief YAML 物理参数与命令行覆盖的运行控制；每个算例只选择一种入口。 */

#include "eonsim/discretization.hpp"
#include <cstdint>
#include <optional>
#include <filesystem>
#include <vector>

namespace eonsim {

enum class ExactSolution { affine, quadratic };

struct SolverConfig {
    double relative_tolerance = 1e-10;
    double absolute_tolerance = 1e-12;
    int maximum_iterations = 1000;
};

/** @brief 按 physical tag 的固定网格流体边界。
 * velocity/traction: value + gradient*(x-origin)，gradient 按行存储；pressure: t=-pressure*n。
 * ramp_time=0 表示立即施加，否则乘 min(t/ramp_time,1)；稳态忽略 ramp。
 */
struct FluidBoundary {
    enum class Type { velocity, traction, pressure };
    int tag=0;
    Type type=Type::velocity;
    Space3::Vector<double> value{},origin{};
    Space3::Tensor<double> gradient{};
    double pressure=0,ramp_time=0;
};
struct PressureGauge { std::int64_t node; double value; }; // 原始网格 ID，非 PETSc 编号

struct FluidConfig {
    enum class Mode { stokes, steady, transient };
    Mode mode = Mode::stokes;
    std::vector<FluidBoundary> boundaries; // 空时保留内置单位通道基准
    std::optional<PressureGauge> pressure_gauge;
    bool traction_outlet=false;
    double density=1, viscosity=1, pressure_drop=1, dt=.05, ramp_time=.1;
    int steps=10;
};

struct SolidConfig {
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

struct FsiConfig {
    bool elastic=false, neo_hookean=false;
    double young=100, poisson=.3, solid_density=1, thickness=.25;
    double dt=.02, mass=2, damping=.3, stiffness=5, pressure=1, density=1, viscosity=1;
    int steps=5;
};

struct Config {
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
