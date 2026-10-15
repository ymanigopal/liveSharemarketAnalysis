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
    st.caption("Edit quantities, buy prices, or add/remove rows directly inside the table. Click **Save & Recalculate** to update Gemini's context.")
    
    edited_df = st.data_editor(
        st.session_state.portfolio,
        num_rows="dynamic",
        use_container_width=True,
        key="portfolio_editor"
    )
    
    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        if st.button("💾 Save & Recalculate", type="primary"):
            st.session_state.portfolio = edited_df
            save_data(PORTFOLIO_FILE, edited_df.to_dict(orient="records"))
            st.cache_data.clear()
            st.toast("Portfolio saved! Recalculating live values...", icon="✅")

    # Fetch live valuation
    live_df = fetch_live_prices(st.session_state.portfolio, usd_inr)
    
    total_inv = live_df["Invested_INR"].sum()
    total_cur = live_df["Current_INR"].sum()
    overall_pnl = total_cur - total_inv
    overall_pnl_pct = round((overall_pnl / total_inv) * 100, 2) if total_inv > 0 else 0.0
    
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Invested (INR)", f"₹{total_inv:,.0f}")
    m2.metric("Current Portfolio Value", f"₹{total_cur:,.0f}", f"{overall_pnl_pct}% (₹{overall_pnl:,.0f})")
    us_val = live_df[live_df["Market"] == "US"]["Current_INR"].sum()
    us_weight = round((us_val / total_cur) * 100, 1) if total_cur > 0 else 0
    m3.metric("India vs US Split", f"{100 - us_weight:.1f}% IN / {us_weight:.1f}% US")
    m4.metric("Active Holdings", len(live_df))

    # Visual Charts & Live Data Table
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("#### Live Valuation & Daily Movers")
        st.dataframe(
            live_df[["Ticker", "Name", "Theme", "Qty", "Buy_Price", "Live_Price", "Day_Chg_%", "Current_INR", "Total_PnL_%"]],
            use_container_width=True,
            hide_index=True
        )
    with c2:
        st.markdown("#### Thematic Concentration Risk")
        fig = px.pie(live_df, values="Current_INR", names="Theme", hole=0.4)
        fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=320)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("🤖 Gemini Personal Analyst Engine")
    user_note = st.text_input("Ask Gemini a specific question or note a recent portfolio change (optional):", 
                              placeholder="e.g., I just added 50 shares of OLAELEC and trimmed DIXON. How does this affect my risk?")
    
    if st.button("🧠 Generate Daily Gemini Portfolio Report", type="primary"):
        if not gemini_key:
            st.error("Please enter your Gemini API Key in the left sidebar first.")
        else:
            with st.spinner("Gemini is analyzing your live holdings, thematic overlaps, and latest news..."):
                client = genai.Client(api_key=gemini_key)
                prompt = f"""
                Act as my personal stock market analyst. My horizon is 3-5 years and risk tolerance is high.
                Today's Date: {datetime.now().strftime('%Y-%m-%d')}
                Here is my current updated portfolio with live prices and INR valuations:
                {live_df.to_markdown(index=False)}
                
                Additional User Note: {user_note}
                
                Generate a concise, high-signal daily report covering:
                1. Portfolio Concentration & Thematic Overlap Alert (Check Semicon/EMS, Defence, AI, Crypto exposure).
                2. Stock-by-Stock Action Table (Classify recent momentum/developments as Positive, Neutral, or Negative, and recommend Hold / Review / Consider Reducing based on fundamentals).
                3. Top 3 Immediate Risks & Catalysts to watch this week.
                4. Direct answer to my Additional User Note (if provided), plus a short 120-word Executive Summary formatted specifically for a daily WhatsApp/SMS alert.
                """
                try:
                    response = client.models.generate_content(
                        model=model_choice,
                        contents=prompt
                    )
                    st.session_state.latest_ai_report = response.text
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"Gemini API Error: {e}")

# ==============================================================================
# SLIDE 2: STOCK RESULTS, EARNINGS & LATEST UPDATES
# ==============================================================================
with tab2:
    st.subheader("📰 Live Stock Results, Quarterly Financials & News Feed")
    col_s1, col_s2 = st.columns([1, 2])
    
    with col_s1:
        selected_ticker = st.selectbox("Select a Portfolio Stock to Inspect:", live_df["Ticker"].tolist())
        stock_obj = yf.Ticker(selected_ticker)
        
        st.markdown("#### Key Valuation & Balance Sheet Metrics")
        try:
            info = stock_obj.info
            metrics_data = {
                "Metric": ["Market Cap", "Trailing P/E", "Forward P/E", "ROE", "Debt to Equity", "52-Week High", "52-Week Low"],
                "Value": [
                    f"{info.get('marketCap', 'N/A'):,}" if isinstance(info.get('marketCap'), (int, float)) else "N/A",
                    str(info.get("trailingPE", "N/A")),
                    str(info.get("forwardPE", "N/A")),
                    f"{round(info.get('returnOnEquity', 0)*100, 2)}%" if info.get('returnOnEquity') else "N/A",
                    str(info.get("debtToEquity", "N/A")),
                    str(info.get("fiftyTwoWeekHigh", "N/A")),
                    str(info.get("fiftyTwoWeekLow", "N/A"))
                ]
            }
            st.table(pd.DataFrame(metrics_data))
        except Exception:
            st.info("Detailed valuation ratios unavailable for this ticker via Yahoo Finance feed.")

    with col_s2:
        st.markdown(f"#### Quarterly Income Statement & Results (`{selected_ticker}`)")
        try:
            q_fin = stock_obj.quarterly_income_stmt
            if q_fin is not None and not q_fin.empty:
                key_rows = [r for r in ["Total Revenue", "Operating Income", "EBITDA", "Net Income"] if r in q_fin.index]
                st.dataframe(q_fin.loc[key_rows], use_container_width=True)
            else:
                st.info("Quarterly table not directly populated in feed—use the Gemini Deep-Dive button below for latest filings.")
        except Exception:
            st.info("Quarterly financials unavailable in raw feed.")

        st.markdown(f"#### Latest News & Announcements (`{selected_ticker}`)")
        try:
            news_list = stock_obj.news
            if news_list:
                for item in news_list[:5]:
                    content = item.get("content", item)
                    title = content.get("title", "Market Update")
                    pub_date = str(content.get("pubDate", ""))
                    st.markdown(f"- **{title}** *(Published: {pub_date[:10]})*")
            else:
                st.write("No recent articles found in the default feed.")
        except Exception:
            st.write("Unable to load news feed.")

        if st.button(f"🔍 Ask Gemini to Summarize Latest Results & Filings for {selected_ticker}"):
            if not gemini_key:
                st.error("Enter your Gemini API Key in the sidebar first.")
            else:
                with st.spinner(f"Analyzing {selected_ticker} quarterly performance and order book..."):
                    client = genai.Client(api_key=gemini_key)
                    q_prompt = f"""
                    Provide a focused quarterly results and business update for {selected_ticker}.
                    Cover:
                    1. Latest quarterly revenue, profit growth, and margin trajectory.
                    2. Recent order wins, capex updates, or regulatory changes.
                    3. Whether the 3-5 year investment thesis is strengthened or weakened.
                    """
                    try:
                        res = client.models.generate_content(model=model_choice, contents=q_prompt)
                        st.markdown(res.text)
                    except Exception as e:
                        st.error(f"Gemini API Error: {e}")

# ==============================================================================
# SLIDE 3: WHATSAPP & SMS REMINDER MANAGER
# ==============================================================================
with tab3:
    st.subheader("📲 Daily WhatsApp & SMS Notification Center")
    st.caption("Add, modify, or toggle phone numbers below. Always include the country code (e.g., `+91` for India or `+1` for US).")
    
    contacts_df = pd.DataFrame(st.session_state.contacts)
    edited_contacts = st.data_editor(
        contacts_df,
        num_rows="dynamic",
        column_config={
            "Name": st.column_config.TextColumn("Recipient Name", required=True),
            "Phone": st.column_config.TextColumn("Phone Number (with +CountryCode)", required=True),
            "Channel": st.column_config.SelectboxColumn("Alert Channel", options=["WhatsApp", "SMS", "Both"], required=True),
            "Active": st.column_config.CheckboxColumn("Receive Daily Alerts?", default=True)
        },
        use_container_width=True,
        key="contacts_editor"
    )
    
    if st.button("💾 Save Recipient Phone Numbers"):
        st.session_state.contacts = edited_contacts.to_dict(orient="records")
        save_data(CONTACTS_FILE, st.session_state.contacts)
        st.success("Recipient phone numbers updated and saved!")

    st.divider()
    st.markdown("#### Dispatch Portfolio Digest Now")
    
    top_stock = live_df.sort_values('Current_INR', ascending=False).iloc[0]['Name'] if not live_df.empty else "N/A"
    default_msg = (
        f"📊 *Daily Portfolio Update ({datetime.now().strftime('%d %b %Y')})*\n"
        f"• Current Value: ₹{total_cur:,.0f}\n"
        f"• Overall PnL: ₹{overall_pnl:,.0f} ({overall_pnl_pct}%)\n"
        f"• Top Holding: {top_stock}\n\n"
    )
    if "latest_ai_report" in st.session_state:
        default_msg += "🧠 *Gemini Analyst Summary:*\n" + st.session_state.latest_ai_report[:600] + "..."
    else:
        default_msg += "💡 *Tip:* Generate a Gemini Report on Slide 1 first to include AI insights in this alert."

    custom_msg = st.text_area("Message Preview (Editable before sending):", value=default_msg, height=200)

    if st.button("🚀 Send WhatsApp / SMS Update to All Active Numbers", type="primary"):
        if not twilio_sid or not twilio_token:
            st.error("Please enter your Twilio Account SID and Auth Token in the sidebar.")
        else:
            try:
                twilio_client = Client(twilio_sid, twilio_token)
                active_recipients = [c for c in st.session_state.contacts if c.get("Active")]
                
                if not active_recipients:
                    st.warning("No active phone numbers selected! Check the 'Receive Daily Alerts?' box above.")
                
                for person in active_recipients:
                    phone = person["Phone"].strip()
                    channel = person["Channel"]
                    name = person["Name"]
                    
                    try:
                        if channel in ["WhatsApp", "Both"]:
                            msg = twilio_client.messages.create(
                                body=custom_msg,
                                from_=twilio_whatsapp_from,
                                to=f"whatsapp:{phone}"
                            )
                            st.success(f"WhatsApp alert sent to {name} ({phone}) — SID: {msg.sid}")
                            
                        if channel in ["SMS", "Both"]:
                            msg = twilio_client.messages.create(
                                body=custom_msg,
                                from_=twilio_sms_from,
                                to=phone
                            )
                            st.success(f"SMS alert sent to {name} ({phone}) — SID: {msg.sid}")
                    except Exception as e:
                        st.error(f"Failed to send alert to {name} ({phone}): {e}")
            except Exception as e:
                st.error(f"Twilio Client initialization error: {e}")
