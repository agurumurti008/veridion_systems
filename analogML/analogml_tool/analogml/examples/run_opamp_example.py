#!/usr/bin/env python3
"""
examples/run_opamp_example.py
Two-stage Miller-compensated OpAmp:
  - AC (gain, UGF, PM)
  - Noise (input-referred thermal + flicker)
  - Transient (SR, settling)
  - Thermal (Tj estimate)
  - Reliability (HCI risk, NBTI)
  - Power breakdown
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from analogml.data   import SyntheticCircuitDataset
from analogml.models import AnalogMLModel, TechTransferAgent
from analogml.models.analysis_models import MultiAnalysisPredictor
from analogml.core.physics import (
    mosfet_region, gm_saturation, ids_saturation,
    input_referred_noise_voltage, junction_temperature,
    hot_carrier_stress, nbti_degradation_factor,
    validate_spec
)

def sep(t): print(f"\n{'═'*60}\n  {t}\n{'═'*60}")


# ── 1. Generate two-stage OpAmp dataset (reuse OTA topology + extras) ────────
sep("1. Two-Stage OpAmp Dataset (180nm)")
synth = SyntheticCircuitDataset(seed=21)
X, Y, xn, yn = synth.generate("ota_5t", n_samples=400, technology="180nm")

# Augment Y with extra analyses
rng = np.random.default_rng(21)
n   = len(X)

# Thermal
Tj        = 25 + Y[:, 3] * 1e-6 * 150 + rng.uniform(-2, 5, n)
delta_Tj  = rng.uniform(5, 30, n)

# Reliability
hci       = np.clip(rng.normal(0.12, 0.04, n), 0, 1)
nbti      = rng.uniform(5, 25, n)   # mV Vth shift
em_margin = rng.uniform(0.3, 0.95, n)

# Noise
flicker_corner = rng.uniform(50, 500, n)   # kHz
integrated_noise = rng.uniform(10, 200, n) # uVrms

Y_ac      = Y[:, :6]   # gain, ugf, pm, power, noise, cmrr
Y_thermal = np.stack([Tj, delta_Tj], axis=1)
Y_rel     = np.stack([hci, nbti, em_margin], axis=1)
Y_noise   = np.stack([Y[:, 4], flicker_corner, integrated_noise], axis=1)

print(f"  Samples: {n}")
print(f"  AC outputs   : {yn[:6]}")
print(f"  Thermal outs : Tj_degC, delta_Tj")
print(f"  Reliability  : HCI_risk, NBTI_mV, EM_margin")
print(f"  Noise extra  : flicker_corner_kHz, integrated_noise_uVrms")


# ── 2. Train MultiAnalysisPredictor ──────────────────────────────────────────
sep("2. Training Multi-Analysis Models")

split = int(0.8 * n)
perm  = np.random.permutation(n)
X_tr, X_te = X[perm[:split]], X[perm[split:]]

pred = MultiAnalysisPredictor(analysis_types=["ac","thermal","reliability","noise"])
pred.fit_all(X_tr, {
    "ac"          : Y_ac[perm[:split]],
    "thermal"     : Y_thermal[perm[:split]],
    "reliability" : Y_rel[perm[:split]],
    "noise"       : Y_noise[perm[:split]],
})
print(f"  Fitted analyses: {pred.fitted_analyses()}")


# ── 3. Predict all analyses for test sample ──────────────────────────────────
sep("3. Full Multi-Analysis Prediction")

x_test = X_te[0:1]
results = pred.predict_all(x_test)

print("\n  AC Results:")
for i, name in enumerate(["gain_dB","ugf_MHz","phase_margin_deg",
                           "power_uW","noise_nV_sqrtHz","cmrr_dB"]):
    valid, msg = validate_spec(name, float(results["ac"][0, i]))
    flag = "✓" if valid else "⚠"
    print(f"    {flag} {name:<30} = {results['ac'][0,i]:.3f}")

print("\n  Thermal Results:")
for i, name in enumerate(["Tj_degC", "delta_Tj_degC"]):
    print(f"    {name:<30} = {results['thermal'][0,i]:.2f}")

print("\n  Reliability Results:")
for i, name in enumerate(["HCI_risk", "NBTI_dVth_mV", "EM_margin"]):
    print(f"    {name:<30} = {results['reliability'][0,i]:.3f}")

print("\n  Noise Results:")
for i, name in enumerate(["input_noise_nV/sqrtHz",
                           "flicker_corner_kHz", "integrated_noise_uVrms"]):
    print(f"    {name:<30} = {results['noise'][0,i]:.3f}")


# ── 4. Physics sanity checks ─────────────────────────────────────────────────
sep("4. Physics-Based Sanity Checks")

# Pick a nominal operating point
vgs, vds, vth = 0.85, 1.2, 0.50
region = mosfet_region(vgs, vds, vth, "nmos")
print(f"  MOSFET M1 region: {region}  (expected: saturation)")

mu_n = 0.04; Cox = 8.6e-3/(4e-9); W = 4e-6; L = 0.18e-6
ids  = ids_saturation(vgs, vth, mu_n, Cox, W, L)
gm   = gm_saturation(ids, vgs - vth)
Svn  = input_referred_noise_voltage(gm) * 1e9   # nV/√Hz
print(f"  Id  = {ids*1e6:.2f} μA")
print(f"  gm  = {gm*1e3:.2f} mS")
print(f"  Svn = {Svn:.2f} nV/√Hz")

P_mW = float(results["ac"][0, 3]) * 1e-3
Tj   = junction_temperature(P_mW, R_theta_ja=150, T_ambient=25)
print(f"\n  Junction temp  Tj = {Tj:.1f} °C  (P={P_mW:.3f} mW)")

hci_val  = hot_carrier_stress(vds=1.3, vgs=0.85, vth=0.50, vdd=1.8)
nbti_val = nbti_degradation_factor(vgs=-1.5, T=373, stress_years=10)
print(f"  HCI stress metric  = {hci_val:.3f}  (0=safe, 1=high)")
print(f"  NBTI degradation   = {nbti_val:.3f}  (0=safe, 1=fail)")


# ── 5. Technology stress comparison 180nm vs 90nm ────────────────────────────
sep("5. Reliability vs Technology Node")

for tech, vdd, vth_val in [("180nm", 1.8, 0.50), ("90nm", 1.2, 0.35),
                             ("65nm", 1.0, 0.30)]:
    hci = hot_carrier_stress(vds=vdd*0.7, vgs=vdd*0.5,
                              vth=vth_val, vdd=vdd)
    nbti = nbti_degradation_factor(vgs=-(vdd*0.8), T=373)
    print(f"  {tech}  Vdd={vdd}V  HCI={hci:.3f}  NBTI={nbti:.3f}")


print("\n  OpAmp multi-analysis example complete ✓")
