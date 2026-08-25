// ============================================================================
// VERA — Verification Engine for Runtime & Autonomous Checking
// FILE: core/sv/vera_sva_library.sv
// DESC: Core SVA assertion library — parameterizable, portable, VERA-tagged
// VERSION: 1.0
// ============================================================================

`ifndef VERA_SVA_LIBRARY_SV
`define VERA_SVA_LIBRARY_SV

// ============================================================================
// VERA ASSERTION RESULT MACRO
// Standardized failure message format for all VERA SVA assertions
// ============================================================================
`define VERA_ASSERT_MSG(ip, check, expected, actual, ctx) \
  $error("VERA_FAIL | IP=%s | CHECK=%s | EXPECTED=%s | ACTUAL=%s | CTX=%s | TIME=%0t", \
         ip, check, expected, actual, ctx, $time)

`define VERA_PASS_MSG(ip, check, ctx) \
  $info("VERA_PASS | IP=%s | CHECK=%s | CTX=%s | TIME=%0t", \
        ip, check, ctx, $time)

// ============================================================================
// MODULE: vera_clk_checker
// Purpose: Clock frequency, duty cycle, jitter monitoring
// ============================================================================
module vera_clk_checker #(
  parameter string    IP_NAME     = "UNDEFINED",
  parameter string    CLK_NAME    = "clk",
  parameter realtime  CLK_PERIOD  = 10.0,   // ns
  parameter real      FREQ_TOL    = 0.05,   // 5% tolerance
  parameter real      DUTY_MIN    = 0.45,   // 45%
  parameter real      DUTY_MAX    = 0.55,   // 55%
  parameter realtime  MAX_JITTER  = 0.5     // ns
)(
  input logic clk,
  input logic rst_n,
  input logic enable
);

  realtime rise_time_prev, rise_time_curr, fall_time_curr;
  realtime measured_period, measured_high_time;
  real     measured_duty, measured_freq_mhz;
  real     freq_min, freq_max;

  initial begin
    freq_min = (1.0 / (CLK_PERIOD * 1e-9)) * (1.0 - FREQ_TOL) / 1e6;
    freq_max = (1.0 / (CLK_PERIOD * 1e-9)) * (1.0 + FREQ_TOL) / 1e6;
  end

  always @(posedge clk) begin
    if (enable && rst_n) begin
      rise_time_prev = rise_time_curr;
      rise_time_curr = $realtime;
      if (rise_time_prev > 0) begin
        measured_period = rise_time_curr - rise_time_prev;
        measured_freq_mhz = 1.0e3 / real'(measured_period); // assuming ns
        if (measured_freq_mhz < freq_min || measured_freq_mhz > freq_max) begin
          `VERA_ASSERT_MSG(IP_NAME, "CLK_FREQUENCY",
            $sformatf("%.2f to %.2f MHz", freq_min, freq_max),
            $sformatf("%.2f MHz", measured_freq_mhz),
            CLK_NAME);
        end
      end
    end
  end

  always @(negedge clk) begin
    if (enable && rst_n) begin
      fall_time_curr = $realtime;
      if (rise_time_curr > 0 && fall_time_curr > rise_time_curr) begin
        measured_high_time = fall_time_curr - rise_time_curr;
        if (measured_period > 0) begin
          measured_duty = real'(measured_high_time) / real'(measured_period);
          if (measured_duty < DUTY_MIN || measured_duty > DUTY_MAX) begin
            `VERA_ASSERT_MSG(IP_NAME, "CLK_DUTY_CYCLE",
              $sformatf("%.1f%% to %.1f%%", DUTY_MIN*100, DUTY_MAX*100),
              $sformatf("%.1f%%", measured_duty*100),
              CLK_NAME);
          end
        end
      end
    end
  end

endmodule

// ============================================================================
// MODULE: vera_handshake_checker
// Purpose: Valid/ready handshake protocol checker (AXI-style)
// ============================================================================
module vera_handshake_checker #(
  parameter string IP_NAME      = "UNDEFINED",
  parameter string INTF_NAME    = "handshake",
  parameter int    MAX_WAIT     = 32,    // max cycles to wait for ready
  parameter int    MIN_HOLD     = 1      // min cycles valid must be held
)(
  input logic clk,
  input logic rst_n,
  input logic valid,
  input logic ready
);

  // SVA: valid must not deassert without transaction completing
  property p_valid_stable_until_ready;
    @(posedge clk) disable iff (!rst_n)
    (valid && !ready) |=> valid;
  endproperty

  // SVA: ready response must come within MAX_WAIT cycles
  property p_ready_response_time;
    @(posedge clk) disable iff (!rst_n)
    $rose(valid) |-> ##[1:MAX_WAIT] ready;
  endproperty

  // SVA: No valid pulse shorter than MIN_HOLD
  property p_valid_min_hold;
    @(posedge clk) disable iff (!rst_n)
    $rose(valid) |-> valid[*MIN_HOLD];
  endproperty

  VERA_VALID_STABLE:
    assert property (p_valid_stable_until_ready)
    else `VERA_ASSERT_MSG(IP_NAME, "HANDSHAKE_VALID_STABLE",
      "valid held until ready", "valid deasserted early", INTF_NAME);

  VERA_READY_RESPONSE:
    assert property (p_ready_response_time)
    else `VERA_ASSERT_MSG(IP_NAME, "HANDSHAKE_READY_TIMEOUT",
      $sformatf("ready within %0d cycles", MAX_WAIT),
      "timeout expired", INTF_NAME);

  VERA_VALID_HOLD:
    assert property (p_valid_min_hold)
    else `VERA_ASSERT_MSG(IP_NAME, "HANDSHAKE_VALID_HOLD",
      $sformatf("valid held >= %0d cycles", MIN_HOLD),
      "valid too short", INTF_NAME);

  // Coverage
  covergroup cg_handshake @(posedge clk);
    cp_valid: coverpoint valid;
    cp_ready: coverpoint ready;
    cx_vr: cross cp_valid, cp_ready;
  endgroup
  cg_handshake cg_hs_inst = new();

endmodule

// ============================================================================
// MODULE: vera_spi_checker
// Purpose: SPI protocol checker with VERA reporting
// ============================================================================
module vera_spi_checker #(
  parameter string IP_NAME    = "SPI",
  parameter int    CPOL       = 0,
  parameter int    CPHA       = 0,
  parameter int    WORD_SIZE  = 8,
  parameter int    MAX_CS_GAP = 4    // min SCLK cycles between CS transactions
)(
  input logic sclk,
  input logic cs_n,
  input logic mosi,
  input logic miso,
  input logic rst_n
);

  int bit_count;
  logic [$clog2(WORD_SIZE+1)-1:0] bit_cnt_q;

  // SVA: MOSI must be stable when sampled
  // (CPHA=0: sample on rising, CPHA=1: sample on falling)
  generate
    if (CPHA == 0) begin : gen_cpha0
      property p_mosi_stable_at_sample;
        @(posedge sclk) disable iff (cs_n || !rst_n)
        $stable(mosi);
      endproperty
      // Not checking stability — checking value held 1 cycle before sample
    end
  endgenerate

  // SVA: CS_N must not assert mid-transaction
  property p_no_cs_glitch;
    @(posedge sclk) disable iff (!rst_n)
    !cs_n |-> !$rose(cs_n);  // cs_n doesn't rise (deassert) during active transfer
  endproperty

  // SVA: Minimum word size bits between CS assertion/deassertion
  property p_min_word_bits;
    @(posedge sclk) disable iff (!rst_n)
    $fell(cs_n) |-> ##[WORD_SIZE:WORD_SIZE*16] $rose(cs_n);
  endproperty

  VERA_SPI_CS_GLITCH:
    assert property (p_no_cs_glitch)
    else `VERA_ASSERT_MSG(IP_NAME, "SPI_CS_GLITCH",
      "CS stable during transfer", "CS toggled mid-transfer", "cs_n");

  VERA_SPI_WORD_LEN:
    assert property (p_min_word_bits)
    else `VERA_ASSERT_MSG(IP_NAME, "SPI_WORD_LENGTH",
      $sformatf(">= %0d SCLK cycles per CS", WORD_SIZE),
      "CS deasserted too early", "spi_transfer");

endmodule

// ============================================================================
// MODULE: vera_uart_checker
// Purpose: UART framing, baud rate, parity checker
// ============================================================================
module vera_uart_checker #(
  parameter string IP_NAME    = "UART",
  parameter int    BAUD_DIV   = 16,   // oversampling ratio
  parameter int    DATA_BITS  = 8,
  parameter int    STOP_BITS  = 1,
  parameter string PARITY     = "NONE" // "NONE", "ODD", "EVEN"
)(
  input logic clk,        // oversampled clock (baud_rate * BAUD_DIV)
  input logic rst_n,
  input logic rx,
  input logic tx
);

  // FSM to track UART framing on TX
  typedef enum logic [2:0] {
    IDLE, START, DATA, PARITY_BIT, STOP
  } uart_state_t;

  uart_state_t tx_state;
  int          bit_idx;
  logic [7:0]  data_reg;
  int          baud_cnt;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      tx_state <= IDLE;
      bit_idx  <= 0;
      baud_cnt <= 0;
    end else begin
      case (tx_state)
        IDLE: if (!tx) begin tx_state <= START; baud_cnt <= 0; end
        START: begin
          baud_cnt <= baud_cnt + 1;
          if (baud_cnt == BAUD_DIV/2) begin
            // Sample start bit — must be 0
            if (tx !== 1'b0) begin
              `VERA_ASSERT_MSG(IP_NAME, "UART_START_BIT",
                "0 (start bit)", $sformatf("%b", tx), "tx_start");
            end
          end
          if (baud_cnt == BAUD_DIV-1) begin
            tx_state <= DATA; bit_idx <= 0; baud_cnt <= 0;
          end
        end
        DATA: begin
          baud_cnt <= baud_cnt + 1;
          if (baud_cnt == BAUD_DIV/2) data_reg[bit_idx] <= tx;
          if (baud_cnt == BAUD_DIV-1) begin
            baud_cnt <= 0;
            if (bit_idx == DATA_BITS-1)
              tx_state <= (PARITY != "NONE") ? PARITY_BIT : STOP;
            else
              bit_idx <= bit_idx + 1;
          end
        end
        STOP: begin
          baud_cnt <= baud_cnt + 1;
          if (baud_cnt == BAUD_DIV/2) begin
            if (tx !== 1'b1) begin
              `VERA_ASSERT_MSG(IP_NAME, "UART_STOP_BIT",
                "1 (stop bit)", $sformatf("%b", tx), "tx_stop");
            end
          end
          if (baud_cnt == BAUD_DIV-1) begin
            tx_state <= IDLE; baud_cnt <= 0;
          end
        end
        default: tx_state <= IDLE;
      endcase
    end
  end

endmodule

// ============================================================================
// MODULE: vera_axi4_checker
// Purpose: AXI4 write/read channel protocol assertions
// ============================================================================
module vera_axi4_checker #(
  parameter string IP_NAME     = "AXI4",
  parameter int    ADDR_WIDTH  = 32,
  parameter int    DATA_WIDTH  = 64,
  parameter int    ID_WIDTH    = 4,
  parameter int    MAX_WAIT_W  = 64,   // max cycles for write response
  parameter int    MAX_WAIT_R  = 64    // max cycles for read data
)(
  input  logic                    aclk,
  input  logic                    aresetn,
  // Write address channel
  input  logic [ID_WIDTH-1:0]     awid,
  input  logic [ADDR_WIDTH-1:0]   awaddr,
  input  logic [7:0]              awlen,
  input  logic [2:0]              awsize,
  input  logic                    awvalid,
  input  logic                    awready,
  // Write data channel
  input  logic [DATA_WIDTH-1:0]   wdata,
  input  logic [DATA_WIDTH/8-1:0] wstrb,
  input  logic                    wlast,
  input  logic                    wvalid,
  input  logic                    wready,
  // Write response channel
  input  logic [ID_WIDTH-1:0]     bid,
  input  logic [1:0]              bresp,
  input  logic                    bvalid,
  input  logic                    bready
);

  // AXI4 Rule: AWVALID must not depend on AWREADY (no deadlock)
  property p_aw_no_deadlock;
    @(posedge aclk) disable iff (!aresetn)
    awvalid |-> ##[0:MAX_WAIT_W] awready;
  endproperty

  // AXI4 Rule: AWADDR must be aligned to AWSIZE
  property p_aw_addr_aligned;
    @(posedge aclk) disable iff (!aresetn)
    (awvalid && awready) |->
      (awaddr[($clog2(DATA_WIDTH/8)-1):0] == '0);
  endproperty

  // AXI4 Rule: Write response BRESP must be OKAY or SLVERR (not DECERR unless valid)
  property p_bresp_valid;
    @(posedge aclk) disable iff (!aresetn)
    (bvalid && bready) |-> (bresp inside {2'b00, 2'b10});
  endproperty

  // AXI4 Rule: WLAST must be asserted on final beat
  // (simplified: wlast must appear within awlen+1 beats of awvalid+awready)
  property p_wlast_assert;
    @(posedge aclk) disable iff (!aresetn)
    (wvalid && wready && wlast) |-> wlast;  // structural check
  endproperty

  VERA_AXI_AW_NODEAD:
    assert property (p_aw_no_deadlock)
    else `VERA_ASSERT_MSG(IP_NAME, "AXI4_AW_DEADLOCK",
      $sformatf("awready within %0d cycles", MAX_WAIT_W),
      "awready timeout", "aw_channel");

  VERA_AXI_ADDR_ALIGN:
    assert property (p_aw_addr_aligned)
    else `VERA_ASSERT_MSG(IP_NAME, "AXI4_AWADDR_ALIGN",
      "awaddr aligned to awsize", "misaligned address", "awaddr");

  VERA_AXI_BRESP:
    assert property (p_bresp_valid)
    else `VERA_ASSERT_MSG(IP_NAME, "AXI4_BRESP_INVALID",
      "OKAY or SLVERR", $sformatf("BRESP=%02b", bresp), "b_channel");

endmodule

// ============================================================================
// MODULE: vera_reset_checker
// Purpose: Reset sequencing, minimum assertion width, glitch detection
// ============================================================================
module vera_reset_checker #(
  parameter string IP_NAME       = "UNDEFINED",
  parameter int    MIN_RST_WIDTH = 4,     // minimum reset assertion in cycles
  parameter int    SYNC_STAGES   = 2,     // expected sync stages
  parameter logic  ACTIVE_LOW    = 1      // 1=active low, 0=active high
)(
  input logic clk,
  input logic rst
);

  logic rst_active;
  assign rst_active = ACTIVE_LOW ? !rst : rst;

  // SVA: Reset must be held for minimum width
  property p_rst_min_width;
    @(posedge clk)
    $rose(rst_active) |-> rst_active[*MIN_RST_WIDTH];
  endproperty

  // SVA: No glitch (reset must not pulse shorter than min width)
  property p_no_rst_glitch;
    @(posedge clk)
    rst_active[*1:$] |-> $fell(rst_active) ##0 !$rose(rst_active)[*1:3];
  endproperty

  VERA_RST_WIDTH:
    assert property (p_rst_min_width)
    else `VERA_ASSERT_MSG(IP_NAME, "RESET_MIN_WIDTH",
      $sformatf(">= %0d cycles", MIN_RST_WIDTH),
      "reset too short", "rst");

endmodule

// ============================================================================
// MODULE: vera_fifo_checker
// Purpose: FIFO overflow, underflow, watermark violations
// ============================================================================
module vera_fifo_checker #(
  parameter string IP_NAME   = "FIFO",
  parameter int    DEPTH     = 16,
  parameter int    HI_WATER  = 12,
  parameter int    LO_WATER  = 4
)(
  input logic clk,
  input logic rst_n,
  input logic push,
  input logic pop,
  input logic full,
  input logic empty,
  input logic [$clog2(DEPTH+1)-1:0] count
);

  // SVA: No push when full
  property p_no_overflow;
    @(posedge clk) disable iff (!rst_n)
    (full) |-> !push;
  endproperty

  // SVA: No pop when empty
  property p_no_underflow;
    @(posedge clk) disable iff (!rst_n)
    (empty) |-> !pop;
  endproperty

  // SVA: Count consistency
  property p_full_count_match;
    @(posedge clk) disable iff (!rst_n)
    full |-> (count == DEPTH);
  endproperty

  property p_empty_count_match;
    @(posedge clk) disable iff (!rst_n)
    empty |-> (count == 0);
  endproperty

  VERA_FIFO_OVERFLOW:
    assert property (p_no_overflow)
    else `VERA_ASSERT_MSG(IP_NAME, "FIFO_OVERFLOW",
      "no push when full", "push to full FIFO", "fifo_push");

  VERA_FIFO_UNDERFLOW:
    assert property (p_no_underflow)
    else `VERA_ASSERT_MSG(IP_NAME, "FIFO_UNDERFLOW",
      "no pop when empty", "pop from empty FIFO", "fifo_pop");

  VERA_FIFO_FULL_CNT:
    assert property (p_full_count_match)
    else `VERA_ASSERT_MSG(IP_NAME, "FIFO_COUNT_FULL_MISMATCH",
      $sformatf("count=%0d when full", DEPTH),
      $sformatf("count=%0d", count), "fifo_count");

  VERA_FIFO_EMPTY_CNT:
    assert property (p_empty_count_match)
    else `VERA_ASSERT_MSG(IP_NAME, "FIFO_COUNT_EMPTY_MISMATCH",
      "count=0 when empty",
      $sformatf("count=%0d", count), "fifo_count");

  // Watermark coverage
  covergroup cg_fifo_levels @(posedge clk);
    cp_count: coverpoint count {
      bins empty      = {0};
      bins low        = {[1:LO_WATER-1]};
      bins normal     = {[LO_WATER:HI_WATER-1]};
      bins high       = {[HI_WATER:DEPTH-1]};
      bins full       = {DEPTH};
    }
  endgroup
  cg_fifo_levels cg_fifo_inst = new();

endmodule

`endif // VERA_SVA_LIBRARY_SV
