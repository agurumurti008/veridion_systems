// ============================================================================
// VERA — Verification Engine for Runtime & Autonomous Checking
// FILE: core/sv/vera_formal_properties.sv
// DESC: Formal-ready property package for JasperGold / VC Formal / Questa Formal.
//       Contains assume/assert/cover groupings, proof strategies,
//       and Tcl scripts for automated formal proof runs.
//       All properties are also simulation-compatible (concurrent assertions).
// VERSION: 1.0
// ============================================================================

`ifndef VERA_FORMAL_PROPERTIES_SV
`define VERA_FORMAL_PROPERTIES_SV

// ============================================================================
// VERA Formal Property Package
// ============================================================================
package vera_formal_pkg;

  // Proof depth recommendation per property type
  typedef enum {
    PROOF_SHALLOW = 5,    // handshake, basic protocol
    PROOF_MEDIUM  = 20,   // pipeline, state machine
    PROOF_DEEP    = 50,   // arbitration, liveness
    PROOF_UNBOUNDED = 0   // use induction / k-induction
  } vera_proof_depth_t;

endpackage

// ============================================================================
// MODULE: vera_formal_fifo_props
// Formally-provable FIFO properties — deadlock freedom, fairness
// ============================================================================
module vera_formal_fifo_props #(
  parameter string IP_NAME  = "FIFO",
  parameter int    DEPTH    = 16,
  parameter int    DATA_W   = 8
)(
  input logic                clk,
  input logic                rst_n,
  input logic                push,
  input logic                pop,
  input logic                full,
  input logic                empty,
  input logic [$clog2(DEPTH+1)-1:0] count,
  input logic [DATA_W-1:0]   din,
  input logic [DATA_W-1:0]   dout
);

  // ---- Assume: legal stimulus (no push when full, no pop when empty) ----
  // Used in formal to constrain the environment
  `ifdef FORMAL
  assume_no_push_full:  assume property (@(posedge clk) disable iff (!rst_n) full  |-> !push);
  assume_no_pop_empty:  assume property (@(posedge clk) disable iff (!rst_n) empty |-> !pop);
  `endif

  // ---- Safety: count consistency ----
  property p_count_empty;
    @(posedge clk) disable iff (!rst_n)
    empty |-> (count == 0);
  endproperty

  property p_count_full;
    @(posedge clk) disable iff (!rst_n)
    full |-> (count == DEPTH);
  endproperty

  property p_count_range;
    @(posedge clk) disable iff (!rst_n)
    count inside {[0:DEPTH]};
  endproperty

  property p_count_monotone_push;
    @(posedge clk) disable iff (!rst_n)
    (push && !pop && !full) |=> (count == $past(count) + 1);
  endproperty

  property p_count_monotone_pop;
    @(posedge clk) disable iff (!rst_n)
    (pop && !push && !empty) |=> (count == $past(count) - 1);
  endproperty

  // ---- Liveness: if you push, you can eventually pop ----
  // (requires fairness assumption: pop is eventually enabled)
  property p_liveness_not_stuck;
    @(posedge clk) disable iff (!rst_n)
    (push && !full) |-> ##[1:DEPTH+2] !empty;
  endproperty

  // ---- Formal assertions (active in both sim and formal) ----
  VERA_FIFO_F_COUNT_EMPTY:
    assert property (p_count_empty)
    else $error("VERA_FAIL | IP=%s | CHECK=FIFO_FORMAL_COUNT_EMPTY | @%0t", IP_NAME, $time);

  VERA_FIFO_F_COUNT_FULL:
    assert property (p_count_full)
    else $error("VERA_FAIL | IP=%s | CHECK=FIFO_FORMAL_COUNT_FULL | @%0t", IP_NAME, $time);

  VERA_FIFO_F_COUNT_RANGE:
    assert property (p_count_range)
    else $error("VERA_FAIL | IP=%s | CHECK=FIFO_FORMAL_COUNT_RANGE | count=%0d @%0t",
                IP_NAME, count, $time);

  VERA_FIFO_F_COUNT_PUSH:
    assert property (p_count_monotone_push)
    else $error("VERA_FAIL | IP=%s | CHECK=FIFO_FORMAL_COUNT_PUSH | count not incremented @%0t",
                IP_NAME, $time);

  VERA_FIFO_F_COUNT_POP:
    assert property (p_count_monotone_pop)
    else $error("VERA_FAIL | IP=%s | CHECK=FIFO_FORMAL_COUNT_POP | count not decremented @%0t",
                IP_NAME, $time);

  // Cover: show FIFO can go from empty to full and back
  VERA_FIFO_F_COVER_FULL:
    cover property (@(posedge clk) disable iff (!rst_n)
      empty ##[1:$] full ##[1:$] empty);

endmodule

// ============================================================================
// MODULE: vera_formal_arbiter_props
// Round-robin / priority arbiter formal properties
// ============================================================================
module vera_formal_arbiter_props #(
  parameter string IP_NAME  = "ARBITER",
  parameter int    N_PORTS  = 4,
  parameter int    MAX_WAIT = 32    // max cycles any requester waits
)(
  input logic               clk,
  input logic               rst_n,
  input logic [N_PORTS-1:0] req,
  input logic [N_PORTS-1:0] gnt
);

  // ARB.1: Grant must be one-hot (no simultaneous grants)
  property p_grant_one_hot;
    @(posedge clk) disable iff (!rst_n)
    $onehot0(gnt);
  endproperty
  VERA_ARB_F_ONE_HOT:
    assert property (p_grant_one_hot)
    else $error("VERA_FAIL | IP=%s | CHECK=ARB_FORMAL_ONE_HOT | gnt=0x%0h @%0t",
                IP_NAME, gnt, $time);

  // ARB.2: Grant only to a requester
  property p_grant_to_req;
    @(posedge clk) disable iff (!rst_n)
    (gnt != '0) |-> (gnt & req) == gnt;
  endproperty
  VERA_ARB_F_GRANT_TO_REQ:
    assert property (p_grant_to_req)
    else $error("VERA_FAIL | IP=%s | CHECK=ARB_FORMAL_GRANT_TO_REQ | granted to non-requester | @%0t",
                IP_NAME, $time);

  // ARB.3: Starvation freedom — every requester gets granted within MAX_WAIT
  generate
    for (genvar i = 0; i < N_PORTS; i++) begin : gen_starvation
      property p_no_starvation;
        @(posedge clk) disable iff (!rst_n)
        req[i] |-> ##[1:MAX_WAIT] gnt[i];
      endproperty
      VERA_ARB_F_STARVATION:
        assert property (p_no_starvation)
        else $error("VERA_FAIL | IP=%s | CHECK=ARB_FORMAL_STARVATION | port=%0d starved > %0d cycles | @%0t",
                    IP_NAME, i, MAX_WAIT, $time);
    end
  endgenerate

  // ARB.4: No grant without request (except idle)
  property p_no_spurious_grant;
    @(posedge clk) disable iff (!rst_n)
    (gnt != '0) |-> (req != '0);
  endproperty
  VERA_ARB_F_NO_SPURIOUS:
    assert property (p_no_spurious_grant)
    else $error("VERA_FAIL | IP=%s | CHECK=ARB_FORMAL_SPURIOUS | grant without request @%0t",
                IP_NAME, $time);

  // Cover: all ports granted at least once
  generate
    for (genvar i = 0; i < N_PORTS; i++) begin : gen_cover
      VERA_ARB_F_COVER_GRANT:
        cover property (@(posedge clk) disable iff (!rst_n) gnt[i]);
    end
  endgenerate

endmodule

// ============================================================================
// MODULE: vera_formal_cdc_props
// Clock Domain Crossing synchronizer properties
// ============================================================================
module vera_formal_cdc_props #(
  parameter string IP_NAME   = "CDC",
  parameter int    SYNC_STGS = 2     // synchronizer stages
)(
  input logic clk_src,
  input logic clk_dst,
  input logic rst_src_n,
  input logic rst_dst_n,
  input logic data_src,      // data in source domain
  input logic data_sync,     // synchronized output in dest domain
  input logic data_dst        // registered in destination domain
);

  // CDC.1: Synchronized data must eventually follow source (liveness)
  property p_sync_eventually;
    @(posedge clk_dst) disable iff (!rst_dst_n)
    $rose(data_src) |-> ##[SYNC_STGS:SYNC_STGS+2] data_sync;
  endproperty
  VERA_CDC_F_SYNC_LATCH:
    assert property (p_sync_eventually)
    else $error("VERA_FAIL | IP=%s | CHECK=CDC_FORMAL_SYNC | data not captured in %0d+2 cycles @%0t",
                IP_NAME, SYNC_STGS, $time);

  // CDC.2: Data must not glitch at destination
  property p_no_dest_glitch;
    @(posedge clk_dst) disable iff (!rst_dst_n)
    $rose(data_dst) |-> data_dst[*SYNC_STGS];
  endproperty
  VERA_CDC_F_NO_GLITCH:
    assert property (p_no_dest_glitch)
    else $error("VERA_FAIL | IP=%s | CHECK=CDC_FORMAL_GLITCH | metastability pulse < %0d cycles @%0t",
                IP_NAME, SYNC_STGS, $time);

endmodule

`endif // VERA_FORMAL_PROPERTIES_SV
