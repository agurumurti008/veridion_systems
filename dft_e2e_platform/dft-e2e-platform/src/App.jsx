import { useState, useEffect, useRef, useCallback, useReducer } from "react";

// ─── SPECKG SEED DATA ─────────────────────────────────────────────────────────
const INITIAL_NODES = [
  { id:"vref",      label:"VREF",         domain:"analog",       layer:["SpecCore","AnalogVeil","DFTVeil"],          testability:"GBT", trim:true,  value:"1.2V",     unit:"V",    desc:"Bandgap reference voltage",          ip:"LDO",  risk:72 },
  { id:"ibias",     label:"IBIAS",        domain:"analog",       layer:["SpecCore","AnalogVeil","DFTVeil"],          testability:"GBT", trim:true,  value:"10µA",      unit:"µA",   desc:"Bias current for analog blocks",     ip:"LDO",  risk:65 },
  { id:"pll_lock",  label:"PLL_LOCK",     domain:"digital",      layer:["SpecCore","DigitalVeil","DFTVeil"],         testability:"GBD", trim:false, value:"100ns",     unit:"ns",   desc:"PLL lock time specification",        ip:"PLL",  risk:55 },
  { id:"adc_inl",   label:"ADC_INL",      domain:"mixed-signal", layer:["SpecCore","AnalogVeil","VerifVeil"],        testability:"GBT", trim:true,  value:"±0.5LSB",   unit:"LSB",  desc:"ADC integral non-linearity",         ip:"ADC",  risk:80 },
  { id:"vddio",     label:"VDDIO_RANGE",  domain:"analog",       layer:["SpecCore","AnalogVeil","TestVeil"],         testability:"GBT", trim:false, value:"1.8–3.3V",  unit:"V",    desc:"IO supply voltage range",            ip:"IO",   risk:40 },
  { id:"clk_freq",  label:"CLK_FREQ",     domain:"digital",      layer:["SpecCore","DigitalVeil","VerifVeil"],       testability:"GBD", trim:false, value:"400MHz",    unit:"MHz",  desc:"Core clock frequency",               ip:"PLL",  risk:50 },
  { id:"psrr",      label:"PSRR",         domain:"analog",       layer:["SpecCore","AnalogVeil","DocVeil"],          testability:"GBT", trim:false, value:"60dB",      unit:"dB",   desc:"Power supply rejection ratio",       ip:"LDO",  risk:58 },
  { id:"adc_enob",  label:"ADC_ENOB",     domain:"mixed-signal", layer:["SpecCore","AnalogVeil","DFTVeil"],          testability:"GBT", trim:true,  value:"11.5b",     unit:"bits", desc:"ADC effective number of bits",       ip:"ADC",  risk:85 },
  { id:"scan_cov",  label:"SCAN_COV",     domain:"digital",      layer:["SpecCore","DigitalVeil","DFTVeil"],         testability:"GBD", trim:false, value:">95%",      unit:"%",    desc:"Scan chain fault coverage target",   ip:"DFT",  risk:35 },
  { id:"ldo_drop",  label:"LDO_DROPOUT",  domain:"analog",       layer:["SpecCore","AnalogVeil","DFTVeil"],          testability:"GBT", trim:true,  value:"200mV",     unit:"mV",   desc:"LDO dropout voltage at full load",   ip:"LDO",  risk:70 },
  { id:"cmrr",      label:"CMRR",         domain:"analog",       layer:["SpecCore","AnalogVeil","VerifVeil"],        testability:"GBT", trim:false, value:"80dB",      unit:"dB",   desc:"Common-mode rejection ratio",        ip:"OTA",  risk:60 },
  { id:"snr",       label:"ADC_SNR",      domain:"mixed-signal", layer:["SpecCore","AnalogVeil","DFTVeil"],          testability:"GBT", trim:false, value:"71dB",      unit:"dB",   desc:"ADC signal-to-noise ratio",          ip:"ADC",  risk:78 },
  { id:"reg_map",   label:"REG_MAP",      domain:"digital",      layer:["SpecCore","DigitalVeil","DocVeil"],         testability:"GBD", trim:false, value:"256b",      unit:"bits", desc:"Control register map width",         ip:"DFT",  risk:30 },
  { id:"trim_dac",  label:"TRIM_DAC",     domain:"mixed-signal", layer:["SpecCore","DFTVeil","DigitalVeil"],         testability:"GBT", trim:true,  value:"8-bit",     unit:"bits", desc:"Trim DAC resolution for calibration",ip:"ADC",  risk:75 },
  { id:"dnl",       label:"ADC_DNL",      domain:"mixed-signal", layer:["SpecCore","AnalogVeil","DFTVeil","VerifVeil"],testability:"GBT",trim:true,  value:"±0.3LSB",   unit:"LSB",  desc:"ADC differential non-linearity",     ip:"ADC",  risk:77 },
  { id:"ota_gbw",   label:"OTA_GBW",      domain:"analog",       layer:["SpecCore","AnalogVeil"],                   testability:"GBT", trim:false, value:"50MHz",     unit:"MHz",  desc:"OTA gain-bandwidth product",         ip:"OTA",  risk:62 },
];

const INITIAL_EDGES = [
  { source:"vref",     target:"ibias",    type:"drives"      },
  { source:"vref",     target:"adc_inl",  type:"constrains"  },
  { source:"vref",     target:"ldo_drop", type:"constrains"  },
  { source:"ibias",    target:"psrr",     type:"affects"     },
  { source:"ibias",    target:"ota_gbw",  type:"drives"      },
  { source:"pll_lock", target:"clk_freq", type:"depends"     },
  { source:"clk_freq", target:"adc_enob", type:"constrains"  },
  { source:"adc_inl",  target:"adc_enob", type:"constrains"  },
  { source:"adc_inl",  target:"dnl",      type:"related"     },
  { source:"adc_enob", target:"snr",      type:"drives"      },
  { source:"vddio",    target:"ldo_drop", type:"constrains"  },
  { source:"ldo_drop", target:"vref",     type:"affects"     },
  { source:"scan_cov", target:"reg_map",  type:"depends"     },
  { source:"reg_map",  target:"trim_dac", type:"drives"      },
  { source:"trim_dac", target:"vref",     type:"trims"       },
  { source:"trim_dac", target:"ibias",    type:"trims"       },
  { source:"trim_dac", target:"dnl",      type:"trims"       },
  { source:"cmrr",     target:"psrr",     type:"related"     },
  { source:"cmrr",     target:"ota_gbw",  type:"related"     },
  { source:"snr",      target:"dnl",      type:"constrains"  },
];

const DOMAIN_COLOR  = { analog:"#f59e0b", digital:"#22d3ee", "mixed-signal":"#a78bfa" };
const TRING         = { GBT:"#10b981", GBD:"#f97316" };
const EDGE_COLOR    = { drives:"#f59e0b", constrains:"#ef4444", affects:"#f97316", depends:"#22d3ee", related:"#64748b", trims:"#a78bfa" };
const ALL_VEILS     = ["SpecCore","AnalogVeil","DigitalVeil","DFTVeil","VerifVeil","TestVeil","DocVeil"];
const VEIL_COLOR    = { SpecCore:"#64748b", AnalogVeil:"#f59e0b", DigitalVeil:"#22d3ee", DFTVeil:"#10b981", VerifVeil:"#a78bfa", TestVeil:"#f97316", DocVeil:"#94a3b8" };

// ─── BFS DOWNSTREAM ──────────────────────────────────────────────────────────
function bfsDownstream(startId, edges) {
  const visited = new Set(), queue = [startId];
  while (queue.length) {
    const cur = queue.shift();
    edges.forEach(e => { if (e.source === cur && !visited.has(e.target)) { visited.add(e.target); queue.push(e.target); }});
  }
  return visited;
}

// ─── STREAMING CLAUDE CALL ───────────────────────────────────────────────────
async function streamClaude(messages, system, onChunk, onDone) {
  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ model:"claude-sonnet-4-20250514", max_tokens:1200, system, messages, stream:true }),
    });
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "", full = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream:true });
      const lines = buf.split("\n");
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        try {
          const d = JSON.parse(line.slice(5));
          if (d.type === "content_block_delta" && d.delta?.text) {
            full += d.delta.text;
            onChunk(full);
          }
        } catch {}
      }
    }
    onDone(full);
  } catch (e) {
    // fallback non-stream
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ model:"claude-sonnet-4-20250514", max_tokens:1200, system, messages }),
    });
    const data = await res.json();
    const text = data.content?.map(b=>b.text||"").join("") || JSON.stringify(data);
    onChunk(text); onDone(text);
  }
}

async function callClaude(messages, system) {
  return new Promise((resolve) => {
    let result = "";
    streamClaude(messages, system, t => { result = t; }, resolve);
  });
}

// ─── STYLES ──────────────────────────────────────────────────────────────────
const S = {
  card:  { background:"rgba(15,23,42,0.85)", border:"1px solid rgba(148,163,184,0.13)", borderRadius:8, padding:16 },
  lbl:   { fontSize:9, letterSpacing:2.5, textTransform:"uppercase", color:"#475569", marginBottom:4, fontWeight:700 },
  mono:  { fontFamily:"'JetBrains Mono','Fira Code','Courier New',monospace", fontSize:12 },
  badge: c => ({ background:c+"22", color:c, border:`1px solid ${c}44`, borderRadius:4, padding:"2px 8px", fontSize:9, letterSpacing:1, fontWeight:700, display:"inline-block" }),
  btn:   (active, color="#f59e0b") => ({
    padding:"7px 14px", borderRadius:6, fontSize:11, letterSpacing:1, fontWeight:600, cursor:"pointer",
    border: active ? `1px solid ${color}` : "1px solid rgba(148,163,184,0.18)",
    background: active ? color+"22" : "rgba(15,23,42,0.6)",
    color: active ? color : "#64748b", transition:"all 0.15s",
  }),
  inp: { background:"rgba(2,8,23,0.7)", border:"1px solid rgba(148,163,184,0.18)", borderRadius:6, padding:"9px 12px", color:"#e2e8f0", fontSize:13, outline:"none", boxSizing:"border-box", width:"100%", fontFamily:"'JetBrains Mono',monospace" },
  scrollbox: { overflowY:"auto", maxHeight:420 },
};

// ─── SPINNER ─────────────────────────────────────────────────────────────────
function Spinner({ color="#f59e0b" }) {
  return (
    <span style={{ display:"inline-block", width:14, height:14, border:`2px solid ${color}44`, borderTopColor:color, borderRadius:"50%", animation:"spin 0.7s linear infinite" }} />
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 1 — SPECKG EXPLORER (draggable force graph)
// ═══════════════════════════════════════════════════════════════════════════════
function SpecKGExplorer({ nodes, edges, onImpact }) {
  const svgRef  = useRef(null);
  const posRef  = useRef({});
  const velRef  = useRef({});
  const frameRef= useRef(null);
  const dragRef = useRef(null);
  const [tick,   setTick]    = useState(0);
  const [selId,  setSelId]   = useState(null);
  const [dims,   setDims]    = useState({w:0,h:0});
  const [filter, setFilter]  = useState("all");
  const [showEdgeLabels, setShowEdgeLabels] = useState(false);
  const [searchQ, setSearchQ] = useState("");

  // Init positions on mount
  useEffect(() => {
    const obs = new ResizeObserver(([e]) => setDims({w:e.contentRect.width, h:e.contentRect.height}));
    if (svgRef.current) obs.observe(svgRef.current);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    if (!dims.w) return;
    nodes.forEach((n,i) => {
      if (!posRef.current[n.id]) {
        const a = (i/nodes.length)*2*Math.PI;
        posRef.current[n.id] = { x: dims.w/2 + Math.cos(a)*dims.w*0.28, y: dims.h/2 + Math.sin(a)*dims.h*0.28 };
        velRef.current[n.id] = { vx:0, vy:0 };
      }
    });
    let t = 0;
    const step = () => {
      if (t++ > 400 && !dragRef.current) { frameRef.current = null; return; }
      const pos = posRef.current, vel = velRef.current;
      const ids = nodes.map(n=>n.id);
      // repulsion
      ids.forEach(a => ids.forEach(b => {
        if (a===b) return;
        const dx=pos[a].x-pos[b].x, dy=pos[a].y-pos[b].y, d=Math.sqrt(dx*dx+dy*dy)||1;
        const f = 3800/(d*d);
        vel[a].vx += (dx/d)*f; vel[a].vy += (dy/d)*f;
      }));
      // spring
      edges.forEach(({source:s,target:t2}) => {
        if (!pos[s]||!pos[t2]) return;
        const dx=pos[t2].x-pos[s].x, dy=pos[t2].y-pos[s].y, d=Math.sqrt(dx*dx+dy*dy)||1;
        const f=(d-140)*0.03, fx=(dx/d)*f, fy=(dy/d)*f;
        vel[s].vx+=fx; vel[s].vy+=fy; vel[t2].vx-=fx; vel[t2].vy-=fy;
      });
      // gravity + damping
      ids.forEach(id => {
        if (dragRef.current?.id === id) return;
        vel[id].vx += (dims.w/2-pos[id].x)*0.004;
        vel[id].vy += (dims.h/2-pos[id].y)*0.004;
        vel[id].vx *= 0.82; vel[id].vy *= 0.82;
        pos[id].x = Math.max(36,Math.min(dims.w-36, pos[id].x+vel[id].vx));
        pos[id].y = Math.max(36,Math.min(dims.h-36, pos[id].y+vel[id].vy));
      });
      setTick(x=>x+1);
      frameRef.current = requestAnimationFrame(step);
    };
    frameRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frameRef.current);
  }, [dims, nodes, edges]);

  // Drag handlers
  const onMouseDown = useCallback((e, id) => {
    e.stopPropagation();
    const svg = svgRef.current.getBoundingClientRect();
    dragRef.current = { id, ox: e.clientX-svg.left - posRef.current[id].x, oy: e.clientY-svg.top - posRef.current[id].y };
    const onMove = ev => {
      const r = svgRef.current.getBoundingClientRect();
      posRef.current[id] = { x: ev.clientX-r.left-dragRef.current.ox, y: ev.clientY-r.top-dragRef.current.oy };
      velRef.current[id] = { vx:0, vy:0 };
      setTick(x=>x+1);
      if (!frameRef.current) { let t2=0; const step2=()=>{ frameRef.current=requestAnimationFrame(step2); setTick(x=>x+1); if(t2++>600)frameRef.current=null; }; step2(); }
    };
    const onUp = () => { dragRef.current=null; window.removeEventListener("mousemove",onMove); window.removeEventListener("mouseup",onUp); };
    window.addEventListener("mousemove",onMove);
    window.addEventListener("mouseup",onUp);
  }, []);

  const selNode = nodes.find(n=>n.id===selId);
  const downstream = selId ? bfsDownstream(selId, edges) : new Set();
  const upstream = selId ? (() => { const s=new Set(), q=[selId]; while(q.length){const c=q.shift(); edges.forEach(e=>{if(e.target===c&&!s.has(e.source)){s.add(e.source);q.push(e.source);}}); } return s; })() : new Set();

  const visNodes = nodes.filter(n => {
    if (searchQ && !n.label.toLowerCase().includes(searchQ.toLowerCase()) && !n.desc.toLowerCase().includes(searchQ.toLowerCase())) return false;
    if (filter==="all") return true;
    if (filter==="GBT"||filter==="GBD") return n.testability===filter;
    if (filter==="trim") return n.trim;
    return n.domain===filter;
  });
  const visIds = new Set(visNodes.map(n=>n.id));

  return (
    <div style={{display:"flex",gap:14,height:560}}>
      {/* Graph pane */}
      <div style={{flex:1,position:"relative",...S.card,padding:0,overflow:"hidden"}}>
        {/* Toolbar */}
        <div style={{position:"absolute",top:10,left:10,right:10,zIndex:10,display:"flex",gap:6,flexWrap:"wrap",alignItems:"center"}}>
          <input value={searchQ} onChange={e=>setSearchQ(e.target.value)} placeholder="Search nodes…" style={{...S.inp,width:140,padding:"5px 10px",fontSize:11}} />
          {["all","analog","digital","mixed-signal","GBT","GBD","trim"].map(f=>(
            <button key={f} onClick={()=>setFilter(f)} style={{...S.btn(filter===f, filter===f && f==="GBT"?"#10b981":f==="GBD"?"#f97316":f==="trim"?"#a78bfa":DOMAIN_COLOR[f]||"#f59e0b"), padding:"4px 10px", fontSize:9}}>{f.toUpperCase()}</button>
          ))}
          <button onClick={()=>setShowEdgeLabels(x=>!x)} style={{...S.btn(showEdgeLabels,"#64748b"),padding:"4px 10px",fontSize:9}}>EDGE LABELS</button>
          <button onClick={()=>setSelId(null)} style={{...S.btn(false,"#64748b"),padding:"4px 10px",fontSize:9}}>CLEAR</button>
        </div>

        <svg ref={svgRef} width="100%" height="100%" style={{position:"absolute",inset:0}}>
          <defs>
            {Object.entries(EDGE_COLOR).map(([t,c])=>(
              <marker key={t} id={`arr-${t}`} markerWidth="7" markerHeight="7" refX="6" refY="2.5" orient="auto">
                <path d="M0,0 L0,5 L7,2.5z" fill={c} opacity="0.7"/>
              </marker>
            ))}
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="blur"/>
              <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
          </defs>

          {/* Edges */}
          {edges.map((e,i)=>{
            const s=posRef.current[e.source], t2=posRef.current[e.target];
            if(!s||!t2||!visIds.has(e.source)||!visIds.has(e.target)) return null;
            const active = selId && (e.source===selId||downstream.has(e.source)||upstream.has(e.target));
            const col = active ? EDGE_COLOR[e.type]||"#94a3b8" : "rgba(100,116,139,0.2)";
            const mx=(s.x+t2.x)/2, my=(s.y+t2.y)/2;
            return (
              <g key={i}>
                <line x1={s.x} y1={s.y} x2={t2.x} y2={t2.y} stroke={col} strokeWidth={active?2:1} markerEnd={`url(#arr-${e.type})`} opacity={active?1:0.35}/>
                {showEdgeLabels && <text x={mx} y={my-4} textAnchor="middle" fill={col} fontSize={8} opacity={0.8}>{e.type}</text>}
              </g>
            );
          })}

          {/* Nodes */}
          {nodes.map(n=>{
            const p=posRef.current[n.id];
            if(!p) return null;
            const visible = visIds.has(n.id);
            const col = DOMAIN_COLOR[n.domain];
            const ring = TRING[n.testability];
            const isSel = selId===n.id;
            const isDn  = downstream.has(n.id);
            const isUp  = upstream.has(n.id);
            const scale = isSel ? 1.35 : 1;
            const opacity = !selId ? (visible?1:0.15) : (isSel||isDn||isUp ? 1 : visible ? 0.25 : 0.08);
            return (
              <g key={n.id} transform={`translate(${p.x},${p.y})`}
                style={{cursor:"pointer"}} opacity={opacity}
                onMouseDown={ev=>onMouseDown(ev,n.id)}
                onClick={()=>setSelId(isSel?null:n.id)}>
                {isSel && <circle r={30} fill="none" stroke={col} strokeWidth={1} opacity={0.3} style={{animation:"pulse 1.5s ease-in-out infinite"}}/>}
                <circle r={22*scale} fill={ring+"18"} stroke={ring} strokeWidth={isSel?2:1.2} filter={isSel?"url(#glow)":undefined}/>
                <circle r={15*scale} fill={col+"2a"} stroke={col} strokeWidth={isSel?2:1}/>
                {n.trim && <circle r={4} cx={13} cy={-13} fill="#a78bfa" stroke="#020817" strokeWidth={1}/>}
                {isDn   && <circle r={3} cx={-13} cy={-13} fill="#10b981"/>}
                {isUp   && <circle r={3} cx={13} cy={13} fill="#f59e0b"/>}
                <text textAnchor="middle" dominantBaseline="middle" style={{fontSize:8,fill:col,fontFamily:"monospace",fontWeight:700,pointerEvents:"none",letterSpacing:0.5}}>
                  {n.label.length>9?n.label.slice(0,8)+"…":n.label}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Mini legend */}
        <div style={{position:"absolute",bottom:10,left:10,display:"flex",gap:8,flexWrap:"wrap"}}>
          {Object.entries(EDGE_COLOR).map(([t,c])=>(
            <span key={t} style={{fontSize:8,color:c,letterSpacing:1}}>─ {t}</span>
          ))}
        </div>
      </div>

      {/* Detail panel */}
      <div style={{width:290,display:"flex",flexDirection:"column",gap:10,overflowY:"auto"}}>
        {selNode ? (
          <>
            <div style={{...S.card}}>
              <div style={{...S.lbl}}>NODE DETAIL</div>
              <div style={{fontSize:17,fontWeight:800,color:DOMAIN_COLOR[selNode.domain],fontFamily:"monospace",letterSpacing:1}}>{selNode.label}</div>
              <div style={{fontSize:11,color:"#64748b",marginTop:4,marginBottom:10,lineHeight:1.5}}>{selNode.desc}</div>
              <div style={{display:"flex",flexWrap:"wrap",gap:5,marginBottom:10}}>
                <span style={S.badge(DOMAIN_COLOR[selNode.domain])}>{selNode.domain}</span>
                <span style={S.badge(TRING[selNode.testability])}>{selNode.testability}</span>
                {selNode.trim && <span style={S.badge("#a78bfa")}>TRIM</span>}
                <span style={S.badge("#64748b")}>{selNode.ip}</span>
              </div>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:6,marginBottom:10}}>
                {[["Value",selNode.value],["Unit",selNode.unit],["Risk Score",selNode.risk+"/100"]].map(([k,v])=>(
                  <div key={k} style={{...S.card,padding:"6px 10px",background:"rgba(2,8,23,0.5)"}}>
                    <div style={{...S.lbl,marginBottom:2}}>{k}</div>
                    <div style={{...S.mono,color:"#e2e8f0",fontSize:11}}>{v}</div>
                  </div>
                ))}
                <div style={{...S.card,padding:"6px 10px",background:"rgba(2,8,23,0.5)"}}>
                  <div style={{...S.lbl,marginBottom:2}}>DOWNSTREAM</div>
                  <div style={{...S.mono,color:"#10b981",fontSize:11}}>{downstream.size} nodes</div>
                </div>
              </div>
              <div style={{...S.lbl}}>LAYERS</div>
              <div style={{display:"flex",flexWrap:"wrap",gap:4,marginBottom:10}}>
                {ALL_VEILS.map(v=>(<span key={v} style={{...S.badge(selNode.layer.includes(v)?VEIL_COLOR[v]:"#1e293b"),opacity:selNode.layer.includes(v)?1:0.35,fontSize:8}}>{v}</span>))}
              </div>
              <button onClick={()=>onImpact(selNode.id)} style={{...S.btn(false,"#f59e0b"),width:"100%",marginBottom:6}}>⚡ CHANGE IMPACT REPORT</button>
            </div>

            {/* Downstream list */}
            {downstream.size > 0 && (
              <div style={{...S.card}}>
                <div style={{...S.lbl}}>DOWNSTREAM CHAIN ({downstream.size})</div>
                {[...downstream].map(id=>{
                  const dn=nodes.find(n=>n.id===id);
                  if(!dn) return null;
                  const edge = edges.find(e=>e.source===selId&&e.target===id)||edges.find(e=>e.target===id);
                  return (
                    <div key={id} onClick={()=>setSelId(id)} style={{display:"flex",alignItems:"center",gap:8,padding:"5px 0",borderBottom:"1px solid rgba(30,41,59,0.6)",cursor:"pointer"}}>
                      <div style={{width:6,height:6,borderRadius:"50%",background:DOMAIN_COLOR[dn.domain],flexShrink:0}}/>
                      <span style={{...S.mono,fontSize:10,color:DOMAIN_COLOR[dn.domain],flex:1}}>{dn.label}</span>
                      {edge && <span style={{fontSize:8,color:EDGE_COLOR[edge.type]||"#64748b"}}>{edge.type}</span>}
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : (
          <div style={{...S.card,flex:1,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:10}}>
            <div style={{fontSize:36,opacity:0.3}}>⬡</div>
            <div style={{color:"#475569",fontSize:12,textAlign:"center",lineHeight:1.7}}>Click a node to inspect<br/>Drag to reposition<br/>Use filters to focus</div>
          </div>
        )}
        {/* Domain summary */}
        <div style={{...S.card,padding:12}}>
          <div style={{...S.lbl}}>GRAPH SUMMARY</div>
          {Object.entries(DOMAIN_COLOR).map(([d,c])=>{
            const cnt = nodes.filter(n=>n.domain===d).length;
            return (
              <div key={d} style={{display:"flex",alignItems:"center",gap:6,marginBottom:4}}>
                <div style={{width:8,height:8,borderRadius:2,background:c}}/>
                <span style={{fontSize:10,color:"#94a3b8",flex:1}}>{d}</span>
                <span style={{...S.mono,fontSize:10,color:c}}>{cnt}</span>
                <div style={{width:60,height:4,background:"#0f172a",borderRadius:2,overflow:"hidden"}}>
                  <div style={{width:`${(cnt/nodes.length)*100}%`,height:"100%",background:c,borderRadius:2}}/>
                </div>
              </div>
            );
          })}
          <div style={{marginTop:8,...S.lbl}}>TRIM CAPABLE</div>
          <div style={{...S.mono,fontSize:11,color:"#a78bfa"}}>{nodes.filter(n=>n.trim).length} / {nodes.length} nodes</div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 2 — DFT PLANNING (streaming chat + structured JSON output)
// ═══════════════════════════════════════════════════════════════════════════════
function DFTPlanning({ nodes }) {
  const [selId, setSelId]   = useState("");
  const [loading, setLoading] = useState(false);
  const [stream, setStream]  = useState("");
  const [result, setResult]  = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
  const [followUp, setFollowUp] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  const node = nodes.find(n=>n.id===selId);

  const runAnalysis = async () => {
    if (!node) return;
    setLoading(true); setStream(""); setResult(null); setChatHistory([]);
    const sys = `You are a senior DFT architect for analog/mixed-signal semiconductor ICs. 
Return ONLY valid JSON with no markdown fences. Schema:
{ gbt_gbd:"GBT"|"GBD", confidence:0-100, rationale:string, trim_budget:{resolution:string,range_pct:number,dac_bits:number,notes:string}, signal_bringout:{strategy:string,mux_levels:number,control_regs:string[],pin_budget:number,notes:string}, process_corners:string[], test_components:string[], sim_implications:string[], risks:string[], speckg_update:{testability:string,trim_flag:boolean,dft_note:string,recommended_veils:string[]} }`;
    const prompt = `Analyze spec parameter: ${node.label}
Description: ${node.desc}
Domain: ${node.domain}
Nominal value: ${node.value} ${node.unit}
Trim capable: ${node.trim}
IP block: ${node.ip}
Risk score: ${node.risk}/100
Layer memberships: ${node.layer.join(", ")}

Provide a complete DFT planning analysis.`;
    let full = "";
    await streamClaude([{role:"user",content:prompt}], sys,
      t => { setStream(t); full=t; },
      () => {
        try {
          const j = JSON.parse(full.replace(/```json|```/g,"").trim());
          setResult(j);
          setStream("");
          setChatHistory([{role:"user",content:prompt},{role:"assistant",content:full}]);
        } catch { setResult({raw:full}); setStream(""); }
        setLoading(false);
      }
    );
  };

  const sendFollowUp = async () => {
    if (!followUp.trim()||chatLoading) return;
    const msg = followUp; setFollowUp(""); setChatLoading(true);
    const msgs = [...chatHistory, {role:"user",content:msg}];
    setChatHistory(msgs);
    let resp = "";
    await streamClaude(msgs, "You are a senior DFT architect. Answer concisely and technically.",
      t => { resp=t; setChatHistory([...msgs,{role:"assistant",content:t}]); },
      () => { setChatHistory([...msgs,{role:"assistant",content:resp}]); setChatLoading(false); }
    );
  };

  return (
    <div style={{display:"flex",flexDirection:"column",gap:12}}>
      {/* Param selector */}
      <div style={{...S.card}}>
        <div style={{...S.lbl}}>SELECT SPEC PARAMETER FOR DFT ANALYSIS</div>
        <div style={{display:"flex",gap:6,flexWrap:"wrap",marginTop:8}}>
          {nodes.map(n=>(
            <button key={n.id} onClick={()=>{setSelId(n.id);setResult(null);setStream("");setChatHistory([]);}}
              style={{...S.btn(selId===n.id, DOMAIN_COLOR[n.domain]), padding:"5px 12px", fontSize:10}}>
              <span style={{color:TRING[n.testability],marginRight:4,fontSize:8}}>●</span>{n.label}
            </button>
          ))}
        </div>
        {node && (
          <div style={{marginTop:10,padding:"8px 12px",background:"rgba(2,8,23,0.5)",borderRadius:6,display:"flex",gap:12,flexWrap:"wrap",alignItems:"center"}}>
            <span style={{...S.mono,fontSize:11,color:DOMAIN_COLOR[node.domain]}}>{node.label}</span>
            <span style={{fontSize:11,color:"#64748b"}}>{node.desc}</span>
            <span style={S.badge(TRING[node.testability])}>{node.testability}</span>
            {node.trim && <span style={S.badge("#a78bfa")}>TRIM</span>}
            <button onClick={runAnalysis} disabled={loading} style={{...S.btn(false,"#f59e0b"),marginLeft:"auto"}}>
              {loading ? <><Spinner/> &nbsp;ANALYZING…</> : "▶ RUN DFT AI ANALYSIS"}
            </button>
          </div>
        )}
      </div>

      {/* Streaming raw */}
      {stream && !result && (
        <div style={{...S.card,...S.mono,fontSize:11,color:"#64748b",whiteSpace:"pre-wrap",maxHeight:200,overflowY:"auto"}}>{stream}</div>
      )}

      {/* Structured result */}
      {result && !result.raw && (
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:10}}>
          {/* Classification */}
          <div style={{...S.card,borderColor:result.gbt_gbd==="GBT"?"#10b98144":"#f9741644"}}>
            <div style={{...S.lbl}}>CLASSIFICATION</div>
            <div style={{display:"flex",alignItems:"baseline",gap:10,marginBottom:8}}>
              <span style={{fontSize:28,fontWeight:900,color:TRING[result.gbt_gbd],fontFamily:"monospace"}}>{result.gbt_gbd}</span>
              <div style={{flex:1,height:4,background:"#0f172a",borderRadius:2}}>
                <div style={{width:`${result.confidence||0}%`,height:"100%",background:TRING[result.gbt_gbd],borderRadius:2,transition:"width 0.8s"}}/>
              </div>
              <span style={{...S.mono,fontSize:10,color:"#64748b"}}>{result.confidence}%</span>
            </div>
            <div style={{fontSize:12,color:"#94a3b8",lineHeight:1.65}}>{result.rationale}</div>
          </div>

          {/* Trim budget */}
          <div style={{...S.card}}>
            <div style={{...S.lbl}}>TRIM BUDGET</div>
            {result.trim_budget && (
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:6,marginBottom:8}}>
                {[["Resolution",result.trim_budget.resolution],["Range",result.trim_budget.range_pct+"%"],["DAC Bits",result.trim_budget.dac_bits+"b"]].map(([k,v])=>(
                  <div key={k} style={{padding:"6px 10px",background:"rgba(2,8,23,0.5)",borderRadius:5}}>
                    <div style={{...S.lbl,marginBottom:2}}>{k}</div>
                    <div style={{...S.mono,fontSize:12,color:"#f59e0b"}}>{v}</div>
                  </div>
                ))}
              </div>
            )}
            {result.trim_budget?.notes && <div style={{fontSize:11,color:"#64748b",lineHeight:1.5}}>{result.trim_budget.notes}</div>}
          </div>

          {/* Signal bring-out */}
          <div style={{...S.card}}>
            <div style={{...S.lbl}}>SIGNAL BRING-OUT STRATEGY</div>
            {result.signal_bringout && (
              <>
                <div style={{fontSize:12,color:"#94a3b8",marginBottom:8,lineHeight:1.6}}>{result.signal_bringout.strategy}</div>
                <div style={{display:"flex",gap:8,marginBottom:8}}>
                  <div style={{padding:"5px 10px",background:"rgba(2,8,23,0.5)",borderRadius:5,flex:1}}>
                    <div style={{...S.lbl,marginBottom:2}}>MUX LEVELS</div>
                    <div style={{...S.mono,fontSize:14,color:"#22d3ee"}}>{result.signal_bringout.mux_levels}</div>
                  </div>
                  <div style={{padding:"5px 10px",background:"rgba(2,8,23,0.5)",borderRadius:5,flex:1}}>
                    <div style={{...S.lbl,marginBottom:2}}>PIN BUDGET</div>
                    <div style={{...S.mono,fontSize:14,color:"#22d3ee"}}>{result.signal_bringout.pin_budget}</div>
                  </div>
                </div>
                <div style={{...S.lbl}}>CONTROL REGISTERS</div>
                <div style={{display:"flex",flexWrap:"wrap",gap:4}}>
                  {result.signal_bringout.control_regs?.map(r=><span key={r} style={S.badge("#22d3ee")}>{r}</span>)}
                </div>
              </>
            )}
          </div>

          {/* Process corners */}
          <div style={{...S.card}}>
            <div style={{...S.lbl}}>PROCESS CORNERS</div>
            <div style={{display:"flex",flexWrap:"wrap",gap:4,marginBottom:10}}>
              {result.process_corners?.map(c=><span key={c} style={S.badge("#64748b")}>{c}</span>)}
            </div>
            <div style={{...S.lbl}}>TEST COMPONENTS</div>
            <ul style={{margin:0,padding:"0 0 0 14px",color:"#94a3b8",fontSize:11,lineHeight:2}}>
              {result.test_components?.map(t=><li key={t}>{t}</li>)}
            </ul>
          </div>

          {/* Risks */}
          <div style={{...S.card}}>
            <div style={{...S.lbl}}>RISKS</div>
            <ul style={{margin:0,padding:"0 0 0 14px",color:"#f97316",fontSize:11,lineHeight:2}}>
              {result.risks?.map(r=><li key={r}>{r}</li>)}
            </ul>
          </div>

          {/* SpecKG update */}
          <div style={{...S.card}}>
            <div style={{...S.lbl}}>SPECKG UPDATE PAYLOAD</div>
            <pre style={{...S.mono,fontSize:10,color:"#a78bfa",margin:0,whiteSpace:"pre-wrap",lineHeight:1.8}}>{JSON.stringify(result.speckg_update,null,2)}</pre>
          </div>
        </div>
      )}

      {result?.raw && (
        <div style={{...S.card,...S.mono,fontSize:11,color:"#94a3b8",whiteSpace:"pre-wrap"}}>{result.raw}</div>
      )}

      {/* Follow-up chat */}
      {chatHistory.length > 0 && (
        <div style={{...S.card}}>
          <div style={{...S.lbl}}>FOLLOW-UP CHAT</div>
          <div style={{...S.scrollbox,maxHeight:200,marginBottom:8}}>
            {chatHistory.slice(2).map((m,i)=>(
              <div key={i} style={{marginBottom:8,borderLeft:`2px solid ${m.role==="user"?"#f59e0b":"#22d3ee"}`,paddingLeft:10}}>
                <div style={{fontSize:9,color:m.role==="user"?"#f59e0b":"#22d3ee",letterSpacing:1,marginBottom:3}}>{m.role.toUpperCase()}</div>
                <div style={{fontSize:12,color:"#94a3b8",lineHeight:1.6,whiteSpace:"pre-wrap"}}>{m.content}</div>
              </div>
            ))}
          </div>
          <div style={{display:"flex",gap:8}}>
            <input value={followUp} onChange={e=>setFollowUp(e.target.value)}
              onKeyDown={e=>{if(e.key==="Enter")sendFollowUp();}}
              placeholder="Ask a follow-up about this parameter…" style={S.inp}/>
            <button onClick={sendFollowUp} disabled={chatLoading||!followUp.trim()} style={{...S.btn(false,"#22d3ee"),whiteSpace:"nowrap"}}>
              {chatLoading?<Spinner color="#22d3ee"/>:"SEND"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 3 — DESIGN AUTOMATION (SKILL / pyHDL)
// ═══════════════════════════════════════════════════════════════════════════════
function DesignAutomation({ nodes }) {
  const [veil, setVeil]    = useState("analog");
  const [selId, setSelId]  = useState("");
  const [loading, setLoading] = useState(false);
  const [code, setCode]    = useState("");
  const [copied, setCopied]= useState(false);

  const filtered = nodes.filter(n => veil==="analog" ? n.domain!=="digital" : n.domain!=="analog");
  const node = filtered.find(n=>n.id===selId);

  const generate = async () => {
    if (!node) return;
    setLoading(true); setCode("");
    const isAnalog = veil==="analog";
    const sys = isAnalog
      ? "You are a Cadence SKILL expert. Output ONLY SKILL script code with detailed inline comments. No markdown."
      : "You are a pyHDL/SystemVerilog RTL expert. Output ONLY Python pyHDL code with inline comments. No markdown.";
    const prompt = isAnalog
      ? `Write a Cadence SKILL script that adds testability infrastructure to the ${node.label} analog block (${node.desc}, ${node.value} ${node.unit}, IP: ${node.ip}).
Include: (1) signal tap creation at key internal nodes, (2) trim switch insertion with ${node.trim?"8-bit":"bypass"} control, (3) observation MUX routing to DFT_OUT pin, (4) specKG node "${node.id}" comment tags on every function. Use real SKILL syntax (db, hi, ge functions).`
      : `Write pyHDL Python code for DFT control logic for ${node.label} (${node.desc}, ${node.value} ${node.unit}, IP: ${node.ip}).
Include: (1) MuxSelect register at address 0x${Math.floor(Math.random()*0xFF).toString(16).padStart(2,"0").toUpperCase()}, (2) scan chain hook signal, (3) trim DAC control if applicable (${node.trim}), (4) specKG node "${node.id}" tags in comments. Use realistic pyHDL/migen-style syntax.`;
    let out = "";
    await streamClaude([{role:"user",content:prompt}], sys, t=>{setCode(t);out=t;}, ()=>setLoading(false));
  };

  const copy = () => { navigator.clipboard?.writeText(code); setCopied(true); setTimeout(()=>setCopied(false),1500); };

  return (
    <div style={{display:"flex",flexDirection:"column",gap:12}}>
      <div style={{display:"flex",gap:8}}>
        <button onClick={()=>{setVeil("analog");setSelId("");setCode("");}} style={{...S.btn(veil==="analog","#f59e0b")}}>ANALOGVEIL — CADENCE SKILL</button>
        <button onClick={()=>{setVeil("digital");setSelId("");setCode("");}} style={{...S.btn(veil==="digital","#22d3ee")}}>DIGITALVEIL — pyHDL RTL</button>
      </div>
      <div style={{...S.card}}>
        <div style={{...S.lbl}}>SELECT {veil==="analog"?"ANALOG/MIXED-SIGNAL":"DIGITAL/MIXED-SIGNAL"} NODE</div>
        <div style={{display:"flex",gap:6,flexWrap:"wrap",marginTop:8}}>
          {filtered.map(n=>(
            <button key={n.id} onClick={()=>setSelId(n.id)} style={{...S.btn(selId===n.id, veil==="analog"?"#f59e0b":"#22d3ee"),fontSize:10,padding:"5px 12px"}}>
              {n.label}{n.trim&&" ✦"}
            </button>
          ))}
        </div>
        {node && (
          <div style={{marginTop:10,display:"flex",gap:10,alignItems:"center",padding:"8px 12px",background:"rgba(2,8,23,0.5)",borderRadius:6,flexWrap:"wrap"}}>
            <span style={{...S.mono,fontSize:11,color:DOMAIN_COLOR[node.domain]}}>{node.label}</span>
            <span style={{fontSize:11,color:"#64748b",flex:1}}>{node.desc} • {node.value} {node.unit}</span>
            {node.trim && <span style={S.badge("#a78bfa")}>TRIM-CAPABLE</span>}
            <span style={S.badge(TRING[node.testability])}>{node.testability}</span>
            <button onClick={generate} disabled={loading} style={{...S.btn(false,veil==="analog"?"#f59e0b":"#22d3ee")}}>
              {loading?<><Spinner color={veil==="analog"?"#f59e0b":"#22d3ee"}/>&nbsp;GENERATING…</>:`▶ GENERATE ${veil==="analog"?"SKILL":"pyHDL"}`}
            </button>
          </div>
        )}
      </div>

      {code && (
        <div style={{...S.card,padding:0,overflow:"hidden"}}>
          <div style={{padding:"8px 14px",borderBottom:"1px solid rgba(148,163,184,0.1)",display:"flex",alignItems:"center",gap:8,background:"rgba(2,8,23,0.4)"}}>
            <span style={{...S.lbl,marginBottom:0}}>GENERATED {veil==="analog"?"SKILL SCRIPT":"pyHDL MODULE"} — {node?.label}</span>
            <span style={{flex:1}}/>
            <span style={S.badge("#64748b")}>specKG:{node?.id}</span>
            <button onClick={copy} style={{...S.btn(copied,"#10b981"),padding:"3px 10px",fontSize:9}}>{copied?"✓ COPIED":"COPY"}</button>
          </div>
          <pre style={{...S.mono,color: veil==="analog"?"#f59e0b":"#22d3ee",margin:0,padding:"14px 16px",whiteSpace:"pre-wrap",fontSize:12,lineHeight:1.8,maxHeight:440,overflowY:"auto"}}>{code}</pre>
        </div>
      )}

      {!code && !loading && (
        <div style={{...S.card,display:"flex",alignItems:"center",justifyContent:"center",height:120,color:"#334155",fontSize:12}}>
          Select a node and click Generate to produce {veil==="analog"?"Cadence SKILL":"pyHDL"} code
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 4 — VERIFICATION PLAN
// ═══════════════════════════════════════════════════════════════════════════════
function VerifPlan({ nodes }) {
  const [sel, setSel] = useState([]);
  const [loading, setLoading] = useState(false);
  const [plan, setPlan] = useState("");
  const toggle = id => setSel(s=>s.includes(id)?s.filter(x=>x!==id):[...s,id]);
  const selAll = () => setSel(nodes.map(n=>n.id));
  const selGBT = () => setSel(nodes.filter(n=>n.testability==="GBT").map(n=>n.id));

  const generate = async () => {
    if (!sel.length) return;
    setLoading(true); setPlan("");
    const selNodes = nodes.filter(n=>sel.includes(n.id));
    const sys = "You are a verification architect for mixed-signal ICs. Write thorough, structured verification plans with numbered sections.";
    const prompt = `Write a complete verification plan for the following SpecKG nodes:
${selNodes.map(n=>`• ${n.label} [${n.testability}${n.trim?" TRIM":""}] (${n.desc}, ${n.value} ${n.unit}, IP:${n.ip})`).join("\n")}

Structure your plan as:
1. ENVIRONMENT REQUIREMENTS — UVM components, interfaces, clocking
2. CONFIGURATION SEQUENCES — Register write order with address/value pairs, dependency chain
3. CHECKER LOGIC — Assertion descriptions, tolerance windows, self-checking TB
4. COVERAGE GOALS — Functional coverage points per GBT parameter, cross-coverage
5. PVT CORNER STRATEGY — Corner list, parameter sensitivity analysis
6. KNOWN RISKS & MITIGATIONS — Process variability, trim interactions
Be specific, technical, and reference specKG node IDs.`;
    await streamClaude([{role:"user",content:prompt}], sys, setPlan, ()=>setLoading(false));
  };

  return (
    <div style={{display:"flex",flexDirection:"column",gap:12}}>
      <div style={{...S.card}}>
        <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
          <div style={{...S.lbl,marginBottom:0}}>SELECT NODES</div>
          <button onClick={selAll} style={{...S.btn(false,"#10b981"),padding:"3px 10px",fontSize:9}}>ALL</button>
          <button onClick={selGBT} style={{...S.btn(false,"#10b981"),padding:"3px 10px",fontSize:9}}>GBT ONLY</button>
          <button onClick={()=>setSel([])} style={{...S.btn(false,"#64748b"),padding:"3px 10px",fontSize:9}}>CLEAR</button>
        </div>
        <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
          {nodes.map(n=>(
            <button key={n.id} onClick={()=>toggle(n.id)}
              style={{...S.btn(sel.includes(n.id),"#10b981"),fontSize:10,padding:"5px 11px"}}>
              <span style={{color:TRING[n.testability],marginRight:3,fontSize:8}}>●</span>{n.label}
            </button>
          ))}
        </div>
        <button onClick={generate} disabled={!sel.length||loading}
          style={{marginTop:10,...S.btn(sel.length>0,"#10b981"),padding:"8px 20px"}}>
          {loading?<><Spinner color="#10b981"/>&nbsp;GENERATING PLAN…</>:`▶ GENERATE VERIF PLAN (${sel.length} nodes)`}
        </button>
      </div>

      {plan && (
        <div style={{...S.card,color:"#e2e8f0",fontSize:13,lineHeight:1.9,whiteSpace:"pre-wrap",...S.scrollbox}}>
          {plan.split("\n").map((line,i)=>{
            const isHeader = /^\d+\.\s+[A-Z]/.test(line)||/^#{1,3}\s/.test(line);
            return <div key={i} style={{color:isHeader?"#f59e0b":"#94a3b8",fontWeight:isHeader?700:400,marginTop:isHeader?14:0,fontFamily:isHeader?"monospace":"inherit",letterSpacing:isHeader?0.5:0}}>{line}</div>;
          })}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 5 — TEST SEQUENCE BUILDER
// ═══════════════════════════════════════════════════════════════════════════════
function TestSequence({ nodes }) {
  const [sel, setSel]      = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult]= useState(null);
  const [raw, setRaw]      = useState("");
  const [view, setView]    = useState("steps");
  const toggle = id => setSel(s=>s.includes(id)?s.filter(x=>x!==id):[...s,id]);

  const generate = async () => {
    if (!sel.length) return;
    setLoading(true); setResult(null); setRaw("");
    const selNodes = nodes.filter(n=>sel.includes(n.id));
    const sys = `You are a senior ATE backend test engineer. Return ONLY valid JSON, no markdown.
Schema: { steps:[{step:number,category:"REG_WRITE"|"PIN_CTRL"|"MEASURE"|"MUX_CHECK"|"TRIM",action:string,register?:string,address?:string,value?:string,pin?:string,force?:string,timing?:string,device?:string,tolerance?:string,notes?:string}], mux_path_checks:string[], measurement_devices:[{param:string,device:string,range:string}], tester_constraints:{platform:string,timing_margin:string,limitations:string[]}, timing_summary:string }`;
    const prompt = `Generate a complete ATE backend test sequence for: ${selNodes.map(n=>`${n.label}(${n.value}${n.unit},${n.testability})`).join(", ")}.
Cover: all required register writes in dependency order, pin force/measure schedule, MUX path verification, measurement device assignments, tester platform constraints, timing margins.`;
    let out="";
    await streamClaude([{role:"user",content:prompt}], sys,
      t=>{setRaw(t);out=t;},
      ()=>{
        try{setResult(JSON.parse(out.replace(/```json|```/g,"").trim()));}catch{setResult({raw:out});}
        setLoading(false);
      }
    );
  };

  const catColor = { REG_WRITE:"#22d3ee", PIN_CTRL:"#a78bfa", MEASURE:"#10b981", MUX_CHECK:"#f59e0b", TRIM:"#f97316" };

  return (
    <div style={{display:"flex",flexDirection:"column",gap:12}}>
      <div style={{...S.card}}>
        <div style={{...S.lbl}}>SELECT PARAMETERS</div>
        <div style={{display:"flex",gap:6,flexWrap:"wrap",marginTop:8}}>
          {nodes.map(n=>(
            <button key={n.id} onClick={()=>toggle(n.id)}
              style={{...S.btn(sel.includes(n.id),"#f97316"),fontSize:10,padding:"5px 11px"}}>
              {n.label}
            </button>
          ))}
        </div>
        <button onClick={generate} disabled={!sel.length||loading}
          style={{marginTop:10,...S.btn(sel.length>0,"#f97316"),padding:"8px 20px"}}>
          {loading?<><Spinner color="#f97316"/>&nbsp;BUILDING SEQUENCE…</>:`▶ BUILD TEST SEQUENCE (${sel.length} params)`}
        </button>
      </div>

      {loading && raw && (
        <div style={{...S.card,...S.mono,fontSize:10,color:"#334155",whiteSpace:"pre-wrap",maxHeight:80,overflow:"hidden",opacity:0.6}}>{raw.slice(0,300)}…</div>
      )}

      {result && !result.raw && (
        <>
          <div style={{display:"flex",gap:8}}>
            {["steps","devices","tester","json"].map(v=>(
              <button key={v} onClick={()=>setView(v)} style={{...S.btn(view===v,"#f97316"),padding:"5px 14px",fontSize:10}}>{v.toUpperCase()}</button>
            ))}
          </div>

          {view==="steps" && (
            <div style={{display:"flex",flexDirection:"column",gap:6,...S.scrollbox}}>
              {result.steps?.map(s=>(
                <div key={s.step} style={{...S.card,padding:"10px 14px",display:"flex",gap:10,alignItems:"flex-start",borderLeft:`3px solid ${catColor[s.category]||"#64748b"}`}}>
                  <div style={{width:24,height:24,borderRadius:"50%",background:(catColor[s.category]||"#64748b")+"22",border:`1px solid ${catColor[s.category]||"#64748b"}`,display:"flex",alignItems:"center",justifyContent:"center",fontSize:10,color:catColor[s.category]||"#64748b",fontWeight:700,flexShrink:0}}>{s.step}</div>
                  <div style={{flex:1}}>
                    <div style={{display:"flex",gap:6,alignItems:"center",marginBottom:4}}>
                      <span style={S.badge(catColor[s.category]||"#64748b")}>{s.category}</span>
                      <span style={{fontSize:12,color:"#e2e8f0"}}>{s.action}</span>
                    </div>
                    <div style={{display:"flex",gap:5,flexWrap:"wrap"}}>
                      {s.register&&<span style={S.badge("#22d3ee")}>REG:{s.register}</span>}
                      {s.address&&<span style={S.badge("#475569")}>0x{s.address}</span>}
                      {s.value&&<span style={S.badge("#f59e0b")}>{s.value}</span>}
                      {s.pin&&<span style={S.badge("#a78bfa")}>PIN:{s.pin}</span>}
                      {s.force&&<span style={S.badge("#f97316")}>FORCE:{s.force}</span>}
                      {s.timing&&<span style={S.badge("#10b981")}>{s.timing}</span>}
                      {s.tolerance&&<span style={S.badge("#64748b")}>±{s.tolerance}</span>}
                      {s.device&&<span style={S.badge("#94a3b8")}>{s.device}</span>}
                    </div>
                    {s.notes&&<div style={{fontSize:10,color:"#475569",marginTop:4}}>{s.notes}</div>}
                  </div>
                </div>
              ))}
              {result.mux_path_checks?.length>0&&(
                <div style={{...S.card}}>
                  <div style={{...S.lbl}}>MUX PATH VERIFICATION</div>
                  <ul style={{margin:0,padding:"0 0 0 14px",color:"#f59e0b",fontSize:11,lineHeight:2}}>
                    {result.mux_path_checks.map(m=><li key={m}>{m}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          {view==="devices" && (
            <div style={{...S.card}}>
              <div style={{...S.lbl}}>MEASUREMENT DEVICE ASSIGNMENTS</div>
              <table style={{width:"100%",borderCollapse:"collapse",fontSize:12,marginTop:8}}>
                <thead><tr>{["PARAMETER","DEVICE","RANGE"].map(h=><th key={h} style={{...S.lbl,padding:"4px 8px",borderBottom:"1px solid #1e293b",textAlign:"left"}}>{h}</th>)}</tr></thead>
                <tbody>
                  {result.measurement_devices?.map((d,i)=>(
                    <tr key={i} style={{borderBottom:"1px solid rgba(30,41,59,0.5)"}}>
                      <td style={{padding:"6px 8px",color:"#f59e0b",...S.mono,fontSize:11}}>{d.param}</td>
                      <td style={{padding:"6px 8px",color:"#94a3b8",fontSize:11}}>{d.device}</td>
                      <td style={{padding:"6px 8px",color:"#22d3ee",...S.mono,fontSize:11}}>{d.range}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {view==="tester" && result.tester_constraints && (
            <div style={{...S.card}}>
              <div style={{...S.lbl}}>TESTER INTEGRATION PLAN</div>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8,marginBottom:12}}>
                {[["Platform",result.tester_constraints.platform],["Timing Margin",result.tester_constraints.timing_margin],["Summary",result.timing_summary]].map(([k,v])=>(
                  <div key={k} style={{padding:"8px 12px",background:"rgba(2,8,23,0.5)",borderRadius:5}}>
                    <div style={{...S.lbl,marginBottom:3}}>{k}</div>
                    <div style={{fontSize:12,color:"#e2e8f0",...S.mono}}>{v}</div>
                  </div>
                ))}
              </div>
              <div style={{...S.lbl}}>LIMITATIONS</div>
              <ul style={{margin:0,padding:"0 0 0 14px",color:"#f97316",fontSize:11,lineHeight:2}}>
                {result.tester_constraints.limitations?.map(l=><li key={l}>{l}</li>)}
              </ul>
            </div>
          )}

          {view==="json" && (
            <pre style={{...S.card,...S.mono,fontSize:10,color:"#22d3ee",whiteSpace:"pre-wrap",maxHeight:440,overflowY:"auto",margin:0}}>
              {JSON.stringify(result,null,2)}
            </pre>
          )}
        </>
      )}
      {result?.raw && <div style={{...S.card,...S.mono,fontSize:11,color:"#94a3b8",whiteSpace:"pre-wrap"}}>{result.raw}</div>}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 6 — RISK & TRACEABILITY
// ═══════════════════════════════════════════════════════════════════════════════
function RiskTrace({ nodes }) {
  const [loading, setLoading] = useState(false);
  const [gaps, setGaps]     = useState(null);
  const [hovNode, setHovNode]= useState(null);

  const svgW=560, svgH=320, pad=48;

  const riskData = nodes.map(n=>({
    ...n,
    cv: n.testability==="GBT" ? 50+n.risk*0.45 : 40+n.risk*0.3,
    pv: n.trim ? 40+n.risk*0.55 : 20+n.risk*0.4,
  }));

  const runGapAnalysis = async () => {
    setLoading(true); setGaps(null);
    const sys=`You are a DFT risk analyst. Return ONLY valid JSON: { gaps:[{node:string,risk:"HIGH"|"MED"|"LOW",issue:string,recommendation:string,priority:number}] }`;
    const prompt=`Analyze DFT coverage gaps for IC spec parameters: ${nodes.map(n=>`${n.label}(${n.testability},trim:${n.trim},layer:${n.layer.join("+")})`).join(", ")}.
Identify the 6 highest-risk gaps considering: missing veil coverage, trim interactions, GBD parameters that should be GBT, cross-domain dependencies.`;
    let out="";
    await streamClaude([{role:"user",content:prompt}],sys,t=>{out=t;},()=>{
      try{setGaps(JSON.parse(out.replace(/```json|```/g,"").trim()));}catch{setGaps({raw:out});}
      setLoading(false);
    });
  };

  const RISK_C = { HIGH:"#ef4444", MED:"#f97316", LOW:"#10b981" };

  return (
    <div style={{display:"flex",flexDirection:"column",gap:12}}>
      <div style={{display:"grid",gridTemplateColumns:"3fr 2fr",gap:12}}>
        {/* Risk Matrix */}
        <div style={{...S.card}}>
          <div style={{...S.lbl}}>RISK MATRIX — COVERAGE CONFIDENCE vs PROCESS VARIABILITY</div>
          <svg width="100%" viewBox={`0 0 ${svgW} ${svgH}`} style={{marginTop:4}}>
            {/* Quadrant backgrounds */}
            <rect x={pad} y={pad} width={(svgW-2*pad)/2} height={(svgH-2*pad)/2} fill="rgba(239,68,68,0.04)"/>
            <rect x={pad+(svgW-2*pad)/2} y={pad+(svgH-2*pad)/2} width={(svgW-2*pad)/2} height={(svgH-2*pad)/2} fill="rgba(16,185,129,0.04)"/>
            {/* Grid lines */}
            {[25,50,75].map(v=>(
              <g key={v}>
                <line x1={pad+(svgW-2*pad)*v/100} y1={pad} x2={pad+(svgW-2*pad)*v/100} y2={svgH-pad} stroke="#1e293b" strokeWidth={1} strokeDasharray="3,3"/>
                <line x1={pad} y1={svgH-pad-(svgH-2*pad)*v/100} x2={svgW-pad} y2={svgH-pad-(svgH-2*pad)*v/100} stroke="#1e293b" strokeWidth={1} strokeDasharray="3,3"/>
              </g>
            ))}
            <line x1={pad} y1={svgH-pad} x2={svgW-pad} y2={svgH-pad} stroke="#334155" strokeWidth={1.5}/>
            <line x1={pad} y1={pad} x2={pad} y2={svgH-pad} stroke="#334155" strokeWidth={1.5}/>
            <text x={svgW/2} y={svgH-8} textAnchor="middle" fill="#475569" fontSize={10} fontFamily="monospace">Coverage Confidence →</text>
            <text x={14} y={svgH/2} textAnchor="middle" fill="#475569" fontSize={10} fontFamily="monospace" transform={`rotate(-90,14,${svgH/2})`}>Process Variability →</text>
            {/* Quadrant labels */}
            {[["HIGH RISK",pad+8,pad+14,"#ef444455"],["LOW RISK",svgW-pad-40,svgH-pad-10,"#10b98155"]].map(([l,x,y,c])=>(
              <text key={l} x={x} y={y} fill={c} fontSize={9} fontFamily="monospace" letterSpacing={1}>{l}</text>
            ))}
            {/* Bubbles */}
            {riskData.map(n=>{
              const x=pad+(n.cv/100)*(svgW-2*pad);
              const y=svgH-pad-(n.pv/100)*(svgH-2*pad);
              const col=DOMAIN_COLOR[n.domain];
              const r=n.trim?13:8;
              const isHov=hovNode===n.id;
              return (
                <g key={n.id} style={{cursor:"pointer"}}
                  onMouseEnter={()=>setHovNode(n.id)} onMouseLeave={()=>setHovNode(null)}>
                  {isHov&&<circle cx={x} cy={y} r={r+6} fill={col+"11"} stroke={col} strokeWidth={1} opacity={0.5}/>}
                  <circle cx={x} cy={y} r={r} fill={col+"33"} stroke={col} strokeWidth={isHov?2:1.2}/>
                  <text x={x} y={y-r-3} textAnchor="middle" fill={col} fontSize={isHov?9:7} fontFamily="monospace">{n.label}</text>
                </g>
              );
            })}
          </svg>
          {hovNode && (()=>{ const n=nodes.find(x=>x.id===hovNode); return n?(
            <div style={{padding:"6px 10px",background:"rgba(2,8,23,0.7)",borderRadius:5,fontSize:11,color:"#94a3b8",marginTop:-6}}>
              <b style={{color:DOMAIN_COLOR[n.domain]}}>{n.label}</b> — {n.desc} • Risk: {n.risk}/100
            </div>
          ):null; })()}
        </div>

        {/* Traceability table */}
        <div style={{...S.card,...S.scrollbox}}>
          <div style={{...S.lbl}}>TRACEABILITY MATRIX</div>
          <table style={{width:"100%",borderCollapse:"collapse",fontSize:10,marginTop:8}}>
            <thead><tr>
              {["PARAM","AV","DV","DFT","VV","TV","DOC"].map(h=><th key={h} style={{...S.lbl,padding:"3px 4px",borderBottom:"1px solid #1e293b",textAlign:"center",fontSize:8}}>{h}</th>)}
            </tr></thead>
            <tbody>
              {nodes.map(n=>{
                const checks=["AnalogVeil","DigitalVeil","DFTVeil","VerifVeil","TestVeil","DocVeil"].map(v=>n.layer.includes(v));
                const score=checks.filter(Boolean).length;
                return (
                  <tr key={n.id} style={{borderBottom:"1px solid rgba(30,41,59,0.5)"}}>
                    <td style={{padding:"4px 4px",color:DOMAIN_COLOR[n.domain],...S.mono,fontSize:9}}>{n.label}</td>
                    {checks.map((v,i)=>(
                      <td key={i} style={{padding:"4px 4px",textAlign:"center"}}>
                        <span style={{color:v?"#10b981":"#1e293b",fontSize:12}}>{v?"✓":"·"}</span>
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* IP Reuse */}
      <div style={{...S.card}}>
        <div style={{...S.lbl}}>IP REUSE — PORTED DFT COVERAGE STATUS</div>
        <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:8,marginTop:8}}>
          {[
            {ip:"LDO",  ids:["vref","ibias","ldo_drop","psrr"],  status:"FULLY PORTED",   color:"#10b981"},
            {ip:"ADC",  ids:["adc_inl","adc_enob","snr","dnl"],  status:"PARTIAL — trim re-cal needed", color:"#f59e0b"},
            {ip:"PLL",  ids:["pll_lock","clk_freq"],              status:"PORTED — timing re-verify",    color:"#f97316"},
            {ip:"DFT",  ids:["scan_cov","reg_map","trim_dac"],    status:"NATIVE — no port needed",      color:"#22d3ee"},
          ].map(({ip,ids,status,color})=>(
            <div key={ip} style={{...S.card,padding:10,borderColor:color+"33"}}>
              <div style={{fontWeight:800,color,fontFamily:"monospace",fontSize:14,marginBottom:4}}>{ip}</div>
              <div style={{fontSize:9,color:"#64748b",marginBottom:8,lineHeight:1.5}}>{status}</div>
              <div style={{display:"flex",flexWrap:"wrap",gap:3}}>
                {ids.map(id=><span key={id} style={{...S.badge(color),fontSize:8}}>{id}</span>)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* AI Gap Analysis */}
      <div style={{...S.card}}>
        <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:8}}>
          <div style={{...S.lbl,marginBottom:0}}>AI-POWERED GAP ANALYSIS</div>
          <button onClick={runGapAnalysis} disabled={loading}
            style={{...S.btn(false,"#a78bfa"),padding:"6px 16px"}}>
            {loading?<><Spinner color="#a78bfa"/>&nbsp;ANALYZING…</>:"🧠 RUN GAP ANALYSIS"}
          </button>
        </div>
        {gaps && !gaps.raw && (
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
            {[...gaps.gaps].sort((a,b)=>a.priority-b.priority).map((g,i)=>(
              <div key={i} style={{...S.card,borderColor:RISK_C[g.risk]+"55",padding:12}}>
                <div style={{display:"flex",gap:6,alignItems:"center",marginBottom:6}}>
                  <span style={S.badge(RISK_C[g.risk])}>{g.risk}</span>
                  <span style={{...S.mono,color:"#f59e0b",fontSize:11}}>{g.node}</span>
                  <span style={{marginLeft:"auto",...S.mono,fontSize:9,color:"#475569"}}>P{g.priority}</span>
                </div>
                <div style={{fontSize:11,color:"#64748b",marginBottom:6,lineHeight:1.6}}>{g.issue}</div>
                <div style={{fontSize:11,color:"#22d3ee",lineHeight:1.5}}>→ {g.recommendation}</div>
              </div>
            ))}
          </div>
        )}
        {gaps?.raw && <div style={{...S.mono,color:"#94a3b8",fontSize:11,whiteSpace:"pre-wrap"}}>{gaps.raw}</div>}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// CHANGE IMPACT MODAL
// ═══════════════════════════════════════════════════════════════════════════════
function ImpactModal({ nodeId, nodes, edges, onClose }) {
  const [text, setText] = useState("");
  const [done, setDone] = useState(false);
  const node = nodes.find(n=>n.id===nodeId);
  const downstream = bfsDownstream(nodeId, edges);

  useEffect(()=>{
    if (!node) return;
    const affected = [...downstream].map(id=>nodes.find(n=>n.id===id)?.label).filter(Boolean);
    const sys="You are a DFT change impact analyst. Write a concise, actionable change impact report with numbered sections.";
    const prompt=`Change impact report for spec parameter: ${node.label} (${node.desc}, ${node.value} ${node.unit}, IP: ${node.ip})
Downstream affected nodes (${affected.length}): ${affected.join(", ")}

Write a structured report covering:
1. DFT RE-PLANNING REQUIRED — which tests must be re-planned
2. VERIFICATION RE-RUNS — which TB configs must rerun, corner priority
3. TEST SEQUENCE MODIFICATIONS — ATE register writes, timing changes
4. PDK/TRIM INTERACTIONS — calibration impacts, silicon correlation risk
5. DOCUMENTATION UPDATES — which DocVeil entries need revision
6. RISK LEVEL & GO/NO-GO RECOMMENDATION — overall assessment`;
    streamClaude([{role:"user",content:prompt}],sys,setText,()=>setDone(true));
  },[nodeId]);

  return (
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.8)",zIndex:1000,display:"flex",alignItems:"center",justifyContent:"center",padding:20}}>
      <div style={{...S.card,maxWidth:660,width:"100%",maxHeight:"82vh",display:"flex",flexDirection:"column",borderColor:"#f59e0b44"}}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:12,flexShrink:0}}>
          <div>
            <div style={{...S.lbl}}>CHANGE IMPACT REPORT</div>
            <div style={{display:"flex",gap:8,alignItems:"baseline"}}>
              <span style={{color:"#f59e0b",fontFamily:"monospace",fontSize:18,fontWeight:800}}>{node?.label}</span>
              <span style={{color:"#475569",fontSize:11}}>{downstream.size} downstream nodes affected</span>
            </div>
            <div style={{display:"flex",gap:4,marginTop:4}}>
              {[...downstream].slice(0,6).map(id=>{const n=nodes.find(x=>x.id===id);return n?<span key={id} style={S.badge(DOMAIN_COLOR[n.domain])}>{n.label}</span>:null;})}
              {downstream.size>6&&<span style={{...S.badge("#64748b")}}>{downstream.size-6} more</span>}
            </div>
          </div>
          <button onClick={onClose} style={{...S.btn(false,"#64748b"),padding:"4px 12px",flexShrink:0}}>✕</button>
        </div>
        <div style={{flex:1,overflowY:"auto",lineHeight:1.9,fontSize:12}}>
          {!done&&!text&&<div style={{color:"#475569",display:"flex",gap:8,alignItems:"center"}}><Spinner/> Generating impact analysis…</div>}
          {text.split("\n").map((line,i)=>{
            const isH=/^\d+\.\s+[A-Z]/.test(line)||/^#{1,3}\s/.test(line);
            return <div key={i} style={{color:isH?"#f59e0b":"#94a3b8",fontWeight:isH?700:400,marginTop:isH?12:0,fontFamily:isH?"monospace":"inherit"}}>{line}</div>;
          })}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ONBOARDING
// ═══════════════════════════════════════════════════════════════════════════════
function Onboarding({ onDismiss }) {
  const cards = [
    {icon:"⬡",  c:"#f59e0b", t:"SpecKG Explorer",      d:"Drag & interact with the force graph. Click nodes to inspect dependencies. Propagate change impact across all Veils."},
    {icon:"🧠", c:"#22d3ee", t:"DFT Planning AI",       d:"AI classifies GBT/GBD, recommends trim budgets, signal bring-out strategy, and writes back to SpecKG. Follow-up chat included."},
    {icon:"⚙️", c:"#a78bfa", t:"Design Automation",     d:"Generate Cadence SKILL stubs for AnalogVeil or pyHDL RTL for DigitalVeil, tagged to their originating SpecKG node."},
    {icon:"✓",  c:"#10b981", t:"Verification Plan",     d:"Multi-select nodes; AI generates UVM env, config sequences, checker logic, coverage goals, and PVT strategy."},
    {icon:"📋", c:"#f97316", t:"Test Sequence Builder",  d:"Produces ATE-ready sequences: register writes, pin schedules, MUX path checks, measurement devices, tester constraints."},
    {icon:"📊", c:"#64748b", t:"Risk & Traceability",   d:"Risk matrix scatter plot, traceability matrix, IP reuse panel, and AI gap analysis with prioritized recommendations."},
  ];
  return (
    <div style={{position:"fixed",inset:0,background:"rgba(2,8,23,0.95)",zIndex:2000,display:"flex",alignItems:"center",justifyContent:"center",padding:24}}>
      <div style={{maxWidth:720,width:"100%"}}>
        <div style={{textAlign:"center",marginBottom:30}}>
          <div style={{fontSize:10,letterSpacing:5,color:"#334155",marginBottom:10}}>SEMICONDUCTOR DFT INTELLIGENCE</div>
          <div style={{fontSize:30,fontWeight:900,color:"#f59e0b",fontFamily:"monospace",letterSpacing:3}}>DFT • E2E PLATFORM</div>
          <div style={{fontSize:12,color:"#334155",marginTop:8,letterSpacing:2}}>SPECKG BACKBONE • ANTHROPIC AI • FULL-STACK VERIFICATION</div>
        </div>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:10,marginBottom:28}}>
          {cards.map(c=>(
            <div key={c.t} style={{...S.card,padding:14,borderColor:c.c+"22",display:"flex",gap:10}}>
              <div style={{fontSize:22,flexShrink:0}}>{c.icon}</div>
              <div>
                <div style={{fontWeight:700,color:c.c,fontSize:12,marginBottom:4,fontFamily:"monospace"}}>{c.t}</div>
                <div style={{fontSize:10,color:"#475569",lineHeight:1.6}}>{c.d}</div>
              </div>
            </div>
          ))}
        </div>
        <div style={{textAlign:"center"}}>
          <button onClick={onDismiss} style={{...S.btn(true,"#f59e0b"),padding:"12px 40px",fontSize:13,letterSpacing:2}}>
            ▶ LAUNCH PLATFORM
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ROOT
// ═══════════════════════════════════════════════════════════════════════════════
export default function App() {
  const [tab, setTab]           = useState("explorer");
  const [impactId, setImpactId] = useState(null);
  const [onboarding, setOnboarding] = useState(true);

  const TABS = [
    {id:"explorer",   label:"⬡ SPECKG EXPLORER"},
    {id:"dft",        label:"🧠 DFT PLANNING"},
    {id:"automation", label:"⚙️ DESIGN AUTOMATION"},
    {id:"verif",      label:"✓ VERIF PLAN"},
    {id:"test",       label:"📋 TEST SEQUENCE"},
    {id:"risk",       label:"📊 RISK & TRACE"},
  ];

  return (
    <div style={{minHeight:"100vh",background:"#020817",color:"#e2e8f0",fontFamily:"'Inter','Segoe UI',system-ui,sans-serif"}}>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100%{opacity:0.2;r:28;} 50%{opacity:0.5;r:32;} }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width:5px; height:5px; }
        ::-webkit-scrollbar-track { background:#0f172a; }
        ::-webkit-scrollbar-thumb { background:#1e293b; border-radius:3px; }
        ::-webkit-scrollbar-thumb:hover { background:#334155; }
      `}</style>

      {onboarding && <Onboarding onDismiss={()=>setOnboarding(false)}/>}
      {impactId && <ImpactModal nodeId={impactId} nodes={INITIAL_NODES} edges={INITIAL_EDGES} onClose={()=>setImpactId(null)}/>}

      {/* Header */}
      <div style={{borderBottom:"1px solid rgba(148,163,184,0.08)",padding:"10px 20px",display:"flex",alignItems:"center",gap:14,background:"rgba(15,23,42,0.9)",position:"sticky",top:0,zIndex:100}}>
        <div style={{fontFamily:"monospace",fontWeight:900,fontSize:15,color:"#f59e0b",letterSpacing:3}}>DFT•E2E</div>
        <div style={{width:1,height:16,background:"#1e293b"}}/>
        <div style={{fontSize:9,color:"#334155",letterSpacing:2,fontWeight:700}}>INTELLIGENCE PLATFORM</div>
        <div style={{flex:1}}/>
        <div style={{display:"flex",gap:5,alignItems:"center"}}>
          {Object.entries(DOMAIN_COLOR).map(([d,c])=><span key={d} style={{...S.badge(c),fontSize:8}}>{d.toUpperCase()}</span>)}
          <span style={{...S.badge("#10b981"),fontSize:8}}>SPECKG v2</span>
          <span style={{...S.badge("#64748b"),fontSize:8}}>{INITIAL_NODES.length} NODES</span>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{borderBottom:"1px solid rgba(148,163,184,0.06)",padding:"0 20px",display:"flex",gap:2,background:"rgba(15,23,42,0.6)",overflowX:"auto"}}>
        {TABS.map(t=>(
          <button key={t.id} onClick={()=>setTab(t.id)} style={{
            padding:"9px 16px", fontSize:10, letterSpacing:1.5, fontWeight:700, cursor:"pointer",
            border:"none", background:"none", whiteSpace:"nowrap", transition:"all 0.15s",
            color: tab===t.id?"#f59e0b":"#475569",
            borderBottom: tab===t.id?"2px solid #f59e0b":"2px solid transparent",
          }}>{t.label}</button>
        ))}
      </div>

      {/* Content */}
      <div style={{padding:"20px",maxWidth:1400,margin:"0 auto"}}>
        {tab==="explorer"   && <SpecKGExplorer nodes={INITIAL_NODES} edges={INITIAL_EDGES} onImpact={setImpactId}/>}
        {tab==="dft"        && <DFTPlanning    nodes={INITIAL_NODES}/>}
        {tab==="automation" && <DesignAutomation nodes={INITIAL_NODES}/>}
        {tab==="verif"      && <VerifPlan      nodes={INITIAL_NODES}/>}
        {tab==="test"       && <TestSequence   nodes={INITIAL_NODES}/>}
        {tab==="risk"       && <RiskTrace      nodes={INITIAL_NODES}/>}
      </div>

      {/* Footer */}
      <div style={{borderTop:"1px solid rgba(148,163,184,0.06)",padding:"8px 20px",display:"flex",justifyContent:"space-between",fontSize:9,...S.mono,color:"#1e293b"}}>
        <span>specKG v2 • {INITIAL_NODES.length} nodes • {INITIAL_EDGES.length} edges • {INITIAL_NODES.filter(n=>n.trim).length} trim-capable</span>
        <span>analogVeil / digitalVeil / DFTVeil / VerifVeil / TestVeil / DocVeil • Claude Sonnet 4</span>
      </div>
    </div>
  );
}
