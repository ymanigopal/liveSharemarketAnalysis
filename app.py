import streamlit as st
import pandas as pd
import yfinance as yf
from google import genai
from twilio.rest import Client
import plotly.express as px
import json
import os
from datetime import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Personal AI Stock Analyst", layout="wide", page_icon="📈")

PORTFOLIO_FILE = "my_portfolio.json"
CONTACTS_FILE = "phone_numbers.json"

# --- INITIALIZE DEFAULT PORTFOLIO (23 STOCKS) ---
DEFAULT_PORTFOLIO = [
    {"Ticker": "AVANTEL.NS", "Name": "Avantel", "Market": "IN", "Theme": "Defence", "Qty": 100, "Buy_Price": 150.0},
    {"Ticker": "BDL.NS", "Name": "Bharat Dynamics", "Market": "IN", "Theme": "Defence", "Qty": 50, "Buy_Price": 1200.0},
    {"Ticker": "CAMS.NS", "Name": "CAMS", "Market": "IN", "Theme": "Fin Services", "Qty": 20, "Buy_Price": 3500.0},
    {"Ticker": "CDSL.NS", "Name": "CDSL", "Market": "IN", "Theme": "Fin Services", "Qty": 50, "Buy_Price": 1400.0},
    {"Ticker": "KAYNES.NS", "Name": "Kaynes Tech", "Market": "IN", "Theme": "Semicon & EMS", "Qty": 15, "Buy_Price": 4200.0},
    {"Ticker": "KPITTECH.NS", "Name": "KPIT Tech", "Market": "IN", "Theme": "Auto Tech / Semicon", "Qty": 40, "Buy_Price": 1500.0},
    {"Ticker": "LEMONTREE.NS", "Name": "Lemon Tree Hotels", "Market": "IN", "Theme": "Hospitality", "Qty": 200, "Buy_Price": 130.0},
    {"Ticker": "MOSCHIP.NS", "Name": "MosChip Tech", "Market": "IN", "Theme": "Semicon & EMS", "Qty": 150, "Buy_Price": 210.0},
    {"Ticker": "OLAELEC.NS", "Name": "Ola Electric", "Market": "IN", "Theme": "EV / Auto", "Qty": 200, "Buy_Price": 95.0},
    {"Ticker": "PGEL.NS", "Name": "PG Electroplast", "Market": "IN", "Theme": "Semicon & EMS", "Qty": 80, "Buy_Price": 600.0},
    {"Ticker": "TATACAP.NS", "Name": "Tata Capital", "Market": "IN", "Theme": "Fin Services", "Qty": 100, "Buy_Price": 350.0},
    {"Ticker": "VAML.NS", "Name": "Vedanta Aluminium", "Market": "IN", "Theme": "Commodities", "Qty": 100, "Buy_Price": 280.0},
    {"Ticker": "VBL.NS", "Name": "Varun Beverages", "Market": "IN", "Theme": "Consumer", "Qty": 60, "Buy_Price": 600.0},
    {"Ticker": "VEDL.NS", "Name": "Vedanta Ltd", "Market": "IN", "Theme": "Commodities", "Qty": 100, "Buy_Price": 450.0},
    {"Ticker": "DIXON.NS", "Name": "Dixon Tech", "Market": "IN", "Theme": "Semicon & EMS", "Qty": 10, "Buy_Price": 12000.0},
    {"Ticker": "EIHOTEL.NS", "Name": "EIH (Oberoi)", "Market": "IN", "Theme": "Hospitality", "Qty": 80, "Buy_Price": 380.0},
    {"Ticker": "ETERNAL.NS", "Name": "Eternal (Zomato)", "Market": "IN", "Theme": "Quick Commerce", "Qty": 250, "Buy_Price": 240.0},
    {"Ticker": "HAL.NS", "Name": "Hindustan Aeronautics", "Market": "IN", "Theme": "Defence", "Qty": 25, "Buy_Price": 4200.0},
    {"Ticker": "INDIGO.NS", "Name": "InterGlobe (IndiGo)", "Market": "IN", "Theme": "Aviation", "Qty": 15, "Buy_Price": 4300.0},
    {"Ticker": "KALYANKJIL.NS", "Name": "Kalyan Jewellers", "Market": "IN", "Theme": "Consumer", "Qty": 60, "Buy_Price": 550.0},
    {"Ticker": "MSTR", "Name": "Strategy Inc", "Market": "US", "Theme": "Crypto Proxy", "Qty": 10, "Buy_Price": 180.0},
    {"Ticker": "ACN", "Name": "Accenture", "Market": "US", "Theme": "IT / AI Services", "Qty": 8, "Buy_Price": 330.0},
    {"Ticker": "NVDA", "Name": "NVIDIA", "Market": "US", "Theme": "Semicon & AI", "Qty": 20, "Buy_Price": 120.0}
]

def load_data(file_path, default_data):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception:
            return default_data
    return default_data

def save_data(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(load_data(PORTFOLIO_FILE, DEFAULT_PORTFOLIO))

if "contacts" not in st.session_state:
    st.session_state.contacts = load_data(CONTACTS_FILE, [
        {"Name": "Primary Number", "Phone": "+919876543210", "Channel": "WhatsApp", "Active": True}
    ])

# --- SIDEBAR: API & SETTINGS ---
with st.sidebar:
    st.header("🔑 API Configuration")
    gemini_key = st.secrets.get("GEMINI_API_KEY", "")
    if not gemini_key:
        gemini_key = st.text_input("Gemini API Key", type="password")
    
    model_choice = st.selectbox("Gemini Model", ["gemini-2.5-flash", "gemini-2.5-pro"])
    
    st.divider()
    st.subheader("📱 Twilio Alert Credentials")
    twilio_sid = st.text_input("Twilio Account SID")
    twilio_token = st.text_input("Twilio Auth Token", type="password")
    twilio_whatsapp_from = st.text_input("Twilio WhatsApp Sender", value="whatsapp:+14155238886")
    twilio_sms_from = st.text_input("Twilio SMS Number", value="+1234567890")
    
    st.divider()
    usd_inr = st.number_input("Live USD to INR Rate (₹)", value=88.75, step=0.1)

# --- LIVE MARKET DATA ENGINE ---
@st.cache_data(ttl=300)
def fetch_live_prices(df, fx_rate):
    updated_rows = []
    for _, row in df.iterrows():
        ticker = row["Ticker"]
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5d")
            if not hist.empty and len(hist) >= 2:
                ltp = round(float(hist["Close"].iloc[-1]), 2)
                prev = float(hist["Close"].iloc[-2])
                day_chg = round(((ltp - prev) / prev) * 100, 2)
            elif not hist.empty:
                ltp = round(float(hist["Close"].iloc[-1]), 2)
                day_chg = 0.0
            else:
                ltp = float(row["Buy_Price"])
                day_chg = 0.0
        except Exception:
            ltp = float(row["Buy_Price"])
            day_chg = 0.0
            
        mult = fx_rate if row["Market"] == "US" else 1.0
        inv_inr = round(float(row["Qty"]) * float(row["Buy_Price"]) * mult, 0)
        cur_inr = round(float(row["Qty"]) * ltp * mult, 0)
        pnl_pct = round(((cur_inr - inv_inr) / inv_inr) * 100, 2) if inv_inr > 0 else 0.0
        
        r_dict = row.to_dict()
        r_dict.update({
            "Live_Price": ltp,
            "Day_Chg_%": day_chg,
            "Invested_INR": inv_inr,
            "Current_INR": cur_inr,
            "Total_PnL_%": pnl_pct
        })
        updated_rows.append(r_dict)
    return pd.DataFrame(updated_rows)

# --- MAIN UI TABS ---
st.title("📊 Personal Stock Market & Gemini Analyst Hub")
tab1, tab2, tab3 = st.tabs([
    "💼 Slide 1: Portfolio & Gemini Analyst", 
    "📰 Slide 2: Earnings, Filings & Daily News", 
    "📲 Slide 3: WhatsApp & SMS Alert Manager"
])

# ==============================================================================
# SLIDE 1: INTERACTIVE PORTFOLIO & GEMINI AI ANALYST
# ==============================================================================
with tab1:
    st.subheader("1. Interactive Portfolio Editor")
    st.caption("Edit quantities, buy prices, or add/remove rows directly inside the table. Click Save & Recalculate to update Gemini context.")
