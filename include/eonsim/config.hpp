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

struct Config {
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
