// ============================================================================
// VERA — Verification Engine for Runtime & Autonomous Checking
// FILE: core/sv/vera_apb_ahb_checkers.sv
// DESC: APB3/APB4 and AHB-Lite protocol checkers.
//       Fully parameterized, VERA-tagged, bind-ready.
// VERSION: 1.0
// REF: ARM IHI0024C (APB), ARM IHI0033B (AHB-Lite)
// ============================================================================

`ifndef VERA_APB_AHB_CHECKERS_SV
`define VERA_APB_AHB_CHECKERS_SV

// ============================================================================
// MODULE: vera_apb_checker
// Covers: APB3 & APB4 (PSTRB, PPROT extensions)
// ============================================================================
module vera_apb_checker #(
  parameter string IP_NAME        = "APB",
  parameter int    ADDR_WIDTH     = 32,
  parameter int    DATA_WIDTH     = 32,
  parameter int    MAX_SETUP_CYC  = 1,    // APB spec: exactly 1 SETUP cycle
  parameter int    MAX_ACCESS_CYC = 16,   // max cycles in ACCESS state
  parameter bit    APB4_ENABLE    = 1     // 1=APB4 (PSTRB/PPROT), 0=APB3
)(
  input logic                   pclk,
  input logic                   presetn,
  input logic [ADDR_WIDTH-1:0]  paddr,
  input logic                   psel,
  input logic                   penable,
  input logic                   pwrite,
  input logic [DATA_WIDTH-1:0]  pwdata,
  input logic [DATA_WIDTH/8-1:0] pstrb,
  input logic [2:0]             pprot,
  input logic [DATA_WIDTH-1:0]  prdata,
  input logic                   pready,
  input logic                   pslverr
);

  // FSM state tracking
  typedef enum logic [1:0] { APB_IDLE, APB_SETUP, APB_ACCESS } apb_state_t;
  apb_state_t state;
  int         access_count;

  always_ff @(posedge pclk or negedge presetn) begin
    if (!presetn) begin
      state        <= APB_IDLE;
      access_count <= 0;
    end else begin
      case (state)
        APB_IDLE:   if (psel && !penable) begin state <= APB_SETUP; access_count <= 0; end
        APB_SETUP:  if (psel &&  penable) begin state <= APB_ACCESS; end
                    else if (!psel)       begin state <= APB_IDLE; end
        APB_ACCESS: if (pready) begin
                      state <= psel ? APB_SETUP : APB_IDLE;
                      access_count <= 0;
                    end else access_count <= access_count + 1;
        default:    state <= APB_IDLE;
      endcase
    end
  end

  // APB.1: PENABLE must come exactly 1 cycle after PSEL in SETUP
  property p_setup_to_enable;
    @(posedge pclk) disable iff (!presetn)
    (psel && !penable) |=> (psel && penable);
  endproperty
  VERA_APB_SETUP_TO_ENABLE:
    assert property (p_setup_to_enable)
    else $error("VERA_FAIL | IP=%s | CHECK=APB_SETUP_TO_ENABLE | PENABLE not raised after 1 cycle of PSEL | @%0t",
                IP_NAME, $time);

  // APB.2: PADDR must be stable during ACCESS phase
  property p_addr_stable_access;
    @(posedge pclk) disable iff (!presetn)
    (psel && penable && !pready) |=> $stable(paddr);
  endproperty
  VERA_APB_ADDR_STABLE:
    assert property (p_addr_stable_access)
    else $error("VERA_FAIL | IP=%s | CHECK=APB_ADDR_STABLE | paddr changed during ACCESS phase | @%0t",
                IP_NAME, $time);

  // APB.3: PWRITE must be stable during ACCESS phase
  property p_write_stable_access;
    @(posedge pclk) disable iff (!presetn)
    (psel && penable && !pready) |=> $stable(pwrite);
  endproperty
  VERA_APB_WRITE_STABLE:
    assert property (p_write_stable_access)
    else $error("VERA_FAIL | IP=%s | CHECK=APB_WRITE_STABLE | pwrite changed during ACCESS phase | @%0t",
                IP_NAME, $time);

  // APB.4: PWDATA must be stable during ACCESS write
  property p_wdata_stable;
    @(posedge pclk) disable iff (!presetn)
    (psel && penable && pwrite && !pready) |=> $stable(pwdata);
  endproperty
  VERA_APB_WDATA_STABLE:
    assert property (p_wdata_stable)
    else $error("VERA_FAIL | IP=%s | CHECK=APB_WDATA_STABLE | pwdata changed during write ACCESS | @%0t",
                IP_NAME, $time);

  // APB.5: PENABLE must not be asserted without PSEL
  property p_enable_after_sel;
    @(posedge pclk) disable iff (!presetn)
    penable |-> psel;
  endproperty
  VERA_APB_ENABLE_AFTER_SEL:
    assert property (p_enable_after_sel)
    else $error("VERA_FAIL | IP=%s | CHECK=APB_ENABLE_AFTER_SEL | PENABLE without PSEL | @%0t",
                IP_NAME, $time);

  // APB.6: ACCESS state timeout
  property p_access_timeout;
    @(posedge pclk) disable iff (!presetn)
    (psel && penable) |-> ##[0:MAX_ACCESS_CYC] pready;
  endproperty
  VERA_APB_ACCESS_TIMEOUT:
    assert property (p_access_timeout)
    else $error("VERA_FAIL | IP=%s | CHECK=APB_ACCESS_TIMEOUT | pready not seen within %0d cycles | @%0t",
                IP_NAME, MAX_ACCESS_CYC, $time);

  // APB.7: PSTRB only valid on write (APB4)
  generate
    if (APB4_ENABLE) begin : gen_apb4
      property p_strb_on_write_only;
        @(posedge pclk) disable iff (!presetn)
        (psel && penable && !pwrite) |-> (pstrb == '0);
      endproperty
      VERA_APB4_STRB_WRITE_ONLY:
        assert property (p_strb_on_write_only)
        else $error("VERA_FAIL | IP=%s | CHECK=APB4_STRB_WRITE_ONLY | pstrb non-zero on read | @%0t",
                    IP_NAME, $time);
    end
  endgenerate

  // APB.8: Reset compliance
  property p_rst_idle;
    @(posedge pclk)
    !presetn |-> (!psel && !penable);
  endproperty
  VERA_APB_RST_IDLE:
    assert property (p_rst_idle)
    else $error("VERA_FAIL | IP=%s | CHECK=APB_RST_IDLE | psel/penable active during reset | @%0t",
                IP_NAME, $time);

  // Coverage
  covergroup cg_apb @(posedge pclk);
    cp_pwrite: coverpoint pwrite iff (psel && penable && pready);
    cp_pslverr: coverpoint pslverr iff (psel && penable && pready);
    cp_phase: coverpoint state;
    cx_rw_err: cross cp_pwrite, cp_pslverr;
  endgroup
  cg_apb cg_apb_inst = new();

endmodule

// ============================================================================
// MODULE: vera_ahb_checker
// Covers: AHB-Lite protocol
// REF: ARM IHI0033B
// ============================================================================
module vera_ahb_checker #(
  parameter string IP_NAME       = "AHB",
  parameter int    ADDR_WIDTH    = 32,
  parameter int    DATA_WIDTH    = 32,
  parameter int    MAX_WAIT_CYC  = 16
)(
  input logic                   hclk,
  input logic                   hresetn,
  // Master outputs
  input logic [ADDR_WIDTH-1:0]  haddr,
  input logic [2:0]             hburst,
  input logic [3:0]             hprot,
  input logic [2:0]             hsize,
  input logic [1:0]             htrans,
  input logic [DATA_WIDTH-1:0]  hwdata,
  input logic                   hwrite,
  // Slave outputs
  input logic [DATA_WIDTH-1:0]  hrdata,
  input logic                   hreadyout,
  input logic                   hresp,
  // Mux
  input logic                   hsel,
  input logic                   hready
);

  // HTRANS encodings
  localparam IDLE   = 2'b00;
  localparam BUSY   = 2'b01;
  localparam NONSEQ = 2'b10;
  localparam SEQ    = 2'b11;

  // HBURST encodings
  localparam SINGLE = 3'b000;
  localparam INCR   = 3'b001;

  int wait_count;
  always_ff @(posedge hclk or negedge hresetn) begin
    if (!hresetn) wait_count <= 0;
    else if (hsel && !hreadyout) wait_count <= wait_count + 1;
    else wait_count <= 0;
  end

  // AHB.1: HADDR must be stable during wait states
  property p_haddr_stable_wait;
    @(posedge hclk) disable iff (!hresetn)
    (hsel && !hreadyout) |=> $stable(haddr);
  endproperty
  VERA_AHB_ADDR_STABLE:
    assert property (p_haddr_stable_wait)
    else $error("VERA_FAIL | IP=%s | CHECK=AHB_ADDR_STABLE | haddr changed during wait state | @%0t",
                IP_NAME, $time);

  // AHB.2: HTRANS must not be SEQ without prior NONSEQ
  property p_seq_after_nonseq;
    @(posedge hclk) disable iff (!hresetn)
    (htrans == SEQ) |-> $past(htrans inside {NONSEQ, SEQ});
  endproperty
  VERA_AHB_SEQ_AFTER_NONSEQ:
    assert property (p_seq_after_nonseq)
    else $error("VERA_FAIL | IP=%s | CHECK=AHB_SEQ_AFTER_NONSEQ | SEQ without prior NONSEQ/SEQ | @%0t",
                IP_NAME, $time);

  // AHB.3: HSIZE must not exceed bus width
  property p_hsize_max;
    @(posedge hclk) disable iff (!hresetn)
    (htrans != IDLE && hsel) |-> (hsize <= $clog2(DATA_WIDTH/8));
  endproperty
  VERA_AHB_SIZE_MAX:
    assert property (p_hsize_max)
    else $error("VERA_FAIL | IP=%s | CHECK=AHB_SIZE_MAX | hsize=%0d exceeds data bus | @%0t",
                IP_NAME, hsize, $time);

  // AHB.4: Slave must not hold HREADY low too long
  property p_wait_timeout;
    @(posedge hclk) disable iff (!hresetn)
    (hsel && htrans != IDLE && !hreadyout) |-> ##[1:MAX_WAIT_CYC] hreadyout;
  endproperty
  VERA_AHB_WAIT_TIMEOUT:
    assert property (p_wait_timeout)
    else $error("VERA_FAIL | IP=%s | CHECK=AHB_WAIT_TIMEOUT | slave held HREADY low > %0d cycles | @%0t",
                IP_NAME, MAX_WAIT_CYC, $time);

  // AHB.5: HRESP ERROR must be two-cycle response
  property p_hresp_two_cycle;
    @(posedge hclk) disable iff (!hresetn)
    (hresp && !hreadyout) |=> (hresp && hreadyout);
  endproperty
  VERA_AHB_HRESP_TWO_CYCLE:
    assert property (p_hresp_two_cycle)
    else $error("VERA_FAIL | IP=%s | CHECK=AHB_HRESP_TWO_CYCLE | ERROR response not 2-cycle | @%0t",
                IP_NAME, $time);

  // AHB.6: HWRITE stable during address phase
  property p_hwrite_stable;
    @(posedge hclk) disable iff (!hresetn)
    (hsel && !hreadyout && htrans != IDLE) |=> $stable(hwrite);
  endproperty
  VERA_AHB_WRITE_STABLE:
    assert property (p_hwrite_stable)
    else $error("VERA_FAIL | IP=%s | CHECK=AHB_WRITE_STABLE | hwrite changed during wait | @%0t",
                IP_NAME, $time);

  // AHB.7: Reset compliance
  property p_rst_idle;
    @(posedge hclk)
    !hresetn |-> (htrans == IDLE);
  endproperty
  VERA_AHB_RST_IDLE:
    assert property (p_rst_idle)
    else $error("VERA_FAIL | IP=%s | CHECK=AHB_RST_IDLE | htrans not IDLE during reset | @%0t",
                IP_NAME, $time);

  // Coverage
  covergroup cg_ahb @(posedge hclk);
    cp_htrans: coverpoint htrans {
      bins idle  = {IDLE};
      bins busy  = {BUSY};
      bins nonseq = {NONSEQ};
      bins seq    = {SEQ};
    }
    cp_hburst: coverpoint hburst;
    cp_hwrite: coverpoint hwrite iff (htrans == NONSEQ && hsel && hreadyout);
    cp_hresp:  coverpoint hresp  iff (hreadyout);
  endgroup
  cg_ahb cg_ahb_inst = new();

endmodule

// ============================================================================
// MODULE: vera_i2c_checker
// Covers: I2C protocol (START, STOP, ACK, address, data framing)
// ============================================================================
module vera_i2c_checker #(
  parameter string IP_NAME    = "I2C",
  parameter int    ADDR_BITS  = 7,       // 7 or 10-bit addressing
  parameter int    MAX_STRETCH_US = 25   // max clock stretch in us (not cycles)
)(
  input logic sda,
  input logic scl,
  input logic clk,      // fast reference clock for timing measurement
  input logic rst_n
);

  // Detect START condition: SDA falls while SCL is high
  logic start_det, stop_det;
  logic sda_dly, scl_dly;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      sda_dly <= 1; scl_dly <= 1;
    end else begin
      sda_dly <= sda;
      scl_dly <= scl;
    end
  end

  assign start_det = scl && scl_dly && sda_dly && !sda;   // SCL high, SDA fall
  assign stop_det  = scl && scl_dly && !sda_dly && sda;   // SCL high, SDA rise

  // I2C.1: SDA must not change while SCL is high (except START/STOP)
  property p_sda_stable_scl_high;
    @(posedge clk) disable iff (!rst_n)
    (scl && scl_dly && !start_det && !stop_det) |=> $stable(sda);
  endproperty
  VERA_I2C_SDA_STABLE:
    assert property (p_sda_stable_scl_high)
    else $error("VERA_FAIL | IP=%s | CHECK=I2C_SDA_STABLE | SDA changed while SCL high (not START/STOP) | @%0t",
                IP_NAME, $time);

  // I2C.2: SCL must have valid high time (not glitch)
  property p_scl_no_glitch;
    @(posedge clk) disable iff (!rst_n)
    $rose(scl) |-> scl[*4];    // SCL must stay high for at least 4 fast clocks
  endproperty
  VERA_I2C_SCL_GLITCH:
    assert property (p_scl_no_glitch)
    else $error("VERA_FAIL | IP=%s | CHECK=I2C_SCL_GLITCH | SCL glitch — high time too short | @%0t",
                IP_NAME, $time);

  // I2C.3: START must be followed by SCL low (data phase begins)
  property p_start_then_scl_low;
    @(posedge clk) disable iff (!rst_n)
    start_det |-> ##[1:10] !scl;
  endproperty
  VERA_I2C_START_SCL_LOW:
    assert property (p_start_then_scl_low)
    else $error("VERA_FAIL | IP=%s | CHECK=I2C_START_SCL_LOW | SCL did not go low after START | @%0t",
                IP_NAME, $time);

  // Coverage
  covergroup cg_i2c @(posedge clk);
    cp_start: coverpoint start_det;
    cp_stop:  coverpoint stop_det;
    cp_scl:   coverpoint scl;
    cp_sda:   coverpoint sda;
  endgroup
  cg_i2c cg_i2c_inst = new();

endmodule

`endif // VERA_APB_AHB_CHECKERS_SV
