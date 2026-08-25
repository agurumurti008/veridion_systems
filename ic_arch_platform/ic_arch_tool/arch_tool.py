"""
IC Architecture Automation Tool — Main Entry Point
===================================================
Usage:
  python arch_tool.py --example iot
  python arch_tool.py --example mcu
  python arch_tool.py --example radar
  python arch_tool.py --spec my_spec.json
  python arch_tool.py --optimize --spec my_spec.json
  python arch_tool.py --brief --spec my_spec.json
  python arch_tool.py --full --example smartphone
"""

import sys
import json
import argparse
from core.arch_engine import parse_spec_from_dict, ArchitectureBuilder
from core.evaluator import ArchitectureEvaluator, ArchitectureOptimizer
from core.ml_engine import ArchKnowledgeBase, GNNArchAdvisor
from core.propagator import ArchitecturePropagator

# ─── Built-in Examples ────────────────────────────────────────────────────────

EXAMPLES = {
    "iot": {
        "app_domain": "iot_sensor",
        "process_node": "22nm",
        "supply_voltage": 1.8,
        "target_frequency": 48.0,
        "power_budget": 5.0,
        "area_budget": 4.0,
        "interface_standards": ["I2C", "SPI", "UART"],
        "performance_targets": {"adc_resolution": 12, "sleep_current_ua": 1},
    },
    "mcu": {
        "app_domain": "industrial_mcu",
        "process_node": "40nm",
        "supply_voltage": 3.3,
        "target_frequency": 200.0,
        "power_budget": 150.0,
        "area_budget": 25.0,
        "interface_standards": ["CAN", "Ethernet", "I2C", "SPI", "UART"],
        "performance_targets": {"flash_mb": 2, "ram_kb": 512},
    },
    "radar": {
        "app_domain": "radar_chip",
        "process_node": "16nm",
        "supply_voltage": 1.0,
        "target_frequency": 1000.0,
        "power_budget": 2000.0,
        "area_budget": 50.0,
        "interface_standards": ["Ethernet"],
        "performance_targets": {"range_m": 250},
    },
    "smartphone": {
        "app_domain": "smartphone_soc",
        "process_node": "4nm",
        "supply_voltage": 0.75,
        "target_frequency": 3000.0,
        "power_budget": 5000.0,
        "area_budget": 100.0,
        "interface_standards": ["USB2", "Ethernet"],
    },
}


def _sep(char="─", n=68):
    print(char * n)


def run_full_flow(spec_dict: dict, optimize: bool = True, show_briefs: bool = True):
    print("\n" + "═" * 68)
    print("  IC ARCHITECTURE AUTOMATION TOOL  |  Full Analysis Flow")
    print("═" * 68)

    # 1. Parse spec
    print("\n[1/6] Parsing specification...")
    spec = parse_spec_from_dict(spec_dict)
    print(f"  Domain    : {spec.app_domain}")
    print(f"  Process   : {spec.process_node}")
    print(f"  Frequency : {spec.target_frequency} MHz")
    print(f"  Power Bdg : {spec.power_budget} mW")
    print(f"  Area Bdg  : {spec.area_budget} mm²")

    # 2. Build architecture
    print("\n[2/6] Building initial architecture...")
    builder = ArchitectureBuilder()
    graph = builder.build(spec)
    print(f"  IPs added         : {len(graph.ip_blocks)}")
    print(f"  Interconnects     : {len(graph.interconnects)}")
    print(f"  Initial power     : {graph.total_power():.1f} mW")
    print(f"  Initial area      : {graph.total_area():.3f} mm²")

    # 3. Initial evaluation
    print("\n[3/6] Running architecture quality assessment...")
    evaluator = ArchitectureEvaluator()
    result = evaluator.evaluate(graph)
    _sep()
    print(f"  Composite Score : {result.composite_score:.4f}  |  Grade: {result.grade}")
    print(f"  Composite Loss  : {result.composite_loss:.4f}")
    _sep()
    print("  Dimension Scores:")
    for k, v in result.scores.items():
        bar = "█" * int(v * 20) + "░" * (20 - int(v * 20))
        print(f"  {k:<20s} {bar} {v:.3f}")
    _sep()
    if result.violations:
        print("  ⚠ VIOLATIONS:")
        for v in result.violations:
            print(f"    ✗ {v}")
    print("  SUGGESTIONS:")
    for s in result.suggestions:
        print(f"    → {s}")

    # 4. ML knowledge base
    print("\n[4/6] Querying knowledge base & GNN advisor...")
    kb = ArchKnowledgeBase()
    advisor = GNNArchAdvisor(kb)
    similar = kb.find_similar(graph, top_k=3)
    print("  Similar historical designs:")
    for sim, design in similar:
        print(f"    {design.design_id}  [{design.app_domain}]  "
              f"score={design.composite_score:.2f}  sim={sim:.3f}")
    learnings = kb.extract_learnings(spec.app_domain)
    if learnings:
        print(f"  Domain learnings ({spec.app_domain}):")
        print(f"    Avg score: {learnings.get('avg_score', 'N/A')}  "
              f"Best: {learnings.get('best_design', 'N/A')}")
    recs = advisor.recommend_ips(graph, top_k=3)
    if recs:
        print("  GNN-recommended IPs to consider adding:")
        for ip_id, score in recs:
            print(f"    + {ip_id:<20s} (relevance={score:.3f})")

    # 5. Optimization loop
    if optimize:
        print("\n[5/6] Running iterative optimization loop...")
        _sep()
        optimizer = ArchitectureOptimizer(evaluator, max_iterations=15)
        graph, result, history = optimizer.optimize(graph, verbose=True)
        _sep()
        print(f"  Final Score : {result.composite_score:.4f}  |  Grade: {result.grade}")
        print(f"  Final Loss  : {result.composite_loss:.4f}")
        print(f"  Final power : {graph.total_power():.1f} mW")
        print(f"  Final area  : {graph.total_area():.3f} mm²")
        print(f"  Final IPs   : {len(graph.ip_blocks)}")
        print("  Remaining violations:")
        if result.violations:
            for v in result.violations:
                print(f"    ✗ {v}")
        else:
            print("    ✓ None")

        # Store optimized design in KB
        kb.add_design(graph, result)
        print("  ✓ Design stored in knowledge base")
    else:
        print("\n[5/6] Optimization skipped (use --optimize flag)")

    # 6. IP design briefs
    if show_briefs:
        print("\n[6/6] Generating IP Design Briefs...")
        propagator = ArchitecturePropagator()
        briefs = propagator.propagate(graph)
        print(f"  Generated {len(briefs)} IP briefs")
        print("\n" + "═" * 68)
        # Print first 2 briefs as example
        for i, (ip_id, brief) in enumerate(briefs.items()):
            if i < 2:
                print(brief.render_text())
        if len(briefs) > 2:
            print(f"  ... ({len(briefs) - 2} more IP briefs generated)")
            print("  Run with --brief flag and a specific IP to see all briefs")
    else:
        print("\n[6/6] IP briefs skipped (use --brief flag)")

    print("\n" + "═" * 68)
    print("  ARCHITECTURE EVALUATION COMPLETE")
    print("═" * 68 + "\n")
    return graph, result


def main():
    parser = argparse.ArgumentParser(
        description="IC Architecture Automation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python arch_tool.py --example iot
  python arch_tool.py --example mcu --optimize
  python arch_tool.py --example radar --full
  python arch_tool.py --spec my_custom_spec.json --full
        """
    )
    parser.add_argument("--example", choices=["iot", "mcu", "radar", "smartphone"],
                        help="Run with a built-in example spec")
    parser.add_argument("--spec", type=str, help="Path to custom JSON spec file")
    parser.add_argument("--optimize", action="store_true",
                        help="Run iterative optimization loop")
    parser.add_argument("--brief", action="store_true",
                        help="Generate and print IP design briefs")
    parser.add_argument("--full", action="store_true",
                        help="Run full flow: build + evaluate + optimize + briefs")

    args = parser.parse_args()

    if not (args.example or args.spec):
        parser.print_help()
        sys.exit(0)

    if args.spec:
        with open(args.spec) as f:
            spec_dict = json.load(f)
    else:
        spec_dict = EXAMPLES[args.example]

    optimize = args.optimize or args.full
    show_briefs = args.brief or args.full

    run_full_flow(spec_dict, optimize=optimize, show_briefs=show_briefs)


if __name__ == "__main__":
    main()
