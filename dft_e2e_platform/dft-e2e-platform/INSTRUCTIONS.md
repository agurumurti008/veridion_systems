# DFT E2E Intelligence Platform
## Complete Setup & Execution Guide

```
╔══════════════════════════════════════════════════════════════════╗
║   DFT • E2E INTELLIGENCE PLATFORM  v1.0                         ║
║   SpecKG Backbone • Anthropic Claude AI • Semiconductor DFT      ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Project Structure](#3-project-structure)
4. [Quick Start (5 minutes)](#4-quick-start)
5. [Running with API Proxy (Recommended)](#5-running-with-api-proxy)
6. [Running Standalone (Claude.ai / Artifacts)](#6-running-standalone)
7. [Platform Capabilities — How to Use Each Tab](#7-platform-capabilities)
8. [SpecKG Data Model](#8-speckg-data-model)
9. [Extending the Platform](#9-extending-the-platform)
10. [Troubleshooting](#10-troubleshooting)
11. [Production Deployment](#11-production-deployment)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    BROWSER (React)                       │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │SpecKG    │  │DFT       │  │Design    │  │Verif / │  │
│  │Explorer  │  │Planning  │  │Automation│  │Test /  │  │
│  │(SVG D3)  │  │(AI Chat) │  │(AI Code) │  │Risk    │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
│                       │                                  │
│              streamClaude() / callClaude()               │
└───────────────────────┼─────────────────────────────────┘
                        │ HTTP POST /v1/messages
                        ▼
           ┌────────────────────────┐
           │   server.js (Node)     │  ← injects ANTHROPIC_API_KEY
           │   localhost:3001       │
           └───────────┬────────────┘
                        │ HTTPS
                        ▼
           ┌────────────────────────┐
           │  api.anthropic.com     │
           │  claude-sonnet-4-...   │
           └────────────────────────┘
```

**Key design decisions:**
- **SpecKG** is a static seed graph (16 nodes, 20 edges) representing a real mixed-signal IC spec hierarchy. In production, replace with live data from your PDK/spec database.
- **All AI calls stream** — responses appear progressively using Server-Sent Events from Anthropic's streaming API.
- **No external graph library** — the force-directed layout is implemented in pure React + SVG with a custom spring simulation.
- **No state management library** — uses React `useState`/`useEffect` only.

---

## 2. Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Node.js | ≥ 18.x | `node --version` |
| npm | ≥ 9.x | `npm --version` |
| Anthropic API key | — | https://console.anthropic.com |

**Get an Anthropic API key:**
1. Go to https://console.anthropic.com/settings/keys
2. Click **Create Key**
3. Copy the key — it starts with `sk-ant-api03-...`
4. Make sure your account has Claude Sonnet 4 access (any paid tier works)

---

## 3. Project Structure

```
dft-e2e-platform/
├── public/
│   └── index.html          ← HTML shell with Google Fonts
├── src/
│   ├── index.js            ← React entry point
│   └── App.jsx             ← Entire platform (1200+ lines)
│                             ├── INITIAL_NODES (16 SpecKG nodes)
│                             ├── INITIAL_EDGES (20 cross-layer edges)
│                             ├── streamClaude()   — streaming API helper
│                             ├── SpecKGExplorer   — Tab 1: force graph
│                             ├── DFTPlanning      — Tab 2: AI planning
│                             ├── DesignAutomation — Tab 3: code gen
│                             ├── VerifPlan        — Tab 4: verif plan
│                             ├── TestSequence     — Tab 5: ATE sequence
│                             ├── RiskTrace        — Tab 6: risk matrix
│                             ├── ImpactModal      — change impact popup
│                             └── Onboarding       — first-load overlay
├── server.js               ← Anthropic API proxy (Node/http)
├── .env.example            ← Environment template
├── .gitignore
├── package.json
└── INSTRUCTIONS.md         ← This file
```

---

## 4. Quick Start

```bash
# ① Clone / unzip into your working directory
cd dft-e2e-platform

# ② Install dependencies
npm install

# ③ Set your API key
cp .env.example .env
# Edit .env and replace sk-ant-YOUR_KEY_HERE with your real key

# ④ Terminal A — start the API proxy
ANTHROPIC_API_KEY=sk-ant-api03-YOUR_KEY node server.js

# ④ Terminal B — start the React dev server
npm start

# ⑤ Open browser
open http://localhost:3000
```

That's it. The onboarding overlay appears on first load.

---

## 5. Running with API Proxy (Recommended)

The proxy server (`server.js`) keeps your API key out of browser memory.

### Terminal A — Proxy

```bash
# Export key then run
export ANTHROPIC_API_KEY="sk-ant-api03-xxxxxxxxxxxxxxxx"
node server.js

# Expected output:
# ✅  Anthropic API proxy running on http://localhost:3001
#     Forwarding to https://api.anthropic.com
#     API key: sk-ant-api03...xxxx
```

### Terminal B — React Dev Server

```bash
npm start
# Opens http://localhost:3000 automatically
```

### Configure React to use the proxy

The app is pre-configured to call `https://api.anthropic.com` directly.
To use your local proxy instead, edit `src/App.jsx` — find the `streamClaude` function and change:

```js
// BEFORE (direct — requires claude.ai artifact context)
const res = await fetch("https://api.anthropic.com/v1/messages", {
  headers: { "Content-Type": "application/json" },

// AFTER (via local proxy — use this for local development)
const res = await fetch("http://localhost:3001/v1/messages", {
  headers: { "Content-Type": "application/json" },
```

---

## 6. Running Standalone (Claude.ai / Artifacts)

The file `src/App.jsx` is a self-contained React component that runs directly
as a **Claude Artifact** with no build step required.

1. Open https://claude.ai
2. Start a new conversation
3. Paste the entire contents of `src/App.jsx` into your message like:

```
Create a React artifact with this code:

[paste App.jsx contents here]
```

Claude will render it as an interactive artifact. The Anthropic API calls work
automatically in the artifact sandbox — no API key setup needed.

---

## 7. Platform Capabilities — How to Use Each Tab

### Tab 1 — SpecKG Explorer

The force-directed knowledge graph of all 16 spec nodes.

| Action | How |
|--------|-----|
| Select a node | Click any circle |
| Inspect dependencies | Right panel shows downstream chain |
| Drag to reposition | Click + drag any node |
| Filter by domain | Click domain badge buttons (top toolbar) |
| Filter by testability | Click GBT / GBD buttons |
| Search nodes | Type in search box |
| Show edge type labels | Toggle EDGE LABELS button |
| Trigger change impact | Click **⚡ CHANGE IMPACT REPORT** in detail panel |

**Color legend:**
- 🟡 Amber nodes = Analog domain
- 🔵 Cyan nodes = Digital domain
- 🟣 Purple nodes = Mixed-signal domain
- 🟢 Outer ring = GBT (Good By Test)
- 🟠 Outer ring = GBD (Good By Design)
- 🟣 Small dot (top-right) = Trim-capable node

---

### Tab 2 — DFT Planning AI

AI-powered GBT/GBD classification and trim budget planning.

**Workflow:**
1. Click any parameter button (e.g., `VREF`, `ADC_INL`, `TRIM_DAC`)
2. Click **▶ RUN DFT AI ANALYSIS**
3. Watch the structured JSON result populate 6 cards:
   - Classification card (GBT/GBD with confidence bar)
   - Trim budget (resolution, range %, DAC bits)
   - Signal bring-out strategy (MUX levels, control registers, pin budget)
   - Process corners list
   - Test components & simulation implications
   - SpecKG update payload (ready to write back to the graph)
4. Use the **Follow-up Chat** to ask technical questions about the analysis

**AI system prompt context:** The model is told it is a DFT architect for analog/mixed-signal ICs and must return structured JSON.

---

### Tab 3 — Design Automation

Generates implementation stubs tagged to SpecKG nodes.

**AnalogVeil — Cadence SKILL:**
1. Select the ANALOGVEIL tab
2. Choose an analog or mixed-signal node
3. Click **▶ GENERATE SKILL**
4. Outputs SKILL code including:
   - `dbOpenCellViewByType` calls for schematic access
   - Signal tap creation at internal nodes
   - Trim switch instantiation
   - MUX routing to DFT_OUT
   - Comments linking to SpecKG node ID

**DigitalVeil — pyHDL:**
1. Select the DIGITALVEIL tab
2. Choose a digital or mixed-signal node
3. Click **▶ GENERATE pyHDL**
4. Outputs Python pyHDL/migen-style code including:
   - MuxSelect register with address
   - Scan chain hook signal
   - Trim DAC control (if trim-capable)
   - SpecKG node ID comment tags

Use the **COPY** button to copy output to clipboard.

---

### Tab 4 — Verification Plan Generator

Generates comprehensive UVM-style verification plans.

**Workflow:**
1. Click node buttons to multi-select (green = selected)
2. Use **ALL** or **GBT ONLY** shortcuts for bulk selection
3. Click **▶ GENERATE VERIF PLAN**
4. AI produces 6-section plan:
   1. Environment Requirements (UVM, interfaces, clocking)
   2. Configuration Sequences (register write order, dependencies)
   3. Checker Logic (assertions, tolerance windows, self-checking TB)
   4. Coverage Goals (functional coverage per GBT param, cross-coverage)
   5. PVT Corner Strategy (corners list, sensitivity analysis)
   6. Known Risks & Mitigations

Section headers render in amber monospace; body in slate gray.

---

### Tab 5 — Test Sequence Builder

Generates ATE-ready test sequences.

**Workflow:**
1. Select parameters (orange = selected)
2. Click **▶ BUILD TEST SEQUENCE**
3. Four view modes:
   - **STEPS** — color-coded step cards by category (REG_WRITE, PIN_CTRL, MEASURE, MUX_CHECK, TRIM)
   - **DEVICES** — measurement device assignment table
   - **TESTER** — tester platform constraints, timing margins, limitations
   - **JSON** — raw JSON for ingestion into ATE automation scripts

**Step categories color code:**
- 🔵 Cyan = REG_WRITE (register writes)
- 🟣 Purple = PIN_CTRL (pin force/measure)
- 🟢 Green = MEASURE (measurement steps)
- 🟡 Amber = MUX_CHECK (mux path verification)
- 🟠 Orange = TRIM (trim DAC operations)

---

### Tab 6 — Risk & Traceability Dashboard

**Risk Matrix (scatter plot):**
- X-axis: Coverage Confidence (higher = better covered)
- Y-axis: Process Variability Impact (higher = more sensitive)
- Bubble size: large = trim-capable node
- Hover a bubble to see node detail
- Bottom-left quadrant = HIGH RISK (low coverage, high variability)
- Top-right quadrant = LOW RISK

**Traceability Matrix:**
- Rows = spec parameters
- Columns = AnalogVeil, DigitalVeil, DFTVeil, VerifVeil, TestVeil, DocVeil
- ✓ = node is a member of that veil layer
- · = not covered

**IP Reuse Panel:**
Shows 4 IP blocks (LDO, ADC, PLL, DFT) with their ported SpecKG sub-graphs and coverage status.

**AI Gap Analysis:**
Click **🧠 RUN GAP ANALYSIS** to get AI-prioritized risk findings with:
- Risk level (HIGH / MED / LOW)
- SpecKG node identified
- Issue description
- Specific recommendation
- Priority number for sequencing remediation

---

### Change Impact Modal

Triggered from the SpecKG Explorer detail panel.

Shows a streaming AI report covering:
1. DFT Re-planning Required
2. Verification Re-runs Needed
3. Test Sequence Modifications
4. PDK/Trim Interactions
5. Documentation Updates
6. Risk Level & Go/No-Go Recommendation

---

## 8. SpecKG Data Model

Each node in `INITIAL_NODES` has this schema:

```js
{
  id:          string,   // unique identifier (e.g. "vref")
  label:       string,   // display name (e.g. "VREF")
  domain:      "analog" | "digital" | "mixed-signal",
  layer:       string[], // veil memberships (e.g. ["SpecCore","AnalogVeil","DFTVeil"])
  testability: "GBT" | "GBD",
  trim:        boolean,  // trim-capable flag
  value:       string,   // nominal spec value (e.g. "1.2V")
  unit:        string,   // unit string (e.g. "V")
  desc:        string,   // human-readable description
  ip:          string,   // IP block name (e.g. "LDO")
  risk:        number,   // 0–100 risk score for risk matrix
}
```

Each edge in `INITIAL_EDGES`:

```js
{
  source: string,   // node id
  target: string,   // node id
  type:   "drives" | "constrains" | "affects" | "depends" | "related" | "trims",
}
```

**Adding new nodes:**
```js
// In App.jsx, append to INITIAL_NODES:
{ id:"my_param", label:"MY_PARAM", domain:"analog", layer:["SpecCore","AnalogVeil","DFTVeil"],
  testability:"GBT", trim:true, value:"500mV", unit:"mV", desc:"My new parameter", ip:"MyIP", risk:65 }

// And edges:
{ source:"vref", target:"my_param", type:"constrains" }
```

---

## 9. Extending the Platform

### Add a new AI capability tab

1. Create a new function component:
```jsx
function MyNewTab({ nodes }) {
  const [result, setResult] = useState("");
  const run = async () => {
    await streamClaude(
      [{ role: "user", content: "Your prompt here" }],
      "Your system prompt here",
      setResult,
      () => console.log("done")
    );
  };
  return <div>...</div>;
}
```

2. Add to the `TABS` array in the `App` component:
```js
{ id: "mytab", label: "🔬 MY TAB" }
```

3. Add the render condition:
```jsx
{tab === "mytab" && <MyNewTab nodes={INITIAL_NODES} />}
```

### Connect to a real SpecKG backend

Replace `INITIAL_NODES` and `INITIAL_EDGES` with a fetch call:

```js
const [nodes, setNodes] = useState([]);
const [edges, setEdges] = useState([]);

useEffect(() => {
  fetch("https://your-speckg-api.com/v1/graph")
    .then(r => r.json())
    .then(d => { setNodes(d.nodes); setEdges(d.edges); });
}, []);
```

### Change the Claude model

In `streamClaude()` / `callClaude()`, change:
```js
model: "claude-sonnet-4-20250514",
// to:
model: "claude-opus-4-5",  // for higher quality
// or:
model: "claude-haiku-4-5-20251001",  // for lower cost/latency
```

---

## 10. Troubleshooting

### "Failed to fetch" / CORS error in browser
- Make sure `server.js` is running (`node server.js`)
- Make sure you edited `streamClaude()` to point to `http://localhost:3001/v1/messages`
- Check ANTHROPIC_API_KEY is set: `echo $ANTHROPIC_API_KEY`

### AI responses show raw JSON with parse errors
- The model occasionally wraps JSON in markdown fences despite instructions
- The code handles this with `.replace(/```json|```/g, "").trim()`
- If still failing, check the raw output in the `.raw` fallback display

### Graph nodes overlap or don't spread out
- Resize the browser window to trigger a ResizeObserver reflow
- The spring simulation runs for 400 ticks then stops; drag nodes to rearrange

### `npm install` fails
```bash
# Clear cache and retry
npm cache clean --force
rm -rf node_modules
npm install
```

### Port 3000 already in use
```bash
# React will ask to use 3001 — say no, then:
PORT=3002 npm start
# And update server.js to listen on 3002 too
```

### API key authentication error (401)
- Verify the key starts with `sk-ant-api03-`
- Check your Anthropic account has active credits
- Regenerate the key at https://console.anthropic.com/settings/keys

---

## 11. Production Deployment

### Build for production

```bash
npm run build
# Creates optimized build/ directory
```

### Deploy to Vercel

```bash
npm install -g vercel
vercel
# Follow prompts; set ANTHROPIC_API_KEY in Vercel dashboard
```

### Deploy to Netlify

```bash
npm install -g netlify-cli
netlify deploy --prod --dir=build
# Set ANTHROPIC_API_KEY in Netlify environment variables
```

### ⚠️ Security Note for Production

In production you **must** use a server-side proxy (like `server.js`) or a
serverless function (Vercel API route / Netlify function) to inject your API
key. Never expose the key in client-side JavaScript.

Example Vercel API route (`api/claude.js`):
```js
export default async function handler(req, res) {
  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': process.env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify(req.body),
  });
  const data = await response.json();
  res.json(data);
}
```

Then in `App.jsx`, change the fetch URL to `/api/claude`.

---

## Support & Contribution

This platform is built on:
- **SpecKG** — analogVeil / digitalVeil surrogate modeling framework
- **Anthropic Claude** — `claude-sonnet-4-20250514`
- **React 18** — hooks-based UI
- **Pure SVG** — force-directed graph without D3

For questions about the SpecKG data model and three-phase surrogate architecture,
refer to the `speckg_complete_v2` codebase documentation (ARCHITECTURE.md, INSTRUCTIONS.md).
