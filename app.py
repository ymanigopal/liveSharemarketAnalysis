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
    if not gemini_
