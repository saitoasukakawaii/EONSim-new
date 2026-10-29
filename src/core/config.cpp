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
    keys(root, {"mesh", "output", "poisson", "fluid", "solid", "solver"}, "case");
    const auto physics = root["poisson"];

    Config config;
    const auto directory = std::filesystem::absolute(path).parent_path();
    const auto mesh = root["mesh"].as<std::string>();
    const auto output = root["output"].as<std::string>();
    if (mesh.empty() || output.empty()) throw std::runtime_error("mesh and output must not be empty");
    config.mesh = (directory / mesh).lexically_normal();
    config.output = (directory / output).lexically_normal();
    if (config.output.extension() != ".vtu") throw std::runtime_error("output must have a .vtu extension");
    if (int(bool(root["fluid"])) + int(bool(root["solid"])) + int(bool(root["poisson"])) != 1) throw std::runtime_error("Select exactly one physics block");
    config.fluid_problem=static_cast<bool>(root["fluid"]);
    config.solid_problem=static_cast<bool>(root["solid"]);
    if (!config.fluid_problem && !config.solid_problem) {
    keys(physics, {"diffusivity", "exact_solution", "dirichlet_tags"}, "poisson");
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
    } else if(config.fluid_problem) {
        const auto f=root["fluid"];
        keys(f,{"mode","density","viscosity","pressure_drop","dt","steps","ramp_time","outlet"},"fluid");
        const auto mode=f["mode"].as<std::string>();
        if(mode=="stokes") config.fluid.mode=FluidConfig::Mode::stokes;
        else if(mode=="steady") config.fluid.mode=FluidConfig::Mode::steady;
        else if(mode=="transient") config.fluid.mode=FluidConfig::Mode::transient;
        else throw std::runtime_error("Unknown fluid mode");
        auto& v=config.fluid;
        if(f["outlet"]) {
            const auto outlet=f["outlet"].as<std::string>();
            if(outlet!="velocity" && outlet!="traction") throw std::runtime_error("Invalid fluid outlet");
            v.traction_outlet=outlet=="traction";
        }
        if(f["density"]) v.density=f["density"].as<double>();
        if(f["viscosity"]) v.viscosity=f["viscosity"].as<double>();
        if(f["pressure_drop"]) v.pressure_drop=f["pressure_drop"].as<double>();
        if(f["dt"]) v.dt=f["dt"].as<double>();
        if(f["ramp_time"]) v.ramp_time=f["ramp_time"].as<double>();
        if(f["steps"]) v.steps=f["steps"].as<int>();
        if(!(v.density>0 && v.viscosity>0 && v.dt>0 && v.ramp_time>0 && v.steps>0) ||
            !std::isfinite(v.density+v.viscosity+v.pressure_drop+v.dt+v.ramp_time))
            throw std::runtime_error("Invalid fluid material/time configuration");
    }
    if(config.solid_problem) {
        const auto s=root["solid"];
        keys(s,{"mode","young","poisson","density","traction","dt","steps"},"solid");
        auto& v=config.solid;
        const auto mode=s["mode"].as<std::string>();
        if(mode!="static" && mode!="unload") throw std::runtime_error("Solid mode must be static or unload");
        v.transient=mode=="unload";
        if(s["young"]) v.young=s["young"].as<double>();
        if(s["poisson"]) v.poisson=s["poisson"].as<double>();
        if(s["density"]) v.density=s["density"].as<double>();
        if(s["traction"]) v.traction=s["traction"].as<double>();
        if(s["dt"]) v.dt=s["dt"].as<double>();
        if(s["steps"]) v.steps=s["steps"].as<int>();
        if(!(v.young>0 && v.poisson>-1 && v.poisson<.5 && v.density>0 && v.dt>0 && v.steps>0) ||
            !std::isfinite(v.young+v.poisson+v.density+v.dt+v.traction)) throw std::runtime_error("Invalid solid parameters");
    }
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
