// ============================================================================
// VERA — Verification Engine for Runtime & Autonomous Checking
// FILE: core/uvm/vera_predictor_base.sv
// DESC: Base predictor and monitor classes for VERA UVM environments.
//       - vera_monitor_base:    parameterized monitor template
//       - vera_predictor_base:  TLM-based reference model predictor
//       - vera_coverage_base:   automatic functional coverage collector
//       - vera_checker_agent:   self-contained checking agent
// VERSION: 1.0
// ============================================================================

`ifndef VERA_PREDICTOR_BASE_SV
`define VERA_PREDICTOR_BASE_SV

// ============================================================================
// vera_monitor_base — Parameterized UVM monitor with VERA hooks
// ============================================================================
class vera_monitor_base #(type T = uvm_sequence_item) extends uvm_monitor;
  `uvm_component_param_utils(vera_monitor_base #(T))

  // Configuration
  string  m_ip_name   = "UNDEFINED";
  string  m_side      = "input";    // "input" or "output"
  bit     m_active    = 1;          // 0=passive (observe only)

  // Analysis port — connects to predictor or scoreboard
  uvm_analysis_port #(T) ap;

  // VERA result port for directly-detected violations
  uvm_analysis_port #(vera_result_item) vera_ap;

  // Virtual interface handle — set in derived class
  // virtual my_if vif;

  function new(string name = "vera_monitor_base", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    ap      = new("ap",      this);
    vera_ap = new("vera_ap", this);
    void'(uvm_config_db #(string)::get(this, "", "ip_name",  m_ip_name));
    void'(uvm_config_db #(string)::get(this, "", "side",     m_side));
    void'(uvm_config_db #(bit)::get(this,   "", "active",    m_active));
  endfunction

  // Override: main collection loop
  virtual task run_phase(uvm_phase phase);
    T item;
    forever begin
      collect_item(item);
      if (item != null) begin
        ap.write(item);
        post_collect(item);
      end
    end
  endtask

  // OVERRIDE in derived class: populate item from interface
  virtual task collect_item(output T item);
    item = null;
    #1; // prevent infinite loop in base
  endtask

  // OVERRIDE: post-collection hook (optional protocol checks)
  virtual function void post_collect(T item); endfunction

  // Helper: emit VERA result directly from monitor
  function void emit_vera_result(
    string checker_name,
    string status,
    string expected,
    string actual,
    string ctx    = "",
    string signal = ""
  );
    vera_result_item r = vera_result_item::type_id::create("mon_result");
    r.ip_name      = m_ip_name;
    r.checker_name = checker_name;
    r.checker_type = "uvm_monitor";
    r.status       = status;
    r.severity     = (status == "PASS") ? "INFO" : "ERROR";
    r.expected_str = expected;
    r.actual_str   = actual;
    r.context_str  = ctx;
    r.debug_signal = signal;
    r.sim_time_ns  = $realtime / 1.0e9;
    vera_ap.write(r);
    vera_report_collector::get().write(r);
  endfunction

endclass


// ============================================================================
// vera_predictor_base — TLM predictor (stimulus → expected response)
// ============================================================================
class vera_predictor_base #(
  type T_IN  = uvm_sequence_item,
  type T_OUT = uvm_sequence_item
) extends uvm_subscriber #(T_IN);

  `uvm_component_param_utils(vera_predictor_base #(T_IN, T_OUT))

  string m_ip_name = "UNDEFINED";

  // Output port to scoreboard expected queue
  uvm_analysis_port #(T_OUT) predicted_ap;

  function new(string name = "vera_predictor_base", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    predicted_ap = new("predicted_ap", this);
    void'(uvm_config_db #(string)::get(this, "", "ip_name", m_ip_name));
  endfunction

  // Called automatically by TLM when new input item arrives
  virtual function void write(T_IN t);
    T_OUT predicted;
    predicted = predict(t);
    if (predicted != null)
      predicted_ap.write(predicted);
  endfunction

  // OVERRIDE: implement reference model transform
  // Returns the predicted output for a given input
  virtual function T_OUT predict(T_IN in_item);
    return null;  // Must override
  endfunction

endclass


// ============================================================================
// vera_coverage_base — Automatic functional coverage collector
// ============================================================================
class vera_coverage_base #(type T = uvm_sequence_item) extends uvm_subscriber #(T);
  `uvm_component_param_utils(vera_coverage_base #(T))

  string m_ip_name = "UNDEFINED";
  T      m_item;

  // Coverage hit tracking (for VERA report integration)
  int    m_total_bins;
  int    m_hit_bins;

  function new(string name = "vera_coverage_base", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    void'(uvm_config_db #(string)::get(this, "", "ip_name", m_ip_name));
  endfunction

  virtual function void write(T t);
    m_item = t;
    sample_coverage(t);
  endfunction

  // OVERRIDE: call your covergroup .sample() here
  virtual function void sample_coverage(T item); endfunction

  // Report coverage to VERA at end of test
  function void report_phase(uvm_phase phase);
    vera_result_item r;
    real cov_pct;
    super.report_phase(phase);

    if (m_total_bins > 0) begin
      cov_pct = real'(m_hit_bins) / real'(m_total_bins) * 100.0;
      r = vera_result_item::type_id::create("cov_result");
      r.ip_name      = m_ip_name;
      r.checker_name = $sformatf("%s_functional_coverage", m_ip_name.tolower());
      r.checker_type = "uvm_coverage";
      r.layer        = "coverage";
      r.status       = (cov_pct >= 95.0) ? "PASS" : "WARNING";
      r.severity     = (cov_pct >= 95.0) ? "INFO"  : "WARNING";
      r.expected_str = ">= 95%";
      r.actual_str   = $sformatf("%.1f%% (%0d/%0d bins)", cov_pct, m_hit_bins, m_total_bins);
      r.margin_str   = $sformatf("%+.1f%%", cov_pct - 95.0);
      vera_report_collector::get().write(r);
    end
  endfunction

endclass


// ============================================================================
// vera_checker_agent — Self-contained checking agent
// Bundles monitor + predictor + scoreboard into one portable component
// ============================================================================
class vera_checker_agent #(
  type T_MON_IN  = uvm_sequence_item,
  type T_MON_OUT = uvm_sequence_item
) extends uvm_agent;

  `uvm_component_param_utils(vera_checker_agent #(T_MON_IN, T_MON_OUT))

  // Sub-components
  vera_monitor_base   #(T_MON_IN)  m_in_monitor;
  vera_monitor_base   #(T_MON_OUT) m_out_monitor;
  vera_predictor_base #(T_MON_IN, T_MON_OUT) m_predictor;
  vera_scoreboard_base#(T_MON_OUT, T_MON_OUT) m_scoreboard;

  string m_ip_name = "UNDEFINED";

  // External analysis exports for connecting to sequencer/driver outputs
  uvm_analysis_export #(T_MON_IN)  stim_export;
  uvm_analysis_export #(T_MON_OUT) response_export;

  // TLM FIFOs
  uvm_tlm_analysis_fifo #(T_MON_IN)  stim_fifo;
  uvm_tlm_analysis_fifo #(T_MON_OUT) resp_fifo;

  function new(string name = "vera_checker_agent", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    void'(uvm_config_db #(string)::get(this, "", "ip_name", m_ip_name));

    m_in_monitor  = vera_monitor_base  #(T_MON_IN)::type_id::create("m_in_mon",  this);
    m_out_monitor = vera_monitor_base  #(T_MON_OUT)::type_id::create("m_out_mon", this);
    m_predictor   = vera_predictor_base#(T_MON_IN, T_MON_OUT)::type_id::create("m_pred", this);
    m_scoreboard  = vera_scoreboard_base#(T_MON_OUT, T_MON_OUT)::type_id::create("m_sb", this);

    stim_export    = new("stim_export",    this);
    response_export = new("response_export", this);
    stim_fifo      = new("stim_fifo",      this);
    resp_fifo      = new("resp_fifo",      this);

    uvm_config_db #(string)::set(this, "*", "ip_name", m_ip_name);
  endfunction

  function void connect_phase(uvm_phase phase);
    // Stimulus path: stim_export → fifo → predictor → scoreboard expected
    stim_export.connect(stim_fifo.analysis_export);
    m_predictor.analysis_export.connect(stim_fifo.get_export);
    m_predictor.predicted_ap.connect(m_scoreboard.expected_export);

    // Response path: response_export → scoreboard actual
    response_export.connect(resp_fifo.analysis_export);
    m_out_monitor.ap.connect(resp_fifo.analysis_export);
  endfunction

endclass


// ============================================================================
// vera_param_checker_component — Standalone parametric checker UVM component
// Checks scalar values against bounds at runtime during simulation
// ============================================================================
class vera_param_checker_component extends uvm_component;
  `uvm_component_utils(vera_param_checker_component)

  string m_ip_name;
  vera_report_collector m_collector;

  function new(string name = "vera_param_chk", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_collector = vera_report_collector::get();
    void'(uvm_config_db #(string)::get(this, "", "ip_name", m_ip_name));
  endfunction

  // Call from test or sequences to check any real-valued measurement
  function vera_result_item check_real(
    string checker_name,
    real   measured,
    real   min_val,
    real   max_val,
    string unit        = "",
    string signal      = "",
    string ctx         = "",
    string rec         = ""
  );
    vera_result_item r = vera_result_item::type_id::create("param_result");
    bit in_spec = (measured >= min_val) && (measured <= max_val);

    r.ip_name       = m_ip_name;
    r.checker_name  = checker_name;
    r.checker_type  = "uvm_parametric";
    r.layer         = "parametric";
    r.status        = in_spec ? "PASS" : "FAIL";
    r.severity      = in_spec ? "INFO" : "ERROR";
    r.expected_str  = $sformatf("%0g to %0g %s", min_val, max_val, unit);
    r.actual_str    = $sformatf("%0g %s", measured, unit);
    r.margin_str    = $sformatf("lo=%+0g hi=%+0g %s",
                                measured - min_val, max_val - measured, unit);
    r.context_str   = ctx;
    r.debug_signal  = signal;
    r.sim_time_ns   = $realtime / 1.0e9;
    r.recommendation = in_spec ? "" : rec;

    m_collector.write(r);
    return r;
  endfunction

  // Convenience: check integer value
  function vera_result_item check_int(
    string checker_name,
    longint measured,
    longint min_val,
    longint max_val,
    string unit   = "",
    string signal = "",
    string ctx    = ""
  );
    return check_real(checker_name, real'(measured),
                      real'(min_val), real'(max_val),
                      unit, signal, ctx);
  endfunction

endclass

`endif // VERA_PREDICTOR_BASE_SV
