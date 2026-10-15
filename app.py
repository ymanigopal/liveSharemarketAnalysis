import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from google import genai
import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Cloud Pulse Dashboard",
    page_icon="⚡",
    layout="wide"
)

# --- GEMINI CLIENT SETUP ---
gemini_key = st.secrets.get("GEMINI_API_KEY", None)

with st.sidebar:
    st.header("⚙️ Configuration")
    if not gemini_key:
        gemini_key = st.text_input("Enter Gemini API Key", type="password")
        if not gemini_key:
            st.info("Add GEMINI_API_KEY to your Streamlit secrets or enter it above to enable AI features.")

    refresh_interval = st.slider("Live Refresh Rate (seconds)", 2, 10, 3)
    pause_updates = st.toggle("Pause Live Stream", value=False)

ai_client = genai.Client(api_key=gemini_key) if gemini_key else None

# --- STATE INITIALIZATION ---
if "metrics_history" not in st.session_state:
    now = datetime.datetime.now()
    st.session_state.metrics_history = pd.DataFrame([
        {
            "timestamp": now - datetime.timedelta(seconds=(10 - i) * 3),
            "throughput": 1200 + np.random.randint(-100, 100),
            "cpu": 45.0 + np.random.uniform(-5, 5),
            "p99_latency": 120 + np.random.randint(-10, 10)
        }
        for i in range(10)
    ])

# --- LIVE STREAM FRAGMENT ---
@st.fragment(run_every=f"{refresh_interval}s" if not pause_updates else None)
def live_dashboard_fragment():
    current_time = datetime.datetime.now()
    new_tp = int(st.session_state.metrics_history.iloc[-1]["throughput"] + np.random.randint(-40, 50))
    new_cpu = round(float(np.clip(st.session_state.metrics_history.iloc[-1]["cpu"] + np.random.uniform(-3, 3.5), 10, 99)), 1)
    new_latency = int(np.clip(st.session_state.metrics_history.iloc[-1]["p99_latency"] + np.random.randint(-6, 7), 50, 400))

    new_row = pd.DataFrame([{
        "timestamp": current_time,
        "throughput": max(new_tp, 100),
        "cpu": new_cpu,
        "p99_latency": new_latency
    }])
    
    st.session_state.metrics_history = pd.concat(
        [st.session_state.metrics_history.iloc[1:], new_row],
        ignore_index=True
    )
    df = st.session_state.metrics_history

    # Metric Cards
    col1, col2, col3, col4 = st.columns(4)
    tp_delta = df["throughput"].iloc[-1] - df["throughput"].iloc[-2]
    cpu_delta = round(df["cpu"].iloc[-1] - df["cpu"].iloc[-2], 1)
    lat_delta = df["p99_latency"].iloc[-1] - df["p99_latency"].iloc[-2]

    col1.metric("Throughput", f"{df['throughput'].iloc[-1]} req/s", delta=f"{tp_delta} req/s")
    col2.metric("CPU Utilization", f"{df['cpu'].iloc[-1]}%", delta=f"{cpu_delta}%", delta_color="inverse")
    col3.metric("p99 Latency", f"{df['p99_latency'].iloc[-1]} ms", delta=f"{lat_delta} ms", delta_color="inverse")
    col4.metric("Stream Status", "LIVE 🟢" if not pause_updates else "PAUSED ⏸️")

    # Real-Time Visualizations
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("📈 Throughput & Latency Trend")
        fig = px.line(df, x="timestamp", y=["throughput", "p99_latency"], markers=True)
        fig.update_layout(height=320, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("💻 CPU Utilization (%)")
        fig_cpu = px.area(df, x="timestamp", y="cpu", color_discrete_sequence=["#FF4B4B"])
        fig_cpu.update_layout(height=320, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_cpu, use_container_width=True)

# Main Screen
st.title("⚡ Cloud Pulse Live Dashboard")
live_dashboard_fragment()

# --- GEMINI COPILOT ---
st.divider()
st.subheader("🤖 Gemini Observability Copilot")

col_prompt, col_btn = st.columns([4, 1])
user_query = col_prompt.text_input(
    "Ask Gemini about system health or performance anomalies:",
    placeholder="e.g., Are there any latency spikes or resource bottlenecks?"
)
analyze_now = col_btn.button("✨ Ask Gemini", use_container_width=True)

if analyze_now:
    if not ai_client:
        st.error("Please provide a Gemini API Key to use the AI Copilot.")
    else:
        with st.spinner("Analyzing telemetry with Gemini..."):
            telemetry_snapshot = st.session_state.metrics_history.tail(5).to_dict(orient="records")
            prompt = f"""
            You are an expert cloud systems engineer.
            Recent telemetry snapshot:
            {telemetry_snapshot}

            User Question: {user_query or 'Summarize system health and highlight any anomalies.'}
            """
            try:
                response = ai_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                st.markdown("### 📋 AI Diagnostics")
                st.write(response.text)
            except Exception as e:
                st.error(f"Error querying Gemini: {e}")
