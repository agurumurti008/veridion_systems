"""Unified CLI for rlc_id.

Usage:
  rlc-id fit --method {prony,era,vfit,subspace,sparam} --data path.csv --order 8
  rlc-id excite --type {step,ramp,impulse,chirp,multitone,prbs} --duration 1e-6 --out excitation.csv
  rlc-id benchmark --topology cascaded --order 6 --methods all --excitations all --out report.csv
  rlc-id anomaly --golden golden.json --measured measured.csv --out anomaly_report.json
"""
from __future__ import annotations
import argparse
import json
import numpy as np

from . import excitation as exc
from .dataloader import load_csv, save_csv, WaveformData
from .synth import series_rlc, parallel_rlc, cascaded_ladder
from .eval import run_benchmark, ALL_METHODS
from .methods.era import ERAIdentifier
from .methods.vector_fitting import VectorFittingIdentifier
from .methods.prony import PronyIdentifier
from .methods.subspace import SubspaceIdentifier
from .methods.sparam import SParameterIdentifier

METHOD_MAP = {"era": ERAIdentifier, "prony": PronyIdentifier, "subspace": SubspaceIdentifier,
              "vfit": VectorFittingIdentifier, "sparam": SParameterIdentifier}


def cmd_fit(args):
    data = load_csv(args.data, freq_col="freq" if args.freq_domain else None)
    method_cls = METHOD_MAP[args.method]
    ident = method_cls()
    if data.is_frequency_domain:
        ident.fit(data.time_or_freq, None, data.y, order=args.order)
    else:
        u = data.u if data.u is not None else np.zeros_like(data.time_or_freq)
        ident.fit(data.time_or_freq, u, data.y, order=args.order)

    poles = ident.poles()
    print(f"Fitted {args.method} (order={args.order}):")
    for i, p in enumerate(poles):
        print(f"  pole[{i}] = {p:.6e}")
    print(f"  passive: {ident.is_passive()}")
    if args.netlist_out:
        with open(args.netlist_out, "w") as f:
            f.write(ident.to_spice_netlist())
        print(f"Netlist written to {args.netlist_out}")


def cmd_excite(args):
    kwargs = {}
    if args.n_points:
        kwargs["n_points"] = args.n_points
    if args.f0:
        kwargs["f0"] = args.f0
    if args.f1:
        kwargs["f1"] = args.f1
    t, u = exc.generate(args.type, args.duration, **kwargs)
    save_csv(WaveformData(t, u, np.zeros_like(t)), args.out)
    print(f"Wrote {args.type} excitation ({len(t)} points) to {args.out}")


def cmd_benchmark(args):
    if args.topology == "series":
        net = series_rlc(50.0, 1e-6, 1e-9)
    elif args.topology == "parallel":
        net = parallel_rlc(1000.0, 1e-6, 1e-9)
    elif args.topology == "cascaded":
        n_stages = args.order // 2 if args.order else 3
        net = cascaded_ladder(n_stages=n_stages, seed=args.seed)
    else:
        raise ValueError(f"unknown topology '{args.topology}'")

    methods = ALL_METHODS if args.methods == "all" else args.methods.split(",")
    excitations = ["impulse", "step", "chirp", "prbs"] if args.excitations == "all" \
        else args.excitations.split(",")
    order = args.order or len(net.poles)

    df = run_benchmark(net, order=order, methods=methods, excitations=excitations)
    df.to_csv(args.out, index=False)
    print(f"Benchmark ({len(df)} runs) written to {args.out}")
    print(df[["method", "excitation", "pole_err_rel", "passive", "runtime_s", "success"]]
          .to_string(index=False))


def cmd_anomaly(args):
    from .anomaly import fit_golden_and_measured, diff_poles, component_sensitivity, explain_shift
    from .synth import cascaded_ladder_from_components

    with open(args.golden) as f:
        golden_spec = json.load(f)
    golden_net = cascaded_ladder_from_components(golden_spec["stages"])

    measured = load_csv(args.measured, freq_col="freq", real_col="real", imag_col="imag")
    vf_golden, vf_measured = fit_golden_and_measured(
        golden_net, measured.time_or_freq, measured.y, order=len(golden_net.poles))
    report = diff_poles(vf_golden.poles(), vf_measured.poles(), rel_threshold=args.threshold)
    print(report.summary())

    output = {
        "n_anomalies": len(report.anomalies),
        "anomalies": [{"golden_pole": str(s.golden_pole), "measured_pole": str(s.measured_pole),
                        "rel_shift": s.rel_shift} for s in report.anomalies],
    }
    if args.explain and report.anomalies:
        sens = component_sensitivity(golden_spec["stages"])
        output["explanations"] = []
        for s in report.anomalies:
            candidates = explain_shift(s, sens)
            output["explanations"].append({"golden_pole": str(s.golden_pole), "candidates": candidates})

    with open(args.out, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"Anomaly report written to {args.out}")


def main():
    parser = argparse.ArgumentParser(prog="rlc-id", description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_fit = sub.add_parser("fit", help="Fit a single method to waveform data")
    p_fit.add_argument("--method", required=True, choices=list(METHOD_MAP))
    p_fit.add_argument("--data", required=True)
    p_fit.add_argument("--order", type=int, default=None)
    p_fit.add_argument("--freq-domain", action="store_true")
    p_fit.add_argument("--netlist-out", default=None)
    p_fit.set_defaults(func=cmd_fit)

    p_exc = sub.add_parser("excite", help="Generate an excitation waveform")
    p_exc.add_argument("--type", required=True, choices=list(exc.GENERATORS))
    p_exc.add_argument("--duration", type=float, required=True)
    p_exc.add_argument("--n-points", type=int, default=2000)
    p_exc.add_argument("--f0", type=float, default=None)
    p_exc.add_argument("--f1", type=float, default=None)
    p_exc.add_argument("--out", required=True)
    p_exc.set_defaults(func=cmd_excite)

    p_bench = sub.add_parser("benchmark", help="Run the multi-method benchmark harness")
    p_bench.add_argument("--topology", choices=["series", "parallel", "cascaded"], default="cascaded")
    p_bench.add_argument("--order", type=int, default=None)
    p_bench.add_argument("--methods", default="all")
    p_bench.add_argument("--excitations", default="all")
    p_bench.add_argument("--seed", type=int, default=42)
    p_bench.add_argument("--out", required=True)
    p_bench.set_defaults(func=cmd_benchmark)

    p_anom = sub.add_parser("anomaly", help="Golden-vs-measured anomaly detection")
    p_anom.add_argument("--golden", required=True, help="JSON with {'stages': [{'R','L','C'},...]}")
    p_anom.add_argument("--measured", required=True, help="CSV with freq,real,imag columns")
    p_anom.add_argument("--threshold", type=float, default=0.05)
    p_anom.add_argument("--explain", action="store_true")
    p_anom.add_argument("--out", required=True)
    p_anom.set_defaults(func=cmd_anomaly)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
