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
void fluid_boundaries(const YAML::Node& f,FluidConfig& config,bool solid=false)
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
            keys(entry,{"tag","type","value","origin","gradient","ramp_time","components"},"fluid.boundaries");
            if(type=="velocity"|| (solid&&type=="displacement")) b.type=FluidBoundary::Type::velocity;
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
        if(entry["components"]) {
            b.components=entry["components"].as<std::vector<int>>();
            std::set<int> unique;
            for(int c:b.components) if(c<0||c>=Space3::dimension||!unique.insert(c).second) throw std::runtime_error("Invalid or repeated boundary component");
            if(b.components.empty()) throw std::runtime_error("Boundary components cannot be empty");
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
    if(f["pressure_normalization"]) {
        if(f["pressure_normalization"].as<std::string>()!="mean") throw std::runtime_error("pressure_normalization must be mean");
        config.mean_pressure=true;
    }
    if(config.mean_pressure&&config.pressure_gauge) throw std::runtime_error("Choose pressure gauge or mean normalization");
    if(!solid&&natural&&(config.pressure_gauge||config.mean_pressure)) throw std::runtime_error("Pressure gauge cannot accompany traction or pressure boundaries");
    const bool complete=std::all_of(config.boundaries.begin(),config.boundaries.end(),[](const auto& b){return b.components.size()==Space3::dimension;});
    if(!solid&&!natural&&complete&&!config.pressure_gauge&&!config.mean_pressure) throw std::runtime_error("All-velocity boundaries require pressure_gauge or mean normalization");
    std::sort(config.boundaries.begin(),config.boundaries.end(),[](const auto& a,const auto& b){return a.tag<b.tag;});
}
} // namespace

Config read_config(const std::filesystem::path& path)
{
    const auto root = YAML::LoadFile(path.string());
    keys(root, {"mesh", "output", "poisson", "fluid", "solid", "motion", "fsi", "solver", "time_control", "time"}, "case");
    const auto physics = root["poisson"];

    Config config;
    if(const auto t=root["time"]) {
        keys(t,{"scheme","rho_infinity"},"time");
        const auto scheme=t["scheme"].as<std::string>();
        if(scheme=="be") config.time_integration.scheme=TimeScheme::backward_euler;
        else if(scheme=="bdf2") config.time_integration.scheme=TimeScheme::bdf2;
        else if(scheme=="generalized_alpha") config.time_integration.scheme=TimeScheme::generalized_alpha;
        else throw std::runtime_error("Unsupported time scheme: "+scheme);
        if(t["rho_infinity"]) {
            if(config.time_integration.scheme!=TimeScheme::generalized_alpha) throw std::runtime_error("rho_infinity requires generalized_alpha");
            config.time_integration.rho_infinity=t["rho_infinity"].as<double>();
        }
        if(!std::isfinite(config.time_integration.rho_infinity)||config.time_integration.rho_infinity<0||config.time_integration.rho_infinity>1)
            throw std::runtime_error("rho_infinity must be in [0,1]");
    }
    if(const auto t=root["time_control"]) {
        keys(t,{"max_retries","minimum_dt","reduction","step_sizes","events"},"time_control");
        auto& c=config.time_control;
        if(t["max_retries"]) c.max_retries=t["max_retries"].as<int>();
        if(t["minimum_dt"]) c.minimum_dt=t["minimum_dt"].as<double>();
        if(t["reduction"]) c.reduction=t["reduction"].as<double>();
        if(t["step_sizes"]) c.step_sizes=t["step_sizes"].as<std::vector<double>>();
        if(t["events"]) c.events=t["events"].as<std::vector<double>>();
        for(double h:c.step_sizes) if(!(h>0)||!std::isfinite(h)) throw std::runtime_error("Invalid scheduled step size");
        double previous_event=0;
        for(double event:c.events) {
            if(!(event>previous_event)||!std::isfinite(event)) throw std::runtime_error("Time events must be finite, positive and strictly increasing");
            previous_event=event;
        }
        if(c.max_retries<0||c.max_retries>30||!(c.minimum_dt>0&&c.reduction>0&&c.reduction<1)||!std::isfinite(c.minimum_dt+c.reduction)) throw std::runtime_error("Invalid time_control");
    }
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
        keys(f,{"mode","density","viscosity","pressure_drop","dt","steps","ramp_time","outlet","boundaries","pressure_gauge","pressure_normalization","regions","stabilization_tau"},"fluid");
        const auto mode=f["mode"].as<std::string>();
        if(mode=="stokes") config.fluid.mode=FluidConfig::Mode::stokes;
        else if(mode=="steady") config.fluid.mode=FluidConfig::Mode::steady;
        else if(mode=="transient") config.fluid.mode=FluidConfig::Mode::transient;
        else throw std::runtime_error("Unknown fluid mode");
        auto& v=config.fluid;
        if(f["stabilization_tau"]) {
            v.stabilization_tau=f["stabilization_tau"].as<double>();
            if(!(*v.stabilization_tau>0)||!std::isfinite(*v.stabilization_tau))
                throw std::runtime_error("fluid.stabilization_tau must be finite and positive");
        }
        if(f["boundaries"]) fluid_boundaries(f,v);
        else if(f["pressure_gauge"]||f["pressure_normalization"]) throw std::runtime_error("Pressure normalization requires tagged boundaries");
        if(f["outlet"]) {
            const auto outlet=f["outlet"].as<std::string>();
            if(outlet!="velocity" && outlet!="traction") throw std::runtime_error("Invalid fluid outlet");
            v.traction_outlet=outlet=="traction";
        }
        if(const auto regions=f["regions"]) {
            if(!regions.IsSequence()||regions.size()==0) throw std::runtime_error("fluid.regions must be nonempty");
            for(const auto& r:regions) {
                keys(r,{"tag","density","viscosity"},"fluid.regions");
                FluidMaterial m{r["density"].as<double>(),r["viscosity"].as<double>()};
                const int tag=r["tag"].as<int>();
                if(tag<=0||!(m.density>0&&m.viscosity>0)||!std::isfinite(m.density+m.viscosity)||!v.regions.emplace(tag,m).second) throw std::runtime_error("Invalid fluid region material");
            }
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
        keys(s,{"mode","young","poisson","density","traction","dt","steps","material","boundaries","regions"},"solid");
        auto& v=config.solid;
        if(s["boundaries"]) {
            FluidConfig boundary_config; fluid_boundaries(s,boundary_config,true); v.boundaries=boundary_config.boundaries;
            for(const auto& b:v.boundaries) if(b.ramp_time!=0)
                throw std::runtime_error("Solid static/unload requires constant-in-time displacement and load");
        }
        if(const auto regions=s["regions"]) {
            if(!regions.IsSequence()||regions.size()==0) throw std::runtime_error("solid.regions must be nonempty");
            for(const auto& r:regions) {
                keys(r,{"tag","young","poisson","density","material"},"solid.regions");
                SolidMaterial m{r["young"].as<double>(),r["poisson"].as<double>(),r["density"].as<double>(),false};
                if(r["material"]) { const auto type=r["material"].as<std::string>(); if(type!="linear"&&type!="neo_hookean") throw std::runtime_error("Invalid region material law"); m.neo_hookean=type=="neo_hookean"; }
                const int tag=r["tag"].as<int>();
                if(tag<=0||!(m.young>0&&m.poisson>-1&&m.poisson<.5&&m.density>0)||!std::isfinite(m.young+m.poisson+m.density)||!v.regions.emplace(tag,m).second) throw std::runtime_error("Invalid solid region material");
            }
        }
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
        keys(f,{"dt","steps","mass","damping","stiffness","pressure","density","viscosity","body","young","poisson","solid_density","thickness","material","domains","stabilization_tau"},"fsi");
        if(f["stabilization_tau"]) {
            config.fsi.stabilization_tau=f["stabilization_tau"].as<double>();
            if(!(*config.fsi.stabilization_tau>0)||!std::isfinite(*config.fsi.stabilization_tau))
                throw std::runtime_error("fsi.stabilization_tau must be finite and positive");
        }
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
        if(const auto d=f["domains"]) {
            keys(d,{"solid_mesh","fluid_region","solid_region","fluid_interface","solid_interface","match_tolerance","pressure_tags","fluid_constraints","mesh_constraints","solid_constraints"},"fsi.domains");
            auto& domain=v.domains;
            domain.solid_mesh=(directory/d["solid_mesh"].as<std::string>()).lexically_normal();
            domain.fluid_region=d["fluid_region"].as<int>(); domain.solid_region=d["solid_region"].as<int>();
            domain.fluid_interface=d["fluid_interface"].as<int>(); domain.solid_interface=d["solid_interface"].as<int>();
            if(d["match_tolerance"]) domain.match_tolerance=d["match_tolerance"].as<double>();
            if(!v.elastic||domain.fluid_region<=0||domain.solid_region<=0||domain.fluid_region==domain.solid_region||domain.fluid_interface<=0||domain.solid_interface<=0||!(domain.match_tolerance>0)||!std::isfinite(domain.match_tolerance)) throw std::runtime_error("Invalid independent FSI domains");
            domain.pressure_tags=d["pressure_tags"].as<std::vector<int>>();
            std::set<int> pressure_seen;
            for(int tag:domain.pressure_tags) if(tag<=0||!pressure_seen.insert(tag).second||tag==domain.fluid_interface) throw std::runtime_error("Invalid FSI pressure tags");
            if(domain.pressure_tags.empty()) throw std::runtime_error("FSI needs pressure boundary");
            auto constraints=[&](const char* key,std::vector<ComponentConstraint>& output) {
                const auto entries=d[key]; if(!entries.IsSequence()) throw std::runtime_error(std::string(key)+" must be a sequence");
                std::set<int> seen;
                for(const auto& entry:entries) {
                    keys(entry,{"tag","components"},key); ComponentConstraint c{entry["tag"].as<int>(),entry["components"].as<std::vector<int>>()};
                    if(c.tag<=0||!seen.insert(c.tag).second||c.components.empty()) throw std::runtime_error("Invalid FSI constraint tag");
                    std::set<int> components; for(int i:c.components) if(i<0||i>=Space3::dimension||!components.insert(i).second) throw std::runtime_error("Invalid FSI constraint component");
                    output.push_back(c);
                }
            };
            constraints("fluid_constraints",domain.fluid_constraints); constraints("mesh_constraints",domain.mesh_constraints); constraints("solid_constraints",domain.solid_constraints);
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
        keys(solver, {"relative_tolerance", "absolute_tolerance", "maximum_iterations", "fields", "pc_recipe"}, "solver");
        if (solver["pc_recipe"]) config.solver.pc_recipe = solver["pc_recipe"].as<std::string>();
        if(!config.solver.pc_recipe.empty()) {
            const auto& recipe=config.solver.pc_recipe;
            if(recipe!="physics"&&recipe!="quantity"&&recipe!="hybrid") throw std::runtime_error("Unknown solver.pc_recipe");
            if(!config.fluid_problem&&!config.fsi_problem) throw std::runtime_error("solver.pc_recipe currently requires independent fluid or FSI");
        }
        if (solver["relative_tolerance"]) config.solver.relative_tolerance = solver["relative_tolerance"].as<double>();
        if (solver["absolute_tolerance"]) config.solver.absolute_tolerance = solver["absolute_tolerance"].as<double>();
        if (solver["maximum_iterations"]) config.solver.maximum_iterations = solver["maximum_iterations"].as<int>();
        if(const auto fields=solver["fields"]) {
            if(!fields.IsMap()||fields.size()==0) throw std::runtime_error("solver.fields must be a nonempty mapping");
            if(!(config.fluid_problem||config.solid_problem||config.fsi_problem||
                (config.motion_problem&&config.motion.mode!=MotionConfig::Mode::rigid)))
                throw std::runtime_error("solver.fields requires a nonlinear solver entry");
            for(const auto& entry:fields) {
                const auto name=entry.first.as<std::string>(); const auto& f=entry.second;
                keys(f,{"residual_scale","absolute_tolerance","relative_tolerance","constraint_scale","constraint_tolerance"},"solver.fields."+name);
                FieldTolerance t;
                t.absolute_tolerance=t.constraint_tolerance=config.solver.absolute_tolerance;
                t.relative_tolerance=config.solver.relative_tolerance;
                if(!f["residual_scale"]) throw std::runtime_error("Missing residual_scale for field "+name);
                t.residual_scale=f["residual_scale"].as<double>();
                if(f["absolute_tolerance"]) t.absolute_tolerance=f["absolute_tolerance"].as<double>();
                if(f["relative_tolerance"]) t.relative_tolerance=f["relative_tolerance"].as<double>();
                if(f["constraint_scale"]) t.constraint_scale=f["constraint_scale"].as<double>();
                if(f["constraint_tolerance"]) t.constraint_tolerance=f["constraint_tolerance"].as<double>();
                if(!(t.residual_scale>0&&t.absolute_tolerance>0&&t.relative_tolerance>=0&&t.relative_tolerance<1&&
                    t.constraint_scale>0&&t.constraint_tolerance>0)||
                    !std::isfinite(t.residual_scale)||!std::isfinite(t.absolute_tolerance)||!std::isfinite(t.relative_tolerance)||
                    !std::isfinite(t.constraint_scale)||!std::isfinite(t.constraint_tolerance))
                    throw std::runtime_error("Invalid field tolerance or scale: "+name);
                if(!config.solver.fields.emplace(name,t).second) throw std::runtime_error("Duplicate solver field: "+name);
            }
        }
    }
    const auto& solver = config.solver;
    if (!std::isfinite(solver.relative_tolerance) || solver.relative_tolerance <= 0.0 || solver.relative_tolerance >= 1.0 ||
        !std::isfinite(solver.absolute_tolerance) || solver.absolute_tolerance <= 0.0 || solver.maximum_iterations <= 0)
        throw std::runtime_error("Invalid solver tolerances or maximum_iterations");
    if(config.time_integration.scheme==TimeScheme::generalized_alpha&&
       !((config.fluid_problem&&config.fluid.mode==FluidConfig::Mode::transient)||(config.solid_problem&&config.solid.transient)||config.fsi_problem||
         (config.motion_problem&&config.motion.mode!=MotionConfig::Mode::rigid)))
        throw std::runtime_error("generalized_alpha requires transient fluid, solid, ALE or FSI");
    if(config.time_integration.scheme==TimeScheme::bdf2 &&
       !((config.fluid_problem&&config.fluid.mode==FluidConfig::Mode::transient)||(config.solid_problem&&config.solid.transient)||config.fsi_problem||
         (config.motion_problem&&config.motion.mode!=MotionConfig::Mode::rigid)))
        throw std::runtime_error("BDF2 requires transient standalone fluid, solid, ALE or FSI");
    return config;
}
} // namespace eonsim
