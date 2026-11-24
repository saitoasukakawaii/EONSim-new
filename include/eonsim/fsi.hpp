#pragma once
/** @file
 * @brief 压力驱动刚体/弹性块、流体、ALE 的单体 SNES 驱动。 */
#include "eonsim/ale.hpp"
#include <cmath>
#include <stdexcept>
namespace eonsim {
/** Eliminate the capacitor equation C*(pc-reference)/effective_dt = Q-(pc-pd)/Rd
 * at the common time stage. Keep the local outlet pressure as one monolithic unknown.
 */
struct RcrStage {
    double offset,capacitance_impedance,total_impedance;

    long double rate_offset,rate_impedance;
    RcrStage(const RcrOutlet& outlet,double reference,double effective_dt,double evaluation_time=0.) {
        if(!(effective_dt>0)||!std::isfinite(effective_dt)) throw std::runtime_error("Invalid RCR time coefficient");
        const long double denominator=static_cast<long double>(outlet.distal_resistance)*outlet.compliance+effective_dt;
        const long double fraction=effective_dt/denominator;
        const double distal=outlet.distal_pressure_at(evaluation_time);
        rate_offset=(static_cast<long double>(distal)-reference)/denominator;
        rate_impedance=outlet.distal_resistance/denominator;
        offset=static_cast<double>((1-fraction)*reference+fraction*distal);
        capacitance_impedance=static_cast<double>(outlet.distal_resistance*fraction);
        total_impedance=outlet.proximal_resistance+capacitance_impedance;
        if(!std::isfinite(offset)||!std::isfinite(total_impedance)||!(total_impedance>0))
            throw std::runtime_error("Nonfinite RCR stage relation");
    }
    double flow(double outlet_pressure) const { return (outlet_pressure-offset)/total_impedance; }
    double capacitor_pressure(double outlet_pressure) const { return std::fma(capacitance_impedance,flow(outlet_pressure),offset); }
    // Subtracting nearly equal absolute capacitor pressures before dividing by dt loses the rate on short steps.
    double capacitor_rate(double outlet_pressure) const { return static_cast<double>(rate_offset+rate_impedance*flow(outlet_pressure)); }
};

struct FsiResult { MeshPartition current_mesh,solid_mesh; std::vector<PointField> fields,solid_fields; double position=0,velocity=0,fluid_force=0,balance=0; };
/// Pressure at absolute evaluation time; no trial-state dependence.
double fsi_pressure(const FsiConfig& config,double time);
/// Collective local-piece write followed by index publication; fatal errors synchronize.
void write_fsi_fields(MPI_Comm comm,const std::filesystem::path& path,const FsiResult& result);
/// collective；界面速度/位移被消元，网格界面测试行被丢弃；仅整体收敛后提交。
FsiResult solve_fsi(MPI_Comm comm,const MeshPartition& mesh,const Config& config);
}
