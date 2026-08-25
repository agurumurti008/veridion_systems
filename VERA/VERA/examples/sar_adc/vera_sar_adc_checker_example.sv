// ============================================================================
// VERA — Verification Engine for Runtime & Autonomous Checking
// FILE: examples/sar_adc/vera_sar_adc_checker_example.sv
// DESC: Full end-to-end VERA checker example for a 12-bit SAR ADC.
//       Shows how to combine:
//       1. SVA for digital interface (EOC, data valid timing)
//       2. UVM Transform Scoreboard (analog in → digital code)
//       3. VERA parametric checker (supply, reference)
//       4. Post-sim Python hooks (FFT, DNL/INL)
// VERSION: 1.0
// ============================================================================

`include "vera_sva_library.sv"
`include "vera_scoreboard_base.sv"
`include "vera_predictor_base.sv"

// ============================================================================
// SAR ADC Transaction Items
// ============================================================================
class sar_adc_input_item extends uvm_sequence_item;
  `uvm_object_utils_begin(sar_adc_input_item)
    `uvm_field_real(vin_v,   UVM_ALL_ON)
    `uvm_field_real(vref_v,  UVM_ALL_ON)
    `uvm_field_real(time_ns, UVM_ALL_ON)
  `uvm_object_utils_end

  real vin_v;
  real vref_v;
  real time_ns;

  function new(string name = "sar_adc_input_item");
    super.new(name);
  endfunction

  function string convert2string();
    return $sformatf("Vin=%.6fV Vref=%.3fV t=%.1fns", vin_v, vref_v, time_ns);
  endfunction
endclass

class sar_adc_output_item extends uvm_sequence_item;
  `uvm_object_utils_begin(sar_adc_output_item)
    `uvm_field_int(code,    UVM_ALL_ON)
    `uvm_field_int(eoc,     UVM_ALL_ON)
    `uvm_field_real(time_ns, UVM_ALL_ON)
  `uvm_object_utils_end

  logic [11:0] code;
  logic        eoc;
  real         time_ns;

  function new(string name = "sar_adc_output_item");
    super.new(name);
  endfunction

  function string convert2string();
    return $sformatf("code=0x%03h (%0d) eoc=%0b t=%.1fns", code, code, eoc, time_ns);
  endfunction
endclass

// ============================================================================
// SAR ADC SVA Checker Module (bind to DUT)
// ============================================================================
module vera_sar_adc_sva_checker #(
  parameter string IP_NAME   = "SAR_ADC_12B",
  parameter int    N_BITS    = 12,
  parameter int    MAX_CONV  = 16,   // max conversion clock cycles
  parameter int    MIN_CONV  = 10    // min conversion clock cycles
)(
  input logic        sclk,
  input logic        rst_n,
  input logic        soc,          // start of conversion
  input logic        eoc,          // end of conversion
  input logic [11:0] data_out,
  input logic        data_valid
);

  // SVA.1: EOC must come within conversion window
  property p_eoc_timing;
    @(posedge sclk) disable iff (!rst_n)
    $rose(soc) |-> ##[MIN_CONV:MAX_CONV] $rose(eoc);
  endproperty
  VERA_SAR_EOC_TIMING:
    assert property (p_eoc_timing)
    else $error("VERA_FAIL | IP=%s | CHECK=SAR_EOC_TIMING | EOC not seen in [%0d:%0d] cycles after SOC | @%0t",
                IP_NAME, MIN_CONV, MAX_CONV, $time);

  // SVA.2: DATA_VALID must come within 2 cycles of EOC
  property p_data_valid_after_eoc;
    @(posedge sclk) disable iff (!rst_n)
    $rose(eoc) |-> ##[0:2] data_valid;
  endproperty
  VERA_SAR_DATA_VALID:
    assert property (p_data_valid_after_eoc)
    else $error("VERA_FAIL | IP=%s | CHECK=SAR_DATA_VALID | data_valid not seen within 2 cycles of EOC | @%0t",
                IP_NAME, $time);

  // SVA.3: DATA must be stable when DATA_VALID asserted
  property p_data_stable_valid;
    @(posedge sclk) disable iff (!rst_n)
    data_valid |=> $stable(data_out);
  endproperty
  VERA_SAR_DATA_STABLE:
    assert property (p_data_stable_valid)
    else $error("VERA_FAIL | IP=%s | CHECK=SAR_DATA_STABLE | data_out changed while data_valid held | @%0t",
                IP_NAME, $time);

  // SVA.4: Output code must be within valid range
  property p_code_valid_range;
    @(posedge sclk) disable iff (!rst_n)
    data_valid |-> (data_out inside {[0:(2**N_BITS)-1]});
  endproperty
  VERA_SAR_CODE_RANGE:
    assert property (p_code_valid_range)
    else $error("VERA_FAIL | IP=%s | CHECK=SAR_CODE_RANGE | code=0x%h out of range [0:%0d] | @%0t",
                IP_NAME, data_out, (2**N_BITS)-1, $time);

  // SVA.5: SOC must not be asserted during conversion
  property p_no_soc_during_conv;
    @(posedge sclk) disable iff (!rst_n)
    $rose(soc) |-> ##1 (!soc)[*MIN_CONV-1];
  endproperty
  VERA_SAR_NO_SOC_DURING_CONV:
    assert property (p_no_soc_during_conv)
    else $error("VERA_FAIL | IP=%s | CHECK=SAR_NO_SOC_DURING_CONV | SOC reasserted during conversion | @%0t",
                IP_NAME, $time);

  // SVA.6: EOC must de-assert after 1 cycle
  property p_eoc_single_cycle;
    @(posedge sclk) disable iff (!rst_n)
    $rose(eoc) |=> !eoc;
  endproperty
  VERA_SAR_EOC_SINGLE:
    assert property (p_eoc_single_cycle)
    else $error("VERA_FAIL | IP=%s | CHECK=SAR_EOC_SINGLE | EOC held for more than 1 cycle | @%0t",
                IP_NAME, $time);

  // SVA.7: Reset must clear EOC and DATA_VALID
  property p_rst_clears_outputs;
    @(posedge sclk)
    !rst_n |-> (!eoc && !data_valid);
  endproperty
  VERA_SAR_RST_CLEAR:
    assert property (p_rst_clears_outputs)
    else $error("VERA_FAIL | IP=%s | CHECK=SAR_RST_CLEAR | EOC or DATA_VALID active during reset | @%0t",
                IP_NAME, $time);

  // Coverage
  covergroup cg_sar_adc @(posedge sclk);
    cp_code: coverpoint data_out iff (data_valid) {
      bins zero       = {0};
      bins low        = {[1:'h1FF]};
      bins mid_low    = {['h200:'h7FF]};
      bins mid_high   = {['h800:'hBFF]};
      bins high       = {['hC00:'hFFE]};
      bins full_scale = {'hFFF};
    }
    cp_soc:  coverpoint soc;
    cp_eoc:  coverpoint eoc;
  endgroup
  cg_sar_adc cg_adc_inst = new();

endmodule

// ============================================================================
// SAR ADC UVM Scoreboard (analog in → digital code verification)
// ============================================================================
class vera_sar_adc_scoreboard extends vera_transform_scoreboard #(
  .T_IN (sar_adc_input_item),
  .T_OUT(sar_adc_output_item)
);
  `uvm_component_utils(vera_sar_adc_scoreboard)

  // ADC parameters (set via config_db)
  int    m_n_bits = 12;
  real   m_vref   = 1.8;
  real   m_tol_lsb = 1.5;  // tolerance in LSBs

  function new(string name, uvm_component parent);
    super.new(name, parent);
    m_ip_name      = "SAR_ADC_12B";
    m_checker_name = "vera_sar_adc_transfer_sb";
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    void'(uvm_config_db #(int)::get(this,  "", "n_bits",   m_n_bits));
    void'(uvm_config_db #(real)::get(this, "", "vref",     m_vref));
    void'(uvm_config_db #(real)::get(this, "", "tol_lsb",  m_tol_lsb));
    // Tolerance in absolute code units
    m_tolerance = m_tol_lsb;
  endfunction

  // Reference model: ideal ADC transfer function
  virtual function real reference_transform(sar_adc_input_item in_item);
    real ideal_code;
    real vin_clipped;
    vin_clipped = in_item.vin_v < 0 ? 0.0 :
                  in_item.vin_v > in_item.vref_v ? in_item.vref_v : in_item.vin_v;
    ideal_code  = $floor(vin_clipped / in_item.vref_v * (2**m_n_bits));
    return ideal_code;
  endfunction

  // Extract numeric code from output item
  virtual function real get_output_value(sar_adc_output_item out_item);
    return real'(out_item.code);
  endfunction

  // OVERRIDE: more descriptive recommendation
  virtual function void check_queues();
    // Call parent which uses compare_items/tolerance
    super.check_queues();
  endfunction

endclass

// ============================================================================
// SAR ADC Full Environment
// ============================================================================
class vera_sar_adc_env extends uvm_env;
  `uvm_component_utils(vera_sar_adc_env)

  vera_sar_adc_scoreboard  m_scoreboard;
  vera_param_checker_component m_param_chk;
  vera_report_collector    m_collector;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_scoreboard = vera_sar_adc_scoreboard::type_id::create("m_scoreboard", this);
    m_param_chk  = vera_param_checker_component::type_id::create("m_param_chk", this);
    m_collector  = vera_report_collector::get();

    uvm_config_db #(string)::set(this, "*", "ip_name", "SAR_ADC_12B");
    uvm_config_db #(string)::set(null, "vera_report_collector",
                                 "report_file", "vera_sar_adc_report.json");
  endfunction

  // Called from test to run supply/reference checks
  function void check_power_on_conditions(
    real vdd_v, real vref_v, real vdd_min, real vdd_max,
    real vref_min, real vref_max
  );
    void'(m_param_chk.check_real("vera_adc_vdd", vdd_v, vdd_min, vdd_max, "V",
      "/tb/vdd", "power-on VDD check",
      "Check power supply routing and decoupling"));
    void'(m_param_chk.check_real("vera_adc_vref", vref_v, vref_min, vref_max, "V",
      "/tb/vref", "power-on VREF check",
      "Check reference buffer stability and load regulation"));
  endfunction

endclass

// ============================================================================
// SAR ADC Base Test
// ============================================================================
class vera_sar_adc_base_test extends uvm_test;
  `uvm_component_utils(vera_sar_adc_base_test)

  vera_sar_adc_env m_env;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_env = vera_sar_adc_env::type_id::create("m_env", this);
  endfunction

  task run_phase(uvm_phase phase);
    phase.raise_objection(this);

    // Check power-on conditions
    m_env.check_power_on_conditions(
      1.80, 1.80,         // measured VDD and VREF
      1.71, 1.89,         // VDD spec
      1.79, 1.81          // VREF spec
    );

    // TODO: Run conversion sequences
    `uvm_info("VERA_SAR_ADC", "Starting ADC conversion test...", UVM_MEDIUM)
    #100000;

    phase.drop_objection(this);
  endtask

endclass
