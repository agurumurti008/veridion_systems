// ============================================================================
// VERA — Verification Engine for Runtime & Autonomous Checking
// FILE: templates/mixed_signal/vera_serdes_checker.sv
// DESC: SerDes / High-Speed IO checker suite.
//       Covers: 8b10b/64b66b encoding, CDR lock, eye mask, comma detect,
//               lane alignment, elastic buffer, receiver equalization checks.
//       Post-sim Python companion: vera_serdes_postsim.py
// VERSION: 1.0
// ============================================================================

`ifndef VERA_SERDES_CHECKER_SV
`define VERA_SERDES_CHECKER_SV

// ============================================================================
// MODULE: vera_8b10b_checker
// Verifies 8b10b encoded serial stream: running disparity, invalid symbols
// ============================================================================
module vera_8b10b_checker #(
  parameter string IP_NAME      = "SERDES",
  parameter int    MAX_RD_ERR   = 0,    // max running disparity errors
  parameter int    MAX_CODE_ERR = 0     // max invalid code errors
)(
  input logic        clk,
  input logic        rst_n,
  input logic [9:0]  rx_symbol,     // 10-bit received symbol
  input logic        rx_valid,      // symbol valid
  input logic        rx_disparity,  // current running disparity (0=neg, 1=pos)
  input logic        rx_code_err,   // decoder flags invalid symbol
  input logic        rx_disp_err,   // decoder flags disparity error
  input logic        rx_comma,      // K28.5 or K28.1 comma detected
  input logic        rx_locked      // CDR/word-lock indicator
);

  int code_err_count;
  int disp_err_count;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      code_err_count <= 0;
      disp_err_count <= 0;
    end else if (rx_valid) begin
      if (rx_code_err) code_err_count <= code_err_count + 1;
      if (rx_disp_err) disp_err_count <= disp_err_count + 1;
    end
  end

  // 8B10B.1: No code errors when locked
  property p_no_code_err_locked;
    @(posedge clk) disable iff (!rst_n)
    (rx_valid && rx_locked) |-> !rx_code_err;
  endproperty
  VERA_8B10B_CODE_ERR:
    assert property (p_no_code_err_locked)
    else $error("VERA_FAIL | IP=%s | CHECK=8B10B_CODE_ERR | invalid 10b symbol while locked | sym=0x%0h @%0t",
                IP_NAME, rx_symbol, $time);

  // 8B10B.2: No running disparity errors when locked
  property p_no_disp_err_locked;
    @(posedge clk) disable iff (!rst_n)
    (rx_valid && rx_locked) |-> !rx_disp_err;
  endproperty
  VERA_8B10B_DISP_ERR:
    assert property (p_no_disp_err_locked)
    else $error("VERA_FAIL | IP=%s | CHECK=8B10B_DISP_ERR | disparity error while locked @%0t",
                IP_NAME, $time);

  // 8B10B.3: After comma detection, lock must be maintained
  property p_lock_after_comma;
    @(posedge clk) disable iff (!rst_n)
    $rose(rx_comma) |-> ##[0:4] rx_locked;
  endproperty
  VERA_8B10B_LOCK_AFTER_COMMA:
    assert property (p_lock_after_comma)
    else $error("VERA_FAIL | IP=%s | CHECK=8B10B_LOCK_AFTER_COMMA | not locked within 4 cycles of comma @%0t",
                IP_NAME, $time);

  // 8B10B.4: Lock must not drop unless reset
  property p_lock_stable;
    @(posedge clk) disable iff (!rst_n)
    $rose(rx_locked) |-> rx_locked[*100];  // stay locked for 100+ cycles
  endproperty
  VERA_8B10B_LOCK_STABLE:
    assert property (p_lock_stable)
    else $error("VERA_FAIL | IP=%s | CHECK=8B10B_LOCK_STABLE | CDR lock lost after <100 cycles @%0t",
                IP_NAME, $time);

  covergroup cg_8b10b @(posedge clk);
    cp_code_err:  coverpoint rx_code_err iff (rx_valid);
    cp_disp_err:  coverpoint rx_disp_err iff (rx_valid);
    cp_comma:     coverpoint rx_comma     iff (rx_valid);
    cp_disp:      coverpoint rx_disparity iff (rx_valid);
    cp_lock:      coverpoint rx_locked;
    cx_err_lock:  cross cp_code_err, cp_lock;
  endgroup
  cg_8b10b cg_8b10b_inst = new();

endmodule

// ============================================================================
// MODULE: vera_serdes_link_checker
// Lane alignment, elastic buffer, PRBS, link error rate
// ============================================================================
module vera_serdes_link_checker #(
  parameter string IP_NAME       = "SERDES",
  parameter int    N_LANES       = 4,
  parameter int    MAX_ALIGN_CYC = 10000,  // max cycles to achieve lane alignment
  parameter int    MAX_BER       = 0,      // max bit errors in observation window
  parameter int    OBS_WINDOW    = 1000,   // BER observation window (symbols)
  parameter int    ELASTIC_DEPTH = 8       // elastic buffer depth
)(
  input logic                  clk,
  input logic                  rst_n,
  input logic [N_LANES-1:0]    lane_lock,       // per-lane CDR lock
  input logic                  link_aligned,     // multi-lane alignment achieved
  input logic [N_LANES-1:0]    lane_prbs_err,    // per-lane PRBS error
  input logic [$clog2(ELASTIC_DEPTH+1)-1:0] elastic_level, // elastic buffer fill level
  input logic                  elastic_underrun, // elastic buffer underrun
  input logic                  elastic_overrun   // elastic buffer overrun
);

  int bit_error_count;
  int obs_count;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      bit_error_count <= 0;
      obs_count       <= 0;
    end else begin
      obs_count <= obs_count + 1;
      bit_error_count <= bit_error_count + $countones(lane_prbs_err);
      if (obs_count >= OBS_WINDOW) begin
        obs_count <= 0;
        bit_error_count <= 0;
      end
    end
  end

  // LINK.1: All lanes must achieve CDR lock before alignment
  property p_all_lanes_lock;
    @(posedge clk) disable iff (!rst_n)
    $rose(link_aligned) |-> (&lane_lock);
  endproperty
  VERA_SERDES_ALL_LANES_LOCK:
    assert property (p_all_lanes_lock)
    else $error("VERA_FAIL | IP=%s | CHECK=SERDES_ALL_LANES_LOCK | alignment asserted but lane_lock=0x%0h @%0t",
                IP_NAME, lane_lock, $time);

  // LINK.2: Alignment must come within MAX_ALIGN_CYC after all lanes lock
  property p_align_time;
    @(posedge clk) disable iff (!rst_n)
    (&lane_lock) |-> ##[1:MAX_ALIGN_CYC] link_aligned;
  endproperty
  VERA_SERDES_ALIGN_TIME:
    assert property (p_align_time)
    else $error("VERA_FAIL | IP=%s | CHECK=SERDES_ALIGN_TIME | alignment not achieved in %0d cycles @%0t",
                IP_NAME, MAX_ALIGN_CYC, $time);

  // LINK.3: No elastic buffer overrun
  property p_no_elastic_overrun;
    @(posedge clk) disable iff (!rst_n)
    !elastic_overrun;
  endproperty
  VERA_SERDES_ELASTIC_OVERRUN:
    assert property (p_no_elastic_overrun)
    else $error("VERA_FAIL | IP=%s | CHECK=SERDES_ELASTIC_OVERRUN | elastic buffer overrun at level=%0d @%0t",
                IP_NAME, elastic_level, $time);

  // LINK.4: No elastic buffer underrun
  property p_no_elastic_underrun;
    @(posedge clk) disable iff (!rst_n)
    !elastic_underrun;
  endproperty
  VERA_SERDES_ELASTIC_UNDERRUN:
    assert property (p_no_elastic_underrun)
    else $error("VERA_FAIL | IP=%s | CHECK=SERDES_ELASTIC_UNDERRUN | elastic buffer underrun @%0t",
                IP_NAME, $time);

  // LINK.5: BER must not exceed MAX_BER over observation window
  property p_ber_limit;
    @(posedge clk) disable iff (!rst_n)
    (obs_count == OBS_WINDOW) |-> (bit_error_count <= MAX_BER);
  endproperty
  VERA_SERDES_BER:
    assert property (p_ber_limit)
    else $error("VERA_FAIL | IP=%s | CHECK=SERDES_BER | errors=%0d in %0d symbols (BER=%.2e) @%0t",
                IP_NAME, bit_error_count, OBS_WINDOW,
                real'(bit_error_count)/real'(OBS_WINDOW*10), $time);

  covergroup cg_serdes @(posedge clk);
    cp_aligned:   coverpoint link_aligned;
    cp_lane_lock: coverpoint lane_lock;
    cp_elast:     coverpoint elastic_level {
      bins empty  = {0};
      bins low    = {[1:ELASTIC_DEPTH/4]};
      bins mid    = {[ELASTIC_DEPTH/4+1:3*ELASTIC_DEPTH/4]};
      bins high   = {[3*ELASTIC_DEPTH/4+1:ELASTIC_DEPTH]};
    }
  endgroup
  cg_serdes cg_serdes_inst = new();

endmodule

`endif // VERA_SERDES_CHECKER_SV
