#include "eonsim/config.hpp"

#include <yaml-cpp/yaml.h>
#include <cmath>
#include <algorithm>
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
Space3::Vector<double> vector3(const YAML::Node& node,const std::string& location)
{
    if(!node.IsSequence()||node.size()!=Space3::dimension) throw std::runtime_error(location+" requires three components");
    Space3::Vector<double> v{};
    for(int d=0;d<Space3::dimension;++d) {
        v[d]=node[d].as<double>();
        if(!std::isfinite(v[d])) throw std::runtime_error(location+" must be finite");
    }
    return v;
}
void fluid_boundaries(const YAML::Node& f,FluidConfig& config)
{
    const auto boundaries=f["boundaries"];
    if(!boundaries.IsSequence()||boundaries.size()==0) throw std::runtime_error("fluid.boundaries must be a nonempty sequence");
    if(f["pressure_drop"]||f["outlet"]||f["ramp_time"]) throw std::runtime_error("Tagged boundaries cannot use benchmark pressure_drop/outlet/ramp_time");
    std::set<int> tags; bool natural=false,velocity=false;
    for(const auto& entry:boundaries) {
        const auto type=entry["type"].as<std::string>();
        FluidBoundary b;
        if(type=="pressure") {
            keys(entry,{"tag","type","value","ramp_time"},"fluid.boundaries.pressure");
            b.type=FluidBoundary::Type::pressure; b.pressure=entry["value"].as<double>();
            if(!std::isfinite(b.pressure)) throw std::runtime_error("Boundary pressure must be finite");
        } else {
            keys(entry,{"tag","type","value","origin","gradient","ramp_time"},"fluid.boundaries");
            if(type=="velocity") b.type=FluidBoundary::Type::velocity;
            else if(type=="traction") b.type=FluidBoundary::Type::traction;
            else throw std::runtime_error("Boundary type must be velocity, traction or pressure");
            b.value=vector3(entry["value"],"boundary value");
            if(entry["origin"]) b.origin=vector3(entry["origin"],"boundary origin");
            if(const auto g=entry["gradient"]) {
                if(!g.IsSequence()||g.size()!=Space3::dimension) throw std::runtime_error("Boundary gradient requires three rows");
                for(int i=0;i<Space3::dimension;++i) {
                    const auto row=vector3(g[i],"boundary gradient row");
                    for(int j=0;j<Space3::dimension;++j) b.gradient[Space3::index(i,j)]=row[j];
                }
            }
        }
        b.tag=entry["tag"].as<int>();
        if(b.tag<=0||!tags.insert(b.tag).second) throw std::runtime_error("Boundary tags must be distinct and positive");
        if(entry["ramp_time"]) b.ramp_time=entry["ramp_time"].as<double>();
        if(!std::isfinite(b.ramp_time)||b.ramp_time<0) throw std::runtime_error("Boundary ramp_time must be finite and nonnegative");
        natural|=b.type!=FluidBoundary::Type::velocity; velocity|=b.type==FluidBoundary::Type::velocity;
        config.boundaries.push_back(b);
    }
    if(!velocity) throw std::runtime_error("At least one velocity boundary is required");
    if(const auto gauge=f["pressure_gauge"]) {
        keys(gauge,{"node","value"},"fluid.pressure_gauge");
        config.pressure_gauge=PressureGauge{gauge["node"].as<std::int64_t>(),gauge["value"].as<double>()};
        if(config.pressure_gauge->node<=0||!std::isfinite(config.pressure_gauge->value)) throw std::runtime_error("Invalid pressure gauge");
    }
    if(natural&&config.pressure_gauge) throw std::runtime_error("Pressure gauge cannot accompany traction or pressure boundaries");
    if(!natural&&!config.pressure_gauge) throw std::runtime_error("All-velocity boundaries require pressure_gauge");
    std::sort(config.boundaries.begin(),config.boundaries.end(),[](const auto& a,const auto& b){return a.tag<b.tag;});
}
} // namespace

Config read_config(const std::filesystem::path& path)
{
    const auto root = YAML::LoadFile(path.string());
    keys(root, {"mesh", "output", "poisson", "fluid", "solid", "motion", "fsi", "solver"}, "case");
    const auto physics = root["poisson"];

    Config config;
    const auto directory = std::filesystem::absolute(path).parent_path();
    const auto mesh = root["mesh"].as<std::string>();
    const auto output = root["output"].as<std::string>();
    if (mesh.empty() || output.empty()) throw std::runtime_error("mesh and output must not be empty");
    config.mesh = (directory / mesh).lexically_normal();
    config.output = (directory / output).lexically_normal();
    if (config.output.extension() != ".vtu") throw std::runtime_error("output must have a .vtu extension");
    if (int(bool(root["fluid"])) + int(bool(root["solid"])) + int(bool(root["poisson"])) + int(bool(root["motion"])) + int(bool(root["fsi"])) != 1) throw std::runtime_error("Select exactly one physics block");
    config.fluid_problem=static_cast<bool>(root["fluid"]);
    config.solid_problem=static_cast<bool>(root["solid"]);
    config.motion_problem=static_cast<bool>(root["motion"]);
    config.fsi_problem=static_cast<bool>(root["fsi"]);
    if (!config.fluid_problem && !config.solid_problem && !config.motion_problem && !config.fsi_problem) {
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
        keys(f,{"mode","density","viscosity","pressure_drop","dt","steps","ramp_time","outlet","boundaries","pressure_gauge"},"fluid");
        const auto mode=f["mode"].as<std::string>();
        if(mode=="stokes") config.fluid.mode=FluidConfig::Mode::stokes;
        else if(mode=="steady") config.fluid.mode=FluidConfig::Mode::steady;
        else if(mode=="transient") config.fluid.mode=FluidConfig::Mode::transient;
        else throw std::runtime_error("Unknown fluid mode");
        auto& v=config.fluid;
        if(f["boundaries"]) fluid_boundaries(f,v);
        else if(f["pressure_gauge"]) throw std::runtime_error("pressure_gauge requires tagged boundaries");
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
        keys(s,{"mode","young","poisson","density","traction","dt","steps","material"},"solid");
        auto& v=config.solid;
        if(s["material"]) {
            const auto material=s["material"].as<std::string>();
            if(material!="linear" && material!="neo_hookean") throw std::runtime_error("Unknown solid material");
            v.neo_hookean=material=="neo_hookean";
        }
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
    if(config.motion_problem) {
        const auto m=root["motion"];
        keys(m,{"mode","dt","steps","speed","amplitude","mass","damping","stiffness","force"},"motion");
        auto& v=config.motion;
        const auto mode=m["mode"].as<std::string>();
        if(mode=="uniform") v.mode=MotionConfig::Mode::uniform;
        else if(mode=="shear") v.mode=MotionConfig::Mode::shear;
        else if(mode=="rigid") v.mode=MotionConfig::Mode::rigid;
        else throw std::runtime_error("Invalid motion mode");
        if(m["dt"]) v.dt=m["dt"].as<double>();
        if(m["steps"]) v.steps=m["steps"].as<int>();
        if(m["speed"]) v.speed=m["speed"].as<double>();
        if(m["amplitude"]) v.amplitude=m["amplitude"].as<double>();
        if(m["mass"]) v.mass=m["mass"].as<double>();
        if(m["damping"]) v.damping=m["damping"].as<double>();
        if(m["stiffness"]) v.stiffness=m["stiffness"].as<double>();
        if(m["force"]) v.force=m["force"].as<double>();
        if(!(v.dt>0 && v.steps>0 && v.mass>0 && v.damping>=0 && v.stiffness>=0) ||
            !std::isfinite(v.dt+v.speed+v.amplitude+v.mass+v.damping+v.stiffness+v.force))
            throw std::runtime_error("Invalid motion parameters");
    }
    if(config.fsi_problem) {
        const auto f=root["fsi"];
        keys(f,{"dt","steps","mass","damping","stiffness","pressure","density","viscosity","body","young","poisson","solid_density","thickness","material"},"fsi");
        auto& v=config.fsi;
        if(f["material"]) {
            const auto material=f["material"].as<std::string>();
            if(material!="linear" && material!="neo_hookean") throw std::runtime_error("Unknown FSI material");
            v.neo_hookean=material=="neo_hookean";
        }
        if(f["body"]) {
            const auto body=f["body"].as<std::string>();
            if(body!="rigid" && body!="elastic") throw std::runtime_error("FSI body must be rigid or elastic");
            v.elastic=body=="elastic";
        }
        if(v.neo_hookean && !v.elastic) throw std::runtime_error("Neo-Hookean FSI requires an elastic body");
        if(f["young"]) v.young=f["young"].as<double>();
        if(f["poisson"]) v.poisson=f["poisson"].as<double>();
        if(f["solid_density"]) v.solid_density=f["solid_density"].as<double>();
        if(f["thickness"]) v.thickness=f["thickness"].as<double>();
        if(!(v.young>0 && v.poisson>-1 && v.poisson<.5 && v.solid_density>0 && v.thickness>0) ||
           !std::isfinite(v.young+v.poisson+v.solid_density+v.thickness)) throw std::runtime_error("Invalid FSI solid parameters");
        if(f["dt"]) v.dt=f["dt"].as<double>();
        if(f["steps"]) v.steps=f["steps"].as<int>();
        if(f["mass"]) v.mass=f["mass"].as<double>();
        if(f["damping"]) v.damping=f["damping"].as<double>();
        if(f["stiffness"]) v.stiffness=f["stiffness"].as<double>();
        if(f["pressure"]) v.pressure=f["pressure"].as<double>();
        if(f["density"]) v.density=f["density"].as<double>();
        if(f["viscosity"]) v.viscosity=f["viscosity"].as<double>();
        if(!(v.dt>0 && v.steps>0 && v.mass>0 && v.damping>=0 && v.stiffness>=0 && v.density>0 && v.viscosity>0) ||
            !std::isfinite(v.dt+v.mass+v.damping+v.stiffness+v.pressure+v.density+v.viscosity))
            throw std::runtime_error("Invalid FSI parameters");
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
