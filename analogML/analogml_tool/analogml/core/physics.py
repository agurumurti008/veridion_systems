"""
core/physics.py
Physics constraint helpers used by PINN loss and data validation.

Covers:
  - KCL node checker
  - MOSFET operating region classifier
  - Noise floor estimator
  - Thermal resistance model
  - Reliability / EM margin estimator
"""
from __future__ import annotations
import math
from typing import Dict, List, Tuple


# ── Constants ─────────────────────────────────────────────────────────────────
k_B  = 1.380649e-23     # Boltzmann (CODATA 2018 exact)
q    = 1.60217662e-19   # electron charge
T0   = 300.0            # nominal temperature [K]


# ─────────────────────────────────────────────────────────────────────────────
# MOSFET operating region
# ─────────────────────────────────────────────────────────────────────────────

class MOSFETRegion:
    OFF       = "off"
    LINEAR    = "linear"
    SATURATION= "saturation"
    SUBTHRESH = "subthreshold"

def mosfet_region(vgs: float, vds: float, vth: float,
                  device: str = "nmos") -> str:
    """Classify MOSFET operating region."""
    if device == "pmos":
        vgs, vds, vth = -vgs, -vds, -vth
    if vgs < vth:
        if vgs > vth - 0.1:
            return MOSFETRegion.SUBTHRESH
        return MOSFETRegion.OFF
    vdsat = vgs - vth
    if vds < vdsat:
        return MOSFETRegion.LINEAR
    return MOSFETRegion.SATURATION


def ids_saturation(vgs: float, vth: float, mu: float, cox: float,
                   W: float, L: float) -> float:
    """Id in saturation (long-channel square-law)."""
    vov = max(vgs - vth, 0)
    return 0.5 * mu * cox * (W / L) * vov**2


def gm_saturation(ids: float, vov: float) -> float:
    """Transconductance gm = 2*Id/Vov."""
    return 2 * ids / max(vov, 1e-9)


def gds_channel_length(ids: float, va: float) -> float:
    """Output conductance via channel-length modulation: gds = Id/Va."""
    return ids / max(abs(va), 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# KCL checker  (for netlist validation)
# ─────────────────────────────────────────────────────────────────────────────

def kcl_residual(currents_at_node: List[float],
                 tol: float = 1e-9) -> Tuple[float, bool]:
    """
    Returns (residual, is_satisfied).
    Sum of currents at a node must be zero (KCL).
    """
    res = sum(currents_at_node)
    return res, abs(res) < tol


# ─────────────────────────────────────────────────────────────────────────────
# Noise models
# ─────────────────────────────────────────────────────────────────────────────

def thermal_noise_current(gm: float, T: float = T0) -> float:
    """Thermal drain current noise PSD: Si = 4kT * (2/3) * gm  [A²/Hz]."""
    return 4 * k_B * T * (2/3) * gm


def flicker_noise_current(kf: float, ids: float, W: float, L: float,
                           cox: float, f: float) -> float:
    """
    Flicker (1/f) noise current PSD.
    Si_1f = Kf * Id^af / (Cox * W * L * f)
    """
    if f <= 0: return 0.0
    return kf * ids / (cox * W * L * f)


def input_referred_noise_voltage(gm: float, T: float = T0,
                                  gamma: float = 2/3) -> float:
    """
    Input-referred thermal noise voltage density [V/√Hz].
    Sv_n = sqrt(4kT*gamma/gm)
    """
    return math.sqrt(4 * k_B * T * gamma / max(gm, 1e-9))


def noise_figure(Rsource: float, gm_in: float,
                 T: float = T0) -> float:
    """
    Approximate noise figure [dB] for a single-transistor amplifier.
    NF = 1 + (2/3)*gm*Rs  (simplified)
    """
    nf_linear = 1 + (2/3) * gm_in * Rsource
    return 10 * math.log10(max(nf_linear, 1.0))


# ─────────────────────────────────────────────────────────────────────────────
# Thermal model
# ─────────────────────────────────────────────────────────────────────────────

def junction_temperature(P_diss: float, R_theta_ja: float,
                          T_ambient: float = 25.0) -> float:
    """Tj = Tambient + P * Rth_ja  [°C]."""
    return T_ambient + P_diss * R_theta_ja


def thermal_resistance_estimate(area_um2: float,
                                 substrate: str = "silicon") -> float:
    """
    Rough die thermal resistance estimate [°C/W].
    substrate: 'silicon' | 'soi' | 'gaas'
    """
    k_thermal = {"silicon": 150, "soi": 20, "gaas": 46}.get(substrate, 150)
    # Rth ~ 1 / (2 * k * sqrt(pi * A))
    A_m2 = area_um2 * 1e-12
    return 1.0 / (2 * k_thermal * math.sqrt(math.pi * max(A_m2, 1e-12)))


# ─────────────────────────────────────────────────────────────────────────────
# Reliability / EM margin
# ─────────────────────────────────────────────────────────────────────────────

def em_margin(J_actual: float, J_max: float) -> float:
    """Electromigration margin = (Jmax - J) / Jmax.  >0 → safe."""
    return (J_max - J_actual) / max(J_max, 1e-12)


def hot_carrier_stress(vds: float, vgs: float, vth: float,
                        vdd: float) -> float:
    """
    Hot-carrier injection risk metric (0→safe, 1→high risk).
    Proxy: (Vds - Vdsat) / Vdd
    """
    vdsat = max(vgs - vth, 0.05)
    hci   = (vds - vdsat) / max(vdd, 0.1)
    return max(0.0, min(1.0, hci))


def nbti_degradation_factor(vgs: float, T: float,
                              stress_years: float = 10) -> float:
    """
    NBTI threshold shift proxy for PMOS.
    ΔVth ∝ exp(Ea/kT) * t^0.25   (simplified)
    Returns normalized degradation (0→1).
    """
    Ea   = 0.5    # eV activation energy
    t_s  = stress_years * 3.15e7   # seconds
    Boltz_eV = 8.617e-5
    factor   = math.exp(-Ea / (Boltz_eV * max(T, 250)))
    delta    = factor * (t_s ** 0.25) * abs(vgs)
    return min(delta / 0.1, 1.0)   # normalize to Vth budget of 100mV


# ─────────────────────────────────────────────────────────────────────────────
# Physics-based spec bounds  (used to validate synthetic data)
# ─────────────────────────────────────────────────────────────────────────────

SPEC_BOUNDS: Dict[str, Tuple[float, float]] = {
    "gain_dB"           : (0,    120),
    "ugf_MHz"           : (0.001, 10000),
    "phase_margin_deg"  : (0,    89.9),
    "power_uW"          : (0.01, 1e6),
    "noise_nV_sqrtHz"   : (0.1,  1e4),
    "cmrr_dB"           : (20,   160),
    "slew_rate_V_us"    : (0.01, 1e4),
    "output_swing_V"    : (0,    5),
    "psrr_dB"           : (0,    140),
    "dropout_mV"        : (10,   2000),
}

def validate_spec(name: str, value: float) -> Tuple[bool, str]:
    """Check if a spec value is physically plausible."""
    if name not in SPEC_BOUNDS:
        return True, "unknown spec"
    lo, hi = SPEC_BOUNDS[name]
    if not (lo <= value <= hi):
        return False, f"{name}={value:.3f} outside [{lo}, {hi}]"
    return True, "ok"
