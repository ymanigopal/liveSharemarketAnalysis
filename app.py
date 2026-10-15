import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
with st.sidebar:
    st.header("⚙️ Configuration")
    if not gemini_key:
        gemini_key = st.text_input("Enter Gemini API Key", type="password")
        if not gemini_key:
            st.info("Add GEMINI_API_KEY to your Streamlit secrets or enter it above to enable AI features.")

    refresh_interval = st.slider("Live Refresh Rate (seconds)", 2, 10, 3)
    pause_updates = st.toggle("Pause Live Stream", value=False)
