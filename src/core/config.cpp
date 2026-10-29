#include "eonsim/config.hpp"

#include <yaml-cpp/yaml.h>
#include <cmath>
#include <set>
#include <stdexcept>
#include <string>

namespace eonsim {
namespace {
void keys(const YAML::Node& node, std::initializer_list<const char*> allowed,
          const std::string& location)
{
    if (!node.IsMap()) throw std::runtime_error(location + " must be a YAML mapping");
    std::set<std::string> names;
    for (const auto* name : allowed) names.insert(name);
    std::set<std::string> seen;
    for (const auto& entry : node) {
        const auto key = entry.first.as<std::string>();
        if (!names.count(key)) throw std::runtime_error("Unknown key: " + location + "." + key);
        if (!seen.insert(key).second) throw std::runtime_error("Duplicate key: " + location + "." + key);
    }
}
} // namespace

Config read_config(const std::filesystem::path& path)
{
    const auto root = YAML::LoadFile(path.string());
    keys(root, {"mesh", "output", "poisson", "solver"}, "case");
    const auto physics = root["poisson"];
    keys(physics, {"diffusivity", "exact_solution", "dirichlet_tags"}, "poisson");
    Config config;
    const auto directory = std::filesystem::absolute(path).parent_path();
    const auto mesh = root["mesh"].as<std::string>();
    const auto output = root["output"].as<std::string>();
    if (mesh.empty() || output.empty()) throw std::runtime_error("mesh and output must not be empty");
    config.mesh = (directory / mesh).lexically_normal();
    config.output = (directory / output).lexically_normal();
    if (config.output.extension() != ".vtu") throw std::runtime_error("output must have a .vtu extension");
    config.diffusivity = physics["diffusivity"].as<double>();
    if (!std::isfinite(config.diffusivity) || config.diffusivity <= 0.0)
        throw std::runtime_error("poisson.diffusivity must be finite and positive");
    const auto solution = physics["exact_solution"].as<std::string>();
    if (solution == "affine") config.exact_solution = ExactSolution::affine;
    else if (solution == "quadratic") config.exact_solution = ExactSolution::quadratic;
    else throw std::runtime_error("exact_solution must be affine or quadratic; general forcing is not implemented");
    config.dirichlet_tags = physics["dirichlet_tags"].as<std::vector<int>>();
    std::set<int> tags;
    for (int tag : config.dirichlet_tags) {
        if (tag <= 0 || !tags.insert(tag).second)
            throw std::runtime_error("dirichlet_tags must contain distinct positive physical tags");
    }
    if (tags.empty()) throw std::runtime_error("At least one Dirichlet physical tag is required");
    if (const auto solver = root["solver"]) {
        keys(solver, {"relative_tolerance", "absolute_tolerance", "maximum_iterations"}, "solver");
        if (solver["relative_tolerance"]) config.solver.relative_tolerance = solver["relative_tolerance"].as<double>();
        if (solver["absolute_tolerance"]) config.solver.absolute_tolerance = solver["absolute_tolerance"].as<double>();
        if (solver["maximum_iterations"]) config.solver.maximum_iterations = solver["maximum_iterations"].as<int>();
    }
    const auto& solver = config.solver;
    if (!std::isfinite(solver.relative_tolerance) || solver.relative_tolerance <= 0.0 || solver.relative_tolerance >= 1.0 ||
        !std::isfinite(solver.absolute_tolerance) || solver.absolute_tolerance <= 0.0 || solver.maximum_iterations <= 0)
        throw std::runtime_error("Invalid solver tolerances or maximum_iterations");
    return config;
}
} // namespace eonsim
