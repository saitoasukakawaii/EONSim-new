#pragma once

#include <filesystem>
#include <vector>

namespace eonsim {

enum class ExactSolution { affine, quadratic };

struct SolverConfig {
    double relative_tolerance = 1e-10;
    double absolute_tolerance = 1e-12;
    int maximum_iterations = 1000;
};

struct FluidConfig {
    enum class Mode { stokes, steady, transient };
    Mode mode = Mode::stokes;
    bool traction_outlet=false;
    double density=1, viscosity=1, pressure_drop=1, dt=.05, ramp_time=.1;
    int steps=10;
};

struct SolidConfig {
    bool transient=false;
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
    double dt=.02, mass=2, damping=.3, stiffness=5, pressure=1, density=1, viscosity=1;
    int steps=5;
};

struct Config {
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
