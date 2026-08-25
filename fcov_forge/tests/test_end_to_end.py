"""
fcov_forge/tests/test_end_to_end.py
=====================================
End-to-end tests for FCovForge.
Run with: python -m pytest tests/ -v
"""

import sys
import os
import textwrap
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from pathlib import Path

from core.model import (
    FeatureModel, Feature, CoverGroup, CoverPoint, CoverBin,
    FeatureCross, FeatureCrossTarget, BinType
)
from parsers.yaml_parser import parse_yaml, parse_yaml_string
from core.cross_engine import CrossEngine
from generators.sv_generator import feature_to_sv, crosses_to_sv, generate_all


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_YAML = textwrap.dedent("""
project: test_chip

features:
  - name: uart_tx
    description: UART transmit feature
    covergroups:
      - name: baud_rate_cg
        clock: "posedge clk"
        coverpoints:
          - name: baud_cp
            variable: baud_rate
            bins:
              - name: BIN_9600
                values: [9600]
              - name: BIN_115200
                values: [115200]
              - name: BIN_1M
                values: [1000000]

  - name: spi_master
    description: SPI master feature
    covergroups:
      - name: spi_mode_cg
        clock: "posedge clk"
        coverpoints:
          - name: mode_cp
            variable: spi_mode
            bins:
              - name: BIN_MODE0
                values: [0]
              - name: BIN_MODE1
                values: [1]
              - name: BIN_MODE2
                values: [2]
              - name: BIN_MODE3
                values: [3]

feature_crosses:
  - name: uart_x_spi
    targets:
      - uart_tx.baud_rate_cg.baud_cp
      - spi_master.spi_mode_cg.mode_cp
    comment: "UART baud rate vs SPI mode"
    goal: 100
""")


@pytest.fixture
def simple_model():
    return parse_yaml_string(SIMPLE_YAML)


@pytest.fixture
def full_model():
    yaml_path = Path(__file__).parent.parent / "examples" / "dma_interrupt_power.yaml"
    if yaml_path.exists():
        return parse_yaml(yaml_path)
    return parse_yaml_string(SIMPLE_YAML)


# ---------------------------------------------------------------------------
# Test: Model parsing
# ---------------------------------------------------------------------------

class TestYAMLParsing:
    def test_project_name(self, simple_model):
        assert simple_model.project_name == "test_chip"

    def test_feature_count(self, simple_model):
        assert len(simple_model.features) == 2

    def test_feature_names(self, simple_model):
        names = {f.name for f in simple_model.features}
        assert "uart_tx" in names
        assert "spi_master" in names

    def test_covergroup_count(self, simple_model):
        feat = simple_model.get_feature("uart_tx")
        assert feat is not None
        assert len(feat.covergroups) == 1

    def test_coverpoint_bins(self, simple_model):
        feat = simple_model.get_feature("uart_tx")
        cg = feat.get_covergroup("baud_rate_cg")
        assert cg is not None
        cp = cg.get_coverpoint("baud_cp")
        assert cp is not None
        assert len(cp.bins) == 3
        assert cp.bins[0].name == "BIN_9600"
        assert cp.bins[0].values == [9600]

    def test_feature_cross_parsed(self, simple_model):
        assert len(simple_model.feature_crosses) == 1
        fc = simple_model.feature_crosses[0]
        assert fc.name == "uart_x_spi"
        assert len(fc.targets) == 2

    def test_all_bin_types(self):
        yaml_str = textwrap.dedent("""
        project: bin_test
        features:
          - name: test_feat
            covergroups:
              - name: test_cg
                coverpoints:
                  - name: cp
                    variable: sig
                    bins:
                      - name: B_VALUES
                        values: [1, 2]
                      - name: B_RANGE
                        ranges: [[0, 15]]
                      - name: B_TRANS
                        type: transition
                        transitions: [[A, B, C]]
                      - name: B_WILD
                        type: wildcard
                        pattern: "8'b1???????"
                      - name: B_AUTO
                        type: auto
                        auto_bin_max: 8
                      - name: B_DEFAULT
                        type: default
                      - name: B_IGNORE
                        type: ignore
                        values: [255]
                      - name: B_ILLEGAL
                        type: illegal
                        ranges: [[256, 511]]
        """)
        model = parse_yaml_string(yaml_str)
        cp = model.features[0].covergroups[0].coverpoints[0]
        types = {b.name: b.bin_type for b in cp.bins}
        assert types["B_VALUES"] == BinType.VALUES
        assert types["B_RANGE"] == BinType.RANGE
        assert types["B_TRANS"] == BinType.TRANSITION
        assert types["B_WILD"] == BinType.WILDCARD
        assert types["B_AUTO"] == BinType.AUTO
        assert types["B_DEFAULT"] == BinType.DEFAULT
        assert types["B_IGNORE"] == BinType.IGNORE
        assert types["B_ILLEGAL"] == BinType.ILLEGAL


# ---------------------------------------------------------------------------
# Test: Address resolution
# ---------------------------------------------------------------------------

class TestAddressResolution:
    def test_feature_resolution(self, simple_model):
        feat = simple_model.resolve_address("uart_tx")
        assert feat.name == "uart_tx"

    def test_covergroup_resolution(self, simple_model):
        cg = simple_model.resolve_address("uart_tx.baud_rate_cg")
        assert cg.name == "baud_rate_cg"

    def test_coverpoint_resolution(self, simple_model):
        cp = simple_model.resolve_address("uart_tx.baud_rate_cg.baud_cp")
        assert cp.name == "baud_cp"

    def test_bin_resolution(self, simple_model):
        b = simple_model.resolve_address("uart_tx.baud_rate_cg.baud_cp.BIN_9600")
        assert b.name == "BIN_9600"

    def test_bad_feature_raises(self, simple_model):
        with pytest.raises(ValueError, match="Feature"):
            simple_model.resolve_address("nonexistent_feature")

    def test_bad_cg_raises(self, simple_model):
        with pytest.raises(ValueError, match="CoverGroup"):
            simple_model.resolve_address("uart_tx.nonexistent_cg")


# ---------------------------------------------------------------------------
# Test: Cross Engine
# ---------------------------------------------------------------------------

class TestCrossEngine:
    def test_validate_ok(self, simple_model):
        engine = CrossEngine(simple_model)
        errors = engine.validate()
        assert errors == []

    def test_validate_bad_target(self, simple_model):
        from core.model import FeatureCross, FeatureCrossTarget
        bad_fc = FeatureCross(
            name="bad_cross",
            targets=[
                FeatureCrossTarget("uart_tx.baud_rate_cg.baud_cp"),
                FeatureCrossTarget("nonexistent_feature"),
            ]
        )
        simple_model.feature_crosses.append(bad_fc)
        engine = CrossEngine(simple_model)
        errors = engine.validate()
        assert len(errors) > 0
        assert "nonexistent_feature" in errors[0]

    def test_synthesize_cross(self, simple_model):
        engine = CrossEngine(simple_model)
        crosses = engine.synthesize_all()
        assert len(crosses) == 1
        sc = crosses[0]
        assert sc.cross_def.name == "uart_x_spi"
        assert len(sc.resolved_targets) == 2

    def test_synthesized_sv_contains_cross(self, simple_model):
        engine = CrossEngine(simple_model)
        crosses = engine.synthesize_all()
        sv = crosses[0].to_sv()
        assert "covergroup" in sv
        assert "cross" in sv
        assert "uart_x_spi" in sv

    def test_feature_level_resolution(self, simple_model):
        """Test that a feature-level target expands to all CPs."""
        from core.model import FeatureCross, FeatureCrossTarget
        fc = FeatureCross(
            name="feat_level_cross",
            targets=[
                FeatureCrossTarget("uart_tx"),
                FeatureCrossTarget("spi_master"),
            ]
        )
        engine = CrossEngine(simple_model)
        sc = engine.synthesize_cross(fc)
        for rt in sc.resolved_targets:
            assert len(rt.coverpoints) > 0

    def test_cg_level_resolution(self, simple_model):
        """Test that a CG-level target expands to all its CPs."""
        from core.model import FeatureCross, FeatureCrossTarget
        fc = FeatureCross(
            name="cg_level_cross",
            targets=[
                FeatureCrossTarget("uart_tx.baud_rate_cg"),
                FeatureCrossTarget("spi_master.spi_mode_cg"),
            ]
        )
        engine = CrossEngine(simple_model)
        sc = engine.synthesize_cross(fc)
        assert all(len(rt.coverpoints) > 0 for rt in sc.resolved_targets)


# ---------------------------------------------------------------------------
# Test: SV Generation
# ---------------------------------------------------------------------------

class TestSVGeneration:
    def test_feature_sv_has_covergroup(self, simple_model):
        feat = simple_model.get_feature("uart_tx")
        sv = feature_to_sv(feat, "test_chip")
        assert "covergroup baud_rate_cg" in sv
        assert "endgroup" in sv

    def test_feature_sv_has_coverpoints(self, simple_model):
        feat = simple_model.get_feature("uart_tx")
        sv = feature_to_sv(feat, "test_chip")
        assert "baud_cp" in sv
        assert "baud_rate" in sv

    def test_feature_sv_has_bins(self, simple_model):
        feat = simple_model.get_feature("uart_tx")
        sv = feature_to_sv(feat, "test_chip")
        assert "BIN_9600" in sv
        assert "9600" in sv

    def test_cross_sv_generation(self, simple_model):
        engine = CrossEngine(simple_model)
        crosses = engine.synthesize_all()
        sv = crosses_to_sv(crosses, "test_chip")
        assert "fcov_cross_uart_x_spi_cg" in sv
        assert "covergroup" in sv

    def test_generate_all_creates_files(self, simple_model, tmp_path):
        generated = generate_all(simple_model, tmp_path)
        assert len(generated) >= 3  # at least features + crosses + package
        for path in generated.values():
            assert path.exists()
            assert path.stat().st_size > 0

    def test_sv_bin_types(self):
        """Test SV rendering for each bin type."""
        yaml_str = textwrap.dedent("""
        project: sv_test
        features:
          - name: all_bins
            covergroups:
              - name: test_cg
                coverpoints:
                  - name: cp
                    variable: x
                    bins:
                      - name: B1
                        values: [1, 2, 3]
                      - name: B2
                        ranges: [[0, 15]]
                      - name: B3
                        type: transition
                        transitions: [[A, B], [C, D, E]]
                      - name: B4
                        type: wildcard
                        pattern: "4'b1?0?"
                      - name: B5
                        type: default
                      - name: B6
                        type: ignore
                        values: [99]
                      - name: B7
                        type: illegal
                        ranges: [[100, 200]]
        """)
        model = parse_yaml_string(yaml_str)
        feat = model.get_feature("all_bins")
        sv = feature_to_sv(feat, "sv_test")

        assert "bins B1 = {1, 2, 3}" in sv
        assert "[0:15]" in sv
        assert "ignore_bins B6" in sv
        assert "illegal_bins B7" in sv
        assert "wildcard bins B4" in sv
        assert "bins B5 = default" in sv


# ---------------------------------------------------------------------------
# Test: Full example file
# ---------------------------------------------------------------------------

class TestFullExample:
    def test_full_yaml_parses(self, full_model):
        assert len(full_model.features) >= 2

    def test_full_yaml_crosses(self, full_model):
        if full_model.project_name == "example_soc":
            assert len(full_model.feature_crosses) >= 3

    def test_three_way_cross(self, full_model):
        if full_model.project_name != "example_soc":
            pytest.skip("Full example not available")
        three_way = next(
            (fc for fc in full_model.feature_crosses if len(fc.targets) >= 3), None
        )
        assert three_way is not None, "Expected a 3-way cross"
        engine = CrossEngine(full_model)
        sc = engine.synthesize_cross(three_way)
        sv = sc.to_sv()
        assert "cross" in sv


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
