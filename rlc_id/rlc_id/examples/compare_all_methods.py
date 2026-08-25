"""Compare all identification methods on a synthetic cascaded RLC ladder.

This is the core empirical deliverable: it PROVES which method performs best under
which regime (excitation type, noise level) rather than asserting it from theory
alone. Run: python examples/compare_all_methods.py
"""
import pandas as pd
from rlc_id.synth import cascaded_ladder
from rlc_id.eval import run_benchmark, ALL_METHODS
from rlc_id import viz

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)

# A 4-stage cascaded ladder (8th order) models a multi-stage PDN: bulk decap ->
# mid-board decap -> on-die decap, each contributing an R-L-C stage.
net = cascaded_ladder(n_stages=4, seed=42)
print(f"Ground-truth network: {net.name}, {len(net.poles)} poles")
print(f"Poles: {net.poles}\n")

# Sweep every method against every excitation type it supports, clean data first.
print("=== Clean data ===")
df_clean = run_benchmark(net, order=8, methods=ALL_METHODS,
                          excitations=["impulse", "step", "chirp", "prbs"])
print(df_clean[["method", "excitation", "pole_err_rel", "passive", "runtime_s", "success"]]
      .sort_values("pole_err_rel").to_string(index=False))

# Now with realistic measurement noise (40dB SNR -- a common bench-measurement level).
print("\n=== 40dB SNR ===")
df_noisy = run_benchmark(net, order=8, methods=ALL_METHODS,
                          excitations=["impulse", "step", "chirp", "prbs"],
                          noise_db_list=[40])
print(df_noisy[["method", "excitation", "pole_err_rel", "passive", "runtime_s", "success"]]
      .sort_values("pole_err_rel").to_string(index=False))

# Save a comparison chart.
path = viz.plot_benchmark_comparison(df_clean, "/tmp/method_comparison_clean.png",
                                      title="Pole recovery error by method (clean data)")
print(f"\nComparison chart saved to {path}")

print("\nConclusion: read the sorted table above -- the best method for THIS network/"
      "excitation/noise combination is whichever has the lowest pole_err_rel with "
      "passive=True and success=True. Re-run with your own topology/noise levels "
      "rather than trusting this one example's ranking to generalize.\n"
      "\n"
      "Two results worth understanding, not ignoring, if you see them:\n"
      "  - 'sparam' underperforms 'vfit' on this specific network: cascaded_ladder's\n"
      "    output is a TRANSFER characteristic (last-stage voltage), not a driving-\n"
      "    point/reflection impedance -- the standard 1-port S=(Z-z0)/(Z+z0) formula\n"
      "    sparam uses is only valid for the latter. This is a real physical\n"
      "    modeling constraint, not a bug: use sparam on genuine 1-port reflection\n"
      "    data (see series_rlc/parallel_rlc, or real VNA S11 measurements).\n"
      "  - 'subspace' with a 'step' excitation can underperform at high order when\n"
      "    poles span a wide magnitude range: a step has zero energy at nonzero\n"
      "    frequencies (see Section 3 of the accompanying analysis), so ARX must\n"
      "    infer B/D entirely from the transient -- and equal per-sample weighting\n"
      "    lets late near-steady-state samples dominate the fit. Broadband\n"
      "    excitation (chirp/prbs) avoids this; that is the point of this table.")
