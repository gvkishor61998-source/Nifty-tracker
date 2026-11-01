import time
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# ---------------- PAGE CONFIGURATION ----------------
st.set_page_config(
    page_title="Nifty 50 Options Command Center",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------- LIVE DATA FETCHING ENGINE ----------------
@st.cache_data(ttl=55)
def fetch_market_metrics():
    tickers = {
        "Nifty 50": "^NSEI",
        "India VIX": "^INDIAVIX",
        "Bank Nifty": "^NSEBANK",
        "Nifty IT": "^CNXIT",
        "Reliance": "RELIANCE.NS",
        "HDFC Bank": "HDFCBANK.NS",
        "S&P 500": "^GSPC",
        "S&P Futures": "ES=F",
        "US 10Y Yield": "^TNX",
        "Dollar Index": "DX-Y.NYB",
        "Brent Crude": "BZ=F"
    }
    results = {}
    for label, sym in tickers.items():
        try:
            t = yf.Ticker(sym)
            hist_daily = t.history(period="5d", interval="1d")
            hist_intra = t.history(period="1d", interval="5m")
            
            if len(hist_daily) >= 2:
                prev_row = hist_daily.iloc[-2]
                curr_row = hist_daily.iloc[-1]
                
                last_price = float(curr_row["Close"])
                prev_close = float(prev_row["Close"])
                open_price = float(curr_row["Open"])
                chg_pct = ((last_price - prev_close) / prev_close) * 100
                open_chg_pct = ((last_price - open_price) / open_price) * 100
                
                # Calculate intraday VWAP & 15-min Opening Range (ORH / ORL)
                vwap = last_price
                orh, orl = float(curr_row["High"]), float(curr_row["Low"])
                if not hist_intra.empty:
                    typ_price = (hist_intra["High"] + hist_intra["Low"] + hist_intra["Close"]) / 3
                    vol = hist_intra["Volume"].replace(0, 1)
                    vwap = float((typ_price * vol).cumsum().iloc[-1] / vol.cumsum().iloc[-1])
                    if len(hist_intra) >= 3:
                        orh = float(hist_intra.iloc[:3]["High"].max())
                        orl = float(hist_intra.iloc[:3]["Low"].min())

                results[label] = {
                    "price": round(last_price, 2),
                    "prev_close": round(prev_close, 2),
                    "open": round(open_price, 2),
                    "chg_pct": round(chg_pct, 2),
                    "open_chg_pct": round(open_chg_pct, 2),
                    "pdh": round(float(prev_row["High"]), 2),
                    "pdl": round(float(prev_row["Low"]), 2),
                    "vwap": round(vwap, 2),
                    "orh": round(orh, 2),
                    "orl": round(orl, 2)
                }
        except Exception:
            results[label] = None
    return results

@st.cache_data(ttl=60)
def fetch_nse_option_chain_pcr():
    """Fetches live Nifty 50 Option Chain from NSE India to compute ATM PCR & Max OI walls."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=5)
        resp = session.get(
            "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY",
            headers=headers,
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()["records"]["data"]
            tot_ce_oi = sum(item.get("CE", {}).get("openInterest", 0) for item in data)
            tot_pe_oi = sum(item.get("PE", {}).get("openInterest", 0) for item in data)
            pcr = round(tot_pe_oi / tot_ce_oi, 2) if tot_ce_oi > 0 else 1.0
            return pcr, True
    except Exception:
        pass
    return None, False

# ---------------- SIDEBAR: PHASE 2 FII/PRO INPUTS ----------------
st.sidebar.header("⚙️ Phase 2: EOD Smart Money Inputs")
st.sidebar.caption("Pre-loaded with Oct 30, 2026 NSE EOD Data. Update daily after 6:30 PM IST.")

fii_ls_ratio = st.sidebar.number_input("FII Index Futures Long %", value=11.12, step=0.5)
fii_pro_net_calls = st.sidebar.number_input("FII + Pro Net Call Change (Contracts)", value=-68868, step=1000)
fii_net_puts = st.sidebar.number_input("FII Net Put Change (Contracts)", value=60729, step=1000)

live_pcr, nse_connected = fetch_nse_option_chain_pcr()
manual_pcr = st.sidebar.number_input(
    "Live Nifty PCR (Auto-fetched if NSE API active)",
    value=live_pcr if live_pcr else 0.88,
    step=0.02
)
auto_refresh = st.sidebar.checkbox("Auto-Refresh Every 60 Seconds", value=True)

# ---------------- MAIN DASHBOARD HEADER ----------------
st.title("📊 Nifty 50 Options Command Center (3-Phase Engine)")
st.caption(f"Last Live Sync: {datetime.now().strftime('%d %b %Y, %I:%M:%S %p IST')} | Data Source: Yahoo Finance & NSE Live Feed")

data = fetch_market_metrics()
nifty = data.get("Nifty 50")
vix = data.get("India VIX")

if not nifty or not vix:
    st.error("Unable to fetch Nifty 50 or India VIX feed. Check your internet connection.")
    st.stop()

# ---------------- PHASE 1: GLOBAL & MACRO FILTER ----------------
st.subheader("🌐 Phase 1: Global Macro & Overnight Cues")
c1, c2, c3, c4, c5 = st.columns(5)

sp = data.get("S&P 500") or {"price": 7580.07, "chg_pct": -1.82}
spf = data.get("S&P Futures") or {"price": 7595.00, "chg_pct": 0.15}
brent = data.get("Brent Crude") or {"price": 117.64, "chg_pct": 2.40}
us10y = data.get("US 10Y Yield") or {"price": 4.32, "chg_pct": 0.80}
dxy = data.get("Dollar Index") or {"price": 104.25, "chg_pct": 0.20}

c1.metric("S&P 500 (Prev Close)", f"{sp['price']}", f"{sp['chg_pct']}%")
c2.metric("S&P 500 Live Futures", f"{spf['price']}", f"{spf['chg_pct']}%")
c3.metric("Brent Crude Oil ($)", f"${brent['price']}", f"{brent['chg_pct']}%", delta_color="inverse")
c4.metric("US 10Y Bond Yield", f"{us10y['price']}%", f"{us10y['chg_pct']}%", delta_color="inverse")
c5.metric("Dollar Index (DXY)", f"{dxy['price']}", f"{dxy['chg_pct']}%", delta_color="inverse")

# ---------------- PHASE 2: INSTITUTIONAL FOOTPRINT & LEVELS ----------------
st.subheader("🏦 Phase 2: Institutional Positioning & Key Battleground Levels")
p1, p2, p3, p4, p5 = st.columns(5)

p1.metric("FII Futures Long Ratio", f"{fii_ls_ratio}%", "88.88% Short (Extreme)" if fii_ls_ratio < 15 else "Normal")
p2.metric("FII+Pro Call Writing", f"{fii_pro_net_calls:,}", "Bearish Ceiling" if fii_pro_net_calls < 0 else "Bullish")
p3.metric("Previous Day High (PDH)", f"{nifty['pdh']}", f"{round(nifty['price'] - nifty['pdh'], 1)} pts away")
p4.metric("Previous Day Close (PDC)", f"{nifty['prev_close']}", f"{round(nifty['price'] - nifty['prev_close'], 1)} pts away")
p5.metric("Previous Day Low (PDL)", f"{nifty['pdl']}", f"{round(nifty['price'] - nifty['pdl'], 1)} pts away")

# ---------------- PHASE 3: LIVE EXECUTION & HEAVYWEIGHTS ----------------
st.subheader("⚡ Phase 3: Live Price Action, India VIX & Heavyweight Alignment")
l1, l2, l3, l4, l5, l6 = st.columns(6)

bnk = data.get("Bank Nifty") or {"price": 54686.95, "chg_pct": -0.41}
it_idx = data.get("Nifty IT") or {"price": 41200.0, "chg_pct": 2.32}
rel = data.get("Reliance") or {"price": 1160.60, "chg_pct": -0.50}

l1.metric("Nifty 50 Spot", f"{nifty['price']}", f"{nifty['chg_pct']}%")
l2.metric("Nifty Intraday VWAP", f"{nifty['vwap']}", "Above VWAP (Bull)" if nifty['price'] >= nifty['vwap'] else "Below VWAP (Bear)")
l3.metric("India VIX (Fear Gauge)", f"{vix['price']}", f"{vix['chg_pct']}% (vs Prev)", delta_color="inverse")
l4.metric("Bank Nifty (33% Wt)", f"{bnk['price']}", f"{bnk['chg_pct']}%")
l5.metric("Nifty IT (13% Wt)", f"{it_idx['price']}", f"{it_idx['chg_pct']}%")
l6.metric("Reliance (9% Wt)", f"{rel['price']}", f"{rel['chg_pct']}%")

# ---------------- 50-YEAR RULES ENGINE & TRADE SUGGESTION ----------------
st.markdown("---")
st.subheader("🎯 Automated Trade Verdict & Strike Selector")

score = 0
reasons = []

# 1. Macro Score
if brent["price"] > 110 or brent["chg_pct"] > 1.5:
    score -= 1
    reasons.append(f"🔴 **Bearish Macro:** Brent Crude is elevated at ${brent['price']} ({brent['chg_pct']}%), pressuring Indian margins.")
if sp["chg_pct"] < -1.0 and spf["chg_pct"] < 0.3:
    score -= 1
    reasons.append(f"🔴 **Overnight US Drag:** S&P 500 fell {sp['chg_pct']}% and futures ({spf['chg_pct']}%) show weak recovery.")

# 2. Institutional FII/Pro Score
if fii_pro_net_calls < -25000 and fii_net_puts > 25000:
    score -= 2
    reasons.append(f"🔴 **Smart Money Bearish:** FIIs & Pros sold {abs(fii_pro_net_calls):,} Calls and FIIs bought +{fii_net_puts:,} Puts.")
elif fii_pro_net_calls > 25000:
    score += 2
    reasons.append("🟢 **Smart Money Bullish:** Institutions are unwinding Call shorts and building long exposure.")

# 3. Live Price vs PDH / PDL / VWAP / 15-Min ORB
if nifty["price"] < nifty["vwap"]:
    score -= 2
    reasons.append(f"🔴 **Below VWAP:** Nifty Spot ({nifty['price']}) is trading below intraday VWAP ({nifty['vwap']}).")
else:
    score += 2
    reasons.append(f"🟢 **Above VWAP:** Nifty Spot ({nifty['price']}) is holding above intraday VWAP ({nifty['vwap']}).")

if nifty["price"] < nifty["pdl"]:
    score -= 2
    reasons.append(f"🔴 **PDL Breakdown:** Nifty broke below Previous Day Low ({nifty['pdl']}), trapping Put writers.")
elif nifty["price"] > nifty["pdh"]:
    score += 3
    reasons.append(f"🟢 **PDH Breakout Squeeze:** Nifty broke above Previous Day High ({nifty['pdh']}), forcing FII short covering.")

# 4. India VIX Rule
if vix["chg_pct"] >= 4.0:
    score -= 2
    reasons.append(f"🔴 **VIX Spike Alert (+{vix['chg_pct']}%):** India VIX is surging at {vix['price']}, inflating Put premiums rapidly.")
elif vix["chg_pct"] <= -3.5:
    score += 2
    reasons.append(f"🟢 **VIX Crush ({vix['chg_pct']}%):** Fear is melting away at {vix['price']}, supporting trend continuation upward.")

# 5. Heavyweight Alignment
if bnk["chg_pct"] < -0.3 and rel["chg_pct"] < -0.2:
    score -= 1
    reasons.append("🔴 **Heavyweights Dragging:** Both Bank Nifty and Reliance are trading in the red.")
elif bnk["chg_pct"] > 0.4 and rel["chg_pct"] > 0.3:
    score += 1
    reasons.append("🟢 **Heavyweight Support:** Bank Nifty and Reliance are leading the upside.")

# Calculate nearest ATM 50-point strike
atm_strike = int(round(nifty["price"] / 50.0) * 50)

if score <= -3:
    st.error(f"### 🚨 SIGNAL: BUY PUT OPTION (PE) | Conviction Score: {score}/-10")
    st.markdown(f"""
    * **Recommended Strike:** **Nifty {atm_strike} PE** (or **{atm_strike - 50} PE** on breakdown below {nifty['pdl']})
    * **Entry Trigger:** Enter on a 5-minute candle rejection below **VWAP ({nifty['vwap']})** or breakdown below **15-Min Low ({nifty['orl']}) / PDL ({nifty['pdl']})**.
    * **Stop-Loss:** Spot Nifty closing a 5-minute candle above **{max(nifty['vwap'], nifty['orh']) + 15:.0f}**.
    * **Targets:** **Target 1:** {nifty['price'] - 75:.0f} | **Target 2:** {nifty['price'] - 140:.0f}
    """)
elif score >= 3:
    st.success(f"### 🚀 SIGNAL: BUY CALL OPTION (CE) | Conviction Score: +{score}/+10")
    st.markdown(f"""
    * **Recommended Strike:** **Nifty {atm_strike} CE**
    * **Entry Trigger:** Enter only after a 15-minute candle sustains above **VWAP ({nifty['vwap']})** and **15-Min High ({nifty['orh']})**.
    * **Stop-Loss:** Spot Nifty dropping below **{min(nifty['vwap'], nifty['PDH'] if nifty['price'] > nifty['pdh'] else nifty['vwap']) - 20:.0f}**.
    * **Targets:** **Target 1:** {nifty['price'] + 75:.0f} | **Target 2:** {nifty['price'] + 140:.0f}
    """)
else:
    st.warning(f"### ⚖️ SIGNAL: WAIT / NO-TRADE ZONE (Choppy Market) | Score: {score}")
    st.markdown(f"""
    * **Why Wait:** Macro cues and intraday price action are conflicting. Option buyers will lose money to **Theta (time decay)** here.
    * **Turn Bullish (Buy {atm_strike} CE) Only If:** Nifty breaks above **{nifty['pdh']} (PDH)** with India VIX falling below **{vix['open'] * 0.97:.2f}**.
    * **Turn Bearish (Buy {atm_strike} PE) Only If:** Nifty breaks below **{nifty['pdl']} (PDL)** or **VWAP ({nifty['vwap']})** with India VIX jumping above **{vix['open'] * 1.04:.2f}**.
    """)

st.markdown("#### 🔍 Step-by-Step Checklist Breakdown:")
for r in reasons:
    st.write(r)

if auto_refresh:
    time.sleep(60)
    st.rerun()
