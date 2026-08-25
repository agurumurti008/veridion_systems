"""
examples/example3_silicon.py
LDO Phase 3 silicon calibration walkthrough.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import torch
except ImportError:
    import torch_shim  # noqa
    import torch

import numpy as np
import json

print("=" * 60)
print("  Example 3 — LDO Phase 3 Silicon Calibration")
print("=" * 60)

os.makedirs('output', exist_ok=True)

# ── 1. Build LDO specKG ─────────────────────────────────────────────────────
from core.spec_kg.knowledge_graph import build_ldo_kg
kg = build_ldo_kg()
print(f"\n[Example3] LDO specKG: {len(kg.specs)} specs, {len(kg.ports)} ports")

# ── 2. Generate demo silicon CSV ────────────────────────────────────────────
from core.phases.phase3_silicon import Phase3SiliconCalibration, SiliconMeasurement

phase3 = Phase3SiliconCalibration(kg)

sim_predictions = {
    'Output_Voltage': 1.800,
    'PSRR_1kHz':      80.0,
    'Phase_Margin':   60.0,
}

# Generate 5 corners × 3 chips = 15 silicon measurements
corners = ['TT', 'SS', 'FF', 'SF', 'FS']
rng     = np.random.default_rng(42)
silicon_data = []

for chip_idx in range(15):
    corner = corners[chip_idx % 5]
    chip_id = f'chip_{chip_idx:03d}_{corner}'
    temp    = [-40.0, 27.0, 125.0][chip_idx % 3]
    vdd     = [1.62, 1.80, 1.98][chip_idx % 3]

    meas = {}
    corner_bias = {'TT': 0.0, 'SS': -0.04, 'FF': +0.035, 'SF': -0.02, 'FS': +0.02}
    cb = corner_bias.get(corner, 0.0)
    for spec_name, sim_val in sim_predictions.items():
        noise = rng.uniform(-0.04, 0.04)
        meas[spec_name] = float(sim_val) * (1 + noise + cb)

    silicon_data.append(SiliconMeasurement(
        chip_id=chip_id,
        pvt_corner=corner,
        temperature=temp,
        vdd=vdd,
        measurements=meas,
    ))

# Save silicon CSV
silicon_csv_path = 'output/silicon_demo_15chips.csv'
header = 'chip_id,pvt_corner,temperature,vdd,' + ','.join(sim_predictions.keys())
rows = []
for sm in silicon_data:
    row = [sm.chip_id, sm.pvt_corner, str(sm.temperature), str(sm.vdd)]
    row += [str(sm.measurements[k]) for k in sim_predictions.keys()]
    rows.append(','.join(row))

with open(silicon_csv_path, 'w', encoding='utf-8') as f:
    f.write(header + '\n')
    f.write('\n'.join(rows))

print(f"\n[Example3] Silicon CSV → {silicon_csv_path}")
print(f"  Chips: {len(silicon_data)}, Corners: {corners}")
print(f"\n  First 3 rows:")
print(f"  {'Chip ID':<20} {'Corner':<6} {'Temp':>6} {'VDD':>6} {'Vout':>8} {'PSRR':>8} {'PM':>6}")
print(f"  {'-'*65}")
for sm in silicon_data[:3]:
    print(f"  {sm.chip_id:<20} {sm.pvt_corner:<6} {sm.temperature:>6.0f} "
          f"{sm.vdd:>6.2f} "
          f"{sm.measurements.get('Output_Voltage',0):>8.4f} "
          f"{sm.measurements.get('PSRR_1kHz',0):>8.2f} "
          f"{sm.measurements.get('Phase_Margin',0):>6.2f}")

# ── 3. Compute gap table ────────────────────────────────────────────────────
print("\n── Gap Analysis (all 15 chips × 3 specs) ──")
gaps = phase3.compute_gaps(silicon_data, sim_predictions)

# ── 4. Per-spec statistics ──────────────────────────────────────────────────
print("\n── Per-Spec Gap Statistics ──")
for spec_name in sim_predictions.keys():
    all_pcts = []
    for chip_id, chip_gaps in gaps.items():
        for g in chip_gaps:
            if g['spec'] == spec_name:
                all_pcts.append(g['gap_pct'])
    if all_pcts:
        arr = np.array(all_pcts)
        n_high = sum(1 for x in all_pcts if abs(x) > 10)
        severity = 'HIGH' if n_high > 5 else 'MEDIUM' if n_high > 0 else 'LOW'
        print(f"  {spec_name:<25}: mean={arr.mean():>6.2f}% "
              f"max={np.abs(arr).max():>5.2f}% "
              f"std={arr.std():>5.2f}  severity={severity}")

# ── 5. Fit gap correction ODE ────────────────────────────────────────────────
print("\n── Fitting Gap Correction ODE (200 epochs) ──")
n_t = 100
t_span    = np.linspace(0, 1e-4, n_t)
sim_traj  = np.ones((n_t, 1)) * sim_predictions['Output_Voltage']
sil_mean  = np.mean([sm.measurements['Output_Voltage'] for sm in silicon_data])
sil_traj  = np.linspace(sil_mean * 0.95, sil_mean, n_t).reshape(-1, 1)

phase3.fit_gap_correction(sim_traj, sil_traj, t_span, epochs=200)

# ── 6. Device insights ──────────────────────────────────────────────────────
print("\n── Device Insights with Suggested PDK Parameters ──")
insights = phase3.extract_device_insights()

print(f"\n  {'Factor':<22} {'Value':>8} {'PDK Param':<14} {'Action'}")
print(f"  {'-'*70}")
for fname, info in insights.items():
    print(f"  {fname:<22} {info['factor']:>8.4f} "
          f"{info['suggested_param']:<14} {info['action']}")

# ── 7. Generate Phase 3 Verilog-A ────────────────────────────────────────────
print("\n── Phase 3 Verilog-A Generation ──")
p3_va_path = phase3.generate_phase3_veriloga(output_dir='output')
print(f"  Phase 3 Verilog-A: {p3_va_path}")

# ── 8. Save JSON reports ─────────────────────────────────────────────────────
gap_report_path  = 'output/gap_report_example3.json'
insights_path    = 'output/device_insights_example3.json'

# Serialise gaps (convert to str-safe)
gap_serial = {}
for cid, glist in gaps.items():
    gap_serial[cid] = [{k: str(v) for k, v in g.items()} for g in glist]
with open(gap_report_path, 'w', encoding='utf-8') as f:
    json.dump(gap_serial, f, indent=2)

# Serialise insights
insights_serial = {k: {ik: str(iv) for ik, iv in v.items()} for k, v in insights.items()}
with open(insights_path, 'w', encoding='utf-8') as f:
    json.dump(insights_serial, f, indent=2)

print(f"\n  Gap Report       → {gap_report_path}")
print(f"  Device Insights  → {insights_path}")
print(f"  Silicon CSV      → {silicon_csv_path}")

print("\n" + "=" * 60)
print("  Example 3 COMPLETE")
print("=" * 60)
