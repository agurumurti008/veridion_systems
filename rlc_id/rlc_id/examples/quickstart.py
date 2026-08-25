"""Quickstart: identify a series RLC network from its impulse response using ERA.

Run: python examples/quickstart.py
"""
import numpy as np
from rlc_id.synth import series_rlc
from rlc_id import excitation as exc
from rlc_id.methods.era import ERAIdentifier

# 1. Ground-truth network (in practice this would be unknown -- we use synth.py's
#    known analytical poles here only to score the identification afterward).
net = series_rlc(R=50.0, L=1e-6, C=1e-9)
true_poles = np.linalg.eigvals(net.ss[0])
print(f"True poles: {true_poles}")

# 2. Generate a realistic (finite-width, not literal Dirac) impulse excitation and
#    simulate the network's response.
alpha = -np.max(true_poles.real)
duration = 8 / alpha
t, u = exc.impulse(duration, n_points=800)
y = net.simulate(t, u)

# 3. Identify: ERA recovers a minimal state-space realization from the impulse
#    response via Hankel-matrix SVD (Juang & Pappa, 1985).
era = ERAIdentifier(input_type="impulse", svd_rel_threshold=1e-4)
era.fit(t, u, y, order=2)

print(f"Identified poles: {era.poles()}")
print(f"Passive: {era.is_passive()}")
rel_err = np.abs(np.sort_complex(era.poles()) - np.sort_complex(true_poles)) / np.abs(true_poles)
print(f"Relative pole error: {rel_err}")

# 4. Predict the response to a NEW excitation (a step, not the impulse used to fit)
#    and compare against ground truth.
t_step = np.linspace(0, duration, 800)
u_step = np.ones_like(t_step)
y_pred = era.predict(u_step, t_step)
y_true = net.simulate(t_step, u_step)
print(f"Step-response prediction NRMSE: {ERAIdentifier.fit_error(y_true, y_pred):.4f}")

# 5. Export a Foster-form SPICE netlist realization of the identified model.
print("\nSPICE netlist (Foster-II realization):")
print(era.to_spice_netlist())
