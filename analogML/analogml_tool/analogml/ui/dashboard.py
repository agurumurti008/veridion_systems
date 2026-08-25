"""
ui/dashboard.py  —  AnalogML Streamlit Dashboard

Run with:  streamlit run analogml/ui/dashboard.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from analogml.data    import SyntheticCircuitDataset
from analogml.models  import AnalogMLModel, TechTransferAgent

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title   = "AnalogML",
    page_icon    = "🔌",
    layout       = "wide",
    initial_sidebar_state = "expanded"
)

# ── custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stSidebar"] { background: #0f172a; }
  [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
  h1 { color: #38bdf8; }
  h2 { color: #7dd3fc; }
  .metric-card {
    background: #1e293b;
    padding: 16px;
    border-radius: 10px;
    border-left: 3px solid #38bdf8;
    margin: 6px 0;
  }
</style>
""", unsafe_allow_html=True)


# ── header ────────────────────────────────────────────────────────────────────
st.title("🔌 AnalogML — Physics-Backed Multi-Fidelity Analog IC Design")
st.caption("Simulation-less analog specification prediction & inverse design")

# ── sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.header("Configuration")

topology  = st.sidebar.selectbox("Topology",
              ["ota_5t", "ota_folded", "ldo", "current_mirror"])
tech_node = st.sidebar.selectbox("Technology Node",
              ["180nm", "90nm", "65nm", "45nm", "28nm"])
n_samples = st.sidebar.slider("Training Samples", 50, 500, 200, 50)
model_mode = st.sidebar.selectbox("Model Mode", ["fast", "nn"])
seed      = st.sidebar.number_input("Random Seed", value=42)

train_btn = st.sidebar.button("🚀 Train Model", type="primary")

# ── session state ─────────────────────────────────────────────────────────────
if "model"    not in st.session_state: st.session_state.model    = None
if "X"        not in st.session_state: st.session_state.X        = None
if "Y"        not in st.session_state: st.session_state.Y        = None
if "x_names"  not in st.session_state: st.session_state.x_names  = []
if "y_names"  not in st.session_state: st.session_state.y_names  = []


# ── train ─────────────────────────────────────────────────────────────────────
if train_btn:
    with st.spinner(f"Generating {n_samples} synthetic {topology} circuits…"):
        synth = SyntheticCircuitDataset(seed=int(seed))
        X, Y, xn, yn = synth.generate(topology, n_samples, tech_node)
        st.session_state.update(X=X, Y=Y, x_names=xn, y_names=yn)

    with st.spinner("Training model…"):
        split = int(0.8 * len(X))
        perm  = np.random.default_rng(int(seed)).permutation(len(X))
        model = AnalogMLModel(mode=model_mode, output_names=yn)
        model.fit(X[perm[:split]], Y[perm[:split]], epochs=150)
        st.session_state.model = model

    st.success(f"✅  Model trained on {split} samples. "
               f"Final loss: {model.history['loss'][-1]:.5f}")


# ── tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Model Performance",
    "🔮 Predict Specs",
    "🎯 Inverse Design",
    "🔄 Tech Transfer",
])


# ─── TAB 1: Model Performance ─────────────────────────────────────────────────
with tab1:
    if st.session_state.model is None:
        st.info("Train a model first using the sidebar.")
    else:
        model  = st.session_state.model
        X, Y   = st.session_state.X, st.session_state.Y
        yn     = st.session_state.y_names

        # parity plots
        perm   = np.random.default_rng(99).permutation(len(X))
        split  = int(0.8*len(X))
        X_te   = X[perm[split:]]
        Y_te   = Y[perm[split:]]
        Y_pred = model.predict(X_te)

        n_out  = min(6, len(yn))
        cols   = st.columns(3)
        for i in range(n_out):
            yp = Y_pred[:, i]
            yt = Y_te[:, i]
            r2 = float(np.corrcoef(yt, yp)[0,1]**2)
            fig = px.scatter(x=yt, y=yp,
                             labels={"x":"True","y":"Predicted"},
                             title=f"{yn[i]}  (R²={r2:.3f})",
                             opacity=0.6, color_discrete_sequence=["#38bdf8"])
            mn, mx = float(yt.min()), float(yt.max())
            fig.add_trace(go.Scatter(x=[mn,mx], y=[mn,mx],
                                     mode="lines",
                                     line=dict(color="red", dash="dash"),
                                     name="Ideal"))
            fig.update_layout(height=280, margin=dict(l=20,r=10,t=35,b=20),
                              paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                              font_color="#e2e8f0")
            with cols[i % 3]:
                st.plotly_chart(fig, use_container_width=True)

        # training loss
        if model.history["loss"]:
            st.subheader("Training Loss")
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(y=model.history["loss"],
                                       name="Train Loss",
                                       line=dict(color="#38bdf8")))
            if model.history["val_loss"]:
                # sparse val_loss
                x_val = np.linspace(0, len(model.history["loss"]),
                                     len(model.history["val_loss"]))
                fig2.add_trace(go.Scatter(x=x_val,
                                           y=model.history["val_loss"],
                                           name="Val Loss",
                                           line=dict(color="#f97316")))
            fig2.update_layout(height=250, xaxis_title="Epoch",
                                yaxis_title="MSE",
                                paper_bgcolor="#0f172a",
                                plot_bgcolor="#1e293b",
                                font_color="#e2e8f0")
            st.plotly_chart(fig2, use_container_width=True)


# ─── TAB 2: Predict Specs ─────────────────────────────────────────────────────
with tab2:
    if st.session_state.model is None:
        st.info("Train a model first.")
    else:
        st.subheader("Enter Circuit Parameters")
        xn = st.session_state.x_names
        cols = st.columns(3)
        x_vals = []
        X_ref  = st.session_state.X
        for i, name in enumerate(xn):
            mn = float(X_ref[:, i].min())
            mx = float(X_ref[:, i].max())
            med = float(np.median(X_ref[:, i]))
            val = cols[i % 3].slider(name, mn, mx, med,
                                      format="%.3f", key=f"inp_{i}")
            x_vals.append(val)

        if st.button("⚡ Predict", type="primary"):
            x_inp  = np.array(x_vals, dtype=np.float32).reshape(1,-1)
            y_pred, y_std = st.session_state.model.predict_with_uncertainty(x_inp)
            y_pred = y_pred[0]; y_std = y_std[0]
            yn     = st.session_state.y_names

            st.subheader("Predicted Specs")
            c1, c2, c3 = st.columns(3)
            cols3 = [c1, c2, c3]
            for i, (name, yp, ys) in enumerate(zip(yn, y_pred, y_std)):
                cols3[i % 3].metric(label=name,
                                     value=f"{yp:.3f}",
                                     delta=f"±{ys:.3f}")


# ─── TAB 3: Inverse Design ────────────────────────────────────────────────────
with tab3:
    if st.session_state.model is None:
        st.info("Train a model first.")
    else:
        st.subheader("🎯 Specify Target Performance")
        yn    = st.session_state.y_names
        X_ref = st.session_state.X
        Y_ref = st.session_state.Y
        targets = {}
        tc = st.columns(3)
        for i, name in enumerate(yn[:6]):
            mn  = float(Y_ref[:, i].min())
            mx  = float(Y_ref[:, i].max())
            med = float(np.median(Y_ref[:, i]))
            v = tc[i % 3].number_input(name, value=round(float(med),2),
                                        key=f"tgt_{i}")
            targets[name] = v

        if st.button("🔍 Find Best Sizes", type="primary"):
            with st.spinner("Searching design space…"):
                x_best = st.session_state.model.recommend_sizes(
                    targets, X_candidates=X_ref)
            y_best = st.session_state.model.predict(
                x_best.reshape(1,-1))[0]

            st.subheader("Recommended Component Sizes")
            xn = st.session_state.x_names
            sc = st.columns(3)
            for i, (n, v) in enumerate(zip(xn, x_best)):
                sc[i%3].metric(n, f"{v:.3f}")

            st.subheader("Expected Performance")
            pc = st.columns(3)
            for i, (n, v) in enumerate(zip(yn, y_best)):
                delta_str = ""
                if n in targets:
                    diff = v - targets[n]
                    delta_str = f"{diff:+.3f}"
                pc[i%3].metric(n, f"{v:.3f}", delta=delta_str)


# ─── TAB 4: Tech Transfer ─────────────────────────────────────────────────────
with tab4:
    st.subheader("🔄 Technology Transfer")
    c1, c2 = st.columns(2)
    src_tech = c1.selectbox("Source Technology", ["180nm","90nm","65nm"], index=0)
    tgt_tech = c2.selectbox("Target Technology", ["90nm","65nm","45nm","28nm"],
                             index=0)

    if st.button("Compute Scaling Rules"):
        agent = TechTransferAgent(src_tech, tgt_tech)
        rules = agent.tech_scaling_rules()
        st.subheader(f"Dennard Scaling Rules: {src_tech} → {tgt_tech}")
        rc = st.columns(4)
        for i, (k, v) in enumerate(rules.items()):
            color = "normal" if abs(v-1) < 0.2 else ("inverse" if v < 0.8 else "off")
            rc[i%4].metric(k, f"×{v:.3f}")

        st.info("""
        **How to use**:
        1. Train a model on source technology circuits.
        2. Use `TechTransferAgent.transfer(X_src)` to map your source-tech
           feature vector to estimated target-tech features.
        3. Feed the result into an `AnalogMLModel` trained on target-tech data.
        4. The scaling rules above give rough first-order size adjustments.
        """)

st.divider()
st.caption("AnalogML v0.1.0 — Physics-Backed Multi-Fidelity Neural Models for Analog IC Design")
