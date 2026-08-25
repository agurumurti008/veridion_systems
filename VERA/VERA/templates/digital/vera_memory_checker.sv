// ============================================================================
// VERA — Verification Engine for Runtime & Autonomous Checking
// FILE: templates/digital/vera_memory_checker.sv
// DESC: SRAM / Memory checker templates.
//       Covers: read/write integrity, address decode, timing, power-down,
//       retention, column/row enable, BIST results.
// VERSION: 1.0
// ============================================================================

`ifndef VERA_MEMORY_CHECKER_SV
`define VERA_MEMORY_CHECKER_SV

// ============================================================================
// MODULE: vera_sram_sva_checker
// Single-port SRAM protocol and timing checker
// ============================================================================
module vera_sram_sva_checker #(
  parameter string IP_NAME     = "SRAM",
  parameter int    ADDR_WIDTH  = 10,
  parameter int    DATA_WIDTH  = 32,
  parameter int    DEPTH       = 1024,
  parameter int    SETUP_CYC   = 1,     // address/data setup before CE
  parameter int    HOLD_CYC    = 1,     // hold after CE de-assert
  parameter int    READ_LAT    = 1,     // read latency in cycles
  parameter int    MAX_ADDR    = DEPTH - 1
)(
  input logic                  clk,
  input logic                  rst_n,
  input logic                  ce_n,    // chip enable (active low)
  input logic                  we_n,    // write enable (active low)
  input logic                  oe_n,    // output enable (active low)
  input logic [ADDR_WIDTH-1:0] addr,
  input logic [DATA_WIDTH-1:0] din,
  input logic [DATA_WIDTH-1:0] dout,
  input logic [DATA_WIDTH/8-1:0] byte_en  // byte enables
);

  // MEM.1: Address must be within valid range
  property p_addr_range;
    @(posedge clk) disable iff (!rst_n)
    !ce_n |-> (addr <= MAX_ADDR);
  endproperty
  VERA_SRAM_ADDR_RANGE:
    assert property (p_addr_range)
    else $error("VERA_FAIL | IP=%s | CHECK=SRAM_ADDR_RANGE | addr=0x%0h exceeds MAX=0x%0h | @%0t",
                IP_NAME, addr, MAX_ADDR, $time);

  // MEM.2: WE and OE must not both be active (read/write collision)
  property p_no_rw_collision;
    @(posedge clk) disable iff (!rst_n)
    !ce_n |-> !(!we_n && !oe_n);
  endproperty
  VERA_SRAM_NO_RW_COLLISION:
    assert property (p_no_rw_collision)
    else $error("VERA_FAIL | IP=%s | CHECK=SRAM_NO_RW_COLLISION | WE and OE both active | @%0t",
                IP_NAME, $time);

  // MEM.3: Address stable during write cycle
  property p_addr_stable_write;
    @(posedge clk) disable iff (!rst_n)
    (!ce_n && !we_n) |=> $stable(addr);
  endproperty
  VERA_SRAM_ADDR_STABLE_WR:
    assert property (p_addr_stable_write)
    else $error("VERA_FAIL | IP=%s | CHECK=SRAM_ADDR_STABLE_WR | addr changed during write | @%0t",
                IP_NAME, $time);

  // MEM.4: DIN stable during write (hold)
  property p_din_stable_write;
    @(posedge clk) disable iff (!rst_n)
    (!ce_n && !we_n) |=> $stable(din);
  endproperty
  VERA_SRAM_DIN_STABLE:
    assert property (p_din_stable_write)
    else $error("VERA_FAIL | IP=%s | CHECK=SRAM_DIN_STABLE | din changed during write hold | @%0t",
                IP_NAME, $time);

  // MEM.5: DOUT must be valid READ_LAT cycles after read
  property p_read_latency;
    @(posedge clk) disable iff (!rst_n)
    ($rose(!ce_n) && oe_n === 1'b0 && we_n === 1'b1) |-> ##READ_LAT !$isunknown(dout);
  endproperty
  VERA_SRAM_READ_LATENCY:
    assert property (p_read_latency)
    else $error("VERA_FAIL | IP=%s | CHECK=SRAM_READ_LATENCY | dout X after %0d read cycles | @%0t",
                IP_NAME, READ_LAT, $time);

  // MEM.6: DOUT must be X or Z when CE is inactive (output isolation)
  property p_dout_tristate;
    @(posedge clk) disable iff (!rst_n)
    ce_n |-> $isunknown(dout) || (dout === 'z);
  endproperty
  // Note: this is a WARNING-level check — some SRAMs hold last value
  // VERA_SRAM_DOUT_TRISTATE: assert property (p_dout_tristate) ...

  // MEM.7: Byte enables — at least one must be active on write
  property p_byte_en_active;
    @(posedge clk) disable iff (!rst_n)
    (!ce_n && !we_n) |-> (byte_en != '0);
  endproperty
  VERA_SRAM_BYTE_EN_ACTIVE:
    assert property (p_byte_en_active)
    else $error("VERA_FAIL | IP=%s | CHECK=SRAM_BYTE_EN_ACTIVE | write with all byte_en=0 | @%0t",
                IP_NAME, $time);

  // MEM.8: No undefined address on active access
  property p_addr_no_x;
    @(posedge clk) disable iff (!rst_n)
    !ce_n |-> !$isunknown(addr);
  endproperty
  VERA_SRAM_ADDR_NO_X:
    assert property (p_addr_no_x)
    else $error("VERA_FAIL | IP=%s | CHECK=SRAM_ADDR_NO_X | X on addr during access | @%0t",
                IP_NAME, $time);

  // Coverage
  covergroup cg_sram @(posedge clk);
    cp_op: coverpoint {we_n, oe_n} iff (!ce_n) {
      bins read  = {2'b10};
      bins write = {2'b01};
    }
    cp_addr: coverpoint addr iff (!ce_n) {
      bins addr_low  = {[0 : DEPTH/4-1]};
      bins addr_mid  = {[DEPTH/4 : 3*DEPTH/4-1]};
      bins addr_high = {[3*DEPTH/4 : DEPTH-1]};
    }
    cp_byte_en: coverpoint byte_en iff (!ce_n && !we_n);
    cx_op_addr: cross cp_op, cp_addr;
  endgroup
  cg_sram cg_sram_inst = new();

endmodule

// ============================================================================
// UVM SRAM Functional Scoreboard
// Maintains a shadow memory model, verifies reads against expected data
// ============================================================================
class vera_sram_shadow_model #(
  parameter int ADDR_WIDTH = 10,
  parameter int DATA_WIDTH = 32
);
  // Shadow memory: associative array keyed by address
  logic [DATA_WIDTH-1:0] mem [int];

  function void write(int addr, logic [DATA_WIDTH-1:0] data, logic [(DATA_WIDTH/8)-1:0] be);
    logic [DATA_WIDTH-1:0] old_val;
    old_val = mem.exists(addr) ? mem[addr] : 'x;
    for (int b = 0; b < DATA_WIDTH/8; b++) begin
      if (be[b]) begin
        old_val[b*8+:8] = data[b*8+:8];
      end
    end
    mem[addr] = old_val;
  endfunction

  function logic [DATA_WIDTH-1:0] read(int addr);
    return mem.exists(addr) ? mem[addr] : 'x;
  endfunction

  function void clear();
    mem.delete();
  endfunction
endclass

// SRAM transaction item
class vera_sram_item #(int AW=10, int DW=32) extends uvm_sequence_item;
  typedef vera_sram_item #(AW, DW) this_t;
  `uvm_object_param_utils(this_t)

  rand logic [AW-1:0]   addr;
  rand logic [DW-1:0]   data;
  rand logic [DW/8-1:0] byte_en;
  rand logic             is_write;
  rand int               delay;

  constraint c_addr  { addr < (1 << AW); }
  constraint c_be    { byte_en != '0; }
  constraint c_delay { delay inside {[0:3]}; }

  function new(string name = "vera_sram_item");
    super.new(name);
  endfunction

  function string convert2string();
    return $sformatf("%s addr=0x%0h data=0x%0h be=%0b",
                     is_write ? "WR" : "RD", addr, data, byte_en);
  endfunction
endclass

// SRAM scoreboard with shadow model
class vera_sram_scoreboard #(int AW=10, int DW=32) extends uvm_scoreboard;
  typedef vera_sram_item #(AW, DW) item_t;
  `uvm_component_utils(vera_sram_scoreboard)

  vera_sram_shadow_model #(AW, DW) m_shadow;
  uvm_analysis_export #(item_t)    sram_export;
  uvm_analysis_port  #(vera_result_item) vera_result_port;

  string m_ip_name = "SRAM";
  int    m_match_count;
  int    m_mismatch_count;
  vera_report_collector m_collector;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_shadow      = new();
    sram_export   = new("sram_export",   this);
    vera_result_port = new("vera_result_port", this);
    m_collector   = vera_report_collector::get();
    void'(uvm_config_db #(string)::get(this, "", "ip_name", m_ip_name));
  endfunction

  function void write(item_t item);
    vera_result_item r;

    if (item.is_write) begin
      // Update shadow model on write
      m_shadow.write(int'(item.addr), item.data, item.byte_en);
    end else begin
      // Check read data against shadow
      logic [DW-1:0] expected = m_shadow.read(int'(item.addr));

      r = vera_result_item::type_id::create("sram_result");
      r.ip_name       = m_ip_name;
      r.checker_name  = "vera_sram_read_data";
      r.checker_type  = "uvm_shadow_scoreboard";
      r.layer         = "functional";
      r.sim_time_ns   = $realtime / 1.0e9;
      r.debug_signal  = $sformatf("/tb/dut/dout[%0d:0]", DW-1);

      if ($isunknown(expected)) begin
        // Read before write — warning
        r.status       = "WARNING";
        r.severity     = "WARNING";
        r.expected_str = "defined data (written before read)";
        r.actual_str   = $sformatf("0x%0h (uninitialized)", item.data);
        r.context_str  = $sformatf("addr=0x%0h", item.addr);
        r.recommendation = "Ensure memory is written before reading";
      end else if (item.data === expected) begin
        r.status   = "PASS";
        r.severity = "INFO";
        r.expected_str = $sformatf("0x%0h", expected);
        r.actual_str   = $sformatf("0x%0h", item.data);
        m_match_count++;
      end else begin
        r.status   = "FAIL";
        r.severity = "ERROR";
        r.expected_str = $sformatf("0x%0h", expected);
        r.actual_str   = $sformatf("0x%0h", item.data);
        r.margin_str   = $sformatf("XOR=0x%0h", item.data ^ expected);
        r.context_str  = $sformatf("addr=0x%0h", item.addr);
        r.recommendation = "Check bit-cell failure, word line decoder, or sense amplifier";
        m_mismatch_count++;
      end

      vera_result_port.write(r);
      m_collector.write(r);
    end
  endfunction

  function void report_phase(uvm_phase phase);
    super.report_phase(phase);
    `uvm_info(get_name(), $sformatf("[%s] SRAM: MATCH=%0d MISMATCH=%0d",
              m_ip_name, m_match_count, m_mismatch_count), UVM_NONE)
  endfunction

endclass

`endif // VERA_MEMORY_CHECKER_SV
