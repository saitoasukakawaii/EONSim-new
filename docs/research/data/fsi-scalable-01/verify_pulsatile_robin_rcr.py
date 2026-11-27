"""Direct-reference test of a pulsatile ALE tube with Robin support and RCR."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd() / "tests"))
from verify_fsi_inlet import Runner, check_rcr_history, error
from verify_fsi_multigrid import audit, flags
from verify_fsi_advanced_pc import compare_history
from generate_tube import generate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--mpiexec", required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True)
    case = json.loads(generate(args.work).read_text())
    geometry = json.loads((args.work / "geometry.json").read_text())
    runner = Runner(args.executable, args.mpiexec, args.work, timeout=120,
                    interface_area=geometry["interface_area"])
    model = dict(tag=2, proximal_resistance=4., distal_resistance=16.,
                 compliance=.005, distal_pressure=.03, initial_capacitor_pressure=.06)
    case["fsi"].update(pressure_face_history=True, output_interval=case["fsi"]["steps"])
    case["fsi"]["domains"].update(rcr_outlet=model, wall_supports=[dict(tag=14, stiffness=200, damping=15)])
    reference, history, log = runner.solve("reference", case, 2, flags("direct"))
    audit(log, history, 2, "direct")
    direct_circuit = check_rcr_history(runner, "reference", model, history)
    fields, trajectory, log = runner.solve("compressed-pressure", case, 2, flags("mono_pressure_auto", ports=True))
    accepted = audit(log, trajectory, 2, "mono_pressure_auto")
    reduced_circuit = check_rcr_history(runner, "compressed-pressure", model, trajectory)
    difference = error(reference, fields)
    history_difference = compare_history(history, trajectory)
    spring_energy = max(row["endpoint_support_spring_energy"] for row in trajectory)
    dissipation = max(row["stage_support_dissipation"] for row in trajectory)
    assert difference <= 2e-9 and spring_energy > 0 and dissipation > 0
    result = dict(dofs=accepted["dofs"], accepted_steps=len(trajectory), ranks=2,
                  dt=case["fsi"]["dt"], inlet_period=case["fsi"]["inlet"]["flow_rate"]["period"],
                  final_field_difference=difference, history_difference=history_difference,
                  direct_circuit_residual=direct_circuit, compressed_circuit_residual=reduced_circuit,
                  max_true_residual_ratio=accepted["max_true_residual_ratio"],
                  peak_support_spring_energy=spring_energy, peak_support_dissipation=dissipation)
    (args.work / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
