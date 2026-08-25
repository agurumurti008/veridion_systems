"""
Test Suite — IC Architecture Automation Tool
=============================================
Validates all major flows: build, evaluate, optimize, propagate, ML.
Run: python tests/test_all.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.arch_engine import parse_spec_from_dict, ArchitectureBuilder, ArchitectureGraph
from core.evaluator import ArchitectureEvaluator, ArchitectureOptimizer, EvalWeights
from core.ml_engine import ArchKnowledgeBase, GNNArchAdvisor, GraphEncoder
from core.propagator import ArchitecturePropagator


def section(title: str):
    print(f"\n{'═'*60}")
    print(f"  TEST: {title}")
    print(f"{'═'*60}")


def check(cond: bool, msg: str):
    status = "✓" if cond else "✗ FAIL"
    print(f"  [{status}] {msg}")
    if not cond:
        raise AssertionError(msg)


# ─── Test 1: IoT Sensor Architecture ─────────────────────────────────────────

def test_iot_sensor():
    section("IoT Sensor — Build & Evaluate")
    spec_dict = {
        "app_domain": "iot_sensor",
        "power_budget": 5.0,
        "area_budget": 4.0,
        "target_frequency": 48.0,
        "interface_standards": ["I2C", "SPI"],
    }
    spec = parse_spec_from_dict(spec_dict)
    check(spec.app_domain == "iot_sensor", "Domain parsed correctly")
    check(spec.power_budget == 5.0, "Power budget set")

    builder = ArchitectureBuilder()
    graph = builder.build(spec)
    check(len(graph.ip_blocks) > 5, f"Enough IPs built ({len(graph.ip_blocks)})")
    check("pmu" in graph.ip_blocks, "PMU present")
    check("pll" in graph.ip_blocks, "PLL present")
    check("adc_12b" in graph.ip_blocks, "ADC present for sensing domain")
    check(graph.total_power() > 0, "Non-zero power")
    check(graph.total_area() > 0, "Non-zero area")

    evaluator = ArchitectureEvaluator()
    result = evaluator.evaluate(graph)
    check(0.0 <= result.composite_score <= 1.0, f"Score in valid range: {result.composite_score:.4f}")
    check(result.grade in ["A+","A","A-","B+","B","B-","C+","C","C-","D","F"],
          f"Valid grade: {result.grade}")
    check(isinstance(result.suggestions, list), "Suggestions returned")
    print(f"  IoT Score: {result.composite_score:.4f}  Grade: {result.grade}")
    print(f"  Power: {graph.total_power():.1f}mW / {spec.power_budget}mW budget")
    return graph, result


# ─── Test 2: Industrial MCU ───────────────────────────────────────────────────

def test_industrial_mcu():
    section("Industrial MCU — Build, Evaluate, Optimize")
    spec_dict = {
        "app_domain": "industrial_mcu",
        "power_budget": 150.0,
        "area_budget": 25.0,
        "target_frequency": 200.0,
        "interface_standards": ["CAN", "Ethernet", "UART"],
        "reliability_targets": {"mtbf_hours": 100000},
    }
    spec = parse_spec_from_dict(spec_dict)
    builder = ArchitectureBuilder()
    graph = builder.build(spec)

    check("can_ctrl" in graph.ip_blocks, "CAN controller present")
    check("eth_mac" in graph.ip_blocks, "Ethernet MAC present")

    evaluator = ArchitectureEvaluator()
    initial_result = evaluator.evaluate(graph)

    # Optimize
    optimizer = ArchitectureOptimizer(evaluator, max_iterations=10)
    opt_graph, opt_result, history = optimizer.optimize(graph, verbose=False)

    check(len(history) > 1, f"Optimization ran for {len(history)} iterations")
    check(opt_result.composite_loss <= initial_result.composite_loss + 0.01,
          f"Score didn't degrade: {initial_result.composite_score:.3f} → {opt_result.composite_score:.3f}")
    print(f"  MCU Score: {initial_result.composite_score:.4f} → {opt_result.composite_score:.4f}")
    print(f"  Grade: {initial_result.grade} → {opt_result.grade}")
    return opt_graph, opt_result


# ─── Test 3: Radar Chip ───────────────────────────────────────────────────────

def test_radar_chip():
    section("Radar Chip — Analog + Mixed-Signal Validation")
    spec_dict = {
        "app_domain": "radar_chip",
        "power_budget": 2000.0,
        "area_budget": 50.0,
        "target_frequency": 1000.0,
        "interface_standards": ["Ethernet"],
    }
    spec = parse_spec_from_dict(spec_dict)
    builder = ArchitectureBuilder()
    graph = builder.build(spec)

    check("radar_fend" in graph.ip_blocks, "Radar RF frontend present")
    check("dsp_core" in graph.ip_blocks, "DSP core present for radar processing")

    evaluator = ArchitectureEvaluator()
    result = evaluator.evaluate(graph)
    check("analog_isolation" in result.losses, "Analog isolation metric computed")
    check("cdc" in result.losses, "CDC metric computed")
    print(f"  Radar Score: {result.composite_score:.4f}  Grade: {result.grade}")
    print(f"  Analog isolation loss: {result.losses['analog_isolation']:.4f}")
    print(f"  CDC loss: {result.losses['cdc']:.4f}")
    return graph, result


# ─── Test 4: Graph Representation ────────────────────────────────────────────

def test_graph_representation():
    section("Graph → Mathematical Representation (Adjacency + Feature Matrices)")
    spec = parse_spec_from_dict({"app_domain": "industrial_mcu"})
    graph = ArchitectureBuilder().build(spec)

    A = graph.adjacency_matrix()
    X = graph.node_feature_matrix()
    E = graph.edge_feature_list()

    n = len(graph.ip_blocks)
    check(len(A) == n, f"Adjacency matrix is {n}x{n}")
    check(all(len(row) == n for row in A), "Adjacency matrix is square")
    check(len(X) == n, f"Node feature matrix has {n} rows")
    check(len(X[0]) == 9, f"Each node has 9 features (got {len(X[0])})")
    check(len(E) > 0, f"Edge feature list has {len(E)} entries")
    print(f"  Graph: {n} nodes, {len(E)} edges")
    print(f"  Adjacency matrix sample (first 3×3):")
    for row in A[:3]:
        print(f"    {[round(v,2) for v in row[:3]]}")


# ─── Test 5: ML Engine ────────────────────────────────────────────────────────

def test_ml_engine():
    section("GNN Encoder + Knowledge Base + Advisor")
    spec = parse_spec_from_dict({"app_domain": "iot_sensor", "power_budget": 5.0})
    graph = ArchitectureBuilder().build(spec)

    encoder = GraphEncoder(seed=42)
    embed = encoder.encode(graph)
    check(len(embed) == 13, f"Embedding dim correct: {len(embed)}")
    check(all(isinstance(v, float) for v in embed), "Embedding is float vector")

    kb = ArchKnowledgeBase()
    similar = kb.find_similar(graph, top_k=3)
    check(len(similar) == 3, f"Found {len(similar)} similar designs")
    check(all(0.0 <= sim <= 1.0 for sim, _ in similar), "Similarity scores in [0,1]")

    learnings = kb.extract_learnings("iot_sensor")
    check("avg_score" in learnings, "Learnings extracted")

    advisor = GNNArchAdvisor(kb)
    quick = advisor.quick_score(graph)
    check(0.0 <= quick <= 1.0, f"Quick score valid: {quick:.4f}")

    recs = advisor.recommend_ips(graph)
    check(isinstance(recs, list), "IP recommendations returned")
    print(f"  Embedding: {[round(v,3) for v in embed[:5]]}...")
    print(f"  Quick score: {quick:.4f}")
    print(f"  Top similar: {[d.design_id for _, d in similar]}")
    print(f"  Recommendations: {[r[0] for r in recs]}")
    print(f"  Learnings: {learnings}")


# ─── Test 6: IP Design Brief Propagation ────────────────────────────────────

def test_propagation():
    section("Architecture Philosophy Propagation → IP Briefs")
    spec = parse_spec_from_dict({"app_domain": "industrial_mcu", "power_budget": 150.0})
    graph = ArchitectureBuilder().build(spec)
    propagator = ArchitecturePropagator()
    briefs = propagator.propagate(graph)

    check(len(briefs) == len(graph.ip_blocks), "Brief count matches IP count")
    for ip_id, brief in briefs.items():
        check(brief.ip_id == ip_id, f"Brief ID matches for {ip_id}")
        check(len(brief.functional_objectives) > 0, f"{ip_id} has functional objectives")
        check(len(brief.coverage_goals) > 0, f"{ip_id} has verification goals")
        check(brief.arch_intent != "", f"{ip_id} has arch intent")

    # Show one brief
    first_brief = list(briefs.values())[0]
    print(f"\n  Sample brief for: {first_brief.ip_name}")
    print(f"  Objectives: {first_brief.functional_objectives[:2]}")
    print(f"  Drives → {first_brief.drives}")
    print(f"  Driven by ← {first_brief.driven_by}")


# ─── Test 7: Custom Spec JSON ─────────────────────────────────────────────────

def test_custom_spec():
    section("Custom Specification — Wearable Health Monitor")
    custom_spec = {
        "app_domain": "iot_sensor",
        "process_node": "28nm",
        "supply_voltage": 1.5,
        "target_frequency": 32.0,
        "power_budget": 3.0,
        "area_budget": 3.5,
        "interface_standards": ["I2C", "SPI", "UART"],
        "performance_targets": {
            "adc_resolution": 16,
            "sleep_current_ua": 0.5,
            "heart_rate_accuracy_bpm": 1,
        },
        "reliability_targets": {"water_resistance_ip": "IP68"},
        "operating_temp_range": [-10, 55],
    }
    spec = parse_spec_from_dict(custom_spec)
    graph = ArchitectureBuilder().build(spec)
    evaluator = ArchitectureEvaluator()
    result = evaluator.evaluate(graph)
    check(spec.process_node == "28nm", "Custom process node preserved")
    check(spec.operating_temp_range == (-10, 55), "Custom temp range preserved")
    check(0 <= result.composite_score <= 1, "Score valid for custom spec")
    print(f"  Wearable Score: {result.composite_score:.4f}  Grade: {result.grade}")
    print(f"  Suggestions: {result.suggestions[0]}")


# ─── Test 8: Loss Function Sensitivity ────────────────────────────────────────

def test_loss_sensitivity():
    section("Loss Function Sensitivity — Over-budget Architecture")
    spec_dict = {
        "app_domain": "iot_sensor",
        "power_budget": 1.0,   # Very tight budget
        "area_budget": 0.5,
        "target_frequency": 48.0,
    }
    spec = parse_spec_from_dict(spec_dict)
    graph = ArchitectureBuilder().build(spec)
    evaluator = ArchitectureEvaluator()
    result = evaluator.evaluate(graph)

    # Power loss should be > 1 (over budget)
    check(result.losses["power"] > 1.0,
          f"Power loss > 1 when over budget: {result.losses['power']:.3f}")
    check(result.losses["area"] > 1.0,
          f"Area loss > 1 when over budget: {result.losses['area']:.3f}")
    check(result.composite_score < 0.6,
          f"Composite score is low when constraints violated: {result.composite_score:.3f}")
    # Check violations are reported
    check(any("BUDGET" in v for v in result.violations), "Budget violations detected")
    print(f"  Power loss (over budget): {result.losses['power']:.3f}")
    print(f"  Area loss (over budget): {result.losses['area']:.3f}")
    print(f"  Violations: {result.violations}")


# ─── Run all ──────────────────────────────────────────────────────────────────

def main():
    print("\n" + "█" * 60)
    print("  IC ARCHITECTURE TOOL — TEST SUITE")
    print("█" * 60)

    tests = [
        ("IoT Sensor",           test_iot_sensor),
        ("Industrial MCU",       test_industrial_mcu),
        ("Radar Chip",           test_radar_chip),
        ("Graph Representation", test_graph_representation),
        ("ML Engine",            test_ml_engine),
        ("IP Propagation",       test_propagation),
        ("Custom Spec",          test_custom_spec),
        ("Loss Sensitivity",     test_loss_sensitivity),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"\n  ✓ PASSED: {name}")
            passed += 1
        except Exception as e:
            print(f"\n  ✗ FAILED: {name} — {e}")
            failed += 1

    print("\n" + "═" * 60)
    print(f"  Results: {passed}/{passed+failed} tests passed")
    if failed == 0:
        print("  ✓ ALL TESTS PASSED")
    else:
        print(f"  ✗ {failed} FAILURES")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
