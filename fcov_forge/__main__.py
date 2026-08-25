"""
fcov_forge/__main__.py
=======================
CLI entry point for FCovForge.

Usage:
  python -m fcov_forge generate --input features.yaml --output out/
  python -m fcov_forge cross --feature1 dma.width_cg --feature2 intr.priority_cg --input features.yaml --output out/
  python -m fcov_forge extract --doc spec.pdf --output extracted.yaml
  python -m fcov_forge validate --input features.yaml
  python -m fcov_forge report --input features.yaml --output coverage_plan.html
"""

import argparse
import sys
import os
from pathlib import Path


def cmd_generate(args):
    """Generate SV from YAML or Excel input."""
    sys.path.insert(0, str(Path(__file__).parent))
    from parsers.yaml_parser import parse_yaml
    from parsers.excel_parser import parse_excel
    from generators.sv_generator import generate_all

    input_path = Path(args.input)
    if input_path.suffix in (".xlsx", ".xls"):
        print(f"[FCovForge] Parsing Excel: {input_path}")
        model = parse_excel(input_path)
    else:
        print(f"[FCovForge] Parsing YAML: {input_path}")
        model = parse_yaml(input_path)

    print(f"[FCovForge] Model: {len(model.features)} feature(s), {len(model.feature_crosses)} cross(es)")
    output_dir = Path(args.output)
    generated = generate_all(model, output_dir)

    print(f"\n[FCovForge] Generated {len(generated)} file(s):")
    for desc, path in generated.items():
        print(f"  ✓ [{desc}] {path}")


def cmd_cross(args):
    """Add a cross between features/covergroups and generate."""
    sys.path.insert(0, str(Path(__file__).parent))
    from parsers.yaml_parser import parse_yaml
    from core.model import FeatureCross, FeatureCrossTarget
    from core.cross_engine import CrossEngine
    from generators.sv_generator import crosses_to_sv
    from pathlib import Path

    model = parse_yaml(args.input)

    # Build an ad-hoc FeatureCross from CLI args
    targets = [FeatureCrossTarget(address=t) for t in args.targets]
    cross_name = args.name or "_x_".join(t.split(".")[0] for t in args.targets)
    fc = FeatureCross(
        name=cross_name,
        targets=targets,
        goal=int(args.goal) if args.goal else 100,
        comment=args.comment or "",
    )
    model.feature_crosses.append(fc)

    engine = CrossEngine(model)
    errors = engine.validate()
    if errors:
        print("[CrossEngine] Errors:")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)

    crosses = engine.synthesize_all()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    sv_text = crosses_to_sv(crosses, model.project_name)
    out.write_text(sv_text)
    print(f"[FCovForge] Written: {out}")


def cmd_extract(args):
    """Extract features from spec document using AI."""
    sys.path.insert(0, str(Path(__file__).parent))
    from ai_extractor.extractor import AIExtractor

    extractor = AIExtractor(api_key=args.api_key)
    result = extractor.extract_from_file(
        path=args.doc,
        focus=args.focus or "all device features",
        output_yaml=args.output,
    )

    # Optionally suggest crosses
    if args.suggest_crosses and result.get("features"):
        import yaml
        crosses = extractor.suggest_crosses(result["features"])
        if crosses:
            result["feature_crosses"] = crosses
            print(f"[AI Extractor] Suggested {len(crosses)} feature cross(es)")
            if args.output:
                with open(args.output, "w") as f:
                    yaml.dump(result, f, default_flow_style=False, sort_keys=False)

    print(f"[FCovForge] Extracted {len(result.get('features', []))} feature(s)")


def cmd_validate(args):
    """Validate a YAML feature definition file."""
    sys.path.insert(0, str(Path(__file__).parent))
    from parsers.yaml_parser import parse_yaml
    from core.cross_engine import CrossEngine

    model = parse_yaml(args.input)
    engine = CrossEngine(model)
    errors = engine.validate()

    total_cgs = sum(len(f.covergroups) for f in model.features)
    total_cps = sum(len(cg.coverpoints) for f in model.features for cg in f.covergroups)
    total_bins = sum(
        len(cp.bins)
        for f in model.features
        for cg in f.covergroups
        for cp in cg.coverpoints
    )

    print(f"[FCovForge] Validation Report")
    print(f"  Features    : {len(model.features)}")
    print(f"  CoverGroups : {total_cgs}")
    print(f"  CoverPoints : {total_cps}")
    print(f"  Bins        : {total_bins}")
    print(f"  Feat Crosses: {len(model.feature_crosses)}")
    print()

    if errors:
        print(f"  ✗ {len(errors)} error(s) found:")
        for e in errors:
            print(f"    - {e}")
        sys.exit(1)
    else:
        print(f"  ✓ No errors found")


def cmd_report(args):
    """Generate an HTML coverage plan report."""
    sys.path.insert(0, str(Path(__file__).parent))
    from parsers.yaml_parser import parse_yaml
    from generators.html_report import generate_html_report

    model = parse_yaml(args.input)
    out = Path(args.output)
    generate_html_report(model, out)
    print(f"[FCovForge] Report written: {out}")


def main():
    parser = argparse.ArgumentParser(
        prog="fcov_forge",
        description="FCovForge — Feature-level functional coverage automation",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # generate
    gen_p = sub.add_parser("generate", help="Generate SV from YAML/Excel")
    gen_p.add_argument("--input", "-i", required=True, help="Input YAML or Excel file")
    gen_p.add_argument("--output", "-o", required=True, help="Output directory")

    # cross
    cross_p = sub.add_parser("cross", help="Define and generate a feature cross")
    cross_p.add_argument("--input", "-i", required=True, help="Input YAML")
    cross_p.add_argument("--targets", "-t", nargs="+", required=True,
                         help="Targets (e.g. feat1.cg1 feat2.cg2)")
    cross_p.add_argument("--output", "-o", required=True, help="Output .sv file")
    cross_p.add_argument("--name", help="Cross name (auto-generated if not set)")
    cross_p.add_argument("--goal", help="Coverage goal %", default="100")
    cross_p.add_argument("--comment", help="Cross description")

    # extract
    ext_p = sub.add_parser("extract", help="AI-extract features from spec document")
    ext_p.add_argument("--doc", required=True, help="Spec document (PDF/TXT/MD)")
    ext_p.add_argument("--output", "-o", required=True, help="Output YAML file")
    ext_p.add_argument("--api-key", help="Anthropic API key (or set ANTHROPIC_API_KEY)")
    ext_p.add_argument("--focus", help="What to focus extraction on")
    ext_p.add_argument("--suggest-crosses", action="store_true",
                       help="Also suggest feature crosses")

    # validate
    val_p = sub.add_parser("validate", help="Validate a YAML feature file")
    val_p.add_argument("--input", "-i", required=True, help="Input YAML file")

    # report
    rep_p = sub.add_parser("report", help="Generate HTML coverage plan")
    rep_p.add_argument("--input", "-i", required=True, help="Input YAML file")
    rep_p.add_argument("--output", "-o", default="coverage_plan.html", help="Output HTML")

    args = parser.parse_args()

    commands = {
        "generate": cmd_generate,
        "cross": cmd_cross,
        "extract": cmd_extract,
        "validate": cmd_validate,
        "report": cmd_report,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
