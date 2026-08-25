"""Post-silicon PDN anomaly detection demo: golden (design-expected) vs. measured
(with an injected parasitic inductance) network, differenced and diagnosed.

Run: python examples/anomaly_detection_demo.py
"""
import copy
import numpy as np
from rlc_id.synth import cascaded_ladder, cascaded_ladder_from_components
from rlc_id.anomaly import fit_golden_and_measured, diff_poles, component_sensitivity, explain_shift

# 1. Golden (design-expected) PDN model: 3-stage cascaded ladder.
golden = cascaded_ladder(n_stages=3, seed=7)
print("Golden component values:")
for i, stage in enumerate(golden.components["stages"]):
    print(f"  stage {i}: R={stage['R']:.4g} L={stage['L']:.4g} C={stage['C']:.4g}")

# 2. Simulate a realistic post-silicon anomaly: stage 1's inductance is 30% higher
#    than designed (e.g. an unmodeled via/bond-wire parasitic).
measured_stages = copy.deepcopy(golden.components["stages"])
measured_stages[1]["L"] *= 1.30
measured_net = cascaded_ladder_from_components(measured_stages)
print(f"\nInjected anomaly: stage 1 L increased by 30% "
      f"({golden.components['stages'][1]['L']:.4g} -> {measured_stages[1]['L']:.4g})")

# 3. Simulate a "measured" frequency sweep (as if from a VNA) of the anomalous network.
pole_mags = np.abs(golden.poles)
w = np.logspace(np.log10(pole_mags.min() / 10), np.log10(pole_mags.max() * 10), 400)
A, B, C, D = measured_net.ss
I = np.eye(A.shape[0])
H_measured = np.array([(C @ np.linalg.solve(1j * wk * I - A, B) + D).item() for wk in w])

# 4. Fit Vector Fitting to both golden and measured data on the same frequency grid.
vf_golden, vf_measured = fit_golden_and_measured(
    golden, w, H_measured, order=len(golden.poles),
    vf_kwargs={"include_real_poles": True, "n_iterations": 15})

# 5. Difference and flag anomalies.
report = diff_poles(vf_golden.poles(), vf_measured.poles(), rel_threshold=0.02)
print(f"\n{report.summary()}")

# 6. Sensitivity analysis: which physical component could explain each flagged shift?
#    Reports the TOP CANDIDATES, not a single answer -- multiple parasitic sources
#    are often indistinguishable from port data alone (see the accompanying
#    technical analysis, Section 6).
sens = component_sensitivity(golden.components["stages"])
for shift in report.anomalies:
    print(f"\nCandidate explanations for pole[{shift.golden_idx}] "
          f"({shift.rel_shift:.1%} shift):")
    for cand in explain_shift(shift, sens, top_n=3):
        print(f"  stage {cand['stage']} {cand['component']}: "
              f"implied change = {cand['implied_delta_frac']:+.1%} "
              f"(fit residual: {cand['fit_residual']:.3e})")

print("\nNote: the top-ranked candidate for stage 1's shift should correctly point "
      "to stage 1's L -- this demonstrates the sensitivity analysis correctly "
      "localizing the injected anomaly, though ambiguity between similarly-sensitive "
      "components is real and should always be reported alongside the top candidate.")
