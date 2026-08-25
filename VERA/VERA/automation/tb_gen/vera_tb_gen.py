#!/usr/bin/env python3
"""
VERA — Verification Engine for Runtime & Autonomous Checking
FILE: automation/tb_gen/vera_tb_gen.py
DESC: IP-level Testbench Generator.
      Reads VERA spec YAML and generates a complete UVM TB skeleton:
        - Interface (.sv)
        - Sequence item (.sv)
        - Driver (.sv)
        - Monitor (.sv)
        - Scoreboard (bound to vera_scoreboard_base)
        - Agent (.sv)
        - Environment (.sv)
        - Base test (.sv)
        - Top-level TB (.sv)
        - Makefile / compile script
VERSION: 1.0
"""

import os
import yaml
import argparse
from datetime import datetime
from pathlib import Path


HEADER = lambda ip, fname, desc: f"""\
// {'='*72}
// VERA Auto-Generated UVM Testbench
// IP    : {ip}
// File  : {fname}
// Desc  : {desc}
// Gen   : {datetime.now().isoformat()}
// NOTE  : Skeleton — fill in protocol-specific logic
// {'='*72}
"""


class VERATBGenerator:

    def __init__(self, spec_path: str, output_dir: str):
        with open(spec_path) as f:
            self.spec = yaml.safe_load(f)
        self.ip       = self.spec["ip_name"]
        self.ip_lower = self.ip.lower()
        self.ip_type  = self.spec.get("ip_type", "generic").lower()
        self.out      = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_all(self):
        print(f"\n{'='*60}")
        print(f"  VERA TB Generator: {self.ip}")
        print(f"  Output: {self.out}")
        print(f"{'='*60}\n")

        self._gen_interface()
        self._gen_seq_item()
        self._gen_driver()
        self._gen_monitor()
        self._gen_scoreboard()
        self._gen_agent()
        self._gen_env()
        self._gen_base_test()
        self._gen_tb_top()
        self._gen_makefile()
        self._gen_filelist()

        print(f"\n  TB Generation Complete — {self.ip}")
        print(f"  Compile: cd {self.out} && make compile")
        print(f"  Simulate: make sim TEST=vera_{self.ip_lower}_base_test\n")

    # -------------------------------------------------------------------------
    def _gen_interface(self):
        ip  = self.ip
        ipl = self.ip_lower
        clk_mhz = self.spec.get("clock", {}).get("freq_mhz", 100.0)
        period  = 1000.0 / clk_mhz

        content = HEADER(ip, f"vera_{ipl}_if.sv", "DUT Interface") + f"""
interface vera_{ipl}_if (input logic clk, input logic rst_n);

  // ---- Signals (customize for {ip}) ----
  // TODO: Add all DUT port signals here
  logic        enable;
  logic        valid_in;
  logic [7:0]  data_in;
  logic        ready_in;
  logic        valid_out;
  logic [7:0]  data_out;
  logic        ready_out;

  // ---- Clocking Block: Driver (DUT inputs) ----
  clocking driver_cb @(posedge clk);
    default input #1 output #1;
    output enable;
    output valid_in;
    output data_in;
    input  ready_in;
  endclocking

  // ---- Clocking Block: Monitor (DUT outputs) ----
  clocking monitor_cb @(posedge clk);
    default input #1;
    input  valid_in;
    input  data_in;
    input  ready_in;
    input  valid_out;
    input  data_out;
    input  ready_out;
  endclocking

  // ---- Modport definitions ----
  modport driver_mp  (clocking driver_cb,  input clk, rst_n);
  modport monitor_mp (clocking monitor_cb, input clk, rst_n);
  modport dut_mp     (input enable, valid_in, data_in, ready_out,
                      output ready_in, valid_out, data_out);

  // ---- Protocol Assertions (inline, always active) ----
  // Bind vera_{ipl}_sva.sv for full assertion suite

endinterface : vera_{ipl}_if
"""
        self._write(f"vera_{ipl}_if.sv", content)

    # -------------------------------------------------------------------------
    def _gen_seq_item(self):
        ip  = self.ip
        ipl = self.ip_lower
        content = HEADER(ip, f"vera_{ipl}_seq_item.sv", "UVM Sequence Item") + f"""
class vera_{ipl}_seq_item extends uvm_sequence_item;
  `uvm_object_utils_begin(vera_{ipl}_seq_item)
    `uvm_field_int(data,    UVM_ALL_ON)
    `uvm_field_int(valid,   UVM_ALL_ON)
    `uvm_field_int(delay,   UVM_ALL_ON)
  `uvm_object_utils_end

  // ---- Fields ----
  rand logic [7:0] data;
  rand logic       valid;
  rand int unsigned delay;   // inter-transaction delay in cycles

  // ---- Constraints ----
  constraint c_delay {{ delay inside {{[0:8]}}; }}
  constraint c_valid {{ valid dist {{1:=90, 0:=10}}; }}

  function new(string name = "vera_{ipl}_seq_item");
    super.new(name);
  endfunction

  function string convert2string();
    return $sformatf("data=0x%02h valid=%0b delay=%0d", data, valid, delay);
  endfunction

endclass : vera_{ipl}_seq_item
"""
        self._write(f"vera_{ipl}_seq_item.sv", content)

    # -------------------------------------------------------------------------
    def _gen_driver(self):
        ip  = self.ip
        ipl = self.ip_lower
        content = HEADER(ip, f"vera_{ipl}_driver.sv", "UVM Driver") + f"""
class vera_{ipl}_driver extends uvm_driver #(vera_{ipl}_seq_item);
  `uvm_component_utils(vera_{ipl}_driver)

  virtual vera_{ipl}_if.driver_mp vif;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db #(virtual vera_{ipl}_if)::get(this, "", "vif", vif))
      `uvm_fatal(get_name(), "vera_{ipl}_if not found in config_db")
  endfunction

  task run_phase(uvm_phase phase);
    vera_{ipl}_seq_item req;
    // Reset drive
    vif.driver_cb.enable   <= 0;
    vif.driver_cb.valid_in <= 0;
    vif.driver_cb.data_in  <= 0;
    @(posedge vif.rst_n);
    repeat(5) @(vif.driver_cb);

    forever begin
      seq_item_port.get_next_item(req);
      drive_item(req);
      seq_item_port.item_done();
    end
  endtask

  task drive_item(vera_{ipl}_seq_item item);
    // Apply inter-transaction delay
    repeat(item.delay) @(vif.driver_cb);
    // Drive
    vif.driver_cb.valid_in <= item.valid;
    vif.driver_cb.data_in  <= item.data;
    // Wait for handshake
    if (item.valid) begin
      @(vif.driver_cb);
      while (!vif.driver_cb.ready_in) @(vif.driver_cb);
    end
    vif.driver_cb.valid_in <= 0;
  endtask

endclass : vera_{ipl}_driver
"""
        self._write(f"vera_{ipl}_driver.sv", content)

    # -------------------------------------------------------------------------
    def _gen_monitor(self):
        ip  = self.ip
        ipl = self.ip_lower
        content = HEADER(ip, f"vera_{ipl}_monitor.sv", "UVM Monitor") + f"""
class vera_{ipl}_monitor extends uvm_monitor;
  `uvm_component_utils(vera_{ipl}_monitor)

  virtual vera_{ipl}_if.monitor_mp vif;

  // Analysis ports — one for input side, one for output side
  uvm_analysis_port #(vera_{ipl}_seq_item) input_ap;
  uvm_analysis_port #(vera_{ipl}_seq_item) output_ap;

  // VERA result port (connects to scoreboard)
  uvm_analysis_port #(vera_result_item) vera_ap;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    input_ap  = new("input_ap",  this);
    output_ap = new("output_ap", this);
    vera_ap   = new("vera_ap",   this);
    if (!uvm_config_db #(virtual vera_{ipl}_if)::get(this, "", "vif", vif))
      `uvm_fatal(get_name(), "vera_{ipl}_if not found in config_db")
  endfunction

  task run_phase(uvm_phase phase);
    fork
      monitor_input();
      monitor_output();
    join
  endtask

  task monitor_input();
    vera_{ipl}_seq_item item;
    forever begin
      @(vif.monitor_cb);
      if (vif.monitor_cb.valid_in && vif.monitor_cb.ready_in) begin
        item           = vera_{ipl}_seq_item::type_id::create("mon_in");
        item.data      = vif.monitor_cb.data_in;
        item.valid     = 1;
        input_ap.write(item);
      end
    end
  endtask

  task monitor_output();
    vera_{ipl}_seq_item item;
    forever begin
      @(vif.monitor_cb);
      if (vif.monitor_cb.valid_out && vif.monitor_cb.ready_out) begin
        item           = vera_{ipl}_seq_item::type_id::create("mon_out");
        item.data      = vif.monitor_cb.data_out;
        item.valid     = 1;
        output_ap.write(item);
      end
    end
  endtask

endclass : vera_{ipl}_monitor
"""
        self._write(f"vera_{ipl}_monitor.sv", content)

    # -------------------------------------------------------------------------
    def _gen_scoreboard(self):
        ip  = self.ip
        ipl = self.ip_lower
        content = HEADER(ip, f"vera_{ipl}_scoreboard.sv", "VERA Scoreboard") + f"""
`include "vera_scoreboard_base.sv"

// Typedef the base class for this IP's transaction type
typedef vera_scoreboard_base #(
  .T_EXP(vera_{ipl}_seq_item),
  .T_ACT(vera_{ipl}_seq_item)
) vera_{ipl}_sb_base_t;

class vera_{ipl}_scoreboard extends vera_{ipl}_sb_base_t;
  `uvm_component_utils(vera_{ipl}_scoreboard)

  function new(string name, uvm_component parent);
    super.new(name, parent);
    m_ip_name      = "{ip}";
    m_checker_name = "vera_{ipl}_scoreboard";
    m_layer        = "functional";
  endfunction

  // ---- Override: custom comparison logic ----
  virtual function bit compare_items(
    vera_{ipl}_seq_item exp_item,
    vera_{ipl}_seq_item act_item
  );
    // TODO: Add IP-specific comparison. Default: compare data field.
    return (exp_item.data === act_item.data);
  endfunction

  virtual function string get_context(
    vera_{ipl}_seq_item exp_item,
    vera_{ipl}_seq_item act_item
  );
    return $sformatf("exp_data=0x%02h act_data=0x%02h", exp_item.data, act_item.data);
  endfunction

  virtual function string get_debug_signal(vera_{ipl}_seq_item exp_item);
    return "/tb/dut/data_out";
  endfunction

  virtual function string get_recommendation(
    vera_{ipl}_seq_item exp_item,
    vera_{ipl}_seq_item act_item
  );
    return $sformatf(
      "Data mismatch: expected 0x%02h, got 0x%02h. Check DUT datapath.",
      exp_item.data, act_item.data);
  endfunction

endclass : vera_{ipl}_scoreboard
"""
        self._write(f"vera_{ipl}_scoreboard.sv", content)

    # -------------------------------------------------------------------------
    def _gen_agent(self):
        ip  = self.ip
        ipl = self.ip_lower
        content = HEADER(ip, f"vera_{ipl}_agent.sv", "UVM Agent") + f"""
class vera_{ipl}_agent extends uvm_agent;
  `uvm_component_utils(vera_{ipl}_agent)

  vera_{ipl}_driver   m_driver;
  vera_{ipl}_monitor  m_monitor;
  uvm_sequencer #(vera_{ipl}_seq_item) m_sequencer;

  uvm_analysis_port #(vera_{ipl}_seq_item) input_ap;
  uvm_analysis_port #(vera_{ipl}_seq_item) output_ap;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_monitor   = vera_{ipl}_monitor::type_id::create("m_monitor", this);
    if (get_is_active() == UVM_ACTIVE) begin
      m_driver    = vera_{ipl}_driver::type_id::create("m_driver", this);
      m_sequencer = uvm_sequencer #(vera_{ipl}_seq_item)::type_id::create(
                      "m_sequencer", this);
    end
    input_ap  = new("input_ap",  this);
    output_ap = new("output_ap", this);
  endfunction

  function void connect_phase(uvm_phase phase);
    if (get_is_active() == UVM_ACTIVE)
      m_driver.seq_item_port.connect(m_sequencer.seq_item_export);
    m_monitor.input_ap.connect(input_ap);
    m_monitor.output_ap.connect(output_ap);
  endfunction

endclass : vera_{ipl}_agent
"""
        self._write(f"vera_{ipl}_agent.sv", content)

    # -------------------------------------------------------------------------
    def _gen_env(self):
        ip  = self.ip
        ipl = self.ip_lower
        content = HEADER(ip, f"vera_{ipl}_env.sv", "UVM Environment") + f"""
class vera_{ipl}_env extends uvm_env;
  `uvm_component_utils(vera_{ipl}_env)

  vera_{ipl}_agent       m_agent;
  vera_{ipl}_scoreboard  m_scoreboard;
  vera_report_collector  m_vera_collector;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_agent         = vera_{ipl}_agent::type_id::create("m_agent", this);
    m_scoreboard    = vera_{ipl}_scoreboard::type_id::create("m_scoreboard", this);
    m_vera_collector = vera_report_collector::get();

    // Pass IP name to scoreboard via config_db
    uvm_config_db #(string)::set(this, "m_scoreboard", "ip_name", "{ip}");
  endfunction

  function void connect_phase(uvm_phase phase);
    // Connect input monitor → scoreboard expected port
    m_agent.input_ap.connect(m_scoreboard.expected_export);
    // Connect output monitor → scoreboard actual port
    m_agent.output_ap.connect(m_scoreboard.actual_export);
  endfunction

endclass : vera_{ipl}_env
"""
        self._write(f"vera_{ipl}_env.sv", content)

    # -------------------------------------------------------------------------
    def _gen_base_test(self):
        ip  = self.ip
        ipl = self.ip_lower
        content = HEADER(ip, f"vera_{ipl}_base_test.sv", "Base UVM Test") + f"""
class vera_{ipl}_base_test extends uvm_test;
  `uvm_component_utils(vera_{ipl}_base_test)

  vera_{ipl}_env m_env;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_env = vera_{ipl}_env::type_id::create("m_env", this);
    // Configure VERA report file
    uvm_config_db #(string)::set(null, "vera_report_collector",
                                 "report_file", "vera_{ipl}_report.json");
  endfunction

  task run_phase(uvm_phase phase);
    uvm_sequence #(vera_{ipl}_seq_item) seq;
    phase.raise_objection(this);

    // TODO: Replace with IP-specific sequences
    seq = uvm_sequence #(vera_{ipl}_seq_item)::type_id::create("seq");
    seq.start(m_env.m_agent.m_sequencer);

    #1000;
    phase.drop_objection(this);
  endtask

endclass : vera_{ipl}_base_test

// ---- Directed tests ----

class vera_{ipl}_reset_test extends vera_{ipl}_base_test;
  `uvm_component_utils(vera_{ipl}_reset_test)
  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction
  task run_phase(uvm_phase phase);
    phase.raise_objection(this);
    // TODO: Apply reset scenarios
    #5000;
    phase.drop_objection(this);
  endtask
endclass

class vera_{ipl}_stress_test extends vera_{ipl}_base_test;
  `uvm_component_utils(vera_{ipl}_stress_test)
  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction
  task run_phase(uvm_phase phase);
    phase.raise_objection(this);
    // TODO: Back-to-back max rate transactions
    #50000;
    phase.drop_objection(this);
  endtask
endclass
"""
        self._write(f"vera_{ipl}_base_test.sv", content)

    # -------------------------------------------------------------------------
    def _gen_tb_top(self):
        ip  = self.ip
        ipl = self.ip_lower
        clk_mhz = self.spec.get("clock", {}).get("freq_mhz", 100.0)
        period  = int(1000.0 / clk_mhz)
        content = HEADER(ip, f"vera_{ipl}_tb_top.sv", "TB Top") + f"""
`timescale 1ns/1ps

// Include VERA SVA library
`include "vera_sva_library.sv"

module vera_{ipl}_tb_top;

  // ---- DUT signals ----
  logic clk;
  logic rst_n;

  // ---- Clock generation ----
  initial clk = 0;
  always #({period//2}) clk = ~clk;   // {clk_mhz} MHz

  // ---- Reset generation ----
  initial begin
    rst_n = 0;
    repeat(20) @(posedge clk);
    rst_n = 1;
  end

  // ---- Interface instantiation ----
  vera_{ipl}_if u_if (.clk(clk), .rst_n(rst_n));

  // ---- DUT instantiation ----
  // TODO: Replace with actual DUT module
  {ipl}_dut u_dut (
    .clk      (clk),
    .rst_n    (rst_n),
    .enable   (u_if.enable),
    .valid_in (u_if.valid_in),
    .data_in  (u_if.data_in),
    .ready_in (u_if.ready_in),
    .valid_out(u_if.valid_out),
    .data_out (u_if.data_out),
    .ready_out(u_if.ready_out)
  );

  // ---- VERA SVA Bind ----
  // SVA assertions bound non-invasively to DUT
  // vera_{ipl}_sva_bind is auto-generated from vera_builder.py
  // bind {ipl}_dut vera_{ipl}_param_chk i_vera_param (.clk(clk), .rst_n(rst_n), ...);

  // ---- UVM Start ----
  initial begin
    // Register interface in config_db
    uvm_config_db #(virtual vera_{ipl}_if)::set(null, "uvm_test_top.*", "vif", u_if);
    // Run test
    run_test();
  end

  // ---- Waveform Dump ----
  initial begin
    $fsdbDumpfile("vera_{ipl}_sim.fsdb");
    $fsdbDumpvars(0, vera_{ipl}_tb_top);
    $fsdbDumpMDA();
  end

  // ---- Simulation timeout ----
  initial begin
    #10_000_000;
    `uvm_fatal("VERA_TIMEOUT", "Simulation timeout — 10ms exceeded")
  end

endmodule : vera_{ipl}_tb_top
"""
        self._write(f"vera_{ipl}_tb_top.sv", content)

    # -------------------------------------------------------------------------
    def _gen_makefile(self):
        ip  = self.ip
        ipl = self.ip_lower
        content = f"""\
# ============================================================
# VERA Auto-Generated Makefile — {ip}
# ============================================================

SIM     ?= xcelium
TEST    ?= vera_{ipl}_base_test
UVM_HOME ?= $(CDNS_INST_DIR)/tools/methodology/UVM/CDNS-1.2d/sv
VERA_HOME ?= ../../..

SRCS = \\
  $(VERA_HOME)/core/sv/vera_sva_library.sv \\
  $(VERA_HOME)/core/uvm/vera_scoreboard_base.sv \\
  vera_{ipl}_if.sv \\
  vera_{ipl}_seq_item.sv \\
  vera_{ipl}_driver.sv \\
  vera_{ipl}_monitor.sv \\
  vera_{ipl}_scoreboard.sv \\
  vera_{ipl}_agent.sv \\
  vera_{ipl}_env.sv \\
  vera_{ipl}_base_test.sv \\
  vera_{ipl}_tb_top.sv

.PHONY: compile sim clean

compile:
ifeq ($(SIM),xcelium)
	xrun -compile -64bit -sv -uvm $(SRCS) -top vera_{ipl}_tb_top
else ifeq ($(SIM),vcs)
	vcs -full64 -sverilog -ntb_opts uvm-1.2 $(SRCS) -top vera_{ipl}_tb_top -o simv
else ifeq ($(SIM),questa)
	vlog -sv $(SRCS) && vopt vera_{ipl}_tb_top -o opt_tb
endif

sim:
ifeq ($(SIM),xcelium)
	xrun -64bit -sv -uvm $(SRCS) -top vera_{ipl}_tb_top \\
	  +UVM_TESTNAME=$(TEST) +UVM_VERBOSITY=UVM_MEDIUM \\
	  -vera_report vera_{ipl}_report.json
else ifeq ($(SIM),vcs)
	./simv +UVM_TESTNAME=$(TEST) +UVM_VERBOSITY=UVM_MEDIUM
else ifeq ($(SIM),questa)
	vsim -c opt_tb +UVM_TESTNAME=$(TEST) -do "run -all; quit"
endif

postsim:
	python3 $(VERA_HOME)/core/python/vera_postsim_engine.py \\
	  --spec ../{ipl}_spec.yaml \\
	  --data sim_data.csv \\
	  --report vera_{ipl}_postsim_report.json

waveload:
	python3 $(VERA_HOME)/automation/waveform_loader/vera_waveload.py \\
	  --report vera_{ipl}_report.json \\
	  --tool simvision \\
	  --output debug_scripts/

clean:
	rm -rf xcelium.d simv csrc DVEfiles *.log *.vcd *.fsdb
	rm -rf vera_*_report.json debug_scripts/ INCA_libs
"""
        self._write("Makefile", content)

    # -------------------------------------------------------------------------
    def _gen_filelist(self):
        ipl = self.ip_lower
        content = f"""\
# VERA Auto-Generated File List — {self.ip}
# Use with: xrun -f vera_{ipl}_filelist.f
../../core/sv/vera_sva_library.sv
../../core/uvm/vera_scoreboard_base.sv
vera_{ipl}_if.sv
vera_{ipl}_seq_item.sv
vera_{ipl}_driver.sv
vera_{ipl}_monitor.sv
vera_{ipl}_scoreboard.sv
vera_{ipl}_agent.sv
vera_{ipl}_env.sv
vera_{ipl}_base_test.sv
vera_{ipl}_tb_top.sv
"""
        self._write(f"vera_{ipl}_filelist.f", content)

    # -------------------------------------------------------------------------
    def _write(self, filename: str, content: str):
        path = os.path.join(self.out, filename)
        with open(path, "w") as f:
            f.write(content)
        print(f"  [VERA TB Gen] {filename}")


# =============================================================================
# CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="VERA TB Generator: Auto-generate UVM TB from IP spec YAML")
    parser.add_argument("--spec",   required=True, help="IP spec YAML")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()

    gen = VERATBGenerator(args.spec, args.output)
    gen.generate_all()


if __name__ == "__main__":
    main()
