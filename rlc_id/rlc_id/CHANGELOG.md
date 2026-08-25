# Changelog

## v0.1.0 -- initial implementation

### Added
- `core/base.py`: `RLCIdentifier` ABC, `StateSpaceModel`, `PoleZeroModel` dataclasses, Foster-II netlist export
- `core/utils.py`: Hankel construction, SVD-knee order selection, pole canonicalization/matching, state-space -> pole-residue conversion
- `synth.py`: series/parallel RLC (closed-form poles), cascaded ladder, Foster/Cauer realization helpers, noise/bandwidth-limited simulation
- `methods/era.py`: Eigensystem Realization Algorithm (Juang & Pappa, 1985)
- `methods/vector_fitting.py`: Vector Fitting (Gustavsen & Semlyen, 1999) with passivity enforcement
- `methods/prony.py`: classic + robust (over-specified-order) Prony
- `methods/subspace.py`: ARX + canonical realization for arbitrary driven input
- `methods/sparam.py`: S-parameter wrapper (delegates to Vector Fitting)
- `methods/laplace_verify.py`: forward-model analytical verifier (not a blind identifier)
- `excitation.py`: step, ramp, impulse, chirp, multitone, PRBS generators
- `eval.py`: multi-method benchmark harness with per-method excitation compatibility
- `anomaly.py`: golden-vs-measured differencing + component sensitivity analysis
- `viz.py`, `dataloader.py`, `cli.py`, `examples/`
- Full pytest suite (91 tests) validating every method against closed-form/analytical ground truth

### Fixed during development (documented for anyone extending this codebase)
- **ERA**: `interp=True` default in `scipy.signal.lsim` turns a single-sample impulse
  into a triangular pulse with half the intended area, corrupting gain by 2x --
  fixed via `interp=False` (zero-order hold) in `synth.simulate()`
- **ERA**: spurious non-decaying D term from sampling *during* the driving pulse
  itself (not the free response) -- fixed by forcing D=0 for strictly-proper systems
- **ERA**: missing `*dt` factor in the step-response differentiation pathway (gain
  off by ~1/dt)
- **Vector Fitting**: pole seeding degenerates to the sweep's minimum frequency
  when `n_pairs==1` (single-resonance case) -- fixed via interior log-grid points
- **Vector Fitting**: severe numerical conditioning failure across wide frequency
  sweeps (raw `s` values spanning many decades) -- fixed via frequency
  normalization + row weighting + column-equilibrated least squares
- **Vector Fitting**: eigenvalue solver doesn't guarantee adjacent conjugate-pair
  ordering, but the real-coefficient basis assumed it -- silently mis-paired poles;
  fixed via `canonicalize_poles()`
- **Vector Fitting**: integer-division bug in real/complex pole-seed count
  (`n_poles=6` seeded only 5 poles) -- fixed to guarantee exact count
- **Prony**: a naive "Steiglitz-McBride" step filtered the signal through the
  inverse of its own characteristic polynomial, un-decaying it into runaway growth
  -- replaced with the correct approach (SM requires driven I/O data, not a free
  response); now uses order over-specification + dominant-pole selection instead
- **Prony**: unstable roots from noise caused Vandermonde overflow in residue
  fitting -- fixed via a stabilization/reflection step
- **Prony**: `y[0]=0` (strict properness) is incompatible with a pure p-pole
  exponential-sum model, forcing a spurious near-zero "correction" pole that could
  dominate residue-magnitude-based selection -- fixed by dropping the leading
  sample (with residue time-shift correction)
- **Subspace**: an initial hand-rolled N4SID oblique-projection implementation was
  numerically unreliable -- replaced with ARX + canonical-form realization, a
  simpler and more robust path to the same general-input capability

### Known limitations (by design, not bugs -- see README and each method's tests)
- Component-level (not just pole-level) identification is fundamentally
  non-unique (Foster/Cauer/Brune equivalence)
- Prony and minimal-order Subspace/ARX are noise-fragile below ~1e-3 relative
  noise at minimal order -- this is textbook behavior, not a defect
  (see `test_prony_classic_is_noise_fragile_by_design`,
  `test_subspace_minimal_order_is_noise_sensitive_by_design`)
- A constant-step excitation cannot identify B/D via ARX (zero energy at nonzero
  frequency -- a genuine persistence-of-excitation violation, see
  `test_subspace_step_input_cannot_identify_gain_pe_violation`)
- `SParameterIdentifier`'s S<->Z/Y conversion assumes driving-point (reflection)
  impedance; applying it to a transfer characteristic is a modeling error
