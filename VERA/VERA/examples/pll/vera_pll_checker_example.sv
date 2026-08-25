// ============================================================================
// VERA — Verification Engine for Runtime & Autonomous Checking
// FILE: examples/pll/vera_pll_checker_example.sv
// DESC: Complete PLL checker combining SVA (lock detection, output stability),
//       UVM scoreboard (divider output vs expected), VERA parametric checker,
//       and post-sim Python hooks for jitter/phase noise analysis.
// VERSION: 1.0
// ============================================================================

`include "vera_sva_library.sv"
`include "vera_scoreboard_base.sv"

// ============================================================================
// PLL SVA Checker Module
// ============================================================================
module vera_pll_sva_checker #(
  parameter string IP_NAME        = "PLL_1G",
  parameter int    N_DIV          = 20,        // reference divider
  parameter int    M_DIV          = 400,       // feedback divider for 1GHz from 50MHz ref
  parameter int    LOCK_TIMEOUT   = 100_000,   // max cycles to achieve lock
  parameter int    LOCK_HOLD_MIN  = 1000,      // min cycles to sustain lock
  parameter int    UNLOCK_GLITCH  = 10         // max unlock glitch width (cycles) — allowed
)(
  input logic pll_clkref,     // reference clock
  input logic pll_clkout,     // VCO output
  input logic pll_locked,     // lock indicator
  input logic pll_en,         // PLL enable
  input logic rst_n
);

  // PLL.1: Lock must be achieved within LOCK_TIMEOUT after enable
  property p_lock_time;
    @(posedge pll_clkref) disable iff (!rst_n)
    $rose(pll_en) |-> ##[1:LOCK_TIMEOUT] $rose(pll_locked);
  endproperty
  VERA_PLL_LOCK_TIME:
    assert property (p_lock_time)
    else $error("VERA_FAIL | IP=%s | CHECK=PLL_LOCK_TIME | lock not achieved within %0d ref cycles | @%0t",
                IP_NAME, LOCK_TIMEOUT, $time);

  // PLL.2: Once locked, lock must hold for minimum time
  property p_lock_stability;
    @(posedge pll_clkref) disable iff (!rst_n)
    $rose(pll_locked) |-> pll_locked[*LOCK_HOLD_MIN];
  endproperty
  VERA_PLL_LOCK_STABILITY:
    assert property (p_lock_stability)
    else $error("VERA_FAIL | IP=%s | CHECK=PLL_LOCK_STABILITY | lock dropped within %0d ref cycles | @%0t",
                IP_NAME, LOCK_HOLD_MIN, $time);

  // PLL.3: PLL disabled must de-assert lock within reasonable time
  property p_lock_clear_on_disable;
    @(posedge pll_clkref) disable iff (!rst_n)
    $fell(pll_en) |-> ##[1:100] !pll_locked;
  endproperty
  VERA_PLL_LOCK_CLEAR:
    assert property (p_lock_clear_on_disable)
    else $error("VERA_FAIL | IP=%s | CHECK=PLL_LOCK_CLEAR | lock still asserted after PLL disable | @%0t",
                IP_NAME, $time);

  // PLL.4: CLKOUT must toggle when locked (simplified: check transitions exist)
  property p_clkout_toggling;
    @(posedge pll_clkref) disable iff (!rst_n)
    (pll_locked) |-> ##[1:N_DIV] $rose(pll_clkout);
  endproperty
  VERA_PLL_CLKOUT_TOGGLE:
    assert property (p_clkout_toggling)
    else $error("VERA_FAIL | IP=%s | CHECK=PLL_CLKOUT_TOGGLE | clkout not toggling while locked | @%0t",
                IP_NAME, $time);

  // PLL.5: Reset must de-assert lock
  property p_rst_de_asserts_lock;
    @(posedge pll_clkref)
    !rst_n |-> !pll_locked;
  endproperty
  VERA_PLL_RST_LOCK:
    assert property (p_rst_de_asserts_lock)
    else $error("VERA_FAIL | IP=%s | CHECK=PLL_RST_LOCK | pll_locked asserted during reset | @%0t",
                IP_NAME, $time);

  // PLL.6: Lock must not assert before enable
  property p_lock_after_enable;
    @(posedge pll_clkref) disable iff (!rst_n)
    !pll_en |-> !pll_locked;
  endproperty
  VERA_PLL_LOCK_AFTER_EN:
    assert property (p_lock_after_enable)
    else $error("VERA_FAIL | IP=%s | CHECK=PLL_LOCK_AFTER_EN | lock asserted while PLL disabled | @%0t",
                IP_NAME, $time);

  // Coverage
  covergroup cg_pll @(posedge pll_clkref);
    cp_locked:  coverpoint pll_locked;
    cp_en:      coverpoint pll_en;
    cx_en_lock: cross cp_locked, cp_en;
    cp_lock_seq: coverpoint {$rose(pll_locked), $fell(pll_locked)} {
      bins acquired  = {2'b10};
      bins lost      = {2'b01};
    }
  endgroup
  cg_pll cg_pll_inst = new();

endmodule

// ============================================================================
// PLL Divider Scoreboard — verifies output frequency matches divider config
// ============================================================================
class pll_div_item extends uvm_sequence_item;
  `uvm_object_utils_begin(pll_div_item)
    `uvm_field_int(div_n, UVM_ALL_ON)
    `uvm_field_int(div_m, UVM_ALL_ON)
    `uvm_field_real(fref_hz, UVM_ALL_ON)
    `uvm_field_real(fout_measured_hz, UVM_ALL_ON)
  `uvm_object_utils_end

  int  div_n;           // reference divider
  int  div_m;           // feedback divider
  real fref_hz;         // reference frequency
  real fout_measured_hz; // measured output frequency

  function new(string name = "pll_div_item");
    super.new(name);
  endfunction

  function string convert2string();
    return $sformatf("N=%0d M=%0d fref=%.3fMHz fout_meas=%.3fMHz fout_exp=%.3fMHz",
                     div_n, div_m, fref_hz/1e6,
                     fout_measured_hz/1e6,
                     (fref_hz * div_m / div_n)/1e6);
  endfunction
endclass

class vera_pll_div_scoreboard extends vera_scoreboard_base #(
  .T_EXP(pll_div_item),
  .T_ACT(pll_div_item)
);
  `uvm_component_utils(vera_pll_div_scoreboard)

  real m_tol_ppm = 100.0;  // ±100 ppm frequency tolerance

  function new(string name, uvm_component parent);
    super.new(name, parent);
    m_ip_name      = "PLL_1G";
    m_checker_name = "vera_pll_freq_accuracy_sb";
    m_layer        = "parametric";
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    void'(uvm_config_db #(real)::get(this, "", "tol_ppm", m_tol_ppm));
  endfunction

  virtual function bit compare_items(pll_div_item exp_item, pll_div_item act_item);
    real fout_expected, error_ppm;
    fout_expected = exp_item.fref_hz * exp_item.div_m / exp_item.div_n;
    error_ppm     = $abs(act_item.fout_measured_hz - fout_expected) / fout_expected * 1.0e6;
    return (error_ppm <= m_tol_ppm);
  endfunction

  virtual function string get_context(pll_div_item exp_item, pll_div_item act_item);
    real fout_expected = exp_item.fref_hz * exp_item.div_m / exp_item.div_n;
    real error_ppm = $abs(act_item.fout_measured_hz - fout_expected) / fout_expected * 1.0e6;
    return $sformatf("N=%0d M=%0d err=%.1fppm tol=%.0fppm",
                     exp_item.div_n, exp_item.div_m, error_ppm, m_tol_ppm);
  endfunction

  virtual function string get_debug_signal(pll_div_item exp_item);
    return "/tb/dut/pll_clkout";
  endfunction

  virtual function string get_recommendation(pll_div_item exp_item, pll_div_item act_item);
    return "Check PLL divider configuration, VCO calibration, or reference frequency accuracy";
  endfunction

endclass

// ============================================================================
// PLL Full Environment
// ============================================================================
class vera_pll_env extends uvm_env;
  `uvm_component_utils(vera_pll_env)

  vera_pll_div_scoreboard   m_div_sb;
  vera_param_checker_component m_param_chk;
  vera_report_collector     m_collector;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_div_sb    = vera_pll_div_scoreboard::type_id::create("m_div_sb",   this);
    m_param_chk = vera_param_checker_component::type_id::create("m_param_chk", this);
    m_collector = vera_report_collector::get();

    uvm_config_db #(string)::set(this, "*", "ip_name", "PLL_1G");
    uvm_config_db #(string)::set(null, "vera_report_collector",
                                 "report_file", "vera_pll_report.json");
  endfunction

  // Convenience: check VCO control voltage at lock
  function void check_vctrl(real vctrl_v, real vctrl_min, real vctrl_max);
    void'(m_param_chk.check_real("vera_pll_vctrl", vctrl_v, vctrl_min, vctrl_max, "V",
      "/tb/dut/vctrl", "VCO control voltage at lock",
      "If out of range, VCO is operating at gain limit — check loop filter or VCO tuning range"));
  endfunction

  // Check lock time (call with measured lock time in ns)
  function void check_lock_time(real lock_time_ns, real max_lock_ns);
    void'(m_param_chk.check_real("vera_pll_lock_time_ns", lock_time_ns, 0.0, max_lock_ns, "ns",
      "/tb/dut/pll_locked", "lock acquisition time",
      "Check loop filter bandwidth, charge pump current, or VCO gain"));
  endfunction

endclass
