## ============================================================================
## VERA — Verification Engine for Runtime & Autonomous Checking
## FILE: scripts/integration/vera_jaspergold.tcl
## DESC: JasperGold automation Tcl script for VERA formal property checking.
##       Reads VERA IP spec, loads design, applies constraints, runs proofs,
##       and generates VERA-format JSON report.
## VERSION: 1.0
## USAGE: jg -tcl vera_jaspergold.tcl -define IP_NAME=MY_IP
## ============================================================================

# --- Configuration (override via -define or environment) ---
set VERA_HOME [expr { [info exists env(VERA_HOME)] ? $env(VERA_HOME) : "../.." }]
set IP_NAME   [expr { [info exists IP_NAME]         ? $IP_NAME         : "UNDEFINED" }]
set DEPTH     [expr { [info exists PROOF_DEPTH]     ? $PROOF_DEPTH     : 20 }]
set REPORT_DIR "./vera_reports/formal"

# Banner
puts "\n  ╔════════════════════════════════════════════════════╗"
puts "  ║  VERA JasperGold Formal Checker v1.0               ║"
puts "  ╚════════════════════════════════════════════════════╝\n"
puts "  IP: $IP_NAME  Depth: $DEPTH"

# --- Analyze design sources ---
proc vera_analyze_sources { src_list } {
    foreach src $src_list {
        if { [string match "*.sv" $src] || [string match "*.svh" $src] } {
            analyze -sv09 -f $src
        } elseif { [string match "*.v" $src] } {
            analyze -verilog -f $src
        }
    }
}

# --- Load VERA SVA library ---
analyze -sv09 "${VERA_HOME}/core/sv/vera_sva_library.sv"
analyze -sv09 "${VERA_HOME}/core/sv/vera_formal_properties.sv"

# --- Elaborate ---
proc vera_elaborate { top_module } {
    elaborate -top $top_module
    puts "  \[VERA Formal\] Elaborated: $top_module"
}

# --- Apply standard clock and reset constraints ---
proc vera_setup_clocks_resets { clk_name rst_name rst_active_low } {
    clock $clk_name -period 10
    if { $rst_active_low } {
        reset -expression "!${rst_name}"
        # Drive reset for 5 cycles at start
        assume -name vera_assume_reset -env { ${rst_name} == 1'b0 } -for 5
        assume -name vera_assume_post_reset -env { ${rst_name} == 1'b1 } -from 6
    } else {
        reset -expression "${rst_name}"
    }
    puts "  \[VERA Formal\] Clock: $clk_name  Reset: $rst_name (active_low=$rst_active_low)"
}

# --- Run VERA property groups ---
proc vera_run_group { group_name depth } {
    puts "\n  \[VERA Formal\] Running: $group_name (depth=$depth)"
    set results [list]
    
    # Get all assertions matching VERA_ prefix
    set vera_props [get_property_list -name "VERA_*"]
    
    foreach prop $vera_props {
        # Set proof depth
        set_max_trace_length $depth
        
        # Run bounded model check
        prove -property $prop
        
        set status [get_property_info -property $prop -field status]
        lappend results [list $prop $status]
        
        set icon [expr { $status eq "proven" ? "✓" : "✗" }]
        puts "    \[$icon\] $prop : $status"
    }
    return $results
}

# --- Generate VERA JSON report from formal results ---
proc vera_write_formal_report { results report_path ip_name } {
    global VERA_HOME
    
    set fd [open $report_path w]
    set ts [clock format [clock seconds] -format "%Y-%m-%dT%H:%M:%S"]
    
    set n_total  [llength $results]
    set n_proven 0
    set n_failed 0
    set n_cex    0
    
    foreach r $results {
        set status [lindex $r 1]
        if { $status eq "proven"       } { incr n_proven }
        if { $status eq "cex"          } { incr n_failed; incr n_cex }
        if { $status eq "vacuous"      } { incr n_proven }
        if { $status eq "unreachable"  } { incr n_proven }
    }
    
    puts $fd "\{"
    puts $fd "  \"vera_report\": \{"
    puts $fd "    \"meta\": \{\"ip_name\": \"$ip_name\", \"checker_type\": \"formal\", \"generated\": \"$ts\"\},"
    puts $fd "    \"summary\": \{\"total\": $n_total, \"pass\": $n_proven, \"fail\": $n_failed, \"cex\": $n_cex\},"
    puts $fd "    \"results\": \["
    
    set i 0
    foreach r $results {
        set prop   [lindex $r 0]
        set status [lindex $r 1]
        set vera_status [expr { $status eq "proven" || $status eq "vacuous" ? "PASS" : "FAIL" }]
        set severity    [expr { $vera_status eq "PASS" ? "INFO" : "ERROR" }]
        
        # Get counterexample trace info if failed
        set cex_info ""
        if { $status eq "cex" } {
            catch {
                set trace_len [get_property_info -property $prop -field cex_length]
                set cex_info "CEX trace length: $trace_len cycles"
            }
        }
        
        puts $fd "      \{"
        puts $fd "        \"ip_name\": \"$ip_name\","
        puts $fd "        \"checker_name\": \"$prop\","
        puts $fd "        \"checker_type\": \"formal\","
        puts $fd "        \"layer\": \"protocol\","
        puts $fd "        \"status\": \"$vera_status\","
        puts $fd "        \"severity\": \"$severity\","
        puts $fd "        \"expected\": \"property proven\","
        puts $fd "        \"actual\": \"$status\","
        puts $fd "        \"context\": \"$cex_info\","
        puts $fd "        \"recommendation\": \"[expr { $vera_status eq \"FAIL\" ? \"Review counterexample trace in JasperGold GUI\" : \"\" }]\""
        puts $fd "      \}[expr { $i < $n_total-1 ? \",\" : \"\" }]"
        incr i
    }
    
    puts $fd "    \]"
    puts $fd "  \}"
    puts $fd "\}"
    close $fd
    
    puts "\n  ╔════════════════════════════════════════════╗"
    puts "  ║  VERA FORMAL SUMMARY"
    puts "  ║  PROVEN : $n_proven"
    puts "  ║  CEX    : $n_cex"
    puts "  ║  TOTAL  : $n_total"
    puts "  ╚════════════════════════════════════════════╝"
    puts "  Report: $report_path\n"
}

# --- Main flow ---
proc vera_formal_main { top depth } {
    global REPORT_DIR IP_NAME
    
    file mkdir $REPORT_DIR
    
    # Setup
    vera_setup_clocks_resets "clk" "rst_n" 1
    
    # Run all VERA_ properties
    set all_results [vera_run_group "vera_all" $depth]
    
    # Write VERA report
    vera_write_formal_report $all_results \
        "${REPORT_DIR}/vera_formal_${IP_NAME}.json" \
        $IP_NAME
    
    # Generate witness traces for any CEX
    foreach r $all_results {
        if { [lindex $r 1] eq "cex" } {
            set prop [lindex $r 0]
            set safe_name [regsub -all {[^A-Za-z0-9_]} $prop "_"]
            catch {
                generate_cex_trace -property $prop \
                    -output "${REPORT_DIR}/cex_${safe_name}.vcd"
                puts "  \[VERA\] CEX trace: ${REPORT_DIR}/cex_${safe_name}.vcd"
            }
        }
    }
}

# Execute if sourced directly
if { [info script] eq [info nameofexecutable] || 1 } {
    vera_formal_main $IP_NAME $DEPTH
}
