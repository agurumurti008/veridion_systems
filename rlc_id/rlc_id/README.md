# rlc_id

RLC network system-identification framework. Prony, ERA, Vector Fitting, subspace
(ARX-based realization), S-parameter, and Laplace-domain verification implemented
as interchangeable strategies behind a common interface, benchmarked against
synthetic ground-truth RLC networks with known analytical poles.

See the accompanying technical analysis for the theory (identifiability limits,
excitation design, method tradeoffs, post-silicon anomaly detection) this
framework is built to let you verify empirically rather than take on faith.

## Install

```bash
uv sync
```

## Quickstart

```bash
python examples/quickstart.py              # fit one method, check against ground truth
python examples/compare_all_methods.py     # the core deliverable: prove which method wins
python examples/anomaly_detection_demo.py  # golden-vs-measured PDN anomaly detection
```

Or via the CLI:

```bash
rlc-id excite --type prbs --duration 1e-6 --out exc.csv
rlc-id fit --method era --data waveform.csv --order 8
rlc-id benchmark --topology cascaded --order 6 --methods all --excitations all --out report.csv
rlc-id anomaly --golden golden.json --measured measured.csv --explain --out anomaly.json
```

## Architecture

Every identification method implements the same interface (`core/base.py`):

```python
class RLCIdentifier(ABC):
    def fit(self, t_or_f, u, y, order=None) -> "RLCIdentifier": ...
    def poles(self) -> np.ndarray: ...
    def state_space(self) -> StateSpaceModel: ...
    def predict(self, u_new, t_new) -> np.ndarray: ...
    def is_passive(self) -> bool: ...
    def to_spice_netlist(self) -> str: ...
```

`eval.py`'s `run_benchmark()` loops over methods uniformly, scoring each against a
`synth.py` ground-truth network's *known* analytical poles (Hungarian-matched) --
this is what makes the comparison a proof rather than an assertion.

## Method selection guide

| Method | Domain | Excitation | Best for | Known limitation |
|---|---|---|---|---|
| **Prony** | Time | Free/impulse response only | Low-order (<8), clean data | Minimal-order fit has ~zero noise averaging; fragile above ~1e-4 relative noise |
| **ERA** | Time | Impulse or step | Clean impulse/step data, any order | Finite-pulse approximation of a true impulse costs accuracy (see `test_era_finite_pulse_practical_approximation`) |
| **Vector Fitting** | Frequency | N/A (internal sweep) | Wideband S/Y/Z data, any order, passivity enforcement | Requires the frequency sweep to actually cover the pole band -- a mismatched sweep silently starves the fit (see `test_vf_cascaded_ladder_mismatched_bandwidth_degrades_gracefully`) |
| **Subspace (ARX)** | Time | **Arbitrary** (step/chirp/PRBS/multitone) | General driven data, any order | Constant/step input has zero energy at nonzero frequencies -- B/D become unidentifiable (persistence-of-excitation violation, not a bug) |
| **S-parameter** | Frequency | N/A (VNA sweep) | Real 1-port reflection (S11) data | The S=(Z-z0)/(Z+z0) conversion assumes driving-point impedance; using it on a transfer characteristic (e.g. a different observation port) is a modeling error, not identification failure |
| **Laplace verify** | N/A | N/A | Sanity-checking an already-fitted model | Not a blind identifier -- takes a candidate pole-residue model and evaluates it analytically |

## The non-uniqueness limitation

**This tool recovers a realization, not necessarily the physical circuit.**
Component-level identification (specific R, L, C values mapped to a specific
topology) is fundamentally unidentifiable from port measurements alone --
Foster/Cauer/Brune/Bott-Duffin network synthesis theory guarantees multiple
distinct RLC topologies produce identical port behavior. What every method here
actually recovers is a transfer-function-equivalent realization (poles, zeros,
residues) -- unique up to that equivalence class, not down to physical
component values, unless you constrain the fit to a known topology (see
`anomaly.py`, which sidesteps this by assuming the golden topology and fitting
only parameter deviations).

## Running tests

```bash
uv run pytest tests/ -v
```

`tests/test_analytical_rlc.py` validates every synthetic network against
closed-form pole formulas (series/parallel RLC) before anything else is trusted.
Each method's test file documents its validated accuracy regime and known failure
modes explicitly -- e.g. `test_prony_classic_is_noise_fragile_by_design` confirms
(not "fixes") a textbook limitation.

## References

- Van Valkenburg, *Introduction to Modern Network Synthesis*, Wiley (Foster/Cauer/Brune)
- Bott, R., Duffin, R.J., "Impedance synthesis without use of transformers," *J. Applied Physics*, 1949
- Marple, S.L., *Digital Spectral Analysis with Applications*, Prentice-Hall, 1987 (Prony)
- Juang, J.-N., Pappa, R.S., "An eigensystem realization algorithm...", *J. Guidance, Control, and Dynamics*, 1985 (ERA)
- Gustavsen, B., Semlyen, A., "Rational approximation of frequency domain responses by vector fitting," *IEEE Trans. Power Delivery* 14(3), 1999
- Ho, B.L., Kalman, R.E., "Effective construction of linear state-variable models...", *Regelungstechnik*, 1966
- Ljung, L., *System Identification: Theory for the User*, 2nd ed., Prentice Hall, 1999 (ARX, persistence of excitation)
- Van Overschee, P., De Moor, B., *Subspace Identification for Linear Systems*, Kluwer, 1996
- Pozar, D.M., *Microwave Engineering*, 4th ed., Wiley, 2011 (S-parameters)
- Swaminathan, M., Engin, A.E., *Power Integrity Modeling and Design for Semiconductors and Systems*, Prentice Hall, 2007
