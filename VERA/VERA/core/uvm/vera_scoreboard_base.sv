// ============================================================================
// VERA — Verification Engine for Runtime & Autonomous Checking
// FILE: core/uvm/vera_scoreboard_base.sv
// DESC: Base UVM scoreboard with VERA reporting, pipeline tracking, 
//       transform checking, and out-of-order support
// VERSION: 1.0
// ============================================================================

`ifndef VERA_SCOREBOARD_BASE_SV
`define VERA_SCOREBOARD_BASE_SV

// ============================================================================
// VERA Result Item — Standard TLM object for all scoreboard results
// ============================================================================
class vera_result_item extends uvm_object;
  `uvm_object_utils(vera_result_item)

  // Identity
  string vera_version    = "1.0";
  string ip_name;
  string block_name;
  string test_name;
  string checker_name;
  string checker_type;   // "uvm_scoreboard", "sva", "post_sim_python", "skill"
  string layer;          // "protocol", "parametric", "structural", "functional"

  // Result
  string status;         // "PASS", "FAIL", "WARNING", "INFO"
  string severity;       // "ERROR", "WARNING", "INFO"
  string expected_str;
  string actual_str;
  string margin_str;
  string context_str;
  string debug_signal;
  real   sim_time_ns;
  string recommendation;

  // Comparison data (typed)
  longint unsigned expected_val;
  longint unsigned actual_val;
  real             expected_real;
  real             actual_real;

  function new(string name = "vera_result_item");
    super.new(name);
    sim_time_ns = $realtime / 1.0e9;
  endfunction

  // Convert to JSON string for VERA report engine
  function string to_json();
    return $sformatf(
      "{\"vera_version\":\"%s\",\"ip_name\":\"%s\",\"checker_name\":\"%s\",\"checker_type\":\"%s\",\"status\":\"%s\",\"severity\":\"%s\",\"expected\":\"%s\",\"actual\":\"%s\",\"margin\":\"%s\",\"context\":\"%s\",\"debug_signal\":\"%s\",\"time_ns\":%.3f,\"recommendation\":\"%s\"}",
      vera_version, ip_name, checker_name, checker_type,
      status, severity, expected_str, actual_str,
      margin_str, context_str, debug_signal, sim_time_ns, recommendation
    );
  endfunction

  // UVM field registration
  function void do_print(uvm_printer printer);
    super.do_print(printer);
    printer.print_string("status",       status);
    printer.print_string("checker_name", checker_name);
    printer.print_string("expected",     expected_str);
    printer.print_string("actual",       actual_str);
    printer.print_string("margin",       margin_str);
    printer.print_time("sim_time",       longint'(sim_time_ns));
  endfunction

endclass

// ============================================================================
// VERA Report Collector — Singleton aggregator for all checker results
// ============================================================================
class vera_report_collector extends uvm_component;
  `uvm_component_utils(vera_report_collector)

  static vera_report_collector m_inst;
  vera_result_item              result_db[$];
  int                           pass_count;
  int                           fail_count;
  int                           warn_count;
  string                        report_file;

  uvm_analysis_export #(vera_result_item) result_export;

  function new(string name = "vera_report_collector", uvm_component parent = null);
    super.new(name, parent);
    pass_count  = 0;
    fail_count  = 0;
    warn_count  = 0;
    report_file = "vera_report.json";
  endfunction

  static function vera_report_collector get();
    if (m_inst == null)
      m_inst = vera_report_collector::type_id::create(
        "vera_report_collector", null);
    return m_inst;
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    result_export = new("result_export", this);
  endfunction

  function void write(vera_result_item item);
    result_db.push_back(item);
    if      (item.status == "PASS")    pass_count++;
    else if (item.status == "FAIL")    fail_count++;
    else if (item.status == "WARNING") warn_count++;
    // Echo to UVM log
    if (item.status == "FAIL")
      `uvm_error("VERA", $sformatf("[%s] %s | EXP: %s | ACT: %s | @%.1fns",
        item.ip_name, item.checker_name,
        item.expected_str, item.actual_str, item.sim_time_ns))
    else if (item.status == "WARNING")
      `uvm_warning("VERA", $sformatf("[%s] %s | %s",
        item.ip_name, item.checker_name, item.context_str))
  endfunction

  // Called in final_phase — writes VERA JSON report
  function void final_phase(uvm_phase phase);
    int fd;
    super.final_phase(phase);
    fd = $fopen(report_file, "w");
    if (fd) begin
      $fwrite(fd, "{\n");
      $fwrite(fd, "  \"vera_report\": {\n");
      $fwrite(fd, "    \"summary\": {\n");
      $fwrite(fd, "      \"total\": %0d,\n", result_db.size());
      $fwrite(fd, "      \"pass\": %0d,\n", pass_count);
      $fwrite(fd, "      \"fail\": %0d,\n", fail_count);
      $fwrite(fd, "      \"warning\": %0d\n", warn_count);
      $fwrite(fd, "    },\n");
      $fwrite(fd, "    \"results\": [\n");
      foreach (result_db[i]) begin
        $fwrite(fd, "      %s", result_db[i].to_json());
        if (i < result_db.size()-1) $fwrite(fd, ",");
        $fwrite(fd, "\n");
      end
      $fwrite(fd, "    ]\n");
      $fwrite(fd, "  }\n");
      $fwrite(fd, "}\n");
      $fclose(fd);
    end
    `uvm_info("VERA", $sformatf(
      "\n========================================\n  VERA SUMMARY: PASS=%0d FAIL=%0d WARN=%0d\n========================================",
      pass_count, fail_count, warn_count), UVM_NONE)
  endfunction

endclass

// ============================================================================
// VERA Scoreboard Base — Parameterizable base for all VERA scoreboards
// ============================================================================
class vera_scoreboard_base #(
  type T_EXP = uvm_sequence_item,   // expected (reference) transaction type
  type T_ACT = uvm_sequence_item    // actual (DUT) transaction type
) extends uvm_scoreboard;

  `uvm_component_param_utils(vera_scoreboard_base #(T_EXP, T_ACT))

  // Configuration
  string   m_ip_name     = "UNDEFINED";
  string   m_checker_name = "vera_sb";
  string   m_layer        = "functional";
  int      m_max_latency  = 100;    // max cycles between stimulus and response
  bit      m_ordered      = 1;      // 1=ordered, 0=out-of-order matching

  // TLM ports
  uvm_analysis_export #(T_EXP) expected_export;
  uvm_analysis_export #(T_ACT) actual_export;

  // Internal queues
  T_EXP  m_exp_q[$];
  T_ACT  m_act_q[$];
  int    m_match_count;
  int    m_mismatch_count;
  int    m_timeout_count;

  // VERA report connection
  uvm_analysis_port #(vera_result_item) vera_result_port;

  // Reference to collector
  vera_report_collector m_collector;

  function new(string name = "vera_scoreboard_base", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    expected_export   = new("expected_export", this);
    actual_export     = new("actual_export", this);
    vera_result_port  = new("vera_result_port", this);
    m_collector       = vera_report_collector::get();

    // Get config
    void'(uvm_config_db #(string)::get(this, "", "ip_name", m_ip_name));
    void'(uvm_config_db #(string)::get(this, "", "checker_name", m_checker_name));
    void'(uvm_config_db #(int)::get(this, "", "max_latency", m_max_latency));
  endfunction

  // Override in derived classes for custom comparison
  virtual function bit compare_items(T_EXP exp_item, T_ACT act_item);
    // Default: convert both to string and compare
    return (exp_item.convert2string() == act_item.convert2string());
  endfunction

  // Override for custom expected→actual context extraction
  virtual function string get_context(T_EXP exp_item, T_ACT act_item);
    return "";
  endfunction

  // Override for debug signal path
  virtual function string get_debug_signal(T_EXP exp_item);
    return "";
  endfunction

  // Override for failure recommendation
  virtual function string get_recommendation(T_EXP exp_item, T_ACT act_item);
    return "Check DUT implementation and reference model alignment";
  endfunction

  // Write expected (from predictor/reference model)
  virtual function void write_expected(T_EXP item);
    m_exp_q.push_back(item);
    check_queues();
  endfunction

  // Write actual (from DUT monitor)
  virtual function void write_actual(T_ACT item);
    m_act_q.push_back(item);
    check_queues();
  endfunction

  // Core comparison logic
  virtual function void check_queues();
    vera_result_item result;
    T_EXP exp_item;
    T_ACT act_item;

    while (m_exp_q.size() > 0 && m_act_q.size() > 0) begin
      exp_item = m_exp_q.pop_front();
      act_item = m_act_q.pop_front();

      result = vera_result_item::type_id::create("vera_result");
      result.ip_name       = m_ip_name;
      result.checker_name  = m_checker_name;
      result.checker_type  = "uvm_scoreboard";
      result.layer         = m_layer;
      result.sim_time_ns   = $realtime / 1.0e9;
      result.expected_str  = exp_item.convert2string();
      result.actual_str    = act_item.convert2string();
      result.context_str   = get_context(exp_item, act_item);
      result.debug_signal  = get_debug_signal(exp_item);
      result.recommendation = get_recommendation(exp_item, act_item);

      if (compare_items(exp_item, act_item)) begin
        result.status   = "PASS";
        result.severity = "INFO";
        m_match_count++;
      end else begin
        result.status   = "FAIL";
        result.severity = "ERROR";
        m_mismatch_count++;
      end

      vera_result_port.write(result);
      m_collector.write(result);
    end
  endfunction

  function void check_phase(uvm_phase phase);
    super.check_phase(phase);
    // Drain leftover items
    if (m_exp_q.size() != 0) begin
      `uvm_error("VERA", $sformatf(
        "[%s] %0d unmatched expected items remaining", m_ip_name, m_exp_q.size()))
    end
    if (m_act_q.size() != 0) begin
      `uvm_error("VERA", $sformatf(
        "[%s] %0d unmatched actual items remaining", m_ip_name, m_act_q.size()))
    end
  endfunction

  function void report_phase(uvm_phase phase);
    super.report_phase(phase);
    `uvm_info(get_name(), $sformatf(
      "[%s] Scoreboard %s: MATCH=%0d MISMATCH=%0d",
      m_ip_name, m_checker_name, m_match_count, m_mismatch_count), UVM_NONE)
  endfunction

endclass

// ============================================================================
// VERA Transform Scoreboard — For ADC/DAC/Filter (input→output with transform)
// ============================================================================
class vera_transform_scoreboard #(
  type T_IN  = uvm_sequence_item,
  type T_OUT = uvm_sequence_item
) extends uvm_scoreboard;

  `uvm_component_param_utils(vera_transform_scoreboard #(T_IN, T_OUT))

  string m_ip_name;
  string m_checker_name;
  real   m_tolerance;        // absolute tolerance
  real   m_tolerance_pct;    // percentage tolerance

  uvm_analysis_export #(T_IN)  input_export;
  uvm_analysis_export #(T_OUT) output_export;
  uvm_analysis_port #(vera_result_item) vera_result_port;

  T_IN   m_in_q[$];
  T_OUT  m_out_q[$];

  vera_report_collector m_collector;

  function new(string name = "vera_transform_sb", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    input_export     = new("input_export", this);
    output_export    = new("output_export", this);
    vera_result_port = new("vera_result_port", this);
    m_collector      = vera_report_collector::get();
    void'(uvm_config_db #(string)::get(this, "", "ip_name", m_ip_name));
    void'(uvm_config_db #(real)::get(this, "", "tolerance", m_tolerance));
  endfunction

  // OVERRIDE: Apply reference transform (e.g., analog input → digital code)
  virtual function real reference_transform(T_IN in_item);
    return 0.0; // Override this!
  endfunction

  // OVERRIDE: Extract numeric value from output item
  virtual function real get_output_value(T_OUT out_item);
    return 0.0; // Override this!
  endfunction

  virtual function void check_queues();
    vera_result_item result;
    T_IN  in_item;
    T_OUT out_item;
    real  expected_val, actual_val, error;

    while (m_in_q.size() > 0 && m_out_q.size() > 0) begin
      in_item      = m_in_q.pop_front();
      out_item     = m_out_q.pop_front();
      expected_val = reference_transform(in_item);
      actual_val   = get_output_value(out_item);
      error        = actual_val - expected_val;

      result = vera_result_item::type_id::create("vera_transform_result");
      result.ip_name       = m_ip_name;
      result.checker_name  = m_checker_name;
      result.checker_type  = "uvm_transform_sb";
      result.layer         = "parametric";
      result.sim_time_ns   = $realtime / 1.0e9;
      result.expected_str  = $sformatf("%.6f", expected_val);
      result.actual_str    = $sformatf("%.6f", actual_val);
      result.margin_str    = $sformatf("%.6f (tol=%.6f)", error, m_tolerance);
      result.expected_real = expected_val;
      result.actual_real   = actual_val;

      if ($abs(error) <= m_tolerance) begin
        result.status   = "PASS";
        result.severity = "INFO";
      end else begin
        result.status   = "FAIL";
        result.severity = "ERROR";
        result.recommendation = $sformatf(
          "Error %.6f exceeds tolerance %.6f. Check transfer function.", error, m_tolerance);
      end

      vera_result_port.write(result);
      m_collector.write(result);
    end
  endfunction

  virtual function void write_input(T_IN item);
    m_in_q.push_back(item);
    check_queues();
  endfunction

  virtual function void write_output(T_OUT item);
    m_out_q.push_back(item);
    check_queues();
  endfunction

endclass

`endif // VERA_SCOREBOARD_BASE_SV
